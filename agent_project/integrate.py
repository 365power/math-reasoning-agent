from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .case import Case
from .validation import (
    CASE_FIELDS,
    DEFAULT_ROLLOUTS,
    DOMAIN_SLUGS,
    validate_delivery_record,
)

BATCH_PATTERN = re.compile(r"[^A-Za-z0-9]+")


def _model_name(record: dict, fallback: str = "") -> str:
    setting = record.get("setting") or {}
    return str(setting.get("model_name") or record.get("model") or fallback)


def _setting(record: dict, fallback_model: str = "") -> dict:
    setting = record.get("setting") or {}
    return {
        "model_name": _model_name(record, fallback_model),
        "temperature": float(setting.get("temperature", 1.0)),
        "top_p": float(setting.get("top_p", 0.95)),
        "max_tokens": int(setting.get("max_tokens", 16384)),
    }


def _normalize_messages(messages: Iterable[dict]) -> list[dict]:
    normalized: list[dict] = []
    for message in messages or []:
        item = dict(message)
        calls = item.get("tool_calls")
        if isinstance(calls, list):
            clean_calls: list[dict] = []
            for call in calls:
                call = dict(call)
                function = dict(call.get("function") or {})
                raw = function.get("arguments")
                if isinstance(raw, str):
                    try:
                        function["arguments"] = json.loads(raw)
                    except json.JSONDecodeError:
                        pass
                call["function"] = function
                clean_calls.append(call)
            item["tool_calls"] = clean_calls
        normalized.append(item)
    return normalized


def _usage(record: dict) -> dict[str, int]:
    usage = record.get("usage") or {}
    completion = int(usage.get("total_completion_tokens", usage.get("completion_tokens", 0)) or 0)
    reasoning = int(
        usage.get("total_reasoning_content_tokens", usage.get("reasoning_content_tokens", 0))
        or 0
    )
    content = int(
        usage.get("total_content_tokens", max(completion - reasoning, 0)) or 0
    )
    return {
        "total_prompt_tokens": int(usage.get("total_prompt_tokens", usage.get("prompt_tokens", 0)) or 0),
        "total_reasoning_content_tokens": reasoning,
        "total_content_tokens": content,
        "total_completion_tokens": completion,
        "total_tokens": int(usage.get("total_tokens", completion) or 0),
    }


def _evidence_usage(record: dict) -> dict[str, int]:
    usage = _usage(record)
    return {
        "content_tokens": usage["total_content_tokens"],
        "reasoning_content_tokens": usage["total_reasoning_content_tokens"],
        "completion_tokens": usage["total_completion_tokens"],
    }


def _evaluation(record: dict) -> dict:
    evaluation = record.get("evaluation") or {}
    score = float(evaluation.get("step_level_score", 0) or 0)
    return {
        "answer_level_accuracy": int(evaluation.get("answer_level_accuracy", 0) or 0),
        "step_level_score": score,
    }


def _tool_statistics(record: dict) -> dict:
    stats = record.get("tool_statistics") or {}
    counts = stats.get("tool_call_counts") or {}
    return {
        "total_tool_calls": int(stats.get("total_tool_calls", sum(int(v or 0) for v in counts.values())) or 0),
        "successful_tool_calls": int(stats.get("successful_tool_calls", 0) or 0),
        "failed_tool_calls": int(stats.get("failed_tool_calls", 0) or 0),
        "tool_call_counts": {str(k): int(v or 0) for k, v in counts.items()},
    }


def _statistics(record: dict) -> dict:
    statistics = record.get("statistics") or (record.get("tool_statistics") or {}).get("statistics") or {}
    return {
        "total_rounds": int(statistics.get("total_rounds", 0) or 0),
        "assistant_rounds": int(statistics.get("assistant_rounds", 0) or 0),
        "tool_rounds": int(statistics.get("tool_rounds", 0) or 0),
    }


def _termination(record: dict) -> dict:
    termination = record.get("termination") or (record.get("tool_statistics") or {}).get("termination") or {}
    return {
        "type": str(termination.get("type") or "answer"),
        "reason": str(termination.get("reason") or "model_finished"),
    }


