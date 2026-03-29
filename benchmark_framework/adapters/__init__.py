"""Module adapters"""
from .base_adapter import BaseModuleAdapter, BenchmarkResult
from .math_adapter import MathAdapter
from .puzzle_adapter import PuzzleAdapter
from .trust_adapter import TrustAdapter

__all__ = [
    'BaseModuleAdapter',
    'BenchmarkResult',
    'MathAdapter',
    'PuzzleAdapter',
    'TrustAdapter'
]
