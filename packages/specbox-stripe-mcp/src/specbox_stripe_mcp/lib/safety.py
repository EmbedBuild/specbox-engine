"""Live-mode guards, secret redaction, key validation.

Centralizes safety-critical logic so tools can't bypass it.
"""

from __future__ import annotations

import re
from typing import Literal

StripeKeyMode = Literal["test", "live", "invalid"]

KEY_PATTERN = re.compile(r"^sk_(test|live)_[A-Za-z0-9]+$")
RESTRICTED_KEY_PATTERN = re.compile(r"^rk_(test|live)_[A-Za-z0-9]+$")
WHSEC_PATTERN = re.compile(r"whsec_[A-Za-z0-9]+")
LIVE_MODE_CONFIRM_TOKEN = "I acknowledge this affects real money"


class SafetyError(Exception):
    """Raised when a safety check fails. Carries a stable error code for tools to surface."""

    def __init__(self, code: str, message: str, remediation: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def detect_key_mode(api_key: str) -> StripeKeyMode:
    """Return 'test', 'live', or 'invalid' based on prefix. No API call."""
    if not isinstance(api_key, str) or not api_key:
        return "invalid"
    match = KEY_PATTERN.match(api_key)
    if match:
        return "test" if match.group(1) == "test" else "live"
    return "invalid"


def guard_live_mode(
    api_key: str,
    *,
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> StripeKeyMode:
    """Validate key mode and enforce live-mode opt-in.

    Returns the detected mode on success. Raises SafetyError otherwise.

    - invalid key  -> E_INVALID_KEY
    - live key without explicit opt-in -> E_LIVE_MODE_NOT_ALLOWED
    - live key with opt-in but wrong token -> E_LIVE_MODE_NOT_ALLOWED
    """
    mode = detect_key_mode(api_key)
    if mode == "invalid":
        raise SafetyError(
            code="E_INVALID_KEY",
            message="Stripe API key is missing or malformed. Expected sk_test_* or sk_live_*.",
        )
    if mode == "live":
        if not allow_live_mode:
            raise SafetyError(
                code="E_LIVE_MODE_NOT_ALLOWED",
                message=(
                    "Live-mode Stripe keys are rejected by default. "
                    "Pass allow_live_mode=True and live_mode_confirm_token to proceed."
                ),
                remediation=(
                    "If you really mean to operate on live data, re-invoke with "
                    'allow_live_mode=true and live_mode_confirm_token="'
                    f'{LIVE_MODE_CONFIRM_TOKEN}".'
                ),
            )
        if live_mode_confirm_token != LIVE_MODE_CONFIRM_TOKEN:
            raise SafetyError(
                code="E_LIVE_MODE_NOT_ALLOWED",
                message=(
                    "live_mode_confirm_token does not match the required literal. "
                    "Refusing to proceed."
                ),
            )
    return mode


def redact_secret(value: str, visible_tail: int = 6) -> str:
    """Redact a Stripe secret, showing only the last N chars of the ID portion.

    Examples:
        redact_secret("sk_test_DUMMYfixtureABCdef") -> "sk_test_****ABCdef"
        redact_secret("whsec_abc123xyz789") -> "whsec_****xyz789"
    """
    if not isinstance(value, str) or len(value) <= visible_tail + 3:
        return "****"
    # Preserve the prefix before the first underscore trio (sk_test_ / sk_live_ / whsec_).
    for prefix in ("sk_test_", "sk_live_", "rk_test_", "rk_live_", "whsec_"):
        if value.startswith(prefix):
            return f"{prefix}****{value[-visible_tail:]}"
    return f"****{value[-visible_tail:]}"


_REDACTION_PATTERNS = [
    re.compile(r"sk_(?:test|live)_[A-Za-z0-9]+"),
    re.compile(r"rk_(?:test|live)_[A-Za-z0-9]+"),
    re.compile(r"whsec_[A-Za-z0-9]+"),
]


def redact_log_line(line: str) -> str:
    """Replace any occurrence of a Stripe secret or webhook secret with a redacted form."""
    out = line
    for pattern in _REDACTION_PATTERNS:
        out = pattern.sub(lambda m: redact_secret(m.group(0)), out)
    return out
