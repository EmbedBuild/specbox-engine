"""Tier 3 tests — board_operations.py (v5.23.0).

See doc/design/v5.23.0-full-mutations.md → "Tier 3 test plan".
"""

from __future__ import annotations

import json
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
from src.tools import board_operations as bo


# ── In-memory backend ────────────────────────────────────────────────


class InMemoryBackend(SpecBackend):
    def __init__(self):
        self.items: dict[str, ItemDTO] = {}
        self.acs: dict[str, list[ChecklistItemDTO]] = {}
        self.comments: list[tuple[str, str]] = []
        self.archived: list[str] = []
        self.closed = False
        self._next_id = 1

    def _new_id(self, prefix="id"):
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    async def validate_auth(self):
        return BackendUser(id="u", username="t", display_name="T")

    async def setup_board(self, name):
        return BoardConfig(board_id="b", board_url="", states={}, labels={}, custom_fields={})

    async def get_board_name(self, board_id):
        return "B"

    async def list_items(self, board_id):
        return list(self.items.values())

    async def get_item(self, board_id, item_id):
        return self.items[item_id]

    async def create_item(self, board_id, name, description="", state="backlog",
                          labels=None, parent_id=None, priority="none",
                          external_source="", external_id="", meta=None):
        iid = self._new_id("item")
        item = ItemDTO(id=iid, name=name, description=description, state=state,
                       labels=list(labels or []), parent_id=parent_id, url=f"u/{iid}",
                       meta=dict(meta or {}))
        self.items[iid] = item
        return item

    async def update_item(self, board_id, item_id, *, name=None, description=None,
                          state=None, labels=None, parent_id=None, priority=None,
                          external_source=None, external_id=None, meta=None):
        item = self.items[item_id]
        if name is not None: item.name = name
        if description is not None: item.description = description
        if state is not None: item.state = state
        if labels is not None: item.labels = list(labels)
        if meta is not None: item.meta = dict(meta)
        return item

    async def find_item_by_field(self, board_id, field_name, value):
        for i in self.items.values():
            if i.meta.get(field_name) == value:
                return i
        return None

    async def get_item_children(self, board_id, parent_id):
        return [i for i in self.items.values() if i.parent_id == parent_id]

    async def get_acceptance_criteria(self, board_id, uc_item_id):
        return list(self.acs.get(uc_item_id, []))

    async def mark_acceptance_criterion(self, board_id, uc_item_id, ac_id, passed):
        for ac in self.acs.get(uc_item_id, []):
            if ac.id == ac_id:
                ac.done = passed
                return ac
        raise ValueError()

    async def create_acceptance_criteria(self, board_id, uc_item_id, criteria):
        created = []
        for ac_id, text in criteria:
            cl = ChecklistItemDTO(id=ac_id, text=text, done=False, backend_id=self._new_id("ac"))
            self.acs.setdefault(uc_item_id, []).append(cl)
            created.append(cl)
        return created

    async def update_acceptance_criterion(self, board_id, uc_item_id, ac_id, *, text=None, done=None):
        for ac in self.acs.get(uc_item_id, []):
            if ac.id == ac_id:
                if text is not None: ac.text = text
                if done is not None: ac.done = done
                return ac
        raise ValueError()

    async def delete_acceptance_criterion(self, board_id, uc_item_id, ac_id):
        acs = self.acs.get(uc_item_id, [])
        for idx, ac in enumerate(acs):
            if ac.id == ac_id:
                acs.pop(idx)
                return
        raise ValueError()

    async def archive_item(self, board_id, item_id, *, reason):
        self.archived.append(item_id)
        if item_id in self.items:
            del self.items[item_id]
        from src.tools._mutation_helpers import utc_now_iso
        return {"archive_location": "test_archive", "archived_at": utc_now_iso()}

    async def add_comment(self, board_id, item_id, text):
        self.comments.append((item_id, text))
        return CommentDTO(id=self._new_id("c"), text=text)

    async def get_comments(self, *a):
        return []

    async def add_attachment(self, *a, **kw):
        return AttachmentDTO(id="a", name="f", url="")

    async def get_attachments(self, *a):
        return []

    async def create_module(self, board_id, name, description=""):
        return ModuleDTO(id="m", name=name)

    async def add_items_to_module(self, *a):
        return None

    async def create_label(self, board_id, name, color):
        return {"id": "l", "name": name, "color": color}

    async def get_labels(self, *a):
        return []

    async def get_state_id(self, board_id, state):
        return state

    async def get_states(self, *a):
        return {}

    async def close(self):
        self.closed = True


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def ctx(backend, monkeypatch):
    async def _fake(c):
        return backend
    monkeypatch.setattr(bo, "get_session_backend", _fake)
    return AsyncMock()


