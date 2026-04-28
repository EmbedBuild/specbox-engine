"""Unit tests for T1 verify_account_setup (v0.2).

Covers UC-001 acceptance criteria. Stripe SDK is patched; no real API.

Mapping test → AC:
- AC-01 → test_standard_mode_returns_capabilities_no_canary,
          test_standard_mode_does_not_call_account_create_or_delete
- AC-02 → test_connect_mode_runs_canary_and_deletes,
          test_connect_mode_response_shape_matches_v01
- AC-03 → test_invalid_account_mode_returns_error,
          test_empty_account_mode_returns_error
- AC-05 → test_standard_mode_with_restricted_key,
          test_standard_mode_with_permission_error_marker
- AC-07 → test_response_data_includes_account_mode_field
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import stripe

from specbox_stripe_mcp.tools.verify_account_setup import verify_account_setup

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


# --- AC-01: standard mode happy path -----------------------------------------


class TestStandardMode:
    def test_standard_mode_returns_capabilities_no_canary(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-01: standard mode returns enabled=true + capabilities, no canary."""
        m_retrieve, _m_create, _m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            project_hint="motofan",
        )

        assert out["success"] is True
        data = out["data"]
        assert data["enabled"] is True
        assert data["platform_account_id"] == "acct_1TESTplatformId"
        assert data["display_name"] == "Moto.Fan"
        assert data["country"] == "ES"
        assert data["default_currency"] == "eur"
        assert sorted(data["capabilities_available"]) == [
            "card_payments",
            "sepa_debit_payments",
            "transfers",
        ]
        assert data["mode"] == "test"
        assert data["account_mode"] == "standard"

    def test_standard_mode_does_not_call_account_create_or_delete(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-01 reinforcement: standard mode never creates or deletes accounts."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            project_hint="motofan",
        )

        m_retrieve.assert_called_once()
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_standard_mode_with_restricted_key(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05: restricted key without account read → E_INSUFFICIENT_PERMISSIONS."""
        m_retrieve, _m_create, _m_delete = patch_stripe
        m_retrieve.side_effect = stripe.error.PermissionError(  # type: ignore[attr-defined]
            "The provided key does not have access to GET /v1/account."
        )

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INSUFFICIENT_PERMISSIONS"
        assert "restricted" in out["error"]["message"].lower()
        assert "remediation" in out["error"]
        assert "Account read" in out["error"]["remediation"]

    def test_standard_mode_with_permission_error_marker(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05 variant: InvalidRequestError with permission marker → E_INSUFFICIENT_PERMISSIONS."""
        m_retrieve, _m_create, _m_delete = patch_stripe
        m_retrieve.side_effect = stripe.error.InvalidRequestError(  # type: ignore[attr-defined]
            "insufficient permissions on this restricted key", param=None
        )

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INSUFFICIENT_PERMISSIONS"


# --- AC-02: connect mode preserves v0.1 behavior ------------------------------


class TestConnectMode:
    def test_connect_mode_runs_canary_and_deletes(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02: connect mode performs canary create+delete just like v0.1."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["enabled"] is True
        assert out["data"]["account_mode"] == "connect"
        m_create.assert_called_once()
        m_delete.assert_called_once_with("acct_1PROBE0000001")

    def test_connect_mode_response_shape_matches_v01(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-02: connect-mode envelope has the exact v0.1 keys (plus account_mode)."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            project_hint="motofan",
        )

        data = out["data"]
        for key in (
            "enabled",
            "platform_account_id",
            "display_name",
            "country",
            "default_currency",
            "capabilities_available",
            "mode",
            "account_mode",
        ):
            assert key in data, f"missing data.{key} in connect-mode response"

    def test_connect_not_enabled_returns_remediation(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02 reinforcement: Connect not activated → enabled:false + remediation URL."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.side_effect = stripe.error.PermissionError(  # type: ignore[attr-defined]
            "Your account has not activated Connect. Please activate Connect in the dashboard."
        )

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["enabled"] is False
        assert out["error"]["code"] == "E_CONNECT_NOT_ENABLED"
        assert "test/connect/overview" in out["error"]["remediation"]
        m_delete.assert_not_called()

    def test_connect_skip_canary_warns(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """skip_canary=True in connect mode warns and skips Account.create."""
        m_retrieve, m_create, _m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            project_hint="motofan",
            skip_canary=True,
        )

        assert out["success"] is True
        assert out["data"]["enabled"] is True
        assert any("skip_canary" in w for w in out.get("warnings", []))
        m_create.assert_not_called()


# --- AC-03: argument validation ----------------------------------------------


class TestArgumentValidation:
    def test_invalid_account_mode_returns_error(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03: account_mode='express' (not 'standard'/'connect') → E_INVALID_ARGUMENT."""
        m_retrieve, m_create, m_delete = patch_stripe

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="express",  # type: ignore[arg-type]
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"
        assert "standard" in out["error"]["message"]
        assert "connect" in out["error"]["message"]
        m_retrieve.assert_not_called()
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_empty_account_mode_returns_error(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03: empty account_mode → E_INVALID_ARGUMENT."""
        m_retrieve, _m_create, _m_delete = patch_stripe

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="",  # type: ignore[arg-type]
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"
        m_retrieve.assert_not_called()


# --- AC-07: response schema documents account_mode ----------------------------


class TestResponseSchema:
    def test_response_data_includes_account_mode_field(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-07: data.account_mode is always present and matches the request."""
        m_retrieve, _m_create, _m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            project_hint="motofan",
        )

        assert "account_mode" in out["data"]
        assert out["data"]["account_mode"] == "standard"

    def test_response_data_account_mode_connect(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-07 variant: account_mode='connect' is reflected in data."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        out = verify_account_setup(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            project_hint="motofan",
        )

        assert out["data"]["account_mode"] == "connect"


# --- Live-mode + heartbeat sanity checks (regression coverage) ----------------


class TestLiveModeAndTelemetry:
    def test_live_key_rejected_without_opt_in(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """sk_live_* without allow_live_mode → E_LIVE_MODE_NOT_ALLOWED, no API calls."""
        m_retrieve, m_create, m_delete = patch_stripe

        out = verify_account_setup(
            stripe_api_key=LIVE_KEY,
            account_mode="standard",
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_LIVE_MODE_NOT_ALLOWED"
        m_retrieve.assert_not_called()
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_heartbeat_carries_account_mode(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """Heartbeat payload includes account_mode for telemetry segmentation."""
        m_retrieve, _m_create, _m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        captured: list[dict[str, Any]] = []

        def capture(*, project: str, event_type: str, payload: dict) -> None:
            captured.append(payload)

        with patch(
            "specbox_stripe_mcp.tools.verify_account_setup.report_heartbeat",
            side_effect=capture,
        ):
            verify_account_setup(
                stripe_api_key=TEST_KEY,
                account_mode="standard",
                project_hint="motofan",
            )

        assert len(captured) == 1
        assert captured[0]["account_mode"] == "standard"
        assert captured[0]["tool"] == "verify_account_setup"
        assert captured[0]["success"] is True
