"""Multi-screen build orchestration with batching and unified theme pass.

Stitch has no ``build_site`` tool: each screen is generated with
``generate_screen_from_text``, batch by batch (groups of ≤``batch_size``
by explicit group, route prefix or order), and a final ``edit_screens``
call over every generated screen unifies the theme (UC-8504). Until
UC-8504 this module called ``ops.build_site``, which the client adapter
never had, so every batch failed while the tool answered ``status: ok``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from ..stitch_enums import DEFAULT_MODEL


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

    async def generate_screen(
        self,
        project_id: str,
        prompt: str,
        *,
        device_type: str = "DESKTOP",
        model_id: str = DEFAULT_MODEL,
    ) -> Any: ...

    async def edit_screens(
        self,
        project_id: str,
        screen_id: str | list[str],
        prompt: str,
        *,
        device_type: str | None = None,
        model_id: str | None = None,
    ) -> Any: ...


def generated_screen_ids(result: Any) -> list[str]:
    """Bare ids of the screens a generate/edit answer created."""
    ids: list[str] = []
    components = result.get("outputComponents") or [] if isinstance(result, dict) else []
    for comp in components:
        for screen in (comp.get("design") or {}).get("screens") or []:
            name = screen.get("id") or screen.get("name") or ""
            if name:
                ids.append(name.rsplit("/screens/", 1)[-1])
    return ids


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
    model_id: str = DEFAULT_MODEL,
) -> dict:
    """Generate every screen, batch by batch, and unify the theme at the end.

    Each spec is one ``generate_screen`` call (Stitch has no ``build_site``).
    A failed screen is recorded with its error and the build goes on; the
    batch is ``ok`` only if all its screens were generated. The unifying
    pass is one ``edit_screens`` over every generated screen
    (``selectedScreenIds``).

    Returns ``{batches, failed_screens, generated_screen_ids, unified_pass,
    unified_pass_applied, total_screens, total_batches}``.
    """

    plan = plan_build(
        specs, batch_size=batch_size, apply_unified_theme_pass=apply_unified_theme_pass
    )
    batch_results: list[BatchResult] = []
    all_screen_ids: list[str] = []
    failed: list[dict] = []

    for i, batch in enumerate(plan.batches):
        started = time.time()
        screens: list[dict] = []
        for spec in batch:
            try:
                res = await ops.generate_screen(
                    project_id, spec.prompt, device_type=device_type, model_id=model_id
                )
                ids = generated_screen_ids(res)
                all_screen_ids.extend(ids)
                screens.append({"name": spec.name, "status": "ok", "screen_ids": ids})
            except BaseException as exc:  # noqa: BLE001 — orchestration boundary
                entry = {"name": spec.name, "status": "error", "error": str(exc)}
                screens.append(entry)
                failed.append(entry)
        errors = [s for s in screens if s["status"] == "error"]
        batch_results.append(
            BatchResult(
                index=i,
                screens=[s.name for s in batch],
                duration_s=round(time.time() - started, 3),
                status="ok" if not errors else "error",
                error="; ".join(f"{s['name']}: {s['error']}" for s in errors) or None,
                result=screens,
            )
        )

    unified: list[dict] = []
    if plan.unified_pass_planned and len(all_screen_ids) > 1:
        started = time.time()
        try:
            await ops.edit_screens(
                project_id, list(all_screen_ids), unified_theme_prompt, model_id=model_id
            )
            unified.append(
                {
                    "screen_ids": list(all_screen_ids),
                    "status": "ok",
                    "duration_s": round(time.time() - started, 3),
                }
            )
        except BaseException as exc:  # noqa: BLE001
            unified.append(
                {
                    "screen_ids": list(all_screen_ids),
                    "status": "error",
                    "duration_s": round(time.time() - started, 3),
                    "error": str(exc),
                }
            )

    return {
        "batches": [_batch_to_dict(b) for b in batch_results],
        "failed_screens": failed,
        "generated_screen_ids": all_screen_ids,
        "unified_pass": unified,
        "unified_pass_applied": any(u["status"] == "ok" for u in unified),
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
        "results": b.result,
    }
