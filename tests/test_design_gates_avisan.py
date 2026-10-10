"""UC-9103 (US-91): las puertas de diseño existentes avisan y bloquean de verdad.

- AC-01: un agente que escribe una página de interfaz sin diseño recibe el aviso en la misma sesión.
  Lo prueba la suite de Node del hook (tests/hooks/design-gate.test.mjs), lanzada aquí dentro de pytest.
- AC-02: el Paso 3 de /implement genera las pantallas que faltan con la cadena de /plan (validación del
  prompt, pipeline v2 y marca de candidato), no llamando a Stitch directamente.
- AC-03: el agente de interfaz y el design-to-code de /implement no copian valores del candidato:
  colores, tipografía y espaciado salen de los tokens del sistema (D18).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
IMPLEMENT = (ENGINE_ROOT / ".claude" / "skills" / "implement" / "SKILL.md").read_text(encoding="utf-8")
UIUX = (ENGINE_ROOT / "agents" / "uiux-designer.md").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _section(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end)]


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
def test_ac01_el_hook_avisa_con_la_entrada_real_de_claude_code():
    res = subprocess.run(
        [NODE, "--test", "tests/hooks/design-gate.test.mjs"],
        cwd=ENGINE_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


class TestPaso3UsaLaCadenaDePlan:
    PASO_3 = _section(IMPLEMENT, "## Paso 3: Generar Diseños en Stitch", "## Paso 3.5")

    def test_ac02_valida_genera_con_v2_y_marca_candidato(self):
        for pieza in (
            "validate_stitch_prompt",
            "stitch_generate_screen_v2",
            "stitch_fetch_screen_code",
            "html_banner",
            "/design-review brief",
        ):
            assert pieza in self.PASO_3, f"el Paso 3 no usa {pieza}"

    def test_ac02_no_llama_a_stitch_directamente(self):
        assert "mcp__stitch__generate_screen_from_text(" not in self.PASO_3
        assert "**Prohibido aquí:** `mcp__stitch__generate_screen_from_text`" in self.PASO_3


class TestValoresDeLosTokens:
    def test_ac03_el_agente_de_interfaz_no_copia_el_candidato(self):
        assert "fielmente" not in UIUX
        assert "Nunca es fuente de valores" in UIUX
        assert "design-system.tokens.json" in UIUX and "D18" in UIUX
        assert "NO copiar colores, fuentes, espaciados ni radios del HTML candidato" in UIUX

    def test_ac03_el_design_to_code_toma_los_valores_del_sistema(self):
        paso_4 = _section(IMPLEMENT, "## Paso 4: Design-to-Code", "### 4.3 Traceability comment")
        assert "Ningun valor visual se copia del HTML" in paso_4
        assert "Leer HTML y extraer: layout, componentes, colores, espaciado, tipografia" not in paso_4
        assert "design-system.tokens.json" in paso_4
