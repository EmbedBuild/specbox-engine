"""UC-9301 (US-93): las condiciones de los hooks casan con lo que vigilan.

- AC-01: ninguna condición del engine ni de la plantilla se escribe como regex, y cada hook casa con lo
  que vigila (tests/hooks/settings-if-syntax.test.mjs); los hooks leen `tool_input`
  (tests/hooks/hook-input-shape.test.mjs). Las dos suites de Node se lanzan aquí dentro de pytest.
- AC-02: la sesión real (antes y después) queda en doc/research/hooks-que-no-saltaban/sesion-real/.
- AC-03: el informe de impacto, en doc/research/hooks-que-no-saltaban/README.md.
- AC-04: la guía, en doc/guides/hooks.md, con ejemplos comprobados que funcionan y que no.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
RESEARCH = ENGINE_ROOT / "doc" / "research" / "hooks-que-no-saltaban"
GUIDE = (ENGINE_ROOT / "doc" / "guides" / "hooks.md").read_text(encoding="utf-8")
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
@pytest.mark.parametrize("suite", ["settings-if-syntax", "hook-input-shape"])
def test_ac01_suites_de_node(suite):
    res = subprocess.run(
        [NODE, "--test", f"tests/hooks/{suite}.test.mjs"], cwd=ENGINE_ROOT, capture_output=True, text=True, timeout=120
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


def test_ac02_la_sesion_real_deja_su_material():
    real = RESEARCH / "sesion-real"
    assert (real / "pasos.txt").read_text(encoding="utf-8").count("\n") >= 13
    assert (real / "disparos-antiguas.tsv").read_text(encoding="utf-8").strip() == ""
    nuevas = (real / "disparos-nuevas.tsv").read_text(encoding="utf-8").strip().splitlines()
    assert len(nuevas) == 21
    for f in ("settings-antiguas.json", "settings-nuevas.json"):
        json.loads((real / f).read_text(encoding="utf-8"))


def test_ac03_el_informe_dice_que_avisa_que_bloquea_y_en_que_repo():
    informe = (RESEARCH / "README.md").read_text(encoding="utf-8")
    for pieza in ("Hook por hook", "Qué habría pasado hoy en cada repo", "exit 1", "Recomendación"):
        assert pieza in informe
    for repo in ("engine", "manager", "cloud", "site", "projects"):
        assert f"| {repo} (" in informe, f"falta el repo {repo}"


def test_ac04_la_guia_tiene_ejemplos_que_funcionan_y_que_no():
    assert "| Un `git commit` | `Bash(*git commit*)` | `Bash(.*git commit.*)` |" in GUIDE
    assert "| Escribir en `src/` del proyecto | `Write(src/**)` | `Write(src/.*)` |" in GUIDE
    assert "tool_input" in GUIDE and "exit 2" in GUIDE