async def _seed(backend, n_ucs=3):
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    ucs = []
    for i in range(1, n_ucs + 1):
        uc_id = f"UC-{i:03d}"
        uc = await backend.create_item(
            "b", f"{uc_id}: F{i}", labels=["UC"], parent_id=us.id,
            meta={"uc_id": uc_id, "us_id": "US-01"},
        )
        ac_pairs = [
            (f"AC-{j:02d}", [
                f"Dado un usuario autenticado cuando ejecuta accion {j} entonces debe ver resultado correcto",
                f"El sistema debe responder en menos de 200ms para la operacion {j} del caso de uso",
                f"Cuando el usuario ingresa datos invalidos el sistema debe mostrar un mensaje de error descriptivo",
            ][j - 1])
            for j in range(1, 4)
        ]
        await backend.create_acceptance_criteria("b", uc.id, ac_pairs)
        ucs.append(uc)
    return us, ucs


# ── validate_ac_quality ──────────────────────────────────────────────


async def test_validate_ac_quality_flags_short_acs(backend, ctx):
    us, ucs = await _seed(backend)
    # Override one AC to be too short
    backend.acs[ucs[0].id][0].text = "short"
    result = await bo.validate_ac_quality("b", ctx)
    assert result["total_acs"] == 9
    assert len(result["failed"]) >= 1
    bad = result["failed"][0]
    assert "too_short" in bad["issues"]


async def test_validate_ac_quality_single_uc(backend, ctx):
    _, ucs = await _seed(backend)
    backend.acs[ucs[0].id][0].text = "x"
    result = await bo.validate_ac_quality("b", ctx, uc_id="UC-002")
    # Only UC-002's ACs should be checked
    assert result["total_acs"] == 3
    assert result["passed"] == 3  # UC-002 ACs are fine


# ── set_ac_metadata ──────────────────────────────────────────────────


