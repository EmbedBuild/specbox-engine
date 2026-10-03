"""US-70 / UC-7001 y UC-7002 — el escaparate público de la home y la foto de actividad.

La migración ``supabase/migrations/20261004000029_site_showcase.sql`` solo existe en
Supabase (objetos del site, no del board). Aquí se aplica sobre la cadena local, dentro
de una transacción que se deshace al terminar: la base de pruebas sigue sin vistas
públicas, como exige UC-4001.

Antes de aplicarla, la transacción da a anon y authenticated lo que Supabase les da por
defecto sobre todo objeto nuevo de public (todos los privilegios), así que cada aserción
de permisos prueba que la migración los cierra.

UC-7001:
- AC-01: solo salen las UC y US fijadas del board EmbedBuild/specbox-manager; una UC sin
  fijar no sale, y fijar algo de otro proyecto es imposible.
- AC-02: el detalle de un recibo no sale nunca, y su enlace solo si apunta a specbox.build
  o al repositorio público del engine.
- AC-03: quien acepta sale con su nombre público si está en site_showcase_signer; si no,
  sin nombre.
- AC-04: anon y authenticated solo leen la vista y no tienen nada sobre las tablas.

UC-7002:
- AC-01: site_activity publica todos los estados y el total coincide con la suma.
- AC-02: anon y authenticated solo tienen SELECT sobre site_activity y site_stats.
"""

from __future__ import annotations

import json
from pathlib import Path

import asyncpg
import pytest

from server.db.migrate import apply_migrations
from server.db.pool import close_pool, get_pool, init_pool
from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

MIGRATION = Path(__file__).resolve().parent.parent / "supabase" / "migrations" / "20261004000029_site_showcase.sql"
BOARD = "EmbedBuild/specbox-manager"
OTHER = "Acme/site-showcase-test"
OWNER = "jesusperezdeveloper"
STRANGER = "showcase-stranger"
PUBLIC_ROLES = ("anon", "authenticated")
VIEWS = ("site_showcase", "site_activity", "site_stats")
TABLES = ("site_showcase_pin", "site_showcase_signer")


def _evidence(link: str, *, by: str, detail: str = "detalle interno: nywjsvumsvxlpflpbord") -> dict:
    return {
        "type": "pr",
        "label": f"recibo {link}",
        "link": link,
        "detail": detail,
        "by": by,
        "at": "2026-10-03T19:04:54+00:00",
        "passed": True,
    }


async def _seed(conn: asyncpg.Connection) -> None:
    for dev, name in ((OWNER, "Jesús Pérez"), (STRANGER, "Persona Sin Firma")):
        await conn.execute(
            "INSERT INTO developers (developer_id, display_name) VALUES ($1, $2) ON CONFLICT (developer_id) DO NOTHING",
            dev,
            name,
        )
    for project in (BOARD, OTHER):
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $1) ON CONFLICT DO NOTHING", project)
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-90', $1, $2, 'in_progress')",
            project,
            "US-90: El escaparate se prueba solo [site]",
        )
        for uc_id, state in (("UC-9001", "done"), ("UC-9002", "in_progress"), ("UC-9003", "archived")):
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name, state) VALUES ($1, $2, 'US-90', $3, $4)",
                uc_id,
                project,
                f"{uc_id}: Caso {uc_id} de {project}",
                state,
            )
    acs = (
        # (ac_id, internal, verdict_by, evidence links)
        ("AC-01", False, OWNER, ["https://github.com/EmbedBuild/specbox-manager/pull/41"]),
        (
            "AC-02",
            False,
            STRANGER,
            [
                "https://specbox.build/activity/",
                "https://projects.specbox.build/login?x=1",
                "https://github.com/EmbedBuild/specbox-engine/pull/206",
            ],
        ),
        (
            "AC-03",
            False,
            OWNER,
            [
                "https://specbox.build.evil.example/x",
                "https://github.com/EmbedBuild/specbox-engine-fake/pull/1",
                "http://specbox.build/",
                "javascript:alert(1)",
            ],
        ),
        ("AC-04", True, OWNER, ["https://specbox.build/"]),
    )
    for ac_id, internal, by, links in acs:
        meta = {
            "verdict": {"at": "2026-10-03T19:04:54+00:00", "by": by, "passed": True},
            "evidence": [_evidence(link, by=by) for link in links],
        }
        for project in (BOARD, OTHER):
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, internal, meta) "
                "VALUES ($1, $2, 'UC-9001', $3, $4, true, $5, $6::jsonb)",
                f"UC-9001::{ac_id}",
                project,
                ac_id,
                f"Texto de {ac_id} en {project}",
                internal,
                json.dumps(meta),
            )
    await conn.execute(
        "INSERT INTO uc_state_transitions (project_id, uc_id, us_id, from_state, to_state, developer_id, source, occurred_at) "
        "VALUES ($1, 'UC-9001', 'US-90', 'backlog', 'in_progress', $2, 'interactive', '2026-10-01T21:35:51Z'), "
        "       ($1, 'UC-9001', 'US-90', 'in_progress', 'done', $3, 'interactive', '2026-10-03T19:05:03Z')",
        BOARD,
        OWNER,
        STRANGER,
    )
    await conn.execute(
        "INSERT INTO site_showcase_pin (kind, item_id, sort_order, business_title) VALUES "
        "('uc', 'UC-9001', 1, NULL), ('us', 'US-90', 1, 'El escaparate, probado')"
    )
    await conn.execute(
        "INSERT INTO site_showcase_signer (developer_id, public_name) VALUES ($1, 'Jesús') "
        "ON CONFLICT (developer_id) DO NOTHING",
        OWNER,
    )


