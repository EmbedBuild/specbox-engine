"""Tests for server.py main() function."""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestServerMain:
    def test_main_defaults_to_streamable_http(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "streamable-http"}, clear=False), \
             patch("src.server.mcp") as mock_mcp:
            from src.server import main
            main()
            mock_mcp.run.assert_called_once()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "streamable-http"

    def test_main_stdio_transport(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}, clear=False), \
             patch("src.server.mcp") as mock_mcp:
            from src.server import main
            main()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "stdio"

    def test_main_sse_transport(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "sse"}, clear=False), \
             patch("src.server.mcp") as mock_mcp:
            from src.server import main
            main()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "sse"

    def test_main_invalid_transport_defaults(self):
        with patch.dict(os.environ, {"MCP_TRANSPORT": "invalid"}, clear=False), \
             patch("src.server.mcp") as mock_mcp:
            from src.server import main
            main()
            call_kwargs = mock_mcp.run.call_args
            assert call_kwargs[1]["transport"] == "streamable-http"
