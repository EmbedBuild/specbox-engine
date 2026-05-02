"""Tests for the decisions queue (v5.29.0 PR-6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.app_docs.queue import (
    INVIOLABLE_FOR_QUEUE,
    enqueue_decision,
    list_queue,
    resolve_entry,
)


# ── enqueue_decision ─────────────────────────────────────────────────


class TestEnqueue:
    def test_creates_skeleton_when_file_missing(self, tmp_path):
        result = enqueue_decision(
            "veg_preview",
            "signup-flow",
            default_applied="Per-ICP Startup score=0.82",
            project_path=tmp_path,
        )
        assert result["ok"] is True
        path = tmp_path / "doc" / "app" / "decisions_queue.md"
        assert path.exists()
        content = path.read_text()
        assert "## Pendientes" in content
        assert "## Resueltas" in content
        assert "veg_preview" in content
        assert result["entry"]["engine_id"].startswith("dq-")

    def test_appends_multiple_entries(self, tmp_path):
        enqueue_decision("veg_preview", "f1", default_applied="X", project_path=tmp_path)
        enqueue_decision("tokens_confirmation", "f2", default_applied="Y", project_path=tmp_path)
        listing = list_queue(tmp_path)
        assert listing["pending_count"] == 2

    def test_inviolable_keys_rejected(self, tmp_path):
        for key in INVIOLABLE_FOR_QUEUE:
            result = enqueue_decision(key, "f", default_applied="x", project_path=tmp_path)
            assert result["ok"] is False, f"{key} should be rejected"
            assert result["error"] == "queue_not_allowed_for_inviolable"

    def test_engine_id_unique_per_entry(self, tmp_path):
        ids = set()
        for _ in range(5):
            r = enqueue_decision("veg_preview", "f", default_applied="x", project_path=tmp_path)
            ids.add(r["entry"]["engine_id"])
        assert len(ids) == 5


# ── list_queue ───────────────────────────────────────────────────────


class TestListQueue:
    def test_reports_not_existing(self, tmp_path):
        result = list_queue(tmp_path)
        assert result["exists"] is False
        assert result["pendientes"] == []
        assert result["resueltas"] == []

    def test_lists_after_enqueue(self, tmp_path):
        enqueue_decision("veg_preview", "f1", default_applied="X", project_path=tmp_path)
        listing = list_queue(tmp_path)
        assert listing["exists"] is True
        assert listing["pending_count"] == 1
        assert listing["pendientes"][0]["feature"] == "f1"
        assert listing["pendientes"][0]["decision_key"] == "veg_preview"

    def test_round_trip_preserves_fields(self, tmp_path):
        enqueue_decision(
            "stitch_design_per_screen",
            "dashboard",
            default_applied="Reused existing HTML",
            blocks="UC-007",
            evidence="doc/design/dashboard/screen.html",
            project_path=tmp_path,
        )
        entries = list_queue(tmp_path)["pendientes"]
        assert entries[0]["blocks"] == "UC-007"
        assert entries[0]["evidence"] == "doc/design/dashboard/screen.html"


# ── resolve_entry ────────────────────────────────────────────────────


class TestResolve:
    def test_moves_entry_to_resueltas(self, tmp_path):
        enqueue_decision("veg_preview", "f1", default_applied="X", project_path=tmp_path)
        engine_id = list_queue(tmp_path)["pendientes"][0]["engine_id"]

        result = resolve_entry(engine_id, resolution="confirmed", project_path=tmp_path)
        assert result["ok"] is True

        listing = list_queue(tmp_path)
        assert listing["pending_count"] == 0
        assert listing["resolved_count"] == 1
        assert listing["resueltas"][0]["resolution"] == "confirmed"
        assert listing["resueltas"][0]["resolved_at"]
        assert listing["resueltas"][0]["auto_resolved"] is False

    def test_unknown_engine_id_returns_error(self, tmp_path):
        enqueue_decision("veg_preview", "f1", default_applied="X", project_path=tmp_path)
        result = resolve_entry("dq-does-not-exist", resolution="x", project_path=tmp_path)
        assert result["ok"] is False
        assert result["error"] == "engine_id_not_found"

    def test_resolve_when_file_missing(self, tmp_path):
        result = resolve_entry("dq-anything", resolution="x", project_path=tmp_path)
        assert result["ok"] is False
        assert result["error"] == "queue_file_not_found"

    def test_auto_resolved_flag_persists(self, tmp_path):
        enqueue_decision("veg_preview", "f1", default_applied="X", project_path=tmp_path)
        engine_id = list_queue(tmp_path)["pendientes"][0]["engine_id"]
        resolve_entry(engine_id, resolution="auto-default", auto_resolved=True, project_path=tmp_path)

        listing = list_queue(tmp_path)
        assert listing["resueltas"][0]["auto_resolved"] is True


# ── Multiple resolves preserve order ─────────────────────────────────


class TestMultipleEntries:
    def test_resolved_entries_stay_resolved(self, tmp_path):
        enqueue_decision("veg_preview", "f1", default_applied="X", project_path=tmp_path)
        enqueue_decision("veg_preview", "f2", default_applied="Y", project_path=tmp_path)
        enqueue_decision("veg_preview", "f3", default_applied="Z", project_path=tmp_path)

        first_id = list_queue(tmp_path)["pendientes"][0]["engine_id"]
        resolve_entry(first_id, resolution="r1", project_path=tmp_path)

        listing = list_queue(tmp_path)
        assert listing["pending_count"] == 2
        assert listing["resolved_count"] == 1
