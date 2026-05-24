# Architectural Decision: Multi-document canonical registry

**Status**: Accepted
**Date**: 2026-05-25
**Version**: v6.0.0 (UC-D005, US-D04)
**Authors**: Jesús Pérez + Claude

## Context

v5.29.0 introdujo dos documentos canónicos bajo `doc/app/`: `app_prd.md` y `app_spec.md`. La implementación cableaba estos dos docs en varios lugares hardcoded:

- `server/app_docs/sync.py:38-39` — constantes `PRD_PATH`, `SPEC_PATH`
- `server/app_docs/sync.py:82-138` — `verify_app_docs_in_sync` con 2 ramas `if prd_path.exists():` / `if spec_path.exists():`
- `server/app_docs/sync.py:141-158` — `record_sync_signature` con misma duplicación
- `server/app_docs/sync.py:166-179` — `EVENT_ZONE_MAP` dict literal con tuples `("app_prd", ...)` / `("app_spec", ...)`
- `.claude/hooks/app-docs-sync-guard.mjs:34-35` — mismo patrón en Node.js
- `.claude/hooks/app-docs-sync-guard.mjs:136-139` — `checkDoc('app_prd', ...)` + `checkDoc('app_spec', ...)`
- `server/tools/onboarding.py:upgrade_project` — implícitamente no soportaba crear docs nuevos en upgrade

Para v6.0 "Discovery Foundations" se introduce un **tercer** documento canónico `app_market.md` (nivel producto: ICPs, JTBDs globales, NSM). Si la implementación replicara el patrón v5.29.x, cada doc canónico futuro (v6.x+ podría añadir `app_research.md`, `app_metrics.md`, etc.) seguiría requiriendo modificar 6+ archivos en lockstep. Es deuda técnica que se compone.

**Discovery viene para quedarse** (decisión del usuario 2026-05-24). El cap arquitectural del PRD original (3 US, 1 doc canónico) es insuficiente — necesitamos base arquitectural permanente que sostenga v6.x+ sin re-refactorizar.

## Decision

Crear un **registro único de documentos canónicos** que sea la source-of-truth para todo el sistema `app_docs`. Patrón:

```python
# server/app_docs/registry.py

@dataclass(frozen=True)
class CanonicalDoc:
    id: str
    path: str
    introduced_in: str  # semver
    template_path: str
    required_zones: Mapping[str, ZoneKind]
    event_zone_map: Mapping[str, list[str]]

CANONICAL_DOCS: list[CanonicalDoc] = [
    CanonicalDoc(id="app_prd",    path="doc/app/app_prd.md",    introduced_in="5.29.0", ...),
    CanonicalDoc(id="app_spec",   path="doc/app/app_spec.md",   introduced_in="5.29.0", ...),
    CanonicalDoc(id="app_market", path="doc/app/app_market.md", introduced_in="6.0.0",  ...),
]
```

Todo el resto del sistema itera sobre `CANONICAL_DOCS`:

- `sync.py:verify_app_docs_in_sync` itera sobre `docs_for_version(engine_version_at_onboard)`
- `sync.py:record_sync_signature` itera
- `sync.py:EVENT_ZONE_MAP` se reconstruye en import time desde `build_event_zone_map()` (preserva el shape `{event: [(doc_id, zone_id), ...]}` para backwards compat)
- `.claude/hooks/app-docs-sync-guard.mjs` lee `templates/canonical_docs.json` (descriptor generado desde Python source) e itera
- `upgrade_project` itera para crear plantillas vacías de docs `introduced_in > engine_version_at_onboard`

**Añadir un doc canónico nuevo en v6.x+ es ahora**: 1 plantilla + 1 entry en `CANONICAL_DOCS` + regenerar JSON descriptor. **Sin tocar `sync.py`, hooks, skills, ni tools.** Validado en UC-D006: la PR que añade `app_market.md` cumple este cap.

### Sub-decisiones

**D-10: Python source-of-truth + JSON regenerado** (PRD §11).

Opciones evaluadas:
- (a) Python source-of-truth + JSON generado por script. Verificación en CI.
- (b) JSON source-of-truth + parsers en Python y Node.js.
- (c) Duplicación honesta con test de sincronización.

Elegida (a) porque:
- Mantiene el patrón existente del repo (Python es donde vive la lógica).
- El descriptor JSON es trivial de regenerar y verificar (`tests/test_canonical_docs_sync.py`).
- Permite tipado fuerte en Python (dataclass + ZoneKind enum) sin perder simplicidad en el hook Node.js.
- Falla rápida si desincronizados (CI block).

Script de regeneración: `.quality/scripts/regenerate-canonical-docs-json.py`. CI ejecuta `--check` flag para verificar.

**D-11: `engine_version_at_onboard` → política conservadora con "unknown"** (PRD §11).

Opciones evaluadas:
- (a) Inferir desde git log de `meta.json` o asumir versión mínima compatible.
- (b) Marcar `"unknown"` siempre + política conservadora documentada.
- (c) Preguntar al usuario en primer `upgrade_project` post-v6.0.

