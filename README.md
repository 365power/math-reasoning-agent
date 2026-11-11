# 科学推理与研究数据采集 Agent（数学/物理基线）

通过 Agent 循环和工具分发表，连接 OpenAI 兼容的大模型 API，
对数学/物理题做多次 rollout。最终交付物是 6.1/6.2 规定的一条完整记录：
题目数据、轨迹、8 次 35B rollout 和正确率全部在一个对象里，
按 `5.1` 写成 `UTF-8`、一行一条、紧凑 JSON 的 `.jsonl` 文件。

当前基线：**7 道题（数学 6 + 物理 1）**，每题 8 次
**Qwen3.5-35B-A3B** rollout，评分模型为 `deepseek-flash`。
解题模型走 ModelScope 的 OpenAI 兼容接口，密钥从 `.env` 读取，不在代码里硬编码。

> 基线目标是把 1–4 道题的全链路跑通并交付格式合规数据；当前已跑 7 道
> （数学 6 + 物理 1）作为试跑批。难度、强模型轨迹、Judge 模型和
> 6.3 目录结构属于后续阶段升级项，详见文末“后续升级项”。

---

## 0. 当前基线状态

| 项目 | 状态 |
|---|---|
| 题目 | `cases/` 下 7 道（数学 6、物理 1） |
| rollout | 每题 8 次，模型 `Qwen/Qwen3.5-35B-A3B` |
| 评分 | `rubric_based_llm_judge`，judge 为 `deepseek-flash` |
| 最终交付 | `outputs/final/delivery/batch01_math_6_20261111.jsonl`、`outputs/final/delivery/batch01_physics_1_20261111.jsonl` |
| 可读副本 | `outputs/final/readable/`（缩进 JSON，不参与交付校验） |
| 质量报告 | `outputs/final/quality_report.md` |
| 第一层校验 | `python -m agent_project.validation --cases cases/` → PASS |
| 第二层校验 | 两个交付 JSONL → PASS（仅难度告警） |
| 测试 | `python -m unittest discover -s tests -v` → 20 个全过 |

基线阶段**不追求**难度 ≤50%/≤30%、独立强模型轨迹和指定 Judge；
这些是后续阶段要补的配置。格式、字段、英文、一行一条 JSONL、
文本完整性和两层校验已经达标。

---

## 1. 题目与设计意图

题目：

\[
\sum_{n=1}^{\infty}\arctan\frac{1}{2n^{2}}
\]

标准答案：

\[
\frac{\pi}{4}
\]

选择理由：

1. 条件完整、答案唯一，适合自动判分。
2. 通项不能直接求和；比值判别法极限为 1，判别失效。
3. 关键结构隐藏在反正切差公式中：
   \(\arctan\frac{1}{2n^2}=\arctan(2n+1)-\arctan(2n-1)\)，随后裂项相消。
4. 常见失败模式：改用比较判别法判敛散、把 arctan 近似成通项、
   漏掉 \(\arctan 1=\pi/4\)、忘记 \(\arctan(2N+1)\to\pi/2\)。
5. 因此它对 35B 级模型构成“步骤分可能很高、答案却容易错”的困扰，
   正好对应 6.1 的 `design_rationale` 和 6.2 的 `average_accuracy`。

这道题是最早的单题样例，数据在 `cases/math_001_arctan_series/case.json`；
当前 `cases/` 下还包含 6 道送审题，字段同样严格对应 6.1。

---

## 2. 数据结构与 Agent 对应关系

| 名称 | 含义 | 代码位置 |
|---|---|---|
| **题目与标准（6.1）** | 6.1 静态字段：`id`、`question`、`answer`、`rubric`、`solution_steps`、`evidence`、`human_review` 等 | `cases/<题目id>/case.json`、`agent_project/case.py` |
| **轨迹与评测（6.2）** | 6.2 动态字段：`trajectory`、`rollout_35B_results`、`average_accuracy`，含 messages、tool_calls、usage、tool_statistics | `agent_project/runner.py` |
| **Agent 内核** | `while True` 循环 + “工具名 → 处理函数”查表分发 | `agent_project/agent.py`、`agent_project/tools/registry.py` |
| **协议适配** | 参照 `agent.py`：OpenAI 兼容 `chat.completions`、`tool_calls`、`role="tool"`、`tool_call_id` | `agent_project/llm.py` |

