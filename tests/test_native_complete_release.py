"""Tests for US-NATIVE-RESERVATION-RELEASE / UC-07.

``complete_uc`` must release the native reservation symmetrically to how
``start_uc`` reserves it (via ``_start_uc_native`` → ``start_uc_atomic``).
Without this, completing a UC leaves an orphan reservation: the UC is ``done``
yet still shows up in "Reservas activas" / ``get_satellite_queue``.

ACs:
- AC-01: native session, owner completes own UC → reservation released, gone
  from uc_reservations (PG-gated end-to-end).
- AC-02: non-native backend (freeform) → the release path is a no-op: complete_uc
  only enters it when _get_native_session_config(ctx) is not None (unit, no DB).
- AC-03: UC reserved by ANOTHER developer → complete_uc does NOT force-release
  it; the reservation is left intact (PG-gated end-to-end).

The PG-gated tests seed identity directly via the pool (the pattern of
test_coordination_reservations.TestReservationsRacePG) and build the native
session state by hand (store_native_credentials), avoiding the set_auth_token
bootstrap so the tests stay focused on complete_uc's release behaviour.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest


# ── AC-02: the release path is gated on a native session (unit, no DB) ──


class _FreeformCtx:
    """A ctx whose backend state is NOT native (freeform)."""

    def __init__(self) -> None:
        self._state: dict[str, object] = {
            "spec_backend_config": {"backend_type": "freeform", "project_id": "p"},
        }

    async def get_state(self, key: str):
        return self._state.get(key)

    async def set_state(self, key: str, value: object) -> None:
        self._state[key] = value


class _NoSessionCtx:
    async def get_state(self, key: str):
        return None

    async def set_state(self, key: str, value: object) -> None:  # pragma: no cover
        pass


async def test_release_path_skipped_for_freeform_session():
    """AC-02: _get_native_session_config returns None for a freeform session, so
    complete_uc's release branch (which is guarded by `is not None`) never runs —
    no regression for non-native backends, which have no reservations to release.
    """
    from server.tools.spec_driven import _get_native_session_config

    assert await _get_native_session_config(_FreeformCtx()) is None
    assert await _get_native_session_config(_NoSessionCtx()) is None


async def test_release_path_active_only_for_native_session():
    """AC-02 (complement): a native session IS recognised, so the release branch
    would run — confirming the guard discriminates by backend_type, not blanket-off.
    """
    from server.tools.spec_driven import _get_native_session_config

    class _NativeCtx:
        async def get_state(self, key: str):
            return {"backend_type": "native", "project_id": "p", "dev_token": "t"}

    cfg = await _get_native_session_config(_NativeCtx())
    assert cfg is not None
    assert cfg["backend_type"] == "native"


# ── PG-gated AC-01 + AC-03 (real Postgres) ──────────────────────────

_DEV_DSN = "postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"
DSN = os.environ.get("SPECBOX_NATIVE_DSN", _DEV_DSN)


def _probe(dsn: str) -> None:
    async def _connect() -> None:
        conn = await asyncio.wait_for(asyncpg.connect(dsn), timeout=2.0)
        try:
            await conn.execute("SELECT 1")
        finally:
            await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_connect())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


try:
    _probe(DSN)
    _PG_REACHABLE = True
    _PG_SKIP_REASON = ""
except Exception as exc:  # noqa: BLE001
    _PG_REACHABLE = False
    _PG_SKIP_REASON = f"dev Postgres not reachable ({exc!r}); run docker compose -f docker-compose.dev.yml up -d"


class _StatefulCtx:
    """Minimal ctx with async get_state/set_state backed by a dict."""

    def __init__(self) -> None:
        self._state: dict[str, object] = {}

    async def get_state(self, key: str):
        return self._state.get(key)

    async def set_state(self, key: str, value: object) -> None:
        self._state[key] = value

    async def delete_state(self, key: str) -> None:
        self._state.pop(key, None)


@pytest.mark.skipif(not _PG_REACHABLE, reason=_PG_SKIP_REASON)
class TestCompleteReleasesReservationPG:
    async def _seed(self, pg, pid, devs_with_tokens):
        """Create the project + register each developer, mint their token, add
        them as member. ``devs_with_tokens`` is a list of (developer_id, token)."""
        from server.coordination.identity import (
            add_project_member,
            register_developer,
            register_mcp_token,
        )

        async with pg.acquire() as conn:
            await conn.execute(
                "INSERT INTO projects (project_id, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                pid,
                "UC-07 release test",
            )
            for dev, token in devs_with_tokens:
                await register_developer(conn, developer_id=dev, display_name=dev)
                await register_mcp_token(conn, developer_id=dev, token=token)
                await add_project_member(conn, project_id=pid, developer_id=dev)

    async def _make_native_ctx(self, pid, token):
        from server.tools.spec_driven import store_native_credentials

        ctx = _StatefulCtx()
        await store_native_credentials(ctx, pid, dev_token=token)
        return ctx

    async def _reservation_count(self, pg, project_id, uc_id) -> int:
        async with pg.acquire() as conn:
            return await conn.fetchval(
                "SELECT count(*) FROM uc_reservations WHERE project_id = $1 AND uc_id = $2",
                project_id,
                uc_id,
            )

    async def test_complete_uc_releases_own_reservation(self, monkeypatch):
        """AC-01: native owner reserves (start_uc) then completes (complete_uc);
        the reservation is gone afterwards."""
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool
        from server.tools.spec_driven import complete_uc, get_session_backend, start_uc

        monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
        pid = f"test-uc07-rel-{uuid.uuid4().hex[:8]}"
        token = "dev-uc07-token"

        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(pg, pid, [("dev-uc07", token)])
            ctx = await self._make_native_ctx(pid, token)

            # Build US + UC through the native backend.
            backend = await get_session_backend(ctx)
            us = await backend.create_item(pid, "US-01 Release story")
            await backend.create_item(pid, "UC-01 Release use case", parent_id=us.id)
            await backend.close()

            # Reserve via start_uc (native → _start_uc_native → start_uc_atomic).
            started = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
            assert "error" not in started, f"start_uc failed: {started}"
            assert await self._reservation_count(pg, pid, "UC-01") == 1, (
                "start_uc should have created exactly one reservation"
            )

            # Complete → reservation must be released (the fix).
            done = await complete_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
            assert "error" not in done, f"complete_uc failed: {done}"
            assert await self._reservation_count(pg, pid, "UC-01") == 0, (
                "AC-01: complete_uc must release the native reservation"
            )
        finally:
            try:
                async with pg.acquire() as conn:
                    await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                    await conn.execute("DELETE FROM developers WHERE developer_id = $1", "dev-uc07")
            finally:
                await close_pool()

    async def test_complete_uc_does_not_release_other_devs_reservation(self, monkeypatch):
        """AC-03: a UC reserved by ANOTHER developer is NOT force-released when a
        different developer completes it; the reservation stays intact."""
        from server.coordination.reservations import reserve_uc
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool
        from server.tools.spec_driven import complete_uc, get_session_backend

        monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
        pid = f"test-uc07-other-{uuid.uuid4().hex[:8]}"
        token_completer = "dev-completer-token"

        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            # Both developers are members; the session belongs to the completer.
            await self._seed(
                pg,
                pid,
                [("dev-completer", token_completer), ("dev-owner", "dev-owner-token")],
            )
            ctx = await self._make_native_ctx(pid, token_completer)

            backend = await get_session_backend(ctx)
            us = await backend.create_item(pid, "US-01 Other-owner story")
            await backend.create_item(pid, "UC-01 Other-owner use case", parent_id=us.id)
            await backend.close()

            # dev-owner (NOT the session dev) reserves the UC.
            async with pg.acquire() as conn:
                await reserve_uc(conn, project_id=pid, uc_id="UC-01", developer_id="dev-owner")
            assert await self._reservation_count(pg, pid, "UC-01") == 1

            # The completer completes the UC. The reservation is owned by
            # dev-owner → must NOT be force-released; complete_uc must still
            # succeed (best-effort release swallows the ownership error).
            done = await complete_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
            assert "error" not in done, f"complete_uc should still succeed: {done}"
            assert await self._reservation_count(pg, pid, "UC-01") == 1, (
                "AC-03: another developer's reservation must be left intact"
            )
        finally:
            try:
                async with pg.acquire() as conn:
                    await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                    await conn.execute(
                        "DELETE FROM developers WHERE developer_id = ANY($1::text[])",
                        ["dev-completer", "dev-owner"],
                    )
            finally:
                await close_pool()
