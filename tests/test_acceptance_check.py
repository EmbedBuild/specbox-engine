"""Tests for server/tools/acceptance.py — US-04 BDD exportable module."""

import json
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers: capture registered tools from register_acceptance_tools
# ---------------------------------------------------------------------------

def _register_tools(engine_path: Path, state_path: Path) -> dict:
    """Register acceptance tools on a mock MCP and return them as a dict."""
    from src.tools.acceptance import register_acceptance_tools

    mcp = MagicMock()
    tools: dict = {}

    def capture_tool(fn=None):
        if fn is None:
            return capture_tool
        tools[fn.__name__] = fn
        return fn

    mcp.tool = capture_tool
    register_acceptance_tools(mcp, engine_path, state_path)
    return tools


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project with a PRD containing AC definitions."""
    proj = tmp_path / "my_project"
    proj.mkdir()

    # PRD with US-01, UC-001, and 3 AC
    prd_dir = proj / "doc" / "prd"
    prd_dir.mkdir(parents=True)
    prd_content = textwrap.dedent("""\
        # PRD: Test Feature

        ## User Stories

        ### US-01: Authentication

        #### UC-001: Login with email

        ##### Acceptance Criteria
        - AC-01: Validates email format before submission
        - AC-02: Shows error message on invalid credentials
        - AC-03: Redirects to dashboard after successful login

        #### UC-002: Registration

        ##### Acceptance Criteria
        - AC-04: Validates password strength
        - AC-05: Sends confirmation email
    """)
    (prd_dir / "test-feature.md").write_text(prd_content)

    # Source file referencing AC-01
    src_dir = proj / "src"
    src_dir.mkdir()
    (src_dir / "auth.py").write_text(
        "# Implementation for AC-01\n"
        "def validate_email(email: str) -> bool:\n"
        "    return '@' in email\n"
    )

    # Test file referencing AC-01
    test_dir = proj / "tests"
    test_dir.mkdir()
    (test_dir / "test_auth.py").write_text(
        "# Test for AC-01\n"
        "def test_validate_email():\n"
        "    from src.auth import validate_email\n"
        "    assert validate_email('test@example.com')\n"
    )

    # Git init so _get_git_info works
    os.system(f"cd {proj} && git init -q && git add -A && git commit -q -m 'init'")

    return proj


@pytest.fixture
def state_dir(tmp_path):
    """Temporary state directory."""
    s = tmp_path / "state"
    s.mkdir()
    return s


@pytest.fixture
def tools(project_dir, state_dir):
    """Registered acceptance tools."""
    return _register_tools(project_dir, state_dir)


# ---------------------------------------------------------------------------
# Tests: run_acceptance_check
# ---------------------------------------------------------------------------

class TestRunAcceptanceCheck:

    def test_returns_error_for_nonexistent_path(self, tools):
        result = tools["run_acceptance_check"]("/nonexistent/path", "UC-001")
        assert "error" in result

    def test_returns_error_when_no_prd(self, tmp_path, state_dir):
        """Project with no PRD files should return an error."""
        proj = tmp_path / "empty_proj"
        proj.mkdir()
        t = _register_tools(proj, state_dir)
        result = t["run_acceptance_check"](str(proj), "UC-001")
        assert "error" in result
        assert "No PRD" in result["error"]

    def test_extracts_ac_for_uc(self, tools, project_dir):
        """AC-44/AC-45: Accepts UC-id and locates PRD, extracts AC."""
        result = tools["run_acceptance_check"](str(project_dir), "UC-001")
        assert "error" not in result
        assert result["total_criteria"] == 3
        # Should have AC-01, AC-02, AC-03
        criteria = result["uc_results"][0]["criteria"]
        ac_ids = {c["ac_id"] for c in criteria}
        assert ac_ids == {"AC-01", "AC-02", "AC-03"}

    def test_accepts_us_id(self, tools, project_dir):
        """AC-44: Accepts US-id and finds all UCs under it."""
        result = tools["run_acceptance_check"](str(project_dir), "US-01")
        assert "error" not in result
        # Should find UC-001 and UC-002 under US-01
        uc_ids = [r["uc_id"] for r in result["uc_results"]]
        assert "UC-001" in uc_ids
        assert "UC-002" in uc_ids

    def test_generates_feature_files(self, tools, project_dir):
        """AC-46: .feature files generated in .quality/acceptance-check/{uc-id}/."""
        result = tools["run_acceptance_check"](str(project_dir), "UC-001")
        features = result.get("features_generated", [])
        assert len(features) == 3
        for feat_path in features:
            full_path = project_dir / feat_path
            assert full_path.exists(), f"Feature file not created: {feat_path}"
            content = full_path.read_text()
            assert "Caracteristica:" in content
            assert "@acceptance" in content

    def test_verdict_with_evidence(self, tools, project_dir):
        """AC-47: Verdict ACCEPTED when code + tests exist for an AC."""
        result = tools["run_acceptance_check"](str(project_dir), "UC-001")
        criteria = result["uc_results"][0]["criteria"]
        # AC-01 should be ACCEPTED (code + test reference it)
        ac01 = next(c for c in criteria if c["ac_id"] == "AC-01")
        assert ac01["verdict"] == "ACCEPTED"
        assert len(ac01["evidence"]) > 0

    def test_verdict_rejected_no_evidence(self, tools, project_dir):
        """AC-47: Verdict REJECTED when no evidence found."""
        result = tools["run_acceptance_check"](str(project_dir), "UC-001")
        criteria = result["uc_results"][0]["criteria"]
        # AC-02 and AC-03 have no code references
        ac02 = next(c for c in criteria if c["ac_id"] == "AC-02")
        assert ac02["verdict"] in ("REJECTED", "CONDITIONAL")

    def test_markdown_report_generated(self, tools, project_dir):
        """AC-48: Result formatted as PR-comment-ready Markdown."""
        tools["run_acceptance_check"](str(project_dir), "UC-001")
        report_md = project_dir / ".quality" / "acceptance-check" / "UC-001" / "report.md"
        assert report_md.exists()
        content = report_md.read_text()
        assert "## Acceptance Check: UC-001" in content
        assert "**Verdict**:" in content
        assert "| AC |" in content
        assert "SDD-JPS Engine" in content

    def test_json_report_generated(self, tools, project_dir):
        """AC-47: JSON report with verdict and evidence per AC."""
        tools["run_acceptance_check"](str(project_dir), "UC-001")
        report_json = project_dir / ".quality" / "acceptance-check" / "UC-001" / "report.json"
        assert report_json.exists()
        data = json.loads(report_json.read_text())
        assert data["uc_id"] == "UC-001"
        assert data["verdict"] in ("ACCEPTED", "CONDITIONAL", "REJECTED")
        assert len(data["criteria"]) == 3

    def test_overall_verdict_across_ucs(self, tools, project_dir):
        """Overall verdict reflects worst case across UCs."""
        result = tools["run_acceptance_check"](str(project_dir), "US-01")
        assert result["verdict"] in ("ACCEPTED", "CONDITIONAL", "REJECTED")
        assert result["total_criteria"] == 5  # 3 from UC-001 + 2 from UC-002

    def test_log_written(self, tools, project_dir):
        """AC-52: Logs each execution in .quality/logs/."""
        tools["run_acceptance_check"](str(project_dir), "UC-001")
        log_file = project_dir / ".quality" / "logs" / "acceptance-check.jsonl"
        assert log_file.exists()
        entries = [json.loads(line) for line in log_file.read_text().strip().splitlines()]
        assert len(entries) >= 1
        assert entries[0]["uc_id"] == "UC-001"
        assert entries[0]["verdict"] in ("ACCEPTED", "CONDITIONAL", "REJECTED")

    def test_no_ac_returns_descriptive_error(self, tmp_path, state_dir):
        """AC-53: Descriptive error if UC has no AC defined."""
        proj = tmp_path / "proj_no_ac"
        proj.mkdir()
        prd_dir = proj / "doc" / "prd"
        prd_dir.mkdir(parents=True)
        (prd_dir / "empty.md").write_text("# PRD\n\n## UC-099: Empty UC\n\nNo criteria here.\n")

        t = _register_tools(proj, state_dir)
        result = t["run_acceptance_check"](str(proj), "UC-099")
        # Should have error for this UC
        uc_result = result["uc_results"][0]
        assert uc_result["verdict"] == "REJECTED"
        assert "No acceptance criteria" in uc_result.get("error", "")

    def test_branch_parameter(self, tools, project_dir):
        """AC-49/AC-50: Branch parameter accepted and used."""
        result = tools["run_acceptance_check"](str(project_dir), "UC-001", "feature/test")
        assert result["branch"] == "feature/test"

    def test_ambiguous_item_id(self, tools, project_dir):
        """Ambiguous numeric-only item_id returns helpful error."""
        result = tools["run_acceptance_check"](str(project_dir), "001")
        assert "error" in result
        assert "Ambiguous" in result["error"]


# ---------------------------------------------------------------------------
# Tests: get_acceptance_report
# ---------------------------------------------------------------------------

class TestGetAcceptanceReport:

    def test_no_report_returns_error(self, tools, project_dir):
        """Returns descriptive error when no report exists."""
        result = tools["get_acceptance_report"](str(project_dir), "UC-999")
        assert "error" in result
        assert "No acceptance report" in result["error"]

    def test_returns_report_after_check(self, tools, project_dir):
        """AC-51: Returns last report for a UC after run_acceptance_check."""
        tools["run_acceptance_check"](str(project_dir), "UC-001")
        result = tools["get_acceptance_report"](str(project_dir), "UC-001")
        assert "error" not in result
        assert result["uc_id"] == "UC-001"
        assert result["verdict"] in ("ACCEPTED", "CONDITIONAL", "REJECTED")
        assert "markdown_content" in result

    def test_case_insensitive_uc_id(self, tools, project_dir):
        """UC id lookup is case-insensitive."""
        tools["run_acceptance_check"](str(project_dir), "UC-001")
        result = tools["get_acceptance_report"](str(project_dir), "uc-001")
        assert "error" not in result
        assert result["uc_id"] == "UC-001"

    def test_nonexistent_project(self, tools):
        """Returns error for non-existent project path."""
        result = tools["get_acceptance_report"]("/nonexistent", "UC-001")
        assert "error" in result

    def test_lists_available_reports(self, tools, project_dir):
        """When report not found, lists available reports."""
        tools["run_acceptance_check"](str(project_dir), "UC-001")
        result = tools["get_acceptance_report"](str(project_dir), "UC-999")
        assert "error" in result
        assert "UC-001" in result.get("available_reports", [])


# ---------------------------------------------------------------------------
# Tests: Tool registration
# ---------------------------------------------------------------------------

class TestToolRegistration:

    def test_registers_two_tools(self, project_dir, state_dir):
        """Exactly 2 tools registered."""
        tools = _register_tools(project_dir, state_dir)
        assert len(tools) == 2

    def test_tool_names(self, project_dir, state_dir):
        tools = _register_tools(project_dir, state_dir)
        assert "run_acceptance_check" in tools
        assert "get_acceptance_report" in tools
