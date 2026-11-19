"""check_plan_contract — el plan relaciona cada criterio con su fase y sus ficheros (US-126 · UC-12604).

Pura: recibe el texto del plan y los criterios de sus UC; no lee ni guarda nada. /plan la llama antes
de entregar un plan, y /implement al empezar para saber si puede enlazar cada criterio con su fase.
"""

from __future__ import annotations

from typing import Any

from ..plan_contract import CONTRACT_NOTICE_OLD_PLAN, incomplete_phases, parse_plan_contract, uncovered_criteria

DEPS_MISSING_NOTICE = (
    "El plan no tiene la sección «## Dependencias nuevas»: escribe una línea por paquete "
    "(«- pypi: nombre», «- npm: nombre») o «Ninguna». La puerta de desviación compara con ella."
)


async def check_plan_contract(
    plan_content: str,
    uc_criteria: dict[str, list[str]] | None = None,
    default_uc: str | None = None,
) -> dict[str, Any]:
    """Check what a plan declares per phase (UC-12604).

    `plan_content` is the plan's text. `uc_criteria` maps each UC of the plan to its criteria ids
    ({"UC-12604": ["AC-01", ...]}); `default_uc` is the UC of a criterion written without it (only
    when the plan names no other UC). Returns contract_version (1 when at least one **Criterios:**
    line outside a code block names a criterion; 0 for an older plan, with a `notice`: /implement
    still works with it, without linking criteria to phases), the phases with their criteria and
    files, the new dependencies, `uncovered` (criteria no phase covers), `incomplete_phases` (phases
    without the **Criterios:** or the **Ficheros:** line), `unattributed` (criteria without their UC
    in a plan of several UCs) and `ok`, true only when none of the three lists has anything.
    """
    contract = parse_plan_contract(plan_content or "", default_uc=default_uc)
    out: dict[str, Any] = {"success": True, **contract.as_dict()}
    if contract.contract_version == 0:
        out["ok"] = False
        out["notice"] = CONTRACT_NOTICE_OLD_PLAN
        return out
    missing = uncovered_criteria(contract, uc_criteria or {})
    incomplete = incomplete_phases(contract)
    unattributed = contract.unattributed()
    out["uncovered"] = missing
    out["incomplete_phases"] = incomplete
    out["unattributed"] = unattributed
    out["ok"] = not (missing or incomplete or unattributed)
    warnings: list[str] = []
    if missing:
        listed = "; ".join(f"{uc}: {', '.join(acs)}" for uc, acs in missing.items())
        warnings.append(f"Criterios que ninguna fase cubre ({listed}): añádelos a la línea **Criterios:** de su fase.")
    if incomplete:
        listed = "; ".join(f"{p['phase']} (sin {' ni '.join(p['missing'])})" for p in incomplete)
        warnings.append(f"Fases sin sus líneas: {listed}. Cada fase lleva **Criterios:** y **Ficheros:**.")
    if unattributed:
        listed = "; ".join(f"{u['phase']}: {u['ac_id']}" for u in unattributed)
        warnings.append(
            f"El plan tiene varias UC y estos criterios no dicen de cuál son ({listed}): "
            "escribe la UC delante («UC-XXXX AC-01»)."
        )
    if contract.dependencies is None:
        warnings.append(DEPS_MISSING_NOTICE)
    if warnings:
        out["warnings"] = warnings
    return out


def register_plan_contract_tools(mcp_instance) -> None:
    """Registra ``check_plan_contract`` (US-126 · UC-12604)."""
    mcp_instance.tool(
        description="Check a plan's contract (pure: pass its text as plan_content and the criteria "
        "of its UCs as uc_criteria {UC: [AC, ...]}). Returns contract_version (1 when a **Criterios:** "
        "line outside a code block names a criterion, 0 for an older plan, with a notice), the "
        "phases with their criteria and files, the plan's «Dependencias nuevas», uncovered "
        "(criteria no phase covers), incomplete_phases (phases missing the **Criterios:** or "
        "**Ficheros:** line), unattributed (criteria without their UC in a plan of several UCs) "
        "and ok. /plan calls it before delivering a plan; /implement at the start."
    )(check_plan_contract)
