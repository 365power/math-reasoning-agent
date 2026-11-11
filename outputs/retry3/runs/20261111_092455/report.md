# 调度批次报告：20261111_092455

| 参数 | 值 |
|---|---|
| `model` | Qwen/Qwen3.5-35B-A3B |
| `mock` | False |
| `judge_mode` | llm |
| `concurrency` | 4 |
| `timeout_s` | 3600.0 |
| `tasks` | 8 success / 0 error / 0 timeout |
| `wall_seconds` | 248.85 |

## 任务明细

| 任务 | 题目 | rollout | 状态 | 抽取答案 | 正确 | 步骤分 | tokens | 工具 | 用时(s) | 停止原因 |
|---|---|---|---|---|---|---|---|---|---|---|
| `math_001_arctan_series#r01` | `math_001_arctan_series` | 1 | success | `\frac{\pi}{4}` | 1 | 6.0 | 15942 | 1 | 135.174 | model_finished |
| `math_001_arctan_series#r02` | `math_001_arctan_series` | 2 | success | `\frac{\pi}{4}` | 1 | 10.0 | 8413 | 1 | 72.067 | model_finished |
| `math_001_arctan_series#r03` | `math_001_arctan_series` | 3 | success | `\frac{\pi}{4}` | 1 | 10.0 | 8912 | 2 | 61.763 | model_finished |
| `math_001_arctan_series#r04` | `math_001_arctan_series` | 4 | success | `\frac{\pi}{4}` | 1 | 10.0 | 9306 | 1 | 74.86 | model_finished |
| `math_001_arctan_series#r05` | `math_001_arctan_series` | 5 | success | `\frac{\pi}{4}` | 1 | 4.0 | 8827 | 1 | 56.83 | model_finished |
| `math_001_arctan_series#r06` | `math_001_arctan_series` | 6 | success | `\frac{\pi}{4}` | 1 | 10.0 | 8463 | 1 | 70.095 | model_finished |
| `math_001_arctan_series#r07` | `math_001_arctan_series` | 7 | success | `\frac{\pi}{4}` | 1 | 6.0 | 15311 | 1 | 134.411 | model_finished |
| `math_001_arctan_series#r08` | `math_001_arctan_series` | 8 | success | `\frac{\pi}{4}` | 1 | 10.0 | 12444 | 1 | 114.213 | model_finished |

## 按题目汇总

| 题目 | 有效 rollout | 正确 | 平均准确率 | 平均步骤分 | tokens | 工具调用 | 失败工具 |
|---|---|---|---|---|---|---|---|
| `math_001_arctan_series` | 8 | 8 | 1.0 | 8.25/10 | 87618 | 9 | 0 |

## 说明

- 每个任务是一个独立 worker 子进程，对应一次真实 agent 会话；失败/超时不会拖垮整批。
- 每个任务使用独立 workspace，python/文件工具被限制在该目录内（不是安全沙箱）。
- 逐任务原始记录在 `tasks/<id>/record.json`，完整消息在 `trajectory.json`。
- 按题目汇总的详细报告见 `cases/<case_id>_report.md`。
- 每题的完整记录在 `cases/<case_id>_data_item.json`；最终提交文件是按学科拆分的 `delivery/<batch>_<domain>_<count>_<YYYYMMDD>.jsonl`，一行一条完整记录。
