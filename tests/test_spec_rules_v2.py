"""US-123 / UC-12302 — los criterios usan lenguaje normativo y límites medibles.

- **AC-01**: un verbo modal débil («debería», «intenta» + infinitivo, «en lo posible», «should»,
  «may») deja el criterio en ``failed`` con ``weak_modal``.
- **AC-02**: un límite de cantidad o tiempo dicho con un calificativo sin cifra ni unidad deja el
  criterio en ``failed`` con ``no_threshold``.
- **AC-03**: una cifra de rendimiento que no dice bajo qué condición vale sale en los avisos con
  ``threshold_without_condition``.
- **AC-04**: las reglas nuevas solo juzgan criterios creados o reescritos con ellas (sello
  ``meta.spec_rules``); los anteriores salen como «anteriores a la regla» y no cuentan para el umbral.

Calibradas contra los 1.835 criterios del tablero del orquestador (2026-11-18): 0 cambian de
veredicto y 4 reciben el aviso de condición.
"""

from __future__ import annotations

import json

import pytest

from server.coordination import enforcement as pol
from server.tools import _mutation_helpers as mh
from server.tools.board_operations import validate_ac_quality
from server.tools.spec_driven import import_spec, start_uc
from server.tools.spec_mutations import add_ac, update_ac
from tests.test_spec_gate_start_uc import AT, CTX, UC, US, _cleanup, _native_board, pg

OLD = {"id": "ac1", "name": "[AC-01] El correo debería quedar guardado en el registro", "state": "backlog", "labels": ["AC"],
       "parent_id": "uc701", "meta": {"ac_id": "AC-01"}}


def v2(text: str) -> list[str]:
    return mh.validate_ac_text(text, rules=2)


# ── Las reglas ──────────────────────────────────────────────────────


@pytest.mark.parametrize("text", [
    "El sistema debería reenviar el correo si falla",
    "La lista queda ordenada en lo posible",
    "The export should contain every row",
    "The panel may show the totals",
    "El sistema intenta reenviar el correo tres veces",
])
def test_a_weak_modal_fails(text):
    """AC-01."""
    assert "weak_modal" in v2(text)


@pytest.mark.parametrize("text", [
    "Un usuario que intenta entrar sin sesión recibe 401",
    "Una sesión de otro rol que lo intenta recibe «sin permiso»",
    "El criterio con un modal débil («debería», «may») queda en `failed`",  # citado: no cuenta
    "Si auto-deploy y webhook podrían disparar builds, --check lo detecta y lo reporta",
])
def test_what_is_not_a_weak_modal(text):
    assert "weak_modal" not in v2(text)


@pytest.mark.parametrize("text", ["La app responde en poco tiempo", "El listado admite muchos proyectos"])
def test_a_limit_without_a_figure_fails(text):
    """AC-02."""
    assert "no_threshold" in v2(text)


@pytest.mark.parametrize("text", [
    "Una o varias pantallas quedan marcadas",
    "La app responde en menos de 200 ms",
    "Muchos proyectos aparecen en la lista con su estado",  # no limita nada: no hay verbo de límite
])
def test_what_is_not_a_vague_limit(text):
    assert "no_threshold" not in v2(text)


def test_a_figure_without_its_condition_is_a_warning():
    """AC-03: aviso, no fallo; con red, volumen o dispositivo no avisa."""
    assert mh.ac_text_warnings("La página carga en 2 s", rules=2) == ["threshold_without_condition"]
    assert v2("La página carga en 2 s") == []
    assert mh.ac_text_warnings("La página carga en 2 s con 4G en un iPhone 12", rules=2) == []
    assert mh.ac_text_warnings("El endpoint responde en 800 ms con el volumen actual", rules=2) == []
    assert mh.ac_text_warnings("El aviso sale cada 5 minutos", rules=2) == []  # periodicidad, no rendimiento


def test_the_old_rules_do_not_change():
    """AC-04: sin sello, el gate es el de siempre."""
    for text in ("El sistema debería reenviar el correo", "La app responde en poco tiempo", "La página carga en 2 s"):
        assert "weak_modal" not in mh.validate_ac_text(text)
        assert "no_threshold" not in mh.validate_ac_text(text)
        assert mh.ac_text_warnings(text) == []


# ── El sello en FreeForm y lo que ve validate_ac_quality ────────────


def _ac_meta(items_content: str, ac_id: str) -> dict:
    return next(i["meta"] for i in json.loads(items_content) if i.get("meta", {}).get("ac_id") == ac_id
                and "AC" in i.get("labels", []))


