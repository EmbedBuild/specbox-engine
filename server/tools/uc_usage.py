"""El coste real de cada UC en tokens y su tiempo de revisión (US-124 · UC-12403).

* ``report_uc_usage`` — la manda el hook ``uc-usage.mjs`` al terminar cada turno (``Stop``), cada
  subagente (``SubagentStop``) y antes de ``complete_uc``: los tokens nuevos que Claude Code informa
  en la transcripción (``message.usage``, cada respuesta una vez) para la UC activa. Solo cifras e
  identificadores cortos; nunca texto de la conversación (AC-04). Se suma en ``uc_usage``
  (migración 0038), una fila por UC, sesión y subagente.
* ``usage_kpis`` y ``review_time_kpis`` — lo que añade ``get_project_kpis``: tokens por UC y por
  criterio (p50 y p90 de las UC con dato real; las demás, «estimado» por la mediana por criterio)
  y el tiempo de revisión (p50 y p90), desde que la UC pasa a revisión hasta que una persona la
  acepta o la devuelve, o vuelve a trabajo.

Solo native: FreeForm no tiene ``get_project_kpis``. Identidad: ``resolve_caller_scope`` (token
explícito, sesión native o el del transporte), como el latido; un proyecto del que el desarrollador
no es miembro se responde como inexistente.
"""

from __future__ import annotations

import math
import re
from typing import Any

import structlog
from fastmcp import Context

from ..coordination.identity import UnauthenticatedError
from ..coordination.scope import resolve_caller_scope
from .session_heartbeat import (
    PROJECT_ID,
    SESSION_ID,
    UC_ID,
    _not_visible,
    _session_project,
    _unauthenticated,
)

logger = structlog.get_logger(__name__)

TOKEN_FIELDS: tuple[str, ...] = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
#: Tope por envío: más de diez mil millones de tokens en un turno es un dato roto, no un turno.
MAX_TOKENS = 10_000_000_000
MAX_MESSAGES = 1_000_000
AGENT_ID = re.compile(r"^[A-Za-z0-9_.:-]{0,128}$")
#: Las UC más recientes que enseña ``by_uc`` (las cifras agregadas cuentan todas).
RECENT_UCS = 20


def _invalid(message: str) -> dict[str, Any]:
    return {"success": False, "code": "INVALID_USAGE", "error": message}


def _count(value: Any, top: int) -> int | None:
    """Un entero entre 0 y ``top`` (un booleano no cuenta), o None."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > top:
        return None
    return value


def validate_usage(
    *, project_id: str, uc_id: str, session_id: str, agent_id: str, counts: dict[str, Any], messages: Any
) -> dict[str, Any] | None:
    """El error del envío, o None si es válido. Pura: la usan la tool y sus pruebas."""
    if not PROJECT_ID.match(project_id or ""):
        return _invalid("project_id no válido.")
    if not UC_ID.match(uc_id or ""):
        return _invalid("uc_id no válido: «UC-1234».")
    if not SESSION_ID.match(session_id or ""):
        return _invalid("session_id no válido: el id de la sesión de Claude Code, de 8 a 64 caracteres.")
    if not AGENT_ID.match(agent_id or ""):
        return _invalid("agent_id no válido: el id del subagente de Claude Code, o vacío para la sesión.")
    for field in TOKEN_FIELDS:
        if _count(counts.get(field, 0), MAX_TOKENS) is None:
            return _invalid(f"{field} tiene que ser un entero entre 0 y {MAX_TOKENS}.")
    if _count(messages, MAX_MESSAGES) is None:
        return _invalid(f"messages tiene que ser un entero entre 0 y {MAX_MESSAGES}.")
    return None


_UPSERT = """
INSERT INTO uc_usage AS u
    (project_id, uc_id, session_id, agent_id, developer_id,
     input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, messages)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
ON CONFLICT (project_id, uc_id, session_id, agent_id) DO UPDATE SET
    input_tokens = u.input_tokens + EXCLUDED.input_tokens,
    output_tokens = u.output_tokens + EXCLUDED.output_tokens,
    cache_creation_input_tokens = u.cache_creation_input_tokens + EXCLUDED.cache_creation_input_tokens,
    cache_read_input_tokens = u.cache_read_input_tokens + EXCLUDED.cache_read_input_tokens,
    messages = u.messages + EXCLUDED.messages,
    last_reported_at = now()
