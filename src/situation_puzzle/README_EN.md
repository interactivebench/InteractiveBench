# Situation Puzzle Benchmark (lateral-thinking Q&A)

A minimal, reproducible Situation Puzzle benchmark to evaluate LLMs as the **player** in a constrained yes/no question game. A fixed model acts as the **judge** (knows the hidden solution).

**No hints**: the judge only returns `YES/NO/BOTH/IRRELEVANT` to questions, and `CORRECT/INCORRECT` to `FINAL:` proposals.

## Files

- `benchmark.py`: batch runner (**single process, sequential, resumable**)
- `client.py`: OpenAI-compatible client wrapper (currently OpenRouter by default)
- `puzzle_loader.py`: loads puzzles from `puzzles_en.json`
- `puzzles_en.json`: English puzzle set
- `run_benchmark.sh`: convenience script (spawns one process per player model)
- `requirements.txt`: minimal dependency list

## Setup

### 1) Credentials / endpoint

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"   # optional
```

> Note: `benchmark.py` currently hardcodes the base URL as `https://openrouter.ai/api/v1`. If you need a custom endpoint, adjust the code or wrap the client.

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Run

Run from this directory:

```bash
bash run_benchmark.sh results
```

Outputs:

- `results/<player>__<judge>.json`: one output file per (player, judge) pair, containing full transcripts and per-puzzle results

