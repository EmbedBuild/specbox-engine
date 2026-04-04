"""Spec-Driven tools: Backend-agnostic operations for US/UC/AC management.

Works with both Trello and Plane backends via the SpecBackend ABC.

Consolidated tool modules:
- auth: set_auth_token
- board: setup_board, get_board_status, import_spec
- user_story: list_us, get_us, move_us, get_us_progress
- use_case: list_uc, get_uc, move_uc, start_uc, complete_uc
- acceptance: mark_ac, mark_ac_batch, get_ac_status
- evidence: attach_evidence, get_evidence
- dashboard: get_sprint_status, get_delivery_report, find_next_uc
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import (
    get_session_backend,
    store_freeform_credentials,
    store_plane_credentials,
    store_session_credentials,
)
from ..models import (
    ImportSpec,
    WORKFLOW_LIST_NAMES,
)
from ..pdf_generator import markdown_to_pdf
from ..spec_backend import (
    ItemDTO,
    ModuleDTO,
    SpecBackend,
    parse_item_id,
)

logger = structlog.get_logger(__name__)

# ── Active UC Marker ─────────────────────────────────────────────────
# The spec-guard.mjs hook checks for this file before allowing writes
# to source code. This ensures the pipeline contract is enforced at
# the filesystem level — no UC active = no code writes allowed.

ACTIVE_UC_FILENAME = ".quality/active_uc.json"


def _write_active_uc_marker(uc_id: str, board_id: str, feature: str = "") -> None:
    """Write the active UC marker so spec-guard.mjs allows code writes."""
    marker_path = Path(ACTIVE_UC_FILENAME)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(
            {
                "uc_id": uc_id,
                "board_id": board_id,
                "feature": feature,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n"
    )
    logger.info("active_uc_marker_written", uc_id=uc_id, path=str(marker_path))


def _clear_active_uc_marker() -> None:
    """Remove the active UC marker after UC completion."""
    marker_path = Path(ACTIVE_UC_FILENAME)
    if marker_path.exists():
        marker_path.unlink()
        logger.info("active_uc_marker_cleared", path=str(marker_path))


# ── Helpers ──────────────────────────────────────────────────────────


def _extract_meta_str(item: ItemDTO, key: str, default: str = "") -> str:
    """Extract a string value from item metadata."""
    val = item.meta.get(key, default)
    return str(val) if val else default


def _extract_meta_float(item: ItemDTO, key: str, default: float = 0.0) -> float:
    """Extract a float value from item metadata."""
    val = item.meta.get(key, default)
    try:
        return float(val) if val else default
    except (TypeError, ValueError):
        return default


def _is_us(item: ItemDTO) -> bool:
    """Check if an item is a User Story."""
    return "US" in item.labels


def _is_uc(item: ItemDTO) -> bool:
    """Check if an item is a Use Case."""
    return "UC" in item.labels


def _get_us_id(item: ItemDTO) -> str:
    """Get the us_id from item metadata or parse from name."""
    us_id = _extract_meta_str(item, "us_id")
    if us_id:
        return us_id
    parsed_id, _ = parse_item_id(item.name, "US")
    return parsed_id


def _get_uc_id(item: ItemDTO) -> str:
    """Get the uc_id from item metadata or parse from name."""
    uc_id = _extract_meta_str(item, "uc_id")
    if uc_id:
        return uc_id
    parsed_id, _ = parse_item_id(item.name, "UC")
    return parsed_id


def _clean_name(name: str, prefix_id: str) -> str:
    """Remove the prefix ID from a name (e.g., 'US-01: Name' -> 'Name')."""
    if prefix_id and name.startswith(prefix_id):
        cleaned = name[len(prefix_id):]
        return cleaned.lstrip(":").lstrip(" ").lstrip("]").lstrip(" ")
    return name


def _find_us_item(items: list[ItemDTO], us_id: str) -> ItemDTO | None:
    """Find a US item by us_id in a pre-fetched items list."""
    for item in items:
        if _is_us(item) and _get_us_id(item) == us_id:
            return item
    return None


def _find_uc_item(items: list[ItemDTO], uc_id: str) -> ItemDTO | None:
    """Find a UC item by uc_id in a pre-fetched items list."""
    for item in items:
        if _is_uc(item) and _get_uc_id(item) == uc_id:
            return item
    return None


def _get_uc_children(items: list[ItemDTO], us_id: str) -> list[ItemDTO]:
    """Get all UC items belonging to a US, matching by parent_id or us_id meta."""
    us_item = _find_us_item(items, us_id)
    children = []
    for item in items:
        if not _is_uc(item):
            continue
        # Match by metadata us_id
        if _extract_meta_str(item, "us_id") == us_id:
            children.append(item)
            continue
        # Match by parent_id
        if us_item and item.parent_id == us_item.id:
            children.append(item)
            continue
    return children


async def _get_ac_counts(
    backend: SpecBackend, board_id: str, uc_item: ItemDTO
) -> tuple[int, int]:
    """Get (total, done) AC counts for a UC item."""
    acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
    total = len(acs)
    done = sum(1 for ac in acs if ac.done)
    return total, done


# ═══════════════════════════════════════════════════════════════════════
# AUTH (1 tool)
# ═══════════════════════════════════════════════════════════════════════


async def set_auth_token(
    api_key: str,
    token: str,
    ctx: Context,
    backend_type: str = "trello",
    base_url: str = "",
    workspace_slug: str = "",
    root_path: str = "",
) -> dict[str, Any]:
    """Configure backend API credentials for this session.

    Each user must call this tool before using any other tool.
    Credentials are isolated per session — other users cannot access yours.

    Args:
        api_key: API key (Trello: 32-char key; Plane: API token; FreeForm: ignored, pass "freeform")
        token: API token (Trello: 64-char OAuth token; Plane/FreeForm: ignored, pass "")
        backend_type: "trello" (default), "plane", or "freeform"
        base_url: Plane base URL (e.g., "https://plane.example.com"); required for Plane
        workspace_slug: Plane workspace slug; required for Plane
        root_path: FreeForm data directory (default: "doc/tracking"); required for FreeForm

    Returns:
        Authentication status with user info if successful.
    """
    if backend_type != "freeform" and (not api_key or not api_key.strip()):
        return {"error": "api_key is required", "code": "MISSING_API_KEY"}

    api_key = api_key.strip() if api_key else ""
    token = token.strip() if token else ""

    if backend_type == "freeform":
        # FreeForm authentication (local filesystem, no API)
        root = root_path.strip() if root_path else "doc/tracking"

        try:
            from ..backends.freeform_backend import FreeformBackend

            backend = FreeformBackend(root=root)
            user = await backend.validate_auth()
            await backend.close()
        except Exception as e:
            logger.error("freeform_auth_error", error=str(e))
            return {"error": f"FreeForm init failed: {str(e)}", "code": "FREEFORM_ERROR"}

        await store_freeform_credentials(ctx, root)
        logger.info("auth_token_set", backend="freeform", root=root)

        return {
            "success": True,
            "backend": "freeform",
            "message": f"FreeForm backend initialized at {root}/",
            "user": {
                "id": user.id,
                "username": user.username,
                "fullName": user.display_name,
            },
            "summary": f"Backend FreeForm configurado. Datos en {root}/. Sin API externa requerida.",
        }

    elif backend_type == "plane":
        # Plane authentication
        if not base_url or not base_url.strip():
            return {"error": "base_url is required for Plane backend", "code": "MISSING_BASE_URL"}
        if not workspace_slug or not workspace_slug.strip():
            return {
                "error": "workspace_slug is required for Plane backend",
                "code": "MISSING_WORKSPACE_SLUG",
            }

        base_url = base_url.strip().rstrip("/")
        workspace_slug = workspace_slug.strip()

        try:
            from ..backends.plane_backend import PlaneBackend

            backend = PlaneBackend(
                base_url=base_url,
                api_key=api_key,
                workspace_slug=workspace_slug,
            )
            user = await backend.validate_auth()
            await backend.close()
        except Exception as e:
            logger.error("plane_auth_error", error=str(e))
            return {"error": f"Plane auth failed: {str(e)}", "code": "INVALID_CREDENTIALS"}

        await store_plane_credentials(ctx, api_key, base_url, workspace_slug)
        logger.info("auth_token_set", backend="plane", user=user.username)

        return {
            "success": True,
            "backend": "plane",
            "message": f"Authenticated as {user.display_name} on Plane",
            "user": {
                "id": user.id,
                "username": user.username,
                "fullName": user.display_name,
            },
        }

    else:
        # Trello authentication (default)
        if not token:
            return {"error": "token is required for Trello backend", "code": "MISSING_TOKEN"}

        try:
            from ..backends.trello_backend import TrelloBackend

            backend = TrelloBackend(api_key=api_key, token=token)
            user = await backend.validate_auth()
            await backend.close()
        except Exception as e:
            logger.error("trello_auth_error", error=str(e))
            return {"error": f"Trello auth failed: {str(e)}", "code": "INVALID_CREDENTIALS"}

        await store_session_credentials(ctx, api_key, token)
        logger.info("auth_token_set", backend="trello", user=user.username)

        return {
            "success": True,
            "backend": "trello",
            "message": f"Authenticated as {user.display_name}",
            "user": {
                "id": user.id,
                "username": user.username,
                "fullName": user.display_name,
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# BOARD & SETUP (3 tools)
# ═══════════════════════════════════════════════════════════════════════


async def setup_board(board_name: str, ctx: Context) -> dict[str, Any]:
    """Create a new board/project with the SpecBox Engine structure.

    Creates the board with 5 workflow states (User Stories, Backlog,
    In Progress, Review, Done), base labels (US, UC, Infra, Bloqueado),
    and any backend-specific configuration (custom fields for Trello).

    Args:
        board_name: Name for the new board/project (e.g., "TALENT-ON")

    Returns:
        Board configuration with IDs for states, custom fields, and labels.
    """
    backend = await get_session_backend(ctx)
    try:
        config = await backend.setup_board(board_name)
        return {
            "board_id": config.board_id,
            "board_url": config.board_url,
            "lists": config.states,
            "custom_fields": config.custom_fields,
            "labels": config.labels,
        }
    finally:
        await backend.close()


async def get_board_status(board_id: str, ctx: Context) -> dict[str, Any]:
    """Get comprehensive status of a SpecBox Engine board/project.

    Reads all items, counts US vs UC per state, and calculates
    progress metrics (hours done/total, UCs done/total).

    Args:
        board_id: Board/project ID

    Returns:
        Board status with state counts, progress percentages, and US summary.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)
        states = await backend.get_states(board_id)

        # Build per-state counts
        list_stats: list[dict[str, Any]] = []
        state_name_map = {v: k for k, v in WORKFLOW_LIST_NAMES.items()}
        for state_key, display_name in WORKFLOW_LIST_NAMES.items():
            state_items = [i for i in items if i.state == state_key]
            us_count = sum(1 for i in state_items if _is_us(i))
            uc_count = sum(1 for i in state_items if _is_uc(i))
            list_stats.append({"name": display_name, "us_count": us_count, "uc_count": uc_count})

        # Progress metrics
        total_hours = 0.0
        done_hours = 0.0
        total_ucs = 0
        done_ucs = 0

        for item in items:
            if _is_uc(item):
                total_ucs += 1
                h = _extract_meta_float(item, "horas")
                total_hours += h
                if item.state == "done":
                    done_ucs += 1
                    done_hours += h

        pct = (done_hours / total_hours * 100) if total_hours > 0 else 0

        # US summary
        us_summary: list[dict[str, Any]] = []
        for item in items:
            if not _is_us(item):
                continue
            us_id = _get_us_id(item)
            uc_children = _get_uc_children(items, us_id)
            uc_done = sum(1 for c in uc_children if c.state == "done")
            us_summary.append({
                "us_id": us_id,
                "name": item.name,
                "status": item.state,
                "uc_progress": f"{uc_done}/{len(uc_children)}",
            })

        blocked_count = sum(1 for us in us_summary if us.get("status") == "blocked")
        summary_text = (
            f"{total_ucs} UCs ({done_ucs} done) | "
            f"{round(pct, 1)}% horas completadas | "
            f"{len(us_summary)} US"
        )
        if blocked_count:
            summary_text += f" | {blocked_count} bloqueados"

        return {
            "lists": list_stats,
            "progress": {
                "horas_done": done_hours,
                "horas_total": total_hours,
                "pct": round(pct, 1),
            },
            "us_summary": us_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary_text,
        }
    finally:
        await backend.close()


