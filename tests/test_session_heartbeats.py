"""US-99 / UC-9901 — el latido de cada sesión de Claude Code en el board.

- **AC-01**: el latido lleva proyecto, desarrollador, UC, fase, si espera y la hora; pesa menos de
  1 KB y no tiene dónde guardar texto de la conversación ni de las specs.
- **AC-02**: al cerrar la sesión o a los quince minutos sin latido, el board la da por terminada.
- **AC-04**: solo los miembros del proyecto y el SuperAdmin leen los latidos; un token revocado no
  los escribe. Sobre Postgres real.

(AC-03, que el latido nunca bloquee la sesión, lo prueban las pruebas del hook.)

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import uuid

import pytest

from server.tools.session_heartbeat import (
    MAX_BYTES,
    PHASES,
    get_live_session,
    report_session_heartbeat,
    validate_heartbeat,
)
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

SESSION = "3f2c9a1e-7b44-4d2a-9c11-0a5b6e7d8f90"


# ── Validación (pura) ──────────────────────────────────────────────────


def _valid(**over):
    base = dict(project_id="Acme/app", session_id=SESSION, phase="implement", uc_id="UC-9901", waiting="none", ended=False)
    base.update(over)
    return validate_heartbeat(**base)


def test_a_complete_heartbeat_is_valid_and_small():
    assert _valid() is None
    assert _valid(uc_id=None, phase="idle", waiting="permission", ended=True) is None
    assert MAX_BYTES == 1024


@pytest.mark.parametrize(
    "over",
    [
        {"phase": "escribiendo la US-99 con el cliente"},
        {"waiting": "a la espera de que Jesús lea el PR"},
        {"uc_id": "UC-9901: Latido de sesión al board"},
        {"session_id": "no es un id de sesión"},
        {"project_id": "Acme/app con espacios"},
    ],
)
def test_free_text_has_nowhere_to_go(over):
    """AC-01: ningún campo admite texto libre, así que la conversación no cabe en el latido."""
    error = _valid(**over)
    assert error is not None and error["code"] == "INVALID_HEARTBEAT"


def test_the_phases_are_the_pipeline_ones():
    assert PHASES == {"idle", "discovery", "prd", "plan", "design", "implement", "tests", "review", "release"}


# ── Postgres ───────────────────────────────────────────────────────────


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _developer(conn, *, member_of: str | None = None, role: str = "member"):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    developer_id = f"hb-dev-{uuid.uuid4().hex[:8]}"
    token = f"hb-tok-{uuid.uuid4().hex[:16]}"
    await register_developer(conn, developer_id=developer_id, display_name="Persona de prueba")
    await register_mcp_token(conn, developer_id=developer_id, token=token)
    if member_of:
        await add_project_member(conn, project_id=member_of, developer_id=developer_id, role=role)
    return developer_id, token


async def _seed(pool):
    project_id = f"Acme/heartbeat-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Latido')", project_id)
        owner = await _developer(conn, member_of=project_id, role="project_admin")
        stranger = await _developer(conn)
    return project_id, owner, stranger


async def _cleanup(pool, project_id, *developers):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        for developer_id, _ in developers:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


async def _row(pool, project_id):
    return await pool.fetchrow("SELECT * FROM session_heartbeats WHERE project_id = $1", project_id)


@pytestmark_pg
async def test_table_is_closed_to_roles_without_privileges_and_has_no_free_text_column():
    pool = await _pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE relname = 'session_heartbeats'")
        role = f"hb_probe_{uuid.uuid4().hex[:6]}"
        await conn.execute(f"CREATE ROLE {role} NOLOGIN")
        try:
            for objeto in ("public.session_heartbeats", "public.v_live_sessions", "public.v_project_live_sessions"):
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    assert not await conn.fetchval(
                        "SELECT has_table_privilege($1, $2, $3)", role, objeto, privilege
                    ), (objeto, privilege)
        finally:
            await conn.execute(f"DROP ROLE {role}")
        columnas = {
            r["column_name"]
            for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'session_heartbeats'"
            )
        }
    assert columnas == {
        "project_id", "session_id", "developer_id", "uc_id", "phase", "waiting", "waiting_since",
        "started_at", "last_beat_at", "ended_at", "ended_reason",
    }


@pytestmark_pg
async def test_a_member_reports_and_the_board_keeps_one_row_per_session():
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        out = await report_session_heartbeat(
            None, SESSION, "plan", uc_id="UC-9901", project_id=project_id, dev_token=owner[1]
        )
        assert out["success"] and out["state"] == "live"
        primero = await _row(pool, project_id)
        assert (primero["developer_id"], primero["uc_id"], primero["phase"], primero["waiting"]) == (
            owner[0], "UC-9901", "plan", "none",
        )
        assert primero["waiting_since"] is None

        out = await report_session_heartbeat(
            None, SESSION, "implement", uc_id="UC-9901", waiting="permission", project_id=project_id, dev_token=owner[1]
        )
        segundo = await _row(pool, project_id)
        assert segundo["phase"] == "implement" and segundo["waiting"] == "permission"
        assert segundo["waiting_since"] is not None
        assert segundo["started_at"] == primero["started_at"]
        assert segundo["last_beat_at"] >= primero["last_beat_at"]

        # Mientras sigue esperando lo mismo, «desde cuándo» no se mueve; al volver la persona, se borra.
        await report_session_heartbeat(
            None, SESSION, "implement", uc_id="UC-9901", waiting="permission", project_id=project_id, dev_token=owner[1]
        )
        assert (await _row(pool, project_id))["waiting_since"] == segundo["waiting_since"]
        await report_session_heartbeat(
            None, SESSION, "implement", uc_id="UC-9901", project_id=project_id, dev_token=owner[1]
        )
        assert (await _row(pool, project_id))["waiting_since"] is None
        assert await pool.fetchval("SELECT count(*) FROM session_heartbeats WHERE project_id = $1", project_id) == 1
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_closing_the_session_ends_it_and_a_quiet_one_ends_at_fifteen_minutes():
    """AC-02."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    otra = "9a8b7c6d-0000-4000-8000-123456789abc"
    try:
        await report_session_heartbeat(None, SESSION, "implement", project_id=project_id, dev_token=owner[1])
        out = await report_session_heartbeat(
            None, SESSION, "idle", ended=True, project_id=project_id, dev_token=owner[1]
        )
        assert out["state"] == "ended"
        cerrada = await _row(pool, project_id)
        assert cerrada["ended_reason"] == "closed" and cerrada["ended_at"] is not None

        await report_session_heartbeat(None, otra, "tests", project_id=project_id, dev_token=owner[1])
        vista = await pool.fetchrow("SELECT * FROM v_live_sessions WHERE project_id = $1", project_id)
        assert vista["session_id"] == otra and vista["stale"] is False

        # Catorce minutos sin latido: sigue viva. Dieciséis: «sin señal» y el barrido la cierra.
        await pool.execute(
            "UPDATE session_heartbeats SET last_beat_at = now() - interval '14 minutes' WHERE session_id = $1", otra
        )
        assert await pool.fetchval("SELECT close_stale_sessions()") == 0
        await pool.execute(
            "UPDATE session_heartbeats SET last_beat_at = now() - interval '16 minutes' WHERE session_id = $1", otra
        )
        assert (await pool.fetchrow("SELECT stale FROM v_live_sessions WHERE project_id = $1", project_id))["stale"]
        assert await pool.fetchval("SELECT close_stale_sessions()") >= 1
        fila = await pool.fetchrow("SELECT ended_reason FROM session_heartbeats WHERE session_id = $1", otra)
        assert fila["ended_reason"] == "timeout"
        assert await pool.fetchrow("SELECT * FROM v_live_sessions WHERE project_id = $1", project_id) is None
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_a_stranger_cannot_write_and_learns_nothing():
    """AC-04: quien no es miembro recibe lo mismo que si el proyecto no existiera."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        out = await report_session_heartbeat(None, SESSION, "implement", project_id=project_id, dev_token=stranger[1])
        assert out["code"] == "PROJECT_NOT_VISIBLE"
        inexistente = await report_session_heartbeat(
            None, SESSION, "implement", project_id="Acme/no-existe", dev_token=stranger[1]
        )
        assert inexistente["code"] == out["code"]
        assert await _row(pool, project_id) is None
        assert (await report_session_heartbeat(None, SESSION, "implement", project_id=project_id))["code"] == (
            "UNAUTHENTICATED"
        )
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_a_revoked_token_cannot_write():
    """AC-04."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        await pool.execute("UPDATE mcp_tokens SET revoked_at = now() WHERE developer_id = $1", owner[0])
        out = await report_session_heartbeat(None, SESSION, "implement", project_id=project_id, dev_token=owner[1])
        assert out["code"] == "UNAUTHENTICATED"
        assert await _row(pool, project_id) is None
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_another_member_cannot_overwrite_someone_elses_session():
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    async with pool.acquire() as conn:
        colega = await _developer(conn, member_of=project_id)
    try:
        await report_session_heartbeat(None, SESSION, "implement", project_id=project_id, dev_token=owner[1])
        out = await report_session_heartbeat(
            None, SESSION, "idle", ended=True, project_id=project_id, dev_token=colega[1]
        )
        assert out["code"] == "PROJECT_NOT_VISIBLE"
        fila = await _row(pool, project_id)
        assert fila["developer_id"] == owner[0] and fila["ended_at"] is None
    finally:
        await _cleanup(pool, project_id, owner, stranger, colega)


