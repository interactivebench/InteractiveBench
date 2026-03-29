"""Base reporter interface"""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseReporter(ABC):
    """Abstract base class for all reporters"""

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return file extension for this reporter"""
        pass

    @abstractmethod
    def generate(self, summary, output_path: Path):
        """
        Generate report from summary

        Args:
            summary: BenchmarkSummary object
            output_path: Path to output file
        """
        pass
