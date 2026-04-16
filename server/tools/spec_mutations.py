"""Tier 1 — Granular & batch mutation tools (v5.23.0 Full Mutations).

8 tools: 6 granular + 2 batch. See doc/design/v5.23.0-full-mutations.md
section "Tier 1" for the full design.

Guiding principles (copied here as a reminder — read the design doc for
rationale):

1. Batch-first: every granular tool's docstring references its batch equivalent.
2. Validation lives here, not in backends (milestone, satellite, link_type).
3. Every mutation is idempotent — returns reason="no_change" on second call.
4. Errors are structured dicts with code field, never raised.
5. All tools take board_id + ctx and always `await backend.close()` in finally.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_session_backend
from ..spec_backend import ItemDTO, SpecBackend, parse_item_id
from . import _mutation_helpers as mh

logger = structlog.get_logger(__name__)


# ── Internal: metadata extraction for UC/US ──────────────────────────


def _uc_meta_updates(
    *,
    hours: float | None,
    screens: list[str] | None,
    actor: str | None,
    context_text: str | None,
    milestone: str | None,
    satellite: str | None,
) -> dict[str, Any]:
    return {
        "horas": hours,
        "pantallas": screens,
        "actor": actor,
        "context": context_text,
        "milestone": milestone,
        "satellite": satellite,
    }


def _us_meta_updates(
    *,
    hours: float | None,
    screens: list[str] | None,
    milestone: str | None,
) -> dict[str, Any]:
    return {
        "horas": hours,
        "pantallas": screens,
        "milestone": milestone,
    }


def _mk_error(code: str, message: str, **ctx: Any) -> dict[str, Any]:
    payload = {"error": message, "code": code}
    payload.update(ctx)
    return payload


# ── 1.1 update_uc ────────────────────────────────────────────────────


async def update_uc(
    board_id: str,
    uc_id: str,
    ctx: Context,
    *,
    name: str | None = None,
    description: str | None = None,
    hours: float | None = None,
    screens: list[str] | None = None,
    actor: str | None = None,
    context_text: str | None = None,
    milestone: str | None = None,
    satellite: str | None = None,
) -> dict[str, Any]:
    """Update metadata of a single Use Case without touching ACs or workflow state.

    For batch updates across many UCs, prefer `update_uc_batch` — it's 1 MCP
    call instead of N and keeps token cost proportional to payload size.
    For bulk initial ingest of UCs, use `import_spec`.

    Only non-None fields are updated (merge semantics). `milestone` must be
    one of H1, H2, H3, H4. `satellite` must match a key declared in the
    orchestrator's settings.local.json → multirepo.satellites.

    Idempotent: calling twice with the same args returns `reason: "no_change"`
    on the second call.

    Returns:
        {uc_id, updated_fields, backend_item_url, updated_at, reason?}
    """
    backend = await get_session_backend(ctx)
    try:
        if milestone is not None:
            ok, err = mh.validate_milestone(milestone)
            if not ok:
                return _mk_error("INVALID_MILESTONE", err or "invalid milestone")
        if satellite is not None:
            ok, err = mh.validate_satellite(satellite, mh.settings_path_from_env())
            if not ok:
                return _mk_error("INVALID_SATELLITE", err or "invalid satellite")

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        meta_updates = _uc_meta_updates(
            hours=hours,
            screens=screens,
            actor=actor,
            context_text=context_text,
            milestone=milestone,
            satellite=satellite,
        )
        merged_meta, meta_changed = mh.merge_meta(uc_item.meta, meta_updates)

        name_changed = name is not None and name != uc_item.name
        desc_changed = description is not None and description != uc_item.description

        if not meta_changed and not name_changed and not desc_changed:
            return {
                "uc_id": uc_id,
                "updated_fields": [],
                "backend_item_url": uc_item.url,
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
            }

        try:
            updated = await backend.update_item(
                board_id,
                uc_item.id,
                name=name if name_changed else None,
                description=description if desc_changed else None,
                meta=merged_meta if meta_changed else None,
            )
        except Exception as e:
            logger.exception("update_uc_backend_error", uc_id=uc_id)
            return _mk_error("BACKEND_ERROR", str(e), backend=type(backend).__name__)

        fields = list(meta_changed)
        if name_changed:
            fields.append("name")
        if desc_changed:
            fields.append("description")

        return {
            "uc_id": uc_id,
            "updated_fields": fields,
            "backend_item_url": updated.url or uc_item.url,
            "updated_at": mh.utc_now_iso(),
        }
    finally:
        await backend.close()


# ── 1.2 update_uc_batch ──────────────────────────────────────────────


async def update_uc_batch(
    board_id: str,
    updates: list[dict[str, Any]],
    ctx: Context,
    *,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """Update metadata of many Use Cases in a single MCP call.

    This is the preferred tool when you need to update more than 2-3 UCs —
    it saves MCP round-trips AND calls `list_items` only once (not once per
    UC like a loop of `update_uc` would).

    Each entry in `updates` is a dict with keys: uc_id (required), name,
    description, hours, screens, actor, context_text, milestone, satellite.
    Only non-None fields are applied per UC.

    By default, errors on individual UCs are collected and the batch
    continues (partial success). Set `stop_on_error=True` to abort on first
    failure.

    Returns:
        {total, succeeded:[{uc_id, updated_fields}], failed:[{uc_id, error, code}], backend_item_urls}
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)
        by_uc: dict[str, ItemDTO] = {}
        for item in items:
            uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
            if uc_id:
                by_uc[uc_id] = item

        succeeded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        urls: dict[str, str] = {}

        for entry in updates:
            uc_id = entry.get("uc_id", "")
            if not uc_id:
                failed.append({"uc_id": "", "error": "missing uc_id", "code": "VALIDATION_FAILED"})
                if stop_on_error:
                    break
                continue

            milestone = entry.get("milestone")
            if milestone is not None:
                ok, err = mh.validate_milestone(milestone)
                if not ok:
                    failed.append({"uc_id": uc_id, "error": err, "code": "INVALID_MILESTONE"})
                    if stop_on_error:
                        break
                    continue

            satellite = entry.get("satellite")
            if satellite is not None:
                ok, err = mh.validate_satellite(satellite, mh.settings_path_from_env())
                if not ok:
                    failed.append({"uc_id": uc_id, "error": err, "code": "INVALID_SATELLITE"})
                    if stop_on_error:
                        break
                    continue

            uc_item = by_uc.get(uc_id)
            if not uc_item:
                failed.append({"uc_id": uc_id, "error": "not found", "code": "UC_NOT_FOUND"})
                if stop_on_error:
                    break
                continue

            meta_updates = _uc_meta_updates(
                hours=entry.get("hours"),
                screens=entry.get("screens"),
                actor=entry.get("actor"),
                context_text=entry.get("context_text"),
                milestone=milestone,
                satellite=satellite,
            )
            merged_meta, meta_changed = mh.merge_meta(uc_item.meta, meta_updates)

            new_name = entry.get("name")
            new_desc = entry.get("description")
            name_changed = new_name is not None and new_name != uc_item.name
            desc_changed = new_desc is not None and new_desc != uc_item.description

            if not meta_changed and not name_changed and not desc_changed:
                succeeded.append({"uc_id": uc_id, "updated_fields": [], "reason": "no_change"})
                urls[uc_id] = uc_item.url
                continue

            try:
                updated = await backend.update_item(
                    board_id,
                    uc_item.id,
                    name=new_name if name_changed else None,
                    description=new_desc if desc_changed else None,
                    meta=merged_meta if meta_changed else None,
                )
            except Exception as e:
                logger.exception("update_uc_batch_backend_error", uc_id=uc_id)
                failed.append(
                    {"uc_id": uc_id, "error": str(e), "code": "BACKEND_ERROR"}
                )
                if stop_on_error:
                    break
                continue

            fields = list(meta_changed)
            if name_changed:
                fields.append("name")
            if desc_changed:
                fields.append("description")
            succeeded.append({"uc_id": uc_id, "updated_fields": fields})
            urls[uc_id] = updated.url or uc_item.url

        return {
            "total": len(updates),
            "succeeded": succeeded,
            "failed": failed,
            "backend_item_urls": urls,
        }
    finally:
        await backend.close()


