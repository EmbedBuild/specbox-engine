"""Spec-Driven tools: Trello domain operations for US/UC/AC management.

Consolidated from dev-engine-trello-mcp tool modules:
- auth: set_auth_token
- board: setup_board, get_board_status, import_spec
- user_story: list_us, get_us, move_us, get_us_progress
- use_case: list_uc, get_uc, move_uc, start_uc, complete_uc
- acceptance: mark_ac, mark_ac_batch, get_ac_status
- evidence: attach_evidence, get_evidence
- dashboard: get_sprint_status, get_delivery_report, find_next_uc
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from fastmcp import Context

from ..auth_gateway import get_session_client, store_session_credentials
from ..board_helpers import (
    build_custom_field_map,
    build_uc_description,
    build_us_description,
    find_card_by_custom_field,
    find_option_id,
    get_card_custom_value,
    get_list_id_for_state,
    get_state_for_list,
    is_uc_card,
    is_us_card,
    parse_checklist_acs,
    parse_uc_description,
)
from ..models import (
    ACTOR_OPTIONS,
    CARD_TYPE_OPTIONS,
    CUSTOM_FIELD_NAMES,
    LIST_NAME_TO_STATE,
    WORKFLOW_LIST_NAMES,
    ImportSpec,
    WorkflowState,
)
from ..pdf_generator import markdown_to_pdf
from ..trello_client import TrelloClient

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# AUTH (1 tool)
# ═══════════════════════════════════════════════════════════════════════


async def set_auth_token(api_key: str, token: str, ctx: Context) -> dict[str, Any]:
    """Configure Trello API credentials for this session.

    Each user must call this tool before using any other tool.
    Credentials are isolated per session — other users cannot access yours.

    Args:
        api_key: Trello API key (32 characters, from https://trello.com/app-key)
        token: Trello API token (64 characters, generated from the API key page)

    Returns:
        Authentication status with user info if successful.
    """
    if not api_key or not api_key.strip():
        return {"error": "api_key is required", "code": "MISSING_API_KEY"}
    if not token or not token.strip():
        return {"error": "token is required", "code": "MISSING_TOKEN"}

    api_key = api_key.strip()
    token = token.strip()

    try:
        client = TrelloClient(api_key=api_key, token=token)
        user_info = await client.get_me()
        await client.close()
    except httpx.HTTPStatusError as e:
        logger.warning("auth_validation_failed", status=e.response.status_code)
        return {
            "error": f"Invalid Trello credentials: HTTP {e.response.status_code}",
            "code": "INVALID_CREDENTIALS",
        }
    except Exception as e:
        logger.error("auth_error", error=str(e))
        return {"error": f"Connection error: {str(e)}", "code": "CONNECTION_ERROR"}

    await store_session_credentials(ctx, api_key, token)
    logger.info("auth_token_set", user=user_info.get("username"))

    return {
        "success": True,
        "message": f"Authenticated as {user_info.get('fullName', user_info.get('username'))}",
        "user": {
            "id": user_info.get("id"),
            "username": user_info.get("username"),
            "fullName": user_info.get("fullName"),
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# BOARD & SETUP (3 tools)
# ═══════════════════════════════════════════════════════════════════════


async def setup_board(board_name: str, ctx: Context) -> dict[str, Any]:
    """Create a new Trello board with the Dev Engine structure.

    Creates the board with 5 workflow lists (Backlog, Ready, In Progress,
    Review, Done), 6 custom fields (tipo, us_id, uc_id, horas, pantallas,
    actor), and base labels (US, UC, Infra, Bloqueado).

    Args:
        board_name: Name for the new board (e.g., "TALENT-ON")

    Returns:
        Board configuration with IDs for lists, custom fields, and labels.
    """
    client = await get_session_client(ctx)
    try:
        board = await client.create_board(board_name, default_lists=False)
        board_id = board["id"]
        logger.info("board_created", board_id=board_id, name=board_name)

        lists_result: dict[str, str] = {}
        for state, list_name in WORKFLOW_LIST_NAMES.items():
            lst = await client.create_list(board_id, list_name)
            lists_result[state] = lst["id"]

        cf_result: dict[str, str] = {}
        cf = await client.create_custom_field(board_id, "tipo", "list", options=CARD_TYPE_OPTIONS)
        cf_result["tipo"] = cf["id"]
        for name in ["us_id", "uc_id", "pantallas"]:
            cf = await client.create_custom_field(board_id, name, "text")
            cf_result[name] = cf["id"]
        cf = await client.create_custom_field(board_id, "horas", "number")
        cf_result["horas"] = cf["id"]
        cf = await client.create_custom_field(board_id, "actor", "list", options=ACTOR_OPTIONS)
        cf_result["actor"] = cf["id"]

        labels_result: dict[str, str] = {}
        label_defs = [("US", "blue"), ("UC", "green"), ("Infra", "yellow"), ("Bloqueado", "red")]
        for label_name, color in label_defs:
            label = await client.create_label(board_id, label_name, color)
            labels_result[label_name] = label["id"]

        return {
            "board_id": board_id,
            "board_url": board.get("url", ""),
            "lists": lists_result,
            "custom_fields": cf_result,
            "labels": labels_result,
        }
    finally:
        await client.close()


async def get_board_status(board_id: str, ctx: Context) -> dict[str, Any]:
    """Get comprehensive status of a Dev Engine board.

    Reads all lists and cards, counts US vs UC per list, and calculates
    progress metrics (hours done/total, UCs done/total).

    Args:
        board_id: Trello board ID

    Returns:
        Board status with list counts, progress percentages, and US summary.
    """
    client = await get_session_client(ctx)
    try:
        lists = await client.get_board_lists(board_id)
        cards = await client.get_board_cards(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        list_stats: list[dict] = []
        for lst in lists:
            lid = lst["id"]
            list_cards = [c for c in cards if c.get("idList") == lid]
            us_count = sum(1 for c in list_cards if is_us_card(c, cf_map, custom_fields))
            uc_count = sum(1 for c in list_cards if is_uc_card(c, cf_map, custom_fields))
            list_stats.append({"name": lst["name"], "us_count": us_count, "uc_count": uc_count})

        done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}
        total_hours = 0.0
        done_hours = 0.0
        total_ucs = 0
        done_ucs = 0

        for card in cards:
            if is_uc_card(card, cf_map, custom_fields):
                total_ucs += 1
                h = get_card_custom_value(card, "horas", cf_map, custom_fields) or 0
                total_hours += float(h)
                if card.get("idList") in done_list_ids:
                    done_ucs += 1
                    done_hours += float(h)

        pct = (done_hours / total_hours * 100) if total_hours > 0 else 0

        us_summary = []
        for card in cards:
            if not is_us_card(card, cf_map, custom_fields):
                continue
            us_id = get_card_custom_value(card, "us_id", cf_map, custom_fields) or ""
            status = get_state_for_list(card.get("idList", ""), lists)
            uc_children = [
                c for c in cards
                if is_uc_card(c, cf_map, custom_fields)
                and get_card_custom_value(c, "us_id", cf_map, custom_fields) == us_id
            ]
            uc_done = sum(1 for c in uc_children if c.get("idList") in done_list_ids)
            us_summary.append({
                "us_id": us_id,
                "name": card.get("name", ""),
                "status": status,
                "uc_progress": f"{uc_done}/{len(uc_children)}",
            })

        return {
            "lists": list_stats,
            "progress": {"horas_done": done_hours, "horas_total": total_hours, "pct": round(pct, 1)},
            "us_summary": us_summary,
        }
    finally:
        await client.close()


async def import_spec(board_id: str, spec: dict, ctx: Context) -> dict[str, Any]:
    """Import a full project specification into the board.

    Creates US and UC cards from a structured spec. Each US gets a card with
    label, custom fields, and a "Casos de Uso" checklist. Each UC gets a card
    with labels, custom fields, description, and "Criterios de Aceptacion" checklist.

    Args:
        board_id: Trello board ID
        spec: JSON spec with structure: {user_stories: [{us_id, name, hours, screens, description, use_cases: [{uc_id, name, actor, hours, screens, acceptance_criteria: [str], context}]}]}

    Returns:
        Import results with counts of created items and any errors.
    """
    client = await get_session_client(ctx)
    try:
        parsed = ImportSpec(**spec)
        lists = await client.get_board_lists(board_id)
        backlog_id = None
        for lst in lists:
            if lst["name"].lower() == "backlog":
                backlog_id = lst["id"]
                break
        if not backlog_id:
            return {"error": "Backlog list not found", "code": "LIST_NOT_FOUND"}

        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)
        board_labels = await client.get_board_labels(board_id)

        us_label_id = next((l["id"] for l in board_labels if l.get("name") == "US"), None)
        uc_label_id = next((l["id"] for l in board_labels if l.get("name") == "UC"), None)

        created_us = 0
        created_uc = 0
        created_ac = 0
        errors: list[str] = []

        for us_spec in parsed.user_stories:
            try:
                us_desc = build_us_description(
                    us_spec.us_id, us_spec.name, us_spec.hours, us_spec.screens, us_spec.description
                )
                us_labels = [us_label_id] if us_label_id else []
                us_card = await client.create_card(backlog_id, f"{us_spec.us_id}: {us_spec.name}", us_desc, us_labels)
                us_card_id = us_card["id"]

                await _set_card_type(client, us_card_id, "US", cf_map, custom_fields)
                await _set_text_field(client, us_card_id, "us_id", us_spec.us_id, cf_map)
                await _set_number_field(client, us_card_id, "horas", us_spec.hours, cf_map)
                await _set_text_field(client, us_card_id, "pantallas", us_spec.screens, cf_map)

                us_group_label = await client.create_label(board_id, us_spec.us_id, "purple")
                us_group_label_id = us_group_label["id"]
                us_checklist = await client.create_checklist(us_card_id, "Casos de Uso")
                created_us += 1

                for uc_spec in us_spec.use_cases:
                    try:
                        uc_desc = build_uc_description(
                            uc_spec.uc_id, uc_spec.name, us_spec.us_id, us_spec.name,
                            uc_spec.actor, uc_spec.hours, uc_spec.screens,
                            uc_spec.acceptance_criteria, uc_spec.context,
                        )
                        uc_labels = []
                        if uc_label_id:
                            uc_labels.append(uc_label_id)
                        uc_labels.append(us_group_label_id)

                        uc_card = await client.create_card(
                            backlog_id, f"{uc_spec.uc_id}: {uc_spec.name}", uc_desc, uc_labels
                        )
                        uc_card_id = uc_card["id"]

                        await _set_card_type(client, uc_card_id, "UC", cf_map, custom_fields)
                        await _set_text_field(client, uc_card_id, "uc_id", uc_spec.uc_id, cf_map)
                        await _set_text_field(client, uc_card_id, "us_id", us_spec.us_id, cf_map)
                        await _set_number_field(client, uc_card_id, "horas", uc_spec.hours, cf_map)
                        await _set_text_field(client, uc_card_id, "pantallas", uc_spec.screens, cf_map)
                        if uc_spec.actor:
                            await _set_actor_field(client, uc_card_id, uc_spec.actor, cf_map, custom_fields)

                        ac_checklist = await client.create_checklist(uc_card_id, "Criterios de Aceptacion")
                        for idx, ac_text in enumerate(uc_spec.acceptance_criteria, 1):
                            ac_id = f"AC-{idx:02d}"
                            await client.add_checklist_item(ac_checklist["id"], f"{ac_id}: {ac_text}")
                            created_ac += 1

                        uc_url = uc_card.get("url", "")
                        await client.add_checklist_item(
                            us_checklist["id"], f"{uc_spec.uc_id}: {uc_spec.name} — {uc_url}",
                        )
                        created_uc += 1

                    except Exception as e:
                        errors.append(f"UC {uc_spec.uc_id}: {str(e)}")
                        logger.error("import_uc_error", uc_id=uc_spec.uc_id, error=str(e))

            except Exception as e:
                errors.append(f"US {us_spec.us_id}: {str(e)}")
                logger.error("import_us_error", us_id=us_spec.us_id, error=str(e))

        return {"created": {"us": created_us, "uc": created_uc, "ac": created_ac}, "errors": errors}
    finally:
        await client.close()


# ═══════════════════════════════════════════════════════════════════════
# USER STORIES (4 tools)
# ═══════════════════════════════════════════════════════════════════════


async def list_us(board_id: str, ctx: Context, status: str | None = None) -> list[dict[str, Any]]:
    """List all User Stories on the board.

    Filters cards with custom field tipo=US. Optionally filter by workflow
    status (backlog, ready, in_progress, review, done).

    Args:
        board_id: Trello board ID
        status: Optional workflow state filter

    Returns:
        List of US summaries with progress metrics.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)
        done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}

        result = []
        for card in cards:
            if not is_us_card(card, cf_map, custom_fields):
                continue
            card_state = get_state_for_list(card.get("idList", ""), lists)
            if status and card_state != status:
                continue

            us_id = get_card_custom_value(card, "us_id", cf_map, custom_fields) or ""
            hours = get_card_custom_value(card, "horas", cf_map, custom_fields) or 0
            screens = get_card_custom_value(card, "pantallas", cf_map, custom_fields) or ""

            uc_children = [
                c for c in cards
                if is_uc_card(c, cf_map, custom_fields)
                and get_card_custom_value(c, "us_id", cf_map, custom_fields) == us_id
            ]
            uc_done = sum(1 for c in uc_children if c.get("idList") in done_list_ids)

            ac_total = 0
            ac_done = 0
            for uc_card in uc_children:
                checklists = await client.get_card_checklists(uc_card["id"])
                acs = parse_checklist_acs(checklists)
                ac_total += len(acs)
                ac_done += sum(1 for ac in acs if ac.done)

            result.append({
                "us_id": us_id,
                "name": card.get("name", ""),
                "hours": float(hours),
                "status": card_state,
                "screens": screens,
                "uc_total": len(uc_children),
                "uc_done": uc_done,
                "ac_total": ac_total,
                "ac_done": ac_done,
            })

        return result
    finally:
        await client.close()


