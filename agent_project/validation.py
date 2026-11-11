from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .case import ALLOWED_DOMAINS, Case, contains_cjk, is_specific_location

DEFAULT_ROLLOUTS = 8

DOMAIN_SLUGS = {
    "Mathematics": "math",
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Biology": "biology",
}

FILENAME_RE = re.compile(
    r"^(?P<batch>[A-Za-z0-9]+)_(?P<domain>math|mathematics|physics|chemistry|biology)"
    r"_(?P<count>\d+)_(?P<date>\d{8})\.jsonl$"
)

CASE_FIELDS = (
    "id",
    "source_title",
    "source_url",
    "domain",
    "subdomain",
    "file_path",
    "context",
    "question",
    "answer",
    "rubric",
    "design_rationale",
    "solution_steps",
    "evidence",
    "scoring_method",
    "human_review",
)

DELIVERY_FIELDS = CASE_FIELDS + (
    "trajectory",
    "rollout_35B_results",
    "average_accuracy",
)

TRAJECTORY_FIELDS = (
    "rollout_id",
    "setting",
    "messages",
    "tools",
    "extracted_answer",
    "evaluation",
    "usage",
    "tool_statistics",
    "statistics",
    "termination",
)

ROLLOUT_FIELDS = (
    "rollout_id",
    "setting",
    "messages",
    "extracted_answer",
    "answer-level_accuracy",
    "step-level_score",
    "usage",
)

ENGLISH_KEYS = {
    "source_title",
    "context",
    "question",
    "answer",
    "design_rationale",
}
CASE_OPTIONAL_FIELDS = {"context"}
OLD_FIELD_NAMES = {
    "data_id": "id",
    "standard_answer": "answer",
    "designation_rationale": "design_rationale",
    "trajectories": "trajectory",
}

_BAD_TEXT = re.compile("�|\x00")
_CONTROL = re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Issue:
    level: str
    code: str
    message: str
    location: str = ""

    def __str__(self) -> str:
        where = f" [{self.location}]" if self.location else ""
        return f"[{self.level}] {self.code}{where}: {self.message}"


def _issue(
    issues: list[Issue],
    level: str,
    code: str,
    message: str,
    location: str = "",
) -> None:
    issues.append(Issue(level=level, code=code, message=message, location=location))


def has_errors(issues: list[Issue]) -> bool:
    return any(item.level == "error" for item in issues)


def _check_text_integrity(value: Any, location: str, issues: list[Issue]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _check_text_integrity(item, f"{location}.{key}" if location else str(key), issues)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_text_integrity(item, f"{location}[{index}]", issues)
    elif isinstance(value, str):
        if _BAD_TEXT.search(value):
            _issue(
                issues,
                "error",
                "text_integrity",
                "text contains U+FFFD or NUL bytes (encoding was damaged)",
                location,
            )
        elif _CONTROL.search(value):
            _issue(
                issues,
                "error",
                "text_integrity",
                "text contains raw control characters",
                location,
            )


def _check_english(value: str, location: str, issues: list[Issue]) -> None:
    if contains_cjk(value):
        _issue(
            issues,
            "error",
            "english",
            "Chinese characters found; questions, answers and trajectories must be English",
            location,
        )


def _check_message_language(
    messages: list[dict], location: str, issues: list[Issue]
) -> None:
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            _issue(issues, "error", "message", "message must be an object", f"{location}[{index}]")
            continue
        role = message.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            _issue(
                issues,
                "error",
                "message.role",
                f"invalid role {role!r}",
                f"{location}[{index}]",
            )
        content = message.get("content")
        if isinstance(content, str):
            _check_english(content, f"{location}[{index}].content", issues)
            if "[truncated," in content:
                _issue(
                    issues,
                    "error",
                    "message.truncated",
                    "tool output is truncated; delivery trajectories must keep full content",
                    f"{location}[{index}].content",
                )
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str):
            _check_english(
                reasoning, f"{location}[{index}].reasoning_content", issues
            )


