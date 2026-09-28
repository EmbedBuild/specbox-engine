"""Caller scope for the shared state registry — UC-3802.

Origin: an external tester (2026-09-24) called ``list_onboarded_projects`` on
the hosted MCP and received the whole ``/data/state/registry.json``: ~100
projects with free-text descriptions (client names, contract amounts, NDA
notes), repository URLs and local paths. The tool had no ``ctx``, no identity
and no scoping — the registry is shared by every session of the server.

This module is the single chokepoint that answers two questions for every
tool that reads or writes that shared registry:

1. **Who is calling?** — :func:`resolve_caller_scope` turns the session's
   native ``dev_token`` (or an explicit token) into a :class:`CallerScope`:
   the developer plus the set of native projects they are a member of. No
   token, an invalid one, or a server without the identity database all map
   to :class:`~server.coordination.identity.UnauthenticatedError` — the tool
   answers with the uniform UNAUTHENTICATED payload and **no data** (AC-01).

2. **What may they see?** — :meth:`CallerScope.can_see` accepts an entry when
   it was registered by the caller or when it is bound to a native project the
   caller belongs to (AC-02). Anything else is invisible: not filtered out of a
   payload, simply never read into one. An entry the caller cannot see is
   reported exactly like an entry that does not exist, so names cannot be
   enumerated.

The registry also stops carrying the fields that made the leak painful
(AC-04): ``description`` and local paths are neither written by the tools nor
returned — :data:`SENSITIVE_REGISTRY_FIELDS` is the shared list, consumed by
the writers here and by :mod:`server.registry_hygiene` (the operator's purge).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import asyncpg
import structlog

from .i18n_messages import extract_locale_from_ctx, unauthenticated_payload
from .identity import UnauthenticatedError, resolve_developer

logger = structlog.get_logger(__name__)

#: Registry field naming the developer who registered the entry (AC-02).
REGISTERED_BY_FIELD = "registered_by"

#: Registry field binding an entry to its native tenant (``owner/repo``).
NATIVE_PROJECT_ID_FIELD = "native_project_id"

#: Fields that never belong in the shared registry or in a project's
#: ``meta.json`` (AC-04): free text about the project and anything that
#: describes the developer's machine. Writers drop them; the hygiene tool
#: removes them from existing state.
SENSITIVE_REGISTRY_FIELDS: tuple[str, ...] = (
    "description",
    "path",
    "local_path",
    "project_path",
    "freeform_root_absolute",
    "root_path",
    "developer",
)

#: What a tool may return about an entry the caller is allowed to see. A
#: whitelist, so a field added to the registry tomorrow is not exposed by
#: accident — and the sensitive fields above are never part of it.
PUBLIC_ENTRY_FIELDS: tuple[str, ...] = (
    "stack",
    "infra",
    "repo_url",
    "registered_at",
    "engine_version",
    "status",
    "archived_at",
    "spec_backend",
    "board_id",
    "trello_board_id",
    "multirepo_role",
    "multirepo_group",
    "backend_history",
    "mirror",
    NATIVE_PROJECT_ID_FIELD,
    REGISTERED_BY_FIELD,
)


@dataclass(frozen=True)
class CallerScope:
    """An authenticated developer and the native projects they belong to.

    Never carries the token. ``project_ids`` are canonical ``owner/repo`` ids
    taken from ``project_members`` at resolution time.
    """

    developer_id: str
    display_name: str
    project_ids: frozenset[str]

    def can_see(self, name: str, entry: Mapping[str, Any] | None) -> bool:
        """True when the registry entry ``name`` belongs to this caller (AC-02).

        An entry is the caller's when they registered it, or when it is bound
        to a native project they are a member of — through its
        ``native_project_id``, a native ``board_id``, its mirror tenant, or
        the entry name itself when the project was registered under its
        canonical id.
        """
        data: Mapping[str, Any] = entry or {}
        owner = data.get(REGISTERED_BY_FIELD)
        if isinstance(owner, str) and owner and owner == self.developer_id:
            return True
        candidates: set[Any] = {name, data.get(NATIVE_PROJECT_ID_FIELD), data.get("project_id")}
        if data.get("spec_backend") == "native":
            candidates.add(data.get("board_id"))
        mirror = data.get("mirror")
        if isinstance(mirror, Mapping):
            candidates.add(mirror.get("project_id"))
        return any(isinstance(c, str) and c in self.project_ids for c in candidates)

    def visible(self, projects: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
        """The subset of ``projects`` (``name → entry``) this caller may see."""
        out: dict[str, dict[str, Any]] = {}
        for name, entry in (projects or {}).items():
            if isinstance(entry, Mapping) and self.can_see(name, entry):
                out[name] = dict(entry)
        return out

    def visible_names(self, projects: Mapping[str, Any] | None) -> list[str]:
        return sorted(self.visible(projects))


def public_entry(name: str, entry: Mapping[str, Any] | None) -> dict[str, Any]:
    """The tool-facing view of an entry the caller may see: whitelisted fields only."""
    data: Mapping[str, Any] = entry or {}
    view: dict[str, Any] = {"name": name}
    for field in PUBLIC_ENTRY_FIELDS:
        if field in data and field not in SENSITIVE_REGISTRY_FIELDS:
            view[field] = data[field]
    return view


def stamp_owner(entry: dict[str, Any], scope: CallerScope, native_project_id: str = "") -> dict[str, Any]:
    """Attribute a registry entry to the caller and drop sensitive fields (AC-02/AC-04).

    ``registered_by`` is set only when absent: re-registering your own
    project keeps you as owner, and a tool never reaches this point for
    someone else's entry. ``native_project_id`` is recorded when given.
    """
    entry.setdefault(REGISTERED_BY_FIELD, scope.developer_id)
    if native_project_id:
        entry[NATIVE_PROJECT_ID_FIELD] = native_project_id
    for field in SENSITIVE_REGISTRY_FIELDS:
        entry.pop(field, None)
    return entry


def strip_sensitive_fields(entry: Mapping[str, Any] | None) -> dict[str, Any]:
    """A copy of ``entry`` without any of :data:`SENSITIVE_REGISTRY_FIELDS`."""
    return {k: v for k, v in (entry or {}).items() if k not in SENSITIVE_REGISTRY_FIELDS}


# ── Identity resolution ─────────────────────────────────────────────


async def list_memberships(
    conn: asyncpg.Connection | asyncpg.Pool,
    developer_id: str,
) -> frozenset[str]:
    """Canonical ids of every native project ``developer_id`` is a member of."""

    async def _run(c: asyncpg.Connection) -> Iterable[asyncpg.Record]:
        return await c.fetch(
            "SELECT project_id FROM project_members WHERE developer_id = $1",
            developer_id,
        )

    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            rows = await _run(c)
    else:
        rows = await _run(conn)
    return frozenset(str(r["project_id"]) for r in rows)


async def resolve_caller_scope(ctx: Any, *, token: str = "") -> CallerScope:
    """Resolve the caller behind ``ctx`` (or an explicit ``token``) to a scope.

    The token comes from the explicit argument when given (tools that take a
    ``dev_token`` parameter, e.g. for a non-native primary session), otherwise
    from the native session opened with ``set_auth_token``. Raises
    :class:`UnauthenticatedError` when there is no usable token, when it maps
    to no developer, or when this server cannot reach the identity database —
    in every case the caller gets no data (AC-01). Tokens are never logged.
    """
    from ..auth_gateway import get_native_session
    from ..db.pool import get_pool

    tok = (token or "").strip()
    if not tok:
        if ctx is None:
            raise UnauthenticatedError("No MCP context and no dev_token: nobody is identified.")
        try:
            session = await get_native_session(ctx)
        except RuntimeError as exc:
            raise UnauthenticatedError(
                "No identified session: open one with set_auth_token(backend_type='native', "
                "token=<dev_token>, project_id=...) or pass dev_token."
            ) from exc
        tok = (session.get("dev_token") or "").strip()
    if not tok:
        raise UnauthenticatedError()

    try:
        pool = await get_pool()
        developer = await resolve_developer(pool, tok)
        memberships = await list_memberships(pool, developer.developer_id)
    except UnauthenticatedError:
        raise
    except Exception as exc:  # noqa: BLE001 — no DSN, DB down, loop closed…: nobody is identified
        # A server that cannot reach its identity database cannot vouch for
        # anyone. The reason stays in the server log (type only, never the
        # DSN or the token); the caller only learns that they are not
        # authenticated — the same envelope, no stack trace (UC-3802 AC-01).
        logger.warning("caller_scope_identity_unavailable", reason=type(exc).__name__)
        raise UnauthenticatedError("Identity service unavailable on this server.") from exc

    return CallerScope(
        developer_id=developer.developer_id,
        display_name=developer.display_name,
        project_ids=memberships,
    )


# ── Envelopes ───────────────────────────────────────────────────────


def unauthenticated_envelope(ctx: Any) -> dict[str, Any]:
    """The uniform UNAUTHENTICATED payload (UC-648 shape) for the session locale."""
    return unauthenticated_payload(locale=extract_locale_from_ctx(ctx))


def not_visible_envelope(project: str, scope: CallerScope, projects: Mapping[str, Any] | None) -> dict[str, Any]:
    """Answer for a project the caller may not see — identical to "not registered".

    Lists only the caller's own projects, so the reply never confirms whether
    ``project`` exists for someone else.
    """
    return {
        "error": f"Project '{project}' is not registered for your identity.",
        "code": "PROJECT_NOT_VISIBLE",
        "available": scope.visible_names(projects),
    }


def name_taken_envelope(project: str) -> dict[str, Any]:
    """Answer for a write on a name already registered under another identity."""
    return {
        "error": (
            f"The name '{project}' is already registered under another identity. "
            "Choose another name, or ask its owner to add you to the project."
        ),
        "code": "PROJECT_NAME_TAKEN",
    }
