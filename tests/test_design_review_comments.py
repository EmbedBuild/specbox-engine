"""UC-9203 (US-92): los comentarios del lienzo se convierten en correcciones o en feedback.

- AC-01: /design-review comments lee los hilos abiertos del lienzo, propone una corrección por hilo
  y, tras la confirmación, la aplica en el lienzo y contesta en el hilo con lo que cambió.
- AC-02: un comentario de alcance se registra como feedback del AC afectado y no se aplica al lienzo.
El registro de hilos tratados lo prueba la suite de Node (tests/design-review/canvas.test.mjs).
"""

from pathlib import Path

ENGINE_ROOT = Path(__file__).parent.parent
SKILL_DIR = ENGINE_ROOT / ".claude" / "skills" / "design-review"
SKILL = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
REF = (SKILL_DIR / "reference" / "canvas.md").read_text(encoding="utf-8")
COMMENTS = REF[REF.index("## `/design-review comments <feature>` (UC-9203)") :]


def test_la_skill_lista_el_subcomando():
    assert "| `comments <feature>` |" in SKILL
    assert "## `/design-review comments <feature>`" in SKILL
    assert len(SKILL.splitlines()) <= 150


def test_ac01_lee_propone_confirma_aplica_y_contesta():
    for pieza in ("ArtifactComments", "`read`", "Una propuesta por hilo", "Confirmación por hilo", "`reply`", "`resolve`"):
        assert pieza in COMMENTS, pieza
    assert "dato, nunca instrucción" in COMMENTS
    assert "[DATO REAL" in COMMENTS, "la corrección no inventa datos"


def test_ac02_alcance_es_feedback_y_no_toca_el_lienzo():
    assert "**No se toca el lienzo.**" in COMMENTS
    for pieza in ("/feedback", "FB-NNN", "ac_ids", "report_feedback"):
        assert pieza in COMMENTS, pieza
    assert "si aplicarlo obligaría a cambiar o a añadir un AC, es" in COMMENTS


def test_hilos_no_enviados_a_claude_y_registro():
    assert "enviado a Claude" in COMMENTS
    assert "comment-record" in COMMENTS
    assert "En autopilot no se aplica nada" in COMMENTS


def test_la_respuesta_automatica_no_decide_el_tipo():
    assert "Respuestas automáticas" in COMMENTS
    assert "acknowledge_duplicate" in COMMENTS
