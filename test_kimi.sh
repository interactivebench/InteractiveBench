#!/bin/bash
# Kimi 2.5 模型快速测试脚本

echo "=================================================="
echo "Kimi 2.5 模型测试 - InteractiveBench"
echo "=================================================="
echo ""

# 1. 检查环境
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "⚠️  请先激活 conda 环境："
    echo "   source activate_env.sh"
    echo ""
    exit 1
fi

echo "✓ 当前环境: $CONDA_DEFAULT_ENV"
echo ""

# 2. 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在"
    echo "   请确保 .env 文件包含 MOONSHOT_API_KEY"
    echo ""
    exit 1
fi

# 从 .env 加载环境变量（使用 python-dotenv）
echo "✓ API 配置已从 .env 文件加载"
echo ""

# 3. 显示测试信息
echo "将要测试的模型: Kimi 2.5 (moonshot/kimi-2.5)"
echo "测试模块: Math, Situation Puzzle, Trust Game"
echo ""

# 4. 询问是否继续
read -p "是否开始测试？(y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "测试已取消"
    exit 0
fi

echo ""
echo "开始测试..."
echo "=================================================="
echo ""

# 5. 运行测试
python run_benchmark.py --models kimi-2.5

# 6. 显示结果
if [ $? -eq 0 ]; then
    echo ""
    echo "=================================================="
    echo "✓ 测试完成！"
    echo "=================================================="
    echo ""
    echo "查看结果："
    echo "  Markdown 报告: cat results/benchmark_report.md"
    echo "  JSON 报告:   cat results/benchmark_report.json"
    echo ""
else
    echo ""
    echo "=================================================="
    echo "✗ 测试失败"
    echo "=================================================="
    echo ""
    echo "请检查错误信息并重试"
    echo ""
fi
