# Reglas Globales - SpecBox Engine v5.19.0

> Estas reglas aplican a TODOS los proyectos que usen el engine.
> Se referencian desde el CLAUDE.md de cada proyecto.

---

## Quality First — Calidad sobre velocidad (v5.15.0)

> **SpecBox Engine ya proporciona velocidad. El trabajo del LLM es CALIDAD.**
> Cada vez que el agente prioriza velocidad sobre calidad, genera deuda tecnica
> que cuesta mas que el tiempo "ahorrado". Un token bien usado > diez tokens desperdiciados.

### Contrato de Calidad

**Antes de escribir cualquier archivo, el agente DEBE:**

1. **Leer** — Leer el archivo que va a modificar (enforcement por `quality-first-guard.mjs`)
2. **Entender** — Comprender el codigo existente, sus patrones, sus convenciones
3. **Articular** — Explicar en texto visible que va a hacer y por que
4. **Implementar** — Solo entonces, escribir el codigo
5. **Verificar** — Confirmar que el cambio es correcto antes de marcarlo como hecho

### Reglas de calidad obligatorias

| Regla | Descripcion | Enforcement |
|-------|-------------|-------------|
| **Read before Write** | Leer archivos existentes antes de modificarlos | Hook BLOQUEANTE (`quality-first-guard.mjs`) |
| **Think before Act** | Articular enfoque antes de implementar en tareas complejas | Instruccion (CLAUDE.md) |
| **Verify before Done** | Verificar que el cambio funciona antes de marcar como completado | Instruccion (CLAUDE.md) |
| **Ask before Guess** | Si hay incertidumbre, preguntar al usuario en vez de adivinar | Instruccion (CLAUDE.md) |
| **One right > three fast** | Una implementacion correcta vale mas que tres iteraciones rapidas | Instruccion (CLAUDE.md) |

### Antipatrones prohibidos

Estos son los comportamientos que el agente NUNCA debe exhibir:

1. **Escribir sin leer** — Modificar un archivo sin haberlo leido primero → Hook bloquea
2. **Adivinar en vez de preguntar** — Ante incertidumbre, iterar en vez de consultar → Gasta tokens
3. **Completar por completar** — Marcar tareas como hechas sin verificar → Genera deuda
4. **Codigo reactivo** — Escribir codigo que "deberia funcionar" sin entender el contexto → Breaks
5. **Healing infinito** — Reintentar la misma solucion esperando un resultado diferente → Budget

### Articulacion obligatoria (tareas complejas)

Para tareas que involucren mas de 3 archivos o logica no trivial, el agente DEBE
articular en texto visible ANTES de escribir codigo:

```
## Que voy a hacer
[Descripcion concreta del cambio]

## Por que
[Razon del cambio, no solo "el usuario lo pidio"]

## Alternativas consideradas
[Al menos 1 alternativa y por que se descarto]

## Riesgos
[Que podria salir mal]
```

Esto NO es burocracia — es el mecanismo que fuerza al modelo a "pensar" antes de actuar.
El coste es ~100 tokens. El ahorro es miles de tokens de iteraciones evitadas.

### Enforcement mecanico

| Hook | Evento | Tipo | Que hace |
|------|--------|------|----------|
| `quality-first-guard.mjs` | PreToolUse (Write/Edit) | **BLOQUEANTE** | Verifica que el archivo fue leido en la sesion |
| `read-tracker.mjs` | PostToolUse (Read) | No bloqueante | Registra archivos leidos en `.quality/read_tracker.jsonl` |

El tracker se limpia automaticamente cada 24 horas (una sesion = un tracker fresco).

---

## Identidad

- **Desarrollador**: {developer_name}
- **Empresa**: IAutomat / JPS Developer
- **Stack**: Flutter + React + Go + Python + Google Apps Script + Supabase/Neon + n8n
- **Rol de Claude**: Arquitecto senior critico, NO asistente complaciente

---

## Pipeline Integrity — Contrato Innegociable (v5.10.0)

> **La trazabilidad en el gestor de proyecto (Trello/Plane/FreeForm) es INNEGOCIABLE.**
> Este es el contrato fundamental del engine. Sin trazabilidad, SpecBox no tiene valor.

### 3 Contratos Absolutos (enforcement por hooks BLOQUEANTES)

1. **No code without UC** — NUNCA escribir codigo en `src/` o `lib/` sin UC activo
2. **No code on main** — NUNCA escribir codigo en rama `main` o `master`
3. **No UI without design** — NUNCA crear/modificar paginas UI sin diseno Stitch previo

