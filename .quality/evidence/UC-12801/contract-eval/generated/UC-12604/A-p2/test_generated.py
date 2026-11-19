"""Pruebas de aceptación de UC-12604 contra las funciones públicas de server/plan_contract.py.

Criterios de la UC:
- AC-01: el plan indica en cada fase los criterios que cubre y cada criterio de la UC aparece en al
  menos una fase.
- AC-02: el tablero guarda ficheros y prueba al marcar un criterio  -> no depende de plan_contract
  (recibos y backends); fuera de este fichero.
- AC-03: `get_uc` devuelve para cada criterio su fase, sus ficheros y su prueba -> aquí solo la parte
  que sale del plan (la fase y los ficheros que el plan espera para esa fase).
- AC-04: un plan anterior, sin relación fases-criterios, no se adivina y el informe dice que falta.
"""

from __future__ import annotations

import pytest

from server.plan_contract import (
    CONTRACT_NOTICE_OLD_PLAN,
    PlanContract,
    expected_files,
    incomplete_phases,
    normalize_ac,
    parse_plan_contract,
    phase_by_number,
    phase_named,
    phase_of,
    uncovered_criteria,
)

UC = "UC-12604"
ALL_ACS = ["AC-01", "AC-02", "AC-03", "AC-04"]

PLAN_NEW = """# Plan UC-12604

## Resumen
Texto libre del plan.

### Fase 1: Leer el contrato
**Criterios:** UC-12604 AC-01, AC-04
**Ficheros:** server/plan_contract.py, tests/test_plan_contract.py

### Fase 2: Recibos y lectura
**Criterios:** UC-12604 AC-02, AC-03
**Ficheros:** server/ac_evidence.py (nuevo), `server/tools/spec_driven.py`

## Dependencias nuevas
Ninguna
"""

PLAN_OLD = """# Plan UC-12604

## Fase 1: Parser
Escribir el parser del plan.
- [ ] Parser

## Fase 2: Tools
Registrar la tool.
- [ ] Tool

**Ficheros:** server/plan_contract.py
"""


# ---------------------------------------------------------------------------
# AC-01: el plan indica en cada fase los criterios que cubre; cada criterio de la UC en alguna fase
# ---------------------------------------------------------------------------


def test_ac01_each_phase_declares_its_criteria_and_files():
    """AC-01: cada fase lleva su línea de criterios (con la UC) y de ficheros."""
    contract = parse_plan_contract(PLAN_NEW)

    assert contract.contract_version == 1
    assert [p.title for p in contract.phases] == ["Fase 1: Leer el contrato", "Fase 2: Recibos y lectura"]
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-04")]
    assert contract.phases[1].criteria == [(UC, "AC-02"), (UC, "AC-03")]
    assert contract.phases[0].has_criteria_line is True
    assert contract.phases[1].has_criteria_line is True
    assert contract.phases[0].files == ["server/plan_contract.py", "tests/test_plan_contract.py"]
    assert contract.phases[1].files == ["server/ac_evidence.py", "server/tools/spec_driven.py"]
    assert contract.named_ucs == [UC]


def test_ac01_every_criterion_of_the_uc_covered_means_nothing_uncovered():
    """AC-01: los cuatro criterios de la UC aparecen en alguna fase -> no queda ninguno sin cubrir."""
    contract = parse_plan_contract(PLAN_NEW)

    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {}


def test_ac01_a_criterion_in_no_phase_is_reported_for_its_uc():
    """AC-01: un criterio que ninguna fase cubre sale en la lista de los no cubiertos de su UC."""
    plan = """### Fase 1: Única
**Criterios:** UC-12604 AC-01, AC-02, AC-03
**Ficheros:** server/plan_contract.py
"""
    contract = parse_plan_contract(plan)

    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {UC: ["AC-04"]}


def test_ac01_several_criteria_uncovered_keep_the_uc_order():
    """AC-01: varios criterios sin fase salen todos, en el orden en que los pide la UC."""
    plan = """### Fase 1: Única
**Criterios:** UC-12604 AC-02
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {UC: ["AC-01", "AC-03", "AC-04"]}


def test_ac01_a_criterion_in_two_phases_counts_as_covered():
    """AC-01: «en al menos una fase»: un criterio repetido en dos fases está cubierto."""
    plan = """### Fase 1: Parser
