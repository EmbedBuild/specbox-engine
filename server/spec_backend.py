"""Abstract backend interface for spec-driven development.

SpecBackend defines the contract that both TrelloBackend and PlaneBackend
must implement. The 21 spec_driven tools call ONLY methods on this interface,
never Trello or Plane APIs directly.

This allows transparent backend switching per project via configuration.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── Lightweight DTOs (backend-agnostic) ──────────────────────────────


@dataclass
class BackendUser:
    """Authenticated user info."""

    id: str
    username: str
    display_name: str


@dataclass
class BoardConfig:
    """Result of setup_board: IDs for states, labels, etc."""

    board_id: str
    board_url: str
    states: dict[str, str]  # workflow_state -> state/list ID
    labels: dict[str, str]  # label_name -> label ID
    custom_fields: dict[str, str]  # field_name -> field ID (Trello only, empty for Plane)


@dataclass
class ItemDTO:
    """A work item (card in Trello, work item in Plane).

    Unified representation for US, UC, and AC across backends.
    """

    id: str
    name: str
    description: str = ""  # raw markdown (Trello) or HTML (Plane)
    state: str = ""  # workflow state key: user_stories, backlog, in_progress, review, done
    state_id: str = ""  # backend-specific state/list ID
    parent_id: str | None = None  # parent item ID (for UC->US, AC->UC)
    labels: list[str] = field(default_factory=list)  # label names
    label_ids: list[str] = field(default_factory=list)  # backend label IDs
    priority: str = "none"
    url: str = ""
    external_source: str = ""
    external_id: str = ""
    # Metadata extracted from custom fields or description
    meta: dict[str, Any] = field(default_factory=dict)
    # Raw backend-specific data (for advanced operations)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChecklistItemDTO:
    """An acceptance criterion (checklist item in Trello, sub-item in Plane)."""

    id: str
    text: str
    done: bool = False
    # In Plane, this is the work item ID; in Trello, the checkItem ID
    backend_id: str = ""


@dataclass
class CommentDTO:
    """A comment/activity entry."""

    id: str
    text: str  # raw text or HTML
    created_at: str = ""
    author: str = ""


@dataclass
class AttachmentDTO:
    """A file attachment or link."""

    id: str
    name: str
    url: str
    size: int = 0
    created_at: str = ""
    mime_type: str = ""


@dataclass
class ModuleDTO:
    """A module (groups UCs under a US)."""

    id: str
    name: str
    status: str = ""
    item_ids: list[str] = field(default_factory=list)


# ── Name parsing helpers ─────────────────────────────────────────────

_US_RE = re.compile(r"\[?(US-\d+)\]?\s*:?\s*(.*)")
_UC_RE = re.compile(r"\[?(UC-\d+)\]?\s*:?\s*(.*)")
_AC_RE = re.compile(r"\[?(AC-\d+)\]?\s*:?\s*(.*)")


def parse_item_id(name: str, prefix: str = "US") -> tuple[str, str]:
    """Extract item ID and clean name from formatted name.

    Supports both Trello format 'US-01: Name' and Plane format '[US-01] Name'.

    Returns:
        (item_id, clean_name) — e.g., ('US-01', 'Registro de usuario')
    """
    patterns = {"US": _US_RE, "UC": _UC_RE, "AC": _AC_RE}
    pattern = patterns.get(prefix)
    if pattern is None:
        return "", name
    match = pattern.match(name)
    if match:
        return match.group(1), match.group(2).strip()
    return "", name


# ── Abstract Backend ─────────────────────────────────────────────────


class SpecBackend(ABC):
    """Unified interface for project management backends (Trello, Plane, etc.).

    Every method maps to operations needed by the 21 spec_driven tools.
    Backend implementations handle API-specific details internally.
    """

    # ── Auth ──────────────────────────────────────────────────────

    @abstractmethod
    async def validate_auth(self) -> BackendUser:
        """Validate credentials and return user info."""

    # ── Board / Project Setup ────────────────────────────────────

    @abstractmethod
    async def setup_board(self, name: str) -> BoardConfig:
        """Create a new board/project with SpecBox Engine structure.

        Must create:
        - 5 workflow states/lists
        - Base labels (US, UC, AC, Infra, Bloqueado)
        - Custom fields (Trello) or equivalent (Plane: labels + name convention)
        """

    @abstractmethod
    async def get_board_name(self, board_id: str) -> str:
        """Get the board/project name."""

    # ── Items (CRUD) ─────────────────────────────────────────────

    @abstractmethod
    async def list_items(self, board_id: str) -> list[ItemDTO]:
        """List ALL items in the board/project.

        Must include: name, state, labels, parent_id, meta fields.
        This is the main data source — tools filter client-side.
        """

    @abstractmethod
    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        """Get a single item by its backend ID with full detail."""

    @abstractmethod
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
        """Create a new item (US, UC, or AC).

        Args:
            board_id: Board/project ID
            name: Item name (formatted: '[US-01] Name' for Plane, 'US-01: Name' for Trello)
            description: Markdown (Trello) or HTML (Plane)
            state: Workflow state key
            labels: Label names to apply
            parent_id: Parent item ID (for hierarchy)
            priority: Priority level
            external_source: Source system for migration tracking
            external_id: Source ID for migration tracking
            meta: Additional metadata (tipo, us_id, uc_id, horas, pantallas, actor)
        """

    @abstractmethod
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
        """Update an existing item. Only non-None fields are changed."""

    @abstractmethod
    async def find_item_by_field(
        self, board_id: str, field_name: str, value: str
    ) -> ItemDTO | None:
        """Find an item by a metadata field value (e.g., us_id='US-01').

        In Trello: searches custom fields.
        In Plane: searches name prefix or labels.
        """

    @abstractmethod
    async def get_item_children(
        self, board_id: str, parent_id: str
    ) -> list[ItemDTO]:
        """Get all direct children of an item.

        In Trello: finds items with matching us_id/uc_id custom field.
        In Plane: uses parent field natively.
        """

    # ── Acceptance Criteria ──────────────────────────────────────

    @abstractmethod
    async def get_acceptance_criteria(
        self, board_id: str, uc_item_id: str
    ) -> list[ChecklistItemDTO]:
        """Get acceptance criteria for a UC.

        In Trello: reads checklist 'Criterios de Aceptacion'.
        In Plane: reads child items with label 'AC'.
        """

    @abstractmethod
    async def mark_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        passed: bool,
    ) -> ChecklistItemDTO:
        """Mark a single AC as passed/failed.

        In Trello: updates checklist item state.
        In Plane: moves AC sub-item to Done/Backlog state.
        """

    @abstractmethod
    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        """Create ACs for a UC.

        Args:
            criteria: list of (ac_id, text) tuples, e.g. [('AC-01', 'Email validates')]

        In Trello: creates checklist items.
        In Plane: creates sub-work-items with label AC.
        """

    @abstractmethod
    async def update_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        *,
        text: str | None = None,
        done: bool | None = None,
    ) -> ChecklistItemDTO:
        """Rewrite an AC's text and/or change its done state.

        Only non-None fields are updated. Distinct from mark_acceptance_criterion
        which only toggles done.

        In Trello: renames the checklist item and/or updates its state.
        In Plane: updates the sub-work-item name and/or state.
        In FreeForm: updates items.json and regenerates the progress README.

        Raises ValueError if the AC is not found.
        """

    @abstractmethod
    async def delete_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
    ) -> None:
        """Remove an AC from a UC.

        Used by delete_ac to implement deletion + renumbering. Raises
        ValueError if the AC is not found.
        """

    # ── Archival ─────────────────────────────────────────────────

    @abstractmethod
    async def archive_item(
        self, board_id: str, item_id: str, *, reason: str,
    ) -> dict[str, Any]:
        """Archive an item without physical deletion.

        Each backend implements archival differently:
        - Trello: move card to "Archived" list (create if needed), or add
          "archived" label as fallback.
        - Plane: move work item to "Cancelled" state + add comment with reason.
        - FreeForm: move entry from items.json to archive.json.

        Returns: {"archive_location": str, "archived_at": str}
        """

    # ── Comments ─────────────────────────────────────────────────

    @abstractmethod
    async def add_comment(
        self, board_id: str, item_id: str, text: str
    ) -> CommentDTO:
        """Add a comment to an item."""

    @abstractmethod
    async def get_comments(
        self, board_id: str, item_id: str
    ) -> list[CommentDTO]:
        """Get all comments for an item."""

    # ── Attachments / Evidence ───────────────────────────────────

    @abstractmethod
    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        """Upload a file attachment to an item.

        In Trello: direct upload via /attachments.
        In Plane: link-based or S3 presigned URL.
        """

    @abstractmethod
    async def get_attachments(
        self, board_id: str, item_id: str
    ) -> list[AttachmentDTO]:
        """Get all attachments for an item."""

    # ── Modules (US grouping) ────────────────────────────────────

    @abstractmethod
    async def create_module(
        self, board_id: str, name: str, description: str = ""
    ) -> ModuleDTO:
        """Create a module to group UCs under a US.

        In Trello: creates a checklist 'Casos de Uso' on the US card.
        In Plane: creates a Module and adds UC items.
        """

    @abstractmethod
    async def add_items_to_module(
        self, board_id: str, module_id: str, item_ids: list[str]
    ) -> None:
        """Add items to a module.

        In Trello: adds checklist items to 'Casos de Uso'.
        In Plane: adds work items to module.
        """

    # ── Labels ───────────────────────────────────────────────────

    @abstractmethod
    async def create_label(
        self, board_id: str, name: str, color: str
    ) -> dict[str, str]:
        """Create a label. Returns {name, id, color}."""

    @abstractmethod
    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        """Get all labels for the board/project."""

    # ── States ───────────────────────────────────────────────────

    @abstractmethod
    async def get_state_id(self, board_id: str, state: str) -> str:
        """Get the backend-specific ID for a workflow state.

        In Trello: returns list ID for the state name.
        In Plane: returns state UUID.
        """

    @abstractmethod
    async def get_states(self, board_id: str) -> dict[str, str]:
        """Get mapping of workflow_state_key -> backend ID."""

    # ── Cleanup ──────────────────────────────────────────────────

    @abstractmethod
    async def close(self) -> None:
        """Release HTTP resources."""

    # ── Convenience (non-abstract) ───────────────────────────────

    async def find_us_items(self, board_id: str) -> list[ItemDTO]:
        """Find all US items. Default: filter list_items by label."""
        items = await self.list_items(board_id)
        return [i for i in items if "US" in i.labels]

    async def find_uc_items(
        self, board_id: str, us_id: str | None = None
    ) -> list[ItemDTO]:
        """Find all UC items, optionally filtered by parent US."""
        items = await self.list_items(board_id)
        ucs = [i for i in items if "UC" in i.labels]
        if us_id:
            ucs = [
                uc for uc in ucs
                if uc.meta.get("us_id") == us_id or self._parent_matches_us(uc, us_id, items)
            ]
        return ucs

    def _parent_matches_us(
        self, uc: ItemDTO, us_id: str, all_items: list[ItemDTO]
    ) -> bool:
        """Check if a UC's parent is the US with the given us_id."""
        if not uc.parent_id:
            return False
        parent = next((i for i in all_items if i.id == uc.parent_id), None)
        if not parent:
            return False
        parsed_id, _ = parse_item_id(parent.name, "US")
        return parsed_id == us_id


# ── Backend type registry ────────────────────────────────────────────

BackendType = str  # "trello" | "plane" | "freeform"
