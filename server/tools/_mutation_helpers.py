"""Internal helpers shared by Tier 1-4 mutation tool modules.

Not registered as MCP tools. Imported by:
- server/tools/spec_mutations.py (Tier 1)
- server/tools/milestone_management.py (Tier 2)
- server/tools/board_operations.py (Tier 3)
- server/tools/acceptance_automation.py (Tier 4)

See doc/design/v5.23.0-full-mutations.md — section "Shared helpers".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal

from ..spec_backend import ChecklistItemDTO, ItemDTO, SpecBackend, parse_item_id

# ── Constants ────────────────────────────────────────────────────────

LINK_TYPES: tuple[str, ...] = (
    "absorbs",
    "blocks",
    "depends_on",
    "supersedes",
    "related_to",
)
VERDICT_TYPES: tuple[str, ...] = ("ACCEPTED", "CONDITIONAL", "REJECTED")


def utc_now_iso() -> str:
    """ISO 8601 UTC timestamp with seconds precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Validators ───────────────────────────────────────────────────────


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


async def check_satellite(backend: Any, board_id: str, value: str) -> tuple[bool, str | None]:
    """Validate a satellite against what the project declared (US-78 / UC-7803).

    ``validate_satellite`` only read the orchestrator settings from the
    SERVER's disk, so with the remote MCP any text was accepted. Order now:

    1. the satellites declared on the board (``declare_satellites``; Native);
    2. with a local MCP only, the orchestrator ``settings.local.json``;
    3. nothing declared anywhere → any non-empty key (mono-repo projects).

    A refusal lists the valid satellites.
    """
    if not value:
        return False, "Satellite key must be a non-empty string"
    declared = await backend.get_board_satellites(board_id)
    if not declared:
        from ..transport import is_remote_transport

        if is_remote_transport():
            return True, None
        return validate_satellite(value, settings_path_from_env())
    if value in declared:
        return True, None
    return False, f"Satellite {value!r} is not declared for this project. Valid satellites: {', '.join(declared)}"


# ── Milestones: removed (US-78 / UC-7807) ────────────────────────────

#: Milestones H1–H4 gave way to epics (D20): deprecated in 6.21.0,
#: removed in 6.23.0. A batch entry that still carries one gets this.
MILESTONES_REMOVED_MESSAGE = (
    "Milestones were removed in v6.23.0. Group stories with epics instead "
    "(add_epic, set_us_epic, list_epics, get_epic)."
)


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


# ── US-33/UC-3303 — check de exposición ──────────────────────────────
#
# D7 convierte los AC en entregable cara-al-cliente: pueden acabar proyectados
# en una reunión. Un AC que cita las credenciales de una cuenta o la ruta
# interna de un fichero deja de ser un criterio y pasa a ser una filtración.
#
# AVISA, NO BLOQUEA (AC-02). El objetivo es visibilidad, no fricción: un
# `exposure_warning` no impide aprobar el Definition Quality Gate, solo aparece
# listado para que una persona lo mire.

#: Indicios de ALTA señal: nombrar esto en un AC casi nunca es inocente.
_EXPOSURE_HIGH_RE = re.compile(
    r"contrase[nñ]|password|passwd|api[ _-]?key|apikey|(?<![a-z_])secret|credencial|client[ _-]secret",
    re.IGNORECASE,
)

#: Prefijos de claves reales de los proveedores que usa el ecosistema.
_EXPOSURE_KEY_RE = re.compile(
    r"sk_live_|sk_test_|ghp_|gho_|sbp_|spbx_|whsec_|eyJ[A-Za-z0-9_-]{20,}"
)

#: Rutas internas con extensión de código. Son la otra mitad del AC-01: quien
#: paga el proyecto no necesita saber en qué fichero vive la implementación.
_EXPOSURE_PATH_RE = re.compile(
    r"[A-Za-z0-9_/.-]+\.(py|ts|tsx|jsx|sql|mjs|json|yaml|yml|sh)(?![A-Za-z])"
)


