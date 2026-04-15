"""Backend-level tests for update_acceptance_criterion / delete_acceptance_criterion.

Covers all 3 backends (Trello, Plane, FreeForm) — the new ABC methods added
in v5.23.0 Tier 1. See doc/design/v5.23.0-full-mutations.md section 1.4.

Design deviation: doc planned 3 separate files under tests/backends/ but the
project tests are flat in tests/; keeping one combined file keeps structure
consistent with existing test layout.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.backends.freeform_backend import FreeformBackend
from src.backends.plane_backend import PlaneBackend
from src.backends.trello_backend import TrelloBackend


# ── Trello ───────────────────────────────────────────────────────────


@pytest.fixture
def trello_backend_with_ac():
    tc = AsyncMock()
    # Initial checklist snapshot
    tc.get_card_checklists.return_value = [
        {
            "id": "cl_ac",
            "name": "Criterios de Aceptacion",
            "checkItems": [
                {
                    "id": "ci_01",
                    "name": "AC-01: Original text",
                    "state": "incomplete",
                },
                {
                    "id": "ci_02",
                    "name": "AC-02: Second",
                    "state": "complete",
                },
            ],
        }
    ]
    tc.update_checklist_item.return_value = {}
    tc.delete_checklist_item = AsyncMock(return_value=None)
    be = TrelloBackend(api_key="k", token="t")
    be.client = tc
    return be, tc


async def test_trello_update_ac_rewrites_text(trello_backend_with_ac):
    be, tc = trello_backend_with_ac
    result = await be.update_acceptance_criterion(
        "board", "card_uc", "AC-01", text="Rewritten text"
    )
    tc.update_checklist_item.assert_awaited_once()
    kwargs = tc.update_checklist_item.call_args.kwargs
    assert kwargs["state"] is None
    assert kwargs["name"] == "AC-01: Rewritten text"
    assert result.id == "AC-01"
    assert result.backend_id == "ci_01"


async def test_trello_update_ac_toggles_done_only(trello_backend_with_ac):
    be, tc = trello_backend_with_ac
    await be.update_acceptance_criterion(
        "board", "card_uc", "AC-01", done=True
    )
    kwargs = tc.update_checklist_item.call_args.kwargs
    assert kwargs["state"] == "complete"
    assert kwargs["name"] is None


async def test_trello_update_ac_not_found_raises(trello_backend_with_ac):
    be, _ = trello_backend_with_ac
    with pytest.raises(ValueError, match="AC-99"):
        await be.update_acceptance_criterion(
            "board", "card_uc", "AC-99", text="X"
        )


async def test_trello_delete_ac_calls_client(trello_backend_with_ac):
    be, tc = trello_backend_with_ac
    await be.delete_acceptance_criterion("board", "card_uc", "AC-02")
    tc.delete_checklist_item.assert_awaited_once_with("card_uc", "ci_02")


# ── Plane ────────────────────────────────────────────────────────────


@pytest.fixture
def plane_backend_with_ac():
    client = AsyncMock()
    client.base_url = "https://plane.example.com"
    client.workspace_slug = "ws"
    # States cache: done and backlog
    client.list_states.return_value = [
        {"id": "st-bl", "name": "Backlog", "group": "backlog"},
        {"id": "st-dn", "name": "Done", "group": "completed"},
    ]
    # Labels cache (AC label)
    client.list_labels.return_value = [
        {"id": "lbl-ac", "name": "AC", "color": "#A855F7"}
    ]
    # Work items: 1 UC + 1 AC child
    client.list_work_items.return_value = [
        {
            "id": "uc-item",
            "name": "UC-001: Example",
            "labels": ["lbl-uc"],
            "state": "st-bl",
            "parent": None,
            "description_html": "",
            "priority": "none",
        },
        {
            "id": "ac-item",
            "name": "[AC-01] Original",
            "labels": ["lbl-ac"],
            "state": "st-bl",
            "parent": "uc-item",
            "description_html": "",
            "priority": "none",
        },
    ]
    client.update_work_item = AsyncMock(return_value={})
    client.delete_work_item = AsyncMock(return_value=None)
    be = PlaneBackend(base_url="https://plane.example.com", api_key="k", workspace_slug="ws")
    be.client = client
    return be, client


async def test_plane_update_ac_rewrites_name(plane_backend_with_ac):
    be, client = plane_backend_with_ac
    result = await be.update_acceptance_criterion(
        "proj", "uc-item", "AC-01", text="New text"
    )
    client.update_work_item.assert_awaited_once()
    args = client.update_work_item.call_args
    assert args[0][0] == "proj"
    assert args[0][1] == "ac-item"
    assert args[1]["name"] == "[AC-01] New text"
    assert "state" not in args[1]
    assert result.text == "New text"


async def test_plane_update_ac_toggles_done(plane_backend_with_ac):
    be, client = plane_backend_with_ac
    await be.update_acceptance_criterion(
        "proj", "uc-item", "AC-01", done=True
    )
    kwargs = client.update_work_item.call_args[1]
    assert kwargs["state"] == "st-dn"


async def test_plane_update_ac_not_found(plane_backend_with_ac):
    be, _ = plane_backend_with_ac
    with pytest.raises(ValueError, match="AC-99"):
        await be.update_acceptance_criterion(
            "proj", "uc-item", "AC-99", text="X"
        )


async def test_plane_delete_ac(plane_backend_with_ac):
    be, client = plane_backend_with_ac
    await be.delete_acceptance_criterion("proj", "uc-item", "AC-01")
    client.delete_work_item.assert_awaited_once_with("proj", "ac-item")


# ── FreeForm ─────────────────────────────────────────────────────────


@pytest.fixture
def freeform_backend(tmp_path):
    root = tmp_path / "tracking"
    be = FreeformBackend(root=str(root))
    return be, root


async def _seed_uc_with_acs(be, board_id: str, uc_name: str = "UC-001: demo"):
    uc = await be.create_item(board_id, name=uc_name, labels=["UC"])
    await be.create_acceptance_criteria(
        board_id, uc.id, [("AC-01", "First"), ("AC-02", "Second")]
    )
    return uc


async def test_freeform_update_ac_rewrites_text(freeform_backend):
    be, _ = freeform_backend
    uc = await _seed_uc_with_acs(be, "board")
    result = await be.update_acceptance_criterion(
        "board", uc.id, "AC-01", text="Rewritten"
    )
    assert result.text == "Rewritten"
    acs = await be.get_acceptance_criteria("board", uc.id)
    ac1 = next(a for a in acs if a.id == "AC-01")
    assert ac1.text == "Rewritten"


async def test_freeform_update_ac_toggles_done(freeform_backend):
    be, _ = freeform_backend
    uc = await _seed_uc_with_acs(be, "board")
    await be.update_acceptance_criterion("board", uc.id, "AC-01", done=True)
    acs = await be.get_acceptance_criteria("board", uc.id)
    ac1 = next(a for a in acs if a.id == "AC-01")
    assert ac1.done is True


async def test_freeform_delete_ac_removes(freeform_backend):
    be, _ = freeform_backend
    uc = await _seed_uc_with_acs(be, "board")
    await be.delete_acceptance_criterion("board", uc.id, "AC-01")
    acs = await be.get_acceptance_criteria("board", uc.id)
    ac_ids = [a.id for a in acs]
    assert "AC-01" not in ac_ids
    assert "AC-02" in ac_ids


async def test_freeform_update_ac_not_found(freeform_backend):
    be, _ = freeform_backend
    uc = await _seed_uc_with_acs(be, "board")
    with pytest.raises(ValueError, match="AC-99"):
        await be.update_acceptance_criterion("board", uc.id, "AC-99", text="x")