**Criterios:** UC-12604 AC-01, AC-02
**Ficheros:** a.py

### Fase 2: Tools
**Criterios:** UC-12604 AC-02, AC-03, AC-04
**Ficheros:** b.py
"""
    contract = parse_plan_contract(plan)

    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {}
    assert phase_of(contract, UC, "AC-02").title == "Fase 1: Parser"  # la primera que lo cubre


def test_ac01_criterion_ids_with_one_or_two_digits_are_the_same_criterion():
    """AC-01: «AC-1» y «AC-01» son el mismo criterio al cubrirlo y al preguntar por él."""
    plan = """### Fase 1: Única
**Criterios:** UC-12604 AC-1, AC-2, AC-3, AC-4
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02"), (UC, "AC-03"), (UC, "AC-04")]
    assert uncovered_criteria(contract, {UC: ["AC-1", "AC-04"]}) == {}
    assert normalize_ac("AC-3") == "AC-03"
    assert normalize_ac(" ac-03 ") == "AC-03"


def test_ac01_a_range_of_criteria_covers_all_those_in_between():
    """AC-01: «AC-01 a AC-04» cubre AC-01, AC-02, AC-03 y AC-04."""
    plan = """### Fase 1: Todo
**Criterios:** UC-12604 AC-01 a AC-04
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02"), (UC, "AC-03"), (UC, "AC-04")]
    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {}


@pytest.mark.parametrize("separator", ["..", "–", "—", "hasta", "al", "to"])
def test_ac01_other_range_spellings_cover_the_same_criteria(separator):
    """AC-01: los rangos con «..», raya, «hasta», «al» o «to» también cubren los de en medio."""
    plan = f"""### Fase 1: Todo
**Criterios:** UC-12604 AC-01 {separator} AC-03
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert [ac for _, ac in contract.phases[0].criteria] == ["AC-01", "AC-02", "AC-03"]


def test_ac01_criteria_written_as_a_list_under_the_line_are_read():
    """AC-01: la línea de criterios puede traer la lista justo debajo, en elementos de lista."""
    plan = """### Fase 1: Lista
**Criterios:**
- UC-12604 AC-01
- UC-12604 AC-03

**Ficheros:**
- server/plan_contract.py
- tests/test_plan_contract.py
"""
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-03")]
    assert contract.phases[0].files == ["server/plan_contract.py", "tests/test_plan_contract.py"]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-02"]}


def test_ac01_criterion_checkboxes_under_the_line_belong_to_the_list():
    """AC-01: una casilla «- [ ] UC-… AC-NN» bajo **Criterios:** sigue siendo parte de la lista."""
    plan = """### Fase 1: Casillas
**Criterios:**
- [ ] UC-12604 AC-01
- [x] UC-12604 AC-02: texto del criterio
"""
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]


def test_ac01_a_phase_without_its_two_lines_is_reported_with_what_it_lacks():
    """AC-01: una fase «Fase N» sin línea de criterios ni de ficheros se señala con lo que le falta."""
    plan = """### Fase 1: Con todo
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py

### Fase 2: Sin nada
Texto de la fase sin las líneas del contrato.
"""
    contract = parse_plan_contract(plan)

    assert [p.title for p in contract.phases] == ["Fase 1: Con todo", "Fase 2: Sin nada"]
    assert incomplete_phases(contract) == [{"phase": "Fase 2: Sin nada", "missing": ["Criterios", "Ficheros"]}]


def test_ac01_a_phase_with_only_the_criteria_line_misses_the_files_line():
    """AC-01: la fase que trae criterios pero no ficheros se señala con «Ficheros»."""
    plan = """### Fase 1: Solo criterios
**Criterios:** UC-12604 AC-01, AC-02
"""
    contract = parse_plan_contract(plan)

    assert incomplete_phases(contract) == [{"phase": "Fase 1: Solo criterios", "missing": ["Ficheros"]}]


