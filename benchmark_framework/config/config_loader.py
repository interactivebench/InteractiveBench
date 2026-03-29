"""Configuration loader for the benchmark framework"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigLoader:
    """Loads and manages framework configuration"""

    DEFAULT_CONFIG_PATH = Path(__file__).parent / "default_config.yaml"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration loader

        Args:
            config_path: Optional path to custom config file.
                        If not provided, uses default_config.yaml
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-separated key"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

        return value if value is not None else default

    def get_framework_config(self) -> Dict[str, Any]:
        """Get framework-level configuration"""
        return self.config.get('framework', {})

    def get_models(self) -> Dict[str, str]:
        """Get model registry (alias -> model_id mapping)"""
        return self.config.get('models', {})

    def get_module_config(self, module_name: str) -> Dict[str, Any]:
        """Get configuration for a specific module"""
        return self.config.get('modules', {}).get(module_name, {})

    def get_all_module_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all modules"""
        return self.config.get('modules', {})

    @staticmethod
    def load(config_path: Optional[str] = None) -> 'ConfigLoader':
        """
        Static factory method to load configuration

        Args:
            config_path: Optional path to custom config file

        Returns:
            ConfigLoader instance
        """
        path = Path(config_path) if config_path else None
        return ConfigLoader(path)
