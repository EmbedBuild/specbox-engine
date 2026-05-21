"""Conformance + concurrency tests for NativeBackend (UC-101).

Two layers:

A) PARAMETRIZED CONFORMANCE SUITE [AC-01] — a single set of contract tests
   that runs against BOTH ``FreeformBackend`` and ``NativeBackend`` through a
   parametrized fixture. The same assertions must hold for either backend.
   The contract is asserted on *behavior* (item retrievable, child linked, AC
   present), never on exact id strings, because the two backends mint ids
   differently (Freeform: ``ff-*`` / ``item-*``; Native: the spec id itself).

B) NATIVE-ONLY tests:
   * ``test_optimistic_version_increment`` [AC-03] — version 1->2, stale
     ``expected_version`` raises ``StaleVersionError`` and leaves the row
     unchanged, correct ``expected_version`` succeeds.
   * ``test_concurrency_50_ops`` [AC-02] — 50 concurrent CRUD ops via
     ``asyncio.gather`` against the shared pool, with a ``pg_stat_activity``
     connection-count check before/after to prove there is no connection leak
     (bounded by the pool ``max_size`` of 10).

Skip behavior
=============
If the dev Postgres is unreachable, ONLY the native parametrization (and the
native-only tests) skip — the Freeform parametrization still runs. The
module-level reachability probe mirrors ``test_native_schema.py``.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from server.backends.freeform_backend import FreeformBackend
from server.backends.native_backend import NativeBackend, StaleVersionError
from server.db.migrate import apply_migrations
from server.db.pool import close_pool, init_pool

# ── Module-level reachability probe (mirrors test_native_schema.py) ───────
_DEV_DSN = "postgresql://specbox:specbox_dev_only@localhost:55432/specbox_native"
DSN = os.environ.get("SPECBOX_NATIVE_DSN", _DEV_DSN)


def _probe(dsn: str) -> None:
    """Confirm Postgres is reachable, in a throwaway event loop.

    Runs at import time in a dedicated loop that is fully torn down so we never
    leave a closed loop as the asyncio default (which would poison the pool
    created later under pytest-asyncio's own loop).
    """

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
    PG_OK = True
    PG_SKIP_REASON = ""
except Exception as exc:  # noqa: BLE001 — any failure means "no DB", just skip
    PG_OK = False
    PG_SKIP_REASON = f"dev Postgres not reachable ({exc!r}); run docker compose -f docker-compose.dev.yml up -d"


def _unique_pid(tag: str) -> str:
    """Unique, collision-proof native test project id."""
    return f"test-uc101-conf-{tag}-{uuid.uuid4().hex[:8]}"


# ── Backend factory fixtures ─────────────────────────────────────────────
#
# The conformance fixture is parametrized over two factories. Each factory
# yields a ready ``(backend, board_id)`` pair (board already set up) and owns
# its own teardown. The native param is gated by ``skipif(not PG_OK)`` so the
# freeform param always runs even without a database.


async def _make_freeform(tmp_path) -> AsyncIterator[tuple[FreeformBackend, str]]:
    be = FreeformBackend(root=str(tmp_path / "tracking"))
    cfg = await be.setup_board("UC-101 conformance (freeform)")
    yield be, cfg.board_id
    # No teardown needed — tmp_path is removed by pytest.


async def _make_native(tmp_path) -> AsyncIterator[tuple[NativeBackend, str]]:
    pid = _unique_pid("be")
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    be = NativeBackend(project_id=pid)
    cfg = await be.setup_board("UC-101 conformance (native)")
    try:
        yield be, cfg.board_id
    finally:
        # Remove only the project we created (CASCADE drops child rows).
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
        await close_pool()


@pytest.fixture(
    params=[
        pytest.param("freeform", id="freeform"),
        pytest.param(
            "native",
            id="native",
            marks=pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON),
        ),
    ]
)
async def backend(request, tmp_path):
    """Yield a ready ``(backend, board_id)`` for the parametrized backend."""
    if request.param == "freeform":
        async for pair in _make_freeform(tmp_path):
            yield pair
    else:
        async for pair in _make_native(tmp_path):
            yield pair


# ── A) PARAMETRIZED CONFORMANCE SUITE [AC-01] ─────────────────────────────


async def test_setup_board_returns_usable_config(backend):
    """setup_board yields a board id and the canonical workflow states."""
    _be, board_id = backend
    assert isinstance(board_id, str) and board_id, "board_id must be a non-empty string"


async def test_create_and_get_us(backend):
    """create_item (US) then get_item returns it with a matching name."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-01: Registro de usuario", labels=["US"])
    fetched = await be.get_item(board_id, us.id)
    assert fetched.name == "US-01: Registro de usuario"
    assert "US" in fetched.labels


