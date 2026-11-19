"""Pruebas de aceptacion de UC-12603 (E3 · Un cambio que toca una UC cerrada se avisa).

Generadas desde ``contract.json`` (misma carpeta) contra las funciones publicas de
``server/closed_files.py``. Sin base de datos, red ni disco.

Alcance: el modulo solo normaliza y combina las listas de ficheros de un cierre
(AC-01) y calcula, para unas rutas cambiadas, que UC cerradas toca el cambio (AC-02,
AC-03, AC-04). El guardado en el tablero (backends) y la puerta de desviacion que
muestra el informe no dependen de este modulo y quedan fuera.
"""

from __future__ import annotations

import copy

import pytest

from server.closed_files import (
    CLOSED_WITHOUT_FILES_NOTICE,
    MAX_CLOSED_FILES,
    MAX_CLOSED_PATH,
    MAX_TOUCHES,
    ClosedFilesError,
    ClosedUc,
    closed_uc_touches,
    merge_closed_files,
    normalize_closed_files,
    normalize_path,
    proposal,
)


def _uc(
    uc_id: str,
    files: list[str] | None,
    *,
    us_id: str = "US-126",
    name: str = "",
    closed_at: str | None = None,
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
# AC-01: el tablero guarda, para cada UC cerrada, los ficheros que cambio su PR
# ---------------------------------------------------------------------------


def test_ac01_close_list_is_stored_normalized_without_empties_or_repeats_in_order():
    """contract: AC-01.pre1, AC-01.post1"""
    raw = [
        "./server\\x.py",
        "tests/test_x.py",
        "  server/x.py  ",  # la misma que la primera, ya normalizada
        "",  # vacia
        "   ",  # solo espacios
        "././docs/a.md",
        "docs\\b.md",
        "tests/test_x.py",  # repetida
    ]
    assert normalize_closed_files(raw) == [
        "server/x.py",
        "tests/test_x.py",
        "docs/a.md",
        "docs/b.md",
    ]


def test_ac01_each_normalized_path_has_the_stored_form():
    """contract: AC-01.pre1, AC-01.post1"""
    assert normalize_path("./server\\x.py") == "server/x.py"
    assert normalize_path("  ./a/b.py ") == "a/b.py"
    # lo que se guarda es lo mismo que lo que se compara despues
    assert normalize_closed_files(["./server\\x.py"]) == [normalize_path("./server\\x.py")]


def test_ac01_reclosing_keeps_the_previous_files_and_adds_the_new_ones():
    """contract: AC-01.pre2, AC-01.post2"""
    merged, truncated = merge_closed_files(["server/a.py", "server/b.py"], ["tests/c.py", "docs/d.md"])
    assert merged == ["server/a.py", "server/b.py", "tests/c.py", "docs/d.md"]
    assert truncated is False


def test_ac01_a_path_in_both_lists_is_stored_once():
    """contract: AC-01.pre2, AC-01.post2"""
    merged, truncated = merge_closed_files(["server/a.py", "server/b.py"], ["server/b.py", "tests/c.py"])
    assert sorted(merged) == ["server/a.py", "server/b.py", "tests/c.py"]
    assert len(merged) == len(set(merged))
    assert truncated is False


def test_ac01_first_close_stores_exactly_the_new_files():
    """contract: AC-01.pre1, AC-01.post2"""
    merged, truncated = merge_closed_files(None, ["server/a.py", "server/b.py"])
    assert merged == ["server/a.py", "server/b.py"]
    assert truncated is False


def test_ac01_over_the_cap_the_most_recent_are_kept_and_truncation_is_reported():
    """contract: AC-01.pre3, AC-01.post3"""
    assert MAX_CLOSED_FILES == 1000
    old = [f"old/{i}.py" for i in range(MAX_CLOSED_FILES)]
    new = ["new/a.py", "new/b.py"]
    merged, truncated = merge_closed_files(old, new)
    assert truncated is True
    assert len(merged) == MAX_CLOSED_FILES
    assert merged[-2:] == new  # lo mas reciente se queda
    assert "old/0.py" not in merged and "old/1.py" not in merged  # lo mas antiguo se pierde
    assert merged[0] == "old/2.py"


def test_ac01_exactly_at_the_cap_is_not_truncated():
    """contract: AC-01.pre3, AC-01.post3"""
    old = [f"old/{i}.py" for i in range(MAX_CLOSED_FILES - 2)]
    merged, truncated = merge_closed_files(old, ["new/a.py", "new/b.py"])
    assert len(merged) == MAX_CLOSED_FILES
    assert truncated is False
    assert merged[:2] == ["old/0.py", "old/1.py"]


def test_ac01_a_pr_over_the_cap_alone_keeps_the_most_recent_and_reports_it():
    """contract: AC-01.pre3, AC-01.post3"""
    new = [f"pr/{i}.py" for i in range(MAX_CLOSED_FILES + 50)]
    # la normalizacion no recorta: el tope se aplica al guardar
    assert normalize_closed_files(new) == new
    merged, truncated = merge_closed_files(None, new)
    assert truncated is True
    assert merged == new[-MAX_CLOSED_FILES:]


def test_ac01_undefined_close_without_list_stores_an_empty_list():
    """contract: AC-01.pre1, AC-01.post1"""
    assert normalize_closed_files(None) == []
    assert normalize_closed_files([]) == []
    assert normalize_closed_files(["", "  ", "./"]) == []


@pytest.mark.parametrize(
    "raw",
    [
        "server/x.py",  # un texto, no una lista
        ("server/x.py",),  # una tupla
        {"server/x.py": 1},
        ["server/x.py", 3],
        ["server/x.py", None],
        [["server/x.py"]],
    ],
)
def test_ac01_undefined_a_list_that_is_not_a_list_of_texts_is_rejected(raw):
    """contract: AC-01.pre1, AC-01.post1"""
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(raw)


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "/server/x.py",
        "../server/x.py",
        "server/../x.py",
        "server/..",
        "..\\server\\x.py",
        "server/a\nb.py",
        "server/a\rb.py",
        "x" * (MAX_CLOSED_PATH + 1),
    ],
)
def test_ac01_undefined_absolute_parent_newline_or_too_long_paths_are_rejected(path):
    """contract: AC-01.pre1, AC-01.post1"""
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(["server/ok.py", path])


