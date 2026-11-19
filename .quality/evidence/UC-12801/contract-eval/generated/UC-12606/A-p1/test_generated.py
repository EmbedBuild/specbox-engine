"""Pruebas de aceptación de UC-12606 (el radio de impacto del cambio) contra server/impact_radius.py.

El módulo cubre la parte del criterio que se puede comprobar sin hook ni git: clasificar los ficheros
(contrato de API, migración de datos, o ninguno para dependencias y código interno), listar las fases
de un plan con su clase, y la decisión de triaje ``impact_radius_approval`` según la medida.
Cada prueba dice su criterio (AC-NN) en el nombre y en el docstring.
"""

from __future__ import annotations

import pytest

from server.impact_radius import classify_path, impact_decision, plan_impact


def _plan(*phases: tuple[str, list[str]]) -> str:
    """Un plan de /plan con una fase por (título, ficheros), cada una con su línea de criterios."""
    out = ["# UC-12606: plan de prueba", ""]
    for number, (title, files) in enumerate(phases, start=1):
        out += [
            f"### Fase {number}: {title}",
            "**Criterios:** UC-12606 AC-01",
            "**Ficheros:** " + ", ".join(files),
            "",
        ]
    return "\n".join(out)


# --------------------------------------------------------------------------------------------------
# AC-01: clasificar el cambio por lo que toca (contrato de API, migración de datos, dependencias o
# código interno) y que la clase aparezca.
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "openapi.yaml",
        "api/openapi.json",
        "docs/api/swagger.yml",
        "openapi-v2.yaml",
        "proto/user.proto",
        "api/schema.graphqls",
        "schema.graphql",
        "./api/openapi.yaml",
        "`api/openapi.yaml`",
    ],
)
def test_ac01_classify_path_api_contract(path):
    """AC-01: un fichero de contrato de API (openapi, swagger, .proto, .graphqls, schema*.graphql)."""
    assert classify_path(path) == "api_contract"


@pytest.mark.parametrize(
    "path",
    [
        "db/migrations/0001_init.sql",
        "supabase/migrations/20261119000001_tabla.sql",
        "migrations/0002_add_col.py",
        "alembic/versions/abc123_add_col.py",
        "db/migrate/20261119_add_users.rb",
        "prisma/schema.prisma",
        "schema.sql",
        "scripts/backfill.sql",
        "db/migrations/seeds/0003_datos.sql",
    ],
)
def test_ac01_classify_path_data_migration(path):
    """AC-01: una migración de datos (carpeta de migraciones, .sql, schema.prisma)."""
    assert classify_path(path) == "data_migration"


@pytest.mark.parametrize(
    "path",
    [
        "server/foo.py",
        "src/components/Button.tsx",
        "lib/main.dart",
        "package.json",
        "package-lock.json",
        "requirements.txt",
        "pyproject.toml",
        "pubspec.yaml",
        "go.mod",
        "",
        "   ",
    ],
)
def test_ac01_classify_path_internal_and_dependencies_are_not_contract_or_migration(path):
    """AC-01: dependencias y código interno no son ni contrato de API ni migración de datos (None)."""
    assert classify_path(path) is None


def test_ac01_plan_impact_reports_class_label_phase_and_files():
    """AC-01: la clase (y su etiqueta legible) aparece junto a la fase y los ficheros que la deciden."""
    plan = _plan(
        ("Contrato", ["openapi.yaml", "server/handler.py"]),
        ("Datos", ["db/migrations/0001_init.sql"]),
        ("Interno", ["server/util.py"]),
    )
    assert plan_impact(plan) == [
        {
            "phase": "Fase 1: Contrato",
            "class": "api_contract",
            "label": "contrato de API",
            "files": ["openapi.yaml"],
        },
        {
            "phase": "Fase 2: Datos",
            "class": "data_migration",
            "label": "migración de datos",
            "files": ["db/migrations/0001_init.sql"],
        },
    ]


