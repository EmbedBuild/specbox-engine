"""UC-404 tests: N×N migrate_backend (AC-10 dry_run, AC-11 additive).

AC-10: dry_run=True returns a preview (counts + state degradations) and writes
nothing — the target stays empty.

AC-11: dry_run=False performs an additive migration — the source is left intact
(``list_items(source)`` identical before/after) and the result carries the
migrated/skipped counts plus the id_map, driven by write_target (UC-401) and
state_mapping (UC-402).

Backends are exercised in-memory (reusing InMemoryBackend from
test_write_target_dispatch) so the suite needs no external credentials. The
session backend (source) and the migration_target_config (target) are stubbed
on a fake Context.
"""

from __future__ import annotations

from typing import Any

import pytest

from server.spec_backend import ItemDTO, parse_item_id
from server.tools import migration as migration_mod
from tests.test_write_target_dispatch import InMemoryBackend


# ═══════════════════════════════════════════════════════════════════════
# Fixtures: fake Context + in-memory source/target wiring
# ═══════════════════════════════════════════════════════════════════════


class _FakeContext:
    """Minimal Context stub: get_state / set_state over a dict."""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self._state = state or {}

    async def get_state(self, key: str) -> Any:
        return self._state.get(key)

    async def set_state(self, key: str, value: Any) -> None:
        self._state[key] = value


def _seed_source(backend: InMemoryBackend) -> None:
    """Populate an InMemoryBackend with 1 US, 2 UC (one in review), 3 AC."""
    # Items are created directly to control logical ids + states.
    us = ItemDTO(
        id="src-us-1",
        name="US-01: Cuentas",
        state="user_stories",
        labels=["US"],
        meta={"us_id": "US-01"},
    )
    uc1 = ItemDTO(
        id="src-uc-1",
        name="UC-001: Alta",
        state="review",  # lossy on plane → degradation expected
        labels=["UC"],
        parent_id="src-us-1",
        meta={"us_id": "US-01", "uc_id": "UC-001"},
    )
    uc2 = ItemDTO(
        id="src-uc-2",
        name="UC-002: Baja",
        state="done",
        labels=["UC"],
        parent_id="src-us-1",
        meta={"us_id": "US-01", "uc_id": "UC-002"},
    )
    backend._items.update({i.id: i for i in (us, uc1, uc2)})
    from server.spec_backend import ChecklistItemDTO

    backend._acs["src-uc-1"] = [
        ChecklistItemDTO(id="AC-01", text="valida", done=True, backend_id="AC-01"),
        ChecklistItemDTO(id="AC-02", text="rechaza", done=False, backend_id="AC-02"),
    ]
    backend._acs["src-uc-2"] = [
        ChecklistItemDTO(id="AC-01", text="limpia", done=False, backend_id="AC-01"),
    ]


class _ConfiguredTargetBackend(InMemoryBackend):
    """InMemoryBackend with the extra surface _read_source + setup_board need."""

    async def setup_board(self, name: str):  # noqa: ANN201
        from server.spec_backend import BoardConfig

        return BoardConfig(
            board_id="target-board",
            board_url="",
            states={},
            labels={},
            custom_fields={},
        )

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        return []

    async def get_states(self, board_id: str) -> dict[str, str]:
        return {}

    async def get_board_name(self, board_id: str) -> str:
        return "Source Board"


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch):
    """Wire source + target in-memory backends into migration_mod.

    Returns (ctx, source_backend, target_backend).
    """
    source = _ConfiguredTargetBackend()
    _seed_source(source)
    target = _ConfiguredTargetBackend()

    async def _fake_session_backend(ctx):  # noqa: ANN001
        return source

    monkeypatch.setattr(migration_mod, "get_session_backend", _fake_session_backend)
    monkeypatch.setattr(
        "server.migration.backend_dispatch.build_backend",
        lambda backend_type, creds: target,
    )

    ctx = _FakeContext()
    return ctx, source, target


# ═══════════════════════════════════════════════════════════════════════
# AC-10 — dry_run preview writes nothing
# ═══════════════════════════════════════════════════════════════════════


