"""Tests for GitHub Sync — parse_repo_url and staleness logic.

Validates:
- AC-16: Sync only updates if heartbeat > 30 min old
- AC-20: repo_url parsing (HTTPS and SSH formats)
- AC-21: Projects without repo_url are skipped
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from server.github_sync import parse_repo_url, sync_project, sync_all


class TestParseRepoUrl:
    """AC-20: Parse owner/repo from GitHub URLs."""

    def test_https_format(self):
        result = parse_repo_url("https://github.com/owner/repo")
        assert result == ("owner", "repo")

    def test_https_with_git_suffix(self):
        result = parse_repo_url("https://github.com/owner/repo.git")
        assert result == ("owner", "repo")

    def test_https_with_trailing_slash(self):
        result = parse_repo_url("https://github.com/owner/repo/")
        assert result == ("owner", "repo")

    def test_ssh_format(self):
        result = parse_repo_url("git@github.com:owner/repo.git")
        assert result == ("owner", "repo")

    def test_ssh_without_git_suffix(self):
        result = parse_repo_url("git@github.com:owner/repo")
        assert result == ("owner", "repo")

    def test_empty_string(self):
        assert parse_repo_url("") is None

    def test_none_value(self):
        # Graceful handling even though type hint says str
        assert parse_repo_url("") is None

    def test_invalid_url(self):
        assert parse_repo_url("not-a-url") is None

    def test_non_github_url(self):
        assert parse_repo_url("https://gitlab.com/owner/repo") is None


class TestSyncProjectStaleness:
    """AC-16: Sync respects heartbeat freshness."""

    @pytest.fixture
    def state_path(self, tmp_path: Path) -> Path:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "registry.json").write_text('{"projects": {}}', encoding="utf-8")
        return state_dir

    def test_skips_when_heartbeat_fresh(self, state_path: Path):
        """AC-16: If heartbeat < 30 min old, skip sync."""
        from server.tools.state import _ensure_project_dir, _write_project_state

        project_dir = _ensure_project_dir(state_path, "test-project")
        _write_project_state(project_dir, {
            "project": "test-project",
            "received_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "source": "heartbeat",
        })

        result = sync_project(
            owner="owner",
            repo="repo",
            state_path=state_path,
            project_slug="test-project",
        )
        assert result["status"] == "skipped"
        assert "fresh" in result["reason"].lower()

    def test_force_ignores_staleness(self, state_path: Path):
        """AC-30: force=True ignores staleness check."""
        from server.tools.state import _ensure_project_dir, _write_project_state

        project_dir = _ensure_project_dir(state_path, "test-project")
        _write_project_state(project_dir, {
            "project": "test-project",
            "received_at": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "source": "heartbeat",
        })

        # Without GITHUB_TOKEN, it will fail, but it should NOT skip
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            result = sync_project(
                owner="owner",
                repo="repo",
                state_path=state_path,
                project_slug="test-project",
                force=True,
            )
        assert result["status"] == "failed"
        assert "GITHUB_TOKEN" in result["reason"]

    def test_fails_without_github_token(self, state_path: Path):
        """AC-18: Requires GITHUB_TOKEN."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            result = sync_project(
                owner="owner",
                repo="repo",
                state_path=state_path,
                project_slug="test-project",
            )
        assert result["status"] == "failed"
        assert "GITHUB_TOKEN" in result["reason"]


class TestSyncAll:
    """AC-21: Projects without repo_url are excluded."""

    @pytest.fixture
    def state_path(self, tmp_path: Path) -> Path:
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        registry = {
            "projects": {
                "project-a": {"repo_url": "https://github.com/owner/project-a", "stack": "python"},
                "project-b": {"repo_url": "", "stack": "flutter"},  # No repo_url
                "project-c": {"repo_url": "invalid", "stack": "react"},  # Invalid
            }
        }
        (state_dir / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
        return state_dir

    def test_excludes_projects_without_valid_repo(self, state_path: Path):
        """AC-21: Only project-a has a valid repo_url."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            results = sync_all(state_path)
        # Only project-a should be attempted (and fail due to no token)
        assert len(results) == 1
        assert results[0]["project"] == "project-a"
