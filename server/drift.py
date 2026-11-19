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


def glob_regex(pattern: str) -> re.Pattern[str]:
    """Un glob del proyecto (``docs/**``, ``**/*.md``, ``*.lock``) como expresión: ``**`` cruza carpetas,
    ``*`` y ``?`` no. Un patrón sin «/» vale en cualquier carpeta (como en .gitignore)."""
    pat = normalize_path(pattern)
    if "/" not in pat.rstrip("/"):
        pat = "**/" + pat
    if pat.endswith("/"):
        pat += "**"
    out = ""
    i = 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pat.startswith("**", i):
            out += ".*"
            i += 2
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    return re.compile(f"^{out}$")


def _covers(entry: str, path: str) -> bool:
    entry = normalize_path(entry)
    return path == entry or (entry.endswith("/") and path.startswith(entry))


def plan_claims(contracts: list[PlanContract]) -> list[tuple[str, frozenset[str | None]]]:
    """``(fichero o carpeta del plan, UC de los criterios de su fase)`` de los planes con contrato.

    Una fase cuyos criterios no dicen su UC (plan de una sola UC) la reclama con ``None``: vale para
    cualquier UC de la rama.
    """
    out: list[tuple[str, frozenset[str | None]]] = []
    for contract in contracts:
        if contract.contract_version == 0:
            continue
        for phase in contract.phases:
            ucs = frozenset(uc for uc, _ in phase.criteria) or frozenset({phase.uc})
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
    patterns = [(p, glob_regex(p)) for p in (exclude or []) if isinstance(p, str) and p.strip()]
    claims = plan_claims([c for _, c in contracts])
    receipt_files = {uc.upper(): {normalize_path(f) for f in fs} for uc, fs in (receipts or {}).items()}

    report_files: list[dict[str, Any]] = []
    unclaimed: list[str] = []
    excluded: list[str] = []
    for raw in dict.fromkeys(normalize_path(f) for f in files if isinstance(f, str)):
        if not raw:
            continue
        rule = next((p for p, rx in patterns if rx.match(raw)), None)
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
    if contracts and all(c.contract_version == 0 for _, c in contracts):
        notes.append("Los planes de estas UC son anteriores al contrato (sin **Criterios:**/**Ficheros:**): solo cuentan los recibos.")
    if not contracts:
        notes.append("No se encontró el plan de estas UC en el orquestador: solo cuentan los recibos de sus criterios.")
    if notes:
        out["notes"] = notes
    return out
