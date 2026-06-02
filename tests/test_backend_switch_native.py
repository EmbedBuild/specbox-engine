"""US-BACKEND-SWITCH-NATIVE — atomic, content-passing backend switch.

Reproduces the dogfood bug (2026-06-02): on a remote MCP, migrate/switch
resolved ``source_id='.'`` against the SERVER filesystem (reading the engine's
own 22/112 tracking, or 0/0) instead of the client's 11/88. The fix is
content-passing: the client reads its ``items.json`` and passes the string; the
server never touches a foreign filesystem.

Phase 1 (UC-810): ``resolve_source_backend`` + ``migrate_preview`` content-passing.
Phase 2 (UC-811): count guard.
... (later phases appended as they are implemented).

Backends are exercised in-memory: freeform via a real memory-mode
``FreeformBackend`` (the path that matters), trello/plane via a stubbed session
backend on a fake Context.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from server.spec_backend import ChecklistItemDTO, ItemDTO
from server.tools import migration as migration_mod


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


class _FakeContext:
    """Minimal Context stub: get_state / set_state over a dict."""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state = state or {}

    async def get_state(self, key: str) -> Any:
        return self._state.get(key)

    async def set_state(self, key: str, value: Any) -> None:
        self._state[key] = value


def _items_json(n_us: int, n_uc_per_us: int, n_ac_per_uc: int) -> str:
    """Build a freeform items.json string with the requested counts."""
    items: list[dict[str, Any]] = []
    for u in range(1, n_us + 1):
        us_id = f"US-{u:02d}"
        us_item_id = f"item-us-{u}"
        items.append(
            {
                "id": us_item_id,
                "name": f"[{us_id}] Story {u}",
                "external_id": us_id,
                "labels": ["US"],
                "state": "backlog",
                "parent_id": None,
                "meta": {"tipo": "US", "us_id": us_id},
            }
        )
        for c in range(1, n_uc_per_us + 1):
            uc_num = (u - 1) * n_uc_per_us + c
            uc_id = f"UC-{uc_num:03d}"
            uc_item_id = f"item-uc-{uc_num}"
            items.append(
                {
                    "id": uc_item_id,
                    "name": f"[{uc_id}] Case {uc_num}",
                    "external_id": uc_id,
                    "labels": ["UC"],
                    "state": "backlog",
                    "parent_id": us_item_id,
                    "meta": {"tipo": "UC", "uc_id": uc_id, "us_id": us_id},
                }
            )
            for a in range(1, n_ac_per_uc + 1):
                items.append(
                    {
                        "id": f"ac-{uc_num}-{a}",
                        "name": f"[AC-{a:02d}] criterion {a}",
                        "state": "pending",
                        "parent_id": uc_item_id,
                        "labels": ["AC"],
                        "meta": {"tipo": "AC", "ac_id": f"AC-{a:02d}"},
                    }
                )
    return json.dumps(items)


# A client items.json with 11 US / 88 UC (8 UC per US) — the dogfood reality.
CLIENT_11_88 = _items_json(11, 8, 5)


class _StubSessionBackend:
    """Stubs the API-backed session backend (trello/plane). Records reads."""

    def __init__(self, items: list[ItemDTO]) -> None:
        self._items = items
        self.read = False

    async def list_items(self, board_id: str) -> list[ItemDTO]:
        self.read = True
        return self._items

    async def get_acceptance_criteria(self, board_id: str, uc_id: str) -> list[ChecklistItemDTO]:
        return []

    async def get_comments(self, board_id: str, item_id: str):  # noqa: ANN201
        return []

    async def get_labels(self, board_id: str):  # noqa: ANN201
        return []

    async def get_states(self, board_id: str):  # noqa: ANN201
        return {}

    async def get_board_name(self, board_id: str) -> str:
        return "Stub API Board"

    async def close(self) -> None:
        return None


# ═══════════════════════════════════════════════════════════════════════
# UC-810 — content-passing in migrate_preview / resolve_source_backend
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_preview_freeform_content_passing_reads_client_counts() -> None:
    """AC-01: freeform preview reports the counts of source_content (11/88),
    never the server filesystem."""
    ctx = _FakeContext()
    result = await migration_mod.migrate_preview(
        source_type="freeform",
        source_id=".",
        target_type="native",
        ctx=ctx,
        source_content=CLIENT_11_88,
    )
    assert result["read_counts"]["us"] == 11
    assert result["read_counts"]["uc"] == 88
    assert result["executable"] is True


@pytest.mark.asyncio
async def test_preview_freeform_does_not_touch_session_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-01: a freeform content-passing preview must NOT call the session
    backend (which on a remote MCP would read the server filesystem)."""
    called = {"session": False}

    async def _boom(_ctx):  # noqa: ANN001, ANN202
        called["session"] = True
        raise AssertionError("session backend must not be used for freeform content")

    monkeypatch.setattr(migration_mod, "get_session_backend", _boom)
    ctx = _FakeContext()
    result = await migration_mod.migrate_preview(
        source_type="freeform",
        source_id=".",
        target_type="native",
        ctx=ctx,
        source_content=CLIENT_11_88,
    )
    assert called["session"] is False
    assert result["read_counts"]["uc"] == 88


