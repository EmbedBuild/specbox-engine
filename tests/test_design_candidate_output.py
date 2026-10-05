"""US-49 · UC-4901 AC-02 — visual providers get the system and return candidates.

Stitch and Claude Design responses mark what they produce as a candidate
(never a production source), the saved HTML carries that mark, and the plan
``/plan`` writes says so explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP

import server.tools.stitch as stitch_v1
import server.tools.stitch_v2 as stitch_v2
from server.design_system import (
    DESIGN_ROLE_CANDIDATE,
    candidate_html_banner,
    candidate_marker,
    mark_html_as_candidate,
)
from server.design_system.provenance import CANDIDATE_BANNER_MARK
from server.tools.claude_design import register_claude_design_tools

ROOT = Path(__file__).resolve().parent.parent


class _FakeStitch:
    async def list_design_systems(self, project_id):
        return []

    async def generate_screen_from_text(self, project_id, prompt, *, device_type=None, model_id=None):
        return {"screen": {"id": "s1"}}

    async def edit_screens(self, project_id, screen_id, prompt, *, device_type=None, model_id=None):
        return {"screen": {"id": screen_id}}

    async def generate_variants(self, project_id, screen_id, **_):
        return {"screens": [{"id": "v1"}]}

    async def fetch_screen_code(self, project_id, screen_id):
        return {"html": "<html><body>hola</body></html>"}


async def _call(mcp: FastMCP, name: str, **kwargs) -> dict:
    tool = await mcp._get_tool(name)
    return await tool.fn(AsyncMock(), **kwargs)


def _assert_candidate(res: dict, provider_name: str) -> None:
    assert res["design_role"] == DESIGN_ROLE_CANDIDATE
    assert res["production_source"] == "system_tokens"
    assert provider_name in res["design_role_note"]
    assert "production source" in res["design_role_note"]
    assert CANDIDATE_BANNER_MARK in res["html_banner"]


# ── the marker itself ───────────────────────────────────────────────────


class TestMarker:
    def test_says_candidate_and_never_production(self):
        es = candidate_marker("stitch", "es")
        assert es["design_role"] == "candidate"
        assert "Nunca es fuente de producción" in es["design_role_note"]
        assert "tokens del sistema" in es["design_role_note"]

    def test_banner_is_a_single_html_comment(self):
        banner = candidate_html_banner("claude_design", "es")
        assert banner.startswith("<!--") and banner.endswith("-->")
        assert banner.count("--") == 2
        assert "Claude Design" in banner

    def test_marking_html_is_idempotent(self):
        once = mark_html_as_candidate("<html></html>", "stitch")
        assert once.splitlines()[0] == candidate_html_banner("stitch")
        assert mark_html_as_candidate(once, "stitch") == once


# ── Stitch ──────────────────────────────────────────────────────────────


@pytest.fixture
def stitch_mcp(tmp_path: Path, monkeypatch):
    fake = _FakeStitch()

    async def _client(*_args, **_kwargs):
        return fake

    monkeypatch.setattr(stitch_v2, "_v2_get_client", _client)
    monkeypatch.setattr(stitch_v1, "get_stitch_client", _client)
    mcp = FastMCP("test-candidates")
    state = tmp_path / "state"
    state.mkdir()
    stitch_v1.register_stitch_tools(mcp, state)
    stitch_v2.register_stitch_v2_tools(mcp, state)
    return mcp


class TestStitchOutputIsCandidate:
    async def test_generate_screen_v2(self, stitch_mcp):
        res = await _call(stitch_mcp, "stitch_generate_screen_v2", project="p", stitch_project_id="sp", prompt="A list")
        assert res["status"] == "ok", res
        _assert_candidate(res, "Stitch")

    async def test_build_site_batched_v2(self, stitch_mcp, monkeypatch):
        async def _fake_build(*_a, **_k):
            return {"total_screens": 1, "total_batches": 1, "batches": [], "unified_pass": [],
                    "unified_pass_applied": False}

        monkeypatch.setattr(stitch_v2, "build_site_batched", _fake_build)
        res = await _call(stitch_mcp, "stitch_build_site_batched_v2", project="p", stitch_project_id="sp",
                          screens=[{"name": "home", "prompt": "A home"}])
        _assert_candidate(res, "Stitch")

    @pytest.mark.parametrize(
        ("tool", "kwargs"),
        [
            ("stitch_generate_screen", {"prompt": "A list"}),
            ("stitch_edit_screen", {"screen_id": "s1", "prompt": "Tighter"}),
            ("stitch_generate_variants", {"screen_id": "s1", "prompt": "More playful"}),
            ("stitch_fetch_screen_code", {"screen_id": "s1"}),
        ],
    )
    async def test_v1_tools_that_produce_or_fetch_screens(self, stitch_mcp, tool, kwargs):
        res = await _call(stitch_mcp, tool, project="p", stitch_project_id="sp", **kwargs)
        assert res["status"] == "ok", res
        _assert_candidate(res, "Stitch")


# ── Claude Design ───────────────────────────────────────────────────────


async def test_claude_design_receives_the_system_and_returns_candidates(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.local.json").write_text(
        json.dumps({"veg": {"providers": ["claude_design"], "claude_design": {"projectId": "cd-1"}}}),
        encoding="utf-8",
    )
    (repo / "package.json").write_text("{}", encoding="utf-8")
    (repo / "dist").mkdir()

    mcp = FastMCP("test-cd")
    register_claude_design_tools(mcp, tmp_path / "state")
    res = await _call(
        mcp,
        "claude_design_sync_design_system",
        project="p",
        project_root=str(repo),
        session_projects=[{"projectId": "cd-1"}],
    )
    assert res["status"] == "ok", res
    assert res["system_input"]["kind"] == "design_system"
    assert "tokens/**" in res["system_input"]["includes"]
    assert "components/**" in res["system_input"]["includes"]
    _assert_candidate(res, "Claude Design")


# ── the skills say it explicitly ────────────────────────────────────────


class TestSkillContract:
    plan = (ROOT / ".claude" / "skills" / "plan" / "SKILL.md").read_text(encoding="utf-8")
    visual = (ROOT / ".claude" / "skills" / "visual-setup" / "SKILL.md").read_text(encoding="utf-8")

    def _template(self) -> str:
        start = self.plan.index("### Template de Plan")
        return self.plan[start : self.plan.index("## Paso 5: Guardar Plan")]

    def test_every_plan_has_a_design_source_section(self):
        template = self._template()
        assert "## Fuente de diseño" in template
        section = template[template.index("## Fuente de diseño") :]
        assert "tokens del sistema" in section
        assert "**candidatos**" in section
        assert "nunca son fuente de producción" in section

    def test_plan_generates_design_md_from_the_system(self):
        assert "system_tokens_content=" in self.plan
        assert "values_outside_system" in self.plan
        assert "SYSTEM_TOKENS_MISSING" in self.plan
        assert "stitch_upload_design_md" in self.plan

    def test_plan_prompts_do_not_invent_design_values(self):
        assert "#F5F5F5" not in self.plan
        assert "Font: [font del proyecto] / Inter" not in self.plan

    def test_plan_saves_designs_marked_as_candidates(self):
        assert "html_banner" in self.plan

    def test_plan_calls_only_tools_that_exist(self):
        assert "flash_safety_net=" not in self.plan
        assert "get_stitch_quota_status(" not in self.plan

    def test_visual_setup_generates_from_the_system(self):
        assert "system_tokens_content=" in self.visual
        assert "SYSTEM_TOKENS_MISSING" in self.visual
        assert "candidatos" in self.visual
