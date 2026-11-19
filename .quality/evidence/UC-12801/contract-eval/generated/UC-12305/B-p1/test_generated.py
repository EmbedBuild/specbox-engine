"""Pruebas de aceptación de UC-12305 / AC-02, generadas desde su contrato (contract.json).

AC-02: `start_uc` no arranca una UC cuyo texto o criterios contienen una marca `[POR DECIDIR`, y el
error muestra cada marca.

Se prueban `pending_marks`, `pending_reason` y `_eval_pending_decisions` de
`server/coordination/enforcement.py`, sin tablero, red ni disco.

Los criterios AC-01 (plantillas), AC-03 (el triaje de /implement) y AC-04 (los modos «warn» y «block»
y la UC anterior a la regla, que decide `start_uc`) no dependen de esas tres funciones y no se prueban aquí.
"""

from __future__ import annotations

import pytest

from server.coordination.enforcement import (
    _eval_pending_decisions,
    pending_marks,
    pending_reason,
)


def make_uc(*, name: str = "Cobrar al cliente", description: str = "", acs: list[tuple[str, str]] | None = None):
    """Una UC como la que ve la medida: `acs` con `ac_id` y `text`, más nombre y descripción."""
    return {
        "uc_id": "UC-900",
        "name": name,
        "description": description,
        "acs": [{"ac_id": ac_id, "text": text} for ac_id, text in (acs or [])],
    }


def by_where(marks: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(m["where"], m["mark"]) for m in marks]


# ── La UC con marca no arranca y el error muestra cada marca ─────────────────────────────────────


def test_mark_in_the_description_stops_the_uc_and_the_error_shows_it():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2, AC-02.post3"""
    uc = make_uc(description="Cobro con tarjeta. [POR DECIDIR: Stripe o Redsys] para el TPV.")

    reason = _eval_pending_decisions(uc)
    marks = pending_marks(uc)

    # post1: hay motivo, la UC no arranca
    assert reason is not None
    assert isinstance(reason, str) and reason.strip()
    # post2: el motivo muestra la marca y dónde está
    assert "Stripe o Redsys" in reason
    assert "la descripción" in reason
    # post3: una entrada con ubicación y lo que falta por decidir
    assert marks == [{"where": "la descripción", "mark": "Stripe o Redsys"}]


def test_mark_in_the_name_stops_the_uc_and_the_error_shows_it():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2, AC-02.post3"""
    uc = make_uc(name="Pagos [POR DECIDIR: el proveedor de pagos]")

    reason = _eval_pending_decisions(uc)
    marks = pending_marks(uc)

    assert reason is not None  # post1
    assert "el proveedor de pagos" in reason  # post2
    assert "el nombre" in reason  # post2: dónde está
    assert marks == [{"where": "el nombre", "mark": "el proveedor de pagos"}]  # post3


def test_mark_in_a_criterion_stops_the_uc_and_the_error_shows_it():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3"""
    uc = make_uc(
        acs=[
            ("AC-01", "El cobro se registra en el libro de caja."),
            ("AC-02", "El importe se cobra con [POR DECIDIR: Stripe o Redsys] y aparece en el recibo."),
        ]
    )

    reason = _eval_pending_decisions(uc)
    marks = pending_marks(uc)

    assert reason is not None  # post1
    assert "Stripe o Redsys" in reason  # post2
    assert "AC-02" in reason  # post2: el criterio donde está
    assert marks == [{"where": "AC-02", "mark": "Stripe o Redsys"}]  # post3


def test_every_mark_of_the_uc_is_shown_wherever_it_is():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3"""
    uc = make_uc(
        name="Cobro [POR DECIDIR: la moneda]",
        description="Resumen. [POR DECIDIR: el plazo de devolución]",
        acs=[
            ("AC-01", "Cobra con [POR DECIDIR: la pasarela de pago]."),
            ("AC-03", "Emite factura [POR DECIDIR: con o sin IVA]."),
        ],
    )

    reason = _eval_pending_decisions(uc)
    marks = pending_marks(uc)

    assert reason is not None  # post1
    for what in ("la pasarela de pago", "con o sin IVA", "la moneda", "el plazo de devolución"):
        assert what in reason  # post2: cada marca aparece en el error
    for where in ("AC-01", "AC-03", "el nombre", "la descripción"):
        assert where in reason  # post2: y dónde está cada una
    assert len(marks) == 4  # post3: una entrada por marca
    assert set(by_where(marks)) == {
        ("AC-01", "la pasarela de pago"),
        ("AC-03", "con o sin IVA"),
        ("el nombre", "la moneda"),
        ("la descripción", "el plazo de devolución"),
    }
    assert all(set(m) == {"where", "mark"} for m in marks)  # post3: ubicación y lo que falta por decidir


