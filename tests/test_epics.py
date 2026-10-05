"""US-78 / UC-7801 — el board guarda las épicas y la épica de cada historia (D20).

- **AC-01**: una épica guarda nombre, objetivo, enlace, orden y fecha objetivo con un EP-NN; un
  identificador repetido en el proyecto se rechaza y dos proyectos tienen cada uno su EP-01.
- **AC-02**: una historia está como mucho en una épica; moverla la saca de la anterior y borrar la
  épica la deja sin épica sin borrar historias, casos de uso ni criterios.
- **AC-03**: el estado de la épica sale de sus historias con la regla de UC-4305 y su avance es la
  suma de criterios hechos sobre la suma de criterios.
- **AC-04**: en FreeForm las épicas viajan en el contenido del board y sobreviven a leerlo y
  volver a escribirlo.
- **AC-05** (permisos de los roles públicos): ``tests/test_db_surface_tables.py`` incluye ``epics``
  en las tablas del board.

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo.
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.epics import NO_EPIC, summarize_board, summarize_epic
from server.spec_backend import (
    EPIC_EXISTS,
    EPIC_INVALID,
    EPIC_NOT_FOUND,
    EPICS_NOT_SUPPORTED,
    EpicDTO,
    EpicError,
    ItemDTO,
    SpecBackend,
    next_epic_id,
    validate_epic_fields,
)
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


# ── Puras ────────────────────────────────────────────────────────────


def test_next_epic_id_follows_the_highest_in_use():
    assert next_epic_id([]) == "EP-01"
    assert next_epic_id(["EP-01", "EP-07", "EP-03"]) == "EP-08"
    assert next_epic_id(["EP-99"]) == "EP-100"
    assert next_epic_id(["no-es-una-epica"]) == "EP-01"


@pytest.mark.parametrize(
    "kwargs",
    [{"epic_id": "E-1"}, {"epic_id": "EP-"}, {"name": "   "}, {"target_date": "05/10/2026"}],
)
def test_malformed_epic_fields_are_refused(kwargs):
    with pytest.raises(EpicError) as exc:
        validate_epic_fields(**kwargs)
    assert exc.value.code == EPIC_INVALID


def test_target_date_can_be_cleared_or_set():
    validate_epic_fields(target_date="")
    validate_epic_fields(epic_id="EP-12", name="Tinta", target_date="2026-10-31")


async def test_backends_without_epics_list_none_and_refuse_to_write():
    # Trello y Plane heredan el comportamiento por defecto (D20: solo si alguien lo pide).
    assert await SpecBackend.list_epics(object(), "board") == []
    with pytest.raises(EpicError) as exc:
        await SpecBackend.create_epic(object(), "board", name="Épica")
    assert exc.value.code == EPICS_NOT_SUPPORTED


def _story(us_id: str, state: str, epic: str | None) -> ItemDTO:
    meta = {"us_id": us_id, "tipo": "US"}
    if epic:
        meta["epic_id"] = epic
    return ItemDTO(id=us_id, name=f"{us_id}: Historia", state=state, labels=["US"], meta=meta)


def _uc(uc_id: str, us_id: str, state: str, satellite: str) -> ItemDTO:
    return ItemDTO(
        id=uc_id,
        name=f"{uc_id}: Caso",
        state=state,
        parent_id=us_id,
        labels=["UC"],
        meta={"uc_id": uc_id, "us_id": us_id, "satellite": satellite},
    )


def _ac(uc_id: str, n: int, done: bool) -> ItemDTO:
    return ItemDTO(
        id=f"{uc_id}::AC-0{n}",
        name=f"[AC-0{n}] Criterio",
        state="done" if done else "backlog",
        parent_id=uc_id,
        labels=["AC"],
    )


def test_ac03_epic_state_and_progress_come_from_its_stories():
    epic = EpicDTO(id="EP-01", name="Tinta", objective="Un solo sistema", position=1)
    items = [
        _story("US-01", "done", "EP-01"),
        _uc("UC-0101", "US-01", "done", "manager"),
        _ac("UC-0101", 1, True),
        _ac("UC-0101", 2, True),
        _story("US-02", "in_progress", "EP-01"),
        _uc("UC-0201", "US-02", "in_progress", "cloud"),
        _ac("UC-0201", 1, True),
        _ac("UC-0201", 2, False),
        _uc("UC-0202", "US-02", "archived", "cloud"),  # archivada: no cuenta
        _ac("UC-0202", 1, False),
        _story("US-03", "done", None),
        _uc("UC-0301", "US-03", "done", "engine"),
        _ac("UC-0301", 1, True),
    ]
    summary = summarize_epic(epic, items)
    assert summary["state"] == "in_progress"
    assert (summary["ac_done"], summary["ac_total"], summary["pct"]) == (3, 4, 75)
    assert (summary["uc_done"], summary["uc_total"]) == (1, 2)
    assert summary["us_ids"] == ["US-01", "US-02"]
    assert summary["satellites"] == ["manager", "cloud"]

    # Cuando la última historia pasa a hecha, la épica pasa a hecha sin que nadie la mueva.
    items[4] = _story("US-02", "done", "EP-01")
    assert summarize_epic(epic, items)["state"] == "done"


def test_ac03_an_epic_without_stories_is_backlog_without_a_fake_zero():
    summary = summarize_epic(EpicDTO(id="EP-02", name="Vacía"), [])
    assert (summary["state"], summary["ac_total"], summary["pct"]) == ("backlog", 0, None)


def test_board_groups_add_up_to_the_whole_board():
    epics = [EpicDTO(id="EP-01", name="Uno", position=1)]
    items = [
        _story("US-01", "done", "EP-01"),
        _uc("UC-0101", "US-01", "done", "engine"),
        _ac("UC-0101", 1, True),
        _story("US-02", "backlog", None),
        _story("US-03", "backlog", "EP-09"),  # apunta a una épica que ya no existe
        _uc("UC-0301", "US-03", "backlog", "cloud"),
        _ac("UC-0301", 1, False),
    ]
    groups = summarize_board(epics, items)
    assert [g["epic_id"] for g in groups] == ["EP-01", NO_EPIC]
    assert sum(g["us_total"] for g in groups) == 3
    assert sum(g["ac_total"] for g in groups) == 2


# ── FreeForm (contenido del board) ───────────────────────────────────


def _freeform_board() -> FreeformBackend:
    items = [
        {
            "id": "item-us1",
            "name": "US-01: Historia uno",
            "state": "backlog",
            "parent_id": None,
            "labels": ["US"],
            "priority": "none",
            "meta": {"us_id": "US-01", "tipo": "US"},
        },
        {
            "id": "item-uc1",
            "name": "UC-001: Caso",
            "state": "backlog",
            "parent_id": "item-us1",
            "labels": ["UC"],
            "priority": "none",
            "meta": {"uc_id": "UC-001", "us_id": "US-01", "tipo": "UC"},
        },
        {
            "id": "item-ac1",
            "name": "[AC-01] Criterio",
            "state": "backlog",
            "parent_id": "item-uc1",
            "labels": ["AC"],
            "priority": "none",
            "meta": {"ac_id": "AC-01"},
        },
        {
            "id": "item-us2",
            "name": "US-02: Historia dos",
            "state": "backlog",
            "parent_id": None,
            "labels": ["US"],
            "priority": "none",
            "meta": {"us_id": "US-02", "tipo": "US"},
        },
    ]
    return FreeformBackend(items_content=json.dumps(items))


async def test_ac01_freeform_epic_keeps_its_fields_and_refuses_a_repeated_id():
    board = _freeform_board()
    created = await board.create_epic(
        "ff", name="Tinta", objective="Un solo sistema", link="doc/prd/x.md", position=3, target_date="2026-10-31"
    )
    assert created.id == "EP-01"
    [listed] = await board.list_epics("ff")
    assert (listed.name, listed.objective, listed.link, listed.position, listed.target_date) == (
        "Tinta",
        "Un solo sistema",
        "doc/prd/x.md",
        3,
        "2026-10-31",
    )
    assert (await board.create_epic("ff", name="Otra")).id == "EP-02"
    with pytest.raises(EpicError) as exc:
        await board.create_epic("ff", name="Repetida", epic_id="EP-01")
    assert exc.value.code == EPIC_EXISTS


async def test_ac02_freeform_story_in_one_epic_and_deleting_the_epic_keeps_the_story():
    board = _freeform_board()
    await board.create_epic("ff", name="Uno")
    await board.create_epic("ff", name="Dos")
    await board.set_us_epic("ff", "item-us1", "EP-01")
    moved = await board.set_us_epic("ff", "item-us1", "EP-02")
    assert moved.meta["epic_id"] == "EP-02"
    before = len(await board.list_items("ff"))
    result = await board.delete_epic("ff", "EP-02")
    assert result["detached_us"] == ["US-01"]
    story = await board.get_item("ff", "item-us1")
    assert "epic_id" not in story.meta
    assert len(await board.list_items("ff")) == before - 1  # solo se fue la épica
    with pytest.raises(EpicError) as exc:
        await board.set_us_epic("ff", "item-us1", "EP-02")
    assert exc.value.code == EPIC_NOT_FOUND


async def test_ac04_freeform_epics_survive_reading_and_writing_the_content_back():
    board = _freeform_board()
    await board.create_epic("ff", name="Tinta", objective="Un solo sistema", target_date="2026-10-31")
    await board.set_us_epic("ff", "item-us2", "EP-01")
    content = board.get_items_content()

    again = FreeformBackend(items_content=content)
    assert await again.list_epics("ff") == await board.list_epics("ff")
    assert (await again.get_item("ff", "item-us2")).meta["epic_id"] == "EP-01"
    assert again.get_items_content() == content


# ── Native (Postgres) ────────────────────────────────────────────────


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _seed(pool):
    """Proyecto con dos historias (una hecha, otra en curso), sus casos de uso y criterios."""
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    project_id = f"Acme/epics-{uuid.uuid4().hex[:8]}"
    developer_id = f"ep-dev-{uuid.uuid4().hex[:8]}"
    token = f"ep-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Ana Owner")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Epics')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        for us_id, state in (("US-01", "done"), ("US-02", "in_progress")):
            await conn.execute(
                "INSERT INTO user_stories (id, project_id, name, state, labels, meta) "
                "VALUES ($1, $2, $3, $4, '[\"US\"]'::jsonb, jsonb_build_object('us_id', $1::text))",
                us_id,
                project_id,
                f"{us_id}: Historia",
                state,
            )
            uc_id = f"UC-{us_id[3:]}01"
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name, state, labels, meta) "
                "VALUES ($1, $2, $3, $4, $5, '[\"UC\"]'::jsonb, jsonb_build_object('uc_id', $1::text, 'satellite', 'engine'))",
                uc_id,
                project_id,
                us_id,
                f"{uc_id}: Caso",
                state,
            )
            for n, done in ((1, True), (2, state == "done")):
                await conn.execute(
                    "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done) "
                    "VALUES ($1, $2, $3, $4, 'Criterio', $5)",
                    f"{uc_id}::AC-0{n}",
                    project_id,
                    uc_id,
                    f"AC-0{n}",
                    done,
                )
    return project_id, developer_id, token


async def _counts(pool, project_id):
    return tuple(
        [
            await pool.fetchval(f"SELECT count(*) FROM {t} WHERE project_id = $1", project_id)
            for t in ("user_stories", "use_cases", "acceptance_criteria")
        ]
    )


@pytestmark_pg
async def test_ac01_native_epic_keeps_its_fields_and_ids_are_per_project():
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_a, _, token_a = await _seed(pool)
    project_b, _, token_b = await _seed(pool)
    a = NativeBackend(project_a, token_a)
    created = await a.create_epic(
        project_a, name="Tinta", objective="Un solo sistema", link="doc/prd/x.md", position=4, target_date="2026-10-31"
    )
    assert created.id == "EP-01"
    [listed] = await a.list_epics(project_a)
    assert (listed.id, listed.name, listed.objective, listed.link, listed.position, listed.target_date) == (
        "EP-01",
        "Tinta",
        "Un solo sistema",
        "doc/prd/x.md",
        4,
        "2026-10-31",
    )
    with pytest.raises(EpicError) as exc:
        await a.create_epic(project_a, name="Repetida", epic_id="EP-01")
    assert exc.value.code == EPIC_EXISTS
    # El otro proyecto tiene su propio EP-01.
    assert (await NativeBackend(project_b, token_b).create_epic(project_b, name="Otra")).id == "EP-01"

    updated = await a.update_epic(project_a, "EP-01", name="Tinta 2", target_date="")
    assert (updated.name, updated.target_date) == ("Tinta 2", None)


@pytestmark_pg
async def test_ac02_native_story_moves_between_epics_and_deleting_keeps_everything_else():
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    board = NativeBackend(project_id, token)
    await board.create_epic(project_id, name="Uno")
    await board.create_epic(project_id, name="Dos")
    await board.set_us_epic(project_id, "US-01", "EP-01")
    moved = await board.set_us_epic(project_id, "US-01", "EP-02")
    assert moved.meta["epic_id"] == "EP-02"
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM user_stories WHERE project_id = $1 AND epic_id IS NOT NULL", project_id
        )
        == 1
    )

    before = await _counts(pool, project_id)
    result = await board.delete_epic(project_id, "EP-02")
    assert result["detached_us"] == ["US-01"]
    assert (
        await pool.fetchval("SELECT epic_id FROM user_stories WHERE project_id = $1 AND id = 'US-01'", project_id)
        is None
    )
    assert await _counts(pool, project_id) == before

    ops = [
        (r["operation"], r["target_id"], r["developer_id"])
        for r in await pool.fetch(
            "SELECT operation, target_id, developer_id FROM audit_log WHERE project_id = $1 ORDER BY id", project_id
        )
    ]
    assert ops == [
        ("create_epic", "EP-01", developer_id),
        ("create_epic", "EP-02", developer_id),
        ("set_us_epic", "US-01", developer_id),
        ("set_us_epic", "US-01", developer_id),
        ("delete_epic", "EP-02", developer_id),
    ]
    with pytest.raises(EpicError) as exc:
        await board.set_us_epic(project_id, "US-01", "EP-02")
    assert exc.value.code == EPIC_NOT_FOUND


@pytestmark_pg
async def test_ac03_native_epic_state_follows_its_stories():
    from server.backends.native_backend import NativeBackend

    pool = await _pool()
    project_id, _, token = await _seed(pool)
    board = NativeBackend(project_id, token)
    epic = await board.create_epic(project_id, name="Épica")
    await board.set_us_epic(project_id, "US-01", epic.id)
    await board.set_us_epic(project_id, "US-02", epic.id)

    summary = summarize_epic(epic, await board.list_items(project_id))
    assert summary["state"] == "in_progress"
    assert (summary["ac_done"], summary["ac_total"]) == (3, 4)

    await pool.execute("UPDATE user_stories SET state = 'done' WHERE project_id = $1 AND id = 'US-02'", project_id)
    assert summarize_epic(epic, await board.list_items(project_id))["state"] == "done"


@pytestmark_pg
async def test_ac01_a_member_of_another_project_cannot_write_its_epics():
    from server.backends.native_backend import NativeBackend
    from server.coordination.identity import ForbiddenError

    pool = await _pool()
    project_a, _, _ = await _seed(pool)
    project_b, _, token_b = await _seed(pool)
    with pytest.raises(ForbiddenError):
        await NativeBackend(project_b, token_b).create_epic(project_a, name="Intrusa")
    assert await pool.fetchval("SELECT count(*) FROM epics WHERE project_id = $1", project_a) == 0
