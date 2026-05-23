"""Integration tests for the UC-502 mutation gate.

Real-Postgres tests gated by ``PG_OK`` (see :mod:`tests._native_db`). Each
test creates its own throwaway ``project_id`` so they can run in parallel
without colliding. Cleanup is best-effort — Postgres cascades drop child
rows when the project is deleted.

Acceptance criteria covered:

* AC-03 (parametrized over the 9 mutators) — a developer whose token is
  revoked between the construction of ``NativeBackend`` and the mutation
  call must be rejected with :class:`UnauthenticatedError`. The cache is
  forcibly invalidated so the revocation is observed immediately.
* AC-04 — a developer with a valid token but no membership in the target
  project must be rejected with :class:`ForbiddenError`. Same parametrization
  over the 9 mutators.
* AC-05 — the revoke + cache-invalidate sequence works: a mutation that
  succeeds while the token is active starts failing after revoke + clear.
* AC-06 — reads must NOT pass through the cached gate (forensics need to
  remain available even for revoked tokens).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from server.backends.native_backend import NativeBackend
from server.coordination.identity import (
    ForbiddenError,
    UnauthenticatedError,
    _clear_auth_cache,
    add_project_member,
    register_developer,
    register_mcp_token,
    revoke_mcp_token,
)
from server.db.migrate import apply_migrations
from server.db.pool import close_pool, init_pool

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()

pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ── Helpers ──────────────────────────────────────────────────────────


def _unique_pid() -> str:
    return f"test-uc502-{uuid.uuid4().hex[:8]}"


def _unique_dev() -> str:
    return f"dev-uc502-{uuid.uuid4().hex[:6]}"


def _unique_token() -> str:
    return f"tok-uc502-{uuid.uuid4().hex}"


async def _seed_project(pool, *, project_id: str, developer_id: str, token: str, add_member: bool = True) -> str:
    """Create project + developer + token + (optional) membership.

    Returns the ``token_id`` minted by ``register_mcp_token``.
    """
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO projects (project_id, name) VALUES ($1, $2)",
            project_id,
            "UC-502 mutation authz",
        )
        await register_developer(conn, developer_id=developer_id, display_name="Tester")
        token_id = await register_mcp_token(conn, developer_id=developer_id, token=token)
        if add_member:
            await add_project_member(conn, project_id=project_id, developer_id=developer_id)
        return token_id


async def _seed_us_uc_acs(backend: NativeBackend, board_id: str) -> tuple[str, str, list[str]]:
    """Create one US + one UC + 3 ACs. Returns ``(us_id, uc_id, [ac_id, ...])``."""
    us = await backend.create_item(board_id, name="US-99: UC-502 fixture", labels=["US"])
    uc = await backend.create_item(board_id, name="UC-901: UC-502 fixture", labels=["UC"], parent_id=us.id)
    await backend.create_acceptance_criteria(
        board_id,
        uc.id,
        [("AC-01", "alpha"), ("AC-02", "beta"), ("AC-03", "gamma")],
    )
    return us.id, uc.id, ["AC-01", "AC-02", "AC-03"]


async def _count(pool, table: str, project_id: str) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(f"SELECT count(*) FROM {table} WHERE project_id = $1", project_id)


async def _delete_project(pool, project_id: str, developer_id: str | None = None) -> None:
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        if developer_id is not None:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_cache_each_test():
    """Drop the shared cache before/after every test for deterministic gates."""
    _clear_auth_cache()
    yield
    _clear_auth_cache()


@pytest.fixture
async def db_pool() -> AsyncIterator:
    """Initialise the asyncpg pool + apply migrations once per test.

    Each test then carves out its own ``project_id`` so they do not collide.
    """
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    yield pool
    await close_pool()


# ── Mutator catalogue ────────────────────────────────────────────────


def _mutators_for(uc_id: str, ac_ids: list[str]):
    """Return ``(name, callable(backend, board_id), table_for_count)`` triples.

    Each callable executes the mutator with the minimal valid argument set
    against the fixture data prepared by :func:`_seed_us_uc_acs`. ``table_for_count``
    is used to assert that a rejected mutation does NOT alter row counts.
    """
    return [
        (
            "create_item",
            lambda be, b: be.create_item(b, name="US-77: should not insert"),
            "user_stories",
        ),
        (
            "update_item",
            lambda be, b: be.update_item(b, uc_id, name="UC-901: tampered"),
            "use_cases",
        ),
        (
            "mark_acceptance_criterion",
            lambda be, b: be.mark_acceptance_criterion(b, uc_id, ac_ids[0], True),
            "acceptance_criteria",
        ),
        (
            "create_acceptance_criteria",
            lambda be, b: be.create_acceptance_criteria(b, uc_id, [("AC-99", "tampered")]),
            "acceptance_criteria",
        ),
        (
            "update_acceptance_criterion",
            lambda be, b: be.update_acceptance_criterion(b, uc_id, ac_ids[1], text="tampered"),
            "acceptance_criteria",
        ),
        (
            "delete_acceptance_criterion",
            lambda be, b: be.delete_acceptance_criterion(b, uc_id, ac_ids[2]),
            "acceptance_criteria",
        ),
        (
            "archive_item",
            lambda be, b: be.archive_item(b, uc_id, reason="tampered"),
            "use_cases",
        ),
        (
            "add_comment",
            lambda be, b: be.add_comment(b, uc_id, "tampered"),
            "use_cases",
        ),
        (
            "add_attachment",
            lambda be, b: be.add_attachment(b, uc_id, "evidence.pdf", b"raw-bytes", "application/pdf"),
            "use_cases",
        ),
    ]


# ── AC-03: revoked token → UNAUTHENTICATED for every mutator ─────────


@pytest.mark.parametrize(
    "mutator_index",
    list(range(9)),
    ids=[
        "create_item",
        "update_item",
        "mark_acceptance_criterion",
        "create_acceptance_criteria",
        "update_acceptance_criterion",
        "delete_acceptance_criterion",
        "archive_item",
        "add_comment",
        "add_attachment",
    ],
)
async def test_ac03_revoked_token_blocks_each_mutator(db_pool, mutator_index):
    """A revoked token must reject every mutation, with no row changes [AC-03]."""
    pid = _unique_pid()
    dev_id = _unique_dev()
    token = _unique_token()
    token_id = await _seed_project(db_pool, project_id=pid, developer_id=dev_id, token=token, add_member=True)
    try:
        backend = NativeBackend(project_id=pid, dev_token=token)
        await backend.setup_board("UC-502 AC-03")
        us_id, uc_id, ac_ids = await _seed_us_uc_acs(backend, pid)

        # Snapshot row counts BEFORE revoke so any side-effect is detectable.
        snapshots: dict[str, int] = {}
        for table in ("user_stories", "use_cases", "acceptance_criteria"):
            snapshots[table] = await _count(db_pool, table, pid)

        # Revoke + invalidate cache → next call must hit the uncached gate.
        async with db_pool.acquire() as conn:
            assert await revoke_mcp_token(conn, token_id=token_id) is True
        _clear_auth_cache()

        mutators = _mutators_for(uc_id, ac_ids)
        name, run, watched_table = mutators[mutator_index]

        with pytest.raises(UnauthenticatedError):
            await run(backend, pid)

        # The row count of the watched table must be unchanged.
        after = await _count(db_pool, watched_table, pid)
        assert after == snapshots[watched_table], (
            f"{name} altered {watched_table} ({snapshots[watched_table]} -> {after}) despite UNAUTHENTICATED"
        )
    finally:
        await _delete_project(db_pool, pid, dev_id)


# ── AC-04: valid token, non-member project → FORBIDDEN ───────────────


@pytest.mark.parametrize(
    "mutator_index",
    list(range(9)),
    ids=[
        "create_item",
        "update_item",
        "mark_acceptance_criterion",
        "create_acceptance_criteria",
        "update_acceptance_criterion",
        "delete_acceptance_criterion",
        "archive_item",
        "add_comment",
        "add_attachment",
    ],
)
async def test_ac04_non_member_blocks_each_mutator(db_pool, mutator_index):
    """Valid token + no project_members row → FORBIDDEN, no row changes [AC-04]."""
    # Two projects: one where the dev is a member (for fixture seeding), and a
    # second where the dev is NOT a member (the target of the rejected calls).
    member_pid = _unique_pid()
    target_pid = _unique_pid()
    dev_id = _unique_dev()
    token = _unique_token()

    # Seed the member project so we can use the dev's good token to build the
    # fixture US/UC/ACs in the TARGET project. Then we'll swap the membership
    # away from the target. Trick: we build the fixture by inserting rows
    # directly with the pool, bypassing the backend's gate. That keeps the
    # test self-contained.
    await _seed_project(db_pool, project_id=member_pid, developer_id=dev_id, token=token, add_member=True)

    # Create the target project but NEVER add the dev as a member.
    async with db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO projects (project_id, name) VALUES ($1, $2)",
            target_pid,
            "UC-502 AC-04 non-member target",
        )

    try:
        # Build the fixture US/UC/ACs in the target project directly via SQL,
        # bypassing the gate (the gate is what we are testing, after all).
        us_id = "US-99"
        uc_id = "UC-901"
        ac_ids = ["AC-01", "AC-02", "AC-03"]
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_stories (id, project_id, name, description, state, labels, priority, external_source, external_id, meta)
                VALUES ($1, $2, 'US-99: fixture', '', 'user_stories', '["US"]'::jsonb, 'none', '', '', '{"tipo": "US"}'::jsonb)
                """,
                us_id,
                target_pid,
            )
            await conn.execute(
                """
                INSERT INTO use_cases (id, project_id, us_id, name, description, state, labels, priority, external_source, external_id, meta)
                VALUES ($1, $2, $3, 'UC-901: fixture', '', 'backlog', '["UC"]'::jsonb, 'none', '', '', '{"tipo": "UC"}'::jsonb)
                """,
                uc_id,
                target_pid,
                us_id,
            )
            for ac in ac_ids:
                await conn.execute(
                    """
                    INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, meta)
                    VALUES ($1, $2, $3, $4, $5, false, '{"tipo": "AC"}'::jsonb)
                    """,
                    f"{uc_id}::{ac}",
                    target_pid,
                    uc_id,
                    ac,
                    f"fixture {ac}",
                )

        # Snapshot rows in the target project's tables.
        snapshots: dict[str, int] = {}
        for table in ("user_stories", "use_cases", "acceptance_criteria"):
            snapshots[table] = await _count(db_pool, table, target_pid)

        # Backend scoped to the TARGET project, where dev is NOT a member.
        backend = NativeBackend(project_id=target_pid, dev_token=token)
        mutators = _mutators_for(uc_id, ac_ids)
        name, run, watched_table = mutators[mutator_index]

        with pytest.raises(ForbiddenError):
            await run(backend, target_pid)

        after = await _count(db_pool, watched_table, target_pid)
        assert after == snapshots[watched_table], (
            f"{name} altered {watched_table} ({snapshots[watched_table]} -> {after}) despite FORBIDDEN"
        )
    finally:
        await _delete_project(db_pool, target_pid)
        await _delete_project(db_pool, member_pid, dev_id)


