"""Tests for the v6.0.1 content-passing acceptance tools (UC-619)."""
from __future__ import annotations

import asyncio
import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP


REPO_ROOT = Path(__file__).resolve().parent.parent


SAMPLE_PRD = textwrap.dedent("""\
    # PRD

    ## US-01: Login

    ### UC-001: Email/password login

    #### Acceptance Criteria
    - AC-01: Validates email format before submission
    - AC-02: Shows error message on invalid credentials
    - AC-03: Redirects to dashboard after successful login

    ### UC-002: Registration

    #### Acceptance Criteria
    - AC-04: Validates password strength
""")


SAMPLE_CODE_INDEX = {
    "src/auth.py": "# AC-01 implementation\ndef validate_email(e): return '@' in e\n",
    "tests/test_auth.py": "# AC-01 test\ndef test_validate_email(): assert validate_email('a@b')\n",
}


@pytest.fixture
def acceptance_tools(tmp_path):
    from server.tools.acceptance import register_acceptance_tools

    mcp = FastMCP(name="test-acceptance")
    register_acceptance_tools(mcp, engine_path=REPO_ROOT, state_path=tmp_path)

    async def _gather():
        out: dict[str, Any] = {}
        for name in ("run_acceptance_check", "get_acceptance_report", "get_e2e_gap_report"):
            tool = await mcp.get_tool(name)
            out[name] = tool.fn
        return out

    return asyncio.run(_gather())


# ─── run_acceptance_check ────────────────────────────────────────────


class TestRunAcceptanceCheckContentAPI:
    def test_happy_path_with_code_index(self, acceptance_tools):
        result = acceptance_tools["run_acceptance_check"](
            prd_content=SAMPLE_PRD,
            item_id="UC-001",
            branch="main",
            code_index=SAMPLE_CODE_INDEX,
        )
        assert "error" not in result
        assert result["verdict"] in ("ACCEPTED", "CONDITIONAL", "REJECTED")
        assert result["total_criteria"] == 3
        # Feature files returned as content
        assert any("AC-01.feature" in k for k in result["feature_files"])
        # Report files for UC
        assert any("UC-001/report.md" in k for k in result["reports"])

    def test_empty_prd_returns_error(self, acceptance_tools):
        result = acceptance_tools["run_acceptance_check"](
            prd_content="",
        )
        assert "error" in result

    def test_us_id_resolves_multiple_ucs(self, acceptance_tools):
        result = acceptance_tools["run_acceptance_check"](
            prd_content=SAMPLE_PRD,
            item_id="US-01",
        )
        uc_ids = [r["uc_id"] for r in result["uc_results"]]
        assert "UC-001" in uc_ids
        assert "UC-002" in uc_ids

    def test_no_code_index_yields_rejected(self, acceptance_tools):
        result = acceptance_tools["run_acceptance_check"](
            prd_content=SAMPLE_PRD,
            item_id="UC-001",
        )
        for c in result["uc_results"][0]["criteria"]:
            assert c["verdict"] == "REJECTED"

    def test_ambiguous_item_id(self, acceptance_tools):
        result = acceptance_tools["run_acceptance_check"](
            prd_content=SAMPLE_PRD,
            item_id="001",
        )
        assert "Ambiguous" in result.get("error", "")

    def test_empty_item_id_finds_all_ucs(self, acceptance_tools):
        result = acceptance_tools["run_acceptance_check"](
            prd_content=SAMPLE_PRD,
            item_id="",
        )
        uc_ids = [r["uc_id"] for r in result["uc_results"]]
        assert "UC-001" in uc_ids
        assert "UC-002" in uc_ids


# ─── get_acceptance_report ───────────────────────────────────────────


class TestGetAcceptanceReportContentAPI:
    def test_with_json_returns_parsed(self, acceptance_tools):
        report = {"uc_id": "UC-001", "verdict": "ACCEPTED", "criteria": []}
        result = acceptance_tools["get_acceptance_report"](
            uc_id="UC-001",
            report_json_content=json.dumps(report),
            report_md_content="## Report MD",
        )
        assert result["uc_id"] == "UC-001"
        assert result["verdict"] == "ACCEPTED"
        assert result["markdown_content"] == "## Report MD"

    def test_no_json_returns_error(self, acceptance_tools):
        result = acceptance_tools["get_acceptance_report"](
            uc_id="UC-001",
        )
        assert "error" in result

    def test_malformed_json_returns_error(self, acceptance_tools):
        result = acceptance_tools["get_acceptance_report"](
            uc_id="UC-001",
            report_json_content="{not valid",
        )
        assert "error" in result


# ─── get_e2e_gap_report ──────────────────────────────────────────────


class TestGetE2EGapReportContentAPI:
    def test_happy_path_no_evidence(self, acceptance_tools):
        result = acceptance_tools["get_e2e_gap_report"](
            prd_content=SAMPLE_PRD,
            project_name="proj",
            stack="python",
        )
        assert result["project"] == "proj"
        assert result["stack"] == "python"
        assert result["coverage"]["total_ucs"] == 2
        assert result["coverage"]["missing"] == 2
        assert result["e2e_plan"] is not None

    def test_with_evidence_marks_covered(self, acceptance_tools):
        evidence_idx = {
            "user_login/acceptance/e2e-evidence-report.html": "<html>UC-001 done</html>",
            "user_login/acceptance/results.json": json.dumps({"uc_id": "UC-001"}),
        }
        result = acceptance_tools["get_e2e_gap_report"](
            prd_content=SAMPLE_PRD,
            project_name="proj",
            stack="react",
            evidence_index=evidence_idx,
        )
        assert result["coverage"]["covered"] == 1
        assert result["coverage"]["missing"] == 1

    def test_unknown_stack_falls_back(self, acceptance_tools):
        result = acceptance_tools["get_e2e_gap_report"](
            prd_content=SAMPLE_PRD,
            stack="unknown",
        )
        if result.get("e2e_plan"):
            assert result["e2e_plan"][0]["framework"] == "Unknown"

    def test_empty_prd_returns_error(self, acceptance_tools):
        result = acceptance_tools["get_e2e_gap_report"](
            prd_content="",
            stack="python",
        )
        assert "error" in result

    def test_feature_file_signals_partial(self, acceptance_tools):
        result = acceptance_tools["get_e2e_gap_report"](
            prd_content=SAMPLE_PRD,
            stack="react",
            feature_files=["tests/acceptance/features/UC-001-login.feature"],
        )
        # UC-001 has a feature file but no evidence ⇒ partial
        uc1 = next(uc for uc in result["uc_results"] if uc["uc_id"] == "UC-001")
        assert uc1["status"] == "partial"