def test_ac01_a_phase_with_only_the_files_line_misses_the_criteria_line():
    """AC-01: la fase que trae ficheros pero no criterios se señala con «Criterios»."""
    plan = """### Fase 1: Con criterios
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py

### Fase 2: Solo ficheros
**Ficheros:** b.py
"""
    contract = parse_plan_contract(plan)

    assert incomplete_phases(contract) == [{"phase": "Fase 2: Solo ficheros", "missing": ["Criterios"]}]


def test_ac01_a_complete_plan_has_no_incomplete_phases():
    """AC-01: un plan con las dos líneas en cada fase no tiene fases incompletas."""
    assert incomplete_phases(parse_plan_contract(PLAN_NEW)) == []


@pytest.mark.parametrize(
    "title",
    [
        "Fase 3: Título con dos puntos",
        "Fase 3. Título con punto",
        "Fase 3 · Título con punto medio",
        "Fase 3",
        "Phase 3: English title",
    ],
)
def test_ac01_phase_titles_in_the_usual_spellings_are_phases(title):
    """AC-01: «Fase N: …», «Fase N. …», «Fase N · …», «Fase N» y «Phase N» son fases del plan."""
    plan = f"""### {title}
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert [p.title for p in contract.phases] == [title]
    assert contract.phases[0].criteria == [(UC, "AC-01")]


def test_ac01_a_phase_heading_names_the_uc_of_criteria_written_without_it():
    """AC-01: un criterio escrito sin UC toma la que nombra el encabezado de su fase."""
    plan = """### Fase 1: UC-12604 Parser
**Criterios:** AC-01, AC-02
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert contract.phases[0].uc == UC
    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-03"]}


def test_ac01_default_uc_gives_its_uc_to_criteria_written_without_it():
    """AC-01: con `default_uc`, los criterios sin UC de un plan que no nombra otra son de esa UC."""
    plan = """### Fase 1: Única
**Criterios:** AC-01, AC-02
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan, default_uc="uc-12604")

    assert contract.phases[0].criteria == [(UC, "AC-01"), (UC, "AC-02")]
    assert contract.named_ucs == [UC]
    assert contract.ambiguous is False
    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {UC: ["AC-03", "AC-04"]}


def test_ac01_criteria_without_uc_in_a_single_uc_plan_still_cover_that_uc():
    """AC-01: en un plan de una sola UC, un criterio sin UC cuenta como criterio de esa UC."""
    plan = """### Fase 1: Única
**Criterios:** AC-01, AC-02, AC-03, AC-04
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert contract.ambiguous is False
    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {}


def test_ac01_a_plan_that_names_several_ucs_does_not_attribute_criteria_without_one():
    """AC-01: en un plan de varias UC, un criterio sin la suya no cubre a ninguna y se avisa."""
    plan = """### Fase 1: UC-12601 Primera
**Criterios:** AC-01
**Ficheros:** a.py

### Fase 2: UC-12604 Segunda
**Criterios:** AC-01, AC-02
**Ficheros:** b.py

### Fase 3: Cierre
**Criterios:** AC-03
**Ficheros:** c.py
"""
    contract = parse_plan_contract(plan)

    assert contract.named_ucs == ["UC-12601", UC]
    assert contract.ambiguous is True
    assert contract.unattributed() == [{"phase": "Fase 3: Cierre", "ac_id": "AC-03"}]
    # AC-03 de UC-12604 no está cubierto: la fase 3 no dice de qué UC es.
    assert uncovered_criteria(contract, {UC: ["AC-01", "AC-02", "AC-03"]}) == {UC: ["AC-03"]}


def test_ac01_uncovered_is_computed_per_uc_when_the_plan_covers_several():
    """AC-01: con varias UC, cada una tiene su propia lista de criterios sin cubrir."""
    plan = """### Fase 1: Primera
**Criterios:** UC-12601 AC-01, AC-02; UC-12604 AC-01
**Ficheros:** a.py

### Fase 2: Segunda
**Criterios:** UC-12604 AC-02
**Ficheros:** b.py
"""
    contract = parse_plan_contract(plan)

    assert uncovered_criteria(contract, {"UC-12601": ["AC-01", "AC-02", "AC-03"], UC: ["AC-01", "AC-02", "AC-03"]}) == {
        "UC-12601": ["AC-03"],
        UC: ["AC-03"],
    }


