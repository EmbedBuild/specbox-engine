"""Pruebas de aceptación de UC-12604 generadas desde su contrato (contract.json).

Criterios probados contra las funciones públicas de ``server/plan_contract.py``:
AC-01 (fases con sus criterios y criterios sin fase), AC-03 (la fase y los ficheros que el plan
da a un criterio) y AC-04 (un plan anterior se lee como contrato 0 y el informe lo dice).
AC-02 (el recibo guarda ficheros y prueba en el tablero) no depende de este módulo y no se prueba.

Sin base de datos, red ni disco: el módulo es puro y recibe el texto del plan.
"""

from __future__ import annotations

import pytest

from server.plan_contract import (
    CONTRACT_NOTICE_OLD_PLAN,
    expected_files,
    incomplete_phases,
    parse_plan_contract,
    phase_named,
    phase_of,
    uncovered_criteria,
)

FENCE = "`" * 3
UC = "UC-12604"
UC_CRITERIA = {UC: ["AC-01", "AC-02", "AC-03", "AC-04"]}


def text(*lines: str) -> str:
    return "\n".join(lines) + "\n"


#: Un plan como lo escribe /plan tras UC-12604: dos fases que cubren los cuatro criterios.
PLAN = text(
    "# Plan UC-12604",
    "",
    "## Fase 1: Contrato del plan",
    "**Criterios:** UC-12604 AC-01, AC-04",
    "**Ficheros:** server/plan_contract.py, server/tools/plan_contract.py",
    "",
    "## Fase 2: Recibos del criterio",
    "**Criterios:** UC-12604 AC-02, AC-03",
    "**Ficheros:** server/ac_evidence.py (nuevo), `server/backends/plane_backend.py`",
    "",
    "## Dependencias nuevas",
    "Ninguna",
)

#: Un plan anterior a UC-12604: fases con tareas, sin líneas de criterios ni de ficheros.
OLD_PLAN = text(
    "# Plan de UC-12000",
    "",
    "## Fase 1: Implementar",
    "- [ ] Escribir el codigo",
    "",
    "## Fase 2: Cerrar",
    "- [ ] Abrir la PR",
    "",
    "## Dependencias nuevas",
    "- pypi: rapidfuzz, `httpx>=0.27`",
    "- nota: esto no es un paquete",
)


# --------------------------------------------------------------------------------------------------
# AC-01: cada fase indica los criterios que cubre y cada criterio de la UC está en alguna fase
# --------------------------------------------------------------------------------------------------


def test_each_phase_declares_the_criteria_it_covers():
    """Las fases salen con sus criterios, sus ficheros y las marcas de lo que declaran.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1
    """
    contract = parse_plan_contract(PLAN)

    assert contract.contract_version == 1
    assert [p.title for p in contract.phases] == [
        "Fase 1: Contrato del plan",
        "Fase 2: Recibos del criterio",
    ]
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-04")]
    assert contract.phases[1].criteria == [(UC, "AC-02"), (UC, "AC-03")]
    assert contract.phases[0].files == ["server/plan_contract.py", "server/tools/plan_contract.py"]
    assert contract.phases[1].files == ["server/ac_evidence.py", "server/backends/plane_backend.py"]
    assert all(p.has_criteria_line and p.has_files_line for p in contract.phases)
    assert contract.named_ucs == [UC]


def test_the_contract_as_dict_reports_what_each_phase_declares():
    """El contrato serializado dice, por fase, criterios, ficheros y si declara cada línea.

    contract: AC-01.pre1, AC-01.post1
    """
    data = parse_plan_contract(PLAN).as_dict()

    assert data["contract_version"] == 1
    assert data["phases"][0] == {
        "title": "Fase 1: Contrato del plan",
        "criteria": [{"uc_id": UC, "ac_id": "AC-01"}, {"uc_id": UC, "ac_id": "AC-04"}],
        "files": ["server/plan_contract.py", "server/tools/plan_contract.py"],
        "declares_criteria": True,
        "declares_files": True,
    }
    assert [p["title"] for p in data["phases"]] == ["Fase 1: Contrato del plan", "Fase 2: Recibos del criterio"]
    assert data["dependencies"] == []


