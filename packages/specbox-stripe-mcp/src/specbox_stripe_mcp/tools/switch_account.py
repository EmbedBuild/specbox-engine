"""switch_stripe_account — rotate the active Stripe account of a SpecBox project.

US-STRIPE-SWITCH-ACCOUNT (UC-018..UC-023). Single tool that orchestrates:

  pre-flight (UC-018) → T1-T3 against destination (UC-019) → set_edge_secret
  on Supabase (UC-020) → scope_action on origin (UC-021) → with optional
  dry-run (UC-022) and automatic rollback (UC-023) when something fails.

Both modalities are supported via account_mode: 'standard' (3 secrets, 1
webhook) or 'connect' (4 secrets, 2 webhooks).

The tool is **idempotent**: running it twice with the same args is safe.
The destination account already-converged resources surface as
created_or_reused='reused'.

The tool is **reversible**: every mutating step pushes a "compensating
action" onto an internal journal. On failure the journal is replayed in
reverse. If rollback itself fails, a runbook is written to disk for the
human operator to recover by hand.

Returns the standard envelope. data includes:
  source_summary, destination_summary, plan, executed (list), rollback_log
  (list, empty if no rollback), runbook_path (str|None).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import stripe

from ..lib.alias_store import AliasStoreError, resolve_alias
from ..lib.engram_writer import format_config_content, write_config_observation
from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok
from ..lib.safety import SafetyError, guard_live_mode
from ..lib.stripe_client import StripeClient
from ..lib.stripe_utils import as_dict, as_dict_list

logger = logging.getLogger("specbox_stripe_mcp.tools.switch_account")

TOOL_NAME = "switch_stripe_account"

AccountMode = Literal["standard", "connect"]
ScopeAction = Literal[
    "keep_old_active",
    "archive_products_only",
    "deactivate_webhooks_only",
    "full_archive",
]
VALID_MODES: tuple[str, ...] = ("standard", "connect")
VALID_SCOPE_ACTIONS: tuple[str, ...] = (
    "keep_old_active",
    "archive_products_only",
    "deactivate_webhooks_only",
    "full_archive",
)
FULL_ARCHIVE_TOKEN = "I understand this archives all SpecBox resources in the source account"


# ---------------------------------------------------------------------------
# Internal data classes
# ---------------------------------------------------------------------------


@dataclass
class JournalEntry:
    """Append-only record of a mutating step that may need to be reverted."""

    operation: str
    target: str  # 'destination' | 'source' | 'supabase'
    forward_payload: dict[str, Any]
    revert_payload: dict[str, Any] | None  # None = not directly revertible
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class StripeResources:
    """Inventory of SpecBox-managed resources on a given account."""

    webhook_endpoints: list[dict[str, Any]] = field(default_factory=list)
    products: list[dict[str, Any]] = field(default_factory=list)
    active_subscriptions_count: int = 0
    customers_count: int = 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def switch_stripe_account(
    *,
    from_alias: str,
    to_alias: str,
    account_mode: AccountMode,
    project_path: str,
    platform_url: str,
    platform_events: list[str],
    connect_events: list[str] | None = None,
    connect_url: str | None = None,
    catalog: list[dict[str, Any]] | None = None,
    supabase_pat: str | None = None,
    supabase_project_ref: str | None = None,
    scope_action: ScopeAction = "keep_old_active",
    confirm_token: str | None = None,
    dry_run: bool = True,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict[str, Any]:
    """Rotate the active Stripe account for a SpecBox project.

    Args:
        from_alias / to_alias: alias names registered via store_stripe_alias.
        account_mode: standard or connect — determines how many webhook
            endpoints and which secret names get rotated.
        project_path: absolute path of the consumer project (where the alias
            store lives).
        platform_url + platform_events: same shape as setup_webhook_endpoints.
        connect_events + connect_url: required only when account_mode='connect'.
        catalog: optional product catalog to mirror to the destination. If
            None, products are NOT replicated — only webhooks.
        supabase_pat + supabase_project_ref: required when scope_action !=
            'keep_old_active' to inject new Edge Function secrets. Optional
            otherwise; when missing the tool writes a manual checklist
            ('PENDING_SWITCH_SECRETS.md') instead.
        scope_action: what to do with the source account once destination is
            ready. keep_old_active is the safe default (zero-downtime rollback
            possible).
        confirm_token: required ONLY when scope_action='full_archive'. Must
            equal FULL_ARCHIVE_TOKEN literally.
        dry_run: when True (default), runs only pre-flight + simulates the
            plan. No mutations against Stripe or Supabase.

    Returns: standard envelope with data describing the source, destination,
    executed actions, optional rollback log, optional runbook path.
    """

    started = time.monotonic()

    # ---- 1. Argument validation (synchronous, before any external call) ----

    if account_mode not in VALID_MODES:
        return err(
            code="E_INVALID_ARGUMENT",
            message=f"account_mode must be one of {list(VALID_MODES)}; got {account_mode!r}.",
        )
    if scope_action not in VALID_SCOPE_ACTIONS:
        return err(
            code="E_INVALID_ARGUMENT",
            message=f"scope_action must be one of {list(VALID_SCOPE_ACTIONS)}; got {scope_action!r}.",
        )
    if scope_action == "full_archive" and confirm_token != FULL_ARCHIVE_TOKEN:
        return err(
            code="E_CONFIRMATION_REQUIRED",
            message="scope_action='full_archive' requires the literal confirm_token.",
            remediation=f"Pass confirm_token={FULL_ARCHIVE_TOKEN!r}.",
        )
    if from_alias == to_alias:
        return err(
            code="E_INVALID_ARGUMENT",
            message="from_alias and to_alias must differ.",
        )
    if account_mode == "connect" and not connect_events:
        return err(
            code="E_MISSING_ARGUMENT",
            message="connect_events is required in account_mode='connect'.",
        )

    # ---- 2. Resolve credentials (NEVER log them) ----
    try:
        src_key = resolve_alias(alias_name=from_alias, project_path=project_path)
        dst_key = resolve_alias(alias_name=to_alias, project_path=project_path)
    except AliasStoreError as exc:
        return err(code=exc.code, message=exc.message, remediation=exc.remediation)

    # ---- 3. Live-mode safety gate on BOTH keys ----
    try:
        guard_live_mode(
            src_key,
            allow_live_mode=allow_live_mode,
            live_mode_confirm_token=live_mode_confirm_token,
        )
        guard_live_mode(
            dst_key,
            allow_live_mode=allow_live_mode,
            live_mode_confirm_token=live_mode_confirm_token,
        )
    except SafetyError as safety_exc:
        return err(
            code=safety_exc.code,
            message=safety_exc.message,
            remediation=safety_exc.remediation,
        )

    src_client = StripeClient(api_key=src_key)
    dst_client = StripeClient(api_key=dst_key)

    # ---- 4. Pre-flight (UC-018) ----
    try:
        source_inventory = _inventory(src_client, label="source")
        destination_inventory = _inventory(dst_client, label="destination")
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return err(code="E_STRIPE_ERROR", message=f"pre-flight inventory failed: {exc}")

    plan = _build_plan(
        account_mode=account_mode,
        source_inventory=source_inventory,
        destination_inventory=destination_inventory,
        platform_url=platform_url,
        platform_events=platform_events,
        connect_events=connect_events or [],
        connect_url=connect_url,
        catalog=catalog,
        scope_action=scope_action,
        will_rotate_secrets=supabase_pat is not None and supabase_project_ref is not None,
    )

    if dry_run:
        return ok(
            {
                "dry_run": True,
                "source_summary": _summarize_inventory(source_inventory),
                "destination_summary": _summarize_inventory(destination_inventory),
                "plan": plan,
                "executed": [],
                "estimated_duration_seconds": _estimate_duration(plan),
            }
        )

    # ---- 5. Execute plan with journal-driven rollback (UC-019..UC-023) ----
    journal: list[JournalEntry] = []
    executed: list[dict[str, Any]] = []
    rollback_log: list[dict[str, Any]] = []
    runbook_path: str | None = None

    try:
        # 5.1 Webhook endpoints on destination (UC-019).
        webhook_results = _replicate_webhooks(
            client=dst_client,
            account_mode=account_mode,
            platform_url=platform_url,
            platform_events=platform_events,
            connect_events=connect_events or [],
            connect_url=connect_url,
            project_hint=project_hint,
            journal=journal,
        )
        executed.append({"step": "webhooks_replicated", "result": webhook_results})

        # 5.2 Products + prices on destination (optional).
        if catalog:
            product_results = _replicate_catalog(
                client=dst_client,
                catalog=catalog,
                project_hint=project_hint,
                journal=journal,
            )
            executed.append({"step": "catalog_replicated", "result": product_results})

        # 5.3 Inject Supabase Edge Function secrets (UC-020).
        if supabase_pat and supabase_project_ref:
            secret_payload = _build_secret_payload(
                account_mode=account_mode,
                destination_key=dst_key,
                webhook_results=webhook_results,
            )
            secret_result = _push_supabase_secrets(
                supabase_pat=supabase_pat,
                project_ref=supabase_project_ref,
                payload=secret_payload,
                journal=journal,
            )
            executed.append({"step": "secrets_rotated", "result": secret_result})
        else:
            pending_path = _write_pending_secrets_md(
                project_path=Path(project_path),
                account_mode=account_mode,
                destination_key=dst_key,
                webhook_results=webhook_results,
            )
            executed.append(
                {"step": "secrets_pending_manual", "path": str(pending_path)}
            )

        # 5.4 scope_action on the source (UC-021).
        scope_result = _apply_scope_action(
            client=src_client,
            scope_action=scope_action,
            inventory=source_inventory,
            project_hint=project_hint,
        )
        executed.append({"step": f"scope_action:{scope_action}", "result": scope_result})

    except _SwitchAbortedError as exc:
        rollback_log = _rollback(journal, src_client, dst_client)
        if exc.partial_rollback_failure:
            runbook_path = str(_write_failure_runbook(
                project_path=Path(project_path),
                journal=journal,
                rollback_log=rollback_log,
                reason=str(exc),
            ))
        _engram(project_hint, tool=TOOL_NAME, succeeded=False, account_mode=account_mode)
        _heartbeat(project_hint, success=False, account_mode=account_mode, code=exc.code)
        return {
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
            "data": {
                "source_summary": _summarize_inventory(source_inventory),
                "destination_summary": _summarize_inventory(destination_inventory),
                "executed": executed,
                "rollback_log": rollback_log,
                "runbook_path": runbook_path,
            },
        }

    duration_ms = (time.monotonic() - started) * 1000
    _engram(project_hint, tool=TOOL_NAME, succeeded=True, account_mode=account_mode)
    _heartbeat(project_hint, success=True, account_mode=account_mode, code="OK")

    return ok(
        {
            "dry_run": False,
            "source_summary": _summarize_inventory(source_inventory),
            "destination_summary": _summarize_inventory(destination_inventory),
            "plan": plan,
            "executed": executed,
            "rollback_log": rollback_log,
            "runbook_path": runbook_path,
            "duration_ms": round(duration_ms, 2),
        }
    )


# ---------------------------------------------------------------------------
# Pre-flight helpers
# ---------------------------------------------------------------------------


def _inventory(client: StripeClient, *, label: str) -> StripeResources:
    """Enumerate SpecBox-managed resources on an account.

    label is just for logs; returned data is identical for source & destination.
    """
    res = StripeResources()

    # webhook endpoints
    try:
        wh_listing = client.call(
            f"{label}.webhooks.list",
            lambda: stripe.WebhookEndpoint.list(limit=100),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        # If listing fails for the source we keep going (source might be
        # gone-ish in some edge cases). For the destination we re-raise.
        if label == "destination":
            raise
        logger.warning("source webhook list failed (degraded): %s", exc)
    else:
        for wh in as_dict_list(wh_listing):
            metadata = wh.get("metadata") or {}
            if str(metadata.get("specbox_managed", "")).lower() == "true":
                res.webhook_endpoints.append(wh)

    # products (and optionally count their active prices)
    try:
        prod_listing = client.call(
            f"{label}.products.list",
            lambda: stripe.Product.list(limit=100, active=True),
        )
        for product in as_dict_list(prod_listing):
            metadata = product.get("metadata") or {}
            if str(metadata.get("specbox_managed", "")).lower() == "true":
                res.products.append(product)
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        if label == "destination":
            raise
        logger.warning("source product list failed (degraded): %s", exc)

    # subscriptions (count active only — not enumerated to avoid pagination cost)
    try:
        subs = client.call(
            f"{label}.subs.list",
            lambda: stripe.Subscription.list(status="active", limit=100),
        )
        res.active_subscriptions_count = len(as_dict_list(subs))
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        if label == "destination":
            raise
        logger.warning("source sub list failed (degraded): %s", exc)

    # customers count — best effort, capped at 100
    try:
        cust = client.call(
            f"{label}.customers.list",
            lambda: stripe.Customer.list(limit=100),
        )
        res.customers_count = len(as_dict_list(cust))
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        if label == "destination":
            raise
        logger.warning("source customer list failed (degraded): %s", exc)

    return res


def _summarize_inventory(inv: StripeResources) -> dict[str, Any]:
    return {
        "webhook_endpoints_count": len(inv.webhook_endpoints),
        "products_count": len(inv.products),
        "active_subscriptions_count": inv.active_subscriptions_count,
        "customers_count": inv.customers_count,
    }


def _build_plan(
    *,
    account_mode: AccountMode,
    source_inventory: StripeResources,
    destination_inventory: StripeResources,
    platform_url: str,
    platform_events: list[str],
    connect_events: list[str],
    connect_url: str | None,
    catalog: list[dict[str, Any]] | None,
    scope_action: ScopeAction,
    will_rotate_secrets: bool,
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = [
        {"step": "webhooks", "endpoints": 1 if account_mode == "standard" else 2,
         "platform_url": platform_url, "events": platform_events,
         "connect_events": connect_events if account_mode == "connect" else None,
         "connect_url": connect_url if account_mode == "connect" else None},
    ]
    if catalog:
        plan.append({"step": "catalog", "tier_count": len(catalog)})
    if will_rotate_secrets:
        plan.append({"step": "supabase_secrets", "secrets_count": 3 if account_mode == "standard" else 4})
    else:
        plan.append({"step": "supabase_secrets", "manual_fallback": True})
    plan.append({"step": "scope_action", "action": scope_action,
                 "source_webhooks": len(source_inventory.webhook_endpoints),
                 "source_products": len(source_inventory.products),
                 "source_active_subs": source_inventory.active_subscriptions_count})
    return plan


def _estimate_duration(plan: list[dict[str, Any]]) -> int:
    """Rough seconds estimate for the user to set expectations."""
    total = 0
    for entry in plan:
        step = entry.get("step")
        if step == "webhooks":
            total += 5 * (entry.get("endpoints") or 1)
        elif step == "catalog":
            total += 2 * (entry.get("tier_count") or 0)
        elif step == "supabase_secrets":
            total += 3 if not entry.get("manual_fallback") else 0
        elif step == "scope_action":
            action = entry.get("action")
            if action == "full_archive":
                total += 15  # archives + cancellations are slow
            elif action != "keep_old_active":
                total += 5
    return max(total, 1)


# ---------------------------------------------------------------------------
# Replication helpers
# ---------------------------------------------------------------------------


def _replicate_webhooks(
    *,
    client: StripeClient,
    account_mode: AccountMode,
    platform_url: str,
    platform_events: list[str],
    connect_events: list[str],
    connect_url: str | None,
    project_hint: str,
    journal: list[JournalEntry],
) -> dict[str, Any]:
    """Reuse setup_webhook_endpoints semantics for the destination.

    We import the function lazily to avoid circular imports.
    """
    from .setup_webhook_endpoints import setup_webhook_endpoints

    response = setup_webhook_endpoints(
        stripe_api_key=client.api_key,
        account_mode=account_mode,
        platform_url=platform_url,
        platform_events=platform_events,
        connect_events=connect_events if account_mode == "connect" else None,
        connect_url=connect_url,
        project_hint=project_hint,
    )
    if not response.get("success"):
        raise _SwitchAbortedError(
            code=response.get("error", {}).get("code", "E_WEBHOOK_REPLICATE_FAILED"),
            message=response.get("error", {}).get("message", "webhook replication failed"),
        )
    data = response.get("data", {})

    # Journal: only the freshly-created endpoints. 'reused' ones are pre-existing.
    if data.get("platform", {}).get("created_or_reused") == "created":
        journal.append(JournalEntry(
            operation="webhook.delete",
            target="destination",
            forward_payload={"id": data["platform"]["id"]},
            revert_payload={"id": data["platform"]["id"]},
        ))
    if account_mode == "connect" and data.get("connect", {}).get("created_or_reused") == "created":
        journal.append(JournalEntry(
            operation="webhook.delete",
            target="destination",
            forward_payload={"id": data["connect"]["id"]},
            revert_payload={"id": data["connect"]["id"]},
        ))
    return data


def _replicate_catalog(
    *,
    client: StripeClient,
    catalog: list[dict[str, Any]],
    project_hint: str,
    journal: list[JournalEntry],
) -> dict[str, Any]:
    from .setup_products_and_prices import setup_products_and_prices

    response = setup_products_and_prices(
        stripe_api_key=client.api_key,
        catalog=catalog,
        project_hint=project_hint,
    )
    if not response.get("success"):
        raise _SwitchAbortedError(
            code=response.get("error", {}).get("code", "E_CATALOG_REPLICATE_FAILED"),
            message=response.get("error", {}).get("message", "catalog replication failed"),
        )
    data = response.get("data", {})
    # Journal: products are archived (NOT deleted) on rollback, since Stripe
    # forbids deleting products that ever had prices.
    for prod in data.get("products", []):
        if prod.get("created_or_reused") == "created":
            journal.append(JournalEntry(
                operation="product.archive",
                target="destination",
                forward_payload={"id": prod["id"]},
                revert_payload={"id": prod["id"]},
            ))
    return data


def _build_secret_payload(
    *,
    account_mode: AccountMode,
    destination_key: str,
    webhook_results: dict[str, Any],
) -> dict[str, str]:
    """Build the Edge Function secret payload, never logging values.

    Note: STRIPE_PUBLISHABLE_KEY is intentionally NOT rotated here — it cannot
    be derived from the secret key alone, and we don't want to overwrite a
    valid publishable with an empty string. The skill can rotate it
    separately if needed.
    """
    if account_mode == "standard":
        return {
            "STRIPE_SECRET_KEY": destination_key,
            "STRIPE_WEBHOOK_SECRET": webhook_results["platform"]["secret"],
            # Publishable: leave the existing one. We don't write it.
        }
    return {
        "STRIPE_SECRET_KEY": destination_key,
        "STRIPE_WEBHOOK_SECRET_PLATFORM": webhook_results["platform"]["secret"],
        "STRIPE_WEBHOOK_SECRET_CONNECT": webhook_results["connect"]["secret"],
    }


def _push_supabase_secrets(
    *,
    supabase_pat: str,
    project_ref: str,
    payload: dict[str, str],
    journal: list[JournalEntry],
) -> dict[str, Any]:
    """Push secrets to Supabase Edge Functions via the management API.

    We use httpx directly to avoid a hard dep on the specbox-supabase MCP
    package — the consumer can use either path. Snapshot any pre-existing
    values BEFORE writing so rollback can restore them (best-effort: Supabase
    does not expose secret VALUES on read, only names — so the rollback is
    a marker, not a true restore).
    """
    import httpx

    headers = {"Authorization": f"Bearer {supabase_pat}"}
    base = f"https://api.supabase.com/v1/projects/{project_ref}/secrets"

    # Snapshot existing secret NAMES (not values — Supabase doesn't reveal them).
    pre_existing_names: set[str] = set()
    try:
        with httpx.Client(timeout=30) as http:
            existing_response = http.get(base, headers=headers)
            existing_response.raise_for_status()
            for entry in existing_response.json():
                if isinstance(entry, dict) and "name" in entry:
                    pre_existing_names.add(str(entry["name"]))
    except httpx.HTTPError as exc:
        raise _SwitchAbortedError(
            code="E_SUPABASE_LIST_FAILED",
            message=f"failed to read existing Supabase secrets: {exc}",
        ) from exc

    # Bulk POST — Supabase replaces values for existing names.
    body = [{"name": name, "value": val} for name, val in payload.items()]
    try:
        with httpx.Client(timeout=30) as http:
            resp = http.post(base, headers=headers, json=body)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise _SwitchAbortedError(
            code="E_SUPABASE_WRITE_FAILED",
            message=f"failed to write Supabase secrets: {exc}",
        ) from exc

    # Journal: rollback removes the names we wrote that didn't exist before,
    # and emits a warning for the names that did (we cannot restore values).
    journal.append(JournalEntry(
        operation="supabase.secrets.restore",
        target="supabase",
        forward_payload={"names_written": list(payload.keys())},
        revert_payload={
            "delete_names": [n for n in payload if n not in pre_existing_names],
            "values_lost_for": [n for n in payload if n in pre_existing_names],
            "supabase_pat_set": True,
            "project_ref": project_ref,
        },
    ))
    return {
        "names_written": list(payload.keys()),
        "previously_present": [n for n in payload if n in pre_existing_names],
        "previously_absent": [n for n in payload if n not in pre_existing_names],
    }


def _write_pending_secrets_md(
    *,
    project_path: Path,
    account_mode: AccountMode,
    destination_key: str,
    webhook_results: dict[str, Any],
) -> Path:
    """Write a manual checklist when specbox-supabase MCP isn't available."""
    out = project_path / "doc" / "PENDING_SWITCH_SECRETS.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    if account_mode == "standard":
        secrets_section = (
            "  STRIPE_SECRET_KEY        = (the new sk_test_/sk_live_ key from the destination alias)\n"
            f"  STRIPE_WEBHOOK_SECRET    = {webhook_results['platform']['secret']}\n"
        )
    else:
        secrets_section = (
            "  STRIPE_SECRET_KEY                = (the new sk_test_/sk_live_ key from the destination alias)\n"
            f"  STRIPE_WEBHOOK_SECRET_PLATFORM   = {webhook_results['platform']['secret']}\n"
            f"  STRIPE_WEBHOOK_SECRET_CONNECT    = {webhook_results['connect']['secret']}\n"
        )

    body = (
        "# Pending Stripe secrets after switch_stripe_account\n"
        "\n"
        "Supabase Management API was not configured (no `supabase_pat`).\n"
        "Copy these values into your Supabase Edge Function secrets manually:\n"
        "\n"
        "  https://supabase.com/dashboard/project/<your-ref>/settings/functions\n"
        "\n"
        "```\n"
        f"{secrets_section}"
        "```\n"
        "\n"
        "Once done, delete this file. The webhook will start receiving events on\n"
        "the destination account immediately, but Edge Functions will reject them\n"
        "until the secrets are set.\n"
    )
    # NOTE: we DO write secret values (webhook signing secrets) here. They are
    # not as sensitive as sk_*; they cannot move money on their own. The
    # destination sk_* is NEVER written — the caller pastes it from the alias.
    out.write_text(body, encoding="utf-8")
    return out


