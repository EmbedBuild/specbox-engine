"""Conversational MCP tools for querying live project state.

Designed for use from Claude.ai iOS via remote MCP connector.
These tools read from project_state.json (written by heartbeat or
GitHub sync) and return human-friendly summaries.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastmcp import FastMCP

from .state import (
    _read_registry,
    _read_project_state,
    _read_meta,
    _apply_session_decay,
    _available_projects,
)


def _humanize_timedelta(dt_iso: str) -> str:
    """Convert an ISO timestamp to a human-friendly 'ago' string."""
    if not dt_iso:
        return "desconocido"
    try:
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        minutes = int(delta.total_seconds() / 60)

        if minutes < 1:
            return "ahora mismo"
        if minutes < 60:
            return f"hace {minutes} minuto{'s' if minutes != 1 else ''}"
        hours = minutes // 60
        if hours < 24:
            return f"hace {hours} hora{'s' if hours != 1 else ''}"
        days = hours // 24
        if days < 7:
            return f"hace {days} dia{'s' if days != 1 else ''}"
        weeks = days // 7
        return f"hace {weeks} semana{'s' if weeks != 1 else ''}"
    except (ValueError, TypeError):
        return "desconocido"


def _health_emoji(state: dict) -> str:
    """Determine health emoji based on state freshness and healing health."""
    healing = state.get("healing_health", "healthy")
    received_at = state.get("received_at", "")

    if healing == "critical":
        return "red_circle"

    if not received_at:
        return "yellow_circle"

    try:
        dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - dt
        hours = age.total_seconds() / 3600

        if hours > 24:
            return "red_circle"
        if hours > 1 or healing == "degraded":
            return "yellow_circle"
        return "green_circle"
    except (ValueError, TypeError):
        return "yellow_circle"


def register_live_state_tools(mcp: FastMCP, state_path: Path):
    """Register conversational MCP tools for live project state queries."""

    @mcp.tool
    def get_project_live_state(slug: str) -> dict:
        """Get the live state of a specific project.

        Returns a consolidated snapshot including current phase, feature,
        plan progress, test coverage, feedback status, and session activity.
        Designed for conversational queries like "how is McProfit doing?".

        Args:
            slug: Project name/slug (e.g. 'mcprofit').
        """
        available = _available_projects(state_path)

        if slug not in available:
            return {
                "error": f"Proyecto '{slug}' no encontrado.",
                "available_projects": available,
            }

        project_dir = state_path / "projects" / slug
        state = _read_project_state(project_dir)

        if not state:
            # Fallback to meta.json
            meta = _read_meta(project_dir)
            if meta:
                return {
                    "project": slug,
                    "data_source": "meta_fallback",
                    "last_activity": meta.get("last_activity", "desconocido"),
                    "time_since_last_update": _humanize_timedelta(
                        meta.get("last_activity", "")
                    ),
                    "active_feature": meta.get("active_feature"),
                    "note": "No hay snapshot de heartbeat. Solo datos basicos de meta.",
                }
            return {
                "project": slug,
                "data_source": "none",
                "note": "No hay datos de estado para este proyecto.",
            }

        # Apply session decay
        state = _apply_session_decay(state)

        progress = state.get("plan_progress", {})
        total = progress.get("total_ucs", 0)
        done = progress.get("completed_ucs", 0)

        return {
            "project": slug,
            "data_source": state.get("source", "unknown"),
            "session_active": state.get("session_active", False),
            "current_phase": state.get("current_phase"),
            "current_feature": state.get("current_feature"),
            "current_branch": state.get("current_branch"),
            "plan_progress": f"{done}/{total} UCs" if total > 0 else None,
            "plan_current_uc": progress.get("current_uc"),
            "last_verdict": state.get("last_verdict"),
            "coverage_pct": state.get("coverage_pct"),
            "tests_passing": state.get("tests_passing", 0),
            "tests_failing": state.get("tests_failing", 0),
            "open_feedback": state.get("open_feedback", 0),
            "blocking_feedback": state.get("blocking_feedback", 0),
            "healing_health": state.get("healing_health"),
            "last_operation": state.get("last_operation"),
            "last_commit": state.get("last_commit"),
            "time_since_last_update": _humanize_timedelta(
                state.get("received_at", "")
            ),
            "health": _health_emoji(state),
        }

    @mcp.tool
    def get_all_projects_overview() -> dict:
        """Get an overview of all registered projects with live state.

        Returns a summary list ordered by most recent activity.
        Designed for "give me a summary of all my projects" queries.
        """
        registry = _read_registry(state_path)
        projects = registry.get("projects", {})

        items = []
        active_sessions = 0
        total_feedback = 0

        for slug in sorted(projects.keys()):
            project_dir = state_path / "projects" / slug
            info = projects[slug]
            state = _read_project_state(project_dir)

            if state:
                state = _apply_session_decay(state)
                session_active = state.get("session_active", False)
                if session_active:
                    active_sessions += 1
                fb = state.get("open_feedback", 0)
                total_feedback += fb

                items.append({
                    "name": slug,
                    "stack": info.get("stack", "unknown"),
                    "session_active": session_active,
                    "current_feature": state.get("current_feature"),
                    "last_operation": state.get("last_operation"),
                    "time_since_last_update": _humanize_timedelta(
                        state.get("received_at", "")
                    ),
                    "health": _health_emoji(state),
                    "received_at": state.get("received_at", ""),
                })
            else:
                meta = _read_meta(project_dir)
                items.append({
                    "name": slug,
                    "stack": info.get("stack", "unknown"),
                    "session_active": False,
                    "current_feature": meta.get("active_feature"),
                    "last_operation": None,
                    "time_since_last_update": _humanize_timedelta(
                        meta.get("last_activity", "")
                    ),
                    "health": "yellow_circle",
                    "received_at": meta.get("last_activity", ""),
                })

        # Sort by most recent activity
        items.sort(key=lambda x: x.get("received_at", ""), reverse=True)

        # Remove internal sort key
        for item in items:
            item.pop("received_at", None)

        return {
            "total_projects": len(items),
            "projects": items,
            "summary": (
                f"{len(items)} proyectos registrados, "
                f"{active_sessions} con sesion activa, "
                f"{total_feedback} con feedback abierto"
            ),
        }

    @mcp.tool
    def get_active_sessions() -> dict:
        """Get projects with an active Claude Code session.

        Returns only projects where session_active=true (after decay check).
        Designed for "what projects are being worked on right now?" queries.
        """
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
                    "current_branch": state.get("current_branch"),
                    "time_since_last_update": _humanize_timedelta(
                        state.get("received_at", "")
                    ),
                })

        if not active:
            return {
                "active_sessions": [],
                "message": "No hay sesiones activas en este momento",
            }

        return {
            "active_sessions": active,
            "count": len(active),
        }

    @mcp.tool
    def refresh_project_state(slug: str) -> dict:
        """Force-refresh a project's state from its GitHub repository.

        Ignores the 30-minute staleness rule and fetches the latest
        specbox-state.json directly from GitHub.

        Args:
            slug: Project name/slug (e.g. 'mcprofit').
        """
        available = _available_projects(state_path)
        if slug not in available:
            return {
                "error": f"Proyecto '{slug}' no encontrado.",
                "available_projects": available,
            }

        registry = _read_registry(state_path)
        project_info = registry.get("projects", {}).get(slug, {})
        repo_url = project_info.get("repo_url", "")

        if not repo_url:
            return {
                "error": f"Proyecto '{slug}' no tiene repo_url configurado.",
                "hint": "Configura repo_url en el registro del proyecto para habilitar GitHub sync.",
            }

        from ..github_sync import parse_repo_url, sync_project

        parsed = parse_repo_url(repo_url)
        if not parsed:
            return {
                "error": f"No se pudo parsear repo_url: {repo_url}",
                "hint": "Formato esperado: https://github.com/owner/repo o git@github.com:owner/repo.git",
            }

        owner, repo = parsed

        result = sync_project(
            owner=owner,
            repo=repo,
            state_path=state_path,
            project_slug=slug,
            force=True,
        )

        if result.get("status") == "updated":
            # Return the fresh state
            project_dir = state_path / "projects" / slug
            state = _read_project_state(project_dir)
            state = _apply_session_decay(state)
            result["current_state"] = state

        return result