async def get_us(board_id: str, us_id: str, ctx: Context) -> dict[str, Any]:
    """Get detailed information about a User Story and its Use Cases.

    Reads the US card and all child UC cards (linked via us_id custom field).

    Args:
        board_id: Trello board ID
        us_id: User Story ID (e.g., "US-01")

    Returns:
        Full US detail with child UCs, attachments, and progress.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)
        done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}

        us_card = None
        for card in cards:
            if is_us_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "us_id", cf_map, custom_fields) == us_id:
                    us_card = card
                    break

        if not us_card:
            return {"error": f"User Story {us_id} not found", "code": "US_NOT_FOUND"}

        attachments = await client.get_card_attachments(us_card["id"])
        attach_list = [
            {"name": a.get("name", ""), "url": a.get("url", ""), "date": a.get("date", "")}
            for a in attachments
        ]

        use_cases = []
        for card in cards:
            if not is_uc_card(card, cf_map, custom_fields):
                continue
            if get_card_custom_value(card, "us_id", cf_map, custom_fields) != us_id:
                continue

            uc_id = get_card_custom_value(card, "uc_id", cf_map, custom_fields) or ""
            uc_hours = get_card_custom_value(card, "horas", cf_map, custom_fields) or 0
            uc_state = get_state_for_list(card.get("idList", ""), lists)
            actor = get_card_custom_value(card, "actor", cf_map, custom_fields) or ""

            checklists = await client.get_card_checklists(card["id"])
            acs = parse_checklist_acs(checklists)

            use_cases.append({
                "uc_id": uc_id,
                "name": card.get("name", ""),
                "actor": actor,
                "hours": float(uc_hours),
                "status": uc_state,
                "ac_total": len(acs),
                "ac_done": sum(1 for ac in acs if ac.done),
            })

        return {
            "us_id": us_id,
            "name": us_card.get("name", ""),
            "hours": float(get_card_custom_value(us_card, "horas", cf_map, custom_fields) or 0),
            "status": get_state_for_list(us_card.get("idList", ""), lists),
            "screens": get_card_custom_value(us_card, "pantallas", cf_map, custom_fields) or "",
            "description": us_card.get("desc", ""),
            "use_cases": use_cases,
            "attachments": attach_list,
        }
    finally:
        await client.close()


async def move_us(board_id: str, us_id: str, target: str, ctx: Context) -> dict[str, Any]:
    """Move a User Story and its Use Cases through the workflow.

    Movement rules:
    - backlog: moves US + ALL UCs to Backlog
    - ready: moves US to Ready + UCs in Backlog to Ready
    - in_progress: moves US to In Progress + UCs in Backlog/Ready to Ready
    - review: ONLY if all UCs are in Review or Done
    - done: ONLY if ALL UCs are in Done

    Args:
        board_id: Trello board ID
        us_id: User Story ID (e.g., "US-01")
        target: Target workflow state

    Returns:
        Movement result with count of UCs moved and any errors.
    """
    if target not in WORKFLOW_LIST_NAMES:
        return {"error": f"Invalid target: {target}. Must be one of: {list(WORKFLOW_LIST_NAMES.keys())}", "code": "INVALID_TARGET"}

    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        us_card = None
        for card in cards:
            if is_us_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "us_id", cf_map, custom_fields) == us_id:
                    us_card = card
                    break

        if not us_card:
            return {"error": f"User Story {us_id} not found", "code": "US_NOT_FOUND"}

        uc_cards = [
            c for c in cards
            if is_uc_card(c, cf_map, custom_fields)
            and get_card_custom_value(c, "us_id", cf_map, custom_fields) == us_id
        ]

        target_list_id = await get_list_id_for_state(client, board_id, target)
        ucs_moved = 0
        errors: list[str] = []

        if target == "review":
            review_done_names = {"review", "done"}
            for uc in uc_cards:
                uc_state = get_state_for_list(uc.get("idList", ""), lists)
                if uc_state not in review_done_names:
                    uc_id = get_card_custom_value(uc, "uc_id", cf_map, custom_fields) or "?"
                    return {
                        "error": f"Cannot move to review: UC {uc_id} is in '{uc_state}'",
                        "code": "UC_NOT_READY_FOR_REVIEW",
                    }

        elif target == "done":
            for uc in uc_cards:
                uc_state = get_state_for_list(uc.get("idList", ""), lists)
                if uc_state != "done":
                    uc_id = get_card_custom_value(uc, "uc_id", cf_map, custom_fields) or "?"
                    return {
                        "error": f"Cannot move to done: UC {uc_id} is in '{uc_state}'",
                        "code": "UC_NOT_DONE",
                    }

        await client.move_card(us_card["id"], target_list_id)

        if target == "backlog":
            for uc in uc_cards:
                await client.move_card(uc["id"], target_list_id)
                ucs_moved += 1
        elif target == "ready":
            backlog_ids = {lst["id"] for lst in lists if lst["name"].lower() == "backlog"}
            for uc in uc_cards:
                if uc.get("idList") in backlog_ids:
                    await client.move_card(uc["id"], target_list_id)
                    ucs_moved += 1
        elif target == "in_progress":
            ready_id = await get_list_id_for_state(client, board_id, "ready")
            backlog_ready_ids = {lst["id"] for lst in lists if lst["name"].lower() in ("backlog", "ready")}
            for uc in uc_cards:
                if uc.get("idList") in backlog_ready_ids:
                    await client.move_card(uc["id"], ready_id)
                    ucs_moved += 1

        return {"us_id": us_id, "new_status": target, "ucs_moved": ucs_moved, "errors": errors}
    finally:
        await client.close()


async def get_us_progress(board_id: str, us_id: str, ctx: Context) -> dict[str, Any]:
    """Get detailed progress for a User Story.

    Reads all child UCs and their acceptance criteria to calculate
    comprehensive progress metrics.

    Args:
        board_id: Trello board ID
        us_id: User Story ID (e.g., "US-01")

    Returns:
        Progress detail with UC-level and AC-level completion stats.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)
        done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}

        us_card = None
        for card in cards:
            if is_us_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "us_id", cf_map, custom_fields) == us_id:
                    us_card = card
                    break

        if not us_card:
            return {"error": f"User Story {us_id} not found", "code": "US_NOT_FOUND"}

        ucs_data = []
        total_acs = 0
        passed_acs = 0
        hours_total = 0.0
        hours_done = 0.0

        for card in cards:
            if not is_uc_card(card, cf_map, custom_fields):
                continue
            if get_card_custom_value(card, "us_id", cf_map, custom_fields) != us_id:
                continue

            uc_id = get_card_custom_value(card, "uc_id", cf_map, custom_fields) or ""
            uc_hours = float(get_card_custom_value(card, "horas", cf_map, custom_fields) or 0)
            uc_state = get_state_for_list(card.get("idList", ""), lists)
            is_done = card.get("idList") in done_list_ids

            checklists = await client.get_card_checklists(card["id"])
            acs = parse_checklist_acs(checklists)

            acs_total_uc = len(acs)
            acs_passed_uc = sum(1 for ac in acs if ac.done)

            total_acs += acs_total_uc
            passed_acs += acs_passed_uc
            hours_total += uc_hours
            if is_done:
                hours_done += uc_hours

            ucs_data.append({
                "uc_id": uc_id,
                "name": card.get("name", ""),
                "status": uc_state,
                "acs_total": acs_total_uc,
                "acs_passed": acs_passed_uc,
            })

        done_ucs = sum(1 for u in ucs_data if u["status"] == "done")

        return {
            "us_id": us_id,
            "name": us_card.get("name", ""),
            "total_ucs": len(ucs_data),
            "done_ucs": done_ucs,
            "total_acs": total_acs,
            "passed_acs": passed_acs,
            "hours_total": hours_total,
            "hours_done": hours_done,
            "ucs": ucs_data,
        }
    finally:
        await client.close()


