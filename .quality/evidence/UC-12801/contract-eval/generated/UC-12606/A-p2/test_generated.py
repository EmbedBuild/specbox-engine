"""Pruebas de aceptación de UC-12606 «El gobierno depende del radio de impacto del cambio real».

Van contra las funciones públicas de ``server/impact_radius.py`` (el triaje de /implement): clasifican
las fases de un plan por los ficheros que declaran (contrato de API, migración de datos o nada que
pida aprobación) y deciden si el triaje pregunta por adelantado. El hook ``impact-radius-guard`` (JS),
el registro en el tablero y el nivel de autopilot no son de este módulo: ver el informe del agente.

Criterios vigentes:
  AC-01 Un hook clasifica cada cambio por lo que toca el diff (contrato de API, migración de datos,
        dependencias o código interno) y la clase aparece en su mensaje.
  AC-02 Un cambio que toca un contrato de API o una migración de datos queda detenido antes del commit
        hasta que una persona lo aprueba, también en autopilot agresivo; la aprobación se puede dar por
        adelantado en el triaje previo de /implement y queda registrada.
  AC-03 Un cambio solo interno no pide aprobación, y la clasificación queda registrada con los ficheros
        que la decidieron.
  AC-04 Con la medida en «warn», el hook muestra la clase del cambio y deja seguir; en «block», detiene
        el commit según AC-02.

Sin base de datos, red ni disco: el módulo es puro y recibe el texto del plan.
"""

from __future__ import annotations

import inspect

import pytest

from server.impact_radius import (
    LABELS,
    MAX_IMPACT_GLOBS,
    ImpactConfigError,
    classify_path,
    impact_decision,
    plan_impact,
)


def _plan(*phases: tuple[str, list[str]]) -> str:
    """Un plan de /plan: una fase por tupla (título, ficheros), con su línea de criterios."""
    lines = ["# Plan de UC-12606", ""]
    for n, (title, files) in enumerate(phases, 1):
        lines += [
            f"## Fase {n}: {title}",
            f"**Criterios:** UC-12606 AC-{n:02d}",
            f"**Ficheros:** {', '.join(files)}",
            "",
        ]
    return "\n".join(lines)


CONTRACT_PLAN = _plan(("Contrato publico", ["api/openapi.yaml", "server/handlers.py"]))
MIGRATION_PLAN = _plan(("Migracion", ["server/db/migrations/0041_nueva.sql", "server/models.py"]))
MIXED_PLAN = _plan(
    ("Contrato publico", ["api/openapi.yaml", "server/handlers.py"]),
    ("Migracion", ["server/db/migrations/0041_x.sql", "db/seed.sql", "README.md"]),
    ("Solo interno", ["server/helpers.py", "package.json", "docs/openapi.md"]),
    ("Mixta", ["proto/user.proto", "prisma/schema.prisma", "`api/schema.graphqls`", "src/app.py"]),
)


# ---------------------------------------------------------------------------------------------
# AC-01: la clasificación sale de los ficheros que se tocan, y la clase se dice en el mensaje
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "openapi.yaml", "api/openapi.json", "docs/openapi.yml", "swagger.json", "api/swagger.yaml",
    "proto/user.proto", "api/schema.graphqls", "api/types.graphqls", "schema.graphql",
    "api/schema.graphql", "schema-v2.graphql",
])
def test_ac01_un_contrato_de_api_se_clasifica_por_su_fichero(path):
    """AC-01: openapi/swagger, .proto, .graphqls y schema*.graphql son «api_contract»."""
    assert classify_path(path) == "api_contract"


@pytest.mark.parametrize("path", [
    "migrations/0001_init.sql", "db/migrate/20240101_add.rb", "alembic/versions/abc_add.py",
    "server/db/migrations/0041_x.sql", "prisma/schema.prisma", "schema.prisma", "queries/report.sql",
])
def test_ac01_una_migracion_de_datos_se_clasifica_por_su_fichero(path):
    """AC-01: carpetas migrations/, alembic/versions/, db/migrate/, .sql y schema.prisma son «data_migration»."""
    assert classify_path(path) == "data_migration"


