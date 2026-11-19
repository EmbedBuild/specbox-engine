"""La puerta de desviación (US-126 · UC-12602): lo que cambia una rama frente a su spec.

Para cada fichero cambiado, la UC de la rama que lo reclama, por el plan (la línea **Ficheros:** de
una fase cuyos criterios son de esa UC) o por los recibos de sus criterios (``files``), o «sin UC».
Las dependencias nuevas que el plan no declara en «## Dependencias nuevas». Las UC cerradas que el
cambio toca (UC-12603), solo como aviso. Y lo que queda fuera: las exclusiones del proyecto.

Puro: no lee disco ni el tablero. La tool ``get_drift_report`` y la orden ``specbox drift`` lo usan.
"""

from __future__ import annotations

import re
from typing import Any

from .closed_files import ClosedUc, closed_uc_touches, normalize_path
from .plan_contract import PlanContract

#: Los nombres de un mismo gestor de paquetes en el plan y en los manifiestos.
ECOSYSTEM_ALIASES = {"pip": "pypi", "uv": "pypi", "yarn": "npm", "pnpm": "npm", "dart": "pub", "golang": "go"}


def ecosystem_key(name: str) -> str:
    key = (name or "").strip().lower()
    return ECOSYSTEM_ALIASES.get(key, key)


def dependency_key(ecosystem: str, name: str) -> str:
    """``httpx>=0.27`` → ``httpx``; ``Rapid_Fuzz[speedup]`` → ``rapid-fuzz`` (PyPI); ``@scope/pkg@^1`` → ``@scope/pkg``."""
    eco = ecosystem_key(ecosystem)
    raw = (name or "").strip().strip("`").strip()
    if eco == "npm":
        scoped = raw.startswith("@")
        base = raw[1:] if scoped else raw
        base = re.split(r"[@\s]", base, maxsplit=1)[0]
        return ("@" + base if scoped else base).lower()
    base = re.split(r"[\s\[<>=!~^;,(]", raw, maxsplit=1)[0]
    if eco == "pypi":
        base = re.sub(r"[-_.]+", "-", base)
    return base.lower()


#: Lo que admite la lista de exclusiones de un proyecto.
MAX_EXCLUDE = 200
MAX_EXCLUDE_LEN = 200
#: Los comodines («*» y «?») que admite un glob de exclusión: ninguno real pasa de unos pocos.
MAX_EXCLUDE_WILDCARDS = 20
#: El largo máximo de una ruta que se compara (más largo no lo genera ningún repositorio real).
MAX_DRIFT_PATH = 1024
#: El trabajo máximo de una llamada al comparar con las exclusiones (casillas de la programación
#: dinámica; ~1 s en el servidor). Un caso normal se queda muy por debajo: casi todas las rutas se
#: descartan antes con la comprobación de los trozos literales.
MAX_GLOB_WORK = 40_000_000

_UC_ID = re.compile(r"\bUC-\d+[a-z]?\b", re.IGNORECASE)
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


class ExcludeTooCostly(ValueError):
    """Las exclusiones, con tantos ficheros, cuestan más de lo que una llamada puede gastar."""


class GlobBudget:
    """Cuenta el trabajo de la comparación con las exclusiones de una llamada (MAX_GLOB_WORK)."""

    def __init__(self, limit: int = MAX_GLOB_WORK) -> None:
        self.limit = limit
        self.spent = 0

    def spend(self, cells: int) -> None:
        self.spent += cells
        if self.spent > self.limit:
            raise ExcludeTooCostly(
                "Las exclusiones del proyecto cuestan demasiado de comparar con tantos ficheros: "
                "simplifica los globs (menos «*» seguidos) o excluye por carpeta."
            )


