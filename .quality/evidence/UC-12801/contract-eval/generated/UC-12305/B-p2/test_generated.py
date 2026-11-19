"""Pruebas de aceptación de UC-12305 (AC-02), generadas desde su contrato.

Contra `pending_marks`, `pending_reason` y `_eval_pending_decisions` de
`server/coordination/enforcement.py`. Sin base de datos, red ni disco.

Criterio probado: AC-02 «`start_uc` no arranca una UC cuyo texto o criterios contienen una marca
`[POR DECIDIR`, y el error muestra cada marca». AC-01 (plantillas), AC-03 (/implement sin triaje) y
AC-04 (modos warn/block y «anterior a la regla») no dependen de estas funciones y quedan fuera.
"""

from __future__ import annotations

from server.coordination.enforcement import (
    _eval_pending_decisions,
    pending_marks,
    pending_reason,
)


def make_uc(acs=None, name="", description="", **extra):
    """Una UC como la que lee el tablero: nombre, descripción y criterios con id y texto."""
    uc = {
        "uc_id": "UC-9000",
        "name": name,
        "description": description,
        "acs": [{"ac_id": ac_id, "text": text} for ac_id, text in (acs or [])],
    }
    uc.update(extra)
    return uc


# --------------------------------------------------------------------------------------
# AC-02: la marca se encuentra, la UC no arranca y el motivo muestra cada marca
# --------------------------------------------------------------------------------------


def test_mark_in_a_criterion_is_found_with_its_criterion_id():
    """
    contract: AC-02.pre1, AC-02.post1
    """
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor de pagos] al confirmar")])

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor de pagos"}]


def test_mark_in_the_name_is_found_as_el_nombre():
    """
    contract: AC-02.pre2, AC-02.post1
    """
    uc = make_uc(name="Cobrar con [POR DECIDIR: el proveedor de pagos]")

    assert pending_marks(uc) == [{"where": "el nombre", "mark": "el proveedor de pagos"}]


def test_mark_in_the_description_is_found_as_la_descripcion():
    """
    contract: AC-02.pre2, AC-02.post1
    """
    uc = make_uc(description="Sirve al cobro. [POR DECIDIR: el plazo de devolución]")

    assert pending_marks(uc) == [{"where": "la descripción", "mark": "el plazo de devolución"}]


def test_a_uc_with_a_mark_in_a_criterion_gets_a_stop_reason():
    """
    contract: AC-02.pre1, AC-02.post2
    """
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor de pagos]")])

    reason = _eval_pending_decisions(uc)

    assert reason is not None
    assert isinstance(reason, str)
    assert reason != ""


def test_a_uc_with_a_mark_in_its_text_gets_a_stop_reason():
    """
    contract: AC-02.pre2, AC-02.post2
    """
    by_name = make_uc(name="Cobrar [POR DECIDIR: la moneda]")
    by_description = make_uc(description="Cobrar. [POR DECIDIR: el IVA]")

    assert isinstance(_eval_pending_decisions(by_name), str)
    assert isinstance(_eval_pending_decisions(by_description), str)


def test_the_reason_shows_every_mark_of_the_uc():
    """
    contract: AC-02.pre1, AC-02.pre2, AC-02.pre3, AC-02.post1, AC-02.post2, AC-02.post3
    """
    uc = make_uc(
        acs=[
            ("AC-01", "Cobra con [POR DECIDIR: el proveedor de pagos]"),
            ("AC-02", "Este criterio no tiene ninguna marca"),
            ("AC-03", "Reintenta tras [POR DECIDIR: el plazo de reintento]"),
        ],
        name="Pagos [POR DECIDIR: la moneda]",
        description="Detalle del cobro [POR DECIDIR: el IVA]",
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el proveedor de pagos"},
        {"where": "AC-03", "mark": "el plazo de reintento"},
        {"where": "el nombre", "mark": "la moneda"},
        {"where": "la descripción", "mark": "el IVA"},
    ]
    reason = _eval_pending_decisions(uc)
    assert reason == (
        "Quedan 4 marca(s) «por decidir»: AC-01: «el proveedor de pagos»; "
        "AC-03: «el plazo de reintento»; el nombre: «la moneda»; la descripción: «el IVA»."
    )
    for mark in ("el proveedor de pagos", "el plazo de reintento", "la moneda", "el IVA"):
        assert f"«{mark}»" in reason


