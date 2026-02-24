# /optimize-agents (Global)

Analiza el sistema multi-agente del proyecto actual y propone optimizaciones.
Soporta tanto el patrón legacy (`.claude/agents/` + `ORCHESTRATOR.md`) como el sistema nativo de **Agent Teams** de Claude Code.

## Uso

```
/optimize-agents [mode]
```

**Modos:**
- `audit` (default) — Analiza y reporta inline, sin modificar archivos
- `report` — Genera report detallado en `doc/plans/agent_optimization_report.md`
- `apply` — Analiza, muestra cambios propuestos, pide confirmación, aplica
- `team-init` — Genera configuración completa de Agent Teams para el proyecto
- `migrate` — Propone plan de migración de `.claude/agents/` a Agent Teams nativo

---

## Paso 0: Detectar Proyecto y Sistema de Agentes

### 0.1 Detectar Stack Tecnológico

Buscar en la raíz del proyecto:

| Archivo | Stack | Substacks a detectar |
|---------|-------|---------------------|
| `pubspec.yaml` | Flutter/Dart | BLoC/Riverpod, Material/Cupertino, Supabase/Firebase, Stripe |
| `package.json` | Node | React/Vue/Next/Svelte, Express/Fastify/Hono, Prisma/Drizzle, Stripe, Neon |
| `requirements.txt` o `pyproject.toml` | Python | Django/FastAPI/Flask, SQLAlchemy/Tortoise, Stripe, Neon |
| `Cargo.toml` | Rust | Axum/Actix/Rocket, Diesel/SQLx |
| `go.mod` | Go | Gin/Echo/Fiber, GORM/SQLx |
| `Gemfile` | Ruby | Rails/Sinatra, ActiveRecord |
| `*.csproj` o `*.sln` | .NET/C# | ASP.NET, EF Core |

**Detección multi-stack**: Si el proyecto tiene múltiples archivos de configuración (ej: `pubspec.yaml` + `package.json` + `requirements.txt`), guardar TODOS como `$STACKS[]`. Esto es común en monorepos y proyectos como los de IAutomat.

**Detección de infra**:
| Archivo/Directorio | Infra |
|-------------------|-------|
| `supabase/` o refs a `supabase` | Supabase |
| `firebase.json` o `google-services.json` | Firebase |
| refs a `neon` o `@neondatabase/serverless` en package.json/requirements.txt | Neon.tech (Serverless Postgres) |
| refs a `stripe` en package.json/requirements.txt/pubspec.yaml | Stripe (Pagos) |
| `.github/workflows/` | GitHub Actions CI/CD |
| `docker-compose.yml` | Docker |
| `n8n/` o refs a `n8n` | n8n workflows |
| `vercel.json` o `netlify.toml` | Edge deploy |
| `.claude/settings.local.json` con `stitch.projectId` o MCP `mcp__stitch__*` disponible | Google Stitch (Design-to-Code) |
| `doc/design/` con archivos `.html` | Stitch HTML designs existentes |

Guardar como `$STACK` (principal) y `$INFRA[]`.

### 0.2 Detectar Sistema de Agentes (Dual: Legacy + Native Teams)

**Sistema Legacy (`.claude/agents/`):**
```
.claude/agents/           → $HAS_LEGACY_AGENTS
.claude/ORCHESTRATOR.md   → $HAS_ORCHESTRATOR
.claude/commands/         → $HAS_COMMANDS
.claude/memory/           → $HAS_MEMORY
CLAUDE.md                 → $HAS_PROJECT_CLAUDE
.claude/design/           → $HAS_DESIGN_SYSTEM
doc/design/               → $HAS_STITCH_DESIGNS
doc/plans/                → $HAS_PLANS
stitch config in settings → $HAS_STITCH_MCP
```

**Sistema Nativo (Agent Teams):**
```
~/.claude/teams/          → $HAS_NATIVE_TEAMS (buscar equipos del proyecto actual)
~/.claude/tasks/          → $HAS_NATIVE_TASKS
settings.json con CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS → $TEAMS_ENABLED
```

**Clasificar el estado:**

| Legacy Agents | Native Teams | Estado |
|:---:|:---:|---|
| No | No | `NO_AGENTS` — Proponer setup desde cero |
| Sí | No | `LEGACY_ONLY` — Funcionar + proponer migración |
| No | Sí | `NATIVE_ONLY` — Auditar sistema nativo |
| Sí | Sí | `HYBRID` — Auditar ambos + detectar conflictos |

**Si `NO_AGENTS`:**

Mostrar:
```
No se detectó sistema de agentes en este proyecto.

Stack detectado: [$STACK] (+ [$INFRA])

════════════════════════════════════════════════════════════
  OPCIÓN A: Agent Teams Nativo (RECOMENDADO)
════════════════════════════════════════════════════════════

Ejecutar: /optimize-agents team-init

Esto generará:
  1. Activación de CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS en settings.json
  2. Configuración de roles especializados para tu stack
  3. CLAUDE.md con instrucciones de coordinación por rol
  4. team-config.json con estructura del equipo

════════════════════════════════════════════════════════════
  OPCIÓN B: Sistema Legacy (.claude/agents/)
════════════════════════════════════════════════════════════

Crear manualmente:
  .claude/agents/         — Archivos de definición de agentes
  .claude/ORCHESTRATOR.md — Routing y workflow de agentes

Setup mínimo recomendado para [$STACK]:
  1. ArchitectAgent (haiku) — Validar estructura antes de cambios
  2. [Stack]BuilderAgent (sonnet) — Generación de código core
  3. QAValidatorAgent (haiku) — Validación post-cambio
```
**EXIT aquí si no hay agentes Y el usuario no elige opción.**

### 0.3 Inventariar Agentes (Legacy)

Listar todos los archivos en `.claude/agents/*.md`.

Para cada agente, extraer:
- **Nombre** (del `# Título` o nombre de archivo)
- **Rol** (de la línea `**Rol:**`)
- **Modelo recomendado** (de `**Modelo recomendado:**` o "ninguno")
- **Responsabilidades** (lista numerada)
- **Tecnologías referenciadas** (buscar: Firebase, Supabase, Neon, Stripe, Material, Cupertino, React, Next, Django, FastAPI, etc.)
- **¿Referencia `_AGENT_COMMON.md`?** (sí/no)
- **File ownership** (buscar rutas de archivos que el agente modifica)

