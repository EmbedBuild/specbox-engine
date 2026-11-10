"""US-117 / UC-11701 — reescribir un criterio hecho lo deja pendiente de comprobar.

Lo que se comprobó y lo que se aceptó era el texto anterior. Decisión de Jesús (2026-11-10): se
invalida por eventos, y reescribir el criterio es uno.

- **AC-01**: ``update_ac`` con texto nuevo sobre un criterio hecho → sin hacer, y la aceptación de
  su UC desaparece de ``uc_acceptances``.
- **AC-02**: lo mismo con SQL directo sobre ``acceptance_criteria`` (trigger de la migración 0035).
- **AC-03**: el mismo texto no cambia nada.
- **AC-04**: la respuesta avisa de que el criterio queda pendiente de volver a comprobarse.

Las de Postgres hacen SKIP limpio sin base de datos de desarrollo
(``docker compose -f docker-compose.dev.yml up -d``).
"""

from __future__ import annotations

import json
import uuid

import pytest

from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)

TEXT = "El informe muestra el total del mes"
NEW_TEXT = "El informe muestra el total del mes y el del año"


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


async def _seed(pool):
    """Una UC hecha y aceptada, con dos criterios hechos y verificados (uno con justificante)."""
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    project_id = f"Acme/ac-reset-{uuid.uuid4().hex[:8]}"
    developer_id = f"ar-dev-{uuid.uuid4().hex[:8]}"
    token = f"ar-tok-{uuid.uuid4().hex[:16]}"
    evidence = [{"type": "test", "label": "test_total", "link": None, "detail": None,
                 "by": developer_id, "at": "2026-11-01T10:00:00+00:00", "passed": True}]
    meta = {"verdict": {"passed": True, "by": developer_id, "at": "2026-11-01T10:00:00+00:00"},
            "evidence": evidence}
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Ana Owner")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'AC reset')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-01', $1, 'US-01: US', 'done')",
            project_id,
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, state, labels, meta) "
            "VALUES ('UC-001', $1, 'US-01', 'UC-001: UC', 'done', '[\"UC\"]'::jsonb, "
            "'{\"uc_id\": \"UC-001\", \"us_id\": \"US-01\"}'::jsonb)",
            project_id,
        )
        for ac_id in ("AC-01", "AC-02"):
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, meta) "
                "VALUES ($1, $2, 'UC-001', $3, $4, true, $5::jsonb)",
                f"UC-001::{ac_id}",
                project_id,
                ac_id,
                TEXT,
                json.dumps(meta),
            )
        await conn.execute(
            "INSERT INTO uc_acceptances (project_id, uc_id, accepted_by_developer_id) VALUES ($1, 'UC-001', $2)",
            project_id,
            developer_id,
        )
    return project_id, developer_id, token


async def _criterion(conn, project_id, ac_id="AC-01"):
    row = await conn.fetchrow(
        "SELECT text, done, meta FROM acceptance_criteria WHERE project_id = $1 AND ac_id = $2", project_id, ac_id
    )
    meta = row["meta"] if isinstance(row["meta"], dict) else json.loads(row["meta"])
    return row["text"], row["done"], meta


async def _accepted(conn, project_id) -> bool:
    return bool(
        await conn.fetchval("SELECT count(*) FROM uc_acceptances WHERE project_id = $1 AND uc_id = 'UC-001'", project_id)
    )


async def _cleanup(pool, project_id, developer_id):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
        await conn.execute("DELETE FROM developers WHERE developer_id = $1", developer_id)


def _use(monkeypatch, backend):
    from server.tools import spec_driven, spec_mutations

    async def _session_backend(ctx, items_content=None):
        return backend

    monkeypatch.setattr(spec_mutations, "get_session_backend", _session_backend)
    monkeypatch.setattr(spec_driven, "get_session_backend", _session_backend)


# ── AC-01 y AC-04 · update_ac ─────────────────────────────────────────