def test_a_plan_whose_phases_carry_both_lines_has_no_incomplete_phase():
    """Con las dos líneas en cada fase no queda ninguna fase incompleta.

    contract: AC-01.pre1, AC-01.post2
    """
    assert incomplete_phases(parse_plan_contract(PLAN)) == []


def test_incomplete_phases_name_what_each_phase_lacks():
    """Una fase sin ficheros, otra sin criterios y otra sin nada salen con el nombre de lo que falta.

    contract: AC-01.pre1, AC-01.post2
    """
    plan = text(
        "## Fase 1: Completa",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Sin ficheros",
        "**Criterios:** UC-12604 AC-02",
        "",
        "## Fase 3: Sin criterios",
        "**Ficheros:** b.py",
        "",
        "## Fase 4: Vacia",
        "- [ ] Documentar",
    )
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 1
    assert incomplete_phases(contract) == [
        {"phase": "Fase 2: Sin ficheros", "missing": ["Ficheros"]},
        {"phase": "Fase 3: Sin criterios", "missing": ["Criterios"]},
        {"phase": "Fase 4: Vacia", "missing": ["Criterios", "Ficheros"]},
    ]


def test_every_criterion_of_the_uc_in_some_phase_leaves_nothing_uncovered():
    """Si cada criterio de la UC está en alguna fase, uncovered_criteria devuelve {}.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    assert uncovered_criteria(parse_plan_contract(PLAN), UC_CRITERIA) == {}


def test_uncovered_criteria_name_those_that_no_phase_covers():
    """Los criterios que ninguna fase cubre salen bajo su UC, en el orden dado.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    only_first_phase = text(
        "## Fase 1: Contrato del plan",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** server/plan_contract.py",
    )
    contract = parse_plan_contract(only_first_phase)

    assert uncovered_criteria(contract, UC_CRITERIA) == {UC: ["AC-02", "AC-03", "AC-04"]}
    assert uncovered_criteria(parse_plan_contract(PLAN), {UC: ["AC-01", "AC-07", "AC-05"]}) == {
        UC: ["AC-07", "AC-05"]
    }


def test_uncovered_criteria_are_reported_per_uc():
    """Con varias UC, un criterio con el mismo número en otra UC no cubre al de esta.

    contract: AC-01.pre2, AC-01.post3
    """
    plan = text(
        "## Fase 1: Primera",
        "**Criterios:** UC-1 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Segunda",
        "**Criterios:** UC-2 AC-01",
        "**Ficheros:** b.py",
    )
    contract = parse_plan_contract(plan)

    assert uncovered_criteria(contract, {"UC-1": ["AC-01"], "UC-2": ["AC-01", "AC-02"]}) == {"UC-2": ["AC-02"]}
    assert uncovered_criteria(contract, {"UC-1": ["AC-01", "AC-02"], "UC-3": ["AC-01"]}) == {
        "UC-1": ["AC-02"],
        "UC-3": ["AC-01"],
    }


@pytest.mark.parametrize(
    "spelling",
    ["AC-01 a AC-03", "AC-01 al AC-03", "AC-01..AC-03", "AC-01–AC-03", "AC-01 hasta 3", "AC-01 to AC-03"],
)
def test_a_range_of_criteria_covers_the_ones_in_between(spelling):
    """Un rango cubre todos los criterios de en medio.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post3
    undefined: un rango de criterios en cualquiera de sus escrituras
    """
    plan = text("## Fase 1: Rango", f"**Criterios:** {UC} {spelling}", "**Ficheros:** a.py")
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02"), (UC, "AC-03")]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03", "AC-04"]}) == {UC: ["AC-04"]}


def test_a_reversed_range_names_only_its_two_ends():
    """Un rango al revés no se expande: solo cuentan sus dos extremos.

    contract: AC-01.pre1, AC-01.post1
    undefined: un rango al revés («AC-03 a AC-01»)
    """
    plan = text("## Fase 1: Al reves", f"**Criterios:** {UC} AC-03 a AC-01", "**Ficheros:** a.py")

    assert parse_plan_contract(plan).phases[0].criteria == [(UC, "AC-03"), (UC, "AC-01")]


