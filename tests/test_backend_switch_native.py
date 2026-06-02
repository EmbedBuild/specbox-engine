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
