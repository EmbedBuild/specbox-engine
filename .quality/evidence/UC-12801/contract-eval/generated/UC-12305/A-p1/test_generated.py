"""Pruebas de aceptación de UC-12305 (B2: lo que falta por decidir queda marcado y bloquea el arranque).

Cubren la parte de los criterios que depende de ``pending_marks``, ``pending_reason`` y
``_eval_pending_decisions`` de ``server/coordination/enforcement.py``:

* AC-02: una UC cuyo texto (nombre, descripción) o criterios contienen una marca ``[POR DECIDIR``
  se detecta, y el motivo que se enseña en el error muestra cada marca.
* AC-04: solo el texto de las marcas pendientes que se enseña en la respuesta (en «warn» y en
  «block» es el mismo motivo); el modo de la medida y la regla «anterior a la regla» no dependen de
  estas funciones y quedan fuera.

AC-01 (plantillas) y AC-03 (/implement sin triaje) no dependen de estas funciones y no se prueban aquí.

Sin base de datos, sin red y sin disco.
"""

from __future__ import annotations

from server.coordination.enforcement import (
    _eval_pending_decisions,
    pending_marks,
    pending_reason,
)


def _uc(name="Cobros", description="", acs=None):
    return {"uc_id": "UC-9001", "name": name, "description": description, "acs": acs or []}


# ---------------------------------------------------------------------------------------------
# AC-02: la UC con una marca `[POR DECIDIR` se detecta, en cualquier parte de su texto o criterios
# ---------------------------------------------------------------------------------------------


def test_ac02_mark_in_a_criterion_is_found_with_its_criterion_id_and_what_is_pending():
    """AC-02: una marca en el texto de un criterio se detecta y dice el criterio y lo que falta decidir."""
    uc = _uc(acs=[{"ac_id": "AC-01", "text": "El cobro usa [POR DECIDIR: el proveedor de pagos] en cada pedido."}])

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor de pagos"}]


def test_ac02_mark_in_the_name_is_found():
    """AC-02: una marca en el nombre de la UC se detecta y dice «el nombre»."""
    uc = _uc(name="Cobros con [POR DECIDIR: el plazo de entrega]")

    assert pending_marks(uc) == [{"where": "el nombre", "mark": "el plazo de entrega"}]


def test_ac02_mark_in_the_description_is_found():
    """AC-02: una marca en la descripción de la UC se detecta y dice «la descripción»."""
    uc = _uc(description="Contexto del cobro. [POR DECIDIR: la moneda de cobro]")

    assert pending_marks(uc) == [{"where": "la descripción", "mark": "la moneda de cobro"}]


def test_ac02_marks_in_criteria_name_and_description_are_all_listed_in_that_order():
    """AC-02: el texto y los criterios se miran juntos; salen primero los criterios, luego nombre y descripción."""
    uc = _uc(
        name="Cobros [POR DECIDIR: el nombre comercial]",
        description="Notas [POR DECIDIR: la fecha de salida]",
        acs=[
            {"ac_id": "AC-01", "text": "Se cobra [POR DECIDIR: el banco]."},
            {"ac_id": "AC-02", "text": "Se factura [POR DECIDIR: el formato de factura]."},
        ],
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el banco"},
        {"where": "AC-02", "mark": "el formato de factura"},
        {"where": "el nombre", "mark": "el nombre comercial"},
        {"where": "la descripción", "mark": "la fecha de salida"},
    ]


def test_ac02_every_mark_of_the_same_text_is_listed():
    """AC-02: «el error muestra cada marca»: dos marcas en un mismo criterio dan dos entradas."""
    uc = _uc(acs=[{"ac_id": "AC-01", "text": "Paga con [POR DECIDIR: Stripe o Redsys] y envía a [POR DECIDIR: el almacén]."}])

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "Stripe o Redsys"},
        {"where": "AC-01", "mark": "el almacén"},
    ]


def test_ac02_mark_without_closing_bracket_still_counts():
    """AC-02: la marca `[POR DECIDIR` cuenta aunque el corchete no se cierre; lo que sigue es lo pendiente."""
    uc = _uc(acs=[{"ac_id": "AC-01", "text": "El plazo es [POR DECIDIR cuántos días"}])

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "cuántos días"}]


def test_ac02_bare_mark_without_detail_says_sin_detalle():
    """AC-02: una marca `[POR DECIDIR` sin nada detrás se detecta y dice «sin detalle»."""
    uc = _uc(acs=[{"ac_id": "AC-03", "text": "Falta [POR DECIDIR"}])

    assert pending_marks(uc) == [{"where": "AC-03", "mark": "sin detalle"}]


def test_ac02_mark_is_found_whatever_the_case_and_spacing():
    """AC-02: minúsculas, espacios dentro de los corchetes y espacios repetidos en el detalle no la esconden."""
    uc = _uc(
        acs=[
            {"ac_id": "AC-01", "text": "Color [por decidir: el color principal]"},
            {"ac_id": "AC-02", "text": "Tipo [ POR DECIDIR :   la   letra  ]"},
        ]
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el color principal"},
        {"where": "AC-02", "mark": "la letra"},
    ]


def test_ac02_a_mark_of_the_description_that_repeats_a_criterion_is_not_counted_twice():
    """AC-02: import_spec copia los criterios en la descripción; la marca repetida se muestra una sola vez."""
    uc = _uc(
        description="## Criterios\n- AC-01: Se cobra [POR DECIDIR: el banco].\n",
        acs=[{"ac_id": "AC-01", "text": "Se cobra [POR DECIDIR: el banco]."}],
    )

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el banco"}]


