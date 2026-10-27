"""Tests for server.py main() function."""

import os
import pytest
from unittest.mock import patch

#: A remote transport has to declare its policy (UC-10806); the tests that run it declare one.
REMOTE = {"SPECBOX_TRANSPORT_AUTH": "enforce"}


class TestServerMain:
    def test_main_defaults_to_streamable_http(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "streamable-http", **REMOTE}, clear=False), \
             patch("server.server.mcp") as mock_mcp:
            from server.server import main
            main()
            mock_mcp.run.assert_called_once()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "streamable-http"

    def test_main_stdio_transport(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}, clear=False), \
             patch("server.server.mcp") as mock_mcp:
            from server.server import main
            main()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "stdio"

    def test_main_sse_transport(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "sse", **REMOTE}, clear=False), \
             patch("server.server.mcp") as mock_mcp:
            from server.server import main
            main()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "sse"

    def test_main_invalid_transport_defaults(self):
        """Unknown MCP_TRANSPORT values fall back to stdio (the safest default
        for local sessions). Historically this was streamable-http; v5.23+
        switched the fallback to stdio to match `MCP_TRANSPORT` unset behaviour."""
        with patch.dict(os.environ, {"MCP_TRANSPORT": "invalid"}, clear=False), \
             patch("server.server.mcp") as mock_mcp:
            from server.server import main
            main()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "stdio"


class TestRemoteServerDeclaresItsPolicy:
    """UC-10806 AC-01: a remote transport without SPECBOX_TRANSPORT_AUTH does not start."""

    @pytest.mark.parametrize("transport", ["http", "streamable-http", "sse"])
    @pytest.mark.parametrize("value", [None, "", "  "])
    def test_remote_without_a_policy_does_not_start(self, transport, value):
        env = {"MCP_TRANSPORT": transport}
        if value is not None:
            env["SPECBOX_TRANSPORT_AUTH"] = value
        with patch.dict(os.environ, env, clear=False), patch("server.server.mcp") as mock_mcp:
            if value is None:
                os.environ.pop("SPECBOX_TRANSPORT_AUTH", None)
            from server.server import main
            with pytest.raises(SystemExit, match="SPECBOX_TRANSPORT_AUTH must be set"):
                main()
            mock_mcp.run.assert_not_called()

    @pytest.mark.parametrize("mode", ["off", "grace", "enforce"])
    def test_remote_with_a_declared_policy_starts(self, mode):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "http", "SPECBOX_TRANSPORT_AUTH": mode}, clear=False), \
             patch("server.server.mcp") as mock_mcp:
            from server.server import main
            main()
            mock_mcp.run.assert_called_once()

    def test_stdio_needs_no_policy(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}, clear=False), patch("server.server.mcp") as mock_mcp:
            os.environ.pop("SPECBOX_TRANSPORT_AUTH", None)
            from server.server import main
            main()
            mock_mcp.run.assert_called_once()
