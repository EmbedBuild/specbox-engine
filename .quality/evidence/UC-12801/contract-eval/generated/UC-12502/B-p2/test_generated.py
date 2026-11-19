"""Pruebas de aceptación de UC-12502 contra las funciones públicas de ``server/approval.py``.

Salen del contrato (``contract.json`` de esta carpeta). Cada prueba cita en su docstring las
condiciones que comprueba (``contract: AC-NN.preN, AC-NN.postN``) y, cuando resuelve algo que el
contrato deja en ``undefined``, lo dice en una línea ``undefined:``.

Fuera de alcance (no dependen de ``server/approval.py``): AC-04 (orden y filtro de ``find_next_uc``),
AC-05 (paso del skill /prd) y AC-07 (guardado en FreeForm); y del AC-02 y el AC-06 el comportamiento
de ``start_uc`` (``AC_NOT_APPROVED``, aviso en «warn», no arrancar en «block»).
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
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
WHO = "jesusperezdeveloper"
WHEN = "2026-11-19T10:15:00+00:00"
HEX32 = re.compile(r"^[0-9a-f]{32}$")


def criteria() -> list[dict]:
    """Los criterios vigentes de una UC de prueba (con los campos de un criterio real)."""
    return [
        {"id": "AC-01", "text": "El tablero registra la aprobación con quién y cuándo.",
         "verification": "automated_test", "done": False},
        {"id": "AC-02", "text": "start_uc no arranca una UC sin criterios aprobados.",
         "verification": "automated_test", "done": False},
        {"id": "AC-03", "text": "Cambiar un criterio deja la UC sin aprobar.",
         "verification": "review", "done": False},
    ]


def approval(acs: list[dict], **extra) -> dict:
    """Una aprobación guardada de estos criterios: su huella, quién y cuándo."""
    saved = {"fingerprint": criteria_fingerprint(acs), "by": WHO, "at": WHEN}
    saved.update(extra)
    return saved


# --------------------------------------------------------------------------------------------
# AC-01 · el tablero registra la aprobación con quién y cuándo
# --------------------------------------------------------------------------------------------


def test_ac01_approved_state_carries_who_and_when():
    """contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post2, AC-01.post3"""
    acs = criteria()
    saved = approval(acs)  # pre1: aprobación guardada con huella, by y at
    fingerprint_now = criteria_fingerprint(copy.deepcopy(acs))  # pre2: mismos criterios, misma huella
    assert fingerprint_now == saved["fingerprint"]

    state = approval_state(saved, fingerprint_now)

    assert state["state"] == "approved"  # post1
    assert state["by"] == WHO  # post2
    assert state["at"] == WHEN  # post3


def test_ac01_fingerprint_is_a_stable_32_hex_string():
    """contract: AC-01.pre2, AC-01.post4"""
    acs = criteria()

    first = criteria_fingerprint(acs)
    second = criteria_fingerprint(copy.deepcopy(acs))

    assert isinstance(first, str)
    assert HEX32.match(first)
    assert first == second


def test_ac01_is_approved_true_for_the_approved_state():
    """contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post5"""
    acs = criteria()
    state = approval_state(approval(acs), criteria_fingerprint(acs))

    assert state["state"] == "approved"
    assert is_approved(state) is True


def test_ac01_state_copies_session_and_source_and_omits_what_the_approval_lacks():
    """contract: AC-01.pre1, AC-01.pre2, AC-01.post2, AC-01.post3
    undefined: qué datos de la aprobación guardada se reflejan además de quién y cuándo, y qué pasa con los que faltan.
    """
    acs = criteria()
    fp = criteria_fingerprint(acs)

    full = approval_state(approval(acs, session_id="sess-9", source="panel"), fp)
    assert full == {"state": "approved", "by": WHO, "at": WHEN, "session_id": "sess-9", "source": "panel"}

    # Sin quién, sin cuándo y con campos a None: el estado no los trae y sigue aprobado.
    bare = approval_state({"fingerprint": fp, "by": None, "at": None, "session_id": None, "source": None}, fp)
    assert bare == {"state": "approved"}
    assert is_approved(bare) is True

    only_who = approval_state({"fingerprint": fp, "by": WHO}, fp)
    assert only_who == {"state": "approved", "by": WHO}


def test_ac01_state_does_not_expose_the_fingerprint_nor_unknown_fields():
    """contract: AC-01.pre1, AC-01.pre2, AC-01.post1
    undefined: si el estado devuelve también la huella u otros campos de la aprobación guardada.
    """
    acs = criteria()
    fp = criteria_fingerprint(acs)
    saved = approval(acs, comment="visto bueno", fingerprint_version=2)

    state = approval_state(saved, fp)

    assert "fingerprint" not in state
    assert "comment" not in state
    assert "fingerprint_version" not in state
    assert set(state) == {"state", "by", "at"}


def test_ac01_fingerprint_of_no_criteria_is_still_a_valid_fingerprint():
    """contract: AC-01.pre2, AC-01.post4
    undefined: qué huella tienen unos criterios vacíos.
    """
    empty = criteria_fingerprint([])

    assert HEX32.match(empty)
    assert empty == criteria_fingerprint([])
    assert empty != criteria_fingerprint(criteria())
    assert approval_state({"fingerprint": empty, "by": WHO, "at": WHEN}, empty)["state"] == "approved"


# --------------------------------------------------------------------------------------------
# AC-02 · una UC sin criterios aprobados no cuenta como aprobada (lo que decide start_uc)
# --------------------------------------------------------------------------------------------


def test_ac02_never_approved_state_is_none_without_who_or_when():
    """contract: AC-02.pre1, AC-02.post1"""
    state = approval_state(None, criteria_fingerprint(criteria()))

    assert state == {"state": "none"}
    assert "by" not in state
    assert "at" not in state


def test_ac02_never_approved_does_not_count_as_approved():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2"""
    state = approval_state(None, criteria_fingerprint(criteria()))

    assert state["state"] == "none"
    assert is_approved(state) is False


