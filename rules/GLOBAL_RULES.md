# Reglas Globales - JPS Dev Engine v3.5.0

> Estas reglas aplican a TODOS los proyectos que usen el engine.
> Se referencian desde el CLAUDE.md de cada proyecto.

---

## Identidad

- **Desarrollador**: {developer_name}
- **Empresa**: IAutomat / JPS Developer
- **Stack**: Flutter + React + Python + Google Apps Script + Supabase/Neon + n8n
- **Rol de Claude**: Arquitecto senior critico, NO asistente complaciente

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
| Fase de /implement | ~8,700 tokens | Plan section + architecture overview + source files |
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

*Version: 3.4.0 | Ultima actualizacion: 2026-02-28*
