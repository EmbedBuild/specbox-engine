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

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
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
        Measure("context_budget", "presupuesto de contexto por subagente", "UC-12210", since="6.38.0"),
        Measure("spec_in_pr", "el PRD cambia en la misma PR que el código", "UC-12211"),
        Measure("spec_quality", "calidad de la spec al empezar una UC", "US-123"),
        Measure("pending_decisions", "marcas «por decidir» al empezar una UC", "US-123"),
        Measure("closing_evidence", "evidencia que pasa al cerrar una UC", "US-124"),
        Measure("independent_review", "revisión independiente antes de fusionar", "US-124"),
        Measure("ac_approval", "criterios aprobados al empezar una UC", "US-125"),
        Measure("drift_gate", "puerta de desviación en el CI local", "US-126"),
        Measure("impact_radius", "radio de impacto del cambio", "US-126"),
        Measure("contract_first", "contrato antes de las pruebas", "US-128"),
        # UC-12215: hoy ya bloquea en los proyectos que se reconocían por su configuración de
        # siempre; los que se reconocen por primera vez (solo el bloque `specbox`) empiezan en «warn».
        Measure("commit_on_main", "commit en main o master", "UC-12215", since="6.37.0"),
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
        if entry and isinstance(entry.get("grandfathered"), dict) and entry["grandfathered"]:
            item["predating_ucs"] = len(entry["grandfathered"])
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


def with_mode(
    raw: Any,
    measure: str,
    mode: str,
    *,
    by: str,
    at: str,
    backend_type: str,
    open_ucs: dict[str, str] | None = None,
) -> tuple[dict, str]:
    """La política guardada con ``measure`` en ``mode``, y el modo que tenía antes.

    Al pasar a «block», ``open_ucs`` ({uc_id: huella}) son las UC abiertas en ese momento: quedan
    como «anteriores a la regla» y la medida no las detiene mientras su huella no cambie (UC-12213).
    """
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
        if old.get("mode") == "block" and old.get("block_since"):
            entry["block_since"] = old["block_since"]
            entry["grandfathered"] = dict(old.get("grandfathered") or {})
        else:
            entry["block_since"] = at
            entry["grandfathered"] = dict(open_ucs or {})
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
    predates: bool = False,
) -> dict[str, Any]:
    """Qué hace una medida con lo que encontró, según su modo en el tablero.

    Devuelve ``{"outcome", "warning"?, "error"?}``:

    * ``pass``          — no encontró nada que señalar;
    * ``off``           — la medida está apagada: ni aviso ni error, la respuesta queda como antes;
    * ``warned``        — en «warn»: un aviso y la operación sigue;
    * ``predates_rule`` — en «block», la UC es anterior a la regla y no cambió: avisa y sigue
      (``predates`` = :func:`predates_rule`, UC-12213);
    * ``skipped``       — en «block» con un salto pendiente: pasa una vez y lo dice;
    * ``blocked``       — en «block»: el error que se devuelve en lugar de hacer la operación.
    """
    if not failed:
        return {"outcome": "pass"}
    mode = mode_of(policy, measure)
    if mode == "off":
        return {"outcome": "off"}
    if mode == "warn":
        return {"outcome": "warned", "warning": warning_for(measure, reason, how_to_continue)}
    if predates:
        note = (
            "Esta UC es anterior a la regla y no ha cambiado, así que la medida no la detiene. Si cambias "
            f"su texto o sus criterios, tendrá que cumplirla. {how_to_continue}"
        )
        return {"outcome": "predates_rule", "warning": warning_for(measure, reason, note)}
    if skip is not None:
        note = f"Bloqueo saltado una vez con motivo: {skip.get('reason', '')}"
        return {"outcome": "skipped", "warning": warning_for(measure, reason, note)}
    return {"outcome": "blocked", "error": enforcement_error(measure, reason, how_to_continue)}


