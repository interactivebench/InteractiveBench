# InteractiveBench 统一测试框架使用指南

## 环境配置

### 激活环境

```bash
# 方式1: 使用激活脚本（推荐）
source activate_env.sh

# 方式2: 手动激活
source ~/miniconda3/etc/profile.d/conda.sh
conda activate interactivebench
```

### 退出环境

```bash
conda deactivate
```

## 快速开始

### 1. 查看可用模型

```bash
python run_benchmark.py --list-models
```

### 2. 测试单个模型

```bash
# 使用别名
python run_benchmark.py --models gpt-4o

# 使用完整模型ID
python run_benchmark.py --models openai/gpt-4o
```

### 3. 测试多个模型

```bash
python run_benchmark.py --models gpt-4o claude-3.5-sonnet gemini-pro
```

### 4. 只运行特定模块

```bash
python run_benchmark.py --models gpt-4o --modules math situation_puzzle
```

### 5. 不使用断点续跑（重新运行所有测试）

```bash
python run_benchmark.py --models gpt-4o --no-resume
```

## 配置新模型

### 方法1: 修改配置文件

编辑 `benchmark_framework/config/default_config.yaml`:

```yaml
models:
  gpt-5: openai/gpt-5-preview  # 添加新模型
```

### 方法2: 使用完整模型ID

```bash
# 无需修改配置，直接使用完整ID
python run_benchmark.py --models openai/gpt-5-preview
```

## 查看结果

测试完成后，结果将保存在 `results/` 目录：

```bash
# JSON格式报告
cat results/benchmark_report.json

# Markdown格式报告
cat results/benchmark_report.md
```

## 命令行选项

```
选项:
  --models, -m        要测试的模型列表（必需）
  --modules, -M       要运行的模块（math, situation_puzzle, trust_game）
  --config, -c        自定义配置文件路径
  --no-resume         不使用断点续跑
  --output-dir, -o    输出目录（默认: results）
  --list-models       列出所有可用模型
  --verbose, -v       启用详细日志
  --quiet, -q         静默模式
```

## 环境变量

确保设置了以下环境变量：

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
```

## 目录结构

```
InteractiveBench/
├── benchmark_framework/    # 框架代码
├── results/                # 测试结果
├── activate_env.sh         # 环境激活脚本
└── run_benchmark.py        # 主入口脚本
```

## 故障排除

### 问题: ModuleNotFoundError

**解决方案**: 确保已激活 interactivebench 环境
```bash
conda activate interactivebench
```

### 问题: conda: command not found

**解决方案**: 使用完整路径
```bash
~/miniconda3/bin/conda activate interactivebench
```

### 问题: API密钥错误

**解决方案**: 检查环境变量是否正确设置
```bash
echo $OPENROUTER_API_KEY
```

## 示例工作流

```bash
# 1. 激活环境
source activate_env.sh

# 2. 设置API密钥（如果还没设置）
export OPENROUTER_API_KEY="your-api-key"

# 3. 测试一个新模型
python run_benchmark.py --models claude-3.5-sonnet

# 4. 查看结果
cat results/benchmark_report.md

# 5. 退出环境
conda deactivate
```
