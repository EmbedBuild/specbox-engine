"""T4 — get_setup_status.

Read-only health check answering: "Is the Stripe setup for this project complete?"

Combines:
- verify_connect_enabled (with skip_canary=True to avoid mutating state)
- webhook endpoint inventory (platform + connect, events alignment)
- product/price inventory by tier_key

NEVER creates, modifies, or deletes a Stripe resource. Safe to call repeatedly.

Verdicts:
- "ready"     — all checks pass
- "partial"   — Connect enabled, but some webhooks/products missing or misaligned
- "not_setup" — Connect not enabled
"""

from __future__ import annotations

import logging
import time
from typing import Any

import stripe

from ..lib.heartbeat import report_heartbeat
from ..lib.idempotency import is_specbox_managed
from ..lib.response import err, ok
from ..lib.safety import SafetyError, guard_live_mode
from ..lib.stripe_client import StripeClient

logger = logging.getLogger("specbox_stripe_mcp.tools.get_setup_status")

TOOL_NAME = "get_setup_status"


def get_setup_status(
    *,
    stripe_api_key: str,
    expected_webhook_url: str | None = None,
    expected_tier_keys: list[str] | None = None,
    expected_currency: str = "eur",
    expected_platform_events: list[str] | None = None,
    expected_connect_events: list[str] | None = None,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict[str, Any]:
    """Inspect Stripe and return a pass/partial/not_setup verdict plus per-check details."""
    started = time.monotonic()
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

    # --- Connect check: we infer from capabilities rather than mutate via canary ---
    try:
        account = client.call(
            "accounts.retrieve", lambda: stripe.Account.retrieve()
        )
    except stripe.error.AuthenticationError as exc:  # type: ignore[attr-defined]
        _emit_heartbeat(
            project=project_hint, success=False,
            duration_ms=(time.monotonic() - started) * 1000, mode=mode,
            code="E_INVALID_KEY",
        )
        return err(code="E_INVALID_KEY", message=str(exc))
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        _emit_heartbeat(
            project=project_hint, success=False,
            duration_ms=(time.monotonic() - started) * 1000, mode=mode,
            code="E_STRIPE_ERROR",
        )
        return err(code="E_STRIPE_ERROR", message=f"account.retrieve: {exc}")

    caps = dict(account.get("capabilities") or {})
    connect_enabled = _infer_connect_enabled(account, caps)

    checks: dict[str, Any] = {
        "connect_enabled": connect_enabled,
        "platform_webhook_endpoint": {"present": False, "id": None, "events_ok": False},
        "connect_webhook_endpoint": {"present": False, "id": None, "events_ok": False},
        "products_found": [],
        "products_missing": [],
        "prices_found": {},
        "prices_missing": [],
    }
    remediation_steps: list[str] = []

    # --- Webhook checks ---
    if expected_webhook_url:
        try:
            listing = client.call(
                "webhook_endpoints.list",
                lambda: stripe.WebhookEndpoint.list(limit=100),
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            return err(code="E_STRIPE_ERROR", message=f"webhook_endpoints.list: {exc}")
        webhooks = list(listing.get("data") or [])
        plat = _pick_webhook(
            webhooks, url=expected_webhook_url, connect=False, expected_events=expected_platform_events,
        )
        conn = _pick_webhook(
            webhooks, url=expected_webhook_url, connect=True, expected_events=expected_connect_events,
        )
        checks["platform_webhook_endpoint"] = plat
        checks["connect_webhook_endpoint"] = conn
        if not plat["present"]:
            remediation_steps.append(
                "Run setup_webhook_endpoints to create the missing platform webhook."
            )
        elif not plat["events_ok"]:
            remediation_steps.append(
                f"Platform webhook missing events: {plat.get('missing_events', [])}"
            )
        if not conn["present"]:
            remediation_steps.append(
                "Run setup_webhook_endpoints to create the missing connect webhook."
            )
        elif not conn["events_ok"]:
            remediation_steps.append(
                f"Connect webhook missing events: {conn.get('missing_events', [])}"
            )

    # --- Product/Price checks ---
    if expected_tier_keys:
        try:
            products_listing = client.call(
                "products.list",
                lambda: stripe.Product.list(limit=100, active=True),
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            return err(code="E_STRIPE_ERROR", message=f"products.list: {exc}")
        products = [
            p for p in (products_listing.get("data") or [])
            if is_specbox_managed(p.get("metadata"))
        ]
        tier_to_product = {
            str(p.get("metadata", {}).get("tier_key", "")): p
            for p in products
            if p.get("metadata", {}).get("tier_key")
        }
        for tier in expected_tier_keys:
            if tier in tier_to_product:
                checks["products_found"].append(tier)
            else:
                checks["products_missing"].append(tier)

        for tier in checks["products_found"]:
            product = tier_to_product[tier]
            try:
                price_listing = client.call(
                    "prices.list",
                    lambda pid=product["id"]: stripe.Price.list(
                        product=pid, active=True, limit=50
                    ),
                )
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                logger.warning("prices.list failed for %s: %s", product.get("id"), exc)
                continue
            managed_prices = [
                pr for pr in (price_listing.get("data") or [])
                if is_specbox_managed(pr.get("metadata"))
                and str(pr.get("currency", "")).lower() == expected_currency.lower()
            ]
            if managed_prices:
                checks["prices_found"][tier] = managed_prices[0].get("id", "")
            else:
                checks["prices_missing"].append(tier)

        if checks["products_missing"] or checks["prices_missing"]:
            remediation_steps.append(
                "Run setup_products_and_prices with the full tier catalog to backfill."
            )

    # --- Verdict ---
    verdict, summary = _compute_verdict(
        connect_enabled=connect_enabled,
        checks=checks,
        expected_webhook_url=expected_webhook_url,
        expected_tier_keys=expected_tier_keys,
    )
    if verdict == "not_setup" and not connect_enabled:
        remediation_steps.insert(
            0,
            _dashboard_hint(mode),
        )

    duration_ms = (time.monotonic() - started) * 1000
    _emit_heartbeat(
        project=project_hint, success=True, duration_ms=duration_ms, mode=mode,
        code="OK",
    )
    return ok(
        {
            "verdict": verdict,
            "checks": checks,
            "summary": summary,
            "remediation_steps": remediation_steps,
            "mode": mode,
            "platform_account_id": account.get("id", ""),
        }
    )


def _infer_connect_enabled(account: dict[str, Any], caps: dict[str, Any]) -> bool:
    # If Connect is active, the platform account reports platform-specific properties:
    # - settings.platform_payments with charges_enabled
    # - capabilities listing platform payments
    # We use a permissive heuristic: any capability present OR settings.platform.* indicates Connect.
    if caps:
        return True
    settings = account.get("settings") or {}
    if "platform_payments" in settings or "dashboard" in settings:
        return True
    charges = account.get("charges_enabled")
    return bool(charges)


def _pick_webhook(
    webhooks: list[dict[str, Any]],
    *,
    url: str,
    connect: bool,
    expected_events: list[str] | None,
) -> dict[str, Any]:
    for endpoint in webhooks:
        if endpoint.get("url") != url:
            continue
        endpoint_connect = bool(endpoint.get("connect") or endpoint.get("application"))
        if endpoint_connect != connect:
            continue
        enabled_events = list(endpoint.get("enabled_events") or [])
        events_ok = True
        missing_events: list[str] = []
        if expected_events is not None:
            expected_set = set(expected_events)
            actual_set = set(enabled_events)
            missing_events = sorted(expected_set - actual_set)
            events_ok = not missing_events
        return {
            "present": True,
            "id": endpoint.get("id", ""),
            "url": url,
            "enabled_events": enabled_events,
            "events_ok": events_ok,
            "missing_events": missing_events,
            "connect": connect,
        }
    return {
        "present": False,
        "id": None,
        "events_ok": False,
        "missing_events": list(expected_events or []),
        "connect": connect,
    }


def _compute_verdict(
    *,
    connect_enabled: bool,
    checks: dict[str, Any],
    expected_webhook_url: str | None,
    expected_tier_keys: list[str] | None,
) -> tuple[str, str]:
    total_checks = 1  # connect always counted
    passed = 1 if connect_enabled else 0

    if expected_webhook_url:
        total_checks += 2
        if checks["platform_webhook_endpoint"]["present"] and checks["platform_webhook_endpoint"]["events_ok"]:
            passed += 1
        if checks["connect_webhook_endpoint"]["present"] and checks["connect_webhook_endpoint"]["events_ok"]:
            passed += 1
    if expected_tier_keys:
        total_checks += len(expected_tier_keys)
        passed += len(checks["products_found"]) - len([
            t for t in checks["products_found"]
            if t not in checks["prices_found"]
        ])

    if not connect_enabled:
        return "not_setup", "Stripe Connect is not activated. Enable it in the dashboard before continuing."
    if passed == total_checks:
        return "ready", f"{passed}/{total_checks} checks pass. Ready to continue."
    return (
        "partial",
        f"{passed}/{total_checks} checks pass. See remediation_steps for the missing items.",
    )


def _dashboard_hint(mode: str) -> str:
    base = (
        "https://dashboard.stripe.com/test/connect/overview"
        if mode == "test"
        else "https://dashboard.stripe.com/connect/overview"
    )
    return f"Activate Connect at {base}"


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
                "idempotency_hit": True,  # read-only: always a "hit"
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
