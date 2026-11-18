"""US-123 / UC-12303 — las alternativas descartadas quedan junto a la spec.

- **AC-01**: las plantillas de PRD incluyen la sección «Alternativas descartadas», con la opción, el
  motivo y quién la descartó.
- **AC-02**: /prd rellena esa sección con las alternativas planteadas en la conversación o en el
  discovery, y escribe «Ninguna» si no las hubo.
- **AC-03**: /plan muestra un aviso antes de generar el plan si un PRD con el formato nuevo no incluye
  la sección; un PRD anterior no genera el aviso.
"""

from __future__ import annotations

from pathlib import Path

from server.tools.prd_format import FORMAT_MARK, check_prd_format_content
from tests.test_prd_format import TEMPLATES, V2

ROOT = Path(__file__).resolve().parent.parent
PRD_SKILL = (ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")
PLAN_SKILL = (ROOT / ".claude/skills/plan/SKILL.md").read_text(encoding="utf-8")


def _codes(text: str) -> list[str]:
    return [w["code"] for w in check_prd_format_content(text)["warnings"]]


def test_ac01_each_template_lists_option_reason_and_who():
    for name, body in TEMPLATES.items():
        assert "## Alternativas descartadas" in body, name
        assert "| Opción | Motivo | Quién la descartó |" in body, name
        assert "«Ninguna»" in body, name


def test_ac02_prd_asks_for_them_and_writes_ninguna_when_there_were_none():
    assert "5. Que alternativas se plantearon y por que se descartaron?" in PRD_SKILL
    assert "las del discovery cuentan" in PRD_SKILL
    assert "Si no hubo ninguna, escribir\n> «Ninguna»: la sección no se quita." in PRD_SKILL
    assert "`missing_alternatives`: falta «Alternativas descartadas»" in PRD_SKILL


def test_ac03_a_new_prd_without_the_section_warns():
    without = V2.replace("## Alternativas descartadas\nNinguna\n\n", "")
    assert _codes(without) == ["missing_alternatives"]
    assert _codes(V2) == []  # «Ninguna» vale


def test_ac03_an_older_prd_without_the_section_does_not_warn():
    old = V2.replace(FORMAT_MARK + "\n", "").replace("## Alternativas descartadas\nNinguna\n\n", "")
    assert check_prd_format_content(old) == {**check_prd_format_content(old), "format_version": 1, "warnings": []}


def test_ac03_plan_shows_the_warning_before_planning():
    step = PLAN_SKILL[PLAN_SKILL.index("### 0.5 Formato del PRD (UC-12304)"):PLAN_SKILL.index("## Paso 1: Explorar Proyecto")]
    assert "`missing_alternatives`" in step and "Enseña cada aviso al usuario antes de seguir" in step