def test_ac02_reason_says_nobody_approved_and_names_the_uc():
    """contract: AC-02.pre1, AC-02.post3"""
    state = approval_state(None, criteria_fingerprint(criteria()))

    reason = not_approved_reason(UC, state)

    assert reason == f"Nadie ha aprobado todavía los criterios de {UC}."
    assert not_approved_reason("UC-99999", state) == "Nadie ha aprobado todavía los criterios de UC-99999."


def test_ac02_a_uc_with_no_criteria_and_no_approval_is_not_approved():
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: qué pasa con una UC sin ningún criterio.
    """
    state = approval_state(None, criteria_fingerprint([]))

    assert state == {"state": "none"}
    assert is_approved(state) is False


@pytest.mark.parametrize(
    "saved",
    [
        {},
        {"by": WHO, "at": WHEN},
        {"fingerprint": "", "by": WHO, "at": WHEN},
        {"fingerprint": None, "by": WHO, "at": WHEN},
        "not-a-dict",
        ["fingerprint"],
        0,
    ],
    ids=["empty-dict", "no-fingerprint", "empty-fingerprint", "none-fingerprint", "string", "list", "int"],
)
def test_ac02_a_saved_approval_without_a_usable_fingerprint_is_none(saved):
    """contract: AC-02.pre1, AC-02.post1, AC-02.post2
    undefined: qué pasa si la aprobación guardada no es un diccionario, o no trae huella o la trae vacía.
    """
    state = approval_state(saved, criteria_fingerprint(criteria()))

    assert state == {"state": "none"}
    assert is_approved(state) is False
    assert not_approved_reason(UC, state) == f"Nadie ha aprobado todavía los criterios de {UC}."


@pytest.mark.parametrize(
    "state",
    [
        None,
        {},
        {"state": "none"},
        {"state": "stale"},
        {"state": "other"},
        {"state": None},
        {"state": ""},
        "approved",
        ["approved"],
        42,
    ],
    ids=["none", "empty", "none-state", "stale", "unknown", "state-none", "state-empty", "str", "list", "int"],
)
def test_ac02_is_approved_is_false_for_anything_that_is_not_an_approved_state(state):
    """contract: AC-02.pre1, AC-02.post2
    undefined: qué devuelve is_approved con un estado ausente, que no es un diccionario o con un nombre desconocido.
    """
    assert is_approved(state) is False


def test_ac02_only_approved_and_migration_count_as_approved():
    """contract: AC-02.pre1, AC-02.post2, AC-01.post5
    undefined: qué estados cuentan como aprobados.
    """
    assert APPROVED_STATES == frozenset({"approved", "migration"})
    assert is_approved({"state": "approved"}) is True
    assert is_approved({"state": "migration"}) is True
    assert is_approved({"state": "stale"}) is False
    assert is_approved({"state": "none"}) is False


# --------------------------------------------------------------------------------------------
# AC-03 · cambiar, añadir o retirar un criterio deja la UC sin aprobar
# --------------------------------------------------------------------------------------------


def _rewritten(acs: list[dict]) -> list[dict]:
    out = copy.deepcopy(acs)
    out[1]["text"] = "start_uc no arranca una UC sin criterios aprobados y lo avisa."
    return out


def _added(acs: list[dict]) -> list[dict]:
    return copy.deepcopy(acs) + [{"id": "AC-04", "text": "find_next_uc no propone UC sin aprobar."}]


def _removed(acs: list[dict]) -> list[dict]:
    return [ac for ac in copy.deepcopy(acs) if ac["id"] != "AC-02"]


CHANGES = pytest.mark.parametrize(
    "change", [_rewritten, _added, _removed], ids=["text-rewritten", "criterion-added", "criterion-removed"]
)


@CHANGES
def test_ac03_any_change_gives_a_different_fingerprint(change):
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1"""
    acs = criteria()
    saved = approval(acs)  # pre1

    changed = change(acs)  # pre2

    assert criteria_fingerprint(changed) != saved["fingerprint"]


