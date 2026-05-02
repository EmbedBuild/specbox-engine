"""Stitch quota tracking (v5.31.0).

Aggregates ``stitch_usage.jsonl`` entries by calendar month and model
class to surface remaining capacity before the user hits Google's
hard ceiling (350 Standard + 200 Experimental per month, no upgrade
path per Stitch foreign forum threads).
"""

from __future__ import annotations

from .computation import (
    DEFAULT_LIMIT_EXPERIMENTAL,
    DEFAULT_LIMIT_STANDARD,
    QuotaPayload,
    QuotaSnapshot,
    classify_model,
    compute_quota,
    compute_quota_payload,
)

__all__ = [
    "DEFAULT_LIMIT_EXPERIMENTAL",
    "DEFAULT_LIMIT_STANDARD",
    "QuotaPayload",
    "QuotaSnapshot",
    "classify_model",
    "compute_quota",
    "compute_quota_payload",
]