def test_the_reason_is_the_one_phrase_pending_reason_builds_from_the_marks():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2"""
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: la pasarela de pago].")])

    marks = pending_marks(uc)
    reason = pending_reason(marks)

    assert reason is not None  # post1
    assert _eval_pending_decisions(uc) == reason  # post1: lo que evalúa la medida es ese motivo
    assert reason == "Quedan 1 marca(s) «por decidir»: AC-01: «la pasarela de pago»."  # post2
    assert pending_reason([]) is None  # sin marcas, sin motivo: contraste de post1


# ── Lo que el criterio no define y el código resuelve ────────────────────────────────────────────


def test_a_uc_without_marks_has_no_reason():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post3

    undefined: si arranca una UC sin ninguna marca (contraste de post1: sin marca, sin motivo).
    """
    uc = make_uc(
        description="Cobro con tarjeta, sin nada pendiente.",
        acs=[("AC-01", "El cobro se registra en el libro de caja.")],
    )

    assert _eval_pending_decisions(uc) is None
    assert pending_marks(uc) == []
    assert pending_reason(pending_marks(uc)) is None


@pytest.mark.parametrize(
    "uc",
    [
        {},
        {"acs": None, "name": None, "description": None},
        {"acs": [], "name": "", "description": ""},
        make_uc(name="", description="", acs=[]),
        {"name": "Solo nombre"},
        {"acs": [{"ac_id": "AC-01"}]},
        {"acs": [{"ac_id": "AC-01", "text": None}]},
    ],
)
def test_a_uc_without_criteria_description_or_name_has_no_marks(uc):
    """contract: AC-02.pre1, AC-02.post1, AC-02.post3

    undefined: UC sin criterios, sin descripción o sin nombre (vacíos o ausentes).
    """
    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


def test_a_uc_with_no_criteria_still_stops_for_a_mark_in_its_text():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post3

    undefined: una UC sin criterios (acs ausente o None) cuyo texto lleva una marca.
    """
    for uc in (
        {"name": "Cobro [POR DECIDIR: la moneda]"},
        {"acs": None, "name": "x", "description": "[POR DECIDIR: la moneda]"},
    ):
        assert _eval_pending_decisions(uc) is not None
        assert by_where(pending_marks(uc))[0][1] == "la moneda"


@pytest.mark.parametrize(
    "text",
    [
        "Cobra con `[POR DECIDIR: Stripe o Redsys]` al pagar.",
        "Cobra con «[POR DECIDIR: Stripe o Redsys]» al pagar.",
        "Una marca `[POR DECIDIR` se escribe con corchetes.",
        "No arranca con una marca `[POR DECIDIR` y el error muestra cada marca.",
    ],
)
def test_a_quoted_mark_is_not_a_mark(text):
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3

    undefined: una marca citada entre comillas invertidas o angulares no cuenta (en el criterio ni en el texto).
    """
    in_criterion = make_uc(acs=[("AC-01", text)])
    in_description = make_uc(description=text)
    in_name = make_uc(name=text)

    for uc in (in_criterion, in_description, in_name):
        assert pending_marks(uc) == []
        assert _eval_pending_decisions(uc) is None