@CHANGES
def test_ac03_any_change_leaves_the_uc_stale_and_not_approved(change):
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2"""
    acs = criteria()
    saved = approval(acs)
    assert is_approved(approval_state(saved, criteria_fingerprint(acs))) is True

    state = approval_state(saved, criteria_fingerprint(change(acs)))

    assert state["state"] == "stale"
    assert is_approved(state) is False


@CHANGES
def test_ac03_stale_state_says_why_and_who_and_when_approved_before(change):
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post2, AC-03.post3"""
    acs = criteria()
    saved = approval(acs)

    state = approval_state(saved, criteria_fingerprint(change(acs)))

    assert state["state"] == "stale"
    assert state["reason"] == "Los criterios cambiaron después de la última aprobación."
    assert state["previous_by"] == WHO
    assert state["previous_at"] == WHEN
    assert "by" not in state and "at" not in state


@CHANGES
def test_ac03_stale_reason_in_plain_words_names_the_uc(change):
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post2, AC-03.post4"""
    acs = criteria()
    state = approval_state(approval(acs), criteria_fingerprint(change(acs)))

    assert state["state"] == "stale"
    assert not_approved_reason(UC, state) == f"Los criterios de {UC} cambiaron después de su última aprobación."


@CHANGES
def test_ac03_a_new_approval_brings_the_uc_back_to_approved(change):
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post2, AC-03.post5"""
    acs = criteria()
    old = approval(acs, by="ana", at="2026-11-18T08:00:00+00:00")
    changed = change(acs)
    fp = criteria_fingerprint(changed)
    assert approval_state(old, fp)["state"] == "stale"

    renewed = approval(changed, by="luis", at="2026-11-19T09:00:00+00:00")
    state = approval_state(renewed, fp)

    assert state["state"] == "approved"
    assert state["by"] == "luis"
    assert state["at"] == "2026-11-19T09:00:00+00:00"
    assert is_approved(state) is True


