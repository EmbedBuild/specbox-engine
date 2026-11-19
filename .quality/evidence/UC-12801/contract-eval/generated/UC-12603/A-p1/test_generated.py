"""Pruebas de aceptación de UC-12603 «Un cambio que toca una UC cerrada se avisa».

Se prueban las funciones públicas de ``server/closed_files.py`` (puras: sin base de datos, red ni
disco). Cada prueba cita su criterio (AC-NN) en el nombre y en el docstring.

Criterios vigentes:
- AC-01: El tablero guarda, para cada UC cerrada, los ficheros que cambió su PR.
- AC-02: Un cambio posterior en uno de esos ficheros, desde otra UC o sin UC, aparece en el informe
  de la puerta de desviación con la UC cerrada que toca.
- AC-03: El aviso muestra la propuesta de revisar los criterios de esa UC, y la spec queda igual
  hasta que una persona decide cambiarla.
- AC-04: Las UC cerradas antes de la medida quedan sin avisos hasta tener su lista de ficheros.
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
    proposal,
)

ENGINE = "EmbedBuild/specbox-engine"
CLOUD = "EmbedBuild/specbox_cloud"


def _uc(uc_id: str, files, *, us: str = "US-1", name: str = "Alta de cliente", closed_at=None, **kw) -> ClosedUc:
    return ClosedUc(uc_id=uc_id, us_id=us, name=name, files=files, closed_at=closed_at, **kw)


# --------------------------------------------------------------------------------------------------
# AC-01: el tablero guarda, para cada UC cerrada, los ficheros que cambió su PR.
# (La parte del módulo es la lista que se guarda: su forma, su suma y su tope.)
# --------------------------------------------------------------------------------------------------


def test_ac01_the_files_of_the_pr_are_stored_normalized_without_repeats_and_in_order():
    """AC-01: la lista que guarda el cierre es relativa al repo, sin repetir y en su orden."""
    stored = normalize_closed_files(["./server\\closed_files.py", "server/closed_files.py", " tests/a.py ", "", "  "])
    assert stored == ["server/closed_files.py", "tests/a.py"]


def test_ac01_a_close_without_files_stores_an_empty_list():
    """AC-01: sin ``files`` no hay nada que guardar (lista vacía, no error)."""
    assert normalize_closed_files(None) == []
    assert normalize_closed_files([]) == []


@pytest.mark.parametrize(
    "raw",
    [
        "server/x.py",  # no es una lista
        ["server/x.py", 3],  # un elemento que no es texto
        ["/etc/passwd"],  # ruta absoluta
        ["server/../secret.txt"],  # sube por «..»
        ["server/x.py\nOTRA"],  # salto de línea
        ["a" * (MAX_CLOSED_PATH + 1)],  # ruta demasiado larga
    ],
)
def test_ac01_an_invalid_list_is_rejected_so_nothing_wrong_is_stored(raw):
    """AC-01: solo se guardan rutas relativas del repositorio; lo demás se rechaza."""
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(raw)


def test_ac01_a_path_of_exactly_the_maximum_length_is_stored():
    """AC-01: el límite de 300 caracteres por ruta es inclusivo."""
    path = "a" * MAX_CLOSED_PATH
    assert normalize_closed_files([path]) == [path]


def test_ac01_the_first_close_keeps_exactly_the_files_of_its_pr():
    """AC-01: una UC que se cierra por primera vez guarda los ficheros de su PR, sin recorte."""
    assert merge_closed_files(None, ["server/a.py", "tests/a.py"]) == (["server/a.py", "tests/a.py"], False)


def test_ac01_a_reclosed_uc_adds_the_files_of_its_new_pr_to_the_ones_it_had():
    """AC-01: al volver a cerrar, se suman los ficheros de la PR nueva sin duplicar los repetidos."""
    stored, truncated = merge_closed_files(["server/a.py", "server/b.py"], ["server/b.py", "server/c.py"])
    assert stored == ["server/a.py", "server/b.py", "server/c.py"]
    assert truncated is False


def test_ac01_a_pr_over_the_cap_keeps_the_most_recent_files_and_says_so():
    """AC-01: por encima de 1000 rutas se quedan las más recientes y se avisa del recorte."""
    old = [f"old/f{i}.py" for i in range(MAX_CLOSED_FILES)]
    new = [f"new/n{i}.py" for i in range(5)]
    stored, truncated = merge_closed_files(old, new)
    assert MAX_CLOSED_FILES == 1000
    assert truncated is True
    assert len(stored) == 1000
    assert stored[-5:] == new
    assert "old/f0.py" not in stored and "old/f4.py" not in stored
    assert "old/f5.py" in stored


def test_ac01_exactly_the_cap_is_not_truncated():
    """AC-01: 1000 rutas caben; el recorte solo empieza con la 1001."""
    stored, truncated = merge_closed_files(None, [f"f{i}.py" for i in range(1000)])
    assert len(stored) == 1000
    assert truncated is False


def test_ac01_a_uc_with_prs_in_two_repositories_keeps_one_list_per_repository():
    """AC-01: los ficheros de cada PR cuentan solo en el repositorio de esa PR."""
    uc = _uc(
        "UC-100",
        ["server/a.py", "web/b.ts"],
        by_repo={ENGINE: ["server/a.py"], CLOUD: ["web/b.ts"]},
    )
    assert files_for(uc, ENGINE, None) == {"server/a.py"}
    assert files_for(uc, CLOUD, None) == {"web/b.ts"}
    # El nombre del repositorio no distingue mayúsculas.
    assert files_for(uc, ENGINE.lower(), None) == {"server/a.py"}


# --------------------------------------------------------------------------------------------------
# AC-02: un cambio posterior en uno de esos ficheros, desde otra UC o sin UC, aparece con la UC
# cerrada que toca.
# --------------------------------------------------------------------------------------------------


def test_ac02_a_change_from_another_uc_names_the_closed_uc_and_the_file_it_touches():
    """AC-02: el cambio de otra UC (la UC-200) en ``server/a.py`` sale con la UC-100 cerrada."""
    closed = [_uc("UC-100", ["server/a.py", "server/b.py"], us="US-7", name="Alta", closed_at="2026-11-01T10:00:00")]
    result = closed_uc_touches(closed, ["server/a.py", "docs/x.md"], exclude=["UC-200"])
    assert result["touches_total"] == 1
    touch = result["touches"][0]
    assert touch["uc_id"] == "UC-100"
    assert touch["us_id"] == "US-7"
    assert touch["name"] == "Alta"
    assert touch["closed_at"] == "2026-11-01T10:00:00"
    assert touch["files"] == ["server/a.py"]  # solo el que cambió, no server/b.py ni docs/x.md
    assert result["by_path"] == {"server/a.py": ["UC-100"]}


def test_ac02_a_change_without_any_uc_also_names_the_closed_uc():
    """AC-02: un cambio sin UC (sin ``exclude``) también sale con la UC cerrada que toca."""
    closed = [_uc("UC-100", ["server/a.py"])]
    for no_uc in (None, [], ""):
        result = closed_uc_touches(closed, ["server/a.py"], no_uc)
        assert result["touches_total"] == 1, no_uc
        assert result["touches"][0]["uc_id"] == "UC-100"
        assert result["by_path"] == {"server/a.py": ["UC-100"]}


def test_ac02_the_ucs_of_the_branch_are_not_another_uc():
    """AC-02: los ficheros de las UC de la propia rama no cuentan como «otra UC» (sin distinguir mayúsculas)."""
    closed = [_uc("UC-100", ["server/a.py"]), _uc("UC-300", ["server/a.py"])]
    by_list = closed_uc_touches(closed, ["server/a.py"], ["uc-100"])
    assert [t["uc_id"] for t in by_list["touches"]] == ["UC-300"]
    assert by_list["by_path"] == {"server/a.py": ["UC-300"]}
    by_text = closed_uc_touches(closed, ["server/a.py"], "UC-300")
    assert [t["uc_id"] for t in by_text["touches"]] == ["UC-100"]
    both = closed_uc_touches(closed, ["server/a.py"], ["UC-100", "UC-300"])
    assert both["touches"] == [] and both["touches_total"] == 0 and both["by_path"] == {}


def test_ac02_changed_paths_are_compared_in_their_normalized_form():
    """AC-02: ``./server\\a.py`` y ``server/a.py`` son el mismo fichero."""
    closed = [_uc("UC-100", ["server/a.py"])]
    result = closed_uc_touches(closed, ["./server\\a.py"])
    assert result["touches"][0]["files"] == ["server/a.py"]
    assert result["by_path"] == {"server/a.py": ["UC-100"]}


def test_ac02_a_change_in_a_file_no_closed_uc_changed_gives_no_warning():
    """AC-02: si el fichero cambiado no está en ninguna UC cerrada, el informe no avisa."""
    closed = [_uc("UC-100", ["server/a.py"])]
    result = closed_uc_touches(closed, ["server/other.py"])
    assert result["touches"] == []
    assert result["touches_total"] == 0
    assert result["by_path"] == {}
    assert result["closed_without_files"] == 0
    assert "notice" not in result


def test_ac02_a_file_shared_by_two_closed_ucs_lists_both_and_the_one_sharing_most_files_goes_first():
    """AC-02: cada fichero lleva todas las UC cerradas que lo tocan; primero la que más ficheros comparte."""
    closed = [
        _uc("UC-1", ["server/a.py"], closed_at="2026-11-18"),
        _uc("UC-2", ["server/a.py", "server/b.py"], closed_at="2026-11-01"),
    ]
    result = closed_uc_touches(closed, ["server/a.py", "server/b.py"])
    assert [t["uc_id"] for t in result["touches"]] == ["UC-2", "UC-1"]
    assert result["touches"][0]["files"] == ["server/a.py", "server/b.py"]
    assert result["by_path"] == {"server/a.py": ["UC-1", "UC-2"], "server/b.py": ["UC-2"]}
    assert result["touches_total"] == 2


def test_ac02_with_the_same_number_of_files_the_most_recent_closed_uc_goes_first():
    """AC-02: a igualdad de ficheros, primero la UC cerrada más recientemente."""
    closed = [
        _uc("UC-OLD", ["server/a.py"], closed_at="2026-10-01T00:00:00"),
        _uc("UC-NEW", ["server/a.py"], closed_at="2026-11-18T00:00:00"),
    ]
    result = closed_uc_touches(closed, ["server/a.py"])
    assert [t["uc_id"] for t in result["touches"]] == ["UC-NEW", "UC-OLD"]


def test_ac02_the_report_lists_at_most_the_limit_and_counts_the_rest():
    """AC-02: el informe trae como mucho 20 avisos (``MAX_TOUCHES``) y ``touches_total`` cuenta todos."""
    assert MAX_TOUCHES == 20
    closed = [_uc(f"UC-{i:03d}", ["server/a.py"], closed_at=f"2026-11-{i % 28 + 1:02d}") for i in range(25)]
    default = closed_uc_touches(closed, ["server/a.py"])
    assert len(default["touches"]) == 20
    assert default["touches_total"] == 25
    assert len(default["by_path"]["server/a.py"]) == 25
    small = closed_uc_touches(closed, ["server/a.py"], limit=2)
    assert len(small["touches"]) == 2
    assert small["touches_total"] == 25


def test_ac02_a_closed_uc_of_another_repository_does_not_count():
    """AC-02: en multirepo, la misma ruta en otro repositorio no es el mismo fichero."""
    closed = [
        _uc("UC-100", ["server/a.py", "web/b.ts"], by_repo={ENGINE: ["server/a.py"], CLOUD: ["web/b.ts"]}),
    ]
    in_engine = closed_uc_touches(closed, ["server/a.py", "web/b.ts"], repo=ENGINE)
    assert in_engine["touches"][0]["files"] == ["server/a.py"]
    assert in_engine["by_path"] == {"server/a.py": ["UC-100"]}
    in_cloud = closed_uc_touches(closed, ["server/a.py", "web/b.ts"], repo=CLOUD.upper())
    assert in_cloud["touches"][0]["files"] == ["web/b.ts"]
    elsewhere = closed_uc_touches(closed, ["server/a.py", "web/b.ts"], repo="EmbedBuild/otro")
    assert elsewhere["touches"] == [] and elsewhere["touches_total"] == 0


def test_ac02_paths_saved_without_repository_count_for_any_repository_of_the_same_satellite():
    """AC-02: las rutas guardadas sin repositorio siguen avisando (no se pierden por tener otras con repo)."""
    closed = [_uc("UC-100", ["server/a.py", "server/b.py"], by_repo={ENGINE: ["server/a.py"]})]
    result = closed_uc_touches(closed, ["server/a.py", "server/b.py"], repo=ENGINE)
    assert result["touches"][0]["files"] == ["server/a.py", "server/b.py"]


def test_ac02_a_closed_uc_of_another_satellite_does_not_count_but_the_same_one_does():
    """AC-02: sin lista por repositorio, la UC cerrada de otro satélite no avisa (sin distinguir mayúsculas)."""
    closed = [_uc("UC-100", ["server/a.py"], satellite="engine")]
    assert closed_uc_touches(closed, ["server/a.py"], satellite="cloud")["touches"] == []
    same = closed_uc_touches(closed, ["server/a.py"], satellite="ENGINE")
    assert same["touches"][0]["uc_id"] == "UC-100"
    # Sin satélite conocido en el cambio, cuentan todas.
    assert closed_uc_touches(closed, ["server/a.py"])["touches_total"] == 1


def test_ac02_no_changed_paths_or_no_closed_ucs_give_an_empty_report():
    """AC-02: sin rutas o sin UC cerradas el informe sale vacío y con su forma completa."""
    expected = {"touches": [], "touches_total": 0, "by_path": {}, "closed_without_files": 0}
    assert closed_uc_touches([_uc("UC-100", ["server/a.py"])], []) == expected
    assert closed_uc_touches([], ["server/a.py"]) == expected


# --------------------------------------------------------------------------------------------------
# AC-03: el aviso muestra la propuesta de revisar los criterios de esa UC, y la spec queda igual
# hasta que una persona decide cambiarla.
# --------------------------------------------------------------------------------------------------


def test_ac03_the_warning_proposes_reviewing_the_criteria_of_that_uc():
    """AC-03: la propuesta nombra la UC, su título y el fichero, y pide revisar sus criterios."""
    closed = [_uc("UC-100", ["server/a.py"], name="Alta de cliente")]
    touch = closed_uc_touches(closed, ["server/a.py"])["touches"][0]
    assert touch["proposal"] == (
        "Este cambio toca `server/a.py`, de UC-100 («Alta de cliente»), ya cerrada: revisa si sus "
        "criterios siguen valiendo. La spec no cambia sola: si hay que cambiarla, lo decide una "
        "persona (update_ac, add_ac o delete_ac)."
    )
    assert touch["proposal"] == proposal("UC-100", "Alta de cliente", ["server/a.py"])


def test_ac03_the_proposal_leaves_the_decision_to_a_person():
    """AC-03: el aviso dice que la spec no cambia sola y que lo decide una persona."""
    text = proposal("UC-9", "Algo", ["a.py"])
    assert "revisa si sus criterios siguen valiendo" in text
    assert "La spec no cambia sola" in text
    assert "lo decide una persona" in text


def test_ac03_the_proposal_lists_five_files_and_counts_the_rest():
    """AC-03: con más de cinco ficheros, la propuesta lista cinco y dice cuántos más."""
    files = [f"src/f{i}.py" for i in range(7)]
    text = proposal("UC-9", "Algo", files)
    for listed in files[:5]:
        assert f"`{listed}`" in text
    assert "`src/f5.py`" not in text and "`src/f6.py`" not in text
    assert "y 2 más" in text
    exactly_five = proposal("UC-9", "Algo", files[:5])
    assert "más" not in exactly_five.split("ya cerrada")[0]


def test_ac03_a_uc_without_title_still_gets_its_proposal_without_empty_quotes():
    """AC-03: sin título, la propuesta sale igual y sin comillas vacías."""
    text = proposal("UC-9", "", ["a.py"])
    assert text.startswith("Este cambio toca `a.py`, de UC-9, ya cerrada: revisa si sus criterios siguen valiendo.")
    assert "«" not in text


def test_ac03_every_warning_carries_its_proposal_for_the_files_it_touches():
    """AC-03: cada aviso de un informe lleva su propuesta, con sus propios ficheros y su UC."""
    closed = [_uc("UC-1", ["a.py"], name="Uno"), _uc("UC-2", ["b.py"], name="Dos")]
    result = closed_uc_touches(closed, ["a.py", "b.py"])
    by_uc = {t["uc_id"]: t for t in result["touches"]}
    assert "`a.py`, de UC-1 («Uno»)" in by_uc["UC-1"]["proposal"]
    assert "`b.py`, de UC-2 («Dos»)" in by_uc["UC-2"]["proposal"]
    assert "`b.py`" not in by_uc["UC-1"]["proposal"]


def test_ac03_the_warning_only_reads_so_the_closed_ucs_and_their_criteria_stay_as_they_were():
    """AC-03: calcular el aviso no cambia ni las UC cerradas ni las rutas: la spec queda igual."""
    closed = [
        _uc("UC-100", ["server/a.py", "server/b.py"], name="Alta", closed_at="2026-11-01",
            by_repo={ENGINE: ["server/a.py"]}, satellite="engine", extra={"criteria": ["AC-01", "AC-02"]}),
        _uc("UC-101", None, name="Vieja"),
    ]
    paths = ["./server/a.py", "server/b.py", "server/a.py"]
    exclude = ["UC-300"]
    snapshot = (copy.deepcopy(closed), copy.deepcopy(paths), copy.deepcopy(exclude))
    first = closed_uc_touches(closed, paths, exclude, repo=ENGINE, satellite="engine")
    assert (closed, paths, exclude) == snapshot
    # Repetirlo da lo mismo: no hay estado que cambie entre llamadas.
    assert closed_uc_touches(closed, paths, exclude, repo=ENGINE, satellite="engine") == first
    assert (closed, paths, exclude) == snapshot


def test_ac03_the_warning_carries_only_information_never_a_change_to_the_spec():
    """AC-03: cada aviso solo informa (UC, historia, título, cierre, ficheros, propuesta)."""
    closed = [_uc("UC-100", ["server/a.py"], us="US-7", name="Alta", closed_at="2026-11-01")]
    touch = closed_uc_touches(closed, ["server/a.py"])["touches"][0]
    assert set(touch) == {"uc_id", "us_id", "name", "closed_at", "files", "proposal"}


# --------------------------------------------------------------------------------------------------
# AC-04: las UC cerradas antes de la medida quedan sin avisos hasta tener su lista de ficheros.
# --------------------------------------------------------------------------------------------------


def test_ac04_a_uc_closed_without_a_file_list_gives_no_warning_and_is_counted():
    """AC-04: una UC cerrada sin lista (``files=None``) no avisa, y el informe cuenta cuántas hay."""
    old = [_uc("UC-OLD", None, name="Cerrada antes")]
    result = closed_uc_touches(old, ["server/a.py"])
    assert result["touches"] == []
    assert result["touches_total"] == 0
    assert result["by_path"] == {}
    assert result["closed_without_files"] == 1
    assert result["notice"] == CLOSED_WITHOUT_FILES_NOTICE.format(n=1)
    assert result["notice"].startswith("1 UC cerradas no tienen su lista de ficheros")
    assert "no avisan hasta que la tengan" in result["notice"]


def test_ac04_old_ucs_are_counted_while_the_ones_with_a_list_keep_warning():
    """AC-04: con UC viejas y UC con lista a la vez, solo avisan las que tienen lista."""
    closed = [
        _uc("UC-OLD1", None),
        _uc("UC-NEW", ["server/a.py"]),
        _uc("UC-OLD2", None),
    ]
    result = closed_uc_touches(closed, ["server/a.py"])
    assert [t["uc_id"] for t in result["touches"]] == ["UC-NEW"]
    assert result["by_path"] == {"server/a.py": ["UC-NEW"]}
    assert result["closed_without_files"] == 2
    assert result["notice"].startswith("2 UC cerradas no tienen su lista de ficheros")


def test_ac04_an_old_uc_never_warns_whatever_the_changed_paths_are():
    """AC-04: sin lista no hay con qué comparar: ninguna ruta hace avisar a la UC vieja."""
    old = [_uc("UC-OLD", None)]
    for paths in (["server/a.py"], ["a.py", "b.py", "c.py"], ["CLAUDE.md"]):
        result = closed_uc_touches(old, paths)
        assert result["touches"] == [] and result["by_path"] == {}


def test_ac04_a_uc_with_an_empty_list_does_not_warn_either():
    """AC-04: una lista vacía tampoco hace avisar a la UC."""
    result = closed_uc_touches([_uc("UC-100", [])], ["server/a.py"])
    assert result["touches"] == [] and result["touches_total"] == 0


def test_ac04_once_the_old_uc_gets_its_file_list_it_starts_warning():
    """AC-04: al darle su lista (complete_uc con ``files`` sobre la UC ya cerrada), la UC empieza a avisar."""
    before = _uc("UC-OLD", None, name="Cerrada antes")
    assert closed_uc_touches([before], ["server/a.py"])["touches"] == []

    stored, truncated = merge_closed_files(None, normalize_closed_files(["./server/a.py", "tests/a.py"]))
    assert truncated is False
    after = _uc("UC-OLD", stored, name="Cerrada antes", closed_at="2026-11-19T08:00:00")
    result = closed_uc_touches([after], ["server/a.py"])
    assert result["closed_without_files"] == 0
    assert "notice" not in result
    assert [t["uc_id"] for t in result["touches"]] == ["UC-OLD"]
    assert result["touches"][0]["files"] == ["server/a.py"]


def test_ac04_closing_without_files_tells_how_to_get_the_warning():
    """AC-04: el aviso al cerrar sin ``files`` dice que no avisará y cómo conseguirlo."""
    assert "La UC se cerró sin `files`" in NO_FILES_AT_CLOSE_NOTICE
    assert "no avisará" in NO_FILES_AT_CLOSE_NOTICE
    assert "complete_uc" in NO_FILES_AT_CLOSE_NOTICE
    assert "gh api repos/<owner>/<repo>/pulls/<n>/files --paginate" in NO_FILES_AT_CLOSE_NOTICE
