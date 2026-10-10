"""UC-9003 (US-90): la skill /design-review y su contrato.

- AC-01: el subcomando brief, con su referencia, toma audiencia y JTBD del canon y del PRD.
- AC-02: sin brief no hay dirección, prompt ni código de pantalla.
- AC-03: la dirección se revisa contra los defaults y respeta tokens y DESIGN.md.
- AC-04: atribución y licencia de cada fuente; SKILL.md de 150 líneas como máximo; una referencia
  por subcomando.
- AC-05: la skill entra en el inventario que publica el engine (la extensión tiene su test propio).
"""

import re
from pathlib import Path

from server.site_publish.inventory import parse_skills

ENGINE_ROOT = Path(__file__).parent.parent
SKILL_DIR = ENGINE_ROOT / ".claude" / "skills" / "design-review"
SKILL_MD = SKILL_DIR / "SKILL.md"

SOURCES = {
    # proyecto: (licencia, fichero de licencia)
    "frontend-design": ("Apache-2.0", "licenses/Apache-2.0.txt"),
    "Impeccable": ("Apache-2.0", "licenses/Apache-2.0.txt"),
    "make-interfaces-feel-better": ("MIT", "licenses/MIT-make-interfaces-feel-better.txt"),
    "emil-design-eng": ("MIT", "licenses/MIT-emilkowalski-skills.txt"),
    "taste-skill": ("MIT", "licenses/MIT-taste-skill.txt"),
}


def _text(rel: str) -> str:
    return (SKILL_DIR / rel).read_text(encoding="utf-8")


def _frontmatter(content: str) -> str:
    assert content.startswith("---"), "SKILL.md tiene que empezar por frontmatter YAML"
    return content.split("---", 2)[1]


class TestEstructura:
    def test_skill_md_cabe_en_150_lineas(self):
        assert len(SKILL_MD.read_text(encoding="utf-8").splitlines()) <= 150

    def test_frontmatter(self):
        front = _frontmatter(SKILL_MD.read_text(encoding="utf-8"))
        assert re.search(r"^name:\s*design-review\s*$", front, re.M)
        assert re.search(r"^description:", front, re.M)
        assert re.search(r"^context:\s*direct\s*$", front, re.M)

    def test_una_referencia_por_subcomando(self):
        content = SKILL_MD.read_text(encoding="utf-8")
        for sub, ref in (
            ("brief", "reference/brief.md"),
            ("direction", "reference/direction.md"),
            ("verify", "reference/verify.md"),
        ):
            assert f"`{sub} <pantalla>`" in content, f"falta el subcomando {sub}"
            assert f"]({ref})" in content, f"SKILL.md no enlaza {ref}"
            assert (SKILL_DIR / ref).is_file(), f"no existe {ref}"

    def test_enlaces_relativos_existen(self):
        for md in [SKILL_MD, *sorted((SKILL_DIR / "reference").glob("*.md")), SKILL_DIR / "THIRD_PARTY_NOTICES.md"]:
            for target in re.findall(r"\]\(((?:\.\./)?[\w./-]+\.(?:md|txt))\)", md.read_text(encoding="utf-8")):
                assert (md.parent / target).resolve().is_file(), f"{md.name}: enlace roto a {target}"


class TestBriefYDireccion:
    def test_brief_hereda_del_canon_sin_repreguntar(self):
        brief = _text("reference/brief.md")
        for fuente in ("app_prd.md", "app_market.md", "get_inheritable_values_tool"):
            assert fuente in brief
        assert "[DATO REAL" in brief, "los datos que faltan se marcan, no se inventan"

    def test_sin_brief_no_hay_diseno(self):
        content = SKILL_MD.read_text(encoding="utf-8")
        assert "Regla de oro: sin brief no hay diseño" in content
        direction = _text("reference/direction.md")
        assert "Brief obligatorio" in direction

    def test_direccion_revisa_defaults_y_respeta_el_sistema(self):
        direction = _text("reference/direction.md")
        assert "defaults.md" in direction
        assert "design-system.tokens.json" in direction
        assert "no inventa valores" in direction

    def test_la_rubrica_prohibe_inventar_datos(self):
        rubric = _text("reference/rubric.md")
        assert "No se inventan datos" in rubric
        assert "scrollWidth" in rubric


class TestAtribucion:
    def test_cada_fuente_tiene_autor_origen_y_licencia(self):
        notices = _text("THIRD_PARTY_NOTICES.md")
        for proyecto, (licencia, fichero) in SOURCES.items():
            fila = next((linea for linea in notices.splitlines() if linea.startswith(f"| {proyecto}")), None)
            assert fila, f"falta {proyecto} en la tabla de THIRD_PARTY_NOTICES.md"
            assert "https://github.com/" in fila, f"{proyecto}: falta el origen"
            assert licencia in fila and fichero in fila, f"{proyecto}: falta la licencia"
            assert (SKILL_DIR / fichero).is_file(), f"{proyecto}: no existe {fichero}"

    def test_textos_de_licencia(self):
        assert "Apache License" in _text("licenses/Apache-2.0.txt")
        for fichero in ("MIT-make-interfaces-feel-better.txt", "MIT-emilkowalski-skills.txt", "MIT-taste-skill.txt"):
            texto = _text(f"licenses/{fichero}")
            assert texto.startswith("MIT License") and "Copyright (c)" in texto

    def test_avisa_de_que_el_contenido_esta_modificado(self):
        assert "Modificado" in _text("THIRD_PARTY_NOTICES.md")


def test_entra_en_el_inventario_publicado():
    skills = {s.skill_key: s for s in parse_skills(ENGINE_ROOT / ".claude" / "skills")}
    assert "design-review" in skills
    assert skills["design-review"].command == "/design-review"
    assert skills["design-review"].description