def test_criteria_listed_under_the_line_belong_to_the_phase_and_tasks_do_not():
    """Los criterios en lista bajo la línea cuentan (también las casillas de criterio); una tarea la cierra.

    contract: AC-01.pre1, AC-01.post1
    undefined: criterios en lista debajo de la línea y casillas «- [ ]» dentro de ella
    """
    plan = text(
        "## Fase 1: Lista",
        "**Criterios:**",
        "- UC-12604 AC-01",
        "- [x] UC-12604 AC-02",
        "",
        "- [ ] Escribir las pruebas",
        "**Ficheros:**",
        "- server/a.py",
        "- `server/b.py` (nuevo)",
        "",
        "## Fase 2: Otra",
        "**Criterios:** UC-12604 AC-03",
        "**Ficheros:** c.py",
    )
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert contract.phases[0].files == ["server/a.py", "server/b.py"]
    assert contract.phases[0].has_criteria_line and contract.phases[0].has_files_line
    assert contract.phases[1].criteria == [(UC, "AC-03")]
    assert incomplete_phases(contract) == []


def test_criterion_ids_are_compared_whatever_their_format():
    """AC-1 y AC-01 son el mismo criterio y la UC se compara sin mirar mayúsculas.

    contract: AC-01.pre2, AC-01.post1, AC-01.post3
    undefined: ids con otro formato (AC-1, uc-12604 en minúsculas)
    """
    plan = text("## Fase 1: Ids", "**Criterios:** uc-12604 ac-1, AC-2", "**Ficheros:** a.py")
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert uncovered_criteria(contract, {"uc-12604": ["AC-1", "ac-2", "AC-3"]}) == {"uc-12604": ["AC-3"]}


def test_a_repeated_criterion_is_kept_once_and_one_in_two_phases_counts_in_both():
    """Un criterio repetido en una fase se guarda una vez; en dos fases figura en las dos.

    contract: AC-01.pre1, AC-01.post1, AC-01.post3
    undefined: un criterio repetido en una fase o repartido en dos
    """
    plan = text(
        "## Fase 1: Primera",
        "**Criterios:** UC-12604 AC-01, AC-01, AC-02",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Segunda",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** b.py",
    )
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert contract.phases[1].criteria == [(UC, "AC-01")]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02"]}) == {}


def test_criteria_without_uc_in_a_plan_of_one_uc_count_for_that_uc():
    """Sin UC escrita y sin otra UC nombrada, los criterios se toman por los de la UC consultada.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post3
    undefined: un criterio escrito sin su UC en un plan de una sola UC
    """
    plan = text("## Fase 1: Sin UC", "**Criterios:** AC-01, AC-02", "**Ficheros:** a.py")
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 1
    assert contract.phases[0].criteria == [(None, "AC-01"), (None, "AC-02")]
    assert contract.named_ucs == []
    assert contract.ambiguous is False
    assert contract.unattributed() == []
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-03"]}


def test_default_uc_gives_its_uc_to_criteria_written_without_one():
    """default_uc atribuye a la UC consultada los criterios sin UC, si el plan no nombra otra.

    contract: AC-01.pre1, AC-01.post1
    undefined: un criterio escrito sin su UC, con default_uc
    """
    plan = text("## Fase 1: Sin UC", "**Criterios:** AC-01, AC-02", "**Ficheros:** a.py")

    contract = parse_plan_contract(plan, default_uc="uc-12604")
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert contract.named_ucs == [UC]

    other = text(
        "## Fase 1: De otra UC",
        "**Criterios:** UC-99 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Sin UC",
        "**Criterios:** AC-02",
        "**Ficheros:** b.py",
    )
    kept = parse_plan_contract(other, default_uc=UC)
    assert kept.named_ucs == ["UC-99"]
    assert kept.phases[1].criteria == [(None, "AC-02")]