async def import_spec(board_id: str, spec: dict, ctx: Context) -> dict[str, Any]:
    """Import a full project specification into the board/project (idempotent).

    Uses find-or-create pattern: if items already exist they are updated,
    otherwise they are created. Safe to call multiple times with the same spec.

    Args:
        board_id: Board/project ID
        spec: JSON spec with structure: {user_stories: [{us_id, name, hours, screens,
              description, use_cases: [{uc_id, name, actor, hours, screens,
              acceptance_criteria: [str], context}]}]}

    Returns:
        Import results with counts of created/updated items and any errors.
    """
    backend = await get_session_backend(ctx)
    try:
        parsed = ImportSpec(**spec)

        created_us = 0
        updated_us = 0
        created_uc = 0
        updated_uc = 0
        created_ac = 0
        errors: list[str] = []

        for us_spec in parsed.user_stories:
            try:
                # Build US description
                us_desc = (
                    f"# {us_spec.us_id}: {us_spec.name}\n\n"
                    f"**Horas estimadas:** {us_spec.hours}\n"
                    f"**Pantallas:** {us_spec.screens}\n\n"
                    f"{us_spec.description}"
                )

                us_meta = {
                    "tipo": "US",
                    "us_id": us_spec.us_id,
                    "horas": us_spec.hours,
                    "pantallas": us_spec.screens,
                }

                # Find-or-create US item
                existing_us = await backend.find_item_by_field(
                    board_id, "us_id", us_spec.us_id
                )
                module: ModuleDTO | None = None
                if existing_us:
                    us_item = await backend.update_item(
                        board_id,
                        existing_us.id,
                        name=f"{us_spec.us_id}: {us_spec.name}",
                        description=us_desc,
                        state="user_stories",
                        meta=us_meta,
                    )
                    updated_us += 1
                else:
                    us_item = await backend.create_item(
                        board_id,
                        name=f"{us_spec.us_id}: {us_spec.name}",
                        description=us_desc,
                        state="user_stories",
                        labels=["US"],
                        meta=us_meta,
                    )
                    # Create module only for new US items (pass only us_id)
                    module = await backend.create_module(board_id, us_spec.us_id)
                    created_us += 1

                new_uc_item_ids: list[str] = []

                for uc_spec in us_spec.use_cases:
                    try:
                        # Build UC description
                        ac_lines = "\n".join(
                            f"- AC-{idx:02d}: {ac}"
                            for idx, ac in enumerate(uc_spec.acceptance_criteria, 1)
                        )
                        uc_desc = (
                            f"# {uc_spec.uc_id}: {uc_spec.name}\n\n"
                            f"**User Story:** {us_spec.us_id}: {us_spec.name}\n"
                            f"**Actor:** {uc_spec.actor}\n"
                            f"**Horas estimadas:** {uc_spec.hours}\n"
                            f"**Pantallas:** {uc_spec.screens}\n\n"
                            f"## Criterios de Aceptacion\n{ac_lines}\n\n"
                            f"## Contexto\n{uc_spec.context}"
                        )

                        # Build labels for UC
                        uc_labels = ["UC"]
                        if uc_spec.actor:
                            uc_labels.append(f"Actor:{uc_spec.actor}")

                        uc_meta = {
                            "tipo": "UC",
                            "uc_id": uc_spec.uc_id,
                            "us_id": us_spec.us_id,
                            "horas": uc_spec.hours,
                            "pantallas": uc_spec.screens,
                            "actor": uc_spec.actor,
                        }

                        # Find-or-create UC item
                        existing_uc = await backend.find_item_by_field(
                            board_id, "uc_id", uc_spec.uc_id
                        )
                        if existing_uc:
                            uc_item = await backend.update_item(
                                board_id,
                                existing_uc.id,
                                name=f"{uc_spec.uc_id}: {uc_spec.name}",
                                description=uc_desc,
                                labels=uc_labels,
                                parent_id=us_item.id,
                                meta=uc_meta,
                            )
                            updated_uc += 1
                        else:
                            uc_item = await backend.create_item(
                                board_id,
                                name=f"{uc_spec.uc_id}: {uc_spec.name}",
                                description=uc_desc,
                                state="backlog",
                                labels=uc_labels,
                                parent_id=us_item.id,
                                meta=uc_meta,
                            )
                            created_uc += 1

                        # Acceptance criteria: create only missing ones
                        criteria = [
                            (f"AC-{idx:02d}", ac_text)
                            for idx, ac_text in enumerate(uc_spec.acceptance_criteria, 1)
                        ]
                        if criteria:
                            if existing_uc:
                                existing_acs = await backend.get_acceptance_criteria(
                                    board_id, uc_item.id
                                )
                                existing_ac_ids = {ac.id for ac in existing_acs}
                                new_criteria = [
                                    (ac_id, text)
                                    for ac_id, text in criteria
                                    if ac_id not in existing_ac_ids
                                ]
                                if new_criteria:
                                    await backend.create_acceptance_criteria(
                                        board_id, uc_item.id, new_criteria
                                    )
                                    created_ac += len(new_criteria)
                            else:
                                await backend.create_acceptance_criteria(
                                    board_id, uc_item.id, criteria
                                )
                                created_ac += len(criteria)

                        # Only track new UCs for module linking
                        if not existing_uc:
                            new_uc_item_ids.append(uc_item.id)

                    except Exception as e:
                        errors.append(f"UC {uc_spec.uc_id}: {str(e)}")
                        logger.error("import_uc_error", uc_id=uc_spec.uc_id, error=str(e))

                # Add only new UC items to module
                if new_uc_item_ids:
                    if module:
                        # Module was just created for new US
                        await backend.add_items_to_module(
                            board_id, module.id, new_uc_item_ids
                        )
                    elif existing_us:
                        # US existed — create module (finds existing US card/item)
                        # In Trello this creates a new checklist; in Plane a new module
                        try:
                            existing_module = await backend.create_module(
                                board_id, us_spec.us_id
                            )
                            await backend.add_items_to_module(
                                board_id, existing_module.id, new_uc_item_ids
                            )
                        except Exception:
                            logger.warning(
                                "import_module_link_skip",
                                us_id=us_spec.us_id,
                                msg="Could not link new UCs to module",
                            )

            except Exception as e:
                errors.append(f"US {us_spec.us_id}: {str(e)}")
                logger.error("import_us_error", us_id=us_spec.us_id, error=str(e))

        return {
            "created": {"us": created_us, "uc": created_uc, "ac": created_ac},
            "updated": {"us": updated_us, "uc": updated_uc},
            "errors": errors,
        }
    finally:
        await backend.close()


