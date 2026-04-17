"""AC-04 enforcement: every tool exposed by the MCP is documented in README.md.

If a new tool is added without adding it to the README, this test fails at
merge time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specbox_stripe_mcp import server as _server  # noqa: F401 — triggers tool registration

_README = Path(__file__).resolve().parents[2] / "README.md"


def _known_mcp_tool_names() -> list[str]:
    """Names of the tool-backing functions (not the MCP wrappers suffixed _tool).

    The README catalogs the functions by their Stripe-domain name, not the
    ``_tool`` suffix. We harvest the names from the tools subpackage.
    """
    from specbox_stripe_mcp.tools import (
        get_setup_status as mod_status,
    )
    from specbox_stripe_mcp.tools import (
        setup_products_and_prices as mod_catalog,
    )
    from specbox_stripe_mcp.tools import (
        setup_webhook_endpoints as mod_webhooks,
    )
    from specbox_stripe_mcp.tools import (
        verify_connect_enabled as mod_verify,
    )
    return [
        mod_verify.TOOL_NAME,
        mod_webhooks.TOOL_NAME,
        mod_catalog.TOOL_NAME,
        mod_status.TOOL_NAME,
    ]


@pytest.fixture(scope="module")
def readme_text() -> str:
    return _README.read_text(encoding="utf-8")


@pytest.mark.parametrize("tool_name", _known_mcp_tool_names())
def test_tool_appears_in_readme_catalog(readme_text: str, tool_name: str) -> None:
    assert tool_name in readme_text, (
        f"{tool_name} is missing from README.md. "
        "Add it to the Tool Catalog section with its input/output schema."
    )


def test_readme_has_required_sections(readme_text: str) -> None:
    """AC-01 enforcement: README covers description + quickstart + catalog + security + PRD link."""
    for marker in [
        "## What it does",
        "## Tool catalog",
        "## Quickstart",
        "## End-to-end example",
        "## Security",
        "doc/prd/specbox_stripe_mcp_prd.md",
    ]:
        assert marker in readme_text, f"README is missing section/marker: {marker!r}"
