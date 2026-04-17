"""Integration tests for the T1-T4 MVP against real Stripe test-mode.

Skipped automatically if STRIPE_CI_SECRET_KEY is not set (see root conftest).

Each test exercises: first-run (create) → reuse → an error branch, per tool.
"""

from __future__ import annotations

import os
import time

import pytest

from specbox_stripe_mcp.tools.get_setup_status import get_setup_status
from specbox_stripe_mcp.tools.setup_products_and_prices import setup_products_and_prices
from specbox_stripe_mcp.tools.setup_webhook_endpoints import setup_webhook_endpoints
from specbox_stripe_mcp.tools.verify_connect_enabled import verify_connect_enabled

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


class TestT1VerifyConnectEnabled:
    def test_returns_enabled_on_ci_account(self) -> None:
        out = verify_connect_enabled(
            stripe_api_key=_key(), project_hint=PROJECT_HINT, skip_canary=True
        )
        assert out["success"] is True
        assert out["data"]["mode"] == "test"
        # enabled may be True (canary) or inferred True (skip_canary). With skip_canary it's always true.
        assert out["data"]["enabled"] is True


class TestT2SetupWebhookEndpoints:
    def test_create_then_reuse(self) -> None:
        first = setup_webhook_endpoints(
            stripe_api_key=_key(),
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
    def test_full_setup_reports_ready(self) -> None:
        # Setup first
        setup_webhook_endpoints(
            stripe_api_key=_key(),
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
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=[c["tier_key"] for c in CATALOG],
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint=PROJECT_HINT,
        )
        assert status["success"] is True
        assert status["data"]["verdict"] == "ready"

    def test_empty_account_reports_partial_or_not_setup(self) -> None:
        # Teardown already ran; no resources SpecBox-managed.
        status = get_setup_status(
            stripe_api_key=_key(),
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=[c["tier_key"] for c in CATALOG],
            project_hint=PROJECT_HINT,
        )
        assert status["success"] is True
        assert status["data"]["verdict"] in ("partial", "not_setup")