一次 rollout 的数据流：

```
case.question
   ↓
system + user messages
   ↓
┌─────────────────────────────────────────────┐
│ chat(messages, tools)                       │
│ 没有 tool_calls → 抽取 \boxed{}，结束        │
│ 有 tool_calls → 回填 assistant              │
│ 查表执行 python/read_file/write_file/...    │
│ 结果包成 role="tool" 回填                   │
└──────────────────┬──────────────────────────┘
                   └──→ 再问模型
   ↓
trajectory + usage + tool_statistics
   ↓
答案精确匹配 + rubric 评分
   ↓
result.json / metrics.json / report.md
   ↓
整合成 6.1/6.2 的一条记录 → <batch>_<domain>_<count>_<date>.jsonl
```

---

## 3. 目录结构

```
math_reasoning_agent/
├─ .env.example              # API 密钥与参数模板
├─ requirements.txt
├─ run.py                    # 命令行入口
├─ cases/
│  ├─ math_001_arctan_series/case.json
│  ├─ math_entrance_jnu_2023_709_i8_log_integral/case.json
│  ├─ ...                    # 一题一个文件夹，文件夹名就是题目 id
│  └─ physics_20261110_backspin_incline_0f8419c2/case.json
├─ data/                     # 文件工具与 python 工具的工作区
├─ outputs/
│  ├─ final/                 # 当前基线交付
│  │  ├─ delivery/*.jsonl    # 最终提交文件（一行一条记录）
│  │  ├─ readable/*.json     # 人工阅读副本，不参与交付校验
│  │  └─ quality_report.md   # 5.4 质检报告
│  └─ scheduler/runs/        # 调度器运行记录
├─ tests/
│  ├─ test_pipeline.py
│  └─ test_validation.py
└─ agent_project/
   ├─ config.py              # 环境变量与路径
   ├─ llm.py                 # OpenAI 兼容客户端 + Mock 客户端
   ├─ agent.py               # Agent 循环 + 工具分发 + 异常兜底
   ├─ case.py                # 6.1 字段的 pydantic 模型
   ├─ judge.py               # \boxed 抽取、答案规范化、rubric 评分
   ├─ runner.py              # 8 次 rollout、轨迹、token、指标
   ├─ integrate.py           # 整合单条交付记录、写 JSONL
   ├─ validation.py          # 两层数据校验（输入格式 / 最终交付）
   ├─ report.py              # Markdown 报告
   ├─ scheduler/             # 多 rollout 调度器（worker 子进程并发）
   └─ tools/
      ├─ base.py             # BaseTool、safe_path、截断
      ├─ registry.py         # 工具注册表（唯一事实来源）
      ├─ python_tool.py      # 隔离子进程执行 Python
      └─ file_tools.py       # read_file / write_file / list_files
```

---

## 4. 安装

```bash
cd math_reasoning_agent
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

> Windows 用户请使用 **PowerShell 7**（`pwsh`）运行命令，不要用 Windows PowerShell 5.1；
> 5.1 的默认编码会导致中文路径和输出乱码。项目内部已统一使用 UTF-8 读写。

如果只想跑 mock 流水线，不安装 `openai` 也可以吗？**不可以**：
`llm.py` 在导入时依赖 `openai`。请按上面的步骤安装。

---

## 5. 配置 API

```bash
# Windows
copy .env.example .env
# macOS / Linux
# cp .env.example .env
```

编辑 `.env`。当前基线的解题模型是 ModelScope 上的 Qwen，变量名仍沿用
`DEEPSEEK_*`（因为客户端是 OpenAI 兼容接口，不绑定具体服务商）：

```ini
DEEPSEEK_API_KEY=你的 ModelScope 密钥
DEEPSEEK_BASE_URL=https://api-inference.modelscope.cn/v1
DEEPSEEK_MODEL=Qwen/Qwen3.5-35B-A3B

# 评分模型；留空则复用解题模型
JUDGE_API_KEY=你的 DeepSeek 密钥
JUDGE_BASE_URL=https://api.deepseek.com
JUDGE_MODEL=deepseek-flash

TEMPERATURE=1.0
TOP_P=0.95
MAX_TOKENS=16384
ROLLOUTS=8
MAX_TOOL_ROUNDS=12
TOOL_TIMEOUT=30
```

如果改用 DeepSeek 作为解题模型，只改三行：

```ini
DEEPSEEK_API_KEY=sk-你的 DeepSeek 密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

