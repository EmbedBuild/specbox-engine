"""UC-12606 · El gobierno depende del radio de impacto del cambio real.

Pruebas de aceptación generadas desde contract.json (AC-01..AC-04) contra las funciones públicas de
``server/impact_radius.py``: ``classify_path``, ``plan_impact`` e ``impact_decision``. Sin base de datos,
sin red y sin disco: el módulo es puro y recibe el texto del plan.

Lo que viven en el hook JS (el commit detenido, el exit 0/2, el registro en el tablero y en
``.quality/logs/impact-radius.jsonl``) queda fuera: el contrato solo recoge lo que este módulo observa.
"""

from __future__ import annotations

import inspect

import pytest

from server.impact_radius import (
    MAX_IMPACT_GLOBS,
    ImpactConfigError,
    classify_path,
    impact_decision,
    plan_impact,
)

API = "api_contract"
MIG = "data_migration"
API_LABEL = "contrato de API"
MIG_LABEL = "migración de datos"
DECISION_KEY = "impact_radius_approval"
DECISION_SOURCE = "plan · fases con contrato de API o migración de datos"


def _plan(*phases: tuple[str, list[str]], criteria: bool = True) -> str:
    """Un plan de /plan: una fase por (título, ficheros), con su línea de criterios y de ficheros."""
    out = ["# Plan de prueba", ""]
    for index, (title, files) in enumerate(phases, start=1):
        out.append(f"### {title}")
        if criteria:
            out.append(f"**Criterios:** UC-12606 AC-{index:02d}")
        out.append(f"**Ficheros:** {', '.join(files)}")
        out.append("")
    return "\n".join(out)


PLAN_CONTRATO = _plan(("Fase 1: Contrato", ["openapi.yaml", "src/app.py"]))
PLAN_MIGRACION = _plan(("Fase 1: Datos", ["migrations/0001_init.sql", "src/db.py"]))
PLAN_INTERNO = _plan(
    ("Fase 1: Interna", ["src/util.py", "package.json", "README.md"]),
    ("Fase 2: Pruebas", ["tests/test_util.py", "tests/fixtures/data.sql", "seeds/seed.sql"]),
)
PLAN_MIXTO = _plan(
    ("Fase 1: Interna", ["src/util.py", "pyproject.toml"]),
    ("Fase 2: Contrato", ["api/openapi.yaml", "src/routes.py", "docs/api.md"]),
    ("Fase 3: Datos", ["db/migrate/2024_add_col.rb", "src/models.py"]),
    ("Fase 4: Interna 2", ["src/other.py"]),
)


# ---------------------------------------------------------------------------------------------------------
# AC-01 · el cambio se clasifica por lo que toca y la clase aparece en el mensaje
# ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "openapi.yaml",
        "openapi.yml",
        "openapi.json",
        "api/openapi.json",
        "openapi-v2.yaml",
        "swagger.yml",
        "docs/swagger.json",
        "service.proto",
        "proto/api.proto",
        "api/types.graphqls",
        "schema.graphql",
        "api/schema-v2.graphql",
    ],
)
def test_ac01_contratos_de_api_son_api_contract(path):
    """contract: AC-01.pre1, AC-01.post1"""
    assert classify_path(path) == API


@pytest.mark.parametrize(
    "path",
    [
        "migrations/0001_init.sql",
        "server/db/migrations/0002_x.py",
        "alembic/versions/abc_add_col.py",
        "db/migrate/2024_create_users.rb",
        "schema.prisma",
        "prisma/schema.prisma",
        "scripts/backup.sql",
        "queries/report.sql",
        "migrations/",
        "db/migrate/",
    ],
)
def test_ac01_migraciones_de_datos_son_data_migration(path):
    """contract: AC-01.pre1, AC-01.post2"""
    assert classify_path(path) == MIG


