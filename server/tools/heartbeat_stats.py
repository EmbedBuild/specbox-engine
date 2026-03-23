"""Heartbeat observability tools — stats, logging, stale detection.

Provides MCP tools and helper functions for monitoring heartbeat health
across all registered projects.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastmcp import FastMCP

from .state import (
    _read_registry,
    _read_project_state,
    _available_projects,
    _ensure_project_dir,
)
from .live_state import _humanize_timedelta


def append_heartbeat_log(
    state_path: Path,
    project: str,
    source_ip: str,
    status: str = "ok",
) -> None:
    """Append a heartbeat receipt to the project's heartbeats.jsonl."""
    project_dir = _ensure_project_dir(state_path, project)
    log_file = project_dir / "heartbeats.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source_ip": source_ip or "unknown",
        "status": status,
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def compute_heartbeat_stats(state_path: Path) -> dict:
    """Compute heartbeat statistics across all projects.

    Returns total counts, per-project stats, and stale project alerts.
    """
    available = _available_projects(state_path)
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    staleness_threshold = timedelta(minutes=30)

    total_24h = 0
    by_project: dict[str, dict] = {}
    stale_projects: list[dict] = []

    for slug in available:
        project_dir = state_path / "projects" / slug
        log_file = project_dir / "heartbeats.jsonl"

        count_24h = 0
        last_heartbeat = None

        if log_file.exists():
            for line in log_file.read_text().strip().splitlines():
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    ts_str = entry.get("received_at") or entry.get("timestamp", "")
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts >= cutoff_24h:
                        count_24h += 1
                    if last_heartbeat is None or ts > last_heartbeat:
                        last_heartbeat = ts
                except (json.JSONDecodeError, ValueError):
                    continue

        total_24h += count_24h

        if count_24h > 0 or last_heartbeat:
            by_project[slug] = {
                "count_24h": count_24h,
                "last_heartbeat": last_heartbeat.isoformat() if last_heartbeat else None,
                "last_heartbeat_ago": _humanize_timedelta(
                    last_heartbeat.isoformat() if last_heartbeat else ""
                ),
            }

        # Check for stale projects — read RAW state (no decay) because
        # stale detection needs to see session_active=true even when old
        state = _read_project_state(project_dir)
        if state:
            if state.get("session_active"):
                received_at_str = state.get("received_at", "")
                if received_at_str:
                    try:
                        received_dt = datetime.fromisoformat(
                            received_at_str.replace("Z", "+00:00")
                        )
                        age = now - received_dt
                        if age > staleness_threshold:
                            stale_projects.append({
                                "project": slug,
                                "last_heartbeat_ago": _humanize_timedelta(received_at_str),
                                "age_minutes": int(age.total_seconds() / 60),
                            })
                    except (ValueError, TypeError):
                        stale_projects.append({
                            "project": slug,
                            "last_heartbeat_ago": "desconocido",
                            "age_minutes": -1,
                        })

    summary_parts = [f"{total_24h} heartbeats en 24h"]
    summary_parts.append(f"{len(by_project)} proyectos con actividad")
    if stale_projects:
        summary_parts.append(f"{len(stale_projects)} con heartbeat stale")

    return {
        "total_24h": total_24h,
        "projects_with_activity": len(by_project),
        "by_project": by_project,
        "stale_projects": stale_projects,
        "summary": " | ".join(summary_parts),
    }


def register_heartbeat_stats_tools(mcp: FastMCP, state_path: Path):
    """Register heartbeat observability MCP tools."""

    @mcp.tool
    def get_heartbeat_stats() -> dict:
        """Get heartbeat statistics across all projects.

        Returns total heartbeats in last 24h, per-project counts with
        last heartbeat timestamp, and alerts for stale projects (session
        active but no heartbeat in 30+ minutes).

        Designed for monitoring heartbeat health from mobile.
        """
        return compute_heartbeat_stats(state_path)
