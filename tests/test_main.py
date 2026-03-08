"""Tests for __main__.py entry point."""

import pytest
from unittest.mock import patch


class TestMain:
    def test_main_calls_server_main(self):
        with patch("src.server.main") as mock_main:
            import importlib
            import src.__main__
            importlib.reload(src.__main__)
            # At least one call happened during reload
            assert mock_main.call_count >= 1