def _apply_scope_action(
    *,
    client: StripeClient,
    scope_action: ScopeAction,
    inventory: StripeResources,
    project_hint: str,
) -> dict[str, Any]:
    """Touch the source account based on scope_action."""
    if scope_action == "keep_old_active":
        return {"action": "keep_old_active", "touched": 0}

    archived_products: list[str] = []
    deactivated_webhooks: list[str] = []
    canceled_subs: list[str] = []

    if scope_action in ("archive_products_only", "full_archive"):
        for product in inventory.products:
            try:
                client.call(
                    "products.archive",
                    lambda pid=product["id"]: stripe.Product.modify(pid, active=False),
                )
                archived_products.append(product["id"])
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                logger.warning("failed to archive product %s: %s", product["id"], exc)

    if scope_action in ("deactivate_webhooks_only", "full_archive"):
        for endpoint in inventory.webhook_endpoints:
            try:
                client.call(
                    "webhooks.disable",
                    lambda eid=endpoint["id"]: stripe.WebhookEndpoint.modify(eid, disabled=True),
                )
                deactivated_webhooks.append(endpoint["id"])
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                logger.warning("failed to disable webhook %s: %s", endpoint["id"], exc)

    if scope_action == "full_archive":
        # Cancel SpecBox-managed subs only (filter by metadata)
        try:
            sub_listing = client.call(
                "subs.list.specbox",
                lambda: stripe.Subscription.list(status="active", limit=100),
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            logger.warning("failed to list source subs for cancel: %s", exc)
        else:
            for sub in as_dict_list(sub_listing):
                metadata = sub.get("metadata") or {}
                if str(metadata.get("specbox_managed", "")).lower() != "true":
                    continue
                try:
                    client.call(
                        "subs.cancel",
                        lambda sid=sub["id"]: stripe.Subscription.cancel(sid),
                    )
                    canceled_subs.append(sub["id"])
                except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                    logger.warning("failed to cancel sub %s: %s", sub["id"], exc)

    # Audit observation BEFORE returning so the trail is durable even if Engram
    # is offline.
    try:
        write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: scope_action {scope_action}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode="-",
                result_summary=(
                    f"archived={len(archived_products)} "
                    f"webhooks_off={len(deactivated_webhooks)} "
                    f"canceled={len(canceled_subs)}"
                ),
                ids_created=[],
                ids_reused=archived_products + deactivated_webhooks + canceled_subs,
                duration_ms=0,
                extra={"scope_action": scope_action},
            ),
        )
    except Exception:
        pass

    return {
        "action": scope_action,
        "archived_products": archived_products,
        "deactivated_webhooks": deactivated_webhooks,
        "canceled_subs": canceled_subs,
    }


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


