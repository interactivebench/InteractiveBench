"""Math module adapter"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Any

from .base_adapter import BaseModuleAdapter, BenchmarkResult


class MathAdapter(BaseModuleAdapter):
    """Adapter for the math module"""

    def validate_environment(self) -> bool:
        """Check if math module dependencies are available"""
        # Check if math directory exists
        math_dir = Path("src/math")
        if not math_dir.exists():
            return False

        # Check if naive.py exists
        naive_path = math_dir / "naive.py"
        if not naive_path.exists():
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
        """Generate command-line arguments for naive.py"""
        dataset_path = self.config.get('dataset_path', 'src/math/data/puzzle_math.json')
        dataset_name = self.config.get('dataset_name', 'hle')
        judge_model = self.config.get('judge_model', 'x-ai/grok-4.1-fast')
        max_tokens = self.config.get('max_tokens', 5000)

        # Determine provider for the model
        provider_type, api_key_env, default_base_url = self._get_provider_info(model)

        cmd = [
            "python",
            "src/math/naive.py",
            "--dataset_path", dataset_path,
            "--dataset_name", dataset_name,
            "--player_model", model,
            "--judge_model", judge_model,
            "--max_tokens", str(max_tokens),
            "--wrong_limit", "-1",  # No early stop
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
                "--openrouter_base_url", default_base_url,
            ])

        return cmd

    def parse_output(self, output_path: str) -> BenchmarkResult:
        """Parse math module JSON output"""
        with open(output_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract model name from filename
        model_name = self._extract_model_from_path(output_path)

        # Calculate metrics
        total = len(data)
        correct = sum(1 for r in data if r.get('correct', 0) == 1)
        accuracy = correct / total if total > 0 else 0.0

        # Count status types
        status_counts = {}
        for r in data:
            status = r.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count "done but wrong"
        wrong_but_done = sum(1 for r in data if self._is_done_but_wrong(r))

        metrics = {
            "accuracy": accuracy,
            "total_questions": total,
            "correct_answers": correct,
            "wrong_but_done": wrong_but_done,
            "status_ok": status_counts.get('ok', 0),
            "status_error": status_counts.get('error', 0),
        }

        return BenchmarkResult(
            module_name="math",
            model_name=model_name,
            status="success",
            metrics=metrics,
            output_path=output_path,
            duration_seconds=0.0,  # Will be set by runner
            metadata={"dataset": self.config.get('dataset_name', 'hle')}
        )

    def get_default_metrics(self) -> Dict[str, Any]:
        return {
            "accuracy": 0.0,
            "total_questions": 0,
            "correct_answers": 0,
            "wrong_but_done": 0,
            "status_ok": 0,
            "status_error": 0,
        }

    def _extract_model_from_path(self, path: str) -> str:
        """
        Extract model name from output filename
        Example: hle__openrouter__openai_gpt-4o__judge=x-ai_grok-4.1-fast.json
        """
        filename = Path(path).stem
        parts = filename.split('__')

        if len(parts) >= 3:
            # Format: {dataset}__{provider}__{model}__judge={judge}
            # Convert back from filename format
            model_part = parts[2]
            return model_part.replace('_', '/')

        return "unknown"

    def _is_done_but_wrong(self, r: dict) -> bool:
        """
        Check if a record is "done but wrong"
        Copied from naive.py logic
        """
        if not isinstance(r, dict):
            return False
        if r.get("status") != "ok":
            return False
        if int(r.get("correct", 0)) != 0:
            return False

        extracted = r.get("extracted_gen_ans", "")
        if not self._normalize_answer(extracted):
            return False

        judge_raw = (r.get("judge_raw") or "").strip()
        if not judge_raw:
            return False
        if judge_raw.startswith("SKIPPED_"):
            return False

        extracted_j = (r.get("extracted_judgement") or "").strip()
        if not extracted_j:
            return False

        return True

    @staticmethod
    def _normalize_answer(s: str) -> str:
        """Normalize answer string"""
        if not s:
            return ""
        import re
        s = s.strip()
        s = re.sub(r"\s+", "", s)
        return s
