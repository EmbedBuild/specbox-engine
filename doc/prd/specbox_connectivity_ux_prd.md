# PRD: specbox_connectivity_ux — Arquitectura de conectividad cliente/servidor

> Origen: FreeForm board `ff-ed0c02f4565a` | Discovery `doc/discovery/specbox_connectivity_ux/icp_jtbd.md` (READY_FOR_PRD)
> Generado: 2026-05-31
> Hereda audiencia + stack de `doc/app/app_prd.md` y `doc/app/app_spec.md`

## Resumen

El PR #82 (v6.7.0) eliminó Python del cliente **eliminando el modo Local del MCP**,
y al hacerlo dejó inalcanzable el estado-en-filesystem del cliente: FreeForm (el
backend más usado por devs solo/locales) y `/audit` dejaron de funcionar vía la
extensión, porque el MCP remoto corre en el VPS y no toca el filesystem del usuario.
Además, el mecanismo de actualización (`updater.ts`) solo sube el binario de la
extensión: no detecta config obsoleta, no migra `settings.json` ni estado, ni
explica el impacto — los clientes descubrieron la rotura por errores crípticos.

Este PRD reenfoca la arquitectura de conectividad bajo un principio único:
**transporte único (MCP remoto, online-first); el server nunca toca un filesystem
ajeno; el estado del cliente entra/sale por content-passing vía el bridge Node**.
Resuelve la regresión FreeForm, convierte la actualización en un proceso robusto y
pedagógico, y cierra el agujero de gobernanza (drift gate ciego) que dejó pasar el
cambio breaking.

## Alcance

### Incluye
- Completar el **MCP Path Contract** para las tools de **mutación** FreeForm
  (content-passing: el cliente hace I/O del `items.json` con Read/Write Node).
- Consolidar **`lib/mcp-client-io.mjs`** como capa cliente canónica de I/O FreeForm.
- Restaurar **FreeForm como opción first-class** en el onboarding de la extensión,
  sin reintroducir Python.
- **Migrador de actualización consciente de la configuración**: detecta config
  obsoleta (ej. modo Local), auto-migra `settings.json` con backup, muestra resumen
  pedagógico por caso de ICP.
- **Inteligencia de migración híbrida**: la extensión detecta config local; el
  server calcula el plan (reusa `upgrade_project` / `detect_*_migration_case`).
- **Drift gate v2**: `validate_discovery_completeness` valida también contra
  `app_spec.md § decisiones canónicas`.
- **Sustituir la decisión canónica** "FreeForm requiere MCP local" por la nueva en
  `app_spec.md` (zona `canonical_decisions`, append-only).
- **Portar los 8 SQuaRE analyzers** de `/audit` a `.quality/scripts/audit/` (Node
  local) + contrato `submit_quality_audit` content-passing, cerrando lo último
  roto en remoto.

### No incluye
- **Modo offline / air-gapped** — descartado: Claude Code exige red, no existe el
  escenario.
- **Empaquetar un server local** (arquetipo B) — descartado por la misma razón.
- Cambios en los backends cloud (Trello/Plane/Native) más allá de su transporte ya
  funcional.

---

## Audiencia (heredada de app_prd.md — VEG uniforme)

Heredada sin cambios. ICPs trazados desde el Discovery:
- **ICP-2** Dev solo con Claude Code (FreeForm local) — primario, el más golpeado.
- **ICP-1** Owner-operator (JPS) — primario, mantiene el remoto y el soporte.
- **ICP-3** Equipo/agencia (Trello/Plane) — secundario, vive la actualización sin ruido.

VEG Readiness: **DISABLED** — el engine no tiene UI de producto propia (decisión
canónica `app_spec.md § brand_visual`). Sin targets de UI nuevos.

---

## User Stories y Use Cases

### US-CONN-TRANSPORT: FreeForm operativo sin Python vía content-passing

