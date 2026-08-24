"""US-33 / UC-3302 — la guía de redacción cara-al-cliente existe y es coherente.

Una guía de estilo en un SKILL.md es fácil de escribir y fácil de que envejezca
sin que nadie lo note. Estos tests la anclan de dos formas:

1. **Existe y dice lo que debe decir** — la regla está en `/prd`, `/plan` la
   aplica, y hay ejemplos reales antes → después.
2. **SUS EJEMPLOS SON CIERTOS** — cada «antes» lo marca de verdad el check de
   UC-3303, y cada «después» no. Sin esto, la guía podría recomendar
   reescrituras que el propio gate seguiría señalando, o marcar como malos
   ejemplos que en realidad pasan.

La segunda es la que importa: ata la documentación (UC-3302) al código
(UC-3303) de modo que no puedan divergir en silencio.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.tools import _mutation_helpers as mh

SKILLS = Path(__file__).resolve().parents[1] / ".claude" / "skills"
PRD = SKILLS / "prd" / "SKILL.md"
PLAN = SKILLS / "plan" / "SKILL.md"


def _prd() -> str:
    return PRD.read_text(encoding="utf-8")


def _plan() -> str:
    return PLAN.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════
# Los pares antes → después de la guía, extraídos como datos
# ═══════════════════════════════════════════════════════════════════════
#
# Copiados de la guía. Si alguien edita un ejemplo del SKILL.md y rompe su
# coherencia con el checker, `test_guide_examples_match_the_checker` lo detecta.

#: Cada par lleva la prohibición que ilustra. Importa porque solo DOS de las
#: tres tienen verificación automática: `detect_ac_exposure` cubre credenciales
#: y rutas internas, pero la jerga y el lenguaje despectivo los revisa una
#: persona. Mezclarlas haría que el test exigiera al checker algo que no hace.
PARES_VERIFICABLES = [
    (
        "UC-3206/AC-03",
        "Se eliminan epic_progress_cache y web/src/lib/trelloProgress.ts; el build "
        "de web termina sin errores y sin ninguna referencia a Trello en src",
        "El portal deja de depender de Trello: el avance de las epicas se calcula sin "
        "la integracion, y una busqueda de «Trello» en el codigo del portal no devuelve "
        "ningun resultado",
    ),
    (
        "UC-202/AC-04",
        "Dado el StatusBadge (Badge.tsx), Cuando renderiza un estado, Entonces usa "
        "las CSS vars --status-* (mismo patron que SpecTree.tsx), no hex inline",
        "Dado un indicador de estado, Cuando se muestra, Entonces toma su color del "
        "sistema de diseno compartido, de modo que un cambio de marca se propaga sin "
        "tocar la pantalla",
    ),
]

#: Pares de la prohibición SIN check automático. Se listan igual —forman parte
#: de la guía y de los ≥3 que pide el AC-02— pero no se les exige al checker lo
#: que el checker no promete.
PARES_HUMANOS = [
    (
        "UC-1701/AC-02",
        "La anon key y la URL se leen de variables de entorno (PUBLIC_*), no estan "
        "hardcodeadas en el codigo fuente versionado",
        "Las claves de acceso publicas se inyectan al construir la aplicacion y no "
        "viajan en el repositorio; cambiarlas no exige tocar el codigo",
    ),
]

PARES = PARES_VERIFICABLES + PARES_HUMANOS


class TestGuideExamplesAreTrue:
    """El ancla real: la guía no puede recomendar lo que el gate rechaza."""

    @pytest.mark.parametrize(
        "origen,antes,despues", PARES_VERIFICABLES, ids=[p[0] for p in PARES_VERIFICABLES]
    )
    def test_guide_examples_match_the_checker(self, origen, antes, despues):
        """El «antes» se marca, el «después» no.

        Si un ejemplo dejara de cumplirse, la guía estaría enseñando a reescribir
        hacia algo que el propio gate sigue señalando — o marcando como malo algo
        que en realidad pasa. Cualquiera de las dos la vuelve inútil.
        """
        assert mh.detect_ac_exposure(antes), f"el «antes» de {origen} ya no se marca"
        assert mh.detect_ac_exposure(despues) == [], (
            f"la reescritura propuesta para {origen} sigue marcada: "
            f"{mh.detect_ac_exposure(despues)}"
        )

    @pytest.mark.parametrize(
        "origen,antes,despues", PARES_HUMANOS, ids=[p[0] for p in PARES_HUMANOS]
    )
    def test_jargon_examples_are_not_machine_checked(self, origen, antes, despues):
        """La tercera prohibición NO tiene check automático, y se dice.

        `detect_ac_exposure` cubre credenciales y rutas internas. La jerga y el
        lenguaje despectivo los revisa una persona.

        El caso de `UC-1701/AC-02` lo demuestra: menciona «anon key», pero esa
        clave es PÚBLICA por diseño —viaja en el bundle del navegador— así que
        el check no la marca, y hace bien. Lo que sobra ahí es «hardcodeadas»,
        que ninguna regex debería intentar juzgar.

        Este test fija esa frontera: si algún día el checker empezara a marcar
        este «antes», sería un falso positivo y habría que revisarlo.
        """
        assert mh.detect_ac_exposure(antes) == [], (
            f"el checker empezó a marcar {origen}: probable falso positivo, "
            "«anon key» es una clave pública"
        )
        assert "hardcode" in antes.lower(), "el ejemplo debe ilustrar jerga interna"

    @pytest.mark.parametrize("origen,antes,despues", PARES, ids=[p[0] for p in PARES])
    def test_rewrites_are_still_verifiable(self, origen, antes, despues):
        """La reescritura no puede ganar en discreción lo que pierde en rigor.

        La regla dice explícitamente que NO autoriza vaguedades bonitas. Si un
        «después» dejara de pasar el gate de testabilidad, la guía estaría
        cambiando un problema por otro.
        """
        assert mh.validate_ac_text(despues) == [], (
            f"la reescritura de {origen} dejó de ser verificable: "
            f"{mh.validate_ac_text(despues)}"
        )


# ═══════════════════════════════════════════════════════════════════════
# AC-01 — la regla está en /prd
# ═══════════════════════════════════════════════════════════════════════


class TestRuleInPrd:
    def test_rule_section_exists(self):
        assert "Regla de redaccion cara-al-cliente" in _prd()

    @pytest.mark.parametrize(
        "prohibicion", ["Credenciales", "Rutas de fichero internas", "despectivo"]
    )
    def test_the_three_prohibitions_are_stated(self, prohibicion):
        """AC-01: credenciales, rutas internas y lenguaje despectivo."""
        assert prohibicion in _prd(), f"la guía no menciona: {prohibicion}"

    def test_states_why(self):
        """La razón, no solo la norma: un AC puede acabar proyectado."""
        texto = _prd()
        assert "proyectado" in texto
        assert "D7" in texto

    def test_says_what_does_not_change(self):
        """Una guía que solo prohíbe se lee como censura y se ignora."""
        texto = _prd()
        assert "sigue teniendo que ser verificable" in texto
        assert "set_ac_internal" in texto, (
            "la guía debe decir que un AC interno legítimo se MARCA, no se reescribe"
        )


# ═══════════════════════════════════════════════════════════════════════
# AC-02 — al menos 3 ejemplos reales antes → después
# ═══════════════════════════════════════════════════════════════════════


class TestRealExamples:
    def test_at_least_three_rewrite_examples(self):
        texto = _prd()
        antes = texto.count("> ❌")
        despues = texto.count("> ✅")
        assert antes >= 3, f"solo {antes} ejemplos de «antes»"
        assert antes == despues, f"{antes} «antes» y {despues} «después» — desparejados"

    @pytest.mark.parametrize("origen", [p[0] for p in PARES])
    def test_examples_cite_their_real_origin(self, origen):
        """AC-02: tomados de AC REALES del ecosistema, con su id.

        Citar el id es lo que hace comprobable que no están inventados: se puede
        ir al board y leerlos.
        """
        assert origen in _prd(), f"el ejemplo {origen} no declara su origen"

    def test_declares_they_are_not_invented(self):
        assert "No son inventados" in _prd()


# ═══════════════════════════════════════════════════════════════════════
# AC-03 — /plan aplica la misma regla
# ═══════════════════════════════════════════════════════════════════════


class TestRuleInPlan:
    def test_plan_applies_the_rule(self):
        assert "Regla de redaccion cara-al-cliente" in _plan()

    def test_plan_says_a_file_path_in_an_ac_is_a_uc_failure(self):
        """AC-03, literal: es fallo de la UC, no un detalle de estilo."""
        texto = _plan()
        assert "cite una ruta de fichero es un fallo de la\nUC" in texto or (
            "ruta de fichero" in texto and "fallo de la" in texto
        )

    def test_plan_distinguishes_plan_from_ac(self):
        """La trampa concreta de /plan: el plan SÍ habla de ficheros, el AC no.

        Sin esta distinción la regla es inaplicable desde este skill, porque su
        salida natural está llena de rutas legítimas.
        """
        texto = _plan()
        assert "el plan puede nombrarlos, el AC no" in texto

    def test_plan_does_not_duplicate_the_rule(self):
        """La regla completa vive en un único sitio.

        Duplicarla en los dos skills garantiza que divergirán: se corrige una y
        se olvida la otra. `/plan` referencia y resume; no copia.
        """
        plan = _plan()
        assert "prd/SKILL.md" in plan, "/plan debe apuntar a la guía canónica"
        assert "No se\nduplica aquí" in plan or "no se duplica" in plan.lower()
