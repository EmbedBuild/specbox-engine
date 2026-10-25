"""El latido de cada sesión de Claude Code en el board (US-99 · UC-9901).

Dos tools sobre ``session_heartbeats`` (migración 0031):

* ``report_session_heartbeat`` — lo manda el hook ``session-heartbeat.mjs`` al empezar la
  sesión, al cambiar de UC, de fase o de espera, como mucho cada dos minutos y al cerrar. Solo
  campos enumerados o de forma fija y con longitud máxima: nunca texto de la conversación ni de
  las specs, y el latido entero pesa menos de 1 KB (AC-01).
* ``get_live_session`` — la sesión viva de un proyecto, para los miembros y el SuperAdmin
  (AC-04). La app y el panel la leen por la API del panel con la misma regla.

Identidad: ``resolve_caller_scope`` (token explícito, sesión native o el del transporte). Un
token revocado no resuelve y no escribe (AC-04). El proyecto se toma del parámetro o de la
sesión native; uno del que el desarrollador no es miembro se responde como inexistente.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from fastmcp import Context

from ..coordination.access_log import is_operator
from ..coordination.scope import resolve_caller_scope
from ..coordination.identity import UnauthenticatedError

logger = structlog.get_logger(__name__)

#: Las fases del pipeline que puede decir un latido (la misma lista que el CHECK de 0031).
PHASES: frozenset[str] = frozenset(
    {"idle", "discovery", "prd", "plan", "design", "implement", "tests", "review", "release"}
)
WAITING: frozenset[str] = frozenset({"none", "decision", "permission"})
SESSION_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")
UC_ID = re.compile(r"^UC-[0-9]{1,6}[a-z]?$")
PROJECT_ID = re.compile(r"^[A-Za-z0-9._/-]{1,200}$")

#: Tope del latido (AC-01): lo que viaja, sin el token.
MAX_BYTES = 1024


def _invalid(message: str) -> dict[str, Any]:
    return {"success": False, "code": "INVALID_HEARTBEAT", "error": message}


def _not_visible(project_id: str) -> dict[str, Any]:
    # Lo ajeno se responde igual que lo inexistente: ninguna pista (modelo de amenazas §4).
    return {"success": False, "code": "PROJECT_NOT_VISIBLE", "error": f"Project {project_id!r} not found."}


def _unauthenticated() -> dict[str, Any]:
    return {
        "success": False,
        "code": "UNAUTHENTICATED",
        "error": "Sin identidad: conecta con tu token de SpecBox o pasa dev_token.",
    }


async def _session_project(ctx: Context | None) -> str:
    """El proyecto de la sesión native, o '' si no la hay."""
    if ctx is None:
        return ""
    from ..auth_gateway import get_native_session

    try:
        session = await get_native_session(ctx)
    except RuntimeError:
        return ""
    return str(session.get("project_id") or "")


def validate_heartbeat(
    *, project_id: str, session_id: str, phase: str, uc_id: str | None, waiting: str, ended: bool
) -> dict[str, Any] | None:
    """El error del latido, o None si es válido. Pura: la usan la tool y sus pruebas."""
    if not PROJECT_ID.match(project_id or ""):
        return _invalid("project_id no válido.")
    if not SESSION_ID.match(session_id or ""):
        return _invalid("session_id no válido: el id de la sesión de Claude Code, de 8 a 64 caracteres.")
    if phase not in PHASES:
        return _invalid(f"phase no válida; una de: {', '.join(sorted(PHASES))}.")
    if uc_id is not None and not UC_ID.match(uc_id):
        return _invalid("uc_id no válido: «UC-1234».")
    if waiting not in WAITING:
        return _invalid(f"waiting no válido; uno de: {', '.join(sorted(WAITING))}.")
    payload = {
        "project_id": project_id,
        "session_id": session_id,
        "phase": phase,
        "uc_id": uc_id,
        "waiting": waiting,
        "ended": bool(ended),
    }
    if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) >= MAX_BYTES:
        return _invalid("El latido pasa de 1 KB.")
    return None


_UPSERT = """
INSERT INTO session_heartbeats AS h
    (project_id, session_id, developer_id, uc_id, phase, waiting, waiting_since,
     started_at, last_beat_at, ended_at, ended_reason)
VALUES ($1, $2, $3, $4, $5, $6, CASE WHEN $6 = 'none' THEN NULL ELSE now() END,
        now(), now(), CASE WHEN $7 THEN now() END, CASE WHEN $7 THEN 'closed' END)
ON CONFLICT (project_id, session_id) DO UPDATE SET
    uc_id = EXCLUDED.uc_id,
    phase = EXCLUDED.phase,
    waiting = EXCLUDED.waiting,
    waiting_since = CASE
        WHEN EXCLUDED.waiting = 'none' THEN NULL
        WHEN h.waiting = EXCLUDED.waiting THEN h.waiting_since
        ELSE now()
    END,
    last_beat_at = now(),
    ended_at = EXCLUDED.ended_at,
    ended_reason = EXCLUDED.ended_reason
