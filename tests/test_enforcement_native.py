"""US-122 / UC-12212 — la política de medidas en el tablero native (Postgres).

Modelo de amenazas §8: sin identidad, otro developer (no ve, no escribe) y ``member`` frente a
``project_admin``. Además: un tablero nuevo frente a uno que ya existía y el salto con motivo en la
auditoría. SKIP limpio sin base de datos (``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.tools.enforcement import get_enforcement_policy, set_enforcement_mode, skip_enforcement
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

MOTIVO = "El cliente validó estos criterios en la reunión del martes."


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _developer(conn, *, member_of: str | None = None, role: str = "member", name: str = "Persona"):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    developer_id = f"enf-dev-{uuid.uuid4().hex[:8]}"
    token = f"enf-tok-{uuid.uuid4().hex[:16]}"
    await register_developer(conn, developer_id=developer_id, display_name=name)
    await register_mcp_token(conn, developer_id=developer_id, token=token)
    if member_of:
        await add_project_member(conn, project_id=member_of, developer_id=developer_id, role=role)
    return developer_id, token


async def _existing_board(pool):
    """Un proyecto como los de antes de esta versión: sin política en meta."""
    project_id = f"Acme/enforce-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Existente')", project_id)
        admin = await _developer(conn, member_of=project_id, role="project_admin", name="Ana Admin")
        member = await _developer(conn, member_of=project_id, name="Luis Miembro")
        stranger = await _developer(conn, name="Otra Persona")
    return project_id, admin, member, stranger


async def _to_block(project_id: str, token: str, measure: str = "spec_quality") -> dict:
    """Pasar a «block» en sus dos pasos (UC-12213): el informe con su código y la confirmación."""
    ask = await set_enforcement_mode(None, measure, "block", board_id=project_id, dev_token=token)
    assert ask["code"] == "CONFIRMATION_REQUIRED", ask
    return await set_enforcement_mode(None, measure, "block", board_id=project_id, dev_token=token,
                                      confirm=ask["confirm"])


async def _cleanup(pool, project_id, *developers):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM audit_log WHERE project_id = $1", project_id)
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        for developer_id, _ in developers:
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


async def test_a_board_created_now_is_new_and_one_from_before_is_existing():
    """AC-02: el alta escribe origin «new»; re-abrir la sesión no lo toca; uno de antes queda en «warn»."""
    from server.migration.native_handling import provision_native_project

    pool = await _pool()
    project_id = f"Acme/nuevo-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        owner = await _developer(conn, name="Creadora")
    try:
        await provision_native_project(pool, project_id=project_id, developer_id=owner[0], name="Nuevo")
        out = await get_enforcement_policy(None, board_id=project_id, dev_token=owner[1])
        assert out["success"] and out["policy"]["origin"] == "new"
        assert {m["mode"] for m in out["policy"]["measures"].values()} == {"warn"}

        await _to_block(project_id, owner[1])
        # Cada set_auth_token vuelve a pasar por el alta: no reescribe la política.
        await provision_native_project(pool, project_id=project_id, developer_id=owner[0], name="Nuevo")
        again = await get_enforcement_policy(None, board_id=project_id, dev_token=owner[1])
        assert again["policy"]["measures"]["spec_quality"]["mode"] == "block"
        assert again["policy"]["origin"] == "new"
    finally:
        await _cleanup(pool, project_id, owner)

    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        out = await get_enforcement_policy(None, board_id=project_id, dev_token=member[1])
        assert out["policy"]["origin"] == "existing"
        assert {m["mode"] for m in out["policy"]["measures"].values()} == {"warn"}
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


async def test_a_project_migrated_into_native_counts_as_existing():
    from server.migration.native_handling import provision_native_project

    pool = await _pool()
    project_id = f"Acme/migrado-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        owner = await _developer(conn)
    try:
        await provision_native_project(
            pool, project_id=project_id, developer_id=owner[0], enforcement_origin="existing"
        )
        out = await get_enforcement_policy(None, board_id=project_id, dev_token=owner[1])
        assert out["policy"]["origin"] == "existing"
    finally:
        await _cleanup(pool, project_id, owner)


async def test_without_identity_or_from_another_project_nothing_is_seen_or_written():
    """Modelo de amenazas §8: sin identidad; otro developer no ve ni escribe (lo ajeno no existe)."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        sin = await get_enforcement_policy(None, board_id=project_id, dev_token="")
        assert sin["code"] == "UNAUTHENTICATED" and "policy" not in sin
        for call in (
            get_enforcement_policy(None, board_id=project_id, dev_token=stranger[1]),
            set_enforcement_mode(None, "spec_quality", "off", board_id=project_id, dev_token=stranger[1]),
            skip_enforcement(None, "spec_quality", "UC-1", MOTIVO, board_id=project_id, dev_token=stranger[1]),
        ):
            out = await call
            assert out["code"] == "PROJECT_NOT_VISIBLE" and "policy" not in out
        assert await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", project_id) is None
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


