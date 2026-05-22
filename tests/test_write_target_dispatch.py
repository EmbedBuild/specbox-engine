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


# ═══════════════════════════════════════════════════════════════════════
# Best-effort isolation — partial failures don't break write_target
# ═══════════════════════════════════════════════════════════════════════


class _ModuleFlakyBackend(InMemoryBackend):
    """create_module raises — write_target must keep going (module is best-effort)."""

    async def create_module(self, board_id: str, name: str, description: str = "") -> ModuleDTO:
        raise RuntimeError("module backend unavailable")


async def test_write_target_module_error_does_not_break(source_data: dict[str, Any]) -> None:
    """writer.py:100-105 — a failing create_module only logs a warning.

    The whole write still succeeds, US/UC/AC counts are intact, no module is
    counted, and the failure is NOT accumulated in errors[] (module is
    best-effort, distinct from AC/comment failures which DO surface).
    """
    target = _ModuleFlakyBackend()

    result = await write_target(target, "board-b", source_data)

    assert result["migrated"]["us"] == 1
    assert result["migrated"]["uc"] == 2
    assert result["migrated"]["ac"] == 3
    assert result["migrated"]["modules"] == 0
    # Module failure is swallowed as a warning — never surfaced in errors[].
    assert result["errors"] == []


class _AcCreateFlakyBackend(InMemoryBackend):
    """create_acceptance_criteria raises — error must land in errors[]."""

    async def create_acceptance_criteria(
        self, board_id: str, uc_item_id: str, criteria: list[tuple[str, str]]
    ) -> list[ChecklistItemDTO]:
        raise RuntimeError("AC store down")


async def test_write_target_ac_create_error_accumulates(source_data: dict[str, Any]) -> None:
    """writer.py:166-171 — a failing create_acceptance_criteria is isolated per-UC.

    UCs are still created, AC count stays 0, and one error per UC-with-ACs is
    accumulated in errors[] tagged with the logical uc_id.
    """
    target = _AcCreateFlakyBackend()

    result = await write_target(target, "board-b", source_data)

    assert result["migrated"]["uc"] == 2
    assert result["migrated"]["ac"] == 0
    # Both UCs in source_data carry ACs → two accumulated errors.
    ac_errors = [e for e in result["errors"] if e.startswith("ACs for")]
    assert len(ac_errors) == 2
    assert any("UC-001" in e for e in ac_errors)
    assert any("UC-002" in e for e in ac_errors)


class _AcMarkFlakyBackend(InMemoryBackend):
    """mark_acceptance_criterion raises — best-effort, must be swallowed."""

    async def mark_acceptance_criterion(
        self, board_id: str, uc_item_id: str, ac_id: str, passed: bool
    ) -> ChecklistItemDTO:
        raise RuntimeError("cannot mark AC done")


async def test_write_target_ac_mark_error_swallowed(source_data: dict[str, Any]) -> None:
    """writer.py:163-164 — a failing mark_acceptance_criterion is best-effort.

    ACs are still created and counted; the done-state re-apply failure for the
    one done AC is swallowed and never surfaced in errors[].
    """
    target = _AcMarkFlakyBackend()

    result = await write_target(target, "board-b", source_data)

    # ACs were created (3 total) despite the mark failure on the done AC.
    assert result["migrated"]["ac"] == 3
    assert result["errors"] == []


class _CommentFlakyBackend(InMemoryBackend):
    """add_comment raises — error must land in errors[]."""

    async def add_comment(self, board_id: str, item_id: str, text: str) -> CommentDTO:
        raise RuntimeError("comment service offline")


async def test_write_target_comment_error_accumulates(source_data: dict[str, Any]) -> None:
    """writer.py:185-186 — a failing add_comment is isolated per-comment.

    US/UC/AC still migrate, comment count stays 0, and the failure is
    accumulated in errors[] tagged with the source item id.
    """
    target = _CommentFlakyBackend()

    result = await write_target(target, "board-b", source_data)

    assert result["migrated"]["us"] == 1
    assert result["migrated"]["comments"] == 0
    comment_errors = [e for e in result["errors"] if e.startswith("Comment on")]
    assert len(comment_errors) == 1
    assert "src-us-1" in comment_errors[0]


# ═══════════════════════════════════════════════════════════════════════
# Hierarchy fallback + orphan comment skip
# ═══════════════════════════════════════════════════════════════════════


async def test_write_target_parent_fallback_via_meta_us_id() -> None:
    """writer.py:124-128 — UC with empty parent_id resolves parent via meta['us_id'].

    The UC carries parent_id="" but meta['us_id']='US-01' pointing at a present
    US. The fallback loop must locate that US in classified['us'] and wire the
    migrated UC's parent_id to the migrated US.
    """
    us = ItemDTO(
        id="src-us-1",
        name="US-01: Cuenta",
        state="user_stories",
        labels=["US"],
        meta={"us_id": "US-01", "tipo": "us"},
    )
    # parent_id deliberately empty — hierarchy must be recovered from meta.
    uc = ItemDTO(
        id="src-uc-1",
        name="UC-001: Alta",
        state="backlog",
        labels=["UC"],
        parent_id="",
        meta={"us_id": "US-01", "uc_id": "UC-001"},
    )
    source = {
        "board_name": "B",
        "source_type": "plane",
        "items": [us, uc],
        "classified": {"us": [us], "uc": [uc], "ac": [], "other": []},
        "ac_data": {},
        "comments_data": {},
        "labels": [],
        "states": {},
    }

    target = InMemoryBackend()
    result = await write_target(target, "board-b", source)

    us_target_id = target.by_label("US")[0].id
    uc_target = target.by_label("UC")[0]
    # Fallback resolved the parent purely from meta['us_id'].
    assert uc_target.parent_id == us_target_id
    assert result["id_map"]["src-uc-1"] == uc_target.id


async def test_write_target_orphan_comment_is_skipped() -> None:
    """writer.py:177 — a comment whose source_item_id is not in id_map is skipped.

    The comments_data references an item id that was never migrated (no US/UC
    created it), so id_map.get(...) is None → continue. No comment is created
    and no error is raised.
    """
    us = ItemDTO(
        id="src-us-1",
        name="US-01: Cuenta",
        state="user_stories",
        labels=["US"],
        meta={"us_id": "US-01"},
    )
    source = {
        "board_name": "B",
        "source_type": "trello",
        "items": [us],
        "classified": {"us": [us], "uc": [], "ac": [], "other": []},
        "ac_data": {},
        # Comment points at an id that never makes it into id_map.
        "comments_data": {"src-ghost-99": [{"text": "huérfano", "created_at": "2026-01-01"}]},
        "labels": [],
        "states": {},
    }

    target = InMemoryBackend()
    result = await write_target(target, "board-b", source)

    assert result["migrated"]["comments"] == 0
    assert result["errors"] == []
    assert "src-ghost-99" not in result["id_map"]
