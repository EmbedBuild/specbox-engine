"""Tier 2 — Milestone & Multirepo tools (v5.23.0 Full Mutations).

8 tools: 7 granular + 1 batch. Zero new ABC methods (confirmed during
S2 impl — satellite queue filtering works client-side via list_items).

See doc/design/v5.23.0-full-mutations.md section "Tier 2".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_session_backend
from ..spec_backend import ItemDTO, parse_item_id
from . import _mutation_helpers as mh

logger = structlog.get_logger(__name__)


# ── Internals ────────────────────────────────────────────────────────


def _mk_error(code: str, message: str, **ctx: Any) -> dict[str, Any]:
    payload = {"error": message, "code": code}
    payload.update(ctx)
    return payload


def _get_uc_id(item: ItemDTO) -> str:
    return item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]


def _is_uc(item: ItemDTO) -> bool:
    return "UC" in item.labels


async def _all_ucs(backend, board_id: str) -> list[ItemDTO]:
    items = await backend.list_items(board_id)
    return [i for i in items if _is_uc(i)]


async def _ac_counts(backend, board_id: str, ucs: list[ItemDTO]) -> dict[str, int]:
    """Return {uc_id: ac_count} for a list of UC items."""
    counts: dict[str, int] = {}
    for uc in ucs:
        uc_id = _get_uc_id(uc)
        if not uc_id:
            continue
        try:
            acs = await backend.get_acceptance_criteria(board_id, uc.id)
            counts[uc_id] = len(acs)
        except Exception:
            counts[uc_id] = 0
    return counts


async def _ac_done_counts(backend, board_id: str, ucs: list[ItemDTO]) -> dict[str, tuple[int, int]]:
    """Return {uc_id: (total, done)} for a list of UC items."""
    counts: dict[str, tuple[int, int]] = {}
    for uc in ucs:
        uc_id = _get_uc_id(uc)
        if not uc_id:
            continue
        try:
            acs = await backend.get_acceptance_criteria(board_id, uc.id)
            counts[uc_id] = (len(acs), sum(1 for a in acs if a.done))
        except Exception:
            counts[uc_id] = (0, 0)
    return counts


def _read_multirepo_settings(path: str | Path | None) -> dict[str, Any]:
    """Read multirepo config from orchestrator's settings.local.json.

    Returns {} if not found or malformed.
    """
    if not path:
        return {}
    p = Path(path) / ".claude" / "settings.local.json" if Path(path).is_dir() else Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get("multirepo", {}) if isinstance(data, dict) else {}


# ── 2.1 set_uc_milestone ─────────────────────────────────────────────


async def set_uc_milestone(
    board_id: str,
    uc_id: str,
    milestone: str,
    ctx: Context,
) -> dict[str, Any]:
    """Assign a milestone (H1|H2|H3|H4) to a UC and report new distribution.

    Shortcut over `update_uc(milestone=...)` that additionally returns the
    full distribution after the assignment. Use `set_uc_milestone_batch` for
    assigning milestones to many UCs in one call.

    Returns:
        {uc_id, milestone, previous_milestone, distribution, total_acs}
    """
    backend = await get_session_backend(ctx)
    try:
        ok, err = mh.validate_milestone(milestone)
        if not ok:
            return _mk_error("INVALID_MILESTONE", err or "invalid milestone")

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found", uc_id=uc_id)

        previous = uc_item.meta.get("milestone")

        if previous != milestone:
            merged, _ = mh.merge_meta(uc_item.meta, {"milestone": milestone})
            await backend.update_item(board_id, uc_item.id, meta=merged)

        ucs = await _all_ucs(backend, board_id)
        # Update the in-memory copy so distribution reflects the change
        for u in ucs:
            if _get_uc_id(u) == uc_id:
                u.meta["milestone"] = milestone
        ac_cnt = await _ac_counts(backend, board_id, ucs)
        dist = mh.compute_distribution(ucs, ac_cnt)
        total_acs = sum(v for v in ac_cnt.values())

        return {
            "uc_id": uc_id,
            "milestone": milestone,
            "previous_milestone": previous,
            "distribution": dist,
            "total_acs": total_acs,
        }
    finally:
        await backend.close()


# ── 2.2 set_uc_milestone_batch ────────────────────────────────────────


async def set_uc_milestone_batch(
    board_id: str,
    assignments: list[dict[str, Any]],
    ctx: Context,
) -> dict[str, Any]:
    """Assign milestones to many UCs in a single MCP call.

    Primary use case: assigning H1..H4 to all UCs on a newly-planned board
    (e.g. 27 UCs of potencial_digital_2026 in one call). For a single UC
    use `set_uc_milestone`.

    Each entry: {"uc_id": str, "milestone": str}.

    Returns:
        {total, succeeded:[{uc_id, milestone, previous}], failed:[...], final_distribution}
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)
        by_uc: dict[str, ItemDTO] = {}
        for item in items:
            uid = _get_uc_id(item)
            if uid and _is_uc(item):
                by_uc[uid] = item

        succeeded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for entry in assignments:
            uc_id = entry.get("uc_id", "")
            ms = entry.get("milestone", "")
            if not uc_id or not ms:
                failed.append({"uc_id": uc_id, "error": "missing uc_id/milestone", "code": "VALIDATION_FAILED"})
                continue
            ok, err = mh.validate_milestone(ms)
            if not ok:
                failed.append({"uc_id": uc_id, "error": err, "code": "INVALID_MILESTONE"})
                continue
            uc_item = by_uc.get(uc_id)
            if not uc_item:
                failed.append({"uc_id": uc_id, "error": "not found", "code": "UC_NOT_FOUND"})
                continue

            previous = uc_item.meta.get("milestone")
            if previous == ms:
                succeeded.append({"uc_id": uc_id, "milestone": ms, "previous": previous, "reason": "no_change"})
                continue

            try:
                merged, _ = mh.merge_meta(uc_item.meta, {"milestone": ms})
                await backend.update_item(board_id, uc_item.id, meta=merged)
                uc_item.meta["milestone"] = ms
                succeeded.append({"uc_id": uc_id, "milestone": ms, "previous": previous})
            except Exception as e:
                failed.append({"uc_id": uc_id, "error": str(e), "code": "BACKEND_ERROR"})

        # Final distribution
        all_ucs = [i for i in items if _is_uc(i)]
        ac_cnt = await _ac_counts(backend, board_id, all_ucs)
        dist = mh.compute_distribution(all_ucs, ac_cnt)

        return {
            "total": len(assignments),
            "succeeded": succeeded,
            "failed": failed,
            "final_distribution": dist,
        }
    finally:
        await backend.close()


