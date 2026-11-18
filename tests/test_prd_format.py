"""US-123 / UC-12304 — el PRD dice qué; el plan, cómo.

- **AC-01**: las plantillas de PRD no incluyen «Stack técnico» ni «Archivos principales»; esa
  información aparece solo en el plan.
- **AC-02**: una restricción de implementación que el PRD necesite va en «Restricciones de
  implementación», marcada como opcional y propia del cambio.
- **AC-03**: /plan muestra un aviso si un PRD con el formato nuevo contiene rutas de fichero fuera de
  esa sección; un PRD anterior no genera el aviso.
- **AC-04**: cada PRD nuevo incluye la versión de su formato, y /plan y /implement leen sin errores
  los PRD que no la tienen (``prd-locate.mjs``, ``prd_writer`` y ``write_implementation_status`` con
  los dos formatos).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from server.prd_writer import append_implementation_status, find_prd_path
from server.tools.prd_format import (
    CURRENT_FORMAT,
    FORMAT_MARK,
    check_prd_format,
    check_prd_format_content,
    prd_format_version,
)

ROOT = Path(__file__).resolve().parent.parent
PRD_SKILL = (ROOT / ".claude/skills/prd/SKILL.md").read_text(encoding="utf-8")
PLAN_SKILL = (ROOT / ".claude/skills/plan/SKILL.md").read_text(encoding="utf-8")
IMPLEMENT_SKILL = (ROOT / ".claude/skills/implement/SKILL.md").read_text(encoding="utf-8")


def _templates() -> dict[str, str]:
    """Cada plantilla de PRD de la skill: de su título a su pie («*Generado: [fecha]*»). Los bloques
    de código de dentro (estado actual y propuesto) no la cortan."""
    out: dict[str, str] = {}
    for match in re.finditer(r"^## Template: (.+)$", PRD_SKILL, re.MULTILINE):
        start = PRD_SKILL.index("```markdown\n", match.end()) + len("```markdown\n")
        end = PRD_SKILL.index("*Generado: [fecha]*\n```", start)
        out[match.group(1)] = PRD_SKILL[start:end]
    return out


TEMPLATES = _templates()

V2 = f"""# PRD: Cobros
{FORMAT_MARK}

> Historia: **US-09**

## Resumen
Cobrar con tarjeta.

## Restricciones de implementación (opcional, de este cambio)
- El webhook sigue en `server/payments/webhook.py`: lo llama el proveedor.

### Detalle
- Y el contrato en `api/openapi.yaml`.

## Use Cases
### UC-901: Cobrar
- [ ] **AC-01**: El cobro queda registrado con su recibo

## Alternativas descartadas
Ninguna

