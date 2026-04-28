"""Integration tests for the v0.2 MVP against real Stripe test-mode.

Skipped automatically if STRIPE_CI_SECRET_KEY is not set (see root conftest).

Coverage:
- TestT1VerifyAccountSetup: smoke checks for both modes.
- TestT2SetupWebhookEndpoints: create→reuse for connect mode (legacy).
- TestT3SetupProductsAndPrices: create→reuse + duplicate tier rejection.
- TestT4GetSetupStatus: full setup verdict + empty account verdict.
- TestUC004FlowStandard: full standard flow → verdict='ready' (UC-004 AC-01).
- TestUC004FlowConnect: full connect flow → verdict='ready' (UC-004 AC-02).
- TestUC004IdempotencyStandard: standard flow twice → all 'reused' (AC-03).
- TestUC004ModeIsolation: standard and connect coexist in the same account
  without interfering with each other (AC-04).

The conftest stripe_teardown autouse fixture wipes ALL SpecBox-managed
resources before and after each test, regardless of account_mode metadata
(it filters only by specbox_managed='true'), satisfying AC-05.
"""

from __future__ import annotations

import os
import time

import pytest

from specbox_stripe_mcp.tools.get_setup_status import get_setup_status
from specbox_stripe_mcp.tools.setup_products_and_prices import setup_products_and_prices
from specbox_stripe_mcp.tools.setup_webhook_endpoints import setup_webhook_endpoints
from specbox_stripe_mcp.tools.verify_account_setup import verify_account_setup

pytestmark = pytest.mark.integration

PROJECT_HINT = f"ci-{int(time.time())}"
WEBHOOK_URL = "https://specbox-ci.example.com/stripe-webhook"
PLATFORM_EVENTS = ["account.updated", "capability.updated"]
CONNECT_EVENTS = ["customer.subscription.created", "invoice.paid"]
CATALOG = [
    {"tier_key": "ci_basic", "product_name": "CI Basic", "unit_amount": 500, "currency": "eur"},
    {"tier_key": "ci_pro",   "product_name": "CI Pro",   "unit_amount": 900, "currency": "eur"},
]


def _key() -> str:
    return os.environ["STRIPE_CI_SECRET_KEY"]


# --- Smoke tests per tool (per-mode where applicable) ------------------------


class TestT1VerifyAccountSetup:
    def test_standard_mode_returns_enabled(self) -> None:
        out = verify_account_setup(
            stripe_api_key=_key(),
            account_mode="standard",
            project_hint=PROJECT_HINT,
        )
        assert out["success"] is True
        assert out["data"]["mode"] == "test"
        assert out["data"]["enabled"] is True
        assert out["data"]["account_mode"] == "standard"

    def test_connect_mode_returns_enabled_with_canary_skipped(self) -> None:
        out = verify_account_setup(
            stripe_api_key=_key(),
            account_mode="connect",
            project_hint=PROJECT_HINT,
            skip_canary=True,
        )
        assert out["success"] is True
        assert out["data"]["mode"] == "test"
        assert out["data"]["enabled"] is True


class TestT2SetupWebhookEndpoints:
    def test_connect_create_then_reuse(self) -> None:
        first = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="connect",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert first["success"] is True
        assert first["data"]["platform"]["created_or_reused"] == "created"
        assert first["data"]["connect"]["created_or_reused"] == "created"
        first_ids = (first["data"]["platform"]["id"], first["data"]["connect"]["id"])

        second = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="connect",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert second["success"] is True
        assert second["data"]["platform"]["created_or_reused"] == "reused"
        assert second["data"]["connect"]["created_or_reused"] == "reused"
        assert (second["data"]["platform"]["id"], second["data"]["connect"]["id"]) == first_ids

    def test_invalid_url_error(self) -> None:
        out = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="connect",
            platform_url="http://insecure.example.com/wh",
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_URL"


class TestT3SetupProductsAndPrices:
    def test_create_then_reuse(self) -> None:
        first = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )
        assert first["success"] is True
        assert {p["tier_key"] for p in first["data"]["products"]} == {"ci_basic", "ci_pro"}
        assert all(p["created_or_reused"] == "created" for p in first["data"]["products"])

        second = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )
        assert second["success"] is True
        assert all(
            p["created_or_reused"] == "reused" for p in second["data"]["products"]
        )
        assert all(
            p["created_or_reused"] == "reused" for p in second["data"]["prices"]
        )

    def test_duplicate_tier_key_rejected(self) -> None:
        out = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=[CATALOG[0], CATALOG[0]],
            project_hint=PROJECT_HINT,
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_DUPLICATE_TIER_KEY"


