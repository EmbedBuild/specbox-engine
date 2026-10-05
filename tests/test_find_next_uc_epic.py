"""US-78 / UC-7804 — el autopilot trabaja por épica o por satélite.

- **AC-01**: ``find_next_uc`` acepta ``epic`` y ``satellite`` (juntos o por separado) y solo
  devuelve UC de ese alcance; sin filtros devuelve lo mismo que antes.
- **AC-02**: con ``epic``, las UC van en el orden de sus historias (US-9 antes que US-10), una
  historia con trabajo en curso va primero y, sin pendientes, devuelve ``None``: la señal para que
  ``/implement EP-NN`` pare (``.claude/skills/implement/SKILL.md`` §0.1a-bis y §8.5.5).
"""

from __future__ import annotations

import json

from server.backends.freeform_backend import FreeformBackend
from server.tools.spec_driven import find_next_uc


class FakeCtx:
    """FreeForm session as in tests/test_freeform_content_passing.py."""

    def __init__(self):
        self._s = {"spec_backend_config": {"backend_type": "freeform", "root_path": "/uc7804/never"}}

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value


def _us(item_id, us_id):
    return {"id": item_id, "name": f"{us_id}: Historia", "state": "user_stories", "parent_id": None,
            "labels": ["US"], "priority": "none", "meta": {"us_id": us_id, "tipo": "US"}}


def _uc(item_id, uc_id, parent, us_id, satellite, state="backlog"):
    return {"id": item_id, "name": f"{uc_id}: Caso", "state": state, "parent_id": parent, "labels": ["UC"],
            "priority": "none", "meta": {"uc_id": uc_id, "us_id": us_id, "tipo": "UC", "satellite": satellite}}


async def _content(uc1002_state="backlog", epic_states=None) -> str:
    epic_states = epic_states or {}
    items = [
        _us("us9", "US-9"),
        _uc("uc0901", "UC-0901", "us9", "US-9", "engine", epic_states.get("UC-0901", "backlog")),
        _uc("uc0902", "UC-0902", "us9", "US-9", "cloud", epic_states.get("UC-0902", "backlog")),
        _us("us10", "US-10"),
        _uc("uc1001", "UC-1001", "us10", "US-10", "engine", epic_states.get("UC-1001", "backlog")),
        _uc("uc1002", "UC-1002", "us10", "US-10", "engine", uc1002_state),
        # Sin épica y con el bloque más grande: lo que elegía find_next_uc sin filtros.
        _us("us20", "US-20"),
        _uc("uc2001", "UC-2001", "us20", "US-20", "site"),
        _uc("uc2002", "UC-2002", "us20", "US-20", "site"),
        _uc("uc2003", "UC-2003", "us20", "US-20", "site"),
    ]
    board = FreeformBackend(items_content=json.dumps(items))
    await board.create_epic("ff", name="Épica")
    await board.set_us_epic("ff", "us9", "EP-01")
    await board.set_us_epic("ff", "us10", "EP-01")
    return board.get_items_content()


async def _next(content, **kw):
    result = await find_next_uc(board_id="ff", ctx=FakeCtx(), items_content=content, **kw)
    return result.get("uc_id") if isinstance(result, dict) and "uc_id" in result else result


async def test_ac01_without_filters_nothing_changes():
    content = await _content()
    assert await _next(content) == "UC-2001"
    assert await _next(content, epic=None, satellite=None) == "UC-2001"


async def test_ac01_epic_satellite_and_both_narrow_the_choice():
    content = await _content()
    assert await _next(content, epic="EP-01") == "UC-0901"
    assert await _next(content, epic="EP-01", satellite="cloud") == "UC-0902"
    assert await _next(content, satellite="engine") in {"UC-0901", "UC-1001", "UC-1002"}
    assert await _next(content, satellite="nadie") is None


async def test_ac02_story_order_and_focus_inside_the_epic():
    # US-9 va antes que US-10 aunque «US-10» < «US-9» como texto.
    assert await _next(await _content(), epic="EP-01") == "UC-0901"
    # Con trabajo en curso en US-10, su siguiente UC va primero.
    assert await _next(await _content(uc1002_state="in_progress"), epic="EP-01") == "UC-1001"


async def test_ac02_none_when_the_epic_has_nothing_pending_and_unknown_epic():
    done = {"UC-0901": "done", "UC-0902": "review", "UC-1001": "done"}
    content = await _content(uc1002_state="done", epic_states=done)
    assert await _next(content, epic="EP-01") is None
    assert (await find_next_uc(board_id="ff", ctx=FakeCtx(), items_content=content, epic="EP-99"))["code"] == (
        "EPIC_NOT_FOUND"
    )
