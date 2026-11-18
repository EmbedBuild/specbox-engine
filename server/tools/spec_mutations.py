"""Tier 1 — Granular & batch mutation tools (v5.23.0 Full Mutations).

8 tools: 6 granular + 2 batch. See doc/design/v5.23.0-full-mutations.md
section "Tier 1" for the full design.

Guiding principles (copied here as a reminder — read the design doc for
rationale):

1. Batch-first: every granular tool's docstring references its batch equivalent.
2. Validation lives here, not in backends (satellite, link_type).
3. Every mutation is idempotent — returns reason="no_change" on second call.
4. Errors are structured dicts with code field, never raised.
5. All tools take board_id + ctx and always `await backend.close()` in finally.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from ..app_docs.roadmap import with_roadmap_sync  # UC-12203
from fastmcp import Context

from ..auth_gateway import get_session_backend
from ._content_passing import returns_items_content
from ..spec_backend import ItemDTO, parse_item_id, with_item_id
from . import _mutation_helpers as mh

logger = structlog.get_logger(__name__)


# ── Internal: un criterio hecho que se reescribe (UC-11701) ──────────


def _plan_ac_update(current: Any, text: str | None, done: bool | None) -> dict[str, Any]:
    """Qué cambia de verdad en un criterio y si queda pendiente de comprobar.

    Un criterio hecho cuyo texto cambia queda sin hacer en todos los backends: lo que se comprobó
    era el texto anterior (en el board native lo hace además el trigger de la migración 0035, para
    cualquier escritor). Un ``done=True`` en la misma llamada no se aplica: el criterio vuelve a
    constar como hecho con ``mark_ac`` y su justificante.
    """
    text_changed = text is not None and text != current.text
    reset = text_changed and bool(current.done)
    if reset:
        return {
            "text_changed": True,
            "done_changed": True,
            "done": False,
            "reset": True,
            "ignored_done": done is True,
        }
    done_changed = done is not None and bool(done) != bool(current.done)
    return {
        "text_changed": text_changed,
        "done_changed": done_changed,
        "done": done if done_changed else None,
        "reset": False,
        "ignored_done": False,
    }


def _verification_change(backend: Any, current: Any, verification: str | None) -> dict[str, Any]:
    """UC-12307: what a ``verification`` in update_ac(_batch) changes.

    ``verification`` is already normalized. Returns ``{"meta": {...}}`` for the backend call when
    it changes, ``{"not_stored": True}`` when the backend has nowhere to keep it, or ``{}``.
    """
    if verification is None:
        return {}
    if not getattr(backend, "STORES_SPEC_META", False):
        return {"not_stored": True}
    if verification == getattr(current, "verification", None):
        return {}
    return {"meta": {"verification": verification}}


async def _record_reset(backend: Any, board_id: str, uc_item_id: str, ac_id: str) -> None:
    """Deja en la UC el veredicto «no pasa» por el texto nuevo.

    Trello, Plane y FreeForm reconstruyen el último veredicto de los comentarios: sin este, el
    «PASSED» del texto anterior volvería a contar si alguien pone el criterio hecho sin mark_ac. En
    el board native el veredicto lo pone el trigger de 0035 y el comentario queda como historial.
    Un fallo al comentar no deshace el cambio.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        await backend.add_comment(
            board_id,
            uc_item_id,
            f"{ac_id}: FAILED — Texto cambiado: pendiente de volver a comprobarse [{stamp}]",
        )
    except Exception as e:  # noqa: BLE001 — el comentario es historial, no el cambio
        logger.warning("ac_reset_comment_failed", ac_id=ac_id, error=str(e))


