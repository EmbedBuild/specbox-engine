"""US-55 / UC-5501 — borrado real de una UC que nunca tuvo trabajo, con sus AC.

AC-01 · Native: ``delete_uc(purge=True)`` borra en una sola transacción la UC, sus AC, sus
        transiciones de estado, su reserva y su registro de rama; después la UC no aparece en
        ninguna lista ni cuenta en el progreso de su US.
AC-02 · Solo si está en backlog o archivada, sin AC hechos, sin evidencia y sin reserva; si no,
        la tool dice el motivo concreto y deja la UC archivada, como hoy.
AC-03 · Cada borrado deja una fila ``purge_uc`` en ``audit_log`` con quién, cuándo, el motivo y
        una copia de la UC y de sus AC.
AC-04 · Respeta el tenant de la sesión; FreeForm borra igual sobre sus ficheros; Trello y Plane
        siguen archivando.

Las pruebas native necesitan Postgres (``tests/_native_db.py``) y se omiten sin él.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.spec_backend import (
    PURGE_NOT_SUPPORTED,
    PURGE_UC_HAS_DONE_AC,
    PURGE_UC_HAS_EVIDENCE,
    PURGE_UC_RESERVED,
    PURGE_UC_STATE,
    PurgeRefused,
    purge_refusal,
)
from server.tools import board_operations as bo
from tests._native_db import DSN, reachable
from tests.test_board_operations import InMemoryBackend, _seed

_PG_OK, _PG_SKIP_REASON = reachable()
needs_pg = pytest.mark.skipif(not _PG_OK, reason=_PG_SKIP_REASON)


def _use(monkeypatch, backend):
    """delete_uc talks to this backend (the session is not under test here)."""

    async def _fake(ctx, items_content=None):
        return backend

    monkeypatch.setattr(bo, "get_session_backend", _fake)
    return AsyncMock()


# ── AC-02: who can be deleted for real (pure) ─────────────────────────


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"state": "backlog"}, None),
        ({"state": "archived"}, None),
        ({"state": "in_progress"}, PURGE_UC_STATE),
        ({"state": "review"}, PURGE_UC_STATE),
        ({"state": "done"}, PURGE_UC_STATE),
        ({"state": "backlog", "done_ac_ids": ["AC-02"]}, PURGE_UC_HAS_DONE_AC),
        ({"state": "backlog", "has_evidence": True}, PURGE_UC_HAS_EVIDENCE),
        ({"state": "archived", "reserved_by": "dev-x"}, PURGE_UC_RESERVED),
    ],
)
def test_ac02_only_a_uc_that_never_had_work_can_go(kwargs, code):
    args = {"done_ac_ids": [], "has_evidence": False, "reserved_by": None, **kwargs}
    refusal = purge_refusal("UC-9", **args)
    assert (refusal.code if refusal else None) == code
    if refusal:
        assert "UC-9" in refusal.message


# ── AC-04: Trello and Plane keep archiving ────────────────────────────


async def test_ac04_a_backend_without_purge_archives_and_says_why(monkeypatch):
    backend = InMemoryBackend()  # stands in for Trello/Plane: no purge_use_case of its own
    ctx = _use(monkeypatch, backend)
    _, ucs = await _seed(backend, n_ucs=1)

    result = await bo.delete_uc("b", "UC-001", "duplicada", ctx, purge=True)

    assert result["purged"] is False
    assert result["purge_refused"]["code"] == PURGE_NOT_SUPPORTED
    assert result["archive_location"] == "test_archive"
    assert ucs[0].id in backend.archived


class _PurgingBackend(InMemoryBackend):
    """A backend that implements purge; ``refuse`` makes it refuse instead."""

    def __init__(self, refuse: PurgeRefused | None = None):
        super().__init__()
        self.refuse = refuse
        self.purged: list[str] = []

    async def purge_use_case(self, board_id, uc_item_id, *, reason):
        if self.refuse:
            raise self.refuse
        self.purged.append(uc_item_id)
        self.items.pop(uc_item_id)
        return {"purged_at": "2026-10-01T00:00:00+00:00", "deleted": {"use_cases": 1}, "snapshot": {"uc": {}}}


async def test_tool_reports_what_was_deleted(monkeypatch):
    backend = _PurgingBackend()
    ctx = _use(monkeypatch, backend)
    _, ucs = await _seed(backend, n_ucs=1)

    result = await bo.delete_uc("b", "UC-001", "duplicada", ctx, purge=True)

    assert result["purged"] is True
    assert result["deleted"] == {"use_cases": 1}
    assert "snapshot" in result
    assert backend.purged == [ucs[0].id]
    assert backend.archived == []


async def test_ac02_refused_purge_leaves_the_uc_archived_with_the_reason(monkeypatch):
    backend = _PurgingBackend(PurgeRefused(PURGE_UC_HAS_DONE_AC, "UC-001 has 1 AC done (AC-01): it had work."))
    ctx = _use(monkeypatch, backend)
    _, ucs = await _seed(backend, n_ucs=1)

    result = await bo.delete_uc("b", "UC-001", "duplicada", ctx, purge=True)

    assert result["purged"] is False
    assert result["purge_refused"] == {
        "code": PURGE_UC_HAS_DONE_AC,
        "message": "UC-001 has 1 AC done (AC-01): it had work.",
    }
    assert ucs[0].id in backend.archived


async def test_without_purge_delete_uc_still_only_archives(monkeypatch):
    backend = _PurgingBackend()
    ctx = _use(monkeypatch, backend)
    await _seed(backend, n_ucs=1)

    result = await bo.delete_uc("b", "UC-001", "obsoleta", ctx)

    assert result["purged"] is False
    assert "purge_refused" not in result
    assert backend.purged == []


# ── AC-04: FreeForm deletes from its own files ────────────────────────


async def _freeform_uc(be: FreeformBackend, uc_id: str = "UC-001"):
    us = await be.create_item("b", "US-01: Historia", labels=["US"], meta={"us_id": "US-01"})
    uc = await be.create_item(
        "b", f"{uc_id}: Caso", labels=["UC"], parent_id=us.id, meta={"uc_id": uc_id, "us_id": "US-01"},
    )
    await be.create_acceptance_criteria("b", uc.id, [("AC-01", "primero"), ("AC-02", "segundo")])
    return us, uc


async def test_ac04_freeform_deletes_the_uc_its_acs_and_comments(tmp_path, monkeypatch):
    root = tmp_path / "tracking"
    be = FreeformBackend(root=str(root))
    us, uc = await _freeform_uc(be)
    await be.add_comment("b", uc.id, "creada por error")
    ctx = _use(monkeypatch, be)

    result = await bo.delete_uc("b", "UC-001", "duplicada de UC-002", ctx, purge=True)

    assert result["purged"] is True
    assert result["deleted"] == {"use_cases": 1, "acceptance_criteria": 2, "comments": 1}
    items = json.loads((root / "items.json").read_text())
    assert [i["id"] for i in items] == [us.id]  # ni la UC ni sus AC
    assert not (root / "comments" / f"{uc.id}.jsonl").exists()
    record = json.loads((root / "purged.jsonl").read_text().splitlines()[-1])
    assert record["uc_id"] == "UC-001"
    assert record["reason"] == "duplicada de UC-002"
    assert [ac["name"] for ac in record["snapshot"]["acceptance_criteria"]] == ["[AC-01] primero", "[AC-02] segundo"]


async def test_ac04_freeform_deletes_an_archived_uc_and_its_orphan_acs(tmp_path, monkeypatch):
    root = tmp_path / "tracking"
    be = FreeformBackend(root=str(root))
    us, uc = await _freeform_uc(be)
    await be.archive_item("b", uc.id, reason="obsoleta")  # sale de items.json; sus AC se quedan
    ctx = _use(monkeypatch, be)

    result = await bo.delete_uc("b", "UC-001", "duplicada", ctx, purge=True)

    assert result["purged"] is True
    assert json.loads((root / "archive.json").read_text()) == []
    assert [i["id"] for i in json.loads((root / "items.json").read_text())] == [us.id]


@pytest.mark.parametrize("why", ["done_ac", "evidence", "in_progress"])
async def test_ac02_freeform_refuses_and_archives(tmp_path, monkeypatch, why):
    root = tmp_path / "tracking"
    be = FreeformBackend(root=str(root))
    _, uc = await _freeform_uc(be)
    if why == "done_ac":
        await be.mark_acceptance_criterion("b", uc.id, "AC-01", True)
    elif why == "evidence":
        await be.add_attachment("b", uc.id, "evidencia.pdf", b"%PDF")
    else:
        await be.update_item("b", uc.id, state="in_progress")
    ctx = _use(monkeypatch, be)

    result = await bo.delete_uc("b", "UC-001", "duplicada", ctx, purge=True)

    expected = {"done_ac": PURGE_UC_HAS_DONE_AC, "evidence": PURGE_UC_HAS_EVIDENCE, "in_progress": PURGE_UC_STATE}
    assert result["purged"] is False
    assert result["purge_refused"]["code"] == expected[why]
    archive = json.loads((root / "archive.json").read_text())
    assert [i["id"] for i in archive] == [uc.id]  # archivada, no perdida
    assert not (root / "purged.jsonl").exists()


async def test_ac04_freeform_memory_mode_returns_the_board_without_the_uc():
    be = FreeformBackend(items_content="[]")
    us, uc = await _freeform_uc(be)

    result = await be.purge_use_case("b", uc.id, reason="duplicada")

    board = json.loads(be.get_items_content())
    assert [i["id"] for i in board] == [us.id]
    assert result["snapshot"]["uc"]["id"] == uc.id
    assert len(result["snapshot"]["acceptance_criteria"]) == 2


# ── Native (Postgres) ─────────────────────────────────────────────────


@pytest.fixture
async def pg_pool():
    from server.db.pool import close_pool, init_pool

    await init_pool(dsn=DSN)
    try:
        yield
    finally:
        await close_pool()


async def _native_project(suffix: int | None = None):
    """A tenant with its developer, a US, a UC with 3 ACs. Returns (backend, dev, project, us, uc)."""
    from server.backends.native_backend import NativeBackend
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token
    from server.db.pool import get_pool

    project = f"test-uc5501-{uuid.uuid4().hex[:8]}"
    developer = f"dev-uc5501-{uuid.uuid4().hex[:6]}"
    token = uuid.uuid4().hex + uuid.uuid4().hex
    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer, display_name="Tester")
        await register_mcp_token(conn, developer_id=developer, token=token)
        await conn.execute(
            "INSERT INTO projects (project_id, name, backend_type, board_url, meta) "
            "VALUES ($1, $1, 'native', '', '{}'::jsonb) ON CONFLICT (project_id) DO NOTHING",
            project,
        )
        await add_project_member(conn, project_id=project, developer_id=developer)
    suffix = suffix if suffix is not None else uuid.uuid4().int % 1_000_000
    backend = NativeBackend(project_id=project, dev_token=token)
    us = await backend.create_item(project, name=f"US-{suffix}: historia", labels=["US"])
    uc = await backend.create_item(project, name=f"UC-{suffix}: creada por error", labels=["UC"], parent_id=us.id)
    await backend.create_acceptance_criteria(project, uc.id, [("AC-01", "uno"), ("AC-02", "dos"), ("AC-03", "tres")])
    return backend, developer, project, us, uc


async def _rows(project: str, uc_id: str) -> dict[str, int]:
    from server.db.pool import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        counts = {
            table: await conn.fetchval(f"SELECT count(*) FROM {table} WHERE project_id = $1 AND uc_id = $2", project, uc_id)
            for table in ("acceptance_criteria", "uc_state_transitions", "uc_reservations", "branch_registry")
        }
        counts["use_cases"] = await conn.fetchval(
            "SELECT count(*) FROM use_cases WHERE project_id = $1 AND id = $2", project, uc_id
        )
    return counts


@needs_pg
async def test_ac01_ac03_native_purge_removes_everything_and_keeps_an_audit_copy(pg_pool):
    from server.coordination.branches import register_branch
    from server.db.pool import get_pool

    backend, developer, project, us, uc = await _native_project()
    # History that hangs from the UC: two state transitions (and back to backlog) and a branch.
    await backend.update_item(project, uc.id, state="in_progress")
    await backend.update_item(project, uc.id, state="backlog")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await register_branch(conn, project_id=project, branch=f"feat/{uc.id}-x", uc_id=uc.id, developer_id=developer)
        progress_before = await conn.fetchval(
            "SELECT uc_total FROM v_us_progress WHERE project_id = $1 AND us_id = $2", project, us.id
        )
    assert (await _rows(project, uc.id))["uc_state_transitions"] == 2

    result = await backend.purge_use_case(project, uc.id, reason="duplicada de otra UC")

    assert result["deleted"] == {
        "acceptance_criteria": 3,
        "uc_state_transitions": 2,
        "uc_reservations": 0,
        "branch_registry": 1,
        "use_cases": 1,
    }
    assert await _rows(project, uc.id) == {
        "acceptance_criteria": 0, "uc_state_transitions": 0, "uc_reservations": 0, "branch_registry": 0, "use_cases": 0,
    }
    listed = await backend.list_items(project)
    assert [i.id for i in listed] == [us.id]  # ni la UC ni sus AC en ninguna lista
    async with pool.acquire() as conn:
        progress_after = await conn.fetchval(
            "SELECT uc_total FROM v_us_progress WHERE project_id = $1 AND us_id = $2", project, us.id
        )
        audit = await conn.fetchrow(
            "SELECT developer_id, operation, target_id, metadata, occurred_at FROM audit_log "
            "WHERE project_id = $1 AND operation = 'purge_uc'",
            project,
        )
    assert progress_before == 1 and progress_after is None  # la US ya no cuenta la UC
    assert audit["developer_id"] == developer
    assert audit["target_id"] == uc.id
    assert audit["occurred_at"] is not None
    metadata = json.loads(audit["metadata"])
    assert metadata["reason"] == "duplicada de otra UC"
    assert metadata["snapshot"]["uc"]["name"] == uc.name
    assert [ac["text"] for ac in metadata["snapshot"]["acceptance_criteria"]] == ["uno", "dos", "tres"]


@needs_pg
async def test_ac02_native_archived_uc_can_be_purged(pg_pool):
    backend, _, project, _, uc = await _native_project()
    await backend.archive_item(project, uc.id, reason="obsoleta")

    result = await backend.purge_use_case(project, uc.id, reason="duplicada")

    assert result["deleted"]["use_cases"] == 1


@needs_pg
@pytest.mark.parametrize("why", ["done_ac", "in_progress", "evidence", "ac_metadata", "reserved"])
async def test_ac02_native_refuses_a_uc_that_had_work_and_touches_nothing(pg_pool, why):
    from server.coordination.reservations import reserve_uc
    from server.db.pool import get_pool

    backend, developer, project, _, uc = await _native_project()
    if why == "done_ac":
        await backend.mark_acceptance_criterion(project, uc.id, "AC-02", True)
    elif why == "in_progress":
        await backend.update_item(project, uc.id, state="in_progress")
    elif why == "evidence":
        await backend.add_attachment(project, uc.id, "evidencia.pdf", b"%PDF")
    elif why == "ac_metadata":
        await backend.update_acceptance_criterion(project, uc.id, "AC-01", text='uno [META: {"verdict": "pass"}]')
    else:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await reserve_uc(conn, project_id=project, uc_id=uc.id, developer_id=developer)
    before = await _rows(project, uc.id)

    with pytest.raises(PurgeRefused) as refused:
        await backend.purge_use_case(project, uc.id, reason="duplicada")

    expected = {
        "done_ac": PURGE_UC_HAS_DONE_AC,
        "in_progress": PURGE_UC_STATE,
        "evidence": PURGE_UC_HAS_EVIDENCE,
        "ac_metadata": PURGE_UC_HAS_EVIDENCE,
        "reserved": PURGE_UC_RESERVED,
    }
    assert refused.value.code == expected[why]
    assert await _rows(project, uc.id) == before


@needs_pg
async def test_ac02_native_tool_archives_a_refused_uc(pg_pool, monkeypatch):
    backend, _, project, _, uc = await _native_project()
    await backend.mark_acceptance_criterion(project, uc.id, "AC-01", True)
    uc_id = uc.name.split(":")[0]
    ctx = _use(monkeypatch, backend)

    result = await bo.delete_uc(project, uc_id, "duplicada", ctx, purge=True)

    assert result["purged"] is False
    assert result["purge_refused"]["code"] == PURGE_UC_HAS_DONE_AC
    assert (await backend.get_item(project, uc.id)).state == "archived"


@needs_pg
async def test_ac04_native_purge_only_touches_the_session_tenant(pg_pool):
    from server.coordination.identity import ForbiddenError, UnauthenticatedError
    from server.backends.native_backend import NativeBackend

    suffix = uuid.uuid4().int % 1_000_000
    backend_a, _, project_a, _, uc_a = await _native_project(suffix)
    backend_b, _, project_b, _, uc_b = await _native_project(suffix)  # same UC id in another tenant
    assert uc_a.id == uc_b.id

    await backend_a.purge_use_case(project_a, uc_a.id, reason="duplicada")

    assert (await _rows(project_b, uc_b.id))["use_cases"] == 1  # the other tenant keeps its UC
    assert (await _rows(project_b, uc_b.id))["acceptance_criteria"] == 3
    with pytest.raises(ForbiddenError):  # a member of A cannot delete in B
        await backend_a.purge_use_case(project_b, uc_b.id, reason="ajena")
    with pytest.raises(UnauthenticatedError):  # nobody without a valid token
        await NativeBackend(project_id=project_b, dev_token="x" * 64).purge_use_case(project_b, uc_b.id, reason="x")
    assert (await _rows(project_b, uc_b.id))["use_cases"] == 1
