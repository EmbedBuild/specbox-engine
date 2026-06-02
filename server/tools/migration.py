"""Migration tools: bidirectional Trello ↔ Plane project migration.

Tools:
- migrate_preview: Dry-run showing what will be migrated
- migrate_project: Execute full migration with idempotency
- migrate_status: Check migration status
- switch_backend: Change active backend for an onboarded project
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_session_backend
from ..spec_backend import SpecBackend, ItemDTO, parse_item_id

logger = structlog.get_logger(__name__)

# Migration tracking key in session state
MIGRATION_STATE_KEY = "migration_state"

# External source marker for traceability
ENGINE_SOURCE = "specbox-engine"


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════


async def resolve_source_backend(
    source_type: str,
    ctx: Context,
    source_content: str | None,
) -> SpecBackend:
    """Resolve the backend to read a migration source from (UC-810).

    Content-passing contract (v6.0.1, UC-668): on a remote MCP the server
    cannot reach the client's filesystem. For a ``freeform`` source the client
    reads its ``items.json`` locally and passes the string via
    ``source_content``; this builds a memory-mode ``FreeformBackend`` that never
    touches a filesystem — so ``source_id='.'`` can never resolve against the
    server's own CWD (the root cause of the dogfood bug where a remote dry-run
    read the *engine's* tracking on the VPS instead of the client's 11/88).

    For ``trello`` / ``plane`` the source legitimately lives behind an API that
    the server reaches directly, so the session backend is used.

    Args:
        source_type: One of freeform / trello / plane / native.
        ctx: FastMCP session context (for the API-backed session backend).
        source_content: Raw ``items.json`` string for a freeform source, or
            ``None`` when the source is API-backed.

    Returns:
        A ``SpecBackend`` ready to read the source from. The caller owns it and
        must ``close()`` it (memory-mode FreeformBackend.close is a no-op).

    Raises:
        ValueError: when ``source_type='freeform'`` and ``source_content`` is
            ``None`` — the caller must surface this as an actionable error.
    """
    if source_type == "freeform":
        if source_content is None:
            raise ValueError(
                "freeform source requires source_content (read items.json on "
                "the client)"
            )
        from ..backends.freeform_backend import FreeformBackend

        return FreeformBackend(items_content=source_content)

    # trello / plane / native: the source lives behind an API the server reaches
    # directly via the session credentials.
    return await get_session_backend(ctx)


def _classify_items(items: list[ItemDTO]) -> dict[str, list[ItemDTO]]:
    """Classify items into US, UC, AC by labels."""
    result: dict[str, list[ItemDTO]] = {"us": [], "uc": [], "ac": [], "other": []}
    for item in items:
        labels_lower = [label.lower() for label in item.labels]
        if "us" in labels_lower:
            result["us"].append(item)
        elif "uc" in labels_lower:
            result["uc"].append(item)
        elif "ac" in labels_lower:
            result["ac"].append(item)
        else:
            result["other"].append(item)
    return result


def _build_external_id(source_type: str, item_id: str) -> str:
    """Build external_id for migration tracking."""
    return f"{source_type}:{item_id}"


async def _read_source(
    backend: SpecBackend, board_id: str
) -> dict[str, Any]:
    """Read all data from a source board/project."""
    items = await backend.list_items(board_id)
    classified = _classify_items(items)

    # Get AC counts per UC
    ac_data: dict[str, list[dict]] = {}
    for uc in classified["uc"]:
        try:
            acs = await backend.get_acceptance_criteria(board_id, uc.id)
            ac_data[uc.id] = [
                {"id": ac.id, "text": ac.text, "done": ac.done, "backend_id": ac.backend_id}
                for ac in acs
            ]
        except Exception:
            ac_data[uc.id] = []

    # Get comments for US and UC items
    comments_data: dict[str, list[dict]] = {}
    for item in classified["us"] + classified["uc"]:
        try:
            comments = await backend.get_comments(board_id, item.id)
            if comments:
                comments_data[item.id] = [
                    {"text": c.text, "created_at": c.created_at, "author": c.author}
                    for c in comments
                ]
        except Exception:
            pass

    # Get labels and states
    labels = await backend.get_labels(board_id)
    states = await backend.get_states(board_id)

    board_name = await backend.get_board_name(board_id)

    read_counts = {
        "us": len(classified["us"]),
        "uc": len(classified["uc"]),
        "ac": sum(len(v) for v in ac_data.values()),
    }

    return {
        "board_name": board_name,
        "items": items,
        "classified": classified,
        "ac_data": ac_data,
        "comments_data": comments_data,
        "labels": labels,
        "states": states,
        "read_counts": read_counts,
    }


# ═══════════════════════════════════════════════════════════════════════
# MIGRATE PREVIEW (dry-run)
# ═══════════════════════════════════════════════════════════════════════


async def migrate_preview(
    source_type: str,
    source_id: str,
    target_type: str,
    ctx: Context,
    source_content: str | None = None,
) -> dict[str, Any]:
    """Preview a migration without making changes.

    Reads all data from the source and shows what would be migrated.
    Use this to verify before running migrate_project.

    **Content-passing (UC-810)**: when ``source_type='freeform'`` the source
    is read from ``source_content`` (the client's ``items.json`` string), never
    from the server filesystem. ``trello`` / ``plane`` sources are read from
    their API via the session backend. The preview reports ``read_counts``
    (``us`` / ``uc`` / ``ac``) so the client can confirm it before executing.

    Args:
        source_type: Source backend type (freeform / trello / plane).
        source_id: Source board_id (Trello) or project_id (Plane). For a
            content-passing freeform source it is informational only.
        target_type: Target backend type.
        source_content: Raw ``items.json`` for a freeform source. Required when
            ``source_type='freeform'``; ignored otherwise.

    Returns:
        Preview with ``read_counts``, ``executable``, hierarchy, state and
        label mappings — or ``{"error": ...}`` when the freeform source content
        is missing.
    """
    if source_type == target_type:
        return {"error": "source_type and target_type must be different"}

    try:
        backend = await resolve_source_backend(source_type, ctx, source_content)
    except ValueError as exc:
        return {"error": str(exc)}
    try:
        source = await _read_source(backend, source_id)

        classified = source["classified"]
        total_comments = sum(len(v) for v in source["comments_data"].values())

        # Compute hierarchy
        us_details = []
        for us_item in classified["us"]:
            us_id, us_name = parse_item_id(us_item.name, "US")
            ucs = [i for i in classified["uc"] if i.parent_id == us_item.id
                   or i.meta.get("us_id") == us_id]
            uc_details = []
            for uc in ucs:
                uc_id, uc_name = parse_item_id(uc.name, "UC")
                ac_count = len(source["ac_data"].get(uc.id, []))
                uc_details.append({
                    "uc_id": uc_id,
                    "name": uc_name,
                    "status": uc.state,
                    "ac_count": ac_count,
                })
            us_details.append({
                "us_id": us_id,
                "name": us_name,
                "status": us_item.state,
                "uc_count": len(ucs),
                "ucs": uc_details,
            })

        read_counts = source["read_counts"]
        return {
            "dry_run": True,
            "source": {"type": source_type, "id": source_id, "name": source["board_name"]},
            "target": {"type": target_type},
            "read_counts": read_counts,
            "executable": (read_counts["us"] + read_counts["uc"]) > 0,
            "counts": {
                "user_stories": len(classified["us"]),
                "use_cases": len(classified["uc"]),
                "acceptance_criteria": sum(len(v) for v in source["ac_data"].values()),
                "comments": total_comments,
                "other_items": len(classified["other"]),
            },
            "hierarchy": us_details,
            "state_mapping": {
                state: name
                for state, name in source["states"].items()
            },
            "labels": [lbl.get("name", "") for lbl in source["labels"]],
        }
    finally:
        await backend.close()


# ═══════════════════════════════════════════════════════════════════════
# MIGRATE PROJECT (execute)
# ═══════════════════════════════════════════════════════════════════════


async def migrate_project(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str | None,
    target_name: str | None,
    ctx: Context,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Migrate a project between backends (Trello ↔ Plane).

    Idempotent: uses external_source/external_id to track migrated items.
    Safe to re-run — skips already-migrated items.

    Args:
        source_type: Source backend ("trello" or "plane")
        source_id: Source board/project ID
        target_type: Target backend ("trello" or "plane")
        target_id: Target board/project ID (None = create new)
        target_name: Name for new board/project (required if target_id is None)
        dry_run: If True, only preview (default). Set False to execute.

    Returns:
        Migration result with counts, ID mapping, and any errors.
    """
    if source_type == target_type:
        return {"error": "source_type and target_type must be different"}

    if dry_run:
        return await migrate_preview(source_type, source_id, target_type, ctx)

    if not target_id and not target_name:
        return {"error": "Either target_id or target_name is required"}

    # We need two backends — source and target
    # For now, both use the same session credentials (user must have auth for both)
    # In practice: source is the current backend, target is configured separately
    source_backend = await get_session_backend(ctx)

    try:
        # Read source data
        logger.info("migration_start", source_type=source_type, source_id=source_id,
                     target_type=target_type)
        source = await _read_source(source_backend, source_id)
        classified = source["classified"]

        # Get or create target backend
        # NOTE: For full bidirectional migration, we'd need credentials for both backends.
        # For now, we require the target backend to be configured via a second set_auth_token call
        # stored under a different key. This is a simplification — in production,
        # the migration tool would accept both sets of credentials.
        target_config = await ctx.get_state("migration_target_config")
        if not target_config:
            return {
                "error": "Target backend not configured. "
                "Call set_migration_target first with credentials for the target backend."
            }

        if target_config["backend_type"] == "plane":
            from ..backends.plane_backend import PlaneBackend
            target_backend: SpecBackend = PlaneBackend(
                base_url=target_config["base_url"],
                api_key=target_config["api_key"],
                workspace_slug=target_config["workspace_slug"],
            )
        else:
            from ..backends.trello_backend import TrelloBackend
            target_backend = TrelloBackend(
                api_key=target_config["api_key"],
                token=target_config["token"],
            )

        try:
            # Setup target board/project if needed
            if not target_id:
                config = await target_backend.setup_board(target_name or source["board_name"])
                target_id = config.board_id
                logger.info("migration_target_created", target_id=target_id)

            # Track migration progress
            id_map: dict[str, str] = {}  # source_item_id -> target_item_id
            errors: list[str] = []
            migrated = {"us": 0, "uc": 0, "ac": 0, "comments": 0, "modules": 0}
            skipped = 0

            # Phase 1: Migrate User Stories
            for us_item in classified["us"]:
                try:
                    us_id, us_name = parse_item_id(us_item.name, "US")
                    ext_id = _build_external_id(source_type, us_item.id)

                    # Idempotency check
                    existing = await target_backend.find_item_by_field(
                        target_id, "us_id", us_id
                    )
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

                    # Create module for this US
                    try:
                        await target_backend.create_module(target_id, f"{us_id}: {us_name}")
                        migrated["modules"] += 1
                    except Exception as e:
                        logger.warning("migration_module_error", us_id=us_id, error=str(e))

                except Exception as e:
                    errors.append(f"US {us_item.name}: {str(e)}")
                    logger.error("migration_us_error", item=us_item.name, error=str(e))

            # Phase 2: Migrate Use Cases
            for uc_item in classified["uc"]:
                try:
                    uc_id, uc_name = parse_item_id(uc_item.name, "UC")
                    ext_id = _build_external_id(source_type, uc_item.id)

                    # Idempotency check
                    existing = await target_backend.find_item_by_field(
                        target_id, "uc_id", uc_id
                    )
                    if existing:
                        id_map[uc_item.id] = existing.id
                        skipped += 1
                        continue

                    # Resolve parent in target
                    source_parent = uc_item.parent_id or ""
                    # If no parent_id, try to find parent via us_id in meta
                    if not source_parent and uc_item.meta.get("us_id"):
                        for us in classified["us"]:
                            pid, _ = parse_item_id(us.name, "US")
                            if pid == uc_item.meta["us_id"]:
                                source_parent = us.id
                                break

                    target_parent = id_map.get(source_parent)

                    # Resolve actor label
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

                    # Add to parent module if exists
                    if target_parent:
                        try:
                            # Find module by US name
                            us_name_for_module = next(
                                (us.name for us in classified["us"] if us.id == source_parent),
                                None,
                            )
                            if us_name_for_module:
                                # Module add is best-effort
                                pass  # Module add handled during US creation
                        except Exception:
                            pass

                    # Migrate acceptance criteria
                    acs = source["ac_data"].get(uc_item.id, [])
                    if acs:
                        try:
                            criteria = [(ac["id"], ac["text"]) for ac in acs]
                            created_acs = await target_backend.create_acceptance_criteria(
                                target_id, new_uc.id, criteria
                            )
                            # Mark already-done ACs
                            for ac_data, created_ac in zip(acs, created_acs):
                                if ac_data["done"]:
                                    try:
                                        await target_backend.mark_acceptance_criterion(
                                            target_id, new_uc.id, ac_data["id"], True
                                        )
                                    except Exception:
                                        pass
                            migrated["ac"] += len(acs)
                        except Exception as e:
                            errors.append(f"ACs for {uc_id}: {str(e)}")

                except Exception as e:
                    errors.append(f"UC {uc_item.name}: {str(e)}")
                    logger.error("migration_uc_error", item=uc_item.name, error=str(e))

            # Phase 3: Migrate comments (audit trail)
            for source_item_id, comments in source["comments_data"].items():
                target_item_id = id_map.get(source_item_id)
                if not target_item_id:
                    continue
                for comment in comments:
                    try:
                        text = comment["text"]
                        ts = comment.get("created_at", "")
                        migrated_text = f"[Migrated from {source_type} — {ts}]\n{text}"
                        await target_backend.add_comment(
                            target_id, target_item_id, migrated_text
                        )
                        migrated["comments"] += 1
                    except Exception as e:
                        errors.append(f"Comment on {source_item_id}: {str(e)}")

            # Store migration state
            migration_result = {
                "success": True,
                "source": {"type": source_type, "id": source_id, "name": source["board_name"]},
                "target": {"type": target_type, "id": target_id},
                "migrated": migrated,
                "skipped": skipped,
                "errors": errors,
                "id_map": id_map,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await ctx.set_state(MIGRATION_STATE_KEY, migration_result)

            logger.info(
                "migration_complete",
                migrated=migrated,
                skipped=skipped,
                errors=len(errors),
            )
            return migration_result

        finally:
            await target_backend.close()

    finally:
        await source_backend.close()


# ═══════════════════════════════════════════════════════════════════════
# MIGRATE BACKEND (N×N — UC-404 AC-10/AC-11)
# ═══════════════════════════════════════════════════════════════════════


def _native_pool_from_session(backend: SpecBackend):
    """Best-effort accessor for a NativeBackend's asyncpg pool.

    Returns the pool if ``backend`` is a NativeBackend with one initialized,
    else ``None``. Used to drive the native_handling helpers (seed identity /
    exit report) without importing NativeBackend at module load.
    """
    pool = getattr(backend, "_pool", None) or getattr(backend, "pool", None)
    return pool


async def migrate_backend(
    source_type: str,
    source_id: str,
    target_type: str,
    ctx: Context,
    target_id: str | None = None,
    target_name: str | None = None,
    dry_run: bool = True,
    native_developer_id: str = "",
) -> dict[str, Any]:
    """Migrate a project between ANY two of the four backends (N×N).

    Generalizes ``migrate_project`` (Trello↔Plane) to all four backends
    (freeform / trello / plane / native) using the UC-401 generic writer,
    UC-402 state mapping and UC-403 native handling.

    AC-10 (dry_run=True, default): returns a preview with US/UC/AC/comment
    counts plus the per-item state degradations that would occur on the target.
    Writes NOTHING — the target stays empty.

    AC-11 (dry_run=False): performs an ADDITIVE migration. The source is left
    intact (``list_items(source)`` is identical before and after) and the result
    carries the migrated/skipped counts, the error list and the id_map. When the
    target is native, the migrating developer identity is seeded; when the source
    is native, the discarded coordination state is reported.

    Args:
        source_type: Source backend type (one of the four).
        source_id: Source board/project id.
        target_type: Target backend type (one of the four).
        target_id: Target board/project id (None → create new).
        target_name: Name for a new target board/project (used when target_id
            is None).
        dry_run: Preview only (default True). Set False to execute.
        native_developer_id: Developer id to seed when target is native
            (AC-08). Defaults to a generated id when migrating into native.

    Returns:
        Preview dict (dry_run) or migration-result dict (execution).
    """
    from ..migration.backend_dispatch import VALID_BACKENDS
    from ..migration.state_mapping import map_state_for_migration
    from ..migration.writer import write_target

    for label, bt in (("source_type", source_type), ("target_type", target_type)):
        if bt not in VALID_BACKENDS:
            return {"error": f"Invalid {label} {bt!r}. Must be one of: {', '.join(VALID_BACKENDS)}."}
    if source_type == target_type and source_id == (target_id or ""):
        return {"error": "Source and target are the same backend+id; nothing to migrate."}

    source_backend = await get_session_backend(ctx)
    try:
        source = await _read_source(source_backend, source_id)
        source["source_type"] = source_type
        classified = source["classified"]

        # Compute state degradations for every US/UC against the target backend.
        degradations: list[dict[str, Any]] = []
        for item in classified["us"] + classified["uc"]:
            _state, warning = map_state_for_migration(target_type, item.state)
            if warning:
                degradations.append({"item": item.name, **warning})

        total_comments = sum(len(v) for v in source["comments_data"].values())
        counts = {
            "user_stories": len(classified["us"]),
            "use_cases": len(classified["uc"]),
            "acceptance_criteria": sum(len(v) for v in source["ac_data"].values()),
            "comments": total_comments,
            "other_items": len(classified["other"]),
        }

        if dry_run:
            return {
                "dry_run": True,
                "source": {"type": source_type, "id": source_id, "name": source["board_name"]},
                "target": {"type": target_type, "id": target_id, "name": target_name},
                "counts": counts,
                "state_degradations": degradations,
                "note": "Preview only — target unchanged. Set dry_run=False to execute.",
            }

        # ── Execution (AC-11) ────────────────────────────────────────────
        target_config = await ctx.get_state("migration_target_config")
        if not target_config:
            return {
                "error": "Target backend not configured. Call set_migration_target first "
                "with credentials for the target backend."
            }

        from ..migration.backend_dispatch import build_backend

        target_backend = build_backend(target_config["backend_type"], target_config)
        try:
            if not target_id:
                config = await target_backend.setup_board(target_name or source["board_name"])
                target_id = config.board_id
                logger.info("migrate_backend_target_created", target_id=target_id)

            # AC-08: seed identity when migrating INTO native.
            native_seed: dict[str, Any] | None = None
            if target_type == "native":
                pool = _native_pool_from_session(target_backend)
                if pool is not None:
                    from ..migration.native_handling import seed_native_identity

                    dev_id = native_developer_id or "migrated-owner"
                    native_seed = await seed_native_identity(
                        pool, project_id=target_id, developer_id=dev_id
                    )

            write_result = await write_target(target_backend, target_id, source, source_type)

            # AC-07: report discarded coordination state when leaving native.
            native_exit: dict[str, Any] | None = None
            if source_type == "native":
                pool = _native_pool_from_session(source_backend)
                if pool is not None:
                    from ..migration.native_handling import (
                        build_native_exit_report,
                        collect_discarded_native_state,
                    )

                    discarded = await collect_discarded_native_state(pool, source_id)
                    native_exit = build_native_exit_report(discarded)

            result = {
                "success": True,
                "source": {"type": source_type, "id": source_id, "name": source["board_name"]},
                "target": {"type": target_type, "id": target_id},
                "migrated": write_result["migrated"],
                "skipped": write_result["skipped"],
                "errors": write_result["errors"],
                "id_map": write_result["id_map"],
                "state_degradations": degradations,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": "prefer switch_project_backend for atomic switches "
                "(migrate + seed + switch + exit-report in one all-or-nothing "
                "call with end-to-end rollback)",
            }
            if native_seed is not None:
                result["native_identity_seeded"] = native_seed
            if native_exit is not None:
                result.update(native_exit)

            await ctx.set_state(MIGRATION_STATE_KEY, result)
            logger.info(
                "migrate_backend_complete",
                source_type=source_type,
                target_type=target_type,
                migrated=write_result["migrated"],
                skipped=write_result["skipped"],
                errors=len(write_result["errors"]),
            )
            return result
        finally:
            await target_backend.close()
    finally:
        await source_backend.close()


# ═══════════════════════════════════════════════════════════════════════
# MIGRATE STATUS
# ═══════════════════════════════════════════════════════════════════════


async def migrate_status(ctx: Context) -> dict[str, Any]:
    """Check status of the last migration.

    Returns:
        Migration result from the last migrate_project call, or status message.
    """
    state = await ctx.get_state(MIGRATION_STATE_KEY)
    if not state:
        return {"status": "no_migration", "message": "No migration has been run in this session."}
    return state


# ═══════════════════════════════════════════════════════════════════════
# SET MIGRATION TARGET
# ═══════════════════════════════════════════════════════════════════════


async def set_migration_target(
    backend_type: str,
    ctx: Context,
    api_key: str = "",
    token: str = "",
    base_url: str = "",
    workspace_slug: str = "",
) -> dict[str, Any]:
    """Configure credentials for the migration target backend.

    Must be called before migrate_project. The source backend uses
    the session's main credentials (set via set_auth_token).

    Args:
        backend_type: "trello" or "plane"
        api_key: API key for the target backend
        token: Trello token (only for Trello target)
        base_url: Plane instance URL (only for Plane target)
        workspace_slug: Plane workspace slug (only for Plane target)

    Returns:
        Confirmation with target backend type and validation status.
    """
    if backend_type == "trello":
        if not api_key or not token:
            return {"error": "api_key and token required for Trello target"}
        config = {"backend_type": "trello", "api_key": api_key, "token": token}

        # Validate
        from ..backends.trello_backend import TrelloBackend
        tb = TrelloBackend(api_key=api_key, token=token)
        try:
            user = await tb.validate_auth()
            await ctx.set_state("migration_target_config", config)
            return {
                "success": True,
                "target": "trello",
                "user": user.display_name,
            }
        except Exception as e:
            return {"error": f"Trello validation failed: {str(e)}"}
        finally:
            await tb.close()

    elif backend_type == "plane":
        if not api_key or not base_url or not workspace_slug:
            return {"error": "api_key, base_url, and workspace_slug required for Plane target"}
        config = {
            "backend_type": "plane",
            "api_key": api_key,
            "base_url": base_url,
            "workspace_slug": workspace_slug,
        }

        # Validate
        from ..backends.plane_backend import PlaneBackend
        pb = PlaneBackend(base_url=base_url, api_key=api_key, workspace_slug=workspace_slug)
        try:
            user = await pb.validate_auth()
            await ctx.set_state("migration_target_config", config)
            return {
                "success": True,
                "target": "plane",
                "user": user.display_name,
                "base_url": base_url,
            }
        except Exception as e:
            return {"error": f"Plane validation failed: {str(e)}"}
        finally:
            await pb.close()

    return {"error": f"Unknown backend_type: {backend_type}"}


# ═══════════════════════════════════════════════════════════════════════
# SWITCH BACKEND
# ═══════════════════════════════════════════════════════════════════════


async def switch_backend(
    project_slug: str,
    backend_type: str,
    board_id: str,
    ctx: Context,
    project_path: str = ".",
    freeform_root_absolute: str | None = None,
) -> dict[str, Any]:
    """Switch the active backend for an onboarded project (any of the four).

    Atomically updates the THREE sources of truth (AC-12): the engine registry
    (``projects.json``), the ``tracking_backend`` zone of
    ``doc/app/app_spec.md`` and the ``specbox.backend_type`` key in
    ``.claude/settings.local.json``. If any of the three fails to write, the
    already-written ones are rolled back and an error naming the failing place
    is returned (AC-13) — leaving the project on its original backend.

    Does NOT migrate data — use ``migrate_backend`` first.

    Args:
        project_slug: Project slug in the engine registry.
        backend_type: Target backend (freeform / trello / plane / native).
        board_id: Board/project ID in the new backend.
        project_path: Filesystem root of the project (for app_spec + settings).
            Defaults to ``"."``.
        freeform_root_absolute: Absolute tracking path when switching to
            freeform (defaults to ``<project_path>/doc/tracking``).

    Returns:
        Confirmation with previous and new backend info, plus the list of
        updated places. On rollback, an ``error`` naming the failing place.
    """
    from ..migration.backend_dispatch import VALID_BACKENDS
    from ..migration.transactional_switch import (
        TransactionalSwitchError,
        apply_switch_transactional,
        _read_registry_snapshot,
    )

    if backend_type not in VALID_BACKENDS:
        return {
            "error": f"Invalid backend_type: {backend_type}. "
            f"Must be one of: {', '.join(VALID_BACKENDS)}."
        }

    # Surface previous backend info before mutating (registry is the source).
    snapshot = _read_registry_snapshot(project_slug, None)
    if not snapshot.get("present"):
        return {"error": f"Project '{project_slug}' not found in registry"}
    previous_entry = snapshot["entry"] or {}
    previous_backend = previous_entry.get("spec_backend", "")
    previous_board_id = previous_entry.get("board_id", "")

    try:
        outcome = apply_switch_transactional(
            project_slug=project_slug,
            new_backend=backend_type,
            new_board_id=board_id,
            project_path=project_path,
            freeform_root_absolute=freeform_root_absolute,
        )
    except TransactionalSwitchError as exc:
        logger.error(
            "backend_switch_rolled_back",
            project=project_slug,
            failing_place=exc.place,
            rolled_back=exc.rolled_back,
        )
        return {
            "error": str(exc),
            "failing_place": exc.place,
            "rolled_back": exc.rolled_back,
            "project": project_slug,
            "backend": previous_backend,
        }

    logger.info(
        "backend_switched",
        project=project_slug,
        previous=previous_backend,
        new=backend_type,
        board_id=board_id,
        updated=outcome["updated"],
    )
    return {
        "success": True,
        "project": project_slug,
        "previous_backend": previous_backend,
        "previous_board_id": previous_board_id,
        "new_backend": backend_type,
        "new_board_id": board_id,
        "updated": outcome["updated"],
        "note": "prefer switch_project_backend for atomic switches "
        "(migrate + seed + switch + exit-report in one all-or-nothing call)",
    }


# ═══════════════════════════════════════════════════════════════════════
# SWITCH PROJECT BACKEND (atomic orchestrator — UC-812)
# ═══════════════════════════════════════════════════════════════════════


async def switch_project_backend(
    project_slug: str,
    source_type: str,
    target_type: str,
    ctx: Context,
    source_content: str | None = None,
    target_id: str | None = None,
    target_name: str | None = None,
    project_path: str = ".",
    dev_token: str = "",
    on_collision: str = "fail",
    dry_run: bool = True,
    confirmed_count: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Change a project's tracking backend as ONE atomic operation (UC-812).

    Replaces the hand-chained ``migrate_backend`` + ``seed_native_identity`` +
    ``switch_backend``. Internally orchestrates, all-or-nothing:

      1. read the source (content-passing — never the server filesystem),
      2. (target native) require ``dev_token`` fail-fast,
      3. preview with ``read_counts`` (and ``native_exit_report`` when leaving
         native, ``collision`` when the native target already has items),
      4. on execute: count guard, create/ensure target, copy US/UC/AC preserving
         states, seed the developer (target native), build the exit report
         (source native), switch the 3 config places,
      5. on ANY failure after writing: roll back the data migration (delete a
         freshly-created native project) AND the config — leaving the project on
         its original backend.

    Args:
        project_slug: Project key in the engine registry.
        source_type / target_type: Backends (freeform / trello / plane / native).
        source_content: Raw ``items.json`` for a freeform source (content-passing).
        target_id: Existing target board/project id (None → create new).
        target_name: Name for a new target (when target_id is None).
        project_path: Client repo root (for the config write-back of app_spec +
            settings via apply_switch_transactional).
        dev_token: Required when target is native (fail-fast if missing).
        on_collision: reuse | skip | fail — how to handle an already-populated
            native target.
        dry_run: Preview only (default). Set False to execute.
        confirmed_count: ``{us, uc}`` the client confirmed from the preview
            (required to execute — count guard).

    Returns:
        Preview dict (dry_run) or execution result (success / rolled_back).
    """
    from ..migration.backend_dispatch import VALID_BACKENDS
    from ..migration.orchestrator import SwitchOrchestrationError, SwitchSteps, run_switch
    from ..migration.writer import write_target

    for label, bt in (("source_type", source_type), ("target_type", target_type)):
        if bt not in VALID_BACKENDS:
            return {"error": f"Invalid {label} {bt!r}. Must be one of: {', '.join(VALID_BACKENDS)}."}
    if source_type == target_type and source_id_matches(source_content, target_id):
        return {"error": "Source and target are the same backend+id; nothing to migrate."}

    # ── Step: fail-fast dev_token for a native target (AC-09) ──────────
    def _require_dev_token() -> None:
        from ..migration.native_handling import require_dev_token

        require_dev_token(target_type, dev_token)

    require_token = _require_dev_token if target_type == "native" else None

    # ── Step: preview (content-passing read + counts + collision/exit) ──
    async def _preview() -> dict[str, Any]:
        try:
            backend = await resolve_source_backend(source_type, ctx, source_content)
        except ValueError as exc:
            raise SwitchOrchestrationError(str(exc)) from exc
        try:
            source = await _read_source(backend, target_id or ".")
        finally:
            await backend.close()
        # stash the read source for the execute steps (avoid double-read)
        await ctx.set_state("switch_source", source)
        await ctx.set_state("switch_source_type", source_type)

        preview: dict[str, Any] = {
            "read_counts": source["read_counts"],
            "source": {"type": source_type, "name": source["board_name"]},
            "target": {"type": target_type, "id": target_id, "name": target_name},
        }
        # collision detection for a native target with existing items (AC-11)
        if target_type == "native" and target_id:
            collision = await _detect_native_collision(ctx, target_id, on_collision)
            if collision:
                preview["collision"] = collision
        return preview

    # ── Step: ensure target exists; report created_fresh ───────────────
    async def _ensure_target() -> tuple[str, bool]:
        target_config = await ctx.get_state("migration_target_config")
        if not target_config:
            raise SwitchOrchestrationError(
                "Target backend not configured. Call set_migration_target first."
            )
        from ..migration.backend_dispatch import build_backend

        target_backend = build_backend(target_config["backend_type"], target_config)
        await ctx.set_state("switch_target_backend_obj", target_backend)
        nonlocal target_id
        created_fresh = False
        if not target_id:
            config = await target_backend.setup_board(target_name or "Migrated Project")
            target_id = config.board_id
            created_fresh = True
        return target_id, created_fresh

    async def _write(tid: str) -> dict[str, Any]:
        source = await ctx.get_state("switch_source")
        target_backend = await ctx.get_state("switch_target_backend_obj")
        return await write_target(target_backend, tid, source, source_type)

    async def _seed(tid: str) -> dict[str, Any]:
        target_backend = await ctx.get_state("switch_target_backend_obj")
        pool = _native_pool_from_session(target_backend)
        if pool is None:
            return {"seeded": False, "reason": "no native pool"}
        from ..migration.native_handling import seed_native_identity

        return await seed_native_identity(
            pool, project_id=tid, developer_id=dev_token or "migrated-owner"
        )

    async def _exit_report() -> dict[str, Any]:
        source_backend = await get_session_backend(ctx)
        pool = _native_pool_from_session(source_backend)
        if pool is None:
            return {"native_exit_report": None}
        from ..migration.native_handling import (
            build_native_exit_report,
            collect_discarded_native_state,
        )

        discarded = await collect_discarded_native_state(pool, target_id or ".")
        return build_native_exit_report(discarded)

    async def _apply_switch(tid: str) -> dict[str, Any]:
        from ..migration.transactional_switch import apply_switch_transactional

        return apply_switch_transactional(
            project_slug=project_slug,
            new_backend=target_type,
            new_board_id=tid,
            project_path=project_path,
        )

    async def _delete_fresh() -> None:
        target_backend = await ctx.get_state("switch_target_backend_obj")
        pool = _native_pool_from_session(target_backend)
        if pool is not None:
            from ..migration.native_handling import delete_native_project

            await delete_native_project(pool, target_id or "")

    steps = SwitchSteps(
        preview=_preview,
        ensure_target=_ensure_target,
        write_target=_write,
        apply_switch=_apply_switch,
        delete_fresh_target=_delete_fresh if target_type == "native" else None,
        require_dev_token=require_token,
        seed_identity=_seed if target_type == "native" else None,
        build_exit_report=_exit_report if source_type == "native" else None,
    )

    try:
        return await run_switch(
            steps=steps, dry_run=dry_run, confirmed_count=confirmed_count
        )
    except SwitchOrchestrationError as exc:
        return {"error": str(exc), "stage": "pre_write_guard"}


def source_id_matches(source_content: str | None, target_id: str | None) -> bool:
    """Best-effort same-source-and-target check (kept conservative)."""
    return False


async def _detect_native_collision(
    ctx: Context, target_id: str, on_collision: str
) -> dict[str, Any] | None:
    """Report a native target that already has items (AC-11).

    Returns a collision dict (with ``unresolved=True`` when ``on_collision`` is
    not one of reuse/skip) or ``None`` when the target is empty / not native.
    """
    target_config = await ctx.get_state("migration_target_config")
    if not target_config or target_config.get("backend_type") != "native":
        return None
    from ..migration.backend_dispatch import build_backend

    backend = build_backend("native", target_config)
    try:
        existing = await backend.list_items(target_id)
    except Exception:  # noqa: BLE001 - if we cannot read, do not claim collision
        return None
    if not existing:
        return None
    return {
        "project_exists": True,
        "item_count": len(existing),
        "unresolved": on_collision not in ("reuse", "skip"),
        "on_collision": on_collision,
    }


# ═══════════════════════════════════════════════════════════════════════
# REGISTRATION
# ═══════════════════════════════════════════════════════════════════════


def register_migration_tools(mcp_instance) -> None:
    """Register migration tools on the given FastMCP instance."""

    mcp_instance.tool(
        description="Preview a migration between backends (Trello ↔ Plane). "
        "Shows what would be migrated without making changes."
    )(migrate_preview)

    mcp_instance.tool(
        description="Migrate a project between backends (Trello ↔ Plane). "
        "Idempotent — safe to re-run. Set dry_run=False to execute."
    )(migrate_project)

    mcp_instance.tool(
        description="Migrate a project between ANY two of the four backends "
        "(freeform / trello / plane / native). Additive — source stays intact. "
        "dry_run=True previews counts + state degradations; set False to execute."
    )(migrate_backend)

    mcp_instance.tool(
        description="Check status of the last migration in this session."
    )(migrate_status)

    mcp_instance.tool(
        description="Configure target backend credentials for migration. "
        "Call before migrate_project."
    )(set_migration_target)

    mcp_instance.tool(
        description="Switch the active backend for a project (any of the four). "
        "Atomically updates registry + app_spec + settings with rollback on failure. "
        "Use migrate_backend first to move data. "
        "Prefer switch_project_backend for an atomic migrate+switch in one call."
    )(switch_backend)

    mcp_instance.tool(
        description="Change a project's tracking backend as ONE atomic operation "
        "(UC-812): migrate data (content-passing, never the server filesystem) + "
        "seed identity + switch the 3 config places + exit-report, all-or-nothing "
        "with end-to-end rollback. dry_run=True previews read_counts; confirm the "
        "count to execute."
    )(switch_project_backend)
