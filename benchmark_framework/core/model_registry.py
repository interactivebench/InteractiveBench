"""Model registry for name resolution and state tracking"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any


class ModelRegistry:
    """Manages model name resolution and benchmark completion state"""

    def __init__(self, models_config: Dict[str, str]):
        """
        Initialize model registry

        Args:
            models_config: Dictionary mapping aliases to full model IDs
        """
        self.models = models_config
        self.state_file = Path('.benchmark_state.json')
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load previous benchmark state"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {'completed': {}, 'version': '1.0.0'}
        return {'completed': {}, 'version': '1.0.0'}

    def _save_state(self):
        """Persist current state to disk"""
        self.state['last_updated'] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def resolve(self, model_identifier: str) -> str:
        """
        Resolve model alias or full ID to canonical model ID

        Args:
            model_identifier: Model alias or full ID

        Returns:
            Canonical model ID (full ID)
        """
        # If it's already a full ID (contains '/'), return as-is
        if '/' in model_identifier:
            return model_identifier

        # Look up in alias registry
        canonical_id = self.models.get(model_identifier)
        if canonical_id:
            return canonical_id

        # Return as-is if not found (might be a new model)
        return model_identifier

    def get_alias(self, model_id: str) -> Optional[str]:
        """
        Get alias for a given model ID

        Args:
            model_id: Full model ID

        Returns:
            Alias if found, None otherwise
        """
        for alias, full_id in self.models.items():
            if full_id == model_id:
                return alias
        return None

    def list_models(self) -> List[Dict[str, str]]:
        """
        List all available models

        Returns:
            List of dictionaries with 'alias' and 'model_id' keys
        """
        return [
            {'alias': alias, 'model_id': model_id}
            for alias, model_id in sorted(self.models.items())
        ]

    def mark_completed(self, module: str, model: str, output_path: str):
        """
        Mark a benchmark as completed

        Args:
            module: Module name
            model: Model identifier
            output_path: Path to output file
        """
        if module not in self.state['completed']:
            self.state['completed'][module] = {}

        self.state['completed'][module][model] = {
            'output_path': output_path,
            'timestamp': time.time()
        }
        self._save_state()

    def is_completed(self, module: str, model: str) -> bool:
        """
        Check if a benchmark has been completed

        Args:
            module: Module name
            model: Model identifier

        Returns:
            True if completed, False otherwise
        """
        return (
            module in self.state['completed'] and
            model in self.state['completed'][module]
        )

    def get_completed_info(self, module: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Get completion information for a benchmark

        Args:
            module: Module name
            model: Model identifier

        Returns:
            Dictionary with 'output_path' and 'timestamp', or None if not completed
        """
        if self.is_completed(module, model):
            return self.state['completed'][module][model]
        return None

    def get_pending(self, models: List[str], modules: List[str]) -> List[tuple]:
        """
        Get list of (module, model) pairs that need to run

        Args:
            models: List of model identifiers
            modules: List of module names

        Returns:
            List of (module, model) tuples that are not yet completed
        """
        pending = []
        for module in modules:
            for model in models:
                if not self.is_completed(module, model):
                    pending.append((module, model))
        return pending

    def clear_module_state(self, module: str):
        """
        Clear completion state for a specific module

        Args:
            module: Module name
        """
        if module in self.state['completed']:
            del self.state['completed'][module]
            self._save_state()

    def clear_all_state(self):
        """Clear all completion state"""
        self.state['completed'] = {}
        self._save_state()
