"""Pruebas de aceptación de UC-12606 contra las funciones públicas de server/impact_radius.py.

Se generan desde el contrato (contract.json): cada prueba prepara sus precondiciones, comprueba
con una aserción cada postcondición que cita y lo dice en su docstring («contract: ...»).
Sin base de datos, red ni disco: el módulo es puro y recibe el texto del plan.
"""

from __future__ import annotations

import pytest

from server.impact_radius import (
    ImpactConfigError,
    classify_path,
    impact_decision,
    plan_impact,
)

SOURCE = "plan · fases con contrato de API o migración de datos"


def _plan(*phases: tuple[str, list[str]]) -> str:
    """Un plan de /plan con una fase por (título, ficheros), cada una con su línea de criterios."""
    lines = ["# Plan de UC-12606", ""]
    for n, (title, files) in enumerate(phases, 1):
        lines += [
            f"### Fase {n}: {title}",
            f"**Criterios:** UC-12606 AC-{n:02d}",
            f"**Ficheros:** {', '.join(files)}",
            "",
        ]
    return "\n".join(lines)


API_PLAN = _plan(("Contrato de la API", ["openapi.yaml", "server/api.py"]))
MIGRATION_PLAN = _plan(("Migración", ["migrations/0001_init.sql"]))
INTERNAL_PLAN = _plan(("Interna", ["server/core.py", "package.json", "docs/guide.md"]))
BOTH_PLAN = _plan(
    ("Contrato de la API", ["openapi.yaml"]),
    ("Migración", ["migrations/0001_init.sql", "db/migrate/3.rb"]),
    ("Interna", ["server/core.py"]),
)


# ---------------------------------------------------------------------------------------------
# AC-01: clasificación por lo que toca el cambio; la clase aparece en el mensaje
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "openapi.yaml",
        "openapi.yml",
        "openapi.json",
        "docs/openapi.json",
        "swagger.yml",
        "api/v1/swagger.json",
        "proto/service.proto",
        "api/types.graphqls",
        "schema.graphql",
        "api/schema_v2.graphql",
    ],
)
def test_ac01_contract_paths_are_api_contract(path):
    """contract: AC-01.pre1, AC-01.post1"""
    assert classify_path(path) == "api_contract"


@pytest.mark.parametrize(
    "path",
    [
        "migrations/0001_init.py",
        "app/migrations/__init__.py",
        "alembic/versions/ab12.py",
        "db/migrate/2020_add_users.rb",
        "queries/report.sql",
        "schema.prisma",
        "prisma/schema.prisma",
    ],
)
def test_ac01_migration_paths_are_data_migration(path):
    """contract: AC-01.pre1, AC-01.post2"""
    assert classify_path(path) == "data_migration"


@pytest.mark.parametrize(
    "path",
    ["package.json", "requirements.txt", "pnpm-lock.yaml", "src/app.py", "server/core.py", "lib/util.dart"],
)
def test_ac01_dependencies_and_internal_are_not_contract_nor_migration(path):
    """contract: AC-01.pre1, AC-01.post3"""
    assert classify_path(path) is None


def test_ac01_plan_impact_one_entry_per_affected_phase_with_class_and_label():
    """contract: AC-01.pre1, AC-01.post4"""
    result = plan_impact(BOTH_PLAN)
    assert [(e["phase"], e["class"], e["label"]) for e in result] == [
        ("Fase 1: Contrato de la API", "api_contract", "contrato de API"),
        ("Fase 2: Migración", "data_migration", "migración de datos"),
    ]


def test_ac01_message_shows_class_label_next_to_phase():
    """contract: AC-01.pre1, AC-01.post5"""
    decision = impact_decision(BOTH_PLAN)
    assert decision is not None
    text = decision["description"]
    assert "Fase 1: Contrato de la API: contrato de API (openapi.yaml)" in text
    assert "Fase 2: Migración: migración de datos (migrations/0001_init.sql, db/migrate/3.rb)" in text
    # la fase interna no aparece en el mensaje
    assert "Fase 3" not in text


