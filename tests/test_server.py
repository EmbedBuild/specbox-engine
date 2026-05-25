"""Tests for server.py — tool registration and configuration."""

import asyncio
import pytest

from server.server import mcp


class TestServerSetup:
    def test_server_name(self):
        assert mcp.name == "specbox-engine"

    def test_has_instructions(self):
        assert mcp.instructions is not None
        # The instructions describe the spec-driven hierarchy used by /prd / /plan.
        assert "spec-driven" in mcp.instructions.lower() or "us" in mcp.instructions.lower()

    async def test_lists_many_tools(self):
        """The engine MCP exposes >100 tools as of v6.0+; assert a healthy floor
        instead of an exact count (which used to drift constantly)."""
        tools = await mcp.list_tools()
        assert len(tools) >= 100, f"Expected ≥100 tools registered, got {len(tools)}"

    async def test_core_tool_names_present(self):
        """Spot-check that the foundational spec-driven tools are registered."""
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        foundational = {
            "set_auth_token",
            "setup_board",
            "list_us",
            "list_uc",
            "start_uc",
            "complete_uc",
            "mark_ac",
            "find_next_uc",
        }
        missing = foundational - names
        assert not missing, f"Foundational tools missing: {missing}"

    async def test_each_tool_has_description(self):
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"

    def test_engine_version_read_from_yaml_not_hardcoded(self):
        """v6.0.2 cleanup: the version in ``instructions`` must match
        ENGINE_VERSION.yaml, not a string that drifts across releases.

        Regression for the hardcoded ``v5.29.0`` literal that survived
        through v6.0.1 in server/server.py."""
        from pathlib import Path
        import yaml

        from server.server import _ENGINE_VERSION

        yaml_path = Path(__file__).resolve().parent.parent / "ENGINE_VERSION.yaml"
        canonical = (yaml.safe_load(yaml_path.read_text()) or {}).get("version")
        assert canonical, "ENGINE_VERSION.yaml missing 'version' key"
        assert _ENGINE_VERSION == canonical
        assert f"v{canonical}" in mcp.instructions
