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
    def generate_benchmark_snapshot() -> dict:
        """Generate a public benchmark snapshot from Sala de Máquinas state data.

        **v6.0.1 — content-passing API**

        Aggregates metrics across all projects (host-side state, not client
        filesystem). Project names are anonymized. The tool returns the
        Markdown content; the client is responsible for writing it (typically
        under ``docs/benchmarks/snapshot_<YYYY-MM-DD>.md``).

        Returns:
            ``{"status": "ok" | "no_data", "markdown_content": str,
            "suggested_filename": "snapshot_<date>.md", ...metrics}``.
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
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        return {
            "status": "ok",
            "markdown_content": markdown,
            "suggested_filename": f"snapshot_{date_str}.md",
            "suggested_relpath": f"docs/benchmarks/snapshot_{date_str}.md",
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
