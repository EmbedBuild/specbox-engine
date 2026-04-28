"""T1 — verify_account_setup (v0.2).

Generalized gate-of-entry tool for SpecBox Stripe skills. Answers:
"Can I use this Stripe account in <account_mode> mode?"

account_mode='standard' (SaaS, e-commerce, B2B):
1. GET /v1/account — confirms the key works and returns capabilities.
2. No canary, no Connect probe. The account does not need Connect activated.
3. Returns enabled:true unless the key itself is invalid or restricted.

account_mode='connect' (marketplace platforms):
1. GET /v1/account — reads the platform account.
2. Canary: POST /v1/accounts type=express + DELETE on success.
3. Mirrors v0.1 verify_connect_enabled behavior.

Backward-compat: tools/verify_connect_enabled.py is a deprecated alias that
calls this with account_mode='connect'.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

import stripe

from ..lib.engram_writer import format_config_content, write_config_observation
from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok
from ..lib.safety import SafetyError, guard_live_mode
from ..lib.stripe_client import StripeClient
from ..lib.stripe_utils import as_dict

logger = logging.getLogger("specbox_stripe_mcp.tools.verify_account_setup")

TOOL_NAME = "verify_account_setup"
CANARY_COUNTRY = "ES"
CANARY_METADATA = {"specbox_probe": "true", "specbox_managed": "probe"}

AccountMode = Literal["standard", "connect"]
VALID_MODES: tuple[str, ...] = ("standard", "connect")

# Stripe error markers reused from v0.1 verify_connect_enabled. Connect-only paths.
CONNECT_DISABLED_MARKERS = (
    "platform_not_active",
    "platform not activated",
    "not enabled connect",
    "connect is not enabled",
    "has not activated connect",
    "please activate connect",
    "activate your connect",
)
INSUFFICIENT_PERMISSIONS_MARKERS = (
    "permission",
    "not authorized",
    "insufficient",
)


def _classify_connect_error(exc: stripe.error.StripeError) -> str:  # type: ignore[attr-defined]
    """Classify a StripeError from the canary into a stable tool error code."""
    text = (str(exc) or "").lower()
    code = getattr(exc, "code", "") or ""
    if isinstance(exc, stripe.error.AuthenticationError):  # type: ignore[attr-defined]
        return "E_INVALID_KEY"
    if isinstance(exc, stripe.error.PermissionError):  # type: ignore[attr-defined]
        if any(marker in text for marker in CONNECT_DISABLED_MARKERS):
            return "E_CONNECT_NOT_ENABLED"
        if any(marker in text for marker in INSUFFICIENT_PERMISSIONS_MARKERS):
            return "E_INSUFFICIENT_PERMISSIONS"
        return "E_CONNECT_NOT_ENABLED"
    if isinstance(exc, stripe.error.InvalidRequestError):  # type: ignore[attr-defined]
        if any(marker in text for marker in CONNECT_DISABLED_MARKERS):
            return "E_CONNECT_NOT_ENABLED"
        if code in ("platform_not_active", "account_connect_not_enabled"):
            return "E_CONNECT_NOT_ENABLED"
    return "E_STRIPE_ERROR"


def _classify_retrieve_error(exc: stripe.error.StripeError) -> str:  # type: ignore[attr-defined]
    """Classify GET /v1/account errors. Restricted keys surface as E_INSUFFICIENT_PERMISSIONS."""
    text = (str(exc) or "").lower()
    if isinstance(exc, stripe.error.AuthenticationError):  # type: ignore[attr-defined]
        return "E_INVALID_KEY"
    if isinstance(exc, stripe.error.PermissionError):  # type: ignore[attr-defined]
        return "E_INSUFFICIENT_PERMISSIONS"
    if any(marker in text for marker in INSUFFICIENT_PERMISSIONS_MARKERS):
        return "E_INSUFFICIENT_PERMISSIONS"
    return "E_STRIPE_ERROR"


def verify_account_setup(
    *,
    stripe_api_key: str,
    account_mode: AccountMode,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
    skip_canary: bool = False,
) -> dict[str, Any]:
    """Verify a Stripe account is usable in the requested mode.

    Args:
        stripe_api_key: sk_test_* or sk_live_*. Required.
        account_mode: "standard" (any Stripe account) or "connect" (marketplace
            platform with Connect activated). Required.
        project_hint: Free-form tag for evidence and telemetry.
        allow_live_mode: Must be True to pass a sk_live_* key (plus confirm token).
        live_mode_confirm_token: Literal string required in live mode.
        skip_canary: connect-mode only — skip the canary probe and infer enablement
            from account retrieval. Ignored in standard mode.

    Returns:
        Standard envelope. data includes: enabled, platform_account_id, display_name,
        country, default_currency, capabilities_available, mode (test/live),
        account_mode (standard/connect).
    """
    started = time.monotonic()

    # --- Argument validation ---
    if account_mode not in VALID_MODES:
        return err(
            code="E_INVALID_ARGUMENT",
            message=(
                f"account_mode must be one of {list(VALID_MODES)}; got "
                f"{account_mode!r}."
            ),
            remediation="Pass account_mode='standard' for normal accounts or 'connect' for marketplace platforms.",
        )

    # --- Safety gate: key mode ---
    try:
        key_mode = guard_live_mode(
            stripe_api_key,
            allow_live_mode=allow_live_mode,
            live_mode_confirm_token=live_mode_confirm_token,
        )
    except SafetyError as safety_exc:
        _emit_heartbeat(
            project=project_hint,
            success=False,
            duration_ms=(time.monotonic() - started) * 1000,
            key_mode="invalid" if safety_exc.code == "E_INVALID_KEY" else "live",
            account_mode=account_mode,
            code=safety_exc.code,
        )
        return err(
            code=safety_exc.code,
            message=safety_exc.message,
            remediation=safety_exc.remediation,
        )

    client = StripeClient(api_key=stripe_api_key)

    # --- Step 1: read platform/account info (both modes) ---
    try:
        account = client.call("accounts.retrieve", lambda: stripe.Account.retrieve())
    except stripe.error.AuthenticationError as exc:  # type: ignore[attr-defined]
        duration_ms = (time.monotonic() - started) * 1000
        _emit_heartbeat(
            project=project_hint,
            success=False,
            duration_ms=duration_ms,
            key_mode=key_mode,
            account_mode=account_mode,
            code="E_INVALID_KEY",
        )
        return err(
            code="E_INVALID_KEY",
            message=f"Stripe rejected the API key: {exc}",
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        duration_ms = (time.monotonic() - started) * 1000
        retrieve_error = _classify_retrieve_error(exc)
        _emit_heartbeat(
            project=project_hint,
            success=False,
            duration_ms=duration_ms,
            key_mode=key_mode,
            account_mode=account_mode,
            code=retrieve_error,
        )
        if retrieve_error == "E_INSUFFICIENT_PERMISSIONS":
            return err(
                code="E_INSUFFICIENT_PERMISSIONS",
                message=(
                    "The provided Stripe key cannot read GET /v1/account. "
                    "This usually means a restricted key without 'Account read' permission."
                ),
                remediation=(
                    "Use a standard secret key (sk_test_* / sk_live_*), or "
                    "grant 'Account read' permission to your restricted key."
                ),
            )
        return err(
            code=retrieve_error,
            message=f"Failed to read account: {exc}",
        )

    platform_info = _extract_platform_info(
        account, key_mode=key_mode, account_mode=account_mode
    )

    warnings: list[str] = []

    # --- Step 2: mode-specific verification ---
    if account_mode == "standard":
        # Standard mode: account retrieval already proves the key is usable.
        # No canary, no Connect probe. enabled=True.
        enabled = True
    else:
        # Connect mode: canary unless explicitly skipped.
        if skip_canary:
            warnings.append(
                "skip_canary=true: Connect enablement is inferred, not verified."
            )
            enabled = True
        else:
            enabled, canary_error = _run_canary(client)
            if canary_error is not None:
                duration_ms = (time.monotonic() - started) * 1000
                dashboard_url = _dashboard_url_for_key_mode(key_mode)
                _emit_heartbeat(
                    project=project_hint,
                    success=False,
                    duration_ms=duration_ms,
                    key_mode=key_mode,
                    account_mode=account_mode,
                    code=canary_error,
                )
                if canary_error == "E_CONNECT_NOT_ENABLED":
                    return {
                        "success": True,
                        "data": {
                            "enabled": False,
                            **platform_info,
                        },
                        "error": {
                            "code": "E_CONNECT_NOT_ENABLED",
                            "message": (
                                "Stripe Connect is not activated for this platform account. "
                                "Enable it once in the dashboard."
                            ),
                            "remediation": f"Activate Connect at {dashboard_url}",
                        },
                    }
                if canary_error == "E_INSUFFICIENT_PERMISSIONS":
                    return err(
                        code="E_INSUFFICIENT_PERMISSIONS",
                        message=(
                            "The provided Stripe key lacks permission for /v1/accounts. "
                            "Use a standard secret key (sk_test_* / sk_live_*), not a restricted key."
                        ),
                    )
                return err(
                    code=canary_error,
                    message="Unexpected Stripe error during Connect canary.",
                )

    duration_ms = (time.monotonic() - started) * 1000
    data = {"enabled": enabled, **platform_info}

    # --- Step 3: evidence + telemetry ---
    evidence: dict[str, Any] = {}
    try:
        obs_id = write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: {TOOL_NAME} on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode=key_mode,
                result_summary=f"enabled={enabled} account_mode={account_mode}",
                duration_ms=duration_ms,
                extra={
                    "skip_canary": str(skip_canary),
                    "account_mode": account_mode,
                    "platform_account_id": platform_info.get("platform_account_id", ""),
                },
            ),
        )
        if obs_id:
            evidence["engram_observation_id"] = obs_id
    except Exception as exc:
        logger.debug("engram write skipped: %s", exc)

    _emit_heartbeat(
        project=project_hint,
        success=True,
        duration_ms=duration_ms,
        key_mode=key_mode,
        account_mode=account_mode,
        code="OK",
    )

    return ok(data, warnings=warnings or None, evidence=evidence or None)


def _extract_platform_info(
    account: Any, *, key_mode: str, account_mode: str
) -> dict[str, Any]:
    """Shape the relevant subset of Stripe Account into the contract fields."""
    acct = as_dict(account)

    caps_dict = acct.get("capabilities") or {}
    if not isinstance(caps_dict, dict):
        caps_dict = {}
    capabilities_available = sorted(caps_dict.keys())

    business_profile = acct.get("business_profile") or {}
    settings = acct.get("settings") or {}
    dashboard = settings.get("dashboard") if isinstance(settings, dict) else {}
    dashboard = dashboard or {}

    display_name = (
        (business_profile.get("name") if isinstance(business_profile, dict) else None)
        or (dashboard.get("display_name") if isinstance(dashboard, dict) else None)
        or acct.get("email")
        or ""
    )
    return {
        "platform_account_id": acct.get("id", ""),
        "display_name": display_name,
        "country": acct.get("country", ""),
        "default_currency": acct.get("default_currency", ""),
        "capabilities_available": capabilities_available,
        "mode": key_mode,
        "account_mode": account_mode,
    }


def _run_canary(client: StripeClient) -> tuple[bool, str | None]:
    """Attempt to create+delete a probe Express account (connect mode only)."""
    try:
        probe = client.call(
            "accounts.create",
            lambda: stripe.Account.create(
                type="express",
                country=CANARY_COUNTRY,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                metadata=CANARY_METADATA,
            ),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return False, _classify_connect_error(exc)

    probe_id = as_dict(probe).get("id", "")
    if not probe_id:
        return False, "E_STRIPE_ERROR"

    try:
        client.call(
            "accounts.delete",
            lambda pid=probe_id: stripe.Account.delete(pid),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        logger.warning("canary cleanup failed for %s: %s", probe_id, exc)

    return True, None


def _dashboard_url_for_key_mode(key_mode: str) -> str:
    return (
        "https://dashboard.stripe.com/test/connect/overview"
        if key_mode == "test"
        else "https://dashboard.stripe.com/connect/overview"
    )


def _emit_heartbeat(
    *,
    project: str,
    success: bool,
    duration_ms: float,
    key_mode: str,
    account_mode: str,
    code: str,
) -> None:
    try:
        report_heartbeat(
            project=project,
            event_type="stripe_mcp_call",
            payload={
                "tool": TOOL_NAME,
                "success": success,
                "duration_ms": round(duration_ms, 2),
                "mode": key_mode,
                "account_mode": account_mode,
                "code": code,
                "idempotency_hit": False,
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
