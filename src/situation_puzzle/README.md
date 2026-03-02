# Situation Puzzle Benchmark（情景推理）

这是一个最小可复现的 Situation Puzzle（情景推理）benchmark，用于评估不同 LLM 作为 **player** 的提问与收敛能力；另有一个固定模型作为 **judge**（知道谜底）。

**没有提示（hint）功能**：judge 只会对问题返回 `YES/NO/BOTH/IRRELEVANT`，并对 `FINAL:` 的最终猜测返回 `CORRECT/INCORRECT`。

## Files

- `benchmark.py`：逐题评测 runner（**单进程、顺序执行、可 resume**）
- `client.py`：OpenAI-compatible 客户端封装（当前默认对接 OpenRouter）
- `puzzle_loader.py`：加载题库 `puzzles_en.json`
- `puzzles_en.json`：英文题库
- `run_benchmark.sh`：便捷脚本（按 player 列表并行启动多个进程）
- `requirements.txt`：依赖列表

## Setup

### 1) 设置凭证 / 端点

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"   # 可选
```

> 注意：当前 `benchmark.py` 内部把 base_url 固定为 `https://openrouter.ai/api/v1`；如需自定义端点，请相应修改源码或自行封装 client。

### 2) 安装依赖

```bash
pip install -r requirements.txt
```

### 3) 运行

在本目录下运行：

```bash
bash run_benchmark.sh results
```

Outputs:
- `results/<player>__<judge>.json`：一个（player, judge）pair 一个文件，包含完整 transcript 与逐题结果

