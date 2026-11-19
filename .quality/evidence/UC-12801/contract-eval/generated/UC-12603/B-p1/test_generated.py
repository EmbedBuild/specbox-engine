"""Pruebas de aceptación de UC-12603 contra la API pública de ``server/closed_files.py``.

Salen del contrato de ``contract.json`` (pre, post y undefined de AC-01..AC-04). Sin base de datos,
sin red y sin disco: el módulo es puro.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from server.closed_files import (
    ClosedFilesError,
    ClosedUc,
    closed_uc_touches,
    files_for,
    merge_closed_files,
    normalize_closed_files,
    proposal,
)


def closed(uc_id: str, files, *, us_id: str = "US-1", name: str = "Nombre", closed_at: str | None = "2026-11-01T10:00:00Z",
           **extra) -> ClosedUc:
    return ClosedUc(uc_id=uc_id, us_id=us_id, name=name, files=files, closed_at=closed_at, **extra)


def by_uc(result: dict) -> dict[str, dict]:
    return {t["uc_id"]: t for t in result["touches"]}


# ---------------------------------------------------------------------------------------------
# AC-01 · El tablero guarda, para cada UC cerrada, los ficheros que cambió su PR
# ---------------------------------------------------------------------------------------------


def test_ac01_stored_list_is_normalized_without_repeats_and_in_arrival_order():
    """Las rutas de la PR se guardan relativas, con «/», sin «./», sin repetir y en su orden.

    contract: AC-01.pre1, AC-01.post1
    """
    raw = ["b.py", "./a.py", "dir\\c.py", "b.py", "  d.py ", "././e.py"]

    stored = normalize_closed_files(raw)

    assert stored == ["b.py", "a.py", "dir/c.py", "d.py", "e.py"]  # post1: forma, orden de llegada
    assert len(stored) == len(set(stored))  # post1: sin repetir
    assert all(not p.startswith("./") and "\\" not in p and not p.startswith("/") for p in stored)  # post1: forma


def test_ac01_reclosing_keeps_old_files_and_adds_the_new_pr_at_the_end():
    """Al cerrar otra vez se conservan los ficheros anteriores y se suman los nuevos al final, sin repetir.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post2
    """
    existing = ["a.py", "b.py"]
    new = normalize_closed_files(["./c.py", "a.py"])

    merged, truncated = merge_closed_files(existing, new)

    assert set(existing) <= set(merged)  # post2: conserva lo anterior
    assert merged[-len(new):] == new  # post2: lo de la PR nueva, al final
    assert merged == ["b.py", "c.py", "a.py"]
    assert len(merged) == len(set(merged))  # post2: sin repetir
    assert truncated is False


def test_ac01_over_1000_paths_keeps_the_most_recent_and_says_it_was_cut():
    """Por encima de 1000 rutas se quedan las 1000 más recientes y se avisa; con 1000 o menos no se recorta.

    contract: AC-01.pre1, AC-01.pre2, AC-01.post3
    """
    # una PR sola de 1001 rutas
    new = [f"f{i}.py" for i in range(1001)]
    merged, truncated = merge_closed_files(None, new)
    assert len(merged) == 1000
    assert merged == new[1:]  # las más recientes
    assert truncated is True  # post3: lo dice

    # exactamente 1000: no se recorta
    merged, truncated = merge_closed_files(None, new[:1000])
    assert merged == new[:1000]
    assert truncated is False

    # lo guardado + la PR nueva pasan de 1000: se quedan las más recientes
    old = [f"old{i}.py" for i in range(600)]
    fresh = [f"new{i}.py" for i in range(600)]
    merged, truncated = merge_closed_files(old, fresh)
    assert len(merged) == 1000
    assert merged[-600:] == fresh  # lo nuevo entero
    assert merged[:400] == old[200:]  # de lo viejo, lo más reciente
    assert truncated is True


def test_ac01_a_pr_without_list_stores_nothing_and_keeps_the_previous_list():
    """Sin lista (None o vacía) no se guarda nada nuevo y la lista anterior sigue igual (undefined).

    contract: AC-01.pre1, AC-01.pre2, AC-01.post1, AC-01.post2
    """
    assert normalize_closed_files(None) == []  # post1: no hay nada que guardar
    assert normalize_closed_files([]) == []

    merged, truncated = merge_closed_files(["a.py", "b.py"], normalize_closed_files(None))
    assert merged == ["a.py", "b.py"]  # post2: lo anterior intacto
    assert truncated is False


@pytest.mark.parametrize(
    "bad",
    ["/etc/passwd", "\\abs\\x.py", "../x.py", "a/../b.py", "..\\x.py", "./../x.py", "a\nb.py", "a\rb.py", "x" * 301],
)
def test_ac01_unsafe_paths_are_rejected_and_no_list_comes_out(bad):
    """Una ruta absoluta, con «..», con saltos de línea o de más de 300 caracteres no se guarda (undefined).

    contract: AC-01.pre1, AC-01.post1
    """
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(["ok.py", bad])  # post1: ni siquiera las buenas salen


def test_ac01_a_path_of_exactly_300_chars_and_dotted_names_are_valid():
    """El límite es 300 caracteres y un nombre con «..» dentro (no como tramo) vale (undefined).

    contract: AC-01.pre1, AC-01.post1
    """
    ok = "x" * 300
    assert normalize_closed_files([ok, "a..b.py", "dir/.hidden", "dir/...x"]) == [ok, "a..b.py", "dir/.hidden", "dir/...x"]


@pytest.mark.parametrize("bad", ["a.py", ("a.py",), {"a.py"}, ["a.py", 3], ["a.py", None], [["a.py"]], 7])
def test_ac01_what_is_not_a_list_of_texts_is_rejected(bad):
    """Lo que no es una lista de textos no se guarda (undefined).

    contract: AC-01.pre1, AC-01.post1
    """
    with pytest.raises(ClosedFilesError):
        normalize_closed_files(bad)


def test_ac01_blank_entries_are_ignored():
    """Una entrada vacía, de espacios o solo «./» se ignora (undefined).

    contract: AC-01.pre1, AC-01.post1
    """
    assert normalize_closed_files(["", "   ", "./", ".\\", "a.py"]) == ["a.py"]
    assert normalize_closed_files(["", "  "]) == []


def test_ac01_normalizing_a_huge_pr_does_not_cut_only_merging_does():
    """Normalizar una PR enorme no recorta: el tope se aplica al unir con lo guardado (undefined).

    contract: AC-01.pre1, AC-01.post1, AC-01.post3
    """
    paths = [f"f{i}.py" for i in range(1500)]

    stored = normalize_closed_files(paths)

    assert stored == paths  # post1: todas, en su orden, sin recortar
    merged, truncated = merge_closed_files(None, stored)
    assert merged == paths[-1000:]  # post3: aquí sí
    assert truncated is True


def test_ac01_merge_ignores_non_text_and_empty_entries_of_the_stored_list():
    """Al unir, lo guardado que no es texto o es vacío se ignora, y lo guardado que no es lista cuenta como nada (undefined).

    contract: AC-01.pre2, AC-01.post2
    """
    merged, truncated = merge_closed_files(["a.py", 3, None, "", "./b.py"], ["c.py"])
    assert merged == ["a.py", "b.py", "c.py"]  # post2
    assert truncated is False

    for not_a_list in (None, "abc", {"a": 1}, 5):
        assert merge_closed_files(not_a_list, ["a.py"]) == (["a.py"], False)  # post2


# ---------------------------------------------------------------------------------------------
# AC-02 · Un cambio posterior en uno de esos ficheros aparece con la UC cerrada que toca
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("exclude", [None, [], "UC-200", ["UC-200"], ["uc-200"]])
def test_ac02_a_later_change_comes_with_the_closed_uc_it_touches(exclude):
    """Un cambio de otra UC o sin UC en un fichero de una UC cerrada sale con esa UC y sus ficheros.

    contract: AC-02.pre1, AC-02.pre2, AC-02.pre3, AC-02.post1, AC-02.post2, AC-02.post3
    """
    uc = closed("UC-100", ["server/a.py", "server/b.py", "docs/x.md"], us_id="US-7", name="Cierra A",
                closed_at="2026-11-01T10:00:00Z")

    result = closed_uc_touches([uc], ["server/a.py", "src/new.py"], exclude)

    assert len(result["touches"]) == 1
    touch = result["touches"][0]
    assert touch["uc_id"] == "UC-100"  # post1
    assert touch["us_id"] == "US-7"  # post1
    assert touch["name"] == "Cierra A"  # post1
    assert touch["closed_at"] == "2026-11-01T10:00:00Z"  # post1
    assert touch["files"] == ["server/a.py"]  # post2: solo lo que cambió el cambio y es de esa UC
    assert "server/b.py" not in touch["files"] and "src/new.py" not in touch["files"]  # post2: nada ajeno
    assert result["by_path"] == {"server/a.py": ["UC-100"]}  # post3
    assert result["touches_total"] == 1  # post3


def test_ac02_a_change_touching_several_closed_ucs_names_each_with_its_own_files():
    """Si el cambio toca ficheros de varias UC cerradas, cada una aparece con los suyos.

    contract: AC-02.pre1, AC-02.pre2, AC-02.pre3, AC-02.post2, AC-02.post3, AC-02.post4
    """
    ucs = [
        closed("UC-100", ["a.py", "b.py"]),
        closed("UC-101", ["b.py", "c.py"], closed_at="2026-11-02T10:00:00Z"),
        closed("UC-102", ["z.py"]),
    ]

    result = closed_uc_touches(ucs, ["a.py", "b.py", "c.py"], ["UC-200"])

    touches = by_uc(result)
    assert set(touches) == {"UC-100", "UC-101"}  # post4: cada una, y no la que no toca
    assert touches["UC-100"]["files"] == ["a.py", "b.py"]  # post2 / post4: los suyos
    assert touches["UC-101"]["files"] == ["b.py", "c.py"]
    assert result["by_path"] == {"a.py": ["UC-100"], "b.py": ["UC-100", "UC-101"], "c.py": ["UC-101"]}  # post3
    assert result["touches_total"] == 2  # post3


def test_ac02_the_own_closed_uc_of_the_branch_does_not_warn():
    """El cambio de la propia UC cerrada (está en exclude, sin importar mayúsculas) no la avisa (undefined).

    contract: AC-02.pre1, AC-02.pre2, AC-02.post1
    """
    uc = closed("UC-100", ["a.py"])
    other = closed("UC-101", ["a.py"])

    for exclude in (["UC-100"], "UC-100", ["uc-100"], "uc-100"):
        result = closed_uc_touches([uc, other], ["a.py"], exclude)
        assert list(by_uc(result)) == ["UC-101"]  # post1: avisa la otra, no la propia
        assert result["by_path"] == {"a.py": ["UC-101"]}


def test_ac02_a_change_touching_no_closed_file_gives_an_empty_report():
    """Un cambio que no toca ningún fichero de las UC cerradas no avisa nada (undefined).

    contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3
    """
    result = closed_uc_touches([closed("UC-100", ["a.py"])], ["other.py"], None)

    assert result["touches"] == []  # post1
    assert result["touches_total"] == 0  # post3
    assert result["by_path"] == {}  # post3
    assert result["closed_without_files"] == 0
    assert "notice" not in result


def test_ac02_changed_paths_are_normalized_and_counted_once():
    """Las rutas del cambio se normalizan, no se repiten y las que no son texto o están vacías se ignoran (undefined).

    contract: AC-02.pre1, AC-02.pre2, AC-02.post2, AC-02.post3
    """
    uc = closed("UC-100", ["server/a.py"])

    result = closed_uc_touches([uc], ["./server/a.py", "server\\a.py", "server/a.py", "", "  ", 3, None], None)

    assert by_uc(result)["UC-100"]["files"] == ["server/a.py"]  # post2: una sola vez
    assert result["by_path"] == {"server/a.py": ["UC-100"]}  # post3


def test_ac02_order_limit_and_totals_when_many_closed_ucs_are_touched():
    """Más ficheros compartidos primero, luego el cierre más reciente; se listan hasta 20 y el total es el completo (undefined).

    contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post3, AC-02.post4
    """
    ucs = [closed(f"UC-{i:03d}", ["shared.py"], closed_at=f"2026-11-{i + 1:02d}T00:00:00Z") for i in range(25)]
    ucs.append(closed("UC-TWO", ["shared.py", "other.py"], closed_at="2026-10-01T00:00:00Z"))

    result = closed_uc_touches(ucs, ["shared.py", "other.py"], None)

    assert result["touches_total"] == 26  # post3: cuenta todas
    assert len(result["touches"]) == 20  # el límite por defecto
    assert result["touches"][0]["uc_id"] == "UC-TWO"  # más ficheros, aunque sea más antigua
    assert [t["uc_id"] for t in result["touches"][1:4]] == ["UC-024", "UC-023", "UC-022"]  # luego las más recientes
    assert len(result["by_path"]["shared.py"]) == 26  # post3 / post4: by_path no se recorta

    short = closed_uc_touches(ucs, ["shared.py", "other.py"], None, limit=3)
    assert len(short["touches"]) == 3
    assert short["touches_total"] == 26


def test_ac02_closed_ucs_of_another_repo_or_satellite_do_not_count():
    """En multirepo solo cuentan las UC cerradas del mismo repositorio (o satélite) que el cambio (undefined).

    contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2
    """
    both = closed(
        "UC-100", ["x.py", "y.py", "z.py"], satellite="engine",
        by_repo={"EmbedBuild/engine": ["x.py"], "EmbedBuild/cloud": ["y.py"]},
    )

    # por repositorio, sin distinguir mayúsculas; la ruta guardada sin repositorio (z.py) cuenta salvo otro satélite
    engine = closed_uc_touches([both], ["x.py", "y.py", "z.py"], None, repo="embedbuild/ENGINE")
    assert by_uc(engine)["UC-100"]["files"] == ["x.py", "z.py"]  # post1 / post2
    cloud = closed_uc_touches([both], ["x.py", "y.py", "z.py"], None, repo="EmbedBuild/cloud")
    assert by_uc(cloud)["UC-100"]["files"] == ["y.py", "z.py"]
    site = closed_uc_touches([both], ["x.py", "y.py"], None, repo="EmbedBuild/site")
    assert site["touches"] == [] and site["touches_total"] == 0  # post1: otro repositorio, sin aviso

    # un satélite distinto deja fuera hasta lo guardado sin repositorio
    other_sat = closed_uc_touches([both], ["x.py", "z.py"], None, repo="EmbedBuild/engine", satellite="site")
    assert by_uc(other_sat)["UC-100"]["files"] == ["x.py"]

    # sin by_repo: manda el satélite (sin mayúsculas); sin repo ni satélite cuentan todas
    plain = closed("UC-101", ["p.py"], satellite="Engine")
    assert by_uc(closed_uc_touches([plain], ["p.py"], None, satellite="engine"))["UC-101"]["files"] == ["p.py"]
    assert closed_uc_touches([plain], ["p.py"], None, satellite="site")["touches"] == []
    assert by_uc(closed_uc_touches([plain], ["p.py"], None))["UC-101"]["files"] == ["p.py"]


def test_ac02_files_for_scopes_the_files_of_a_closed_uc_by_repo_and_satellite():
    """``files_for`` da los ficheros de la UC cerrada que cuentan para un repositorio o satélite (undefined).

    contract: AC-02.pre1, AC-02.pre2, AC-02.post2
    """
    uc = closed("UC-100", ["x.py", "y.py", "z.py"], satellite="engine",
                by_repo={"o/engine": ["x.py"], "o/cloud": ["y.py"]})

    assert files_for(uc, "o/engine", None) == {"x.py", "z.py"}  # post2: su repositorio + lo sin repositorio
    assert files_for(uc, "O/CLOUD", "engine") == {"y.py", "z.py"}
    assert files_for(uc, "o/engine", "cloud") == {"x.py"}  # otro satélite: solo lo de su repositorio
    assert files_for(uc, "o/site", None) == {"z.py"}  # otro repositorio: solo lo guardado sin repositorio
    assert files_for(uc, None, None) == {"x.py", "y.py", "z.py"}  # sin repo ni satélite, todo
    assert files_for(uc, None, "cloud") == set()  # satélite distinto sin repositorio
    assert files_for(closed("UC-101", None), None, None) == set()  # sin lista, nada


# ---------------------------------------------------------------------------------------------
# AC-03 · El aviso propone revisar los criterios y la spec queda igual hasta que una persona decide
# ---------------------------------------------------------------------------------------------


def test_ac03_the_warning_proposes_reviewing_the_criteria_and_leaves_the_decision_to_a_person():
    """El aviso nombra la UC, propone revisar sus criterios y dice que lo decide una persona.

    contract: AC-03.pre1, AC-03.post1, AC-03.post2
    """
    uc = closed("UC-100", ["server/a.py"], name="Cierra A")

    result = closed_uc_touches([uc], ["server/a.py"], None)

    text = result["touches"][0]["proposal"]
    assert "UC-100" in text  # post1: nombra la UC
    assert "Cierra A" in text
    assert "revisa si sus criterios siguen valiendo" in text  # post1: la propuesta
    assert "`server/a.py`" in text  # el fichero que toca
    assert "no cambia sola" in text  # post2: el engine no la cambia
    assert "lo decide una persona" in text  # post2: la decisión es de una persona
    for tool in ("update_ac", "add_ac", "delete_ac"):  # post2: las vías de una persona
        assert tool in text
    assert text == proposal("UC-100", "Cierra A", ["server/a.py"])  # la función pública da el mismo aviso


def test_ac03_asking_for_the_warning_changes_nothing_of_the_spec():
    """Calcular el aviso deja las UC cerradas, las rutas y exclude exactamente como estaban.

    contract: AC-03.pre1, AC-03.pre2, AC-03.post3
    """
    ucs = [
        closed("UC-100", ["a.py", "b.py"], name="Cierra A", by_repo={"o/r": ["a.py"]}, satellite="engine"),
        closed("UC-101", None),
        closed("UC-102", ["c.py"]),
    ]
    paths = ["./a.py", "c.py", "none.py"]
    exclude = ["UC-200"]
    ucs_before, paths_before, exclude_before = copy.deepcopy(ucs), list(paths), list(exclude)

    result = closed_uc_touches(ucs, paths, exclude, repo="o/r")
    result["touches"][0]["files"].append("zzz.py")  # tocar el informe no toca la UC
    result["by_path"].clear()

    assert ucs == ucs_before  # post3: ficheros, nombre, cierre y repos de cada UC
    assert paths == paths_before  # post3
    assert exclude == exclude_before  # post3


def test_ac03_without_a_name_the_title_is_left_out():
    """Una UC sin nombre sale sin el título entre paréntesis; con nombre, entre «» (undefined).

    contract: AC-03.pre1, AC-03.post1
    """
    nameless = proposal("UC-1", "", ["a.py"])
    named = proposal("UC-1", "Nombre", ["a.py"])

    assert "UC-1" in nameless and "revisa si sus criterios siguen valiendo" in nameless  # post1
    assert "(«" not in nameless
    assert "UC-1 («Nombre»)" in named


def test_ac03_the_warning_names_the_first_five_files_and_counts_the_rest():
    """El aviso nombra los 5 primeros ficheros y cuenta el resto con «y N más» (undefined).

    contract: AC-03.pre1, AC-03.post1
    """
    five = proposal("UC-1", "N", [f"f{i}.py" for i in range(1, 6)])
    seven = proposal("UC-1", "N", [f"f{i}.py" for i in range(1, 8)])

    assert "más" not in five  # con 5, todos
    assert "`f5.py`" in five
    assert "`f5.py`" in seven and "`f6.py`" not in seven  # post1: nombra 5
    assert "y 2 más" in seven


def test_ac03_the_warning_is_pure_and_repeatable():
    """Con los mismos datos el aviso sale idéntico cada vez (undefined).

    contract: AC-03.pre1, AC-03.pre2, AC-03.post1, AC-03.post3
    """
    ucs = [closed("UC-100", ["a.py"], name="Cierra A")]
    first = closed_uc_touches(ucs, ["a.py"], None)
    second = closed_uc_touches(ucs, ["a.py"], None)

    assert first == second  # post3: nada cambió entre una y otra
    assert first["touches"][0]["proposal"] == second["touches"][0]["proposal"]  # post1


# ---------------------------------------------------------------------------------------------
# AC-04 · Las UC cerradas antes de la medida quedan sin avisos hasta tener su lista
# ---------------------------------------------------------------------------------------------


def test_ac04_a_uc_closed_without_a_list_never_warns_and_is_counted():
    """Una UC sin lista no avisa aunque el cambio toque lo que su PR cambió, y se cuenta con un aviso.

    contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post2
    """
    old = closed("UC-OLD", None)
    new = closed("UC-NEW", ["a.py"])

    result = closed_uc_touches([old, new], ["a.py", "b.py"], None)

    assert list(by_uc(result)) == ["UC-NEW"]  # post1: la vieja no aparece
    assert all("UC-OLD" not in uc_ids for uc_ids in result["by_path"].values())  # post1
    assert result["touches_total"] == 1  # post1: no cuenta
    assert result["closed_without_files"] == 1  # post2
    assert "notice" in result and result["notice"].startswith("1 ")  # post2: dice cuántas
    assert "lista de ficheros" in result["notice"]

    alone = closed_uc_touches([old], ["a.py"], None)
    assert alone["touches"] == [] and alone["by_path"] == {} and alone["touches_total"] == 0  # post1
    assert alone["closed_without_files"] == 1 and "notice" in alone  # post2


def test_ac04_without_uncounted_ucs_the_report_has_no_notice():
    """Sin UC cerradas sin lista, closed_without_files es 0 y no hay notice.

    contract: AC-04.pre2, AC-04.post2
    """
    result = closed_uc_touches([closed("UC-100", ["a.py"])], ["a.py"], None)

    assert result["closed_without_files"] == 0  # post2
    assert "notice" not in result  # post2


def test_ac04_the_uc_warns_normally_once_it_has_its_list():
    """Al recibir su lista, la UC antes vieja avisa y deja de contar como sin lista.

    contract: AC-04.pre1, AC-04.pre2, AC-04.pre3, AC-04.post1, AC-04.post2, AC-04.post3
    """
    before = closed("UC-OLD", None)
    paths = ["a.py", "z.py"]

    first = closed_uc_touches([before], paths, None)
    assert first["touches"] == [] and first["touches_total"] == 0  # post1: sin lista, sin aviso
    assert first["closed_without_files"] == 1  # post2

    after = dataclasses.replace(before, files=["a.py", "b.py"])  # pre3: recibe su lista
    second = closed_uc_touches([after], paths, None)

    assert by_uc(second)["UC-OLD"]["files"] == ["a.py"]  # post3: avisa con los ficheros que comparte
    assert second["by_path"] == {"a.py": ["UC-OLD"]}  # post3
    assert second["touches_total"] == 1  # post3
    assert second["closed_without_files"] == 0  # post3: deja de contar
    assert "notice" not in second  # post2 / post3


def test_ac04_a_closed_uc_with_an_empty_list_has_a_list_and_never_warns():
    """Una UC con la lista vacía (files = []) no se cuenta como «sin lista» y no avisa (undefined).

    contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post2
    """
    result = closed_uc_touches([closed("UC-100", [])], ["a.py"], None)

    assert result["touches"] == [] and result["touches_total"] == 0  # post1
    assert result["closed_without_files"] == 0  # post2: tiene lista, aunque vacía
    assert "notice" not in result


def test_ac04_a_uc_without_a_list_is_counted_even_if_excluded_or_with_no_changed_paths():
    """Se cuenta como «sin lista» aunque esté en exclude o no haya rutas cambiadas; el número va en el notice (undefined).

    contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post2
    """
    ucs = [closed("UC-1", None), closed("UC-2", None), closed("UC-3", None)]

    excluded = closed_uc_touches(ucs, ["a.py"], ["UC-1"])
    assert excluded["closed_without_files"] == 3  # post2: la excluida también
    assert excluded["touches"] == []  # post1

    empty = closed_uc_touches(ucs, [], None)
    assert empty["closed_without_files"] == 3  # post2
    assert empty["notice"].startswith("3 ")  # post2: el número en el texto
    assert empty["touches"] == [] and empty["touches_total"] == 0  # post1