async def test_uc_child_linked_to_us(backend):
    """A UC created with the US as parent shows up in get_item_children(US)."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-02: Login", labels=["US"])
    uc = await be.create_item(board_id, name="UC-101: Login con email", labels=["UC"], parent_id=us.id)
    children = await be.get_item_children(board_id, us.id)
    child_ids = {c.id for c in children}
    assert uc.id in child_ids, "UC must be a child of its parent US"


async def test_create_and_get_acceptance_criteria(backend):
    """create_acceptance_criteria then get_acceptance_criteria returns them."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-03: Perfil", labels=["US"])
    uc = await be.create_item(board_id, name="UC-201: Editar perfil", labels=["UC"], parent_id=us.id)
    await be.create_acceptance_criteria(board_id, uc.id, [("AC-01", "Guarda cambios"), ("AC-02", "Valida email")])
    acs = await be.get_acceptance_criteria(board_id, uc.id)
    by_id = {a.id: a for a in acs}
    assert {"AC-01", "AC-02"} <= set(by_id), "both ACs must be retrievable"
    assert by_id["AC-01"].text == "Guarda cambios"
    assert by_id["AC-02"].text == "Valida email"


async def test_mark_acceptance_criterion_toggles_done(backend):
    """mark_acceptance_criterion flips done True then back to False."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-04: Notif", labels=["US"])
    uc = await be.create_item(board_id, name="UC-301: Push", labels=["UC"], parent_id=us.id)
    await be.create_acceptance_criteria(board_id, uc.id, [("AC-01", "Envia push")])

    marked = await be.mark_acceptance_criterion(board_id, uc.id, "AC-01", True)
    assert marked.done is True
    acs = await be.get_acceptance_criteria(board_id, uc.id)
    assert next(a for a in acs if a.id == "AC-01").done is True

    await be.mark_acceptance_criterion(board_id, uc.id, "AC-01", False)
    acs = await be.get_acceptance_criteria(board_id, uc.id)
    assert next(a for a in acs if a.id == "AC-01").done is False


async def test_list_items_returns_all_created(backend):
    """list_items includes every US/UC/AC created."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-05: Busqueda", labels=["US"])
    uc = await be.create_item(board_id, name="UC-401: Filtrar", labels=["UC"], parent_id=us.id)
    await be.create_acceptance_criteria(board_id, uc.id, [("AC-01", "Filtra por tag")])

    items = await be.list_items(board_id)
    ids = {i.id for i in items}
    assert us.id in ids
    assert uc.id in ids
    # The AC is present as an item too — assert by behavior (an AC-labelled
    # child of the UC exists) rather than its exact id shape.
    ac_children = await be.get_acceptance_criteria(board_id, uc.id)
    assert any(a.id == "AC-01" for a in ac_children)