def _reset_notice(ac_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Lo que añade la respuesta cuando el criterio queda pendiente (AC-04)."""
    if not plan["reset"]:
        return {}
    warning = (
        f"{ac_id} queda pendiente de volver a comprobarse: su texto cambió y lo comprobado era el "
        "texto anterior. Márcalo con mark_ac y su justificante cuando vuelva a pasar."
    )
    notice: dict[str, Any] = {"reset_to_pending": True, "warning": warning}
    if plan["ignored_done"]:
        notice["ignored"] = ["done"]
        notice["warning"] = warning + " El done=true de esta llamada no se aplica."
    return notice


# ── Internal: metadata extraction for UC/US ──────────────────────────


def _uc_meta_updates(
    *,
    hours: float | None,
    screens: list[str] | None,
    actor: str | None,
    context_text: str | None,
    satellite: str | None,
) -> dict[str, Any]:
    return {
        "horas": hours,
        "pantallas": screens,
        "actor": actor,
        "context": context_text,
        "satellite": satellite,
    }


def _us_meta_updates(
    *,
    hours: float | None,
    screens: list[str] | None,
) -> dict[str, Any]:
    return {
        "horas": hours,
        "pantallas": screens,
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
    satellite: str | None = None,
    no_prd_reason: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Update metadata of a single Use Case without touching ACs or workflow state.

    `no_prd_reason` (UC-12211): marks the UC as «sin PRD» with a reason (at least 10 characters,
    no credentials), so the spec_in_pr measure lets its PR merge without touching a PRD; "" clears it.

    For batch updates across many UCs, prefer `update_uc_batch` — it's 1 MCP
    call instead of N and keeps token cost proportional to payload size.
    For bulk initial ingest of UCs, use `import_spec`.

    Only non-None fields are updated (merge semantics). `satellite` must
    match a key declared in the orchestrator's settings.local.json →
    multirepo.satellites. (Milestones were removed in v6.23.0: use epics.)

    Idempotent: calling twice with the same args returns `reason: "no_change"`
    on the second call.

    `items_content` (FreeForm content-passing, UC-660): pass items.json as a
    string for remote MCP; the mutated string is returned under `items_content`.

    Returns:
        {uc_id, updated_fields, backend_item_url, updated_at, reason?}
        plus `items_content` when `items_content` was provided.
    """
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if satellite is not None:
            ok, err = await mh.check_satellite(backend, board_id, satellite)
            if not ok:
                return _mk_error("INVALID_SATELLITE", err or "invalid satellite")

        if no_prd_reason:
            reason = " ".join(no_prd_reason.split())
            if len(reason) < 10:
                return _mk_error(
                    "REASON_REQUIRED",
                    "Marcar una UC «sin PRD» exige un motivo de al menos 10 caracteres.",
                    uc_id=uc_id,
                )
            if any("credential" in tag for tag in mh.detect_ac_exposure(reason)):
                return _mk_error("SENSITIVE_DATA", "El motivo menciona credenciales: descríbelo sin ellas.", uc_id=uc_id)
            no_prd_reason = reason

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        meta_updates = _uc_meta_updates(
            hours=hours,
            screens=screens,
            actor=actor,
            context_text=context_text,
            satellite=satellite,
        )
        if no_prd_reason is not None:
            meta_updates["no_prd_reason"] = no_prd_reason
        merged_meta, meta_changed = mh.merge_meta(uc_item.meta, meta_updates)

        if name is not None:
            name = with_item_id(uc_id, name)  # UC-7802 AC-03: the id once
        name_changed = name is not None and name != uc_item.name
        desc_changed = description is not None and description != uc_item.description

        if not meta_changed and not name_changed and not desc_changed:
            no_change = {
                "uc_id": uc_id,
                "updated_fields": [],
                "backend_item_url": uc_item.url,
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
            }
            if items_content is not None:
                no_change["items_content"] = backend.get_items_content()
            return no_change

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

        result = {
            "uc_id": uc_id,
            "updated_fields": fields,
            "backend_item_url": updated.url or uc_item.url,
            "updated_at": mh.utc_now_iso(),
        }
        if items_content is not None:
            result["items_content"] = backend.get_items_content()
        return result
    finally:
        await backend.close()


# ── 1.2 update_uc_batch ──────────────────────────────────────────────


@returns_items_content
async def update_uc_batch(
    board_id: str,
    updates: list[dict[str, Any]],
    ctx: Context,
    *,
    stop_on_error: bool = False,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Update metadata of many Use Cases in a single MCP call.

    This is the preferred tool when you need to update more than 2-3 UCs —
    it saves MCP round-trips AND calls `list_items` only once (not once per
    UC like a loop of `update_uc` would).

    Each entry in `updates` is a dict with keys: uc_id (required), name,
    description, hours, screens, actor, context_text, satellite. Only
    non-None fields are applied per UC. An entry with ``milestone`` fails
    with MILESTONES_REMOVED (removed in v6.23.0: use epics).

    By default, errors on individual UCs are collected and the batch
    continues (partial success). Set `stop_on_error=True` to abort on first
    failure.

    Returns:
        {total, succeeded:[{uc_id, updated_fields}], failed:[{uc_id, error, code}], backend_item_urls}
    """
    backend = await get_session_backend(ctx, items_content=items_content)
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

            if "milestone" in entry:
                failed.append({"uc_id": uc_id, "error": mh.MILESTONES_REMOVED_MESSAGE, "code": "MILESTONES_REMOVED"})
                if stop_on_error:
                    break
                continue

            satellite = entry.get("satellite")
            if satellite is not None:
                ok, err = await mh.check_satellite(backend, board_id, satellite)
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
                satellite=satellite,
            )
            merged_meta, meta_changed = mh.merge_meta(uc_item.meta, meta_updates)

            new_name = entry.get("name")
            if new_name is not None:
                new_name = with_item_id(uc_id, new_name)  # UC-7802 AC-03
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


@returns_items_content
async def update_us(
    board_id: str,
    us_id: str,
    ctx: Context,
    *,
    name: str | None = None,
    description: str | None = None,
    hours: float | None = None,
    screens: list[str] | None = None,
    exclusions: list[str] | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Update metadata of a User Story (name, description, hours, screens, exclusions).

    Milestones were removed in v6.23.0: the story's epic (``set_us_epic``)
    groups the work now.

    There is no `update_us_batch` in v1 — US-level mutations are rare
    (typically 1-5 per project). Use repeated `update_us` calls when
    needed.

    `exclusions` (UC-12306) replaces what the story leaves out (the PRD's «No incluye»);
    `[]` clears it. It clears the `no_exclusions` warning of import_spec without
    reimporting. Trello and Plane do not store it (`exclusions_not_stored`).

    Returns:
        {us_id, updated_fields, backend_item_url, updated_at, exclusions_not_stored?}
    """
    try:
        exclusions = mh.normalize_exclusions(exclusions)
    except ValueError as e:
        return _mk_error("INVALID_EXCLUSIONS", str(e), us_id=us_id)
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        us_item = await mh.find_us(backend, board_id, us_id)
        if not us_item:
            return _mk_error("US_NOT_FOUND", f"User Story {us_id} not found", us_id=us_id)

        not_stored: dict[str, Any] = {}
        meta_updates = _us_meta_updates(hours=hours, screens=screens)
        if exclusions is not None:
            if getattr(backend, "STORES_SPEC_META", False):
                meta_updates["exclusions"] = exclusions
            else:
                not_stored = {"exclusions_not_stored": True}
        merged_meta, meta_changed = mh.merge_meta(us_item.meta, meta_updates)

        if name is not None:
            name = with_item_id(us_id, name)  # UC-7802 AC-03: the id once
        name_changed = name is not None and name != us_item.name
        desc_changed = description is not None and description != us_item.description

        if not meta_changed and not name_changed and not desc_changed:
            return {
                "us_id": us_id,
                "updated_fields": [],
                "backend_item_url": us_item.url,
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
                **not_stored,
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
            "backend_item_url": url,
            "updated_at": mh.utc_now_iso(),
            **not_stored,
        }
    finally:
        await backend.close()


# ── 1.4 update_ac ────────────────────────────────────────────────────


@returns_items_content
async def update_ac(
    board_id: str,
    uc_id: str,
    ac_id: str,
    ctx: Context,
    *,
    text: str | None = None,
    done: bool | None = None,
    verification: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Rewrite an AC's text, change its done state and/or say how it is checked.

    Distinct from `mark_ac`, which only toggles `done`. Use `update_ac` when
    the Definition Quality Gate flags an AC as vague or untestable and you
    need to rewrite its text.

    For batch updates across many ACs, use `update_ac_batch`. For pure
    done-flag toggles without text rewrites, prefer `mark_ac_batch` — it's
    cheaper.

    Only non-None fields are updated. If `done` is omitted, the existing
    done state is preserved.

    Rewriting the text of a criterion that is done leaves it pending
    (UC-11701): what was checked was the previous text. The response then
    carries `reset_to_pending` and a `warning`; a `done=true` in the same call
    is not applied (mark it again with `mark_ac` and its receipt).

    `verification` (UC-12307) says how the criterion is checked: automated_test,
    manual_test, review or measurement. It clears the `no_verification` warning of
    validate_ac_quality and leaves the done state as it is (the criterion's text has
    not changed). Trello and Plane do not store it: `verification_not_stored`.

    Returns:
        {uc_id, ac_id, updated_fields, updated_at, reason?, reset_to_pending?, warning?, ignored?,
         verification_not_stored?}
    """
    try:
        verification = mh.normalize_verification(verification)
    except mh.VerificationError as e:
        return _mk_error("INVALID_VERIFICATION", str(e), uc_id=uc_id, ac_id=ac_id)
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        current = await mh.find_ac(backend, board_id, uc_item.id, ac_id)
        if not current:
            # UC-12501: a retired criterion is neither rewritten nor marked.
            retired = await mh.retired_error(backend, board_id, uc_item.id, uc_id, ac_id)
            if retired is not None:
                return retired
            return _mk_error(
                "AC_NOT_FOUND", f"AC {ac_id} not found in {uc_id}", uc_id=uc_id, ac_id=ac_id
            )

        plan = _plan_ac_update(current, text, done)
        text_changed = plan["text_changed"]
        done_changed = plan["done_changed"]
        verif = _verification_change(backend, current, verification)
        not_stored = {"verification_not_stored": True} if verif.get("not_stored") else {}

        if not text_changed and not done_changed and "meta" not in verif:
            return {
                "uc_id": uc_id,
                "ac_id": ac_id,
                "updated_fields": [],
                "updated_at": mh.utc_now_iso(),
                "reason": "no_change",
                **not_stored,
            }

        try:
            await backend.update_acceptance_criterion(
                board_id,
                uc_item.id,
                ac_id,
                text=text if text_changed else None,
                done=plan["done"],
                **({"meta": verif["meta"]} if "meta" in verif else {}),
            )
        except ValueError as e:
            return _mk_error("AC_NOT_FOUND", str(e), uc_id=uc_id, ac_id=ac_id)
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        if plan["reset"]:
            await _record_reset(backend, board_id, uc_item.id, ac_id)

        fields: list[str] = []
        if text_changed:
            fields.append("text")
        if done_changed:
            fields.append("done")
        if "meta" in verif:
            fields.append("verification")

        return {
            "uc_id": uc_id,
            "ac_id": ac_id,
            "updated_fields": fields,
            "updated_at": mh.utc_now_iso(),
            **_reset_notice(ac_id, plan),
            **not_stored,
        }
    finally:
        await backend.close()


# ── 1.5 update_ac_batch ──────────────────────────────────────────────


@returns_items_content
async def update_ac_batch(
    board_id: str,
    updates: list[dict[str, Any]],
    ctx: Context,
    *,
    stop_on_error: bool = False,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Update many ACs across multiple UCs in a single MCP call.

    Preferred when the Definition Quality Gate flags multiple vague ACs at
    once, or when marking many ACs done after a successful acceptance run.
    Note: if you only need to flip `done` flags (no text rewrites),
    `mark_ac_batch` is cheaper — prefer it for that use case.

    Each entry: {uc_id, ac_id, text?, done?, verification?}. `verification` (UC-12307):
    automated_test, manual_test, review or measurement; an invalid one fails that entry
    with INVALID_VERIFICATION. Trello and Plane do not store it (`verification_not_stored`
    on the entry).

    Returns:
        {total, succeeded:[{uc_id, ac_id, updated_fields}], failed:[{uc_id, ac_id, error, code}]}
    """
    backend = await get_session_backend(ctx, items_content=items_content)
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
                retired = await mh.retired_error(backend, board_id, uc_item.id, uc_id, ac_id)
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": retired["error"], "code": "AC_RETIRED"}
                    if retired is not None
                    else {"uc_id": uc_id, "ac_id": ac_id, "error": "AC not found", "code": "AC_NOT_FOUND"}
                )
                if stop_on_error:
                    break
                continue

            text = entry.get("text")
            done = entry.get("done")
            try:
                verification = mh.normalize_verification(entry.get("verification"))
            except mh.VerificationError as e:
                failed.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "error": str(e), "code": "INVALID_VERIFICATION"}
                )
                if stop_on_error:
                    break
                continue
            plan = _plan_ac_update(current, text, done)
            text_changed = plan["text_changed"]
            done_changed = plan["done_changed"]
            verif = _verification_change(backend, current, verification)
            not_stored = {"verification_not_stored": True} if verif.get("not_stored") else {}

            if not text_changed and not done_changed and "meta" not in verif:
                succeeded.append(
                    {"uc_id": uc_id, "ac_id": ac_id, "updated_fields": [], "reason": "no_change", **not_stored}
                )
                continue

            try:
                await backend.update_acceptance_criterion(
                    board_id,
                    uc_item.id,
                    ac_id,
                    text=text if text_changed else None,
                    done=plan["done"],
                    **({"meta": verif["meta"]} if "meta" in verif else {}),
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

            if plan["reset"]:
                await _record_reset(backend, board_id, uc_item.id, ac_id)

            fields: list[str] = []
            if text_changed:
                fields.append("text")
            if done_changed:
                fields.append("done")
            if "meta" in verif:
                fields.append("verification")
            succeeded.append(
                {
                    "uc_id": uc_id,
                    "ac_id": ac_id,
                    "updated_fields": fields,
                    **_reset_notice(ac_id, plan),
                    **not_stored,
                }
            )

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
    verification: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Append a new Acceptance Criterion to an existing UC.

    Auto-assigns the next AC-NN id (e.g. if AC-01..AC-05 exist, the new AC
    is AC-06). Empty UCs get AC-01. Retired ids count (UC-12501): if AC-05 was
    retired from AC-01..AC-05, the new AC is AC-06, never AC-05 again.

    `verification` (UC-12307) says how the criterion is checked: automated_test,
    manual_test, review or measurement. Without it, validate_ac_quality warns
    `no_verification`. Trello and Plane do not store it (`verification_not_stored`).

    Use this for 1-2 AC additions. For adding many ACs at once, prefer
    rewriting the UC's full AC list via `import_spec` — it's idempotent and
    cheaper than a loop.

    `items_content` (FreeForm content-passing, UC-660): pass items.json as a
    string for remote MCP; the mutated string is returned under `items_content`.

    Returns:
        {uc_id, ac_id, text, done, verification, created_at, spec_gate,
         verification_not_stored?}
        plus `items_content` when `items_content` was provided.
    """
    try:
        verification = mh.normalize_verification(verification)
    except mh.VerificationError as e:
        return _mk_error("INVALID_VERIFICATION", str(e), uc_id=uc_id)
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if not text or not text.strip():
            return _mk_error("VALIDATION_FAILED", "text must be non-empty")

        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        existing = await backend.get_acceptance_criteria(board_id, uc_item.id)
        # UC-12501: a retired id is never used again in its UC.
        new_id = mh.next_ac_id(existing, await mh.retired_ids(backend, board_id, uc_item.id))
        stored = verification is not None and bool(getattr(backend, "STORES_SPEC_META", False))

        try:
            created = await backend.create_acceptance_criteria(
                board_id,
                uc_item.id,
                [(new_id, text)],
                **({"meta_by_ac": {new_id: {"verification": verification}}} if stored else {}),
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
        result = {
            "uc_id": uc_id,
            "ac_id": new_id,
            "text": text,
            "done": done,
            "verification": verification if stored else None,
            "created_at": mh.utc_now_iso(),
            "backend_id": created_ac.backend_id if created_ac else "",
        }
        if verification is not None and not stored:
            result["verification_not_stored"] = True  # UC-12307: Trello and Plane
        # UC-12301 AC-04: the spec gate of the UC with its new criterion (information only).
        from .enforcement import spec_gate_summary

        result["spec_gate"] = await spec_gate_summary(ctx, board_id, [{
            "uc_id": uc_id,
            "acs": [{"ac_id": ac.id, "text": ac.text, "spec_rules": ac.spec_rules} for ac in existing]
            + [{"ac_id": new_id, "text": text, "spec_rules": mh.SPEC_RULES_VERSION}],
        }])
        if items_content is not None:
            result["items_content"] = backend.get_items_content()
        return result
    finally:
        await backend.close()


# ── 1.7 delete_ac ────────────────────────────────────────────────────


@returns_items_content
async def delete_ac(
    board_id: str,
    uc_id: str,
    ac_id: str,
    ctx: Context,
    *,
    reason: str | None = None,
    retired_by: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Retire an AC from a UC (UC-12501). The other ACs keep their ids.

    The retired AC leaves the current criteria but stays on the board with its reason, its date,
    who retired it and its receipts (`get_uc` returns it under `retired_criteria`), and its id is
    never used again in that UC: retiring AC-03 from AC-01..AC-05 leaves AC-01, AC-02, AC-04 and
    AC-05, and the next new AC is AC-06. Native keeps it in its own table, FreeForm in the UC's
    meta; Trello and Plane have nowhere to keep it and delete it (`retired_not_stored`).

    `reason` is required (10 to 500 characters): it is what anyone reading the UC later sees.
    `retired_by` is only used by FreeForm (the freeform-fragment hook puts the git author); native
    takes it from the session.

    Returns:
        {uc_id, retired_ac_id, reason, retired_at, retired?, retired_not_stored?}
    """
    clean_reason = (reason or "").strip()
    if not mh.REASON_MIN <= len(clean_reason) <= mh.REASON_MAX:
        return _mk_error(
            "REASON_REQUIRED",
            f"Para retirar {ac_id} hace falta un motivo de {mh.REASON_MIN} a {mh.REASON_MAX} "
            "caracteres: es lo que verá quien lea la UC después.",
            uc_id=uc_id,
            ac_id=ac_id,
        )
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _mk_error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)

        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
        if not any(a.id == ac_id for a in acs):
            retired = await mh.retired_error(backend, board_id, uc_item.id, uc_id, ac_id)
            if retired is not None:
                return retired
            return _mk_error(
                "AC_NOT_FOUND",
                f"AC {ac_id} not found in {uc_id}",
                uc_id=uc_id,
                ac_id=ac_id,
            )

        try:
            record = await backend.retire_acceptance_criterion(
                board_id, uc_item.id, ac_id, reason=clean_reason, retired_by=(retired_by or None)
            )
        except ValueError as e:
            return _mk_error("AC_NOT_FOUND", str(e), uc_id=uc_id, ac_id=ac_id)
        except Exception as e:
            return _mk_error("BACKEND_ERROR", str(e))

        result: dict[str, Any] = {
            "uc_id": uc_id,
            "retired_ac_id": ac_id,
            "reason": clean_reason,
            "retired_at": (record or {}).get("retired_at") or mh.utc_now_iso(),
        }
        if record is None:
            result["retired_not_stored"] = True
            # Trello y Plane: el comentario de la UC es todo el rastro que queda.
            try:
                await backend.add_comment(
                    board_id, uc_item.id, f"AC {ac_id} retirado ({result['retired_at']}): {clean_reason}"
                )
            except Exception:
                logger.exception("delete_ac_comment_failed", uc=uc_id, ac=ac_id)
        else:
            result["retired"] = record
        return result
    finally:
        await backend.close()


