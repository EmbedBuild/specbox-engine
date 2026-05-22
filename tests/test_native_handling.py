"""Tests for Native-specific migration handling (UC-403).

Covers the three ACs of UC-403:

* **AC-07** — migrating *out of* Native collects (but does not migrate) the
  multi-developer coordination state: claims, developer roster, branches.
  ``build_native_exit_report`` wraps it under ``discarded_native_state`` with a
  note.
* **AC-08** — migrating *into* Native seeds a developer identity
  (``register_developer`` + ``add_project_member``) idempotently, and the
  imported rows carry ``version == 1`` (the schema default).
* **AC-09** (Frontier 2) — the serialized report never contains the DSN nor its
  dev password.

Skip behavior mirrors ``test_native_backend_conformance.py``: the whole module
skips when the dev/Supabase Postgres is unreachable. With the dev Postgres up
(docker-compose.dev.yml) nothing should skip.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest

from server.backends.native_backend import NativeBackend
from server.coordination import claims as claims_mod
from server.db.migrate import apply_migrations
from server.db.pool import close_pool, init_pool
from server.migration.native_handling import (
    DISCARD_NOTE,
    build_native_exit_report,
    collect_discarded_native_state,
    seed_native_identity,
)
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()

pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


def _unique_pid(tag: str) -> str:
    """Unique, collision-proof native test project id."""
    return f"test-uc403-{tag}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def native_pool() -> AsyncIterator[asyncpg.Pool]:
    """A migrated shared pool for native-only tests; closes on teardown."""
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    try:
        yield pool
    finally:
        await close_pool()


# ── AC-07: Native → other collects discarded coordination state ──────────


async def test_collect_discarded_native_state_reports_claim(native_pool):
    """A developer + claim over a UC appears in the discarded-state report. [AC-07]"""
    pid = _unique_pid("exit")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 exit test")
    try:
        # Seed an owner so the claim's FK to developers is satisfied.
        await seed_native_identity(native_pool, pid, "dev-exit", display_name="Dev Exit")

        # Create a US + UC, then claim the UC.
        us = await be.create_item(pid, name="US-01: Exit", labels=["US"])
        uc = await be.create_item(pid, name="UC-101: Migrate out", labels=["UC"], parent_id=us.id)
        async with native_pool.acquire() as conn:
            await claims_mod.claim_uc(
                conn,
                project_id=pid,
                uc_id=uc.id,
                developer_id="dev-exit",
                branch="feature/uc-101-migrate-out",
            )

        discarded = await collect_discarded_native_state(native_pool, pid)

        assert discarded["counts"]["claims"] >= 1
        assert discarded["counts"]["developers"] >= 1
        claim_uc_ids = {c["uc_id"] for c in discarded["claims"]}
        assert uc.id in claim_uc_ids, "the active claim must appear with its uc_id"
        the_claim = next(c for c in discarded["claims"] if c["uc_id"] == uc.id)
        assert the_claim["developer_id"] == "dev-exit"

        # build_native_exit_report wraps it under the section + note.
        report = build_native_exit_report(discarded)
        assert report["discarded_native_state"] == discarded
        assert report["note"] == DISCARD_NOTE
        assert "NOT migrated" in report["note"]
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


async def test_collect_discarded_native_state_reports_branch(native_pool):
    """A registered branch appears in the discarded-state report. [AC-07]"""
    from server.coordination import branches as branches_mod

    pid = _unique_pid("branch")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 branch test")
    try:
        await seed_native_identity(native_pool, pid, "dev-br")
        async with native_pool.acquire() as conn:
            await branches_mod.register_branch(
                conn,
                project_id=pid,
                branch="feature/uc-202-foo",
                uc_id="UC-202",
                developer_id="dev-br",
            )

        discarded = await collect_discarded_native_state(native_pool, pid)
        assert discarded["counts"]["branches"] >= 1
        branch_names = {b["branch"] for b in discarded["branches"]}
        assert "feature/uc-202-foo" in branch_names
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


async def test_collect_discarded_empty_when_no_coordination(native_pool):
    """A project with no claims/devs/branches reports zero counts. [AC-07]"""
    pid = _unique_pid("empty")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 empty test")
    try:
        discarded = await collect_discarded_native_state(native_pool, pid)
        assert discarded["counts"] == {"claims": 0, "developers": 0, "branches": 0}
        assert discarded["claims"] == []
        assert discarded["developers"] == []
        assert discarded["branches"] == []
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


# ── AC-08: other → Native seeds identity, rows are version 1 ─────────────


async def test_seed_native_identity_adds_member_and_is_idempotent(native_pool):
    """seed_native_identity registers + adds member; second call is a no-op. [AC-08]"""
    pid = _unique_pid("seed")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 seed test")
    try:
        result = await seed_native_identity(native_pool, pid, "dev-x", display_name="Dev X")
        assert result == {
            "developer_id": "dev-x",
            "registered": True,
            "member_added": True,
        }

        # A row exists in project_members for this project + developer.
        async with native_pool.acquire() as conn:
            member = await conn.fetchrow(
                "SELECT role FROM project_members WHERE project_id = $1 AND developer_id = $2",
                pid,
                "dev-x",
            )
        assert member is not None, "developer must be a member of the migrated project"

        # Idempotent: a second call does not raise and keeps a single member row.
        await seed_native_identity(native_pool, pid, "dev-x", display_name="Dev X Renamed")
        async with native_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT count(*) FROM project_members WHERE project_id = $1 AND developer_id = $2",
                pid,
                "dev-x",
            )
        assert count == 1, "re-seeding must not duplicate the membership"
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


async def test_migrated_user_story_has_version_1(native_pool):
    """A US created in a migrated Native project carries version == 1. [AC-08]"""
    pid = _unique_pid("ver1")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 version test")
    try:
        await seed_native_identity(native_pool, pid, "dev-v")
        us = await be.create_item(pid, name="US-01: Imported", labels=["US"])

        async with native_pool.acquire() as conn:
            version = await conn.fetchval(
                "SELECT version FROM user_stories WHERE project_id = $1 AND id = $2",
                pid,
                us.id,
            )
        assert version == 1, "freshly migrated rows must start at version 1 (schema default)"
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


async def test_seed_native_identity_does_not_persist_token(native_pool):
    """The clear token is never persisted; only its hash lands in developers. [AC-08/AC-09]"""
    pid = _unique_pid("notok")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 token test")
    try:
        secret = "super-secret-token-value"
        await seed_native_identity(native_pool, pid, "dev-t", token=secret)
        async with native_pool.acquire() as conn:
            token_hash = await conn.fetchval("SELECT token_hash FROM developers WHERE developer_id = $1", "dev-t")
        assert token_hash is not None
        assert secret not in token_hash, "the clear token must never be stored"
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)


# ── AC-09: Frontier 2 — serialized report carries no DSN/credentials ─────


async def test_serialized_report_never_leaks_dsn(native_pool):
    """json.dumps of the report contains neither the DSN nor its dev password. [AC-09]"""
    pid = _unique_pid("f2")
    be = NativeBackend(project_id=pid)
    await be.setup_board("UC-403 frontier-2 test")
    try:
        await seed_native_identity(native_pool, pid, "dev-f2", display_name="Frontier Two")
        us = await be.create_item(pid, name="US-01: Secret", labels=["US"])
        uc = await be.create_item(pid, name="UC-101: Secret UC", labels=["UC"], parent_id=us.id)
        async with native_pool.acquire() as conn:
            await claims_mod.claim_uc(
                conn,
                project_id=pid,
                uc_id=uc.id,
                developer_id="dev-f2",
                branch="feature/uc-101-secret",
            )

        discarded = await collect_discarded_native_state(native_pool, pid)
        report = build_native_exit_report(discarded)
        serialized = json.dumps(report)

        assert DSN not in serialized, "the DSN must never appear in the report"
        assert "specbox_dev_only" not in serialized, "the DSN password must never leak"
        assert "token_hash" not in serialized, "no token material may appear in the report"
    finally:
        async with native_pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
