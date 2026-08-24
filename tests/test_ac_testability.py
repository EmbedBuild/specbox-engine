"""US-33 / UC-3304 — el gate de testabilidad de AC deja de estar invertido.

Estos tests corren en cualquier sitio: `validate_ac_text` es pura y sin I/O.

El corpus NO está inventado. Los 18 AC de US-11 son los del board del
orquestador, copiados literalmente: es la US del espejo dual-backend, entregada
con `tests/test_dual_backend.py` y dogfoodeada en producción sobre un cliente
real. El gate anterior marcaba los 18 como `not_testable`. Un AC verificado por
tests automatizados no puede ser no testable, y ese contraste es lo que define
el arreglo.
"""

from __future__ import annotations

import pytest

from server.tools import _mutation_helpers as mh

# ═══════════════════════════════════════════════════════════════════════
# Corpus congelado — AC reales del board (2026-08-24)
# ═══════════════════════════════════════════════════════════════════════

#: Los 18 AC de US-11 (espejo dual-backend). Entregada CON suite automatizada.
#: El gate anterior marcaba los 18. AC-01 exige que no marque ninguno.
US11_ACS = [
    "AC-01: Una escritura con éxito en ambos backends → ambos reflejan el cambio.",
    "AC-02 (CRÍTICO): El espejo lanza excepción en una escritura → la tool devuelve el resultado del primario, NO falla, y se emite un log estructurado de drift.",
    "AC-03: Cualquier lectura → solo el primario es consultado; el espejo nunca.",
    "AC-04: item_id primario ≠ espejo → el wrapper resuelve por id lógico (UC-XXX/US-XX) vía find_item_by_field contra su propio board_id antes de escribir en el espejo; si no existe, loguea 'missing mirror item' y continúa.",
    "AC-05: close() cierra ambos backends; un fallo cerrando el espejo no impide cerrar el primario.",
    "AC-01: Sin 'mirror' en BACKEND_STATE_KEY → get_session_backend devuelve el backend simple actual (backward-compat exacto).",
    "AC-02: Con 'mirror' y primario ≠ native → devuelve DualBackendWrapper(primary, NativeBackend(...)).",
    "AC-03 (Frontier 2): el sub-dict 'mirror' solo contiene project_id + dev_token; nunca DSN.",
    "AC-04: Nuevo store_mirror_native_credentials(ctx, project_id, dev_token) persiste el sub-dict 'mirror' en BACKEND_STATE_KEY.",
    "AC-01: Fallo escribiendo cualquiera de los 3 lugares (registry projects.json / app_spec.md zona tracking_backend / settings.local.json) → rollback total, ninguno queda a medias.",
    "AC-02: detect_project_backend sigue devolviendo el primario; un nuevo campo 'mirror' expone el espejo.",
    "AC-01: enable_mirror con primario native → rechazo fail-fast con code=MIRROR_ON_NATIVE_FORBIDDEN.",
    "AC-02: enable_mirror hace validate_auth del espejo + backfill inicial: el espejo Native arranca con el mismo conteo US/UC/AC que el primario.",
    "AC-03: enable_mirror persiste 'mirror' en los 3 lugares de verdad vía la transacción atómica.",
    "AC-04: disable_mirror revierte a single-backend sin pérdida en el primario.",
    "AC-01: Cubre los AC-01..AC-05 de UC-1101, con foco en la garantía crítica AC-02 vía fallo inyectado en el espejo: resultado del primario y latencia del flujo idénticos con y sin espejo caído (0 fallos propagados, 0 rollbacks).",
    "AC-02: Cubre el rechazo primario-native (MIRROR_ON_NATIVE_FORBIDDEN) y la resolución por id lógico.",
    "AC-03: Verifica backward-compat: sin 'mirror' en config, el comportamiento es idéntico al baseline (suite existente sin regresión).",
]

#: Criterios GENUINAMENTE no verificables. La red que impide que el arreglo se
#: convierta en un sello de goma: subir la aprobación no vale de nada si estos
#: dejan de detectarse.
#:
#: Los tres primeros llevan `AC-0X` delante a propósito — sin el lookbehind de
#: `_MEASUREMENT_RE`, el número del propio id contaba como medición y redimía al
#: calificativo, dejándolos pasar limpios.
CORPUS_NEGATIVO = [
    "la app debe ser rapida",
    "AC-05: la app es rapida",
    "US-11 tiene buena experiencia de usuario",
    "buena experiencia de usuario",
    "la interfaz es intuitiva y moderna",
    "el sistema es robusto y escalable",
    "navegacion comoda",
]

#: Criterios verificables cuyo verbo NO estaba en la lista inicial. Se
#: descubrieron midiendo contra el board real y quedan aquí como red: son
#: exactamente el tipo de falso positivo que este cambio viene a eliminar.
CORPUS_POSITIVO_REAL = [
    "Un conteo fila a fila por tabla antes y despues de la migracion arroja cifras identicas",
    "La migracion es repetible: ejecutarla dos veces produce exactamente el mismo resultado",
    "Al cambiar cualquier filtro, el feed se recarga via useActivity con los nuevos params",
    "Las graficas reflejan el scope y los filtros activos",
    "El export respeta el scoping por rol y los filtros activos",
    "Cerrar un AC en el board se refleja en el portal en la siguiente carga de la pantalla",
]


# ═══════════════════════════════════════════════════════════════════════
# AC-01 — los AC de US-11 dejan de estar marcados
# ═══════════════════════════════════════════════════════════════════════


