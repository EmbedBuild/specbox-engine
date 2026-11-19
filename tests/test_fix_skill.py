"""UC-12701 (US-127) — /fix: un arreglo con una UC y un criterio.

/fix es una skill (instrucciones para el agente): estas pruebas comprueban que su texto lleva las
puertas que piden los criterios y en el orden que exigen las medidas de EP-20, y que /manual-test
pasa por /fix solo con tablero. El límite de alcance tiene sus pruebas en
`tests/hooks/fix-scope.test.mjs` y la rama `fix/`, en `tests/hooks/uc-lifecycle-guard.test.mjs`.

- AC-01: crea la UC con un criterio, sin PRD ni plan, en la historia indicada o en la de bugs.
- AC-02: rama de la UC y prueba que falla antes del arreglo.
- AC-03: start_uc, recibo del criterio y complete_uc.
- AC-04: para y propone /prd con más de 5 ficheros, un contrato de API o una migración.
- AC-05: /manual-test arregla con /fix cuando hay tablero.
- AC-06: sin tablero, /manual-test arregla como hoy y /fix dice que necesita uno.
- AC-07: un bug que no se reproduce con una prueba no entra en /fix.
"""

from __future__ import annotations

import re
from pathlib import Path

from server.site_publish.inventory import parse_skills

ROOT = Path(__file__).resolve().parent.parent
FIX = (ROOT / ".claude/skills/fix/SKILL.md").read_text(encoding="utf-8")
MANUAL = (ROOT / ".claude/skills/manual-test/SKILL.md").read_text(encoding="utf-8")


def _pos(text: str, needle: str) -> int:
    i = text.find(needle)
    assert i >= 0, f"falta «{needle}»"
    return i


def test_fix_is_a_skill_the_inventory_and_the_extension_know():
    skills = {s.skill_key: s for s in parse_skills(ROOT / ".claude" / "skills")}
    assert skills["fix"].command == "/fix" and skills["fix"].description
    constants = (ROOT / "vscode-extension/src/constants.ts").read_text(encoding="utf-8")
    assert "'fix'" in constants
    assert "fix: 'pipeline'" in (ROOT / "vscode-extension/src/views/skill-categories.ts").read_text(encoding="utf-8")


def test_ac01_the_uc_goes_to_the_given_story_or_the_bugs_one_without_prd_or_plan():
    assert "«Arreglos sin PRD»" in FIX and "import_spec" in FIX and '"use_cases": []' in FIX
    # El id va explícito: en una historia vacía add_uc tomaría el siguiente número del tablero entero.
    assert re.search(r"Pásalo siempre en `uc_id`", FIX)
    assert "validate_ac_quality" in FIX and 'no_prd_reason="Arreglo con /fix' in FIX


def test_the_board_calls_go_in_the_order_the_measures_need():
    # spec_quality, ac_approval y spec_in_pr: el motivo sin PRD entra en el marcador con start_uc.
    order = ["add_uc(", "validate_ac_quality(", "update_uc(board_id, uc_id, no_prd_reason", "approve_criteria(",
             "start_uc(board_id, uc_id)", "mark_ac_batch(", 'move_uc(board_id, uc_id, "review")',
             "record_review_verdict(", "gh pr merge", "complete_uc("]
    positions = [_pos(FIX, step) for step in order]
    assert positions == sorted(positions), "los pasos del tablero no van en el orden que piden las medidas"
    # La aprobación la da la persona, desde la sesión principal.
    assert "AskUserQuestion" in FIX and "SUBAGENT_CANNOT_APPROVE" in FIX


def test_ac02_the_test_fails_first_and_goes_alone_on_the_fix_branch():
    assert _pos(FIX, "## Paso 1 — Reproducir el bug con una prueba") < _pos(FIX, "## Paso 2 — La historia")
    assert "falla por el bug" in FIX
    assert "git switch -c fix/UC-XXXX-<slug>" in FIX
    assert _pos(FIX, "Commit de **la prueba sola**") < _pos(FIX, "## Paso 6 — El arreglo")
    # Nunca en las carpetas de aceptación (son de AG-09a).
    assert "**nunca** en las de aceptación" in FIX and "tests/acceptance/" in FIX


def test_ac03_the_receipt_carries_the_test_and_the_files_before_the_ci():
    receipt = FIX[_pos(FIX, "mark_ac_batch(board_id, uc_id, results="):]
    assert '"type": "test"' in receipt and '"test":' in receipt and '"files":' in receipt
    assert "antes del CI y de la PR" in FIX
    assert "--paginate" in FIX and 'repo="<owner/repo>"' in FIX


def test_ac04_the_scope_check_runs_before_the_fix_commit_and_proposes_prd():
    assert _pos(FIX, "scripts/scope.mjs") < _pos(FIX, "commit del arreglo: `fix(UC-XXXX)")
    stop = FIX[_pos(FIX, "## Paso 8"):_pos(FIX, "## Paso 9")]
    assert "más de 5 ficheros" in stop and "contrato de API" in stop and "migración de datos" in stop
    assert "/prd" in stop and "release_uc" in stop and "No hagas commit del arreglo" in stop


def test_ac05_ac06_manual_test_uses_fix_only_with_a_board():
    assert "Skill" in MANUAL.split("---", 2)[1] and "mcp__SpecBox-MCP" in MANUAL.split("---", 2)[1]
    assert "**¿Hay tablero?**" in MANUAL
    step = MANUAL[_pos(MANUAL, "4. **Si FAIL/BUG detectado**"):_pos(MANUAL, "### 4.3")]
    assert "**Con tablero y el arreglo en el código del repositorio**: arreglarlo con **/fix**" in step
    assert "**Sin tablero, o si el arreglo es de configuración o de datos**" in step
    assert "se fusiona antes de seguir" in step
    assert "| # | Bug | Severidad | Commit fix | UC | PR | Estado |" in MANUAL


def test_ac06_fix_without_a_board_says_it_needs_one():
    no_board = FIX[_pos(FIX, "## Paso 0 — ¿Hay tablero?"):_pos(FIX, "## Paso 1")]
    assert "/fix necesita un tablero" in no_board and "sin error" in no_board


def test_ac07_a_bug_without_a_reproducing_test_goes_to_feedback():
    step = FIX[_pos(FIX, "**Si no se puede reproducir con una prueba**"):_pos(FIX, "**Primera medida del alcance.**")]
    assert "/feedback" in step and "no lo toma" in step
    # Y es antes de tocar el tablero: no deja UC.
    assert _pos(FIX, "**Si no se puede reproducir con una prueba**") < _pos(FIX, "## Paso 2 — La historia")