@pytest.mark.asyncio
async def test_preview_freeform_without_content_errors() -> None:
    """AC-02: freeform source without source_content returns an explicit error
    instead of reading the server filesystem."""
    ctx = _FakeContext()
    result = await migration_mod.migrate_preview(
        source_type="freeform",
        source_id=".",
        target_type="native",
        ctx=ctx,
        source_content=None,
    )
    assert "error" in result
    assert "source_content" in result["error"]


@pytest.mark.asyncio
async def test_preview_trello_uses_session_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-03: a trello source (no source_content) is read from the session API
    backend, not from a filesystem."""
    items = [
        ItemDTO(id="u1", name="US-01: A", state="backlog", labels=["US"], meta={"us_id": "US-01"}),
        ItemDTO(
            id="c1",
            name="UC-001: B",
            state="backlog",
            labels=["UC"],
            parent_id="u1",
            meta={"us_id": "US-01", "uc_id": "UC-001"},
        ),
    ]
    stub = _StubSessionBackend(items)

    async def _fake_session(_ctx):  # noqa: ANN001, ANN202
        return stub

    monkeypatch.setattr(migration_mod, "get_session_backend", _fake_session)
    ctx = _FakeContext()
    result = await migration_mod.migrate_preview(
        source_type="trello",
        source_id="board-123",
        target_type="plane",
        ctx=ctx,
    )
    assert stub.read is True
    assert result["read_counts"]["us"] == 1
    assert result["read_counts"]["uc"] == 1


# ═══════════════════════════════════════════════════════════════════════
# UC-811 — count guard
# ═══════════════════════════════════════════════════════════════════════


def test_count_guard_blocks_zero_read() -> None:
    """AC-04: a dry-run that read 0 items blocks the execute."""
    from server.migration.count_guard import CountGuardError, verify_count

    with pytest.raises(CountGuardError, match="read 0 items"):
        verify_count({"us": 0, "uc": 0, "ac": 0}, confirmed_count={"us": 0, "uc": 0})


def test_count_guard_rejects_mismatch() -> None:
    """AC-05: a confirmed count different from the preview is rejected."""
    from server.migration.count_guard import CountGuardError, verify_count

    with pytest.raises(CountGuardError, match="count mismatch: preview read 11/88"):
        verify_count({"us": 11, "uc": 88, "ac": 440}, confirmed_count={"us": 22, "uc": 112})


def test_count_guard_rejects_missing_confirmation() -> None:
    """AC-05: executing without confirming the count is rejected."""
    from server.migration.count_guard import CountGuardError, verify_count

    with pytest.raises(CountGuardError, match="count not confirmed"):
        verify_count({"us": 11, "uc": 88}, confirmed_count=None)


def test_count_guard_accepts_match() -> None:
    """AC-05: a confirmed count matching the preview proceeds (no raise)."""
    from server.migration.count_guard import verify_count

    # Should not raise. ac is informational and ignored in the comparison.
    verify_count({"us": 11, "uc": 88, "ac": 440}, confirmed_count={"us": 11, "uc": 88})


# ═══════════════════════════════════════════════════════════════════════
# UC-812 — atomic orchestrator (run_switch)
# ═══════════════════════════════════════════════════════════════════════


def _ok_steps(*, fail_switch: bool = False, created_fresh: bool = True):
    """Build a SwitchSteps wired with in-memory fakes for a freeform→native run."""
    from server.migration.orchestrator import SwitchSteps

    calls: dict[str, Any] = {"deleted": False}

    async def preview():
        return {"read_counts": {"us": 11, "uc": 88, "ac": 440}}

    async def ensure_target():
        return ("proj-new", created_fresh)

    async def write_target(_tid):
        calls["written"] = True
        return {"migrated": 99, "skipped": 0, "errors": [], "id_map": {}}

    async def seed_identity(_tid):
        calls["seeded"] = True
        return {"developer_id": "jesusperezdeveloper", "member_added": True}

    async def apply_switch(_tid):
        if fail_switch:
            from server.migration.transactional_switch import TransactionalSwitchError

            raise TransactionalSwitchError("settings", RuntimeError("disk full"), [])
        calls["switched"] = True
        return {"updated": ["registry", "app_spec", "settings"]}

    async def delete_fresh():
        calls["deleted"] = True

    steps = SwitchSteps(
        preview=preview,
        ensure_target=ensure_target,
        write_target=write_target,
        apply_switch=apply_switch,
        delete_fresh_target=delete_fresh,
        seed_identity=seed_identity,
    )
    return steps, calls


@pytest.mark.asyncio
async def test_orchestrator_freeform_to_native_four_substeps() -> None:
    """AC-06: a successful switch runs ensure_target + write + seed + switch."""
    from server.migration.orchestrator import run_switch

    steps, calls = _ok_steps()
    result = await run_switch(
        steps=steps, dry_run=False, confirmed_count={"us": 11, "uc": 88}
    )
    assert result["success"] is True
    assert result["completed_steps"] == [
        "ensure_target",
        "write_target",
        "seed_identity",
        "apply_switch",
    ]
    assert calls["written"] and calls["seeded"] and calls["switched"]
    assert calls["deleted"] is False  # no rollback on success


@pytest.mark.asyncio
async def test_orchestrator_rolls_back_data_on_switch_failure() -> None:
    """AC-07: if the config switch fails after writing data, the freshly-created
    native project is deleted (data rollback) and rolled_back is reported."""
    from server.migration.orchestrator import run_switch

    steps, calls = _ok_steps(fail_switch=True, created_fresh=True)
    result = await run_switch(
        steps=steps, dry_run=False, confirmed_count={"us": 11, "uc": 88}
    )
    assert result["success"] is False
    assert result["rolled_back"] is True
    assert result["failing_step"] == "apply_switch"
    assert result["data_rollback"]["data_rolled_back"] is True
    assert calls["deleted"] is True


@pytest.mark.asyncio
async def test_orchestrator_dry_run_does_not_write() -> None:
    """Dry-run returns the preview and writes nothing."""
    from server.migration.orchestrator import run_switch

    steps, calls = _ok_steps()
    result = await run_switch(steps=steps, dry_run=True, confirmed_count=None)
    assert result["dry_run"] is True
    assert result["read_counts"]["uc"] == 88
    assert "written" not in calls


@pytest.mark.asyncio
async def test_orchestrator_count_guard_blocks_execute() -> None:
    """The orchestrator refuses to execute on a count mismatch (no writes)."""
    from server.migration.orchestrator import run_switch, SwitchOrchestrationError

    steps, calls = _ok_steps()
    with pytest.raises(SwitchOrchestrationError, match="count mismatch"):
        await run_switch(
            steps=steps, dry_run=False, confirmed_count={"us": 22, "uc": 112}
        )
    assert "written" not in calls


@pytest.mark.asyncio
async def test_orchestrator_dev_token_fail_fast_before_preview() -> None:
    """AC-09: a missing dev_token fails before the source is even read."""
    from server.migration.orchestrator import SwitchSteps, run_switch
    from server.migration.native_handling import MissingDevTokenError, require_dev_token

    read = {"happened": False}

    async def preview():
        read["happened"] = True
        return {"read_counts": {"us": 1, "uc": 1}}

    def _require():
        require_dev_token("native", "")  # raises

    steps = SwitchSteps(
        preview=preview,
        ensure_target=lambda: None,  # never reached
        write_target=lambda _t: None,
        apply_switch=lambda _t: None,
        require_dev_token=_require,
    )
    with pytest.raises(MissingDevTokenError):
        await run_switch(steps=steps, dry_run=True, confirmed_count=None)
    assert read["happened"] is False  # fail-fast: preview never ran


def test_legacy_tools_carry_prefer_note() -> None:
    """AC-08: migrate_backend/switch_backend success payloads recommend the
    atomic tool. Verified by source inspection (cheap, no live backends)."""
    import inspect

    from server.tools import migration as m

    src = inspect.getsource(m)
    # both success returns embed the recommendation
    assert src.count("prefer switch_project_backend") >= 2


# ═══════════════════════════════════════════════════════════════════════
# UC-813 — native target: fail-fast, state preservation, collision
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_native_target_requires_dev_token_no_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-09: missing dev_token for a native target raises before any I/O —
    no source read, no DB write."""
    from server.migration.native_handling import MissingDevTokenError, require_dev_token

    # The guard is pure and runs first; assert it raises and nothing else ran.
    with pytest.raises(MissingDevTokenError, match="dev_token"):
        require_dev_token("native", "   ")  # whitespace counts as absent


