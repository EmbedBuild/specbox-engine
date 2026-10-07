"""The MCP reads from the board only what each tool needs (US-89 / UC-8901).

On the hosted MCP every row the native backend reads crosses the database
pooler, and the pooler is what filled the Supabase egress quota: a tool about one
UC read every story, UC and criterion of the project (``list_items``), and the
listings read the criteria of every UC one by one just to count them.

These tests record every SQL statement the native backend sends and check:

- AC-01: the tools about one UC never read the UCs or criteria of the whole
  project, nor anything of another story.
- AC-02: the tools about one story read only that story.
- AC-03 (local part): the board-wide reads leave the long text in the database
  and count criteria in one query.
- AC-04: every response is the same as reading the whole board.

Postgres-gated (``tests/_native_db.py``).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import asyncpg
import pytest

from server.spec_backend import SpecBackend
from server.tools import epics as ep
from server.tools import spec_driven as sd
from tests._native_db import DSN, reachable

_PG_OK, _PG_SKIP_REASON = reachable()
pytestmark = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)

_CONTEXT = "Contexto largo de la UC. " * 40
_OTHER_STORY = ("US-02", "UC-0201")

#: A read of the UCs or criteria filtered only by project: the whole board.
_WHOLE_PROJECT = re.compile(
    r"FROM (use_cases|acceptance_criteria) WHERE project_id = \$1(?: ORDER BY \w+)?$",
    re.IGNORECASE,
)


class _Ctx:
    def __init__(self) -> None:
        self._state: dict[str, object] = {}

    async def get_state(self, key: str):
        return self._state.get(key)

    async def set_state(self, key: str, value: object) -> None:
        self._state[key] = value

    async def delete_state(self, key: str) -> None:
        self._state.pop(key, None)


def _record_sql(monkeypatch) -> list[tuple[str, tuple]]:
    """Every statement any pooled connection sends, as (normalized SQL, args)."""
    calls: list[tuple[str, tuple]] = []
    for name in ("fetch", "fetchrow", "fetchval", "execute", "executemany"):
        original = getattr(asyncpg.connection.Connection, name)

        def wrapper(self, query, *args, __original=original, **kwargs):
            calls.append((" ".join(str(query).split()), args))
            return __original(self, query, *args, **kwargs)

        monkeypatch.setattr(asyncpg.connection.Connection, name, wrapper)
    return calls


def _whole_project_reads(calls: list[tuple[str, tuple]]) -> list[str]:
    return [sql for sql, _ in calls if _WHOLE_PROJECT.search(sql)]


def _touches_other_story(calls: list[tuple[str, tuple]]) -> list[str]:
    hits = []
    for sql, args in calls:
        flat = [a for arg in args for a in (arg if isinstance(arg, (list, tuple)) else [arg])]
        if any(other in sql for other in _OTHER_STORY) or any(a in _OTHER_STORY for a in flat):
            hits.append(sql)
    return hits


def _without_clock(value: Any) -> Any:
    """Drop the key that carries the time of the call."""
    if isinstance(value, dict):
        return {k: _without_clock(v) for k, v in value.items() if k != "generated_at"}
    if isinstance(value, list):
        return [_without_clock(v) for v in value]
    return value


@pytest.fixture
async def board(monkeypatch, tmp_path):
    """Two stories: US-01 (UC-0101, UC-0102) in EP-01 and US-02 (UC-0201)."""
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import close_pool, init_pool
    from server.tools.spec_driven import get_session_backend, store_native_credentials

    monkeypatch.chdir(tmp_path)  # start_uc / complete_uc write the local active-UC marker
    monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
    pid = f"test-uc8901-{uuid.uuid4().hex[:8]}"
    dev, token = f"dev-uc8901-{uuid.uuid4().hex[:6]}", f"tok-uc8901-{uuid.uuid4().hex}"

    pool = await init_pool(dsn=DSN)
    try:
        await apply_migrations(pool)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $1)", pid)
            await register_developer(conn, developer_id=dev, display_name=dev)
            await register_mcp_token(conn, developer_id=dev, token=token)
            await add_project_member(conn, project_id=pid, developer_id=dev)
        ctx = _Ctx()
        await store_native_credentials(ctx, pid, dev_token=token)

        backend = await get_session_backend(ctx)
        try:
            stories = {}
            for us_id, ucs in (("US-01", ("UC-0101", "UC-0102")), ("US-02", ("UC-0201",))):
                us = await backend.create_item(
                    pid, f"{us_id} Historia {us_id}", description="Descripción de la historia " * 20
                )
                await backend.update_item(pid, us.id, state="backlog")
                stories[us_id] = us
                for uc_id in ucs:
                    uc = await backend.create_item(
                        pid,
                        f"{uc_id} Caso {uc_id}",
                        description="Descripción del caso " * 30,
                        parent_id=us.id,
                        meta={"horas": 2, "actor": "Developer", "satellite": "engine", "context": _CONTEXT},
                    )
                    await backend.update_item(pid, uc.id, state="backlog")
                    await backend.create_acceptance_criteria(
                        pid, uc.id, [("AC-01", f"{uc_id} primero"), ("AC-02", f"{uc_id} segundo")]
                    )
            await backend.create_epic(pid, name="Épica de prueba")
            await backend.set_us_epic(pid, stories["US-01"].id, "EP-01")
        finally:
            await backend.close()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE acceptance_criteria SET internal = true WHERE project_id = $1 AND uc_id = 'UC-0102' "
                "AND ac_id = 'AC-02'",
                pid,
            )
        await sd.mark_ac(pid, "UC-0102", "AC-01", True, ctx, evidence={"type": "test", "label": "prueba"})
        yield pid, ctx
    finally:
        try:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev)
        finally:
            await close_pool()


async def test_ac01_tools_about_one_uc_never_read_the_whole_board(board, monkeypatch):
    pid, ctx = board
    calls = _record_sql(monkeypatch)

    assert "error" not in await sd.get_uc(pid, "UC-0101", ctx)
    assert "error" not in await sd.start_uc(pid, "UC-0101", ctx)
    assert "error" not in await sd.mark_ac(pid, "UC-0101", "AC-01", True, ctx, evidence="ok")
    batch = await sd.mark_ac_batch(pid, "UC-0101", [{"ac_id": "AC-02", "passed": True, "evidence": "ok"}], ctx)
    assert "error" not in batch
    attached = await sd.attach_evidence(pid, "UC-0101", "uc", "ag09", "# Evidencia\n\nTodo bien.", ctx)
    assert "error" not in attached
    assert "error" not in await sd.move_uc(pid, "UC-0101", "review", ctx)
    assert "error" not in await sd.complete_uc(pid, "UC-0101", ctx)

    assert calls, "the recorder saw no SQL"
    assert _whole_project_reads(calls) == []
    assert _touches_other_story(calls) == []


async def test_ac02_tools_about_one_story_read_only_that_story(board, monkeypatch):
    pid, ctx = board
    calls = _record_sql(monkeypatch)

    detail = await sd.get_us(pid, "US-01", ctx)
    assert [uc["uc_id"] for uc in detail["use_cases"]] == ["UC-0101", "UC-0102"]
    assert [uc["uc_id"] for uc in await sd.list_uc(pid, ctx, us_id="US-01")] == ["UC-0101", "UC-0102"]
    assert (await sd.get_us_progress(pid, "US-01", ctx))["total_ucs"] == 2
    # The story follows its UCs (UC-4305): starting and closing UC-0102 syncs US-01.
    started = await sd.start_uc(pid, "UC-0102", ctx)
    assert started["us_state_change"] == {"us_id": "US-01", "from": "backlog", "to": "in_progress"}
    await sd.move_uc(pid, "UC-0102", "backlog", ctx)

    assert _whole_project_reads(calls) == []
    assert _touches_other_story(calls) == []


async def test_ac03_board_wide_reads_leave_the_long_text_and_count_in_one_query(board, monkeypatch):
    pid, ctx = board
    from server.tools.spec_driven import get_session_backend

    backend = await get_session_backend(ctx)
    try:
        summary = await backend.list_board_summary(pid, with_acs=True)
        ucs = [i for i in summary if "UC" in i.labels]
        acs = [i for i in summary if "AC" in i.labels]
        assert {u.id for u in ucs} == {"UC-0101", "UC-0102", "UC-0201"}
        assert all(i.description == "" for i in summary)
        assert all(not ({"comments", "context", "attachments"} & set(u.meta)) for u in ucs)
        assert all(u.meta["satellite"] == "engine" and u.meta["horas"] == 2 for u in ucs)
        assert len(acs) == 6 and all("evidence" not in a.meta for a in acs)
        assert [a.state for a in acs if a.parent_id == "UC-0102"] == ["done", "backlog"]
        assert [i.id for i in await backend.list_board_summary(pid) if "AC" in i.labels] == []

        calls = _record_sql(monkeypatch)
        counts = await backend.count_acceptance_criteria(pid, ["UC-0101", "UC-0102", "UC-0201", "UC-9999"])
        # Internal criteria count, as get_acceptance_criteria returns them.
        assert counts == {"UC-0101": (2, 0), "UC-0102": (2, 1), "UC-0201": (2, 0), "UC-9999": (0, 0)}
        assert len([sql for sql, _ in calls if "acceptance_criteria" in sql]) == 1
    finally:
        await backend.close()

    calls = _record_sql(monkeypatch)
    await sd.list_us(pid, ctx)
    ac_reads = [sql for sql, _ in calls if "FROM acceptance_criteria" in sql]
    assert len(ac_reads) == 1 and "GROUP BY" in ac_reads[0]


async def test_ac04_every_response_is_the_same_as_reading_the_whole_board(board, monkeypatch):
    pid, ctx = board
    from server.backends.native_backend import NativeBackend

    async def responses() -> dict[str, Any]:
        return {
            "get_board_status": await sd.get_board_status(pid, ctx),
            "list_us": await sd.list_us(pid, ctx),
            "list_us_backlog": await sd.list_us(pid, ctx, status="backlog"),
            "list_uc": await sd.list_uc(pid, ctx),
            "list_uc_us01": await sd.list_uc(pid, ctx, us_id="US-01"),
            "list_uc_done": await sd.list_uc(pid, ctx, status="done"),
            "get_us": await sd.get_us(pid, "US-01", ctx),
            "get_us_missing": await sd.get_us(pid, "US-99", ctx),
            "get_us_progress": await sd.get_us_progress(pid, "US-02", ctx),
            "get_uc": await sd.get_uc(pid, "UC-0102", ctx),
            "get_uc_missing": await sd.get_uc(pid, "UC-9999", ctx),
            "find_next_uc": await sd.find_next_uc(pid, ctx),
            "find_next_uc_epic": await sd.find_next_uc(pid, ctx, epic="EP-01"),
            "get_sprint_status": await sd.get_sprint_status(pid, ctx),
            "get_delivery_report": await sd.get_delivery_report(pid, ctx),
            "list_epics": await ep.list_epics(pid, ctx),
            "get_epic": await ep.get_epic(pid, "EP-01", ctx),
        }

    scoped = await responses()
    for name in ("list_story_items", "list_board_summary", "count_acceptance_criteria"):
        monkeypatch.setattr(NativeBackend, name, getattr(SpecBackend, name))
    whole_board = await responses()

    assert scoped["get_uc"]["context"] == _CONTEXT
    assert scoped["get_uc"]["description_raw"].startswith("Descripción del caso")
    for name in whole_board:
        assert _without_clock(scoped[name]) == _without_clock(whole_board[name]), name
