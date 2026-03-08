"""Auth module - Per-session Trello credential management via FastMCP Context.

Each MCP client provides their own Trello API Key + Token by calling
set_auth_token() as the first operation. Credentials are stored in the
FastMCP session state and isolated between clients.

No global singleton. No env vars for credentials.
"""

from __future__ import annotations

from fastmcp import Context

from .trello_client import TrelloClient

AUTH_STATE_KEY = "trello_credentials"


async def get_session_client(ctx: Context) -> TrelloClient:
    """Create a TrelloClient from session-stored credentials.

    Raises a clear error if set_auth_token has not been called yet.
    """
    creds = await ctx.get_state(AUTH_STATE_KEY)
    if not creds:
        raise RuntimeError(
            "Trello credentials not configured for this session. "
            "Call set_auth_token(api_key, token) first."
        )
    return TrelloClient(api_key=creds["api_key"], token=creds["token"])


async def store_session_credentials(ctx: Context, api_key: str, token: str) -> None:
    """Store credentials in the session state."""
    await ctx.set_state(AUTH_STATE_KEY, {"api_key": api_key, "token": token})


async def clear_session_credentials(ctx: Context) -> None:
    """Clear credentials from the session state."""
    await ctx.delete_state(AUTH_STATE_KEY)
