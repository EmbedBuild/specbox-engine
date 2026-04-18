"""FastMCP server exposing SpecBox Supabase tools."""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

from .tools.list_edge_secrets import list_edge_secrets
from .tools.set_edge_secret import set_edge_secret
from .tools.unset_edge_secret import unset_edge_secret

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

mcp = FastMCP(
    "specbox-supabase-mcp",
    instructions=(
        "SpecBox MCP for Supabase Management API. Complements the official Supabase MCP "
        "(which does NOT cover Edge Function secrets management, per issue #120). "
        "3 tools: set_edge_secret (bulk POST), list_edge_secrets (GET, read-only), "
        "unset_edge_secret (bulk DELETE with mandatory confirm token). "
        "Secret VALUES never appear in logs or Engram observations — only NAMES."
    ),
)


@mcp.tool()
def set_edge_secret_tool(
    supabase_access_token: str,
    project_ref: str,
    secrets: dict[str, str],
    project_hint: str = "unknown",
    base_url: str | None = None,
) -> dict:
    """Create or overwrite Edge Function secrets (bulk). Idempotent by design.

    Secret values flow to Supabase and are immediately discarded; they never
    appear in logs, responses, or Engram.
    """
    return set_edge_secret(
        supabase_access_token=supabase_access_token,
        project_ref=project_ref,
        secrets=secrets,
        project_hint=project_hint,
        base_url=base_url,
    )


@mcp.tool()
def list_edge_secrets_tool(
    supabase_access_token: str,
    project_ref: str,
    expected_names: list[str] | None = None,
    project_hint: str = "unknown",
    base_url: str | None = None,
) -> dict:
    """Read-only: list secret names currently configured (values never returned).

    If ``expected_names`` is passed, the response includes ``missing_names`` and
    ``extra_names`` for quick diffing from the caller.
    """
    return list_edge_secrets(
        supabase_access_token=supabase_access_token,
        project_ref=project_ref,
        expected_names=expected_names,
        project_hint=project_hint,
        base_url=base_url,
    )


@mcp.tool()
def unset_edge_secret_tool(
    supabase_access_token: str,
    project_ref: str,
    names: list[str],
    confirm_token: str,
    project_hint: str = "unknown",
    base_url: str | None = None,
) -> dict:
    """Delete secrets (bulk). Requires literal confirm_token.

    Writes a pre-action Engram observation with the exact list of names about
    to be deleted (audit trail).
    """
    return unset_edge_secret(
        supabase_access_token=supabase_access_token,
        project_ref=project_ref,
        names=names,
        confirm_token=confirm_token,
        project_hint=project_hint,
        base_url=base_url,
    )


def main() -> None:
    """Entrypoint for the ``specbox-supabase-mcp`` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
