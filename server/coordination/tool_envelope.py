"""Answer a tool call from a middleware with a structured envelope.

A tool whose return annotation is not a plain object (``dict | None``,
``list``…) has an output schema that wraps the value under ``result``
(``x-fastmcp-wrap-result``). An envelope sent for such a tool is wrapped the
same way when the wrapped value may be an object; when it may not (a tool that
returns a list) the envelope goes back as an error result, which the protocol
does not validate against the output schema. Used by the UC-8603 and UC-8604
middlewares.
"""

from __future__ import annotations

import json
from typing import Any


def _accepts_object(schema: dict[str, Any]) -> bool:
    if not schema:
        return True
    kind = schema.get("type")
    if kind == "object" or (isinstance(kind, list) and "object" in kind):
        return True
    return any(_accepts_object(s) for s in schema.get("anyOf", []) + schema.get("oneOf", []))


async def envelope_result(context: Any, tool: str, payload: dict[str, Any]) -> Any:
    from fastmcp.tools.tool import ToolResult
    from mcp.types import TextContent

    text = [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]
    schema: dict[str, Any] = {}
    server = getattr(getattr(context, "fastmcp_context", None), "fastmcp", None)
    if server is not None:
        try:
            schema = (await server.get_tool(tool)).output_schema or {}
        except Exception:  # noqa: BLE001 - an unknown tool keeps the plain payload
            schema = {}
    if not schema.get("x-fastmcp-wrap-result"):
        return ToolResult(content=text, structured_content=payload)
    if _accepts_object((schema.get("properties") or {}).get("result") or {}):
        return ToolResult(content=text, structured_content={"result": payload})
    return ToolResult(content=text, structured_content=None, is_error=True)  # type: ignore[call-arg]
