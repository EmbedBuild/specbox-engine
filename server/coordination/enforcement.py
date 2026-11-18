"""Las medidas de EP-20 tienen un modo por proyecto (US-122 · UC-12212).

EP-20 («Lo que la spec pide, el motor lo impone») añade medidas que pueden detener el trabajo:
la calidad de la spec al empezar una UC, la evidencia al cerrarla, la revisión independiente…
Un proyecto que ya existía no puede amanecer bloqueado por una regla que no conocía, así que cada
medida tiene un modo por proyecto:

* ``off``   — la medida no mira nada: la respuesta queda como antes de que existiera.
* ``warn``  — mira, avisa en la respuesta y la operación sigue igual.
* ``block`` — detiene la operación con un error que dice la medida, el motivo y cómo seguir.

La política vive con el tablero, porque el MCP es remoto y no lee el disco del cliente (US-86):

* native: ``projects.meta.enforcement`` (lo escribe el alta del proyecto con ``origin: "new"``);
* FreeForm: ``doc/tracking/policy.json``, junto a ``items.json``;
* Trello y Plane: nada que guardar; «warn» como máximo, y la respuesta lo dice (D20).

Un tablero sin política es un tablero que ya existía: todas sus medidas en «warn». Un tablero
nuevo toma el modo de proyecto nuevo de cada medida, que nace en «warn» y solo pasa a «block» en
una versión del engine cuando supera la prueba de UC-12213 (≤10 % de saltos en 14 días con al menos
20 bloqueos). Ninguna medida pasa a «block» en un proyecto sin que una persona lo cambie.

Este módulo es puro: lo usan las tools (``server/tools/enforcement.py``), las medidas cuando se
implementen y sus pruebas. Los hooks tienen su copia del catálogo en
``.claude/hooks/lib/enforcement-policy.mjs``; una prueba comprueba que coinciden.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

MODES: tuple[str, ...] = ("off", "warn", "block")
SCHEMA = 1
POLICY_FILE = "policy.json"
ORIGINS = ("new", "existing")
# Trello y Plane no guardan la política: ninguna medida pasa de «warn» (D20).
CAPPED_BACKENDS = frozenset({"trello", "plane"})

UC_ID = re.compile(r"^UC-[0-9]{1,6}[a-z]?$")
REASON_MIN = 10
REASON_MAX = 500
MAX_SKIPS = 200


@dataclass(frozen=True)
class Measure:
    """Una medida de EP-20 que puede detener el trabajo."""

    key: str
    label: str
    uc: str
    # Modo de un proyecto nuevo. Cambia a «block» solo con la prueba de UC-12213 y en una
    # versión del engine con su codename; un proyecto que ya existía siempre empieza en «warn».
    new_default: str = "warn"
    # Versión del engine en la que la medida empieza a comprobar algo. None = declarada, aún sin
    # implementar: su modo se guarda, pero todavía no detiene ni avisa de nada.
    since: str | None = None


MEASURES: dict[str, Measure] = {
    m.key: m
    for m in (
        Measure("context_budget", "presupuesto de contexto por subagente", "UC-12210"),
        Measure("spec_in_pr", "el PRD cambia en la misma PR que el código", "UC-12211"),
        Measure("spec_quality", "calidad de la spec al empezar una UC", "US-123"),
        Measure("pending_decisions", "marcas «por decidir» al empezar una UC", "US-123"),
        Measure("closing_evidence", "evidencia que pasa al cerrar una UC", "US-124"),
        Measure("independent_review", "revisión independiente antes de fusionar", "US-124"),
        Measure("ac_approval", "criterios aprobados al empezar una UC", "US-125"),
        Measure("drift_gate", "puerta de desviación en el CI local", "US-126"),
        Measure("impact_radius", "radio de impacto del cambio", "US-126"),
        Measure("contract_first", "contrato antes de las pruebas", "US-128"),
    )
}


class PolicyError(ValueError):
    """Una petición que no se puede aplicar a la política; ``code`` es el código del envelope."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ── Lectura ─────────────────────────────────────────────────────────


def new_policy() -> dict[str, Any]:
    """La política que guarda un tablero creado a partir de esta versión."""
    return {"schema": SCHEMA, "origin": "new", "measures": {}, "skips": []}


def _stored(raw: Any) -> dict[str, Any]:
    """La política guardada, saneada; un tablero sin ella cuenta como «existing»."""
    if not isinstance(raw, dict):
        return {"schema": SCHEMA, "origin": "existing", "measures": {}, "skips": []}
    origin = raw.get("origin") if raw.get("origin") in ORIGINS else "existing"
    measures = raw.get("measures") if isinstance(raw.get("measures"), dict) else {}
    skips = [s for s in raw.get("skips") or [] if isinstance(s, dict)] if isinstance(raw.get("skips"), list) else []
    clean: dict[str, Any] = {}
    for key, entry in measures.items():
        if key in MEASURES and isinstance(entry, dict) and entry.get("mode") in MODES:
            clean[key] = dict(entry)
    return {"schema": SCHEMA, "origin": origin, "measures": clean, "skips": skips}