async def test_migrate_backend_dry_run_returns_preview(wired) -> None:
    ctx, source, target = wired

    result = await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert result["counts"]["user_stories"] == 1
    assert result["counts"]["use_cases"] == 2
    assert result["counts"]["acceptance_criteria"] == 3


async def test_migrate_backend_dry_run_writes_nothing(wired) -> None:
    ctx, source, target = wired

    await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        dry_run=True,
    )

    # Target stays empty.
    assert target._items == {}


async def test_migrate_backend_dry_run_reports_state_degradations(wired) -> None:
    """AC-10: a UC in 'review' migrating to plane is flagged as lossy."""
    ctx, source, target = wired

    result = await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        dry_run=True,
    )

    degr = result["state_degradations"]
    assert any(
        d["original_state"] == "review" and d["degrades_to"] == "in_progress" for d in degr
    ), degr


async def test_migrate_backend_dry_run_identity_target_no_degradation(wired) -> None:
    """freeform target is the identity map → no degradations."""
    ctx, source, target = wired

    result = await migration_mod.migrate_backend(
        source_type="plane",
        source_id="src-board",
        target_type="freeform",
        ctx=ctx,
        dry_run=True,
    )
    assert result["state_degradations"] == []


# ═══════════════════════════════════════════════════════════════════════
# AC-11 — additive execution: source intact, counts + id_map
# ═══════════════════════════════════════════════════════════════════════


async def test_migrate_backend_execute_additive_counts(wired) -> None:
    ctx, source, target = wired
    await ctx.set_state("migration_target_config", {"backend_type": "plane"})

    result = await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        target_id="target-board",
        dry_run=False,
    )

    assert result["success"] is True
    assert result["migrated"]["us"] == 1
    assert result["migrated"]["uc"] == 2
    assert result["migrated"]["ac"] == 3
    assert "id_map" in result
    assert result["id_map"]["src-us-1"]


async def test_migrate_backend_execute_source_intact(wired) -> None:
    """AC-11: list_items(source) is identical before and after migration."""
    ctx, source, target = wired
    await ctx.set_state("migration_target_config", {"backend_type": "plane"})

    before = await source.list_items("src-board")
    before_ids = {i.id for i in before}

    await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        target_id="target-board",
        dry_run=False,
    )

    after = await source.list_items("src-board")
    after_ids = {i.id for i in after}
    assert before_ids == after_ids
    assert len(after) == 3


async def test_migrate_backend_execute_materializes_target(wired) -> None:
    ctx, source, target = wired
    await ctx.set_state("migration_target_config", {"backend_type": "plane"})

    await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        target_id="target-board",
        dry_run=False,
    )

    assert len(target.by_label("US")) == 1
    assert len(target.by_label("UC")) == 2
    uc_logical = {parse_item_id(uc.name, "UC")[0] for uc in target.by_label("UC")}
    assert uc_logical == {"UC-001", "UC-002"}


async def test_migrate_backend_execute_requires_target_config(wired) -> None:
    """Execution without migration_target_config errors clearly."""
    ctx, source, target = wired

    result = await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="src-board",
        target_type="plane",
        ctx=ctx,
        target_id="target-board",
        dry_run=False,
    )
    assert "error" in result
    assert "Target backend not configured" in result["error"]


# ═══════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════


async def test_migrate_backend_rejects_invalid_backend(wired) -> None:
    ctx, source, target = wired
    result = await migration_mod.migrate_backend(
        source_type="github",
        source_id="x",
        target_type="plane",
        ctx=ctx,
        dry_run=True,
    )
    assert "error" in result
    assert "Invalid source_type" in result["error"]


async def test_migrate_backend_rejects_same_backend_and_id(wired) -> None:
    ctx, source, target = wired
    result = await migration_mod.migrate_backend(
        source_type="freeform",
        source_id="same",
        target_type="freeform",
        ctx=ctx,
        target_id="same",
        dry_run=True,
    )
    assert "error" in result
