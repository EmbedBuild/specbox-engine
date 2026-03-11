"""Tests for auth_gateway v2 — multi-backend credential management."""

import pytest
from unittest.mock import AsyncMock

from src.auth_gateway import (
    get_session_backend,
    get_session_client,
    store_session_credentials,
    store_plane_credentials,
    clear_session_credentials,
    AUTH_STATE_KEY,
    BACKEND_STATE_KEY,
)
from src.backends.trello_backend import TrelloBackend
from src.backends.plane_backend import PlaneBackend


# ── get_session_backend ──────────────────────────────────────────────


class TestGetSessionBackend:
    async def test_get_session_backend_trello_legacy(self):
        """Legacy path: BACKEND_STATE_KEY=None, AUTH_STATE_KEY has Trello creds."""
        state_map = {
            BACKEND_STATE_KEY: None,
            AUTH_STATE_KEY: {"api_key": "legacy_key", "token": "legacy_tok"},
        }

        ctx = AsyncMock()

        async def get_state_side_effect(key):
            return state_map.get(key)

        ctx.get_state = AsyncMock(side_effect=get_state_side_effect)

        backend = await get_session_backend(ctx)
        assert isinstance(backend, TrelloBackend)
        # Creds stored in internal client
        assert backend.client.api_key == "legacy_key"
        assert backend.client.token == "legacy_tok"

    async def test_get_session_backend_trello_unified(self):
        """Unified path: BACKEND_STATE_KEY has Trello config."""
        state_map = {
            BACKEND_STATE_KEY: {
                "backend_type": "trello",
                "api_key": "k",
                "token": "t",
            },
        }

        ctx = AsyncMock()

        async def get_state_side_effect(key):
            return state_map.get(key)

        ctx.get_state = AsyncMock(side_effect=get_state_side_effect)

        backend = await get_session_backend(ctx)
        assert isinstance(backend, TrelloBackend)
        assert backend.client.api_key == "k"
        assert backend.client.token == "t"

    async def test_get_session_backend_plane(self):
        """Unified path: BACKEND_STATE_KEY has Plane config."""
        state_map = {
            BACKEND_STATE_KEY: {
                "backend_type": "plane",
                "api_key": "k",
                "base_url": "https://plane.test",
                "workspace_slug": "ws",
            },
        }

        ctx = AsyncMock()

        async def get_state_side_effect(key):
            return state_map.get(key)

        ctx.get_state = AsyncMock(side_effect=get_state_side_effect)

        backend = await get_session_backend(ctx)
        assert isinstance(backend, PlaneBackend)
        assert backend.client.api_key == "k"
        assert backend.client.base_url == "https://plane.test"
        assert backend.client.workspace_slug == "ws"

    async def test_get_session_backend_no_creds(self):
        """No credentials at all → RuntimeError."""
        state_map = {
            BACKEND_STATE_KEY: None,
            AUTH_STATE_KEY: None,
        }

        ctx = AsyncMock()

        async def get_state_side_effect(key):
            return state_map.get(key)

        ctx.get_state = AsyncMock(side_effect=get_state_side_effect)

        with pytest.raises(RuntimeError, match="Backend credentials not configured"):
            await get_session_backend(ctx)


# ── store / clear ────────────────────────────────────────────────────


class TestStorePlaneCredentials:
    async def test_store_plane_credentials(self):
        """store_plane_credentials sets BACKEND_STATE_KEY with plane config."""
        ctx = AsyncMock()

        await store_plane_credentials(
            ctx,
            api_key="plane_key",
            base_url="https://plane.example.com",
            workspace_slug="my-ws",
        )

        ctx.set_state.assert_called_once_with(
            BACKEND_STATE_KEY,
            {
                "backend_type": "plane",
                "api_key": "plane_key",
                "base_url": "https://plane.example.com",
                "workspace_slug": "my-ws",
            },
        )


class TestStoreSessionCredentialsSetssBothKeys:
    async def test_store_session_credentials_sets_both_keys(self):
        """store_session_credentials writes both AUTH_STATE_KEY and BACKEND_STATE_KEY."""
        ctx = AsyncMock()

        await store_session_credentials(ctx, "mykey", "mytoken")

        calls = ctx.set_state.call_args_list
        assert len(calls) == 2

        # First call: legacy key
        assert calls[0].args == (AUTH_STATE_KEY, {"api_key": "mykey", "token": "mytoken"})
        # Second call: unified key
        assert calls[1].args == (
            BACKEND_STATE_KEY,
            {"backend_type": "trello", "api_key": "mykey", "token": "mytoken"},
        )


class TestClearSessionCredentials:
    async def test_clear_session_credentials(self):
        """clear_session_credentials deletes both keys."""
        ctx = AsyncMock()

        await clear_session_credentials(ctx)

        calls = ctx.delete_state.call_args_list
        assert len(calls) == 2
        deleted_keys = {c.args[0] for c in calls}
        assert deleted_keys == {AUTH_STATE_KEY, BACKEND_STATE_KEY}
