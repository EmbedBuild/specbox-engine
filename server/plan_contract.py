"""El contrato de un plan de /plan: fases, criterios, ficheros y dependencias (US-126 · UC-12604).

Desde UC-12604 cada fase del plan lleva dos líneas que se pueden leer:

    ### Fase 2: Retirar sin renumerar
    **Criterios:** UC-12501 AC-01, AC-03
    **Ficheros:** server/tools/spec_mutations.py, server/backends/native_backend.py

y el plan tiene una sección ``## Dependencias nuevas`` con una línea por paquete (``- pypi: rapidfuzz``)
o la palabra «Ninguna». Este módulo es puro (no lee disco): recibe el texto del plan.

``contract_version`` es 1 si al menos una línea ``**Criterios:**`` nombra algún criterio (``AC-NN``)
fuera de un bloque de código, y 0 si no: un plan anterior, o uno que solo trae líneas sueltas de
ficheros. Un plan de contrato 0 no se adivina: no tiene fases y quien lo use dice que la relación
entre fases y criterios no está. Lo que va dentro de un bloque de código (``` o ~~~) es un ejemplo y
no cuenta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_HEADING = re.compile(r"^(#{2,4})\s+(.+?)\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
#: «Fase 2: …», «Fase 2. …», «Fase 2 · …», «Fase 2 (UC-1) …», «Fase 2» sola; no «Fase 2 bloqueada» ni
#: «Fase 2.1».
_PHASE_TITLE = re.compile(r"^(?:\W+\s*)?(?:fase|phase)\s+(\d+)\s*(?:[:·—–(\[-]|\.(?!\d)|$)", re.IGNORECASE)
#: La UC de una fase: al principio del título, o justo tras «Fase N» (entre paréntesis o corchetes, o
#: tras «·», «:» o una raya). Una UC citada más adelante en el título no es la de la fase.
_HEADING_UC = re.compile(
    r"^(?:\W+\s*)?(UC-\d+[a-z]?)\b"
    r"|^(?:\W+\s*)?(?:fase|phase)\s+\d+\s*(?:[(\[]\s*|[:.·—–-]\s*)(UC-\d+[a-z]?)\b",
    re.IGNORECASE,
)
#: Una casilla de criterio («- [ ] UC-1 AC-01», «- [x] AC-02: texto»), que sí es parte de la lista.
_CRITERION_ITEM = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s+\**\s*(?:UC-\d+[a-z]?\b|AC-\d+\b)", re.IGNORECASE)
_CHECKBOX = re.compile(r"^\s*[-*]\s+\[[ xX]\]")
_CRITERIA_LINE = re.compile(r"^\s*[-*]?\s*\*\*Criterios:?\*\*:?\s*(.*)$", re.IGNORECASE)
_FILES_LINE = re.compile(r"^\s*[-*]?\s*\*\*Ficheros:?\*\*:?\s*(.*)$", re.IGNORECASE)
_LIST_ITEM = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_RANGE = re.compile(
    r"\bAC-(\d+)\s*(?:\.\.|–|—|\ba\b|\bal\b|\bhasta\b|\bto\b)\s*(?:AC-)?(\d+)\b", re.IGNORECASE
)
_TOKEN = re.compile(r"\b(UC-\d+[a-z]?)\b|\bAC-(\d+)\b", re.IGNORECASE)
_BACKTICKED = re.compile(r"`([^`]+)`")
_ANNOTATION = re.compile(r"\s+\([^)]*\)\s*$")
_DEPS_HEADING = re.compile(r"^##\s+Dependencias\s+nuevas\b", re.IGNORECASE)
_DEP_LINE = re.compile(r"^\s*[-*]\s+`?([A-Za-z]+)`?\s*:\s*(.+?)\s*$")
_NONE_WORDS = {"ninguna", "ninguno", "none", "-", "—"}
#: Los gestores de paquetes que la sección «Dependencias nuevas» entiende; otra palabra antes de «:»
#: (una nota, por ejemplo) no es un paquete.
ECOSYSTEMS = frozenset({
    "pypi", "pip", "npm", "pnpm", "yarn", "pub", "dart", "go", "cargo", "gem", "maven", "gradle",
    "nuget", "composer", "brew", "apt", "docker",
})

CONTRACT_NOTICE_OLD_PLAN = (
    "El plan no relaciona fases y criterios (no tiene líneas **Criterios:** ni **Ficheros:** en sus "
    "fases): la comparación con el plan y la fase de cada criterio no están disponibles. Los planes "
    "nuevos de /plan las llevan."
)


def ac_key(number: str | int) -> str:
    """``AC-1`` y ``AC-01`` son el mismo criterio: el id con al menos dos cifras."""
    return f"AC-{int(number):02d}"


def _heading_uc(title: str) -> str | None:
    match = _HEADING_UC.search(title)
    if not match:
        return None
    return next(g for g in match.groups() if g).upper()


def _dep_names(text: str) -> list[str]:
    """``rapidfuzz, `httpx>=0.27` `` → [rapidfuzz, httpx>=0.27]; la primera palabra de cada trozo."""
    out: list[str] = []
    for part in re.split(r"[,;]", text):
        words = part.strip().strip("`").split()
        name = words[0].strip("`") if words else ""
        if name and name.lower() not in _NONE_WORDS and name not in out:
            out.append(name)
    return out


def normalize_ac(ac_id: str) -> str:
    match = re.fullmatch(r"\s*AC-(\d+)\s*", ac_id or "", re.IGNORECASE)
    return ac_key(match[1]) if match else (ac_id or "").upper()


@dataclass
class Phase:
    """Una fase del plan con lo que declara."""

    title: str
    criteria: list[tuple[str | None, str]] = field(default_factory=list)  # (UC, AC)
    files: list[str] = field(default_factory=list)
    has_criteria_line: bool = False
    has_files_line: bool = False
    uc: str | None = None  # la UC que nombra su encabezado

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "criteria": [{"uc_id": uc, "ac_id": ac} for uc, ac in self.criteria],
            "files": list(self.files),
            "declares_criteria": self.has_criteria_line,
            "declares_files": self.has_files_line,
        }


@dataclass
class PlanContract:
    """Lo que el plan declara: sus fases, sus dependencias nuevas y la versión del contrato."""

    phases: list[Phase]
    dependencies: list[dict[str, str]] | None  # None = el plan no tiene la sección
    contract_version: int
    named_ucs: list[str] = field(default_factory=list)  # las UC que nombran criterios o fases

    @property
    def ambiguous(self) -> bool:
        """El plan nombra varias UC: un criterio escrito sin la suya no se atribuye a ninguna."""
        return len(self.named_ucs) > 1

    def unattributed(self) -> list[dict[str, str]]:
        """Los criterios sin UC de un plan de varias UC (no se sabe de cuál son)."""
        if not self.ambiguous:
            return []
        return [{"phase": p.title, "ac_id": ac} for p in self.phases for uc, ac in p.criteria if uc is None]

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "phases": [p.as_dict() for p in self.phases],
            "dependencies": self.dependencies,
        }


def _criteria_of(text: str, uc: str | None) -> list[tuple[str | None, str]]:
    """``UC-12501 AC-01, AC-03; UC-12502 AC-02`` → [(UC-12501, AC-01), (UC-12501, AC-03), (UC-12502, AC-02)].

    Un rango (``AC-01 a AC-04``, ``AC-01..AC-04``, ``AC-01–AC-04``) cubre todos los de en medio.
    """
    expanded = _RANGE.sub(
        lambda m: ", ".join(ac_key(n) for n in range(int(m[1]), int(m[2]) + 1))
        if int(m[1]) <= int(m[2]) and int(m[2]) - int(m[1]) < 100 else m[0],
        text,
    )
    out: list[tuple[str | None, str]] = []
    current = uc
    for match in _TOKEN.finditer(expanded):
        if match.group(1):
            current = match.group(1).upper()
        else:
            pair = (current, ac_key(match.group(2)))
            if pair not in out:
                out.append(pair)
    return out


def _files_of(text: str) -> list[str]:
    """Las rutas de una línea de ficheros, separadas por comas o punto y coma. En un trozo con comillas
    invertidas cuentan las que van entre ellas («`a.py` y `b.py`»); en uno sin ellas, el trozo entero
    sin la anotación final entre paréntesis («server/x.py (nuevo)»)."""
    out: list[str] = []
    for part in re.split(r"[,;]", text):
        quoted = _BACKTICKED.findall(part)
        for raw in quoted or [part]:
            path = _ANNOTATION.sub("", raw.strip().strip("`").strip()).strip()
            if path and path.lower() not in _NONE_WORDS and path not in out:
                out.append(path)
    return out


def parse_plan_contract(plan_content: str, *, default_uc: str | None = None) -> PlanContract:
    """Las fases, las dependencias nuevas y la versión del contrato.

    Una fase es un encabezado ``##``–``####`` cuyo título empieza por «Fase N» (aunque no traiga las
    líneas, para poder decir que le faltan) o cualquier encabezado con una línea de criterios o de
    ficheros debajo. Las líneas pueden traer el contenido detrás o en una lista justo debajo.
    ``default_uc`` es la UC de un criterio escrito sin la suya, solo si el plan no nombra otra.
    """
    phases: list[Phase] = []
    current: Phase | None = None
    in_deps = False
    fence: str | None = None  # la marca que abrió el bloque de código («```», «````», «~~~»)
    deps: list[dict[str, str]] | None = None
    collecting: str | None = None  # "criteria" | "files": la lista que sigue a una línea vacía
    collected = 0

    def _register(phase: Phase) -> None:
        if not any(p is phase for p in phases):
            phases.append(phase)

    for line in (plan_content or "").splitlines():
        opener = _FENCE.match(line)
        if fence is not None:
            # Solo lo cierra una marca del mismo carácter y al menos igual de larga, sola en su línea.
            if opener and opener[1][0] == fence[0] and len(opener[1]) >= len(fence) and not line.strip()[len(opener[1]):].strip():
                fence = None
            continue
        if opener:
            fence = opener[1]
            collecting = None
            continue
        heading = _HEADING.match(line)
        if heading:
            collecting = None
            in_deps = bool(_DEPS_HEADING.match(line))
            if in_deps:
                deps = deps if deps is not None else []
                current = None
                continue
            title = heading.group(2).strip()
            current = Phase(title=title, uc=_heading_uc(title))
            if _PHASE_TITLE.match(title):
                _register(current)
            continue
        if in_deps:
            dep = _DEP_LINE.match(line)
            if dep and deps is not None and dep.group(1).lower() in ECOSYSTEMS:
                for name in _dep_names(dep.group(2)):
                    entry = {"ecosystem": dep.group(1).lower(), "name": name}
                    if entry not in deps:
                        deps.append(entry)
            continue
        if current is None:
            continue
        if collecting:
            item = _LIST_ITEM.match(line)
            # La lista acaba en la primera línea en blanco tras algún elemento o en una tarea «- [ ]»
            # (una casilla que empieza por su criterio sí es de la lista de criterios).
            is_criterion = collecting == "criteria" and _CRITERION_ITEM.match(line)
            if item and (not _CHECKBOX.match(line) or is_criterion):
                collected += 1
                if collecting == "criteria":
                    current.criteria += [c for c in _criteria_of(item[1], current.uc) if c not in current.criteria]
                else:
                    current.files += [f for f in _files_of(item[1]) if f not in current.files]
                continue
            if not line.strip() and not collected:
                continue
            collecting = None
        crit = _CRITERIA_LINE.match(line)
        if crit:
            current.has_criteria_line = True
            current.criteria += [c for c in _criteria_of(crit.group(1), current.uc) if c not in current.criteria]
            collecting = "criteria" if not crit.group(1).strip() else None
            collected = 0
            _register(current)
            continue
        files = _FILES_LINE.match(line)
        if files:
            current.has_files_line = True
            current.files += [f for f in _files_of(files.group(1)) if f not in current.files]
            collecting = "files" if not files.group(1).strip() else None
            collected = 0
            _register(current)

    if not any(p.criteria for p in phases):
        return PlanContract(phases=[], dependencies=deps, contract_version=0)

    named: list[str] = []
    for phase in phases:
        for uc in [phase.uc, *(c[0] for c in phase.criteria)]:
            if uc and uc not in named:
                named.append(uc)
    default = (default_uc or "").upper() or None
    if default and (not named or named == [default]):
        for phase in phases:
            phase.criteria = list(dict.fromkeys((uc or default, ac) for uc, ac in phase.criteria))
        named = [default]
    return PlanContract(phases=phases, dependencies=deps, contract_version=1, named_ucs=named)


def incomplete_phases(contract: PlanContract) -> list[dict[str, Any]]:
    """Las fases a las que les falta la línea de criterios o la de ficheros (UC-12604 AC-01)."""
    out: list[dict[str, Any]] = []
    for phase in contract.phases:
        missing = [name for name, has in (("Criterios", phase.has_criteria_line), ("Ficheros", phase.has_files_line)) if not has]
        if missing:
            out.append({"phase": phase.title, "missing": missing})
    return out


def _matches(contract: PlanContract, uc: str | None, uc_id: str) -> bool:
    if uc is not None:
        return uc == uc_id.upper()
    # Un criterio sin UC solo es de esta UC si el plan no nombra varias.
    return not contract.ambiguous


def uncovered_criteria(contract: PlanContract, uc_criteria: dict[str, list[str]]) -> dict[str, list[str]]:
    """Los criterios de cada UC que no aparecen en ninguna fase (UC-12604 AC-01)."""
    covered = {(uc, ac) for phase in contract.phases for uc, ac in phase.criteria}
    single = len(uc_criteria) == 1
    out: dict[str, list[str]] = {}
    for uc_id, acs in uc_criteria.items():
        missing = [
            ac for ac in acs
            if (uc_id.upper(), normalize_ac(ac)) not in covered
            and not (single and not contract.ambiguous and (None, normalize_ac(ac)) in covered)
        ]
        if missing:
            out[uc_id] = missing
    return out


def phase_of(contract: PlanContract, uc_id: str, ac_id: str) -> Phase | None:
    """La primera fase que cubre el criterio, o None."""
    key = normalize_ac(ac_id)
    for phase in contract.phases:
        for uc, ac in phase.criteria:
            if ac == key and _matches(contract, uc, uc_id):
                return phase
    return None


def _title_key(title: str) -> str:
    return " ".join((title or "").split()).casefold()


def _covers(contract: PlanContract, phase: Phase, uc_id: str, ac_id: str) -> bool:
    key = normalize_ac(ac_id)
    return any(ac == key and _matches(contract, uc, uc_id) for uc, ac in phase.criteria)


def phase_named(contract: PlanContract, title: str, uc_id: str, ac_id: str) -> Phase | None:
    """La fase del plan que nombra un recibo, para ese criterio.

    Con el mismo título: la que cubre la UC y el criterio, o la única con ese título. Si no hay ninguna
    con ese título y es «Fase N» (el plan se renumeró o el recibo abrevia), solo una fase N que cubra
    la UC y el criterio. Si no, None: quien llama usa la primera fase que nombra el criterio.
    """
    same = [p for p in contract.phases if _title_key(p.title) == _title_key(title)]
    covering = [p for p in same if _covers(contract, p, uc_id, ac_id)]
    if covering:
        return covering[0]
    if len(same) == 1:
        return same[0]
    if same:
        return None
    number = _PHASE_TITLE.match(title or "")
    if number:
        for phase in contract.phases:
            own = _PHASE_TITLE.match(phase.title)
            if own and own[1] == number[1] and _covers(contract, phase, uc_id, ac_id):
                return phase
    return None


def expected_files(contract: PlanContract) -> list[str]:
    """Todos los ficheros que el plan espera tocar, en el orden en que aparecen."""
    out: list[str] = []
    for phase in contract.phases:
        out += [f for f in phase.files if f not in out]
    return out
