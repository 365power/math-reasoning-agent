# 科学推理数据质检报告（batch01 试跑批）

- 生成日期：2026-11-11
- 数据目录：`outputs/final/`
- 交付文件：
  - `delivery/batch01_math_6_20261111.jsonl`（数学 6 题）
  - `delivery/batch01_physics_1_20261111.jsonl`（物理 1 题）
  - `readable/` 下为缩进阅读副本，不参与交付校验

## 1. 总量与学科分布

| 学科 | 题目数 | 占比 | rollout 数 |
|---|---:|---:|---:|
| Mathematics | 6 | 85.7% | 48 |
| Physics | 1 | 14.3% | 8 |
| Chemistry | 0 | 0% | 0 |
| Biology | 0 | 0% | 0 |
| **合计** | **7** | **100%** | **56** |

本批是试跑批，尚未达到需求说明书 1.6 要求的四学科各占 25%。

## 2. 逐题结果

| id | 学科 | 8 次平均正确率 | 步骤分均值 | 单题 ≤50% |
|---|---|---:|---:|---|
| math_001_arctan_series | Mathematics | 1.0000 | 8.25 | 否 |
| math_entrance_jnu_2023_709_i8_log_integral | Mathematics | 1.0000 | 7.25 | 否 |
| math_entrance_jnu_2023_709_ii2_root_asymptotics | Mathematics | 1.0000 | 3.25 | 否 |
| math_entrance_jnu_2025_810_q6_rank_count | Mathematics | 0.8750 | 4.375 | 否 |
| math_entrance_jnu_2025_810_q9_logdet_bound | Mathematics | 0.7500 | 7.00 | 否 |
| math_entrance_njust_2023_840_q5_hilbert | Mathematics | 0.8750 | 8.25 | 否 |
| physics_20261110_backspin_incline_0f8419c2 | Physics | 0.7500 | 4.00 | 否 |

- 总体正确率：50 / 56 = **0.8929**。
- 总体步骤分均值：339 / 56 = **6.05**（满分 10）。
- 正式验收要求整体 ≤30%，本批未达到；按当前基线安排，本批作为试跑批接收，
  难度门槛留到后续阶段（见第 9 节）。

## 3. 来源与去重

来源：

- 暨南大学 2023 年 709 数学分析 A 卷（2 题）
- 暨南大学 2025 年 810 高等代数 A 卷（2 题）
- 南京理工大学 2023 年 840 高等代数（1 题）
- 同济《高等数学》无穷级数改编题（1 题）
- OpenStax, University Physics Volume 1, Section 11.1（1 题）

去重检查：

- `id`：7 个，全部唯一。
- `question`：7 条，文本无重复。
- 同来源题目为不同题号，不属于重复数据。

已知问题：`math_001_arctan_series` 的 `source_url` 仍是书目信息，`evidence.location` 使用 “Context section 1” 这类章节级定位，未达到“具体页码/题号或原始材料”的要求。按当前安排暂不处理。

## 4. 人工审核

- 7 题的 `human_review.status` 均为 `approved`。
- `review_result` 记录了独立推导、数值核对或等价形式核对。
- 需人工重点抽查低步骤分题目：`root_asymptotics`（3.25）、`rank_count`（4.375）、`physics`（4.00）。当前未重新评分。

## 5. Qwen3.5-35B-A3B rollout

- 每题 8 条，共 56 条，字段完整：`setting`、`messages`、`extracted_answer`、`answer-level_accuracy`、`step-level_score`、`usage`。
- 实际模型名：`Qwen/Qwen3.5-35B-A3B`。
- 答案判定：先做规范化精确匹配；失败且抽到非空答案时，由 LLM judge 判符号等价；`exact_match_accuracy` 保留原始精确匹配结果供复核。
- 56 条 rollout 均保留 `reasoning_content`，工具调用结果以 `role="tool"` 回填。

## 6. 轨迹数据

- 每题 1 条 `trajectory`，包含 `reasoning_content`、`tool_calls`、工具统计和终止原因。
- 当前轨迹取自 Qwen3.5-35B-A3B 的 rollout，与 8 次 rollout 使用同一模型。
- 需求说明书要求“至少一条强模型的带工具轨迹”；当前基线暂用 Qwen3.5-35B-A3B，独立强模型轨迹列为后续升级项（见第 9 节）。

## 7. 格式与文本完整性

- 编码：UTF-8，无 BOM；换行：`\n`；每条记录一行紧凑 JSON。
- 顶层字段：18 个，名称与 6.1 一致；无 `designation_rationale` 等旧字段。
- rollout 字段：`answer-level_accuracy`、`step-level_score` 使用连字符。
- trajectory 字段：`answer_level_accuracy`、`step_level_score` 使用下划线。
- 文件名：`<batch>_<domain>_<count>_<YYYYMMDD>.jsonl`；数学 6 条、物理 1 条。
- 文本完整性：最终交付 0 个 U+FFFD、0 个 NUL、0 个控制字符；英文检查 0 个中文字符。
- 采集编码修复：python 工具改为 `-I -X utf8`，避免 `-I` 忽略 `PYTHONIOENCODING` 导致 Unicode 输出变成 U+FFFD；新增单测 `test_python_tool_keeps_unicode_intact`。
- 修复前遗留的内部乱码产物已移出项目，保存到系统临时备份目录，不参与交付。

## 8. 校验结果

第一层（输入题目格式）：

```bash
python -m agent_project.validation --cases cases/
# PASS (0 error(s), 0 warning(s))
```

第二层（最终交付格式）：

```bash
python -m agent_project.validation --jsonl outputs/final/delivery/batch01_math_6_20261111.jsonl
python -m agent_project.validation --jsonl outputs/final/delivery/batch01_physics_1_20261111.jsonl
# PASS（仅难度告警）
```

难度强制检查：

```bash
python -m agent_project.validation --jsonl ... --enforce-difficulty
# FAIL：每题平均正确率 > 50%，整体 > 30%
```

测试：

```bash
python -m unittest discover -s tests -v
# Ran 20 tests, OK
```

## 9. 当前基线的已知后续项

按当前安排，下面这些不作为本基线的阻塞项，后续阶段再补：

1. **难度**：单题 ≤50%、整体 ≤30% 的正式验收门槛。
2. **强模型轨迹**：当前 trajectory 为 Qwen3.5-35B-A3B，后续换独立强模型。
3. **Judge 模型**：当前为 `deepseek-flash`；后续按需求切换为 `gpt-oss-120` 或 `gemini-3.5-flash-thinking`。
4. **原始来源与证据**：`math_001_arctan_series` 仍是章节级引用；后续补具体页码/题号或公开原始材料。
5. **交付目录**：后续补 `scientific_reasoning_data/batch_01/main_file/` 与 `scripts/`（`format_check.py`、`score.py`）。
6. **学科分布**：后续补化学、生物，达到四学科各 25%。

本基线的验收口径：格式、字段、英文、一行一条 JSONL、文本完整性和两层校验。