### 0.4 Inventariar Equipos Nativos (Agent Teams)

Si `$HAS_NATIVE_TEAMS`:
- Leer `~/.claude/teams/*/config.json`
- Para cada team, extraer:
  - **Nombre del team**
  - **Miembros** (nombre, agent_id, agent_type)
  - **Estado** (activo/inactivo — verificar si hay procesos Claude corriendo)
- Leer `~/.claude/tasks/*/`
  - **Tareas pendientes** vs completadas vs en progreso
  - **Tareas huérfanas** (en in_progress sin agente activo)
  - **Dependencias rotas** (dependen de tarea inexistente)

### 0.5 Inventariar Comandos

Listar todos los archivos en `.claude/commands/*.md`.

Para cada comando, extraer:
- **Nombre** (del filename)
- **Agentes referenciados** (@NombreAgente)
- **Número de pasos** del workflow
- **¿Tiene checkpoints?** (buscar "CHECKPOINT", "verificar", "validate", "analyze")
- **¿Usa subagents?** (buscar "Task tool", "subagent", "agent team")

---

## Paso 1: Documentation Sync Analysis (25 puntos)

### 1.1 Detectar Tecnologías Reales del Proyecto

**Flutter/Dart:**
- Buscar en `lib/` imports de material.dart, cupertino.dart
- Buscar en `pubspec.yaml` dependencias: flutter_bloc, riverpod, supabase_flutter, firebase_core, stripe_sdk/flutter_stripe
- Buscar refs a supabase/firebase/stripe en archivos .dart

**Node/TS (React incluido):**
- Buscar en `package.json` dependencias: react (19.x), next, vue, angular, svelte
- Buscar en `package.json` ORMs: prisma, typeorm, drizzle, mongoose
- Buscar en `package.json` frameworks: express, fastify, hono, koa
- Buscar en `package.json` servicios: stripe, @stripe/stripe-js, @neondatabase/serverless
- Buscar en `src/` imports de @tanstack/react-query, zustand, redux, jotai

**Python:**
- Buscar en requirements.txt/pyproject.toml: django, fastapi, flask
- Buscar en requirements.txt/pyproject.toml: sqlalchemy, tortoise, peewee
- Buscar en requirements.txt/pyproject.toml: stripe, neon-serverless, psycopg2 (con refs a neon)

Guardar como `$ACTUAL_TECH`.

### 1.2 Cross-Reference: Agentes vs Tecnología Real

Para cada agente (legacy) o rol definido (native teams):
1. Leer contenido completo del archivo/configuración
2. Buscar referencias a tecnologías
3. Comparar contra `$ACTUAL_TECH`
4. Clasificar mismatches:

| Severidad | Ejemplo |
|-----------|---------|
| **CRITICAL** | Agente referencia Firebase, proyecto usa Supabase |
| **HIGH** | Agente referencia Cupertino widgets, proyecto usa Material 3 |
| **MEDIUM** | Agente referencia REST API, proyecto usa GraphQL |
| **LOW** | Agente menciona nombre de paquete deprecado |

### 1.3 Cross-Reference: ORCHESTRATOR.md vs Agentes

Si `$HAS_ORCHESTRATOR`:
- Comparar lista de agentes en ORCHESTRATOR vs archivos reales en `.claude/agents/`
- Detectar agentes listados pero sin archivo
- Detectar archivos de agente no listados en ORCHESTRATOR
- Verificar modelos coinciden entre ORCHESTRATOR y archivos individuales
- Verificar que agentes deprecated tengan marca visible

### 1.4 Cross-Reference: Comandos vs Agentes

Para cada comando:
- Verificar que agentes referenciados existen
- Verificar que rutas de archivo referenciadas existen en el proyecto
- Verificar que tecnologías mencionadas coinciden con `$ACTUAL_TECH`

### 1.5 Cross-Reference: CONVENTIONS.md vs Agentes

Si `$HAS_MEMORY` y existe `CONVENTIONS.md`:
- Extraer reglas de arquitectura
- Verificar que agentes son consistentes con convenciones
- Detectar contradicciones (ej: convenciones dicen "no data/", agente incluye plantilla con "data/")

**Resultado: `$DOC_SYNC_FINDINGS[]` con severidad por hallazgo**

---

## Paso 2: Validation Strategy Analysis (15 puntos)

### 2.1 Analizar Feature Pipeline

Buscar comando de feature (patrones: `feature.md`, `*-feature.md`).

Si existe:
- Leer el archivo completo
- Extraer pasos del workflow (buscar "### Paso", "### Step", "### Phase")
- Identificar checkpoints (buscar "CHECKPOINT", "✅", "validate", "analyze", "verify")
- Contar: `$TOTAL_STEPS`, `$CHECKPOINT_COUNT`

### 2.2 Evaluar Cobertura de Checkpoints

```
Ratio = $CHECKPOINT_COUNT / max($TOTAL_STEPS - 1, 1)
```

| Ratio | Rating | Recomendación |
|-------|--------|---------------|
| 0% | **POOR** | Añadir checkpoints después de cada fase de agente |
| < 33% | **LOW** | Añadir checkpoints después de fases de generación de código |
| 33-66% | **MODERATE** | Considerar checkpoint después de fase UI |
| > 66% | **GOOD** | Buena cobertura |

### 2.3 Evaluar Calidad de Checkpoints

Para cada checkpoint encontrado:
- ¿Ejecuta análisis estático? (dart analyze, eslint, tsc, etc.)
- ¿Ejecuta tests?
- ¿Tiene instrucción "corregir antes de continuar"?
- ¿Bloquea avance?

### 2.4 Evaluar Hooks de Quality Gate (Agent Teams)

Si `$TEAMS_ENABLED`:
- ¿Existen hooks `TeammateIdle`? → Quality gate cuando un agente termina
- ¿Existen hooks `TaskCompleted`? → Quality gate cuando una tarea se completa
- ¿Los hooks ejecutan linting/testing?

