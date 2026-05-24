# Plan: v6.0 "Discovery Foundations" — US-D01..D04 (6 UCs)

> Generado: 2026-05-25
> Origen: FreeForm local (board `ff-ed0c02f4565a`) | US-D01, US-D02, US-D03, US-D04
> PRD: doc/prd/discovery_module_v6_prd.md
> Estado: Pendiente
> Stitch designs: N/A (engine sin UI de producto)
> VEG: DISABLED (heredado de app_spec.md — engine sin UI de producto)

---

## Resumen

v6.0 introduce dos cosas que viajan juntas:

1. **Multi-doc Foundation (US-D04, H1)** — refactor permanente del sistema `app_docs` de un modelo hardcoded a 2 docs (PRD/SPEC) a un registro extensible de N docs. Es base arquitectural; se hace primero porque desbloquea a Discovery y a futuros docs canónicos (v6.x+).
2. **Discovery feature (US-D01..D03, H2-H4)** — módulo conversacional `/discovery` con artefactos `icp_jtbd.md` por feature + `app_market.md` por proyecto, trazabilidad ICP→JTBD→AC→E2E, drift detection.

Backwards compatibility total con proyectos v5.x: `discovery.gate_mode=off` default en upgrade, `upgrade_project` crea plantilla `app_market.md` pristine pero no afecta comportamiento hasta que el usuario invoque `/discovery`. 11 open decisions del PRD resueltas.

---

## Análisis UI (Fase 0)

**N/A** — Feature de plataforma (engine + skills + tools MCP). No hay UI de producto. No hay componentes Stitch ni VEG.

---

## Análisis técnico — puntos de integración verificados

| Punto | Ubicación | Hallazgo relevante para el plan |
|-------|-----------|---------------------------------|
| Constantes hardcoded PRD/SPEC | `server/app_docs/sync.py:38-39` | `PRD_PATH = "doc/app/app_prd.md"`, `SPEC_PATH = "doc/app/app_spec.md"`. Eliminar en UC-D005. |
| 2 ramas if duplicadas en verify | `server/app_docs/sync.py:82-138` | `verify_app_docs_in_sync` tiene 2 bloques `if prd_path.exists():` / `if spec_path.exists():` con misma lógica. Iterar sobre registry. |
| 2 ramas if duplicadas en record | `server/app_docs/sync.py:141-158` | `record_sync_signature` idem. Iterar sobre registry. |
| EVENT_ZONE_MAP hardcoded | `server/app_docs/sync.py:166-179` | Dict `{event: [(doc, zone_id), ...]}` con app_prd/app_spec hardcoded. Mover a `event_zone_map` por doc dentro de cada `CanonicalDoc`. |
| Hook duplicado del patrón Python | `.claude/hooks/app-docs-sync-guard.mjs:34-35` | `PRD_PATH`/`SPEC_PATH` const en JS también. Lee descriptor JSON nuevo `templates/canonical_docs.json`. |
| Hook llamadas duplicadas | `.claude/hooks/app-docs-sync-guard.mjs:136-139` | `checkDoc('app_prd', ...)` + `checkDoc('app_spec', ...)`. Iterar. |
| upgrade_project | `server/tools/onboarding.py:816-932` | Regenera CLAUDE.md/settings/team-config/quality-baseline. NO toca `doc/app/`. UC-D005 AC-10 lo extiende para iterar sobre `CANONICAL_DOCS` y crear plantillas de docs `introduced_in > engine_version_at_onboard` cuando el archivo NO existe. |
| onboard_project | `server/tools/onboarding.py:566-700+` | NO copia app_prd.md.template ni app_spec.md.template — eso lo hace `/app-init`. UC-D005 AC-05 añade campo `engine_version_at_onboard` capturado aquí. |
| Migración v5.29 precedente | `server/app_docs/migration_v529.py` | Patrón directo para `detect_v60_migration_case`. CaseId Literal + MigrationPlan dataclass + dispatcher de 10 casos. UC-D005 sigue el mismo patrón con 8 casos para v6.0. |
| Template app_prd existente | `templates/app_prd.md.template` | 6 zonas con marcadores `<!-- @specbox:zone start kind="manual\|auto\|hybrid" id="..." -->`. Patrón a seguir para `app_market.md.template`. |
| Parser de zonas | `server/app_docs/zones.py` | `parse_document`, `replace_zone_body`, `compute_signature`. Lee marcadores con regex. UC-D005 AC-13 añade soporte para `status="template-pristine"`. |
| Hook signature lib | `.claude/hooks/app-docs-sync-guard.mjs:48-81` | Replica el cómputo de signature de Python en JS (ZONE_RE + ATTR_RE + sha256). Mantener; solo cambia la fuente de la lista de docs. |
| /app-init skill | `.claude/skills/app-init/SKILL.md` | Modos init/refresh/upgrade-zones. UC-D005 extiende refresh para detectar missing canonical docs introducidos en versiones > engine_version_at_onboard. |
| /app-sync skill | `.claude/skills/app-sync/SKILL.md` | Lee `verify_app_docs(project_path)`. La refactorización de la tool MCP es invisible al skill (sigue funcionando igual con doc_ids=None). |
| evaluate_autopilot_decision catálogo | `server/app_docs/autopilot.py:66+` | 19 decision_keys hardcoded. UC-D003 añade `discovery_completeness_gate` (20). |
| Tools MCP a refactorizar (5) | `server/tools/onboarding.py` y `server/app_docs/*.py` | `read_app_docs_tool`, `apply_app_docs_sync`, `record_app_docs_signature`, `detect_app_docs_drift`, `verify_app_docs` — todas iteran. Signatura externa preservada (param opcional `doc_ids: list[str] = None`). |
| Skill discovery (nuevo) | `.claude/skills/discovery/SKILL.md` | Crear en UC-D001/D002. Frontmatter `context: direct` (escribe artefactos). Bilingüe ES/EN. |
| MCP tools nuevos (3) | `server/tools/discovery.py` (nuevo) | `start_discovery`, `validate_discovery_completeness`, `detect_v60_migration_case`. Registrar en `server/server.py`. |
| Hook nuevo | `.claude/hooks/pre-prd-discovery-check.mjs` | PreToolUse para invocación de `/prd`. Lee `specbox.discovery.gate_mode` de settings. |
| HTML Evidence Report | `.quality/scripts/api-evidence-generator.js` + `patrol-evidence-generator.js` + `maestro-evidence-generator.js` | Sección "Discovery alignment" nueva añadida en UC-D003 — usa template HTML extender. |
| Suite test fixtures v5.x | `tests/` | No existen fixtures de "proyecto v5.x simulado". Hay que crear `tests/fixtures/v5_29_project/`, `v5_33_project/`, `v5_35_project/` con docs canónicos representativos para AC-D005-06 y AC-D005-12. |