# ── 1.8 add_uc ───────────────────────────────────────────────────────


@with_roadmap_sync
async def add_uc(
    board_id: str,
    us_id: str,
    name: str,
    description: str,
    acceptance_criteria: list[str | dict[str, Any]],
    ctx: Context,
    *,
    hours: float | None = None,
    screens: list[str] | None = None,
    actor: str | None = None,
    context_text: str | None = None,
    satellite: str | None = None,
    items_content: str | None = None,
    uc_id: str | None = None,
    with_roadmap: bool = False,
) -> dict[str, Any]:
    """Create a single new Use Case under an existing User Story.

    Use this for 1-3 UC additions after the initial spec import. For
    creating more than 3 UCs at once, use `import_spec` — it's designed for
    bulk ingest and is idempotent. Using `add_uc` in a loop is an anti-pattern.

    `acceptance_criteria` is a list of plain text strings or, as in import_spec,
    `{text, verification}` objects (UC-12307: automated_test, manual_test, review or
    measurement). ACs are created with ids AC-01, AC-02, ..., AC-NN automatically.

    Numbering (UC-12214):
    - When every UC of the story follows `UC-{story number}{NN}`, the new one continues
      that series (US-122 with UC-12212 and UC-12213 → UC-12214).
    - Otherwise (correlative boards, an empty story) it takes the next number of the
      whole board (UC-001..UC-027 → UC-028).
    - `uc_id` chooses the id; `UC_ID_TAKEN` when the board already has it.
    - If the computed id already belongs to another story, nothing is created and
      `UC_ID_CONFLICT` names that story (pass `uc_id` to choose another).

    `items_content` (FreeForm content-passing, UC-660): when the MCP server is
    remote it cannot read the client's items.json. Pass its contents as a
    string and the mutated items.json is returned under the `items_content`
    key for the client to write back. Omit it for local MCP / disk mode.

    Returns:
        {uc_id, name, ac_count, numbering, backend_item_url, created_at}
        (`numbering`: "story", "board" or "explicit") plus `items_content`
        (mutated items.json string) when `items_content` was provided.
    """
    # UC-12307: texts and verifications first, so a bad value creates nothing.
    ac_texts: list[str] = []
    ac_verifications: list[str | None] = []
    try:
        for ac in acceptance_criteria:
            if isinstance(ac, dict):
                ac_texts.append(str(ac.get("text", ac.get("name", ""))))
                ac_verifications.append(mh.normalize_verification(ac.get("verification")))
            else:
                ac_texts.append(str(ac))
                ac_verifications.append(None)
    except mh.VerificationError as e:
        return _mk_error("INVALID_VERIFICATION", str(e), us_id=us_id)

    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if satellite is not None:
            ok, err = await mh.check_satellite(backend, board_id, satellite)
            if not ok:
                return _mk_error("INVALID_SATELLITE", err or "invalid satellite")

        us_item = await mh.find_us(backend, board_id, us_id)
        if not us_item:
            return _mk_error("US_NOT_FOUND", f"User Story {us_id} not found", us_id=us_id)

        if uc_id:
            if not mh.is_valid_uc_id(uc_id):
                return _mk_error(
                    "INVALID_UC_ID", f"{uc_id!r} is not a UC id (UC- plus letters, digits or dashes)",
                    uc_id=uc_id,
                )
            owner = await mh.uc_owner(backend, board_id, uc_id)
            if owner is not None:
                return _mk_error(
                    "UC_ID_TAKEN", f"{uc_id} already exists in {owner or 'the board'}; nothing was created",
                    uc_id=uc_id, us_id=owner,
                )
            new_uc_id, numbering = uc_id, "explicit"
        else:
            choice = await mh.choose_uc_id(backend, board_id, us_id)
            if choice.taken_by is not None:
                return _mk_error(
                    "UC_ID_CONFLICT",
                    f"The next id for {us_id} would be {choice.uc_id}, but {choice.taken_by or 'the board'} "
                    "already has it; nothing was created. Pass uc_id to choose another.",
                    uc_id=choice.uc_id, us_id=choice.taken_by, numbering=choice.numbering,
                )
            new_uc_id, numbering = choice.uc_id, choice.numbering

        full_name = with_item_id(new_uc_id, name)
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
            (f"AC-{i + 1:02d}", text) for i, text in enumerate(ac_texts)
        ]
        stores = bool(getattr(backend, "STORES_SPEC_META", False))
        metas = {
            ac_id: {"verification": v}
            for (ac_id, _), v in zip(ac_pairs, ac_verifications)
            if v is not None
        }
        if ac_pairs:
            try:
                await backend.create_acceptance_criteria(
                    board_id,
                    created.id,
                    ac_pairs,
                    **({"meta_by_ac": metas} if metas and stores else {}),
                )
            except Exception:
                logger.exception("add_uc_create_acs_failed", uc=new_uc_id)

        result = {
            "uc_id": new_uc_id,
            "name": name,
            "ac_count": len(ac_pairs),
            "numbering": numbering,
            "backend_item_url": created.url,
            "created_at": mh.utc_now_iso(),
        }
        if metas and not stores:
            result["verification_not_stored"] = True  # UC-12307: Trello and Plane
        if items_content is not None:
            result["items_content"] = backend.get_items_content()
        return result
    finally:
        await backend.close()


