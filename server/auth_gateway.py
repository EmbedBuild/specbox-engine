"""Auth module - Per-session credential management via FastMCP Context.

Supports multiple backends (Trello, Plane) and service proxies (Stitch).
Each MCP client provides credentials by calling set_auth_token() as the
first operation. Credentials are stored in the FastMCP session state and
isolated between clients.

Backend selection:
- Trello: api_key + token → TrelloBackend
- Plane: base_url + api_key + workspace_slug → PlaneBackend

Service proxies:
- Stitch: api_key per project → StitchClient
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp import Context

if TYPE_CHECKING:
    from .spec_backend import SpecBackend
    from .stitch_client import StitchClient

# Legacy key kept for backward compatibility
AUTH_STATE_KEY = "trello_credentials"
# New unified key
BACKEND_STATE_KEY = "spec_backend_config"
# Stitch credentials keyed per project: stitch_config_{project}
STITCH_STATE_PREFIX = "stitch_config_"


async def get_session_backend(ctx: Context) -> "SpecBackend":
    """Create a SpecBackend from session-stored credentials.

    Checks for new-style backend config first, falls back to legacy Trello creds.
    Raises a clear error if no credentials are configured.
    """
    # Try new unified config first
    config = await ctx.get_state(BACKEND_STATE_KEY)
    if config:
        backend_type = config.get("backend_type", "trello")
        if backend_type == "plane":
            from .backends.plane_backend import PlaneBackend

            return PlaneBackend(
                base_url=config["base_url"],
                api_key=config["api_key"],
                workspace_slug=config["workspace_slug"],
            )
        else:
            from .backends.trello_backend import TrelloBackend

            return TrelloBackend(
                api_key=config["api_key"], token=config["token"]
            )

    # Fallback to legacy Trello credentials
    creds = await ctx.get_state(AUTH_STATE_KEY)
    if creds:
        from .backends.trello_backend import TrelloBackend

        return TrelloBackend(api_key=creds["api_key"], token=creds["token"])

    raise RuntimeError(
        "Backend credentials not configured for this session. "
        "Call set_auth_token(api_key, token) for Trello or "
        "set_auth_token(api_key, base_url, workspace_slug) for Plane first."
    )


# --- Legacy Trello-only functions (kept for backward compat) ---


async def get_session_client(ctx: Context):
    """Create a TrelloClient from session-stored credentials.

    DEPRECATED: Use get_session_backend() instead.
    Kept for backward compatibility during migration.
    """
    creds = await ctx.get_state(AUTH_STATE_KEY)
    if not creds:
        raise RuntimeError(
            "Trello credentials not configured for this session. "
            "Call set_auth_token(api_key, token) first."
        )
    from .trello_client import TrelloClient

    return TrelloClient(api_key=creds["api_key"], token=creds["token"])


async def store_session_credentials(ctx: Context, api_key: str, token: str) -> None:
    """Store Trello credentials in the session state."""
    await ctx.set_state(AUTH_STATE_KEY, {"api_key": api_key, "token": token})
    # Also store as unified config for new code
    await ctx.set_state(
        BACKEND_STATE_KEY,
        {"backend_type": "trello", "api_key": api_key, "token": token},
    )


async def store_plane_credentials(
    ctx: Context, api_key: str, base_url: str, workspace_slug: str
) -> None:
    """Store Plane credentials in the session state."""
    await ctx.set_state(
        BACKEND_STATE_KEY,
        {
            "backend_type": "plane",
            "api_key": api_key,
            "base_url": base_url,
            "workspace_slug": workspace_slug,
        },
    )


async def clear_session_credentials(ctx: Context) -> None:
    """Clear credentials from the session state."""
    await ctx.delete_state(AUTH_STATE_KEY)
    await ctx.delete_state(BACKEND_STATE_KEY)


# --- Stitch proxy credentials ---


async def store_stitch_credentials(
    ctx: Context, project: str, api_key: str
) -> None:
    """Store Stitch API Key for a project in the session state."""
    state_key = f"{STITCH_STATE_PREFIX}{project}"
    await ctx.set_state(state_key, {"api_key": api_key, "project": project})


async def get_stitch_client(ctx: Context, project: str) -> "StitchClient":
    """Create a StitchClient from session-stored Stitch credentials.

    Raises RuntimeError if no Stitch key is configured for the project.
    """
    state_key = f"{STITCH_STATE_PREFIX}{project}"
    config = await ctx.get_state(state_key)
    if not config:
        raise RuntimeError(
            f"Stitch API Key not configured for project '{project}'. "
            "Call stitch_set_api_key(project, api_key) first."
        )
    from .stitch_client import StitchClient

    return StitchClient(api_key=config["api_key"])
