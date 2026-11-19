"""Pruebas de aceptación de UC-12603 «Un cambio que toca una UC cerrada se avisa».

Criterios vigentes:

- AC-01: El tablero guarda, para cada UC cerrada, los ficheros que cambió su PR.
- AC-02: Un cambio posterior en uno de esos ficheros, desde otra UC o sin UC, aparece en el informe de la
  puerta de desviación con la UC cerrada que toca.
- AC-03: El aviso muestra la propuesta de revisar los criterios de esa UC, y la spec queda igual hasta que
  una persona decide cambiarla.
- AC-04: Las UC cerradas antes de la medida quedan sin avisos hasta tener su lista de ficheros.

Solo se prueba lo que depende de ``server.closed_files`` (puro: sin base de datos, red ni disco).
"""

from __future__ import annotations

import copy

import pytest

from server.closed_files import (
    CLOSED_WITHOUT_FILES_NOTICE,
    MAX_CLOSED_FILES,
    MAX_CLOSED_PATH,
    MAX_TOUCHES,
    NO_FILES_AT_CLOSE_NOTICE,
    ClosedFilesError,
    ClosedUc,
    closed_uc_touches,
    files_for,
    merge_closed_files,
    normalize_closed_files,
    normalize_path,
    proposal,
)


def make_uc(
    uc_id: str = "UC-100",
    files: list[str] | None = None,
    *,
    us_id: str = "US-10",
    name: str = "Alta de usuarios",
    closed_at: str | None = "2026-11-01T10:00:00+00:00",
    by_repo: dict[str, list[str]] | None = None,
    satellite: str | None = None,
) -> ClosedUc:
    return ClosedUc(
        uc_id=uc_id,
        us_id=us_id,
        name=name,
        files=files,
        closed_at=closed_at,
        by_repo=by_repo,
        satellite=satellite,
    )


# ---------------------------------------------------------------------------
# AC-01 · El tablero guarda, para cada UC cerrada, los ficheros que cambió su PR
# ---------------------------------------------------------------------------


def test_ac01_normalize_keeps_pr_files_relative_without_repeats_and_in_order():
    """AC-01: la lista que se guarda es la de la PR, en su orden, sin repetidos y con la forma canónica."""
    raw = ["./server\\closed_files.py", "tests/test_a.py", "server/closed_files.py", "  docs/readme.md  ", ""]
    assert normalize_closed_files(raw) == ["server/closed_files.py", "tests/test_a.py", "docs/readme.md"]


def test_ac01_normalize_path_forms():
    """AC-01: ``./server\\x.py`` se guarda como ``server/x.py`` (así se comparan después)."""
    assert normalize_path("./server\\x.py") == "server/x.py"
    assert normalize_path("././a/b.py") == "a/b.py"
    assert normalize_path("  a/b.py ") == "a/b.py"


def test_ac01_no_files_means_empty_list_and_empty_list_stays_empty():
    """AC-01: sin ficheros (None o lista vacía) no se inventa ninguno."""
    assert normalize_closed_files(None) == []
    assert normalize_closed_files([]) == []
    assert normalize_closed_files(["", "  "]) == []


@pytest.mark.parametrize(
    "raw",
    [
        ["/etc/passwd"],
        ["../fuera.py"],
        ["a/../b.py"],
        ["a\nb.py"],
        ["a\rb.py"],
        "server/x.py",
        ["server/x.py", 3],
        {"server/x.py": 1},
    ],
)
def test_ac01_invalid_lists_are_rejected_so_nothing_wrong_is_stored(raw):
    """AC-01: una lista que no son rutas relativas al repositorio no se guarda."""
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(raw)


def test_ac01_path_length_boundary_is_300_characters():
    """AC-01: una ruta de 300 caracteres cabe; una de 301 no."""
    assert MAX_CLOSED_PATH == 300
    ok = "a" * 300
    assert normalize_closed_files([ok]) == [ok]
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(["a" * 301])


def test_ac01_merge_with_nothing_stored_keeps_exactly_the_pr_files():
    """AC-01: la primera vez que se cierra la UC se guardan los ficheros de su PR."""
    files = ["server/closed_files.py", "tests/test_closed_files.py"]
    stored, truncated = merge_closed_files(None, normalize_closed_files(files))
    assert stored == files
    assert truncated is False


