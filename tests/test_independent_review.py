"""US-124 / UC-12402 — quien implementa no da el visto bueno a su propio trabajo.

- **AC-01**: la fusión automática exige un veredicto de aceptación de una persona o de un evaluador en
  un contexto distinto del que implementó (la regla; el hook merge-guard, en
  tests/hooks/merge-guard.test.mjs, con la misma regla: aquí la paridad).
- **AC-02**: el veredicto registra quién lo dio (agente con su identificador) y el tablero rechaza el
  del mismo agente que implementó la UC.
- **AC-03**: fuera de «agresivo», hace falta una persona; la aceptación de una persona vale ya en
  revisión (migración 0036) y se anula al volver a trabajo.
- **AC-04**: «warn»/«block» en merge-guard; aquí, el informe de impacto que mide la medida.

FreeForm por contenido (el MCP remoto) aquí; native contra Postgres al final (SKIP sin base).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.coordination import enforcement as pol
from server.review import (
    AGGRESSIVE,
    client_identity,
    independent_review_result,
    is_independent,
    same_context,
)
from server.tools.review import record_review_verdict
from server.tools.spec_driven import get_uc, move_uc, start_uc
from tests.test_spec_gate_start_uc import CTX, US, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "Cobrar con tarjeta", "state": "backlog",
      "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
AC = {"id": "ac1", "name": "[AC-01] El cobro queda registrado con su recibo", "state": "backlog", "labels": ["AC"],
      "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}
MAIN = {"client_session_id": "sess-1"}
EVALUATOR = {"client_session_id": "sess-1", "client_agent_id": "agent-9", "client_agent_type": "general-purpose"}


# ── La regla ────────────────────────────────────────────────────────


def test_identity_and_independence():
    implementer = {"developer_id": "ana", **client_identity("sess-1"), "at": "x"}
    assert same_context(implementer, client_identity("sess-1"))
    assert not same_context(implementer, client_identity("sess-1", "agent-9"))
    assert is_independent(implementer, client_identity("sess-1", "agent-9"))
    assert is_independent(implementer, client_identity("sess-2"))
    assert not is_independent(implementer, client_identity())  # sin el hook no cuenta
    assert is_independent(None, client_identity("sess-1", "agent-9"))  # implementador desconocido: subagente
    assert not is_independent(None, client_identity("sess-1"))
    assert client_identity("a b", "x" * 200, "Explore") == {"agent_type": "Explore"}


def test_ac01_ac03_what_lets_a_uc_merge():
    accepted = {"verdict": "accepted", "independent": True, "at": "2026-11-19T10:00:00Z"}
    returned = {"verdict": "returned", "reason": "falta el caso vacío", "at": "2026-11-19T11:00:00Z"}
    assert independent_review_result(human_acceptance={"by": "Ana"}, verdicts=[], level="equilibrado")["ok"]
    assert independent_review_result(human_acceptance=None, verdicts=[accepted], level=AGGRESSIVE)["ok"]
    assert independent_review_result(human_acceptance=None, verdicts=[accepted], level="",
                                      backend_type="freeform")["ok"]
    assert independent_review_result(human_acceptance=None, verdicts=[accepted],
                                     level="equilibrado")["reason_code"] == "no_person_acceptance"
    assert independent_review_result(human_acceptance=None, verdicts=[{**accepted, "independent": False}],
                                     level=AGGRESSIVE)["reason_code"] == "no_independent_verdict"
    back = independent_review_result(human_acceptance={"by": "Ana"}, verdicts=[accepted, returned], level=AGGRESSIVE)
    assert back == {"ok": False, "reason_code": "returned", "reason": "La UC fue devuelta: falta el caso vacío."}


@pytest.mark.skipif(shutil.which("node") is None, reason="sin node")
def test_ac01_merge_guard_applies_the_same_rule():
    acc = {"verdict": "accepted", "independent": True, "at": "2026-11-19T10:00:00Z"}
    ret = {"verdict": "returned", "reason": "x" * 12, "at": "2026-11-19T11:00:00Z"}
    cases = [
        {"human_acceptance": None, "verdicts": [acc], "level": AGGRESSIVE, "backend_type": "native"},
        {"human_acceptance": None, "verdicts": [acc], "level": "equilibrado", "backend_type": "native"},
        {"human_acceptance": None, "verdicts": [acc], "level": "", "backend_type": "freeform"},
        {"human_acceptance": {"by": "Ana"}, "verdicts": [], "level": "", "backend_type": "native"},
        {"human_acceptance": None, "verdicts": [acc, ret], "level": AGGRESSIVE, "backend_type": "native"},
        {"human_acceptance": None, "verdicts": [], "level": AGGRESSIVE, "backend_type": "native"},
    ]
    lib = ROOT / ".claude" / "hooks" / "lib" / "independent-review.mjs"
    js_cases = [{"humanAcceptance": c["human_acceptance"], "verdicts": c["verdicts"], "level": c["level"],
                 "backendType": c["backend_type"]} for c in cases]
    code = (f"import('{lib}').then(m => process.stdout.write(JSON.stringify("
            f"{json.dumps(js_cases)}.map(c => m.independentReview(c)))))")
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    for case, got in zip(cases, js):
        assert got == independent_review_result(**case)


def test_independent_review_is_active_and_measurable():
    assert pol.MEASURES["independent_review"].since == "6.42.0"
    assert "independent_review" not in pol.NOT_MEASURABLE
    review = {"uc_id": "UC-1", "state": "review", "human_accepted": False, "review_verdicts": []}
    assert "contexto distinto" in pol.IMPACT_EVALUATORS["independent_review"](review)
    assert pol.IMPACT_EVALUATORS["independent_review"]({**review, "human_accepted": True}) is None
    assert pol.IMPACT_EVALUATORS["independent_review"]({**review, "state": "in_progress"}) is None


# ── FreeForm por contenido ──────────────────────────────────────────


async def _in_review(identity: dict) -> str:
    started = await start_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, AC]), **identity)
    moved = await move_uc("ff", "UC-701", "review", CTX, items_content=started["items_content"])
    return moved["items_content"]


async def test_ac02_the_implementer_is_kept_and_the_same_context_is_rejected():
    board = await _in_review(MAIN)
    detail = await get_uc("ff", "UC-701", CTX, items_content=board)
    assert detail["implementer"]["session_id"] == "sess-1" and "agent_id" not in detail["implementer"]
    same = await record_review_verdict("ff", "UC-701", "accepted", CTX, items_content=board, **MAIN)
    assert same["code"] == "SAME_AGENT_VERDICT"


async def test_ac02_an_isolated_evaluator_is_recorded_with_its_identity():
    board = await _in_review(MAIN)
    out = await record_review_verdict("ff", "UC-701", "accepted", CTX, items_content=board, **EVALUATOR)
    assert out["success"] and out["independent"] is True
    assert out["by"] == {"kind": "agent", "developer_id": None, "session_id": "sess-1", "agent_id": "agent-9",
                         "agent_type": "general-purpose"}
    detail = await get_uc("ff", "UC-701", CTX, items_content=out["items_content"])
    [verdict] = detail["review_verdicts"]
    assert verdict["verdict"] == "accepted" and verdict["agent_id"] == "agent-9" and verdict["independent"]


async def test_a_verdict_without_the_hook_is_kept_but_not_independent():
    board = await _in_review(MAIN)
    out = await record_review_verdict("ff", "UC-701", "accepted", CTX, items_content=board)
    assert out["success"] and out["independent"] is False and "note" in out


async def test_returning_needs_a_reason_and_the_uc_must_be_in_review():
    board = await _in_review(MAIN)
    no_reason = await record_review_verdict("ff", "UC-701", "returned", CTX, items_content=board, **EVALUATOR)
    assert no_reason["code"] == "INVALID_REASON"
    secret = await record_review_verdict("ff", "UC-701", "returned", CTX, reason="usa la password: hunter2 en prod",
                                         items_content=board, **EVALUATOR)
    assert secret["code"] == "SENSITIVE_DATA"
    bad = await record_review_verdict("ff", "UC-701", "maybe", CTX, items_content=board, **EVALUATOR)
    assert bad["code"] == "INVALID_VERDICT"
    backlog = await record_review_verdict("ff", "UC-701", "accepted", CTX, items_content=json.dumps([US, UC, AC]),
                                          **EVALUATOR)
    assert backlog["code"] == "UC_NOT_IN_REVIEW"


# ── Native ──────────────────────────────────────────────────────────


@pg
async def test_native_verdicts_the_implementer_and_the_acceptance_in_review(monkeypatch, tmp_path):
    """AC-02 y AC-03 en native: tabla 0036, implementador, rechazo y aceptación humana en revisión."""
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"]})
    try:
        assert (await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx, **MAIN))["status"] == "in_progress"
        async with pool.acquire() as conn:
            implementer = json.loads(await conn.fetchval(
                "SELECT meta->'implementer' FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", pid))
        assert implementer["developer_id"] == dev and implementer["session_id"] == "sess-1"
        await move_uc(board_id=pid, uc_id="UC-01", target="review", ctx=ctx)

        same = await record_review_verdict(pid, "UC-01", "accepted", ctx, **MAIN)
        assert same["code"] == "SAME_AGENT_VERDICT"
        ok = await record_review_verdict(pid, "UC-01", "accepted", ctx, **EVALUATOR)
        assert ok["success"] and ok["independent"] and ok["by"]["developer_id"] == dev
        detail = await get_uc(pid, "UC-01", ctx)
        assert detail["review_verdicts"][-1]["agent_id"] == "agent-9"

        report = await pol_report(pid, token)
        assert all(u["uc_id"] != "UC-01" for u in report["measures"]["independent_review"]["ucs"])

        # AC-03: una persona acepta en revisión (lo escribe el panel); vale al pasar a hecha y se
        # anula al volver a trabajo.
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO uc_acceptances (project_id, uc_id, accepted_by_developer_id) VALUES ($1, 'UC-01', $2)",
                pid, dev)
            await conn.execute("UPDATE use_cases SET state = 'done' WHERE project_id = $1 AND id = 'UC-01'", pid)
            kept = await conn.fetchval("SELECT count(*) FROM uc_acceptances WHERE project_id = $1", pid)
            await conn.execute("UPDATE use_cases SET state = 'in_progress' WHERE project_id = $1 AND id = 'UC-01'", pid)
            voided = await conn.fetchval("SELECT count(*) FROM uc_acceptances WHERE project_id = $1", pid)
        assert kept == 1 and voided == 0
    finally:
        await _cleanup(pool, pid, dev)


async def pol_report(pid: str, token: str) -> dict:
    from server.tools.enforcement import get_enforcement_impact

    out = await get_enforcement_impact(None, board_id=pid, dev_token=token)
    assert out["success"], out
    return out["report"]


def test_the_migration_has_its_twin():
    local = ROOT / "server" / "db" / "migrations" / "0036_review_verdicts.sql"
    twin = ROOT / "supabase" / "migrations" / "20261118000036_review_verdicts.sql"
    assert local.read_bytes() == twin.read_bytes()
