# Math Interactive Benchmark（naive / 情景推理式问答 / pass@k）

本目录提供一套面向数学题的交互式 benchmark 流水线，用来对比三种评测方式：

- **naive**：模型直接解题，judge 仅做“答案等价性”0/1 判定（`naive.py`）
- **情景推理式问答**：模型可向“judger”发起多轮 **Yes/No/Both/Irrelevant** 问答以缩小不确定性，最后再提交答案并判等价（`turtle.py`，文件名为历史沿用）
- **pass@k**：在同一题目集合上对同一模型进行多次采样/复评，并根据 naive 与问答法的 token 比例为每个模型估算合适的 \(k\)（`passk_eval.py`）

默认对接 **OpenRouter（OpenAI-compatible）**。

## 目录结构

```text
src/math/
  README.md
  data/
    puzzle_math.json
  naive.py
  turtle.py
  passk_eval.py
  naive.sh
  turtle.sh
  compute_k.sh
  run_passk.sh
```

## 文件说明

- **`data/puzzle_math.json`**：示例/默认数据集（hard set），每条只含 `problem/solution/exp_ans`
- **`naive.py`**：直接解题 + judge 判等价（支持断点续跑、`wrong_limit` 截断）
- **`turtle.py`**：情景推理式问答解题（多轮 Q&A）+ judge 判等价（支持断点续跑）
- **`passk_eval.py`**：计算 \(k\)（基于 naive∩问答 的输出 token 估算）并跑 pass@k
- **`naive.sh` / `turtle.sh`**：批量跑评测的示例脚本
- **`compute_k.sh` / `run_passk.sh`**：pass@k 的便捷脚本（按模型并行启动）

> 说明：虽然脚本文件名/输出文件名里仍保留 `turtle`（例如 `turtle.py`、`__turtle__`、`turtle_history`），但这里的任务表述统一为 **Situation Puzzle / 情景推理** 风格的多轮问答。

## 环境变量

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"   # 可选
```

`naive.py` / `turtle.py` 也提供参数 `--openrouter_base_url`（默认 `https://openrouter.ai/api/v1`）。

## 依赖安装

这些脚本至少会用到：

```bash
pip install openai python-dotenv tqdm
```

如需运行 pass@k 的统计/某些环境下的绘图脚本（如果你自己补充），可能还需要：

```bash
pip install pandas matplotlib
```

## 数据格式约定

`naive.py` / `turtle.py` 输入的 dataset JSON 必须是 **list[dict]**。每条建议包含：

- **`problem`**：题面（string）
- **`solution`**：参考解/解析（string，可为空但建议保留，供 judger 使用）
- **`exp_ans`** 或 **`final_answer`**：标准答案（string；代码会优先读 `final_answer`，否则读 `exp_ans`）

示例（与 `data/puzzle_math.json` 一致）：

```json
[
  {
    "problem": "...",
    "solution": "...",
    "exp_ans": "B"
  }
]
```

## 输出文件命名约定（自动生成）

为便于批量实验对齐，输出文件名自动编码了数据集名、provider、player/judge：

- **naive（`naive.py`）**
  - `results/<dataset>__openrouter__<player>__judge=<judge>.json`
- **情景推理式问答（`turtle.py`，历史命名）**
  - `results/<dataset>__turtle__openrouter__<player>__judge=<judge>.json`
- **pass@k（`passk_eval.py`）**
  - `results/<dataset>__passk__openrouter__<player>__judge=<judge>.json`

其中 `<player>`/`<judge>` 会把 `/` 替换为 `_` 以便落盘。

## 最小可跑流程（推荐顺序）

下面以 `data/puzzle_math.json` 与 `dataset_name=hle` 为例。

### 1) 跑 naive（直接解题）

```bash
python naive.py \
  --dataset_path data/puzzle_math.json \
  --dataset_name hle \
  --player_model "openai/gpt-5-mini" \
  --judge_model "x-ai/grok-4.1-fast" \
  --max_tokens 5000
```

可选：

- `--wrong_limit N`：只收集到 N 条“确实做了且 judge 判错”的样本后提前停止（用于构造 hard set/控成本）
- `--max_n N`：只跑前 N 条

### 2) 跑情景推理式问答（多轮 Q&A）

```bash
python turtle.py \
  --dataset_path data/puzzle_math.json \
  --dataset_name hle \
  --player_model "openai/gpt-5-mini" \
  --judge_model "x-ai/grok-4.1-fast" \
  --out_dir results \
  --max_rounds 20
```

或按 `turtle.sh` 里的 `PLAYERS` 并行批跑：

```bash
bash turtle.sh
```

### 3) 只计算 \(k\)（不跑 pass@k）

```bash
bash compute_k.sh hle results "x-ai/grok-4.1-fast"
```

它会在 `results/` 下写出 `hle__passk_k_stats.json`。

### 4) 跑 pass@k（可选）

`run_passk.sh` 会自动筛选 **naive 与问答法都已有结果** 的模型，确保题目交集对齐：

```bash
bash run_passk.sh --max-n 50
```

常用参数：

- `--k 5`：覆盖为所有模型共用同一个 \(k\)
- `--verbose`：打印更详细的调用/进度
- `--skip-draw`：跳过末尾的绘图步骤（当前仓库未必包含 `draw_passk.py`）

## 断点续跑（resume）行为说明

- `naive.py`：若输出文件已存在，会加载旧 JSON，并跳过“已处理且记录合法”的 `problem`；`wrong_limit` 也会计入旧文件里“做了但做错了”的记录。
- `turtle.py`：若输出文件已存在，会跳过已经有 `turtle_history` 的 `problem`，并在每做完一题后覆盖写回，方便中断恢复。

## 成本与注意事项

- judge 判等价本身也是一次模型调用；**judge 选择会显著影响结果**。
- 情景推理式问答会显著增加调用量，`--max_rounds` 是最直接的成本旋钮。
- `turtle.sh` / `run_passk.sh` 会并行启动多个 Python 进程；请留意 provider 的速率限制与费用。