> `DeepSeek V4.1-Flash-1017` 是展示名，DeepSeek API 实际接受的 model id 是
> `deepseek-flash`（另一个可用 id 是 `deepseek-v4-pro`）。服务商调整命名时，
> 只改 `DEEPSEEK_MODEL` 即可，代码无需动。
>
> 基线阶段 judge 暂用 `deepseek-flash`；需求建议的
> `gpt-oss-120` / `gemini-3.5-flash-thinking` 属于后续升级项。

---

## 6. 运行

### 6.1 先跑 mock（不花 token，验证全链路）

```bash
python run.py --mock --rollouts 2
```

预期：

- 模型先调用 `python` 做数值核验，再给出含 `\boxed{\frac{\pi}{4}}` 的推导
- `average_accuracy = 1.0`
- `outputs/` 下生成三份文件

### 6.2 正式跑 8 次 rollout

```bash
python run.py --rollouts 8
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--case cases/math_001_arctan_series/case.json` | 指定题目 |
| `--rollouts 8` | 覆盖 `.env` 中的 `ROLLOUTS` |
| `--mock` | 使用脚本化模型，不调用 API |
| `--no-llm-judge` | 用启发式评分，不调用评分模型 |
| `--output-dir outputs` | 输出目录 |
| `--batch batch01` | 交付 JSONL 的批次名 |

建议首次正式运行时先用 `--rollouts 2` 控制成本，确认无误后再跑满 8 次。
最终提交要求 8 次，`run.py` 和调度器都会对 rollout 数和模型名给出校验提示。

### 6.3 两层数据校验

```bash
# 第一层：提交上来的题目数据是否符合 6.1（英文、rubric=10、证据定位等）
python -m agent_project.validation --case cases/math_001_arctan_series/case.json
python -m agent_project.validation --cases cases/

# 第二层：最终交付 JSONL 是否符合 5.1/6.1/6.2
python -m agent_project.validation \
    --jsonl outputs/final/delivery/batch01_math_6_20261111.jsonl
python -m agent_project.validation \
    --jsonl outputs/final/delivery/batch01_physics_1_20261111.jsonl

# mock 调试时允许模型名不是 Qwen3.5-35B-A3B
python -m agent_project.validation --jsonl ... --allow-model-mismatch

# 把关难度：单题平均准确率 > 50%、整体 > 30% 直接判失败
# 基线阶段难度未达标，这条会失败，属于预期；格式校验用上面的命令即可
python -m agent_project.validation --jsonl ... --enforce-difficulty
```

第二层会检查：UTF-8 无 BOM、`\n` 换行、一行一条紧凑 JSON、文件名数量一致、
字段名和层级、英文文本、8 条 rollout、连字符字段名、`trajectory` 的
`reasoning_content` / `tool_calls` / 工具统计、答案与步骤分范围、
`average_accuracy` 与逐条结果一致，以及文本完整性（U+FFFD、NUL、乱码）。

### 6.4 接收其他同学的数据批量跑

1. 提交者按 `cases/<题目id>/case.json` 的字段格式准备 6.1 题目，
   放进 `cases/`。**唯一规定格式**：一题一个文件夹，文件夹名就是题目
   `id`，里面只有一个 `case.json`，即 `cases/<题目id>/case.json`。
   不接受平铺 JSON，也不接受图片、PDF 等附件。
2. 先做第一层校验，全部通过再跑：

```bash
python -m agent_project.validation --cases cases/
```

3. 调度器按目录批量跑，每题默认 8 次：

```bash
python -m agent_project.scheduler --cases-dir cases --rollouts 8 \
    --batch batch01 --concurrency 4
```

4. 产物：

```
outputs/scheduler/delivery/<batch>_<domain>_<count>_<YYYYMMDD>.jsonl
outputs/scheduler/runs/<run_id>/cases/<case_id>_data_item.json
```

正式交付的 `.jsonl` 按 5.1 必须“一行一条记录”，所以单条记录是一整行。
如果要人工阅读，加 `--readable-delivery`，会在 `outputs/scheduler/readable/`
额外生成同名、缩进 2 空格的 `.json` 副本；可读副本不参与交付校验。

5. 交付前做第二层校验：

