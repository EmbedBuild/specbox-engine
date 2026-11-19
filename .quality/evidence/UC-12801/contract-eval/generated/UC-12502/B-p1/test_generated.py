"""Pruebas de aceptación de UC-12502 (aprobación de criterios) contra server/approval.py.

Generadas desde contract.json: cada prueba cita en su docstring las condiciones del contrato que
comprueba. Sin base de datos, red ni disco.
"""

from __future__ import annotations

from types import SimpleNamespace

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

UC = "UC-12502"
BY = "jesusperezdeveloper"
AT = "2026-11-19T10:00:00+00:00"
STALE_REASON = "Los criterios de UC-12502 cambiaron después de su última aprobación."
NONE_REASON = "Nadie ha aprobado todavía los criterios de UC-12502."


def _criteria():
    """AC-01 «Texto uno» y AC-02 «Texto dos», como los guarda el tablero."""
    return [
        {"id": "AC-01", "text": "Texto uno"},
        {"id": "AC-02", "text": "Texto dos"},
    ]


def _approval(acs, **extra):
    """Un registro de aprobación de esos criterios: su huella más lo que se le pase."""
    return {"fingerprint": criteria_fingerprint(acs), **extra}


def _approved_record(acs):
    return _approval(acs, by=BY, at=AT)


# ---------------------------------------------------------------------------------------------
# AC-01 · El tablero registra la aprobación con quién la dio y cuándo
# ---------------------------------------------------------------------------------------------


def test_ac01_a_saved_approval_reads_back_as_approved_with_who_and_when():
    """contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post2, AC-01.post3, AC-01.post4

    La aprobación guardada de los criterios vigentes se lee como «approved» con quién la dio, cuándo,
    su sesión y su origen, sin arrastrar la huella ni otras claves del registro.
    """
    acs = _criteria()
    record = _approval(
        acs, by=BY, at=AT, session_id="sess-1", source="panel", unrelated="no debe salir"
    )

    state = approval_state(record, criteria_fingerprint(acs))

    assert state["state"] == "approved"  # post1
    assert state["by"] == BY  # post2
    assert state["at"] == AT  # post3
    assert state["session_id"] == "sess-1"  # post4
    assert state["source"] == "panel"  # post4
    assert "fingerprint" not in state  # post4
    assert "unrelated" not in state  # post4
    assert set(state) == {"state", "by", "at", "session_id", "source"}  # post4


def test_ac01_the_approval_is_recognised_whatever_form_the_criteria_come_in():
    """contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post2

    La huella guardada vale para los mismos criterios vengan como diccionarios (id o ac_id) o como
    objetos, y en cualquier orden.
    """
    as_dicts = _criteria()
    record = _approved_record(as_dicts)

    as_ac_id_dicts = [{"ac_id": "AC-02", "text": "Texto dos"}, {"ac_id": "AC-01", "text": "Texto uno"}]
    as_objects = [SimpleNamespace(id="AC-01", text="Texto uno"), SimpleNamespace(id="AC-02", text="Texto dos")]

    for acs in (as_dicts, as_ac_id_dicts, as_objects):
        state = approval_state(record, criteria_fingerprint(acs))
        assert state["state"] == "approved"  # post1
        assert state["by"] == BY  # post2


def test_ac01_fields_the_record_does_not_carry_are_left_out_of_the_state():
    """contract: AC-01.pre2, AC-01.post1, AC-01.post2, AC-01.post3, AC-01.post4

    Sin session_id, source o con at a None, el estado no los inventa: solo lleva lo que el registro trae.
    """
    acs = _criteria()
    fp = criteria_fingerprint(acs)

    only_who = approval_state({"fingerprint": fp, "by": BY, "at": None, "session_id": None}, fp)
    assert only_who == {"state": "approved", "by": BY}  # post1, post2, post4 (nada más)
    assert "at" not in only_who  # post3 no se inventa

    bare = approval_state({"fingerprint": fp}, fp)
    assert bare == {"state": "approved"}  # post1
    for key in ("by", "at", "session_id", "source"):
        assert key not in bare  # post2, post3, post4

    verbatim = approval_state({"fingerprint": fp, "by": "Jesús Pérez", "at": 1763546400}, fp)
    assert verbatim["by"] == "Jesús Pérez"  # post2: el módulo no valida ni transforma by
    assert verbatim["at"] == 1763546400  # post3: tampoco at


