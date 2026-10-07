"""A project's state is read and written only by who can see it — US-86 · UC-8603.

Many tools take a ``project`` name and turn it into
``STATE_PATH/projects/<project>``: the telemetry reports, the activity reads,
the audit evidence, the design usage logs. Until UC-8603 none of them asked
who was calling, and none checked the name, so on the hosted server any
session could write into another project's folder, read its activity, list
every registered project, or step out of ``projects/`` with ``../``.

Two pieces close it:

* :func:`project_state_dir` is the only way to build that folder. It accepts a
  plain name (spaces allowed) or a canonical ``owner/repo`` id, and rejects
  anything else — empty, absolute, ``\\``, ``.``/``..`` segments, more than one
  ``/`` — with :class:`InvalidProjectNameError` (``INVALID_PROJECT_NAME``).
* :class:`ProjectStateScopeMiddleware` runs before the tools: for
  :data:`PROJECT_NAME_TOOLS` it answers ``INVALID_PROJECT_NAME`` without
  calling the tool, and on a remote transport, for :data:`STATE_PROJECT_TOOLS`,
  it resolves the caller (:func:`resolve_caller_scope`) and lets the call
  through only when the project is registered and visible to them. Anything
  else is answered like a project that does not exist (T2): the reply lists
  only the caller's own projects.

On ``stdio`` the state belongs to whoever runs the server: names are still
checked, identity is not asked for.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import structlog

from ..transport import is_remote_transport
from .identity import UnauthenticatedError
from .scope import not_visible_envelope, resolve_caller_scope, unauthenticated_envelope
from .tool_envelope import envelope_result

logger = structlog.get_logger(__name__)

INVALID_PROJECT_NAME = "INVALID_PROJECT_NAME"

#: Tools whose ``project`` reads or writes that project's state. On a remote
#: transport the middleware lets them through only for a project the caller
#: can see. (The registry tools — onboard, register, upgrade, archive,
#: reset… — resolve the caller themselves since UC-3802/UC-3804.)
STATE_PROJECT_TOOLS: frozenset[str] = frozenset(
    {
        "report_session",
        "report_checkpoint",
        "report_healing",
        "report_acceptance_tests",
        "report_acceptance_validation",
        "report_merge_status",
        "report_feedback",
        "report_feedback_resolution",
        "report_e2e_results",
        "report_heartbeat",
        "get_project_activity",
        "get_project_timeline",
        "attach_audit_evidence",
        "get_last_audit",
        "upload_design_md_to_stitch",
    }
)

#: Tools whose ``project`` names a folder under ``projects/``: the name is
#: checked before the tool runs, on every transport.
PROJECT_NAME_TOOLS: frozenset[str] = STATE_PROJECT_TOOLS | frozenset(
    {
        "onboard_project",
        "register_project",
        "update_project_meta",
        "upgrade_project",
        "archive_project",
        "get_onboarding_status",
        "reset_project",
    }
)


class InvalidProjectNameError(ValueError):
    """The name cannot be a folder under ``projects/``."""

    code = INVALID_PROJECT_NAME


def check_project_name(project: Any) -> str:
    """Return ``project`` when it can name a folder under ``projects/``.

    Valid: a plain name (``moto.fan``, ``Gemelo Digital``) or a canonical
    ``owner/repo`` id. Invalid: not a string, empty, surrounding whitespace,
    absolute, a backslash or NUL, a ``.`` or ``..`` segment, an empty segment,
    or more than one ``/``.
    """
    if not isinstance(project, str) or not project.strip() or project != project.strip():
        raise InvalidProjectNameError("The project name is empty.")
    if "\\" in project or "\x00" in project or project.startswith("/"):
        raise InvalidProjectNameError(f"'{project}' is not a project name.")
    segments = project.split("/")
    if len(segments) > 2 or any(s.strip() in ("", ".", "..") or s != s.strip() for s in segments):
        raise InvalidProjectNameError(
            f"'{project}' is not a project name: use a name or an owner/repo id."
        )
    return project


def project_state_dir(state_path: Path, project: Any) -> Path:
    """``state_path/projects/<project>`` for a valid name; never outside it."""
    name = check_project_name(project)
    base = (state_path / "projects").resolve()
    path = (base / name).resolve()
    if path == base or base not in path.parents:
        raise InvalidProjectNameError(f"'{project}' is not a project name.")
    return state_path / "projects" / name


def invalid_name_envelope(project: Any, exc: InvalidProjectNameError) -> dict[str, Any]:
    return {"error": str(exc), "code": INVALID_PROJECT_NAME, "project": project if isinstance(project, str) else None}


def _registry_projects(state_path: Path) -> dict[str, Any]:
    try:
        data = json.loads((state_path / "registry.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    projects = data.get("projects") if isinstance(data, Mapping) else None
    return dict(projects) if isinstance(projects, Mapping) else {}


try:  # FastMCP is always present on the server; keep the module importable without it.
    from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
except ImportError:  # pragma: no cover
    Middleware = object  # type: ignore[assignment,misc]
    CallNext = Any  # type: ignore[assignment,misc]
    MiddlewareContext = Any  # type: ignore[assignment,misc]


class ProjectStateScopeMiddleware(Middleware):  # type: ignore[misc,valid-type]
    """Check the project name and, remotely, who may touch that project's state."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path

    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext) -> Any:  # type: ignore[valid-type]
        tool = str(getattr(context.message, "name", "") or "")
        if tool not in PROJECT_NAME_TOOLS:
            return await call_next(context)
        arguments = getattr(context.message, "arguments", None) or {}
        project = arguments.get("project") if isinstance(arguments, Mapping) else None
        try:
            check_project_name(project)
        except InvalidProjectNameError as exc:
            return await envelope_result(context, tool, invalid_name_envelope(project, exc))
        if tool not in STATE_PROJECT_TOOLS or not is_remote_transport():
            return await call_next(context)

        ctx = context.fastmcp_context
        try:
            scope = await resolve_caller_scope(ctx, token=str(arguments.get("dev_token") or ""))
        except UnauthenticatedError:
            return await envelope_result(context, tool, unauthenticated_envelope(ctx))
        projects = _registry_projects(self.state_path)
        entry = projects.get(project)
        if not isinstance(entry, Mapping) or not scope.can_see(project, entry):
            logger.info("project_state_not_visible", tool=tool, developer_id=scope.developer_id)
            return await envelope_result(context, tool, not_visible_envelope(project, scope, projects))
        return await call_next(context)