```bash
python -m agent_project.validation \
    --jsonl outputs/scheduler/delivery/<batch>_<domain>_<count>_<date>.jsonl
```

基线阶段不要加 `--enforce-difficulty`；难度尚未达标，加了会按预期失败。

只用 mock 验证整条批量链路：

```bash
python -m agent_project.scheduler --cases-dir cases --rollouts 8 --mock --batch check01
```

---

## 7. 输出文件

| 文件 | 内容 |
|---|---|
| `outputs/<case_id>_result.json` | 内部结果：题目字段 + 全部 rollout 的完整调试信息 |
| `outputs/<case_id>_metrics.json` | 参数、平均正确率、步骤分、token、工具成功率、耗时 |
| `outputs/<case_id>_report.md` | 人类可读报告，含逐次 rollout 表与工具统计 |
| `outputs/<case_id>_data_item.json` | 按 6.1/6.2 整理好的**单条交付记录**（便于人工查看） |
| `outputs/batch01_<domain>_<count>_<YYYYMMDD>.jsonl` | 单机运行生成的最终提交文件：UTF-8 无 BOM，一行一条记录 |
| `outputs/final/delivery/batch01_math_6_20261111.jsonl` | **当前基线数学最终提交文件**（6 题） |
| `outputs/final/delivery/batch01_physics_1_20261111.jsonl` | **当前基线物理最终提交文件**（1 题） |
| `outputs/final/readable/*.json` | 人工阅读副本，缩进排版，不参与交付校验 |
| `outputs/final/quality_report.md` | 5.4 质检报告：逐题正确率、步骤分、来源、去重、审核与校验结果 |

调度器运行时：

```
outputs/scheduler/
├─ batch01_progress.jsonl                 # 逐 worker 进度，内部调试用
├─ delivery/
│  └─ batch01_math_1_<YYYYMMDD>.jsonl     # 最终交付，一行一条完整记录
└─ runs/<run_id>/
   ├─ cases/<case_id>_data_item.json      # 每题的单条交付记录
   ├─ cases/<case_id>_report.md
   └─ report.md
```

文件名规则完全按 5.1：`<批次>_<学科>_<数量>_<YYYYMMDD>.jsonl`，
学科使用 `math` / `physics` / `chemistry` / `biology`。一个批次里有多个学科时，
按学科拆成多个文件。

已有的内部结果也可以单独整理成一条记录或 JSONL：

```bash
python -m agent_project.integrate --result outputs/<case_id>_result.json \
    --jsonl-dir outputs
```

### 7.1 一条交付记录的字段

顶层只有 6.1 规定的 18 个字段，不再包一层 `data_item` / `trajectories`：

- 元数据：`id`、`source_title`、`source_url`、`domain`、`subdomain`、`file_path`
- 题目：`context`、`question`、`answer`、`rubric`
- 设计：`design_rationale`、`solution_steps`、`evidence`、`scoring_method`、`human_review`
- 轨迹：`trajectory`（数组，至少一条带思维链、带工具轨迹；当前基线为 Qwen，强模型版本见第 12 节）
- 难度：`rollout_35B_results`（8 条 Qwen3.5-35B-A3B rollout）、`average_accuracy`

`trajectory` 每项：`setting`、`messages`（assistant 保留 `reasoning_content` 和
`tool_calls`）、`tools`、`extracted_answer`、`evaluation`、`usage`、
`tool_statistics`、`statistics`、`termination`。`tools` 是扁平结构
（`type` / `name` / `description` / `parameters`）。

`rollout_35B_results` 每项：`rollout_id`、`setting`、`messages`、
`extracted_answer`、`answer-level_accuracy`、`step-level_score`、`usage`。
注意 `answer-level_accuracy` 和 `step-level_score` 按 6.1 使用**连字符**，
与 `trajectory.evaluation` 里的下划线字段不同。

### 7.2 指标定义

| 指标 | 定义 |
|---|---|
| `answer_level_accuracy` | `\boxed{}` 抽取答案与标准答案精确匹配为 1；精确匹配失败但答案非空且 LLM judge 判为等价时为 1。0 或 1 |
| `step_level_score` | 评分模型按 rubric 逐条命中的 points 之和，满分 10 |
| `average_accuracy` | 所有 rollout 的 `answer_level_accuracy` 平均值 |
| `average_step_score` | 所有 rollout 的步骤分平均值 |
| `tool_call_success_rate` | 成功工具调用 / 总工具调用 |
| `total_tokens` | 所有 rollout 的 prompt + completion token 之和 |
| `average_duration_seconds` | 平均单次 rollout 耗时 |
| `termination_counts` | 各停止原因出现次数（`model_finished` / `max_tool_rounds` / `max_tokens` / `error`） |

