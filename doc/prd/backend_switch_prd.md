# PRD: [US-BACKEND-SWITCH] Cambio guiado de backend entre los 4 (FreeForm/Trello/Plane/Native)

> Origen: FreeForm board specbox-engine (`ff-ed0c02f4565a`) | US-BACKEND-SWITCH
> Generado: 2026-05-22
> Tipo: PRD Técnico (feature de plataforma, sin UI de producto)

## Resumen

SpecBox tiene hoy 4 backends de spec-driven (FreeForm, Trello, Plane, Native) sobre la abstracción `SpecBackend`, pero **cambiar de uno a otro sin perder datos ni avance es solo parcialmente posible**: de los 12 pares de migración posibles, únicamente 4 están cubiertos (Trello↔Plane bidireccional + Trello/Plane→FreeForm unidireccional). Native está completamente aislado y FreeForm es un sumidero (solo recibe, nunca exporta). Esta US generaliza la migración a **N×N completo entre los 4 backends**, garantizando que el avance de ejecución (estado de UC, AC marcados, comments) y la trazabilidad de evidencias se preservan, y entrega un flujo guiado de principio a fin vía el skill `/switch-backend`.

El valor: un proyecto puede empezar en FreeForm (rápido, local, sin fricción), promocionar a Trello/Plane cuando necesita reporting a cliente, o subir a Native cuando el equipo crece a multi-dev — y volver — sin perder una sola hora de trabajo registrado.

## Alcance

### Incluye
- Migración N×N completa entre los 4 backends (los 12 pares), idempotente y aditiva (nunca borra el origen hasta confirmar).
- Generalización de `switch_backend` a los 4 backends (hoy solo trello/plane).
- Preservación del avance: estado de UC (`state`), AC marcados (`done`), comentarios, jerarquía US→UC→AC.
- Matriz de mapeo de estados bidireccional entre los 4 backends.
- Manejo del caso Native: descarte con reporte de claims/identidad/branches al salir; siembra de `expected_version` + identidad al entrar.
- Actualización transaccional de los 3 lugares que hoy quedan desincronizados tras migrar: `projects.json`, `app_spec.md` (zona auto `tracking_backend`), `.claude/settings.local.json` (`specbox.backend_type`).
- Aviso explícito del riesgo de evidencias huérfanas/stale + método de regeneración guiado (`regenerate_evidence`) con progreso por UC.
- Skill conversacional `/switch-backend` que orquesta todo el flujo de forma segura y guiada.

### No incluye
- **Migración del contenido binario de attachments** — se preservan como URLs/referencias para descarga manual (límite heredado de `migrate_to_freeform_tool`). Re-upload binario queda fuera.
- **Re-vinculación física de la evidencia** — la evidencia (`evidence/`, verdicts AG-09) NO se mueve ni se toca; vive en el filesystem independiente del board. Solo se avisa y se ofrece regenerar.
- **Migración de histórico de concurrencia Native** (claims activos, identidad de developers, branches registradas) hacia backends single-user — se descarta con reporte, no se traslada.
- **Migración multi-repo orchestrator/satellite** — fuera de v1; se asume mono-repo.
- **UI en la Sala de Máquinas** para disparar migraciones — el flujo es vía skill/tools MCP.

---

## Objetivos

1. **Cobertura N×N** — Cubrir los 12 pares de migración entre los 4 backends, no solo los 4 actuales.
2. **Cero pérdida de avance** — Garantizar que el estado de ejecución (UC state, AC done, comments) sobrevive cualquier migración, verificable con counts antes/después.
3. **Consistencia post-migración** — Que tras migrar, los 3 lugares de verdad (registry, app_spec, settings) reflejen el nuevo backend sin drift.
4. **Transparencia del riesgo** — Que el usuario sea informado del riesgo sobre evidencias y tenga un método claro y con progreso para regenerarlas.
5. **Flujo guiado seguro** — Una experiencia de principio a fin con preview obligatorio, confirmación literal y reporte auditable.

---

## Estado Actual vs Propuesto

### ACTUAL (4 de 12 pares):
```
         →Trello  →Plane  →FreeForm  →Native
Trello      —       ✅       ✅         ❌
Plane       ✅      —        ✅         ❌
FreeForm    ❌      ❌       —          ❌
Native      ❌      ❌       ❌         —
```
- `switch_backend` (server/tools/migration.py:550): solo reescribe registry, solo trello/plane.
- `migrate_project` (migration.py:190): solo Trello↔Plane, exige `set_migration_target`.
- `migrate_to_freeform_tool` (app_docs/migrate_freeform.py:26): unidireccional →FreeForm.