async def test_only_the_admin_changes_a_mode_and_it_stays_in_the_audit():
    """AC-01 y AC-02: un miembro no cambia modos; la administradora sí, con fila en la auditoría."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        denied = await set_enforcement_mode(None, "spec_quality", "block", board_id=project_id, dev_token=member[1])
        assert denied["code"] == "FORBIDDEN" and "project_admin" in denied["error"]
        assert await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", project_id) is None

        ok = await _to_block(project_id, admin[1])
        assert ok["success"] and (ok["previous"], ok["mode"]) == ("warn", "block")
        assert ok["policy"]["measures"]["spec_quality"]["set_by"] == admin[0]
        assert ok["policy"]["origin"] == "existing"
        row = await pool.fetchrow(
            "SELECT developer_id, target_id, metadata FROM audit_log "
            "WHERE project_id = $1 AND operation = 'enforcement_mode'",
            project_id,
        )
        metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        assert (row["developer_id"], row["target_id"]) == (admin[0], "spec_quality")
        assert metadata == {"measure": "spec_quality", "from": "warn", "to": "block"}

        seen = await get_enforcement_policy(None, board_id=project_id, dev_token=member[1])
        assert seen["policy"]["measures"]["spec_quality"]["mode"] == "block"
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


async def test_a_member_skips_a_block_with_a_reason_that_stays_on_the_board():
    """AC-05: quién, cuándo y por qué, en el tablero y en la auditoría."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        nada = await skip_enforcement(None, "spec_quality", "UC-7", MOTIVO, board_id=project_id, dev_token=member[1])
        assert nada["code"] == "NOTHING_TO_SKIP"

        await _to_block(project_id, admin[1])
        corto = await skip_enforcement(None, "spec_quality", "UC-7", "porque", board_id=project_id,
                                       dev_token=member[1])
        assert corto["code"] == "REASON_REQUIRED" and corto["measure"] == "spec_quality"

        out = await skip_enforcement(None, "spec_quality", "UC-7", MOTIVO, board_id=project_id, dev_token=member[1])
        assert out["success"] and out["skip"]["by"] == member[0] and out["skip"]["reason"] == MOTIVO
        stored = json.loads(
            await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", project_id)
        )
        assert stored["skips"] == [out["skip"]]
        row = await pool.fetchrow(
            "SELECT developer_id, target_id, metadata, occurred_at FROM audit_log "
            "WHERE project_id = $1 AND operation = 'enforcement_skip'",
            project_id,
        )
        metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
        assert (row["developer_id"], row["target_id"]) == (member[0], "UC-7")
        assert metadata == {"measure": "spec_quality", "uc_id": "UC-7", "reason": MOTIVO}
        assert row["occurred_at"] is not None
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


# ══ UC-12213 — informe de impacto, lo anterior a la regla y los bloqueos ══

from server.tools.enforcement import (  # noqa: E402
    enforcement_readiness,
    get_enforcement_impact,
    record_enforcement_event,
)


async def _seed_ucs(pool, project_id):
    """Una historia con una UC vaga, una con marca «por decidir», una bien escrita y una cerrada."""
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO user_stories (id, project_id, name) VALUES ('US-1', $1, 'H')", project_id)
        for uc_id, state, desc in (("UC-101", "backlog", ""), ("UC-102", "in_progress", "[POR DECIDIR: proveedor]"),
                                   ("UC-103", "backlog", ""), ("UC-104", "done", "")):
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name, description, state) VALUES ($2, $1, 'US-1', $3, $4, $5)",
                project_id, uc_id, f"{uc_id}: C", desc, state,
            )
        for uc_id, text in (("UC-101", "Funciona bien"), ("UC-102", "El informe muestra 3 UC con su motivo"),
                            ("UC-103", "El informe muestra 3 UC con su motivo"), ("UC-104", "Funciona bien")):
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text) VALUES ($2, $1, $3, 'AC-01', $4)",
                project_id, f"{uc_id}::AC-01", uc_id, text,
            )


