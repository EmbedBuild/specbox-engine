"""Best-effort telemetry to the SpecBox engine MCP.

If SPECBOX_ENGINE_MCP_URL is unset or unreachable, drop silently.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("specbox_stripe_mcp.heartbeat")

HEARTBEAT_TIMEOUT_S = 2.0


def _endpoint() -> str | None:
    base = os.getenv("SPECBOX_ENGINE_MCP_URL")
    if not base:
        return None
    return base.rstrip("/") + "/api/report/heartbeat"


def report_heartbeat(
    *,
    project: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Fire-and-forget POST. Never raises, never blocks more than 2s."""
    url = _endpoint()
    if url is None:
        return
    token = os.getenv("SPECBOX_SYNC_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "project": project,
        "event_type": event_type,
        "payload": payload,
    }
    try:
        httpx.post(url, json=body, headers=headers, timeout=HEARTBEAT_TIMEOUT_S)
    except Exception as exc:
        logger.debug("heartbeat dropped: %s", exc)


def report_healing(
    *,
    project: str,
    hook: str,
    root_cause: str,
    resolution: str,
) -> None:
    url = os.getenv("SPECBOX_ENGINE_MCP_URL")
    if not url:
        return
    endpoint = url.rstrip("/") + "/api/report/healing"
    token = os.getenv("SPECBOX_SYNC_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = {
        "project": project,
        "agent": "specbox-stripe-mcp",
        "hook": hook,
        "root_cause": root_cause,
        "resolution": resolution,
    }
    try:
        httpx.post(endpoint, json=body, headers=headers, timeout=HEARTBEAT_TIMEOUT_S)
    except Exception as exc:
        logger.debug("healing report dropped: %s", exc)