| Hooks | Rating |
|-------|--------|
| Ambos configurados con linting + tests | **EXCELLENT** |
| Solo TaskCompleted | **GOOD** |
| Solo TeammateIdle | **MODERATE** |
| Ninguno | **POOR** — Proponer hooks |

**Resultado: `$VALIDATION_FINDINGS[]`**

---

## Paso 3: Model Optimization Analysis (10 puntos)

### 3.1 Clasificar Tareas de Agentes

Para cada agente/rol, clasificar su tarea principal:

| Tipo de Tarea | Modelo Óptimo | Criterios |
|---------------|---------------|-----------|
| Validación read-only | `haiku` | Grep, analyze, verificar patrones |
| Decisiones de arquitectura | `haiku` | Validación de estructura, sin generar código |
| Generación de código (simple) | `sonnet` | Repositories, modelos, boilerplate |
| Generación de código (complejo) | `sonnet` | UI, lógica compleja, multi-archivo |
| Diseño/planificación estratégica | `opus` | Decisiones arquitectónicas de alto nivel, PRDs |
| **Lead Agent (coordinación)** | `sonnet` | Delegación, síntesis, no genera código |
| **Reviewer (debate/challenge)** | `sonnet` | Revisión de código, hipótesis competitivas |

### 3.2 Comparar con Estado Actual

Para cada agente:
- Modelo actual (extraído en paso 0.3) o "ninguno"
- Modelo recomendado (según clasificación)
- ¿Mismatch o falta modelo?

### 3.3 Estimar Impacto en Coste

```
Coste relativo por llamada:
  haiku  ≈ 1x
  sonnet ≈ 5x
  opus   ≈ 25x

Para Agent Teams: multiplicar por N teammates activos simultáneamente.
Ej: 4 teammates sonnet = 20x coste base

Ahorro potencial = suma(agentes donde actual > óptimo)
```

**Resultado: `$MODEL_FINDINGS[]`**

---

## Paso 4: Team Coordination Analysis (20 puntos) — NUEVO

> Este paso reemplaza y amplía el anterior "Parallelization Analysis".
> Evalúa tanto la paralelización como la coordinación entre agentes.

### 4.1 Construir Grafo de Dependencias

Del feature pipeline (si existe):
- Extraer cada paso
- Determinar dependencias (qué pasos dependen de outputs de cuáles)
- Identificar pasos independientes que podrían ser paralelos

### 4.2 File Ownership Matrix

**CRÍTICO para Agent Teams** — Dos agentes editando el mismo archivo = conflictos.

Para cada agente/rol:
1. Extraer los archivos/directorios que modifica (de su definición o por convención del stack)
2. Construir matriz de ownership:

```
                        | Frontend  | Backend   | Tests    | DB       |
  src/components/       |    ★      |           |          |          |
  src/api/              |           |    ★      |          |          |
  src/hooks/            |    ★      |    ◆      |          |          |  ← CONFLICTO
  __tests__/            |           |           |    ★     |          |
  supabase/migrations/  |           |           |          |    ★     |

★ = Owner principal    ◆ = Puede modificar (conflicto potencial)
```

Clasificar conflictos:

| Tipo | Severidad | Ejemplo |
|------|-----------|---------|
| **Overlap total** | CRITICAL | Dos agentes "ownan" mismo directorio |
| **Overlap parcial** | HIGH | Ambos pueden editar `src/hooks/` |
| **Overlap de tipos** | MEDIUM | Frontend y Backend editan archivos `.ts` en mismo dir |
| **Sin overlap** | OK | Ownership limpio por directorio |

### 4.3 Evaluar Estrategia de Paralelización

**Si usa Agent Teams nativo:**
- ¿Los teammates tienen scope claro y no superpuesto?
- ¿El número de teammates es adecuado? (3-5 recomendado)
- ¿Ratio tareas/teammate? (5-6 es óptimo)
- ¿Se usa plan approval para tareas riesgosas?

**Si usa Legacy agents:**
- Identificar oportunidades de paralelización:

| Paso A | Paso B | ¿Paralelo? |
|--------|--------|------------|
| Generación UI | Traducciones/i18n | SÍ |
| Generación UI | Configuración de rutas/navegación | SÍ |
| Tests unitarios | Tests de widget/componente | SÍ |
| Linting | Type checking | SÍ |
| Frontend components | Backend API endpoints | SÍ |
| **Stitch design generation** | **DB migrations** | **SÍ** (Stitch tarda minutos, aprovechar la espera) |
| **Stitch design generation** | **Backend API endpoints** | **SÍ** (diseño y API en paralelo) |
| **Stitch HTML → code** | Backend code | SÍ (si el HTML ya está listo) |
| Repository | BLoC/Store (depende del repo) | NO |
| Entity/Model | Repository (depende de entity) | NO |
| DB migrations | Backend code (depende de migrations) | NO |
| **Stitch HTML → code** | DB migrations (depende de schema) | NO (necesita schema definido para datos reales) |

### 4.4 Evaluar Comunicación Inter-agente

| Patrón | Cuándo usar | ¿El proyecto lo necesita? |
|--------|------------|--------------------------|
| **Subagents** (report-only) | Tareas focalizadas sin discusión | Para linting, análisis estático |
| **Agent Teams message** (punto a punto) | Un agente necesita output de otro | Para Frontend que depende de API |
| **Agent Teams broadcast** | Todos deben saber algo | Para decisiones de arquitectura |
| **Debate/Challenge** | Debugging, hipótesis competitivas | Para bugs complejos |
| **Async handoff (Stitch)** | Tarea larga bloqueante (diseño UI) | Para Stitch: lanzar generación y continuar con otra tarea mientras espera |

Evaluar si el proyecto está usando el patrón correcto para cada tipo de interacción.

### 4.6 Evaluar Flujo Stitch (Design-to-Code)

Si `$HAS_STITCH_MCP` o `$HAS_STITCH_DESIGNS`:

**Detectar el flujo actual:**
- ¿Se usa Stitch via MCP (`mcp__stitch__generate_screen_from_text`)?
- ¿Los HTMLs se guardan en `doc/design/{feature}/`?
- ¿Se registran prompts en `doc/design/{feature}/{feature}_stitch_prompts.md`?
- ¿Existe `/design-to-code` como comando o se hace manualmente?

