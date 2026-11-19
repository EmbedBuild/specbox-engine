"""Pruebas de aceptación de UC-12604 (criterios enlazados con su fase, sus ficheros y su prueba).

Generadas desde el contrato (contract.json de esta carpeta) contra las funciones públicas de
``server/plan_contract.py``. Puras: sin base de datos, red ni disco.

Criterios cubiertos: AC-01, AC-03 (la parte que sale del plan: fase y ficheros) y AC-04.
Fuera: AC-02 (el recibo que guarda ficheros y prueba vive en los backends, no en este módulo).
"""

from __future__ import annotations

import textwrap

import pytest

from server.plan_contract import (
    CONTRACT_NOTICE_OLD_PLAN,
    PlanContract,
    Phase,
    expected_files,
    incomplete_phases,
    parse_plan_contract,
    phase_by_number,
    phase_named,
    phase_of,
    uncovered_criteria,
)

UC = "UC-12604"


def _plan(text: str) -> str:
    return textwrap.dedent(text).lstrip("\n")


def _pairs(phase_dict: dict) -> list[tuple[str | None, str]]:
    return [(c["uc_id"], c["ac_id"]) for c in phase_dict["criteria"]]


FULL_PLAN = _plan(
    """
    # Plan UC-12604

    ### Fase 1: Leer el plan
    **Criterios:** UC-12604 AC-01, AC-1
    **Ficheros:** server/plan_contract.py, `server/tools/plan_contract.py` y `tests/test_plan.py`

    ### Fase 2: Informe
    **Criterios:** UC-12604 AC-02 a AC-03
    **Ficheros:** server/informe.py (nuevo)

    ### Fase 3: Recibos
    **Criterios:**
    - UC-12604 AC-4
    **Ficheros:**
    - server/ac_evidence.py
    - server/backends/plane_backend.py

    ## Dependencias nuevas
    Ninguna
    """
)


# --------------------------------------------------------------------------------------------------
# AC-01 · el plan indica en cada fase los criterios que cubre, y cada criterio aparece en una fase
# --------------------------------------------------------------------------------------------------


def test_ac01_each_phase_lists_the_criteria_its_line_names():
    """Cada fase lleva los criterios de su línea Criterios, normalizados, expandidos y sin repetir.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1
    """
    contract = parse_plan_contract(FULL_PLAN)
    assert contract.contract_version == 1
    data = contract.as_dict()
    assert data["contract_version"] == 1
    assert [p["title"] for p in data["phases"]] == ["Fase 1: Leer el plan", "Fase 2: Informe", "Fase 3: Recibos"]
    assert all(p["declares_criteria"] is True for p in data["phases"])
    # «AC-01, AC-1» son el mismo criterio: una sola vez.
    assert _pairs(data["phases"][0]) == [(UC, "AC-01")]
    # «AC-02 a AC-03» se expande a los criterios de en medio.
    assert _pairs(data["phases"][1]) == [(UC, "AC-02"), (UC, "AC-03")]
    # La lista debajo de la línea y el id sin cero (AC-4) también valen.
    assert _pairs(data["phases"][2]) == [(UC, "AC-04")]


def test_ac01_range_with_dots_and_dash_covers_every_criterion_between():
    """Un rango con «..» o con raya cubre también los de en medio.

    contract: AC-01.pre1, AC-01.post1
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01..AC-03
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-12604 AC-04–AC-06
        **Ficheros:** b.py
        """
    )
    data = parse_plan_contract(plan).as_dict()
    assert _pairs(data["phases"][0]) == [(UC, "AC-01"), (UC, "AC-02"), (UC, "AC-03")]
    assert _pairs(data["phases"][1]) == [(UC, "AC-04"), (UC, "AC-05"), (UC, "AC-06")]


def test_ac01_every_criterion_of_the_uc_in_some_phase_leaves_nothing_uncovered():
    """Con todos los criterios en alguna fase, uncovered_criteria es {} y no hay fases incompletas.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post2, AC-01.post4
    """
    contract = parse_plan_contract(FULL_PLAN)
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03", "AC-04"]}) == {}
    assert incomplete_phases(contract) == []


def test_ac01_a_criterion_written_with_one_digit_counts_as_covered():
    """Un criterio escrito AC-4 en el plan cubre el AC-04 de la UC (y al revés).

    contract: AC-01.pre1, AC-01.pre2, AC-01.post2
    """
    contract = parse_plan_contract(FULL_PLAN)
    assert uncovered_criteria(contract, {UC: ["AC-1", "AC-2", "AC-3", "AC-4"]}) == {}


