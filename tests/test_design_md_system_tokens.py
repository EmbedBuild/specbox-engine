"""US-49 · UC-4901 AC-01 and AC-03 — DESIGN.md comes from the system tokens.

AC-01: with ``design-system.tokens.json`` the document takes colours,
typography, radii and states from it and holds no value outside it — in the
SpecBox view and in the Material 3 view Stitch parses.
AC-03: without it, the result carries a notice that explains how to adopt the
tokens and links to the guide.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

from server.design_md.generator import GeneratorInputs, generate_design_md
from server.design_md.system_view import build_material3_from_system
from server.design_md.writer import serialize
from server.design_system import (
    SYSTEM_TOKENS_GUIDE_URL,
    find_values_outside,
    parse_system_tokens,
    system_tokens_notice,
)
from server.tools.stitch_v2 import register_stitch_v2_tools

FIXTURE = Path(__file__).parent / "fixtures" / "design_system" / "tinta.design-system.tokens.json"
TOKENS_REL = "src/styles/tokens/design-system.tokens.json"
BRAND_KIT = "- primary: #112233\n- background: #FFFFFF\n- text_primary: #000000\n- font_family: Inter\n"


@pytest.fixture(scope="module")
def tinta_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tinta(tinta_text):
    return parse_system_tokens(tinta_text, source=TOKENS_REL)


@pytest.fixture
def mcp_v2(tmp_path: Path):
    mcp = FastMCP("test-uc4901")
    state = tmp_path / "state"
    state.mkdir()
    register_stitch_v2_tools(mcp, state)
    return mcp, state


async def _call(mcp: FastMCP, **kwargs) -> dict:
    tool = await mcp._get_tool("generate_design_md_tool")
    return await tool.fn(AsyncMock(), **kwargs)


# ── AC-01: the generator ────────────────────────────────────────────────


class TestGeneratedFromSystem:
    def _doc(self, tinta, **extra):
        return generate_design_md(
            GeneratorInputs(project_root=None, project_name="site", system_tokens=tinta, **extra)
        )

    def test_takes_colours_typography_radii_and_states_from_the_tokens(self, tinta):
        fm = self._doc(tinta).front_matter
        assert fm.colors.primary == tinta.color("accent") == "#1A1B1E"
        assert fm.colors.background == tinta.color("paper-000")
        assert fm.colors.surface == tinta.color("paper-100")
        assert fm.colors.text_primary == tinta.color("ink-900")
        assert fm.colors.error == tinta.color("danger-text")
        # States: every status-* colour of the system is in the front-matter.
        dumped = fm.colors.model_dump()
        for name, per_theme in tinta.colors.items():
            if name.startswith("status-"):
                assert dumped[name.replace("-", "_")] == per_theme["light"]
        assert fm.typography.fontFamily.heading == tinta.families["sans"]
        assert fm.typography.fontSize.h1 == tinta.styles["display-xl"].font_size
        assert fm.typography.fontSize.body == tinta.styles["body-md"].font_size
        assert fm.rounded.md == tinta.radius["radius-md"] == "6px"
        assert fm.rounded.full == tinta.radius["radius-pill"]
        assert fm.source == tinta.describe()

    def test_ignores_brand_kit_and_archetype_when_tokens_exist(self, tinta):
        doc = self._doc(tinta, brand_kit_text=BRAND_KIT, veg_text="Arquetipo: gen_z")
        text = serialize(doc)
        assert "#112233" not in text
        assert "Inter" not in text

    @pytest.mark.parametrize("material3", [False, True], ids=["specbox-view", "material3-view"])
    def test_holds_no_value_outside_the_tokens(self, tinta, material3):
        doc = self._doc(tinta)
        m3 = build_material3_from_system(doc, tinta) if material3 else None
        text = serialize(doc, material3=m3)
        assert find_values_outside(text, tinta) == []
        if m3 is not None:
            assert m3.warnings == []
            assert m3.theme.headline_font.value == "IBM_PLEX_SANS"
            assert m3.theme.roundness.value == "ROUND_FOUR"  # 4px, the system radius closest to 6px

    def test_the_archetype_document_would_not_pass(self, tinta):
        legacy = serialize(generate_design_md(GeneratorInputs(project_root=None, project_name="p")))
        kinds = {d.kind for d in find_values_outside(legacy, tinta)}
        assert {"color", "font_family", "font_weight"} <= kinds

    def test_a_font_stitch_lacks_is_reported_not_hidden(self, tinta_text):
        data = json.loads(tinta_text)
        data["type"]["families"]["sans"] = '"Atkinson Hyperlegible", sans-serif'
        tokens = parse_system_tokens(json.dumps(data))
        doc = generate_design_md(GeneratorInputs(project_root=None, project_name="p", system_tokens=tokens))
        m3 = build_material3_from_system(doc, tokens)
        assert any("Atkinson Hyperlegible" in w for w in m3.warnings)
        found = {(d.kind, d.value) for d in find_values_outside(serialize(doc, material3=m3), tokens)}
        assert ("font_family", "inter") in found


# ── AC-01 + AC-03: the tool ─────────────────────────────────────────────


class TestToolContentMode:
    async def test_generates_from_the_tokens_the_client_sends(self, mcp_v2, tinta_text):
        mcp, state = mcp_v2
        res = await _call(
            mcp,
            project="specpox_site",
            system_tokens_content=tinta_text,
            system_tokens_path=TOKENS_REL,
            brand_kit_content=BRAND_KIT,
        )
        assert res["status"] == "ok", res
        assert res["mode"] == "content"
        assert res["suggested_relpath"] == "doc/design/DESIGN.md"
        assert res["design_source"]["kind"] == "system_tokens"
        assert res["system_tokens"] == {"found": True, "kind": "system_tokens", "path": TOKENS_REL,
                                        "name": "SpecBox", "version": "2"}
        assert res["values_outside_system"] == []
        assert "notice" not in res
        assert "#112233" not in res["design_md_content"]
        assert res["material3"]["theme"]["headlineFont"] == "IBM_PLEX_SANS"
        # Content mode never writes the project on the server.
        assert not (state / "projects" / "specpox_site" / "meta.json").exists()

    async def test_without_tokens_the_result_carries_the_notice_and_the_guide(self, mcp_v2):
        mcp, _ = mcp_v2
        res = await _call(mcp, project="p", brand_kit_content=BRAND_KIT)
        assert res["status"] == "ok"
        assert res["system_tokens"] == {"found": False}
        assert res["design_source"] == {"kind": "brand_kit"}
        notice = res["notice"]
        assert notice["code"] == "SYSTEM_TOKENS_MISSING"
        assert notice["guide_url"] == SYSTEM_TOKENS_GUIDE_URL
        assert SYSTEM_TOKENS_GUIDE_URL in notice["message"]
        assert "design-system.tokens.json" in notice["message"]
        assert "build:sync" in notice["message"]  # how to adopt them
        assert "src/styles/tokens/design-system.tokens.json" in notice["looked_in"]

    async def test_with_no_input_at_all_it_still_generates_and_warns(self, mcp_v2):
        mcp, _ = mcp_v2
        res = await _call(mcp, project="p")
        assert res["mode"] == "content"
        assert res["design_source"] == {"kind": "archetype"}
        assert res["notice"]["code"] == "SYSTEM_TOKENS_MISSING"

    async def test_invalid_tokens_are_an_error_not_a_silent_fallback(self, mcp_v2):
        mcp, _ = mcp_v2
        res = await _call(mcp, project="p", system_tokens_content="{}", system_tokens_path="x.json",
                          brand_kit_content=BRAND_KIT)
        assert res["code"] == "SYSTEM_TOKENS_INVALID"
        assert "design_md_content" not in res
        assert res["guide_url"] == SYSTEM_TOKENS_GUIDE_URL


class TestToolDiskMode:
    async def test_finds_the_tokens_where_sync_leaves_them(self, mcp_v2, tmp_path, tinta_text):
        mcp, _ = mcp_v2
        root = tmp_path / "site"
        (root / "src" / "styles" / "tokens").mkdir(parents=True)
        (root / TOKENS_REL).write_text(tinta_text, encoding="utf-8")
        (root / "doc" / "brand").mkdir(parents=True)
        (root / "doc" / "brand" / "brand_kit.md").write_text(BRAND_KIT, encoding="utf-8")

        res = await _call(mcp, project="site", project_root=str(root))
        assert res["mode"] == "disk"
        assert res["system_tokens"]["path"] == TOKENS_REL
        assert res["values_outside_system"] == []
        written = (root / "doc" / "design" / "DESIGN.md").read_text(encoding="utf-8")
        assert written == res["design_md_content"]
        assert "#112233" not in written

    async def test_without_tokens_on_disk_it_warns(self, mcp_v2, tmp_path):
        mcp, _ = mcp_v2
        root = tmp_path / "plain"
        root.mkdir()
        res = await _call(mcp, project="plain", project_root=str(root))
        assert res["mode"] == "disk"
        assert res["notice"]["code"] == "SYSTEM_TOKENS_MISSING"

    async def test_a_remote_server_never_reads_the_clients_path(self, mcp_v2, tmp_path, monkeypatch, tinta_text):
        mcp, _ = mcp_v2
        monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
        root = tmp_path / "site"
        (root / "src" / "styles" / "tokens").mkdir(parents=True)
        (root / TOKENS_REL).write_text(tinta_text, encoding="utf-8")

        res = await _call(mcp, project="site", project_root=str(root))
        assert res["code"] == "DESIGN_MD_CONTENT_REQUIRED"
        assert "system_tokens_content" in res["error"]
        assert not (root / "doc" / "design" / "DESIGN.md").exists()

        # Same server, content mode: works.
        ok = await _call(mcp, project="site", project_root=str(root), system_tokens_content=tinta_text,
                         system_tokens_path=TOKENS_REL)
        assert ok["mode"] == "content"
        assert ok["values_outside_system"] == []
        assert not (root / "doc" / "design" / "DESIGN.md").exists()


class TestNoticeLocale:
    def test_spanish(self):
        notice = system_tokens_notice("es")
        assert notice["locale"] == "es"
        assert notice["message"].startswith("Este proyecto no tiene tokens del sistema")
        assert SYSTEM_TOKENS_GUIDE_URL in notice["message"]

    def test_english_by_default(self):
        assert system_tokens_notice()["message"].startswith("This project has no design system tokens")


def test_the_guide_the_notice_links_to_exists():
    guide = Path(__file__).parent.parent / "doc" / "guides" / "design-system-tokens.md"
    assert SYSTEM_TOKENS_GUIDE_URL.endswith("/doc/guides/design-system-tokens.md")
    text = guide.read_text(encoding="utf-8")
    assert "design-system.tokens.json" in text
    assert "npm run build:sync" in text
