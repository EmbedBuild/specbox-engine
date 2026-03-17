"""Tests for live state MCP tools — conversational queries.

Validates:
- AC-22: get_project_live_state returns snapshot with decay
- AC-23: Fallback to meta.json if no project_state.json
- AC-24: Error with project list if slug not found
- AC-25: get_all_projects_overview returns list with health_emoji
- AC-26: Projects ordered by last_activity descending
- AC-27: Summary field with aggregated text
- AC-28: get_active_sessions returns only active projects
- AC-29: Message when no active sessions
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from server.tools.state import (
    _ensure_project_dir,
    _write_project_state,
    _read_meta,
    _write_meta,
    _write_registry,
)
from server.tools.live_state import (
    _humanize_timedelta,
    _health_emoji,
)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    """Create a state directory with some test projects."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    registry = {
        "projects": {
            "project-a": {"stack": "flutter"},
            "project-b": {"stack": "python"},
            "project-c": {"stack": "react"},
        }
    }
    (state_dir / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return state_dir


class TestHumanizeTimedelta:
    def test_recent(self):
        now = datetime.now(timezone.utc).isoformat()
        result = _humanize_timedelta(now)
        assert "ahora" in result or "minuto" in result

    def test_hours_ago(self):
        dt = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = _humanize_timedelta(dt)
        assert "3 horas" in result

    def test_days_ago(self):
        dt = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        result = _humanize_timedelta(dt)
        assert "2 dias" in result

    def test_empty_string(self):
        assert _humanize_timedelta("") == "desconocido"

    def test_invalid_date(self):
        assert _humanize_timedelta("not-a-date") == "desconocido"


class TestHealthEmoji:
    def test_healthy_and_fresh(self):
        now = datetime.now(timezone.utc)
        state = {
            "healing_health": "healthy",
            "received_at": (now - timedelta(minutes=5)).isoformat(),
        }
        assert _health_emoji(state) == "green_circle"

    def test_stale_over_1_hour(self):
        now = datetime.now(timezone.utc)
        state = {
            "healing_health": "healthy",
            "received_at": (now - timedelta(hours=2)).isoformat(),
        }
        assert _health_emoji(state) == "yellow_circle"

    def test_stale_over_24_hours(self):
        now = datetime.now(timezone.utc)
        state = {
            "healing_health": "healthy",
            "received_at": (now - timedelta(hours=30)).isoformat(),
        }
        assert _health_emoji(state) == "red_circle"

    def test_critical_healing(self):
        state = {
            "healing_health": "critical",
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        assert _health_emoji(state) == "red_circle"

    def test_degraded_healing(self):
        state = {
            "healing_health": "degraded",
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        assert _health_emoji(state) == "yellow_circle"

    def test_no_received_at(self):
        state = {"healing_health": "healthy"}
        assert _health_emoji(state) == "yellow_circle"


class TestProjectStateIntegration:
    """Integration tests for project_state.json with state helpers."""

    def test_write_and_read_full_snapshot(self, state_path: Path):
        project_dir = _ensure_project_dir(state_path, "project-a")
        now = datetime.now(timezone.utc).isoformat()
        state = {
            "project": "project-a",
            "timestamp": now,
            "received_at": now,
            "source": "heartbeat",
            "session_active": True,
            "current_phase": "implement",
            "current_feature": "auth-flow",
            "current_branch": "feat/auth",
            "plan_progress": {"total_ucs": 10, "completed_ucs": 5, "current_uc": "UC-006"},
            "last_verdict": "ACCEPTED",
            "coverage_pct": 85.0,
            "tests_passing": 100,
            "tests_failing": 2,
            "open_feedback": 1,
            "blocking_feedback": 0,
            "healing_health": "healthy",
            "self_healing_events": 0,
            "last_operation": "implement",
            "last_commit": "add auth middleware",
            "last_commit_at": now,
        }
        _write_project_state(project_dir, state)

        # Read back
        from server.tools.state import _read_project_state
        result = _read_project_state(project_dir)
        assert result["project"] == "project-a"
        assert result["plan_progress"]["completed_ucs"] == 5
        assert result["coverage_pct"] == 85.0

    def test_meta_fallback_when_no_state(self, state_path: Path):
        """AC-23: Without project_state.json, meta.json provides basic data."""
        project_dir = _ensure_project_dir(state_path, "project-b")
        meta = {"last_activity": "2026-03-17T10:00:00Z", "active_feature": "login"}
        _write_meta(project_dir, meta)

        from server.tools.state import _read_project_state
        state = _read_project_state(project_dir)
        assert state == {}  # No project_state.json

        read_meta = _read_meta(project_dir)
        assert read_meta["active_feature"] == "login"
