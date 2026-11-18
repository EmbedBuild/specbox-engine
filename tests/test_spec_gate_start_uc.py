"""US-123 / UC-12301 — start_uc no arranca una UC cuya spec no pasa el gate.

- **AC-01**: con ``spec_quality`` en «block», una UC con algún criterio en ``failed`` devuelve
  ``AC_QUALITY_BELOW_THRESHOLD``, no se reserva y queda en su estado.
- **AC-02**: una UC sin criterios no arranca: el gate la cuenta con un ``pass_rate`` de 0.
- **AC-03**: el umbral se guarda por proyecto (1,0 por defecto) y el error nombra cada criterio que
  falla con su motivo.
- **AC-04**: ``import_spec`` y ``add_ac`` devuelven ``spec_gate`` de cada UC que tocan.
- **AC-06**: en «warn» arranca y la respuesta lista lo que falla; en «block» no; una UC anterior a la
  regla arranca en cualquier modo.

FreeForm por contenido (el MCP remoto) aquí; native contra Postgres al final (SKIP sin base).
"""

from __future__ import annotations

import json
import time
import uuid

import pytest

from server.coordination import enforcement as pol
from server.tools.board_operations import validate_ac_quality
from server.tools.spec_driven import import_spec, start_uc
from server.tools.spec_mutations import add_ac

AT = "2026-11-18T10:00:00+00:00"


class _Ctx:
    def __init__(self, config):
        self._config = config

    async def get_state(self, key):
        return self._config


CTX = _Ctx({"backend_type": "freeform", "content_only": True})
US = {"id": "us7", "name": "US-07: Pagos", "description": "", "state": "user_stories", "labels": ["US"],
      "meta": {"us_id": "US-07"}}
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "Cobrar con tarjeta", "state": "backlog",
      "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
GOOD = {"id": "ac1", "name": "[AC-01] El cobro queda registrado con su recibo", "state": "backlog", "labels": ["AC"],
        "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}
BAD = {"id": "ac2", "name": "[AC-02] La app es buena", "state": "backlog", "labels": ["AC"], "parent_id": "uc701",
       "meta": {"ac_id": "AC-02"}}


def _policy(mode: str = "block", *, threshold: float | None = None, open_ucs: dict | None = None) -> dict:
    stored, _ = pol.with_mode(None, "spec_quality", mode, by="ana", at=AT, backend_type="freeform",
                              open_ucs=open_ucs or {}, threshold=threshold)
    return stored


def _state(items_content: str, uc_id: str = "UC-701") -> str:
    return next(i["state"] for i in json.loads(items_content) if i.get("meta", {}).get("uc_id") == uc_id)


# ── La parte pura ───────────────────────────────────────────────────


def test_the_gate_counts_a_uc_without_criteria_as_zero():
    """AC-02."""
    result = pol.spec_quality_result({"uc_id": "UC-1", "acs": []})
    assert result["pass_rate"] == 0 and not result["meets_threshold"]
    assert "no tiene criterios" in pol.spec_quality_reason(result)


def test_the_threshold_is_per_project_and_one_by_default():
    """AC-03: 1,0 sin nada guardado; set_enforcement_mode lo guarda y se conserva al cambiar el modo."""
    assert pol.effective_policy(None, backend_type="native")["measures"]["spec_quality"]["threshold"] == 1.0
    stored = _policy("warn", threshold=0.8)
    assert pol.threshold_of(stored) == 0.8
    again, _ = pol.with_mode(stored, "spec_quality", "block", by="ana", at=AT, backend_type="freeform")
    assert pol.threshold_of(again) == 0.8
    assert pol.effective_policy(again, backend_type="freeform")["measures"]["spec_quality"]["threshold"] == 0.8
    for bad in (0, 1.5, -1, True, "1"):
        with pytest.raises(pol.PolicyError) as e:
            pol.with_mode(None, "spec_quality", "warn", by="ana", at=AT, backend_type="freeform", threshold=bad)
        assert e.value.code == "INVALID_THRESHOLD"
    with pytest.raises(pol.PolicyError) as e:
        pol.with_mode(None, "spec_in_pr", "warn", by="ana", at=AT, backend_type="freeform", threshold=0.5)
    assert e.value.code == "THRESHOLD_NOT_SUPPORTED"


def test_spec_quality_is_active_from_this_version():
    assert pol.effective_policy(None, backend_type="native")["measures"]["spec_quality"]["active"] is True


def test_validate_ac_quality_gives_zero_to_a_uc_without_criteria():
    """AC-02 también en la tool que mide el gate."""
    import asyncio

    board = json.dumps([US, UC])
    out = asyncio.run(validate_ac_quality("ff", CTX, uc_id="UC-701", items_content=board))
    assert out["total_acs"] == 0 and out["pass_rate"] == 0


# ── start_uc con FreeForm por contenido ─────────────────────────────


async def test_block_stops_the_start_names_each_failing_criterion_and_moves_nothing():
    """AC-01 y AC-03."""
    board = json.dumps([US, UC, GOOD, BAD])
    out = await start_uc("ff", "UC-701", CTX, items_content=board, policy_content=json.dumps(_policy()))
    assert out["success"] is False and out["code"] == "AC_QUALITY_BELOW_THRESHOLD"
    assert out["measure"] == "spec_quality" and out["uc_id"] == "UC-701"
    assert out["pass_rate"] == 0.5 and out["threshold"] == 1.0
    assert [f["ac_id"] for f in out["failed"]] == ["AC-02"]
    assert "AC-02 (vague, no_observable_outcome)" in out["error"]
    assert "skip_enforcement" in out["how_to_continue"]
    # Nada se movió: la respuesta no trae tablero que guardar y el hook no fusiona nada.
    assert "items_content" not in out and "active_uc_marker" not in out
    line = json.loads(out["event_line"])
    assert line["measure"] == "spec_quality" and line["uc_id"] == "UC-701" and line["outcome"] == "blocked"


async def test_block_stops_a_uc_without_criteria():
    """AC-02."""
    out = await start_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC]),
                         policy_content=json.dumps(_policy()))
    assert out["code"] == "AC_QUALITY_BELOW_THRESHOLD" and out["pass_rate"] == 0 and out["total"] == 0


