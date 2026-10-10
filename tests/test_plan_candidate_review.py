"""UC-9004 (US-90): /plan critica cada candidato de Stitch o Claude Design antes de guardarlo.

- AC-01: tras generar cada pantalla, /plan obtiene su captura y un revisor aislado la puntúa con la
  rúbrica y lista sus defectos con severidad.
- AC-02: con «Needs changes», una sola edición con los defectos concretos; se conserva la versión
  con mejor puntuación y la revisión queda junto al diseño.
- AC-03: en autopilot el veredicto avisa sin detener el plan y queda anotado en el plan.
"""

from pathlib import Path

ENGINE_ROOT = Path(__file__).parent.parent
PLAN = (ENGINE_ROOT / ".claude" / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
RUBRIC = ENGINE_ROOT / ".claude" / "skills" / "design-review" / "reference" / "rubric.md"


def _seccion(titulo: str, siguiente: str) -> str:
    inicio = PLAN.index(titulo)
    return PLAN[inicio : PLAN.index(siguiente, inicio)]


CRITICA = _seccion("### 6.4b Criticar el candidato", "### 6.5 Registrar prompts usados")


def test_la_critica_va_despues_de_guardar_el_html_y_antes_de_registrar_prompts():
    assert PLAN.index("### 6.4 Obtener y guardar HTML") < PLAN.index("### 6.4b") < PLAN.index("### 6.5")


def test_ac01_captura_y_revisor_aislado_con_la_rubrica():
    assert "stitch_fetch_screen_image" in CRITICA
    assert "{screen_name}.png" in CRITICA
    assert "subagente" in CRITICA and "no** reciba el" in CRITICA
    assert "design-review/reference/rubric.md" in CRITICA
    assert RUBRIC.is_file(), "la rúbrica de /design-review tiene que existir"
    assert "por severidad" in CRITICA


def test_ac02_una_sola_edicion_mejor_version_y_revision_junto_al_diseno():
    assert "**una sola** edición" in CRITICA
    assert "stitch_edit_screen" in CRITICA
    assert "Se conserva la versión con mejor total" in CRITICA
    assert "{screen_name}.review.md" in CRITICA
    assert "no pide datos que el brief no da" in CRITICA


def test_ac03_autopilot_avisa_sin_detener_y_se_anota_en_el_plan():
    assert "avisa y no detiene el plan" in CRITICA
    assert "Revisión de candidatos" in CRITICA
    resumen = PLAN[PLAN.index("## Output Final") :]
    assert "### Revisión de candidatos (6.4b)" in resumen


def test_sin_brief_no_hay_prompt_y_el_lote_tambien_se_critica():
    assert "Sin brief no se construye el prompt" in PLAN
    assert "/design-review brief <pantalla>" in PLAN
    assert "pasa por la crítica de 6.4b" in PLAN


def test_claude_design_se_critica_sobre_la_copia_congelada():
    # UC-9201 (US-92): el lienzo ya no se critica solo a petición; se critica su copia congelada,
    # sin abrirlo ni capturarlo.
    assert "todo artboard de un lienzo de Claude Design" in CRITICA
    assert "copia congelada" in CRITICA