@pytest.mark.parametrize(
    "path",
    [
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "go.mod",
        "src/app.py",
        "server/tools/x.py",
        "tests/test_x.py",
        "types.graphql",
        "README.md",
        "openapi.md",
    ],
)
def test_ac01_dependencias_y_codigo_interno_no_son_contrato_ni_migracion(path):
    """contract: AC-01.pre1, AC-01.post3"""
    assert classify_path(path) is None


@pytest.mark.parametrize(
    "path, expected",
    [
        ("./openapi.yaml", API),
        ("/openapi.yaml", API),
        ("`openapi.yaml`", API),
        ("  openapi.yaml  ", API),
        ("api\\openapi.yaml", API),
        (".\\migrations\\0001.sql", MIG),
        ("`./db/migrate/2024_x.rb`", MIG),
        ("./src/app.py", None),
    ],
)
def test_ac01_la_ruta_se_limpia_antes_de_clasificar(path, expected):
    """contract: AC-01.pre1, AC-01.post1, AC-01.post2, AC-01.post3"""
    assert classify_path(path) == expected


def test_ac01_plan_impact_clasifica_cada_fase_por_sus_ficheros():
    """contract: AC-01.pre2, AC-01.post4"""
    result = plan_impact(PLAN_MIXTO)

    assert [(e["phase"], e["class"], e["label"]) for e in result] == [
        ("Fase 2: Contrato", API, API_LABEL),
        ("Fase 3: Datos", MIG, MIG_LABEL),
    ]
    # Cada entrada trae exactamente su título, su clase, su etiqueta y sus ficheros.
    assert all(set(e) == {"phase", "class", "label", "files"} for e in result)


def test_ac01_la_etiqueta_de_cada_clase_es_la_del_mensaje():
    """contract: AC-01.pre2, AC-01.post4"""
    only_api = plan_impact(PLAN_CONTRATO)
    only_mig = plan_impact(PLAN_MIGRACION)

    assert [(e["class"], e["label"]) for e in only_api] == [(API, API_LABEL)]
    assert [(e["class"], e["label"]) for e in only_mig] == [(MIG, MIG_LABEL)]


def test_ac01_el_mensaje_del_triaje_nombra_la_clase_y_la_fase():
    """contract: AC-01.pre2, AC-01.post5"""
    decision = impact_decision(PLAN_MIXTO)

    assert decision is not None
    description = decision["description"]
    assert API_LABEL in description
    assert MIG_LABEL in description
    assert "Fase 2: Contrato" in description
    assert "Fase 3: Datos" in description
    # Las fases internas no se nombran.
    assert "Fase 1: Interna" not in description
    assert "Fase 4: Interna 2" not in description


def test_ac01_el_mensaje_solo_atribuye_a_cada_fase_su_propia_clase():
    """contract: AC-01.pre2, AC-01.post5"""
    solo_api = impact_decision(PLAN_CONTRATO)["description"]
    solo_migracion = impact_decision(PLAN_MIGRACION)["description"]

    assert f"Fase 1: Contrato: {API_LABEL} (" in solo_api
    assert f": {MIG_LABEL} (" not in solo_api
    assert f"Fase 1: Datos: {MIG_LABEL} (" in solo_migracion
    assert f": {API_LABEL} (" not in solo_migracion


@pytest.mark.parametrize("path", ["", "   ", "\t"])
def test_ac01_una_ruta_vacia_no_tiene_clase(path):
    """contract: AC-01.pre1, AC-01.post3"""
    assert classify_path(path) is None


@pytest.mark.parametrize("path", ["OPENAPI.yaml", "openapi.yaml.bak", "docs/openapi.yaml.md"])
def test_ac01_el_nombre_del_contrato_debe_ser_exacto(path):
    """contract: AC-01.pre1, AC-01.post3"""
    assert classify_path(path) is None