def test_ac03_going_back_to_the_approved_text_brings_back_the_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2
    undefined: si volver al texto aprobado devuelve la UC a «approved» sin nueva aprobación.
    """
    acs = criteria()
    saved = approval(acs)
    assert approval_state(saved, criteria_fingerprint(_rewritten(acs)))["state"] == "stale"

    state = approval_state(saved, criteria_fingerprint(copy.deepcopy(acs)))

    assert state["state"] == "approved"


def test_ac03_changing_how_a_criterion_is_verified_or_marking_it_does_not_void_the_approval():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2
    undefined: si cambiar cómo se comprueba un criterio o marcarlo como hecho invalida la aprobación.
    """
    acs = criteria()
    saved = approval(acs)

    other = copy.deepcopy(acs)
    other[0]["verification"] = "review"
    other[1]["done"] = True
    other[2]["evidence"] = [{"type": "test", "passed": True}]
    other[2]["internal"] = True

    assert criteria_fingerprint(other) == saved["fingerprint"]
    assert approval_state(saved, criteria_fingerprint(other))["state"] == "approved"


def test_ac03_whitespace_only_changes_keep_the_approval_but_case_changes_void_it():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2
    undefined: si un cambio solo de espacios o de saltos en el texto invalida la aprobación, y si un cambio de mayúsculas lo hace.
    """
    acs = criteria()
    saved = approval(acs)

    spaced = copy.deepcopy(acs)
    spaced[0]["text"] = "  El tablero   registra la aprobación\ncon quién  y cuándo.\t"
    assert criteria_fingerprint(spaced) == saved["fingerprint"]
    assert approval_state(saved, criteria_fingerprint(spaced))["state"] == "approved"

    cased = copy.deepcopy(acs)
    cased[0]["text"] = cased[0]["text"].upper()
    assert criteria_fingerprint(cased) != saved["fingerprint"]
    assert approval_state(saved, criteria_fingerprint(cased))["state"] == "stale"

    punctuated = copy.deepcopy(acs)
    punctuated[2]["text"] = punctuated[2]["text"].rstrip(".")
    assert criteria_fingerprint(punctuated) != saved["fingerprint"]


def test_ac03_input_order_does_not_change_the_fingerprint_but_renumbering_does():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post2
    undefined: si el orden en que llegan los criterios cambia la huella, y si renumerar o intercambiar textos la cambia.
    """
    acs = criteria()
    saved = approval(acs)

    assert criteria_fingerprint(list(reversed(acs))) == saved["fingerprint"]
    assert criteria_fingerprint([acs[2], acs[0], acs[1]]) == saved["fingerprint"]

    swapped = copy.deepcopy(acs)
    swapped[0]["text"], swapped[1]["text"] = acs[1]["text"], acs[0]["text"]
    assert criteria_fingerprint(swapped) != saved["fingerprint"]
    assert approval_state(saved, criteria_fingerprint(swapped))["state"] == "stale"

    renumbered = copy.deepcopy(acs)
    renumbered[1]["id"] = "AC-05"
    assert criteria_fingerprint(renumbered) != saved["fingerprint"]
    assert approval_state(saved, criteria_fingerprint(renumbered))["state"] == "stale"

    # Retirar un criterio sin renumerar el resto también cambia la huella.
    assert criteria_fingerprint(_removed(acs)) != saved["fingerprint"]


