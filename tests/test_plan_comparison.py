"""UC-12601 (US-126) — al cerrar, lo hecho se compara con el plan.

- AC-01: el estado de implementación de cada fase recibe los ficheros que el plan esperaba y muestra
  los que sobran y los que faltan.
- AC-02: run_acceptance_check comprueba cada criterio por la prueba que lleva su etiqueta y su
  resultado, no por la aparición de su id en el código.
- AC-03: la documentación de Spec-Code Sync incluye la comparación con el plan y la nota de UC-12204
  queda retirada (tests/test_doc_promises.py, test_uc_12601_*).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

import subprocess

from server.delta_generator import NO_PLAN_COMPARISON, NO_PLAN_PHASE, compare_files, generate_phase_delta
from server.implement_context.phase_outputs import parse_phase_outputs
from server.tools.evidence_regen import _results_for_check
from server.prd_parser import parse_implementation_status
from server.tools.acceptance import (
    AC_LINE_PATTERN,
    _extract_ac_from_prd,
    _find_ucs_for_us,
    run_acceptance_check_from_content,
)
from server.tools.implement_context_tools import register_implement_context_tools

ROOT = Path(__file__).resolve().parent.parent
PLAN = """# Plan
### Fase 0: Preparación
**Criterios:** UC-701 AC-04
**Ficheros:** doc/notas.md
### Fase 1: Base
**Criterios:** UC-701 AC-01
**Ficheros:** server/a.py, ./server/b.py
### Fase 2: Lectura
**Criterios:** UC-701 AC-02
**Ficheros:** server/c.py, server/vistas/
### Fase 3: Otra UC
**Criterios:** UC-702 AC-01
**Ficheros:** server/otra.py
## Dependencias nuevas
- Ninguna
"""
PRD = """# PRD
#### UC-12: Otra cosa
- [ ] **AC-01**: Lo de otra UC queda registrado
#### UC-12601: E2 · Al cerrar, lo hecho se compara con el plan
- [ ] **AC-01**: El estado de cada fase muestra lo que sobra y lo que falta
- [x] **AC-02**: La comprobación juzga por la prueba
- AC-03: La documentación incluye la comparación
"""


def _phase_line(index: int, created: list[str], modified: list[str] | None = None,
                deleted: list[str] | None = None, plan_phase: int | None = None) -> str:
    line = {"phase": f"fase-{index}", "phase_index": index, "agent": "AG-01", "status": "ok",
            "files_created": created, "files_modified": modified or [], "files_deleted": deleted or []}
    if plan_phase is not None:
        line["plan_phase"] = plan_phase
    return json.dumps(line)


@pytest.fixture
def server() -> FastMCP:
    mcp = FastMCP("plan-comparison-test")
    register_implement_context_tools(mcp, ROOT)
    return mcp


async def _aggregate(server: FastMCP, args: dict) -> dict:
    async with Client(server) as client:
        result = await client.call_tool("aggregate_phase_outputs", args, raise_on_error=False)
    return result.structured_content or {}


# ── AC-01: cada fase frente a su fase del plan ───────────────────────


def test_the_block_lists_extra_and_missing_files_counts_deletions_and_folders():
    expected = [f"server/m{i}.py" for i in range(8)]
    block = generate_phase_delta(
        phase_number=1, phase_name="Base", phase_status="complete",
        files_created=[f"server/x{i}.py" for i in range(7)], files_modified=[],
        files_deleted=["server/m0.py"], plan_files_expected=expected,
    )
    assert "Archivos adicionales (7)" in block and all(f"`server/x{i}.py`" in block for i in range(7))
    assert "Archivos esperados no tocados (7)" in block and all(f"`server/m{i}.py`" in block for i in range(1, 8))
    assert "`server/m0.py`" not in block.split("Archivos esperados no tocados")[1]  # borrado = tocado
    assert NO_PLAN_COMPARISON in generate_phase_delta(phase_number=1, phase_name="x", phase_status="complete")
    # Rutas normalizadas y carpetas: «server/vistas/» la cubre un fichero de dentro.
    assert compare_files(["./server/c.py", "server/vistas/lista.py"], ["server/c.py", "server/vistas/"]) == ([], [])
    assert compare_files(["server/c.py"], ["server/vistas/"]) == (["server/c.py"], ["server/vistas/"])
    # Muchos ficheros: el bloque enseña 50 y el total, y no pierde la otra lista por el tope de palabras.
    big = generate_phase_delta(phase_number=1, phase_name="x", phase_status="complete",
                               files_created=[f"n{i}.py" for i in range(600)], plan_files_expected=["falta.py"])
    assert "Archivos adicionales (600)" in big and "y 550 más" in big and "`falta.py`" in big


async def test_each_task_is_compared_with_the_plan_phase_it_names_by_number(server):
    content = "\n".join([
        _phase_line(1, ["server/a.py"], ["server/b.py"], plan_phase=1),
        _phase_line(4, ["server/c.py", "server/vistas/lista.py", "server/extra.py"], plan_phase=2),
    ])
    out = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": content, "plan_content": PLAN})
    first, second = out["phase_deltas"]
    assert "Sin deltas" in first  # la Fase 1, no la Fase 0 que va primero en el plan
    assert "Archivos adicionales (1): `server/extra.py`" in second  # phase_index 4 ≠ plan_phase 2
    # Solo las fases ejecutadas: ni la Fase 0 ni la de la otra UC «faltan».
    assert out["plan_comparison"] == {
        "available": True, "phases": [1, 2],
        "expected": ["server/a.py", "server/b.py", "server/c.py", "server/vistas/"],
        "extra": ["server/extra.py"], "missing": [],
    }


async def test_without_plan_phase_or_plan_lines_there_is_nothing_to_compare(server):
    content = _phase_line(1, ["server/a.py"])  # sin plan_phase: el orden de la skill no es la fase del plan
    out = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": content, "plan_content": PLAN})
    assert NO_PLAN_PHASE in out["phase_deltas"][0] and out["plan_comparison"]["available"] is False
    tagged = _phase_line(1, ["server/a.py"], plan_phase=2)
    no_files = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": tagged,
                                         "plan_content": PLAN.replace("**Ficheros:** server/c.py, server/vistas/\n", "")})
    assert NO_PLAN_COMPARISON in no_files["phase_deltas"][0]
    fenced = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": tagged,
                                       "plan_content": "# Plan\n```\n" + PLAN + "```\n"})
    assert fenced["plan_comparison"]["available"] is False
    old = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": tagged})
    assert "no llegó el plan" in old["phase_deltas"][0] and old["plan_comparison"]["available"] is False


async def test_a_retried_phase_does_not_report_the_other_attempts_files_as_missing(server):
    content = "\n".join([_phase_line(1, ["server/a.py"], plan_phase=1), _phase_line(1, ["server/b.py"], plan_phase=1)])
    out = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": content, "plan_content": PLAN})
    assert all("Sin deltas" in block for block in out["phase_deltas"])
    assert out["plan_comparison"]["missing"] == [] and out["plan_comparison"]["extra"] == []


def test_comparison_not_available_is_not_a_deviation():
    prd = f"""## Implementation Status

