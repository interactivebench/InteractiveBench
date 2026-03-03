# Situation Puzzle Benchmark

This is a minimal, reproducible Situation Puzzle benchmark designed to evaluate different LLMs as **players** in terms of their questioning strategies and convergence ability. A fixed model serves as the **judge** (which knows the ground-truth solution).

There is **no hint mechanism**: the judge only responds to questions with `YES / NO / BOTH / IRRELEVANT`, and to final guesses prefixed with `FINAL:` with `CORRECT / INCORRECT`.

## Files

- `benchmark.py`: Per-puzzle evaluation runner (**single-process, sequential execution, resume supported**)
- `client.py`: OpenAI-compatible client wrapper (currently defaults to OpenRouter)
- `puzzle_loader.py`: Puzzle dataset loader
- `data/puzzles_en.json`: English puzzle dataset
- `run_benchmark.sh`: Convenience script (launches multiple processes in parallel over a list of players)

## Setup

### 1) Configure Credentials / Endpoint

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"   # Optional
```

> Note: `benchmark.py` currently hardcodes the base_url as `https://openrouter.ai/api/v1`.  
> If you need a custom endpoint, please modify the source code accordingly or wrap your own client.

### 2) Run

Execute in this directory:

```bash
./run_benchmark.sh results
```

Outputs:
- `results/<player>__<judge>.json`: One file per (player, judge) pair, containing the full transcript and per-puzzle results.