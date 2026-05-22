"""Generic write-target for N×N backend migration (UC-401).

Extracts and generalizes the 3-phase write logic of
``server/tools/migration.py:migrate_project`` (US + module, UC + AC with
idempotency, comments) into a backend-agnostic coroutine that writes the
``source_data`` dict produced by ``migration._read_source`` into ANY of the
four backends.

State translation between backends is OUT OF SCOPE here — it belongs to
UC-402. ``write_target`` writes the workflow state exactly as it arrives in
``source_data``.
"""

from __future__ import annotations

from typing import Any

import structlog

from ..spec_backend import SpecBackend, parse_item_id
from ..tools.migration import ENGINE_SOURCE, _build_external_id

logger = structlog.get_logger(__name__)


async def write_target(
    target_backend: SpecBackend,
    target_id: str,
    source_data: dict[str, Any],
    source_type: str | None = None,
) -> dict[str, Any]:
    """Write a read-source payload into a target backend (any of the 4).

    Creates US, UC and AC in ``target_backend`` from the dict returned by
    ``migration._read_source``, preserving the parent→child hierarchy via an
    id_map and the logical us_id / uc_id / ac_id in each item's meta.

    Idempotent: items already present in the target (matched by their logical
    us_id / uc_id) are skipped, not duplicated. Re-running ``write_target`` on
    an already-populated target reports them under ``skipped`` and creates 0
    new items.

    Args:
        target_backend: The destination backend (already constructed).
        target_id: Destination board/project ID.
        source_data: Dict from ``_read_source`` with keys ``board_name``,
            ``items``, ``classified`` (us/uc/ac/other), ``ac_data``
            (uc_id → list of {id, text, done, backend_id}), ``comments_data``,
            ``labels``, ``states`` and optionally ``source_type``.
        source_type: Source backend type used to build the external_id for
            traceability. Falls back to ``source_data['source_type']`` and
            finally to ``"unknown"``.

    Returns:
        Dict with ``migrated`` (us/uc/ac/comments/modules counts), ``skipped``
        (int), ``errors`` (list[str]) and ``id_map`` (source_item_id →
        target_item_id).
    """
    src_type = source_type or source_data.get("source_type") or "unknown"
    classified = source_data["classified"]
    ac_data: dict[str, list[dict[str, Any]]] = source_data.get("ac_data", {})
    comments_data: dict[str, list[dict[str, Any]]] = source_data.get("comments_data", {})

    id_map: dict[str, str] = {}  # source_item_id -> target_item_id
    errors: list[str] = []
    migrated = {"us": 0, "uc": 0, "ac": 0, "comments": 0, "modules": 0}
    skipped = 0

    # ── Phase 1: User Stories (+ module per US) ──────────────────────
    for us_item in classified["us"]:
        try:
            us_id, us_name = parse_item_id(us_item.name, "US")
            ext_id = _build_external_id(src_type, us_item.id)

            # Idempotency: skip if a US with this logical id already exists.
            existing = await target_backend.find_item_by_field(target_id, "us_id", us_id)
            if existing:
                id_map[us_item.id] = existing.id
                skipped += 1
                continue

            new_us = await target_backend.create_item(
                target_id,
                name=us_item.name,
                description=us_item.description,
                state=us_item.state,
                labels=["US"],
                priority=us_item.priority,
                external_source=ENGINE_SOURCE,
                external_id=ext_id,
                meta=us_item.meta,
            )
            id_map[us_item.id] = new_us.id
            migrated["us"] += 1

            # Best-effort module for this US.
            try:
                await target_backend.create_module(target_id, f"{us_id}: {us_name}")
                migrated["modules"] += 1
            except Exception as exc:  # noqa: BLE001 - module is best-effort
                logger.warning("write_target_module_error", us_id=us_id, error=str(exc))

        except Exception as exc:  # noqa: BLE001 - per-item isolation
            errors.append(f"US {us_item.name}: {exc}")
            logger.error("write_target_us_error", item=us_item.name, error=str(exc))

    # ── Phase 2: Use Cases (+ acceptance criteria) ───────────────────
    for uc_item in classified["uc"]:
        try:
            uc_id, _uc_name = parse_item_id(uc_item.name, "UC")
            ext_id = _build_external_id(src_type, uc_item.id)

            # Idempotency: skip if a UC with this logical id already exists.
            existing = await target_backend.find_item_by_field(target_id, "uc_id", uc_id)
            if existing:
                id_map[uc_item.id] = existing.id
                skipped += 1
                continue

            # Resolve parent in target: prefer explicit parent_id, fall back to
            # the US whose logical id matches uc_item.meta["us_id"].
            source_parent = uc_item.parent_id or ""
            if not source_parent and uc_item.meta.get("us_id"):
                for us in classified["us"]:
                    pid, _ = parse_item_id(us.name, "US")
                    if pid == uc_item.meta["us_id"]:
                        source_parent = us.id
                        break

            target_parent = id_map.get(source_parent)

            uc_labels = ["UC"]
            actor = uc_item.meta.get("actor", "")
            if actor and actor != "Todos":
                uc_labels.append(f"Actor:{actor}")

            new_uc = await target_backend.create_item(
                target_id,
                name=uc_item.name,
                description=uc_item.description,
                state=uc_item.state,
                labels=uc_labels,
                parent_id=target_parent,
                priority=uc_item.priority,
                external_source=ENGINE_SOURCE,
                external_id=ext_id,
                meta=uc_item.meta,
            )
            id_map[uc_item.id] = new_uc.id
            migrated["uc"] += 1

            # Acceptance criteria for this UC.
            acs = ac_data.get(uc_item.id, [])
            if acs:
                try:
                    criteria = [(ac["id"], ac["text"]) for ac in acs]
                    await target_backend.create_acceptance_criteria(target_id, new_uc.id, criteria)
                    # Re-apply done state for already-passed ACs.
                    for ac in acs:
                        if ac["done"]:
                            try:
                                await target_backend.mark_acceptance_criterion(target_id, new_uc.id, ac["id"], True)
                            except Exception:  # noqa: BLE001 - best-effort
                                pass
                    migrated["ac"] += len(acs)
                except Exception as exc:  # noqa: BLE001 - per-UC isolation
                    errors.append(f"ACs for {uc_id}: {exc}")

        except Exception as exc:  # noqa: BLE001 - per-item isolation
            errors.append(f"UC {uc_item.name}: {exc}")
            logger.error("write_target_uc_error", item=uc_item.name, error=str(exc))

    # ── Phase 3: Comments (audit trail) ──────────────────────────────
    for source_item_id, comments in comments_data.items():
        target_item_id = id_map.get(source_item_id)
        if not target_item_id:
            continue
        for comment in comments:
            try:
                text = comment["text"]
                ts = comment.get("created_at", "")
                migrated_text = f"[Migrated from {src_type} — {ts}]\n{text}"
                await target_backend.add_comment(target_id, target_item_id, migrated_text)
                migrated["comments"] += 1
            except Exception as exc:  # noqa: BLE001 - per-comment isolation
                errors.append(f"Comment on {source_item_id}: {exc}")

    logger.info(
        "write_target_complete",
        source_type=src_type,
        migrated=migrated,
        skipped=skipped,
        errors=len(errors),
    )

    return {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "id_map": id_map,
    }
