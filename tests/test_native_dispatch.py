"""Dispatch tests for UC-103 — wiring NativeBackend into auth_gateway / set_auth_token / discovery.

Covers the UC-103 acceptance criteria for backend dispatch:

- AC-07: ``native`` resolves end-to-end —
    * ``get_session_backend`` returns a :class:`NativeBackend` scoped to the
      session's ``project_id`` (test A);
    * ``store_native_credentials`` writes ONLY ``{backend_type, project_id}`` —
      no DSN / credential leaks into session state (Frontier 2) (test B);
    * ``detect_backend`` reports ``native`` from
      ``specbox.backend_type == "native"`` (test C).
- AC-09: NO-REGRESSION — the pre-existing freeform / plane / trello dispatch
  branches still resolve to their respective backends (test D).
- AC-08: a full native session round-trips US → UC → AC through a real
  Postgres (test E, SKIPS cleanly if no dev DB).

Tests A–D need NO database — ``NativeBackend.__init__`` is lazy (it only
stores ``project_id`` and never connects), so constructing one is free. Only
test E touches Postgres and is gated by the module-level reachability probe
(mirrors ``tests/test_native_schema.py``).
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from server.auth_gateway import (
    BACKEND_STATE_KEY,
    get_session_backend,
    store_native_credentials,
)
from server.app_docs.discovery import detect_backend
from server.backends.freeform_backend import FreeformBackend
from server.backends.native_backend import NativeBackend
from server.backends.plane_backend import PlaneBackend
from server.backends.trello_backend import TrelloBackend

# DSN + reachability probe live in tests/_native_db.py so Supabase TLS handling
# is applied consistently across native test modules [AC-38, AC-39].
from tests._native_db import DSN, reachable


def _mock_ctx(state_map: dict[str, object]) -> AsyncMock:
    """Build a ctx whose async get_state reads from ``state_map``.

    Mirrors tests/test_auth_gateway_v2.py: an async ``get_state`` side-effect
    over a dict, plus a plain (auto) ``set_state`` mock.
    """
    ctx = AsyncMock()

    async def get_state_side_effect(key):
        return state_map.get(key)

    ctx.get_state = AsyncMock(side_effect=get_state_side_effect)
    return ctx


# ── A) get_session_backend → NativeBackend [AC-07] (no PG) ───────────


class TestGetSessionBackendNative:
    async def test_resolves_native_backend_scoped_to_project_and_dev_token(self):
        """Native config → NativeBackend with project_id + dev_token wired [UC-505 AC-20]."""
        state_map = {
            BACKEND_STATE_KEY: {
                "backend_type": "native",
                "project_id": "p1",
                "dev_token": "t1",
            },
        }
        ctx = _mock_ctx(state_map)

        backend = await get_session_backend(ctx)

        assert isinstance(backend, NativeBackend)
        assert backend.project_id == "p1"
        assert backend._dev_token == "t1"


# ── B) store_native_credentials [AC-07 / Frontier 2] (no PG) ─────────


class TestStoreNativeCredentials:
    async def test_stores_backend_type_project_id_and_dev_token(self):
        """set_state called once with exactly {backend_type, project_id, dev_token} — no DSN [UC-505 AC-20]."""
        ctx = AsyncMock()

        await store_native_credentials(ctx, "proj-x", dev_token="t1")

        ctx.set_state.assert_called_once_with(
            BACKEND_STATE_KEY,
            {"backend_type": "native", "project_id": "proj-x", "dev_token": "t1"},
        )

    async def test_no_dsn_or_db_credential_key_present(self):
        """Frontier 2: the stored payload must NOT carry any DSN/db-credential key.

        The session DOES carry ``dev_token`` (Frontier 1 user credential) — that
        is intentional. What must never appear is a DSN, password, or any
        database-level credential. UC-505 keeps Frontier 2 intact.
        """
        ctx = AsyncMock()

        await store_native_credentials(ctx, "proj-y", dev_token="t1")

        _key, payload = ctx.set_state.call_args.args
        assert set(payload.keys()) == {"backend_type", "project_id", "dev_token"}
        forbidden_db_creds = {"dsn", "password", "credential", "credentials", "api_key", "secret"}
        assert not (set(payload.keys()) & forbidden_db_creds), (
            f"native session payload leaked a DB credential key: {payload.keys()}"
        )

    async def test_rejects_empty_dev_token(self):
        """UC-505 AC-21: empty dev_token is rejected at the entry point."""
        ctx = AsyncMock()
        with pytest.raises(ValueError, match="dev_token is required"):
            await store_native_credentials(ctx, "proj-z", dev_token="")
        ctx.set_state.assert_not_called()

    async def test_rejects_empty_project_id(self):
        """UC-505 AC-21 (defensive): empty project_id is also rejected."""
        ctx = AsyncMock()
        with pytest.raises(ValueError, match="project_id is required"):
            await store_native_credentials(ctx, "", dev_token="t1")
        ctx.set_state.assert_not_called()


# ── C) detect native backend [AC-07] (no PG) ─────────────────────────


class TestDetectNativeBackend:
    def test_detects_native_from_settings(self, tmp_path: Path):
        """specbox.backend_type == 'native' → detect_backend reports native."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir(parents=True)
        settings = {
            "specbox": {
                "backend_type": "native",
                "project_id": "native-proj-1",
            }
        }
        (claude_dir / "settings.local.json").write_text(json.dumps(settings), encoding="utf-8")

        result = detect_backend(str(tmp_path))

        assert result["backend_type"] == "native"
        assert result["source"] == "settings_specbox"
        assert result["native_project_id"] == "native-proj-1"


