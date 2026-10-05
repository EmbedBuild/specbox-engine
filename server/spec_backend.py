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
    # US-33/UC-3301: when true, this AC is internal — the business portal does
    # not show it to the stakeholder. Additive with a `False` default, so the
    # backends that have no such concept (Trello / Plane / FreeForm) keep
    # behaving exactly as before: every AC they return is client-facing.
    internal: bool = False
    # US-56/UC-5601: the receipts of this AC — each {type, label, link, detail,
    # by, at, passed} — and its last verdict {passed, by, at}. Only the Native
    # board stores them per AC; the other backends return them empty and
    # `get_uc` rebuilds them from the UC comments (server/ac_evidence.py).
    evidence: list[dict[str, Any]] = field(default_factory=list)
    verdict: dict[str, Any] | None = None


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


@dataclass
class EpicDTO:
    """An epic: groups user stories (US-78 / UC-7801, decision D20).

    Each story belongs to one epic or to none; the story carries the link
    (``meta["epic_id"]`` on its ItemDTO). State and progress are not stored:
    :mod:`server.epics` derives them from the epic's stories.
    """

    id: str  # EP-NN, unique within the project
    name: str
    objective: str = ""
    link: str = ""  # its PRD or discovery
    position: int = 0
    target_date: str | None = None  # YYYY-MM-DD
    created_at: str = ""
    updated_at: str = ""


#: An epic id: ``EP-`` and a number (EP-01, EP-12, EP-100).
EPIC_ID_RE = re.compile(r"^EP-\d+$")


class EpicError(Exception):
    """An epic operation refused with a stable ``code`` (US-78 / UC-7801)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


EPICS_NOT_SUPPORTED = "EPICS_NOT_SUPPORTED"
EPIC_EXISTS = "EPIC_EXISTS"
EPIC_NOT_FOUND = "EPIC_NOT_FOUND"
EPIC_INVALID = "EPIC_INVALID"


def next_epic_id(existing: list[str]) -> str:
    """The next free EP-NN after the highest one in use (EP-01 for an empty board)."""
    numbers = [int(e[3:]) for e in existing if EPIC_ID_RE.match(e)]
    return f"EP-{(max(numbers) + 1 if numbers else 1):02d}"


def validate_epic_fields(
    *, epic_id: str | None = None, name: str | None = None, target_date: str | None = None
) -> None:
    """Raise :class:`EpicError` (``EPIC_INVALID``) for a malformed id, an empty name or a bad date.

    ``target_date`` may be ``""`` (clear it) or ``YYYY-MM-DD``.
    """
    from datetime import date

    if epic_id is not None and not EPIC_ID_RE.match(epic_id):
        raise EpicError(EPIC_INVALID, f"Epic id {epic_id!r} must look like EP-01.")
    if name is not None and not name.strip():
        raise EpicError(EPIC_INVALID, "An epic needs a name.")
    if target_date:
        try:
            date.fromisoformat(target_date)
        except ValueError as exc:
            raise EpicError(EPIC_INVALID, f"target_date {target_date!r} must be YYYY-MM-DD.") from exc


# ── Name parsing helpers ─────────────────────────────────────────────

# UC-707 bug C: accept an optional single-letter suffix on the numeric id
# (e.g. "[UC-004b]") so a split/derived item keeps its full logical id instead
# of collapsing to "UC-004". The suffix is captured as part of group 1.
_US_RE = re.compile(r"\[?(US-\d+[a-zA-Z]?)\]?\s*:?\s*(.*)")
_UC_RE = re.compile(r"\[?(UC-\d+[a-zA-Z]?)\]?\s*:?\s*(.*)")
_AC_RE = re.compile(r"\[?(AC-\d+[a-zA-Z]?)\]?\s*:?\s*(.*)")


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


# ── Real deletion of a UC that never had work (US-55 / UC-5501) ──────

#: States from which a UC can be deleted for real: never started, or archived.
PURGEABLE_UC_STATES = frozenset({"backlog", "archived"})

PURGE_NOT_SUPPORTED = "PURGE_NOT_SUPPORTED"
PURGE_UC_STATE = "PURGE_UC_STATE"
PURGE_UC_HAS_DONE_AC = "PURGE_UC_HAS_DONE_AC"
PURGE_UC_HAS_EVIDENCE = "PURGE_UC_HAS_EVIDENCE"
PURGE_UC_RESERVED = "PURGE_UC_RESERVED"


class PurgeRefused(Exception):
    """A UC cannot be deleted for real; ``code`` says why (``PURGE_*``).

    The caller keeps today's behaviour: the UC is archived, never lost.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def purge_refusal(
    uc_id: str,
    *,
    state: str,
    done_ac_ids: list[str],
    has_evidence: bool,
    reserved_by: str | None,
) -> PurgeRefused | None:
    """Why a UC cannot be deleted for real, or None when it can (UC-5501 AC-02).

    Real deletion is only for a UC that never had work: in backlog or archived,
    no AC done, no evidence attached and nobody holding a reservation on it.
    """
    if state not in PURGEABLE_UC_STATES:
        return PurgeRefused(
            PURGE_UC_STATE,
            f"{uc_id} is in '{state}': only a UC in backlog or archived can be deleted for real.",
        )
    if done_ac_ids:
        return PurgeRefused(
            PURGE_UC_HAS_DONE_AC,
            f"{uc_id} has {len(done_ac_ids)} AC done ({', '.join(done_ac_ids)}): it had work.",
        )
    if has_evidence:
        return PurgeRefused(
            PURGE_UC_HAS_EVIDENCE,
            f"{uc_id} has evidence attached (to the UC or to one of its AC): it had work.",
        )
    if reserved_by:
        return PurgeRefused(
            PURGE_UC_RESERVED,
            f"{uc_id} is reserved by {reserved_by}: release it first.",
        )
    return None


