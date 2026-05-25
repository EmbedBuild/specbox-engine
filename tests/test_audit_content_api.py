"""Tests for the v6.0.1 content-passing audit tools (UC-618)."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP


REPO_ROOT = Path(__file__).resolve().parent.parent


def _build_minimal_report() -> dict:
    """A QualityReport dict that round-trips through schema.from_dict.

    Mirrors the bare minimum the schema accepts. Fields kept loose to
    survive schema evolution; the contract here is content-passing, not
    schema fidelity.
    """
    from server.audit.schema import QualityReport

    # Use the schema's empty constructor if available; otherwise build a
    # mock dict that to_dict / from_dict accepts.
    report = QualityReport.empty(project="t-proj", scope="full")
    return report.to_dict()


@pytest.fixture
def audit_tools(tmp_path):
    from server.tools.audit import register_audit_tools

    mcp = FastMCP(name="t-audit")
    register_audit_tools(mcp, engine_path=REPO_ROOT, state_path=tmp_path)

    async def _gather():
        out: dict[str, Any] = {}
        for n in (
            "check_audit_tools_status",
            "submit_quality_audit",
            "run_quality_audit",
            "attach_audit_evidence",
            "get_last_audit",
        ):
            tool = await mcp.get_tool(n)
            out[n] = tool.fn
        return out

    return asyncio.run(_gather())


class TestCheckAuditToolsStatus:
    def test_no_stack(self, audit_tools):
        result = audit_tools["check_audit_tools_status"]()
        assert "installed" in result or "missing" in result or "all_present" in result

    def test_python_stack(self, audit_tools):
        result = audit_tools["check_audit_tools_status"](stack="python")
        assert isinstance(result, dict)


class TestSubmitQualityAudit:
    def test_invalid_report_returns_error(self, audit_tools):
        result = audit_tools["submit_quality_audit"](
            project="proj-x",
            report={"not": "valid"},
        )
        assert "error" in result

    def test_valid_minimal_report_round_trips(self, audit_tools):
        try:
            payload = _build_minimal_report()
        except (AttributeError, TypeError):
            pytest.skip("QualityReport.empty() not available in this schema version")
        result = audit_tools["submit_quality_audit"](
            project="t-proj",
            report=payload,
        )
        assert "error" not in result
        assert result["project"] == "t-proj"
        assert "audit_tools_status" in result


class TestRunQualityAuditDeprecation:
    def test_no_report_returns_deprecation(self, audit_tools):
        result = audit_tools["run_quality_audit"](
            project="proj-x",
            project_path="/tmp/anything",
        )
        assert "error" in result
        assert "v6.0.1" in result["error"]
        assert result["migration"]["replacement"] == "submit_quality_audit"

    def test_with_report_delegates_to_submit(self, audit_tools):
        try:
            payload = _build_minimal_report()
        except (AttributeError, TypeError):
            pytest.skip("QualityReport.empty() not available")
        result = audit_tools["run_quality_audit"](
            project="t-proj",
            report=payload,
        )
        assert "error" not in result
        assert result["project"] == "t-proj"


class TestGetLastAudit:
    def test_no_meta_returns_error(self, audit_tools):
        result = audit_tools["get_last_audit"](project="nonexistent")
        assert "error" in result
