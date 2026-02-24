# JPS Dev Engine v3.1.0

Sistema de programacion agentica basado en **Agent Skills** para Claude Code.

Repositorio canonico que contiene Skills auto-descubribles, hooks de calidad, patrones de arquitectura, templates de agentes, configuracion de Agent Teams y patrones de infraestructura para desarrollo profesional con Claude Code.

---

## Quick Start

```bash
# 1. Clonar
git clone <repo-url> ~/jps_dev_engine
cd ~/jps_dev_engine

# 2. Instalar commands globales
./install.sh

# 3. Verificar commands
ls -la ~/.claude/commands/
# Deberias ver: prd.md, plan.md, implement.md, adapt-ui.md, optimize-agents.md

# 4. Verificar skills
ls -la ~/.claude/skills/
# Deberias ver: prd, plan, implement, adapt-ui, optimize-agents, quality-gate, explore
```

Los commands y skills quedan disponibles globalmente en Claude Code. Las Skills se auto-descubren cuando son relevantes.

---

## Flujo Completo de Desarrollo

Este es el flujo end-to-end que el engine proporciona. Cada paso tiene su propio comando y puede ejecutarse de forma independiente, pero el flujo completo es donde el sistema brilla:

```
/prd ──────────> PRD + Work Item (Plane/Trello)
                   │
                   │  El PRD documenta requisitos, funcionalidades,
                   │  interacciones UI y criterios de aceptacion.
                   │
                   ▼
/plan ─────────> Plan tecnico + Diseños Stitch (HTML)
                   │
                   │  El plan desglosa el trabajo en fases ordenadas,
                   │  analiza componentes UI, mapea agentes y genera
                   │  diseños de pantalla via Google Stitch MCP.
                   │  Se guarda en doc/plans/{nombre}_plan.md
                   │
                   ▼
/implement ────> Autopilot: rama + codigo + QA + PR
                   │
                   │  Lee el plan, crea rama feature/, ejecuta todas
                   │  las fases (incluyendo design-to-code si hay
                   │  diseños Stitch), valida con tests y lint,
                   │  y crea PR lista para review.
                   │
                   ▼
               PR lista para review en GitHub
```

### Comandos de soporte

```
/adapt-ui ──────────> Escanea widgets del proyecto, genera mapeo UI
/optimize-agents ───> Audita y optimiza sistema agentico (score /100)
/quality-gate ──────> Quality gates adaptativos con evidence auditable
```

---

## Commands en Detalle

> **v3.0:** Los commands han sido migrados a Agent Skills. Los archivos en `commands/` se mantienen como referencia. Las Skills en `.claude/skills/` son la version activa con auto-discovery, context isolation, y hooks.

### `/prd` — Generar PRD

**Archivo**: `commands/prd.md`

Genera un Product Requirements Document estructurado y opcionalmente crea un Work Item en Plane o Trello.

```
/prd "titulo" "descripcion de requerimientos"
```

**Que hace:**
1. Detecta tipo de PRD (feature nueva o refactor tecnico)
2. Recopila informacion: funcionalidades, interacciones UI, criterios
3. Genera PRD con template estructurado (funcionalidades, visualizacion de datos, acciones, formularios)
4. Crea Work Item en Plane/Trello con prioridad y asignacion

**Output:** PRD en markdown + Work Item creado (ej: `PROYECTO-42`)

**Siguiente paso:** `/plan PROYECTO-42`

---

### `/plan` — Generar Plan de Implementacion

**Archivo**: `commands/plan.md`

Genera un plan tecnico detallado con analisis de componentes UI y diseños via Google Stitch MCP.

```
/plan PROYECTO-42           # Desde work item de Plane
/plan "descripcion"         # Desde texto directo
/plan feature:nombre        # Analizar feature existente
```

**Que hace:**
1. **Detecta origen** y extrae requisitos del PRD
2. **Explora el proyecto**: stack, agentes disponibles, widgets existentes
3. **Analiza componentes UI** (obligatorio): tabla de componentes requeridos vs existentes
4. **Mapea agentes**: asigna AG-01 a AG-07 segun las fases
5. **Genera plan por fases**: DB → UI → Feature → Integracion → QA
6. **Genera diseños en Stitch MCP**: crea pantallas HTML automaticamente si la feature tiene UI
7. **Guarda plan** en `doc/plans/{nombre}_plan.md`
8. **Guarda HTMLs** en `doc/design/{feature}/`

