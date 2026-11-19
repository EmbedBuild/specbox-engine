"""UC-12502 (US-125) — una persona aprueba los criterios antes de implementar.

- AC-01: approve_criteria registra la aprobación con quién y cuándo.
- AC-02: start_uc no arranca una UC sin criterios aprobados (AC_NOT_APPROVED) con la medida en «block».
- AC-03: cambiar el texto de un criterio aprobado, añadir uno o retirarlo deja la UC sin aprobar.
- AC-04: find_next_uc no propone UC sin aprobar en «block» salvo con include_unapproved; en «warn»,
  propone primero las aprobadas y avisa en las demás.
- AC-05: /prd pide la aprobación (texto de la skill y clave de autopilot «ask» en todos los niveles).
- AC-06: en «warn» start_uc arranca con aviso; en «block», no; una UC anterior a la regla cuenta como
  «aprobada por migración».
- AC-07: en FreeForm la aprobación queda en items.json con quién y cuándo, y start_uc aplica la misma regla.
"""

from __future__ import annotations

import json
from pathlib import Path

from server.approval import APPROVED_STATES, approval_state, criteria_fingerprint, criteria_snapshot
from server.coordination import enforcement as pol
from server.tools.approval import approve_criteria
from server.tools.spec_driven import find_next_uc, get_uc, start_uc
from server.tools.spec_mutations import add_ac, delete_ac, update_ac
from tests.test_spec_gate_start_uc import AT, CTX, US, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "Cobrar con tarjeta", "state": "backlog",
      "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
UC2 = {"id": "uc702", "name": "UC-702: Devolver", "description": "Devolver un cobro", "state": "backlog",
       "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": "UC-702", "us_id": "US-07"}}
