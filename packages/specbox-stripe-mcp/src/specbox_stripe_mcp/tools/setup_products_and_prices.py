"""T3 — setup_products_and_prices.

Creates or idempotently reuses a product+price catalog keyed by `tier_key`.

Key design decisions (PRD §5, T3):
- Idempotency by metadata.tier_key per project (Stripe has no natural unique key).
- Stripe does NOT allow editing prices. If unit_amount/currency/interval changes,
  we create a new Price and archive the previous one with active=false.
- Product name/description can be updated in place.
- archive_unmanaged_tiers=True archives SpecBox-managed products whose tier_key
  is no longer in the incoming catalog. Useful when the project removes a tier.
- Errors: E_CURRENCY_NOT_ENABLED, E_DUPLICATE_TIER_KEY, E_PRICE_CONFLICT.
"""

from __future__ import annotations

import logging
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
from ..lib.stripe_client import StripeClient
from ..lib.stripe_utils import as_dict, as_dict_list

logger = logging.getLogger("specbox_stripe_mcp.tools.setup_products_and_prices")

TOOL_NAME = "setup_products_and_prices"

DEFAULT_INTERVAL = "month"


def setup_products_and_prices(
    *,
    stripe_api_key: str,
    catalog: list[dict[str, Any]],
    archive_unmanaged_tiers: bool = False,
    project_hint: str = "unknown",
    allow_live_mode: bool = False,
    live_mode_confirm_token: str | None = None,
) -> dict[str, Any]:
    """Reconcile the Stripe catalog to match the declared tiers.

    Each item in `catalog`:
        {
            "tier_key": "bronce",
            "product_name": "Sponsor Bronce",
            "description": "optional",
            "unit_amount": 500,        # cents
            "currency": "eur",
            "interval": "month",        # or "year"; default "month"
            "trial_period_days": null,  # optional
            "extra_metadata": {"foo": "bar"}  # optional
        }
    """
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
            idempotency_hit=False,
        )
        return err(
            code=safety_exc.code,
            message=safety_exc.message,
            remediation=safety_exc.remediation,
        )

    # --- Pre-flight: duplicate tier_keys (pure input validation, no Stripe) ---
    tier_keys: list[str] = []
    for item in catalog:
        tier = item.get("tier_key")
        if not tier:
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                code="E_INVALID_INPUT",
                message="every catalog entry must include a non-empty tier_key",
            )
        tier_keys.append(tier)
    duplicates = sorted({t for t in tier_keys if tier_keys.count(t) > 1})
    if duplicates:
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_DUPLICATE_TIER_KEY",
            message=f"catalog contains duplicate tier_key(s): {duplicates}",
        )

    client = StripeClient(api_key=stripe_api_key)

    # --- Fetch existing SpecBox-managed products (needed for reuse + archive) ---
    try:
        products_listing = client.call(
            "products.list",
            lambda: stripe.Product.list(limit=100, active=True),
        )
    except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
        return _fail(
            project_hint=project_hint, started=started, mode=mode,
            code="E_STRIPE_ERROR",
            message=f"Failed to list products: {exc}",
        )

    # Normalize ListObject → list[dict] to avoid StripeObject.get() collisions.
    existing_products = [
        p for p in as_dict_list(products_listing)
        if is_specbox_managed(p.get("metadata"))
    ]
    existing_by_tier: dict[str, dict[str, Any]] = {
        str(p.get("metadata", {}).get("tier_key", "")): p
        for p in existing_products
        if p.get("metadata", {}).get("tier_key")
    }

    product_results: list[dict[str, Any]] = []
    price_results: list[dict[str, Any]] = []
    archived_products: list[dict[str, Any]] = []
    all_prices_reused = True

    for item in catalog:
        try:
            product_res, price_res, reused = _reconcile_tier(
                client=client,
                item=item,
                existing_by_tier=existing_by_tier,
                project_hint=project_hint,
            )
        except _PriceConflictError as exc:
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                code="E_PRICE_CONFLICT",
                message=str(exc),
            )
        except _CurrencyError as exc:
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                code="E_CURRENCY_NOT_ENABLED",
                message=str(exc),
            )
        except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
            return _fail(
                project_hint=project_hint, started=started, mode=mode,
                code="E_STRIPE_ERROR",
                message=f"Failed reconciling tier {item.get('tier_key')!r}: {exc}",
            )
        product_results.append(product_res)
        price_results.append(price_res)
        if not reused:
            all_prices_reused = False

    # --- Optional: archive products no longer in the new catalog ---
    if archive_unmanaged_tiers:
        incoming_tiers = set(tier_keys)
        for tier, product in existing_by_tier.items():
            if tier in incoming_tiers:
                continue
            try:
                archived = client.call(
                    "products.archive",
                    lambda pid=product["id"]: stripe.Product.modify(pid, active=False),
                )
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                logger.warning("failed to archive product %s: %s", product.get("id"), exc)
                continue
            archived_products.append(
                {"id": as_dict(archived).get("id", product["id"]), "tier_key": tier}
            )

    duration_ms = (time.monotonic() - started) * 1000

    evidence = {}
    tier_mapping = {
        r["tier_key"]: {
            "product_id": r["id"],
            "price_id": next(
                (p["id"] for p in price_results if p["tier_key"] == r["tier_key"]),
                None,
            ),
        }
        for r in product_results
    }
    try:
        obs_id = write_config_observation(
            project=project_hint,
            title=f"stripe-mcp: {TOOL_NAME} on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode=mode,
                result_summary=(
                    f"tiers={len(product_results)} "
                    f"prices_all_reused={all_prices_reused} "
                    f"archived={len(archived_products)}"
                ),
                ids_created=[
                    r["id"] for r in product_results
                    if r["created_or_reused"] == "created"
                ],
                ids_reused=[
                    r["id"] for r in product_results
                    if r["created_or_reused"] in ("reused", "updated")
                ],
                duration_ms=duration_ms,
                extra={"tier_mapping": tier_mapping},
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
        idempotency_hit=all_prices_reused,
    )

    return ok(
        {
            "products": product_results,
            "prices": price_results,
            "archived": archived_products,
            "tier_mapping": tier_mapping,
        },
        evidence=evidence or None,
    )


