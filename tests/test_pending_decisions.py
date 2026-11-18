"""US-123 / UC-12305 — lo que falta por decidir queda marcado y bloquea el arranque.

- **AC-01**: las plantillas de PRD y de plan traen la marca ``[POR DECIDIR: …]`` y la sección
  «Pendiente de decidir».
- **AC-02**: ``start_uc`` no arranca una UC con una marca en su texto o en sus criterios, y el error
  muestra cada marca.
- **AC-03**: sin la tool de triaje, /implement para antes de crear la rama (la skill lo dice).
- **AC-04**: en «warn» arranca y muestra las marcas; en «block» no; una UC anterior a la regla
  arranca en cualquier modo.

Lo citado entre comillas invertidas o angulares no es una marca: la propia UC-12305 nombra
`[POR DECIDIR` en sus criterios.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.coordination import enforcement as pol
from server.tools.spec_driven import start_uc
from tests.test_spec_gate_start_uc import (
    AT,
    CTX,
    UC,
    US,
    _cleanup,
    _native_board,
    pg,
)

ENGINE = Path(__file__).resolve().parent.parent
GOOD = {"id": "ac1", "name": "[AC-01] El cobro queda registrado con su recibo", "state": "backlog", "labels": ["AC"],
        "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}
MARKED = {"id": "ac2", "name": "[AC-02] El cobro queda registrado en el proveedor [POR DECIDIR: Stripe o Redsys]",
          "state": "backlog", "labels": ["AC"], "parent_id": "uc701", "meta": {"ac_id": "AC-02"}}


def _policy(mode: str = "block", open_ucs: dict | None = None) -> str:
    stored, _ = pol.with_mode(None, "pending_decisions", mode, by="ana", at=AT, backend_type="freeform",
                              open_ucs=open_ucs or {})
    return json.dumps(stored)


# ── Las marcas ──────────────────────────────────────────────────────


def test_marks_are_found_with_what_is_missing_and_where():
    uc = {
        "name": "UC-9: Cobrar",
        "description": "Cobro con tarjeta. [POR DECIDIR: el plazo de devolución]\n- AC-02: x [POR DECIDIR: Stripe o Redsys]",
        "acs": [{"ac_id": "AC-01", "text": "El cobro queda registrado"},
                {"ac_id": "AC-02", "text": "El cobro queda en el proveedor [POR DECIDIR: Stripe o Redsys]"}],
    }
    marks = pol.pending_marks(uc)
    # La de la descripción que repite la del criterio no se cuenta dos veces.
    assert marks == [
        {"where": "AC-02", "mark": "Stripe o Redsys"},
        {"where": "la descripción", "mark": "el plazo de devolución"},
    ]
    reason = pol.pending_reason(marks)
    assert "2 marca(s)" in reason and "AC-02: «Stripe o Redsys»" in reason


def test_a_quoted_mark_is_not_a_mark():
    """UC-12305 cita `[POR DECIDIR` en sus propios criterios: no puede detenerse a sí misma."""
    uc = {"name": "", "description": "La plantilla trae la marca `[POR DECIDIR: …]`.",
          "acs": [{"ac_id": "AC-02", "text": "start_uc no arranca una UC con una marca `[POR DECIDIR`."},
                  {"ac_id": "AC-03", "text": "La sección lista la marca «[POR DECIDIR: x]»."}]}
    assert pol.pending_marks(uc) == []


def test_pending_decisions_is_active_from_this_version():
    assert pol.effective_policy(None, backend_type="native")["measures"]["pending_decisions"]["active"] is True


# ── start_uc ────────────────────────────────────────────────────────


async def test_block_stops_a_uc_with_a_mark_and_names_it():
    """AC-02."""
    board = json.dumps([US, UC, GOOD, MARKED])
    out = await start_uc("ff", "UC-701", CTX, items_content=board, policy_content=_policy())
    assert out["code"] == "PENDING_DECISIONS" and out["measure"] == "pending_decisions"
    assert out["pending_marks"] == [{"where": "AC-02", "mark": "Stripe o Redsys"}]
    assert "«Stripe o Redsys»" in out["error"]
    assert "items_content" not in out


async def test_warn_starts_and_shows_the_marks():
    """AC-04: «warn» arranca y las marcas salen en la respuesta."""
    out = await start_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, GOOD, MARKED]))
    assert out["status"] == "in_progress"
    [warning] = [w for w in out["enforcement_warnings"] if w["measure"] == "pending_decisions"]
    assert warning["pending_marks"][0]["mark"] == "Stripe o Redsys"


async def test_a_uc_that_predates_the_rule_starts_in_block():
    """AC-04."""
    from server.tools.enforcement import _freeform_open_ucs

    board = json.dumps([US, UC, GOOD, MARKED])
    uc = next(u for u in await _freeform_open_ucs(board) if u["uc_id"] == "UC-701")
    out = await start_uc("ff", "UC-701", CTX, items_content=board,
                         policy_content=_policy(open_ucs=pol.open_uc_fingerprints([uc])))
    assert out["status"] == "in_progress"
    assert [w["outcome"] for w in out["enforcement_warnings"] if w["measure"] == "pending_decisions"] == ["predates_rule"]


async def test_import_spec_reports_the_marks_of_each_uc():
    from server.tools.spec_driven import import_spec

    spec = {"user_stories": [{"us_id": "US-08", "name": "Facturas", "use_cases": [
        {"uc_id": "UC-801", "name": "Emitir",
         "acceptance_criteria": ["La factura queda emitida con la serie [POR DECIDIR: serie A o B]"]},
    ]}]}
    out = await import_spec("ff", spec, CTX, items_content="[]")
    assert out["spec_gate"][0]["pending_marks"] == [{"where": "AC-01", "mark": "serie A o B"}]


@pg
async def test_native_block_leaves_a_marked_uc_unreserved(monkeypatch, tmp_path):
    """AC-02 en native: la marca en la descripción detiene el arranque y nada queda reservado."""
    pool, pid, dev, token, ctx = await _native_board(
        monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado con su recibo"]}
    )
    try:
        from server.tools.enforcement import set_enforcement_mode

        ask = await set_enforcement_mode(None, "pending_decisions", "block", board_id=pid, dev_token=token)
        await set_enforcement_mode(None, "pending_decisions", "block", board_id=pid, dev_token=token,
                                   confirm=ask["confirm"])
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE use_cases SET description = 'Cobro. [POR DECIDIR: el plazo de devolución]' "
                "WHERE project_id = $1 AND id = 'UC-01'", pid,
            )
        out = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert out["code"] == "PENDING_DECISIONS", out
        assert out["pending_marks"] == [{"where": "la descripción", "mark": "el plazo de devolución"}]
        async with pool.acquire() as conn:
            state = await conn.fetchval("SELECT state FROM use_cases WHERE project_id = $1 AND id = 'UC-01'", pid)
            reserved = await conn.fetchval("SELECT count(*) FROM uc_reservations WHERE project_id = $1", pid)
        assert (state, reserved) == ("backlog", 0)
    finally:
        await _cleanup(pool, pid, dev)


# ── Plantillas y /implement ─────────────────────────────────────────


def _skill(name: str) -> str:
    return (ENGINE / ".claude/skills" / name / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("template", ["PRD Spec-Driven", "PRD Feature (Freeform)", "PRD Tecnico"])
def test_each_prd_template_has_the_mark_and_the_pending_section(template):
    """AC-01."""
    body = _skill("prd").split(f"## Template: {template}", 1)[1].split("\n## Template: ", 1)[0]
    body = body.split("## Paso 2.5:", 1)[0]
    assert "## Pendiente de decidir" in body and "[POR DECIDIR:" in body


def test_the_plan_template_has_the_mark_and_the_pending_section():
    """AC-01."""
    template = _skill("plan").split("### Template de Plan", 1)[1].split("\n## Paso 5", 1)[0]
    assert "## Pendiente de decidir" in template and "[POR DECIDIR:" in template


def test_implement_stops_without_the_triage():
    """AC-03: la nota de degradación («el gate se omite») ya no existe; /implement para y lo dice."""
    step = _skill("implement").split("### 0.4c", 1)[1].split("\n### ", 1)[0]
    assert "se omite" not in step and "Degradacion" not in step
    assert "Sin triaje no hay rama" in step and "antes de `start_uc` y de crear la rama" in step


def test_uc_12305_does_not_stop_itself():
    """La UC real del tablero, con sus criterios tal como están: ninguna marca que cuente."""
    uc = {"name": "UC-12305: B2 · Lo que falta por decidir queda marcado y bloquea el arranque",
          "description": "", "acs": [
              {"ac_id": "AC-01", "text": "Las plantillas de PRD y de plan incluyen la marca `[POR DECIDIR: …]` y una "
                                         "sección «Pendiente de decidir» que la lista."},
              {"ac_id": "AC-02", "text": "`start_uc` no arranca una UC cuyo texto o criterios contienen una marca "
                                         "`[POR DECIDIR`, y el error muestra cada marca."},
          ]}
    assert pol.pending_marks(uc) == []