def test_ac01_criteria_no_phase_covers_are_listed_in_the_order_received():
    """uncovered_criteria nombra los criterios sin fase, en el orden recibido, y no los cubiertos.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01, AC-02
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-12604 AC-04
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    result = uncovered_criteria(contract, {UC: ["AC-05", "AC-04", "AC-03", "AC-02", "AC-01"]})
    assert result == {UC: ["AC-05", "AC-03"]}
    assert "AC-04" not in result[UC]
    assert "AC-01" not in result[UC]


def test_ac01_only_the_ucs_with_something_uncovered_appear_in_the_result():
    """En un plan de varias UC, las que tienen todo cubierto no salen en el resultado.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01, AC-02; UC-99 AC-01
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-99 AC-02
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    result = uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"], "UC-99": ["AC-01", "AC-02"]})
    assert result == {UC: ["AC-03"]}
    assert "UC-99" not in result


def test_ac01_a_uc_with_no_criteria_gives_nothing_uncovered():
    """Una UC sin criterios no aporta nada a uncovered_criteria; sin UC tampoco.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post2
    """
    contract = parse_plan_contract(FULL_PLAN)
    assert uncovered_criteria(contract, {UC: []}) == {}
    assert uncovered_criteria(contract, {}) == {}


def test_ac01_a_phase_without_its_lines_is_reported_with_what_it_lacks():
    """incomplete_phases dice, por cada fase, si le falta Criterios, Ficheros o las dos.

    contract: AC-01.pre1, AC-01.pre3, AC-01.post5
    """
    plan = _plan(
        """
        ### Fase 1: Completa
        **Criterios:** UC-12604 AC-01
        **Ficheros:** a.py

        ### Fase 2: Sin criterios
        **Ficheros:** b.py

        ### Fase 3: Sin ficheros
        **Criterios:** UC-12604 AC-02

        ### Fase 4: Sin nada
        Solo texto.
        """
    )
    contract = parse_plan_contract(plan)
    assert contract.contract_version == 1
    assert incomplete_phases(contract) == [
        {"phase": "Fase 2: Sin criterios", "missing": ["Criterios"]},
        {"phase": "Fase 3: Sin ficheros", "missing": ["Ficheros"]},
        {"phase": "Fase 4: Sin nada", "missing": ["Criterios", "Ficheros"]},
    ]
    data = contract.as_dict()
    assert [(p["declares_criteria"], p["declares_files"]) for p in data["phases"]] == [
        (True, True),
        (False, True),
        (True, False),
        (False, False),
    ]


def test_ac01_all_phases_with_both_lines_report_no_incomplete_phase():
    """Un plan con las dos líneas en cada fase no tiene fases incompletas.

    contract: AC-01.pre1, AC-01.post4
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-12604 AC-02
        **Ficheros:** b.py
        """
    )
    assert incomplete_phases(parse_plan_contract(plan)) == []


