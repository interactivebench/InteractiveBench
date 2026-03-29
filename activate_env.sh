#!/bin/bash
# 激活InteractiveBench conda环境

source ~/miniconda3/etc/profile.d/conda.sh
conda activate interactivebench

echo "✓ 已激活 interactivebench 环境"
echo "当前Python版本: $(python --version)"
echo ""
echo "使用方法："
echo "  python run_benchmark.py --list-models"
echo "  python run_benchmark.py --models gpt-4o"
echo ""
echo "退出环境: conda deactivate"
