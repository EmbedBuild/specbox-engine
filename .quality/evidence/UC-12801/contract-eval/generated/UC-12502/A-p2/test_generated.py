"""Pruebas de aceptación de UC-12502 (B8 · una persona aprueba los criterios antes de implementar)
contra las funciones públicas de ``server/approval.py``.

Cada prueba dice en su nombre o en su docstring el criterio que demuestra (AC-NN). Los criterios que
dependen de otras piezas (start_uc, find_next_uc, /prd, el almacenamiento del tablero) solo se
cubren en lo que el módulo decide: la huella, el estado de la aprobación y el predicado «cuenta como
aprobada».
"""

from __future__ import annotations

import json

import pytest

from server.approval import (
    APPROVED_STATES,
    MIGRATION_LABEL,
    approval_state,
    criteria_fingerprint,
    criteria_snapshot,
    is_approved,
    not_approved_reason,
)

CRITERIA = [
    {"id": "AC-01", "text": "El tablero registra la aprobación con quién y cuándo."},
    {"id": "AC-02", "text": "start_uc no arranca una UC sin criterios aprobados."},
    {"id": "AC-03", "text": "Cambiar un criterio aprobado deja la UC sin aprobar."},
]

WHO = "jesusperezdeveloper"
WHEN = "2026-11-19T10:30:00+00:00"


def _approval(acs, **extra):
    """Lo que una aprobación guarda: la huella de los criterios vigentes con quién y cuándo."""
    record = {"fingerprint": criteria_fingerprint(acs), "by": WHO, "at": WHEN}
    record.update(extra)
    return record


# --------------------------------------------------------------------------- AC-01


def test_ac01_la_aprobacion_guarda_quien_y_cuando_y_la_huella_de_los_criterios_vigentes():
    """AC-01: con la huella vigente, el estado es «approved» y lleva quién y cuándo."""
    latest = _approval(CRITERIA, session_id="sesion-7", source="mcp")

    state = approval_state(latest, criteria_fingerprint(CRITERIA))

    assert state == {
        "state": "approved",
        "by": WHO,
        "at": WHEN,
        "session_id": "sesion-7",
        "source": "mcp",
    }


def test_ac01_la_huella_es_estable_de_32_hexadecimales_y_ordena_por_numero_de_id():
    """AC-01: la huella que se registra es determinista y no depende del orden de entrada."""
    desordenados = [
        {"id": "AC-10", "text": "diez"},
        {"id": "AC-02", "text": "dos"},
        {"id": "AC-01", "text": "uno"},
    ]
    fp = criteria_fingerprint(desordenados)

    assert len(fp) == 32
    assert int(fp, 16) >= 0
    assert fp == criteria_fingerprint(list(reversed(desordenados)))
    assert [p["id"] for p in criteria_snapshot(desordenados)] == ["AC-01", "AC-02", "AC-10"]


def test_ac01_sin_quien_ni_cuando_en_el_registro_el_estado_no_los_inventa():
    """AC-01: solo salen quién y cuándo si la aprobación los guardó."""
    state = approval_state({"fingerprint": criteria_fingerprint(CRITERIA)}, criteria_fingerprint(CRITERIA))

    assert state == {"state": "approved"}
    assert "by" not in state and "at" not in state


# --------------------------------------------------------------------------- AC-02


@pytest.mark.parametrize(
    "latest",
    [None, {}, {"fingerprint": ""}],
    ids=["sin_registro", "registro_vacio", "huella_vacia"],
)
def test_ac02_una_uc_sin_aprobacion_no_cuenta_como_aprobada_y_start_uc_la_pararia(latest):
    """AC-02 (la parte del módulo): sin criterios aprobados el predicado de la puerta es falso.

    El error ``AC_NOT_APPROVED`` lo devuelve ``start_uc`` y queda fuera de este módulo.
    """
    state = approval_state(latest, criteria_fingerprint(CRITERIA))

    assert state == {"state": "none"}
    assert is_approved(state) is False
    assert not_approved_reason("UC-12502", state) == "Nadie ha aprobado todavía los criterios de UC-12502."


def test_ac02_el_predicado_de_la_puerta_solo_deja_pasar_aprobada_y_migracion():
    """AC-02: solo «approved» y «migration» cuentan como aprobadas."""
    assert APPROVED_STATES == frozenset({"approved", "migration"})
    assert is_approved({"state": "approved"}) is True
    assert is_approved({"state": "migration"}) is True
    assert is_approved({"state": "stale"}) is False
    assert is_approved({"state": "none"}) is False
    assert is_approved(None) is False
    assert is_approved({}) is False


# --------------------------------------------------------------------------- AC-03


def _changed_text(acs):
    return [dict(acs[0], text=acs[0]["text"] + " Y además con la fecha."), *acs[1:]]


def _added(acs):
    return [*acs, {"id": "AC-04", "text": "Un criterio nuevo y verificable."}]