# ═══════════════════════════════════════════════════════════════════════
# USE CASES (5 tools)
# ═══════════════════════════════════════════════════════════════════════


async def list_uc(board_id: str, ctx: Context, us_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    """List Use Cases on the board, optionally filtered by parent US or status.

    Args:
        board_id: Trello board ID
        us_id: Optional parent US ID filter (e.g., "US-01")
        status: Optional workflow state filter (backlog, ready, in_progress, review, done)

    Returns:
        List of UC summaries with AC progress.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        result = []
        for card in cards:
            if not is_uc_card(card, cf_map, custom_fields):
                continue
            card_us_id = get_card_custom_value(card, "us_id", cf_map, custom_fields) or ""
            if us_id and card_us_id != us_id:
                continue
            card_state = get_state_for_list(card.get("idList", ""), lists)
            if status and card_state != status:
                continue

            uc_id = get_card_custom_value(card, "uc_id", cf_map, custom_fields) or ""
            hours = get_card_custom_value(card, "horas", cf_map, custom_fields) or 0
            screens = get_card_custom_value(card, "pantallas", cf_map, custom_fields) or ""
            actor = get_card_custom_value(card, "actor", cf_map, custom_fields) or ""

            checklists = await client.get_card_checklists(card["id"])
            acs = parse_checklist_acs(checklists)

            result.append({
                "uc_id": uc_id,
                "us_id": card_us_id,
                "name": card.get("name", ""),
                "actor": actor,
                "hours": float(hours),
                "status": card_state,
                "screens": screens,
                "ac_total": len(acs),
                "ac_done": sum(1 for ac in acs if ac.done),
            })

        return result
    finally:
        await client.close()


async def get_uc(board_id: str, uc_id: str, ctx: Context) -> dict[str, Any]:
    """Get full details of a Use Case, optimized for LLM consumption.

    Reads the UC card, parses its structured markdown description,
    reads AC checklist status, and returns a complete JSON representation.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")

    Returns:
        Complete UC detail with acceptance criteria, context, and attachments.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        uc_card = None
        for card in cards:
            if is_uc_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "uc_id", cf_map, custom_fields) == uc_id:
                    uc_card = card
                    break

        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        desc_raw = uc_card.get("desc", "")
        parsed = parse_uc_description(desc_raw)

        card_us_id = get_card_custom_value(uc_card, "us_id", cf_map, custom_fields) or ""
        hours = float(get_card_custom_value(uc_card, "horas", cf_map, custom_fields) or 0)
        screens_raw = get_card_custom_value(uc_card, "pantallas", cf_map, custom_fields) or ""
        actor = get_card_custom_value(uc_card, "actor", cf_map, custom_fields) or ""
        status = get_state_for_list(uc_card.get("idList", ""), lists)

        screens = [s.strip() for s in screens_raw.split(",") if s.strip()] if screens_raw else parsed.get("screens", [])

        us_name = ""
        for card in cards:
            if is_us_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "us_id", cf_map, custom_fields) == card_us_id:
                    us_name = card.get("name", "").replace(f"{card_us_id}: ", "")
                    break

        checklists = await client.get_card_checklists(uc_card["id"])
        acs = parse_checklist_acs(checklists)
        ac_list = [{"id": ac.id, "text": ac.text, "done": ac.done} for ac in acs]

        attachments = await client.get_card_attachments(uc_card["id"])
        attach_list = [
            {"name": a.get("name", ""), "url": a.get("url", ""), "date": a.get("date", "")}
            for a in attachments
        ]

        return {
            "uc_id": uc_id,
            "name": uc_card.get("name", "").replace(f"{uc_id}: ", ""),
            "us_id": card_us_id,
            "us_name": us_name,
            "actor": actor or parsed.get("actor", ""),
            "hours": hours,
            "screens": screens,
            "status": status,
            "acceptance_criteria": ac_list,
            "context": parsed.get("context", ""),
            "description_raw": desc_raw,
            "attachments": attach_list,
            "trello_card_id": uc_card["id"],
            "trello_card_url": uc_card.get("url", ""),
        }
    finally:
        await client.close()