@pytest.mark.parametrize("path", [
    # dependencias
    "package.json", "requirements.txt", "pyproject.toml", "go.mod", "pubspec.yaml", "uv.lock", "Cargo.toml",
    # código interno
    "src/main.py", "server/impact_radius.py", "lib/widgets/button.dart", "other.graphql",
])
def test_ac01_dependencias_y_codigo_interno_no_son_contrato_ni_migracion(path):
    """AC-01: dependencias y código interno no caen en ninguna de las dos clases que piden aprobación."""
    assert classify_path(path) is None


@pytest.mark.parametrize("path", [
    "README.md", "docs/openapi.md", "migrations/README.md", "migrations/notes.txt",
    "db/seed.sql", "seeds/users.sql", "tests/fixtures/data.sql", "seed_data.sql", "test/schema.sql",
])
def test_ac01_documentacion_semillas_y_fixtures_no_cuentan(path):
    """AC-01: documentación, semillas y datos de prueba fuera de una migración se tratan como internos."""
    assert classify_path(path) is None


def test_ac01_una_semilla_dentro_de_una_carpeta_de_migraciones_si_cuenta():
    """AC-01: la excepción de las semillas no vale dentro de una carpeta de migraciones."""
    assert classify_path("migrations/seeds/x.sql") == "data_migration"


@pytest.mark.parametrize("raw, expected", [
    ("./openapi.yaml", "api_contract"),
    ("/openapi.yaml", "api_contract"),
    ("`openapi.yaml`", "api_contract"),
    ("server\\migrations\\0002.sql", "data_migration"),
    ("", None),
])
def test_ac01_las_rutas_se_limpian_antes_de_clasificar(raw, expected):
    """AC-01: la ruta tal como la escribe un plan (con ./, comillas o barras de Windows) se clasifica igual."""
    assert classify_path(raw) == expected


def test_ac01_las_clases_tienen_el_nombre_que_se_dice_en_el_mensaje():
    """AC-01: la clase se nombra con su etiqueta legible."""
    assert LABELS == {"api_contract": "contrato de API", "data_migration": "migración de datos"}


def test_ac01_plan_impact_clasifica_cada_fase_con_su_clase_su_etiqueta_y_sus_ficheros():
    """AC-01: el triaje devuelve, por fase, la clase del cambio (contrato o migración) y su etiqueta."""
    plan = _plan(
        ("Contrato publico", ["api/openapi.yaml", "server/handlers.py"]),
        ("Migracion", ["server/db/migrations/0041_x.sql", "server/models.py"]),
        ("Solo interno", ["server/helpers.py"]),
    )
    assert plan_impact(plan) == [
        {"phase": "Fase 1: Contrato publico", "class": "api_contract", "label": "contrato de API",
         "files": ["api/openapi.yaml"]},
        {"phase": "Fase 2: Migracion", "class": "data_migration", "label": "migración de datos",
         "files": ["server/db/migrations/0041_x.sql"]},
    ]


def test_ac01_una_fase_con_contrato_y_migracion_da_una_entrada_por_clase():
    """AC-01: una fase que toca las dos clases sale dos veces, cada una con sus ficheros."""
    plan = _plan(("Mixta", ["proto/user.proto", "prisma/schema.prisma", "`api/schema.graphqls`", "src/app.py"]))
    assert plan_impact(plan) == [
        {"phase": "Fase 1: Mixta", "class": "api_contract", "label": "contrato de API",
         "files": ["proto/user.proto", "api/schema.graphqls"]},
        {"phase": "Fase 1: Mixta", "class": "data_migration", "label": "migración de datos",
         "files": ["prisma/schema.prisma"]},
    ]


def test_ac01_la_clase_y_los_ficheros_aparecen_en_el_mensaje_de_un_contrato():
    """AC-01: el mensaje del triaje dice «contrato de API» y el fichero que lo decide."""
    decision = impact_decision(CONTRACT_PLAN)
    assert decision is not None
    text = decision["description"]
    assert "Fase 1: Contrato publico: contrato de API (api/openapi.yaml)" in text
    assert "server/handlers.py" not in text