def test_ac01_phase_with_both_classes_gets_one_entry_per_class_in_fixed_order():
    """contract: AC-01.pre1, AC-01.post4 (undefined: un fichero de contrato y otro de migración en la misma fase)"""
    plan = _plan(("Mixta", ["migrations/0001.sql", "openapi.yaml"]))
    result = plan_impact(plan)
    assert [(e["class"], e["files"]) for e in result] == [
        ("api_contract", ["openapi.yaml"]),
        ("data_migration", ["migrations/0001.sql"]),
    ]
    assert {e["phase"] for e in result} == {"Fase 1: Mixta"}


@pytest.mark.parametrize(
    "path, expected",
    [
        ("./migrations/x.py", "data_migration"),
        ("/migrations/x.py", "data_migration"),
        ("migrations\\x.py", "data_migration"),
        ("`migrations/x.py`", "data_migration"),
        ("  migrations/x.py  ", "data_migration"),
        ("./openapi.yaml", "api_contract"),
        ("`api/openapi.yaml`", "api_contract"),
        ("api\\swagger.json", "api_contract"),
    ],
)
def test_ac01_path_formats_are_normalised(path, expected):
    """contract: AC-01.pre1, AC-01.post1, AC-01.post2 (undefined: rutas con ./, /, barras invertidas, comillas)"""
    assert classify_path(path) == expected


@pytest.mark.parametrize("path", ["", "   ", "``", "./"])
def test_ac01_empty_path_is_not_classified(path):
    """contract: AC-01.pre1, AC-01.post3 (undefined: ruta vacía)"""
    assert classify_path(path) is None


@pytest.mark.parametrize(
    "path",
    [
        "migrations/README.md",
        "migrations/notes.txt",
        "docs/openapi.md",
        "openapi.txt",
        "schema.graphql.md",
        "db/seeds/data.sql",
        "tests/fixtures/x.sql",
        "fixtures/a.sql",
        "test/seed/a.sql",
        "spec/x.sql",
        "seed.sql",
    ],
)
def test_ac01_documentation_and_seeds_outside_migrations_are_not_classified(path):
    """contract: AC-01.pre1, AC-01.post3 (undefined: documentación, semillas y datos de prueba)"""
    assert classify_path(path) is None


def test_ac01_seed_inside_a_migrations_folder_still_counts_as_migration():
    """contract: AC-01.pre1, AC-01.post2 (undefined: semilla dentro de una carpeta de migraciones)"""
    assert classify_path("migrations/seed.sql") == "data_migration"
    assert classify_path("db/migrate/fixtures/x.rb") == "data_migration"


def test_ac01_file_that_is_contract_and_in_migrations_folder_is_contract():
    """contract: AC-01.pre1, AC-01.post1 (undefined: un fichero que es de contrato y de migración a la vez)"""
    assert classify_path("migrations/openapi.yaml") == "api_contract"


def test_ac01_folder_names_are_case_sensitive_and_names_must_match_whole_folder():
    """contract: AC-01.pre1, AC-01.post3 (undefined: mayúsculas y carpetas de nombre parecido)"""
    assert classify_path("Migrations/x.py") is None
    assert classify_path("src/migrations_helper.py") is None
    assert classify_path("x.SQL") is None
    assert classify_path("openapi.yaml.bak") is None


def test_ac01_folder_only_entries_in_a_plan_are_classified():
    """contract: AC-01.pre1, AC-01.post2 (undefined: una carpeta entera declarada como ruta)"""
    assert classify_path("db/migrate/") == "data_migration"
    assert classify_path("migrations") == "data_migration"


def test_ac01_project_api_globs_classify_extra_paths_as_contract():
    """contract: AC-01.pre1, AC-01.post4 (undefined: rutas propias del proyecto, api_globs)"""
    plan = _plan(("Rutas", ["api/routes/users.py", "src/models/user.py", "api/routes/a/b.py"]))
    assert plan_impact(plan) == []
    result = plan_impact(plan, {"api_globs": ["api/**/*.py"]})
    assert result == [
        {
            "phase": "Fase 1: Rutas",
            "class": "api_contract",
            "label": "contrato de API",
            "files": ["api/routes/users.py", "api/routes/a/b.py"],
        }
    ]


def test_ac01_project_migration_globs_classify_but_never_docs_or_seeds():
    """contract: AC-01.pre1, AC-01.post4 (undefined: rutas propias del proyecto, migration_globs)"""
    plan = _plan(("Datos", ["src/models/user.py", "docs/api/x.md", "db/seeds/u.py"]))
    result = plan_impact(plan, {"migration_globs": ["src/models/**", "docs/**", "db/seeds/**"]})
    assert result == [
        {
            "phase": "Fase 1: Datos",
            "class": "data_migration",
            "label": "migración de datos",
            "files": ["src/models/user.py"],
        }
    ]