async def move_uc(board_id: str, uc_id: str, target: str, ctx: Context) -> dict[str, Any]:
    """Move a Use Case to a workflow state.

    When moving to 'done', automatically marks the corresponding checkitem
    in the parent US's checklist as complete.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")
        target: Target state (backlog, ready, in_progress, review, done)

    Returns:
        Movement result with US checklist update status.
    """
    if target not in WORKFLOW_LIST_NAMES:
        return {"error": f"Invalid target: {target}", "code": "INVALID_TARGET"}

    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        uc_card = None
        for card in cards:
            if is_uc_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "uc_id", cf_map, custom_fields) == uc_id:
                    uc_card = card
                    break

        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        target_list_id = await get_list_id_for_state(client, board_id, target)
        await client.move_card(uc_card["id"], target_list_id)

        us_checklist_updated = False
        us_all_done = False
        card_us_id = get_card_custom_value(uc_card, "us_id", cf_map, custom_fields) or ""

        if target == "done" and card_us_id:
            us_checklist_updated, us_all_done = await _update_us_checklist_for_uc(
                client, cards, cf_map, custom_fields, lists, card_us_id, uc_id
            )

        return {
            "uc_id": uc_id,
            "new_status": target,
            "us_checklist_updated": us_checklist_updated,
            "us_all_done": us_all_done,
        }
    finally:
        await client.close()