def test_the_reason_of_a_single_mark_counts_one():
    """
    contract: AC-02.pre1, AC-02.post2, AC-02.post3
    """
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor de pagos]")])

    assert _eval_pending_decisions(uc) == "Quedan 1 marca(s) «por decidir»: AC-01: «el proveedor de pagos»."


def test_the_reason_of_two_marks_in_the_same_criterion_lists_both():
    """
    contract: AC-02.pre1, AC-02.pre3, AC-02.post1, AC-02.post3
    """
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor] y [POR DECIDIR: la moneda]")])

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el proveedor"},
        {"where": "AC-01", "mark": "la moneda"},
    ]
    assert _eval_pending_decisions(uc) == (
        "Quedan 2 marca(s) «por decidir»: AC-01: «el proveedor»; AC-01: «la moneda»."
    )


def test_pending_reason_writes_the_sentence_from_the_marks():
    """
    contract: AC-02.pre1, AC-02.post3
    """
    marks = [
        {"where": "AC-01", "mark": "el proveedor de pagos"},
        {"where": "la descripción", "mark": "el plazo"},
    ]

    assert pending_reason(marks) == (
        "Quedan 2 marca(s) «por decidir»: AC-01: «el proveedor de pagos»; la descripción: «el plazo»."
    )
    assert pending_reason(marks[:1]) == "Quedan 1 marca(s) «por decidir»: AC-01: «el proveedor de pagos»."


def test_the_stop_reason_is_the_sentence_of_the_marks_found():
    """
    contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3
    """
    uc = make_uc(
        acs=[("AC-07", "Envía [POR DECIDIR: el canal]")],
        description="Texto. [POR DECIDIR: el remitente]",
    )

    assert _eval_pending_decisions(uc) == pending_reason(pending_marks(uc))


# --------------------------------------------------------------------------------------
# Lo que AC-02 no define y el código resuelve de un modo observable
# --------------------------------------------------------------------------------------


def test_undefined_a_uc_without_marks_gets_no_reason_and_the_same_uc_with_one_does():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: Qué devuelven las funciones con una UC sin ninguna marca.
    """
    clean = make_uc(acs=[("AC-01", "Cobra al confirmar el pedido")], name="Cobrar", description="Cobro simple")

    assert pending_marks(clean) == []
    assert _eval_pending_decisions(clean) is None
    assert pending_reason([]) is None

    marked = make_uc(
        acs=[("AC-01", "Cobra al confirmar el pedido [POR DECIDIR: el proveedor]")], name="Cobrar", description="Cobro simple"
    )
    assert pending_marks(marked) == [{"where": "AC-01", "mark": "el proveedor"}]
    assert _eval_pending_decisions(marked) is not None


def test_undefined_a_quoted_mark_is_not_a_mark():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: Si una marca citada entre comillas invertidas o angulares cuenta como marca.
    """
    quoted = make_uc(
        acs=[
            ("AC-01", "Las plantillas incluyen la marca `[POR DECIDIR: …]` y una sección"),
            ("AC-02", "El texto «[POR DECIDIR: el plazo]» se cita sin decidir nada"),
        ],
        description="Se escribe `[POR DECIDIR: x]` en la plantilla",
    )

    assert pending_marks(quoted) == []
    assert _eval_pending_decisions(quoted) is None

    # La misma marca escrita tal cual sí cuenta.
    bare = make_uc(acs=[("AC-01", "Las plantillas incluyen [POR DECIDIR: el plazo]")])
    assert pending_marks(bare) == [{"where": "AC-01", "mark": "el plazo"}]