def _glob_tokens(pattern: str) -> list[str]:
    """``docs/**/*.md`` → [d, o, c, s, /, **/, *, ., m, d]. Los ``*`` seguidos se juntan."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            j = i
            while j < len(pattern) and pattern[j] == "*":
                j += 1
            if pattern.startswith("/", j):
                if not out or out[-1] != "**/":
                    out.append("**/")
                i = j + 1
            else:
                if not out or out[-1] not in ("**", "*"):
                    out.append("**")
                elif out[-1] == "*":
                    out[-1] = "**"
                i = j
        elif pattern[i] == "*":
            if not out or out[-1] not in ("*", "**"):
                out.append("*")
            i += 1
        else:
            out.append(pattern[i])
            i += 1
    return out


def _glob_match(tokens: list[str], path: str) -> bool:
    """¿``path`` entero casa con el glob? Programación dinámica: tiempo ``len(tokens) × len(path)``,
    sin la vuelta atrás de una expresión regular (un glob con muchos ``*`` no cuelga el servidor)."""
    n = len(path)
    nxt = [False] * (n + 1)
    nxt[n] = True  # sin tokens, casa solo el final
    for tok in reversed(tokens):
        cur = [False] * (n + 1)
        if tok == "**/":
            # Cero o más carpetas: o sigue sin consumir nada, o consume hasta una «/» incluida.
            reach = False  # ¿desde j se llega, consumiendo hasta alguna «/», a un punto que casa?
            for j in range(n - 1, -1, -1):
                reach = (path[j] == "/" and nxt[j + 1]) or reach
                cur[j] = nxt[j] or reach
            cur[n] = nxt[n]
        elif tok == "**":
            cur[n] = nxt[n]
            for j in range(n - 1, -1, -1):
                cur[j] = nxt[j] or cur[j + 1]
        elif tok == "*":
            cur[n] = nxt[n]
            for j in range(n - 1, -1, -1):
                cur[j] = nxt[j] or (path[j] != "/" and cur[j + 1])
        elif tok == "?":
            for j in range(n):
                cur[j] = path[j] != "/" and nxt[j + 1]
        else:
            for j in range(n):
                cur[j] = path[j] == tok and nxt[j + 1]
        nxt = cur
    return nxt[0]


def _literal_chunks(tokens: list[str]) -> tuple[list[str], bool, bool]:
    """Los trozos literales del glob en orden, y si el primero va al principio y el último al final."""
    chunks: list[str] = []
    cur = ""
    for tok in tokens:
        if tok in ("**/", "**", "*", "?"):
            if cur:
                chunks.append(cur)
            cur = ""
        else:
            cur += tok
    if cur:
        chunks.append(cur)
    wild = ("**/", "**", "*", "?")
    return chunks, bool(tokens) and tokens[0] not in wild, bool(tokens) and tokens[-1] not in wild


def _could_match(chunks: list[str], at_start: bool, at_end: bool, path: str) -> bool:
    """Condición necesaria (en tiempo lineal, con ``str.find``): los trozos literales aparecen en orden."""
    if not chunks:
        return True
    start, end = 0, len(path)
    if at_start:
        if not path.startswith(chunks[0]):
            return False
        start = len(chunks[0])
        chunks = chunks[1:]
    if at_end and chunks:
        if not path.endswith(chunks[-1]) or len(path) - len(chunks[-1]) < start:
            return False
        end = len(path) - len(chunks[-1])
        chunks = chunks[:-1]
    for chunk in chunks:
        found = path.find(chunk, start, end)
        if found < 0:
            return False
        start = found + len(chunk)
    return True


def glob_matcher(pattern: str):
    """Un glob del proyecto (como en .gitignore) → ``match(ruta, budget=None) -> bool``.

    ``**`` cruza carpetas y ``*`` y ``?`` no. Un patrón sin «/» vale en cualquier carpeta; uno que
    empieza por «/» solo en la raíz; un nombre sin comodines (``docs``) cubre también lo que hay dentro.
    Con ``budget`` (GlobBudget), cada comparación completa gasta su trabajo y, pasado el tope, lanza
    ExcludeTooCostly: una llamada no puede tener ocupado el servidor compartido.
    """
    pat = (pattern or "").strip().replace("\\", "/")
    anchored = pat.startswith("/")
    pat = pat.lstrip("/")
    while pat.startswith("./"):
        pat = pat[2:]
    if not pat:
        return lambda path, budget=None: False
    if pat.endswith("/"):
        pat += "**"
    if not anchored and "/" not in pat.rstrip("/"):
        pat = "**/" + pat
    variants = [_glob_tokens(pat)]
    if not pat.endswith("**"):
        variants.append(_glob_tokens(pat + "/**"))
    prepared = [(tokens, *_literal_chunks(tokens)) for tokens in variants]

    def match(path: str, budget: GlobBudget | None = None) -> bool:
        for tokens, chunks, at_start, at_end in prepared:
            if budget is not None:
                # La comprobación previa también cuesta: un trozo buscado y la ruta recorrida.
                budget.spend(len(chunks) + len(path) // 16 + 1)
            if not _could_match(chunks, at_start, at_end, path):
                continue
            if budget is not None:
                budget.spend(len(tokens) * (len(path) + 1))
            if _glob_match(tokens, path):
                return True
        return False

    return match


def _outside_code(text: str) -> list[str]:
    lines: list[str] = []
    fence: str | None = None
    for line in (text or "").splitlines():
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener[1][0] == fence[0] and len(opener[1]) >= len(fence):
                fence = None
            continue
        if opener:
            fence = opener[1]
            continue
        lines.append(line)
    return lines


def plan_owner(path: str, text: str) -> str | None:
    """La UC de un plan cuyos criterios no dicen la suya: la única del título (``# …``), si no la única
    del nombre del fichero y, si no, la única que nombra el plan. Con dos o más, ninguna."""
    lines = _outside_code(text)
    title = next((line for line in lines if re.match(r"^#\s", line)), "")
    for source in (title, path.rsplit("/", 1)[-1], "\n".join(lines)):
        ucs = {m.upper() for m in _UC_ID.findall(source)}
        if len(ucs) == 1:
            return ucs.pop()
        if len(ucs) > 1:
            return None
    return None


def plan_mentions(text: str) -> set[str]:
    """Las UC que nombra el plan fuera de los bloques de código."""
    return {m.upper() for m in _UC_ID.findall("\n".join(_outside_code(text)))}


def _covers(entry: str, path: str) -> bool:
    entry = normalize_path(entry)
    return path == entry or (entry.endswith("/") and path.startswith(entry))


def _plan_ucs(contract: PlanContract, owner: str | None) -> str | None:
    """La UC de los criterios que no dicen la suya: la única que nombra el contrato, o el dueño del plan."""
    if len(contract.named_ucs) == 1:
        return contract.named_ucs[0]
    return owner if not contract.named_ucs else None


def plan_claims(
    contracts: list[PlanContract], branch: set[str] | None = None, owners: list[str | None] | None = None,
) -> list[tuple[str, frozenset[str]]]:
    """``(fichero o carpeta del plan, UC de los criterios de su fase)`` de los planes con contrato.

    Un criterio sin UC es de la única UC que nombra el plan o, si no nombra ninguna, del dueño del plan
    (``plan_owner``). Si no se sabe de quién es, la fase no reclama nada: el plan de otra UC que solo
    cita una de la rama no le da por buenos sus ficheros.
    """
    out: list[tuple[str, frozenset[str]]] = []
    for i, contract in enumerate(contracts):
        if contract.contract_version == 0:
            continue
        default = _plan_ucs(contract, (owners or [None] * len(contracts))[i])
        for phase in contract.phases:
            ucs = frozenset(u for u in ({uc or default for uc, _ in phase.criteria} or {phase.uc or default}) if u)
            if ucs:
                out += [(f, ucs) for f in phase.files]
    return out


def _old_plan_ucs(
    docs: list[tuple[str, PlanContract, str | None, set[str]]], branch: list[str], known: set[str], claiming: set[str],
    done: set[str] | None = None,
) -> list[str]:
    """Las UC de la rama que existen en el tablero, siguen abiertas (no «done»), no reclaman ningún
    fichero y tienen un plan que no declara ficheros por fase (anterior al contrato, o sin líneas
    **Ficheros:** en sus fases)."""
    out: list[str] = []
    for uc in branch:
        if uc not in known or uc in claiming or uc in (done or set()):
            continue
        for _path, contract, owner, mentions in docs:
            if contract.contract_version == 0:
                if owner == uc or (owner is None and uc in mentions):
                    out.append(uc)
                    break
                continue
            default = _plan_ucs(contract, owner)
            phases = [p for p in contract.phases if uc in {c or default for c, _ in p.criteria} | {p.uc}]
            if phases and not any(p.files for p in phases):
                out.append(uc)
                break
    return out


def build_drift_report(
    *,
    files: list[str],
    uc_ids: list[str],
    contracts: list[tuple[str, PlanContract]] | list[tuple[str, PlanContract, str]],
    receipts: dict[str, set[str]] | None = None,
    closed: list[ClosedUc] | None = None,
    dependencies_added: list[dict[str, str]] | None = None,
    exclude: list[str] | None = None,
    known_ucs: set[str] | None = None,
    done_ucs: set[str] | None = None,
    repo: str | None = None,
    satellite: str | None = None,
) -> dict[str, Any]:
    """El informe de la puerta (UC-12602 AC-01 a AC-04, UC-12603 AC-02 y AC-03).

    ``contracts`` son ``(ruta del plan, contrato)`` o ``(ruta, contrato, texto)``: con el texto se sabe
    de qué UC es un plan cuyos criterios no dicen la suya. ``receipts``, los ficheros de los recibos de
    los criterios de cada UC de la rama; ``closed``, las UC cerradas con su lista; ``known_ucs``, las UC
    que existen en el tablero (None si no se pudo leer); ``done_ucs``, las que están cerradas. ``ok`` es
    falso si queda algún fichero sin UC
    o alguna dependencia sin declarar. Lanza ExcludeTooCostly si las exclusiones cuestan demasiado.
    """
    branch = [u.upper() for u in dict.fromkeys(uc_ids)]
    mine = set(branch)
    docs: list[tuple[str, PlanContract, str | None, set[str]]] = []
    for item in contracts:
        path, contract = item[0], item[1]
        text = item[2] if len(item) > 2 else None
        docs.append((
            path, contract,
            plan_owner(path, text) if text is not None else None,
            plan_mentions(text) if text is not None else set(contract.named_ucs),
        ))
    patterns = [(p, glob_matcher(p)) for p in (exclude or []) if isinstance(p, str) and p.strip()]
    budget = GlobBudget()
    claims = plan_claims([c for _, c, _, _ in docs], mine, [o for _, _, o, _ in docs])
    receipt_files = {uc.upper(): {normalize_path(f) for f in fs} for uc, fs in (receipts or {}).items()}

    report_files: list[dict[str, Any]] = []
    unclaimed: list[str] = []
    excluded: list[str] = []
    for raw in dict.fromkeys(normalize_path(f) for f in files if isinstance(f, str)):
        if not raw:
            continue
        rule = next((p for p, matches in patterns if matches(raw, budget)), None)
        if rule:
            excluded.append(raw)
            report_files.append({"path": raw, "excluded_by": rule, "claimed_by": [], "source": None})
            continue
        by_plan = sorted({uc for entry, ucs in claims if _covers(entry, raw) for uc in ucs if uc in mine})
        by_receipt = sorted(uc for uc, fs in receipt_files.items() if uc in mine and raw in fs)
        claimed = sorted(set(by_plan) | set(by_receipt))
        planned_for = sorted({u for entry, ucs in claims if _covers(entry, raw) for u in ucs if u and u not in mine})
        source = "plan+receipt" if by_plan and by_receipt else "plan" if by_plan else "receipt" if by_receipt else None
        entry: dict[str, Any] = {"path": raw, "claimed_by": claimed, "source": source}
        if planned_for:
            entry["planned_for"] = planned_for
        report_files.append(entry)
        if not claimed:
            unclaimed.append(raw)

    declared: dict[str, dict[str, str]] = {}
    plans_without_section: list[str] = []
    for path, contract, _, _ in docs:
        if contract.dependencies is None:
            plans_without_section.append(path)
            continue
        for dep in contract.dependencies:
            key = f"{ecosystem_key(dep['ecosystem'])}:{dependency_key(dep['ecosystem'], dep['name'])}"
            declared[key] = dep
    added = [d for d in (dependencies_added or []) if isinstance(d, dict) and d.get("name")]
    undeclared = [
        d for d in added
        if f"{ecosystem_key(d.get('ecosystem', ''))}:{dependency_key(d.get('ecosystem', ''), d['name'])}" not in declared
    ]

    # La puerta no juzga solo cuando ninguna UC de la rama reclama ficheros y alguna existe en el
    # tablero, sigue abierta y tiene un plan que no declara ficheros por fase (anterior al contrato):
    # lo dice, y esos ficheros no son «sin UC». Si alguna UC reclama ficheros, se juzga todo (una UC
    # de plan viejo citada en un commit no esconde los desvíos de la otra). Una UC que el tablero no
    # tiene, una cerrada o una sin plan no frena nada: sus ficheros cuentan como «sin UC».
    claiming = {u for _, ucs in claims for u in ucs if u in mine} | {u for u in branch if receipt_files.get(u)}
    known = {k.upper() for k in known_ucs} if known_ucs is not None else set()
    done = {k.upper() for k in done_ucs or ()}
    old_plan = [] if claiming else _old_plan_ucs(docs, branch, known, claiming, done)
    not_judged = list(unclaimed) if old_plan else []
    if not_judged:
        unclaimed = []
    judgeable = not not_judged
    touches = closed_uc_touches(
        closed or [], [f["path"] for f in report_files if "excluded_by" not in f], branch, repo=repo, satellite=satellite,
    )
    out: dict[str, Any] = {
        "uc_ids": branch,
        "plans": [
            {"path": path, "contract_version": c.contract_version, "ucs": c.named_ucs, "owner": owner}
            for path, c, owner, _ in docs
        ],
        "files": report_files,
        "unclaimed": unclaimed,
        "not_judged": not_judged,
        "judgeable": judgeable,
        "old_plan_ucs": old_plan,
        "exclude": [p for p, _ in patterns],
        "excluded": excluded,
        "dependencies": {"added": added, "undeclared": undeclared, "plans_without_section": plans_without_section},
        "closed_touches": touches["touches"],
        "closed_touches_total": touches["touches_total"],
        "closed_without_files": touches["closed_without_files"],
        "ok": not unclaimed and not undeclared,
    }
    if known_ucs is not None:
        out["unknown_ucs"] = [u for u in branch if u not in {k.upper() for k in known_ucs}]
    notes: list[str] = []
    if not branch:
        notes.append("La rama no nombra ninguna UC (asuntos de los commits, nombre de la rama ni marcador): todo queda «sin UC».")
    if not judgeable:
        notes.append(
            f"Los planes de {', '.join(old_plan)} no declaran ficheros por fase (anteriores al contrato) y sus "
            "recibos no traen `files`: la puerta no puede decir qué fichero es de qué UC y no juzga "
            f"{len(not_judged)} fichero(s). Los planes nuevos de /plan traen las líneas **Ficheros:**."
        )
    elif docs and all(c.contract_version == 0 for _, c, _, _ in docs):
        notes.append("Los planes de estas UC son anteriores al contrato (sin **Criterios:**/**Ficheros:**): solo cuentan los recibos.")
    if not docs and branch:
        notes.append("No se encontró el plan de estas UC en el orquestador: solo cuentan los recibos de sus criterios.")
    if known_ucs is None and branch:
        notes.append("No se pudo leer el tablero: no se sabe si estas UC existen, y sus ficheros se juzgan solo con el plan.")
    if notes:
        out["notes"] = notes
    return out