Elegida (b) porque:
- No pretende saber lo que no sabe (más honesto).
- La política conservadora (solo verifica docs `introduced_in <= 5.29.0`) hace que proyectos v5.x preexistentes vean comportamiento idéntico al pre-refactor.
- Trade-off: usuarios v5.x con `app_market.md` ya rellenado manualmente no recibirán warnings de drift sobre ese doc hasta que seteen manualmente `specbox.engine_version_at_onboard` a su versión real. Documentado en CHANGELOG como caveat.

## Alternativas descartadas

### Polimorfismo (subclases de `CanonicalDoc` por tipo)

Considerado: `AppPRD(CanonicalDoc)`, `AppSpec(CanonicalDoc)`, `AppMarket(CanonicalDoc)` con `render()`, `validate()` polimórficos.

Descartado porque:
- **Over-engineering** para 3 docs. La lógica de render es trivial (renderers por zone_id, no por doc).
- Los docs no tienen comportamiento diferenciado real — solo metadatos diferentes.
- Añadir un doc nuevo requeriría 1 plantilla + 1 entry, no 1 plantilla + 1 entry + 1 clase + 1 registro.

### Plugin system (descubrimiento dinámico)

Considerado: cargar `CanonicalDoc` entries desde un directorio `server/app_docs/canonical/*.py` con auto-discovery.

Descartado porque:
- No hay 3rd-party canonical docs ni los habrá (es feature interna del engine).
- Auto-discovery introduce surprise factor (¿qué docs hay realmente?).
- Más complejo de testear y debuggear.

### Mantener el patrón v5.29.x con if/else explícito

Considerado: simplemente añadir `app_market.md` con un tercer bloque `if market_path.exists():` y un tercer `checkDoc('app_market', ...)` en el hook.

Descartado porque:
- El propio refactor sería trivial (3 horas), pero la próxima vez (v6.1) sería igual de costoso.
- Cada doc nuevo añade O(N) líneas duplicadas en N puntos del código (N=6+).
- Las migraciones rotas en futuras versiones serían cuestión de tiempo.

## Consequences

### Positivas

- **Extensibilidad arquitectural**: añadir doc canónico v6.x+ es trivial (1 entry + 1 plantilla).
- **Reducción de duplicación**: `sync.py` pierde ~30% de líneas duplicadas (medible con `lizard`).
- **Backwards compat total**: API externa preserved. `read_app_docs_tool(doc_ids=None)` reproduce comportamiento previo. Hook fallback a hardcoded `app_prd`+`app_spec` si JSON descriptor falta (proyectos v5.x).
- **Trazabilidad version-aware**: `introduced_in` permite que proyectos v5.x vean comportamiento idéntico al pre-refactor (el hook ignora `app_market.md` que no existe en su versión).
- **Documentación viva**: el registro ES la documentación de qué docs canónicos existen, en qué versión, con qué zonas.

### Negativas / costes

- **Coordinación Python ↔ JSON**: cada cambio en `registry.py` requiere regenerar `templates/canonical_docs.json`. Mitigado con script + test en CI (`tests/test_canonical_docs_sync.py`). Riesgo PL-04 / R-12 del plan.
- **Política `"unknown"`**: usuarios v5.x preexistentes pierden warnings de drift sobre docs nuevos hasta setear manualmente `engine_version_at_onboard`. Documentado.
- **Frozen dataclass**: si en el futuro queremos mutar entries en runtime (ej. extensión opt-in por proyecto), el `frozen=True` requiere ajuste. Aceptable porque la mutación dinámica no está en el roadmap.

### Cómo extender en futuras versiones

Para añadir un doc canónico nuevo (ej. `app_research.md` en v6.2):

1. Crear `templates/app_research.md.template` con marcadores de zona.
2. Añadir entry en `server/app_docs/registry.py`:
   ```python
   CanonicalDoc(
       id="app_research",
       path="doc/app/app_research.md",
       introduced_in="6.2.0",
       template_path="templates/app_research.md.template",
       required_zones={...},
       event_zone_map={...},
   ),
   ```
3. Ejecutar: `python3 .quality/scripts/regenerate-canonical-docs-json.py`.
4. Commit con `tests/test_canonical_docs_sync.py` verde.

**No requiere modificar**: `sync.py`, `app-docs-sync-guard.mjs`, `verify_app_docs`, `record_app_docs_signature`, ningún skill, `upgrade_project` (el bucle ya lo crea automáticamente para proyectos cuyo `engine_version_at_onboard < 6.2.0`).

## Notes

- El registro NO incluye renderers de zonas (`_render_zone_body`). Esos siguen como dispatcher centralizado en `sync.py` indexado por `zone_id`. Cuando un doc nuevo tiene zonas auto con renderer custom, se añade el case en `_render_zone_body`. Considerado pero descartado: registrar renderer functions en cada `CanonicalDoc.zone_renderers: dict[str, Callable]` — over-engineering hasta que tengamos 5+ docs con renderers diversos.
- El campo `status="template-pristine"` en zonas (zones.py) es propiedad cross-cutting, no específica del registro. Sirve para diferenciar "plantilla recién creada por upgrade" vs "doc inicializado por el usuario". El hook y el verifier lo respetan.
