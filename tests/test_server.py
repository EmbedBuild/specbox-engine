"""Tests for server.py — tool registration and configuration."""

import asyncio
import pytest

from src.server import mcp


class TestServerSetup:
    def test_server_name(self):
        assert mcp.name == "dev-engine-trello"

    def test_has_instructions(self):
        assert mcp.instructions is not None
        assert "User Stories" in mcp.instructions

    async def test_lists_21_tools(self):
        tools = await mcp.list_tools()
        assert len(tools) == 21

    async def test_tool_names(self):
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        expected = {
            "set_auth_token",
            "setup_board", "get_board_status", "import_spec",
            "list_us", "get_us", "move_us", "get_us_progress",
            "list_uc", "get_uc", "move_uc", "start_uc", "complete_uc",
            "mark_ac", "mark_ac_batch", "get_ac_status",
            "attach_evidence", "get_evidence",
            "get_sprint_status", "get_delivery_report", "find_next_uc",
        }
        assert names == expected

    async def test_each_tool_has_description(self):
        tools = await mcp.list_tools()
        for tool in tools:
            assert tool.description, f"Tool {tool.name} has no description"