## Pendiente de decidir
- Ninguno
"""


# ── Las plantillas ──────────────────────────────────────────────────


def test_the_three_templates_are_found():
    assert set(TEMPLATES) == {"PRD Spec-Driven", "PRD Feature (Freeform)", "PRD Tecnico"}


def test_ac01_no_stack_or_files_in_the_prd_templates_but_in_the_plan():
    for name, body in TEMPLATES.items():
        assert "Stack Tecnico" not in body and "Stack técnico" not in body, name
        assert "Archivos Principales" not in body and "Archivos principales" not in body, name
    assert "## Archivos a Crear/Modificar" in PLAN_SKILL
    assert "El stack y los ficheros salen de aquí" in PLAN_SKILL


def test_ac02_each_template_has_optional_restrictions_of_the_change():
    for name, body in TEMPLATES.items():
        assert "## Restricciones de implementación (opcional, de este cambio)" in body, name


def test_ac04_each_template_carries_its_format_and_passes_its_own_check():
    for name, body in TEMPLATES.items():
        assert body.splitlines()[1] == FORMAT_MARK, name  # justo debajo del título
        result = check_prd_format_content(body)
        assert result["format_version"] == CURRENT_FORMAT == 2, name
        assert result["warnings"] == [], (name, result["warnings"])


def test_prd_plan_and_implement_call_or_accept_the_format():
    """AC-03 y AC-04 en las skills: /prd y /plan llaman a la tool; /implement lee los dos formatos."""
    assert "## Paso 2.6: Comprobar el formato del PRD (UC-12304)" in PRD_SKILL
    assert "check_prd_format(prd_content=<texto del PRD>)" in PRD_SKILL
    assert "### 0.5 Formato del PRD (UC-12304)" in PLAN_SKILL
    assert "check_prd_format(prd_content=<texto del PRD>)" in PLAN_SKILL
    assert "Los dos formatos del PRD se leen igual (UC-12304)" in IMPLEMENT_SKILL


# ── check_prd_format ────────────────────────────────────────────────


def test_ac03_paths_inside_the_restrictions_do_not_warn():
    assert check_prd_format_content(V2)["warnings"] == []


def test_ac03_a_path_outside_the_restrictions_warns_with_its_line_and_section():
    text = V2.replace("Cobrar con tarjeta.", "Cobrar con tarjeta desde `web/src/lib/pay.ts`.")
    text = text.replace("### UC-901: Cobrar", "### UC-901: Cobrar (scripts/charge.sh)")
    warnings = check_prd_format_content(text)["warnings"]
    assert [(w["code"], w["section"], w["paths"]) for w in warnings] == [
        ("paths_outside_restrictions", "Resumen", ["web/src/lib/pay.ts"]),
        ("paths_outside_restrictions", "UC-901: Cobrar (scripts/charge.sh)", ["scripts/charge.sh"]),
    ]
    assert warnings[0]["line"] == text.splitlines().index("Cobrar con tarjeta desde `web/src/lib/pay.ts`.") + 1


def test_ac03_a_prd_without_the_mark_gets_no_warning():
    old = V2.replace(FORMAT_MARK + "\n", "").replace("Cobrar con tarjeta.", "Ver `server/x.py`. [POR DECIDIR: el proveedor]")
    old = old.replace("## Pendiente de decidir\n- Ninguno\n", "")
    result = check_prd_format_content(old)
    assert result["format_version"] == 1 and result["warnings"] == []
    assert "PRD anterior" in result["summary"]


def test_the_implementation_status_the_engine_appends_may_name_files():
    text = V2 + "\n---\n\n## Implementation Status\n\n### UC-901\n- Ficheros: `server/payments/charge.py`\n"
    assert check_prd_format_content(text)["warnings"] == []


def test_marks_without_their_section_warn_and_quoted_marks_do_not():
    text = V2.replace("## Pendiente de decidir\n- Ninguno\n", "").replace(
        "Cobrar con tarjeta.", "Cobrar con [POR DECIDIR: el proveedor]."
    )
    warnings = check_prd_format_content(text)["warnings"]
    assert [w["code"] for w in warnings] == ["missing_pending_section"]
    quoted = text.replace("[POR DECIDIR: el proveedor]", "la marca `[POR DECIDIR: …]`")
    assert check_prd_format_content(quoted)["warnings"] == []


def test_the_format_mark_is_read_only_near_the_title():
    assert prd_format_version(V2) == 2
    assert prd_format_version("# PRD\n" + "\n" * 20 + FORMAT_MARK) == 1
    assert prd_format_version("# PRD\n<!--   @specbox:prd   format=\"3\"   -->\n") == 3


async def test_the_tool_is_pure_and_checks_its_input():
    assert (await check_prd_format(V2))["format_version"] == 2
    assert (await check_prd_format(None))["code"] == "VALIDATION_FAILED"  # type: ignore[arg-type]


# ── AC-04: los PRD de los dos formatos se siguen encontrando y escribiendo ──


@pytest.mark.parametrize("text", [V2, V2.replace(FORMAT_MARK + "\n", "")], ids=["formato 2", "formato 1"])
def test_ac04_both_formats_are_found_and_take_the_implementation_status(tmp_path, text):
    prd = tmp_path / "doc" / "prd" / "cobros" / "prd.md"
    prd.parent.mkdir(parents=True)
    prd.write_text(text, encoding="utf-8")
    for found in (find_prd_path(tmp_path, feature="cobros"), find_prd_path(tmp_path, us_id="US-09")):
        assert found is not None and found.relative_to(tmp_path).as_posix() == "doc/prd/cobros/prd.md"
    assert append_implementation_status(prd, "UC-901", "feature/UC-901", ["### Fase 1\n- `server/x.py`"])
    written = prd.read_text(encoding="utf-8")
    assert written.startswith(text.rstrip("\n")) and "## Implementation Status" in written
    assert check_prd_format_content(written)["warnings"] == []  # lo añadido por el engine no avisa

    if shutil.which("node") is None:
        pytest.skip("sin node")
    lib = ROOT / ".claude" / "hooks" / "lib" / "prd-locate.mjs"
    code = (
        f"import('{lib}').then(m => process.stdout.write(JSON.stringify("
        f"m.locatePrd({{ root: {json.dumps(str(tmp_path))}, feature: '', usId: 'US-09' }}))))"
    )
    js = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    assert js == "doc/prd/cobros/prd.md"


async def test_ac04_write_implementation_status_with_both_formats(tmp_path):
    """La tool, con el contenido del cliente (MCP remoto): escribe en los dos formatos."""
    from fastmcp import Client, FastMCP

    from server.tools.sync import register_sync_tools

    mcp = FastMCP("t")
    register_sync_tools(mcp, ROOT)
    for text in (V2, V2.replace(FORMAT_MARK + "\n", "")):
        async with Client(mcp) as client:
            result = await client.call_tool("write_implementation_status", {
                "project_path": str(tmp_path / "repo"), "uc_id": "UC-901", "branch": "feature/UC-901",
                "phase_deltas": ["### Fase 1\n- hecho"], "us_id": "US-09",
                "files_content": {"doc/prd/cobros/prd.md": text},
            })
        out = result.structured_content or json.loads(result.content[0].text)
        out = out.get("result", out)
        assert out["success"] is True, out
        changed = out["files_changed"]["doc/prd/cobros/prd.md"]
        assert changed.startswith(text.rstrip("\n")) and "UC-901" in changed
