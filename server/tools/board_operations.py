"""Tier 3 — Board Operations tools (v5.23.0 Full Mutations).

5 tools. Adds archive_item ABC method.

See doc/design/v5.23.0-full-mutations.md section "Tier 3".
"""

from __future__ import annotations

import json
from pathlib import Path
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


# ── 3.1 validate_ac_quality ──────────────────────────────────────────


async def validate_ac_quality(
    board_id: str,
    ctx: Context,
    *,
    uc_id: str | None = None,
) -> dict[str, Any]:
    """Validate AC quality against the Definition Quality Gate rules.

    Applies the same rules as `/prd` step 2.5 but retroactively on
    existing ACs. If `uc_id` is passed, validates only that UC.
    Otherwise, validates the whole board.

    Use this tool to audit AC quality before a milestone acceptance check.
    For rewriting flagged ACs, use `update_ac` or `update_ac_batch`.

    Returns:
        {total_acs, passed, failed:[{uc_id, ac_id, text, issues}], pass_rate}
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)
        ucs = [i for i in items if "UC" in i.labels]

        if uc_id is not None:
            ucs = [u for u in ucs if _get_uc_id(u) == uc_id]
            if not ucs:
                return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found")

        total = 0
        failed: list[dict[str, Any]] = []

        for uc in ucs:
            uid = _get_uc_id(uc)
            try:
                acs = await backend.get_acceptance_criteria(board_id, uc.id)
            except Exception:
                continue

            for ac in acs:
                total += 1
                issues = mh.validate_ac_text(ac.text)
                if issues:
                    failed.append({
                        "uc_id": uid,
                        "ac_id": ac.id,
                        "text": ac.text,
                        "issues": issues,
                    })

        passed = total - len(failed)
        rate = round(passed / total, 4) if total else 1.0
        return {
            "total_acs": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": rate,
        }
    finally:
        await backend.close()


# ── 3.2 set_ac_metadata ──────────────────────────────────────────────


async def set_ac_metadata(
    board_id: str,
    uc_id: str,
    ac_id: str,
    ctx: Context,
    *,
    evidence_url: str | None = None,
    screenshot: str | None = None,
    verdict: str | None = None,
) -> dict[str, Any]:
    """Attach structured evidence metadata to a single AC.

    Complements `attach_evidence` (which operates at UC level). This tool
    stores per-AC metadata: evidence URL, screenshot path, and/or acceptance
    verdict.

    For updating AC text/done, use `update_ac`. This tool is for metadata
    only.

    Returns:
        {uc_id, ac_id, metadata, updated_at}
    """
    backend = await get_session_backend(ctx)
    try:
        if verdict is not None and verdict not in mh.VERDICT_TYPES:
            return _mk_error(
                "VALIDATION_FAILED",
                f"verdict must be one of {mh.VERDICT_TYPES}, got {verdict!r}",
            )

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found")

        ac = await mh.find_ac(backend, board_id, uc_item.id, ac_id)
        if not ac:
            return _mk_error("AC_NOT_FOUND", f"AC {ac_id} not found in {uc_id}")

        metadata: dict[str, str] = {}
        if evidence_url is not None:
            metadata["evidence_url"] = evidence_url
        if screenshot is not None:
            metadata["screenshot"] = screenshot
        if verdict is not None:
            metadata["verdict"] = verdict

        if not metadata:
            return {
                "uc_id": uc_id,
                "ac_id": ac_id,
                "metadata": {},
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
            }

        # Store metadata as JSON suffix in the AC text (backend-agnostic).
        # Format: "original text [META: {...}]"
        import re
        clean_text = re.sub(r"\s*\[META:\s*\{.*?\}\]$", "", ac.text).strip()
        existing_meta: dict[str, str] = {}
        meta_match = re.search(r"\[META:\s*(\{.*?\})\]$", ac.text)
        if meta_match:
            try:
                existing_meta = json.loads(meta_match.group(1))
            except json.JSONDecodeError:
                pass

        existing_meta.update(metadata)
        new_text = f"{clean_text} [META: {json.dumps(existing_meta)}]"

        try:
            await backend.update_acceptance_criterion(
                board_id, uc_item.id, ac_id, text=new_text
            )
        except ValueError as e:
            return _mk_error("AC_NOT_FOUND", str(e))
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        return {
            "uc_id": uc_id,
            "ac_id": ac_id,
            "metadata": existing_meta,
            "updated_at": mh.utc_now_iso(),
        }
    finally:
        await backend.close()


# ── 3.3 link_uc_parent ───────────────────────────────────────────────


async def link_uc_parent(
    board_id: str,
    uc_id: str,
    parent_uc_id: str,
    link_type: str,
    ctx: Context,
) -> dict[str, Any]:
    """Formalize a relationship between two UCs.

    `link_type` must be one of: absorbs, blocks, depends_on, supersedes,
    related_to. The relationship is persisted in the child UC's
    meta.links list and audit comments are added to BOTH cards.

    Returns:
        {uc_id, parent_uc_id, link_type, created_at}
    """
    backend = await get_session_backend(ctx)
    try:
        ok, err = mh.validate_link_type(link_type)
        if not ok:
            return _mk_error("INVALID_LINK_TYPE", err or "invalid link type")

        child_item = await mh.find_uc(backend, board_id, uc_id)
        if not child_item:
            return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found", uc_id=uc_id)

        parent_item = await mh.find_uc(backend, board_id, parent_uc_id)
        if not parent_item:
            return _mk_error("UC_NOT_FOUND", f"UC {parent_uc_id} not found", uc_id=parent_uc_id)

        now = mh.utc_now_iso()

        # Add link to child's meta
        links: list[dict[str, str]] = child_item.meta.get("links", [])
        if not isinstance(links, list):
            links = []

        # Idempotency: don't duplicate
        existing = next(
            (l for l in links if l.get("target_uc_id") == parent_uc_id and l.get("type") == link_type),
            None,
        )
        if existing:
            return {
                "uc_id": uc_id,
                "parent_uc_id": parent_uc_id,
                "link_type": link_type,
                "created_at": existing.get("created_at", now),
                "reason": "no_change",
            }

        links.append({
            "type": link_type,
            "target_uc_id": parent_uc_id,
            "created_at": now,
        })
        merged, _ = mh.merge_meta(child_item.meta, {"links": links})
        await backend.update_item(board_id, child_item.id, meta=merged)

        # Audit comment on BOTH cards (AC-15)
        comment_child = f"Link: {uc_id} —[{link_type}]→ {parent_uc_id} ({now})"
        comment_parent = f"Link: {uc_id} —[{link_type}]→ {parent_uc_id} ({now})"
        try:
            await backend.add_comment(board_id, child_item.id, comment_child)
            await backend.add_comment(board_id, parent_item.id, comment_parent)
        except Exception:
            logger.exception("link_uc_parent_comment_failed", uc=uc_id, parent=parent_uc_id)

        return {
            "uc_id": uc_id,
            "parent_uc_id": parent_uc_id,
            "link_type": link_type,
            "created_at": now,
        }
    finally:
        await backend.close()


# ── 3.4 delete_uc ────────────────────────────────────────────────────


async def delete_uc(
    board_id: str,
    uc_id: str,
    reason: str,
    ctx: Context,
    *,
    absorbed_by: str | None = None,
) -> dict[str, Any]:
    """Archive a UC (does NOT physically delete — moves to archive location).

    If `absorbed_by` is provided, calls `link_uc_parent` with link_type
    "absorbs" before archiving. This formalizes UC consolidation.

    Use this for UC removal. There is no batch variant — UC deletion is
    rare and always requires a per-UC `reason` for audit.

    Returns:
        {uc_id, deleted_at, reason, absorbed_by, archive_location}
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"UC {uc_id} not found", uc_id=uc_id)

        # Link before archiving (AC-16)
        if absorbed_by:
            parent = await mh.find_uc(backend, board_id, absorbed_by)
            if not parent:
                return _mk_error(
                    "UC_NOT_FOUND",
                    f"absorbed_by UC {absorbed_by} not found",
                    uc_id=absorbed_by,
                )
            # Persist link in meta
            links: list[dict[str, str]] = uc_item.meta.get("links", [])
            if not isinstance(links, list):
                links = []
            now = mh.utc_now_iso()
            links.append({
                "type": "absorbs",
                "target_uc_id": absorbed_by,
                "created_at": now,
            })
            merged, _ = mh.merge_meta(uc_item.meta, {"links": links})
            await backend.update_item(board_id, uc_item.id, meta=merged)

            comment = f"Link: {uc_id} —[absorbs]→ {absorbed_by} ({now})"
            try:
                await backend.add_comment(board_id, uc_item.id, comment)
                await backend.add_comment(board_id, parent.id, comment)
            except Exception:
                logger.exception("delete_uc_link_comment_failed", uc=uc_id)

        try:
            result = await backend.archive_item(board_id, uc_item.id, reason=reason)
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        return {
            "uc_id": uc_id,
            "deleted_at": result.get("archived_at", mh.utc_now_iso()),
            "reason": reason,
            "absorbed_by": absorbed_by,
            "archive_location": result.get("archive_location", "unknown"),
        }
    finally:
        await backend.close()