### Implementation Status — UC-701
**Timestamp:** 2026-11-19T00:00:00Z
**Branch:** feat/x

#### Fase 1: Base
- **Estado:** complete
- **Deltas vs plan:** {NO_PLAN_COMPARISON}
"""
    [status] = parse_implementation_status(prd, "UC-701")
    assert status.overall_status == "conforme"


# ── AC-02: el criterio, por su prueba ────────────────────────────────


def test_the_criteria_lines_prd_writes_are_read_and_status_sections_are_not():
    assert AC_LINE_PATTERN.match("- [ ] **AC-01**: Texto").group(1, 2) == ("AC-01", "Texto")
    assert AC_LINE_PATTERN.match("- AC-07: Texto").group(1) == "AC-07"
    criteria = _extract_ac_from_prd(PRD, "UC-12601")
    assert [c["ac_id"] for c in criteria] == ["AC-01", "AC-02", "AC-03"]
    assert criteria[0]["description"] == "El estado de cada fase muestra lo que sobra y lo que falta"
    assert [c["ac_id"] for c in _extract_ac_from_prd(PRD, "UC-12")] == ["AC-01"]  # no abre UC-12601
    # Lo entregado que escribe el engine («Comportamiento entregado») no son criterios.
    with_status = PRD + "\n## Implementation Status\n\n### Implementation Status — UC-12601\n\n" \
        "#### Comportamiento entregado\n\n- **AC-01**: Compara cada fase\n- **AC-04**: Algo que no es criterio\n"
    assert [c["ac_id"] for c in _extract_ac_from_prd(with_status, "UC-12601")] == ["AC-01", "AC-02", "AC-03"]
    story = "### US-126: Puerta\nComo dijo UC-12204, …\n#### UC-12601: Uno\n- AC-01: x\n| UC-12602 | Dos |\n" \
        "## Implementation Status\n### Implementation Status — UC-12699\n"
    assert _find_ucs_for_us(story, "US-126") == ["UC-12601", "UC-12602"]  # ni UC-12204 ni UC-12699


def test_a_criterion_passes_only_by_its_tagged_test():
    results = json.dumps({"uc_id": "UC-12601", "results": [
        {"id": "AC-01", "scenario": "lista sobrantes", "status": "PASS"},
        {"id": "AC-02", "scenario": "juzga por prueba", "status": "FAIL", "error": "esperaba ACCEPTED"},
    ]})
    # Aunque el código nombre los tres criterios, cuenta la prueba.
    code_index = {"server/x.py": "# AC-01 AC-02 AC-03"}
    out = run_acceptance_check_from_content(prd_content=PRD, item_id="UC-12601", code_index=code_index,
                                            results_content=results)
    by_ac = {c["ac_id"]: c for c in out["uc_results"][0]["criteria"]}
    assert out["method"] == "results" and "note" not in out
    assert by_ac["AC-01"]["verdict"] == "ACCEPTED"
    assert by_ac["AC-02"]["verdict"] == "REJECTED" and "esperaba ACCEPTED" in by_ac["AC-02"]["reason"]
    assert by_ac["AC-03"]["verdict"] == "REJECTED" and by_ac["AC-03"]["reason"].startswith("Sin prueba")
    heuristic = run_acceptance_check_from_content(prd_content=PRD, item_id="UC-12601", code_index=code_index)
    assert heuristic["method"] == "heuristic" and "results.json" in heuristic["note"]


def test_a_results_file_that_cannot_be_read_is_an_error_not_the_old_search():
    code_index = {"server/x.py": "# AC-01 AC-02 AC-03"}
    for bad in ('{"uc_id": "UC-12601", "results": [{"id": "AC-01", "status": "FA', '{"results": 5}', "true", "[]",
                '{"results": [{"status": "PASS"}]}'):
        out = run_acceptance_check_from_content(prd_content=PRD, item_id="UC-12601", code_index=code_index,
                                                results_content=bad)
        assert out.get("code") == "INVALID_RESULTS", (bad, out)


def test_the_latest_run_wins_ids_are_normalized_and_a_skip_is_not_a_pass():
    runs = json.dumps([
        {"uc_id": "UC-12601", "results": [{"id": "AC-01", "status": "FAIL", "error": "viejo"}]},
        {"uc_id": "UC-12601", "results": [{"id": " AC-1 ", "status": "PASS"}, {"id": "AC-02", "status": "SKIP"}]},
    ])
    out = run_acceptance_check_from_content(prd_content=PRD, item_id="UC-12601", code_index={}, results_content=runs)
    by_ac = {c["ac_id"]: c for c in out["uc_results"][0]["criteria"]}
    assert by_ac["AC-01"]["verdict"] == "ACCEPTED"  # la ejecución más reciente manda
    assert by_ac["AC-02"]["verdict"] == "REJECTED" and "SKIP" in by_ac["AC-02"]["reason"]


# ── Segunda vuelta de la revisión de la PR #398 ──────────────────────


async def test_a_bad_plan_phase_never_drops_the_line(server):
    lines = [_phase_line(1, ["server/a.py"], plan_phase=1),
             json.dumps({**json.loads(_phase_line(2, ["server/roto.py"])), "status": "error", "plan_phase": "{plan_phase}"}),
             json.dumps({**json.loads(_phase_line(3, ["server/c.py"])), "plan_phase": "Fase 2"}),
             json.dumps({**json.loads(_phase_line(4, ["server/d.py"])), "plan_phase": "2.1"})]
    entries = parse_phase_outputs("\n".join(lines))
    assert [e.plan_phase for e in entries] == [1, None, 2, None]  # las cuatro líneas siguen
    out = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": "\n".join(lines), "plan_content": PLAN})
    assert out["overall_status"] == "error" and len(out["phase_deltas"]) == 4  # la fase fallida sigue ahí
    assert NO_PLAN_PHASE in out["phase_deltas"][1]
    missing = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": _phase_line(1, ["a.py"], plan_phase=9),
                                        "plan_content": PLAN})
    assert "no tiene una única «Fase 9»" in missing["phase_deltas"][0]  # el motivo verdadero


def test_the_phase_outputs_validator_accepts_plan_phase(tmp_path):
    jsonl = tmp_path / "phase_outputs.jsonl"
    jsonl.write_text(json.dumps({"schema_version": 1, **json.loads(_phase_line(1, ["server/a.py"], plan_phase=2))}) + "\n")
    run = subprocess.run(["node", str(ROOT / ".quality/scripts/validate-phase-outputs.mjs"), str(jsonl)],
                         capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr


def test_regeneration_says_why_a_uc_is_pending_and_keeps_the_old_results_format():
    assert _results_for_check('{"uc_id": "UC-1", "results": []}')[0] is not None
    assert _results_for_check('{"criteria": [{"ac": "AC-01"}]}') == (
        None, "results.json en el formato anterior (sin «results»): juzgado por la búsqueda del id")
    assert _results_for_check('{"results": [').__getitem__(0) == '{"results": ['  # roto: se pasa y la comprobación lo rechaza
    assert _results_for_check(None) == (None, "")


def test_criterion_ids_are_whole_a_reopened_section_does_not_repeat_and_prefixed_ids_open():
    prd = """### US-20: Algo
