"""La puerta de desviación del CI local (US-126): lo que la rama cambia frente a la spec.

UC-12603: ``get_closed_uc_files`` dice, para unas rutas cambiadas, qué UC cerradas las cambiaron en su
cierre (``complete_uc(files=[…])``), con la propuesta de revisar sus criterios. Solo lee: la spec no
cambia hasta que una persona lo decide.
"""

from __future__ import annotations

from typing import Any

from fastmcp import Context

from ..auth_gateway import get_session_backend
from ..closed_files import NOT_SUPPORTED_NOTICE, ClosedUc, closed_uc_touches
from .spec_driven import _get_uc_id, _get_us_id, _is_uc, _is_us


def closed_ucs_of(items: list[Any]) -> list[ClosedUc]:
    """Las UC hechas del tablero con la lista que guardó su cierre (None si se cerraron sin ella)."""
    stories = {i.id: _get_us_id(i) for i in items if _is_us(i)}
    out: list[ClosedUc] = []
    for item in items:
        if not _is_uc(item) or item.state != "done":
            continue
        meta = item.meta or {}
        files = meta.get("closed_files")
        out.append(ClosedUc(
            uc_id=_get_uc_id(item),
            us_id=str(meta.get("us_id") or stories.get(item.parent_id or "", "")),
            name=_display_name(item.name, _get_uc_id(item)),
            files=[f for f in files if isinstance(f, str)] if isinstance(files, list) else None,
            closed_at=meta.get("closed_files_at") if isinstance(meta.get("closed_files_at"), str) else None,
        ))
    return out


def _display_name(name: str, uc_id: str) -> str:
    clean = (name or "").strip()
    for prefix in (f"[{uc_id}]", f"{uc_id}:", uc_id):
        if prefix and clean.startswith(prefix):
            return clean[len(prefix):].strip(" :·-")
    return clean


async def get_closed_uc_files(
    board_id: str,
    paths: list[str],
    ctx: Context,
    exclude_uc_ids: list[str] | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Which closed UCs changed these files when they were closed (UC-12603). Read-only.

    Args:
        board_id: Board/project ID.
        paths: Files changed by the branch, relative to the repo.
        exclude_uc_ids: The branch's own UCs (their files are not «another UC»).
        items_content: FreeForm content-passing: the whole items.json for the remote MCP.

    Returns:
        `touches`: one entry per closed UC that changed any of the paths, with `files` and a
        `proposal` to review its criteria (the board does not change: a person decides).
        `by_path`: path → closed UCs. `closed_without_files`: closed UCs without their list (closed
        before 6.46.0, or without `files`), which never warn, with a `notice`. Trello and Plane do not
        keep the list: `supported: false`.
    """
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        return {"error": "paths debe ser una lista de rutas (texto)", "code": "INVALID_PATHS"}
    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        if not getattr(backend, "STORES_SPEC_META", False):
            return {"success": True, "supported": False, "touches": [], "by_path": {}, "closed_without_files": 0,
                    "notice": NOT_SUPPORTED_NOTICE}
        items = await backend.list_board_summary(board_id)
        report = closed_uc_touches(closed_ucs_of(items), paths, exclude_uc_ids)
        return {"success": True, "supported": True, **report}
    finally:
        await backend.close()


def register_spec_drift_tools(mcp_instance) -> None:
    """Registra las tools de la puerta de desviación (US-126)."""
    mcp_instance.tool(
        description="Which closed UCs changed these files when they were closed (read-only, UC-12603): "
        "pass the branch's changed paths and its own UCs as exclude_uc_ids. Returns touches (closed UC, "
        "its files, and a proposal to review its criteria; the spec does not change), by_path and "
        "closed_without_files (closed without their file list, before 6.46.0: they never warn)."
    )(get_closed_uc_files)
