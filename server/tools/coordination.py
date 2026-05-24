"""MCP tools for the NativeBackend coordination layer — identity + reservations (H2/H3).

These tools live outside the spec-driven tool set on purpose: they operate on
the coordination tables (developers / project_members / uc_reservations /
branch_registry), not on the spec hierarchy. They are only meaningful for a
native session.

Tools (H2 — identity)
---------------------
- ``whoami`` — resolve the session's developer token to {developer_id,
  display_name}; UNAUTHENTICATED on an invalid/absent token [AC-15].

  Note: prior to UC-504 this module also exposed an admin tool to bootstrap
  developers (developer + token in one MCP call). That surface was removed
  (AC-16): developer registration is now an admin/panel concern, and tokens
  are minted via the internal helpers
  :func:`server.coordination.identity.register_mcp_token` /
  :func:`~server.coordination.identity.revoke_mcp_token`, NOT through MCP.

Tools (H3 — reservations)
-------------------------
- ``reserve_uc`` — reserve a UC for the authenticated developer [AC-16].
  Renamed from ``claim_uc`` in v5.35.0 (US-CLAIM-RENAME / UC-603). The
  ``claim_uc`` MCP tool name is reintroduced as a deprecated alias in
  UC-604 and removed in v5.37.0 / UC-612.
- ``release_uc`` — release a reservation (owner only) [AC-17].
- ``register_native_branch`` — register a branch ↔ UC mapping; rejects
  collisions and suggests ``feature/{uc_id}-...`` naming [AC-23].

Every reservation tool authenticates via the session token first (Frontier 1)
and authorizes against the current project — UNAUTHENTICATED / FORBIDDEN apply.
"""

from __future__ import annotations

import warnings
from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_native_session
from ..coordination.branches import (
    BranchCollisionError,
    register_branch,
    suggest_branch_name,
)
from ..coordination.identity import (
    ForbiddenError,
    UnauthenticatedError,
    authenticate_and_authorize,
    resolve_developer,
)
from ..coordination.reservations import (
    AlreadyReservedError,
    NotReservationOwnerError,
    release_uc as _release_uc,
    reserve_uc as _reserve_uc,
)
from ..db.pool import get_pool

logger = structlog.get_logger(__name__)


async def _authed_dev(ctx: Context):
    """Resolve session → (project_id, Developer, pool) or raise a coded error.

    Centralizes the Frontier-1 gate for the reservation tools: native session +
    token resolution + project membership. Returns the project_id, the
    authenticated Developer, and the pool. Raises UnauthenticatedError /
    ForbiddenError (callers translate to coded dicts).
    """
    session = await get_native_session(ctx)
    project_id = session["project_id"]
    token = session.get("dev_token", "")
    pool = await get_pool()
    async with pool.acquire() as conn:
        dev = await authenticate_and_authorize(conn, token=token, project_id=project_id)
    return project_id, dev, pool


async def whoami(ctx: Context) -> dict[str, Any]:
    """Resolve the session's developer token to its identity [AC-15].

    Returns ``{developer_id, display_name}`` on success. With an absent or
    invalid token, returns ``UNAUTHENTICATED`` WITHOUT revealing whether a
    developer exists (no enumeration).
    """
    try:
        session = await get_native_session(ctx)
    except RuntimeError as e:
        return {"error": str(e), "code": "NOT_NATIVE_SESSION"}

    token = session.get("dev_token", "")
    pool = await get_pool()
    try:
        dev = await resolve_developer(pool, token)
    except UnauthenticatedError as e:
        # Same message whether the token is absent, malformed, or simply
        # matches no developer — no enumeration signal.
        return {"error": str(e), "code": "UNAUTHENTICATED"}

    return {
        "success": True,
        "developer_id": dev.developer_id,
        "display_name": dev.display_name,
        "summary": f"Autenticado como {dev.developer_id} ({dev.display_name}).",
    }


# ── H3: reservation tools ────────────────────────────────────────────


async def reserve_uc(uc_id: str, ctx: Context, branch: str = "") -> dict[str, Any]:
    """Reserve a UC for the authenticated developer [AC-16].

    Frontier 1 first (UNAUTHENTICATED / FORBIDDEN). Then a single INSERT under
    the UNIQUE(project_id, uc_id) constraint: if another dev already holds it,
    returns ALREADY_RESERVED with owner / reserved_at / branch [AC-19]. Same dev
    re-reserving is idempotent.
    """
    try:
        project_id, dev, pool = await _authed_dev(ctx)
    except RuntimeError as e:
        return {"error": str(e), "code": "NOT_NATIVE_SESSION"}
    except UnauthenticatedError as e:
        return {"error": str(e), "code": "UNAUTHENTICATED"}
    except ForbiddenError as e:
        return {"error": str(e), "code": "FORBIDDEN"}

    try:
        async with pool.acquire() as conn:
            reservation = await _reserve_uc(
                conn,
                project_id=project_id,
                uc_id=uc_id,
                developer_id=dev.developer_id,
                branch=branch,
            )
    except AlreadyReservedError as e:
        return {"error": str(e), **e.to_payload()}

    return {
        "success": True,
        "code": "RESERVED",
        **reservation.to_public(),
        "summary": f"UC {uc_id} reservado por {dev.developer_id}.",
    }


