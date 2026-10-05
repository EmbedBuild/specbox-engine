"""US-78 / UC-7802 — las tools crean, editan y consultan épicas.

- **AC-01**: desde el MCP se crea, edita, lista, consulta y borra una épica y se mete o se saca
  una historia; en native cada cambio deja su fila en ``audit_log`` con quién y cuándo.
- **AC-02**: ``get_epic`` devuelve sus historias, estado, avance (hechos/total y %), fecha
  objetivo y satélites.
- **AC-03**: crear o renombrar una historia o un caso de uso con el id ya en el nombre lo deja
  una sola vez.

Más la lista de ``doc/security/threat-model.md`` §8: sin identidad → ``UNAUTHENTICATED`` sin
datos; otro developer → ``FORBIDDEN`` sin escribir. Las de Postgres hacen SKIP sin base.
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.spec_backend import with_item_id
from server.tools import epics as ep
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


def _use(monkeypatch, module, backend):
    async def _fake(_ctx, *, items_content=None):
        return backend

    monkeypatch.setattr(module, "get_session_backend", _fake)


def _freeform() -> FreeformBackend:
    items = [
        {"id": "item-us1", "name": "US-01: Historia", "state": "in_progress", "parent_id": None,
         "labels": ["US"], "priority": "none", "meta": {"us_id": "US-01", "tipo": "US"}},
        {"id": "item-uc1", "name": "UC-001: Caso", "state": "done", "parent_id": "item-us1",
         "labels": ["UC"], "priority": "none",
         "meta": {"uc_id": "UC-001", "us_id": "US-01", "tipo": "UC", "satellite": "engine"}},
        {"id": "item-uc2", "name": "UC-002: Otro", "state": "in_progress", "parent_id": "item-us1",
         "labels": ["UC"], "priority": "none",
         "meta": {"uc_id": "UC-002", "us_id": "US-01", "tipo": "UC", "satellite": "cloud"}},
        {"id": "item-ac1", "name": "[AC-01] Uno", "state": "done", "parent_id": "item-uc1",
         "labels": ["AC"], "priority": "none", "meta": {"ac_id": "AC-01"}},
        {"id": "item-ac2", "name": "[AC-01] Dos", "state": "backlog", "parent_id": "item-uc2",
         "labels": ["AC"], "priority": "none", "meta": {"ac_id": "AC-01"}},
    ]
    return FreeformBackend(items_content=json.dumps(items))


class _KeepOpen(FreeformBackend):
    """FreeForm en memoria que sobrevive al ``close()`` de cada tool."""

    async def close(self) -> None:
        return None


# ── AC-01 y AC-02 (FreeForm) ─────────────────────────────────────────


async def test_ac01_ac02_epic_lifecycle_through_the_tools(monkeypatch):
    board = _KeepOpen(items_content=_freeform().get_items_content())
    _use(monkeypatch, ep, board)

    created = await ep.add_epic("ff", "Tinta", ctx=None, objective="Un solo sistema", target_date="2026-10-31")
    assert created["epic"]["epic_id"] == "EP-01"
    assert (await ep.set_us_epic("ff", "US-01", ctx=None, epic_id="EP-01")) == {
        "us_id": "US-01",
        "epic_id": "EP-01",
        "previous_epic_id": None,
    }

    epic = await ep.get_epic("ff", "EP-01", ctx=None)
    assert epic["state"] == "in_progress"
    assert (epic["ac_done"], epic["ac_total"], epic["pct"]) == (1, 2, 50)
    assert epic["target_date"] == "2026-10-31"
    assert epic["satellites"] == ["engine", "cloud"]
    assert [s["us_id"] for s in epic["stories"]] == ["US-01"]
    assert epic["stories"][0]["uc_total"] == 2

    updated = await ep.update_epic("ff", "EP-01", ctx=None, name="Tinta 2", target_date="")
    assert (updated["epic"]["name"], updated["epic"]["target_date"]) == ("Tinta 2", None)
    assert updated["updated_fields"] == ["name", "target_date"]

    listed = await ep.list_epics("ff", ctx=None)
    assert [e["epic_id"] for e in listed["epics"]] == ["EP-01"] and listed["sin_epica"] is None

    out = await ep.set_us_epic("ff", "US-01", ctx=None, epic_id=None)
    assert out["previous_epic_id"] == "EP-01" and out["epic_id"] is None
    assert (await ep.list_epics("ff", ctx=None))["sin_epica"]["us_ids"] == ["US-01"]

    assert await ep.delete_epic("ff", "EP-01", ctx=None) == {"deleted": "EP-01", "detached_us": []}
    assert (await ep.get_epic("ff", "EP-01", ctx=None))["code"] == "EPIC_NOT_FOUND"


async def test_unknown_story_and_epic_answer_with_a_code(monkeypatch):
    board = _KeepOpen(items_content=_freeform().get_items_content())
    _use(monkeypatch, ep, board)
    assert (await ep.set_us_epic("ff", "US-99", ctx=None, epic_id="EP-01"))["code"] == "US_NOT_FOUND"
    assert (await ep.set_us_epic("ff", "US-01", ctx=None, epic_id="EP-09"))["code"] == "EPIC_NOT_FOUND"
    assert (await ep.add_epic("ff", "  ", ctx=None))["code"] == "EPIC_INVALID"


# ── AC-03 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,expected",
    [
        ("US-78: US-78: Nombre", "US-78: Nombre"),
        ("[US-78] Nombre", "US-78: Nombre"),
        ("Nombre", "US-78: Nombre"),
        ("US-781: Otra", "US-78: US-781: Otra"),
    ],
)
def test_ac03_the_id_goes_in_front_once(name, expected):
    assert with_item_id("US-78", name) == expected


async def test_ac03_import_add_and_rename_keep_the_id_once(monkeypatch):
    from server.tools import spec_driven, spec_mutations

    board = _KeepOpen(items_content="[]")
    _use(monkeypatch, spec_driven, board)
    _use(monkeypatch, spec_mutations, board)

    spec = {
        "user_stories": [
            {
                "us_id": "US-90",
                "name": "US-90: Historia",
                "use_cases": [
                    {"uc_id": "UC-9001", "name": "UC-9001: Caso", "actor": "x", "acceptance_criteria": ["Se ve algo."]}
                ],
            }
        ]
    }
    await spec_driven.import_spec("ff", spec, ctx=None)
    await spec_mutations.add_uc("ff", "US-90", "UC-9002: Otro caso", "desc", ["Se ve otra cosa."], ctx=None)
    await spec_mutations.update_us("ff", "US-90", ctx=None, name="US-90: US-90: Renombrada")
    await spec_mutations.update_uc("ff", "UC-9001", ctx=None, name="UC-9001: UC-9001: Renombrado")

    names = sorted(i.name for i in await board.list_items("ff") if {"US", "UC"} & set(i.labels))
    assert names == ["UC-9001: Renombrado", "UC-9002: Otro caso", "US-90: Renombrada"]


# ── Native: auditoría, sin identidad, otro developer ─────────────────


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _tenant(pool):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    project_id = f"Acme/epic-tools-{uuid.uuid4().hex[:8]}"
    developer_id = f"et-dev-{uuid.uuid4().hex[:8]}"
    token = f"et-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Dev")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'x')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, labels, meta) "
            "VALUES ('US-01', $1, 'US-01: Historia', '[\"US\"]'::jsonb, '{\"us_id\": \"US-01\"}'::jsonb)",
            project_id,
        )
    return project_id, developer_id, token


@pytestmark_pg
async def test_ac01_native_every_change_is_audited_with_who_and_when(monkeypatch):
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_id, developer_id, token = await _tenant(pool)
    _use(monkeypatch, ep, NativeBackend(project_id, token))

    await ep.add_epic(project_id, "Una", ctx=None)
    await ep.update_epic(project_id, "EP-01", ctx=None, objective="Objetivo")
    await ep.set_us_epic(project_id, "US-01", ctx=None, epic_id="EP-01")
    await ep.set_us_epic(project_id, "US-01", ctx=None, epic_id=None)
    await ep.delete_epic(project_id, "EP-01", ctx=None)

    rows = await pool.fetch(
        "SELECT operation, target_id, developer_id, occurred_at FROM audit_log WHERE project_id = $1 ORDER BY id",
        project_id,
    )
    assert [(r["operation"], r["target_id"]) for r in rows] == [
        ("create_epic", "EP-01"),
        ("update_epic", "EP-01"),
        ("set_us_epic", "US-01"),
        ("set_us_epic", "US-01"),
        ("delete_epic", "EP-01"),
    ]
    assert {r["developer_id"] for r in rows} == {developer_id}
    assert all(r["occurred_at"] is not None for r in rows)


@pytestmark_pg
async def test_without_identity_the_tools_answer_unauthenticated_and_no_data(monkeypatch):
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_id, _, _ = await _tenant(pool)
    _use(monkeypatch, ep, NativeBackend(project_id, "token-que-no-existe"))

    assert (await ep.list_epics(project_id, ctx=None)) == {
        "error": "No valid developer token presented.",
        "code": "UNAUTHENTICATED",
    }
    assert (await ep.add_epic(project_id, "Nada", ctx=None))["code"] == "UNAUTHENTICATED"
    assert await pool.fetchval("SELECT count(*) FROM epics WHERE project_id = $1", project_id) == 0


@pytestmark_pg
async def test_another_developer_neither_sees_nor_writes(monkeypatch):
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    victim, _, victim_token = await _tenant(pool)
    other, _, other_token = await _tenant(pool)
    await NativeBackend(victim, victim_token).create_epic(victim, name="Privada")

    _use(monkeypatch, ep, NativeBackend(other, other_token))
    assert (await ep.list_epics(victim, ctx=None))["code"] == "FORBIDDEN"
    assert (await ep.get_epic(victim, "EP-01", ctx=None))["code"] == "FORBIDDEN"
    assert (await ep.add_epic(victim, "Intrusa", ctx=None))["code"] == "FORBIDDEN"
    assert (await ep.set_us_epic(victim, "US-01", ctx=None, epic_id="EP-01"))["code"] == "FORBIDDEN"
    assert await pool.fetchval("SELECT count(*) FROM epics WHERE project_id = $1", victim) == 1
