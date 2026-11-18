"""US-124 / UC-12401 — complete_uc exige cada criterio con evidencia que pasa.

- **AC-01**: con la medida en «block», ``complete_uc`` devuelve ``AC_WITHOUT_PASSING_EVIDENCE`` si
  algún criterio no está hecho con un recibo que pasa, y deja la UC en su estado.
- **AC-02**: el error muestra cada criterio que falta y su motivo: sin marcar, sin evidencia o con
  evidencia que falla.
- **AC-03**: una prueba de aceptación que falla no llega a la fusión automática (el hook merge-guard,
  con la misma regla: aquí la paridad; el hook, en tests/hooks/merge-guard.test.mjs).
- **AC-04**: un criterio que se comprueba a mano queda demostrado con un recibo escrito y quien lo
  marcó.
- **AC-05**: en FreeForm el veredicto y los recibos de cada criterio quedan en items.json y
  complete_uc aplica la misma regla que en native.
- **AC-06**: en «warn» cierra y avisa; en «block» no cierra; una UC empezada antes de pasar la medida
  a «block» cierra con aviso.

FreeForm por contenido (el MCP remoto) aquí; native contra Postgres al final (SKIP sin base).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.coordination import enforcement as pol
from server.spec_backend import ChecklistItemDTO, CommentDTO
from server.tools.enforcement import criteria_with_receipts
from server.tools.spec_driven import complete_uc, get_uc, mark_ac, mark_ac_batch
from server.tools.spec_mutations import update_ac
from tests.test_spec_gate_start_uc import AT, CTX, US, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "Cobrar con tarjeta", "state": "review",
      "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
PASS = {"type": "test", "label": "tests/test_cobro.py: cobra", "by": "ana", "at": AT, "passed": True}
FAIL = {**PASS, "passed": False}


def _ac(n: int, *, done: bool, evidence: list | None = None, verdict: dict | None = None) -> dict:
    meta: dict = {"ac_id": f"AC-0{n}", "spec_rules": 3}
    if evidence is not None:
        meta["evidence"] = evidence
    if verdict is not None:
        meta["verdict"] = verdict
    return {"id": f"ac{n}", "name": f"[AC-0{n}] El cobro queda registrado con el recibo {n}",
            "state": "done" if done else "backlog", "labels": ["AC"], "parent_id": "uc701", "meta": meta}


GOOD = _ac(1, done=True, evidence=[PASS], verdict={"passed": True, "by": "ana", "at": AT})
NOT_DONE = _ac(2, done=False)
NO_EVIDENCE = _ac(3, done=True, evidence=[], verdict={"passed": True, "by": None, "at": AT})
FAILING = _ac(4, done=True, evidence=[FAIL], verdict={"passed": True, "by": "ana", "at": AT})


def _policy(mode: str = "block", *, open_ucs: dict | None = None) -> str:
    stored, _ = pol.with_mode(None, "closing_evidence", mode, by="ana", at=AT, backend_type="freeform",
                              open_ucs=open_ucs or {})
    return json.dumps(stored)


def _state(items_content: str, uc_id: str = "UC-701") -> str:
    return next(i["state"] for i in json.loads(items_content) if i.get("meta", {}).get("uc_id") == uc_id)


# ── La regla ────────────────────────────────────────────────────────


def _rule_acs(*items: dict) -> list[dict]:
    return [{"ac_id": i["meta"]["ac_id"], "done": i["state"] == "done", "evidence": i["meta"].get("evidence")}
            for i in items]


def test_ac02_each_missing_criterion_with_its_reason():
    result = pol.closing_evidence_result({"acs": _rule_acs(GOOD, NOT_DONE, NO_EVIDENCE, FAILING)})
    assert result["total"] == 4 and not result["ok"]
    assert result["missing"] == [
        {"ac_id": "AC-02", "reason": "not_done"},
        {"ac_id": "AC-03", "reason": "no_evidence"},
        {"ac_id": "AC-04", "reason": "failing_evidence"},
    ]
    assert pol.closing_evidence_reason(result) == (
        "3 de 4 criterios sin demostrar: AC-02 (sin marcar), AC-03 (sin evidencia), AC-04 (con evidencia que falla)."
    )


def test_a_uc_without_criteria_has_nothing_demonstrated_and_unknown_evidence_counts_done():
    assert pol.closing_evidence_result({"acs": []})["missing"] == [{"ac_id": None, "reason": "no_criteria"}]
    unknown = pol.closing_evidence_result({"acs": [{"ac_id": "AC-01", "done": True, "evidence": None}]})
    assert unknown["ok"]


def test_a_later_passing_receipt_demonstrates_a_criterion_that_failed_before():
    redone = _rule_acs(_ac(1, done=True, evidence=[FAIL, PASS]))
    assert pol.closing_evidence_result({"acs": redone})["ok"]


def test_ac06_started_before_the_block():
    stored = json.loads(_policy("block"))
    since = stored["measures"]["closing_evidence"]["block_since"]
    assert since == AT
    assert pol.started_before_block(stored, "closing_evidence", "2026-11-17T10:00:00+00:00")
    assert not pol.started_before_block(stored, "closing_evidence", "2026-11-19T10:00:00+00:00")
    assert not pol.started_before_block(stored, "closing_evidence", None)
    warn = json.loads(_policy("warn"))
    assert not pol.started_before_block(warn, "closing_evidence", "2026-11-17T10:00:00+00:00")


def test_closing_evidence_is_active_from_this_version():
    assert pol.MEASURES["closing_evidence"].since == "6.41.0"
    assert pol.effective_policy(None, backend_type="native")["measures"]["closing_evidence"]["active"] is True


@pytest.mark.skipif(shutil.which("node") is None, reason="sin node")
def test_ac03_the_merge_hook_applies_the_same_rule():
    """Paridad: lib/closing-evidence.mjs da los mismos criterios y el mismo motivo que el servidor."""
    cases = [
        _rule_acs(GOOD, NOT_DONE, NO_EVIDENCE, FAILING),
        _rule_acs(GOOD),
        [],
        [{"ac_id": "AC-01", "done": True, "evidence": None}],
        _rule_acs(_ac(1, done=True, evidence=[FAIL, PASS])),
    ]
    lib = ROOT / ".claude" / "hooks" / "lib" / "closing-evidence.mjs"
    code = (
        f"import('{lib}').then(m => process.stdout.write(JSON.stringify({json.dumps(cases)}.map(acs => "
        "{ const r = m.closingEvidence(acs); return { r, reason: m.closingReason(r) }; }))))"
    )
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    for case, got in zip(cases, js):
        expected = pol.closing_evidence_result({"acs": case})
        assert got["r"] == expected
        assert got["reason"] == pol.closing_evidence_reason(expected)


# ── complete_uc con FreeForm por contenido ──────────────────────────


async def test_ac01_ac02_block_names_each_criterion_and_moves_nothing():
    board = json.dumps([US, UC, GOOD, NOT_DONE, NO_EVIDENCE, FAILING])
    out = await complete_uc("ff", "UC-701", CTX, items_content=board, policy_content=_policy("block"))
    assert out["success"] is False and out["code"] == "AC_WITHOUT_PASSING_EVIDENCE"
    assert out["measure"] == "closing_evidence" and out["uc_id"] == "UC-701"
    assert [(m["ac_id"], m["reason"]) for m in out["missing"]] == [
        ("AC-02", "not_done"), ("AC-03", "no_evidence"), ("AC-04", "failing_evidence")]
    assert "AC-03 (sin evidencia)" in out["error"] and "mark_ac" in out["how_to_continue"]
    assert "items_content" not in out  # nada se movió: no hay tablero que guardar
    line = json.loads(out["event_line"])
    assert line["measure"] == "closing_evidence" and line["outcome"] == "blocked"


async def test_ac06_warn_closes_and_lists_what_is_missing():
    board = json.dumps([US, UC, GOOD, NOT_DONE])
    out = await complete_uc("ff", "UC-701", CTX, items_content=board, policy_content=_policy("warn"))
    assert _state(out["items_content"]) == "done"
    [warning] = out["enforcement_warnings"]
    assert warning["measure"] == "closing_evidence" and warning["outcome"] == "warned"
    assert [m["ac_id"] for m in warning["missing"]] == ["AC-02"]


async def test_off_and_a_demonstrated_uc_close_without_warnings():
    off = await complete_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, NOT_DONE]),
                            policy_content=_policy("off"))
    assert _state(off["items_content"]) == "done" and "enforcement_warnings" not in off
    ok = await complete_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, GOOD]),
                           policy_content=_policy("block"))
    assert _state(ok["items_content"]) == "done" and "enforcement_warnings" not in ok


async def test_ac06_a_uc_open_before_the_block_closes_with_a_warning():
    """FreeForm no guarda la fecha de inicio: cuenta la huella de las UC abiertas al pasar a «block»."""
    uc = {"uc_id": "UC-701", "name": UC["name"], "description": UC["description"], "state": "review",
          "acs": [{"ac_id": "AC-02", "text": NOT_DONE["name"][8:]}]}
    policy = _policy("block", open_ucs={"UC-701": pol.uc_fingerprint(uc)})
    out = await complete_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, NOT_DONE]), policy_content=policy)
    assert _state(out["items_content"]) == "done"
    assert out["enforcement_warnings"][0]["outcome"] == "predates_rule"


async def test_a_skip_closes_once():
    stored = json.loads(_policy("block"))
    stored, _ = pol.with_skip(stored, "closing_evidence", "UC-701", "Se comprobó a mano con el cliente en la demo",
                              by="ana", at=AT, backend_type="freeform")
    out = await complete_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, NOT_DONE]),
                            policy_content=json.dumps(stored))
    assert _state(out["items_content"]) == "done"
    assert out["enforcement_warnings"][0]["outcome"] == "skipped"
    assert json.loads(out["policy_content"])["skips"] == []  # gastado: el cliente lo guarda


# ── AC-04 y AC-05: FreeForm guarda veredicto y recibos ──────────────


def _ac_meta(items_content: str, ac_id: str) -> dict:
    return next(i["meta"] for i in json.loads(items_content)
                if "AC" in i.get("labels", []) and i.get("meta", {}).get("ac_id") == ac_id)


async def test_ac04_ac05_freeform_keeps_the_verdict_the_receipt_and_who_marked_it():
    board = json.dumps([US, UC, NOT_DONE])
    note = "Comprobado a mano en el iPhone: el recibo llega por correo"
    out = await mark_ac("ff", "UC-701", "AC-02", True, CTX, evidence=note, items_content=board,
                        marked_by="  Jesús   Pérez ")
    meta = _ac_meta(out["items_content"], "AC-02")
    assert meta["verdict"]["passed"] is True and meta["verdict"]["by"] == "Jesús Pérez"
    [receipt] = meta["evidence"]
    assert receipt["label"] == note and receipt["by"] == "Jesús Pérez" and receipt["passed"] is True
    detail = await get_uc("ff", "UC-701", CTX, items_content=out["items_content"])
    [ac] = detail["acceptance_criteria"]
    assert ac["evidence"][0]["label"] == note and ac["verified"]["by"] == "Jesús Pérez"
    closed = await complete_uc("ff", "UC-701", CTX, items_content=out["items_content"],
                               policy_content=_policy("block"))
    assert _state(closed["items_content"]) == "done"


async def test_ac05_a_batch_keeps_every_receipt_and_a_failure_stops_the_close():
    board = json.dumps([US, UC, _ac(1, done=False), _ac(2, done=False)])
    out = await mark_ac_batch("ff", "UC-701", [
        {"ac_id": "AC-01", "passed": True, "evidence": {"type": "test", "label": "cobra"}},
        {"ac_id": "AC-02", "passed": False, "evidence": {"type": "test", "label": "devuelve"}},
    ], CTX, items_content=board, marked_by="ana")
    assert _ac_meta(out["items_content"], "AC-02")["evidence"][0]["passed"] is False
    blocked = await complete_uc("ff", "UC-701", CTX, items_content=out["items_content"],
                                policy_content=_policy("block"))
    assert [(m["ac_id"], m["reason"]) for m in blocked["missing"]] == [("AC-02", "not_done")]


async def test_rewriting_a_done_criterion_leaves_its_verdict_failing_like_native():
    out = await update_ac("ff", "UC-701", "AC-01", CTX, text="El cobro queda registrado con su recibo y la fecha",
                          items_content=json.dumps([US, UC, GOOD]))
    meta = _ac_meta(out["items_content"], "AC-01")
    assert meta["verdict"]["passed"] is False and meta["verdict"]["source"] == "text_changed"


async def test_receipts_from_comments_count_for_backends_without_a_store():
    """Trello, Plane y FreeForm anterior: el recibo se reconstruye de los comentarios de la UC."""

    class _Old:
        async def get_acceptance_criteria(self, board_id, uc_item_id):
            return [ChecklistItemDTO(id="AC-01", text="El cobro queda registrado", done=True)]

        async def get_comments(self, board_id, uc_item_id):
            return [CommentDTO(id="c1", text="AC-01: PASSED — cobra [2026-11-18 10:00 UTC]")]

    [ac] = await criteria_with_receipts(_Old(), "b", SimpleNamespace(id="uc"))
    assert ac["evidence"][0]["passed"] is True and pol.closing_evidence_result({"acs": [ac]})["ok"]


def test_the_impact_report_uses_the_same_rule():
    uc = {"uc_id": "UC-701", "state": "review", "acs": _rule_acs(GOOD, FAILING)}
    assert pol.IMPACT_EVALUATORS["closing_evidence"](uc) == "1 de 2 criterios sin demostrar: AC-04 (con evidencia que falla)."
    assert pol.IMPACT_EVALUATORS["closing_evidence"]({**uc, "state": "in_progress"}) is None


# ── Native ──────────────────────────────────────────────────────────


@pg
async def test_native_block_keeps_the_uc_in_review_with_its_reservation_then_closes(monkeypatch, tmp_path):
    """AC-01 y AC-06 en native: bloqueo con la UC y la reserva intactas; corregida, cierra."""
    from server.tools.enforcement import set_enforcement_mode
    from server.tools.spec_driven import move_uc, start_uc

    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"]})
    try:
        ask = await set_enforcement_mode(None, "closing_evidence", "block", board_id=pid, dev_token=token)
        done = await set_enforcement_mode(None, "closing_evidence", "block", board_id=pid, dev_token=token,
                                          confirm=ask["confirm"])
        assert done["success"], done
        assert (await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx))["status"] == "in_progress"
        await move_uc(board_id=pid, uc_id="UC-01", target="review", ctx=ctx)

        blocked = await complete_uc(pid, "UC-01", ctx)
        assert blocked["code"] == "AC_WITHOUT_PASSING_EVIDENCE", blocked
        assert [(m["ac_id"], m["reason"]) for m in blocked["missing"]] == [("AC-01", "not_done")]
        async with pool.acquire() as conn:
            state = await conn.fetchval("SELECT state FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", pid)
            reserved = await conn.fetchval("SELECT count(*) FROM uc_reservations WHERE project_id = $1", pid)
            blocks = await conn.fetchval(
                "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'enforcement_block'", pid)
        assert state == "review" and reserved == 1 and blocks == 1

        await mark_ac(pid, "UC-01", "AC-01", True, ctx, evidence={"type": "test", "label": "cobra"})
        closed = await complete_uc(pid, "UC-01", ctx)
        assert "code" not in closed and "enforcement_warnings" not in closed, closed
        async with pool.acquire() as conn:
            passes = await conn.fetchval(
                "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'enforcement_pass'", pid)
        assert passes == 1
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_native_a_uc_started_before_the_block_closes_with_a_warning(monkeypatch, tmp_path):
    from server.tools.enforcement import set_enforcement_mode
    from server.tools.spec_driven import move_uc, start_uc

    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"]})
    try:
        assert (await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx))["status"] == "in_progress"
        await move_uc(board_id=pid, uc_id="UC-01", target="review", ctx=ctx)
        async with pool.acquire() as conn:  # empezó hace un día: antes de la regla
            await conn.execute(
                "UPDATE use_cases SET started_at = now() - interval '1 day', name = 'UC-01 Caso reescrito' "
                "WHERE project_id = $1 AND id = 'UC-01'", pid)
        ask = await set_enforcement_mode(None, "closing_evidence", "block", board_id=pid, dev_token=token)
        await set_enforcement_mode(None, "closing_evidence", "block", board_id=pid, dev_token=token, confirm=ask["confirm"])
        out = await complete_uc(pid, "UC-01", ctx)
        assert out["enforcement_warnings"][0]["outcome"] == "predates_rule", out
        async with pool.acquire() as conn:
            state = await conn.fetchval("SELECT state FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", pid)
        assert state == "done"
    finally:
        await _cleanup(pool, pid, dev)