def test_ac01_reclosing_adds_the_new_pr_files_to_the_stored_ones():
    """AC-01: si la UC se reabre y se vuelve a cerrar, suma los ficheros de su PR nueva sin repetir."""
    stored, truncated = merge_closed_files(["a.py", "b.py"], ["b.py", "c.py"])
    assert stored == ["a.py", "b.py", "c.py"]
    assert truncated is False


def test_ac01_merge_ignores_junk_in_what_was_stored():
    """AC-01: lo ya guardado que no sea ruta (None, números) o no sea lista no rompe el cierre."""
    assert merge_closed_files(["a.py", None, 7, "", "a.py"], ["b.py"]) == (["a.py", "b.py"], False)
    assert merge_closed_files("a.py", ["b.py"]) == (["b.py"], False)


def test_ac01_a_pr_over_the_cap_still_closes_and_keeps_the_most_recent_files():
    """AC-01: una PR de más de 1000 ficheros cierra igual: se guardan las 1000 más recientes y se avisa."""
    assert MAX_CLOSED_FILES == 1000
    raw = [f"src/f{i:04d}.py" for i in range(1500)]
    normalized = normalize_closed_files(raw)
    assert len(normalized) == 1500  # normalizar no recorta: el tope se aplica al guardar
    stored, truncated = merge_closed_files(None, normalized)
    assert truncated is True
    assert len(stored) == 1000
    assert stored[0] == "src/f0500.py"
    assert stored[-1] == "src/f1499.py"


def test_ac01_cap_boundary_exactly_1000_is_not_truncated_1001_is():
    """AC-01: justo 1000 rutas no se recortan; con 1001 se pierde la más antigua."""
    exactly = [f"p{i}.py" for i in range(1000)]
    stored, truncated = merge_closed_files(None, exactly)
    assert (len(stored), truncated) == (1000, False)

    stored, truncated = merge_closed_files(exactly, ["nuevo.py"])
    assert truncated is True
    assert len(stored) == 1000
    assert "p0.py" not in stored
    assert stored[-1] == "nuevo.py"


def test_ac01_stored_files_by_repo_are_kept_per_repository():
    """AC-01: una UC con PR en dos repositorios guarda dos listas, una por repositorio."""
    uc = make_uc(
        files=["server/a.py", "web/b.ts"],
        by_repo={"EmbedBuild/specbox-engine": ["server/a.py"], "EmbedBuild/specbox_cloud": ["web/b.ts"]},
    )
    assert uc.by_repo["EmbedBuild/specbox-engine"] == ["server/a.py"]
    assert uc.by_repo["EmbedBuild/specbox_cloud"] == ["web/b.ts"]
    assert files_for(uc, "EmbedBuild/specbox-engine", None) == {"server/a.py"}
    assert files_for(uc, "EmbedBuild/specbox_cloud", None) == {"web/b.ts"}


def test_ac01_what_was_stored_at_close_is_what_the_board_reads_back_later():
    """AC-01: los ficheros guardados al cerrar son los que se leen después para esa UC."""
    stored, _ = merge_closed_files(None, normalize_closed_files(["./server/closed_files.py", "tests/t.py"]))
    uc = make_uc("UC-12603", stored)
    out = closed_uc_touches([uc], ["server/closed_files.py", "tests/t.py"])
    assert out["touches"][0]["files"] == ["server/closed_files.py", "tests/t.py"]


def test_ac01_closed_uc_record_defaults():
    """AC-01: una UC cerrada sin datos opcionales tiene su lista y nada más."""
    uc = ClosedUc(uc_id="UC-1", us_id="US-1", name="x", files=["a.py"])
    assert uc.closed_at is None
    assert uc.by_repo is None
    assert uc.satellite is None
    assert uc.extra == {}
    other = ClosedUc(uc_id="UC-2", us_id="US-1", name="y", files=["b.py"])
    uc.extra["k"] = 1
    assert other.extra == {}


# ---------------------------------------------------------------------------
# AC-02 · Un cambio posterior en un fichero de una UC cerrada aparece con la UC que toca
# ---------------------------------------------------------------------------


