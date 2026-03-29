#!/usr/bin/env python3
"""
InteractiveBench Unified Testing Framework - Main Entry Point

This is the primary interface for running benchmarks across all modules.

Usage:
    python run_benchmark.py --models gpt-4o
    python run_benchmark.py --models gpt-4o claude-3.5-sonnet
    python run_benchmark.py --models gpt-4o --modules math situation_puzzle
"""

import sys
from benchmark_framework.cli import main

if __name__ == '__main__':
    sys.exit(main() or 0)