**Output:** Plan en `doc/plans/` + HTMLs de diseño en `doc/design/`

**Siguiente paso:** `/implement {nombre_del_plan}`

---

### `/implement` — Autopilot de Implementacion

**Archivo**: `commands/implement.md`

Lee un plan y ejecuta todo el proceso de implementacion de forma autonoma: crea rama, implementa cada fase, genera diseños si faltan, convierte diseños a codigo, ejecuta tests, y crea PR.

```
/implement nombre_del_plan          # Busca doc/plans/{nombre}_plan.md
/implement doc/plans/mi_plan.md     # Path directo al plan
/implement                          # Lista planes disponibles y pregunta
```

**Flujo interno detallado:**

```
Paso 0: Cargar Plan
│  Lee doc/plans/{nombre}_plan.md
│  Parsea: titulo, fases, componentes UI, agentes, diseños
│  Verifica working tree limpio (git status)
│
Paso 1: Crear Rama
│  git checkout -b feature/{nombre-plan-kebab-case} main
│
Paso 2: Detectar Sistema de Agentes
│  Agent Teams nativo / Subagentes legacy / Claude directo
│  Mapea agentes a fases del plan
│
Paso 3: Generar Diseños Stitch (si faltan)
│  ¿El plan referencia doc/design/ pero no existen HTMLs?
│  → Genera automaticamente con mcp__stitch__generate_screen_from_text
│  → Guarda HTMLs en doc/design/{feature}/
│  → Registra prompts en {feature}_stitch_prompts.md
│
Paso 4: Design-to-Code (si hay diseños)
│  Lee HTMLs de doc/design/{feature}/
│  Convierte a codigo del stack:
│    Flutter → Widgets + Layouts (mobile/tablet/desktop)
│    React → Components + Server/Client Components
│    Apps Script → Templates HtmlService
│  Commit: "design: add Stitch designs for {feature}"
│
Paso 5: Ejecutar Fases del Plan
│  Para cada fase:
│    → Implementar todas las tareas de la fase
│    → Ejecutar validacion del stack (dart analyze, eslint, ruff, etc.)
│    → Commit parcial: "feat({feature}): {descripcion fase}"
│
Paso 6: Integracion
│  Registrar en DI / Routing / Config segun stack
│  Build final
│  Commit: "chore({feature}): integration and wiring"
│
Paso 7: QA y Validacion
│  Ejecutar tests (flutter test, jest, pytest, npm test)
│  Verificar coverage >= 85%
│  Si < 85%: generar tests adicionales (hasta 3 intentos)
│  Lint final sin errores
│  Commit: "test({feature}): add tests with 85%+ coverage"
│
Paso 8: Crear Pull Request
   git push -u origin feature/{nombre}
   gh pr create con:
     - Resumen del plan
     - Cambios por fase
     - Diseños Stitch (si aplica)
     - Test plan con checklist
```

**Output:** Rama con commits por fase + PR lista para review en GitHub

**Manejo de errores:**
- Error de compilacion → intenta fix automatico, si persiste reporta y para
- Error en Stitch → reintenta una vez, si falla continua sin ese diseño
- Coverage < 85% → genera tests adicionales (3 intentos), si no alcanza crea PR con nota
- Conflictos de merge → reporta al usuario, no resuelve automaticamente

---

### `/adapt-ui` — Mapeo de Componentes UI

**Archivo**: `commands/adapt-ui.md`

Escanea la estructura de widgets/componentes del proyecto y genera un archivo de mapeo UI.

```
/adapt-ui /path/al/proyecto              # Solo detectar
/adapt-ui /path/al/proyecto --normalize  # Detectar + mover widgets a core
```

**Que hace:**
1. Detecta framework (Flutter, React, Apps Script, etc.)
2. Localiza todas las carpetas de widgets/componentes
3. Detecta widgets dispersos (candidatos a centralizar)
4. Categoriza por tipo: Navigation, Data Display, Selection, Data Entry, Actions, Feedback
5. Detecta design tokens (colores, spacing, theme)
6. Genera `.claude/ui-adapter.md` con mapeo completo
7. Opcionalmente normaliza ubicaciones (mueve widgets a `core/`)

