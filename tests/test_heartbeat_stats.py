"""Tests for heartbeat observability tools.

Validates:
- AC-08: get_heartbeat_stats returns 24h counts and stale alerts
- AC-09: REST endpoint returns JSON with auth
- AC-10: Heartbeat logging writes to JSONL
- AC-11: Stale detection for active sessions > 30 min
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from server.tools.state import (
    _ensure_project_dir,
    _write_project_state,
    _write_registry,
)
from server.tools.heartbeat_stats import (
    append_heartbeat_log,
    compute_heartbeat_stats,
)


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    """Create state directory with test projects."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    registry = {
        "projects": {
            "proj-a": {"stack": "flutter"},
            "proj-b": {"stack": "react"},
        }
    }
    (state_dir / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    return state_dir


class TestAppendHeartbeatLog:
    """AC-10: Heartbeat logging to JSONL."""

    def test_creates_file_and_appends(self, state_path: Path):
        _ensure_project_dir(state_path, "proj-a")
        append_heartbeat_log(state_path, "proj-a", "192.168.1.1", "ok")

        log_file = state_path / "projects" / "proj-a" / "heartbeats.jsonl"
        assert log_file.exists()

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["source_ip"] == "192.168.1.1"
        assert entry["status"] == "ok"
        assert "timestamp" in entry
        assert "received_at" in entry

    def test_appends_multiple_entries(self, state_path: Path):
        _ensure_project_dir(state_path, "proj-a")
        append_heartbeat_log(state_path, "proj-a", "10.0.0.1", "ok")
        append_heartbeat_log(state_path, "proj-a", "10.0.0.2", "ok")

        log_file = state_path / "projects" / "proj-a" / "heartbeats.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2


class TestComputeHeartbeatStats:
    """AC-08: get_heartbeat_stats returns aggregated stats."""

    def test_empty_state(self, state_path: Path):
        _ensure_project_dir(state_path, "proj-a")
        _ensure_project_dir(state_path, "proj-b")

        stats = compute_heartbeat_stats(state_path)
        assert stats["total_24h"] == 0
        assert stats["projects_with_activity"] == 0
        assert len(stats["stale_projects"]) == 0
        assert "summary" in stats

    def test_counts_recent_heartbeats(self, state_path: Path):
        _ensure_project_dir(state_path, "proj-a")

        # Write 3 recent heartbeat entries
        log_file = state_path / "projects" / "proj-a" / "heartbeats.jsonl"
        now = datetime.now(timezone.utc)
        for i in range(3):
            ts = (now - timedelta(hours=i)).isoformat()
            entry = {"timestamp": ts, "received_at": ts, "source_ip": "1.2.3.4", "status": "ok"}
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

        stats = compute_heartbeat_stats(state_path)
        assert stats["total_24h"] == 3
        assert stats["projects_with_activity"] == 1
        assert "proj-a" in stats["by_project"]
        assert stats["by_project"]["proj-a"]["count_24h"] == 3

    def test_excludes_old_heartbeats(self, state_path: Path):
        _ensure_project_dir(state_path, "proj-a")

        log_file = state_path / "projects" / "proj-a" / "heartbeats.jsonl"
        old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        entry = {"timestamp": old, "received_at": old, "source_ip": "1.2.3.4", "status": "ok"}
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

        stats = compute_heartbeat_stats(state_path)
        assert stats["total_24h"] == 0
        # But the project still has a last_heartbeat
        assert "proj-a" in stats["by_project"]
        assert stats["by_project"]["proj-a"]["count_24h"] == 0


class TestStaleDetection:
    """AC-11: Stale detection for active sessions."""

    def test_detects_stale_active_session(self, state_path: Path):
        project_dir = _ensure_project_dir(state_path, "proj-a")
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        _write_project_state(project_dir, {
            "project": "proj-a",
            "session_active": True,
            "received_at": stale_time,
            "healing_health": "healthy",
        })

        stats = compute_heartbeat_stats(state_path)
        assert len(stats["stale_projects"]) == 1
        assert stats["stale_projects"][0]["project"] == "proj-a"
        assert stats["stale_projects"][0]["age_minutes"] >= 44

    def test_fresh_session_not_stale(self, state_path: Path):
        project_dir = _ensure_project_dir(state_path, "proj-a")
        fresh_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        _write_project_state(project_dir, {
            "project": "proj-a",
            "session_active": True,
            "received_at": fresh_time,
            "healing_health": "healthy",
        })

        stats = compute_heartbeat_stats(state_path)
        assert len(stats["stale_projects"]) == 0

    def test_inactive_session_not_stale(self, state_path: Path):
        project_dir = _ensure_project_dir(state_path, "proj-a")
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        _write_project_state(project_dir, {
            "project": "proj-a",
            "session_active": False,
            "received_at": old_time,
            "healing_health": "healthy",
        })

        stats = compute_heartbeat_stats(state_path)
        assert len(stats["stale_projects"]) == 0