### PROPUESTO (12 de 12 pares):
```
         →Trello  →Plane  →FreeForm  →Native
Trello      —       ✅       ✅         ✅
Plane       ✅      —        ✅         ✅
FreeForm    ✅      ✅       —          ✅
Native      ✅      ✅       ✅         —
```
- `migrate_backend(source, target, dry_run)` genérica vía `_read_source` + nuevo `_write_target`.
- `switch_backend` generalizado a los 4 + update transaccional de los 3 lugares.
- `regenerate_evidence` opt-in con progreso por UC.
- Skill `/switch-backend` orquestador.

---

## User Story

**ID**: US-BACKEND-SWITCH
**Nombre**: Cambio guiado de backend entre los 4 (FreeForm/Trello/Plane/Native)
**Actor**: Desarrollador/equipo que usa SpecBox y necesita cambiar de gestor de tracking
**Horas estimadas**: 52h
**Pantallas**: ninguna (feature de plataforma; el "frontend" es el skill conversacional `/switch-backend`)

> Como desarrollador o equipo que usa SpecBox, quiero cambiar el backend de tracking de mi proyecto entre cualquiera de los 4 (FreeForm/Trello/Plane/Native) de forma guiada, para adaptar el gestor a la fase del proyecto (local → reporting a cliente → multi-dev) sin perder datos ni el avance de ejecución registrado.

---

## Use Cases

### UC-401: Lectura/escritura genérica entre los 4 backends
- **Actor**: Engine
- **Horas**: 12h
- **Pantallas**: —
- **Estado**: backlog

`_read_source` (migration.py:56) ya es backend-agnóstico. Crear `_write_target` simétrico que escriba en cualquiera de los 4 ABC, y generalizar el dispatch a los 4 (patrón de auth_gateway.py:51-73), reemplazando el hardcode trello/plane.

#### Acceptance Criteria
- [ ] **AC-01**: `_write_target(target_backend, target_id, source_data)` crea US, UC y AC en cualquiera de los 4 backends a partir del dict que devuelve `_read_source`, preservando jerarquía padre→hijo (parent_id) y el `uc_id`/`us_id`/`ac_id` lógico en `meta`; un test de round-trip lee de un backend A, escribe en B y verifica que `list_items(B)` devuelve el mismo número de US/UC/AC y los mismos IDs lógicos que el origen.
- [ ] **AC-02**: El dispatch de backend acepta los 4 valores (`freeform`, `trello`, `plane`, `native`) tanto como origen como destino; pasar un `backend_type` inválido devuelve un error explícito que nombra los 4 valores válidos, verificado por test parametrizado sobre los 4 tipos.
- [ ] **AC-03**: La escritura es idempotente vía `external_id` (igual que `migrate_project`): reejecutar `_write_target` con los mismos datos sobre un destino ya poblado no duplica items y reporta el conteo de `skipped`, verificado ejecutando la migración dos veces y comprobando 0 duplicados en la segunda pasada.

### UC-402: Matriz de mapeo de estados bidireccional entre los 4 backends
- **Actor**: Engine
- **Horas**: 8h
- **Pantallas**: —
- **Estado**: backlog

Cada backend nombra los estados de workflow distinto. Construir un mapeo bidireccional canónico (claves del ABC: `user_stories/backlog/in_progress/review/done`) ↔ estado nativo de cada backend, para que el avance del UC no se degrade al migrar.

#### Acceptance Criteria
- [ ] **AC-01**: Existe una tabla de mapeo que traduce cada uno de los 5 estados canónicos del ABC (`user_stories`, `backlog`, `in_progress`, `review`, `done`) al estado nativo de cada uno de los 4 backends y viceversa; un test verifica que migrar un UC en estado `in_progress` de cualquier origen a cualquier destino produce un UC cuyo `state` re-leído mapea de vuelta a `in_progress`.
- [ ] **AC-02**: Cuando un estado de origen no tiene equivalente exacto en el destino, el mapeo aplica el fallback documentado (`done`→`done`, cualquier estado intermedio desconocido→`backlog`) y registra una entrada de warning en el reporte de migración nombrando el UC y el estado degradado, verificado con un caso de estado sin equivalente directo.
- [ ] **AC-03**: La migración preserva los AC marcados como `done` (campo `ChecklistItemDTO.done`) entre los 4 backends; un test migra un UC con 3 de 5 AC marcados y verifica que en el destino exactamente esos 3 AC quedan `done` y los otros 2 `pending`.

