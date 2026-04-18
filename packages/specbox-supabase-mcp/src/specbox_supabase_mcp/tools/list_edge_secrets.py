"""T2 — list_edge_secrets.

Read-only: GET /v1/projects/{ref}/secrets returns names + updated_at (never
values, by design of the Supabase API).

If ``expected_names`` is provided, computes ``missing_names`` and ``extra_names``
so skills can diff without implementing the logic themselves.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok
from ..lib.safety import SafetyError, validate_access_token, validate_project_ref
from ..lib.supabase_client import SupabaseAPIError, SupabaseClient

logger = logging.getLogger("specbox_supabase_mcp.tools.list_edge_secrets")

TOOL_NAME = "list_edge_secrets"


def list_edge_secrets(
    *,
    supabase_access_token: str,
    project_ref: str,
    expected_names: list[str] | None = None,
    project_hint: str = "unknown",
    base_url: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        validate_access_token(supabase_access_token)
        validate_project_ref(project_ref)
    except SafetyError as safety_exc:
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000, safety_exc.code)
        return err(code=safety_exc.code, message=safety_exc.message,
                   remediation=safety_exc.remediation)

    client = SupabaseClient(
        access_token=supabase_access_token,
        base_url=base_url,
        project_hint=project_hint,
    )
    try:
        response = client.call(
            "secrets.list", "GET", f"/v1/projects/{project_ref}/secrets"
        )
    except SupabaseAPIError as api_exc:
        code = _classify(api_exc.status_code)
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000, code)
        return err(code=code, message=api_exc.message)

    try:
        body = response.json() or []
    except Exception:
        body = []

    names = sorted(
        str(item.get("name", ""))
        for item in body
        if isinstance(item, dict) and item.get("name")
    )
    last_updated_at = max(
        (str(item.get("updated_at", "")) for item in body if isinstance(item, dict)),
        default="",
    )

    data: dict[str, Any] = {
        "project_ref": project_ref,
        "names": names,
        "count": len(names),
        "last_updated_at": last_updated_at,
    }

    if expected_names is not None:
        expected_set = set(expected_names)
        actual_set = set(names)
        data["missing_names"] = sorted(expected_set - actual_set)
        data["extra_names"] = sorted(actual_set - expected_set)

    duration_ms = (time.monotonic() - started) * 1000
    _emit(project_ref, project_hint, True, duration_ms, "OK")
    return ok(data)


# --- internals --------------------------------------------------------------


def _classify(status: int) -> str:
    return {
        401: "E_INVALID_TOKEN",
        403: "E_INSUFFICIENT_PERMISSIONS",
        404: "E_PROJECT_NOT_FOUND",
        429: "E_RATE_LIMITED",
    }.get(status, "E_SUPABASE_ERROR")


def _emit(
    project_ref: str,
    project_hint: str,
    success: bool,
    duration_ms: float,
    code: str,
) -> None:
    try:
        report_heartbeat(
            project=project_hint,
            event_type="supabase_mcp_call",
            payload={
                "tool": TOOL_NAME,
                "success": success,
                "duration_ms": round(duration_ms, 2),
                "project_ref": project_ref,
                "code": code,
                "idempotency_hit": True,  # read-only always idempotent
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
