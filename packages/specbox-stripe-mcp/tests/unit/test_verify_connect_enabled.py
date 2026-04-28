"""Unit tests for the verify_connect_enabled deprecated shim (UC-001 AC-04).

Since v0.2 verify_connect_enabled is a thin alias around
verify_account_setup(account_mode='connect'). These tests verify:
- The shim emits a DeprecationWarning on every call.
- The shim returns the same response shape as v0.1.
- The shim forwards all arguments correctly.

Stripe SDK is patched; no real API.
"""

from __future__ import annotations

import warnings
from unittest.mock import patch

import pytest
import stripe

from specbox_stripe_mcp.tools.verify_connect_enabled import verify_connect_enabled

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"
LIVE_KEY = "sk_" + "live_" + "FixtureKeyNotRealNotFromStripe"


class FakeAccount(dict):
    """Mimics a stripe.Account object closely enough for our .get() usage."""


def _fake_platform_account() -> FakeAccount:
    return FakeAccount(
        id="acct_1TESTplatformId",
        country="ES",
        default_currency="eur",
        capabilities={
            "card_payments": "active",
            "transfers": "active",
            "sepa_debit_payments": "inactive",
        },
        business_profile={"name": "Moto.Fan"},
        email="owner@motofan.test",
    )


def _fake_probe_account() -> FakeAccount:
    return FakeAccount(id="acct_1PROBE0000001")


@pytest.fixture
def patch_stripe():  # type: ignore[no-untyped-def]
    """Patch the Stripe SDK calls used by T1."""
    with (
        patch("stripe.Account.retrieve") as m_retrieve,
        patch("stripe.Account.create") as m_create,
        patch("stripe.Account.delete") as m_delete,
    ):
        yield m_retrieve, m_create, m_delete


# --- AC-04: alias deprecated --------------------------------------------------


class TestDeprecation:
    def test_alias_emits_deprecation_warning(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-04: every call to the alias emits a DeprecationWarning pointing to the new name."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        with warnings.catch_warnings(record=True) as recorded:
            warnings.simplefilter("always")
            verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        deprecation_warnings = [
            w for w in recorded if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 1
        msg = str(deprecation_warnings[0].message)
        assert "deprecated" in msg.lower()
        assert "verify_account_setup" in msg
        assert "account_mode='connect'" in msg

    def test_alias_returns_same_envelope_as_v01(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-04: response shape preserves the v0.1 keys consumers expect."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key=TEST_KEY, project_hint="motofan"
            )

        assert out["success"] is True
        for key in (
            "enabled",
            "platform_account_id",
            "display_name",
            "country",
            "default_currency",
            "capabilities_available",
            "mode",
        ):
            assert key in out["data"], f"missing data.{key} (v0.1 contract)"

    def test_alias_forces_connect_mode(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-04: alias always delegates with account_mode='connect' regardless of caller."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key=TEST_KEY, project_hint="motofan"
            )

        assert out["data"]["account_mode"] == "connect"
        m_create.assert_called_once()  # canary did run


# --- Regression coverage of the old behavior (still works through the shim) ---


class TestBackwardCompatibleBehavior:
    def test_enabled_happy_path(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """v0.1 happy path still produces enabled=true with full platform info."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key=TEST_KEY, project_hint="motofan"
            )

        assert out["success"] is True
        data = out["data"]
        assert data["enabled"] is True
        assert data["platform_account_id"] == "acct_1TESTplatformId"
        assert data["display_name"] == "Moto.Fan"
        assert data["mode"] == "test"

    def test_connect_not_enabled_returns_remediation(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """v0.1 path: Connect not activated → enabled:false + remediation URL."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.side_effect = stripe.error.PermissionError(  # type: ignore[attr-defined]
            "Your account has not activated Connect. Please activate Connect in the dashboard."
        )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key=TEST_KEY, project_hint="motofan"
            )

        assert out["success"] is True
        assert out["data"]["enabled"] is False
        assert out["error"]["code"] == "E_CONNECT_NOT_ENABLED"
        assert "dashboard.stripe.com" in out["error"]["remediation"]
        m_delete.assert_not_called()

    def test_invalid_key_rejected_before_canary(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """v0.1 path: malformed key → E_INVALID_KEY without any API call."""
        m_retrieve, m_create, m_delete = patch_stripe

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key="garbage", project_hint="motofan"
            )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_KEY"
        m_retrieve.assert_not_called()
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_canary_account_is_deleted_after_create(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """v0.1 path: successful canary deletes the probe account."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        m_create.assert_called_once()
        m_delete.assert_called_once_with("acct_1PROBE0000001")

    def test_live_key_rejected_without_opt_in(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """v0.1 path: sk_live_* without opt-in → E_LIVE_MODE_NOT_ALLOWED."""
        m_retrieve, _m_create, _m_delete = patch_stripe

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key=LIVE_KEY, project_hint="motofan"
            )

        assert out["success"] is False
        assert out["error"]["code"] == "E_LIVE_MODE_NOT_ALLOWED"
        m_retrieve.assert_not_called()


class TestSkipCanary:
    def test_skip_canary_warns_and_skips_create(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            out = verify_connect_enabled(
                stripe_api_key=TEST_KEY, project_hint="motofan", skip_canary=True
            )

        assert out["success"] is True
        assert out["data"]["enabled"] is True
        assert out.get("warnings")
        assert any("skip_canary" in w for w in out["warnings"])
        m_create.assert_not_called()
        m_delete.assert_not_called()