**Output:** `.claude/ui-adapter.md`

---

### `/optimize-agents` — Auditar Sistema Agentico

**Archivo**: `commands/optimize-agents.md`

Analiza, puntua y optimiza el sistema multi-agente del proyecto. Soporta tanto subagentes legacy como Agent Teams nativos.

```
/optimize-agents audit       # Analisis completo con score (default)
/optimize-agents report      # Reporte ejecutivo en doc/plans/
/optimize-agents apply       # Aplicar recomendaciones con confirmacion
/optimize-agents team-init   # Inicializar Agent Teams desde cero
/optimize-agents migrate     # Migrar legacy → Agent Teams
```

**Dimensiones de analisis (100 puntos):**
1. Documentation Sync (25pts) — CLAUDE.md vs codigo real
2. Validation Strategy (15pts) — hooks y gates de calidad
3. Model Optimization (10pts) — asignacion de modelos por complejidad
4. Team Coordination (20pts) — coordinacion entre agentes
5. Deprecation Hygiene (15pts) — limpieza de codigo obsoleto
6. Agent Teams Readiness (15pts) — preparacion para Agent Teams

**Incluye Engine Sync:** detecta version del engine y compara archivos copiados vs originales.

**Output:** Score /100 con recomendaciones priorizadas.

---

## Hooks System (v3.0)

Enforcement automatico — no hace falta recordar ejecutarlos manualmente:

| Hook | Evento | Comportamiento |
|------|--------|----------------|
| pre-commit-lint | PostToolUse (git commit) | BLOQUEANTE: falla el commit si lint tiene errores |
| on-session-end | Stop | Registra telemetria de sesion en .quality/logs/ |
| implement-checkpoint | Manual (llamado por /implement) | Guarda progreso de fase para resume |

Configuracion en `.claude/settings.json`. Los hooks se ejecutan automaticamente por Claude Code.

---

## Self-Healing Protocol (v3.1)

Cuando `/implement` encuentra errores durante la ejecución, el sistema intenta auto-recuperarse antes de pedir intervención humana:

| Nivel | Acción | Ejemplo |
|-------|--------|---------|
| **1: Auto-Fix** | Ejecuta auto-fix del stack | `dart fix --apply`, `eslint --fix` |
| **2: Diagnóstico** | Analiza error y aplica fix específico | Import faltante, tipo incorrecto |
| **3: Rollback** | Revierte fase y reintenta desde cero | `git stash` + fresh attempt |
| **4: Humano** | Genera error report y pausa | `.quality/evidence/{feature}/error_report.md` |

Todos los intentos se registran en `.quality/evidence/{feature}/healing.jsonl` para auditoría.

---

## Stacks Soportados

| Stack | Version | Arquitectura | Estado |
|-------|---------|-------------|--------|
| **Flutter** | 3.38+ | Clean Architecture, BLoC+Freezed, Responsive (3 layouts), DataSource pattern | Completo |
| **React** | 19.x | Next.js 15 App Router, Server Components, TanStack Query, Zustand, Tailwind CSS | Completo |
| **Python** | 3.12+ | FastAPI, SQLAlchemy 2 async, Pydantic v2, Repository pattern | Completo |
| **Google Apps Script** | V8 | clasp + TypeScript + esbuild, batch operations, PropertiesService | Completo |

Cada stack tiene su carpeta en `architecture/` con:
- `overview.md` — Vision general, principios, herramientas
- `folder-structure.md` — Estructura de carpetas detallada
- `patterns.md` — Patrones de codigo con ejemplos
- `testing-strategy.md` — Estrategia de testing, herramientas, mocks

---

## Servicios de Infraestructura

| Servicio | Carpeta | Contenido |
|----------|---------|-----------|
| **Supabase** | `infra/supabase/` | MCP tools, RLS policies, migrations, Realtime, DataSource pattern |
| **Neon** | `infra/neon/` | Connection pooling, branching, Drizzle ORM, serverless |
| **Stripe** | `infra/stripe/` | Webhooks, Checkout Sessions, Subscriptions, Customer Portal |
| **Firebase** | `infra/firebase/` | Firestore rules, Auth, Cloud Functions, Storage |
| **n8n** | `infra/n8n/` | Workflow patterns, triggers, webhooks, error handling |

