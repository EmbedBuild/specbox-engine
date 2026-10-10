"""Tests del parser de inventario de capacidades (UC-2001, US-20).

Cubren AC-01 (build_capability_inventory puro), AC-02 (agentes), AC-03 (tools — las del
registro del servidor, UC-6201), AC-04 (skills) y AC-05 (extensión VSCode).

Estrategia: un árbol fixture mínimo en tmp_path para aserciones deterministas sobre conteos,
+ una verificación contra el repo real (parents[1]) para garantizar que el parser funciona
sobre las fuentes canónicas de hoy. Las tools se comparan con lo que un cliente MCP recibe en
``tools/list``.
"""

import asyncio
from pathlib import Path

import pytest
from fastmcp import Client

from server.site_publish.inventory import (
    CapabilityInventory,
    build_capability_inventory,
    parse_agents,
    parse_skills,
    parse_vscode_ext,
    registered_tools,
)

ENGINE_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Fixture: árbol mínimo de un "engine" sintético
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_engine(tmp_path: Path) -> Path:
    root = tmp_path / "engine"

    # agents/
    agents = root / "agents"
    agents.mkdir(parents=True)
    (agents / "orchestrator.md").write_text(
        "# Orquestador de Agentes (Orchestrator)\n\n> banner\n\nCoordina subagentes.\n",
        encoding="utf-8",
    )
    (agents / "db-specialist.md").write_text(
        "# DB Specialist (AG-03)\n\nDisena el schema y RLS.\n", encoding="utf-8"
    )

    # .claude/skills/
    skills = root / ".claude" / "skills"
    (skills / "prd").mkdir(parents=True)
    (skills / "prd" / "SKILL.md").write_text(
        "---\nname: prd-generator\ndescription: Generate PRDs from descriptions.\n---\n# /prd\n",
        encoding="utf-8",
    )
    (skills / "plan").mkdir()
    (skills / "plan" / "SKILL.md").write_text(
        "---\nname: plan\ndescription: >\n  Multi-line\n  technical plan.\n---\n# /plan\n",
        encoding="utf-8",
    )

    # vscode-extension/package.json
    vsc = root / "vscode-extension"
    vsc.mkdir()
    (vsc / "package.json").write_text(
        '{"name": "specbox-engine", "publisher": "EmbedBuild", "version": "6.11.0"}',
        encoding="utf-8",
    )

    return root


# ---------------------------------------------------------------------------
# AC-01 — build_capability_inventory puro (sin red)
# ---------------------------------------------------------------------------
def test_build_capability_inventory_returns_four_lists(fake_engine):
    inv = build_capability_inventory(fake_engine)
    assert isinstance(inv, CapabilityInventory)
    assert len(inv.agents) == 2
    assert inv.tools == []  # sin server/server.py no hay registro que leer
    assert len(inv.skills) == 2
    assert inv.vscode_ext is not None


# ---------------------------------------------------------------------------
# AC-02 — agentes de agents/*.md
# ---------------------------------------------------------------------------
def test_parse_agents_name_from_paren(fake_engine):
    agents = parse_agents(fake_engine / "agents")
    by_key = {a.agent_key: a for a in agents}
    assert by_key["orchestrator"].name == "Orchestrator"
    assert by_key["db-specialist"].name == "AG-03"
    # role = primer párrafo de texto tras el H1
    assert "Coordina" in by_key["orchestrator"].role
    assert all(a.name for a in agents)


def test_parse_agents_real_repo_has_known_agents():
    agents = parse_agents(ENGINE_ROOT / "agents")
    assert len(agents) >= 10
    keys = {a.agent_key for a in agents}
    for expected in ("orchestrator", "db-specialist", "developer-tester"):
        assert expected in keys
    assert all(a.name for a in agents)