RETURNING input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, messages
"""


async def report_uc_usage(
    ctx: Context,
    uc_id: str,
    session_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    messages: int = 0,
    agent_id: str = "",
    project_id: str = "",
    dev_token: str = "",
) -> dict[str, Any]:
    """Suma a la UC los tokens nuevos de una sesión o un subagente (UC-12403 AC-01, AC-04).

    Lo manda el hook ``uc-usage``: lo que Claude Code informa en la transcripción desde el último
    envío, cada respuesta una vez. ``agent_id`` vacío es la sesión principal. Solo enteros e
    identificadores; exige ser miembro del proyecto. Devuelve lo que lleva acumulado esa fila.
    """
    pid = (project_id or "").strip() or await _session_project(ctx)
    counts = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
    }
    agent = (agent_id or "").strip()
    error = validate_usage(
        project_id=pid, uc_id=uc_id, session_id=session_id, agent_id=agent, counts=counts, messages=messages
    )
    if error is not None:
        return error
    if not any(counts.values()) and not messages:
        return {"success": True, "recorded": False, "uc_id": uc_id, "note": "Nada que sumar."}
    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except UnauthenticatedError:
        return _unauthenticated()
    if pid not in scope.project_ids:
        return _not_visible(pid)

    import asyncpg

    from ..db.pool import get_pool

    pool = await get_pool()
    try:
        row = await pool.fetchrow(
            _UPSERT, pid, uc_id, session_id, agent, scope.developer_id,
            *(counts[f] for f in TOKEN_FIELDS), messages,
        )
    except asyncpg.ForeignKeyViolationError:
        return {"success": False, "code": "UC_NOT_FOUND", "error": f"Use Case {uc_id} not found."}
    logger.info("uc_usage", project_id=pid, uc_id=uc_id, agent=bool(agent))
    return {
        "success": True,
        "recorded": True,
        "uc_id": uc_id,
        "session_id": session_id,
        "agent_id": agent,
        "totals": dict(row),
    }


# ── Métricas (get_project_kpis) ──────────────────────────────────────


def percentile(values: list[float], q: float) -> float | None:
    """El percentil ``q`` (0..1) con interpolación lineal, como ``percentile_cont``; None si no hay datos."""
    data = sorted(values)
    if not data:
        return None
    pos = (len(data) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    return data[low] + (data[high] - data[low]) * (pos - low)


_USAGE_ROWS = """
WITH usage AS (
    SELECT uc_id,
           sum(input_tokens + cache_creation_input_tokens + cache_read_input_tokens) AS input_total,
           sum(output_tokens) AS output_total
      FROM uc_usage WHERE project_id = $1 GROUP BY uc_id
), crit AS (
    SELECT uc_id, count(*) AS criteria FROM acceptance_criteria WHERE project_id = $1 GROUP BY uc_id
)
SELECT u.id AS uc_id, u.state, u.completed_at, COALESCE(c.criteria, 0) AS criteria,
       us.input_total, us.output_total
  FROM use_cases u
  LEFT JOIN crit c ON c.uc_id = u.id
  LEFT JOIN usage us ON us.uc_id = u.id
 WHERE u.project_id = $1 AND (u.state IN ('review', 'done') OR us.uc_id IS NOT NULL)
 ORDER BY u.completed_at DESC NULLS FIRST, u.id DESC
