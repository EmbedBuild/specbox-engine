"""US-100 / UC-10001 — el board apunta los eventos que merecen un aviso (migración 0033).

- **AC-01**: cuando una UC pasa a hecha, una historia se cierra, una UC queda lista para aceptar, una
  sesión espera una respuesta o una sesión se para, el board registra un evento con proyecto, tipo,
  objetivo y hora en la misma transacción del cambio (muy por debajo de dos segundos), sin texto de
  specs ni datos personales.
- **AC-02** (la parte del board): un mismo cambio produce un solo evento aunque se repita, se reintente
  o el trigger vuelva a saltar. Que cada evento llegue una sola vez a cada dispositivo lo cierra el
  panel con su clave única por (evento, dispositivo) (UC-10002).

Sobre Postgres real; SKIP limpio sin base de desarrollo (``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.db.migrate import apply_migrations
from server.db.pool import close_pool, get_pool, init_pool
from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

PASA = [{"type": "test", "label": "prueba", "passed": True}]
NO_PASA = [{"type": "test", "label": "prueba", "passed": False}]


@pytest.fixture(autouse=True)
async def _pool():
    await init_pool(dsn=DSN)
    pool = await get_pool()
    await apply_migrations(pool)
    try:
        yield
    finally:
        await close_pool()


@pytest.fixture
async def proyecto():
    pool = await get_pool()
    project_id = f"Acme/avisos-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Avisos')", project_id)
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'Historia', 'in_progress')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state) VALUES ('UC-101', $1, 'US-01', 'Caso', 'in_progress')",
            project_id,
        )
        for ac in ("AC-01", "AC-02"):
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) VALUES ($1, $2, 'UC-101', $3, 'Criterio secreto del cliente')",
                f"UC-101::{ac}", project_id, ac,
            )
    yield project_id
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)


async def _eventos(project_id: str, kind: str | None = None) -> list[dict]:
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT kind, target_id, event_key, occurred_at FROM notification_events "
        "WHERE project_id = $1 AND ($2::text IS NULL OR kind = $2) ORDER BY id",
        project_id, kind,
    )
    return [dict(r) for r in rows]


async def _uc(project_id: str, estado: str) -> None:
    pool = await get_pool()
    await pool.execute("UPDATE use_cases SET state = $2 WHERE project_id = $1 AND id = 'UC-101'", project_id, estado)


async def _criterio(project_id: str, ac: str, *, done: bool, evidencia=None, internal: bool | None = None) -> None:
    pool = await get_pool()
    meta = json.dumps({"evidence": evidencia} if evidencia is not None else {})
    if internal is None:
        await pool.execute(
            "UPDATE acceptance_criteria SET done = $3, meta = $4::jsonb WHERE project_id = $1 AND id = $2",
            project_id, f"UC-101::{ac}", done, meta,
        )
    else:
        await pool.execute(
            "UPDATE acceptance_criteria SET done = $3, meta = $4::jsonb, internal = $5 WHERE project_id = $1 AND id = $2",
            project_id, f"UC-101::{ac}", done, meta, internal,
        )


async def test_table_is_closed_to_roles_without_privileges():
    pool = await get_pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE relname = 'notification_events'")
        role = f"ne_probe_{uuid.uuid4().hex[:6]}"
        await conn.execute(f"CREATE ROLE {role} NOLOGIN")
        try:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert not await conn.fetchval(
                    "SELECT has_table_privilege($1, 'public.notification_events', $2)", role, privilege
                ), privilege
            assert not await conn.fetchval(
                "SELECT has_function_privilege($1, 'public.notification_event_add(text,text,text,text)', 'EXECUTE')", role
            )
        finally:
            await conn.execute(f"DROP ROLE {role}")


async def test_uc_done_once_per_transition(proyecto):
    """AC-01 y AC-02: cada paso a hecha, un evento; repetir el mismo estado no apunta otro."""
    await _uc(proyecto, "done")
    await _uc(proyecto, "done")
    eventos = await _eventos(proyecto, "uc_done")
    assert [(e["kind"], e["target_id"]) for e in eventos] == [("uc_done", "UC-101")]
    await _uc(proyecto, "review")
    await _uc(proyecto, "done")
    assert len(await _eventos(proyecto, "uc_done")) == 2


async def test_uc_ready_follows_the_panel_rule(proyecto):
    """AC-01: «lista para aceptar» = hecha, sin aceptación, criterios visibles hechos con recibo que pasa."""
    await _criterio(proyecto, "AC-01", done=True, evidencia=PASA)
    await _uc(proyecto, "done")
    assert await _eventos(proyecto, "uc_ready") == []  # AC-02 sin hacer
    await _criterio(proyecto, "AC-02", done=True, evidencia=NO_PASA)
    assert await _eventos(proyecto, "uc_ready") == []  # un recibo que no pasa no cuenta
    await _criterio(proyecto, "AC-02", done=True, evidencia=PASA)
    eventos = await _eventos(proyecto, "uc_ready")
    assert [(e["kind"], e["target_id"]) for e in eventos] == [("uc_ready", "UC-101")]
    # Otro cambio de un criterio con la UC ya lista no apunta otro evento.
    await _criterio(proyecto, "AC-01", done=True, evidencia=PASA + PASA)
    assert len(await _eventos(proyecto, "uc_ready")) == 1


async def test_uc_ready_ignores_internal_criteria_and_accepted_ucs(proyecto):
    pool = await get_pool()
    await _criterio(proyecto, "AC-01", done=True, evidencia=PASA)
    await _criterio(proyecto, "AC-02", done=False, internal=True)  # interno: no cuenta
    await pool.execute(
        "INSERT INTO uc_acceptances (project_id, uc_id, accepted_by_developer_id) VALUES ($1, 'UC-101', 'dev-x')", proyecto
    )
    await _uc(proyecto, "done")
    assert await _eventos(proyecto, "uc_ready") == []  # ya aceptada
    await pool.execute("DELETE FROM uc_acceptances WHERE project_id = $1", proyecto)
    await _criterio(proyecto, "AC-01", done=True, evidencia=PASA)  # un cambio vuelve a mirarla
    assert [e["target_id"] for e in await _eventos(proyecto, "uc_ready")] == ["UC-101"]


async def test_uc_ready_again_after_completing_again(proyecto):
    """Una vez por cada vez que se completa (completed_at cambia)."""
    for ac in ("AC-01", "AC-02"):
        await _criterio(proyecto, ac, done=True, evidencia=PASA)
    await _uc(proyecto, "done")
    await _uc(proyecto, "review")
    await _uc(proyecto, "done")
    assert len(await _eventos(proyecto, "uc_ready")) == 2


async def test_us_done_once_per_close_and_once_per_transaction(proyecto):
    pool = await get_pool()
    await pool.execute("UPDATE user_stories SET state = 'done' WHERE project_id = $1", proyecto)
    await pool.execute("UPDATE user_stories SET state = 'done' WHERE project_id = $1", proyecto)
    assert [(e["kind"], e["target_id"]) for e in await _eventos(proyecto, "us_done")] == [("us_done", "US-01")]
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("UPDATE user_stories SET state = 'review' WHERE project_id = $1", proyecto)
        await conn.execute("UPDATE user_stories SET state = 'done' WHERE project_id = $1", proyecto)
        await conn.execute("UPDATE user_stories SET state = 'review' WHERE project_id = $1", proyecto)
        await conn.execute("UPDATE user_stories SET state = 'done' WHERE project_id = $1", proyecto)
    assert len(await _eventos(proyecto, "us_done")) == 2  # el segundo cierre, una sola vez


async def test_session_waiting_and_stopped(proyecto):
    pool = await get_pool()
    sesion = "3f2c9a1e-7b44-4d2a-9c11-0a5b6e7d8f90"
    await pool.execute(
        "INSERT INTO session_heartbeats (project_id, session_id, developer_id, uc_id, phase) VALUES ($1, $2, 'dev-x', 'UC-101', 'implement')",
        proyecto, sesion,
    )
    espera = "UPDATE session_heartbeats SET waiting = 'decision', waiting_since = now() - make_interval(secs => $3) WHERE project_id = $1 AND session_id = $2"
    await pool.execute(espera, proyecto, sesion, 0.0)
    await pool.execute("UPDATE session_heartbeats SET last_beat_at = now() WHERE project_id = $1 AND session_id = $2", proyecto, sesion)
    assert [(e["kind"], e["target_id"]) for e in await _eventos(proyecto, "session_waiting")] == [("session_waiting", "UC-101")]
    await pool.execute(
        "UPDATE session_heartbeats SET waiting = 'none', waiting_since = NULL WHERE project_id = $1 AND session_id = $2", proyecto, sesion
    )
    await pool.execute(espera, proyecto, sesion, 0.0)
    assert len(await _eventos(proyecto, "session_waiting")) == 2  # otra espera, otro aviso

    # Se cierra por tiempo con una UC abierta: «sesión parada», una vez.
    await pool.execute("SELECT close_stale_sessions(interval '0 seconds')")
    await pool.execute("SELECT close_stale_sessions(interval '0 seconds')")
    assert [(e["kind"], e["target_id"]) for e in await _eventos(proyecto, "session_stopped")] == [("session_stopped", "UC-101")]

    # Cerrada a mano, o por tiempo sin UC: sin aviso.
    otra, sin_uc = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee"
    await pool.execute(
        "INSERT INTO session_heartbeats (project_id, session_id, developer_id, uc_id, phase) VALUES ($1, $2, 'dev-x', 'UC-101', 'tests'), ($1, $3, 'dev-x', NULL, 'idle')",
        proyecto, otra, sin_uc,
    )
    await pool.execute(
        "UPDATE session_heartbeats SET ended_at = now(), ended_reason = 'closed' WHERE project_id = $1 AND session_id = $2", proyecto, otra
    )
    await pool.execute("SELECT close_stale_sessions(interval '0 seconds')")
    assert len(await _eventos(proyecto, "session_stopped")) == 1


async def test_events_are_written_with_the_change_and_carry_no_spec_text(proyecto):
    """AC-01: en la misma transacción que el cambio; solo identificadores, nunca nombres ni criterios."""
    pool = await get_pool()
    async with pool.acquire() as conn, conn.transaction():
        antes = await conn.fetchval("SELECT clock_timestamp()")
        await conn.execute("UPDATE use_cases SET state = 'done' WHERE project_id = $1 AND id = 'UC-101'", proyecto)
        dentro = await conn.fetch("SELECT occurred_at FROM notification_events WHERE project_id = $1", proyecto)
        assert len(dentro) == 1  # visible ya dentro de la transacción del cambio
        assert (dentro[0]["occurred_at"] - antes).total_seconds() < 2
    filas = await pool.fetch("SELECT * FROM notification_events WHERE project_id = $1", proyecto)
    texto = json.dumps([dict(r) for r in filas], default=str)
    for prohibido in ("Criterio secreto del cliente", "Caso", "Historia"):
        assert prohibido not in texto
    columnas = await pool.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'notification_events' ORDER BY ordinal_position"
    )
    assert [c["column_name"] for c in columnas] == [
        "id", "project_id", "kind", "target_id", "event_key", "occurred_at", "dispatched_at",
    ]


async def test_retries_do_not_duplicate(proyecto):
    """AC-02: reintentar el mismo evento (misma clave) no crea otra fila."""
    pool = await get_pool()
    for _ in range(3):
        await pool.execute("SELECT notification_event_add($1, 'uc_done', 'UC-101', 'UC-101:reintento')", proyecto)
    rows = await pool.fetch(
        "SELECT event_key FROM notification_events WHERE project_id = $1 AND event_key = 'uc_done:UC-101:reintento'", proyecto
    )
    assert len(rows) == 1


async def test_free_form_ids_get_events_and_a_failed_event_never_blocks_the_change():
    """Un aviso nunca bloquea el board: ids libres funcionan y un evento imposible se pierde, el cambio no."""
    pool = await get_pool()
    project_id = f"Acme/ids-libres-{uuid.uuid4().hex[:8]}"
    largo = "UC-" + "X" * 70
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Ids')", project_id)
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-VSCODE-AUTOCLONE', $1, 'H', 'in_progress')",
            project_id,
        )
        for uc in ("UC-A", largo):
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name, state) VALUES ($1, $2, 'US-VSCODE-AUTOCLONE', 'C', 'in_progress')",
                uc, project_id,
            )
    try:
        await pool.execute("UPDATE use_cases SET state = 'done' WHERE project_id = $1", project_id)
        await pool.execute("UPDATE user_stories SET state = 'done' WHERE project_id = $1", project_id)
        estados = await pool.fetch("SELECT id, state FROM use_cases WHERE project_id = $1 ORDER BY id", project_id)
        assert {r["state"] for r in estados} == {"done"}  # el cambio entra aunque un evento no quepa
        eventos = await _eventos(project_id)
        assert ("uc_done", "UC-A") in [(e["kind"], e["target_id"]) for e in eventos]
        assert ("us_done", "US-VSCODE-AUTOCLONE") in [(e["kind"], e["target_id"]) for e in eventos]
        assert largo not in [e["target_id"] for e in eventos]
    finally:
        await pool.execute("DELETE FROM projects WHERE project_id = $1", project_id)
