"""Tests for the app-docs sync orchestrator (v5.29.0 PR-11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app_docs.sync import (
    EVENT_ZONE_MAP,
    record_sync_signature,
    sync_app_docs,
    verify_app_docs_in_sync,
)


def _seed_app_prd(path: Path, roadmap_body: str = "## 5. Roadmap de US\n\n(empty)") -> None:
    path.write_text(
        "<!-- @specbox:zone start kind=\"manual\" id=\"vision\" -->\nv\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"audience\" -->\na\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"scope\" -->\ns\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"hybrid\" id=\"success_metrics\" -->\nm\n<!-- @specbox:zone end -->\n"
        f"<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" auto_sync_on=\"complete_uc\" -->\n"
        f"{roadmap_body}\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"stakeholders\" -->\np\n<!-- @specbox:zone end -->\n",
        encoding="utf-8",
    )


def _seed_app_spec(path: Path, tracking_body: str = "## 2. Tracking backend\n\n- Tipo: freeform") -> None:
    path.write_text(
        "<!-- @specbox:zone start kind=\"auto\" id=\"stack\" -->\n## 1. Stack\n<!-- @specbox:zone end -->\n"
        f"<!-- @specbox:zone start kind=\"auto\" id=\"tracking_backend\" -->\n{tracking_body}\n"
        "<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"brand_visual\" -->\nb\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"manual\" id=\"conventions\" -->\nc\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"auto\" id=\"autopilot\" -->\n## 5. Autopilot\n- Level: low\n<!-- @specbox:zone end -->\n"
        "<!-- @specbox:zone start kind=\"hybrid\" id=\"canonical_decisions\" -->\nd\n<!-- @specbox:zone end -->\n",
        encoding="utf-8",
    )


# ── verify_app_docs_in_sync ──────────────────────────────────────────


class TestVerify:
    def test_no_docs_in_sync_returns_true(self, tmp_path):
        result = verify_app_docs_in_sync(tmp_path)
        assert result.in_sync is True
        assert result.prd_signature is None
        assert result.spec_signature is None

    def test_docs_present_no_lock_in_sync(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        _seed_app_spec(app / "app_spec.md")
        result = verify_app_docs_in_sync(tmp_path)
        assert result.in_sync is True  # no lock = no drift baseline yet

    def test_lock_records_signature(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        record_sync_signature(tmp_path)
        lock = json.loads((tmp_path / ".quality" / "app_docs_sync.lock").read_text())
        assert "app_prd" in lock["signatures"]

    def test_drift_detected_when_doc_changes_after_lock(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        record_sync_signature(tmp_path)
        # Modify the manual zone — signature changes.
        path = app / "app_prd.md"
        path.write_text(path.read_text().replace("v\n", "edited content\n"))

        result = verify_app_docs_in_sync(tmp_path)
        assert result.in_sync is False
        assert any("drifted" in d.message for d in result.drift)

    def test_malformed_doc_reported_as_error(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        (app / "app_prd.md").write_text(
            "<!-- @specbox:zone start kind=\"manual\" id=\"x\" -->\nopen\n"
        )
        result = verify_app_docs_in_sync(tmp_path)
        assert result.in_sync is False
        assert any(d.severity == "error" for d in result.drift)


# ── sync_app_docs ────────────────────────────────────────────────────


class TestSync:
    def test_unknown_event_type_rejected(self, tmp_path):
        result = sync_app_docs("nonexistent_event", {}, tmp_path)
        assert result["ok"] is False
        assert result["error"] == "unknown_event_type"

    def test_set_auth_token_updates_tracking_backend(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_spec(app / "app_spec.md")

        result = sync_app_docs(
            "set_auth_token",
            {
                "backend_type": "freeform",
                "freeform_root_absolute": "/abs/doc/tracking",
                "external_reporting": "no",
            },
            tmp_path,
        )
        assert result["ok"] is True
        assert any(t["zone_id"] == "tracking_backend" for t in result["touched"])
        new = (app / "app_spec.md").read_text()
        assert "/abs/doc/tracking" in new

    def test_idempotent_when_payload_unchanged(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_spec(app / "app_spec.md")
        payload = {
            "backend_type": "freeform",
            "freeform_root_absolute": "/abs/doc/tracking",
            "external_reporting": "no",
        }
        sync_app_docs("set_auth_token", payload, tmp_path)
        result2 = sync_app_docs("set_auth_token", payload, tmp_path)
        assert all(t["reason"] == "no_change" for t in result2["skipped"]) or result2["touched"] == []

    def test_skips_when_doc_missing(self, tmp_path):
        result = sync_app_docs("set_auth_token", {"backend_type": "freeform"}, tmp_path)
        assert result["ok"] is True
        assert any(s["reason"] == "document_not_present" for s in result["skipped"])

    def test_complete_uc_event_targets_roadmap(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        result = sync_app_docs(
            "complete_uc",
            {
                "rows": [
                    {
                        "us_id": "US-01",
                        "title": "Demo",
                        "state": "done",
                        "uc_count": 3,
                        "updated_at": "2026-05-02",
                    }
                ]
            },
            tmp_path,
        )
        assert any(t["zone_id"] == "roadmap" for t in result["touched"])
        assert "US-01" in (app / "app_prd.md").read_text()

    def test_autopilot_config_change_updates_zone(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_spec(app / "app_spec.md")
        result = sync_app_docs(
            "autopilot_config_change",
            {"level": "equilibrado", "image_budget_eur_per_feature": 12, "queue_enabled": True},
            tmp_path,
        )
        assert any(t["zone_id"] == "autopilot" for t in result["touched"])
        text = (app / "app_spec.md").read_text()
        assert "Level:** equilibrado" in text or "Level: equilibrado" in text

    def test_event_zone_map_completeness(self):
        # Sanity: every event has at least one (document, zone) target.
        for event, targets in EVENT_ZONE_MAP.items():
            assert targets, f"event {event!r} has no targets"
            for doc, zid in targets:
                assert doc in {"app_prd", "app_spec"}
                assert zid


# ── record_sync_signature ────────────────────────────────────────────


class TestRecordSignature:
    def test_idempotent_when_no_changes(self, tmp_path):
        app = tmp_path / "doc" / "app"
        app.mkdir(parents=True)
        _seed_app_prd(app / "app_prd.md")
        first = record_sync_signature(tmp_path)["signatures"]["app_prd"]
        second = record_sync_signature(tmp_path)["signatures"]["app_prd"]
        assert first == second
