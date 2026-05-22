"""Tests for UC-405 regenerate_evidence (AC-14 / AC-15 / AC-16)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.tools.evidence_regen import (
    _scan_ucs_with_evidence,
    regenerate_evidence_impl,
    register_evidence_regen_tools,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_results(project: Path, feature: str, uc_id: str, n_acs: int, timestamp: str):
    """Create .quality/evidence/{feature}/acceptance/results.json."""
    acc_dir = project / ".quality" / "evidence" / feature / "acceptance"
    acc_dir.mkdir(parents=True, exist_ok=True)
    results = [{"id": f"AC-{i:02d}", "scenario": f"scenario {i}", "status": "PASS"} for i in range(1, n_acs + 1)]
    payload = {
        "feature": feature,
        "uc_id": uc_id,
        "us_id": "US-99",
        "timestamp": timestamp,
        "source": "pytest-bdd",
        "stack": "python",
        "evidence_type": "response-log",
        "tests_total": n_acs,
        "tests_passed": n_acs,
        "tests_failed": 0,
        "results": results,
    }
    path = acc_dir / "results.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def project_with_evidence(tmp_path):
    """A project with two prior evidence files (UC-901, UC-902)."""
    old_ts = "2020-01-01T00:00:00+00:00"
    _write_results(tmp_path, "featA", "UC-901", n_acs=2, timestamp=old_ts)
    _write_results(tmp_path, "featB", "UC-902", n_acs=3, timestamp=old_ts)
    return tmp_path


def _make_runner(verdict_by_uc: dict[str, str], rewrite_ts: str):
    """Build a fake acceptance_runner that rewrites results.json + returns a verdict."""

    def runner(project_path: str, uc_id: str, branch: str) -> dict:
        # Rewrite the matching results.json with a fresh timestamp.
        evidence_base = Path(project_path) / ".quality" / "evidence"
        for feature_dir in evidence_base.iterdir():
            rj = feature_dir / "acceptance" / "results.json"
            if not rj.is_file():
                continue
            data = json.loads(rj.read_text())
            if data.get("uc_id", "").upper() == uc_id.upper():
                data["timestamp"] = rewrite_ts
                rj.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"verdict": verdict_by_uc.get(uc_id.upper(), "ACCEPTED")}

    return runner


# ---------------------------------------------------------------------------
# _scan_ucs_with_evidence
# ---------------------------------------------------------------------------


class TestScan:
    def test_finds_both_ucs(self, project_with_evidence):
        found = _scan_ucs_with_evidence(str(project_with_evidence))
        assert set(found) == {"UC-901", "UC-902"}
        assert found["UC-901"]["feature"] == "featA"
        assert found["UC-901"]["n_acs"] == 2
        assert found["UC-902"]["n_acs"] == 3

    def test_empty_when_no_evidence(self, tmp_path):
        assert _scan_ucs_with_evidence(str(tmp_path)) == {}

    def test_ignores_malformed_json(self, tmp_path):
        acc = tmp_path / ".quality" / "evidence" / "bad" / "acceptance"
        acc.mkdir(parents=True)
        (acc / "results.json").write_text("{not json", encoding="utf-8")
        assert _scan_ucs_with_evidence(str(tmp_path)) == {}


# ---------------------------------------------------------------------------
# AC-14 — re-runs acceptance, results.json gets a fresh timestamp
# ---------------------------------------------------------------------------


class TestAC14:
    def test_both_results_have_fresh_timestamp(self, project_with_evidence):
        start = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
        fresh_ts = "2026-05-22T12:00:30+00:00"
        runner = _make_runner({"UC-901": "ACCEPTED", "UC-902": "ACCEPTED"}, fresh_ts)

        result = regenerate_evidence_impl(
            str(project_with_evidence),
            acceptance_runner=runner,
            now=lambda: start,
        )

        assert result["total"] == 2
        # Each processed UC has a results.json timestamp posterior to start.
        for feature in ("featA", "featB"):
            rj = project_with_evidence / ".quality" / "evidence" / feature / "acceptance" / "results.json"
            ts = datetime.fromisoformat(json.loads(rj.read_text())["timestamp"])
            assert ts >= start

    def test_requires_runner(self, project_with_evidence):
        result = regenerate_evidence_impl(str(project_with_evidence), acceptance_runner=None)
        assert "error" in result
        assert result["total"] == 0

    def test_ucs_filter(self, project_with_evidence):
        runner = _make_runner({"UC-901": "ACCEPTED"}, "2026-05-22T12:00:30+00:00")
        result = regenerate_evidence_impl(
            str(project_with_evidence),
            ucs=["UC-901"],
            acceptance_runner=runner,
            now=lambda: datetime(2026, 5, 22, tzinfo=timezone.utc),
        )
        assert result["total"] == 1
        assert result["summary"]["regenerated"] == ["UC-901"]
        assert "UC-902" not in result["progress_lines"][0]


# ---------------------------------------------------------------------------
# AC-15 — progress lines + summary buckets
# ---------------------------------------------------------------------------


class TestAC15:
    def test_progress_format_and_buckets(self, project_with_evidence):
        # Add a third UC that the runner will SKIP (raises).
        _write_results(project_with_evidence, "featC", "UC-903", n_acs=1, timestamp="2020-01-01T00:00:00+00:00")

        def runner(project_path, uc_id, branch):
            if uc_id.upper() == "UC-901":
                return {"verdict": "ACCEPTED"}
            if uc_id.upper() == "UC-902":
                return {"verdict": "REJECTED"}
            raise RuntimeError("no PRD found")  # UC-903 → SKIP

        result = regenerate_evidence_impl(
            str(project_with_evidence),
            acceptance_runner=runner,
            now=lambda: datetime(2026, 5, 22, tzinfo=timezone.utc),
        )

        assert result["total"] == 3
        lines = result["progress_lines"]
        assert lines[0] == "[1/3] UC-901: PASS (2 ACs con evidencia)"
        assert lines[1] == "[2/3] UC-902: FAIL (3 ACs con evidencia)"
        assert lines[2] == "[3/3] UC-903: SKIP (1 ACs con evidencia)"

        summary = result["summary"]
        assert summary["regenerated"] == ["UC-901"]
        assert summary["failed"] == ["UC-902"]
        assert summary["pending"] == ["UC-903"]

    def test_conditional_is_fail(self, project_with_evidence):
        runner = _make_runner(
            {"UC-901": "CONDITIONAL", "UC-902": "ACCEPTED"},
            "2026-05-22T12:00:30+00:00",
        )
        result = regenerate_evidence_impl(
            str(project_with_evidence),
            acceptance_runner=runner,
            now=lambda: datetime(2026, 5, 22, tzinfo=timezone.utc),
        )
        assert result["summary"]["failed"] == ["UC-901"]
        assert result["summary"]["regenerated"] == ["UC-902"]

    def test_runner_returns_error_is_skip(self, project_with_evidence):
        def runner(project_path, uc_id, branch):
            return {"error": "No PRD files found"}

        result = regenerate_evidence_impl(
            str(project_with_evidence),
            acceptance_runner=runner,
            now=lambda: datetime(2026, 5, 22, tzinfo=timezone.utc),
        )
        assert set(result["summary"]["pending"]) == {"UC-901", "UC-902"}


# ---------------------------------------------------------------------------
# AC-16 — Markdown report persisted with one line per UC
# ---------------------------------------------------------------------------


class TestAC16:
    def test_report_written_with_line_per_uc(self, project_with_evidence):
        runner = _make_runner(
            {"UC-901": "ACCEPTED", "UC-902": "REJECTED"},
            "2026-05-22T12:00:30+00:00",
        )
        result = regenerate_evidence_impl(
            str(project_with_evidence),
            acceptance_runner=runner,
            now=lambda: datetime(2026, 5, 22, 9, 30, 0, tzinfo=timezone.utc),
        )

        report_path = Path(result["report_path"])
        assert report_path.exists()
        assert report_path.parent == project_with_evidence / "doc" / "migrations"
        assert report_path.name == "evidence_regeneration_20260522T093000Z.md"

        content = report_path.read_text()
        # One detail line per processed UC.
        assert "UC-901: PASS (2 ACs con evidencia)" in content
        assert "UC-902: FAIL (3 ACs con evidencia)" in content
        assert "Regenerados (PASS): 1" in content
        assert "Fallidos (FAIL): 1" in content

    def test_creates_migrations_dir(self, project_with_evidence):
        assert not (project_with_evidence / "doc" / "migrations").exists()
        runner = _make_runner({"UC-901": "ACCEPTED", "UC-902": "ACCEPTED"}, "2026-05-22T12:00:30+00:00")
        regenerate_evidence_impl(
            str(project_with_evidence),
            acceptance_runner=runner,
            now=lambda: datetime(2026, 5, 22, tzinfo=timezone.utc),
        )
        assert (project_with_evidence / "doc" / "migrations").is_dir()


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_registers_tool(self, tmp_path):
        registered = {}

        class FakeMCP:
            def tool(self, fn):
                registered[fn.__name__] = fn
                return fn

        register_evidence_regen_tools(FakeMCP(), tmp_path, tmp_path)
        assert "regenerate_evidence" in registered
