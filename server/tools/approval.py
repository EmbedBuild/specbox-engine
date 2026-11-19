"""approve_criteria — una persona aprueba los criterios de una UC antes de implementar (US-125 · UC-12502).

La aprobación guarda la huella de los criterios vigentes con quién y cuándo (``server/approval.py``).
La da la sesión que habla con la persona: /prd la pide al terminar de sembrar y la registra si la
persona dice que sí. Un subagente no aprueba (``SUBAGENT_CANNOT_APPROVE``): el hook agent-identity
(o freeform-fragment en FreeForm) pone el contexto de Claude Code en la llamada, no el modelo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastmcp import Context

from ..approval import criteria_fingerprint, criteria_snapshot
from ..auth_gateway import get_session_backend
from ..review import client_identity
from . import _mutation_helpers as mh
from ._content_passing import returns_items_content

logger = structlog.get_logger("approval")

#: Cuántas UC aprueba una llamada como mucho.
MAX_UCS = 50


def _error(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "code": code, "error": message, **extra}


@returns_items_content
async def approve_criteria(
    board_id: str,
    ctx: Context,
    uc_ids: list[str] | None = None,
    us_id: str | None = None,
    approved_by: str | None = None,
    client_session_id: str = "",
    client_agent_id: str = "",
    client_agent_type: str = "",
    items_content: str | None = None,
) -> dict[str, Any]:
    """Record that a person approved the current acceptance criteria of some UCs (UC-12502).

    Pass `uc_ids` (up to 50) or `us_id` (every UC of that story). Each approval keeps the
    fingerprint of the UC's current criteria (id and text) with who and when; rewriting a
    criterion, adding one or retiring one leaves the UC unapproved until a new approval.
    Call it only after the person said yes (/prd asks at the end of seeding). A call from a
    subagent is rejected (SUBAGENT_CANNOT_APPROVE); the Claude Code context comes from a hook.
    `approved_by` is only used by FreeForm (the freeform-fragment hook puts the git author);
    native takes it from the session. Trello and Plane cannot keep it (APPROVAL_NOT_SUPPORTED).
    The measure ac_approval reads it in start_uc and find_next_uc.

    Returns:
        {success, approved: [{uc_id, criteria, fingerprint, by, at}], errors: [{uc_id, code, error}]}
    """
    identity = client_identity(client_session_id, client_agent_id, client_agent_type)
    if identity.get("agent_id"):
        return _error(
            "SUBAGENT_CANNOT_APPROVE",
            "Approving the criteria is a person's decision: a subagent cannot do it. Ask the person "
            "in the main session and call approve_criteria from there.",
        )
    wanted = [u.strip() for u in (uc_ids or []) if isinstance(u, str) and u.strip()]
    if not wanted and not (us_id or "").strip():
        return _error("NOTHING_TO_APPROVE", "Pass uc_ids or us_id.")
    if len(wanted) > MAX_UCS:
        return _error("TOO_MANY_UCS", f"At most {MAX_UCS} UCs per call; split it.")

    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if not getattr(backend, "STORES_SPEC_META", False):
            # Trello y Plane no tienen dónde guardarla (y escribir el meta reescribiría la descripción
            # en Plane): la medida ac_approval no se aplica en esos tableros.
            return _error(
                "APPROVAL_NOT_SUPPORTED",
                "This board (Trello or Plane) has nowhere to keep the approval of criteria; the "
                "measure ac_approval does not apply to it. Native and FreeForm keep it.",
            )
        targets: list[tuple[str, Any]] = []
        errors: list[dict[str, Any]] = []
        if wanted:
            for uc_id in dict.fromkeys(wanted):
                uc_item = await mh.find_uc(backend, board_id, uc_id)
                if uc_item is None:
                    errors.append({"uc_id": uc_id, "code": "UC_NOT_FOUND", "error": f"Use Case {uc_id} not found"})
                else:
                    targets.append((uc_id, uc_item))
        else:
            story = us_id.strip()  # type: ignore[union-attr]
            for uc_item in await backend.find_uc_items(board_id, story):
                uc_id = (uc_item.meta or {}).get("uc_id") or mh.parse_item_id(uc_item.name, "UC")[0]
                if uc_id:
                    targets.append((uc_id, uc_item))
            if not targets:
                return _error("US_NOT_FOUND", f"{story} has no UCs on this board.", us_id=story)
            if len(targets) > MAX_UCS:
                return _error("TOO_MANY_UCS", f"{story} has {len(targets)} UCs; approve them with uc_ids, "
                              f"at most {MAX_UCS} per call.", us_id=story)

        now = datetime.now(timezone.utc).isoformat()
        approved: list[dict[str, Any]] = []
        for uc_id, uc_item in targets:
            acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
            if not acs:
                errors.append({"uc_id": uc_id, "code": "NO_CRITERIA",
                               "error": f"{uc_id} has no acceptance criteria to approve."})
                continue
            record = {
                "fingerprint": criteria_fingerprint(acs),
                "criteria": criteria_snapshot(acs),
                "by": (approved_by or "").strip()[:100] or None,
                "at": now,
                "source": "person",
                **({"session_id": identity["session_id"]} if identity.get("session_id") else {}),
            }
            try:
                saved = await backend.record_criteria_approval(board_id, uc_item, record)
            except Exception as e:  # noqa: BLE001
                errors.append({"uc_id": uc_id, "code": "BACKEND_ERROR", "error": str(e)})
                continue
            approved.append({
                "uc_id": uc_id,
                "criteria": len(record["criteria"]),
                "fingerprint": saved["fingerprint"],
                "by": saved.get("by"),
                "at": saved.get("at"),
            })
        result: dict[str, Any] = {"success": bool(approved), "approved": approved, "errors": errors}
        if items_content is not None:
            result["items_content"] = backend.get_items_content()
        logger.info("criteria_approved", board=board_id, ucs=[a["uc_id"] for a in approved], errors=len(errors))
        return result
    finally:
        await backend.close()


def register_approval_tools(mcp_instance) -> None:
    """Registra la tool de aprobación de criterios (US-125 · UC-12502)."""
    mcp_instance.tool(
        description="Record that a person approved the current acceptance criteria of some UCs "
        "(uc_ids, or every UC of us_id) before implementing. Keeps a fingerprint of the criteria "
        "with who and when: changing, adding or retiring a criterion leaves the UC unapproved. "
        "Call it only after the person said yes; a subagent cannot approve "
        "(SUBAGENT_CANNOT_APPROVE). start_uc and find_next_uc read it (measure ac_approval)."
    )(approve_criteria)
