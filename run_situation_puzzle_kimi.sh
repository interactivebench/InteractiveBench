#!/bin/bash

# Kimi-k2.5 Situation Puzzle 测试脚本

CONDA_ENV="interactivebench"
PUZZLES_FILE="src/situation_puzzle/data/puzzles_en.json"
OUTPUT_FILE="results/situation_puzzle_kimi_full.json"
MAX_ROUNDS=20

# 检查是否添加 --resume 参数
RESUME_ARG=""
if [ "$1" == "--resume" ] || [ "$1" == "-r" ]; then
    RESUME_ARG="--resume"
    echo "📥 使用续跑模式"
else
    echo "🚀 开始新测试"
fi

echo "📝 题目文件: $PUZZLES_FILE"
echo "📊 输出文件: $OUTPUT_FILE"
echo "🔄 最大轮数: $MAX_ROUNDS"
echo ""

~/miniconda3/bin/conda run -n $CONDA_ENV python src/situation_puzzle/benchmark.py \
    --puzzles "$PUZZLES_FILE" \
    --player_model kimi-k2.5 \
    --judge_model kimi-k2.5 \
    --provider custom \
    --custom_base_url https://api.moonshot.ai/v1 \
    --custom_api_key sk-1OGPdmjAajyHhEBK31XziYd7xdY1VCdOxXr24e2tf60cOrEB \
    --max_rounds $MAX_ROUNDS \
    $RESUME_ARG \
    --out "$OUTPUT_FILE"
