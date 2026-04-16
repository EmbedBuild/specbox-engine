"""Tier 2 tests — milestone_management.py (v5.23.0).

See doc/design/v5.23.0-full-mutations.md → "Tier 2 test plan".
Reuses the InMemoryBackend from test_spec_mutations.py pattern.
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
from src.tools import milestone_management as mm


# ── In-memory backend (same as Tier 1 tests) ────────────────────────


class InMemoryBackend(SpecBackend):
    def __init__(self):
        self.items: dict[str, ItemDTO] = {}
        self.acs: dict[str, list[ChecklistItemDTO]] = {}
        self.comments: list[tuple[str, str]] = []
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
        raise ValueError(f"AC {ac_id} not found")

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
        raise ValueError(f"AC {ac_id} not found")

    async def delete_acceptance_criterion(self, board_id, uc_item_id, ac_id):
        acs = self.acs.get(uc_item_id, [])
        for idx, ac in enumerate(acs):
            if ac.id == ac_id:
                acs.pop(idx)
                return
        raise ValueError()

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
    monkeypatch.setattr(mm, "get_session_backend", _fake)
    return AsyncMock()


async def _seed_27_ucs(backend: InMemoryBackend) -> list[ItemDTO]:
    """Mimics potencial_digital_2026: US-01 with UC-001..UC-027."""
    us = await backend.create_item(
        "b", "US-01: Plataforma", labels=["US"], meta={"us_id": "US-01"}
    )
    ucs = []
    for i in range(1, 28):
        uc_id = f"UC-{i:03d}"
        uc = await backend.create_item(
            "b",
            name=f"{uc_id}: Feature {i}",
            labels=["UC"],
            parent_id=us.id,
            state="backlog",
            meta={"uc_id": uc_id, "us_id": "US-01"},
        )
        # Each UC gets i ACs (1..27) — total = 27*28/2 = 378 ACs
        ac_pairs = [(f"AC-{j:02d}", f"Criterion {j}") for j in range(1, i + 1)]
        await backend.create_acceptance_criteria("b", uc.id, ac_pairs)
        ucs.append(uc)
    return ucs


# ── set_uc_milestone_batch with 27-UC fixture ────────────────────────


async def test_batch_milestone_27_ucs(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    assignments = [
        {"uc_id": f"UC-{i:03d}", "milestone": f"H{(i % 4) + 1}"}
        for i in range(1, 28)
    ]
    result = await mm.set_uc_milestone_batch("b", assignments, ctx)
    assert result["total"] == 27
    assert len(result["succeeded"]) == 27
    assert len(result["failed"]) == 0
    dist = result["final_distribution"]
    # Every milestone bucket should have UCs
    for m in ("H1", "H2", "H3", "H4"):
        assert len(dist[m]["ucs"]) > 0


async def test_batch_milestone_mixed_errors(backend, ctx):
    await _seed_27_ucs(backend)
    assignments = [
        {"uc_id": "UC-001", "milestone": "H1"},
        {"uc_id": "UC-999", "milestone": "H1"},   # not found
        {"uc_id": "UC-002", "milestone": "H99"},   # invalid
    ]
    result = await mm.set_uc_milestone_batch("b", assignments, ctx)
    assert len(result["succeeded"]) == 1
    assert len(result["failed"]) == 2
    codes = {f["code"] for f in result["failed"]}
    assert "UC_NOT_FOUND" in codes
    assert "INVALID_MILESTONE" in codes


async def test_batch_milestone_idempotent(backend, ctx):
    await _seed_27_ucs(backend)
    assignments = [{"uc_id": "UC-001", "milestone": "H1"}]
    await mm.set_uc_milestone_batch("b", assignments, ctx)
    result = await mm.set_uc_milestone_batch("b", assignments, ctx)
    assert result["succeeded"][0].get("reason") == "no_change"


# ── set_uc_milestone (single) ────────────────────────────────────────


async def test_set_milestone_returns_distribution(backend, ctx):
    await _seed_27_ucs(backend)
    result = await mm.set_uc_milestone("b", "UC-005", "H2", ctx)
    assert result["uc_id"] == "UC-005"
    assert result["milestone"] == "H2"
    assert result["previous_milestone"] is None
    assert "H2" in result["distribution"]
    assert result["total_acs"] == 378  # 27*28/2


# ── rebalance_milestones ─────────────────────────────────────────────


async def test_rebalance_dry_run_does_not_apply(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    # Assign all to H1 — heavily unbalanced
    for uc in ucs:
        uc.meta["milestone"] = "H1"
    result = await mm.rebalance_milestones("b", ctx, dry_run=True)
    assert len(result["suggested_moves"]) > 0
    # Verify nothing actually changed in the backend
    for uc in backend.items.values():
        if "UC" in uc.labels:
            assert uc.meta.get("milestone") == "H1"


async def test_rebalance_apply_changes_milestones(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    for uc in ucs:
        uc.meta["milestone"] = "H1"
    result = await mm.rebalance_milestones("b", ctx, dry_run=False)
    assert len(result["suggested_moves"]) > 0
    # Some UCs should have been moved away from H1
    milestones = {uc.meta.get("milestone") for uc in backend.items.values() if "UC" in uc.labels}
    assert len(milestones) > 1  # Not all H1 anymore


# ── get_milestone_status ─────────────────────────────────────────────


async def test_milestone_status_correct_counts(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    # Assign first 7 to H1, make 3 done, 2 in_progress, 2 backlog
    for i, uc in enumerate(ucs[:7]):
        uc.meta["milestone"] = "H1"
        if i < 3:
            uc.state = "done"
        elif i < 5:
            uc.state = "in_progress"
        else:
            uc.state = "backlog"

    # Mark AC-01 as done on first UC
    first_uc_id = ucs[0].id
    await backend.mark_acceptance_criterion("b", first_uc_id, "AC-01", True)

    result = await mm.get_milestone_status("b", "H1", ctx)
    assert result["milestone"] == "H1"
    assert result["total_ucs"] == 7
    assert result["done_ucs"] == 3
    assert result["in_progress_ucs"] == 2
    assert result["backlog_ucs"] == 2
    assert result["passed_acs"] >= 1
    assert result["ac_pass_rate"] > 0.0


# ── get_satellite_queue ──────────────────────────────────────────────


async def test_satellite_queue_filters(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    # Assign satellites
    ucs[0].meta["satellite"] = "backend"
    ucs[0].meta["milestone"] = "H1"
    ucs[1].meta["satellite"] = "backend"
    ucs[1].meta["milestone"] = "H2"
    ucs[2].meta["satellite"] = "mobile"
    ucs[2].meta["milestone"] = "H1"

    result = await mm.get_satellite_queue("b", "backend", ctx)
    assert result["satellite"] == "backend"
    assert len(result["queue"]) == 2

    result_h1 = await mm.get_satellite_queue("b", "backend", ctx, milestone="H1")
    assert len(result_h1["queue"]) == 1
    assert result_h1["queue"][0]["uc_id"] == "UC-001"


# ── sync_multirepo_state ─────────────────────────────────────────────


async def test_sync_multirepo_propagates_prefix(backend, ctx, tmp_path):
    ucs = await _seed_27_ucs(backend)
    # Rename some UCs to have prefix
    ucs[0].name = "API-UC-001: Backend service"
    ucs[1].name = "MOB-UC-002: Mobile screen"
    ucs[2].meta["satellite"] = "existing"  # should be skipped

    # Write settings
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.local.json"
    settings.write_text(json.dumps({
        "multirepo": {
            "enabled": True,
            "role": "orchestrator",
            "satellites": {
                "backend": {"path": "../api", "uc_prefix": "API"},
                "mobile": {"path": "../mob", "uc_prefix": "MOB"},
            }
        }
    }))

    result = await mm.sync_multirepo_state(str(tmp_path), ctx)
    assert "UC-001" in result["updated_ucs"]
    assert "UC-002" in result["updated_ucs"]
    assert "UC-003" in result["skipped_ucs"]  # already had satellite
    # Verify meta was set
    assert ucs[0].meta["satellite"] == "backend"
    assert ucs[1].meta["satellite"] == "mobile"


async def test_sync_multirepo_preserves_existing(backend, ctx, tmp_path):
    ucs = await _seed_27_ucs(backend)
    ucs[0].meta["satellite"] = "existing-sat"

    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    settings = claude_dir / "settings.local.json"
    settings.write_text(json.dumps({
        "multirepo": {"satellites": {"backend": {"uc_prefix": "API"}}}
    }))

    result = await mm.sync_multirepo_state(str(tmp_path), ctx)
    # UC-001 should be skipped because it already has a satellite
    assert "UC-001" in result["skipped_ucs"]
    assert ucs[0].meta["satellite"] == "existing-sat"


# ── get_cross_repo_dependencies ──────────────────────────────────────


async def test_cross_repo_deps_detects_cross_satellite(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    # UC-027 is in satellite "backend", references UC-002 which is in "mobile"
    ucs[26].meta["satellite"] = "backend"
    ucs[26].description = "Depende de UC-002 para autenticación"
    ucs[1].meta["satellite"] = "mobile"

    result = await mm.get_cross_repo_dependencies("b", ctx)
    deps = result["dependencies"]
    assert len(deps) >= 1
    dep = next(d for d in deps if d["uc_id"] == "UC-027")
    assert dep["depends_on"] == "UC-002"
    assert dep["satellite_from"] == "backend"
    assert dep["satellite_to"] == "mobile"


async def test_cross_repo_deps_ignores_same_satellite(backend, ctx):
    ucs = await _seed_27_ucs(backend)
    ucs[0].meta["satellite"] = "backend"
    ucs[0].description = "Depende de UC-002"
    ucs[1].meta["satellite"] = "backend"  # same satellite

    result = await mm.get_cross_repo_dependencies("b", ctx)
    assert result["dependencies"] == []


# ── set_uc_satellite ─────────────────────────────────────────────────


async def test_set_uc_satellite_idempotent(backend, ctx):
    await _seed_27_ucs(backend)
    r1 = await mm.set_uc_satellite("b", "UC-001", "backend", ctx)
    assert r1.get("error") is None
    r2 = await mm.set_uc_satellite("b", "UC-001", "backend", ctx)
    assert r2["reason"] == "no_change"