def test_ac01_undefined_a_valid_odd_path_is_accepted():
    """contract: AC-01.pre1, AC-01.post1"""
    limit_path = "x" * MAX_CLOSED_PATH
    assert normalize_closed_files([limit_path]) == [limit_path]  # justo en el limite
    assert normalize_closed_files(["a..b/c.py", "..hidden/x.py", "dir/.env"]) == ["a..b/c.py", "..hidden/x.py", "dir/.env"]
    assert normalize_closed_files(["server/a.py\n", "\tserver/b.py"]) == ["server/a.py", "server/b.py"]  # los extremos se recortan


def test_ac01_undefined_paths_that_differ_only_in_case_are_different():
    """contract: AC-01.pre1, AC-01.post1"""
    assert normalize_closed_files(["Server/X.py", "server/x.py"]) == ["Server/X.py", "server/x.py"]


def test_ac01_undefined_what_was_already_stored_is_normalized_and_non_texts_are_ignored():
    """contract: AC-01.pre2, AC-01.post2"""
    stored = ["./server\\a.py", None, 7, "", "server/b.py", "server/b.py"]
    merged, truncated = merge_closed_files(stored, ["tests/c.py"])
    assert merged == ["server/a.py", "server/b.py", "tests/c.py"]
    assert truncated is False
    # algo guardado que no es una lista cuenta como nada guardado
    assert merge_closed_files("server/a.py", ["tests/c.py"]) == (["tests/c.py"], False)
    assert merge_closed_files({"a": 1}, ["tests/c.py"]) == (["tests/c.py"], False)
    assert merge_closed_files([], []) == ([], False)