---

## Fases de Implementación

> Mapeo **1 UC = 1 ciclo /implement**. Orden estricto por dependencias.
> Agentes: AG-03 (backend Python + JS) en todas; AG-04 (QA) en cada UC.
> AG-01 (feature-generator) en UC-D001/D002 para diseño del skill conversacional.

---

### Milestone H1 — Foundation Multi-doc (US-D04)

#### Fase 1 — UC-D005: Refactor app_docs a registro multi-doc [AG-03]

**Dependencias**: ninguna (cimiento). **Estimado**: 12h. **Branch**: `feature/uc-d005-multi-doc-registry`.

**Cubre AC-D005-01..13 (13 ACs).**

**Sub-fases**:

1. **Crear `server/app_docs/registry.py`** [AG-03]
   - `@dataclass(frozen=True) class CanonicalDoc` con campos: `id: str`, `path: str`, `introduced_in: str` (semver), `template_path: str`, `required_zones: dict[str, ZoneKind]`, `event_zone_map: dict[str, list[str]]`.
   - `CANONICAL_DOCS: list[CanonicalDoc]` con 3 entries: app_prd (introduced_in="5.29.0"), app_spec (5.29.0), app_market (6.0.0).
   - Helper `get_doc(doc_id: str) -> CanonicalDoc | None`.
   - Helper `docs_for_version(engine_version: str) -> list[CanonicalDoc]` — filtra por `introduced_in <= engine_version`.
   - Cubre **AC-01**.

2. **Refactorizar `server/app_docs/sync.py`** [AG-03]
   - Eliminar constantes `PRD_PATH`, `SPEC_PATH`.
   - `verify_app_docs_in_sync(project_path, engine_version_at_onboard=None)`: itera sobre `CANONICAL_DOCS`. Para cada doc, si `introduced_in > engine_version_at_onboard` (con política conservadora cuando es None/unknown → solo verifica docs con `introduced_in <= "5.29.0"`), salta el chequeo. Si el doc no existe en disco, salta sin warning. Si existe, computa signature y compara con lock.
   - `record_sync_signature(project_path)`: itera sobre `CANONICAL_DOCS`, computa signature de cada doc presente y la guarda en `.quality/app_docs_sync.lock` bajo `signatures.{doc_id}`.
   - `EVENT_ZONE_MAP` se reconstruye iterando sobre `CANONICAL_DOCS` y agregando `event_zone_map` de cada doc. Sigue siendo cacheable a nivel módulo.
   - Cubre **AC-02, AC-04**.