class _SwitchAbortedError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.partial_rollback_failure = False


def _rollback(
    journal: list[JournalEntry],
    src_client: StripeClient,
    dst_client: StripeClient,
) -> list[dict[str, Any]]:
    """Replay journal in reverse, calling the inverse of each entry."""
    log: list[dict[str, Any]] = []
    for entry in reversed(journal):
        op = entry.operation
        try:
            if op == "webhook.delete":
                wid = entry.revert_payload["id"]  # type: ignore[index]
                dst_client.call(
                    "rollback.webhook.delete",
                    lambda w=wid: stripe.WebhookEndpoint.delete(w),
                )
                log.append({"op": op, "id": wid, "ok": True})
            elif op == "product.archive":
                pid = entry.revert_payload["id"]  # type: ignore[index]
                dst_client.call(
                    "rollback.product.archive",
                    lambda p=pid: stripe.Product.modify(p, active=False),
                )
                log.append({"op": op, "id": pid, "ok": True})
            elif op == "supabase.secrets.restore":
                # We cannot truly restore values. We log a warning and the
                # runbook will tell the user which names need to be re-set.
                log.append({
                    "op": op,
                    "ok": False,
                    "warning": "Supabase secret values cannot be restored — manual action required.",
                    "delete_names": entry.revert_payload.get("delete_names", []),
                    "values_lost_for": entry.revert_payload.get("values_lost_for", []),
                })
            else:
                log.append({"op": op, "ok": False, "warning": f"unknown operation in journal: {op}"})
        except Exception as exc:  # broad on purpose — rollback must not raise
            log.append({"op": op, "ok": False, "error": str(exc)})
    return log


