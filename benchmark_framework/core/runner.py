"""Core benchmark runner"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from ..config.config_loader import ConfigLoader
from .model_registry import ModelRegistry


class BenchmarkSummary:
    """Summary of all benchmark results"""

    def __init__(
        self,
        total_tasks: int,
        completed_tasks: int,
        failed_tasks: int,
        total_duration_seconds: float,
        results: List[Any],
        timestamp: str
    ):
        self.total_tasks = total_tasks
        self.completed_tasks = completed_tasks
        self.failed_tasks = failed_tasks
        self.total_duration_seconds = total_duration_seconds
        self.results = results
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'total_duration_seconds': self.total_duration_seconds,
            'timestamp': self.timestamp,
            'results': [r.to_dict() if hasattr(r, 'to_dict') else r for r in self.results]
        }


class BenchmarkRunner:
    """Main benchmark orchestration engine"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize benchmark runner

        Args:
            config_path: Optional path to custom config file
        """
        self.config_loader = ConfigLoader.load(config_path)
        self.model_registry = ModelRegistry(self.config_loader.get_models())

        # Get output directory
        framework_config = self.config_loader.get_framework_config()
        self.output_dir = Path(framework_config.get('output_dir', 'results'))
        self.output_dir.mkdir(exist_ok=True)

        # Adapters will be registered later
        self.adapters = {}
        self.results = []

    def register_adapter(self, name: str, adapter):
        """
        Register a module adapter

        Args:
            name: Module name
            adapter: Adapter instance
        """
        self.adapters[name] = adapter

    def run_benchmark(
        self,
        models: List[str],
        modules: Optional[List[str]] = None,
        resume: bool = True,
        verbose: bool = True
    ) -> BenchmarkSummary:
        """
        Run benchmark across specified models and modules

        Args:
            models: List of model identifiers
            modules: List of module names (None = all registered)
            resume: Whether to skip completed benchmarks
            verbose: Whether to print progress

        Returns:
            BenchmarkSummary object
        """
        # Resolve model names
        resolved_models = [self.model_registry.resolve(m) for m in models]

        # Determine which modules to run
        if modules is None:
            modules = list(self.adapters.keys())

        # Filter out modules that don't have adapters
        valid_modules = [m for m in modules if m in self.adapters]
        if not valid_modules:
            if verbose:
                print("[ERROR] No valid modules specified")
            return BenchmarkSummary(0, 0, 0, 0.0, [], time.strftime("%Y-%m-%d %H:%M:%S"))

        # Create tasks
        tasks = self._create_tasks(resolved_models, valid_modules, resume)

        if verbose:
            print(f"\n{'='*60}")
            print(f"InteractiveBench Unified Testing Framework")
            print(f"{'='*60}")
            print(f"Models: {', '.join(models)}")
            print(f"Modules: {', '.join(valid_modules)}")
            print(f"Total tasks: {len(tasks)}")
            if resume:
                print(f"Resume: enabled (will skip completed tasks)")
            else:
                print(f"Resume: disabled (will run all tasks)")
            print(f"Output: {self.output_dir}")
            print(f"{'='*60}\n")

        # Execute tasks sequentially
        start_time = time.time()

        for i, (module, model) in enumerate(tasks, 1):
            if verbose:
                print(f"[{i}/{len(tasks)}] Running {module} with {model}...")

            result = self._run_task(module, model, resume, verbose)
            if result:
                self.results.append(result)

                # Mark as completed
                if result.status == 'success':
                    self.model_registry.mark_completed(module, model, result.output_path)

        duration = time.time() - start_time

        # Generate summary
        completed = len([r for r in self.results if r.status == 'success'])
        failed = len([r for r in self.results if r.status == 'error'])

        summary = BenchmarkSummary(
            total_tasks=len(tasks),
            completed_tasks=completed,
            failed_tasks=failed,
            total_duration_seconds=duration,
            results=self.results,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )

        if verbose:
            self._print_summary(summary)

        return summary

    def _create_tasks(
        self,
        models: List[str],
        modules: List[str],
        resume: bool
    ) -> List[tuple]:
        """
        Create list of (module, model) tasks

        Args:
            models: List of model identifiers
            modules: List of module names
            resume: Whether to filter out completed tasks

        Returns:
            List of (module, model) tuples
        """
        tasks = []

        for module in modules:
            for model in models:
                if resume and self.model_registry.is_completed(module, model):
                    # Skip if already completed
                    continue
                tasks.append((module, model))

        return tasks

    def _run_task(
        self,
        module: str,
        model: str,
        resume: bool,
        verbose: bool
    ):
        """
        Execute a single benchmark task

        Args:
            module: Module name
            model: Model identifier
            resume: Whether resume is enabled
            verbose: Whether to print progress

        Returns:
            BenchmarkResult object or None
        """
        adapter = self.adapters.get(module)

        if not adapter:
            if verbose:
                print(f"[ERROR] No adapter found for module: {module}")
            return None

        # Validate environment
        if not adapter.validate_environment():
            if verbose:
                print(f"[ERROR] Environment validation failed for {module}")
            return None

        # Get output path
        output_path = adapter.get_output_path(model, str(self.output_dir))

        # Check if we should resume
        if resume and output_path.exists():
            if verbose:
                print(f"  [INFO] Resuming from existing output: {output_path}")

            try:
                result = adapter.parse_output(str(output_path))
                # Mark as completed since we're using existing result
                self.model_registry.mark_completed(module, model, str(output_path))
                return result
            except Exception as e:
                if verbose:
                    print(f"  [WARN] Failed to parse existing output, will re-run: {e}")

        # Build command
        cmd = adapter.get_command_args(model, str(self.output_dir))

        # Execute
        try:
            if verbose:
                print(f"  [CMD] {' '.join(cmd)}")

            start = time.time()

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            duration = time.time() - start

            # Parse output
            if output_path.exists():
                benchmark_result = adapter.parse_output(str(output_path))
                benchmark_result.duration_seconds = duration

                if verbose:
                    print(f"  [DONE] Completed in {duration:.1f}s")

                return benchmark_result
            else:
                if verbose:
                    print(f"  [ERROR] Output file not found: {output_path}")

                return None

        except subprocess.TimeoutExpired:
            if verbose:
                print(f"  [ERROR] Task timed out")
            return None
        except subprocess.CalledProcessError as e:
            if verbose:
                print(f"  [ERROR] Task failed with exit code {e.returncode}")
                if e.stderr:
                    print(f"  [STDERR] {e.stderr}")
            return None
        except Exception as e:
            if verbose:
                print(f"  [ERROR] Unexpected error: {e}")
            return None

    def _print_summary(self, summary: BenchmarkSummary):
        """Print benchmark summary"""
        print(f"\n{'='*60}")
        print(f"Benchmark Complete!")
        print(f"{'='*60}")
        print(f"Total tasks: {summary.total_tasks}")
        print(f"Completed: {summary.completed_tasks}")
        print(f"Failed: {summary.failed_tasks}")
        print(f"Duration: {summary.total_duration_seconds:.1f}s")
        print(f"\nResults saved to: {self.output_dir}")
        print(f"{'='*60}\n")