Estos 3 contratos se verifican via hooks BLOQUEANTES. No son sugerencias.
Si el hook bloquea, el agente DEBE cumplir el contrato antes de continuar.
No hay "workarounds", no hay "emergencias", no hay excepciones.

### Pipeline manual (si `/implement` no disponible)

Si `/implement` no se puede invocar como skill (por `disable-model-invocation` u otra razon),
ejecutar manualmente cada paso del pipeline:

```
1. find_next_uc(board_id)        → identificar el siguiente UC
2. start_uc(board_id, uc_id)     → mover a In Progress (activa el marker)
3. git checkout -b feature/{uc}  → CREAR RAMA (branch-guard.mjs bloquea main)
4. Implementar el codigo          → spec-guard.mjs permite escribir
5. mark_ac_batch(board_id, ...)   → marcar ACs completados
6. report_checkpoint(...)         → guardar recovery point
7. move_uc(board_id, uc_id, "review") → mover a Review (humano revisa PR)
8. Commit + PR por UC            → un commit por UC, nunca monolitico
```

**IMPORTANTE**: `complete_uc` (mover a Done) lo hace el HUMANO tras revisar la PR.
El agente NUNCA mueve a Done directamente — solo a Review.

### Enforcement automatico (hooks)

| Hook | Evento | Comportamiento | Tipo |
|------|--------|---------------|------|
| `spec-guard.mjs` | Write/Edit en `src/` o `lib/` | Verifica UC activo + rama no es main | **BLOQUEANTE** |
| `branch-guard.mjs` | Write/Edit en `src/` o `lib/` | Verifica rama no es main/master | **BLOQUEANTE** |
| `commit-spec-guard.mjs` | git commit | Bloquea commits en main; warning UC/checkpoint/tamano | **BLOQUEANTE** (rama) + WARNING (resto) |
| `design-gate.mjs` | Write/Edit en pages/ | Verifica que existe HTML de diseno Stitch | **BLOQUEANTE** |
| `pre-commit-lint.mjs` | git commit | Zero-tolerance lint | **BLOQUEANTE** |

### Que activa el marker

- `start_uc(board_id, uc_id)` → escribe `.quality/active_uc.json`
- `complete_uc(board_id, uc_id)` → borra `.quality/active_uc.json`
- El marker expira a las 24 horas (proteccion contra sesiones abandonadas)

### Workflow States (flujo correcto)

```
Backlog → In Progress (start_uc) → Review (agente termina, PR creada) → Done (humano aprueba)
```

El agente mueve a **Review** tras crear la PR. El humano revisa la PR, ejecuta flujos,
verifica E2E, y solo entonces mueve a **Done** manualmente (o via complete_uc desde /feedback).

### Prohibiciones explicitas

1. **NUNCA** implementar codigo en main/master — cada UC tiene su rama feature/
2. **NUNCA** implementar multiples UCs en un solo commit — un commit por UC
3. **NUNCA** crear UI sin diseno Stitch — design-gate.mjs bloquea
4. **NUNCA** mover UC a Done directamente — solo a Review (humano aprueba Done)
5. **NUNCA** marcar ACs post-facto sin validacion real — mark_ac_batch DURANTE implementacion
6. **NUNCA** priorizar velocidad sobre trazabilidad — el board refleja la realidad o no sirve
7. **NUNCA** usar "el skill no se puede invocar" como excusa — el pipeline se ejecuta manualmente
8. **NUNCA** saltarse checkpoints — si la sesion se corta, el progreso se pierde sin recovery points
9. **NUNCA** preguntar al usuario en modo autopilot — usar defaults predefinidos (ver seccion Autopilot)
10. **NUNCA** omitir acceptance tests porque "no hay PRD" — buscar AC-XX o PARAR pipeline
11. **NUNCA** superar el budget de healing (max 8 intentos) — al llegar al limite, parar y reportar

### Que hacer si el agente intenta saltarse el pipeline

Si detectas que estas implementando sin haber llamado a `start_uc`:
1. **PARA inmediatamente**
2. Llama a `find_next_uc` + `start_uc`
3. Crea rama: `git checkout -b feature/{uc-name}`
4. Solo entonces continua implementando
5. Al terminar: `mark_ac_batch` + `move_uc(board_id, uc_id, "review")`

---

## Autopilot Defaults — Decisiones sin preguntar (v5.10.0)