def test_undefined_the_criteria_that_name_the_mark_do_not_stop_their_own_uc():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: Si una marca citada entre comillas invertidas o angulares (como la que nombra este mismo criterio) cuenta como marca.
    """
    uc = make_uc(
        acs=[
            (
                "AC-01",
                "Las plantillas de PRD y de plan incluyen la marca `[POR DECIDIR: …]` y una sección "
                "«Pendiente de decidir» que la lista.",
            ),
            (
                "AC-02",
                "`start_uc` no arranca una UC cuyo texto o criterios contienen una marca `[POR DECIDIR`, "
                "y el error muestra cada marca.",
            ),
        ],
        name="B2 · Lo que falta por decidir queda marcado y bloquea el arranque",
        description="Capacidad B2: marcar lo que falta por decidir con `[POR DECIDIR`.",
    )

    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


def test_undefined_the_mark_ignores_case_and_inner_spaces():
    """
    contract: AC-02.pre1, AC-02.post1
    undefined: Si la marca distingue mayúsculas de minúsculas o cuenta con espacios distintos dentro del corchete.
    """
    uc = make_uc(
        acs=[
            ("AC-01", "Uno [por decidir: a]"),
            ("AC-02", "Dos [ POR DECIDIR : b ]"),
            ("AC-03", "Tres [POR DECIDIR:c]"),
            ("AC-04", "Cuatro [Por Decidir: d]"),
        ]
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "a"},
        {"where": "AC-02", "mark": "b"},
        {"where": "AC-03", "mark": "c"},
        {"where": "AC-04", "mark": "d"},
    ]


def test_undefined_a_mark_without_detail_shows_sin_detalle():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post3
    undefined: Qué se muestra como lo que falta por decidir cuando la marca no trae detalle.
    """
    uc = make_uc(
        acs=[
            ("AC-01", "Uno [POR DECIDIR]"),
            ("AC-02", "Dos [POR DECIDIR: ]"),
            ("AC-03", "Tres [POR DECIDIR:]"),
        ]
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "sin detalle"},
        {"where": "AC-02", "mark": "sin detalle"},
        {"where": "AC-03", "mark": "sin detalle"},
    ]
    assert _eval_pending_decisions(uc) == (
        "Quedan 3 marca(s) «por decidir»: AC-01: «sin detalle»; AC-02: «sin detalle»; AC-03: «sin detalle»."
    )


def test_undefined_a_mark_without_closing_bracket_runs_to_the_end_of_the_line():
    """
    contract: AC-02.pre1, AC-02.post1
    undefined: Dónde acaba lo que falta por decidir si la marca no cierra el corchete o el detalle sigue en la línea siguiente.
    """
    unclosed = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el plazo de devolución")])
    assert pending_marks(unclosed) == [{"where": "AC-01", "mark": "el plazo de devolución"}]

    unclosed_then_more = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el plazo y algo más\nsegunda línea")])
    assert pending_marks(unclosed_then_more) == [{"where": "AC-01", "mark": "el plazo y algo más"}]

    # Un detalle que sigue en la línea siguiente se corta en el salto de línea.
    multiline = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el plazo\nde devolución]")])
    assert pending_marks(multiline) == [{"where": "AC-01", "mark": "el plazo"}]


def test_undefined_the_detail_collapses_repeated_spaces_and_drops_quoted_fragments():
    """
    contract: AC-02.pre1, AC-02.post1
    undefined: Qué pasa con los espacios repetidos dentro del detalle de la marca y con un fragmento citado dentro del detalle.
    """
    spaces = make_uc(acs=[("AC-01", "Cobra [POR DECIDIR:   el   plazo   de   devolución   ]")])
    assert pending_marks(spaces) == [{"where": "AC-01", "mark": "el plazo de devolución"}]

    quoted_inside = make_uc(acs=[("AC-01", "Guarda [POR DECIDIR: usar `redis` o no]")])
    assert pending_marks(quoted_inside) == [{"where": "AC-01", "mark": "usar o no"}]