# ── 1.3 update_us ────────────────────────────────────────────────────


async def update_us(
    board_id: str,
    us_id: str,
    ctx: Context,
    *,
    name: str | None = None,
    description: str | None = None,
    hours: float | None = None,
    screens: list[str] | None = None,
    milestone: str | None = None,
    propagate_milestone: bool = True,
) -> dict[str, Any]:
    """Update metadata of a User Story.

    If `milestone` is set and `propagate_milestone=True` (default), the
    milestone is assigned to all child UCs that do NOT already have a
    milestone set. UCs that already have a milestone are never overwritten.

    There is no `update_us_batch` in v1 — US-level mutations are rare
    (typically 1-5 per project). Use repeated `update_us` calls when
    needed.

    Returns:
        {us_id, updated_fields, propagated_to_ucs, backend_item_url, updated_at}
    """
    backend = await get_session_backend(ctx)
    try:
        if milestone is not None:
            ok, err = mh.validate_milestone(milestone)
            if not ok:
                return _mk_error("INVALID_MILESTONE", err or "invalid milestone")

        us_item = await mh.find_us(backend, board_id, us_id)
        if not us_item:
            return _mk_error("US_NOT_FOUND", f"User Story {us_id} not found", us_id=us_id)

        meta_updates = _us_meta_updates(
            hours=hours, screens=screens, milestone=milestone
        )
        merged_meta, meta_changed = mh.merge_meta(us_item.meta, meta_updates)

        name_changed = name is not None and name != us_item.name
        desc_changed = description is not None and description != us_item.description

        propagated: list[str] = []
        if milestone is not None and propagate_milestone:
            children = await backend.get_item_children(board_id, us_item.id)
            for child in children:
                if "UC" not in child.labels:
                    continue
                if child.meta.get("milestone"):
                    continue
                uc_spec_id = child.meta.get("uc_id") or parse_item_id(child.name, "UC")[0]
                try:
                    child_merged, child_changed = mh.merge_meta(
                        child.meta, {"milestone": milestone}
                    )
                    if child_changed:
                        await backend.update_item(board_id, child.id, meta=child_merged)
                        propagated.append(uc_spec_id or child.id)
                except Exception:
                    logger.exception("propagate_milestone_error", uc=uc_spec_id)

        if not meta_changed and not name_changed and not desc_changed and not propagated:
            return {
                "us_id": us_id,
                "updated_fields": [],
                "propagated_to_ucs": [],
                "backend_item_url": us_item.url,
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
            }

        if meta_changed or name_changed or desc_changed:
            try:
                updated = await backend.update_item(
                    board_id,
                    us_item.id,
                    name=name if name_changed else None,
                    description=description if desc_changed else None,
                    meta=merged_meta if meta_changed else None,
                )
                url = updated.url or us_item.url
            except Exception as e:
                return _mk_error("BACKEND_ERROR", str(e))
        else:
            url = us_item.url

        fields = list(meta_changed)
        if name_changed:
            fields.append("name")
        if desc_changed:
            fields.append("description")

        return {
            "us_id": us_id,
            "updated_fields": fields,
            "propagated_to_ucs": propagated,
            "backend_item_url": url,
            "updated_at": mh.utc_now_iso(),
        }
    finally:
        await backend.close()


