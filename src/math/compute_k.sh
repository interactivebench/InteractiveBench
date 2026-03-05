#!/usr/bin/env bash
set -euo pipefail

# 只计算 k（不跑 pass@k，不需要 OPENROUTER_API_KEY）

DATASET_NAME="${1:-hle}"
RESULTS_DIR="${2:-results}"
JUDGE_MODEL="${3:-x-ai/grok-4.1-fast}"

python3 passk_eval.py \
  --results_dir "${RESULTS_DIR}" \
  --dataset_name "${DATASET_NAME}" \
  --judge_model "${JUDGE_MODEL}" \
  --compute_k_only

