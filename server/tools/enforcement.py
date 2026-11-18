"""El modo de cada medida de EP-20 en un tablero (US-122 · UC-12212).

Tres tools sobre la política de ``server/coordination/enforcement.py``:

* ``get_enforcement_policy`` — el modo de cada medida, su origen y desde cuándo bloquea;
* ``set_enforcement_mode``   — cambia el modo de una medida (en native, solo ``project_admin``);
* ``skip_enforcement``       — salta un bloqueo con motivo; queda quién, cuándo y por qué, y la
  siguiente comprobación de esa medida en esa UC pasa una vez. La plantilla de permisos la pone en
  «ask»: una persona lo confirma en Claude Code.

Y antes de endurecer (UC-12213):

* ``get_enforcement_impact``   — cuántas UC abiertas detendría cada medida en «block» y por qué, cuántas
  son «anteriores a la regla» y los bloqueos de 14 días con su porcentaje de saltos; no cambia nada;
* ``record_enforcement_event`` — una medida detuvo una UC o la dejó pasar (las de los hooks);
* ``enforcement_readiness``    — solo operador: qué medidas podrían nacer en «block» en los proyectos
  nuevos según los tableros de EmbedBuild.

``set_enforcement_mode`` pasa a «block» en dos pasos: informe y código ``confirm``, y luego la
confirmación, que deja las UC abiertas como «anteriores a la regla».

Dónde se lee y se escribe:

* native: ``projects.meta.enforcement``. Identidad y alcance como las decisiones (UC-9902):
  ``resolve_caller_scope``; el proyecto es ``board_id`` o el de la sesión; lo ajeno responde como
  inexistente. Cada cambio deja una fila en ``audit_log``. Los hooks la llaman sin abrir sesión del
  tablero, con la identidad del transporte.
* FreeForm: ``doc/tracking/policy.json``. Con el MCP remoto llega en ``policy_content`` (lo pone el
  hook freeform-fragment) y vuelve mutado en ``policy_content``; con el MCP local se lee del disco.
* Trello y Plane: no se guarda nada; las medidas quedan en «warn» como máximo y la respuesta lo dice.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from fastmcp import Context

from ..coordination import enforcement as policy_mod
from ..coordination.enforcement import PolicyError

logger = structlog.get_logger(__name__)

OP_ENFORCEMENT_MODE = "enforcement_mode"
OP_ENFORCEMENT_SKIP = "enforcement_skip"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _invalid(code: str, message: str) -> dict[str, Any]:
    return {"success": False, "code": code, "error": message}


# ── Dónde vive la política de este tablero ──────────────────────────


class _Target:
    """El tablero sobre el que actúa la llamada y cómo leer y guardar su política."""

    def __init__(self, kind: str, *, backend_type: str, project_id: str = "", path: Path | None = None,
                 raw: Any = None, actor: str = "", developer_id: str = "") -> None:
        self.kind = kind  # native | freeform_disk | freeform_content | capped
        self.backend_type = backend_type
        self.project_id = project_id
        self.path = path
        self.raw = raw
        self.actor = actor
        self.developer_id = developer_id


def _parse_policy_content(policy_content: str) -> Any:
    text = (policy_content or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise PolicyError("INVALID_POLICY_CONTENT", f"policy_content no es JSON válido: {e.msg}.") from e
    if not isinstance(parsed, dict):
        raise PolicyError("INVALID_POLICY_CONTENT", "policy_content tiene que ser el objeto de doc/tracking/policy.json.")
    return parsed


async def _optional_identity(ctx: Context | None, dev_token: str) -> str:
    """El developer de la llamada si lo hay (FreeForm no lo exige); '' si no."""
    from ..coordination.identity import UnauthenticatedError
    from ..coordination.scope import resolve_caller_scope

    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except (UnauthenticatedError, RuntimeError):
        return ""
    except Exception:  # noqa: BLE001 — sin base de identidad (FreeForm local) no hay developer
        return ""
    return scope.developer_id


async def _resolve_target(
    ctx: Context | None, board_id: str, policy_content: str | None, dev_token: str, actor: str
) -> tuple[_Target | None, dict | None]:
    from ..auth_gateway import BACKEND_STATE_KEY

    if policy_content is not None:
        raw = _parse_policy_content(policy_content)
        who = (await _optional_identity(ctx, dev_token)) or (actor or "").strip()[:80] or "desconocido"
        return _Target("freeform_content", backend_type="freeform", raw=raw, actor=who), None

    config = (await ctx.get_state(BACKEND_STATE_KEY) or {}) if ctx is not None else {}
    backend_type = config.get("backend_type") or ""
    if backend_type in policy_mod.CAPPED_BACKENDS:
        return _Target("capped", backend_type=backend_type, actor=actor or ""), None
    if backend_type == "freeform":
        from ..transport import is_remote_transport

        root = config.get("root_path") or ""
        if config.get("content_only") or is_remote_transport() or not root or not Path(root).is_absolute():
            return None, _invalid(
                "POLICY_CONTENT_REQUIRED",
                "FreeForm con el MCP remoto: la política llega en policy_content (el contenido de "
                "doc/tracking/policy.json; el hook freeform-fragment lo pone solo). Sin ese fichero, "
                "pasa policy_content=\"\" y el tablero se trata como uno que ya existía.",
            )
        path = Path(root) / policy_mod.POLICY_FILE
        raw = json.loads(path.read_text()) if path.exists() else None
        who = (await _optional_identity(ctx, dev_token)) or (actor or "").strip()[:80] or "local"
        return _Target("freeform_disk", backend_type="freeform", path=path, raw=raw, actor=who), None

    # native, con sesión del tablero o con la identidad del transporte (los hooks).
    from ..coordination.identity import UnauthenticatedError
    from ..coordination.scope import resolve_caller_scope
    from .session_heartbeat import PROJECT_ID, _not_visible, _session_project, _unauthenticated

    pid = (board_id or "").strip() or await _session_project(ctx)
    if not PROJECT_ID.match(pid or ""):
        return None, _invalid("INVALID_BOARD_ID", "board_id tiene que ser el proyecto native, como «Org/repo».")
    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except UnauthenticatedError:
        return None, _unauthenticated()
    if pid not in scope.project_ids:
        return None, _not_visible(pid)
    from ..db.pool import get_pool

    pool = await get_pool()
    raw = await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", pid)
    raw = json.loads(raw) if isinstance(raw, str) else raw
    return _Target("native", backend_type="native", project_id=pid, raw=raw,
                   actor=scope.developer_id, developer_id=scope.developer_id), None


def _out(target: _Target, payload: dict[str, Any], stored: dict | None = None) -> dict[str, Any]:
    """Respuesta común; en FreeForm por contenido devuelve el fichero mutado."""
    result = {"success": True, "backend_type": target.backend_type, **payload}
    if target.project_id:
        result["board_id"] = target.project_id
    if stored is not None and target.kind == "freeform_content":
        result["policy_content"] = json.dumps(stored, ensure_ascii=False, indent=2) + "\n"
    return result


# ── Escrituras native (con fila de auditoría) ───────────────────────

_ADMIN_ONLY = (
    "Cambiar el modo de una medida es cosa de quien administra el proyecto (project_admin). "
    "Pídeselo, o usa skip_enforcement con motivo para una UC concreta."
)


async def _require_admin(target: _Target) -> None:
    from ..db.pool import get_pool

    pool = await get_pool()
    role = await pool.fetchval(
        "SELECT role FROM project_members WHERE project_id = $1 AND developer_id = $2",
        target.project_id,
        target.developer_id,
    )
    if role != "project_admin":
        raise PolicyError("FORBIDDEN", _ADMIN_ONLY)


async def _native_apply(target: _Target, mutate, *, operation: str, admin_only: bool, metadata) -> Any:
    """Aplica ``mutate(raw) -> (stored, extra)`` a la política native bajo bloqueo de fila."""
    from ..coordination.audit import record_destructive
    from ..db.pool import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if admin_only:
                role = await conn.fetchval(
                    "SELECT role FROM project_members WHERE project_id = $1 AND developer_id = $2",
                    target.project_id,
                    target.developer_id,
                )
                if role != "project_admin":
                    raise PolicyError(
                        "FORBIDDEN",
                        "Cambiar el modo de una medida es cosa de quien administra el proyecto "
                        "(project_admin). Pídeselo, o usa skip_enforcement con motivo para una UC concreta.",
                    )
            raw = await conn.fetchval(
                "SELECT meta->'enforcement' FROM projects WHERE project_id = $1 FOR UPDATE", target.project_id
            )
            raw = json.loads(raw) if isinstance(raw, str) else raw
            stored, extra = mutate(raw)
            await conn.execute(
                "UPDATE projects SET meta = meta || jsonb_build_object('enforcement', $2::jsonb), "
                "updated_at = now() WHERE project_id = $1",
                target.project_id,
                json.dumps(stored),
            )
            await record_destructive(
                conn,
                developer_id=target.developer_id,
                project_id=target.project_id,
                operation=operation,
                target_id=metadata(extra)["target"],
                metadata={k: v for k, v in metadata(extra).items() if k != "target"},
            )
    return stored, extra


def _save_disk(target: _Target, stored: dict) -> None:
    target.path.parent.mkdir(parents=True, exist_ok=True)
    target.path.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n")


# ── UC abiertas y bloqueos de un tablero (UC-12213) ─────────────────

EVENTS_FILE = "enforcement_events.jsonl"
_EVENT_OPS = {"enforcement_block": "blocked", "enforcement_pass": "passed", OP_ENFORCEMENT_SKIP: "skipped"}
_EVENT_LOOKBACK_DAYS = 60


async def _native_open_ucs(project_id: str) -> list[dict[str, Any]]:
    from ..db.pool import get_pool

    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT u.id AS uc_id, u.name, u.description, u.state,
               COALESCE(
                   json_agg(json_build_object('ac_id', a.ac_id, 'text', a.text, 'done', a.done,
                                              'evidence', COALESCE(a.meta->'evidence', '[]'::jsonb))
                            ORDER BY a.ac_id) FILTER (WHERE a.ac_id IS NOT NULL),
                   '[]'::json) AS acs
          FROM use_cases u
          LEFT JOIN acceptance_criteria a ON a.project_id = u.project_id AND a.uc_id = u.id
         WHERE u.project_id = $1 AND u.state NOT IN ('done', 'archived')
         GROUP BY u.id, u.name, u.description, u.state
         ORDER BY u.id
        """,
        project_id,
    )
    out = []
    for r in rows:
        acs = json.loads(r["acs"]) if isinstance(r["acs"], str) else r["acs"]
        out.append({"uc_id": r["uc_id"], "name": r["name"], "description": r["description"], "state": r["state"],
                    "acs": acs, "evidence_known": True})
    return out


