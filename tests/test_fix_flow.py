"""UC-12701 AC-01 y AC-03 — el recorrido de /fix con las tools reales, en un tablero FreeForm.

La secuencia es la que manda `.claude/skills/fix/SKILL.md` (Pasos 2 a 10), en su orden: la historia
de bugs se crea vacía, la UC nace con su id explícito y un criterio, sin PRD y con el criterio
aprobado, arranca, recibe su recibo con la prueba y los ficheros, pasa a revisión y se cierra con los
ficheros de su PR. Si una medida de EP-20 pidiera otro orden, esta prueba lo diría.
"""

from __future__ import annotations

import json

from server.tools.approval import approve_criteria
from server.tools.board_operations import validate_ac_quality
from server.tools.spec_driven import complete_uc, get_uc, get_us, import_spec, mark_ac_batch, move_uc, start_uc
from server.tools.spec_mutations import add_uc, update_uc
from tests.test_spec_gate_start_uc import CTX

CRITERION = "El total de la factura queda en 120,00 € con dos líneas de 60,00 €"
FILES = ["src/facturas/total.py", "tests/test_total.py"]


def _story(us_id: str, name: str = "Arreglos sin PRD") -> dict:
    return {"user_stories": [{
        "us_id": us_id, "name": name, "screens": "",
        "description": "Arreglos pequeños hechos con /fix: cada uno con su UC, su criterio y su prueba.",
        "exclusions": ["Funcionalidad nueva o cambios grandes: van por /prd"],
        "use_cases": [],
    }]}


async def test_the_fix_flow_leaves_a_closed_uc_with_its_criterion_and_receipt():
    # Un tablero con una historia de producto (US-30) y sin historia de bugs.
    board = (await import_spec("ff", _story("US-30", "Facturas"), CTX, items_content="[]"))["items_content"]

    # Paso 2: la historia de bugs, vacía, con el siguiente id libre.
    created = await import_spec("ff", _story("US-31"), CTX, items_content=board)
    assert created["created"]["us"] == 1 and created["created"]["uc"] == 0
    board = created["items_content"]

    # Paso 3: la UC con su id explícito (la serie de la historia empieza en UC-3101) y un criterio.
    uc = await add_uc("ff", "US-31", "Arreglo · el total de la factura sale a cero",
                      "Con dos líneas el total salía 0: se sumaba antes de cargar las líneas.",
                      [{"text": CRITERION, "verification": "automated_test"}], CTX,
                      uc_id="UC-3101", actor="Quien emite la factura", items_content=board)
    assert uc["uc_id"] == "UC-3101"
    board = uc["items_content"]
    quality = await validate_ac_quality("ff", CTX, uc_id="UC-3101", items_content=board)
    assert not quality.get("failed"), quality
    marked = await update_uc("ff", "UC-3101", CTX, no_prd_reason="Arreglo con /fix: el total sale a cero",
                             items_content=board)
    board = marked["items_content"]

    # Paso 4: la persona aprueba el criterio.
    approved = await approve_criteria("ff", CTX, uc_ids=["UC-3101"], approved_by="Ana",
                                      client_session_id="sess-fix", items_content=board)
    assert approved["success"] is True
    board = approved["items_content"]

    # Paso 5: arranca, con el motivo sin PRD en el marcador.
    started = await start_uc("ff", "UC-3101", CTX, items_content=board, client_session_id="sess-fix")
    assert started["status"] == "in_progress" and "AC_NOT_APPROVED" not in json.dumps(started)
    assert started["active_uc_marker"].get("no_prd_reason", "").startswith("Arreglo con /fix")
    board = started["items_content"]

    # Paso 9: el recibo (la prueba y los ficheros) y la revisión.
    receipt = {"ac_id": "AC-01", "passed": True, "evidence": {
        "type": "test", "label": "tests/test_total.py: test_total_con_dos_lineas",
        "detail": "falla antes del arreglo (a1b2c3d) y pasa después", "commit": "e4f5a6b", "repo": "Acme/facturas",
        "test": "pytest tests/test_total.py::test_total_con_dos_lineas", "files": FILES}}
    batch = await mark_ac_batch("ff", "UC-3101", [receipt], CTX, items_content=board)
    assert batch["passed"] == 1
    board = batch["items_content"]
    board = (await move_uc("ff", "UC-3101", "review", CTX, items_content=board))["items_content"]

    # Paso 10: el cierre con los ficheros de la PR.
    closed = await complete_uc("ff", "UC-3101", CTX, files=FILES, repo="Acme/facturas", items_content=board)
    assert closed.get("closed_files") == 2, closed
    board = closed["items_content"]

    # AC-03: la UC queda hecha y visible en su historia, con su criterio demostrado por la prueba.
    detail = await get_uc("ff", "UC-3101", CTX, items_content=board)
    assert detail["status"] == "done"
    [ac] = detail["acceptance_criteria"]
    assert ac["done"] and ac["test"] == "pytest tests/test_total.py::test_total_con_dos_lineas"
    assert sorted(ac["files"]) == sorted(FILES)
    story = await get_us("ff", "US-31", CTX, items_content=board)
    assert [u["uc_id"] for u in story["use_cases"]] == ["UC-3101"]