# ── 2.3 set_uc_satellite ─────────────────────────────────────────────


async def set_uc_satellite(
    board_id: str,
    uc_id: str,
    satellite: str,
    ctx: Context,
) -> dict[str, Any]:
    """Assign a UC to a satellite repo.

    Validates that `satellite` is a declared key in the orchestrator's
    settings.local.json → multirepo.satellites. If no config is found,
    any non-empty string is accepted (freeform projects).

    For assigning a UC milestone, use `set_uc_milestone` instead. For
    batch satellite assignment, use `update_uc_batch(satellite=...)`.

    Returns:
        {uc_id, satellite, previous_satellite, updated_at}
    """
    backend = await get_session_backend(ctx)
    try:
        ok, err = mh.validate_satellite(satellite, mh.settings_path_from_env())
        if not ok:
            return _mk_error("INVALID_SATELLITE", err or "invalid satellite")

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found", uc_id=uc_id)

        previous = uc_item.meta.get("satellite")
        if previous == satellite:
            return {
                "uc_id": uc_id,
                "satellite": satellite,
                "previous_satellite": previous,
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
            }

        merged, _ = mh.merge_meta(uc_item.meta, {"satellite": satellite})
        await backend.update_item(board_id, uc_item.id, meta=merged)
        return {
            "uc_id": uc_id,
            "satellite": satellite,
            "previous_satellite": previous,
            "updated_at": mh.utc_now_iso(),
        }
    finally:
        await backend.close()


# ── 2.4 get_milestone_status ─────────────────────────────────────────


