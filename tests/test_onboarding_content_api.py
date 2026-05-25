"""Tests for the v6.0.1 content-passing onboarding tools (UC-617).

Covers:
  * detect_project_stack — stack detection + infra detection from dep files
  * get_onboarding_status — artifact presence + registry lookup (host-side)
  * get_visual_gap_report — settings parsing + artifact presence checks

The 3 wrappers no longer touch the client filesystem; the caller is
expected to scan the local repo and pass signals as parameters.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP


REPO_ROOT = Path(__file__).resolve().parent.parent


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def onboarding_tools(tmp_path):
    """Extract the registered onboarding MCP tools as raw callables.

    The host-side state_path is pointed at tmp_path so registry lookups
    in get_onboarding_status remain hermetic across test runs.
    """
    from server.tools.onboarding import register_onboarding_tools

    mcp = FastMCP(name="test-onboarding")
    register_onboarding_tools(mcp, engine_path=REPO_ROOT, state_path=tmp_path)

    async def _gather():
        out: dict[str, Any] = {}
        for name in ("detect_project_stack", "get_onboarding_status", "get_visual_gap_report"):
            tool = await mcp.get_tool(name)
            out[name] = tool.fn
        return out

    return asyncio.run(_gather())


# ─── detect_project_stack ────────────────────────────────────────────


class TestDetectProjectStack:
    def test_react_with_next_app_router_and_supabase(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"](
            project_name="my-app",
            marker_files_present=["package.json"],
            dep_files={"package.json": '{"dependencies": {"@supabase/supabase-js": "2.x"}}'},
            feature_dirs_present=["src/app"],
        )
        assert result["stack"] == "react"
        assert result["architecture_pattern"] == "next-app-router"
        assert "supabase" in result["infra"]
        assert result["project_name"] == "my-app"

    def test_flutter_feature_first(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"](
            marker_files_present=["pubspec.yaml"],
            dep_files={"pubspec.yaml": "dependencies:\n  firebase_core: ^2.0.0\n"},
            feature_dirs_present=["lib/features"],
        )
        assert result["stack"] == "flutter"
        assert result["architecture_pattern"] == "feature-first"
        assert "firebase" in result["infra"]

    def test_python_src_layout(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"](
            marker_files_present=["pyproject.toml"],
            dep_files={"pyproject.toml": "[project]\ndependencies = ['stripe>=5.0']\n"},
            feature_dirs_present=["src"],
        )
        assert result["stack"] == "python"
        assert result["architecture_pattern"] == "src-layout"
        assert "stripe" in result["infra"]

    def test_go_clean_architecture(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"](
            marker_files_present=["go.mod"],
            dep_files={"go.mod": "module example.com/foo\n"},
            feature_dirs_present=["cmd", "internal"],
        )
        assert result["stack"] == "go"
        assert result["architecture_pattern"] == "clean-architecture"
        assert result["infra"] == []

    def test_empty_bundle_returns_unknown(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"]()
        assert result["stack"] == "unknown"
        assert result["architecture_pattern"] == "unknown"
        assert result["infra"] == []
        assert result["files_found"] == []

    def test_malformed_dep_file_does_not_crash(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"](
            marker_files_present=["package.json"],
            dep_files={"package.json": None},
            feature_dirs_present=[],
        )
        assert result["stack"] == "react"
        assert result["infra"] == []

    def test_apps_script(self, onboarding_tools):
        result = onboarding_tools["detect_project_stack"](
            marker_files_present=[".clasp.json"],
        )
        assert result["stack"] == "google-apps-script"
        assert result["architecture_pattern"] == "clasp-project"


# ─── get_onboarding_status ───────────────────────────────────────────


class TestGetOnboardingStatus:
    def test_empty_presence_reports_all_missing(self, onboarding_tools):
        result = onboarding_tools["get_onboarding_status"](project_name="ghost")
        assert result["fully_onboarded"] is False
        assert result["registered_in_engine"] is False
        assert "CLAUDE.md" in result["missing"]
        assert result["present"] == []

    def test_partial_presence(self, onboarding_tools):
        result = onboarding_tools["get_onboarding_status"](
            project_name="midway",
            artifact_presence={
                "CLAUDE.md": True,
                ".claude/settings.json": True,
                ".quality/": True,
                # rest default to False
            },
        )
        assert result["fully_onboarded"] is False
        assert "CLAUDE.md" in result["present"]
        assert ".quality/baselines/" in result["missing"]

    def test_fully_onboarded_with_registry(self, onboarding_tools, tmp_path):
        # Seed the state registry on the MCP host
        (tmp_path / "registry.json").write_text(
            json.dumps({"projects": {"reg_proj": {"name": "reg_proj"}}}),
            encoding="utf-8",
        )
        result = onboarding_tools["get_onboarding_status"](
            project_name="reg_proj",
            artifact_presence={
                "CLAUDE.md": True,
                ".claude/settings.json": True,
                "team-config.json": True,
                ".quality/": True,
                ".quality/baselines/": True,
                ".quality/evidence/": True,
                ".quality/logs/": True,
                ".quality/scripts/": True,
            },
        )
        assert result["fully_onboarded"] is True
        assert result["registered_in_engine"] is True
        assert result["missing"] == []


# ─── get_visual_gap_report ───────────────────────────────────────────


class TestGetVisualGapReport:
    def test_not_applicable_when_no_stitch_signals(self, onboarding_tools):
        result = onboarding_tools["get_visual_gap_report"](
            settings_local_json_content=None,
            artifact_presence={},
            has_design_htmls=False,
            has_veg_base_files=False,
        )
        assert result["status"] == "not_applicable"
        assert result["uses_stitch"] is False

    def test_partial_when_only_stitch_configured(self, onboarding_tools):
        """Settings has projectId (counted as 1 of 10) but no brand kit/veg files
        → still partial, not full 'missing'."""
        settings = json.dumps({"stitch": {"projectId": "abc123"}})
        result = onboarding_tools["get_visual_gap_report"](
            settings_local_json_content=settings,
            artifact_presence={},
        )
        assert result["uses_stitch"] is True
        assert result["status"] == "partial"
        assert result["coverage"]["coverage_pct"] < 100
        assert result["coverage"]["coverage_pct"] > 0

    def test_partial_with_brand_kit_only(self, onboarding_tools):
        settings = json.dumps({"stitch": {"projectId": "abc"}})
        result = onboarding_tools["get_visual_gap_report"](
            settings_local_json_content=settings,
            artifact_presence={
                "doc/brand/brand_kit/SKILL.md": True,
                "doc/brand/brand_kit/variables.css": True,
                "doc/brand/brand_kit/tailwind.config.js": True,
                "doc/brand/brand_kit/light.md": True,
                "doc/brand/brand_kit/dark.md": True,
            },
        )
        assert result["status"] == "partial"
        assert result["categories"]["brand_kit"] == "5/5"

    def test_complete_setup(self, onboarding_tools):
        settings = json.dumps({
            "stitch": {
                "projectId": "abc",
                "designSystemAssetId": "ds-1",
                "multiFormFactor": {"DESKTOP": True},
            },
        })
        all_artifacts = {
            "doc/brand/brand_kit/SKILL.md": True,
            "doc/brand/brand_kit/variables.css": True,
            "doc/brand/brand_kit/tailwind.config.js": True,
            "doc/brand/brand_kit/light.md": True,
            "doc/brand/brand_kit/dark.md": True,
            "doc/design/stitch-prompt-template.md": True,
        }
        result = onboarding_tools["get_visual_gap_report"](
            settings_local_json_content=settings,
            artifact_presence=all_artifacts,
            has_veg_base_files=True,
        )
        assert result["status"] == "complete"
        assert result["coverage"]["coverage_pct"] == 100

    def test_html_designs_without_settings(self, onboarding_tools):
        """has_design_htmls=True alone is enough to flag the project as using Stitch."""
        result = onboarding_tools["get_visual_gap_report"](
            settings_local_json_content=None,
            artifact_presence={},
            has_design_htmls=True,
        )
        assert result["uses_stitch"] is True
        assert result["status"] == "missing"

    def test_malformed_settings_treated_as_empty(self, onboarding_tools):
        result = onboarding_tools["get_visual_gap_report"](
            settings_local_json_content="{not valid",
            artifact_presence={},
        )
        assert result["uses_stitch"] is False
