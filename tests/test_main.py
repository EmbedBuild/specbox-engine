"""Tests for __main__.py entry point."""

import pytest
from unittest.mock import patch


class TestMain:
    def test_main_calls_server_main(self):
        with patch("server.server.main") as mock_main:
            import importlib
            import server.__main__
            importlib.reload(server.__main__)
            # At least one call happened during reload
            assert mock_main.call_count >= 1