> Como **dev solo que usa FreeForm en local** (ICP-2), quiero que mis tools de
> tracking lean y escriban mi `doc/tracking/` real a través del MCP remoto sin
> instalar Python ni un MCP local, para recuperar la trazabilidad US→UC→AC que la
> v6.7.0 me rompió, sin pagar el coste de runtime que zero-python prometió eliminar.

**Prioridad**: urgent · **Complejidad**: Alta · JTBDs: JR-FCUX.1, JR-FCUX.2, JR-FCUX.3, JR-FCUX.4, JE-FCUX.2

#### UC-660: Tools de mutación FreeForm con content-passing
- **Actor**: dev FreeForm (ICP-2) / agente del pipeline
- **Horas**: 10h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-01** [JR-FCUX.4]: Cada tool de mutación FreeForm (`add_uc`, `add_ac`,
  `mark_ac`, `update_uc`, `import_spec`, `complete_uc`, `start_uc`) acepta el
  contenido de `items.json` como parámetro string y devuelve el `items.json`
  mutado como string, sin que el server llame `Path(...).resolve()` contra un
  filesystem ajeno. Verificable: test que ejecuta cada tool con
  `SPECBOX_ENGINE_MCP_URL` set y un `items.json` inyectado por string, y asserta
  que el resultado refleja la mutación sin tocar el FS del server.
- [ ] **AC-02** [JR-FCUX.1]: Con el MCP en modo remoto (`SPECBOX_ENGINE_MCP_URL`
  set), una secuencia `add_uc` → `mark_ac` → `find_next_uc` sobre un `items.json`
  de cliente pasado por content-passing devuelve resultados correctos (el UC
  aparece, el AC queda marcado, el siguiente UC es el esperado) — replicando el
  flujo que hoy falla con "esto no existe".
- [ ] **AC-03** [JR-FCUX.4]: Las tools de mutación FreeForm migradas conservan
  compatibilidad in-process (callers Python del propio server) vía helper
  `*_impl(path)` preservado, igual que el patrón v6.0.1. Verificable: los tests
  existentes de FreeForm in-process siguen verdes sin modificación.

#### UC-661: Bridge cliente canónico para I/O FreeForm
- **Actor**: skills/hooks del cliente (Node)
- **Horas**: 6h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-04** [JR-FCUX.4]: `lib/mcp-client-io.mjs` expone helpers
  (`readTrackingBundle`/`writeTrackingBundle` o reuso de `readContentBundle`/
  `writeContentBundle`) que las skills FreeForm usan para leer/escribir
  `doc/tracking/` resolviendo la raíz vía `git rev-parse --show-toplevel`.
  Verificable: test `node:test` que lee un `items.json` de fixture y escribe el
  resultado, con guard de path-traversal activo (rechaza `..` y paths absolutos
  fuera del repo).
- [ ] **AC-05** [JR-FCUX.4]: Las skills que mutan FreeForm (`/prd`, `/implement`,
  `/feedback` en su ruta de tracking) usan el bridge en lugar de pasar paths al
  server. Verificable: grep en `.claude/skills/` no encuentra llamadas a tools de
  mutación FreeForm con `project_path` como ruta de filesystem del server.

#### UC-662: FreeForm first-class en onboarding de la extensión (sin Python)
- **Actor**: dev nuevo (ICP-2) en la extensión VSCode
- **Horas**: 5h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-06** [JR-FCUX.2]: El onboarding de la extensión ofrece FreeForm como
  opción operativa de primer nivel junto a Native/Trello; al elegirla, configura
  el MCP remoto + el bridge sin pedir Python en ningún punto. Verificable: test de
  la extensión que simula la elección de FreeForm y asserta que el `settings.json`
  resultante apunta al remoto y NO contiene referencias a Python/uv/modo Local.
- [ ] **AC-07** [JE-FCUX.2]: Tras elegir FreeForm en el onboarding, el health
  check / sidebar reporta el backend como operativo (no "degraded" por falta de
  modo local). Verificable: test que tras configurar FreeForm, `evaluatePrerequisites`
  devuelve `ready` para ese proyecto.

