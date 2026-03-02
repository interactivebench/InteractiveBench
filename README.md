# InteractiveBench

交互式（interactive）benchmark 合集：通过**多轮交互**（对局 / 问答 / 评审）来评估不同大模型在策略、推理与不确定性消解上的表现。

本仓库的目标是把“能跑的实验代码”整理成一个**可复现、可扩展、可对比**的 benchmark 仓库：清晰的入口、可断点续跑、稳定的结果落盘与最少的隐藏假设。

## 仓库内容一览

- **`src/trust_game/`**：Repeated Prisoner’s Dilemma（信任游戏）多智能体对战与 tournament（baseline + LLM，支持 OpenRouter）。
- **`src/situation_puzzle/`**：Situation Puzzle（情景推理）——固定 judge + 被测 player 的多轮问答评测，输出完整 transcript。
- **`src/math/`**：数学交互式评测流水线：naive 解题 vs 情景推理式问答解题，以及 pass@k 复评（主要面向 OpenRouter）。

## 快速开始（通用）

### 环境要求

- Python **3.10+**
- 你需要有可用的模型调用端点（本仓库多数脚本默认使用 **OpenRouter 的 OpenAI-compatible API**）

### 统一的环境变量（建议）

多数脚本会读取以下变量（可写进各子目录的 `.env`，或直接 export）：

- **`OPENROUTER_API_KEY`**：必需
- **`OPENROUTER_BASE_URL`**：可选，默认 `https://openrouter.ai/api/v1`

示例：

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
```

### 依赖安装建议

各子 benchmark 的依赖不同。最简单的方式是按你要跑的子目录 README 安装：

- `src/trust_game/README.md`
- `src/situation_puzzle/README.md`
- `src/math/README.md`

如果你希望一次装全（用于跑完整合集），通常需要这些包（偏“能覆盖大多数脚本”的合集安装）：

```bash
pip install openai python-dotenv tqdm datasets pandas matplotlib httpx
```

> 说明：不同任务只需要其中一部分；请以各子目录 README 为准。

## 目录结构

```text
InteractiveBench/
  README.md
  LICENSE
  src/
    trust_game/
    situation_puzzle/
    math/
```

## 运行入口（按子 benchmark / 子目录）

> 约定：本仓库**不移动目录结构**。部分脚本/字段沿用历史命名（例如 `src/math/turtle.py`、输出文件名中的 `__turtle__`、字段 `turtle_history`），但语义已统一为 **Situation Puzzle / 情景推理式问答**。

### 1) Repeated Prisoner’s Dilemma（`src/trust_game/`）

- **适合评测**：策略、互惠/报复、长期收益最大化（\(\delta\) 继续概率）
- **入口**：`python main.py`（支持 `single` / `tournament` / `ablation`）
- **输出**：JSON 结果 + `plots/` 下图像（见子目录 README）

详细用法见：`src/trust_game/README.md`

### 2) Situation Puzzle（情景推理，`src/situation_puzzle/`）

- **适合评测**：提问效率、信息增益、在受限反馈（YES/NO/…）下的推理与收敛能力
- **入口**：`bash run_benchmark.sh results`
- **输出**：每个（player, judge）pair 一个 JSON（含完整对话记录）；可选生成 CSV 汇总与图表（见子目录 README）

详细用法见：`src/situation_puzzle/README.md`

### 3) Math Interactive（`src/math/`）

- **适合评测**：在“可询问判定器/裁判”的交互设定下，模型如何用问题消解不确定性并提升正确率；以及与 naive 解题的对比、pass@k 复评等
- **入口**：以 `naive.py`（naive）与 `turtle.py`（情景推理式问答）为核心，配套 `run_passk.sh` / `compute_k.sh`

详细用法见：`src/math/README.md`

## 结果产物与复现

- **结果落盘**：多数脚本会把运行结果落到各自目录下的 `results/`（或你指定的输出目录），并尽量包含可复现的 meta 信息（模型名、超参等）。
- **断点续跑**：多数脚本支持“输出文件存在则跳过已完成样本/对局”的 resume 逻辑（具体见各子目录 README）。
- **复现建议**：更系统的建议见 `REPRODUCIBILITY.md`（版本/依赖/seed/并发/缓存等）。

## 贡献

- 贡献规范见 `CONTRIBUTING.md`（新增 benchmark 子目录、结果格式、README 要求等）。

## 引用 / 使用许可

- **License**：MIT（见 `LICENSE`）
- 如你在论文/报告中使用本仓库的评测流程，建议在引用中注明：仓库名 + 运行的子 benchmark + commit hash（若你 fork 并有修改）。
