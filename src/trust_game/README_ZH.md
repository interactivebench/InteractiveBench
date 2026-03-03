# Repeated Prisoner's Dilemma (Trust Game) Benchmark

一个用于测试多个 LLM 在重复囚徒困境（信任游戏）中的策略和推理能力的 Python 多智能体环境。

## 功能特性

- 支持多个 LLM Agent 进行重复囚徒困境游戏
- 提供 baseline agents（Random, Grim Trigger, TFT）
- 支持自定义 payoff 矩阵
- 支持循环 tournament（两两对战）
- 完整的游戏历史记录和统计
- 支持 OpenRouter API 调用 LLM

## 文件结构

- `agents.py`: Agent 定义（Random, Grim Trigger, TFT, LLM）
- `game.py`: 单局游戏逻辑
- `tournament.py`: 循环 tournament 管理
- `main.py`: 主入口和命令行接口
- `test_single_game.sh`: 单局游戏测试脚本
- `test_tournament.sh`: Tournament 测试脚本

## 环境变量配置

使用 OpenRouter API 时，需要设置以下环境变量。有两种方式：

### 方式一：使用 .env 文件（推荐）

在 `trust_game` 目录下创建 `.env` 文件：

```bash
# OpenRouter API Key（必需）
OPENROUTER_API_KEY=your-api-key-here

# 可选：OpenRouter 的额外 headers
OPENROUTER_HTTP_REFERER=https://your-site.com
OPENROUTER_X_TITLE=Trust Game Benchmark
```

### 方式二：使用环境变量

```bash
export OPENROUTER_API_KEY="your-api-key"
# 可选
export OPENROUTER_HTTP_REFERER="your-referer"
export OPENROUTER_X_TITLE="your-title"
```

**注意**：代码会自动加载 `.env` 文件（如果存在），同时也会读取系统环境变量。

## 使用方法

### 1. 单局游戏

```bash
python main.py --mode single \
    --agents "Grim Trigger-1:tft" "Random-1:random:0.6" \
    --rounds-range 3 7
```

### 2. 循环 Tournament（默认）

```bash
# 使用默认 baseline agents
python main.py

# 指定 agents
python main.py \
    --agents "Grim Trigger-1:tft" "Random-1:random:0.5" "Random-2:random:0.7" \
    --rounds-range 3 7 \
    --num-games 3

# 使用 LLM agents
python main.py \
    --agents "GPT-4:llm:gpt-4" "Gemini:llm:google/gemini-pro" "Grim Trigger-1:tft" \
    --rounds-range 3 7 \
    --num-games 2 \
    --output results.json
```

### 3. Agent 格式说明

Agent 格式：`name:type[:param]`

- `random`: 随机策略
  - 格式：`name:random:cooperate_prob`（cooperate_prob 可选，默认 0.5）
  - 示例：`Random-1:random:0.6`
  
- `tft`: TFT baseline
  - 格式：`name:tft`
  - 示例：`TFT-1:tft`
  
- `grim`: Grim Trigger baseline
  - 格式：`name:grim`
  - 示例：`Grim Trigger-1:grim`
  
- `llm`: LLM Agent
  - 格式：`name:llm:model_name`
  - 示例：`GPT-4:llm:gpt-4` 或 `Gemini:llm:google/gemini-pro`

### 4. 快速测试脚本

提供了两个便捷的测试脚本，使用便宜的 LLM 模型进行测试：

#### 单局游戏测试

```bash
./test_single_game.sh
```

该脚本使用 `openai/gpt-3.5-turbo` 与 Grim Trigger baseline 进行单局游戏测试。

#### Tournament 测试

```bash
./test_tournament.sh
```

该脚本使用多个便宜的 LLM 模型（gpt-3.5-turbo, claude-3-haiku, gemini-flash-1.5）与 baseline agents 进行循环 tournament。

**注意**：可以在脚本中修改模型列表，添加或替换其他便宜的模型。

### 5. 输出结果

使用 `--output` 参数可以将结果保存为 JSON 文件：

```bash
python main.py --output results.json
```

## 代码示例

### 在代码中使用

```python
import asyncio
from agents import RandomAgent, GrimTriggerAgent, LLMAgent
from game import Game
from tournament import Tournament

async def example():
    # 创建 agents
    agent1 = GrimTriggerAgent("Grim Trigger")
    agent2 = LLMAgent("GPT-4", "gpt-4")
    
    # 单局游戏
    game = Game(agent1, agent2, rounds_range=(3, 7))
    result = await game.play()
    print(result)
    
    # Tournament
    agents = [
        RandomAgent("Random-1"),
        GrimTriggerAgent("Grim Trigger-1"),
        LLMAgent("GPT-4", "gpt-4")
    ]
    tournament = Tournament(agents, rounds_range=(3, 7), num_games=2)
    result = await tournament.run()
    tournament.print_summary(result)

asyncio.run(example())
```

## Payoff 矩阵

默认 payoff 矩阵：
- 双方合作：2/2
- 一方合作一方背叛：-1/3 或 3/-1
- 双方背叛：0/0

可以通过代码自定义 payoff 矩阵。

## 日志功能

系统会自动记录每次 LLM 交互的详细信息：

### LLM Agent 日志

- **位置**: `logs/` 目录下，文件名格式为 `{agent_name}_{timestamp}.log`
- **内容**:
  - 每轮发送的完整 prompt（包括系统提示和对话历史）
  - LLM 的原始回复
  - 解析后的动作
  - 错误信息（如果有）

### 游戏日志

- **位置**: 控制台输出
- **内容**:
  - 游戏开始/结束信息
  - 每轮的动作和 payoff
  - 最终总分

### 查看日志

```bash
# 查看最新的日志文件
ls -lt logs/ | head

# 实时查看日志（如果游戏正在运行）
tail -f logs/LLM-Test_*.log
```

## 注意事项

- LLM Agent 需要有效的 API key
- 游戏回合数是随机的（在指定范围内），LLM 只知道范围，不知道精确回合数
- 支持 Python 3.10+
- 日志文件会自动保存在 `logs/` 目录，建议将其添加到 `.gitignore`

