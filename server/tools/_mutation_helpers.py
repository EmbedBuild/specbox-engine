"""Internal helpers shared by Tier 1-4 mutation tool modules.

Not registered as MCP tools. Imported by:
- server/tools/spec_mutations.py (Tier 1)
- server/tools/milestone_management.py (Tier 2, future)
- server/tools/board_operations.py (Tier 3, future)
- server/tools/acceptance_automation.py (Tier 4, future)

See doc/design/v5.23.0-full-mutations.md — section "Shared helpers".
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..spec_backend import ChecklistItemDTO, ItemDTO, SpecBackend, parse_item_id

# ── Constants ────────────────────────────────────────────────────────

MILESTONES: tuple[str, ...] = ("H1", "H2", "H3", "H4")
LINK_TYPES: tuple[str, ...] = (
    "absorbs",
    "blocks",
    "depends_on",
    "supersedes",
    "related_to",
)
VERDICT_TYPES: tuple[str, ...] = ("ACCEPTED", "CONDITIONAL", "REJECTED")
DEFAULT_MILESTONE_TARGETS: dict[str, float] = {
    "H1": 0.30,
    "H2": 0.25,
    "H3": 0.25,
    "H4": 0.20,
}


def utc_now_iso() -> str:
    """ISO 8601 UTC timestamp with seconds precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Validators ───────────────────────────────────────────────────────


def validate_milestone(value: str) -> tuple[bool, str | None]:
    """Check if value is a valid milestone key."""
    if value in MILESTONES:
        return True, None
    return False, f"Milestone must be one of {MILESTONES}, got {value!r}"


def validate_link_type(value: str) -> tuple[bool, str | None]:
    """Check if value is a valid UC link type."""
    if value in LINK_TYPES:
        return True, None
    return False, f"Link type must be one of {LINK_TYPES}, got {value!r}"


def validate_satellite(
    value: str, settings_path: Path | None
) -> tuple[bool, str | None]:
    """Check that `value` is a declared satellite key in orchestrator settings.

    If settings_path is None or does not exist, any non-empty string is
    accepted (freeform projects without a multirepo config).
    """
    if not value:
        return False, "Satellite key must be a non-empty string"

    if settings_path is None or not Path(settings_path).exists():
        return True, None

    try:
        data = json.loads(Path(settings_path).read_text())
    except (OSError, json.JSONDecodeError) as e:
        return False, f"Failed to read settings at {settings_path}: {e}"

    satellites = (
        data.get("multirepo", {}).get("satellites", {}) if isinstance(data, dict) else {}
    )
    if not isinstance(satellites, dict) or not satellites:
        # No satellites declared → accept (backwards-compatible)
        return True, None

    if value in satellites:
        return True, None
    declared = sorted(satellites.keys())
    return False, f"Satellite {value!r} not declared in settings; declared: {declared}"


#: US-33/UC-3304 — señales de RESULTADO OBSERVABLE.
#:
#: Un AC es verificable cuando afirma algo que se puede ir a mirar. Verbos en
#: 3ª persona del indicativo describiendo lo que el sistema hace: es como se
#: redacta un criterio en este ecosistema y como está redactada la mayoría del
#: board. La regla anterior no los reconocía, y por eso penalizaba justo la
#: redacción que pretendía fomentar.
_OUTCOME_VERBS = (
    "devuelve", "muestra", "marca", "crea", "borra", "elimina", "aparece",
    "queda", "falla", "bloquea", "registra", "preserva", "rechaza", "emite",
    "persiste", "revierte", "cierra", "resuelve", "expone", "cubre",
    "verifica", "lanza", "responde", "incluye", "contiene", "existe",
    "aplica", "propaga", "detecta", "avisa", "reporta", "genera", "escribe",
    "guarda", "actualiza", "asigna", "oculta", "returns", "shows",
    # Añadidos tras medir contra el board real: cada uno venía de un AC
    # perfectamente verificable que la lista anterior marcaba por no conocer su
    # verbo. Es la prueba de que una lista léxica tiene cola — ver el aviso del
    # docstring.
    "arroja", "produce", "refleja", "respeta", "recarga", "renderiza",
    "contradice", "adjunta", "selecciona", "impide", "conserva",
)