def test_ac02_change_without_uc_in_a_closed_file_names_the_closed_uc():
    """AC-02: un cambio sin UC en un fichero de UC-100 sale en el informe con UC-100."""
    closed = [make_uc("UC-100", ["server/a.py", "server/b.py"], us_id="US-10", name="Alta de usuarios")]
    out = closed_uc_touches(closed, ["server/a.py"])
    assert out["touches_total"] == 1
    assert len(out["touches"]) == 1
    touch = out["touches"][0]
    assert touch["uc_id"] == "UC-100"
    assert touch["us_id"] == "US-10"
    assert touch["name"] == "Alta de usuarios"
    assert touch["closed_at"] == "2026-11-01T10:00:00+00:00"
    assert touch["files"] == ["server/a.py"]
    assert out["by_path"] == {"server/a.py": ["UC-100"]}


def test_ac02_change_from_another_uc_still_names_the_closed_uc():
    """AC-02: un cambio hecho desde otra UC (UC-200, la de la rama) avisa de la cerrada UC-100."""
    closed = [make_uc("UC-100", ["server/a.py"])]
    out = closed_uc_touches(closed, ["server/a.py", "server/nuevo.py"], exclude=["UC-200"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-100"]
    assert out["touches"][0]["files"] == ["server/a.py"]
    assert out["by_path"] == {"server/a.py": ["UC-100"]}


def test_ac02_the_branch_own_uc_is_not_another_uc():
    """AC-02: los ficheros de la propia UC de la rama no cuentan como «otra UC» (en cualquier mayúscula)."""
    closed = [make_uc("UC-100", ["server/a.py"]), make_uc("UC-101", ["server/a.py"])]
    out = closed_uc_touches(closed, ["server/a.py"], exclude=["uc-100"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-101"]
    assert out["by_path"] == {"server/a.py": ["UC-101"]}
    assert out["touches_total"] == 1


def test_ac02_exclude_accepts_a_single_uc_id_as_text():
    """AC-02: ``exclude`` puede ser un texto con una sola UC."""
    closed = [make_uc("UC-100", ["server/a.py"])]
    out = closed_uc_touches(closed, ["server/a.py"], exclude="UC-100")
    assert out["touches"] == []
    assert out["touches_total"] == 0


def test_ac02_a_change_in_files_no_closed_uc_changed_reports_nothing():
    """AC-02: si el cambio no toca ficheros de UC cerradas el informe queda vacío."""
    closed = [make_uc("UC-100", ["server/a.py"])]
    out = closed_uc_touches(closed, ["docs/otra.md"])
    assert out["touches"] == []
    assert out["touches_total"] == 0
    assert out["by_path"] == {}
    assert out["closed_without_files"] == 0
    assert "notice" not in out


def test_ac02_no_changed_paths_reports_nothing():
    """AC-02: sin rutas cambiadas no hay avisos."""
    closed = [make_uc("UC-100", ["server/a.py"])]
    out = closed_uc_touches(closed, [])
    assert out["touches"] == [] and out["touches_total"] == 0 and out["by_path"] == {}


def test_ac02_changed_paths_are_compared_in_canonical_form():
    """AC-02: ``./server\\a.py`` en el cambio coincide con ``server/a.py`` guardado."""
    closed = [make_uc("UC-100", ["server/a.py"])]
    out = closed_uc_touches(closed, ["./server\\a.py", "server/a.py"])
    assert out["touches"][0]["files"] == ["server/a.py"]  # sin repetir
    assert out["by_path"] == {"server/a.py": ["UC-100"]}


def test_ac02_a_file_changed_by_two_closed_ucs_names_both():
    """AC-02: si dos UC cerradas cambiaron el mismo fichero, `by_path` las nombra a las dos."""
    closed = [make_uc("UC-100", ["server/a.py"]), make_uc("UC-101", ["server/a.py", "server/z.py"])]
    out = closed_uc_touches(closed, ["server/a.py"])
    assert out["by_path"] == {"server/a.py": ["UC-100", "UC-101"]}
    assert out["touches_total"] == 2


def test_ac02_the_uc_sharing_most_files_comes_first_then_the_most_recent():
    """AC-02: salen primero las UC que más ficheros comparten con el cambio y, a igualdad, las más recientes."""
    closed = [
        make_uc("UC-1", ["a.py"], closed_at="2026-11-10T00:00:00+00:00"),
        make_uc("UC-2", ["a.py", "b.py"], closed_at="2026-11-01T00:00:00+00:00"),
        make_uc("UC-3", ["a.py"], closed_at="2026-11-15T00:00:00+00:00"),
    ]
    out = closed_uc_touches(closed, ["a.py", "b.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-2", "UC-3", "UC-1"]
    assert out["touches"][0]["files"] == ["a.py", "b.py"]


def test_ac02_report_is_capped_at_20_touches_but_counts_all():
    """AC-02: el informe trae como mucho 20 avisos y `touches_total` cuenta todos."""
    assert MAX_TOUCHES == 20
    closed = [make_uc(f"UC-{i}", ["a.py"], closed_at=f"2026-11-{(i % 28) + 1:02d}T00:00:00+00:00") for i in range(25)]
    out = closed_uc_touches(closed, ["a.py"])
    assert len(out["touches"]) == 20
    assert out["touches_total"] == 25
    assert len(out["by_path"]["a.py"]) == 25  # el mapa ruta → UC no se recorta


def test_ac02_limit_argument_caps_the_touches():
    """AC-02: con `limit=3` el informe trae 3 avisos y el total real."""
    closed = [make_uc(f"UC-{i}", ["a.py"]) for i in range(5)]
    out = closed_uc_touches(closed, ["a.py"], limit=3)
    assert len(out["touches"]) == 3
    assert out["touches_total"] == 5


def test_ac02_a_closed_uc_of_another_repository_does_not_count():
    """AC-02: una UC cerrada con la misma ruta en otro repositorio no avisa de un cambio en este."""
    uc = make_uc(
        "UC-300",
        ["src/app.ts"],
        by_repo={"EmbedBuild/specbox_cloud": ["src/app.ts"]},
    )
    assert closed_uc_touches([uc], ["src/app.ts"], repo="EmbedBuild/specbox-engine")["touches"] == []
    out = closed_uc_touches([uc], ["src/app.ts"], repo="EmbedBuild/specbox_cloud")
    assert [t["uc_id"] for t in out["touches"]] == ["UC-300"]


def test_ac02_repository_name_is_compared_ignoring_case():
    """AC-02: `EmbedBuild/Specbox_Cloud` y `embedbuild/specbox_cloud` son el mismo repositorio."""
    uc = make_uc("UC-300", ["src/app.ts"], by_repo={"EmbedBuild/specbox_cloud": ["src/app.ts"]})
    out = closed_uc_touches([uc], ["src/app.ts"], repo="embedbuild/SPECBOX_CLOUD")
    assert out["touches_total"] == 1


def test_ac02_paths_stored_without_repository_count_for_any_repository():
    """AC-02: las rutas guardadas sin repositorio cuentan aunque la UC tenga lista por repositorio."""
    uc = make_uc(
        "UC-301",
        ["old/legacy.py", "src/app.ts"],
        by_repo={"EmbedBuild/specbox_cloud": ["src/app.ts"]},
    )
    out = closed_uc_touches([uc], ["old/legacy.py"], repo="EmbedBuild/specbox-engine")
    assert [t["uc_id"] for t in out["touches"]] == ["UC-301"]
    assert files_for(uc, "EmbedBuild/specbox-engine", None) == {"old/legacy.py"}


def test_ac02_a_closed_uc_of_another_satellite_does_not_count():
    """AC-02: sin lista por repositorio, una UC de otro satélite no avisa; del mismo (sin mirar mayúsculas), sí."""
    uc = make_uc("UC-400", ["a.py"], satellite="engine")
    assert closed_uc_touches([uc], ["a.py"], satellite="cloud")["touches"] == []
    assert closed_uc_touches([uc], ["a.py"], satellite="ENGINE")["touches_total"] == 1


def test_ac02_without_repository_or_satellite_every_stored_file_counts():
    """AC-02: sin repositorio ni satélite en el cambio, cuentan todos los ficheros de la UC."""
    uc = make_uc(
        "UC-401",
        ["a.py", "b.py"],
        satellite="engine",
        by_repo={"EmbedBuild/specbox-engine": ["a.py"], "EmbedBuild/specbox_cloud": ["b.py"]},
    )
    assert files_for(uc, None, None) == {"a.py", "b.py"}
    out = closed_uc_touches([uc], ["a.py", "b.py"])
    assert out["touches"][0]["files"] == ["a.py", "b.py"]


# ---------------------------------------------------------------------------
# AC-03 · El aviso propone revisar los criterios y la spec queda igual
# ---------------------------------------------------------------------------


def test_ac03_touch_carries_the_proposal_to_review_the_criteria():
    """AC-03: cada aviso trae la propuesta de revisar los criterios de la UC cerrada que toca."""
    closed = [make_uc("UC-100", ["server/a.py"], name="Alta de usuarios")]
    touch = closed_uc_touches(closed, ["server/a.py"])["touches"][0]
    text = touch["proposal"]
    assert "UC-100" in text
    assert "«Alta de usuarios»" in text
    assert "`server/a.py`" in text
    assert "revisa si sus criterios siguen valiendo" in text
    assert text == proposal("UC-100", "Alta de usuarios", ["server/a.py"])


def test_ac03_proposal_exact_text_for_one_file():
    """AC-03: el texto de la propuesta, completo, para un fichero y un nombre."""
    assert proposal("UC-100", "Alta de usuarios", ["server/a.py"]) == (
        "Este cambio toca `server/a.py`, de UC-100 («Alta de usuarios»), ya cerrada: revisa si sus criterios "
        "siguen valiendo. La spec no cambia sola: si hay que cambiarla, lo decide una persona (update_ac, "
        "add_ac o delete_ac)."
    )


def test_ac03_proposal_leaves_the_decision_to_a_person_and_does_not_change_the_spec():
    """AC-03: la propuesta dice que la spec no cambia sola y que lo decide una persona."""
    text = proposal("UC-7", "x", ["a.py"])
    assert "La spec no cambia sola" in text
    assert "lo decide una persona" in text
    for tool in ("update_ac", "add_ac", "delete_ac"):
        assert tool in text


def test_ac03_proposal_lists_five_files_and_counts_the_rest():
    """AC-03: con 7 ficheros la propuesta enseña 5 y dice «y 2 más»; con 5 no añade nada."""
    seven = [f"f{i}.py" for i in range(7)]
    text = proposal("UC-9", "Grande", seven)
    for f in seven[:5]:
        assert f"`{f}`" in text
    assert "`f5.py`" not in text and "`f6.py`" not in text
    assert "y 2 más" in text

    five = proposal("UC-9", "Grande", seven[:5])
    assert " más" not in five.split("ya cerrada")[0]


def test_ac03_proposal_without_a_name_has_no_title_brackets():
    """AC-03: una UC sin nombre no deja «» vacíos en la propuesta."""
    text = proposal("UC-9", "", ["a.py"])
    assert "«" not in text and "»" not in text
    assert "de UC-9, ya cerrada" in text


def test_ac03_touch_only_informs_it_has_no_fields_that_change_the_spec():
    """AC-03: el aviso es informativo: solo trae UC, historia, nombre, cierre, ficheros y propuesta."""
    closed = [make_uc("UC-100", ["server/a.py"])]
    touch = closed_uc_touches(closed, ["server/a.py"])["touches"][0]
    assert set(touch) == {"uc_id", "us_id", "name", "closed_at", "files", "proposal"}
    out = closed_uc_touches(closed, ["server/a.py"])
    assert set(out) == {"touches", "touches_total", "by_path", "closed_without_files"}


def test_ac03_the_closed_ucs_and_their_criteria_stay_the_same_after_the_warning():
    """AC-03: la UC cerrada (su lista, su nombre, sus datos) queda igual tras avisar: el engine no cambia la spec."""
    closed = [
        make_uc("UC-100", ["server/a.py", "server/b.py"], by_repo={"o/r": ["server/a.py"]}, satellite="engine"),
        make_uc("UC-101", None),
        make_uc("UC-102", ["x.py"]),
    ]
    before = copy.deepcopy(closed)
    paths = ["server/a.py", "x.py"]
    paths_before = list(paths)
    closed_uc_touches(closed, paths, exclude=["UC-102"], repo="o/r", satellite="engine")
    closed_uc_touches(closed, paths)
    assert closed == before
    assert paths == paths_before


def test_ac03_editing_the_report_does_not_edit_the_stored_ucs():
    """AC-03: el informe es una copia: tocar sus listas no cambia los ficheros guardados de la UC."""
    uc = make_uc("UC-100", ["server/a.py", "server/b.py"])
    out = closed_uc_touches([uc], ["server/a.py"])
    out["touches"][0]["files"].append("inventado.py")
    out["by_path"]["server/a.py"].append("UC-999")
    assert uc.files == ["server/a.py", "server/b.py"]


# ---------------------------------------------------------------------------
# AC-04 · Las UC cerradas antes de la medida no avisan hasta tener su lista de ficheros
# ---------------------------------------------------------------------------


def test_ac04_a_closed_uc_without_list_does_not_warn_and_is_counted():
    """AC-04: una UC cerrada sin lista de ficheros no avisa y se cuenta en `closed_without_files`."""
    old = make_uc("UC-050", None)
    out = closed_uc_touches([old], ["server/a.py"])
    assert out["touches"] == []
    assert out["touches_total"] == 0
    assert out["by_path"] == {}
    assert out["closed_without_files"] == 1


def test_ac04_the_report_says_how_many_closed_ucs_have_no_list():
    """AC-04: el informe lleva un `notice` con cuántas UC cerradas no tienen lista y cómo darles una."""
    out = closed_uc_touches([make_uc("UC-050", None), make_uc("UC-051", None)], ["a.py"])
    assert out["closed_without_files"] == 2
    assert out["notice"] == CLOSED_WITHOUT_FILES_NOTICE.format(n=2)
    assert out["notice"].startswith("2 UC cerradas no tienen su lista de ficheros")
    assert "no avisan hasta que la tengan" in out["notice"]
    assert "complete_uc con `files`" in out["notice"]


def test_ac04_old_closes_do_not_hide_the_warnings_of_ucs_that_do_have_a_list():
    """AC-04: junto a UC antiguas sin lista, la UC con lista sí avisa."""
    closed = [make_uc("UC-050", None), make_uc("UC-100", ["server/a.py"]), make_uc("UC-051", None)]
    out = closed_uc_touches(closed, ["server/a.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-100"]
    assert out["touches_total"] == 1
    assert out["closed_without_files"] == 2
    assert "2 UC cerradas" in out["notice"]


def test_ac04_a_uc_without_list_warns_once_it_gets_its_list():
    """AC-04: la misma UC no avisa sin lista y empieza a avisar cuando se cierra con `files`."""
    before = make_uc("UC-050", None)
    assert closed_uc_touches([before], ["server/a.py"])["touches"] == []

    stored, _ = merge_closed_files(None, normalize_closed_files(["server/a.py"]))
    after = make_uc("UC-050", stored)
    out = closed_uc_touches([after], ["server/a.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-050"]
    assert out["closed_without_files"] == 0
    assert "notice" not in out


def test_ac04_a_uc_with_an_empty_list_has_its_list_and_is_not_counted_as_missing():
    """AC-04: una lista vacía es una lista: no se cuenta como «sin lista» ni avisa de nada."""
    out = closed_uc_touches([make_uc("UC-060", [])], ["server/a.py"])
    assert out["touches"] == []
    assert out["closed_without_files"] == 0
    assert "notice" not in out


def test_ac04_with_no_closed_ucs_there_is_no_notice():
    """AC-04: sin UC cerradas sin lista el informe no lleva `notice`."""
    out = closed_uc_touches([], ["a.py"])
    assert out == {"touches": [], "touches_total": 0, "by_path": {}, "closed_without_files": 0}


def test_ac04_closing_without_files_warns_that_later_changes_will_not_be_noticed():
    """AC-04: al cerrar sin `files` se avisa de que un cambio posterior en sus ficheros no avisará."""
    assert "La UC se cerró sin `files`" in NO_FILES_AT_CLOSE_NOTICE
    assert "no avisará" in NO_FILES_AT_CLOSE_NOTICE
    assert "complete_uc" in NO_FILES_AT_CLOSE_NOTICE
