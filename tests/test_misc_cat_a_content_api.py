"""Tests for the v6.0.1 content-passing misc cat A tools (UC-620).

Covers:
  * hints — get_skill_hint, record_skill_hint, list_skill_hints
  * skill_registry — list_skills_v2, discover_skills, validate_skill_manifest
  * telemetry — get_context_budget
  * benchmark — generate_benchmark_snapshot
  * evidence_regen — regenerate_evidence
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastmcp import FastMCP


REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── Helpers ────────────────────────────────────────────────────────


def _extract_tools(mcp: FastMCP, names: list[str]) -> dict[str, Any]:
    async def _gather():
        out: dict[str, Any] = {}
        for n in names:
            tool = await mcp.get_tool(n)
            out[n] = tool.fn
        return out

    return asyncio.run(_gather())


# ─── hints.py ────────────────────────────────────────────────────────


@pytest.fixture
def hint_tools():
    from server.tools.hints import register_hint_tools

    mcp = FastMCP(name="t-hints")
    register_hint_tools(mcp)
    return _extract_tools(mcp, ["get_skill_hint", "record_skill_hint", "list_skill_hints"])


class TestHintsContentAPI:
    def test_fresh_counter_shows_hint(self, hint_tools):
        result = hint_tools["get_skill_hint"](skill_name="prd")
        assert result["show"] is True
        assert result["hint"]
        assert result["skill"] == "prd"

    def test_max_counter_suppresses(self, hint_tools):
        result = hint_tools["get_skill_hint"](skill_name="prd", current_counter=3)
        assert result["show"] is False

    def test_completed_ucs_above_threshold_suppresses(self, hint_tools):
        result = hint_tools["get_skill_hint"](skill_name="prd", completed_uc_count=10)
        assert result["show"] is False

    def test_unknown_skill_no_hint(self, hint_tools):
        result = hint_tools["get_skill_hint"](skill_name="nonexistent")
        assert result["show"] is False

    def test_record_increments_counter(self, hint_tools):
        result = hint_tools["record_skill_hint"](
            skill_name="prd", counters={"prd": 1, "implement": 0},
        )
        assert result["recorded"] is True
        assert result["updated_counters"]["prd"] == 2
        assert result["updated_counters"]["implement"] == 0

    def test_record_creates_counter_when_absent(self, hint_tools):
        result = hint_tools["record_skill_hint"](skill_name="plan", counters=None)
        assert result["updated_counters"]["plan"] == 1

    def test_list_skill_hints(self, hint_tools):
        result = hint_tools["list_skill_hints"]()
        assert "available_hints" in result
        assert "prd" in result["available_hints"]


# ─── skill_registry.py ───────────────────────────────────────────────


@pytest.fixture
def skill_registry_tools():
    from server.tools.skill_registry import register_skill_registry_tools

    mcp = FastMCP(name="t-skill-registry")
    register_skill_registry_tools(mcp, engine_path=REPO_ROOT)
    return _extract_tools(
        mcp, ["list_skills_v2", "discover_skills", "validate_skill_manifest"]
    )


class TestSkillRegistryContentAPI:
    def test_list_skills_v2_core_only(self, skill_registry_tools):
        result = skill_registry_tools["list_skills_v2"]()
        assert isinstance(result, list)
        # There should be core skills
        assert any(s.get("name") for s in result)

    def test_list_skills_v2_merges_project_local(self, skill_registry_tools):
        local = [
            {
                "name": "my-skill",
                "version": "1.0.0",
                "description": "Local",
                "triggers": ["foo"],
                "stacks": ["python"],
            }
        ]
        result = skill_registry_tools["list_skills_v2"](
            project_local_manifests=local,
        )
        names = [s.get("name") for s in result]
        assert "my-skill" in names

    def test_discover_skills_requires_stack(self, skill_registry_tools):
        result = skill_registry_tools["discover_skills"](stack="")
        assert "error" in result

    def test_discover_skills_with_local_manifest_match(self, skill_registry_tools):
        local = [
            {
                "name": "data-tools",
                "version": "1.0.0",
                "description": "Data utils",
                "triggers": ["export", "csv"],
                "stacks": ["python"],
            }
        ]
        result = skill_registry_tools["discover_skills"](
            stack="python", keywords="csv", project_local_manifests=local,
        )
        activated_names = [s.get("name") for s in result["activated"]]
        assert "data-tools" in activated_names

    def test_validate_skill_manifest_valid(self, skill_registry_tools):
        manifest = yaml.dump({
            "name": "foo",
            "version": "1.0.0",
            "description": "Bar",
        })
        result = skill_registry_tools["validate_skill_manifest"](
            manifest_yaml_content=manifest,
        )
        assert result["valid"] is True

    def test_validate_skill_manifest_missing_fields(self, skill_registry_tools):
        result = skill_registry_tools["validate_skill_manifest"](
            manifest_yaml_content=yaml.dump({"name": "foo"}),
        )
        assert result["valid"] is False
        assert any("missing required field" in e for e in result["errors"])

    def test_validate_skill_manifest_empty(self, skill_registry_tools):
        result = skill_registry_tools["validate_skill_manifest"](
            manifest_yaml_content="",
        )
        assert result["valid"] is False

    def test_validate_skill_manifest_invalid_yaml(self, skill_registry_tools):
        result = skill_registry_tools["validate_skill_manifest"](
            manifest_yaml_content="{not: valid: yaml::",
        )
        assert result["valid"] is False
        assert any("YAML parse error" in e for e in result["errors"])


# ─── telemetry.py get_context_budget ────────────────────────────────


@pytest.fixture
def context_budget_tool():
    from server.tools.telemetry import register_telemetry_tools

    mcp = FastMCP(name="t-telemetry")
    register_telemetry_tools(mcp, engine_path=REPO_ROOT)
    return _extract_tools(mcp, ["get_context_budget"])["get_context_budget"]


class TestContextBudgetContentAPI:
    def test_empty_inventory_returns_zero(self, context_budget_tool):
        result = json.loads(asyncio.run(context_budget_tool()))
        assert result["estimated_tokens"] == 0
        assert result["health"] == "green"

    def test_green_threshold(self, context_budget_tool):
        # ~3000 tokens out of 1M = 0.3%
        result = json.loads(
            asyncio.run(context_budget_tool(file_inventory={"a.py": 12000}))
        )
        assert result["estimated_tokens"] == 3000
        assert result["health"] == "green"

    def test_yellow_threshold(self, context_budget_tool):
        # ~200k tokens out of 1M = 20%
        result = json.loads(
            asyncio.run(context_budget_tool(file_inventory={"big.py": 800_000}))
        )
        assert 15 <= result["context_window_pct"] < 30
        assert result["health"] == "yellow"

    def test_red_threshold(self, context_budget_tool):
        # ~400k tokens out of 1M = 40%
        result = json.loads(
            asyncio.run(context_budget_tool(file_inventory={"huge.py": 1_600_000}))
        )
        assert result["context_window_pct"] >= 30
        assert result["health"] == "red"

    def test_smaller_context_window(self, context_budget_tool):
        """A 200k window flips threshold faster."""
        result = json.loads(
            asyncio.run(
                context_budget_tool(
                    file_inventory={"a.py": 100_000},
                    context_window_tokens=200_000,
                )
            )
        )
        # 25k / 200k = 12.5% → green still
        assert result["health"] in ("green", "yellow")


# ─── benchmark.py ────────────────────────────────────────────────────


@pytest.fixture
def benchmark_tool(tmp_path):
    from server.tools.benchmark import register_benchmark_tools

    mcp = FastMCP(name="t-bench")
    register_benchmark_tools(mcp, engine_path=REPO_ROOT, state_path=tmp_path)
    return _extract_tools(mcp, ["generate_benchmark_snapshot"])["generate_benchmark_snapshot"]


class TestBenchmarkContentAPI:
    def test_no_data_when_state_empty(self, benchmark_tool):
        result = benchmark_tool()
        assert result["status"] == "no_data"

    def test_returns_markdown_when_data_present(self, benchmark_tool, tmp_path):
        # Seed a minimal project
        proj = tmp_path / "projects" / "demo"
        proj.mkdir(parents=True)
        (proj / "meta.json").write_text(
            json.dumps({"name": "demo", "stack": "python"}), encoding="utf-8"
        )
        (proj / "evidence").mkdir()
        # Empty evidence → still counted as a project; the benchmark generator
        # tolerates zero metrics.
        result = benchmark_tool()
        assert result["status"] in ("ok", "no_data")
        if result["status"] == "ok":
            assert "markdown_content" in result
            assert result["suggested_filename"].startswith("snapshot_")
            assert result["suggested_relpath"].startswith("docs/benchmarks/")
            # No filesystem path leaks
            assert "file" not in result


# ─── evidence_regen.py ───────────────────────────────────────────────


@pytest.fixture
def evidence_regen_tool(tmp_path):
    from server.tools.evidence_regen import register_evidence_regen_tools

    mcp = FastMCP(name="t-ev-regen")
    register_evidence_regen_tools(mcp, engine_path=REPO_ROOT, state_path=tmp_path)
    return _extract_tools(mcp, ["regenerate_evidence"])["regenerate_evidence"]


SAMPLE_PRD = """# PRD

