"""Pruebas de aceptación de UC-12604 contra las funciones públicas de server/plan_contract.py.

Criterios vigentes de la UC (get_uc):

- AC-01: el plan indica en cada fase los criterios que cubre y cada criterio de la UC aparece en al
  menos una fase.
- AC-02: al marcar un criterio como hecho el tablero guarda ficheros y prueba (backends: fuera del módulo).
- AC-03: ``get_uc`` devuelve para cada criterio su fase, sus ficheros y su prueba (aquí solo la parte que
  sale del plan: la fase y los ficheros que el plan espera para ella).
- AC-04: un plan anterior que no relaciona fases y criterios sigue funcionando y se ve que falta la relación.
"""

from __future__ import annotations

from server.plan_contract import (
    CONTRACT_NOTICE_OLD_PLAN,
    ac_key,
    expected_files,
    incomplete_phases,
    normalize_ac,
    parse_plan_contract,
    phase_named,
    phase_of,
    uncovered_criteria,
)


def plan(*lines: str) -> str:
    return "\n".join(lines) + "\n"


UC = "UC-12501"

CONTRACT_PLAN = plan(
    "# Plan de UC-12501",
    "",
    "### Fase 1: Base",
    "**Criterios:** UC-12501 AC-01, AC-03",
    "**Ficheros:** server/a.py, server/b.py",
    "",
    "### Fase 2: Retirar sin renumerar",
    "**Criterios:** UC-12501 AC-02",
    "**Ficheros:** `server/c.py` (nuevo), server/a.py",
    "",
    "## Dependencias nuevas",
    "- pypi: rapidfuzz",
)


# --------------------------------------------------------------------------------------------- AC-01


def test_ac01_each_phase_declares_the_criteria_it_covers():
    """AC-01: cada fase del plan trae sus criterios, con la UC a la que pertenecen."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert contract.contract_version == 1
    assert [p.title for p in contract.phases] == ["Fase 1: Base", "Fase 2: Retirar sin renumerar"]
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-03")]
    assert contract.phases[1].criteria == [(UC, "AC-02")]
    assert contract.phases[0].has_criteria_line is True
    assert contract.phases[1].has_criteria_line is True


def test_ac01_phase_as_dict_publishes_criteria_files_and_declarations():
    """AC-01: la fase se puede entregar como dato, con los criterios que cubre."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert contract.as_dict()["phases"][0] == {
        "title": "Fase 1: Base",
        "criteria": [{"uc_id": UC, "ac_id": "AC-01"}, {"uc_id": UC, "ac_id": "AC-03"}],
        "files": ["server/a.py", "server/b.py"],
        "declares_criteria": True,
        "declares_files": True,
    }
    assert contract.as_dict()["contract_version"] == 1


def test_ac01_every_criterion_of_the_uc_in_some_phase_leaves_nothing_uncovered():
    """AC-01: si cada criterio de la UC aparece en alguna fase, no queda ninguno sin cubrir."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {}


def test_ac01_a_criterion_in_no_phase_is_reported_for_its_uc():
    """AC-01: un criterio de la UC que ninguna fase cubre se dice, con su UC."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03", "AC-04"]}) == {UC: ["AC-04"]}
    assert uncovered_criteria(contract, {UC: ["AC-05", "AC-04"]}) == {UC: ["AC-05", "AC-04"]}


def test_ac01_ac1_and_ac01_are_the_same_criterion():
    """AC-01: AC-1 y AC-01 son el mismo criterio, tanto al escribir el plan como al compararlo."""
    contract = parse_plan_contract(plan("### Fase 1: X", "**Criterios:** UC-12501 AC-1, AC-2", "**Ficheros:** a.py"))
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-2"]}) == {}
    assert ac_key(3) == "AC-03"
    assert ac_key("7") == "AC-07"
    assert normalize_ac("AC-3") == "AC-03"
    assert normalize_ac(" ac-12 ") == "AC-12"