# ═══════════════════════════════════════════════════════════════════════
# USER STORIES (4 tools)
# ═══════════════════════════════════════════════════════════════════════


async def list_us(
    board_id: str, ctx: Context, status: str | None = None
) -> list[dict[str, Any]]:
    """List all User Stories on the board/project.

    Filters items with label US. Optionally filter by workflow
    status (user_stories, backlog, in_progress, review, done).

    Args:
        board_id: Board/project ID
        status: Optional workflow state filter

    Returns:
        List of US summaries with progress metrics.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        result: list[dict[str, Any]] = []
        for item in items:
            if not _is_us(item):
                continue
            if status and item.state != status:
                continue

            us_id = _get_us_id(item)
            hours = _extract_meta_float(item, "horas")
            screens = _extract_meta_str(item, "pantallas")

            uc_children = _get_uc_children(items, us_id)
            uc_done = sum(1 for c in uc_children if c.state == "done")

            # Get AC counts for each UC
            ac_total = 0
            ac_done = 0
            for uc_item in uc_children:
                t, d = await _get_ac_counts(backend, board_id, uc_item)
                ac_total += t
                ac_done += d

            result.append({
                "us_id": us_id,
                "name": item.name,
                "hours": hours,
                "status": item.state,
                "screens": screens,
                "uc_total": len(uc_children),
                "uc_done": uc_done,
                "ac_total": ac_total,
                "ac_done": ac_done,
            })

        return result
    finally:
        await backend.close()


async def get_us(board_id: str, us_id: str, ctx: Context) -> dict[str, Any]:
    """Get detailed information about a User Story and its Use Cases.

    Reads the US item and all child UC items.

    Args:
        board_id: Board/project ID
        us_id: User Story ID (e.g., "US-01")

    Returns:
        Full US detail with child UCs, attachments, and progress.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        us_item = _find_us_item(items, us_id)
        if not us_item:
            return {"error": f"User Story {us_id} not found", "code": "US_NOT_FOUND"}

        # Get attachments
        attachments = await backend.get_attachments(board_id, us_item.id)
        attach_list = [
            {"name": a.name, "url": a.url, "date": a.created_at}
            for a in attachments
        ]

        # Get child UCs
        uc_children = _get_uc_children(items, us_id)
        use_cases: list[dict[str, Any]] = []
        for uc_item in uc_children:
            uc_id = _get_uc_id(uc_item)
            uc_hours = _extract_meta_float(uc_item, "horas")
            actor = _extract_meta_str(uc_item, "actor")

            ac_total, ac_done = await _get_ac_counts(backend, board_id, uc_item)

            use_cases.append({
                "uc_id": uc_id,
                "name": uc_item.name,
                "actor": actor,
                "hours": uc_hours,
                "status": uc_item.state,
                "ac_total": ac_total,
                "ac_done": ac_done,
            })

        return {
            "us_id": us_id,
            "name": us_item.name,
            "hours": _extract_meta_float(us_item, "horas"),
            "status": us_item.state,
            "screens": _extract_meta_str(us_item, "pantallas"),
            "description": us_item.description,
            "use_cases": use_cases,
            "attachments": attach_list,
        }
    finally:
        await backend.close()


