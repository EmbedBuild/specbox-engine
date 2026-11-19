"""Pruebas de aceptación de UC-12502 contra las funciones públicas de ``server/approval.py``.

Cada prueba cita el criterio que demuestra (``AC-NN``). Solo se cubre lo que vive en el módulo:
la huella de los criterios, el estado de la aprobación y las funciones que lo interpretan. Lo que
pertenece a las tools (``approve_criteria``, ``start_uc``, ``find_next_uc``), a /prd o al
almacenamiento de FreeForm queda fuera y se dice en el informe.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

from server.approval import (
    APPROVED_STATES,
    MIGRATION_LABEL,
    approval_state,
    criteria_fingerprint,
    criteria_snapshot,
    is_approved,
    not_approved_reason,
)

UC = "UC-12502"
WHO = "jesusperezdeveloper"
WHEN = "2026-11-19T10:00:00+00:00"


def _criteria() -> list[dict]:
    return [
        {"id": "AC-01", "text": "El tablero registra la aprobación de los criterios."},
        {"id": "AC-02", "text": "start_uc no arranca una UC sin criterios aprobados."},
    ]


def _approval(fp: str, **extra) -> dict:
    return {"fingerprint": fp, "by": WHO, "at": WHEN, **extra}


# --------------------------------------------------------------------------- AC-01


def test_ac01_la_aprobacion_guarda_quien_y_cuando():
    """AC-01: la aprobación vigente de los criterios dice quién la dio y cuándo."""
    fp = criteria_fingerprint(_criteria())
    state = approval_state(_approval(fp, session_id="sesion-7", source="panel"), fp)
    assert state["state"] == "approved"
    assert state["by"] == WHO
    assert state["at"] == WHEN
    assert state["session_id"] == "sesion-7"
    assert state["source"] == "panel"
    assert is_approved(state) is True


def test_ac01_sin_quien_ni_cuando_no_se_inventan():
    """AC-01: si el registro no trae quién o cuándo, el estado no los inventa."""
    fp = criteria_fingerprint(_criteria())
    state = approval_state({"fingerprint": fp}, fp)
    assert state == {"state": "approved"}


def test_ac01_lo_que_se_aprueba_son_los_criterios_vigentes_con_su_id_y_su_texto():
    """AC-01: la foto de lo aprobado es [{id, text}] en orden de id, también con más de 9 criterios."""
    acs = [
        {"id": "AC-10", "text": "diez"},
        {"id": "AC-02", "text": "dos"},
        {"id": "AC-01", "text": "uno"},
    ]
    assert criteria_snapshot(acs) == [
        {"id": "AC-01", "text": "uno"},
        {"id": "AC-02", "text": "dos"},
        {"id": "AC-10", "text": "diez"},
    ]


def test_ac01_la_huella_es_estable_y_de_32_caracteres_hex():
    """AC-01: la huella que se guarda es determinista y no depende del orden en que lleguen los criterios."""
    acs = _criteria()
    fp = criteria_fingerprint(acs)
    assert re.fullmatch(r"[0-9a-f]{32}", fp)
    assert criteria_fingerprint(acs) == fp
    assert criteria_fingerprint(list(reversed(acs))) == fp


# --------------------------------------------------------------------------- AC-02


def test_ac02_una_uc_sin_aprobacion_no_cuenta_como_aprobada():
    """AC-02: sin ninguna aprobación el estado es «none» y no se cuenta como aprobada (lo que hace parar a start_uc)."""
    fp = criteria_fingerprint(_criteria())
    state = approval_state(None, fp)
    assert state == {"state": "none"}
    assert is_approved(state) is False
    assert is_approved(None) is False


def test_ac02_el_motivo_del_rechazo_nombra_la_uc():
    """AC-02: el motivo en llano de que una UC sin aprobar no arranque nombra su id."""
    fp = criteria_fingerprint(_criteria())
    reason = not_approved_reason(UC, approval_state(None, fp))
    assert reason == "Nadie ha aprobado todavía los criterios de UC-12502."


def test_ac02_un_registro_sin_huella_tampoco_aprueba():
    """AC-02: un registro de aprobación vacío o sin huella equivale a no haber aprobado."""
    fp = criteria_fingerprint(_criteria())
    assert approval_state({}, fp) == {"state": "none"}
    assert approval_state({"fingerprint": "", "by": WHO, "at": WHEN}, fp) == {"state": "none"}
    assert is_approved(approval_state({"by": WHO}, fp)) is False


# --------------------------------------------------------------------------- AC-03


def test_ac03_cambiar_el_texto_de_un_criterio_aprobado_deja_la_uc_sin_aprobar():
    """AC-03: reescribir el texto de un criterio aprobado cambia la huella y la UC queda «stale»."""
    original = _criteria()
    fp_aprobada = criteria_fingerprint(original)
    aprobacion = _approval(fp_aprobada)
    assert approval_state(aprobacion, fp_aprobada)["state"] == "approved"

    reescrito = _criteria()
    reescrito[1]["text"] = "start_uc no arranca una UC sin criterios aprobados y responde AC_NOT_APPROVED."
    fp_nueva = criteria_fingerprint(reescrito)
    assert fp_nueva != fp_aprobada

    state = approval_state(aprobacion, fp_nueva)
    assert state["state"] == "stale"
    assert state["reason"] == "Los criterios cambiaron después de la última aprobación."
    assert state["previous_by"] == WHO
    assert state["previous_at"] == WHEN
    assert is_approved(state) is False
    assert not_approved_reason(UC, state) == (
        "Los criterios de UC-12502 cambiaron después de su última aprobación."
    )


def test_ac03_anadir_un_criterio_deja_la_uc_sin_aprobar():
    """AC-03: añadir un criterio a una UC aprobada la deja «stale»."""
    original = _criteria()
    fp_aprobada = criteria_fingerprint(original)
    ampliado = original + [{"id": "AC-03", "text": "Un criterio nuevo."}]
    fp_nueva = criteria_fingerprint(ampliado)
    assert fp_nueva != fp_aprobada
    state = approval_state(_approval(fp_aprobada), fp_nueva)
    assert state["state"] == "stale"
    assert is_approved(state) is False


def test_ac03_retirar_un_criterio_deja_la_uc_sin_aprobar():
    """AC-03: retirar un criterio de una UC aprobada la deja «stale»."""
    original = _criteria()
    fp_aprobada = criteria_fingerprint(original)
    sin_el_segundo = original[:1]
    fp_nueva = criteria_fingerprint(sin_el_segundo)
    assert fp_nueva != fp_aprobada
    state = approval_state(_approval(fp_aprobada), fp_nueva)
    assert state["state"] == "stale"
    assert is_approved(state) is False


def test_ac03_una_nueva_aprobacion_devuelve_la_uc_a_aprobada():
    """AC-03: tras cambiar los criterios, solo una nueva aprobación (nueva huella) la deja aprobada otra vez."""
    original = _criteria()
    fp_vieja = criteria_fingerprint(original)
    cambiados = original + [{"id": "AC-03", "text": "Un criterio nuevo."}]
    fp_nueva = criteria_fingerprint(cambiados)

    vieja = _approval(fp_vieja)
    assert approval_state(vieja, fp_nueva)["state"] == "stale"

    nueva = {"fingerprint": fp_nueva, "by": "otra.persona", "at": "2026-11-20T09:00:00+00:00"}
    state = approval_state(nueva, fp_nueva)
    assert state["state"] == "approved"
    assert state["by"] == "otra.persona"
    assert state["at"] == "2026-11-20T09:00:00+00:00"
    assert is_approved(state) is True


def test_ac03_solo_cuentan_texto_alta_y_baja_no_la_verificacion_ni_el_estado_ni_los_espacios():
    """AC-03 (límite): cambiar cómo se comprueba un criterio, marcarlo o repetir espacios no invalida la aprobación."""
    base = [
        {"id": "AC-01", "text": "El tablero   registra la aprobación.", "verification": "review", "done": False},
        {"id": "AC-02", "text": "Otro criterio.", "verification": "review", "done": False},
    ]
    fp = criteria_fingerprint(base)
    cambiado = [
        {"id": "AC-01", "text": "El tablero registra la aprobación.", "verification": "automated_test", "done": True},
        {"id": "AC-02", "text": "  Otro   criterio. ", "verification": "manual", "done": True},
    ]
    assert criteria_fingerprint(cambiado) == fp
    assert approval_state(_approval(fp), criteria_fingerprint(cambiado))["state"] == "approved"


# --------------------------------------------------------------------------- AC-06


def test_ac06_una_uc_anterior_a_la_regla_cuenta_como_aprobada_por_migracion():
    """AC-06: una UC anterior a la regla y sin aprobación cuenta como aprobada, con la marca «aprobada por migración»."""
    fp = criteria_fingerprint(_criteria())
    state = approval_state(None, fp, predates=True)
    assert state == {"state": "migration", "source": "migration", "label": "aprobada por migración"}
    assert MIGRATION_LABEL == "aprobada por migración"
    assert is_approved(state) is True
    assert "migration" in APPROVED_STATES and "approved" in APPROVED_STATES


def test_ac06_la_aprobacion_real_gana_a_la_de_migracion():
    """AC-06: si una UC anterior a la regla tiene aprobación vigente, es «approved» y sin marca de migración."""
    fp = criteria_fingerprint(_criteria())
    state = approval_state(_approval(fp), fp, predates=True)
    assert state["state"] == "approved"
    assert state["by"] == WHO
    assert "label" not in state


def test_ac06_una_uc_anterior_a_la_regla_con_aprobacion_caducada_sigue_contando_por_migracion():
    """AC-06: una UC anterior a la regla cuya aprobación quedó «stale» cuenta como aprobada por migración."""
    fp_vieja = criteria_fingerprint(_criteria())
    fp_nueva = criteria_fingerprint(_criteria() + [{"id": "AC-03", "text": "Nuevo."}])
    state = approval_state(_approval(fp_vieja), fp_nueva, predates=True)
    assert state["state"] == "migration"
    assert state["label"] == "aprobada por migración"
    assert is_approved(state) is True


def test_ac06_una_uc_posterior_a_la_regla_sin_aprobar_no_cuenta_y_su_aviso_dice_por_que():
    """AC-06: sin ser anterior a la regla, una UC sin aprobar no cuenta como aprobada; el aviso (warn) y el motivo (block) salen de aquí."""
    fp = criteria_fingerprint(_criteria())
    sin_aprobar = approval_state(None, fp, predates=False)
    assert sin_aprobar == {"state": "none"}
    assert is_approved(sin_aprobar) is False
    assert not_approved_reason(UC, sin_aprobar) == "Nadie ha aprobado todavía los criterios de UC-12502."

    caducada = approval_state(_approval(fp), criteria_fingerprint(_criteria()[:1]), predates=False)
    assert caducada["state"] == "stale"
    assert is_approved(caducada) is False
    assert not_approved_reason(UC, caducada) == (
        "Los criterios de UC-12502 cambiaron después de su última aprobación."
    )


# --------------------------------------------------------------------------- AC-07


def test_ac07_la_misma_regla_vale_para_criterios_de_freeform_y_de_native():
    """AC-07 (parte del módulo): la huella no depende de si los criterios llegan como dicts de FreeForm, con ``ac_id``, o como objetos de native."""
    como_freeform = [
        {"id": "AC-01", "text": "Uno."},
        {"id": "AC-02", "text": "Dos."},
    ]
    con_ac_id = [
        {"ac_id": "AC-01", "text": "Uno."},
        {"ac_id": "AC-02", "text": "Dos."},
    ]
    como_objetos = [
        SimpleNamespace(id="AC-01", text="Uno."),
        SimpleNamespace(id="AC-02", text="Dos."),
    ]
    fp = criteria_fingerprint(como_freeform)
    assert criteria_fingerprint(con_ac_id) == fp
    assert criteria_fingerprint(como_objetos) == fp
    assert criteria_snapshot(como_objetos) == criteria_snapshot(como_freeform)


def test_ac07_el_mismo_estado_sale_con_los_dos_formatos_de_criterio():
    """AC-07 (parte del módulo): aprobar con criterios de un formato y comprobar con los del otro da «approved», y un cambio da «stale» en ambos."""
    freeform = [{"id": "AC-01", "text": "Uno."}, {"id": "AC-02", "text": "Dos."}]
    native = [SimpleNamespace(id="AC-01", text="Uno."), SimpleNamespace(id="AC-02", text="Dos.")]
    aprobacion = _approval(criteria_fingerprint(freeform))

    assert approval_state(aprobacion, criteria_fingerprint(native))["state"] == "approved"

    native_cambiado = [SimpleNamespace(id="AC-01", text="Uno."), SimpleNamespace(id="AC-02", text="Dos, cambiado.")]
    freeform_cambiado = [{"id": "AC-01", "text": "Uno."}, {"id": "AC-02", "text": "Dos, cambiado."}]
    assert approval_state(aprobacion, criteria_fingerprint(native_cambiado))["state"] == "stale"
    assert approval_state(aprobacion, criteria_fingerprint(freeform_cambiado))["state"] == "stale"