def validate_case_payload(
    raw: dict[str, Any] | Any,
    *,
    location: str = "",
) -> list[Issue]:
    """第一层：校验提交上来的题目数据本身是否符合 6.1 格式。"""
    issues: list[Issue] = []
    if not isinstance(raw, dict):
        _issue(issues, "error", "case.type", "case payload must be a JSON object", location)
        return issues

    for old, new in OLD_FIELD_NAMES.items():
        if old in raw:
            _issue(
                issues,
                "error",
                "field.old_name",
                f"field {old!r} is obsolete; use {new!r}",
                location,
            )

    for field in CASE_FIELDS:
        if field in CASE_OPTIONAL_FIELDS:
            continue
        if field not in raw:
            _issue(issues, "error", "field.missing", f"required field {field!r} is missing", location)

    if not str(raw.get("source_url", "")).strip():
        _issue(
            issues,
            "warning",
            "source_url.empty",
            "source_url is empty; record a URL, DOI or bibliographic reference",
            location,
        )

    for field in ENGLISH_KEYS:
        value = raw.get(field)
        if isinstance(value, str):
            _check_english(value, f"{location}.{field}", issues)

    steps = raw.get("solution_steps")
    if isinstance(steps, list):
        for index, step in enumerate(steps):
            if isinstance(step, str):
                _check_english(step, f"{location}.solution_steps[{index}]", issues)
    elif steps is not None:
        _issue(issues, "error", "solution_steps.type", "must be a list of strings", location)

    evidence = raw.get("evidence")
    if isinstance(evidence, list):
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                _issue(
                    issues,
                    "error",
                    "evidence.type",
                    "each evidence item must be an object",
                    f"{location}.evidence[{index}]",
                )
                continue
            for key in ("source", "location", "content"):
                if not str(item.get(key, "")).strip():
                    _issue(
                        issues,
                        "error",
                        "evidence.missing",
                        f"evidence item is missing {key!r}",
                        f"{location}.evidence[{index}]",
                    )
            loc = str(item.get("location", ""))
            if loc and not is_specific_location(loc):
                _issue(
                    issues,
                    "error",
                    "evidence.locator",
                    "location must name a concrete page, section, equation, problem or paragraph",
                    f"{location}.evidence[{index}]",
                )
            content = item.get("content")
            if isinstance(content, str):
                _check_english(content, f"{location}.evidence[{index}].content", issues)
    elif evidence is not None:
        _issue(issues, "error", "evidence.type", "must be a list", location)

    rubric = raw.get("rubric")
    if isinstance(rubric, dict):
        if rubric.get("total_points") != 10:
            _issue(
                issues,
                "error",
                "rubric.total_points",
                "total_points must be exactly 10",
                location,
            )
        criteria = rubric.get("criteria")
        if isinstance(criteria, list):
            total = 0
            for index, item in enumerate(criteria):
                if not isinstance(item, dict):
                    continue
                total += int(item.get("points", 0) or 0)
                description = item.get("description")
                if isinstance(description, str):
                    _check_english(
                        description,
                        f"{location}.rubric.criteria[{index}].description",
                        issues,
                    )
            if criteria and total != int(rubric.get("total_points", 0) or 0):
                _issue(
                    issues,
                    "error",
                    "rubric.points",
                    f"criteria points sum to {total}, expected total_points",
                    location,
                )
    elif rubric is not None:
        _issue(issues, "error", "rubric.type", "must be an object", location)

    method = raw.get("scoring_method")
    if isinstance(method, dict):
        if method.get("max_score") != 10:
            _issue(issues, "error", "scoring.max_score", "max_score must be 10", location)
        description = str(method.get("description", ""))
        _check_english(description, f"{location}.scoring_method.description", issues)

    review = raw.get("human_review")
    if isinstance(review, dict):
        for key in ("review_result", "modification"):
            value = review.get(key)
            if isinstance(value, str):
                _check_english(value, f"{location}.human_review.{key}", issues)

    domain = raw.get("domain")
    if domain and domain not in ALLOWED_DOMAINS:
        _issue(
            issues,
            "error",
            "domain",
            f"domain must be one of {sorted(ALLOWED_DOMAINS)}, got {domain!r}",
            location,
        )

    _check_text_integrity(raw, location, issues)

    if not has_errors(issues):
        try:
            Case.model_validate(raw)
        except ValidationError as exc:
            for error in exc.errors():
                where = ".".join(str(part) for part in error.get("loc", ()))
                _issue(
                    issues,
                    "error",
                    "case.schema",
                    str(error.get("msg", "invalid value")),
                    f"{location}.{where}".strip("."),
                )
    return issues


def _case_subset(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in CASE_FIELDS if key in record}


