"""MCP tools to manage the encrypted alias store.

UC-017 (US-STRIPE-SWITCH-ACCOUNT): store_stripe_alias, list_stripe_aliases,
delete_stripe_alias. Resolution from alias to api_key inside other tools is
handled by ``lib.alias_store.resolve_alias`` directly — not exposed as a tool
because returning a plaintext key over MCP would defeat the purpose.
"""

from __future__ import annotations

import logging
from typing import Any

from ..lib.alias_store import (
    AliasStoreError,
    delete_alias,
    list_aliases,
    store_alias,
)
from ..lib.heartbeat import report_heartbeat
from ..lib.response import err, ok

logger = logging.getLogger("specbox_stripe_mcp.tools.alias_management")


def store_stripe_alias(
    *,
    alias_name: str,
    stripe_api_key: str,
    project_path: str,
) -> dict[str, Any]:
    """Persist a Stripe API credential under ``alias_name`` for this project.

    The credential is encrypted with AES-256-GCM using a key derived from the
    macOS Keychain (or the SPECBOX_ALIAS_PASSPHRASE env var on Linux/CI).
    Subsequent tools can refer to ``account_alias=alias_name`` instead of
    passing the raw ``stripe_api_key``.

    The plaintext key is NEVER logged, written to Engram, or returned in
    telemetry. Only metadata (alias name, key mode, timestamps).
    """
    try:
        meta = store_alias(
            alias_name=alias_name,
            stripe_api_key=stripe_api_key,
            project_path=project_path,
        )
    except AliasStoreError as exc:
        _emit_heartbeat(
            project_hint=project_path,
            tool="store_stripe_alias",
            success=False,
            code=exc.code,
        )
        return err(code=exc.code, message=exc.message, remediation=exc.remediation)

    _emit_heartbeat(
        project_hint=project_path,
        tool="store_stripe_alias",
        success=True,
        code="OK",
        extra={"alias_name": alias_name, "mode": meta["mode"]},
    )
    return ok(meta)


def list_stripe_aliases_tool(*, project_path: str) -> dict[str, Any]:
    """List the aliases stored for this project. Never returns plaintext keys."""
    try:
        items = list_aliases(project_path=project_path)
    except AliasStoreError as exc:
        return err(code=exc.code, message=exc.message, remediation=exc.remediation)

    _emit_heartbeat(
        project_hint=project_path,
        tool="list_stripe_aliases",
        success=True,
        code="OK",
        extra={"count": len(items)},
    )
    return ok({"aliases": items, "count": len(items)})


def delete_stripe_alias(
    *,
    alias_name: str,
    project_path: str,
    confirm_token: str,
) -> dict[str, Any]:
    """Delete an alias entry. Requires the literal confirm_token.

    The token must equal "I want to delete the {alias_name} alias" exactly,
    so a typo or a copy-paste from a chat doesn't accidentally drop credentials.
    """
    try:
        deleted = delete_alias(
            alias_name=alias_name,
            project_path=project_path,
            confirm_token=confirm_token,
        )
    except AliasStoreError as exc:
        _emit_heartbeat(
            project_hint=project_path,
            tool="delete_stripe_alias",
            success=False,
            code=exc.code,
        )
        return err(code=exc.code, message=exc.message, remediation=exc.remediation)

    _emit_heartbeat(
        project_hint=project_path,
        tool="delete_stripe_alias",
        success=True,
        code="OK",
        extra={"alias_name": alias_name, "deleted": deleted},
    )
    return ok({"alias_name": alias_name, "deleted": deleted})


# ---- Telemetry helper -----------------------------------------------------


def _emit_heartbeat(
    *,
    project_hint: str,
    tool: str,
    success: bool,
    code: str,
    extra: dict[str, Any] | None = None,
) -> None:
    try:
        report_heartbeat(
            project=project_hint,
            event_type="stripe_mcp_call",
            payload={
                "tool": tool,
                "success": success,
                "code": code,
                **(extra or {}),
            },
        )
    except Exception as exc:
        logger.debug("heartbeat emission skipped: %s", exc)
