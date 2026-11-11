from __future__ import annotations

import time
from typing import Any, Callable

from .agent import Agent
from .case import Case
from .config import Settings
from .judge import RubricJudge, answers_match, extract_boxed
from .tools import tools

SYSTEM_PROMPT = """\
You are a rigorous scientific reasoning agent. You may call tools to support your work, but you must complete the mathematical argument yourself.

Rules:
1. Analyze the problem structure first. Before giving the final answer, call the python tool at least once for numerical verification.
2. Numerical results are only for verification; they cannot replace a rigorous proof.
3. State the justification for every reasoning step. Do not invent unverified theorems or tool results.
4. Put only the final value or expression inside \\boxed{...} (for example \\boxed{\\frac{\\pi}{4}}). Do not put a full equation, a summation process, or prose inside it.
5. Write the entire response in English.
"""


def _flatten_tools(specs: list[dict]) -> list[dict]:
    """6.2 的 trajectory.tools 用扁平结构记录；调用 API 时仍是 OpenAI 嵌套格式。"""
    return [
        {
            "type": spec["type"],
            "name": spec["function"]["name"],
            "description": spec["function"]["description"],
            "parameters": spec["function"]["parameters"],
        }
        for spec in specs
    ]


def build_user_message(case: Case) -> str:
    context = f"\n[Context]\n{case.context}" if case.context else ""
    return (
        f"[Problem]\n{case.question}\n"
        f"{context}\n\n"
        "Provide a complete, verifiable derivation. If you use tools, explain how the tool "
        "results support your reasoning. Give the final answer with \\boxed{...} and write "
        "the entire response in English."
    )


def run_case(
    settings: Settings,
    case: Case,
    client: Any,
    judge_client: Any,
    rollouts: int | None = None,
    use_llm_judge: bool = True,
    progress: Callable[[str], None] | None = None,
) -> tuple[dict, dict]:
    n_rollouts = rollouts or settings.rollouts
    agent = Agent(settings, client)
    judge = RubricJudge(judge_client, use_llm=use_llm_judge)
    tool_specs = _flatten_tools(tools())

    records: list[dict] = []
    judge_usage_total = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
    }
    started = time.perf_counter()

    for i in range(n_rollouts):
        if progress:
            progress(f"[rollout {i + 1}/{n_rollouts}] 开始")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(case)},
        ]
        result = agent.agent_loop(messages)
        extracted = extract_boxed(result.final_content)
        exact_correct = int(answers_match(extracted, case.answer))

        try:
            judged = judge.judge(case, result.final_content, extracted)
        except Exception as exc:  # noqa: BLE001 - 评分失败退回启发式
            judged = RubricJudge(judge_client, use_llm=False).judge(
                case, result.final_content, extracted
            )
            judged.model = "heuristic"
            judged.reasoning += (
                f" (judge failed, heuristic fallback: {type(exc).__name__}: {exc})"
            )

        # 等价符号形式（如 log(5/4)/(4(log2)^2) 与 log(5/4)/(log4)^2）无法靠字符串匹配，
        # 在精确匹配失败时以 LLM judge 的答案判定为准；抽不出答案时不采信 judge。
        judge_correct = int(
            bool(extracted)
            and judged.source == "llm"
            and int(judged.answer_level_accuracy or 0) == 1
        )
        answer_correct = int(exact_correct or judge_correct)

        for key in judge_usage_total:
            judge_usage_total[key] += int(judged.usage.get(key, 0) or 0)

        completion = int(result.usage.get("completion_tokens", 0))
        reasoning = int(result.usage.get("reasoning_tokens", 0))
        usage = {
            "total_prompt_tokens": int(result.usage.get("prompt_tokens", 0)),
            "total_reasoning_content_tokens": reasoning,
            "total_content_tokens": max(completion - reasoning, 0),
            "total_completion_tokens": completion,
            "total_tokens": int(result.usage.get("total_tokens", 0)),
        }

        record = {
            "rollout_id": i + 1,
            "setting": {
                "model_name": getattr(client, "model", settings.model),
                "temperature": settings.temperature,
                "top_p": settings.top_p,
                "max_tokens": settings.max_tokens,
            },
            "messages": [
                {"role": "user", "content": build_user_message(case)}
            ]
            + result.messages,
            "tools": tool_specs,
            "extracted_answer": extracted,
            "evaluation": {
                "answer_level_accuracy": answer_correct,
                "exact_match_accuracy": exact_correct,
                "step_level_score": judged.step_level_score,
                "matched_criteria": judged.matched_criteria,
                "missing_or_wrong": judged.missing_or_wrong,
                "judge_answer_level_accuracy": judged.answer_level_accuracy,
                "judge_reasoning": judged.reasoning,
                "judge_source": judged.source,
                "judge_model": judged.model,
                "judge_prompt": judged.prompt,
                "judge_raw_response": judged.raw_response,
            },
            "usage": usage,
            "tool_statistics": result.tool_statistics,
            "statistics": {
                "total_rounds": sum(
                    1 for m in result.messages if m.get("role") == "assistant"
                ),
                "assistant_rounds": sum(
                    1 for m in result.messages if m.get("role") == "assistant"
                ),
                "tool_rounds": sum(
                    1 for m in result.messages if m.get("role") == "tool"
                ),
            },
            "termination": dict(result.tool_statistics.get("termination", {})),
            "duration_seconds": round(result.duration_seconds, 3),
        }
        records.append(record)
        if progress:
            term = record["termination"]
            tail = f"，stop={term.get('reason', 'unknown')}"
            if term.get("error"):
                tail += f"，错误={term['error']}"
            progress(
                f"[rollout {i + 1}/{n_rollouts}] 完成："
                f"answer={extracted or '(空)'}，"
                f"accuracy={answer_correct}，"
                f"step={judged.step_level_score:.0f}/{case.rubric.total_points}，"
                f"tools={result.tool_statistics.get('total_tool_calls', 0)}，"
                f"tokens={usage['total_tokens']}"
                f"{tail}"
            )

    elapsed = time.perf_counter() - started
    return summarize_records(
        case=case,
        records=records,
        settings=settings,
        client=client,
        judge_client=judge_client,
        n_rollouts=n_rollouts,
        use_llm_judge=use_llm_judge,
        judge_usage_total=judge_usage_total,
        elapsed=elapsed,
    )