async def start_uc(board_id: str, uc_id: str, ctx: Context) -> dict[str, Any]:
    """Start working on a Use Case.

    Shortcut that moves the UC to In Progress, adds a timestamp comment,
    and returns the full UC detail for the LLM to work with.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")

    Returns:
        Full UC detail (same as get_uc) for immediate use.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        uc_card = None
        for card in cards:
            if is_uc_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "uc_id", cf_map, custom_fields) == uc_id:
                    uc_card = card
                    break

        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        target_list_id = await get_list_id_for_state(client, board_id, "in_progress")
        await client.move_card(uc_card["id"], target_list_id)

        now = datetime.now(timezone.utc).isoformat()
        await client.add_comment(uc_card["id"], f"Desarrollo iniciado: {now}")
    finally:
        await client.close()

    return await get_uc(board_id, uc_id, ctx)


async def complete_uc(board_id: str, uc_id: str, ctx: Context, evidence: str | None = None) -> dict[str, Any]:
    """Mark a Use Case as complete.

    Moves to Done, marks the corresponding checkitem in the parent US
    checklist as complete, and optionally adds evidence as a comment.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")
        evidence: Optional evidence text to add as comment

    Returns:
        Completion result with US update status.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        uc_card = None
        for card in cards:
            if is_uc_card(card, cf_map, custom_fields):
                if get_card_custom_value(card, "uc_id", cf_map, custom_fields) == uc_id:
                    uc_card = card
                    break

        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        done_list_id = await get_list_id_for_state(client, board_id, "done")
        await client.move_card(uc_card["id"], done_list_id)

        if evidence:
            await client.add_comment(uc_card["id"], evidence)

        card_us_id = get_card_custom_value(uc_card, "us_id", cf_map, custom_fields) or ""
        us_checklist_updated = False
        us_all_done = False

        if card_us_id:
            us_checklist_updated, us_all_done = await _update_us_checklist_for_uc(
                client, cards, cf_map, custom_fields, lists, card_us_id, uc_id
            )

        now = datetime.now(timezone.utc).isoformat()
        return {
            "uc_id": uc_id,
            "completed_at": now,
            "us_checklist_updated": us_checklist_updated,
            "us_all_done": us_all_done,
            "us_id": card_us_id,
        }
    finally:
        await client.close()


# ═══════════════════════════════════════════════════════════════════════
# ACCEPTANCE CRITERIA (3 tools)
# ═══════════════════════════════════════════════════════════════════════


async def mark_ac(board_id: str, uc_id: str, ac_id: str, passed: bool, ctx: Context, evidence: str | None = None) -> dict[str, Any]:
    """Mark a single Acceptance Criterion as passed or failed.

    Updates the checkitem state in the UC's checklist and adds a comment.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")
        ac_id: Acceptance Criterion ID (e.g., "AC-01")
        passed: True if the criterion passed, False if failed
        evidence: Optional evidence text

    Returns:
        AC status update result with totals.
    """
    client = await get_session_client(ctx)
    try:
        uc_card = await _find_uc_card(client, board_id, uc_id)
        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        checkitem_id, _ = await _find_ac_checkitem(client, uc_card["id"], ac_id)
        if not checkitem_id:
            return {"error": f"AC {ac_id} not found in {uc_id}", "code": "AC_NOT_FOUND"}

        state = "complete" if passed else "incomplete"
        await client.update_checklist_item(uc_card["id"], checkitem_id, state)

        status_text = "PASSED" if passed else "FAILED"
        comment = f"{ac_id}: {status_text}"
        if evidence:
            comment += f" — {evidence}"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        comment += f" [{now}]"
        await client.add_comment(uc_card["id"], comment)

        checklists = await client.get_card_checklists(uc_card["id"])
        acs = parse_checklist_acs(checklists)

        return {
            "uc_id": uc_id,
            "ac_id": ac_id,
            "passed": passed,
            "ac_total": len(acs),
            "ac_done": sum(1 for ac in acs if ac.done),
        }
    finally:
        await client.close()