class TestUS11NoLongerFlagged:
    @pytest.mark.parametrize("texto", US11_ACS, ids=range(len(US11_ACS)))
    def test_us11_ac_passes(self, texto):
        """AC-01: ninguno de los 18 se marca como no verificable.

        Son AC de una US entregada con suite automatizada y dogfoodeada en
        producción. Si el gate los rechaza, mide otra cosa.
        """
        issues = mh.validate_ac_text(texto)
        assert "no_observable_outcome" not in issues, f"marcado sin resultado observable: {texto[:70]}"
        assert "not_testable" not in issues, f"marcado como no testable: {texto[:70]}"

    def test_us11_passes_as_a_whole(self):
        """La cifra del AC-01: 0 de 18 marcados."""
        marcados = [t for t in US11_ACS if mh.validate_ac_text(t)]
        assert marcados == [], f"{len(marcados)} de {len(US11_ACS)} AC de US-11 siguen marcados"


# ═══════════════════════════════════════════════════════════════════════
# AC-02 — lo genuinamente vago SIGUE detectándose
# ═══════════════════════════════════════════════════════════════════════


class TestVagueStillCaught:
    @pytest.mark.parametrize("texto", CORPUS_NEGATIVO)
    def test_vague_criterion_is_flagged(self, texto):
        """AC-02: la red que impide que el arreglo sea un sello de goma.

        Subir la tasa de aprobación no vale nada si estos dejan de detectarse.
        La métrica de éxito de esta UC no es la tasa: es **tasa alta con el
        corpus negativo aún detectado**.
        """
        assert mh.validate_ac_text(texto), f"criterio vago aprobado: {texto!r}"

    def test_debe_no_longer_launders_a_vague_criterion(self):
        """El caso que estaba INVERTIDO: «debe» aprobaba cualquier cosa.

        Con la regla anterior, meter un «debe» decorativo bastaba para pasar el
        gate sin mejorar el criterio — el incentivo era redactar para el linter.
        """
        assert "subjective_language" in mh.validate_ac_text("la app debe ser rapida")

    def test_a_measurement_redeems_a_subjective_word(self):
        """«rápida» es una impresión; «en menos de 200 ms» es un hecho.

        La medición es lo que separa un calificativo vacío de uno respaldado, y
        por eso un AC puede decir «rápida» y aprobar si además mide.
        """
        assert mh.validate_ac_text("AC-03: la home responde en menos de 200 ms aunque sea rapida") == []


# ═══════════════════════════════════════════════════════════════════════
# AC-04 — dos problemas distintos, dos etiquetas distintas
# ═══════════════════════════════════════════════════════════════════════


class TestDistinctVerdicts:
    def test_missing_outcome_and_subjective_are_different_tags(self):
        """AC-04: el informe deja de emitir un único motivo agregado."""
        sin_resultado = mh.validate_ac_text("el modulo de facturacion")
        subjetivo = mh.validate_ac_text("la respuesta debe ser rapida")

        assert "no_observable_outcome" in sin_resultado
        assert "subjective_language" not in sin_resultado

        assert "subjective_language" in subjetivo
        assert "no_observable_outcome" not in subjetivo

        assert set(sin_resultado) != set(subjetivo), (
            "dos AC con problemas distintos siguen recibiendo la misma etiqueta"
        )

    def test_not_testable_is_kept_as_compat_alias(self):
        """`not_testable` acompaña a la etiqueta específica durante una versión.

        Nada en el código ramifica sobre su valor —el único consumidor pasa las
        etiquetas como strings al skill— así que mantenerlo cuesta cero y evita
        romper informes históricos y lectores humanos.
        """
        for texto in ("el modulo de facturacion", "la respuesta debe ser rapida"):
            issues = mh.validate_ac_text(texto)
            assert "not_testable" in issues

    def test_a_passing_ac_has_no_tags_at_all(self):
        assert mh.validate_ac_text("mark_ac preserva el valor de internal al cambiar done") == []


# ═══════════════════════════════════════════════════════════════════════
# Falsos positivos reales encontrados midiendo contra el board
# ═══════════════════════════════════════════════════════════════════════


class TestRealWorldFalsePositives:
    @pytest.mark.parametrize("texto", CORPUS_POSITIVO_REAL)
    def test_verifiable_criterion_is_not_flagged(self, texto):
        """Criterios verificables cuyo verbo no estaba en la lista inicial.

        Salieron de medir contra los 547 AC del board, no de imaginarlos. Son
        la evidencia de que `_OUTCOME_VERBS` es una lista y toda lista tiene
        cola — y la red que impide que la cola crezca sin que nadie lo note.
        """
        assert mh.validate_ac_text(texto) == [], f"falso positivo: {texto[:70]}"


# ═══════════════════════════════════════════════════════════════════════
# Las reglas de longitud siguen vivas
# ═══════════════════════════════════════════════════════════════════════


class TestLengthRulesSurvive:
    """Medidas sobre el board, `too_short` y `vague` no dispararon NUNCA (0 de
    537). Eso no significa que sobren: significa que ese board no los provoca.
    Se conservan y se cubren para que el arreglo de la tercera regla no se lleve
    por delante a las otras dos."""

    def test_too_short(self):
        assert "too_short" in mh.validate_ac_text("corto")

    def test_vague_by_length(self):
        issues = mh.validate_ac_text("texto de 15 car")
        assert "vague" in issues
        assert "too_short" not in issues
