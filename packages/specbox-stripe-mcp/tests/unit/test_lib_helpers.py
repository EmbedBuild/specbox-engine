"""Coverage tests for lib/idempotency.py and lib/stripe_client.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import stripe

from specbox_stripe_mcp.lib.idempotency import (
    base_metadata,
    is_specbox_managed,
    stable_idempotency_key,
)
from specbox_stripe_mcp.lib.stripe_client import StripeClient


class TestIdempotencyHelpers:
    def test_base_metadata_contains_required_fields(self) -> None:
        md = base_metadata("proj-x")
        assert md["specbox_managed"] == "true"
        assert md["specbox_project_hint"] == "proj-x"
        assert md["specbox_version"]
        assert md["specbox_created_at"]

    def test_base_metadata_merges_extra(self) -> None:
        md = base_metadata("p", extra={"tier_key": "bronce", "num": 42})
        assert md["tier_key"] == "bronce"
        # extras coerced to str
        assert md["num"] == "42"

    def test_base_metadata_unknown_project_when_empty(self) -> None:
        md = base_metadata("")
        assert md["specbox_project_hint"] == "unknown"

    def test_is_specbox_managed_true(self) -> None:
        assert is_specbox_managed({"specbox_managed": "true"}) is True

    def test_is_specbox_managed_false_for_missing(self) -> None:
        assert is_specbox_managed({}) is False
        assert is_specbox_managed(None) is False

    def test_is_specbox_managed_case_insensitive(self) -> None:
        assert is_specbox_managed({"specbox_managed": "TRUE"}) is True
        assert is_specbox_managed({"specbox_managed": "True"}) is True

    def test_stable_idempotency_key_is_deterministic(self) -> None:
        key_a = stable_idempotency_key("tool", "url", False, ["a", "b"])
        key_b = stable_idempotency_key("tool", "url", False, ["a", "b"])
        assert key_a == key_b
        assert key_a.startswith("specbox-")

    def test_stable_idempotency_key_changes_with_inputs(self) -> None:
        a = stable_idempotency_key("tool", "url_1")
        b = stable_idempotency_key("tool", "url_2")
        assert a != b


class TestStripeClientRetry:
    def test_non_retryable_error_raises(self) -> None:
        client = StripeClient(api_key="sk_test_abc")

        def op() -> dict:
            raise stripe.error.InvalidRequestError(  # type: ignore[attr-defined]
                "bad param", param="x"
            )

        with pytest.raises(stripe.error.InvalidRequestError):  # type: ignore[attr-defined]
            client.call("op", op)

    def test_retry_exhausted_raises_last_exception(self) -> None:
        client = StripeClient(api_key="sk_test_abc")

        def op() -> dict:
            raise stripe.error.RateLimitError("always limited")  # type: ignore[attr-defined]

        with patch("time.sleep"), patch(
            "specbox_stripe_mcp.lib.stripe_client.report_healing"
        ):
            with pytest.raises(stripe.error.RateLimitError):  # type: ignore[attr-defined]
                client.call("x.y", op)

    def test_api_version_override(self) -> None:
        client = StripeClient(api_key="sk_test_abc", api_version="2023-10-16")
        assert client.api_version == "2023-10-16"
