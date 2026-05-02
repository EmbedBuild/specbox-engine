"""Tests for the v5.28→v5.29 migration tooling (PR-9).

Each of the 10 hypothetical project states from the v5.29 plan gets a
fixture and a detection assertion. The runner is exercised in dry-run
mode for read-only fidelity and in apply mode for cases where the
narrow automatic subset is permitted to write settings.local.json.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from server.app_docs.migration_v529 import (
    apply_settings_specbox_block,
    detect_case,
    run_migration,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _write_settings(project_path: Path, payload: dict) -> None:
    p = project_path / ".claude" / "settings.local.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding="utf-8")


def _make_quality_dir(project_path: Path) -> None:
    (project_path / ".quality").mkdir(parents=True, exist_ok=True)


# ── Detection per case ───────────────────────────────────────────────


class TestCase1Empty:
    def test_empty_project_with_quality_only_returns_case_1(self, tmp_path):
        _make_quality_dir(tmp_path)
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_1_empty"
        assert any(s.name == "run_app_init" for s in plan.steps)


class TestCase2FreeformLocal:
    def test_freeform_settings_present(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
        _make_quality_dir(tmp_path)
        _write_settings(
            tmp_path,
            {"specbox": {"backend_type": "freeform", "freeform_root_absolute": "doc/tracking"}},
        )
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_2_freeform_local"
        assert any("absolute" in s.description.lower() for s in plan.steps)


class TestCase3FreeformVps:
    def test_remote_mcp_with_relative_path_is_blocker(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.vps")
        _make_quality_dir(tmp_path)
        _write_settings(
            tmp_path,
            {"specbox": {"backend_type": "freeform", "freeform_root_absolute": "doc/tracking"}},
        )
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_3_freeform_vps"
        assert plan.backup_required is True
        assert any(s.severity == "blocker" for s in plan.steps)


class TestCase4Trello:
    def test_legacy_trello_settings(self, tmp_path):
        _make_quality_dir(tmp_path)
        _write_settings(tmp_path, {"trello": {"boardId": "abc123"}})
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_4_trello"


class TestCase5Plane:
    def test_legacy_plane_settings(self, tmp_path):
        _make_quality_dir(tmp_path)
        _write_settings(tmp_path, {"plane": {"projectId": "uuid-1"}})
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_5_plane"


class TestCase6Multirepo:
    def test_multirepo_satellite_detected(self, tmp_path):
        _make_quality_dir(tmp_path)
        _write_settings(
            tmp_path,
            {
                "multirepo": {"enabled": True, "role": "satellite", "orchestrator": "../orch"},
                "specbox": {"backend_type": "trello"},
            },
        )
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_6_multirepo"


class TestCase7FeatureInProgress:
    def test_active_uc_takes_priority(self, tmp_path):
        _make_quality_dir(tmp_path)
        (tmp_path / ".quality" / "active_uc.json").write_text(
            json.dumps({"uc_id": "UC-007", "feature": "demo"})
        )
        _write_settings(tmp_path, {"trello": {"boardId": "abc"}})  # would be case 4 otherwise
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_7_feature_in_progress"
        assert any(s.severity == "warning" for s in plan.steps)


class TestCase8PendingFeedback:
    def test_pending_feedback_critical(self, tmp_path):
        feedback_dir = tmp_path / ".quality" / "evidence" / "feedback"
        feedback_dir.mkdir(parents=True)
        (feedback_dir / "FB-001.json").write_text(
            json.dumps({"severity": "critical", "resolved_at": None})
        )
        plan = detect_case(tmp_path)
        # case 8 is detected as the case_id when no other backend signal applies
        # (and no active UC). Falls through afterwards if other signals present.
        assert plan.case_id == "case_8_pending_feedback"


class TestCase9ManualAppMd:
    def test_app_prd_without_zone_markers(self, tmp_path):
        _make_quality_dir(tmp_path)
        app_dir = tmp_path / "doc" / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "app_prd.md").write_text(
            "# App PRD\n\n## Vision\nSomething the user wrote by hand.\n"
        )
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_9_manual_app_md"
        assert plan.backup_required is True


class TestCase10FreshClone:
    def test_no_quality_no_settings_no_tracking(self, tmp_path):
        plan = detect_case(tmp_path)
        assert plan.case_id == "case_10_fresh_clone"
        assert any("install.sh" in s.description for s in plan.steps)


# ── apply_settings_specbox_block ────────────────────────────────────


class TestApplySpecboxBlock:
    def test_creates_new_settings_file(self, tmp_path):
        result = apply_settings_specbox_block(
            tmp_path, freeform_root_absolute=str(tmp_path / "doc" / "tracking")
        )
        assert result["changed"] is True
        data = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
        assert data["specbox"]["backend_type"] == "freeform"
        assert data["specbox"]["autopilot"]["level"] == "equilibrado"
        assert data["specbox"]["freeform_root_absolute"].endswith("doc/tracking")

    def test_preserves_existing_user_keys(self, tmp_path):
        _write_settings(tmp_path, {"plane": {"projectId": "p1"}, "specbox": {"backend_type": "plane"}})
        apply_settings_specbox_block(tmp_path, backend_type="plane")
        data = json.loads((tmp_path / ".claude" / "settings.local.json").read_text())
        assert data["plane"]["projectId"] == "p1"
        assert data["specbox"]["backend_type"] == "plane"

    def test_idempotent_when_already_present(self, tmp_path):
        apply_settings_specbox_block(tmp_path)
        result = apply_settings_specbox_block(tmp_path)
        assert result["changed"] is False


# ── run_migration ───────────────────────────────────────────────────


class TestRunMigration:
    def test_dry_run_reports_steps_without_writing(self, tmp_path):
        _make_quality_dir(tmp_path)
        _write_settings(tmp_path, {"trello": {"boardId": "X"}})
        report = run_migration(tmp_path, apply=False)
        assert report["mode"] == "dry-run"
        assert report["case_id"] == "case_4_trello"
        assert report["automatic_actions"] == []

    def test_apply_writes_specbox_block_for_safe_cases(self, tmp_path):
        _make_quality_dir(tmp_path)
        report = run_migration(tmp_path, apply=True)
        assert report["mode"] == "applied"
        assert any("settings_local_json" in a for a in report["automatic_actions"])

    def test_apply_defers_for_case_7(self, tmp_path):
        _make_quality_dir(tmp_path)
        (tmp_path / ".quality" / "active_uc.json").write_text(json.dumps({"uc_id": "UC-1"}))
        report = run_migration(tmp_path, apply=True)
        assert report["mode"] == "deferred"
        assert report["case_id"] == "case_7_feature_in_progress"

    def test_apply_defers_for_case_3(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.vps")
        _make_quality_dir(tmp_path)
        _write_settings(
            tmp_path,
            {"specbox": {"backend_type": "freeform", "freeform_root_absolute": "doc/tracking"}},
        )
        report = run_migration(tmp_path, apply=True)
        assert report["mode"] == "deferred"
        assert report["case_id"] == "case_3_freeform_vps"

    def test_apply_defers_for_case_9(self, tmp_path):
        _make_quality_dir(tmp_path)
        app_dir = tmp_path / "doc" / "app"
        app_dir.mkdir(parents=True)
        (app_dir / "app_prd.md").write_text("# manual\n")
        report = run_migration(tmp_path, apply=True)
        assert report["mode"] == "deferred"
        assert report["case_id"] == "case_9_manual_app_md"