@pytestmark_pg
async def test_only_members_and_the_superadmin_read_the_live_session(monkeypatch):
    """AC-04."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        await report_session_heartbeat(
            None, SESSION, "review", uc_id="UC-9901", waiting="decision", project_id=project_id, dev_token=owner[1]
        )
        leida = await get_live_session(None, project_id=project_id, dev_token=owner[1])
        assert leida["session"]["uc_id"] == "UC-9901"
        assert leida["session"]["waiting"] == "decision" and leida["session"]["stale"] is False

        ajena = await get_live_session(None, project_id=project_id, dev_token=stranger[1])
        assert ajena["code"] == "PROJECT_NOT_VISIBLE" and "session" not in ajena

        monkeypatch.setenv("SPECBOX_OPERATOR_DEVELOPER_IDS", stranger[0])
        operador = await get_live_session(None, project_id=project_id, dev_token=stranger[1])
        assert operador["session"]["session_id"] == SESSION

        assert (await get_live_session(None, project_id=project_id))["code"] == "UNAUTHENTICATED"
    finally:
        await _cleanup(pool, project_id, owner, stranger)


# ── Todas las sesiones vivas del proyecto (US-99 · UC-10609) ───────────

OTRA = "9a8b7c6d-0000-4000-8000-123456789abc"
TERCERA = "5e6f7a8b-1111-4111-8111-abcdefabcdef"


@pytestmark_pg
async def test_two_sessions_at_once_are_both_live_ordered_by_last_beat():
    """AC-01: dos sesiones a la vez en repositorios distintos del mismo board (cada satélite manda su
    latido al board del orquestador) aparecen las dos, con su UC, su fase y si esperan, de la del
    último latido a la más antigua. La sesión «viva» de siempre sigue siendo la última."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    async with pool.acquire() as conn:
        colega = await _developer(conn, member_of=project_id)
    try:
        # La del satélite cloud empieza antes; la de la app, después y esperando una respuesta.
        await report_session_heartbeat(
            None, SESSION, "implement", uc_id="UC-10610", project_id=project_id, dev_token=owner[1]
        )
        await report_session_heartbeat(
            None, OTRA, "tests", uc_id="UC-10611", waiting="decision", project_id=project_id, dev_token=colega[1]
        )
        await pool.execute(
            "UPDATE session_heartbeats SET last_beat_at = now() - interval '3 minutes' WHERE session_id = $1", SESSION
        )

        leida = await get_live_session(None, project_id=project_id, dev_token=owner[1])
        sesiones = leida["sessions"]
        assert [s["session_id"] for s in sesiones] == [OTRA, SESSION]
        assert [(s["uc_id"], s["phase"], s["waiting"]) for s in sesiones] == [
            ("UC-10611", "tests", "decision"),
            ("UC-10610", "implement", "none"),
        ]
        assert sesiones[0]["waiting_since"] is not None and sesiones[1]["waiting_since"] is None
        assert sesiones[0]["developer_id"] == colega[0]
        assert sesiones[0]["last_beat_at"] > sesiones[1]["last_beat_at"]
        # Compatibilidad: `session` es la del último latido, como antes.
        assert leida["session"]["session_id"] == OTRA

        # Un latido nuevo de la primera la sube arriba.
        await report_session_heartbeat(
            None, SESSION, "review", uc_id="UC-10610", project_id=project_id, dev_token=owner[1]
        )
        orden = [s["session_id"] for s in (await get_live_session(None, project_id=project_id, dev_token=owner[1]))["sessions"]]
        assert orden == [SESSION, OTRA]
    finally:
        await _cleanup(pool, project_id, owner, stranger, colega)


