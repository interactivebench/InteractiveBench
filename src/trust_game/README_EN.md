# Repeated Prisoner's Dilemma (Trust Game) Benchmark

A Python multi-agent environment for evaluating multiple LLMs in a repeated Prisoner’s Dilemma (trust game), focusing on strategy, reciprocity, retaliation, and long-run payoff under continuation probability \(\delta\).

## Features

- Repeated Prisoner’s Dilemma for multiple agents
- Baseline agents (Random, TitForTat)
- Customizable payoff matrix
- Round-robin tournament (pairwise matchups)
- Full game history and summary statistics
- LLM agents via OpenRouter (OpenAI-compatible API)

## Files

- `agents.py`: agent implementations (Random, TitForTat, LLM, etc.)
- `game.py`: single game logic
- `tournament.py`: tournament orchestration
- `main.py`: CLI entrypoint
- `test_single_game.sh`: quick single-game script (cheap model)
- `test_tournament.sh`: quick tournament script (multiple cheap models)

## Install dependencies

```bash
pip install openai python-dotenv
# for plotting outputs under plots/:
pip install matplotlib
```

## Environment variables

Using OpenRouter requires setting credentials. You can use either a `.env` file or shell environment variables.

### Option A: `.env` file (recommended)

Create `.env` under `trust_game/`:

```bash
OPENROUTER_API_KEY=your-api-key-here

# optional OpenRouter headers
OPENROUTER_HTTP_REFERER=https://your-site.com
OPENROUTER_X_TITLE=Trust Game Benchmark
```

### Option B: export variables

```bash
export OPENROUTER_API_KEY="your-api-key"
export OPENROUTER_HTTP_REFERER="your-referer"   # optional
export OPENROUTER_X_TITLE="your-title"          # optional
```

The code will load `.env` automatically (if present) and will also read system environment variables.

## Usage

### 1) Single game

```bash
python main.py --mode single \
  --agents "TitForTat-1:tft" "Random-1:random:0.6" \
  --rounds-range 3 7
```

### 2) Tournament (default)

```bash
# default baseline agents
python main.py

# specify agents
python main.py \
  --agents "TitForTat-1:tft" "Random-1:random:0.5" "Random-2:random:0.7" \
  --rounds-range 3 7 \
  --num-games 3

# include LLM agents
python main.py \
  --agents "GPT-4:llm:gpt-4" "Gemini:llm:google/gemini-pro" "TitForTat-1:tft" \
  --rounds-range 3 7 \
  --num-games 2 \
  --output results.json
```

### 3) Agent spec format

Agent spec: `name:type[:param]`

- `random`: random policy
  - format: `name:random:cooperate_prob` (optional, default 0.5)
  - example: `Random-1:random:0.6`
- `tft`: TitForTat
  - format: `name:tft`
  - example: `TitForTat-1:tft`
- `llm`: LLM agent
  - format: `name:llm:model_name`
  - examples: `GPT-4:llm:gpt-4`, `Gemini:llm:google/gemini-pro`

### 4) Quick test scripts

```bash
./test_single_game.sh
./test_tournament.sh
```

### 5) Output

Use `--output` to save results as JSON:

```bash
python main.py --output results.json
```

## Notes

- Prompts sent to the model APIs are in English.
- LLM agents require valid API keys.
- Logs are written under `logs/`; you should keep them ignored by git (see `.gitignore`).