# ── H3: deprecated alias (UC-604) ────────────────────────────────────
#
# claim_uc is the v5.34.x name for what is now reserve_uc. We keep it
# registered as a separate MCP tool during the v5.35-v5.36 deprecation
# window so callers that have not yet migrated keep working. The alias
# does three observable things on top of forwarding to reserve_uc:
#
#   1. Emits a single DeprecationWarning (stacklevel=2 so the warning
#      points at the *caller*, not at this wrapper) — capturable by
#      `pytest.warns(DeprecationWarning)`.
#   2. Logs a structured "deprecated_tool_called" record so operators
#      can quantify legacy usage before the v5.37.0 removal.
#   3. Enriches the success/conflict payload with legacy aliases:
#        - `claimed_at` mirrors `reserved_at` (same value)
#        - `legacy_code` maps the new code to its v5.34.x name
#          (RESERVED → CLAIMED, ALREADY_RESERVED → ALREADY_CLAIMED).
#      Auth-failure codes (UNAUTHENTICATED / FORBIDDEN / NOT_NATIVE_SESSION)
#      are not rename-specific and pass through untouched.
#
# UC-612 will remove this entire block in v5.37.0 along with the dual
# payload fields and the structured log event.

#: New → legacy ``code`` mapping for the v5.35-v5.36 deprecation window.
#: Anything not in this dict is not specific to the claim→reservation
#: rename and passes through without a ``legacy_code`` annotation.
_DEPRECATED_CODE_ALIASES: dict[str, str] = {
    "RESERVED": "CLAIMED",
    "ALREADY_RESERVED": "ALREADY_CLAIMED",
}

#: Description string registered on FastMCP for the deprecated alias.
#: The literal prefix is asserted by UC-604 AC-01.
_CLAIM_UC_DEPRECATED_DESCRIPTION = (
    "[DEPRECATED desde v5.35.0 — usa reserve_uc. Se elimina en v5.37.0] "
    "Alias deprecado de reserve_uc. Llamarlo emite DeprecationWarning y "
    "devuelve un payload enriquecido con las claves legacy (claimed_at, "
    "legacy_code) además de las nuevas (reserved_at, code). Migra a reserve_uc."
)


def _add_legacy_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    """Return ``payload`` with the v5.34.x legacy keys appended.

    Adds ``claimed_at`` mirroring ``reserved_at`` (when present) and
    ``legacy_code`` mapping the new ``code`` via
    :data:`_DEPRECATED_CODE_ALIASES`. The original dict is not mutated.
    """
    enriched = dict(payload)
    if "reserved_at" in enriched and "claimed_at" not in enriched:
        enriched["claimed_at"] = enriched["reserved_at"]
    code = enriched.get("code")
    if isinstance(code, str) and code in _DEPRECATED_CODE_ALIASES:
        enriched["legacy_code"] = _DEPRECATED_CODE_ALIASES[code]
    return enriched


