"""PAT validation + secret/value redaction.

Supabase Personal Access Tokens start with `sbp_`. The ref of a Supabase project
is 20 lowercase alphanumeric characters.

Crucial: secret VALUES (the map passed to set_edge_secret) never appear in
logs or evidence — only the NAMES. This is a non-negotiable contract; see
PRD §9 Security.
"""

from __future__ import annotations

import re

PAT_PATTERN = re.compile(r"^sbp_[A-Za-z0-9_-]+$")
PROJECT_REF_PATTERN = re.compile(r"^[a-z0-9]{20}$")
SECRET_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class SafetyError(Exception):
    """Raised when a safety check fails. Carries a stable error code for tools to surface."""

    def __init__(self, code: str, message: str, remediation: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation


def validate_access_token(token: str) -> None:
    """Raise SafetyError with E_INVALID_INPUT if the PAT is malformed."""
    if not isinstance(token, str) or not PAT_PATTERN.match(token):
        raise SafetyError(
            code="E_INVALID_INPUT",
            message="Supabase access token is missing or malformed. Expected sbp_* format.",
            remediation=(
                "Generate a Personal Access Token at "
                "https://supabase.com/dashboard/account/tokens"
            ),
        )


def validate_project_ref(ref: str) -> None:
    """Raise SafetyError with E_INVALID_INPUT if the project ref is malformed."""
    if not isinstance(ref, str) or not PROJECT_REF_PATTERN.match(ref):
        raise SafetyError(
            code="E_INVALID_INPUT",
            message=(
                f"project_ref must be 20 lowercase alphanumeric characters; got {ref!r}."
            ),
            remediation=(
                "Find your project ref in the Supabase dashboard URL: "
                "https://supabase.com/dashboard/project/<ref>"
            ),
        )


def validate_secret_names(names: list[str]) -> None:
    """Raise SafetyError with E_INVALID_INPUT if any name violates UPPER_SNAKE_CASE."""
    invalid = [n for n in names if not isinstance(n, str) or not SECRET_NAME_PATTERN.match(n)]
    if invalid:
        raise SafetyError(
            code="E_INVALID_INPUT",
            message=(
                f"Secret names must match ^[A-Z][A-Z0-9_]*$ (POSIX env var convention). "
                f"Invalid: {invalid}"
            ),
        )


def redact_token(value: str, visible_tail: int = 6) -> str:
    """Redact a PAT, showing only the last N chars.

    Example:
        redact_token("sbp_DummyFixtureToken012345abcDEF") -> "sbp_****abcDEF"
    """
    if not isinstance(value, str) or len(value) <= visible_tail + 4:
        return "****"
    if value.startswith("sbp_"):
        return f"sbp_****{value[-visible_tail:]}"
    return f"****{value[-visible_tail:]}"


_REDACTION_PATTERNS = [
    re.compile(r"sbp_[A-Za-z0-9_-]+"),
]


def redact_log_line(line: str) -> str:
    """Replace any occurrence of a Supabase PAT with a redacted form."""
    out = line
    for pattern in _REDACTION_PATTERNS:
        out = pattern.sub(lambda m: redact_token(m.group(0)), out)
    return out
