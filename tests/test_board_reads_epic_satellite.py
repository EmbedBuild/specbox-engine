"""US-78 / UC-7803 — las lecturas del board dicen la épica y el satélite.

- **AC-01**: ``list_us``/``get_us`` devuelven la épica y los satélites de la historia;
  ``list_uc``/``get_uc``, el satélite del caso de uso y la épica de su historia.
- **AC-02**: ``get_board_status`` desglosa por épica con «sin épica» y los grupos suman el board.
- **AC-03**: un satélite que el proyecto no declara se rechaza con la lista de los válidos, también
  con el MCP remoto (``declare_satellites`` lo guarda en el board).
- **AC-04**: ``get_cross_repo_dependencies`` reconoce ids de cualquier longitud.
"""

from __future__ import annotations

import json
import uuid

import pytest

from server.backends.freeform_backend import FreeformBackend
from server.tools import _mutation_helpers as mh
from server.tools import milestone_management as mm
from server.tools import spec_driven as sd
from tests._native_db import DSN, reachable

PG_OK, PG_SKIP_REASON = reachable()
pytestmark_pg = pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)


class _KeepOpen(FreeformBackend):
    async def close(self) -> None:
        return None


def _use(monkeypatch, module, backend):
    async def _fake(_ctx, *, items_content=None):
        return backend

    monkeypatch.setattr(module, "get_session_backend", _fake)


def _item(item_id, name, labels, state="backlog", parent=None, **meta):
    return {"id": item_id, "name": name, "state": state, "parent_id": parent, "labels": labels,
            "priority": "none", "meta": meta}


async def _board() -> _KeepOpen:
    items = [
        _item("us1", "US-01: Uno", ["US"], "in_progress", us_id="US-01"),
        _item("uc1", "UC-0101: A", ["UC"], "done", "us1", uc_id="UC-0101", us_id="US-01", satellite="engine"),
        _item("uc2", "UC-0102: B", ["UC"], "in_progress", "us1", uc_id="UC-0102", us_id="US-01", satellite="cloud"),
        _item("ac1", "[AC-01] x", ["AC"], "done", "uc1", ac_id="AC-01"),
        _item("ac2", "[AC-01] y", ["AC"], "backlog", "uc2", ac_id="AC-01"),
        _item("us2", "US-02: Dos", ["US"], "backlog", us_id="US-02"),
        _item("uc3", "UC-0201: C", ["UC"], "backlog", "us2", uc_id="UC-0201", us_id="US-02", satellite="site"),
        _item("ac3", "[AC-01] z", ["AC"], "backlog", "uc3", ac_id="AC-01"),
    ]
    board = _KeepOpen(items_content=json.dumps(items))
    await board.create_epic("ff", name="Primera")
    await board.set_us_epic("ff", "us1", "EP-01")
    return board


async def test_ac01_story_and_case_reads_carry_epic_and_satellite(monkeypatch):
    _use(monkeypatch, sd, await _board())

    stories = {s["us_id"]: s for s in await sd.list_us("ff", ctx=None)}
    assert (stories["US-01"]["epic_id"], stories["US-01"]["satellites"]) == ("EP-01", ["engine", "cloud"])
    assert (stories["US-02"]["epic_id"], stories["US-02"]["satellites"]) == (None, ["site"])

    us = await sd.get_us("ff", "US-01", ctx=None)
    assert (us["epic_id"], us["satellites"]) == ("EP-01", ["engine", "cloud"])
    assert [u["satellite"] for u in us["use_cases"]] == ["engine", "cloud"]

    cases = {c["uc_id"]: c for c in await sd.list_uc("ff", ctx=None)}
    assert (cases["UC-0102"]["satellite"], cases["UC-0102"]["epic_id"]) == ("cloud", "EP-01")
    assert (cases["UC-0201"]["satellite"], cases["UC-0201"]["epic_id"]) == ("site", None)

    uc = await sd.get_uc("ff", "UC-0101", ctx=None)
    assert (uc["satellite"], uc["epic_id"]) == ("engine", "EP-01")


async def test_ac02_board_status_by_epic_adds_up_to_the_board(monkeypatch):
    _use(monkeypatch, sd, await _board())
    status = await sd.get_board_status("ff", ctx=None)
    groups = status["by_epic"]
    assert [g["epic_id"] for g in groups] == ["EP-01", "sin_epica"]
    assert sum(g["us_total"] for g in groups) == 2
    assert sum(g["uc_total"] for g in groups) == 3
    assert sum(g["ac_total"] for g in groups) == 3
    assert (groups[0]["state"], groups[0]["ac_done"], groups[0]["ac_total"]) == ("in_progress", 1, 2)
    assert [u["epic_id"] for u in status["us_summary"]] == ["EP-01", None]


# ── AC-03 ────────────────────────────────────────────────────────────


class _Declared:
    def __init__(self, declared):
        self.declared = declared

    async def get_board_satellites(self, board_id):
        return self.declared