async def test_warn_starts_and_lists_what_fails():
    """AC-06: «warn» (lo de partida) arranca y avisa con los criterios que fallan."""
    board = json.dumps([US, UC, GOOD, BAD])
    out = await start_uc("ff", "UC-701", CTX, items_content=board)
    assert out["status"] == "in_progress" and _state(out["items_content"]) == "in_progress"
    [warning] = out["enforcement_warnings"]
    assert warning["measure"] == "spec_quality" and warning["outcome"] == "warned"
    assert [f["ac_id"] for f in warning["failed"]] == ["AC-02"]
    assert "skip_enforcement" not in warning["how_to_continue"]  # en «warn» no hay bloqueo que saltar


async def test_a_uc_that_predates_the_rule_starts_in_block():
    """AC-06: abierta cuando la medida pasó a «block» y sin cambios desde entonces."""
    from server.tools.enforcement import _freeform_open_ucs

    board = json.dumps([US, UC, GOOD, BAD])
    uc = next(u for u in await _freeform_open_ucs(board) if u["uc_id"] == "UC-701")
    stored = _policy(open_ucs=pol.open_uc_fingerprints([uc]))
    out = await start_uc("ff", "UC-701", CTX, items_content=board, policy_content=json.dumps(stored))
    assert out["status"] == "in_progress"
    assert out["enforcement_warnings"][0]["outcome"] == "predates_rule"

    # Si cambia un criterio deja de ser anterior a la regla.
    changed = json.dumps([US, UC, GOOD, {**BAD, "name": "[AC-02] La app es muy buena"}])
    blocked = await start_uc("ff", "UC-701", CTX, items_content=changed, policy_content=json.dumps(stored))
    assert blocked["code"] == "AC_QUALITY_BELOW_THRESHOLD"


async def test_a_skip_lets_it_start_once_and_comes_back_spent():
    stored, _ = pol.with_skip(_policy(), "spec_quality", "UC-701", "El cliente aceptó estos criterios ayer.",
                              by="ana", at=AT, backend_type="freeform")
    board = json.dumps([US, UC, GOOD, BAD])
    out = await start_uc("ff", "UC-701", CTX, items_content=board, policy_content=json.dumps(stored))
    assert out["status"] == "in_progress"
    assert out["enforcement_warnings"][0]["outcome"] == "skipped"
    assert json.loads(out["policy_content"])["skips"] == []