### UC-403: Manejo del backend Native (entrada y salida)
- **Actor**: Engine
- **Horas**: 10h
- **Pantallas**: —
- **Estado**: backlog

Native tiene estado que no vive en el ABC de spec: tablas `developers` (0002), `uc_claims` (0003), `expected_version` (concurrencia optimista). Definir el comportamiento al entrar y salir de Native.

#### Acceptance Criteria
- [ ] **AC-01**: Al migrar de Native a cualquier backend single-user, el avance completo (US/UC/AC con estado, comentarios) se migra y los claims de UC, la identidad de developers y las branches registradas se descartan, listándose en una sección "discarded_native_state" del reporte de migración con el conteo de cada tipo descartado; verificado migrando un proyecto Native con ≥1 claim activo y comprobando que el destino tiene el avance pero el reporte enumera el claim descartado.
- [ ] **AC-02**: Al migrar de cualquier backend a Native, cada US/UC creado se siembra con `expected_version=1` y se asocia a la identidad del developer actual (resuelta vía `whoami`/token), verificado leyendo en Postgres que las filas migradas tienen `expected_version=1` y un `developer_id` no nulo.
- [ ] **AC-03**: El DSN de Postgres nunca se solicita ni se persiste en sesión ni en disco durante la migración hacia/desde Native; el acceso usa exclusivamente la env var `SPECBOX_NATIVE_DSN` (Frontier 2), verificado con un test que ejecuta la migración con el DSN solo en el entorno y confirma que ningún archivo de salida (reporte, projects.json, settings) contiene la cadena del DSN.

### UC-404: Tool `migrate_backend` N×N + `switch_backend` generalizado + update transaccional
- **Actor**: Engine
- **Horas**: 12h
- **Pantallas**: —
- **Estado**: backlog

Tool de orquestación de la migración (preview + ejecución) y actualización consistente del estado del proyecto.

#### Acceptance Criteria
- [ ] **AC-01**: `migrate_backend(source_type, source_id, target_type, target_id?, dry_run=True)` con `dry_run=True` devuelve un preview con los counts de US/UC/AC/comments y el mapeo de estados sin escribir nada en el destino ni en el origen, verificado comprobando que tras un dry-run el destino sigue vacío.
- [ ] **AC-02**: `migrate_backend` con `dry_run=False` ejecuta la migración aditiva (el origen permanece intacto y legible tras la migración) y devuelve un id_map origen→destino + counts de migrados/skipped/errores, verificado comprobando que `list_items(source)` devuelve el mismo conteo antes y después de la ejecución.
- [ ] **AC-03**: `switch_backend` acepta los 4 backend_types y, al cambiar el backend activo de un proyecto, actualiza atómicamente los 3 lugares de verdad —`projects.json` (campo `spec_backend` + `board_id`), la zona auto `tracking_backend` de `doc/app/app_spec.md`, y `specbox.backend_type` en `.claude/settings.local.json`— de modo que `detect_project_backend` tras el switch devuelve el nuevo backend desde cualquiera de sus niveles de prioridad; verificado leyendo los 3 archivos tras el switch y confirmando coherencia.
- [ ] **AC-04**: Si la actualización de cualquiera de los 3 lugares falla, `switch_backend` revierte los ya escritos (rollback) y devuelve un error que nombra el lugar que falló, dejando el proyecto en su backend original; verificado simulando un fallo de escritura en settings y comprobando que `projects.json` y `app_spec.md` quedan sin cambios.

### UC-405: Regeneración de evidencias con progreso por UC
- **Actor**: Engine
- **Horas**: 6h
- **Pantallas**: —
- **Estado**: backlog

La evidencia vive en `.quality/evidence/{feature}/acceptance/results.json` indexada por `uc_id` lógico (results-json-spec.md:13), no por el ID del backend, así que el vínculo sobrevive si se preserva `uc_id`. Riesgo real: evidencia huérfana o stale respecto al código. Tool opt-in que reejecuta acceptance por UC.

