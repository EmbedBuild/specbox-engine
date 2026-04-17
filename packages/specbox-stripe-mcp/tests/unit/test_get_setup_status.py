"""Unit tests for T4 get_setup_status.

Covers AC-01..AC-06 of UC-4.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from specbox_stripe_mcp.tools.get_setup_status import get_setup_status

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"
WEBHOOK_URL = "https://proj.supabase.co/functions/v1/stripe-webhook"
TIERS = ["bronce", "plata", "oro"]
PLATFORM_EVENTS = ["account.updated", "capability.updated"]
CONNECT_EVENTS = ["customer.subscription.created", "invoice.paid"]


class _Listing(dict):
    pass


def _account(*, with_connect: bool = True) -> dict[str, Any]:
    if with_connect:
        return {
            "id": "acct_platform",
            "country": "ES",
            "default_currency": "eur",
            "capabilities": {"card_payments": "active", "transfers": "active"},
            "settings": {"dashboard": {"display_name": "Proj"}, "platform_payments": {}},
            "charges_enabled": True,
        }
    return {
        "id": "acct_platform",
        "country": "ES",
        "default_currency": "eur",
        "capabilities": {},
        "settings": {},
        "charges_enabled": False,
    }


def _webhook(
    *,
    wid: str,
    url: str = WEBHOOK_URL,
    connect: bool,
    events: list[str],
    managed: bool = True,
) -> dict[str, Any]:
    return {
        "id": wid,
        "url": url,
        "connect": connect,
        "enabled_events": events,
        "metadata": {"specbox_managed": "true"} if managed else {},
        "status": "enabled",
    }


def _product(pid: str, tier: str, *, managed: bool = True) -> dict[str, Any]:
    md = {"tier_key": tier}
    if managed:
        md["specbox_managed"] = "true"
    return {"id": pid, "name": f"Sponsor {tier}", "metadata": md, "active": True}


def _price(prid: str, product: str, tier: str) -> dict[str, Any]:
    return {
        "id": prid,
        "product": product,
        "unit_amount": 500,
        "currency": "eur",
        "recurring": {"interval": "month"},
        "metadata": {"specbox_managed": "true", "tier_key": tier},
        "active": True,
    }


@pytest.fixture
def patch_stripe():  # type: ignore[no-untyped-def]
    with patch("stripe.Account.retrieve") as m_acc, patch(
        "stripe.WebhookEndpoint.list"
    ) as m_wh, patch("stripe.Product.list") as m_plist, patch(
        "stripe.Price.list"
    ) as m_prlist, patch("stripe.Account.create") as m_acreate, patch(
        "stripe.WebhookEndpoint.create"
    ) as m_wcreate, patch("stripe.Product.create") as m_pcreate, patch(
        "stripe.Price.create"
    ) as m_prcreate, patch("stripe.WebhookEndpoint.modify") as m_wmodify, patch(
        "stripe.Product.modify"
    ) as m_pmodify, patch("stripe.Price.modify") as m_prmodify:
        yield {
            "acc": m_acc,
            "wh": m_wh,
            "plist": m_plist,
            "prlist": m_prlist,
            # Mutating mocks below must remain untouched for AC-05.
            "acreate": m_acreate,
            "wcreate": m_wcreate,
            "pcreate": m_pcreate,
            "prcreate": m_prcreate,
            "wmodify": m_wmodify,
            "pmodify": m_pmodify,
            "prmodify": m_prmodify,
        }


class TestAcceptance:
    def test_ready_when_everything_aligned(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-01: Connect + 2 webhooks + 3 products + 3 prices → verdict=ready."""
        m = patch_stripe
        m["acc"].return_value = _account(with_connect=True)
        m["wh"].return_value = _Listing(data=[
            _webhook(wid="we_pf", connect=False, events=PLATFORM_EVENTS),
            _webhook(wid="we_cn", connect=True, events=CONNECT_EVENTS),
        ])
        m["plist"].return_value = _Listing(
            data=[_product(f"prod_{t}", t) for t in TIERS]
        )
        m["prlist"].side_effect = lambda product, **_: _Listing(
            data=[_price(f"price_{product}", product, product.replace("prod_", ""))]
        )

        out = get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=TIERS,
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["verdict"] == "ready"
        assert out["data"]["checks"]["connect_enabled"] is True
        assert out["data"]["checks"]["platform_webhook_endpoint"]["present"] is True
        assert out["data"]["checks"]["connect_webhook_endpoint"]["present"] is True
        assert sorted(out["data"]["checks"]["products_found"]) == sorted(TIERS)
        assert not out["data"]["checks"]["products_missing"]
        assert not out["data"]["checks"]["prices_missing"]
        assert "pass" in out["data"]["summary"].lower()

    def test_partial_when_connect_webhook_missing(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02: platform webhook present but connect missing → partial + remediation."""
        m = patch_stripe
        m["acc"].return_value = _account(with_connect=True)
        m["wh"].return_value = _Listing(data=[
            _webhook(wid="we_pf", connect=False, events=PLATFORM_EVENTS),
        ])
        m["plist"].return_value = _Listing(data=[])

        out = get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_webhook_url=WEBHOOK_URL,
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["data"]["verdict"] == "partial"
        assert out["data"]["checks"]["platform_webhook_endpoint"]["present"] is True
        assert out["data"]["checks"]["connect_webhook_endpoint"]["present"] is False
        remediation = " ".join(out["data"]["remediation_steps"])
        assert "connect webhook" in remediation.lower()

    def test_partial_when_tier_missing(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03: 2 tiers present, 1 missing → partial + products_missing populated."""
        m = patch_stripe
        m["acc"].return_value = _account(with_connect=True)
        m["wh"].return_value = _Listing(data=[])
        m["plist"].return_value = _Listing(
            data=[_product("prod_bronce", "bronce"), _product("prod_plata", "plata")]
        )
        m["prlist"].side_effect = lambda product, **_: _Listing(
            data=[_price(f"price_{product}", product, product.replace("prod_", ""))]
        )

        out = get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_tier_keys=TIERS,
            project_hint="motofan",
        )

        assert out["data"]["verdict"] == "partial"
        assert out["data"]["checks"]["products_missing"] == ["oro"]
        assert "oro" not in out["data"]["checks"]["prices_found"]

    def test_not_setup_when_connect_disabled(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-04: Connect disabled → verdict=not_setup + dashboard URL in remediation."""
        m = patch_stripe
        m["acc"].return_value = _account(with_connect=False)
        m["wh"].return_value = _Listing(data=[])
        m["plist"].return_value = _Listing(data=[])

        out = get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_tier_keys=TIERS,
            project_hint="motofan",
        )

        assert out["data"]["verdict"] == "not_setup"
        assert out["data"]["checks"]["connect_enabled"] is False
        remediation = " ".join(out["data"]["remediation_steps"])
        assert "dashboard.stripe.com" in remediation

    def test_tool_is_read_only(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05: no mutating Stripe call is ever made, regardless of inputs."""
        m = patch_stripe
        m["acc"].return_value = _account(with_connect=True)
        m["wh"].return_value = _Listing(data=[
            _webhook(wid="we_pf", connect=False, events=PLATFORM_EVENTS),
            _webhook(wid="we_cn", connect=True, events=CONNECT_EVENTS),
        ])
        m["plist"].return_value = _Listing(
            data=[_product(f"prod_{t}", t) for t in TIERS]
        )
        m["prlist"].side_effect = lambda product, **_: _Listing(
            data=[_price(f"price_{product}", product, product.replace("prod_", ""))]
        )

        get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=TIERS,
            project_hint="motofan",
        )
        # Call a second time — same result, still no mutations.
        get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_webhook_url=WEBHOOK_URL,
            expected_tier_keys=TIERS,
            project_hint="motofan",
        )

        for key in ("acreate", "wcreate", "pcreate", "prcreate",
                    "wmodify", "pmodify", "prmodify"):
            assert m[key].call_count == 0, f"mutating call {key} was invoked"

    def test_events_ok_false_when_expected_events_missing(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-06: webhook present but missing expected events → events_ok=false + missing_events."""
        m = patch_stripe
        m["acc"].return_value = _account(with_connect=True)
        m["wh"].return_value = _Listing(data=[
            _webhook(wid="we_pf", connect=False, events=["account.updated"]),
            _webhook(wid="we_cn", connect=True, events=CONNECT_EVENTS),
        ])
        m["plist"].return_value = _Listing(data=[])

        out = get_setup_status(
            stripe_api_key=TEST_KEY,
            expected_webhook_url=WEBHOOK_URL,
            expected_platform_events=PLATFORM_EVENTS,
            expected_connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        pf = out["data"]["checks"]["platform_webhook_endpoint"]
        assert pf["present"] is True
        assert pf["events_ok"] is False
        assert "capability.updated" in pf["missing_events"]
