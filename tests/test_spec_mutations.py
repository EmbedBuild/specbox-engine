"""Tool-level tests for Tier 1 mutation tools (v5.23.0).

Covers the 8 tools in server/tools/spec_mutations.py with an in-memory
backend implemented as a lightweight SpecBackend subclass. See
doc/design/v5.23.0-full-mutations.md → "Tier 1 test plan".
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.spec_backend import (
    AttachmentDTO,
    BackendUser,
    BoardConfig,
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
    ModuleDTO,
    SpecBackend,
)
from src.tools import spec_mutations as sm


# ── In-memory backend ────────────────────────────────────────────────


class InMemoryBackend(SpecBackend):
    """Minimal SpecBackend for testing tool logic.

    Stores items and ACs in dicts. Enough surface to drive Tier 1 tools.
    """

    def __init__(self):
        self.items: dict[str, ItemDTO] = {}
        self.acs: dict[str, list[ChecklistItemDTO]] = {}  # uc_item_id -> list
        self.comments: list[tuple[str, str]] = []  # (item_id, text)
        self.closed = False
        self._next_id = 1

    def _new_id(self, prefix: str = "id") -> str:
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    # Auth / board
    async def validate_auth(self) -> BackendUser:
        return BackendUser(id="u1", username="test", display_name="Test")

    async def setup_board(self, name):
        return BoardConfig(board_id="b1", board_url="", states={}, labels={}, custom_fields={})

    async def get_board_name(self, board_id):
        return "Test Board"

    # Items
    async def list_items(self, board_id):
        return list(self.items.values())

    async def get_item(self, board_id, item_id):
        return self.items[item_id]

    async def create_item(
        self,
        board_id,
        name,
        description="",
        state="backlog",
        labels=None,
        parent_id=None,
        priority="none",
        external_source="",
        external_id="",
        meta=None,
    ):
        item_id = self._new_id("item")
        item = ItemDTO(
            id=item_id,
            name=name,
            description=description,
            state=state,
            labels=list(labels or []),
            parent_id=parent_id,
            priority=priority,
            url=f"https://test/{item_id}",
            meta=dict(meta or {}),
        )
        self.items[item_id] = item
        return item

    async def update_item(
        self,
        board_id,
        item_id,
        *,
        name=None,
        description=None,
        state=None,
        labels=None,
        parent_id=None,
        priority=None,
        external_source=None,
        external_id=None,
        meta=None,
    ):
        item = self.items[item_id]
        if name is not None:
            item.name = name
        if description is not None:
            item.description = description
        if state is not None:
            item.state = state
        if labels is not None:
            item.labels = list(labels)
        if meta is not None:
            item.meta = dict(meta)
        return item

    async def find_item_by_field(self, board_id, field_name, value):
        for item in self.items.values():
            if item.meta.get(field_name) == value:
                return item
        return None

    async def get_item_children(self, board_id, parent_id):
        return [i for i in self.items.values() if i.parent_id == parent_id]

    # ACs
    async def get_acceptance_criteria(self, board_id, uc_item_id):
        return list(self.acs.get(uc_item_id, []))

    async def mark_acceptance_criterion(self, board_id, uc_item_id, ac_id, passed):
        for ac in self.acs.get(uc_item_id, []):
            if ac.id == ac_id:
                ac.done = passed
                return ac
        raise ValueError(f"AC {ac_id} not found")

    async def create_acceptance_criteria(self, board_id, uc_item_id, criteria):
        created: list[ChecklistItemDTO] = []
        for ac_id, text in criteria:
            cl = ChecklistItemDTO(
                id=ac_id, text=text, done=False, backend_id=self._new_id("ac")
            )
            self.acs.setdefault(uc_item_id, []).append(cl)
            created.append(cl)
        return created

    async def update_acceptance_criterion(
        self, board_id, uc_item_id, ac_id, *, text=None, done=None
    ):
        for ac in self.acs.get(uc_item_id, []):
            if ac.id == ac_id:
                if text is not None:
                    ac.text = text
                if done is not None:
                    ac.done = done
                return ac
        raise ValueError(f"AC {ac_id} not found")

    async def delete_acceptance_criterion(self, board_id, uc_item_id, ac_id):
        acs = self.acs.get(uc_item_id, [])
        for idx, ac in enumerate(acs):
            if ac.id == ac_id:
                acs.pop(idx)
                return
        raise ValueError(f"AC {ac_id} not found")

    # Comments / attachments / modules / labels / states — minimal stubs
    async def add_comment(self, board_id, item_id, text):
        self.comments.append((item_id, text))
        return CommentDTO(id=self._new_id("cmt"), text=text)

    async def get_comments(self, board_id, item_id):
        return []

    async def add_attachment(self, board_id, item_id, filename, content, mime_type="application/pdf"):
        return AttachmentDTO(id="a", name=filename, url="")

    async def get_attachments(self, board_id, item_id):
        return []

    async def create_module(self, board_id, name, description=""):
        return ModuleDTO(id="m", name=name)

    async def add_items_to_module(self, board_id, module_id, item_ids):
        return None

    async def create_label(self, board_id, name, color):
        return {"id": "l", "name": name, "color": color}

    async def get_labels(self, board_id):
        return []

    async def get_state_id(self, board_id, state):
        return state

    async def get_states(self, board_id):
        return {}

    async def close(self):
        self.closed = True


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def ctx(backend, monkeypatch):
    """Mock Context that resolves to our in-memory backend."""
    async def _fake_get_session_backend(_ctx):
        return backend

    monkeypatch.setattr(sm, "get_session_backend", _fake_get_session_backend)
    return AsyncMock()


async def _seed_us_uc(backend: InMemoryBackend, us_id="US-01", uc_id="UC-001"):
    us = await backend.create_item(
        "board",
        name=f"{us_id}: Auth",
        labels=["US"],
        meta={"us_id": us_id, "tipo": "US"},
    )
    uc = await backend.create_item(
        "board",
        name=f"{uc_id}: Login",
        description="Original desc",
        labels=["UC"],
        parent_id=us.id,
        meta={"uc_id": uc_id, "us_id": us_id, "tipo": "UC", "horas": 3.0},
    )
    await backend.create_acceptance_criteria(
        "board", uc.id, [("AC-01", "Valida email"), ("AC-02", "Muestra error")]
    )
    return us, uc


# ── update_uc ────────────────────────────────────────────────────────


async def test_update_uc_happy_path(backend, ctx):
    _, uc = await _seed_us_uc(backend)
    result = await sm.update_uc(
        "board", "UC-001", ctx, hours=5.0, milestone="H1", actor="Admin"
    )
    assert result.get("error") is None
    assert set(result["updated_fields"]) == {"horas", "milestone", "actor"}
    assert backend.items[uc.id].meta["horas"] == 5.0
    assert backend.items[uc.id].meta["milestone"] == "H1"
    assert backend.closed


async def test_update_uc_idempotent(backend, ctx):
    await _seed_us_uc(backend)
    # First call
    first = await sm.update_uc("board", "UC-001", ctx, hours=8.0, milestone="H2")
    assert "H2" not in (first.get("reason") or "")
    # Second call with same args → no_change
    second = await sm.update_uc("board", "UC-001", ctx, hours=8.0, milestone="H2")
    assert second["reason"] == "no_change"
    assert second["updated_fields"] == []


async def test_update_uc_not_found(backend, ctx):
    result = await sm.update_uc("board", "UC-999", ctx, hours=5.0)
    assert result["code"] == "UC_NOT_FOUND"


async def test_update_uc_invalid_milestone(backend, ctx):
    await _seed_us_uc(backend)
    result = await sm.update_uc("board", "UC-001", ctx, milestone="H9")
    assert result["code"] == "INVALID_MILESTONE"


# ── update_uc_batch ──────────────────────────────────────────────────


async def test_update_uc_batch_mixed_success(backend, ctx):
    await _seed_us_uc(backend, us_id="US-01", uc_id="UC-001")
    await _seed_us_uc(backend, us_id="US-02", uc_id="UC-002")
    updates = [
        {"uc_id": "UC-001", "milestone": "H1", "hours": 10.0},
        {"uc_id": "UC-999", "milestone": "H1"},  # not found
        {"uc_id": "UC-002", "milestone": "H2"},
    ]
    result = await sm.update_uc_batch("board", updates, ctx, stop_on_error=False)
    assert result["total"] == 3
    assert len(result["succeeded"]) == 2
    assert len(result["failed"]) == 1
    assert result["failed"][0]["code"] == "UC_NOT_FOUND"


async def test_update_uc_batch_calls_list_items_once(backend, ctx):
    await _seed_us_uc(backend, us_id="US-01", uc_id="UC-001")
    await _seed_us_uc(backend, us_id="US-02", uc_id="UC-002")

    # Wrap list_items to count calls
    original = backend.list_items
    call_count = {"n": 0}

    async def counting_list(board_id):
        call_count["n"] += 1
        return await original(board_id)

    backend.list_items = counting_list
    updates = [
        {"uc_id": "UC-001", "milestone": "H1"},
        {"uc_id": "UC-002", "milestone": "H2"},
    ]
    await sm.update_uc_batch("board", updates, ctx)
    assert call_count["n"] == 1  # AC-23: batch calls list_items at most once


# ── update_us ────────────────────────────────────────────────────────


async def test_update_us_propagates_milestone_only_to_unassigned(backend, ctx):
    us, uc1 = await _seed_us_uc(backend)  # UC-001 no milestone
    # Add UC-002 that already has a milestone → must NOT be overwritten
    uc2 = await backend.create_item(
        "board",
        name="UC-002: Registro",
        labels=["UC"],
        parent_id=us.id,
        meta={"uc_id": "UC-002", "us_id": "US-01", "milestone": "H4"},
    )
    result = await sm.update_us(
        "board", "US-01", ctx, milestone="H1", propagate_milestone=True
    )
    assert "UC-001" in result["propagated_to_ucs"]
    assert "UC-002" not in result["propagated_to_ucs"]
    assert backend.items[uc1.id].meta["milestone"] == "H1"
    assert backend.items[uc2.id].meta["milestone"] == "H4"  # preserved


# ── update_ac ────────────────────────────────────────────────────────


async def test_update_ac_preserves_done_when_omitted(backend, ctx):
    _, uc = await _seed_us_uc(backend)
    # Mark AC-01 as done first
    await backend.mark_acceptance_criterion("board", uc.id, "AC-01", True)
    # Rewrite text, don't pass done
    result = await sm.update_ac(
        "board", "UC-001", "AC-01", ctx, text="Valida email RFC 5322"
    )
    assert "text" in result["updated_fields"]
    assert "done" not in result["updated_fields"]
    ac = next(a for a in backend.acs[uc.id] if a.id == "AC-01")
    assert ac.done is True  # preserved


async def test_update_ac_not_found(backend, ctx):
    await _seed_us_uc(backend)
    result = await sm.update_ac("board", "UC-001", "AC-99", ctx, text="x")
    assert result["code"] == "AC_NOT_FOUND"


# ── add_ac ───────────────────────────────────────────────────────────


async def test_add_ac_auto_assigns_next_id(backend, ctx):
    _, uc = await _seed_us_uc(backend)  # has AC-01, AC-02
    result = await sm.add_ac("board", "UC-001", "Nuevo criterio", ctx)
    assert result["ac_id"] == "AC-03"
    acs = backend.acs[uc.id]
    assert any(a.id == "AC-03" for a in acs)


async def test_add_ac_empty_uc_gets_ac01(backend, ctx):
    us = await backend.create_item(
        "board", name="US-01: X", labels=["US"], meta={"us_id": "US-01"}
    )
    await backend.create_item(
        "board",
        name="UC-010: Empty",
        labels=["UC"],
        parent_id=us.id,
        meta={"uc_id": "UC-010", "us_id": "US-01"},
    )
    result = await sm.add_ac("board", "UC-010", "First", ctx)
    assert result["ac_id"] == "AC-01"


# ── delete_ac ────────────────────────────────────────────────────────


async def test_delete_ac_renumbers_remaining(backend, ctx):
    _, uc = await _seed_us_uc(backend)
    # Seed 5 ACs total
    await backend.create_acceptance_criteria(
        "board", uc.id, [("AC-03", "c"), ("AC-04", "d"), ("AC-05", "e")]
    )
    result = await sm.delete_ac("board", "UC-001", "AC-03", ctx, reason="obsoleto")
    assert result["deleted_ac_id"] == "AC-03"
    assert result["renumbered_acs"] == {"AC-04": "AC-03", "AC-05": "AC-04"}
    remaining_ids = sorted(a.id for a in backend.acs[uc.id])
    assert remaining_ids == ["AC-01", "AC-02", "AC-03", "AC-04"]
    # Comment logged
    assert any("AC-03 deleted" in c[1] for c in backend.comments)


# ── add_uc ───────────────────────────────────────────────────────────


async def test_add_uc_assigns_next_uc_id(backend, ctx):
    us = await backend.create_item(
        "board", name="US-01: Auth", labels=["US"], meta={"us_id": "US-01"}
    )
    # Seed UC-001..UC-027
    for i in range(1, 28):
        uc_id = f"UC-{i:03d}"
        await backend.create_item(
            "board",
            name=f"{uc_id}: seed",
            labels=["UC"],
            parent_id=us.id,
            meta={"uc_id": uc_id, "us_id": "US-01"},
        )
    result = await sm.add_uc(
        "board",
        "US-01",
        "New use case",
        "descr",
        ["Primer AC gherkin dado cuando entonces debe validar"],
        ctx,
        hours=4.0,
        milestone="H2",
    )
    assert result["uc_id"] == "UC-028"
    assert result["ac_count"] == 1
    # Validate stored meta
    new_item = next(
        i for i in backend.items.values() if i.meta.get("uc_id") == "UC-028"
    )
    assert new_item.meta["milestone"] == "H2"
    assert new_item.meta["horas"] == 4.0
