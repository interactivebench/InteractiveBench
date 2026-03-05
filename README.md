# InteractiveBench

The official repository for the [paper](./Interactive_Benchmarks.pdf) **Interactive Benchmarks**.

![](assets/overview.png)

## Repository Overview

- **`src/situation_puzzle/`**: Situation-based reasoning.
- **`src/math/`**: Interactive math evaluation pipeline: naive solving vs. Interactive-Proof-style solving, with pass@k evaluation as a comparison baseline.
- **`src/trust_game/`**: Trust Game tournament (baseline + LLM agents).

## Quick Start

### Requirements

- Python **3.10+**
- A valid model endpoint is required (most scripts in this repository default to using the **OpenRouter OpenAI-compatible API**).

### Unified Environment Variables (Recommended)

Most scripts read the following environment variables (you may define them in a `.env` file inside each subdirectory, or export them directly):

- **`OPENROUTER_API_KEY`**: Required  
- **`OPENROUTER_BASE_URL`**: Optional (default: `https://openrouter.ai/api/v1`)

Example:

```bash
export OPENROUTER_API_KEY="sk-..."
export OPENROUTER_BASE_URL="https://openrouter.ai/api/v1"
```

### Installing Dependencies

```bash
pip install -r requirements.txt
```

> Note: Different tasks require only subsets of dependencies. Please refer to each subdirectory’s README for details.

## Directory Structure

```text
InteractiveBench/
  README.md
  LICENSE
  src/
    trust_game/
    situation_puzzle/
    math/
    poker/
```

## Results and Reproducibility

- **Result Outputs**: Most scripts write results to a `results/` directory (or a specified output path) within their respective folders, and include reproducibility metadata whenever possible (e.g., model name, hyperparameters).
- **Resume Support**: Most scripts support resume functionality (i.e., skipping completed samples/matches if output files already exist). See each subdirectory’s README for specifics.

## Contributing

- Contribution guidelines are provided in `CONTRIBUTING.md` (including requirements for adding new benchmark subdirectories, result formats, README standards, etc.).

## Citation / License

- **License**: MIT (see `LICENSE`)
- If you use this repository’s evaluation pipeline in a paper or report, please cite:
  repository name + the specific benchmark used + the commit hash (especially if you forked and modified the code).