def detect_ac_exposure(text: str) -> list[str]:
    """Return exposure warning tags for an AC text. Empty list = nothing to flag.

    POR QUÉ NO SE MARCA TODA MENCIÓN DE «usuario» O «token»
    --------------------------------------------------------
    El AC-01 enumera «usuario, contraseña, token, api key, secret». Aplicado al
    pie de la letra sobre el board del orquestador, eso marca **72 de 547** AC,
    y 46 de esos 72 son la palabra «usuario» usada como ROL —«el usuario ve su
    panel»—, que no expone nada. Un aviso que salta en uno de cada ocho
    criterios no lo lee nadie, y un aviso que nadie lee no protege nada.

    Así que se distingue la mención del indicio:

    - `contraseña`, `password`, `api key`, `secret`, `credencial` → siempre.
      Nombrarlos en un criterio casi nunca es inocente.
    - `usuario` → solo si va acompañado de contraseña/credencial, o seguido de
      un valor (`usuario: ...`). Como rol no cuenta.
    - `token` → solo si va seguido de un valor. En este ecosistema `dev_token`
      y `mcp_tokens` son conceptos de dominio con su propia US, no secretos.
    - Prefijos de clave real (`sk_live_`, `ghp_`, `sbp_`, JWT…) → siempre, sin
      importar el contexto.

    Medido con esta regla: 12 avisos de credencial en el manager (de 72), y el
    AC-04 de UC-083 de `potencial_digital_2026` —que cita usuario y contraseña
    de la cuenta de revisión de App Store— se sigue marcando, que es el AC-03.

    Returns:
        Lista con `exposure_warning` más la categoría concreta, para que el
        informe pueda decir POR QUÉ y no solo QUE.
    """
    stripped = (text or "").strip()
    if not stripped:
        return []

    lower = stripped.lower()
    tags: list[str] = []

    credential = bool(_EXPOSURE_HIGH_RE.search(stripped)) or bool(_EXPOSURE_KEY_RE.search(stripped))
    if not credential and "usuario" in lower:
        credential = bool(
            re.search(r"contrase[nñ]|password|credencial", lower)
            or re.search(r"usuario\s*[:=]", lower)
        )
    if not credential:
        credential = bool(re.search(r"token\s*[:=]\s*\S", lower))

    if credential:
        tags.append("exposure_credentials")
    if _EXPOSURE_PATH_RE.search(stripped):
        tags.append("exposure_internal_path")

    if tags:
        tags.insert(0, "exposure_warning")
    return tags


def validate_ac_text(text: str, *, rules: int = 1) -> list[str]:
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

    if rules >= 2:
        issues += spec_rule_issues(stripped)

    return issues


# ── UC-12302 — lenguaje normativo y límites medibles (reglas versión 2) ──
#
# Solo para criterios escritos con estas reglas: el backend guarda `meta.spec_rules` al crear un
# criterio o reescribir su texto (native y FreeForm). Un criterio sin sello es «anterior a la
# regla» y se juzga con las reglas de antes. Calibradas contra los 1.835 criterios del tablero del
# orquestador (plan de US-123, §2): «intenta» aparece 23 veces y siempre es una persona que intenta
# algo, y casi todas las cifras con unidad de tiempo son plazos, no rendimiento.
# «podría» queda fuera: en el tablero describe situaciones («…podrían disparar builds»), no promesas.

#: Desde qué versión de reglas se aplican lenguaje normativo y límites con cifra (UC-12302).
RULES_NORMATIVE = 2
#: Desde qué versión de reglas un criterio sin «cómo se comprueba» recibe ``no_verification``
#: (UC-12307). Los criterios escritos antes no tienen el campo y no se les pide.
RULES_VERIFICATION = 3

#: Versión de las reglas del gate que estampa el backend en cada criterio nuevo o reescrito.
SPEC_RULES_VERSION = RULES_VERIFICATION

#: Lo citado no es lo que el criterio afirma: «debería», "rápido" o `may` entre comillas son el
#: nombre de algo (UC-12302 cita las palabras de su propia regla).
_QUOTED_SPANS_RE = re.compile(r"`[^`\n]*`|«[^»\n]*»|\"[^\"\n]*\"|“[^”\n]*”")

_WEAK_MODAL_RE = re.compile(
    r"\b(?:deber[ií]an?|idealmente|procuran?|procurar[aá]n?|should|may|might|tries to|try to)\b"
    r"|\ben lo posible\b|\bsi es posible\b|\ba ser posible\b",
    re.IGNORECASE,
)
#: «intenta reenviar»: el criterio promete intentarlo, no conseguirlo. «Una sesión que intenta entrar
#: recibe 401» sí afirma un resultado, y por eso solo cuenta si no queda ningún verbo de resultado.
_TRY_RE = re.compile(r"\bintenta(?:r[aá]n?|n)?\s+(?:de\s+)?\w+(?:ar|er|ir)\b", re.IGNORECASE)
#: «… que intenta entrar», «si lo intenta»: es el actor del caso, no la promesa del criterio.
_ACTOR_TRIES_RE = re.compile(r"\b(?:que|quien(?:es)?|si|cuando|mientras)\s+(?:(?:lo|la|los|las|se|le)\s+)?$", re.IGNORECASE)

