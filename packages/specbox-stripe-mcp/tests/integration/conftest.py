"""Integration-only fixtures: real Stripe test-mode teardown.

Runs before and after each integration test. Requires STRIPE_CI_SECRET_KEY in the
environment; otherwise the tests themselves are skipped by the root conftest.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import stripe


def _specbox_managed(metadata: dict) -> bool:
    return str(metadata.get("specbox_managed", "")).lower() == "true"


def _clean_account() -> None:
    """Archive/delete all SpecBox-managed resources in the test account."""
    # Webhooks → DELETE
    for endpoint in stripe.WebhookEndpoint.list(limit=100).get("data", []):
        if _specbox_managed(endpoint.get("metadata") or {}):
            try:
                stripe.WebhookEndpoint.delete(endpoint["id"])
            except Exception:
                pass
    # Prices → archive first (Stripe refuses DELETE if product still references them)
    for price in stripe.Price.list(limit=100, active=True).get("data", []):
        if _specbox_managed(price.get("metadata") or {}):
            try:
                stripe.Price.modify(price["id"], active=False)
            except Exception:
                pass
    # Products → archive
    for product in stripe.Product.list(limit=100, active=True).get("data", []):
        if _specbox_managed(product.get("metadata") or {}):
            try:
                stripe.Product.modify(product["id"], active=False)
            except Exception:
                pass
    # Probe accounts from T1 canaries (leaked on cleanup failure)
    for account in stripe.Account.list(limit=100).get("data", []):
        metadata = account.get("metadata") or {}
        if str(metadata.get("specbox_probe", "")).lower() == "true":
            try:
                stripe.Account.delete(account["id"])
            except Exception:
                pass


@pytest.fixture
def ci_stripe_key() -> str:
    """Returns the integration Stripe key. Guaranteed present because the
    root conftest skips integration tests when it's missing."""
    key = os.environ["STRIPE_CI_SECRET_KEY"]
    stripe.api_key = key
    return key


@pytest.fixture(autouse=True)
def stripe_teardown(ci_stripe_key: str) -> Iterator[None]:
    """Clean before and after every integration test."""
    stripe.api_key = ci_stripe_key
    _clean_account()
    try:
        yield
    finally:
        _clean_account()
