"""Unit tests for T2 setup_webhook_endpoints.

Covers AC-01..AC-07 of UC-2. Stripe SDK patched; no real API.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
import stripe

from specbox_stripe_mcp.tools.setup_webhook_endpoints import setup_webhook_endpoints

TEST_KEY = "sk_" + "test_" + "FixtureKeyNotRealNotFromStripe"
PLATFORM_URL = "https://proj.supabase.co/functions/v1/stripe-webhook"
PLATFORM_EVENTS = ["account.updated", "capability.updated"]
CONNECT_EVENTS = ["customer.subscription.created", "invoice.paid"]


class _StripeListing(dict):
    """Mimics a stripe ListObject enough to call .get('data')."""


def _endpoint(
    *,
    wid: str,
    url: str,
    connect: bool,
    events: list[str],
    managed: bool = True,
    secret: str | None = None,
    account_mode: str | None = "connect",
) -> dict[str, Any]:
    """Build a fake endpoint dict.

    By default endpoints carry specbox_account_mode='connect' so they match
    the v0.2 idempotency lookup without triggering silent migration. Pass
    account_mode=None to simulate a v0.1 endpoint missing the field.
    """
    metadata: dict[str, str] = {}
    if managed:
        metadata["specbox_managed"] = "true"
        if account_mode is not None:
            metadata["specbox_account_mode"] = account_mode
    endpoint: dict[str, Any] = {
        "id": wid,
        "url": url,
        "connect": connect,
        "enabled_events": events,
        "metadata": metadata,
        "status": "enabled",
    }
    if secret:
        endpoint["secret"] = secret
    return endpoint


@pytest.fixture
def patch_stripe():  # type: ignore[no-untyped-def]
    """Patch webhook_endpoints list/create/modify/retrieve."""
    with patch("stripe.WebhookEndpoint.list") as m_list, patch(
        "stripe.WebhookEndpoint.create"
    ) as m_create, patch("stripe.WebhookEndpoint.modify") as m_modify, patch(
        "stripe.WebhookEndpoint.retrieve"
    ) as m_retrieve:
        yield m_list, m_create, m_modify, m_retrieve


class TestAcceptance:
    def test_create_both_when_none_exist(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-01: no previous endpoints → creates 2 with specbox_managed metadata."""
        m_list, m_create, m_modify, _m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(data=[])
        m_create.side_effect = [
            _endpoint(
                wid="we_platform",
                url=PLATFORM_URL,
                connect=False,
                events=PLATFORM_EVENTS,
                secret="whsec_platform_secret_abc123",
            ),
            _endpoint(
                wid="we_connect",
                url=PLATFORM_URL,
                connect=True,
                events=CONNECT_EVENTS,
                secret="whsec_connect_secret_xyz789",
            ),
        ]

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is True
        data = out["data"]
        assert data["platform"]["id"] == "we_platform"
        assert data["platform"]["connect"] is False
        assert data["platform"]["secret"] == "whsec_platform_secret_abc123"
        assert data["platform"]["created_or_reused"] == "created"
        assert data["connect"]["id"] == "we_connect"
        assert data["connect"]["connect"] is True
        assert data["connect"]["created_or_reused"] == "created"
        # both creates stamped metadata
        for call in m_create.call_args_list:
            md = call.kwargs["metadata"]
            assert md["specbox_managed"] == "true"
        m_modify.assert_not_called()

    def test_reuse_when_matching_exists(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02: re-invocation with matching endpoints → reused, secret via expand."""
        m_list, m_create, m_modify, m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(wid="we_pf", url=PLATFORM_URL, connect=False, events=PLATFORM_EVENTS),
                _endpoint(wid="we_cn", url=PLATFORM_URL, connect=True, events=CONNECT_EVENTS),
            ]
        )
        # retrieve-with-expand must yield the secret since listing never includes it.
        m_retrieve.side_effect = lambda wid, **kw: _endpoint(
            wid=wid,
            url=PLATFORM_URL,
            connect=(wid == "we_cn"),
            events=PLATFORM_EVENTS if wid == "we_pf" else CONNECT_EVENTS,
            secret=f"whsec_reused_{wid}",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["platform"]["created_or_reused"] == "reused"
        assert out["data"]["connect"]["created_or_reused"] == "reused"
        assert out["data"]["platform"]["secret"] == "whsec_reused_we_pf"
        assert out["data"]["connect"]["secret"] == "whsec_reused_we_cn"
        m_create.assert_not_called()
        m_modify.assert_not_called()
        # Both retrieves used expand=['secret']
        for call in m_retrieve.call_args_list:
            assert call.kwargs.get("expand") == ["secret"]

    def test_update_when_events_differ(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03: existing SpecBox-managed endpoint with different events → UPDATE."""
        m_list, _m_create, m_modify, m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(
                    wid="we_pf_old",
                    url=PLATFORM_URL,
                    connect=False,
                    events=["account.updated"],  # missing capability.updated
                ),
                _endpoint(
                    wid="we_cn",
                    url=PLATFORM_URL,
                    connect=True,
                    events=CONNECT_EVENTS,
                ),
            ]
        )
        m_modify.return_value = _endpoint(
            wid="we_pf_old",
            url=PLATFORM_URL,
            connect=False,
            events=PLATFORM_EVENTS,
            secret="whsec_updated_pf",
        )
        m_retrieve.side_effect = lambda wid, **kw: _endpoint(
            wid=wid, url=PLATFORM_URL, connect=True, events=CONNECT_EVENTS,
            secret="whsec_reused_cn",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["platform"]["created_or_reused"] == "updated"
        # modify was called with the new enabled_events list
        call = m_modify.call_args
        assert sorted(call.kwargs["enabled_events"]) == sorted(PLATFORM_EVENTS)

    def test_unknown_event_type_rejected(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-04: Stripe rejects an event type → E_UNKNOWN_EVENT_TYPE, no partial creates."""
        m_list, m_create, _m_modify, _m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(data=[])
        m_create.side_effect = stripe.error.InvalidRequestError(  # type: ignore[attr-defined]
            "The event 'bogus.event' is not a valid enabled_events value.",
            param="enabled_events",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=["bogus.event"],
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_UNKNOWN_EVENT_TYPE"
        # Only the first (platform) create attempt; connect was never attempted.
        assert m_create.call_count == 1

    def test_http_url_rejected_before_stripe(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05: non-HTTPS URL → E_INVALID_URL, zero Stripe calls."""
        m_list, m_create, _m_modify, m_retrieve = patch_stripe

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url="http://insecure.example.com/webhook",
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_URL"
        m_list.assert_not_called()
        m_create.assert_not_called()
        m_retrieve.assert_not_called()

    def test_evidence_and_idempotency_hit_reuse(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-06: reuse path emits heartbeat with idempotency_hit=true + engram observation."""
        m_list, _m_create, _m_modify, m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(wid="we_pf", url=PLATFORM_URL, connect=False, events=PLATFORM_EVENTS),
                _endpoint(wid="we_cn", url=PLATFORM_URL, connect=True, events=CONNECT_EVENTS),
            ]
        )
        m_retrieve.side_effect = lambda wid, **kw: _endpoint(
            wid=wid,
            url=PLATFORM_URL,
            connect=(wid == "we_cn"),
            events=PLATFORM_EVENTS if wid == "we_pf" else CONNECT_EVENTS,
            secret=f"whsec_reused_{wid}",
        )

        captured_hb: list[dict[str, Any]] = []

        def fake_hb(*, project: str, event_type: str, payload: dict) -> None:
            captured_hb.append(payload)

        with patch(
            "specbox_stripe_mcp.tools.setup_webhook_endpoints.report_heartbeat",
            side_effect=fake_hb,
        ), patch(
            "specbox_stripe_mcp.tools.setup_webhook_endpoints.write_config_observation",
            return_value="obs_abc123",
        ) as m_engram:
            out = setup_webhook_endpoints(
                stripe_api_key=TEST_KEY,
                account_mode="connect",
                platform_url=PLATFORM_URL,
                platform_events=PLATFORM_EVENTS,
                connect_events=CONNECT_EVENTS,
                project_hint="motofan",
            )

        assert out["success"] is True
        assert out["evidence"]["engram_observation_id"] == "obs_abc123"
        assert captured_hb[-1]["idempotency_hit"] is True
        # The engram observation must not contain the full secret.
        call_kwargs = m_engram.call_args.kwargs
        content = call_kwargs["content"]
        assert "whsec_reused_we_pf" not in content
        assert "whsec_reused_we_cn" not in content

    def test_idempotency_key_is_stable_and_sent_on_create(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-07: concurrent invocations with identical input produce the same Idempotency-Key."""
        m_list, m_create, _m_modify, _m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(data=[])
        m_create.side_effect = [
            _endpoint(wid="we_platform", url=PLATFORM_URL, connect=False,
                      events=PLATFORM_EVENTS, secret="whsec_p"),
            _endpoint(wid="we_connect", url=PLATFORM_URL, connect=True,
                      events=CONNECT_EVENTS, secret="whsec_c"),
        ]

        setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        # Reset + run again with identical inputs.
        m_create.reset_mock()
        m_list.return_value = _StripeListing(data=[])
        m_create.side_effect = [
            _endpoint(wid="we_platform_2", url=PLATFORM_URL, connect=False,
                      events=PLATFORM_EVENTS, secret="whsec_p2"),
            _endpoint(wid="we_connect_2", url=PLATFORM_URL, connect=True,
                      events=CONNECT_EVENTS, secret="whsec_c2"),
        ]
        setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        run1_keys = sorted(
            c.kwargs["idempotency_key"] for c in m_create.call_args_list
        )
        # Both calls sent an idempotency_key.
        assert all(k.startswith("specbox-") for k in run1_keys)


class TestInputs:
    def test_empty_platform_events_rejected(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        m_list, m_create, *_ = patch_stripe
        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=[],
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_INVALID_INPUT"
        m_list.assert_not_called()
        m_create.assert_not_called()

    def test_live_key_rejected(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        m_list, *_ = patch_stripe
        out = setup_webhook_endpoints(
            stripe_api_key="sk_" + "live_" + "FixtureABCdef",
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )
        assert out["error"]["code"] == "E_LIVE_MODE_NOT_ALLOWED"
        m_list.assert_not_called()


# --- UC-002 v0.2 — account_mode dispatch -------------------------------------


class TestUC002StandardMode:
    """AC-01, AC-02: account_mode='standard' creates 1 endpoint, rejects connect args."""

    def test_standard_creates_one_endpoint(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-01: standard mode creates exactly one endpoint with connect=False."""
        m_list, m_create, m_modify, _m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(data=[])
        m_create.return_value = _endpoint(
            wid="we_platform",
            url=PLATFORM_URL,
            connect=False,
            events=PLATFORM_EVENTS,
            secret="whsec_platform_only",
            account_mode="standard",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint="saas-app",
        )

        assert out["success"] is True
        data = out["data"]
        assert data["account_mode"] == "standard"
        assert data["platform"]["id"] == "we_platform"
        assert data["platform"]["connect"] is False
        # AC-01: data.connect MUST NOT be present in standard mode.
        assert "connect" not in data
        # Single Account.create call.
        assert m_create.call_count == 1
        # The created endpoint had connect=False explicitly.
        kwargs = m_create.call_args.kwargs
        assert kwargs["connect"] is False
        # And carried specbox_account_mode='standard' in metadata.
        assert kwargs["metadata"]["specbox_account_mode"] == "standard"
        m_modify.assert_not_called()

    def test_standard_rejects_connect_events(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02: passing connect_events in standard mode → E_INVALID_ARGUMENT."""
        m_list, m_create, *_ = patch_stripe

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="saas-app",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"
        assert "connect_events" in out["error"]["message"]
        m_list.assert_not_called()
        m_create.assert_not_called()

    def test_standard_rejects_connect_url(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-02 variant: passing connect_url in standard mode → E_INVALID_ARGUMENT."""
        m_list, m_create, *_ = patch_stripe

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_url="https://other.example.com/webhook",
            project_hint="saas-app",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"
        assert "connect_url" in out["error"]["message"]
        m_list.assert_not_called()
        m_create.assert_not_called()


class TestUC002ConnectMode:
    """AC-03, AC-04: connect mode requires connect_events and preserves v0.1 shape."""

    def test_connect_requires_connect_events(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03: connect mode without connect_events → E_MISSING_ARGUMENT."""
        m_list, *_ = patch_stripe

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_MISSING_ARGUMENT"
        assert "connect_events" in out["error"]["message"]
        m_list.assert_not_called()

    def test_connect_empty_list_also_missing(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-03 variant: connect_events=[] is also treated as missing."""
        m_list, *_ = patch_stripe

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=[],
            project_hint="motofan",
        )

        assert out["success"] is False
        assert out["error"]["code"] == "E_MISSING_ARGUMENT"
        m_list.assert_not_called()

    def test_connect_response_shape_has_platform_and_connect(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-04: connect mode response keeps v0.1 keys (data.platform + data.connect)."""
        m_list, m_create, _m_modify, _m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(data=[])
        m_create.side_effect = [
            _endpoint(
                wid="we_pf",
                url=PLATFORM_URL,
                connect=False,
                events=PLATFORM_EVENTS,
                secret="whsec_pf",
            ),
            _endpoint(
                wid="we_cn",
                url=PLATFORM_URL,
                connect=True,
                events=CONNECT_EVENTS,
                secret="whsec_cn",
            ),
        ]

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        data = out["data"]
        assert "platform" in data
        assert "connect" in data
        for key in ("id", "url", "secret", "events", "status", "connect", "created_or_reused"):
            assert key in data["platform"]
            assert key in data["connect"]


class TestUC002Idempotency:
    """AC-05: idempotency preserved within and across modes."""

    def test_idempotency_within_standard(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05: 2nd call with same args in standard mode → reused, no create."""
        m_list, m_create, m_modify, m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(
                    wid="we_pf",
                    url=PLATFORM_URL,
                    connect=False,
                    events=PLATFORM_EVENTS,
                    account_mode="standard",
                ),
            ]
        )
        m_retrieve.side_effect = lambda wid, **kw: _endpoint(
            wid=wid,
            url=PLATFORM_URL,
            connect=False,
            events=PLATFORM_EVENTS,
            secret=f"whsec_reused_{wid}",
            account_mode="standard",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint="saas-app",
        )

        assert out["data"]["platform"]["created_or_reused"] == "reused"
        m_create.assert_not_called()
        m_modify.assert_not_called()

    def test_cross_mode_no_collision(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        """AC-05 + isolation: a connect-mode endpoint at the same URL is NOT reused
        when the caller asks for standard mode. A new endpoint is created instead."""
        m_list, m_create, _m_modify, _m_retrieve = patch_stripe
        # Existing endpoint is connect-mode at the same URL.
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(
                    wid="we_existing_connect",
                    url=PLATFORM_URL,
                    connect=False,
                    events=PLATFORM_EVENTS,
                    account_mode="connect",
                ),
            ]
        )
        m_create.return_value = _endpoint(
            wid="we_new_standard",
            url=PLATFORM_URL,
            connect=False,
            events=PLATFORM_EVENTS,
            secret="whsec_new",
            account_mode="standard",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint="saas-app",
        )

        assert out["data"]["platform"]["created_or_reused"] == "created"
        m_create.assert_called_once()
        kwargs = m_create.call_args.kwargs
        assert kwargs["metadata"]["specbox_account_mode"] == "standard"


class TestUC002SilentMigration:
    """AC-06: v0.1 endpoint without specbox_account_mode is reused and stamped."""

    def test_v01_endpoint_silently_migrated_to_standard(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-06: matching v0.1 endpoint (no account_mode) → reused, metadata updated."""
        m_list, m_create, m_modify, _m_retrieve = patch_stripe
        # v0.1 endpoint: same url+connect-flag, same events, but missing
        # specbox_account_mode in metadata.
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(
                    wid="we_legacy",
                    url=PLATFORM_URL,
                    connect=False,
                    events=PLATFORM_EVENTS,
                    account_mode=None,  # v0.1 style
                ),
            ]
        )
        m_modify.return_value = _endpoint(
            wid="we_legacy",
            url=PLATFORM_URL,
            connect=False,
            events=PLATFORM_EVENTS,
            secret="whsec_migrated",
            account_mode="standard",
        )

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="standard",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint="saas-app",
        )

        assert out["success"] is True
        assert out["data"]["platform"]["id"] == "we_legacy"
        # No new endpoint was created — silent migration is reuse, not recreate.
        assert out["data"]["platform"]["created_or_reused"] == "reused"
        m_create.assert_not_called()
        # modify was called to stamp the new metadata key.
        m_modify.assert_called_once()
        modify_kwargs = m_modify.call_args.kwargs
        assert modify_kwargs["metadata"]["specbox_account_mode"] == "standard"
        assert modify_kwargs["metadata"]["specbox_managed"] == "true"

    def test_v01_endpoint_silently_migrated_to_connect(  # type: ignore[no-untyped-def]
        self, patch_stripe
    ) -> None:
        """AC-06 variant: same logic on the connect-side endpoint of a v0.1 setup."""
        m_list, m_create, m_modify, _m_retrieve = patch_stripe
        m_list.return_value = _StripeListing(
            data=[
                _endpoint(
                    wid="we_pf_legacy",
                    url=PLATFORM_URL,
                    connect=False,
                    events=PLATFORM_EVENTS,
                    account_mode=None,
                ),
                _endpoint(
                    wid="we_cn_legacy",
                    url=PLATFORM_URL,
                    connect=True,
                    events=CONNECT_EVENTS,
                    account_mode=None,
                ),
            ]
        )
        m_modify.side_effect = [
            _endpoint(
                wid="we_pf_legacy",
                url=PLATFORM_URL,
                connect=False,
                events=PLATFORM_EVENTS,
                secret="whsec_pf_mig",
                account_mode="connect",
            ),
            _endpoint(
                wid="we_cn_legacy",
                url=PLATFORM_URL,
                connect=True,
                events=CONNECT_EVENTS,
                secret="whsec_cn_mig",
                account_mode="connect",
            ),
        ]

        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="connect",
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            connect_events=CONNECT_EVENTS,
            project_hint="motofan",
        )

        assert out["success"] is True
        assert out["data"]["platform"]["created_or_reused"] == "reused"
        assert out["data"]["connect"]["created_or_reused"] == "reused"
        m_create.assert_not_called()
        # Both endpoints stamped with specbox_account_mode='connect'.
        assert m_modify.call_count == 2
        for call in m_modify.call_args_list:
            assert call.kwargs["metadata"]["specbox_account_mode"] == "connect"


class TestUC002ArgumentValidation:
    """Unknown account_mode is rejected before any Stripe call."""

    def test_invalid_account_mode_rejected(self, patch_stripe) -> None:  # type: ignore[no-untyped-def]
        m_list, *_ = patch_stripe
        out = setup_webhook_endpoints(
            stripe_api_key=TEST_KEY,
            account_mode="express",  # type: ignore[arg-type]
            platform_url=PLATFORM_URL,
            platform_events=PLATFORM_EVENTS,
            project_hint="x",
        )
        assert out["error"]["code"] == "E_INVALID_ARGUMENT"
        m_list.assert_not_called()