3. **Generar descriptor JSON para el hook Node.js** [AG-03]
   - Crear script `.quality/scripts/regenerate-canonical-docs-json.py` que importa `CANONICAL_DOCS` y escribe `templates/canonical_docs.json` con shape: `[{id, path, introduced_in, template_path, required_zones_keys, event_zone_map}, ...]` (omitiendo objetos no-serializable como ZoneKind enum — convertir a string).
   - Añadir test `tests/test_canonical_docs_sync.py` que ejecuta el script y verifica que `templates/canonical_docs.json` queda byte-igual (CI failure si desincronizados). Cubre R-12 del PRD.
   - Documentar en CLAUDE.md sección nueva "Multi-doc Foundation" cómo regenerar.

4. **Refactorizar `.claude/hooks/app-docs-sync-guard.mjs`** [AG-03]
   - Eliminar `PRD_PATH`, `SPEC_PATH` const.
   - Cargar `templates/canonical_docs.json` al inicio. Si no existe (proyecto que no recibió v6.0 todavía) → fallback al patrón v5.29 (hardcoded `app_prd` + `app_spec`).
   - Loop sobre los docs: para cada uno, leer `engine_version_at_onboard` del `meta.json` del proyecto (vía `lib/config.mjs` que ya lee settings.local.json — añadir helper `getEngineVersionAtOnboard()`). Si el doc tiene `introduced_in > engine_version_at_onboard`, skip.
   - `checkDoc(doc.id, doc.path, lockedSig)` — misma función, generalizada.
   - Cubre **AC-03**.

5. **Migración meta.json: añadir `engine_version_at_onboard`** [AG-03]
   - Modificar `server/tools/onboarding.py:onboard_project` (líneas ~566-700) — al escribir `meta.json`, añadir `meta["engine_version_at_onboard"] = current_engine_version`. Capturado en `_read_engine_version(engine_path)`.
   - Modificar `upgrade_project` (líneas ~816-932) — preservar `engine_version_at_onboard` si ya existe en meta; si no existe (proyecto v5.x pre-v6.0), marcar como `"unknown"` (NO inferir, política conservadora D-11 opción b).
   - Cubre **AC-05**.

6. **Extender `upgrade_project` para crear plantillas de docs canónicos nuevos** [AG-03]
   - Tras regenerar los 4 archivos onboarding (CLAUDE.md/settings/team-config/quality-baseline), iterar sobre `CANONICAL_DOCS`. Para cada doc con `introduced_in > engine_version_at_onboard`:
     - Resolver path absoluto: `{project_repo_path}/{doc.path}`. Pero ¡cuidado!: `upgrade_project` no recibe `project_repo_path` — solo `project` name. El return son CONTENIDOS de archivos que el usuario copia. **Solución**: añadir `canonical_docs_to_create: list[{path, content}]` al return; el agente que llama copia los contenidos al proyecto destino (mismo patrón que el resto de `files` del return).
     - Leer `template_path` del registry y añadir al return.
   - Mantener invariante: NO sobrescribir archivos existentes. La verificación de existencia la hace el agente que copia. Documentar en docstring de `upgrade_project`.
   - Añadir campo `canonical_docs_created: list[dict]` al return reportando qué docs se ofrecen.
   - Cubre **AC-10, AC-11**.

7. **Marcador `status="template-pristine"` en zone parser** [AG-03]
   - Modificar `server/app_docs/zones.py:parse_document` — el regex de zonas ya parsea atributos arbitrarios; verificar que `status` se reconoce y se expone en el objeto Zone. Si no, añadir.
   - Helper `is_template_pristine(zone) -> bool` que devuelve `zone.attrs.get("status") == "template-pristine"`.
   - Modificar `verify_app_docs_in_sync` — si TODOS las zonas manuales de un doc tienen `status="template-pristine"`, el doc cuenta como "no inicializado" → no warning aunque haya signature drift (lock guarda hash de la plantilla vacía).
   - Modificar `.claude/hooks/app-docs-sync-guard.mjs` para mismo comportamiento (regex de status + skip).
   - Helper en `/discovery` y `/app-init`: cuando se escribe contenido nuevo en una zona, eliminar el atributo `status="template-pristine"` del marcador.
   - Cubre **AC-13**.