async def test_a_lower_threshold_lets_half_the_criteria_fail():
    """AC-03: con umbral 0,5, una UC con la mitad de sus criterios bien arranca sin aviso."""
    board = json.dumps([US, UC, GOOD, BAD])
    out = await start_uc("ff", "UC-701", CTX, items_content=board,
                         policy_content=json.dumps(_policy(threshold=0.5)))
    assert out["status"] == "in_progress" and "enforcement_warnings" not in out


async def test_off_says_nothing_and_resuming_a_uc_is_not_checked():
    board = json.dumps([US, UC, GOOD, BAD])
    off = await start_uc("ff", "UC-701", CTX, items_content=board, policy_content=json.dumps(_policy("off")))
    assert off["status"] == "in_progress" and "enforcement_warnings" not in off
    # Retomar una UC en curso no la revalida (NFR de compatibilidad).
    resumed = await start_uc("ff", "UC-701", CTX, items_content=off["items_content"],
                             policy_content=json.dumps(_policy()))
    assert resumed["status"] == "in_progress" and "code" not in resumed


# ── import_spec y add_ac devuelven el gate (AC-04) ──────────────────


async def test_import_spec_returns_the_gate_of_each_uc_it_touches():
    spec = {"user_stories": [{"us_id": "US-08", "name": "Facturas", "use_cases": [
        {"uc_id": "UC-801", "name": "Emitir", "acceptance_criteria": ["La factura queda emitida con su número"]},
        {"uc_id": "UC-802", "name": "Anular", "acceptance_criteria": ["Va bien"]},
        {"uc_id": "UC-803", "name": "Vacía"},
    ]}]}
    out = await import_spec("ff", spec, CTX, items_content="[]")
    gate = {g["uc_id"]: g for g in out["spec_gate"]}
    assert gate["UC-801"]["meets_threshold"] and gate["UC-801"]["pass_rate"] == 1
    assert not gate["UC-802"]["meets_threshold"] and gate["UC-802"]["failed"][0]["ac_id"] == "AC-01"
    assert gate["UC-803"]["pass_rate"] == 0 and gate["UC-803"]["total"] == 0


async def test_add_ac_returns_the_gate_of_its_uc():
    board = json.dumps([US, UC, GOOD])
    out = await add_ac("ff", "UC-701", "Rápido", CTX, items_content=board)
    [gate] = out["spec_gate"]
    assert gate["uc_id"] == "UC-701" and gate["total"] == 2 and gate["pass_rate"] == 0.5
    assert [f["ac_id"] for f in gate["failed"]] == ["AC-02"]


# ── Native, contra Postgres ─────────────────────────────────────────

from tests._native_db import DSN, reachable  # noqa: E402

_PG_OK, _PG_SKIP_REASON = reachable()
pg = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


class _StatefulCtx:
    def __init__(self) -> None:
        self._state: dict[str, object] = {}

    async def get_state(self, key):
        return self._state.get(key)

    async def set_state(self, key, value) -> None:
        self._state[key] = value

    async def delete_state(self, key) -> None:
        self._state.pop(key, None)


async def _native_board(monkeypatch, tmp_path, *, criteria: dict[str, list[str]]):
    """Un proyecto native con US-01 y una UC por clave de ``criteria``, todas en backlog."""
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool
    from server.tools.spec_driven import get_session_backend, store_native_credentials

    monkeypatch.chdir(tmp_path)  # start_uc escribe el marcador local de UC activa
    monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
    pid = f"Acme/gate-{uuid.uuid4().hex[:8]}"
    dev, token = f"dev-gate-{uuid.uuid4().hex[:6]}", f"tok-gate-{uuid.uuid4().hex}"
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $1)", pid)
        await register_developer(conn, developer_id=dev, display_name=dev)
        await register_mcp_token(conn, developer_id=dev, token=token)
        await add_project_member(conn, project_id=pid, developer_id=dev, role="project_admin")
    ctx = _StatefulCtx()
    await store_native_credentials(ctx, pid, dev_token=token)
    backend = await get_session_backend(ctx)
    try:
        us = await backend.create_item(pid, "US-01 Pagos")
        for uc_id, texts in criteria.items():
            uc = await backend.create_item(pid, f"{uc_id} Caso {uc_id}", parent_id=us.id)
            await backend.update_item(pid, uc.id, state="backlog")
            if texts:
                await backend.create_acceptance_criteria(
                    pid, uc.id, [(f"AC-{i:02d}", t) for i, t in enumerate(texts, 1)]
                )
    finally:
        await backend.close()
    return pool, pid, dev, token, ctx


