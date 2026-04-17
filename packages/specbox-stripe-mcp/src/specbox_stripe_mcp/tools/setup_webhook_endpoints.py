"""T2 — setup_webhook_endpoints.

Creates (or idempotently reuses) the 2 webhook endpoints (platform + connect)
with the correct event lists, and returns their signing secrets.

Key design decisions (PRD §5, T2):
- Idempotency: metadata.specbox_managed='true' + url + connect-flag. Never create
  a duplicate when a matching SpecBox-managed endpoint exists.
- Secret recovery: Stripe only returns the signing secret on CREATE. On REUSE
  we must fetch it with expand=['secret'].
- Concurrency: POST uses a deterministic Idempotency-Key so two concurrent
  invocations from the same caller intent collapse into one Stripe object.
- api_version defaults to '2024-11-20.acacia' but is overridable per-call.
- Errors: E_INVALID_URL (non-HTTPS), E_UNKNOWN_EVENT_TYPE (Stripe rejects event
  name), E_LIMIT_REACHED (>16 webhooks/account cap).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

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

logger = logging.getLogger("specbox_stripe_mcp.tools.setup_webhook_endpoints")

TOOL_NAME = "setup_webhook_endpoints"
HTTPS_URL = re.compile(r"^https://", re.IGNORECASE)


def setup_webhook_endpoints(
    *,
    stripe_api_key: str,
    platform_url: str,
    platform_events: list[str],
    connect_events: list[str],
    connect_url: str | None = None,
    api_version: str | None = None,
    project_hint: str = "unknown",
    description_prefix: str | None = None,
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict[str, Any]:
    """Ensure the 2 SpecBox-managed webhook endpoints exist with the requested events.

    Args:
        stripe_api_key: sk_test_* or sk_live_*.
        platform_url: HTTPS URL receiving platform-scope events.
        platform_events: list of event types (e.g. ['account.updated']).
        connect_events: list of event types for connect-scope events.
        connect_url: defaults to platform_url (dual-secret, single-endpoint pattern).
        api_version: Stripe API version to pin this endpoint to.
        project_hint: free-form tag for metadata + evidence.
        description_prefix: free text prefixing the Stripe description field.
        allow_live_mode / live_mode_confirm_token: live-mode opt-in.

    Returns:
        Standard envelope with data={platform, connect}, each item including
        id, url, secret, events, status, connect (bool), and created_or_reused.
    """
    started = time.monotonic()
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
            code=safety_exc.code,
            idempotency_hit=False,
        )
        return err(
            code=safety_exc.code,
            message=safety_exc.message,
            remediation=safety_exc.remediation,
        )

    # --- Input validation (happens before any Stripe call) ---
    if not HTTPS_URL.match(platform_url or ""):
        return _fail(
            project_hint=project_hint,
            started=started,
            mode=mode,
            code="E_INVALID_URL",
            message=(
                f"platform_url must start with https://; got {platform_url!r}. "
                "Stripe rejects non-HTTPS webhook endpoints."
            ),
        )
    resolved_connect_url = connect_url or platform_url
    if not HTTPS_URL.match(resolved_connect_url):
        return _fail(
            project_hint=project_hint,
            started=started,
            mode=mode,
            code="E_INVALID_URL",
            message=f"connect_url must start with https://; got {resolved_connect_url!r}.",
        )
    if not platform_events:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_INVALID_INPUT",
            message="platform_events cannot be empty.",
        )
    if not connect_events:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_INVALID_INPUT",
            message="connect_events cannot be empty.",
        )

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
            code="E_STRIPE_ERROR",
            message=f"Failed to list webhook endpoints: {exc}",
        )

    existing = list(listing.get("data", []) or [])

    try:
        platform_result = _reconcile_one(
            client=client,
            existing=existing,
            url=platform_url,
            events=platform_events,
            connect=False,
            api_version=effective_api_version,
            project_hint=project_hint,
            description_prefix=description_prefix,
        )
    except _EventError as exc:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_UNKNOWN_EVENT_TYPE",
            message=str(exc),
        )
    except _LimitError as exc:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_LIMIT_REACHED",
            message=str(exc),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_STRIPE_ERROR",
            message=f"Failed on platform webhook: {exc}",
        )

    # connect endpoint reconciliation must avoid the platform endpoint we just
    # reconciled even if URLs match, so we filter it out.
    connect_existing = [e for e in existing if e.get("id") != platform_result["id"]]

    try:
        connect_result = _reconcile_one(
            client=client,
            existing=connect_existing,
            url=resolved_connect_url,
            events=connect_events,
            connect=True,
            api_version=effective_api_version,
            project_hint=project_hint,
            description_prefix=description_prefix,
        )
    except _EventError as exc:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_UNKNOWN_EVENT_TYPE",
            message=str(exc),
        )
    except _LimitError as exc:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_LIMIT_REACHED",
            message=str(exc),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_STRIPE_ERROR",
            message=f"Failed on connect webhook: {exc}",
        )

    duration_ms = (time.monotonic() - started) * 1000
    idempotency_hit = (
        platform_result["created_or_reused"] == "reused"
        and connect_result["created_or_reused"] == "reused"
    )

    data = {
        "platform": platform_result,
        "connect": connect_result,
    }

    # Evidence: observation WITHOUT full secrets.
    evidence = {}
    try:
        obs_id = write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: {TOOL_NAME} on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode=mode,
                result_summary=(
                    f"platform={platform_result['created_or_reused']} "
                    f"connect={connect_result['created_or_reused']}"
                ),
                ids_created=[
                    r["id"]
                    for r in (platform_result, connect_result)
                    if r["created_or_reused"] == "created"
                ],
                ids_reused=[
                    r["id"]
                    for r in (platform_result, connect_result)
                    if r["created_or_reused"] in ("reused", "updated")
                ],
                duration_ms=duration_ms,
                extra={
                    "platform_url": platform_url,
                    "connect_url": resolved_connect_url,
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
    api_version: str,
    project_hint: str,
    description_prefix: str | None,
) -> dict[str, Any]:
    """Find or create one webhook endpoint. Return the canonical dict."""
    match = _find_match(existing, url=url, connect=connect)
    description = _build_description(connect=connect, project_hint=project_hint, prefix=description_prefix)

    if match is not None:
        same_events = set(match.get("enabled_events", []) or []) == set(events)
        if same_events:
            secret = match.get("secret") or _fetch_secret(client, match["id"])
            return _format_result(match, secret=secret, created_or_reused="reused", connect=connect)
        # Update to align events + description.
        try:
            updated = client.call(
                "webhook_endpoints.update",
                lambda eid=match["id"]: stripe.WebhookEndpoint.modify(
                    eid,
                    enabled_events=events,
                    description=description,
                ),
            )
        except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
            _raise_classified(exc, events=events)
            raise
        secret = updated.get("secret") or _fetch_secret(client, updated["id"])
        return _format_result(updated, secret=secret, created_or_reused="updated", connect=connect)

    # Create.
    metadata = base_metadata(project_hint)
    idempotency_key = stable_idempotency_key(
        TOOL_NAME, url, connect, sorted(events), api_version
    )
    try:
        created = client.call(
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
    # On CREATE the secret is present directly in the response.
    secret = created.get("secret") or _fetch_secret(client, created["id"])
    return _format_result(created, secret=secret, created_or_reused="created", connect=connect)


def _find_match(
    existing: list[dict[str, Any]],
    *,
    url: str,
    connect: bool,
) -> dict[str, Any] | None:
    """Return the first SpecBox-managed endpoint matching url+connect, or None."""
    for endpoint in existing:
        if endpoint.get("url") != url:
            continue
        # Stripe returns `connect` or not at all depending on API version; normalize.
        endpoint_connect = bool(endpoint.get("connect") or endpoint.get("application"))
        if endpoint_connect != connect:
            continue
        metadata = endpoint.get("metadata") or {}
        if not is_specbox_managed(metadata):
            continue
        return endpoint
    return None


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
    return refreshed.get("secret", "") or ""


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
    code: str,
    message: str,
) -> dict[str, Any]:
    duration_ms = (time.monotonic() - started) * 1000
    _emit_heartbeat(
        project=project_hint,
        success=False,
        duration_ms=duration_ms,
        mode=mode,
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
                "code": code,
                "idempotency_hit": idempotency_hit,
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
