# Math Interactive Benchmark (naive / Interactive Q&A / pass@k)

This directory provides an interactive benchmark pipeline for mathematical problem solving, designed to compare three evaluation paradigms:

- **naive**: The model directly solves the problem, and the judge performs a binary (0/1) answer-equivalence check (`naive.py`).
- **Interactive Q&A**: The model can engage in multiple rounds of **Yes/No/Both/Irrelevant** questioning with a “judger” to reduce uncertainty before submitting a final answer, which is then checked for equivalence (`turtle.py`, filename retained for historical reasons).
- **pass@k**: The same model is sampled multiple times on the same problem set. Based on the token usage ratio between naive and interactive methods, an appropriate \(k\) is estimated per model (`passk_eval.py`).

The default backend is **OpenRouter (OpenAI-compatible API)**.

---

## Directory Structure

```text
src/math/
  README.md
  data/
    puzzle_math.json
  naive.py
  turtle.py
  passk_eval.py
  naive.sh
  turtle.sh
  compute_k.sh
  run_passk.sh
```

---

## File Descriptions

- **`data/puzzle_math.json`**: Example/default dataset (hard set), each entry contains `problem / solution / exp_ans`
- **`naive.py`**: Direct solving + judge equivalence checking
- **`turtle.py`**: Interactive Q&A solving (multi-round) + judge equivalence checking (supports resume)
- **`passk_eval.py`**: Computes \(k\) (based on token estimates from naive ∩ interactive outputs) and runs pass@k
- **`naive.sh` / `turtle.sh`**: Example batch evaluation scripts
- **`compute_k.sh` / `run_passk.sh`**: Convenience scripts for pass@k (parallelized over models)

---

## Environment Variables

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"   # Optional
```

---

## Dataset Format Specification

The input dataset JSON for `naive.py` / `turtle.py` must be a **list[dict]**. Each entry is recommended to include:

- **`problem`**: Problem statement (string)
- **`solution`**: Reference solution / explanation (string; optional but recommended for judger use)
- **`exp_ans`** or **`final_answer`**: Ground-truth answer (string; the code prioritizes `final_answer`, otherwise falls back to `exp_ans`)

Example (consistent with `data/puzzle_math.json`):

```json
[
  {
    "problem": "...",
    "solution": "...",
    "exp_ans": "B"
  }
]
```

---

## Output Filename Convention (Auto-generated)

To facilitate large-scale experiment alignment, output filenames automatically encode dataset name, provider, player, and judge:

- **naive (`naive.py`)**
  - `results/<dataset>__openrouter__<player>__judge=<judge>.json`
- **Interactive Q&A (`turtle.py`)**
  - `results/<dataset>__turtle__openrouter__<player>__judge=<judge>.json`
- **pass@k (`passk_eval.py`)**
  - `results/<dataset>__passk__openrouter__<player>__judge=<judge>.json`

In filenames, `/` in `<player>` or `<judge>` is replaced with `_` for compatibility.

---

## Minimal Runnable Workflow (Recommended Order)

Using `data/puzzle_math.json` with `dataset_name=hle` as an example:

### 1) Run naive (direct solving)

```bash
python naive.py \
  --dataset_path data/puzzle_math.json \
  --dataset_name hle \
  --player_model "openai/gpt-5-mini" \
  --judge_model "x-ai/grok-4.1-fast" \
  --max_tokens 5000
```

---

### 2) Run Interactive Q&A (multi-round)

```bash
python turtle.py \
  --dataset_path data/puzzle_math.json \
  --dataset_name hle \
  --player_model "openai/gpt-5-mini" \
  --judge_model "x-ai/grok-4.1-fast" \
  --out_dir results \
  --max_rounds 20
```

Or batch-run in parallel according to the `PLAYERS` list in `turtle.sh`:

```bash
bash turtle.sh
```

---

### 3) Compute \(k\) Only (without running pass@k)

```bash
bash compute_k.sh hle results "x-ai/grok-4.1-fast"
```

This will generate `hle__passk_k_stats.json` under `results/`.

---

### 4) Run pass@k (Optional)

`run_passk.sh` automatically filters models that already have results from both naive and interactive methods, ensuring proper problem-set intersection alignment:

```bash
bash run_passk.sh --max-n 50
```

---

## Resume Behavior

- `naive.py`: If the output file exists, it loads the previous JSON and skips problems that have already been processed with valid records.
- `turtle.py`: If the output file exists, it skips problems that already contain `turtle_history`. The file is overwritten after each completed problem to support safe interruption and recovery.

---

## Cost and Notes

- Interactive Q&A significantly increases API calls; `--max_rounds` is the primary cost-control parameter.
- `turtle.sh` and `run_passk.sh` launch multiple Python processes in parallel. Be mindful of provider rate limits and associated costs.