# ── D) NO-REGRESSION: freeform / plane / trello still resolve [AC-09] ─


class TestNoRegression:
    async def test_freeform_still_resolves(self, tmp_path: Path):
        state_map = {
            BACKEND_STATE_KEY: {
                "backend_type": "freeform",
                "root_path": str(tmp_path),
            },
        }
        ctx = _mock_ctx(state_map)

        backend = await get_session_backend(ctx)
        assert isinstance(backend, FreeformBackend)

    async def test_plane_still_resolves(self):
        state_map = {
            BACKEND_STATE_KEY: {
                "backend_type": "plane",
                "api_key": "k",
                "base_url": "https://plane.test",
                "workspace_slug": "ws",
            },
        }
        ctx = _mock_ctx(state_map)

        backend = await get_session_backend(ctx)
        assert isinstance(backend, PlaneBackend)
        assert backend.client.base_url == "https://plane.test"
        assert backend.client.workspace_slug == "ws"

    async def test_trello_still_resolves(self):
        state_map = {
            BACKEND_STATE_KEY: {
                "backend_type": "trello",
                "api_key": "k",
                "token": "t",
            },
        }
        ctx = _mock_ctx(state_map)

        backend = await get_session_backend(ctx)
        assert isinstance(backend, TrelloBackend)
        assert backend.client.api_key == "k"
        assert backend.client.token == "t"


# ── E) AC-08 native session round-trip [needs PG — SKIP if unreachable] ──
#
# The class below is only meaningful with a live DB; we gate it with a
# class-level skip flag computed once so the no-DB CI path stays green
# [AC-38, AC-39]. DSN + probe come from tests/_native_db (imported at top).
_PG_REACHABLE, _PG_SKIP_REASON = reachable()


class StatefulCtx:
    """A minimal ctx with async get_state/set_state backed by a dict.

    set_auth_token() and get_session_backend() both await get_state/set_state,
    so we back them with a real dict to model a single native session.
    """

    def __init__(self) -> None:
        self._state: dict[str, object] = {}

    async def get_state(self, key: str):
        return self._state.get(key)

    async def set_state(self, key: str, value: object) -> None:
        self._state[key] = value

    async def delete_state(self, key: str) -> None:
        self._state.pop(key, None)