#### Acceptance Criteria
- [ ] **AC-01**: `regenerate_evidence(project, ucs=None)` identifica los UCs que tenían evidencia previa (escaneando `.quality/evidence/*/acceptance/results.json`) y, para cada uno, reejecuta `run_acceptance_check` contra el código actual regenerando `results.json` + HTML report; verificado comprobando que tras la regeneración cada UC procesado tiene un `results.json` con `generated_at` posterior al inicio de la ejecución.
- [ ] **AC-02**: La tool reporta el progreso por UC con el formato `[X/N] UC-XXX: {PASS|FAIL|SKIP} ({n_acs} ACs con evidencia)` y al terminar entrega un resumen final con las listas de UCs regenerados, fallidos y pendientes, verificado capturando la salida sobre un proyecto con ≥2 UCs y comprobando que aparece una línea por UC más el resumen.
- [ ] **AC-03**: El resultado de la regeneración se persiste en `doc/migrations/evidence_regeneration_{timestamp}.md` con el detalle por UC y el resumen, verificado comprobando que el archivo existe tras la ejecución y contiene una entrada por cada UC procesado.

### UC-406: Skill guiado `/switch-backend`
- **Actor**: Desarrollador/equipo
- **Horas**: 4h
- **Pantallas**: — (skill conversacional)
- **Estado**: backlog

Orquestador conversacional de principio a fin que envuelve las tools anteriores con una UX segura.

#### Acceptance Criteria
- [ ] **AC-01**: El skill detecta el backend actual del proyecto vía `detect_project_backend`, pregunta el backend destino entre los 3 restantes, y solicita las credenciales del destino de forma segura (para Native, indica que se usa la env var `SPECBOX_NATIVE_DSN` y NO pide el DSN por chat); verificado mediante el SKILL.md que documenta cada paso y la convención de credenciales por backend.
- [ ] **AC-02**: Antes de ejecutar, el skill muestra el preview (`migrate_backend dry_run=True`) con los counts y exige una confirmación literal del usuario; verificado por el SKILL.md que define el paso de confirmación bloqueante antes de `dry_run=False`.
- [ ] **AC-03**: Tras la migración, el skill presenta un reporte que (a) confirma el switch y la consistencia de los 3 lugares, (b) avisa de que la evidencia sigue intacta en el filesystem, (c) si el origen era Native, lista el estado de concurrencia descartado, y (d) ofrece lanzar `regenerate_evidence` como paso opcional; verificado por el SKILL.md que enumera las 4 secciones del reporte final.

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Integridad de datos | 0 pérdida de US/UC/AC/estado/comments en cualquier par de migración | Test de round-trip con counts antes/después |
| Seguridad (Frontier 2) | DSN de Native nunca en sesión ni disco | Grep de la cadena DSN en todos los archivos de salida |
| Idempotencia | Reejecutar una migración no duplica items | Doble pasada → 0 duplicados |
| Atomicidad | El switch o actualiza los 3 lugares o ninguno | Test de fallo simulado + rollback |
| Reversibilidad | El origen permanece intacto tras migrar (migración aditiva) | `list_items(source)` igual antes/después |
| Compatibilidad | Las tools existentes (`migrate_project`, `migrate_to_freeform_tool`) siguen funcionando | Suite de regresión de migración existente en verde |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| MCP remoto (VPS) no puede escribir el filesystem local (FreeForm/settings/app_spec) | Alta | Alto | El skill `/switch-backend` corre en sesión local con MCP local (stdio); documentar este requisito como precondición, igual que en la decisión canónica "FreeForm requiere MCP local" |
| Mapeo de estados con pérdida semántica entre backends muy distintos | Media | Medio | Fallback documentado + warning en reporte (UC-402 AC-02); el usuario ve qué se degradó |
| Doble credencial (origen + destino) en la misma sesión | Media | Medio | Reutilizar el patrón `set_migration_target`; para Native, env var; documentar en el skill |
| Evidencia stale tras migrar genera falsa confianza | Media | Alto | Aviso explícito en el reporte + `regenerate_evidence` opt-in (UC-405) |
| Rollback parcial deja estado inconsistente entre los 3 lugares | Baja | Alto | Escritura transaccional con rollback explícito (UC-404 AC-04) |

---

## Stack Técnico (estimado)

