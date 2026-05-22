"""UC-401 tests: generic backend dispatch + write_target foundations.

Covers:
- AC-01: round-trip read A → write B preserves US/UC/AC counts + logical IDs.
- AC-02: build_backend accepts the 4 valid types; invalid raises ValueError
  naming all 4.
- AC-03: write_target is idempotent via logical us_id/uc_id — a second pass
  on a populated target creates 0 items and reports skipped > 0.
"""

from __future__ import annotations

from typing import Any

import pytest

from server.migration.backend_dispatch import VALID_BACKENDS, build_backend
from server.migration.writer import write_target
from server.spec_backend import (
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
    ModuleDTO,
    parse_item_id,
)


# ═══════════════════════════════════════════════════════════════════════
# AC-02 — Backend dispatch
# ═══════════════════════════════════════════════════════════════════════


class _Sentinel:
    """Stand-in returned by monkeypatched backend classes."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


@pytest.fixture
def _patch_backend_classes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the four backend classes so no real credentials are needed."""
    monkeypatch.setattr("server.backends.plane_backend.PlaneBackend", _Sentinel, raising=True)
    monkeypatch.setattr("server.backends.freeform_backend.FreeformBackend", _Sentinel, raising=True)
    monkeypatch.setattr("server.backends.native_backend.NativeBackend", _Sentinel, raising=True)
    monkeypatch.setattr("server.backends.trello_backend.TrelloBackend", _Sentinel, raising=True)


_CREDS_BY_TYPE: dict[str, dict[str, str]] = {
    "freeform": {"root_path": "/tmp/tracking"},
    "trello": {"api_key": "k", "token": "t"},
    "plane": {"base_url": "https://p", "api_key": "k", "workspace_slug": "ws"},
    "native": {"project_id": "proj-1"},
}


@pytest.mark.parametrize("backend_type", VALID_BACKENDS)
def test_build_backend_accepts_four_types(backend_type: str, _patch_backend_classes: None) -> None:
    """AC-02: each of the 4 valid types builds without error."""
    backend = build_backend(backend_type, _CREDS_BY_TYPE[backend_type])
    assert isinstance(backend, _Sentinel)


def test_build_backend_invalid_names_all_four() -> None:
    """AC-02: invalid backend_type raises ValueError naming all 4 valid types."""
    with pytest.raises(ValueError) as exc_info:
        build_backend("github", {})
    message = str(exc_info.value)
    for valid in VALID_BACKENDS:
        assert valid in message, f"{valid!r} missing from error: {message}"


def test_valid_backends_constant() -> None:
    assert set(VALID_BACKENDS) == {"freeform", "trello", "plane", "native"}


# ═══════════════════════════════════════════════════════════════════════
# In-memory backend (implements only what write_target uses)
# ═══════════════════════════════════════════════════════════════════════


class InMemoryBackend:
    """Stateful in-memory backend for round-trip / idempotency tests.

    Implements only the subset of the SpecBackend surface that ``write_target``
    and the round-trip read path exercise. Idempotency keys off the logical
    us_id / uc_id stored in each item's meta (matching find_item_by_field).
    """

    def __init__(self) -> None:
        self._items: dict[str, ItemDTO] = {}
        self._acs: dict[str, list[ChecklistItemDTO]] = {}
        self._comments: dict[str, list[CommentDTO]] = {}
        self._modules: dict[str, ModuleDTO] = {}
        self._counter = 0

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}-{self._counter}"

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
        item = ItemDTO(
            id=self._next_id("item"),
            name=name,
            description=description,
            state=state,
            parent_id=parent_id,
            labels=list(labels or []),
            priority=priority,
            external_source=external_source,
            external_id=external_id,
            meta=dict(meta or {}),
        )
        self._items[item.id] = item
        return item

    async def find_item_by_field(self, board_id: str, field_name: str, value: str) -> ItemDTO | None:
        # Match against the logical id parsed from the item name, which is how
        # the real backends resolve us_id / uc_id idempotency.
        prefix = "US" if field_name == "us_id" else "UC"
        for item in self._items.values():
            parsed, _ = parse_item_id(item.name, prefix)
            if parsed == value:
                return item
        return None

    async def create_acceptance_criteria(
        self, board_id: str, uc_item_id: str, criteria: list[tuple[str, str]]
    ) -> list[ChecklistItemDTO]:
        created = [ChecklistItemDTO(id=ac_id, text=text, done=False, backend_id=ac_id) for ac_id, text in criteria]
        self._acs.setdefault(uc_item_id, []).extend(created)
        return created

    async def mark_acceptance_criterion(
        self, board_id: str, uc_item_id: str, ac_id: str, passed: bool
    ) -> ChecklistItemDTO:
        for ac in self._acs.get(uc_item_id, []):
            if ac.id == ac_id:
                ac.done = passed
                return ac
        raise ValueError(f"AC {ac_id} not found")

    async def get_acceptance_criteria(self, board_id: str, uc_item_id: str) -> list[ChecklistItemDTO]:
        return list(self._acs.get(uc_item_id, []))

    async def create_module(self, board_id: str, name: str, description: str = "") -> ModuleDTO:
        module = ModuleDTO(id=self._next_id("module"), name=name)
        self._modules[module.id] = module
        return module

    async def add_comment(self, board_id: str, item_id: str, text: str) -> CommentDTO:
        comment = CommentDTO(id=self._next_id("comment"), text=text)
        self._comments.setdefault(item_id, []).append(comment)
        return comment

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        return list(self._items.values())

    async def get_comments(self, board_id: str, item_id: str) -> list[CommentDTO]:
        return list(self._comments.get(item_id, []))

    async def close(self) -> None:
        return None

    # Test helper (not part of the backend surface).
    def by_label(self, label: str) -> list[ItemDTO]:
        return [i for i in self._items.values() if label in i.labels]