_VAGUE_LIMIT_RE = re.compile(
    r"\ben poco tiempo\b|\br[aá]pid(?:o|a|os|as|amente)\b|\blent(?:o|a|os|as|amente)\b"
    r"|\bmuch[oa]s\b|\bpoc[oa]s\b|\bpronto\b|\benseguida\b|\bdemasiad[oa]s?\b",
    re.IGNORECASE,
)
#: Lo que limita una cantidad o un tiempo. «una o varias pantallas» no limita nada.
_LIMIT_VERB_RE = re.compile(
    r"\b(?:responden?|cargan?|tardan?|admiten?|soportan?|procesan?|aceptan?|terminan?)\b"
    r"|\bcomo m[aá]ximo\b|\bcomo mucho\b|\ben menos de\b|\bno m[aá]s de\b",
    re.IGNORECASE,
)

_PERF_FIGURE_RE = re.compile(
    r"\b(?:responden?|cargan?|tardan?|aparecen?|se abren?|terminan?|devuelven?|contestan?)\b[^.;\n]{0,60}?"
    r"(?<![A-Za-z\d-])\d+(?:[.,]\d+)?\s*(?:ms|s|seg|segundos?|min|minutos?)\b",
    re.IGNORECASE,
)
_CONDITION_RE = re.compile(
    r"\bp\s?9[059]\b|percentil|\b[345]g\b|wi-?fi|\bred\b|conexi[oó]n|\bcon\s+\d+"
    r"|\d+\s+(?:filas|registros|elementos|criterios|usuarios|ucs?|acs?|peticiones|ficheros|archivos)\b"
    r"|dispositivo|iphone|android|m[oó]vil|escritorio|navegador|en local\b|en producci[oó]n|servidor|volumen",
    re.IGNORECASE,
)


def _unquoted(text: str) -> str:
    return _QUOTED_SPANS_RE.sub(" ", text or "")


def spec_rule_issues(text: str) -> list[str]:
    """Fallos de las reglas versión 2: ``weak_modal`` y ``no_threshold`` (UC-12302 AC-01, AC-02)."""
    plain = _unquoted(text)
    lower = plain.lower()
    issues: list[str] = []
    weak = bool(_WEAK_MODAL_RE.search(plain))
    if not weak:
        tried = _TRY_RE.search(plain)
        if tried and not _ACTOR_TRIES_RE.search(plain[: tried.start()]):
            rest = (lower[: tried.start()] + " " + lower[tried.end():])
            weak = not any(v in rest for v in _OUTCOME_VERBS)
    if weak:
        issues.append("weak_modal")
    if _VAGUE_LIMIT_RE.search(plain) and _LIMIT_VERB_RE.search(plain) and not _MEASUREMENT_RE.search(lower):
        issues.append("no_threshold")
    return issues


def ac_text_warnings(text: str, *, rules: int = 1) -> list[str]:
    """Avisos que no cuentan para el umbral: ``threshold_without_condition`` (UC-12302 AC-03)."""
    if rules < 2:
        return []
    plain = _unquoted(text)
    if _PERF_FIGURE_RE.search(plain) and not _CONDITION_RE.search(plain):
        return ["threshold_without_condition"]
    return []


