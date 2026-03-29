"""Base adapter interface for all module adapters"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class BenchmarkResult:
    """Unified result structure across all modules"""

    module_name: str
    model_name: str
    status: str  # success, error, timeout
    metrics: Dict[str, Any]
    output_path: str
    duration_seconds: float
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: __import__('time').strftime("%Y-%m-%d %H:%M:%S"))
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'module_name': self.module_name,
            'model_name': self.model_name,
            'status': self.status,
            'metrics': self.metrics,
            'output_path': self.output_path,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message,
            'timestamp': self.timestamp,
            'metadata': self.metadata
        }


class BaseModuleAdapter(ABC):
    """Abstract base class for all module adapters"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter

        Args:
            config: Module-specific configuration
        """
        self.config = config
        self.module_name = self.__class__.__name__.replace('Adapter', '').lower()

    @abstractmethod
    def validate_environment(self) -> bool:
        """
        Check if module dependencies are available

        Returns:
            True if environment is valid, False otherwise
        """
        pass

    @abstractmethod
    def get_command_args(self, model: str, output_dir: str) -> List[str]:
        """
        Generate command-line arguments for running the module

        Args:
            model: Model identifier
            output_dir: Output directory path

        Returns:
            List of command-line arguments
        """
        pass

    @abstractmethod
    def parse_output(self, output_path: str) -> BenchmarkResult:
        """
        Parse module output into unified result format

        Args:
            output_path: Path to module output file

        Returns:
            BenchmarkResult object
        """
        pass

    @abstractmethod
    def get_default_metrics(self) -> Dict[str, Any]:
        """
        Return default metrics structure for this module

        Returns:
            Dictionary with default metric values
        """
        pass

    def get_required_env_vars(self) -> List[str]:
        """
        Return list of required environment variables

        Returns:
            List of environment variable names
        """
        return ["OPENROUTER_API_KEY"]

    def get_output_path(self, model: str, output_dir: str) -> Path:
        """
        Generate standardized output path for this module

        Args:
            model: Model identifier
            output_dir: Output directory path

        Returns:
            Path object for output file
        """
        # Sanitize model name for filename
        safe_model = model.replace('/', '_').replace(':', '-')

        # Subclasses can override this for custom naming
        return Path(output_dir) / f"{self.module_name}_{safe_model}.json"