#: DELIBERADAMENTE FUERA: `tiene`, `deja`, `sigue`, `permite`, `mantiene`,
#: `vuelve`, `pasa`, `abre`, `termina`, `arranca`, `lee`.
#:
#: Incluirlos subía la aprobación del board del 98,17 % al 99,63 % (de 10 AC
#: marcados a 2), pero son verbos tan comunes en español que aparecen en casi
#: cualquier frase: la señal deja de ser «afirma un resultado observable» y pasa
#: a ser «es una oración en español». Un gate que no marca nada no es un gate, y
#: el sobreajuste no sería a este board sino a cualquiera.
#:
#: El precio son ~10 marcados, algunos falsos positivos. Se paga a gusto:
#: equivocarse pidiendo una reescritura es mucho más barato que equivocarse
#: aprobando lo que no se puede verificar.

#: Calificativos subjetivos: describen una impresión, no un hecho comprobable.
#: Solo disparan cuando la frase NO aporta ninguna medición — «rápida» es vago,
#: «responde en menos de 200 ms» no lo es aunque también diga «rápida».
_SUBJECTIVE_TERMS = (
    "rápida", "rapida", "rápido", "rapido", "veloz", "lenta", "lento",
    "intuitiv", "fácil", "facil", "sencill", "amigable", "cómod", "comod",
    "buena experiencia", "mala experiencia", "óptim", "optim", "eficiente",
    "moderno", "moderna", "atractiv", "bonit", "elegante", "robust",
    "escalable", "user friendly", "fluid",
)

#: Una medición concreta: comparador, cifra, porcentaje o unidad de tiempo.
#:
#: El `(?<![A-Za-z\d-])` NO es cosmético. Sin él, el «01» de `AC-01` cuenta como
#: medición — y casi todos los AC del board llevan su propio id en el texto. El
#: efecto medido: «AC-05: la app es rápida» pasaba limpio, porque el id redimía
#: al calificativo subjetivo. Eso habría convertido el gate en el sello de goma
#: que este mismo cambio venía a evitar. Una cifra solo cuenta como medición si
#: no va pegada a un identificador. El `\\d` del lookbehind tampoco sobra: sin
#: él la regex bloquea el «0» de `AC-05` pero reengancha en el «5».
_MEASUREMENT_RE = re.compile(
    r"[<>]=?\s*\d"
    r"|(?<![A-Za-z\d-])\d+\s*%"
    r"|(?<![A-Za-z\d-])\d+\s*(ms|s|seg|segundos|min|h|kb|mb|gb)\b"
    r"|(?<![A-Za-z\d-])\d+(?![\w-])"
)

#: Identificador de código: backticks, snake_case, CamelCase, ruta con
#: extensión, constante en mayúsculas, o llamada con paréntesis.
_CODE_REF_RE = re.compile(
    r"`[^`]+`|\b[a-z_]+_[a-z_]+\b|\b[a-zA-Z][a-z]+[A-Z]\w*\b|\b\w+\.(py|ts|tsx|sql|mjs|json|yaml|md)\b"
    r"|\b[A-Z][A-Z0-9_]{3,}\b|\b\w+\(\)"
)