def spec_rules_of(meta: Any) -> int:
    """La versión de reglas guardada en el ``meta`` de un criterio; 1 si no hay sello."""
    value = meta.get("spec_rules") if isinstance(meta, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else 1


# ── UC-12307 — cómo se comprueba cada criterio ───────────────────────

#: Las cuatro formas de comprobar un criterio: una prueba automática, una prueba a mano, una
#: revisión (de código, de diseño, de un documento) o una medida (tiempo, tamaño, cobertura…).
VERIFICATION_METHODS: tuple[str, ...] = ("automated_test", "manual_test", "review", "measurement")


class VerificationError(ValueError):
    """Un valor de ``verification`` que no es una de las cuatro formas."""


def normalize_verification(value: Any) -> str | None:
    """``None`` o una de :data:`VERIFICATION_METHODS`; cualquier otro valor lanza VerificationError.

    Acepta mayúsculas, espacios y guiones («Automated test», ``manual-test``) para no rechazar
    lo que un cliente escribe a mano, pero guarda siempre la forma canónica.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise VerificationError(f"verification must be a string, got {type(value).__name__}")
    key = re.sub(r"[\s-]+", "_", value.strip().lower())
    if key not in VERIFICATION_METHODS:
        raise VerificationError(
            f"verification {value!r} is not one of: {', '.join(VERIFICATION_METHODS)}"
        )
    return key


#: Las claves del ``meta`` de un criterio que una tool puede escribir. El resto (``spec_rules``,
#: ``evidence``, ``verdict``…) lo escribe solo el propio backend.
AC_META_KEYS = frozenset({"verification"})


def ac_meta_extra(meta: dict[str, Any] | None) -> dict[str, Any]:
    """De un ``meta`` recibido, solo las claves de :data:`AC_META_KEYS` con valor."""
    return {k: v for k, v in (meta or {}).items() if k in AC_META_KEYS and v is not None}


def verification_of(meta: Any) -> str | None:
    """La forma de comprobación guardada en el ``meta`` de un criterio (None si no hay o no vale)."""
    value = meta.get("verification") if isinstance(meta, dict) else None
    return value if value in VERIFICATION_METHODS else None


def normalize_exclusions(value: Any) -> list[str] | None:
    """UC-12306: las exclusiones de una historia como lista de textos sin vacíos.

    ``None`` = no se dijeron (se conservan las que hubiera); ``[]`` = ninguna. Un texto suelto
    cuenta como una exclusión; cualquier otra cosa que no sea lista lanza ValueError.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError("exclusions must be a list of strings")
    return [v.strip() for v in value if v.strip()]


def exclusions_of(meta: Any) -> list[str]:
    """Las exclusiones guardadas en el ``meta`` de una historia ([] si no hay)."""
    value = meta.get("exclusions") if isinstance(meta, dict) else None
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


NO_EXCLUSIONS_MESSAGE = (
    "La historia no dice qué queda fuera. Añade sus exclusiones (la sección «No incluye» del PRD) "
    "con import_spec (exclusions) o update_us(exclusions=[...])."
)


def verification_warnings(verification: str | None, *, rules: int = 1) -> list[str]:
    """``no_verification`` para un criterio escrito con las reglas 3 o más que no dice cómo se
    comprueba (UC-12307 AC-03). Uno anterior no tenía el campo y queda sin aviso (AC-04)."""
    if rules < RULES_VERIFICATION or verification:
        return []
    return ["no_verification"]


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

    Returns 0 if no UCs exist. A FreeForm fragment (UC-11102) only carries part
    of the board, so the highest number it declares for the whole board counts too.
    """
    items = await backend.list_items(board_id)
    max_num = backend.logical_id_floor("UC")
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


_STORY_NUMBER_RE = re.compile(r"^US-(\d+)$")
_UC_ID_RE = re.compile(r"^UC-[A-Za-z0-9][A-Za-z0-9-]*$")


def is_valid_uc_id(uc_id: str | None) -> bool:
    """An explicit UC id: `UC-` plus letters, digits or dashes (UC-12214, UC-004b)."""
    return bool(_UC_ID_RE.fullmatch(uc_id or ""))


def uc_owners(items: list[ItemDTO]) -> dict[str, str]:
    """`{uc_id: us_id}` of every UC on the board (`us_id` from its meta or its parent story)."""
    stories = {i.id: i for i in items if "US" in i.labels}
    owners: dict[str, str] = {}
    for item in items:
        if "UC" not in item.labels:
            continue
        uc_id = item.meta.get("uc_id") or parse_item_id(item.name, "UC")[0]
        if not uc_id:
            continue
        us_id = item.meta.get("us_id") or ""
        if not us_id and item.parent_id in stories:
            parent = stories[item.parent_id]
            us_id = parent.meta.get("us_id") or parse_item_id(parent.name, "US")[0] or ""
        owners[uc_id] = us_id
    return owners


def _uc_number(uc_id: str) -> int:
    try:
        return int(uc_id.split("-")[1])
    except (IndexError, ValueError):
        return 0


@dataclass(frozen=True)
class UcIdChoice:
    """The id `add_uc` would give a new UC (UC-12214).

    `numbering`: "story" when the story's UCs follow `UC-{story number}{NN}` and the new one
    continues that series; "board" when it takes the next number of the whole board.
    `taken_by`: the story that already has that id, if any (a conflict: nothing is created).
    """

    uc_id: str
    numbering: str
    taken_by: str | None = None


async def choose_uc_id(backend: SpecBackend, board_id: str, us_id: str) -> UcIdChoice:
    """Next UC id for a story (UC-12214).

    - When every UC of the story follows `UC-{story number}{NN}` (US-122 → UC-12201, UC-12202…),
      the new one continues that series: UC-12212 and UC-12213 → UC-12214.
    - Otherwise (correlative boards, an empty story), the next number of the whole board, as
      before: UC-001…UC-027 → UC-028.

    Numbers that parallel calls already reserved (a FreeForm fragment, UC-11102) are skipped.
    """
    items = await backend.list_items(board_id)
    owners = uc_owners(items)
    reserved = backend.reserved_logical_numbers("UC")
    siblings = [uc for uc, owner in owners.items() if owner == us_id]

    story = _STORY_NUMBER_RE.fullmatch(us_id or "")
    if story and siblings:
        prefix = story.group(1)
        series = re.compile(rf"^UC-{prefix}(\d{{2,}})$")
        matches = [series.fullmatch(uc) for uc in siblings]
        if all(matches):
            nn = max(int(m.group(1)) for m in matches if m) + 1
            while int(f"{prefix}{nn:02d}") in reserved:
                nn += 1
            candidate = f"UC-{prefix}{nn:02d}"
            return UcIdChoice(candidate, "story", owners.get(candidate))

    top = max([backend.logical_id_floor("UC"), *(_uc_number(uc) for uc in owners), *reserved, 0])
    candidate = format_uc_id(top + 1)
    return UcIdChoice(candidate, "board", owners.get(candidate))


async def uc_owner(backend: SpecBackend, board_id: str, uc_id: str) -> str | None:
    """The story that has `uc_id` (`""` when it has none), or None when the board does not."""
    return uc_owners(await backend.list_items(board_id)).get(uc_id)


def next_ac_id(existing: list[ChecklistItemDTO], retired_ids: Iterable[str] = ()) -> str:
    """Compute the next AC-NN id from the existing ACs and the retired ones (UC-12501).

    A retired id is never used again in its UC: if AC-05 was retired from AC-01..AC-05, the next
    one is AC-06, not AC-05.
    """
    max_num = 0
    for ac_id in [ac.id for ac in existing] + list(retired_ids):
        if not ac_id or not ac_id.startswith("AC-"):
            continue
        try:
            num = int(ac_id.split("-")[1])
        except (IndexError, ValueError):
            continue
        if num > max_num:
            max_num = num
    return f"AC-{max_num + 1:02d}"


#: Largo del motivo al retirar un criterio (UC-12501): lo que verá quien lea la UC después.
REASON_MIN = 10
REASON_MAX = 500


async def retired_ids(backend: Any, board_id: str, uc_item_id: str) -> list[str]:
    """Los ids retirados de una UC (UC-12501); vacío si el backend no los guarda."""
    return [r["id"] for r in await backend.get_retired_criteria(board_id, uc_item_id)]


async def retired_error(backend: Any, board_id: str, uc_item_id: str, uc_id: str, ac_id: str) -> dict[str, Any] | None:
    """El error ``AC_RETIRED`` si ``ac_id`` está retirado en la UC, con su motivo; None si no lo está."""
    try:
        retired = await backend.get_retired_criteria(board_id, uc_item_id)
    except Exception:  # noqa: BLE001 — sin poder mirarlo, el error sigue siendo AC_NOT_FOUND
        return None
    record = next((r for r in retired if r.get("id") == ac_id), None)
    if record is None:
        return None
    return {
        "error": (
            f"El criterio {ac_id} de {uc_id} está retirado ({record.get('retired_at', '')}): "
            f"{record.get('reason', '')}. Un criterio retirado no se marca ni se reescribe; "
            "si hace falta, añade uno nuevo con add_ac."
        ),
        "code": "AC_RETIRED",
        "uc_id": uc_id,
        "ac_id": ac_id,
        "retired": record,
    }


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


# ── import_spec sobre una UC que ya existe (UC-12501) ────────────────

#: Qué hace import_spec con una UC que ya está en el tablero.
ON_EXISTING_UC = ("report", "apply")
#: Campos de la UC que import_spec compara además del nombre y los criterios.
_COMPARED_FIELDS = {"actor": "actor", "horas": "hours", "pantallas": "screens", "satellite": "satellite", "us_id": "us_id"}


def norm_text(text: str) -> str:
    """El texto de un criterio sin espacios repetidos: lo que se compara al emparejar."""
    return " ".join(str(text or "").split())


def _context_of(description: str) -> str:
    parts = str(description or "").split("## Contexto\n", 1)
    return parts[1].strip() if len(parts) == 2 else ""


def plan_existing_uc(
    *,
    existing_name: str,
    existing_meta: dict[str, Any],
    existing_description: str,
    existing_acs: list[ChecklistItemDTO],
    retired: Iterable[dict[str, Any]],
    spec_name: str,
    spec_meta: dict[str, Any],
    spec_context: str,
    spec_criteria: list[str],
    spec_verifications: list[str | None],
    stores_meta: bool,
) -> dict[str, Any]:
    """Lo que la spec cambiaría en una UC que ya existe, sin tocar nada (UC-12501 AC-04).

    Los criterios se emparejan por texto (``norm_text``): uno que coincide conserva su id; uno de
    la spec que no está toma el siguiente id libre, contando los retirados; uno vigente que la spec
    no trae sigue igual y sale en ``criteria_missing``. Un texto de la spec que es el de un criterio
    retirado no vuelve (se retiró a propósito) y sale en ``criteria_retired``. Nunca se reescribe ni
    se retira un criterio.

    Devuelve ``differences`` (lo que se avisa), ``identical``, ``new`` [(id, texto)],
    ``new_verifications`` {id: verification}, ``verification_updates`` [(id, verification)] y
    ``final`` [(id, texto)]: los vigentes tras aplicar, en orden de id.
    """
    differences: dict[str, Any] = {
        "name": None,
        "fields": [],
        "criteria_added": [],
        "criteria_missing": [],
        "criteria_retired": [],
        "verification_changed": [],
    }
    if norm_text(existing_name) != norm_text(spec_name):
        differences["name"] = {"from": existing_name, "to": spec_name}
    meta = existing_meta if isinstance(existing_meta, dict) else {}
    for key, label in _COMPARED_FIELDS.items():
        if key not in spec_meta:
            continue
        before, after = meta.get(key), spec_meta.get(key)
        if key == "horas":
            try:
                same = float(before or 0) == float(after or 0)
            except (TypeError, ValueError):
                same = before == after
        else:
            same = str(before or "") == str(after or "")
        if not same:
            differences["fields"].append(label)
    if norm_text(_context_of(existing_description)) != norm_text(spec_context):
        differences["fields"].append("context")

    unmatched = list(existing_acs)
    new: list[tuple[str, str]] = []
    new_verifications: dict[str, str] = {}
    verification_updates: list[tuple[str, str]] = []
    retired_list = [r for r in retired if isinstance(r, dict) and r.get("id")]
    retired_by_text = {norm_text(r.get("text", "")): r for r in retired_list}
    taken = [ac.id for ac in existing_acs] + [r["id"] for r in retired_list]
    for index, text in enumerate(spec_criteria):
        wanted = spec_verifications[index] if index < len(spec_verifications) else None
        match = next((ac for ac in unmatched if norm_text(ac.text) == norm_text(text)), None)
        if match is None and norm_text(text) in retired_by_text:
            gone = retired_by_text[norm_text(text)]
            differences["criteria_retired"].append({"id": gone["id"], "text": text, "reason": gone.get("reason")})
            continue
        if match is None:
            ac_id = next_ac_id([], taken)
            taken.append(ac_id)
            new.append((ac_id, text))
            if wanted:
                new_verifications[ac_id] = wanted
            differences["criteria_added"].append(text)
            continue
        unmatched.remove(match)
        current = getattr(match, "verification", None)
        if wanted and stores_meta and current != wanted:
            verification_updates.append((match.id, wanted))
            differences["verification_changed"].append({"id": match.id, "from": current, "to": wanted})
    differences["criteria_missing"] = [{"id": ac.id, "text": ac.text} for ac in unmatched]

    final = sorted([(ac.id, ac.text) for ac in existing_acs] + new, key=lambda pair: _ac_number(pair[0]))
    identical = not (
        differences["name"] or differences["fields"] or differences["criteria_added"]
        or differences["criteria_missing"] or differences["criteria_retired"]
        or differences["verification_changed"]
    )
    return {
        "differences": differences,
        "identical": identical,
        "new": new,
        "new_verifications": new_verifications,
        "verification_updates": verification_updates,
        "final": final,
    }


def _ac_number(ac_id: str) -> int:
    try:
        return int(str(ac_id).split("-")[1])
    except (IndexError, ValueError):
        return 10**6