#### UC-501: Uno
- AC-01: Lo primero queda
- AC-02.1.1: Un subapartado que no es un criterio
- **AC-03b**: Tampoco
#### UC-501 — Schema (resumen)
- AC-01: Lo primero queda
### MGR-US-21: Con prefijo
#### UC-601: Otra
- AC-01: Algo queda
"""
    assert [c["ac_id"] for c in _extract_ac_from_prd(prd, "UC-501")] == ["AC-01"]
    assert _find_ucs_for_us(prd, "US-21") == ["UC-601"]  # «MGR-US-21» nombra US-21


def test_an_empty_results_file_is_an_error_and_the_newest_run_wins_by_time():
    out = run_acceptance_check_from_content(prd_content=PRD, item_id="UC-12601", code_index={"x.py": "AC-01"},
                                            results_content="   ")
    assert out["code"] == "INVALID_RESULTS"
    runs = json.dumps([
        {"uc_id": "UC-12601", "timestamp": "2026-11-19T10:00:00Z", "results": [{"id": "AC-01", "status": "PASS"}]},
        {"uc_id": "UC-12601", "timestamp": "2026-11-18T10:00:00Z", "results": [{"id": "AC-01", "status": "FAIL"}]},
        {"timestamp": "2026-11-19T11:00:00Z", "results": [{"id": "AC-02", "status": "PASS"}]},
        {"uc_id": "UC-12601", "timestamp": "2026-11-19T09:00:00Z", "results": [{"id": "AC-02", "status": "FAIL"}]},
    ])
    by_ac = {c["ac_id"]: c for c in run_acceptance_check_from_content(
        prd_content=PRD, item_id="UC-12601", code_index={}, results_content=runs)["uc_results"][0]["criteria"]}
    assert by_ac["AC-01"]["verdict"] == "ACCEPTED"  # el PASS es más reciente que el FAIL aunque vaya antes
    assert by_ac["AC-02"]["verdict"] == "ACCEPTED"  # la ejecución sin uc_id, más reciente, manda


def test_title_form_plan_phase_and_the_reason_of_the_whole_comparison():
    from server.implement_context.phase_outputs import PhaseOutput

    base = {"phase": "x", "phase_index": 1, "agent": "AG-01", "status": "ok"}
    assert PhaseOutput(**base, plan_phase="Fase 1: Base").plan_phase == 1
    assert PhaseOutput(**base, plan_phase="Fase 2. Lectura").plan_phase == 2
    assert PhaseOutput(**base, plan_phase="2.1").plan_phase is None


async def test_plan_comparison_says_its_true_reason(server):
    untagged = _phase_line(1, ["server/a.py"])
    no_plan = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": untagged})
    assert "no llegó el plan" in no_plan["plan_comparison"]["reason"] and "no llegó el plan" in no_plan["phase_deltas"][0]
    with_plan = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": untagged, "plan_content": PLAN})
    assert with_plan["plan_comparison"]["reason"] == NO_PLAN_PHASE
    missing = await _aggregate(server, {"feature_slug": "uc-701", "plan_content": PLAN,
                                        "phase_outputs_content": _phase_line(1, ["a.py"], plan_phase=9)})
    assert "«Fase 9»" in missing["plan_comparison"]["reason"]
