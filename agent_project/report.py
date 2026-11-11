from __future__ import annotations

from .case import Case


def _cell(value: object) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text if text else "(空)"


def render_markdown(case: Case, result: dict, metrics: dict) -> str:
    p = metrics["parameters"]
    m = metrics["metrics"]
    records = result.get("rollout_35B_results", [])

    lines: list[str] = []
    lines.append(f"# 评测报告：{case.id}")
    lines.append("")
    lines.append(f"**题目**：{case.question}")
    lines.append("")
    lines.append(f"**标准答案**：`{case.answer}`　**满分**：{case.rubric.total_points}")
    lines.append("")
    lines.append("## 运行参数")
    lines.append("")
    lines.append("| 参数 | 值 |")
    lines.append("|---|---|")
    for key, value in p.items():
        lines.append(f"| `{key}` | {_cell(value)} |")
    lines.append("")
    lines.append("## 核心指标")
    lines.append("")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    for key, value in m.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k}={v}" for k, v in value.items()) or "(无)"
        lines.append(f"| `{key}` | {_cell(value)} |")
    lines.append("")
    lines.append("## 逐次 rollout")
    lines.append("")
    lines.append(
        "| # | 抽取答案 | 答案正确 | 步骤分 | 工具调用 | tokens | 用时(s) | 停止原因 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in records:
        lines.append(
            "| {i} | `{ans}` | {acc} | {step} | {tools} | {tokens} | {dur} | {stop} |".format(
                i=r["rollout_id"],
                ans=_cell(r["extracted_answer"]),
                acc=r["evaluation"]["answer_level_accuracy"],
                step=r["evaluation"]["step_level_score"],
                tools=r["tool_statistics"].get("total_tool_calls", 0),
                tokens=r["usage"]["total_tokens"],
                dur=r["duration_seconds"],
                stop=_cell(r["termination"].get("reason", "unknown")),
            )
        )
    lines.append("")

    tool_counts: dict[str, int] = {}
    for r in records:
        for name, count in r["tool_statistics"].get("tool_call_counts", {}).items():
            tool_counts[name] = tool_counts.get(name, 0) + int(count)
    lines.append("## 工具使用")
    lines.append("")
    if tool_counts:
        lines.append("| 工具 | 调用次数 |")
        lines.append("|---|---|")
        for name, count in sorted(tool_counts.items()):
            lines.append(f"| `{name}` | {count} |")
    else:
        lines.append("本轮没有调用任何工具。")
    lines.append("")

    lines.append("## 说明")
    lines.append("")
    lines.append(
        f"- `answer_level_accuracy`：抽取答案与标准答案规范化后精确匹配，得到 {m['correct_rollouts']}/{len(records)}。"
    )
    lines.append(
        f"- `average_accuracy`：{m['average_accuracy']}；`average_step_score`：{m['average_step_score']}/{m['step_score_max']}。"
    )
    lines.append(
        "- `rollout_35B_results` 为 6.2 规定的字段名；本项目按需求将模型换成 DeepSeek V4.1-Flash-1017，"
        "字段名保持与数据契约一致。"
    )
    lines.append(
        "- 完整消息轨迹、工具调用、token 用量见同名 `_result.json`；机器可读指标见 `_metrics.json`。"
    )
    lines.append("")
    return "\n".join(lines)