# ---------------------------------------------------------------------------------------------
# AC-02 · Una UC sin criterios aprobados no cuenta como aprobada
# ---------------------------------------------------------------------------------------------


def test_ac02_a_uc_nobody_approved_is_none_and_not_approved():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    Sin ningún registro de aprobación el estado es «none», no cuenta como aprobada y el motivo lo dice.
    """
    acs = _criteria()

    state = approval_state(None, criteria_fingerprint(acs))

    assert state == {"state": "none"}  # post1
    assert is_approved(state) is False  # post2
    assert not_approved_reason(UC, state) == NONE_REASON  # post3


@pytest.mark.parametrize(
    "latest",
    [{}, {"by": BY, "at": AT}, {"fingerprint": None}, {"fingerprint": ""}, "approved", [], 0],
    ids=["dict-vacio", "sin-huella", "huella-None", "huella-vacia", "cadena", "lista", "cero"],
)
def test_ac02_a_record_that_cannot_be_an_approval_leaves_the_uc_without_approval(latest):
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    Un registro que no es un diccionario o no trae huella no aprueba nada: el estado es «none».
    """
    state = approval_state(latest, criteria_fingerprint(_criteria()))

    assert state == {"state": "none"}  # post1
    assert is_approved(state) is False  # post2
    assert not_approved_reason(UC, state) == NONE_REASON  # post3


def test_ac02_a_uc_with_no_criteria_and_no_approval_is_none():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3

    Una UC sin ningún criterio también necesita su aprobación: sin registro es «none».
    """
    state = approval_state(None, criteria_fingerprint([]))

    assert state == {"state": "none"}  # post1
    assert is_approved(state) is False  # post2
    assert not_approved_reason(UC, state) == NONE_REASON  # post3


def test_ac02_only_approved_and_migration_states_count_as_approved():
    """contract: AC-02.pre2, AC-02.post1, AC-02.post2

    is_approved es True solo para «approved» y «migration»; «none», «stale», un estado desconocido,
    None y lo que no es un diccionario no cuentan.
    """
    assert approval_state(None, "f" * 32) == {"state": "none"}  # post1
    assert APPROVED_STATES == frozenset({"approved", "migration"})

    assert is_approved({"state": "approved"}) is True
    assert is_approved({"state": "migration"}) is True
    assert is_approved({"state": "none"}) is False  # post2
    assert is_approved({"state": "stale"}) is False  # post2
    assert is_approved({"state": "otro"}) is False
    assert is_approved({}) is False
    assert is_approved(None) is False
    assert is_approved("approved") is False


def test_ac02_the_reason_for_a_uc_without_approval_names_that_uc():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post3

    El motivo lleva el id de la UC que se le pase.
    """
    state = approval_state(None, criteria_fingerprint(_criteria()))

    assert not_approved_reason("UC-12502", state) == "Nadie ha aprobado todavía los criterios de UC-12502."  # post3
    assert not_approved_reason("UC-99999", state) == "Nadie ha aprobado todavía los criterios de UC-99999."  # post3


# ---------------------------------------------------------------------------------------------
# AC-03 · Cambiar, añadir o retirar un criterio deja la UC sin aprobar hasta otra aprobación
# ---------------------------------------------------------------------------------------------


def _rewritten():
    return [{"id": "AC-01", "text": "Texto uno"}, {"id": "AC-02", "text": "Texto dos reescrito"}]


def _with_added():
    return [*_criteria(), {"id": "AC-03", "text": "Texto tres"}]


def _with_retired():
    return [{"id": "AC-01", "text": "Texto uno"}]  # AC-02 ya no está entre los vigentes