def _removed(acs):
    return [acs[0], acs[2]]


@pytest.mark.parametrize(
    "mutate",
    [_changed_text, _added, _removed],
    ids=["cambia_el_texto", "se_anade_uno", "se_retira_uno"],
)
def test_ac03_cambiar_anadir_o_retirar_un_criterio_deja_la_uc_sin_aprobar(mutate):
    """AC-03: tras cambiar un texto, añadir un criterio o retirarlo, la UC queda «stale»."""
    aprobada = _approval(CRITERIA)
    assert approval_state(aprobada, criteria_fingerprint(CRITERIA))["state"] == "approved"

    nuevos = mutate(CRITERIA)
    state = approval_state(aprobada, criteria_fingerprint(nuevos))

    assert criteria_fingerprint(nuevos) != criteria_fingerprint(CRITERIA)
    assert state["state"] == "stale"
    assert state["reason"] == "Los criterios cambiaron después de la última aprobación."
    assert state["previous_by"] == WHO
    assert state["previous_at"] == WHEN
    assert is_approved(state) is False
    assert not_approved_reason("UC-12502", state) == (
        "Los criterios de UC-12502 cambiaron después de su última aprobación."
    )


def test_ac03_sigue_sin_aprobar_hasta_una_nueva_aprobacion():
    """AC-03: la UC vuelve a «approved» solo cuando alguien aprueba los criterios nuevos."""
    aprobada = _approval(CRITERIA)
    nuevos = _added(CRITERIA)
    fp_nuevos = criteria_fingerprint(nuevos)

    assert approval_state(aprobada, fp_nuevos)["state"] == "stale"

    reaprobada = {"fingerprint": fp_nuevos, "by": "ana", "at": "2026-11-20T09:00:00+00:00"}
    state = approval_state(reaprobada, fp_nuevos)

    assert state == {"state": "approved", "by": "ana", "at": "2026-11-20T09:00:00+00:00"}
    assert is_approved(state) is True


def test_ac03_cambiar_un_solo_caracter_del_texto_cambia_la_huella():
    """AC-03: el cambio mínimo de un texto aprobado ya invalida la aprobación."""
    a = [{"id": "AC-01", "text": "Muestra 3 filas."}]
    b = [{"id": "AC-01", "text": "Muestra 4 filas."}]

    assert approval_state(_approval(a), criteria_fingerprint(b))["state"] == "stale"


def test_ac03_los_espacios_repetidos_no_cuentan_como_cambio_de_texto():
    """AC-03 (frontera): reformatear espacios no es cambiar el criterio y la aprobación se mantiene."""
    compacto = [{"id": "AC-01", "text": "Muestra tres filas."}]
    con_espacios = [{"id": "AC-01", "text": "  Muestra   tres \n filas.  "}]

    assert criteria_fingerprint(compacto) == criteria_fingerprint(con_espacios)
    assert approval_state(_approval(compacto), criteria_fingerprint(con_espacios))["state"] == "approved"


def test_ac03_cambiar_como_se_verifica_o_marcar_un_criterio_no_invalida_la_aprobacion():
    """AC-03 (frontera): solo cuentan id y texto; verification, done y evidencia no cambian la huella."""
    base = [{"id": "AC-01", "text": "Muestra tres filas.", "verification": "review", "done": False}]
    otro = [{"id": "AC-01", "text": "Muestra tres filas.", "verification": "automated_test", "done": True,
             "evidence": [{"passed": True}]}]

    assert criteria_fingerprint(base) == criteria_fingerprint(otro)
    assert approval_state(_approval(base), criteria_fingerprint(otro))["state"] == "approved"


# --------------------------------------------------------------------------- AC-04


@pytest.mark.parametrize(
    ("state", "propuesta"),
    [
        ({"state": "approved"}, True),
        ({"state": "migration"}, True),
        ({"state": "stale"}, False),
        ({"state": "none"}, False),
    ],
    ids=["aprobada", "por_migracion", "stale", "sin_aprobar"],
)
def test_ac04_el_predicado_que_usa_find_next_uc_separa_aprobadas_de_las_demas(state, propuesta):
    """AC-04 (la parte del módulo): ``is_approved`` es lo que decide si una UC se propone.

    El filtro en «block» y el orden en «warn» los hace ``find_next_uc`` y quedan fuera.
    """
    assert is_approved(state) is propuesta


def test_ac04_en_warn_las_aprobadas_van_primero_al_ordenar_por_el_predicado():
    """AC-04 (la parte del módulo): ordenar por ``is_approved`` pone las aprobadas delante, sin perder las demás."""
    fp = criteria_fingerprint(CRITERIA)
    estados = {
        "UC-1": approval_state(None, fp),
        "UC-2": approval_state(_approval(CRITERIA), fp),
        "UC-3": approval_state(_approval(_added(CRITERIA)), fp),
        "UC-4": approval_state(None, fp, predates=True),
    }

    orden = sorted(estados, key=lambda uc: not is_approved(estados[uc]))

    assert orden[:2] == ["UC-2", "UC-4"]
    assert sorted(orden[2:]) == ["UC-1", "UC-3"]


