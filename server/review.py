"""Quien implementa no da el visto bueno a su propio trabajo (US-124 · UC-12402).

La parte pura de la revisión independiente, sin tablero ni red:

- **Identidad del contexto.** Claude Code da a cada hook ``session_id`` y, dentro de un subagente,
  ``agent_id`` y ``agent_type``. Los hooks ``agent-identity`` y ``freeform-fragment`` la ponen en
  ``start_uc`` (quién implementa) y en ``record_review_verdict`` (quién revisa) como
  ``client_session_id``, ``client_agent_id`` y ``client_agent_type``. Sale de Claude Code, no del modelo;
  un cliente sin esos hooks no la manda y su veredicto no cuenta como independiente.
- **Independiente.** Un veredicto es independiente si su contexto (sesión y agente) no es el de quien
  implementó. Un subagente evaluador de la misma sesión tiene otro ``agent_id``: vale.
- **Lo que deja fusionar** (:func:`independent_review_result`): la aceptación de una persona (el panel)
  en cualquier nivel de autopilot; en «agresivo», y en FreeForm, que no tiene panel, también el último
  veredicto «aceptada» de un contexto independiente. Una UC devuelta después no se fusiona.
- **Caducan** (:func:`voids_review`): al volver a trabajo desde revisión o hecha, o al reabrir una UC
  hecha, los veredictos vigentes caducan (``voided_at``), igual que la aceptación de una persona. La
  regla solo cuenta los vigentes: lo revisado tiene que ser el trabajo que se va a fusionar.

El hook merge-guard aplica la misma regla en ``lib/independent-review.mjs`` (una prueba compara las dos).
"""

from __future__ import annotations

import re
from typing import Any

VERDICTS: tuple[str, ...] = ("accepted", "returned")
REASON_MIN = 10
REASON_MAX = 500
#: Lo que se guarda de cada UC en la lista de veredictos (FreeForm) y lo que enseña get_uc.
MAX_VERDICTS = 20
SHOWN_VERDICTS = 5

_ID_RE = re.compile(r"^[A-Za-z0-9_.:@/-]{1,128}$")
AGGRESSIVE = "agresivo"