async def test_the_impact_report_reads_the_board_without_changing_it():
    """AC-01 con Postgres: UC abiertas y motivo; nada cambia en el tablero."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        await _seed_ucs(pool, project_id)
        before = await pool.fetchval("SELECT count(*) FROM audit_log WHERE project_id = $1", project_id)
        out = await get_enforcement_impact(None, board_id=project_id, dev_token=member[1])
        report = out["report"]
        assert out["success"] and report["open_ucs"] == 3
        quality = report["measures"]["spec_quality"]
        assert [u["uc_id"] for u in quality["ucs"]] == ["UC-101"] and "AC-01" in quality["ucs"][0]["reason"]
        assert [u["uc_id"] for u in report["measures"]["pending_decisions"]["ucs"]] == ["UC-102"]
        assert await pool.fetchval("SELECT count(*) FROM audit_log WHERE project_id = $1", project_id) == before
        assert await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", project_id) is None
        ajeno = await get_enforcement_impact(None, board_id=project_id, dev_token=stranger[1])
        assert ajeno["code"] == "PROJECT_NOT_VISIBLE" and "report" not in ajeno
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


async def test_going_to_block_asks_first_and_keeps_the_open_ucs_safe():
    """AC-02 y AC-03 con Postgres."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        await _seed_ucs(pool, project_id)
        ask = await set_enforcement_mode(None, "spec_quality", "block", board_id=project_id, dev_token=admin[1])
        assert ask["code"] == "CONFIRMATION_REQUIRED" and ask["impact"]["would_block"] == 1
        assert await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", project_id) is None
        ok = await set_enforcement_mode(None, "spec_quality", "block", board_id=project_id, dev_token=admin[1],
                                        confirm=ask["confirm"])
        assert ok["success"] and ok["policy"]["measures"]["spec_quality"]["predating_ucs"] == 3

        quality = (await get_enforcement_impact(None, board_id=project_id, dev_token=member[1]))["report"]["measures"]["spec_quality"]
        assert (quality["would_block"], quality["predates_rule"], quality["blocks_now"]) == (1, 1, 0)

        # Reescribir el criterio vago la saca de «anterior a la regla»: ya la detendría.
        await pool.execute(
            "UPDATE acceptance_criteria SET text = 'Funciona muy bien' WHERE project_id = $1 AND uc_id = 'UC-101'",
            project_id,
        )
        quality = (await get_enforcement_impact(None, board_id=project_id, dev_token=member[1]))["report"]["measures"]["spec_quality"]
        assert (quality["predates_rule"], quality["blocks_now"]) == (0, 1)
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


async def test_blocks_are_recorded_and_end_corrected_or_skipped():
    """AC-04 con Postgres: bloqueos en la auditoría y el porcentaje de saltos en el informe."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        await _to_block(project_id, admin[1])
        for uc in ("UC-1", "UC-2"):
            rec = await record_enforcement_event(None, "spec_quality", uc, "blocked", board_id=project_id,
                                                 dev_token=member[1])
            assert rec["success"] and rec["event"]["outcome"] == "blocked"
        await record_enforcement_event(None, "spec_quality", "UC-1", "passed", board_id=project_id, dev_token=member[1])
        await skip_enforcement(None, "spec_quality", "UC-2", MOTIVO, board_id=project_id, dev_token=member[1])
        events = (await get_enforcement_impact(None, board_id=project_id, dev_token=member[1]))["report"]["measures"]["spec_quality"]["events"]
        assert (events["blocks"], events["corrected"], events["skipped"], events["skip_rate"]) == (2, 1, 1, 0.5)
        ops = [r["operation"] for r in await pool.fetch(
            "SELECT operation FROM audit_log WHERE project_id = $1 AND operation LIKE 'enforcement_%' ORDER BY id",
            project_id,
        )]
        assert ops == ["enforcement_mode", "enforcement_block", "enforcement_block", "enforcement_pass", "enforcement_skip"]
        ajeno = await record_enforcement_event(None, "spec_quality", "UC-1", "blocked", board_id=project_id,
                                               dev_token=stranger[1])
        assert ajeno["code"] == "PROJECT_NOT_VISIBLE"
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)


async def test_readiness_is_for_the_operator_only(monkeypatch):
    """AC-05: la lectura de candidatas es del operador; nadie más la ve."""
    pool = await _pool()
    project_id, admin, member, stranger = await _existing_board(pool)
    try:
        sin = await enforcement_readiness(None, dev_token="")
        assert sin["code"] == "UNAUTHENTICATED"
        assert (await enforcement_readiness(None, dev_token=member[1]))["code"] == "FORBIDDEN"
        monkeypatch.setenv("SPECBOX_OPERATOR_DEVELOPER_IDS", admin[0])
        out = await enforcement_readiness(None, dev_token=admin[1])
        assert out["success"] and set(out["measures"]) >= {"spec_quality", "closing_evidence"}
        assert all(m["candidate"] is False for m in out["measures"].values())  # sin 20 bloqueos no hay dato
        assert "codename" in out["rule"]
    finally:
        await _cleanup(pool, project_id, admin, member, stranger)