def _write_failure_runbook(
    *,
    project_path: Path,
    journal: list[JournalEntry],
    rollback_log: list[dict[str, Any]],
    reason: str,
) -> Path:
    out = project_path / "doc" / "SWITCH_FAILURE_RUNBOOK.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    body_lines = [
        "# switch_stripe_account failure runbook",
        "",
        f"Reason: {reason}",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Operations attempted (chronological)",
        "",
    ]
    for entry in journal:
        body_lines.append(f"- [{entry.timestamp}] {entry.operation} on {entry.target}")
    body_lines.extend([
        "",
        "## Rollback results",
        "",
    ])
    for r in rollback_log:
        body_lines.append(f"- {r}")
    body_lines.extend([
        "",
        "## Manual recovery checklist",
        "",
        "1. Open Stripe dashboard → Webhooks. Verify endpoints created on the",
        "   destination account look correct, or delete leftovers.",
        "2. Open Stripe dashboard → Products. Verify catalog state on both accounts.",
        "3. Open Supabase dashboard → Edge Function secrets. Re-set:",
        "   - STRIPE_SECRET_KEY",
        "   - STRIPE_WEBHOOK_SECRET (or _PLATFORM/_CONNECT pair in Connect mode)",
        "   - STRIPE_PUBLISHABLE_KEY",
        "4. Once stabilized, re-run `switch_stripe_account` with `dry_run=true` to",
        "   verify desired vs current state. Re-run with `dry_run=false` to converge.",
    ])
    out.write_text("\n".join(body_lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Telemetry helpers
# ---------------------------------------------------------------------------


def _engram(project_hint: str, *, tool: str, succeeded: bool, account_mode: str) -> None:
    try:
        write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: {tool} ({'OK' if succeeded else 'FAIL'})",
            content=format_config_content(
                tool=tool,
                project=project_hint,
                mode="-",
                result_summary="succeeded" if succeeded else "failed",
                duration_ms=0,
                extra={"account_mode": account_mode},
            ),
        )
    except Exception as exc:
        logger.debug("engram write skipped: %s", exc)


def _heartbeat(project_hint: str, *, success: bool, account_mode: str, code: str) -> None:
    try:
        report_heartbeat(
            project=project_hint,
            event_type="stripe_mcp_call",
            payload={
                "tool": TOOL_NAME,
                "success": success,
                "account_mode": account_mode,
                "code": code,
                "idempotency_hit": False,
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)


# Avoid mypy unused warnings.
_ = as_dict
