from __future__ import annotations

import ast
import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from .case import Case
from .llm import LLMResponse


# ---------------------------------------------------------------------------
# 答案抽取与规范化
# ---------------------------------------------------------------------------
def extract_boxed(text: str) -> str:
    """取最后一个 \\boxed{...}，支持花括号嵌套。"""
    if not text:
        return ""
    start = text.rfind("\\boxed")
    if start == -1:
        return ""
    i = text.find("{", start)
    if i == -1:
        return ""
    depth = 0
    for j in range(i, len(text)):
        ch = text[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1 : j].strip()
    return ""


_PI_QUARTERS = {
    r"\frac{\pi}{4}",
    r"\frac{\pi}{4}",
    r"\pi/4",
    r"\frac{1}{4}\pi",
    r"\frac14\pi",
    r"π/4",
    "0.785398163397448",
    "0.7853981634",
}


def _compact(value: str) -> str:
    value = value.strip().strip("$").strip()
    for token in (r"\displaystyle", r"\left", r"\right", r"\,", r"\;", r"\!"):
        value = value.replace(token, "")
    value = value.replace("\\dfrac", "\\frac").replace("\\tfrac", "\\frac")
    value = value.replace("π", r"\pi")
    value = re.sub(r"\s+", "", value)
    return value


def _rhs_of_last_top_level_equals(value: str) -> str:
    depth = 0
    pos = -1
    for i, ch in enumerate(value):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "=" and depth == 0:
            pos = i
    return value[pos + 1 :].strip() if pos != -1 else value


def _read_group(value: str, start: int) -> tuple[str | None, int]:
    """value[start] 必须是 '{'，返回 (括号内文本, 右括号后一位)。"""
    depth = 0
    for i in range(start, len(value)):
        if value[i] == "{":
            depth += 1
        elif value[i] == "}":
            depth -= 1
            if depth == 0:
                return value[start + 1 : i], i + 1
    return None, start


def _expand_fractions(value: str) -> str:
    """把任意嵌套深度的 \\frac{a}{b} 展开为 (a)/(b)。"""
    out: list[str] = []
    i = 0
    while i < len(value):
        if value.startswith(r"\frac", i):
            j = i + len(r"\frac")
            if j < len(value) and value[j] == "{":
                numerator, end_num = _read_group(value, j)
                if (
                    numerator is not None
                    and end_num < len(value)
                    and value[end_num] == "{"
                ):
                    denominator, end_den = _read_group(value, end_num)
                    if denominator is not None:
                        out.append(
                            "("
                            + _expand_fractions(numerator)
                            + ")/("
                            + _expand_fractions(denominator)
                            + ")"
                        )
                        i = end_den
                        continue
        out.append(value[i])
        i += 1
    return "".join(out)


def _strip_outer_parens(value: str) -> str:
    """只去掉真正包住整个表达式的括号，避免 strip('()') 误删半边括号。"""
    while len(value) >= 2 and value[0] == "(" and value[-1] == ")":
        depth = 0
        encloses_all = True
        for i, ch in enumerate(value):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(value) - 1:
                    encloses_all = False
                    break
        if not encloses_all or depth != 0:
            break
        value = value[1:-1]
    return value


def _drop_numerator_parens(value: str) -> str:
    """(a)/(b) 与 a/(b) 视为同一写法；a/b 中含 + - 时保留括号。"""
    pattern = re.compile(r"\(([^()]*)\)/")
    while True:
        match = pattern.search(value)
        if not match:
            return value
        inner = match.group(1)
        if any(ch in inner for ch in "+-/"):
            return value
        value = value[: match.start()] + inner + "/" + value[match.end() :]


_NUMERIC_RE = re.compile(r"^[0-9eE+\-*/(). ]+$")


def _eval_numeric(value: str) -> float | None:
    """仅对纯数字四则表达式求值，供 3/32 与 0.09375 这类比较使用。"""
    if not _NUMERIC_RE.match(value):
        return None
    try:
        tree = ast.parse(value, mode="eval")
    except SyntaxError:
        return None
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
    )
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        return None
    try:
        return float(eval(compile(tree, "<answer>", "eval"), {"__builtins__": {}}, {}))
    except (ArithmeticError, ValueError):
        return None


def normalize_answer(value: str) -> str:
    value = _compact(value)
    # 模型常把整个等式塞进 \boxed{}；只比较最后一个顶层等号的右侧。
    value = _rhs_of_last_top_level_equals(value)
    if value in _PI_QUARTERS:
        return "pi/4"
    # 单字符上下标去掉花括号，便于后续分数展开匹配 v_0^{2} 与 v_0^2。
    value = re.sub(r"\^\{([^{}])\}", r"^\1", value)
    value = re.sub(r"_\{([^{}])\}", r"_\1", value)
    value = _expand_fractions(value)
    value = _drop_numerator_parens(value)
    value = _strip_outer_parens(value)
    value = value.replace(r"\pi", "pi").replace(r"\cdot", "*")
    return value


def answers_match(candidate: str, reference: str) -> bool:
    cand = normalize_answer(candidate)
    ref = normalize_answer(reference)
    if not cand:
        return False
    if cand == ref:
        return True
    cand_value = _eval_numeric(cand)
    ref_value = _eval_numeric(ref)
    if cand_value is not None and ref_value is not None:
        return math.isclose(cand_value, ref_value, rel_tol=1e-9, abs_tol=1e-12)
    return False