async def move_us(
    board_id: str, us_id: str, target: str, ctx: Context
) -> dict[str, Any]:
    """Move a User Story and its Use Cases through the workflow.

    Movement rules:
    - user_stories: moves US + ALL UCs to User Stories
    - backlog: moves US to Backlog + UCs in User Stories to Backlog
    - in_progress: moves US to In Progress + UCs in User Stories/Backlog to Backlog
    - review: ONLY if all UCs are in Review or Done
    - done: ONLY if ALL UCs are in Done

    Args:
        board_id: Board/project ID
        us_id: User Story ID (e.g., "US-01")
        target: Target workflow state

    Returns:
        Movement result with count of UCs moved and any errors.
    """
    if target not in WORKFLOW_LIST_NAMES:
        return {
            "error": f"Invalid target: {target}. Must be one of: {list(WORKFLOW_LIST_NAMES.keys())}",
            "code": "INVALID_TARGET",
        }

    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        us_item = _find_us_item(items, us_id)
        if not us_item:
            return {"error": f"User Story {us_id} not found", "code": "US_NOT_FOUND"}

        uc_children = _get_uc_children(items, us_id)
        ucs_moved = 0
        errors: list[str] = []

        # Validate state transitions
        if target == "review":
            review_done_states = {"review", "done"}
            for uc in uc_children:
                if uc.state not in review_done_states:
                    uc_id = _get_uc_id(uc)
                    return {
                        "error": f"Cannot move to review: UC {uc_id} is in '{uc.state}'",
                        "code": "UC_NOT_READY_FOR_REVIEW",
                    }

        elif target == "done":
            for uc in uc_children:
                if uc.state != "done":
                    uc_id = _get_uc_id(uc)
                    return {
                        "error": f"Cannot move to done: UC {uc_id} is in '{uc.state}'",
                        "code": "UC_NOT_DONE",
                    }

        # Move US
        await backend.update_item(board_id, us_item.id, state=target)

        # Move children based on rules
        if target == "user_stories":
            for uc in uc_children:
                await backend.update_item(board_id, uc.id, state=target)
                ucs_moved += 1

        elif target == "backlog":
            for uc in uc_children:
                if uc.state == "user_stories":
                    await backend.update_item(board_id, uc.id, state="backlog")
                    ucs_moved += 1

        elif target == "in_progress":
            for uc in uc_children:
                if uc.state in ("user_stories", "backlog"):
                    await backend.update_item(board_id, uc.id, state="backlog")
                    ucs_moved += 1

        return {
            "us_id": us_id,
            "new_status": target,
            "ucs_moved": ucs_moved,
            "errors": errors,
        }
    finally:
        await backend.close()