---

## Sistema de Agentes

### Agentes Disponibles

| ID | Agente | Rol | Cuando se usa |
|----|--------|-----|---------------|
| — | Orchestrator | Coordinador de subagentes | Siempre (si hay orquestacion) |
| AG-01 | Feature Generator | Genera features completas | Fase de estructura y logica |
| AG-02 | UI/UX Designer | Diseño de interfaces | Fase UI + design-to-code |
| AG-03 | DB Specialist | Supabase, Neon, Firebase | Fase de preparacion DB |
| AG-04 | QA Validation | Testing (85%+ coverage) | Fase final de validacion |
| AG-05 | n8n Specialist | Workflows de automatizacion | Si hay integracion n8n |
| AG-06 | Design Specialist | Google Stitch MCP | Generacion de diseños |
| AG-07 | Apps Script Specialist | Google Apps Script | Proyectos GAS |
| AG-08 | Quality Auditor | Verificacion independiente | Auditoria post-QA, GO/NO-GO |

### Agent Teams (Claude Code nativo)

Configuracion para la feature experimental de Agent Teams de Claude Code:

```
agent-teams/
├── README.md                          # Documentacion completa
├── templates/
│   └── team-config.template.json      # Config base con todos los roles
├── prompts/                           # Prompts por rol
│   ├── lead.md
│   ├── flutter-dev.md
│   ├── react-dev.md
│   ├── db-infra.md
│   ├── qa-reviewer.md
│   ├── ui-designer.md
│   └── appscript-specialist.md
└── hooks/                             # Hooks de calidad
```

Cada rol tiene: modelo asignado, prompt especializado, file ownership y quality gates.

---

## Quality Gate System

Sistema de quality gates adaptativos con baseline auto-descubierto y evidencia auditable.

### Problema que resuelve

Antes: el pipeline confiaba en que Claude "recordara" hacer lint/test entre fases. No habia enforcement real ni evidencia auditable.

Ahora: quality gates automaticos entre cada fase, con evidence persistente y un auditor independiente (AG-08).

### Flujo con quality gates

```
/implement staff_management
  │
  ├─ [Pre-flight] Verificar/crear baseline → .quality/baseline.json
  ├─ [Fase 1: DB] → GATE: lint 0/0/0 ✅ compile ✅
  ├─ [Fase 2: Feature] → GATE: lint 0/0/0 ✅ compile ✅ tests pass ✅
  ├─ [Fase 3: QA] → GATE: coverage ≥ baseline ✅
  ├─ [AG-08: Audit] → Verifica tests reales, arquitectura, convenciones
  └─ [PR] → Con quality report y evidence adjunta
```

### Politicas

| Metrica | Politica | Descripcion |
|---------|----------|-------------|
| Lint | zero-tolerance | 0/0/0 siempre. BLOQUEANTE |
| Coverage | ratchet | Nunca baja. Sube progresivamente |
| Tests | no-regression | Nunca menos passing. Failing = 0 |
| Architecture | ratchet | Nunca mas violaciones |

### Comandos

```bash
/quality-gate           # Audit: escanea y genera baseline
/quality-gate check     # Valida contra baseline (GO/NO-GO)
/quality-gate plan      # Plan progresivo de mejora
/quality-gate fix       # Ejecuta siguiente paso del plan
/quality-gate report    # Report completo
```

### Evidence auditable

Cada feature genera `.quality/evidence/{feature}/` con:
- Metricas pre/post por fase
- Resultado del audit de AG-08
- Report legible con veredicto

---

## Integracion con Google Stitch MCP

El engine se integra con Google Stitch para generacion automatica de diseños UI:

| Herramienta MCP | Uso |
|-----------------|-----|
| `mcp__stitch__list_projects` | Listar proyectos Stitch |
| `mcp__stitch__get_project` | Detalles de un proyecto |
| `mcp__stitch__list_screens` | Listar pantallas generadas |
| `mcp__stitch__get_screen` | Obtener HTML de una pantalla |
| `mcp__stitch__generate_screen_from_text` | Generar pantalla desde prompt |

