"""A remote server never touches a path the client names — US-86 · UC-8604.

Threat model §8, rule 3: nothing from the server's disk on a remote transport.
These tools take a path that lives on the client's machine (``project_path``,
``project_root``, ``target_path``, ``design_md_path``, ``orchestrator_path``)
and resolve it on the server's filesystem. Remotely that reads or writes the
server's own disk — the engine's ``/app`` for the default ``"."``, or any
directory the server can write, other projects' state included — and the
client takes the answer as if it were about its repository.

:class:`ClientPathGuardMiddleware` answers before the tool runs, so no path is
resolved, no file is read, created or changed:

* ``APP_DOCS_CONTENT_REQUIRED`` for the canonical documents, decisions queue,
  canonical decisions, autopilot log, drift, v5.29 migration and
  implementation status: they work on ``doc/app/``, ``.quality/`` or the PRD of
  the client's repository.
* ``REMOTE_PATH_REJECTED`` for the rest: Claude Design's ``project_root``,
  DESIGN.md registration, the Stitch prompt validator's palette, the multirepo
  satellite sync and the Trello/Plane → FreeForm download.

A rule with ``optional=True`` only rejects when the path is actually given
(the tool works without it). On ``stdio`` the server runs on the client's
machine and nothing changes.

The backend-switch tools (``switch_backend``, ``switch_project_backend``,
``enable_mirror``, ``disable_mirror``) are not rejected: remotely they write
the registry only and return the local files' changes for the client to apply
(:mod:`server.migration.transactional_switch`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..transport import is_remote_transport
from .tool_envelope import envelope_result

APP_DOCS_CONTENT_REQUIRED = "APP_DOCS_CONTENT_REQUIRED"
REMOTE_PATH_REJECTED = "REMOTE_PATH_REJECTED"


@dataclass(frozen=True)
class ClientPathRule:
    code: str
    path_params: tuple[str, ...]
    #: True when the tool works without the path: reject only if it is given.
    optional: bool = False


def _app_docs(param: str = "project_path") -> ClientPathRule:
    return ClientPathRule(APP_DOCS_CONTENT_REQUIRED, (param,))


def _rejected(*params: str, optional: bool = False) -> ClientPathRule:
    return ClientPathRule(REMOTE_PATH_REJECTED, params, optional)


#: Every registered tool that resolves a client path on the server's disk.
#: ``tests/test_client_path_guard.py`` checks this list against the server's
#: tool registry (UC-8606 extends that check to new tools).
CLIENT_PATH_TOOLS: Mapping[str, ClientPathRule] = {
    # Canonical documents and their sync lock (server/app_docs/sync.py)
    "verify_app_docs": _app_docs(),
    "apply_app_docs_sync": _app_docs(),
    "record_app_docs_signature": _app_docs(),
    # Canonical decisions store (server/app_docs/canonical.py)
    "get_canonical_decision": _app_docs(),
    "list_canonical_decisions": _app_docs(),
    "record_canonical_confirmation": _app_docs(),
    "revoke_canonical_decision": _app_docs(),
    # Deferred decisions queue (server/app_docs/queue.py)
    "enqueue_decision_tool": _app_docs(),
    "list_decisions_queue": _app_docs(),
    "resolve_queue_entry": _app_docs(),
    # Autopilot log, drift, backend discovery, v5.29 migration
    "evaluate_autopilot_decision": _app_docs(),
    "detect_app_docs_drift": _app_docs(),
    "app_docs_drift_for_heartbeat": _app_docs(),
    "detect_project_backend": _app_docs(),
    "detect_v529_migration_case": _app_docs(),
    "run_v529_migration": _app_docs(),
    # Implementation status in the PRD (server/tools/sync.py)
    "get_implementation_status": _app_docs(),
    "write_implementation_status": _app_docs(),
    # Everything else that reads or writes a client path
    "migrate_to_freeform_tool": _rejected("target_path"),
    "claude_design_status": _rejected("project_root"),
    "claude_design_create_project": _rejected("project_root"),
    "claude_design_sync_design_system": _rejected("project_root"),
    "upload_design_md_to_stitch": _rejected("design_md_path", "project_root", optional=True),
    "validate_stitch_prompt": _rejected("project_root", optional=True),
    "sync_multirepo_state": _rejected("orchestrator_path"),
}

_HOW_TO = {
    APP_DOCS_CONTENT_REQUIRED: (
        "This tool works on doc/app/, .quality/ or the PRD of your repository. Run it "
        "with the engine's local MCP server (stdio) from your repository; the "
        "app-docs-sync-guard hook already computes the document signatures locally."
    ),
    REMOTE_PATH_REJECTED: (
        "Run it with the engine's local MCP server (stdio) from your repository, or "
        "call it without the path when the tool allows it."
    ),
}


def rejection(tool: str, rule: ClientPathRule, given: Mapping[str, Any]) -> dict[str, Any]:
    """The envelope for ``tool`` called remotely with a client path."""
    names = ", ".join(rule.path_params)
    return {
        "error": (
            f"{rule.code}: this MCP server is remote, so it cannot read or write "
            f"{names} — that path lives on your machine, not on the server."
        ),
        "code": rule.code,
        "tool": tool,
        "path_params": list(rule.path_params),
        "how_to": _HOW_TO[rule.code],
    }


def rule_rejects(rule: ClientPathRule, arguments: Mapping[str, Any]) -> bool:
    if not rule.optional:
        return True
    return any(arguments.get(p) not in (None, "") for p in rule.path_params)


try:  # FastMCP is always present on the server; keep the module importable without it.
    from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
except ImportError:  # pragma: no cover
    Middleware = object  # type: ignore[assignment,misc]
    CallNext = Any  # type: ignore[assignment,misc]
    MiddlewareContext = Any  # type: ignore[assignment,misc]


class ClientPathGuardMiddleware(Middleware):  # type: ignore[misc,valid-type]
    """On a remote transport, answer before any tool resolves a client path."""

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:  # type: ignore[valid-type]
        tool = str(getattr(context.message, "name", "") or "")
        rule = CLIENT_PATH_TOOLS.get(tool)
        if rule is None or not is_remote_transport():
            return await call_next(context)
        arguments = getattr(context.message, "arguments", None) or {}
        if not isinstance(arguments, Mapping) or not rule_rejects(rule, arguments):
            return await call_next(context)

        return await envelope_result(context, tool, rejection(tool, rule, arguments))
