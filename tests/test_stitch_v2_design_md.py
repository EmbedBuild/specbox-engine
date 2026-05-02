"""Tests for stitch_v2 MCP tools (v5.31.0 Phase 2).

Validates the thin wrapper layer between FastMCP and the design_md
module: argument resolution, default paths, telemetry writes, idempotency,
meta.json persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from server.tools.stitch_v2 import (
    _pick_veg_path,
    register_stitch_v2_tools,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def mcp_with_v2(tmp_path: Path):
    """A FastMCP instance with v2 tools registered against a tmp state dir."""
    mcp = FastMCP("test-v2")
    state = tmp_path / "state"
    state.mkdir()
    register_stitch_v2_tools(mcp, state)
    return mcp, state


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """A minimal SpecBox project layout under tmp."""
    root = tmp_path / "demo-project"
    (root / "doc" / "brand").mkdir(parents=True)
    (root / "doc" / "design").mkdir(parents=True)
    (root / "doc" / "brand" / "brand_kit.md").write_text(
        "- primary: #112233\n"
        "- background: #FFFFFF\n"
        "- text_primary: #000000\n",
        encoding="utf-8",
    )
    return root


async def _call_tool(mcp: FastMCP, name: str, **kwargs):
    """Resolve a registered tool by name and invoke its fn directly.

    FastMCP exposes ``_get_tool`` as the canonical lookup; the underlying
    function is at ``tool.fn``. We call ``fn`` directly so the tests do
    not depend on FastMCP's transport layer.
    """
    tool = await mcp._get_tool(name)
    ctx = AsyncMock()
    return await tool.fn(ctx, **kwargs)


# ── _pick_veg_path ──────────────────────────────────────────────────────


class TestPickVegPath:
    def test_returns_none_when_no_veg_dir(self, tmp_path: Path):
        assert _pick_veg_path(tmp_path) is None

    def test_returns_none_when_dir_is_empty(self, tmp_path: Path):
        (tmp_path / "doc" / "veg").mkdir(parents=True)
        assert _pick_veg_path(tmp_path) is None

    def test_picks_global_md_when_present(self, tmp_path: Path):
        global_dir = tmp_path / "doc" / "veg" / "global"
        global_dir.mkdir(parents=True)
        target = global_dir / "global.md"
        target.write_text("# VEG global", encoding="utf-8")
        # Plus a feature file that should NOT win.
        (tmp_path / "doc" / "veg" / "feat_x").mkdir(parents=True)
        (tmp_path / "doc" / "veg" / "feat_x" / "veg.md").write_text(
            "# feat", encoding="utf-8"
        )
        assert _pick_veg_path(tmp_path) == target

    def test_falls_back_to_most_recent(self, tmp_path: Path):
        veg = tmp_path / "doc" / "veg"
        veg.mkdir(parents=True)
        first = veg / "old.md"
        first.write_text("old", encoding="utf-8")
        second = veg / "new.md"
        second.write_text("new", encoding="utf-8")
        # Force second to be more recent
        import os
        import time

        ts_old = time.time() - 1000
        os.utime(first, (ts_old, ts_old))
        assert _pick_veg_path(tmp_path) == second


# ── generate_design_md_tool ──────────────────────────────────────────────


class TestGenerateDesignMdTool:
    @pytest.mark.asyncio
    async def test_creates_design_md_at_default_path(self, mcp_with_v2, project_root):
        mcp, _state = mcp_with_v2
        result = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
            project_name="Demo",
        )
        assert result["status"] == "ok"
        path = Path(result["path"])
        assert path == project_root / "doc" / "design" / "DESIGN.md"
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "## Overview" in content

    @pytest.mark.asyncio
    async def test_uses_brand_kit_palette(self, mcp_with_v2, project_root):
        mcp, _state = mcp_with_v2
        result = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        assert result["status"] == "ok"
        content = (project_root / "doc" / "design" / "DESIGN.md").read_text(
            encoding="utf-8"
        )
        # primary from brand_kit.md should appear in the front-matter.
        assert "'#112233'" in content

    @pytest.mark.asyncio
    async def test_archetype_override_wins(self, mcp_with_v2, project_root):
        mcp, _state = mcp_with_v2
        # Remove brand_kit so palette comes purely from archetype.
        (project_root / "doc" / "brand" / "brand_kit.md").unlink()
        result = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
            archetype_override="gov",
        )
        assert result["status"] == "ok"
        content = (project_root / "doc" / "design" / "DESIGN.md").read_text(
            encoding="utf-8"
        )
        # Gov archetype primary
        assert "'#1F4E8C'" in content

    @pytest.mark.asyncio
    async def test_returns_error_for_bad_root(self, mcp_with_v2):
        mcp, _state = mcp_with_v2
        result = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root="/nonexistent/path/qz",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_idempotent_signature_stable(self, mcp_with_v2, project_root):
        mcp, _state = mcp_with_v2
        r1 = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        r2 = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        assert r1["signature"] == r2["signature"]

    @pytest.mark.asyncio
    async def test_writes_telemetry_entry(self, mcp_with_v2, project_root):
        mcp, state = mcp_with_v2
        await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        log = state / "projects" / "demo" / "stitch_usage.jsonl"
        assert log.exists()
        lines = log.read_text(encoding="utf-8").strip().split("\n")
        last = json.loads(lines[-1])
        assert last["tool"] == "generate_design_md"
        assert last["status"] == "ok"
        assert "signature" in last

    @pytest.mark.asyncio
    async def test_persists_meta_signature(self, mcp_with_v2, project_root):
        mcp, state = mcp_with_v2
        result = await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        meta = json.loads(
            (state / "projects" / "demo" / "meta.json").read_text(encoding="utf-8")
        )
        assert meta["design_md"]["signature"] == result["signature"]
        assert meta["design_md"]["primary_color"] == "#112233"


# ── upload_design_md_to_stitch ──────────────────────────────────────────


class TestUploadDesignMdToStitch:
    @pytest.mark.asyncio
    async def test_registers_inline_prefix_mode(self, mcp_with_v2, project_root):
        mcp, state = mcp_with_v2
        # First generate.
        await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        # Then register.
        result = await _call_tool(
            mcp,
            "upload_design_md_to_stitch",
            project="demo",
            stitch_project_id="stitch-pid-123",
            project_root=str(project_root),
        )
        assert result["status"] == "ok"
        assert result["mode"] == "inline-prefix"
        assert result["stitch_project_id"] == "stitch-pid-123"
        # Meta updated.
        meta = json.loads(
            (state / "projects" / "demo" / "meta.json").read_text(encoding="utf-8")
        )
        assert meta["design_md"]["stitch_project_id"] == "stitch-pid-123"
        assert meta["design_md"]["mode"] == "inline-prefix"

    @pytest.mark.asyncio
    async def test_errors_when_design_md_absent(self, mcp_with_v2, project_root):
        mcp, _state = mcp_with_v2
        result = await _call_tool(
            mcp,
            "upload_design_md_to_stitch",
            project="demo",
            stitch_project_id="pid",
            project_root=str(project_root),
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_errors_when_neither_path_nor_root_given(self, mcp_with_v2):
        mcp, _state = mcp_with_v2
        result = await _call_tool(
            mcp,
            "upload_design_md_to_stitch",
            project="demo",
            stitch_project_id="pid",
        )
        assert "error" in result

    @pytest.mark.asyncio
    async def test_explicit_design_md_path_works(self, mcp_with_v2, project_root):
        mcp, _state = mcp_with_v2
        await _call_tool(
            mcp,
            "generate_design_md_tool",
            project="demo",
            project_root=str(project_root),
        )
        explicit = project_root / "doc" / "design" / "DESIGN.md"
        result = await _call_tool(
            mcp,
            "upload_design_md_to_stitch",
            project="demo",
            stitch_project_id="pid-2",
            design_md_path=str(explicit),
        )
        assert result["status"] == "ok"
        assert result["path"] == str(explicit)
