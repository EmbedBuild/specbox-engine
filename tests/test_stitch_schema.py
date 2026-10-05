"""US-84 · UC-8408 AC-01 — the schema refresh never writes the API key."""

from __future__ import annotations

import json

import httpx
import respx

from server import stitch_schema

KEY = "AIza-test-key-never-written-1234"
TOOLS = [
    {"name": "list_screens", "inputSchema": {"type": "object", "properties": {"projectId": {"type": "string"}}}},
    {"name": "create_project", "inputSchema": {"type": "object", "properties": {"title": {"type": "string"}}}},
]


def _tools_list() -> httpx.Response:
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": "schema", "result": {"tools": TOOLS}})


@respx.mock
def test_refresh_writes_the_snapshot_without_the_key(tmp_path, monkeypatch, capsys):
    route = respx.post(stitch_schema.STITCH_MCP_URL).mock(return_value=_tools_list())
    monkeypatch.setenv("STITCH_API_KEY", KEY)
    out = tmp_path / "schema.json"

    assert stitch_schema.main(["--output", str(out)]) == 0

    assert route.calls[0].request.headers["x-goog-api-key"] == KEY
    assert json.loads(route.calls[0].request.content)["method"] == "tools/list"
    text = out.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["tool_count"] == 2
    assert [t["name"] for t in data["tools"]] == ["create_project", "list_screens"]
    assert data["fetched_at"].endswith("Z")
    printed = capsys.readouterr()
    assert KEY not in text and KEY not in printed.out and KEY not in printed.err


@respx.mock
def test_refresh_reads_server_sent_events(tmp_path, monkeypatch):
    body = "data: " + json.dumps({"jsonrpc": "2.0", "id": "schema", "result": {"tools": TOOLS}}) + "\n\n"
    respx.post(stitch_schema.STITCH_MCP_URL).mock(
        return_value=httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    )
    monkeypatch.setenv("STITCH_API_KEY", KEY)
    out = tmp_path / "schema.json"
    assert stitch_schema.main(["--output", str(out)]) == 0
    assert json.loads(out.read_text())["tool_count"] == 2


def test_refresh_without_key_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("STITCH_API_KEY", raising=False)
    out = tmp_path / "schema.json"
    assert stitch_schema.main(["--output", str(out)]) == 2
    assert not out.exists()
    assert "STITCH_API_KEY" in capsys.readouterr().err