---

### US-CONN-AUDIT: /audit operativo en remoto vía analyzers locales

> Como **owner del engine** (ICP-1) y **dev que audita su proyecto** (ICP-2), quiero
> que `/audit` funcione con el MCP remoto ejecutando los 8 analyzers SQuaRE en el
> cliente (Node) y enviando el `QualityReport` por content-passing, para cerrar la
> última pieza que quedó rota en remoto desde v6.0.1 y poder auditar calidad sin un
> MCP local.

**Prioridad**: high · **Complejidad**: Alta · JTBDs: JR-FCUX.3, JR-FCUX.4

#### UC-663: Porting de los 8 SQuaRE analyzers a `.quality/scripts/audit/` (Node local)
- **Actor**: skill `/audit` / dev (ICP-2)
- **Horas**: 12h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-08** [JR-FCUX.4]: Los 8 analyzers SQuaRE (functional, performance,
  compatibility, usability, reliability, security, maintainability, portability)
  se ejecutan client-side desde `.quality/scripts/audit/` (Node) escaneando el
  código local, sin que el server toque el filesystem del cliente. Verificable:
  test que corre cada analyzer sobre un fixture y asserta que produce su bloque del
  `QualityReport` (score 0-100, traffic_light, findings, recommendations).
- [ ] **AC-09** [JR-FCUX.3]: `submit_quality_audit(report)` acepta el
  `QualityReport` construido client-side por content-passing, lo persiste bajo
  `evidence/audits/` y autogenera `audit_id` si no se pasa. Verificable: test que
  envía un report serializado y asserta persistencia (JSON + PDF) + `audit_id`
  formato `audit_YYYYMMDDTHHMMSSZ`.
- [ ] **AC-10** [JR-FCUX.3]: La skill `/audit` orquesta el flujo nuevo (lazy-check
  de tools externas → ejecutar analyzers locales → `submit_quality_audit`) y
  funciona end-to-end con `SPECBOX_ENGINE_MCP_URL` set. Verificable: smoke test que
  ejecuta `/audit` en remoto sobre el propio repo y produce evidencia válida.

---

### US-CONN-UPGRADE: Actualización robusta y pedagógica consciente de la configuración

> Como **dev que actualiza SpecBox vía la extensión** (ICP-2, ICP-3), quiero que la
> actualización detecte si mi configuración quedó obsoleta, la migre por mí con
> backup, y me explique qué cambió y qué debo hacer, para no descubrir roturas por
> errores crípticos y confiar en que pulsar "Update" es seguro.

**Prioridad**: urgent · **Complejidad**: Alta · JTBDs: JR-FCUX.5, JR-FCUX.6, JR-FCUX.7, JE-FCUX.1

#### UC-664: Detección de configuración obsoleta (cliente)
- **Actor**: extensión VSCode
- **Horas**: 5h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-11** [JR-FCUX.7]: Al activarse tras una actualización, la extensión lee
  `.claude/settings.local.json` + la config MCP y clasifica el estado del cliente
  en uno de los casos canónicos (FreeForm+Local-obsoleto, FreeForm+Remoto-ya-ok,
  Trello/Plane-sin-cambios, Native+OAuth-sin-cambios, onboarding-incompleto).
  Verificable: función pura `detectClientConfigCase(settings, mcpConfig)` con test
  que cubre los 5 casos.
- [ ] **AC-12** [JR-FCUX.7]: La extensión envía el caso detectado + la versión
  origen al server vía `upgrade_project` / `detect_*_migration_case` y recibe un
  **plan de migración** (acciones + diffs propuestos). Verificable: test de
  integración mock-server que asserta que el plan recibido corresponde al caso.