@pytestmark_pg
async def test_closed_and_quiet_sessions_are_left_out_of_the_live_list():
    """AC-02: una sesión cerrada, o sin latido en quince minutos, no está en la lista; aunque el
    barrido aún no haya cerrado la callada."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        for sesion, fase in ((SESSION, "implement"), (OTRA, "plan"), (TERCERA, "tests")):
            await report_session_heartbeat(None, sesion, fase, project_id=project_id, dev_token=owner[1])

        await report_session_heartbeat(None, OTRA, "idle", ended=True, project_id=project_id, dev_token=owner[1])
        await pool.execute(
            "UPDATE session_heartbeats SET last_beat_at = now() - interval '16 minutes' WHERE session_id = $1", TERCERA
        )
        await pool.execute(
            "UPDATE session_heartbeats SET last_beat_at = now() - interval '14 minutes' WHERE session_id = $1", SESSION
        )

        leida = await get_live_session(None, project_id=project_id, dev_token=owner[1])
        assert [s["session_id"] for s in leida["sessions"]] == [SESSION]
        # Sin barrer todavía, la callada sigue sin terminar en la tabla: la lista la deja fuera igual.
        assert (await pool.fetchval("SELECT ended_at FROM session_heartbeats WHERE session_id = $1", TERCERA)) is None

        # Pasados los quince minutos, la última también sale; sin ninguna, la lista queda vacía.
        await pool.execute(
            "UPDATE session_heartbeats SET last_beat_at = now() - interval '15 minutes 1 second' WHERE session_id = $1",
            SESSION,
        )
        assert (await get_live_session(None, project_id=project_id, dev_token=owner[1]))["sessions"] == []
        await pool.fetchval("SELECT close_stale_sessions()")
        vacia = await get_live_session(None, project_id=project_id, dev_token=owner[1])
        assert vacia["session"] is None and vacia["sessions"] == []
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_the_live_list_only_has_this_projects_sessions_and_strangers_see_nothing():
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    otro_id, otro_owner, otro_stranger = await _seed(pool)
    try:
        await report_session_heartbeat(None, SESSION, "implement", project_id=project_id, dev_token=owner[1])
        await report_session_heartbeat(None, OTRA, "plan", project_id=otro_id, dev_token=otro_owner[1])
        leida = await get_live_session(None, project_id=project_id, dev_token=owner[1])
        assert [s["session_id"] for s in leida["sessions"]] == [SESSION]
        ajena = await get_live_session(None, project_id=project_id, dev_token=stranger[1])
        assert ajena["code"] == "PROJECT_NOT_VISIBLE" and "sessions" not in ajena
    finally:
        await _cleanup(pool, project_id, owner, stranger)
        await _cleanup(pool, otro_id, otro_owner, otro_stranger)
