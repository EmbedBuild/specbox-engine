"""GitHub Sync — reads specbox-state.json from project repos via GitHub API.

Used to keep project state fresh when the local machine is off.
Heartbeat always has priority: sync only updates if the last heartbeat
is older than 30 minutes (configurable).
"""

import base64
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx


def parse_repo_url(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL.

    Supports:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - git@github.com:owner/repo.git
    """
    if not url:
        return None

    # HTTPS format
    m = re.match(r"https?://github\.com/([^/]+)/([^/.]+)(?:\.git)?/?$", url)
    if m:
        return m.group(1), m.group(2)

    # SSH format
    m = re.match(r"git@github\.com:([^/]+)/([^/.]+)(?:\.git)?$", url)
    if m:
        return m.group(1), m.group(2)

    return None


def sync_project(
    owner: str,
    repo: str,
    state_path: Path,
    project_slug: str,
    branch: str = "main",
    force: bool = False,
    staleness_minutes: int = 30,
) -> dict:
    """Sync a single project's state from its GitHub repo.

    Reads specbox-state.json from the repo via GitHub API and updates
    project_state.json if the existing heartbeat is stale enough.

    Args:
        owner: GitHub repo owner.
        repo: GitHub repo name.
        state_path: Path to /data/state.
        project_slug: Project name in registry.
        branch: Git branch to read from.
        force: If True, ignore staleness check.
        staleness_minutes: Only update if heartbeat is older than this.

    Returns:
        Dict with status, reason, and metadata.
    """
    from .tools.state import (
        _ensure_project_dir,
        _read_project_state,
        _write_project_state,
        _read_meta,
        _write_meta,
        _invalidate_cache,
    )

    project_dir = _ensure_project_dir(state_path, project_slug)

    # Check staleness BEFORE requiring token — if heartbeat is fresh, skip early
    if not force:
        existing = _read_project_state(project_dir)
        if existing:
            received_at = existing.get("received_at", "")
            if received_at:
                try:
                    received_dt = datetime.fromisoformat(
                        received_at.replace("Z", "+00:00")
                    )
                    age = datetime.now(timezone.utc) - received_dt
                    age_minutes = age.total_seconds() / 60
                    if age_minutes < staleness_minutes:
                        return {
                            "project": project_slug,
                            "status": "skipped",
                            "reason": f"Heartbeat is fresh ({int(age_minutes)}min old, threshold={staleness_minutes}min)",
                            "last_state_age_minutes": int(age_minutes),
                        }
                except (ValueError, TypeError):
                    pass

    github_token = os.getenv("GITHUB_TOKEN", "")
    if not github_token:
        return {
            "project": project_slug,
            "status": "failed",
            "reason": "GITHUB_TOKEN env var not configured",
        }

    # Fetch specbox-state.json from GitHub
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/specbox-state.json"
    params = {"ref": branch}
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers, params=params)

        if resp.status_code == 404:
            return {
                "project": project_slug,
                "status": "failed",
                "reason": f"specbox-state.json not found in {owner}/{repo}@{branch}",
            }

        if resp.status_code != 200:
            return {
                "project": project_slug,
                "status": "failed",
                "reason": f"GitHub API returned {resp.status_code}",
            }

        data = resp.json()
        content = base64.b64decode(data.get("content", "")).decode("utf-8")
        remote_state = json.loads(content)

    except (httpx.HTTPError, json.JSONDecodeError, KeyError) as exc:
        return {
            "project": project_slug,
            "status": "failed",
            "reason": f"Error fetching from GitHub: {exc}",
        }

    # Build project_state from remote data
    now = datetime.now(timezone.utc).isoformat()
    state_data = {
        "project": project_slug,
        "timestamp": remote_state.get("timestamp", now),
        "received_at": now,
        "source": "github_sync",
        "session_active": False,  # If reading from GitHub, session is not active
        "current_phase": remote_state.get("current_phase"),
        "current_feature": remote_state.get("current_feature"),
        "current_branch": remote_state.get("current_branch"),
        "plan_progress": {
            "total_ucs": remote_state.get("plan_total_ucs", 0),
            "completed_ucs": remote_state.get("plan_completed_ucs", 0),
            "current_uc": remote_state.get("plan_current_uc"),
        },
        "last_verdict": remote_state.get("last_verdict"),
        "coverage_pct": remote_state.get("coverage_pct"),
        "tests_passing": remote_state.get("tests_passing", 0),
        "tests_failing": remote_state.get("tests_failing", 0),
        "open_feedback": remote_state.get("open_feedback", 0),
        "blocking_feedback": remote_state.get("blocking_feedback", 0),
        "healing_health": remote_state.get("healing_health", "healthy"),
        "self_healing_events": remote_state.get("self_healing_events", 0),
        "last_operation": remote_state.get("last_operation", "idle"),
        "last_commit": remote_state.get("last_commit"),
        "last_commit_at": remote_state.get("last_commit_at"),
    }

    _write_project_state(project_dir, state_data)

    # Update meta
    meta = _read_meta(project_dir)
    meta["last_activity"] = state_data["timestamp"]
    _write_meta(project_dir, meta)

    _invalidate_cache(state_path)

    return {
        "project": project_slug,
        "status": "updated",
        "reason": f"Synced from {owner}/{repo}@{branch}",
        "source_timestamp": remote_state.get("timestamp", ""),
    }


def sync_all(
    state_path: Path,
    force: bool = False,
    staleness_minutes: int = 30,
) -> list[dict]:
    """Sync all registered projects that have a repo_url configured.

    Returns a list of per-project result dicts.
    """
    from .tools.state import _read_registry

    registry = _read_registry(state_path)
    projects = registry.get("projects", {})

    results = []
    for slug, info in sorted(projects.items()):
        repo_url = info.get("repo_url", "")
        parsed = parse_repo_url(repo_url)
        if not parsed:
            continue  # Skip projects without valid repo_url (AC-21)

        owner, repo = parsed
        result = sync_project(
            owner=owner,
            repo=repo,
            state_path=state_path,
            project_slug=slug,
            force=force,
            staleness_minutes=staleness_minutes,
        )
        results.append(result)

    return results