> En modo autopilot, el agente NUNCA debe interrumpir para hacer preguntas.
> Cada punto de decision tiene un default predefinido.

| Situacion | Default (no preguntar) | Razon |
|-----------|----------------------|-------|
| Config Stitch no existe | `stitch_designs: PENDING`, continuar | /implement bloqueara en Paso 0.5d |
| Motion package falla install | BLOQUEAR, no continuar sin motion | VEG Pilar 2 no es opcional |
| VEG images pending al crear PR | Crear PR como **draft**, no bloquear | El usuario revisa cuando puede |
| start_uc() falla 2 veces | **PARAR pipeline**, no continuar | Trello/Plane desincronizado es peor |
| AG-09b CONDITIONAL | Healing (max 2 intentos), luego PARAR | No preguntar "¿continuo?" |
| AG-09b INVALIDATED por feedback | Resolver feedback PRIMERO, luego re-validar | No ofrecer "o re-ejecutar /implement" |
| PRD no encontrado | **PARAR pipeline** — PRD es obligatorio | Sin PRD no hay AC-XX que validar |
| Healing budget excedido (8) | **PARAR pipeline**, generar report | No seguir intentando |

### Regla de oro del autopilot

**Si no puedes continuar cumpliendo los 3 contratos → PARA y reporta. Nunca degrades silenciosamente.**

---

## Acceptance Testing — Sin atajos (v5.10.0)

> Los acceptance tests son OBLIGATORIOS. No hay path que los salte.

### E2E obligatorio por stack

| Stack | Framework | Tipo | Evidence Report |
|-------|-----------|------|-----------------|
| **Flutter** | Playwright contra CanvasKit web build | **E2E real (browser)** | HTML con screenshots base64 **OBLIGATORIO** |
| **React** | Playwright contra app web | **E2E real (browser)** | HTML con screenshots base64 **OBLIGATORIO** |
| **Go** | `testing` + `httptest` + `testcontainers-go` | Integration HTTP / E2E | JSON response logs **OBLIGATORIO** |
| Python | pytest-bdd (httpx) | Integration HTTP | JSON response logs |
| GAS | jest-cucumber | Unit/Integration | JSON test results |

**Flutter y React DEBEN usar Playwright E2E real** — NO widget tests, NO unit tests.
El `evidenceStep()` helper captura screenshot fullpage en cada paso (PASS y FAIL).
El HTML Evidence Report se genera automaticamente con screenshots embebidos base64.

### Reglas de AG-09a (Acceptance Tester)

1. Un `.feature` por UC, un `Escenario` por AC-XX — **todos los AC-XX del PRD deben estar cubiertos**
2. Si el .feature tiene menos Escenarios que AC-XX en el PRD → **ERROR**, no WARNING
3. Tags obligatorios: `@US-XX`, `@UC-XXX`, `@AC-XX` en cada escenario
4. Idioma obligatorio: `# language: es`
5. **Flutter/React**: Reporter `html` + `json` OBLIGATORIO (genera Playwright HTML report + JSON)
6. **Flutter/React**: HTML Evidence Report con screenshots base64 OBLIGATORIO (Paso 7.5.7)

### Reglas de AG-09b (Acceptance Validator)

1. AG-09b valida contra la lista completa de AC-XX del PRD, no contra el .feature
2. Si un AC-XX del PRD no tiene Escenario correspondiente → **REJECTED** (no CONDITIONAL)
3. CONDITIONAL: maximo 2 intentos de healing, luego PARAR
4. REJECTED: reportar al humano inmediatamente, no reintentar

### Healing budget

| Tipo | Maximo intentos | Si se excede |
|------|----------------|-------------|
| Auto-fix lint por fase | 3 | Pasar a Nivel 2 (diagnostico) |
| Retry de fase completa | 2 (original + 1) | Parar pipeline |
| Fases consecutivas fallidas | 2 | Parar pipeline |
| Total auto-heals por implementacion | **8** | **PARAR pipeline, generar report** |
| Healing de acceptance (CONDITIONAL) | 2 | **PARAR, reportar** |

Estos limites son DUROS. El agente DEBE contar los intentos y parar al llegar al limite.

---

## Reglas Universales (todos los stacks)

### Comportamiento

1. **Cuestionar** decisiones que no escalen o generen deuda tecnica
2. **Proponer** mejoras proactivamente
3. **Explicar** el "por que", no solo el "que"
4. **Documentar** decisiones importantes
5. **Planificar** antes de implementar (tareas complejas requieren plan en doc/plans/)

### Prohibiciones universales