def _pick_strong(records: list[dict]) -> dict:
    def rank(record: dict) -> tuple:
        stats = record.get("tool_statistics") or {}
        messages = record.get("messages") or []
        reasoning = any(
            isinstance(message, dict) and str(message.get("reasoning_content") or "").strip()
            for message in messages
        )
        return (
            int(stats.get("total_tool_calls", 0) or 0) > 0,
            int(_evaluation(record)["step_level_score"] * 1000),
            reasoning,
        )

    return max(records, key=rank)


def _trajectory_item(record: dict, fallback_model: str = "") -> dict:
    return {
        "rollout_id": 0,
        "setting": _setting(record, fallback_model),
        "messages": _normalize_messages(record.get("messages") or []),
        "tools": list(record.get("tools") or []),
        "extracted_answer": str(record.get("extracted_answer") or ""),
        "evaluation": _evaluation(record),
        "usage": _usage(record),
        "tool_statistics": _tool_statistics(record),
        "statistics": _statistics(record),
        "termination": _termination(record),
    }


def _rollout_item(record: dict, rollout_id: int, fallback_model: str = "") -> dict:
    evaluation = _evaluation(record)
    return {
        "rollout_id": rollout_id,
        "setting": _setting(record, fallback_model),
        "messages": _normalize_messages(record.get("messages") or []),
        "extracted_answer": str(record.get("extracted_answer") or ""),
        "answer-level_accuracy": evaluation["answer_level_accuracy"],
        "step-level_score": evaluation["step_level_score"],
        "usage": _evidence_usage(record),
    }


def _case_fields(case: Case | dict[str, Any] | None) -> dict:
    if isinstance(case, Case):
        return case.to_dict()
    if isinstance(case, dict):
        return Case.model_validate({key: case[key] for key in CASE_FIELDS if key in case}).to_dict()
    raise ValueError("a Case object or a 6.1 case dict is required")


def build_delivery_record(
    case: Case | dict[str, Any] | None,
    result_doc: dict[str, Any],
    system_prompt: str = "",
    *,
    source_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """把内部 rollout 结果整合成 6.1/6.2 规定的一条完整交付记录。"""
    base = _case_fields(case if case is not None else source_doc or result_doc)
    records = [
        record
        for record in (result_doc.get("rollout_35B_results") or [])
        if record.get("messages")
    ]
    if not records:
        raise ValueError("result contains no usable rollout records")

    records.sort(key=lambda record: int(record.get("rollout_id", 0) or 0))
    fallback_model = _model_name(records[0])
    rollouts = [
        _rollout_item(record, index, fallback_model)
        for index, record in enumerate(records, start=1)
    ]
    average = sum(item["answer-level_accuracy"] for item in rollouts) / len(rollouts)

    record = {
        **base,
        "trajectory": [_trajectory_item(_pick_strong(records), fallback_model)],
        "rollout_35B_results": rollouts,
        "average_accuracy": round(average, 6),
    }

    issues = validate_delivery_record(
        record,
        expect_rollouts=0,
        strict_model=False,
        enforce_difficulty=False,
    )
    errors = [issue for issue in issues if issue.level == "error"]
    if errors:
        detail = "; ".join(str(issue) for issue in errors[:8])
        raise ValueError(f"delivery record failed validation: {detail}")
    return record


def dumps_record(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))