def test_ac01_a_criterion_without_its_uc_in_a_plan_of_several_ucs_is_not_attributed():
    """Sin UC en un plan de varias, el criterio no se atribuye a ninguna y queda sin cubrir.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-1 AC-01; UC-2 AC-01
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** AC-02
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    assert contract.ambiguous is True
    assert contract.named_ucs == ["UC-1", "UC-2"]
    assert contract.unattributed() == [{"phase": "Fase 2: Dos", "ac_id": "AC-02"}]
    assert uncovered_criteria(contract, {"UC-1": ["AC-01", "AC-02"], "UC-2": ["AC-01", "AC-02"]}) == {
        "UC-1": ["AC-02"],
        "UC-2": ["AC-02"],
    }


def test_ac01_a_criterion_without_uc_is_taken_by_default_uc_when_the_plan_names_no_other():
    """Con default_uc, un criterio sin UC es de esa UC si el plan no nombra otra.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post3
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** AC-01, AC-02
        **Ficheros:** a.py
        """
    )
    with_default = parse_plan_contract(plan, default_uc="uc-12604")
    assert _pairs(with_default.as_dict()["phases"][0]) == [(UC, "AC-01"), (UC, "AC-02")]
    assert with_default.named_ucs == [UC]
    assert uncovered_criteria(with_default, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-03"]}
    # Sin default_uc el criterio queda sin UC, pero con una sola UC pedida sigue valiendo.
    without_default = parse_plan_contract(plan)
    assert _pairs(without_default.as_dict()["phases"][0]) == [(None, "AC-01"), (None, "AC-02")]
    assert uncovered_criteria(without_default, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-03"]}


def test_ac01_default_uc_does_not_override_another_uc_the_plan_names():
    """Si el plan nombra otra UC, default_uc no reatribuye sus criterios.

    contract: AC-01.pre1, AC-01.post1
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-2 AC-01; AC-02
        **Ficheros:** a.py
        """
    )
    contract = parse_plan_contract(plan, default_uc="UC-1")
    assert _pairs(contract.as_dict()["phases"][0]) == [("UC-2", "AC-01"), ("UC-2", "AC-02")]
    assert contract.named_ucs == ["UC-2"]


def test_ac01_criteria_lines_inside_a_code_block_do_not_count():
    """Lo que va en un bloque de código (``` o ~~~) es un ejemplo: no añade fases ni criterios.

    contract: AC-01.pre1, AC-01.post1
    """
    plan = _plan(
        """
        ### Fase 1: Real
        **Criterios:** UC-12604 AC-01
        **Ficheros:** a.py

        ```markdown
        ### Fase 2: Ejemplo
        **Criterios:** UC-12604 AC-02
        **Ficheros:** b.py
        ```

        ~~~
        **Criterios:** UC-12604 AC-03
        ~~~
        """
    )
    data = parse_plan_contract(plan).as_dict()
    assert [p["title"] for p in data["phases"]] == ["Fase 1: Real"]
    assert _pairs(data["phases"][0]) == [(UC, "AC-01")]


def test_ac01_an_empty_or_missing_plan_covers_no_criterion():
    """Con el texto vacío o None todos los criterios de la UC se dan por sin cubrir.

    contract: AC-01.pre2, AC-01.post3
    """
    for text in ("", None):
        contract = parse_plan_contract(text)
        assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02"]}) == {UC: ["AC-01", "AC-02"]}


def test_ac01_lowercase_ids_are_normalized_and_a_reversed_range_is_not_expanded():
    """«ac-1» es AC-01 y «uc-12604» es UC-12604; un rango invertido solo nombra sus dos extremos.

    contract: AC-01.pre1, AC-01.post1
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** uc-12604 ac-1, ac-2
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-12604 AC-04 a AC-02
        **Ficheros:** b.py
        """
    )
    data = parse_plan_contract(plan).as_dict()
    assert _pairs(data["phases"][0]) == [(UC, "AC-01"), (UC, "AC-02")]
    assert _pairs(data["phases"][1]) == [(UC, "AC-04"), (UC, "AC-02")]


def test_ac01_a_heading_that_is_not_a_phase_but_carries_a_criteria_line_is_a_phase():
    """Un encabezado cualquiera con línea de criterios o de ficheros cuenta como fase.

    contract: AC-01.pre1, AC-01.post1, AC-01.post4
    """
    plan = _plan(
        """
        ## Paso A
        **Criterios:** UC-12604 AC-01
        **Ficheros:** x.py
        """
    )
    contract = parse_plan_contract(plan)
    assert contract.contract_version == 1
    data = contract.as_dict()
    assert [p["title"] for p in data["phases"]] == ["Paso A"]
    assert _pairs(data["phases"][0]) == [(UC, "AC-01")]
    assert incomplete_phases(contract) == []


def test_ac01_the_uc_may_be_passed_in_lowercase_and_comes_back_as_passed():
    """uc_criteria con la UC en minúsculas se compara sin distinguir mayúsculas y se devuelve tal cual.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    contract = parse_plan_contract(FULL_PLAN)
    assert uncovered_criteria(contract, {"uc-12604": ["AC-01", "AC-09"]}) == {"uc-12604": ["AC-09"]}


# --------------------------------------------------------------------------------------------------
# AC-03 · la fase y los ficheros de cada criterio (la parte que sale del plan)
# --------------------------------------------------------------------------------------------------


def test_ac03_phase_of_gives_the_phase_that_covers_the_criterion():
    """phase_of devuelve la fase que cubre el criterio, con una o dos cifras y la UC en cualquier caja.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    """
    contract = parse_plan_contract(FULL_PLAN)
    phase = phase_of(contract, UC, "AC-02")
    assert isinstance(phase, Phase)
    assert phase.title == "Fase 2: Informe"
    assert phase_of(contract, UC, "AC-2").title == "Fase 2: Informe"
    assert phase_of(contract, "uc-12604", "ac-03").title == "Fase 2: Informe"
    assert phase_of(contract, UC, "AC-01").title == "Fase 1: Leer el plan"
    assert phase_of(contract, UC, "AC-04").title == "Fase 3: Recibos"


def test_ac03_phase_of_gives_the_first_phase_when_several_cover_the_criterion():
    """Si dos fases cubren el criterio, se devuelve la primera del plan.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-12604 AC-01, AC-02
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    assert phase_of(contract, UC, "AC-01").title == "Fase 1: Uno"
    assert phase_of(contract, UC, "AC-02").title == "Fase 2: Dos"


def test_ac03_the_phase_files_are_the_ones_of_its_files_line():
    """Phase.files son los de su línea Ficheros: en orden, sin repetir, sin comillas ni anotación final.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2
    """
    contract = parse_plan_contract(FULL_PLAN)
    first = phase_of(contract, UC, "AC-01")
    assert first.files == ["server/plan_contract.py", "server/tools/plan_contract.py", "tests/test_plan.py"]
    # «server/informe.py (nuevo)»: la anotación no es parte de la ruta.
    assert phase_of(contract, UC, "AC-03").files == ["server/informe.py"]
    # Los ficheros en lista debajo de la línea también cuentan.
    assert phase_of(contract, UC, "AC-04").files == ["server/ac_evidence.py", "server/backends/plane_backend.py"]


def test_ac03_files_separated_by_semicolons_or_commas_are_not_repeated():
    """Comas y punto y coma separan; una ruta repetida cuenta una vez; las comillas invertidas no son parte.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post2
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01
        **Ficheros:** a.py; b.py (nuevo), a.py, `c.py`
        """
    )
    contract = parse_plan_contract(plan)
    assert phase_of(contract, UC, "AC-01").files == ["a.py", "b.py", "c.py"]


def test_ac03_a_phase_may_declare_no_files_and_then_it_has_none():
    """Una fase sin línea Ficheros no espera ninguno (no se inventan).

    contract: AC-03.pre2, AC-03.post1, AC-03.post2
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-12604 AC-01
        """
    )
    contract = parse_plan_contract(plan)
    phase = phase_of(contract, UC, "AC-01")
    assert phase is not None
    assert phase.files == []


def test_ac03_phase_of_is_none_when_no_phase_covers_the_criterion():
    """Un criterio que ninguna fase nombra no tiene fase.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post3
    """
    contract = parse_plan_contract(FULL_PLAN)
    assert phase_of(contract, UC, "AC-09") is None
    assert phase_of(contract, "UC-1", "AC-01") is None
    assert phase_of(contract, UC, "no es un criterio") is None


def test_ac03_in_a_plan_of_several_ucs_the_phase_is_the_one_of_the_uc_and_the_criterion():
    """Con el mismo id en dos UC, cada una tiene su fase; una UC que el plan no nombra no tiene ninguna.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post3
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-1 AC-01
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** UC-2 AC-01
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    assert phase_of(contract, "UC-1", "AC-01").files == ["a.py"]
    assert phase_of(contract, "UC-2", "AC-01").files == ["b.py"]
    assert phase_of(contract, "UC-3", "AC-01") is None


def test_ac03_a_criterion_without_uc_in_a_plan_of_several_ucs_has_no_phase():
    """Un criterio sin UC en un plan de varias no se atribuye: phase_of no lo encuentra.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post3
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** UC-1 AC-01; UC-2 AC-01
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** AC-02
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    assert phase_of(contract, "UC-1", "AC-02") is None
    assert phase_of(contract, "UC-2", "AC-02") is None


def test_ac03_a_plan_of_one_uc_attributes_a_criterion_without_uc_to_it():
    """En un plan de una sola UC, un criterio escrito sin la UC tiene su fase.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Criterios:** AC-01
        **Ficheros:** a.py
        """
    )
    contract = parse_plan_contract(plan)
    assert phase_of(contract, UC, "AC-01").title == "Fase 1: Uno"


def test_ac03_the_phase_a_receipt_names_is_the_one_with_that_title_that_covers_the_criterion():
    """phase_named elige, entre fases del mismo título, la que cubre la UC y el criterio.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    """
    plan = _plan(
        """
        ### Fase 1: Implementar
        **Criterios:** UC-1 AC-01
        **Ficheros:** a.py

        ### Fase 1: Implementar
        **Criterios:** UC-2 AC-01
        **Ficheros:** b.py
        """
    )
    contract = parse_plan_contract(plan)
    first = phase_named(contract, "Fase 1: Implementar", "UC-1", "AC-01")
    second = phase_named(contract, "fase 1:   implementar", "UC-2", "AC-01")
    assert first is not None and first.files == ["a.py"]
    assert second is not None and second.files == ["b.py"]
    assert ("UC-2", "AC-01") in second.criteria


def test_ac03_a_receipt_with_an_abbreviated_phase_finds_the_phase_by_its_number():
    """Un recibo que dice solo «Fase 2» se une a la Fase 2 que cubre la UC y el criterio.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post3
    """
    contract = parse_plan_contract(FULL_PLAN)
    named = phase_named(contract, "Fase 2", UC, "AC-02")
    assert named is not None and named.title == "Fase 2: Informe"
    # La Fase 2 no cubre AC-04 y no hay otra con ese título ni número: sin fase.
    assert phase_named(contract, "Fase 2", UC, "AC-04") is None
    assert phase_named(contract, "Una fase que no existe", UC, "AC-02") is None
    assert phase_by_number(contract, 3).title == "Fase 3: Recibos"
    assert phase_by_number(contract, 9) is None


def test_ac03_a_plan_without_the_relation_gives_no_phase_for_any_criterion():
    """Con un plan anterior, ningún criterio tiene fase (la prueba y la fase vendrán del recibo).

    contract: AC-03.pre2, AC-03.post3
    """
    contract = parse_plan_contract("### Fase 1: Uno\n**Ficheros:** a.py\n")
    assert phase_of(contract, UC, "AC-01") is None
    assert phase_named(contract, "Fase 1: Uno", UC, "AC-01") is None


# --------------------------------------------------------------------------------------------------
# AC-04 · un plan anterior sigue funcionando y el informe dice que falta la relación
# --------------------------------------------------------------------------------------------------

OLD_PLAN = _plan(
    """
    # Plan antiguo

    ### Fase 1: Hacer cosas
    Se toca server/a.py y server/b.py.
    **Ficheros:** server/a.py, server/b.py

    ### Fase 2: Más cosas
    Sin relacionar con criterios.
    """
)


def test_ac04_an_older_plan_is_contract_0_and_its_phases_are_not_guessed():
    """Un plan sin líneas Criterios es de contrato 0 y no se adivinan sus fases.

    contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post2
    """
    contract = parse_plan_contract(OLD_PLAN)
    assert isinstance(contract, PlanContract)
    assert contract.contract_version == 0
    assert contract.phases == []
    assert contract.as_dict() == {"contract_version": 0, "phases": [], "dependencies": None}
    assert contract.named_ucs == []


@pytest.mark.parametrize(
    "plan",
    [
        pytest.param("", id="vacio"),
        pytest.param(None, id="none"),
        pytest.param("Un plan en prosa, sin encabezados ni líneas.", id="prosa"),
        pytest.param("### Fase 1: Solo el título\n", id="fase-sin-lineas"),
        pytest.param("### Fase 1: Uno\n**Ficheros:** a.py\n", id="solo-ficheros"),
        pytest.param("### Fase 1: Uno\n**Criterios:**\n**Ficheros:** a.py\n", id="criterios-vacia"),
        pytest.param("### Fase 1: Uno\n**Criterios:** ninguno\n**Ficheros:** a.py\n", id="criterios-sin-ac"),
        pytest.param("### Fase 1: Uno\n```\n**Criterios:** UC-1 AC-01\n```\n", id="criterios-en-bloque"),
        pytest.param("### Fase 1: Uno\n~~~\n**Criterios:** UC-1 AC-01\n~~~\n**Ficheros:** a.py\n", id="criterios-en-bloque-tilde"),
    ],
)
def test_ac04_a_plan_that_names_no_criterion_outside_a_code_block_is_contract_0(plan):
    """Ninguna línea Criterios con un AC-NN fuera de un bloque de código: contrato 0 y sin fases.

    contract: AC-04.pre1, AC-04.post1, AC-04.post2
    """
    contract = parse_plan_contract(plan)
    assert contract.contract_version == 0
    assert contract.phases == []
    data = contract.as_dict()
    assert data["contract_version"] == 0
    assert data["phases"] == []


def test_ac04_the_notice_of_the_report_says_the_plan_does_not_relate_phases_and_criteria():
    """El aviso del informe dice que el plan no relaciona fases y criterios y qué no hay por ello.

    contract: AC-04.pre1, AC-04.post3
    """
    assert parse_plan_contract(OLD_PLAN).contract_version == 0
    notice = CONTRACT_NOTICE_OLD_PLAN
    assert isinstance(notice, str) and notice
    assert "no relaciona fases y criterios" in notice
    assert "**Criterios:**" in notice and "**Ficheros:**" in notice
    assert "la comparación con el plan" in notice
    assert "la fase de cada criterio" in notice
    assert "no están disponibles" in notice
    assert "planes nuevos de /plan" in notice


def test_ac04_the_helpers_implement_calls_keep_working_with_an_older_plan():
    """Con un plan anterior, las funciones de lectura no fallan y devuelven vacío o None.

    contract: AC-04.pre1, AC-04.pre2, AC-04.post4
    """
    contract = parse_plan_contract(OLD_PLAN, default_uc=UC)
    assert incomplete_phases(contract) == []
    assert expected_files(contract) == []
    assert phase_of(contract, UC, "AC-01") is None
    assert phase_by_number(contract, 1) is None
    assert phase_by_number(contract, 2) is None
    assert phase_named(contract, "Fase 1: Hacer cosas", UC, "AC-01") is None
    assert contract.unattributed() == []
    assert contract.ambiguous is False


def test_ac04_with_an_older_plan_every_criterion_of_the_uc_is_reported_as_uncovered():
    """uncovered_criteria no falla con un plan anterior: todos los criterios quedan sin fase.

    contract: AC-04.pre1, AC-04.pre2, AC-04.post1
    """
    contract = parse_plan_contract(OLD_PLAN)
    assert contract.contract_version == 0
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-01", "AC-02", "AC-03"]}
    assert uncovered_criteria(contract, {}) == {}


def test_ac04_an_older_plan_still_reports_its_new_dependencies():
    """La sección Dependencias nuevas se lee aunque el plan sea anterior (contrato 0).

    contract: AC-04.pre1, AC-04.post1, AC-04.post2
    """
    plan = _plan(
        """
        ### Fase 1: Uno
        **Ficheros:** a.py

        ## Dependencias nuevas
        - npm: left-pad
        - pypi: rapidfuzz, httpx>=0.27
        """
    )
    contract = parse_plan_contract(plan)
    assert contract.contract_version == 0
    assert contract.as_dict() == {
        "contract_version": 0,
        "phases": [],
        "dependencies": [
            {"ecosystem": "npm", "name": "left-pad"},
            {"ecosystem": "pypi", "name": "rapidfuzz"},
            {"ecosystem": "pypi", "name": "httpx>=0.27"},
        ],
    }


def test_ac04_an_older_plan_with_the_word_ninguna_in_its_dependencies_has_an_empty_list():
    """«Ninguna» en Dependencias nuevas da una lista vacía (el plan sí tiene la sección), no None.

    contract: AC-04.pre1, AC-04.post2
    """
    contract = parse_plan_contract("### Fase 1: Uno\n\n## Dependencias nuevas\nNinguna\n")
    assert contract.as_dict() == {"contract_version": 0, "phases": [], "dependencies": []}


def test_ac04_default_uc_changes_nothing_in_an_older_plan():
    """default_uc no inventa criterios ni UC en un plan anterior.

    contract: AC-04.pre1, AC-04.post1
    """
    without = parse_plan_contract(OLD_PLAN)
    with_default = parse_plan_contract(OLD_PLAN, default_uc=UC)
    assert with_default.contract_version == without.contract_version == 0
    assert with_default.phases == without.phases == []
    assert with_default.named_ucs == without.named_ucs == []


def test_ac04_one_criterion_named_outside_a_code_block_is_enough_to_leave_contract_0():
    """Sin criterio nombrado es contrato 0 y sin fases; basta uno fuera de un bloque para pasar a contrato 1.

    contract: AC-04.pre1, AC-04.post1
    """
    older = _plan(
        """
        ### Fase 1: Uno
        **Ficheros:** a.py

        ### Fase 2: Dos
        **Criterios:** sin criterios todavía
        **Ficheros:** b.py
        """
    )
    older_contract = parse_plan_contract(older)
    assert older_contract.contract_version == 0
    assert older_contract.phases == []
    newer = older.replace("sin criterios todavía", "UC-12604 AC-01")
    newer_contract = parse_plan_contract(newer)
    assert newer_contract.contract_version == 1
    assert [p.title for p in newer_contract.phases] == ["Fase 1: Uno", "Fase 2: Dos"]
    assert incomplete_phases(newer_contract) == [{"phase": "Fase 1: Uno", "missing": ["Criterios"]}]
