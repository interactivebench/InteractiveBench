# models=("qwen/qwen3-max" "moonshotai/kimi-k2-0905" "deepseek/deepseek-v3.2" "openai/gpt-5-mini")
models=("openai/gpt-5-mini")
for model in "${models[@]}"; do
    python naive.py \
    --dataset_path data/puzzle_math.json \
    --dataset_name hle \
    --player_model $model \
    --judge_model x-ai/grok-4.1-fast \
    --wrong_limit 52 \
    --max_tokens 5000
done