**Reglas:**
- Siempre Light Mode
- Una pantalla a la vez (la API tarda minutos)
- `GEMINI_3_PRO` para pantallas complejas, `GEMINI_3_FLASH` para simples
- HTMLs guardados en `doc/design/{feature}/`
- Prompts registrados en `doc/design/{feature}/{feature}_stitch_prompts.md`

**Configuracion por proyecto** en `.claude/settings.local.json`:
```json
{
  "stitch": {
    "projectId": "ID_PROYECTO",
    "deviceType": "DESKTOP",
    "modelId": "GEMINI_3_PRO"
  }
}
```

---

## Templates para Nuevos Proyectos

| Template | Proposito |
|----------|-----------|
| `CLAUDE.md.template` | Instrucciones del proyecto para Claude Code |
| `settings.json.template` | Permisos y configuracion de Claude Code |
| `team-config.json.template` | Configuracion de Agent Teams con todos los roles |

### Configurar un proyecto nuevo

1. Copiar `templates/CLAUDE.md.template` → `{proyecto}/CLAUDE.md`
2. Rellenar los placeholders (`{PROJECT_NAME}`, `{STACK}`, etc.)
3. Copiar agentes necesarios a `{proyecto}/.claude/agents/`
4. Ejecutar `/optimize-agents audit` para verificar configuracion

---

## Reglas Globales

El archivo `rules/GLOBAL_RULES.md` define reglas que aplican a **todos** los proyectos:

- **Comportamiento de Claude**: Arquitecto senior critico, no asistente complaciente
- **Prohibiciones universales**: No produccion sin confirmacion, no codigo sin tests, no commits sin validacion
- **Reglas por stack**: State management, arquitectura, hooks obligatorios por stack
- **Testing**: 85% coverage minimo, happy path + edge cases + fuzz
- **Checklist de feature**: Plan → Estructura → Modelo → Repository → UI → Tests → Lint

---

## Estructura del Repositorio

```
jps_dev_engine/
├── CLAUDE.md                      # Descripcion del engine para Claude
├── ENGINE_VERSION.yaml            # Version, stacks, servicios, changelog
├── README.md                      # Este archivo
├── install.sh                     # Instalador de commands + skills + hooks
│
├── .claude/                       # Configuracion Claude Code (v3.0)
│   ├── settings.json              #   Hooks config
│   ├── skills/                    #   Agent Skills (7 skills)
│   │   ├── prd/SKILL.md
│   │   ├── plan/SKILL.md
│   │   ├── implement/SKILL.md
│   │   ├── adapt-ui/SKILL.md
│   │   ├── optimize-agents/SKILL.md
│   │   ├── quality-gate/SKILL.md
│   │   └── explore/SKILL.md
│   └── hooks/                     #   Hook scripts
│       ├── pre-commit-lint.sh
│       ├── on-session-end.sh
│       └── implement-checkpoint.sh
│
├── commands/                      # Commands legacy (referencia)
│   ├── prd.md                     #   /prd — PRD + Work Item
│   ├── plan.md                    #   /plan — Plan tecnico + Stitch
│   ├── implement.md               #   /implement — Autopilot end-to-end
│   ├── adapt-ui.md                #   /adapt-ui — Mapeo de widgets
│   ├── optimize-agents.md         #   /optimize-agents — Audit agentico
│   └── quality-gate.md            #   /quality-gate — Quality gates adaptativos
│
├── agents/                        # Templates de agentes (9 roles)
│   ├── orchestrator.md
│   ├── feature-generator.md       #   AG-01
│   ├── uiux-designer.md           #   AG-02
│   ├── db-specialist.md           #   AG-03
│   ├── qa-validation.md           #   AG-04
│   ├── n8n-specialist.md          #   AG-05
│   ├── design-specialist.md       #   AG-06
│   ├── appscript-specialist.md    #   AG-07
│   ├── quality-auditor.md         #   AG-08 (NEW)
│   └── templates/
│
├── agent-teams/                   # Agent Teams nativo (Claude Code)
│   ├── README.md
│   ├── templates/
│   │   └── team-config.template.json
│   ├── prompts/                   #   Prompts por rol
│   └── hooks/                     #   Hooks de calidad
│
├── architecture/                  # Patrones por stack
│   ├── flutter/                   #   Clean Arch, BLoC, Responsive
│   ├── react/                     #   Next.js, Server Components
│   ├── python/                    #   FastAPI, SQLAlchemy
│   └── google-apps-script/        #   clasp, TypeScript, V8
│
├── design/                        # Integracion Google Stitch MCP
│   └── stitch/
│       ├── README.md
│       └── prompt-template.md
│
├── infra/                         # Patrones por servicio
│   ├── supabase/
│   ├── neon/
│   ├── stripe/
│   ├── firebase/
│   └── n8n/
│
├── templates/                     # Templates para nuevos proyectos
│   ├── CLAUDE.md.template
│   ├── settings.json.template
│   └── team-config.json.template
│
├── rules/                         # Reglas globales
│   └── GLOBAL_RULES.md
│
└── docs/                          # Documentacion del sistema
    ├── getting-started.md
    ├── commands.md
    ├── agent-teams.md
    └── architecture.md
```

