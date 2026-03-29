"""Situation Puzzle module adapter"""

import json
from pathlib import Path
from typing import Dict, List, Any

from .base_adapter import BaseModuleAdapter, BenchmarkResult


class PuzzleAdapter(BaseModuleAdapter):
    """Adapter for the situation_puzzle module"""

    def validate_environment(self) -> bool:
        """Check if situation_puzzle module dependencies are available"""
        puzzle_dir = Path("src/situation_puzzle")
        if not puzzle_dir.exists():
            return False

        benchmark_path = puzzle_dir / "benchmark.py"
        if not benchmark_path.exists():
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
        """Generate command-line arguments for benchmark.py"""
        puzzles_path = self.config.get('puzzles_path', 'src/situation_puzzle/data/puzzles_en.json')
        judge_model = self.config.get('judge_model', 'x-ai/grok-4.1-fast')
        max_rounds = self.config.get('max_rounds', 20)

        # Determine provider for the model
        provider_type, api_key_env, default_base_url = self._get_provider_info(model)

        cmd = [
            "python",
            "src/situation_puzzle/benchmark.py",
            "--puzzles_path", puzzles_path,
            "--player_model", model,
            "--judge_model", judge_model,
            "--max_rounds", str(max_rounds),
            "--out_dir", output_dir,
            "--provider", provider_type,
        ]

        # Add provider-specific arguments
        if provider_type == "custom":
            # For custom providers like Moonshot
            cmd.extend([
                "--custom_base_url", default_base_url,
            ])
        else:
            # For OpenRouter
            cmd.extend([
                "--base_url", default_base_url,
            ])

        return cmd

    def get_output_path(self, model: str, output_dir: str) -> Path:
        """
        Generate standardized output path for situation_puzzle module
        Format: {player}__{judge}.json
        """
        judge_model = self.config.get('judge_model', 'x-ai/grok-4.1-fast')
        safe_player = model.replace('/', '_').replace(':', '-')
        safe_judge = judge_model.replace('/', '_').replace(':', '-')

        return Path(output_dir) / f"{safe_player}__{safe_judge}.json"

    def parse_output(self, output_path: str) -> BenchmarkResult:
        """Parse situation_puzzle module JSON output"""
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract model info
        player_model = data.get('player_model', 'unknown')
        judge_model = data.get('judge_model', 'unknown')

        # Get results
        results = data.get('results', [])
        summary = data.get('summary', {})

        # Calculate metrics
        total_puzzles = len(results)
        correct_count = sum(1 for r in results if r.get('success', False))
        accuracy = summary.get('accuracy', correct_count / total_puzzles if total_puzzles > 0 else 0.0)

        # Calculate average turns
        turns_list = [r.get('turns_used', 0) for r in results if r.get('success', False)]
        avg_turns = sum(turns_list) / len(turns_list) if turns_list else 0

        metrics = {
            "accuracy": accuracy,
            "total_puzzles": total_puzzles,
            "correct_puzzles": correct_count,
            "avg_turns": avg_turns,
            "max_rounds": data.get('max_rounds', 0)
        }

        return BenchmarkResult(
            module_name="situation_puzzle",
            model_name=player_model,
            status="success",
            metrics=metrics,
            output_path=output_path,
            duration_seconds=0.0,
            metadata={
                'judge_model': judge_model,
                'puzzles_path': data.get('puzzles_path', '')
            }
        )

    def get_default_metrics(self) -> Dict[str, Any]:
        return {
            "accuracy": 0.0,
            "total_puzzles": 0,
            "correct_puzzles": 0,
            "avg_turns": 0.0,
            "max_rounds": 20
        }