**Evaluar eficiencia del flujo Stitch:**

| Patrón | Estado | Rating |
|--------|--------|--------|
| Stitch genera mientras otro agente trabaja en DB/API | Paralelo | **EXCELLENT** |
| Stitch genera y todos esperan | Secuencial bloqueante | **POOR** |
| HTMLs generados pero no convertidos a código | Pendiente | **NEEDS_ACTION** |
| No usa Stitch en features con UI | Oportunidad perdida | **SUGGEST** |

**Oportunidades de Agent Teams con Stitch:**

El flujo ideal con Agent Teams es:

```
Lead asigna tareas:
  T1: [DBInfra]           → Crear migrations/schemas      (paralelo)
  T2: [DesignSpecialist]  → Generar pantallas en Stitch    (paralelo, tarda minutos)
  T3: [PythonBackend]     → Crear API endpoints            (paralelo)
      ⏳ Stitch generando...
  T4: [FlutterSpecialist] → Convertir HTML → Flutter code  (depende de T2)
  T5: [ReactSpecialist]   → Convertir HTML → React code    (depende de T2)
  T6: [QA]                → Tests                          (depende de T3, T4, T5)
```

Stitch es **el cuello de botella ideal para paralelizar**: mientras genera (minutos), otros teammates trabajan en DB, API, tests, etc.

**Checklist Stitch:**
- [ ] ¿Config de Stitch en `.claude/settings.local.json`?
- [ ] ¿`doc/design/` existe con HTMLs?
- [ ] ¿Prompts registrados para trazabilidad?
- [ ] ¿Flujo de Stitch se ejecuta en paralelo con otras tareas?
- [ ] ¿Existe teammate o subagent dedicado a design?

### 4.5 Evaluar Failure Documentation

- ¿Existe `doc/failures/` o documentación de intentos fallidos?
- ¿Los agentes tienen instrucciones de documentar errores?
- ¿Hay README de progreso mantenidos por agentes?

| Estado | Rating |
|--------|--------|
| doc/failures/ + instrucciones en agentes | **GOOD** |
| Solo instrucciones en agentes | **MODERATE** |
| Nada | **POOR** — Proponer failure docs |

**Resultado: `$COORDINATION_FINDINGS[]`**

---

## Paso 5: Deprecation Hygiene Analysis (15 puntos)

### 5.1 Buscar Deprecaciones Explícitas

En `.claude/agents/*.md`: buscar "DEPRECATED", "deprecated", "obsolete", "obsoleto".

Para cada agente deprecated:
- ¿Sigue listado en ORCHESTRATOR.md sin marca?
- ¿Sigue referenciado en comandos?
- ¿Tiene un reemplazo claro indicado?

### 5.2 Buscar Staleness Implícito

Para cada agente:
- ¿Referencia archivos/directorios que ya no existen?
- ¿Referencia patrones no usados en el codebase?
- ¿Cuándo se actualizó por última vez? (git log)

### 5.3 Verificar Consistencia de `_AGENT_COMMON.md`

Si existe `_AGENT_COMMON.md`:
- ¿Todos los agentes lo referencian?
- ¿Hay reglas en common que conflicten con agentes individuales?
- ¿El archivo common coincide con estado actual del proyecto?

### 5.4 Auditar Teams Nativos (si aplica)

Si `$HAS_NATIVE_TEAMS`:
- **Teams huérfanos**: config.json sin actividad reciente y sin cleanup
- **Tareas stuck**: in_progress > 24h sin agente activo
- **Tareas con dependencias rotas**: dependen de tarea que no existe
- **Sesiones tmux huérfanas**: `tmux ls` para detectar sesiones zombie

### 5.5 Detectar Gaps (Agentes Faltantes)

Basado en la estructura del proyecto:

| El Proyecto Tiene | Agente Esperado | ¿Existe? |
|-------------------|----------------|----------|
| Base de datos (Supabase/Neon/Prisma/etc) | DB Specialist | ? |
| Componentes UI (Flutter widgets / React components) | UI/Design Agent | ? |
| Directorio de tests | QA/Test Agent | ? |
| Capa API (REST/GraphQL) | API/Integration Agent | ? |
| Pagos (Stripe) | Payments/Billing Agent | ? |
| Stitch MCP + `doc/design/` HTMLs | Design Specialist (Stitch) | ? |
| Config CI/CD | DevOps Agent | ? |
| Multiple stacks (Flutter + Python + React) | Cross-stack Coordinator | ? |
| n8n workflows | Automation Agent | ? |

Solo reportar como sugerencia, NO como error.

**Resultado: `$STALE_FINDINGS[]`**

---

## Paso 6: Agent Teams Readiness Assessment (15 puntos) — NUEVO

> Evalúa cuán preparado está el proyecto para usar Agent Teams nativo.

### 6.1 Prerequisitos Técnicos

| Requisito | Estado | Acción |
|-----------|--------|--------|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` en settings.json | ✅/❌ | Activar |
| tmux instalado (para split panes) | ✅/❌ | `brew install tmux` |
| Proyecto git inicializado | ✅/❌ | Requerido para worktrees |
| CLAUDE.md con instrucciones de proyecto | ✅/❌ | Crear con contexto del stack |

### 6.2 Evaluar Complejidad para Agent Teams

```
Puntuación de complejidad:
  Líneas de código > 20k          +3
  Multi-stack (Flutter + Python)   +3
  Componentes UI > 20              +2
  Capa de DB compleja              +2
  CI/CD pipeline                   +1
  Tests > 50 archivos              +1
  n8n/automations                  +1
  Stitch design-to-code flow       +2 (agrega bottleneck paralelizable + rol extra)
                                   ────
  TOTAL:                           /15

  0-3:  Simple   → Subagents suficientes, Agent Teams innecesario
  4-7:  Moderado → Agent Teams opcional, beneficioso para features grandes
  8-11: Complejo → Agent Teams recomendado para productividad
  12+:  Masivo   → Agent Teams esencial, considerar equipos especializados
