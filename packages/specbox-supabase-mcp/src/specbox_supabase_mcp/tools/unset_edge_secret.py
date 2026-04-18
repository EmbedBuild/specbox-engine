"""T3 — unset_edge_secret.

Deletes one or more secrets from a Supabase project via
DELETE /v1/projects/{ref}/secrets with body [name, name, ...].

Safety:
- Requires literal ``confirm_token``.
- Writes a pre-action Engram observation with the exact names about to be
  deleted (audit trail) BEFORE the DELETE is sent.
- Reports deleted vs skipped (names that weren't present to begin with).
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..lib.engram_writer import format_config_content, write_config_observation
from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok
from ..lib.safety import SafetyError, validate_access_token, validate_project_ref
from ..lib.supabase_client import SupabaseAPIError, SupabaseClient

logger = logging.getLogger("specbox_supabase_mcp.tools.unset_edge_secret")

TOOL_NAME = "unset_edge_secret"
CONFIRM_TOKEN_LITERAL = "I understand this removes secrets from the Supabase project"


def unset_edge_secret(
    *,
    supabase_access_token: str,
    project_ref: str,
    names: list[str],
    confirm_token: str,
    project_hint: str = "unknown",
    base_url: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    try:
        validate_access_token(supabase_access_token)
        validate_project_ref(project_ref)
    except SafetyError as safety_exc:
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000, safety_exc.code, False)
        return err(code=safety_exc.code, message=safety_exc.message,
                   remediation=safety_exc.remediation)

    if confirm_token != CONFIRM_TOKEN_LITERAL:
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000,
              "E_CONFIRM_TOKEN_MISMATCH", False)
        return err(
            code="E_CONFIRM_TOKEN_MISMATCH",
            message=(
                f"confirm_token does not match the required literal. "
                f"Expected {CONFIRM_TOKEN_LITERAL!r}."
            ),
        )

    if not isinstance(names, list) or not names:
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000, "E_INVALID_INPUT", False)
        return err(
            code="E_INVALID_INPUT",
            message="names must be a non-empty list of secret names to delete.",
        )
    if any(not isinstance(n, str) or not n for n in names):
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000, "E_INVALID_INPUT", False)
        return err(
            code="E_INVALID_INPUT",
            message="all entries in names must be non-empty strings.",
        )

    client = SupabaseClient(
        access_token=supabase_access_token,
        base_url=base_url,
        project_hint=project_hint,
    )

    # --- Step 1: GET existing to compute deleted / skipped ---
    try:
        list_response = client.call(
            "secrets.list", "GET", f"/v1/projects/{project_ref}/secrets"
        )
    except SupabaseAPIError as api_exc:
        code = _classify(api_exc.status_code)
        _emit(project_ref, project_hint, False,
              (time.monotonic() - started) * 1000, code, False)
        return err(code=code, message=api_exc.message)

    try:
        existing = list_response.json() or []
    except Exception:
        existing = []
    existing_names = {str(item.get("name", "")) for item in existing if item.get("name")}

    deleted = sorted(n for n in set(names) if n in existing_names)
    skipped = sorted(n for n in set(names) if n not in existing_names)

    # --- Step 2: pre-action audit observation ---
    try:
        write_config_observation(
            project=project_hint,
            title=f"supabase-mcp: {TOOL_NAME} PRE-ACTION on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode="cloud",
                result_summary=f"about-to-delete={len(deleted)} skipped={len(skipped)}",
                ids_created=[],
                ids_reused=deleted,
                extra={
                    "project_ref": project_ref,
                    "names_to_delete": deleted,
                    "names_skipped": skipped,
                },
            ),
        )
    except Exception as exc:
        logger.debug("engram pre-action write skipped: %s", exc)

    # --- Step 3: DELETE (only if there's something to delete) ---
    if deleted:
        try:
            client.call(
                "secrets.delete", "DELETE",
                f"/v1/projects/{project_ref}/secrets",
                json=deleted,
            )
        except SupabaseAPIError as api_exc:
            code = _classify(api_exc.status_code)
            _emit(project_ref, project_hint, False,
                  (time.monotonic() - started) * 1000, code, False)
            return err(code=code, message=api_exc.message)

    duration_ms = (time.monotonic() - started) * 1000
    idempotency_hit = not deleted  # no-op = idempotency_hit
    _emit(project_ref, project_hint, True, duration_ms, "OK", idempotency_hit)

    return ok(
        {
            "project_ref": project_ref,
            "deleted": deleted,
            "skipped": skipped,
            "before_count": len(existing_names),
            "after_count": len(existing_names) - len(deleted),
        }
    )


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
    idempotency_hit: bool,
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
                "idempotency_hit": idempotency_hit,
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