async def test_a_new_or_rewritten_criterion_is_stamped_and_an_unchanged_one_is_not():
    board = json.dumps([US, UC, OLD])
    added = await add_ac("ff", "UC-701", "El correo queda reenviado con su registro", CTX, items_content=board)
    assert _ac_meta(added["items_content"], "AC-02")["spec_rules"] == mh.SPEC_RULES_VERSION
    assert "spec_rules" not in _ac_meta(added["items_content"], "AC-01")
    same = await update_ac("ff", "UC-701", "AC-01", CTX, text="El correo debería quedar guardado en el registro",
                           items_content=added["items_content"])
    assert "spec_rules" not in _ac_meta(same["items_content"], "AC-01")
    rewritten = await update_ac("ff", "UC-701", "AC-01", CTX, text="El correo debería quedar guardado dos veces",
                                items_content=added["items_content"])
    assert _ac_meta(rewritten["items_content"], "AC-01")["spec_rules"] == mh.SPEC_RULES_VERSION

    spec = {"user_stories": [{"us_id": "US-09", "name": "Avisos", "use_cases": [
        {"uc_id": "UC-901", "name": "Avisar", "acceptance_criteria": ["El aviso queda enviado con su fecha"]}]}]}
    imported = await import_spec("ff", spec, CTX, items_content="[]")
    assert _ac_meta(imported["items_content"], "AC-01")["spec_rules"] == mh.SPEC_RULES_VERSION


async def test_validate_ac_quality_judges_each_criterion_by_its_rules():
    """AC-01..AC-04 en la tool que mide el gate."""
    old = {**OLD, "name": "[AC-01] El sistema debería reenviar el correo y lo registra"}
    new_weak = {"id": "ac2", "name": "[AC-02] La lista queda ordenada en lo posible", "state": "backlog",
                "labels": ["AC"], "parent_id": "uc701", "meta": {"ac_id": "AC-02", "spec_rules": 2}}
    new_perf = {"id": "ac3", "name": "[AC-03] La página carga en 2 s", "state": "backlog", "labels": ["AC"],
                "parent_id": "uc701", "meta": {"ac_id": "AC-03", "spec_rules": 2}}
    out = await validate_ac_quality("ff", CTX, uc_id="UC-701", items_content=json.dumps([US, UC, old, new_weak, new_perf]))
    assert [(f["ac_id"], f["issues"]) for f in out["failed"]] == [("AC-02", ["weak_modal"])]
    assert out["pass_rate"] == round(2 / 3, 4)  # el anterior a la regla no cuenta como fallo
    assert [(w["ac_id"], w["warnings"]) for w in out["warnings"]] == [("AC-03", ["threshold_without_condition"])]
    assert out["exposure_warnings"] == 0
    assert out["predates_rule"] == [{"uc_id": "UC-701", "ac_id": "AC-01", "text": old["name"][8:],
                                     "would_flag": ["weak_modal"]}]


async def test_start_uc_blocks_a_new_weak_criterion_but_not_an_old_one():
    """AC-04 en el arranque: el criterio anterior a la regla no cuenta para el umbral."""
    stored, _ = pol.with_mode(None, "spec_quality", "block", by="ana", at=AT, backend_type="freeform", open_ucs={})
    old_only = await start_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, OLD]),
                              policy_content=json.dumps(stored))
    assert old_only["status"] == "in_progress"
    new = {**OLD, "meta": {"ac_id": "AC-01", "spec_rules": 2}}
    blocked = await start_uc("ff", "UC-701", CTX, items_content=json.dumps([US, UC, new]),
                             policy_content=json.dumps(stored))
    assert blocked["code"] == "AC_QUALITY_BELOW_THRESHOLD" and "weak_modal" in blocked["error"]


# ── Native ──────────────────────────────────────────────────────────


@pg
async def test_native_stamps_on_create_and_on_a_real_rewrite(monkeypatch, tmp_path):
    pool, pid, dev, token, ctx = await _native_board(monkeypatch, tmp_path, criteria={"UC-01": ["El cobro queda registrado"]})
    try:
        async with pool.acquire() as conn:
            # Un criterio de antes de esta versión: sin sello.
            await conn.execute(
                "INSERT INTO acceptance_criteria (id, project_id, uc_id, ac_id, text, meta) "
                "VALUES ($1, $2, 'UC-01', 'AC-02', 'El sistema debería avisar', '{}'::jsonb)",
                "UC-01::AC-02", pid,
            )

        async def stamps():
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT ac_id, meta->>'spec_rules' AS r FROM acceptance_criteria WHERE project_id = $1 ORDER BY ac_id",
                    pid,
                )
            return {r["ac_id"]: r["r"] for r in rows}

        assert await stamps() == {"AC-01": str(mh.SPEC_RULES_VERSION), "AC-02": None}
        await update_ac(pid, "UC-01", "AC-02", ctx, text="El sistema debería avisar")
        assert (await stamps())["AC-02"] is None  # mismo texto: sigue siendo anterior a la regla
        out = await validate_ac_quality(pid, ctx, uc_id="UC-01")
        assert out["failed"] == [] and out["predates_rule"][0]["ac_id"] == "AC-02"
        await update_ac(pid, "UC-01", "AC-02", ctx, text="El sistema debería avisar por correo")
        assert (await stamps())["AC-02"] == str(mh.SPEC_RULES_VERSION)
        out = await validate_ac_quality(pid, ctx, uc_id="UC-01")
        assert [(f["ac_id"], f["issues"]) for f in out["failed"]] == [("AC-02", ["weak_modal"])]
    finally:
        await _cleanup(pool, pid, dev)
