"""MCP tools for the NativeBackend coordination layer — identity + claims (H2/H3).

These tools live outside the spec-driven tool set on purpose: they operate on
the coordination tables (developers / project_members / uc_claims /
branch_registry), not on the spec hierarchy. They are only meaningful for a
native session.

Tools (H2 — identity)
---------------------
- ``register_native_developer`` — admin bootstrap: create/update a developer and
  associate it with the current native project. Stores only the token hash.
- ``whoami`` — resolve the session's developer token to {developer_id,
  display_name}; UNAUTHENTICATED on an invalid/absent token [AC-15].

Tools (H3 — claims)
-------------------
- ``claim_uc`` — claim a UC for the authenticated developer [AC-16].
- ``release_uc`` — release a claim (owner only) [AC-17].
- ``register_native_branch`` — register a branch ↔ UC mapping; rejects
  collisions and suggests ``feature/{uc_id}-...`` naming [AC-23].

Every claim tool authenticates via the session token first (Frontier 1) and
authorizes against the current project — UNAUTHENTICATED / FORBIDDEN apply.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_native_session
from ..coordination.branches import (
    BranchCollisionError,
    register_branch,
    suggest_branch_name,
)
from ..coordination.claims import (
    AlreadyClaimedError,
    NotClaimOwnerError,
    claim_uc as _claim_uc,
    release_uc as _release_uc,
)
from ..coordination.identity import (
    ForbiddenError,
    UnauthenticatedError,
    add_project_member,
    authenticate_and_authorize,
    register_developer,
    resolve_developer,
)
from ..db.pool import get_pool

logger = structlog.get_logger(__name__)


async def _authed_dev(ctx: Context):
    """Resolve session → (project_id, Developer, pool) or raise a coded error.

    Centralizes the Frontier-1 gate for the claim tools: native session +
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


async def register_native_developer(
    developer_id: str,
    display_name: str,
    dev_token: str,
    ctx: Context,
    make_member: bool = True,
) -> dict[str, Any]:
    """Register (or update) a developer for the current native project.

    Admin/bootstrap operation. The ``dev_token`` is hashed (SHA-256) before
    storage — the clear token is never persisted or logged [AC-10, AC-11].

    Args:
        developer_id: Stable, human-readable id (e.g. "jesus").
        display_name: Human display name.
        dev_token: The developer's token. Hashed, never stored in clear.
        make_member: When True, also associates the developer with the current
            project (so they pass authorization on native calls) [AC-13].

    Returns:
        ``{success, developer_id, display_name, project_id, member}`` — never
        echoes the token.
    """
    try:
        session = await get_native_session(ctx)
    except RuntimeError as e:
        return {"error": str(e), "code": "NOT_NATIVE_SESSION"}

    project_id = session["project_id"]
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                dev = await register_developer(
                    conn,
                    developer_id=developer_id,
                    display_name=display_name,
                    token=dev_token,
                )
                if make_member:
                    await add_project_member(
                        conn, project_id=project_id, developer_id=developer_id
                    )
    except UnauthenticatedError as e:
        # hash_token rejects an empty token.
        return {"error": str(e), "code": "UNAUTHENTICATED"}

    return {
        "success": True,
        "developer_id": dev.developer_id,
        "display_name": dev.display_name,
        "project_id": project_id,
        "member": make_member,
        "summary": (
            f"Developer {dev.developer_id!r} registrado"
            + (f" y asociado al proyecto {project_id!r}." if make_member else ".")
        ),
    }


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


# ── H3: claim tools ──────────────────────────────────────────────────


async def claim_uc(uc_id: str, ctx: Context, branch: str = "") -> dict[str, Any]:
    """Claim a UC for the authenticated developer [AC-16].

    Frontier 1 first (UNAUTHENTICATED / FORBIDDEN). Then a single INSERT under
    the UNIQUE(project_id, uc_id) constraint: if another dev already holds it,
    returns ALREADY_CLAIMED with owner / claimed_at / branch [AC-19]. Same dev
    re-claiming is idempotent.
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
            claim = await _claim_uc(
                conn,
                project_id=project_id,
                uc_id=uc_id,
                developer_id=dev.developer_id,
                branch=branch,
            )
    except AlreadyClaimedError as e:
        return {"error": str(e), **e.to_conflict()}

    return {
        "success": True,
        **claim.to_public(),
        "summary": f"UC {uc_id} reclamado por {dev.developer_id}.",
    }


async def release_uc(uc_id: str, ctx: Context) -> dict[str, Any]:
    """Release a UC claim — only the owner may do so [AC-17].

    Returns NOT_CLAIM_OWNER (claim untouched) if a different dev holds it.
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
    except NotClaimOwnerError as e:
        return {
            "error": str(e),
            "code": "NOT_CLAIM_OWNER",
            "uc_id": uc_id,
            "owner": e.owner,
        }

    if not released:
        return {"success": True, "uc_id": uc_id, "released": False, "summary": f"UC {uc_id} no tenía claim."}
    return {"success": True, "uc_id": uc_id, "released": True, "summary": f"UC {uc_id} liberado."}


async def register_native_branch(
    uc_id: str, branch: str, ctx: Context
) -> dict[str, Any]:
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
    """Register the native coordination tools (H2 identity + H3 claims)."""
    # H2 — identity
    mcp_instance.tool(
        description="Register (or update) a developer for the current native project. "
        "Stores only the SHA-256 token hash, never the clear token. Native backend only."
    )(register_native_developer)
    mcp_instance.tool(
        description="Resolve the current session's developer token to {developer_id, display_name}. "
        "Returns UNAUTHENTICATED for an absent/invalid token. Native backend only."
    )(whoami)
    # H3 — claims
    mcp_instance.tool(
        description="Claim a UC for the authenticated developer. ALREADY_CLAIMED (with owner/"
        "claimed_at/branch) if held by another dev. Native backend only."
    )(claim_uc)
    mcp_instance.tool(
        description="Release a UC claim. Only the claim owner may release it (NOT_CLAIM_OWNER "
        "otherwise). Native backend only."
    )(release_uc)
    mcp_instance.tool(
        description="Register a branch <-> UC mapping. Rejects branch-name collisions and "
        "suggests feature/{uc_id}-... naming. Native backend only."
    )(register_native_branch)