@pytest.mark.asyncio
async def test_native_preserves_mixed_states() -> None:
    """AC-10: migrating to native via write_target preserves done/in_progress/
    review states (it must NOT degrade everything to backlog like import_spec)."""
    from server.migration.writer import write_target
    from tests.test_write_target_dispatch import InMemoryBackend

    # Source: one US done, one UC in_progress, one UC review.
    us = ItemDTO(id="s-us", name="US-01: A", state="done", labels=["US"], meta={"us_id": "US-01"})
    uc1 = ItemDTO(
        id="s-uc1", name="UC-001: B", state="in_progress", labels=["UC"],
        parent_id="s-us", meta={"us_id": "US-01", "uc_id": "UC-001"},
    )
    uc2 = ItemDTO(
        id="s-uc2", name="UC-002: C", state="review", labels=["UC"],
        parent_id="s-us", meta={"us_id": "US-01", "uc_id": "UC-002"},
    )
    source_data = {
        "board_name": "src",
        "items": [us, uc1, uc2],
        "classified": {"us": [us], "uc": [uc1, uc2], "ac": [], "other": []},
        "ac_data": {},
        "comments_data": {},
        "labels": [],
        "states": {},
    }
    target = InMemoryBackend()
    await write_target(target, "tgt", source_data, "freeform")

    # Key by the most specific logical id: UC items by uc_id, US items by us_id.
    states: dict[str, str] = {}
    for i in target._items.values():
        key = i.meta.get("uc_id") or i.meta.get("us_id")
        if key:
            states[key] = i.state
    assert states["US-01"] == "done"
    assert states["UC-001"] == "in_progress"
    assert states["UC-002"] == "review"


