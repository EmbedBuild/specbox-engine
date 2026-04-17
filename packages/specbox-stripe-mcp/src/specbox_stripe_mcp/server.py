"""FastMCP server exposing SpecBox Stripe tools.

Mirrors the layout of the engine's own server/server.py so consumers have a
consistent experience across SpecBox MCPs.
"""

from __future__ import annotations

import logging
import os

from fastmcp import FastMCP

from .tools.get_setup_status import get_setup_status
from .tools.setup_products_and_prices import setup_products_and_prices
from .tools.setup_webhook_endpoints import setup_webhook_endpoints
from .tools.verify_connect_enabled import verify_connect_enabled

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

mcp = FastMCP(
    "specbox-stripe-mcp",
    instructions=(
        "SpecBox MCP for Stripe setup-as-code. Complements the official Stripe MCP: "
        "this one builds the track (Connect gate, webhooks, products/prices, health check), "
        "while the official Stripe MCP runs business operations on it. "
        "Test-mode by default; live-mode requires explicit opt-in with a confirm token."
    ),
)


@mcp.tool()
def verify_connect_enabled_tool(
    stripe_api_key: str,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
    skip_canary: bool = False,
) -> dict:
    """Check whether Stripe Connect is enabled for the platform account behind this key.

    Use this as the first step of any SpecBox payments skill. If enabled=false, the skill
    should abort with the remediation URL (dashboard activation is manual and irreducible).
    """
    return verify_connect_enabled(
        stripe_api_key=stripe_api_key,
        project_hint=project_hint,
        allow_live_mode=allow_live_mode,
        live_mode_confirm_token=live_mode_confirm_token,
        skip_canary=skip_canary,
    )


@mcp.tool()
def setup_webhook_endpoints_tool(
    stripe_api_key: str,
    platform_url: str,
    platform_events: list[str],
    connect_events: list[str],
    connect_url: str | None = None,
    api_version: str | None = None,
    project_hint: str = "unknown",
    description_prefix: str | None = None,
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict:
    """Create or idempotently reuse the 2 SpecBox-managed webhook endpoints.

    Returns ``data.platform`` and ``data.connect``, each with ``id``, ``secret``,
    ``events``, and ``created_or_reused`` in {"created","reused","updated"}.
    Secrets for reused endpoints are fetched via Stripe's ``expand=['secret']``.
    """
    return setup_webhook_endpoints(
        stripe_api_key=stripe_api_key,
        platform_url=platform_url,
        platform_events=platform_events,
        connect_events=connect_events,
        connect_url=connect_url,
        api_version=api_version,
        project_hint=project_hint,
        description_prefix=description_prefix,
        allow_live_mode=allow_live_mode,
        live_mode_confirm_token=live_mode_confirm_token,
    )


@mcp.tool()
def setup_products_and_prices_tool(
    stripe_api_key: str,
    catalog: list[dict],
    archive_unmanaged_tiers: bool = False,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict:
    """Reconcile the Stripe product+price catalog to match the declared tiers.

    Each catalog item requires ``tier_key``, ``product_name``, ``unit_amount``
    (cents), and ``currency``. Optional: ``description``, ``interval``
    ("month"/"year"; default "month"), ``trial_period_days``, ``extra_metadata``.

    Returns ``data.products``, ``data.prices``, ``data.archived``, and
    ``data.tier_mapping``.
    """
    return setup_products_and_prices(
        stripe_api_key=stripe_api_key,
        catalog=catalog,
        archive_unmanaged_tiers=archive_unmanaged_tiers,
        project_hint=project_hint,
        allow_live_mode=allow_live_mode,
        live_mode_confirm_token=live_mode_confirm_token,
    )


@mcp.tool()
def get_setup_status_tool(
    stripe_api_key: str,
    expected_webhook_url: str | None = None,
    expected_tier_keys: list[str] | None = None,
    expected_currency: str = "eur",
    expected_platform_events: list[str] | None = None,
    expected_connect_events: list[str] | None = None,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict:
    """Read-only health check for the Stripe setup of this project.

    Returns ``data.verdict`` in {"ready", "partial", "not_setup"} plus per-check
    details and ``remediation_steps`` when not ready. Never mutates Stripe.
    """
    return get_setup_status(
        stripe_api_key=stripe_api_key,
        expected_webhook_url=expected_webhook_url,
        expected_tier_keys=expected_tier_keys,
        expected_currency=expected_currency,
        expected_platform_events=expected_platform_events,
        expected_connect_events=expected_connect_events,
        project_hint=project_hint,
        allow_live_mode=allow_live_mode,
        live_mode_confirm_token=live_mode_confirm_token,
    )


def main() -> None:
    """Entrypoint used by the `specbox-stripe-mcp` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