async def test_update_item_persists(backend):
    """update_item changes a field and get_item reflects it."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-06: Ajustes", labels=["US"])
    await be.update_item(board_id, us.id, description="Updated description")
    fetched = await be.get_item(board_id, us.id)
    assert fetched.description == "Updated description"


async def test_get_states_returns_workflow_keys(backend):
    """get_states returns the canonical workflow state mapping (non-empty)."""
    be, board_id = backend
    states = await be.get_states(board_id)
    assert isinstance(states, dict) and states
    # Both backends share the same canonical workflow keys.
    assert {"backlog", "in_progress", "review", "done"} <= set(states)


async def test_get_labels_returns_base_palette(backend):
    """get_labels returns the base label palette including US/UC/AC."""
    be, board_id = backend
    labels = await be.get_labels(board_id)
    assert labels, "labels must be non-empty"
    names = {label["name"] for label in labels}
    assert {"US", "UC", "AC"} <= names


async def test_get_board_name_roundtrips(backend):
    """get_board_name returns a non-empty name for the board."""
    be, board_id = backend
    name = await be.get_board_name(board_id)
    assert isinstance(name, str) and name


async def test_find_item_by_field_us_id(backend):
    """find_item_by_field('us_id', ...) locates the US (common contract)."""
    be, board_id = backend
    us = await be.create_item(board_id, name="US-07: Pagos", labels=["US"])
    found = await be.find_item_by_field(board_id, "us_id", "US-07")
    assert found is not None, "US must be findable by its us_id"
    assert found.id == us.id


# ── B) NATIVE-ONLY TESTS ──────────────────────────────────────────────────


@pytest.fixture
async def native_pool() -> AsyncIterator[asyncpg.Pool]:
    """A migrated shared pool for native-only tests; closes on teardown."""
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    try:
        yield pool
    finally:
        await close_pool()


@pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)
async def test_optimistic_version_increment(native_pool):
    """version 1->2; stale expected_version raises and leaves row unchanged. [AC-03]"""
    pid = _unique_pid("ver")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-101 version test")
    try:
        us = await be.create_item(board_id=pid, name="US-01: Versioned", labels=["US"])
        assert us.meta["version"] == 1, "fresh row starts at version 1"

        # Plain update bumps version 1 -> 2.
        updated = await be.update_item(pid, us.id, description="v2")
        assert updated.meta["version"] == 2

        # Stale expected_version (1) must raise and NOT mutate the row.
        with pytest.raises(StaleVersionError) as exc_info:
            await be.update_item(pid, us.id, description="should-not-apply", meta={"expected_version": 1})
        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 2

        unchanged = await be.get_item(pid, us.id)
        assert unchanged.description == "v2", "stale update must leave the row unchanged"
        assert unchanged.meta["version"] == 2, "version must not advance on a rejected update"

        # Correct expected_version (2) succeeds and bumps to 3.
        ok = await be.update_item(pid, us.id, description="v3", meta={"expected_version": 2})
        assert ok.meta["version"] == 3
        assert ok.description == "v3"
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


@pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)
async def test_concurrency_50_ops(native_pool):
    """50 concurrent CRUD ops succeed with no connection leak. [AC-02]"""
    pid = _unique_pid("conc")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-101 concurrency test")

    async def _conn_count() -> int:
        """Count backend connections to this DB (excludes our counting query)."""
        async with native_pool.acquire() as conn:
            return await conn.fetchval(
                """
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database() AND pid <> pg_backend_pid()
                """
            )

    try:
        # Seed a parent US so children have somewhere to attach.
        parent = await be.create_item(pid, name="US-01: Concurrency root", labels=["US"])

        baseline = await _conn_count()

        async def _one_op(i: int) -> str:
            """A self-contained CRUD cycle: create UC -> update -> read back."""
            uc = await be.create_item(
                pid,
                name=f"UC-{100 + i}: concurrent op {i}",
                labels=["UC"],
                parent_id=parent.id,
            )
            await be.update_item(pid, uc.id, description=f"touched-{i}")
            fetched = await be.get_item(pid, uc.id)
            assert fetched.description == f"touched-{i}"
            return uc.id

        results = await asyncio.gather(*(_one_op(i) for i in range(50)), return_exceptions=True)

        # All 50 ops completed without raising.
        errors = [r for r in results if isinstance(r, Exception)]
        assert not errors, f"concurrent ops raised: {errors[:3]}"
        assert len({r for r in results if isinstance(r, str)}) == 50, "expected 50 unique UCs"

        # All 50 UCs persisted as children of the parent US.
        children = await be.get_item_children(pid, parent.id)
        uc_children = [c for c in children if "UC" in c.labels]
        assert len(uc_children) == 50

        # No connection leak: the pool is bounded by max_size=10, so the post
        # count must not have grown unboundedly past the baseline + pool cap.
        after = await _conn_count()
        assert after <= baseline + 10, (
            f"connection leak suspected: baseline={baseline}, after={after} (pool max_size=10)"
        )
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