def attach_warnings(response: dict[str, Any], warnings: list[dict]) -> dict[str, Any]:
    """Añade los avisos de las medidas a una respuesta; sin avisos, la deja intacta (AC-03)."""
    if warnings:
        response = {**response, "enforcement_warnings": list(warnings)}
    return response


# ── Antes de endurecer: impacto, lo anterior a la regla y los bloqueos (UC-12213) ──

OPEN_EXCLUDED_STATES = frozenset({"done", "archived"})
OUTCOMES = ("blocked", "passed", "skipped")
WINDOW_DAYS = 14
READINESS_MIN_BLOCKS = 20
READINESS_MAX_SKIP_RATE = 0.10
CORRECTED_WITHIN = timedelta(hours=24)
MAX_LISTED_UCS = 25


def uc_fingerprint(uc: dict[str, Any]) -> str:
    """Huella del texto de una UC y de sus criterios: cambia si cambia lo que la UC pide.

    El estado, las marcas y la evidencia no cuentan: mover o empezar una UC no la saca de
    «anterior a la regla»; reescribir su descripción o un criterio, sí.
    """
    parts = [str(uc.get("name", "")).strip(), str(uc.get("description", "")).strip()]
    for ac in sorted(uc.get("acs") or [], key=lambda a: str(a.get("ac_id", ""))):
        parts.append(f"{ac.get('ac_id', '')}:{str(ac.get('text', '')).strip()}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def predates_rule(raw: Any, measure: str, uc: dict[str, Any]) -> bool:
    """True si la UC estaba abierta cuando ``measure`` pasó a «block» y no ha cambiado desde entonces."""
    entry = _stored(raw)["measures"].get(measure) or {}
    if entry.get("mode") != "block":
        return False
    snapshot = entry.get("grandfathered") or {}
    return bool(uc.get("uc_id")) and snapshot.get(uc["uc_id"]) == uc_fingerprint(uc)


def open_uc_fingerprints(ucs: list[dict[str, Any]]) -> dict[str, str]:
    """{uc_id: huella} de las UC abiertas: lo que queda «anterior a la regla» al pasar a «block»."""
    return {uc["uc_id"]: uc_fingerprint(uc) for uc in ucs if uc.get("uc_id") and uc.get("state") not in OPEN_EXCLUDED_STATES}


_PENDING_MARK = re.compile(r"\[\s*POR DECIDIR", re.IGNORECASE)


def _eval_spec_quality(uc: dict[str, Any]) -> str | None:
    from ..tools._mutation_helpers import validate_ac_text

    acs = uc.get("acs") or []
    if not acs:
        return "No tiene criterios de aceptación."
    bad = [str(ac.get("ac_id", "?")) for ac in acs if validate_ac_text(str(ac.get("text", "")))]
    return f"{len(bad)} criterio(s) no pasan la calidad: {', '.join(bad[:6])}." if bad else None


def _eval_pending_decisions(uc: dict[str, Any]) -> str | None:
    where = []
    if _PENDING_MARK.search(str(uc.get("description", ""))):
        where.append("la descripción")
    where += [str(ac.get("ac_id", "?")) for ac in uc.get("acs") or [] if _PENDING_MARK.search(str(ac.get("text", "")))]
    return f"Quedan marcas «por decidir» en {', '.join(where[:6])}." if where else None


def _eval_closing_evidence(uc: dict[str, Any]) -> str | None:
    if uc.get("state") != "review":
        return None  # solo detiene al cerrar: lo que está en revisión es lo que se cerraría
    # FreeForm guarda la evidencia en comentarios que no viajan con el tablero: ahí solo cuenta «hecho».
    known = uc.get("evidence_known", True)
    sin = [
        str(ac.get("ac_id", "?"))
        for ac in uc.get("acs") or []
        if not ac.get("done") or (known and not ac.get("evidence"))
    ]
    return f"{len(sin)} criterio(s) sin hecho o sin evidencia: {', '.join(sin[:6])}." if sin else None


#: Lo que cada medida detendría, medido con lo que el tablero sabe de una UC. Las que dependen del
#: repositorio, de la sesión o de algo que aún no existe no se pueden medir aquí, y el informe lo dice.
IMPACT_EVALUATORS = {
    "spec_quality": _eval_spec_quality,
    "pending_decisions": _eval_pending_decisions,
    "closing_evidence": _eval_closing_evidence,
}
NOT_MEASURABLE = {
    "context_budget": "Depende de la sesión de Claude Code, no del tablero.",
    "spec_in_pr": "Depende de la PR y del repositorio, no del tablero.",
    "independent_review": "Depende del veredicto de revisión, que aún no guarda el tablero (US-124).",
    "ac_approval": "La aprobación de criterios llega con UC-12502; hasta entonces no hay qué medir.",
    "drift_gate": "Depende del CI local del repositorio, no del tablero.",
    "impact_radius": "Depende del diff del repositorio, no del tablero.",
    "contract_first": "Depende del orden de los cambios en el repositorio, no del tablero.",
    "commit_on_main": "Depende de la rama del commit, no del tablero.",
}


def _parse_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def event_stats(events: list[dict[str, Any]], measure: str, *, now: datetime, days: int = WINDOW_DAYS) -> dict[str, Any]:
    """Bloqueos de una medida en la ventana y cómo terminó cada uno (UC-12213 AC-04).

    Eventos ``{measure, uc_id, outcome, at, reason?}`` con ``outcome`` = blocked, passed o skipped.
    Un bloqueo termina «corregido» si la misma medida pasa en la misma UC en las 24 h siguientes sin
    un salto de por medio, y «saltado» si hay un salto con motivo en esa UC después del bloqueo.
    El porcentaje de saltos es saltos / bloqueos de la ventana.
    """
    since = now - timedelta(days=days)
    own = sorted(
        (e for e in events if e.get("measure") == measure and _parse_at(e.get("at"))),
        key=lambda e: _parse_at(e["at"]),
    )
    window = [e for e in own if _parse_at(e["at"]) >= since]
    blocks = [e for e in window if e.get("outcome") == "blocked"]
    skips = [e for e in window if e.get("outcome") == "skipped"]
    corrected = skipped = 0
    for block in blocks:
        at = _parse_at(block["at"])
        later = [e for e in own if e.get("uc_id") == block.get("uc_id") and _parse_at(e["at"]) > at]
        first = next((e for e in later if e.get("outcome") in ("passed", "skipped")), None)
        if first and first["outcome"] == "skipped":
            skipped += 1
        elif first and _parse_at(first["at"]) - at <= CORRECTED_WITHIN:
            corrected += 1
    first_block = next((e for e in own if e.get("outcome") == "blocked"), None)
    rate = round(len(skips) / len(blocks), 4) if blocks else None
    return {
        "window_days": days,
        "blocks": len(blocks),
        "corrected": corrected,
        "skipped": skipped,
        "open": len(blocks) - corrected - skipped,
        "skips": len(skips),
        "skip_rate": rate,
        "first_block_at": first_block["at"] if first_block else None,
    }


def impact_report(
    raw: Any, ucs: list[dict[str, Any]], *, backend_type: str, events: list[dict[str, Any]] | None = None,
    now: datetime, measures: list[str] | None = None,
) -> dict[str, Any]:
    """Cuántas UC abiertas detendría cada medida en «block» y por qué, sin cambiar nada (AC-01).

    Para cada medida: el modo, si se puede medir desde el tablero, las UC que detendría (con el
    motivo), cuántas de ellas son «anteriores a la regla» y quedan a salvo mientras no cambien, y
    los bloqueos de los últimos 14 días con su porcentaje de saltos (AC-04).
    """
    policy = effective_policy(raw, backend_type=backend_type)
    open_ucs = [uc for uc in ucs if uc.get("state") not in OPEN_EXCLUDED_STATES]
    report: dict[str, Any] = {}
    for key in measures or list(MEASURES):
        mode = mode_of(policy, key)
        item: dict[str, Any] = {"mode": mode, "label": MEASURES[key].label}
        evaluate = IMPACT_EVALUATORS.get(key)
        if evaluate is None:
            item.update(measurable=False, why_not=NOT_MEASURABLE.get(key, "No se puede medir desde el tablero."))
        else:
            hits = []
            protected = 0
            for uc in open_ucs:
                reason = evaluate(uc)
                if not reason:
                    continue
                # Si pasa a «block» ahora, todas las abiertas quedan anteriores a la regla.
                safe = predates_rule(raw, key, uc) if mode == "block" else True
                protected += 1 if safe else 0
                hits.append({"uc_id": uc["uc_id"], "state": uc.get("state"), "reason": reason, "predates_rule": safe})
            item.update(
                measurable=True,
                would_block=len(hits),
                predates_rule=protected,
                blocks_now=len(hits) - protected if mode == "block" else 0,
                ucs=hits[:MAX_LISTED_UCS],
            )
            if len(hits) > MAX_LISTED_UCS:
                item["more_ucs"] = len(hits) - MAX_LISTED_UCS
        item["events"] = event_stats(events or [], key, now=now)
        report[key] = item
    return {
        "backend_type": backend_type,
        "origin": policy["origin"],
        "open_ucs": len(open_ucs),
        "measures": report,
        "note": (
            "would_block = UC abiertas que la medida detendría en «block»; predates_rule = cuántas de "
            "ellas son anteriores a la regla y no se detienen mientras su texto o sus criterios no cambien. "
            "El informe no cambia nada del tablero."
        ),
    }


def confirm_token(board: str, measure: str, mode: str, current: str, impact: dict[str, Any]) -> str:
    """El código que la segunda llamada de set_enforcement_mode tiene que traer para pasar a «block».

    Cambia si cambia el impacto: confirmar un informe viejo no vale.
    """
    digest = json.dumps(
        [board, measure, mode, current, impact.get("would_block"), impact.get("predates_rule")], sort_keys=True
    )
    return hashlib.sha256(digest.encode("utf-8")).hexdigest()[:12]


def readiness(events: list[dict[str, Any]], *, now: datetime) -> dict[str, Any]:
    """Qué medidas podrían pasar a «block» por defecto en los proyectos nuevos (UC-12213 AC-05).

    Regla: en los tableros de EmbedBuild, bloqueos durante al menos 14 días seguidos (el primero, hace
    14 días o más), al menos 20 bloqueos en los últimos 14 días y saltos en el 10 % o menos. Con menos
    de 20 bloqueos no hay dato. Es una lectura: el valor por defecto lo cambia una versión del engine
    con su codename, nunca esta función.
    """
    out: dict[str, Any] = {}
    for key, measure in MEASURES.items():
        stats = event_stats(events, key, now=now)
        first = _parse_at(stats["first_block_at"]) if stats["first_block_at"] else None
        long_enough = bool(first and now - first >= timedelta(days=WINDOW_DAYS))
        enough = stats["blocks"] >= READINESS_MIN_BLOCKS
        low_skips = stats["skip_rate"] is not None and stats["skip_rate"] <= READINESS_MAX_SKIP_RATE
        if not enough:
            verdict = f"Sin dato: {stats['blocks']} bloqueos en 14 días (hacen falta {READINESS_MIN_BLOCKS})."
        elif not long_enough:
            verdict = "Aún no lleva 14 días seguidos bloqueando."
        elif not low_skips:
            verdict = f"Demasiados saltos: {stats['skip_rate']:.0%} (máximo {READINESS_MAX_SKIP_RATE:.0%})."
        else:
            verdict = "Candidata a «block» por defecto en los proyectos nuevos."
        out[key] = {
            **stats,
            "new_default": measure.new_default,
            "candidate": enough and long_enough and low_skips,
            "verdict": verdict,
        }
    return out