def test_the_uc_of_a_phase_heading_goes_to_its_criteria():
    """Si el encabezado de la fase nombra la UC, sus criterios sin UC son de esa UC.

    contract: AC-01.pre1, AC-01.post1
    undefined: un criterio escrito sin su UC en una fase cuyo encabezado la nombra
    """
    plan = text("### Fase 1 (UC-12604): Contrato", "**Criterios:** AC-01", "**Ficheros:** a.py")
    contract = parse_plan_contract(plan)

    assert contract.phases[0].uc == UC
    assert contract.phases[0].criteria == [(UC, "AC-01")]
    assert uncovered_criteria(contract, {UC: ["AC-01"]}) == {}


def test_a_criterion_without_uc_in_a_plan_of_several_ucs_is_not_attributed():
    """En un plan de varias UC, un criterio sin la suya no cubre a ninguna y se avisa.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post3
    undefined: un criterio escrito sin su UC en un plan que nombra varias UC
    """
    plan = text(
        "## Fase 1: Primera",
        "**Criterios:** UC-1 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Segunda",
        "**Criterios:** UC-2 AC-01",
        "**Ficheros:** b.py",
        "",
        "## Fase 3: Sin UC",
        "**Criterios:** AC-02",
        "**Ficheros:** c.py",
    )
    contract = parse_plan_contract(plan)

    assert contract.named_ucs == ["UC-1", "UC-2"]
    assert contract.ambiguous is True
    assert contract.unattributed() == [{"phase": "Fase 3: Sin UC", "ac_id": "AC-02"}]
    assert uncovered_criteria(contract, {"UC-1": ["AC-01", "AC-02"], "UC-2": ["AC-01"]}) == {"UC-1": ["AC-02"]}


def test_a_heading_with_the_lines_is_a_phase_even_without_the_word_fase():
    """Un encabezado con líneas Criterios o Ficheros es una fase; «Fase 2 bloqueada» o «Fase 2.1», no.

    contract: AC-01.pre1, AC-01.post1, AC-01.post2
    undefined: un encabezado sin «Fase N» con las líneas; títulos «Fase 2 bloqueada» y «Fase 2.1»
    """
    plan = text(
        "## Implementación",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py",
        "### Fase 2 bloqueada",
        "- [ ] pendiente",
        "### Fase 2.1",
        "- [ ] algo",
        "## Fase 3: Con lineas",
        "**Criterios:** UC-12604 AC-02",
        "**Ficheros:** b.py",
    )
    contract = parse_plan_contract(plan)

    assert [p.title for p in contract.phases] == ["Implementación", "Fase 3: Con lineas"]
    assert incomplete_phases(contract) == []


@pytest.mark.parametrize(
    ("marks", "version"),
    [("#", 0), ("##", 1), ("###", 1), ("####", 1), ("#####", 0)],
)
def test_only_headings_from_level_two_to_four_open_a_phase(marks, version):
    """Los encabezados # y ##### no abren fase; ## a #### sí.

    contract: AC-01.pre1, AC-01.post1
    undefined: encabezados de nivel # o #####
    """
    plan = text(f"{marks} Fase 1: Nivel", "**Criterios:** UC-12604 AC-01", "**Ficheros:** a.py")
    contract = parse_plan_contract(plan)

    assert contract.contract_version == version
    assert len(contract.phases) == version


def test_the_lines_accept_a_dash_bold_variants_and_files_in_several_notations():
    """La línea admite guion, dos puntos fuera de las negritas y mayúsculas; los ficheros, comillas, anotación y «ninguno».

    contract: AC-01.pre1, AC-01.post1, AC-01.post2
    undefined: variantes de formato de la línea; ficheros con «ninguno», anotación o comillas invertidas
    """
    plan = text(
        "## Fase 1: Formatos",
        "- **Criterios**: UC-12604 AC-01",
        "* **FICHEROS:** `a.py` y `b.py`; c.py (nuevo), Ninguno",
        "",
        "## Fase 2: Sin ficheros",
        "**Criterios:** UC-12604 AC-02",
        "**Ficheros:** Ninguno",
    )
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01")]
    assert contract.phases[0].files == ["a.py", "b.py", "c.py"]
    assert contract.phases[1].files == []
    assert contract.phases[1].has_files_line is True
    assert incomplete_phases(contract) == []


