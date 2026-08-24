"""US-33 / UC-3303 — check de exposición: AC que no deberían proyectarse.

D7 convierte los AC en entregable cara-al-cliente. Un criterio que cita las
credenciales de una cuenta o la ruta interna de un fichero deja de ser un
criterio y pasa a ser una filtración delante de quien paga el proyecto.

AVISA, NO BLOQUEA (AC-02). El objetivo es visibilidad, no fricción.

NOTA DE SEGURIDAD SOBRE EL AC-03
--------------------------------
El AC-03 ancla el check a un AC real de `potencial_digital_2026` que menciona
usuario y contraseña de la cuenta de revisión de App Store. **Su texto no se
copia aquí, ni al repo, ni a la salida de ningún test**: se referencia por id y
la verificación contra el AC real se hizo fuera de banda, consultando el board.
Lo que este fichero usa es la FORMA del criterio, no su contenido — una frase
que describe qué menciona, sin mencionar nada.
"""

from __future__ import annotations

import pytest

from server.tools import _mutation_helpers as mh

# ═══════════════════════════════════════════════════════════════════════
# AC-01 — qué se marca y qué no
# ═══════════════════════════════════════════════════════════════════════

#: Indicios reales. Deben marcarse.
EXPONEN = [
    # Credenciales por nombre
    "la contraseña de la cuenta de servicio se guarda en el vault",
    "el usuario y contraseña de la cuenta de revision de App Store estan en la ficha",
    "la api key de Stripe se inyecta como secret de la Edge Function",
    "el client secret del proveedor OAuth se rota cada 90 dias",
    "usuario: admin",
    "token: spbx_pruebafalsa123",
    # Prefijos de clave real (todos inventados, ninguno valido)
    "la clave sk_live_NOESREALSOLOFORMATO se revoca al terminar",
    "el PAT ghp_NOESREALSOLOFORMATO deja de usarse",
    # Rutas internas de codigo
    "cubierto por tests/test_dual_backend.py",
    "la logica vive en server/backends/native_backend.py y se testea aparte",
    "la migracion 0021_ac_internal.sql se aplica antes del despliegue",
]

#: Menciones inocentes. NO deben marcarse — si saltan, el aviso se vuelve ruido
#: y deja de leerse, que es la forma habitual de que un check muera.
NO_EXPONEN = [
    "el usuario ve su panel de proyectos",
    "un usuario autenticado accede al detalle de la US",
    "el usuario no miembro obtiene cero filas",
    "el dev_token se valida contra mcp_tokens antes de cada mutacion",
    "reserve_uc devuelve el token de reserva al mismo developer",
    "la sesion caduca a los 30 minutos",
    "el panel muestra el nombre del usuario y su rol",
]


class TestWhatGetsFlagged:
    @pytest.mark.parametrize("texto", EXPONEN)
    def test_exposure_is_flagged(self, texto):
        """AC-01: credenciales y rutas internas se marcan."""
        tags = mh.detect_ac_exposure(texto)
        assert "exposure_warning" in tags, f"no marcado: {texto[:60]}"

    @pytest.mark.parametrize("texto", NO_EXPONEN)
    def test_innocent_mention_is_not_flagged(self, texto):
        """La otra mitad del diseño, y la que decide si esto sirve.

        Aplicar el AC-01 al pie de la letra —marcar toda mención de «usuario» o
        «token»— señalaba **72 de 547** AC del board, y 46 eran la palabra
        «usuario» usada como ROL. Un aviso que salta en uno de cada ocho
        criterios no lo lee nadie, y un aviso que nadie lee no protege nada.
        """
        assert mh.detect_ac_exposure(texto) == [], f"falso positivo: {texto[:60]}"

    def test_categories_are_distinguished(self):
        """El informe puede decir POR QUÉ, no solo QUE."""
        cred = mh.detect_ac_exposure("la contraseña de la cuenta esta en la ficha")
        ruta = mh.detect_ac_exposure("cubierto por tests/test_dual_backend.py")

        assert "exposure_credentials" in cred
        assert "exposure_internal_path" not in cred
        assert "exposure_internal_path" in ruta
        assert "exposure_credentials" not in ruta

    def test_both_categories_can_coexist(self):
        tags = mh.detect_ac_exposure(
            "la contraseña se lee de server/config.py al arrancar"
        )
        assert {"exposure_warning", "exposure_credentials", "exposure_internal_path"} <= set(tags)

    def test_empty_text_is_not_flagged(self):
        assert mh.detect_ac_exposure("") == []
        assert mh.detect_ac_exposure("   ") == []


class TestAC03Shape:
    """AC-03 — la forma del criterio real, sin su contenido.

    El AC real (`potencial_digital_2026`, UC-083/AC-04) se verificó fuera de
    banda consultando el board por id: el check lo marca. Aquí se fija la forma
    para que el comportamiento quede cubierto por la suite sin que el texto del
    AC —que contiene credenciales— entre nunca en el repositorio.
    """

    def test_usuario_y_contrasena_de_una_cuenta_is_flagged(self):
        tags = mh.detect_ac_exposure(
            "verificar con el usuario y contraseña de la cuenta de revision de la store"
        )
        assert "exposure_credentials" in tags

    def test_accentless_spelling_is_also_caught(self):
        """`contrasena` sin ñ se escribe a menudo y no puede escaparse."""
        tags = mh.detect_ac_exposure("el usuario y contrasena de la cuenta de revision")
        assert "exposure_credentials" in tags


# ═══════════════════════════════════════════════════════════════════════
# AC-02 — avisa, pero NO bloquea
# ═══════════════════════════════════════════════════════════════════════


class TestWarnDoesNotBlock:
    def test_exposure_is_not_a_quality_issue(self):
        """Un AC puede exponer credenciales y ser impecable como criterio.

        Son dos ejes distintos. Si el aviso entrara en `validate_ac_text`,
        bajaría el `pass_rate` y bloquearía el Definition Quality Gate — que es
        justo lo que el AC-02 prohíbe.
        """
        texto = "el sistema devuelve la contraseña enmascarada en el detalle"
        assert mh.validate_ac_text(texto) == [], "el aviso se coló en las issues bloqueantes"
        assert "exposure_warning" in mh.detect_ac_exposure(texto)

    def test_the_two_checks_are_independent_functions(self):
        """No hay solapamiento de etiquetas entre los dos ejes."""
        bloqueantes = set()
        avisos = set()
        for t in EXPONEN + NO_EXPONEN:
            bloqueantes |= set(mh.validate_ac_text(t))
            avisos |= set(mh.detect_ac_exposure(t))
        assert not (bloqueantes & avisos), (
            f"etiquetas compartidas entre calidad y exposición: {bloqueantes & avisos}"
        )
