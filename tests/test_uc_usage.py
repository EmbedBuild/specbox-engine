"""US-124 / UC-12403 — cada UC registra su coste en tokens y su tiempo de revisión.

- **AC-01**: ``report_uc_usage`` suma a la UC los tokens que informa Claude Code, por sesión y
  subagente (el hook ``uc-usage``, en tests/hooks/uc-usage.test.mjs, los saca de la transcripción).
- **AC-02**: el tiempo de revisión va de la entrada en revisión a la aceptación o la devolución de
  una persona (o la vuelta a trabajo); ``get_project_kpis`` da su p50 y su p90.
- **AC-03**: ``get_project_kpis`` da los tokens por UC y por criterio, con «estimado» donde no hay dato.
- **AC-04**: solo cifras: la tool rechaza lo que no sea un entero o un identificador y la tabla no
  tiene columnas de texto libre.

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from server.tools.uc_usage import (
    RECENT_UCS,
    TOKEN_FIELDS,
    percentile,
    report_uc_usage,
    review_time_kpis,
    summarize_usage,
    usage_kpis,
    validate_usage,
)
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

SESSION = "3f2c9a1e-7b44-4d2a-9c11-0a5b6e7d8f90"
ZERO = dict.fromkeys(TOKEN_FIELDS, 0)


# ── Puras ─────────────────────────────────────────────────────────────


def _valid(**over):
    base = {"project_id": "Acme/x", "uc_id": "UC-1", "session_id": SESSION, "agent_id": "", "counts": dict(ZERO),
            "messages": 1}
    base.update(over)
    return validate_usage(**base)


def test_ac04_only_numbers_and_short_ids_are_accepted():
    assert _valid() is None
    assert _valid(agent_id="af76a0cc43cd28323") is None
    for bad in ("diez", 1.5, -1, True, None, 10**11):
        assert _valid(counts={**ZERO, "output_tokens": bad})["code"] == "INVALID_USAGE"
    assert _valid(messages="3")["code"] == "INVALID_USAGE"
    assert _valid(agent_id="un texto con espacios")["code"] == "INVALID_USAGE"
    assert _valid(uc_id="UC-1: con texto")["code"] == "INVALID_USAGE"
    assert _valid(session_id="corta")["code"] == "INVALID_USAGE"


def test_percentile_matches_percentile_cont():
    assert percentile([], 0.5) is None
    assert percentile([5.0], 0.9) == 5.0
    assert percentile([1, 2, 3, 4], 0.5) == 2.5
    assert percentile([0, 10], 0.9) == 9.0


def test_ac03_tokens_per_uc_and_per_criterion_with_the_estimated_mark():
    rows = [
        {"uc_id": "UC-3", "state": "review", "criteria": 4, "input_total": None, "output_total": None},
        {"uc_id": "UC-2", "state": "done", "criteria": 2, "input_total": 900, "output_total": 100},
        {"uc_id": "UC-1", "state": "done", "criteria": 4, "input_total": 3000, "output_total": 1000},
        {"uc_id": "UC-0", "state": "done", "criteria": 0, "input_total": None, "output_total": None},
    ]
    out = summarize_usage(rows)
    assert out["ucs_with_usage"] == 2 and out["ucs_without_usage"] == 2 and out["estimated"] is True
    assert out["per_uc_p50"] == 2500 and out["per_uc_p90"] == 3700
    assert out["per_criterion_p50"] == 750  # 500 y 1000 por criterio
    by = {u["uc_id"]: u for u in out["by_uc"]}
    assert by["UC-2"] == {"uc_id": "UC-2", "state": "done", "criteria": 2, "estimated": False, "tokens": 1000,
                          "input_tokens": 900, "output_tokens": 100, "tokens_per_criterion": 500}
    assert by["UC-3"]["estimated"] is True and by["UC-3"]["tokens"] == 3000  # 750 × 4
    assert by["UC-0"]["estimated"] is True and by["UC-0"]["tokens"] is None  # sin criterios, sin estimación

    nothing = summarize_usage([{"uc_id": "UC-9", "state": "done", "criteria": 3, "input_total": None,
                                "output_total": None}])
    assert nothing["estimated"] is True and nothing["per_uc_p50"] is None
    assert nothing["by_uc"][0]["tokens"] is None
    assert summarize_usage([])["estimated"] is False
    many = [{"uc_id": f"UC-{i}", "state": "done", "criteria": 1, "input_total": 1, "output_total": 1}
            for i in range(RECENT_UCS + 5)]
    assert len(summarize_usage(many)["by_uc"]) == RECENT_UCS


# ── Postgres ──────────────────────────────────────────────────────────


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _developer(conn, *, member_of: str | None = None):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    developer_id = f"use-dev-{uuid.uuid4().hex[:8]}"
    token = f"use-tok-{uuid.uuid4().hex[:16]}"
    await register_developer(conn, developer_id=developer_id, display_name="Persona de prueba")
    await register_mcp_token(conn, developer_id=developer_id, token=token)
    if member_of:
        await add_project_member(conn, project_id=member_of, developer_id=developer_id, role="project_admin")
    return developer_id, token


async def _seed(pool):
    project_id = f"Acme/usage-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Coste')", project_id)
        await conn.execute(
            "INSERT INTO user_stories (project_id, id, name, state) VALUES ($1, 'US-01', 'US-01: Cobros', 'in_progress')",
            project_id,
        )
        for uc in ("UC-01", "UC-02"):
            await conn.execute(
                "INSERT INTO use_cases (project_id, id, us_id, name, state) VALUES ($1, $2, 'US-01', $2, 'in_progress')",
                project_id, uc,
            )
        for ac in ("AC-01", "AC-02"):
            await conn.execute(
                "INSERT INTO acceptance_criteria (project_id, id, uc_id, ac_id, text) VALUES ($1, $2, 'UC-01', $3, 'Criterio')",
                project_id, f"UC-01::{ac}", ac,
            )
        owner = await _developer(conn, member_of=project_id)
        stranger = await _developer(conn)
    return project_id, owner, stranger


async def _cleanup(pool, project_id, *developers):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        for developer_id, _ in developers:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


@pg
async def test_ac04_the_table_has_no_free_text_column():
    pool = await _pool()
    columns = {
        r["column_name"]: r["data_type"]
        for r in await pool.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'uc_usage'")
    }
    assert set(columns) == {
        "project_id", "uc_id", "session_id", "agent_id", "developer_id", *TOKEN_FIELDS, "messages",
        "first_reported_at", "last_reported_at",
    }
    numbers = {c for c, t in columns.items() if t in ("bigint", "integer")}
    assert numbers == {*TOKEN_FIELDS, "messages"}


@pg
async def test_ac01_a_member_reports_and_the_uc_adds_up_per_session_and_subagent():
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        kwargs = {"project_id": project_id, "dev_token": owner[1]}
        first = await report_uc_usage(None, "UC-01", SESSION, input_tokens=10, output_tokens=20,
                                      cache_creation_input_tokens=30, cache_read_input_tokens=40, messages=2, **kwargs)
        assert first["success"] and first["recorded"]
        again = await report_uc_usage(None, "UC-01", SESSION, input_tokens=1, output_tokens=2, messages=1, **kwargs)
        assert again["totals"] == {"input_tokens": 11, "output_tokens": 22, "cache_creation_input_tokens": 30,
                                   "cache_read_input_tokens": 40, "messages": 3}
        sub = await report_uc_usage(None, "UC-01", SESSION, input_tokens=5, output_tokens=5, messages=1,
                                    agent_id="af76a0cc43cd28323", **kwargs)
        assert sub["agent_id"] == "af76a0cc43cd28323"
        rows = await pool.fetch("SELECT agent_id, developer_id FROM uc_usage WHERE project_id = $1 ORDER BY agent_id",
                                project_id)
        assert [(r["agent_id"], r["developer_id"]) for r in rows] == [("", owner[0]), ("af76a0cc43cd28323", owner[0])]

        empty = await report_uc_usage(None, "UC-01", SESSION, **kwargs)
        assert empty["recorded"] is False
        missing = await report_uc_usage(None, "UC-77", SESSION, output_tokens=1, messages=1, **kwargs)
        assert missing["code"] == "UC_NOT_FOUND"
        bad = await report_uc_usage(None, "UC-01", SESSION, output_tokens="mucho", **kwargs)
        assert bad["code"] == "INVALID_USAGE"

        # Quien no es miembro recibe lo mismo que si el proyecto no existiera, y no escribe.
        foreign = await report_uc_usage(None, "UC-02", SESSION, output_tokens=1, messages=1,
                                        project_id=project_id, dev_token=stranger[1])
        assert foreign["code"] == "PROJECT_NOT_VISIBLE"
        assert await pool.fetchval("SELECT count(*) FROM uc_usage WHERE project_id = $1 AND uc_id = 'UC-02'",
                                   project_id) == 0
        anonymous = await report_uc_usage(None, "UC-01", SESSION, output_tokens=1, messages=1, project_id=project_id)
        assert anonymous["code"] == "UNAUTHENTICATED"

        # AC-03: UC-01 con dato real (16+27+30+40 = 113 entre 2 criterios); UC-02, en revisión sin dato.
        await pool.execute("UPDATE use_cases SET state = 'review' WHERE project_id = $1", project_id)
        kpis = await usage_kpis(pool, project_id)
        by = {u["uc_id"]: u for u in kpis["by_uc"]}
        assert by["UC-01"]["tokens"] == 113 and by["UC-01"]["estimated"] is False
        assert by["UC-01"]["tokens_per_criterion"] == 56
        assert by["UC-02"]["estimated"] is True and by["UC-02"]["tokens"] is None  # sin criterios
        assert kpis["estimated"] is True and kpis["ucs_with_usage"] == 1
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pg
async def test_ac02_review_time_ends_with_a_person_or_back_to_work():
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        t0 = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
        async with pool.acquire() as conn:
            async def transition(uc, from_state, to_state, minutes):
                await conn.execute(
                    "INSERT INTO uc_state_transitions (project_id, uc_id, us_id, from_state, to_state, occurred_at, source)"
                    " VALUES ($1, $2, 'US-01', $3, $4, $5, 'interactive')",
                    project_id, uc, from_state, to_state, t0 + timedelta(minutes=minutes),
                )

            # UC-01: entra en revisión y una persona la acepta a los 30 min.
            await transition("UC-01", "in_progress", "review", 0)
            await conn.execute(
                "INSERT INTO uc_review_verdicts (project_id, uc_id, verdict, by_kind, developer_id, independent, at)"
                " VALUES ($1, 'UC-01', 'accepted', 'person', $2, true, $3)",
                project_id, owner[0], t0 + timedelta(minutes=30),
            )
            # UC-02: vuelve a trabajo a los 90 min; luego otra revisión que sigue abierta (no cuenta).
            await transition("UC-02", "in_progress", "review", 0)
            await transition("UC-02", "review", "in_progress", 90)
            await transition("UC-02", "in_progress", "review", 120)
            # Un veredicto de agente no cierra la revisión humana.
            await conn.execute(
                "INSERT INTO uc_review_verdicts (project_id, uc_id, verdict, by_kind, independent, at)"
                " VALUES ($1, 'UC-02', 'accepted', 'agent', true, $2)",
                project_id, t0 + timedelta(minutes=125),
            )
        out = await review_time_kpis(pool, project_id)
        assert out["review_episodes"] == 2
        assert out["review_time_p50"] == pytest.approx(3600.0)  # 1800 s y 5400 s
        assert out["review_time_p90"] == pytest.approx(5040.0)
        assert out["review_time_unit"] == "seconds"
    finally:
        await _cleanup(pool, project_id, owner, stranger)


@pg
async def test_ac03_the_most_recent_ucs_come_first():
    """by_uc: primero las UC en revisión, luego las hechas de la más reciente a la más antigua; las de sin
    fecha (anteriores a 0012), al final. El id se ordena como número, no como texto."""
    pool = await _pool()
    project_id, owner, stranger = await _seed(pool)
    try:
        async with pool.acquire() as conn:
            for uc, state, done_at in (("UC-900", "done", None), ("UC-1000", "done", "2026-11-18"),
                                       ("UC-1001", "done", "2026-11-17"), ("UC-99", "review", None)):
                await conn.execute(
                    "INSERT INTO use_cases (project_id, id, us_id, name, state) VALUES ($1, $2, 'US-01', $2, $3)",
                    project_id, uc, state,
                )
                if done_at:
                    await conn.execute(
                        "UPDATE use_cases SET completed_at = $3::date WHERE project_id = $1 AND id = $2",
                        project_id, uc, datetime.fromisoformat(done_at).date(),
                    )
        order = [u["uc_id"] for u in (await usage_kpis(pool, project_id))["by_uc"]]
        assert order == ["UC-99", "UC-1000", "UC-1001", "UC-900"]
    finally:
        await _cleanup(pool, project_id, owner, stranger)


def test_the_migration_has_its_twin():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    local = root / "server" / "db" / "migrations" / "0038_uc_usage.sql"
    twin = root / "supabase" / "migrations" / "20261118000038_uc_usage.sql"
    assert local.read_bytes() == twin.read_bytes()
