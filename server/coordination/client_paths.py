"""A remote server never touches a path the client names — US-86 · UC-8604.

Threat model §8, rule 3: nothing from the server's disk on a remote transport.
These tools take a path that lives on the client's machine (``project_path``,
``project_root``, ``target_path``, ``design_md_path``, ``orchestrator_path``)
and resolve it on the server's filesystem. Remotely that reads or writes the
server's own disk — the engine's ``/app`` for the default ``"."``, or any
directory the server can write, other projects' state included — and the
client takes the answer as if it were about its repository.

:class:`ClientPathGuardMiddleware` answers before the tool runs, so no path is
resolved, no file is read, created or changed — unless the call brings the
content instead (content mode, :mod:`server.app_docs.workspace`):

* ``APP_DOCS_CONTENT_REQUIRED`` for the canonical documents, decisions queue,
  canonical decisions, autopilot log, drift, v5.29 migration and
  implementation status: send ``files_content`` and apply the returned
  ``files_changed`` / ``files_appended`` in the repository.
* ``CLIENT_CONTENT_REQUIRED`` for Claude Design (``files_content``), the
  Stitch prompt validator's palette (``design_md_content``), the multirepo
  satellite sync (``settings_content``) and the board diff, whose snapshots
  live in the client's ``.quality/board_snapshots`` (``from_content`` and
  ``to_content``, UC-8905).
* ``REMOTE_PATH_REJECTED`` where a remote server has nothing to do with the
  path: registering a DESIGN.md path for inline prefixes (use
  ``stitch_upload_design_md``) and the Trello/Plane → FreeForm download (use
  ``switch_project_backend``).

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
CLIENT_CONTENT_REQUIRED = "CLIENT_CONTENT_REQUIRED"
REMOTE_PATH_REJECTED = "REMOTE_PATH_REJECTED"


@dataclass(frozen=True)
class ClientPathRule:
    code: str
    path_params: tuple[str, ...]
    #: True when the tool works without the path: reject only if it is given.
    optional: bool = False
    #: Parameters that carry the content instead: when one is sent, the call passes.
    content_params: tuple[str, ...] = ()
    #: What to send instead of the path.
    how_to: str = ""


_FILES_HOW_TO = (
    "Send the files this tool reads as files_content ({relpath: text}, relative to the "
    "repository root) and apply the answer in your repository: write files_changed, "
    "delete files_deleted, append files_appended. files_requested lists files the tool "
    "looked for and you did not send; send them too when they exist."
)


def _app_docs(param: str = "project_path") -> ClientPathRule:
    return ClientPathRule(APP_DOCS_CONTENT_REQUIRED, (param,), content_params=("files_content",), how_to=_FILES_HOW_TO)


def _content(*params: str, content: str, how_to: str, optional: bool = False) -> ClientPathRule:
    return ClientPathRule(CLIENT_CONTENT_REQUIRED, params, optional, (content,), how_to)


def _rejected(*params: str, how_to: str, optional: bool = False) -> ClientPathRule:
    return ClientPathRule(REMOTE_PATH_REJECTED, params, optional, (), how_to)


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
    # Claude Design, Stitch prompt palette, multirepo sync: content mode
    "claude_design_status": _content(
        "project_root",
        content="files_content",
        how_to=(
            "Send files_content with .claude/settings.local.json, the design-system's package.json "
            "and one file of its dist/ (or its Storybook config); a satellite sends the orchestrator's."
        ),
    ),
    "claude_design_sync_design_system": _content(
        "project_root",
        content="files_content",
        how_to=(
            "Send files_content with .claude/settings.local.json, the design-system's package.json "
            "and one file of its dist/ (or its Storybook config); a satellite sends the orchestrator's."
        ),
    ),
    "validate_stitch_prompt": _content(
        "project_root",
        content="design_md_content",
        optional=True,
        how_to="Send doc/design/DESIGN.md as design_md_content to resolve named colours against its palette.",
    ),
    "sync_multirepo_state": _content(
        "orchestrator_path",
        content="settings_content",
        how_to="Send the orchestrator's .claude/settings.local.json as settings_content.",
    ),
    # Board snapshots: files of the client's repository, named by board and snapshot (UC-8905)
    "get_board_diff": ClientPathRule(
        CLIENT_CONTENT_REQUIRED,
        ("from_snapshot", "to_snapshot"),
        content_params=("from_content", "to_content"),
        how_to=(
            "Read .quality/board_snapshots/<board_id>/<snapshot>.json in your repository and "
            "send both snapshots as from_content and to_content."
        ),
    ),
    # Nothing to do with a client path on a remote server
    "upload_design_md_to_stitch": _rejected(
        "design_md_path",
        "project_root",
        optional=True,
        how_to=(
            "It registers a local path for inline prompt prefixes. Remotely, upload the document "
            "with stitch_upload_design_md (design_md_content) and create the design system from it."
        ),
    ),
    "migrate_to_freeform_tool": _rejected(
        "target_path",
        how_to="Use switch_project_backend (source → freeform) with the MCP remote, or this tool with the local MCP.",
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
        "content_params": list(rule.content_params),
        "how_to": rule.how_to,
    }


def rule_rejects(rule: ClientPathRule, arguments: Mapping[str, Any]) -> bool:
    if any(arguments.get(p) is not None for p in rule.content_params):
        return False
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