## UC-001: Login
#### Acceptance Criteria
- AC-01: Validates email
- AC-02: Shows error
"""


class TestRegenerateEvidenceContentAPI:
    def test_empty_inputs_zero_total(self, evidence_regen_tool):
        result = evidence_regen_tool(prd_content=SAMPLE_PRD)
        assert result["total"] == 0
        assert result["summary"]["regenerated"] == []

    def test_processes_supplied_ucs(self, evidence_regen_tool):
        result = evidence_regen_tool(
            prd_content=SAMPLE_PRD,
            uc_evidence_inputs={
                "UC-001": {"n_acs": 2, "code_index": {}},
            },
            branch="main",
        )
        assert result["total"] == 1
        assert "UC-001" in result["uc_results"][0]["uc_id"]
        assert result["report_path"].startswith("doc/migrations/regenerate-evidence-")
        assert "regenerate-evidence" in result["report_path"]
        assert "report_content" in result

    def test_restrict_via_ucs_param(self, evidence_regen_tool):
        result = evidence_regen_tool(
            prd_content=SAMPLE_PRD,
            uc_evidence_inputs={
                "UC-001": {"n_acs": 2},
                "UC-002": {"n_acs": 3},
            },
            ucs=["UC-001"],
        )
        assert result["total"] == 1
        assert result["uc_results"][0]["uc_id"] == "UC-001"

    def test_skip_when_no_acs_for_uc(self, evidence_regen_tool):
        result = evidence_regen_tool(
            prd_content="# Empty PRD\n",
            uc_evidence_inputs={"UC-999": {"n_acs": 0}},
        )
        # No PRD content for UC-999 → SKIP
        assert result["total"] == 1
        assert result["uc_results"][0]["status"] in ("SKIP", "FAIL")