@pytest.mark.parametrize(
    "path, expected",
    [
        ("tests/fixtures/data.sql", None),
        ("seeds/seed.sql", None),
        ("db/seed.sql", None),
        ("fixtures/x.sql", None),
        ("docs/migrations/readme.md", None),
        ("migrations/README.md", None),
        # Dentro de una carpeta de migraciones, una semilla sí cuenta.
        ("server/db/migrations/seed.sql", MIG),
    ],
)
def test_ac01_semillas_y_documentacion_no_son_migracion_salvo_dentro_de_una(path, expected):
    """contract: AC-01.pre1, AC-01.post2, AC-01.post3"""
    assert classify_path(path) == expected


def test_ac01_la_misma_ruta_escrita_de_dos_formas_se_repite():
    """contract: AC-01.pre2, AC-01.post4"""
    plan = _plan(("Fase 1: Contrato", ["openapi.yaml", "./openapi.yaml"]))

    (entry,) = plan_impact(plan)

    assert entry["class"] == API
    assert entry["files"] == ["openapi.yaml", "openapi.yaml"]


# ---------------------------------------------------------------------------------------------------------
# AC-02 · contrato o migración piden aprobación de una persona, también por adelantado en el triaje
# ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("plan", [PLAN_CONTRATO, PLAN_MIGRACION, PLAN_MIXTO], ids=["api", "migracion", "mixto"])
@pytest.mark.parametrize("mode", [None, "block"], ids=["sin-medida", "block"])
def test_ac02_un_plan_con_contrato_o_migracion_pide_aprobacion_por_adelantado(plan, mode):
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1"""
    decision = impact_decision(plan, mode=mode)

    assert decision is not None
    assert decision["decision_key"] == DECISION_KEY
    assert decision["source"] == DECISION_SOURCE
    assert set(decision) == {"description", "source", "decision_key"}


def test_ac02_la_descripcion_nombra_cada_fase_con_su_clase_y_sus_ficheros():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    description = impact_decision(PLAN_MIXTO, mode="block")["description"]

    assert "Fase 2: Contrato: contrato de API (api/openapi.yaml)" in description
    assert "Fase 3: Datos: migración de datos (db/migrate/2024_add_col.rb)" in description


def test_ac02_la_descripcion_dice_que_hace_falta_una_persona_y_que_queda_registrada():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    description = impact_decision(PLAN_CONTRATO, mode="block")["description"]

    assert "necesitan la aprobación de una persona" in description
    assert "«block»" in description
    assert "queda registrada" in description
    assert "skip_enforcement" in description
    assert 'measure="impact_radius"' in description
    assert "una por fase" in description


def test_ac02_la_decision_no_depende_del_nivel_de_autopilot():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post3"""
    parameters = set(inspect.signature(impact_decision).parameters)

    # Ningún parámetro de nivel de autopilot: solo el plan, la medida y los globs del proyecto.
    assert parameters == {"plan_content", "mode", "impact"}
    # El mismo plan da siempre la misma decisión, sea cual sea el nivel con el que se llame.
    first = impact_decision(PLAN_MIXTO, mode="block")
    again = impact_decision(PLAN_MIXTO, mode="block")
    assert first == again
    assert first == impact_decision(PLAN_MIXTO)
    with pytest.raises(TypeError):
        impact_decision(PLAN_MIXTO, mode="block", level="agresivo")  # type: ignore[call-arg]


def test_ac02_un_plan_sin_linea_de_criterios_no_tiene_fases_y_no_pide_aprobacion():
    """contract: AC-02.pre1, AC-02.post1"""
    plan = _plan(("Fase 1: Contrato", ["openapi.yaml"]), criteria=False)

    assert plan_impact(plan) == []
    assert impact_decision(plan) is None
    assert impact_decision(plan, mode="block") is None


@pytest.mark.parametrize("plan", [None, "", "texto libre sin fases"])
def test_ac02_un_plan_vacio_o_sin_fases_no_pide_aprobacion(plan):
    """contract: AC-02.pre1, AC-02.post1"""
    assert plan_impact(plan) == []
    assert impact_decision(plan) is None
    assert impact_decision(plan, mode="block") is None