```

### 6.3 Proponer Estructura de Team

Basado en `$STACKS[]` y complejidad, proponer roles:

**Para Flutter + Python + React + Supabase/Neon + Stripe + Stitch (stack tipo IAutomat):**

| Rol | Modelo | Responsabilidad | File Ownership |
|-----|--------|----------------|----------------|
| **Lead** (coordinador) | sonnet | Planifica, delega, sintetiza. NO implementa. | Ninguno |
| **Design Specialist** | sonnet | Genera pantallas en Stitch (MCP), guarda HTMLs, registra prompts. Tarea larga → lanzar primero y en paralelo. | `doc/design/` |
| **Flutter Specialist** | sonnet | Widgets, BLoC, navegación, UI. Convierte HTML de Stitch a Flutter. | `lib/` |
| **React Specialist** | sonnet | Components, hooks, state management. Convierte HTML de Stitch a React. | `src/`, `pages/` |
| **Python Backend** | sonnet | APIs, lógica de negocio, scripts, Stripe webhooks | `backend/`, `scripts/`, `*.py` |
| **DB/Infra** | sonnet | Migrations, RLS, Edge Functions (Supabase/Neon) | `supabase/`, `firebase/`, `neon/`, `migrations/` |
| **QA Reviewer** | haiku | Tests, linting, análisis estático | `tests/`, `__tests__/` |

> **Nota sobre Design Specialist**: Este rol lanza generación en Stitch como primera tarea (tarda minutos). Mientras Stitch genera, DBInfra y PythonBackend trabajan en paralelo. Cuando el HTML está listo, FlutterSpecialist/ReactSpecialist lo convierten a código.

**Para Flutter solo:**

| Rol | Modelo | Responsabilidad | File Ownership |
|-----|--------|----------------|----------------|
| **Lead** | sonnet | Coordinación | Ninguno |
| **Feature Builder** | sonnet | Modelos, repos, BLoCs | `lib/data/`, `lib/domain/` |
| **UI Builder** | sonnet | Widgets, pages, layouts | `lib/presentation/` |
| **QA** | haiku | Tests + dart analyze | `test/` |

**Para React + Python:**

| Rol | Modelo | Responsabilidad | File Ownership |
|-----|--------|----------------|----------------|
| **Lead** | sonnet | Coordinación | Ninguno |
| **Frontend** | sonnet | React components, hooks, pages | `src/` |
| **Backend** | sonnet | FastAPI/Django endpoints, models | `backend/`, `api/` |
| **QA** | haiku | Tests + linting | `tests/`, `__tests__/` |

### 6.4 Evaluar si Migrar de Legacy a Native

| Factor | Peso | Beneficio de migrar |
|--------|------|-------------------|
| Agentes necesitan comunicarse entre sí | Alto | Teams tiene messaging directo |
| Pipeline tiene oportunidades de paralelización | Alto | Teams ejecuta en paralelo real |
| Proyecto > 50k LOC | Medio | Context isolation mejora rendimiento |
| Equipos > 3 agentes | Medio | Task board nativo mejor que manual |
| Debugging complejo frecuente | Medio | Debate/challenge entre teammates |
| Solo 1-2 agentes simples | Bajo | Subagents suficientes |

**Resultado: `$READINESS_FINDINGS[]`**

---

## Paso 7: Calcular Health Score

```
Componentes (ponderados):
  Documentation Sync:        25 puntos
  Validation Strategy:       15 puntos
  Model Optimization:        10 puntos
  Team Coordination:         20 puntos   ← NUEVO (reemplaza Parallelization)
  Deprecation Hygiene:       15 puntos
  Agent Teams Readiness:     15 puntos   ← NUEVO
                             ─────────
  TOTAL:                    100 puntos

Penalización por hallazgo:
  LOW:      -2 puntos (mínimo 0 por categoría)
  MEDIUM:   -5 puntos
  HIGH:     -10 puntos
  CRITICAL: -15 puntos

Si un check no aplica (ej: no hay feature pipeline):
  → No penalizar, dar puntos completos de esa categoría
```

| Score | Rating | Etiqueta |
|-------|--------|----------|
| 90-100 | Excelente | Sistema de agentes bien mantenido |
| 70-89 | Bueno | Mejoras menores recomendadas |
| 50-69 | Regular | Varios issues necesitan atención |
| 30-49 | Pobre | Overhaul significativo recomendado |
| 0-29 | Crítico | Reestructuración mayor necesaria |

---

## Paso 8: Generar Output

### Modo: `audit` (default)

Imprimir directamente en la conversación:

```
════════════════════════════════════════════════════════════
  AGENT SYSTEM OPTIMIZATION REPORT v2
  Project: [nombre del proyecto de CLAUDE.md o nombre del directorio]
  Stack: [stacks detectados]
  Infra: [infra detectada]
  System: [LEGACY_ONLY | NATIVE_ONLY | HYBRID | NO_AGENTS]
  Agents: [N] detected ([N] active, [N] deprecated)
  Teams: [N native teams] ([N active tasks], [N stuck])
  Date: [fecha]
════════════════════════════════════════════════════════════

HEALTH SCORE: [XX]/100 — [Rating]

────────────────────────────────────────────────────────────
1. DOCUMENTATION SYNC                           [XX/25]
────────────────────────────────────────────────────────────

[Si hay issues:]
| # | Sev. | Archivo | Issue | Recomendación |
|---|------|---------|-------|---------------|
| 1 | CRIT | agents/XxxAgent.md | Referencia Firebase, proyecto usa Supabase | Actualizar refs de backend |
| 2 | HIGH | ORCHESTRATOR.md | Lista DesignSystemAgent sin marca deprecated | Añadir DEPRECATED o eliminar |
| 3 | MED  | commands/feature.md | Referencia path lib/data/ que está prohibido | Actualizar paths |

[Si no hay issues:]
✅ Toda la documentación de agentes es consistente con el estado actual del proyecto.

────────────────────────────────────────────────────────────
2. VALIDATION STRATEGY                          [XX/15]
────────────────────────────────────────────────────────────

Pipeline: [nombre del comando]
Pasos: [N] total, [N] checkpoints
Ratio: [X]% — [Rating]

[Si Agent Teams habilitado:]
Hooks configurados:
  TeammateIdle:   [✅ Sí / ❌ No]
  TaskCompleted:  [✅ Sí / ❌ No]