AC1 = {"id": "ac1", "name": "[AC-01] El cobro queda registrado con su recibo", "state": "backlog",
       "labels": ["AC"], "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}
AC2 = {"id": "ac2", "name": "[AC-02] El recibo incluye el importe y la fecha", "state": "backlog",
       "labels": ["AC"], "parent_id": "uc701", "meta": {"ac_id": "AC-02"}}
AC3 = {"id": "ac3", "name": "[AC-01] La devolución queda registrada con su motivo", "state": "backlog",
       "labels": ["AC"], "parent_id": "uc702", "meta": {"ac_id": "AC-01"}}
REASON = "La cubre otra historia del tablero"


def _board(*extra: dict) -> str:
    return json.dumps([US, UC, AC1, AC2, *extra])


def _policy(mode: str = "block", open_ucs: dict | None = None) -> str:
    stored, _ = pol.with_mode(None, "ac_approval", mode, by="ana", at=AT, backend_type="freeform",
                              open_ucs=open_ucs or {})
    return json.dumps(stored)


# ── La regla, sin tablero ───────────────────────────────────────────


def test_the_fingerprint_follows_ids_and_texts_only():
    acs = [{"id": "AC-02", "text": "Dos"}, {"id": "AC-01", "text": "Uno  queda"}]
    same = [{"ac_id": "AC-01", "text": "Uno queda"}, {"id": "AC-02", "text": "Dos"}]
    assert criteria_fingerprint(acs) == criteria_fingerprint(same)  # orden y espacios no cuentan
    assert criteria_snapshot(acs) == [{"id": "AC-01", "text": "Uno queda"}, {"id": "AC-02", "text": "Dos"}]
    changed = [{"id": "AC-01", "text": "Uno cambia"}, {"id": "AC-02", "text": "Dos"}]
    added = [*acs, {"id": "AC-03", "text": "Tres"}]
    retired = acs[:1]
    fps = {criteria_fingerprint(x) for x in (acs, changed, added, retired)}
    assert len(fps) == 4


def test_the_states_of_an_approval():
    fp = criteria_fingerprint([{"id": "AC-01", "text": "Uno"}])
    latest = {"fingerprint": fp, "by": "ana", "at": AT}
    assert approval_state(latest, fp)["state"] == "approved"
    assert approval_state(latest, "0" * 32)["state"] == "stale"
    assert approval_state(None, fp)["state"] == "none"
    migrated = approval_state(None, fp, predates=True)
    assert migrated == {"state": "migration", "source": "migration", "label": "aprobada por migración"}
    assert APPROVED_STATES == {"approved", "migration"}


def test_ac_approval_is_active_and_measurable():
    assert pol.MEASURES["ac_approval"].since == "6.44.0"
    assert "ac_approval" not in pol.NOT_MEASURABLE and "ac_approval" in pol.IMPACT_EVALUATORS


def test_the_autopilot_never_approves_criteria_and_prd_asks():
    """AC-05: la clave criteria_approval pregunta en los cuatro niveles; /prd y /implement lo dicen."""
    from server.app_docs.autopilot import DECISION_KEYS

    tiers = DECISION_KEYS["criteria_approval"]["tiers"]
    assert set(tiers.values()) == {"ask"} and len(tiers) == 4
    mjs = (ROOT / ".claude/hooks/lib/autopilot.mjs").read_text()
    assert "criteria_approval:" in mjs and "agresivo: 'ask'" in mjs.split("criteria_approval:")[1].split("\n")[0]
    prd = (ROOT / ".claude/skills/prd/SKILL.md").read_text()
    assert "approve_criteria(" in prd and "criteria_approval" in prd
    assert "AC_NOT_APPROVED" in (ROOT / ".claude/skills/implement/SKILL.md").read_text()


# ── FreeForm (AC-01, AC-03, AC-07) ──────────────────────────────────


async def test_freeform_approval_is_kept_with_who_and_when_and_any_change_voids_it():
    out = await approve_criteria("ff", CTX, uc_ids=["UC-701"], approved_by="Ana", client_session_id="sess-1",
                                 items_content=_board())
    [ok] = out["approved"]
    assert ok["uc_id"] == "UC-701" and ok["criteria"] == 2 and ok["by"] == "Ana" and ok["at"]
    uc_item = next(i for i in json.loads(out["items_content"]) if i["id"] == "uc701")
    stored = uc_item["meta"]["criteria_approval"]
    assert stored["by"] == "Ana" and stored["session_id"] == "sess-1" and len(stored["criteria"]) == 2
    board = out["items_content"]
    assert (await get_uc("ff", "UC-701", CTX, items_content=board))["criteria_approval"]["state"] == "approved"

    # AC-03: reescribir, añadir y retirar dejan la UC sin aprobar; cambiar la verificación, no.
    verif = await update_ac("ff", "UC-701", "AC-01", CTX, verification="automated_test", items_content=board)
    assert (await get_uc("ff", "UC-701", CTX, items_content=verif["items_content"]))["criteria_approval"]["state"] == "approved"
    for change in (
        update_ac("ff", "UC-701", "AC-01", CTX, text="El cobro queda registrado con su recibo y su hora", items_content=board),
        add_ac("ff", "UC-701", "El cobro duplicado se rechaza", CTX, items_content=board),
        delete_ac("ff", "UC-701", "AC-02", CTX, reason=REASON, items_content=board),
    ):
        changed = await change
        state = (await get_uc("ff", "UC-701", CTX, items_content=changed["items_content"]))["criteria_approval"]
        assert state["state"] == "stale" and state["previous_by"] == "Ana"


async def test_a_subagent_cannot_approve_and_a_uc_needs_criteria():
    sub = await approve_criteria("ff", CTX, uc_ids=["UC-701"], client_session_id="sess-1",
                                 client_agent_id="agent-9", items_content=_board())
    assert sub["code"] == "SUBAGENT_CANNOT_APPROVE"
    empty = await approve_criteria("ff", CTX, uc_ids=["UC-702"], items_content=_board(UC2))
    assert empty["success"] is False and empty["errors"][0]["code"] == "NO_CRITERIA"
    nothing = await approve_criteria("ff", CTX, items_content=_board())
    assert nothing["code"] == "NOTHING_TO_APPROVE"
    story = await approve_criteria("ff", CTX, us_id="US-07", items_content=_board(UC2, AC3))
    assert sorted(a["uc_id"] for a in story["approved"]) == ["UC-701", "UC-702"]


async def test_freeform_start_uc_applies_the_same_rule():
    """AC-02, AC-06, AC-07."""
    blocked = await start_uc("ff", "UC-701", CTX, items_content=_board(), policy_content=_policy("block"))
    assert blocked["code"] == "AC_NOT_APPROVED"
    warned = await start_uc("ff", "UC-701", CTX, items_content=_board(), policy_content=_policy("warn"))
    assert warned["status"] == "in_progress"
    assert [w["measure"] for w in warned["enforcement_warnings"]] == ["ac_approval"]
    approved = await approve_criteria("ff", CTX, uc_ids=["UC-701"], approved_by="Ana", items_content=_board())
    ok = await start_uc("ff", "UC-701", CTX, items_content=approved["items_content"],
                        policy_content=_policy("block"))
    assert ok["status"] == "in_progress" and ok["criteria_approval"]["state"] == "approved"


async def test_a_uc_that_predates_the_rule_counts_as_approved_by_migration():
    """AC-06."""
    from server.tools.enforcement import _freeform_open_ucs

    board = _board()
    uc = next(u for u in await _freeform_open_ucs(board) if u["uc_id"] == "UC-701")
    out = await start_uc("ff", "UC-701", CTX, items_content=board,
                         policy_content=_policy("block", pol.open_uc_fingerprints([uc])))
    assert out["status"] == "in_progress"
    assert out["criteria_approval"] == {"state": "migration", "source": "migration", "label": "aprobada por migración"}


async def test_find_next_uc_filters_in_block_and_prefers_approved_in_warn():
    """AC-04."""
    board = _board(UC2, AC3)
    blocked = await find_next_uc("ff", CTX, items_content=board, policy_content=_policy("block"))
    assert blocked["code"] == "NO_APPROVED_UC" and set(blocked["unapproved_ucs"]) == {"UC-701", "UC-702"}
    forced = await find_next_uc("ff", CTX, items_content=board, policy_content=_policy("block"), include_unapproved=True)
    assert forced["uc_id"] in {"UC-701", "UC-702"}

    approved = await approve_criteria("ff", CTX, uc_ids=["UC-702"], items_content=board)
    for mode in ("block", "warn"):
        picked = await find_next_uc("ff", CTX, items_content=approved["items_content"], policy_content=_policy(mode))
        assert picked["uc_id"] == "UC-702" and picked["criteria_approval"]["state"] == "approved"

    warned = await find_next_uc("ff", CTX, items_content=board, policy_content=_policy("warn"))
    assert warned["uc_id"] in {"UC-701", "UC-702"}
    assert [w["measure"] for w in warned["enforcement_warnings"]] == ["ac_approval"]


# ── Native (Postgres) ───────────────────────────────────────────────


async def _to_block(pid: str, token: str) -> None:
    from server.tools.enforcement import set_enforcement_mode

    ask = await set_enforcement_mode(None, "ac_approval", "block", board_id=pid, dev_token=token)
    done = await set_enforcement_mode(None, "ac_approval", "block", board_id=pid, dev_token=token,
                                      confirm=ask["confirm"])
    assert done["success"], done


@pg
async def test_native_approval_table_gate_and_impact(monkeypatch, tmp_path):
    pool, pid, dev, token, ctx = await _native_board(
        monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado con su recibo"]})
    try:
        # Anterior a la regla: arranca como «aprobada por migración».
        await _to_block(pid, token)
        old = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert old["status"] == "in_progress" and old["criteria_approval"]["state"] == "migration"

        # Una UC nueva tras pasar a «block» no arranca sin aprobación (AC-02).
        backend_uc = await add_ac(pid, "UC-01", "El recibo incluye el importe y la fecha", ctx)
        assert backend_uc["ac_id"] == "AC-02"
        from server.tools.spec_driven import get_session_backend

        backend = await get_session_backend(ctx)
        try:
            us = await backend.find_item_by_field(pid, "us_id", "US-01")
            uc = await backend.create_item(pid, "UC-02 Devolver", parent_id=us.id if us else None)
            await backend.update_item(pid, uc.id, state="backlog")
            await backend.create_acceptance_criteria(pid, uc.id, [("AC-01", "La devolución queda registrada")])
        finally:
            await backend.close()
        blocked = await start_uc(board_id=pid, uc_id="UC-02", ctx=ctx)
        assert blocked["code"] == "AC_NOT_APPROVED"

        out = await approve_criteria(pid, ctx, uc_ids=["UC-02"], approved_by="no-cuenta", client_session_id="sess-1")
        [ok] = out["approved"]
        assert ok["by"] == dev  # native: quién sale de la sesión
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT approved_by, session_id, jsonb_array_length(criteria) AS n FROM uc_criteria_approvals "
                "WHERE project_id = $1 AND uc_id = 'UC-02'", pid)
        assert row["approved_by"] == dev and row["session_id"] == "sess-1" and row["n"] == 1

        report = await _impact(pid, token)
        assert all(u["uc_id"] != "UC-02" for u in report["measures"]["ac_approval"]["ucs"])
        await update_ac(pid, "UC-02", "AC-01", ctx, text="La devolución queda registrada con su motivo")
        assert (await get_uc(pid, "UC-02", ctx))["criteria_approval"]["state"] == "stale"
        report = await _impact(pid, token)
        assert any(u["uc_id"] == "UC-02" for u in report["measures"]["ac_approval"]["ucs"])
        assert (await start_uc(board_id=pid, uc_id="UC-02", ctx=ctx))["code"] == "AC_NOT_APPROVED"
    finally:
        await _cleanup(pool, pid, dev)


async def _impact(pid: str, token: str) -> dict:
    from server.tools.enforcement import get_enforcement_impact

    out = await get_enforcement_impact(None, board_id=pid, dev_token=token)
    return out["report"]


def test_the_migration_has_its_twin():
    src = ROOT / "server/db/migrations/0040_uc_criteria_approvals.sql"
    [twin] = list((ROOT / "supabase/migrations").glob("*_uc_criteria_approvals.sql"))
    assert src.read_bytes() == twin.read_bytes()


# ── Revisión aislada de UC-12502 ────────────────────────────────────


async def test_find_next_uc_looks_past_25_candidates():
    """Sin tope: con 30 UC y solo la última aprobada, «block» la propone."""
    items = [US]
    for n in range(1, 31):
        uc_id = f"UC-7{n:02d}"
        items.append({"id": f"uc{n}", "name": f"{uc_id}: Caso {n}", "description": "", "state": "backlog",
                      "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": uc_id, "us_id": "US-07"}})
        items.append({"id": f"ac{n}", "name": f"[AC-01] El caso {n} queda registrado", "state": "backlog",
                      "labels": ["AC"], "parent_id": f"uc{n}", "meta": {"ac_id": "AC-01"}})
    board = json.dumps(items)
    approved = await approve_criteria("ff", CTX, uc_ids=["UC-730"], items_content=board)
    picked = await find_next_uc("ff", CTX, items_content=approved["items_content"], policy_content=_policy("block"))
    assert picked["uc_id"] == "UC-730"
    many = [US] + [{"id": f"x{n}", "name": f"UC-8{n:02d}: Caso {n}", "description": "", "state": "backlog",
                    "labels": ["UC"], "parent_id": "us7", "meta": {"uc_id": f"UC-8{n:02d}", "us_id": "US-07"}}
                   for n in range(1, 52)]
    too_many = await approve_criteria("ff", CTX, us_id="US-07", items_content=json.dumps(many))
    assert too_many["code"] == "TOO_MANY_UCS"


