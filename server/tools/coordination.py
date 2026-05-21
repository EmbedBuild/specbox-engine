"""MCP tools for the NativeBackend coordination layer — identity (H2).

These tools live outside the spec-driven tool set on purpose: they operate on
the ``developers`` / ``project_members`` tables (server.coordination.identity),
not on the spec hierarchy. They are only meaningful for a native session.

Tools (H2)
----------
- ``register_native_developer`` — admin bootstrap: create/update a developer and
  associate it with the current native project. Stores only the token hash.
- ``whoami`` — resolve the session's developer token to {developer_id,
  display_name}; UNAUTHENTICATED on an invalid/absent token [AC-15].

The H3 claim tools (claim_uc / release_uc) are registered from their own module.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_native_session
from ..coordination.identity import (
    UnauthenticatedError,
    add_project_member,
    register_developer,
    resolve_developer,
)
from ..db.pool import get_pool

logger = structlog.get_logger(__name__)


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


def register_coordination_tools(mcp_instance) -> None:
    """Register the H2 native coordination tools on the FastMCP instance."""
    mcp_instance.tool(
        description="Register (or update) a developer for the current native project. "
        "Stores only the SHA-256 token hash, never the clear token. Native backend only."
    )(register_native_developer)
    mcp_instance.tool(
        description="Resolve the current session's developer token to {developer_id, display_name}. "
        "Returns UNAUTHENTICATED for an absent/invalid token. Native backend only."
    )(whoami)