@pytestmark_pg
async def test_update_ac_with_new_text_leaves_it_pending_and_voids_the_acceptance(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_driven, spec_mutations

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        _use(monkeypatch, NativeBackend(project_id=project_id, dev_token=token))
        result = await spec_mutations.update_ac(project_id, "UC-001", "AC-01", ctx=None, text=NEW_TEXT)

        assert result["updated_fields"] == ["text", "done"]
        assert result["reset_to_pending"] is True
        assert "pendiente de volver a comprobarse" in result["warning"]  # AC-04
        async with pool.acquire() as conn:
            text, done, meta = await _criterion(conn, project_id)
            assert (text, done) == (NEW_TEXT, False)
            assert meta["verdict"]["passed"] is False and meta["verdict"]["reason"] == "text_changed"
            assert meta["verdict"]["by"] == developer_id, "firma quien reescribe, no un desconocido"
            assert meta["verdict"]["previous_text"] == TEXT
            assert meta["evidence"][0]["label"] == "test_total", "los justificantes quedan como historial"
            assert not await _accepted(conn, project_id)
            other = await _criterion(conn, project_id, "AC-02")
            assert other[1] is True, "el otro criterio no se toca"

        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        ac = next(a for a in uc["acceptance_criteria"] if a["id"] == "AC-01")
        assert ac["done"] is False and ac["verified"] is None
        assert uc["human_acceptance"] is None
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
async def test_done_true_in_the_same_call_is_not_applied(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_mutations

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        _use(monkeypatch, NativeBackend(project_id=project_id, dev_token=token))
        result = await spec_mutations.update_ac(project_id, "UC-001", "AC-01", ctx=None, text=NEW_TEXT, done=True)

        assert result["reset_to_pending"] is True and result["ignored"] == ["done"]
        async with pool.acquire() as conn:
            assert (await _criterion(conn, project_id))[1] is False
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
async def test_marking_it_done_again_without_mark_ac_does_not_bring_back_the_old_verification(monkeypatch):
    """El veredicto queda en «no pasa»: un done=true sin mark_ac no resucita la verificación."""
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_driven, spec_mutations

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        _use(monkeypatch, NativeBackend(project_id=project_id, dev_token=token))
        await spec_mutations.update_ac(project_id, "UC-001", "AC-01", ctx=None, text=NEW_TEXT)
        await spec_mutations.update_ac(project_id, "UC-001", "AC-01", ctx=None, done=True)

        uc = await spec_driven.get_uc(board_id=project_id, uc_id="UC-001", ctx=None)
        ac = next(a for a in uc["acceptance_criteria"] if a["id"] == "AC-01")
        assert ac["done"] is True and ac["verified"] is None
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
async def test_update_ac_batch_resets_and_warns_each_rewritten_criterion(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_mutations

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        _use(monkeypatch, NativeBackend(project_id=project_id, dev_token=token))
        result = await spec_mutations.update_ac_batch(
            project_id,
            [{"uc_id": "UC-001", "ac_id": "AC-01", "text": NEW_TEXT}, {"uc_id": "UC-001", "ac_id": "AC-02", "text": TEXT}],
            ctx=None,
        )
        rewritten, same = result["succeeded"]
        assert rewritten["reset_to_pending"] is True and "warning" in rewritten
        assert same["reason"] == "no_change" and "reset_to_pending" not in same
        async with pool.acquire() as conn:
            assert (await _criterion(conn, project_id))[1] is False
            assert (await _criterion(conn, project_id, "AC-02"))[1] is True
            assert not await _accepted(conn, project_id)
    finally:
        await _cleanup(pool, project_id, developer_id)


# ── AC-02 · SQL directo ───────────────────────────────────────────────


@pytestmark_pg
async def test_direct_sql_text_change_leaves_it_pending_and_voids_the_acceptance():
    pool = await _pool()
    project_id, developer_id, _ = await _seed(pool)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE acceptance_criteria SET text = $2 WHERE project_id = $1 AND ac_id = 'AC-01'", project_id, NEW_TEXT
            )
            text, done, meta = await _criterion(conn, project_id)
            assert (text, done) == (NEW_TEXT, False)
            assert meta["verdict"] == {
                "passed": False, "by": None, "at": meta["verdict"]["at"], "reason": "text_changed", "previous_text": TEXT,
            }
            assert len(meta["evidence"]) == 1
            assert not await _accepted(conn, project_id)
    finally:
        await _cleanup(pool, project_id, developer_id)


@pytestmark_pg
async def test_direct_sql_on_a_pending_or_internal_criterion():
    """Un criterio sin hacer solo cambia de texto; uno interno hecho queda sin hacer sin tocar la aceptación."""
    pool = await _pool()
    project_id, developer_id, _ = await _seed(pool)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, done, internal) "
                "VALUES ('UC-001::AC-03', $1, 'UC-001', 'AC-03', 'Interno', true, true)",
                project_id,
            )
            await conn.execute(
                "UPDATE acceptance_criteria SET text = 'Interno nuevo' WHERE project_id = $1 AND ac_id = 'AC-03'",
                project_id,
            )
            assert (await _criterion(conn, project_id, "AC-03"))[1] is False
            assert await _accepted(conn, project_id), "un criterio interno no anula la aceptación"

            await conn.execute("UPDATE acceptance_criteria SET done = false WHERE project_id = $1 AND ac_id = 'AC-03'", project_id)
            await conn.execute(
                "UPDATE acceptance_criteria SET text = 'Otra vez' WHERE project_id = $1 AND ac_id = 'AC-03'", project_id
            )
            _, done, meta = await _criterion(conn, project_id, "AC-03")
            assert done is False
            assert meta["verdict"]["previous_text"] == "Interno", "sin hacer: el trigger no se mete"
    finally:
        await _cleanup(pool, project_id, developer_id)


