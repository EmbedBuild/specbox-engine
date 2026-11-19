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

from server.delta_generator import NO_PLAN_COMPARISON, generate_phase_delta
from server.prd_parser import parse_implementation_status
from server.tools.acceptance import AC_LINE_PATTERN, _extract_ac_from_prd, run_acceptance_check_from_content
from server.tools.implement_context_tools import register_implement_context_tools

ROOT = Path(__file__).resolve().parent.parent
PLAN = """# Plan
### Fase 1: Base
**Criterios:** UC-701 AC-01
**Ficheros:** server/a.py, server/b.py
### Fase 2: Lectura
**Criterios:** UC-701 AC-02
**Ficheros:** server/c.py
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


def _phase_line(index: int, created: list[str], modified: list[str] | None = None, deleted: list[str] | None = None) -> str:
    return json.dumps({"phase": f"fase-{index}", "phase_index": index, "agent": "AG-01", "status": "ok",
                       "files_created": created, "files_modified": modified or [], "files_deleted": deleted or []})


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


def test_the_block_lists_every_extra_and_missing_file_and_counts_deletions():
    expected = [f"server/m{i}.py" for i in range(8)]
    block = generate_phase_delta(
        phase_number=1, phase_name="Base", phase_status="complete",
        files_created=[f"server/x{i}.py" for i in range(7)], files_modified=[],
        files_deleted=["server/m0.py"], plan_files_expected=expected,
    )
    assert all(f"`server/x{i}.py`" in block for i in range(7))  # sin el recorte de 5 de antes
    assert all(f"`server/m{i}.py`" in block for i in range(1, 8))
    assert "`server/m0.py`" not in block.split("Archivos esperados no tocados")[1]  # borrado = tocado
    assert NO_PLAN_COMPARISON in generate_phase_delta(phase_number=1, phase_name="x", phase_status="complete")


async def test_each_phase_is_compared_with_its_phase_of_the_plan(server):
    content = "\n".join([
        _phase_line(1, ["server/a.py"], ["server/b.py"]),
        _phase_line(2, ["server/c.py", "server/extra.py"]),
    ])
    out = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": content, "plan_content": PLAN})
    first, second = out["phase_deltas"]
    assert "Sin deltas" in first
    assert "Archivos adicionales: `server/extra.py`" in second
    assert out["plan_comparison"] == {"available": True, "expected": ["server/a.py", "server/b.py", "server/c.py"],
                                      "extra": ["server/extra.py"], "missing": []}
    old = await _aggregate(server, {"feature_slug": "uc-701", "phase_outputs_content": content})
    assert all(NO_PLAN_COMPARISON in block for block in old["phase_deltas"])
    assert old["plan_comparison"]["available"] is False


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


def test_the_criteria_lines_prd_writes_are_read_and_sections_match_whole_ids():
    assert AC_LINE_PATTERN.match("- [ ] **AC-01**: Texto").group(1, 2) == ("AC-01", "Texto")
    assert AC_LINE_PATTERN.match("- AC-07: Texto").group(1) == "AC-07"
    criteria = _extract_ac_from_prd(PRD, "UC-12601")
    assert [c["ac_id"] for c in criteria] == ["AC-01", "AC-02", "AC-03"]
    assert criteria[0]["description"] == "El estado de cada fase muestra lo que sobra y lo que falta"
    assert [c["ac_id"] for c in _extract_ac_from_prd(PRD, "UC-12")] == ["AC-01"]  # no abre UC-12601


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
