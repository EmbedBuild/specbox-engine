# Plan: specbox_connectivity_ux — Arquitectura de conectividad cliente/servidor

> Generado: 2026-05-31
> Origen: PRD `doc/prd/specbox_connectivity_ux_prd.md` (FreeForm board `ff-ed0c02f4565a`)
> Discovery: `doc/discovery/specbox_connectivity_ux/icp_jtbd.md` (READY_FOR_PRD)
> Estado: Pendiente
> Stack: Python (FastMCP, server/VPS) + Node ESM (cliente: hooks, bridge, extensión TS)
> **VEG**: DISABLED (el engine no tiene UI de producto propia — `app_spec.md § brand_visual`)
> **Stitch (Paso 6)**: N/A — no hay pantallas; la única superficie cliente es la extensión (notificaciones)

---

## Resumen

Reenfocar la conectividad cliente/servidor de SpecBox bajo un transporte único
(MCP remoto, online-first) donde el server nunca toca un filesystem ajeno y el
estado del cliente fluye por content-passing vía un bridge Node. Cierra la
regresión FreeForm de v6.7.0, hace `/audit` operativo en remoto, convierte la
actualización de la extensión en un proceso pedagógico, y blinda el drift gate
contra violaciones de decisiones canónicas.

## Análisis de superficie (no-UI)

Este PRD no genera UI de producto. Las superficies tocadas son:

| Capa | Componentes | Lenguaje |
|------|-------------|----------|
| Server MCP (VPS) | tools de mutación FreeForm, audit submit, drift gate | Python |
| Bridge cliente | `lib/mcp-client-io.mjs` | Node ESM |
| Skills | `/prd`, `/implement`, `/feedback`, `/audit`, `/discovery` (rutas FreeForm/audit/gate) | Markdown |
| Extensión VSCode | onboarding FreeForm, updater pedagógico, detección de config | TypeScript |
| Analyzers audit | 8 SQuaRE → `.quality/scripts/audit/` | Node |
| Canon | `app_spec.md § canonical_decisions` | Markdown |

No hay componentes UI que mapear (Paso 2 de UI: N/A). No hay VEG (Paso 2.5b: N/A).
No hay Stitch (Paso 6: N/A).

---

## Orden de implementación (por dependencias técnicas)

El orden NO es el orden de las US — lo dictan las dependencias. Secuencia propuesta:

```
1. UC-660  (server: tools mutación FreeForm content-passing)   ← base de todo
2. UC-661  (cliente: bridge canónico)                          ← depende de UC-660 (contrato)
3. UC-662  (extensión: FreeForm first-class onboarding)        ← depende de UC-661
   ───────── desbloquea FreeForm end-to-end (la regresión urgente) ─────────
4. UC-663  (audit: analyzers locales + submit)                 ← reusa patrón content-passing de UC-660
5. UC-667  (server: drift gate vs decisiones canónicas)        ← independiente, paralelizable
6. UC-668  (canon: registrar nueva decisión)                   ← depende de UC-667 (gate debe aceptarla)
7. UC-664  (extensión: detección config obsoleta)              ← independiente del transporte
8. UC-665  (extensión: auto-migración + backup + copy)         ← depende de UC-664
9. UC-666  (extensión: updater orquestador no-bloqueante)      ← depende de UC-664, UC-665
```

**Hito 1 (urgent — desbloquea clientes hoy)**: UC-660 → UC-661 → UC-662.
**Hito 2 (cierra lo roto en remoto)**: UC-663.
**Hito 3 (gobernanza)**: UC-667 → UC-668.
**Hito 4 (experiencia de actualización)**: UC-664 → UC-665 → UC-666.

Hitos 2, 3 y 4 son paralelizables entre sí una vez cerrado el Hito 1.

---

## Fases de implementación por UC

### UC-660 — Tools de mutación FreeForm con content-passing [server, 10h]

**Objetivo**: que `add_uc`, `add_ac`, `mark_ac`, `update_uc`, `import_spec`,
`complete_uc`, `start_uc` operen sobre `items.json` pasado como string, sin
`Path(...).resolve()` contra el FS del server.

- [ ] Inventariar las tools de mutación FreeForm en `server/tools/spec_mutations.py`,
  `spec_driven.py`, `milestone_management.py`, `board_operations.py` que hoy
  resuelven path contra el FS.
- [ ] Para cada tool: añadir parámetro `items_content: str | None` (content-passing)
  y devolver `items_content` mutado + el resultado semántico. Preservar el helper
  `*_impl(path)` para callers in-process (patrón v6.0.1).
- [ ] Replicar el patrón de `FreeformBackend` para operar sobre un dict en memoria
  en vez de leer/escribir disco cuando viene `items_content`.
- [ ] Tests: (AC-01) cada tool con `SPECBOX_ENGINE_MCP_URL` set + items.json por
  string; (AC-02) secuencia add_uc→mark_ac→find_next_uc; (AC-03) suite in-process
  existente verde sin cambios.
