# InteractiveBench

An interactive benchmark suite for evaluating LLMs via **multi-turn interaction** (games, Q&A, judging). The repository is organized to be **reproducible**, **extensible**, and **easy to compare**: clear entrypoints, resumable runs, and stable result artifacts.

## What’s inside

- **`src/trust_game/`**: Repeated Prisoner’s Dilemma (Trust Game) multi-agent environment (baselines + LLM agents, OpenRouter supported).
- **`src/situation_puzzle/`**: Situation Puzzle (lateral-thinking / yes-no game) evaluation with a fixed judge and an evaluated player; full transcripts are saved.
- **`src/math/`**: Interactive math pipeline: naive solving vs Situation-Puzzle-style yes/no Q&A solving, plus pass@k re-evaluation (mainly for OpenRouter).

## Quick start

### Requirements

- Python **3.10+**
- A working model endpoint (most scripts default to **OpenRouter’s OpenAI-compatible API**)

### Shared environment variables (recommended)

Most scripts read:

- **`OPENROUTER_API_KEY`** (required)
- **`OPENROUTER_BASE_URL`** (optional, default `https://openrouter.ai/api/v1`)

Example:

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
```

### Dependency installation

Each sub-benchmark has its own minimal dependencies. Follow the README in the subdirectory you want to run:

- `src/trust_game/README.md` (and `README_EN.md`)
- `src/situation_puzzle/README.md` (and `README_EN.md`)
- `src/math/README.md` (and `README_EN.md`)

If you want a “cover most scripts” install:

```bash
pip install openai python-dotenv tqdm datasets pandas matplotlib httpx
```

## Repository layout

```text
InteractiveBench/
  README.md
  README_EN.md
  LICENSE
  src/
    trust_game/
    situation_puzzle/
    math/
```

## Entrypoints by sub-benchmark

> Note: we do **not** change the directory layout. Some scripts/fields keep legacy names (e.g., `src/math/turtle.py`, `__turtle__` in output filenames, `turtle_history` fields), but the semantics are unified as **Situation Puzzle / lateral-thinking style yes/no Q&A**.

### 1) Repeated Prisoner’s Dilemma (`src/trust_game/`)

- **Good for**: strategic behavior, reciprocity/retaliation, long-run payoff maximization with continuation probability \(\delta\)
- **Entrypoint**: `python main.py` (`single` / `tournament` / `ablation`)
- **Outputs**: JSON results + plots under `plots/` (see subdir README)

See: `src/trust_game/README_EN.md`

### 2) Situation Puzzle (`src/situation_puzzle/`)

- **Good for**: question efficiency, information gain, convergence under restricted feedback (YES/NO/BOTH/IRRELEVANT)
- **Entrypoint**: `bash run_benchmark.sh results`
- **Outputs**: one JSON per (player, judge) pair (full transcripts); optional CSV/plots (see subdir README)

See: `src/situation_puzzle/README_EN.md`

### 3) Math Interactive (`src/math/`)

- **Good for**: how models reduce uncertainty via judge-interaction, and comparisons vs naive solving; pass@k re-evaluation
- **Entrypoint**: `naive.py` (naive) + `turtle.py` (Situation-Puzzle-style Q&A), plus `run_passk.sh` / `compute_k.sh`

See: `src/math/README_EN.md`

## Results and reproducibility

- **Artifacts**: scripts typically write into `results/` (or your specified output directory), including meta fields for reproducibility.
- **Resuming**: most scripts support “skip finished items if output exists” behavior.
- **Guidelines**: see `REPRODUCIBILITY.md` for what to record (versions, seeds, concurrency, caching, etc.).

## Contributing

See `CONTRIBUTING.md`.

## License

MIT (see `LICENSE`). If you use this benchmark in a paper/report, please cite the repository + the specific sub-benchmark + the commit hash you ran.

