"""Tier 3 tests — board_operations.py (v5.23.0).

See doc/design/v5.23.0-full-mutations.md → "Tier 3 test plan".
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

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
from server.tools import board_operations as bo


# ── In-memory backend ────────────────────────────────────────────────


class InMemoryBackend(SpecBackend):
    def __init__(self):
        self.items: dict[str, ItemDTO] = {}
        self.acs: dict[str, list[ChecklistItemDTO]] = {}
        self.comments: list[tuple[str, str]] = []
        self.archived: list[str] = []
        self.closed = False
        self._next_id = 1

    def _new_id(self, prefix="id"):
        self._next_id += 1
        return f"{prefix}-{self._next_id}"

    async def validate_auth(self):
        return BackendUser(id="u", username="t", display_name="T")

    async def setup_board(self, name):
        return BoardConfig(board_id="b", board_url="", states={}, labels={}, custom_fields={})

    async def get_board_name(self, board_id):
        return "B"

    async def list_items(self, board_id):
        return list(self.items.values())

    async def get_item(self, board_id, item_id):
        return self.items[item_id]

    async def create_item(self, board_id, name, description="", state="backlog",
                          labels=None, parent_id=None, priority="none",
                          external_source="", external_id="", meta=None):
        iid = self._new_id("item")
        item = ItemDTO(id=iid, name=name, description=description, state=state,
                       labels=list(labels or []), parent_id=parent_id, url=f"u/{iid}",
                       meta=dict(meta or {}))
        self.items[iid] = item
        return item

    async def update_item(self, board_id, item_id, *, name=None, description=None,
                          state=None, labels=None, parent_id=None, priority=None,
                          external_source=None, external_id=None, meta=None):
        item = self.items[item_id]
        if name is not None: item.name = name
        if description is not None: item.description = description
        if state is not None: item.state = state
        if labels is not None: item.labels = list(labels)
        if meta is not None: item.meta = dict(meta)
        return item

    async def find_item_by_field(self, board_id, field_name, value):
        for i in self.items.values():
            if i.meta.get(field_name) == value:
                return i
        return None

    async def get_item_children(self, board_id, parent_id):
        return [i for i in self.items.values() if i.parent_id == parent_id]

    async def get_acceptance_criteria(self, board_id, uc_item_id):
        return list(self.acs.get(uc_item_id, []))

    async def mark_acceptance_criterion(self, board_id, uc_item_id, ac_id, passed, evidence=None):
        for ac in self.acs.get(uc_item_id, []):
            if ac.id == ac_id:
                ac.done = passed
                return ac
        raise ValueError()

    async def create_acceptance_criteria(self, board_id, uc_item_id, criteria):
        created = []
        for ac_id, text in criteria:
            cl = ChecklistItemDTO(id=ac_id, text=text, done=False, backend_id=self._new_id("ac"))
            self.acs.setdefault(uc_item_id, []).append(cl)
            created.append(cl)
        return created

    async def update_acceptance_criterion(self, board_id, uc_item_id, ac_id, *, text=None, done=None):
        for ac in self.acs.get(uc_item_id, []):
            if ac.id == ac_id:
                if text is not None: ac.text = text
                if done is not None: ac.done = done
                return ac
        raise ValueError()

    async def delete_acceptance_criterion(self, board_id, uc_item_id, ac_id):
        acs = self.acs.get(uc_item_id, [])
        for idx, ac in enumerate(acs):
            if ac.id == ac_id:
                acs.pop(idx)
                return
        raise ValueError()

    async def archive_item(self, board_id, item_id, *, reason):
        self.archived.append(item_id)
        if item_id in self.items:
            del self.items[item_id]
        from server.tools._mutation_helpers import utc_now_iso
        return {"archive_location": "test_archive", "archived_at": utc_now_iso()}

    async def add_comment(self, board_id, item_id, text):
        self.comments.append((item_id, text))
        return CommentDTO(id=self._new_id("c"), text=text)

    async def get_comments(self, *a):
        return []

    async def add_attachment(self, *a, **kw):
        return AttachmentDTO(id="a", name="f", url="")

    async def get_attachments(self, *a):
        return []

    async def create_module(self, board_id, name, description=""):
        return ModuleDTO(id="m", name=name)

    async def add_items_to_module(self, *a):
        return None

    async def create_label(self, board_id, name, color):
        return {"id": "l", "name": name, "color": color}

    async def get_labels(self, *a):
        return []

    async def get_state_id(self, board_id, state):
        return state

    async def get_states(self, *a):
        return {}

    async def close(self):
        self.closed = True


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def ctx(backend, monkeypatch):
    async def _fake(c, items_content=None):
        return backend
    monkeypatch.setattr(bo, "get_session_backend", _fake)
    return AsyncMock()


async def _seed(backend, n_ucs=3):
    us = await backend.create_item("b", "US-01: X", labels=["US"], meta={"us_id": "US-01"})
    ucs = []
    for i in range(1, n_ucs + 1):
        uc_id = f"UC-{i:03d}"
        uc = await backend.create_item(
            "b", f"{uc_id}: F{i}", labels=["UC"], parent_id=us.id,
            meta={"uc_id": uc_id, "us_id": "US-01"},
        )
        ac_pairs = [
            (f"AC-{j:02d}", [
                f"Dado un usuario autenticado cuando ejecuta accion {j} entonces debe ver resultado correcto",
                f"El sistema debe responder en menos de 200ms para la operacion {j} del caso de uso",
                f"Cuando el usuario ingresa datos invalidos el sistema debe mostrar un mensaje de error descriptivo",
            ][j - 1])
            for j in range(1, 4)
        ]
        await backend.create_acceptance_criteria("b", uc.id, ac_pairs)
        ucs.append(uc)
    return us, ucs


# ── validate_ac_quality ──────────────────────────────────────────────


async def test_validate_ac_quality_flags_short_acs(backend, ctx):
    us, ucs = await _seed(backend)
    # Override one AC to be too short
    backend.acs[ucs[0].id][0].text = "short"
    result = await bo.validate_ac_quality("b", ctx)
    assert result["total_acs"] == 9
    assert len(result["failed"]) >= 1
    bad = result["failed"][0]
    assert "too_short" in bad["issues"]


async def test_validate_ac_quality_single_uc(backend, ctx):
    _, ucs = await _seed(backend)
    backend.acs[ucs[0].id][0].text = "x"
    result = await bo.validate_ac_quality("b", ctx, uc_id="UC-002")
    # Only UC-002's ACs should be checked
    assert result["total_acs"] == 3
    assert result["passed"] == 3  # UC-002 ACs are fine


# ── US-33/UC-3303: avisos de exposición ──────────────────────────────


async def test_validate_ac_quality_reports_exposure_in_its_own_list(backend, ctx):
    """AC-01/AC-02: el aviso sale en `warnings`, NO en `failed`."""
    _, ucs = await _seed(backend)
    backend.acs[ucs[0].id][0].text = (
        "el sistema devuelve la contraseña de la cuenta enmascarada en el detalle"
    )
    result = await bo.validate_ac_quality("b", ctx)

    avisados = [w for w in result["warnings"] if "exposure_warning" in w["warnings"]]
    assert len(avisados) == 1
    assert "exposure_credentials" in avisados[0]["warnings"]
    assert result["exposure_warnings"] == 1

    # Y NO aparece entre los fallos de calidad: son dos ejes distintos.
    assert all(a["ac_id"] != avisados[0]["ac_id"] for a in result["failed"])


async def test_exposure_warning_does_not_move_pass_rate(backend, ctx):
    """AC-02: avisa pero no bloquea el Definition Quality Gate.

    Se compara el `pass_rate` del mismo board con y sin un AC que expone
    credenciales. Si el aviso contara, este test fallaría — y con él el gate
    empezaría a bloquear por un eje que solo pretende dar visibilidad.
    """
    _, ucs = await _seed(backend)
    limpio = await bo.validate_ac_quality("b", ctx)

    backend.acs[ucs[0].id][0].text = (
        "el sistema devuelve la contraseña de la cuenta enmascarada en el detalle"
    )
    con_aviso = await bo.validate_ac_quality("b", ctx)

    assert con_aviso["exposure_warnings"] == 1
    assert con_aviso["pass_rate"] == limpio["pass_rate"]
    assert con_aviso["passed"] == limpio["passed"]
    assert len(con_aviso["failed"]) == len(limpio["failed"])


async def test_board_without_exposure_reports_empty_warnings(backend, ctx):
    await _seed(backend)
    result = await bo.validate_ac_quality("b", ctx)
    assert result["warnings"] == []
    assert result["exposure_warnings"] == 0


# ── set_ac_metadata ──────────────────────────────────────────────────


async def test_set_ac_metadata_stores_evidence(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.set_ac_metadata(
        "b", "UC-001", "AC-01", ctx,
        evidence_url="https://example.com/evidence.html",
        verdict="ACCEPTED",
    )
    assert result.get("error") is None
    assert result["metadata"]["evidence_url"] == "https://example.com/evidence.html"
    assert result["metadata"]["verdict"] == "ACCEPTED"
    # Verify text was updated with META suffix
    ac = backend.acs[ucs[0].id][0]
    assert "[META:" in ac.text


async def test_set_ac_metadata_invalid_verdict(backend, ctx):
    await _seed(backend)
    result = await bo.set_ac_metadata("b", "UC-001", "AC-01", ctx, verdict="BOGUS")
    assert result["code"] == "VALIDATION_FAILED"


# ── link_uc_parent ───────────────────────────────────────────────────


async def test_link_uc_parent_creates_comments_on_both(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.link_uc_parent("b", "UC-001", "UC-002", "absorbs", ctx)
    assert result.get("error") is None
    assert result["link_type"] == "absorbs"
    # Comments on both cards
    commented_ids = {c[0] for c in backend.comments}
    assert ucs[0].id in commented_ids
    assert ucs[1].id in commented_ids
    # Link stored in meta
    links = backend.items[ucs[0].id].meta.get("links", [])
    assert any(l["target_uc_id"] == "UC-002" for l in links)


async def test_link_uc_parent_idempotent(backend, ctx):
    await _seed(backend)
    await bo.link_uc_parent("b", "UC-001", "UC-002", "depends_on", ctx)
    r2 = await bo.link_uc_parent("b", "UC-001", "UC-002", "depends_on", ctx)
    assert r2.get("reason") == "no_change"


# ── delete_uc ────────────────────────────────────────────────────────


async def test_delete_uc_archives(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.delete_uc("b", "UC-001", "obsolete", ctx)
    assert result.get("error") is None
    assert result["archive_location"] == "test_archive"
    assert ucs[0].id in backend.archived


async def test_delete_uc_with_absorbed_by_links_first(backend, ctx):
    _, ucs = await _seed(backend)
    result = await bo.delete_uc("b", "UC-003", "absorbed", ctx, absorbed_by="UC-001")
    assert result["absorbed_by"] == "UC-001"
    # Link added before archival
    assert ucs[2].id in backend.archived
    # Comment on parent
    assert any("absorbs" in c[1] for c in backend.comments)


# ── get_board_diff ───────────────────────────────────────────────────


SNAP_FROM = {
    "items": [
        {"uc_id": "UC-001", "name": "Login", "state": "backlog", "milestone": "H1", "ac_count": 3, "ac_done": 0},
        {"uc_id": "UC-002", "name": "Register", "state": "backlog", "milestone": "H1", "ac_count": 2, "ac_done": 1},
        {"uc_id": "UC-003", "name": "Removed", "state": "backlog", "milestone": "H2", "ac_count": 1, "ac_done": 0},
    ]
}
SNAP_TO = {
    "items": [
        {"uc_id": "UC-001", "name": "Login", "state": "done", "milestone": "H1", "ac_count": 3, "ac_done": 3},
        {"uc_id": "UC-002", "name": "Register", "state": "backlog", "milestone": "H2", "ac_count": 2, "ac_done": 1},
        {"uc_id": "UC-004", "name": "New UC", "state": "backlog", "milestone": "H3", "ac_count": 5, "ac_done": 0},
    ]
}


def _check_diff(result: dict) -> None:
    assert result["added_ucs"] == ["UC-004"]
    assert result["removed_ucs"] == ["UC-003"]
    # UC-001 changed state; the milestone of UC-002 no longer counts (removed in v6.23.0)
    assert result["modified_ucs"] == [{"uc_id": "UC-001", "changes": {"state": ["backlog", "done"]}}]
    assert "milestone_moves" not in result
    assert result["ac_changes"]["passed_delta"] == 3  # UC-001 went 0→3


@pytest.fixture
def no_disk(monkeypatch):
    """Fail on any filesystem call while armed."""
    import builtins
    import pathlib

    armed = {"on": False}

    def trip(original):
        def wrapper(*a, **k):
            if armed["on"]:
                raise AssertionError("disk access")
            return original(*a, **k)

        return wrapper

    for name in ("read_text", "exists", "open", "is_file"):
        monkeypatch.setattr(pathlib.Path, name, trip(getattr(pathlib.Path, name)))
    monkeypatch.setattr(builtins, "open", trip(builtins.open))
    return armed


async def test_board_diff_detects_changes(tmp_path, ctx, monkeypatch):
    board_dir = tmp_path / ".quality" / "board_snapshots" / "board1"
    board_dir.mkdir(parents=True)
    (board_dir / "snap1.json").write_text(json.dumps(SNAP_FROM))
    (board_dir / "snap2.json").write_text(json.dumps(SNAP_TO))

    monkeypatch.chdir(tmp_path)
    _check_diff(await bo.get_board_diff("board1", "snap1", "snap2", ctx))


async def test_board_diff_reads_an_owner_repo_board_locally(tmp_path, ctx, monkeypatch):
    board_dir = tmp_path / ".quality" / "board_snapshots" / "Owner" / "repo"
    board_dir.mkdir(parents=True)
    (board_dir / "a.json").write_text(json.dumps(SNAP_FROM))
    (board_dir / "b.json").write_text(json.dumps(SNAP_TO))

    monkeypatch.chdir(tmp_path)
    _check_diff(await bo.get_board_diff("Owner/repo", "a", "b", ctx))


async def test_board_diff_compares_the_content_sent_without_touching_disk(tmp_path, ctx, monkeypatch, no_disk):
    monkeypatch.chdir(tmp_path)
    no_disk["on"] = True
    result = await bo.get_board_diff(
        "board1", "snap1", "snap2", ctx, from_content=json.dumps(SNAP_FROM), to_content=json.dumps(SNAP_TO)
    )
    no_disk["on"] = False
    _check_diff(result)


@pytest.mark.parametrize("given", ["from_content", "to_content"])
async def test_board_diff_needs_both_snapshots(ctx, no_disk, given):
    no_disk["on"] = True
    result = await bo.get_board_diff("board1", "snap1", "snap2", ctx, **{given: json.dumps(SNAP_FROM)})
    no_disk["on"] = False
    assert result["code"] == "VALIDATION_FAILED"
    assert "from_content and to_content" in result["error"]


@pytest.mark.parametrize("content", ["not json", "[1, 2]", "null"])
async def test_board_diff_rejects_a_snapshot_that_is_not_an_object(ctx, content):
    result = await bo.get_board_diff("board1", "a", "b", ctx, from_content=content, to_content=json.dumps(SNAP_TO))
    assert result["code"] == "VALIDATION_FAILED"
    assert "from_content is not a board snapshot" in result["error"]


@pytest.mark.parametrize(
    ("board_id", "snapshot"),
    [
        ("", "snap1"),
        ("../../data/state/projects/x", "meta"),
        ("/etc", "snap1"),
        ("a/b/c", "snap1"),
        ("a\\b", "snap1"),
        ("a\x00", "snap1"),
        ("..", "snap1"),
        ("board1", ".."),
        ("board1", "../../../meta"),
        ("board1", "a/b"),
        ("board1", "a\\b"),
        ("board1", ""),
        ("board1", " snap1"),
    ],
)
async def test_board_diff_rejects_names_outside_the_snapshots_folder(ctx, no_disk, board_id, snapshot):
    no_disk["on"] = True
    result = await bo.get_board_diff(board_id, snapshot, "snap2", ctx)
    no_disk["on"] = False
    assert result["code"] == "VALIDATION_FAILED"
    assert "not a" in result["error"]


# ── Backend archive_item tests ───────────────────────────────────────


async def test_freeform_archive_item(tmp_path):
    from server.backends.freeform_backend import FreeformBackend
    be = FreeformBackend(root=str(tmp_path / "tracking"))
    uc = await be.create_item("b", "UC-001: Test", labels=["UC"], meta={"uc_id": "UC-001"})
    result = await be.archive_item("b", uc.id, reason="obsolete")
    assert result["archive_location"] == "archive.json"
    # Verify item removed from items.json
    items = await be.list_items("b")
    assert not any(i.id == uc.id for i in items)
    # Verify archive.json has the item
    archive = json.loads((tmp_path / "tracking" / "archive.json").read_text())
    assert len(archive) == 1
    assert archive[0]["archive_reason"] == "obsolete"