- **Modelo**: Existente — `SpecBackend` ABC + DTOs (server/spec_backend.py)
- **Módulos a tocar**: `server/tools/migration.py` (generalizar), `server/auth_gateway.py` (dispatch), `server/app_docs/sync.py` (zona tracking_backend), nuevo `server/tools/` para `regenerate_evidence`, nueva skill `.claude/skills/switch-backend/`
- **State**: filesystem (projects.json, app_spec.md, settings.local.json) + Postgres (Native)
- **Tests**: pytest en `tests/` (round-trip, parametrizado por backend, rollback, idempotencia)

## Archivos Principales (estimado)
```
server/tools/migration.py            ← _write_target, migrate_backend, switch_backend generalizado
server/tools/evidence_regen.py       ← regenerate_evidence (nuevo)
server/migration/state_mapping.py    ← matriz bidireccional de estados (nuevo)
server/migration/native_handling.py  ← entrada/salida Native (nuevo)
server/app_docs/sync.py              ← apply_app_docs_sync para tracking_backend
.claude/skills/switch-backend/SKILL.md  ← orquestador guiado (nuevo)
tests/test_migrate_backend_nxn.py    ← round-trip + parametrizado (nuevo)
tests/test_switch_backend_transactional.py  ← rollback + 3 lugares (nuevo)
```

## Dependencias
- Native Backend operativo (US-NATIVE-BACKEND + US-NATIVE-SUPABASE, ambas done) ✅
- Postgres dev local (`docker-compose.dev.yml`) para tests Native
- `run_acceptance_check` (acceptance.py:286) para UC-405

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01** (UC-401): `_write_target` crea US/UC/AC en cualquier backend preservando jerarquía e IDs lógicos; round-trip verifica counts e IDs.
- [ ] **AC-02** (UC-401): Dispatch acepta los 4 backend_types; inválido → error que nombra los 4.
- [ ] **AC-03** (UC-401): Escritura idempotente vía external_id; doble pasada → 0 duplicados.
- [ ] **AC-04** (UC-402): Tabla de mapeo traduce los 5 estados canónicos ↔ nativo de los 4 backends; UC `in_progress` round-trips correctamente.
- [ ] **AC-05** (UC-402): Estado sin equivalente aplica fallback documentado + warning nombrando UC y estado.
- [ ] **AC-06** (UC-402): AC marcados `done` se preservan; 3 de 5 marcados → exactamente 3 done en destino.
- [ ] **AC-07** (UC-403): Native→single-user migra avance y descarta claims/identidad/branches, listándolos en "discarded_native_state" del reporte.
- [ ] **AC-08** (UC-403): →Native siembra `expected_version=1` + developer_id no nulo, verificado en Postgres.
- [ ] **AC-09** (UC-403): DSN solo vía `SPECBOX_NATIVE_DSN`, nunca en archivos de salida.
- [ ] **AC-10** (UC-404): `migrate_backend dry_run=True` devuelve counts sin escribir; destino sigue vacío.
- [ ] **AC-11** (UC-404): `dry_run=False` migra aditivamente (origen intacto) + id_map + counts.
- [ ] **AC-12** (UC-404): `switch_backend` actualiza atómicamente los 3 lugares; `detect_project_backend` devuelve el nuevo backend.
- [ ] **AC-13** (UC-404): Fallo en un lugar → rollback de los demás + error que nombra el lugar fallido.
- [ ] **AC-14** (UC-405): `regenerate_evidence` reejecuta acceptance por UC con evidencia previa; `results.json` con timestamp fresco.
- [ ] **AC-15** (UC-405): Progreso por UC `[X/N] UC-XXX: {PASS|FAIL|SKIP}` + resumen final.
- [ ] **AC-16** (UC-405): Resultado persistido en `doc/migrations/evidence_regeneration_{ts}.md`.
- [ ] **AC-17** (UC-406): Skill detecta backend actual, pregunta destino, pide credenciales seguras (Native via env var).
- [ ] **AC-18** (UC-406): Preview obligatorio + confirmación literal antes de ejecutar.
- [ ] **AC-19** (UC-406): Reporte final con 4 secciones (switch OK, evidencia intacta, claims descartados si Native, ofrece regenerate_evidence).

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila/importa sin errores
- [ ] Tests con 85%+ coverage en los módulos nuevos
- [ ] Suite de migración existente (Trello↔Plane, →FreeForm) sigue en verde (no regresión)

---
**Prioridad**: high
**Complejidad**: Alta
**VEG Readiness**: DISABLED (feature de plataforma sin UI de producto — heredado de app_spec.md: engine sin UI salvo Sala de Máquinas)
*Generado: 2026-05-22*
