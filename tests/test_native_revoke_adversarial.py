"""UC-506 — Adversarial tests for the cached mutation gate.

Two AC, one file:

* AC-22 — Document the *exposure window* of the cached gate (UC-502 AC-02):
  after a token is revoked from another connection, the cached entry keeps
  letting mutations through until either the TTL elapses or
  :func:`_clear_auth_cache` is called. This is intentional — the cache exists
  precisely to absorb the indexed SELECT cost of the gate — but it is also a
  documented attack surface. The test makes the contract explicit:

      (a) Seed dev + token + member + project.
      (b) Run one mutation while the token is active so the gate caches it.
      (c) Revoke the token from another connection (simulates the admin panel).
      (d) Run another mutation immediately — MUST SUCCEED (cache hit, by design).
      (e) Call ``_clear_auth_cache()`` to simulate either the TTL elapsing or
          an explicit invalidation.
      (f) Run a third mutation — MUST FAIL with :class:`UnauthenticatedError`,
          and the underlying row count MUST be unchanged.

* AC-23 — Membership revocation alone (without revoking the token) must reject
  every one of the 9 mutators with :class:`ForbiddenError`, with no row-count
  side effects. This complements ``test_native_mutation_authz`` AC-04 (which
  asserts non-membership at fixture time) by asserting the symmetric path:
  membership existed and was deleted mid-flight.

Both tests follow the same fixture pattern as ``test_native_mutation_authz`` /
``test_audit_log_destructive``: per-test isolated ``project_id`` + ``developer_id``
+ ``token``, full teardown that cascades through ``projects`` and ``developers``.
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


def _unique_pid(tag: str) -> str:
    return f"test-uc506-{tag}-{uuid.uuid4().hex[:8]}"


def _unique_dev() -> str:
    return f"adv-dev-{uuid.uuid4().hex[:8]}"


def _unique_token() -> str:
    return f"adv-tok-{uuid.uuid4().hex[:16]}"


async def _seed(pool, *, project_id: str, developer_id: str, token: str) -> str:
    """Create project + dev + mcp_token + member. Returns the token_id."""
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Adversarial Tester")
        token_id = await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute(
            """
            INSERT INTO projects (project_id, name, backend_type, board_url, meta)
            VALUES ($1, $1, 'native', '', '{}'::jsonb)
            ON CONFLICT (project_id) DO NOTHING
            """,
            project_id,
        )
        await add_project_member(conn, project_id=project_id, developer_id=developer_id)
        return token_id


async def _seed_us_uc_acs(backend: NativeBackend, board_id: str) -> tuple[str, str, list[str]]:
    """Seed one US + UC + 3 ACs through the gated backend (we're a member here)."""
    suffix = uuid.uuid4().int % 1_000_000
    us = await backend.create_item(board_id, name=f"US-{suffix}: UC-506 fixture", labels=["US"])
    uc = await backend.create_item(board_id, name=f"UC-{suffix}: UC-506 fixture", labels=["UC"], parent_id=us.id)
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
    """Force a clean cache before AND after each test so the gate observes
    only state set up by THIS test, never leftover entries from a sibling.
    """
    _clear_auth_cache()
    yield
    _clear_auth_cache()


@pytest.fixture
async def db_pool() -> AsyncIterator:
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    yield pool
    await close_pool()


# ── AC-22 — Exposure window of the cached gate ──────────────────────


async def test_ac22_revoke_with_cache_documents_exposure_window(db_pool):
    """Revoked token + cache hit = mutation passes (documented exposure) [AC-22].

    Steps:
        (a) Seed dev + token + member + project with 3 ACs.
        (b) Mark one AC done → success, gate caches the (token, project) pair.
        (c) Revoke the token from another connection.
        (d) Mark another AC immediately → MUST SUCCEED (cache hit, by design).
        (e) ``_clear_auth_cache()`` to simulate TTL elapse / explicit invalidation.
        (f) Mark a third AC → MUST raise ``UnauthenticatedError`` and the
            ``acceptance_criteria`` row count for the project MUST be unchanged.

    This makes the exposure-window contract explicit and regression-protected.
    """
    pid = _unique_pid("ac22")
    dev_id = _unique_dev()
    token = _unique_token()
    token_id = await _seed(db_pool, project_id=pid, developer_id=dev_id, token=token)
    try:
        backend = NativeBackend(project_id=pid, dev_token=token)
        await backend.setup_board("UC-506 AC-22")
        _us_id, uc_id, ac_ids = await _seed_us_uc_acs(backend, pid)

        # (b) Prime the cache: this mutation populates (token, project) in
        # the gate's TTL-bounded cache.
        marked = await backend.mark_acceptance_criterion(pid, uc_id, ac_ids[0], True)
        assert marked.done is True

        # (c) Revoke the token from another connection. The DB now has
        # ``revoked_at IS NOT NULL`` but the gate's in-process cache still
        # holds the (token_hash, project_id) → Developer mapping.
        async with db_pool.acquire() as conn:
            assert await revoke_mcp_token(conn, token_id=token_id) is True

        # (d) Within the TTL window — and crucially WITHOUT clearing the cache
        # — the mutation MUST still succeed. This is the documented exposure
        # window: trading a 30s revocation lag for the cost of an indexed
        # SELECT on every mutator. Documenting it here means any future change
        # to the cache semantics breaks this test loudly.
        before_count = await _count(db_pool, "acceptance_criteria", pid)
        marked_during_window = await backend.mark_acceptance_criterion(pid, uc_id, ac_ids[1], True)
        assert marked_during_window.done is True, (
            "AC-22 contract: a cached gate entry must absorb the revocation "
            "for up to _CACHE_TTL_SECONDS — this mutation MUST succeed."
        )
        # Row count must not have changed (mark only flips ``done``).
        mid_count = await _count(db_pool, "acceptance_criteria", pid)
        assert mid_count == before_count

        # (e) Simulate TTL elapse / explicit invalidation. After this, the
        # next call must re-enter the uncached gate and see the revoke.
        _clear_auth_cache()

        # (f) After invalidation, the same mutation MUST fail.
        with pytest.raises(UnauthenticatedError):
            await backend.mark_acceptance_criterion(pid, uc_id, ac_ids[2], True)

        # And the AC table for the project must be unchanged by the failed call.
        after_count = await _count(db_pool, "acceptance_criteria", pid)
        assert after_count == mid_count, "rejected mutation must not alter acceptance_criteria row count"

        # Defensive: verify the third AC is still ``done=False`` — the failed
        # mark must not have leaked through.
        acs = await backend.get_acceptance_criteria(pid, uc_id)
        ac_third = next(a for a in acs if a.id == ac_ids[2])
        assert ac_third.done is False, "rejected mark must not flip done"
    finally:
        await _delete_project(db_pool, pid, dev_id)


# ── AC-23 — Membership removal blocks every mutator ──────────────────

# The 9 mutator catalogue is identical to test_native_mutation_authz so the
# two suites can be cross-referenced. Each entry maps to:
# (name, callable(backend, board_id), table_for_count_snapshot)


def _mutators_for(uc_id: str, ac_ids: list[str]):
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
            lambda be, b: be.add_attachment(b, uc_id, "ref.txt", b"hello", "text/plain"),
            "use_cases",
        ),
    ]


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
async def test_ac23_membership_removal_blocks_each_mutator(db_pool, mutator_index):
    """Removing project_members (token still active) → FORBIDDEN for every mutator [AC-23].

    Different from AC-04 in ``test_native_mutation_authz``: that variant asserts
    "never was a member"; this one asserts "was a member, membership got
    revoked mid-flight". Both must end in ``ForbiddenError`` with zero row
    side-effects.
    """
    pid = _unique_pid("ac23")
    dev_id = _unique_dev()
    token = _unique_token()
    await _seed(db_pool, project_id=pid, developer_id=dev_id, token=token)
    try:
        backend = NativeBackend(project_id=pid, dev_token=token)
        await backend.setup_board("UC-506 AC-23")
        _us_id, uc_id, ac_ids = await _seed_us_uc_acs(backend, pid)

        # Snapshot the watched tables BEFORE removing membership. Any side-
        # effect produced by the rejected mutator will be visible as a delta.
        snapshots: dict[str, int] = {}
        for table in ("user_stories", "use_cases", "acceptance_criteria"):
            snapshots[table] = await _count(db_pool, table, pid)

        # Remove the membership from another connection. The token is still
        # active — only the (project_id, developer_id) edge is gone. Then
        # flush the cache so the gate re-evaluates and sees the missing edge
        # (otherwise the cached "authorized" entry would let the mutator in).
        async with db_pool.acquire() as conn:
            removed = await conn.fetchval(
                """
                DELETE FROM project_members
                 WHERE project_id = $1 AND developer_id = $2
                RETURNING 1
                """,
                pid,
                dev_id,
            )
        assert removed == 1, "fixture seeded the membership, DELETE must hit a row"
        _clear_auth_cache()

        mutators = _mutators_for(uc_id, ac_ids)
        name, run, watched_table = mutators[mutator_index]

        with pytest.raises(ForbiddenError):
            await run(backend, pid)

        after = await _count(db_pool, watched_table, pid)
        assert after == snapshots[watched_table], (
            f"{name} altered {watched_table} ({snapshots[watched_table]} -> {after}) "
            "despite FORBIDDEN — membership removal must be a strict gate."
        )
    finally:
        await _delete_project(db_pool, pid, dev_id)