# ═══════════════════════════════════════════════════════════════════════
# Fixtures: a source payload with 1 US, 2 UC, 3 AC (1 done)
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture
def source_data() -> dict[str, Any]:
    """Shape matching migration._read_source: 1 US, 2 UC, 3 AC (1 done)."""
    us = ItemDTO(
        id="src-us-1",
        name="US-01: Autenticación",
        description="As a user...",
        state="user_stories",
        labels=["US"],
        meta={"us_id": "US-01", "tipo": "us"},
    )
    uc1 = ItemDTO(
        id="src-uc-1",
        name="UC-001: Login",
        state="backlog",
        labels=["UC"],
        parent_id="src-us-1",
        meta={"us_id": "US-01", "uc_id": "UC-001", "actor": "Usuario"},
    )
    uc2 = ItemDTO(
        id="src-uc-2",
        name="UC-002: Logout",
        state="done",
        labels=["UC"],
        parent_id="src-us-1",
        meta={"us_id": "US-01", "uc_id": "UC-002"},
    )
    return {
        "board_name": "Source Board",
        "source_type": "trello",
        "items": [us, uc1, uc2],
        "classified": {"us": [us], "uc": [uc1, uc2], "ac": [], "other": []},
        "ac_data": {
            "src-uc-1": [
                {"id": "AC-01", "text": "valida email", "done": True, "backend_id": "AC-01"},
                {"id": "AC-02", "text": "rechaza pass corta", "done": False, "backend_id": "AC-02"},
            ],
            "src-uc-2": [
                {"id": "AC-01", "text": "limpia sesión", "done": False, "backend_id": "AC-01"},
            ],
        },
        "comments_data": {
            "src-us-1": [{"text": "spec firmado", "created_at": "2026-01-01", "author": "x"}],
        },
        "labels": [],
        "states": {},
    }


# ═══════════════════════════════════════════════════════════════════════
# AC-01 — Round-trip A → B preserves counts + logical IDs
# ═══════════════════════════════════════════════════════════════════════


async def test_write_target_round_trip_counts(source_data: dict[str, Any]) -> None:
    """AC-01: writing the source into a target reproduces US/UC/AC counts."""
    target = InMemoryBackend()

    result = await write_target(target, "board-b", source_data)

    assert result["migrated"]["us"] == 1
    assert result["migrated"]["uc"] == 2
    assert result["migrated"]["ac"] == 3
    assert result["migrated"]["comments"] == 1
    assert result["skipped"] == 0
    assert result["errors"] == []

    # Same number of US / UC items materialized in the target.
    assert len(target.by_label("US")) == 1
    assert len(target.by_label("UC")) == 2


async def test_write_target_preserves_logical_ids(source_data: dict[str, Any]) -> None:
    """AC-01: logical us_id/uc_id and parent→child hierarchy are preserved."""
    target = InMemoryBackend()
    result = await write_target(target, "board-b", source_data)

    us_items = target.by_label("US")
    uc_items = target.by_label("UC")

    us_target_id = us_items[0].id
    assert parse_item_id(us_items[0].name, "US")[0] == "US-01"

    uc_logical = {parse_item_id(uc.name, "UC")[0] for uc in uc_items}
    assert uc_logical == {"UC-001", "UC-002"}

    # Hierarchy: every UC's parent_id maps to the migrated US.
    for uc in uc_items:
        assert uc.parent_id == us_target_id

    # id_map links source ids to target ids.
    assert result["id_map"]["src-us-1"] == us_target_id


async def test_write_target_preserves_ac_done_state(source_data: dict[str, Any]) -> None:
    """AC-01: a done AC stays done after migration."""
    target = InMemoryBackend()
    await write_target(target, "board-b", source_data)

    uc1 = next(uc for uc in target.by_label("UC") if parse_item_id(uc.name, "UC")[0] == "UC-001")
    acs = await target.get_acceptance_criteria("board-b", uc1.id)
    done_map = {ac.id: ac.done for ac in acs}
    assert done_map["AC-01"] is True
    assert done_map["AC-02"] is False


async def test_write_target_state_passthrough(source_data: dict[str, Any]) -> None:
    """State is written as-is (translation is UC-402, not here)."""
    target = InMemoryBackend()
    await write_target(target, "board-b", source_data)

    uc2 = next(uc for uc in target.by_label("UC") if parse_item_id(uc.name, "UC")[0] == "UC-002")
    assert uc2.state == "done"


# ═══════════════════════════════════════════════════════════════════════
# AC-03 — Idempotency: double pass → 0 duplicates
# ═══════════════════════════════════════════════════════════════════════


async def test_write_target_idempotent_double_pass(source_data: dict[str, Any]) -> None:
    """AC-03: re-running write_target on a populated target duplicates nothing."""
    target = InMemoryBackend()

    first = await write_target(target, "board-b", source_data)
    assert first["migrated"]["us"] == 1
    assert first["migrated"]["uc"] == 2

    second = await write_target(target, "board-b", source_data)
    assert second["migrated"]["us"] == 0
    assert second["migrated"]["uc"] == 0
    assert second["skipped"] > 0

    # No duplication in the target.
    assert len(target.by_label("US")) == 1
    assert len(target.by_label("UC")) == 2
