"""Tests for benchmark generation (US-05: Benchmarking Público con Datos Reales).

Covers:
- AC-59: Metric aggregation (total UCs, coverage, healing, acceptance, time, delta)
- AC-60: Project name anonymization and generic stack categories
- AC-61: Markdown rendering with Metodología section
- AC-62: File output path
- AC-63/65/66: REST endpoint behavior (via generate_benchmark directly)
"""

import json
from pathlib import Path

import pytest

from src.benchmark_generator import (
    anonymize_project_name,
    generate_benchmark,
    render_benchmark_markdown,
    _categorize_stack,
)


# ---------------------------------------------------------------------------
# Helpers to create sample state data
# ---------------------------------------------------------------------------

def _create_project(
    state_path: Path,
    name: str,
    stack: str = "flutter",
    *,
    sessions: list[dict] | None = None,
    healing: list[dict] | None = None,
    validations: list[dict] | None = None,
    checkpoints: list[dict] | None = None,
    meta: dict | None = None,
):
    """Create a project with sample state data under state_path."""
    # registry
    registry_file = state_path / "registry.json"
    if registry_file.exists():
        registry = json.loads(registry_file.read_text())
    else:
        registry = {"projects": {}}

    registry["projects"][name] = {"stack": stack}
    registry_file.write_text(json.dumps(registry))

    # project dir
    proj_dir = state_path / "projects" / name
    proj_dir.mkdir(parents=True, exist_ok=True)

    def _write_jsonl(filename: str, records: list[dict]):
        path = proj_dir / filename
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

    if sessions:
        _write_jsonl("sessions.jsonl", sessions)
    if healing:
        _write_jsonl("healing.jsonl", healing)
    if validations:
        _write_jsonl("acceptance_validations.jsonl", validations)
    if checkpoints:
        _write_jsonl("checkpoints.jsonl", checkpoints)

    if meta:
        (proj_dir / "meta.json").write_text(json.dumps(meta))


# ---------------------------------------------------------------------------
# Test anonymize_project_name (AC-60)
# ---------------------------------------------------------------------------

class TestAnonymization:
    def test_first_project(self):
        assert anonymize_project_name(0) == "Proyecto A"

    def test_second_project(self):
        assert anonymize_project_name(1) == "Proyecto B"

    def test_last_single_letter(self):
        assert anonymize_project_name(25) == "Proyecto Z"

    def test_double_letter(self):
        # index 26 → AA
        result = anonymize_project_name(26)
        assert result == "Proyecto AA"

    def test_double_letter_ab(self):
        result = anonymize_project_name(27)
        assert result == "Proyecto AB"


# ---------------------------------------------------------------------------
# Test _categorize_stack (AC-60)
# ---------------------------------------------------------------------------

class TestCategorizeStack:
    def test_flutter(self):
        assert _categorize_stack("flutter") == "Mobile/Desktop (Flutter)"

    def test_react(self):
        assert _categorize_stack("react") == "Web Frontend (React)"

    def test_python(self):
        assert _categorize_stack("python") == "Backend (Python)"

    def test_gas(self):
        assert _categorize_stack("google-apps-script") == "Automation (Apps Script)"

    def test_unknown(self):
        assert _categorize_stack("rust") == "Other"

    def test_case_insensitive(self):
        assert _categorize_stack("Flutter") == "Mobile/Desktop (Flutter)"

    def test_none(self):
        assert _categorize_stack(None) == "Other"


# ---------------------------------------------------------------------------
# Test generate_benchmark (AC-59)
# ---------------------------------------------------------------------------

