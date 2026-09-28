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
