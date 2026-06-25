"""MCP tools for the Claude Design visual provider (US-29 · UC-2902).

Claude Design (``claude.ai/design``) is operated through the harness
``DesignSync`` tool, NOT a server-side HTTP API. So unlike ``stitch_*`` (which
proxy an httpx client to Stitch's MCP), the ``claude_design_*`` tools are
**orchestrators**: they resolve the design-system site (the topology gate,
UC-2903), anchor the ``projectId``, verify session identity, and return a
**structured plan of DesignSync calls** for the agent to execute in the
mandatory order ``list/read → finalize_plan → write/delete``.

Two hard rules, both contractual:

1. **No credentials.** No tool accepts a ``token``/``api_key`` and none is
   persisted. Claude Design uses the claude.ai login of the session on this
   machine — the consumption is billed to that user's subscription (AC-03,
   AC-06). This is the opposite of Stitch, which stores an obfuscated API key.

2. **No programmatic delete.** ``DesignSync`` exposes no ``delete_project``, so
   there is intentionally no ``claude_design_delete_project``. Removing a
   project is a manual action in claude.ai (AC-05).

The pure helpers below are unit-tested directly; the ``@mcp.tool`` wrappers are
thin shells over them.

Trazabilidad: Discovery ``disc-52cbe4033fae`` · US-29 · UC-2902.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import structlog
from fastmcp import Context, FastMCP

from ..veg.design_system_gate import evaluate_gate
from ..veg.visual_provider import claude_design_config, parse_providers

logger = structlog.get_logger(__name__)

# The exact set of DesignSync methods, in their mandatory ordering buckets.
# Used to validate that a sync plan never writes before finalize_plan.
_READ_METHODS = frozenset(
    {"list_projects", "get_project", "list_files", "get_file"}
)
_SETUP_METHODS = frozenset({"create_project"})
_PLAN_METHODS = frozenset({"finalize_plan"})
_WRITE_METHODS = frozenset(
    {"write_files", "delete_files", "register_assets", "unregister_assets"}
)

# Reason strings (stable — tests assert on substrings).
REASON_NO_LOGIN = "requires active claude.ai login on this machine"


def _read_project_settings(project_root: Path) -> dict[str, Any]:
    """Read ``.claude/settings.local.json`` for a project root (or {})."""
    p = project_root / ".claude" / "settings.local.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def assert_session_identity(
    session_projects: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Verify there is an active claude.ai login on this machine (AC-06).

    ``session_projects`` is the result of a DesignSync read
    (``list_projects``), which the harness only returns when a login is active
    and filtered to *writable* projects. The engine cannot call DesignSync
    itself, so the agent passes the read result in.

    Returns ``{"ok": True}`` when a login is present (a list — possibly empty —
    means the read succeeded), or ``{"ok": False, "reason": ...}`` when there
    is no active login (``None``). Never uses any external credential.
    """
    if session_projects is None:
        return {"ok": False, "reason": REASON_NO_LOGIN}
    return {"ok": True}