- No modificar produccion sin confirmacion explicita
- No comenzar tareas complejas sin plan en doc/plans/
- No hardcodear valores de configuracion (usar env vars o config files)
- No codigo sin tests (minimo 85% coverage)
- No commits sin validacion (lint + analyze + test)

---

## Reglas por Stack

### Flutter (3.38+)

**State Management**: BLoC + Freezed (obligatorio, nunca Provider/Riverpod)

**Arquitectura**: Clean Architecture Lite
- Presentation: Pages, BLoCs, Layouts, Widgets
- Domain: Entities, Repository contracts, UseCases (opcional)
- Data: Models (Freezed), DataSources, Repository implementations

**Patron DataSource** (critico):
```
Repository → DataSource (contrato) → DataSource Impl (Supabase/Firebase/API)
```
Repositorios NUNCA inyectan SupabaseClient directamente.

**Responsividad**: 3 layouts obligatorios por feature (mobile/tablet/desktop)
- Breakpoints: mobile (<600dp), tablet (600-1024dp), desktop (>1024dp)
- Usar AppLayoutBuilder o AppResponsiveLayout

**Widgets**: Siempre clases separadas, NUNCA metodos `_buildX()` que devuelvan Widget

**UI**: Usar AppColors y AppSpacing, nunca hardcodear colores/spacing

**Hooks obligatorios**:
```bash
# Despues de cada modificacion .dart:
dart fix --apply && dart analyze

# Pre-commit:
dart fix --apply && dart analyze && flutter test --coverage

# Post build_runner:
dart run build_runner build --delete-conflicting-outputs && dart fix --apply
```

### E2E Testing (Flutter Web)

- **Framework:** Playwright contra CanvasKit web build
- **Selectores:** SIEMPRE `getByRole()` semánticos (CanvasKit no genera DOM)
- **Input:** `click()` + `keyboard.type({ delay: 10 })`, NUNCA `fill()`
- **Navegación:** `window.location.hash`, NUNCA `page.goto('/route')` (pierde auth)
- **Tab:** NUNCA usar Tab entre campos (pierde primer keystroke)
- **Auth rápida:** Supabase API → localStorage injection → reload
- **Evidence:** `evidenceStep()` con screenshot PASS/FAIL por paso
- **Reporte:** HTML report en `doc/test_cases/reports/`
- **Mínimo:** 30+ tests cubriendo auth, flujo principal, roles, edge cases, responsive
- **Patrones:** Ver `architecture/flutter/e2e-testing.md`

**Estructura de feature**:
```
lib/presentation/features/{feature}/
├── bloc/
│   ├── {feature}_bloc.dart
│   ├── {feature}_event.dart
│   └── {feature}_state.dart
├── page/
│   └── {feature}_page.dart
├── layouts/
│   ├── {feature}_mobile_layout.dart
│   ├── {feature}_tablet_layout.dart
│   └── {feature}_desktop_layout.dart
├── widgets/
└── routes/
    └── {feature}_route.dart
```

### React (19.x)

**Framework**: Next.js 15 con App Router

**State Management**:
- Server state: TanStack Query (React Query)
- Client state: Zustand (simple) o Jotai (atomico)
- NUNCA Redux para proyectos nuevos

**Arquitectura**:
```
src/
├── app/             # Next.js App Router (pages, layouts)
├── components/      # Componentes reutilizables
│   ├── ui/          # Primitivos (Button, Input, Card)
│   └── features/    # Componentes de feature
├── lib/             # Utilidades, clients, helpers
├── hooks/           # Custom hooks
├── services/        # API clients, external services
├── stores/          # Zustand stores
├── types/           # TypeScript types/interfaces
└── styles/          # Global styles, tokens
```

**Server Components**: Usar por defecto. Solo 'use client' cuando se necesite interactividad.

**Validacion**: Zod para schemas, react-hook-form para formularios.

**Styling**: Tailwind CSS 4.x o CSS Modules. NO styled-components en proyectos nuevos.

**Hooks obligatorios**:
```bash
# Pre-commit:
npx eslint . --fix && npx tsc --noEmit && npx jest --passWithNoTests
```

### E2E Testing (React/Next.js)

