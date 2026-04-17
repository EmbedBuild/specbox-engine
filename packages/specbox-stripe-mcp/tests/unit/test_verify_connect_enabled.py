"""Unit tests for T1 verify_connect_enabled.

Covers acceptance criteria AC-01..AC-06 of UC-1. Stripe SDK is patched; no real API.

Mapping test → AC:
- AC-01 → test_enabled_happy_path
- AC-02 → test_connect_not_enabled_returns_remediation
- AC-03 → test_invalid_key_rejected_before_canary
- AC-04 → test_canary_account_is_deleted_after_create
- AC-05 → test_live_key_rejected_without_opt_in
- AC-06 → test_heartbeat_emitted_on_success
"""

from __future__ import annotations

from typing import Any
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
    with patch("stripe.Account.retrieve") as m_retrieve, patch(
        "stripe.Account.create"
    ) as m_create, patch("stripe.Account.delete") as m_delete:
        yield m_retrieve, m_create, m_delete


class TestAcceptance:
    def test_enabled_happy_path(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-01: valid test key + Connect active → enabled:true with full platform info."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

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

    def test_connect_not_enabled_returns_remediation(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-02: Connect not activated → enabled:false + remediation URL."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.side_effect = stripe.error.PermissionError(  # type: ignore[attr-defined]
            "Your account has not activated Connect. Please activate Connect in the dashboard."
        )

        out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert out["success"] is True  # tool itself succeeded
        assert out["data"]["enabled"] is False
        assert out["error"]["code"] == "E_CONNECT_NOT_ENABLED"
        assert "dashboard.stripe.com" in out["error"]["remediation"]
        assert "test/connect/overview" in out["error"]["remediation"]
        m_delete.assert_not_called()

    def test_invalid_key_rejected_before_canary(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-03: malformed key → E_INVALID_KEY without canary call."""
        m_retrieve, m_create, m_delete = patch_stripe

        out = verify_connect_enabled(stripe_api_key="garbage", project_hint="motofan")

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_KEY"
        m_retrieve.assert_not_called()
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_invalid_key_via_auth_error(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03 variant: well-formed but unauthenticated → E_INVALID_KEY on retrieve."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.side_effect = stripe.error.AuthenticationError(  # type: ignore[attr-defined]
            "Invalid API key provided"
        )

        out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_KEY"
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_canary_account_is_deleted_after_create(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-04: successful canary creates and immediately deletes probe account."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        out = verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert out["success"] is True
        assert out["data"]["enabled"] is True
        m_create.assert_called_once()
        m_delete.assert_called_once_with("acct_1PROBE0000001")

    def test_canary_probe_carries_specbox_metadata(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-04 reinforcement: probe account carries specbox_probe metadata for trace recovery."""
        m_retrieve, m_create, _m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()

        verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        kwargs = m_create.call_args.kwargs
        assert kwargs["type"] == "express"
        assert kwargs["country"] == "ES"
        assert kwargs["metadata"]["specbox_probe"] == "true"

    def test_live_key_rejected_without_opt_in(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-05: sk_live_* without allow_live_mode → E_LIVE_MODE_NOT_ALLOWED, no API calls."""
        m_retrieve, m_create, m_delete = patch_stripe

        out = verify_connect_enabled(stripe_api_key=LIVE_KEY, project_hint="motofan")

        assert out["success"] is False
        assert out["error"]["code"] == "E_LIVE_MODE_NOT_ALLOWED"
        m_retrieve.assert_not_called()
        m_create.assert_not_called()
        m_delete.assert_not_called()

    def test_live_key_accepted_with_full_opt_in(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-05 inverse: sk_live_* with allow_live_mode + correct token → proceeds, mode='live'."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        out = verify_connect_enabled(
            stripe_api_key=LIVE_KEY,
            project_hint="motofan",
            allow_live_mode=True,
            live_mode_confirm_token="I acknowledge this affects real money",
        )

        assert out["success"] is True
        assert out["data"]["mode"] == "live"

    def test_heartbeat_emitted_on_success(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-06: every execution emits a heartbeat with tool, success, duration_ms, mode."""
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.return_value = _fake_probe_account()
        m_delete.return_value = {"deleted": True, "id": "acct_1PROBE0000001"}

        captured: list[dict[str, Any]] = []

        def capture(*, project: str, event_type: str, payload: dict) -> None:
            captured.append(
                {"project": project, "event_type": event_type, "payload": payload}
            )

        with patch(
            "specbox_stripe_mcp.tools.verify_connect_enabled.report_heartbeat",
            side_effect=capture,
        ):
            verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert len(captured) == 1
        hb = captured[0]
        assert hb["project"] == "motofan"
        assert hb["event_type"] == "stripe_mcp_call"
        assert hb["payload"]["tool"] == "verify_connect_enabled"
        assert hb["payload"]["success"] is True
        assert hb["payload"]["mode"] == "test"
        assert isinstance(hb["payload"]["duration_ms"], (int, float))
        assert hb["payload"]["duration_ms"] >= 0

    def test_heartbeat_emitted_on_failure(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-06 reinforcement: heartbeat emitted even when Connect is not enabled."""
        m_retrieve, m_create, _m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()
        m_create.side_effect = stripe.error.PermissionError(  # type: ignore[attr-defined]
            "Connect is not enabled for this platform"
        )

        captured: list[dict[str, Any]] = []

        def capture(*, project: str, event_type: str, payload: dict) -> None:
            captured.append(payload)

        with patch(
            "specbox_stripe_mcp.tools.verify_connect_enabled.report_heartbeat",
            side_effect=capture,
        ):
            verify_connect_enabled(stripe_api_key=TEST_KEY, project_hint="motofan")

        assert any(p["success"] is False for p in captured)


class TestSkipCanary:
    def test_skip_canary_warns_and_skips_create(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        m_retrieve, m_create, m_delete = patch_stripe
        m_retrieve.return_value = _fake_platform_account()

        out = verify_connect_enabled(
            stripe_api_key=TEST_KEY, project_hint="motofan", skip_canary=True
        )

        assert out["success"] is True
        assert out["data"]["enabled"] is True
        assert out.get("warnings")
        assert any("skip_canary" in w for w in out["warnings"])
        m_create.assert_not_called()
        m_delete.assert_not_called()