async def test_set_ac_metadata_stores_evidence(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.set_ac_metadata(
        "b", "UC-001", "AC-01", ctx,
        evidence_url="https://example.com/evidence.html",
        verdict="ACCEPTED",
    )
    assert result.get("error") is None
    assert result["metadata"]["evidence_url"] == "https://example.com/evidence.html"
    assert result["metadata"]["verdict"] == "ACCEPTED"
    # Verify text was updated with META suffix
    ac = backend.acs[ucs[0].id][0]
    assert "[META:" in ac.text


async def test_set_ac_metadata_invalid_verdict(backend, ctx):
    await _seed(backend)
    result = await bo.set_ac_metadata("b", "UC-001", "AC-01", ctx, verdict="BOGUS")
    assert result["code"] == "VALIDATION_FAILED"


# ── link_uc_parent ───────────────────────────────────────────────────


async def test_link_uc_parent_creates_comments_on_both(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.link_uc_parent("b", "UC-001", "UC-002", "absorbs", ctx)
    assert result.get("error") is None
    assert result["link_type"] == "absorbs"
    # Comments on both cards
    commented_ids = {c[0] for c in backend.comments}
    assert ucs[0].id in commented_ids
    assert ucs[1].id in commented_ids
    # Link stored in meta
    links = backend.items[ucs[0].id].meta.get("links", [])
    assert any(l["target_uc_id"] == "UC-002" for l in links)


async def test_link_uc_parent_idempotent(backend, ctx):
    await _seed(backend)
    await bo.link_uc_parent("b", "UC-001", "UC-002", "depends_on", ctx)
    r2 = await bo.link_uc_parent("b", "UC-001", "UC-002", "depends_on", ctx)
    assert r2.get("reason") == "no_change"


# ── delete_uc ────────────────────────────────────────────────────────


async def test_delete_uc_archives(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.delete_uc("b", "UC-001", "obsolete", ctx)
    assert result.get("error") is None
    assert result["archive_location"] == "test_archive"
    assert ucs[0].id in backend.archived


async def test_delete_uc_with_absorbed_by_links_first(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.delete_uc("b", "UC-003", "absorbed", ctx, absorbed_by="UC-001")
    assert result["absorbed_by"] == "UC-001"
    # Link added before archival
    assert ucs[2].id in backend.archived
    # Comment on parent
    assert any("absorbs" in c[1] for c in backend.comments)


# ── get_board_diff ───────────────────────────────────────────────────


async def test_board_diff_detects_changes(tmp_path, ctx, monkeypatch):
    # Patch Path resolution to use tmp_path
    board_dir = tmp_path / ".quality" / "board_snapshots" / "board1"
    board_dir.mkdir(parents=True)

    snap_from = {
        "items": [
            {"uc_id": "UC-001", "name": "Login", "state": "backlog", "milestone": "H1", "ac_count": 3, "ac_done": 0},
            {"uc_id": "UC-002", "name": "Register", "state": "backlog", "milestone": "H1", "ac_count": 2, "ac_done": 1},
            {"uc_id": "UC-003", "name": "Removed", "state": "backlog", "milestone": "H2", "ac_count": 1, "ac_done": 0},
        ]
    }
    snap_to = {
        "items": [
            {"uc_id": "UC-001", "name": "Login", "state": "done", "milestone": "H1", "ac_count": 3, "ac_done": 3},
            {"uc_id": "UC-002", "name": "Register", "state": "backlog", "milestone": "H2", "ac_count": 2, "ac_done": 1},
            {"uc_id": "UC-004", "name": "New UC", "state": "backlog", "milestone": "H3", "ac_count": 5, "ac_done": 0},
        ]
    }
    (board_dir / "snap1.json").write_text(json.dumps(snap_from))
    (board_dir / "snap2.json").write_text(json.dumps(snap_to))

    monkeypatch.chdir(tmp_path)
    result = await bo.get_board_diff("board1", "snap1", "snap2", ctx)
    assert result["added_ucs"] == ["UC-004"]
    assert result["removed_ucs"] == ["UC-003"]
    assert len(result["modified_ucs"]) == 2  # UC-001 state changed, UC-002 milestone changed
    assert len(result["milestone_moves"]) == 1  # UC-002 H1→H2
    assert result["ac_changes"]["passed_delta"] == 3  # UC-001 went 0→3


# ── Backend archive_item tests ───────────────────────────────────────


async def test_freeform_archive_item(tmp_path):
    from src.backends.freeform_backend import FreeformBackend
    be = FreeformBackend(root=str(tmp_path / "tracking"))
    uc = await be.create_item("b", "UC-001: Test", labels=["UC"], meta={"uc_id": "UC-001"})
    result = await be.archive_item("b", uc.id, reason="obsolete")
    assert result["archive_location"] == "archive.json"
    # Verify item removed from items.json
    items = await be.list_items("b")
    assert not any(i.id == uc.id for i in items)
    # Verify archive.json has the item
    archive = json.loads((tmp_path / "tracking" / "archive.json").read_text())
    assert len(archive) == 1
    assert archive[0]["archive_reason"] == "obsolete"
