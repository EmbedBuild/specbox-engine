"""UC-9101 (US-91): /design-review verify.

- AC-01 y AC-02: el script mide a 1440 y 390 y aplica las reglas con su ubicación. Lo prueba la suite
  de Node (tests/design-review/verify.test.mjs), que aquí se lanza dentro de pytest. La integración con
  navegador necesita Playwright (SPECBOX_PLAYWRIGHT o el del proyecto) y se salta si no está.
- AC-03: revisor aislado con la rúbrica de 8 criterios y veredicto con los tres problemas prioritarios.
- AC-04: sin dependencias nuevas: usa el Playwright del proyecto y, si no lo hay, sale con código 2.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
SKILL_DIR = ENGINE_ROOT / ".claude" / "skills" / "design-review"
SCRIPT = SKILL_DIR / "scripts" / "verify.mjs"
NODE_SUITE = ENGINE_ROOT / "tests" / "design-review" / "verify.test.mjs"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node no está disponible")

RULES = (
    "desbordamiento",
    "texto-degradado",
    "borde-lateral",
    "eyebrow",
    "transition-all",
    "emoji-icono",
    "contraste",
    "area-pulsacion",
    "cifras-tabulares",
    "estados-controles",
    "movimiento-reducido",
)


def _verify_md() -> str:
    return (SKILL_DIR / "reference" / "verify.md").read_text(encoding="utf-8")


@needs_node
def test_ac01_ac02_la_suite_de_node_pasa():
    res = subprocess.run(
        [NODE, "--test", str(NODE_SUITE)], cwd=ENGINE_ROOT, capture_output=True, text=True, timeout=300
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


def test_ac02_cada_regla_del_script_esta_documentada():
    script = SCRIPT.read_text(encoding="utf-8")
    reference = _verify_md()
    for rule in RULES:
        assert f"'{rule}'" in script, f"el script no conoce la regla {rule}"
        assert f"`{rule}`" in reference, f"reference/verify.md no explica {rule}"


def test_ac03_revisor_aislado_con_la_rubrica_y_tres_problemas():
    reference = _verify_md()
    assert "subagente" in reference and "Quien diseñó no se revisa" in reference
    assert "rubric.md" in reference
    assert "Tres problemas prioritarios" in reference
    assert "Block | Needs changes | Approve" in reference
    assert "{pantalla}.verify.md" in reference


def test_ac03_la_correccion_es_una_ronda_y_detecta_cifras_sin_fuente():
    reference = _verify_md()
    assert "No hay ronda 2" in reference
    assert "--previous" in reference and "--sources" in reference
    assert "dato_sin_fuente" in reference


@needs_node
def test_ac04_sin_playwright_sale_con_codigo_2_sin_instalar_nada(tmp_path: Path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "sin-playwright"}), encoding="utf-8")
    page = tmp_path / "p.html"
    page.write_text("<!doctype html><title>p</title><p>Hola</p>", encoding="utf-8")
    res = subprocess.run(
        [NODE, str(SCRIPT), str(page), "--out", str(tmp_path / "out")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert res.returncode == 2, res.stderr
    assert "no tiene Playwright" in res.stderr
    assert not (tmp_path / "node_modules").exists()


def test_ac04_el_script_no_trae_dependencias():
    script = SCRIPT.read_text(encoding="utf-8")
    imports = {line.split("from")[-1].strip(" ';") for line in script.splitlines() if line.startswith("import ")}
    assert imports <= {"node:module", "node:fs", "node:path", "node:url"}, imports
    assert "npm install" not in script and "npx" not in script