#: An AC carries evidence when set_ac_metadata wrote its JSON suffix into the text.
AC_METADATA_MARK = "[META:"


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

    async def get_uc_acceptance(self, board_id: str, uc_item_id: str) -> dict[str, Any] | None:
        """La aceptación humana de una UC (US-76), o None si no la tiene.

        Una persona owner o admin del proyecto la da desde el panel, nunca un agente por MCP: el
        engine solo la lee. Devuelve ``{by, by_id, at}`` (nombre de quien aceptó, su developer_id
        y la fecha ISO). Solo el backend Native la guarda; Trello, Plane y FreeForm no tienen
        dónde y devuelven None.
        """
        return None

    @abstractmethod
    async def mark_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        passed: bool,
        evidence: dict[str, Any] | None = None,
    ) -> ChecklistItemDTO:
        """Mark a single AC as passed/failed.

        In Trello: updates checklist item state.
        In Plane: moves AC sub-item to Done/Backlog state.

        ``evidence`` (US-56/UC-5601) is the normalized receipt
        ``{type, label, link, detail}`` from `server.ac_evidence`. The Native
        board stores it with the AC, plus who marked it and when; Trello, Plane
        and FreeForm have nowhere to put it per AC and ignore it — the UC
        comment the tool writes is their record.
        """

    async def set_ac_internal(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        internal: bool,
    ) -> ChecklistItemDTO:
        """Mark/unmark an AC as internal (US-33/UC-3301).

        Deliberately **not** abstract: `internal` is a property of the Native
        board, which is what the business portal reads. Trello, Plane and
        FreeForm have no equivalent, and forcing them to grow a stub would be
        pretending they support something they don't.

        The default raises so a caller on those backends gets a precise reason
        instead of a silent no-op — the failure mode this whole US exists to
        avoid.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support internal ACs; "
            "this is a Native-board feature (US-33/UC-3301)."
        )

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

    async def purge_use_case(
        self, board_id: str, uc_item_id: str, *, reason: str,
    ) -> dict[str, Any]:
        """Delete a UC that never had work for real, with its ACs (US-55 / UC-5501).

        Only backends that own their storage implement it (Native, FreeForm);
        Trello and Plane keep archiving, so the default refuses with
        ``PURGE_NOT_SUPPORTED``. Implementations check :func:`purge_refusal`
        and raise :class:`PurgeRefused` without touching anything, or delete
        and return ``{"purged_at": str, "deleted": {what: count}, "snapshot":
        {"uc": {...}, "acceptance_criteria": [...]}}``.

        Raises ValueError if the UC is not found.
        """
        raise PurgeRefused(
            PURGE_NOT_SUPPORTED,
            f"{type(self).__name__} cannot delete for real: the UC is archived instead.",
        )

    # ── Epics (US-78 / UC-7801) ──────────────────────────────────
    #
    # Not abstract: epics live in the boards SpecBox owns (Native and
    # FreeForm). Trello and Plane list none and refuse to write, so a reader
    # on those backends sees "no epics" and a writer gets a precise reason
    # (decision D20: they are added only if someone asks).

    async def list_epics(self, board_id: str) -> list[EpicDTO]:
        """All epics of the board, ordered by ``position`` and then id."""
        return []

    async def create_epic(
        self,
        board_id: str,
        *,
        name: str,
        objective: str = "",
        link: str = "",
        position: int | None = None,
        target_date: str | None = None,
        epic_id: str | None = None,
    ) -> EpicDTO:
        """Create an epic. Without ``epic_id`` it takes the next free EP-NN.

        ``position`` defaults to the end of the list. Raises :class:`EpicError`
        (``EPIC_EXISTS`` if ``epic_id`` is taken, ``EPIC_INVALID`` for bad data).
        """
        raise EpicError(EPICS_NOT_SUPPORTED, f"{type(self).__name__} has no epics (D20: Native and FreeForm).")

    async def update_epic(
        self,
        board_id: str,
        epic_id: str,
        *,
        name: str | None = None,
        objective: str | None = None,
        link: str | None = None,
        position: int | None = None,
        target_date: str | None = None,
    ) -> EpicDTO:
        """Change the given fields; ``target_date=""`` clears the date."""
        raise EpicError(EPICS_NOT_SUPPORTED, f"{type(self).__name__} has no epics (D20: Native and FreeForm).")

    async def delete_epic(self, board_id: str, epic_id: str) -> dict[str, Any]:
        """Delete an epic; its stories stay, without epic.

        Returns ``{"epic": <EpicDTO as dict>, "detached_us": [us_id, ...]}``.
        """
        raise EpicError(EPICS_NOT_SUPPORTED, f"{type(self).__name__} has no epics (D20: Native and FreeForm).")

    async def set_us_epic(self, board_id: str, us_item_id: str, epic_id: str | None) -> ItemDTO:
        """Put a story in an epic (it leaves its previous one), or take it out with ``None``."""
        raise EpicError(EPICS_NOT_SUPPORTED, f"{type(self).__name__} has no epics (D20: Native and FreeForm).")

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