def test_ac03_rewriting_the_text_of_an_approved_criterion_voids_the_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1

    Con la aprobación vigente la UC está «approved»; al reescribir el texto de AC-02 la huella cambia y
    la UC queda «stale».
    """
    before = _criteria()
    record = _approved_record(before)
    fp0 = criteria_fingerprint(before)
    assert approval_state(record, fp0)["state"] == "approved"  # pre1

    after = _rewritten()
    fp1 = criteria_fingerprint(after)

    assert fp1 != fp0  # post1
    assert approval_state(record, fp1)["state"] == "stale"  # post1


def test_ac03_adding_a_criterion_to_an_approved_uc_voids_the_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post2

    Con la aprobación vigente la UC está «approved»; al añadir AC-03 la huella cambia y queda «stale».
    """
    before = _criteria()
    record = _approved_record(before)
    fp0 = criteria_fingerprint(before)
    assert approval_state(record, fp0)["state"] == "approved"  # pre1

    after = _with_added()
    fp1 = criteria_fingerprint(after)

    assert fp1 != fp0  # post2
    assert approval_state(record, fp1)["state"] == "stale"  # post2


def test_ac03_retiring_a_criterion_from_an_approved_uc_voids_the_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post3

    Con la aprobación vigente la UC está «approved»; al retirar AC-02 (ya no figura entre los vigentes)
    la huella cambia y queda «stale», retire el primero, el último o uno del medio.
    """
    before = _criteria()
    record = _approved_record(before)
    fp0 = criteria_fingerprint(before)
    assert approval_state(record, fp0)["state"] == "approved"  # pre1

    fp1 = criteria_fingerprint(_with_retired())
    assert fp1 != fp0  # post3
    assert approval_state(record, fp1)["state"] == "stale"  # post3

    three = [*_criteria(), {"id": "AC-03", "text": "Texto tres"}]
    record3 = _approved_record(three)
    for retired_id in ("AC-01", "AC-02", "AC-03"):
        remaining = [ac for ac in three if ac["id"] != retired_id]
        assert approval_state(record3, criteria_fingerprint(remaining))["state"] == "stale"  # post3


@pytest.mark.parametrize(
    "change", [_rewritten, _with_added, _with_retired], ids=["reescribir", "anadir", "retirar"]
)
def test_ac03_a_voided_approval_is_not_approved_and_says_why(change):
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post4

    Tras reescribir, añadir o retirar un criterio la UC no cuenta como aprobada y el motivo es el de
    criterios cambiados.
    """
    before = _criteria()
    record = _approved_record(before)
    assert is_approved(approval_state(record, criteria_fingerprint(before))) is True  # pre1

    state = approval_state(record, criteria_fingerprint(change()))

    assert state["state"] == "stale"
    assert is_approved(state) is False  # post4
    assert not_approved_reason(UC, state) == STALE_REASON  # post4


def test_ac03_the_stale_state_keeps_who_and_when_of_the_previous_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post5

    El estado «stale» no hace pasar la aprobación vieja por vigente: guarda quién y cuándo aprobó antes
    como previous_by y previous_at y da un motivo.
    """
    before = _criteria()
    record = _approved_record(before)
    assert approval_state(record, criteria_fingerprint(before))["state"] == "approved"  # pre1

    state = approval_state(record, criteria_fingerprint(_rewritten()))

    assert state["state"] == "stale"  # post1
    assert state["previous_by"] == BY  # post5
    assert state["previous_at"] == AT  # post5
    assert state["reason"] == "Los criterios cambiaron después de la última aprobación."  # post5
    assert "by" not in state and "at" not in state  # post5: no es una aprobación vigente
    assert set(state) == {"state", "reason", "previous_by", "previous_at"}  # post5


def test_ac03_a_stale_state_without_who_and_when_does_not_invent_them():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post5

    Si la aprobación anterior no traía by ni at, el estado «stale» no los inventa pero sí da el motivo.
    """
    before = _criteria()
    record = _approval(before)  # solo la huella

    state = approval_state(record, criteria_fingerprint(_with_added()))

    assert state["state"] == "stale"  # post1
    assert "previous_by" not in state  # post5
    assert "previous_at" not in state  # post5
    assert state["reason"] == "Los criterios cambiaron después de la última aprobación."  # post5