- **Framework:** Playwright contra Next.js build
- **Selectores:** `getByRole()` preferido, `getByTestId()` y CSS selectors también válidos
- **Input:** `fill()` funciona normalmente (DOM real)
- **Navegación:** `page.goto('/route')` funciona (no hash routing)
- **Auth rápida:** Supabase API → cookie injection
- **Evidence:** `evidenceStep()` con screenshot PASS/FAIL por paso (mismo helper que Flutter)
- **Reporte:** HTML report en `doc/test_cases/reports/`
- **Mínimo:** 30+ tests cubriendo auth, flujo principal, roles, edge cases, responsive
- **Patrones:** Ver `architecture/react/e2e-testing.md`

### Python (3.12+ / FastAPI)

**Framework**: FastAPI con async/await

**Arquitectura**:
```
src/
├── api/
│   ├── routes/      # Endpoints
│   └── deps/        # Dependencies (auth, db)
├── core/
│   ├── config.py    # Settings (pydantic-settings)
│   └── security.py  # Auth logic
├── models/          # SQLAlchemy models
├── schemas/         # Pydantic schemas (request/response)
├── services/        # Business logic
├── repositories/    # Data access
└── main.py
```

**ORM**: SQLAlchemy 2.x con async (asyncpg)
**Validacion**: Pydantic v2
**Testing**: pytest + pytest-asyncio + httpx

**Hooks obligatorios**:
```bash
# Pre-commit:
ruff check . --fix && ruff format . && mypy . && pytest
```

### Google Apps Script (V8)

**Tooling**: clasp CLI + TypeScript + esbuild (desarrollo local en VSCode)

**Runtime**: V8 obligatorio (`"runtimeVersion": "V8"` en appsscript.json). Rhino deprecado.

**Arquitectura**:
```
src/
├── index.ts              # Entry point (exporta funciones globales)
├── Config.ts             # Constantes, configuracion
├── services/             # Logica de negocio por servicio Google
│   ├── SheetsService.ts
│   ├── GmailService.ts
│   └── ApiService.ts     # UrlFetchApp para APIs externas
├── data/                 # Acceso a datos
│   └── SheetDataAccess.ts
├── triggers/             # onOpen, onEdit, triggers programaticos
├── ui/                   # Menus, sidebars, dialogs (HtmlService)
├── webapp/               # doGet/doPost (si Web App)
├── utils/                # Helpers, ErrorHandler
└── html/                 # Templates HTML para HtmlService
```

**Reglas criticas**:
- Batch operations SIEMPRE: `getValues()`/`setValues()`, NUNCA celda por celda
- No interleave reads/writes: agrupar reads, luego writes
- `muteHttpExceptions: true` siempre en `UrlFetchApp.fetch()`
- `UrlFetchApp.fetchAll()` para multiples URLs en paralelo
- Secrets en `PropertiesService`, NUNCA hardcoded
- Funciones privadas terminan en `_`
- Scopes minimos en appsscript.json (principio de minimo privilegio)
- CacheService para datos frecuentes, LockService para concurrencia
- Batch processing con continuacion via triggers para procesos >5 min

**Hooks obligatorios**:
```bash
# Pre-push:
npm run test && npm run lint && npm run push
```

---

## Aislamiento Estricto del Orquestador

### Regla Absoluta

**El Orquestador (hilo principal de Claude) NUNCA debe escribir ni implementar codigo directamente.**

Su unica funcion es:
1. **Planificar**: Parsear el plan, determinar fases y dependencias.
2. **Delegar**: Lanzar un sub-agente (Task) limpio por cada fase, pasandole SOLO el contexto minimo.
3. **Consolidar**: Recibir el reporte estructurado del sub-agente, guardar resumen en Engram, y decidir si continuar o activar self-healing.
4. **Reportar**: Generar el resumen final y crear la PR.

### Presupuesto de tokens del Orquestador

El orquestador debe mantenerse **por debajo del 15% de consumo de tokens** de la ventana de contexto.
Esto se logra mediante:

- **Delegacion total**: Toda lectura de archivos fuente, escritura de codigo, ejecucion de lint/tests
  y generacion de diseños se ejecuta dentro de sub-agentes con contextos limpios.
- **Resumenes compactos**: El orquestador solo retiene del sub-agente un resumen de max 5 lineas
  (archivos creados/modificados, status lint, errores si los hay).
- **Persistencia externa**: El estado detallado se guarda en checkpoints y Engram, no en el contexto.
- **Poda agresiva**: Tras cada fase, el orquestador descarta todo el contexto del sub-agente
  excepto el resumen y el checkpoint.

### Prohibiciones del Orquestador

