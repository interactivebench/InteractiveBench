#!/bin/bash
# Tournament 测试脚本 - 使用多个便宜的 LLM 进行测试

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

# 定义便宜的 LLM 模型列表
# 这些模型在 OpenRouter 上通常比较便宜
MODELS=(
    "x-ai/grok-4.1-fast"
    "google/gemini-3-flash-preview"
    "openai/gpt-5-mini"
    "moonshotai/kimi-k2-0905"
    "deepseek/deepseek-v3.2"
    "qwen/qwen3-max"
    # "minimax/minimax-m2.1"
)

# 构建 agent 列表
AGENTS=()
for MODEL in "${MODELS[@]}"; do
    MODEL_NAME=$(echo "$MODEL" | sed 's/\//-/g' | sed 's/\./-/g')
    AGENTS+=("LLM-${MODEL_NAME}:llm:${MODEL}")
done

# 添加 baseline agents
AGENTS+=("Grim Trigger-1:grim")
AGENTS+=("Random-1:random:0.5")
AGENTS+=("TFT-1:tft")

echo "=========================================="
echo "Tournament 测试 - 使用多个 LLM"
echo "=========================================="
echo "LLM 模型数量: ${#MODELS[@]}"
echo "Baseline agents: 3 (Grim Trigger, Random, TFT)"
echo "总 agents 数量: ${#AGENTS[@]}"
echo ""
echo "模型列表:"
for MODEL in "${MODELS[@]}"; do
    echo "  - $MODEL"
done
echo "=========================================="
echo ""

# 运行 tournament
python main.py \
    --mode tournament \
    --agents "${AGENTS[@]}" \
    --delta 0.80 \
    --max-rounds 35 \
    --repeats 5 \
    --seed 1234 \
    --output "result/test_tournament_result.json" \
    --pair-concurrency 4

echo ""
echo "✅ 测试完成！结果已保存到 test_tournament_result.json"