@pytest.mark.asyncio
async def test_native_collision_marked_unresolved_when_fail() -> None:
    """AC-11: an already-populated native target with on_collision='fail' is
    reported as an unresolved collision (the execute must refuse it)."""
    from server.migration.orchestrator import run_switch, SwitchOrchestrationError, SwitchSteps

    async def preview():
        # the tool would set this when list_items(target) is non-empty
        return {
            "read_counts": {"us": 1, "uc": 1},
            "collision": {"project_exists": True, "item_count": 5, "unresolved": True},
        }

    steps = SwitchSteps(
        preview=preview,
        ensure_target=lambda: ("t", False),
        write_target=lambda _t: None,
        apply_switch=lambda _t: None,
    )
    with pytest.raises(SwitchOrchestrationError, match="specify on_collision"):
        await run_switch(steps=steps, dry_run=False, confirmed_count={"us": 1, "uc": 1})


# ═══════════════════════════════════════════════════════════════════════
# UC-814 — native source: DTO read + exit-report
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_native_source_read_via_session_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-12: a native source is read via the session backend (NativeBackend
    DTO), not from a filesystem."""
    items = [
        ItemDTO(id="u1", name="US-01: A", state="done", labels=["US"], meta={"us_id": "US-01"}),
        ItemDTO(
            id="c1", name="UC-001: B", state="review", labels=["UC"],
            parent_id="u1", meta={"us_id": "US-01", "uc_id": "UC-001"},
        ),
    ]
    stub = _StubSessionBackend(items)

    async def _fake_session(_ctx):  # noqa: ANN001, ANN202
        return stub

    monkeypatch.setattr(migration_mod, "get_session_backend", _fake_session)
    ctx = _FakeContext()
    backend = await migration_mod.resolve_source_backend("native", ctx, None)
    assert backend is stub  # native uses the session (DB-backed) backend
    src = await migration_mod._read_source(backend, "proj-x")
    assert stub.read is True
    assert src["read_counts"]["us"] == 1
    assert src["read_counts"]["uc"] == 1


@pytest.mark.asyncio
async def test_native_exit_report_present_in_preview() -> None:
    """AC-13: when leaving native, the preview carries the discarded-state
    report so the user sees it BEFORE confirming the execute."""
    from server.migration.orchestrator import run_switch, SwitchSteps

    async def preview():
        # the tool composes this: read_counts + native_exit_report merged in
        return {
            "read_counts": {"us": 1, "uc": 1},
            "discarded_native_state": {"reservations": 2, "developers": 1, "branches": 1},
            "note": "Reservations ... are NOT migrated to single-user backends.",
        }

    steps = SwitchSteps(
        preview=preview,
        ensure_target=lambda: ("t", True),
        write_target=lambda _t: None,
        apply_switch=lambda _t: None,
    )
    result = await run_switch(steps=steps, dry_run=True, confirmed_count=None)
    assert result["dry_run"] is True
    assert result["discarded_native_state"]["reservations"] == 2


def test_build_native_exit_report_shape() -> None:
    """AC-14: build_native_exit_report wraps the discarded state + an honest
    note so the final result reports what was dropped."""
    from server.migration.native_handling import build_native_exit_report

    report = build_native_exit_report({"reservations": [{"uc_id": "UC-1"}], "developers": []})
    assert "discarded_native_state" in report
    assert "NOT migrated" in report["note"]


# ═══════════════════════════════════════════════════════════════════════
# UC-816 — onboard native documents the empty DB
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_onboard_native_documents_empty_db(tmp_path) -> None:
    """AC-17: onboard_project(backend_type='native') reports that the DB is
    empty and must be populated, so the user does not expect Cloud data."""
    from pathlib import Path

    from fastmcp import FastMCP

    from server.tools.onboarding import register_onboarding_tools

    repo_root = Path(__file__).resolve().parent.parent
    mcp = FastMCP(name="test-onboard-native")
    register_onboarding_tools(mcp, engine_path=repo_root, state_path=tmp_path)
    tool = await mcp.get_tool("onboard_project")

    result = await tool.fn(
        project="acme-native",
        stack="python",
        backend_type="native",
    )
    assert result.get("native_db_state") == "empty"
    assert "native DB empty" in result.get("next_action", "")
    assert "populate" in result.get("next_action", "")


# ═══════════════════════════════════════════════════════════════════════
# UC-817 — E2E: reproduce the original bug
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_e2e_remote_mcp_reads_client_not_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-18: with a remote MCP (SPECBOX_ENGINE_MCP_URL set) and a client
    items.json of 11 US / 88 UC passed as source_content, the preview reports
    11/88 (the client) and NEVER touches the server filesystem (which a spy
    holds at 22/112 and must stay unread)."""
    # Simulate a remote MCP deployment.
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.com/mcp")

    # The server's own tracking (the engine's 22/112) — must NEVER be read.
    server_fs = {"read": False}

    async def _server_session_backend(_ctx):  # noqa: ANN001, ANN202
        server_fs["read"] = True
        raise AssertionError(
            "remote MCP read the SERVER filesystem (the 22/112 engine tracking) "
            "instead of the client's source_content — this is the original bug"
        )

    monkeypatch.setattr(migration_mod, "get_session_backend", _server_session_backend)

    ctx = _FakeContext()
    result = await migration_mod.migrate_preview(
        source_type="freeform",
        source_id=".",  # the poisoned arg from the original bug
        target_type="native",
        ctx=ctx,
        source_content=CLIENT_11_88,
    )

    assert result["read_counts"]["us"] == 11
    assert result["read_counts"]["uc"] == 88
    assert server_fs["read"] is False  # server FS never touched