async def mark_ac_batch(board_id: str, uc_id: str, results: list[dict], ctx: Context) -> dict[str, Any]:
    """Mark multiple Acceptance Criteria at once.

    Processes all AC results in a single operation and adds a consolidated comment.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")
        results: List of {ac_id: str, passed: bool, evidence: str | None}

    Returns:
        Batch result with total/passed/failed counts.
    """
    client = await get_session_client(ctx)
    try:
        uc_card = await _find_uc_card(client, board_id, uc_id)
        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        details = []
        passed_count = 0
        failed_count = 0

        for r in results:
            ac_id = r.get("ac_id", "")
            passed = r.get("passed", False)

            checkitem_id, _ = await _find_ac_checkitem(client, uc_card["id"], ac_id)
            if checkitem_id:
                state = "complete" if passed else "incomplete"
                await client.update_checklist_item(uc_card["id"], checkitem_id, state)

            if passed:
                passed_count += 1
            else:
                failed_count += 1

            details.append({"ac_id": ac_id, "passed": passed})

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        comment_lines = [f"Validacion AG-09b [{now}]:"]
        for d in details:
            status_text = "PASSED" if d["passed"] else "FAILED"
            comment_lines.append(f"  {d['ac_id']}: {status_text}")
        await client.add_comment(uc_card["id"], "\n".join(comment_lines))

        if failed_count == 0 and passed_count > 0:
            await client.add_comment(uc_card["id"], "Todos los criterios de aceptacion validados")

        return {
            "uc_id": uc_id,
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "details": details,
        }
    finally:
        await client.close()


async def get_ac_status(board_id: str, uc_id: str, ctx: Context) -> dict[str, Any]:
    """Get the status of all Acceptance Criteria for a Use Case.

    Args:
        board_id: Trello board ID
        uc_id: Use Case ID (e.g., "UC-001")

    Returns:
        AC status with total, done, pending counts and individual criteria.
    """
    client = await get_session_client(ctx)
    try:
        uc_card = await _find_uc_card(client, board_id, uc_id)
        if not uc_card:
            return {"error": f"Use Case {uc_id} not found", "code": "UC_NOT_FOUND"}

        checklists = await client.get_card_checklists(uc_card["id"])
        acs = parse_checklist_acs(checklists)

        done_count = sum(1 for ac in acs if ac.done)
        return {
            "uc_id": uc_id,
            "total": len(acs),
            "done": done_count,
            "pending": len(acs) - done_count,
            "criteria": [{"id": ac.id, "text": ac.text, "done": ac.done} for ac in acs],
        }
    finally:
        await client.close()


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
    """Convert markdown to PDF and attach it to a US or UC card.

    Generates a PDF from the markdown content, uploads it as an attachment,
    and adds a summary comment.

    Args:
        board_id: Trello board ID
        target_id: US or UC ID (e.g., "US-01" or "UC-001")
        target_type: "us" or "uc"
        evidence_type: Type of evidence: "prd", "plan", "ag09", "delivery", "feedback"
        markdown_content: Markdown text to convert to PDF
        summary: Optional summary for the comment

    Returns:
        Attachment result with URL and comment status.
    """
    if target_type not in ("us", "uc"):
        return {"error": "target_type must be 'us' or 'uc'", "code": "INVALID_TARGET_TYPE"}
    if evidence_type not in ("prd", "plan", "ag09", "delivery", "feedback"):
        return {"error": "Invalid evidence_type", "code": "INVALID_EVIDENCE_TYPE"}

    client = await get_session_client(ctx)
    try:
        field_name = "us_id" if target_type == "us" else "uc_id"
        card = await find_card_by_custom_field(client, board_id, field_name, target_id)
        if not card:
            return {"error": f"{target_type.upper()} {target_id} not found", "code": "TARGET_NOT_FOUND"}

        filename = f"{target_id}_{evidence_type}.pdf"
        title = f"{target_id} - {evidence_type.upper()}"
        pdf_bytes = markdown_to_pdf(markdown_content, title=title)

        attachment = await client.add_attachment(card["id"], pdf_bytes, filename)

        if not summary:
            summary = f"Evidencia {evidence_type.upper()} generada ({len(markdown_content)} chars)"
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        await client.add_comment(card["id"], f"{evidence_type.upper()} generado [{now}] — {summary}")

        return {
            "target_id": target_id,
            "evidence_type": evidence_type,
            "attachment_id": attachment.get("id", ""),
            "attachment_url": attachment.get("url", ""),
            "comment_added": True,
        }
    finally:
        await client.close()


async def get_evidence(
    board_id: str,
    target_id: str,
    target_type: str,
    ctx: Context,
    evidence_type: str | None = None,
) -> dict[str, Any]:
    """Get evidence attachments and activity for a US or UC card.

    Args:
        board_id: Trello board ID
        target_id: US or UC ID (e.g., "US-01" or "UC-001")
        target_type: "us" or "uc"
        evidence_type: Optional filter by evidence type name

    Returns:
        Attachments and activity comments for the target card.
    """
    if target_type not in ("us", "uc"):
        return {"error": "target_type must be 'us' or 'uc'", "code": "INVALID_TARGET_TYPE"}

    client = await get_session_client(ctx)
    try:
        field_name = "us_id" if target_type == "us" else "uc_id"
        card = await find_card_by_custom_field(client, board_id, field_name, target_id)
        if not card:
            return {"error": f"{target_type.upper()} {target_id} not found", "code": "TARGET_NOT_FOUND"}

        attachments = await client.get_card_attachments(card["id"])
        attach_list = []
        for a in attachments:
            name = a.get("name", "")
            if evidence_type and evidence_type not in name.lower():
                continue
            attach_list.append({
                "name": name,
                "url": a.get("url", ""),
                "date": a.get("date", ""),
                "size": a.get("bytes", 0),
            })

        actions = await client.get_card_actions(card["id"], filter="commentCard")
        activity = [
            {"text": a.get("data", {}).get("text", ""), "date": a.get("date", "")}
            for a in actions
        ]

        return {"target_id": target_id, "attachments": attach_list, "activity": activity}
    finally:
        await client.close()


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD (3 tools)
# ═══════════════════════════════════════════════════════════════════════