def test_ac03_stale_state_omits_previous_who_and_when_if_the_old_approval_lacked_them():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post2, AC-03.post3
    undefined: qué trae el estado stale si la aprobación anterior no guardaba quién o cuándo.
    """
    acs = criteria()
    fp_old = criteria_fingerprint(acs)
    fp_new = criteria_fingerprint(_added(acs))

    only_fp = approval_state({"fingerprint": fp_old}, fp_new)
    assert only_fp == {"state": "stale", "reason": "Los criterios cambiaron después de la última aprobación."}

    only_at = approval_state({"fingerprint": fp_old, "at": WHEN, "by": None}, fp_new)
    assert only_at["state"] == "stale"
    assert only_at["previous_at"] == WHEN
    assert "previous_by" not in only_at

    only_by = approval_state({"fingerprint": fp_old, "by": WHO}, fp_new)
    assert only_by["previous_by"] == WHO
    assert "previous_at" not in only_by


def test_ac03_snapshot_orders_by_number_with_non_numeric_ids_last():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    undefined: cómo ordena criteria_snapshot los ids que no son numéricos.
    """
    shuffled = [
        {"id": "AC-10", "text": "diez"},
        {"id": "ZZ", "text": "zeta"},
        {"id": "AC-2", "text": "dos"},
        {"id": "AA", "text": "a"},
        {"id": "AC-1", "text": "uno"},
        {"id": "AC-X", "text": "equis"},
    ]

    snapshot = criteria_snapshot(shuffled)

    assert [p["id"] for p in snapshot] == ["AC-1", "AC-2", "AC-10", "AA", "AC-X", "ZZ"]
    assert snapshot[0] == {"id": "AC-1", "text": "uno"}


def test_ac03_snapshot_accepts_dicts_with_id_or_ac_id_and_objects_with_attributes():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    undefined: qué formas de criterio acepta (diccionario con id o ac_id, objeto con atributos).
    """

    @dataclass
    class Criterion:
        id: str
        text: str

    expected = [{"id": "AC-01", "text": "uno"}, {"id": "AC-02", "text": "dos"}]

    from_dicts = criteria_snapshot([{"id": "AC-02", "text": "dos"}, {"id": "AC-01", "text": "uno"}])
    from_ac_id = criteria_snapshot([{"ac_id": "AC-02", "text": "dos"}, {"ac_id": "AC-01", "text": "uno"}])
    from_objects = criteria_snapshot([Criterion("AC-02", "dos"), Criterion("AC-01", "uno")])
    from_namespaces = criteria_snapshot([SimpleNamespace(id="AC-02", text="dos"), SimpleNamespace(id="AC-01", text="uno")])

    assert from_dicts == expected
    assert from_ac_id == expected
    assert from_objects == expected
    assert from_namespaces == expected
    assert (
        criteria_fingerprint([{"id": "AC-01", "text": "uno"}, {"id": "AC-02", "text": "dos"}])
        == criteria_fingerprint([Criterion("AC-01", "uno"), Criterion("AC-02", "dos")])
        == criteria_fingerprint([{"ac_id": "AC-01", "text": "uno"}, {"ac_id": "AC-02", "text": "dos"}])
    )


def test_ac03_snapshot_normalizes_text_and_treats_a_missing_text_as_empty():
    """contract: AC-03.pre1, AC-03.pre2, AC-03.post1
    undefined: qué pasa con un criterio sin texto.
    """
    snapshot = criteria_snapshot(
        [{"id": "AC-01", "text": "  dos   espacios\ty\nsaltos "}, {"id": "AC-02"}, {"id": "AC-03", "text": None}]
    )

    assert snapshot == [
        {"id": "AC-01", "text": "dos espacios y saltos"},
        {"id": "AC-02", "text": ""},
        {"id": "AC-03", "text": ""},
    ]
    # Rellenar un criterio que estaba vacío cambia la huella: la UC deja de estar aprobada.
    empty = [{"id": "AC-01", "text": ""}]
    filled = [{"id": "AC-01", "text": "ya tiene texto"}]
    assert criteria_fingerprint(empty) != criteria_fingerprint(filled)
    assert approval_state({"fingerprint": criteria_fingerprint(empty)}, criteria_fingerprint(filled))["state"] == "stale"


# --------------------------------------------------------------------------------------------
# AC-06 · las UC anteriores a la regla cuentan como aprobadas «por migración»
# --------------------------------------------------------------------------------------------


def test_ac06_predating_uc_without_approval_is_migration():
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1"""
    state = approval_state(None, criteria_fingerprint(criteria()), predates=True)

    assert state["state"] == "migration"