8. **Tests de regresión contra fixtures v5.x** [AG-04]
   - Crear `tests/fixtures/v5_29_project/`, `v5_33_project/`, `v5_35_project/` con `meta.json` correspondiente + `doc/app/app_prd.md` + `doc/app/app_spec.md` con contenido representativo (no plantilla pura — datos del estilo real).
   - `tests/test_multi_doc_registry_regression.py` — matriz `{v5.29, v5.33, v5.35 fixtures} × {verify, repair via apply_sync, hook signature check, /app-sync subcommands stub}`. Snapshots de output esperado. Cualquier diferencia con baseline pre-refactor → FAIL.
   - Cubre **AC-06**.

9. **Refactor de `read_app_docs_tool` con param opcional** [AG-03]
   - Añadir param `doc_ids: list[str] | None = None`. Si None, devuelve todos los docs presentes en el proyecto (iterar `CANONICAL_DOCS` filtrado por `engine_version_at_onboard`).
   - Backwards compat: callers que pasen `doc_ids=["app_prd", "app_spec"]` reciben mismo output que antes.
   - Cubre **AC-08**.

10. **Test fixture específico AC-D005-12** [AG-04]
    - `tests/test_upgrade_v5_to_v6_preserves_existing.py` — fixture de proyecto v5.35 con `app_prd.md` modificado manualmente (algún contenido no-template). Ejecuta `upgrade_project` simulado, verifica:
      - `app_prd.md` queda byte-por-byte igual al fixture original.
      - `app_spec.md` queda byte-por-byte igual.
      - `canonical_docs_to_create` en return incluye `app_market` con plantilla.
      - `engine_version_at_onboard` se preserva si existía o se marca `"unknown"` si no.
    - Cubre **AC-12**.

11. **Documento de decisión arquitectural** [AG-03]
    - Crear `doc/decisions/multi_doc_registry.md` explicando:
      - Por qué multi-doc (Discovery + futuras docs canónicas v6.x+).
      - Patrón elegido: dataclass + lista mutable; descartados subclasses (over-engineering para 3 docs), plugins (over-engineering, no hay 3rd-party).
      - Source-of-truth: Python (`registry.py`), descriptor JSON regenerado por script (D-10 opción b).
      - Política `engine_version_at_onboard`: `"unknown"` con fallback conservador (D-11 opción b).
      - Cómo extender en futuras versiones: 1 plantilla + 1 entrada en `CANONICAL_DOCS` + regenerar JSON.
    - Cubre **AC-09**.

12. **Verificación AC-07 (cap arquitectural validable)** [AG-03]
    - Documentar en el plan de UC-D006 que solo debe modificar: 1 archivo nuevo (`app_market.md.template`) + 1 entrada en `registry.py`. Si el diff de UC-D006 toca `sync.py` o el hook, el refactor de UC-D005 está incompleto → FAIL del plan.

**Fase QA total UC-D005**: tests unit (registry, parser de zonas, autopilot decision logic) + tests integración (fixtures v5.x + AC-D005-12) + verificación que docstring + decisión doc existen.

**Criterio de éxito Fase**: 147+ tests Python existentes verdes (regresión 0), 5 tests nuevos verdes, `git grep -n "PRD_PATH\|SPEC_PATH" server/app_docs/` devuelve 0 hits, `git grep -n "app_prd\\\\|app_spec" .claude/hooks/app-docs-sync-guard.mjs` devuelve 0 hits hardcoded.

---

#### Fase 2 — UC-D006: Introducción de app_market.md vía el registro [AG-03]

**Dependencias**: UC-D005 completo. **Estimado**: 2h. **Branch**: `feature/uc-d006-app-market-template`.

**Cubre AC-D006-01..05 (5 ACs).**

**Sub-fases**:

1. **Crear `templates/app_market.md.template`** [AG-03]
   - 8 zonas con marcadores según PRD §4.1.1: icps_primary (manual), anti_icps (manual), jtbds_rational (manual), jtbds_emotional (manual), north_star_metric (manual), positioning (manual), anti_features (manual), exportable_copy (auto).
   - Cada zona manual lleva `status="template-pristine"`.
   - Placeholders `{project_name}` y `{date_iso}` para sustitución (mismo patrón que app_prd.md.template).
   - Cubre **AC-01**.