- **Riesgo clave**: romper callers in-process. Mitigación: `*_impl` preservado +
  los tests existentes como gate de no-regresión.

### UC-661 — Bridge cliente canónico para I/O FreeForm [cliente, 6h]

**Objetivo**: una sola puerta Node para que las skills lean/escriban `doc/tracking/`.

- [ ] Extender `lib/mcp-client-io.mjs` con `readTrackingBundle()` /
  `writeTrackingBundle()` (o reusar `readContentBundle`/`writeContentBundle`)
  resolviendo raíz vía `git rev-parse --show-toplevel`.
- [ ] Mantener el guard de path-traversal (rechaza `..` y absolutos fuera del repo).
- [ ] Tests `node:test` (AC-04): lee fixture, escribe resultado, guard activo.
- **Dependencia**: el contrato de UC-660 (qué string entra/sale).

### UC-662 — FreeForm first-class en onboarding de la extensión [extensión, 5h]

**Objetivo**: revertir el daño UX de #82 sin reintroducir Python.

- [ ] En `vscode-extension/src/mcp.ts` / `onboard.ts`: añadir FreeForm como opción
  de onboarding de primer nivel (junto a Native/Trello), que configura remoto +
  bridge, cero Python.
- [ ] `health.ts` / `prerequisites.ts`: FreeForm configurado → `ready` (no degraded).
- [ ] Tests (AC-06): settings resultante apunta a remoto, sin Python/uv/Local;
  (AC-07) `evaluatePrerequisites` devuelve `ready`.
- **Dependencia**: bridge de UC-661 operativo.

### UC-663 — Porting de los 8 SQuaRE analyzers a Node local [cliente, 12h]

**Objetivo**: `/audit` funciona en remoto ejecutando analyzers client-side.

- [ ] Portar los 8 analyzers de `server/audit/analyzers/*.py` a
  `.quality/scripts/audit/*.mjs` (functional, performance, compatibility,
  usability, reliability, security, maintainability, portability).
- [ ] `submit_quality_audit(report)` (server) acepta el `QualityReport` por
  content-passing, persiste bajo `evidence/audits/`, autogenera `audit_id`.
- [ ] Actualizar la skill `/audit`: lazy-check tools externas → correr analyzers
  locales → `submit_quality_audit`.
- [ ] Tests: (AC-08) cada analyzer sobre fixture produce su bloque; (AC-09) submit
  persiste JSON+PDF + audit_id; (AC-10) smoke `/audit` en remoto sobre el repo.
- **Riesgo**: la lógica Python de scoring/PDF debe replicarse o quedarse server-side.
  Decisión a tomar en implementación: scoring puede quedarse en `submit_quality_audit`
  (server) recibiendo métricas crudas; el PDF se genera server-side (ReportLab ya existe).
  Los analyzers locales solo recogen señales del FS. **Esto reduce el porting**: los
  `.mjs` recolectan, el server normaliza+puntúa+renderiza.

### UC-667 — Validación de drift contra decisiones canónicas [server, 5h]

**Objetivo**: el gate no deja pasar un cambio que contradiga `app_spec.md`.

- [ ] `validate_discovery_completeness` acepta `app_spec_content` (content-passing)
  y extrae la zona `canonical_decisions`.
- [ ] `server/app_docs/drift_detector.py`: detectar si el artefacto contradice una
  decisión registrada sin declararla.
- [ ] Tests: (AC-19) contradicción no declarada → no READY; (AC-20)
  `documented_exception` justificada → READY (usar el propio artefacto de esta
  feature como fixture); (AC-21) payload distingue mercado vs canónico.
- **Independiente** — paralelizable con Hitos 1/2/4.

### UC-668 — Registrar la nueva decisión canónica [canon, 2h]

- [ ] En `app_spec.md § canonical_decisions` (hybrid, append-only): añadir la nueva
  decisión y marcar "FreeForm requiere MCP local" como revisada/sustituida con
  referencia a este PRD. Sin borrar histórico.
- [ ] Test (AC-22): ambas entradas presentes con la relación de sustitución.
- **Dependencia**: UC-667 debe aceptar `documented_exception` antes (si no, el
  propio commit que registra la decisión podría auto-bloquearse).

### UC-664 — Detección de configuración obsoleta [extensión, 5h]

- [ ] `vscode-extension/src/migration.ts` (nuevo): `detectClientConfigCase(settings, mcpConfig)`
  puro → clasifica en los 5 casos.
- [ ] Integración con `upgrade_project` / `detect_*_migration_case` para recibir el plan.
- [ ] Tests: (AC-11) los 5 casos; (AC-12) plan recibido corresponde al caso (mock-server).

### UC-665 — Auto-migración con backup + resumen pedagógico [extensión, 7h]

- [ ] Backup `settings.local.json` → `.bak-<ts>` antes de tocar (AC-13).
- [ ] Aplicar migración Local→Remoto+bridge; copy pedagógico por caso (4 secciones) (AC-14).
- [ ] Comando "SpecBox: Revert last migration" (AC-15).
- [ ] Gate inviolable: movimiento de datos exige confirmación, reconfig de transporte no (AC-16).
- **Dependencia**: UC-664 (caso + plan).

