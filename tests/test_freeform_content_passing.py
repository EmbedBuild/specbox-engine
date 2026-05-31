"""UC-660 — FreeForm mutation tools content-passing (memory mode).

The MCP Path Contract (v6.0.1) requires that a remote MCP server never reaches
the client's filesystem. UC-660 completes this for the 7 FreeForm *mutation*
tools: they accept the client's items.json as a string (`items_content`),
operate on an in-memory FreeformBackend, and return the mutated items.json
string for the client to write back.

AC-01: each mutation tool accepts items.json as a string and returns the
       mutated string, without the server calling Path(...).resolve() against a
       foreign filesystem.
AC-02: the add_uc → mark_ac → find_next_uc chain works end-to-end in remote
       mode on a client board passed by content-passing.
AC-03: in-process callers (disk mode) keep working unchanged — covered by the
       existing test_freeform_backend / test_spec_driven suites, plus the
       disk-mode assertions here.
"""
from __future__ import annotations

import json

import pytest

from server.backends.freeform_backend import FreeformBackend, FreeformPathError
from server.tools.spec_driven import (
    complete_uc,
    find_next_uc,
    import_spec,
    mark_ac,
    start_uc,
)
from server.tools.spec_mutations import add_ac, add_uc, update_uc


class FakeCtx:
    """Minimal FastMCP Context double holding a FreeForm session config.

    root_path points at a path that must never be created/read — any tool that
    honours content-passing operates purely in memory, so touching this path
    would be a bug the tests would surface (the dir simply never appears).
    """

    def __init__(self, root_path: str = "/uc660/does/not/exist"):
        self._s = {
            "spec_backend_config": {"backend_type": "freeform", "root_path": root_path}
        }

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value


def _board_with_us(us_id: str = "US-50") -> str:
    """A minimal items.json string with a single US and no UCs."""
    return json.dumps(
        [
            {
                "id": "item-us1",
                "name": f"{us_id}: Demo",
                "description": "",
                "state": "backlog",
                "parent_id": None,
                "labels": ["US"],
                "priority": "none",
                "meta": {"us_id": us_id, "tipo": "US"},
            }
        ]
    )


# ── AC-01: each mutation tool accepts + returns items.json string ─────


@pytest.mark.asyncio
async def test_add_uc_content_passing_returns_mutated_string(monkeypatch, tmp_path):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    ctx = FakeCtx(root_path=str(tmp_path / "never_used"))
    board = _board_with_us()

    res = await add_uc(
        board_id="ff",
        us_id="US-50",
        name="Content-passing UC",
        description="d",
        acceptance_criteria=["AC uno debe pasar", "AC dos debe pasar"],
        ctx=ctx,
        items_content=board,
    )

    assert "items_content" in res
    mutated = json.loads(res["items_content"])
    names = [i["name"] for i in mutated]
    assert any("Content-passing UC" in n for n in names)
    assert sum(1 for i in mutated if "AC" in i.get("labels", [])) == 2
    # The server never created the (bogus) root path.
    assert not (tmp_path / "never_used").exists()


@pytest.mark.asyncio
async def test_add_ac_content_passing(monkeypatch):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    ctx = FakeCtx()
    board = _board_with_us()
    board = (await add_uc(
        board_id="ff", us_id="US-50", name="UC", description="d",
        acceptance_criteria=["AC uno debe pasar"], ctx=ctx, items_content=board,
    ))["items_content"]

    res = await add_ac(
        board_id="ff", uc_id="UC-001", text="AC dos debe pasar",
        ctx=ctx, items_content=board,
    )
    assert "items_content" in res
    mutated = json.loads(res["items_content"])
    assert sum(1 for i in mutated if "AC" in i.get("labels", [])) == 2


@pytest.mark.asyncio
async def test_update_uc_content_passing(monkeypatch):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    ctx = FakeCtx()
    board = _board_with_us()
    board = (await add_uc(
        board_id="ff", us_id="US-50", name="UC", description="d",
        acceptance_criteria=["AC uno debe pasar"], ctx=ctx, items_content=board,
    ))["items_content"]

    res = await update_uc(
        board_id="ff", uc_id="UC-001", ctx=ctx, hours=5, items_content=board,
    )
    assert "items_content" in res
    mutated = json.loads(res["items_content"])
    uc = next(i for i in mutated if i.get("meta", {}).get("uc_id") == "UC-001")
    assert uc["meta"]["horas"] == 5