2. **Añadir entry en `CANONICAL_DOCS`** [AG-03]
   - Una sola línea en `server/app_docs/registry.py`:
     ```python
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
     ```
   - Regenerar `templates/canonical_docs.json` ejecutando el script de Fase 1.3 (verificado por CI).
   - Cubre **AC-02**.

3. **Validación AC-03 — cap arquitectural** [AG-04]
   - Revisión visual del diff de la PR. Esperado:
     - `templates/app_market.md.template` (CREATE)
     - `server/app_docs/registry.py` (MODIFY: 1 entry + 15-20 líneas)
     - `templates/canonical_docs.json` (MODIFY: regenerado automáticamente)
     - Tests verdes sin tocar nada más.
   - Documentado en PR description: "Este UC valida el cap de US-D04 — si la PR toca sync.py, hook o skills, el refactor de UC-D005 es incompleto."

4. **Test fixture AC-D006-04** [AG-04]
   - `tests/test_app_market_in_v5_35_upgrade.py` — usa fixture v5.35 ya creado en UC-D005, simula upgrade a v6.0 que crea `app_market.md` plantilla pristine. Ejecuta hook `app-docs-sync-guard.mjs` (subprocess) y verifica exit 0 + no warning emitido sobre `app_market`.
   - Cubre **AC-04**.

5. **Test AC-D006-05 — output de /app-sync --check** [AG-04]
   - Modificar `/app-sync --check` output para incluir status "template-pristine" cuando aplique: `app_market: template-pristine (introduced_in 6.0.0, project_version_at_onboard 5.33.0, awaiting first /discovery)`. Test que mockea fixture v5.33 con `app_market.md` pristine y verifica el output exacto.
   - Cubre **AC-05**.

**Criterio de éxito Fase**: 5 ACs pasando, diff de PR limita el alcance, regresión 0 en proyectos sin v6.0.

---

### Milestone H2 — Discovery feature (US-D01)

#### Fase 3 — UC-D001: /discovery standard mode [AG-01 + AG-03]

**Dependencias**: UC-D005 + UC-D006 (registry funcional + app_market template). **Estimado**: 12h. **Branch**: `feature/uc-d001-discovery-standard`.

**Cubre AC-D001-01..10 (10 ACs).**

**Sub-fases**:

1. **MCP tool `start_discovery`** [AG-03]
   - Crear `server/tools/discovery.py`. Función registrada con `@mcp.tool`:
     ```python
     def start_discovery(feature_name: str, project_path: str, mode: str = "auto") -> dict:
         """Returns {discovery_id, status, artifact_path, mode_used}"""
     ```
   - Lógica: en `auto` lee `doc/app/app_market.md` y detecta si está vacío/pristine (todas las zonas con `status="template-pristine"`) → bootstrap; si tiene contenido → standard.
   - Crea `doc/discovery/<feature_name>/` y `icp_jtbd.md` con UUID + timestamp.
   - Idempotente: detecta artefacto existente y devuelve `status="resumable"`.
   - Cubre **AC-01** y soporta AC-09 (idempotencia).

2. **MCP tool `validate_discovery_completeness`** [AG-03]
   - Lee `doc/discovery/<feature_name>/icp_jtbd.md`.
   - Valida: >=1 ICP, >=1 JTBD racional por ICP, >=1 JTBD emocional por ICP, sección evidence presente (con texto o waiver), drift section resuelta.
   - Si falta cualquier elemento → `{verdict: "DISCOVERY_INCOMPLETE", missing: [...], drift: {...}}`.
   - Si todo presente → `{verdict: "READY_FOR_PRD", missing: [], drift: {...}}`.
   - Cubre soporte a AC-10.

3. **Skill `.claude/skills/discovery/SKILL.md`** [AG-01]
   - Frontmatter `context: direct`, `allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git:*)`.
   - Estructura según PRD §4.6.1: Overview / Phase 1 / Phase 2 / Phase 3 / Bootstrap mode / Qualitative gate prompts.
   - Pedagogical content inline en español E inglés (PRD §6.1-6.4): micro-justificación, ejemplos del ecosistema (PaddockManager, McProfit, Futbase, SpecBox), anti-patterns por concepto.
   - 3 preguntas fijas para qualitative gate (D-04 opción a).
   - Flujo bootstrap incluido (delegado a UC-D002 para implementación completa).
   - Cubre **AC-01..AC-07, AC-10**.

