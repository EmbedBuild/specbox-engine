"""UC-9202 (US-92): las pantallas aprobadas del lienzo llegan a la carpeta de diseño con su origen.

- AC-01: `/design-review import` deja fuente, vista congelada que se abre sin conexión y una vista del
  lienzo con dirección y versión. Lo prueba la suite de Node del script (tests/design-review/canvas.test.mjs),
  lanzada aquí dentro de pytest.
- AC-02: una pantalla importada satisface la puerta de diseño igual que una de Stitch
  (tests/hooks/design-gate.test.mjs).
- AC-03: sin cambios, cero escrituras; con cambios, solo lo que cambió (canvas.test.mjs).
- AC-04: ni la vista congelada ni el código que sale de ella llevan piezas del motor del lienzo: el
  script y la puerta de diseño buscan las mismas, y /implement parte de la vista congelada.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
SKILL_DIR = ENGINE_ROOT / ".claude" / "skills" / "design-review"
CANVAS = (SKILL_DIR / "scripts" / "canvas.mjs").read_text(encoding="utf-8")
GATE = (ENGINE_ROOT / ".claude" / "hooks" / "design-gate.mjs").read_text(encoding="utf-8")
IMPLEMENT = (ENGINE_ROOT / ".claude" / "skills" / "implement" / "SKILL.md").read_text(encoding="utf-8")
PLAN = (ENGINE_ROOT / ".claude" / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
@pytest.mark.parametrize("suite", ["tests/design-review/canvas.test.mjs", "tests/hooks/design-gate.test.mjs"])
def test_suites_de_node(suite):
    res = subprocess.run([NODE, "--test", suite], cwd=ENGINE_ROOT, capture_output=True, text=True, timeout=180)
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


def _trace_names(source: str) -> list[str]:
    block = source[source.index("ENGINE_TRACES = [") :]
    block = block[: block.index("];")]
    return re.findall(r"\['([^']+)',", block)


def test_ac04_el_script_y_la_puerta_buscan_las_mismas_piezas_del_motor():
    script, gate = _trace_names(CANVAS), _trace_names(GATE)
    assert script == gate
    for pieza in ("support.js", "<x-dc>", "DCLogic", "<sc-for>", "<dc-import>", "<x-import>", "/_blob/"):
        assert pieza in script


def test_ac04_el_motor_no_entra_en_el_proyecto_ni_en_el_engine():
    assert "no se copia" in " ".join(line.lstrip("/ ") for line in CANVAS.splitlines()[:30])
    assert not list(ENGINE_ROOT.rglob("dc-runtime.js")), "el motor del lienzo no es nuestro: no se versiona"


def test_la_skill_documenta_el_subcomando_con_su_referencia():
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "`import <feature> [artboard…]`" in skill
    assert "](reference/canvas.md)" in skill
    ref = (SKILL_DIR / "reference" / "canvas.md").read_text(encoding="utf-8")
    for pieza in ("artifact-type/dc-runtime.js", "claude-design.json", "canvas.html", "faltan_blobs", "Aprobar es nombrar"):
        assert pieza in ref, pieza


def test_plan_e_implement_usan_la_vista_congelada():
    paso_4 = IMPLEMENT[IMPLEMENT.index("## Paso 4: Design-to-Code") : IMPLEMENT.index("### 4.0")]
    assert "vista congelada" in paso_4
    assert "/design-review import" in paso_4
    paso_6_4 = PLAN[PLAN.index("### 6.4 Obtener y guardar HTML") : PLAN.index("### 6.4b")]
    assert "/design-review import" in paso_6_4
    assert "se guardan con su `html_banner`" not in paso_6_4, "Claude Design ya no se guarda a mano"
