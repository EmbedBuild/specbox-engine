"""UC-706 — creating US/UC/AC emits audit events so the Cloud panel refreshes.

The realtime broadcast trigger (``audit_log_broadcast_change``) only fires on
INSERT to ``audit_log``. Creation (``create_item`` / ``create_acceptance_criteria``
/ ``import_spec``) used to write no audit row, so seeding a US/UC/AC didn't
refresh the panel live. These tests verify the events are now emitted, with the
agreed granularity: individual creates → one event each; ``import_spec`` (bulk)
→ ONE aggregate ``import_spec`` event.

Postgres-gated; SKIP cleanly when no dev DB is reachable
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import uuid

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


async def _make_backend():
    """A ready (backend, board_id, pool, cleanup_ids) for one test."""
    from server.backends.native_backend import NativeBackend
    from server.coordination.identity import (
        add_project_member,
        register_developer,
        register_mcp_token,
    )
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pid = f"Acme/uc706-{uuid.uuid4().hex[:8]}"
    dev_id = f"uc706-dev-{uuid.uuid4().hex[:8]}"
    token = f"uc706-tok-{uuid.uuid4().hex[:16]}"
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=dev_id, display_name="UC706 Tester")
        await register_mcp_token(conn, developer_id=dev_id, token=token)
        await conn.execute(
            "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
            "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT DO NOTHING",
            pid,
        )
        await add_project_member(conn, project_id=pid, developer_id=dev_id)
    be = NativeBackend(project_id=pid, dev_token=token)
    return be, pid, pool, dev_id


async def _events(pool, project_id, op):
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT target_id, metadata FROM audit_log "
            "WHERE project_id = $1 AND operation = $2 ORDER BY id",
            project_id,
            op,
        )


async def _cleanup(pool, pid, dev_id):
    from server.db.pool import close_pool

    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
        await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev_id)
    await close_pool()


async def test_ac01_create_us_and_uc_emit_events():
    """AC-01: create_item for a US and a UC each writes one create_us/create_uc
    audit row, targeting the created id."""
    be, pid, pool, dev_id = await _make_backend()
    try:
        us = await be.create_item(pid, name="US-01: Algo", labels=["US"])
        uc = await be.create_item(pid, name="UC-101: Hacer algo", labels=["UC"], parent_id=us.id)

        us_events = await _events(pool, pid, "create_us")
        uc_events = await _events(pool, pid, "create_uc")
        assert len(us_events) == 1
        assert us_events[0]["target_id"] == "US-01"
        assert len(uc_events) == 1
        assert uc_events[0]["target_id"] == "UC-101"
    finally:
        await _cleanup(pool, pid, dev_id)


async def test_ac02_create_acceptance_criteria_emits_event():
    """AC-02: creating ACs writes a create_ac event. A single AC targets that
    AC; a bulk create targets the UC with a count in metadata (not one per AC)."""
    import json

    be, pid, pool, dev_id = await _make_backend()
    try:
        us = await be.create_item(pid, name="US-02: X", labels=["US"])
        uc = await be.create_item(pid, name="UC-201: Y", labels=["UC"], parent_id=us.id)

        # Single AC → one event targeting the AC.
        await be.create_acceptance_criteria(pid, uc.id, [("AC-01", "criterio uno")])
        # Bulk ACs → one aggregate event on the UC with a count.
        await be.create_acceptance_criteria(
            pid, uc.id, [("AC-02", "dos"), ("AC-03", "tres"), ("AC-04", "cuatro")]
        )

        ac_events = await _events(pool, pid, "create_ac")
        # 2 events total (one single + one aggregate), NOT 4.
        assert len(ac_events) == 2
        single = ac_events[0]
        assert single["target_id"] == "AC-01"
        aggregate = ac_events[1]
        assert aggregate["target_id"] == uc.id
        meta = aggregate["metadata"]
        meta = json.loads(meta) if isinstance(meta, str) else meta
        assert meta == {"ac": 3}
    finally:
        await _cleanup(pool, pid, dev_id)


async def test_ac03_import_spec_emits_single_aggregate_event():
    """AC-03: import_spec seeds N items but writes exactly ONE import_spec audit
    event with the counts in metadata — NOT one per item (no feed flood)."""
    import json

    from server.tools.spec_driven import import_spec

    be, pid, pool, dev_id = await _make_backend()
    # import_spec resolves the backend from the session; patch get_session_backend
    # to return our authenticated backend, and close to a no-op.
    import server.tools.spec_driven as sd

    orig_get = sd.get_session_backend
    orig_close = be.close

    async def _fake_get(ctx, items_content=None):
        return be

    async def _noop_close():
        return None

    sd.get_session_backend = _fake_get  # type: ignore[assignment]
    be.close = _noop_close  # type: ignore[assignment]
    try:
        spec = {
            "user_stories": [
                {
                    "us_id": "US-90",
                    "name": "Seed",
                    "hours": 1,
                    "screens": "",
                    "description": "d",
                    "use_cases": [
                        {
                            "uc_id": "UC-901",
                            "name": "A",
                            "actor": "x",
                            "hours": 1,
                            "screens": "",
                            "context": "",
                            "acceptance_criteria": ["uno", "dos", "tres"],
                        },
                        {
                            "uc_id": "UC-902",
                            "name": "B",
                            "actor": "x",
                            "hours": 1,
                            "screens": "",
                            "context": "",
                            "acceptance_criteria": ["a", "b"],
                        },
                    ],
                }
            ]
        }
        res = await import_spec(pid, spec, ctx=None)  # ctx unused by our fake
        assert res["created"] == {"us": 1, "uc": 2, "ac": 5}

        # AC-03: exactly ONE import_spec event with the counts; and ZERO
        # per-item create_us/create_uc/create_ac events (suppressed).
        imp = await _events(pool, pid, "import_spec")
        assert len(imp) == 1
        meta = imp[0]["metadata"]
        meta = json.loads(meta) if isinstance(meta, str) else meta
        assert meta == {"us": 1, "uc": 2, "ac": 5}

        assert len(await _events(pool, pid, "create_us")) == 0
        assert len(await _events(pool, pid, "create_uc")) == 0
        assert len(await _events(pool, pid, "create_ac")) == 0
    finally:
        sd.get_session_backend = orig_get  # type: ignore[assignment]
        be.close = orig_close  # type: ignore[assignment]
        await _cleanup(pool, pid, dev_id)
