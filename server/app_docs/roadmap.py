"""La zona «roadmap» de app_prd.md sale del tablero (US-122 · UC-12203).

`@requires_app_docs_sync` existía pero no estaba aplicado a ninguna tool, y su extractor mandaba
`rows=[]`: si se hubiera aplicado, habría vaciado la zona («(sin datos)»). Además escribía en el
disco del servidor, que con el MCP remoto no es el del proyecto (US-86).

Ahora, tras `complete_uc`, `move_uc`, `add_uc`, `delete_uc` y `mark_ac_batch`:

* el servidor calcula el cuerpo de la zona con lo que dice el tablero (una fila por historia, con
  su estado y sus UC hechas/total) y lo devuelve en ``app_docs_sync.roadmap_body``; nunca escribe
  en disco;
* el hook ``app-docs-fragment`` lo escribe en ``doc/app/app_prd.md`` del repositorio que lo tiene
  (el orquestador en un proyecto multirepo), y solo si ese repositorio está en su rama principal:
  la zona se regenera desde el tablero, así que dos ramas no chocan al fusionar;
* con FreeForm por fragmentos el servidor no ve el tablero entero (``render: "client"``) y el hook
  calcula el mismo cuerpo con su ``items.json`` (``.claude/hooks/lib/roadmap.mjs``; una prueba
  compara los dos).

Si algo falla, la respuesta lleva ``app_docs_sync.ok = false`` con el motivo y el cambio de estado
de la UC sigue hecho: la sincronización nunca deshace ni bloquea la tool.
"""

from __future__ import annotations

import functools
import inspect
import json
import re
from typing import Any

ROADMAP_DOC = "doc/app/app_prd.md"
ROADMAP_ZONE = "roadmap"
ROADMAP_TOOLS = ("complete_uc", "move_uc", "add_uc", "delete_uc", "mark_ac_batch")
_US_PREFIX = re.compile(r"^\[?US-\d+[a-z]?\]?\s*[:—–-]?\s*")
_US_NUMBER = re.compile(r"^US-(\d+)")


def _title(name: str, us_id: str) -> str:
    text = _US_PREFIX.sub("", str(name or "").strip()) if us_id else str(name or "").strip()
    return " ".join(text.split()).replace("|", "\\|")


def _order(row: dict[str, Any]) -> tuple[int, str]:
    m = _US_NUMBER.match(row["us_id"])
    return (int(m.group(1)) if m else 10**9, row["us_id"])


def rows_from_items(items: list[Any]) -> list[dict[str, Any]]:
    """Una fila por historia no archivada: id, título, estado y UC hechas/total (sin archivadas)."""
    from ..spec_backend import parse_item_id

    stories: dict[str, dict[str, Any]] = {}
    for item in items:
        if "US" in item.labels and item.state != "archived":
            us_id = item.meta.get("us_id") or parse_item_id(item.name, "US")[0] or ""
            if us_id:
                stories[item.id] = {"us_id": us_id, "title": _title(item.name, us_id), "state": item.state, "done": 0, "total": 0}
    for item in items:
        if "UC" in item.labels and item.state != "archived" and item.parent_id in stories:
            row = stories[item.parent_id]
            row["total"] += 1
            row["done"] += 1 if item.state == "done" else 0
    return sorted(stories.values(), key=_order)


async def rows_native(project_id: str) -> list[dict[str, Any]]:
    """Las mismas filas con una sola consulta al tablero native."""
    from ..db.pool import get_pool

    pool = await get_pool()
    records = await pool.fetch(
        """
        SELECT us.id, us.name, us.state,
               count(uc.id) FILTER (WHERE uc.state <> 'archived') AS total,
               count(uc.id) FILTER (WHERE uc.state = 'done') AS done
          FROM user_stories us
          LEFT JOIN use_cases uc ON uc.project_id = us.project_id AND uc.us_id = us.id
         WHERE us.project_id = $1 AND us.state <> 'archived'
         GROUP BY us.id, us.name, us.state
        """,
        project_id,
    )
    rows = [
        {"us_id": r["id"], "title": _title(r["name"], r["id"]), "state": r["state"], "done": r["done"], "total": r["total"]}
        for r in records
    ]
    return sorted(rows, key=_order)


