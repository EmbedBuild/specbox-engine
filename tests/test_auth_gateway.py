"""Tests for auth_gateway module (per-session credentials)."""

import pytest
from unittest.mock import AsyncMock

from src.auth_gateway import get_session_client, store_session_credentials, clear_session_credentials, AUTH_STATE_KEY


class TestGetSessionClient:
    async def test_raises_when_no_credentials(self):
        ctx = AsyncMock()
        ctx.get_state.return_value = None
        with pytest.raises(RuntimeError, match="not configured"):
            await get_session_client(ctx)

    async def test_returns_client_with_credentials(self):
        ctx = AsyncMock()
        ctx.get_state.return_value = {"api_key": "k", "token": "t"}
        client = await get_session_client(ctx)
        assert client.api_key == "k"
        assert client.token == "t"
        await client.close()


class TestStoreSessionCredentials:
    async def test_stores_credentials(self):
        ctx = AsyncMock()
        await store_session_credentials(ctx, "mykey", "mytoken")
        ctx.set_state.assert_called_once_with(AUTH_STATE_KEY, {"api_key": "mykey", "token": "mytoken"})


class TestClearSessionCredentials:
    async def test_clears_credentials(self):
        ctx = AsyncMock()
        await clear_session_credentials(ctx)
        ctx.delete_state.assert_called_once_with(AUTH_STATE_KEY)
