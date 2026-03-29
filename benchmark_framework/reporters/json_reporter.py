"""JSON report generator"""

import json
from pathlib import Path
from .base_reporter import BaseReporter


class JSONReporter(BaseReporter):
    """Generate JSON format reports"""

    @property
    def file_extension(self) -> str:
        return "json"

    def generate(self, summary, output_path: Path):
        """
        Generate JSON report

        Args:
            summary: BenchmarkSummary object
            output_path: Path to output file
        """
        report = {
            "benchmark_summary": {
                "total_tasks": summary.total_tasks,
                "completed_tasks": summary.completed_tasks,
                "failed_tasks": summary.failed_tasks,
                "total_duration_seconds": summary.total_duration_seconds,
                "timestamp": summary.timestamp
            },
            "results": [r.to_dict() if hasattr(r, 'to_dict') else r for r in summary.results]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
