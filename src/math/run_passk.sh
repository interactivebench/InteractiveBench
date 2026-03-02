#!/usr/bin/env bash
set -euo pipefail

# 运行 pass@k（按模型并行，Python 内部不并行）
# 默认：每个模型使用自己的 k（由 passk_eval.py 根据该模型 naive∩turtle 的 token 比例计算）。
# 可用 --k 覆盖为“所有模型共用同一个 k”。
#
# 用法示例：
#   bash run_passk.sh
#   bash run_passk.sh --k 5 --max-n 30
#   bash run_passk.sh --verbose
#
# 依赖：OPENROUTER_API_KEY 已设置；环境里有 openai 包（因为复用了 naive.py 的 client）。

DATASET_NAME="hle"
RESULTS_DIR="results"
JUDGE_MODEL="x-ai/grok-4.1-fast"
OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
TEMPERATURE="0.8"
MAX_ATTEMPTS="3"
MAX_N="-1"
K=""   # optional: override-all k
VERBOSE="0"
SKIP_DRAW="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-name) DATASET_NAME="$2"; shift 2 ;;
    --results-dir) RESULTS_DIR="$2"; shift 2 ;;
    --judge-model) JUDGE_MODEL="$2"; shift 2 ;;
    --openrouter-base-url) OPENROUTER_BASE_URL="$2"; shift 2 ;;
    --temperature) TEMPERATURE="$2"; shift 2 ;;
    --max-attempts) MAX_ATTEMPTS="$2"; shift 2 ;;
    --max-n) MAX_N="$2"; shift 2 ;;
    --k) K="$2"; shift 2 ;;
    --verbose) VERBOSE="1"; shift 1 ;;
    --skip-draw) SKIP_DRAW="1"; shift 1 ;;
    -h|--help)
      sed -n '1,120p' "$0"
      exit 0
      ;;
    *)
      echo "[ERROR] unknown arg: $1"
      exit 1
      ;;
  esac
done

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "[ERROR] OPENROUTER_API_KEY 未设置。"
  exit 1
fi

cleanup() {
  echo "中断信号收到，终止所有子进程..."
  trap - INT TERM
  kill -- -$$ 2>/dev/null || true
  exit 1
}
trap cleanup INT TERM

echo "[INFO] run pass@k (parallel per model)"
if [[ -n "${K}" ]]; then
  echo "[INFO] override: all models use k=${K}"
fi

# 只跑同时存在 naive 与 turtle 的模型（保证题目交集对齐）
MODELS=($(python3 - <<PY
import re
from pathlib import Path
root=Path("${RESULTS_DIR}")
ds="${DATASET_NAME}"
naive=list(root.glob(f"{ds}__openrouter__*__judge=*.json"))
turtle=set(p.stem for p in root.glob(f"{ds}__turtle__openrouter__*__judge=*.json"))
def mid(stem):
    m=re.search(r"__openrouter__([^_].*?)__judge=", stem)
    if not m: return None
    tok=m.group(1)
    return tok.replace("_","/",1) if "_" in tok else tok
out=[]
for p in naive:
    m=mid(p.stem)
    if not m: 
        continue
    if any(s.startswith(f"{ds}__turtle__openrouter__{m.replace('/','_',1)}__judge=") for s in turtle):
        out.append(m)
print(" ".join(sorted(set(out))))
PY
))

if [[ "${#MODELS[@]}" -eq 0 ]]; then
  echo "[WARN] no common models found (naive ∩ turtle)."
  exit 0
fi

for player in "${MODELS[@]}"; do
  python3 passk_eval.py \
    --results_dir "${RESULTS_DIR}" \
    --dataset_name "${DATASET_NAME}" \
    --judge_model "${JUDGE_MODEL}" \
    --openrouter_base_url "${OPENROUTER_BASE_URL}" \
    --temperature "${TEMPERATURE}" \
    --max_attempts "${MAX_ATTEMPTS}" \
    --max_n "${MAX_N}" \
    --player_model "${player}" \
    $( [[ -n "${K}" ]] && echo "--k_override ${K}" ) \
    $( [[ "${VERBOSE}" == "1" ]] && echo "--verbose_calls --verbose_progress" ) \
    >/dev/stdout 2>/dev/stderr &
done

wait

if [[ "${SKIP_DRAW}" == "1" ]]; then
  echo "[INFO] done (skip draw)."
  exit 0
fi

python3 draw_passk.py
echo "[INFO] done. check figs/passk_model_accuracy_set2.pdf and figs/passk_model_avg_attempts_set2.pdf"

