"""The Stitch MCP schema the client is checked against (US-84 · UC-8408).

``mcp_tools_schema.json`` is a snapshot of ``tools/list`` from
https://stitch.googleapis.com/mcp. ``tests/test_stitch_contract.py`` validates
the arguments every :class:`server.stitch_client.StitchClient` method sends
against it, so a call the API would reject fails in CI instead of in front of
a developer.

Refresh it when Google changes the API::

    STITCH_API_KEY=... python -m server.stitch_schema

The key is read from the environment and only sent to Stitch: it is never
written to the snapshot, to a log or to the output.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

STITCH_MCP_URL = "https://stitch.googleapis.com/mcp"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / ".quality"
    / "evidence"
    / "stitch_smoke"
    / "mcp_tools_schema.json"
)


def fetch_tools(api_key: str, *, url: str = STITCH_MCP_URL, timeout: float = 30.0) -> list[dict[str, Any]]:
    """Return the ``tools`` of a live ``tools/list`` call."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "x-goog-api-key": api_key,
    }
    body = {"jsonrpc": "2.0", "id": "schema", "method": "tools/list", "params": {}}
    resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    if "text/event-stream" in resp.headers.get("content-type", ""):
        data = next(
            json.loads(line[6:])
            for line in resp.text.splitlines()
            if line.startswith("data: ") and line[6:].strip()
        )
    else:
        data = resp.json()
    if "error" in data:
        raise RuntimeError(f"tools/list failed: {data['error'].get('message')}")
    return data["result"]["tools"]


def snapshot(tools: list[dict[str, Any]], *, url: str = STITCH_MCP_URL) -> dict[str, Any]:
    return {
        "endpoint": url,
        "fetched_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool_count": len(tools),
        "tools": sorted(tools, key=lambda t: t["name"]),
    }


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def input_schema(tool_name: str, schema: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The ``inputSchema`` of ``tool_name``, or ``None`` if Stitch has no such tool."""
    schema = schema or load_schema()
    for tool in schema["tools"]:
        if tool["name"] == tool_name:
            return tool["inputSchema"]
    return None


def closed(schema: dict[str, Any]) -> dict[str, Any]:
    """A copy where every object with ``properties`` rejects unknown keys.

    Stitch does not declare ``additionalProperties: false``, but it answers an
    unknown argument with «invalid argument»: the contract has to say so.
    """
    schema = copy.deepcopy(schema)

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if "properties" in node and "additionalProperties" not in node:
                node["additionalProperties"] = False
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for value in node:
                _walk(value)

    _walk(schema)
    return schema


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the Stitch MCP schema snapshot.")
    parser.add_argument("--api-key-env", default="STITCH_API_KEY", help="environment variable with the key")
    parser.add_argument("--output", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args(argv)

    api_key = os.environ.get(args.api_key_env, "")
    if not api_key:
        print(f"Set {args.api_key_env} with your Stitch API key.", file=sys.stderr)
        return 2
    tools = fetch_tools(api_key)
    data = snapshot(tools)
    args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{data['tool_count']} tools from {data['endpoint']} at {data['fetched_at']} → {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