def summarize_records(
    *,
    case: Case,
    records: list[dict],
    settings: Settings,
    client: Any,
    judge_client: Any,
    n_rollouts: int,
    use_llm_judge: bool,
    judge_usage_total: dict[str, int],
    elapsed: float,
) -> tuple[dict, dict]:
    """把一批 rollout 记录汇总成 6.2 的 result_doc + metrics。

    单测/命令行流水线和调度器共用这一处聚合逻辑，避免指标口径分叉。
    """
    average_accuracy = (
        sum(r["evaluation"]["answer_level_accuracy"] for r in records) / len(records)
        if records
        else 0.0
    )
    average_step_score = (
        sum(r["evaluation"]["step_level_score"] for r in records) / len(records)
        if records
        else 0.0
    )

    trajectory = {**records[0], "rollout_id": 0} if records else {}
    result_doc = {
        **case.to_dict(),
        "trajectory": trajectory,
        "rollout_35B_results": records,
        "average_accuracy": round(average_accuracy, 6),
    }

    total_tool_calls = sum(
        r["tool_statistics"].get("total_tool_calls", 0) for r in records
    )
    successful_tool_calls = sum(
        r["tool_statistics"].get("successful_tool_calls", 0) for r in records
    )
    failed_tool_calls = sum(
        r["tool_statistics"].get("failed_tool_calls", 0) for r in records
    )
    termination_counts: dict[str, int] = {}
    for r in records:
        reason = str(r["termination"].get("reason", "unknown"))
        termination_counts[reason] = termination_counts.get(reason, 0) + 1

    metrics = {
        "case_id": case.id,
        "parameters": {
            "model": getattr(client, "model", settings.model),
            "base_url": settings.base_url,
            "judge_model": getattr(judge_client, "model", settings.judge_model),
            "temperature": settings.temperature,
            "top_p": settings.top_p,
            "max_tokens": settings.max_tokens,
            "rollouts": n_rollouts,
            "max_tool_rounds": settings.max_tool_rounds,
            "tool_timeout_seconds": settings.tool_timeout,
            "judge_mode": "llm" if use_llm_judge else "heuristic",
        },
        "metrics": {
            "average_accuracy": round(average_accuracy, 6),
            "correct_rollouts": sum(
                r["evaluation"]["answer_level_accuracy"] for r in records
            ),
            "average_step_score": round(average_step_score, 3),
            "step_score_max": case.rubric.total_points,
            "total_tool_calls": total_tool_calls,
            "successful_tool_calls": successful_tool_calls,
            "failed_tool_calls": failed_tool_calls,
            "tool_call_success_rate": round(
                successful_tool_calls / total_tool_calls, 4
            )
            if total_tool_calls
            else None,
            "total_tokens": sum(r["usage"]["total_tokens"] for r in records),
            "average_tokens_per_rollout": round(
                sum(r["usage"]["total_tokens"] for r in records) / len(records), 1
            )
            if records
            else 0,
            "total_reasoning_tokens": sum(
                r["usage"]["total_reasoning_content_tokens"] for r in records
            ),
            "average_duration_seconds": round(elapsed / len(records), 2)
            if records
            else 0,
            "termination_counts": termination_counts,
            "judge_usage": judge_usage_total,
        },
        "elapsed_seconds": round(elapsed, 2),
    }
    return result_doc, metrics