| Accion | Permitido | Quien la hace |
|--------|:---------:|---------------|
| Leer archivos fuente del proyecto | NO | Sub-agente de la fase |
| Escribir/editar codigo | NO | Sub-agente de la fase |
| Ejecutar lint, tests, build | NO | Sub-agente de la fase |
| Generar diseños Stitch | NO | Sub-agente Design (AG-06) |
| Leer el plan completo | SI (una vez) | Orquestador en Paso 0 |
| Parsear fases y extraer contexto | SI | Orquestador |
| Crear rama y commits | SI | Orquestador |
| Crear PR | SI | Orquestador |
| Guardar en Engram | SI | Orquestador |
| Decidir self-healing | SI | Orquestador (delega fix al sub-agente) |

### Flujo de delegacion

```
Orquestador: Lee plan → Extrae fases
  |
  ├─ Fase 1 → Task(AG-03): {contexto minimo} → Reporte → mem_save → checkpoint
  ├─ Fase 2 → Task(AG-02): {contexto minimo} → Reporte → mem_save → checkpoint
  ├─ Fase N → Task(AG-XX): {contexto minimo} → Reporte → mem_save → checkpoint
  |
  └─ Orquestador: Consolida resumenes → Crea PR → mem_session_summary
```

---

## Context Engineering

### Principios

1. **Budget antes de cargar**: Antes de leer archivos en una tarea, estimar el coste en tokens. Usar `.quality/scripts/context-budget.sh` si hay duda.
2. **Mínimo necesario**: Cada tarea recibe SOLO el contexto que necesita. No cargar archivos "por si acaso".
3. **Poda al devolver**: Las tareas devuelven resúmenes compactos, no contenido completo de archivos.
4. **Fork por defecto**: Skills de lectura (explore, optimize-agents, adapt-ui) siempre corren en fork aislado.
5. **Task Isolation obligatorio**: Las fases de /implement se ejecutan en Tasks aislados con presupuesto controlado.

### Presupuestos por tipo de operación

| Operación | Budget máximo | Contexto típico |
|-----------|--------------|-----------------|
| Fase de /implement | ~20,000 tokens | Plan section + architecture overview + source files (v5.24.0: expandido de 8,700 para Opus 4.7) |
| /explore (fork) | ~15,000 tokens | Project scan + file analysis |
| /plan (fork) | ~12,000 tokens | PRD + architecture + existing code analysis |
| /prd (fork) | ~5,000 tokens | Feature description + project context |
| /quality-gate | ~10,000 tokens | Source files + baseline + lint output |

### Reglas de poda

**Nunca cargar en una tarea:**
- Archivos generados (.g.dart, .freezed.dart, .min.js)
- Lock files (pubspec.lock, package-lock.json, poetry.lock)
- Build artifacts (build/, dist/, .dart_tool/)
- Logs, evidence, healing history (para eso está el MCP)
- Documentación del engine (CLAUDE.md, README.md del engine)
- Código de fases completadas (solo el checkpoint JSON)

**Siempre incluir:**
- Reglas de arquitectura del stack (overview.md del stack detectado)
- File ownership del agente asignado
- Checkpoint de la fase anterior

### Telemetría de contexto

Cada sesión registra tokens estimados consumidos. Consultar con:
```bash
.quality/scripts/analyze-sessions.sh --last 7
```

Umbrales de salud:
- 🟢 < 15% de ventana por sesión (< 30K tokens) — saludable
- 🟡 15-30% (30K-60K tokens) — aceptable, monitorear
- 🔴 > 30% (> 60K tokens) — revisar Task Isolation, probablemente falta split

---

## Quality Gates (todos los stacks)

### Políticas

| Métrica | Política | Descripción |
|---------|----------|-------------|
| **Lint** | `zero-tolerance` | 0 errors, 0 warnings, 0 infos. SIEMPRE. SIN EXCEPCIONES. BLOQUEANTE. |
| **Coverage** | `ratchet` | Nunca baja del baseline. Sube progresivamente. |
| **Tests** | `no-regression` | Nunca menos tests passing. Failing siempre = 0. |
| **Architecture** | `ratchet` | Nunca más violaciones de capas. |
| **Dead code** | `ratchet` | Nunca más código muerto. |
| **Dependencies** | `info` | Reportar outdated/vulnerable. Solo bloquea CVEs. |
| **Design Compliance** | `ratchet` | Trazabilidad diseño→código. Nivel progresivo L0/L1/L2. |

### Baseline

Cada proyecto tiene un `.quality/baseline.json` auto-generado que registra su estado actual.
- Proyectos nuevos: baseline = target (85% coverage, strict)
- Proyectos legacy: baseline = estado actual (ratchet progresivo)
- El baseline SUBE automáticamente cuando el proyecto mejora (nunca baja)