def test_ac03_the_uc_stays_unapproved_until_a_new_approval_of_the_new_criteria():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post6

    Mientras no haya una aprobación nueva la UC sigue «stale» (también si se vuelve a preguntar); con
    una nueva aprobación de los criterios nuevos vuelve a «approved» con el by y el at de la nueva.
    """
    before = _criteria()
    old_record = _approved_record(before)
    after = _rewritten()
    fp1 = criteria_fingerprint(after)

    assert approval_state(old_record, fp1)["state"] == "stale"  # post1
    assert approval_state(old_record, fp1)["state"] == "stale"  # post6: sigue igual hasta aprobar
    assert is_approved(approval_state(old_record, fp1)) is False  # post6

    new_record = _approval(after, by="otra.persona", at="2026-11-19T12:30:00+00:00")
    state = approval_state(new_record, fp1)

    assert state["state"] == "approved"  # post6
    assert state["by"] == "otra.persona"  # post6
    assert state["at"] == "2026-11-19T12:30:00+00:00"  # post6
    assert is_approved(state) is True  # post6
    # la aprobación vieja no resucita sobre los criterios nuevos
    assert approval_state(old_record, fp1)["state"] == "stale"  # post6


def test_ac03_each_change_gives_a_different_fingerprint_and_a_distinct_approval_is_needed():
    """contract: AC-03.pre2, AC-03.post1, AC-03.post2, AC-03.post3

    Reescribir, añadir y retirar dan huellas distintas entre sí y de la original: aprobar una variante no
    aprueba las otras.
    """
    base = criteria_fingerprint(_criteria())
    variants = {
        "reescribir": criteria_fingerprint(_rewritten()),
        "anadir": criteria_fingerprint(_with_added()),
        "retirar": criteria_fingerprint(_with_retired()),
    }

    assert len({base, *variants.values()}) == 4  # post1, post2, post3

    record_of_rewrite = _approval(_rewritten(), by=BY, at=AT)
    assert approval_state(record_of_rewrite, variants["reescribir"])["state"] == "approved"
    assert approval_state(record_of_rewrite, variants["anadir"])["state"] == "stale"  # post2
    assert approval_state(record_of_rewrite, variants["retirar"])["state"] == "stale"  # post3
    assert approval_state(record_of_rewrite, base)["state"] == "stale"  # post1


# --- lo que el criterio no define y el módulo resuelve de un modo observable -------------------


def test_ac03_undefined_changes_that_do_not_touch_id_or_text_keep_the_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1

    Contraste con post1: reescribir el texto anula la aprobación, pero cambiar la verificación,
    marcar un criterio como hecho o añadirle recibos (campos que no son id ni texto) no cambia la huella.
    """
    before = _criteria()
    fp0 = criteria_fingerprint(before)
    record = _approved_record(before)

    assert approval_state(record, criteria_fingerprint(_rewritten()))["state"] == "stale"  # post1 (control)

    decorated = [
        {"id": "AC-01", "text": "Texto uno", "done": True, "verification": "automated_test", "evidence": [{"passed": True}]},
        {"id": "AC-02", "text": "Texto dos", "done": False, "verification": "review", "internal": True},
    ]
    assert criteria_fingerprint(decorated) == fp0
    assert approval_state(record, criteria_fingerprint(decorated))["state"] == "approved"

    as_objects = [
        SimpleNamespace(id="AC-01", text="Texto uno", done=True, verification="manual"),
        SimpleNamespace(id="AC-02", text="Texto dos", done=True, verification="review"),
    ]
    assert criteria_fingerprint(as_objects) == fp0


