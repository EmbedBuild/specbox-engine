"""UC-9302 (US-93): cada hook avisa o bloquea por el canal que llega.

- AC-01: las órdenes destructivas se impiden antes de ejecutarse y `--force-with-lease` pasa.
- AC-02: commit en main, evidencia inválida y lint se comprueban antes del commit y lo impiden.
- AC-03: los avisos que no bloquean llegan al agente como nota.
- AC-04: ningún hook registrado termina con un código que ni bloquea ni llega al agente
  (tests/hooks/hook-channels.test.mjs, hook a hook, lanzado aquí dentro de pytest).
- AC-05: el informe de impacto dice qué impediría cada hook en cada repo antes de propagar.
Las sesiones reales de Claude Code están en doc/research/hooks-que-no-saltaban/sesion-real-canales.md.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENGINE_ROOT = Path(__file__).parent.parent
RESEARCH = ENGINE_ROOT / "doc" / "research" / "hooks-que-no-saltaban"
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node no está disponible")
@pytest.mark.parametrize("suite", ["hook-channels", "quality-first-guard", "hook-input-shape"])
def test_suites_de_node(suite):
    res = subprocess.run(
        [NODE, "--test", f"tests/hooks/{suite}.test.mjs"], cwd=ENGINE_ROOT, capture_output=True, text=True, timeout=300
    )
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


def test_ac02_las_comprobaciones_de_commit_corren_antes_del_commit():
    settings = json.loads((ENGINE_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre = [h["command"] for g in settings["hooks"]["PreToolUse"] if g["matcher"] == "Bash" for h in g["hooks"]]
    post = [h["command"] for g in settings["hooks"]["PostToolUse"] if g["matcher"] == "Bash" for h in g["hooks"]]
    for hook in ("commit-spec-guard", "pre-commit-lint", "e2e-gate", "app-docs-sync-guard"):
        assert any(hook in c for c in pre), f"{hook} no corre antes del commit"
        assert not any(hook in c for c in post), f"{hook} sigue corriendo después del commit"


def test_ac01_ac03_sesiones_reales_documentadas():
    sesiones = (RESEARCH / "sesion-real-canales.md").read_text(encoding="utf-8")
    for pieza in ("GUARDIA DE CALIDAD", "COMMIT BLOQUEADO", "LINT:", "--force-with-lease", "SPEC GUARD: el commit sigue"):
        assert pieza in sesiones


def test_ac05_el_informe_dice_que_impediria_en_cada_repo():
    informe = (RESEARCH / "README.md").read_text(encoding="utf-8")
    seccion = informe[informe.index("## Después de UC-9302") :]
    assert "### Qué impediría hoy en cada repo" in seccion
    for repo in ("engine", "manager", "cloud", "site", "projects"):
        assert f"| {repo} (" in seccion
    assert "### Antes de propagar" in seccion


def test_el_registro_de_lecturas_no_se_versiona():
    assert "read_tracker.jsonl" in (ENGINE_ROOT / ".quality" / ".gitignore").read_text(encoding="utf-8")
