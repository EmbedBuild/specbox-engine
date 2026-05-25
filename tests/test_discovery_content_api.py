"""Tests for the v6.0.1 content-passing Discovery tools (UC-614).

The three @mcp.tool functions in server/tools/discovery.py no longer touch
the filesystem. They operate on string content passed by the caller. These
tests exercise the registered tool callables via a FastMCP instance,
verifying the new content-passing contract end-to-end.

Coverage matrix (5 cases × 3 tools):

  1. happy path                   — valid content, expected verdict
  2. empty / None content         — treated as missing
  3. malformed content            — graceful degradation, no crash
  4. idempotency / resume         — second call recognizes prior state
  5. partial bundle (mig case)    — only some signals provided
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
def discovery_tools():
    """Build a FastMCP server with the discovery tools registered and
    return a dict of {tool_name: sync callable} for direct invocation."""
    from server.tools.discovery import register_product_discovery_tools

    mcp = FastMCP(name="test-discovery")
    register_product_discovery_tools(mcp, engine_path=REPO_ROOT)

    async def _gather():
        out: dict[str, Any] = {}
        for name in (
            "start_discovery",
            "validate_discovery_completeness",
            "detect_v60_migration_case",
        ):
            tool = await mcp.get_tool(name)
            out[name] = tool.fn
        return out

    return asyncio.run(_gather())


# ─── start_discovery ────────────────────────────────────────────────


class TestStartDiscoveryContentAPI:
    def test_happy_path_creates_skeleton(self, discovery_tools):
        """Standard mode with non-pristine app_market_content."""
        result = discovery_tools["start_discovery"](
            feature_name="user_export",
            app_market_content=(
                '<!-- @specbox:zone start kind="manual" id="icps_primary" -->\n'
                "Real ICP content here.\n"
                '<!-- @specbox:zone end -->\n'
            ),
            existing_artifact_content=None,
            mode="auto",
        )
        assert result["status"] == "created"
        assert result["mode_used"] == "standard"
        assert result["app_market_present"] is True
        assert result["discovery_id"].startswith("disc-")
        assert "skeleton_content" in result
        assert "# Discovery: user_export" in result["skeleton_content"]
        assert result["artifact_path"] == "doc/discovery/user_export/icp_jtbd.md"

    def test_empty_app_market_triggers_bootstrap(self, discovery_tools):
        """app_market_content=None ⇒ bootstrap mode auto-detected."""
        result = discovery_tools["start_discovery"](
            feature_name="first_feature",
            app_market_content=None,
            existing_artifact_content=None,
            mode="auto",
        )
        assert result["status"] == "created"
        assert result["mode_used"] == "bootstrap"
        assert result["app_market_present"] is False
        assert "skeleton_content" in result

    def test_pristine_app_market_triggers_bootstrap(self, discovery_tools):
        """Plantilla pristine ⇒ bootstrap mode."""
        pristine = (
            '<!-- @specbox:zone start kind="manual" id="icps_primary" '
            'status="template-pristine" -->\n'
            "Pristine plantilla content.\n"
            '<!-- @specbox:zone end -->\n'
        )
        result = discovery_tools["start_discovery"](
            feature_name="bootstrap_feat",
            app_market_content=pristine,
            existing_artifact_content=None,
            mode="auto",
        )
        assert result["status"] == "created"
        assert result["mode_used"] == "bootstrap"
        assert result["app_market_present"] is True

    def test_malformed_app_market_falls_back_to_bootstrap(self, discovery_tools):
        """Malformed content ⇒ bootstrap mode (no crash)."""
        result = discovery_tools["start_discovery"](
            feature_name="malf_feat",
            app_market_content="<!-- @specbox:zone start kind=\"manual\" id=\"x\" -->\n"
                               "(no end marker — malformed)",
            existing_artifact_content=None,
            mode="auto",
        )
        assert result["status"] == "created"
        assert result["mode_used"] == "bootstrap"

    def test_resumable_when_existing_artifact_passed(self, discovery_tools):
        """Passing existing_artifact_content ⇒ status='resumable'."""
        existing = (
            "# Discovery: resume_feat\n\n"
            "**Discovery ID**: disc-abcdef123456\n"
            "**Mode**: standard\n\n"
            "## ICPs involucrados\n\n_(Pendiente)_\n\n"
            "## JTBDs racionales\n\n_(Pendiente)_\n\n"
            "## JTBDs emocionales\n\n_(Pendiente)_\n\n"
            "## Validation evidence\n\n_(Pendiente)_\n"
        )
        result = discovery_tools["start_discovery"](
            feature_name="resume_feat",
            app_market_content=None,
            existing_artifact_content=existing,
            mode="auto",
        )
        assert result["status"] == "resumable"
        assert result["discovery_id"] == "disc-abcdef123456"
        assert result["mode_used"] == "standard"
        assert result["current_verdict"] == "DISCOVERY_INCOMPLETE"
        assert "icps_involucrados" in result["missing"]

    def test_resumable_with_unknown_metadata(self, discovery_tools):
        """Existing artifact with no Discovery ID / Mode metadata ⇒ unknown."""
        result = discovery_tools["start_discovery"](
            feature_name="partial",
            app_market_content=None,
            existing_artifact_content="# Discovery: partial\n\nNo metadata here.",
            mode="auto",
        )
        assert result["status"] == "resumable"
        assert result["discovery_id"] == "unknown"
        assert result["mode_used"] == "unknown"

    def test_invalid_feature_name_rejected(self, discovery_tools):
        result = discovery_tools["start_discovery"](
            feature_name="has space",
            app_market_content=None,
            existing_artifact_content=None,
            mode="auto",
        )
        assert "error" in result
        assert result["code"] == "INVALID_FEATURE_NAME"

    def test_empty_feature_name_rejected(self, discovery_tools):
        result = discovery_tools["start_discovery"](
            feature_name="   ",
            app_market_content=None,
            existing_artifact_content=None,
            mode="auto",
        )
        assert "error" in result
        assert result["code"] == "INVALID_FEATURE_NAME"

    def test_force_standard_mode(self, discovery_tools):
        """mode='standard' overrides auto-detection even when bootstrap signals present."""
        result = discovery_tools["start_discovery"](
            feature_name="forced",
            app_market_content=None,  # would normally trigger bootstrap
            existing_artifact_content=None,
            mode="standard",
        )
        assert result["status"] == "created"
        assert result["mode_used"] == "standard"

    def test_force_bootstrap_mode(self, discovery_tools):
        result = discovery_tools["start_discovery"](
            feature_name="forced_boot",
            app_market_content=(
                '<!-- @specbox:zone start kind="manual" id="x" -->\nReal\n'
                '<!-- @specbox:zone end -->\n'
            ),
            existing_artifact_content=None,
            mode="bootstrap",
        )
        assert result["status"] == "created"
        assert result["mode_used"] == "bootstrap"

    def test_invalid_mode_rejected(self, discovery_tools):
        result = discovery_tools["start_discovery"](
            feature_name="foo",
            app_market_content=None,
            existing_artifact_content=None,
            mode="nonsense",
        )
        assert "error" in result
        assert result["code"] == "INVALID_MODE"


# ─── validate_discovery_completeness ────────────────────────────────


class TestValidateCompletenessContentAPI:
    def test_happy_path_ready_for_prd(self, discovery_tools):
        filled = """# Discovery: feat

