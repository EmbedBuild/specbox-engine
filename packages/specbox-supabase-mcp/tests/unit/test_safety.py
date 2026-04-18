"""Tests for lib/safety.py (UC-SB-4 transversal)."""

from __future__ import annotations

import pytest

from specbox_supabase_mcp.lib.safety import (
    SafetyError,
    redact_log_line,
    redact_token,
    validate_access_token,
    validate_project_ref,
    validate_secret_names,
)


class TestValidateAccessToken:
    def test_valid_pat_passes(self) -> None:
        validate_access_token("sbp_" + "DummyFixtureToken012345abcDEF")

    def test_missing_prefix_rejected(self) -> None:
        with pytest.raises(SafetyError) as ei:
            validate_access_token("pat_" + "withoutSbpPrefix")
        assert ei.value.code == "E_INVALID_INPUT"

    def test_empty_rejected(self) -> None:
        with pytest.raises(SafetyError):
            validate_access_token("")

    def test_non_string_rejected(self) -> None:
        with pytest.raises(SafetyError):
            validate_access_token(None)  # type: ignore[arg-type]


class TestValidateProjectRef:
    def test_valid_ref(self) -> None:
        validate_project_ref("abcdefghij0123456789")  # exactly 20 chars

    def test_too_short(self) -> None:
        with pytest.raises(SafetyError):
            validate_project_ref("tooshort")

    def test_uppercase_rejected(self) -> None:
        with pytest.raises(SafetyError):
            validate_project_ref("ABCDEFGHIJKLMNOPQRST")

    def test_hyphens_rejected(self) -> None:
        with pytest.raises(SafetyError):
            validate_project_ref("abc-def-ghij01234567")


class TestValidateSecretNames:
    def test_valid_names(self) -> None:
        validate_secret_names(["FOO", "BAR_BAZ", "MY_SECRET_42"])

    def test_lowercase_rejected(self) -> None:
        with pytest.raises(SafetyError) as ei:
            validate_secret_names(["lowercase"])
        assert "invalid" in ei.value.message.lower() or "match" in ei.value.message.lower()

    def test_starts_with_digit_rejected(self) -> None:
        with pytest.raises(SafetyError):
            validate_secret_names(["1_STARTS_DIGIT"])

    def test_spaces_rejected(self) -> None:
        with pytest.raises(SafetyError):
            validate_secret_names(["HAS SPACE"])


class TestRedaction:
    def test_redact_pat(self) -> None:
        out = redact_token("sbp_" + "FullDummyTokenContents98765")
        assert out.startswith("sbp_****")
        assert out.endswith("ts98765"[-6:])

    def test_redact_short_string(self) -> None:
        assert redact_token("sbp_x") == "****"

    def test_redact_log_line_with_pat(self) -> None:
        raw = "connecting with sbp_" + "DummyPATContents9988771234 worked"
        out = redact_log_line(raw)
        assert "DummyPATContents" not in out
        assert "sbp_****" in out

    def test_redact_line_no_secret_unchanged(self) -> None:
        raw = "normal log line, no secrets"
        assert redact_log_line(raw) == raw