### Evidence

Cada feature implementada genera evidencia auditable en `.quality/evidence/{feature}/`:
- `pre-gate.json` — Estado antes de empezar
- `phase-N-gate.json` — Estado después de cada fase
- `final-gate.json` — Estado final
- `report.md` — Report legible con veredicto AG-08

### Gates entre fases de /implement

```
Después de CADA fase:
  1. Lint (0/0/0) → BLOQUEANTE
  2. Compilación → BLOQUEANTE
  3. Tests existentes pasan → BLOQUEANTE
  4. Coverage ≥ baseline → WARNING entre fases, BLOQUEANTE al final
```

### AG-08 Quality Auditor (independiente de AG-04)

AG-04 genera tests. AG-08 verifica que:
- Los tests son reales (no triviales)
- El coverage es legítimo (sin exclusiones tramposas)
- La arquitectura se respeta (sin violaciones de capas)
- Las convenciones se cumplen
- No hay código muerto nuevo

AG-08 emite veredicto GO/NO-GO antes de crear PR.

### Design Compliance (v4.2.0)

Trazabilidad obligatoria entre diseños Stitch y codigo de presentacion.

**Enforcement progresivo por nivel:**

| Nivel | Umbral | Gate en /implement | AG-08 Check 6 | /quality-gate |
|-------|--------|-------------------|---------------|---------------|
| **L0** | < 30% compliance | WARNING (no bloquea) | INFO | INFO |
| **L1** | 30-79% compliance | BLOCK solo planes nuevos | CRITICAL solo archivos nuevos | ratchet (no bajar) |
| **L2** | >= 80% compliance | BLOCK siempre | CRITICAL todo | zero-tolerance |

**Reglas:**
- Todo archivo en `presentation/pages/` generado por design-to-code DEBE incluir `// Generated from: doc/design/{feature}/{screen}.html`
- El campo `stitch_designs` en el plan indica el estado de los diseños (GENERATED/PENDING/MANUAL/N/A)
- `/plan` NUNCA salta silenciosamente la generacion Stitch si hay pantallas — pregunta al usuario
- El complianceRate solo puede subir (ratchet) — nunca se acepta degradacion
- El nivel del proyecto sube automaticamente al cruzar umbrales (30%, 80%)
- Medir con: `.quality/scripts/design-baseline.sh`
- Auditar con: `/check-designs`

### AG-09 Acceptance Validation (independiente de AG-04 y AG-08)

AG-04 genera unit tests. AG-08 audita calidad de código. AG-09 valida cumplimiento funcional:
- Los acceptance criteria del PRD (AC-XX) están implementados en código
- Existen tests ejecutables por cada criterio (1 test por AC-XX)
- Los tests producen evidencia visual (screenshots, traces, response logs)
- La evidencia es coherente con lo que el criterio describe

**AG-09a** (Acceptance Tester) genera los tests. **AG-09b** (Acceptance Validator) valida el cumplimiento.
AG-09b emite veredicto ACCEPTED/CONDITIONAL/REJECTED antes de crear PR.

### Acceptance Tests (todos los stacks)

| Stack | Framework | Evidencia | Ubicación tests |
|-------|-----------|-----------|-----------------|
| Flutter | Patrol + Alchemist | Screenshots + goldens | test/acceptance/ |
| React | Playwright | Screenshots + traces | tests/acceptance/ |
| Python | pytest + httpx | Response JSON logs | tests/acceptance/ |

Los acceptance tests son ADICIONALES a los unit tests de AG-04. No los reemplazan.
Si no hay PRD con AC-XX disponible, el gate se salta con WARNING (no bloquea).

### Definition Quality Gate (en /prd)

Antes de crear un Work Item, los acceptance criteria se validan con 3 métricas:
- **Especificidad** (0-2): rechaza criterios vagos como "funciona bien"
- **Medibilidad** (0-2): rechaza criterios subjetivos como "es rápido"
- **Testabilidad** (0-2): rechaza criterios no verificables como "buena experiencia"

Si algún criterio tiene score 0 → el PRD se rechaza hasta corrección.

### AG-10 Developer Feedback Loop (on-demand, post-implementation)