def test_ac01_la_clase_y_los_ficheros_aparecen_en_el_mensaje_de_una_migracion():
    """AC-01: el mensaje del triaje dice «migración de datos» y el fichero que lo decide."""
    decision = impact_decision(MIGRATION_PLAN)
    assert decision is not None
    text = decision["description"]
    assert "Fase 1: Migracion: migración de datos (server/db/migrations/0041_nueva.sql)" in text
    assert "server/models.py" not in text


def test_ac01_se_clasifica_por_lo_que_toca_el_cambio_y_no_por_palabras_del_plan():
    """AC-01: un plan que habla de «contrato de API» y «data model» pero solo toca código interno no cuenta."""
    plan = (
        "# Plan: cambio de contrato de API y data model\n\n"
        "El contrato de API y el modelo de datos no cambian: solo refactor de migraciones lentas.\n\n"
        "## Fase 1: Refactor interno\n"
        "**Criterios:** UC-12606 AC-03\n"
        "**Ficheros:** server/helpers.py, server/formatter.py\n"
    )
    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac01_los_ficheros_de_una_lista_y_con_anotacion_se_clasifican_y_un_ejemplo_en_bloque_no():
    """AC-01: una lista bajo **Ficheros:** y la anotación «(nuevo)» no estorban; un bloque de código es un ejemplo."""
    plan = (
        "## Fase 1: Lista y anotacion\n"
        "**Criterios:** UC-12606 AC-01\n"
        "**Ficheros:**\n"
        "- `server/db/migrations/0042_nueva.sql` (nuevo)\n"
        "- server/util.py\n"
        "- openapi.yaml (modificado)\n\n"
        "## Fase 2: Ejemplo en bloque\n"
        "**Criterios:** UC-12606 AC-02\n"
        "**Ficheros:** server/util.py\n\n"
        "```\n"
        "**Ficheros:** openapi.yaml, migrations/0001.sql\n"
        "```\n"
    )
    assert plan_impact(plan) == [
        {"phase": "Fase 1: Lista y anotacion", "class": "api_contract", "label": "contrato de API",
         "files": ["openapi.yaml"]},
        {"phase": "Fase 1: Lista y anotacion", "class": "data_migration", "label": "migración de datos",
         "files": ["server/db/migrations/0042_nueva.sql"]},
    ]


_PROJECT_PLAN = (
    "## Fase 1: Rutas\n"
    "**Criterios:** UC-12606 AC-01\n"
    "**Ficheros:** server/routes/users.py, server/models.py, docs/routes/readme.md\n\n"
    "## Fase 2: Datos\n"
    "**Criterios:** UC-12606 AC-02\n"
    "**Ficheros:** server/sql/0007_cambio.py, seeds/server/sql/seed.py, tests/server/sql/t.py\n\n"
    "## Fase 3: Firmas\n"
    "**Criterios:** UC-12606 AC-03\n"
    "**Ficheros:** server/tools/specs.py, server/other.py\n"
)


def test_ac01_sin_globs_del_proyecto_esos_ficheros_son_internos():
    """AC-01: sin configuración del proyecto, rutas propias del proyecto no se clasifican."""
    for impact in (None, {}, {"api_globs": [], "migration_globs": [], "signature_globs": []}):
        assert plan_impact(_PROJECT_PLAN, impact) == []


def test_ac01_los_globs_de_contrato_del_proyecto_clasifican_sus_rutas():
    """AC-01: ``api_globs`` del proyecto hace de contrato de API las rutas que casan."""
    result = plan_impact(_PROJECT_PLAN, {"api_globs": ["server/routes/**"]})
    assert result == [
        {"phase": "Fase 1: Rutas", "class": "api_contract", "label": "contrato de API",
         "files": ["server/routes/users.py"]},
    ]


def test_ac01_los_globs_de_migracion_del_proyecto_clasifican_sus_rutas_salvo_semillas_y_pruebas():
    """AC-01: ``migration_globs`` hace migración lo que casa, y las semillas y las pruebas siguen fuera."""
    result = plan_impact(_PROJECT_PLAN, {"migration_globs": ["server/sql/**"]})
    assert result == [
        {"phase": "Fase 2: Datos", "class": "data_migration", "label": "migración de datos",
         "files": ["server/sql/0007_cambio.py"]},
    ]