## ICPs involucrados

### ICP-1: Real ICP
Content here, substantial enough.

## JTBDs racionales

- **JR-F1.1** [ICP-1]: When user X, want Y, so Z. Real content.

## JTBDs emocionales

- **JE-F1.1** [ICP-1]: Feel in control.

## Validation evidence

- Evidence type: conversation
- Description: 3 users interviewed in May 2026.

## Drift from app_market

- Resolución: no drift detected
"""
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=filled,
        )
        assert result["verdict"] == "READY_FOR_PRD"
        assert result["missing"] == []
        assert result["artifact_path"] == "doc/discovery/feat/icp_jtbd.md"

    def test_empty_content_returns_artifact_not_found(self, discovery_tools):
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="missing",
            icp_jtbd_content=None,
        )
        assert result["verdict"] == "DISCOVERY_INCOMPLETE"
        assert "artifact_not_found" in result["missing"]
        assert "error" in result

    def test_blank_string_returns_artifact_not_found(self, discovery_tools):
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="blank",
            icp_jtbd_content="   \n\n  ",
        )
        assert result["verdict"] == "DISCOVERY_INCOMPLETE"
        assert "artifact_not_found" in result["missing"]

    def test_skeleton_is_incomplete(self, discovery_tools):
        """Initial skeleton (all sections pending) returns INCOMPLETE."""
        from server.tools.discovery import _render_initial_icp_jtbd

        skel = _render_initial_icp_jtbd("foo", "disc-x", "standard", None)
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="foo",
            icp_jtbd_content=skel,
        )
        assert result["verdict"] == "DISCOVERY_INCOMPLETE"
        for section in ("icps_involucrados", "jtbds_racionales", "jtbds_emocionales", "validation_evidence"):
            assert section in result["missing"]

    def test_partial_completion_reports_specific_missing(self, discovery_tools):
        partial = """# Discovery: x