"""


def summarize_usage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Tokens por UC y por criterio a partir de las filas de ``_USAGE_ROWS``. Pura y testeable.

    Las cifras agregadas (p50 y p90) son solo de las UC con dato real. Una UC en revisión o hecha
    sin dato real lleva ``estimated: true`` y, si hay mediana por criterio, la estimación
    ``mediana por criterio × criterios``; ``estimated`` del conjunto dice si alguna lo es (AC-03).
    """
    real = [r for r in rows if r.get("input_total") is not None]
    per_uc = [float(r["input_total"] + r["output_total"]) for r in real]
    per_criterion = [float(r["input_total"] + r["output_total"]) / r["criteria"] for r in real if r["criteria"]]
    criterion_p50 = percentile(per_criterion, 0.5)
    by_uc = []
    for r in rows[:RECENT_UCS]:
        if r.get("input_total") is not None:
            tokens = int(r["input_total"] + r["output_total"])
            by_uc.append({
                "uc_id": r["uc_id"], "state": r["state"], "criteria": r["criteria"], "estimated": False,
                "tokens": tokens, "input_tokens": int(r["input_total"]), "output_tokens": int(r["output_total"]),
                "tokens_per_criterion": round(tokens / r["criteria"]) if r["criteria"] else None,
            })
        else:
            guess = round(criterion_p50 * r["criteria"]) if criterion_p50 is not None and r["criteria"] else None
            by_uc.append({
                "uc_id": r["uc_id"], "state": r["state"], "criteria": r["criteria"], "estimated": True,
                "tokens": guess, "input_tokens": None, "output_tokens": None,
                "tokens_per_criterion": round(criterion_p50) if guess is not None else None,
            })
    reviewed = [r for r in rows if r["state"] in ("review", "done")]
    without = sum(1 for r in reviewed if r.get("input_total") is None)

    def _round(value: float | None) -> int | None:
        return round(value) if value is not None else None

    return {
        "ucs_with_usage": len(real),
        "ucs_without_usage": without,
        "estimated": without > 0,
        "per_uc_p50": _round(percentile(per_uc, 0.5)),
        "per_uc_p90": _round(percentile(per_uc, 0.9)),
        "per_criterion_p50": _round(criterion_p50),
        "per_criterion_p90": _round(percentile(per_criterion, 0.9)),
        "by_uc": by_uc,
        "note": (
            "Tokens de entrada (con caché) y de salida que informa Claude Code. Las UC sin dato real "
            "llevan estimated: true y, si se puede, la mediana por criterio × sus criterios."
        ),
    }


async def usage_kpis(pool: Any, project_id: str) -> dict[str, Any]:
    rows = [dict(r) for r in await pool.fetch(_USAGE_ROWS, project_id)]
    return summarize_usage(rows)


_REVIEW_TIMES = """
WITH entries AS (
    SELECT t.uc_id, t.occurred_at AS entered,
           lead(t.occurred_at) OVER (PARTITION BY t.uc_id ORDER BY t.occurred_at) AS next_entry
      FROM uc_state_transitions t
     WHERE t.project_id = $1 AND t.to_state = 'review'
), episodes AS (
    SELECT e.entered, LEAST(
        (SELECT min(v.at) FROM uc_review_verdicts v
          WHERE v.project_id = $1 AND v.uc_id = e.uc_id AND v.by_kind = 'person'
            AND v.at >= e.entered AND (e.next_entry IS NULL OR v.at < e.next_entry)),
        (SELECT min(a.accepted_at) FROM uc_acceptances a
          WHERE a.project_id = $1 AND a.uc_id = e.uc_id
            AND a.accepted_at >= e.entered AND (e.next_entry IS NULL OR a.accepted_at < e.next_entry)),
        (SELECT min(x.occurred_at) FROM uc_state_transitions x
          WHERE x.project_id = $1 AND x.uc_id = e.uc_id AND x.from_state = 'review'
            AND x.to_state IN ('backlog', 'user_stories', 'in_progress')
            AND x.occurred_at > e.entered AND (e.next_entry IS NULL OR x.occurred_at < e.next_entry))
    ) AS ended
      FROM entries e
)
SELECT extract(epoch FROM ended - entered)::float8 AS seconds
  FROM episodes
 WHERE ended IS NOT NULL
"""


async def review_time_kpis(pool: Any, project_id: str) -> dict[str, Any]:
    """Tiempo de revisión (UC-12403 AC-02): de la entrada en revisión a la aceptación o la devolución
    de una persona, o a la vuelta a trabajo. Los episodios aún abiertos no cuentan."""
    seconds = [float(r["seconds"]) for r in await pool.fetch(_REVIEW_TIMES, project_id)]
    return {
        "review_episodes": len(seconds),
        "review_time_p50": percentile(seconds, 0.5),
        "review_time_p90": percentile(seconds, 0.9),
        "review_time_unit": "seconds",
    }


def register_uc_usage_tools(mcp_instance) -> None:
    """Registra la tool del coste en tokens de cada UC (UC-12403)."""
    mcp_instance.tool(
        description=(
            "Suma a una UC los tokens nuevos de una sesión o un subagente de Claude Code (entrada, "
            "salida, caché creada y leída, y respuestas), del uso que informa la transcripción. Solo "
            "cifras e identificadores, nunca texto. Lo manda el hook uc-usage. Exige ser miembro del "
            "proyecto; solo native."
        )
    )(report_uc_usage)