@pytest.mark.asyncio
async def test_e2e_zero_read_blocks_real_execute() -> None:
    """AC-18 corollary: an empty source (the 0/0 case from the bug) blocks the
    real execute via the count guard — never writes a hollow project."""
    from server.migration.count_guard import CountGuardError, verify_count

    empty_preview = await migration_mod.migrate_preview(
        source_type="freeform",
        source_id=".",
        target_type="native",
        ctx=_FakeContext(),
        source_content="[]",  # empty board — the 0/0 server-CWD case
    )
    assert empty_preview["read_counts"]["us"] == 0
    assert empty_preview["executable"] is False
    with pytest.raises(CountGuardError, match="read 0 items"):
        verify_count(empty_preview["read_counts"], confirmed_count={"us": 0, "uc": 0})


# ── AC-19: freeform → native end-to-end (requires Postgres) ──────────────

try:
    from tests._native_db import DSN, reachable

    _PG_OK, _PG_REASON = reachable()
except Exception as _exc:  # noqa: BLE001 - native infra optional
    _PG_OK, _PG_REASON = False, f"native db infra unavailable: {_exc}"


@pytest.mark.skipif(not _PG_OK, reason=_PG_REASON)
@pytest.mark.asyncio
async def test_e2e_freeform_to_native_preserves_states() -> None:
    """AC-19: migrating a freeform board to native (real Postgres) reconstructs
    the project with the developer as a member and states NOT degraded to
    backlog."""
    from server.backends.native_backend import NativeBackend
    from server.db.pool import apply_migrations, close_pool, init_pool
    from server.migration.native_handling import seed_native_identity
    from server.migration.writer import write_target
    from server.tools.migration import _read_source, resolve_source_backend

    # Source: a memory-mode freeform board with mixed states.
    source_items = json.loads(_items_json(2, 2, 3))
    # mark a couple of items non-backlog to prove preservation
    for it in source_items:
        if it.get("external_id") == "UC-001":
            it["state"] = "in_progress"
        if it.get("external_id") == "UC-002":
            it["state"] = "done"
    source_content = json.dumps(source_items)

    pid = f"bsn-e2e-{abs(hash(source_content)) % 10_000_000}"
    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    seed = await seed_native_identity(pool, project_id=pid, developer_id="jesusperezdeveloper")
    try:
        # Read source via content-passing (the client path), write to native.
        src_backend = await resolve_source_backend("freeform", None, source_content)
        source = await _read_source(src_backend, ".")
        await src_backend.close()

        native = NativeBackend(project_id=pid, dev_token=seed.get("token", ""))
        # the project row exists from seed_native_identity; ensure board
        await native.setup_board("bsn e2e")
        result = await write_target(native, pid, source, "freeform")

        assert result["migrated"]["us"] == 2
        assert result["migrated"]["uc"] == 4

        items = await native.list_items(pid)
        states = {i.meta.get("uc_id"): i.state for i in items if i.meta.get("uc_id")}
        assert states.get("UC-001") == "in_progress"
        assert states.get("UC-002") == "done"

        # developer associated as a member
        async with pool.acquire() as conn:
            member = await conn.fetchval(
                "SELECT count(*) FROM project_members WHERE project_id = $1 "
                "AND developer_id = $2",
                pid,
                "jesusperezdeveloper",
            )
        assert member == 1
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", pid)
            await conn.execute(
                "DELETE FROM developers WHERE developer_id = $1", "jesusperezdeveloper"
            )
        await close_pool()
