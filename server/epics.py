"""Estado y avance de las épicas (US-78 · UC-7801, decisión D20).

Una épica no guarda su estado ni su avance: se deducen de sus historias, igual
que el estado de una historia se deduce de sus casos de uso (UC-4305). Así
nadie mueve una épica a mano y nunca miente sobre lo que hay debajo.

- **Estado**: la regla de :func:`server.tools.spec_driven.derive_us_state`
  aplicada a los estados de sus historias. Sin nada empezado (o sin historias)
  la épica está ``backlog``.
- **Avance**: criterios hechos sobre criterios totales de los casos de uso de
  sus historias. Sin criterios, ``pct`` es ``None``: un 0 % inventado diría que
  hay trabajo pendiente donde no hay nada que medir (D18, «sin fallback
  silencioso a cero»).
- **Satélites**: los de sus casos de uso, sin repetir, en orden de aparición.

Funciones puras sobre los DTO del backend: valen igual para Native y FreeForm.
"""

from __future__ import annotations

from typing import Any

from .spec_backend import EpicDTO, ItemDTO, parse_item_id

#: Estados del flujo; una UC archivada (cualquier otro estado) no cuenta.
WORKFLOW_STATES = ("user_stories", "backlog", "in_progress", "review", "done")

#: Clave del grupo de historias sin épica en los desgloses.
NO_EPIC = "sin_epica"


def _labels(item: ItemDTO) -> list[str]:
    return item.labels or []


def us_logical_id(item: ItemDTO) -> str:
    """El US-XX de una historia (meta o nombre)."""
    return item.meta.get("us_id") or parse_item_id(item.name, "US")[0] or item.id


def epic_of(item: ItemDTO) -> str | None:
    """La épica de una historia, o None."""
    return item.meta.get("epic_id") or None


def _children(items: list[ItemDTO], story: ItemDTO) -> list[ItemDTO]:
    us_id = us_logical_id(story)
    return [
        i
        for i in items
        if "UC" in _labels(i)
        and i.state in WORKFLOW_STATES
        and (i.meta.get("us_id") == us_id or (i.parent_id is not None and i.parent_id == story.id))
    ]


def summarize_stories(stories: list[ItemDTO], items: list[ItemDTO]) -> dict[str, Any]:
    """Estado, recuentos, avance y satélites de un grupo de historias."""
    from .tools.spec_driven import derive_us_state  # import tardío: spec_driven importa este módulo

    ucs = [uc for story in stories for uc in _children(items, story)]
    uc_ids = {uc.id for uc in ucs}
    acs = [i for i in items if "AC" in _labels(i) and i.parent_id in uc_ids]
    ac_done = sum(1 for ac in acs if ac.state == "done")
    satellites: list[str] = []
    for uc in ucs:
        sat = uc.meta.get("satellite")
        if sat and sat not in satellites:
            satellites.append(sat)
    return {
        "state": derive_us_state([s.state for s in stories]) or "backlog",
        "us_ids": [us_logical_id(s) for s in stories],
        "us_total": len(stories),
        "us_done": sum(1 for s in stories if s.state == "done"),
        "uc_total": len(ucs),
        "uc_done": sum(1 for uc in ucs if uc.state == "done"),
        "ac_total": len(acs),
        "ac_done": ac_done,
        "pct": round(ac_done * 100 / len(acs)) if acs else None,
        "satellites": satellites,
    }


def summarize_epic(epic: EpicDTO, items: list[ItemDTO]) -> dict[str, Any]:
    """La ficha de una épica con su estado y su avance deducidos."""
    stories = [i for i in items if "US" in _labels(i) and epic_of(i) == epic.id]
    return {
        "epic_id": epic.id,
        "name": epic.name,
        "objective": epic.objective,
        "link": epic.link,
        "position": epic.position,
        "target_date": epic.target_date,
        **summarize_stories(stories, items),
    }


def summarize_board(epics: list[EpicDTO], items: list[ItemDTO]) -> list[dict[str, Any]]:
    """Todas las épicas en su orden y, al final, el grupo «sin épica» si tiene historias.

    Una historia que apunta a una épica que ya no existe cuenta como sin épica,
    así la suma de los grupos siempre cuadra con el total del board.
    """
    known = {e.id for e in epics}
    groups = [summarize_epic(e, items) for e in epics]
    loose = [i for i in items if "US" in _labels(i) and epic_of(i) not in known]
    if loose:
        groups.append({"epic_id": NO_EPIC, "name": "Sin épica", **summarize_stories(loose, items)})
    return groups