# ---------------------------------------------------------------------------
# AC-03 — tools del registro del servidor (UC-6201)
# ---------------------------------------------------------------------------
async def _tools_list_names() -> list[str]:
    """Los nombres que recibe un cliente MCP real al pedir ``tools/list``."""
    from server.server import mcp

    async with Client(mcp) as client:
        return [t.name for t in await client.list_tools()]


def test_inventory_publishes_the_same_tools_as_tools_list():
    """UC-6201 AC-02: lo que site_publish publica es lo que el servidor expone.

    El parser anterior leía decoradores con regex y se perdía las tools registradas como
    ``mcp_instance.tool(...)(fn)``: el site decía 126 y el MCP exponía 192. Su test comparaba
    el regex consigo mismo, así que nunca falló.
    """
    inventory = [t.tool_name for t in build_capability_inventory(ENGINE_ROOT).tools]
    listed = asyncio.run(_tools_list_names())

    assert len(inventory) == len(set(inventory)), "el inventario repite tools"
    assert set(inventory) == set(listed), (
        f"faltan en el inventario: {sorted(set(listed) - set(inventory))}; "
        f"sobran: {sorted(set(inventory) - set(listed))}"
    )


def test_registered_tools_point_to_their_module():
    tools = registered_tools(ENGINE_ROOT)
    assert tools, "el servidor no registra ninguna tool"
    for tool in tools:
        assert tool.module.startswith("server/") and tool.module.endswith(".py"), tool
        assert (ENGINE_ROOT / tool.module).is_file(), tool


def test_registered_tools_without_server_is_empty(tmp_path):
    assert registered_tools(tmp_path) == []


def test_registered_tools_refuses_another_engine(tmp_path):
    """Las tools salen del servidor importado: nunca se publican como si fueran de otro."""
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "server.py").write_text("mcp = None\n", encoding="utf-8")
    with pytest.raises(ValueError, match="otro engine"):
        registered_tools(tmp_path)


# ---------------------------------------------------------------------------
# AC-04 — skills de .claude/skills/*/SKILL.md
# ---------------------------------------------------------------------------
def test_parse_skills_inline_and_block_description(fake_engine):
    skills = parse_skills(fake_engine / ".claude" / "skills")
    by_key = {s.skill_key: s for s in skills}
    assert by_key["prd"].command == "/prd"
    assert by_key["prd"].description == "Generate PRDs from descriptions."
    # forma de bloque ">"
    assert by_key["plan"].description == "Multi-line technical plan."


def test_parse_skills_real_repo():
    skills = parse_skills(ENGINE_ROOT / ".claude" / "skills")
    assert len(skills) == 26
    assert all(s.description for s in skills)
    assert all(s.command.startswith("/") for s in skills)


# ---------------------------------------------------------------------------
# AC-05 — extensión VSCode de package.json
# ---------------------------------------------------------------------------
def test_parse_vscode_ext_marketplace_id(fake_engine):
    ext = parse_vscode_ext(fake_engine / "vscode-extension" / "package.json")
    assert ext is not None
    assert ext.marketplace_id == "EmbedBuild.specbox-engine"
    assert ext.version == "6.11.0"
    assert ext.publisher == "EmbedBuild"


def test_parse_vscode_ext_real_repo():
    ext = parse_vscode_ext(ENGINE_ROOT / "vscode-extension" / "package.json")
    assert ext is not None
    assert ext.marketplace_id == "EmbedBuild.specbox-engine"


def test_parse_vscode_ext_missing_returns_none(tmp_path):
    assert parse_vscode_ext(tmp_path / "nope.json") is None


# ---------------------------------------------------------------------------
# AC-01 — degradación: fuentes ausentes → listas vacías sin lanzar
# ---------------------------------------------------------------------------
def test_build_inventory_empty_root_degrades(tmp_path):
    inv = build_capability_inventory(tmp_path)
    assert inv.agents == []
    assert inv.tools == []
    assert inv.skills == []
    assert inv.vscode_ext is None