@pytest.fixture
async def conn():
    """Una conexión con la migración aplicada dentro de una transacción que se deshace."""
    await init_pool(dsn=DSN)
    pool = await get_pool()
    try:
        await apply_migrations(pool)
        async with pool.acquire() as connection:
            tr = connection.transaction()
            await tr.start()
            try:
                for role in PUBLIC_ROLES:
                    if not await connection.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role):
                        await connection.execute(f"CREATE ROLE {role} NOLOGIN")
                await connection.execute("GRANT USAGE ON SCHEMA public TO anon, authenticated")
                # Lo que Supabase da por defecto sobre todo objeto nuevo de public.
                await connection.execute(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated"
                )
                await connection.execute(MIGRATION.read_text(encoding="utf-8"))
                await _seed(connection)
                yield connection
            finally:
                await tr.rollback()
    finally:
        await close_pool()


async def _as(conn: asyncpg.Connection, role: str, sql: str) -> list[asyncpg.Record]:
    """Lee como ``role``. El savepoint se deshace siempre: un SET LOCAL ROLE sobrevive a
    un savepoint liberado y dejaría la conexión con el rol público."""
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(f"SET LOCAL ROLE {role}")
        return await conn.fetch(sql)
    finally:
        await tr.rollback()


async def _denied(conn: asyncpg.Connection, role: str, sql: str) -> None:
    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(f"SET LOCAL ROLE {role}")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(sql)
    finally:
        await tr.rollback()


async def _showcase(conn: asyncpg.Connection, kind: str) -> dict[str, asyncpg.Record]:
    rows = await _as(conn, "anon", f"SELECT * FROM site_showcase WHERE kind = '{kind}'")
    return {r["item_id"]: r for r in rows}


def _criteria(row: asyncpg.Record) -> dict[str, dict]:
    return {c["ac_id"]: c for c in json.loads(row["criteria"])}


# ── UC-7001 ─────────────────────────────────────────────────────────


async def test_ac01_only_pinned_items_of_our_board_are_shown(conn):
    ucs = await _showcase(conn, "uc")
    assert "UC-9001" in ucs and "UC-9002" not in ucs and "UC-9003" not in ucs
    row = ucs["UC-9001"]
    assert row["title"] == f"Caso UC-9001 de {BOARD}"
    assert row["us_title"] == "El escaparate se prueba solo"
    assert {c["text"] for c in _criteria(row).values()} <= {f"Texto de AC-0{n} en {BOARD}" for n in range(1, 5)}
    history = json.loads(row["history"])
    assert [(h["from"], h["to"]) for h in history] == [("backlog", "in_progress"), ("in_progress", "done")]

    uss = await _showcase(conn, "us")
    assert uss["US-90"]["title"] == "El escaparate se prueba solo"
    assert uss["US-90"]["business_title"] == "El escaparate, probado"
    # UC-9001 hecha, UC-9002 en curso; la archivada no cuenta.
    assert (uss["US-90"]["done"], uss["US-90"]["total"]) == (1, 2)