def test_ac01_a_plan_without_unattributed_criteria_reports_none():
    """AC-01: si todo criterio dice su UC (o el plan es de una), `unattributed` va vacío."""
    assert parse_plan_contract(PLAN_NEW).unattributed() == []


def test_ac01_the_contract_as_dict_lists_each_phase_with_its_criteria_and_files():
    """AC-01: la forma serializada trae, por fase, sus criterios con UC, sus ficheros y qué líneas declara."""
    data = parse_plan_contract(PLAN_NEW).as_dict()

    assert data["contract_version"] == 1
    assert data["dependencies"] == []
    assert data["phases"][0] == {
        "title": "Fase 1: Leer el contrato",
        "criteria": [{"uc_id": UC, "ac_id": "AC-01"}, {"uc_id": UC, "ac_id": "AC-04"}],
        "files": ["server/plan_contract.py", "tests/test_plan_contract.py"],
        "declares_criteria": True,
        "declares_files": True,
    }
    assert [c["ac_id"] for c in data["phases"][1]["criteria"]] == ["AC-02", "AC-03"]


def test_ac01_criteria_lines_inside_a_code_block_do_not_cover_anything():
    """AC-01: lo que va en un bloque de código es un ejemplo y no cubre criterios."""
    plan = """### Fase 1: Real
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py

### Fase 2: Ejemplo
Así se escribe una fase:

```markdown
### Fase 9: De mentira
**Criterios:** UC-12604 AC-02, AC-03, AC-04
**Ficheros:** falso.py
```
"""
    contract = parse_plan_contract(plan)

    assert [p.title for p in contract.phases] == ["Fase 1: Real", "Fase 2: Ejemplo"]
    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {UC: ["AC-02", "AC-03", "AC-04"]}
    assert expected_files(contract) == ["a.py"]


@pytest.mark.parametrize("fence", ["~~~", "````"])
def test_ac01_tilde_and_longer_fences_hide_their_content_too(fence):
    """AC-01: un bloque con ~~~ o con cuatro comillas también esconde su contenido del contrato."""
    plan = f"""### Fase 1: Real
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py

{fence}
**Criterios:** UC-12604 AC-04
```
**Criterios:** UC-12604 AC-03
{fence}
"""
    contract = parse_plan_contract(plan)

    assert contract.phases[0].criteria == [(UC, "AC-01")]


# ---------------------------------------------------------------------------
# AC-03: get_uc devuelve la fase y los ficheros del plan para cada criterio (parte del plan)
# ---------------------------------------------------------------------------


def test_ac03_phase_of_gives_the_phase_that_covers_each_criterion():
    """AC-03: para cada criterio, la fase del plan que lo cubre."""
    contract = parse_plan_contract(PLAN_NEW)

    assert phase_of(contract, UC, "AC-01").title == "Fase 1: Leer el contrato"
    assert phase_of(contract, UC, "AC-04").title == "Fase 1: Leer el contrato"
    assert phase_of(contract, UC, "AC-02").title == "Fase 2: Recibos y lectura"
    assert phase_of(contract, UC, "AC-03").title == "Fase 2: Recibos y lectura"


def test_ac03_phase_of_accepts_the_short_criterion_id_and_a_lowercase_uc():
    """AC-03: «AC-3» y «uc-12604» llegan a la misma fase que «AC-03» y «UC-12604»."""
    contract = parse_plan_contract(PLAN_NEW)

    assert phase_of(contract, "uc-12604", "AC-3") is phase_of(contract, UC, "AC-03")
    assert phase_of(contract, UC, "AC-3").title == "Fase 2: Recibos y lectura"


def test_ac03_phase_of_a_criterion_no_phase_covers_is_none():
    """AC-03: un criterio que el plan no cubre no tiene fase."""
    contract = parse_plan_contract(PLAN_NEW)

    assert phase_of(contract, UC, "AC-09") is None


