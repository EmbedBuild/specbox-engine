"""UC-9104 (US-91): /design-review verify funciona en apps Flutter.

- AC-01: reglas de pulido y movimiento para Flutter (48 dp, curvas y duraciones, Material 3) y la
  skill elige la del stack (pubspec.yaml → Flutter; un destino .dart va por Flutter).
- AC-02: capturas a 390 y 820 con las pruebas de widgets, sin simulador. La integración real necesita
  flutter: tests/design-review/flutter.test.mjs con SPECBOX_FLUTTER="fvm flutter"; aquí se lanza la
  suite de Node y se comprueba la plantilla.
- AC-03: áreas táctiles por debajo de 48 dp y escala de texto anulada, con su ubicación.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
SKILL_DIR = ENGINE_ROOT / ".claude" / "skills" / "design-review"
FLUTTER_MD = (SKILL_DIR / "reference" / "flutter.md").read_text(encoding="utf-8")
TEMPLATE = (SKILL_DIR / "scripts" / "flutter" / "design_review_golden_test.dart.tmpl").read_text(encoding="utf-8")
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
def test_suite_de_node():
    res = subprocess.run(
        [NODE, "--test", "tests/design-review/flutter.test.mjs"],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


def test_ac01_reglas_para_flutter_y_eleccion_por_stack():
    for pieza in ("48 dp", "Material 3", "Durations.short4", "Curves.easeIn", "disableAnimationsOf", "TextScaler"):
        assert pieza in FLUTTER_MD, f"falta «{pieza}» en reference/flutter.md"
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "pubspec.yaml" in skill and "](reference/flutter.md)" in skill
    assert "endsWith('.dart')" in (SKILL_DIR / "scripts" / "verify.mjs").read_text(encoding="utf-8")


def test_ac02_la_plantilla_captura_dos_tamanos_solo_con_flutter_test():
    assert "Size(390, 844)" in TEMPLATE and "Size(820, 1180)" in TEMPLATE
    assert "matchesGoldenFile" in TEMPLATE
    imports = [line for line in TEMPLATE.splitlines() if line.startswith("import 'package:")]
    assert all(i.startswith(("import 'package:flutter/", "import 'package:flutter_test/")) for i in imports), imports
    for marcador in ("{{NAME}}", "{{IMPORTS}}", "{{SCREEN}}"):
        assert marcador in TEMPLATE
    assert "overflowed" in TEMPLATE and "FontLoader" in TEMPLATE


def test_ac03_las_reglas_dicen_donde():
    rules = (SKILL_DIR / "scripts" / "flutter-rules.mjs").read_text(encoding="utf-8")
    for regla in ("area-pulsacion", "escala-texto"):
        assert f"'{regla}'" in rules
    assert "linea: i + 1" in rules and "columna:" in rules