async def get_milestone_status(
    board_id: str,
    milestone: str,
    ctx: Context,
) -> dict[str, Any]:
    """Sprint status filtered by milestone.

    Use `get_sprint_status` (existing spec-driven tool) for an unfiltered
    board-wide view. This tool narrows to a single milestone's UCs.

    Returns:
        {milestone, total_ucs, done_ucs, in_progress_ucs, review_ucs,
         backlog_ucs, total_acs, passed_acs, ac_pass_rate, blocked}
    """
    backend = await get_session_backend(ctx)
    try:
        ok, err = mh.validate_milestone(milestone)
        if not ok:
            return _mk_error("INVALID_MILESTONE", err or "invalid milestone")

        ucs = await _all_ucs(backend, board_id)
        filtered = [u for u in ucs if u.meta.get("milestone") == milestone]

        done = in_progress = review = backlog = 0
        blocked: list[dict[str, str]] = []
        total_acs = passed_acs = 0

        for uc in filtered:
            state = uc.state.lower() if uc.state else ""
            if state == "done":
                done += 1
            elif state == "in_progress":
                in_progress += 1
            elif state == "review":
                review += 1
            else:
                backlog += 1

            if "Bloqueado" in uc.labels or "bloqueado" in [l.lower() for l in uc.labels]:
                blocked.append({"uc_id": _get_uc_id(uc), "reason": "Bloqueado label"})

            try:
                acs = await backend.get_acceptance_criteria(board_id, uc.id)
                total_acs += len(acs)
                passed_acs += sum(1 for a in acs if a.done)
            except Exception:
                pass

        rate = round(passed_acs / total_acs, 4) if total_acs else 0.0

        return {
            "milestone": milestone,
            "total_ucs": len(filtered),
            "done_ucs": done,
            "in_progress_ucs": in_progress,
            "review_ucs": review,
            "backlog_ucs": backlog,
            "total_acs": total_acs,
            "passed_acs": passed_acs,
            "ac_pass_rate": rate,
            "blocked": blocked,
        }
    finally:
        await backend.close()


# ── 2.5 rebalance_milestones ─────────────────────────────────────────


