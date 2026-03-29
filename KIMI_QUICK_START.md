# 🚀 Kimi 2.5 快速测试指南

## ✅ 已完成的配置

- ✅ API Key 已配置到 `.env` 文件
- ✅ API URL 已更新为 `https://api.moonshot.ai/v1`
- ✅ 框架已支持 Kimi 模型
- ✅ `.env` 文件已添加到 `.gitignore`（不会被提交到 git）

## 🎯 立即开始测试

### 方法 1: 使用测试脚本（最简单）

```bash
# 1. 激活环境
source activate_env.sh

# 2. 运行测试脚本
./test_kimi.sh
```

### 方法 2: 直接使用框架

```bash
# 1. 激活环境
source activate_env.sh

# 2. 测试 Kimi 2.5（一条命令搞定）
python run_benchmark.py --models kimi-2.5

# 3. 查看结果
cat results/benchmark_report.md
```

## 📊 查看可用模型

```bash
python run_benchmark.py --list-models
```

输出包含：
```
kimi-2.5                  moonshot/kimi-2.5
```

## ⚙️ .env 文件说明

`.env` 文件位于项目根目录，包含以下配置：

```bash
MOONSHOT_API_KEY=sk-1OGPdmjAajyHhEBK31XziYd7xdY1VCdOxXr24e2tf60cOrEB
MOONSHOT_BASE_URL=https://api.moonshot.ai/v1
CUSTOM_API_KEY=sk-1OGPdmjAajyHhEBK31XziYd7xdY1VCdOxXr24e2tf60cOrEB
CUSTOM_BASE_URL=https://api.moonshot.ai/v1
```

### 修改 API Key

如果需要更换 API Key，直接编辑 `.env` 文件：

```bash
# 编辑 .env 文件
nano .env

# 或者使用任何文本编辑器修改
```

## 🎮 测试单个模块

### Math 模块

```bash
python src/math/naive.py \
  --dataset_path src/math/data/puzzle_math.json \
  --dataset_name hle \
  --player_model moonshot/kimi-2.5 \
  --judge_model x-ai/grok-4.1-fast \
  --provider custom \
  --custom_base_url https://api.moonshot.ai/v1
```

### Situation Puzzle 模块

```bash
python src/situation_puzzle/benchmark.py \
  --puzzles_path src/situation_puzzle/data/puzzles_en.json \
  --player_model moonshot/kimi-2.5 \
  --judge_model x-ai/grok-4.1-fast \
  --provider custom \
  --custom_base_url https://api.moonshot.ai/v1 \
  --out_dir results
```

### Trust Game 模块

```bash
python src/trust_game/main.py \
  --mode tournament \
  --agents "Kimi:llm:moonshot/kimi-2.5" "GrimTrigger:grim" "TFT:tft" \
  --repeats 5 \
  --output results/trust_game_kimi.json
```

## 📈 测试报告

测试完成后会生成以下文件：

- `results/benchmark_report.md` - Markdown 格式报告
- `results/benchmark_report.json` - JSON 格式数据
- `.benchmark_state.json` - 测试状态（用于断点续跑）

## 🔄 断点续跑

如果测试中断，再次运行相同命令会自动跳过已完成的测试：

```bash
python run_benchmark.py --models kimi-2.5
```

## 🧹 清理测试结果

```bash
# 删除所有结果
rm -rf results/

# 重置测试状态
rm .benchmark_state.json

# 重新开始测试
python run_benchmark.py --models kimi-2.5
```

## 🆚 对比测试

同时测试多个模型：

```bash
# 设置 OpenRouter API Key（如果要测试 OpenRouter 模型）
export OPENROUTER_API_KEY="your-openrouter-key"

# 同时测试 Kimi、GPT-4o、Claude
python run_benchmark.py --models kimi-2.5 gpt-4o claude-3.5-sonnet
```

## 📝 完整测试流程示例

```bash
# Step 1: 激活环境
source activate_env.sh

# Step 2: 查看可用模型
python run_benchmark.py --list-models

# Step 3: 运行测试
python run_benchmark.py --models kimi-2.5

# Step 4: 等待测试完成...

# Step 5: 查看结果
cat results/benchmark_report.md

# Step 6: 退出环境
conda deactivate
```

## ⚠️ 常见问题

### 问题：API Key 错误

**错误信息**：`Authentication failed`

**解决方案**：
1. 检查 `.env` 文件是否存在
2. 确认 API Key 是否正确
3. 运行 `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('MOONSHOT_API_KEY'))"` 检查

### 问题：网络连接失败

**错误信息**：`Connection error` 或 `Timeout`

**解决方案**：
1. 检查网络连接
2. 确认 API 地址可访问：`https://api.moonshot.ai/v1`
3. 检查防火墙设置

### 问题：模块找不到

**错误信息**：`ModuleNotFoundError`

**解决方案**：
```bash
# 确保已激活 conda 环境
conda activate interactivebench

# 或者使用完整路径
~/miniconda3/bin/conda run -n interactivebench python run_benchmark.py --models kimi-2.5
```

## 📚 更多文档

- `KIMI_TEST_GUIDE.md` - 详细测试指南
- `FRAMEWORK_GUIDE.md` - 框架使用说明
- `README.md` - 项目总览

## 🎉 现在开始测试吧！

```bash
source activate_env.sh
python run_benchmark.py --models kimi-2.5
```
