"""Trello backend — thin adapter wrapping TrelloClient + board_helpers into SpecBackend."""

from __future__ import annotations

from typing import Any

import structlog

from ..board_helpers import (
    build_custom_field_map,
    find_card_by_custom_field,
    find_option_id,
    get_card_custom_value,
    get_list_id_for_state,
    get_state_for_list,
    get_us_children,
    is_us_card,
    parse_checklist_acs,
)
from ..models import (
    ACTOR_OPTIONS,
    CARD_TYPE_OPTIONS,
    CUSTOM_FIELD_NAMES,
    LIST_NAME_TO_STATE,
    WORKFLOW_LIST_NAMES,
    WorkflowState,
)
from ..spec_backend import (
    AttachmentDTO,
    BackendUser,
    BoardConfig,
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
    ModuleDTO,
    SpecBackend,
    parse_item_id,
)
from ..trello_client import TrelloClient

logger = structlog.get_logger(__name__)

# Custom field definitions used by setup_board
_CUSTOM_FIELD_DEFS: list[dict[str, Any]] = [
    {"name": "tipo", "type": "list", "options": CARD_TYPE_OPTIONS},
    {"name": "us_id", "type": "text"},
    {"name": "uc_id", "type": "text"},
    {"name": "horas", "type": "number"},
    {"name": "pantallas", "type": "text"},
    {"name": "actor", "type": "list", "options": ACTOR_OPTIONS},
]

# Labels created by setup_board
_LABEL_DEFS: list[tuple[str, str]] = [
    ("US", "blue"),
    ("UC", "green"),
    ("Infra", "orange"),
    ("Bloqueado", "red"),
]


