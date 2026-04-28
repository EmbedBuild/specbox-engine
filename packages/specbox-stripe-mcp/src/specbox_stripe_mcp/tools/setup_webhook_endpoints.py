"""T2 — setup_webhook_endpoints (v0.2).

Creates (or idempotently reuses) the SpecBox-managed webhook endpoints for the
requested account_mode, and returns their signing secrets.

account_mode='standard': 1 endpoint (platform-scope only). Stripe Standard
accounts cannot subscribe to Connect events. data.connect is omitted from the
response. Passing connect_events or connect_url is rejected as a misuse.

account_mode='connect': 2 endpoints (platform + connect). Mirrors v0.1 behavior
exactly. connect_events is required.

Key design decisions:
- Idempotency: metadata.specbox_managed='true' + url + connect-flag +
  account_mode. Cross-mode collisions are prevented by including account_mode in
  the lookup. v0.1 endpoints (without specbox_account_mode) are silently
  migrated on first reuse — see _annotate_account_mode.
- Secret recovery: Stripe only returns the signing secret on CREATE. On REUSE
  we must fetch it with expand=['secret'].
- Concurrency: POST uses a deterministic Idempotency-Key so two concurrent
  invocations from the same caller intent collapse into one Stripe object.
- api_version defaults to '2024-11-20.acacia' but is overridable per-call.
- Errors: E_INVALID_URL (non-HTTPS), E_INVALID_ARGUMENT (mode/args mismatch),
  E_MISSING_ARGUMENT (missing required-by-mode arg), E_UNKNOWN_EVENT_TYPE
  (Stripe rejects event name), E_LIMIT_REACHED (>16 webhooks/account cap).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Literal

import stripe

from ..lib.engram_writer import format_config_content, write_config_observation
from ..lib.heartbeat import report_heartbeat
from ..lib.idempotency import (
    base_metadata,
    is_specbox_managed,
    stable_idempotency_key,
)
from ..lib.response import err, ok
from ..lib.safety import SafetyError, guard_live_mode
from ..lib.stripe_client import DEFAULT_API_VERSION, StripeClient
from ..lib.stripe_utils import as_dict, as_dict_list

logger = logging.getLogger("specbox_stripe_mcp.tools.setup_webhook_endpoints")

TOOL_NAME = "setup_webhook_endpoints"
HTTPS_URL = re.compile(r"^https://", re.IGNORECASE)

AccountMode = Literal["standard", "connect"]
VALID_MODES: tuple[str, ...] = ("standard", "connect")
SPECBOX_ACCOUNT_MODE_KEY = "specbox_account_mode"


def setup_webhook_endpoints(
    *,
    stripe_api_key: str,
    account_mode: AccountMode,
    platform_url: str,
    platform_events: list[str],
    connect_events: list[str] | None = None,
    connect_url: str | None = None,
    api_version: str | None = None,
    project_hint: str = "unknown",
    description_prefix: str | None = None,
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict[str, Any]:
    """Ensure the SpecBox-managed webhook endpoints exist for the requested mode.

    Args:
        stripe_api_key: sk_test_* or sk_live_*.
        account_mode: 'standard' (1 endpoint, platform-scope) or 'connect'
            (2 endpoints, platform + connect-scope). Required.
        platform_url: HTTPS URL receiving platform-scope events.
        platform_events: list of event types (e.g. ['account.updated']).
        connect_events: list of event types for connect-scope events.
            Required in account_mode='connect'. Rejected in 'standard'.
        connect_url: defaults to platform_url (dual-secret, single-endpoint
            pattern). Rejected in account_mode='standard'.
        api_version: Stripe API version to pin this endpoint to.
        project_hint: free-form tag for metadata + evidence.
        description_prefix: free text prefixing the Stripe description field.
        allow_live_mode / live_mode_confirm_token: live-mode opt-in.

    Returns:
        Standard envelope. In 'connect' mode: data={platform, connect}. In
        'standard' mode: data={platform} (no connect key). Each entry has
        id, url, secret, events, status, connect (bool), and created_or_reused.
    """
    started = time.monotonic()

    # --- Argument validation: account_mode ---
    if account_mode not in VALID_MODES:
        return err(
            code="E_INVALID_ARGUMENT",
            message=(
                f"account_mode must be one of {list(VALID_MODES)}; got "
                f"{account_mode!r}."
            ),
            remediation="Pass account_mode='standard' or 'connect'.",
        )

    # --- Argument validation: mode-specific args ---
    if account_mode == "standard":
        if connect_events is not None:
            return err(
                code="E_INVALID_ARGUMENT",
                message=(
                    "connect_events is only valid in account_mode='connect'. "
                    "Standard accounts cannot subscribe to Connect events."
                ),
                remediation="Remove connect_events or switch to account_mode='connect'.",
            )
        if connect_url is not None:
            return err(
                code="E_INVALID_ARGUMENT",
                message=(
                    "connect_url is only valid in account_mode='connect'. "
                    "Standard accounts only need platform_url."
                ),
                remediation="Remove connect_url or switch to account_mode='connect'.",
            )
    else:  # connect mode
        if not connect_events:
            return err(
                code="E_MISSING_ARGUMENT",
                message="connect_events is required in account_mode='connect'.",
                remediation="Pass a non-empty list of connect-scope event types.",
            )

    # --- Safety gate ---
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
            account_mode=account_mode,
            code=safety_exc.code,
            idempotency_hit=False,
        )
        return err(
            code=safety_exc.code,
            message=safety_exc.message,
            remediation=safety_exc.remediation,
        )

    # --- URL validation ---
    if not HTTPS_URL.match(platform_url or ""):
        return _fail(
            project_hint=project_hint,
            started=started,
            mode=mode,
            account_mode=account_mode,
            code="E_INVALID_URL",
            message=(
                f"platform_url must start with https://; got {platform_url!r}. "
                "Stripe rejects non-HTTPS webhook endpoints."
            ),
        )
    if not platform_events:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            account_mode=account_mode,
            code="E_INVALID_INPUT",
            message="platform_events cannot be empty.",
        )

    # connect_url validation only when in connect mode (it was rejected earlier
    # otherwise). If not provided, fall back to platform_url.
    if account_mode == "connect":
        resolved_connect_url = connect_url or platform_url
        if not HTTPS_URL.match(resolved_connect_url):
            return _fail(
                project_hint=project_hint,
                started=started,
                mode=mode,
                account_mode=account_mode,
                code="E_INVALID_URL",
                message=(
                    f"connect_url must start with https://; got {resolved_connect_url!r}."
                ),
            )
    else:
        resolved_connect_url = None

    effective_api_version = api_version or DEFAULT_API_VERSION
    client = StripeClient(api_key=stripe_api_key, api_version=effective_api_version)

    # --- Pull existing webhooks to detect reuse/update candidates ---
    try:
        listing = client.call(
            "webhook_endpoints.list",
            lambda: stripe.WebhookEndpoint.list(limit=100),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            account_mode=account_mode,
            code="E_STRIPE_ERROR",
            message=f"Failed to list webhook endpoints: {exc}",
        )

    existing = as_dict_list(listing)

    # --- Reconcile platform endpoint (always) ---
    try:
        platform_result = _reconcile_one(
            client=client,
            existing=existing,
            url=platform_url,
            events=platform_events,
            connect=False,
            account_mode=account_mode,
            api_version=effective_api_version,
            project_hint=project_hint,
            description_prefix=description_prefix,
        )
    except _EventError as exc:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            account_mode=account_mode,
            code="E_UNKNOWN_EVENT_TYPE",
            message=str(exc),
        )
    except _LimitError as exc:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            account_mode=account_mode,
            code="E_LIMIT_REACHED",
            message=str(exc),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            account_mode=account_mode,
            code="E_STRIPE_ERROR",
            message=f"Failed on platform webhook: {exc}",
        )

    # --- Reconcile connect endpoint (connect mode only) ---
    connect_result: dict[str, Any] | None = None
    if account_mode == "connect":
        connect_existing = [
            e for e in existing if e.get("id") != platform_result["id"]
        ]
        try:
            connect_result = _reconcile_one(
                client=client,
                existing=connect_existing,
                url=resolved_connect_url or platform_url,
                events=connect_events or [],
                connect=True,
                account_mode=account_mode,
                api_version=effective_api_version,
                project_hint=project_hint,
                description_prefix=description_prefix,
            )
        except _EventError as exc:
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                account_mode=account_mode,
                code="E_UNKNOWN_EVENT_TYPE",
                message=str(exc),
            )
        except _LimitError as exc:
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                account_mode=account_mode,
                code="E_LIMIT_REACHED",
                message=str(exc),
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                account_mode=account_mode,
                code="E_STRIPE_ERROR",
                message=f"Failed on connect webhook: {exc}",
            )

    duration_ms = (time.monotonic() - started) * 1000
    idempotency_hit = platform_result["created_or_reused"] == "reused" and (
        connect_result is None or connect_result["created_or_reused"] == "reused"
    )

    data: dict[str, Any] = {"platform": platform_result, "account_mode": account_mode}
    if connect_result is not None:
        data["connect"] = connect_result

    # Evidence: observation WITHOUT full secrets.
    evidence: dict[str, Any] = {}
    try:
        results_for_log = (
            (platform_result, connect_result) if connect_result else (platform_result,)
        )
        result_summary_parts = [f"platform={platform_result['created_or_reused']}"]
        if connect_result is not None:
            result_summary_parts.append(
                f"connect={connect_result['created_or_reused']}"
            )
        obs_id = write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: {TOOL_NAME} on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode=mode,
                result_summary=" ".join(result_summary_parts),
                ids_created=[
                    r["id"] for r in results_for_log if r["created_or_reused"] == "created"
                ],
                ids_reused=[
                    r["id"]
                    for r in results_for_log
                    if r["created_or_reused"] in ("reused", "updated")
                ],
                duration_ms=duration_ms,
                extra={
                    "account_mode": account_mode,
                    "platform_url": platform_url,
                    "connect_url": resolved_connect_url or "",
                    "api_version": effective_api_version,
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
        account_mode=account_mode,
        code="OK",
        idempotency_hit=idempotency_hit,
    )

    return ok(data, evidence=evidence or None)


# --- Internals --------------------------------------------------------------


class _EventError(Exception):
    """Stripe rejected an event type (unknown to the api_version)."""


class _LimitError(Exception):
    """Stripe limit reached (e.g. 16 webhook endpoints per account)."""


def _reconcile_one(
    *,
    client: StripeClient,
    existing: list[dict[str, Any]],
    url: str,
    events: list[str],
    connect: bool,
    account_mode: str,
    api_version: str,
    project_hint: str,
    description_prefix: str | None,
) -> dict[str, Any]:
    """Find or create one webhook endpoint. Return the canonical dict.

    Match precedence:
    1. SpecBox-managed endpoint with same url+connect+account_mode → reuse.
    2. SpecBox-managed endpoint with same url+connect AND no specbox_account_mode
       (v0.1 endpoint) → silent migration: reuse and stamp account_mode now.
    3. Otherwise → create.
    """
    match, needs_migration = _find_match(
        existing, url=url, connect=connect, account_mode=account_mode
    )
    description = _build_description(
        connect=connect, project_hint=project_hint, prefix=description_prefix
    )

    if match is not None:
        same_events = set(match.get("enabled_events", []) or []) == set(events)
        if same_events and not needs_migration:
            secret = match.get("secret") or _fetch_secret(client, match["id"])
            return _format_result(match, secret=secret, created_or_reused="reused", connect=connect)
        # Update events and/or stamp account_mode in metadata.
        merged_metadata = dict(match.get("metadata") or {})
        merged_metadata[SPECBOX_ACCOUNT_MODE_KEY] = account_mode
        try:
            updated_raw = client.call(
                "webhook_endpoints.update",
                lambda eid=match["id"]: stripe.WebhookEndpoint.modify(
                    eid,
                    enabled_events=events,
                    description=description,
                    metadata=merged_metadata,
                ),
            )
        except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
            _raise_classified(exc, events=events)
            raise
        updated = as_dict(updated_raw)
        secret = updated.get("secret") or _fetch_secret(client, updated["id"])
        # Migration with same events should still surface as 'reused' to callers,
        # because no new endpoint was created. Only treat as 'updated' when the
        # event set actually changed.
        outcome = "reused" if same_events else "updated"
        return _format_result(updated, secret=secret, created_or_reused=outcome, connect=connect)

    # Create.
    metadata = base_metadata(project_hint, extra={SPECBOX_ACCOUNT_MODE_KEY: account_mode})
    idempotency_key = stable_idempotency_key(
        TOOL_NAME, url, connect, account_mode, sorted(events), api_version
    )
    try:
        created_raw = client.call(
            "webhook_endpoints.create",
            lambda: stripe.WebhookEndpoint.create(
                url=url,
                enabled_events=events,
                connect=connect,
                metadata=metadata,
                description=description,
                api_version=api_version,
                idempotency_key=idempotency_key,
            ),
        )
    except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
        _raise_classified(exc, events=events)
        raise
    created = as_dict(created_raw)
    secret = created.get("secret") or _fetch_secret(client, created["id"])
    return _format_result(created, secret=secret, created_or_reused="created", connect=connect)


def _find_match(
    existing: list[dict[str, Any]],
    *,
    url: str,
    connect: bool,
    account_mode: str,
) -> tuple[dict[str, Any] | None, bool]:
    """Find a SpecBox-managed endpoint matching url+connect.

    Returns (endpoint_or_None, needs_migration). needs_migration is True when
    the matched endpoint is a v0.1 endpoint (no specbox_account_mode) that
    should be silently migrated to the requested account_mode.

    Cross-mode collisions are prevented: an endpoint stamped with a different
    specbox_account_mode is NOT considered a match — the caller will create a
    new endpoint instead.
    """
    legacy_match: dict[str, Any] | None = None

    for endpoint in existing:
        if endpoint.get("url") != url:
            continue
        endpoint_connect = bool(endpoint.get("connect") or endpoint.get("application"))
        if endpoint_connect != connect:
            continue
        metadata = endpoint.get("metadata") or {}
        if not is_specbox_managed(metadata):
            continue
        endpoint_mode = metadata.get(SPECBOX_ACCOUNT_MODE_KEY)
        if endpoint_mode == account_mode:
            return endpoint, False
        if endpoint_mode is None or endpoint_mode == "":
            # v0.1 endpoint candidate — keep looking for an exact match first.
            if legacy_match is None:
                legacy_match = endpoint
        # endpoint_mode set but different → cross-mode, not a match.

    if legacy_match is not None:
        return legacy_match, True
    return None, False


def _fetch_secret(client: StripeClient, endpoint_id: str) -> str:
    """Fetch signing secret for an existing endpoint via expand=['secret']."""
    try:
        refreshed = client.call(
            "webhook_endpoints.retrieve.expand_secret",
            lambda: stripe.WebhookEndpoint.retrieve(endpoint_id, expand=["secret"]),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        logger.warning("failed to expand secret for %s: %s", endpoint_id, exc)
        return ""
    return as_dict(refreshed).get("secret", "") or ""


def _build_description(*, connect: bool, project_hint: str, prefix: str | None) -> str:
    scope = "connect" if connect else "platform"
    head = prefix or "SpecBox managed"
    return f"{head} — {scope} events for {project_hint}"


def _format_result(
    endpoint: dict[str, Any],
    *,
    secret: str,
    created_or_reused: str,
    connect: bool,
) -> dict[str, Any]:
    return {
        "id": endpoint.get("id", ""),
        "url": endpoint.get("url", ""),
        "secret": secret,
        "events": list(endpoint.get("enabled_events", []) or []),
        "status": endpoint.get("status", ""),
        "connect": connect,
        "created_or_reused": created_or_reused,
    }


def _raise_classified(exc: stripe.error.StripeError, *, events: list[str]) -> None:  # type: ignore[attr-defined]
    """Translate a Stripe InvalidRequestError into our typed errors when possible."""
    text = (str(exc) or "").lower()
    if "enabled_events" in text or "event_types" in text or "unknown event" in text:
        unknown = [e for e in events if e.lower() in text]
        suffix = f" (unknown: {unknown})" if unknown else ""
        raise _EventError(
            f"Stripe rejected one or more event types for the configured api_version{suffix}. "
            f"Original: {exc}"
        )
    if "limit" in text and "webhook" in text:
        raise _LimitError(f"Stripe webhook_endpoint limit reached. Original: {exc}")


def _fail(
    *,
    project_hint: str,
    started: float,
    mode: str,
    account_mode: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    duration_ms = (time.monotonic() - started) * 1000
    _emit_heartbeat(
        project=project_hint,
        success=False,
        duration_ms=duration_ms,
        mode=mode,
        account_mode=account_mode,
        code=code,
        idempotency_hit=False,
    )
    return err(code=code, message=message)


def _emit_heartbeat(
    *,
    project: str,
    success: bool,
    duration_ms: float,
    mode: str,
    account_mode: str,
    code: str,
    idempotency_hit: bool,
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
                "account_mode": account_mode,
                "code": code,
                "idempotency_hit": idempotency_hit,
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