def _check_trajectory(
    record: dict[str, Any],
    *,
    issues: list[Issue],
) -> None:
    trajectory = record.get("trajectory")
    if not isinstance(trajectory, list) or not trajectory:
        _issue(
            issues,
            "error",
            "trajectory.missing",
            "trajectory must be a non-empty array of strong-model trajectories",
        )
        return

    for index, item in enumerate(trajectory):
        where = f"trajectory[{index}]"
        if not isinstance(item, dict):
            _issue(issues, "error", "trajectory.type", "must be an object", where)
            continue
        extra = set(item) - set(TRAJECTORY_FIELDS)
        if extra:
            _issue(
                issues,
                "error",
                "trajectory.extra_field",
                f"unexpected fields: {sorted(extra)}",
                where,
            )
        for field in TRAJECTORY_FIELDS:
            if field not in item:
                _issue(
                    issues,
                    "error",
                    "trajectory.missing_field",
                    f"missing field {field!r}",
                    where,
                )

        setting = item.get("setting") or {}
        if not str(setting.get("model_name", "")).strip():
            _issue(issues, "error", "setting.model_name", "model_name is required", where)
        for key in ("temperature", "top_p", "max_tokens"):
            if key not in setting:
                _issue(issues, "warning", "setting.field", f"missing {key}", where)

        messages = item.get("messages")
        if not isinstance(messages, list) or not messages:
            _issue(issues, "error", "trajectory.messages", "messages must be non-empty", where)
        else:
            _check_message_language(messages, f"{where}.messages", issues)
            assistants = [
                message
                for message in messages
                if isinstance(message, dict) and message.get("role") == "assistant"
            ]
            if not any(
                isinstance(message.get("reasoning_content"), str)
                and message.get("reasoning_content", "").strip()
                for message in assistants
            ):
                _issue(
                    issues,
                    "error",
                    "trajectory.reasoning",
                    "at least one assistant message must contain reasoning_content",
                    where,
                )
            if not any(message.get("tool_calls") for message in assistants):
                _issue(
                    issues,
                    "error",
                    "trajectory.tool_calls",
                    "at least one assistant message must contain tool_calls",
                    where,
                )
            if not any(
                isinstance(message, dict) and message.get("role") == "tool"
                for message in messages
            ):
                _issue(
                    issues,
                    "error",
                    "trajectory.observation",
                    "messages must contain at least one tool observation",
                    where,
                )

        tools = item.get("tools")
        if not isinstance(tools, list) or not tools:
            _issue(issues, "error", "trajectory.tools", "tools must be non-empty", where)
        else:
            for tool_index, tool in enumerate(tools):
                if not isinstance(tool, dict):
                    continue
                for key in ("type", "name", "description", "parameters"):
                    if key not in tool:
                        _issue(
                            issues,
                            "error",
                            "trajectory.tool_field",
                            f"tool is missing {key!r}",
                            f"{where}.tools[{tool_index}]",
                        )

        if not str(item.get("extracted_answer", "")).strip():
            _issue(
                issues,
                "warning",
                "trajectory.extracted_answer",
                "extracted_answer is empty",
                where,
            )

        evaluation = item.get("evaluation") or {}
        accuracy = evaluation.get("answer_level_accuracy")
        if accuracy not in (0, 1):
            _issue(
                issues,
                "error",
                "trajectory.evaluation.answer_level_accuracy",
                "must be 0 or 1",
                where,
            )
        score = evaluation.get("step_level_score")
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 10:
            _issue(
                issues,
                "error",
                "trajectory.evaluation.step_level_score",
                "must be between 0 and 10",
                where,
            )

        usage = item.get("usage") or {}
        for key in (
            "total_prompt_tokens",
            "total_reasoning_content_tokens",
            "total_content_tokens",
            "total_completion_tokens",
            "total_tokens",
        ):
            if not isinstance(usage.get(key), int):
                _issue(
                    issues,
                    "error",
                    "trajectory.usage",
                    f"usage.{key} must be an integer",
                    where,
                )

        stats = item.get("tool_statistics") or {}
        total_calls = stats.get("total_tool_calls")
        counts = stats.get("tool_call_counts")
        if not isinstance(total_calls, int) or total_calls < 1:
            _issue(
                issues,
                "error",
                "trajectory.tool_statistics",
                "total_tool_calls must be >= 1",
                where,
            )
        if isinstance(counts, dict) and isinstance(total_calls, int):
            if sum(int(value or 0) for value in counts.values()) != total_calls:
                _issue(
                    issues,
                    "warning",
                    "trajectory.tool_statistics",
                    "tool_call_counts does not sum to total_tool_calls",
                    where,
                )
        for key in ("successful_tool_calls", "failed_tool_calls"):
            if not isinstance(stats.get(key), int):
                _issue(
                    issues,
                    "warning",
                    "trajectory.tool_statistics",
                    f"missing integer {key}",
                    where,
                )

        statistics = item.get("statistics") or {}
        for key in ("total_rounds", "assistant_rounds", "tool_rounds"):
            if not isinstance(statistics.get(key), int):
                _issue(
                    issues,
                    "error",
                    "trajectory.statistics",
                    f"statistics.{key} must be an integer",
                    where,
                )

        termination = item.get("termination") or {}
        if not str(termination.get("type", "")).strip():
            _issue(issues, "error", "trajectory.termination", "type is required", where)
        if not str(termination.get("reason", "")).strip():
            _issue(issues, "error", "trajectory.termination", "reason is required", where)


