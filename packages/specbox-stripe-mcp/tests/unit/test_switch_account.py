"""Unit tests for switch_stripe_account (UC-018..UC-023).

We mock Stripe SDK calls + httpx for Supabase. The alias_store uses the
passphrase backend via SPECBOX_ALIAS_PASSPHRASE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from specbox_stripe_mcp.lib.alias_store import store_alias
from specbox_stripe_mcp.tools.switch_account import (
    FULL_ARCHIVE_TOKEN,
    switch_stripe_account,
)

KEY_FROM = "sk_" + "test_" + "FromAccountFixtureNotReal"
KEY_TO = "sk_" + "test_" + "ToAccountFixtureNotReal"
PLATFORM_URL = "https://app.example.com/functions/v1/stripe-webhook"


@pytest.fixture(autouse=True)
def _passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPECBOX_ALIAS_PASSPHRASE", "test-passphrase-1234567890")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Initialize a project with two aliases."""
    store_alias(alias_name="from", stripe_api_key=KEY_FROM, project_path=str(tmp_path))
    store_alias(alias_name="to", stripe_api_key=KEY_TO, project_path=str(tmp_path))
    return tmp_path


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------


class TestArgValidation:
    def test_invalid_account_mode(self, project: Path) -> None:
        out = switch_stripe_account(
            from_alias="from",
            to_alias="to",
            account_mode="hybrid",  # type: ignore[arg-type]
            project_path=str(project),
            platform_url=PLATFORM_URL,
            platform_events=["customer.subscription.updated"],
        )
        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"

    def test_invalid_scope_action(self, project: Path) -> None:
        out = switch_stripe_account(
            from_alias="from",
            to_alias="to",
            account_mode="standard",
            project_path=str(project),
            platform_url=PLATFORM_URL,
            platform_events=["customer.subscription.updated"],
            scope_action="nuke_everything",  # type: ignore[arg-type]
        )
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"

    def test_full_archive_requires_confirm_token(self, project: Path) -> None:
        out = switch_stripe_account(
            from_alias="from",
            to_alias="to",
            account_mode="standard",
            project_path=str(project),
            platform_url=PLATFORM_URL,
            platform_events=["customer.subscription.updated"],
            scope_action="full_archive",
            confirm_token="oops wrong token",
        )
        assert out["error"]["code"] == "E_CONFIRMATION_REQUIRED"

    def test_full_archive_accepts_correct_token(self, project: Path) -> None:
        # dry_run=True so we don't actually mutate; we only verify the
        # validation pipeline lets it through.
        with _StubStripe():
            out = switch_stripe_account(
                from_alias="from",
                to_alias="to",
                account_mode="standard",
                project_path=str(project),
                platform_url=PLATFORM_URL,
                platform_events=["customer.subscription.updated"],
                scope_action="full_archive",
                confirm_token=FULL_ARCHIVE_TOKEN,
                dry_run=True,
            )
        assert out["success"] is True
        assert out["data"]["dry_run"] is True

    def test_same_alias_rejected(self, project: Path) -> None:
        out = switch_stripe_account(
            from_alias="from",
            to_alias="from",
            account_mode="standard",
            project_path=str(project),
            platform_url=PLATFORM_URL,
            platform_events=["x"],
        )
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"

    def test_connect_mode_requires_connect_events(self, project: Path) -> None:
        out = switch_stripe_account(
            from_alias="from",
            to_alias="to",
            account_mode="connect",
            project_path=str(project),
            platform_url=PLATFORM_URL,
            platform_events=["account.updated"],
            connect_events=None,
        )
        assert out["error"]["code"] == "E_MISSING_ARGUMENT"

    def test_unknown_alias(self, project: Path) -> None:
        out = switch_stripe_account(
            from_alias="ghost",
            to_alias="to",
            account_mode="standard",
            project_path=str(project),
            platform_url=PLATFORM_URL,
            platform_events=["x"],
        )
        assert out["error"]["code"] == "E_ALIAS_NOT_FOUND"