### UC-666 — Updater orquestador no-bloqueante [extensión, 4h]

- [ ] Refactor `vscode-extension/src/updater.ts`: orquestar binario → skills/hooks →
  detección → migración → resumen, fire-and-forget con try/catch por fase (patrón v6.6.2) (AC-17).
- [ ] Caso "sin cambios" (Trello/Plane) → mensaje mínimo (AC-18).
- **Dependencia**: UC-664, UC-665.

---

## Alternativas y tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|----------------------|-------|
| Transporte | Remoto único + content-passing (C) | Transporte dual local empaquetado (B) | Offline no existe en sistema agéntico (Claude exige red); B = problema inexistente |
| I/O FreeForm | Bridge Node encapsulado (UC-661) | Cada skill hace su Read/Write | Una sola puerta = guard + tests centralizados, menos frágil |
| Audit scoring | Recolectar señales en Node, puntuar+PDF en server | Portar scoring+ReportLab a Node | Reduce el porting; reusa ReportLab existente; el FS-scan (lo que rompía en remoto) sí va a Node |
| Auto-migración config | Auto + backup + revert | Preview+confirm estilo /switch-backend | No cambia backend (FreeForm sigue FreeForm), solo restaura transporte; mover datos sí pide confirmación |
| Gate | Validar `app_spec.md` además de `app_market.md` | Solo `app_market.md` (status quo) | Es la causa-raíz que dejó pasar #82 |

---

## Archivos a crear/modificar

```
server/
├── tools/spec_mutations.py, spec_driven.py        # content-passing en mutadores FreeForm (UC-660)
├── tools/milestone_management.py, board_operations.py  # idem si aplica
├── tools/audit.py                                  # submit_quality_audit content-passing (UC-663)
├── tools/discovery.py                              # validate_discovery_completeness vs app_spec (UC-667)
├── app_docs/drift_detector.py                      # drift de decisión canónica (UC-667)
└── backends/freeform_backend.py                    # helpers *_impl preservados (UC-660)

.claude/hooks/lib/mcp-client-io.mjs                 # bridge canónico (UC-661)
.claude/skills/{prd,implement,feedback}/SKILL.md    # usar bridge (UC-661)
.claude/skills/audit/SKILL.md                       # flujo analyzers locales (UC-663)

.quality/scripts/audit/*.mjs                        # 8 analyzers locales (UC-663) — NUEVO

vscode-extension/src/
├── mcp.ts, onboard.ts, health.ts, prerequisites.ts # FreeForm first-class (UC-662)
├── migration.ts                                    # detectClientConfigCase + auto-migración (UC-664,665) — NUEVO
└── updater.ts                                       # orquestador no-bloqueante (UC-666)

doc/app/app_spec.md                                 # nueva decisión canónica (UC-668)
```

---

## Estrategia de tests (Acceptance Engine)

- **Server (pytest)**: UC-660 (content-passing + in-process verde), UC-663 (submit),
  UC-667 (gate). Correr la suite **con y sin** `SPECBOX_ENGINE_MCP_URL` (NFR compatibilidad).
- **Cliente (`node:test`)**: UC-661 (bridge + guard), UC-662/664/665/666 (extensión).
- **Smoke end-to-end**: UC-663 (`/audit` en remoto) — el gate más fuerte de "ya no está roto".
- **El propio artefacto de esta feature** es fixture vivo de UC-667 AC-20.
- Evidencia: cada UC ACCEPTED con HTML Evidence Report (NSM del proyecto).

---

## Riesgos del plan

| Riesgo | Mitigación |
|--------|-----------|
| El porting de analyzers infravalora la lógica Python (scoring/PDF) | Decisión de diseño: Node solo recolecta señales FS; server puntúa+renderiza. Reduce superficie |
| Migrar 7 tools de mutación rompe in-process | `*_impl` preservado + suite in-process como gate (igual que v6.0.1) |
| UC-668 se auto-bloquea por el gate nuevo | Orden forzado: UC-667 (aceptar documented_exception) antes de UC-668 |
| Inventario incompleto de rutas I/O FreeForm | UC-660 arranca con inventario exhaustivo; bridge como única puerta lo hace detectable |
| `/implement` de este PRD necesita FreeForm operativo... que es lo que arregla | Bootstrap: implementar UC-660/661 primero permite que el resto del pipeline ya use el flujo arreglado (dogfooding) |

---

## Referencias

- PRD: `doc/prd/specbox_connectivity_ux_prd.md`
- Discovery: `doc/discovery/specbox_connectivity_ux/icp_jtbd.md`
- ADR base: `doc/decisions/mcp_path_contract.md` (v6.0.1 — patrón content-passing)
- Tracking: FreeForm `ff-ed0c02f4565a` — US-CONN-TRANSPORT/AUDIT/UPGRADE/GATE (UC-660…668)
- Memoria: `project_connectivity_ux_architecture.md`
