"""T1 — verify_connect_enabled.

Gate-of-entry tool for all SpecBox Stripe skills. Answers:
"Can I create Connect Express accounts on this platform?"

Behavior (PRD §5, T1):
1. GET /v1/accounts/{platform_id} — reads the platform account (id implicit in key).
2. Canary: POST /v1/accounts type=express country=ES capabilities={card_payments,transfers}
   with metadata.specbox_probe=true.
3. If canary succeeds → DELETE /v1/accounts/{id} immediately, return enabled:true.
4. If canary fails with platform_not_active-ish error → return enabled:false with
   remediation pointing to the Connect dashboard.

No persistent side-effects on success path (canary account is deleted).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import stripe

from ..lib.engram_writer import format_config_content, write_config_observation
from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok
from ..lib.safety import SafetyError, guard_live_mode
from ..lib.stripe_client import StripeClient

logger = logging.getLogger("specbox_stripe_mcp.tools.verify_connect_enabled")

TOOL_NAME = "verify_connect_enabled"
CANARY_COUNTRY = "ES"
CANARY_METADATA = {"specbox_probe": "true", "specbox_managed": "probe"}

# Stripe error codes / messages that indicate Connect is not activated on this account.
CONNECT_DISABLED_MARKERS = (
    "platform_not_active",
    "platform not activated",
    "not enabled connect",
    "connect is not enabled",
    "has not activated connect",
    "please activate connect",
    "activate your connect",
)
# Stripe error codes that indicate the key lacks permission for accounts.* even though Connect exists.
INSUFFICIENT_PERMISSIONS_MARKERS = (
    "permission",
    "not authorized",
    "insufficient",
)


def _classify_connect_error(exc: stripe.error.StripeError) -> str:  # type: ignore[attr-defined]
    """Classify a StripeError from the canary into one of the stable tool error codes."""
    text = (str(exc) or "").lower()
    code = getattr(exc, "code", "") or ""
    if isinstance(exc, stripe.error.AuthenticationError):  # type: ignore[attr-defined]
        return "E_INVALID_KEY"
    if isinstance(exc, stripe.error.PermissionError):  # type: ignore[attr-defined]
        # Could be Connect disabled OR restricted key. Distinguish by marker.
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


def verify_connect_enabled(
    *,
    stripe_api_key: str,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
    skip_canary: bool = False,
) -> dict[str, Any]:
    """Verify whether Stripe Connect is enabled for the platform account behind this key.

    Args:
        stripe_api_key: sk_test_* or sk_live_*. Required.
        project_hint: Free-form tag for evidence and telemetry (e.g. "motofan").
        allow_live_mode: Must be True to pass a sk_live_* key (plus confirm token).
        live_mode_confirm_token: Literal string required in live mode.
        skip_canary: If True, does not attempt POST /v1/accounts. Useful when the platform
            rate-limits canaries. The tool then reports enabled:true if account retrieval
            succeeds, with a warning that Connect capability is inferred, not verified.

    Returns:
        Standard response envelope. See module docstring for details.
    """
    started = time.monotonic()
    # --- Safety gate: key mode ---
    try:
        mode = guard_live_mode(
            stripe_api_key,
            allow_live_mode=allow_live_mode,
            live_mode_confirm_token=live_mode_confirm_token,
        )
    except SafetyError as safety_exc:
        _emit_heartbeat(
            project=project_hint,
            success=False,
            duration_ms=(time.monotonic() - started) * 1000,
            mode="invalid" if safety_exc.code == "E_INVALID_KEY" else "live",
            code=safety_exc.code,
        )
        return err(
            code=safety_exc.code,
            message=safety_exc.message,
            remediation=safety_exc.remediation,
        )

    client = StripeClient(api_key=stripe_api_key)

    # --- Step 1: read platform account ---
    try:
        account = client.call("accounts.retrieve", lambda: stripe.Account.retrieve())
    except stripe.error.AuthenticationError as exc:  # type: ignore[attr-defined]
        duration_ms = (time.monotonic() - started) * 1000
        _emit_heartbeat(
            project=project_hint, success=False, duration_ms=duration_ms, mode=mode,
            code="E_INVALID_KEY",
        )
        return err(
            code="E_INVALID_KEY",
            message=f"Stripe rejected the API key: {exc}",
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        duration_ms = (time.monotonic() - started) * 1000
        _emit_heartbeat(
            project=project_hint, success=False, duration_ms=duration_ms, mode=mode,
            code="E_STRIPE_ERROR",
        )
        return err(
            code="E_STRIPE_ERROR",
            message=f"Failed to read platform account: {exc}",
        )

    platform_info = _extract_platform_info(account, mode=mode)

    warnings: list[str] = []

    # --- Step 2: canary (optional) ---
    if skip_canary:
        warnings.append(
            "skip_canary=true: Connect enablement is inferred, not verified."
        )
        enabled = True
    else:
        enabled, canary_error = _run_canary(client)
        if canary_error is not None:
            duration_ms = (time.monotonic() - started) * 1000
            dashboard_url = _dashboard_url_for_mode(mode)
            _emit_heartbeat(
                project=project_hint,
                success=False,
                duration_ms=duration_ms,
                mode=mode,
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
    evidence = {}
    try:
        obs_id = write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: {TOOL_NAME} on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode=mode,
                result_summary=f"enabled={enabled}",
                duration_ms=duration_ms,
                extra={
                    "skip_canary": str(skip_canary),
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
        mode=mode,
        code="OK",
    )

    return ok(data, warnings=warnings or None, evidence=evidence or None)


def _extract_platform_info(account: Any, *, mode: str) -> dict[str, Any]:
    """Shape the relevant subset of Stripe Account into the contract fields."""
    caps_dict = {}
    try:
        caps_dict = dict(account.get("capabilities", {}) or {})
    except Exception:
        caps_dict = {}
    capabilities_available = sorted(caps_dict.keys())
    display_name = (
        account.get("business_profile", {}).get("name")
        or account.get("settings", {}).get("dashboard", {}).get("display_name")
        or account.get("email")
        or ""
    )
    return {
        "platform_account_id": account.get("id", ""),
        "display_name": display_name,
        "country": account.get("country", ""),
        "default_currency": account.get("default_currency", ""),
        "capabilities_available": capabilities_available,
        "mode": mode,
    }


def _run_canary(client: StripeClient) -> tuple[bool, str | None]:
    """Attempt to create+delete a probe Express account.

    Returns (enabled, error_code). If enabled, error_code is None. If not enabled,
    enabled=False and error_code is one of E_CONNECT_NOT_ENABLED /
    E_INSUFFICIENT_PERMISSIONS / E_STRIPE_ERROR.
    """
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

    probe_id = probe.get("id", "")
    if not probe_id:
        return False, "E_STRIPE_ERROR"

    # Best-effort cleanup. If delete fails we still return enabled=True but emit a warning
    # via log; leaving a probe-tagged residue is acceptable (metadata identifies it).
    try:
        client.call(
            "accounts.delete",
            lambda pid=probe_id: stripe.Account.delete(pid),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        logger.warning("canary cleanup failed for %s: %s", probe_id, exc)

    return True, None


def _dashboard_url_for_mode(mode: str) -> str:
    return (
        "https://dashboard.stripe.com/test/connect/overview"
        if mode == "test"
        else "https://dashboard.stripe.com/connect/overview"
    )


def _emit_heartbeat(
    *,
    project: str,
    success: bool,
    duration_ms: float,
    mode: str,
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
                "mode": mode,
                "code": code,
                "idempotency_hit": False,
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
