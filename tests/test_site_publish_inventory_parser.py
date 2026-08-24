"""Tests del parser de inventario de capacidades (UC-2001, US-20).

Cubren AC-01 (build_capability_inventory puro), AC-02 (agentes), AC-03 (tools — incluido el
caso crítico "decorador comentado NO cuenta"), AC-04 (skills) y AC-05 (extensión VSCode).

Estrategia: un árbol fixture mínimo en tmp_path para aserciones deterministas sobre conteos,
+ una verificación contra el repo real (parents[1]) para garantizar que el parser funciona
sobre las fuentes canónicas de hoy (13 agentes, 120 tools, 25 skills, ext v6.11.0).
"""

from pathlib import Path

import re

import pytest

from server.site_publish.inventory import (
    CapabilityInventory,
    build_capability_inventory,
    parse_agents,
    parse_skills,
    parse_tools,
    parse_vscode_ext,
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

    # server/ con tools reales y una mención comentada (NO debe contar)
    server = root / "server"
    (server / "tools").mkdir(parents=True)
    (server / "engine.py").write_text(
        "import x\n\n"
        "@mcp.tool\n"
        "def get_engine_version():\n    return '1'\n\n"
        "@mcp.tool\n"
        "async def get_engine_status():\n    return {}\n\n"
        "# Nota: @mcp.tool en un comentario NO cuenta.\n"
        '"""Docstring que menciona @mcp.tool tampoco cuenta."""\n',
        encoding="utf-8",
    )
    (server / "tools" / "other.py").write_text(
        "@mcp.tool\ndef list_plans():\n    return []\n", encoding="utf-8"
    )
    # tests/ debe excluirse
    (server / "tests").mkdir()
    (server / "tests" / "test_x.py").write_text(
        "@mcp.tool\ndef should_not_count():\n    pass\n", encoding="utf-8"
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
    assert len(inv.tools) == 3  # 2 en engine.py + 1 en tools/other.py; comentario/docstring/tests excluidos
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
# AC-03 — tools por decoradores reales (comentados NO cuentan)
# ---------------------------------------------------------------------------
def test_parse_tools_ignores_comments_and_tests(fake_engine):
    tools = parse_tools(fake_engine / "server")
    names = {t.tool_name for t in tools}
    assert names == {"get_engine_version", "get_engine_status", "list_plans"}
    assert "should_not_count" not in names  # tests/ excluido
    assert all(t.module for t in tools)


def test_parse_tools_real_repo_count_matches_grep():
    """El conteo del parser coincide con los decoradores reales del repo.

    Antes el número estaba congelado (120) y se rompía cada vez que se añadía una
    tool — de hecho llevaba roto desde que US-33 y US-34 añadieron cinco. Ahora se
    cuenta igual que promete el nombre del test: con una búsqueda independiente,
    que no comparte código con el parser que verifica.
    """
    decoradores = re.compile(r"^\s*@(?:mcp|app|server)\.tool")
    esperado = 0
    for py in (ENGINE_ROOT / "server").rglob("*.py"):
        if "tests" in py.parts or "__pycache__" in py.parts:
            continue
        esperado += sum(1 for l in py.read_text(encoding="utf-8").splitlines() if decoradores.match(l))

    tools = parse_tools(ENGINE_ROOT / "server")
    assert esperado > 0, "la búsqueda de control no encontró ninguna tool"
    assert len(tools) == esperado
    assert all(t.tool_name for t in tools)


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
    assert len(skills) == 25
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
