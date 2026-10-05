"""Tools de épicas (US-78 · UC-7802, decisión D20).

La épica agrupa historias: cada historia está en una épica o en ninguna, y el
estado y el avance de la épica se deducen de sus historias (:mod:`server.epics`).
Estas tools son la única forma de crearlas y moverlas: el panel las muestra.

- ``add_epic``, ``update_epic``, ``delete_epic``: la ficha de la épica.
- ``set_us_epic``: mete una historia en una épica (sale de la anterior) o la saca.
- ``list_epics``, ``get_epic``: las épicas con su estado, avance y satélites.

Native y FreeForm (con ``items_content``). Trello y Plane responden
``EPICS_NOT_SUPPORTED``. En native, cada escritura comprueba la membresía del
proyecto escrito y deja su fila en ``audit_log``; cada lectura, la del proyecto
leído (US-83). Los fallos vuelven como sobre ``{code, error}``, nunca con datos.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastmcp import Context

from ..auth_gateway import get_session_backend
from ..epics import NO_EPIC, epic_of, summarize_board, summarize_epic, summarize_stories, us_logical_id
from ..spec_backend import EPIC_NOT_FOUND, EpicError, SpecBackend
from ._content_passing import returns_items_content

logger = structlog.get_logger(__name__)


def _err(code: str, message: str, **ctx: Any) -> dict[str, Any]:
    return {"error": message, "code": code, **ctx}


async def _run(
    ctx: Context,
    items_content: str | None,
    op: Callable[[SpecBackend], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    """Abre el backend de la sesión, ejecuta ``op`` y convierte los rechazos en sobres."""
    from ..coordination.identity import ForbiddenError, UnauthenticatedError

    backend = await get_session_backend(ctx, items_content=items_content)
    try:
        return await op(backend)
    except EpicError as exc:
        return _err(exc.code, exc.message)
    except ForbiddenError as exc:
        return _err("FORBIDDEN", str(exc))
    except UnauthenticatedError as exc:
        return _err("UNAUTHENTICATED", str(exc))
    finally:
        await backend.close()


async def _find_epic(backend: SpecBackend, board_id: str, epic_id: str):
    epic = next((e for e in await backend.list_epics(board_id) if e.id == epic_id), None)
    if epic is None:
        raise EpicError(EPIC_NOT_FOUND, f"{epic_id} does not exist.")
    return epic


@returns_items_content
async def add_epic(
    board_id: str,
    name: str,
    ctx: Context,
    objective: str = "",
    link: str = "",
    position: int | None = None,
    target_date: str | None = None,
    epic_id: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Create an epic: the group above user stories (D20).

    Without ``epic_id`` it takes the next free EP-NN; ``position`` defaults to
    the end; ``target_date`` is YYYY-MM-DD. Returns the epic with its derived
    state and progress (empty until stories join it with ``set_us_epic``).
    """

    async def op(backend: SpecBackend) -> dict[str, Any]:
        epic = await backend.create_epic(
            board_id,
            name=name,
            objective=objective,
            link=link,
            position=position,
            target_date=target_date,
            epic_id=epic_id,
        )
        return {"epic": summarize_epic(epic, await backend.list_items(board_id))}

    return await _run(ctx, items_content, op)