def test_ac01_plan_impact_phase_with_both_classes_gives_one_entry_per_class():
    """AC-01: una fase que toca contrato y migración sale con las dos clases, contrato primero."""
    plan = _plan(("Mixta", ["db/migrations/0001.sql", "openapi.yaml", "server/x.py"]))
    result = plan_impact(plan)
    assert [(e["class"], e["files"]) for e in result] == [
        ("api_contract", ["openapi.yaml"]),
        ("data_migration", ["db/migrations/0001.sql"]),
    ]
    assert {e["phase"] for e in result} == {"Fase 1: Mixta"}


def test_ac01_plan_impact_classifies_with_project_api_globs():
    """AC-01: los globs de contrato del proyecto (specbox.impact.api_globs) también clasifican."""
    plan = _plan(("Rutas", ["api/routes/users.py", "server/util.py"]))
    assert plan_impact(plan) == []
    assert plan_impact(plan, {"api_globs": ["api/routes/**"]}) == [
        {
            "phase": "Fase 1: Rutas",
            "class": "api_contract",
            "label": "contrato de API",
            "files": ["api/routes/users.py"],
        }
    ]


def test_ac01_plan_impact_classifies_with_project_migration_globs():
    """AC-01: los globs de migración del proyecto (specbox.impact.migration_globs) también clasifican."""
    plan = _plan(("Cambios", ["data/changes/0001_add.py", "server/util.py"]))
    assert plan_impact(plan) == []
    assert plan_impact(plan, {"migration_globs": ["data/changes/*.py"]}) == [
        {
            "phase": "Fase 1: Cambios",
            "class": "data_migration",
            "label": "migración de datos",
            "files": ["data/changes/0001_add.py"],
        }
    ]


def test_ac01_plan_impact_signature_globs_count_as_contract_with_note():
    """AC-01: un fichero de firmas del proyecto cuenta como contrato y lo dice (si cambia la firma)."""
    plan = _plan(("Tools", ["server/tools/spec.py", "server/util.py"]))
    assert plan_impact(plan) == []
    result = plan_impact(plan, {"signature_globs": ["server/tools/*.py"]})
    assert result == [
        {
            "phase": "Fase 1: Tools",
            "class": "api_contract",
            "label": "contrato de API",
            "files": ["server/tools/spec.py (si cambia la firma de una función pública)"],
        }
    ]


def test_ac01_decision_names_the_class_of_the_change():
    """AC-01: la decisión del triaje dice la clase del cambio y la fase que la tiene."""
    plan = _plan(("Contrato", ["openapi.yaml"]), ("Datos", ["db/migrations/0001.sql"]))
    decision = impact_decision(plan)
    assert decision is not None
    assert "Fase 1: Contrato: contrato de API (openapi.yaml)" in decision["description"]
    assert "Fase 2: Datos: migración de datos (db/migrations/0001.sql)" in decision["description"]


# --------------------------------------------------------------------------------------------------
# AC-02: un cambio de contrato o de migración pide la aprobación de una persona; se puede dar por
# adelantado en el triaje previo de /implement y queda registrada.
# --------------------------------------------------------------------------------------------------


def test_ac02_contract_plan_yields_impact_radius_approval_decision():
    """AC-02: el triaje de /implement recibe la decisión impact_radius_approval para un contrato."""
    decision = impact_decision(_plan(("Contrato", ["openapi.yaml"])), mode="block")
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"
    assert decision["source"] == "plan · fases con contrato de API o migración de datos"
    assert decision["description"].startswith("El plan cambia un contrato de API o una migración de datos (")
    assert "Fase 1: Contrato: contrato de API (openapi.yaml)" in decision["description"]
    assert set(decision) == {"description", "source", "decision_key"}


def test_ac02_migration_plan_yields_impact_radius_approval_decision():
    """AC-02: una migración de datos también pide la aprobación por adelantado."""
    decision = impact_decision(_plan(("Datos", ["supabase/migrations/20261119000001_x.sql"])), mode="block")
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"
    assert "Fase 1: Datos: migración de datos (supabase/migrations/20261119000001_x.sql)" in decision["description"]


def test_ac02_decision_says_commits_need_a_person_and_the_approval_is_recorded():
    """AC-02: la decisión explica que el commit necesita a una persona y que la aprobación queda
    registrada con skip_enforcement (measure impact_radius, una por fase)."""
    description = impact_decision(_plan(("Contrato", ["openapi.yaml"])), mode="block")["description"]
    assert "Con la medida impact_radius en «block»" in description
    assert "esos commits necesitan la aprobación de una persona" in description
    assert "si la das ahora, queda registrada" in description
    assert 'skip_enforcement con measure="impact_radius", una por fase' in description
    assert "el commit no se detiene" in description