def test_ac01_undefined_a_repeated_path_moves_to_the_position_of_the_new_files():
    """contract: AC-01.pre2, AC-01.post2"""
    merged, _ = merge_closed_files(["a.py", "b.py", "c.py"], ["b.py"])
    assert merged == ["a.py", "c.py", "b.py"]


# ---------------------------------------------------------------------------
# AC-02: un cambio posterior en esos ficheros aparece con la UC cerrada que toca
# ---------------------------------------------------------------------------


def _closed_board() -> list[ClosedUc]:
    return [
        _uc("UC-100", ["server/x.py", "server/y.py", "docs/z.md"], us_id="US-10", name="Primera", closed_at="2026-11-01T10:00:00Z"),
        _uc("UC-200", ["docs/only.md"], us_id="US-20", name="Segunda", closed_at="2026-11-02T10:00:00Z"),
    ]


def test_ac02_a_change_in_a_closed_uc_file_names_that_uc():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2, AC-02.post3"""
    out = closed_uc_touches(_closed_board(), ["server/x.py", "src/unrelated.py"])
    assert out["touches_total"] == 1
    assert len(out["touches"]) == 1
    touch = out["touches"][0]
    assert touch["uc_id"] == "UC-100"
    assert touch["us_id"] == "US-10"
    assert touch["name"] == "Primera"
    assert touch["closed_at"] == "2026-11-01T10:00:00Z"
    # solo los ficheros que toca el cambio, no todos los de la UC
    assert touch["files"] == ["server/x.py"]
    assert out["by_path"] == {"server/x.py": ["UC-100"]}


@pytest.mark.parametrize("exclude", [None, [], "UC-999", ["UC-999", "UC-998"]])
def test_ac02_the_change_from_no_uc_or_from_another_uc_reports_the_closed_uc(exclude):
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3"""
    out = closed_uc_touches(_closed_board(), ["docs/z.md"], exclude)
    assert out["touches_total"] == 1
    assert [t["uc_id"] for t in out["touches"]] == ["UC-100"]
    assert out["touches"][0]["files"] == ["docs/z.md"]


def test_ac02_the_report_lists_only_the_files_the_change_touches_for_each_uc():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2, AC-02.post3"""
    out = closed_uc_touches(_closed_board(), ["server/x.py", "server/y.py", "docs/only.md"])
    by_uc = {t["uc_id"]: t["files"] for t in out["touches"]}
    assert by_uc == {"UC-100": ["server/x.py", "server/y.py"], "UC-200": ["docs/only.md"]}
    assert out["touches_total"] == 2
    assert out["by_path"] == {
        "server/x.py": ["UC-100"],
        "server/y.py": ["UC-100"],
        "docs/only.md": ["UC-200"],
    }


def test_ac02_a_path_touched_by_two_closed_ucs_names_both():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2, AC-02.post3"""
    closed = [_uc("UC-1", ["shared.py", "a.py"]), _uc("UC-2", ["shared.py"]), _uc("UC-3", ["c.py"])]
    out = closed_uc_touches(closed, ["shared.py"])
    assert out["by_path"] == {"shared.py": ["UC-1", "UC-2"]}
    assert out["touches_total"] == 2
    assert {t["uc_id"] for t in out["touches"]} == {"UC-1", "UC-2"}