---

## Ejemplo: Flujo Completo de una Feature

Este ejemplo muestra como se usa el engine para implementar una feature completa desde cero:

### 1. Crear el PRD

```
> /prd "Sistema de gestion de staff" "Necesitamos una pantalla para
  gestionar el personal: ver lista, crear, editar, eliminar.
  Cada miembro tiene nombre, email, rol y estado activo/inactivo.
  Filtrar por rol y buscar por nombre."
```

**Resultado:** PRD estructurado + Work Item `PROYECTO-15` en Plane

### 2. Generar el plan

```
> /plan PROYECTO-15
```

**Resultado:**
- `doc/plans/staff_management_plan.md` con 5 fases
- `doc/design/staff_management/staff_list.html` (diseño Stitch)
- `doc/design/staff_management/staff_form.html` (diseño Stitch)

### 3. Implementar

```
> /implement staff_management
```

**Resultado (automatico):**
1. Crea rama `feature/staff-management`
2. Verifica que los HTMLs de Stitch existen
3. Convierte diseños a widgets Flutter (o React/etc.)
4. Ejecuta Fase 1: tablas en Supabase + RLS
5. Ejecuta Fase 2: modelos Freezed + repository
6. Ejecuta Fase 3: BLoC + pages + layouts responsivos
7. Ejecuta Fase 4: DI + rutas + build_runner
8. Ejecuta Fase 5: tests con 87% coverage
9. Push + crea PR con resumen completo

```
✅ Implementacion Completada

Plan: doc/plans/staff_management_plan.md
Rama: feature/staff-management
PR: https://github.com/user/repo/pull/3

Archivos creados: 23
Tests: 45 pasando
Coverage: 87%
Commits: 7
Diseños Stitch: 2 pantallas
```

### 4. Review y merge

El desarrollador revisa la PR en GitHub y hace merge.

---

## Uso en un Proyecto Existente

1. **Instalar commands** (si no lo has hecho): `./install.sh`
2. **Copiar CLAUDE.md template** al proyecto y personalizar
3. **Copiar agentes** que necesites a `.claude/agents/`
4. **Ejecutar `/optimize-agents audit`** para evaluar la configuracion actual
5. **Seguir recomendaciones** del audit para mejorar

Ver guia completa en [docs/getting-started.md](docs/getting-started.md).

---

## Actualizacion

```bash
cd ~/jps_dev_engine
git pull
./install.sh
```

Los symlinks se actualizan automaticamente. Ejecuta `/optimize-agents audit` en tus proyectos para verificar que estan al dia con la nueva version del engine.

---

## Filosofia

1. **Consistencia > Velocidad** — Mejor hacer las cosas bien que rapido
2. **Documentacion ejecutable** — Los commands SON la documentacion
3. **Claude como arquitecto critico** — Cuestiona, no complace
4. **Escalable desde dia 1** — Multi-stack, multi-servicio, multi-agente
5. **Autopilot con control** — `/implement` automatiza, pero el humano revisa la PR

---

## Licencia

MIT

---

v3.1.0 | 2026-02-24 | JPS Developer
