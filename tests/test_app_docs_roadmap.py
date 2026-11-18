"""US-122 / UC-12203 — la zona «roadmap» de app_prd.md sale del tablero tras cada cambio.

- **AC-01**: complete_uc, move_uc, add_uc, delete_uc y mark_ac_batch devuelven ``app_docs_sync``.
- **AC-02**: tras complete_uc la zona cuenta la UC cerrada, también con el MCP remoto (contenido).
- **AC-03**: si la sincronización falla, ``app_docs_sync.ok = false`` con el motivo y la UC conserva
  el cambio de estado.
- **AC-04/05**: el cuerpo solo depende del tablero (mismo tablero, mismo texto) y el hook calcula lo
  mismo que el servidor; dónde y cuándo se escribe lo prueban ``tests/hooks/app-docs-fragment.test.mjs``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from server.app_docs import roadmap
from server.tools.board_operations import delete_uc
from server.tools.spec_driven import complete_uc, mark_ac_batch, move_uc
from server.tools.spec_mutations import add_uc
from tests._native_db import DSN, reachable

ENGINE = Path(__file__).resolve().parent.parent


def _item(item_id, name, labels, state="backlog", parent=None, meta=None):
    return {"id": item_id, "name": name, "description": "", "state": state, "parent_id": parent,
            "labels": labels, "meta": meta or {}}


BOARD = [
    _item("us1", "US-01: Pagos | cobros", ["US"], "in_progress", meta={"us_id": "US-01"}),
    _item("uc1", "UC-001: Cobrar", ["UC"], "in_progress", "us1", {"uc_id": "UC-001", "us_id": "US-01"}),
    _item("ac1", "[AC-01] El cobro queda registrado", ["AC"], "backlog", "uc1", {"ac_id": "AC-01"}),
    _item("uc2", "UC-002: Devolver", ["UC"], "done", "us1", {"uc_id": "UC-002", "us_id": "US-01"}),
    _item("uc3", "UC-003: Viejo", ["UC"], "archived", "us1", {"uc_id": "UC-003", "us_id": "US-01"}),
    _item("us10", "US-10: Informes", ["US"], "backlog", meta={"us_id": "US-10"}),
    _item("us2", "US-02:   Alta   de clientes", ["US"], "done", meta={"us_id": "US-02"}),
    _item("us9", "US-09: Retirada", ["US"], "archived", meta={"us_id": "US-09"}),
]


class _Ctx:
    def __init__(self, config):
        self._config = config

    async def get_state(self, key):
        return self._config


CTX = _Ctx({"backend_type": "freeform", "content_only": True})


def test_the_zone_is_one_row_per_story_from_the_board():
    rows = roadmap.rows_from_items([_dto(d) for d in BOARD])
    assert [(r["us_id"], r["title"], r["state"], f"{r['done']}/{r['total']}") for r in rows] == [
        ("US-01", "Pagos \\| cobros", "in_progress", "1/2"),
        ("US-02", "Alta de clientes", "done", "0/0"),
        ("US-10", "Informes", "backlog", "0/0"),
    ]
    body = roadmap.render(rows)
    assert body.splitlines()[0] == "## 5. Roadmap de US"
    assert "| US-01 | Pagos \\| cobros | in_progress | 1/2 |" in body
    assert roadmap.render(rows) == body  # mismo tablero, mismo texto (AC-04)
    assert "(sin historias)" in roadmap.render([])


def _dto(d):
    from server.spec_backend import ItemDTO

    return ItemDTO(id=d["id"], name=d["name"], state=d["state"], parent_id=d["parent_id"], labels=d["labels"], meta=d["meta"])


@pytest.mark.parametrize("call", ["complete_uc", "move_uc", "add_uc", "delete_uc", "mark_ac_batch"])
async def test_each_state_changing_tool_carries_the_roadmap(call):
    """AC-01."""
    content = json.dumps(BOARD)
    calls = {
        "complete_uc": lambda: complete_uc("ff", "UC-001", CTX, items_content=content),
        "move_uc": lambda: move_uc("ff", "UC-001", "review", CTX, items_content=content),
        "add_uc": lambda: add_uc("ff", "US-10", "Exportar", "Exportar a CSV",
                                 ["El fichero CSV aparece con 3 columnas"], CTX, items_content=content),
        "delete_uc": lambda: delete_uc("ff", "UC-001", "Absorbida por UC-002", CTX, absorbed_by="UC-002",
                                       items_content=content),
        "mark_ac_batch": lambda: mark_ac_batch("ff", "UC-001", [{"ac_id": "AC-01", "passed": True}], CTX,
                                               items_content=content),
    }
    out = await calls[call]()
    assert "error" not in out, out
    sync = out["app_docs_sync"]
    assert sync["ok"] is True and sync["zone"] == "roadmap" and sync["document"] == "doc/app/app_prd.md"
    assert sync["roadmap_body"].startswith("## 5. Roadmap de US")


async def test_after_complete_uc_the_zone_counts_the_closed_uc():
    """AC-02 con el MCP remoto: el cuerpo viaja en la respuesta, calculado con el tablero ya cambiado."""
    out = await complete_uc("ff", "UC-001", CTX, items_content=json.dumps(BOARD))
    # Era la última UC abierta: la historia pasa a «done» y la zona lo cuenta (la archivada no cuenta).
    assert "| US-01 | Pagos \\| cobros | done | 2/2 |" in out["app_docs_sync"]["roadmap_body"]


async def test_a_fragment_leaves_the_zone_to_the_client():
    fragment = json.dumps({"format": "specbox-freeform-fragment/1", "max_ids": {"US": 10, "UC": 3, "EP": 0},
                           "items": BOARD[:3]})
    out = await move_uc("ff", "UC-001", "review", CTX, items_content=fragment)
    assert out["app_docs_sync"] == {"ok": True, "document": "doc/app/app_prd.md", "zone": "roadmap", "render": "client"}


async def test_a_failed_sync_says_why_and_keeps_the_state_change(monkeypatch):
    """AC-03."""
    async def boom(*args, **kwargs):
        raise RuntimeError("el tablero no respondió")

    monkeypatch.setattr(roadmap, "roadmap_sync", boom)
    out = await move_uc("ff", "UC-001", "review", CTX, items_content=json.dumps(BOARD))
    assert out["app_docs_sync"]["ok"] is False
    assert "el tablero no respondió" in out["app_docs_sync"]["reason"]
    moved = next(i for i in json.loads(out["items_content"]) if i["id"] == "uc1")
    assert moved["state"] == "review"


async def test_an_error_of_the_tool_is_left_alone():
    out = await move_uc("ff", "UC-999", "review", CTX, items_content=json.dumps(BOARD))
    assert "error" in out and "app_docs_sync" not in out


@pytest.mark.skipif(shutil.which("node") is None, reason="sin node")
def test_the_hook_renders_exactly_what_the_server_renders(tmp_path):
    """AC-04: FreeForm por fragmentos — el hook calcula el mismo texto con su items.json."""
    (tmp_path / "items.json").write_text(json.dumps(BOARD))
    lib = ENGINE / ".claude" / "hooks" / "lib" / "roadmap.mjs"
    code = (
        f"import('{lib}').then(m => process.stdout.write(m.render(m.rowsFromItems("
        f"JSON.parse(require('fs').readFileSync('{tmp_path / 'items.json'}', 'utf8'))))))"
    )
    js = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    assert js == roadmap.render(roadmap.rows_from_items([_dto(d) for d in BOARD]))


def test_the_hook_replaces_the_zone_like_the_server(tmp_path):
    from server.app_docs.zones import replace_zone_body

    doc = (
        "# PRD\n\n<!-- @specbox:zone start kind=\"auto\" id=\"roadmap\" auto_sync_on=\"complete_uc\" -->\n"
        "## 5. Roadmap de US\n\n| viejo |\n<!-- @specbox:zone end -->\n\nFin\n"
    )
    body = roadmap.render(roadmap.rows_from_items([_dto(d) for d in BOARD]))
    py = replace_zone_body(doc, "roadmap", body)
    if shutil.which("node") is None:
        pytest.skip("sin node")
    (tmp_path / "doc.md").write_text(doc)
    (tmp_path / "body.md").write_text(body)
    lib = ENGINE / ".claude" / "hooks" / "lib" / "roadmap.mjs"
    code = (
        f"const fs=require('fs');import('{lib}').then(m => process.stdout.write(m.replaceZone("
        f"fs.readFileSync('{tmp_path / 'doc.md'}','utf8'),'roadmap',fs.readFileSync('{tmp_path / 'body.md'}','utf8'))))"
    )
    js = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    assert js == py


PG_OK, PG_SKIP_REASON = reachable()


@pytest.mark.skipif(not PG_OK, reason=PG_SKIP_REASON)
async def test_native_rows_come_from_one_query():
    from server.db.migrate import apply_migrations
    from server.db.pool import init_pool

    pool = await init_pool(dsn=DSN)
    await apply_migrations(pool)
    project_id = f"Acme/roadmap-{uuid.uuid4().hex[:8]}"
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO projects (project_id, name) VALUES ($1, 'Roadmap')", project_id)
        await conn.execute("INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-2', $1, 'Dos', 'done')", project_id)
        await conn.execute("INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-1', $1, 'US-1: Uno', 'in_progress')", project_id)
        await conn.execute("INSERT INTO user_stories (id, project_id, name, state) VALUES ('US-3', $1, 'Tres', 'archived')", project_id)
        for uc, state in (("UC-11", "done"), ("UC-12", "backlog"), ("UC-13", "archived")):
            await conn.execute(
                "INSERT INTO use_cases (id, project_id, us_id, name, state) VALUES ($2, $1, 'US-1', $2, $3)",
                project_id, uc, state,
            )
    try:
        rows = await roadmap.rows_native(project_id)
        assert [(r["us_id"], r["title"], r["state"], r["done"], r["total"]) for r in rows] == [
            ("US-1", "Uno", "in_progress", 1, 2),
            ("US-2", "Dos", "done", 0, 0),
        ]
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)