class TestGenerateBenchmark:
    def test_empty_state(self, tmp_path):
        """No projects → zero metrics."""
        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["total_projects"] == 0
        assert metrics["total_ucs"] == 0
        assert metrics["engine_version"] == "4.2.0"
        assert "generated_at" in metrics

    def test_single_project_basic(self, tmp_path):
        """One project with sessions and healing."""
        _create_project(
            tmp_path, "proj-alpha", "flutter",
            sessions=[
                {"timestamp": "2026-03-10T10:00:00Z", "delta_count": 5},
                {"timestamp": "2026-03-11T10:00:00Z", "delta_count": 3},
            ],
            healing=[
                {"timestamp": "2026-03-10T10:00:00Z", "result": "resolved"},
                {"timestamp": "2026-03-10T11:00:00Z", "result": "failed"},
            ],
            validations=[
                {"timestamp": "2026-03-10T10:00:00Z", "verdict": "ACCEPTED"},
                {"timestamp": "2026-03-10T11:00:00Z", "verdict": "REJECTED"},
            ],
            meta={"uc_count": 5, "coverage": 85.0},
        )

        metrics = generate_benchmark(tmp_path, "4.2.0")

        assert metrics["total_projects"] == 1
        assert metrics["total_ucs"] == 5
        assert metrics["coverage_avg"] == 85.0
        assert metrics["healing_resolution_rate"] == 50.0  # 1/2
        assert metrics["acceptance_rate"] == 50.0  # 1/2
        assert metrics["delta_count_avg"] == 4.0  # (5+3)/2

    def test_multiple_projects(self, tmp_path):
        """Two projects aggregate correctly."""
        _create_project(
            tmp_path, "alpha", "flutter",
            sessions=[{"timestamp": "2026-03-10T10:00:00Z", "delta_count": 10}],
            healing=[{"timestamp": "2026-03-10T10:00:00Z", "result": "resolved"}],
            validations=[{"timestamp": "2026-03-10T10:00:00Z", "verdict": "ACCEPTED"}],
            meta={"uc_count": 3, "coverage": 80.0},
        )
        _create_project(
            tmp_path, "beta", "react",
            sessions=[{"timestamp": "2026-03-10T10:00:00Z", "delta_count": 6}],
            healing=[
                {"timestamp": "2026-03-10T10:00:00Z", "result": "resolved"},
                {"timestamp": "2026-03-10T11:00:00Z", "result": "resolved"},
            ],
            validations=[
                {"timestamp": "2026-03-10T10:00:00Z", "verdict": "ACCEPTED"},
                {"timestamp": "2026-03-10T11:00:00Z", "verdict": "ACCEPTED"},
            ],
            meta={"uc_count": 7, "coverage": 90.0},
        )

        metrics = generate_benchmark(tmp_path, "4.2.0")

        assert metrics["total_projects"] == 2
        assert metrics["total_ucs"] == 10  # 3 + 7
        assert metrics["coverage_avg"] == 85.0  # (80 + 90) / 2
        assert metrics["healing_resolution_rate"] == 100.0  # 3/3
        assert metrics["acceptance_rate"] == 100.0  # 3/3
        assert metrics["delta_count_avg"] == 8.0  # (10 + 6) / 2

    def test_projects_anonymized(self, tmp_path):
        """Project names in output are anonymized (AC-60)."""
        _create_project(tmp_path, "secret-project", "python", meta={"uc_count": 1})

        metrics = generate_benchmark(tmp_path, "4.2.0")
        names = [p["name"] for p in metrics["projects"]]
        assert "secret-project" not in names
        assert names[0] == "Proyecto A"

    def test_stack_categories_generic(self, tmp_path):
        """Stack categories are generic, not specific (AC-60)."""
        _create_project(tmp_path, "myapp", "flutter", meta={"uc_count": 1})

        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["projects"][0]["stack_category"] == "Mobile/Desktop (Flutter)"

    def test_uc_count_from_checkpoints_fallback(self, tmp_path):
        """When meta has no uc_count, count from checkpoints."""
        _create_project(
            tmp_path, "proj", "react",
            checkpoints=[
                {"timestamp": "2026-03-10T10:00:00Z", "uc_id": "UC-001", "phase": "start"},
                {"timestamp": "2026-03-10T11:00:00Z", "uc_id": "UC-001", "phase": "complete"},
                {"timestamp": "2026-03-10T12:00:00Z", "uc_id": "UC-002", "phase": "start"},
            ],
            meta={},  # no uc_count
        )

        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["total_ucs"] == 2  # UC-001 and UC-002

    def test_time_per_uc_from_checkpoints(self, tmp_path):
        """Time per UC calculated from checkpoint timestamps."""
        _create_project(
            tmp_path, "proj", "python",
            checkpoints=[
                {"timestamp": "2026-03-10T10:00:00+00:00", "uc_id": "UC-001", "phase": "start"},
                {"timestamp": "2026-03-10T12:00:00+00:00", "uc_id": "UC-001", "phase": "complete"},
            ],
            meta={"uc_count": 1},
        )

        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["avg_time_per_uc_hours"] == 2.0

    def test_no_coverage_data(self, tmp_path):
        """Projects without coverage data → coverage_avg = 0."""
        _create_project(tmp_path, "proj", "flutter", meta={"uc_count": 1})

        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["coverage_avg"] == 0.0

    def test_missing_project_dir(self, tmp_path):
        """Project in registry but no directory on disk → skipped."""
        registry = {"projects": {"ghost": {"stack": "flutter"}}}
        (tmp_path / "registry.json").write_text(json.dumps(registry))

        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["total_projects"] == 0

    def test_generated_at_and_version(self, tmp_path):
        """Metrics include generated_at and engine_version (AC-65)."""
        metrics = generate_benchmark(tmp_path, "5.0.0")
        assert metrics["engine_version"] == "5.0.0"
        assert "T" in metrics["generated_at"]  # ISO format