def test_ac01_a_range_of_criteria_covers_the_ones_in_between():
    """AC-01: ``AC-01 a AC-04``, ``AC-01..AC-04`` y ``AC-01–AC-04`` cubren los criterios de en medio."""
    for spelling in ("AC-01 a AC-04", "AC-01..AC-04", "AC-01–AC-04", "AC-01 hasta AC-04"):
        contract = parse_plan_contract(plan("### Fase 1: X", f"**Criterios:** UC-12501 {spelling}", "**Ficheros:** a.py"))
        assert contract.phases[0].criteria == [(UC, f"AC-0{n}") for n in (1, 2, 3, 4)], spelling
        assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03", "AC-04"]}) == {}, spelling
        assert uncovered_criteria(contract, {UC: ["AC-05"]}) == {UC: ["AC-05"]}, spelling


def test_ac01_criteria_can_be_a_list_under_the_line():
    """AC-01: la línea de criterios puede traerlos en una lista justo debajo."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: X",
            "**Criterios:**",
            "- UC-12501 AC-01",
            "- UC-12501 AC-02",
            "**Ficheros:**",
            "- server/a.py",
            "",
            "### Fase 2: Y",
            "**Criterios:** UC-12501 AC-03",
            "**Ficheros:** server/b.py",
        )
    )
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert contract.phases[0].files == ["server/a.py"]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {}


def test_ac01_criteria_of_a_phase_do_not_repeat():
    """AC-01: un criterio nombrado dos veces en la misma fase cuenta una vez."""
    contract = parse_plan_contract(plan("### Fase 1: X", "**Criterios:** UC-12501 AC-01, AC-01, AC-1", "**Ficheros:** a.py"))
    assert contract.phases[0].criteria == [(UC, "AC-01")]


def test_ac01_a_phase_without_its_lines_is_reported_with_what_it_misses():
    """AC-01: una fase sin su línea de criterios o de ficheros se señala con lo que le falta."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: Base",
            "**Criterios:** UC-12501 AC-01",
            "**Ficheros:** a.py",
            "",
            "### Fase 2: Sin ficheros",
            "**Criterios:** UC-12501 AC-02",
            "",
            "### Fase 3: Sin criterios",
            "**Ficheros:** b.py",
            "",
            "### Fase 4",
            "",
            "## Notas",
            "Esto no es una fase.",
        )
    )
    assert contract.contract_version == 1
    assert incomplete_phases(contract) == [
        {"phase": "Fase 2: Sin ficheros", "missing": ["Ficheros"]},
        {"phase": "Fase 3: Sin criterios", "missing": ["Criterios"]},
        {"phase": "Fase 4", "missing": ["Criterios", "Ficheros"]},
    ]


def test_ac01_a_complete_plan_has_no_incomplete_phase():
    """AC-01: un plan con las dos líneas en cada fase no tiene fases incompletas."""
    assert incomplete_phases(parse_plan_contract(CONTRACT_PLAN)) == []


def test_ac01_a_heading_that_is_not_called_phase_counts_when_it_has_the_lines():
    """AC-01: un encabezado que no se llama «Fase N» cuenta como fase si trae una línea de criterios."""
    contract = parse_plan_contract(
        plan("### Entrega final", "**Criterios:** UC-12501 AC-01", "**Ficheros:** a.py", "", "### Notas", "texto")
    )
    assert [p.title for p in contract.phases] == ["Entrega final"]
    assert contract.phases[0].criteria == [(UC, "AC-01")]