async def test_ac01_nothing_of_another_project_can_be_pinned(conn):
    with pytest.raises(asyncpg.CheckViolationError):
        async with conn.transaction():
            await conn.execute(
                "INSERT INTO site_showcase_pin (project_id, kind, item_id) VALUES ($1, 'uc', 'UC-9002')",
                OTHER,
            )


async def test_ac01_internal_criteria_are_never_shown(conn):
    assert "AC-04" not in _criteria((await _showcase(conn, "uc"))["UC-9001"])


async def test_ac02_no_detail_and_only_public_links(conn):
    criteria = _criteria((await _showcase(conn, "uc"))["UC-9001"])
    receipts = [e for c in criteria.values() for e in c["evidence"]]
    assert receipts and all("detail" not in e for e in receipts)
    assert all(set(e) == {"type", "label", "link", "at", "by", "passed"} for e in receipts)
    links = {e["label"].removeprefix("recibo "): e["link"] for e in receipts}
    assert links["https://github.com/EmbedBuild/specbox-manager/pull/41"] is None
    assert links["https://specbox.build/activity/"] == "https://specbox.build/activity/"
    assert links["https://projects.specbox.build/login?x=1"] == "https://projects.specbox.build/login?x=1"
    assert links["https://github.com/EmbedBuild/specbox-engine/pull/206"] == (
        "https://github.com/EmbedBuild/specbox-engine/pull/206"
    )
    for hostile in (
        "https://specbox.build.evil.example/x",
        "https://github.com/EmbedBuild/specbox-engine-fake/pull/1",
        "http://specbox.build/",
        "javascript:alert(1)",
    ):
        assert links[hostile] is None, hostile


async def test_ac03_only_listed_signers_have_a_name(conn):
    row = (await _showcase(conn, "uc"))["UC-9001"]
    criteria = _criteria(row)
    assert criteria["AC-01"]["accepted_by"] == "Jesús"
    assert criteria["AC-02"]["accepted_by"] is None
    assert {e["by"] for e in criteria["AC-01"]["evidence"]} == {"Jesús"}
    assert {e["by"] for e in criteria["AC-02"]["evidence"]} == {None}
    assert [h["by"] for h in json.loads(row["history"])] == ["Jesús", None]
    raw = row["criteria"] + row["history"]
    assert OWNER not in raw and STRANGER not in raw


@pytest.mark.parametrize("role", PUBLIC_ROLES)
async def test_ac04_public_roles_only_read_the_view(conn, role):
    assert await _as(conn, role, "SELECT kind FROM site_showcase")
    for table in TABLES:
        await _denied(conn, role, f"SELECT * FROM {table}")
        await _denied(conn, role, f"DELETE FROM {table}")
    await _denied(conn, role, "INSERT INTO site_showcase_pin (kind, item_id) VALUES ('uc', 'UC-9002')")


async def test_ac04_and_uc7002_ac02_grants_are_select_only(conn):
    rows = await conn.fetch(
        "SELECT table_name, grantee, privilege_type FROM information_schema.role_table_grants "
        "WHERE table_schema = 'public' AND table_name = ANY($1::text[]) AND grantee = ANY($2::text[])",
        list(VIEWS + TABLES),
        list(PUBLIC_ROLES),
    )
    granted = {(r["table_name"], r["grantee"], r["privilege_type"]) for r in rows}
    assert granted == {(v, role, "SELECT") for v in VIEWS for role in PUBLIC_ROLES}


# ── UC-7002 ─────────────────────────────────────────────────────────


async def test_uc7002_ac01_activity_total_matches_the_published_states(conn):
    (row,) = await _as(conn, "anon", "SELECT use_cases_count, uc_by_state FROM site_activity")
    by_state = json.loads(row["uc_by_state"])
    assert {"backlog", "in_progress", "review", "done", "archived"} <= set(by_state)
    assert sum(by_state.values()) == row["use_cases_count"]
    assert by_state["archived"] >= 2  # UC-9003 en los dos proyectos sembrados
