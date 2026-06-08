"""Tests for UC-1007 (US-10) — move_uc(done) releases the native reservation.

Root-cause fix symmetric to complete_uc: a UC closed with ``move_uc(target='done')``
must release its reservation, otherwise it lingers as an orphan in
``uc_reservations`` (the UC is ``done`` yet still shows in "Reservas activas"
until released by hand). Unlike complete_uc, move_uc emits ``OP_RELEASE_UC``
(not ``OP_COMPLETE_UC``) — moving is not a completion event, so the activity
feed must not record a fake completion.

ACs (local AC-01/02/03 = PRD AC-19/20/21):
- AC-19: native session, owner moves own UC to done → reservation released
  (PG-gated end-to-end).
- AC-20: release is best-effort — a UC reserved by ANOTHER developer is NOT
  force-released and move_uc still succeeds (PG-gated).
- AC-21: move_uc to a target OTHER than done (review) does NOT release the
  reservation; only `done` releases it (PG-gated). The native suite stays green.

Mirrors the harness of test_native_complete_release.py: PG-gated tests seed
identity via the pool and build the native session by hand
(store_native_credentials), avoiding the set_auth_token bootstrap.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import asyncpg
import pytest


# ── AC-21 unit: the release branch is gated on target == "done" ──


async def test_release_only_on_done_target_guard():
    """AC-21 (unit): the release call in move_uc is guarded by `target == "done"`.

    A static guard check complements the PG end-to-end below: confirms the source
    only enters the release branch for `done`, never for review/backlog/etc.
    """
    import inspect

    from server.tools import spec_driven

    src = inspect.getsource(spec_driven.move_uc)
    # The release must be conditioned on the done target, and must use the
    # honest release helper (not the complete_uc one).
    assert 'if target == "done":' in src
    assert "_release_reservation_native" in src
    assert "_release_uc_native" not in src, (
        "move_uc must NOT reuse the complete_uc helper (it would emit OP_COMPLETE_UC)"
    )


async def test_release_helper_emits_release_not_complete():
    """The move helper audits OP_RELEASE_UC, never OP_COMPLETE_UC (honest feed).

    Inspect the *code* (docstring stripped) so the assertion isn't fooled by the
    docstring, which legitimately names OP_COMPLETE_UC to explain why it is NOT used.
    """
    import ast
    import inspect
    import textwrap

    from server.tools import spec_driven

    src = textwrap.dedent(inspect.getsource(spec_driven._release_reservation_native))
    tree = ast.parse(src)
    func = tree.body[0]
    # Drop the leading docstring expression node before re-rendering the body.
    if (
        func.body
        and isinstance(func.body[0], ast.Expr)
        and isinstance(func.body[0].value, ast.Constant)
    ):
        func.body = func.body[1:]
    code_only = ast.unparse(func)
    assert "OP_RELEASE_UC" in code_only, "the move helper must audit a release event"
    assert "OP_COMPLETE_UC" not in code_only, (
        "move_uc release must NOT emit a completion event (it would pollute the activity feed)"
    )


# ── PG-gated AC-19 + AC-20 + AC-21 (real Postgres) ──────────────────

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
class TestMoveReleasesReservationPG:
    async def _seed(self, pg, pid, devs_with_tokens):
        from server.coordination.identity import (
            add_project_member,
            register_developer,
            register_mcp_token,
        )

        async with pg.acquire() as conn:
            await conn.execute(
                "INSERT INTO projects (project_id, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                pid,
                "UC-1007 move release test",
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

    async def test_move_to_done_releases_own_reservation(self, monkeypatch):
        """AC-19: native owner reserves (start_uc) then move_uc(done); the
        reservation is gone afterwards, just like complete_uc."""
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool
        from server.tools.spec_driven import get_session_backend, move_uc, start_uc

        monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
        pid = f"test-uc1007-done-{uuid.uuid4().hex[:8]}"
        token = "dev-uc1007-token"

        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(pg, pid, [("dev-uc1007", token)])
            ctx = await self._make_native_ctx(pid, token)

            backend = await get_session_backend(ctx)
            us = await backend.create_item(pid, "US-01 Move-done story")
            await backend.create_item(pid, "UC-01 Move-done use case", parent_id=us.id)
            await backend.close()

            started = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
            assert "error" not in started, f"start_uc failed: {started}"
            assert await self._reservation_count(pg, pid, "UC-01") == 1

            moved = await move_uc(board_id=pid, uc_id="UC-01", target="done", ctx=ctx)
            assert "error" not in moved, f"move_uc failed: {moved}"
            assert moved["new_status"] == "done"
            assert await self._reservation_count(pg, pid, "UC-01") == 0, (
                "AC-19: move_uc(done) must release the native reservation"
            )
        finally:
            try:
                async with pg.acquire() as conn:
                    await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                    await conn.execute("DELETE FROM developers WHERE developer_id = $1", "dev-uc1007")
            finally:
                await close_pool()

    async def test_move_to_review_keeps_reservation(self, monkeypatch):
        """AC-21: move_uc to a non-done target (review) must NOT release the
        reservation — the work stays attributable while in review."""
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool
        from server.tools.spec_driven import get_session_backend, move_uc, start_uc

        monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
        pid = f"test-uc1007-review-{uuid.uuid4().hex[:8]}"
        token = "dev-uc1007r-token"

        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(pg, pid, [("dev-uc1007r", token)])
            ctx = await self._make_native_ctx(pid, token)

            backend = await get_session_backend(ctx)
            us = await backend.create_item(pid, "US-01 Move-review story")
            await backend.create_item(pid, "UC-01 Move-review use case", parent_id=us.id)
            await backend.close()

            started = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
            assert "error" not in started, f"start_uc failed: {started}"
            assert await self._reservation_count(pg, pid, "UC-01") == 1

            moved = await move_uc(board_id=pid, uc_id="UC-01", target="review", ctx=ctx)
            assert "error" not in moved, f"move_uc failed: {moved}"
            assert moved["new_status"] == "review"
            assert await self._reservation_count(pg, pid, "UC-01") == 1, (
                "AC-21: move_uc(review) must NOT release the reservation"
            )
        finally:
            try:
                async with pg.acquire() as conn:
                    await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                    await conn.execute("DELETE FROM developers WHERE developer_id = $1", "dev-uc1007r")
            finally:
                await close_pool()

    async def test_move_to_done_does_not_release_other_devs_reservation(self, monkeypatch):
        """AC-20: best-effort. A UC reserved by ANOTHER developer is NOT
        force-released when a different developer moves it to done; move_uc
        still succeeds (the ownership error is swallowed)."""
        from server.coordination.reservations import reserve_uc
        from server.db.migrate import apply_migrations
        from server.db.pool import close_pool, init_pool
        from server.tools.spec_driven import get_session_backend, move_uc

        monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
        pid = f"test-uc1007-other-{uuid.uuid4().hex[:8]}"
        token_mover = "dev-mover-token"

        pg = await init_pool(dsn=DSN)
        try:
            await apply_migrations(pg)
            await self._seed(
                pg,
                pid,
                [("dev-mover", token_mover), ("dev-owner", "dev-owner-token")],
            )
            ctx = await self._make_native_ctx(pid, token_mover)

            backend = await get_session_backend(ctx)
            us = await backend.create_item(pid, "US-01 Other-owner story")
            await backend.create_item(pid, "UC-01 Other-owner use case", parent_id=us.id)
            await backend.close()

            async with pg.acquire() as conn:
                await reserve_uc(conn, project_id=pid, uc_id="UC-01", developer_id="dev-owner")
            assert await self._reservation_count(pg, pid, "UC-01") == 1

            moved = await move_uc(board_id=pid, uc_id="UC-01", target="done", ctx=ctx)
            assert "error" not in moved, f"move_uc should still succeed: {moved}"
            assert moved["new_status"] == "done"
            assert await self._reservation_count(pg, pid, "UC-01") == 1, (
                "AC-20: another developer's reservation must be left intact"
            )
        finally:
            try:
                async with pg.acquire() as conn:
                    await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                    await conn.execute(
                        "DELETE FROM developers WHERE developer_id = ANY($1::text[])",
                        ["dev-mover", "dev-owner"],
                    )
            finally:
                await close_pool()