4. **Flujo conversacional 3 fases** [AG-01]
   - Phase 1 (ICP identification): lee `app_market.md`, muestra ICPs canónicos, captura selección 1-3 + ICPs nuevos. Sanity check "3 personas concretas" por ICP nuevo. **AC-02, AC-03**.
   - Phase 2 (JTBD extraction): genera drafts con LLM (D-01 opción a) usando contexto feature + descripción problema. User edita. Format enforced "Cuando X, quiero Y, para Z". Pedagogical content inline. **AC-04, AC-05**.
   - Phase 3 (validation gate): resumen + pregunta evidence (libre o waiver). Registra. **AC-06**.

5. **Output `icp_jtbd.md`** [AG-03]
   - Estructura según PRD §4.1.2. Discovery ID UUID. Timestamps ISO. **AC-07**.

6. **Verdict explícito** [AG-03]
   - Invoca `validate_discovery_completeness` al final. Output user-facing: `READY_FOR_PRD: doc/discovery/<feature>/icp_jtbd.md` o `DISCOVERY_INCOMPLETE: faltan [list]`. **AC-10**.

7. **Idempotencia + resume** [AG-03]
   - Si `icp_jtbd.md` existe parcialmente, el skill detecta y ofrece resumir o reiniciar. **AC-09**.

8. **Test E2E AC-D001-08 (tiempo)** [AG-04]
   - Test manual durante validation period — no automatizable trivialmente (depende de velocidad humana). Test automatizado: el skill ejecuta los 3 phases con respuestas mockeadas en <30s wall time (no es el target real, pero verifica que el código no tiene cuellos artificiales). Documentado.

**Criterio de éxito Fase**: 10 ACs pasando, skill invocable con `/discovery feature_test` en proyecto fixture con `app_market.md` rellenado, output `icp_jtbd.md` validado contra schema.

---

#### Fase 4 — UC-D002: /discovery bootstrap mode [AG-01 + AG-03]

**Dependencias**: UC-D001 (skill base existe). **Estimado**: 8h. **Branch**: `feature/uc-d002-discovery-bootstrap`.

**Cubre AC-D002-01..06 (6 ACs).**

**Sub-fases**:

1. **Detección automática modo bootstrap** [AG-03]
   - `start_discovery` en modo `auto` ya tiene la lógica (UC-D001 sub-fase 1). UC-D002 valida el flujo descendente.
   - Cubre **AC-01**.

2. **Mensaje pedagógico inicial** [AG-01]
   - En el skill, branch bootstrap: muestra "Antes de definir esta feature, necesitamos definir para quién es el producto entero. Esto solo se hace una vez por proyecto."
   - Cubre **AC-02**.

3. **Fase producto: 5 bloques esenciales** [AG-01]
   - Captura: ICPs primarios (1-3), no-ICPs, JTBDs racionales globales (3-5), JTBDs emocionales globales (2-3), NSM. Bloques opcionales (posicionamiento, anti-features) ofrecidos con skip option.
   - Escribe `doc/app/app_market.md` con contenido capturado, eliminando atributo `status="template-pristine"` de cada zona rellenada.
   - Cubre **AC-03**.

4. **Auto-derivación "Exportable copy"** [AG-01]
   - Genera con LLM extractos de landing headline, LinkedIn post template, elevator pitch, derivados de ICPs+JTBDs definidos. Escribe en zona auto `exportable_copy` de `app_market.md`.
   - Cubre **AC-04**.

5. **Descenso automático al modo estándar** [AG-03]
   - Tras completar `app_market.md`, el skill llama recursivamente al flujo UC-D001 con la feature solicitada.
   - Cubre **AC-05**.

6. **Test tiempo total <=75 min** [AG-04]
   - Mismo enfoque que AC-D001-08: test automatizado verifica que el código completa los pasos en <60s con mocks (target humano es 75 min). Documentado.
   - Cubre **AC-06**.

**Criterio de éxito Fase**: 6 ACs pasando, bootstrap funcional en proyecto fixture sin `app_market.md`.

---

### Milestone H3 — Pipeline integration (US-D02)

#### Fase 5 — UC-D003: Integración Discovery <-> PRD <-> Plan <-> Implement [AG-03]

**Dependencias**: UC-D001 + UC-D002 (Discovery funcional). **Estimado**: 12h. **Branch**: `feature/uc-d003-pipeline-integration`.

**Cubre AC-D003-01..07 (7 ACs).**

