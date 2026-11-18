"""US-122 / UC-12211 — el PRD cambia en la misma PR que el código: la parte del servidor.

- **AC-02**: una UC se marca «sin PRD» con motivo (update_uc no_prd_reason) y el marcador de UC
  activa lo lleva, para que prd-sync-guard la deje pasar.
- **AC-03**: el estado de implementación incluye, por criterio, el comportamiento entregado.
- **AC-04**: el marcador dice para qué medidas la UC es anterior a la regla.
- La búsqueda del PRD del servidor y la del hook dan lo mismo (lib/prd-locate.mjs).
El hook se prueba en ``tests/hooks/prd-sync-guard.test.mjs``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from server.coordination import enforcement as pol
from server.prd_writer import append_implementation_status, find_prd_path
from server.tools.spec_driven import start_uc
from server.tools.spec_mutations import update_uc

ENGINE = Path(__file__).resolve().parent.parent


class _Ctx:
    def __init__(self, config):
        self._config = config

    async def get_state(self, key):
        return self._config


CTX = _Ctx({"backend_type": "freeform", "content_only": True})
US = {"id": "us7", "name": "US-07: Pagos", "description": "", "state": "backlog", "labels": ["US"], "meta": {"us_id": "US-07"}}
UC = {"id": "uc701", "name": "UC-701: Cobrar", "description": "Cobrar con tarjeta", "state": "backlog", "labels": ["UC"],
      "parent_id": "us7", "meta": {"uc_id": "UC-701", "us_id": "US-07"}}
AC = {"id": "ac1", "name": "[AC-01] El cobro queda registrado", "state": "backlog", "labels": ["AC"], "parent_id": "uc701",
      "meta": {"ac_id": "AC-01"}}


async def test_a_uc_is_marked_without_prd_with_a_reason_and_the_marker_carries_it():
    """AC-02."""
    board = json.dumps([US, UC, AC])
    corto = await update_uc("ff", "UC-701", CTX, no_prd_reason="nada", items_content=board)
    assert corto["code"] == "REASON_REQUIRED"
    motivo = "Arreglo de la CI, sin cambio de comportamiento"
    out = await update_uc("ff", "UC-701", CTX, no_prd_reason=motivo, items_content=board)
    assert "no_prd_reason" in out["updated_fields"]
    started = await start_uc("ff", "UC-701", CTX, items_content=out["items_content"])
    assert started["active_uc_marker"]["no_prd_reason"] == motivo
    cleared = await update_uc("ff", "UC-701", CTX, no_prd_reason="", items_content=out["items_content"])
    again = await start_uc("ff", "UC-701", CTX, items_content=cleared["items_content"])
    assert "no_prd_reason" not in again["active_uc_marker"]


async def test_the_marker_says_which_measures_the_uc_predates():
    """AC-04: una UC abierta cuando spec_in_pr pasó a «block», sin cambios desde entonces."""
    from server.tools.enforcement import _freeform_open_ucs

    board = json.dumps([US, UC, AC])
    uc = next(u for u in await _freeform_open_ucs(board) if u["uc_id"] == "UC-701")
    stored, _ = pol.with_mode(None, "spec_in_pr", "block", by="ana", at="2026-11-18T10:00:00+00:00",
                              backend_type="freeform", open_ucs=pol.open_uc_fingerprints([uc]))
    out = await start_uc("ff", "UC-701", CTX, items_content=board, policy_content=json.dumps(stored))
    assert out["active_uc_marker"]["predates_rule"] == ["spec_in_pr"]

    changed = json.dumps([US, UC, {**AC, "name": "[AC-01] El cobro queda registrado con su recibo"}])
    out2 = await start_uc("ff", "UC-701", CTX, items_content=changed, policy_content=json.dumps(stored))
    assert "predates_rule" not in out2["active_uc_marker"]
    sin = await start_uc("ff", "UC-701", CTX, items_content=board)
    assert "predates_rule" not in sin["active_uc_marker"]


def test_the_implementation_status_says_what_each_criterion_does(tmp_path):
    """AC-03."""
    prd = tmp_path / "prd.md"
    prd.write_text("# PRD\n")
    assert append_implementation_status(
        prd, "UC-701", "feature/UC-701-x", ["#### Fase 1\n- src/x.ts"],
        timestamp="2026-11-18T10:00:00Z",
        behaviors={"AC-02": "El recibo   aparece en el correo", "AC-01": "El cobro queda en el tablero"},
    )
    text = prd.read_text()
    block = text[text.index("#### Comportamiento entregado"):]
    assert block.splitlines()[2:4] == ["- **AC-01**: El cobro queda en el tablero", "- **AC-02**: El recibo aparece en el correo"]
    assert "src/x.ts" in text  # ficheros y decisiones siguen


CASES = [
    ({"doc/prd/pagos/prd.md": "# PRD\n## US-07\n", "doc/prd/otro/prd.md": "# Otro US-09\n"}, "UC-701", "US-07"),
    ({"doc/prd/pagos/prd.md": "# PRD\n## US-07\n"}, "pagos", ""),
    ({"doc/prd/pagos.md": "# PRD\n"}, "pagos", ""),
    ({"doc/prds/pagos_prd.md": "# PRD\n", "doc/prd/pagos/prd.md": "x"}, "pagos", ""),
    ({"doc/prds/us_07_prd.md": "# PRD\n"}, "", "US-07"),
    ({"doc/prds/unico.md": "# PRD\n"}, "", "US-99"),
    ({"doc/prd/a/prd.md": "US-07", "doc/prd/b/prd.md": "US-07"}, "", "US-07"),
    ({}, "x", "US-07"),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="sin node")
@pytest.mark.parametrize(("files", "feature", "us_id"), CASES)
def test_the_hook_finds_the_same_prd_as_the_server(tmp_path, files, feature, us_id):
    for rel, content in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(content)
    found = find_prd_path(tmp_path, feature=feature or None, us_id=us_id or None)
    expected = str(found.relative_to(tmp_path)) if found else None
    lib = ENGINE / ".claude" / "hooks" / "lib" / "prd-locate.mjs"
    code = (
        f"import('{lib}').then(m => process.stdout.write(JSON.stringify("
        f"m.locatePrd({{ root: {json.dumps(str(tmp_path))}, feature: {json.dumps(feature)}, usId: {json.dumps(us_id)} }}))))"
    )
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    assert js == expected
