from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_delivery(path: Path, record: dict[str, Any]) -> int:
    """按任务 id 去重写入 JSONL，同 id 的旧记录被替换。"""
    by_id: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            by_id[str(parsed.get("id"))] = line
    by_id[str(record["id"])] = json.dumps(record, ensure_ascii=False)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(by_id.values()) + "\n", encoding="utf-8")
    return len(by_id)


def _cell(value: object) -> str:
    text = str(value).replace("|", "\\|").replace("\n", " ")
    return text if text else "(空)"


def render_batch_report(summary: dict[str, Any]) -> str:
    tasks = summary.get("tasks", [])
    cases = summary.get("cases", [])

    lines = [f"# 调度批次报告：{summary['run_id']}", ""]
    lines += [
        "| 参数 | 值 |",
        "|---|---|",
        f"| `model` | {_cell(summary['model'])} |",
        f"| `mock` | {summary['mock']} |",
        f"| `judge_mode` | {'llm' if summary['use_llm_judge'] else 'heuristic'} |",
        f"| `concurrency` | {summary['concurrency']} |",
        f"| `timeout_s` | {summary['timeout_s']} |",
        f"| `tasks` | {summary['success']} success / {summary['error']} error / {summary['timeout']} timeout |",
        f"| `wall_seconds` | {summary['wall_seconds']} |",
        "",
    ]

    lines += [
        "## 任务明细",
        "",
        "| 任务 | 题目 | rollout | 状态 | 抽取答案 | 正确 | 步骤分 | tokens | 工具 | 用时(s) | 停止原因 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t in tasks:
        lines.append(
            "| `{id}` | `{case}` | {r} | {status} | `{answer}` | {acc} | {step} | {tokens} | {tools} | {dur} | {term} |".format(
                id=_cell(t["id"]),
                case=_cell(t["case_id"]),
                r=t["rollout_id"],
                status=t["status"],
                answer=_cell(t.get("answer") or ""),
                acc=t.get("accuracy"),
                step=t.get("step_score"),
                tokens=t.get("tokens", 0),
                tools=t.get("tool_calls", 0),
                dur=t.get("duration_s", 0),
                term=_cell(t.get("termination", "")),
            )
        )
    lines.append("")

    lines += [
        "## 按题目汇总",
        "",
        "| 题目 | 有效 rollout | 正确 | 平均准确率 | 平均步骤分 | tokens | 工具调用 | 失败工具 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in cases:
        lines.append(
            "| `{case}` | {n} | {correct} | {acc} | {step}/{max} | {tokens} | {tools} | {failed} |".format(
                case=_cell(c["case_id"]),
                n=c["rollouts"],
                correct=c["correct_rollouts"],
                acc=c["average_accuracy"],
                step=c["average_step_score"],
                max=c["step_score_max"],
                tokens=c["total_tokens"],
                tools=c["total_tool_calls"],
                failed=c["failed_tool_calls"],
            )
        )
    lines += [
        "",
        "## 说明",
        "",
        "- 每个任务是一个独立 worker 子进程，对应一次真实 agent 会话；失败/超时不会拖垮整批。",
        "- 每个任务使用独立 workspace，python/文件工具被限制在该目录内（不是安全沙箱）。",
        "- 逐任务原始记录在 `tasks/<id>/record.json`，完整消息在 `trajectory.json`。",
        "- 按题目汇总的详细报告见 `cases/<case_id>_report.md`。",
        "- 每题的完整记录在 `cases/<case_id>_data_item.json`；最终提交文件是按学科拆分的 "
        "`delivery/<batch>_<domain>_<count>_<YYYYMMDD>.jsonl`，一行一条完整记录。",
        "",
    ]
    return "\n".join(lines)
