"""Helpers for deterministic idempotency keys and metadata conventions.

All SpecBox-managed Stripe resources carry the same baseline metadata; keeping the
constants here avoids drift across tools.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

SPECBOX_MANAGED_KEY = "specbox_managed"
SPECBOX_MANAGED_VALUE = "true"
SPECBOX_VERSION_KEY = "specbox_version"
SPECBOX_PROJECT_HINT_KEY = "specbox_project_hint"
SPECBOX_CREATED_AT_KEY = "specbox_created_at"
SPECBOX_VERSION = "0.1.0"


def base_metadata(project_hint: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return the metadata every create call should stamp into a resource.

    `extra` is merged last so callers can add resource-specific keys
    (e.g. tier_key for products, specbox_test_seller_idx for sellers).
    """
    out: dict[str, str] = {
        SPECBOX_MANAGED_KEY: SPECBOX_MANAGED_VALUE,
        SPECBOX_VERSION_KEY: SPECBOX_VERSION,
        SPECBOX_PROJECT_HINT_KEY: project_hint or "unknown",
        SPECBOX_CREATED_AT_KEY: datetime.now(UTC).isoformat(),
    }
    if extra:
        out.update({k: str(v) for k, v in extra.items()})
    return out


def is_specbox_managed(metadata: dict[str, Any] | None) -> bool:
    """Return True if the metadata dict marks the resource as SpecBox-managed."""
    if not metadata:
        return False
    return str(metadata.get(SPECBOX_MANAGED_KEY, "")).lower() == SPECBOX_MANAGED_VALUE


def stable_idempotency_key(*parts: Any) -> str:
    """Produce a deterministic Idempotency-Key from the parts that should uniquely
    identify the intended resource.

    Stripe requires idempotency keys to be unique per intended operation but stable
    across retries. We build them from tool name + semantic lookup keys (url+connect
    flag for webhooks, tier_key for products, etc.) so concurrent re-invocations of
    the same logical operation yield the same key.
    """
    payload = json.dumps(list(parts), sort_keys=True, default=str, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"specbox-{digest[:32]}"