def test_ac01_project_signature_globs_mark_the_file_as_possible_contract_change():
    """contract: AC-01.pre1, AC-01.post4 (undefined: rutas propias del proyecto, signature_globs)"""
    plan = _plan(("Firmas", ["app/handlers.py", "app/other.py"]))
    result = plan_impact(plan, {"signature_globs": ["app/handlers.py"]})
    assert result == [
        {
            "phase": "Fase 1: Firmas",
            "class": "api_contract",
            "label": "contrato de API",
            "files": ["app/handlers.py (si cambia la firma de una función pública)"],
        }
    ]


def test_ac01_default_classification_wins_over_project_globs():
    """contract: AC-01.pre1, AC-01.post1 (undefined: rutas propias del proyecto frente a las reglas por defecto)"""
    plan = _plan(("Choque", ["openapi.yaml"]))
    result = plan_impact(plan, {"migration_globs": ["openapi.yaml"]})
    assert [e["class"] for e in result] == ["api_contract"]


@pytest.mark.parametrize(
    "impact",
    [
        "x",
        ["a"],
        {"api_globs": "x"},
        {"api_globs": ["a"] * 21},
        {"migration_globs": ["a" * 201]},
        {"signature_globs": ["*" * 21]},
        {"api_globs": [1]},
    ],
)
def test_ac01_invalid_project_globs_raise_config_error(impact):
    """contract: AC-01.pre1, AC-01.post4 (undefined: configuración inválida del proyecto)"""
    with pytest.raises(ImpactConfigError):
        plan_impact(API_PLAN, impact)


def test_ac01_project_globs_at_the_limits_are_accepted():
    """contract: AC-01.pre1, AC-01.post4 (undefined: topes de la configuración del proyecto)"""
    assert plan_impact(API_PLAN, {"api_globs": ["zzz"] * 20}) == plan_impact(API_PLAN)
    assert plan_impact(API_PLAN, {"api_globs": ["z" * 200]}) == plan_impact(API_PLAN)
    assert plan_impact(API_PLAN, {"api_globs": ["", "  "]}) == plan_impact(API_PLAN)
    assert plan_impact(API_PLAN, {}) == plan_impact(API_PLAN, None)


# ---------------------------------------------------------------------------------------------
# AC-02: la aprobación por adelantado en el triaje previo de /implement
# ---------------------------------------------------------------------------------------------


def test_ac02_plan_touching_contract_gives_the_approval_decision():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post4"""
    decision = impact_decision(API_PLAN)
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"
    assert decision["source"] == SOURCE
    assert set(decision) == {"description", "source", "decision_key"}


def test_ac02_plan_touching_migration_gives_the_approval_decision():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post4"""
    decision = impact_decision(MIGRATION_PLAN)
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"
    assert decision["source"] == SOURCE


def test_ac02_project_globs_also_trigger_the_decision():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1"""
    plan = _plan(("Rutas", ["api/routes/users.py"]))
    assert impact_decision(plan) is None
    decision = impact_decision(plan, impact={"api_globs": ["api/**/*.py"]})
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"


def test_ac02_description_names_each_phase_with_class_and_files():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    text = impact_decision(BOTH_PLAN)["description"]
    assert "Fase 1: Contrato de la API: contrato de API (openapi.yaml)" in text
    assert "Fase 2: Migración: migración de datos (migrations/0001_init.sql, db/migrate/3.rb)" in text
    assert text.index("Fase 1:") < text.index("Fase 2:")


def test_ac02_description_shows_up_to_three_files_per_phase_with_ellipsis_after():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    three = _plan(("Tres", ["migrations/a.sql", "migrations/b.sql", "migrations/c.sql"]))
    text = impact_decision(three)["description"]
    assert "(migrations/a.sql, migrations/b.sql, migrations/c.sql)" in text
    assert "…" not in text

    four = _plan(("Cuatro", ["migrations/a.sql", "migrations/b.sql", "migrations/c.sql", "migrations/d.sql"]))
    text = impact_decision(four)["description"]
    assert "(migrations/a.sql, migrations/b.sql, migrations/c.sql…)" in text
    assert "migrations/d.sql" not in text


def test_ac02_description_lists_at_most_five_phases_and_counts_the_rest():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""

    def plan_of(n: int) -> str:
        return _plan(*[(f"Paso{i}", [f"migrations/{i}.sql"]) for i in range(1, n + 1)])

    five = impact_decision(plan_of(5))["description"]
    assert "Fase 5: Paso5" in five
    assert "más" not in five

    seven = impact_decision(plan_of(7))["description"]
    for i in range(1, 6):
        assert f"Fase {i}: Paso{i}" in seven
    assert "Fase 6" not in seven
    assert "Fase 7" not in seven
    assert " y 2 más)" in seven

    six = impact_decision(plan_of(6))["description"]
    assert "Fase 6" not in six
    assert " y 1 más)" in six


def test_ac02_description_says_approval_is_recorded_and_commit_not_stopped():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post3"""
    text = impact_decision(API_PLAN)["description"]
    assert "queda registrada" in text
    assert 'skip_enforcement con measure="impact_radius"' in text
    assert "una por fase" in text
    assert "el commit no se detiene" in text
    assert "aprobación de una persona" in text


