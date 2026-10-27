"""UC-11008: the agents a new project's CLAUDE.md names exist where it says they are.

The template said «Agentes disponibles en .claude/agents/», but onboard_project and upgrade_project
never copied them (and the engine's agents/*.md have no Claude Code subagent frontmatter, so they
must not go there). The CLAUDE.md now says they live in agents/ of the engine clone and that
list_agent_definitions lists them; these tests keep the table, the folder and the tool in step.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastmcp import Client, FastMCP

from server.tools.features import register_feature_tools
from server.tools.onboarding import _generate_onboarding_files

ENGINE = Path(__file__).resolve().parent.parent
TEMPLATE = ENGINE / "templates" / "CLAUDE.md.template"
AGENT_ROW = re.compile(r"^\| (AG-[0-9a-z]+) \| [^|]+ \| agents/([a-z0-9-]+\.md) \|$", re.MULTILINE)


def _named(text: str) -> dict[str, str]:
    return {file: agent_id for agent_id, file in AGENT_ROW.findall(text)}


def test_the_template_names_exactly_the_agents_of_the_engine():
    named = set(_named(TEMPLATE.read_text(encoding="utf-8")))
    on_disk = {p.name for p in (ENGINE / "agents").glob("*.md")}
    assert named == on_disk, {"named, not in agents/": sorted(named - on_disk), "in agents/, not named": sorted(on_disk - named)}


def test_a_new_project_claude_md_points_where_the_agents_are():
    files, _, _ = _generate_onboarding_files(ENGINE, "demo", "react", [], "dev")
    claude_md = files["CLAUDE.md"]
    assert ".claude/agents/" not in claude_md, "the agents are never copied to .claude/agents/"
    assert "list_agent_definitions" in claude_md and "~/.specbox/specbox-engine/agents/" in claude_md
    named = _named(claude_md)
    assert named, "the table survives the template substitution"
    for file in named:
        assert (ENGINE / "agents" / file).is_file(), file


async def test_list_agent_definitions_returns_every_named_agent(tmp_path):
    mcp = FastMCP("test")
    register_feature_tools(mcp, ENGINE)
    async with Client(mcp) as client:
        result = await client.call_tool("list_agent_definitions", {})
    listed = {a["filename"] for a in result.structured_content["result"]}
    assert set(_named(TEMPLATE.read_text(encoding="utf-8"))) <= listed