@pytest.mark.asyncio
async def test_import_spec_content_passing(monkeypatch):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    ctx = FakeCtx()
    spec = {
        "user_stories": [
            {
                "us_id": "US-50", "name": "Demo", "hours": 1, "screens": "",
                "description": "d",
                "use_cases": [
                    {
                        "uc_id": "UC-001", "name": "P", "actor": "dev", "hours": 1,
                        "screens": "",
                        "acceptance_criteria": ["AC uno debe pasar"], "context": "",
                    }
                ],
            }
        ]
    }
    res = await import_spec(board_id="ff", spec=spec, ctx=ctx, items_content="[]")
    assert "items_content" in res
    mutated = json.loads(res["items_content"])
    assert len(mutated) == 3  # 1 US + 1 UC + 1 AC


@pytest.mark.asyncio
async def test_mark_start_complete_content_passing(monkeypatch):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    ctx = FakeCtx()
    board = _board_with_us()
    board = (await add_uc(
        board_id="ff", us_id="US-50", name="UC", description="d",
        acceptance_criteria=["AC uno debe pasar"], ctx=ctx, items_content=board,
    ))["items_content"]

    r_mark = await mark_ac(
        board_id="ff", uc_id="UC-001", ac_id="AC-01", passed=True,
        ctx=ctx, items_content=board,
    )
    assert r_mark["passed"] and r_mark["ac_done"] == 1
    board = r_mark["items_content"]

    r_start = await start_uc(board_id="ff", uc_id="UC-001", ctx=ctx, items_content=board)
    assert r_start["status"] == "in_progress"
    board = r_start["items_content"]

    r_done = await complete_uc(board_id="ff", uc_id="UC-001", ctx=ctx, items_content=board)
    assert r_done["uc_id"] == "UC-001"
    mutated = json.loads(r_done["items_content"])
    uc = next(i for i in mutated if i.get("meta", {}).get("uc_id") == "UC-001")
    assert uc["state"] == "done"


# ── AC-02: full chain add_uc → mark_ac → find_next_uc in remote mode ──


@pytest.mark.asyncio
async def test_ac02_full_chain_remote(monkeypatch):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    ctx = FakeCtx()
    board = _board_with_us()

    board = (await add_uc(
        board_id="ff", us_id="US-50", name="UC uno", description="d",
        acceptance_criteria=["AC uno debe pasar", "AC dos debe pasar"],
        ctx=ctx, items_content=board,
    ))["items_content"]
    board = (await add_uc(
        board_id="ff", us_id="US-50", name="UC dos", description="d",
        acceptance_criteria=["AC tres debe pasar"], ctx=ctx, items_content=board,
    ))["items_content"]

    board = (await mark_ac(
        board_id="ff", uc_id="UC-001", ac_id="AC-01", passed=True,
        ctx=ctx, items_content=board,
    ))["items_content"]

    nxt = await find_next_uc(board_id="ff", ctx=ctx, items_content=board)
    assert nxt["uc_id"] == "UC-001", "UC-001 still pending → first in line"

    # Complete UC-001 → find_next_uc must skip it.
    for ac in ("AC-02",):
        board = (await mark_ac(
            board_id="ff", uc_id="UC-001", ac_id=ac, passed=True,
            ctx=ctx, items_content=board,
        ))["items_content"]
    board = (await complete_uc(
        board_id="ff", uc_id="UC-001", ctx=ctx, items_content=board,
    ))["items_content"]

    nxt2 = await find_next_uc(board_id="ff", ctx=ctx, items_content=board)
    assert nxt2["uc_id"] == "UC-002", "UC-001 done → UC-002 is next"


# ── AC-03 + backend memory-mode unit guarantees ──────────────────────


def test_memory_mode_never_touches_filesystem():
    b = FreeformBackend(items_content="[]")
    assert b._memory_mode is True
    assert b.root is None


def test_memory_mode_rejects_non_array():
    with pytest.raises(ValueError):
        FreeformBackend(items_content='{"not": "an array"}')


def test_memory_mode_empty_string_is_empty_board():
    b = FreeformBackend(items_content="   ")
    assert b._load_items() == []


def test_disk_mode_still_requires_absolute_path():
    with pytest.raises(FreeformPathError):
        FreeformBackend(root="relative/path")


def test_disk_mode_requires_root_or_items_content():
    with pytest.raises(ValueError):
        FreeformBackend()


def test_get_items_content_roundtrips(tmp_path):
    # Disk mode: get_items_content reflects what was saved.
    b = FreeformBackend(root=str(tmp_path))
    b._save_items([{"id": "x", "name": "US-01: t", "labels": ["US"]}])
    content = b.get_items_content()
    assert json.loads(content)[0]["id"] == "x"
