"""US-78 / UC-7807 — los milestones desaparecen en la versión anunciada (6.23.0).

- **AC-01**: las tools de milestone ya no están en la lista de tools del servidor, los
  parámetros de milestone ya no se aceptan (una llamada con ``milestone`` falla) y una entrada
  de ``update_uc_batch`` con ``milestone`` falla con ``MILESTONES_REMOVED``. Sigue valiendo lo de
  UC-7806: ni las skills, ni las plantillas, ni las reglas, ni ``docs/`` enseñan milestones.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from server.tools import _mutation_helpers as mh

ROOT = Path(__file__).resolve().parents[1]

REMOVED_TOOLS = {
    "set_uc_milestone",
    "set_uc_milestone_batch",
    "get_milestone_status",
    "rebalance_milestones",
    "milestone_acceptance_check",
}
NO_MILESTONE_PARAM = {"update_uc", "update_uc_batch", "update_us", "add_uc", "get_satellite_queue"}


async def _tools() -> dict:
    from server.server import mcp

    return {tool.name: tool for tool in await mcp.list_tools()}


async def test_milestone_tools_are_gone():
    tools = await _tools()
    assert REMOVED_TOOLS.isdisjoint(tools)
    assert not [name for name in tools if "milestone" in name]


async def test_no_tool_takes_a_milestone_any_more():
    tools = await _tools()
    with_param = sorted(
        name
        for name, tool in tools.items()
        if {"milestone", "propagate_milestone"} & set(inspect.signature(tool.fn).parameters)
    )
    assert with_param == []
    assert NO_MILESTONE_PARAM <= set(tools)


async def test_a_call_with_milestone_is_rejected():
    from fastmcp import Client

    from server.server import mcp

    async with Client(mcp) as client:
        result = await client.call_tool(
            "update_uc", {"board_id": "b", "uc_id": "UC-001", "milestone": "H1"}, raise_on_error=False
        )
    assert result.is_error
    assert "milestone" in result.content[0].text.lower()


def test_batch_entries_with_milestone_are_refused():
    assert "removed in v6.23.0" in mh.MILESTONES_REMOVED_MESSAGE
    assert not hasattr(mh, "validate_milestone")
    assert not hasattr(mh, "milestone_deprecated")


def test_skills_templates_rules_and_docs_do_not_teach_milestones():
    places = [ROOT / ".claude" / "skills", ROOT / "templates", ROOT / "rules", ROOT / "docs", ROOT / "agents",
              ROOT / "doc" / "tracking" / "_templates"]
    hits = [
        str(f.relative_to(ROOT))
        for base in places
        if base.exists()
        for f in base.rglob("*")
        if f.is_file() and f.suffix in {".md", ".json", ".yaml", ".yml", ".template"}
        and "milestone" in f.read_text(errors="ignore").lower()
    ]
    assert hits == []


@pytest.mark.parametrize("module", ["spec_mutations", "milestone_management", "acceptance_automation"])
def test_no_module_wraps_a_tool_with_the_deprecation(module):
    source = (ROOT / "server" / "tools" / f"{module}.py").read_text()
    assert "milestone_deprecated" not in source
    assert "MILESTONE_DEPRECATED_LABEL" not in source