def test_undefined_the_same_mark_in_two_criteria_counts_twice():
    """
    contract: AC-02.pre1, AC-02.pre3, AC-02.post1, AC-02.post3
    undefined: Cuántas veces se muestra una marca repetida: la misma en dos criterios.
    """
    uc = make_uc(
        acs=[
            ("AC-01", "Cobra con [POR DECIDIR: el proveedor]"),
            ("AC-02", "Reembolsa con [POR DECIDIR: el proveedor]"),
        ]
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el proveedor"},
        {"where": "AC-02", "mark": "el proveedor"},
    ]
    assert _eval_pending_decisions(uc) == (
        "Quedan 2 marca(s) «por decidir»: AC-01: «el proveedor»; AC-02: «el proveedor»."
    )


def test_undefined_the_same_mark_twice_in_one_criterion_counts_twice():
    """
    contract: AC-02.pre1, AC-02.post1
    undefined: Cuántas veces se muestra una marca repetida: la misma dos veces en un criterio.
    """
    uc = make_uc(acs=[("AC-01", "Cobra [POR DECIDIR: el proveedor] y reembolsa [POR DECIDIR: el proveedor]")])

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el proveedor"},
        {"where": "AC-01", "mark": "el proveedor"},
    ]


def test_undefined_a_text_mark_that_repeats_a_criterion_mark_is_not_counted_twice():
    """
    contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3
    undefined: Cuántas veces se muestra una marca repetida: la misma en un criterio y en el nombre o la descripción.
    """
    in_description = make_uc(
        acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")],
        description="- AC-01: Cobra con [POR DECIDIR: el proveedor]",
    )
    assert pending_marks(in_description) == [{"where": "AC-01", "mark": "el proveedor"}]

    in_name = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")], name="Cobrar [POR DECIDIR: el proveedor]")
    assert pending_marks(in_name) == [{"where": "AC-01", "mark": "el proveedor"}]

    # Una marca distinta de la descripción sí se suma.
    different = make_uc(
        acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")],
        description="Cobra [POR DECIDIR: el proveedor] y devuelve [POR DECIDIR: el plazo]",
    )
    assert pending_marks(different) == [
        {"where": "AC-01", "mark": "el proveedor"},
        {"where": "la descripción", "mark": "el plazo"},
    ]
    assert _eval_pending_decisions(different) == (
        "Quedan 2 marca(s) «por decidir»: AC-01: «el proveedor»; la descripción: «el plazo»."
    )


def test_undefined_the_same_mark_in_name_and_description_counts_once():
    """
    contract: AC-02.pre2, AC-02.post1
    undefined: Cuántas veces se muestra una marca repetida: la misma en el nombre y la descripción.
    """
    uc = make_uc(
        name="Cobrar [POR DECIDIR: la moneda]",
        description="Cobro en [POR DECIDIR: la moneda]",
    )

    assert pending_marks(uc) == [{"where": "el nombre", "mark": "la moneda"}]


def test_undefined_the_same_mark_twice_in_the_description_counts_once():
    """
    contract: AC-02.pre2, AC-02.post1
    undefined: Cuántas veces se muestra una marca repetida: la misma dos veces en una descripción.
    """
    uc = make_uc(description="Cobra [POR DECIDIR: la moneda] y devuelve en [POR DECIDIR: la moneda]")

    assert pending_marks(uc) == [{"where": "la descripción", "mark": "la moneda"}]