def test_ac06_migration_state_carries_the_label_and_source():
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1, AC-06.post2"""
    state = approval_state(None, criteria_fingerprint(criteria()), predates=True)

    assert state["state"] == "migration"
    assert state["label"] == "aprobada por migración"
    assert state["label"] == MIGRATION_LABEL
    assert state["source"] == "migration"


def test_ac06_migration_state_counts_as_approved():
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1, AC-06.post3"""
    state = approval_state(None, criteria_fingerprint(criteria()), predates=True)

    assert state["state"] == "migration"
    assert is_approved(state) is True


def test_ac06_the_same_uc_not_predating_the_rule_is_not_approved():
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1, AC-06.post3
    undefined: contraste: sin la marca de anterior a la regla, la misma UC no cuenta como aprobada.
    """
    fp = criteria_fingerprint(criteria())

    assert approval_state(None, fp, predates=False) == {"state": "none"}
    assert approval_state(None, fp) == {"state": "none"}
    assert is_approved(approval_state(None, fp)) is False
    assert approval_state(None, fp, predates=True)["state"] == "migration"


def test_ac06_migration_state_has_no_who_or_when():
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1, AC-06.post2
    undefined: si el estado «migration» trae quién o cuándo.
    """
    state = approval_state(None, criteria_fingerprint(criteria()), predates=True)

    assert set(state) == {"state", "source", "label"}
    for key in ("by", "at", "previous_by", "previous_at", "reason"):
        assert key not in state


def test_ac06_predating_uc_with_an_approval_of_changed_criteria_is_still_migration():
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1, AC-06.post3
    undefined: si una UC anterior a la regla con una aprobación guardada de criterios que cambiaron sigue contando como aprobada por migración.
    """
    acs = criteria()
    saved = approval(acs)
    fp_changed = criteria_fingerprint(_rewritten(acs))

    state = approval_state(saved, fp_changed, predates=True)

    assert state == {"state": "migration", "source": "migration", "label": MIGRATION_LABEL}
    assert is_approved(state) is True
    # La misma aprobación sin la marca de anterior a la regla deja la UC en «stale».
    assert approval_state(saved, fp_changed, predates=False)["state"] == "stale"


@pytest.mark.parametrize("saved", ["not-a-dict", {}, {"fingerprint": ""}], ids=["string", "empty", "empty-fingerprint"])
def test_ac06_predating_uc_with_an_unusable_saved_approval_is_migration(saved):
    """contract: AC-06.pre1, AC-06.pre2, AC-06.post1, AC-06.post3
    undefined: qué estado tiene una UC anterior a la regla cuya aprobación guardada no sirve.
    """
    state = approval_state(saved, criteria_fingerprint(criteria()), predates=True)

    assert state["state"] == "migration"
    assert is_approved(state) is True


def test_ac06_predating_uc_with_a_matching_approval_is_approved_not_migration():
    """contract: AC-06.pre1, AC-06.post3
    undefined: qué estado tiene una UC anterior a la regla cuya aprobación sí coincide con sus criterios de ahora.
    """
    acs = criteria()
    saved = approval(acs)

    state = approval_state(saved, criteria_fingerprint(acs), predates=True)

    assert state == {"state": "approved", "by": WHO, "at": WHEN}
    assert "label" not in state
    assert is_approved(state) is True