def test_ac03_phase_of_does_not_take_a_criterion_of_another_uc():
    """AC-03: en un plan de varias UC, la fase de un criterio es la de su UC y no la de otra con su mismo AC."""
    plan = """### Fase 1: UC-12601 Primera
**Criterios:** AC-01
**Ficheros:** a.py

### Fase 2: UC-12604 Segunda
**Criterios:** AC-01
**Ficheros:** b.py
"""
    contract = parse_plan_contract(plan)

    assert phase_of(contract, "UC-12601", "AC-01").title == "Fase 1: UC-12601 Primera"
    assert phase_of(contract, UC, "AC-01").title == "Fase 2: UC-12604 Segunda"
    assert phase_of(contract, "UC-99999", "AC-01") is None


def test_ac03_the_files_the_plan_expects_for_a_criterion_are_those_of_its_phase():
    """AC-03: los ficheros que el plan espera para un criterio son los de su fase."""
    contract = parse_plan_contract(PLAN_NEW)

    assert phase_of(contract, UC, "AC-01").files == ["server/plan_contract.py", "tests/test_plan_contract.py"]
    assert phase_of(contract, UC, "AC-03").files == ["server/ac_evidence.py", "server/tools/spec_driven.py"]


def test_ac03_expected_files_lists_all_the_plan_files_once_in_order():
    """AC-03: todos los ficheros del plan, sin repetir y en el orden en que aparecen."""
    plan = """### Fase 1: Primera
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py, b.py

### Fase 2: Segunda
**Criterios:** UC-12604 AC-02
**Ficheros:** b.py, c.py
"""
    contract = parse_plan_contract(plan)

    assert expected_files(contract) == ["a.py", "b.py", "c.py"]


def test_ac03_a_receipt_naming_the_phase_by_its_title_finds_that_phase():
    """AC-03: el recibo que nombra la fase por su título (aunque cambie el espacio o las mayúsculas) la encuentra."""
    contract = parse_plan_contract(PLAN_NEW)

    found = phase_named(contract, "  fase 2:   recibos y lectura ", UC, "AC-03")
    assert found is not None
    assert found.title == "Fase 2: Recibos y lectura"


def test_ac03_a_receipt_naming_only_phase_n_finds_the_phase_that_covers_its_criterion():
    """AC-03: si el recibo dice «Fase 2» y el plan se renumeró o abrevia, vale la fase 2 que cubre el criterio."""
    contract = parse_plan_contract(PLAN_NEW)

    assert phase_named(contract, "Fase 2", UC, "AC-03").title == "Fase 2: Recibos y lectura"
    # la Fase 2 no cubre AC-01: no se adivina otra.
    assert phase_named(contract, "Fase 2", UC, "AC-01") is None


def test_ac03_a_receipt_naming_an_unknown_phase_gets_no_phase():
    """AC-03: un recibo con una fase que el plan no tiene no recibe ninguna."""
    contract = parse_plan_contract(PLAN_NEW)

    assert phase_named(contract, "Fase 7: Inexistente", UC, "AC-01") is None


def test_ac03_phase_by_number_looks_up_the_phase_by_its_number_not_its_position():
    """AC-03: «Fase N» se busca por su número: un plan que empieza en la Fase 0 no se desplaza."""
    plan = """### Fase 0: Preparar
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py

### Fase 1: Hacer
**Criterios:** UC-12604 AC-02, AC-03
**Ficheros:** b.py
"""
    contract = parse_plan_contract(plan)

    assert phase_by_number(contract, 0).title == "Fase 0: Preparar"
    assert phase_by_number(contract, 1).files == ["b.py"]
    assert phase_by_number(contract, 2) is None


def test_ac03_phase_by_number_does_not_guess_when_two_phases_share_the_number():
    """AC-03: con dos fases con el mismo número (plan de varias UC) no se adivina cuál."""
    plan = """### Fase 1: UC-12601 Primera
**Criterios:** AC-01
**Ficheros:** a.py

### Fase 1: UC-12604 Segunda
**Criterios:** AC-01
**Ficheros:** b.py
"""
    contract = parse_plan_contract(plan)

    assert phase_by_number(contract, 1) is None


# ---------------------------------------------------------------------------
# AC-04: un plan anterior sin relación fases-criterios no se adivina y el informe dice que falta
# ---------------------------------------------------------------------------


