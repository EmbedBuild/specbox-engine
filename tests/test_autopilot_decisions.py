"""US-99 / UC-9902 — las decisiones aplazadas del autopilot en el board.

- **AC-01**: una decisión aplazada se publica con proyecto, UC, pregunta, opciones y opción por
  defecto, con el mismo id que la cola del proyecto, y sin credenciales.
- **AC-02**: resolverla deja quién, cuándo y qué opción; la siguiente sesión la recoge una sola vez
  y la trata como resuelta.
- **AC-03**: la lista de pendientes respeta la pertenencia: un proyecto ajeno responde como si no
  existiera.

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.app_docs.autopilot import evaluate_decision
from server.tools.autopilot_decisions import (
    list_pending_decisions,
    publish_decision,
    resolve_decision,
    take_resolved_decisions,
    validate_decision,
)
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

OPCIONES = [
    {"id": "ep-17", "label": "EP-17 SpecBox Mobile"},
    {"id": "nueva", "label": "Una épica nueva"},
]
PREGUNTA = "¿A qué épica va la historia de avisos en el teléfono?"
DQ = "dq-20261024T214500-a1b2-featur"


# ── Validación (pura) ──────────────────────────────────────────────────


def _valid(**over):
    base = dict(
        decision_key="feature_epic_assignment",
        question=PREGUNTA,
        options=OPCIONES,
        default_option="ep-17",
        uc_id="UC-10001",
        decision_id=DQ,
    )
    base.update(over)
    return validate_decision(**base)


def test_a_complete_decision_is_valid():
    assert _valid() is None
    assert _valid(uc_id=None, decision_id="") is None


@pytest.mark.parametrize(
    "over,code",
    [
        ({"decision_key": "destructive_action"}, "QUEUE_NOT_ALLOWED"),
        ({"decision_key": "definition_quality_gate"}, "QUEUE_NOT_ALLOWED"),
        ({"question": "¿Uso la api key sk_live_51Abc para el cobro?"}, "SENSITIVE_DATA"),
        ({"options": [{"id": "a", "label": "Con la contraseña de la cuenta de revisión"}, {"id": "b", "label": "Sin ella"}], "default_option": "a"}, "SENSITIVE_DATA"),
        ({"options": OPCIONES[:1]}, "INVALID_DECISION"),
        ({"options": OPCIONES * 4}, "INVALID_DECISION"),
        ({"default_option": "otra"}, "INVALID_DECISION"),
        ({"options": [{"id": "Mayúsculas y espacios", "label": "x"}, OPCIONES[1]]}, "INVALID_DECISION"),
        ({"question": "?" * 301}, "INVALID_DECISION"),
        ({"decision_id": "cualquier-cosa"}, "INVALID_DECISION"),
    ],
)
def test_what_cannot_be_published(over, code):
    """AC-01: ni las que no se aplazan, ni credenciales, ni formas que el panel no sabría pintar."""
    error = _valid(**over)
    assert error is not None and error["code"] == code


def test_the_autopilot_queues_what_it_would_ask_when_the_queue_is_on(tmp_path):
    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"specbox": {"autopilot": {"level": "agresivo", "queue_enabled": True}}}))
    ctx = {"projectPath": str(tmp_path), "defaultOption": "ep-17"}
    assert evaluate_decision("feature_epic_assignment", ctx)["action"] == "queue"
    # Sin opción por defecto, se pregunta; las inviolables y las que definen la feature, nunca se aplazan.
    assert evaluate_decision("feature_epic_assignment", {"projectPath": str(tmp_path)})["action"] == "ask"
    assert evaluate_decision("destructive_action", ctx)["action"] == "ask"
    assert evaluate_decision("feature_problem_definition", ctx)["action"] == "ask"
    settings.write_text(json.dumps({"specbox": {"autopilot": {"level": "agresivo"}}}))
    assert evaluate_decision("feature_epic_assignment", ctx)["action"] == "ask"


# ── Postgres ───────────────────────────────────────────────────────────


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _developer(conn, *, member_of: str | None = None, name: str = "Persona de prueba"):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    developer_id = f"dq-dev-{uuid.uuid4().hex[:8]}"
    token = f"dq-tok-{uuid.uuid4().hex[:16]}"
    await register_developer(conn, developer_id=developer_id, display_name=name)
    await register_mcp_token(conn, developer_id=developer_id, token=token)
    if member_of:
        await add_project_member(conn, project_id=member_of, developer_id=developer_id, role="member")
    return developer_id, token


async def _seed(pool):
    project_id = f"Acme/decisions-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Decisiones')", project_id)
        owner = await _developer(conn, member_of=project_id, name="Ana Owner")
        stranger = await _developer(conn)
    return project_id, owner, stranger


async def _cleanup(pool, project_id, *developers):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        for developer_id, _ in developers:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


async def _publish(project_id, token, **over):
    args = dict(
        decision_key="feature_epic_assignment",
        question=PREGUNTA,
        options=OPCIONES,
        default_option="ep-17",
        uc_id="UC-10001",
        decision_id=DQ,
        project_id=project_id,
        dev_token=token,
    )
    args.update(over)
    return await publish_decision(None, **args)


@pytestmark_pg
async def test_table_is_closed_to_roles_without_privileges():
    pool = await _pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE relname = 'autopilot_decisions'")
        role = f"dq_probe_{uuid.uuid4().hex[:6]}"
        await conn.execute(f"CREATE ROLE {role} NOLOGIN")
        try:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert not await conn.fetchval(
                    "SELECT has_table_privilege($1, 'public.autopilot_decisions', $2)", role, privilege
                ), privilege
        finally:
            await conn.execute(f"DROP ROLE {role}")


@pytestmark_pg
async def test_a_member_publishes_once_with_everything_the_panel_needs():
    """AC-01."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        out = await _publish(project_id, owner[1])
        assert out["success"] and out["created"] is True
        d = out["decision"]
        assert (d["decision_id"], d["uc_id"], d["question"], d["default_option"], d["created_by"]) == (
            DQ, "UC-10001", PREGUNTA, "ep-17", owner[0],
        )
        assert d["options"] == OPCIONES and d["resolved_at"] is None

        otra_vez = await _publish(project_id, owner[1], question="Otra redacción")
        assert otra_vez["created"] is False and otra_vez["decision"]["question"] == PREGUNTA
        assert await pool.fetchval("SELECT count(*) FROM autopilot_decisions WHERE project_id = $1", project_id) == 1

        sin_id = await _publish(project_id, owner[1], decision_id="")
        assert sin_id["decision"]["decision_id"].startswith("dq-")
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_pending_list_respects_membership():
    """AC-03: lo ajeno responde igual que lo inexistente."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        await _publish(project_id, owner[1])
        lista = await list_pending_decisions(None, project_id=project_id, dev_token=owner[1])
        assert lista["total"] == 1 and lista["decisions"][0]["decision_id"] == DQ

        ajena = await list_pending_decisions(None, project_id=project_id, dev_token=stranger[1])
        inexistente = await list_pending_decisions(None, project_id="Acme/no-existe", dev_token=stranger[1])
        assert ajena["code"] == inexistente["code"] == "PROJECT_NOT_VISIBLE"
        assert "decisions" not in ajena

        assert (await _publish(project_id, stranger[1]))["code"] == "PROJECT_NOT_VISIBLE"
        assert (await list_pending_decisions(None, project_id=project_id))["code"] == "UNAUTHENTICATED"
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_resolving_records_who_when_and_what_and_does_not_change_afterwards():
    """AC-02."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        await _publish(project_id, owner[1])
        mala = await resolve_decision(None, DQ, "otra", project_id=project_id, dev_token=owner[1])
        assert mala["code"] == "INVALID_DECISION"

        out = await resolve_decision(None, DQ, "nueva", via="app", project_id=project_id, dev_token=owner[1])
        d = out["decision"]
        assert out["already_resolved"] is False
        assert (d["resolution"], d["resolved_by"], d["resolved_via"]) == ("nueva", owner[0], "app")
        assert d["resolved_at"] is not None

        segunda = await resolve_decision(None, DQ, "ep-17", via="panel", project_id=project_id, dev_token=owner[1])
        assert segunda["already_resolved"] is True and segunda["decision"]["resolution"] == "nueva"
        assert (await list_pending_decisions(None, project_id=project_id, dev_token=owner[1]))["total"] == 0

        assert (await resolve_decision(None, DQ, "nueva", project_id=project_id, dev_token=stranger[1]))["code"] == (
            "PROJECT_NOT_VISIBLE"
        )
        no_hay = await resolve_decision(
            None, "dq-20261024T000000-ffff-otra", "nueva", project_id=project_id, dev_token=owner[1]
        )
        assert no_hay["code"] == "DECISION_NOT_FOUND"
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_the_next_session_takes_each_resolution_once():
    """AC-02: se entrega una vez, con la opción en llano y quién la eligió."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        await _publish(project_id, owner[1])
        assert (await take_resolved_decisions(None, project_id=project_id, dev_token=owner[1]))["total"] == 0
        await resolve_decision(None, DQ, "nueva", via="panel", project_id=project_id, dev_token=owner[1])

        primera = await take_resolved_decisions(None, project_id=project_id, dev_token=owner[1])
        assert primera["total"] == 1
        d = primera["decisions"][0]
        assert (d["decision_id"], d["resolution"], d["resolution_label"], d["resolved_by_name"], d["resolved_via"]) == (
            DQ, "nueva", "Una épica nueva", "Ana Owner", "panel",
        )
        assert d["applied_at"] is not None
        assert (await take_resolved_decisions(None, project_id=project_id, dev_token=owner[1]))["total"] == 0
        assert (await take_resolved_decisions(None, project_id=project_id, dev_token=stranger[1]))["code"] == (
            "PROJECT_NOT_VISIBLE"
        )
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pytestmark_pg
async def test_a_revoked_token_cannot_publish():
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        await pool.execute("UPDATE mcp_tokens SET revoked_at = now() WHERE developer_id = $1", owner[0])
        assert (await _publish(project_id, owner[1]))["code"] == "UNAUTHENTICATED"
        assert await pool.fetchval("SELECT count(*) FROM autopilot_decisions WHERE project_id = $1", project_id) == 0
    finally:
        await _cleanup(pool, project_id, owner, stranger)