def test_ac02_a_different_mark_in_the_description_is_still_listed_next_to_the_criterion_one():
    """AC-02: la descripción solo se descuenta si repite la marca de un criterio; una distinta cuenta."""
    uc = _uc(
        description="- AC-01: Se cobra [POR DECIDIR: el banco]. Aparte: [POR DECIDIR: el IVA aplicable]",
        acs=[{"ac_id": "AC-01", "text": "Se cobra [POR DECIDIR: el banco]."}],
    )

    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el banco"},
        {"where": "la descripción", "mark": "el IVA aplicable"},
    ]


def test_ac02_uc_without_marks_has_no_pending_marks_and_no_reason():
    """AC-02: una UC sin marca no se detiene: no hay marcas y el motivo es None."""
    uc = _uc(
        name="Cobros",
        description="Cobra el pedido con tarjeta.",
        acs=[{"ac_id": "AC-01", "text": "El cobro con tarjeta muestra el recibo en menos de 2 s."}],
    )

    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


def test_ac02_uc_without_criteria_or_description_does_not_fail():
    """AC-02: una UC sin criterios ni descripción (None) no rompe la detección."""
    assert pending_marks({"uc_id": "UC-9002", "name": "Solo nombre", "description": None, "acs": None}) == []
    assert pending_marks({"uc_id": "UC-9002"}) == []
    assert pending_marks({"acs": [{"text": "Falta [POR DECIDIR: el dato]"}]}) == [{"where": "?", "mark": "el dato"}]


# ---------------------------------------------------------------------------------------------
# AC-02: lo citado no es una marca (UC-12305 nombra `[POR DECIDIR` en sus propios criterios)
# ---------------------------------------------------------------------------------------------


def test_ac02_the_criteria_of_uc_12305_themselves_do_not_block_it():
    """AC-02: los criterios de UC-12305 citan `[POR DECIDIR` entre comillas invertidas y no cuentan como marca."""
    uc = _uc(
        name="B2 · Lo que falta por decidir queda marcado y bloquea el arranque",
        acs=[
            {
                "ac_id": "AC-01",
                "text": "Las plantillas de PRD y de plan incluyen la marca `[POR DECIDIR: …]` y una sección "
                "«Pendiente de decidir» que la lista.",
            },
            {
                "ac_id": "AC-02",
                "text": "`start_uc` no arranca una UC cuyo texto o criterios contienen una marca `[POR DECIDIR`, "
                "y el error muestra cada marca.",
            },
        ],
    )

    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


def test_ac02_a_mark_between_guillemets_is_quoted_and_does_not_count():
    """AC-02: una marca entre « » es una cita, no una marca."""
    uc = _uc(acs=[{"ac_id": "AC-01", "text": "La plantilla trae la marca «[POR DECIDIR: ejemplo]» como muestra."}])

    assert pending_marks(uc) == []


def test_ac02_a_real_mark_next_to_a_quoted_one_is_the_only_one_listed():
    """AC-02: con una cita y una marca real en el mismo texto, solo la real se muestra."""
    uc = _uc(acs=[{"ac_id": "AC-01", "text": "Escribe `[POR DECIDIR: ejemplo]` y deja [POR DECIDIR: el banco]."}])

    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el banco"}]


# ---------------------------------------------------------------------------------------------
# AC-02: el error muestra cada marca (el motivo que lleva PENDING_DECISIONS)
# ---------------------------------------------------------------------------------------------


def test_ac02_reason_shows_each_mark_with_its_place_and_counts_them():
    """AC-02: el motivo del error dice cuántas marcas quedan y muestra cada una con su sitio."""
    marks = [
        {"where": "AC-01", "mark": "el proveedor de pagos"},
        {"where": "la descripción", "mark": "el plazo"},
    ]

    assert pending_reason(marks) == (
        "Quedan 2 marca(s) «por decidir»: AC-01: «el proveedor de pagos»; la descripción: «el plazo»."
    )


def test_ac02_reason_for_a_single_mark():
    """AC-02: con una sola marca el motivo la nombra y cuenta 1."""
    assert pending_reason([{"where": "el nombre", "mark": "sin detalle"}]) == (
        "Quedan 1 marca(s) «por decidir»: el nombre: «sin detalle»."
    )


def test_ac02_reason_without_marks_is_none():
    """AC-02: sin marcas no hay motivo y la UC puede arrancar."""
    assert pending_reason([]) is None


def test_ac02_and_ac04_evaluator_reason_names_every_mark_of_the_uc():
    """AC-02 y AC-04: el texto con las marcas pendientes (el que se muestra al arrancar o al bloquear) las nombra todas."""
    uc = _uc(
        name="Cobros [POR DECIDIR: el nombre comercial]",
        acs=[
            {"ac_id": "AC-01", "text": "Paga con [POR DECIDIR: Stripe o Redsys]."},
            {"ac_id": "AC-02", "text": "Cobra en euros."},
            {"ac_id": "AC-03", "text": "Factura en [POR DECIDIR: el formato]."},
        ],
    )

    reason = _eval_pending_decisions(uc)

    assert reason == (
        "Quedan 3 marca(s) «por decidir»: AC-01: «Stripe o Redsys»; AC-03: «el formato»; "
        "el nombre: «el nombre comercial»."
    )


def test_ac02_evaluator_reason_matches_the_reason_built_from_the_marks():
    """AC-02: el evaluador de la medida devuelve exactamente el motivo de las marcas de la UC."""
    uc = _uc(
        description="Notas [POR DECIDIR: la fecha de salida]",
        acs=[{"ac_id": "AC-01", "text": "Se cobra [POR DECIDIR: el banco]."}],
    )

    assert _eval_pending_decisions(uc) == pending_reason(pending_marks(uc))
    assert _eval_pending_decisions(uc) is not None