def validate_ac_text(text: str) -> list[str]:
    """Return a list of issue tags for an AC text. Empty list = passes.

    US-33/UC-3304 — el veredicto estaba INVERTIDO donde importaba.

    La regla anterior marcaba `not_testable` todo AC sin Gherkin ni una de siete
    cadenas (`debe`, `must`, un comparador, un porcentaje). Medido sobre los 537
    AC del board del orquestador: aprobaba el 30,54 %, y el **100 %** de los
    fallos eran de ese único tipo — ni un solo `too_short`, ni un solo `vague`.
    Un gate de tres reglas del que dos nunca disparan es una sola regla mal
    calibrada con dos adornos.

    Lo grave no era la tasa sino la dirección. Ejecutado contra casos concretos::

        "la app debe ser rápida"                        → PASABA
        "mark_ac preserva el valor de internal al ..."  → FALLABA

    La segunda es un AC real de esta misma US. La primera no tiene nada que
    medir. El gate empujaba a **redactar para el linter**: meter un «debe»
    decorativo aprobaba sin mejorar el criterio.

    Ahora se responden dos preguntas SEPARADAS, que es lo que pide AC-04 —
    dos AC con problemas distintos dejan de recibir la misma etiqueta:

    - ``no_observable_outcome``: no afirma nada que se pueda ir a mirar.
    - ``subjective_language``: se apoya en un calificativo de impresión sin
      aportar ninguna medición.

    `not_testable` se sigue emitiendo junto a la etiqueta específica para no
    romper informes ni lectores humanos; se retira en el release siguiente.
    Nada en el código ramifica sobre su valor (el único consumidor es
    `validate_ac_quality`, que las pasa como strings al skill).

    LO QUE ESTO SIGUE SIN SER, y conviene decirlo
    ---------------------------------------------
    Sigue siendo un heurístico **léxico**, no un clasificador de testabilidad.
    `_OUTCOME_VERBS` es una lista, y toda lista tiene cola: al medirla contra
    los 547 AC reales del board aparecieron criterios perfectamente
    verificables marcados solo porque su verbo no estaba dentro («arroja»,
    «produce», «refleja», «respeta»...). Se añadieron, pero el siguiente AC con
    un verbo nuevo volverá a fallar.

    La diferencia con la regla anterior no es que ésta sea infalible: es que
    falla en la dirección correcta y en un orden de magnitud menos de casos
    (de 373 falsos positivos a un puñado), y que ya NO aprueba lo que no tiene
    nada que medir. Un gate que se equivoca aprobando «debe ser rápida» es
    peor que uno que se equivoca marcando «arroja cifras idénticas»: el primero
    deja pasar lo que no se puede verificar, el segundo solo pide una
    reescritura.

    Por eso el check **avisa y no bloquea** el Definition Quality Gate.

    Rules:
    - `too_short`: text < 10 chars
    - `vague`: text < 20 chars (but >= 10)
    - `no_observable_outcome`: no Gherkin, ni flecha condición→resultado, ni
      verbo de resultado, ni medición, ni identificador de código, ni literal
      entrecomillado, ni `debe`/`must`
    - `subjective_language`: calificativo subjetivo sin medición que lo respalde
    - `not_testable`: alias de compatibilidad — se emite si dispara cualquiera
      de las dos anteriores
    """
    issues: list[str] = []
    stripped = (text or "").strip()
    if len(stripped) < 10:
        issues.append("too_short")
    elif len(stripped) < 20:
        issues.append("vague")

    lower = stripped.lower()

    has_gherkin = any(kw in lower for kw in ("dado ", "cuando ", "entonces "))
    # La flecha es la forma canónica de «condición → resultado» en este board.
    has_arrow = "→" in stripped or "->" in stripped
    has_outcome_verb = any(v in lower for v in _OUTCOME_VERBS)
    has_measurement = bool(_MEASUREMENT_RE.search(lower))
    has_code_ref = bool(_CODE_REF_RE.search(stripped))
    has_quoted = bool(re.search(r"['\"«][^'\"»]{2,}['\"»]", stripped))
    has_obligation = bool(re.search(r"\bdebe\b|\bmust\b", lower))

    observable = (
        has_gherkin
        or has_arrow
        or has_outcome_verb
        or has_measurement
        or has_code_ref
        or has_quoted
        or has_obligation
    )
    if not observable:
        issues.append("no_observable_outcome")

    # La medición es lo que redime a un calificativo subjetivo: «rápida» es una
    # impresión, «responde en menos de 200 ms» es un hecho. Por eso `debe` NO
    # cuenta aquí — era precisamente el token que dejaba pasar «debe ser rápida».
    if any(t in lower for t in _SUBJECTIVE_TERMS) and not has_measurement:
        issues.append("subjective_language")

    if "no_observable_outcome" in issues or "subjective_language" in issues:
        issues.append("not_testable")  # alias de compatibilidad, se retira en el próximo release

    return issues


# ── Item finders (thin wrappers over list_items) ─────────────────────


async def find_uc(
    backend: SpecBackend, board_id: str, uc_id: str
) -> ItemDTO | None:
    """Find a UC by its spec id (e.g. 'UC-001')."""
    return await backend.find_item_by_field(board_id, "uc_id", uc_id)


async def find_us(
    backend: SpecBackend, board_id: str, us_id: str
) -> ItemDTO | None:
    """Find a US by its spec id (e.g. 'US-01')."""
    return await backend.find_item_by_field(board_id, "us_id", us_id)


async def find_ac(
    backend: SpecBackend, board_id: str, uc_item_id: str, ac_id: str
) -> ChecklistItemDTO | None:
    """Find an AC on a UC by its spec id (e.g. 'AC-01')."""
    try:
        acs = await backend.get_acceptance_criteria(board_id, uc_item_id)
    except Exception:
        return None
    for ac in acs:
        if ac.id == ac_id:
            return ac
    return None