[Si hay issues:]
| # | Entre pasos | Issue | Recomendación |
|---|-------------|-------|---------------|
| 1 | Repository → UI | Sin checkpoint de validación | Añadir `[analyze cmd]` checkpoint |

[Si no hay issues:]
✅ Los checkpoints de validación están bien distribuidos.

────────────────────────────────────────────────────────────
3. MODEL OPTIMIZATION                           [XX/10]
────────────────────────────────────────────────────────────

| Agente/Rol | Modelo Actual | Recomendado | Nota |
|------------|--------------|-------------|------|
| Lead | sonnet | sonnet | ✅ |
| Flutter Specialist | sonnet | sonnet | ✅ |
| QAValidator | (ninguno) | haiku | ⚠️ Añadir recomendación |

[Si Agent Teams:]
Coste estimado por sesión de team (4 teammates × sonnet): ~20x coste base
Ahorro si QA usa haiku: -15% del total

[Si no hay issues:]
✅ Todos los agentes tienen recomendaciones de modelo apropiadas.

────────────────────────────────────────────────────────────
4. TEAM COORDINATION                            [XX/20]
────────────────────────────────────────────────────────────

[File Ownership Matrix:]
                        | Flutter | React  | Python | DB     | QA     |
  lib/                  |    ★    |        |        |        |        |
  src/                  |         |   ★    |        |        |        |
  backend/              |         |        |   ★    |        |        |
  supabase/ + neon/     |         |        |        |   ★    |        |
  test/ + __tests__/    |         |        |        |        |   ★    |

Conflictos detectados: [N]
[Si hay conflictos, listarlos con severidad]

[Paralelización:]
Pipeline actual:
  DB Setup ──→ Models ──→ Repository ──→ BLoC ──→ UI
                                         ↓
                                       Tests

Oportunidades de paralelización:
| Grupo paralelo | Ahorro estimado |
|---------------|-----------------|
| UI + i18n + Routing | ~27% |
| Unit tests + Widget tests | ~15% |

[Comunicación inter-agente:]
| Patrón actual | Recomendado | Razón |
|--------------|-------------|-------|
| Sin comunicación | Agent Teams message | Frontend depende de API contracts de Backend |

[Failure documentation:]
Estado: [GOOD / MODERATE / POOR]

────────────────────────────────────────────────────────────
5. DEPRECATION HYGIENE                          [XX/15]
────────────────────────────────────────────────────────────

[Si hay issues:]
| # | Agente/Archivo | Estado | Issue |
|---|---------------|--------|-------|
| 1 | DesignSystemAgent.md | DEPRECATED | Sigue en ORCHESTRATOR sin marca |
| 2 | OldDataAgent.md | STALE | Referencia feature eliminada |

[Si Agent Teams:]
Teams huérfanos: [N]
Tareas stuck: [N]
Sesiones tmux zombie: [N]

[Si no hay issues:]
✅ No se encontraron agentes obsoletos o deprecados sin marcar.

────────────────────────────────────────────────────────────
6. AGENT TEAMS READINESS                        [XX/15]
────────────────────────────────────────────────────────────

Prerequisitos:
  Agent Teams habilitado:   [✅ / ❌]
  tmux instalado:           [✅ / ❌]
  Git inicializado:         [✅ / ❌]
  CLAUDE.md configurado:    [✅ / ❌]

Complejidad del proyecto: [X]/13 — [Simple/Moderado/Complejo/Masivo]
Recomendación: [Subagents suficientes / Agent Teams opcional / Agent Teams recomendado]

[Si recomienda Agent Teams:]
Estructura propuesta:
| Rol | Modelo | File Ownership |
|-----|--------|---------------|
| Lead | sonnet | (coordinación) |
| [roles según stack] |

[Si ya tiene Agent Teams:]
Estado actual del equipo: [métricas]

════════════════════════════════════════════════════════════
  RESUMEN
════════════════════════════════════════════════════════════

Quick Wins (< 5 min cada uno):
  1. [acción específica con archivo]
  2. [acción específica con archivo]

Mejoras a Medio Plazo:
  1. [acción con estimación de esfuerzo]
  2. [acción con estimación de esfuerzo]

Agent Teams Actions:
  1. [acción relacionada con teams si aplica]

Para aplicar fixes:    /optimize-agents apply
Para generar report:   /optimize-agents report
Para init Agent Teams: /optimize-agents team-init
Para migrar a Teams:   /optimize-agents migrate
════════════════════════════════════════════════════════════
```

### Modo: `report`

Mismo contenido que audit, pero:
1. Crear `doc/plans/agent_optimization_report.md` con el report completo
2. Incluir diffs de modificación propuestos para cada recomendación
3. Añadir "Checklist de Implementación" al final:

```markdown
## Checklist de Implementación

### Quick Wins
- [ ] [Acción 1] — Archivo: [path] — Cambio: [descripción]
- [ ] [Acción 2] — Archivo: [path] — Cambio: [descripción]

### Medio Plazo
- [ ] [Acción 1] — Archivos: [paths] — Esfuerzo: [estimación]
- [ ] [Acción 2] — Archivos: [paths] — Esfuerzo: [estimación]

### Agent Teams
- [ ] [Acción 1] — Config: [detalle]
- [ ] [Acción 2] — Config: [detalle]

---
*Generado por /optimize-agents el [fecha]*
```

### Modo: `apply`

1. Ejecutar audit completo
2. Presentar hallazgos agrupados por tipo de acción
3. Para cada fix, mostrar el cambio propuesto y PEDIR confirmación:

```
Cambio propuesto 1 de N:

Archivo: .claude/agents/XxxAgent.md
Acción: Actualizar referencia de backend
Cambio:
  ANTES: **Backend:** Firebase (Firestore + Auth)
  DESPUÉS: **Backend:** Supabase (PostgreSQL + Auth)