# ── AC-05: revoke + cache invalidate flips a previously-passing call ─


async def test_ac05_revoke_and_clear_invalidates_a_previously_passing_call(db_pool):
    """A mutation that succeeds while active starts failing after revoke + clear [AC-05]."""
    pid = _unique_pid()
    dev_id = _unique_dev()
    token = _unique_token()
    token_id = await _seed_project(db_pool, project_id=pid, developer_id=dev_id, token=token, add_member=True)
    try:
        backend = NativeBackend(project_id=pid, dev_token=token)
        await backend.setup_board("UC-502 AC-05")
        _us_id, uc_id, _ = await _seed_us_uc_acs(backend, pid)

        # (a) Successful mutation while the token is active → enters the cache.
        c1 = await backend.add_comment(pid, uc_id, "first comment, allowed")
        assert c1.text == "first comment, allowed"

        # (b) Revoke from another connection (simulates the panel).
        async with db_pool.acquire() as conn:
            assert await revoke_mcp_token(conn, token_id=token_id) is True

        # (c) Force cache invalidation — the gate must observe the revoke.
        _clear_auth_cache()

        # (d) The next mutation must fail.
        with pytest.raises(UnauthenticatedError):
            await backend.add_comment(pid, uc_id, "second comment, denied")
    finally:
        await _delete_project(db_pool, pid, dev_id)