def test_a_quoted_mark_does_not_hide_a_real_one_next_to_it():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: una marca citada y otra real en el mismo texto; solo la real cuenta.
    """
    uc = make_uc(
        description="La marca `[POR DECIDIR: de ejemplo]` existe. [POR DECIDIR: el IVA aplicable] sigue abierta."
    )

    reason = _eval_pending_decisions(uc)

    assert reason is not None
    assert "el IVA aplicable" in reason
    assert "de ejemplo" not in reason
    assert pending_marks(uc) == [{"where": "la descripción", "mark": "el IVA aplicable"}]


def test_the_criteria_of_uc_12305_itself_do_not_stop_it():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3

    undefined: los criterios de esta misma UC citan la marca entre comillas invertidas y no la detienen.
    """
    uc = make_uc(
        name="B2 · Lo que falta por decidir queda marcado y bloquea el arranque",
        description="Capacidad B2: marcar lo que falta por decidir.",
        acs=[
            ("AC-01", "Las plantillas de PRD y de plan incluyen la marca `[POR DECIDIR: …]` y una sección "
                      "«Pendiente de decidir» que la lista."),
            ("AC-02", "`start_uc` no arranca una UC cuyo texto o criterios contienen una marca `[POR DECIDIR`, "
                      "y el error muestra cada marca."),
        ],
    )

    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


@pytest.mark.parametrize(
    "text",
    ["Cobra con [POR DECIDIR]", "Cobra con [POR DECIDIR: ]", "Cobra con [POR DECIDIR:]", "Cobra con [POR DECIDIR    ]"],
)
def test_a_mark_without_detail_still_stops_and_says_so(text):
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: una marca sin detalle se muestra como «sin detalle».
    """
    uc = make_uc(acs=[("AC-01", text)])

    reason = _eval_pending_decisions(uc)

    assert reason is not None  # post1
    assert "sin detalle" in reason  # post2
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "sin detalle"}]  # post3


@pytest.mark.parametrize(
    "text",
    [
        "Cobra con [por decidir: Stripe o Redsys].",
        "Cobra con [Por Decidir: Stripe o Redsys].",
        "Cobra con [ POR DECIDIR : Stripe o Redsys ].",
        "Cobra con [POR DECIDIR Stripe o Redsys].",
    ],
)
def test_the_mark_ignores_case_and_spaces_inside_the_brackets(text):
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: mayúsculas y minúsculas, y espacios dentro de los corchetes, o los dos puntos ausentes.
    """
    uc = make_uc(acs=[("AC-01", text)])

    reason = _eval_pending_decisions(uc)

    assert reason is not None  # post1
    assert "Stripe o Redsys" in reason  # post2
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "Stripe o Redsys"}]  # post3


def test_a_mark_without_the_closing_bracket_still_counts():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: una marca a la que le falta el corchete de cierre; llega hasta el fin de la línea.
    """
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: la pasarela de pago\nsegunda línea sin marca")])

    reason = _eval_pending_decisions(uc)

    assert reason is not None  # post1
    assert "la pasarela de pago" in reason  # post2
    assert "segunda línea" not in reason  # no arrastra la línea siguiente
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "la pasarela de pago"}]  # post3


def test_an_unclosed_backtick_does_not_quote_the_mark():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post3

    undefined: una comilla invertida sin cerrar no entrecomilla nada.
    """
    uc = make_uc(acs=[("AC-01", "Cobra con `[POR DECIDIR: la pasarela de pago] y sigue.")])

    assert _eval_pending_decisions(uc) is not None
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "la pasarela de pago"}]


def test_a_backtick_pair_on_one_line_does_not_quote_a_mark_on_the_next_line():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post3

    undefined: las comillas solo protegen dentro de su línea.
    """
    uc = make_uc(acs=[("AC-01", "Usa `uno` y `dos`.\n[POR DECIDIR: la pasarela de pago]")])

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "la pasarela de pago"}]
    assert _eval_pending_decisions(uc) is not None


def test_a_mark_repeated_in_the_criterion_and_the_description_is_shown_once():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: import_spec copia los criterios a la descripción; la misma marca no se cuenta dos veces.
    """
    uc = make_uc(
        description="## Criterios\n- AC-01: Cobra con [POR DECIDIR: Stripe o Redsys] al pagar.",
        acs=[("AC-01", "Cobra con [POR DECIDIR: Stripe o Redsys] al pagar.")],
    )

    reason = _eval_pending_decisions(uc)

    assert reason is not None  # post1
    assert reason.count("Stripe o Redsys") == 1  # post2: una sola vez
    assert "Quedan 1 marca(s)" in reason
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "Stripe o Redsys"}]  # post3: la del criterio