# --- Internals --------------------------------------------------------------


class _PriceConflictError(Exception):
    """Non-SpecBox price exists that conflicts with the intended shape."""


class _CurrencyError(Exception):
    """Stripe rejected due to currency not enabled on the platform account."""


def _reconcile_tier(
    *,
    client: StripeClient,
    item: dict[str, Any],
    existing_by_tier: dict[str, dict[str, Any]],
    project_hint: str,
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Reconcile one tier. Returns (product_result, price_result, reused_price_flag)."""
    tier: str = str(item["tier_key"])
    desired_name: str = str(item.get("product_name") or tier)
    desired_description: str | None = item.get("description")
    unit_amount: int = int(item["unit_amount"])
    currency: str = str(item["currency"]).lower()
    interval: str = str(item.get("interval") or DEFAULT_INTERVAL)
    trial_days = item.get("trial_period_days")
    extra_metadata: dict[str, Any] = item.get("extra_metadata") or {}

    product_extra_metadata = {"tier_key": tier, **{k: str(v) for k, v in extra_metadata.items()}}
    metadata_for_create = base_metadata(project_hint, extra=product_extra_metadata)

    product = existing_by_tier.get(tier)
    if product is None:
        try:
            product_raw = client.call(
                "products.create",
                lambda: stripe.Product.create(
                    name=desired_name,
                    description=desired_description,
                    metadata=metadata_for_create,
                    idempotency_key=stable_idempotency_key(
                        TOOL_NAME, "product", project_hint, tier
                    ),
                ),
            )
        except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
            _maybe_raise_currency(exc)
            raise
        product = as_dict(product_raw)
        product_res = _product_result(product, tier=tier, created_or_reused="created")
    else:
        name_differs = product.get("name") != desired_name
        desc_differs = (product.get("description") or None) != (desired_description or None)
        if name_differs or desc_differs:
            product_raw = client.call(
                "products.update",
                lambda pid=product["id"]: stripe.Product.modify(
                    pid,
                    name=desired_name,
                    description=desired_description,
                ),
            )
            product = as_dict(product_raw)
            product_res = _product_result(product, tier=tier, created_or_reused="updated")
        else:
            product_res = _product_result(product, tier=tier, created_or_reused="reused")

    # --- Price reconciliation ---
    try:
        price_listing = client.call(
            "prices.list",
            lambda pid=product["id"]: stripe.Price.list(product=pid, active=True, limit=100),
        )
    except stripe.error.StripeError:  # type: ignore[attr-defined]
        raise

    existing_prices = as_dict_list(price_listing)
    match = _find_price_match(
        existing_prices,
        unit_amount=unit_amount,
        currency=currency,
        interval=interval,
    )

    if match is not None:
        # Verify it's SpecBox-managed (or at least not conflicting). If unmanaged but
        # matches exactly we treat as reusable; metadata tier_key will be stamped next.
        if not is_specbox_managed(match.get("metadata")):
            # Still reusable shape-wise; tag it so future runs recognize it.
            try:
                match_raw = client.call(
                    "prices.adopt",
                    lambda pid=match["id"]: stripe.Price.modify(
                        pid,
                        metadata={
                            "specbox_managed": "true",
                            "tier_key": tier,
                            "specbox_adopted": "true",
                        },
                    ),
                )
                match = as_dict(match_raw)
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                raise _PriceConflictError(
                    f"price {match.get('id')} conflicts for tier {tier}: {exc}"
                ) from exc
        price_res = _price_result(match, tier=tier, created_or_reused="reused")
        reused_flag = True
        # Archive OTHER active prices SpecBox-managed that don't match shape.
        for older in existing_prices:
            if older.get("id") == match.get("id"):
                continue
            if not is_specbox_managed(older.get("metadata")):
                continue
            try:
                client.call(
                    "prices.archive",
                    lambda oid=older["id"]: stripe.Price.modify(oid, active=False),
                )
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                logger.warning("failed to archive stale price %s: %s", older.get("id"), exc)
    else:
        # Shape drift → create new price and archive previous SpecBox ones.
        recurring = {"interval": interval}
        if trial_days:
            recurring["trial_period_days"] = int(trial_days)
        try:
            created_price_raw = client.call(
                "prices.create",
                lambda: stripe.Price.create(
                    product=product["id"],
                    unit_amount=unit_amount,
                    currency=currency,
                    recurring=recurring,
                    metadata={
                        "specbox_managed": "true",
                        "tier_key": tier,
                        "specbox_project_hint": project_hint,
                    },
                    idempotency_key=stable_idempotency_key(
                        TOOL_NAME, "price", project_hint, tier, unit_amount, currency, interval
                    ),
                ),
            )
            created_price = as_dict(created_price_raw)
        except stripe.error.InvalidRequestError as exc:  # type: ignore[attr-defined]
            _maybe_raise_currency(exc)
            raise
        # Archive existing SpecBox prices for this product.
        for older in existing_prices:
            if not is_specbox_managed(older.get("metadata")):
                continue
            try:
                client.call(
                    "prices.archive",
                    lambda oid=older["id"]: stripe.Price.modify(oid, active=False),
                )
            except stripe.error.StripeError as exc:  # type: ignore[attr-defined]
                logger.warning("failed to archive old price %s: %s", older.get("id"), exc)
        price_res = _price_result(created_price, tier=tier, created_or_reused="created")
        reused_flag = False

    return product_res, price_res, reused_flag


def _find_price_match(
    prices: list[dict[str, Any]],
    *,
    unit_amount: int,
    currency: str,
    interval: str,
) -> dict[str, Any] | None:
    for p in prices:
        if int(p.get("unit_amount") or 0) != unit_amount:
            continue
        if str(p.get("currency") or "").lower() != currency:
            continue
        recurring = p.get("recurring") or {}
        if str(recurring.get("interval") or "") != interval:
            continue
        return p
    return None


def _maybe_raise_currency(exc: stripe.error.InvalidRequestError) -> None:  # type: ignore[attr-defined]
    text = (str(exc) or "").lower()
    if "currency" in text and ("not" in text or "enabled" in text):
        raise _CurrencyError(
            f"Currency is not enabled on this Stripe account. Original: {exc}"
        )


def _product_result(
    product: dict[str, Any],
    *,
    tier: str,
    created_or_reused: str,
) -> dict[str, Any]:
    return {
        "id": product.get("id", ""),
        "tier_key": tier,
        "name": product.get("name", ""),
        "description": product.get("description") or "",
        "created_or_reused": created_or_reused,
    }


def _price_result(
    price: dict[str, Any],
    *,
    tier: str,
    created_or_reused: str,
) -> dict[str, Any]:
    recurring = price.get("recurring") or {}
    return {
        "id": price.get("id", ""),
        "tier_key": tier,
        "product_id": price.get("product", ""),
        "unit_amount": price.get("unit_amount", 0),
        "currency": price.get("currency", ""),
        "interval": recurring.get("interval", ""),
        "created_or_reused": created_or_reused,
    }


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