## ICPs involucrados

### ICP-1: Substantial ICP content here, not a placeholder.

## JTBDs racionales

- **JR-1**: Real rational JTBD content here.

## JTBDs emocionales

_(Pendiente — fase 2 del flujo `/discovery`)_

## Validation evidence

- Evidence: real evidence here.

## Drift from app_market

- Resolución: no drift detected
"""
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="x",
            icp_jtbd_content=partial,
        )
        assert result["verdict"] == "DISCOVERY_INCOMPLETE"
        assert "jtbds_emocionales" in result["missing"]
        assert "icps_involucrados" not in result["missing"]
        assert "jtbds_racionales" not in result["missing"]


# ─── detect_v60_migration_case ──────────────────────────────────────


class TestDetectV60MigrationCaseContentAPI:
    def test_active_uc_priority(self, discovery_tools):
        """Case 3 wins regardless of other signals."""
        result = discovery_tools["detect_v60_migration_case"](
            app_market_content="any content",
            settings_local_json_content=json.dumps(
                {"specbox": {"engine_version_at_onboard": "6.0.0"}}
            ),
            active_uc_present=True,
            pending_critical_feedback=[],
            has_discovery_dir=False,
            has_app_dir=True,
        )
        assert result["case_id"] == "case_3_active_uc"

    def test_pending_feedback_priority(self, discovery_tools):
        """Case 4 wins when no active UC."""
        result = discovery_tools["detect_v60_migration_case"](
            settings_local_json_content=None,
            active_uc_present=False,
            pending_critical_feedback=["fb-001.json"],
            has_discovery_dir=False,
            has_app_dir=True,
        )
        assert result["case_id"] == "case_4_pending_feedback"

    def test_case_1_pre_v529_no_app_dir(self, discovery_tools):
        result = discovery_tools["detect_v60_migration_case"](
            has_app_dir=False,
        )
        assert result["case_id"] == "case_1_pre_v529"

    def test_case_2_v529_v535_no_market(self, discovery_tools):
        result = discovery_tools["detect_v60_migration_case"](
            app_prd_content="# PRD\n",
            app_spec_content="# Spec\n",
            app_market_content=None,
            settings_local_json_content=json.dumps(
                {"specbox": {"engine_version_at_onboard": "5.35.0"}}
            ),
            has_app_dir=True,
            has_discovery_dir=False,
        )
        assert result["case_id"] == "case_2_v529_v535"

    def test_case_5_multirepo_orchestrator(self, discovery_tools):
        settings = {
            "specbox": {"engine_version_at_onboard": "5.35.0"},
            "multirepo": {"enabled": True, "role": "orchestrator"},
        }
        result = discovery_tools["detect_v60_migration_case"](
            settings_local_json_content=json.dumps(settings),
            has_app_dir=True,
        )
        assert result["case_id"] == "case_5_multirepo_orchestrator"

    def test_case_6_multirepo_satellite(self, discovery_tools):
        settings = {
            "multirepo": {"enabled": True, "role": "satellite", "orchestrator": "../orch"},
        }
        result = discovery_tools["detect_v60_migration_case"](
            settings_local_json_content=json.dumps(settings),
            has_app_dir=True,
        )
        assert result["case_id"] == "case_6_multirepo_satellite"

    def test_case_7_fresh_v6_with_market(self, discovery_tools):
        result = discovery_tools["detect_v60_migration_case"](
            app_market_content="# Market\n",
            settings_local_json_content=json.dumps(
                {"specbox": {"engine_version_at_onboard": "6.0.0"}}
            ),
            has_app_dir=True,
        )
        assert result["case_id"] == "case_7_fresh_v6"

    def test_case_8_manual_discovery_dir(self, discovery_tools):
        result = discovery_tools["detect_v60_migration_case"](
            settings_local_json_content=json.dumps({"specbox": {}}),
            has_app_dir=True,
            has_discovery_dir=True,
            app_market_content=None,
        )
        assert result["case_id"] == "case_8_manual_discovery"
        assert result["backup_required"] is True

    def test_partial_bundle_no_settings(self, discovery_tools):
        """Missing settings_local_json_content does not crash."""
        result = discovery_tools["detect_v60_migration_case"](
            settings_local_json_content=None,
            has_app_dir=True,
        )
        assert "case_id" in result

    def test_malformed_settings_handled(self, discovery_tools):
        """Malformed JSON settings ⇒ empty dict, no crash."""
        result = discovery_tools["detect_v60_migration_case"](
            settings_local_json_content="{not valid json",
            has_app_dir=True,
        )
        assert "case_id" in result


# ─── Drift resolution coverage (issue #62, v6.0.2) ─────────────────


def _doc_with_drift(resolution_line: str) -> str:
    """Helper: render an otherwise-complete icp_jtbd.md with the given
    'Resolución: ...' line in the Drift section."""
    return f"""# Discovery: feat