def test_ac01_criteria_inside_a_code_block_are_an_example_and_cover_nothing():
    """AC-01: lo que va dentro de un bloque de código (``` o ~~~) es un ejemplo y no cubre criterios."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: Base",
            "**Criterios:** UC-12501 AC-01",
            "**Ficheros:** a.py",
            "",
            "Ejemplo del formato:",
            "```",
            "### Fase 9: Ejemplo",
            "**Criterios:** UC-12501 AC-09",
            "**Ficheros:** ejemplo.py",
            "```",
            "~~~",
            "**Criterios:** UC-12501 AC-08",
            "~~~",
        )
    )
    assert [p.title for p in contract.phases] == ["Fase 1: Base"]
    assert contract.phases[0].criteria == [(UC, "AC-01")]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-08", "AC-09"]}) == {UC: ["AC-08", "AC-09"]}


def test_ac01_criteria_without_uc_in_a_single_uc_plan_cover_that_uc():
    """AC-01: en un plan de una sola UC, un criterio escrito sin su UC cubre el de esa UC."""
    text = plan("### Fase 1: X", "**Criterios:** AC-01, AC-02", "**Ficheros:** a.py")
    contract = parse_plan_contract(text)
    assert contract.ambiguous is False
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-03"]}
    assert contract.unattributed() == []


def test_ac01_default_uc_attributes_criteria_written_without_it():
    """AC-01: con ``default_uc``, los criterios sin UC se atribuyen a ella si el plan no nombra otra."""
    text = plan("### Fase 1: X", "**Criterios:** AC-01, AC-02", "**Ficheros:** a.py")
    contract = parse_plan_contract(text, default_uc="uc-12604")
    assert contract.phases[0].criteria == [("UC-12604", "AC-01"), ("UC-12604", "AC-02")]
    assert contract.named_ucs == ["UC-12604"]
    assert uncovered_criteria(contract, {"UC-12604": ["AC-01", "AC-02", "AC-03"]}) == {"UC-12604": ["AC-03"]}


def test_ac01_default_uc_does_not_override_the_uc_the_plan_names():
    """AC-01: si el plan nombra otra UC, ``default_uc`` no se le pega a sus criterios."""
    text = plan("### Fase 1: X", "**Criterios:** UC-12501 AC-01", "**Ficheros:** a.py")
    contract = parse_plan_contract(text, default_uc="UC-99999")
    assert contract.phases[0].criteria == [(UC, "AC-01")]
    assert contract.named_ucs == [UC]


def test_ac01_the_uc_of_a_phase_can_come_from_its_heading():
    """AC-01: la UC de un criterio sin ella sale del encabezado de su fase («Fase 1 (UC-1)»)."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1 (UC-12501): Base",
            "**Criterios:** AC-01",
            "**Ficheros:** a.py",
            "",
            "### Fase 2 (UC-12502): Otra",
            "**Criterios:** AC-01, AC-02",
            "**Ficheros:** b.py",
        )
    )
    assert contract.phases[0].uc == "UC-12501"
    assert contract.phases[0].criteria == [("UC-12501", "AC-01")]
    assert contract.phases[1].criteria == [("UC-12502", "AC-01"), ("UC-12502", "AC-02")]
    assert contract.named_ucs == ["UC-12501", "UC-12502"]
    assert uncovered_criteria(contract, {"UC-12501": ["AC-01"], "UC-12502": ["AC-01", "AC-02"]}) == {}


MULTI_UC_PLAN = plan(
    "### Fase 1: Primera",
    "**Criterios:** UC-1 AC-01",
    "**Ficheros:** a.py",
    "",
    "### Fase 2: Segunda",
    "**Criterios:** UC-2 AC-01, AC-02",
    "**Ficheros:** b.py",
    "",
    "### Fase 3: Tercera",
    "**Criterios:** AC-03",
    "**Ficheros:** c.py",
)


def test_ac01_in_a_multi_uc_plan_a_criterion_covers_only_its_own_uc():
    """AC-01: en un plan de varias UC, AC-01 de una UC no cubre el AC-01 de otra."""
    contract = parse_plan_contract(MULTI_UC_PLAN)
    assert contract.ambiguous is True
    assert uncovered_criteria(contract, {"UC-1": ["AC-01"], "UC-2": ["AC-01", "AC-02"]}) == {}
    assert uncovered_criteria(contract, {"UC-1": ["AC-01", "AC-02"], "UC-2": ["AC-01"]}) == {"UC-1": ["AC-02"]}