async def test_warn_keeps_the_stale_state_of_the_first_uc():
    approved = await approve_criteria("ff", CTX, uc_ids=["UC-701"], approved_by="Ana", items_content=_board())
    changed = await update_ac("ff", "UC-701", "AC-01", CTX, text="El cobro queda registrado con su hora",
                              items_content=approved["items_content"])
    warned = await find_next_uc("ff", CTX, items_content=changed["items_content"], policy_content=_policy("warn"))
    assert warned["uc_id"] == "UC-701" and warned["criteria_approval"]["state"] == "stale"


async def test_trello_and_plane_do_not_apply_the_measure(monkeypatch):
    """No guardan la aprobación: approve_criteria no escribe nada y start_uc no avisa por ella."""
    from server.tools import approval as approval_mod
    from server.tools.enforcement import start_gate

    class _Capped:
        STORES_SPEC_META = False

        async def get_acceptance_criteria(self, board_id, uc_item_id):
            return []

        async def close(self):
            return None

    async def _backend(ctx, items_content=None):
        return _Capped()

    monkeypatch.setattr(approval_mod, "get_session_backend", _backend)
    out = await approve_criteria("trello-board", CTX, uc_ids=["UC-1"])
    assert out["code"] == "APPROVAL_NOT_SUPPORTED"
    uc_item = type("UC", (), {"id": "c1", "name": "UC-1: X", "description": "", "state": "backlog", "meta": {}})()
    gate = await start_gate(None, "trello-board", "UC-1", uc_item, _Capped())
    assert all(w["measure"] != "ac_approval" for w in gate["warnings"])