WHERE h.developer_id = EXCLUDED.developer_id
RETURNING project_id, session_id, uc_id, phase, waiting, waiting_since, started_at, last_beat_at,
          ended_at, ended_reason
"""


async def report_session_heartbeat(
    ctx: Context,
    session_id: str,
    phase: str,
    uc_id: str | None = None,
    waiting: str = "none",
    ended: bool = False,
    project_id: str = "",
    dev_token: str = "",
) -> dict[str, Any]:
    """Registra el latido de una sesión de Claude Code (UC-9901).

    ``phase`` ∈ idle · discovery · prd · plan · design · implement · tests · review · release;
    ``waiting`` ∈ none · decision · permission; ``ended=True`` da la sesión por cerrada. El
    proyecto es ``project_id`` o el de la sesión native. Exige que quien llama sea miembro del
    proyecto; una sesión de otro desarrollador no se puede sobrescribir. Nunca recibe texto de la
    conversación ni de las specs.
    """
    pid = (project_id or "").strip() or await _session_project(ctx)
    error = validate_heartbeat(
        project_id=pid, session_id=session_id, phase=phase, uc_id=uc_id, waiting=waiting, ended=ended
    )
    if error is not None:
        return error
    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except UnauthenticatedError:
        return _unauthenticated()
    if pid not in scope.project_ids:
        return _not_visible(pid)

    from ..db.pool import get_pool

    pool = await get_pool()
    row = await pool.fetchrow(_UPSERT, pid, session_id, scope.developer_id, uc_id, phase, waiting, bool(ended))
    if row is None:
        # La sesión existe y es de otro desarrollador: tampoco se dice.
        return _not_visible(pid)
    logger.info("session_heartbeat", project_id=pid, phase=phase, waiting=waiting, ended=bool(ended))
    return {
        "success": True,
        "project_id": row["project_id"],
        "session_id": row["session_id"],
        "state": "ended" if row["ended_at"] is not None else "live",
        "uc_id": row["uc_id"],
        "phase": row["phase"],
        "waiting": row["waiting"],
        "last_beat_at": row["last_beat_at"].isoformat(),
    }


def _isoformat(row) -> dict[str, Any]:
    fila = dict(row)
    for key in ("waiting_since", "started_at", "last_beat_at"):
        if fila.get(key) is not None:
            fila[key] = fila[key].isoformat()
    return fila


async def get_live_session(ctx: Context, project_id: str = "", dev_token: str = "") -> dict[str, Any]:
    """La sesión viva de un proyecto, para sus miembros y el SuperAdmin (UC-9901 AC-04).

    Devuelve ``session: null`` cuando no hay ninguna sin terminar; ``stale: true`` cuando la más
    reciente lleva más de quince minutos sin latido (el board la cerrará en el siguiente barrido).
    ``sessions`` son todas las sesiones vivas del proyecto, de la del último latido a la más antigua
    (UC-10609): las de cada satélite que trabaja a la vez en el mismo board, sin las cerradas ni las
    que llevan quince minutos sin latido.
    """
    pid = (project_id or "").strip() or await _session_project(ctx)
    if not PROJECT_ID.match(pid or ""):
        return _invalid("project_id no válido.")
    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except UnauthenticatedError:
        return _unauthenticated()

    from ..db.pool import get_pool

    pool = await get_pool()
    if pid not in scope.project_ids and not await is_operator(scope.developer_id, pool=pool):
        return _not_visible(pid)
    row = await pool.fetchrow(
        "SELECT project_id, session_id, developer_id, uc_id, phase, waiting, waiting_since, "
        "started_at, last_beat_at, stale FROM v_live_sessions WHERE project_id = $1",
        pid,
    )
    vivas = await pool.fetch(
        "SELECT session_id, developer_id, uc_id, phase, waiting, waiting_since, started_at, last_beat_at "
        "FROM v_project_live_sessions WHERE project_id = $1 ORDER BY last_beat_at DESC, session_id",
        pid,
    )
    return {
        "success": True,
        "project_id": pid,
        "session": None if row is None else _isoformat(row),
        "sessions": [_isoformat(v) for v in vivas],
    }


def register_session_heartbeat_tools(mcp_instance) -> None:
    """Registra las dos tools del latido (UC-9901)."""
    mcp_instance.tool(
        description=(
            "Registra el latido de una sesión de Claude Code en el board: proyecto, UC, fase "
            "(idle/discovery/prd/plan/design/implement/tests/review/release), si espera "
            "(none/decision/permission) y si ha terminado. Menos de 1 KB, nunca texto de la "
            "conversación. Exige ser miembro del proyecto."
        )
    )(report_session_heartbeat)
    mcp_instance.tool(
        description=(
            "La sesión viva de un proyecto (fase, UC, si espera y desde cuándo, stale a los 15 "
            "minutos sin latido) o null, y en sessions todas las sesiones vivas del proyecto, de la "
            "del último latido a la más antigua. Para miembros del proyecto y el SuperAdmin."
        )
    )(get_live_session)