def test_ac01_in_a_multi_uc_plan_a_criterion_without_uc_is_unattributed_and_covers_none():
    """AC-01: en un plan de varias UC, un criterio sin su UC se lista como sin atribuir y no cubre ninguna."""
    contract = parse_plan_contract(MULTI_UC_PLAN)
    assert contract.unattributed() == [{"phase": "Fase 3: Tercera", "ac_id": "AC-03"}]
    assert uncovered_criteria(contract, {"UC-1": ["AC-01", "AC-03"], "UC-2": ["AC-01", "AC-02"]}) == {"UC-1": ["AC-03"]}


def test_ac01_uc_ids_are_compared_case_insensitively():
    """AC-01: el id de la UC se compara sin distinguir mayúsculas."""
    contract = parse_plan_contract(plan("### Fase 1: X", "**Criterios:** uc-12501 AC-01", "**Ficheros:** a.py"))
    assert contract.phases[0].criteria == [(UC, "AC-01")]
    assert uncovered_criteria(contract, {"uc-12501": ["AC-01"]}) == {}


# --------------------------------------------------------------------------------------------- AC-03
# get_uc pone en cada criterio su fase (si el recibo no la dice, la del plan) y los ficheros que el
# plan espera para esa fase. La parte de «prueba» sale del recibo y no del módulo.


def test_ac03_phase_of_gives_the_phase_that_covers_the_criterion():
    """AC-03: la fase de un criterio es la fase del plan que lo cubre."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert phase_of(contract, UC, "AC-01").title == "Fase 1: Base"
    assert phase_of(contract, UC, "AC-03").title == "Fase 1: Base"
    assert phase_of(contract, UC, "AC-02").title == "Fase 2: Retirar sin renumerar"


def test_ac03_phase_of_a_criterion_no_phase_covers_is_none():
    """AC-03: un criterio que ninguna fase cubre no tiene fase."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert phase_of(contract, UC, "AC-04") is None
    assert phase_of(contract, "UC-99999", "AC-01") is None


def test_ac03_phase_of_accepts_ac1_and_a_lowercase_uc():
    """AC-03: AC-1 es AC-01 y el id de la UC no distingue mayúsculas al buscar la fase."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert phase_of(contract, "uc-12501", "AC-2").title == "Fase 2: Retirar sin renumerar"
    assert phase_of(contract, UC, "AC-3").title == "Fase 1: Base"


def test_ac03_phase_of_gives_the_first_phase_when_two_cover_the_criterion():
    """AC-03: si varias fases cubren el criterio, su fase es la primera."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: Primera",
            "**Criterios:** UC-12501 AC-01",
            "**Ficheros:** a.py",
            "",
            "### Fase 2: Segunda",
            "**Criterios:** UC-12501 AC-01, AC-02",
            "**Ficheros:** b.py",
        )
    )
    assert phase_of(contract, UC, "AC-01").title == "Fase 1: Primera"
    assert phase_of(contract, UC, "AC-02").title == "Fase 2: Segunda"


def test_ac03_the_files_of_the_criterion_phase_are_the_ones_the_plan_expects_for_it():
    """AC-03: los ficheros que el plan espera para la fase de un criterio son los de su línea Ficheros."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert phase_of(contract, UC, "AC-01").files == ["server/a.py", "server/b.py"]
    assert phase_of(contract, UC, "AC-02").files == ["server/c.py", "server/a.py"]


def test_ac03_files_are_clean_paths_in_any_of_the_written_forms():
    """AC-03: los ficheros de una fase salen limpios: sin comillas, anotaciones ni repeticiones."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: X",
            "**Criterios:** UC-12501 AC-01",
            "**Ficheros:** server/x.py (nuevo); `server/y.py` y `server/z.py`, server/x.py, ninguno",
        )
    )
    assert contract.phases[0].files == ["server/x.py", "server/y.py", "server/z.py"]


def test_ac03_in_a_multi_uc_plan_the_phase_of_a_criterion_is_the_one_of_its_uc():
    """AC-03: en un plan de varias UC, la fase del AC-01 de cada UC es la suya."""
    contract = parse_plan_contract(MULTI_UC_PLAN)
    assert phase_of(contract, "UC-1", "AC-01").title == "Fase 1: Primera"
    assert phase_of(contract, "UC-2", "AC-01").title == "Fase 2: Segunda"
    assert phase_of(contract, "UC-1", "AC-03") is None  # sin UC en un plan de varias: no se adivina