@pytest.mark.skipif(not _PG_REACHABLE, reason=_PG_SKIP_REASON)
class TestNativeSessionRoundTrip:
    async def test_round_trip_us_uc_ac(self, monkeypatch: pytest.MonkeyPatch):
        """A native session created via set_auth_token round-trips US→UC→AC. [AC-08]"""
        from server.db.pool import close_pool, get_pool
        from server.tools.spec_driven import set_auth_token

        # Frontier 2: the pool reads the DSN only from SPECBOX_NATIVE_DSN — never
        # from session config. The dispatch path (set_auth_token → NativeBackend
        # → get_pool) has no DSN injection point by design, so we provide the
        # documented dev DSN via the env var for the duration of this test.
        monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)

        project_id = f"test-uc103-rt-{uuid.uuid4().hex[:8]}"
        ctx = StatefulCtx()

        try:
            # 1. Build a native session (no DSN passed — Frontier 2). UC-505
            # makes the dev_token mandatory; UC-502 then wires a mutation gate
            # that re-validates ``(token, project_id)`` against
            # ``mcp_tokens`` + ``project_members`` on every write. So before we
            # hit the gate via ``create_item`` we seed the dev identity for
            # the same clear token used by the session (registered + member).
            # UC-506 will move this seeding into the dispatch layer itself.
            auth = await set_auth_token(
                api_key="",
                token="dev-roundtrip-token",
                ctx=ctx,
                backend_type="native",
                project_id=project_id,
            )
            assert auth.get("success") is True, f"set_auth_token failed: {auth}"
            assert auth.get("backend") == "native"

            # Seed the developer + mcp_token + membership so the UC-502 gate
            # accepts the calls below. ``set_auth_token`` already created the
            # project row through ``setup_board`` so the FKs are satisfied.
            from server.migration.native_handling import seed_native_identity

            await seed_native_identity(await get_pool(), project_id, "dev-roundtrip", token="dev-roundtrip-token")

            # 2. Resolve the backend from the same session.
            backend = await get_session_backend(ctx)
            assert isinstance(backend, NativeBackend)
            assert backend.project_id == project_id

            board_id = project_id

            # 3. Create US → UC (child) → ACs through the backend.
            us = await backend.create_item(board_id, "US-01 Native round-trip story")
            assert us.meta.get("tipo") == "US"

            uc = await backend.create_item(
                board_id,
                "UC-101 Native round-trip use case",
                parent_id=us.id,
            )
            assert uc.meta.get("tipo") == "UC"
            assert uc.parent_id == us.id

            await backend.create_acceptance_criteria(
                board_id,
                uc.id,
                [
                    ("AC-01", "First criterion round-trips"),
                    ("AC-02", "Second criterion round-trips"),
                ],
            )

            # 4. List items back — the US and UC must both be present.
            items = await backend.list_items(board_id)
            names = {i.name for i in items}
            assert any("US-01" in n for n in names), f"US not found in {names}"
            assert any("UC-101" in n for n in names), f"UC not found in {names}"

            # 5. UC must be a child of the US.
            children = await backend.get_item_children(board_id, us.id)
            child_ids = {c.id for c in children}
            assert uc.id in child_ids, f"UC {uc.id} not a child of US {us.id}"

            # 6. ACs round-trip identical (text + count), by behavior not ids.
            acs = await backend.get_acceptance_criteria(board_id, uc.id)
            ac_texts = {ac.text for ac in acs}
            assert len(acs) == 2, f"expected 2 ACs, got {len(acs)}"
            assert ac_texts == {
                "First criterion round-trips",
                "Second criterion round-trips",
            }, f"AC texts did not round-trip: {ac_texts}"
            assert all(ac.done is False for ac in acs), "fresh ACs should be undone"

        finally:
            # Clean up ONLY the test project (CASCADE removes US/UC/AC), then
            # release the shared pool. Never DROP tables.
            try:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    await conn.execute(
                        "DELETE FROM projects WHERE project_id = $1",
                        project_id,
                    )
            finally:
                await close_pool()
