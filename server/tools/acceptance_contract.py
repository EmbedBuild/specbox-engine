"""check_acceptance_contract — el contrato de cada criterio antes de las pruebas (US-128 · UC-12801).

Pura, como check_plan_contract: recibe el contrato (``contract.json``), los criterios vigentes de la
UC y, si los hay, los resultados de las pruebas (``results.json``); no lee el tablero ni el disco ni
guarda nada. AG-09a la llama tras escribir el contrato (Paso 7.5.0 de /implement) y otra vez con
los resultados, para saber que cada prueba cita lo que comprueba.
"""

from __future__ import annotations

from typing import Any

from ..acceptance_contract import contract_report


async def check_acceptance_contract(
    contract_content: str,
    uc_criteria: list[str] | None = None,
    uc_id: str | None = None,
    results_content: str | None = None,
) -> dict[str, Any]:
    """Check the acceptance contract of a UC (UC-12801).

    `contract_content` is the text of `.quality/evidence/<feature>/acceptance/contract.json`
    (schema 1: per criterion `pre` and `post` conditions with ids `AC-NN.preN`/`AC-NN.postN` and a
    text, and `undefined`, a list that may be empty but is written). `uc_criteria` are the UC's
    current criteria ids (["AC-01", ...]) and `uc_id` its id. Returns `missing` (criteria without a
    contract), `incomplete` (criteria without pre, post or undefined), `invalid` (entries that are
    not valid), `extra` (criteria the UC no longer has, a warning), `uc_mismatch` and `ok`. With
    `results_content` (the tests' results.json, one run or a list where the latest wins per
    criterion) it also returns `citations`: `uncited` (tests that do not cite a pre and a post of
    their criterion), `unknown` (citations of a condition the contract does not have, of another
    criterion or of the other kind) and `not_cited` (conditions no test checks, a warning); then
    `ok` also needs those two lists empty. INVALID_CONTRACT / INVALID_RESULTS when the content
    cannot be read.
    """
    return contract_report(contract_content, uc_criteria, uc_id, results_content)


def register_acceptance_contract_tools(mcp_instance) -> None:
    """Registra ``check_acceptance_contract`` (US-128 · UC-12801)."""
    mcp_instance.tool(
        description="Check the acceptance contract of a UC before its tests (pure: pass the text of "
        "contract.json as contract_content, the UC's current criteria ids as uc_criteria and its "
        "uc_id). Returns missing (criteria without a contract), incomplete (without pre, post or "
        "undefined), invalid, extra and ok. With results_content (results.json) it also checks that "
        "each test cites a pre and a post condition of its criterion (citations: uncited, unknown, "
        "not_cited). AG-09a calls it after writing the contract and again with the results."
    )(check_acceptance_contract)
