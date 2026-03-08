"""Tests for tools/auth.py."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.tools.auth import set_auth_token


class TestSetAuthToken:
    async def test_empty_api_key(self, mock_ctx):
        result = await set_auth_token("", "token", mock_ctx)
        assert result["code"] == "MISSING_API_KEY"

    async def test_empty_token(self, mock_ctx):
        result = await set_auth_token("key", "", mock_ctx)
        assert result["code"] == "MISSING_TOKEN"

    async def test_successful_auth(self, mock_ctx):
        mock_client = AsyncMock()
        mock_client.get_me.return_value = {
            "id": "user123",
            "username": "testuser",
            "fullName": "Test User",
        }
        mock_client.close = AsyncMock()

        with patch("src.tools.auth.TrelloClient", return_value=mock_client):
            result = await set_auth_token("valid_key", "valid_token", mock_ctx)

        assert result["success"] is True
        assert result["user"]["username"] == "testuser"
        assert "Test User" in result["message"]

    async def test_invalid_credentials(self, mock_ctx):
        import httpx
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_client.get_me.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )
        mock_client.close = AsyncMock()

        with patch("src.tools.auth.TrelloClient", return_value=mock_client):
            result = await set_auth_token("bad_key", "bad_token", mock_ctx)

        assert result["code"] == "INVALID_CREDENTIALS"

    async def test_connection_error(self, mock_ctx):
        mock_client = AsyncMock()
        mock_client.get_me.side_effect = Exception("Connection refused")
        mock_client.close = AsyncMock()

        with patch("src.tools.auth.TrelloClient", return_value=mock_client):
            result = await set_auth_token("key", "token", mock_ctx)

        assert result["code"] == "CONNECTION_ERROR"