# --------------------------------------------------------------------------- AC-06


def test_ac06_una_uc_anterior_a_la_regla_cuenta_como_aprobada_por_migracion():
    """AC-06: una UC anterior a la regla sin aprobación cuenta como aprobada, con la marca."""
    state = approval_state(None, criteria_fingerprint(CRITERIA), predates=True)

    assert MIGRATION_LABEL == "aprobada por migración"
    assert state == {"state": "migration", "source": "migration", "label": "aprobada por migración"}
    assert is_approved(state) is True


def test_ac06_una_uc_anterior_con_criterios_cambiados_tambien_cuenta_como_migracion():
    """AC-06: la anterior a la regla no queda «stale» aunque tuviera una aprobación vieja."""
    state = approval_state(_approval(CRITERIA), criteria_fingerprint(_added(CRITERIA)), predates=True)

    assert state["state"] == "migration"
    assert state["label"] == "aprobada por migración"
    assert is_approved(state) is True


def test_ac06_si_una_persona_ya_aprobo_la_uc_anterior_cuenta_como_aprobada_no_por_migracion():
    """AC-06 (frontera): la aprobación real de los criterios vigentes gana a la marca de migración."""
    state = approval_state(_approval(CRITERIA), criteria_fingerprint(CRITERIA), predates=True)

    assert state["state"] == "approved"
    assert state["by"] == WHO
    assert "label" not in state


def test_ac06_una_uc_posterior_a_la_regla_sin_aprobar_no_cuenta_y_block_no_la_arrancaria():
    """AC-06 (la parte del módulo): sin ser anterior a la regla, sin aprobar no pasa el predicado."""
    state = approval_state(None, criteria_fingerprint(CRITERIA), predates=False)

    assert state == {"state": "none"}
    assert is_approved(state) is False


# --------------------------------------------------------------------------- AC-07


class _Criterio:
    """Un criterio como lo entrega un backend con objetos (atributos id y text)."""

    def __init__(self, id, text):
        self.id = id
        self.text = text


def test_ac07_la_misma_regla_para_cualquier_backend_la_huella_no_depende_de_la_forma_del_criterio():
    """AC-07: criterios como dict con ``id``, dict con ``ac_id`` u objeto dan la misma huella y el mismo estado."""
    como_dict = [{"id": c["id"], "text": c["text"]} for c in CRITERIA]
    como_ac_id = [{"ac_id": c["id"], "text": c["text"]} for c in CRITERIA]
    como_objeto = [_Criterio(c["id"], c["text"]) for c in CRITERIA]

    fp = criteria_fingerprint(como_dict)
    assert criteria_fingerprint(como_ac_id) == fp
    assert criteria_fingerprint(como_objeto) == fp

    aprobada = _approval(como_dict)
    estados = [approval_state(aprobada, criteria_fingerprint(acs)) for acs in (como_dict, como_ac_id, como_objeto)]
    assert estados[0] == estados[1] == estados[2]
    assert estados[0]["state"] == "approved"


def test_ac07_la_aprobacion_guardada_en_ficheros_del_tablero_se_lee_con_quien_y_cuando(tmp_path):
    """AC-07: una aprobación escrita como JSON en el fichero del tablero se lee con quién y cuándo.

    El guardado en ``items.json`` lo hace el backend FreeForm; aquí solo se comprueba que el
    registro, tras pasar por un fichero, produce el estado esperado con la regla del módulo.
    """
    tablero = tmp_path / "items.json"
    tablero.write_text(json.dumps({"UC-12502": {"criteria_approval": _approval(CRITERIA)}}), encoding="utf-8")

    guardada = json.loads(tablero.read_text(encoding="utf-8"))["UC-12502"]["criteria_approval"]
    state = approval_state(guardada, criteria_fingerprint(CRITERIA))

    assert state == {"state": "approved", "by": WHO, "at": WHEN}


def test_ac07_en_ficheros_tambien_se_invalida_al_cambiar_un_criterio_sin_importar_quien_lo_escribe(tmp_path):
    """AC-07: la regla de «stale» es la misma con el registro leído de un fichero, lo escriba quien lo escriba."""
    tablero = tmp_path / "items.json"
    tablero.write_text(json.dumps({"criteria_approval": _approval(CRITERIA)}), encoding="utf-8")
    guardada = json.loads(tablero.read_text(encoding="utf-8"))["criteria_approval"]

    editados = [dict(CRITERIA[0], text="Reescrito a mano en el fichero."), *CRITERIA[1:]]
    state = approval_state(guardada, criteria_fingerprint(editados))

    assert state["state"] == "stale"
    assert state["previous_by"] == WHO
    assert state["previous_at"] == WHEN