# ── AC-06: reads bypass the cached gate ──────────────────────────────


async def test_ac06_reads_succeed_with_revoked_token(db_pool):
    """Forensic and whoami reads must remain available even after revoke [AC-06]."""
    pid = _unique_pid()
    dev_id = _unique_dev()
    token = _unique_token()
    token_id = await _seed_project(db_pool, project_id=pid, developer_id=dev_id, token=token, add_member=True)
    try:
        backend = NativeBackend(project_id=pid, dev_token=token)
        await backend.setup_board("UC-502 AC-06")
        us_id, uc_id, _ = await _seed_us_uc_acs(backend, pid)

        # Revoke + invalidate the cache so every following call would re-enter
        # the gate if it were enforced. Reads must STILL work.
        async with db_pool.acquire() as conn:
            assert await revoke_mcp_token(conn, token_id=token_id) is True
        _clear_auth_cache()

        # Each read returns data without raising — by design, the gate does
        # not protect reads (decision documented in UC-502 AC-06).
        items = await backend.list_items(pid)
        ids = {i.id for i in items}
        assert us_id in ids and uc_id in ids, "list_items must still serve data"

        fetched = await backend.get_item(pid, uc_id)
        assert fetched.id == uc_id

        acs = await backend.get_acceptance_criteria(pid, uc_id)
        assert {a.id for a in acs} == {"AC-01", "AC-02", "AC-03"}

        comments = await backend.get_comments(pid, uc_id)
        assert isinstance(comments, list)

        attachments = await backend.get_attachments(pid, uc_id)
        assert isinstance(attachments, list)

        found = await backend.find_item_by_field(pid, "us_id", "US-99")
        assert found is not None and found.id == us_id
    finally:
        await _delete_project(db_pool, pid, dev_id)
