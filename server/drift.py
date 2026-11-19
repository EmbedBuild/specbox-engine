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


def glob_matcher(pattern: str):
    """Un glob del proyecto (como en .gitignore) → ``match(ruta) -> bool``.

    ``**`` cruza carpetas y ``*`` y ``?`` no. Un patrón sin «/» vale en cualquier carpeta; uno que
    empieza por «/» solo en la raíz; un nombre sin comodines (``docs``) cubre también lo que hay dentro.
    """
    pat = (pattern or "").strip().replace("\\", "/")
    anchored = pat.startswith("/")
    pat = pat.lstrip("/")
    while pat.startswith("./"):
        pat = pat[2:]
    if not pat:
        return lambda path: False
    if pat.endswith("/"):
        pat += "**"
    if not anchored and "/" not in pat.rstrip("/"):
        pat = "**/" + pat
    whole = _glob_tokens(pat)
    inside = _glob_tokens(pat + "/**") if not pat.endswith("**") else None

    def match(path: str) -> bool:
        return _glob_match(whole, path) or (inside is not None and _glob_match(inside, path))

    return match


def _covers(entry: str, path: str) -> bool:
    entry = normalize_path(entry)
    return path == entry or (entry.endswith("/") and path.startswith(entry))


def plan_claims(contracts: list[PlanContract], branch: set[str]) -> list[tuple[str, frozenset[str | None]]]:
    """``(fichero o carpeta del plan, UC de los criterios de su fase)`` de los planes con contrato.

    Una fase cuyos criterios no dicen su UC la reclama con ``None`` (vale para cualquier UC de la
    rama) solo si el plan no nombra otras UC que las de la rama: el plan de otra UC que solo cita una
    de la rama no le da por buenos sus ficheros.
    """
    out: list[tuple[str, frozenset[str | None]]] = []
    for contract in contracts:
        if contract.contract_version == 0:
            continue
        own_plan = all(u in branch for u in contract.named_ucs)
        for phase in contract.phases:
            ucs = frozenset(uc for uc, _ in phase.criteria) or frozenset({phase.uc})
            if None in ucs and not own_plan:
                ucs = frozenset(u for u in ucs if u is not None)
            if ucs:
                out += [(f, ucs) for f in phase.files]
    return out


def build_drift_report(
    *,
    files: list[str],
    uc_ids: list[str],
    contracts: list[tuple[str, PlanContract]],
    receipts: dict[str, set[str]] | None = None,
    closed: list[ClosedUc] | None = None,
    dependencies_added: list[dict[str, str]] | None = None,
    exclude: list[str] | None = None,
    known_ucs: set[str] | None = None,
    repo: str | None = None,
    satellite: str | None = None,
) -> dict[str, Any]:
    """El informe de la puerta (UC-12602 AC-01 a AC-04, UC-12603 AC-02 y AC-03).

    ``contracts`` son ``(ruta del plan, contrato)``; ``receipts``, los ficheros de los recibos de los
    criterios de cada UC de la rama; ``closed``, las UC cerradas con su lista; ``known_ucs``, las UC
    que existen en el tablero (None si no se pudo leer). ``ok`` es falso si queda algún fichero sin UC
    o alguna dependencia sin declarar.
    """
    branch = [u.upper() for u in dict.fromkeys(uc_ids)]
    mine = set(branch)
    patterns = [(p, glob_matcher(p)) for p in (exclude or []) if isinstance(p, str) and p.strip()]
    claims = plan_claims([c for _, c in contracts], mine)
    receipt_files = {uc.upper(): {normalize_path(f) for f in fs} for uc, fs in (receipts or {}).items()}

    report_files: list[dict[str, Any]] = []
    unclaimed: list[str] = []
    excluded: list[str] = []
    for raw in dict.fromkeys(normalize_path(f) for f in files if isinstance(f, str)):
        if not raw:
            continue
        rule = next((p for p, matches in patterns if matches(raw)), None)
        if rule:
            excluded.append(raw)
            report_files.append({"path": raw, "excluded_by": rule, "claimed_by": [], "source": None})
            continue
        by_plan = sorted({
            uc for entry, ucs in claims if _covers(entry, raw)
            for uc in (branch if None in ucs else [u for u in ucs if u in mine])
        })
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
    for path, contract in contracts:
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

    # Con UC pero sin nada que las relacione con ficheros (planes de contrato 0 y recibos sin
    # `files`), la puerta no puede juzgar: lo dice, pero esos ficheros no son «sin UC».
    judgeable = not branch or bool(claims) or any(receipt_files.get(u) for u in branch)
    not_judged = [] if judgeable else list(unclaimed)
    if not judgeable:
        unclaimed = []
    touches = closed_uc_touches(
        closed or [], [f["path"] for f in report_files if "excluded_by" not in f], branch, repo=repo, satellite=satellite,
    )
    out: dict[str, Any] = {
        "uc_ids": branch,
        "plans": [
            {"path": path, "contract_version": c.contract_version, "ucs": c.named_ucs} for path, c in contracts
        ],
        "files": report_files,
        "unclaimed": unclaimed,
        "not_judged": not_judged,
        "judgeable": judgeable,
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
            "Ningún plan de estas UC declara ficheros por fase (planes anteriores al contrato) y sus recibos no "
            "traen `files`: la puerta no puede decir qué fichero es de qué UC y no cuenta ninguno como «sin UC». "
            "Los planes nuevos de /plan traen las líneas **Ficheros:**."
        )
    elif contracts and all(c.contract_version == 0 for _, c in contracts):
        notes.append("Los planes de estas UC son anteriores al contrato (sin **Criterios:**/**Ficheros:**): solo cuentan los recibos.")
    if not contracts and branch:
        notes.append("No se encontró el plan de estas UC en el orquestador: solo cuentan los recibos de sus criterios.")
    if notes:
        out["notes"] = notes
    return out
