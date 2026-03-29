"""Trust Game module adapter"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any

from .base_adapter import BaseModuleAdapter, BenchmarkResult


class TrustAdapter(BaseModuleAdapter):
    """Adapter for the trust_game module"""

    def validate_environment(self) -> bool:
        """Check if trust_game module dependencies are available"""
        trust_dir = Path("src/trust_game")
        if not trust_dir.exists():
            return False

        main_path = trust_dir / "main.py"
        if not main_path.exists():
            return False

        return True

    def _get_provider_info(self, model: str) -> tuple:
        """
        Determine provider type and settings for a model

        Returns:
            (provider_type, api_key_env, base_url)
        """
        # Check if model uses custom provider
        if model.startswith("moonshot/") or "kimi" in model.lower():
            return ("custom", "CUSTOM_API_KEY", "https://api.moonshot.ai/v1")
        else:
            return ("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1")

    def get_command_args(self, model: str, output_dir: str) -> List[str]:
        """
        Generate command-line arguments for main.py
        For trust_game, we need to create an LLM agent and play against baseline agents
        """
        delta = self.config.get('delta', 0.9)
        rounds_range = self.config.get('rounds_range', [3, 7])
        num_games = self.config.get('num_games', 5)
        max_rounds = self.config.get('max_rounds', 25)

        output_file = Path(output_dir) / f"trust_game_{model.replace('/', '_')}.json"

        # Determine provider for the model
        provider_type, api_key_env, default_base_url = self._get_provider_info(model)

        # Trust game uses custom agent format
        # Format: name:type:model or name:type:model:api_key:base_url
        agent_spec = f"KimiLLM:llm:{model}"

        cmd = [
            "python",
            "src/trust_game/main.py",
            "--mode", "tournament",
            "--agents", agent_spec, "GrimTrigger:grim", "TFT:tft", "Random:random:0.5",
            "--delta", str(delta),
            "--rounds-range", str(rounds_range[0]), str(rounds_range[1]),
            "--repeats", str(num_games),
            "--max-rounds", str(max_rounds),
            "--output", str(output_file)
        ]

        # Note: Trust game reads API keys from environment variables
        # For custom providers, we need to set CUSTOM_API_KEY and CUSTOM_BASE_URL

        return cmd

    def parse_output(self, output_path: str) -> BenchmarkResult:
        """Parse trust_game module JSON output"""
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract model info from the results
        # Trust game output format may vary, so we'll handle multiple formats

        # Try to extract summary information
        summary = data.get('summary', {})
        player_scores = data.get('player_scores', {})
        agent_stats = data.get('agent_stats', {})

        # Find the LLM agent's stats
        llm_stats = {}
        for agent_name, stats in agent_stats.items():
            if 'LLM' in agent_name or 'KimiLLM' in agent_name:
                llm_stats = stats
                break

        # Calculate metrics
        avg_score = llm_stats.get('avg_score_per_round', summary.get('avg_score', 0.0))
        cooperation_rate = llm_stats.get('cooperation_rate', 0.0)
        total_games = llm_stats.get('total_games', data.get('num_games', 0))

        metrics = {
            "avg_score_per_round": avg_score,
            "cooperation_rate": cooperation_rate,
            "total_games": total_games,
            "delta": data.get('delta', 0.9)
        }

        # Extract model name from filename or data
        model_name = "unknown"
        if 'llm_model' in data:
            model_name = data['llm_model']
        else:
            # Try to extract from filename
            filename = Path(output_path).stem
            if 'trust_game_' in filename:
                model_name = filename.replace('trust_game_', '').replace('_', '/')

        return BenchmarkResult(
            module_name="trust_game",
            model_name=model_name,
            status="success",
            metrics=metrics,
            output_path=output_path,
            duration_seconds=0.0,
            metadata={
                'delta': data.get('delta', 0.9),
                'num_games': total_games
            }
        )

    def get_default_metrics(self) -> Dict[str, Any]:
        return {
            "avg_score_per_round": 0.0,
            "cooperation_rate": 0.0,
            "total_games": 0,
            "delta": 0.9
        }