# ---------------------------------------------------------------------------
# Test render_benchmark_markdown (AC-61)
# ---------------------------------------------------------------------------

class TestRenderMarkdown:
    def _sample_metrics(self):
        return {
            "total_projects": 2,
            "total_ucs": 10,
            "projects": [
                {
                    "name": "Proyecto A",
                    "stack_category": "Mobile/Desktop (Flutter)",
                    "uc_count": 5,
                    "sessions": 20,
                    "healing_events": 4,
                    "healing_resolved": 3,
                    "healing_rate": 75.0,
                    "validations": 5,
                    "accepted": 4,
                    "acceptance_rate": 80.0,
                    "coverage": 85.0,
                },
                {
                    "name": "Proyecto B",
                    "stack_category": "Web Frontend (React)",
                    "uc_count": 5,
                    "sessions": 15,
                    "healing_events": 2,
                    "healing_resolved": 2,
                    "healing_rate": 100.0,
                    "validations": 5,
                    "accepted": 5,
                    "acceptance_rate": 100.0,
                    "coverage": None,
                },
            ],
            "coverage_avg": 85.0,
            "healing_resolution_rate": 83.3,
            "acceptance_rate": 90.0,
            "avg_time_per_uc_hours": 3.5,
            "delta_count_avg": 8.2,
            "generated_at": "2026-03-13T12:00:00+00:00",
            "engine_version": "4.2.0",
        }

    def test_contains_title(self):
        md = render_benchmark_markdown(self._sample_metrics())
        assert "# SpecBox Engine" in md
        assert "Benchmark Snapshot" in md

    def test_contains_summary_table(self):
        md = render_benchmark_markdown(self._sample_metrics())
        assert "Resumen Agregado" in md
        assert "Total Use Cases" in md
        assert "10" in md

    def test_contains_project_table(self):
        md = render_benchmark_markdown(self._sample_metrics())
        assert "Proyecto A" in md
        assert "Proyecto B" in md
        assert "Mobile/Desktop (Flutter)" in md

    def test_contains_metodologia(self):
        """AC-61: Must have Metodología section."""
        md = render_benchmark_markdown(self._sample_metrics())
        assert "## Metodología" in md
        assert "Tasa de resolución healing" in md
        assert "Anonimización" in md

    def test_coverage_na_for_none(self):
        md = render_benchmark_markdown(self._sample_metrics())
        assert "N/A" in md  # Proyecto B has no coverage

    def test_engine_version_in_footer(self):
        md = render_benchmark_markdown(self._sample_metrics())
        assert "v4.2.0" in md

    def test_empty_projects(self):
        metrics = {
            "total_projects": 0,
            "total_ucs": 0,
            "projects": [],
            "coverage_avg": 0.0,
            "healing_resolution_rate": 0.0,
            "acceptance_rate": 0.0,
            "avg_time_per_uc_hours": 0.0,
            "delta_count_avg": 0.0,
            "generated_at": "2026-03-13T12:00:00+00:00",
            "engine_version": "4.2.0",
        }
        md = render_benchmark_markdown(metrics)
        assert "Resumen Agregado" in md
        # No project detail table when empty
        assert "Detalle por Proyecto" not in md


# ---------------------------------------------------------------------------
# Test snapshot file generation (AC-62)
# ---------------------------------------------------------------------------

class TestSnapshotFile:
    def test_generates_file(self, tmp_path):
        """generate_benchmark_snapshot writes file to disk."""
        # We test the generator + markdown render directly since the MCP tool
        # wraps them with path logic
        _create_project(tmp_path, "proj", "flutter", meta={"uc_count": 3})

        metrics = generate_benchmark(tmp_path, "4.2.0")
        md = render_benchmark_markdown(metrics)

        out = tmp_path / "docs" / "benchmarks" / "snapshot_2026-03-13.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")

        assert out.exists()
        content = out.read_text()
        assert "Benchmark Snapshot" in content
        assert "Proyecto A" in content


# ---------------------------------------------------------------------------
# Test 404 behavior for REST endpoint (AC-66)
# ---------------------------------------------------------------------------

class TestBenchmarkPublicEndpoint:
    def test_no_data_returns_empty(self, tmp_path):
        """When no projects exist, generate_benchmark returns total_projects=0 (→ 404 at API)."""
        metrics = generate_benchmark(tmp_path, "4.2.0")
        assert metrics["total_projects"] == 0
