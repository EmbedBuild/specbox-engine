"""Helper functions for board operations: finding cards, parsing descriptions, etc."""

from __future__ import annotations

import re
from typing import Any

from .models import (
    WORKFLOW_LIST_NAMES,
    LIST_NAME_TO_STATE,
    AcceptanceCriterion,
    WorkflowState,
)
from .trello_client import TrelloClient


async def get_list_id_by_name(client: TrelloClient, board_id: str, name: str) -> str | None:
    """Get list ID by name (case-insensitive)."""
    lists = await client.get_board_lists(board_id)
    name_lower = name.lower()
    for lst in lists:
        if lst.get("name", "").lower() == name_lower:
            return lst["id"]
    return None


async def get_list_map(client: TrelloClient, board_id: str) -> dict[str, str]:
    """Get mapping of list name (lowercase) -> list_id."""
    lists = await client.get_board_lists(board_id)
    return {lst["name"].lower(): lst["id"] for lst in lists}


async def get_list_id_for_state(client: TrelloClient, board_id: str, state: WorkflowState) -> str:
    """Get list ID for a workflow state. Raises if not found."""
    list_name = WORKFLOW_LIST_NAMES[state]
    list_id = await get_list_id_by_name(client, board_id, list_name)
    if not list_id:
        raise ValueError(f"List '{list_name}' not found on board {board_id}")
    return list_id


def get_state_for_list(list_id: str, lists: list[dict]) -> str:
    """Given a list_id and board lists, return the workflow state name."""
    for lst in lists:
        if lst["id"] == list_id:
            name = lst.get("name", "")
            return LIST_NAME_TO_STATE.get(name, name.lower())
    return "unknown"


def extract_custom_field_value(
    card: dict,
    field_id: str,
    field_type: str,
    custom_fields: list[dict] | None = None,
) -> Any:
    """Extract a custom field value from a card's customFieldItems."""
    items = card.get("customFieldItems", [])
    for item in items:
        if item.get("idCustomField") == field_id:
            if field_type == "text":
                return item.get("value", {}).get("text", "")
            elif field_type == "number":
                val = item.get("value", {}).get("number", "0")
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return 0.0
            elif field_type == "list":
                id_value = item.get("idValue", "")
                if custom_fields and id_value:
                    for cf in custom_fields:
                        if cf["id"] == field_id:
                            for opt in cf.get("options", []):
                                if opt["id"] == id_value:
                                    return opt.get("value", {}).get("text", "")
                return id_value
    return None


def build_custom_field_map(custom_fields: list[dict]) -> dict[str, dict]:
    """Build a map of field_name -> {id, type, options} from board custom fields."""
    result: dict[str, dict] = {}
    for cf in custom_fields:
        name = cf.get("name", "").lower()
        result[name] = {
            "id": cf["id"],
            "type": cf.get("type", "text"),
            "options": cf.get("options", []),
        }
    return result


def get_card_custom_value(card: dict, field_name: str, cf_map: dict[str, dict], custom_fields: list[dict]) -> Any:
    """Get a custom field value by field name using the cf_map."""
    cf_info = cf_map.get(field_name.lower())
    if not cf_info:
        return None
    return extract_custom_field_value(card, cf_info["id"], cf_info["type"], custom_fields)


def is_us_card(card: dict, cf_map: dict[str, dict], custom_fields: list[dict]) -> bool:
    """Check if a card is a User Story (tipo=US)."""
    tipo = get_card_custom_value(card, "tipo", cf_map, custom_fields)
    return tipo == "US"


def is_uc_card(card: dict, cf_map: dict[str, dict], custom_fields: list[dict]) -> bool:
    """Check if a card is a Use Case (tipo=UC)."""
    tipo = get_card_custom_value(card, "tipo", cf_map, custom_fields)
    return tipo == "UC"


async def find_card_by_custom_field(
    client: TrelloClient,
    board_id: str,
    field_name: str,
    value: str,
) -> dict | None:
    """Find a card on the board by custom field value (e.g., us_id=US-01)."""
    cards = await client.get_board_cards(board_id)
    custom_fields = await client.get_board_custom_fields(board_id)
    cf_map = build_custom_field_map(custom_fields)

    for card in cards:
        card_value = get_card_custom_value(card, field_name, cf_map, custom_fields)
        if card_value == value:
            return card
    return None


async def get_us_children(client: TrelloClient, board_id: str, us_id: str) -> list[dict]:
    """Get all UC cards that belong to a US (via custom field us_id)."""
    cards = await client.get_board_cards(board_id)
    custom_fields = await client.get_board_custom_fields(board_id)
    cf_map = build_custom_field_map(custom_fields)

    children = []
    for card in cards:
        if not is_uc_card(card, cf_map, custom_fields):
            continue
        card_us_id = get_card_custom_value(card, "us_id", cf_map, custom_fields)
        if card_us_id == us_id:
            children.append(card)
    return children


