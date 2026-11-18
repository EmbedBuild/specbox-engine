"""record_review_verdict — el veredicto de quien revisa una UC (US-124 · UC-12402).

Un agente evaluador (AG-09b en un subagente) registra «aceptada» o «devuelta» para una UC en
revisión. El tablero guarda quién lo dio, desde qué contexto de Claude Code (lo pone un hook, no el
modelo) y si era independiente de quien implementó; rechaza el veredicto del mismo contexto que
implementó (``SAME_AGENT_VERDICT``). Una persona no usa esta tool: acepta o devuelve desde el panel
(UC-12404), porque por MCP no se distingue a la persona del agente que usa su token (US-76).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastmcp import Context

from ..review import ReviewError, client_identity, is_independent, same_context, validate_verdict
from . import _mutation_helpers as mh
from ._content_passing import returns_items_content
from ..auth_gateway import get_session_backend

logger = structlog.get_logger("review")


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "code": code, "error": message, **extra}


@returns_items_content
async def record_review_verdict(
    board_id: str,
    uc_id: str,
    verdict: str,
    ctx: Context,
    reason: str | None = None,
    client_session_id: str = "",
    client_agent_id: str = "",
    client_agent_type: str = "",
    items_content: str | None = None,
) -> dict[str, Any]:
    """Register the review verdict of an evaluator on a UC in review (UC-12402).

    `verdict`: "accepted" or "returned"; returning needs a `reason` of 10 to 500 characters (what to
    fix, no credentials). The Claude Code context (`client_session_id`, `client_agent_id`,
    `client_agent_type`) is filled by the agent-identity / freeform-fragment hooks from the hook
    input, never by the model. A verdict from the same context that started the UC is rejected
    with SAME_AGENT_VERDICT; one without that context is kept but does not count as independent.
    The merge-guard hook (measure independent_review) reads these verdicts before `gh pr merge`.

    Returns:
        {success, uc_id, verdict, independent, by: {kind, developer_id, session_id, agent_id,
         agent_type}, at, note?}
    """
    try:
        verdict, why = validate_verdict(verdict, reason)
    except ReviewError as e:
        return _error(e.code, str(e), uc_id=uc_id)
    if why and "exposure_credentials" in mh.detect_ac_exposure(why):
        return _error("SENSITIVE_DATA", "the reason looks like it carries a credential; describe it without it",
                      uc_id=uc_id)
    identity = client_identity(client_session_id, client_agent_id, client_agent_type)

    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        uc_item = await mh.find_uc(backend, board_id, uc_id)
        if not uc_item:
            return _error("UC_NOT_FOUND", f"Use Case {uc_id} not found", uc_id=uc_id)
        if uc_item.state != "review":
            return _error(
                "UC_NOT_IN_REVIEW",
                f"{uc_id} is in «{uc_item.state}»: a review verdict is for a UC in review "
                "(move it with move_uc after marking its criteria).",
                uc_id=uc_id,
            )
        implementer = uc_item.meta.get("implementer") if isinstance(uc_item.meta, dict) else None
        implementer = implementer if isinstance(implementer, dict) else None
        if same_context(implementer, identity):
            return _error(
                "SAME_AGENT_VERDICT",
                f"The verdict comes from the same context that implemented {uc_id} (session and agent). "
                "Launch an isolated evaluator (a subagent) or ask a person to accept it in the panel.",
                uc_id=uc_id,
            )
        developer_id = ""
        if hasattr(backend, "_require_membership_cached"):
            try:
                developer_id = (await backend._require_membership_cached(board_id)).developer_id
            except Exception:  # noqa: BLE001 — the write below re-checks membership and reports it
                developer_id = ""
        record = {
            "verdict": verdict,
            "by_kind": "agent",
            "developer_id": developer_id or None,
            **identity,
            "independent": is_independent(implementer, identity),
            "reason": why,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            saved = await backend.record_review_verdict(board_id, uc_item, record)
        except Exception as e:  # noqa: BLE001
            return _error("BACKEND_ERROR", str(e), uc_id=uc_id)
        result: dict[str, Any] = {
            "success": True,
            "uc_id": uc_id,
            "verdict": verdict,
            "independent": saved["independent"],
            "by": {"kind": "agent", "developer_id": saved.get("developer_id"),
                   **{k: saved[k] for k in ("session_id", "agent_id", "agent_type") if saved.get(k)}},
            "at": saved["at"],
        }
        if not saved["independent"]:
            result["note"] = (
                "Kept, but it does not count as independent: it came without the Claude Code context "
                "(the agent-identity hook) or from the main session of a UC whose implementer is unknown."
            )
        if items_content is not None:
            result["items_content"] = backend.get_items_content()
        return result
    finally:
        await backend.close()


def register_review_tools(mcp_instance) -> None:
    """Registra la tool de revisión independiente (US-124 · UC-12402)."""
    mcp_instance.tool(
        description="Register the review verdict («accepted» or «returned», with a reason) of an "
        "evaluator on a UC in review. The Claude Code context comes from a hook; a verdict from "
        "the same context that implemented the UC is rejected (SAME_AGENT_VERDICT). merge-guard "
        "reads these verdicts (measure independent_review) before gh pr merge."
    )(record_review_verdict)