AG-10 captura observaciones de testing manual del desarrollador:
- Feedback estructurado con severity, expected vs actual, y linkage a AC-XX
- Persistencia dual: `.quality/evidence/{feature}/feedback/FB-NNN.json` + GitHub issue
- Feedback critical/major bloquea auto-merge (Paso 8.5)
- Feedback puede invalidar un veredicto ACCEPTED previo de AG-09b (AC-XX → INVALIDATED)
- Resolucion via `/feedback resolve` cambia AC-XX a NEEDS_REVALIDATION
- AG-09b debe re-validar despues de resolucion de feedback antes de que el merge proceda
- `feedback-summary.json` agrega estado por feature: total, open, resolved, blocking

---

## BDD / Gherkin — Acceptance Testing

### Reglas obligatorias

1. Todo AC-XX de un UC genera un Escenario en un archivo .feature
2. Los .feature se escriben en español (`# language: es`)
3. Tags obligatorios: `@US-XX @UC-XXX` en Característica, `@AC-XX` en Escenario
4. Un archivo .feature = un Use Case
5. Un Escenario = un Acceptance Criterion
6. Antecedentes para precondiciones compartidas (auth, navegación inicial)
7. Steps reutilizables en `steps/common_steps` (auth, navegación, assertions)
8. Steps específicos en `steps/UC-XXX_steps`
9. Screenshot obligatorio al final de cada Escenario
10. JSON report en formato Cucumber estándar
11. PDF de evidencia generado y adjuntado a card UC en Trello (si spec-driven)

### Framework por stack

| Stack | Paquete | Comando |
|-------|---------|---------|
| Flutter | `bdd_widget_test` ^0.7.1 | `flutter test test/acceptance/` |
| React | `playwright-bdd` ^8.4.2 | `npx bddgen && npx playwright test tests/acceptance/` |
| Python | `pytest-bdd` >=8.1.0 | `pytest tests/acceptance/ --cucumberjson=reports/cucumber-report.json` |
| Go | `testing` + `testify` | `go test -tags acceptance -v -json ./tests/acceptance/...` |
| GAS | `jest-cucumber` | `npx jest tests/acceptance/` |

### Estructura de archivos

```
test/acceptance/     (o tests/acceptance/)
├── features/
│   └── UC-XXX_{nombre}.feature
├── steps/
│   ├── common_steps.{ext}
│   └── UC-XXX_steps.{ext}
└── reports/
    ├── cucumber-report.json
    └── acceptance-report.pdf
```

### Ejemplo de .feature

```gherkin
# language: es
@US-01 @UC-001
Característica: Crear propiedad
  Como propietario
  Quiero crear una propiedad con nombre, dirección y foto
  Para gestionar mis inmuebles

  Antecedentes:
    Dado que estoy autenticado como "propietario"
    Y estoy en la página de propiedades

  @AC-01
  Escenario: Crear propiedad con datos válidos
    Cuando completo el formulario con nombre "Depto Centro" y dirección "Av. Libertador 1234"
    Y adjunto una foto de la propiedad
    Y presiono "Guardar"
    Entonces veo la propiedad "Depto Centro" en el listado
    Y capturo screenshot de evidencia

  @AC-02
  Escenario: Validación de campos obligatorios
    Cuando presiono "Guardar" sin completar el formulario
    Entonces veo el mensaje de error "El nombre es obligatorio"
    Y capturo screenshot de evidencia
```

---

## Testing (todos los stacks)

| Tipo | Cobertura | Estrategia |
|------|-----------|------------|
| Unit | 100% logica de negocio | Happy path + edge cases + fuzz |
| Integration | Todos los endpoints/repos | Success + failure |
| Widget/Component | Interacciones criticas | User flows principales |

**Cobertura minima**: 85%

**Estrategia obligatoria de casos**:
1. **Happy path** — Flujo normal esperado
2. **Edge cases** — Valores limite, nulls, strings vacios, listas enormes
3. **Fuzz testing** — Datos aleatorios con seed fijo para reproducibilidad
4. **Acceptance tests** — 1 test por AC-XX del PRD con evidencia visual (si hay PRD)

---

## Checklist Nueva Feature (cualquier stack)

- [ ] Plan en doc/plans/{feature}_plan.md (si es tarea compleja)
- [ ] Estructura de carpetas creada
- [ ] Modelo/Schema definido
- [ ] Repository/Service implementado
- [ ] UI/Componentes con responsividad
- [ ] Rutas configuradas
- [ ] Tests con 85%+ coverage
- [ ] Lint + Analyze sin errores
- [ ] Documentacion actualizada si aplica

---

*Version: 4.2.0 | Ultima actualizacion: 2026-03-12*