def _check_rollouts(
    record: dict[str, Any],
    *,
    expect_rollouts: int,
    strict_model: bool,
    issues: list[Issue],
) -> None:
    rollouts = record.get("rollout_35B_results")
    if not isinstance(rollouts, list) or not rollouts:
        _issue(
            issues,
            "error",
            "rollout.missing",
            "rollout_35B_results must be a non-empty array",
        )
        return

    if expect_rollouts and len(rollouts) != expect_rollouts:
        _issue(
            issues,
            "error",
            "rollout.count",
            f"expected {expect_rollouts} rollouts, found {len(rollouts)}",
        )

    ids: list[int] = []
    accuracies: list[int] = []
    for index, item in enumerate(rollouts):
        where = f"rollout_35B_results[{index}]"
        if not isinstance(item, dict):
            _issue(issues, "error", "rollout.type", "must be an object", where)
            continue
        extra = set(item) - set(ROLLOUT_FIELDS)
        if extra:
            _issue(
                issues,
                "error",
                "rollout.extra_field",
                f"unexpected fields: {sorted(extra)}; use 6.1 field names",
                where,
            )
        for field in ROLLOUT_FIELDS:
            if field not in item:
                _issue(
                    issues,
                    "error",
                    "rollout.missing_field",
                    f"missing field {field!r}",
                    where,
                )

        rollout_id = item.get("rollout_id")
        if not isinstance(rollout_id, int) or rollout_id < 1:
            _issue(issues, "error", "rollout.id", "rollout_id must be a positive integer", where)
        else:
            ids.append(rollout_id)

        setting = item.get("setting") or {}
        model_name = str(setting.get("model_name", "")).strip()
        if not model_name:
            _issue(issues, "error", "rollout.setting", "model_name is required", where)
        elif "qwen3.5-35b-a3b" not in model_name.lower():
            level = "error" if strict_model else "warning"
            _issue(
                issues,
                level,
                "rollout.model",
                f"rollout model is {model_name!r}; the requirement is Qwen3.5-35B-A3B",
                where,
            )
        for key in ("temperature", "top_p", "max_tokens"):
            if key not in setting:
                _issue(issues, "warning", "rollout.setting", f"missing {key}", where)

        messages = item.get("messages")
        if not isinstance(messages, list) or not messages:
            _issue(issues, "error", "rollout.messages", "messages must be non-empty", where)
        else:
            _check_message_language(messages, f"{where}.messages", issues)
            if not any(
                isinstance(message, dict) and message.get("role") == "assistant"
                for message in messages
            ):
                _issue(
                    issues,
                    "error",
                    "rollout.messages",
                    "messages must contain an assistant reply",
                    where,
                )

        if not isinstance(item.get("extracted_answer"), str):
            _issue(
                issues,
                "error",
                "rollout.extracted_answer",
                "extracted_answer must be a string",
                where,
            )

        accuracy = item.get("answer-level_accuracy")
        if accuracy not in (0, 1):
            _issue(
                issues,
                "error",
                "rollout.answer-level_accuracy",
                "must be 0 or 1 (field name uses hyphens)",
                where,
            )
        else:
            accuracies.append(int(accuracy))

        score = item.get("step-level_score")
        if not isinstance(score, (int, float)) or not 0 <= float(score) <= 10:
            _issue(
                issues,
                "error",
                "rollout.step-level_score",
                "must be between 0 and 10 (field name uses hyphens)",
                where,
            )

        usage = item.get("usage") or {}
        for key in ("content_tokens", "reasoning_content_tokens", "completion_tokens"):
            if not isinstance(usage.get(key), int):
                _issue(
                    issues,
                    "error",
                    "rollout.usage",
                    f"usage.{key} must be an integer",
                    where,
                )

    if len(ids) != len(set(ids)):
        _issue(issues, "error", "rollout.duplicate_id", "rollout_id values must be unique")
    elif ids and sorted(ids) != list(range(1, len(ids) + 1)):
        _issue(
            issues,
            "error",
            "rollout.id_sequence",
            f"rollout_id values must be 1..{len(ids)}, got {sorted(ids)}",
        )

    average = record.get("average_accuracy")
    if not isinstance(average, (int, float)) or not 0 <= float(average) <= 1:
        _issue(
            issues,
            "error",
            "average_accuracy",
            "average_accuracy must be a number between 0 and 1",
        )
    elif accuracies and len(accuracies) == len(rollouts):
        expected = sum(accuracies) / len(accuracies)
        if abs(float(average) - expected) > 1e-6:
            _issue(
                issues,
                "error",
                "average_accuracy.mismatch",
                f"average_accuracy={average} but rollouts average to {expected:.6f}",
            )