# ── 1.4 update_ac ────────────────────────────────────────────────────


async def update_ac(
    board_id: str,
    uc_id: str,
    ac_id: str,
    ctx: Context,
    *,
    text: str | None = None,
    done: bool | None = None,
) -> dict[str, Any]:
    """Rewrite an AC's text and/or change its done state.

    Distinct from `mark_ac`, which only toggles `done`. Use `update_ac` when
    the Definition Quality Gate flags an AC as vague or untestable and you
    need to rewrite its text.

    For batch updates across many ACs, use `update_ac_batch`. For pure
    done-flag toggles without text rewrites, prefer `mark_ac_batch` — it's
    cheaper.

    Only non-None fields are updated. If `done` is omitted, the existing
    done state is preserved.

    Returns:
        {uc_id, ac_id, updated_fields, updated_at, reason?}
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        current = await mh.find_ac(backend, board_id, uc_item.id, ac_id)
        if not current:
            return _mk_error(
                "AC_NOT_FOUND", f"AC {ac_id} not found in {uc_id}", uc_id=uc_id, ac_id=ac_id
            )

        text_changed = text is not None and text != current.text
        done_changed = done is not None and bool(done) != bool(current.done)

        if not text_changed and not done_changed:
            return {
                "uc_id": uc_id,
                "ac_id": ac_id,
                "updated_fields": [],
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
            }

        try:
            await backend.update_acceptance_criterion(
                board_id,
                uc_item.id,
                ac_id,
                text=text if text_changed else None,
                done=done if done_changed else None,
            )
        except ValueError as e:
            return _mk_error("AC_NOT_FOUND", str(e), uc_id=uc_id, ac_id=ac_id)
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        fields: list[str] = []
        if text_changed:
            fields.append("text")
        if done_changed:
            fields.append("done")

        return {
            "uc_id": uc_id,
            "ac_id": ac_id,
            "updated_fields": fields,
            "updated_at": mh.utc_now_iso(),
        }
    finally:
        await backend.close()


# ── 1.5 update_ac_batch ──────────────────────────────────────────────


async def update_ac_batch(
    board_id: str,
    updates: list[dict[str, Any]],
    ctx: Context,
    *,
    stop_on_error: bool = False,
) -> dict[str, Any]:
    """Update many ACs across multiple UCs in a single MCP call.

    Preferred when the Definition Quality Gate flags multiple vague ACs at
    once, or when marking many ACs done after a successful acceptance run.
    Note: if you only need to flip `done` flags (no text rewrites),
    `mark_ac_batch` is cheaper — prefer it for that use case.

    Each entry: {uc_id, ac_id, text?, done?}.

    Returns:
        {total, succeeded:[{uc_id, ac_id, updated_fields}], failed:[{uc_id, ac_id, error, code}]}
    """
    backend = await get_session_backend(ctx)
    try:
        # Cache UC lookups across the batch — list_items once, find per uc_id.
        items = await backend.list_items(board_id)
        by_uc: dict[str, ItemDTO] = {}
        for item in items:
            uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
            if uc_id:
                by_uc[uc_id] = item

        # Cache AC snapshots per UC to check current values and idempotency.
        ac_snapshots: dict[str, dict[str, Any]] = {}

        async def _snapshot(uc_item: ItemDTO) -> dict[str, Any]:
            if uc_item.id in ac_snapshots:
                return ac_snapshots[uc_item.id]
            acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
            snap = {ac.id: ac for ac in acs}
            ac_snapshots[uc_item.id] = snap
            return snap

        succeeded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for entry in updates:
            uc_id = entry.get("uc_id", "")
            ac_id = entry.get("ac_id", "")
            if not uc_id or not ac_id:
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": "missing uc_id/ac_id", "code": "VALIDATION_FAILED"}
                )
                if stop_on_error:
                    break
                continue

            uc_item = by_uc.get(uc_id)
            if not uc_item:
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": "UC not found", "code": "UC_NOT_FOUND"}
                )
                if stop_on_error:
                    break
                continue

            snap = await _snapshot(uc_item)
            current = snap.get(ac_id)
            if current is None:
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": "AC not found", "code": "AC_NOT_FOUND"}
                )
                if stop_on_error:
                    break
                continue

            text = entry.get("text")
            done = entry.get("done")
            text_changed = text is not None and text != current.text
            done_changed = done is not None and bool(done) != bool(current.done)

            if not text_changed and not done_changed:
                succeeded.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "updated_fields": [], "reason": "no_change"}
                )
                continue

            try:
                await backend.update_acceptance_criterion(
                    board_id,
                    uc_item.id,
                    ac_id,
                    text=text if text_changed else None,
                    done=done if done_changed else None,
                )
            except ValueError as e:
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": str(e), "code": "AC_NOT_FOUND"}
                )
                if stop_on_error:
                    break
                continue
            except Exception as e:
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": str(e), "code": "BACKEND_ERROR"}
                )
                if stop_on_error:
                    break
                continue

            fields: list[str] = []
            if text_changed:
                fields.append("text")
            if done_changed:
                fields.append("done")
            succeeded.append({"uc_id": uc_id, "ac_id": ac_id, "updated_fields": fields})

        return {
            "total": len(updates),
            "succeeded": succeeded,
            "failed": failed,
        }
    finally:
        await backend.close()


# ── 1.6 add_ac ───────────────────────────────────────────────────────


async def add_ac(
    board_id: str,
    uc_id: str,
    text: str,
    ctx: Context,
    *,
    done: bool = False,
) -> dict[str, Any]:
    """Append a new Acceptance Criterion to an existing UC.

    Auto-assigns the next AC-NN id (e.g. if AC-01..AC-05 exist, the new AC
    is AC-06). Empty UCs get AC-01.

    Use this for 1-2 AC additions. For adding many ACs at once, prefer
    rewriting the UC's full AC list via `import_spec` — it's idempotent and
    cheaper than a loop.

    Returns:
        {uc_id, ac_id, text, done, created_at}
    """
    backend = await get_session_backend(ctx)
    try:
        if not text or not text.strip():
            return _mk_error("VALIDATION_FAILED", "text must be non-empty")

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        existing = await backend.get_acceptance_criteria(board_id, uc_item.id)
        new_id = mh.next_ac_id(existing)

        try:
            created = await backend.create_acceptance_criteria(
                board_id, uc_item.id, [(new_id, text)]
            )
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        if done:
            try:
                await backend.update_acceptance_criterion(
                    board_id, uc_item.id, new_id, done=True
                )
            except Exception:
                logger.exception("add_ac_mark_done_failed", uc=uc_id, ac=new_id)

        created_ac = created[0] if created else None
        return {
            "uc_id": uc_id,
            "ac_id": new_id,
            "text": text,
            "done": done,
            "created_at": mh.utc_now_iso(),
            "backend_id": created_ac.backend_id if created_ac else "",
        }
    finally:
        await backend.close()


# ── 1.7 delete_ac ────────────────────────────────────────────────────


async def delete_ac(
    board_id: str,
    uc_id: str,
    ac_id: str,
    ctx: Context,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """Remove an AC from a UC and renumber subsequent ACs.

    If `reason` is provided, it's logged as a comment on the parent UC
    for audit.

    Renumbering: if AC-03 is deleted from [AC-01, AC-02, AC-03, AC-04, AC-05],
    the result is [AC-01, AC-02, AC-03 (was AC-04), AC-04 (was AC-05)].

    Returns:
        {uc_id, deleted_ac_id, renumbered_acs, deleted_at, reason?}
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
        target = next((a for a in acs if a.id == ac_id), None)
        if not target:
            return _mk_error(
                "AC_NOT_FOUND",
                f"AC {ac_id} not found in {uc_id}",
                uc_id=uc_id,
                ac_id=ac_id,
            )

        # Compute renumber plan — ACs strictly after the deleted one shift down by 1.
        def _ac_num(s: str) -> int:
            try:
                return int(s.split("-")[1])
            except (IndexError, ValueError):
                return -1

        target_num = _ac_num(ac_id)
        shifted: list[tuple[str, str, str]] = []  # (old_id, new_id, text)
        for ac in acs:
            n = _ac_num(ac.id)
            if n > target_num:
                new_id = f"AC-{n - 1:02d}"
                shifted.append((ac.id, new_id, ac.text))

        # Apply deletion, then renumber. Renumber order: ascending old id so
        # we don't collide with existing ids in any backend.
        try:
            await backend.delete_acceptance_criterion(board_id, uc_item.id, ac_id)
        except ValueError as e:
            return _mk_error("AC_NOT_FOUND", str(e))
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        renumbered: dict[str, str] = {}
        # The rename from "AC-04" -> "AC-03" requires that the text stays
        # the same but the id embedded in the name changes. Our
        # update_acceptance_criterion rewrites by ac_id (the OLD one) and
        # accepts `text=` which the backend re-serializes as "{NEW_ID}: ...".
        # However the backend resolves the item by OLD ac_id — we rename in
        # place by issuing a text rewrite that also encodes the new id.
        # Each backend's update_acceptance_criterion embeds {ac_id} in the
        # rendered name, so we pass the OLD ac_id as locator and text as the
        # NEW text — but we need the new id in the name.
        # Solution: treat the rename as (delete old, create new).
        # That preserves the text and id semantics cleanly for all backends.
        for old_id, new_id, text in shifted:
            try:
                await backend.delete_acceptance_criterion(board_id, uc_item.id, old_id)
                await backend.create_acceptance_criteria(
                    board_id, uc_item.id, [(new_id, text)]
                )
                renumbered[old_id] = new_id
            except Exception:
                logger.exception(
                    "renumber_ac_failed", uc=uc_id, old_id=old_id, new_id=new_id
                )

        if reason:
            try:
                await backend.add_comment(
                    board_id,
                    uc_item.id,
                    f"AC {ac_id} deleted ({mh.utc_now_iso()}): {reason}",
                )
            except Exception:
                logger.exception("delete_ac_comment_failed", uc=uc_id, ac=ac_id)

        return {
            "uc_id": uc_id,
            "deleted_ac_id": ac_id,
            "renumbered_acs": renumbered,
            "deleted_at": mh.utc_now_iso(),
            "reason": reason,
        }
    finally:
        await backend.close()