async def find_max_uc_number(backend: SpecBackend, board_id: str) -> int:
    """Scan all items and return the max UC numeric suffix (e.g. 27 for UC-027).

    Returns 0 if no UCs exist.
    """
    items = await backend.list_items(board_id)
    max_num = 0
    for item in items:
        uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
        if not uc_id or not uc_id.startswith("UC-"):
            continue
        try:
            num = int(uc_id.split("-")[1])
        except (IndexError, ValueError):
            continue
        if num > max_num:
            max_num = num
    return max_num


def next_ac_id(existing: list[ChecklistItemDTO]) -> str:
    """Compute the next AC-NN id from a list of existing ACs."""
    max_num = 0
    for ac in existing:
        if not ac.id or not ac.id.startswith("AC-"):
            continue
        try:
            num = int(ac.id.split("-")[1])
        except (IndexError, ValueError):
            continue
        if num > max_num:
            max_num = num
    return f"AC-{max_num + 1:02d}"


def format_uc_id(number: int) -> str:
    """Format a UC number as 'UC-NNN' (zero-padded to 3 digits)."""
    return f"UC-{number:03d}"


# ── Meta merge (only-non-None semantics) ─────────────────────────────


def merge_meta(
    existing: dict[str, Any] | None, updates: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Merge `updates` into `existing`, returning (merged, changed_fields).

    Only keys with non-None values in `updates` are applied. A key is
    listed in `changed_fields` only if the new value differs from the
    existing value (list/dict equality is deep via `==`).
    """
    merged: dict[str, Any] = dict(existing or {})
    changed: list[str] = []
    for key, new_val in updates.items():
        if new_val is None:
            continue
        old_val = merged.get(key)
        if old_val != new_val:
            merged[key] = new_val
            changed.append(key)
    return merged, changed


# ── AC classification (for estimate_from_ac, validate_ac_quality) ────


_SIMPLE_KEYWORDS = ("valida", "muestra", "lista", "abre", "renderiza", "visualiza")
_INTEGRATION_KEYWORDS = ("integra", "api", "sync", "llama a", "webhook", "endpoint")
_E2E_KEYWORDS = (
    "load test",
    "<200ms",
    "e2e",
    "end-to-end",
    "rendimiento",
    "performance",
    "stress",
)


def classify_ac(text: str) -> Literal["simple", "integration", "e2e"]:
    """Classify an AC by its text.

    Order of checks: e2e → integration → simple (most specific first).
    Default: simple.
    """
    lower = (text or "").lower()
    for kw in _E2E_KEYWORDS:
        if kw in lower:
            return "e2e"
    for kw in _INTEGRATION_KEYWORDS:
        if kw in lower:
            return "integration"
    for kw in _SIMPLE_KEYWORDS:
        if kw in lower:
            return "simple"
    return "simple"


# ── Milestone distribution math ──────────────────────────────────────


def compute_distribution(
    items: list[ItemDTO], ac_counts: dict[str, int]
) -> dict[str, dict[str, Any]]:
    """Compute per-milestone distribution from a list of UCs.

    Args:
        items: list of UC ItemDTOs with optional meta["milestone"]
        ac_counts: mapping uc_id -> number of ACs

    Returns:
        {
            "H1": {"ucs": [uc_id, ...], "ac_count": int, "pct_acs": float},
            ...
        }
    """
    distribution: dict[str, dict[str, Any]] = {
        m: {"ucs": [], "ac_count": 0, "pct_acs": 0.0} for m in MILESTONES
    }
    total_acs = 0
    for item in items:
        milestone = item.meta.get("milestone")
        if milestone not in MILESTONES:
            continue
        uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
        if not uc_id:
            continue
        ac_count = int(ac_counts.get(uc_id, 0))
        bucket = distribution[milestone]
        bucket["ucs"].append(uc_id)
        bucket["ac_count"] = int(bucket["ac_count"]) + ac_count
        total_acs += ac_count

    if total_acs > 0:
        for bucket in distribution.values():
            bucket["pct_acs"] = round(
                int(bucket["ac_count"]) / total_acs, 4
            )

    return distribution


# ── Settings path resolution ─────────────────────────────────────────


def settings_path_from_env() -> Path | None:
    """Resolve the orchestrator settings.local.json path from the environment.

    Looks at `SPECBOX_PROJECT_ROOT` first, then the current working dir.
    Returns None if no settings.local.json is found.
    """
    import os

    candidates: list[Path] = []
    root = os.getenv("SPECBOX_PROJECT_ROOT")
    if root:
        candidates.append(Path(root) / ".claude" / "settings.local.json")
    candidates.append(Path.cwd() / ".claude" / "settings.local.json")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
