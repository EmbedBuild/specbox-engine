"""UC-9204 (US-92): cada proyecto tiene un sistema de diseño utilizable desde el lienzo.

- AC-01: /visual-setup publica el sistema desde los tokens del proyecto con un tokens.css que declara
  sus variables: un lienzo lo instala y sus artboards no declaran variables. Lo prueba la suite de Node
  del generador (tests/visual-setup/ds-artifact.test.mjs), lanzada aquí dentro de pytest.
- AC-02: con componentes compilados, el sistema publica el bundle y su guía dice cómo cargarlo.
- AC-03: el camino que sigue /visual-setup sale de una prueba real documentada.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
VISUAL_SETUP = (ENGINE_ROOT / ".claude" / "skills" / "visual-setup" / "SKILL.md").read_text(encoding="utf-8")
GUIDE = (ENGINE_ROOT / "doc" / "guides" / "design-system-tokens.md").read_text(encoding="utf-8")
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
def test_suite_de_node_del_generador():
    res = subprocess.run(
        [NODE, "--test", "tests/visual-setup/ds-artifact.test.mjs"],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


class TestPaso293:
    PASO = VISUAL_SETUP[VISUAL_SETUP.index("### 2.9.3") : VISUAL_SETUP.index("## Paso 3: Configurar Google Stitch")]

    def test_ac01_publica_desde_los_tokens_con_artifact(self):
        for pieza in ("ds-artifact.mjs build", "design-system.tokens.json", "Design System", "veg.claude_design.designSystem"):
            assert pieza in self.PASO, pieza

    def test_ac01_no_exige_un_sistema_compilado(self):
        assert "Basta con `design-system.tokens.json`" in self.PASO

    def test_ac02_compila_los_componentes_como_script_clasico(self):
        for pieza in ("--format=iife", "--global-name", "window.React", "--bundle-js", "--types"):
            assert pieza in self.PASO, pieza

    def test_reglas_del_tipo_que_muerden(self):
        # .d.ts no es un tipo servido; la página vuelve a guardar el índice al abrirse.
        assert '"contentType": "text/plain"' in self.PASO
        assert "la página lo vuelve a guardar" in self.PASO

    def test_ac03_el_camino_de_designsync_remite_a_la_prueba_real(self):
        assert "sistema-instalable.md" in self.PASO
        assert (ENGINE_ROOT / "doc" / "research" / "claude-design-import" / "sistema-instalable.md").is_file()


def test_ac02_la_guia_explica_como_cargar_los_componentes():
    seccion = GUIDE[GUIDE.index("## Usarlos desde un lienzo de Claude Design") :]
    for pieza in ("tokens.css", "--global-name", "x-import", "Consuming this system", "generated from tokens.json"):
        assert pieza in seccion, pieza
