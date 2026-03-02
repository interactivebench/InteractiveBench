# Math Interactive Benchmark (naive / Situation-Puzzle-style Q&A / pass@k)

This directory contains an interactive benchmarking pipeline for math problems, comparing:

- **naive**: the model solves directly; the judge only performs 0/1 equivalence checking (`naive.py`)
- **Situation-Puzzle-style Q&A**: the model can ask a *judger* multiple rounds of constrained Q&A (**Yes/No/Both/Irrelevant**) to reduce uncertainty, then submits a final answer for equivalence grading (`turtle.py`, legacy filename)
- **pass@k**: re-evaluates models with multiple attempts per problem, and estimates a suitable \(k\) per model based on output-token ratios between naive and Q&A methods (`passk_eval.py`)

Default provider: **OpenRouter (OpenAI-compatible)**.

## Layout

```text
src/math/
  README.md
  README_EN.md
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

## Files

- **`data/puzzle_math.json`**: example/default hard set dataset; each item keeps only `problem/solution/exp_ans`
- **`naive.py`**: direct solving + equivalence judge (supports resume and `wrong_limit`)
- **`turtle.py`**: Situation-Puzzle-style multi-turn Q&A solving + equivalence judge (supports resume)
- **`passk_eval.py`**: compute \(k\) (from token ratio on naive∩Q&A overlap) and run pass@k
- **`naive.sh` / `turtle.sh`**: example batch scripts
- **`compute_k.sh` / `run_passk.sh`**: pass@k convenience scripts (parallel per model)

> Naming note: output filenames and fields still include legacy `turtle` tokens (e.g., `turtle.py`, `__turtle__`, `turtle_history`). Semantically, this method is described as **Situation Puzzle / lateral-thinking style constrained Q&A**.

## Environment variables

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"   # optional
```

`naive.py` and `turtle.py` also accept `--openrouter_base_url` (default `https://openrouter.ai/api/v1`).

## Install dependencies

Minimum:

```bash
pip install openai python-dotenv tqdm
```

Optional (for some stats/plots if you add them):

```bash
pip install pandas matplotlib
```

## Dataset format

Inputs to `naive.py` / `turtle.py` must be a JSON **list of objects**. Each item should contain:

- **`problem`**: the question text (string)
- **`solution`**: reference solution/notes (string; can be empty but recommended since the judger may use it)
- **`exp_ans`** or **`final_answer`**: expected final answer (string; code prefers `final_answer`, falls back to `exp_ans`)

Example (matches `data/puzzle_math.json`):

```json
[
  {
    "problem": "...",
    "solution": "...",
    "exp_ans": "B"
  }
]
```

## Output naming convention

Outputs encode dataset name, provider, player, and judge:

- **naive (`naive.py`)**
  - `results/<dataset>__openrouter__<player>__judge=<judge>.json`
- **Q&A method (`turtle.py`, legacy naming)**
  - `results/<dataset>__turtle__openrouter__<player>__judge=<judge>.json`
- **pass@k (`passk_eval.py`)**
  - `results/<dataset>__passk__openrouter__<player>__judge=<judge>.json`

`/` is replaced by `_` in model ids for filenames.

## Minimal runnable workflow (recommended)

Example uses `data/puzzle_math.json` and `dataset_name=hle`.

### 1) Run naive

```bash
python naive.py \
  --dataset_path data/puzzle_math.json \
  --dataset_name hle \
  --player_model "openai/gpt-5-mini" \
  --judge_model "x-ai/grok-4.1-fast" \
  --max_tokens 5000
```

Useful options:

- `--wrong_limit N`: early stop after collecting N “attempted-but-wrong” items (cost control / hard set construction)
- `--max_n N`: only run the first N items

### 2) Run Situation-Puzzle-style Q&A

```bash
python turtle.py \
  --dataset_path data/puzzle_math.json \
  --dataset_name hle \
  --player_model "openai/gpt-5-mini" \
  --judge_model "x-ai/grok-4.1-fast" \
  --out_dir results \
  --max_rounds 20
```

Or batch-run players in parallel (see `turtle.sh`):

```bash
bash turtle.sh
```

### 3) Compute \(k\) only (no pass@k yet)

```bash
bash compute_k.sh hle results "x-ai/grok-4.1-fast"
```

This writes `results/hle__passk_k_stats.json`.

### 4) Run pass@k (optional)

`run_passk.sh` automatically selects models that have both naive and Q&A results (so the overlap is aligned):

```bash
bash run_passk.sh --max-n 50
```

Common args:

- `--k 5`: force a single shared \(k\) for all models
- `--verbose`: print more call/progress logs
- `--skip-draw`: skip the final drawing step (the repo may not include a draw script in all versions)

## Resume behavior

- `naive.py`: if the output file exists, it loads and skips already-processed problems (based on “valid record”); `wrong_limit` also counts existing “attempted-but-wrong” records.
- `turtle.py`: if the output file exists, it skips problems that already have `turtle_history`, and rewrites the output after each item for safe resuming.

## Cost notes

- Equivalence judging is itself a model call; **judge choice can significantly affect results**.
- Q&A has much higher call volume; `--max_rounds` is the primary cost knob.
- `turtle.sh` / `run_passk.sh` start multiple Python processes; watch provider rate limits and cost.

