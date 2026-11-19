"""El radio de impacto de un plan (US-126 · UC-12606): sus fases con contrato de API o migración.

El hook ``impact-radius-guard`` clasifica cada commit por sus ficheros (``.claude/hooks/lib/impact-radius.mjs``)
y, con la medida ``impact_radius`` en «block», detiene el de contrato de API o de migración de datos
hasta que una persona lo aprueba. Este módulo hace lo mismo con los ficheros que el plan declara por
fase (``**Ficheros:**``) para que el triaje de /implement pregunte una vez, por adelantado.

Solo las reglas por defecto, que comparten los dos (una prueba lo comprueba): el servidor es
compartido y no compara globs que mande el cliente. Puro: no lee disco.
"""

from __future__ import annotations

import re
from typing import Any

from .plan_contract import parse_plan_contract

LABELS = {"api_contract": "contrato de API", "data_migration": "migración de datos"}


#: Los globs del proyecto que admite el triaje (los mismos topes que la puerta de desviación).
MAX_IMPACT_GLOBS = 20
_DOC_RE = re.compile(r"\.(md|markdown|txt|rst)$", re.IGNORECASE)
_SEED_RE = re.compile(r"(^|/)(seeds?|fixtures?|tests?|__tests__|spec)/|(^|/)seed[^/]*$", re.IGNORECASE)
_IN_MIGRATION_DIR_RE = re.compile(r"(^|/)(migrations|alembic/versions|db/migrate)/")


def _seed_or_fixture(path: str) -> bool:
    """Semillas y datos de prueba fuera de una carpeta de migraciones (dentro de una, cuentan)."""
    return bool(_SEED_RE.search(path)) and not _IN_MIGRATION_DIR_RE.search(path)


def _clean(path: str) -> str:
    p = (path or "").strip().strip("`").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def classify_path(path: str) -> str | None:
    """``api_contract``, ``data_migration`` o None (dependencias o interno) para una ruta del plan.

    Las mismas reglas por defecto que el hook (``DEFAULT_API`` y ``DEFAULT_MIGRATION`` de
    lib/impact-radius.mjs; una prueba lo compara).
    """
    p = _clean(path)
    if not p:
        return None
    base = p.rstrip("/").rsplit("/", 1)[-1]
    if (base.startswith(("openapi", "swagger")) and base.endswith((".yaml", ".yml", ".json"))) \
            or base.endswith((".proto", ".graphqls")) or (base.startswith("schema") and base.endswith(".graphql")):
        return "api_contract"
    if _DOC_RE.search(base) or _seed_or_fixture(p):
        return None
    folder = f"/{p}" if p.endswith("/") else f"/{p.rsplit('/', 1)[0]}/" if "/" in p else "/"
    if any(seg in folder or seg in f"/{p}/" for seg in ("/migrations/", "/alembic/versions/", "/db/migrate/")) \
            or base.endswith(".sql") or base == "schema.prisma":
        return "data_migration"
    return None


class ImpactConfigError(ValueError):
    """Los globs del proyecto no son válidos."""


def _matchers(impact: dict[str, Any] | None) -> dict[str, list]:
    from .drift import MAX_EXCLUDE_LEN, MAX_EXCLUDE_WILDCARDS, glob_matcher

    out: dict[str, list] = {"api_globs": [], "migration_globs": [], "signature_globs": []}
    if not impact:
        return out
    if not isinstance(impact, dict):
        raise ImpactConfigError("impact tiene que ser {api_globs, migration_globs, signature_globs}")
    for key in out:
        globs = impact.get(key) or []
        if not isinstance(globs, list) or len(globs) > MAX_IMPACT_GLOBS or not all(
            isinstance(g, str) and len(g) <= MAX_EXCLUDE_LEN and g.count("*") + g.count("?") <= MAX_EXCLUDE_WILDCARDS
            for g in globs
        ):
            raise ImpactConfigError(
                f"{key}: hasta {MAX_IMPACT_GLOBS} globs de hasta {MAX_EXCLUDE_LEN} caracteres y {MAX_EXCLUDE_WILDCARDS} comodines"
            )
        out[key] = [glob_matcher(g) for g in globs if g.strip()]
    return out


def plan_impact(plan_content: str | None, impact: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Las fases del plan con contrato de API o migración de datos: ``{phase, class, label, files}``.

    Con ``impact`` (los globs del proyecto, ``specbox.impact``), también sus rutas de contrato o de
    migración y los ficheros de firmas, que pueden cambiar el contrato si cambian sus parámetros.
    """
    from .drift import GlobBudget

    matchers = _matchers(impact)
    budget = GlobBudget()
    contract = parse_plan_contract(plan_content or "")
    out: list[dict[str, Any]] = []
    for phase in contract.phases:
        found: dict[str, list[str]] = {}
        for raw in phase.files:
            path = _clean(raw)
            cls = classify_path(path)
            if cls is None and any(m(path, budget) for m in matchers["api_globs"]):
                cls = "api_contract"
            if cls is None and not _DOC_RE.search(path) and not _seed_or_fixture(path) \
                    and any(m(path, budget) for m in matchers["migration_globs"]):
                cls = "data_migration"
            if cls is None and any(m(path, budget) for m in matchers["signature_globs"]):
                cls = "api_contract"
                path = f"{path} (si cambia la firma de una función pública)"
            if cls:
                found.setdefault(cls, []).append(path)
        for cls in ("api_contract", "data_migration"):
            if found.get(cls):
                out.append({"phase": phase.title, "class": cls, "label": LABELS[cls], "files": found[cls]})
    return out


def impact_decision(plan_content: str | None, *, mode: str | None = None,
                    impact: dict[str, Any] | None = None) -> dict[str, str] | None:
    """La decisión del triaje (``impact_radius_approval``) si el plan toca contrato o migración.

    Con ``mode`` (el de la medida en el tablero), solo en «block»: en «warn» u «off» no hay nada que
    aprobar y el triaje no pregunta. Sin él, pregunta (el lado seguro).
    """
    if mode is not None and mode != "block":
        return None
    phases = plan_impact(plan_content, impact)
    if not phases:
        return None
    parts = [f"{p['phase']}: {p['label']} ({', '.join(p['files'][:3])}{'…' if len(p['files']) > 3 else ''})"
             for p in phases[:5]]
    more = f" y {len(phases) - 5} más" if len(phases) > 5 else ""
    return {
        "description": (
            "El plan cambia un contrato de API o una migración de datos (" + "; ".join(parts) + more + "). "
            "Con la medida impact_radius en «block», esos commits necesitan la aprobación de una persona: "
            "si la das ahora, queda registrada (skip_enforcement con measure=\"impact_radius\", una por fase) "
            "y el commit no se detiene."
        ),
        "source": "plan · fases con contrato de API o migración de datos",
        "decision_key": "impact_radius_approval",
    }
