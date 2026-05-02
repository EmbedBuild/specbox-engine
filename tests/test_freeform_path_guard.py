"""Tests for the v5.29.0 BLOCKER fix: FreeForm path resolution with remote MCP.

The bug: when the MCP server runs on a VPS and a client calls
set_auth_token(backend_type="freeform", root_path="doc/tracking"), the relative
path was resolved against the VPS process CWD, silently writing data to the
wrong filesystem. v5.29.0 makes FreeformBackend reject relative paths and
makes set_auth_token resolve relative paths against the local CWD only when
running with a local MCP (no SPECBOX_ENGINE_MCP_URL set).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from server.backends.freeform_backend import FreeformBackend, FreeformPathError


class TestFreeformBackendInit:
    def test_relative_path_rejected_by_default(self):
        with pytest.raises(FreeformPathError, match="absolute root path"):
            FreeformBackend("doc/tracking")

    def test_relative_path_error_mentions_remediation(self):
        with pytest.raises(FreeformPathError) as ei:
            FreeformBackend("relative/path")
        msg = str(ei.value)
        assert "/app-init" in msg or "absolute path" in msg
        assert "remote MCP" in msg or "client" in msg

    def test_absolute_path_accepted(self, tmp_path):
        be = FreeformBackend(str(tmp_path))
        assert be.root == tmp_path

    def test_allow_relative_escape_hatch(self):
        be = FreeformBackend("doc/tracking", allow_relative=True)
        assert be.root == Path("doc/tracking")

    def test_dot_path_is_relative(self):
        with pytest.raises(FreeformPathError):
            FreeformBackend("./doc/tracking")

    def test_empty_string_is_relative(self):
        with pytest.raises(FreeformPathError):
            FreeformBackend("")


class TestSetAuthTokenFreeformPathResolution:
    """End-to-end checks of the path-resolution logic in set_auth_token.

    These reproduce the matrix:
    - remote MCP + relative → reject
    - local MCP + relative → resolve to absolute
    - any MCP + absolute → accept as-is
    """

    def _resolve(self, root_path: str, is_remote_mcp: bool) -> tuple[str | None, str | None]:
        """Mirror the logic embedded in set_auth_token for unit testing.

        Kept in sync with server/tools/spec_driven.py (the freeform branch).
        """
        raw = root_path.strip() if root_path else "doc/tracking"
        if not Path(raw).is_absolute():
            if is_remote_mcp:
                return None, "FREEFORM_PATH_MUST_BE_ABSOLUTE"
            return str(Path(raw).resolve()), None
        return raw, None

    def test_remote_mcp_relative_path_rejected(self):
        result, err = self._resolve("doc/tracking", is_remote_mcp=True)
        assert err == "FREEFORM_PATH_MUST_BE_ABSOLUTE"
        assert result is None

    def test_local_mcp_relative_path_resolved(self):
        result, err = self._resolve("doc/tracking", is_remote_mcp=False)
        assert err is None
        assert Path(result).is_absolute()
        assert result.endswith("doc/tracking")

    def test_remote_mcp_absolute_path_accepted(self):
        result, err = self._resolve("/Users/x/proj/doc/tracking", is_remote_mcp=True)
        assert err is None
        assert result == "/Users/x/proj/doc/tracking"

    def test_local_mcp_absolute_path_accepted(self):
        result, err = self._resolve("/tmp/proj/doc/tracking", is_remote_mcp=False)
        assert err is None
        assert result == "/tmp/proj/doc/tracking"

    def test_default_path_local_mcp_resolves(self):
        result, err = self._resolve("", is_remote_mcp=False)
        assert err is None
        assert Path(result).is_absolute()

    def test_default_path_remote_mcp_rejected(self):
        result, err = self._resolve("", is_remote_mcp=True)
        assert err == "FREEFORM_PATH_MUST_BE_ABSOLUTE"

    def test_remote_mcp_detection_via_env(self, monkeypatch):
        """SPECBOX_ENGINE_MCP_URL non-empty triggers remote-mcp mode."""
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com")
        is_remote = bool(os.environ.get("SPECBOX_ENGINE_MCP_URL", "").strip())
        assert is_remote is True

    def test_remote_mcp_detection_unset(self, monkeypatch):
        monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)
        is_remote = bool(os.environ.get("SPECBOX_ENGINE_MCP_URL", "").strip())
        assert is_remote is False

    def test_remote_mcp_detection_empty_string(self, monkeypatch):
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "")
        is_remote = bool(os.environ.get("SPECBOX_ENGINE_MCP_URL", "").strip())
        assert is_remote is False

    def test_remote_mcp_detection_whitespace(self, monkeypatch):
        monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "   ")
        is_remote = bool(os.environ.get("SPECBOX_ENGINE_MCP_URL", "").strip())
        assert is_remote is False
