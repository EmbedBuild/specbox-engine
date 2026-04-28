"""T1 — verify_connect_enabled (DEPRECATED in v0.2).

This module is preserved as a backward-compatibility shim. New callers should
use `verify_account_setup(account_mode='connect')` from
`tools.verify_account_setup` instead.

The shim emits a DeprecationWarning on every call. It will be removed in v0.3.
"""

from __future__ import annotations

import warnings
from typing import Any

from .verify_account_setup import verify_account_setup

TOOL_NAME = "verify_connect_enabled"  # kept for telemetry compatibility


def verify_connect_enabled(
    *,
    stripe_api_key: str,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
    skip_canary: bool = False,
) -> dict[str, Any]:
    """Deprecated alias for verify_account_setup(account_mode='connect').

    Use verify_account_setup directly in new code. The argument list and return
    shape are forwarded unchanged when account_mode='connect' is used.
    """
    warnings.warn(
        "verify_connect_enabled is deprecated and will be removed in v0.3. "
        "Use verify_account_setup(account_mode='connect') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return verify_account_setup(
        stripe_api_key=stripe_api_key,
        account_mode="connect",
        project_hint=project_hint,
        allow_live_mode=allow_live_mode,
        live_mode_confirm_token=live_mode_confirm_token,
        skip_canary=skip_canary,
    )