def test_ac02_plan_without_contract_lines_gives_no_decision():
    """contract: AC-02.pre1, AC-02.post1 (undefined: plan sin líneas **Criterios:**, vacío o None)"""
    no_contract = "### Fase 1: X\n**Ficheros:** openapi.yaml, migrations/0001.sql\n"
    assert impact_decision(no_contract) is None
    assert plan_impact(no_contract) == []
    assert impact_decision("") is None
    assert impact_decision(None) is None
    assert plan_impact(None) == []
    assert plan_impact("") == []


def test_ac02_decision_does_not_depend_on_anything_but_plan_and_mode():
    """contract: AC-02.pre2, AC-02.post1 (undefined: el nivel de autopilot no es un dato del módulo)"""
    assert impact_decision(API_PLAN) == impact_decision(API_PLAN)
    assert impact_decision(API_PLAN) == impact_decision(API_PLAN, mode="block")
    with pytest.raises(TypeError):
        impact_decision(API_PLAN, autopilot="aggressive")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------------------------
# AC-03: un cambio solo interno no pide aprobación; la clasificación lleva los ficheros que decidieron
# ---------------------------------------------------------------------------------------------


def test_ac03_internal_only_plan_asks_no_approval():
    """contract: AC-03.pre1, AC-03.post1"""
    assert impact_decision(INTERNAL_PLAN) is None


def test_ac03_internal_only_plan_asks_no_approval_even_in_block():
    """contract: AC-03.pre1, AC-03.post2"""
    assert impact_decision(INTERNAL_PLAN, mode="block") is None


def test_ac03_internal_only_plan_has_empty_classification():
    """contract: AC-03.pre1, AC-03.post3"""
    assert plan_impact(INTERNAL_PLAN) == []


def test_ac03_dependencies_only_plan_asks_no_approval():
    """contract: AC-03.pre1, AC-03.post1, AC-03.post2, AC-03.post3 (undefined: las dependencias cuentan como interno)"""
    plan = _plan(("Dependencias", ["package.json", "requirements.txt", "pnpm-lock.yaml"]))
    assert impact_decision(plan) is None
    assert impact_decision(plan, mode="block") is None
    assert plan_impact(plan) == []


def test_ac03_phase_without_files_or_with_only_docs_and_seeds_is_not_classified():
    """contract: AC-03.pre1, AC-03.post3 (undefined: fase sin ficheros o solo con documentación o semillas)"""
    plan = _plan(
        ("Vacía", []),
        ("Docs", ["docs/openapi.md", "migrations/README.md"]),
        ("Semillas", ["db/seeds/data.sql", "tests/fixtures/x.sql"]),
    )
    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac03_mixed_phase_lists_only_the_files_that_decided_the_class():
    """contract: AC-03.pre2, AC-03.post4"""
    plan = _plan(
        (
            "Mixta",
            ["server/core.py", "openapi.yaml", "docs/guide.md", "package.json", "api/types.proto", "migrations/0001.sql"],
        )
    )
    result = plan_impact(plan)
    assert result == [
        {
            "phase": "Fase 1: Mixta",
            "class": "api_contract",
            "label": "contrato de API",
            "files": ["openapi.yaml", "api/types.proto"],
        },
        {
            "phase": "Fase 1: Mixta",
            "class": "data_migration",
            "label": "migración de datos",
            "files": ["migrations/0001.sql"],
        },
    ]
    deciding = {f for e in result for f in e["files"]}
    assert "server/core.py" not in deciding
    assert "docs/guide.md" not in deciding
    assert "package.json" not in deciding


