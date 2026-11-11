# 评测报告：math_entrance_jnu_2023_709_ii2_root_asymptotics

**题目**：For each integer \(n\ge2\), let \(y_n\) be the unique real number in \((1/2,1)\) for which \(\sum_{k=1}^{n} y_n^k=1\). Set \(t_n=2^{-n-2}\). Evaluate \(\lim_{n\to\infty}\frac{8^n}{n^2}\left(y_n-\frac12-t_n-2(n+1)t_n^2\right)\).

**标准答案**：`\frac{3}{32}`　**满分**：10

## 运行参数

| 参数 | 值 |
|---|---|
| `model` | Qwen/Qwen3.5-35B-A3B |
| `base_url` | https://api-inference.modelscope.cn/v1 |
| `judge_model` | deepseek-flash |
| `temperature` | 1.0 |
| `top_p` | 0.95 |
| `max_tokens` | 16384 |
| `rollouts` | 8 |
| `max_tool_rounds` | 12 |
| `tool_timeout_seconds` | 30 |
| `judge_mode` | llm |

## 核心指标

| 指标 | 值 |
|---|---|
| `average_accuracy` | 1.0 |
| `correct_rollouts` | 8 |
| `average_step_score` | 3.25 |
| `step_score_max` | 10 |
| `total_tool_calls` | 1 |
| `successful_tool_calls` | 1 |
| `failed_tool_calls` | 0 |
| `tool_call_success_rate` | 1.0 |
| `total_tokens` | 253619 |
| `average_tokens_per_rollout` | 31702.4 |
| `total_reasoning_tokens` | 223179 |
| `average_duration_seconds` | 313.05 |
| `termination_counts` | model_finished=8 |
| `judge_usage` | prompt_tokens=20377, completion_tokens=41282, total_tokens=61659, reasoning_tokens=39913 |

## 逐次 rollout

| # | 抽取答案 | 答案正确 | 步骤分 | 工具调用 | tokens | 用时(s) | 停止原因 |
|---|---|---|---|---|---|---|---|
| 1 | `\frac{3}{32}` | 1 | 0.0 | 1 | 37338 | 323.766 | model_finished |
| 2 | `\frac{3}{32}` | 1 | 4.0 | 0 | 34222 | 351.479 | model_finished |
| 3 | `\frac{3}{32}` | 1 | 4.0 | 0 | 26958 | 259.253 | model_finished |
| 4 | `\frac{3}{32}` | 1 | 2.0 | 0 | 29876 | 312.857 | model_finished |
| 5 | `\frac{3}{32}` | 1 | 4.0 | 0 | 35963 | 362.457 | model_finished |
| 6 | `\frac{3}{32}` | 1 | 4.0 | 0 | 29716 | 290.542 | model_finished |
| 7 | `\frac{3}{32}` | 1 | 4.0 | 0 | 25586 | 261.29 | model_finished |
| 8 | `3/32` | 1 | 4.0 | 0 | 33960 | 342.744 | model_finished |

## 工具使用

| 工具 | 调用次数 |
|---|---|
| `python` | 1 |

## 说明

- `answer_level_accuracy`：抽取答案与标准答案规范化后精确匹配，得到 8/8。
- `average_accuracy`：1.0；`average_step_score`：3.25/10。
- `rollout_35B_results` 为 6.2 规定的字段名；本项目按需求将模型换成 DeepSeek V4.1-Flash-1017，字段名保持与数据契约一致。
- 完整消息轨迹、工具调用、token 用量见同名 `_result.json`；机器可读指标见 `_metrics.json`。
