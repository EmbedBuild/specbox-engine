"""US-76 / UC-7601 — la aceptación humana de cada UC.

Hasta ahora «aceptado» era el veredicto de mark_ac, firmado por el dueño del token de la sesión: en
autopilot, la persona aunque marque el agente. La aceptación humana la da el owner o un admin del
proyecto desde el panel, una vez por UC (decisión de Jesús, 2026-10-04); el engine solo la lee.

- **AC-01**: la migración 0029 crea ``uc_acceptances`` cerrada a los roles públicos y con
  seguridad por filas, y la aceptación se anula sola si la UC sale de «done» o un criterio no
  interno queda sin hacer.
- **AC-02**: ``get_uc`` devuelve ``human_acceptance`` separado del veredicto de cada criterio
  (``verified``), y nada del servidor escribe en la tabla.

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

ROOT = Path(__file__).resolve().parents[1]


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _seed(pool, *, internal_ac: bool = True):
    """Proyecto con una UC hecha y sus criterios hechos (uno interno, si se pide)."""
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    project_id = f"Acme/uc-accept-{uuid.uuid4().hex[:8]}"
    developer_id = f"ua-dev-{uuid.uuid4().hex[:8]}"
    token = f"ua-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Ana Owner")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'UC accept')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'US', 'done')", project_id
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state, labels, meta) "
            "VALUES ('UC-001', $1, 'US-01', 'UC-001: UC', 'done', '[\"UC\"]'::jsonb, '{\"uc_id\": \"UC-001\"}'::jsonb)",
            project_id,
        )
        criteria = [("AC-01", False), ("AC-02", False)] + ([("AC-03", True)] if internal_ac else [])
        for ac_id, internal in criteria:
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, internal) "
                "VALUES ($1, $2, 'UC-001', $3, 'Criterio', true, $4)",
                f"UC-001::{ac_id}",
                project_id,
                ac_id,
                internal,
            )
    return project_id, developer_id, token


async def _accept(conn, project_id, developer_id):
    """Lo que hace el panel: una fila por UC aceptada."""
    await conn.execute(
        "INSERT INTO uc_acceptances (project_id, uc_id, accepted_by_developer_id) VALUES ($1, 'UC-001', $2)",
        project_id,
        developer_id,
    )


async def _accepted(conn, project_id) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT count(*) FROM uc_acceptances WHERE project_id = $1 AND uc_id = 'UC-001'", project_id
        )
    )


async def _cleanup(pool, project_id, developer_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


# ── AC-01 · la tabla ───────────────────────────────────────────────────


@pytestmark_pg
async def test_table_is_closed_to_roles_without_privileges():
    pool = await _pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE relname = 'uc_acceptances'")
        role = f"uc_accept_probe_{uuid.uuid4().hex[:6]}"
        await conn.execute(f"CREATE ROLE {role} NOLOGIN")
        try:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert not await conn.fetchval(
                    "SELECT has_table_privilege($1, 'public.uc_acceptances', $2)", role, privilege
                ), privilege
        finally:
            await conn.execute(f"DROP ROLE {role}")


@pytestmark_pg
async def test_acceptance_voids_when_the_uc_leaves_done():
    pool = await _pool()
    project_id, developer_id, _ = await _seed(pool)
    try:
        async with pool.acquire() as conn:
            await _accept(conn, project_id, developer_id)
            await conn.execute(
                "UPDATE use_cases SET name = 'renombrada' WHERE project_id = $1 AND id = 'UC-001'", project_id
            )
            assert await _accepted(conn, project_id), "otro cambio de la UC no la anula"
            await conn.execute(
                "UPDATE use_cases SET state = 'in_progress' WHERE project_id = $1 AND id = 'UC-001'", project_id
            )
            assert not await _accepted(conn, project_id), "reabrir la UC anula la aceptación"
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
async def test_acceptance_voids_when_a_visible_criterion_is_undone():
    pool = await _pool()
    project_id, developer_id, _ = await _seed(pool)
    try:
        async with pool.acquire() as conn:
            await _accept(conn, project_id, developer_id)
            await conn.execute(
                "UPDATE acceptance_criteria SET done = false WHERE project_id = $1 AND ac_id = 'AC-03'", project_id
            )
            assert await _accepted(conn, project_id), "deshacer un criterio interno no la anula"
            await conn.execute(
                "UPDATE acceptance_criteria SET done = false WHERE project_id = $1 AND ac_id = 'AC-01'", project_id
            )
            assert not await _accepted(conn, project_id), "deshacer un criterio visible la anula"

            await conn.execute("UPDATE acceptance_criteria SET done = true WHERE project_id = $1", project_id)
            await _accept(conn, project_id, developer_id)
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) "
                "VALUES ('UC-001::AC-04', $1, 'UC-001', 'AC-04', 'Nuevo')",
                project_id,
            )
            assert not await _accepted(conn, project_id), "un criterio nuevo sin hacer la anula"

            await conn.execute("UPDATE acceptance_criteria SET done = true WHERE project_id = $1", project_id)
            await conn.execute(
                "UPDATE acceptance_criteria SET done = false WHERE project_id = $1 AND ac_id = 'AC-03'", project_id
            )
            await _accept(conn, project_id, developer_id)
            await conn.execute(
                "UPDATE acceptance_criteria SET internal = false WHERE project_id = $1 AND ac_id = 'AC-03'", project_id
            )
            assert not await _accepted(conn, project_id), "un criterio interno sin hacer que pasa a visible la anula"
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
async def test_deleting_the_uc_deletes_its_acceptance():
    pool = await _pool()
    project_id, developer_id, _ = await _seed(pool)
    try:
        async with pool.acquire() as conn:
            await _accept(conn, project_id, developer_id)
            await conn.execute("DELETE FROM acceptance_criteria WHERE project_id = $1", project_id)
            await conn.execute("DELETE FROM use_cases WHERE project_id = $1", project_id)
            assert not await _accepted(conn, project_id)
    finally:
        await _cleanup(pool, project_id, developer_id)


# ── AC-02 · la lectura ────────────────────────────────────────────────


@pytestmark_pg
async def test_get_uc_returns_the_human_acceptance_apart_from_each_verdict(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_driven

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        backend = NativeBackend(project_id=project_id, dev_token=token)

        async def _session_backend(ctx, items_content=None):
            return backend

        monkeypatch.setattr(spec_driven, "get_session_backend", _session_backend)

        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        assert uc["human_acceptance"] is None, "sin aceptación del panel no hay human_acceptance"
        for ac in uc["acceptance_criteria"]:
            assert "verified" in ac and ac["accepted"] == ac["verified"]

        async with pool.acquire() as conn:
            await _accept(conn, project_id, developer_id)
        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        acceptance = uc["human_acceptance"]
        assert acceptance["by"] == "Ana Owner" and acceptance["by_id"] == developer_id and acceptance["at"]
    finally:
        await _cleanup(pool, project_id, developer_id)


def test_nothing_in_the_server_writes_uc_acceptances():
    """Solo el panel acepta: ninguna tool ni backend del engine escribe en la tabla."""
    writes = re.compile(
        r"(INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE)\s+(?:TABLE\s+)?(?:public\.)?uc_acceptances\b", re.I
    )
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for path in (ROOT / "server").rglob("*.py")
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if writes.search(line)
    ]
    assert offenders == [], offenders
