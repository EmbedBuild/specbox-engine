"""Las decisiones aplazadas del autopilot en el board (US-99 · UC-9902).

Cuatro tools sobre ``autopilot_decisions`` (migración 0032):

* ``publish_decision`` — la sesión aplaza una decisión: además de anotarla en
  ``doc/app/decisions_queue.md`` (``enqueue_decision_tool``, mismo id ``dq-…``), la publica aquí
  con su UC, la pregunta, las opciones y la opción por defecto que aplicó mientras tanto. Nunca
  credenciales (AC-01).
* ``list_pending_decisions`` — las que siguen esperando a una persona (AC-03).
* ``resolve_decision`` — una persona elige una opción (desde una sesión; el panel y la app lo hacen
  por su API con el mismo efecto). Quedan quién, cuándo y qué (AC-02).
* ``take_resolved_decisions`` — al arrancar, la sesión recoge las resueltas que aún no había
  aplicado y las da por aplicadas: no vuelve a preguntarlas (AC-02).

Identidad y alcance como el latido (UC-9901): ``resolve_caller_scope``; el proyecto es el
parámetro o el de la sesión native; si no eres miembro, el proyecto no existe para ti.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from fastmcp import Context

from ..app_docs.queue import INVIOLABLE_FOR_QUEUE, _new_engine_id
from ..coordination.identity import UnauthenticatedError
from ..coordination.scope import resolve_caller_scope
from .session_heartbeat import PROJECT_ID, UC_ID, _not_visible, _session_project, _unauthenticated
from ._mutation_helpers import detect_ac_exposure

logger = structlog.get_logger(__name__)

DECISION_ID = re.compile(r"^dq-[0-9]{8}T[0-9]{6}-[0-9a-f]{4}-[a-z0-9]{1,6}$")
DECISION_KEY = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
OPTION_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
VIAS = frozenset({"panel", "app", "session"})


def _invalid(message: str) -> dict[str, Any]:
    return {"success": False, "code": "INVALID_DECISION", "error": message}


def validate_decision(
    *, decision_key: str, question: str, options: Any, default_option: str, uc_id: str | None, decision_id: str
) -> dict[str, Any] | None:
    """El error de una decisión, o None si se puede publicar. Pura."""
    if not DECISION_KEY.match(decision_key or ""):
        return _invalid("decision_key no válida.")
    if decision_key in INVIOLABLE_FOR_QUEUE:
        return {
            "success": False,
            "code": "QUEUE_NOT_ALLOWED",
            "error": f"{decision_key!r} no se aplaza: se pregunta en el momento.",
        }
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 300:
        return _invalid("La pregunta tiene que tener de 3 a 300 caracteres.")
    if not isinstance(options, list) or not 2 <= len(options) <= 6:
        return _invalid("Hacen falta de 2 a 6 opciones.")
    ids: list[str] = []
    for o in options:
        if not isinstance(o, dict) or not OPTION_ID.match(str(o.get("id", ""))):
            return _invalid("Cada opción es {id, label} con un id corto en minúsculas.")
        label = o.get("label")
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120:
            return _invalid("Cada opción necesita una etiqueta de 1 a 120 caracteres.")
        ids.append(o["id"])
    if len(set(ids)) != len(ids):
        return _invalid("Hay opciones con el mismo id.")
    if default_option not in ids:
        return _invalid("La opción por defecto tiene que ser una de las opciones.")
    if uc_id is not None and not UC_ID.match(uc_id):
        return _invalid("uc_id no válido: «UC-1234».")
    if decision_id and not DECISION_ID.match(decision_id):
        return _invalid("decision_id no válido: el id dq-… de la cola.")
    texto = " ".join([question, *(o["label"] for o in options)])
    if any("credential" in tag for tag in detect_ac_exposure(texto)):
        return {
            "success": False,
            "code": "SENSITIVE_DATA",
            "error": "La decisión menciona credenciales: descríbela sin ellas.",
        }
    return None


async def _scope_for(ctx: Context | None, project_id: str, dev_token: str):
    """(project_id, scope) o el envelope de error. Lo ajeno responde como inexistente."""
    pid = (project_id or "").strip() or await _session_project(ctx)
    if not PROJECT_ID.match(pid or ""):
        return None, {"success": False, "code": "INVALID_DECISION", "error": "project_id no válido."}
    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except UnauthenticatedError:
        return None, _unauthenticated()
    if pid not in scope.project_ids:
        return None, _not_visible(pid)
    return (pid, scope), None


def _row(row: Any) -> dict[str, Any]:
    data = dict(row)
    if isinstance(data.get("options"), str):
        data["options"] = json.loads(data["options"])
    for key in ("created_at", "resolved_at", "applied_at"):
        if data.get(key) is not None:
            data[key] = data[key].isoformat()
    return data


_COLUMNS = (
    "decision_id, uc_id, decision_key, question, options, default_option, created_by, created_at, "
    "resolved_at, resolved_by, resolution, resolved_via, applied_at"
)


async def publish_decision(
    ctx: Context,
    decision_key: str,
    question: str,
    options: list[dict[str, str]],
    default_option: str,
    uc_id: str | None = None,
    decision_id: str = "",
    project_id: str = "",
    dev_token: str = "",
) -> dict[str, Any]:
    """Publica en el board una decisión que el autopilot ha aplazado (UC-9902 AC-01).

    ``options`` = [{"id": "a", "label": "…"}, …] (de 2 a 6); ``default_option`` es la que la sesión
    aplica mientras nadie decide. Usa el mismo ``decision_id`` que devolvió
    ``enqueue_decision_tool`` para que la cola del proyecto y el board hablen de lo mismo. Repetir
    la llamada con el mismo id no duplica nada. Rechaza las decisiones que no se aplazan y las que
    mencionan credenciales.
    """
    error = validate_decision(
        decision_key=decision_key,
        question=question,
        options=options,
        default_option=default_option,
        uc_id=uc_id,
        decision_id=decision_id,
    )
    if error is not None:
        return error
    found, error = await _scope_for(ctx, project_id, dev_token)
    if error is not None:
        return error
    pid, scope = found
    did = decision_id or _new_engine_id(decision_key)
    opciones = [{"id": o["id"], "label": o["label"].strip()} for o in options]

    from ..db.pool import get_pool

    pool = await get_pool()
    row = await pool.fetchrow(
        f"""
        INSERT INTO autopilot_decisions
            (project_id, decision_id, uc_id, decision_key, question, options, default_option, created_by)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
        ON CONFLICT (project_id, decision_id) DO NOTHING
        RETURNING {_COLUMNS}
        """,
        pid,
        did,
        uc_id,
        decision_key,
        question.strip(),
        json.dumps(opciones, ensure_ascii=False),
        default_option,
        scope.developer_id,
    )
    nueva = row is not None
    if row is None:
        row = await pool.fetchrow(
            f"SELECT {_COLUMNS} FROM autopilot_decisions WHERE project_id = $1 AND decision_id = $2", pid, did
        )
    logger.info("autopilot_decision_published", project_id=pid, decision_key=decision_key, new=nueva)
    return {"success": True, "project_id": pid, "created": nueva, "decision": _row(row)}


async def list_pending_decisions(ctx: Context, project_id: str = "", dev_token: str = "") -> dict[str, Any]:
    """Las decisiones del proyecto que esperan a una persona, de la más antigua a la más reciente."""
    found, error = await _scope_for(ctx, project_id, dev_token)
    if error is not None:
        return error
    pid, _scope = found

    from ..db.pool import get_pool

    pool = await get_pool()
    rows = await pool.fetch(
        f"SELECT {_COLUMNS} FROM autopilot_decisions "
        "WHERE project_id = $1 AND resolved_at IS NULL ORDER BY created_at, decision_id",
        pid,
    )
    pendientes = [_row(r) for r in rows]
    return {"success": True, "project_id": pid, "total": len(pendientes), "decisions": pendientes}


async def resolve_decision(
    ctx: Context,
    decision_id: str,
    option: str,
    via: str = "session",
    project_id: str = "",
    dev_token: str = "",
) -> dict[str, Any]:
    """Resuelve una decisión con una de sus opciones (UC-9902 AC-02).

    Quedan quién, cuándo, qué opción y desde dónde (``via`` = session, panel o app). Una decisión
    ya resuelta no cambia: devuelve la resolución que tenía.
    """
    if not DECISION_ID.match(decision_id or ""):
        return _invalid("decision_id no válido.")
    if not OPTION_ID.match(option or ""):
        return _invalid("option no válida.")
    if via not in VIAS:
        return _invalid("via tiene que ser session, panel o app.")
    found, error = await _scope_for(ctx, project_id, dev_token)
    if error is not None:
        return error
    pid, scope = found

    from ..db.pool import get_pool

    pool = await get_pool()
    row = await pool.fetchrow(
        f"""
        UPDATE autopilot_decisions
           SET resolved_at = now(), resolved_by = $3, resolution = $4, resolved_via = $5
         WHERE project_id = $1 AND decision_id = $2 AND resolved_at IS NULL
           AND options @> jsonb_build_array(jsonb_build_object('id', $4::text))
        RETURNING {_COLUMNS}
        """,
        pid,
        decision_id,
        scope.developer_id,
        option,
        via,
    )
    if row is not None:
        logger.info("autopilot_decision_resolved", project_id=pid, via=via)
        return {"success": True, "project_id": pid, "already_resolved": False, "decision": _row(row)}
    actual = await pool.fetchrow(
        f"SELECT {_COLUMNS} FROM autopilot_decisions WHERE project_id = $1 AND decision_id = $2", pid, decision_id
    )
    if actual is None:
        return {"success": False, "code": "DECISION_NOT_FOUND", "error": f"No hay ninguna decisión {decision_id}."}
    if actual["resolved_at"] is not None:
        return {"success": True, "project_id": pid, "already_resolved": True, "decision": _row(actual)}
    return _invalid(f"{option!r} no es una de las opciones de {decision_id}.")


async def take_resolved_decisions(ctx: Context, project_id: str = "", dev_token: str = "") -> dict[str, Any]:
    """Las decisiones resueltas que ninguna sesión había recogido; quedan como aplicadas (AC-02).

    La llama el arranque de sesión (``session-start.mjs``) para tratarlas como resueltas y no volver
    a preguntarlas. Cada decisión se entrega una sola vez.
    """
    found, error = await _scope_for(ctx, project_id, dev_token)
    if error is not None:
        return error
    pid, _scope = found

    from ..db.pool import get_pool

    pool = await get_pool()
    rows = await pool.fetch(
        f"""
        WITH tomadas AS (
            UPDATE autopilot_decisions SET applied_at = now()
             WHERE project_id = $1 AND resolved_at IS NOT NULL AND applied_at IS NULL
            RETURNING {_COLUMNS}
        )
        SELECT t.*, d.display_name AS resolved_by_name
          FROM tomadas t LEFT JOIN developers d ON d.developer_id = t.resolved_by
         ORDER BY t.resolved_at, t.decision_id
        """,
        pid,
    )
    decisiones = []
    for r in rows:
        data = _row(r)
        etiquetas = {o["id"]: o["label"] for o in data["options"]}
        data["resolution_label"] = etiquetas.get(data["resolution"], data["resolution"])
        decisiones.append(data)
    return {"success": True, "project_id": pid, "total": len(decisiones), "decisions": decisiones}


def register_autopilot_decision_tools(mcp_instance) -> None:
    """Registra las cuatro tools de decisiones aplazadas (UC-9902)."""
    mcp_instance.tool(
        description=(
            "Publica en el board una decisión aplazada por el autopilot: UC, pregunta, opciones "
            "[{id,label}] y la opción por defecto aplicada mientras tanto; mismo id dq-… que la cola "
            "del proyecto. Sin credenciales. Exige ser miembro del proyecto."
        )
    )(publish_decision)
    mcp_instance.tool(
        description="Las decisiones aplazadas del proyecto que esperan a una persona. Exige ser miembro."
    )(list_pending_decisions)
    mcp_instance.tool(
        description=(
            "Resuelve una decisión aplazada con una de sus opciones (via: session, panel o app); quedan "
            "quién y cuándo. Una ya resuelta no cambia. Exige ser miembro."
        )
    )(resolve_decision)
    mcp_instance.tool(
        description=(
            "Las decisiones resueltas que ninguna sesión había recogido, con su opción; quedan como "
            "aplicadas para no volver a preguntarlas. La llama el arranque de sesión."
        )
    )(take_resolved_decisions)