**Sub-fases**:

1. **`/prd` Paso 0 nuevo: detección y herencia** [AG-03]
   - Modificar `.claude/skills/prd/SKILL.md` (NOTA: si el SKILL.md viene del repo central /Users/jesusperezsanchez/.claude/skills/prd/SKILL.md, hay que decidir si se modifica ahí o se crea override local en `.claude/skills/`).
   - **DECISIÓN PENDIENTE durante implement**: ¿modificamos el global o creamos local override? Recomendación: local override en `.claude/skills/prd/SKILL.md` para no afectar otros proyectos hasta que v6.0 sea estable.
   - Paso 0 nuevo: detecta `doc/discovery/<feature_name>/icp_jtbd.md`. Si existe y verdict=READY_FOR_PRD, lee y pre-rellena "Audience" + "Success Criteria" del PRD.
   - Cubre **AC-01, AC-02**.

2. **Tagging [JR-X.Y] / [JE-X.Y] en ACs durante /prd** [AG-03]
   - Paso N nuevo: durante AC drafting, prompt "¿qué JTBD satisface este AC?". Tag se inserta en el AC.
   - Warning si AC sin tag al final del PRD.
   - Cubre **AC-03**.

3. **`/plan` chequeo de cobertura JTBD** [AG-03]
   - Modificar `.claude/skills/plan/SKILL.md` (mismo dilema global vs local).
   - Paso nuevo: lee PRD taggeado, calcula cobertura JTBD por UC. Warning si JTBD definido en discovery no tiene UC.
   - No bloqueante en v6.0.
   - Cubre **AC-04**.

4. **`/implement` qualitative gate para [JE-X.Y]** [AG-03]
   - Modificar `.claude/skills/implement/SKILL.md`.
   - Antes de marcar AC con tag JE como passed: prompt al developer con 3 preguntas reflexivas fijas (D-04 opción a) + screenshot review obligatorio.
   - Cubre **AC-05**.

5. **HTML Evidence Report extender: sección Discovery alignment** [AG-03]
   - Modificar los 3 generators (`api-evidence-generator.js`, `patrol-evidence-generator.js`, `maestro-evidence-generator.js`).
   - Sección nueva: cobertura JTBD alcanzada, AC con qualitative gate passed, AC sin JTBD tag.
   - Cubre **AC-06**.

6. **Sync bidireccional via `apply_app_docs_sync` extendido** [AG-03]
   - Añadir eventos en `EVENT_ZONE_MAP` (en realidad en `event_zone_map` de cada CanonicalDoc del registry): cambios en `icp_jtbd.md` post-PRD → warning de drift; cambios en AC sin update de JTBDs → warning inverso.
   - Cubre **AC-07**.

**Criterio de éxito Fase**: 7 ACs pasando, pipeline `/discovery → /prd → /plan → /implement` ejecutado end-to-end con feature dummy.

---

### Milestone H4 — Drift detection (US-D03)

#### Fase 6 — UC-D004: Drift detection ICP/JTBD [AG-03]

**Dependencias**: UC-D001 + UC-D006 (Discovery + app_market). **Estimado**: 6h. **Branch**: `feature/uc-d004-drift-detection`.

**Cubre AC-D004-01..06 (6 ACs, AC-06 deferred a v6.1).**

**Sub-fases**:

1. **Comparación en final de Phase 2 de UC-D001** [AG-03]
   - Modifica skill `/discovery` Phase 2: tras JTBD extraction, compara ICPs/JTBDs declarados vs `app_market.md`. Lista elementos nuevos.
   - Cubre **AC-01**.

2. **Resolución 3 vías por elemento nuevo** [AG-03]
   - Prompt por cada elemento nuevo: (a) feature_creep_rejected, (b) app_market_updated, (c) documented_exception.
   - Si (b): ofrece actualizar `app_market.md` ahí mismo (escribe en zonas correspondientes, elimina template-pristine si aplica).
   - Si (c): registra excepción con justificación obligatoria en `icp_jtbd.md` sección "Drift from app_market".
   - Si (a): marca feature como cancelada, NO genera artefacto válido para `/prd`.
   - Cubre **AC-02, AC-03, AC-04**.

3. **Hook `verify_app_market` extendido** [AG-03]
   - Refactor de `verify_app_docs`: añade chequeo de sync entre `app_market.md` y `icp_jtbd.md` de las últimas N features (default N=5). Si hay drift sistemático sin resolver (>=3 features con elementos nuevos sin resolución), warning durante invocación de cualquier slash command (vía hook session-start o similar).
   - Cubre **AC-05**.