def render(rows: list[dict[str, Any]]) -> str:
    """El cuerpo de la zona. Solo depende del tablero: la misma foto da el mismo texto."""
    out = [
        "## 5. Roadmap de US",
        "",
        "> Esta zona la mantiene el engine con lo que dice el tablero: se regenera tras complete_uc, "
        "move_uc, add_uc, delete_uc y mark_ac_batch. No la edites a mano.",
        "",
        "| US | Título | Estado | UCs |",
        "|----|--------|--------|-----|",
    ]
    if not rows:
        out.append("| (sin historias) | | | |")
    for r in rows:
        out.append(f"| {r['us_id']} | {r['title']} | {r['state']} | {r['done']}/{r['total']} |")
    return "\n".join(out)


def _is_fragment(content: str) -> bool:
    try:
        parsed = json.loads(content or "[]")
    except json.JSONDecodeError:
        return False
    return isinstance(parsed, dict) and "format" in parsed


async def roadmap_sync(ctx: Any, board_id: str, items_content: str | None, result: dict[str, Any]) -> dict[str, Any]:
    """El ``app_docs_sync`` de una tool que cambia el estado del tablero."""
    base: dict[str, Any] = {"ok": True, "document": ROADMAP_DOC, "zone": ROADMAP_ZONE}
    if items_content is not None:
        content = result.get("items_content") if isinstance(result.get("items_content"), str) else items_content
        if _is_fragment(content):
            # El fragmento no trae el tablero entero: el hook calcula la zona con su items.json.
            return {**base, "render": "client"}
        from ..backends.freeform_backend import FreeformBackend

        rows = rows_from_items(await FreeformBackend(items_content=content).list_items(board_id))
        return {**base, "roadmap_body": render(rows), "stories": len(rows)}

    from ..auth_gateway import BACKEND_STATE_KEY, get_session_backend

    config = (await ctx.get_state(BACKEND_STATE_KEY) or {}) if ctx is not None else {}
    if config.get("backend_type") == "native":
        rows = await rows_native(board_id)
    else:
        backend = await get_session_backend(ctx)
        try:
            rows = rows_from_items(await backend.list_items(board_id))
        finally:
            await backend.close()
    return {**base, "roadmap_body": render(rows), "stories": len(rows)}


def with_roadmap_sync(fn):
    """Tras una tool que cambia el tablero, ``app_docs_sync`` con la zona «roadmap» (UC-12203).

    Solo si la llamada trae ``with_roadmap=True``, que pone el hook app-docs-fragment cuando el
    proyecto tiene app_prd.md y su repositorio está en la rama principal (UC-12218): sin pedirla, la
    respuesta queda como antes y no gasta contexto. Va por fuera de ``@returns_items_content`` para
    ver el tablero ya cambiado. Nunca cambia el resultado de la tool más allá de añadir
    ``app_docs_sync``, ni lanza.
    """
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = await fn(*args, **kwargs)
        if not isinstance(result, dict) or result.get("error") or result.get("success") is False:
            return result
        try:
            bound = signature.bind_partial(*args, **kwargs).arguments
            if bound.get("with_roadmap") is not True:
                return result
            result["app_docs_sync"] = await roadmap_sync(
                bound.get("ctx"), str(bound.get("board_id") or ""), bound.get("items_content"), result
            )
        except Exception as exc:  # noqa: BLE001 — la sincronización nunca deshace la tool
            result["app_docs_sync"] = {
                "ok": False,
                "document": ROADMAP_DOC,
                "zone": ROADMAP_ZONE,
                "error": "roadmap_sync_failed",
                "reason": f"{type(exc).__name__}: {str(exc)[:200]}",
            }
        return result

    return wrapper