def test_ac04_an_older_plan_is_contract_0_with_no_phases():
    """AC-04: un plan sin líneas **Criterios:** es de contrato 0 y no tiene fases (no se adivinan)."""
    contract = parse_plan_contract(PLAN_OLD)

    assert contract.contract_version == 0
    assert contract.phases == []
    assert contract.as_dict() == {"contract_version": 0, "phases": [], "dependencies": None}


def test_ac04_a_plan_with_only_loose_files_lines_is_still_contract_0():
    """AC-04: líneas sueltas de ficheros sin ningún criterio no hacen un plan de contrato 1."""
    plan = """### Fase 1: Parser
**Ficheros:** server/plan_contract.py

### Fase 2: Tools
**Ficheros:** server/tools/plan_contract.py
"""
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 0
    assert contract.phases == []


def test_ac04_a_criteria_line_that_names_no_criterion_does_not_make_contract_1():
    """AC-04: una línea **Criterios:** sin ningún AC-NN no cuenta como relación entre fases y criterios."""
    plan = """### Fase 1: Parser
**Criterios:** ninguno todavía
**Ficheros:** a.py
"""
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 0
    assert contract.phases == []


@pytest.mark.parametrize("text", ["", None, "   \n\n  "])
def test_ac04_an_empty_plan_is_contract_0(text):
    """AC-04: un plan vacío (o sin texto) tampoco explota: contrato 0."""
    contract = parse_plan_contract(text)

    assert contract.contract_version == 0
    assert contract.phases == []


def test_ac04_the_queries_on_an_older_plan_work_and_find_no_relation():
    """AC-04: sobre un plan anterior las consultas no fallan: no hay fase, ni ficheros, ni fases incompletas."""
    contract = parse_plan_contract(PLAN_OLD)

    assert phase_of(contract, UC, "AC-01") is None
    assert phase_by_number(contract, 1) is None
    assert phase_named(contract, "Fase 1: Parser", UC, "AC-01") is None
    assert expected_files(contract) == []
    assert incomplete_phases(contract) == []
    assert contract.unattributed() == []
    assert contract.ambiguous is False
    assert contract.named_ucs == []


def test_ac04_with_an_older_plan_every_criterion_is_reported_as_not_covered():
    """AC-04: con un plan sin relación, ningún criterio figura cubierto (la relación no está)."""
    contract = parse_plan_contract(PLAN_OLD)

    assert uncovered_criteria(contract, {UC: ALL_ACS}) == {UC: ALL_ACS}


def test_ac04_the_older_plan_notice_says_the_relation_between_phases_and_criteria_is_missing():
    """AC-04: el aviso del informe dice que el plan no relaciona fases y criterios."""
    assert isinstance(CONTRACT_NOTICE_OLD_PLAN, str)
    assert "no relaciona fases y criterios" in CONTRACT_NOTICE_OLD_PLAN
    assert "**Criterios:**" in CONTRACT_NOTICE_OLD_PLAN
    assert "**Ficheros:**" in CONTRACT_NOTICE_OLD_PLAN
    assert "la fase de cada criterio no están disponibles" in CONTRACT_NOTICE_OLD_PLAN


def test_ac04_example_lines_in_a_code_block_do_not_turn_an_older_plan_into_contract_1():
    """AC-04: un plan anterior que enseña las líneas como ejemplo en un bloque de código sigue siendo de contrato 0."""
    plan = """## Fase 1: Parser
Cada fase se escribe así:

```
### Fase 1: Ejemplo
**Criterios:** UC-12604 AC-01
**Ficheros:** server/plan_contract.py
```
"""
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 0
    assert contract.phases == []


def test_ac04_a_plan_with_a_real_criteria_line_is_contract_1_even_with_examples_around():
    """AC-04: la versión de contrato la dan las líneas reales: con una fuera de bloque de código es 1."""
    plan = """### Fase 1: Real
**Criterios:** UC-12604 AC-01
**Ficheros:** a.py

~~~
**Criterios:** UC-12604 AC-02
~~~
"""
    contract = parse_plan_contract(plan)

    assert contract.contract_version == 1
    assert isinstance(contract, PlanContract)
    assert [c for p in contract.phases for c in p.criteria] == [(UC, "AC-01")]