def parse_uc_description(description: str) -> dict[str, Any]:
    """Parse structured markdown of a UC card description into a dict."""
    result: dict[str, Any] = {
        "uc_id": "",
        "name": "",
        "us_id": "",
        "us_name": "",
        "actor": "",
        "hours": 0,
        "screens": [],
        "acceptance_criteria": [],
        "context": "",
        "notes": "",
    }

    if not description:
        return result

    # Parse header: ## UC-001: Name
    header_match = re.search(r"##\s+(UC-\d+):\s*(.+)", description)
    if header_match:
        result["uc_id"] = header_match.group(1)
        result["name"] = header_match.group(2).strip()

    # Parse metadata fields
    us_match = re.search(r"\*\*User Story\*\*:\s*(US-\d+)\s*(.*)", description)
    if us_match:
        result["us_id"] = us_match.group(1)
        result["us_name"] = us_match.group(2).strip()

    actor_match = re.search(r"\*\*Actor\*\*:\s*(.+)", description)
    if actor_match:
        result["actor"] = actor_match.group(1).strip()

    hours_match = re.search(r"\*\*Horas\*\*:\s*(\d+(?:\.\d+)?)", description)
    if hours_match:
        result["hours"] = float(hours_match.group(1))

    screens_match = re.search(r"\*\*Pantallas\*\*:\s*(.+)", description)
    if screens_match:
        raw = screens_match.group(1).strip()
        result["screens"] = [s.strip() for s in raw.split(",") if s.strip()]

    # Parse Acceptance Criteria
    ac_section = re.search(r"###\s*Criterios de Aceptacion\s*\n(.*?)(?=\n###|\Z)", description, re.DOTALL)
    if ac_section:
        ac_lines = ac_section.group(1).strip().split("\n")
        for line in ac_lines:
            ac_match = re.match(r"-\s*(AC-\d+):\s*(.+)", line.strip())
            if ac_match:
                result["acceptance_criteria"].append({
                    "id": ac_match.group(1),
                    "text": ac_match.group(2).strip(),
                })

    # Parse Context
    ctx_section = re.search(r"###\s*Contexto\s*\n(.*?)(?=\n###|\Z)", description, re.DOTALL)
    if ctx_section:
        result["context"] = ctx_section.group(1).strip()

    # Parse Notes
    notes_section = re.search(r"###\s*Notas\s*\n(.*?)(?=\n###|\Z)", description, re.DOTALL)
    if notes_section:
        result["notes"] = notes_section.group(1).strip()

    return result


def build_us_description(us_id: str, name: str, hours: float, screens: str, description: str = "") -> str:
    """Generate markdown description for a US card."""
    lines = [
        f"## {us_id}: {name}",
        "",
        f"**Horas**: {hours}",
        f"**Pantallas**: {screens}",
    ]
    if description:
        lines.extend(["", "### Descripcion", "", description])
    return "\n".join(lines)


def build_uc_description(
    uc_id: str,
    name: str,
    us_id: str,
    us_name: str,
    actor: str,
    hours: float,
    screens: str,
    acceptance_criteria: list[str],
    context: str = "",
) -> str:
    """Generate parseable markdown description for a UC card."""
    lines = [
        f"## {uc_id}: {name}",
        "",
        f"**User Story**: {us_id} {us_name}",
        f"**Actor**: {actor}",
        f"**Horas**: {hours}",
        f"**Pantallas**: {screens}",
        "",
        "### Criterios de Aceptacion",
    ]

    for i, ac_text in enumerate(acceptance_criteria, 1):
        ac_id = f"AC-{i:02d}"
        lines.append(f"- {ac_id}: {ac_text}")

    if context:
        lines.extend(["", "### Contexto", "", context])

    lines.extend(["", "### Notas", "", "[Notas adicionales]"])
    return "\n".join(lines)


def parse_checklist_acs(checklists: list[dict]) -> list[AcceptanceCriterion]:
    """Parse acceptance criteria from card checklists."""
    criteria: list[AcceptanceCriterion] = []
    for cl in checklists:
        if "aceptacion" in cl.get("name", "").lower() or "acceptance" in cl.get("name", "").lower():
            for item in cl.get("checkItems", []):
                name = item.get("name", "")
                ac_match = re.match(r"(AC-\d+):\s*(.+)", name)
                if ac_match:
                    criteria.append(AcceptanceCriterion(
                        id=ac_match.group(1),
                        text=ac_match.group(2).strip(),
                        done=item.get("state") == "complete",
                    ))
                else:
                    criteria.append(AcceptanceCriterion(
                        id=f"AC-{len(criteria) + 1:02d}",
                        text=name,
                        done=item.get("state") == "complete",
                    ))
    return criteria


def find_option_id(custom_fields: list[dict], field_name: str, option_text: str) -> str | None:
    """Find the option ID for a list-type custom field."""
    for cf in custom_fields:
        if cf.get("name", "").lower() == field_name.lower() and cf.get("type") == "list":
            for opt in cf.get("options", []):
                if opt.get("value", {}).get("text", "") == option_text:
                    return opt["id"]
    return None
