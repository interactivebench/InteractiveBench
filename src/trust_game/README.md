# Repeated Prisoner’s Dilemma (Trust Game) Benchmark

A Python multi-agent environment for evaluating the strategic and reasoning capabilities of multiple LLMs in the repeated Prisoner’s Dilemma (Trust Game).

## Features

- Supports multiple LLM agents playing repeated Prisoner’s Dilemma
- Includes baseline agents (Random, Grim Trigger, TFT)
- Customizable payoff matrix
- Round-robin tournament (pairwise matches)
- Complete game history and statistics
- OpenRouter API support for LLM calls

## File Structure

- `agents.py`: Agent definitions (Random, Grim Trigger, TFT, LLM)
- `game.py`: Single-game logic
- `tournament.py`: Round-robin tournament management
- `main.py`: Main entry point and CLI interface
- `test_single_game.sh`: Single-game test script
- `test_tournament.sh`: Tournament test script

## Environment Variable Configuration

When using the OpenRouter API, you must configure the following environment variables. Two options are available:

### Option 1: Use a `.env` File (Recommended)

Create a `.env` file inside the `trust_game` directory:

```bash
# OpenRouter API Key (required)
OPENROUTER_API_KEY=your-api-key-here

# Optional: additional OpenRouter headers
OPENROUTER_HTTP_REFERER=https://your-site.com
OPENROUTER_X_TITLE=Trust Game Benchmark
```

### Option 2: Use System Environment Variables

```bash
export OPENROUTER_API_KEY="your-api-key"
# Optional
export OPENROUTER_HTTP_REFERER="your-referer"
export OPENROUTER_X_TITLE="your-title"
```

**Note**: The code automatically loads the `.env` file (if present) and also reads system environment variables.

## Usage

### 1. Single Game

```bash
python main.py --mode single \
    --agents "Grim Trigger-1:tft" "Random-1:random:0.6" \
    --rounds-range 3 7
```

### 2. Round-Robin Tournament (Default)

```bash
# Use default baseline agents
python main.py

# Specify agents
python main.py \
    --agents "Grim Trigger-1:tft" "Random-1:random:0.5" "Random-2:random:0.7" \
    --rounds-range 3 7 \
    --num-games 3

# Use LLM agents
python main.py \
    --agents "GPT-4:llm:gpt-4" "Gemini:llm:google/gemini-pro" "Grim Trigger-1:tft" \
    --rounds-range 3 7 \
    --num-games 2 \
    --output results.json
```

## Agent Format

Agent format: `name:type[:param]`

- `random`: Random strategy  
  - Format: `name:random:cooperate_prob` (cooperate_prob optional, default 0.5)  
  - Example: `Random-1:random:0.6`
  
- `tft`: Tit-for-Tat baseline  
  - Format: `name:tft`  
  - Example: `TFT-1:tft`
  
- `grim`: Grim Trigger baseline  
  - Format: `name:grim`  
  - Example: `Grim Trigger-1:grim`
  
- `llm`: LLM agent  
  - Format: `name:llm:model_name`  
  - Example: `GPT-4:llm:gpt-4` or `Gemini:llm:google/gemini-pro`

## Quick Test Scripts

Two convenience scripts are provided for testing with low-cost LLM models:

### Single Game Test

```bash
./test_single_game.sh
```

This script runs a single game between `openai/gpt-3.5-turbo` and the Grim Trigger baseline.

### Tournament Test

```bash
./test_tournament.sh
```

This script runs a round-robin tournament using multiple low-cost LLM models (gpt-3.5-turbo, claude-3-haiku, gemini-flash-1.5) along with baseline agents.

**Note**: You may modify the model list in the scripts to add or replace other low-cost models.

## Output Results

Use the `--output` argument to save results as a JSON file:

```bash
python main.py --output results.json
```

## Code Example

### Using in Python

```python
import asyncio
from agents import RandomAgent, GrimTriggerAgent, LLMAgent
from game import Game
from tournament import Tournament

async def example():
    # Create agents
    agent1 = GrimTriggerAgent("Grim Trigger")
    agent2 = LLMAgent("GPT-4", "gpt-4")
    
    # Single game
    game = Game(agent1, agent2, rounds_range=(3, 7))
    result = await game.play()
    print(result)
    
    # Tournament
    agents = [
        RandomAgent("Random-1"),
        GrimTriggerAgent("Grim Trigger-1"),
        LLMAgent("GPT-4", "gpt-4")
    ]
    tournament = Tournament(agents, rounds_range=(3, 7), num_games=2)
    result = await tournament.run()
    tournament.print_summary(result)

asyncio.run(example())
```

## Payoff Matrix

Default payoff matrix:

- Mutual cooperation: 2 / 2  
- One cooperates, one defects: -1 / 3 or 3 / -1  
- Mutual defection: 0 / 0  

The payoff matrix can be customized in the code.

## Logging

The system automatically records detailed information for each LLM interaction.

### LLM Agent Logs

- **Location**: `logs/` directory, filename format `{agent_name}_{timestamp}.log`
- **Contents**:
  - Full prompt sent each round (including system prompt and conversation history)
  - Raw LLM response
  - Parsed action
  - Error messages (if any)

### Game Logs

- **Location**: Console output
- **Contents**:
  - Game start/end messages
  - Actions and payoffs per round
  - Final total scores

### Viewing Logs

```bash
# View the most recent log files
ls -lt logs/ | head

# Live view (if a game is running)
tail -f logs/LLM-Test_*.log
```

## Notes

- LLM agents require a valid API key.
- The number of rounds is randomized within the specified range; LLM agents know only the range, not the exact number.
- Requires Python 3.10+.
- Log files are automatically saved under `logs/`; it is recommended to add this directory to `.gitignore`.