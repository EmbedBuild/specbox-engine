"""Tests for remote management summary fields.

Validates:
- AC-04: get_project_live_state summary max 300 chars
- AC-05: get_all_projects_overview summary_table is Markdown table
- AC-06: get_active_sessions summary in Spanish
- AC-07: No ISO timestamps in summaries
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from server.tools.state import (
    _ensure_project_dir,
    _write_project_state,
    _read_project_state,
    _apply_session_decay,
    _available_projects,
    _read_registry,
    _read_meta,
)
from server.tools.live_state import (
    _humanize_timedelta,
    _health_emoji,
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


def _write_fresh_state(state_path: Path, slug: str, **overrides):
    """Helper to write a fresh project state."""
    project_dir = _ensure_project_dir(state_path, slug)
    now = datetime.now(timezone.utc)
    state = {
        "project": slug,
        "timestamp": now.isoformat(),
        "received_at": (now - timedelta(minutes=2)).isoformat(),
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
        **overrides,
    }
    _write_project_state(project_dir, state)


def _simulate_get_project_live_state(state_path: Path, slug: str) -> dict:
    """Simulate the tool logic without FastMCP registration."""
    project_dir = state_path / "projects" / slug
    state = _read_project_state(project_dir)
    if not state:
        return {"project": slug, "data_source": "none"}

    state = _apply_session_decay(state)

    progress = state.get("plan_progress", {})
    total = progress.get("total_ucs", 0)
    done = progress.get("completed_ucs", 0)

    session_str = "sesion activa" if state.get("session_active") else "inactivo"
    health = _health_emoji(state)
    time_ago = _humanize_timedelta(state.get("received_at", ""))
    plan_str = f"{done}/{total} UCs" if total > 0 else None
    feature = state.get("current_feature") or "—"
    verdict = state.get("last_verdict") or "—"

    parts = [f"**{slug}** — {session_str}"]
    if state.get("current_feature"):
        parts.append(f"Feature: {feature}")
    if plan_str:
        parts.append(f"UCs: {plan_str}")
    parts.append(f"Veredicto: {verdict}")
    parts.append(f"Health: {health}")
    parts.append(f"Actualizado: {time_ago}")
    summary = " | ".join(parts)
    if len(summary) > 300:
        summary = summary[:297] + "..."

    return {
        "project": slug,
        "summary": summary,
        "time_since_last_update": time_ago,
        "health": health,
    }


def _simulate_get_all_projects_overview(state_path: Path) -> dict:
    """Simulate the tool logic for overview."""
    registry = _read_registry(state_path)
    projects = registry.get("projects", {})
    items = []

    for slug in sorted(projects.keys()):
        project_dir = state_path / "projects" / slug
        state = _read_project_state(project_dir)
        if state:
            state = _apply_session_decay(state)
            items.append({
                "name": slug,
                "health": _health_emoji(state),
                "current_feature": state.get("current_feature"),
                "time_since_last_update": _humanize_timedelta(state.get("received_at", "")),
                "received_at": state.get("received_at", ""),
            })
        else:
            items.append({
                "name": slug,
                "health": "yellow_circle",
                "current_feature": None,
                "time_since_last_update": "desconocido",
                "received_at": "",
            })

    items.sort(key=lambda x: x.get("received_at", ""), reverse=True)
    for item in items:
        item.pop("received_at", None)

    table_lines = [
        "| Proyecto | Estado | Feature | Ultima actividad |",
        "|----------|--------|---------|-----------------|",
    ]
    for item in items:
        name = item.get("name", "?")
        health = item.get("health", "yellow_circle")
        feature = item.get("current_feature") or "—"
        time_ago = item.get("time_since_last_update", "—")
        table_lines.append(f"| {name} | {health} | {feature} | {time_ago} |")

    return {"summary_table": "\n".join(table_lines), "projects": items}


def _simulate_get_active_sessions(state_path: Path) -> dict:
    """Simulate the active sessions tool logic."""
    available = _available_projects(state_path)
    active = []

    for slug in available:
        project_dir = state_path / "projects" / slug
        state = _read_project_state(project_dir)
        if not state:
            continue
        state = _apply_session_decay(state)
        if state.get("session_active"):
            active.append({
                "name": slug,
                "current_feature": state.get("current_feature"),
                "current_phase": state.get("current_phase"),
            })

    if not active:
        return {"summary": "No hay sesiones activas en este momento"}

    session_descs = []
    for s in active:
        parts = [s["name"]]
        if s.get("current_phase"):
            parts.append(s["current_phase"])
        if s.get("current_feature"):
            parts.append(s["current_feature"])
        session_descs.append(f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0])

    if len(active) == 1:
        summary = f"Hay 1 sesion activa: {session_descs[0]}"
    else:
        summary = f"Hay {len(active)} sesiones activas: {', '.join(session_descs)}"

    return {"summary": summary, "count": len(active)}


class TestProjectLiveStateSummary:
    """AC-04: summary field max 300 chars."""

    def test_summary_present(self, state_path: Path):
        _write_fresh_state(state_path, "proj-a")
        result = _simulate_get_project_live_state(state_path, "proj-a")
        assert "summary" in result
        assert len(result["summary"]) <= 300

    def test_summary_contains_project_name(self, state_path: Path):
        _write_fresh_state(state_path, "proj-a")
        result = _simulate_get_project_live_state(state_path, "proj-a")
        assert "proj-a" in result["summary"]

    def test_summary_no_iso_timestamps(self, state_path: Path):
        """AC-07: No raw ISO timestamps in summary."""
        _write_fresh_state(state_path, "proj-a")
        result = _simulate_get_project_live_state(state_path, "proj-a")
        iso_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"
        assert not re.search(iso_pattern, result["summary"])


class TestAllProjectsOverviewSummaryTable:
    """AC-05: summary_table is a Markdown table."""

    def test_summary_table_present(self, state_path: Path):
        _write_fresh_state(state_path, "proj-a")
        _write_fresh_state(state_path, "proj-b", current_feature="dashboard")
        result = _simulate_get_all_projects_overview(state_path)
        assert "summary_table" in result

    def test_summary_table_is_markdown(self, state_path: Path):
        _write_fresh_state(state_path, "proj-a")
        result = _simulate_get_all_projects_overview(state_path)
        table = result["summary_table"]
        lines = table.strip().split("\n")
        assert len(lines) >= 3
        assert "Proyecto" in lines[0]
        assert "---" in lines[1]


class TestActiveSessionsSummary:
    """AC-06: summary in Spanish."""

    def test_summary_with_active_sessions(self, state_path: Path):
        _write_fresh_state(state_path, "proj-a")
        result = _simulate_get_active_sessions(state_path)
        assert "summary" in result
        assert "sesion" in result["summary"].lower() or "sesiones" in result["summary"].lower()

    def test_summary_no_sessions(self, state_path: Path):
        _ensure_project_dir(state_path, "proj-a")
        result = _simulate_get_active_sessions(state_path)
        assert "summary" in result
        assert "No hay sesiones activas" in result["summary"]
