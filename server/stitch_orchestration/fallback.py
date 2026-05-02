"""Fallback chain for Stitch screen generation.

Plan §3.3 specifies the strategy ladder:

    edit_baseline → variants_refine → regenerate

The Flash safety net is opt-in (default ``False``) and runs only as a
last resort, marking results as ``degraded=True``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Literal, Protocol


class FallbackStrategy(str, Enum):
    EDIT_BASELINE = "edit_baseline"
    VARIANTS_REFINE = "variants_refine"
    REGENERATE = "regenerate"
    FLASH_SAFETY_NET = "flash_safety_net"


class FallbackOutcome(str, Enum):
    OK_FIRST_TRY = "ok_first_try"
    OK_AFTER_FALLBACK = "ok_after_fallback"
    OK_DEGRADED = "ok_degraded"
    FAILED = "failed"


# ── Protocol implemented by the real StitchClient adapter ───────────────


class StitchOps(Protocol):
    """The minimal surface fallback needs from a Stitch client.

    Each method may raise — the fallback handler interprets exceptions
    via ``classify_error`` and decides whether to retry or surface.
    """

    async def generate_screen(
        self,
        project_id: str,
        prompt: str,
        *,
        device_type: str = "DESKTOP",
        model_id: str = "GEMINI_3_PRO",
    ) -> Any: ...

    async def edit_screens(
        self,
        project_id: str,
        screen_id: str,
        prompt: str,
        *,
        device_type: str | None = None,
        model_id: str | None = None,
    ) -> Any: ...

    async def generate_variants(
        self,
        project_id: str,
        screen_id: str,
        *,
        prompt: str | None = None,
        variant_count: int = 1,
        creative_range: str = "REFINE",
        aspects: list[str] | None = None,
    ) -> Any: ...


# ── Result shape ───────────────────────────────────────────────────────


@dataclass
class FallbackResult:
    outcome: FallbackOutcome
    final_strategy: str
    model_used: str
    attempts: list[dict] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    degraded: bool = False
    degraded_reason: str | None = None


# ── Error classification ───────────────────────────────────────────────


_TRANSIENT_HINTS = (
    "timeout",
    "5xx",
    "502",
    "503",
    "504",
    "connection",
    "read",
)
_QUOTA_HINTS = ("quota", "rate limit", "exhausted", "429")
_CONTENT_HINTS = ("content policy", "rejected", "unsafe")


def classify_error(exc: BaseException) -> Literal["transient", "quota", "content", "unknown"]:
    msg = (str(exc) or "").lower()
    if any(h in msg for h in _CONTENT_HINTS):
        return "content"
    if any(h in msg for h in _QUOTA_HINTS):
        return "quota"
    if any(h in msg for h in _TRANSIENT_HINTS):
        return "transient"
    return "unknown"


# ── Main entry point ───────────────────────────────────────────────────


async def generate_screen_with_fallback(
    ops: StitchOps,
    project_id: str,
    prompt: str,
    *,
    device_type: str = "DESKTOP",
    model_id: str = "GEMINI_3_PRO",
    flash_model_id: str = "GEMINI_3_FLASH",
    baseline_screen_id: str | None = None,
    fallback_strategy: list[FallbackStrategy] | None = None,
    enable_flash_safety_net: bool = False,
    max_total_attempts: int = 3,
    sleep: Callable[[float], Awaitable[None]] | None = None,
) -> FallbackResult:
    """Run the fallback ladder until a generation succeeds or we give up.

    Args:
        ops: Anything implementing :class:`StitchOps` (real client or mock).
        baseline_screen_id: If provided, ``edit_baseline`` and
            ``variants_refine`` strategies operate on this existing
            screen; without it those strategies are skipped.
        fallback_strategy: Strategies in order. Defaults to
            ``[EDIT_BASELINE, VARIANTS_REFINE, REGENERATE]``.
        enable_flash_safety_net: When True, append a final attempt with
            ``flash_model_id`` and mark the result ``degraded=True``.
            Default False — calling code must opt in explicitly.
        max_total_attempts: Hard ceiling across all strategies.
    """

    strategies = list(
        fallback_strategy or [
            FallbackStrategy.EDIT_BASELINE,
            FallbackStrategy.VARIANTS_REFINE,
            FallbackStrategy.REGENERATE,
        ]
    )
    if enable_flash_safety_net:
        strategies.append(FallbackStrategy.FLASH_SAFETY_NET)

    attempts: list[dict] = []

    # Attempt 0: the natural call.
    primary = await _run_strategy(
        ops,
        FallbackStrategy.REGENERATE,
        project_id=project_id,
        prompt=prompt,
        device_type=device_type,
        model_id=model_id,
        baseline_screen_id=baseline_screen_id,
        attempts=attempts,
    )
    if primary is not None:
        return FallbackResult(
            outcome=FallbackOutcome.OK_FIRST_TRY,
            final_strategy=FallbackStrategy.REGENERATE.value,
            model_used=model_id,
            attempts=attempts,
            result=primary,
        )

    # Fall back through the ladder.
    for strat in strategies:
        if len(attempts) >= max_total_attempts:
            break
        # Skip baseline-dependent strategies if no baseline.
        if strat in (FallbackStrategy.EDIT_BASELINE, FallbackStrategy.VARIANTS_REFINE):
            if not baseline_screen_id:
                continue

        chosen_model = (
            flash_model_id
            if strat == FallbackStrategy.FLASH_SAFETY_NET
            else model_id
        )

        out = await _run_strategy(
            ops,
            strat,
            project_id=project_id,
            prompt=prompt,
            device_type=device_type,
            model_id=chosen_model,
            baseline_screen_id=baseline_screen_id,
            attempts=attempts,
        )
        if out is not None:
            if strat == FallbackStrategy.FLASH_SAFETY_NET:
                last_err = next(
                    (a["error"] for a in attempts if a.get("error")),
                    "PRO chain exhausted",
                )
                return FallbackResult(
                    outcome=FallbackOutcome.OK_DEGRADED,
                    final_strategy=strat.value,
                    model_used=flash_model_id,
                    attempts=attempts,
                    result=out,
                    degraded=True,
                    degraded_reason=last_err,
                )
            return FallbackResult(
                outcome=FallbackOutcome.OK_AFTER_FALLBACK,
                final_strategy=strat.value,
                model_used=chosen_model,
                attempts=attempts,
                result=out,
            )

    return FallbackResult(
        outcome=FallbackOutcome.FAILED,
        final_strategy=attempts[-1]["strategy"] if attempts else "none",
        model_used=model_id,
        attempts=attempts,
        error=attempts[-1]["error"] if attempts else "no attempts recorded",
    )


# ── Strategy executor ──────────────────────────────────────────────────


async def _run_strategy(
    ops: StitchOps,
    strat: FallbackStrategy,
    *,
    project_id: str,
    prompt: str,
    device_type: str,
    model_id: str,
    baseline_screen_id: str | None,
    attempts: list[dict],
) -> Any | None:
    """Execute one strategy. Returns the result on success or None on
    failure (and appends an entry to ``attempts``)."""

    started_at = time.time()
    entry: dict = {
        "strategy": strat.value,
        "model": model_id,
        "started_at": started_at,
    }
    try:
        if strat == FallbackStrategy.EDIT_BASELINE:
            assert baseline_screen_id
            res = await ops.edit_screens(
                project_id, baseline_screen_id, prompt, model_id=model_id
            )
        elif strat == FallbackStrategy.VARIANTS_REFINE:
            assert baseline_screen_id
            res = await ops.generate_variants(
                project_id,
                baseline_screen_id,
                prompt=prompt,
                variant_count=1,
                creative_range="REFINE",
            )
        else:
            # REGENERATE and FLASH_SAFETY_NET both call generate_screen,
            # only model_id differs.
            res = await ops.generate_screen(
                project_id,
                prompt,
                device_type=device_type,
                model_id=model_id,
            )
        entry["status"] = "ok"
        entry["duration_s"] = round(time.time() - started_at, 3)
        attempts.append(entry)
        return res
    except BaseException as exc:  # noqa: BLE001 — orchestration boundary
        entry["status"] = "error"
        entry["error"] = str(exc)
        entry["error_type"] = type(exc).__name__
        entry["error_class"] = classify_error(exc)
        entry["duration_s"] = round(time.time() - started_at, 3)
        attempts.append(entry)
        return None