class ReviewError(ValueError):
    """Un veredicto que no se puede registrar; ``code`` es el del envelope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def client_identity(session_id: Any = "", agent_id: Any = "", agent_type: Any = "") -> dict[str, str]:
    """La identidad del contexto que llama, solo con los campos válidos (identificadores cortos)."""
    out: dict[str, str] = {}
    for key, value in (("session_id", session_id), ("agent_id", agent_id), ("agent_type", agent_type)):
        if isinstance(value, str) and _ID_RE.match(value.strip()):
            out[key] = value.strip()
    return out


def implementer_record(developer_id: str, identity: dict[str, str], at: str) -> dict[str, Any]:
    """Quién arrancó la UC: developer, sesión, agente y cuándo (va en el ``meta`` de la UC)."""
    return {"developer_id": developer_id or None, **identity, "at": at}


def same_context(implementer: dict[str, Any] | None, identity: dict[str, str]) -> bool:
    """True si el que revisa es el mismo contexto que implementó (misma sesión y mismo agente)."""
    if not implementer or not identity.get("session_id") or not implementer.get("session_id"):
        return False
    return (
        implementer.get("session_id") == identity.get("session_id")
        and (implementer.get("agent_id") or "") == (identity.get("agent_id") or "")
    )


def is_independent(implementer: dict[str, Any] | None, identity: dict[str, str]) -> bool:
    """True si el contexto que revisa no es el que implementó.

    Sin identidad (un cliente sin el hook) nunca es independiente. Sin implementador conocido (una UC
    empezada antes de la 6.42.0 o sin el hook) solo un subagente (``agent_id``) cuenta: quien
    implementa suele ser la sesión principal.
    """
    if not identity.get("session_id"):
        return False
    if not implementer or not implementer.get("session_id"):
        return bool(identity.get("agent_id"))
    return not same_context(implementer, identity)


def validate_verdict(verdict: Any, reason: Any) -> tuple[str, str | None]:
    """(veredicto, motivo) válidos, o ReviewError. Devolver una UC exige un motivo de 10 a 500 caracteres."""
    if verdict not in VERDICTS:
        raise ReviewError("INVALID_VERDICT", f"verdict must be one of: {', '.join(VERDICTS)}")
    text = " ".join(str(reason).split()) if isinstance(reason, str) else ""
    if verdict == "returned" and not (REASON_MIN <= len(text) <= REASON_MAX):
        raise ReviewError(
            "INVALID_REASON",
            f"returning a UC needs a reason of {REASON_MIN} to {REASON_MAX} characters: what to fix",
        )
    if text and len(text) > REASON_MAX:
        raise ReviewError("INVALID_REASON", f"reason is longer than {REASON_MAX} characters")
    return verdict, (text or None)


#: Estados de trabajo: volver a uno de ellos desde revisión o hecha caduca los veredictos.
REVIEWED_STATES: frozenset[str] = frozenset({"review", "done"})


def voids_review(old_state: str | None, new_state: str | None) -> bool:
    """True si pasar de ``old_state`` a ``new_state`` caduca los veredictos y la aceptación humana.

    La misma regla que el trigger de la migración 0037 (y que la aceptación humana de 0036): volver a
    trabajo desde revisión o hecha, o reabrir una UC hecha. Pasar de revisión a hecha no caduca nada.
    """
    if old_state == new_state:
        return False
    return (old_state in REVIEWED_STATES and new_state not in REVIEWED_STATES) or (
        old_state == "done" and new_state == "review"
    )


def void_verdicts(verdicts: list[dict[str, Any]], at: str) -> list[dict[str, Any]]:
    """Los veredictos con ``voided_at`` puesto en los que estaban vigentes (FreeForm y el meta)."""
    return [
        {**v, "voided_at": at} if isinstance(v, dict) and not v.get("voided_at") else v
        for v in verdicts or []
    ]


def _latest(verdicts: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [
        v for v in verdicts or []
        if isinstance(v, dict) and v.get("verdict") in VERDICTS and not v.get("voided_at")
    ]
    return max(valid, key=lambda v: str(v.get("at") or "")) if valid else None


def independent_review_result(
    *,
    human_acceptance: dict[str, Any] | None,
    verdicts: list[dict[str, Any]],
    level: str = "",
    backend_type: str = "",
) -> dict[str, Any]:
    """Si la revisión deja fusionar la UC (UC-12402 AC-01, AC-03).

    Devuelve ``{"ok", "reason_code"?, "reason"?}``. ``reason_code``: ``returned`` (devuelta después del
    último visto bueno), ``no_person_acceptance`` (fuera del autopilot «agresivo» hace falta una
    persona) o ``no_independent_verdict``. Solo cuentan los veredictos vigentes (sin ``voided_at``).
    """
    latest = _latest(verdicts)
    if latest is not None and latest.get("verdict") == "returned":
        why = latest.get("reason") or "sin motivo"
        return {"ok": False, "reason_code": "returned", "reason": f"La UC fue devuelta: {why}."}
    if human_acceptance:
        return {"ok": True}
    agent_ok = latest is not None and latest.get("verdict") == "accepted" and bool(latest.get("independent"))
    if (level == AGGRESSIVE or backend_type == "freeform") and agent_ok:
        return {"ok": True}
    if level != AGGRESSIVE and backend_type != "freeform":
        return {
            "ok": False,
            "reason_code": "no_person_acceptance",
            "reason": "Falta que una persona acepte la UC en el panel (fuera del autopilot «agresivo»).",
        }
    return {
        "ok": False,
        "reason_code": "no_independent_verdict",
        "reason": "Falta el veredicto «aceptada» de un evaluador en un contexto distinto del que implementó.",
    }


INDEPENDENT_HOW_TO = (
    "En autopilot «agresivo», lanza un evaluador aislado (subagente AG-09b) que revise los criterios y sus "
    "recibos y registre su veredicto con record_review_verdict. En los demás niveles, una persona acepta la "
    "UC en revisión desde el panel."
)
