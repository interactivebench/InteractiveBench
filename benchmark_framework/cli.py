"""Command-line interface for the benchmark framework"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from benchmark_framework.core.runner import BenchmarkRunner
from benchmark_framework.config.config_loader import ConfigLoader


def setup_logging(verbose: bool = False):
    """Configure logging"""
    import logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_adapters(runner: BenchmarkRunner) -> bool:
    """
    Load all module adapters

    Args:
        runner: BenchmarkRunner instance

    Returns:
        True if successful, False otherwise
    """
    try:
        # Import adapters
        from .adapters.math_adapter import MathAdapter
        from .adapters.puzzle_adapter import PuzzleAdapter
        from .adapters.trust_adapter import TrustAdapter

        # Get module configs
        module_configs = runner.config_loader.get_all_module_configs()

        # Register adapters
        runner.register_adapter('math', MathAdapter(module_configs.get('math', {})))
        runner.register_adapter('situation_puzzle', PuzzleAdapter(module_configs.get('situation_puzzle', {})))
        runner.register_adapter('trust_game', TrustAdapter(module_configs.get('trust_game', {})))

        return True
    except ImportError as e:
        print(f"[ERROR] Failed to import adapters: {e}")
        return False


def list_models(config: ConfigLoader):
    """List all available models"""
    from .core.model_registry import ModelRegistry

    models = config.get_models()

    print("\n" + "="*60)
    print("Available Models")
    print("="*60 + "\n")

    if not models:
        print("[INFO] No models registered in config")
        return

    # Print as table
    print(f"{'Alias':<25} {'Model ID':<40}")
    print("-" * 65)

    for alias, model_id in sorted(models.items()):
        print(f"{alias:<25} {model_id:<40}")

    print("\n" + "="*60 + "\n")

    print("Usage:")
    print("  python run_benchmark.py --models <alias>")
    print("  python run_benchmark.py --models <full_model_id>")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="InteractiveBench Unified Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all modules for a single model
  python run_benchmark.py --models gpt-4o

  # Run specific modules
  python run_benchmark.py --models gpt-4o --modules math situation_puzzle

  # Run multiple models
  python run_benchmark.py --models gpt-4o claude-3.5-sonnet gemini-pro

  # Use custom config
  python run_benchmark.py --config my_config.yaml --models gpt-4o

  # Run without resume (start fresh)
  python run_benchmark.py --models gpt-4o --no-resume

  # List available models
  python run_benchmark.py --list-models
        """
    )

    # Model selection
    parser.add_argument(
        '--models', '-m',
        nargs='+',
        help='Models to benchmark (can use aliases or full model IDs)'
    )

    # Module selection
    parser.add_argument(
        '--modules', '-M',
        nargs='+',
        choices=['math', 'situation_puzzle', 'trust_game'],
        help='Modules to run (default: all)'
    )

    # Configuration
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to custom config file'
    )

    # Execution options
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Do not resume from existing results'
    )

    # Output options
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default='results',
        help='Output directory for results (default: results)'
    )

    # Utility
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='List all available models and exit'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Load config
    try:
        config = ConfigLoader.load(args.config)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    # Handle --list-models
    if args.list_models:
        list_models(config)
        return 0

    # Validate required arguments
    if not args.models:
        parser.error("--models is required (unless using --list-models)")

    # Create runner
    runner = BenchmarkRunner(config_path=args.config)

    # Update output dir if specified
    if args.output_dir:
        runner.output_dir = Path(args.output_dir)
        runner.output_dir.mkdir(exist_ok=True)

    # Load adapters
    if not load_adapters(runner):
        return 1

    # Determine verbosity
    verbose = not args.quiet

    # Run benchmark
    summary = runner.run_benchmark(
        models=args.models,
        modules=args.modules,
        resume=not args.no_resume,
        verbose=verbose
    )

    # Generate reports
    if summary.results:
        from .reporters.json_reporter import JSONReporter
        from .reporters.markdown_reporter import MarkdownReporter

        json_reporter = JSONReporter()
        md_reporter = MarkdownReporter()

        json_path = runner.output_dir / "benchmark_report.json"
        md_path = runner.output_dir / "benchmark_report.md"

        json_reporter.generate(summary, json_path)
        md_reporter.generate(summary, md_path)

        if verbose:
            print(f"\n[INFO] Reports generated:")
            print(f"  - JSON: {json_path}")
            print(f"  - Markdown: {md_path}")

    return 0 if summary.failed_tasks == 0 else 1


if __name__ == '__main__':
    sys.exit(main() or 0)
