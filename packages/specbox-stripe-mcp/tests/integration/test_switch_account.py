"""Integration test for switch_stripe_account against TWO Stripe test accounts.

Skipped automatically unless BOTH STRIPE_CI_SECRET_KEY_A and
STRIPE_CI_SECRET_KEY_B are set. The two keys must point to different test
accounts (the test verifies cross-account rotation is observable from
inventories, so they cannot be the same account).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specbox_stripe_mcp.lib.alias_store import store_alias
from specbox_stripe_mcp.tools.switch_account import switch_stripe_account

KEY_A = os.environ.get("STRIPE_CI_SECRET_KEY_A", "")
KEY_B = os.environ.get("STRIPE_CI_SECRET_KEY_B", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not (KEY_A and KEY_B),
        reason="Requires STRIPE_CI_SECRET_KEY_A and _B (two different test accounts).",
    ),
    pytest.mark.skipif(
        KEY_A == KEY_B,
        reason="A and B point to the same account; switch test would be vacuous.",
    ),
]

PLATFORM_URL = "https://specbox-ci.example.com/stripe-webhook-switch-test"
PLATFORM_EVENTS = ["customer.subscription.updated", "invoice.paid"]


@pytest.fixture(autouse=True)
def _passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECBOX_ALIAS_PASSPHRASE", "ci-passphrase-1234567890")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A throwaway project rooted at tmp_path with both aliases stored."""
    store_alias(alias_name="a", stripe_api_key=KEY_A, project_path=str(tmp_path))
    store_alias(alias_name="b", stripe_api_key=KEY_B, project_path=str(tmp_path))
    return tmp_path


def test_switch_test_to_test(project: Path) -> None:
    """Round-trip: a → b → a. Both legs converge and idempotency holds."""
    # 1. dry-run a → b
    dry = switch_stripe_account(
        from_alias="a",
        to_alias="b",
        account_mode="standard",
        project_path=str(project),
        platform_url=PLATFORM_URL,
        platform_events=PLATFORM_EVENTS,
        scope_action="keep_old_active",
        dry_run=True,
    )
    assert dry["success"] is True, dry
    assert dry["data"]["dry_run"] is True

    # 2. real a → b
    real_ab = switch_stripe_account(
        from_alias="a",
        to_alias="b",
        account_mode="standard",
        project_path=str(project),
        platform_url=PLATFORM_URL,
        platform_events=PLATFORM_EVENTS,
        scope_action="keep_old_active",
        dry_run=False,
    )
    assert real_ab["success"] is True, real_ab
    assert real_ab["data"]["dry_run"] is False

    # 3. real a → b again (idempotency check)
    real_ab2 = switch_stripe_account(
        from_alias="a",
        to_alias="b",
        account_mode="standard",
        project_path=str(project),
        platform_url=PLATFORM_URL,
        platform_events=PLATFORM_EVENTS,
        scope_action="keep_old_active",
        dry_run=False,
    )
    assert real_ab2["success"] is True
    # Re-run reuses webhooks created on first run.
    webhook_step = next(
        s for s in real_ab2["data"]["executed"] if s["step"] == "webhooks_replicated"
    )
    assert webhook_step["result"]["platform"]["created_or_reused"] == "reused"

    # 4. real b → a
    real_ba = switch_stripe_account(
        from_alias="b",
        to_alias="a",
        account_mode="standard",
        project_path=str(project),
        platform_url=PLATFORM_URL,
        platform_events=PLATFORM_EVENTS,
        scope_action="keep_old_active",
        dry_run=False,
    )
    assert real_ba["success"] is True


def test_dry_run_only_against_real_accounts(project: Path) -> None:
    """Sanity check: dry_run never mutates either account.

    We snapshot inventories before and after a dry-run and assert no diff.
    """
    pre_a = _inventory_snapshot(KEY_A)
    pre_b = _inventory_snapshot(KEY_B)

    out = switch_stripe_account(
        from_alias="a",
        to_alias="b",
        account_mode="standard",
        project_path=str(project),
        platform_url=PLATFORM_URL,
        platform_events=PLATFORM_EVENTS,
        scope_action="full_archive",  # would archive everything if real
        confirm_token="I understand this archives all SpecBox resources in the source account",
        dry_run=True,
    )
    assert out["success"] is True
    assert out["data"]["executed"] == []

    post_a = _inventory_snapshot(KEY_A)
    post_b = _inventory_snapshot(KEY_B)
    assert pre_a == post_a, "dry-run mutated the source account!"
    assert pre_b == post_b, "dry-run mutated the destination account!"


def _inventory_snapshot(key: str) -> tuple[int, int]:
    """Return (webhook_count, product_count) for SpecBox-managed resources."""
    import stripe
    stripe.api_key = key
    webhook_count = 0
    for wh in stripe.WebhookEndpoint.list(limit=100).get("data", []):
        metadata = wh.get("metadata") or {}
        if str(metadata.get("specbox_managed", "")).lower() == "true":
            webhook_count += 1
    product_count = 0
    for p in stripe.Product.list(limit=100, active=True).get("data", []):
        metadata = p.get("metadata") or {}
        if str(metadata.get("specbox_managed", "")).lower() == "true":
            product_count += 1
    return webhook_count, product_count
