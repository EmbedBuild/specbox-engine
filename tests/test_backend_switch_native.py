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