#### UC-665: Auto-migración de config con backup + resumen pedagógico
- **Actor**: extensión VSCode / dev (ICP-2, ICP-3)
- **Horas**: 7h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-13** [JR-FCUX.5]: Cuando el caso es "config obsoleta" (ej. modo Local),
  la extensión hace **backup** de `settings.local.json` (a `settings.local.json.bak-<ts>`)
  ANTES de tocar nada, y luego aplica la migración (Local→Remoto+bridge).
  Verificable: test que asserta que el `.bak` existe con el contenido original y
  que el `settings.local.json` migrado apunta al remoto.
- [ ] **AC-14** [JR-FCUX.6, JE-FCUX.1]: Tras migrar, la extensión muestra un
  resumen pedagógico no bloqueante con: qué cambió, qué se migró automáticamente,
  dónde está el backup, y qué — si algo — debe hacer el usuario, con copy
  específico por caso de ICP. Verificable: test que para cada caso asserta el copy
  contiene las 4 secciones (cambió/migrado/backup/acción).
- [ ] **AC-15** [JE-FCUX.1]: La migración de `settings.json` es **reversible**: un
  comando "SpecBox: Revert last migration" restaura desde el `.bak` más reciente.
  Verificable: test que migra, revierte y asserta que el `settings.local.json`
  vuelve al estado original byte-a-byte.
- [ ] **AC-16** [JR-FCUX.5]: La auto-migración respeta el gate de acciones
  destructivas inviolables: **mover/transformar datos de tracking** (no solo
  reconfigurar transporte) NO se auto-ejecuta — se propone con confirmación
  explícita. Verificable: test que un plan que incluye movimiento de datos exige
  confirmación, mientras que uno que solo reconfigura transporte no.

#### UC-666: Updater no bloqueante y orquestador del flujo completo
- **Actor**: extensión VSCode
- **Horas**: 4h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-17** [JE-FCUX.1]: El flujo de actualización (binario → skills/hooks →
  detección de config → migración → resumen) se ejecuta sin bloquear la activación
  (patrón fire-and-forget de v6.6.2), con try/catch por fase que impide que un
  fallo cuelgue la extensión. Verificable: test que simula un fallo en la fase de
  migración y asserta que la activación completa igualmente.
- [ ] **AC-18** [JR-FCUX.6]: Tras una actualización exitosa sin config obsoleta
  (ej. Trello/Plane), el usuario ve un mensaje mínimo "Actualizado a vX — sin
  cambios para tu configuración", sin ruido innecesario. Verificable: test que
  para el caso "sin cambios" asserta el copy breve y la ausencia de prompts de
  migración.

---

### US-CONN-GATE: Drift gate consciente de las decisiones canónicas

> Como **owner del engine** (ICP-1), quiero que el drift gate de `/discovery`
> valide los cambios también contra `app_spec.md § decisiones canónicas` (no solo
> `app_market.md`), para que un cambio que contradiga una decisión registrada no
> pueda declararse `no_drift` y colarse a producción — como ocurrió con el PR #82.

**Prioridad**: high · **Complejidad**: Media · JTBDs: JR-FCUX.8, JE-FCUX.3

#### UC-667: Validación de drift contra decisiones canónicas
- **Actor**: `/discovery` / owner (ICP-1)
- **Horas**: 5h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-19** [JR-FCUX.8]: `validate_discovery_completeness` acepta el contenido
  de `app_spec.md § canonical_decisions` (content-passing) y detecta si el
  Discovery contradice alguna decisión registrada. Verificable: test que con un
  artefacto que contradice una decisión canónica SIN declararla en "Drift from
  app_market" devuelve `verdict != READY_FOR_PRD` con un `missing` específico.
- [ ] **AC-20** [JR-FCUX.8]: Cuando un Discovery contradice una decisión canónica
  pero la declara explícitamente como `documented_exception` con justificación
  (como hace este propio Discovery), el gate la acepta. Verificable: test que con
  el artefacto de `specbox_connectivity_ux` devuelve `READY_FOR_PRD`.
