"""La aprobación de los criterios de una UC antes de implementar (US-125 · UC-12502).

Una aprobación guarda la huella de los criterios vigentes (id y texto, también los internos) con
quién y cuándo. Una UC está aprobada si la huella de su última aprobación es la de sus criterios de
ahora: cambiar un texto, añadir un criterio o retirarlo cambia la huella y la UC queda sin aprobar,
con la misma regla en native y en FreeForm, lo escriba quien lo escriba. Cambiar cómo se comprueba
un criterio (``verification``), marcarlo o pasarlo a interno no la cambia.

Estados (``criteria_approval.state``):

- ``approved``: la última aprobación es de estos criterios;
- ``stale``: hubo aprobación, pero los criterios cambiaron después;
- ``none``: nunca se aprobaron;
- ``migration``: la medida ``ac_approval`` está en «block» y la UC es anterior a la regla
  (``predates_rule``): cuenta como aprobada, con la marca «aprobada por migración».
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from .tools._mutation_helpers import norm_text

APPROVED_STATES = frozenset({"approved", "migration"})
MIGRATION_LABEL = "aprobada por migración"


def _ac_number(ac_id: str) -> tuple[int, str]:
    try:
        return int(str(ac_id).split("-")[1]), str(ac_id)
    except (IndexError, ValueError):
        return 10**6, str(ac_id)


def criteria_snapshot(acs: Iterable[Any]) -> list[dict[str, str]]:
    """Los criterios vigentes como ``[{id, text}]`` en orden de id (lo que se aprueba)."""
    pairs = []
    for ac in acs:
        ac_id = (ac.get("id") or ac.get("ac_id")) if isinstance(ac, dict) else getattr(ac, "id", "")
        text = ac.get("text") if isinstance(ac, dict) else getattr(ac, "text", "")
        pairs.append({"id": str(ac_id), "text": norm_text(text)})
    return sorted(pairs, key=lambda p: _ac_number(p["id"]))


def criteria_fingerprint(acs: Iterable[Any]) -> str:
    """La huella de los criterios vigentes: cambia si cambia su id o su texto, o si hay uno más o menos."""
    snapshot = criteria_snapshot(acs)
    joined = "\n".join(f"{p['id']}:{p['text']}" for p in snapshot)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:32]


def approval_state(latest: dict[str, Any] | None, fingerprint: str, *, predates: bool = False) -> dict[str, Any]:
    """El estado de la aprobación de una UC con estos criterios (ver el docstring del módulo)."""
    if isinstance(latest, dict) and latest.get("fingerprint") == fingerprint:
        out: dict[str, Any] = {"state": "approved"}
        for key in ("by", "at", "session_id", "source"):
            if latest.get(key) is not None:
                out[key] = latest[key]
        return out
    if predates:
        return {"state": "migration", "source": "migration", "label": MIGRATION_LABEL}
    if isinstance(latest, dict) and latest.get("fingerprint"):
        out = {"state": "stale", "reason": "Los criterios cambiaron después de la última aprobación."}
        for key in ("by", "at"):
            if latest.get(key) is not None:
                out[f"previous_{key}"] = latest[key]
        return out
    return {"state": "none"}


def is_approved(state: dict[str, Any] | None) -> bool:
    """True si el estado cuenta como aprobado (también «aprobada por migración»)."""
    return isinstance(state, dict) and state.get("state") in APPROVED_STATES


def not_approved_reason(uc_id: str, state: dict[str, Any]) -> str:
    """El motivo, en llano, de que una UC no cuente como aprobada."""
    if state.get("state") == "stale":
        return f"Los criterios de {uc_id} cambiaron después de su última aprobación."
    return f"Nadie ha aprobado todavía los criterios de {uc_id}."