¿Aplicar? (opciones: Sí / No / Aplicar todos / Saltar resto)
```

4. Aplicar cambios confirmados
5. Ejecutar validación post-cambio:

**Flutter:** `dart analyze`
**Node/React:** `npm run lint` o `npx eslint .` o `npx tsc --noEmit`
**Python:** `python -m mypy .` o `python -m flake8 .`
**Rust:** `cargo check`
**Go:** `go vet ./...`

### Modo: `team-init`

Genera la configuración completa de Agent Teams para el proyecto actual.

**Pasos:**

1. Ejecutar detección de stack (Paso 0.1)
2. Evaluar complejidad (Paso 6.2)
3. Proponer estructura de team (Paso 6.3) y pedir confirmación
4. Generar los siguientes archivos:

**4a. Activar Agent Teams en settings.json del proyecto:**

Si no existe `.claude/settings.json`, crearlo. Si existe, añadir:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "auto"
}
```

**4b. Generar `team-config.json` en `.claude/`:**

```json
{
  "version": "1.0",
  "project": "[nombre del proyecto]",
  "stacks": ["flutter", "python", "react", "stripe", "neon"],
  "generatedDate": "[fecha]",
  "team": {
    "recommendedSize": 5,
    "maxSize": 7,
    "roles": [
      {
        "name": "Lead",
        "model": "sonnet",
        "type": "coordinator",
        "responsibilities": [
          "Planificar y descomponer tareas",
          "Asignar trabajo a teammates",
          "Sintetizar resultados",
          "Resolver conflictos entre teammates",
          "NO implementar código directamente"
        ],
        "fileOwnership": [],
        "spawnPromptTemplate": "You are the team lead for {project}. Your role is coordination only. Break down the task into subtasks, assign to specialists, and synthesize results. Do NOT write code yourself — delegate to teammates. Stack: {stacks}. Architecture: {architecture}."
      },
      {
        "name": "DesignSpecialist",
        "model": "sonnet",
        "type": "implementer",
        "responsibilities": [
          "Generate UI screens via Google Stitch MCP (mcp__stitch__generate_screen_from_text)",
          "Build detailed design prompts from PRD/plan requirements",
          "Save HTML outputs to doc/design/{feature}/",
          "Register prompts in doc/design/{feature}/{feature}_stitch_prompts.md",
          "ALWAYS use Light Mode in Stitch prompts",
          "Use GEMINI_3_PRO for complex screens, GEMINI_3_FLASH for simple ones",
          "Generate ONE screen at a time (API takes minutes per screen)"
        ],
        "fileOwnership": ["doc/design/"],
        "spawnPromptTemplate": "You are the Design specialist for {project}. You generate UI screens using Google Stitch MCP. For each screen: 1) Build a detailed prompt with Design System tokens, components, states, layout. 2) Call mcp__stitch__generate_screen_from_text. 3) Save HTML to doc/design/{feature}/. 4) Register prompt in {feature}_stitch_prompts.md. ALWAYS use Light Mode. Stitch config: projectId={stitch_projectId}, deviceType={stitch_deviceType}, modelId={stitch_modelId}. IMPORTANT: Generation takes minutes per screen — the Lead should assign you FIRST so other teammates work in parallel while you wait.",
        "mcpTools": [
          "mcp__stitch__generate_screen_from_text",
          "mcp__stitch__get_screen",
          "mcp__stitch__list_screens",
          "mcp__stitch__get_project"
        ],
        "notes": "This role is the primary bottleneck in UI features. Assign FIRST so DB/API work happens in parallel during Stitch generation wait time."
      },
      {
        "name": "FlutterSpecialist",
        "model": "sonnet",
        "type": "implementer",
        "responsibilities": [
          "Widgets, pages, layouts",
          "Convert Stitch HTML designs to Flutter widgets",
          "BLoC/state management",
          "Navegación con GoRouter",
          "Clean Architecture en lib/"
        ],
        "fileOwnership": ["lib/"],
        "spawnPromptTemplate": "You are the Flutter specialist for {project}. You own all code under lib/. Architecture: Clean Architecture with BLoC, feature-first. Use Material 3. Dependencies: {flutter_deps}. When Stitch HTML designs are available in doc/design/{feature}/, convert them to Flutter widgets matching the design exactly. Do NOT modify files outside lib/."
      },
      {
        "name": "ReactSpecialist",
        "model": "sonnet",
        "type": "implementer",
        "responsibilities": [
          "React 19.x components, hooks, pages",
          "State management (zustand/redux/jotai)",
          "Next.js 15.x pages/app router si aplica",
          "Stripe Elements/Checkout UI integration",
          "Tailwind/CSS-in-JS"
        ],
        "fileOwnership": ["src/", "pages/", "app/", "components/"],
        "spawnPromptTemplate": "You are the React/frontend specialist for {project}. You own all code under src/ and pages/. Framework: React 19.x + {react_framework}. State: {state_management}. Payments UI: Stripe Elements if needed. When Stitch HTML designs are available in doc/design/{feature}/, convert them to React components matching the design exactly. Do NOT modify backend or database files."
      },
      {
        "name": "PythonBackend",
        "model": "sonnet",
        "type": "implementer",
        "responsibilities": [
          "API endpoints",
          "Business logic",
          "Data processing scripts",
          "Stripe integration (webhooks, checkout sessions, subscriptions)",
          "n8n workflow integrations"
        ],
        "fileOwnership": ["backend/", "api/", "scripts/", "*.py"],
        "spawnPromptTemplate": "You are the Python backend specialist for {project}. You own backend/, api/, and scripts/. Framework: {python_framework}. DB: {database}. Payments: Stripe (handle webhooks, checkout, subscriptions). Do NOT modify frontend code."
      },
      {
        "name": "DBInfra",
        "model": "sonnet",
        "type": "implementer",
        "responsibilities": [
          "Database migrations (Supabase/Neon)",
          "RLS policies",
          "Edge Functions",
          "Neon.tech serverless Postgres config",
          "Firebase/Supabase config"
        ],
        "fileOwnership": ["supabase/", "firebase/", "neon/", "migrations/"],
        "spawnPromptTemplate": "You are the DB/Infrastructure specialist for {project}. You own supabase/, neon/, and migration files. Databases: {database_provider} (may include Supabase and/or Neon.tech serverless Postgres). Create migrations, configure RLS, and Edge Functions. Do NOT modify application code."
      },
      {
        "name": "QAReviewer",
        "model": "haiku",
        "type": "reviewer",
        "responsibilities": [
          "Ejecutar y escribir tests",
          "Análisis estático (dart analyze, eslint, mypy)",
          "Code review de outputs de otros teammates",
          "Verificar cobertura > 85%"
        ],
        "fileOwnership": ["test/", "tests/", "__tests__/"],
        "spawnPromptTemplate": "You are the QA reviewer for {project}. Run tests, check linting, verify code quality. Commands: {test_commands}. Reject changes that break tests or reduce coverage. Challenge other teammates' implementations."
      }
    ],
    "taskGuidelines": {
      "tasksPerTeammate": "5-6 optimal",
      "taskSizing": "Each task should produce a clear deliverable (a function, a test file, a component)",
      "dependencies": "Define explicitly — blocked tasks auto-unblock when dependency completes",
      "planApproval": "Require for tasks touching shared code or DB schemas"
    },
    "communicationRules": {
      "message": "Use for direct dependency (Frontend needs API contract from Backend)",
      "broadcast": "Use sparingly — only for architecture decisions affecting all",
      "debate": "Use for debugging: spawn competing hypothesis investigators"
    },
    "hooks": {
      "TeammateIdle": {
        "description": "Run linting when a teammate finishes",
        "suggestedCommand": "Run the appropriate linter for the teammate's file ownership area"
      },
      "TaskCompleted": {
        "description": "Verify tests pass when a task completes",
        "suggestedCommand": "Run tests relevant to the completed task's file ownership area"
      }
    }
  }
}
```