## ICPs involucrados

### ICP-1: Real ICP content, substantial.

## JTBDs racionales

- **JR-1** [ICP-1]: rational content.

## JTBDs emocionales

- **JE-1** [ICP-1]: emotional content.

## Validation evidence

- Evidence: real evidence here.

## Drift from app_market

- {resolution_line}
"""


class TestDriftResolutionParsing:
    """The drift parser must accept all 4 canonical resolutions and expose
    `drift.kind` so future strict-gate modes can distinguish them.

    Regression for issue #62 (v6.0.1 smoke test): `no_drift` was not
    recognised, causing `drift.resolved=false` on heredada features that
    introduced no ICPs/JTBDs.
    """

    def test_no_drift_snake_case_resolves(self, discovery_tools):
        """The shape that the /discovery skill writes on heredada features."""
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=_doc_with_drift("Resolución: no_drift"),
        )
        assert result["verdict"] == "READY_FOR_PRD"
        assert result["drift"]["resolved"] is True
        assert result["drift"]["kind"] == "no_drift"

    def test_no_drift_legacy_phrase_resolves(self, discovery_tools):
        """Legacy 'no drift detected' (with spaces) normalises to 'no_drift'."""
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=_doc_with_drift("Resolución: no drift detected"),
        )
        assert result["verdict"] == "READY_FOR_PRD"
        assert result["drift"]["resolved"] is True
        assert result["drift"]["kind"] == "no_drift"

    def test_documented_exception_resolves_with_kind(self, discovery_tools):
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=_doc_with_drift(
                "Resolución: documented_exception — justified because X"
            ),
        )
        assert result["drift"]["resolved"] is True
        assert result["drift"]["kind"] == "documented_exception"

    def test_app_market_updated_resolves_with_kind(self, discovery_tools):
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=_doc_with_drift("Resolución: app_market_updated"),
        )
        assert result["drift"]["resolved"] is True
        assert result["drift"]["kind"] == "app_market_updated"

    def test_feature_creep_rejected_resolves_with_kind(self, discovery_tools):
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=_doc_with_drift("Resolución: feature_creep_rejected"),
        )
        assert result["drift"]["resolved"] is True
        assert result["drift"]["kind"] == "feature_creep_rejected"

    def test_pending_resolution_stays_unresolved(self, discovery_tools):
        """An unresolved pending drift still pushes 'drift_resolution' to missing."""
        result = discovery_tools["validate_discovery_completeness"](
            feature_name="feat",
            icp_jtbd_content=_doc_with_drift("Resolución: pendiente"),
        )
        assert result["drift"]["resolved"] is False
        assert "kind" not in result["drift"]
        assert "drift_resolution" in result["missing"]
        assert result["verdict"] == "DISCOVERY_INCOMPLETE"
