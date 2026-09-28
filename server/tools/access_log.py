"""MCP tool to consult the tool access log — operator only (UC-3803 AC-02)."""

from __future__ import annotations

from datetime import datetime, time as dtime, timezone
from typing import Any

from fastmcp import Context, FastMCP

from ..coordination.access_log import (
    ANONYMOUS_LABEL,
    KIND_ANONYMOUS,
    MAX_QUERY_LIMIT,
    get_store,
    is_operator,
)
from ..coordination.identity import UnauthenticatedError
from ..coordination.scope import resolve_caller_scope, unauthenticated_envelope


def parse_bound(raw: str, *, end: bool) -> datetime | None:
    """Parse ``YYYY-MM-DD`` (whole day) or an ISO datetime; naive values are UTC."""
    text = (raw or "").strip()
    if not text:
        return None
    if len(text) == 10:
        day = datetime.strptime(text, "%Y-%m-%d").date()
        edge = dtime.max if end else dtime.min
        return datetime.combine(day, edge, tzinfo=timezone.utc)
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def register_access_log_tools(mcp: FastMCP) -> None:
    @mcp.tool
    async def get_tool_access_log(
        developer_id: str = "",
        date_from: str = "",
        date_to: str = "",
        tool: str = "",
        limit: int = 200,
        dev_token: str = "",
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Consult the per-call access log of this server (ecosystem operator only).

        Every tool call is recorded with date and time, tool name, the caller's
        identity (or "anónimo") and its outcome (UC-3803). Only the ecosystem
        operator (the cloud panel SuperAdmin) may read it: any other identity
        receives an authorization error and no entries; no identity receives
        UNAUTHENTICATED.

        Args:
            developer_id: Exact developer id to filter by; "anónimo" selects
                unidentified calls; empty = every identity.
            date_from: Start of the range, ``YYYY-MM-DD`` (whole day) or ISO datetime.
            date_to: End of the range, inclusive, same formats.
            tool: Exact tool name to filter by (empty = every tool).
            limit: Max entries, newest first (1..1000).
            dev_token: Developer token when the current session is not native.

        Entries never contain credentials, argument values or tool payloads —
        only argument names and short error codes (AC-03).
        """
        try:
            scope = await resolve_caller_scope(ctx, token=dev_token)
        except UnauthenticatedError:
            return unauthenticated_envelope(ctx)
        if not await is_operator(scope.developer_id):
            return {
                "error": "Only the ecosystem operator may consult the access log.",
                "code": "FORBIDDEN",
                "status": "forbidden",
                "entries": [],
            }

        try:
            since = parse_bound(date_from, end=False)
            until = parse_bound(date_to, end=True)
        except ValueError as exc:
            return {"error": f"Invalid date: {exc}", "code": "INVALID_DATE", "entries": []}
        if since and until and since > until:
            return {"error": "date_from is after date_to.", "code": "INVALID_DATE", "entries": []}

        wanted_dev: str | None = None
        wanted_kind: str | None = None
        ident = (developer_id or "").strip()
        if ident.lower() in {ANONYMOUS_LABEL, "anonimo", "anonymous"}:
            wanted_kind = KIND_ANONYMOUS
        elif ident:
            wanted_dev = ident

        capped = max(1, min(int(limit or 200), MAX_QUERY_LIMIT))
        entries = await get_store().query(
            developer_id=wanted_dev,
            identity_kind=wanted_kind,
            date_from=since,
            date_to=until,
            tool=tool.strip() or None,
            limit=capped,
        )
        return {
            "operator": scope.developer_id,
            "filters": {
                "developer_id": ident or None,
                "date_from": since.isoformat() if since else None,
                "date_to": until.isoformat() if until else None,
                "tool": tool.strip() or None,
                "limit": capped,
            },
            "total": len(entries),
            "truncated": len(entries) >= capped,
            "entries": entries,
        }