@returns_items_content
async def update_epic(
    board_id: str,
    epic_id: str,
    ctx: Context,
    name: str | None = None,
    objective: str | None = None,
    link: str | None = None,
    position: int | None = None,
    target_date: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Change an epic's name, objective, link, position or target date.

    Only the fields you pass change; ``target_date=""`` clears the date.
    """
    fields = {
        k: v
        for k, v in {
            "name": name,
            "objective": objective,
            "link": link,
            "position": position,
            "target_date": target_date,
        }.items()
        if v is not None
    }

    async def op(backend: SpecBackend) -> dict[str, Any]:
        epic = await backend.update_epic(board_id, epic_id, **fields)
        return {
            "epic": summarize_epic(epic, await backend.list_items(board_id)),
            "updated_fields": sorted(fields),
        }

    return await _run(ctx, items_content, op)


@returns_items_content
async def delete_epic(
    board_id: str,
    epic_id: str,
    ctx: Context,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Delete an epic. Its stories stay on the board, without epic; nothing else is deleted."""

    async def op(backend: SpecBackend) -> dict[str, Any]:
        result = await backend.delete_epic(board_id, epic_id)
        return {"deleted": epic_id, "detached_us": result["detached_us"]}

    return await _run(ctx, items_content, op)


@returns_items_content
async def set_us_epic(
    board_id: str,
    us_id: str,
    ctx: Context,
    epic_id: str | None = None,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Put a user story in an epic (it leaves its previous one), or take it out with ``epic_id=None``."""

    async def op(backend: SpecBackend) -> dict[str, Any]:
        story = await backend.find_item_by_field(board_id, "us_id", us_id)
        if story is None:
            return _err("US_NOT_FOUND", f"User Story {us_id} not found", us_id=us_id)
        previous = epic_of(story)
        updated = await backend.set_us_epic(board_id, story.id, epic_id)
        return {"us_id": us_id, "epic_id": epic_of(updated), "previous_epic_id": previous}

    return await _run(ctx, items_content, op)


@returns_items_content
async def list_epics(
    board_id: str,
    ctx: Context,
    items_content: str | None = None,
) -> dict[str, Any]:
    """List the epics in order with derived state, progress (done/total criteria and %) and satellites.

    The stories without epic come last as ``sin_epica`` so the groups add up to the board.
    """

    async def op(backend: SpecBackend) -> dict[str, Any]:
        groups = summarize_board(await backend.list_epics(board_id), await backend.list_items(board_id))
        epics = [g for g in groups if g["epic_id"] != NO_EPIC]
        loose = next((g for g in groups if g["epic_id"] == NO_EPIC), None)
        return {"epics": epics, "sin_epica": loose, "total": len(epics)}

    return await _run(ctx, items_content, op)


@returns_items_content
async def get_epic(
    board_id: str,
    epic_id: str,
    ctx: Context,
    items_content: str | None = None,
) -> dict[str, Any]:
    """Get an epic: its fields, derived state and progress, satellites and each of its stories."""

    async def op(backend: SpecBackend) -> dict[str, Any]:
        epic = await _find_epic(backend, board_id, epic_id)
        items = await backend.list_items(board_id)
        summary = summarize_epic(epic, items)
        stories = [i for i in items if "US" in (i.labels or []) and epic_of(i) == epic_id]
        summary["stories"] = [
            {"us_id": us_logical_id(s), "name": s.name, "state": s.state, **_story_counts(s, items)}
            for s in stories
        ]
        return summary

    return await _run(ctx, items_content, op)


def _story_counts(story, items) -> dict[str, Any]:
    counts = summarize_stories([story], items)
    return {k: counts[k] for k in ("uc_total", "uc_done", "ac_total", "ac_done", "pct", "satellites")}


def register_epic_tools(mcp_instance) -> None:
    """Register the 6 epic tools (US-78 / UC-7802)."""
    mcp_instance.tool(
        description="Create an epic (EP-NN): the group above user stories, with name, objective, "
        "link to its PRD, position and optional target date. Native and FreeForm."
    )(add_epic)
    mcp_instance.tool(
        description="Change an epic's name, objective, link, position or target date "
        "(target_date='' clears it)."
    )(update_epic)
    mcp_instance.tool(
        description="Delete an epic; its user stories stay, without epic."
    )(delete_epic)
    mcp_instance.tool(
        description="Put a user story in an epic (it leaves the previous one) or take it out "
        "with epic_id=None."
    )(set_us_epic)
    mcp_instance.tool(
        description="List epics with derived state, progress (done/total criteria and %) and "
        "satellites, plus the stories without epic."
    )(list_epics)
    mcp_instance.tool(
        description="Get one epic: fields, derived state and progress, satellites and its stories."
    )(get_epic)