# ---------------------------------------------------------------------------
# 评分结果
# ---------------------------------------------------------------------------
@dataclass
class JudgeResult:
    answer_level_accuracy: int
    step_level_score: float
    matched_criteria: list[int] = field(default_factory=list)
    missing_or_wrong: list[str] = field(default_factory=list)
    reasoning: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    source: str = "llm"
    model: str = ""
    prompt: str = ""
    raw_response: str = ""


def _heuristic_judge(case: Case, candidate: str, extracted: str) -> JudgeResult:
    text = candidate or ""
    lower = text.lower()
    matched: list[int] = []
    missing: list[str] = []

    checks = {
        1: ("差公式", lambda: "arctan" in lower and ("2n+1" in text or "2N+1" in text)),
        2: ("通项验证", lambda: ("4n" in text or "4N" in text) or "2n^2" in text or "2n^{2}" in text),
        3: ("拆分", lambda: "arctan(2n+1)" in text.replace(" ", "")),
        4: ("部分和", lambda: "s_n" in lower or "S_N" in text or "部分和" in text),
        5: (
            "极限",
            lambda: (
                "pi/2" in lower
                or "π/2" in text
                or r"\pi}{2}" in text
                or r"\frac{\pi}{2}" in text
            )
            and answers_match(extracted, case.answer),
        ),
    }
    for cid, (label, fn) in checks.items():
        try:
            ok = bool(fn())
        except Exception:
            ok = False
        if ok:
            matched.append(cid)
        else:
            missing.append(label)

    score = 0.0
    for criterion in case.rubric.criteria:
        if criterion.criterion_id in matched:
            score += criterion.points
    score = min(score, case.rubric.total_points)
    answer_ok = int(answers_match(extracted, case.answer))
    return JudgeResult(
        answer_level_accuracy=answer_ok,
        step_level_score=score,
        matched_criteria=matched,
        missing_or_wrong=missing,
        reasoning="Heuristic scoring (no judge model was called).",
        source="heuristic",
        model="heuristic",
    )


class RubricJudge:
    def __init__(self, client: Any, use_llm: bool = True):
        self.client = client
        self.use_llm = use_llm

    @property
    def model(self) -> str:
        return str(getattr(self.client, "model", "") or "")

    def judge(self, case: Case, candidate: str, extracted: str) -> JudgeResult:
        if not self.use_llm:
            result = _heuristic_judge(case, candidate, extracted)
            result.model = "heuristic"
            return result

        rubric = [
            {
                "criterion_id": c.criterion_id,
                "description": c.description,
                "points": c.points,
            }
            for c in case.rubric.criteria
        ]
        prompt = f"""You are a strict scientific-reasoning grader. Score the candidate solution using only the problem, the reference answer, and the rubric.

[Problem]
{case.question}

[Reference answer]
{case.answer}

[Reference solution steps]
{chr(10).join(case.solution_steps)}

[Rubric (maximum {case.rubric.total_points} points)]
{json.dumps(rubric, ensure_ascii=False, indent=2)}

[Candidate solution]
{candidate}

Requirements:
1. Evaluate each rubric criterion independently. Award a criterion only when the candidate explicitly states the required point.
2. answer_level_accuracy must be 0 or 1.
3. step_level_score is the sum of points for matched criteria and must not exceed {case.rubric.total_points}.
4. Return exactly one JSON object, with no Markdown fence or extra text, in this format:
{{"answer_level_accuracy": 0, "step_level_score": 0, "matched_criteria": [], "missing_or_wrong": [], "reasoning": ""}}
"""
        response: LLMResponse = self.client.chat(
            [{"role": "user", "content": prompt}],
            tools=None,
            tool_choice=None,
            temperature=0.0,
            top_p=1.0,
            max_tokens=8192,
        )
        raw_response = response.content or ""
        parsed = self._parse(raw_response)
        if not parsed or "step_level_score" not in parsed:
            fallback = _heuristic_judge(case, candidate, extracted)
            fallback.reasoning = (
                "The judge model did not return parseable JSON; "
                "heuristic scoring was used instead."
            )
            fallback.usage = response.usage
            fallback.source = "heuristic_fallback"
            fallback.model = self.model
            fallback.prompt = prompt
            fallback.raw_response = raw_response
            return fallback
        answer_from_judge = int(parsed.get("answer_level_accuracy", 0) or 0)
        answer_from_judge = 1 if answer_from_judge else 0
        score = float(parsed.get("step_level_score", 0) or 0)
        score = max(0.0, min(score, float(case.rubric.total_points)))

        return JudgeResult(
            answer_level_accuracy=answer_from_judge,
            step_level_score=score,
            matched_criteria=list(parsed.get("matched_criteria", []) or []),
            missing_or_wrong=list(parsed.get("missing_or_wrong", []) or []),
            reasoning=str(parsed.get("reasoning", "")),
            usage=response.usage,
            source="llm",
            model=self.model,
            prompt=prompt,
            raw_response=raw_response,
        )

    @staticmethod
    def _parse(text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}