def test_ac02_la_decision_nombra_hasta_cinco_fases_y_cuenta_el_resto():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    cinco = _plan(*[(f"Fase {i}: Contrato {i}", ["openapi.yaml"]) for i in range(1, 6)])
    siete = _plan(*[(f"Fase {i}: Contrato {i}", ["openapi.yaml"]) for i in range(1, 8)])

    d5 = impact_decision(cinco, mode="block")["description"]
    d7 = impact_decision(siete, mode="block")["description"]

    assert "Fase 5: Contrato 5" in d5
    assert " más)" not in d5
    assert "Fase 5: Contrato 5" in d7
    assert "Fase 6: Contrato 6" not in d7
    assert "Fase 7: Contrato 7" not in d7
    assert "y 2 más" in d7


def test_ac02_la_decision_nombra_hasta_tres_ficheros_por_fase_y_el_resto_se_elide():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post2"""
    tres = _plan(("Fase 1: Datos", [f"migrations/00{i}.sql" for i in range(3)]))
    cinco = _plan(("Fase 1: Datos", [f"migrations/00{i}.sql" for i in range(5)]))

    d3 = impact_decision(tres, mode="block")["description"]
    d5 = impact_decision(cinco, mode="block")["description"]

    assert "migrations/002.sql" in d3 and "…" not in d3
    assert "migrations/002.sql…" in d5
    assert "migrations/003.sql" not in d5
    # La clasificación (plan_impact) sí lleva todos los ficheros.
    assert [e["files"] for e in plan_impact(cinco)] == [[f"migrations/00{i}.sql" for i in range(5)]]


GLOBS = {
    "api_globs": ["routes/**"],
    "migration_globs": ["db/changes/*.xml"],
    "signature_globs": ["server/tools/*.py"],
}
PLAN_GLOBS = _plan(
    (
        "Fase 1: Proyecto",
        [
            "routes/users.ts",
            "db/changes/001.xml",
            "server/tools/specs.py",
            "docs/routes/readme.md",
            "seeds/routes/x.ts",
            "notes.md",
        ],
    )
)


def test_ac02_sin_globs_del_proyecto_solo_valen_las_reglas_por_defecto():
    """contract: AC-02.pre1, AC-02.post1"""
    assert plan_impact(PLAN_GLOBS) == []
    assert impact_decision(PLAN_GLOBS, mode="block") is None


def test_ac02_los_globs_del_proyecto_amplian_contrato_migracion_y_firmas():
    """contract: AC-02.pre1, AC-02.pre2, AC-02.post1, AC-02.post2"""
    result = plan_impact(PLAN_GLOBS, GLOBS)

    assert result == [
        {
            "phase": "Fase 1: Proyecto",
            "class": API,
            "label": API_LABEL,
            "files": ["routes/users.ts", "server/tools/specs.py (si cambia la firma de una función pública)"],
        },
        {"phase": "Fase 1: Proyecto", "class": MIG, "label": MIG_LABEL, "files": ["db/changes/001.xml"]},
    ]
    decision = impact_decision(PLAN_GLOBS, mode="block", impact=GLOBS)
    assert decision["decision_key"] == DECISION_KEY
    assert "routes/users.ts" in decision["description"]
    assert "db/changes/001.xml" in decision["description"]


def test_ac02_una_semilla_o_documentacion_no_cuenta_como_migracion_por_glob():
    """contract: AC-02.pre1, AC-02.post1"""
    plan = _plan(("Fase 1: Datos", ["docs/db/changes/readme.md", "seeds/db/changes/x.xml", "db/changes/y.xml"]))

    result = plan_impact(plan, {"migration_globs": ["**/changes/**"]})

    assert [(e["class"], e["files"]) for e in result] == [(MIG, ["db/changes/y.xml"])]


@pytest.mark.parametrize(
    "impact",
    [
        "x",
        ["api_globs"],
        {"api_globs": "x"},
        {"api_globs": [1]},
        {"api_globs": ["a"] * (MAX_IMPACT_GLOBS + 1)},
        {"migration_globs": ["a" * 201]},
        {"signature_globs": ["*" * 21]},
    ],
    ids=["no-dict", "lista", "no-lista", "no-str", "demasiados", "demasiado-largo", "demasiados-comodines"],
)
def test_ac02_unos_globs_invalidos_del_proyecto_se_rechazan(impact):
    """contract: AC-02.pre1, AC-02.post1"""
    with pytest.raises(ImpactConfigError):
        plan_impact(PLAN_CONTRATO, impact)
    with pytest.raises(ImpactConfigError):
        impact_decision(PLAN_CONTRATO, mode="block", impact=impact)


def test_ac02_el_tope_de_globs_es_inclusivo_y_lo_demas_se_ignora():
    """contract: AC-02.pre1, AC-02.post1"""
    exacto = {"api_globs": [f"zz{i}" for i in range(MAX_IMPACT_GLOBS)]}

    assert plan_impact(PLAN_CONTRATO, exacto) == plan_impact(PLAN_CONTRATO)
    assert plan_impact(PLAN_CONTRATO, {}) == plan_impact(PLAN_CONTRATO)
    assert plan_impact(PLAN_CONTRATO, {"bogus": ["x"]}) == plan_impact(PLAN_CONTRATO)
    assert plan_impact(PLAN_CONTRATO, None) == plan_impact(PLAN_CONTRATO)


# ---------------------------------------------------------------------------------------------------------
# AC-03 · lo solo interno no pide aprobación y la clasificación guarda los ficheros que la decidieron
# ---------------------------------------------------------------------------------------------------------


def test_ac03_un_plan_solo_interno_no_tiene_fases_de_impacto():
    """contract: AC-03.pre1, AC-03.post1"""
    assert plan_impact(PLAN_INTERNO) == []


@pytest.mark.parametrize("mode", [None, "block"], ids=["sin-medida", "block"])
def test_ac03_un_plan_solo_interno_no_pide_aprobacion(mode):
    """contract: AC-03.pre1, AC-03.post2"""
    assert impact_decision(PLAN_INTERNO, mode=mode) is None


def test_ac03_dependencias_documentacion_y_semillas_tampoco_piden_aprobacion():
    """contract: AC-03.pre1, AC-03.post1, AC-03.post2"""
    plan = _plan(
        ("Fase 1: Dependencias", ["package.json", "pyproject.toml", "requirements.txt", "go.mod"]),
        ("Fase 2: Docs", ["README.md", "docs/guia.md", "notas.txt"]),
        ("Fase 3: Datos de prueba", ["seeds/seed.sql", "tests/fixtures/data.sql", "fixtures/x.sql"]),
    )

    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


def test_ac03_la_clasificacion_lleva_los_ficheros_que_decidieron_cada_clase():
    """contract: AC-03.pre2, AC-03.post3"""
    result = plan_impact(PLAN_MIXTO)

    by_phase = {e["phase"]: e for e in result}
    # Solo las fases de contrato o migración; las internas no aparecen.
    assert set(by_phase) == {"Fase 2: Contrato", "Fase 3: Datos"}
    # Cada entrada trae los ficheros que la decidieron y ninguno de los internos de su fase.
    assert by_phase["Fase 2: Contrato"]["files"] == ["api/openapi.yaml"]
    assert by_phase["Fase 3: Datos"]["files"] == ["db/migrate/2024_add_col.rb"]
    for entry in result:
        assert "src/routes.py" not in entry["files"]
        assert "docs/api.md" not in entry["files"]
        assert "src/models.py" not in entry["files"]


def test_ac03_un_cambio_interno_no_se_cuela_con_uno_de_contrato_en_otra_fase():
    """contract: AC-03.pre2, AC-03.post3"""
    result = plan_impact(PLAN_MIXTO)

    nombradas = {e["phase"] for e in result}
    assert "Fase 1: Interna" not in nombradas
    assert "Fase 4: Interna 2" not in nombradas
    # La decisión sí pide aprobación porque hay una fase de contrato o migración.
    assert impact_decision(PLAN_MIXTO, mode="block") is not None


def test_ac03_una_fase_con_contrato_y_migracion_da_dos_entradas_con_el_mismo_titulo():
    """contract: AC-03.pre2, AC-03.post3"""
    plan = _plan(("Fase 1: Mixta", ["src/a.py", "api/service.proto", "db/migrate/2024_x.rb", "migrations/1.sql"]))

    result = plan_impact(plan)

    assert [(e["phase"], e["class"], e["files"]) for e in result] == [
        ("Fase 1: Mixta", API, ["api/service.proto"]),
        ("Fase 1: Mixta", MIG, ["db/migrate/2024_x.rb", "migrations/1.sql"]),
    ]


def test_ac03_documentacion_dentro_de_una_carpeta_de_migraciones_no_pide_aprobacion():
    """contract: AC-03.pre1, AC-03.post1, AC-03.post2"""
    plan = _plan(("Fase 1: Docs", ["migrations/README.md", "docs/migrations/readme.md"]))

    assert plan_impact(plan) == []
    assert impact_decision(plan, mode="block") is None


# ---------------------------------------------------------------------------------------------------------
# AC-04 · en «warn» deja seguir y muestra la clase; en «block» detiene según AC-02
# ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("plan", [PLAN_CONTRATO, PLAN_MIGRACION, PLAN_MIXTO], ids=["api", "migracion", "mixto"])
def test_ac04_en_warn_no_hay_nada_que_aprobar(plan):
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1"""
    assert impact_decision(plan, mode="warn") is None


