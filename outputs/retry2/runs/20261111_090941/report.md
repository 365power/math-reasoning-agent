# 调度批次报告：20261111_090941

| 参数 | 值 |
|---|---|
| `model` | Qwen/Qwen3.5-35B-A3B |
| `mock` | False |
| `judge_mode` | llm |
| `concurrency` | 1 |
| `timeout_s` | 3600.0 |
| `tasks` | 1 success / 0 error / 0 timeout |
| `wall_seconds` | 300.59 |

## 任务明细

| 任务 | 题目 | rollout | 状态 | 抽取答案 | 正确 | 步骤分 | tokens | 工具 | 用时(s) | 停止原因 |
|---|---|---|---|---|---|---|---|---|---|---|
| `physics_20261110_backspin_incline_0f8419c2#r04` | `physics_20261110_backspin_incline_0f8419c2` | 4 | success | `\frac{46 v_0^2}{145 g}` | 1 | 0.0 | 22869 | 0 | 248.366 | model_finished |

## 按题目汇总

| 题目 | 有效 rollout | 正确 | 平均准确率 | 平均步骤分 | tokens | 工具调用 | 失败工具 |
|---|---|---|---|---|---|---|---|
| `physics_20261110_backspin_incline_0f8419c2` | 1 | 1 | 1.0 | 0.0/10 | 22869 | 0 | 0 |

## 说明

- 每个任务是一个独立 worker 子进程，对应一次真实 agent 会话；失败/超时不会拖垮整批。
- 每个任务使用独立 workspace，python/文件工具被限制在该目录内（不是安全沙箱）。
- 逐任务原始记录在 `tasks/<id>/record.json`，完整消息在 `trajectory.json`。
- 按题目汇总的详细报告见 `cases/<case_id>_report.md`。
- 每题的完整记录在 `cases/<case_id>_data_item.json`；最终提交文件是按学科拆分的 `delivery/<batch>_<domain>_<count>_<YYYYMMDD>.jsonl`，一行一条完整记录。
