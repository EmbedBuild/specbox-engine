<p align="center">
  <img src=".github/assets/Logo SpecBox.png" alt="SpecBox Engine" width="280" />
</p>

<h1 align="center">SpecBox Engine v5.25.0 — Stripe Connect</h1>

<p align="center">
  <strong>SpecBox Engine by JPS</strong> — Sistema de programacion agentica para Claude Code.<br/>
  <a href="#english-version">English version below</a>
</p>

Monorepo unificado que contiene Agent Skills auto-descubribles, hooks de calidad, patrones de arquitectura multi-stack, templates de agentes, MCP server con 138 tools, dashboard embebido (Sala de Maquinas), y pipeline spec-driven con Trello/Plane/FreeForm para desarrollo profesional con Claude Code.

**Novedad v5.25.0**: nueva skill [`/stripe-connect`](.claude/skills/stripe-connect/SKILL.md) — scaffoldea una integración Stripe Connect marketplace completa (Express + Direct charges + subscriptions embedded) en proyectos Supabase + React/Flutter en un solo comando. Ver [docs/skills/stripe-connect.md](docs/skills/stripe-connect.md).

---

## Tabla de Contenidos

- [Quick Start](#quick-start)
- [Flujo Completo de Desarrollo](#flujo-completo-de-desarrollo)
- [Skills (Comandos)](#skills-comandos)
- [Sistema de Agentes](#sistema-de-agentes)
- [Stacks Soportados](#stacks-soportados)
- [Servicios de Infraestructura](#servicios-de-infraestructura)
- [Quality Gate System](#quality-gate-system)
- [Hooks System](#hooks-system)
- [Self-Healing Protocol](#self-healing-protocol)
- [VEG — Visual Experience Generation](#veg--visual-experience-generation)
- [Multi-Backend: Trello + Plane + FreeForm](#multi-backend-trello--plane--freeform)
- [Spec-Driven Pipeline](#spec-driven-pipeline)
- [Pipeline Integrity (v5.7.0)](#pipeline-integrity-v570)
- [Hardened Autopilot Guards (v4.0.1)](#hardened-autopilot-guards-v401)
- [MCP Server](#mcp-server)
- [Sala de Maquinas (Dashboard)](#sala-de-maquinas-dashboard)
- [Google Stitch MCP](#google-stitch-mcp)
- [Context Engineering](#context-engineering)
- [Engram — Persistent Memory](#engram--persistent-memory)
- [Templates para Nuevos Proyectos](#templates-para-nuevos-proyectos)
- [Estructura del Repositorio](#estructura-del-repositorio)
- [Ejemplo: Flujo Completo](#ejemplo-flujo-completo)
- [Uso en Proyecto Existente](#uso-en-proyecto-existente)
- [Configuracion por Proyecto](#configuracion-por-proyecto)
- [Actualizacion](#actualizacion)
- [Filosofia](#filosofia)
- [Licencia](#licencia)

---

## Quick Start

```bash
# 1. Clonar
git clone <repo-url> ~/specbox-engine
cd ~/specbox-engine

# 2. Instalar skills + hooks + commands globales
./install.sh

# 3. Verificar skills
ls -la ~/.claude/skills/
# Deberias ver: prd, plan, implement, adapt-ui, optimize-agents, quality-gate,
# explore, feedback, check-designs, visual-setup, acceptance-check, quickstart,
# remote, release, compliance (15 skills)

# 4. Verificar hooks
ls -la ~/.claude/hooks/
# Deberias ver: 20 hooks .mjs + lib/ con 4 shared modules

# 5. Iniciar MCP server (opcional — para telemetria y dashboard)
pip install -e .
specbox-engine
```

Las Skills se auto-descubren cuando son relevantes. Los hooks se ejecutan automaticamente por Claude Code.

---

## Flujo Completo de Desarrollo

```
/prd ──────────> PRD + Work Item (Trello/Plane)
                   │
                   │  Documenta requisitos, US/UC/AC,
                   │  audiencia, VEG, NFRs.
                   │  Definition Quality Gate rechaza
                   │  criterios vagos o no-testables.
                   │
                   ▼
/plan ─────────> Plan tecnico + Diseños Stitch (HTML) + VEG
                   │
                   │  Desglosa en fases, analiza UI,
                   │  genera diseños Stitch MCP,
                   │  genera VEG (imagenes/motion/design),
                   │  guarda en doc/plans/ + doc/design/
                   │
                   ▼
/implement ────> Autopilot: rama + codigo + QA + Acceptance Gate + PR
                   │
                   │  Crea rama feature/, ejecuta fases,
                   │  design-to-code, genera imagenes VEG,
                   │  inyecta motion, tests, AG-08 audit,
                   │  AG-09a acceptance tests, AG-09b validation,
                   │  crea PR con acceptance evidence.
                   │
                   ▼
               Merge secuencial → pull main → siguiente UC
```

### Flujo Spec-Driven (Trello / Plane / FreeForm)

```
/prd ──> PRD + Board/Project (US/UC/AC cards/work-items)
           │
/plan ──> Plan tecnico + Stitch + VEG
           │  (adjunta plan como evidencia PDF a la US)
           │
/implement US-01 ──> Autopilot por UC:
           │
           ├── find_next_uc → UC-001 (Ready)
           │   ├── start_uc(UC-001) → In Progress
           │   ├── git checkout -b feature/...
           │   ├── Implementar fases
           │   ├── AG-08 + AG-09a + AG-09b
           │   ├── gh pr create
           │   ├── Auto-merge (si GO + ACCEPTED)
           │   ├── complete_uc(UC-001) → Done
           │   └── git pull main
           │
           ├── find_next_uc → UC-002 (Ready)
           │   ├── start_uc(UC-002) → In Progress
           │   ├── ... (mismo ciclo, rama nueva)
           │   └── git pull main
           │
           └── No mas UCs → move_us(US-01, "done")
```

### Comandos de soporte

| Comando | Proposito |
|---------|-----------|
| `/adapt-ui` | Escanea widgets/componentes del proyecto, genera mapeo UI |
| `/optimize-agents` | Audita y optimiza sistema agentico (score /100) |
| `/quality-gate` | Quality gates adaptativos con evidence auditable |
| `/explore` | Exploracion read-only del codebase |
| `/feedback` | Captura feedback de testing manual, bloquea merge si no resuelto |
| `/check-designs` | Escaneo retroactivo de compliance Stitch por UC |
| `/acceptance-check` | Validacion standalone de AC sin pipeline completo |
| `/quickstart` | Tutorial interactivo de onboarding (< 5 min) |
| `/remote` | Gestion remota de proyectos (WhatsApp/Discord via OpenClaw) |
| `/release` | Audita residuos + bump version + changelog + push |
| `/visual-setup` | Configura identidad visual: brand kit + Stitch DS + VEG |
| `/compliance` | Audita compliance SpecBox: version, hooks, settings, scoring A+ a F |

---

## Skills (Comandos)

> Desde v3.0, los commands se migraron a Agent Skills con YAML frontmatter, auto-discovery, context isolation, y hooks. Los archivos en `commands/` se mantienen como referencia.

### `/prd` — Generar PRD

Genera un Product Requirements Document estructurado con US/UC/AC hierarchy.

```
/prd "titulo" "descripcion de requerimientos"
```

**Que hace:**
1. Detecta tipo de PRD (feature nueva o refactor)
2. Recopila info: funcionalidades, interacciones UI, criterios
3. Genera PRD con template estructurado (US-XX, UC-XXX, AC-XX)
4. **Definition Quality Gate**: Rechaza criterios vagos o no-testables
5. Detecta audiencia y genera VEG Readiness
6. Crea Work Items en Trello o Plane con US/UC/AC cards
7. Adjunta PRD como evidencia PDF a la US

**Output:** `doc/prd/PRD_{nombre}.md` + Board/Project con cards

**Modos:**
- **Spec-Driven (Trello/Plane)**: Enriquece especificacion firmada por cliente
- **Freeform**: Crea PRD desde cero a partir de descripcion

---

### `/plan` — Generar Plan de Implementacion

Genera plan tecnico con analisis UI, diseños Stitch, y VEG.

```
/plan US-01                    # Desde User Story de Trello/Plane
/plan PROYECTO-42              # Desde work item de Plane
/plan "descripcion"            # Desde texto directo
```

**Que hace:**
1. Detecta origen y extrae requisitos del PRD
2. Explora el proyecto: stack, agentes, widgets existentes
3. Analiza componentes UI (obligatorio)
4. Mapea agentes AG-01 a AG-09 segun fases
5. Genera plan por fases: DB → UI → Feature → Integracion → QA
6. Genera VEG (Paso 2.5b): imagenes, motion, design
7. Genera diseños en Stitch MCP: pantallas HTML
8. Guarda plan en `doc/plans/` + HTMLs en `doc/design/` + VEG en `doc/veg/`
9. Adjunta plan como evidencia PDF a la US en Trello/Plane

**Output:** Plan + Stitch HTMLs + VEG artifacts

---

### `/implement` — Autopilot de Implementacion

Lee un plan y ejecuta el proceso completo de implementacion de forma autonoma.

```
/implement US-01                    # Ejecuta todos los UCs de la US en secuencia
/implement UC-001                   # Ejecuta un UC individual
/implement nombre_del_plan          # Busca doc/plans/{nombre}_plan.md
/implement doc/plans/mi_plan.md     # Path directo
/implement                          # Lista planes y pregunta
```

**Flujo interno:**

| Paso | Descripcion | Enforcement |
|------|-------------|-------------|
| 0 | Cargar y validar plan | — |
| 0.1a | Si Trello/Plane: cargar US/UC, `start_uc` | — |
| 0.3 | Detectar VEG | — |
| 0.5 | Pre-flight: working tree, rama, fetch | HARD BLOCK |
| **0.5b** | **Guardia anti-main** | **ERROR FATAL** (v4.0.1) |
| **0.5c** | **Validacion start_uc** | **ERROR FATAL** (v4.0.1) |
| **0.5d** | **Stitch Design Gate** | **BLOCKED** (v4.2.0) |
| 1 | Crear rama feature/ | — |
| 2 | Orquestacion por sub-agentes | — |
| 3 | Generar diseños Stitch (si faltan) | — |
| 3.5 | Generar imagenes VEG (si activo) | Cost warning |
| **3.5.5** | **Prohibicion placeholders CSS** | **REGLA** (v4.0.1) |
| 4 | Design-to-code + motion | — |
| 5 | Ejecutar fases del plan | Lint gates |
| 6 | Integracion | Build check |
| 7 | QA + Acceptance Gate | AG-08, AG-09a/b |
| 8 | Crear PR | — |
| **8.5.0** | **Validacion pre-merge** | **HARD BLOCK** (v4.0.1) |
| 8.5 | Merge secuencial + siguiente UC | Auto-merge conditions |

**Manejo de errores:**
- Compilacion → auto-fix (3 intentos), si persiste → healing protocol
- Stitch → reintenta una vez, si falla → continua sin diseño
- Coverage < 85% → genera tests adicionales (3 intentos)
- Conflictos → reporta al usuario, no resuelve automaticamente

---

### `/adapt-ui` — Mapeo de Componentes UI

```
/adapt-ui /path/al/proyecto              # Detectar
/adapt-ui /path/al/proyecto --normalize  # Detectar + mover a core
```

Escanea widgets/componentes, detecta framework, categoriza por tipo (Navigation, Data Display, Selection, Data Entry, Actions, Feedback), detecta design tokens, genera `.claude/ui-adapter.md`.

---

### `/optimize-agents` — Auditar Sistema Agentico

```
/optimize-agents audit       # Analisis completo (default)
/optimize-agents report      # Reporte ejecutivo
/optimize-agents apply       # Aplicar recomendaciones
/optimize-agents team-init   # Inicializar Agent Teams
/optimize-agents migrate     # Migrar legacy → Agent Teams
```

**Dimensiones (100 puntos):**

| Dimension | Puntos | Que evalua |
|-----------|--------|------------|
| Documentation Sync | 25 | CLAUDE.md vs codigo real |
| Validation Strategy | 15 | Hooks y gates de calidad |
| Model Optimization | 10 | Asignacion de modelos por complejidad |
| Team Coordination | 20 | Coordinacion entre agentes |
| Deprecation Hygiene | 15 | Limpieza de codigo obsoleto |
| Agent Teams Readiness | 15 | Preparacion para Agent Teams |

Incluye **Engine Sync**: detecta version del engine y compara archivos del proyecto con los originales.

---

### `/quality-gate` — Quality Gates Adaptativos

```
/quality-gate           # Audit: escanea y genera baseline
/quality-gate check     # Valida contra baseline
/quality-gate plan      # Plan progresivo de mejora
/quality-gate fix       # Ejecuta siguiente paso del plan
/quality-gate report    # Report completo
```

---

### `/explore` — Exploracion Read-Only

Exploracion del codebase sin capacidad de modificar archivos. Modo fork con Explore agent.

---

### `/feedback` — Feedback de Testing Manual

```
/feedback "descripcion del bug"       # Captura feedback
/feedback list                         # Lista feedback por feature
/feedback resolve FB-NNN               # Marca resuelto
```

Crea GitHub issues, vincula a AC-XX del PRD, bloquea merge si no resuelto.

---

### `/stripe-connect` — Scaffolder de Stripe Connect marketplace (v5.25.0)

```
/stripe-connect                      # Preflight + preguntas mínimas + generación
```

Scaffoldea una integración Stripe Connect marketplace completa en proyectos Supabase + React/Flutter en un único comando. Connect Express + Direct charges + subscriptions embedded (Payment Element/Sheet + Apple/Google Pay). Embedded-only por diseño — nunca redirect a stripe.com.

**Genera:**
- US-SPONSORSHIP con 12 UCs (UC-301..UC-312) en el spec backend
- 5 Edge Functions Supabase + 4 migraciones SQL con RLS
- Templates frontend React (4 archivos) o Flutter (7 archivos)
- Hook `stripe-safety-guard.mjs` (bloquea webhooks sin firma, sin idempotencia, Checkout hosted, sk_live hardcoded, Payment Links)
- Diseños Stitch de 6 pantallas si hay VEG configurado
- 12 tests Gherkin de aceptación (en español, con `stripe trigger` + test clocks)
- Docs parametrizadas (README de setup, Connect, Apple/Google Pay, events catalog, test scenarios)
- Cableado del Stripe MCP oficial en `.claude/settings.local.json`

**Alcance v1:** Supabase + React/Flutter + Connect Express + Direct charges + subscriptions. Otros backends y SaaS vanilla (`/stripe` hermana) reservados para v2.

Ver [docs/skills/stripe-connect.md](docs/skills/stripe-connect.md) para flujo completo.

---

## Sistema de Agentes

### Agentes Disponibles

| ID | Agente | Rol | Cuando |
|----|--------|-----|--------|
| — | **Orchestrator** | Coordinador. NUNCA escribe codigo. | Siempre |
| AG-01 | Feature Generator | Genera estructura completa por stack | Fase de logica |
| AG-02 | UI/UX Designer | Interfaces, responsiveness, VEG Motion | Fase UI |
| AG-03 | DB Specialist | Supabase, Neon, Firebase, migrations | Fase DB |
| AG-04 | QA Validation | Tests unitarios, 85%+ coverage | Fase QA |
| AG-05 | n8n Specialist | Workflows de automatizacion | Si hay n8n |
| AG-06 | Design Specialist | Google Stitch MCP, VEG enrichment | Diseños |
| AG-07 | Apps Script Specialist | Google Apps Script (clasp, V8) | Proyectos GAS |
| AG-08 | Quality Auditor | Verificacion independiente, GO/NO-GO | Post-QA |
| AG-09a | Acceptance Tester | Genera .feature + step definitions | Paso 7.5 |
| AG-09b | Acceptance Validator | Valida cumplimiento, ACCEPTED/REJECTED | Paso 7.7 |
| AG-10 | Developer Tester | Procesa feedback humano, GitHub issues | /feedback |

### Aislamiento Estricto del Orquestador

El Orquestador (main Claude thread) **NUNCA escribe codigo directamente**:

| Accion | Orquestador | Sub-agente |
|--------|:-----------:|:----------:|
| Leer codigo fuente | ❌ | ✅ |
| Escribir/editar codigo | ❌ | ✅ |
| Ejecutar lint/tests/build | ❌ | ✅ |
| Generar diseños Stitch | ❌ | AG-06 |
| Leer plan (1 vez) | ✅ | — |
| Crear rama y commits | ✅ | — |
| Crear PR | ✅ | — |
| Gestionar Trello/Plane state | ✅ | — |
| Decidir self-healing | ✅ | (delega fix) |

**Token budget del Orquestador**: Max 15% del context window (~30K tokens).

### Agent Teams (Claude Code nativo)

Configuracion para la feature experimental de Agent Teams:

```
agent-teams/
├── README.md
├── templates/team-config.template.json
├── prompts/                    # Prompts por rol
│   ├── lead.md
│   ├── flutter-dev.md
│   ├── react-dev.md
│   ├── db-infra.md
│   ├── qa-reviewer.md
│   ├── ui-designer.md
│   └── appscript-specialist.md
└── hooks/
```

---

## Stacks Soportados

| Stack | Version | Arquitectura | Docs |
|-------|---------|-------------|------|
| **Flutter** | 3.38+ | Clean Architecture, BLoC+Freezed, Responsive (3 layouts), DataSource | 6 docs |
| **React** | 19.x | App Router / SPA, Server Components, TanStack Query, Tailwind CSS | 3 docs |
| **Go** | 1.23+ | Clean Architecture, cmd/internal structure, testcontainers-go | 4 docs |
| **Python** | 3.12+ | FastAPI, SQLAlchemy 2 async, Pydantic v2, Repository pattern | 2 docs |
| **Google Apps Script** | V8 | clasp + TypeScript + esbuild, batch operations, PropertiesService | 4 docs |

Cada stack tiene su carpeta en `architecture/` con overview, folder-structure, patterns, testing-strategy, y e2e-testing.

---

## Servicios de Infraestructura

| Servicio | Carpeta | Contenido |
|----------|---------|-----------|
| **Supabase** | `infra/supabase/` | MCP tools, RLS policies, migrations, Realtime, DataSource |
| **Neon** | `infra/neon/` | Connection pooling, branching, Drizzle ORM, serverless |
| **Stripe** | `infra/stripe/` | Webhooks, Checkout, Subscriptions, Customer Portal |
| **Firebase** | `infra/firebase/` | Firestore rules, Auth, Cloud Functions, Storage |
| **n8n** | `infra/n8n/` | Workflow patterns, triggers, webhooks, error handling |

---

## Quality Gate System

Quality gates automaticos entre cada fase de `/implement`, con evidence persistente y auditor independiente (AG-08).

### Flujo con quality gates

```
/implement staff_management
  │
  ├─ [Pre-flight] Verificar/crear baseline → .quality/baseline.json
  ├─ [Fase 1: DB] → GATE: lint 0/0/0 ✅ compile ✅
  ├─ [Fase 2: Feature] → GATE: lint 0/0/0 ✅ compile ✅ tests ✅
  ├─ [Fase 3: QA] → GATE: coverage >= baseline ✅
  ├─ [AG-08: Audit] → GO / CONDITIONAL GO / NO-GO
  ├─ [AG-09a: Tests] → .feature + step definitions + screenshots
  ├─ [AG-09b: Gate] → ACCEPTED / CONDITIONAL / REJECTED
  └─ [PR] → Quality report + acceptance evidence
```

### Politicas

| Metrica | Politica | Descripcion |
|---------|----------|-------------|
| **Lint** | zero-tolerance | 0 errores / 0 warnings / 0 info. BLOQUEANTE |
| **Coverage** | ratchet | Nunca baja. Sube progresivamente |
| **Tests** | no-regression | Nunca menos passing. Failing = 0 |
| **Architecture** | ratchet | Nunca mas violaciones |

### Evidence auditable

Cada feature genera `.quality/evidence/{feature}/` con:
- Metricas pre/post por fase
- Resultado AG-08 (GO/NO-GO)
- Acceptance tests AG-09a (screenshots, traces, .feature files)
- Acceptance report AG-09b (ACCEPTED/REJECTED)
- Report con veredicto legible

---

## Hooks System

Enforcement automatico — no hace falta recordar ejecutarlos:

| Hook | Evento | Comportamiento |
|------|--------|----------------|
| **quality-first-guard.mjs** | PreToolUse (Write/Edit) | **BLOQUEANTE**: verifica que el archivo fue leido antes de modificarlo (v5.15.0) |
| **healing-budget-guard.mjs** | PreToolUse (Write/Edit) | **BLOQUEANTE**: para al agente tras 8 intentos de healing por feature (v5.19.0) |
| **pipeline-phase-guard.mjs** | PreToolUse (Write/Edit) | **BLOQUEANTE**: valida dependencias entre fases (DB antes de Feature, etc.) (v5.19.0) |
| **no-bypass-guard.mjs** | PreToolUse (Bash) | **BLOQUEANTE**: impide --no-verify, push --force, reset --hard (v5.13.0) |
| read-tracker.mjs | PostToolUse (Read) | Registra archivos leidos para quality-first-guard (v5.15.0) |
| **spec-guard.mjs** | PostToolUse (Write/Edit en src/lib/) | **BLOQUEANTE**: verifica UC activo antes de escribir codigo (v5.7.0) |
| **branch-guard.mjs** | PostToolUse (Write/Edit en src/lib/) | **BLOQUEANTE**: impide escribir en main/master (v5.10.0) |
| **commit-spec-guard.mjs** | PostToolUse (git commit) | **BLOQUEANTE** en main + WARNING: UC activo, checkpoint, tamano (v5.7.0) |
| **pre-commit-lint.mjs** | PostToolUse (git commit) | **BLOQUEANTE**: zero-tolerance lint (0 errores, 0 warnings) |
| **e2e-gate.mjs** | PostToolUse (git commit) | **BLOQUEANTE**: valida results.json + HTML Evidence Report (v5.13.0) |
| checkpoint-freshness-guard.mjs | PostToolUse (git commit) | WARNING si checkpoint >30 min durante implementacion (v5.19.0) |
| uc-lifecycle-guard.mjs | PostToolUse (git push) | WARNING si push sin mover UC a Review (v5.19.0) |
| **design-gate.mjs** | PostToolUse (Write/Edit pages/) | **BLOQUEANTE**: requiere HTML Stitch en doc/design/ (v4.2.0) |
| on-session-end.mjs | Stop | Registra telemetria en .quality/logs/ + heartbeat |
| implement-checkpoint.mjs | Manual (/implement) | Guarda progreso de fase para resume |
| implement-healing.mjs | Manual (/implement) | Registra eventos de self-healing |
| post-implement-validate.mjs | Manual (/implement) | Detecta regresion de baseline |
| heartbeat-sender.mjs | Manual (hooks) | Envia snapshot de estado al VPS; cola local si offline |
| mcp-report.mjs | Utility | Cliente MCP reutilizable para telemetria remota |
| e2e-report.mjs | Manual (/implement) | Reporta resultados Playwright E2E a telemetria MCP |

**9 hooks BLOQUEANTES** + 11 no-bloqueantes = 20 hooks totales. Todos en Node.js (.mjs), cross-platform (macOS/Linux/Windows), zero npm dependencies. Configuracion en `.claude/settings.json`.

---

## Self-Healing Protocol

Cuando `/implement` encuentra errores, el sistema intenta auto-recuperarse:

| Nivel | Accion | Ejemplo |
|-------|--------|---------|
| **1: Auto-Fix** | Ejecuta auto-fix del stack | `dart fix --apply`, `eslint --fix`, `ruff check --fix` |
| **2: Diagnostico** | Analiza error, aplica fix especifico | Import faltante, tipo incorrecto |
| **3: Rollback** | Revierte fase, reintenta desde cero | `git stash` + fresh attempt |
| **4: Humano** | Genera error report y pausa | `.quality/evidence/{feature}/error_report.md` |

Todos los intentos se registran en `.quality/evidence/{feature}/healing.jsonl`.

---

## VEG — Visual Experience Generation

Sistema de 3 modos para generar decisiones visuales (imagenes, motion, design) adaptadas a la audiencia del proyecto.

### Modos

| Modo | Nombre | Cuando |
|------|--------|--------|
| 1 | **Uniform** | Audiencia homogenea (mismo VEG para todo) |
| 2 | **Per Profile** | Variantes por perfil de usuario |
| 3 | **Per ICP+JTBD** | Personalizado por ICP con JTBD racional y emocional |

### 3 Pilares

| Pilar | Contenido | Integracion |
|-------|-----------|-------------|
| **Pilar 1: Imagenes** | Tipo, mood, paleta, prompts por seccion | Paso 3.5 genera con MCP (Canva/Freepik/etc.) |
| **Pilar 2: Motion** | Nivel (1-3), page enter, scroll reveal, hover | Paso 4 inyecta catalogo en AG-02 |
| **Pilar 3: Design** | Densidad, whitespace, tipografia, CTA, sombras | Paso 3 enriquece prompts Stitch |

### 6 Arquetipos

| Arquetipo | Target | Ejemplo |
|-----------|--------|---------|
| Corporate | Decision-makers empresariales | iAutomat.com |
| Startup | Early adopters tecnicos | SaaS dashboard |
| Creative | Artistas y disenadores | Portfolio creativo |
| Consumer | Usuarios finales masivos | App de delivery |
| Gen-Z | Audiencia joven digital-native | Red social |
| Government | Instituciones publicas | Portal de tramites |

### Image Generation Pipeline (Paso 3.5)

```
1. Leer VEG Pilar 1 → prompts por seccion
2. Advertencia de costes (OBLIGATORIO)
3. Health check del MCP (Canva/Freepik/etc.)
4. Generar imagenes con MCP
5. Guardar en doc/veg/{feature}/assets/
6. Registrar en image_prompts.md
```

**Providers soportados:**

| Provider | Coste | Calidad |
|----------|-------|---------|
| **Canva** (Pro/Premium) | €0 adicional | Alta (Magic Media) |
| Freepik (Mystic) | Segun plan | Alta (stock + AI) |
| lansespirit (OpenAI/Gemini) | $0.02-0.19/img | Muy alta |

**Si MCP no disponible**: Crea `PENDING_IMAGES.md` con prompts para generacion manual.

### Prohibicion de Placeholders CSS (v4.0.1)

> Cuando el VEG especifica imagenes (Pilar 1), **NUNCA** usar gradientes CSS, iconos SVG inline, o iniciales de texto como sustituto. Solo imagenes reales o `<img>` con paths pendientes.

---

## Multi-Backend: Trello + Plane + FreeForm

Desde v4.1.0, el engine soporta multiples gestores de proyecto intercambiables. Los 3 backends implementan la misma interfaz `SpecBackend` (25 metodos), por lo que todos los tools MCP funcionan de forma identica con cualquiera.

### Arquitectura Multi-Backend

```
spec_driven.py (21 tools, backend-agnostic)
        │
        ▼
  SpecBackend ABC ─── 25 metodos unificados
   ┌────┼────────────┐
   │    │             │
TrelloBackend  PlaneBackend  FreeformBackend
   │              │              │
TrelloClient   PlaneClient   JSON + Markdown local
(httpx+retry)  (httpx+retry)  (pathlib, sin API)
```

### Configuracion de backend

El backend se elige al autenticarse. Solo uno esta activo por sesion. Todos los tools MCP (`setup_board`, `find_next_uc`, `mark_ac`, etc.) funcionan exactamente igual con cualquiera:

**Trello** — `set_auth_token(token="TRELLO_TOKEN", api_key="TRELLO_KEY")`

**Plane (cloud o self-hosted)** — `set_auth_token(token="PLANE_API_KEY", backend_type="plane", base_url="https://app.plane.so", workspace_slug="my-ws")`

**FreeForm (local, sin API)** — `set_auth_token(api_key="freeform", token="", backend_type="freeform", root_path="doc/tracking")`

> Para Plane self-hosted (CE), cambia `base_url` a tu dominio (ej. `https://plane.miempresa.com`).

### FreeForm Backend (v5.8.0)

Backend sin API externa para proyectos personales o donde Trello/Plane es overkill. Almacena todo como JSON local y genera Markdowns de progreso automaticamente:

```
doc/tracking/
├── boards/{board_id}/
│   ├── config.json          ← BoardConfig
│   ├── items.json           ← Todos los items (US/UC/AC)
│   ├── comments/{item_id}.jsonl
│   └── attachments/{item_id}/
└── progress/
    ├── README.md            ← Vista general con tablas US/UC
    └── UC-XXX.md            ← Detalle por UC con ACs y estado
```

Los hooks de Pipeline Integrity (v5.7.0) funcionan igual con FreeForm — leen `.quality/active_uc.json` que es backend-agnostic.

### Migracion entre backends

| Tool | Proposito |
|------|-----------|
| `migrate_preview` | Vista previa de la migracion (dry run) |
| `migrate_project` | Migrar US/UC/AC entre backends |
| `migrate_status` | Estado de la migracion en curso |
| `set_migration_target` | Configurar backend destino |
| `switch_backend` | Cambiar backend activo de la sesion |

La migracion es idempotente: usa `external_source` + `external_id` para evitar duplicados.

---

## Pipeline Integrity (v5.7.0)

Enforcement a nivel de hooks que hace **imposible** escribir codigo sin UC activo en un proyecto spec-driven.

### spec-guard.mjs (BLOQUEANTE)

```
Agente intenta Write/Edit en src/ o lib/
  ↓
¿Existe .quality/active_uc.json?
├── NO → ❌ BLOQUEADO: "No active UC. Call start_uc() first."
├── SI → ¿Tiene menos de 24 horas?
│   ├── SI → ✅ Permitido
│   └── NO → ❌ BLOQUEADO: "Active UC expired (>24h). Call start_uc() again."
└── Proyecto sin boardId configurado → ✅ No es spec-driven, permitir
```

### commit-spec-guard.mjs (WARNING)

```
Agente intenta git commit
  ↓
Verificar:
├── ¿UC activo? → WARNING si no
├── ¿Checkpoint reciente (<30 min)? → WARNING si stale
└── ¿Commit < 500 lineas? → WARNING si grande
```

Resultado del incidente embed-build (2026-03-24): un agente implemento 9 UCs sin pipeline, dejando Trello vacio. Estos hooks previenen que esto vuelva a ocurrir.

---

## Spec-Driven Pipeline

Pipeline basado en especificacion con Trello, Plane o FreeForm como fuente de verdad.

### Jerarquia

```
Board/Project
├── US-01: User Story (card/work-item en lista workflow)
│   ├── UC-001: Use Case (card hija / sub-work-item)
│   │   ├── AC-01: Acceptance Criterion (checklist item / sub-item)
│   │   ├── AC-02: ...
│   │   └── AC-03: ...
│   ├── UC-002: ...
│   └── UC-003: ...
├── US-02: ...
└── ...
```

### Workflow States

```
Backlog → Ready → In Progress → Review → Done
```

### Tools MCP (backend-agnostic)

| Tool | Proposito |
|------|-----------|
| `setup_board` | Crear board/proyecto con listas workflow |
| `import_spec` | Importar US/UC/AC desde JSON |
| `get_us` / `list_us` | Leer User Stories |
| `get_uc` / `list_uc` | Leer Use Cases |
| `find_next_uc` | Siguiente UC en Ready |
| `start_uc` | Mover UC a In Progress |
| `complete_uc` | Mover UC a Done |
| `move_us` / `move_uc` | Cambiar estado |
| `mark_ac` / `mark_ac_batch` | Marcar criterios de aceptacion |
| `attach_evidence` | Adjuntar PDF de evidencia |
| `get_evidence` | Buscar evidencia adjunta |
| `get_board_status` | Estado completo del board/proyecto |
| `get_delivery_report` | Reporte de entrega |

### Configuracion

En `.claude/project-config.json` (PREFERIDO):

```json
{
  "trello": {
    "boardId": "ID_DEL_BOARD"
  },
  "plane": {
    "projectId": "ID_DEL_PROYECTO",
    "baseUrl": "https://app.plane.so",
    "workspaceSlug": "mi-workspace"
  },
  "stitch": {
    "projectId": "ID_PROYECTO_STITCH",
    "deviceType": "DESKTOP",
    "modelId": "GEMINI_3_PRO"
  }
}
```

> **Nota v4.0.1**: `.claude/project-config.json` es la ubicacion preferida porque Claude Code rechaza campos custom en `settings.local.json`.

---

## Hardened Autopilot Guards (v4.0.1+)

La v4.0.1 introduce **HARD BLOCKS** que previenen las violaciones de protocolo mas criticas durante la implementacion autonoma. Estas validaciones detienen el pipeline inmediatamente si se detecta una inconsistencia.

### Paso 0.5b: Guardia anti-main (ERROR FATAL)

```
¿Estamos implementando codigo directamente en main/master?
├── En Paso 0: OK (el Paso 1 creara la rama)
├── En Paso 5+: ❌ ERROR FATAL — PARAR INMEDIATAMENTE
└── Razon: Sin rama feature/ → sin PR → sin acceptance evidence → sin review
```

### Paso 0.5c: Validacion Trello/Plane state (ERROR FATAL)

```
¿Se llamo start_uc antes de implementar? (Trello/Plane spec-driven)
├── SI y status == "in_progress": OK
├── SI pero status incorrecto: Recovery automatico (reintentar start_uc)
└── NO: ❌ ERROR FATAL — llamar start_uc o PARAR
```

### Paso 0.5d: Stitch Design Gate (BLOCKED) — v4.2.0

```
¿El UC tiene pantallas definidas?
├── No → SKIP (gate no aplica)
└── Si → ¿Existen HTMLs en doc/design/{feature}/?
    ├── Si → OK, continuar
    └── No → ❌ BLOCKED
        "No Stitch designs found for UC-XXX.
         Run /plan first or generate designs manually."
```

Complementado por:
- **Hook `design-gate.mjs`**: WARNING en cada Write/Edit sobre `presentation/pages/` si no hay diseño.
- **AG-08 Check 6**: NO-GO si paginas carecen de `// Generated from: doc/design/...` comment.
- **/check-designs**: Escaneo retroactivo de compliance Stitch por UC.

### Paso 3.5.5: Prohibicion de placeholders CSS

```
¿El VEG tiene Pilar 1 (Imagenes)?
├── SI: PROHIBIDO usar gradientes CSS, iconos SVG, o iniciales como sustituto
└── NO: Libre de usar cualquier tecnica visual
```

### Paso 8.5.0: Validacion pre-merge (4 checks BLOQUEANTES)

| Check | Que valida | Si falla |
|-------|-----------|----------|
| 1 | Rama actual es `feature/*` | ERROR FATAL |
| 2 | PR abierta existe (`gh pr view`) | ERROR FATAL |
| 3 | UC en estado `in_progress` (Trello/Plane) | Recovery + WARNING |
| 4 | `veg_images_pending == false` | Merge bloqueado, espera usuario |

### Por que estos guards son necesarios

Antes de v4.0.1, estas validaciones eran "soft requirements" — documentadas en el skill pero no validadas en runtime. El agente podia:
- Implementar todo en main sin crear rama
- Crear PR sin haber llamado start_uc
- Auto-merge con imagenes placeholder degradando calidad visual
- Saltarse complete_uc dejando el board Trello/Plane inconsistente
- **Generar paginas UI directamente sin diseños Stitch previos** (corregido en v4.2.0)

Ahora son **HARD BLOCKS** que detienen el pipeline.

---

## MCP Server

Servidor MCP unificado con 138 tools en 24 modulos.

### Arquitectura

```
server/
├── server.py              # FastMCP main server
├── dashboard_api.py       # REST API para dashboard
├── auth_gateway.py        # Credenciales per-session (Trello + Plane + FreeForm)
├── spec_backend.py        # SpecBackend ABC (25 metodos)
├── trello_client.py       # Async httpx con retry (Trello)
├── stitch_client.py       # Async MCP JSON-RPC client (Stitch)
├── board_helpers.py       # Card parsing, custom fields (Trello)
├── backends/              # Multi-backend implementations
│   ├── trello_backend.py  #   TrelloBackend (SpecBackend wrapper)
│   ├── plane_backend.py   #   PlaneBackend (SpecBackend implementation)
│   ├── plane_client.py    #   PlaneClient (httpx async, X-Api-Key)
│   └── freeform_backend.py #  FreeformBackend (JSON + Markdown local)
├── models.py              # Pydantic models (US, UC, AC)
├── pdf_generator.py       # Markdown → PDF
├── tools/                 # 24 modulos, 138 tools
│   ├── engine.py          # 3 tools: version, status, stacks
│   ├── plans.py           # 3 tools: list, read, architecture
│   ├── quality.py         # 4 tools: baseline, logs, evidence
│   ├── skills.py          # 2 tools: list, read
│   ├── features.py        # 6 tools: in-progress, designs
│   ├── telemetry.py       # 6 tools: sessions, events
│   ├── hooks.py           # 3 tools: list, config, source
│   ├── onboarding.py      # 9 tools: register, onboard, upgrade
│   ├── state.py           # 17 tools: report, checkpoint, healing
│   ├── spec_driven.py     # 21 tools: backend-agnostic (US/UC/AC)
│   ├── migration.py       # 5 tools: Trello ↔ Plane migration
│   ├── stitch.py          # 13 tools: Stitch MCP proxy
│   ├── heartbeat_stats.py # 1 tool: heartbeat observability
│   ├── acceptance.py      # 3 tools: acceptance check, report, gap
│   ├── benchmark.py       # 1 tool: benchmark snapshot
│   ├── hints.py           # 3 tools: skill hints
│   ├── live_state.py      # 4 tools: project live state
│   ├── skill_registry.py  # 3 tools: discover, validate
│   └── sync.py            # 2 tools: GitHub sync
├── resources/             # 8 MCP Resources
└── dashboard/             # React 19 + Vite frontend
```

### Ejecucion

```bash
# Instalar dependencias
pip install -e .

# Ejecutar servidor
specbox-engine

# Docker
docker compose up
```

**Dependencias**: Python 3.12+, FastMCP 3.0.0+, httpx, pydantic, fpdf2, structlog.

---

## Sala de Maquinas (Dashboard)

Dashboard embebido (React 19 + Vite) que **cada usuario despliega con su propia instancia del MCP server**. La Sala de Maquinas muestra los datos de **tus** proyectos, almacenados localmente en tu `STATE_PATH`. No hay servidor central compartido — cada instalacion es independiente y privada.

**Features:**
- Estado de proyectos onboarded
- Telemetria de sesiones
- Self-healing events y resolution rates
- Quality baselines y evidencia
- Spec-Driven: estado de boards Trello y proyectos Plane
- Acceptance tests y validaciones
- E2E test results

**Seguridad en produccion:**

| Variable | Valor recomendado | Descripcion |
|----------|-------------------|-------------|
| `DASHBOARD_TOKEN` | Token secreto largo | **Obligatorio**. Sin token, el dashboard es accesible sin autenticacion |
| `DASHBOARD_CORS_ORIGIN` | `https://tu-dominio.com` | Restringe que origenes pueden hacer requests. Vacio = solo mismo origen |

```bash
# Ejemplo: produccion segura
DASHBOARD_TOKEN=mi-token-secreto-largo
DASHBOARD_CORS_ORIGIN=https://mi-sala.ejemplo.com
```

---

## Google Stitch MCP

Generacion automatica de diseños UI via Google Stitch. Desde v5.6.0 el Engine incluye un **Stitch MCP Proxy** que permite usar Stitch desde claude.ai sin configurar un conector OAuth adicional.

### Stitch Proxy (v5.6.0) — 13 tools

El proxy cubre los 12 tools nativos de Stitch + configuracion de API Key por proyecto:

| Tool del Engine | Stitch nativo | Descripcion |
|----------------|---------------|-------------|
| `stitch_set_api_key` | — | Configurar API Key por proyecto |
| `stitch_create_project` | `create_project` | Crear proyecto/workspace |
| `stitch_list_projects` | `list_projects` | Listar proyectos |
| `stitch_get_project` | `get_project` | Detalles de un proyecto |
| `stitch_list_screens` | `list_screens` | Listar pantallas |
| `stitch_get_screen` | `get_screen` | Metadata de pantalla |
| `stitch_fetch_screen_code` | `fetch_screen_code` | Descargar HTML raw |
| `stitch_fetch_screen_image` | `fetch_screen_image` | Screenshot hi-res (base64) |
| `stitch_generate_screen` | `generate_screen_from_text` | Generar pantalla desde prompt |
| `stitch_edit_screen` | `edit_screens` | Editar pantalla existente |
| `stitch_generate_variants` | `generate_variants` | Variantes (REFINE/EXPLORE/REIMAGINE) |
| `stitch_extract_design_context` | `extract_design_context` | Extraer Design DNA |
| `stitch_build_site` | `build_site` | Sitio multi-pagina |

### Acceso directo (Claude Code local)

Tambien disponible via MCP directo con estas herramientas:

| Herramienta MCP | Uso |
|-----------------|-----|
| `mcp__stitch__list_projects` | Listar proyectos Stitch |
| `mcp__stitch__get_project` | Detalles de un proyecto |
| `mcp__stitch__list_screens` | Listar pantallas |
| `mcp__stitch__get_screen` | Obtener HTML de pantalla |
| `mcp__stitch__generate_screen_from_text` | Generar pantalla desde prompt |

**Reglas:**
- Siempre Light Mode
- Una pantalla a la vez (la API tarda minutos)
- `GEMINI_3_PRO` para complejas, `GEMINI_3_FLASH` para simples
- HTMLs en `doc/design/{feature}/`
- Prompts en `doc/design/{feature}/{feature}_stitch_prompts.md`

---

## Context Engineering

Sistema de gestion de contexto para mantener el orquestador dentro de limites.

| Operacion | Budget max |
|-----------|-----------|
| Fase de implementacion | ~20,000 tokens (v5.24.0: expandido para Opus 4.7) |
| Resumen de sub-agente | Max 5 lineas |
| Plan (lectura unica) | Sin limite |
| Checkpoint | ~500 tokens |

**Reglas de pruning:**
- Agressive pruning despues de cada fase
- External persistence (checkpoints, Engram)
- Compact summaries por defecto
- Fork isolation para sub-agentes

---

## Engram — Persistent Memory

Memoria persistente FTS5 para sobrevivir compactaciones de contexto.

```
mem_save    → Guardar informacion
mem_search  → Buscar por keywords
mem_context → Recuperar contexto del proyecto
```

**Protocolo "Surviving Compaction":**
1. `mem_context` con proyecto actual
2. `mem_search` con keywords relevantes
3. Solo despues de recuperar → continuar

**Instalacion**: Binario Go precompilado (~5 MB) desde [GitHub releases](https://github.com/Gentleman-Programming/engram/releases).

---

## Templates para Nuevos Proyectos

| Template | Proposito |
|----------|-----------|
| `CLAUDE.md.template` | Instrucciones Claude Code + Engram + VEG |
| `settings.json.template` | Permisos, hooks, MCP config |
| `team-config.json.template` | Agent Teams con todos los roles |
| `quality-baseline.json.template` | Baseline de calidad inicial |

### Onboarding automatico

```
# Via MCP
onboard_project(path, name)   # Auto-detecta stack, genera CLAUDE.md, configura hooks
upgrade_project(name)          # Actualiza al ultimo template del engine
```

---

## Estructura del Repositorio

```
specbox-engine/
├── CLAUDE.md                          # Instrucciones del engine para Claude
├── ENGINE_VERSION.yaml                # Version 5.19.0, stacks, servicios, changelog
├── README.md                          # Este archivo
├── CHANGELOG.md                       # Historial de cambios desde v1.0.0
├── LICENSE                            # MIT
├── install.sh                         # Instalador de skills + hooks + commands
├── pyproject.toml                     # Python project config (FastMCP 3.0.0+)
├── Dockerfile                         # Multi-stage (Node 20 + Python 3.12)
├── docker-compose.yml                 # Docker Compose config
│
├── .claude/                           # Configuracion Claude Code
│   ├── settings.json                  #   Hooks config
│   ├── skills/                        #   15 Agent Skills
│   │   ├── prd/SKILL.md              #     PRD generator
│   │   ├── plan/SKILL.md             #     Plan + Stitch + VEG
│   │   ├── implement/SKILL.md        #     Autopilot (1880+ lineas)
│   │   ├── adapt-ui/SKILL.md         #     UI component scanner
│   │   ├── optimize-agents/SKILL.md  #     Agent system auditor
│   │   ├── quality-gate/SKILL.md     #     Quality gates
│   │   ├── explore/SKILL.md          #     Read-only exploration
│   │   ├── feedback/SKILL.md         #     Developer feedback
│   │   ├── acceptance-check/SKILL.md #     Standalone AC validation
│   │   ├── check-designs/SKILL.md    #     Stitch compliance scan
│   │   ├── visual-setup/SKILL.md     #     Brand kit + Stitch DS + VEG
│   │   ├── quickstart/SKILL.md       #     Interactive onboarding
│   │   ├── remote/SKILL.md           #     Remote project management
│   │   ├── release/SKILL.md          #     Automated release pipeline
│   │   └── compliance/SKILL.md       #     SpecBox compliance audit
│   └── hooks/                         #   20 Hook scripts + lib/
│       ├── quality-first-guard.mjs    #     BLOQUEANTE: read before write (v5.15.0)
│       ├── healing-budget-guard.mjs   #     BLOQUEANTE: max 8 healing (v5.19.0)
│       ├── pipeline-phase-guard.mjs   #     BLOQUEANTE: phase ordering (v5.19.0)
│       ├── no-bypass-guard.mjs        #     BLOQUEANTE: no --no-verify/--force (v5.13.0)
│       ├── spec-guard.mjs             #     BLOQUEANTE: UC activo para writes (v5.7.0)
│       ├── branch-guard.mjs           #     BLOQUEANTE: no writes on main (v5.10.0)
│       ├── commit-spec-guard.mjs      #     BLOQUEANTE + WARNING: commits (v5.7.0)
│       ├── pre-commit-lint.mjs        #     BLOQUEANTE: zero-tolerance lint
│       ├── e2e-gate.mjs               #     BLOQUEANTE: evidence validation (v5.13.0)
│       ├── design-gate.mjs            #     BLOQUEANTE: Stitch design required (v4.2.0)
│       ├── checkpoint-freshness-guard.mjs # WARNING: stale checkpoint (v5.19.0)
│       ├── uc-lifecycle-guard.mjs     #     WARNING: push sin move_uc (v5.19.0)
│       ├── read-tracker.mjs           #     Tracks reads for quality-first-guard
│       ├── on-session-end.mjs         #     Session telemetry + heartbeat
│       ├── implement-checkpoint.mjs   #     Phase checkpointing
│       ├── implement-healing.mjs      #     Healing event logging
│       ├── post-implement-validate.mjs #    Baseline regression
│       ├── heartbeat-sender.mjs       #     Estado al VPS (cola si offline)
│       ├── mcp-report.mjs             #     MCP client helper
│       ├── e2e-report.mjs             #     Playwright E2E reporting
│       └── lib/                       #     Shared: utils, output, config, http
│
├── server/                            # MCP Server + Dashboard
│   ├── server.py                      #   FastMCP main
│   ├── dashboard_api.py               #   REST API
│   ├── auth_gateway.py                #   Per-session credentials
│   ├── trello_client.py               #   Async Trello client
│   ├── board_helpers.py               #   Card parsing
│   ├── models.py                      #   Pydantic models
│   ├── pdf_generator.py               #   Markdown → PDF
│   ├── tools/                         #   24 modules, 138 tools
│   │   ├── engine.py                  #     Version, status, rules
│   │   ├── plans.py                   #     Plans management
│   │   ├── quality.py                 #     Quality baselines
│   │   ├── skills.py                  #     Skill discovery
│   │   ├── features.py               #     Feature tracking
│   │   ├── telemetry.py              #     Sessions, events
│   │   ├── hooks.py                   #     Hook config
│   │   ├── onboarding.py             #     Project onboarding
│   │   ├── state.py                   #     State reporting
│   │   ├── spec_driven.py            #     Backend-agnostic (21 tools)
│   │   └── migration.py             #     Trello ↔ Plane (5 tools)
│   ├── backends/                      #   Multi-backend layer
│   │   ├── trello_backend.py         #     TrelloBackend (SpecBackend)
│   │   ├── plane_backend.py          #     PlaneBackend (SpecBackend)
│   │   ├── plane_client.py           #     PlaneClient (httpx async)
│   │   └── freeform_backend.py       #     FreeformBackend (JSON + Markdown)
│   ├── spec_backend.py               #   SpecBackend ABC (25 methods)
│   ├── resources/                     #   8 MCP Resources
│   └── dashboard/                     #   Sala de Maquinas (React 19 + Vite)
│       └── src/
│
├── commands/                          # Commands legacy (referencia)
│   ├── prd.md
│   ├── plan.md
│   ├── implement.md
│   ├── adapt-ui.md
│   ├── optimize-agents.md
│   ├── quality-gate.md
│   └── feedback.md
│
├── agents/                            # 12 Agent templates
│   ├── orchestrator.md                #   Coordinador principal
│   ├── feature-generator.md           #   AG-01
│   ├── uiux-designer.md              #   AG-02
│   ├── db-specialist.md              #   AG-03
│   ├── qa-validation.md              #   AG-04
│   ├── n8n-specialist.md             #   AG-05
│   ├── design-specialist.md          #   AG-06
│   ├── appscript-specialist.md       #   AG-07
│   ├── quality-auditor.md            #   AG-08
│   ├── acceptance-tester.md          #   AG-09a
│   ├── acceptance-validator.md       #   AG-09b
│   ├── developer-tester.md           #   AG-10
│   └── templates/
│
├── agent-teams/                       # Agent Teams nativo (Claude Code)
│   ├── README.md
│   ├── templates/team-config.template.json
│   ├── prompts/                       #   Prompts por rol
│   └── hooks/
│
├── architecture/                      # Patrones por stack (15 docs)
│   ├── flutter/                       #   6 docs: overview, folder, bloc, responsive, testing, e2e
│   ├── react/                         #   3 docs: overview, testing, e2e
│   ├── python/                        #   2 docs: overview, testing
│   └── google-apps-script/            #   4 docs: overview, folder, patterns, testing
│
├── design/                            # Google Stitch MCP integration
│   └── stitch/
│       ├── README.md
│       └── prompt-template.md
│
├── infra/                             # Patrones por servicio (5 servicios)
│   ├── supabase/patterns.md
│   ├── neon/patterns.md
│   ├── stripe/patterns.md
│   ├── firebase/patterns.md
│   └── n8n/patterns.md
│
├── templates/                         # Templates para nuevos proyectos
│   ├── CLAUDE.md.template
│   ├── settings.json.template
│   ├── team-config.json.template
│   └── quality-baseline.json.template
│
├── rules/                             # Reglas globales
│   └── GLOBAL_RULES.md               #   525 lineas: comportamiento, stacks, quality, BDD
│
├── doc/                               # Documentacion interna
│   ├── templates/                     #   VEG template, archetypes, Gherkin template
│   ├── plans/                         #   Planes del propio engine
│   ├── research/                      #   VEG providers, motion strategy, tooling
│   └── knowledgeguide/                #   Guia para audiencia no-tecnica
│
├── docs/                              # Documentacion publica
│   ├── getting-started.md
│   ├── commands.md
│   ├── agent-teams.md
│   └── architecture.md
│
└── tests/                             # 171+ tests unificados
```

---

## Ejemplo: Flujo Completo

### 1. Crear PRD + Board Trello/Plane

```
> /prd "Sistema de gestion de staff" "Necesitamos una pantalla para
  gestionar el personal: ver lista, crear, editar, eliminar.
  Cada miembro tiene nombre, email, rol y estado activo/inactivo."
```

**Resultado:**
- `doc/prd/PRD_staff_management.md` con US-01, UC-001..003, AC-01..09
- Board Trello / proyecto Plane con cards/work-items US y UC creados
- Definition Quality Gate: todos los AC verificados como testables

### 2. Generar Plan + Diseños

```
> /plan US-01
```

**Resultado:**
- `doc/plans/staff_management_plan.md` con 5 fases
- `doc/design/staff_management/*.html` (pantallas Stitch)
- `doc/veg/staff_management/veg-*.md` (VEG artifacts)
- Plan adjunto como PDF a la US en Trello/Plane

### 3. Implementar

```
> /implement US-01
```

**Resultado (automatico, por UC):**

```
UC-001: CRUD Backend
  ├── start_uc(UC-001)
  ├── git checkout -b feature/staff-crud-backend
  ├── Fase 1: tablas Supabase + RLS
  ├── Fase 2: models + repository
  ├── AG-08: GO ✅
  ├── AG-09b: ACCEPTED ✅
  ├── gh pr create + auto-merge
  ├── complete_uc(UC-001)
  └── git pull main

UC-002: UI Staff List
  ├── start_uc(UC-002)
  ├── git checkout -b feature/staff-ui-list
  ├── Stitch designs → code
  ├── VEG images → Canva MCP
  ├── VEG motion → Framer Motion
  ├── AG-08: GO ✅
  ├── AG-09b: ACCEPTED ✅
  ├── gh pr create + auto-merge
  ├── complete_uc(UC-002)
  └── git pull main

No mas UCs → move_us(US-01, "done") + delivery report
```

### 4. Review (si no auto-merge)

La PR incluye:
- Resumen del plan
- Cambios por fase
- Acceptance evidence (tabla AC-XX con status y screenshots)
- AG-08 verdict + AG-09b verdict
- Test plan con checklist
- VEG images status

---

## Uso en Proyecto Existente

### Opcion A: Instalacion manual

```bash
# 1. Instalar skills + hooks
cd ~/specbox-engine && ./install.sh

# 2. Copiar CLAUDE.md template
cp ~/specbox-engine/templates/CLAUDE.md.template ./CLAUDE.md
# Editar placeholders

# 3. Copiar agentes necesarios
mkdir -p .claude/agents
cp ~/specbox-engine/agents/{orchestrator,feature-generator,qa-validation}.md .claude/agents/

# 4. Audit
/optimize-agents audit
```

### Opcion B: Onboarding automatico (via MCP)

```
onboard_project("/path/to/project", "mi-proyecto")
```

Auto-detecta stack, genera CLAUDE.md, configura hooks, crea baseline.

### Documentacion

| Documento | Contenido |
|-----------|-----------|
| [docs/getting-started.md](docs/getting-started.md) | Guia de inicio rapido |
| [docs/commands.md](docs/commands.md) | Referencia de Skills |
| [docs/agent-teams.md](docs/agent-teams.md) | Orquestacion multi-agente |
| [docs/architecture.md](docs/architecture.md) | Guia de arquitectura multi-stack |

---

## Configuracion por Proyecto

### `.claude/project-config.json` (RECOMENDADO)

```json
{
  "trello": {
    "boardId": "ID_DEL_BOARD"
  },
  "stitch": {
    "projectId": "ID_PROYECTO_STITCH",
    "deviceType": "DESKTOP",
    "modelId": "GEMINI_3_PRO"
  },
  "veg": {
    "image_provider": {
      "primary": "canva",
      "fallback": "lansespirit",
      "maxImagesPerScreen": 5
    }
  }
}
```

> **Por que no `settings.local.json`?** Claude Code valida el schema de `settings.local.json` y rechaza campos custom como `trello` o `stitch`. Usar `project-config.json` evita este problema.

---

## Actualizacion

```bash
cd ~/specbox-engine
git pull
./install.sh
```

Los symlinks se actualizan automaticamente. Ejecuta `/optimize-agents audit` en tus proyectos para verificar compatibilidad.

### Version Matrix

```
# Ver que proyectos necesitan upgrade
get_version_matrix()

# Upgrade individual
upgrade_project("mi-proyecto")

# Upgrade masivo
upgrade_all_projects()
```

---

## Filosofia

1. **Consistencia > Velocidad** — Mejor hacer las cosas bien que rapido
2. **Documentacion ejecutable** — Los Skills SON la documentacion
3. **Claude como arquitecto critico** — Cuestiona, no complace
4. **Escalable desde dia 1** — Multi-stack, multi-servicio, multi-agente
5. **Autopilot con control** — `/implement` automatiza con acceptance evidence para review humano
6. **Enforcement > Documentacion** — Los HARD BLOCKS previenen violaciones, no las advertencias (v4.0.1)
7. **Calidad visual no negociable** — VEG Pilar 1 exige imagenes reales, no placeholders (v4.0.1)
8. **Trazabilidad innegociable** — Pipeline Integrity impide escribir codigo sin UC activo (v5.7.0)
9. **Mecanico > Instruccional** — Todo lo mandatory se enforce por hooks BLOQUEANTES, no por prompts (v5.19.0)

---

## Licencia

> **Este proyecto es source-available, no open source.**

SpecBox Engine se distribuye bajo la [Business Source License 1.1](LICENSE).

Puedes ver, estudiar y evaluar el codigo libremente. Puedes contribuir mejoras via Pull Request. Pero **el uso en produccion o con fines comerciales requiere un acuerdo de licencia** con el autor.

Comparto mi trabajo porque creo en la transparencia y en construir confianza. Pero compartir no es regalar — si SpecBox te aporta valor en tu negocio, hablemos para que ambos ganemos.

Mas informacion en [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) o contacta en **jesus@embed.build**.

---

v5.25.0 | 2026-04-17 | JPS Developer

---

<a id="english-version"></a>

# English Version

<p align="center">
  <img src=".github/assets/Logo SpecBox.png" alt="SpecBox Engine" width="280" />
</p>

<h1 align="center">SpecBox Engine v5.25.0 — Stripe Connect</h1>

<p align="center">
  <strong>SpecBox Engine by JPS</strong> — An agentic programming system for Claude Code.
</p>

Unified monorepo containing auto-discoverable Agent Skills, quality hooks, multi-stack architecture patterns, agent templates, MCP server with 138 tools, embedded dashboard (Sala de Maquinas), and spec-driven pipeline with Trello/Plane/FreeForm for professional development with Claude Code.

**New in v5.25.0**: new skill [`/stripe-connect`](.claude/skills/stripe-connect/SKILL.md) — scaffolds a complete Stripe Connect marketplace integration (Express + Direct charges + embedded subscriptions) in Supabase + React/Flutter projects with a single command. See [docs/skills/stripe-connect.md](docs/skills/stripe-connect.md).

---

## Table of Contents

- [Quick Start](#quick-start-en)
- [Full Development Flow](#full-development-flow)
- [Skills (Commands)](#skills-commands)
- [Agent System](#agent-system)
- [Supported Stacks](#supported-stacks)
- [Infrastructure Services](#infrastructure-services)
- [Quality Gate System](#quality-gate-system-en)
- [Hooks System](#hooks-system-en)
- [Self-Healing Protocol](#self-healing-protocol-en)
- [VEG — Visual Experience Generation](#veg-en)
- [Multi-Backend: Trello + Plane + FreeForm](#multi-backend-en)
- [Spec-Driven Pipeline](#spec-driven-pipeline-en)
- [Hardened Autopilot Guards](#hardened-autopilot-guards)
- [MCP Server](#mcp-server-en)
- [Sala de Maquinas (Dashboard)](#dashboard-en)
- [Google Stitch MCP](#stitch-en)
- [Context Engineering](#context-engineering-en)
- [Templates for New Projects](#templates-en)
- [Repository Structure](#repo-structure-en)
- [Example: Full Flow](#example-en)
- [Using in Existing Projects](#existing-projects-en)
- [Project Configuration](#project-config-en)
- [Upgrading](#upgrading-en)
- [Philosophy](#philosophy-en)
- [License](#license-en)

---

<a id="quick-start-en"></a>

## Quick Start

```bash
# 1. Clone
git clone <repo-url> ~/specbox-engine
cd ~/specbox-engine

# 2. Install skills + hooks + commands globally
./install.sh

# 3. Verify skills
ls -la ~/.claude/skills/
# You should see: prd, plan, implement, adapt-ui, optimize-agents, quality-gate,
# explore, feedback, check-designs, visual-setup, acceptance-check, quickstart,
# remote, release, compliance (15 skills)

# 4. Verify hooks
ls -la ~/.claude/hooks/
# You should see: 20 hooks .mjs + lib/ with 4 shared modules

# 5. Start MCP server (optional — for telemetry and dashboard)
pip install -e .
specbox-engine
```

Skills are auto-discovered when relevant. Hooks run automatically via Claude Code.

---

## Full Development Flow

```
/prd ──────────> PRD + Work Item (Trello/Plane)
                   │
                   │  Documents requirements, US/UC/AC,
                   │  audience, VEG, NFRs.
                   │  Definition Quality Gate rejects
                   │  vague or untestable criteria.
                   │
                   ▼
/plan ─────────> Technical plan + Stitch designs (HTML) + VEG
                   │
                   │  Breaks into phases, analyzes UI,
                   │  generates Stitch MCP designs,
                   │  generates VEG (images/motion/design),
                   │  saves to doc/plans/ + doc/design/
                   │
                   ▼
/implement ────> Autopilot: branch + code + QA + Acceptance Gate + PR
                   │
                   │  Creates feature/ branch, executes phases,
                   │  design-to-code, generates VEG images,
                   │  injects motion, tests, AG-08 audit,
                   │  AG-09a acceptance tests, AG-09b validation,
                   │  creates PR with acceptance evidence.
                   │
                   ▼
               Sequential merge → pull main → next UC
```

### Spec-Driven Flow (Trello / Plane)

```
/prd ──> PRD + Board/Project (US/UC/AC cards/work-items)
           │
/plan ──> Technical plan + Stitch + VEG
           │  (attaches plan as PDF evidence to the US)
           │
/implement US-01 ──> Autopilot per UC:
           │
           ├── find_next_uc → UC-001 (Ready)
           │   ├── start_uc(UC-001) → In Progress
           │   ├── git checkout -b feature/...
           │   ├── Implement phases
           │   ├── AG-08 + AG-09a + AG-09b
           │   ├── gh pr create
           │   ├── Auto-merge (if GO + ACCEPTED)
           │   ├── complete_uc(UC-001) → Done
           │   └── git pull main
           │
           ├── find_next_uc → UC-002 (Ready)
           │   ├── start_uc(UC-002) → In Progress
           │   ├── ... (same cycle, new branch)
           │   └── git pull main
           │
           └── No more UCs → move_us(US-01, "done")
```

### Support Commands

| Command | Purpose |
|---------|---------|
| `/adapt-ui` | Scans project widgets/components, generates UI mapping |
| `/optimize-agents` | Audits and optimizes the agentic system (score /100) |
| `/quality-gate` | Adaptive quality gates with auditable evidence |
| `/explore` | Read-only codebase exploration |
| `/feedback` | Captures manual testing feedback, blocks merge if unresolved |

---

## Skills (Commands)

> Since v3.0, commands were migrated to Agent Skills with YAML frontmatter, auto-discovery, context isolation, and hooks. Files in `commands/` are kept as legacy reference.

### `/prd` — Generate PRD

Generates a structured Product Requirements Document with US/UC/AC hierarchy.

```
/prd "title" "requirements description"
```

**What it does:**
1. Detects PRD type (new feature or refactor)
2. Gathers info: features, UI interactions, criteria
3. Generates PRD with structured template (US-XX, UC-XXX, AC-XX)
4. **Definition Quality Gate**: Rejects vague or untestable criteria
5. Detects audience and generates VEG Readiness
6. Creates Work Items in Trello or Plane with US/UC/AC cards
7. Attaches PRD as PDF evidence to the US

### `/plan` — Generate Implementation Plan

Generates technical plan with UI analysis, Stitch designs, and VEG.

```
/plan US-01                    # From Trello/Plane User Story
/plan PROYECTO-42              # From Plane work item
/plan "description"            # From direct text
```

### `/implement` — Implementation Autopilot

Reads a plan and executes the full implementation process autonomously.

```
/implement US-01                    # Executes all UCs in sequence
/implement UC-001                   # Executes a single UC
/implement plan_name                # Searches doc/plans/{name}_plan.md
/implement doc/plans/my_plan.md     # Direct path
/implement                          # Lists plans and asks
```

**Internal flow:**

| Step | Description | Enforcement |
|------|-------------|-------------|
| 0 | Load and validate plan | — |
| 0.1a | If Trello/Plane: load US/UC, `start_uc` | — |
| 0.5 | Pre-flight: working tree, branch, fetch | HARD BLOCK |
| **0.5b** | **Anti-main guard** | **FATAL ERROR** (v4.0.1) |
| **0.5c** | **start_uc validation** | **FATAL ERROR** (v4.0.1) |
| 1 | Create feature/ branch | — |
| 2 | Sub-agent orchestration | — |
| 3 | Generate Stitch designs (if missing) | — |
| 3.5 | Generate VEG images (if active) | Cost warning |
| **3.5.5** | **CSS placeholder prohibition** | **RULE** (v4.0.1) |
| 4 | Design-to-code + motion | — |
| 5 | Execute plan phases | Lint gates |
| 6 | Integration | Build check |
| 7 | QA + Acceptance Gate | AG-08, AG-09a/b |
| 8 | Create PR | — |
| **8.5.0** | **Pre-merge validation** | **HARD BLOCK** (v4.0.1) |
| 8.5 | Sequential merge + next UC | Auto-merge conditions |

### `/adapt-ui` — UI Component Mapping

Scans widgets/components, detects framework, categorizes by type, detects design tokens, generates `.claude/ui-adapter.md`.

### `/optimize-agents` — Audit Agentic System

Evaluates 6 dimensions (100 points): Documentation Sync, Validation Strategy, Model Optimization, Team Coordination, Deprecation Hygiene, Agent Teams Readiness.

### `/quality-gate` — Adaptive Quality Gates

Policies: zero-tolerance lint, ratchet coverage, no-regression tests.

### `/explore` — Read-Only Exploration

Read-only codebase exploration in fork mode with Explore agent.

### `/feedback` — Manual Testing Feedback

Creates GitHub issues, links to AC-XX from PRD, blocks merge if unresolved.

---

### `/stripe-connect` — Stripe Connect marketplace scaffolder (v5.25.0)

Scaffolds a complete Stripe Connect marketplace integration (Express + Direct charges + embedded subscriptions via Payment Element/Sheet + Apple/Google Pay) in Supabase + React/Flutter projects in a single command. Embedded-only by design — never redirects to stripe.com.

**Generates:** US-SPONSORSHIP + 12 UCs (UC-301..UC-312) in the project's spec backend, 5 Supabase Edge Functions + 4 SQL migrations with RLS, frontend templates (React 4 files or Flutter 7 files), `stripe-safety-guard.mjs` hook (blocks webhooks without signature/idempotency, hosted Checkout, sk_live hardcoded, Payment Links), 6 Stitch screen designs if VEG is configured, 12 Gherkin `.feature` acceptance tests with `stripe trigger` + test clocks, parameterized docs, and wires the official Stripe MCP.

**v1 scope:** Supabase + React/Flutter + Connect Express + Direct charges + subscriptions. Other backends and SaaS vanilla (`/stripe` sibling) reserved for v2.

See [docs/skills/stripe-connect.md](docs/skills/stripe-connect.md) for the complete flow.

---

## Agent System

| ID | Agent | Role | When |
|----|-------|------|------|
| — | **Orchestrator** | Coordinator. NEVER writes code. | Always |
| AG-01 | Feature Generator | Generates full structure per stack | Logic phase |
| AG-02 | UI/UX Designer | Interfaces, responsiveness, VEG Motion | UI phase |
| AG-03 | DB Specialist | Supabase, Neon, Firebase, migrations | DB phase |
| AG-04 | QA Validation | Unit tests, 85%+ coverage | QA phase |
| AG-05 | n8n Specialist | Automation workflows | If n8n present |
| AG-06 | Design Specialist | Google Stitch MCP, VEG enrichment | Designs |
| AG-07 | Apps Script Specialist | Google Apps Script (clasp, V8) | GAS projects |
| AG-08 | Quality Auditor | Independent verification, GO/NO-GO | Post-QA |
| AG-09a | Acceptance Tester | Generates .feature + step definitions | Step 7.5 |
| AG-09b | Acceptance Validator | Validates compliance, ACCEPTED/REJECTED | Step 7.7 |
| AG-10 | Developer Tester | Processes human feedback, GitHub issues | /feedback |

### Strict Orchestrator Isolation

The Orchestrator (main Claude thread) **NEVER writes code directly**:

| Action | Orchestrator | Sub-agent |
|--------|:-----------:|:----------:|
| Read source code | No | Yes |
| Write/edit code | No | Yes |
| Run lint/tests/build | No | Yes |
| Generate Stitch designs | No | AG-06 |
| Read plan (once) | Yes | — |
| Create branch and commits | Yes | — |
| Create PR | Yes | — |
| Manage Trello/Plane state | Yes | — |
| Decide self-healing | Yes | (delegates fix) |

---

## Supported Stacks

| Stack | Version | Architecture |
|-------|---------|-------------|
| **Flutter** | 3.38+ | Clean Architecture, BLoC+Freezed, Responsive (3 layouts), DataSource |
| **React** | 19.x | App Router / SPA, Server Components, TanStack Query, Tailwind CSS |
| **Python** | 3.12+ | FastAPI, SQLAlchemy 2 async, Pydantic v2, Repository pattern |
| **Google Apps Script** | V8 | clasp + TypeScript + esbuild, batch operations, PropertiesService |

Each stack has its folder in `architecture/` with overview, folder-structure, patterns, testing-strategy, and e2e-testing.

---

## Infrastructure Services

| Service | Folder | Content |
|---------|--------|---------|
| **Supabase** | `infra/supabase/` | MCP tools, RLS policies, migrations, Realtime, DataSource |
| **Neon** | `infra/neon/` | Connection pooling, branching, Drizzle ORM, serverless |
| **Stripe** | `infra/stripe/` | Webhooks, Checkout, Subscriptions, Customer Portal |
| **Firebase** | `infra/firebase/` | Firestore rules, Auth, Cloud Functions, Storage |
| **n8n** | `infra/n8n/` | Workflow patterns, triggers, webhooks, error handling |

---

<a id="quality-gate-system-en"></a>

## Quality Gate System

Automatic quality gates between each `/implement` phase, with persistent evidence and independent auditor (AG-08).

### Policies

| Metric | Policy | Description |
|--------|--------|-------------|
| **Lint** | zero-tolerance | 0 errors / 0 warnings / 0 info. BLOCKING |
| **Coverage** | ratchet | Never decreases. Progressively increases |
| **Tests** | no-regression | Never fewer passing. Failing = 0 |
| **Architecture** | ratchet | Never more violations |

---

<a id="hooks-system-en"></a>

## Hooks System

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| `pre-commit-lint.mjs` | PostToolUse (git commit) | **BLOCKING**: fails commit if lint has errors |
| `on-session-end.mjs` | Stop | Logs telemetry to .quality/logs/ + Engram |
| `implement-checkpoint.mjs` | Manual (/implement) | Saves phase progress for resume |
| `implement-healing.mjs` | Manual (/implement) | Logs self-healing events |
| `post-implement-validate.mjs` | Manual (/implement) | Detects baseline regression |

---

<a id="self-healing-protocol-en"></a>

## Self-Healing Protocol

When `/implement` encounters errors, the system attempts auto-recovery:

| Level | Action | Example |
|-------|--------|---------|
| **1: Auto-Fix** | Runs stack auto-fix | `dart fix --apply`, `eslint --fix`, `ruff check --fix` |
| **2: Diagnostic** | Analyzes error, applies specific fix | Missing import, wrong type |
| **3: Rollback** | Reverts phase, retries from scratch | `git stash` + fresh attempt |
| **4: Human** | Generates error report and pauses | `.quality/evidence/{feature}/error_report.md` |

All attempts are logged in `.quality/evidence/{feature}/healing.jsonl`.

---

<a id="veg-en"></a>

## VEG — Visual Experience Generation

System with 3 modes for generating visual decisions (images, motion, design) tailored to the project audience.

### Modes

| Mode | Name | When |
|------|------|------|
| 1 | **Uniform** | Homogeneous audience (same VEG for all) |
| 2 | **Per Profile** | Variants per user profile |
| 3 | **Per ICP+JTBD** | Customized per ICP with rational and emotional JTBD |

### 3 Pillars

| Pillar | Content | Integration |
|--------|---------|-------------|
| **Pillar 1: Images** | Type, mood, palette, per-section prompts | Step 3.5 generates with MCP (Canva/Freepik/etc.) |
| **Pillar 2: Motion** | Level (1-3), page enter, scroll reveal, hover | Step 4 injects catalog into AG-02 |
| **Pillar 3: Design** | Density, whitespace, typography, CTA, shadows | Step 3 enriches Stitch prompts |

### 6 Archetypes

Corporate, Startup, Creative, Consumer, Gen-Z, Government — derived from target audience. Defined in `doc/templates/veg-archetypes.md`.

### Image Generation Providers

| Provider | Cost | Quality |
|----------|------|---------|
| **Canva** (Pro/Premium) | €0 extra | High (Magic Media) |
| Freepik (Mystic) | Per plan | High (stock + AI) |
| lansespirit (OpenAI/Gemini) | $0.02-0.19/img | Very high |

**If MCP unavailable**: Creates `PENDING_IMAGES.md` with prompts for manual generation.

---

<a id="multi-backend-en"></a>

## Multi-Backend: Trello + Plane + FreeForm

Since v4.1.0, the engine supports multiple interchangeable project managers. All 3 backends implement the same `SpecBackend` interface (25 methods), so all MCP tools work identically with any of them.

### Multi-Backend Architecture

```
spec_driven.py (21 tools, backend-agnostic)
        │
        ▼
  SpecBackend ABC ─── 25 unified methods
   ┌────┼────────────┐
   │    │             │
TrelloBackend  PlaneBackend  FreeformBackend
   │              │              │
TrelloClient   PlaneClient   JSON + Markdown local
(httpx+retry)  (httpx+retry)  (pathlib, no API)
```

### Backend Configuration

The backend is selected at authentication time. Only one is active per session. All MCP tools (`setup_board`, `find_next_uc`, `mark_ac`, etc.) work identically with any backend:

**Trello** — `set_auth_token(token="TRELLO_TOKEN", api_key="TRELLO_KEY")`

**Plane (cloud or self-hosted)** — `set_auth_token(token="PLANE_API_KEY", backend_type="plane", base_url="https://app.plane.so", workspace_slug="my-ws")`

> For self-hosted Plane (CE), change `base_url` to your domain (e.g. `https://plane.mycompany.com`).

**FreeForm (local, no API)** — `set_auth_token(api_key="freeform", token="", backend_type="freeform", root_path="doc/tracking")`

### FreeForm Backend (v5.8.0)

No-API backend for personal projects or where Trello/Plane is overkill. Stores everything as local JSON and auto-generates progress Markdowns:

```
doc/tracking/
├── boards/{board_id}/
│   ├── config.json          ← BoardConfig
│   ├── items.json           ← All items (US/UC/AC)
│   ├── comments/{item_id}.jsonl
│   └── attachments/{item_id}/
└── progress/
    ├── README.md            ← Overview with US/UC tables
    └── UC-XXX.md            ← Detail per UC with ACs and status
```

Pipeline Integrity hooks (v5.7.0) work identically with FreeForm — they read `.quality/active_uc.json` which is backend-agnostic.

### Migration Tools

| Tool | Purpose |
|------|---------|
| `migrate_preview` | Preview migration (dry run) |
| `migrate_project` | Migrate US/UC/AC between backends |
| `migrate_status` | Current migration status |
| `set_migration_target` | Configure target backend |
| `switch_backend` | Switch active session backend |

Migration is idempotent: uses `external_source` + `external_id` to prevent duplicates.

---

<a id="spec-driven-pipeline-en"></a>

## Spec-Driven Pipeline

Specification-based pipeline with Trello, Plane, or FreeForm as source of truth.

### Hierarchy

```
Board/Project
├── US-01: User Story (card/work-item in workflow list)
│   ├── UC-001: Use Case (child card / sub-work-item)
│   │   ├── AC-01: Acceptance Criterion (checklist item / sub-item)
│   │   ├── AC-02: ...
│   │   └── AC-03: ...
│   ├── UC-002: ...
│   └── UC-003: ...
├── US-02: ...
└── ...
```

### Workflow States

```
Backlog → Ready → In Progress → Review → Done
```

### MCP Tools (backend-agnostic)

| Tool | Purpose |
|------|---------|
| `setup_board` | Create board/project with workflow lists |
| `import_spec` | Import US/UC/AC from JSON |
| `get_us` / `list_us` | Read User Stories |
| `get_uc` / `list_uc` | Read Use Cases |
| `find_next_uc` | Next UC in Ready |
| `start_uc` | Move UC to In Progress |
| `complete_uc` | Move UC to Done |
| `move_us` / `move_uc` | Change state |
| `mark_ac` / `mark_ac_batch` | Mark acceptance criteria |
| `attach_evidence` | Attach PDF evidence |
| `get_evidence` | Search attached evidence |
| `get_board_status` | Full board/project status |
| `get_delivery_report` | Delivery report |

---

## Hardened Autopilot Guards (v4.0.1+)

HARD BLOCKS that prevent the most critical protocol violations during autonomous implementation:

| Guard | What it validates | If it fails |
|-------|-------------------|-------------|
| **Step 0.5b: Anti-main** | Not implementing on main/master | FATAL ERROR — stops immediately |
| **Step 0.5c: start_uc** | start_uc was called before implementing | FATAL ERROR — call start_uc or stop |
| **Step 0.5d: Design Gate** (v4.2.0) | Stitch HTMLs exist for UC screens | BLOCKED — run /plan first |
| **Step 3.5.5: CSS placeholders** | No CSS gradients/SVG as image substitutes | RULE — only real images |
| **Step 8.5.0: Pre-merge** | feature/ branch + open PR + UC in_progress + no pending images | HARD BLOCK per check |

---

<a id="mcp-server-en"></a>

## MCP Server

Unified MCP server with 138 tools in a single endpoint.

### Architecture

```
server/
├── server.py              # FastMCP main server
├── dashboard_api.py       # REST API for dashboard
├── auth_gateway.py        # Per-session credentials (Trello + Plane)
├── spec_backend.py        # SpecBackend ABC (23 methods)
├── trello_client.py       # Async httpx with retry (Trello)
├── board_helpers.py       # Card parsing, custom fields (Trello)
├── backends/              # Multi-backend implementations
│   ├── trello_backend.py  #   TrelloBackend (SpecBackend wrapper)
│   ├── plane_backend.py   #   PlaneBackend (SpecBackend implementation)
│   └── plane_client.py    #   PlaneClient (httpx async, X-Api-Key)
├── models.py              # Pydantic models (US, UC, AC)
├── pdf_generator.py       # Markdown → PDF
├── tools/                 # 11 tool modules
│   ├── engine.py          # 3 tools: version, status, rules
│   ├── plans.py           # 3 tools: list, read, architecture
│   ├── quality.py         # 4 tools: baseline, logs, evidence
│   ├── skills.py          # 2 tools: list, read
│   ├── features.py        # 7 tools: in-progress, designs
│   ├── telemetry.py       # 8 tools: sessions, events, dashboard
│   ├── hooks.py           # 3 tools: list, config, source
│   ├── onboarding.py      # 10+ tools: register, onboard, upgrade
│   ├── state.py           # 20 tools: report, checkpoint, healing
│   ├── spec_driven.py     # 21 tools: backend-agnostic (US/UC/AC)
│   └── migration.py       # 5 tools: Trello ↔ Plane migration
├── resources/             # 8 MCP Resources
└── dashboard/             # React 19 + Vite frontend
```

### Running

```bash
# Install dependencies
pip install -e .

# Run server
specbox-engine

# Docker
docker compose up
```

**Dependencies**: Python 3.12+, FastMCP 3.0.0+, httpx, pydantic, fpdf2, structlog.

---

<a id="dashboard-en"></a>

## Sala de Maquinas (Dashboard)

Embedded dashboard (React 19 + Vite) that **each user deploys with their own MCP server instance**. The dashboard shows data from **your** projects, stored locally in your `STATE_PATH`. There is no shared central server — each installation is independent and private.

**Production security:**

| Variable | Recommended value | Description |
|----------|-------------------|-------------|
| `DASHBOARD_TOKEN` | Long secret token | **Required**. Without token, dashboard is accessible without authentication |
| `DASHBOARD_CORS_ORIGIN` | `https://your-domain.com` | Restricts which origins can make requests. Empty = same-origin only |

---

<a id="stitch-en"></a>

## Google Stitch MCP

Automatic UI design generation via Google Stitch. Since v5.6.0, the Engine includes a **Stitch MCP Proxy** — 13 tools that cover all 12 native Stitch tools + per-project API Key management. This enables claude.ai users to access Stitch without a separate OAuth connector.

| Engine Tool | Stitch Native | Description |
|-------------|---------------|-------------|
| `stitch_set_api_key` | — | Configure API Key per project |
| `stitch_create_project` | `create_project` | Create workspace |
| `stitch_list_projects` | `list_projects` | List projects |
| `stitch_get_project` | `get_project` | Project details |
| `stitch_list_screens` | `list_screens` | List screens |
| `stitch_get_screen` | `get_screen` | Screen metadata |
| `stitch_fetch_screen_code` | `fetch_screen_code` | Download raw HTML |
| `stitch_fetch_screen_image` | `fetch_screen_image` | Hi-res screenshot (base64) |
| `stitch_generate_screen` | `generate_screen_from_text` | Generate screen from prompt |
| `stitch_edit_screen` | `edit_screens` | Edit existing screen |
| `stitch_generate_variants` | `generate_variants` | Variants (REFINE/EXPLORE/REIMAGINE) |
| `stitch_extract_design_context` | `extract_design_context` | Extract Design DNA |
| `stitch_build_site` | `build_site` | Multi-page site assembly |

**Rules:** Always Light Mode. One screen at a time. `GEMINI_3_PRO` for complex, `GEMINI_3_FLASH` for simple.

---

<a id="context-engineering-en"></a>

## Context Engineering

Context management system to keep the orchestrator within limits.

| Operation | Max budget |
|-----------|-----------|
| Implementation phase | ~20,000 tokens (v5.24.0: expanded for Opus 4.7) |
| Sub-agent summary | Max 5 lines |
| Plan (single read) | No limit |
| Checkpoint | ~500 tokens |

**Pruning rules:** Aggressive pruning after each phase, external persistence (checkpoints, Engram), compact summaries by default, fork isolation for sub-agents.

---

<a id="templates-en"></a>

## Templates for New Projects

| Template | Purpose |
|----------|---------|
| `CLAUDE.md.template` | Claude Code instructions + Engram + VEG |
| `settings.json.template` | Permissions, hooks, MCP config |
| `team-config.json.template` | Agent Teams with all roles |
| `quality-baseline.json.template` | Initial quality baseline |

### Automatic Onboarding

```
# Via MCP
onboard_project(path, name)   # Auto-detects stack, generates CLAUDE.md, configures hooks
upgrade_project(name)          # Upgrades to latest engine template
```

---

<a id="repo-structure-en"></a>

## Repository Structure

```
specbox-engine/
├── CLAUDE.md                          # Engine instructions for Claude
├── ENGINE_VERSION.yaml                # Version 4.1.0, stacks, services, changelog
├── README.md                          # This file
├── CHANGELOG.md                       # Change history since v1.0.0
├── LICENSE                            # MIT
├── install.sh                         # Skills + hooks + commands installer
├── pyproject.toml                     # Python project config (FastMCP 3.0.0+)
├── Dockerfile                         # Multi-stage (Node 20 + Python 3.12)
├── docker-compose.yml                 # Docker Compose config
│
├── .claude/                           # Claude Code configuration
│   ├── settings.json                  #   Hooks config
│   ├── skills/                        #   8 Agent Skills
│   └── hooks/                         #   6 Hook scripts
│
├── server/                            # MCP Server + Dashboard
│   ├── server.py                      #   FastMCP main
│   ├── spec_backend.py                #   SpecBackend ABC (23 methods)
│   ├── backends/                      #   Multi-backend layer
│   │   ├── trello_backend.py         #     TrelloBackend
│   │   ├── plane_backend.py          #     PlaneBackend
│   │   └── plane_client.py           #     PlaneClient
│   ├── tools/                         #   24 modules, 138 tools
│   └── dashboard/                     #   Sala de Maquinas (React 19 + Vite)
│
├── agents/                            # 12 Agent templates (AG-01 to AG-10)
├── agent-teams/                       # Native Agent Teams (Claude Code)
├── architecture/                      # Patterns per stack (15 docs)
├── design/                            # Google Stitch MCP integration
├── infra/                             # Patterns per service (5 services)
├── templates/                         # Templates for new projects
├── rules/                             # Global rules
├── doc/                               # Internal documentation
├── docs/                              # Public documentation
└── tests/                             # 171+ unified tests
```

---

<a id="example-en"></a>

## Example: Full Flow

### 1. Create PRD + Trello/Plane Board

```
> /prd "Staff management system" "We need a screen to manage
  staff: view list, create, edit, delete.
  Each member has name, email, role and active/inactive status."
```

**Result:**
- `doc/prd/PRD_staff_management.md` with US-01, UC-001..003, AC-01..09
- Board/Project with US and UC cards created
- Definition Quality Gate: all ACs verified as testable

### 2. Generate Plan + Designs

```
> /plan US-01
```

**Result:**
- `doc/plans/staff_management_plan.md` with 5 phases
- `doc/design/staff_management/*.html` (Stitch screens)
- `doc/veg/staff_management/veg-*.md` (VEG artifacts)
- Plan attached as PDF to the US

### 3. Implement

```
> /implement US-01
```

**Result (automatic, per UC):**

```
UC-001: CRUD Backend
  ├── start_uc(UC-001)
  ├── git checkout -b feature/staff-crud-backend
  ├── Phase 1: Supabase tables + RLS
  ├── Phase 2: models + repository
  ├── AG-08: GO ✅
  ├── AG-09b: ACCEPTED ✅
  ├── gh pr create + auto-merge
  ├── complete_uc(UC-001)
  └── git pull main

UC-002: UI Staff List
  ├── start_uc(UC-002)
  ├── git checkout -b feature/staff-ui-list
  ├── Stitch designs → code
  ├── VEG images → Canva MCP
  ├── VEG motion → Framer Motion
  ├── AG-08: GO ✅
  ├── AG-09b: ACCEPTED ✅
  ├── gh pr create + auto-merge
  ├── complete_uc(UC-002)
  └── git pull main

No more UCs → move_us(US-01, "done") + delivery report
```

---

<a id="existing-projects-en"></a>

## Using in Existing Projects

### Option A: Manual installation

```bash
# 1. Install skills + hooks
cd ~/specbox-engine && ./install.sh

# 2. Copy CLAUDE.md template
cp ~/specbox-engine/templates/CLAUDE.md.template ./CLAUDE.md
# Edit placeholders

# 3. Audit
/optimize-agents audit
```

### Option B: Automatic onboarding (via MCP)

```
onboard_project("/path/to/project", "my-project")
```

Auto-detects stack, generates CLAUDE.md, configures hooks, creates baseline.

---

<a id="project-config-en"></a>

## Project Configuration

### `.claude/project-config.json` (RECOMMENDED)

```json
{
  "trello": {
    "boardId": "BOARD_ID"
  },
  "plane": {
    "projectId": "PROJECT_ID",
    "baseUrl": "https://app.plane.so",
    "workspaceSlug": "my-workspace"
  },
  "stitch": {
    "projectId": "STITCH_PROJECT_ID",
    "deviceType": "DESKTOP",
    "modelId": "GEMINI_3_PRO"
  },
  "veg": {
    "image_provider": {
      "primary": "canva",
      "fallback": "lansespirit",
      "maxImagesPerScreen": 5
    }
  }
}
```

> **Why not `settings.local.json`?** Claude Code validates the `settings.local.json` schema and rejects custom fields like `trello` or `stitch`. Using `project-config.json` avoids this problem.

---

<a id="upgrading-en"></a>

## Upgrading

```bash
cd ~/specbox-engine
git pull
./install.sh
```

Symlinks are updated automatically. Run `/optimize-agents audit` in your projects to verify compatibility.

### Version Matrix

```
# Check which projects need upgrading
get_version_matrix()

# Individual upgrade
upgrade_project("my-project")

# Batch upgrade
upgrade_all_projects()
```

---

<a id="philosophy-en"></a>

## Philosophy

1. **Consistency > Speed** — Better to do things right than fast
2. **Executable documentation** — Skills ARE the documentation
3. **Claude as critical architect** — Questions, doesn't please
4. **Scalable from day 1** — Multi-stack, multi-service, multi-agent
5. **Autopilot with control** — `/implement` automates with acceptance evidence for human review
6. **Enforcement > Documentation** — HARD BLOCKS prevent violations, not warnings (v4.0.1)
7. **Non-negotiable visual quality** — VEG Pillar 1 demands real images, not placeholders (v4.0.1)

---

<a id="license-en"></a>

## License

> **This project is source-available, not open source.**

SpecBox Engine is distributed under the [Business Source License 1.1](LICENSE).

You can view, study, and evaluate the code freely. You can contribute improvements via Pull Request. But **production or commercial use requires a license agreement** with the author.

I share my work because I believe in transparency and building trust. But sharing is not giving away — if SpecBox brings value to your business, let's talk so we both win.

More details at [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md) or contact **jesus@embed.build**.

---

v5.25.0 | 2026-04-17 | JPS Developer
