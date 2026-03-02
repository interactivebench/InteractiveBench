#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  echo "中断信号收到，终止所有子进程..."
  trap - INT TERM
  kill -- -$$ 2>/dev/null || true
  exit 1
}

trap cleanup INT TERM

DATASET_PATH="data/puzzle_math.json"
DATASET_NAME="hle"
OUT_DIR="results"
MAX_ROUNDS=20
JUDGE_MODEL="x-ai/grok-4.1-fast"

PLAYERS=(
  "qwen/qwen3-max"
  # "moonshotai/kimi-k2-0905"
  "deepseek/deepseek-v3.2"
  "x-ai/grok-4.1-fast"
  # "openai/gpt-5-mini"
  # "google/gemini-3-flash-preview"
)

for player in "${PLAYERS[@]}"; do
  python turtle.py \
    --dataset_path "${DATASET_PATH}" \
    --dataset_name "${DATASET_NAME}" \
    --player_model "${player}" \
    --judge_model "${JUDGE_MODEL}" \
    --out_dir "${OUT_DIR}" \
    --max_rounds "${MAX_ROUNDS}" &
done

wait
