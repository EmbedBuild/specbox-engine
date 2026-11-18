"""El modo de cada medida de EP-20 en un tablero (US-122 · UC-12212).

Tres tools sobre la política de ``server/coordination/enforcement.py``:

* ``get_enforcement_policy`` — el modo de cada medida, su origen y desde cuándo bloquea;
* ``set_enforcement_mode``   — cambia el modo de una medida (en native, solo ``project_admin``);
* ``skip_enforcement``       — salta un bloqueo con motivo; queda quién, cuándo y por qué, y la
  siguiente comprobación de esa medida en esa UC pasa una vez. La plantilla de permisos la pone en
  «ask»: una persona lo confirma en Claude Code.

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
    policy_content: str | None = None,
    dev_token: str = "",
    actor: str = "",
) -> dict[str, Any]:
    """Cambia el modo de una medida en este tablero: «off», «warn» o «block».

    Ninguna medida pasa a «block» sola: lo cambia una persona (en native, quien tiene
    ``project_admin``; la plantilla de permisos pide confirmación). Queda quién y cuándo.
    """
    try:
        target, error = await _resolve_target(ctx, board_id, policy_content, dev_token, actor)
        if error is not None:
            return error
        at = _now()

        def mutate(raw):
            return policy_mod.with_mode(raw, measure, mode, by=target.actor, at=at, backend_type=target.backend_type)

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
            if target.kind == "freeform_disk":
                _save_disk(target, stored)
    except PolicyError as e:
        return policy_mod.policy_error(e, measure=measure)
    logger.info("enforcement_skip_recorded", backend=target.backend_type, measure=measure)
    return _out(target, {"skip": skip}, stored)


def register_enforcement_tools(mcp_instance) -> None:
    """Registra las tres tools de la política de medidas (UC-12212)."""
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
            "project_admin; queda en la auditoría. Trello y Plane: no se guarda (warn como máximo)."
        )
    )(set_enforcement_mode)
    mcp_instance.tool(
        description=(
            "Salta una vez el bloqueo de una medida en una UC con un motivo (mín. 10 caracteres). "
            "Quedan quién, cuándo y por qué en el tablero. Solo para medidas en «block»."
        )
    )(skip_enforcement)
