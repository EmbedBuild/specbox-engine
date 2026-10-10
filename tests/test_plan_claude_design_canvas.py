"""UC-9201 (US-92): /plan crea un lienzo de Claude Design por feature con el sistema de diseño del proyecto.

- AC-01: un único lienzo por feature, dos artboards por pantalla (1440 y 390) y la dirección anotada en
  el plan. El esqueleto lo hace `canvas.mjs scaffold` (tests/design-review/canvas.test.mjs).
- AC-02: el sistema del proyecto queda instalado en el lienzo y, si publica componentes, se montan.
- AC-03: cada artboard parte del brief de /design-review.
- AC-04: sin la herramienta Artifact, sin la plantilla Design o sin sesión de claude.ai, /plan dice
  cuál falta y sigue con Stitch.
"""

import json
from pathlib import Path

from fastmcp import Client, FastMCP

from server.tools.claude_design import register_claude_design_tools

ENGINE_ROOT = Path(__file__).parent.parent
PLAN = (ENGINE_ROOT / ".claude" / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
CANVAS_REF = (ENGINE_ROOT / ".claude" / "skills" / "design-review" / "reference" / "canvas.md").read_text(encoding="utf-8")
PASO = PLAN[PLAN.index("### 6.0b Lienzo de Claude Design") : PLAN.index("### 6.0 Detectar Proyecto Stitch")]
CRITICA = PLAN[PLAN.index("### 6.4b") : PLAN.index("### 6.5")]


class TestPaso60b:
    def test_ac01_un_lienzo_por_feature_con_el_esqueleto(self):
        assert "Un lienzo por feature" in PASO
        assert "nunca se crea otro" in PASO
        assert "canvas.mjs scaffold" in PASO
        assert "1440 y 390" in PASO

    def test_ac01_la_direccion_va_al_plan(self):
        assert "Anotar en el plan" in PASO
        fuente = PLAN[PLAN.index("## Fuente de diseño") : PLAN.index("## Fases de Implementación")]
        assert "Lienzo de Claude Design" in fuente
        assert "| Pantalla | Artboard 1440 | Artboard 390 | Brief |" in fuente

    def test_ac02_sistema_instalado_y_componentes_reales(self):
        for pieza in ("veg.claude_design.designSystem", "copias_del_sistema", "sin declarar variables", "<x-import component-from-global-scope"):
            assert pieza in PASO, pieza
        assert "nunca imitaciones" in PASO

    def test_ac03_sin_brief_no_hay_artboard(self):
        assert "Sin brief no" in PASO and "hay artboard" in PASO
        assert "[DATO REAL" in PASO

    def test_ac04_dice_que_falta_y_sigue_con_stitch(self):
        for motivo in ("no tiene la herramienta Artifact", "La plantilla Design no está disponible", "No hay sesión de claude.ai"):
            assert motivo in PASO, motivo
        assert "se sigue con Stitch (6.0a), sin fallar" in PASO

    def test_designsync_ya_no_es_el_camino_del_lienzo(self):
        assert "**No** se usa `DesignSync`" in PASO
        assert "claude_design_sync_design_system" not in PASO

    def test_la_critica_alcanza_al_lienzo_sin_abrirlo(self):
        assert "todo artboard de un lienzo de Claude Design" in CRITICA
        assert "copia congelada" in CRITICA
        assert "solo se critica cuando el usuario" not in CRITICA


def test_la_referencia_explica_el_esqueleto():
    seccion = CANVAS_REF[CANVAS_REF.index("## El lienzo de una feature (UC-9201)") : CANVAS_REF.index("## `/design-review import")]
    for pieza in ("Main.dc.html", "designSystems", "sin_brief", "pantallas", "<dc-import>"):
        assert pieza in seccion, pieza


async def _status(tmp_path: Path, settings: dict) -> dict:
    (tmp_path / ".claude").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".claude" / "settings.local.json").write_text(json.dumps(settings), encoding="utf-8")
    mcp = FastMCP("test")
    register_claude_design_tools(mcp, tmp_path)
    async with Client(mcp) as client:
        result = await client.call_tool("claude_design_status", {"project": "p", "project_root": str(tmp_path)})
    return result.data if isinstance(result.data, dict) else json.loads(result.content[0].text)


async def test_status_da_el_sistema_publicado_para_el_lienzo(tmp_path: Path):
    url = "https://claude.ai/artifact/RdNh3zEkgd71XiR2TMR23M"
    st = await _status(tmp_path, {"veg": {"providers": ["claude_design"], "claude_design": {"designSystem": url}}})
    assert st["design_system_artifact"] == url
    assert "6.0b" in st["canvas_next"]


async def test_status_sin_sistema_publicado_dice_como_publicarlo(tmp_path: Path):
    st = await _status(tmp_path, {"veg": {"providers": ["claude_design"]}})
    assert st["design_system_artifact"] is None
    assert "/visual-setup 2.9.3" in st["canvas_next"]
