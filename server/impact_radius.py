"""El radio de impacto de un plan (US-126 · UC-12606): sus fases con contrato de API o migración.

El hook ``impact-radius-guard`` clasifica cada commit por sus ficheros (``.claude/hooks/lib/impact-radius.mjs``)
y, con la medida ``impact_radius`` en «block», detiene el de contrato de API o de migración de datos
hasta que una persona lo aprueba. Este módulo hace lo mismo con los ficheros que el plan declara por
fase (``**Ficheros:**``) para que el triaje de /implement pregunte una vez, por adelantado.

Solo las reglas por defecto, que comparten los dos (una prueba lo comprueba): el servidor es
compartido y no compara globs que mande el cliente. Puro: no lee disco.
"""

from __future__ import annotations

from typing import Any

from .plan_contract import parse_plan_contract

LABELS = {"api_contract": "contrato de API", "data_migration": "migración de datos"}


def classify_path(path: str) -> str | None:
    """``api_contract``, ``data_migration`` o None (dependencias o interno) para una ruta del plan."""
    p = (path or "").strip().strip("`").replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")
    if not p:
        return None
    base = p.rstrip("/").rsplit("/", 1)[-1]
    if (base.startswith("openapi") and base.endswith((".yaml", ".yml", ".json"))) or base.endswith(".proto") \
            or base == "schema.graphql":
        return "api_contract"
    if "/migrations/" in f"/{p}" or (p.endswith("/") and base == "migrations") or base.endswith(".sql") \
            or p == "prisma/schema.prisma":
        return "data_migration"
    return None


def plan_impact(plan_content: str | None) -> list[dict[str, Any]]:
    """Las fases del plan con contrato de API o migración de datos: ``{phase, class, label, files}``."""
    contract = parse_plan_contract(plan_content or "")
    out: list[dict[str, Any]] = []
    for phase in contract.phases:
        found: dict[str, list[str]] = {}
        for path in phase.files:
            cls = classify_path(path)
            if cls:
                found.setdefault(cls, []).append(path)
        for cls in ("api_contract", "data_migration"):
            if found.get(cls):
                out.append({"phase": phase.title, "class": cls, "label": LABELS[cls], "files": found[cls]})
    return out


def impact_decision(plan_content: str | None) -> dict[str, str] | None:
    """La decisión del triaje (``impact_radius_approval``) si el plan toca contrato o migración."""
    phases = plan_impact(plan_content)
    if not phases:
        return None
    parts = [f"{p['phase']}: {p['label']} ({', '.join(p['files'][:3])}{'…' if len(p['files']) > 3 else ''})"
             for p in phases[:5]]
    more = f" y {len(phases) - 5} más" if len(phases) > 5 else ""
    return {
        "description": (
            "El plan cambia un contrato de API o una migración de datos (" + "; ".join(parts) + more + "). "
            "Con la medida impact_radius en «block», esos commits necesitan la aprobación de una persona: "
            "si la das ahora, queda registrada (skip_enforcement con measure=\"impact_radius\") y el commit no se detiene."
        ),
        "source": "plan · fases con contrato de API o migración de datos",
        "decision_key": "impact_radius_approval",
    }