def test_ac01_los_ficheros_de_firmas_cuentan_como_contrato_con_su_aviso():
    """AC-01: un fichero de ``signature_globs`` es contrato de API si cambia la firma de una función pública."""
    result = plan_impact(_PROJECT_PLAN, {"signature_globs": ["server/tools/*.py"]})
    assert result == [
        {"phase": "Fase 3: Firmas", "class": "api_contract", "label": "contrato de API",
         "files": ["server/tools/specs.py (si cambia la firma de una función pública)"]},
    ]


def test_ac01_los_globs_del_proyecto_admiten_como_mucho_el_tope_y_tienen_que_ser_texto():
    """AC-01: una configuración con más globs del tope o con tipos que no son texto se rechaza."""
    assert MAX_IMPACT_GLOBS == 20
    assert plan_impact(_PROJECT_PLAN, {"api_globs": [f"g{i}" for i in range(MAX_IMPACT_GLOBS)]}) == []
    for bad in (
        {"api_globs": ["a"] * (MAX_IMPACT_GLOBS + 1)},
        {"migration_globs": ["a"] * (MAX_IMPACT_GLOBS + 1)},
        {"signature_globs": [123]},
        {"api_globs": "server/routes/**"},
        "api_globs",
    ):
        with pytest.raises(ImpactConfigError):
            plan_impact(_PROJECT_PLAN, bad)


# ---------------------------------------------------------------------------------------------
# AC-02: contrato o migración piden la aprobación de una persona, también por adelantado en el triaje
# ---------------------------------------------------------------------------------------------

def test_ac02_un_plan_con_contrato_de_api_pide_aprobacion_por_adelantado_en_el_triaje():
    """AC-02: el triaje devuelve la decisión ``impact_radius_approval`` y explica cómo queda registrada."""
    decision = impact_decision(CONTRACT_PLAN)
    assert decision is not None
    assert set(decision) == {"description", "source", "decision_key"}
    assert decision["decision_key"] == "impact_radius_approval"
    assert decision["source"] == "plan · fases con contrato de API o migración de datos"
    text = decision["description"]
    assert text.startswith("El plan cambia un contrato de API o una migración de datos (")
    assert "necesitan la aprobación de una persona" in text
    assert "si la das ahora, queda registrada" in text
    assert 'skip_enforcement con measure="impact_radius", una por fase' in text
    assert "el commit no se detiene" in text


def test_ac02_un_plan_con_migracion_de_datos_pide_aprobacion_por_adelantado_en_el_triaje():
    """AC-02: lo mismo para una migración de datos."""
    decision = impact_decision(MIGRATION_PLAN)
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"
    assert "necesitan la aprobación de una persona" in decision["description"]
    assert 'skip_enforcement con measure="impact_radius"' in decision["description"]


def test_ac02_basta_una_fase_con_contrato_entre_otras_internas_para_preguntar():
    """AC-02: un plan mixto pregunta, y la decisión es la misma con cualquier combinación de fases."""
    decision = impact_decision(MIXED_PLAN, mode="block")
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"


def test_ac02_la_decision_no_depende_del_nivel_de_autopilot():
    """AC-02: el triaje no recibe nivel de autopilot (solo plan, medida y globs): pregunta igual en todos."""
    params = inspect.signature(impact_decision).parameters
    assert list(params) == ["plan_content", "mode", "impact"]
    first = impact_decision(CONTRACT_PLAN, mode="block")
    assert first == impact_decision(CONTRACT_PLAN, mode="block")
    assert first == impact_decision(CONTRACT_PLAN)


def test_ac02_el_mensaje_nombra_cada_fase_para_aprobarla_una_a_una():
    """AC-02: la aprobación es una por fase: el mensaje lista cada fase con cambio, también las dos clases de una misma."""
    decision = impact_decision(MIXED_PLAN)
    assert decision is not None
    text = decision["description"]
    assert "Fase 1: Contrato publico: contrato de API (api/openapi.yaml)" in text
    assert "Fase 2: Migracion: migración de datos (server/db/migrations/0041_x.sql)" in text
    assert "Fase 4: Mixta: contrato de API (proto/user.proto, api/schema.graphqls)" in text
    assert "Fase 4: Mixta: migración de datos (prisma/schema.prisma)" in text