# ── AC-03 · el mismo texto ────────────────────────────────────────────


@pytestmark_pg
async def test_same_text_changes_nothing(monkeypatch):
    from server.backends.native_backend import NativeBackend
    from server.tools import spec_mutations

    pool = await _pool()
    project_id, developer_id, token = await _seed(pool)
    try:
        _use(monkeypatch, NativeBackend(project_id=project_id, dev_token=token))
        result = await spec_mutations.update_ac(project_id, "UC-001", "AC-01", ctx=None, text=TEXT)
        assert result["reason"] == "no_change" and "reset_to_pending" not in result

        async with pool.acquire() as conn:
            # También por SQL: un SET con el mismo texto no es un cambio.
            await conn.execute(
                "UPDATE acceptance_criteria SET text = $2 WHERE project_id = $1 AND ac_id = 'AC-01'", project_id, TEXT
            )
            text, done, meta = await _criterion(conn, project_id)
            assert (text, done) == (TEXT, True) and meta["verdict"]["passed"] is True
            assert await _accepted(conn, project_id)
    finally:
        await _cleanup(pool, project_id, developer_id)


# ── Sin trigger: Trello, Plane y FreeForm (por la tool) ───────────────


async def test_freeform_rewrite_leaves_it_pending_and_the_old_passed_comment_no_longer_counts(monkeypatch):
    from server.backends.freeform_backend import FreeformBackend
    from server.tools import spec_driven, spec_mutations

    class _KeepOpen(FreeformBackend):
        async def close(self) -> None:
            return None

    def _item(item_id, name, labels, state, parent=None, **meta):
        return {"id": item_id, "name": name, "state": state, "parent_id": parent, "labels": labels,
                "priority": "none", "meta": meta}

    items = [
        _item("us1", "US-01: Historia", ["US"], "done", us_id="US-01"),
        _item("uc1", "UC-001: Caso", ["UC"], "done", "us1", uc_id="UC-001", us_id="US-01"),
        _item("ac1", f"[AC-01] {TEXT}", ["AC"], "done", "uc1", ac_id="AC-01"),
    ]
    backend = _KeepOpen(items_content=json.dumps(items))
    board = "ff-test"
    await backend.add_comment(board, "uc1", "AC-01: PASSED — test_total [2026-11-01 10:00 UTC]")
    _use(monkeypatch, backend)

    uc = await spec_driven.get_uc(board_id=board, uc_id="UC-001", ctx=None)
    assert uc["acceptance_criteria"][0]["verified"] is not None, "antes, el PASSED cuenta"

    result = await spec_mutations.update_ac(board, "UC-001", "AC-01", ctx=None, text=NEW_TEXT, done=True)
    assert result["reset_to_pending"] is True and result["ignored"] == ["done"]

    uc = await spec_driven.get_uc(board_id=board, uc_id="UC-001", ctx=None)
    ac = uc["acceptance_criteria"][0]
    assert (ac["text"], ac["done"], ac["verified"]) == (NEW_TEXT, False, None)

    await spec_mutations.update_ac(board, "UC-001", "AC-01", ctx=None, done=True)
    uc = await spec_driven.get_uc(board_id=board, uc_id="UC-001", ctx=None)
    assert uc["acceptance_criteria"][0]["verified"] is None, "el PASSED del texto anterior ya no cuenta"