def test_ac03_undefined_whitespace_inside_the_text_is_not_a_change_but_case_and_words_are():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1

    Contraste con post1: los espacios repetidos, los saltos de línea y los espacios de los extremos no
    cambian la huella; una mayúscula distinta o una palabra distinta sí la cambian y dejan «stale».
    """
    before = _criteria()
    fp0 = criteria_fingerprint(before)
    record = _approved_record(before)

    spaced = [{"id": "AC-01", "text": "  Texto   uno\n"}, {"id": "AC-02", "text": "Texto\tdos "}]
    assert criteria_fingerprint(spaced) == fp0
    assert approval_state(record, criteria_fingerprint(spaced))["state"] == "approved"

    for text in ("texto uno", "Texto uno.", "Texto  1"):
        changed = [{"id": "AC-01", "text": text}, {"id": "AC-02", "text": "Texto dos"}]
        assert criteria_fingerprint(changed) != fp0  # post1
        assert approval_state(record, criteria_fingerprint(changed))["state"] == "stale"  # post1


def test_ac03_undefined_reordering_the_criteria_is_not_a_change_but_changing_an_id_is():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1

    Contraste con post1: el orden en que lleguen los criterios no cambia la huella (se ordenan por
    número de id); darle otro id al mismo texto sí la cambia y deja «stale».
    """
    before = _criteria()
    fp0 = criteria_fingerprint(before)
    record = _approved_record(before)

    assert criteria_fingerprint(list(reversed(before))) == fp0
    assert approval_state(record, criteria_fingerprint(list(reversed(before))))["state"] == "approved"

    renumbered = [{"id": "AC-01", "text": "Texto uno"}, {"id": "AC-03", "text": "Texto dos"}]
    assert criteria_fingerprint(renumbered) != fp0  # post1
    assert approval_state(record, criteria_fingerprint(renumbered))["state"] == "stale"  # post1