class TestT4GetSetupStatus:
    def test_connect_full_setup_reports_ready(self) -> None:
        setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="connect",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )

        status = get_setup_status(
            stripe_api_key=_key(),
            account_mode="connect",
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=[c["tier_key"] for c in CATALOG],
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert status["success"] is True
        assert status["data"]["verdict"] == "ready"
        assert status["data"]["account_mode"] == "connect"

    def test_empty_account_reports_not_setup_or_partial(self) -> None:
        status = get_setup_status(
            stripe_api_key=_key(),
            account_mode="connect",
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=[c["tier_key"] for c in CATALOG],
            project_hint=PROJECT_HINT,
        )
        assert status["success"] is True
        assert status["data"]["verdict"] in ("partial", "not_setup")


# --- UC-004: end-to-end flows per mode ---------------------------------------


class TestUC004FlowStandard:
    """AC-01: full standard flow ends in verdict='ready'."""

    def test_standard_full_flow_reaches_ready(self) -> None:
        verify_out = verify_account_setup(
            stripe_api_key=_key(),
            account_mode="standard",
            project_hint=PROJECT_HINT,
        )
        assert verify_out["success"] is True
        assert verify_out["data"]["enabled"] is True

        wh_out = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="standard",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert wh_out["success"] is True
        assert wh_out["data"]["platform"]["connect"] is False
        assert "connect" not in wh_out["data"]

        prod_out = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )
        assert prod_out["success"] is True

        status = get_setup_status(
            stripe_api_key=_key(),
            account_mode="standard",
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=[c["tier_key"] for c in CATALOG],
            expected_platform_events=PLATFORM_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert status["success"] is True
        assert status["data"]["verdict"] == "ready"
        assert status["data"]["account_mode"] == "standard"
        # Connect-specific keys must not appear in standard mode.
        assert "connect_webhook_endpoint" not in status["data"]["checks"]
        assert "connect_enabled" not in status["data"]["checks"]


class TestUC004FlowConnect:
    """AC-02: full connect flow ends in verdict='ready'."""

    def test_connect_full_flow_reaches_ready(self) -> None:
        verify_out = verify_account_setup(
            stripe_api_key=_key(),
            account_mode="connect",
            project_hint=PROJECT_HINT,
            skip_canary=True,  # avoid creating Express probe accounts on every CI run
        )
        assert verify_out["success"] is True

        wh_out = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="connect",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert wh_out["success"] is True
        assert "platform" in wh_out["data"]
        assert "connect" in wh_out["data"]

        prod_out = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )
        assert prod_out["success"] is True

        status = get_setup_status(
            stripe_api_key=_key(),
            account_mode="connect",
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=[c["tier_key"] for c in CATALOG],
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert status["success"] is True
        assert status["data"]["verdict"] == "ready"


class TestUC004IdempotencyStandard:
    """AC-03: standard flow twice → all resources 'reused' on the second pass."""

    def test_standard_flow_idempotent(self) -> None:
        # First pass — creates everything.
        first_wh = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="standard",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint=PROJECT_HINT,
        )
        first_pp = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )
        assert first_wh["data"]["platform"]["created_or_reused"] == "created"
        assert all(p["created_or_reused"] == "created" for p in first_pp["data"]["products"])

        # Second pass — everything reused.
        second_wh = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="standard",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint=PROJECT_HINT,
        )
        second_pp = setup_products_and_prices(
            stripe_api_key=_key(),
            catalog=CATALOG,
            project_hint=PROJECT_HINT,
        )
        assert second_wh["data"]["platform"]["created_or_reused"] == "reused"
        assert second_wh["data"]["platform"]["id"] == first_wh["data"]["platform"]["id"]
        assert all(p["created_or_reused"] == "reused" for p in second_pp["data"]["products"])
        assert all(p["created_or_reused"] == "reused" for p in second_pp["data"]["prices"])


class TestUC004ModeIsolation:
    """AC-04: standard and connect resources coexist without interference."""

    def test_standard_and_connect_resources_coexist(self) -> None:
        # Standard endpoint at WEBHOOK_URL (connect=False).
        std = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="standard",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert std["success"] is True
        std_id = std["data"]["platform"]["id"]

        # Now register a connect-mode setup with a *different* URL so the
        # connect-side endpoint has somewhere distinct to live. The platform
        # endpoint at WEBHOOK_URL should stay the standard one (cross-mode
        # isolation prevents reusing it).
        cn_url = WEBHOOK_URL.replace("stripe-webhook", "stripe-webhook-connect")
        cn = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="connect",
            platform_url=cn_url,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert cn["success"] is True
        cn_platform_id = cn["data"]["platform"]["id"]
        cn_connect_id = cn["data"]["connect"]["id"]

        # The three endpoints must be distinct (no cross-mode reuse).
        assert std_id != cn_platform_id
        assert std_id != cn_connect_id
        assert cn_platform_id != cn_connect_id

        # Re-run the standard call — it should reuse the standard endpoint, not
        # the connect-mode platform endpoint that lives at a different URL.
        std_again = setup_webhook_endpoints(
            stripe_api_key=_key(),
            account_mode="standard",
            platform_url=WEBHOOK_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert std_again["data"]["platform"]["created_or_reused"] == "reused"
        assert std_again["data"]["platform"]["id"] == std_id

        # And the connect status reports ready for its own URL.
        status_cn = get_setup_status(
            stripe_api_key=_key(),
            account_mode="connect",
            expected_webhook_url=cn_url,
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert status_cn["data"]["checks"]["platform_webhook_endpoint"]["id"] == cn_platform_id
        assert status_cn["data"]["checks"]["connect_webhook_endpoint"]["id"] == cn_connect_id
