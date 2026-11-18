"""US-123 / UC-12307 — cada criterio dice cómo se comprueba.

- **AC-01**: el criterio incluye el campo «cómo se comprueba» (``verification``: prueba automática,
  prueba manual, revisión o medida) y ``get_uc`` lo devuelve.
- **AC-02**: ``import_spec`` y ``add_ac`` aceptan ese campo (también ``add_uc``, ``update_ac`` y
  ``update_ac_batch``), y /prd lo rellena para cada criterio al escribir la spec.
- **AC-03**: ``validate_ac_quality`` devuelve en avisos los criterios sin forma de comprobación, con el
  motivo ``no_verification``.
- **AC-04**: el aviso solo aparece en criterios creados después de publicar el campo (reglas 3); los
  anteriores quedan sin aviso.
- **AC-05**: en FreeForm el campo queda en los ficheros del tablero y ``get_uc`` lo devuelve igual que
  en native.

FreeForm por contenido (el MCP remoto) aquí; native contra Postgres al final (SKIP sin base).
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from server.backends.dual_backend import DualBackendWrapper
from server.backends.freeform_backend import FreeformBackend
from server.backends.native_backend import NativeBackend
from server.backends.plane_backend import PlaneBackend
from server.backends.trello_backend import TrelloBackend
from server.tools import _mutation_helpers as mh
from server.tools.board_operations import validate_ac_quality
from server.tools.spec_driven import get_uc, import_spec
from server.tools.spec_mutations import add_ac, add_uc, update_ac, update_ac_batch
from tests.test_spec_gate_start_uc import CTX, UC, US, _cleanup, _native_board, pg

ROOT = Path(__file__).resolve().parent.parent

SPEC = {"user_stories": [{"us_id": "US-09", "name": "Avisos", "use_cases": [
    {"uc_id": "UC-901", "name": "Avisar", "acceptance_criteria": [
        {"text": "El aviso queda enviado con su fecha", "verification": "automated_test"},
        {"text": "El correo del aviso muestra el nombre del proyecto", "verification": "Manual test"},
        "El registro incluye la hora del envío",
    ]}]}]}


def _ac_meta(items_content: str, ac_id: str, uc_item: str | None = None) -> dict:
    return next(
        i["meta"] for i in json.loads(items_content)
        if "AC" in i.get("labels", []) and i.get("meta", {}).get("ac_id") == ac_id
        and (uc_item is None or i.get("parent_id") == uc_item)
    )


def _verifications(detail: dict) -> dict[str, str | None]:
    return {ac["id"]: ac["verification"] for ac in detail["acceptance_criteria"]}


# ── La parte pura ───────────────────────────────────────────────────


def test_the_four_ways_to_check_a_criterion():
    """AC-01: cuatro valores; se acepta lo escrito a mano y se guarda la forma canónica."""
    assert mh.VERIFICATION_METHODS == ("automated_test", "manual_test", "review", "measurement")
    assert mh.normalize_verification("Automated test") == "automated_test"
    assert mh.normalize_verification("manual-test") == "manual_test"
    assert mh.normalize_verification(None) is None
    for bad in ("e2e", "", 3):
        with pytest.raises(mh.VerificationError):
            mh.normalize_verification(bad)


def test_no_verification_only_for_criteria_written_under_rules_3():
    """AC-03 y AC-04."""
    assert mh.SPEC_RULES_VERSION == mh.RULES_VERIFICATION == 3
    assert mh.verification_warnings(None, rules=3) == ["no_verification"]
    assert mh.verification_warnings("review", rules=3) == []
    assert mh.verification_warnings(None, rules=2) == []  # escrito con la 6.39: el campo no existía
    assert mh.verification_warnings(None, rules=1) == []  # sin sello


def test_a_tool_can_only_write_the_verification_key():
    """El resto del meta del criterio (sello, recibos, veredicto) lo escribe solo el backend."""
    assert mh.ac_meta_extra({"verification": "review", "spec_rules": 9, "verdict": {"passed": True}}) == {
        "verification": "review"
    }
    assert mh.ac_meta_extra(None) == {}


def test_every_backend_takes_the_new_arguments():
    """El ABC gana argumentos opcionales: los cuatro backends y el doble los aceptan."""
    for cls in (NativeBackend, FreeformBackend, TrelloBackend, PlaneBackend, DualBackendWrapper):
        assert "meta_by_ac" in inspect.signature(cls.create_acceptance_criteria).parameters, cls
        assert "meta" in inspect.signature(cls.update_acceptance_criterion).parameters, cls
    assert NativeBackend.STORES_SPEC_META and FreeformBackend.STORES_SPEC_META
    assert not TrelloBackend.STORES_SPEC_META and not PlaneBackend.STORES_SPEC_META


# ── FreeForm por contenido ──────────────────────────────────────────


async def test_import_spec_keeps_the_verification_in_the_board_files_and_get_uc_returns_it():
    """AC-01, AC-02 y AC-05."""
    out = await import_spec("ff", json.loads(json.dumps(SPEC)), CTX, items_content="[]")
    assert out["errors"] == [] and out["created"]["ac"] == 3
    board = out["items_content"]
    assert _ac_meta(board, "AC-01")["verification"] == "automated_test"
    assert _ac_meta(board, "AC-02")["verification"] == "manual_test"
    assert "verification" not in _ac_meta(board, "AC-03")
    detail = await get_uc("ff", "UC-901", CTX, items_content=board)
    assert _verifications(detail) == {"AC-01": "automated_test", "AC-02": "manual_test", "AC-03": None}


async def test_reimporting_sets_the_verification_of_an_existing_criterion_without_rewriting_it():
    first = await import_spec("ff", {"user_stories": [{"us_id": "US-09", "name": "Avisos", "use_cases": [
        {"uc_id": "UC-901", "name": "Avisar", "acceptance_criteria": ["El aviso queda enviado con su fecha"]}]}]},
        CTX, items_content="[]")
    again = await import_spec("ff", json.loads(json.dumps(SPEC)), CTX, items_content=first["items_content"])
    assert again["created"]["ac"] == 2 and again["updated"]["ac_verification"] == 1
    assert _ac_meta(again["items_content"], "AC-01")["verification"] == "automated_test"
    same = await import_spec("ff", json.loads(json.dumps(SPEC)), CTX, items_content=again["items_content"])
    assert "ac_verification" not in same["updated"]  # nada cambia: no se reescribe


async def test_import_spec_names_a_bad_verification_and_imports_nothing():
    bad = json.loads(json.dumps(SPEC))
    bad["user_stories"][0]["use_cases"][0]["acceptance_criteria"][0]["verification"] = "e2e"
    with pytest.raises(ValueError, match="e2e"):
        await import_spec("ff", bad, CTX, items_content="[]")


async def test_add_ac_and_add_uc_take_the_verification():
    """AC-02 en las tools de una en una."""
    board = json.dumps([US, UC])
    added = await add_ac("ff", "UC-701", "El cobro queda registrado con su recibo", CTX,
                         verification="measurement", items_content=board)
    assert added["verification"] == "measurement" and "verification_not_stored" not in added
    assert _ac_meta(added["items_content"], "AC-01")["verification"] == "measurement"
    wrong = await add_ac("ff", "UC-701", "Otro criterio queda guardado", CTX, verification="a ojo",
                         items_content=board)
    assert wrong["code"] == "INVALID_VERIFICATION"

    created = await add_uc("ff", "US-07", "Devolver", "Devolver un cobro", [
        {"text": "La devolución queda registrada", "verification": "review"},
        "El cliente recibe el correo de la devolución",
    ], CTX, items_content=board)
    detail = await get_uc("ff", created["uc_id"], CTX, items_content=created["items_content"])
    assert _verifications(detail) == {"AC-01": "review", "AC-02": None}
    refused = await add_uc("ff", "US-07", "Devolver", "", [{"text": "x", "verification": "nunca"}], CTX,
                           items_content=board)
    assert refused["code"] == "INVALID_VERIFICATION"


async def test_validate_ac_quality_warns_no_verification_only_on_new_criteria():
    """AC-03 y AC-04: el aviso no cuenta para el umbral."""
    old = {"id": "ac1", "name": "[AC-01] El cobro queda registrado con su recibo", "state": "backlog",
           "labels": ["AC"], "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}
    v2 = {**old, "id": "ac2", "name": "[AC-02] El recibo incluye el importe", "meta": {"ac_id": "AC-02", "spec_rules": 2}}
    new = {**old, "id": "ac3", "name": "[AC-03] El recibo incluye la fecha", "meta": {"ac_id": "AC-03", "spec_rules": 3}}
    told = {**old, "id": "ac4", "name": "[AC-04] El recibo incluye el cliente",
            "meta": {"ac_id": "AC-04", "spec_rules": 3, "verification": "automated_test"}}
    out = await validate_ac_quality("ff", CTX, uc_id="UC-701", items_content=json.dumps([US, UC, old, v2, new, told]))
    assert [(w["ac_id"], w["warnings"]) for w in out["warnings"]] == [("AC-03", ["no_verification"])]
    assert out["failed"] == [] and out["pass_rate"] == 1.0
    assert "predates_rule" not in out  # no se le pide a un criterio anterior lo que no existía


async def test_update_ac_sets_the_verification_and_keeps_the_criterion_done():
    """La forma de corregir el aviso sin reimportar: el texto no cambia, el criterio sigue hecho."""
    done = {"id": "ac1", "name": "[AC-01] El cobro queda registrado con su recibo", "state": "done",
            "labels": ["AC"], "parent_id": "uc701", "meta": {"ac_id": "AC-01", "spec_rules": 3}}
    board = json.dumps([US, UC, done])
    out = await update_ac("ff", "UC-701", "AC-01", CTX, verification="automated_test", items_content=board)
    assert out["updated_fields"] == ["verification"] and "reset_to_pending" not in out
    meta = _ac_meta(out["items_content"], "AC-01")
    assert meta["verification"] == "automated_test" and meta["spec_rules"] == 3
    after = await validate_ac_quality("ff", CTX, uc_id="UC-701", items_content=out["items_content"])
    assert after["warnings"] == []
    detail = await get_uc("ff", "UC-701", CTX, items_content=out["items_content"])
    assert detail["acceptance_criteria"][0]["done"] is True
    same = await update_ac("ff", "UC-701", "AC-01", CTX, verification="automated_test",
                           items_content=out["items_content"])
    assert same["reason"] == "no_change"
    bad = await update_ac("ff", "UC-701", "AC-01", CTX, verification="nope", items_content=board)
    assert bad["code"] == "INVALID_VERIFICATION"


async def test_update_ac_batch_sets_verifications_and_fails_only_the_bad_entry():
    a1 = {"id": "ac1", "name": "[AC-01] El cobro queda registrado", "state": "backlog", "labels": ["AC"],
          "parent_id": "uc701", "meta": {"ac_id": "AC-01", "spec_rules": 3}}
    a2 = {**a1, "id": "ac2", "name": "[AC-02] El recibo incluye el importe", "meta": {"ac_id": "AC-02", "spec_rules": 3}}
    out = await update_ac_batch("ff", [
        {"uc_id": "UC-701", "ac_id": "AC-01", "verification": "review"},
        {"uc_id": "UC-701", "ac_id": "AC-02", "verification": "otra"},
    ], CTX, items_content=json.dumps([US, UC, a1, a2]))
    assert [(s["ac_id"], s["updated_fields"]) for s in out["succeeded"]] == [("AC-01", ["verification"])]
    assert [(f["ac_id"], f["code"]) for f in out["failed"]] == [("AC-02", "INVALID_VERIFICATION")]
    assert _ac_meta(out["items_content"], "AC-01")["verification"] == "review"


async def test_a_backend_without_per_criterion_metadata_says_it_did_not_store_it(monkeypatch):
    """Trello y Plane no tienen dónde guardarlo: la respuesta lo dice en vez de callar."""
    monkeypatch.setattr(FreeformBackend, "STORES_SPEC_META", False)
    board = json.dumps([US, UC])
    added = await add_ac("ff", "UC-701", "El cobro queda registrado con su recibo", CTX,
                         verification="review", items_content=board)
    assert added["verification_not_stored"] is True and added["verification"] is None
    assert "verification" not in _ac_meta(added["items_content"], "AC-01")
    imported = await import_spec("ff", json.loads(json.dumps(SPEC)), CTX, items_content="[]")
    assert imported["verification_not_stored"] is True
    updated = await update_ac("ff", "UC-701", "AC-01", CTX, verification="review",
                              items_content=added["items_content"])
    assert updated["reason"] == "no_change" and updated["verification_not_stored"] is True


def test_prd_fills_the_verification_of_each_criterion():
    """AC-02: /prd decide cómo se comprueba cada criterio y lo siembra con import_spec."""
    skill = (ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")
    assert "### 2.5.1b Decidir cómo se comprueba cada criterio (UC-12307)" in skill
    for value in mh.VERIFICATION_METHODS:
        assert f"`{value}`" in skill
    assert '{"text": "…", "verification": "automated_test"}' in skill


# ── Native ──────────────────────────────────────────────────────────


@pg
async def test_native_keeps_the_verification_with_the_criterion(monkeypatch, tmp_path):
    """AC-01 a AC-04 en native: create, update, get_uc y validate_ac_quality."""
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": []})
    try:
        added = await add_ac(pid, "UC-01", "El cobro queda registrado con su recibo", ctx, verification="automated_test")
        assert added["verification"] == "automated_test"
        await add_ac(pid, "UC-01", "El recibo incluye el importe", ctx)
        async with pool.acquire() as conn:
            # Un criterio de la 6.39 (reglas 2) y otro de antes: ninguno recibe el aviso.
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, meta) VALUES "
                "($1, $3, 'UC-01', 'AC-03', 'El recibo incluye la fecha', '{\"spec_rules\": 2}'::jsonb), "
                "($2, $3, 'UC-01', 'AC-04', 'El recibo incluye el cliente', '{}'::jsonb)",
                "UC-01::AC-03", "UC-01::AC-04", pid,
            )
        detail = await get_uc(pid, "UC-01", ctx)
        assert _verifications(detail) == {"AC-01": "automated_test", "AC-02": None, "AC-03": None, "AC-04": None}
        out = await validate_ac_quality(pid, ctx, uc_id="UC-01")
        assert [(w["ac_id"], w["warnings"]) for w in out["warnings"]] == [("AC-02", ["no_verification"])]

        fixed = await update_ac(pid, "UC-01", "AC-02", ctx, verification="manual_test")
        assert fixed["updated_fields"] == ["verification"]
        rewritten = await update_ac(pid, "UC-01", "AC-01", ctx, text="El cobro queda registrado con su recibo y su fecha",
                                    verification="review")
        assert set(rewritten["updated_fields"]) == {"text", "verification"}
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ac_id, meta FROM acceptance_criteria WHERE project_id = $1 ORDER BY ac_id", pid
            )
        metas = {r["ac_id"]: json.loads(r["meta"]) if isinstance(r["meta"], str) else r["meta"] for r in rows}
        assert metas["AC-01"]["verification"] == "review" and metas["AC-01"]["spec_rules"] == 3
        assert metas["AC-02"]["verification"] == "manual_test"
        assert (await validate_ac_quality(pid, ctx, uc_id="UC-01"))["warnings"] == []
    finally:
        await _cleanup(pool, pid, dev)
