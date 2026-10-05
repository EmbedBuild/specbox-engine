"""US-78 / UC-7805 — /prd declara las épicas y la siembra las crea.

- **AC-01**: un spec declara épicas y la épica de cada historia; ``import_spec`` crea las que no
  existen, reutiliza las que sí (por id o por nombre) y asigna cada historia.
- **AC-03**: los títulos sembrados no llevan el satélite entre corchetes; el satélite va en cada
  caso de uso (``satellite`` del spec, validado como en ``set_uc_satellite``).
- Re-sembrar una historia no le cambia el estado (antes volvía a ``user_stories``).

AC-02 (la pregunta de /prd) vive en ``.claude/skills/prd/SKILL.md``.
"""

from __future__ import annotations

import uuid

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.spec_backend import SpecBackend
from server.tools import spec_driven as sd
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


class _KeepOpen(FreeformBackend):
    async def close(self) -> None:
        return None


def _use(monkeypatch, backend):
    async def _fake(_ctx, *, items_content=None):
        return backend

    monkeypatch.setattr(sd, "get_session_backend", _fake)


SPEC = {
    "epics": [
        {"name": "Seguridad", "objective": "Nadie lee lo que no es suyo", "link": "doc/prd/x.md"},
        {"epic_id": "EP-07", "name": "Tinta", "objective": "Un solo sistema", "target_date": "2026-10-31"},
    ],
    "user_stories": [
        {
            "us_id": "US-10",
            "name": "Leer exige ser miembro [engine]",
            "epic": "seguridad",  # por nombre, sin importar mayúsculas
            "use_cases": [
                {"uc_id": "UC-1001", "name": "Lecturas", "actor": "sistema", "satellite": "engine",
                 "acceptance_criteria": ["Se deniega."]},
            ],
        },
        {
            "us_id": "US-11",
            "name": "El panel pinta Tinta [cloud][manager]",
            "epic": "EP-07",
            "use_cases": [
                {"uc_id": "UC-1101", "name": "Panel", "actor": "x", "satellite": "cloud",
                 "acceptance_criteria": ["Se ve."]},
                {"uc_id": "UC-1102", "name": "Registro", "actor": "x", "satellite": "manager",
                 "acceptance_criteria": ["Existe."]},
            ],
        },
        {"us_id": "US-12", "name": "Sin épica", "use_cases": []},
    ],
}


async def _stories(board):
    return {i.meta.get("us_id"): i for i in await board.list_items("b") if "US" in i.labels}


async def test_ac01_import_creates_reuses_and_assigns_epics(monkeypatch):
    board = _KeepOpen(items_content="[]")
    await board.create_epic("b", name="Seguridad")  # ya existe: se reutiliza por nombre
    _use(monkeypatch, board)

    result = await sd.import_spec("b", SPEC, ctx=None)
    assert result["errors"] == []
    assert result["epics"]["reused"] == ["EP-01"] and result["epics"]["created"] == ["EP-07"]
    assert result["epics"]["assigned"] == {"US-10": "EP-01", "US-11": "EP-07"}

    epics = {e.id: e for e in await board.list_epics("b")}
    assert (epics["EP-07"].name, epics["EP-07"].target_date) == ("Tinta", "2026-10-31")
    stories = await _stories(board)
    assert stories["US-10"].meta["epic_id"] == "EP-01"
    assert stories["US-11"].meta["epic_id"] == "EP-07"
    assert "epic_id" not in stories["US-12"].meta

    # Re-sembrar no duplica épicas ni mueve la historia de estado.
    await board.update_item("b", stories["US-10"].id, state="in_progress")
    again = await sd.import_spec("b", SPEC, ctx=None)
    assert again["epics"]["created"] == [] and sorted(again["epics"]["reused"]) == ["EP-01", "EP-07"]
    assert len(await board.list_epics("b")) == 2
    assert (await _stories(board))["US-10"].state == "in_progress"


async def test_ac03_titles_without_satellite_tags_and_satellite_on_each_uc(monkeypatch):
    board = _KeepOpen(items_content="[]")
    _use(monkeypatch, board)
    await sd.import_spec("b", SPEC, ctx=None)

    stories = await _stories(board)
    assert stories["US-10"].name == "US-10: Leer exige ser miembro"
    assert stories["US-11"].name == "US-11: El panel pinta Tinta"
    sats = {i.meta["uc_id"]: i.meta.get("satellite") for i in await board.list_items("b") if "UC" in i.labels}
    assert sats == {"UC-1001": "engine", "UC-1101": "cloud", "UC-1102": "manager"}


async def test_unknown_epic_is_reported_and_the_story_is_still_seeded(monkeypatch):
    board = _KeepOpen(items_content="[]")
    _use(monkeypatch, board)
    spec = {"user_stories": [{"us_id": "US-20", "name": "Huérfana", "epic": "EP-99", "use_cases": []}]}
    result = await sd.import_spec("b", spec, ctx=None)
    assert result["created"]["us"] == 1
    assert result["errors"] == ["US US-20: epic 'EP-99' is neither declared nor on the board"]


class _NoEpics(_KeepOpen):
    """Como Trello/Plane: hereda el comportamiento por defecto de SpecBackend."""

    list_epics = SpecBackend.list_epics
    create_epic = SpecBackend.create_epic
    set_us_epic = SpecBackend.set_us_epic


async def test_a_backend_without_epics_seeds_the_rest_and_says_why(monkeypatch):
    board = _NoEpics(items_content="[]")
    _use(monkeypatch, board)
    result = await sd.import_spec("b", SPEC, ctx=None)
    assert result["created"]["us"] == 3 and result["errors"] == []
    assert "has no epics" in result["epics"]["skipped"]


@pytestmark_pg
async def test_ac01_native_seed_creates_epics_with_audit(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    project_id = f"Acme/seed-epics-{uuid.uuid4().hex[:8]}"
    developer_id = f"se-dev-{uuid.uuid4().hex[:8]}"
    token = f"se-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Dev")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'x')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")

    _use(monkeypatch, NativeBackend(project_id, token))
    result = await sd.import_spec(project_id, SPEC, ctx=None)
    assert result["errors"] == [] and result["epics"]["created"] == ["EP-01", "EP-07"]

    rows = await pool.fetch(
        "SELECT id, epic_id, name FROM user_stories WHERE project_id = $1 ORDER BY id", project_id
    )
    assert [(r["id"], r["epic_id"]) for r in rows] == [("US-10", "EP-01"), ("US-11", "EP-07"), ("US-12", None)]
    assert rows[0]["name"] == "US-10: Leer exige ser miembro"
    ops = [
        r["operation"]
        for r in await pool.fetch("SELECT operation FROM audit_log WHERE project_id = $1 ORDER BY id", project_id)
    ]
    assert ops.count("create_epic") == 2 and ops.count("set_us_epic") == 2
