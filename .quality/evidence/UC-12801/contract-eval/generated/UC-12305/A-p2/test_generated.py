"""UC-12305 · Lo que falta por decidir queda marcado y bloquea el arranque.

Pruebas de aceptación de los criterios que dependen de ``pending_marks``, ``pending_reason`` y
``_eval_pending_decisions`` (``server/coordination/enforcement.py``):

* AC-02: ``start_uc`` no arranca una UC cuyo texto o criterios contienen una marca ``[POR DECIDIR``,
  y el error muestra cada marca. El «no arranca» lo decide ``_eval_pending_decisions`` (un motivo no
  vacío detiene; ``None`` deja arrancar) y lo que el error muestra es ``pending_reason``.
* AC-04 (solo la parte de las marcas): con la medida en «warn» la respuesta muestra las marcas
  pendientes; son las mismas que ``pending_marks`` devuelve y el mismo motivo que en «block».

Fuera de estas pruebas (no dependen de esas funciones): AC-01 (plantillas), AC-03 (triaje de
/implement) y, de AC-04, el efecto de los modos «warn» y «block» y la UC «anterior a la regla».

Sin base de datos, red ni disco: las funciones son puras y reciben la UC como diccionario.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

# Que la prueba se pueda lanzar desde cualquier carpeta: sube hasta la raíz del repositorio.
for _parent in Path(__file__).resolve().parents:
    if (_parent / "server" / "coordination" / "enforcement.py").exists():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break

from server.coordination.enforcement import (  # noqa: E402
    _eval_pending_decisions,
    pending_marks,
    pending_reason,
)


def make_uc(name: str = "Cobrar al cliente", description: str = "", acs: list[tuple[str, str]] | None = None) -> dict:
    """Una UC como la que lee la medida: nombre, descripción y criterios con ``ac_id`` y ``text``."""
    return {
        "uc_id": "UC-9000",
        "name": name,
        "description": description,
        "acs": [{"ac_id": ac_id, "text": text} for ac_id, text in (acs or [])],
    }


# --------------------------------------------------------------------------------------
# AC-02 · una UC con una marca en su texto o en sus criterios no arranca
# --------------------------------------------------------------------------------------


def test_ac02_uc_without_marks_has_no_marks_and_starts():
    """AC-02: una UC sin ninguna marca no se detiene: sin marcas y sin motivo."""
    uc = make_uc(
        name="Cobrar al cliente",
        description="El cliente paga con tarjeta.",
        acs=[("AC-01", "El cobro muestra el importe en euros."), ("AC-02", "El recibo llega por correo.")],
    )
    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


def test_ac02_mark_in_a_criterion_stops_the_uc_and_says_where():
    """AC-02: una marca en un criterio detiene la UC y se atribuye a ese criterio (AC-02)."""
    uc = make_uc(acs=[("AC-01", "Cobra con tarjeta."), ("AC-02", "Cobra con [POR DECIDIR: Stripe o Redsys] siempre.")])
    assert pending_marks(uc) == [{"where": "AC-02", "mark": "Stripe o Redsys"}]
    assert _eval_pending_decisions(uc) is not None


def test_ac02_mark_in_the_name_stops_the_uc():
    """AC-02: una marca en el nombre de la UC (su texto) detiene la UC."""
    uc = make_uc(name="Cobrar [POR DECIDIR: la moneda] al cliente", acs=[("AC-01", "Cobra con tarjeta.")])
    assert pending_marks(uc) == [{"where": "el nombre", "mark": "la moneda"}]
    assert _eval_pending_decisions(uc) is not None


def test_ac02_mark_in_the_description_stops_the_uc():
    """AC-02: una marca en la descripción de la UC (su texto) detiene la UC."""
    uc = make_uc(description="Cobro con tarjeta. [POR DECIDIR: el proveedor de pagos]", acs=[("AC-01", "Cobra.")])
    assert pending_marks(uc) == [{"where": "la descripción", "mark": "el proveedor de pagos"}]
    assert _eval_pending_decisions(uc) is not None


def test_ac02_mark_without_closing_bracket_still_counts():
    """AC-02: el criterio habla de una marca `[POR DECIDIR` (el prefijo basta; no exige el cierre)."""
    uc = make_uc(acs=[("AC-01", "El pago se hace con [POR DECIDIR el proveedor")])
    marks = pending_marks(uc)
    assert len(marks) == 1
    assert marks[0]["where"] == "AC-01"
    assert _eval_pending_decisions(uc) is not None


def test_ac02_mark_is_found_with_spacing_before_the_colon():
    """AC-02: `[POR DECIDIR : x]`, con espacios antes de los dos puntos, también es una marca."""
    uc = make_uc(acs=[("AC-01", "Se cobra [POR DECIDIR : la comisión] al vender.")])
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "la comisión"}]


def test_ac02_mark_without_detail_is_still_a_mark_and_the_error_shows_it():
    """AC-02: `[POR DECIDIR]` a secas detiene la UC y el error lo muestra como «sin detalle»."""
    uc = make_uc(acs=[("AC-01", "Se cobra [POR DECIDIR] al vender.")])
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "sin detalle"}]
    assert pending_reason(pending_marks(uc)) == "Quedan 1 marca(s) «por decidir»: AC-01: «sin detalle»."


def test_ac02_error_shows_each_mark_with_its_place_and_the_count():
    """AC-02: el error muestra cada marca: tres marcas en tres sitios, las tres con su sitio y el total."""
    uc = make_uc(
        name="Pagos [POR DECIDIR: el proveedor de pagos]",
        description="Notas [POR DECIDIR: la moneda]",
        acs=[("AC-01", "Cobra con [POR DECIDIR: Stripe o Redsys] siempre."), ("AC-02", "Sin marca.")],
    )
    reason = _eval_pending_decisions(uc)
    assert reason is not None
    assert reason.startswith("Quedan 3 marca(s)")
    for text in ("AC-01", "«Stripe o Redsys»", "el nombre", "«el proveedor de pagos»", "la descripción", "«la moneda»"):
        assert text in reason, f"falta {text!r} en {reason!r}"
    # AC-02 no tiene marca: no aparece en el error.
    assert "AC-02" not in reason


def test_ac02_error_lists_marks_in_order_criteria_then_name_then_description():
    """AC-02: el error lista las marcas en el orden criterios, nombre y descripción."""
    uc = make_uc(
        name="Pagos [POR DECIDIR: n]",
        description="[POR DECIDIR: d]",
        acs=[("AC-01", "[POR DECIDIR: a]"), ("AC-03", "[POR DECIDIR: c]")],
    )
    assert [(m["where"], m["mark"]) for m in pending_marks(uc)] == [
        ("AC-01", "a"),
        ("AC-03", "c"),
        ("el nombre", "n"),
        ("la descripción", "d"),
    ]
    assert _eval_pending_decisions(uc) == (
        "Quedan 4 marca(s) «por decidir»: AC-01: «a»; AC-03: «c»; el nombre: «n»; la descripción: «d»."
    )


def test_ac02_several_marks_in_one_criterion_are_all_listed():
    """AC-02: un criterio con dos marcas las muestra las dos, no solo la primera."""
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor] y envía a [POR DECIDIR: la empresa de reparto].")])
    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el proveedor"},
        {"where": "AC-01", "mark": "la empresa de reparto"},
    ]
    reason = _eval_pending_decisions(uc)
    assert reason is not None and reason.startswith("Quedan 2 marca(s)")
    assert "«el proveedor»" in reason and "«la empresa de reparto»" in reason


def test_ac02_same_mark_text_in_two_criteria_is_listed_twice():
    """AC-02: dos criterios con la misma marca la muestran los dos, cada uno con su id."""
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: x]."), ("AC-02", "Reembolsa con [POR DECIDIR: x].")])
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "x"}, {"where": "AC-02", "mark": "x"}]
    reason = _eval_pending_decisions(uc)
    assert reason is not None and "AC-01: «x»" in reason and "AC-02: «x»" in reason


def test_ac02_mark_detail_is_shown_with_its_whitespace_tidied():
    """AC-02: el error muestra lo que falta decidir con los espacios y saltos normalizados."""
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR:   el   proveedor   de pagos  ].")])
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor de pagos"}]


def test_ac02_description_that_repeats_a_criterion_mark_is_not_counted_twice():
    """AC-02: import_spec copia los criterios a la descripción; esa marca repetida cuenta una vez, en el criterio."""
    uc = make_uc(
        description="## Criterios\n- AC-01: Cobra con [POR DECIDIR: el proveedor]\n",
        acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")],
    )
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor"}]
    assert _eval_pending_decisions(uc) == "Quedan 1 marca(s) «por decidir»: AC-01: «el proveedor»."


def test_ac02_name_that_repeats_a_criterion_mark_is_not_counted_twice():
    """AC-02: una marca del nombre que repite la de un criterio cuenta una vez."""
    uc = make_uc(name="Pagos [POR DECIDIR: el proveedor]", acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")])
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "el proveedor"}]


def test_ac02_description_mark_different_from_the_criteria_is_still_counted():
    """AC-02: la deduplicación solo quita repeticiones; una marca distinta en la descripción sigue contando."""
    uc = make_uc(
        description="- AC-01: Cobra con [POR DECIDIR: el proveedor]\nOtra duda: [POR DECIDIR: el plazo de reembolso]",
        acs=[("AC-01", "Cobra con [POR DECIDIR: el proveedor]")],
    )
    assert pending_marks(uc) == [
        {"where": "AC-01", "mark": "el proveedor"},
        {"where": "la descripción", "mark": "el plazo de reembolso"},
    ]


@pytest.mark.parametrize(
    "text",
    [
        "La UC admite una marca `[POR DECIDIR: x]` en su texto.",
        "La UC admite una marca «[POR DECIDIR: x]» en su texto.",
        "Contienen una marca `[POR DECIDIR`, y el error la muestra.",
    ],
)
def test_ac02_a_mark_quoted_in_backticks_or_guillemets_is_not_a_mark(text):
    """AC-02: lo citado entre comillas invertidas o angulares nombra la marca, no la pone: la UC arranca."""
    for uc in (
        make_uc(acs=[("AC-01", text)]),
        make_uc(name=text),
        make_uc(description=text),
    ):
        assert pending_marks(uc) == []
        assert _eval_pending_decisions(uc) is None


def test_ac02_quoted_mark_next_to_a_real_one_only_counts_the_real_one():
    """AC-02: en un mismo texto, la marca citada no cuenta y la real sí."""
    uc = make_uc(acs=[("AC-01", "La marca `[POR DECIDIR: citada]` no cuenta, pero [POR DECIDIR: la real] sí.")])
    assert pending_marks(uc) == [{"where": "AC-01", "mark": "la real"}]
    reason = _eval_pending_decisions(uc)
    assert reason is not None and "«la real»" in reason and "citada" not in reason


def test_ac02_uc_12305_does_not_stop_itself():
    """AC-02: la propia UC-12305 nombra la marca entre comillas invertidas en sus criterios y arranca."""
    uc = {
        "uc_id": "UC-12305",
        "name": "B2 · Lo que falta por decidir queda marcado y bloquea el arranque",
        "description": (
            "# UC-12305: B2 · Lo que falta por decidir queda marcado y bloquea el arranque\n\n"
            "## Criterios de Aceptacion\n"
            "- AC-01: Las plantillas de PRD y de plan incluyen la marca `[POR DECIDIR: …]` y una sección "
            "«Pendiente de decidir» que la lista.\n"
            "- AC-02: `start_uc` no arranca una UC cuyo texto o criterios contienen una marca `[POR DECIDIR`, "
            "y el error muestra cada marca.\n"
        ),
        "acs": [
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
            {
                "ac_id": "AC-03",
                "text": "Sin la herramienta de triaje disponible, /implement se detiene antes de crear la rama "
                "y muestra el motivo, en lugar de seguir sin el triaje.",
            },
            {
                "ac_id": "AC-04",
                "text": "Con la medida en «warn», `start_uc` arranca la UC y su respuesta muestra las marcas "
                "pendientes; en «block», no arranca; una UC «anterior a la regla» arranca en cualquier modo.",
            },
        ],
    }
    assert pending_marks(uc) == []
    assert _eval_pending_decisions(uc) is None


def test_ac02_uc_without_criteria_is_judged_by_its_text_alone():
    """AC-02: una UC sin criterios con una marca en el nombre se detiene; sin marca, no."""
    assert pending_marks({"uc_id": "UC-1", "name": "Limpia", "description": ""}) == []
    assert _eval_pending_decisions({"uc_id": "UC-1", "name": "Limpia", "description": ""}) is None
    marked = {"uc_id": "UC-1", "name": "Con [POR DECIDIR: el alcance]", "description": "", "acs": []}
    assert pending_marks(marked) == [{"where": "el nombre", "mark": "el alcance"}]
    assert _eval_pending_decisions(marked) is not None


def test_ac02_pending_reason_of_no_marks_is_none_and_of_marks_names_each_one():
    """AC-02: sin marcas no hay motivo (la UC arranca); con marcas, el motivo las nombra todas."""
    assert pending_reason([]) is None
    marks = [{"where": "AC-01", "mark": "a"}, {"where": "el nombre", "mark": "b"}]
    reason = pending_reason(marks)
    assert reason == "Quedan 2 marca(s) «por decidir»: AC-01: «a»; el nombre: «b»."


def test_ac02_evaluating_a_uc_does_not_change_it():
    """AC-02: la medida solo lee: la UC queda igual tras mirarla."""
    uc = make_uc(
        name="Pagos [POR DECIDIR: n]",
        description="[POR DECIDIR: d]",
        acs=[("AC-01", "[POR DECIDIR: a]")],
    )
    before = copy.deepcopy(uc)
    pending_marks(uc)
    _eval_pending_decisions(uc)
    assert uc == before


# --------------------------------------------------------------------------------------
# AC-04 · (parte de las marcas) la respuesta muestra las marcas pendientes
# --------------------------------------------------------------------------------------


def test_ac04_response_shows_the_pending_marks_as_where_and_mark_entries():
    """AC-04: la respuesta de start_uc lleva las marcas como entradas {where, mark}, y se pueden serializar."""
    uc = make_uc(
        name="Pagos [POR DECIDIR: el proveedor de pagos]",
        acs=[("AC-01", "Cobra con [POR DECIDIR: Stripe o Redsys]."), ("AC-02", "Sin marca.")],
    )
    marks = pending_marks(uc)
    assert marks == [
        {"where": "AC-01", "mark": "Stripe o Redsys"},
        {"where": "el nombre", "mark": "el proveedor de pagos"},
    ]
    assert all(set(m) == {"where", "mark"} for m in marks)
    assert json.loads(json.dumps(marks)) == marks


def test_ac04_the_message_shown_names_every_pending_mark_and_matches_the_evaluation():
    """AC-04: el motivo de la respuesta nombra cada marca pendiente y es el mismo que da la medida."""
    uc = make_uc(
        description="Duda: [POR DECIDIR: la moneda]",
        acs=[("AC-01", "Cobra con [POR DECIDIR: Stripe o Redsys]."), ("AC-02", "Reembolsa en [POR DECIDIR: 14 o 30 días].")],
    )
    marks = pending_marks(uc)
    reason = pending_reason(marks)
    assert reason is not None
    assert reason == _eval_pending_decisions(uc)
    assert reason.startswith("Quedan 3 marca(s)")
    for mark in marks:
        assert mark["where"] in reason
        assert f"«{mark['mark']}»" in reason


def test_ac04_uc_without_marks_shows_nothing_pending():
    """AC-04: una UC sin marcas no muestra marcas pendientes ni motivo, sea cual sea la medida."""
    uc = make_uc(acs=[("AC-01", "Cobra con tarjeta."), ("AC-02", "Envía el recibo.")])
    assert pending_marks(uc) == []
    assert pending_reason(pending_marks(uc)) is None
    assert _eval_pending_decisions(uc) is None


def test_ac04_marks_and_message_do_not_depend_on_a_mode():
    """AC-04: marcas y motivo son los mismos en «warn» y en «block»: la medida no recibe ningún modo."""
    uc = make_uc(acs=[("AC-01", "Cobra con [POR DECIDIR: Stripe o Redsys].")])
    first = (pending_marks(uc), _eval_pending_decisions(uc))
    second = (pending_marks(uc), _eval_pending_decisions(uc))
    assert first == second
    assert first[1] == "Quedan 1 marca(s) «por decidir»: AC-01: «Stripe o Redsys»."
