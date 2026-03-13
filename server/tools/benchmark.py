"""MCP tool for benchmark snapshot generation (UC-013).

AC-59: generate_benchmark_snapshot tool
AC-62: Outputs to docs/benchmarks/snapshot_{date}.md
"""

from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastmcp import FastMCP


def register_benchmark_tools(mcp: FastMCP, engine_path: Path, state_path: Path) -> None:
    """Register benchmark-related MCP tools."""

    def _get_engine_version() -> str:
        """Read engine version from ENGINE_VERSION.yaml."""
        version_file = engine_path / "ENGINE_VERSION.yaml"
        if version_file.exists():
            try:
                with open(version_file) as f:
                    data = yaml.safe_load(f)
                    return data.get("version", "unknown")
            except Exception:
                pass
        return "unknown"

    @mcp.tool()
    def generate_benchmark_snapshot(output_path: str = "") -> dict:
        """Generate a public benchmark snapshot from Sala de Máquinas state data.

        Aggregates metrics across all projects: total UCs, coverage average,
        healing resolution rate, acceptance rate, time per UC, and delta count.
        Project names are anonymized. Outputs Markdown to docs/benchmarks/.

        Args:
            output_path: Optional custom output path. Defaults to
                         docs/benchmarks/snapshot_{date}.md under engine_path.

        Returns:
            Dict with metrics summary and the path where the file was written.
        """
        from ..benchmark_generator import generate_benchmark, render_benchmark_markdown

        engine_version = _get_engine_version()
        metrics = generate_benchmark(state_path, engine_version)

        if metrics["total_projects"] == 0:
            return {
                "status": "no_data",
                "message": "No projects found in state. Nothing to benchmark.",
                "generated_at": metrics["generated_at"],
            }

        markdown = render_benchmark_markdown(metrics)

        # Determine output path (AC-62)
        if output_path:
            out = Path(output_path)
        else:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            benchmarks_dir = engine_path / "docs" / "benchmarks"
            benchmarks_dir.mkdir(parents=True, exist_ok=True)
            out = benchmarks_dir / f"snapshot_{date_str}.md"

        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")

        return {
            "status": "ok",
            "file": str(out),
            "total_projects": metrics["total_projects"],
            "total_ucs": metrics["total_ucs"],
            "coverage_avg": metrics["coverage_avg"],
            "healing_resolution_rate": metrics["healing_resolution_rate"],
            "acceptance_rate": metrics["acceptance_rate"],
            "avg_time_per_uc_hours": metrics["avg_time_per_uc_hours"],
            "delta_count_avg": metrics["delta_count_avg"],
            "generated_at": metrics["generated_at"],
            "engine_version": engine_version,
        }
