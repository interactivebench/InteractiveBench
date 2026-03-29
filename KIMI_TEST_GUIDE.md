# Kimi 2.5 模型测试指南

本指南说明如何在 InteractiveBench 框架中测试 Moonshot Kimi 2.5 模型。

## 环境准备

### 1. 激活 conda 环境

```bash
source activate_env.sh
```

### 2. API 密钥配置

API 密钥已经配置在 `.env` 文件中，无需手动设置！

如果需要更换 API Key，编辑项目根目录的 `.env` 文件：

```bash
# .env 文件内容
MOONSHOT_API_KEY=your-new-api-key
MOONSHOT_BASE_URL=https://api.moonshot.ai/v1
```

**获取 API 密钥**：
- 访问 [Moonshot 开放平台](https://platform.moonshot.cn/)
- 注册账号并创建 API Key
- 将 API Key 设置为环境变量

## 快速测试

### 测试单个模块

```bash
# Math 模块
python src/math/naive.py \
  --dataset_path src/math/data/puzzle_math.json \
  --dataset_name hle \
  --player_model moonshot/kimi-2.5 \
  --judge_model x-ai/grok-4.1-fast \
  --provider custom \
  --custom_base_url https://api.moonshot.cn/v1

# Situation Puzzle 模块
python src/situation_puzzle/benchmark.py \
  --puzzles_path src/situation_puzzle/data/puzzles_en.json \
  --player_model moonshot/kimi-2.5 \
  --judge_model x-ai/grok-4.1-fast \
  --provider custom \
  --custom_base_url https://api.moonshot.cn/v1 \
  --out_dir results

# Trust Game 模块
python src/trust_game/main.py \
  --mode tournament \
  --agents "KimiLLM:llm:moonshot/kimi-2.5" "GrimTrigger:grim" "TFT:tft" \
  --repeats 5 \
  --output results/trust_game_kimi.json
```

**注意**：Trust Game 模块会从环境变量读取 API Key，所以需要确保设置了 `MOONSHOT_API_KEY`。

### 使用统一框架测试所有模块

```bash
# 使用框架测试 kimi-2.5（推荐）
python run_benchmark.py --models kimi-2.5
```

框架会自动：
- 识别 Kimi 模型需要使用 custom provider
- 设置正确的 base_url
- 在所有三个模块上运行测试
- 生成统一的性能报告

## 查看结果

```bash
# 查看 Markdown 报告
cat results/benchmark_report.md

# 查看 JSON 报告
cat results/benchmark_report.json
```

## 命令行参数说明

### Math 模块

```bash
python src/math/naive.py \
  --dataset_path <数据集路径> \
  --dataset_name <数据集名称> \
  --player_model moonshot/kimi-2.5 \
  --judge_model <裁判模型> \
  --provider custom \                    # 使用自定义 provider
  --custom_base_url https://api.moonshot.cn/v1  # Moonshot API 地址
```

### Situation Puzzle 模块

```bash
python src/situation_puzzle/benchmark.py \
  --puzzles_path <谜题路径> \
  --player_model moonshot/kimi-2.5 \
  --judge_model <裁判模型> \
  --provider custom \
  --custom_base_url https://api.moonshot.cn/v1 \
  --out_dir <输出目录>
```

### Trust Game 模块

```bash
# Trust Game 模块从环境变量读取 API 配置
export MOONSHOT_API_KEY="your-api-key"
export CUSTOM_API_KEY="your-api-key"
export CUSTOM_BASE_URL="https://api.moonshot.cn/v1"

python src/trust_game/main.py \
  --mode tournament \
  --agents "Kimi:llm:moonshot/kimi-2.5" "GrimTrigger:grim" "TFT:tft" \
  --repeats 5 \
  --output <输出文件>
```

## 框架配置

### 添加新的 Kimi 模型变体

编辑 `benchmark_framework/config/default_config.yaml`：

```yaml
models:
  kimi-2.5: moonshot/kimi-2.5
  kimi-2.5-pro: moonshot/kimi-2.5-pro  # 如果有新版本
```

### 修改模块默认配置

```yaml
modules:
  math:
    judge_model: "x-ai/grok-4.1-fast"
    max_tokens: 5000

  situation_puzzle:
    judge_model: "x-ai/grok-4.1-fast"
    max_rounds: 20

  trust_game:
    delta: 0.9
    num_games: 5
```

## API 调用方式

### Moonshot API 调用示例

```python
from openai import OpenAI

client = OpenAI(
    api_key="MOONSHOT_API_KEY",  # 你的 Moonshot API Key
    base_url="https://api.moonshot.cn/v1",
)

response = client.chat.completions.create(
    model="moonshot-v1-8k",  # 或 moonshot-v1-32k, moonshot-v1-128k
    messages=[
        {"role": "user", "content": "你好"}
    ],
    temperature=0.3,
)

print(response.choices[0].message.content)
```

### 模型名称映射

| 别名 | 完整模型ID | 说明 |
|------|-----------|------|
| kimi-2.5 | moonshot/kimi-2.5 | Kimi 2.5 主模型 |
| kimi-2.5-pro | moonshot/kimi-2.5-pro | Kimi 2.5 Pro（如有） |

## 故障排除

### 问题 1: API Key 错误

**错误信息**：`CUSTOM_API_KEY is missing for custom provider`

**解决方案**：
```bash
export MOONSHOT_API_KEY="your-actual-api-key"
```

### 问题 2: 模型名称错误

**错误信息**：`Model not found`

**解决方案**：确保使用正确的模型名称 `moonshot/kimi-2.5`

### 问题 3: 网络连接问题

**错误信息**：`Connection error` 或 `Timeout`

**解决方案**：
1. 检查网络连接
2. 确认 API 地址可访问：`https://api.moonshot.cn/v1`
3. 检查防火墙设置

## 完整测试流程

```bash
# 1. 激活环境
source activate_env.sh

# 2. 设置 API 密钥
export MOONSHOT_API_KEY="sk-your-key"

# 3. 运行测试
python run_benchmark.py --models kimi-2.5

# 4. 查看结果
cat results/benchmark_report.md

# 5. 退出环境
conda deactivate
```

## 临时文件和日志

测试过程中会生成以下文件：

- `results/` - 测试结果目录
- `.benchmark_state.json` - 框架状态文件（用于断点续跑）
- `logs/` - Trust Game 模块的详细日志

清理测试结果：

```bash
# 删除结果
rm -rf results/

# 重置框架状态
rm .benchmark_state.json
```

## 与 OpenRouter 模型对比

你可以同时测试 Kimi 和 OpenRouter 模型：

```bash
# 设置 OpenRouter API Key
export OPENROUTER_API_KEY="sk-openrouter-key"

# 同时测试多个模型
python run_benchmark.py --models kimi-2.5 gpt-4o claude-3.5-sonnet
```

报告会自动生成对比表格。

## 技术细节

### Provider 类型

框架支持两种 provider 类型：

1. **openrouter** - OpenRouter 聚合服务
   - API Key: `OPENROUTER_API_KEY`
   - Base URL: `https://openrouter.ai/api/v1`

2. **custom** - 自定义 OpenAI 兼容 API
   - API Key: `CUSTOM_API_KEY` 或 `MOONSHOT_API_KEY`
   - Base URL: `https://api.moonshot.cn/v1`

### 自动识别机制

框架通过模型名称自动识别 provider：

- 包含 `moonshot/` 或 `kimi` → custom provider
- 其他 → openrouter provider

### 环境变量优先级

1. 命令行参数（最高优先级）
2. 环境变量
3. 配置文件默认值（最低优先级）

## 下一步

测试完成后，你可以：

1. 分析性能指标
2. 与其他模型对比
3. 调整测试参数
4. 添加更多 Kimi 模型变体

如有问题，请参考主文档或提交 issue。