def validate_delivery_record(
    record: dict[str, Any] | Any,
    *,
    expect_rollouts: int = DEFAULT_ROLLOUTS,
    strict_model: bool = True,
    enforce_difficulty: bool = False,
    location: str = "",
) -> list[Issue]:
    """第二层：校验最终交付记录是否符合 6.1/6.2 与 5.1 的字段和内容要求。"""
    issues: list[Issue] = []
    if not isinstance(record, dict):
        _issue(issues, "error", "delivery.type", "record must be a JSON object", location)
        return issues

    missing = [field for field in DELIVERY_FIELDS if field not in record]
    for field in missing:
        _issue(
            issues,
            "error",
            "field.missing",
            f"required delivery field {field!r} is missing",
            location,
        )
    extra = set(record) - set(DELIVERY_FIELDS)
    if extra:
        _issue(
            issues,
            "error",
            "field.extra",
            f"unexpected top-level fields: {sorted(extra)}; delivery must use 6.1 field names only",
            location,
        )

    issues.extend(validate_case_payload(_case_subset(record), location=location))
    _check_trajectory(record, issues=issues)
    _check_rollouts(
        record,
        expect_rollouts=expect_rollouts,
        strict_model=strict_model,
        issues=issues,
    )

    average = record.get("average_accuracy")
    if isinstance(average, (int, float)):
        if float(average) > 0.5:
            _issue(
                issues,
                "error" if enforce_difficulty else "warning",
                "difficulty.per_question",
                f"average_accuracy={average} > 0.5; one question must be hard enough (<= 50%)",
                location,
            )
    _check_text_integrity(record, location, issues)
    return issues


def validate_jsonl(
    path: str | Path,
    *,
    expect_rollouts: int = DEFAULT_ROLLOUTS,
    strict_model: bool = True,
    enforce_difficulty: bool = False,
) -> list[Issue]:
    """校验交付 .jsonl：编码、每行一条记录、文件命名、字段和内容。"""
    issues: list[Issue] = []
    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        _issue(issues, "error", "jsonl.read", str(exc), str(path))
        return issues

    if raw.startswith(b"\xef\xbb\xbf"):
        _issue(issues, "error", "jsonl.bom", "file must be UTF-8 without BOM", str(path))
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _issue(issues, "error", "jsonl.utf8", f"not valid UTF-8: {exc}", str(path))
        return issues

    if "\r" in text:
        _issue(
            issues,
            "error",
            "jsonl.newline",
            "line separator must be \\n, not CRLF",
            str(path),
        )
        text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not lines:
        _issue(issues, "error", "jsonl.empty", "file has no records", str(path))
        return issues

    for index, line in enumerate(lines, start=1):
        where = f"{path.name}:{index}"
        if not line.strip():
            _issue(issues, "error", "jsonl.blank_line", "blank line is not allowed", where)
            continue
        if line != line.strip():
            _issue(
                issues,
                "warning",
                "jsonl.spacing",
                "line has leading or trailing whitespace",
                where,
            )
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            _issue(issues, "error", "jsonl.json", f"invalid JSON: {exc}", where)
            continue
        compact = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        if line.strip() != compact:
            _issue(
                issues,
                "warning",
                "jsonl.compact",
                "line is not compact JSON (one complete record per line)",
                where,
            )
        issues.extend(
            validate_delivery_record(
                record,
                expect_rollouts=expect_rollouts,
                strict_model=strict_model,
                enforce_difficulty=enforce_difficulty,
                location=where,
            )
        )

    match = FILENAME_RE.match(path.name)
    if not match:
        _issue(
            issues,
            "error",
            "jsonl.filename",
            "expected <batch>_<domain>_<count>_<YYYYMMDD>.jsonl, "
            "e.g. batch01_physics_1000_20260915.jsonl",
            str(path),
        )
    else:
        count = int(match.group("count"))
        if count != len(lines):
            _issue(
                issues,
                "error",
                "jsonl.filename_count",
                f"filename says {count} records, file has {len(lines)}",
                str(path),
            )

    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    ids = [str(record.get("id")) for record in records]
    if len(ids) != len(set(ids)):
        _issue(issues, "error", "jsonl.duplicate_id", "record ids must be unique", str(path))

    if records:
        overall = sum(float(record.get("average_accuracy") or 0) for record in records) / len(records)
        if overall > 0.3:
            _issue(
                issues,
                "error" if enforce_difficulty else "warning",
                "difficulty.overall",
                f"overall average_accuracy={overall:.4f} > 0.30",
                str(path),
            )
    return issues


