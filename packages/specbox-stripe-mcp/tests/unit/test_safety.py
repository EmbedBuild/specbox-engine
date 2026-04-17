"""Tests for lib/safety.py."""

from __future__ import annotations

import pytest

from specbox_stripe_mcp.lib.safety import (
    LIVE_MODE_CONFIRM_TOKEN,
    SafetyError,
    detect_key_mode,
    guard_live_mode,
    redact_log_line,
    redact_secret,
)


class TestDetectKeyMode:
    def test_test_key(self) -> None:
        assert detect_key_mode("sk_test_DUMMYfixtureKEY01234567") == "test"

    def test_live_key(self) -> None:
        assert detect_key_mode("sk_live_DUMMYfixtureKEY01234567") == "live"

    def test_malformed(self) -> None:
        assert detect_key_mode("not_a_key") == "invalid"

    def test_empty(self) -> None:
        assert detect_key_mode("") == "invalid"

    def test_none_like(self) -> None:
        assert detect_key_mode(None) == "invalid"  # type: ignore[arg-type]

    def test_restricted_key_is_not_test_or_live(self) -> None:
        assert detect_key_mode("rk_test_abc") == "invalid"


class TestGuardLiveMode:
    def test_test_key_passes(self) -> None:
        assert guard_live_mode("sk_test_abc123") == "test"

    def test_live_key_rejected_without_opt_in(self) -> None:
        with pytest.raises(SafetyError) as ei:
            guard_live_mode("sk_live_abc123")
        assert ei.value.code == "E_LIVE_MODE_NOT_ALLOWED"
        assert "allow_live_mode" in ei.value.message

    def test_live_key_rejected_with_opt_in_but_no_token(self) -> None:
        with pytest.raises(SafetyError) as ei:
            guard_live_mode("sk_live_abc123", allow_live_mode=True)
        assert ei.value.code == "E_LIVE_MODE_NOT_ALLOWED"

    def test_live_key_rejected_with_wrong_token(self) -> None:
        with pytest.raises(SafetyError) as ei:
            guard_live_mode(
                "sk_live_abc123",
                allow_live_mode=True,
                live_mode_confirm_token="wrong",
            )
        assert ei.value.code == "E_LIVE_MODE_NOT_ALLOWED"

    def test_live_key_accepted_with_token(self) -> None:
        assert (
            guard_live_mode(
                "sk_live_abc123",
                allow_live_mode=True,
                live_mode_confirm_token=LIVE_MODE_CONFIRM_TOKEN,
            )
            == "live"
        )

    def test_invalid_key(self) -> None:
        with pytest.raises(SafetyError) as ei:
            guard_live_mode("bad")
        assert ei.value.code == "E_INVALID_KEY"


class TestRedact:
    def test_redact_sk_test(self) -> None:
        out = redact_secret("sk_test_DUMMYfixtureKEY01234567")
        assert out.startswith("sk_test_****")
        assert out.endswith("234567")
        assert "DUMMYfixture" not in out

    def test_redact_whsec(self) -> None:
        out = redact_secret("whsec_abc123xyz789longtail")
        assert out.startswith("whsec_****")
        assert out.endswith("ngtail")

    def test_redact_short_string(self) -> None:
        assert redact_secret("short") == "****"

    def test_redact_line_with_multiple_secrets(self) -> None:
        raw = "using sk_test_abc123xyz789 with whsec_secret12345longtail works"
        out = redact_log_line(raw)
        assert "sk_test_abc123xyz789" not in out
        assert "whsec_secret12345longtail" not in out
        assert "sk_test_****" in out
        assert "whsec_****" in out

    def test_redact_line_preserves_non_secret_text(self) -> None:
        raw = "hello world no secrets here"
        assert redact_log_line(raw) == raw