# ── 1.8 add_uc ───────────────────────────────────────────────────────


async def add_uc(
    board_id: str,
    us_id: str,
    name: str,
    description: str,
    acceptance_criteria: list[str],
    ctx: Context,
    *,
    hours: float | None = None,
    screens: list[str] | None = None,
    actor: str | None = None,
    context_text: str | None = None,
    milestone: str | None = None,
    satellite: str | None = None,
) -> dict[str, Any]:
    """Create a single new Use Case under an existing User Story.

    Use this for 1-3 UC additions after the initial spec import. For
    creating more than 3 UCs at once, use `import_spec` — it's designed for
    bulk ingest and is idempotent. Using `add_uc` in a loop is an anti-pattern.

    `acceptance_criteria` is a list of plain text strings. ACs are created
    with ids AC-01, AC-02, ..., AC-NN automatically.

    uc_id is auto-assigned by scanning `max(uc_id)` on the board and
    incrementing (e.g. UC-001..UC-027 exist → new UC is UC-028).

    Returns:
        {uc_id, name, ac_count, backend_item_url, created_at}
    """
    backend = await get_session_backend(ctx)
    try:
        if milestone is not None:
            ok, err = mh.validate_milestone(milestone)
            if not ok:
                return _mk_error("INVALID_MILESTONE", err or "invalid milestone")
        if satellite is not None:
            ok, err = mh.validate_satellite(satellite, mh.settings_path_from_env())
            if not ok:
                return _mk_error("INVALID_SATELLITE", err or "invalid satellite")

        us_item = await mh.find_us(backend, board_id, us_id)
        if not us_item:
            return _mk_error("US_NOT_FOUND", f"User Story {us_id} not found", us_id=us_id)

        max_num = await mh.find_max_uc_number(backend, board_id)
        new_uc_id = mh.format_uc_id(max_num + 1)

        full_name = f"{new_uc_id}: {name}"
        meta: dict[str, Any] = {
            "tipo": "UC",
            "uc_id": new_uc_id,
            "us_id": us_id,
        }
        for key, val in {
            "horas": hours,
            "pantallas": screens,
            "actor": actor,
            "context": context_text,
            "milestone": milestone,
            "satellite": satellite,
        }.items():
            if val is not None:
                meta[key] = val

        try:
            created = await backend.create_item(
                board_id,
                name=full_name,
                description=description,
                state="backlog",
                labels=["UC"],
                parent_id=us_item.id,
                meta=meta,
            )
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        ac_pairs: list[tuple[str, str]] = [
            (f"AC-{i + 1:02d}", text) for i, text in enumerate(acceptance_criteria)
        ]
        if ac_pairs:
            try:
                await backend.create_acceptance_criteria(board_id, created.id, ac_pairs)
            except Exception:
                logger.exception("add_uc_create_acs_failed", uc=new_uc_id)

        return {
            "uc_id": new_uc_id,
            "name": name,
            "ac_count": len(ac_pairs),
            "backend_item_url": created.url,
            "created_at": mh.utc_now_iso(),
        }
    finally:
        await backend.close()