# ── Registration ─────────────────────────────────────────────────────


def register_spec_mutations_tools(mcp_instance) -> None:
    """Register the 8 Tier 1 mutation tools on the given FastMCP instance."""
    mcp_instance.tool(
        description="Update metadata of a single Use Case (name, description, hours, "
        "screens, actor, context, satellite). Idempotent. For batch "
        "updates on many UCs use update_uc_batch."
    )(update_uc)
    mcp_instance.tool(
        description="Update metadata of many Use Cases in a single MCP call. Preferred "
        "when updating more than 2-3 UCs — saves round-trips and calls list_items once."
    )(update_uc_batch)
    mcp_instance.tool(
        description="Update metadata of a User Story (name, description, hours, screens, "
        "exclusions: what the story leaves out, [] clears it). To group stories use epics "
        "(set_us_epic)."
    )(update_us)
    mcp_instance.tool(
        description="Rewrite an AC's text, change its done state and/or set how it is checked "
        "(verification: automated_test, manual_test, review, measurement). For pure done-flag "
        "toggles use mark_ac/mark_ac_batch. For many AC rewrites use update_ac_batch."
    )(update_ac)
    mcp_instance.tool(
        description="Update many ACs across multiple UCs in a single call ({uc_id, ac_id, text?, "
        "done?, verification?}). Preferred for Definition Quality Gate rewrites of multiple "
        "vague ACs, or no_verification warnings, at once."
    )(update_ac_batch)
    mcp_instance.tool(
        description="Append a new AC to an existing UC. Auto-assigns next AC-NN id. Pass "
        "verification (automated_test, manual_test, review, measurement) to say how it is "
        "checked. Use for 1-2 additions; for many at once prefer import_spec."
    )(add_ac)
    mcp_instance.tool(
        description="Retire an AC from a UC with a required reason (10-500 chars). The other ACs "
        "keep their ids and the retired id is never used again; get_uc lists it under "
        "retired_criteria with its reason, date and receipts (UC-12501)."
    )(delete_ac)
    mcp_instance.tool(
        description="Create a single new Use Case under an existing US. Use for 1-3 additions; "
        "for bulk creation prefer import_spec. Numbering: if every UC of the story follows "
        "UC-{story number}{NN} (US-122 → UC-12212, UC-12213), the new one continues that series "
        "(UC-12214); otherwise it takes the next number of the whole board (UC-027 → UC-028). "
        "Pass uc_id to choose it (UC_ID_TAKEN if it exists). If the computed id belongs to "
        "another story, nothing is created (UC_ID_CONFLICT)."
    )(add_uc)
