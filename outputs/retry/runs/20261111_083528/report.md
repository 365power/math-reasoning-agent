# 调度批次报告：20261111_083528

| 参数 | 值 |
|---|---|
| `model` | Qwen/Qwen3.5-35B-A3B |
| `mock` | False |
| `judge_mode` | llm |
| `concurrency` | 4 |
| `timeout_s` | 3600.0 |
| `tasks` | 12 success / 0 error / 0 timeout |
| `wall_seconds` | 1513.35 |

## 任务明细

| 任务 | 题目 | rollout | 状态 | 抽取答案 | 正确 | 步骤分 | tokens | 工具 | 用时(s) | 停止原因 |
|---|---|---|---|---|---|---|---|---|---|---|
| `math_entrance_njust_2023_840_q5_hilbert#r01` | `math_entrance_njust_2023_840_q5_hilbert` | 1 | success | `(-1)^{n-j} n \binom{2n-1}{n-1} \binom{n-1}{j-1} \binom{n+j-2}{j-1}` | 0 | 8.0 | 27421 | 0 | 309.76 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r02` | `math_entrance_njust_2023_840_q5_hilbert` | 2 | success | `(-1)^{n+j} (2n-1) \binom{2n-2}{n-1} \binom{n-1}{j-1} \binom{n+j-2}{j-1}` | 0 | 10.0 | 27222 | 0 | 324.773 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r03` | `math_entrance_njust_2023_840_q5_hilbert` | 3 | success | `(-1)^{n+j} (2n-1) \binom{2n-2}{n-1} \binom{n+j-2}{n-1} \binom{n-1}{j-1}` | 0 | 10.0 | 25135 | 0 | 267.704 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r04` | `math_entrance_njust_2023_840_q5_hilbert` | 4 | success | `(-1)^{n+j} (n+j-1) \binom{2n-1}{n-j} \binom{n+j-2}{j-1}^2` | 0 | 10.0 | 26858 | 0 | 294.08 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r05` | `math_entrance_njust_2023_840_q5_hilbert` | 5 | success | `(-1)^{n+j} (n+j-1) \binom{2n-1}{n-j} \binom{n+j-2}{n-1}^2` | 0 | 8.0 | 23161 | 0 | 248.226 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r06` | `math_entrance_njust_2023_840_q5_hilbert` | 6 | success | `(-1)^{n+j} (n+j-1) \binom{2n-1}{n-j} \binom{n+j-2}{j-1}^2` | 0 | 10.0 | 32387 | 0 | 372.163 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r07` | `math_entrance_njust_2023_840_q5_hilbert` | 7 | success | `(-1)^{n+j} (n+j-1) \binom{2n-1}{n-j} \binom{n+j-2}{j-1}^2` | 0 | 10.0 | 49681 | 5 | 388.375 | model_finished |
| `math_entrance_njust_2023_840_q5_hilbert#r08` | `math_entrance_njust_2023_840_q5_hilbert` | 8 | success | `(空)` | 0 | 0.0 | 52156 | 12 | 138.913 | max_tool_rounds |
| `physics_20261110_backspin_incline_0f8419c2#r01` | `physics_20261110_backspin_incline_0f8419c2` | 1 | success | `\frac{46 v_0^2}{145 g}` | 1 | 0.0 | 54046 | 3 | 600.143 | model_finished |
| `physics_20261110_backspin_incline_0f8419c2#r02` | `physics_20261110_backspin_incline_0f8419c2` | 2 | success | `\frac{46}{145}\frac{v_0^2}{g}` | 0 | 10.0 | 27671 | 0 | 329.618 | model_finished |
| `physics_20261110_backspin_incline_0f8419c2#r03` | `physics_20261110_backspin_incline_0f8419c2` | 3 | success | `\frac{46 v_0^2}{145 g}` | 1 | 5.0 | 33343 | 1 | 355.887 | model_finished |
| `physics_20261110_backspin_incline_0f8419c2#r04` | `physics_20261110_backspin_incline_0f8419c2` | 4 | success | `\frac{46 v_0^2}{145 g}` | 1 | 0.0 | 121874 | 11 | 720.318 | model_finished |

## 按题目汇总

| 题目 | 有效 rollout | 正确 | 平均准确率 | 平均步骤分 | tokens | 工具调用 | 失败工具 |
|---|---|---|---|---|---|---|---|
| `math_entrance_njust_2023_840_q5_hilbert` | 8 | 0 | 0.0 | 8.25/10 | 264021 | 17 | 0 |
| `physics_20261110_backspin_incline_0f8419c2` | 4 | 3 | 0.75 | 3.75/10 | 236934 | 15 | 0 |

## 说明

- 每个任务是一个独立 worker 子进程，对应一次真实 agent 会话；失败/超时不会拖垮整批。
- 每个任务使用独立 workspace，python/文件工具被限制在该目录内（不是安全沙箱）。
- 逐任务原始记录在 `tasks/<id>/record.json`，完整消息在 `trajectory.json`。
- 按题目汇总的详细报告见 `cases/<case_id>_report.md`。
- 每题的完整记录在 `cases/<case_id>_data_item.json`；最终提交文件是按学科拆分的 `delivery/<batch>_<domain>_<count>_<YYYYMMDD>.jsonl`，一行一条完整记录。