def test_ac03_files_keep_plan_order_and_are_cleaned():
    """contract: AC-03.pre2, AC-03.post4 (undefined: formato de las rutas del plan)"""
    plan = _plan(("Orden", ["./migrations/b.sql", "`migrations/a.sql`", "migrations/c.sql"]))
    (entry,) = plan_impact(plan)
    assert entry["files"] == ["migrations/b.sql", "migrations/a.sql", "migrations/c.sql"]


def test_ac03_duplicate_file_in_a_phase_is_listed_once_and_in_two_phases_twice():
    """contract: AC-03.pre2, AC-03.post4 (undefined: un fichero repetido en una fase o en dos fases)"""
    plan = _plan(
        ("Primera", ["openapi.yaml", "openapi.yaml", "server/core.py"]),
        ("Segunda", ["openapi.yaml"]),
    )
    result = plan_impact(plan)
    assert [(e["phase"], e["files"]) for e in result] == [
        ("Fase 1: Primera", ["openapi.yaml"]),
        ("Fase 2: Segunda", ["openapi.yaml"]),
    ]


def test_ac03_only_the_affected_phases_appear_among_several():
    """contract: AC-03.pre2, AC-03.post4"""
    result = plan_impact(BOTH_PLAN)
    assert [e["phase"] for e in result] == ["Fase 1: Contrato de la API", "Fase 2: Migración"]
    assert result[1]["files"] == ["migrations/0001_init.sql", "db/migrate/3.rb"]


# ---------------------------------------------------------------------------------------------
# AC-04: la medida en «warn» deja seguir; en «block» pide la aprobación
# ---------------------------------------------------------------------------------------------


def test_ac04_warn_does_not_stop_nor_ask():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1"""
    assert impact_decision(API_PLAN, mode="warn") is None
    assert impact_decision(MIGRATION_PLAN, mode="warn") is None
    assert impact_decision(BOTH_PLAN, mode="warn") is None


def test_ac04_block_gives_the_same_decision_as_ac02():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post2"""
    for plan in (API_PLAN, MIGRATION_PLAN, BOTH_PLAN):
        blocked = impact_decision(plan, mode="block")
        assert blocked is not None
        assert blocked["decision_key"] == "impact_radius_approval"
        assert blocked["source"] == SOURCE
        assert blocked == impact_decision(plan)


def test_ac04_off_does_not_ask():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post3"""
    assert impact_decision(API_PLAN, mode="off") is None
    assert impact_decision(MIGRATION_PLAN, mode="off") is None


def test_ac04_class_is_available_for_display_whatever_the_mode():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post4"""
    for mode in ("warn", "off", "block", None):
        impact_decision(API_PLAN, mode=mode)  # el modo no cambia la clasificación
        result = plan_impact(API_PLAN)
        assert [(e["class"], e["label"], e["files"]) for e in result] == [
            ("api_contract", "contrato de API", ["openapi.yaml"])
        ]
    # en «warn» no hay decisión que pedir, pero la clase sigue ahí para mostrarla
    assert impact_decision(API_PLAN, mode="warn") is None
    assert plan_impact(API_PLAN)[0]["class"] == "api_contract"


def test_ac04_no_mode_asks_the_safe_side():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post2 (undefined: la medida no se indica)"""
    decision = impact_decision(API_PLAN, mode=None)
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"


@pytest.mark.parametrize("mode", ["", "BLOCK", "Block", "warning", "enforce", " block"])
def test_ac04_unknown_mode_does_not_ask(mode):
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1 (undefined: valor desconocido de la medida)"""
    assert impact_decision(API_PLAN, mode=mode) is None


def test_ac04_internal_plan_in_any_mode_asks_nothing():
    """contract: AC-04.pre1, AC-04.post1, AC-04.post2 (undefined: el plan no toca contrato ni migración)"""
    for mode in ("warn", "off", "block", None):
        assert impact_decision(INTERNAL_PLAN, mode=mode) is None
