"""Multi-screen build orchestration with batching and unified theme pass.

Stitch's ``build_site`` is reliable up to about 5 connected screens per
call (community-reported). Beyond that, the call either fails outright
or returns inconsistent geometry. This module partitions screens into
groups of ≤``batch_size`` and applies a final ``edit_screens`` pass that
unifies the theme across all generated screens.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol


# ── Inputs ──────────────────────────────────────────────────────────────


@dataclass
class ScreenSpec:
    """One screen request inside a multi-screen build."""

    name: str
    prompt: str
    route: str = "/"
    order: int = 0
    group: str | None = None  # explicit grouping wins over route prefix


# ── Outputs ─────────────────────────────────────────────────────────────


@dataclass
class BatchResult:
    index: int
    screens: list[str]  # screen names in this batch
    duration_s: float
    status: str  # ok | error
    error: str | None = None
    result: Any = None


@dataclass
class BatchPlan:
    batches: list[list[ScreenSpec]]
    unified_pass_planned: bool


# ── Partition logic ────────────────────────────────────────────────────


def partition_screens(
    specs: list[ScreenSpec], *, batch_size: int = 4
) -> list[list[ScreenSpec]]:
    """Group screens into batches of ≤``batch_size``.

    Priority:
    1. Explicit ``group`` tag (all specs with the same group go together).
    2. Route prefix (everything under ``/admin/`` groups).
    3. Order chunks of ``batch_size`` from ``order``-sorted list.
    """

    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if not specs:
        return []
    if len(specs) <= batch_size:
        return [list(sorted(specs, key=lambda s: s.order))]

    # Bucket by group first.
    explicit: dict[str, list[ScreenSpec]] = {}
    no_group: list[ScreenSpec] = []
    for s in specs:
        if s.group:
            explicit.setdefault(s.group, []).append(s)
        else:
            no_group.append(s)

    # For un-grouped, try to bucket by route prefix.
    by_prefix: dict[str, list[ScreenSpec]] = {}
    for s in no_group:
        prefix = _route_prefix(s.route)
        by_prefix.setdefault(prefix, []).append(s)

    # Merge buckets that exceed batch_size into chunks.
    batches: list[list[ScreenSpec]] = []
    for bucket in list(explicit.values()) + list(by_prefix.values()):
        bucket.sort(key=lambda s: s.order)
        for i in range(0, len(bucket), batch_size):
            batches.append(bucket[i : i + batch_size])

    return batches


def _route_prefix(route: str) -> str:
    """Return the first non-empty path segment, or ``/`` for the root."""
    parts = [p for p in route.split("/") if p]
    return f"/{parts[0]}" if parts else "/"


# ── Build operation protocol ───────────────────────────────────────────


class BuildOps(Protocol):
    """The minimal operations the batched build needs."""

    async def build_site(
        self, project_id: str, routes: list[dict[str, str]]
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

    async def generate_screen(
        self,
        project_id: str,
        prompt: str,
        *,
        device_type: str = "DESKTOP",
        model_id: str = "GEMINI_3_PRO",
    ) -> Any: ...


# ── Plan + execute ─────────────────────────────────────────────────────


def plan_build(
    specs: list[ScreenSpec],
    *,
    batch_size: int = 4,
    apply_unified_theme_pass: bool = True,
) -> BatchPlan:
    return BatchPlan(
        batches=partition_screens(specs, batch_size=batch_size),
        unified_pass_planned=apply_unified_theme_pass and len(specs) > batch_size,
    )


async def build_site_batched(
    ops: BuildOps,
    project_id: str,
    specs: list[ScreenSpec],
    *,
    batch_size: int = 4,
    apply_unified_theme_pass: bool = True,
    unified_theme_prompt: str = (
        "Standardize headers, navigation, footers, and primary buttons across "
        "all selected screens to match DESIGN.md component patterns. "
        "Preserve content and layout of each screen."
    ),
    device_type: str = "DESKTOP",
    model_id: str = "GEMINI_3_PRO",
) -> dict:
    """Run ``ops.build_site`` in batches and apply a final unifying pass.

    Returns ``{batches, unified_pass, total_screens}``.
    """

    plan = plan_build(
        specs, batch_size=batch_size, apply_unified_theme_pass=apply_unified_theme_pass
    )
    batch_results: list[BatchResult] = []
    all_screen_ids: list[str] = []

    for i, batch in enumerate(plan.batches):
        started = time.time()
        try:
            routes_payload = [
                {"screenId": s.name, "route": s.route, "prompt": s.prompt}
                for s in batch
            ]
            res = await ops.build_site(project_id, routes_payload)
            batch_results.append(
                BatchResult(
                    index=i,
                    screens=[s.name for s in batch],
                    duration_s=round(time.time() - started, 3),
                    status="ok",
                    result=res,
                )
            )
            # Best-effort: pull screen ids from the result if present.
            for s in batch:
                all_screen_ids.append(s.name)
        except BaseException as exc:  # noqa: BLE001 — orchestration boundary
            batch_results.append(
                BatchResult(
                    index=i,
                    screens=[s.name for s in batch],
                    duration_s=round(time.time() - started, 3),
                    status="error",
                    error=str(exc),
                )
            )

    # Optional unifying pass: edit_screens on the first generated screen
    # with a multi-target hint. The native multi-select is not exposed
    # in the current MCP surface, so we approximate by editing each
    # screen individually with the same prompt — still strictly cheaper
    # than regenerating from scratch, and produces a consistent result.
    unified: list[dict] = []
    if plan.unified_pass_planned and any(b.status == "ok" for b in batch_results):
        for screen_id in all_screen_ids:
            started = time.time()
            try:
                await ops.edit_screens(
                    project_id, screen_id, unified_theme_prompt
                )
                unified.append(
                    {
                        "screen_id": screen_id,
                        "status": "ok",
                        "duration_s": round(time.time() - started, 3),
                    }
                )
            except BaseException as exc:  # noqa: BLE001
                unified.append(
                    {
                        "screen_id": screen_id,
                        "status": "error",
                        "duration_s": round(time.time() - started, 3),
                        "error": str(exc),
                    }
                )

    return {
        "batches": [_batch_to_dict(b) for b in batch_results],
        "unified_pass": unified,
        "unified_pass_applied": bool(unified),
        "total_screens": len(specs),
        "total_batches": len(plan.batches),
    }


def _batch_to_dict(b: BatchResult) -> dict:
    return {
        "index": b.index,
        "screens": b.screens,
        "duration_s": b.duration_s,
        "status": b.status,
        "error": b.error,
    }