def effective_policy(raw: Any, *, backend_type: str) -> dict[str, Any]:
    """El modo que rige cada medida en un tablero, con de dónde sale.

    ``raw`` es lo guardado (``projects.meta.enforcement`` o ``policy.json``), o None.
    """
    stored = _stored(raw)
    capped_backend = backend_type in CAPPED_BACKENDS
    out: dict[str, Any] = {}
    for key, measure in MEASURES.items():
        entry = stored["measures"].get(key)
        if entry:
            mode, source = entry["mode"], "set"
        else:
            mode = measure.new_default if stored["origin"] == "new" else "warn"
            source = "default"
        capped = capped_backend and mode == "block"
        if capped:
            mode = "warn"
        item: dict[str, Any] = {
            "mode": mode,
            "source": source,
            "label": measure.label,
            "uc": measure.uc,
            "active": measure.since is not None,
        }
        if capped:
            item["capped"] = True
        for field in ("set_by", "set_at", "block_since"):
            if entry and entry.get(field):
                item[field] = entry[field]
        out[key] = item
    policy: dict[str, Any] = {
        "schema": SCHEMA,
        "origin": stored["origin"],
        "backend_type": backend_type,
        "max_mode": "warn" if capped_backend else "block",
        "measures": out,
        "pending_skips": len(stored["skips"]),
    }
    if capped_backend:
        policy["notice"] = (
            f"Con {backend_type.capitalize()}, SpecBox avisa pero no detiene el trabajo: las medidas "
            "quedan en «warn» como máximo. Para que una medida pueda bloquear, el proyecto tiene que "
            "estar en native o en FreeForm."
        )
    elif stored["origin"] == "existing":
        policy["notice"] = (
            "Este tablero ya existía antes de las medidas de EP-20: todas empiezan en «warn» y "
            "ninguna pasa a «block» sin que una persona lo cambie con set_enforcement_mode."
        )
    return policy


def mode_of(policy: dict[str, Any], measure: str) -> str:
    """El modo de una medida en una política efectiva («warn» si no la conoce)."""
    entry = (policy.get("measures") or {}).get(measure) or {}
    return entry.get("mode") if entry.get("mode") in MODES else "warn"


# ── Cambios ─────────────────────────────────────────────────────────


def _known(measure: str) -> Measure:
    if measure not in MEASURES:
        raise PolicyError(
            "UNKNOWN_MEASURE",
            f"No hay ninguna medida {measure!r}. Las medidas son: {', '.join(MEASURES)}.",
        )
    return MEASURES[measure]


def with_mode(raw: Any, measure: str, mode: str, *, by: str, at: str, backend_type: str) -> tuple[dict, str]:
    """La política guardada con ``measure`` en ``mode``, y el modo que tenía antes."""
    _known(measure)
    if mode not in MODES:
        raise PolicyError("INVALID_MODE", f"El modo tiene que ser {', '.join(MODES)}; llegó {mode!r}.")
    if backend_type in CAPPED_BACKENDS:
        raise PolicyError(
            "NOT_SUPPORTED",
            f"Con {backend_type.capitalize()} la política no se guarda: las medidas quedan en «warn» "
            "como máximo. Para cambiar un modo, el proyecto tiene que estar en native o en FreeForm.",
        )
    previous = mode_of(effective_policy(raw, backend_type=backend_type), measure)
    stored = _stored(raw)
    entry: dict[str, Any] = {"mode": mode, "set_by": by, "set_at": at}
    old = stored["measures"].get(measure) or {}
    if mode == "block":
        entry["block_since"] = old.get("block_since") if old.get("mode") == "block" and old.get("block_since") else at
    stored["measures"][measure] = entry
    return stored, previous


def validate_skip(measure: str, uc_id: str, reason: str) -> str:
    """El motivo saneado de un salto, o PolicyError."""
    _known(measure)
    if not UC_ID.match(uc_id or ""):
        raise PolicyError("INVALID_UC_ID", "uc_id tiene que ser el id de la UC, como «UC-12212».")
    text = " ".join(str(reason or "").split())
    if len(text) < REASON_MIN:
        raise PolicyError(
            "REASON_REQUIRED",
            f"Saltar un bloqueo exige un motivo de al menos {REASON_MIN} caracteres: por qué esta UC "
            "puede seguir sin cumplir la medida.",
        )
    if len(text) > REASON_MAX:
        raise PolicyError("REASON_TOO_LONG", f"El motivo tiene que caber en {REASON_MAX} caracteres.")
    from ..tools._mutation_helpers import detect_ac_exposure

    if any("credential" in tag for tag in detect_ac_exposure(text)):
        raise PolicyError("SENSITIVE_DATA", "El motivo menciona credenciales: descríbelo sin ellas.")
    return text