def test_ac02_el_mensaje_enseña_hasta_tres_ficheros_y_cinco_fases():
    """AC-02: el mensaje resume: tres ficheros por fase con «…» y cinco fases con «y N más»."""
    phases = [
        (f"Contrato {i}", [f"a{i}/openapi.yaml", f"a{i}/x.proto", f"a{i}/y.proto", f"a{i}/z.proto"])
        for i in range(1, 8)
    ]
    decision = impact_decision(_plan(*phases), mode="block")
    assert decision is not None
    text = decision["description"]
    assert "Fase 1: Contrato 1: contrato de API (a1/openapi.yaml, a1/x.proto, a1/y.proto…)" in text
    assert "a1/z.proto" not in text
    assert "Fase 5: Contrato 5" in text
    assert "Fase 6: Contrato 6" not in text
    assert "Fase 5: Contrato 5: contrato de API (a5/openapi.yaml, a5/x.proto, a5/y.proto…) y 2 más)" in text


# ---------------------------------------------------------------------------------------------
# AC-03: un cambio solo interno no pide aprobación y la clasificación lleva los ficheros que la decidieron
# ---------------------------------------------------------------------------------------------

def test_ac03_un_plan_solo_interno_no_pide_aprobacion():
    """AC-03: sin contrato ni migración no hay fases con impacto ni decisión, ni siquiera en «block»."""
    plan = _plan(
        ("Logica", ["server/helpers.py", "server/formatter.py"]),
        ("Pruebas", ["tests/test_helpers.py", "lib/widgets/button.dart"]),
    )
    assert plan_impact(plan) == []
    assert impact_decision(plan) is None
    assert impact_decision(plan, mode="block") is None


def test_ac03_un_plan_solo_de_dependencias_no_pide_aprobacion():
    """AC-03: package.json, requirements.txt, pyproject.toml y go.mod no piden aprobación."""
    plan = _plan(("Dependencias", ["package.json", "requirements.txt", "pyproject.toml", "go.mod", "pubspec.yaml"]))
    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac03_documentacion_semillas_y_pruebas_no_piden_aprobacion():
    """AC-03: un plan que solo toca documentación, semillas o datos de prueba es interno."""
    plan = _plan(
        ("Docs", ["README.md", "docs/openapi.md", "migrations/README.md"]),
        ("Datos de prueba", ["db/seed.sql", "seeds/users.sql", "tests/fixtures/data.sql"]),
    )
    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac03_sin_plan_no_hay_nada_que_aprobar():
    """AC-03: ni un plan ausente ni uno vacío piden aprobación."""
    assert plan_impact(None) == []
    assert plan_impact("") == []
    assert impact_decision(None, mode="block") is None
    assert impact_decision("", mode="block") is None


def test_ac03_las_fases_internas_de_un_plan_mixto_no_entran_en_la_clasificacion():
    """AC-03: solo las fases con contrato o migración salen; la fase solo interna no."""
    result = plan_impact(MIXED_PLAN)
    assert [(e["phase"], e["class"]) for e in result] == [
        ("Fase 1: Contrato publico", "api_contract"),
        ("Fase 2: Migracion", "data_migration"),
        ("Fase 4: Mixta", "api_contract"),
        ("Fase 4: Mixta", "data_migration"),
    ]
    assert all("Fase 3" not in e["phase"] for e in result)
    decision = impact_decision(MIXED_PLAN, mode="block")
    assert decision is not None
    assert "Fase 3" not in decision["description"]
    assert "server/helpers.py" not in decision["description"]


