"""UC-4002 (US-40) — the public roles lose every write privilege on the board and
the deny policies are restrictive.

Postgres-gated like the rest of the native suite. Supabase's default privileges
give anon and authenticated ALL on every table and sequence of ``public``; the
fixture recreates that (roles created when missing, ALL granted on every table
and sequence of public) and re-applies the engine migrations, so every
assertion proves that migration 0024 closes what the platform opens:

- AC-01: anon and authenticated hold no INSERT / UPDATE / DELETE / TRUNCATE on
  any table of public — writing as them is a permission error —, no privilege
  at all on the board tables, and tables created afterwards grant them SELECT
  only.
- AC-02: the deny policy of every board table is RESTRICTIVE, so on the
  sensitive tables (tokens, identities, organizations, audit) a permissive
  ``USING (true)`` policy added in a test, with SELECT granted back, still
  returns zero rows to anon.

Nothing here survives the module: the AC-02 and new-table checks run inside
transactions that are rolled back, and the grants the fixture adds are the ones
0024 revokes.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from server.coordination.identity import register_developer, register_mcp_token
from server.db.migrate import apply_migrations
from server.db.pool import close_pool, get_pool, init_pool
from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

BOARD_TABLES = (
    "acceptance_criteria",
    "audit_log",
    "branch_registry",
    "developers",
    "epics",
    "github_identities",
    "mcp_tokens",
    "organization_members",
    "organizations",
    "project_members",
    "projects",
    "tool_access_log",
    "uc_reservations",
    "uc_state_transitions",
    "use_cases",
    "user_stories",
)
SENSITIVE_TABLES = (
    "mcp_tokens",
    "developers",
    "github_identities",
    "organizations",
    "organization_members",
    "audit_log",
)
WRITE_PRIVILEGES = ["INSERT", "UPDATE", "DELETE", "TRUNCATE"]
ALL_TABLE_PRIVILEGES = ["SELECT", *WRITE_PRIVILEGES, "REFERENCES", "TRIGGER"]
PUBLIC_ROLES = ("anon", "authenticated")


@pytest.fixture
async def pool():
    await init_pool(dsn=DSN)
    pool = await get_pool()
    try:
        await apply_migrations(pool)
        async with pool.acquire() as conn:
            for role, options in (("anon", ""), ("authenticated", ""), ("service_role", " BYPASSRLS")):
                if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                    await conn.execute(f"CREATE ROLE {role} NOLOGIN{options}")
            # What Supabase's default privileges give the public roles.
            await conn.execute("GRANT USAGE ON SCHEMA public TO anon, authenticated")
            await conn.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated")
            await conn.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated")
        await apply_migrations(pool)
        yield pool
    finally:
        await close_pool()


async def _denied_as(conn: asyncpg.Connection, role: str, sql: str, *args) -> None:
    """Run ``sql`` as ``role`` and require a permission error (42501)."""
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(f"SET LOCAL ROLE {role}")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(sql, *args)
    finally:
        await tr.rollback()


# ── AC-01 — no writes for the public roles ───────────────────────────


async def test_ac01_public_roles_cannot_write_any_table_of_public(pool):
    leaks = await pool.fetch(
        """
        SELECT c.relname, r.rolname, p.priv
          FROM pg_class c
         CROSS JOIN unnest($1::text[]) AS r(rolname)
         CROSS JOIN unnest($2::text[]) AS p(priv)
         WHERE c.relkind IN ('r', 'p') AND c.relnamespace = 'public'::regnamespace
           AND has_table_privilege(r.rolname, c.oid, p.priv)
        """,
        list(PUBLIC_ROLES),
        WRITE_PRIVILEGES,
    )
    assert [tuple(row) for row in leaks] == []


async def test_ac01_board_tables_grant_nothing_to_the_public_roles(pool):
    present = {
        r["relname"]
        for r in await pool.fetch(
            "SELECT relname FROM pg_class WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace"
        )
    }
    assert set(BOARD_TABLES) <= present, f"board tables missing: {set(BOARD_TABLES) - present}"
    leaks = await pool.fetch(
        """
        SELECT t.name, r.rolname, p.priv
          FROM unnest($1::text[]) AS t(name)
         CROSS JOIN unnest($2::text[]) AS r(rolname)
         CROSS JOIN unnest($3::text[]) AS p(priv)
         WHERE has_table_privilege(r.rolname, ('public.' || quote_ident(t.name))::regclass, p.priv)
        """,
        list(BOARD_TABLES),
        list(PUBLIC_ROLES),
        ALL_TABLE_PRIVILEGES,
    )
    assert [tuple(row) for row in leaks] == []


async def test_ac01_writing_the_board_as_a_public_role_is_a_permission_error(pool):
    writes = (
        ("INSERT INTO projects (project_id, name) VALUES ($1, $1)", f"uc4002/{uuid.uuid4().hex[:8]}"),
        ("UPDATE use_cases SET state = 'done' WHERE project_id = $1", "uc4002/none"),
        ("DELETE FROM audit_log WHERE project_id = $1", "uc4002/none"),
        ("DELETE FROM mcp_tokens WHERE developer_id = $1", "uc4002/none"),
        ("INSERT INTO epics (project_id, id, name) VALUES ($1, 'EP-01', 'x')", "uc4002/none"),
    )
    async with pool.acquire() as conn:
        for sql, arg in writes:
            for role in PUBLIC_ROLES:
                await _denied_as(conn, role, sql, arg)


async def test_ac01_tables_created_later_are_read_only_for_the_public_roles(pool):
    name = f"uc4002_probe_{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(f"CREATE TABLE public.{name} (id int)")
            for role in PUBLIC_ROLES:
                granted = {
                    priv: await conn.fetchval(
                        "SELECT has_table_privilege($1, $2::regclass, $3)", role, f"public.{name}", priv
                    )
                    for priv in ALL_TABLE_PRIVILEGES
                }
                assert granted == {priv: priv == "SELECT" for priv in ALL_TABLE_PRIVILEGES}, (role, granted)
        finally:
            await tr.rollback()


# ── AC-02 — restrictive deny ─────────────────────────────────────────


async def test_ac02_every_board_table_has_rls_and_a_restrictive_deny(pool):
    for table in BOARD_TABLES:
        assert await pool.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid = $1::regclass", f"public.{table}"), (
            table
        )
        policy = await pool.fetchrow(
            "SELECT permissive, roles::text[] AS roles, cmd, qual, with_check FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = $1 AND policyname = $2",
            table,
            f"specbox_deny_anon_{table}",
        )
        assert policy is not None, table
        assert policy["permissive"] == "RESTRICTIVE", table
        assert sorted(policy["roles"]) == ["anon", "authenticated"], table
        assert policy["cmd"] == "ALL" and policy["qual"] == "false" and policy["with_check"] == "false", table


async def test_ac02_a_permissive_policy_does_not_open_a_sensitive_table(pool):
    dev = f"dev-uc4002-{uuid.uuid4().hex[:6]}"
    org = f"org-uc4002-{uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            # One real row in each sensitive table, so "zero rows" is not vacuous.
            await register_developer(conn, developer_id=dev, display_name="Probe")
            await register_mcp_token(conn, developer_id=dev, token=f"tok-{uuid.uuid4().hex}")
            await conn.execute(
                "INSERT INTO github_identities (github_user_id, github_login, developer_id) VALUES ($1, $2, $3)",
                900_000_000 + uuid.uuid4().int % 1_000_000,
                f"probe-{dev}",
                dev,
            )
            await conn.execute("INSERT INTO organizations (id, name, slug) VALUES ($1, $1, $1)", org)
            await conn.execute(
                "INSERT INTO organization_members (organization_id, developer_id) VALUES ($1, $2)", org, dev
            )
            await conn.execute(
                "INSERT INTO audit_log (project_id, operation, target_id) VALUES ('uc4002/probe', 'probe', $1)", dev
            )
            for table in SENSITIVE_TABLES:
                assert await conn.fetchval(f"SELECT count(*) FROM public.{table}") >= 1, table
                # Two mistakes at once: SELECT granted back and a policy that lets everything through.
                await conn.execute(f"GRANT SELECT ON public.{table} TO anon")
                await conn.execute(
                    f"CREATE POLICY uc4002_leak ON public.{table} AS PERMISSIVE FOR SELECT TO anon USING (true)"
                )
                await conn.execute("SET LOCAL ROLE anon")
                seen = await conn.fetchval(f"SELECT count(*) FROM public.{table}")
                await conn.execute("RESET ROLE")
                assert seen == 0, f"{table}: anon read {seen} rows through a permissive policy"
        finally:
            await tr.rollback()
