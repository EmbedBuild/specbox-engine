"""FreeForm content mode with fragments (UC-11103, UC-11102) — the server side.

``items_content`` may carry only the part of items.json a tool needs, as a
``specbox-freeform-fragment/1`` object with the highest US/UC/EP number of the
whole board. A new UC or epic never repeats an id the fragment does not show,
the answer comes back as a fragment (never as items.json), and the plain array
keeps working exactly as before.
"""

from __future__ import annotations

import json

import pytest

from server.backends.freeform_backend import FRAGMENT_FORMAT, FreeformBackend
from server.tools.epics import add_epic
from server.tools.spec_driven import get_uc, start_uc
from server.tools.spec_mutations import add_uc


class FakeCtx:
    """A content-only FreeForm session, as on the hosted MCP."""

    def __init__(self):
        self._s = {"spec_backend_config": {"backend_type": "freeform", "content_only": True}}

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value


US = {
    "id": "item-us7",
    "name": "US-07: Pagos",
    "description": "Historia de pagos",
    "state": "in_progress",
    "parent_id": None,
    "labels": ["US"],
    "priority": "none",
    "meta": {"us_id": "US-07", "tipo": "US"},
}


def _fragment(items: list[dict], **max_ids: int) -> str:
    return json.dumps({"format": FRAGMENT_FORMAT, "max_ids": max_ids, "items": items})


@pytest.mark.asyncio
async def test_uc11102_add_uc_with_a_fragment_takes_the_number_after_the_whole_board():
    # The fragment only carries the story; the board has UCs up to UC-131 elsewhere.
    res = await add_uc(
        board_id="ff", us_id="US-07", name="Cobrar con tarjeta", description="d",
        acceptance_criteria=["El pago queda registrado"], ctx=FakeCtx(),
        items_content=_fragment([US], US=12, UC=131, EP=3),
    )

    assert res["uc_id"] == "UC-132"
    back = json.loads(res["items_content"])
    assert back["format"] == FRAGMENT_FORMAT and "Never write it as the whole items.json" in back["note"]
    assert back["max_ids"] == {"US": 12, "UC": 132, "EP": 3}
    names = [i["name"] for i in back["items"]]
    assert names[0] == "US-07: Pagos" and any(n.startswith("[UC-132]") or "UC-132" in n for n in names)
    assert sum(1 for i in back["items"] if "AC" in i["labels"]) == 1


@pytest.mark.asyncio
async def test_a_uc_in_the_fragment_above_the_declared_floor_still_counts():
    uc = {**US, "id": "item-uc9", "name": "UC-140: Reembolsos", "labels": ["UC"], "parent_id": "item-us7",
          "meta": {"uc_id": "UC-140", "us_id": "US-07", "tipo": "UC"}}
    res = await add_uc(
        board_id="ff", us_id="US-07", name="Otra", description="d", acceptance_criteria=[],
        ctx=FakeCtx(), items_content=_fragment([US, uc], UC=131),
    )
    assert res["uc_id"] == "UC-141"
    assert json.loads(res["items_content"])["max_ids"]["UC"] == 141


@pytest.mark.asyncio
async def test_uc11102_add_epic_with_a_fragment_skips_the_epics_it_does_not_carry():
    res = await add_epic(board_id="ff", name="Cobros", ctx=FakeCtx(), items_content=_fragment([], EP=18))
    assert res["epic"]["epic_id"] == "EP-19"
    assert json.loads(res["items_content"])["max_ids"]["EP"] == 19


@pytest.mark.asyncio
async def test_reading_with_a_fragment_answers_and_gives_the_fragment_back():
    board = FreeformBackend(items_content=json.dumps([US]))
    uc = await board.create_item("ff", name="UC-132: Cobrar", parent_id="item-us7", labels=["UC"],
                                 meta={"uc_id": "UC-132", "us_id": "US-07"})
    await board.create_acceptance_criteria("ff", uc.id, [("AC-01", "El pago queda registrado")])
    fragment = _fragment(json.loads(board.get_items_content()), US=12, UC=132, EP=3)

    read = await get_uc(board_id="ff", uc_id="UC-132", ctx=FakeCtx(), items_content=fragment)
    started = await start_uc(board_id="ff", uc_id="UC-132", ctx=FakeCtx(), items_content=fragment)

    assert read["uc_id"] == "UC-132" and read["acceptance_criteria"][0]["id"] == "AC-01"
    assert "items_content" not in read  # a read gives nothing back to merge
    assert started["status"] == "in_progress"
    moved = {i["id"]: i["state"] for i in json.loads(started["items_content"])["items"]}
    assert moved[uc.id] == "in_progress"


@pytest.mark.asyncio
async def test_the_plain_array_keeps_its_exact_format():
    res = await add_uc(
        board_id="ff", us_id="US-07", name="Cobrar", description="d", acceptance_criteria=[],
        ctx=FakeCtx(), items_content=json.dumps([US]),
    )
    assert res["uc_id"] == "UC-001"
    assert res["items_content"].startswith("[\n  {") and res["items_content"].endswith("]\n")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (json.dumps({"format": "specbox-freeform-fragment/9", "items": []}), "is not supported"),
        (json.dumps({"format": FRAGMENT_FORMAT, "items": {}}), "items must be an array"),
        (json.dumps({"format": FRAGMENT_FORMAT, "items": [], "max_ids": {"UC": -1}}), "non-negative"),
        (json.dumps({"format": FRAGMENT_FORMAT, "items": [], "max_ids": {"UC": "131"}}), "non-negative"),
    ],
)
def test_a_malformed_fragment_is_rejected_with_what_is_wrong(content, message):
    with pytest.raises(ValueError, match=message):
        FreeformBackend(items_content=content)


def test_other_backends_have_no_floor():
    assert FreeformBackend(items_content="[]").logical_id_floor("UC") == 0