# --------------------------------------------------------------------------------------------------
# AC-03: la fase y los ficheros que el plan da a un criterio (lo que get_uc toma del plan)
# --------------------------------------------------------------------------------------------------


def test_phase_of_returns_the_phase_that_covers_the_criterion():
    """La fase de un criterio es la que lo cubre, con su título.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    """
    contract = parse_plan_contract(PLAN)

    first = phase_of(contract, UC, "AC-01")
    second = phase_of(contract, UC, "AC-03")

    assert first is contract.phases[0]
    assert first.title == "Fase 1: Contrato del plan"
    assert phase_of(contract, UC, "AC-04") is contract.phases[0]
    assert second is contract.phases[1]
    assert second.title == "Fase 2: Recibos del criterio"
    assert phase_of(contract, UC, "AC-02") is contract.phases[1]


def test_phase_of_reads_ids_in_any_format():
    """El criterio y la UC se buscan sin importar el formato del id.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    """
    contract = parse_plan_contract(PLAN)

    assert phase_of(contract, "uc-12604", "AC-3") is contract.phases[1]
    assert phase_of(contract, UC, " ac-03 ") is contract.phases[1]


def test_the_files_the_plan_expects_for_a_criterion_come_from_its_phase_line():
    """Los ficheros esperados para un criterio son los de la línea Ficheros de su fase, limpios.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2
    """
    contract = parse_plan_contract(PLAN)

    assert phase_of(contract, UC, "AC-01").files == ["server/plan_contract.py", "server/tools/plan_contract.py"]
    assert phase_of(contract, UC, "AC-03").files == ["server/ac_evidence.py", "server/backends/plane_backend.py"]

    plan = text(
        "## Fase 1: Anotados",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py (nuevo), b.py (modificado), `c.py` (nuevo), a.py, `a.py`",
    )
    assert phase_of(parse_plan_contract(plan), UC, "AC-01").files == ["a.py", "b.py", "c.py"]


def test_expected_files_gathers_every_phase_without_repeating_in_plan_order():
    """Todos los ficheros del plan, una vez cada uno y en el orden en que aparecen.

    contract: AC-03.pre1, AC-03.post3
    """
    assert expected_files(parse_plan_contract(PLAN)) == [
        "server/plan_contract.py",
        "server/tools/plan_contract.py",
        "server/ac_evidence.py",
        "server/backends/plane_backend.py",
    ]

    plan = text(
        "## Fase 1: Primera",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py, b.py",
        "",
        "## Fase 2: Segunda",
        "**Criterios:** UC-12604 AC-02",
        "**Ficheros:** b.py, c.py (nuevo)",
        "",
        "## Fase 3: Tercera",
        "**Criterios:** UC-12604 AC-03",
        "**Ficheros:** a.py, d.py",
    )
    assert expected_files(parse_plan_contract(plan)) == ["a.py", "b.py", "c.py", "d.py"]


def test_phase_named_returns_the_phase_a_receipt_names():
    """El título del recibo da la fase que cubre el criterio, sin importar mayúsculas ni espacios.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post4
    """
    contract = parse_plan_contract(PLAN)

    assert phase_named(contract, "Fase 2: Recibos del criterio", UC, "AC-03") is contract.phases[1]
    assert phase_named(contract, "  FASE 2:   recibos DEL criterio ", UC, "AC-03") is contract.phases[1]
    assert phase_named(contract, "Fase 1: Contrato del plan", UC, "AC-04") is contract.phases[0]