async def claim_uc(uc_id: str, ctx: Context, branch: str = "") -> dict[str, Any]:
    """[DEPRECATED v5.35.0] Alias of :func:`reserve_uc`. Removed in v5.37.0.

    Behaves exactly like :func:`reserve_uc` but additionally:

    - emits a :class:`DeprecationWarning` pointing at the caller,
    - logs a structured ``deprecated_tool_called`` event,
    - enriches the response payload with ``claimed_at`` (= ``reserved_at``)
      and ``legacy_code`` (the v5.34.x equivalent of the new ``code``).

    The dual payload lets callers migrate at their own pace during
    v5.35-v5.36 without breaking. UC-612 removes this alias entirely in
    v5.37.0.
    """
    warnings.warn(
        "claim_uc is deprecated since v5.35.0; use reserve_uc. "
        "Removed in v5.37.0.",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.info(
        "deprecated_tool_called",
        tool="claim_uc",
        since_version="v5.35.0",
        remove_in_version="v5.37.0",
        replacement="reserve_uc",
    )
    payload = await reserve_uc(uc_id, ctx, branch)
    return _add_legacy_aliases(payload)


async def release_uc(uc_id: str, ctx: Context) -> dict[str, Any]:
    """Release a UC reservation — only the owner may do so [AC-17].

    Returns NOT_RESERVATION_OWNER (reservation untouched) if a different dev holds it.
    """
    try:
        project_id, dev, pool = await _authed_dev(ctx)
    except RuntimeError as e:
        return {"error": str(e), "code": "NOT_NATIVE_SESSION"}
    except UnauthenticatedError as e:
        return {"error": str(e), "code": "UNAUTHENTICATED"}
    except ForbiddenError as e:
        return {"error": str(e), "code": "FORBIDDEN"}

    try:
        async with pool.acquire() as conn:
            released = await _release_uc(
                conn,
                project_id=project_id,
                uc_id=uc_id,
                developer_id=dev.developer_id,
            )
    except NotReservationOwnerError as e:
        return {
            "error": str(e),
            "code": "NOT_RESERVATION_OWNER",
            "uc_id": uc_id,
            "owner": e.owner,
        }

    if not released:
        return {
            "success": True,
            "uc_id": uc_id,
            "released": False,
            "summary": f"UC {uc_id} no tenía reserva.",
        }
    return {
        "success": True,
        "uc_id": uc_id,
        "released": True,
        "summary": f"UC {uc_id} liberado.",
    }


async def register_native_branch(uc_id: str, branch: str, ctx: Context) -> dict[str, Any]:
    """Register a branch ↔ UC mapping; reject collisions; suggest naming [AC-23].

    On a collision (branch already used for another UC/dev) returns
    BRANCH_COLLISION plus the ``suggested`` ``feature/{uc_id}-...`` name.
    """
    try:
        project_id, dev, pool = await _authed_dev(ctx)
    except RuntimeError as e:
        return {"error": str(e), "code": "NOT_NATIVE_SESSION"}
    except UnauthenticatedError as e:
        return {"error": str(e), "code": "UNAUTHENTICATED"}
    except ForbiddenError as e:
        return {"error": str(e), "code": "FORBIDDEN"}

    try:
        async with pool.acquire() as conn:
            entry = await register_branch(
                conn,
                project_id=project_id,
                branch=branch,
                uc_id=uc_id,
                developer_id=dev.developer_id,
            )
    except BranchCollisionError as e:
        return {
            "error": str(e),
            "code": "BRANCH_COLLISION",
            "branch": branch,
            "existing_uc": e.existing_uc,
            "existing_developer": e.existing_dev,
            "suggested": suggest_branch_name(uc_id),
        }

    return {
        "success": True,
        "project_id": entry.project_id,
        "branch": entry.branch,
        "uc_id": entry.uc_id,
        "developer_id": entry.developer_id,
        "summary": f"Branch {branch!r} registrado para {uc_id}.",
    }


def register_coordination_tools(mcp_instance) -> None:
    """Register the native coordination tools (H2 identity + H3 reservations).

    UC-504: the legacy admin bootstrap tool was removed from the MCP surface.
    Developer registration is now an admin/panel concern; tokens are minted
    via the internal :func:`server.coordination.identity.register_mcp_token`
    helper, never through MCP.

    UC-603: ``claim_uc`` was renamed to ``reserve_uc`` and ``ALREADY_CLAIMED``
    became ``ALREADY_RESERVED``.

    UC-604: ``claim_uc`` is reintroduced as a **deprecated alias** of
    :func:`reserve_uc` for the v5.35-v5.36 window. It emits a
    :class:`DeprecationWarning` + structured log entry on every call and
    returns a payload that carries BOTH vocabularies. UC-612 removes it in
    v5.37.0.
    """
    # H2 — identity
    mcp_instance.tool(
        description="Resolve the current session's developer token to {developer_id, display_name}. "
        "Returns UNAUTHENTICATED for an absent/invalid token. Native backend only."
    )(whoami)
    # H3 — reservations
    mcp_instance.tool(
        description=(
            "Reservar un UC para el developer autenticado (reserve_uc). Devuelve "
            "code=RESERVED en éxito o ALREADY_RESERVED (con owner/reserved_at/branch) "
            "si otro dev lo tiene. Si el caller no es el dueño al liberarlo, "
            "release_uc devuelve NOT_RESERVATION_OWNER. Native backend only."
        )
    )(reserve_uc)
    # H3 — deprecated alias (UC-604, removed in v5.37.0 / UC-612)
    mcp_instance.tool(description=_CLAIM_UC_DEPRECATED_DESCRIPTION)(claim_uc)
    mcp_instance.tool(
        description=(
            "Liberar la reserva de un UC (release_uc). Solo el dueño puede hacerlo; "
            "en caso contrario devuelve NOT_RESERVATION_OWNER y la reserva queda intacta. "
            "Native backend only."
        )
    )(release_uc)
    mcp_instance.tool(
        description="Register a branch <-> UC mapping. Rejects branch-name collisions and "
        "suggests feature/{uc_id}-... naming. Native backend only."
    )(register_native_branch)
