"""Tier 2 — Multirepo tools (v5.23.0 Full Mutations).

The milestone tools (set_uc_milestone, set_uc_milestone_batch,
get_milestone_status, rebalance_milestones) were removed in v6.23.0
(US-78/UC-7807): epics group the work now.

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
from ._content_passing import returns_items_content
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
        return _parse_multirepo_settings(p.read_text())
    except OSError:
        return {}


def _parse_multirepo_settings(text: str) -> dict[str, Any]:
    """The ``multirepo`` block of a settings.local.json text ({} if malformed)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data.get("multirepo", {}) if isinstance(data, dict) else {}


# ── 2.3 set_uc_satellite ─────────────────────────────────────────────


@returns_items_content
async def set_uc_satellite(
    board_id: str,
    uc_id: str,
    satellite: str,
    ctx: Context,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Assign a UC to a satellite repo.

    Validates that `satellite` is a declared key in the orchestrator's
    settings.local.json → multirepo.satellites. If no config is found,
    any non-empty string is accepted (freeform projects).

    For batch satellite assignment, use `update_uc_batch(satellite=...)`.

    Returns:
        {uc_id, satellite, previous_satellite, updated_at}
    """
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        ok, err = await mh.check_satellite(backend, board_id, satellite)
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


# ── 2.6 get_satellite_queue ──────────────────────────────────────────


async def get_satellite_queue(
    board_id: str,
    satellite: str,
    ctx: Context,
    *,
    items_content: str | None = None,
) -> dict[str, Any]:
    """List UCs assigned to a satellite, in Backlog.

    More specific than `find_next_uc`: returns the full ordered queue, not
    just the next one. Use `find_next_uc` with `uc_scope` for single-item
    picking.

    Returns:
        {satellite, queue:[{uc_id, name, ac_count, hours, dependencies}]}
    """
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        ucs = await _all_ucs(backend, board_id)
        ac_cnt = await _ac_counts(backend, board_id, ucs)

        filtered = [
            u for u in ucs
            if u.meta.get("satellite") == satellite
            and u.state in ("backlog", "")
        ]

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
            "queue": queue,
        }
    finally:
        await backend.close()


# ── 2.7 sync_multirepo_state ─────────────────────────────────────────


@returns_items_content
async def sync_multirepo_state(
    orchestrator_path: str,
    ctx: Context,
    items_content: str | None = None,
    settings_content: str | None = None,
) -> dict[str, Any]:
    """Propagate satellite labels from orchestrator settings to board cards.

    Reads settings.local.json → multirepo.satellites, looks at each UC's
    name prefix or explicit `satellite` meta, and assigns the satellite key
    to UCs that don't have one yet. UCs with an existing satellite are
    never overwritten.

    Useful after restructuring a repo from mono to multi.

    Remote MCP: send the orchestrator's ``.claude/settings.local.json`` as
    ``settings_content``; the server never reads ``orchestrator_path`` there
    (UC-8604).

    Returns:
        {updated_ucs, skipped_ucs, board_id}
    """
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if settings_content is not None:
            mr_config = _parse_multirepo_settings(settings_content)
        else:
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


# ── declare_satellites (US-78 / UC-7803) ─────────────────────────────


async def declare_satellites(
    board_id: str,
    satellites: list[str],
    ctx: Context,
) -> dict[str, Any]:
    """Declare the satellites of a multi-repo project on its board (Native).

    ``set_uc_satellite``, ``update_uc``, ``update_uc_batch`` and ``add_uc``
    validate against this list, also with the remote MCP (which cannot read
    the orchestrator's settings.local.json). Replaces the previous list.

    Returns:
        {board_id, satellites, previous}
    """
    from ..coordination.identity import ForbiddenError, UnauthenticatedError

    backend = await get_session_backend(ctx)
    try:
        previous = await backend.get_board_satellites(board_id)
        stored = await backend.set_board_satellites(board_id, satellites)
        return {"board_id": board_id, "satellites": stored, "previous": previous}
    except NotImplementedError as e:
        return _mk_error("NOT_SUPPORTED", str(e))
    except ValueError as e:
        return _mk_error("VALIDATION_FAILED", str(e))
    except ForbiddenError as e:
        return _mk_error("FORBIDDEN", str(e))
    except UnauthenticatedError as e:
        return _mk_error("UNAUTHENTICATED", str(e))
    finally:
        await backend.close()


# ── 2.8 get_cross_repo_dependencies ──────────────────────────────────

# US-78 / UC-7803: any length. ``UC-\d{3}`` cut UC-5101 into "UC-510" and reported
# dependencies on the wrong (or a missing) UC.
_UC_REF_RE = re.compile(r"\bUC-\d+[a-zA-Z]?\b")


async def get_cross_repo_dependencies(
    board_id: str,
    ctx: Context,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Detect UCs that reference UCs in a different satellite.

    Scans each UC's description, context meta, and links for UC-NNN
    references. Flags as a cross-repo dependency when the referenced UC
    belongs to a different satellite.

    Returns:
        {dependencies: [{uc_id, depends_on, satellite_from, satellite_to,
          dependency_type}]}
    """
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        ucs = await _all_ucs(backend, board_id)
        sat_map: dict[str, str] = {}
        for uc in ucs:
            uc_id = _get_uc_id(uc)
            if uc_id:
                sat_map[uc_id] = uc.meta.get("satellite", "")

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
                    })

        return {"dependencies": deps}
    finally:
        await backend.close()


# ── Registration ─────────────────────────────────────────────────────


def register_milestone_management_tools(mcp_instance) -> None:
    """Register the Tier 2 multirepo tools (+ declare_satellites, UC-7803)."""
    mcp_instance.tool(
        description="Assign a UC to a satellite repo. Validates the satellite key against "
        "the orchestrator's multirepo settings."
    )(set_uc_satellite)
    mcp_instance.tool(
        description="List UCs assigned to a satellite repo, in Backlog. Returns the full "
        "ordered queue."
    )(get_satellite_queue)
    mcp_instance.tool(
        description="Propagate satellite labels from orchestrator settings.local.json to board "
        "cards without a satellite assigned. Remote MCP: send that file as settings_content; "
        "the server never reads orchestrator_path."
    )(sync_multirepo_state)
    mcp_instance.tool(
        description="Declare the satellites of a multi-repo project on its board (Native). "
        "Satellite assignments are validated against this list, also with the remote MCP."
    )(declare_satellites)
    mcp_instance.tool(
        description="Detect cross-satellite UC dependencies by scanning descriptions, context, "
        "and links for UC-NNN references to UCs in different satellites."
    )(get_cross_repo_dependencies)
