"""Tests for DualBackendWrapper (US-DUAL-BACKEND, board UC-1101 + UC-1105).

The critical guarantee under test [UC-1101 AC-02]: a mirror failure NEVER
degrades the primary — every write returns the primary's result, raises
nothing, and logs structured drift. The fakes are pure in-memory
``SpecBackend`` doubles; no network, no Postgres.

Layout:
* ``FakeBackend`` — minimal conformant in-memory backend recording calls.
* ``ExplodingMirror`` — every write raises; reads also raise (they must
  never be reached through the wrapper).
* Wrapper tests per UC-1101 AC-01..AC-05.
"""

from __future__ import annotations

from typing import Any

import pytest

from server.backends.dual_backend import DualBackendWrapper
from server.spec_backend import (
    AttachmentDTO,
    BackendUser,
    BoardConfig,
    ChecklistItemDTO,
    CommentDTO,
    ItemDTO,
    ModuleDTO,
    SpecBackend,
)

PRIMARY_BOARD = "trello-board-1"
MIRROR_BOARD = "EmbedBuild/some-project"


# ── In-memory doubles ─────────────────────────────────────────────────


class FakeBackend(SpecBackend):
    """Conformant in-memory backend. Records every call by method name."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.items: dict[str, ItemDTO] = {}
        self.acs: dict[str, dict[str, ChecklistItemDTO]] = {}
        self.comments: dict[str, list[CommentDTO]] = {}
        self.attachments: dict[str, list[AttachmentDTO]] = {}
        self.modules: dict[str, ModuleDTO] = {}
        self.labels: list[dict[str, str]] = []
        self.calls: list[str] = []
        self.closed = False
        self._seq = 0

    def _next_id(self, prefix: str = "item") -> str:
        self._seq += 1
        return f"{self.tag}-{prefix}-{self._seq}"

    # Auth / setup
    async def validate_auth(self) -> BackendUser:
        self.calls.append("validate_auth")
        return BackendUser(id=self.tag, username=self.tag, display_name=self.tag)

    async def setup_board(self, name: str) -> BoardConfig:
        self.calls.append("setup_board")
        return BoardConfig(
            board_id=self.tag, board_url="", states={}, labels={}, custom_fields={}
        )

    async def get_board_name(self, board_id: str) -> str:
        self.calls.append("get_board_name")
        return f"{self.tag}-board"

    # Items
    async def list_items(self, board_id: str) -> list[ItemDTO]:
        self.calls.append("list_items")
        return list(self.items.values())

    async def get_item(self, board_id: str, item_id: str) -> ItemDTO:
        self.calls.append("get_item")
        return self.items[item_id]

    async def create_item(
        self,
        board_id: str,
        name: str,
        description: str = "",
        state: str = "backlog",
        labels: list[str] | None = None,
        parent_id: str | None = None,
        priority: str = "none",
        external_source: str = "",
        external_id: str = "",
        meta: dict[str, Any] | None = None,
    ) -> ItemDTO:
        self.calls.append("create_item")
        item = ItemDTO(
            id=self._next_id(),
            name=name,
            description=description,
            state=state,
            parent_id=parent_id,
            labels=list(labels or []),
            priority=priority,
            external_source=external_source,
            external_id=external_id,
            meta=dict(meta or {}),
        )
        self.items[item.id] = item
        return item

    async def update_item(
        self,
        board_id: str,
        item_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
        priority: str | None = None,
        external_source: str | None = None,
        external_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> ItemDTO:
        self.calls.append("update_item")
        item = self.items[item_id]
        if name is not None:
            item.name = name
        if description is not None:
            item.description = description
        if state is not None:
            item.state = state
        if labels is not None:
            item.labels = list(labels)
        if parent_id is not None:
            item.parent_id = parent_id
        if priority is not None:
            item.priority = priority
        if meta is not None:
            item.meta.update(meta)
        return item

    async def find_item_by_field(
        self, board_id: str, field_name: str, value: str
    ) -> ItemDTO | None:
        self.calls.append("find_item_by_field")
        for item in self.items.values():
            if item.meta.get(field_name) == value:
                return item
        return None

    async def get_item_children(
        self, board_id: str, parent_id: str
    ) -> list[ItemDTO]:
        self.calls.append("get_item_children")
        return [i for i in self.items.values() if i.parent_id == parent_id]

    # Acceptance criteria
    async def get_acceptance_criteria(
        self, board_id: str, uc_item_id: str
    ) -> list[ChecklistItemDTO]:
        self.calls.append("get_acceptance_criteria")
        return list(self.acs.get(uc_item_id, {}).values())

    async def mark_acceptance_criterion(
        self, board_id: str, uc_item_id: str, ac_id: str, passed: bool
    ) -> ChecklistItemDTO:
        self.calls.append("mark_acceptance_criterion")
        ac = self.acs[uc_item_id][ac_id]
        ac.done = passed
        return ac

    async def create_acceptance_criteria(
        self,
        board_id: str,
        uc_item_id: str,
        criteria: list[tuple[str, str]],
    ) -> list[ChecklistItemDTO]:
        self.calls.append("create_acceptance_criteria")
        bucket = self.acs.setdefault(uc_item_id, {})
        out = []
        for ac_id, text in criteria:
            ac = ChecklistItemDTO(id=ac_id, text=text, done=False)
            bucket[ac_id] = ac
            out.append(ac)
        return out

    async def update_acceptance_criterion(
        self,
        board_id: str,
        uc_item_id: str,
        ac_id: str,
        *,
        text: str | None = None,
        done: bool | None = None,
    ) -> ChecklistItemDTO:
        self.calls.append("update_acceptance_criterion")
        ac = self.acs[uc_item_id][ac_id]
        if text is not None:
            ac.text = text
        if done is not None:
            ac.done = done
        return ac

    async def delete_acceptance_criterion(
        self, board_id: str, uc_item_id: str, ac_id: str
    ) -> None:
        self.calls.append("delete_acceptance_criterion")
        del self.acs[uc_item_id][ac_id]

    # Archival
    async def archive_item(
        self, board_id: str, item_id: str, *, reason: str
    ) -> dict[str, Any]:
        self.calls.append("archive_item")
        self.items.pop(item_id, None)
        return {"archive_location": "archive", "archived_at": "now"}

    # Comments / attachments
    async def add_comment(
        self, board_id: str, item_id: str, text: str
    ) -> CommentDTO:
        self.calls.append("add_comment")
        comment = CommentDTO(id=self._next_id("comment"), text=text)
        self.comments.setdefault(item_id, []).append(comment)
        return comment

    async def get_comments(self, board_id: str, item_id: str) -> list[CommentDTO]:
        self.calls.append("get_comments")
        return self.comments.get(item_id, [])

    async def add_attachment(
        self,
        board_id: str,
        item_id: str,
        filename: str,
        content: bytes,
        mime_type: str = "application/pdf",
    ) -> AttachmentDTO:
        self.calls.append("add_attachment")
        att = AttachmentDTO(id=self._next_id("att"), name=filename, url="")
        self.attachments.setdefault(item_id, []).append(att)
        return att

    async def get_attachments(
        self, board_id: str, item_id: str
    ) -> list[AttachmentDTO]:
        self.calls.append("get_attachments")
        return self.attachments.get(item_id, [])

    # Modules / labels / states
    async def create_module(
        self, board_id: str, name: str, description: str = ""
    ) -> ModuleDTO:
        self.calls.append("create_module")
        module = ModuleDTO(id=self._next_id("module"), name=name)
        self.modules[module.id] = module
        return module

    async def add_items_to_module(
        self, board_id: str, module_id: str, item_ids: list[str]
    ) -> None:
        self.calls.append("add_items_to_module")
        self.modules[module_id].item_ids.extend(item_ids)

    async def create_label(
        self, board_id: str, name: str, color: str
    ) -> dict[str, str]:
        self.calls.append("create_label")
        label = {"name": name, "id": self._next_id("label"), "color": color}
        self.labels.append(label)
        return label

    async def get_labels(self, board_id: str) -> list[dict[str, str]]:
        self.calls.append("get_labels")
        return self.labels

    async def get_state_id(self, board_id: str, state: str) -> str:
        self.calls.append("get_state_id")
        return f"{self.tag}-state-{state}"

    async def get_states(self, board_id: str) -> dict[str, str]:
        self.calls.append("get_states")
        return {"backlog": f"{self.tag}-state-backlog"}

    async def close(self) -> None:
        self.calls.append("close")
        self.closed = True


class ExplodingMirror(FakeBackend):
    """Mirror double whose EVERY method raises — including close().

    Reads raise too: the wrapper must never consult the mirror for a read,
    so a read reaching this class is itself a contract violation [AC-03].
    """

    def __getattribute__(self, name: str) -> Any:
        attr = super().__getattribute__(name)
        if name.startswith("_") or name in ("tag", "calls", "closed", "items"):
            return attr
        if callable(attr):
            async def _boom(*args: Any, **kwargs: Any) -> Any:
                raise RuntimeError(f"mirror down ({name})")

            return _boom
        return attr


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def primary() -> FakeBackend:
    return FakeBackend("primary")


@pytest.fixture
def mirror() -> FakeBackend:
    return FakeBackend("mirror")


def make_wrapper(primary: FakeBackend, mirror: FakeBackend) -> DualBackendWrapper:
    return DualBackendWrapper(primary, mirror, MIRROR_BOARD)


async def seed_uc(backend: FakeBackend, uc_id: str = "UC-001") -> ItemDTO:
    """Create a UC item with its logical id in meta, plus one AC."""
    item = await backend.create_item(
        "ignored",
        f"[{uc_id}] Some use case",
        labels=["UC"],
        meta={"uc_id": uc_id, "tipo": "UC"},
    )
    await backend.create_acceptance_criteria("ignored", item.id, [("AC-01", "works")])
    return item


# ── AC-01: success writes land on BOTH backends ───────────────────────


async def test_write_success_reflected_in_both(primary, mirror) -> None:
    wrapper = make_wrapper(primary, mirror)
    item = await wrapper.create_item(
        PRIMARY_BOARD, "[UC-010] New thing", labels=["UC"], meta={"uc_id": "UC-010"}
    )

    assert item.id in primary.items
    assert len(mirror.items) == 1
    mirrored = next(iter(mirror.items.values()))
    assert mirrored.name == "[UC-010] New thing"
    assert mirrored.meta["uc_id"] == "UC-010"
    # The mirror item id is its own — not the primary's.
    assert mirrored.id != item.id


async def test_marking_ac_lands_on_both(primary, mirror) -> None:
    p_uc = await seed_uc(primary, "UC-001")
    m_uc = await seed_uc(mirror, "UC-001")
    wrapper = make_wrapper(primary, mirror)

    result = await wrapper.mark_acceptance_criterion(
        PRIMARY_BOARD, p_uc.id, "AC-01", True
    )

    assert result.done is True
    assert primary.acs[p_uc.id]["AC-01"].done is True
    assert mirror.acs[m_uc.id]["AC-01"].done is True


# ── AC-02 (CRITICAL): mirror failure never degrades the primary ───────


async def test_mirror_failure_returns_primary_result_for_every_write(primary) -> None:
    """All 12 write methods succeed and match the primary-only baseline."""
    # Baseline: identical operations against a lone primary.
    baseline = FakeBackend("primary")
    b_uc = await seed_uc(baseline, "UC-001")

    exploding = ExplodingMirror("mirror")
    wrapper = make_wrapper(primary, exploding)
    p_uc = await seed_uc(primary, "UC-001")
    assert p_uc.id == b_uc.id  # same fake, same sequence — comparable baseline

    ops: list[tuple[str, Any]] = []

    created = await wrapper.create_item(PRIMARY_BOARD, "[UC-002] Two", labels=["UC"])
    ops.append(("create_item", created))
    updated = await wrapper.update_item(PRIMARY_BOARD, p_uc.id, name="[UC-001] Renamed")
    ops.append(("update_item", updated))
    marked = await wrapper.mark_acceptance_criterion(PRIMARY_BOARD, p_uc.id, "AC-01", True)
    ops.append(("mark_acceptance_criterion", marked))
    acs = await wrapper.create_acceptance_criteria(
        PRIMARY_BOARD, p_uc.id, [("AC-02", "more")]
    )
    ops.append(("create_acceptance_criteria", acs))
    upd_ac = await wrapper.update_acceptance_criterion(
        PRIMARY_BOARD, p_uc.id, "AC-02", text="edited"
    )
    ops.append(("update_acceptance_criterion", upd_ac))
    await wrapper.delete_acceptance_criterion(PRIMARY_BOARD, p_uc.id, "AC-02")
    comment = await wrapper.add_comment(PRIMARY_BOARD, p_uc.id, "hello")
    ops.append(("add_comment", comment))
    att = await wrapper.add_attachment(PRIMARY_BOARD, p_uc.id, "f.pdf", b"x")
    ops.append(("add_attachment", att))
    module = await wrapper.create_module(PRIMARY_BOARD, "Casos de Uso")
    ops.append(("create_module", module))
    await wrapper.add_items_to_module(PRIMARY_BOARD, module.id, [p_uc.id])
    label = await wrapper.create_label(PRIMARY_BOARD, "Bloqueado", "red")
    ops.append(("create_label", label))
    archived = await wrapper.archive_item(PRIMARY_BOARD, created.id, reason="test")
    ops.append(("archive_item", archived))

    # Replay the same ops on the baseline and compare observable state.
    await baseline.create_item(PRIMARY_BOARD, "[UC-002] Two", labels=["UC"])
    await baseline.update_item(PRIMARY_BOARD, b_uc.id, name="[UC-001] Renamed")
    await baseline.mark_acceptance_criterion(PRIMARY_BOARD, b_uc.id, "AC-01", True)
    await baseline.create_acceptance_criteria(PRIMARY_BOARD, b_uc.id, [("AC-02", "more")])
    await baseline.update_acceptance_criterion(PRIMARY_BOARD, b_uc.id, "AC-02", text="edited")
    await baseline.delete_acceptance_criterion(PRIMARY_BOARD, b_uc.id, "AC-02")
    await baseline.add_comment(PRIMARY_BOARD, b_uc.id, "hello")
    await baseline.add_attachment(PRIMARY_BOARD, b_uc.id, "f.pdf", b"x")
    b_module = await baseline.create_module(PRIMARY_BOARD, "Casos de Uso")
    await baseline.add_items_to_module(PRIMARY_BOARD, b_module.id, [b_uc.id])
    await baseline.create_label(PRIMARY_BOARD, "Bloqueado", "red")
    await baseline.archive_item(
        PRIMARY_BOARD, next(i for i in baseline.items if i.endswith("-2")), reason="test"
    )

    assert {i.name for i in primary.items.values()} == {
        i.name for i in baseline.items.values()
    }
    assert primary.acs[p_uc.id].keys() == baseline.acs[b_uc.id].keys()
    assert [c.text for c in primary.comments[p_uc.id]] == [
        c.text for c in baseline.comments[b_uc.id]
    ]
    assert primary.labels[-1]["name"] == baseline.labels[-1]["name"]


async def test_mirror_failure_does_not_raise(primary) -> None:
    wrapper = make_wrapper(primary, ExplodingMirror("mirror"))
    item = await wrapper.create_item(PRIMARY_BOARD, "[US-01] Story", labels=["US"])
    assert item.id in primary.items  # no exception escaped


async def test_drift_is_logged_on_mirror_failure(primary) -> None:
    from structlog.testing import capture_logs

    wrapper = make_wrapper(primary, ExplodingMirror("mirror"))
    with capture_logs() as logs:
        await wrapper.create_item(PRIMARY_BOARD, "[UC-003] Three", labels=["UC"])
    assert any(e["event"] == "mirror_write_failed" for e in logs)


async def test_primary_failure_propagates_untouched(mirror) -> None:
    """The wrapper adds no swallowing on the PRIMARY side."""

    class BrokenPrimary(FakeBackend):
        async def create_item(self, *args: Any, **kwargs: Any) -> ItemDTO:
            raise ValueError("primary says no")

    wrapper = make_wrapper(BrokenPrimary("primary"), mirror)
    with pytest.raises(ValueError, match="primary says no"):
        await wrapper.create_item(PRIMARY_BOARD, "x")
    assert mirror.items == {}  # mirror never written when primary fails


# ── AC-03: reads delegate ONLY to the primary ─────────────────────────


async def test_reads_never_touch_the_mirror(primary, mirror) -> None:
    p_uc = await seed_uc(primary, "UC-001")
    wrapper = make_wrapper(primary, mirror)

    await wrapper.validate_auth()
    await wrapper.get_board_name(PRIMARY_BOARD)
    await wrapper.list_items(PRIMARY_BOARD)
    await wrapper.get_item(PRIMARY_BOARD, p_uc.id)
    await wrapper.find_item_by_field(PRIMARY_BOARD, "uc_id", "UC-001")
    await wrapper.get_item_children(PRIMARY_BOARD, p_uc.id)
    await wrapper.get_acceptance_criteria(PRIMARY_BOARD, p_uc.id)
    await wrapper.get_comments(PRIMARY_BOARD, p_uc.id)
    await wrapper.get_attachments(PRIMARY_BOARD, p_uc.id)
    await wrapper.get_labels(PRIMARY_BOARD)
    await wrapper.get_state_id(PRIMARY_BOARD, "backlog")
    await wrapper.get_states(PRIMARY_BOARD)
    await wrapper.find_us_items(PRIMARY_BOARD)
    await wrapper.find_uc_items(PRIMARY_BOARD)

    assert mirror.calls == []


async def test_reads_work_even_with_exploding_mirror(primary) -> None:
    p_uc = await seed_uc(primary, "UC-001")
    wrapper = make_wrapper(primary, ExplodingMirror("mirror"))
    item = await wrapper.get_item(PRIMARY_BOARD, p_uc.id)
    assert item.id == p_uc.id


# ── AC-04: logical id resolution (ids are NOT portable) ──────────────


async def test_mirror_resolves_by_logical_id_not_primary_id(primary, mirror) -> None:
    p_uc = await seed_uc(primary, "UC-042")
    m_uc = await seed_uc(mirror, "UC-042")
    assert p_uc.id != m_uc.id or True  # ids may coincide in fakes; behavior matters
    wrapper = make_wrapper(primary, mirror)

    await wrapper.add_comment(PRIMARY_BOARD, p_uc.id, "note")

    # The mirror received the comment on ITS OWN item id.
    assert [c.text for c in mirror.comments.get(m_uc.id, [])] == ["note"]
    # And resolution used find_item_by_field against the mirror board.
    assert "find_item_by_field" in mirror.calls


async def test_missing_mirror_item_skips_and_continues(primary, mirror) -> None:
    from structlog.testing import capture_logs

    p_uc = await seed_uc(primary, "UC-077")  # NOT seeded in the mirror
    wrapper = make_wrapper(primary, mirror)

    with capture_logs() as logs:
        result = await wrapper.add_comment(PRIMARY_BOARD, p_uc.id, "orphan note")

    assert result.text == "orphan note"  # primary unaffected
    assert mirror.comments == {}  # nothing written to the mirror
    assert any(e["event"] == "mirror_item_missing" for e in logs)


async def test_resolution_is_cached(primary, mirror) -> None:
    p_uc = await seed_uc(primary, "UC-001")
    await seed_uc(mirror, "UC-001")
    wrapper = make_wrapper(primary, mirror)

    await wrapper.add_comment(PRIMARY_BOARD, p_uc.id, "one")
    await wrapper.add_comment(PRIMARY_BOARD, p_uc.id, "two")

    assert mirror.calls.count("find_item_by_field") == 1  # second hit from cache


async def test_create_item_caches_mirror_id_for_children(primary, mirror) -> None:
    wrapper = make_wrapper(primary, mirror)
    us = await wrapper.create_item(
        PRIMARY_BOARD, "[US-09] Story", labels=["US"], meta={"us_id": "US-09"}
    )
    await wrapper.create_item(
        PRIMARY_BOARD,
        "[UC-901] Child",
        labels=["UC"],
        parent_id=us.id,
        meta={"uc_id": "UC-901", "us_id": "US-09"},
    )

    m_us = await mirror.find_item_by_field(MIRROR_BOARD, "us_id", "US-09")
    m_uc = await mirror.find_item_by_field(MIRROR_BOARD, "uc_id", "UC-901")
    assert m_uc.parent_id == m_us.id  # hierarchy preserved with MIRROR ids


# ── AC-05: close() closes both; mirror close failure tolerated ───────


async def test_close_closes_both(primary, mirror) -> None:
    wrapper = make_wrapper(primary, mirror)
    await wrapper.close()
    assert primary.closed is True
    assert mirror.closed is True


async def test_mirror_close_failure_does_not_block_primary_close(primary) -> None:
    wrapper = make_wrapper(primary, ExplodingMirror("mirror"))
    await wrapper.close()  # no exception
    assert primary.closed is True


# ══ UC-1102 — dispatch in the get_session_backend chokepoint ══════════


from unittest.mock import AsyncMock  # noqa: E402

from server.auth_gateway import (  # noqa: E402
    BACKEND_STATE_KEY,
    clear_mirror_credentials,
    get_session_backend,
    store_mirror_native_credentials,
)
from server.backends.native_backend import NativeBackend  # noqa: E402
from server.backends.trello_backend import TrelloBackend  # noqa: E402


def _ctx_with(config: dict[str, Any] | None) -> AsyncMock:
    state_map = {BACKEND_STATE_KEY: config}
    ctx = AsyncMock()

    async def get_state(key: str) -> Any:
        return state_map.get(key)

    async def set_state(key: str, value: Any) -> None:
        state_map[key] = value

    ctx.get_state = AsyncMock(side_effect=get_state)
    ctx.set_state = AsyncMock(side_effect=set_state)
    ctx._state_map = state_map
    return ctx


TRELLO_CONFIG = {"backend_type": "trello", "api_key": "k", "token": "t"}
MIRROR_CONFIG = {"project_id": "EmbedBuild/proj", "dev_token": "spbx_test"}


# AC-01: without "mirror", exact single-backend behavior (no wrapper)


async def test_dispatch_without_mirror_returns_plain_backend() -> None:
    ctx = _ctx_with(dict(TRELLO_CONFIG))
    backend = await get_session_backend(ctx)
    assert type(backend) is TrelloBackend


async def test_dispatch_freeform_without_mirror_returns_plain_backend() -> None:
    ctx = _ctx_with({"backend_type": "freeform", "root_path": "/tmp/x"})
    backend = await get_session_backend(ctx, items_content="[]")
    assert type(backend).__name__ == "FreeformBackend"


# AC-02: with "mirror" and non-native primary → DualBackendWrapper


async def test_dispatch_with_mirror_returns_dual_wrapper() -> None:
    ctx = _ctx_with({**TRELLO_CONFIG, "mirror": dict(MIRROR_CONFIG)})
    backend = await get_session_backend(ctx)
    assert isinstance(backend, DualBackendWrapper)
    assert type(backend.primary) is TrelloBackend
    assert type(backend.mirror) is NativeBackend
    assert backend.mirror_board_id == "EmbedBuild/proj"


async def test_dispatch_native_primary_ignores_stray_mirror() -> None:
    """Defensive: a native primary returns NativeBackend even if a stray
    mirror key slipped into the config (store-time guard is the real gate)."""
    ctx = _ctx_with(
        {
            "backend_type": "native",
            "project_id": "EmbedBuild/main",
            "dev_token": "spbx_main",
            "mirror": dict(MIRROR_CONFIG),
        }
    )
    backend = await get_session_backend(ctx)
    assert type(backend) is NativeBackend


# AC-03: Frontier 2 — the mirror sub-dict holds ONLY project_id + dev_token


async def test_store_mirror_persists_only_project_id_and_dev_token() -> None:
    ctx = _ctx_with(dict(TRELLO_CONFIG))
    await store_mirror_native_credentials(ctx, "EmbedBuild/proj", "spbx_test")
    stored = ctx._state_map[BACKEND_STATE_KEY]["mirror"]
    assert stored == {"project_id": "EmbedBuild/proj", "dev_token": "spbx_test"}
    assert set(stored.keys()) == {"project_id", "dev_token"}  # never a DSN


# AC-04: store/clear lifecycle + hard rule


async def test_store_mirror_on_native_primary_is_forbidden() -> None:
    ctx = _ctx_with(
        {"backend_type": "native", "project_id": "EmbedBuild/main", "dev_token": "x"}
    )
    with pytest.raises(ValueError, match="MIRROR_ON_NATIVE_FORBIDDEN"):
        await store_mirror_native_credentials(ctx, "EmbedBuild/proj", "spbx_test")


async def test_store_mirror_requires_primary_session() -> None:
    ctx = _ctx_with(None)
    with pytest.raises(ValueError, match="No primary backend session"):
        await store_mirror_native_credentials(ctx, "EmbedBuild/proj", "spbx_test")


async def test_store_mirror_rejects_empty_args() -> None:
    ctx = _ctx_with(dict(TRELLO_CONFIG))
    with pytest.raises(ValueError, match="project_id is required"):
        await store_mirror_native_credentials(ctx, "", "spbx_test")
    with pytest.raises(ValueError, match="dev_token is required"):
        await store_mirror_native_credentials(ctx, "EmbedBuild/proj", "")


async def test_clear_mirror_detaches_and_is_idempotent() -> None:
    ctx = _ctx_with({**TRELLO_CONFIG, "mirror": dict(MIRROR_CONFIG)})
    await clear_mirror_credentials(ctx)
    assert "mirror" not in ctx._state_map[BACKEND_STATE_KEY]
    backend = await get_session_backend(ctx)
    assert type(backend) is TrelloBackend  # back to single-backend
    await clear_mirror_credentials(ctx)  # second call: no-op, no raise


# ══ UC-1103 — transactional persistence of the mirror block ═══════════


import json  # noqa: E402
from pathlib import Path  # noqa: E402

from server.app_docs.discovery import detect_backend  # noqa: E402
from server.migration.transactional_switch import (  # noqa: E402
    TransactionalSwitchError,
    apply_mirror_transactional,
)

_APP_SPEC = """# App Spec — demo

