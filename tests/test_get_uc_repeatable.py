"""US-117 / UC-11703 — get_uc marca los criterios hechos sin prueba que se repita.

La suite de no regresión vuelve a pasar las pruebas en cada UC, pero un criterio cuyo único recibo es
una captura, un enlace o una nota no tiene nada que lo vuelva a comprobar solo. La marca no dice que
falle.

- **AC-01**: cada criterio hecho dice si tiene al menos un recibo «test» que pasa.
- **AC-02**: uno hecho sin ninguno aparece con la marca «sin prueba que se repita».
- **AC-03**: ``/implement`` deja un recibo «test» con el nombre de la prueba, además de la captura.
- **AC-04**: se calcula al leer: los criterios ya hechos la muestran sin migración.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from server.ac_evidence import NO_REPEATABLE_TEST, repeatable_test
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

ROOT = Path(__file__).resolve().parents[1]


# ── Unidad ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("done", "evidence", "expected"),
    [
        (True, [{"type": "test", "passed": True}], True),
        (True, [{"type": "screenshot", "passed": True}, {"type": "test", "passed": True}], True),
        (True, [{"type": "screenshot", "passed": True}], False),
        (True, [{"type": "url", "passed": True}, {"type": "pr", "passed": True}], False),
        (True, [{"type": "test", "passed": False}], False),  # una prueba que no pasa no respalda
        (True, [], False),
        (False, [{"type": "screenshot", "passed": True}], None),  # sin hacer: sin marca
        (False, [], None),
    ],
)
def test_ac01_ac02_the_rule(done, evidence, expected):
    assert repeatable_test(done, evidence) is expected


# ── AC-03 · /implement ────────────────────────────────────────────────


def test_ac03_implement_leaves_a_test_receipt_per_acceptance_test():
    skill = (ROOT / ".claude/skills/implement/SKILL.md").read_text(encoding="utf-8")
    section = skill[skill.index("### 8.5.4"): skill.index("### 8.5.5")]
    assert "Cada AC que cubre una prueba de aceptación lleva un recibo `test`" in section
    assert '"type": "test"' in section and "{scenario}" in section
    assert "además de su" in section and "captura" in section
    assert "sin prueba que se repita" in section


# ── AC-01, AC-02 y AC-04 · get_uc ─────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_shared_pool():
    import server.db.pool as poolmod

    poolmod._pool = None
    yield
    poolmod._pool = None


@pytestmark_pg
@pytest.mark.asyncio
async def test_ac01_ac02_ac04_get_uc_on_native_without_migration(monkeypatch):
    """Criterios marcados antes de que existiera la marca: get_uc la calcula al leerlos."""
    from server.backends.native_backend import NativeBackend
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool
    from server.tools import spec_driven

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    project_id = f"Acme/repeat-{uuid.uuid4().hex[:8]}"
    developer_id = f"rp-dev-{uuid.uuid4().hex[:8]}"
    token = f"rp-tok-{uuid.uuid4().hex[:16]}"

    def _meta(*types):
        return {
            "evidence": [{"type": t, "label": t, "link": None, "detail": None, "by": developer_id,
                          "at": "2026-10-01T10:00:00+00:00", "passed": True} for t in types],
            "verdict": {"passed": True, "by": developer_id, "at": "2026-10-01T10:00:00+00:00"},
        }

    criteria = [
        ("AC-01", True, _meta("test", "screenshot")),  # prueba que se repite
        ("AC-02", True, _meta("screenshot")),  # solo captura
        ("AC-03", True, {}),  # hecho sin recibos
        ("AC-04", False, _meta("screenshot")),  # sin hacer
    ]
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Repeat Tester")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Repeat')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute("INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'US', 'backlog')", project_id)
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state, labels, meta) "
            "VALUES ('UC-001', $1, 'US-01', 'UC-001: UC', 'backlog', '[\"UC\"]'::jsonb, '{\"uc_id\": \"UC-001\"}'::jsonb)",
            project_id,
        )
        for ac_id, done, meta in criteria:
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, meta) "
                "VALUES ($1, $2, 'UC-001', $3, 'Criterio', $4, $5::jsonb)",
                f"UC-001::{ac_id}", project_id, ac_id, done, json.dumps(meta),
            )
    try:
        backend = NativeBackend(project_id=project_id, dev_token=token)

        async def _session_backend(ctx, items_content=None):
            return backend

        monkeypatch.setattr(spec_driven, "get_session_backend", _session_backend)
        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        acs = {a["id"]: a for a in uc["acceptance_criteria"]}
        assert (acs["AC-01"]["repeatable_test"], acs["AC-01"]["flags"]) == (True, [])
        assert (acs["AC-02"]["repeatable_test"], acs["AC-02"]["flags"]) == (False, [NO_REPEATABLE_TEST])
        assert (acs["AC-03"]["repeatable_test"], acs["AC-03"]["flags"]) == (False, [NO_REPEATABLE_TEST])
        assert (acs["AC-04"]["repeatable_test"], acs["AC-04"]["flags"]) == (None, [])
        assert NO_REPEATABLE_TEST == "sin_prueba_que_se_repita"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
            await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


@pytest.mark.asyncio
async def test_ac01_ac02_get_uc_on_freeform_reads_the_type_from_the_comments(monkeypatch):
    """Sin almacén por criterio (Trello, Plane, FreeForm) el tipo sale del comentario estructurado."""
    from server.backends.freeform_backend import FreeformBackend
    from server.tools import spec_driven

    class _KeepOpen(FreeformBackend):
        async def close(self) -> None:
            return None

    def _item(item_id, name, labels, state, parent=None, **meta):
        return {"id": item_id, "name": name, "state": state, "parent_id": parent, "labels": labels,
                "priority": "none", "meta": meta}

    items = [
        _item("us1", "US-01: Historia", ["US"], "done", us_id="US-01"),
        _item("uc1", "UC-001: Caso", ["UC"], "done", "us1", uc_id="UC-001", us_id="US-01"),
        _item("ac1", "[AC-01] Con prueba", ["AC"], "done", "uc1", ac_id="AC-01"),
        _item("ac2", "[AC-02] Con nota", ["AC"], "done", "uc1", ac_id="AC-02"),
    ]
    backend = _KeepOpen(items_content=json.dumps(items))
    await backend.add_comment("ff", "uc1", "AC-01: PASSED — [test] test_x · commit abc1234 [2026-11-10 01:00 UTC]")
    await backend.add_comment("ff", "uc1", "AC-02: PASSED — 12 passed [2026-11-10 01:00 UTC]")

    async def _session_backend(ctx, items_content=None):
        return backend

    monkeypatch.setattr(spec_driven, "get_session_backend", _session_backend)
    uc = await spec_driven.get_uc(board_id="ff", uc_id="UC-001", ctx=None)
    acs = {a["id"]: a for a in uc["acceptance_criteria"]}
    assert acs["AC-01"]["repeatable_test"] is True and acs["AC-01"]["flags"] == []
    assert acs["AC-02"]["repeatable_test"] is False and acs["AC-02"]["flags"] == [NO_REPEATABLE_TEST]
