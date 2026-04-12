"""Tests for the Quality Audit module (ISO/IEC 25010 v1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.audit.schema import (
    AUDIT_SCHEMA_VERSION,
    CharacteristicResult,
    Finding,
    QualityReport,
    Recommendation,
    Severity,
    SquareCharacteristic,
    ToolUsage,
    TrafficLight,
    new_audit_id,
    now_iso,
)
from server.audit.scoring import (
    GREEN_MIN,
    AMBER_MIN,
    clamp,
    global_score,
    maintainability_score,
    score_from_findings,
    traffic_light,
)
from server.audit.tool_runner import run_tool, which
from server.audit.tool_check import audit_tools_catalog, check_audit_tools
from server.audit.reporters import load_brand, write_json_report, write_pdf_report
from server.audit.orchestrator import run_audit
from server.audit.signals import fetch_specbox_signals


# ---------- schema ----------

def _sample_report() -> QualityReport:
    chars = []
    for idx, c in enumerate(SquareCharacteristic):
        chars.append(CharacteristicResult(
            characteristic=c,
            score=70.0 + idx,
            traffic_light=TrafficLight.AMBER,
            justification=f"{c.value} sample",
            raw_metrics={"k": idx},
            findings=[
                Finding(
                    severity=Severity.MEDIUM,
                    description=f"sample finding {idx}",
                    remediation="fix it",
                    file="foo.py",
                    line=idx + 1,
                )
            ],
            recommendations=[
                Recommendation(
                    priority=Severity.MEDIUM,
                    action="do the thing",
                    rationale="because",
                    finding_ref="sample",
                )
            ],
            breakdown={
                "classic_60": {"score": 80, "weight": 0.6, "contribution": 48},
                "specbox_40": {"score": 60, "weight": 0.4, "contribution": 24},
                "formula": "0.60 * classic + 0.40 * specbox",
            } if c == SquareCharacteristic.MAINTAINABILITY else None,
        ))
    return QualityReport(
        audit_id=new_audit_id(),
        project="test-project",
        project_path="/tmp/test",
        commit="abc123",
        generated_at=now_iso(),
        stack={"detected": "python", "analyzers_run": [c.value for c in SquareCharacteristic], "analyzers_skipped": []},
        global_score=72.5,
        global_traffic_light=TrafficLight.AMBER,
        characteristics=chars,
        tools_used=[ToolUsage(name="semgrep", status="missing", message="not installed")],
        meta={"duration_ms": 1234, "warnings": ["test warning"]},
    )


def test_schema_round_trip():
    original = _sample_report()
    as_dict = original.to_dict()
    assert as_dict["audit_schema_version"] == AUDIT_SCHEMA_VERSION
    assert len(as_dict["characteristics"]) == 8
    restored = QualityReport.from_dict(as_dict)
    assert restored.project == original.project
    assert restored.global_score == original.global_score
    assert len(restored.characteristics) == 8
    # breakdown preserved on maintainability
    maint = next(c for c in restored.characteristics if c.characteristic == SquareCharacteristic.MAINTAINABILITY)
    assert maint.breakdown is not None
    assert maint.breakdown["classic_60"]["weight"] == 0.6


# ---------- scoring ----------

def test_traffic_light_thresholds():
    assert traffic_light(GREEN_MIN) == TrafficLight.GREEN
    assert traffic_light(GREEN_MIN - 0.1) == TrafficLight.AMBER
    assert traffic_light(AMBER_MIN) == TrafficLight.AMBER
    assert traffic_light(AMBER_MIN - 0.1) == TrafficLight.RED
    assert traffic_light(0) == TrafficLight.RED
    assert traffic_light(100) == TrafficLight.GREEN


def test_clamp():
    assert clamp(-5) == 0.0
    assert clamp(150) == 100.0
    assert clamp(42.7) == 42.7


def test_score_from_findings_penalties():
    findings = [
        Finding(severity=Severity.CRITICAL, description="x", remediation="y"),
        Finding(severity=Severity.LOW, description="x", remediation="y"),
    ]
    s = score_from_findings(findings, base=100.0)
    assert s == 100.0 - 25.0 - 2.0
    # Floor at 0
    many = [Finding(severity=Severity.CRITICAL, description="x", remediation="y") for _ in range(20)]
    assert score_from_findings(many, base=100.0) == 0.0


def test_maintainability_mix_60_40():
    final, bd = maintainability_score(80.0, 60.0)
    assert final == pytest.approx(0.6 * 80 + 0.4 * 60)
    assert bd["classic_60"]["weight"] == 0.60
    assert bd["specbox_40"]["weight"] == 0.40
    assert bd["classic_60"]["contribution"] == pytest.approx(48.0)
    assert bd["specbox_40"]["contribution"] == pytest.approx(24.0)
    assert "formula" in bd


def test_global_score_ignores_skipped():
    results = []
    for i, c in enumerate(list(SquareCharacteristic)[:3]):
        results.append(CharacteristicResult(
            characteristic=c,
            score=60.0 + i * 10,
            traffic_light=TrafficLight.AMBER,
            skipped=(i == 2),
            skipped_reason="test" if i == 2 else None,
        ))
    g = global_score(results)
    assert g == pytest.approx((60.0 + 70.0) / 2)


# ---------- tool_runner ----------

def test_tool_runner_missing_binary():
    res = run_tool(["definitely-not-a-real-binary-xyz-123"], timeout=2.0)
    assert not res.available
    assert res.tool == "definitely-not-a-real-binary-xyz-123"
    usage = res.to_usage()
    assert usage.status == "missing"


def test_tool_runner_runs_echo():
    if which("echo") is None:
        pytest.skip("echo not available")
    res = run_tool(["echo", "hello"], timeout=5.0)
    assert res.available
    assert res.returncode == 0
    assert "hello" in res.stdout


# ---------- tool_check ----------

def test_audit_tools_catalog_has_expected_entries():
    catalog = audit_tools_catalog()
    names = {t.name for t in catalog}
    assert {"semgrep", "gitleaks", "pip-audit", "lizard"}.issubset(names)
    # Every entry has a non-empty installer
    for tool in catalog:
        assert tool.installer
        assert tool.purpose


def test_check_audit_tools_reports_missing():
    status = check_audit_tools(stack=None)
    assert "all_present" in status
    assert "installed" in status
    assert "missing" in status
    assert "install_commands" in status
    assert status["installed_count"] + status["missing_count"] == (
        len(status["installed"]) + len(status["missing"])
    )
    # Every missing tool has an install command
    assert len(status["install_commands"]) == status["missing_count"]


def test_check_audit_tools_filters_by_stack():
    # When stack='python', npm (which has stack_hint='react') is excluded
    py_status = check_audit_tools(stack="python")
    py_tools = {t["name"] if isinstance(t, dict) else t.name
                for t in py_status["installed"] + py_status["missing"]}
    assert "npm" not in py_tools
    # pip-audit is python-relevant and should appear
    assert "pip-audit" in py_tools


def test_install_script_exists_and_executable():
    script = Path(__file__).resolve().parent.parent / ".quality" / "scripts" / "install-audit-tools.sh"
    assert script.exists(), f"install script missing: {script}"
    assert script.stat().st_mode & 0o111, "install script not executable"


# ---------- brand loader fallback ----------

def test_brand_loader_fallback():
    brand = load_brand(engine_path=Path("/tmp/nonexistent-engine-xyz"))
    assert brand.primary_color == "#29F3E3"
    assert brand.background_color == "#000000"
    assert brand.source == "fallback"
    assert brand.warning is not None


# ---------- signals ----------

def test_signals_empty_project(tmp_path: Path):
    sig = fetch_specbox_signals(tmp_path, "empty-proj", state_path=None)
    assert sig["ac_status"]["total"] == 0
    assert sig["evidence"]["uc_total"] == 0
    assert sig["healing"]["total_events"] == 0


def test_signals_reads_healing_jsonl(tmp_path: Path):
    evidence = tmp_path / ".quality" / "evidence" / "uc-001"
    evidence.mkdir(parents=True)
    (evidence / "healing.jsonl").write_text(
        json.dumps({"result": "resolved", "level": 1}) + "\n"
        + json.dumps({"result": "failed", "level": 2}) + "\n"
        + json.dumps({"result": "resolved", "level": 1}) + "\n",
        encoding="utf-8",
    )
    sig = fetch_specbox_signals(tmp_path, "p", state_path=None)
    assert sig["healing"]["total_events"] == 3
    assert sig["healing"]["resolved"] == 2
    assert sig["healing"]["failed"] == 1
    assert sig["evidence"]["uc_total"] == 1
    assert sig["evidence"]["uc_with_evidence"] == 1


# ---------- orchestrator end-to-end ----------

def _minimal_project(tmp_path: Path) -> Path:
    proj = tmp_path / "sample-proj"
    proj.mkdir()
    (proj / "README.md").write_text("# Sample\n", encoding="utf-8")
    (proj / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    (proj / "pyproject.toml").write_text('[project]\nname = "sample"\n', encoding="utf-8")
    (proj / "uv.lock").write_text("# lockfile\n", encoding="utf-8")
    src = proj / "src"
    src.mkdir()
    (src / "app.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    tests = proj / "tests"
    tests.mkdir()
    (tests / "test_app.py").write_text("def test_hello():\n    assert True\n", encoding="utf-8")
    return proj


def test_orchestrator_runs_all_8_analyzers(tmp_path: Path):
    proj = _minimal_project(tmp_path)

    def stack(_p): return {"stack": "python", "infra": [], "engine_version": "test"}
    def signals(_p, _n): return fetch_specbox_signals(_p, _n, state_path=None)

    report = run_audit(
        project_path=proj,
        project_name="sample-proj",
        detect_stack=stack,
        fetch_specbox_signals=signals,
    )
    assert report.audit_schema_version == "1.0"
    assert len(report.characteristics) == 8
    ids = {c.characteristic.value for c in report.characteristics}
    assert ids == {
        "functional_suitability", "performance_efficiency", "compatibility",
        "usability", "reliability", "security", "maintainability", "portability",
    }
    # Global score is in [0, 100]
    assert 0 <= report.global_score <= 100
    # Maintainability has a breakdown (60/40 mix)
    maint = next(c for c in report.characteristics if c.characteristic == SquareCharacteristic.MAINTAINABILITY)
    assert maint.breakdown is not None
    assert maint.breakdown["classic_60"]["weight"] == 0.60
    assert maint.breakdown["specbox_40"]["weight"] == 0.40
    # Duration recorded
    assert report.meta["duration_ms"] >= 0


def test_orchestrator_scope_filter(tmp_path: Path):
    proj = _minimal_project(tmp_path)

    def stack(_p): return {"stack": "python", "infra": []}
    def signals(_p, _n): return fetch_specbox_signals(_p, _n, state_path=None)

    report = run_audit(
        project_path=proj,
        project_name="sample-proj",
        detect_stack=stack,
        fetch_specbox_signals=signals,
        scope="security",
    )
    active = [c for c in report.characteristics if not c.skipped]
    assert len(active) == 1
    assert active[0].characteristic == SquareCharacteristic.SECURITY


# ---------- reporters end-to-end ----------

def test_json_reporter_writes_valid_file(tmp_path: Path):
    report = _sample_report()
    out = tmp_path / "audit_sample.json"
    write_json_report(report, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["audit_schema_version"] == "1.0"
    assert len(data["characteristics"]) == 8
    # Round-trip via JSON should also work
    restored = QualityReport.from_dict(data)
    assert restored.global_score == report.global_score


def test_pdf_reporter_produces_file(tmp_path: Path):
    report = _sample_report()
    brand = load_brand(engine_path=None)
    out = tmp_path / "audit_sample.pdf"
    write_pdf_report(report, out, brand)
    assert out.exists()
    # Minimal PDF header check
    assert out.read_bytes().startswith(b"%PDF-")
    assert out.stat().st_size > 1000  # not an empty shell