def test_phase_named_follows_a_renumbered_plan_through_the_phase_number():
    """Si el título es «Fase N» y el plan se renumeró, vale la fase N que cubre el criterio.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post4
    """
    contract = parse_plan_contract(PLAN)

    assert phase_named(contract, "Fase 2", UC, "AC-03") is contract.phases[1]
    assert phase_named(contract, "Fase 2: Nombre antiguo", UC, "AC-02") is contract.phases[1]
    assert phase_named(contract, "Fase 1", UC, "AC-04") is contract.phases[0]
    # La fase 1 existe pero no cubre AC-03: no se le atribuye.
    assert phase_named(contract, "Fase 1", UC, "AC-03") is None


def test_the_first_phase_that_covers_a_criterion_wins():
    """Un criterio cubierto por dos fases devuelve la primera.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    undefined: un criterio cubierto por varias fases
    """
    plan = text(
        "## Fase 1: Primera",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Segunda",
        "**Criterios:** UC-12604 AC-01, AC-02",
        "**Ficheros:** b.py",
    )
    contract = parse_plan_contract(plan)

    assert phase_of(contract, UC, "AC-01") is contract.phases[0]
    assert phase_of(contract, UC, "AC-02") is contract.phases[1]


def test_phase_of_gives_none_for_a_criterion_no_phase_covers_or_of_another_uc():
    """Un criterio que ninguna fase cubre, o de otra UC, no tiene fase.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    undefined: un criterio que ninguna fase cubre o que es de otra UC
    """
    contract = parse_plan_contract(PLAN)

    assert phase_of(contract, UC, "AC-09") is None
    assert phase_of(contract, "UC-99", "AC-01") is None
    assert phase_of(contract, UC, "no es un criterio") is None


def test_phase_of_with_several_ucs_follows_the_uc_and_never_guesses_an_unattributed_criterion():
    """En un plan de varias UC la fase se busca por UC; un criterio sin UC no se atribuye.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    undefined: un criterio escrito sin UC en un plan que nombra varias UC
    """
    plan = text(
        "## Fase 1: Primera",
        "**Criterios:** UC-1 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 2: Segunda",
        "**Criterios:** UC-2 AC-01",
        "**Ficheros:** b.py",
        "",
        "## Fase 3: Sin UC",
        "**Criterios:** AC-02",
        "**Ficheros:** c.py",
    )
    contract = parse_plan_contract(plan)

    assert phase_of(contract, "UC-1", "AC-01") is contract.phases[0]
    assert phase_of(contract, "UC-2", "AC-01") is contract.phases[1]
    assert phase_of(contract, "UC-1", "AC-02") is None
    assert phase_of(contract, "UC-2", "AC-02") is None

    single = parse_plan_contract(text("## Fase 1: Sin UC", "**Criterios:** AC-01", "**Ficheros:** a.py"))
    assert phase_of(single, UC, "AC-01") is single.phases[0]


def test_phase_of_with_a_plan_of_contract_zero_gives_none():
    """Un plan de contrato 0 no tiene fases que devolver.

    contract: AC-03.pre2, AC-03.post1
    undefined: un plan de contrato 0
    """
    assert phase_of(parse_plan_contract(OLD_PLAN), UC, "AC-01") is None
    assert phase_named(parse_plan_contract(OLD_PLAN), "Fase 1: Implementar", UC, "AC-01") is None


def test_phase_named_with_repeated_titles_picks_the_one_that_covers_and_otherwise_none():
    """Con el mismo título en dos fases gana la que cubre la UC y el criterio; si ninguna, None.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post4
    undefined: dos fases con el mismo título
    """
    plan = text(
        "## Fase 1: Repetida",
        "**Criterios:** UC-1 AC-01",
        "**Ficheros:** a.py",
        "",
        "## Fase 1: Repetida",
        "**Criterios:** UC-2 AC-01",
        "**Ficheros:** b.py",
    )
    contract = parse_plan_contract(plan)

    assert phase_named(contract, "Fase 1: Repetida", "UC-1", "AC-01") is contract.phases[0]
    assert phase_named(contract, "Fase 1: Repetida", "UC-2", "AC-01") is contract.phases[1]
    assert phase_named(contract, "Fase 1: Repetida", "UC-3", "AC-01") is None