4. **AC-06 `/discovery --review`** [AG-03]
   - **DEFERRED a v6.1** por D-08. En v6.0 NO implementar. Documentar en CHANGELOG y skill que es backlog.
   - Marca AC-06 como `done` con nota "deferred to v6.1" para no bloquear el verdict de UC-D004.

**Criterio de éxito Fase**: 5 ACs implementados + 1 deferred documented.

---

### Fase 7 — Documentación final, version bump, CHANGELOG [AG-03 + AG-04]

**Dependencias**: Fases 1-6 completas. **Estimado**: 2h. **Branch**: `feature/v6.0-docs-release`.

**Sub-fases**:

1. **Actualizar `ENGINE_VERSION.yaml`** → version 6.0.0, codename "Discovery Foundations".
2. **Actualizar `pyproject.toml`** → version 6.0.0.
3. **Actualizar `CLAUDE.md`** → version actual, codename, sección nueva "Discovery Module v6.0" + sección "Multi-doc Foundation (v6.0)".
4. **Actualizar `README.md`** → sección destacada "v6.0: Product Discovery + Multi-doc Foundation".
5. **CHANGELOG.md** entries para US-D01..D04.
6. **`server/server.py:get_engine_version`** → "6.0.0".
7. **Pre-commit hook `version-consistency-check.mjs`** verifica alineación de los 5 archivos.
8. **Tag git `v6.0.0`** (manual, NO automerge — el usuario decide cuando lanzar).
9. **Audit `run_quality_audit` score ISO 25010 >= baseline v5.35.x**.

**Criterio de éxito Fase**: version bump consistente, audit verde, CHANGELOG completo.

---

## Mapping AC → Fase

| AC | Fase | UC |
|----|------|-----|
| AC-D001-01..10 | Fase 3 | UC-D001 |
| AC-D002-01..06 | Fase 4 | UC-D002 |
| AC-D003-01..07 | Fase 5 | UC-D003 |
| AC-D004-01..06 | Fase 6 | UC-D004 (AC-06 deferred) |
| AC-D005-01..13 | Fase 1 | UC-D005 |
| AC-D006-01..05 | Fase 2 | UC-D006 |

Total ACs: 47 implementables + 1 deferred = 48.

---

## Riesgos del plan (más allá del PRD §8)

| ID | Riesgo | Mitigación |
|---|---|---|
| PL-01 | Skill `/discovery` requiere bilingüe ES/EN; QA pedagógico desigual | Generar primero ES (idioma del mantenedor), revisión EN después; usar dos beta users por idioma idealmente |
| PL-02 | Modificar skills globales (`/prd`, `/plan`, `/implement`) afecta a otros proyectos en el sistema | Override local en `.claude/skills/` del repo; promover a global cuando v6.0 sea estable |
| PL-03 | Tests de regresión fixtures v5.x requieren reconstruir estado de proyectos pasados | Crear fixtures sintéticos minimalistas representativos, no réplicas exactas |
| PL-04 | `templates/canonical_docs.json` regenerado puede crear merge conflicts en PRs paralelas | Script de regeneración idempotente; CI valida; en práctica solo cambia cuando se añade un doc canónico (raro) |
| PL-05 | `engine_version_at_onboard` "unknown" deja silenciado al hook en proyectos v5.x — usuarios no ven warnings que sí deberían ver | Documentado en CHANGELOG: usuarios v5.x pueden setear manualmente el field a la versión correcta para activar warnings completos |

---

## Notas de implementación (referencia para /implement)

- **Branches**: una por UC. NO mezclar UCs en una sola PR.
- **Auto-merge**: deshabilitado por defecto en v6.0 (decisión del usuario). PRs abiertas para review manual.
- **Tests**: cada UC debe tener tests verdes antes de PR. Regresión 0 obligatoria en suite native + canonical docs.
- **Hooks que pueden bloquear**: `spec-guard` (requiere active UC → start_uc antes de cada fase), `branch-guard` (no main), `pre-commit-lint`, `app-docs-sync-guard` (warning-only en v5.29.x, sigue así en v6.0 hasta v6.1).
- **Postgres dev local** NO requerido para Discovery — es feature de filesystem + Python + Node hooks. Sí requerido para tests de coordination que ya existen y deben seguir verdes.

---

**Fin del plan v6.0.0 — Discovery Foundations**
