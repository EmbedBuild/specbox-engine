"""T1 — set_edge_secret.

Bulk-creates or overwrites Supabase Edge Function secrets via
POST /v1/projects/{ref}/secrets.

Behavior (PRD §5, T1):
1. Validate PAT, project_ref, and secret name shape before any HTTP call.
2. GET current secrets to determine previously_present / previously_absent
   and to compute idempotency_hit for the heartbeat.
3. POST the new values. Supabase overwrites by name (no conflict on re-run).
4. Write Engram observation with NAMES ONLY — never values.
5. Emit heartbeat with idempotency_hit = (previously_absent is empty).

Critical security invariant: the ``secrets`` dict values flow to Supabase and
are never logged, never written to Engram, never appear in the response.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ..lib.engram_writer import format_config_content, write_config_observation
from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok
from ..lib.safety import (
    SafetyError,
    validate_access_token,
    validate_project_ref,
    validate_secret_names,
)
from ..lib.supabase_client import SupabaseAPIError, SupabaseClient

logger = logging.getLogger("specbox_supabase_mcp.tools.set_edge_secret")

TOOL_NAME = "set_edge_secret"


def set_edge_secret(
    *,
    supabase_access_token: str,
    project_ref: str,
    secrets: dict[str, str],
    project_hint: str = "unknown",
    base_url: str | None = None,
) -> dict[str, Any]:
    """Inject (create or overwrite) one or more Edge Function secrets in a Supabase project.

    Args:
        supabase_access_token: PAT (sbp_*).
        project_ref: 20-char project reference.
        secrets: {NAME: value} mapping. Names must be UPPER_SNAKE_CASE.
        project_hint: free-form tag for evidence + telemetry.
        base_url: optional override for self-hosted Supabase (v1.1 feature;
            defaults to https://api.supabase.com).
    """
    started = time.monotonic()

    # --- Safety: PAT + ref + names ---
    try:
        validate_access_token(supabase_access_token)
        validate_project_ref(project_ref)
    except SafetyError as safety_exc:
        _emit_heartbeat(
            project_ref=project_ref, project_hint=project_hint, success=False,
            duration_ms=(time.monotonic() - started) * 1000,
            code=safety_exc.code, idempotency_hit=False,
        )
        return err(code=safety_exc.code, message=safety_exc.message,
                   remediation=safety_exc.remediation)

    if not isinstance(secrets, dict) or not secrets:
        return _fail(
            project_ref=project_ref, project_hint=project_hint, started=started,
            code="E_INVALID_INPUT",
            message="secrets must be a non-empty dict of {NAME: value}.",
        )

    try:
        validate_secret_names(list(secrets.keys()))
    except SafetyError as safety_exc:
        return _fail(
            project_ref=project_ref, project_hint=project_hint, started=started,
            code=safety_exc.code, message=safety_exc.message,
        )

    if any(not isinstance(v, str) for v in secrets.values()):
        return _fail(
            project_ref=project_ref, project_hint=project_hint, started=started,
            code="E_INVALID_INPUT",
            message="All secret values must be strings.",
        )

    client = SupabaseClient(
        access_token=supabase_access_token,
        base_url=base_url,
        project_hint=project_hint,
    )

    # --- Step 1: inventory current secrets to compute idempotency ---
    existing_names = _list_names(client, project_ref)
    if isinstance(existing_names, dict):  # error dict
        return _finalize_error(existing_names, project_ref, project_hint, started)

    desired_names = sorted(secrets.keys())
    previously_present = sorted(set(desired_names) & set(existing_names))
    previously_absent = sorted(set(desired_names) - set(existing_names))

    # --- Step 2: POST the bulk payload ---
    body = [{"name": name, "value": value} for name, value in secrets.items()]
    try:
        client.call("secrets.create", "POST",
                    f"/v1/projects/{project_ref}/secrets", json=body)
    except SupabaseAPIError as api_exc:
        return _classified_error(api_exc, project_ref, project_hint, started)

    duration_ms = (time.monotonic() - started) * 1000
    all_overwritten = not previously_absent

    evidence: dict[str, Any] = {}
    try:
        obs_id = write_config_observation(
            project=project_hint,
            title=f"supabase-mcp: {TOOL_NAME} on {project_hint}",
            content=format_config_content(
                tool=TOOL_NAME,
                project=project_hint,
                mode="cloud",
                result_summary=(
                    f"applied={len(desired_names)} "
                    f"previously_present={len(previously_present)} "
                    f"all_overwritten={all_overwritten}"
                ),
                ids_created=previously_absent,
                ids_reused=previously_present,
                duration_ms=duration_ms,
                extra={"project_ref": project_ref},
            ),
        )
        if obs_id:
            evidence["engram_observation_id"] = obs_id
    except Exception as exc:
        logger.debug("engram write skipped: %s", exc)

    _emit_heartbeat(
        project_ref=project_ref, project_hint=project_hint, success=True,
        duration_ms=duration_ms, code="OK", idempotency_hit=all_overwritten,
    )

    return ok(
        {
            "project_ref": project_ref,
            "applied": desired_names,
            "all_overwritten": all_overwritten,
            "previously_present": previously_present,
            "previously_absent": previously_absent,
        },
        evidence=evidence or None,
    )


# --- Internals --------------------------------------------------------------


def _list_names(client: SupabaseClient, project_ref: str) -> list[str] | dict[str, Any]:
    """GET existing secret names. Returns list on success, error dict on failure."""
    try:
        response = client.call(
            "secrets.list", "GET", f"/v1/projects/{project_ref}/secrets"
        )
    except SupabaseAPIError as api_exc:
        return _shape_error(api_exc)
    try:
        body = response.json()
    except Exception:
        body = []
    return [str(item.get("name", "")) for item in (body or []) if item.get("name")]


def _classified_error(
    api_exc: SupabaseAPIError,
    project_ref: str,
    project_hint: str,
    started: float,
) -> dict[str, Any]:
    """Map a SupabaseAPIError to our stable error codes + emit heartbeat."""
    shaped = _shape_error(api_exc)
    return _finalize_error(shaped, project_ref, project_hint, started)


def _shape_error(api_exc: SupabaseAPIError) -> dict[str, Any]:
    """Translate HTTP status into our error vocabulary."""
    code = "E_SUPABASE_ERROR"
    if api_exc.status_code == 401:
        code = "E_INVALID_TOKEN"
    elif api_exc.status_code == 403:
        code = "E_INSUFFICIENT_PERMISSIONS"
    elif api_exc.status_code == 404:
        code = "E_PROJECT_NOT_FOUND"
    elif api_exc.status_code == 429:
        code = "E_RATE_LIMITED"
    return err(code=code, message=api_exc.message)


def _finalize_error(
    error_dict: dict[str, Any],
    project_ref: str,
    project_hint: str,
    started: float,
) -> dict[str, Any]:
    code = error_dict["error"]["code"]
    _emit_heartbeat(
        project_ref=project_ref, project_hint=project_hint, success=False,
        duration_ms=(time.monotonic() - started) * 1000,
        code=code, idempotency_hit=False,
    )
    return error_dict


def _fail(
    *,
    project_ref: str,
    project_hint: str,
    started: float,
    code: str,
    message: str,
) -> dict[str, Any]:
    _emit_heartbeat(
        project_ref=project_ref, project_hint=project_hint, success=False,
        duration_ms=(time.monotonic() - started) * 1000,
        code=code, idempotency_hit=False,
    )
    return err(code=code, message=message)


def _emit_heartbeat(
    *,
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
