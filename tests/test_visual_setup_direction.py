"""UC-9002 (US-90): /visual-setup propone una dirección propia en lugar de estéticas prefabricadas.

- AC-01: sin combinaciones fijas; dirección (paleta de 4 a 6 colores con función, tipografías con
  papel, concepto de composición) derivada de la audiencia y los JTBD del proyecto.
- AC-02: antes de presentarla, se compara con los valores por defecto de la categoría y cada
  coincidencia se sustituye o se justifica por escrito.
- AC-03: la dirección llega al DESIGN.md con una sección de lo que se rehúsa, y un proyecto con
  tokens del sistema conserva sus valores sin cambios.
"""

from pathlib import Path

from server.design_md.generator import GeneratorInputs, generate_design_md
from server.design_md.io import compute_signature
from server.design_system import parse_system_tokens
from server.tools.stitch_v2 import _pick_brand_kit_path

ENGINE_ROOT = Path(__file__).parent.parent
VISUAL_SETUP = (ENGINE_ROOT / ".claude" / "skills" / "visual-setup" / "SKILL.md").read_text(encoding="utf-8")
TINTA = Path(__file__).parent / "fixtures" / "design_system" / "tinta.design-system.tokens.json"

# Brand kit con el formato que escribe /visual-setup (Paso 2.4) tras la dirección.
BRAND_KIT = """# Brand: Paddock

> Motociclismo. Dirección: la oficina de carrera durante el fin de semana

## Paleta

| Rol | Hex | Función |
|-----|-----|---------|
| Fondo | #FFFFFF | Fondo de página |
| Superficie | #EDEFF1 | Columna lateral y fila seleccionada |
| Texto | #1E2329 | Texto principal |
| Texto secundario | #59616A | Metadatos |
| Acción | #1E2329 | Botón principal y foco |
| Pendiente | #F25C05 | Falta verificar |
| Borde | #D5D9DD | Separadores |

## Tipografía

- **Heading**: Saira Condensed (600/700)
- **Body**: Atkinson Hyperlegible (400, 16px base)

## Lo que se rehúsa

- Tres tarjetas KPI con barras de progreso: un titular con lo que hay que hacer
- Inter y un botón azul: Saira Condensed y la acción en asfalto
"""


class TestSinPresets:
    def test_ac01_no_quedan_las_esteticas_prefabricadas(self):
        for preset in ("Calm Enterprise", "Bold Startup", "Developer DX", "#4F46E5 (Indigo)", "Preset de estetica"):
            assert preset not in VISUAL_SETUP, f"sigue el preset {preset}"

    def test_ac01_la_direccion_sale_de_la_audiencia_y_tiene_sus_piezas(self):
        seccion = VISUAL_SETUP[VISUAL_SETUP.index("**Pregunta 2: Dirección visual") : VISUAL_SETUP.index("**Pregunta 3:")]
        for pieza in ("app_prd.md", "app_market.md", "JTBD", "4 a 6 colores con su función",
                      "familias con su papel", "Concepto de composición"):
            assert pieza in seccion, f"falta «{pieza}» en la Pregunta 2"
        assert "design-review/reference/direction.md" in seccion

    def test_ac02_revision_contra_los_defaults_con_motivo_escrito(self):
        seccion = VISUAL_SETUP[VISUAL_SETUP.index("**Pregunta 2: Dirección visual") : VISUAL_SETUP.index("**Pregunta 3:")]
        for default in ("Inter, Roboto, Arial o Space Grotesk", "degradado violeta", "crema con",
                        "terracota", "negro con verde ácido"):
            assert default in seccion, f"falta el default «{default}»"
        assert "defaults.md" in seccion
        assert "el motivo queda escrito" in seccion
        assert "Default que aparecía | Qué hice | Por qué" in seccion


class TestDesignMd:
    def test_ac03_la_paleta_y_las_tipografias_del_brand_kit_llegan_al_design_md(self):
        doc = generate_design_md(GeneratorInputs(project_root=None, project_name="Paddock", brand_kit_text=BRAND_KIT))
        colors = doc.front_matter.colors
        assert colors.primary == "#1E2329"
        assert colors.background == "#FFFFFF"
        assert colors.surface == "#EDEFF1"
        assert colors.text_primary == "#1E2329"
        assert colors.text_secondary == "#59616A"
        assert colors.border == "#D5D9DD"
        fam = doc.front_matter.typography.fontFamily
        assert (fam.heading, fam.body) == ("Saira Condensed", "Atkinson Hyperlegible")

    def test_ac03_lo_que_se_rehusa_queda_en_el_design_md(self):
        doc = generate_design_md(GeneratorInputs(project_root=None, project_name="Paddock", brand_kit_text=BRAND_KIT))
        assert "**Lo que se rehúsa (dirección del proyecto)**" in doc.dos_and_donts
        assert "- Inter y un botón azul: Saira Condensed y la acción en asfalto" in doc.dos_and_donts

    def test_ac03_sin_seccion_no_se_inventa_nada(self):
        kit = BRAND_KIT.split("## Lo que se rehúsa")[0]
        doc = generate_design_md(GeneratorInputs(project_root=None, project_name="Paddock", brand_kit_text=kit))
        assert "Lo que se rehúsa" not in doc.dos_and_donts

    def test_ac03_con_tokens_del_sistema_el_design_md_no_cambia(self):
        tokens = parse_system_tokens(TINTA.read_text(encoding="utf-8"), source="design-system.tokens.json")
        sin_kit = generate_design_md(GeneratorInputs(project_root=None, project_name="demo", system_tokens=tokens))
        con_kit = generate_design_md(
            GeneratorInputs(project_root=None, project_name="demo", system_tokens=tokens, brand_kit_text=BRAND_KIT)
        )
        assert compute_signature(sin_kit) == compute_signature(con_kit)
        assert "Lo que se rehúsa" not in con_kit.dos_and_donts


class TestBrandKitPath:
    def test_lee_el_brand_kit_que_escribe_visual_setup(self, tmp_path: Path):
        assert _pick_brand_kit_path(tmp_path) == tmp_path / "doc" / "brand" / "brand_kit" / "SKILL.md"

    def test_un_brand_kit_plano_antiguo_sigue_mandando(self, tmp_path: Path):
        flat = tmp_path / "doc" / "brand" / "brand_kit.md"
        flat.parent.mkdir(parents=True)
        flat.write_text("- primary: #112233\n", encoding="utf-8")
        assert _pick_brand_kit_path(tmp_path) == flat

    def test_visual_setup_pasa_el_fichero_que_escribe(self):
        assert "brand_kit_content=<doc/brand/brand_kit/SKILL.md>" in VISUAL_SETUP