def test_undefined_marks_are_listed_criteria_first_then_name_then_description():
    """
    contract: AC-02.pre1, AC-02.pre2, AC-02.pre3, AC-02.post1, AC-02.post3
    undefined: En qué orden se listan las marcas en el motivo (criterios, nombre, descripción).
    """
    # El orden de las claves del diccionario no cambia el orden de las marcas.
    uc = {
        "description": "Descripción [POR DECIDIR: tres]",
        "name": "Nombre [POR DECIDIR: dos]",
        "acs": [
            {"ac_id": "AC-02", "text": "Segundo [POR DECIDIR: uno-b]"},
            {"ac_id": "AC-01", "text": "Primero [POR DECIDIR: uno-a]"},
        ],
    }

    assert [m["mark"] for m in pending_marks(uc)] == ["uno-b", "uno-a", "dos", "tres"]
    assert _eval_pending_decisions(uc) == (
        "Quedan 4 marca(s) «por decidir»: AC-02: «uno-b»; AC-01: «uno-a»; el nombre: «dos»; la descripción: «tres»."
    )


def test_undefined_degenerate_ucs_have_no_marks_and_a_mark_added_is_found():
    """
    contract: AC-02.pre2, AC-02.post1, AC-02.post2
    undefined: Qué devuelven las funciones con una UC vacía, sin criterios o con textos ausentes, vacíos o que no son cadenas.
    """
    degenerate = [
        {},
        {"acs": None, "name": None, "description": None},
        {"acs": [], "name": "", "description": ""},
        {"acs": [{"ac_id": "AC-01"}, {"ac_id": "AC-02", "text": None}, {"ac_id": "AC-03", "text": ""}]},
        {"name": 12345, "description": 678},
        {"acs": [{"ac_id": "AC-01", "text": 42}]},
    ]
    for uc in degenerate:
        assert pending_marks(uc) == [], uc
        assert _eval_pending_decisions(uc) is None, uc
        # Con una marca en la descripción, la misma UC se detiene.
        with_mark = {**uc, "description": "Falta [POR DECIDIR: algo]"}
        assert pending_marks(with_mark) == [{"where": "la descripción", "mark": "algo"}], with_mark
        assert isinstance(_eval_pending_decisions(with_mark), str)


def test_undefined_a_criterion_without_id_is_shown_as_question_mark():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post3
    undefined: Qué devuelven las funciones con un criterio sin id.
    """
    uc = {"name": "", "description": "", "acs": [{"text": "Cobra con [POR DECIDIR: el proveedor]"}]}

    assert pending_marks(uc) == [{"where": "?", "mark": "el proveedor"}]
    assert _eval_pending_decisions(uc) == "Quedan 1 marca(s) «por decidir»: ?: «el proveedor»."


def test_undefined_the_state_of_the_uc_does_not_change_its_marks():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: Si el estado de la UC influye en que se muestren sus marcas.
    """
    for state in ("backlog", "user_stories", "in_progress", "review", "done"):
        uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")], state=state)

        assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor"}], state
        assert _eval_pending_decisions(uc) == (
            "Quedan 1 marca(s) «por decidir»: AC-01: «el proveedor»."
        ), state


def test_undefined_por_decidir_without_the_bracket_is_not_a_mark():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: Si el texto «por decidir» sin los corchetes de la marca cuenta como marca.
    """
    plain = make_uc(
        acs=[
            ("AC-01", "Falta por decidir el proveedor de pagos"),
            ("AC-02", "POR DECIDIR: el plazo, sin corchete de apertura"),
        ],
        name="Lo que queda por decidir",
        description="Todo está por decidir todavía",
    )

    assert pending_marks(plain) == []
    assert _eval_pending_decisions(plain) is None

    bracketed = make_uc(acs=[("AC-01", "Falta [POR DECIDIR: el proveedor de pagos]")])
    assert pending_marks(bracketed) == [{"where": "AC-01", "mark": "el proveedor de pagos"}]


def test_undefined_an_unclosed_backtick_does_not_quote_the_mark():
    """
    contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: Qué pasa con una comilla invertida sin cerrar delante de la marca.
    """
    uc = make_uc(acs=[("AC-01", "Una comilla `suelta antes de [POR DECIDIR: el proveedor]")])

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor"}]
    assert isinstance(_eval_pending_decisions(uc), str)