def test_ac03_undefined_reverting_the_change_brings_the_old_approval_back():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1

    La huella depende solo del contenido vigente: tras reescribir un criterio («stale», post1), dejar el
    texto como estaba vuelve a la huella original y la aprobación antigua vuelve a valer.
    """
    before = _criteria()
    record = _approved_record(before)

    assert approval_state(record, criteria_fingerprint(_rewritten()))["state"] == "stale"  # post1

    restored = [{"id": "AC-01", "text": "Texto uno"}, {"id": "AC-02", "text": "Texto dos"}]
    assert criteria_fingerprint(restored) == criteria_fingerprint(before)
    assert approval_state(record, criteria_fingerprint(restored))["state"] == "approved"


def test_ac03_undefined_the_fingerprint_is_a_stable_32_hex_digest():
    """contract: AC-03.pre1, AC-03.post1

    La huella es siempre la misma para los mismos criterios, de 32 caracteres hexadecimales, y cambia
    con el texto (post1).
    """
    acs = _criteria()
    fp = criteria_fingerprint(acs)

    assert fp == criteria_fingerprint(_criteria())
    assert isinstance(fp, str) and len(fp) == 32
    assert fp == fp.lower()
    int(fp, 16)  # hexadecimal
    assert criteria_fingerprint(_rewritten()) != fp  # post1


def test_ac03_undefined_the_snapshot_is_ordered_by_number_and_normalises_the_text():
    """contract: AC-03.pre1, AC-03.post2

    Los criterios vigentes se guardan como [{id, text}] en orden de número (AC-2 antes que AC-10), con el
    texto sin espacios repetidos; los ids que no siguen AC-NN van al final. Añadir un criterio (post2)
    cambia la huella.
    """
    shuffled = [
        {"id": "AC-10", "text": "diez"},
        {"ac_id": "AC-2", "text": "  dos   dos "},
        SimpleNamespace(id="AC-1", text="uno"),
    ]

    assert criteria_snapshot(shuffled) == [
        {"id": "AC-1", "text": "uno"},
        {"id": "AC-2", "text": "dos dos"},
        {"id": "AC-10", "text": "diez"},
    ]

    odd = [{"id": "foo", "text": "f"}, {"id": "AC-x", "text": "x"}, {"id": "AC-03", "text": "tres"}]
    assert [p["id"] for p in criteria_snapshot(odd)] == ["AC-03", "AC-x", "foo"]

    assert criteria_snapshot([]) == []
    assert criteria_fingerprint([*shuffled, {"id": "AC-11", "text": "once"}]) != criteria_fingerprint(shuffled)  # post2


# ---------------------------------------------------------------------------------------------
# AC-06 · Las UC anteriores a la regla cuentan como aprobadas, «aprobada por migración»
# ---------------------------------------------------------------------------------------------


def test_ac06_a_uc_predating_the_rule_without_approval_counts_as_approved_by_migration():
    """contract: AC-06.pre1, AC-06.post1, AC-06.post2, AC-06.post3

    Una UC anterior a la regla sin ninguna aprobación queda en «migration» con su marca, cuenta como
    aprobada y no inventa un by ni un at.
    """
    fp = criteria_fingerprint(_criteria())

    state = approval_state(None, fp, predates=True)

    assert state == {"state": "migration", "source": "migration", "label": "aprobada por migración"}  # post1
    assert state["label"] == MIGRATION_LABEL == "aprobada por migración"  # post1
    assert is_approved(state) is True  # post2
    assert "by" not in state and "at" not in state  # post3


def test_ac06_a_uc_predating_the_rule_with_a_record_of_other_criteria_is_still_migration():
    """contract: AC-06.pre1, AC-06.post1, AC-06.post2, AC-06.post3

    Anterior a la regla y con un registro cuya huella es otra (la aprobación quedó obsoleta): cuenta como
    migración, aprobada, y no arrastra el by ni el at del registro obsoleto.
    """
    old_criteria = _criteria()
    old_record = _approved_record(old_criteria)
    now = criteria_fingerprint(_rewritten())

    state = approval_state(old_record, now, predates=True)

    assert state == {"state": "migration", "source": "migration", "label": MIGRATION_LABEL}  # post1
    assert is_approved(state) is True  # post2
    for key in ("by", "at", "previous_by", "previous_at", "reason"):
        assert key not in state  # post3


def test_ac06_without_the_predates_flag_the_same_uc_is_not_counted_as_approved():
    """contract: AC-06.pre1, AC-06.post1, AC-06.post2

    predates vale False por defecto: la misma UC sin aprobación y sin la marca es «none» y no cuenta,
    mientras que con predates=True pasa a «migration» y cuenta (post1, post2).
    """
    fp = criteria_fingerprint(_criteria())

    default = approval_state(None, fp)
    explicit_false = approval_state(None, fp, predates=False)
    flagged = approval_state(None, fp, predates=True)

    assert default == explicit_false == {"state": "none"}
    assert is_approved(default) is False
    assert flagged["state"] == "migration"  # post1
    assert is_approved(flagged) is True  # post2


def test_ac06_a_real_approval_of_the_current_criteria_wins_over_the_migration_mark():
    """contract: AC-06.pre1, AC-06.post1, AC-06.post2

    Si además de ser anterior a la regla tiene una aprobación de los criterios de ahora, el estado es
    «approved» (con su by y su at), sin la marca de migración; con otra huella vuelve a «migration»
    (post1) y en ambos casos cuenta como aprobada (post2).
    """
    acs = _criteria()
    fp = criteria_fingerprint(acs)

    with_real = approval_state(_approved_record(acs), fp, predates=True)
    assert with_real["state"] == "approved"
    assert with_real["by"] == BY and with_real["at"] == AT
    assert "label" not in with_real and "source" not in with_real
    assert is_approved(with_real) is True  # post2

    other = approval_state(_approved_record(acs), criteria_fingerprint(_with_added()), predates=True)
    assert other["state"] == "migration"  # post1
    assert is_approved(other) is True  # post2


def test_ac06_the_migration_state_has_no_reason_to_be_not_approved_and_is_not_stale():
    """contract: AC-06.pre1, AC-06.post1, AC-06.post2

    La UC anterior a la regla no se queda «stale» aunque cambien sus criterios: sigue en «migration»
    (post1) y aprobada (post2). El motivo de no estar aprobada solo se pide cuando no lo está.
    """
    before = _criteria()
    record = _approved_record(before)

    for acs in (_rewritten(), _with_added(), _with_retired()):
        state = approval_state(record, criteria_fingerprint(acs), predates=True)
        assert state["state"] == "migration"  # post1
        assert is_approved(state) is True  # post2

    # sin la marca, los mismos cambios sí la dejan «stale» y sin aprobar
    unflagged = approval_state(record, criteria_fingerprint(_rewritten()))
    assert unflagged["state"] == "stale"
    assert is_approved(unflagged) is False
