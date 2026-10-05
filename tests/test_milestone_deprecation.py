"""US-78 / UC-7806 — los milestones avisan de que se retiran.

- **AC-01**: cada tool y cada parámetro de milestone sigue funcionando y su respuesta lleva
  ``deprecation`` (desde 6.21.0, se retira en 6.23.0, usar épicas); las tools que solo aceptan un
  milestone opcional avisan solo cuando se usa.
- **AC-02** (parte del engine): ni las skills, ni las plantillas, ni las reglas, ni ``docs/``
  enseñan milestones; el changelog de la 6.21.0 anuncia la retirada.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from server.backends.freeform_backend import FreeformBackend
from server.tools import _mutation_helpers as mh
from server.tools import milestone_management as mm
from server.tools import spec_mutations as sm

ROOT = Path(__file__).resolve().parents[1]


class _KeepOpen(FreeformBackend):
    async def close(self) -> None:
        return None


def _board(monkeypatch) -> _KeepOpen:
    items = [
        {"id": "us1", "name": "US-01: H", "state": "backlog", "parent_id": None, "labels": ["US"],
         "priority": "none", "meta": {"us_id": "US-01", "tipo": "US"}},
        {"id": "uc1", "name": "UC-001: C", "state": "backlog", "parent_id": "us1", "labels": ["UC"],
         "priority": "none", "meta": {"uc_id": "UC-001", "us_id": "US-01", "tipo": "UC"}},
    ]
    board = _KeepOpen(items_content=json.dumps(items))

    async def _fake(_ctx, *, items_content=None):
        return board

    monkeypatch.setattr(mm, "get_session_backend", _fake)
    monkeypatch.setattr(sm, "get_session_backend", _fake)
    return board


async def test_ac01_milestone_tools_still_work_and_say_they_are_leaving(monkeypatch):
    board = _board(monkeypatch)
    tool = mh.milestone_deprecated(mm.set_uc_milestone)
    result = await tool("ff", "UC-001", "H2", ctx=None)
    assert result["milestone"] == "H2"
    assert (await board.get_item("ff", "uc1")).meta["milestone"] == "H2"
    assert result["deprecation"] == {
        "since": "6.21.0",
        "removed_in": "6.23.0",
        "use_instead": "epics: add_epic, set_us_epic, list_epics, get_epic",
        "message": mh.MILESTONE_DEPRECATION["message"],
    }


async def test_ac01_optional_milestone_params_warn_only_when_used(monkeypatch):
    _board(monkeypatch)
    update = mh.milestone_deprecated(sm.update_uc, when=mh.uses_milestone)
    assert "deprecation" in await update("ff", "UC-001", ctx=None, milestone="H1")
    assert "deprecation" not in await update("ff", "UC-001", ctx=None, actor="otro")

    batch = mh.milestone_deprecated(sm.update_uc_batch, when=mh.uses_milestone)
    assert "deprecation" in await batch("ff", [{"uc_id": "UC-001", "milestone": "H3"}], ctx=None)
    assert "deprecation" not in await batch("ff", [{"uc_id": "UC-001", "actor": "x"}], ctx=None)


def test_ac01_registered_tools_carry_the_notice():
    from server.server import mcp

    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in ("set_uc_milestone", "set_uc_milestone_batch", "get_milestone_status", "rebalance_milestones",
                 "milestone_acceptance_check"):
        assert tools[name].description.startswith(mh.MILESTONE_DEPRECATED_LABEL), name
    # The wrapper keeps the signature FastMCP shows.
    assert "milestone" in tools["update_uc"].parameters["properties"]


def test_ac02_skills_templates_rules_and_docs_no_longer_teach_milestones():
    places = [ROOT / ".claude" / "skills", ROOT / "templates", ROOT / "rules", ROOT / "docs", ROOT / "agents",
              ROOT / "doc" / "tracking" / "_templates"]
    hits = [
        str(f.relative_to(ROOT))
        for base in places
        if base.exists()
        for f in base.rglob("*")
        if f.is_file() and f.suffix in {".md", ".json", ".yaml", ".yml", ".template"}
        and "milestone" in f.read_text(errors="ignore").lower()
    ]
    assert hits == []
