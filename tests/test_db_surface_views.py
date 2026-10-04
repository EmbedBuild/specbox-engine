"""UC-4001 (US-40) — the board's views and its indicator / lifecycle functions
are closed by default.

Postgres-gated like the rest of the native suite. Supabase hands anon,
authenticated and service_role privileges on every new object of ``public``;
the fixture recreates that situation for the objects this UC covers (roles
created when missing, SELECT on the views and EXECUTE on the functions granted
to the public roles) and then re-applies the engine migrations, so every
assertion proves that migration 0023 closes what the platform defaults open:

- AC-01: every view of ``public`` runs with the invoker's rights and neither
  anon nor authenticated can read it — querying it as either role is a
  permission error, never rows.
- AC-02: the indicator and lifecycle functions have a pinned ``search_path``
  and only server-side roles may execute them; taking EXECUTE away does not
  stop the lifecycle triggers from recording a transition written by the
  server role.

The grants the fixture adds are exactly the ones 0023 revokes, so running this
module against a real Supabase leaves no extra privilege behind.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from server.db.migrate import apply_migrations
from server.db.pool import close_pool, get_pool, init_pool
from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

BOARD_VIEWS = (
    "project_kpis",
    "v_uc_lifecycle",
    "v_lifecycle_kpis",
    "v_us_progress",
    "v_weekly_throughput",
    "v_active_time_estimate",
)
ANALYTICS_VIEWS = BOARD_VIEWS[1:]  # 0014 + 0016 grant these to specbox_analytics_ro
SERVER_CALLABLE_FUNCTIONS = (
    "fn_lifecycle_kpis(text)",
    "fn_backfill_lifecycle(text, boolean)",
    "fn_recompute_lifecycle_columns(text)",
)
TRIGGER_FUNCTIONS = (
    "uc_lifecycle_columns()",
    "uc_record_transition()",
    "tool_access_log_append_only()",
    "uc_acceptance_void_on_state()",  # 0029 (US-76)
    "uc_acceptance_void_on_criterion()",
)
CLOSED_FUNCTIONS = SERVER_CALLABLE_FUNCTIONS + TRIGGER_FUNCTIONS
PUBLIC_ROLES = ("anon", "authenticated")
ALL_TABLE_PRIVILEGES = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]


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
            # What Supabase's default privileges give the public roles on these objects.
            await conn.execute("GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role")
            await conn.execute(f"GRANT SELECT ON {', '.join(BOARD_VIEWS)} TO anon, authenticated")
            await conn.execute(
                f"GRANT EXECUTE ON FUNCTION {', '.join(CLOSED_FUNCTIONS)} TO PUBLIC, anon, authenticated"
            )
        await apply_migrations(pool)
        yield pool
    finally:
        await close_pool()


async def _public_views(pool: asyncpg.Pool) -> dict[str, list[str] | None]:
    rows = await pool.fetch(
        "SELECT c.relname, c.reloptions FROM pg_class c "
        "WHERE c.relkind = 'v' AND c.relnamespace = 'public'::regnamespace"
    )
    return {r["relname"]: r["reloptions"] for r in rows}


def _runs_with_invoker_rights(reloptions: list[str] | None) -> bool:
    for option in reloptions or ():
        key, _, value = option.partition("=")
        if key == "security_invoker":
            return value.lower() in ("on", "true", "yes", "1")
    return False


async def _denied_as(conn: asyncpg.Connection, role: str, sql: str) -> None:
    """Run ``sql`` as ``role`` and require a permission error (42501)."""
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(f"SET LOCAL ROLE {role}")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(sql)
    finally:
        await tr.rollback()


# ── AC-01 — views ────────────────────────────────────────────────────


async def test_ac01_every_view_runs_with_the_invoker_rights(pool):
    views = await _public_views(pool)
    assert set(BOARD_VIEWS) <= set(views), f"board views missing: {set(BOARD_VIEWS) - set(views)}"
    bypassing = sorted(name for name, options in views.items() if not _runs_with_invoker_rights(options))
    assert bypassing == [], f"views evaluated with their owner's rights: {bypassing}"


async def test_ac01_public_roles_hold_no_privilege_on_any_view(pool):
    leaks = await pool.fetch(
        """
        SELECT c.relname, r.rolname, p.priv
          FROM pg_class c
         CROSS JOIN unnest($1::text[]) AS r(rolname)
         CROSS JOIN unnest($2::text[]) AS p(priv)
         WHERE c.relkind = 'v' AND c.relnamespace = 'public'::regnamespace
           AND has_table_privilege(r.rolname, c.oid, p.priv)
        """,
        list(PUBLIC_ROLES),
        ALL_TABLE_PRIVILEGES,
    )
    assert [tuple(row) for row in leaks] == []


async def test_ac01_reading_any_view_with_a_public_role_is_a_permission_error(pool):
    views = await _public_views(pool)
    async with pool.acquire() as conn:
        for view in sorted(views):
            for role in PUBLIC_ROLES:
                await _denied_as(conn, role, f'SELECT * FROM public."{view}" LIMIT 1')


async def test_ac01_server_side_roles_keep_their_reads(pool):
    for view in BOARD_VIEWS:
        assert await pool.fetchval(
            "SELECT has_table_privilege('service_role', $1::regclass, 'SELECT')", f"public.{view}"
        ), view
    for view in ANALYTICS_VIEWS:
        assert await pool.fetchval(
            "SELECT has_table_privilege('specbox_analytics_ro', $1::regclass, 'SELECT')", f"public.{view}"
        ), view


# ── AC-02 — functions ────────────────────────────────────────────────


async def test_ac02_functions_have_a_pinned_search_path(pool):
    for fn in CLOSED_FUNCTIONS:
        config = await pool.fetchval("SELECT proconfig FROM pg_proc WHERE oid = $1::regprocedure", f"public.{fn}")
        assert any(entry.startswith("search_path=") for entry in (config or [])), (fn, config)


async def test_ac02_only_server_side_roles_can_execute(pool):
    for fn in CLOSED_FUNCTIONS:
        signature = f"public.{fn}"
        for role in PUBLIC_ROLES:
            assert not await pool.fetchval(
                "SELECT has_function_privilege($1, $2::regprocedure, 'EXECUTE')", role, signature
            ), (role, fn)
        public_grants = await pool.fetchval(
            "SELECT count(*) FROM pg_proc p, aclexplode(p.proacl) a "
            "WHERE p.oid = $1::regprocedure AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'",
            signature,
        )
        assert public_grants == 0, fn
    for fn in SERVER_CALLABLE_FUNCTIONS:
        assert await pool.fetchval(
            "SELECT has_function_privilege('service_role', $1::regprocedure, 'EXECUTE')", f"public.{fn}"
        ), fn
    assert await pool.fetchval(
        "SELECT has_function_privilege('specbox_analytics_ro', 'public.fn_lifecycle_kpis(text)'::regprocedure, 'EXECUTE')"
    )


async def test_ac02_calling_the_functions_with_a_public_role_is_a_permission_error(pool):
    calls = (
        "SELECT * FROM public.fn_lifecycle_kpis('uc4001/none')",
        "SELECT public.fn_recompute_lifecycle_columns('uc4001/none')",
        "SELECT * FROM public.fn_backfill_lifecycle('uc4001/none', true)",
    )
    async with pool.acquire() as conn:
        for sql in calls:
            for role in PUBLIC_ROLES:
                await _denied_as(conn, role, sql)


async def test_ac02_lifecycle_triggers_fire_for_a_writer_without_execute(pool):
    """Taking EXECUTE away does not stop the triggers: Postgres checks it only when
    the trigger is created. The writer is a throwaway role with the table grants a
    server role holds and no EXECUTE at all (on Supabase, service_role does get an
    explicit EXECUTE from the default privileges, so it cannot prove this)."""
    project_id = f"uc4001/{uuid.uuid4().hex[:8]}"
    writer = f"uc4001_writer_{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(f"CREATE ROLE {writer} NOLOGIN BYPASSRLS")
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {writer}")
            await conn.execute(f"GRANT SELECT, UPDATE ON use_cases TO {writer}")
            await conn.execute(f"GRANT SELECT, INSERT ON uc_state_transitions TO {writer}")
            await conn.execute(f"GRANT USAGE ON SEQUENCE uc_state_transitions_id_seq TO {writer}")
            for fn in TRIGGER_FUNCTIONS:
                assert not await conn.fetchval(
                    "SELECT has_function_privilege($1, $2::regprocedure, 'EXECUTE')", writer, f"public.{fn}"
                ), fn
            await conn.execute(
                "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
                "VALUES ($1, $1, 'native', '', '{}'::jsonb)",
                project_id,
            )
            await conn.execute(
                "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'US', 'in_progress')",
                project_id,
            )
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name, state) "
                "VALUES ('UC-01', $1, 'US-01', 'UC', 'backlog')",
                project_id,
            )
            await conn.execute(f"SET LOCAL ROLE {writer}")
            await conn.execute(
                "UPDATE use_cases SET state = 'in_progress' WHERE project_id = $1 AND id = 'UC-01'", project_id
            )
            await conn.execute("RESET ROLE")
            moves = await conn.fetch(
                "SELECT from_state, to_state FROM uc_state_transitions WHERE project_id = $1 AND uc_id = 'UC-01'",
                project_id,
            )
            assert [tuple(m) for m in moves] == [("backlog", "in_progress")]
            assert await conn.fetchval(
                "SELECT started_at IS NOT NULL FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", project_id
            )
        finally:
            await tr.rollback()