def dump_record_json(path: str | Path, record: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def write_jsonl(path: str | Path, records: Iterable[dict[str, Any]]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [dumps_record(record) for record in records]
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line + "\n")
    return target


def delivery_filename(
    batch: str,
    domain: str,
    count: int,
    date: str | None = None,
) -> str:
    safe_batch = BATCH_PATTERN.sub("", batch) or "batch01"
    slug = DOMAIN_SLUGS.get(domain, domain.lower())
    day = date or datetime.now().strftime("%Y%m%d")
    return f"{safe_batch}_{slug}_{count}_{day}.jsonl"


def write_readable_json(path: str | Path, records: Iterable[dict[str, Any]]) -> Path:
    """人工查看用的缩进版；正式交付仍是 write_jsonl 的一行一条。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(list(records), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def write_delivery_by_domain(
    output_dir: str | Path,
    batch: str,
    records: list[dict[str, Any]],
    date: str | None = None,
    readable_dir: str | Path | None = None,
) -> list[Path]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("domain", "")), []).append(record)

    written: list[Path] = []
    for domain in sorted(grouped, key=lambda item: list(DOMAIN_SLUGS).index(item) if item in DOMAIN_SLUGS else 99):
        items = grouped[domain]
        name = delivery_filename(batch, domain, len(items), date)
        target = write_jsonl(Path(output_dir) / name, items)
        written.append(target)
        if readable_dir is not None:
            write_readable_json(Path(readable_dir) / f"{target.stem}.json", items)
    return written


def integrate_result_file(
    result_path: str | Path,
    metrics_path: str | Path | None = None,
    out_path: str | Path | None = None,
    system_prompt: str = "",
    expected_rollouts: int | None = DEFAULT_ROLLOUTS,
) -> tuple[Path, dict[str, Any]]:
    result_path = Path(result_path)
    result_doc = json.loads(result_path.read_text(encoding="utf-8"))
    payload = build_delivery_record(None, result_doc, system_prompt)
    issues = validate_delivery_record(
        payload,
        expect_rollouts=expected_rollouts or 0,
        strict_model=False,
    )
    errors = [issue for issue in issues if issue.level == "error"]
    if errors:
        raise ValueError("; ".join(str(issue) for issue in errors[:8]))
    target = Path(out_path) if out_path else result_path.with_name(
        f"{payload['id']}_data_item.json"
    )
    dump_record_json(target, payload)
    return target, payload


def integrate_run_dir(
    run_dir: str | Path,
    out_dir: str | Path,
    batch: str,
    date: str | None = None,
) -> tuple[list[Path], list[Path]]:
    sources = sorted((Path(run_dir) / "cases").glob("*_result.json"))
    if not sources:
        raise ValueError(f"no *_result.json under {Path(run_dir) / 'cases'}")
    record_paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for source in sources:
        target, payload = integrate_result_file(source, None, None, "", None)
        record_paths.append(target)
        records.append(payload)
    jsonl_paths = write_delivery_by_domain(out_dir, batch, records, date)
    return record_paths, jsonl_paths


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="把内部 rollout 结果整合成 6.1/6.2 的一条完整记录或 JSONL"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--result", type=Path, help="内部 *_result.json 路径")
    source.add_argument("--run-dir", type=Path, help="调度器运行目录")
    parser.add_argument("--metrics", type=Path, default=None, help="兼容旧参数，可忽略")
    parser.add_argument("--out", type=Path, default=None, help="单条记录输出路径")
    parser.add_argument("--jsonl-dir", type=Path, default=None, help="批量 JSONL 输出目录")
    parser.add_argument("--batch", default="batch01", help="批次名，如 batch01")
    parser.add_argument("--date", default=None, help="文件名日期 YYYYMMDD，默认今天")
    parser.add_argument(
        "--expect-rollouts",
        type=int,
        default=DEFAULT_ROLLOUTS,
        help=f"校验 rollout 条数（默认 {DEFAULT_ROLLOUTS}，传 0 表示不校验）",
    )
    args = parser.parse_args()

    try:
        if args.result:
            target, payload = integrate_result_file(
                args.result, args.metrics, args.out, "", args.expect_rollouts
            )
            jsonl_paths = []
            if args.jsonl_dir:
                jsonl_paths = write_delivery_by_domain(
                    args.jsonl_dir, args.batch, [payload], args.date
                )
            print(f"record : {target}")
            print(f"id     : {payload['id']}")
            print(f"rollouts: {len(payload['rollout_35B_results'])}")
            print(f"accuracy: {payload['average_accuracy']}")
            for path in jsonl_paths:
                print(f"jsonl  : {path}")
            return 0

        out_dir = args.jsonl_dir or Path(args.run_dir) / "delivery"
        record_paths, jsonl_paths = integrate_run_dir(
            args.run_dir, out_dir, args.batch, args.date
        )
        print(f"records: {len(record_paths)}")
        for path in jsonl_paths:
            print(f"jsonl  : {path}")
        return 0
    except ValueError as exc:
        print(f"integrate failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
