"""UC-3801 — El backend FreeForm remoto no toca el disco del servidor.

Origen: reporte de un tester externo (2026-09-24). Con el MCP remoto,
``set_auth_token(backend_type='freeform', root_path='doc/tracking')`` respondía
"initialized at /app/doc/tracking/" y cualquier ``board_id`` devolvía las 27
historias del propio engine: el guard dependía de ``SPECBOX_ENGINE_MCP_URL`` en
el entorno del SERVIDOR (un ajuste de cliente que nadie pone en el VPS) y el
backlog del engine viajaba en la imagen.

AC-01: en transporte HTTP, configurar FreeForm con una ruta se rechaza con un
       mensaje que explica el modo de contenido pasado desde el cliente.
AC-02: en remoto, cada lectura o mutación opera solo sobre ``items_content`` y
       devuelve el contenido actualizado; el servidor no conserva archivos.
AC-03: sin contenido no hay board: cualquier sesión remota (nueva o legacy con
       root_path) recibe un error de configuración, nunca el backlog del engine;
       y ``doc/tracking`` queda fuera de la imagen.
AC-04: la detección depende del transporte del servidor (``MCP_TRANSPORT``),
       no de una variable configurada en el cliente; se prueban ambos modos.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.auth_gateway import (
    BACKEND_STATE_KEY,
    FREEFORM_CONTENT_REQUIRED_CODE,
    get_session_backend,
)
from server.backends.freeform_backend import FreeformBackend
from server.tools.milestone_management import set_uc_satellite
from server.tools.spec_driven import (
    get_board_status,
    list_us,
    move_uc,
    set_auth_token,
)
from server.transport import is_remote_transport, transport_name

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_TRACKING = REPO_ROOT / "doc" / "tracking"


class FakeCtx:
    """Minimal FastMCP Context double holding the session config."""

    def __init__(self, config: dict | None = None):
        self._s: dict = {}
        if config is not None:
            self._s[BACKEND_STATE_KEY] = config

    async def get_state(self, key):
        return self._s.get(key)

    async def set_state(self, key, value):
        self._s[key] = value

    async def delete_state(self, key):
        self._s.pop(key, None)

    @property
    def config(self) -> dict | None:
        return self._s.get(BACKEND_STATE_KEY)


async def _client_board() -> str:
    """A client board built with the backend itself, so the item shape is exact."""
    backend = FreeformBackend(items_content="[]")
    us = await backend.create_item(
        "client-board",
        name="US-01: Historia del cliente",
        description="",
        state="user_stories",
        labels=["US"],
        meta={"tipo": "US", "us_id": "US-01", "horas": 4},
    )
    await backend.create_item(
        "client-board",
        name="UC-001: Caso del cliente",
        description="",
        state="backlog",
        labels=["UC"],
        parent_id=us.id,
        meta={"tipo": "UC", "uc_id": "UC-001", "us_id": "US-01", "horas": 2},
    )
    return backend.get_items_content()


@pytest.fixture
def remote(monkeypatch):
    """Server started with the HTTP transport (the VPS deployment)."""
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)


@pytest.fixture
def local(monkeypatch):
    """Server started over stdio (Claude Code local)."""
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    monkeypatch.delenv("SPECBOX_ENGINE_MCP_URL", raising=False)


# ── AC-04: la detección es del servidor, no del cliente ────────────────


def test_ac04_transport_detection_reads_the_server_env(monkeypatch):
    for name in ("http", "streamable-http", "sse", "HTTP", " http "):
        monkeypatch.setenv("MCP_TRANSPORT", name)
        assert is_remote_transport(), name
    for name in ("stdio", "", "STDIO"):
        monkeypatch.setenv("MCP_TRANSPORT", name)
        assert not is_remote_transport(), repr(name)
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    assert transport_name() == "stdio"
    assert not is_remote_transport()


def test_ac04_client_env_var_does_not_make_the_server_remote(monkeypatch):
    monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.test/mcp")
    assert not is_remote_transport()


# ── AC-01: en remoto, una ruta se rechaza con un mensaje pedagógico ────


async def test_ac01_remote_rejects_a_directory_path(remote):
    ctx = FakeCtx()
    res = await set_auth_token(
        "freeform", "", ctx, backend_type="freeform", root_path="/Users/dev/proj/doc/tracking"
    )
    assert res["code"] == "FREEFORM_REMOTE_DISK_MODE_REJECTED"
    assert "items_content" in res["error"]
    assert "SPECBOX_ENGINE_MCP_URL" in res["error"]
    assert res["how_to"]["session"].endswith("# no root_path")
    assert ctx.config is None, "una configuración rechazada no deja sesión"


async def test_ac01_remote_rejects_relative_paths_too(remote):
    res = await set_auth_token("freeform", "", FakeCtx(), backend_type="freeform", root_path="doc/tracking")
    assert res["code"] == "FREEFORM_REMOTE_DISK_MODE_REJECTED"


async def test_ac01_remote_without_path_opens_a_content_only_session(remote):
    ctx = FakeCtx()
    res = await set_auth_token("freeform", "", ctx, backend_type="freeform")
    assert res["success"] is True
    assert res["mode"] == "content_only"
    assert "items_content" in res["message"]
    assert ctx.config == {"backend_type": "freeform", "root_path": None, "content_only": True}


# ── AC-02 / AC-03: solo contenido del cliente; nunca el disco del servidor ──


async def test_ac03_remote_session_without_content_is_a_configuration_error(remote):
    ctx = FakeCtx({"backend_type": "freeform", "root_path": None, "content_only": True})
    with pytest.raises(RuntimeError, match=FREEFORM_CONTENT_REQUIRED_CODE):
        await get_session_backend(ctx)
    # Cualquier identificador de board, misma respuesta: error, nunca historias.
    for board_id in ("agency-ops-platform", "totally-random-nonexistent-board-xyz123"):
        with pytest.raises(RuntimeError, match=FREEFORM_CONTENT_REQUIRED_CODE):
            await list_us(board_id, ctx)


async def test_ac03_legacy_remote_session_with_root_path_never_reads_the_server_disk(remote):
    # Una sesión abierta antes del fix apuntando al backlog del propio engine.
    ctx = FakeCtx({"backend_type": "freeform", "root_path": str(ENGINE_TRACKING)})
    with pytest.raises(RuntimeError, match=FREEFORM_CONTENT_REQUIRED_CODE):
        await get_session_backend(ctx)
    with pytest.raises(RuntimeError, match=FREEFORM_CONTENT_REQUIRED_CODE):
        await get_board_status("EmbedBuild/specbox-engine", ctx)


async def test_ac03_dockerignore_keeps_the_engine_backlog_out_of_the_image():
    lines = [ln.strip() for ln in (REPO_ROOT / ".dockerignore").read_text().splitlines()]
    assert "doc/tracking/" in lines


async def test_ac02_remote_reads_and_mutations_use_only_the_client_content(remote):
    ctx = FakeCtx({"backend_type": "freeform", "root_path": None, "content_only": True})
    board = await _client_board()

    # Lectura: refleja el board del cliente, con cualquier board_id.
    stories = await list_us("whatever", ctx, items_content=board)
    assert [s["us_id"] for s in stories] == ["US-01"]
    status = await get_board_status("whatever", ctx, items_content=board)
    assert status["summary"].startswith("1 UCs")

    # Mutación original (UC-660): devuelve el contenido actualizado.
    moved = await move_uc("whatever", "UC-001", "in_progress", ctx, items_content=board)
    assert moved["new_status"] == "in_progress"
    assert '"in_progress"' in moved["items_content"]

    # Mutación de otro módulo (decorador UC-3801): también lo devuelve.
    tagged = await set_uc_satellite("whatever", "UC-001", "engine", ctx, items_content=moved["items_content"])
    assert tagged["satellite"] == "engine"
    assert '"satellite": "engine"' in tagged["items_content"]
    # El contenido devuelto acumula ambas mutaciones: nada se perdió por el camino.
    assert '"in_progress"' in tagged["items_content"]

    # El servidor no conservó nada: una llamada sin contenido sigue fallando.
    with pytest.raises(RuntimeError, match=FREEFORM_CONTENT_REQUIRED_CODE):
        await list_us("whatever", ctx)


async def test_ac02_no_items_content_key_when_the_caller_did_not_pass_content(local, tmp_path):
    # En disco (local) el decorador es transparente: sin items_content no añade nada.
    ctx = FakeCtx()
    res = await set_auth_token("freeform", "", ctx, backend_type="freeform", root_path=str(tmp_path))
    assert res["mode"] == "disk"
    status = await get_board_status("any", ctx)
    assert "items_content" not in status


# ── AC-04: el modo local sigue en disco y el env var de cliente no cambia nada ──


async def test_ac04_local_server_keeps_disk_mode_with_absolute_path(local, tmp_path):
    ctx = FakeCtx()
    res = await set_auth_token("freeform", "", ctx, backend_type="freeform", root_path=str(tmp_path))
    assert res["success"] is True and res["mode"] == "disk"
    assert str(tmp_path) in res["message"]
    assert ctx.config["root_path"] == str(tmp_path)
    assert ctx.config["content_only"] is False


async def test_ac04_client_env_var_on_a_local_server_changes_nothing(local, monkeypatch, tmp_path):
    monkeypatch.setenv("SPECBOX_ENGINE_MCP_URL", "https://mcp.example.test/mcp")
    ctx = FakeCtx()
    res = await set_auth_token("freeform", "", ctx, backend_type="freeform", root_path=str(tmp_path))
    assert res["success"] is True and res["mode"] == "disk"


async def test_ac04_remote_decision_holds_without_the_client_env_var(remote):
    # Exactamente el caso del tester: el servidor no tiene SPECBOX_ENGINE_MCP_URL.
    res = await set_auth_token("freeform", "", FakeCtx(), backend_type="freeform", root_path="doc/tracking")
    assert res["code"] == "FREEFORM_REMOTE_DISK_MODE_REJECTED"