# ── 3.5 get_board_diff ───────────────────────────────────────────────


async def get_board_diff(
    board_id: str,
    from_snapshot: str,
    to_snapshot: str,
    ctx: Context,
) -> dict[str, Any]:
    """Compare board state between two timestamped snapshots.

    Snapshots are stored under `.quality/board_snapshots/{board_id}/{timestamp}.json`.
    To create one, call `get_board_status` and save the result there.

    This tool only works forward from when snapshots were taken. There is
    no retroactive history in Trello/Plane.

    Returns:
        {from, to, added_ucs, removed_ucs, modified_ucs, milestone_moves, ac_changes}
    """
    # This tool is purely file-based — no backend needed
    try:
        from_path = Path(f".quality/board_snapshots/{board_id}/{from_snapshot}.json")
        to_path = Path(f".quality/board_snapshots/{board_id}/{to_snapshot}.json")

        if not from_path.exists():
            return _mk_error("VALIDATION_FAILED", f"Snapshot not found: {from_path}")
        if not to_path.exists():
            return _mk_error("VALIDATION_FAILED", f"Snapshot not found: {to_path}")

        from_data = json.loads(from_path.read_text())
        to_data = json.loads(to_path.read_text())

        # Parse UCs from snapshot data — expect {items: [{uc_id, name, state, milestone, ac_count, ac_done}]}
        def _uc_map(data: dict) -> dict[str, dict]:
            items = data.get("items", data.get("ucs", []))
            result = {}
            for it in items:
                uid = it.get("uc_id", "")
                if uid:
                    result[uid] = it
            return result

        from_ucs = _uc_map(from_data)
        to_ucs = _uc_map(to_data)

        from_ids = set(from_ucs.keys())
        to_ids = set(to_ucs.keys())

        added = sorted(to_ids - from_ids)
        removed = sorted(from_ids - to_ids)

        modified: list[dict[str, Any]] = []
        milestone_moves: list[dict[str, str]] = []
        ac_added = ac_removed = ac_passed_delta = 0

        for uid in from_ids & to_ids:
            f_item = from_ucs[uid]
            t_item = to_ucs[uid]
            changes: dict[str, list] = {}

            for field in ("name", "state", "milestone", "hours"):
                fv = f_item.get(field)
                tv = t_item.get(field)
                if fv != tv:
                    changes[field] = [fv, tv]
                    if field == "milestone":
                        milestone_moves.append({
                            "uc_id": uid,
                            "from": str(fv or ""),
                            "to": str(tv or ""),
                        })

            f_ac = int(f_item.get("ac_count", 0))
            t_ac = int(t_item.get("ac_count", 0))
            if t_ac > f_ac:
                ac_added += t_ac - f_ac
            elif t_ac < f_ac:
                ac_removed += f_ac - t_ac

            f_done = int(f_item.get("ac_done", 0))
            t_done = int(t_item.get("ac_done", 0))
            ac_passed_delta += t_done - f_done

            if changes:
                modified.append({"uc_id": uid, "changes": changes})

        return {
            "from": from_snapshot,
            "to": to_snapshot,
            "added_ucs": added,
            "removed_ucs": removed,
            "modified_ucs": modified,
            "milestone_moves": milestone_moves,
            "ac_changes": {
                "added": ac_added,
                "removed": ac_removed,
                "passed_delta": ac_passed_delta,
            },
        }
    except Exception as e:
        if "error" in str(type(e)):
            raise
        return _mk_error("BACKEND_ERROR", str(e))


# ── Registration ─────────────────────────────────────────────────────


def register_board_operations_tools(mcp_instance) -> None:
    """Register the 5 Tier 3 board operation tools."""
    mcp_instance.tool(
        description="Validate AC quality against Definition Quality Gate rules. "
        "Flags vague, too-short, and untestable ACs. For a single UC pass uc_id."
    )(validate_ac_quality)
    mcp_instance.tool(
        description="Attach structured evidence metadata (URL, screenshot, verdict) "
        "to a single AC. Complements attach_evidence which works at UC level."
    )(set_ac_metadata)
    mcp_instance.tool(
        description="Formalize a relationship between two UCs (absorbs, blocks, "
        "depends_on, supersedes, related_to). Adds audit comment on BOTH cards."
    )(link_uc_parent)
    mcp_instance.tool(
        description="Archive a UC (soft delete). Optionally records an 'absorbs' link "
        "before archiving. Per-UC reason required for audit trail."
    )(delete_uc)
    mcp_instance.tool(
        description="Compare board state between two timestamped snapshots. Detects "
        "added/removed/modified UCs, milestone moves, and AC count changes."
    )(get_board_diff)