class TrelloBackend(SpecBackend):
    """SpecBackend implementation backed by Trello REST API."""

    def __init__(self, api_key: str, token: str) -> None:
        self.client = TrelloClient(api_key=api_key, token=token)

    # ── Auth ──────────────────────────────────────────────────────

    async def validate_auth(self) -> BackendUser:
        me = await self.client.get_me()
        return BackendUser(
            id=me["id"],
            username=me.get("username", ""),
            display_name=me.get("fullName", me.get("username", "")),
        )

    # ── Board / Project Setup ────────────────────────────────────

    async def setup_board(self, name: str) -> BoardConfig:
        board = await self.client.create_board(name, default_lists=False)
        board_id = board["id"]
        board_url = board.get("url", "")

        # Create 5 workflow lists
        states: dict[str, str] = {}
        for state_key in WORKFLOW_LIST_NAMES:
            list_name = WORKFLOW_LIST_NAMES[state_key]
            lst = await self.client.create_list(board_id, list_name)
            states[state_key] = lst["id"]

        # Create 6 custom fields
        custom_fields: dict[str, str] = {}
        for cf_def in _CUSTOM_FIELD_DEFS:
            cf = await self.client.create_custom_field(
                board_id,
                cf_def["name"],
                cf_def["type"],
                options=cf_def.get("options"),
            )
            custom_fields[cf_def["name"]] = cf["id"]

        # Create 4 labels
        labels: dict[str, str] = {}
        for label_name, label_color in _LABEL_DEFS:
            lbl = await self.client.create_label(board_id, label_name, label_color)
            labels[label_name] = lbl["id"]

        logger.info(
            "trello_board_setup",
            board_id=board_id,
            lists=len(states),
            custom_fields=len(custom_fields),
            labels=len(labels),
        )

        return BoardConfig(
            board_id=board_id,
            board_url=board_url,
            states=states,
            labels=labels,
            custom_fields=custom_fields,
        )

    async def get_board_name(self, board_id: str) -> str:
        board = await self.client.get_board(board_id)
        return board.get("name", "")

    # ── Internal helpers ─────────────────────────────────────────

    async def _fetch_board_context(
        self, board_id: str
    ) -> tuple[list[dict], list[dict], dict[str, dict]]:
        """Fetch lists, custom_fields, and cf_map for a board."""
        lists = await self.client.get_board_lists(board_id)
        custom_fields = await self.client.get_board_custom_fields(board_id)
        cf_map = build_custom_field_map(custom_fields)
        return lists, custom_fields, cf_map

    def _card_to_item(
        self,
        card: dict,
        lists: list[dict],
        custom_fields: list[dict],
        cf_map: dict[str, dict],
        us_id_to_card_id: dict[str, str] | None = None,
    ) -> ItemDTO:
        """Convert a raw Trello card dict into an ItemDTO."""
        meta: dict[str, Any] = {}
        for field_name in CUSTOM_FIELD_NAMES:
            val = get_card_custom_value(card, field_name, cf_map, custom_fields)
            if val is not None:
                meta[field_name] = val

        # Derive parent_id: for UC cards, resolve from us_id lookup table
        parent_id: str | None = None
        tipo = meta.get("tipo")
        if tipo == "UC" and meta.get("us_id") and us_id_to_card_id:
            parent_id = us_id_to_card_id.get(str(meta["us_id"]))

        return ItemDTO(
            id=card["id"],
            name=card.get("name", ""),
            description=card.get("desc", ""),
            state=get_state_for_list(card.get("idList", ""), lists),
            state_id=card.get("idList", ""),
            parent_id=parent_id,
            labels=[label["name"] for label in card.get("labels", [])],
            label_ids=[label["id"] for label in card.get("labels", [])],
            url=card.get("url", ""),
            meta=meta,
            raw=card,
        )

    async def _resolve_label_ids(
        self, board_id: str, label_names: list[str]
    ) -> list[str]:
        """Resolve label names to Trello label IDs."""
        board_labels = await self.client.get_board_labels(board_id)
        name_to_id = {lbl["name"]: lbl["id"] for lbl in board_labels if lbl.get("name")}
        resolved: list[str] = []
        for name in label_names:
            lid = name_to_id.get(name)
            if lid:
                resolved.append(lid)
            else:
                logger.warning("trello_label_not_found", label=name, board_id=board_id)
        return resolved

    async def _set_custom_fields(
        self,
        card_id: str,
        board_id: str,
        meta: dict[str, Any],
        custom_fields: list[dict] | None = None,
        cf_map: dict[str, dict] | None = None,
    ) -> None:
        """Set custom field values on a card from a meta dict."""
        if not meta:
            return
        if custom_fields is None or cf_map is None:
            _, custom_fields, cf_map = await self._fetch_board_context(board_id)

        for field_name, value in meta.items():
            cf_info = cf_map.get(field_name.lower())
            if not cf_info:
                continue

            field_id = cf_info["id"]
            field_type = cf_info["type"]

            if field_type == "text":
                await self.client.set_custom_field_value(
                    card_id, field_id, {"value": {"text": str(value)}}
                )
            elif field_type == "number":
                await self.client.set_custom_field_value(
                    card_id, field_id, {"value": {"number": str(value)}}
                )
            elif field_type == "list":
                option_id = find_option_id(custom_fields, field_name, str(value))
                if option_id:
                    await self.client.set_custom_field_value(
                        card_id, field_id, {"idValue": option_id}
                    )
                else:
                    logger.warning(
                        "trello_option_not_found",
                        field=field_name,
                        value=value,
                    )

    # ── Items (CRUD) ─────────────────────────────────────────────

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        cards = await self.client.get_board_cards(board_id)
        lists, custom_fields, cf_map = await self._fetch_board_context(board_id)

        # Build US-ID -> card-ID lookup for parent resolution
        us_id_to_card_id: dict[str, str] = {}
        for c in cards:
            if is_us_card(c, cf_map, custom_fields):
                us_id_val = get_card_custom_value(c, "us_id", cf_map, custom_fields)
                if us_id_val:
                    us_id_to_card_id[str(us_id_val)] = c["id"]

        return [
            self._card_to_item(card, lists, custom_fields, cf_map, us_id_to_card_id)
            for card in cards
        ]

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        card = await self.client.get_card(item_id)
        lists, custom_fields, cf_map = await self._fetch_board_context(board_id)
        return self._card_to_item(card, lists, custom_fields, cf_map)

    async def create_item(
        self,
        board_id: str,
        name: str,
        description: str = "",
        state: str = "backlog",
        labels: list[str] | None = None,
        parent_id: str | None = None,
        priority: str = "none",
        external_source: str = "",
        external_id: str = "",
        meta: dict[str, Any] | None = None,
    ) -> ItemDTO:
        # Resolve state to list ID
        list_id = await get_list_id_for_state(
            self.client, board_id, state  # type: ignore[arg-type]
        )

        # Resolve labels
        label_ids: list[str] | None = None
        if labels:
            label_ids = await self._resolve_label_ids(board_id, labels)

        # Create the card
        card = await self.client.create_card(
            list_id=list_id,
            name=name,
            desc=description,
            label_ids=label_ids,
        )

        # Set custom fields from meta
        if meta:
            await self._set_custom_fields(card["id"], board_id, meta)

        # Return full item
        return await self.get_item(board_id, card["id"])

    async def update_item(
        self,
        board_id: str,
        item_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
        priority: str | None = None,
        external_source: str | None = None,
        external_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ItemDTO:
        # Update basic card fields
        update_params: dict[str, Any] = {}
        if name is not None:
            update_params["name"] = name
        if description is not None:
            update_params["desc"] = description

        if update_params:
            await self.client.update_card(item_id, **update_params)

        # Move to new list if state changed
        if state is not None:
            new_list_id = await get_list_id_for_state(
                self.client, board_id, state  # type: ignore[arg-type]
            )
            await self.client.move_card(item_id, new_list_id)

        # Update labels
        if labels is not None:
            label_ids = await self._resolve_label_ids(board_id, labels)
            # Trello requires adding labels individually; first get current
            current_card = await self.client.get_card(item_id)
            current_label_ids = {lbl["id"] for lbl in current_card.get("labels", [])}
            for lid in label_ids:
                if lid not in current_label_ids:
                    await self.client.add_label_to_card(item_id, lid)

        # Update custom fields
        if meta:
            await self._set_custom_fields(item_id, board_id, meta)

        return await self.get_item(board_id, item_id)

    async def find_item_by_field(
        self, board_id: str, field_name: str, value: str
    ) -> ItemDTO | None:
        card = await find_card_by_custom_field(
            self.client, board_id, field_name, value
        )
        if card is None:
            return None
        lists, custom_fields, cf_map = await self._fetch_board_context(board_id)
        return self._card_to_item(card, lists, custom_fields, cf_map)

    async def get_item_children(
        self, board_id: str, parent_id: str
    ) -> list[ItemDTO]:
        """Get children of a parent item.

        For US parents: returns UC cards whose us_id custom field matches.
        For UC parents: returns empty list (ACs are checklist items, use
        get_acceptance_criteria instead).
        """
        # Determine parent tipo
        parent_card = await self.client.get_card(parent_id)
        _, custom_fields, cf_map = await self._fetch_board_context(board_id)
        parent_tipo = get_card_custom_value(
            parent_card, "tipo", cf_map, custom_fields
        )

        if parent_tipo == "US":
            # Find the us_id value (e.g. "US-01")
            us_id_val = get_card_custom_value(
                parent_card, "us_id", cf_map, custom_fields
            )
            if not us_id_val:
                # Fallback: parse from card name
                us_id_val, _ = parse_item_id(parent_card.get("name", ""), "US")
            if not us_id_val:
                return []

            child_cards = await get_us_children(self.client, board_id, us_id_val)
            lists = await self.client.get_board_lists(board_id)
            return [
                self._card_to_item(c, lists, custom_fields, cf_map)
                for c in child_cards
            ]

        # UC or other types: no card-level children in Trello
        return []

    # ── Acceptance Criteria ──────────────────────────────────────

    async def get_acceptance_criteria(
        self, board_id: str, uc_item_id: str
    ) -> list[ChecklistItemDTO]:
        checklists = await self.client.get_card_checklists(uc_item_id)
        parsed = parse_checklist_acs(checklists)
        result: list[ChecklistItemDTO] = []
        for ac in parsed:
            # Find the backend checkitem ID
            backend_id = self._find_checkitem_id(checklists, ac.id, ac.text)
            result.append(
                ChecklistItemDTO(
                    id=ac.id,
                    text=ac.text,
                    done=ac.done,
                    backend_id=backend_id,
                )
            )
        return result

    @staticmethod
    def _find_checkitem_id(
        checklists: list[dict], ac_id: str, ac_text: str
    ) -> str:
        """Find the Trello checkItem ID matching an AC."""
        for cl in checklists:
            cl_name = cl.get("name", "").lower()
            if "aceptacion" not in cl_name and "acceptance" not in cl_name:
                continue
            for item in cl.get("checkItems", []):
                item_name = item.get("name", "")
                if item_name.startswith(f"{ac_id}:") or item_name.startswith(f"{ac_id} "):
                    return item.get("id", "")
                if ac_text and ac_text in item_name:
                    return item.get("id", "")
        return ""

    async def mark_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        passed: bool,
    ) -> ChecklistItemDTO:
        checklists = await self.client.get_card_checklists(uc_item_id)
        parsed = parse_checklist_acs(checklists)

        # Find the matching AC
        target_ac = None
        for ac in parsed:
            if ac.id == ac_id:
                target_ac = ac
                break

        if target_ac is None:
            raise ValueError(f"AC '{ac_id}' not found on card {uc_item_id}")

        checkitem_id = self._find_checkitem_id(checklists, ac_id, target_ac.text)
        if not checkitem_id:
            raise ValueError(
                f"Checklist item for '{ac_id}' not found on card {uc_item_id}"
            )

        state = "complete" if passed else "incomplete"
        await self.client.update_checklist_item(uc_item_id, checkitem_id, state=state)

        return ChecklistItemDTO(
            id=ac_id,
            text=target_ac.text,
            done=passed,
            backend_id=checkitem_id,
        )

    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        checklist = await self.client.create_checklist(
            uc_item_id, "Criterios de Aceptacion"
        )
        checklist_id = checklist["id"]

        result: list[ChecklistItemDTO] = []
        for ac_id, text in criteria:
            item = await self.client.add_checklist_item(
                checklist_id, f"{ac_id}: {text}"
            )
            result.append(
                ChecklistItemDTO(
                    id=ac_id,
                    text=text,
                    done=False,
                    backend_id=item.get("id", ""),
                )
            )
        return result

    # ── Comments ─────────────────────────────────────────────────

    async def add_comment(
        self, board_id: str, item_id: str, text: str
    ) -> CommentDTO:
        action = await self.client.add_comment(item_id, text)
        return CommentDTO(
            id=action.get("id", ""),
            text=text,
            created_at=action.get("date", ""),
            author=action.get("memberCreator", {}).get("username", ""),
        )

    async def get_comments(
        self, board_id: str, item_id: str
    ) -> list[CommentDTO]:
        actions = await self.client.get_card_actions(item_id, filter="commentCard")
        return [
            CommentDTO(
                id=a.get("id", ""),
                text=a.get("data", {}).get("text", ""),
                created_at=a.get("date", ""),
                author=a.get("memberCreator", {}).get("username", ""),
            )
            for a in actions
        ]

    # ── Attachments / Evidence ───────────────────────────────────

    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        att = await self.client.add_attachment(item_id, content, filename, mime_type)
        return AttachmentDTO(
            id=att.get("id", ""),
            name=att.get("name", filename),
            url=att.get("url", ""),
            size=att.get("bytes", 0),
            created_at=att.get("date", ""),
            mime_type=att.get("mimeType", mime_type),
        )

    async def get_attachments(
        self, board_id: str, item_id: str
    ) -> list[AttachmentDTO]:
        attachments = await self.client.get_card_attachments(item_id)
        return [
            AttachmentDTO(
                id=a.get("id", ""),
                name=a.get("name", ""),
                url=a.get("url", ""),
                size=a.get("bytes", 0),
                created_at=a.get("date", ""),
                mime_type=a.get("mimeType", ""),
            )
            for a in attachments
        ]

    # ── Modules (US grouping) ────────────────────────────────────

    async def create_module(
        self, board_id: str, name: str, description: str = ""
    ) -> ModuleDTO:
        """Create a 'Casos de Uso' checklist on the US card identified by *name*.

        In Trello, modules are represented as checklists on US cards.
        The *name* parameter is used to locate the US card by custom field us_id.
        """
        # Find US card by us_id matching the module name
        card = await find_card_by_custom_field(
            self.client, board_id, "us_id", name
        )
        if card is None:
            raise ValueError(
                f"US card with us_id='{name}' not found on board {board_id}"
            )

        checklist = await self.client.create_checklist(card["id"], "Casos de Uso")
        return ModuleDTO(
            id=checklist["id"],
            name="Casos de Uso",
            status="active",
            item_ids=[],
        )

    async def add_items_to_module(
        self, board_id: str, module_id: str, item_ids: list[str]
    ) -> None:
        """Add items as checklist entries in the module (checklist).

        Each item_id is a card ID; its name is fetched and added as a
        checklist item.
        """
        for item_id in item_ids:
            card = await self.client.get_card(item_id)
            card_name = card.get("name", item_id)
            await self.client.add_checklist_item(module_id, card_name)

    # ── Labels ───────────────────────────────────────────────────

    async def create_label(
        self, board_id: str, name: str, color: str
    ) -> dict[str, str]:
        lbl = await self.client.create_label(board_id, name, color)
        return {"name": name, "id": lbl["id"], "color": color}

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        labels = await self.client.get_board_labels(board_id)
        return [
            {
                "name": lbl.get("name", ""),
                "id": lbl.get("id", ""),
                "color": lbl.get("color", ""),
            }
            for lbl in labels
        ]

    # ── States ───────────────────────────────────────────────────

    async def get_state_id(self, board_id: str, state: str) -> str:
        return await get_list_id_for_state(
            self.client, board_id, state  # type: ignore[arg-type]
        )

    async def get_states(self, board_id: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for state_key in WORKFLOW_LIST_NAMES:
            try:
                list_id = await get_list_id_for_state(
                    self.client, board_id, state_key
                )
                result[state_key] = list_id
            except ValueError:
                logger.warning(
                    "trello_state_missing", state=state_key, board_id=board_id
                )
        return result

    # ── Cleanup ──────────────────────────────────────────────────

    async def close(self) -> None:
        await self.client.close()