# ── Registration ─────────────────────────────────────────────────────


def register_spec_mutations_tools(mcp_instance) -> None:
    """Register the 8 Tier 1 mutation tools on the given FastMCP instance."""
    mcp_instance.tool(
        description="Update metadata of a single Use Case (name, description, hours, "
        "screens, actor, context, milestone, satellite). Idempotent. For batch "
        "updates on many UCs use update_uc_batch."
    )(update_uc)
    mcp_instance.tool(
        description="Update metadata of many Use Cases in a single MCP call. Preferred "
        "when updating more than 2-3 UCs — saves round-trips and calls list_items once."
    )(update_uc_batch)
    mcp_instance.tool(
        description="Update metadata of a User Story. Optionally propagates milestone to "
        "child UCs without a milestone set (existing milestones never overwritten)."
    )(update_us)
    mcp_instance.tool(
        description="Rewrite an AC's text and/or change its done state. For pure done-flag "
        "toggles use mark_ac/mark_ac_batch. For many AC rewrites use update_ac_batch."
    )(update_ac)
    mcp_instance.tool(
        description="Update many ACs across multiple UCs in a single call. Preferred for "
        "Definition Quality Gate rewrites of multiple vague ACs at once."
    )(update_ac_batch)
    mcp_instance.tool(
        description="Append a new AC to an existing UC. Auto-assigns next AC-NN id. Use "
        "for 1-2 additions; for many at once prefer import_spec."
    )(add_ac)
    mcp_instance.tool(
        description="Remove an AC from a UC and renumber subsequent ACs. Optional reason "
        "logged as a comment on the UC for audit."
    )(delete_ac)
    mcp_instance.tool(
        description="Create a single new Use Case under an existing US. Auto-assigns next "
        "uc_id. Use for 1-3 additions; for bulk creation prefer import_spec."
    )(add_uc)