def test_phase_named_with_an_unknown_title_gives_none_and_a_single_title_is_kept():
    """Un título que el plan no tiene no da fase; un título único se devuelve aunque no cubra el criterio.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post4
    undefined: un recibo que nombra una fase que el plan no tiene; un título único que no cubre el criterio
    """
    contract = parse_plan_contract(PLAN)

    assert phase_named(contract, "Fase 7: Inexistente", UC, "AC-03") is None
    assert phase_named(contract, "Recibos", UC, "AC-03") is None
    assert phase_named(contract, "", UC, "AC-03") is None
    assert phase_named(contract, None, UC, "AC-03") is None
    assert phase_named(contract, "Fase 1: Contrato del plan", UC, "AC-03") is contract.phases[0]


# --------------------------------------------------------------------------------------------------
# AC-04: un plan anterior sigue funcionando y el informe dice que falta la relación
# --------------------------------------------------------------------------------------------------


def test_an_older_plan_is_read_as_contract_zero_without_phases():
    """Un plan anterior se lee sin fallar, como contrato 0 y sin fases: no se adivinan.

    contract: AC-04.pre1, AC-04.post1
    """
    contract = parse_plan_contract(OLD_PLAN)

    assert contract.contract_version == 0
    assert contract.phases == []
    assert contract.named_ucs == []
    data = contract.as_dict()
    assert data["contract_version"] == 0
    assert data["phases"] == []


@pytest.mark.parametrize(
    "plan",
    [
        pytest.param(text("## Fase 1: Solo ficheros", "**Ficheros:** a.py"), id="solo-ficheros"),
        pytest.param(
            text("## Fase 1: Sin criterio", "**Criterios:** todos", "**Ficheros:** a.py"),
            id="criterios-sin-ac",
        ),
        pytest.param(
            text("## Fase 1: Sin negritas", "Criterios: UC-12604 AC-01", "Ficheros: a.py"),
            id="sin-negritas",
        ),
        pytest.param(text("## Fase 1: Citados", "- Cubre UC-12604 AC-01 y AC-02"), id="criterios-citados"),
        pytest.param("", id="vacio"),
        pytest.param("   \n\n", id="en-blanco"),
        pytest.param(None, id="none"),
    ],
)
def test_a_plan_that_names_no_criterion_in_a_criteria_line_is_contract_zero(plan):
    """Sin una línea **Criterios:** que nombre algún AC-NN el plan es de contrato 0, aunque venga vacío o None.

    contract: AC-04.pre1, AC-04.post1
    undefined: plan vacío, en blanco o None; solo líneas Ficheros; una línea Criterios sin criterio
    """
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 0
    assert contract.phases == []


def test_the_report_says_the_relation_between_phases_and_criteria_is_missing():
    """El aviso del informe dice que el plan no relaciona fases y criterios y que los planes nuevos sí.

    contract: AC-04.pre1, AC-04.post2
    """
    notice = CONTRACT_NOTICE_OLD_PLAN

    assert isinstance(notice, str) and notice
    assert "no relaciona fases y criterios" in notice
    assert "**Criterios:**" in notice
    assert "**Ficheros:**" in notice
    assert "Los planes nuevos de /plan las llevan" in notice


def test_queries_on_an_older_plan_do_not_fail_and_claim_nothing_about_the_plan():
    """Con un plan anterior no hay fase, ni ficheros, ni fases incompletas; todos los criterios quedan sin relación.

    contract: AC-04.pre1, AC-04.post3
    """
    contract = parse_plan_contract(OLD_PLAN)

    assert phase_of(contract, UC, "AC-01") is None
    assert expected_files(contract) == []
    assert incomplete_phases(contract) == []
    assert uncovered_criteria(contract, UC_CRITERIA) == {UC: ["AC-01", "AC-02", "AC-03", "AC-04"]}
    assert contract.ambiguous is False
    assert contract.unattributed() == []


