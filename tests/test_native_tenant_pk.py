"""Tenant-scoped primary keys for the Native Backend (UC-707).

Regression suite for the v6.9.x blocker: the atomic ingest of a FreeForm→Native
migration collided on ``user_stories_pkey`` because the PK was the LOGICAL id
alone ("US-01"), not namespaced by project. Two projects in the same shared
Postgres could not both hold a "US-01".

Layout:
  * Unit tests (no DB) — the bug-C id parser (``parse_item_id`` accepting an
    alphabetic suffix like "UC-004b") and the bug-A actionable large-source
    guard of ``switch_project_backend``. These run everywhere.
  * Postgres-gated tests — the core cross-tenant isolation: ingest the SAME
    logical ids (US-01..US-15) into TWO different native projects in the same
    DB without colliding, both tenants isolated (AC-02). They SKIP cleanly
    when no dev DB.

The cross-tenant test is the one that was missing and let the bug ship: prior
ingest suites only ever wrote a single project, never two sharing logical ids.
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.spec_backend import parse_item_id

# Reuse the batch suite's Postgres scaffolding (probe, identity seed, counters).
from tests._native_db import DSN, reachable
from tests.test_native_batch_ingestion import _count_rows, _seed_identity

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ═══════════════════════════════════════════════════════════════════════
# UNIT — bug C: parse_item_id accepts an alphabetic suffix (UC-707 AC-03)
# ═══════════════════════════════════════════════════════════════════════


def test_parse_item_id_keeps_alpha_suffix_uc():
    # "[UC-004b]" must resolve to "UC-004b", not collapse to "UC-004".
    item_id, name = parse_item_id("[UC-004b] Split use case", "UC")
    assert item_id == "UC-004b"
    assert name == "Split use case"


def test_parse_item_id_keeps_alpha_suffix_us_and_ac():
    assert parse_item_id("[US-12a] Story", "US")[0] == "US-12a"
    assert parse_item_id("AC-07c: Criterion", "AC")[0] == "AC-07c"


def test_parse_item_id_plain_ids_unchanged():
    # No suffix → unchanged behaviour (the suffix group is optional).
    assert parse_item_id("[UC-004] Plain", "UC")[0] == "UC-004"
    assert parse_item_id("US-01: Registro", "US")[0] == "US-01"


def test_parse_item_id_does_not_swallow_word_after_space():
    # The suffix is glued to the digits — a following word is not absorbed.
    item_id, name = parse_item_id("[UC-004] beta release", "UC")
    assert item_id == "UC-004"
    assert name == "beta release"


# ═══════════════════════════════════════════════════════════════════════
# UNIT — bug A: large freeform→native source is refused with an actionable
# envelope, NOT the misleading "Target backend not configured" (UC-707 AC-05)
# ═══════════════════════════════════════════════════════════════════════


class _FakeCtx:
    """Minimal Context double — switch_project_backend only touches state for
    the steps that the bug-A guard short-circuits before reaching."""

    def __init__(self):
        self._state: dict = {}

    async def get_state(self, k):
        return self._state.get(k)

    async def set_state(self, k, v):
        self._state[k] = v


async def test_switch_refuses_oversized_freeform_native_with_remediation():
    from server.tools.migration import (
        BATCH_TRANSPORT_THRESHOLD_BYTES,
        switch_project_backend,
    )

    big = json.dumps([{"id": "x", "name": "[US-01] x", "labels": ["US"]}]) + (
        "x" * (BATCH_TRANSPORT_THRESHOLD_BYTES + 1)
    )
    out = await switch_project_backend(
        project_slug="proj",
        source_type="freeform",
        target_type="native",
        ctx=_FakeCtx(),
        source_content=big,
        target_id="owner/repo",
        dev_token="tok",
        dry_run=False,  # execute path — the guard only fires here
    )
    assert out["status"] == "SOURCE_TOO_LARGE_USE_BATCH"
    assert "batch" in out["error"].lower()
    assert out["source_bytes"] > out["threshold_bytes"]
    assert any("start_migration_session" in step for step in out["remediation"])
    # Crucially NOT the misleading guard the reporter saw.
    assert "Target backend not configured" not in out.get("error", "")


async def test_switch_allows_small_freeform_native_past_guard():
    """A sub-threshold source does not trip the bug-A guard (it proceeds to the
    normal flow, which fails later for unrelated reasons in this unit context)."""
    from server.tools.migration import switch_project_backend

    small = json.dumps([{"id": "x", "name": "[US-01] x", "labels": ["US"]}])
    out = await switch_project_backend(
        project_slug="proj",
        source_type="freeform",
        target_type="native",
        ctx=_FakeCtx(),
        source_content=small,
        target_id="owner/repo",
        dev_token="tok",
        dry_run=False,
    )
    # Whatever happens, it is NOT the oversize refusal.
    assert out.get("status") != "SOURCE_TOO_LARGE_USE_BATCH"


# ═══════════════════════════════════════════════════════════════════════
# UNIT — bug B: a native target never surfaces the impossible-to-satisfy
# "Target backend not configured" guard (UC-707 AC-04)
# ═══════════════════════════════════════════════════════════════════════


async def test_set_migration_target_rejects_native_by_design():
    """set_migration_target has no native branch (no API creds to stash) — the
    premise of bug B. The native path must therefore NOT depend on its config."""
    from server.tools.migration import set_migration_target

    out = await set_migration_target(backend_type="native", ctx=_FakeCtx())
    assert "Unknown backend_type: native" in out.get("error", "")


async def test_native_dry_run_does_not_demand_migration_target_config():
    """AC-04: a native-target dry_run preview reaches the source read WITHOUT
    raising the 'Target backend not configured' guard (which set_migration_target
    can never satisfy for native). It may fail later reading the source, but the
    failure must not be that guard."""
    from server.tools.migration import switch_project_backend

    small = json.dumps([
        {"id": "u1", "name": "[US-01] x", "labels": ["US"], "parent_id": None,
         "meta": {"tipo": "US", "us_id": "US-01"}},
    ])
    out = await switch_project_backend(
        project_slug="proj",
        source_type="freeform",
        target_type="native",
        ctx=_FakeCtx(),
        source_content=small,
        target_id="owner/repo",
        dev_token="tok",
        dry_run=True,  # preview only — reads source, no target write
    )
    blob = json.dumps(out)
    assert "Target backend not configured" not in blob


# ═══════════════════════════════════════════════════════════════════════
# Fixture — N US/UC sharing the SAME logical ids across projects
# ═══════════════════════════════════════════════════════════════════════


def _make_items_us01_to_us15() -> str:
    """A freeform items.json with US-01..US-15, each with 1 UC + 2 AC.

    The logical ids are deliberately the canonical "US-01".."US-15" so two
    projects ingesting this same blob exercise the cross-tenant PK collision
    the bug was about.
    """
    items: list[dict] = []
    for n in range(1, 16):
        us_id = f"US-{n:02d}"
        us_item = f"item-us-{n}"
        items.append({
            "id": us_item,
            "name": f"[{us_id}] Story {n}",
            "external_id": us_id, "external_source": None,
            "description": "shared-id story", "labels": ["US"],
            "priority": "high", "state": "in_progress", "parent_id": None,
            "meta": {"tipo": "US", "us_id": us_id},
        })
        uc_id = f"UC-{100 + n}"
        uc_item = f"item-uc-{n}"
        items.append({
            "id": uc_item,
            "name": f"[{uc_id}] Use case for story {n}",
            "external_id": uc_id, "external_source": None,
            "description": "uc", "labels": ["UC"],
            "priority": "high", "state": "done", "parent_id": us_item,
            "meta": {"tipo": "UC", "uc_id": uc_id, "us_id": us_id, "actor": "Sistema"},
        })
        for a in range(1, 3):
            ac_id = f"AC-{a:02d}"
            items.append({
                "id": f"ac-{n}-{a}",
                "name": f"[{ac_id}] Criterion {a} of story {n}",
                "external_id": None, "external_source": None,
                "description": "", "labels": ["AC"],
                "priority": "high", "state": "user_stories", "parent_id": uc_item,
                "meta": {"tipo": "AC", "ac_id": ac_id, "uc_id": uc_id},
            })
    return json.dumps(items, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════
# Postgres-gated — cross-tenant isolation (UC-707 AC-01, AC-02)
# ═══════════════════════════════════════════════════════════════════════


@pytestmark_pg
class TestCrossTenantIsolation:
    async def _setup(self):
        from server.db.migrate import apply_migrations
        from server.db.pool import init_pool

        pool = await init_pool(dsn=DSN)
        await apply_migrations(pool)  # includes 0009_tenant_scoped_pks
        pid_a = f"tenant-a-{uuid.uuid4().hex[:8]}"
        pid_b = f"tenant-b-{uuid.uuid4().hex[:8]}"
        dev_a, tok_a = await _seed_identity(pool, pid_a)
        dev_b, tok_b = await _seed_identity(pool, pid_b)
        return pool, (pid_a, dev_a, tok_a), (pid_b, dev_b, tok_b)

    async def _teardown(self, pool, a, b):
        from server.db.pool import close_pool

        async with pool.acquire() as conn:
            for pid, dev, _tok in (a, b):
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev)
        await close_pool()

    async def _ingest(self, pid: str, token: str, blob: str):
        from server.backends.freeform_backend import FreeformBackend
        from server.backends.native_backend import NativeBackend
        from server.tools.migration import _read_source

        src = FreeformBackend(items_content=blob)
        try:
            source = await _read_source(src, ".")
        finally:
            await src.close()
        backend = NativeBackend(project_id=pid, dev_token=token)
        return await backend.ingest_atomic(pid, source, source_type="freeform")

    async def test_same_logical_ids_into_two_tenants_do_not_collide(self):
        """AC-02: US-01..US-15 ingested into TWO projects in the same DB →
        no user_stories_pkey collision; each tenant isolated and complete."""
        pool, a, b = await self._setup()
        pid_a, _dev_a, tok_a = a
        pid_b, _dev_b, tok_b = b
        try:
            blob = _make_items_us01_to_us15()

            # First tenant ingests the shared ids cleanly.
            res_a = await self._ingest(pid_a, tok_a, blob)
            assert res_a["migrated"]["us"] == 15
            assert res_a["migrated"]["uc"] == 15

            # Second tenant ingests the EXACT SAME logical ids. Pre-fix this
            # raised `duplicate key ... user_stories_pkey (id)=(US-01)`.
            res_b = await self._ingest(pid_b, tok_b, blob)
            assert res_b["migrated"]["us"] == 15
            assert res_b["migrated"]["uc"] == 15

            # Both tenants fully populated and isolated.
            counts_a = await _count_rows(pool, pid_a)
            counts_b = await _count_rows(pool, pid_b)
            assert counts_a == {"us": 15, "uc": 15, "ac": 30}
            assert counts_b == {"us": 15, "uc": 15, "ac": 30}

            # The "US-01" row exists once per tenant (the PK is now composite).
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT project_id FROM user_stories WHERE id = 'US-01' "
                    "AND project_id = ANY($1::text[]) ORDER BY project_id",
                    [pid_a, pid_b],
                )
            assert {r["project_id"] for r in rows} == {pid_a, pid_b}
        finally:
            await self._teardown(pool, a, b)

    async def test_composite_fk_keeps_children_in_same_tenant(self):
        """AC-01: the rewired composite FKs keep UC→US and AC→UC within one
        tenant — a UC in tenant B references tenant B's US, never tenant A's."""
        pool, a, b = await self._setup()
        pid_a, _dev_a, tok_a = a
        pid_b, _dev_b, tok_b = b
        try:
            blob = _make_items_us01_to_us15()
            await self._ingest(pid_a, tok_a, blob)
            await self._ingest(pid_b, tok_b, blob)

            async with pool.acquire() as conn:
                # Every UC in tenant B points at a US that also lives in tenant B.
                orphan = await conn.fetchval(
                    """
                    SELECT count(*) FROM use_cases uc
                    WHERE uc.project_id = $1
                      AND uc.us_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM user_stories us
                         WHERE us.project_id = uc.project_id AND us.id = uc.us_id
                      )
                    """,
                    pid_b,
                )
            assert orphan == 0
        finally:
            await self._teardown(pool, a, b)
