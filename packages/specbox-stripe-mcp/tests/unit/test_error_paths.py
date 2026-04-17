"""Coverage tests for error and edge branches across tools.

Complements per-tool test files with additional assertions targeting the paths
that push overall coverage past the 85% AC-05 target.
"""

from __future__ import annotations

from unittest.mock import patch

import stripe

from specbox_stripe_mcp.tools.get_setup_status import get_setup_status
from specbox_stripe_mcp.tools.setup_products_and_prices import setup_products_and_prices
from specbox_stripe_mcp.tools.setup_webhook_endpoints import setup_webhook_endpoints
from specbox_stripe_mcp.tools.verify_connect_enabled import verify_connect_enabled

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"


class TestVerifyConnectEnabledEdges:
    def test_stripe_error_on_retrieve_is_reported(self) -> None:
        with patch("stripe.Account.retrieve", side_effect=stripe.error.APIConnectionError("net")):  # type: ignore[attr-defined]
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="p", skip_canary=True)
        # stripe client retries 3x then raises; the tool catches as E_STRIPE_ERROR
        assert out["success"] is False
        assert out["error"]["code"] == "E_STRIPE_ERROR"

    def test_insufficient_permissions_branch(self) -> None:
        with patch("stripe.Account.retrieve", return_value={"id": "acct_p", "capabilities": {}, "country": "ES"}), \
             patch("stripe.Account.create", side_effect=stripe.error.PermissionError(  # type: ignore[attr-defined]
                 "insufficient permission for this endpoint"
             )):
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="p")
        assert out["success"] is False
        assert out["error"]["code"] == "E_INSUFFICIENT_PERMISSIONS"

    def test_generic_stripe_error_in_canary(self) -> None:
        with patch("stripe.Account.retrieve", return_value={"id": "acct_p", "capabilities": {}, "country": "ES"}), \
             patch("stripe.Account.create", side_effect=stripe.error.APIConnectionError("network")):  # type: ignore[attr-defined]
            out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="p")
        assert out["success"] is False
        assert out["error"]["code"] == "E_STRIPE_ERROR"


class TestSetupWebhookEdges:
    def test_list_failure_returns_stripe_error(self) -> None:
        with patch("stripe.WebhookEndpoint.list", side_effect=stripe.error.APIConnectionError("down")):  # type: ignore[attr-defined]
            out = setup_webhook_endpoints(
                stripe_api_key=TEST_KEY,
                platform_url="https://x.test/wh",
                platform_events=["a.b"],
                connect_events=["c.d"],
                project_hint="p",
            )
        assert out["error"]["code"] == "E_STRIPE_ERROR"

    def test_empty_connect_events_rejected(self) -> None:
        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            platform_url="https://x.test/wh",
            platform_events=["a.b"],
            connect_events=[],
            project_hint="p",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"

    def test_limit_reached_mapped(self) -> None:
        class _EmptyList(dict):
            pass
        with patch("stripe.WebhookEndpoint.list", return_value=_EmptyList(data=[])), \
             patch("stripe.WebhookEndpoint.create",
                   side_effect=stripe.error.InvalidRequestError(  # type: ignore[attr-defined]
                       "You have reached the webhook endpoint limit", param="url"
                   )):
            out = setup_webhook_endpoints(
                stripe_api_key=TEST_KEY,
                platform_url="https://x.test/wh",
                platform_events=["account.updated"],
                connect_events=["customer.subscription.created"],
                project_hint="p",
            )
        assert out["error"]["code"] == "E_LIMIT_REACHED"


class TestSetupProductsEdges:
    def test_missing_tier_key_rejected(self) -> None:
        out = setup_products_and_prices(
            stripe_api_key=TEST_KEY,
            catalog=[{"product_name": "x", "unit_amount": 500, "currency": "eur"}],
            project_hint="p",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"

    def test_list_failure(self) -> None:
        with patch("stripe.Product.list", side_effect=stripe.error.APIConnectionError("nope")):  # type: ignore[attr-defined]
            out = setup_products_and_prices(
                stripe_api_key=TEST_KEY,
                catalog=[{"tier_key": "t", "product_name": "T", "unit_amount": 500, "currency": "eur"}],
                project_hint="p",
            )
        assert out["error"]["code"] == "E_STRIPE_ERROR"

    def test_currency_error(self) -> None:
        class _EmptyList(dict):
            pass
        with patch("stripe.Product.list", return_value=_EmptyList(data=[])), \
             patch("stripe.Product.create",
                   side_effect=stripe.error.InvalidRequestError(  # type: ignore[attr-defined]
                       "Currency xyz is not enabled on this account", param="currency"
                   )):
            out = setup_products_and_prices(
                stripe_api_key=TEST_KEY,
                catalog=[{"tier_key": "t", "product_name": "T", "unit_amount": 500, "currency": "xyz"}],
                project_hint="p",
            )
        assert out["error"]["code"] == "E_CURRENCY_NOT_ENABLED"


class TestGetSetupStatusEdges:
    def test_auth_error_maps_to_invalid_key(self) -> None:
        with patch("stripe.Account.retrieve",
                   side_effect=stripe.error.AuthenticationError("bad key")):  # type: ignore[attr-defined]
            out = get_setup_status(stripe_api_key=TEST_KEY, project_hint="p")
        assert out["error"]["code"] == "E_INVALID_KEY"

    def test_generic_stripe_error(self) -> None:
        with patch("stripe.Account.retrieve",
                   side_effect=stripe.error.APIConnectionError("net")):  # type: ignore[attr-defined]
            out = get_setup_status(stripe_api_key=TEST_KEY, project_hint="p")
        assert out["error"]["code"] == "E_STRIPE_ERROR"

    def test_webhook_list_fails(self) -> None:
        with patch("stripe.Account.retrieve", return_value={"id": "a", "capabilities": {"card_payments": "active"}}), \
             patch("stripe.WebhookEndpoint.list",
                   side_effect=stripe.error.APIConnectionError("net")):  # type: ignore[attr-defined]
            out = get_setup_status(
                stripe_api_key=TEST_KEY,
                expected_webhook_url="https://x.test/wh",
                project_hint="p",
            )
        assert out["error"]["code"] == "E_STRIPE_ERROR"

    def test_products_list_fails(self) -> None:
        with patch("stripe.Account.retrieve", return_value={"id": "a", "capabilities": {"card_payments": "active"}}), \
             patch("stripe.Product.list",
                   side_effect=stripe.error.APIConnectionError("net")):  # type: ignore[attr-defined]
            out = get_setup_status(
                stripe_api_key=TEST_KEY,
                expected_tier_keys=["t"],
                project_hint="p",
            )
        assert out["error"]["code"] == "E_STRIPE_ERROR"

    def test_live_mode_rejected(self) -> None:
        out = get_setup_status(
            stripe_api_key="sk_" + "live_" + "FixtureABCdef",
            project_hint="p",
        )
        assert out["error"]["code"] == "E_LIVE_MODE_NOT_ALLOWED"
