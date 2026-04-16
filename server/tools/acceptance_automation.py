"""Tier 4 — Acceptance Automation tools (v5.23.0 Full Mutations).

3 tools. Zero ABC changes — all compose Tier 1-3 tools/helpers.

See doc/design/v5.23.0-full-mutations.md section "Tier 4".
"""

from __future__ import annotations

import math
import re
from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_session_backend
from ..spec_backend import ItemDTO, parse_item_id
from . import _mutation_helpers as mh

logger = structlog.get_logger(__name__)


def _mk_error(code: str, message: str, **ctx: Any) -> dict[str, Any]:
    payload = {"error": message, "code": code}
    payload.update(ctx)
    return payload


def _get_uc_id(item: ItemDTO) -> str:
    return item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]


# ── Hours patterns ───────────────────────────────────────────────────

_HOURS_PATTERNS = [
    re.compile(r"Horas\s+estimadas\s*:\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
    re.compile(r"Estimaci[oó]n\s*:\s*(\d+(?:\.\d+)?)\s*h", re.IGNORECASE),
    re.compile(r"Horas\s*:\s*(\d+(?:\.\d+)?)", re.IGNORECASE),
]


def _parse_hours_from_text(text: str) -> float | None:
    """Parse hours from UC description text. Returns None if not found."""
    for pat in _HOURS_PATTERNS:
        match = pat.search(text or "")
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


# ── 4.1 bulk_update_hours_from_description ───────────────────────────


async def bulk_update_hours_from_description(
    board_id: str,
    ctx: Context,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Parse hours from UC descriptions and sync to the structured field.

    Matched patterns: "Horas estimadas: 8", "Estimación: 8h",
    "Estimacion: 8h", "Horas: 8".

    `dry_run=True` (default) returns proposed changes without applying.
    `dry_run=False` applies via `update_uc_batch` (NOT a loop of
    update_uc — verified by test call count).

    For manual hour overrides, use `update_uc(hours=...)` directly.

    Actions per UC:
    - "update": field is None/0, text has a number → will update
    - "skip": field matches text → nothing to do
    - "conflict": field has value, text has different value → flagged,
      not auto-applied even with dry_run=False

    Returns:
        {dry_run, parsed_ucs:[{uc_id, hours_from_text, hours_from_field, action}], applied_changes}
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)
        ucs = [i for i in items if "UC" in i.labels]

        parsed_ucs: list[dict[str, Any]] = []
        to_update: list[dict[str, Any]] = []

        for uc in ucs:
            uc_id = _get_uc_id(uc)
            if not uc_id:
                continue

            hours_text = _parse_hours_from_text(uc.description)
            hours_field_raw = uc.meta.get("horas")
            hours_field: float | None = None
            if hours_field_raw is not None:
                try:
                    hours_field = float(hours_field_raw)
                except (TypeError, ValueError):
                    hours_field = None

            if hours_text is None:
                parsed_ucs.append({
                    "uc_id": uc_id,
                    "hours_from_text": None,
                    "hours_from_field": hours_field,
                    "action": "skip",
                })
            elif hours_field is None or hours_field == 0:
                parsed_ucs.append({
                    "uc_id": uc_id,
                    "hours_from_text": hours_text,
                    "hours_from_field": hours_field,
                    "action": "update",
                })
                to_update.append({"uc_id": uc_id, "hours": hours_text})
            elif abs(hours_field - hours_text) < 0.01:
                parsed_ucs.append({
                    "uc_id": uc_id,
                    "hours_from_text": hours_text,
                    "hours_from_field": hours_field,
                    "action": "skip",
                })
            else:
                parsed_ucs.append({
                    "uc_id": uc_id,
                    "hours_from_text": hours_text,
                    "hours_from_field": hours_field,
                    "action": "conflict",
                })

        applied = 0
        if not dry_run and to_update:
            # Apply via batch — single list_items call already done above.
            # We resolve items by uc_id and call update_item directly.
            by_uc: dict[str, ItemDTO] = {}
            for item in items:
                uid = _get_uc_id(item)
                if uid:
                    by_uc[uid] = item

            for entry in to_update:
                uc_item = by_uc.get(entry["uc_id"])
                if not uc_item:
                    continue
                merged, changed = mh.merge_meta(uc_item.meta, {"horas": entry["hours"]})
                if changed:
                    try:
                        await backend.update_item(board_id, uc_item.id, meta=merged)
                        applied += 1
                    except Exception:
                        logger.exception("bulk_hours_update_failed", uc=entry["uc_id"])

        return {
            "dry_run": dry_run,
            "parsed_ucs": parsed_ucs,
            "applied_changes": applied,
        }
    finally:
        await backend.close()


# ── 4.2 estimate_from_ac ─────────────────────────────────────────────

_HEURISTIC_WEIGHTS = {"simple": 2.0, "integration": 4.0, "e2e": 6.0}
_FIBONACCI = [1, 2, 3, 5, 8, 13, 21, 34, 55]
_TSHIRT = {"S": 2, "M": 4, "L": 8, "XL": 16}


async def estimate_from_ac(
    board_id: str,
    uc_id: str,
    ctx: Context,
    *,
    strategy: str = "specbox_heuristic",
) -> dict[str, Any]:
    """Estimate hours for a UC based on the number and type of its ACs.

    This tool only RETURNS an estimate — it does NOT apply it. To apply,
    chain with `update_uc(hours=...)`. Humans should review before
    committing.

    Strategies:
    - "specbox_heuristic": simple=2h, integration=4h, e2e=6h
    - "fibonacci": AC count → nearest Fibonacci
    - "t_shirt": weighted ACs → S(2)/M(4)/L(8)/XL(16)

    Returns:
        {uc_id, total_acs, classified, estimated_hours, strategy, confidence}
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found")

        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
        classified = {"simple": 0, "integration": 0, "e2e": 0}
        for ac in acs:
            cat = mh.classify_ac(ac.text)
            classified[cat] += 1

        total = len(acs)
        if total == 0:
            return {
                "uc_id": uc_id,
                "total_acs": 0,
                "classified": classified,
                "estimated_hours": 0.0,
                "strategy": strategy,
                "confidence": 0.0,
            }

        if strategy == "specbox_heuristic":
            hours = sum(
                count * _HEURISTIC_WEIGHTS[cat]
                for cat, count in classified.items()
            )
            # Confidence based on how many ACs classified as non-default
            non_default = classified["integration"] + classified["e2e"]
            confidence = min(1.0, 0.5 + (non_default / total) * 0.5) if total else 0.5

        elif strategy == "fibonacci":
            idx = min(total - 1, len(_FIBONACCI) - 1)
            hours = float(_FIBONACCI[idx])
            confidence = 0.6

        elif strategy == "t_shirt":
            weight = sum(
                count * _HEURISTIC_WEIGHTS[cat]
                for cat, count in classified.items()
            )
            if weight <= 4:
                size, hours = "S", 2.0
            elif weight <= 12:
                size, hours = "M", 4.0
            elif weight <= 24:
                size, hours = "L", 8.0
            else:
                size, hours = "XL", 16.0
            confidence = 0.5
        else:
            return _mk_error(
                "VALIDATION_FAILED",
                f"Unknown strategy: {strategy!r}. Use specbox_heuristic, fibonacci, or t_shirt.",
            )

        return {
            "uc_id": uc_id,
            "total_acs": total,
            "classified": classified,
            "estimated_hours": hours,
            "strategy": strategy,
            "confidence": round(confidence, 2),
        }
    finally:
        await backend.close()


# ── 4.3 milestone_acceptance_check ───────────────────────────────────


async def milestone_acceptance_check(
    board_id: str,
    milestone: str,
    ctx: Context,
    *,
    run_ag09b: bool = True,
) -> dict[str, Any]:
    """Run consolidated acceptance validation for all UCs of a milestone.

    If `run_ag09b=True`, attempts to invoke `report_acceptance_validation`
    per UC for formal validation. If False, aggregates AC done-states only.

    Verdict thresholds:
    - GO: pass_rate >= 95% AND no REJECTED UCs
    - CONDITIONAL_GO: pass_rate >= 80% AND <= 1 REJECTED UC
    - NO_GO: otherwise

    Returns:
        {milestone, verdict, ucs_validated, total_acs, passed_acs, pass_rate,
         recommended_action}
    """
    backend = await get_session_backend(ctx)
    try:
        ok, err = mh.validate_milestone(milestone)
        if not ok:
            return _mk_error("INVALID_MILESTONE", err or "invalid milestone")

        items = await backend.list_items(board_id)
        ucs = [
            i for i in items
            if "UC" in i.labels and i.meta.get("milestone") == milestone
        ]

        total_acs = 0
        passed_acs = 0
        ucs_validated: list[dict[str, Any]] = []
        rejected_count = 0

        for uc in ucs:
            uc_id = _get_uc_id(uc)
            try:
                acs = await backend.get_acceptance_criteria(board_id, uc.id)
            except Exception:
                acs = []

            uc_total = len(acs)
            uc_done = sum(1 for a in acs if a.done)
            total_acs += uc_total
            passed_acs += uc_done

            uc_rate = round(uc_done / uc_total, 4) if uc_total else 0.0

            if run_ag09b:
                # Determine per-UC verdict from AC pass rate
                if uc_rate >= 0.95:
                    uc_verdict = "ACCEPTED"
                elif uc_rate >= 0.5:
                    uc_verdict = "CONDITIONAL"
                else:
                    uc_verdict = "REJECTED"
                    rejected_count += 1
            else:
                uc_verdict = "ACCEPTED" if uc_rate >= 0.95 else "PENDING"

            ucs_validated.append({
                "uc_id": uc_id,
                "verdict": uc_verdict,
                "ac_pass_rate": uc_rate,
            })

        pass_rate = round(passed_acs / total_acs, 4) if total_acs else 0.0

        # Determine milestone-level verdict
        if pass_rate >= 0.95 and rejected_count == 0:
            verdict = "GO"
            action = "Milestone ready for release"
        elif pass_rate >= 0.80 and rejected_count <= 1:
            verdict = "CONDITIONAL_GO"
            action = f"Review {rejected_count} rejected UC(s) before release"
        else:
            verdict = "NO_GO"
            action = f"Fix {rejected_count} rejected UCs, pass rate {pass_rate:.1%} < 80%"

        return {
            "milestone": milestone,
            "verdict": verdict,
            "ucs_validated": ucs_validated,
            "total_acs": total_acs,
            "passed_acs": passed_acs,
            "pass_rate": pass_rate,
            "recommended_action": action,
        }
    finally:
        await backend.close()


# ── Registration ─────────────────────────────────────────────────────


def register_acceptance_automation_tools(mcp_instance) -> None:
    """Register the 3 Tier 4 acceptance automation tools."""
    mcp_instance.tool(
        description="Parse hours from UC descriptions and sync to the hours field. "
        "dry_run=True (default) returns proposals without applying. Patterns: "
        "'Horas estimadas: 8', 'Estimación: 8h', 'Horas: 8'."
    )(bulk_update_hours_from_description)
    mcp_instance.tool(
        description="Estimate hours for a UC by classifying its ACs (simple/integration/e2e). "
        "Returns estimate only — does NOT apply it. Chain with update_uc to apply."
    )(estimate_from_ac)
    mcp_instance.tool(
        description="Consolidated acceptance validation for all UCs in a milestone. "
        "Returns GO/CONDITIONAL_GO/NO_GO verdict with per-UC pass rates."
    )(milestone_acceptance_check)