async def rebalance_milestones(
    board_id: str,
    ctx: Context,
    *,
    target_distribution: dict[str, float] | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Suggest UC moves to align real AC distribution with targets.

    Default target: H1=30%, H2=25%, H3=25%, H4=20%.
    `dry_run=True` (default) only returns suggestions. `dry_run=False`
    applies them via internal milestone updates.

    Do NOT use this for initial milestone assignment — use
    `set_uc_milestone_batch` for that. This tool is for rebalancing an
    already-assigned board.

    Returns:
        {current_distribution, target_distribution, suggested_moves,
         projected_distribution, deviations_pct}
    """
    backend = await get_session_backend(ctx)
    try:
        targets = target_distribution or dict(mh.DEFAULT_MILESTONE_TARGETS)

        ucs = await _all_ucs(backend, board_id)
        ac_cnt = await _ac_counts(backend, board_id, ucs)
        current_dist = mh.compute_distribution(ucs, ac_cnt)
        total_acs = sum(v for v in ac_cnt.values())

        if total_acs == 0:
            return {
                "current_distribution": current_dist,
                "target_distribution": targets,
                "suggested_moves": [],
                "projected_distribution": current_dist,
                "deviations_pct": {m: 0.0 for m in mh.MILESTONES},
            }

        # Greedy: sort UCs by AC count descending, reassign to milestone with
        # the largest remaining gap to target.
        milestone_ucs = [u for u in ucs if u.meta.get("milestone") in mh.MILESTONES]
        sorted_ucs = sorted(
            milestone_ucs,
            key=lambda u: ac_cnt.get(_get_uc_id(u), 0),
            reverse=True,
        )

        # Budget per milestone in ACs
        budgets = {m: round(targets.get(m, 0.0) * total_acs) for m in mh.MILESTONES}
        filled = {m: 0 for m in mh.MILESTONES}
        moves: list[dict[str, str]] = []
        new_assignments: dict[str, str] = {}

        for uc in sorted_ucs:
            uc_id = _get_uc_id(uc)
            ac = ac_cnt.get(uc_id, 0)
            current_ms = uc.meta.get("milestone", "")

            # Find milestone with largest remaining gap
            best_ms = current_ms
            best_gap = budgets.get(current_ms, 0) - filled.get(current_ms, 0)
            for m in mh.MILESTONES:
                gap = budgets[m] - filled[m]
                if gap > best_gap:
                    best_ms = m
                    best_gap = gap

            filled[best_ms] = filled.get(best_ms, 0) + ac
            new_assignments[uc_id] = best_ms
            if best_ms != current_ms:
                moves.append({
                    "uc_id": uc_id,
                    "from_milestone": current_ms,
                    "to_milestone": best_ms,
                    "reason": f"Rebalance: {current_ms} overfull, {best_ms} had {best_gap} ACs of gap",
                })

        # Apply if not dry_run
        if not dry_run and moves:
            for move in moves:
                uc_item = next(
                    (u for u in ucs if _get_uc_id(u) == move["uc_id"]), None
                )
                if uc_item:
                    merged, _ = mh.merge_meta(uc_item.meta, {"milestone": move["to_milestone"]})
                    try:
                        await backend.update_item(board_id, uc_item.id, meta=merged)
                        uc_item.meta["milestone"] = move["to_milestone"]
                    except Exception:
                        logger.exception("rebalance_apply_failed", uc=move["uc_id"])

        # Projected distribution
        projected_dist = mh.compute_distribution(ucs, ac_cnt)
        deviations = {}
        for m in mh.MILESTONES:
            actual_pct = projected_dist[m]["pct_acs"]
            target_pct = targets.get(m, 0.0)
            deviations[m] = round(actual_pct - target_pct, 4)

        return {
            "current_distribution": current_dist if dry_run else projected_dist,
            "target_distribution": targets,
            "suggested_moves": moves,
            "projected_distribution": projected_dist,
            "deviations_pct": deviations,
        }
    finally:
        await backend.close()


# ── 2.6 get_satellite_queue ──────────────────────────────────────────


async def get_satellite_queue(
    board_id: str,
    satellite: str,
    ctx: Context,
    *,
    milestone: str | None = None,
) -> dict[str, Any]:
    """List UCs assigned to a satellite, in Backlog, optionally filtered by milestone.

    More specific than `find_next_uc`: returns the full ordered queue, not
    just the next one. Use `find_next_uc` with `uc_scope` for single-item
    picking.

    Returns:
        {satellite, milestone, queue:[{uc_id, name, ac_count, hours, dependencies}]}
    """
    backend = await get_session_backend(ctx)
    try:
        if milestone is not None:
            ok, err = mh.validate_milestone(milestone)
            if not ok:
                return _mk_error("INVALID_MILESTONE", err or "invalid milestone")

        ucs = await _all_ucs(backend, board_id)
        ac_cnt = await _ac_counts(backend, board_id, ucs)

        filtered = [
            u for u in ucs
            if u.meta.get("satellite") == satellite
            and u.state in ("backlog", "")
        ]
        if milestone is not None:
            filtered = [u for u in filtered if u.meta.get("milestone") == milestone]

        queue: list[dict[str, Any]] = []
        for uc in filtered:
            uc_id = _get_uc_id(uc)
            links = uc.meta.get("links", [])
            deps = [
                lnk.get("target_uc_id", "")
                for lnk in links
                if isinstance(lnk, dict) and lnk.get("type") in ("depends_on", "blocks")
            ]
            queue.append({
                "uc_id": uc_id,
                "name": uc.name,
                "ac_count": ac_cnt.get(uc_id, 0),
                "hours": uc.meta.get("horas"),
                "dependencies": deps,
            })

        return {
            "satellite": satellite,
            "milestone": milestone,
            "queue": queue,
        }
    finally:
        await backend.close()


# ── 2.7 sync_multirepo_state ─────────────────────────────────────────


async def sync_multirepo_state(
    orchestrator_path: str,
    ctx: Context,
) -> dict[str, Any]:
    """Propagate satellite labels from orchestrator settings to board cards.

    Reads settings.local.json → multirepo.satellites, looks at each UC's
    name prefix or explicit `satellite` meta, and assigns the satellite key
    to UCs that don't have one yet. UCs with an existing satellite are
    never overwritten.

    Useful after restructuring a repo from mono to multi.

    Returns:
        {updated_ucs, skipped_ucs, board_id}
    """
    backend = await get_session_backend(ctx)
    try:
        mr_config = _read_multirepo_settings(orchestrator_path)
        satellites = mr_config.get("satellites", {})
        if not isinstance(satellites, dict) or not satellites:
            return _mk_error(
                "VALIDATION_FAILED",
                "No multirepo.satellites found in orchestrator settings",
            )

        # Build prefix → satellite_key mapping
        prefix_map: dict[str, str] = {}
        for sat_key, sat_cfg in satellites.items():
            prefix = sat_cfg.get("uc_prefix", "")
            if prefix:
                prefix_map[prefix.upper()] = sat_key

        # Get board_id from backend config or from the first item
        items = await backend.list_items("")
        if not items:
            return _mk_error("VALIDATION_FAILED", "Board is empty — no items to sync")

        board_id = ""
        ucs = [i for i in items if _is_uc(i)]

        updated: list[str] = []
        skipped: list[str] = []

        for uc in ucs:
            uc_id = _get_uc_id(uc)
            if not uc_id:
                continue

            if uc.meta.get("satellite"):
                skipped.append(uc_id)
                continue

            # Try prefix matching (e.g. UC name starts with "API-" or "[API-")
            assigned = None
            name_upper = uc.name.upper()
            for prefix, sat_key in prefix_map.items():
                if name_upper.startswith(prefix) or name_upper.startswith(f"[{prefix}"):
                    assigned = sat_key
                    break

            if not assigned:
                skipped.append(uc_id)
                continue

            merged, changed = mh.merge_meta(uc.meta, {"satellite": assigned})
            if changed:
                try:
                    await backend.update_item("", uc.id, meta=merged)
                    uc.meta["satellite"] = assigned
                    updated.append(uc_id)
                except Exception:
                    logger.exception("sync_multirepo_failed", uc=uc_id)
                    skipped.append(uc_id)
            else:
                skipped.append(uc_id)

        return {
            "updated_ucs": updated,
            "skipped_ucs": skipped,
            "board_id": board_id,
        }
    finally:
        await backend.close()


# ── 2.8 get_cross_repo_dependencies ──────────────────────────────────

_UC_REF_RE = re.compile(r"UC-\d{3}")


async def get_cross_repo_dependencies(
    board_id: str,
    ctx: Context,
) -> dict[str, Any]:
    """Detect UCs that reference UCs in a different satellite.

    Scans each UC's description, context meta, and links for UC-NNN
    references. Flags as a cross-repo dependency when the referenced UC
    belongs to a different satellite.

    Returns:
        {dependencies: [{uc_id, depends_on, satellite_from, satellite_to,
          dependency_type, blocks_milestone}]}
    """
    backend = await get_session_backend(ctx)
    try:
        ucs = await _all_ucs(backend, board_id)
        sat_map: dict[str, str] = {}
        ms_map: dict[str, str | None] = {}
        for uc in ucs:
            uc_id = _get_uc_id(uc)
            if uc_id:
                sat_map[uc_id] = uc.meta.get("satellite", "")
                ms_map[uc_id] = uc.meta.get("milestone")

        deps: list[dict[str, Any]] = []

        for uc in ucs:
            uc_id = _get_uc_id(uc)
            if not uc_id:
                continue
            my_sat = sat_map.get(uc_id, "")

            # Gather referenced UC ids from description + context + links
            refs: set[str] = set()
            text_blob = (uc.description or "") + " " + str(uc.meta.get("context", ""))
            for match in _UC_REF_RE.findall(text_blob):
                refs.add(match)

            links = uc.meta.get("links", [])
            for lnk in links:
                if isinstance(lnk, dict):
                    target = lnk.get("target_uc_id", "")
                    if target:
                        refs.add(target)

            for ref_uc_id in refs:
                if ref_uc_id == uc_id:
                    continue
                ref_sat = sat_map.get(ref_uc_id, "")
                if my_sat and ref_sat and my_sat != ref_sat:
                    dep_type = "depends_on"
                    for lnk in links:
                        if isinstance(lnk, dict) and lnk.get("target_uc_id") == ref_uc_id:
                            dep_type = lnk.get("type", "depends_on")
                            break
                    deps.append({
                        "uc_id": uc_id,
                        "depends_on": ref_uc_id,
                        "satellite_from": my_sat,
                        "satellite_to": ref_sat,
                        "dependency_type": dep_type,
                        "blocks_milestone": ms_map.get(uc_id),
                    })

        return {"dependencies": deps}
    finally:
        await backend.close()


# ── Registration ─────────────────────────────────────────────────────


def register_milestone_management_tools(mcp_instance) -> None:
    """Register the 8 Tier 2 milestone & multirepo tools."""
    mcp_instance.tool(
        description="Assign a milestone (H1-H4) to a UC and return updated distribution. "
        "For batch assignment use set_uc_milestone_batch."
    )(set_uc_milestone)
    mcp_instance.tool(
        description="Assign milestones to many UCs in one call. Primary use case: initial "
        "milestone assignment of all UCs on a newly-planned board."
    )(set_uc_milestone_batch)
    mcp_instance.tool(
        description="Assign a UC to a satellite repo. Validates the satellite key against "
        "the orchestrator's multirepo settings."
    )(set_uc_satellite)
    mcp_instance.tool(
        description="Sprint status filtered by milestone: UC counts by state, AC pass rate, "
        "blocked items. For board-wide view use get_sprint_status."
    )(get_milestone_status)
    mcp_instance.tool(
        description="Suggest UC moves to align AC distribution with target percentages. "
        "dry_run=True (default) only returns suggestions."
    )(rebalance_milestones)
    mcp_instance.tool(
        description="List UCs assigned to a satellite repo, in Backlog, optionally filtered "
        "by milestone. Returns the full ordered queue."
    )(get_satellite_queue)
    mcp_instance.tool(
        description="Propagate satellite labels from orchestrator settings.local.json to board "
        "cards without a satellite assigned."
    )(sync_multirepo_state)
    mcp_instance.tool(
        description="Detect cross-satellite UC dependencies by scanning descriptions, context, "
        "and links for UC-NNN references to UCs in different satellites."
    )(get_cross_repo_dependencies)