def test_ac03_a_receipt_naming_a_phase_gets_that_phase():
    """AC-03: el recibo que nombra una fase por su título recibe esa fase (sin distinguir mayúsculas ni espacios)."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    found = phase_named(contract, "  fase 2:   RETIRAR sin renumerar ", UC, "AC-02")
    assert found is not None and found.title == "Fase 2: Retirar sin renumerar"


def test_ac03_a_receipt_naming_only_the_phase_number_gets_the_phase_that_covers_the_criterion():
    """AC-03: un recibo que abrevia «Fase 2» recibe la fase 2 del plan solo si cubre el criterio."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert phase_named(contract, "Fase 2", UC, "AC-02").title == "Fase 2: Retirar sin renumerar"
    assert phase_named(contract, "Fase 1", UC, "AC-03").title == "Fase 1: Base"
    assert phase_named(contract, "Fase 1", UC, "AC-02") is None
    assert phase_named(contract, "Fase 7", UC, "AC-02") is None


def test_ac03_a_receipt_with_a_repeated_title_gets_the_phase_that_covers_its_criterion():
    """AC-03: con dos fases del mismo título, el recibo recibe la que cubre su criterio."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: Tests",
            "**Criterios:** UC-1 AC-01",
            "**Ficheros:** a.py",
            "",
            "### Fase 2: Tests",
            "**Criterios:** UC-2 AC-01",
            "**Ficheros:** b.py",
        )
    )
    assert phase_named(contract, "Fase 2: Tests", "UC-2", "AC-01").files == ["b.py"]
    assert phase_named(contract, "Fase 1: Tests", "UC-1", "AC-01").files == ["a.py"]


def test_ac03_expected_files_of_the_plan_follow_the_order_of_the_phases_without_repeats():
    """AC-03: los ficheros que el plan espera, en el orden en que aparecen y sin repetir."""
    contract = parse_plan_contract(CONTRACT_PLAN)
    assert expected_files(contract) == ["server/a.py", "server/b.py", "server/c.py"]


# --------------------------------------------------------------------------------------------- AC-04

OLD_PLAN = plan(
    "# Plan de UC-12501",
    "",
    "## Fase 1: Base",
    "- [ ] Escribir el módulo",
    "- [ ] UC-12501 AC-01 verificado",
    "**Ficheros:** server/a.py",
    "",
    "## Fase 2: Pruebas",
    "- [ ] Probar",
    "",
    "## Dependencias nuevas",
    "- pypi: rapidfuzz",
)


def test_ac04_an_older_plan_without_criteria_lines_is_contract_zero_and_not_guessed():
    """AC-04: un plan anterior, sin líneas **Criterios:**, es contrato 0 y no se adivinan sus fases."""
    contract = parse_plan_contract(OLD_PLAN)
    assert contract.contract_version == 0
    assert contract.phases == []
    assert contract.as_dict()["contract_version"] == 0
    assert contract.as_dict()["phases"] == []


def test_ac04_an_older_plan_still_gives_its_new_dependencies():
    """AC-04: el plan anterior sigue leyéndose: sus dependencias nuevas no se pierden."""
    contract = parse_plan_contract(OLD_PLAN)
    assert contract.dependencies == [{"ecosystem": "pypi", "name": "rapidfuzz"}]
    assert parse_plan_contract(plan("## Fase 1: X", "- [ ] algo")).dependencies is None


def test_ac04_an_older_plan_relates_no_criterion_to_a_phase_or_files():
    """AC-04: con un plan anterior, ningún criterio tiene fase y no hay ficheros esperados."""
    contract = parse_plan_contract(OLD_PLAN)
    assert phase_of(contract, UC, "AC-01") is None
    assert phase_named(contract, "Fase 1: Base", UC, "AC-01") is None
    assert expected_files(contract) == []
    assert incomplete_phases(contract) == []
    assert contract.unattributed() == []


def test_ac04_the_report_says_the_relation_between_phases_and_criteria_is_missing():
    """AC-04: el aviso del informe dice que el plan no relaciona fases y criterios."""
    assert "no relaciona fases y criterios" in CONTRACT_NOTICE_OLD_PLAN
    assert "**Criterios:**" in CONTRACT_NOTICE_OLD_PLAN
    assert "**Ficheros:**" in CONTRACT_NOTICE_OLD_PLAN
    assert "no están disponibles" in CONTRACT_NOTICE_OLD_PLAN
    assert "Los planes nuevos de /plan las llevan" in CONTRACT_NOTICE_OLD_PLAN
    # y quien lo use distingue un plan anterior de uno nuevo por la versión del contrato
    assert parse_plan_contract(OLD_PLAN).contract_version != parse_plan_contract(CONTRACT_PLAN).contract_version


def test_ac04_a_plan_with_only_loose_file_lines_is_contract_zero():
    """AC-04: un plan que solo trae líneas sueltas de ficheros no es contrato 1."""
    contract = parse_plan_contract(
        plan("### Fase 1: Base", "**Ficheros:** server/a.py", "", "### Fase 2: Otra", "**Ficheros:** server/b.py")
    )
    assert contract.contract_version == 0
    assert contract.phases == []


def test_ac04_a_criteria_line_that_names_no_criterion_does_not_make_a_contract():
    """AC-04: una línea **Criterios:** que no nombra ningún criterio (AC-NN) no hace contrato 1."""
    contract = parse_plan_contract(plan("### Fase 1: Base", "**Criterios:** ninguno", "**Ficheros:** server/a.py"))
    assert contract.contract_version == 0
    assert contract.phases == []


def test_ac04_a_plan_whose_only_criteria_lines_are_inside_code_blocks_is_contract_zero():
    """AC-04: si las líneas **Criterios:** solo salen dentro de un bloque de código, el plan es anterior."""
    for fence in ("```", "~~~", "````"):
        contract = parse_plan_contract(
            plan(
                "## Fase 1: Base",
                "- [ ] hacer algo",
                "",
                "Así se escribe una fase nueva:",
                fence,
                "### Fase 1: Ejemplo",
                "**Criterios:** UC-12501 AC-01",
                "**Ficheros:** server/a.py",
                fence,
            )
        )
        assert contract.contract_version == 0, fence
        assert contract.phases == [], fence


def test_ac04_a_longer_fence_is_not_closed_by_a_shorter_one():
    """AC-04: un bloque abierto con ```` no lo cierra un ``` interior: lo de dentro sigue siendo ejemplo."""
    contract = parse_plan_contract(
        plan(
            "## Fase 1: Base",
            "````",
            "```",
            "**Criterios:** UC-12501 AC-01",
            "```",
            "**Criterios:** UC-12501 AC-02",
            "````",
        )
    )
    assert contract.contract_version == 0
    assert contract.phases == []


def test_ac04_empty_or_missing_plan_text_is_contract_zero():
    """AC-04: un plan vacío (o sin texto) es contrato 0, sin fases ni error."""
    for text in ("", "   \n\n", None):
        contract = parse_plan_contract(text)  # type: ignore[arg-type]
        assert contract.contract_version == 0
        assert contract.phases == []
        assert contract.dependencies is None


def test_ac04_a_contract_one_plan_is_not_reported_as_older():
    """AC-04: un plan con una línea **Criterios:** que nombra un criterio es contrato 1 aunque otra fase no la traiga."""
    contract = parse_plan_contract(
        plan(
            "### Fase 1: Base",
            "**Criterios:** UC-12501 AC-01",
            "**Ficheros:** a.py",
            "",
            "### Fase 2: Sin líneas",
        )
    )
    assert contract.contract_version == 1
    assert incomplete_phases(contract) == [{"phase": "Fase 2: Sin líneas", "missing": ["Criterios", "Ficheros"]}]
