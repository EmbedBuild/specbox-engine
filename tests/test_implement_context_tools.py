"""/implement without the engine's Python (UC-11202).

The two MCP tools give the same content as the local Python helpers, the
skill no longer imports ``server.*`` nor runs Python, and a project with no
engine clone and no Python gets a context file the hooks can read.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from server.delta_generator import compile_uc_status
from server.implement_context import (
    aggregate_for_spec_sync,
    compute_plan_hash,
    context_path,
    write_execution_context,
)
from server.tools.implement_context_tools import register_implement_context_tools

ENGINE = Path(__file__).resolve().parents[1]
SKILL = ENGINE / ".claude" / "skills" / "implement" / "SKILL.md"
FEATURE = "uc-11202-demo"

RUN = {
    "branch": "feature/UC-11202-implement-sin-python",
    "stack": "react",
    "project_name": "demo",
    "project_root_absolute": "/work/demo",
    "uc_id": "UC-11202",
    "us_id": "US-112",
    "backend_type": "native",
    "board_id": "EmbedBuild/specbox-manager",
    "plan_path": "doc/plans/demo_plan.md",
    "autopilot_level": "agresivo",
}

PHASES = [
    {"phase": "db", "phase_index": 1, "agent": "AG-03", "status": "ok", "duration_s": 12.5,
     "files_created": ["supabase/migrations/1.sql"], "summary": "Tabla y RLS."},
    {"phase": "feature", "phase_index": 2, "agent": "AG-01", "status": "partial", "duration_s": 40.25,
     "files_created": ["src/a.ts"], "files_modified": ["src/b.ts", "src/c.ts"], "healing_attempts": 2,
     "summary": "Texto con separador de línea dentro."},
    {"phase": "qa", "phase_index": 3, "agent": "AG-04", "status": "error", "files_modified": ["src/b.ts"],
     "files_deleted": ["src/old.ts"], "error": "2 pruebas fallan"},
]


def _jsonl(entries: list[dict]) -> str:
    lines = [json.dumps({"schema_version": 1, "ts": "2026-10-27T22:00:00Z", **e}, ensure_ascii=False) for e in entries]
    lines.insert(1, "{esto no es json")  # a corrupt line is skipped by both paths
    return "\n".join(lines) + "\n"


def _without_timestamps(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if k not in ("started_at", "last_updated_at")}


@pytest.fixture
def server() -> FastMCP:
    mcp = FastMCP("implement-context-test")
    register_implement_context_tools(mcp, ENGINE)
    return mcp


async def _call(server: FastMCP, tool: str, args: dict) -> dict:
    async with Client(server) as client:
        result = await client.call_tool(tool, args, raise_on_error=False)
    return result.structured_content or {}


# ── AC-03: the same content as the Python ──────────────────────────────


async def test_ac03_execution_context_is_the_same_as_the_python(server, tmp_path):
    plan = tmp_path / RUN["plan_path"]
    plan.parent.mkdir(parents=True)
    plan.write_text("# Plan\n\nFase 1 — ñandú ✓\n", encoding="utf-8")
    written = write_execution_context(
        FEATURE, engine_version="6.29.1", plan_hash=compute_plan_hash(plan), project_root=tmp_path, **RUN
    )

    out = await _call(
        server,
        "build_execution_context",
        {"feature_slug": FEATURE, "engine_version": "6.29.1", "plan_content": plan.read_text(encoding="utf-8"), **RUN},
    )

    assert out["path"] == ".quality/evidence/uc-11202-demo/execution_context.json"
    assert out["changed"] is True
    python_file = json.loads(written.read_text(encoding="utf-8"))
    tool_file = json.loads(out["content"])
    assert _without_timestamps(tool_file) == _without_timestamps(python_file)
    assert list(tool_file) == list(python_file)  # same keys, same order (sort_keys)
    assert out["content"] == json.dumps(tool_file, ensure_ascii=False, indent=2, sort_keys=True)


async def test_ac03_rerunning_keeps_the_file_when_only_timestamps_would_change(server, tmp_path):
    path = write_execution_context(FEATURE, engine_version="6.29.1", project_root=tmp_path, **RUN)
    existing = path.read_text(encoding="utf-8")

    same = await _call(
        server,
        "build_execution_context",
        {"feature_slug": FEATURE, "engine_version": "6.29.1", "existing_content": existing, **RUN},
    )
    moved = await _call(
        server,
        "build_execution_context",
        {"feature_slug": FEATURE, "engine_version": "6.29.1", "existing_content": existing, **{**RUN, "branch": "otra"}},
    )

    assert same == {"path": same["path"], "content": existing, "changed": False}
    assert moved["changed"] is True and json.loads(moved["content"])["branch"] == "otra"


async def test_ac03_the_aggregate_is_the_same_as_the_python(server, tmp_path):
    content = _jsonl(PHASES)
    jsonl = tmp_path / ".quality" / "evidence" / FEATURE / "phase_outputs.jsonl"
    jsonl.parent.mkdir(parents=True)
    jsonl.write_text(content, encoding="utf-8")
    python_agg = aggregate_for_spec_sync(FEATURE, project_root=tmp_path)

    out = await _call(server, "aggregate_phase_outputs", {"feature_slug": FEATURE, "phase_outputs_content": content})

    deltas = out.pop("phase_deltas")
    assert out == {
        "feature_slug": python_agg.feature_slug,
        "overall_status": python_agg.overall_status,
        "delta_count": python_agg.delta_count,
        "files_created": python_agg.files_created,
        "files_modified": python_agg.files_modified,
        "files_deleted": python_agg.files_deleted,
        "phases": python_agg.phases,
        "total_duration_s": python_agg.total_duration_s,
        "total_healing_attempts": python_agg.total_healing_attempts,
    }
    assert out["overall_status"] == "error" and len(out["phases"]) == 3
    # One Markdown block per phase, which write_implementation_status compiles as is.
    assert len(deltas) == 3 and deltas[1].startswith("#### Fase 2: feature")
    assert "needs_healing" in deltas[1] and "2 pruebas fallan" in deltas[2]
    assert "### Implementation Status — UC-11202" in compile_uc_status("UC-11202", RUN["branch"], deltas)


async def test_an_empty_or_missing_file_aggregates_as_empty(server):
    out = await _call(server, "aggregate_phase_outputs", {"feature_slug": FEATURE})
    assert out["overall_status"] == "empty" and out["phase_deltas"] == [] and out["delta_count"] == 0


@pytest.mark.parametrize("slug", ["../fuera", "a/b", "..", "", "con espacio"])
async def test_a_slug_that_is_not_one_segment_is_rejected(server, slug):
    built = await _call(server, "build_execution_context", {"feature_slug": slug, **RUN})
    aggregated = await _call(server, "aggregate_phase_outputs", {"feature_slug": slug})
    assert built["error"] == aggregated["error"] == "INVALID_FEATURE_SLUG"


async def test_the_engine_version_defaults_to_the_server_one(server):
    out = await _call(server, "build_execution_context", {"feature_slug": FEATURE, **RUN})
    version = re.search(r"^version:\s*\"?([\d.]+)", (ENGINE / "ENGINE_VERSION.yaml").read_text(), re.M).group(1)
    assert json.loads(out["content"])["engine_version"] == version


# ── AC-02: the skill imports nothing from the engine ───────────────────


def test_ac02_the_implement_skill_has_no_engine_python():
    text = SKILL.read_text(encoding="utf-8")
    assert not re.search(r"\b(from|import)\s+server\b", text)
    assert "server.implement_context" not in text
    python_blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    # Only the traceability comment template for Python projects remains.
    assert python_blocks == ["# Generated from: doc/design/{feature}/{screen}.html\n"]
    for helper in ("aggregate_for_spec_sync", "compile_uc_status", "append_implementation_status", "find_prd_path"):
        assert helper not in text


# ── AC-01: a project without the engine clone and without Python ──────


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node (the hooks' runtime)")
async def test_ac01_the_context_phase_completes_without_engine_or_python(server, tmp_path):
    project = tmp_path / "proyecto"
    project.mkdir()

    out = await _call(server, "build_execution_context", {"feature_slug": FEATURE, **RUN})
    target = project / out["path"]  # what the skill's Write does
    target.parent.mkdir(parents=True)
    target.write_text(out["content"], encoding="utf-8")

    # The hooks read it with only node on the PATH: no python, no engine checkout.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    node = bin_dir / ("node.exe" if os.name == "nt" else "node")
    real_node = Path(shutil.which("node")).resolve()
    try:
        node.symlink_to(real_node)  # a copy would lose Homebrew's @rpath libnode
    except OSError:
        shutil.copy2(real_node, node)
    reader = (ENGINE / ".claude" / "hooks" / "lib" / "execution-context.mjs").as_uri()
    script = (
        f"import {{ readExecutionContext }} from {json.dumps(reader)};"
        f"console.log(JSON.stringify(readExecutionContext({json.dumps(FEATURE)}, process.cwd())));"
    )
    env = {"PATH": str(bin_dir), "HOME": str(tmp_path)}
    assert shutil.which("python3", path=str(bin_dir)) is None and shutil.which("python", path=str(bin_dir)) is None
    done = subprocess.run(
        [str(node), "--input-type=module", "-e", script], cwd=project, env=env, capture_output=True, text=True, timeout=30
    )

    assert done.returncode == 0, done.stderr
    read = json.loads(done.stdout)
    assert {k: read[k] for k in ("feature_slug", "branch", "stack", "uc_id", "backend_type")} == {
        "feature_slug": FEATURE,
        "branch": RUN["branch"],
        "stack": "react",
        "uc_id": "UC-11202",
        "backend_type": "native",
    }
    assert context_path(FEATURE, project) == target