async def get_sprint_status(board_id: str, ctx: Context) -> dict[str, Any]:
    """Get executive summary of the entire board.

    Provides counts by status, hours progress, AC pass rates, and blocked items.

    Args:
        board_id: Trello board ID

    Returns:
        Sprint status dashboard with comprehensive metrics.
    """
    client = await get_session_client(ctx)
    try:
        board = await client.get_board(board_id)
        lists = await client.get_board_lists(board_id)
        cards = await client.get_board_cards(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        board_labels = await client.get_board_labels(board_id)
        blocked_label_id = next((l["id"] for l in board_labels if l.get("name", "").lower() == "bloqueado"), None)

        total_us = 0
        total_uc = 0
        total_ac = 0
        by_status: dict[str, dict[str, int]] = {}
        hours_total = 0.0
        hours_done = 0.0
        hours_in_progress = 0.0
        acs_passed = 0
        blocked: list[dict] = []

        done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}
        ip_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "in progress"}

        for state in WORKFLOW_LIST_NAMES:
            by_status[state] = {"us": 0, "uc": 0}

        for card in cards:
            card_state = get_state_for_list(card.get("idList", ""), lists)
            _is_us = is_us_card(card, cf_map, custom_fields)
            _is_uc = is_uc_card(card, cf_map, custom_fields)

            if _is_us:
                total_us += 1
                if card_state in by_status:
                    by_status[card_state]["us"] += 1
            elif _is_uc:
                total_uc += 1
                if card_state in by_status:
                    by_status[card_state]["uc"] += 1

                h = float(get_card_custom_value(card, "horas", cf_map, custom_fields) or 0)
                hours_total += h
                if card.get("idList") in done_list_ids:
                    hours_done += h
                elif card.get("idList") in ip_list_ids:
                    hours_in_progress += h

                checklists = await client.get_card_checklists(card["id"])
                acs = parse_checklist_acs(checklists)
                total_ac += len(acs)
                acs_passed += sum(1 for ac in acs if ac.done)

            if blocked_label_id and blocked_label_id in [l.get("id") for l in card.get("labels", [])]:
                card_id_val = ""
                if _is_us:
                    card_id_val = get_card_custom_value(card, "us_id", cf_map, custom_fields) or ""
                elif _is_uc:
                    card_id_val = get_card_custom_value(card, "uc_id", cf_map, custom_fields) or ""
                blocked.append({"id": card_id_val, "name": card.get("name", ""), "status": card_state})

        hours_pct = (hours_done / hours_total * 100) if hours_total > 0 else 0
        acs_pct = (acs_passed / total_ac * 100) if total_ac > 0 else 0

        return {
            "board_name": board.get("name", ""),
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
            "acs": {"total": total_ac, "passed": acs_passed, "pct": round(acs_pct, 1)},
            "blocked": blocked,
        }
    finally:
        await client.close()


async def get_delivery_report(board_id: str, ctx: Context) -> dict[str, Any]:
    """Generate a client-oriented delivery report.

    Summarizes progress per User Story with completion percentages.

    Args:
        board_id: Trello board ID

    Returns:
        Delivery report with per-US progress and overall summary.
    """
    client = await get_session_client(ctx)
    try:
        board = await client.get_board(board_id)
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)
        done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}

        us_cards = [c for c in cards if is_us_card(c, cf_map, custom_fields)]
        total_us = len(us_cards)
        completed_us = 0
        user_stories = []

        for us_card in us_cards:
            us_id = get_card_custom_value(us_card, "us_id", cf_map, custom_fields) or ""
            us_name = us_card.get("name", "").replace(f"{us_id}: ", "")
            us_hours = float(get_card_custom_value(us_card, "horas", cf_map, custom_fields) or 0)
            us_status = get_state_for_list(us_card.get("idList", ""), lists)

            uc_children = [
                c for c in cards
                if is_uc_card(c, cf_map, custom_fields)
                and get_card_custom_value(c, "us_id", cf_map, custom_fields) == us_id
            ]
            uc_done = sum(1 for c in uc_children if c.get("idList") in done_list_ids)
            uc_total = len(uc_children)

            ac_total = 0
            ac_passed = 0
            for uc in uc_children:
                cls = await client.get_card_checklists(uc["id"])
                acs = parse_checklist_acs(cls)
                ac_total += len(acs)
                ac_passed += sum(1 for ac in acs if ac.done)

            if us_status == "done":
                completed_us += 1

            user_stories.append({
                "us_id": us_id,
                "name": us_name,
                "status": us_status,
                "hours": us_hours,
                "ucs_completed": f"{uc_done}/{uc_total}",
                "acs_passed": f"{ac_passed}/{ac_total}",
            })

        pct = (completed_us / total_us * 100) if total_us > 0 else 0

        return {
            "project": board.get("name", ""),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {"total_us": total_us, "completed_us": completed_us, "pct": round(pct, 1)},
            "user_stories": user_stories,
        }
    finally:
        await client.close()


async def find_next_uc(board_id: str, ctx: Context) -> dict[str, Any] | None:
    """Find the next Use Case to work on.

    Priority:
    1. UCs in Ready whose US has UCs in In Progress (maintain focus)
    2. UCs in Ready from the US with most UCs in Ready (start a block)
    3. First UC in Ready by position

    Args:
        board_id: Trello board ID

    Returns:
        Full UC detail (same as get_uc) or None if nothing in Ready.
    """
    client = await get_session_client(ctx)
    try:
        cards = await client.get_board_cards(board_id)
        lists = await client.get_board_lists(board_id)
        custom_fields = await client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)

        ready_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "ready"}
        ip_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "in progress"}

        ready_ucs = [
            c for c in cards
            if is_uc_card(c, cf_map, custom_fields) and c.get("idList") in ready_list_ids
        ]

        if not ready_ucs:
            return None

        us_with_ip = set()
        for card in cards:
            if is_uc_card(card, cf_map, custom_fields) and card.get("idList") in ip_list_ids:
                uid = get_card_custom_value(card, "us_id", cf_map, custom_fields) or ""
                if uid:
                    us_with_ip.add(uid)

        priority1 = [
            c for c in ready_ucs
            if (get_card_custom_value(c, "us_id", cf_map, custom_fields) or "") in us_with_ip
        ]

        if priority1:
            chosen = priority1[0]
        else:
            us_ready_count: dict[str, int] = {}
            for c in ready_ucs:
                uid = get_card_custom_value(c, "us_id", cf_map, custom_fields) or ""
                us_ready_count[uid] = us_ready_count.get(uid, 0) + 1

            if us_ready_count:
                top_us = max(us_ready_count, key=us_ready_count.get)
                priority2 = [
                    c for c in ready_ucs
                    if get_card_custom_value(c, "us_id", cf_map, custom_fields) == top_us
                ]
                chosen = priority2[0] if priority2 else ready_ucs[0]
            else:
                chosen = ready_ucs[0]

        uc_id = get_card_custom_value(chosen, "uc_id", cf_map, custom_fields) or ""
    finally:
        await client.close()

    return await get_uc(board_id, uc_id, ctx)