### 7.3 答案规范化

支持以下等价写法：

```
\frac{\pi}{4}   \dfrac{\pi}{4}   \pi/4   π/4   0.785398163397448
```

模型把整个等式放进 `\boxed{}`（如
`\displaystyle\sum_{n=1}^{\infty}\arctan\frac{1}{2n^2}=\frac{\pi}{4}`）时，
只取最后一个顶层等号的右侧参与比较，因此仍判为正确。

其他数值答案会尝试按浮点数比较；未命中时可用
`--no-llm-judge` 之外的方式人工复核，或在 `judge.py` 中补充等价形式。

---

## 8. 换成 DeepSeek 或别的模型

当前基线已经是 Qwen3.5-35B-A3B（见第 5 节）。如果要换回 DeepSeek 或其他
OpenAI 兼容模型，只改 `.env` 三行，然后运行 `python run.py --rollouts 8`：

```ini
DEEPSEEK_API_KEY=你的 DeepSeek 密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

6.2 的字段名 `rollout_35B_results` 保持不变，
`setting.model_name` 会记录实际调用的模型，方便复核。

---

## 9. 换成另一道题

复制 `cases/<已有题目id>/case.json`，新建 `cases/<新题目id>/case.json`
（文件夹名必须等于题目 `id`），保持 6.1 字段不变：

- `rubric.total_points` 和 `scoring_method.max_score` 都必须是 10，
  `rubric.criteria` 的 `points` 之和也必须是 10
- `answer` 必须是可抽取、可比较的最终答案
- `solution_steps` 至少一条；`evidence` 至少一条，`location` 要写到具体页码/章节/公式/题号
- 题干、答案、评分点、分步过程、证据内容和审核结果必须是英文
- `human_review.status` 建议填 `approved`

校验：

```bash
python -m agent_project.validation --case cases/<新题目id>/case.json
python -m unittest discover -s tests -v
```

---

## 10. 安全与限制

- `python` 工具会在本机子进程中执行模型生成的代码。`-I -X utf8`、超时和工作区
  只能降低风险，**不是安全沙箱**。请只在临时目录、容器或虚拟机中运行，
  不要放密钥、隐私数据或生产代码。
- 文件工具通过 `safe_path` 限制在工作区 `data/` 内；bash 类命令未提供。
- 8 次 rollout 会产生真实费用，先用 `--rollouts 2` 验证。
- 评分模型可能误判步骤分；`answer_level_accuracy` 先做字符串精确匹配，
  失败时再由 LLM judge 判断符号等价（如 `log(5/4)/(4(log2)^2)` 与
  `log(5/4)/(log4)^2`）。抽取不到答案时不采信 judge。
  `exact_match_accuracy` 保留原始精确匹配结果供复核。
- `reasoning_content` 的返回格式因服务商而异；轨迹会保存，但不会在后续
  请求中回传，避免部分 API 因未知字段报错。

---

## 11. 测试

```bash
python -m unittest discover -s tests -v
```

当前共 20 个测试，覆盖：题目字段校验、`\boxed{}` 嵌套抽取、答案规范化、
路径越界拦截、python 工具执行、Unicode 输出完整性、两层数据校验、
mock 端到端 rollout。

---

## 12. 后续升级项（不属于当前基线）

当前基线只要求跑通 1–4 道题并交付格式合规的数据。以下项目留到后续阶段：

- **难度**：单题 8 次平均正确率 ≤50%、整体 ≤30%。
- **强模型轨迹**：`trajectory` 换成独立强模型，不再复用 Qwen rollout。
- **Judge**：按需求使用 `gpt-oss-120` 或 `gemini-3.5-flash-thinking`。
- **来源与证据**：为每道题补具体页码/题号或原始材料。
- **6.3 目录**：`scientific_reasoning_data/batch_01/main_file/`、
  `scripts/format_check.py`、`score.py`。
- **学科分布**：数学/物理/化学/生物各 25%。

这些不影响当前基线的格式校验和交付。