@pytest.mark.parametrize("mark", [FENCE, "~~~", "`" * 4], ids=["backticks", "tildes", "four-backticks"])
def test_criteria_lines_inside_a_code_block_are_an_example_and_do_not_make_a_new_plan(mark):
    """Un ejemplo dentro de un bloque de código no vuelve nuevo a un plan anterior.

    contract: AC-04.pre1, AC-04.post4
    """
    plan = text(
        "## Fase 1: Hacer",
        "Asi se escribe una fase:",
        f"{mark}markdown",
        "### Fase 1: Retirar sin renumerar",
        "**Criterios:** UC-12501 AC-01, AC-03",
        "**Ficheros:** server/tools/spec_mutations.py",
        mark,
    )
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 0
    assert contract.phases == []


def test_an_example_in_a_code_block_does_not_add_phases_to_a_real_plan():
    """En un plan nuevo, las fases de un ejemplo en bloque de código no cuentan.

    contract: AC-01.pre1, AC-01.post1
    undefined: un ejemplo de fase dentro de un bloque de código en un plan nuevo
    """
    plan = text(
        "## Fase 1: Real",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py",
        "Ejemplo:",
        FENCE,
        "### Fase 9: Ejemplo",
        "**Criterios:** UC-99 AC-09",
        "**Ficheros:** z.py",
        FENCE,
        "",
        "## Fase 2: Otra real",
        "**Criterios:** UC-12604 AC-02",
        "**Ficheros:** b.py",
    )
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 1
    assert [p.title for p in contract.phases] == ["Fase 1: Real", "Fase 2: Otra real"]
    assert contract.named_ucs == [UC]
    assert expected_files(contract) == ["a.py", "b.py"]


def test_a_longer_fence_is_not_closed_by_a_shorter_one_nor_a_tilde_fence_by_backticks():
    """Una valla de cuatro comillas no la cierra una de tres, ni una ~~~ una de comillas; lo de después sí cuenta.

    contract: AC-04.pre1, AC-04.post4
    undefined: una valla más larga que contiene otra más corta; una valla ~~~ que contiene una ```
    """
    four = "`" * 4
    nested = text(
        "## Fase 1: Ejemplo",
        f"{four}markdown",
        FENCE,
        "**Criterios:** UC-9 AC-02",
        FENCE,
        four,
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py",
    )
    contract = parse_plan_contract(nested)
    assert contract.contract_version == 1
    assert contract.phases[0].criteria == [(UC, "AC-01")]

    tilde = text(
        "## Fase 1: Ejemplo",
        "~~~",
        FENCE,
        "**Criterios:** UC-9 AC-02",
        "~~~",
        "**Criterios:** UC-12604 AC-01",
        "**Ficheros:** a.py",
    )
    contract = parse_plan_contract(tilde)
    assert contract.contract_version == 1
    assert contract.phases[0].criteria == [(UC, "AC-01")]

    only_inside = text(
        "## Fase 1: Ejemplo",
        f"{four}markdown",
        FENCE,
        "**Criterios:** UC-9 AC-02",
        FENCE,
        "**Criterios:** UC-9 AC-03",
        four,
    )
    assert parse_plan_contract(only_inside).contract_version == 0


def test_an_older_plan_keeps_its_dependencies_and_a_missing_section_is_none():
    """El contrato 0 conserva las dependencias; sin sección son None y con «Ninguna», lista vacía.

    contract: AC-04.pre1, AC-04.post1
    undefined: un plan anterior con sección «Dependencias nuevas»: si la conserva, None frente a «Ninguna»
    """
    contract = parse_plan_contract(OLD_PLAN)
    assert contract.contract_version == 0
    assert contract.dependencies == [
        {"ecosystem": "pypi", "name": "rapidfuzz"},
        {"ecosystem": "pypi", "name": "httpx>=0.27"},
    ]
    assert contract.as_dict()["dependencies"] == contract.dependencies

    without_section = parse_plan_contract(text("## Fase 1: Hacer", "- [ ] algo"))
    assert without_section.contract_version == 0
    assert without_section.dependencies is None

    none_needed = parse_plan_contract(text("## Fase 1: Hacer", "## Dependencias nuevas", "Ninguna"))
    assert none_needed.contract_version == 0
    assert none_needed.dependencies == []