# ═══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════


async def _find_uc_card(client: TrelloClient, board_id: str, uc_id: str) -> dict | None:
    """Find a UC card by uc_id custom field."""
    cards = await client.get_board_cards(board_id)
    custom_fields = await client.get_board_custom_fields(board_id)
    cf_map = build_custom_field_map(custom_fields)
    for card in cards:
        if is_uc_card(card, cf_map, custom_fields):
            if get_card_custom_value(card, "uc_id", cf_map, custom_fields) == uc_id:
                return card
    return None


async def _find_ac_checkitem(client: TrelloClient, card_id: str, ac_id: str) -> tuple[str | None, str | None]:
    """Find a checkitem by AC-XX id. Returns (checkitem_id, checklist_id)."""
    checklists = await client.get_card_checklists(card_id)
    for cl in checklists:
        if "aceptacion" in cl.get("name", "").lower() or "acceptance" in cl.get("name", "").lower():
            for item in cl.get("checkItems", []):
                if item.get("name", "").startswith(ac_id):
                    return item["id"], cl["id"]
    return None, None


async def _set_card_type(
    client: TrelloClient, card_id: str, tipo: str, cf_map: dict, custom_fields: list[dict]
) -> None:
    cf_info = cf_map.get("tipo")
    if not cf_info:
        return
    option_id = find_option_id(custom_fields, "tipo", tipo)
    if option_id:
        await client.set_custom_field_value(card_id, cf_info["id"], {"idValue": option_id})


async def _set_text_field(client: TrelloClient, card_id: str, field_name: str, value: str, cf_map: dict) -> None:
    cf_info = cf_map.get(field_name.lower())
    if not cf_info or not value:
        return
    await client.set_custom_field_value(card_id, cf_info["id"], {"value": {"text": str(value)}})


async def _set_number_field(client: TrelloClient, card_id: str, field_name: str, value: float, cf_map: dict) -> None:
    cf_info = cf_map.get(field_name.lower())
    if not cf_info:
        return
    await client.set_custom_field_value(card_id, cf_info["id"], {"value": {"number": str(value)}})


async def _set_actor_field(
    client: TrelloClient, card_id: str, actor: str, cf_map: dict, custom_fields: list[dict]
) -> None:
    cf_info = cf_map.get("actor")
    if not cf_info:
        return
    option_id = find_option_id(custom_fields, "actor", actor)
    if option_id:
        await client.set_custom_field_value(card_id, cf_info["id"], {"idValue": option_id})


async def _update_us_checklist_for_uc(
    client: TrelloClient,
    cards: list[dict],
    cf_map: dict,
    custom_fields: list[dict],
    lists: list[dict],
    us_id: str,
    uc_id: str,
) -> tuple[bool, bool]:
    """Update parent US checklist when a UC is completed."""
    us_card = None
    for card in cards:
        if is_us_card(card, cf_map, custom_fields):
            if get_card_custom_value(card, "us_id", cf_map, custom_fields) == us_id:
                us_card = card
                break

    if not us_card:
        return False, False

    us_checklists = await client.get_card_checklists(us_card["id"])
    checklist_updated = False
    for cl in us_checklists:
        if "caso" in cl.get("name", "").lower() or "use" in cl.get("name", "").lower():
            for item in cl.get("checkItems", []):
                if uc_id in item.get("name", ""):
                    await client.update_checklist_item(us_card["id"], item["id"], "complete")
                    checklist_updated = True
                    break

    done_list_ids = {lst["id"] for lst in lists if lst["name"].lower() == "done"}
    uc_siblings = [
        c for c in cards
        if is_uc_card(c, cf_map, custom_fields)
        and get_card_custom_value(c, "us_id", cf_map, custom_fields) == us_id
    ]

    all_done = all(
        c.get("idList") in done_list_ids
        or get_card_custom_value(c, "uc_id", cf_map, custom_fields) == uc_id
        for c in uc_siblings
    )

    if all_done and uc_siblings:
        total_ucs = len(uc_siblings)
        total_acs = 0
        for uc in uc_siblings:
            cls = await client.get_card_checklists(uc["id"])
            acs = parse_checklist_acs(cls)
            total_acs += len(acs)

        await client.add_comment(
            us_card["id"],
            f"{us_id} completada: {total_ucs}/{total_ucs} UCs, {total_acs} ACs",
        )

    return checklist_updated, all_done


def register_spec_driven_tools(mcp_instance) -> None:
    """Register all 21 spec-driven tools on the given FastMCP instance."""

    # Auth (1)
    mcp_instance.tool(
        description="Configure Trello API credentials for this session. "
        "MUST be called before any other spec-driven tool."
    )(set_auth_token)

    # Board & Setup (3)
    mcp_instance.tool(
        description="Create a new board with Dev Engine structure: 5 workflow lists, "
        "6 custom fields, and base labels."
    )(setup_board)
    mcp_instance.tool(
        description="Get board status: card counts per list, hours progress, US summary."
    )(get_board_status)
    mcp_instance.tool(
        description="Import a full project spec (US + UC + AC) into the board from JSON."
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
        description="Move a UC to a workflow state. Auto-updates parent US checklist."
    )(move_uc)
    mcp_instance.tool(
        description="Start working on a UC: moves to In Progress, adds timestamp, returns full detail."
    )(start_uc)
    mcp_instance.tool(
        description="Complete a UC: moves to Done, updates parent US checklist, adds evidence."
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
        description="Convert markdown to PDF and attach as evidence to a US or UC card."
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
