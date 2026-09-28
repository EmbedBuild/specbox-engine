"""UC-3901 AC-04 — al conectar, el servidor anuncia exactamente la versión publicada.

La versión publicada es la de la última entrada de CHANGELOG.md; ENGINE_VERSION.yaml
tiene que decir lo mismo, y el handshake MCP (serverInfo.version) tiene que
devolverla tal cual. Si alguna de las tres se separa, esta prueba falla.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import patch

import yaml
from fastmcp import Client

from server.coordination.transport_auth import TransportAuthMiddleware
from server.server import _ENGINE_VERSION, main, mcp

ROOT = Path(__file__).resolve().parent.parent


def _published_version() -> str:
    for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^## \[(\d+\.\d+\.\d+)\]", line)
        if match:
            return match.group(1)
    raise AssertionError("CHANGELOG.md no tiene ninguna versión publicada")


def test_engine_version_yaml_is_the_published_version():
    declared = yaml.safe_load((ROOT / "ENGINE_VERSION.yaml").read_text(encoding="utf-8"))["version"]
    assert declared == _published_version()
    assert _ENGINE_VERSION == declared


async def test_the_handshake_announces_exactly_the_published_version():
    async with Client(mcp) as client:
        assert client.initialize_result.serverInfo.version == _published_version()


def test_http_transports_authenticate_every_request_and_stdio_does_not():
    for transport, expects_auth in (("streamable-http", True), ("sse", True), ("stdio", False)):
        with patch.dict(os.environ, {"MCP_TRANSPORT": transport}, clear=False), patch("server.server.mcp") as fake:
            main()
        middleware = fake.run.call_args.kwargs.get("middleware") or []
        classes = [m.cls for m in middleware]
        assert (TransportAuthMiddleware in classes) is expects_auth, transport
