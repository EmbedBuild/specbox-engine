"""UC-4305 (US-02) — starting, reviewing or completing a UC moves its story.

Origin (2026-09-28): ``start_uc`` left the story in its initial column and it had
to be moved by hand; two stories stayed open with every UC done because
``complete_uc`` only commented on them. The story now follows its UCs in the
same operation that moves them:

- AC-01: starting a UC, or moving it back to in progress, puts its story in
  progress — also a story in review or done that is reopened — and the sibling
  UCs keep their state.
- AC-02: when a UC goes to review and every UC of the story (archived ones
  aside) is in review or done, the story goes to review.
- AC-03: completing the last pending UC (archived ones aside) puts the story in
  done; while any UC is pending the story is not done.
- AC-04: same behaviour on FreeForm (content-passing, in memory) and on the
  native board (Postgres-gated).
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.tools.spec_driven import complete_uc, derive_us_state, get_us, move_uc, start_uc

# ── derive_us_state (pure) ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        (["in_progress", "backlog", "backlog"], "in_progress"),
        (["in_progress", "done", "review"], "in_progress"),
        (["review", "done", "done"], "review"),
        (["review", "review"], "review"),
        (["done", "done"], "done"),
        (["done", "done", "archived"], "done"),
        (["review", "archived"], "review"),
        (["done", "backlog"], "in_progress"),
        (["review", "user_stories"], "in_progress"),
        (["backlog", "backlog"], None),
        (["user_stories"], None),
        (["archived"], None),
        ([], None),
    ],
)
def test_derive_us_state(states, expected):
    assert derive_us_state(states) == expected


# ── FreeForm, content-passing (in memory) ────────────────────────────


class FakeCtx:
    """FastMCP Context double holding a FreeForm session; the path is never touched."""

    def __init__(self) -> None:
        self._s = {"spec_backend_config": {"backend_type": "freeform", "root_path": "/uc4305/never/used"}}

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value


def _board(us_state: str, uc_states: list[str]) -> str:
    items = [
        {
            "id": "item-us",
            "name": "US-01: Story",
            "description": "",
            "state": us_state,
            "parent_id": None,
            "labels": ["US"],
            "priority": "none",
            "meta": {"us_id": "US-01", "tipo": "US"},
        }
    ]
    for n, state in enumerate(uc_states, start=1):
        items.append(
            {
                "id": f"item-uc{n}",
                "name": f"UC-0{n}: Use case {n}",
                "description": "",
                "state": state,
                "parent_id": "item-us",
                "labels": ["UC"],
                "priority": "none",
                "meta": {"uc_id": f"UC-0{n}", "us_id": "US-01", "tipo": "UC"},
            }
        )
    return json.dumps(items)


def _states(board: str) -> dict[str, str]:
    items = json.loads(board)
    out = {}
    for item in items:
        meta = item.get("meta", {})
        key = meta.get("uc_id") or meta.get("us_id")
        out[key] = item["state"]
    return out


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")
    return FakeCtx()


async def test_ac01_starting_a_uc_puts_its_story_in_progress_and_leaves_siblings(ctx):
    board = _board("user_stories", ["backlog", "user_stories", "backlog"])
    result = await start_uc(board_id="ff", uc_id="UC-01", ctx=ctx, items_content=board)
    states = _states(result["items_content"])
    assert states["US-01"] == "in_progress"
    assert states == {"US-01": "in_progress", "UC-01": "in_progress", "UC-02": "user_stories", "UC-03": "backlog"}
    assert result["us_state_change"] == {"us_id": "US-01", "from": "user_stories", "to": "in_progress"}


async def test_ac01_starting_a_uc_of_a_closed_story_reopens_it(ctx):
    board = _board("done", ["done", "done"])
    result = await start_uc(board_id="ff", uc_id="UC-02", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "in_progress"


async def test_ac01_moving_a_uc_back_to_progress_takes_the_story_out_of_review(ctx):
    board = _board("review", ["review", "done"])
    result = await move_uc(board_id="ff", uc_id="UC-01", target="in_progress", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "in_progress"
    assert result["us_state_change"]["to"] == "in_progress"


async def test_ac01_a_story_already_in_progress_is_left_alone(ctx):
    board = _board("in_progress", ["done", "backlog"])
    result = await start_uc(board_id="ff", uc_id="UC-02", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "in_progress"
    assert "us_state_change" not in result


async def test_ac02_last_uc_to_review_puts_the_story_in_review(ctx):
    board = _board("in_progress", ["in_progress", "done", "archived"])
    result = await move_uc(board_id="ff", uc_id="UC-01", target="review", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "review"
    assert result["us_state_change"] == {"us_id": "US-01", "from": "in_progress", "to": "review"}


async def test_ac02_review_with_pending_siblings_keeps_the_story_in_progress(ctx):
    board = _board("in_progress", ["in_progress", "backlog"])
    result = await move_uc(board_id="ff", uc_id="UC-01", target="review", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "in_progress"
    assert "us_state_change" not in result


async def test_ac03_completing_the_last_pending_uc_closes_the_story(ctx):
    board = _board("review", ["review", "done", "archived"])
    result = await complete_uc(board_id="ff", uc_id="UC-01", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "done"
    assert result["us_state_change"] == {"us_id": "US-01", "from": "review", "to": "done"}


async def test_ac03_completing_a_uc_with_pending_siblings_does_not_close_the_story(ctx):
    board = _board("in_progress", ["in_progress", "backlog"])
    result = await complete_uc(board_id="ff", uc_id="UC-01", ctx=ctx, items_content=board)
    assert _states(result["items_content"])["US-01"] == "in_progress"
    assert "us_state_change" not in result


async def test_a_story_that_fails_to_move_never_fails_the_uc(ctx, monkeypatch):
    from server.backends.freeform_backend import FreeformBackend

    original = FreeformBackend.update_item

    async def refuse_stories(self, board_id, item_id, **fields):
        if item_id == "item-us":
            raise RuntimeError("story locked")
        return await original(self, board_id, item_id, **fields)

    monkeypatch.setattr(FreeformBackend, "update_item", refuse_stories)
    board = _board("backlog", ["backlog"])
    result = await start_uc(board_id="ff", uc_id="UC-01", ctx=ctx, items_content=board)
    states = _states(result["items_content"])
    assert states["UC-01"] == "in_progress" and states["US-01"] == "backlog"
    assert result["us_state_change"] == {"us_id": "US-01", "error": "story locked"}


# ── Native board (Postgres-gated) ────────────────────────────────────

from tests._native_db import DSN, reachable  # noqa: E402

_PG_OK, _PG_SKIP_REASON = reachable()
pg = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


class _StatefulCtx:
    def __init__(self) -> None:
        self._state: dict[str, object] = {}

    async def get_state(self, key: str):
        return self._state.get(key)

    async def set_state(self, key: str, value: object) -> None:
        self._state[key] = value

    async def delete_state(self, key: str) -> None:
        self._state.pop(key, None)


@pg
async def test_ac04_native_story_follows_start_review_reopen_and_done(monkeypatch, tmp_path):
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.migrate import apply_migrations
    from server.db.pool import close_pool, init_pool
    from server.tools.spec_driven import get_session_backend, store_native_credentials

    monkeypatch.chdir(tmp_path)  # start_uc/complete_uc write the local active-UC marker
    monkeypatch.setenv("SPECBOX_NATIVE_DSN", DSN)
    pid = f"test-uc4305-{uuid.uuid4().hex[:8]}"
    dev, token = f"dev-uc4305-{uuid.uuid4().hex[:6]}", f"tok-uc4305-{uuid.uuid4().hex}"

    pool = await init_pool(dsn=DSN)
    try:
        await apply_migrations(pool)
        async with pool.acquire() as conn:
            await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, $1)", pid)
            await register_developer(conn, developer_id=dev, display_name=dev)
            await register_mcp_token(conn, developer_id=dev, token=token)
            await add_project_member(conn, project_id=pid, developer_id=dev)
        ctx = _StatefulCtx()
        await store_native_credentials(ctx, pid, dev_token=token)

        backend = await get_session_backend(ctx)
        try:
            us = await backend.create_item(pid, "US-01 Story that follows its UCs")
            for n in (1, 2):
                uc = await backend.create_item(pid, f"UC-0{n} Use case {n}", parent_id=us.id)
                await backend.update_item(pid, uc.id, state="backlog")
            await backend.update_item(pid, us.id, state="user_stories")
        finally:
            await backend.close()

        async def story() -> tuple[str, dict[str, str]]:
            detail = await get_us(board_id=pid, us_id="US-01", ctx=ctx)
            return detail["status"], {uc["uc_id"]: uc["status"] for uc in detail["use_cases"]}

        started = await start_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert "error" not in started, started
        assert await story() == ("in_progress", {"UC-01": "in_progress", "UC-02": "backlog"})
        assert started["us_state_change"]["to"] == "in_progress"

        await move_uc(board_id=pid, uc_id="UC-01", target="review", ctx=ctx)
        assert (await story())[0] == "in_progress"  # UC-02 still pending

        await start_uc(board_id=pid, uc_id="UC-02", ctx=ctx)
        await move_uc(board_id=pid, uc_id="UC-02", target="review", ctx=ctx)
        assert (await story())[0] == "review"

        await complete_uc(board_id=pid, uc_id="UC-01", ctx=ctx)
        assert (await story())[0] == "review"
        closed = await complete_uc(board_id=pid, uc_id="UC-02", ctx=ctx)
        assert closed["us_state_change"] == {"us_id": "US-01", "from": "review", "to": "done"}
        assert await story() == ("done", {"UC-01": "done", "UC-02": "done"})

        reopened = await start_uc(board_id=pid, uc_id="UC-02", ctx=ctx)
        assert reopened["us_state_change"] == {"us_id": "US-01", "from": "done", "to": "in_progress"}
        assert await story() == ("in_progress", {"UC-01": "done", "UC-02": "in_progress"})
    finally:
        try:
            async with pool.acquire() as conn:
                await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
                await conn.execute("DELETE FROM developers WHERE developer_id = $1", dev)
        finally:
            await close_pool()