@pg
async def test_native_find_next_uc_counts_predating_ucs_with_description(monkeypatch, tmp_path):
    """El caso de la revisión: una UC con descripción, abierta al pasar a «block», no se detiene."""
    pool, pid, dev, token, ctx = await _native_board(
        monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado con su recibo"]})
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE use_cases SET description = 'Cobrar con tarjeta y dejar el recibo' "
                "WHERE project_id = $1 AND id = 'UC-01'", pid)
        await _to_block(pid, token)
        picked = await find_next_uc(pid, ctx)
        assert picked["uc_id"] == "UC-01" and picked["criteria_approval"]["state"] == "migration"
    finally:
        await _cleanup(pool, pid, dev)


@pg
async def test_a_freeform_approval_travels_to_native(monkeypatch, tmp_path):
    """Cambiar de backend conserva la aprobación con su autor (los ids y textos viajan igual)."""
    from server.backends.freeform_backend import FreeformBackend
    from server.tools.migration import _read_source
    from server.tools.spec_driven import get_session_backend

    board = (await approve_criteria("ff", CTX, uc_ids=["UC-701"], approved_by="Ana", items_content=_board()))
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={})
    try:
        src = FreeformBackend(items_content=board["items_content"])
        try:
            source = await _read_source(src, ".")
        finally:
            await src.close()
        backend = await get_session_backend(ctx)
        try:
            result = await backend.ingest_atomic(pid, source, source_type="freeform")
        finally:
            await backend.close()
        assert result["migrated"]["approvals"] == 1
        state = (await get_uc(pid, "UC-701", ctx))["criteria_approval"]
        assert state["state"] == "approved" and state["by"] == "Ana"
    finally:
        await _cleanup(pool, pid, dev)