**4c. Actualizar CLAUDE.md del proyecto:**

Añadir sección de Agent Teams al CLAUDE.md existente (o crear si no existe):

```markdown
## Agent Teams Configuration

Este proyecto usa Agent Teams para coordinación multi-agente.

### Roles del Equipo

| Rol | Modelo | Scope |
|-----|--------|-------|
| Lead | sonnet | Coordinación (no implementa) |
| [roles según stack detectado] |

### Reglas de Coordinación

1. **File Ownership**: Cada teammate solo modifica archivos en su scope. Ver `.claude/team-config.json`.
2. **Plan Approval**: Requerido para cambios en DB schemas y shared code.
3. **Communication**: Usar `message` para dependencias directas. `broadcast` solo para decisiones de arquitectura.
4. **Quality Gates**: Todos los cambios pasan por QA Reviewer antes de merge.

### Spawn Prompts

Para iniciar un team manualmente, usar este prompt como base:

"Create an agent team for [tarea]. Roles: [lista de roles de team-config.json]. Each teammate should only modify files in their ownership area. Require plan approval for DB changes."
```

**4d. Generar templates de prompts en `.claude/team-prompts/`:**

Crear un archivo por rol con el spawn prompt expandido:

`.claude/team-prompts/lead.md`
`.claude/team-prompts/design-specialist.md`  ← Stitch MCP (generar primero, es cuello de botella)
`.claude/team-prompts/flutter-specialist.md`
`.claude/team-prompts/react-specialist.md`
`.claude/team-prompts/python-backend.md`
`.claude/team-prompts/db-infra.md`
`.claude/team-prompts/qa-reviewer.md`

Cada archivo contiene el spawn prompt completo con variables resueltas para el proyecto actual.

**4e. Confirmar al usuario:**

```
✅ Agent Teams configurado para [proyecto]

Archivos generados:
  .claude/settings.json          — Agent Teams habilitado
  .claude/team-config.json       — Configuración del equipo
  .claude/team-prompts/          — Spawn prompts por rol
  CLAUDE.md                      — Actualizado con reglas de coordinación

Equipo propuesto ([N] roles):
  [tabla de roles]

Para usar:
  1. Describe la tarea y pide "create an agent team"
  2. Claude usará la configuración de team-config.json
  3. Cada teammate recibirá su spawn prompt especializado

Para auditar el sistema: /optimize-agents audit
```

### Modo: `migrate`

Propone un plan de migración de `.claude/agents/` a Agent Teams nativo.

1. Ejecutar inventario de agentes legacy (Paso 0.3)
2. Mapear cada agente legacy a un rol de Agent Teams
3. Generar plan de migración:

```
════════════════════════════════════════════════════════════
  MIGRATION PLAN: Legacy Agents → Agent Teams
════════════════════════════════════════════════════════════

Agentes legacy detectados: [N]

Mapeo propuesto:
| Agente Legacy | → Rol Agent Teams | Modelo | Cambios |
|--------------|-------------------|--------|---------|
| ArchitectAgent.md | Lead | sonnet | Expandir a coordinador completo |
| UIDesignerAgent.md | FlutterSpecialist | sonnet | Añadir file ownership |
| BackendAgent.md | PythonBackend | sonnet | Separar DB a rol propio |
| QAAgent.md | QAReviewer | haiku | Añadir hooks de quality gate |

Elementos a migrar:
- [ ] Crear .claude/team-config.json con roles mapeados
- [ ] Crear .claude/team-prompts/ con spawn prompts
- [ ] Actualizar CLAUDE.md con reglas de coordinación
- [ ] Activar CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
- [ ] Configurar hooks TeammateIdle y TaskCompleted

Elementos a mantener (compatibilidad):
- .claude/agents/ → Mantener como referencia (no borrar)
- .claude/ORCHESTRATOR.md → Mantener como documentación
- .claude/commands/ → Siguen funcionando con ambos sistemas

¿Ejecutar migración? (opciones: Sí / Solo generar config / Cancelar)
════════════════════════════════════════════════════════════
```

---

## Notas Importantes

- Este comando es **read-only por defecto** (modos audit y report)
- Solo los modos `apply`, `team-init` y `migrate` modifican archivos, siempre con confirmación
- Funciona en **cualquier proyecto** — detecta automáticamente si usa legacy agents, native teams, o ninguno
- Los checks se **adaptan al stack** detectado (Flutter, React, Python, etc.)
- Si un check no aplica (ej: no hay feature pipeline), se salta y se indica
- El score **no penaliza** por checks no aplicables
- Archivos de agente sin cambios necesarios se marcan como ✅
- **Agent Teams es experimental** — las funcionalidades marcadas con "Agent Teams" requieren `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` activado
- El modo `team-init` genera configuración que funciona tanto con teams nativos como con subagents normales
