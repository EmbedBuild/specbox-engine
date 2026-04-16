"""Tier 4 tests — acceptance_automation.py (v5.23.0).

See doc/design/v5.23.0-full-mutations.md → "Tier 4 test plan".
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
from src.tools import acceptance_automation as aa


# ── In-memory backend ────────────────────────────────────────────────


class InMemoryBackend(SpecBackend):
    def __init__(self):
        self.items: dict[str, ItemDTO] = {}
        self.acs: dict[str, list[ChecklistItemDTO]] = {}
        self.closed = False
        self._next_id = 1
        self.update_item_calls = 0

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
        self.update_item_calls += 1
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
            if ac.id == ac_id: ac.done = passed; return ac
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
            if ac.id == ac_id: acs.pop(idx); return
        raise ValueError()

    async def archive_item(self, board_id, item_id, *, reason):
        return {"archive_location": "test", "archived_at": "now"}

    async def add_comment(self, board_id, item_id, text):
        return CommentDTO(id=self._new_id("c"), text=text)

    async def get_comments(self, *a): return []
    async def add_attachment(self, *a, **kw): return AttachmentDTO(id="a", name="f", url="")
    async def get_attachments(self, *a): return []
    async def create_module(self, board_id, name, description=""): return ModuleDTO(id="m", name=name)
    async def add_items_to_module(self, *a): return None
    async def create_label(self, board_id, name, color): return {"id": "l", "name": name, "color": color}
    async def get_labels(self, *a): return []
    async def get_state_id(self, board_id, state): return state
    async def get_states(self, *a): return {}
    async def close(self): self.closed = True


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def ctx(backend, monkeypatch):
    async def _fake(c):
        return backend
    monkeypatch.setattr(aa, "get_session_backend", _fake)
    return AsyncMock()


async def _seed_22_ucs_with_hours_in_desc(backend):
    """Mimics potencial_digital_2026: 22 UCs with hours in description."""
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    for i in range(1, 23):
        uc_id = f"UC-{i:03d}"
        desc = f"## {uc_id}: Feature {i}\n\nHoras estimadas: {i + 1}\n\nDescripción del caso de uso."
        uc = await backend.create_item(
            "b", f"{uc_id}: Feature {i}", description=desc,
            labels=["UC"], parent_id=us.id,
            meta={"uc_id": uc_id, "us_id": "US-01"},
        )
        await backend.create_acceptance_criteria(
            "b", uc.id,
            [(f"AC-{j:02d}", f"Dado un usuario cuando opera entonces debe validar resultado {j}") for j in range(1, 4)]
        )
    return us


async def _seed_milestone_ucs(backend, milestone="H1", n=5, ac_done_ratio=1.0):
    """Seed n UCs in a milestone with controlled AC done ratio."""
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    ucs = []
    for i in range(1, n + 1):
        uc_id = f"UC-{i:03d}"
        uc = await backend.create_item(
            "b", f"{uc_id}: F{i}", labels=["UC"], parent_id=us.id,
            meta={"uc_id": uc_id, "us_id": "US-01", "milestone": milestone},
        )
        ac_pairs = [(f"AC-{j:02d}", f"Dado usuario cuando opera entonces debe validar {j}") for j in range(1, 4)]
        await backend.create_acceptance_criteria("b", uc.id, ac_pairs)
        # Mark some ACs as done
        acs = backend.acs[uc.id]
        done_count = round(len(acs) * ac_done_ratio)
        for ac in acs[:done_count]:
            ac.done = True
        ucs.append(uc)
    return us, ucs


# ── bulk_update_hours_from_description ───────────────────────────────


async def test_bulk_hours_dry_run_returns_22_updates(backend, ctx):
    await _seed_22_ucs_with_hours_in_desc(backend)
    result = await aa.bulk_update_hours_from_description("b", ctx, dry_run=True)
    updates = [p for p in result["parsed_ucs"] if p["action"] == "update"]
    assert len(updates) == 22
    assert result["applied_changes"] == 0


async def test_bulk_hours_apply_calls_update_not_loop(backend, ctx):
    await _seed_22_ucs_with_hours_in_desc(backend)
    result = await aa.bulk_update_hours_from_description("b", ctx, dry_run=False)
    assert result["applied_changes"] == 22
    # Verify hours are set in meta
    for item in backend.items.values():
        if "UC" in item.labels:
            assert item.meta.get("horas") is not None


async def test_bulk_hours_conflict_not_applied(backend, ctx):
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    uc = await backend.create_item(
        "b", "UC-001: F1",
        description="Horas estimadas: 10",
        labels=["UC"], parent_id=us.id,
        meta={"uc_id": "UC-001", "horas": 5.0},  # existing != text
    )
    result = await aa.bulk_update_hours_from_description("b", ctx, dry_run=False)
    conflicts = [p for p in result["parsed_ucs"] if p["action"] == "conflict"]
    assert len(conflicts) == 1
    assert result["applied_changes"] == 0


# ── estimate_from_ac ─────────────────────────────────────────────────


async def test_estimate_heuristic_classifies_correctly(backend, ctx):
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    uc = await backend.create_item(
        "b", "UC-001: F1", labels=["UC"], parent_id=us.id,
        meta={"uc_id": "UC-001"},
    )
    await backend.create_acceptance_criteria("b", uc.id, [
        ("AC-01", "Muestra el nombre del usuario en la pantalla principal"),
        ("AC-02", "Integra con el webhook de Stripe para procesar pagos"),
        ("AC-03", "E2E test que valida el flujo completo de checkout end-to-end"),
    ])
    result = await aa.estimate_from_ac("b", "UC-001", ctx)
    assert result["classified"] == {"simple": 1, "integration": 1, "e2e": 1}
    assert result["estimated_hours"] == 2.0 + 4.0 + 6.0  # 12h


async def test_estimate_fibonacci(backend, ctx):
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    uc = await backend.create_item(
        "b", "UC-001: F1", labels=["UC"], parent_id=us.id,
        meta={"uc_id": "UC-001"},
    )
    await backend.create_acceptance_criteria("b", uc.id, [
        (f"AC-{i:02d}", f"Dado un usuario cuando valida AC{i} entonces debe funcionar correctamente")
        for i in range(1, 6)
    ])
    result = await aa.estimate_from_ac("b", "UC-001", ctx, strategy="fibonacci")
    assert result["estimated_hours"] == 8.0  # 5 ACs → index 4 → fib[4]=8


# ── milestone_acceptance_check ───────────────────────────────────────


async def test_milestone_check_go_verdict(backend, ctx):
    await _seed_milestone_ucs(backend, "H1", n=3, ac_done_ratio=1.0)
    result = await aa.milestone_acceptance_check("b", "H1", ctx, run_ag09b=False)
    assert result["verdict"] == "GO"
    assert result["pass_rate"] == 1.0
    assert result["total_acs"] == 9
    assert result["passed_acs"] == 9


async def test_milestone_check_no_go_verdict(backend, ctx):
    await _seed_milestone_ucs(backend, "H1", n=3, ac_done_ratio=0.0)
    result = await aa.milestone_acceptance_check("b", "H1", ctx, run_ag09b=True)
    assert result["verdict"] == "NO_GO"
    assert result["pass_rate"] == 0.0


async def test_milestone_check_conditional_go(backend, ctx):
    # 3 UCs: 2 with all ACs done, 1 with 2/3 done → overall ~88%
    us, ucs = await _seed_milestone_ucs(backend, "H1", n=3, ac_done_ratio=1.0)
    # Undo 1 AC on the last UC
    backend.acs[ucs[2].id][2].done = False
    result = await aa.milestone_acceptance_check("b", "H1", ctx, run_ag09b=True)
    assert result["pass_rate"] == pytest.approx(8 / 9, abs=0.01)
    assert result["verdict"] == "CONDITIONAL_GO"