def with_skip(
    raw: Any, measure: str, uc_id: str, reason: str, *, by: str, at: str, backend_type: str
) -> tuple[dict, dict]:
    """La política guardada con un salto pendiente de ``measure`` en ``uc_id``, y ese salto.

    Solo se salta lo que bloquea: con la medida en «warn» u «off» no hay nada que saltar.
    """
    text = validate_skip(measure, uc_id, reason)
    mode = mode_of(effective_policy(raw, backend_type=backend_type), measure)
    if mode != "block":
        raise PolicyError(
            "NOTHING_TO_SKIP",
            f"La medida {measure} está en «{mode}» en este tablero: no detiene el trabajo, así que no "
            "hay bloqueo que saltar.",
        )
    stored = _stored(raw)
    skip = {"measure": measure, "uc_id": uc_id, "reason": text, "by": by, "at": at}
    stored["skips"] = [*stored["skips"], skip][-MAX_SKIPS:]
    return stored, skip


def take_skip(raw: Any, measure: str, uc_id: str) -> tuple[dict, dict | None]:
    """Gasta el salto pendiente más antiguo de ``measure`` en ``uc_id`` (pasa una vez)."""
    stored = _stored(raw)
    for i, skip in enumerate(stored["skips"]):
        if skip.get("measure") == measure and skip.get("uc_id") == uc_id:
            stored["skips"] = stored["skips"][:i] + stored["skips"][i + 1 :]
            return stored, skip
    return stored, None


# ── Lo que ve el cliente ────────────────────────────────────────────


def enforcement_error(measure: str, reason: str, how_to_continue: str, *, code: str = "ENFORCEMENT_BLOCKED") -> dict:
    """El error de una medida que detiene el trabajo (UC-12212 AC-06).

    El texto de ``error`` lleva la medida, el motivo y cómo seguir, para que un cliente con skills
    anteriores, que no conoce los campos nuevos, enseñe igualmente qué lo detuvo.
    """
    label = MEASURES[measure].label if measure in MEASURES else measure
    return {
        "success": False,
        "code": code,
        "measure": measure,
        "reason": reason,
        "how_to_continue": how_to_continue,
        "error": (
            f"SpecBox detuvo la operación por la medida «{label}» ({measure}). Motivo: {reason} "
            f"Cómo seguir: {how_to_continue}"
        ),
    }


def policy_error(err: PolicyError, *, measure: str = "") -> dict:
    """Un PolicyError como envelope con el mismo formato que los demás errores nuevos."""
    out: dict[str, Any] = {"success": False, "code": err.code, "error": str(err)}
    if measure:
        out["measure"] = measure
    return out


def warning_for(measure: str, reason: str, how_to_continue: str) -> dict:
    """El aviso de una medida en «warn»: la operación sigue y la respuesta lo cuenta."""
    label = MEASURES[measure].label if measure in MEASURES else measure
    return {
        "measure": measure,
        "reason": reason,
        "how_to_continue": how_to_continue,
        "message": f"Aviso de SpecBox («{label}», {measure}): {reason} {how_to_continue}",
    }


def check(
    policy: dict[str, Any],
    measure: str,
    *,
    failed: bool,
    reason: str = "",
    how_to_continue: str = "",
    skip: dict | None = None,
) -> dict[str, Any]:
    """Qué hace una medida con lo que encontró, según su modo en el tablero.

    Devuelve ``{"outcome", "warning"?, "error"?}``:

    * ``pass``    — no encontró nada que señalar;
    * ``off``     — la medida está apagada: ni aviso ni error, la respuesta queda como antes;
    * ``warned``  — en «warn»: un aviso y la operación sigue;
    * ``skipped`` — en «block» con un salto pendiente: pasa una vez y lo dice;
    * ``blocked`` — en «block»: el error que se devuelve en lugar de hacer la operación.
    """
    if not failed:
        return {"outcome": "pass"}
    mode = mode_of(policy, measure)
    if mode == "off":
        return {"outcome": "off"}
    if mode == "warn":
        return {"outcome": "warned", "warning": warning_for(measure, reason, how_to_continue)}
    if skip is not None:
        note = f"Bloqueo saltado una vez con motivo: {skip.get('reason', '')}"
        return {"outcome": "skipped", "warning": warning_for(measure, reason, note)}
    return {"outcome": "blocked", "error": enforcement_error(measure, reason, how_to_continue)}


def attach_warnings(response: dict[str, Any], warnings: list[dict]) -> dict[str, Any]:
    """Añade los avisos de las medidas a una respuesta; sin avisos, la deja intacta (AC-03)."""
    if warnings:
        response = {**response, "enforcement_warnings": list(warnings)}
    return response
