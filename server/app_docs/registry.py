"""Canonical documents registry (v6.0.0, UC-D005).

Source-of-truth única para qué documentos canónicos existen en `doc/app/`,
en qué versión del engine se introdujeron, qué zonas requieren y qué
eventos de pipeline mutan cada zona.

Antes de v6.0 (v5.29.x), el sistema `app_docs` tenía hardcoded `app_prd`
y `app_spec` en múltiples lugares (sync.py, hook, skills, tools). Esto
hacía que añadir un tercer doc canónico (`app_market.md` en v6.0) fuera
una operación frágil con 6+ puntos a actualizar.

v6.0 introduce este registro: añadir un doc canónico ahora se reduce a:
  1. Crear plantilla en `templates/<doc_id>.md.template`.
  2. Añadir una entry en `CANONICAL_DOCS` aquí.
  3. Regenerar `templates/canonical_docs.json` con el script de build
     (`.quality/scripts/regenerate-canonical-docs-json.py`).

Sin cambios en `sync.py`, hook, skills ni tools.

El descriptor JSON existe porque el hook `app-docs-sync-guard.mjs` está
en Node.js y no puede importar este módulo Python. La sincronización
Python ↔ JSON está verificada en CI (`tests/test_canonical_docs_sync.py`).

Patrón resuelto en D-10 (PRD §11): Python source-of-truth + JSON regenerado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .zones import ZoneKind


@dataclass(frozen=True)
class CanonicalDoc:
    """Descriptor de un documento canónico bajo `doc/app/`.

    Attributes:
        id: Identificador estable (ej. "app_prd", "app_market"). Usado
            como key en signatures, logs, hooks, sync state.
        path: Ruta relativa al repo del proyecto (ej. "doc/app/app_prd.md").
        introduced_in: Versión semver del engine en la que se introdujo
            este doc (ej. "5.29.0", "6.0.0"). El hook y el verificador
            ignoran este doc en proyectos cuyo `engine_version_at_onboard`
            sea inferior a este valor.
        template_path: Ruta relativa al engine donde vive la plantilla
            (ej. "templates/app_market.md.template"). Usada por
            `upgrade_project` para escribir plantillas pristine en
            proyectos que actualizan a una versión que introduce el doc.
        required_zones: Mapa de zone_id → ZoneKind esperado. Usado por
            `validate_document` para verificar que el doc tiene las
            zonas requeridas con el kind correcto.
        event_zone_map: Mapa de evento de pipeline → list[zone_id] que
            ese evento mutará en este doc. Reemplaza el dict global
            `EVENT_ZONE_MAP` hardcoded de la v5.29.x.
    """

    id: str
    path: str
    introduced_in: str  # semver
    template_path: str
    required_zones: Mapping[str, ZoneKind] = field(default_factory=dict)
    event_zone_map: Mapping[str, list[str]] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────
# Registro de documentos canónicos
# ─────────────────────────────────────────────────────────────────────
#
# Añadir un doc nuevo: insertar una entrada aquí + crear plantilla +
# regenerar templates/canonical_docs.json. NO se requiere cambiar
# ninguna otra parte del sistema app_docs.
#
CANONICAL_DOCS: list[CanonicalDoc] = [
    CanonicalDoc(
        id="app_prd",
        path="doc/app/app_prd.md",
        introduced_in="5.29.0",
        template_path="templates/app_prd.md.template",
        required_zones={
            "vision": ZoneKind.MANUAL,
            "audience": ZoneKind.MANUAL,
            "scope": ZoneKind.MANUAL,
            "success_metrics": ZoneKind.HYBRID,
            "roadmap": ZoneKind.AUTO,
            "stakeholders": ZoneKind.MANUAL,
        },
        event_zone_map={
            "complete_uc": ["roadmap"],
            "move_uc": ["roadmap"],
            "add_uc": ["roadmap"],
            "delete_uc": ["roadmap"],
            "mark_ac_batch": ["roadmap", "success_metrics"],
        },
    ),
    CanonicalDoc(
        id="app_spec",
        path="doc/app/app_spec.md",
        introduced_in="5.29.0",
        template_path="templates/app_spec.md.template",
        required_zones={
            "stack": ZoneKind.AUTO,
            "tracking_backend": ZoneKind.AUTO,
            "autopilot": ZoneKind.AUTO,
            "canonical_decisions": ZoneKind.HYBRID,
        },
        event_zone_map={
            "set_auth_token": ["tracking_backend"],
            "lockfile_change": ["stack"],
            "framework_detected": ["stack"],
            "release_version_bump": ["stack"],
            "autopilot_config_change": ["autopilot"],
            "canonical_decision_created": ["canonical_decisions"],
            "canonical_decision_revoked": ["canonical_decisions"],
        },
    ),
    CanonicalDoc(
        id="app_market",
        path="doc/app/app_market.md",
        introduced_in="6.0.0",
        template_path="templates/app_market.md.template",
        required_zones={
            "icps_primary": ZoneKind.MANUAL,
            "anti_icps": ZoneKind.MANUAL,
            "jtbds_rational": ZoneKind.MANUAL,
            "jtbds_emotional": ZoneKind.MANUAL,
            "north_star_metric": ZoneKind.MANUAL,
            "positioning": ZoneKind.MANUAL,
            "anti_features": ZoneKind.MANUAL,
            "exportable_copy": ZoneKind.AUTO,
        },
        event_zone_map={
            "app_market_icp_added": ["exportable_copy"],
            "app_market_jtbd_added": ["exportable_copy"],
            "nsm_updated": ["exportable_copy"],
        },
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Helpers de consulta
# ─────────────────────────────────────────────────────────────────────


def get_doc(doc_id: str) -> CanonicalDoc | None:
    """Devuelve el CanonicalDoc con el id dado, o None si no existe."""
    for doc in CANONICAL_DOCS:
        if doc.id == doc_id:
            return doc
    return None


def _semver_tuple(version: str) -> tuple[int, ...]:
    """Convierte '6.0.0' → (6, 0, 0) para comparación numérica.

    Tolera sufijos comunes ('6.0.0-rc.1', '6.0.0.dev0') quedándose con
    los componentes numéricos del prefijo. Si no encuentra ninguno,
    devuelve (0,) como fallback conservador.
    """
    import re

    parts = re.findall(r"\d+", version)
    if not parts:
        return (0,)
    return tuple(int(p) for p in parts)


def docs_for_version(engine_version: str | None) -> list[CanonicalDoc]:
    """Devuelve los docs canónicos que existen en la versión dada.

    Args:
        engine_version: Versión semver del engine. Si es None o "unknown",
            política conservadora: solo devuelve docs con
            `introduced_in <= "5.29.0"` (los pre-v6.0). Esto evita que
            el hook warnee sobre `app_market.md` en proyectos v5.x que
            actualizaron sin capturar `engine_version_at_onboard`.

    Resuelve D-11 (PRD §11) como opción (b): unknown + política conservadora.
    """
    if engine_version is None or engine_version == "unknown":
        # Política conservadora: solo docs pre-v6.0
        engine_version = "5.29.0"

    project_v = _semver_tuple(engine_version)
    return [
        doc
        for doc in CANONICAL_DOCS
        if _semver_tuple(doc.introduced_in) <= project_v
    ]


def build_event_zone_map() -> dict[str, list[tuple[str, str]]]:
    """Reconstruye el EVENT_ZONE_MAP global desde el registro.

    Devuelve {event: [(doc_id, zone_id), ...]} — mismo shape que el
    dict hardcoded de la v5.29.x, pero generado iterando sobre los
    `event_zone_map` por doc del registro.

    Esto preserva backwards compat para callers de `sync.py:EVENT_ZONE_MAP`
    que esperan ese shape exacto.
    """
    out: dict[str, list[tuple[str, str]]] = {}
    for doc in CANONICAL_DOCS:
        for event, zone_ids in doc.event_zone_map.items():
            out.setdefault(event, []).extend((doc.id, zid) for zid in zone_ids)
    return out
