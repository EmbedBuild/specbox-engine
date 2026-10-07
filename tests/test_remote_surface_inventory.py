"""Inventory of what a remote caller can make the server touch (US-86 · UC-8606).

Same approach as the mutator and reader inventories of
``tests/test_tenant_isolation.py``: walk every tool the server registers —
decorated or registered with ``mcp.tool(...)(fn)`` — and fail when a new one
opens a hole that US-86 closed:

* a parameter that names a path on the client's machine without the remote
  guard (``CLIENT_PATH_TOOLS``, UC-8604);
* a ``project`` that becomes ``STATE_PATH/projects/<project>`` without the name
  check (``PROJECT_NAME_TOOLS``) or without resolving who calls on a remote
  transport (``STATE_PROJECT_TOOLS`` or ``resolve_caller_scope`` in the tool),
  UC-8603;
* code anywhere in ``server/`` that builds ``projects/<name>`` by hand instead
  of ``project_state_dir``.

An exception goes in an approved list with its reason. The last tests feed
the checks a tool that breaks each rule, so a check that stops checking fails.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from pathlib import Path

from server.coordination.client_paths import CLIENT_PATH_TOOLS
from server.coordination.project_state_scope import (
    PROJECT_NAME_TOOLS,
    STATE_PROJECT_TOOLS,
    project_state_dir,
)

SERVER = Path(__file__).resolve().parent.parent / "server"

PATH_LIKE = re.compile(r"(path|root|_dir$|folder)", re.I)
NOT_A_PATH = re.compile(r"(content|present|inventory|files_modified|has_)", re.I)

#: Tools with a path-like parameter that the guard does not reject, and why.
APPROVED_PATHS: dict[str, str] = {
    "generate_design_md_tool": "own guard: DESIGN_MD_CONTENT_REQUIRED remotely (UC-4901)",
    "set_auth_token": "FreeForm root_path rejected remotely (UC-3801)",
    "get_visual_gap_report": "system_tokens_path only labels the content sent",
    "onboard_project": "freeform_root_absolute is stored in the registry, never opened",
    "report_e2e_results": "report_path is stored as text, never opened",
    "run_quality_audit": "project_path is never used: the tool raises (deprecated)",
    "claude_design_create_project": "project_root is never used: it returns the DesignSync call to make",
    "switch_backend": "remotely writes the registry only and returns client_writes (UC-8604)",
    "switch_project_backend": "remotely writes the registry only and returns client_writes (UC-8604)",
    "enable_mirror": "remotely writes the registry only and returns client_writes (UC-8604)",
    "disable_mirror": "remotely writes the registry only and returns client_writes (UC-8604)",
}

#: Calls that turn ``project`` into a folder under ``STATE_PATH/projects``.
STATE_MARKERS = re.compile(
    r"\b(project_state_dir|_ensure_project_dir|audit_dir|update_project_meta|_store_design_md_meta)\("
)

#: The tool resolves who calls itself (UC-3802 registry tools, UC-3804 operator gate).
CALLER_RESOLVED = re.compile(r"\b(resolve_caller_scope|_operator_gate)\(")

#: Tools whose ``project`` reaches the state and that need no extra check, and why.
APPROVED_STATE: dict[str, str] = {
    "generate_design_md_tool": "writes meta.json only in disk mode, which is rejected remotely",
}

#: Builds ``projects/<x>`` by hand: ``"projects" / name`` in any quoting.
HAND_BUILT = re.compile(r"""["']projects["']\s*/""")


def path_problems(name: str, fn: Callable) -> list[str]:
    """A tool with a client path must be guarded or approved."""
    params = [p for p in inspect.signature(fn).parameters if PATH_LIKE.search(p) and not NOT_A_PATH.search(p)]
    if not params or name in APPROVED_PATHS:
        return []
    rule = CLIENT_PATH_TOOLS.get(name)
    if rule is None:
        return [f"{name}: client path {params} without remote guard (add it to CLIENT_PATH_TOOLS)"]
    missing = set(rule.path_params) - set(params)
    return [f"{name}: guarded params {sorted(missing)} are not parameters"] if missing else []


def state_problems(name: str, fn: Callable) -> list[str]:
    """A tool whose ``project`` becomes a state folder must check name and caller."""
    if "project" not in inspect.signature(fn).parameters or name in APPROVED_STATE:
        return []
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return []
    if not STATE_MARKERS.search(source):
        return []
    problems = []
    if name not in PROJECT_NAME_TOOLS:
        problems.append(f"{name}: project reaches the state without the name check (PROJECT_NAME_TOOLS)")
    if name not in STATE_PROJECT_TOOLS and not CALLER_RESOLVED.search(source):
        problems.append(f"{name}: project reaches the state without resolving the caller remotely")
    return problems


def hand_built_paths(root: Path) -> list[str]:
    found = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "project_state_scope.py":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if HAND_BUILT.search(line):
                found.append(f"{path.relative_to(root.parent)}:{number}: {line.strip()}")
    return found


async def _registered_tools() -> dict[str, Callable]:
    from server.server import mcp

    return {tool.name: tool.fn for tool in await mcp.list_tools() if getattr(tool, "fn", None)}


# ── The server as it is ──────────────────────────────────────────────


async def test_every_tool_with_a_client_path_is_guarded_or_approved():
    tools = await _registered_tools()
    problems = [p for name, fn in sorted(tools.items()) for p in path_problems(name, fn)]
    assert problems == []
    assert set(CLIENT_PATH_TOOLS) <= set(tools), sorted(set(CLIENT_PATH_TOOLS) - set(tools))


async def test_every_tool_whose_project_reaches_the_state_checks_name_and_caller():
    tools = await _registered_tools()
    problems = [p for name, fn in sorted(tools.items()) for p in state_problems(name, fn)]
    assert problems == []
    assert STATE_PROJECT_TOOLS <= PROJECT_NAME_TOOLS


def test_no_code_builds_a_project_state_path_by_hand():
    assert hand_built_paths(SERVER) == []


def test_approved_entries_say_why():
    for reason in {**APPROVED_PATHS, **APPROVED_STATE}.values():
        assert len(reason) > 20


# ── The checks catch what they are for (AC-03) ───────────────────────


def test_path_check_flags_an_unguarded_client_path():
    async def leaky_report(project_path: str = ".") -> dict:
        return {}

    assert path_problems("leaky_report", leaky_report) == [
        "leaky_report: client path ['project_path'] without remote guard (add it to CLIENT_PATH_TOOLS)"
    ]


def test_state_check_flags_a_project_that_reaches_the_state_unchecked():
    def leaky_state(project: str) -> dict:
        folder = project_state_dir(Path("/data/state"), project)
        return {"folder": str(folder)}

    problems = state_problems("leaky_state", leaky_state)
    assert len(problems) == 2
    assert "name check" in problems[0]
    assert "resolving the caller" in problems[1]


def test_hand_built_check_flags_a_state_path_built_by_hand(tmp_path):
    pkg = tmp_path / "server"
    pkg.mkdir()
    (pkg / "leaky.py").write_text('folder = state_path / "projects" / name\n', encoding="utf-8")
    assert hand_built_paths(pkg) == ['server/leaky.py:1: folder = state_path / "projects" / name']
