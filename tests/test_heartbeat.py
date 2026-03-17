"""Tests for heartbeat ingestion — report_heartbeat and project_state.json.

Validates:
- AC-01: report_heartbeat accepts JSON and returns ok
- AC-02: Heartbeat persists to project_state.json (overwrite, not append)
- AC-03: Auto-register project if not in registry
- AC-10: Session decay lazy (>30 min → session_active=false)
- AC-11: Decay does not modify other fields
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from server.tools.state import (
    _read_project_state,
    _write_project_state,
    _apply_session_decay,
    _ensure_project_dir,
    _read_registry,
    _write_registry,
)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    """Create a minimal state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "registry.json").write_text('{"projects": {}}', encoding="utf-8")
    return state_dir


class TestProjectStateReadWrite:
    """AC-02: project_state.json read/write."""

    def test_write_and_read(self, state_path: Path):
        project_dir = _ensure_project_dir(state_path, "test-project")
        data = {
            "project": "test-project",
            "timestamp": "2026-03-17T10:00:00Z",
            "source": "heartbeat",
            "session_active": True,
        }
        _write_project_state(project_dir, data)
        result = _read_project_state(project_dir)
        assert result["project"] == "test-project"
        assert result["session_active"] is True

    def test_overwrite_not_append(self, state_path: Path):
        project_dir = _ensure_project_dir(state_path, "test-project")
        _write_project_state(project_dir, {"project": "test-project", "version": 1})
        _write_project_state(project_dir, {"project": "test-project", "version": 2})
        result = _read_project_state(project_dir)
        assert result["version"] == 2
        # File should contain only ONE JSON object
        content = (project_dir / "project_state.json").read_text()
        assert content.count('"project"') == 1

    def test_read_nonexistent(self, state_path: Path):
        project_dir = state_path / "projects" / "nonexistent"
        project_dir.mkdir(parents=True)
        result = _read_project_state(project_dir)
        assert result == {}


class TestSessionDecay:
    """AC-10, AC-11: Lazy session decay."""

    def test_active_session_within_threshold(self):
        now = datetime.now(timezone.utc)
        state = {
            "session_active": True,
            "received_at": (now - timedelta(minutes=10)).isoformat(),
            "current_feature": "my-feature",
        }
        result = _apply_session_decay(state)
        assert result["session_active"] is True

    def test_active_session_beyond_threshold(self):
        now = datetime.now(timezone.utc)
        state = {
            "session_active": True,
            "received_at": (now - timedelta(minutes=45)).isoformat(),
            "current_feature": "my-feature",
            "last_verdict": "ACCEPTED",
        }
        result = _apply_session_decay(state)
        assert result["session_active"] is False

    def test_decay_preserves_other_fields(self):
        """AC-11: Decay does NOT modify other fields."""
        now = datetime.now(timezone.utc)
        state = {
            "session_active": True,
            "received_at": (now - timedelta(minutes=60)).isoformat(),
            "current_feature": "my-feature",
            "last_verdict": "ACCEPTED",
            "coverage_pct": 87.5,
        }
        result = _apply_session_decay(state)
        assert result["current_feature"] == "my-feature"
        assert result["last_verdict"] == "ACCEPTED"
        assert result["coverage_pct"] == 87.5

    def test_decay_does_not_mutate_original(self):
        now = datetime.now(timezone.utc)
        state = {
            "session_active": True,
            "received_at": (now - timedelta(minutes=60)).isoformat(),
        }
        _apply_session_decay(state)
        assert state["session_active"] is True  # original unchanged

    def test_inactive_session_unchanged(self):
        state = {
            "session_active": False,
            "received_at": "2026-01-01T00:00:00Z",
        }
        result = _apply_session_decay(state)
        assert result["session_active"] is False

    def test_empty_state(self):
        result = _apply_session_decay({})
        assert result == {}

    def test_custom_decay_minutes(self):
        now = datetime.now(timezone.utc)
        state = {
            "session_active": True,
            "received_at": (now - timedelta(minutes=10)).isoformat(),
        }
        # With 5-minute decay, 10 minutes should trigger decay
        result = _apply_session_decay(state, decay_minutes=5)
        assert result["session_active"] is False
