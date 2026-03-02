#!/bin/bash
# 单局游戏测试脚本 - 使用便宜的 LLM 进行测试

# 设置脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 加载 .env 文件（如果存在）
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

# 检查 API key
if [ -z "$OPENROUTER_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  警告: 未设置 OPENROUTER_API_KEY 或 OPENAI_API_KEY 环境变量"
    echo "   将使用模拟响应（仅用于测试）"
    echo ""
fi


EVAL_MODELS=(
    "google/gemini-2.5-flash"
    "openai/gpt-4.1"
    "x-ai/grok-4.1-fast"
    "anthropic/claude-haiku-4.5"
    "qwen/qwen3-max"
    "deepseek/deepseek-v3.2-exp"
    "moonshotai/kimi-k2-thinking"
)

echo "=========================================="
echo "单局游戏测试 - 每个模型 vs TitForTat"
echo "=========================================="
echo "模型数量: ${#EVAL_MODELS[@]}"
echo ""

for EVAL_MODEL in "${EVAL_MODELS[@]}"; do
    EVAL_MODEL_NAME=$(echo "$EVAL_MODEL" | sed 's/\//-/g' | sed 's/\./-/g')
    
    echo "----------------------------------------"
    echo "测试模型: $EVAL_MODEL"
    echo "----------------------------------------"
    
    # 运行单局游戏：每个模型 vs TitForTat
    python main.py \
        --mode single \
        --agents "LLM-${EVAL_MODEL_NAME}:llm:${EVAL_MODEL}" "TitForTat-1:tft" \
        --delta 0.90 \
        --max-rounds 200 \
        --seed 1234 \
        --output "result/test_single_game_result_${EVAL_MODEL_NAME}.json"
    
    echo ""
done


echo "=========================================="
echo "✅ 所有测试完成！"
echo "结果已保存到 result/ 目录下"
echo "=========================================="