- [ ] **AC-21** [JE-FCUX.3]: El reporte de drift distingue entre drift de mercado
  (`app_market.md`) y drift de decisión canónica (`app_spec.md`), nombrando la
  decisión concreta contradicha. Verificable: test que asserta el payload incluye
  `canonical_decision_drift: {decision, resolved, kind}`.

#### UC-668: Registro de la nueva decisión canónica
- **Actor**: pipeline / owner
- **Horas**: 2h
- **Estado**: user_stories

**Acceptance Criteria:**
- [ ] **AC-22** [JR-FCUX.8]: `app_spec.md § canonical_decisions` registra la nueva
  decisión ("MCP server nunca toca filesystem ajeno; estado cliente vía
  content-passing/bridge; transporte único remoto online-first") y marca la
  anterior ("FreeForm requiere MCP local") como **revisada/sustituida** con
  referencia a este PRD, sin borrar el histórico (append-only). Verificable: el
  archivo contiene ambas entradas con la relación de sustitución explícita.

---

## Interacciones UI

> El engine no tiene UI de producto propia. La única superficie "UI" es la
> extensión VSCode (mensajes/notificaciones), cubierta abajo.

### Acciones del usuario (extensión)
| Acción | UC asociado | Frecuencia | Criticidad | Requiere confirmación |
|--------|-------------|------------|------------|----------------------|
| Elegir FreeForm en onboarding | UC-662 | Una vez/proyecto | Media | No |
| Actualizar la extensión | UC-666 | Por release | Alta (puede romper config) | No (auto-migra con backup) |
| Aceptar movimiento de datos en migración | UC-665 | Raro | Alta (irreversible) | **Sí** |
| Revertir migración | UC-665 | Raro | Media | No |

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Compatibilidad | El MCP remoto opera FreeForm idéntico a como lo hacía el modo local | Suite FreeForm verde con `SPECBOX_ENGINE_MCP_URL` set |
| Seguridad | El bridge cliente rechaza path-traversal (`..`, absolutos fuera de repo) | Test de guard en `mcp-client-io.mjs` |
| Reversibilidad | Toda auto-migración de config tiene backup restaurable | Test migrate→revert byte-a-byte |
| No-bloqueo | La actualización nunca cuelga la activación de la extensión | Test fire-and-forget con fallo simulado |
| Cero Python | Ningún path del cliente (onboarding/update/FreeForm) requiere Python | grep user-facing CLEAN + test config |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Migrar tools de mutación FreeForm rompe callers in-process | Media | Alto | Preservar helpers `*_impl(path)` (patrón v6.0.1); tests in-process verdes como gate |
| El bridge no cubre todas las rutas de I/O FreeForm (evidencia, attachments) | Media | Medio | Inventario exhaustivo en `/plan`; `mcp-client-io.mjs` como única puerta |
| Auto-migrar `settings.json` corrompe config del usuario | Baja | Alto | Backup obligatorio pre-migración + revert command + reversibilidad testeada |
| El gate v2 produce falsos positivos que bloquean Discoveries legítimos | Media | Medio | `documented_exception` siempre desbloquea; modo `warn` por defecto antes de `block` |
| Clientes ya rotos en v6.7.0 con data en estado inconsistente | Media | Medio | El plan de migración detecta y reconcilia; data nunca se mueve sin confirmación |

---

## Stack Técnico (heredado de app_spec.md)

- **Server / MCP**: Python (FastMCP) ≥3.12, gestor `uv` — solo lado server (VPS).
- **Cliente**: Node.js (ESM `.mjs`) — bridge, hooks, extensión TS. Cero Python.
- **Tracking**: FreeForm (`doc/tracking/` local) vía content-passing.
- **Tests**: pytest (server) + `node:test` (bridge/extensión).

## Archivos Principales (estimado — se afina en /plan)
- `server/backends/freeform_backend.py` — helpers `*_impl` preservados.
- `server/tools/spec_mutations.py` / `spec_driven.py` — tools migradas a content-passing.
- `server/tools/audit.py` — contrato `submit_quality_audit` + README en `.quality/scripts/audit/`.
- `server/app_docs/drift_detector.py` + `server/tools/discovery.py` — gate v2.
- `.claude/hooks/lib/mcp-client-io.mjs` — bridge canónico.
- `vscode-extension/src/{mcp,updater,onboard,prerequisites,migration}.ts` — onboarding FreeForm + updater pedagógico.
- `doc/app/app_spec.md` — nueva decisión canónica.

## Dependencias
- MCP Path Contract (v6.0.1) — base del content-passing (ya en producción).
- `upgrade_project` / `detect_*_migration_case` (server) — reusados por el migrador.
- Patrón fire-and-forget de activación (v6.6.2) — reusado por el updater.

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

**US-CONN-TRANSPORT** (UC-660, UC-661, UC-662)
- [ ] **AC-01**: Tools de mutación FreeForm content-passing sin tocar FS del server (UC-660)
- [ ] **AC-02**: Flujo add_uc→mark_ac→find_next_uc correcto en remoto (UC-660)
- [ ] **AC-03**: Compatibilidad in-process preservada vía `*_impl` (UC-660)
- [ ] **AC-04**: Bridge `mcp-client-io.mjs` con guard path-traversal (UC-661)
- [ ] **AC-05**: Skills FreeForm usan el bridge, no paths al server (UC-661)
- [ ] **AC-06**: FreeForm first-class en onboarding sin Python (UC-662)
- [ ] **AC-07**: Health check reporta FreeForm operativo (UC-662)

**US-CONN-AUDIT** (UC-663)
- [ ] **AC-08**: Los 8 analyzers SQuaRE corren client-side en `.quality/scripts/audit/` (UC-663)
- [ ] **AC-09**: `submit_quality_audit` acepta report client-side + persiste + audit_id (UC-663)
- [ ] **AC-10**: `/audit` end-to-end en remoto produce evidencia válida (UC-663)

**US-CONN-UPGRADE** (UC-664, UC-665, UC-666)
- [ ] **AC-11**: `detectClientConfigCase` clasifica los 5 casos (UC-664)
- [ ] **AC-12**: Extensión recibe plan de migración del server (UC-664)
- [ ] **AC-13**: Backup de settings antes de migrar (UC-665)
- [ ] **AC-14**: Resumen pedagógico con 4 secciones por caso (UC-665)
- [ ] **AC-15**: Migración reversible vía revert command (UC-665)
- [ ] **AC-16**: Movimiento de datos exige confirmación (gate inviolable) (UC-665)
- [ ] **AC-17**: Updater no bloquea la activación (UC-666)
- [ ] **AC-18**: Mensaje mínimo "sin cambios" para Trello/Plane (UC-666)

**US-CONN-GATE** (UC-667, UC-668)
- [ ] **AC-19**: Gate detecta contradicción de decisión canónica (UC-667)
- [ ] **AC-20**: Gate acepta `documented_exception` justificada (UC-667)
- [ ] **AC-21**: Reporte distingue drift mercado vs canónico (UC-667)
- [ ] **AC-22**: Nueva decisión canónica registrada en app_spec.md (UC-668)

### Técnicos (no validados por AG-09)
- [ ] Suite pytest verde con y sin `SPECBOX_ENGINE_MCP_URL`
- [ ] Suite `node:test` de la extensión + bridge verde
- [ ] grep cero-python user-facing CLEAN
- [ ] Compliance audit del engine ≥ A

---
**Prioridad**: urgent (US-CONN-TRANSPORT + US-CONN-UPGRADE), high (US-CONN-AUDIT + US-CONN-GATE)
**Complejidad**: Alta
**US**: 4 · **UC**: 9 (UC-660…UC-668) · **AC**: 22
*Generado: 2026-05-31*