async def _cleanup(pool, pid, dev):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM audit_log WHERE project_id = $1", pid)
        await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
        await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev)


async def _to_block(pid: str, token: str) -> None:
    from server.tools.enforcement import set_enforcement_mode

    ask = await set_enforcement_mode(None, "spec_quality", "block", board_id=pid, dev_token=token)
    done = await set_enforcement_mode(None, "spec_quality", "block", board_id=pid, dev_token=token,
                                      confirm=ask["confirm"])
    assert done["success"], done


@pg
async def test_native_block_leaves_the_uc_unreserved_and_in_backlog_then_a_fix_passes(monkeypatch, tmp_path):
    """AC-01 y AC-03 en native; el bloqueo y su corrección quedan en la auditoría."""
    from server.tools.spec_mutations import update_ac

    pool, pid, dev, token, ctx = await _native_board(
        monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado con su recibo", "La app es buena"]}
    )
    try:
        # La UC ya estaba abierta al pasar a «block»: anterior a la regla, arranca en cualquier modo.
        await _to_block(pid, token)
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE use_cases SET name = 'UC-01 Caso reescrito' WHERE project_id = $1 AND id = 'UC-01'", pid
            )
        out = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert out["code"] == "AC_QUALITY_BELOW_THRESHOLD", out
        assert [f["ac_id"] for f in out["failed"]] == ["AC-02"] and "AC-02" in out["error"]
        async with pool.acquire() as conn:
            state = await conn.fetchval("SELECT state FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", pid)
            reserved = await conn.fetchval("SELECT count(*) FROM uc_reservations WHERE project_id = $1", pid)
            blocks = await conn.fetchval(
                "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'enforcement_block'", pid
            )
        assert (state, reserved, blocks) == ("backlog", 0, 1)

        fixed = await update_ac(pid, "UC-01", "AC-02", ctx, text="La pantalla de pago muestra el importe con IVA")
        assert "error" not in fixed, fixed
        started = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert started["status"] == "in_progress" and "enforcement_warnings" not in started
        async with pool.acquire() as conn:
            passes = await conn.fetchval(
                "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'enforcement_pass'", pid
            )
        assert passes == 1  # el paso que corrige el bloqueo de hace un momento
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_native_warn_starts_and_an_old_uc_starts_in_block(monkeypatch, tmp_path):
    """AC-06 en native: «warn» arranca y avisa; una UC anterior a la regla arranca en «block»."""
    pool, pid, dev, token, ctx = await _native_board(
        monkeypatch, tmp_path, criteria={"UC-01": [], "UC-02": ["Va bien"]}
    )
    try:
        warned = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert warned["status"] == "in_progress"
        assert warned["enforcement_warnings"][0]["pass_rate"] == 0
        await _to_block(pid, token)
        old = await start_uc(board_id=pid, uc_id="UC-02", ctx=ctx)
        assert old["status"] == "in_progress"
        assert old["enforcement_warnings"][0]["outcome"] == "predates_rule"
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_native_start_uc_with_50_criteria_answers_within_500_ms(monkeypatch, tmp_path):
    """NFR del PRD de EP-20: start_uc con las comprobaciones nuevas, 500 ms o menos en p95."""
    texts = [f"La factura {n} queda registrada con su número y su fecha" for n in range(50)]
    ucs = {f"UC-{n:02d}": texts for n in range(1, 11)}
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria=ucs)
    try:
        await _to_block(pid, token)
        took = []
        for uc_id in ucs:
            start = time.perf_counter()
            out = await start_uc(board_id=pid, uc_id=uc_id, ctx=ctx)
            took.append(time.perf_counter() - start)
            assert out["status"] == "in_progress", out
        took.sort()
        assert took[int(len(took) * 0.95) - 1] <= 0.5, took
    finally:
        await _cleanup(pool, pid, dev)
