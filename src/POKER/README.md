# POKER: Multi-Table LLM Texas Hold'em Benchmark

This directory contains a Vite + React poker benchmark app where six fixed LLM agents play No-Limit Texas Hold'em across multiple tables.

## What It Does

- Runs 10 tables in parallel (6 players per table).
- Uses fixed model identities per seat:
  - `x-ai/grok-4.1-fast`
  - `google/gemini-3-flash-preview`
  - `openai/gpt-5-mini`
  - `moonshotai/kimi-k2-thinking`
  - `deepseek/deepseek-v3.2`
  - `qwen/qwen3-max`
- Logs gameplay and per-hand stats as NDJSON.
- Includes analysis scripts and generated result figures (`poker_stats_*.png/.pdf`).

## Run Locally

Prerequisites: Node.js 18+.

1. Install dependencies:
   `npm install`
2. Set OpenRouter key:
   - `.env.local`:
     `OPENROUTER_POKER_API=sk-...`
   - or export shell env var:
     `export OPENROUTER_POKER_API="sk-..."`
3. Start dev server:
   `npm run dev`

## Logging Outputs

During runtime, the dev middleware writes:

- `game-log-{tableId}.ndjson` (action/state events)
- `stats-log-{tableId}.ndjson` (per-hand aggregated player stats)

for `tableId` from `1` to `10`.

## Analysis

Use:

`python3 analyze_stats.py`

to generate summary plots from `stats-log-*.ndjson`.