def test_ac03_la_clasificacion_lleva_solo_los_ficheros_que_la_decidieron():
    """AC-03: cada entrada lista los ficheros de su clase y deja fuera los internos, las semillas y la documentación."""
    result = plan_impact(MIXED_PLAN)
    by_key = {(e["phase"], e["class"]): e["files"] for e in result}
    assert by_key[("Fase 1: Contrato publico", "api_contract")] == ["api/openapi.yaml"]
    assert by_key[("Fase 2: Migracion", "data_migration")] == ["server/db/migrations/0041_x.sql"]
    assert by_key[("Fase 4: Mixta", "api_contract")] == ["proto/user.proto", "api/schema.graphqls"]
    assert by_key[("Fase 4: Mixta", "data_migration")] == ["prisma/schema.prisma"]
    listed = {path for files in by_key.values() for path in files}
    for internal in ("server/handlers.py", "db/seed.sql", "README.md", "package.json", "docs/openapi.md", "src/app.py"):
        assert internal not in listed


def test_ac03_una_fase_con_contrato_no_arrastra_a_las_fases_internas_de_su_plan():
    """AC-03: con una sola fase de contrato, la clasificación tiene una entrada y la interna no pide nada."""
    plan = _plan(("Interna", ["server/helpers.py"]), ("Contrato", ["openapi.yaml"]), ("Interna dos", ["lib/a.dart"]))
    assert plan_impact(plan) == [
        {"phase": "Fase 2: Contrato", "class": "api_contract", "label": "contrato de API", "files": ["openapi.yaml"]},
    ]


# ---------------------------------------------------------------------------------------------
# AC-04: «warn» deja seguir (el triaje no pregunta), «block» detiene según AC-02
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("plan", [CONTRACT_PLAN, MIGRATION_PLAN, MIXED_PLAN], ids=["contrato", "migracion", "mixto"])
def test_ac04_con_la_medida_en_warn_el_triaje_no_pregunta_y_deja_seguir(plan):
    """AC-04: en «warn» no hay nada que aprobar, aunque el plan toque contrato o migración."""
    assert impact_decision(plan, mode="warn") is None


@pytest.mark.parametrize("plan", [CONTRACT_PLAN, MIGRATION_PLAN, MIXED_PLAN], ids=["contrato", "migracion", "mixto"])
def test_ac04_con_la_medida_apagada_el_triaje_no_pregunta(plan):
    """AC-04: en «off» tampoco se pregunta."""
    assert impact_decision(plan, mode="off") is None


@pytest.mark.parametrize("plan", [CONTRACT_PLAN, MIGRATION_PLAN, MIXED_PLAN], ids=["contrato", "migracion", "mixto"])
def test_ac04_con_la_medida_en_block_el_triaje_pide_la_aprobacion(plan):
    """AC-04: en «block» el plan con contrato o migración da la decisión de AC-02."""
    decision = impact_decision(plan, mode="block")
    assert decision is not None
    assert decision["decision_key"] == "impact_radius_approval"
    assert "necesitan la aprobación de una persona" in decision["description"]


def test_ac04_sin_saber_la_medida_el_triaje_pregunta_que_es_el_lado_seguro():
    """AC-04: sin ``mode`` pregunta, y con lo mismo que en «block»."""
    assert impact_decision(CONTRACT_PLAN) is not None
    assert impact_decision(CONTRACT_PLAN) == impact_decision(CONTRACT_PLAN, mode="block")
    assert impact_decision(MIGRATION_PLAN, mode=None) == impact_decision(MIGRATION_PLAN, mode="block")


def test_ac04_la_clasificacion_no_depende_de_la_medida():
    """AC-04: en «warn» la clase del cambio sigue saliendo (solo cambia si se pregunta)."""
    expected = plan_impact(CONTRACT_PLAN)
    assert expected == [
        {"phase": "Fase 1: Contrato publico", "class": "api_contract", "label": "contrato de API",
         "files": ["api/openapi.yaml"]},
    ]
    assert impact_decision(CONTRACT_PLAN, mode="warn") is None
    assert plan_impact(CONTRACT_PLAN) == expected


def test_ac04_en_block_un_plan_solo_interno_sigue_sin_pedir_aprobacion():
    """AC-04: «block» detiene según AC-02, o sea solo contrato o migración; lo interno pasa."""
    plan = _plan(("Interna", ["server/helpers.py", "package.json"]))
    assert impact_decision(plan, mode="block") is None
    assert impact_decision(plan, mode="warn") is None