@pytest.mark.parametrize("remote", [False, True])
async def test_ac03_undeclared_satellite_is_refused_with_the_valid_list(monkeypatch, remote):
    import server.transport as transport

    monkeypatch.setattr(transport, "is_remote_transport", lambda: remote)
    ok, err = await mh.check_satellite(_Declared(["engine", "cloud"]), "b", "satelite-inventado")
    assert not ok
    assert "Valid satellites: engine, cloud" in err
    assert (await mh.check_satellite(_Declared(["engine", "cloud"]), "b", "cloud")) == (True, None)


async def test_ac03_without_declaration_remote_accepts_and_local_reads_the_settings(monkeypatch, tmp_path):
    import server.transport as transport

    settings = tmp_path / ".claude" / "settings.local.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"multirepo": {"satellites": {"engine": {}, "cloud": {}}}}))
    monkeypatch.setenv("SPECBOX_PROJECT_ROOT", str(tmp_path))

    monkeypatch.setattr(transport, "is_remote_transport", lambda: True)
    assert (await mh.check_satellite(_Declared(None), "b", "otro")) == (True, None)

    monkeypatch.setattr(transport, "is_remote_transport", lambda: False)
    ok, _ = await mh.check_satellite(_Declared(None), "b", "otro")
    assert not ok


async def _pool():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    return pool


@pytestmark_pg
async def test_ac03_native_declaration_survives_the_remote_transport(monkeypatch):
    import server.transport as transport
    from server.backends.native_backend import NativeBackend
    from server.coordination.identity import add_project_member, register_developer, register_mcp_token

    pool = await _pool()
    project_id = f"Acme/sats-{uuid.uuid4().hex[:8]}"
    developer_id = f"sat-dev-{uuid.uuid4().hex[:8]}"
    token = f"sat-tok-{uuid.uuid4().hex[:16]}"
    async with pool.acquire() as conn:
        await register_developer(conn, developer_id=developer_id, display_name="Dev")
        await register_mcp_token(conn, developer_id=developer_id, token=token)
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'x')", project_id)
        await add_project_member(conn, project_id=project_id, developer_id=developer_id, role="project_admin")
        await conn.execute(
            "INSERT INTO user_stories (id, project_id, name, labels, meta) "
            "VALUES ('US-01', $1, 'US-01: H', '[\"US\"]'::jsonb, '{\"us_id\": \"US-01\"}'::jsonb)",
            project_id,
        )
        await conn.execute(
            "INSERT INTO use_cases (id, project_id, us_id, name, labels, meta) VALUES "
            "('UC-0101', $1, 'US-01', 'UC-0101: C', '[\"UC\"]'::jsonb, '{\"uc_id\": \"UC-0101\"}'::jsonb)",
            project_id,
        )
    monkeypatch.setattr(transport, "is_remote_transport", lambda: True)
    _use(monkeypatch, mm, NativeBackend(project_id, token))

    declared = await mm.declare_satellites(project_id, ["engine", "cloud", "engine"], ctx=None)
    assert declared == {"board_id": project_id, "satellites": ["engine", "cloud"], "previous": None}

    refused = await mm.set_uc_satellite(project_id, "UC-0101", "inventado", ctx=None)
    assert refused["code"] == "INVALID_SATELLITE" and "Valid satellites: engine, cloud" in refused["error"]
    assert (await mm.set_uc_satellite(project_id, "UC-0101", "cloud", ctx=None))["satellite"] == "cloud"
    assert await pool.fetchval(
        "SELECT count(*) FROM audit_log WHERE project_id = $1 AND operation = 'declare_satellites'", project_id
    ) == 1


# ── AC-04 ────────────────────────────────────────────────────────────


async def test_ac04_dependencies_read_ids_of_any_length(monkeypatch):
    items = [
        _item("us5", "US-05: Vieja", ["US"], us_id="US-05"),
        # UC-510 existe en otro satélite: con UC-\d{3}, «UC-5101» se leía como «UC-510».
        _item("uc510", "UC-510: Vieja", ["UC"], parent="us5", uc_id="UC-510", us_id="US-05", satellite="cloud"),
        _item("us51", "US-51: Nueva", ["US"], us_id="US-51"),
        _item("uc5101", "UC-5101: Se apoya en UC-5101 y en UC-5103", ["UC"], parent="us51", uc_id="UC-5101",
              us_id="US-51", satellite="engine"),
        _item("uc5103", "UC-5103: Panel", ["UC"], parent="us51", uc_id="UC-5103", us_id="US-51", satellite="cloud"),
    ]
    items[3]["description"] = "Depende de UC-5103; ver también UC-9999 (no existe)."
    _use(monkeypatch, mm, _KeepOpen(items_content=json.dumps(items)))

    deps = (await mm.get_cross_repo_dependencies("ff", ctx=None))["dependencies"]
    assert [(d["uc_id"], d["depends_on"]) for d in deps] == [("UC-5101", "UC-5103")]