def test_ac02_a_change_that_touches_none_of_the_files_reports_nothing():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post4"""
    out = closed_uc_touches(_closed_board(), ["src/new_file.py", "README.md"])
    assert out["touches"] == []
    assert out["touches_total"] == 0
    assert out["by_path"] == {}


def test_ac02_a_uc_with_no_common_file_is_not_counted():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post3, AC-02.post4"""
    out = closed_uc_touches(_closed_board(), ["docs/only.md"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-200"]
    assert out["touches_total"] == 1


@pytest.mark.parametrize("exclude", [["UC-100"], ["uc-100"], "UC-100", "uc-100", ["Uc-100", "UC-555"]])
def test_ac02_the_ucs_of_the_branch_are_not_reported_as_another_closed_uc(exclude):
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post5"""
    out = closed_uc_touches(_closed_board(), ["server/x.py", "docs/only.md"], exclude)
    assert [t["uc_id"] for t in out["touches"]] == ["UC-200"]
    assert out["touches_total"] == 1
    assert out["by_path"] == {"docs/only.md": ["UC-200"]}


def test_ac02_undefined_the_uc_that_shares_more_files_comes_first_then_the_most_recent():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3"""
    closed = [
        _uc("UC-OLD1", ["a.py"], closed_at="2026-01-01T00:00:00Z"),
        _uc("UC-TWO", ["a.py", "b.py"], closed_at="2026-02-01T00:00:00Z"),
        _uc("UC-NEW1", ["a.py"], closed_at="2026-03-01T00:00:00Z"),
    ]
    out = closed_uc_touches(closed, ["a.py", "b.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-TWO", "UC-NEW1", "UC-OLD1"]


def test_ac02_undefined_a_uc_closed_without_date_goes_after_the_dated_ones_with_the_same_count():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1"""
    closed = [_uc("UC-NODATE", ["a.py"], closed_at=None), _uc("UC-DATED", ["a.py"], closed_at="2026-01-01T00:00:00Z")]
    out = closed_uc_touches(closed, ["a.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-DATED", "UC-NODATE"]
    assert out["touches"][1]["closed_at"] is None


def test_ac02_undefined_the_report_shows_up_to_the_limit_and_the_total_counts_all():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3"""
    assert MAX_TOUCHES == 20
    closed = [_uc(f"UC-{i:03d}", ["hot.py"], closed_at=f"2026-01-{(i % 28) + 1:02d}T00:00:00Z") for i in range(MAX_TOUCHES + 5)]
    out = closed_uc_touches(closed, ["hot.py"])
    assert len(out["touches"]) == MAX_TOUCHES
    assert out["touches_total"] == MAX_TOUCHES + 5
    assert len(out["by_path"]["hot.py"]) == MAX_TOUCHES + 5  # by_path no se recorta
    small = closed_uc_touches(closed, ["hot.py"], limit=3)
    assert len(small["touches"]) == 3
    assert small["touches_total"] == MAX_TOUCHES + 5


def test_ac02_undefined_changed_paths_are_normalized_counted_once_and_non_texts_ignored():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    closed = [_uc("UC-1", ["server/x.py", "docs/a.md"])]
    out = closed_uc_touches(closed, ["./server\\x.py", "server/x.py", None, 3, "", "  docs/a.md  "])  # type: ignore[list-item]
    assert out["touches"][0]["files"] == ["server/x.py", "docs/a.md"]
    assert out["by_path"] == {"server/x.py": ["UC-1"], "docs/a.md": ["UC-1"]}
    assert out["touches_total"] == 1


def test_ac02_undefined_without_changed_paths_or_closed_ucs_there_is_nothing_to_report():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post4"""
    assert closed_uc_touches(_closed_board(), [])["touches"] == []
    empty = closed_uc_touches([], ["a.py"])
    assert empty["touches"] == [] and empty["touches_total"] == 0 and empty["by_path"] == {}
    assert empty["closed_without_files"] == 0


def test_ac02_undefined_a_closed_uc_of_another_repository_is_not_reported():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post4"""
    closed = [_uc("UC-1", ["server/x.py", "server/y.py"], by_repo={"acme/engine": ["server/x.py"], "acme/cloud": ["server/y.py"]})]
    in_engine = closed_uc_touches(closed, ["server/x.py", "server/y.py"], repo="acme/engine")
    assert in_engine["touches"][0]["files"] == ["server/x.py"]
    in_cloud = closed_uc_touches(closed, ["server/x.py", "server/y.py"], repo="ACME/Cloud")  # sin distinguir mayusculas
    assert in_cloud["touches"][0]["files"] == ["server/y.py"]
    elsewhere = closed_uc_touches(closed, ["server/x.py", "server/y.py"], repo="acme/other")
    assert elsewhere["touches"] == [] and elsewhere["touches_total"] == 0
    # sin repo en el cambio, cuentan todas las rutas de la UC
    anywhere = closed_uc_touches(closed, ["server/x.py", "server/y.py"])
    assert anywhere["touches"][0]["files"] == ["server/x.py", "server/y.py"]


def test_ac02_undefined_paths_saved_without_repository_count_unless_the_uc_is_of_another_satellite():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post4"""
    closed = [_uc("UC-1", ["a.py", "b.py"], by_repo={"acme/engine": ["a.py"]}, satellite="engine")]
    # b.py se guardo sin repositorio: cuenta en cualquier repo
    assert closed_uc_touches(closed, ["a.py", "b.py"], repo="acme/engine")["touches"][0]["files"] == ["a.py", "b.py"]
    assert closed_uc_touches(closed, ["a.py", "b.py"], repo="acme/cloud")["touches"][0]["files"] == ["b.py"]
    # pero si la UC es de otro satelite, solo cuentan las rutas de ese repositorio
    other = closed_uc_touches(closed, ["a.py", "b.py"], repo="acme/cloud", satellite="cloud")
    assert other["touches"] == []
    same_repo_other_satellite = closed_uc_touches(closed, ["a.py", "b.py"], repo="acme/engine", satellite="cloud")
    assert same_repo_other_satellite["touches"][0]["files"] == ["a.py"]


def test_ac02_undefined_a_closed_uc_of_another_satellite_is_not_reported_without_repository_data():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post4"""
    closed = [_uc("UC-1", ["a.py"], satellite="engine")]
    assert closed_uc_touches(closed, ["a.py"], satellite="cloud")["touches"] == []
    assert closed_uc_touches(closed, ["a.py"], satellite="ENGINE")["touches_total"] == 1  # sin distinguir mayusculas
    assert closed_uc_touches(closed, ["a.py"])["touches_total"] == 1  # sin satelite en el cambio, cuenta
    unlabelled = [_uc("UC-2", ["a.py"], satellite=None)]
    assert closed_uc_touches(unlabelled, ["a.py"], satellite="cloud")["touches_total"] == 1  # UC sin satelite, cuenta


# ---------------------------------------------------------------------------
# AC-03: el aviso propone revisar los criterios y la spec queda igual
# ---------------------------------------------------------------------------


def test_ac03_the_notice_proposes_to_review_the_criteria_of_that_uc():
    """contract: AC-03.pre1, AC-03.post1"""
    closed = [_uc("UC-12603", ["server/closed_files.py"], name="E3 · Un cambio que toca una UC cerrada se avisa")]
    out = closed_uc_touches(closed, ["server/closed_files.py"])
    text = out["touches"][0]["proposal"]
    assert "UC-12603" in text
    assert "«E3 · Un cambio que toca una UC cerrada se avisa»" in text
    assert "`server/closed_files.py`" in text
    assert "revisa si sus criterios siguen valiendo" in text


def test_ac03_the_proposal_names_only_the_files_the_change_touches():
    """contract: AC-03.pre1, AC-03.post1"""
    closed = [_uc("UC-1", ["a.py", "b.py", "c.py"], name="Uno")]
    text = closed_uc_touches(closed, ["b.py"])["touches"][0]["proposal"]
    assert "`b.py`" in text
    assert "`a.py`" not in text and "`c.py`" not in text


def test_ac03_the_proposal_leaves_the_decision_to_a_person():
    """contract: AC-03.pre1, AC-03.post2"""
    closed = [_uc("UC-1", ["a.py"], name="Uno")]
    text = closed_uc_touches(closed, ["a.py"])["touches"][0]["proposal"]
    assert "La spec no cambia sola" in text
    assert "lo decide una persona" in text
    assert "(update_ac, add_ac o delete_ac)" in text


def test_ac03_the_proposal_function_gives_the_same_text_as_the_report():
    """contract: AC-03.pre1, AC-03.post1, AC-03.post2"""
    closed = [_uc("UC-7", ["a.py", "b.py"], name="Siete")]
    touch = closed_uc_touches(closed, ["a.py", "b.py"])["touches"][0]
    assert touch["proposal"] == proposal("UC-7", "Siete", ["a.py", "b.py"])
    text = proposal("UC-7", "Siete", ["a.py", "b.py"])
    assert "revisa si sus criterios siguen valiendo" in text
    assert "lo decide una persona" in text


def test_ac03_computing_the_report_does_not_change_the_closed_ucs_nor_the_inputs():
    """contract: AC-03.pre1, AC-03.post3"""
    closed = [
        _uc("UC-1", ["a.py", "b.py"], name="Uno", closed_at="2026-01-01T00:00:00Z", by_repo={"o/r": ["a.py", "b.py"]}, satellite="engine"),
        _uc("UC-2", None, name="Dos"),
        _uc("UC-3", ["a.py"], name="Tres"),
    ]
    paths = ["./a.py", "b.py", "c.py"]
    exclude = ["UC-3"]
    closed_before, paths_before, exclude_before = copy.deepcopy(closed), copy.deepcopy(paths), copy.deepcopy(exclude)

    first = closed_uc_touches(closed, paths, exclude, repo="o/r", satellite="engine")
    assert closed == closed_before
    assert paths == paths_before
    assert exclude == exclude_before
    assert closed[0].files == ["a.py", "b.py"]
    assert closed[0].by_repo == {"o/r": ["a.py", "b.py"]}

    second = closed_uc_touches(closed, paths, exclude, repo="o/r", satellite="engine")
    assert second == first  # repetir la llamada da el mismo informe


def test_ac03_the_report_is_only_data_the_proposal_is_text_not_an_action():
    """contract: AC-03.pre1, AC-03.post2, AC-03.post3"""
    closed = [_uc("UC-1", ["a.py"], name="Uno")]
    out = closed_uc_touches(closed, ["a.py"])
    assert isinstance(out["touches"][0]["proposal"], str)
    assert set(out) == {"touches", "touches_total", "by_path", "closed_without_files"}  # sin cambios de spec ni acciones
    assert set(out["touches"][0]) == {"uc_id", "us_id", "name", "closed_at", "files", "proposal"}


def test_ac03_undefined_the_proposal_lists_five_files_and_counts_the_rest():
    """contract: AC-03.pre1, AC-03.post1"""
    files = [f"f{i}.py" for i in range(7)]
    text = proposal("UC-1", "Uno", files)
    for f in files[:5]:
        assert f"`{f}`" in text
    for f in files[5:]:
        assert f"`{f}`" not in text
    assert "y 2 más" in text
    exactly_five = proposal("UC-1", "Uno", files[:5])
    assert "más" not in exactly_five.split("ya cerrada")[0]
    six = proposal("UC-1", "Uno", files[:6])
    assert "y 1 más" in six


def test_ac03_undefined_a_uc_without_name_has_no_title_in_the_proposal():
    """contract: AC-03.pre1, AC-03.post1"""
    text = proposal("UC-9", "", ["a.py"])
    assert "UC-9" in text
    assert "«" not in text and "»" not in text
    assert "revisa si sus criterios siguen valiendo" in text
    via_report = closed_uc_touches([_uc("UC-9", ["a.py"], name="")], ["a.py"])["touches"][0]["proposal"]
    assert "«" not in via_report


# ---------------------------------------------------------------------------
# AC-04: las UC cerradas sin lista de ficheros no avisan hasta tenerla
# ---------------------------------------------------------------------------


def test_ac04_a_uc_closed_without_list_does_not_warn_even_if_others_do():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1"""
    closed = [
        _uc("UC-OLD", None, name="Antigua", closed_at="2025-01-01T00:00:00Z"),
        _uc("UC-NEW", ["server/x.py"], name="Nueva", closed_at="2026-11-01T00:00:00Z"),
    ]
    out = closed_uc_touches(closed, ["server/x.py", "server/y.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-NEW"]
    assert out["touches_total"] == 1
    assert out["by_path"] == {"server/x.py": ["UC-NEW"]}
    assert all("UC-OLD" not in ids for ids in out["by_path"].values())


def test_ac04_only_uc_without_list_gives_no_warning_at_all():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1"""
    out = closed_uc_touches([_uc("UC-OLD", None)], ["anything.py", "server/x.py"])
    assert out["touches"] == []
    assert out["touches_total"] == 0
    assert out["by_path"] == {}


def test_ac04_the_ucs_without_list_are_counted_and_the_notice_says_how_many():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post2"""
    closed = [_uc("UC-OLD", None), _uc("UC-NEW", ["a.py"])]
    out = closed_uc_touches(closed, ["a.py"])
    assert out["closed_without_files"] == 1
    assert out["notice"] == CLOSED_WITHOUT_FILES_NOTICE.format(n=1)
    assert "1 UC cerradas no tienen su lista de ficheros" in out["notice"]
    assert "no avisan hasta que la tengan" in out["notice"]
    assert "complete_uc" in out["notice"]


def test_ac04_with_several_ucs_without_list_the_count_and_notice_use_the_total():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post2"""
    closed = [_uc("UC-A", None), _uc("UC-B", None), _uc("UC-C", None), _uc("UC-D", ["x.py"])]
    out = closed_uc_touches(closed, ["x.py"])
    assert out["closed_without_files"] == 3
    assert "3 UC cerradas no tienen su lista de ficheros" in out["notice"]
    assert out["touches_total"] == 1


def test_ac04_when_the_uc_gets_its_list_it_stops_being_counted_and_it_warns():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post3"""
    uc = _uc("UC-OLD", None, name="Antigua")
    before = closed_uc_touches([uc], ["server/x.py"])
    assert before["touches"] == [] and before["closed_without_files"] == 1

    uc.files = ["server/x.py", "server/z.py"]  # complete_uc con files sobre la UC ya cerrada
    after = closed_uc_touches([uc], ["server/x.py"])
    assert after["closed_without_files"] == 0
    assert "notice" not in after
    assert after["touches_total"] == 1
    assert after["touches"][0]["uc_id"] == "UC-OLD"
    assert after["touches"][0]["files"] == ["server/x.py"]
    assert after["by_path"] == {"server/x.py": ["UC-OLD"]}


def test_ac04_the_list_added_later_is_the_merge_of_what_it_had_and_it_starts_from_nothing():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post3"""
    stored, truncated = merge_closed_files(None, normalize_closed_files(["./server/x.py", "server/y.py"]))
    assert (stored, truncated) == (["server/x.py", "server/y.py"], False)
    uc = _uc("UC-OLD", None)
    uc.files = stored
    out = closed_uc_touches([uc], ["server/y.py"])
    assert [t["uc_id"] for t in out["touches"]] == ["UC-OLD"]
    assert out["closed_without_files"] == 0


def test_ac04_undefined_with_no_uc_without_list_there_is_no_notice():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post2"""
    out = closed_uc_touches([_uc("UC-1", ["a.py"]), _uc("UC-2", ["b.py"])], ["a.py"])
    assert out["closed_without_files"] == 0
    assert "notice" not in out


def test_ac04_undefined_a_uc_closed_with_an_empty_list_counts_as_having_a_list():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post2"""
    out = closed_uc_touches([_uc("UC-EMPTY", [])], ["a.py"])
    assert out["closed_without_files"] == 0
    assert "notice" not in out
    assert out["touches"] == [] and out["touches_total"] == 0


def test_ac04_undefined_a_uc_without_list_is_counted_even_if_excluded_or_of_another_satellite():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post2"""
    closed = [_uc("UC-OLD", None, satellite="cloud")]
    out = closed_uc_touches(closed, ["a.py"], exclude=["UC-OLD"], satellite="engine", repo="acme/engine")
    assert out["closed_without_files"] == 1
    assert "1 UC cerradas" in out["notice"]
    assert out["touches"] == []
