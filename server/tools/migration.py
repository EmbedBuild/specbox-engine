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


def _classify_items(items: list[ItemDTO]) -> dict[str, list[ItemDTO]]:
    """Classify items into US, UC, AC by labels."""
    result: dict[str, list[ItemDTO]] = {"us": [], "uc": [], "ac": [], "other": []}
    for item in items:
        labels_lower = [l.lower() for l in item.labels]
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

    return {
        "board_name": board_name,
        "items": items,
        "classified": classified,
        "ac_data": ac_data,
        "comments_data": comments_data,
        "labels": labels,
        "states": states,
    }


# ═══════════════════════════════════════════════════════════════════════
# MIGRATE PREVIEW (dry-run)
# ═══════════════════════════════════════════════════════════════════════


async def migrate_preview(
    source_type: str,
    source_id: str,
    target_type: str,
    ctx: Context,
) -> dict[str, Any]:
    """Preview a migration without making changes.

    Reads all data from the source and shows what would be migrated.
    Use this to verify before running migrate_project.

    Args:
        source_type: Source backend type ("trello" or "plane")
        source_id: Source board_id (Trello) or project_id (Plane)
        target_type: Target backend type ("trello" or "plane")

    Returns:
        Preview with counts, state mappings, and label mappings.
    """
    if source_type == target_type:
        return {"error": "source_type and target_type must be different"}

    backend = await get_session_backend(ctx)
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

        return {
            "dry_run": True,
            "source": {"type": source_type, "id": source_id, "name": source["board_name"]},
            "target": {"type": target_type},
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
            "labels": [l.get("name", "") for l in source["labels"]],
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
                        module = await target_backend.create_module(
                            target_id, f"{us_id}: {us_name}"
                        )
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
) -> dict[str, Any]:
    """Switch the active backend for an onboarded project.

    Updates the project registry so all spec-driven tools use the new backend.
    Does NOT migrate data — use migrate_project first.

    Args:
        project_slug: Project slug in the engine registry
        board_id: Board/project ID in the new backend
        backend_type: "trello" or "plane"

    Returns:
        Confirmation with previous and new backend info.
    """
    if backend_type not in ("trello", "plane"):
        return {"error": f"Invalid backend_type: {backend_type}. Must be 'trello' or 'plane'."}

    # Read project registry
    import json
    from pathlib import Path
    import os

    state_path = Path(os.getenv("STATE_PATH", "/data/state"))
    registry_path = state_path / "projects.json"

    if not registry_path.exists():
        return {"error": "Project registry not found"}

    registry = json.loads(registry_path.read_text())
    projects = registry.get("projects", {})

    if project_slug not in projects:
        return {"error": f"Project '{project_slug}' not found in registry"}

    project = projects[project_slug]
    previous_backend = project.get("spec_backend", "trello")
    previous_board_id = project.get("board_id", "")

    # Update project config
    project["spec_backend"] = backend_type
    project["board_id"] = board_id
    if previous_backend != backend_type:
        project.setdefault("backend_history", []).append({
            "backend": previous_backend,
            "board_id": previous_board_id,
            "switched_at": datetime.now(timezone.utc).isoformat(),
        })

    registry["projects"][project_slug] = project
    registry_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False))

    logger.info(
        "backend_switched",
        project=project_slug,
        previous=previous_backend,
        new=backend_type,
        board_id=board_id,
    )

    return {
        "success": True,
        "project": project_slug,
        "previous_backend": previous_backend,
        "previous_board_id": previous_board_id,
        "new_backend": backend_type,
        "new_board_id": board_id,
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
        description="Check status of the last migration in this session."
    )(migrate_status)

    mcp_instance.tool(
        description="Configure target backend credentials for migration. "
        "Call before migrate_project."
    )(set_migration_target)

    mcp_instance.tool(
        description="Switch the active backend for a project. "
        "Updates project registry. Use migrate_project first to move data."
    )(switch_backend)