def test_ac02_decision_does_not_depend_on_an_autopilot_level():
    """AC-02: la decisión no tiene un nivel de autopilot que la relaje: el mismo plan da la misma
    decisión sin importar de dónde se pida (sin modo y con «block»)."""
    plan = _plan(("Contrato", ["openapi.yaml"]))
    assert impact_decision(plan) == impact_decision(plan, mode="block")
    assert impact_decision(plan) is not None


def test_ac02_decision_lists_every_phase_that_needs_approval():
    """AC-02: cada fase con contrato o migración consta en la decisión (una aprobación por fase)."""
    plan = _plan(
        ("Primera", ["openapi.yaml"]),
        ("Segunda", ["db/migrations/0001.sql"]),
        ("Tercera", ["schema.graphqls"]),
    )
    description = impact_decision(plan, mode="block")["description"]
    for title in ("Fase 1: Primera", "Fase 2: Segunda", "Fase 3: Tercera"):
        assert title in description


def test_ac02_decision_shows_first_three_files_of_a_phase_and_ellipsis():
    """AC-02: de cada fase se muestran como mucho tres ficheros, con «…» si hay más."""
    files = ["openapi.yaml", "v2/openapi.yaml", "v3/openapi.yaml", "v4/openapi.yaml"]
    plan = _plan(("Contratos", files))
    description = impact_decision(plan, mode="block")["description"]
    assert "(openapi.yaml, v2/openapi.yaml, v3/openapi.yaml…)" in description
    assert "v4/openapi.yaml" not in description
    assert plan_impact(plan)[0]["files"] == files


def test_ac02_decision_names_five_phases_and_counts_the_rest():
    """AC-02: con más de cinco fases afectadas, la decisión nombra cinco y cuenta las demás."""
    plan = _plan(*[(f"F{n}", ["openapi.yaml"]) for n in range(1, 7)])
    description = impact_decision(plan, mode="block")["description"]
    assert "Fase 5: F5" in description
    assert "Fase 6: F6" not in description
    assert " y 1 más)" in description


# --------------------------------------------------------------------------------------------------
# AC-03: un cambio solo interno no pide aprobación y la clasificación queda con los ficheros que la
# decidieron.
# --------------------------------------------------------------------------------------------------


def test_ac03_internal_only_plan_asks_for_no_approval():
    """AC-03: un plan solo de código interno no da fases afectadas ni decisión, tampoco en «block»."""
    plan = _plan(("Lógica", ["server/foo.py", "src/app.ts"]), ("Pruebas", ["tests/test_foo.py"]))
    assert plan_impact(plan) == []
    assert impact_decision(plan) is None
    assert impact_decision(plan, mode="block") is None


def test_ac03_dependencies_only_plan_asks_for_no_approval():
    """AC-03: un cambio solo de dependencias no pide aprobación, tampoco en «block»."""
    plan = _plan(("Dependencias", ["package.json", "package-lock.json", "requirements.txt", "go.mod"]))
    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac03_documentation_seeds_and_fixtures_are_internal():
    """AC-03: documentación, semillas y datos de prueba fuera de una carpeta de migraciones son
    internos aunque lleven .sql o estén junto a ellas."""
    files = [
        "docs/migrations/README.md",
        "doc/api/openapi-notes.md",
        "db/seeds/dev.sql",
        "tests/fixtures/data.sql",
        "seed.sql",
        "spec/data.sql",
    ]
    for path in files:
        assert classify_path(path) is None, path
    plan = _plan(("Datos de prueba", files))
    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac03_documentation_under_a_project_glob_is_still_internal():
    """AC-03: un .md dentro de los globs de migración del proyecto no cuenta como migración."""
    plan = _plan(("Notas", ["data/changes/README.md"]))
    assert plan_impact(plan, {"migration_globs": ["data/changes/**"]}) == []


