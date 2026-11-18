"""El marcador de UC activa nunca impide empezar ni cerrar una UC.

Regresión de UC-3903 (2026-09-29): con el servidor remoto sin privilegios,
start_uc fallaba con PermissionError al escribir `.quality/active_uc.json` junto
a su propio código. El marcador solo sirve al hook del cliente (spec-guard) y
solo tiene sentido cuando servidor y cliente comparten disco (stdio).
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from server.tools import spec_driven as sd


def test_remote_server_does_not_touch_the_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, {"MCP_TRANSPORT": "http"}):
        sd._write_active_uc_marker("UC-1", "board")
        sd._clear_active_uc_marker()
    assert not (tmp_path / ".quality").exists()


def test_local_server_still_writes_and_clears_the_marker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}):
        sd._write_active_uc_marker("UC-1", "board", feature="f")
        marker = tmp_path / ".quality" / "active_uc.json"
        assert marker.exists() and '"uc_id": "UC-1"' in marker.read_text()
        sd._clear_active_uc_marker()
        assert not marker.exists()


def test_a_disk_error_never_breaks_the_call(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path(".quality").write_text("un fichero donde debería haber un directorio")
    with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}):
        sd._write_active_uc_marker("UC-1", "board")  # mkdir falla: no debe propagarse
        sd._clear_active_uc_marker()


# ── UC-12216: start_uc devuelve el marcador; el hook uc-state-marker lo escribe ──

import json  # noqa: E402

import pytest  # noqa: E402


def test_the_marker_is_returned_even_when_the_server_cannot_write_it(tmp_path, monkeypatch):
    """AC-01: con el MCP remoto no toca su disco, pero devuelve UC, historia y reserva."""
    monkeypatch.chdir(tmp_path)
    reservation = {"uc_id": "UC-1", "owner": "dev-ana", "reserved_at": "2026-11-18T10:00:00+00:00"}
    with patch.dict(os.environ, {"MCP_TRANSPORT": "http"}):
        marker = sd._write_active_uc_marker("UC-1", "board", feature="f", reservation=reservation, us_id="US-9")
    assert not (tmp_path / ".quality").exists()
    assert (marker["uc_id"], marker["board_id"], marker["us_id"]) == ("UC-1", "board", "US-9")
    assert marker["reservation"] == {
        "uc_id": "UC-1", "developer_id": "dev-ana", "reserved_at": "2026-11-18T10:00:00+00:00", "backend": "native",
    }
    with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}):
        written = sd._write_active_uc_marker("UC-1", "board", feature="f", reservation=reservation, us_id="US-9")
    on_disk = json.loads((tmp_path / ".quality" / "active_uc.json").read_text())
    assert on_disk == written  # el hook escribe lo mismo que escribiría el servidor local


class _Ctx:
    def __init__(self, config):
        self._config = config

    async def get_state(self, key):
        return self._config


@pytest.mark.parametrize("remote", [True, False])
async def test_start_uc_answer_carries_the_marker_in_content_mode(tmp_path, monkeypatch, remote):
    """AC-01: en modo contenido (FreeForm con MCP remoto) la respuesta lleva el marcador."""
    monkeypatch.chdir(tmp_path)
    us = {"id": "ff-us", "name": "US-09: H", "labels": ["US"], "state": "backlog", "meta": {"us_id": "US-09"}}
    uc = {"id": "ff-uc", "name": "UC-091: C", "labels": ["UC"], "state": "backlog", "parent_id": "ff-us",
          "meta": {"uc_id": "UC-091", "us_id": "US-09"}}
    ctx = _Ctx({"backend_type": "freeform", "content_only": True})
    with patch.dict(os.environ, {"MCP_TRANSPORT": "http" if remote else "stdio"}):
        out = await sd.start_uc("ff", "UC-091", ctx, items_content=json.dumps([us, uc]))
    marker = out["active_uc_marker"]
    assert (marker["uc_id"], marker["us_id"], marker["board_id"]) == ("UC-091", "US-09", "ff")
    assert not (tmp_path / ".quality").exists()  # en modo contenido el servidor nunca escribe