# ---------------------------------------------------------------------------
# Dry-run flow
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_returns_plan_without_mutating(self, project: Path) -> None:
        with _StubStripe(
            inventory_source={
                "webhooks": [_fake_webhook("we_old", PLATFORM_URL, connect=False, managed=True)],
                "products": [_fake_product("prod_old")],
            },
            inventory_destination={"webhooks": [], "products": []},
        ):
            out = switch_stripe_account(
                from_alias="from",
                to_alias="to",
                account_mode="standard",
                project_path=str(project),
                platform_url=PLATFORM_URL,
                platform_events=["customer.subscription.updated"],
                dry_run=True,
            )
        assert out["success"] is True
        data = out["data"]
        assert data["dry_run"] is True
        assert data["source_summary"]["webhook_endpoints_count"] == 1
        assert data["source_summary"]["products_count"] == 1
        assert data["destination_summary"]["webhook_endpoints_count"] == 0
        assert data["executed"] == []  # nothing executed in dry-run
        assert any(s["step"] == "webhooks" for s in data["plan"])

    def test_dry_run_estimates_duration(self, project: Path) -> None:
        with _StubStripe():
            out = switch_stripe_account(
                from_alias="from",
                to_alias="to",
                account_mode="standard",
                project_path=str(project),
                platform_url=PLATFORM_URL,
                platform_events=["x"],
                dry_run=True,
            )
        assert out["data"]["estimated_duration_seconds"] >= 1


# ---------------------------------------------------------------------------
# Test fixtures and helpers
# ---------------------------------------------------------------------------


def _fake_webhook(
    wid: str,
    url: str,
    *,
    connect: bool,
    managed: bool,
    events: list[str] | None = None,
    secret: str | None = None,
    account_mode: str | None = "standard",
) -> dict[str, Any]:
    metadata: dict[str, str] = {}
    if managed:
        metadata["specbox_managed"] = "true"
        if account_mode is not None:
            metadata["specbox_account_mode"] = account_mode
    return {
        "id": wid,
        "url": url,
        "connect": connect,
        "enabled_events": events or ["customer.subscription.updated"],
        "metadata": metadata,
        "status": "enabled",
        **({"secret": secret} if secret else {}),
    }


def _fake_product(pid: str, *, managed: bool = True) -> dict[str, Any]:
    metadata: dict[str, str] = {}
    if managed:
        metadata["specbox_managed"] = "true"
        metadata["tier_key"] = "basic"
    return {"id": pid, "name": "Basic", "metadata": metadata, "active": True}


class _StripeListing(dict):
    """Mimics a stripe ListObject."""


class _StubStripe:
    """Context manager that patches Stripe SDK calls used by switch_stripe_account.

    Provides default empty inventories. Callers can pass inventory_source
    and inventory_destination dicts to override.
    """

    def __init__(
        self,
        *,
        inventory_source: dict[str, list[dict[str, Any]]] | None = None,
        inventory_destination: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self.src = inventory_source or {"webhooks": [], "products": []}
        self.dst = inventory_destination or {"webhooks": [], "products": []}
        self._patches: list[Any] = []

    def __enter__(self) -> None:
        # Track which key is currently in stripe.api_key per call to route to
        # source vs destination inventory. simpler: we don't differentiate —
        # both inventories return the same thing per call ordering.
        # Here we simply alternate based on which call is made.
        self._patches.append(
            patch("stripe.WebhookEndpoint.list", side_effect=self._list_webhooks),
        )
        self._patches.append(
            patch("stripe.Product.list", side_effect=self._list_products),
        )
        self._patches.append(
            patch("stripe.Subscription.list", return_value=_StripeListing(data=[])),
        )
        self._patches.append(
            patch("stripe.Customer.list", return_value=_StripeListing(data=[])),
        )
        for p in self._patches:
            p.start()
        # Ordering: pre-flight is called twice (source then destination).
        # We use a simple counter per resource type to alternate.
        self._wh_calls = 0
        self._prod_calls = 0

    def __exit__(self, *_a: Any) -> None:
        for p in self._patches:
            p.stop()

    def _list_webhooks(self, *args: Any, **kwargs: Any) -> _StripeListing:
        self._wh_calls += 1
        if self._wh_calls == 1:
            return _StripeListing(data=self.src["webhooks"])
        if self._wh_calls == 2:
            return _StripeListing(data=self.dst["webhooks"])
        # subsequent calls: replicate (setup_webhook_endpoints internal listing)
        return _StripeListing(data=self.dst["webhooks"])

    def _list_products(self, *args: Any, **kwargs: Any) -> _StripeListing:
        self._prod_calls += 1
        if self._prod_calls == 1:
            return _StripeListing(data=self.src["products"])
        return _StripeListing(data=self.dst["products"])
