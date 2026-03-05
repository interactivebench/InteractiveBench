#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  echo "中断信号收到，终止所有子进程..."
  trap - INT TERM
  kill -- -$$ 2>/dev/null || true
  exit 1
}

trap cleanup INT TERM

# load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

: "${OPENROUTER_API_KEY:?Please export OPENROUTER_API_KEY before running.}"
: "${OPENROUTER_BASE_URL:=https://openrouter.ai/api/v1}"

OUT_DIR="${1:-results}"
PUZZLES="${PUZZLES:-data/puzzles_en.json}"
MAX_ROUNDS="${MAX_ROUNDS:-20}"
PLAYER_TEMPERATURE="${PLAYER_TEMPERATURE:-0.0}"

JUDGE_MODEL="${JUDGE_MODEL:-x-ai/grok-4.1-fast}"

PLAYERS=(
  "qwen/qwen3-max"
  "moonshotai/kimi-k2-0905"
  "deepseek/deepseek-v3.2"
  "x-ai/grok-4.1-fast"
  "openai/gpt-5-mini"
  "google/gemini-3-flash-preview"
)

mkdir -p "$OUT_DIR"

sanitize() {
  echo "$1" | sed 's#[/: ]#_#g'
}

echo "[run_benchmark] OPENROUTER_BASE_URL=$OPENROUTER_BASE_URL"
echo "[run_benchmark] OUT_DIR=$OUT_DIR  MAX_ROUNDS=$MAX_ROUNDS  PLAYER_TEMPERATURE=$PLAYER_TEMPERATURE"
echo "[run_benchmark] JUDGE_MODEL=$JUDGE_MODEL"
echo "[run_benchmark] PUZZLES=$PUZZLES"

for player in "${PLAYERS[@]}"; do
  pfile="$(sanitize "$player")__$(sanitize "$JUDGE_MODEL").json"
  out_path="$OUT_DIR/$pfile"

  echo ""
  echo "[run_benchmark] player=$player  -> $out_path"

  python benchmark.py \
    --puzzles "$PUZZLES" \
    --out "$out_path" \
    --resume \
    --max_rounds "$MAX_ROUNDS" \
    --player_temperature "$PLAYER_TEMPERATURE" \
    --player_model "$player" \
    --judge_model "$JUDGE_MODEL" &
done
wait

echo ""
echo "[run_benchmark] Done. Outputs in: $OUT_DIR"
