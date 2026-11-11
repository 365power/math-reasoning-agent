# 评测报告：math_entrance_jnu_2023_709_i8_log_integral

**题目**：Let \(a\) and \(b\) be real numbers with \(0<a<b\). Evaluate the improper integral \(\int_0^1 \sin(\log(1/x))\,\frac{x^b-x^a}{\log x}\,dx\), where \(\log\) is the natural logarithm.

**标准答案**：`\arctan(b+1)-\arctan(a+1)`　**满分**：10

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
| `average_accuracy` | 0.875 |
| `correct_rollouts` | 7 |
| `average_step_score` | 7.25 |
| `step_score_max` | 10 |
| `total_tool_calls` | 18 |
| `successful_tool_calls` | 18 |
| `failed_tool_calls` | 0 |
| `tool_call_success_rate` | 1.0 |
| `total_tokens` | 193535 |
| `average_tokens_per_rollout` | 24191.9 |
| `total_reasoning_tokens` | 118026 |
| `average_duration_seconds` | 192.62 |
| `termination_counts` | model_finished=8 |
| `judge_usage` | prompt_tokens=10396, completion_tokens=12169, total_tokens=22565, reasoning_tokens=11272 |

## 逐次 rollout

| # | 抽取答案 | 答案正确 | 步骤分 | 工具调用 | tokens | 用时(s) | 停止原因 |
|---|---|---|---|---|---|---|---|
| 1 | `\arctan(b+1) - \arctan(a+1)` | 1 | 8.0 | 2 | 15566 | 124.904 | model_finished |
| 2 | `\arctan\left(\frac{1}{a+1}\right) - \arctan\left(\frac{1}{b+1}\right)` | 0 | 10.0 | 4 | 22870 | 166.748 | model_finished |
| 3 | `\arctan(b+1) - \arctan(a+1)` | 1 | 8.0 | 3 | 35933 | 285.708 | model_finished |
| 4 | `\arctan(b+1) - \arctan(a+1)` | 1 | 2.0 | 2 | 23851 | 184.35 | model_finished |
| 5 | `\arctan(b+1) - \arctan(a+1)` | 1 | 8.0 | 0 | 21222 | 226.847 | model_finished |
| 6 | `\arctan(b+1) - \arctan(a+1)` | 1 | 2.0 | 2 | 29241 | 219.554 | model_finished |
| 7 | `\arctan(b+1) - \arctan(a+1)` | 1 | 10.0 | 2 | 25384 | 186.411 | model_finished |
| 8 | `\arctan(b+1) - \arctan(a+1)` | 1 | 10.0 | 3 | 19468 | 146.44 | model_finished |

## 工具使用

| 工具 | 调用次数 |
|---|---|
| `python` | 15 |
| `write_file` | 3 |

## 说明

- `answer_level_accuracy`：抽取答案与标准答案规范化后精确匹配，得到 7/8。
- `average_accuracy`：0.875；`average_step_score`：7.25/10。
- `rollout_35B_results` 为 6.2 规定的字段名；本项目按需求将模型换成 DeepSeek V4.1-Flash-1017，字段名保持与数据契约一致。
- 完整消息轨迹、工具调用、token 用量见同名 `_result.json`；机器可读指标见 `_metrics.json`。