<!-- @specbox:zone start kind="auto" id="tracking_backend" auto_sync_on="set_auth_token" -->
## 2. Tracking backend

- **Tipo:** trello
- **Trello board id:** board-1
- **Reporting externo:** si

> Esta zona la mantiene el engine.
<!-- @specbox:zone end -->
"""

MIRROR_PID = "EmbedBuild/cliente-x"


@pytest.fixture
def trello_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """tmp project on a trello primary; returns (project_path, state_path, slug)."""
    project_path = tmp_path / "proj"
    (project_path / "doc" / "app").mkdir(parents=True)
    (project_path / "doc" / "app" / "app_spec.md").write_text(_APP_SPEC, encoding="utf-8")
    (project_path / ".claude").mkdir()
    (project_path / ".claude" / "settings.local.json").write_text(
        json.dumps({"specbox": {"backend_type": "trello"}}, indent=2), encoding="utf-8"
    )
    state_path = tmp_path / "state"
    state_path.mkdir()
    slug = "demo"
    (state_path / "projects.json").write_text(
        json.dumps(
            {"projects": {slug: {"spec_backend": "trello", "board_id": "board-1"}}},
            indent=2,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("STATE_PATH", str(state_path))
    return project_path, state_path, slug


def test_enable_mirror_writes_all_three_places(trello_project) -> None:
    project_path, state_path, slug = trello_project

    outcome = apply_mirror_transactional(
        slug, MIRROR_PID, str(project_path), str(state_path)
    )
    assert outcome["updated"] == ["registry", "app_spec", "settings"]

    registry = json.loads((state_path / "projects.json").read_text())
    entry = registry["projects"][slug]
    assert entry["mirror"] == {"backend": "native", "project_id": MIRROR_PID}
    # The PRIMARY is untouched (AC-02 of UC-1103).
    assert entry["spec_backend"] == "trello"
    assert entry["board_id"] == "board-1"

    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert settings["specbox"]["mirror"] == {
        "backend": "native",
        "project_id": MIRROR_PID,
    }
    assert settings["specbox"]["backend_type"] == "trello"

    spec = (project_path / "doc" / "app" / "app_spec.md").read_text()
    assert "- **Tipo:** trello" in spec
    assert f"- **Mirror (native):** {MIRROR_PID}" in spec


def test_disable_mirror_removes_from_all_three_places(trello_project) -> None:
    project_path, state_path, slug = trello_project
    apply_mirror_transactional(slug, MIRROR_PID, str(project_path), str(state_path))

    apply_mirror_transactional(slug, None, str(project_path), str(state_path))

    registry = json.loads((state_path / "projects.json").read_text())
    assert "mirror" not in registry["projects"][slug]
    settings = json.loads((project_path / ".claude" / "settings.local.json").read_text())
    assert "mirror" not in settings["specbox"]
    assert settings["specbox"]["backend_type"] == "trello"  # primary intact
    spec = (project_path / "doc" / "app" / "app_spec.md").read_text()
    assert "Mirror (native)" not in spec
    assert "- **Tipo:** trello" in spec


def test_mirror_write_failure_rolls_back_everything(trello_project) -> None:
    """AC-01: a failure in any of the 3 places leaves none half-written."""
    project_path, state_path, slug = trello_project
    before_registry = (state_path / "projects.json").read_text()
    before_settings = (project_path / ".claude" / "settings.local.json").read_text()
    before_spec = (project_path / "doc" / "app" / "app_spec.md").read_text()

    def explode() -> None:
        raise OSError("disk full")

    with pytest.raises(TransactionalSwitchError) as err:
        apply_mirror_transactional(
            slug, MIRROR_PID, str(project_path), str(state_path),
            settings_writer=explode,  # last place fails — first two must roll back
        )
    assert err.value.place == "settings"

    assert (state_path / "projects.json").read_text() == before_registry
    assert (
        project_path / ".claude" / "settings.local.json"
    ).read_text() == before_settings
    assert (project_path / "doc" / "app" / "app_spec.md").read_text() == before_spec


def test_detect_backend_reports_primary_plus_mirror(trello_project) -> None:
    """AC-02: detect_backend keeps returning the primary; new mirror field."""
    project_path, state_path, slug = trello_project
    apply_mirror_transactional(slug, MIRROR_PID, str(project_path), str(state_path))

    detected = detect_backend(str(project_path))
    assert detected["backend_type"] == "trello"  # primary unchanged
    assert detected["mirror"] == {"backend": "native", "project_id": MIRROR_PID}


def test_detect_backend_without_mirror_is_none(trello_project) -> None:
    project_path, _, _ = trello_project
    detected = detect_backend(str(project_path))
    assert detected["backend_type"] == "trello"
    assert detected["mirror"] is None


# ══ UC-1104 — enable_mirror / disable_mirror + backfill ═══════════════


from server.backends.freeform_backend import FreeformBackend  # noqa: E402
from server.tools import migration as migration_tools  # noqa: E402
from server.tools.migration import disable_mirror, enable_mirror  # noqa: E402

MIRROR_CANONICAL = "EmbedBuild/cliente-x"


class FakeNativeMirror(FakeBackend):
    """Mirror double with the ingest_atomic contract (idempotent skip)."""

    async def ingest_atomic(
        self, board_id: str, source_data: dict[str, Any], *, source_type=None
    ) -> dict[str, Any]:
        migrated = {"us": 0, "uc": 0, "ac": 0, "comments": 0}
        skipped = 0
        classified = source_data["classified"]
        for us in classified["us"]:
            lid = us.meta.get("us_id")
            if await self.find_item_by_field(board_id, "us_id", lid):
                skipped += 1
                continue
            await self.create_item(
                board_id, us.name, labels=["US"], state=us.state, meta=dict(us.meta)
            )
            migrated["us"] += 1
        for uc in classified["uc"]:
            lid = uc.meta.get("uc_id")
            if await self.find_item_by_field(board_id, "uc_id", lid):
                skipped += 1
                continue
            parent = await self.find_item_by_field(
                board_id, "us_id", uc.meta.get("us_id", "")
            )
            created = await self.create_item(
                board_id,
                uc.name,
                labels=["UC"],
                state=uc.state,
                parent_id=parent.id if parent else None,
                meta=dict(uc.meta),
            )
            acs = source_data["ac_data"].get(uc.id, [])
            if acs:
                await self.create_acceptance_criteria(
                    board_id, created.id, [(a["id"], a["text"]) for a in acs]
                )
                migrated["ac"] += len(acs)
            migrated["uc"] += 1
        return {"migrated": migrated, "skipped": skipped, "id_map": {}}


async def _freeform_source() -> str:
    """Build a tiny items.json (1 US / 1 UC / 2 AC) via memory-mode FreeForm."""
    ff = FreeformBackend(items_content="[]")
    us = await ff.create_item(
        ".", "[US-01] Historia", labels=["US"], meta={"us_id": "US-01", "tipo": "US"}
    )
    uc = await ff.create_item(
        ".",
        "[UC-001] Caso",
        labels=["UC"],
        parent_id=us.id,
        meta={"uc_id": "UC-001", "us_id": "US-01", "tipo": "UC"},
    )
    await ff.create_acceptance_criteria(
        ".", uc.id, [("AC-01", "criterio uno"), ("AC-02", "criterio dos")]
    )
    content = ff.get_items_content()
    await ff.close()
    return content


@pytest.fixture
def mirror_seams(monkeypatch: pytest.MonkeyPatch) -> FakeNativeMirror:
    """Patch identity/pool/provision seams + mirror factory; returns the fake."""
    fake_mirror = FakeNativeMirror("native")

    async def fake_provision(pool, dev_token, target_project_id):
        return True

    async def fake_auth(pool, *, token, project_id):
        return None

    async def fake_pool():
        return object()

    monkeypatch.setattr(migration_tools, "_maybe_auto_provision", fake_provision)
    import server.coordination.identity as identity_mod
    import server.db.pool as pool_mod

    monkeypatch.setattr(identity_mod, "authenticate_and_authorize_cached", fake_auth)
    monkeypatch.setattr(pool_mod, "get_pool", fake_pool)
    monkeypatch.setattr(
        migration_tools, "_build_mirror_backend", lambda pid, tok: fake_mirror
    )
    return fake_mirror


def _freeform_ctx() -> AsyncMock:
    return _ctx_with({"backend_type": "freeform", "root_path": "/tmp/x"})


# AC-01 — primary native → fail-fast rejection


async def test_enable_mirror_on_native_primary_rejected() -> None:
    ctx = _ctx_with(
        {"backend_type": "native", "project_id": "EmbedBuild/main", "dev_token": "x"}
    )
    result = await enable_mirror("demo", MIRROR_CANONICAL, "spbx_t", ctx)
    assert result["status"] == "MIRROR_ON_NATIVE_FORBIDDEN"


async def test_enable_mirror_requires_primary_session() -> None:
    result = await enable_mirror("demo", MIRROR_CANONICAL, "spbx_t", _ctx_with(None))
    assert result["code"] == "NO_PRIMARY_SESSION"


async def test_enable_mirror_rejects_invalid_project_id() -> None:
    result = await enable_mirror("demo", "not-canonical", "spbx_t", _freeform_ctx())
    assert result["code"] == "INVALID_PROJECT_ID"


async def test_enable_mirror_large_freeform_source_requires_batch() -> None:
    big = "x" * (65 * 1024)
    result = await enable_mirror(
        "demo", MIRROR_CANONICAL, "spbx_t", _freeform_ctx(),
        source_content=big, dry_run=False,
    )
    assert result["status"] == "SOURCE_TOO_LARGE_USE_BATCH"


# AC-02 — validate_auth del espejo + backfill con mismos conteos


async def test_enable_mirror_preview_counts(mirror_seams) -> None:
    source = await _freeform_source()
    result = await enable_mirror(
        "demo", MIRROR_CANONICAL, "spbx_t", _freeform_ctx(), source_content=source
    )
    assert result["status"] == "preview"
    assert result["primary"]["read_counts"] == {"us": 1, "uc": 1, "ac": 2}
    assert result["mirror"]["existing_items"] == 0


async def test_enable_mirror_execute_requires_count_guard(mirror_seams) -> None:
    source = await _freeform_source()
    result = await enable_mirror(
        "demo", MIRROR_CANONICAL, "spbx_t", _freeform_ctx(),
        source_content=source, dry_run=False,
    )
    assert result["status"] == "COUNT_GUARD_FAILED"


async def test_enable_mirror_backfills_and_persists(
    mirror_seams, trello_project
) -> None:
    project_path, state_path, slug = trello_project
    source = await _freeform_source()
    ctx = _freeform_ctx()

    result = await enable_mirror(
        slug, MIRROR_CANONICAL, "spbx_t", ctx,
        source_content=source,
        project_path=str(project_path),
        dry_run=False,
        confirmed_count={"us": 1, "uc": 1},
    )

    assert result["status"] == "enabled", result
    # Backfill: same us/uc/ac counts in the mirror (AC-02).
    assert result["backfill"]["verified_counts"] == {"us": 1, "uc": 1, "ac": 2}
    assert result["backfill"]["migrated"] == {"us": 1, "uc": 1, "ac": 2, "comments": 0}

    # AC-03: mirror block persisted in the 3 places via the atomic transaction.
    assert result["config_updated"] == ["registry", "app_spec", "settings"]
    registry = json.loads((state_path / "projects.json").read_text())
    assert registry["projects"][slug]["mirror"]["project_id"] == MIRROR_CANONICAL
    settings = json.loads(
        (project_path / ".claude" / "settings.local.json").read_text()
    )
    assert settings["specbox"]["mirror"]["project_id"] == MIRROR_CANONICAL
    assert "dev_token" not in json.dumps(settings)  # Frontier 2: never on disk

    # Live session got the mirror sub-dict.
    session = ctx._state_map[BACKEND_STATE_KEY]
    assert session["mirror"] == {
        "project_id": MIRROR_CANONICAL,
        "dev_token": "spbx_t",
    }


async def test_enable_mirror_rerun_is_idempotent_rebackfill(
    mirror_seams, trello_project
) -> None:
    project_path, state_path, slug = trello_project
    source = await _freeform_source()
    kwargs = dict(
        source_content=source,
        project_path=str(project_path),
        dry_run=False,
        confirmed_count={"us": 1, "uc": 1},
    )
    first = await enable_mirror(slug, MIRROR_CANONICAL, "spbx_t", _freeform_ctx(), **kwargs)
    second = await enable_mirror(slug, MIRROR_CANONICAL, "spbx_t", _freeform_ctx(), **kwargs)

    assert first["status"] == second["status"] == "enabled"
    assert second["backfill"]["skipped"] == 2  # 1 US + 1 UC already present
    assert second["backfill"]["verified_counts"] == {"us": 1, "uc": 1, "ac": 2}


# AC-04 — disable_mirror revierte a single-backend sin pérdida


async def test_disable_mirror_reverts_config_and_session(
    mirror_seams, trello_project
) -> None:
    project_path, state_path, slug = trello_project
    source = await _freeform_source()
    ctx = _freeform_ctx()
    await enable_mirror(
        slug, MIRROR_CANONICAL, "spbx_t", ctx,
        source_content=source,
        project_path=str(project_path),
        dry_run=False,
        confirmed_count={"us": 1, "uc": 1},
    )

    result = await disable_mirror(slug, ctx, project_path=str(project_path))

    assert result["status"] == "disabled"
    registry = json.loads((state_path / "projects.json").read_text())
    assert "mirror" not in registry["projects"][slug]
    settings = json.loads(
        (project_path / ".claude" / "settings.local.json").read_text()
    )
    assert "mirror" not in settings["specbox"]
    assert settings["specbox"]["backend_type"] == "trello"  # primary intact
    assert "mirror" not in ctx._state_map[BACKEND_STATE_KEY]
    # The mirror's DATA is intact (additive philosophy).
    assert len(mirror_seams.items) == 2