async def get_us_progress(
    board_id: str, us_id: str, ctx: Context
) -> dict[str, Any]:
    """Get detailed progress for a User Story.

    Reads all child UCs and their acceptance criteria to calculate
    comprehensive progress metrics.

    Args:
        board_id: Board/project ID
        us_id: User Story ID (e.g., "US-01")

    Returns:
        Progress detail with UC-level and AC-level completion stats.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        us_item = _find_us_item(items, us_id)
        if not us_item:
            return {"error": f"User Story {us_id} not found", "code": "US_NOT_FOUND"}

        uc_children = _get_uc_children(items, us_id)

        ucs_data: list[dict[str, Any]] = []
        total_acs = 0
        passed_acs = 0
        hours_total = 0.0
        hours_done = 0.0

        for uc_item in uc_children:
            uc_id = _get_uc_id(uc_item)
            uc_hours = _extract_meta_float(uc_item, "horas")
            is_done = uc_item.state == "done"

            acs_total_uc, acs_passed_uc = await _get_ac_counts(
                backend, board_id, uc_item
            )

            total_acs += acs_total_uc
            passed_acs += acs_passed_uc
            hours_total += uc_hours
            if is_done:
                hours_done += uc_hours

            ucs_data.append({
                "uc_id": uc_id,
                "name": uc_item.name,
                "status": uc_item.state,
                "acs_total": acs_total_uc,
                "acs_passed": acs_passed_uc,
            })

        done_ucs = sum(1 for u in ucs_data if u["status"] == "done")

        return {
            "us_id": us_id,
            "name": us_item.name,
            "total_ucs": len(ucs_data),
            "done_ucs": done_ucs,
            "total_acs": total_acs,
            "passed_acs": passed_acs,
            "hours_total": hours_total,
            "hours_done": hours_done,
            "ucs": ucs_data,
        }
    finally:
        await backend.close()


# ═══════════════════════════════════════════════════════════════════════
# USE CASES (5 tools)
# ═══════════════════════════════════════════════════════════════════════


async def list_uc(
    board_id: str,
    ctx: Context,
    us_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List Use Cases on the board/project, optionally filtered by parent US or status.

    Args:
        board_id: Board/project ID
        us_id: Optional parent US ID filter (e.g., "US-01")
        status: Optional workflow state filter (user_stories, backlog, in_progress, review, done)

    Returns:
        List of UC summaries with AC progress.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        result: list[dict[str, Any]] = []
        for item in items:
            if not _is_uc(item):
                continue
            item_us_id = _extract_meta_str(item, "us_id")
            # Also check parent_id for Plane-style hierarchy
            if not item_us_id and item.parent_id:
                parent = next((i for i in items if i.id == item.parent_id), None)
                if parent:
                    item_us_id = _get_us_id(parent)
            if us_id and item_us_id != us_id:
                continue
            if status and item.state != status:
                continue

            uc_id = _get_uc_id(item)
            hours = _extract_meta_float(item, "horas")
            screens = _extract_meta_str(item, "pantallas")
            actor = _extract_meta_str(item, "actor")

            ac_total, ac_done = await _get_ac_counts(backend, board_id, item)

            result.append({
                "uc_id": uc_id,
                "us_id": item_us_id,
                "name": item.name,
                "actor": actor,
                "hours": hours,
                "status": item.state,
                "screens": screens,
                "ac_total": ac_total,
                "ac_done": ac_done,
            })

        return result
    finally:
        await backend.close()


async def get_uc(board_id: str, uc_id: str, ctx: Context) -> dict[str, Any]:
    """Get full details of a Use Case, optimized for LLM consumption.

    Reads the UC item, its acceptance criteria, and attachments,
    returning a complete JSON representation.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")

    Returns:
        Complete UC detail with acceptance criteria, context, and attachments.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        uc_item = _find_uc_item(items, uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        # Get parent US info
        item_us_id = _extract_meta_str(uc_item, "us_id")
        if not item_us_id and uc_item.parent_id:
            parent = next((i for i in items if i.id == uc_item.parent_id), None)
            if parent:
                item_us_id = _get_us_id(parent)

        us_name = ""
        if item_us_id:
            us_item = _find_us_item(items, item_us_id)
            if us_item:
                us_name = _clean_name(us_item.name, item_us_id)

        # Get ACs
        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
        ac_list = [{"id": ac.id, "text": ac.text, "done": ac.done} for ac in acs]

        # Get attachments
        attachments = await backend.get_attachments(board_id, uc_item.id)
        attach_list = [
            {"name": a.name, "url": a.url, "date": a.created_at}
            for a in attachments
        ]

        # Extract metadata
        hours = _extract_meta_float(uc_item, "horas")
        screens_raw = _extract_meta_str(uc_item, "pantallas")
        actor = _extract_meta_str(uc_item, "actor")
        context = _extract_meta_str(uc_item, "context")

        screens = (
            [s.strip() for s in screens_raw.split(",") if s.strip()]
            if screens_raw
            else []
        )

        result: dict[str, Any] = {
            "uc_id": uc_id,
            "name": _clean_name(uc_item.name, uc_id),
            "us_id": item_us_id,
            "us_name": us_name,
            "actor": actor,
            "hours": hours,
            "screens": screens,
            "status": uc_item.state,
            "acceptance_criteria": ac_list,
            "context": context,
            "description_raw": uc_item.description,
            "attachments": attach_list,
            # Backend-agnostic identifiers
            "backend_item_id": uc_item.id,
            "backend_item_url": uc_item.url,
            "card_id": uc_item.id,
            "card_url": uc_item.url,
        }

        return result
    finally:
        await backend.close()


async def move_uc(
    board_id: str, uc_id: str, target: str, ctx: Context
) -> dict[str, Any]:
    """Move a Use Case to a workflow state.

    When moving to 'done', automatically updates the parent US module/checklist.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")
        target: Target state (user_stories, backlog, in_progress, review, done)

    Returns:
        Movement result with parent US update status.
    """
    if target not in WORKFLOW_LIST_NAMES:
        return {"error": f"Invalid target: {target}", "code": "INVALID_TARGET"}

    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        uc_item = _find_uc_item(items, uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        # Capture original state for summary (AC-16)
        original_state = uc_item.state or "unknown"

        # Move UC
        await backend.update_item(board_id, uc_item.id, state=target)

        us_checklist_updated = False
        us_all_done = False
        item_us_id = _extract_meta_str(uc_item, "us_id")
        if not item_us_id and uc_item.parent_id:
            parent = next((i for i in items if i.id == uc_item.parent_id), None)
            if parent:
                item_us_id = _get_us_id(parent)

        if target == "done" and item_us_id:
            us_checklist_updated, us_all_done = await _handle_uc_completion(
                backend, board_id, items, item_us_id, uc_id
            )

        return {
            "uc_id": uc_id,
            "new_status": target,
            "us_checklist_updated": us_checklist_updated,
            "us_all_done": us_all_done,
            "summary": f"{uc_id} movido de {original_state} a {target}",
        }
    finally:
        await backend.close()


async def start_uc(board_id: str, uc_id: str, ctx: Context) -> dict[str, Any]:
    """Start working on a Use Case.

    Shortcut that moves the UC to In Progress, adds a timestamp comment,
    and returns the full UC detail for the LLM to work with.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")

    Returns:
        Full UC detail (same as get_uc) for immediate use.
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await backend.find_item_by_field(board_id, "uc_id", uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        # Move to in_progress
        await backend.update_item(board_id, uc_item.id, state="in_progress")

        # Add timestamp comment
        now = datetime.now(timezone.utc).isoformat()
        await backend.add_comment(board_id, uc_item.id, f"Desarrollo iniciado: {now}")

        # Write active UC marker for spec-guard.mjs enforcement
        feature = _extract_meta_str(uc_item, "feature", uc_id)
        _write_active_uc_marker(uc_id, board_id, feature)
    finally:
        await backend.close()

    # Return full UC detail (creates a new backend session)
    return await get_uc(board_id, uc_id, ctx)


async def complete_uc(
    board_id: str, uc_id: str, ctx: Context, evidence: str | None = None
) -> dict[str, Any]:
    """Mark a Use Case as complete.

    Moves to Done, updates the parent US module/checklist,
    and optionally adds evidence as a comment.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")
        evidence: Optional evidence text to add as comment

    Returns:
        Completion result with US update status.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        uc_item = _find_uc_item(items, uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        # Move to done
        await backend.update_item(board_id, uc_item.id, state="done")

        # Add evidence comment
        if evidence:
            await backend.add_comment(board_id, uc_item.id, evidence)

        # Handle parent US updates
        item_us_id = _extract_meta_str(uc_item, "us_id")
        if not item_us_id and uc_item.parent_id:
            parent = next((i for i in items if i.id == uc_item.parent_id), None)
            if parent:
                item_us_id = _get_us_id(parent)

        us_checklist_updated = False
        us_all_done = False

        if item_us_id:
            us_checklist_updated, us_all_done = await _handle_uc_completion(
                backend, board_id, items, item_us_id, uc_id
            )

        # Clear active UC marker — next UC must call start_uc again
        _clear_active_uc_marker()

        now = datetime.now(timezone.utc).isoformat()
        return {
            "uc_id": uc_id,
            "completed_at": now,
            "us_checklist_updated": us_checklist_updated,
            "us_all_done": us_all_done,
            "us_id": item_us_id,
        }
    finally:
        await backend.close()


# ═══════════════════════════════════════════════════════════════════════
# ACCEPTANCE CRITERIA (3 tools)
# ═══════════════════════════════════════════════════════════════════════


async def mark_ac(
    board_id: str,
    uc_id: str,
    ac_id: str,
    passed: bool,
    ctx: Context,
    evidence: str | None = None,
) -> dict[str, Any]:
    """Mark a single Acceptance Criterion as passed or failed.

    Updates the AC status and adds a comment.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")
        ac_id: Acceptance Criterion ID (e.g., "AC-01")
        passed: True if the criterion passed, False if failed
        evidence: Optional evidence text

    Returns:
        AC status update result with totals.
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await backend.find_item_by_field(board_id, "uc_id", uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        # Mark the AC
        try:
            await backend.mark_acceptance_criterion(
                board_id, uc_item.id, ac_id, passed
            )
        except Exception as e:
            return {
                "error": f"AC {ac_id} not found in {uc_id}: {str(e)}",
                "code": "AC_NOT_FOUND",
            }

        # Add comment
        status_text = "PASSED" if passed else "FAILED"
        comment = f"{ac_id}: {status_text}"
        if evidence:
            comment += f" — {evidence}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        comment += f" [{now}]"
        await backend.add_comment(board_id, uc_item.id, comment)

        # Get updated AC counts
        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)

        status_label = "PASSED" if passed else "FAILED"
        return {
            "uc_id": uc_id,
            "ac_id": ac_id,
            "passed": passed,
            "ac_total": len(acs),
            "ac_done": sum(1 for ac in acs if ac.done),
            "summary": f"{ac_id} marcado como {status_label} en {uc_id}",
        }
    finally:
        await backend.close()


async def mark_ac_batch(
    board_id: str, uc_id: str, results: list[dict], ctx: Context
) -> dict[str, Any]:
    """Mark multiple Acceptance Criteria at once.

    Processes all AC results in a single operation and adds a consolidated comment.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")
        results: List of {ac_id: str, passed: bool, evidence: str | None}

    Returns:
        Batch result with total/passed/failed counts.
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await backend.find_item_by_field(board_id, "uc_id", uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        details: list[dict[str, Any]] = []
        passed_count = 0
        failed_count = 0

        for r in results:
            ac_id = r.get("ac_id", "")
            passed = r.get("passed", False)

            try:
                await backend.mark_acceptance_criterion(
                    board_id, uc_item.id, ac_id, passed
                )
            except Exception:
                logger.warning(
                    "mark_ac_batch_skip", uc_id=uc_id, ac_id=ac_id, error="not_found"
                )

            if passed:
                passed_count += 1
            else:
                failed_count += 1

            details.append({"ac_id": ac_id, "passed": passed})

        # Add consolidated comment
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        comment_lines = [f"Validacion AG-09b [{now}]:"]
        for d in details:
            status_text = "PASSED" if d["passed"] else "FAILED"
            comment_lines.append(f"  {d['ac_id']}: {status_text}")
        await backend.add_comment(board_id, uc_item.id, "\n".join(comment_lines))

        if failed_count == 0 and passed_count > 0:
            await backend.add_comment(
                board_id,
                uc_item.id,
                "Todos los criterios de aceptacion validados",
            )

        return {
            "uc_id": uc_id,
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "details": details,
            "summary": f"Marcados {passed_count}/{len(results)} criterios como done en {uc_id}",
        }
    finally:
        await backend.close()


async def get_ac_status(
    board_id: str, uc_id: str, ctx: Context
) -> dict[str, Any]:
    """Get the status of all Acceptance Criteria for a Use Case.

    Args:
        board_id: Board/project ID
        uc_id: Use Case ID (e.g., "UC-001")

    Returns:
        AC status with total, done, pending counts and individual criteria.
    """
    backend = await get_session_backend(ctx)
    try:
        uc_item = await backend.find_item_by_field(board_id, "uc_id", uc_id)
        if not uc_item:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
        done_count = sum(1 for ac in acs if ac.done)

        return {
            "uc_id": uc_id,
            "total": len(acs),
            "done": done_count,
            "pending": len(acs) - done_count,
            "criteria": [
                {"id": ac.id, "text": ac.text, "done": ac.done} for ac in acs
            ],
        }
    finally:
        await backend.close()


# ═══════════════════════════════════════════════════════════════════════
# EVIDENCE (2 tools)
# ═══════════════════════════════════════════════════════════════════════


async def attach_evidence(
    board_id: str,
    target_id: str,
    target_type: str,
    evidence_type: str,
    markdown_content: str,
    ctx: Context,
    summary: str | None = None,
) -> dict[str, Any]:
    """Convert markdown to PDF and attach it to a US or UC item.

    Generates a PDF from the markdown content, uploads it as an attachment,
    and adds a summary comment.

    Args:
        board_id: Board/project ID
        target_id: US or UC ID (e.g., "US-01" or "UC-001")
        target_type: "us" or "uc"
        evidence_type: Type of evidence: "prd", "plan", "ag09", "delivery", "feedback"
        markdown_content: Markdown text to convert to PDF
        summary: Optional summary for the comment

    Returns:
        Attachment result with URL and comment status.
    """
    if target_type not in ("us", "uc"):
        return {
            "error": "target_type must be 'us' or 'uc'",
            "code": "INVALID_TARGET_TYPE",
        }
    if evidence_type not in ("prd", "plan", "ag09", "delivery", "feedback"):
        return {"error": "Invalid evidence_type", "code": "INVALID_EVIDENCE_TYPE"}

    backend = await get_session_backend(ctx)
    try:
        field_name = "us_id" if target_type == "us" else "uc_id"
        item = await backend.find_item_by_field(board_id, field_name, target_id)
        if not item:
            return {
                "error": f"{target_type.upper()} {target_id} not found",
                "code": "TARGET_NOT_FOUND",
            }

        filename = f"{target_id}_{evidence_type}.pdf"
        title = f"{target_id} - {evidence_type.upper()}"
        pdf_bytes = markdown_to_pdf(markdown_content, title=title)

        attachment = await backend.add_attachment(
            board_id, item.id, filename, pdf_bytes
        )

        if not summary:
            summary = f"Evidencia {evidence_type.upper()} generada ({len(markdown_content)} chars)"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        await backend.add_comment(
            board_id,
            item.id,
            f"{evidence_type.upper()} generado [{now}] — {summary}",
        )

        return {
            "target_id": target_id,
            "evidence_type": evidence_type,
            "attachment_id": attachment.id,
            "attachment_url": attachment.url,
            "comment_added": True,
        }
    finally:
        await backend.close()


async def get_evidence(
    board_id: str,
    target_id: str,
    target_type: str,
    ctx: Context,
    evidence_type: str | None = None,
) -> dict[str, Any]:
    """Get evidence attachments and activity for a US or UC item.

    Args:
        board_id: Board/project ID
        target_id: US or UC ID (e.g., "US-01" or "UC-001")
        target_type: "us" or "uc"
        evidence_type: Optional filter by evidence type name

    Returns:
        Attachments and activity comments for the target item.
    """
    if target_type not in ("us", "uc"):
        return {
            "error": "target_type must be 'us' or 'uc'",
            "code": "INVALID_TARGET_TYPE",
        }

    backend = await get_session_backend(ctx)
    try:
        field_name = "us_id" if target_type == "us" else "uc_id"
        item = await backend.find_item_by_field(board_id, field_name, target_id)
        if not item:
            return {
                "error": f"{target_type.upper()} {target_id} not found",
                "code": "TARGET_NOT_FOUND",
            }

        # Get attachments
        attachments = await backend.get_attachments(board_id, item.id)
        attach_list: list[dict[str, Any]] = []
        for a in attachments:
            if evidence_type and evidence_type not in a.name.lower():
                continue
            attach_list.append({
                "name": a.name,
                "url": a.url,
                "date": a.created_at,
                "size": a.size,
            })

        # Get comments as activity
        comments = await backend.get_comments(board_id, item.id)
        activity = [{"text": c.text, "date": c.created_at} for c in comments]

        return {
            "target_id": target_id,
            "attachments": attach_list,
            "activity": activity,
        }
    finally:
        await backend.close()


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD (3 tools)
# ═══════════════════════════════════════════════════════════════════════


async def get_sprint_status(board_id: str, ctx: Context) -> dict[str, Any]:
    """Get executive summary of the entire board/project.

    Provides counts by status, hours progress, AC pass rates, and blocked items.

    Args:
        board_id: Board/project ID

    Returns:
        Sprint status dashboard with comprehensive metrics.
    """
    backend = await get_session_backend(ctx)
    try:
        board_name = await backend.get_board_name(board_id)
        items = await backend.list_items(board_id)

        total_us = 0
        total_uc = 0
        total_ac = 0
        by_status: dict[str, dict[str, int]] = {}
        hours_total = 0.0
        hours_done = 0.0
        hours_in_progress = 0.0
        acs_passed = 0
        blocked: list[dict[str, Any]] = []

        for state in WORKFLOW_LIST_NAMES:
            by_status[state] = {"us": 0, "uc": 0}

        for item in items:
            is_us = _is_us(item)
            is_uc = _is_uc(item)

            if is_us:
                total_us += 1
                if item.state in by_status:
                    by_status[item.state]["us"] += 1
            elif is_uc:
                total_uc += 1
                if item.state in by_status:
                    by_status[item.state]["uc"] += 1

                h = _extract_meta_float(item, "horas")
                hours_total += h
                if item.state == "done":
                    hours_done += h
                elif item.state == "in_progress":
                    hours_in_progress += h

                ac_t, ac_d = await _get_ac_counts(backend, board_id, item)
                total_ac += ac_t
                acs_passed += ac_d

            # Check for blocked
            if "Bloqueado" in item.labels or "bloqueado" in [
                l.lower() for l in item.labels
            ]:
                item_id_val = ""
                if is_us:
                    item_id_val = _get_us_id(item)
                elif is_uc:
                    item_id_val = _get_uc_id(item)
                blocked.append({
                    "id": item_id_val,
                    "name": item.name,
                    "status": item.state,
                })

        hours_pct = (hours_done / hours_total * 100) if hours_total > 0 else 0
        acs_pct = (acs_passed / total_ac * 100) if total_ac > 0 else 0

        summary_parts = [
            f"{board_name}: {total_us} US, {total_uc} UCs",
            f"Horas: {round(hours_pct, 1)}% ({hours_done:.0f}/{hours_total:.0f}h)",
            f"ACs: {round(acs_pct, 1)}% ({acs_passed}/{total_ac})",
        ]
        if blocked:
            summary_parts.append(f"{len(blocked)} bloqueados")

        return {
            "board_name": board_name,
            "total_us": total_us,
            "total_uc": total_uc,
            "total_ac": total_ac,
            "by_status": by_status,
            "hours": {
                "total": hours_total,
                "done": hours_done,
                "in_progress": hours_in_progress,
                "pct": round(hours_pct, 1),
            },
            "acs": {
                "total": total_ac,
                "passed": acs_passed,
                "pct": round(acs_pct, 1),
            },
            "blocked": blocked,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": " | ".join(summary_parts),
        }
    finally:
        await backend.close()


async def get_delivery_report(board_id: str, ctx: Context) -> dict[str, Any]:
    """Generate a client-oriented delivery report.

    Summarizes progress per User Story with completion percentages.

    Args:
        board_id: Board/project ID

    Returns:
        Delivery report with per-US progress and overall summary.
    """
    backend = await get_session_backend(ctx)
    try:
        board_name = await backend.get_board_name(board_id)
        items = await backend.list_items(board_id)

        us_items = [i for i in items if _is_us(i)]
        total_us = len(us_items)
        completed_us = 0
        user_stories: list[dict[str, Any]] = []

        for us_item in us_items:
            us_id = _get_us_id(us_item)
            us_name = _clean_name(us_item.name, us_id)
            us_hours = _extract_meta_float(us_item, "horas")

            uc_children = _get_uc_children(items, us_id)
            uc_done = sum(1 for c in uc_children if c.state == "done")
            uc_total = len(uc_children)

            ac_total = 0
            ac_passed = 0
            for uc_item in uc_children:
                t, d = await _get_ac_counts(backend, board_id, uc_item)
                ac_total += t
                ac_passed += d

            if us_item.state == "done":
                completed_us += 1

            user_stories.append({
                "us_id": us_id,
                "name": us_name,
                "status": us_item.state,
                "hours": us_hours,
                "ucs_completed": f"{uc_done}/{uc_total}",
                "acs_passed": f"{ac_passed}/{ac_total}",
            })

        pct = (completed_us / total_us * 100) if total_us > 0 else 0

        summary_text = (
            f"{board_name}: {completed_us}/{total_us} US completadas ({round(pct, 1)}%)"
        )

        return {
            "project": board_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_us": total_us,
                "completed_us": completed_us,
                "pct": round(pct, 1),
            },
            "summary_text": summary_text,
            "user_stories": user_stories,
        }
    finally:
        await backend.close()


async def find_next_uc(board_id: str, ctx: Context) -> dict[str, Any] | None:
    """Find the next Use Case to work on.

    Priority:
    1. UCs in Backlog whose US has UCs in In Progress (maintain focus)
    2. UCs in Backlog from the US with most UCs in Backlog (start a block)
    3. First UC in Backlog by position

    Args:
        board_id: Board/project ID

    Returns:
        Full UC detail (same as get_uc) or None if nothing in Backlog.
    """
    backend = await get_session_backend(ctx)
    try:
        items = await backend.list_items(board_id)

        # Find all UCs in Backlog
        ready_ucs = [i for i in items if _is_uc(i) and i.state == "backlog"]
        if not ready_ucs:
            return None

        # Find USs that have UCs in progress
        us_with_ip: set[str] = set()
        for item in items:
            if _is_uc(item) and item.state == "in_progress":
                uid = _extract_meta_str(item, "us_id")
                if not uid and item.parent_id:
                    parent = next(
                        (i for i in items if i.id == item.parent_id), None
                    )
                    if parent:
                        uid = _get_us_id(parent)
                if uid:
                    us_with_ip.add(uid)

        # Priority 1: UCs from USs with in-progress work
        def _get_item_us_id(item: ItemDTO) -> str:
            uid = _extract_meta_str(item, "us_id")
            if not uid and item.parent_id:
                parent = next(
                    (i for i in items if i.id == item.parent_id), None
                )
                if parent:
                    uid = _get_us_id(parent)
            return uid

        priority1 = [c for c in ready_ucs if _get_item_us_id(c) in us_with_ip]

        if priority1:
            chosen = priority1[0]
        else:
            # Priority 2: US with most UCs in backlog
            us_ready_count: dict[str, int] = {}
            for c in ready_ucs:
                uid = _get_item_us_id(c)
                us_ready_count[uid] = us_ready_count.get(uid, 0) + 1

            if us_ready_count:
                top_us = max(us_ready_count, key=lambda k: us_ready_count[k])
                priority2 = [
                    c for c in ready_ucs if _get_item_us_id(c) == top_us
                ]
                chosen = priority2[0] if priority2 else ready_ucs[0]
            else:
                chosen = ready_ucs[0]

        uc_id = _get_uc_id(chosen)
    finally:
        await backend.close()

    # Return full UC detail (creates a new backend session)
    return await get_uc(board_id, uc_id, ctx)


# ═══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════


async def _handle_uc_completion(
    backend: SpecBackend,
    board_id: str,
    items: list[ItemDTO],
    us_id: str,
    completed_uc_id: str,
) -> tuple[bool, bool]:
    """Handle parent US updates when a UC is completed.

    Checks if all sibling UCs are done and adds a completion comment
    to the parent US if so.

    Returns:
        (checklist_updated, all_done) tuple.
    """
    us_item = _find_us_item(items, us_id)
    if not us_item:
        return False, False

    uc_siblings = _get_uc_children(items, us_id)

    # Check if all UCs are done (including the one just completed)
    all_done = all(
        c.state == "done" or _get_uc_id(c) == completed_uc_id
        for c in uc_siblings
    )

    checklist_updated = True  # Backend handles module/checklist updates internally

    if all_done and uc_siblings:
        total_ucs = len(uc_siblings)
        total_acs = 0
        for uc in uc_siblings:
            ac_t, _ = await _get_ac_counts(backend, board_id, uc)
            total_acs += ac_t

        await backend.add_comment(
            board_id,
            us_item.id,
            f"{us_id} completada: {total_ucs}/{total_ucs} UCs, {total_acs} ACs",
        )

    return checklist_updated, all_done


# ═══════════════════════════════════════════════════════════════════════
# TOOL REGISTRATION
# ═══════════════════════════════════════════════════════════════════════


def register_spec_driven_tools(mcp_instance) -> None:
    """Register all 21 spec-driven tools on the given FastMCP instance."""

    # Auth (1)
    mcp_instance.tool(
        description="Configure backend API credentials (Trello or Plane) for this session. "
        "MUST be called before any other spec-driven tool."
    )(set_auth_token)

    # Board & Setup (3)
    mcp_instance.tool(
        description="Create a new board/project with SpecBox Engine structure: 5 workflow states, "
        "custom fields (Trello), and base labels."
    )(setup_board)
    mcp_instance.tool(
        description="Get board/project status: item counts per state, hours progress, US summary."
    )(get_board_status)
    mcp_instance.tool(
        description="Import a full project spec (US + UC + AC) into the board/project from JSON."
    )(import_spec)

    # User Stories (4)
    mcp_instance.tool(
        description="List all User Stories. Optional filter by status."
    )(list_us)
    mcp_instance.tool(
        description="Get full detail of a User Story including child Use Cases and attachments."
    )(get_us)
    mcp_instance.tool(
        description="Move a User Story through the workflow. Enforces rules."
    )(move_us)
    mcp_instance.tool(
        description="Get detailed progress for a User Story: UC completion, AC pass rates, hours."
    )(get_us_progress)

    # Use Cases (5)
    mcp_instance.tool(
        description="List Use Cases. Optional filter by parent US or status."
    )(list_uc)
    mcp_instance.tool(
        description="Get full UC detail optimized for LLM: acceptance criteria, context, screens."
    )(get_uc)
    mcp_instance.tool(
        description="Move a UC to a workflow state. Auto-updates parent US module/checklist."
    )(move_uc)
    mcp_instance.tool(
        description="Start working on a UC: moves to In Progress, adds timestamp, returns full detail."
    )(start_uc)
    mcp_instance.tool(
        description="Complete a UC: moves to Done, updates parent US, adds evidence."
    )(complete_uc)

    # Acceptance Criteria (3)
    mcp_instance.tool(
        description="Mark a single AC as passed/failed with optional evidence."
    )(mark_ac)
    mcp_instance.tool(
        description="Mark multiple ACs at once (batch AG-09b validation)."
    )(mark_ac_batch)
    mcp_instance.tool(
        description="Get status of all Acceptance Criteria for a UC."
    )(get_ac_status)

    # Evidence (2)
    mcp_instance.tool(
        description="Convert markdown to PDF and attach as evidence to a US or UC item."
    )(attach_evidence)
    mcp_instance.tool(
        description="Get evidence attachments and activity for a US or UC."
    )(get_evidence)

    # Dashboard (3)
    mcp_instance.tool(
        description="Executive sprint dashboard: counts by status, hours, AC rates, blocked items."
    )(get_sprint_status)
    mcp_instance.tool(
        description="Client-oriented delivery report: per-US progress with completion percentages."
    )(get_delivery_report)
    mcp_instance.tool(
        description="Find the next UC to work on. Priority: active US focus, then largest ready block."
    )(find_next_uc)
