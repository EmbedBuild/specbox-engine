"""UC-9102 (US-91): /implement verifica cada pantalla tras el design-to-code.

- AC-01: la verificación revisa también el pulido medible (áreas de 44 px, estados deshabilitado y
  pulsado, movimiento reducido y cifras tabulares) con su ubicación, sin una pasada de pulido aparte.
  Las reglas las prueba la suite de Node de verify (tests/design-review/verify.test.mjs).
- AC-02: /implement ejecuta la verificación de UC-9101 y adjunta veredicto, capturas y hallazgos como
  evidencia de los AC de la UC.
- AC-03: en modo aviso el veredicto va a la PR y a la evidencia sin impedir el merge; cada proyecto pasa
  a modo bloqueante desde su configuración (lo prueba tests/hooks/design-review-gate.test.mjs).
- AC-04: la ronda de corrección no inventa datos: marcador visible y `dato_sin_fuente` en la medición
  siguiente.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
IMPLEMENT = (ENGINE_ROOT / ".claude" / "skills" / "implement" / "SKILL.md").read_text(encoding="utf-8")
VERIFY_SCRIPT = (ENGINE_ROOT / ".claude" / "skills" / "design-review" / "scripts" / "verify.mjs").read_text(
    encoding="utf-8"
)
PASO_65 = IMPLEMENT[IMPLEMENT.index("## Paso 6.5: Verificación de pantallas") : IMPLEMENT.index("## Paso 7: QA")]
NODE = shutil.which("node")


def test_ac01_el_pulido_va_en_las_reglas_y_no_en_una_pasada_aparte():
    for regla in ("cifras-tabulares", "estados-controles", "movimiento-reducido"):
        assert f"'{regla}'" in VERIFY_SCRIPT
        assert f"`{regla}`" in PASO_65
    assert "const TAP = 44;" in VERIFY_SCRIPT
    assert "isMobile: true, hasTouch: true" in VERIFY_SCRIPT
    assert "no es una pasada aparte" in PASO_65


def test_ac02_ejecuta_verify_y_adjunta_la_evidencia():
    assert "design-review/scripts/verify.mjs" in PASO_65
    assert "subagente aislado" in PASO_65
    assert '"type": "screenshot"' in PASO_65
    assert 'attach_evidence(board_id, uc_id, "uc", "ag09"' in PASO_65
    assert "{pantalla}.verify.md" in PASO_65


def test_ac03_modo_aviso_por_defecto_y_bloqueante_desde_la_configuracion():
    assert "specbox.design_review.mode" in PASO_65
    assert "| `warn` (por defecto) |" in PASO_65
    assert "design-review-gate.mjs" in PASO_65
    assert "Cambiarlo no exige tocar esta skill" in PASO_65
    assert "## Design Review" in IMPLEMENT, "la PR lleva el veredicto"


def test_ac04_la_correccion_no_inventa_datos():
    assert "[DATO REAL: …]" in PASO_65
    assert "--previous" in PASO_65 and "--sources" in PASO_65
    assert "dato_sin_fuente" in PASO_65
    assert "No hay\n   ronda 2" in PASO_65 or "No hay ronda 2" in PASO_65


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
def test_ac03_el_hook_aplica_el_modo():
    res = subprocess.run(
        [NODE, "--test", "tests/hooks/design-review-gate.test.mjs"],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]