def _load_records(path: Path) -> list[tuple[str, Any]]:
    if path.is_dir():
        files = sorted(path.glob("*.json"))
        files += sorted(
            item for item in path.rglob("case.json") if item.parent != path
        )
        files = sorted(set(files)) + sorted(path.glob("*.jsonl"))
    else:
        files = [path]
    records: list[tuple[str, Any]] = []
    for file in files:
        label = str(file.relative_to(path)) if path.is_dir() else file.name
        text = file.read_text(encoding="utf-8")
        if file.suffix.lower() == ".jsonl":
            for index, line in enumerate(text.splitlines(), start=1):
                if line.strip():
                    records.append((f"{label}:{index}", json.loads(line)))
        else:
            records.append((label, json.loads(text)))
    return records


def validate_case_path(path: str | Path) -> list[Issue]:
    path = Path(path)
    issues: list[Issue] = []
    records = _load_records(path)
    if not records:
        _issue(issues, "error", "case.empty", "no case files found", str(path))
        return issues
    ids: list[str] = []
    for where, raw in records:
        issues.extend(validate_case_payload(raw, location=where))
        if isinstance(raw, dict) and raw.get("id"):
            ids.append(str(raw["id"]))
    if len(ids) != len(set(ids)):
        _issue(issues, "error", "case.duplicate_id", "case ids must be unique", str(path))
    return issues


def _print_report(title: str, issues: list[Issue]) -> int:
    errors = sum(1 for issue in issues if issue.level == "error")
    warnings = sum(1 for issue in issues if issue.level == "warning")
    print(f"{title}: {'PASS' if errors == 0 else 'FAIL'} "
          f"({errors} error(s), {warnings} warning(s))")
    for issue in issues:
        print(f"  {issue}")
    return 0 if errors == 0 else 1


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="两层数据校验：第一层检查题目输入格式，第二层检查最终 JSONL 交付物"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--case", type=Path, help="单个题目 JSON / JSONL 路径")
    source.add_argument("--cases", type=Path, help="题目目录（批量第一层校验）")
    source.add_argument("--jsonl", type=Path, help="最终交付 JSONL 路径（第二层校验）")
    parser.add_argument(
        "--expect-rollouts",
        type=int,
        default=DEFAULT_ROLLOUTS,
        help=f"rollout 条数（默认 {DEFAULT_ROLLOUTS}，传 0 表示不校验）",
    )
    parser.add_argument(
        "--allow-model-mismatch",
        action="store_true",
        help="rollout 模型不是 Qwen3.5-35B-A3B 时只警告不报错（mock 调试用）",
    )
    parser.add_argument(
        "--enforce-difficulty",
        action="store_true",
        help="把平均准确率超限（单题 > 50%%、整体 > 30%%）当作错误",
    )
    args = parser.parse_args()

    strict_model = not args.allow_model_mismatch
    if args.case:
        issues = validate_case_path(args.case)
        return _print_report(f"Layer 1 input {args.case}", issues)
    if args.cases:
        issues = validate_case_path(args.cases)
        return _print_report(f"Layer 1 input {args.cases}", issues)
    issues = validate_jsonl(
        args.jsonl,
        expect_rollouts=args.expect_rollouts,
        strict_model=strict_model,
        enforce_difficulty=args.enforce_difficulty,
    )
    return _print_report(f"Layer 2 delivery {args.jsonl}", issues)


if __name__ == "__main__":
    raise SystemExit(main())