async def _freeform_open_ucs(items_content: str) -> list[dict[str, Any]]:
    from ..backends.freeform_backend import FreeformBackend
    from ..spec_backend import parse_item_id

    backend = FreeformBackend(items_content=items_content)
    out = []
    for item in await backend.list_items("freeform"):
        if "UC" not in item.labels or item.state in policy_mod.OPEN_EXCLUDED_STATES:
            continue
        uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
        if not uc_id:
            continue
        acs = await backend.get_acceptance_criteria("freeform", item.id)
        out.append({
            "uc_id": uc_id,
            "name": item.name,
            "description": item.description,
            "state": item.state,
            # FreeForm guarda la evidencia en los comentarios, que no viajan con items.json.
            "evidence_known": False,
            "acs": [{"ac_id": ac.id, "text": ac.text, "done": ac.done, "evidence": []} for ac in acs],
        })
    return out


def _parse_events(content: str) -> list[dict[str, Any]]:
    events = []
    for line in (content or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("outcome") in ("blocked", "passed", "skipped"):
            events.append(event)
    return events


async def _native_events(project_ids: list[str] | None, *, like: str | None = None) -> list[dict[str, Any]]:
    from ..db.pool import get_pool

    pool = await get_pool()
    where = "project_id = ANY($1::text[])" if project_ids is not None else "project_id LIKE $1"
    rows = await pool.fetch(
        f"""
        SELECT project_id, operation, metadata, occurred_at FROM audit_log
         WHERE {where} AND operation = ANY($2::text[])
           AND occurred_at >= now() - make_interval(days => {_EVENT_LOOKBACK_DAYS})
         ORDER BY occurred_at
        """,
        project_ids if project_ids is not None else like,
        list(_EVENT_OPS),
    )
    events = []
    for r in rows:
        meta = r["metadata"]
        meta = json.loads(meta) if isinstance(meta, str) else (meta or {})
        events.append({
            "project_id": r["project_id"],
            "measure": meta.get("measure"),
            "uc_id": meta.get("uc_id"),
            "outcome": _EVENT_OPS[r["operation"]],
            "at": r["occurred_at"].isoformat(),
        })
    return events


async def _board_data(target: _Target, board_content: str | None, events_content: str | None):
    """(UC abiertas, eventos) del tablero, o PolicyError si con FreeForm remoto falta el contenido."""
    if target.kind == "native":
        return await _native_open_ucs(target.project_id), await _native_events([target.project_id])
    if target.kind == "freeform_disk":
        items_path = target.path.parent / "items.json"
        events_path = target.path.parent / EVENTS_FILE
        items = items_path.read_text() if items_path.exists() else "[]"
        events = events_path.read_text() if events_path.exists() else ""
        return await _freeform_open_ucs(items), _parse_events(events)
    if target.kind == "freeform_content":
        if board_content is None:
            raise PolicyError(
                "BOARD_CONTENT_REQUIRED",
                "Para medir el impacto hace falta el tablero: pasa doc/tracking/items.json en board_content "
                "(el hook freeform-fragment lo pone solo).",
            )
        return await _freeform_open_ucs(board_content), _parse_events(events_content or "")
    return [], []


def _event_line(measure: str, uc_id: str, outcome: str, at: str, by: str, reason: str = "") -> str:
    event = {"measure": measure, "uc_id": uc_id, "outcome": outcome, "at": at, "by": by}
    if reason:
        event["reason"] = reason
    return json.dumps(event, ensure_ascii=False)


def _append_disk_event(target: _Target, line: str) -> None:
    path = target.path.parent / EVENTS_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ── Tools ───────────────────────────────────────────────────────────


async def get_enforcement_policy(
    ctx: Context,
    board_id: str = "",
    policy_content: str | None = None,
    dev_token: str = "",
) -> dict[str, Any]:
    """El modo («off», «warn» o «block») de cada medida de EP-20 en este tablero.

    Cada medida dice su modo, si sale del valor por defecto o lo puso una persona (``source``,
    ``set_by``, ``set_at``), desde cuándo bloquea (``block_since``) y si ya comprueba algo
    (``active``). ``origin`` = «new» (tablero creado con estas medidas) o «existing» (ya existía:
    todo empieza en «warn»). Trello y Plane: «warn» como máximo.
    """
    try:
        target, error = await _resolve_target(ctx, board_id, policy_content, dev_token, "")
    except PolicyError as e:
        return policy_mod.policy_error(e)
    if error is not None:
        return error
    policy = policy_mod.effective_policy(target.raw, backend_type=target.backend_type)
    return _out(target, {"policy": policy})


async def set_enforcement_mode(
    ctx: Context,
    measure: str,
    mode: str,
    board_id: str = "",
    confirm: str = "",
    policy_content: str | None = None,
    board_content: str | None = None,
    events_content: str | None = None,
    dev_token: str = "",
    actor: str = "",
    threshold: float | None = None,
) -> dict[str, Any]:
    """Cambia el modo de una medida en este tablero: «off», «warn» o «block».

    Ninguna medida pasa a «block» sola: lo cambia una persona (en native, quien tiene
    ``project_admin``; la plantilla de permisos pide confirmación). Queda quién y cuándo.

    Pasar a «block» va en dos pasos (UC-12213): la primera llamada no cambia nada y devuelve el
    informe de impacto de la medida y un código ``confirm``; la segunda, con ese código, la aplica.
    Las UC abiertas en ese momento quedan «anteriores a la regla»: la medida no las detiene mientras
    su texto o sus criterios no cambien.

    ``threshold`` (solo ``spec_quality``, UC-12301): la parte de los criterios de una UC que tiene que
    pasar el gate para que start_uc la arranque; 1 por defecto (todos). Para cambiarlo sin cambiar
    el modo, pasa el modo que ya tiene.
    """
    try:
        target, error = await _resolve_target(ctx, board_id, policy_content, dev_token, actor)
        if error is not None:
            return error
        at = _now()
        policy_mod.with_mode(
            target.raw, measure, mode, by=target.actor, at=at, backend_type=target.backend_type, threshold=threshold
        )
        if target.kind == "native":
            await _require_admin(target)
        current =policy_mod.mode_of(policy_mod.effective_policy(target.raw, backend_type=target.backend_type), measure)
        open_ucs: dict[str, str] | None = None
        if mode == "block" and current != "block":
            ucs, events = await _board_data(target, board_content, events_content)
            report = policy_mod.impact_report(
                target.raw, ucs, backend_type=target.backend_type, events=events,
                now=datetime.now(timezone.utc), measures=[measure], threshold=threshold,
            )
            impact = report["measures"][measure]
            expected = policy_mod.confirm_token(target.project_id or target.backend_type, measure, mode, current, impact)
            if confirm != expected:
                return {
                    "success": False,
                    "code": "CONFIRMATION_REQUIRED",
                    "measure": measure,
                    "confirm": expected,
                    "impact": impact,
                    "open_ucs": report["open_ucs"],
                    "error": (
                        f"Pasar {measure} de «{current}» a «block» detendría el trabajo que no la cumpla. "
                        f"Hoy la incumplen {impact.get('would_block', 'no se sabe cuántas')} UC abiertas; todas "
                        "quedarían «anteriores a la regla» mientras no cambien. Revisa el informe y, si sigues, "
                        f"repite la llamada con confirm=\"{expected}\"."
                    ),
                }
            open_ucs = policy_mod.open_uc_fingerprints(ucs)

        def mutate(raw):
            return policy_mod.with_mode(
                raw, measure, mode, by=target.actor, at=at, backend_type=target.backend_type, open_ucs=open_ucs,
                threshold=threshold,
            )

        if target.kind == "native":
            stored, previous = await _native_apply(
                target, mutate, operation=OP_ENFORCEMENT_MODE, admin_only=True,
                metadata=lambda prev: {"target": measure, "measure": measure, "from": prev, "to": mode},
            )
        else:
            stored, previous = mutate(target.raw)
            if target.kind == "freeform_disk":
                _save_disk(target, stored)
    except PolicyError as e:
        return policy_mod.policy_error(e, measure=measure)
    logger.info("enforcement_mode_set", backend=target.backend_type, measure=measure, mode=mode)
    policy = policy_mod.effective_policy(stored, backend_type=target.backend_type)
    return _out(
        target,
        {"measure": measure, "previous": previous, "mode": mode, "policy": policy},
        stored,
    )


async def skip_enforcement(
    ctx: Context,
    measure: str,
    uc_id: str,
    reason: str,
    board_id: str = "",
    policy_content: str | None = None,
    dev_token: str = "",
    actor: str = "",
) -> dict[str, Any]:
    """Salta una vez el bloqueo de una medida en una UC, con un motivo que queda en el tablero.

    Exige un motivo (al menos 10 caracteres, sin credenciales). Quedan quién, cuándo y por qué, y la
    siguiente comprobación de esa medida en esa UC pasa una vez y lo dice. Solo se salta lo que
    bloquea: con la medida en «warn» u «off» responde NOTHING_TO_SKIP.
    """
    try:
        target, error = await _resolve_target(ctx, board_id, policy_content, dev_token, actor)
        if error is not None:
            return error
        if target.kind == "capped":
            raise PolicyError(
                "NOTHING_TO_SKIP",
                f"Con {target.backend_type.capitalize()} las medidas solo avisan: no hay bloqueo que saltar.",
            )
        at = _now()

        def mutate(raw):
            return policy_mod.with_skip(
                raw, measure, uc_id, reason, by=target.actor, at=at, backend_type=target.backend_type
            )

        if target.kind == "native":
            stored, skip = await _native_apply(
                target, mutate, operation=OP_ENFORCEMENT_SKIP, admin_only=False,
                metadata=lambda s: {"target": uc_id, "measure": measure, "uc_id": uc_id, "reason": s["reason"]},
            )
        else:
            stored, skip = mutate(target.raw)
            line = _event_line(measure, uc_id, "skipped", at, target.actor, skip["reason"])
            if target.kind == "freeform_disk":
                _save_disk(target, stored)
                _append_disk_event(target, line)
    except PolicyError as e:
        return policy_mod.policy_error(e, measure=measure)
    logger.info("enforcement_skip_recorded", backend=target.backend_type, measure=measure)
    out = _out(target, {"skip": skip}, stored)
    if target.kind == "freeform_content":
        out["event_line"] = line  # el hook lo añade a doc/tracking/enforcement_events.jsonl
    return out


async def get_enforcement_impact(
    ctx: Context,
    board_id: str = "",
    policy_content: str | None = None,
    board_content: str | None = None,
    events_content: str | None = None,
    dev_token: str = "",
) -> dict[str, Any]:
    """Cuántas UC abiertas detendría cada medida en «block» y por qué, sin cambiar nada (UC-12213).

    Por medida: modo, si se puede medir desde el tablero, las UC que detendría con su motivo, cuántas
    son «anteriores a la regla» (a salvo mientras su texto y sus criterios no cambien) y los bloqueos
    de los últimos 14 días: corregidos, saltados con motivo y el porcentaje de saltos.
    """
    try:
        target, error = await _resolve_target(ctx, board_id, policy_content, dev_token, "")
        if error is not None:
            return error
        if target.kind == "capped":
            return _out(target, {
                "report": None,
                "notice": f"Con {target.backend_type.capitalize()} ninguna medida pasa de «warn»: no hay impacto que medir.",
            })
        ucs, events = await _board_data(target, board_content, events_content)
    except PolicyError as e:
        return policy_mod.policy_error(e)
    report = policy_mod.impact_report(
        target.raw, ucs, backend_type=target.backend_type, events=events, now=datetime.now(timezone.utc)
    )
    return _out(target, {"report": report})


async def record_enforcement_event(
    ctx: Context,
    measure: str,
    uc_id: str,
    outcome: str,
    board_id: str = "",
    policy_content: str | None = None,
    dev_token: str = "",
    actor: str = "",
) -> dict[str, Any]:
    """Registra que una medida detuvo una UC (``blocked``) o que la dejó pasar (``passed``).

    La llaman las medidas que aplican los hooks (contexto, PR, CI, diff). Con un ``passed`` en las
    24 h siguientes a un ``blocked`` de la misma medida y UC, el bloqueo cuenta como corregido; los
    saltos los registra ``skip_enforcement`` con su motivo. Native: ``audit_log``. FreeForm:
    ``doc/tracking/enforcement_events.jsonl`` (con el MCP remoto, el hook añade ``event_line``).
    """
    if outcome not in ("blocked", "passed"):
        return {"success": False, "code": "INVALID_OUTCOME", "measure": measure,
                "error": "outcome tiene que ser «blocked» o «passed»; los saltos los registra skip_enforcement."}
    try:
        if measure not in policy_mod.MEASURES:
            raise PolicyError("UNKNOWN_MEASURE", f"No hay ninguna medida {measure!r}.")
        if not policy_mod.UC_ID.match(uc_id or ""):
            raise PolicyError("INVALID_UC_ID", "uc_id tiene que ser el id de la UC, como «UC-12212».")
        target, error = await _resolve_target(ctx, board_id, policy_content, dev_token, actor)
        if error is not None:
            return error
        if target.kind == "capped":
            return _out(target, {"recorded": False, "notice": "Trello y Plane no guardan bloqueos: solo avisan."})
        at = _now()
        line = _event_line(measure, uc_id, outcome, at, target.actor)
        if target.kind == "native":
            from ..coordination.audit import record_destructive
            from ..db.pool import get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                await record_destructive(
                    conn,
                    developer_id=target.developer_id,
                    project_id=target.project_id,
                    operation="enforcement_block" if outcome == "blocked" else "enforcement_pass",
                    target_id=uc_id,
                    metadata={"measure": measure, "uc_id": uc_id},
                )
        elif target.kind == "freeform_disk":
            _append_disk_event(target, line)
    except PolicyError as e:
        return policy_mod.policy_error(e, measure=measure)
    out = _out(target, {"recorded": True, "event": json.loads(line)})
    if target.kind == "freeform_content":
        out["event_line"] = line
    return out


async def enforcement_readiness(ctx: Context, dev_token: str = "") -> dict[str, Any]:
    """Qué medidas podrían nacer en «block» en los proyectos nuevos (UC-12213 AC-05). Solo operador.

    Recorre los tableros de EmbedBuild: por medida, bloqueos de los últimos 14 días, corregidos,
    saltados y porcentaje de saltos. Candidata si lleva 14 días seguidos bloqueando, con al menos 20
    bloqueos y un 10 % de saltos o menos. Es una lectura: el valor por defecto lo cambia una versión
    del engine con su codename, nunca esta tool.
    """
    from ..coordination.access_log import is_operator
    from ..coordination.identity import UnauthenticatedError
    from ..coordination.scope import resolve_caller_scope
    from .session_heartbeat import _unauthenticated

    try:
        scope = await resolve_caller_scope(ctx, token=dev_token)
    except UnauthenticatedError:
        return _unauthenticated()
    if not await is_operator(scope.developer_id):
        return {"success": False, "code": "FORBIDDEN", "error": "Solo el operador de SpecBox ve esta lectura."}
    events = await _native_events(None, like="EmbedBuild/%")
    return {
        "success": True,
        "boards": "EmbedBuild/*",
        "rule": (
            f"Candidata a «block» por defecto: {policy_mod.WINDOW_DAYS} días seguidos bloqueando, al menos "
            f"{policy_mod.READINESS_MIN_BLOCKS} bloqueos y saltos ≤ {policy_mod.READINESS_MAX_SKIP_RATE:.0%}. "
            "El cambio lo hace una versión del engine con su codename."
        ),
        "measures": policy_mod.readiness(events, now=datetime.now(timezone.utc)),
    }


def register_enforcement_tools(mcp_instance) -> None:
    """Registra las tools de la política de medidas (UC-12212 y UC-12213)."""
    mcp_instance.tool(
        description=(
            "Modo («off», «warn» o «block») de cada medida de EP-20 que puede detener el trabajo en "
            "este tablero, con su origen («new»/«existing») y quién lo cambió. Native: exige ser "
            "miembro. FreeForm remoto: pasa doc/tracking/policy.json en policy_content."
        )
    )(get_enforcement_policy)
    mcp_instance.tool(
        description=(
            "Cambia el modo de una medida de EP-20 en este tablero (off, warn o block). Native: solo "
            "project_admin; queda en la auditoría. Pasar a block va en dos pasos: la primera llamada "
            "devuelve el informe de impacto y un código confirm; la segunda, con confirm, lo aplica y "
            "deja las UC abiertas como anteriores a la regla. Trello y Plane: warn como máximo. "
            "threshold (solo spec_quality): parte de los criterios que tiene que pasar el gate en "
            "start_uc, de 0 a 1 (1 por defecto)."
        )
    )(set_enforcement_mode)
    mcp_instance.tool(
        description=(
            "Informe de impacto de las medidas de EP-20 en este tablero, sin cambiar nada: cuántas UC "
            "abiertas detendría cada medida en block y por qué, cuántas son anteriores a la regla y los "
            "bloqueos de 14 días con su porcentaje de saltos. FreeForm remoto: board_content y events_content."
        )
    )(get_enforcement_impact)
    mcp_instance.tool(
        description=(
            "Registra que una medida de EP-20 detuvo una UC (blocked) o la dejó pasar (passed). La usan "
            "las medidas de los hooks; un passed en 24 h tras un blocked cuenta como corregido."
        )
    )(record_enforcement_event)
    mcp_instance.tool(
        description=(
            "Solo operador: por medida, bloqueos, correcciones y saltos de 14 días en los tableros de "
            "EmbedBuild y si es candidata a block por defecto (≥20 bloqueos, ≤10 % de saltos, 14 días)."
        )
    )(enforcement_readiness)
    mcp_instance.tool(
        description=(
            "Salta una vez el bloqueo de una medida en una UC con un motivo (mín. 10 caracteres). "
            "Quedan quién, cuándo y por qué en el tablero. Solo para medidas en «block»."
        )
    )(skip_enforcement)


# ── Lo que el marcador de UC activa sabe de la política (UC-12211) ───


async def _native_uc(project_id: str, uc_id: str) -> dict[str, Any] | None:
    """La UC con sus criterios, como la ve el informe de impacto (misma huella)."""
    from ..db.pool import get_pool

    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT u.id AS uc_id, u.name, u.description, u.state,
               COALESCE(json_agg(json_build_object('ac_id', a.ac_id, 'text', a.text) ORDER BY a.ac_id)
                        FILTER (WHERE a.ac_id IS NOT NULL), '[]'::json) AS acs
          FROM use_cases u
          LEFT JOIN acceptance_criteria a ON a.project_id = u.project_id AND a.uc_id = u.id
         WHERE u.project_id = $1 AND u.id = $2
         GROUP BY u.id, u.name, u.description, u.state
        """,
        project_id,
        uc_id,
    )
    if row is None:
        return None
    acs = json.loads(row["acs"]) if isinstance(row["acs"], str) else row["acs"]
    return {"uc_id": row["uc_id"], "name": row["name"], "description": row["description"], "state": row["state"], "acs": acs}


async def marker_policy_extras(
    ctx: Context | None, board_id: str, uc_id: str, items_content: str | None, policy_content: str | None
) -> dict[str, Any]:
    """``predates_rule``: las medidas en «block» para las que la UC es anterior a la regla.

    Va en el marcador de UC activa para que los hooks que aplican medidas (spec_in_pr…) no
    detengan una UC anterior a la regla. Nunca lanza: sin datos, no añade nada.
    """
    from ..auth_gateway import BACKEND_STATE_KEY

    try:
        config = (await ctx.get_state(BACKEND_STATE_KEY) or {}) if ctx is not None else {}
        backend_type = config.get("backend_type") or ""
        raw: Any = None
        uc: dict[str, Any] | None = None
        if backend_type == "native":
            from ..db.pool import get_pool

            pool = await get_pool()
            raw = await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", board_id)
            raw = json.loads(raw) if isinstance(raw, str) else raw
            if raw:
                uc = await _native_uc(board_id, uc_id)
        elif backend_type == "freeform":
            if policy_content is not None:
                raw = _parse_policy_content(policy_content)
            elif config.get("root_path") and Path(config["root_path"]).is_absolute():
                path = Path(config["root_path"]) / policy_mod.POLICY_FILE
                raw = json.loads(path.read_text()) if path.exists() else None
            if raw:
                content = items_content
                if content is None and config.get("root_path"):
                    items_path = Path(config["root_path"]) / "items.json"
                    content = items_path.read_text() if items_path.exists() else None
                if content is not None:
                    uc = next((u for u in await _freeform_open_ucs(content) if u["uc_id"] == uc_id), None)
        if not raw or uc is None:
            return {}
        predates = policy_mod.predating_measures(raw, uc)
        return {"predates_rule": predates} if predates else {}
    except Exception:  # noqa: BLE001 — el marcador es una ayuda: nunca la razón de que falle start_uc
        return {}


# ── Las medidas que comprueba start_uc antes de arrancar una UC (US-123) ──

#: Estados desde los que una UC «arranca». Retomar una UC en curso, en revisión o hecha no la
#: revalida con las reglas nuevas (NFR de compatibilidad del PRD de EP-20).
START_GATE_STATES = frozenset({"backlog", "user_stories"})
#: Las medidas de start_uc, en el orden en que se comprueban (UC-12301, UC-12305).
START_MEASURES: tuple[str, ...] = ("spec_quality", "pending_decisions")
_START_CODES = {"spec_quality": "AC_QUALITY_BELOW_THRESHOLD", "pending_decisions": "PENDING_DECISIONS"}
_START_HOW_TO = {
    "spec_quality": policy_mod.SPEC_QUALITY_HOW_TO,
    "pending_decisions": policy_mod.PENDING_HOW_TO,
}
_CORRECTION_WINDOW_HOURS = 24


async def _gate_policy(ctx: Context | None, board_id: str, policy_content: str | None) -> tuple[str, Any, Path | None]:
    """(backend, política guardada, fichero de FreeForm local) del tablero de la sesión."""
    from ..auth_gateway import BACKEND_STATE_KEY

    config = (await ctx.get_state(BACKEND_STATE_KEY) or {}) if ctx is not None else {}
    backend_type = config.get("backend_type") or ""
    if backend_type == "native":
        from ..db.pool import get_pool

        pool = await get_pool()
        raw = await pool.fetchval("SELECT meta->'enforcement' FROM projects WHERE project_id = $1", board_id)
        return backend_type, (json.loads(raw) if isinstance(raw, str) else raw), None
    if backend_type == "freeform":
        if policy_content is not None:
            return backend_type, _parse_policy_content(policy_content), None
        root = config.get("root_path") or ""
        if root and Path(root).is_absolute() and not config.get("content_only"):
            path = Path(root) / policy_mod.POLICY_FILE
            return backend_type, (json.loads(path.read_text()) if path.exists() else None), path
    return backend_type, None, None


def _evaluate_start(measure: str, uc: dict[str, Any], raw: Any) -> tuple[bool, str, dict[str, Any]]:
    """(no pasa, motivo, detalle para la respuesta) de una medida de start_uc."""
    if measure == "spec_quality":
        result = policy_mod.spec_quality_result(uc, policy_mod.threshold_of(raw))
        detail = {k: result[k] for k in ("pass_rate", "threshold", "total", "failed")}
        return not result["meets_threshold"], policy_mod.spec_quality_reason(result) or "", detail
    if measure == "pending_decisions":
        marks = policy_mod.pending_marks(uc)
        return bool(marks), policy_mod.pending_reason(marks) or "", {"pending_marks": marks}
    raise ValueError(f"start_uc no comprueba la medida {measure!r}")


async def _native_take_skip(project_id: str, measure: str, uc_id: str) -> dict | None:
    """Gasta, bajo bloqueo de fila, el salto pendiente de ``measure`` en ``uc_id``."""
    from ..db.pool import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            raw = await conn.fetchval(
                "SELECT meta->'enforcement' FROM projects WHERE project_id = $1 FOR UPDATE", project_id
            )
            raw = json.loads(raw) if isinstance(raw, str) else raw
            stored, skip = policy_mod.take_skip(raw, measure, uc_id)
            if skip is not None:
                await conn.execute(
                    "UPDATE projects SET meta = meta || jsonb_build_object('enforcement', $2::jsonb), "
                    "updated_at = now() WHERE project_id = $1",
                    project_id,
                    json.dumps(stored),
                )
    return skip


async def _native_record(project_id: str, developer_id: str, measure: str, uc_id: str, outcome: str) -> None:
    """Un bloqueo de start_uc, o el paso que lo corrige (solo si hubo bloqueo en las últimas 24 h)."""
    from ..coordination.audit import record_destructive
    from ..db.pool import get_pool

    pool = await get_pool()
    async with pool.acquire() as conn:
        if outcome == "passed":
            blocked = await conn.fetchval(
                f"""
                SELECT 1 FROM audit_log
                 WHERE project_id = $1 AND operation = 'enforcement_block' AND target_id = $2
                   AND metadata->>'measure' = $3
                   AND occurred_at >= now() - interval '{_CORRECTION_WINDOW_HOURS} hours'
                 LIMIT 1
                """,
                project_id,
                uc_id,
                measure,
            )
            if not blocked:
                return
        await record_destructive(
            conn,
            developer_id=developer_id or None,
            project_id=project_id,
            operation="enforcement_block" if outcome == "blocked" else "enforcement_pass",
            target_id=uc_id,
            metadata={"measure": measure, "uc_id": uc_id},
        )


async def start_gate(
    ctx: Context | None,
    board_id: str,
    uc_id: str,
    uc_item: Any,
    backend: Any,
    *,
    policy_content: str | None = None,
    developer_id: str = "",
) -> dict[str, Any]:
    """Las medidas de EP-20 que start_uc comprueba antes de arrancar una UC (UC-12301).

    Devuelve ``{"error": …}`` si una medida en «block» detiene el arranque (no se reserva ni se mueve
    nada), o ``{"warnings": […]}`` con lo que avisan las medidas en «warn» y las UC anteriores a la
    regla o con un salto. FreeForm por contenido añade ``policy_content`` (si se gastó un salto) y
    ``event_lines`` para el hook freeform-fragment. Solo actúa si la UC arranca (backlog o
    user_stories). Nunca es la razón de que start_uc falle: si no puede comprobar, avisa y sigue.
    """
    out: dict[str, Any] = {"warnings": [], "event_lines": []}
    if (getattr(uc_item, "state", "") or "") not in START_GATE_STATES:
        return out
    try:
        backend_type, raw, disk = await _gate_policy(ctx, board_id, policy_content)
        policy = policy_mod.effective_policy(raw, backend_type=backend_type)
        measures = [
            m for m in START_MEASURES
            if policy["measures"][m]["active"] and policy_mod.mode_of(policy, m) != "off"
        ]
        if not measures:
            return out
        acs = await backend.get_acceptance_criteria(board_id, uc_item.id)
        uc = {
            "uc_id": uc_id,
            "name": uc_item.name,
            "description": uc_item.description,
            "state": uc_item.state,
            "acs": [{"ac_id": ac.id, "text": ac.text} for ac in acs],
        }
        at = _now()
        by = developer_id or "start_uc"
        for measure in measures:
            failed, reason, detail = _evaluate_start(measure, uc, raw)
            mode = policy_mod.mode_of(policy, measure)
            predates = failed and mode == "block" and policy_mod.predates_rule(raw, measure, uc)
            skip = None
            if failed and mode == "block" and not predates:
                if backend_type == "native":
                    skip = await _native_take_skip(board_id, measure, uc_id)
                else:
                    stored, skip = policy_mod.take_skip(raw, measure, uc_id)
                    if skip is not None:
                        raw = stored
                        if disk is not None:
                            disk.parent.mkdir(parents=True, exist_ok=True)
                            disk.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n")
                        elif policy_content is not None:
                            out["policy_content"] = json.dumps(stored, ensure_ascii=False, indent=2) + "\n"
            how_to = _START_HOW_TO[measure] + (policy_mod.SKIP_HOW_TO if mode == "block" else "")
            decision = policy_mod.check(
                policy, measure, failed=failed, reason=reason, how_to_continue=how_to,
                skip=skip, predates=predates,
            )
            outcome = decision["outcome"]
            if outcome in ("blocked", "pass") and mode != "off":
                event = "blocked" if outcome == "blocked" else "passed"
                if backend_type == "native":
                    await _native_record(board_id, developer_id, measure, uc_id, event)
                elif outcome == "blocked":
                    line = _event_line(measure, uc_id, "blocked", at, by)
                    if disk is not None:
                        path = disk.parent / EVENTS_FILE
                        with path.open("a", encoding="utf-8") as fh:
                            fh.write(line + "\n")
                    elif backend_type == "freeform":
                        out["event_lines"].append(line)
            if outcome == "blocked":
                error = {**decision["error"], "code": _START_CODES[measure], "uc_id": uc_id, **detail}
                logger.info("start_uc_blocked", measure=measure, uc_id=uc_id, backend=backend_type)
                return {"error": error, "event_lines": out["event_lines"], **(
                    {"policy_content": out["policy_content"]} if "policy_content" in out else {}
                )}
            if decision.get("warning"):
                out["warnings"].append({**decision["warning"], "outcome": outcome, **detail})
    except Exception as e:  # noqa: BLE001 — la medida avisa de que no pudo mirar; start_uc sigue
        logger.warning("start_gate_failed", uc_id=uc_id, error=str(e))
        out["warnings"].append({
            "measure": "spec_quality",
            "reason": f"No se pudo comprobar la spec de {uc_id}: {e}",
            "how_to_continue": "La UC arranca igualmente. Repite start_uc si quieres la comprobación.",
            "message": f"Aviso de SpecBox: no se pudo comprobar la spec de {uc_id} ({e}); la UC arranca.",
            "outcome": "unchecked",
        })
    return out


async def spec_gate_summary(
    ctx: Context | None, board_id: str, ucs: list[dict[str, Any]], policy_content: str | None = None
) -> list[dict[str, Any]]:
    """El gate de calidad de cada UC que toca import_spec o add_ac (UC-12301 AC-04). Solo informa.

    Usa el umbral del tablero si se puede leer (native, FreeForm local o ``policy_content``); si no,
    1,0. ``meets_threshold`` dice si start_uc la arrancaría con ``spec_quality`` en «block».
    """
    try:
        _, raw, _ = await _gate_policy(ctx, board_id, policy_content)
        threshold = policy_mod.threshold_of(raw)
    except Exception:  # noqa: BLE001 — informar del gate nunca hace fallar el alta
        threshold = policy_mod.DEFAULT_THRESHOLD
    out = []
    for uc in ucs:
        result = policy_mod.spec_quality_result(uc, threshold)
        out.append({
            "uc_id": uc.get("uc_id"),
            **{k: result[k] for k in ("pass_rate", "threshold", "total", "meets_threshold", "failed")},
            "pending_marks": policy_mod.pending_marks(uc),  # UC-12305
        })
    return out
