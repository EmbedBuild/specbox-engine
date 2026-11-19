"""El contrato de un plan de /plan: fases, criterios, ficheros y dependencias (US-126 · UC-12604).

Desde UC-12604 cada fase del plan lleva dos líneas que se pueden leer:

    ### Fase 2: Retirar sin renumerar
    **Criterios:** UC-12501 AC-01, AC-03
    **Ficheros:** server/tools/spec_mutations.py, server/backends/native_backend.py

y el plan tiene una sección ``## Dependencias nuevas`` con una línea por paquete (``- pypi: rapidfuzz``)
o la palabra «Ninguna». Este módulo es puro (no lee disco): recibe el texto del plan.

``contract_version`` es 1 si alguna fase trae esas líneas y 0 si el plan es anterior. Un plan de
contrato 0 no se adivina: quien lo use dice que la relación entre fases y criterios no está.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
_CRITERIA_LINE = re.compile(r"^\s*[-*]?\s*\*\*Criterios:?\*\*:?\s*(.*)$", re.IGNORECASE)
_FILES_LINE = re.compile(r"^\s*[-*]?\s*\*\*Ficheros:?\*\*:?\s*(.*)$", re.IGNORECASE)
_TOKEN = re.compile(r"\b(UC-\d+[a-z]?)\b|\b(AC-\d+)\b", re.IGNORECASE)
_DEPS_HEADING = re.compile(r"^##\s+Dependencias\s+nuevas\b", re.IGNORECASE)
_DEP_LINE = re.compile(r"^\s*[-*]\s+(?:`)?([A-Za-z0-9_.-]+)\s*:\s*([^`\s]+)(?:`)?")
_NONE_WORDS = {"ninguna", "ninguno", "none", "-", "—"}

CONTRACT_NOTICE_OLD_PLAN = (
    "El plan no relaciona fases y criterios (no tiene líneas **Criterios:** ni **Ficheros:** en sus "
    "fases): la comparación con el plan y la fase de cada criterio no están disponibles. Los planes "
    "nuevos de /plan las llevan."
)


@dataclass
class Phase:
    """Una fase del plan con lo que declara."""

    title: str
    criteria: list[tuple[str | None, str]] = field(default_factory=list)  # (UC, AC)
    files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "criteria": [{"uc_id": uc, "ac_id": ac} for uc, ac in self.criteria],
            "files": list(self.files),
        }


@dataclass
class PlanContract:
    """Lo que el plan declara: sus fases, sus dependencias nuevas y la versión del contrato."""

    phases: list[Phase]
    dependencies: list[dict[str, str]] | None  # None = el plan no tiene la sección
    contract_version: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "phases": [p.as_dict() for p in self.phases],
            "dependencies": self.dependencies,
        }


def _criteria_of(text: str, default_uc: str | None) -> list[tuple[str | None, str]]:
    """``UC-12501 AC-01, AC-03; UC-12502 AC-02`` → [(UC-12501, AC-01), (UC-12501, AC-03), (UC-12502, AC-02)]."""
    out: list[tuple[str | None, str]] = []
    current = default_uc
    for match in _TOKEN.finditer(text):
        if match.group(1):
            current = match.group(1).upper()
        else:
            pair = (current, match.group(2).upper())
            if pair not in out:
                out.append(pair)
    return out


def _files_of(text: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"[,;]", text):
        path = part.strip().strip("`").strip()
        if path and path.lower() not in _NONE_WORDS and path not in out:
            out.append(path)
    return out


def parse_plan_contract(plan_content: str, *, default_uc: str | None = None) -> PlanContract:
    """Las fases (un encabezado ``##``–``####`` con una línea de criterios o de ficheros debajo), las
    dependencias nuevas y la versión del contrato. ``default_uc`` es la UC de un criterio escrito sin
    su UC (un plan de una sola UC)."""
    phases: list[Phase] = []
    current: Phase | None = None
    in_deps = False
    deps: list[dict[str, str]] | None = None
    for line in (plan_content or "").splitlines():
        heading = _HEADING.match(line)
        if heading:
            in_deps = bool(_DEPS_HEADING.match(line))
            if in_deps:
                deps = deps if deps is not None else []
                current = None
                continue
            current = Phase(title=heading.group(2).strip())
            continue
        if in_deps:
            dep = _DEP_LINE.match(line)
            if dep and deps is not None:
                entry = {"ecosystem": dep.group(1).lower(), "name": dep.group(2)}
                if entry not in deps:
                    deps.append(entry)
            continue
        if current is None:
            continue
        crit = _CRITERIA_LINE.match(line)
        if crit:
            current.criteria += [c for c in _criteria_of(crit.group(1), default_uc) if c not in current.criteria]
            if not any(p is current for p in phases):
                phases.append(current)
            continue
        files = _FILES_LINE.match(line)
        if files:
            current.files += [f for f in _files_of(files.group(1)) if f not in current.files]
            if not any(p is current for p in phases):
                phases.append(current)
    return PlanContract(phases=phases, dependencies=deps, contract_version=1 if phases else 0)


def uncovered_criteria(contract: PlanContract, uc_criteria: dict[str, list[str]]) -> dict[str, list[str]]:
    """Los criterios de cada UC que no aparecen en ninguna fase (UC-12604 AC-01)."""
    covered = {(uc, ac) for phase in contract.phases for uc, ac in phase.criteria}
    single = len(uc_criteria) == 1
    out: dict[str, list[str]] = {}
    for uc_id, acs in uc_criteria.items():
        missing = [
            ac for ac in acs
            if (uc_id.upper(), ac.upper()) not in covered and not (single and (None, ac.upper()) in covered)
        ]
        if missing:
            out[uc_id] = missing
    return out


def phase_of(contract: PlanContract, uc_id: str, ac_id: str) -> Phase | None:
    """La primera fase que cubre el criterio, o None."""
    for phase in contract.phases:
        for uc, ac in phase.criteria:
            if ac == ac_id.upper() and (uc is None or uc == uc_id.upper()):
                return phase
    return None


def expected_files(contract: PlanContract) -> list[str]:
    """Todos los ficheros que el plan espera tocar, en el orden en que aparecen."""
    out: list[str] = []
    for phase in contract.phases:
        out += [f for f in phase.files if f not in out]
    return out