@pytest.mark.parametrize("plan", [PLAN_CONTRATO, PLAN_MIGRACION, PLAN_MIXTO], ids=["api", "migracion", "mixto"])
def test_ac04_en_warn_la_clase_del_cambio_sigue_disponible(plan):
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post2"""
    assert impact_decision(plan, mode="warn") is None

    result = plan_impact(plan)
    assert result, "la clase del cambio se sigue mostrando"
    for entry in result:
        assert entry["class"] in {API, MIG}
        assert entry["label"] in {API_LABEL, MIG_LABEL}
        assert entry["files"]
        assert entry["phase"].startswith("Fase ")


@pytest.mark.parametrize("plan", [PLAN_CONTRATO, PLAN_MIGRACION, PLAN_MIXTO], ids=["api", "migracion", "mixto"])
def test_ac04_en_block_la_decision_es_la_de_ac02_y_la_misma_que_sin_indicar_la_medida(plan):
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post3"""
    block = impact_decision(plan, mode="block")

    assert block is not None
    assert block["decision_key"] == DECISION_KEY
    assert block == impact_decision(plan)


@pytest.mark.parametrize("plan", [PLAN_CONTRATO, PLAN_MIGRACION, PLAN_MIXTO], ids=["api", "migracion", "mixto"])
def test_ac04_en_off_no_hay_nada_que_aprobar(plan):
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post4"""
    assert impact_decision(plan, mode="off") is None


@pytest.mark.parametrize("mode", ["BLOCK", "Block", "strict", "", "warning", " block"])
def test_ac04_un_valor_de_la_medida_que_no_es_block_no_pregunta(mode):
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1"""
    assert impact_decision(PLAN_CONTRATO, mode=mode) is None


def test_ac04_pasar_de_warn_a_block_es_lo_unico_que_cambia_la_decision():
    """contract: AC-04.pre1, AC-04.pre2, AC-04.post1, AC-04.post3"""
    warn = impact_decision(PLAN_MIXTO, mode="warn")
    block = impact_decision(PLAN_MIXTO, mode="block")

    assert warn is None
    assert block is not None
    # La clase del cambio se muestra igual con cualquiera de las dos medidas (plan_impact no recibe la medida).
    assert "mode" not in inspect.signature(plan_impact).parameters
    assert [e["class"] for e in plan_impact(PLAN_MIXTO)] == [API, MIG]
