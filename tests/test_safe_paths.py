"""The engine's read-only tools never leave the folder they read from — US-107 · UC-10701.

Audit of 2026-10-27 (ENG-S-01): ``read_plan(plan_name="/etc/os-release")``
answered with the file, without a token, on the hosted MCP. Each tool runs here
against a fake engine in ``tmp_path`` with a secret next to it: every way out
(absolute name, ``..``, backslash, NUL, a symlink inside the folder) must come
back without the secret, and the names that worked before must still work.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastmcp import FastMCP

from server.tools._safe_paths import child_within
from server.tools.features import register_feature_tools
from server.tools.hooks import register_hook_tools
from server.tools.plans import register_plan_tools
from server.tools.quality import register_quality_tools
from server.tools.skills import register_skill_tools
from server.tools.telemetry import register_telemetry_tools

SECRET = "TOP-SECRET-OUTSIDE-THE-ENGINE"


# ── child_within ──────────────────────────────────────────────────────


def test_child_within_accepts_one_segment_inside(tmp_path):
    assert child_within(tmp_path, "plan.md") == tmp_path / "plan.md"
    assert child_within(tmp_path, "a..b.md") == tmp_path / "a..b.md"


@pytest.mark.parametrize("name", ["", ".", "..", "/etc/passwd", "../x", "a/b", "a\\..\\b", "x\x00y", "..\\x"])
def test_child_within_rejects_what_leaves_or_is_not_a_segment(tmp_path, name):
    assert child_within(tmp_path, name) is None


def test_child_within_rejects_a_symlink_that_points_out(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    base = tmp_path / "base"
    base.mkdir()
    (base / "link").symlink_to(outside)
    assert child_within(base, "link") is None


def test_child_within_rejects_what_is_not_a_string(tmp_path):
    assert child_within(tmp_path, None) is None  # type: ignore[arg-type]


# ── The tools ─────────────────────────────────────────────────────────


@pytest.fixture
def engine(tmp_path) -> Path:
    """A fake engine and, next to it, files with the secret in every shape a tool reads."""
    root = tmp_path / "engine"
    files = {
        "doc/plans/alpha.md": "# Alpha plan",
        "doc/design/feat/screen.html": "<p>design</p>",
        ".claude/hooks/guard.mjs": "// guard",
        ".claude/skills/demo/SKILL.md": "---\nname: demo\n---\nDemo skill",
        ".quality/baselines/proj.json": json.dumps({"lint": 0}),
        ".quality/evidence/feat/checkpoint.json": json.dumps({"phase": 1}),
        ".quality/evidence/feat/healing.jsonl": json.dumps({"level": 1, "result": "resolved"}),
        ".quality/logs/sessions_2026-10-27.jsonl": json.dumps({"event": "start"}),
        "architecture/react/overview.md": "# React overview",
        "infra/supabase/setup.md": "# Supabase setup",
        "agent-teams/prompts/lead-agent.md": "# Lead agent",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    secret = tmp_path / "secret"
    secret.mkdir()
    for name in ("secret.txt", "secret.md", "secret.json", "secret.mjs", "SKILL.md", "page.html", "checkpoint.json"):
        (secret / name).write_text(json.dumps(SECRET) if name.endswith(".json") else SECRET, encoding="utf-8")
    (secret / "healing.jsonl").write_text(json.dumps({"note": SECRET}), encoding="utf-8")
    # A symlink inside the plans folder that points out of the engine
    (root / "doc" / "plans" / "escape.md").symlink_to(secret / "secret.md")
    return root


@pytest.fixture
async def tools(engine) -> dict:
    mcp = FastMCP("safe-paths")
    for register in (
        register_plan_tools,
        register_hook_tools,
        register_quality_tools,
        register_telemetry_tools,
        register_feature_tools,
        register_skill_tools,
    ):
        register(mcp, engine)
    return {tool.name: tool.fn for tool in await mcp.list_tools()}


def _attempts(engine: Path, suffix: str = "") -> list[str]:
    secret = engine.parent / "secret"
    return [
        str(secret / f"secret{suffix}"),
        f"../../secret/secret{suffix}",
        f"..\\..\\secret\\secret{suffix}",
        f"../secret{suffix}\x00",
        str(secret),
        "../../secret",
        "..",
    ]


#: tool -> (argument, suffix of the file it reads, valid name, text the valid name returns)
CASES = {
    "read_plan": ("plan_name", ".txt", "alpha", "# Alpha plan"),
    "get_hook_source": ("hook_name", ".mjs", "guard.mjs", "// guard"),
    "get_quality_baseline": ("project_name", "", "proj", '"lint": 0'),
    "get_feature_evidence": ("feature_name", "", "feat", '"phase": 1'),
    "get_healing_log": ("feature_name", "", "feat", '"resolved"'),
    "read_agent_prompt": ("role_name", "", "lead-agent", "# Lead agent"),
    "read_skill": ("skill_name", "", "demo", "Demo skill"),
    "get_infra_doc": ("service", "", "supabase", "# Supabase setup"),
    "list_designs": ("feature_name", "", "feat", "screen.html"),
    "get_quality_logs": ("date", "", "2026-10-27", '"start"'),
    "get_session_events": ("date", "", "2026-10-27", '"start"'),
}


def _call(fn, **kwargs) -> str:
    try:
        return json.dumps(fn(**kwargs), default=str)
    except (OSError, ValueError) as exc:  # an error is a refusal too, as long as the secret is not in it
        return str(exc)


@pytest.mark.parametrize("tool", sorted(CASES))
async def test_a_name_that_leaves_the_folder_returns_nothing_from_outside(tools, engine, tool):
    arg, suffix, _, _ = CASES[tool]
    for attempt in _attempts(engine, suffix):
        assert SECRET not in _call(tools[tool], **{arg: attempt}), f"{tool}({arg}={attempt!r})"


@pytest.mark.parametrize("tool", sorted(CASES))
async def test_a_valid_name_still_returns_its_content(tools, tool):
    arg, _, valid, expected = CASES[tool]
    assert expected in _call(tools[tool], **{arg: valid})


async def test_architecture_doc_checks_both_names(tools, engine):
    fn = tools["get_architecture_doc"]
    secret = engine.parent / "secret"
    for stack, doc in [(str(secret), "secret"), ("../../secret", "secret"), ("react", "../../../secret/secret")]:
        out = _call(fn, stack=stack, doc_type=doc)
        assert SECRET not in out and "secret.md" not in out
    assert "# React overview" in _call(fn, stack="react", doc_type="overview")


async def test_a_symlink_inside_the_plans_folder_does_not_lead_out(tools):
    assert SECRET not in _call(tools["read_plan"], plan_name="escape.md")