def resolve_writability(
    project_id: str | None,
    session_projects: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Decide whether the active session can write the anchored project.

    DesignSync's ``list_projects`` is filtered to *writable* projects. So if a
    ``project_id`` is anchored:

    - it appears in ``session_projects`` → the active session is writable;
      proceed (even if another account created it — JR-CD.4 multi-account).
    - it does NOT appear → the active login has no write access → pending.

    When no ``project_id`` is anchored yet (first run), writability is N/A and
    creation will happen under the active session.
    """
    if session_projects is None:
        return {"writable": False, "reason": REASON_NO_LOGIN}
    if not project_id:
        # No anchor yet — a create_project under the active session will own it.
        return {"writable": True, "needs_create": True}

    ids = {p.get("projectId") for p in session_projects}
    owners = {
        p.get("projectId"): p.get("owner")
        for p in session_projects
    }
    if project_id in ids:
        return {
            "writable": True,
            "foreign_owner": owners.get(project_id),
        }
    return {
        "writable": False,
        "reason": (
            f"anchored projectId {project_id!r} is not writable by the active "
            "claude.ai session on this machine"
        ),
    }


def build_sync_plan(
    project_id: str | None,
    site_path: str,
    writes: list[str],
    deletes: list[str] | None = None,
) -> dict[str, Any]:
    """Build the ordered DesignSync call plan for a sync (AC-02).

    The plan always reads first, then ``finalize_plan`` (which returns a
    ``planId``), then writes/deletes. A write is NEVER emitted before a
    finalized plan. Returns a dict the agent executes step by step.

    Raises ``ValueError`` if asked to write without any project context — a
    write with no ``projectId`` and no ``create_project`` step is rejected
    before reaching DesignSync.
    """
    if (writes or deletes) and not project_id:
        raise ValueError(
            "cannot plan writes without a projectId — create_project first"
        )

    steps: list[dict[str, Any]] = [
        # 1. read — confirm login + current state
        {"order": 1, "method": "list_files", "projectId": project_id},
    ]
    # 2. finalize_plan — locks the exact writes/deletes + localDir, returns planId
    steps.append(
        {
            "order": 2,
            "method": "finalize_plan",
            "projectId": project_id,
            "writes": writes,
            "deletes": deletes or [],
            "localDir": site_path,
        }
    )
    # 3. write/delete — only with the planId from step 2
    steps.append(
        {
            "order": 3,
            "method": "write_files",
            "projectId": project_id,
            "requires": "planId from step 2",
            "files_from": site_path,
        }
    )
    return {"ordered_steps": steps, "contract": "list/read → finalize_plan → write/delete"}


def validate_plan_ordering(steps: list[dict[str, Any]]) -> None:
    """Assert a plan never writes before a finalize_plan step (AC-02).

    Raises ``ValueError`` if a write/delete method appears before any
    finalize_plan in the ordered list.
    """
    seen_finalize = False
    for step in sorted(steps, key=lambda s: s.get("order", 0)):
        method = step.get("method")
        if method in _PLAN_METHODS:
            seen_finalize = True
        elif method in _WRITE_METHODS and not seen_finalize:
            raise ValueError(
                f"write method {method!r} appears before finalize_plan — "
                "violates the DesignSync ordering contract"
            )


def anchor_project_id(project_root: Path, project_id: str) -> dict[str, Any]:
    """Persist the Claude Design ``projectId`` in ``veg.claude_design`` (AC-04).

    Writes only the projectId (NOT a secret) into the project's
    settings.local.json under ``veg.claude_design.projectId``, merging with the
    existing JSON (never overwriting other keys). Returns the updated block.
    """
    settings_file = project_root / ".claude" / "settings.local.json"
    data: dict[str, Any] = {}
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    if not isinstance(data, dict):
        data = {}

    veg = data.setdefault("veg", {})
    if not isinstance(veg, dict):
        veg = {}
        data["veg"] = veg
    cd = veg.setdefault("claude_design", {})
    if not isinstance(cd, dict):
        cd = {}
        veg["claude_design"] = cd
    cd["projectId"] = project_id

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return cd


def register_claude_design_tools(mcp: FastMCP, state_path: Path):
    """Register Claude Design orchestrator tools on the MCP instance.

    Mirrors ``register_stitch_tools(mcp, state_path)``. The tools delegate to
    the harness ``DesignSync`` tool; they never hold a claude.ai token.
    """

    def _log_usage(project: str, tool: str) -> None:
        try:
            log_dir = state_path / "projects" / project
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "claude_design_usage.jsonl", "a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "tool": tool,
                            "timestamp": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            ),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except OSError:
            pass  # best-effort

    @mcp.tool
    async def claude_design_list_projects(ctx: Context, project: str) -> dict:
        """List the user's Claude Design projects (read — no permission prompt).

        This is an orchestration tool: it instructs the agent to run the
        DesignSync ``list_projects`` read under the active claude.ai login of
        this machine, and to feed the result back. No credentials are taken.
        """
        _log_usage(project, "list_projects")
        return {
            "status": "ok",
            "project": project,
            "designsync_call": {"method": "list_projects"},
            "note": (
                "Run DesignSync.list_projects under the active claude.ai login "
                "of this machine. The engine holds no token."
            ),
        }

    @mcp.tool
    async def claude_design_get_project(
        ctx: Context, project: str, project_id: str
    ) -> dict:
        """Read one Claude Design project's metadata (read — no prompt)."""
        _log_usage(project, "get_project")
        return {
            "status": "ok",
            "project": project,
            "designsync_call": {"method": "get_project", "projectId": project_id},
        }

    @mcp.tool
    async def claude_design_create_project(
        ctx: Context,
        project: str,
        project_root: str,
        name: str,
        session_projects: list[dict] | None = None,
    ) -> dict:
        """Create a Claude Design project and anchor its projectId (AC-04).

        Verifies an active login first (AC-06). The actual creation is a
        DesignSync ``create_project`` call (permission-prompted) the agent
        runs; this tool returns the call to make and, once the agent reports
        the new ``projectId`` back via ``claude_design_status``/anchor, the
        engine persists it. No token is accepted or stored.
        """
        identity = assert_session_identity(session_projects)
        if not identity["ok"]:
            return {
                "status": "pending",
                "project": project,
                "reason": identity["reason"],
            }
        _log_usage(project, "create_project")
        return {
            "status": "ok",
            "project": project,
            "designsync_call": {"method": "create_project", "name": name},
            "after": (
                "When DesignSync returns the new projectId, the engine anchors "
                "it in veg.claude_design.projectId (no secret persisted)."
            ),
        }

    @mcp.tool
    async def claude_design_sync_design_system(
        ctx: Context,
        project: str,
        project_root: str,
        session_projects: list[dict] | None = None,
    ) -> dict:
        """Plan the design-system sync to Claude Design (AC-02, AC-06).

        Resolves the topology gate (UC-2903) to find the site and projectId,
        verifies the active session is writable, and returns an ordered
        DesignSync plan (read → finalize_plan → write). Marks ``pending`` —
        never raises — when there is no login or no compiled design-system.
        """
        root = Path(project_root)
        settings = _read_project_settings(root)
        # Provider must include claude_design (validated upstream by /plan).
        if "claude_design" not in parse_providers(settings):
            return {
                "status": "skipped",
                "project": project,
                "reason": "claude_design not in veg.providers",
            }

        gate, site = evaluate_gate(project_root)
        if not gate.ready:
            return {
                "status": "pending",
                "project": project,
                "reason": gate.reason,
                "site": str(site.site_path),
            }

        cd_cfg = claude_design_config(settings)
        project_id = cd_cfg.get("projectId")

        write_check = resolve_writability(project_id, session_projects)
        if not write_check["writable"]:
            return {
                "status": "pending",
                "project": project,
                "reason": write_check["reason"],
            }

        _log_usage(project, "sync_design_system")
        plan = build_sync_plan(
            project_id=project_id or "<to-create>",
            site_path=str(site.site_path),
            writes=["components/**", "tokens/**", "_ds_bundle.js", "styles.css"],
        )
        validate_plan_ordering(plan["ordered_steps"])
        result: dict[str, Any] = {
            "status": "ok",
            "project": project,
            "site": str(site.site_path),
            "anchor_settings": str(site.anchor_settings_path),
            "consumes_from_orchestrator": site.consumes_from_orchestrator,
            "plan": plan,
        }
        if write_check.get("foreign_owner"):
            result["warning"] = (
                f"projectId owned by {write_check['foreign_owner']}; the active "
                "claude.ai session is writable and will be used (its "
                "subscription is consumed)."
            )
        return result

    @mcp.tool
    async def claude_design_status(
        ctx: Context,
        project: str,
        project_root: str,
        session_projects: list[dict] | None = None,
    ) -> dict:
        """Report the Claude Design capability state for a project.

        Surfaces providers, anchored projectId, gate readiness, and whether an
        active claude.ai login is present on this machine (so it's auditable
        whose subscription would be consumed). Read-only; never raises.
        """
        root = Path(project_root)
        settings = _read_project_settings(root)
        providers = parse_providers(settings)
        gate, site = evaluate_gate(project_root)
        cd_cfg = claude_design_config(settings)
        identity = assert_session_identity(session_projects)
        return {
            "status": "ok",
            "project": project,
            "providers": providers,
            "claude_design_active": "claude_design" in providers,
            "projectId": cd_cfg.get("projectId"),
            "site": str(site.site_path),
            "role": site.role,
            "gate_ready": gate.ready,
            "gate_reason": gate.reason,
            "login_active": identity["ok"],
            "no_delete_project": (
                "DesignSync exposes no delete_project; removing a Claude Design "
                "project is a manual action in claude.ai."
            ),
        }