def test_ac03_classification_keeps_only_the_files_that_decided_it():
    """AC-03: la clasificación lleva los ficheros que la decidieron, no los internos de la misma fase,
    y con las rutas limpias (sin «./», sin comillas invertidas)."""
    plan = _plan(
        ("Mixta", ["`./api/openapi.yaml`", "server/handler.py", "README.md", "package.json", "db/migrations/0001.sql"])
    )
    result = plan_impact(plan)
    by_class = {e["class"]: e["files"] for e in result}
    assert by_class == {
        "api_contract": ["api/openapi.yaml"],
        "data_migration": ["db/migrations/0001.sql"],
    }


def test_ac03_internal_phase_next_to_contract_phase_is_left_out_of_the_decision():
    """AC-03: en un plan con una fase de contrato y otra interna, solo la de contrato aparece en
    la decisión; la interna no pide nada."""
    plan = _plan(("Contrato", ["openapi.yaml"]), ("Interno", ["server/util.py"]))
    assert [e["phase"] for e in plan_impact(plan)] == ["Fase 1: Contrato"]
    description = impact_decision(plan, mode="block")["description"]
    assert "Fase 1: Contrato" in description
    assert "Fase 2: Interno" not in description
    assert "server/util.py" not in description


@pytest.mark.parametrize("plan", [None, "", "   \n", "Un plan sin fases ni criterios.\n\nopenapi.yaml"])
def test_ac03_plan_with_nothing_to_classify_asks_for_no_approval(plan):
    """AC-03: sin plan o sin fases con contrato legible no hay nada que clasificar ni aprobar."""
    assert plan_impact(plan) == []
    assert impact_decision(plan) is None
    assert impact_decision(plan, mode="block") is None


# --------------------------------------------------------------------------------------------------
# AC-04: con la medida en «warn» se muestra la clase y se deja seguir; en «block» se detiene según
# AC-02. Aquí: la decisión del triaje solo pregunta en «block» (o sin medida, el lado seguro).
# --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["warn", "off"])
def test_ac04_triage_does_not_ask_unless_the_measure_is_block(mode):
    """AC-04: con la medida en «warn» u «off» el triaje no pregunta y el trabajo sigue."""
    plan = _plan(("Contrato", ["openapi.yaml"]), ("Datos", ["db/migrations/0001.sql"]))
    assert impact_decision(plan, mode=mode) is None


def test_ac04_triage_asks_in_block_and_without_a_measure():
    """AC-04: en «block» el triaje pide la aprobación de AC-02; sin medida (lado seguro) también."""
    plan = _plan(("Contrato", ["openapi.yaml"]))
    in_block = impact_decision(plan, mode="block")
    assert in_block is not None
    assert in_block["decision_key"] == "impact_radius_approval"
    assert impact_decision(plan, mode=None) == in_block
    assert impact_decision(plan) == in_block


def test_ac04_class_stays_visible_whatever_the_measure():
    """AC-04: en «warn» no se pregunta, pero la clase del cambio sigue saliendo de plan_impact (es
    lo que se muestra); solo la decisión depende de la medida."""
    plan = _plan(("Contrato", ["openapi.yaml"]))
    assert impact_decision(plan, mode="warn") is None
    assert [(e["class"], e["label"]) for e in plan_impact(plan)] == [("api_contract", "contrato de API")]


@pytest.mark.parametrize("mode", ["warn", "off", "block", None])
def test_ac04_internal_change_never_asks_in_any_mode(mode):
    """AC-04: un cambio interno no se detiene en ningún modo, «block» incluido."""
    plan = _plan(("Interno", ["server/util.py", "package.json"]))
    assert impact_decision(plan, mode=mode) is None


def test_ac04_project_globs_make_the_block_decision_ask():
    """AC-04: lo que los globs del proyecto marcan como contrato se detiene en «block» y no en «warn»."""
    plan = _plan(("Rutas", ["api/routes/users.py"]))
    impact = {"api_globs": ["api/routes/**"]}
    assert impact_decision(plan, mode="warn", impact=impact) is None
    decision = impact_decision(plan, mode="block", impact=impact)
    assert decision is not None
    assert "Fase 1: Rutas: contrato de API (api/routes/users.py)" in decision["description"]
    assert impact_decision(plan, mode="block") is None