def test_a_mark_repeated_in_the_name_and_the_description_is_shown_once_at_the_name():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: la misma marca en el nombre y en la descripción.
    """
    uc = make_uc(
        name="Cobro [POR DECIDIR: la moneda]",
        description="Resumen. [POR DECIDIR: la moneda]",
    )

    assert pending_marks(uc) == [{"where": "el nombre", "mark": "la moneda"}]
    reason = _eval_pending_decisions(uc)
    assert reason is not None
    assert reason.count("la moneda") == 1


def test_the_same_mark_twice_in_the_description_is_shown_once():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post3

    undefined: la misma marca dos veces en un mismo texto de la UC.
    """
    uc = make_uc(description="[POR DECIDIR: la moneda] y más abajo otra vez [POR DECIDIR: la moneda].")

    assert pending_marks(uc) == [{"where": "la descripción", "mark": "la moneda"}]


def test_the_same_mark_in_two_criteria_is_shown_in_each():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: la misma marca en dos criterios distintos cuenta una vez por criterio.
    """
    uc = make_uc(
        acs=[
            ("AC-01", "Cobra con [POR DECIDIR: la pasarela de pago]."),
            ("AC-02", "Reembolsa con [POR DECIDIR: la pasarela de pago]."),
        ]
    )

    reason = _eval_pending_decisions(uc)
    marks = pending_marks(uc)

    assert reason is not None  # post1
    assert "AC-01" in reason and "AC-02" in reason  # post2: cada criterio
    assert by_where(marks) == [("AC-01", "la pasarela de pago"), ("AC-02", "la pasarela de pago")]  # post3
    assert "Quedan 2 marca(s)" in reason


def test_the_mark_text_is_shown_with_its_whitespace_normalised():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: espacios, tabuladores y repeticiones dentro de lo que falta por decidir.
    """
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR:   la   pasarela\t de  pago  ].")])

    reason = _eval_pending_decisions(uc)

    assert reason is not None
    assert "«la pasarela de pago»" in reason  # post2
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "la pasarela de pago"}]  # post3


def test_a_criterion_without_id_is_named_with_a_question_mark():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: cómo se nombra el criterio de una marca cuando no trae id.
    """
    uc = {"name": "x", "description": "", "acs": [{"text": "Cobra con [POR DECIDIR: la pasarela de pago]."}]}

    reason = _eval_pending_decisions(uc)

    assert reason is not None  # post1
    assert "?: «la pasarela de pago»" in reason  # post2
    assert pending_marks(uc) == [{"where": "?", "mark": "la pasarela de pago"}]  # post3


def test_the_marks_are_listed_criteria_first_then_name_then_description():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: el orden en que se muestran las marcas.
    """
    uc = make_uc(
        name="Cobro [POR DECIDIR: n]",
        description="Resumen [POR DECIDIR: d]",
        acs=[("AC-01", "a [POR DECIDIR: c1]"), ("AC-02", "b [POR DECIDIR: c2]")],
    )

    marks = pending_marks(uc)
    reason = _eval_pending_decisions(uc)

    assert by_where(marks) == [("AC-01", "c1"), ("AC-02", "c2"), ("el nombre", "n"), ("la descripción", "d")]
    assert reason == (
        "Quedan 4 marca(s) «por decidir»: AC-01: «c1»; AC-02: «c2»; el nombre: «n»; la descripción: «d»."
    )


def test_there_is_no_cap_on_how_many_marks_are_shown():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    undefined: si hay un tope de marcas mostradas; con 60 criterios marcados salen las 60.
    """
    acs = [(f"AC-{i:02d}", f"Decide [POR DECIDIR: el punto {i}].") for i in range(1, 61)]
    uc = make_uc(acs=acs)

    marks = pending_marks(uc)
    reason = _eval_pending_decisions(uc)

    assert len(marks) == 60  # post3
    assert reason is not None  # post1
    assert "Quedan 60 marca(s)" in reason
    for i in (1, 30, 60):
        assert f"el punto {i}»" in reason  # post2
