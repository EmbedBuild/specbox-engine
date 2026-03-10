# SDD-JPS Engine v4.0.3 — Public Release

**Spec-Driven Development Engine by JPS** — Sistema de programacion agentica para Claude Code.

Monorepo unificado que contiene Agent Skills auto-descubribles, hooks de calidad, patrones de arquitectura multi-stack, templates de agentes, MCP server con 73+ tools, dashboard embebido (Sala de Maquinas), y pipeline spec-driven con Trello para desarrollo profesional con Claude Code.

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
- [Spec-Driven Pipeline (Trello)](#spec-driven-pipeline-trello)
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
git clone <repo-url> ~/sdd-jps-engine
cd ~/sdd-jps-engine

# 2. Instalar skills + hooks + commands globales
./install.sh

# 3. Verificar skills
ls -la ~/.claude/skills/
# Deberias ver: prd, plan, implement, adapt-ui, optimize-agents, quality-gate, explore, feedback

# 4. Verificar hooks
ls -la ~/.claude/hooks/
# Deberias ver: pre-commit-lint.sh, on-session-end.sh, implement-checkpoint.sh, etc.

# 5. Iniciar MCP server (opcional — para telemetria y dashboard)
pip install -e .
sdd-jps-engine
```

Las Skills se auto-descubren cuando son relevantes. Los hooks se ejecutan automaticamente por Claude Code.

---

## Flujo Completo de Desarrollo

```
/prd ──────────> PRD + Work Item (Trello)
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

### Flujo Spec-Driven (Trello)

```
/prd ──> PRD + Trello Board (US/UC/AC cards)
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
6. Crea Work Item en Trello con US/UC/AC cards
7. Adjunta PRD como evidencia PDF a la US

**Output:** `doc/prd/PRD_{nombre}.md` + Trello board con cards

**Modos:**
- **Spec-Driven (Trello)**: Enriquece especificacion firmada por cliente
- **Freeform**: Crea PRD desde cero a partir de descripcion

---

### `/plan` — Generar Plan de Implementacion

Genera plan tecnico con analisis UI, diseños Stitch, y VEG.

```
/plan US-01                    # Desde User Story de Trello
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
9. Adjunta plan como evidencia PDF a la US en Trello

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
| 0.1a | Si Trello: cargar US/UC, `start_uc` | — |
| 0.3 | Detectar VEG | — |
| 0.5 | Pre-flight: working tree, rama, fetch | HARD BLOCK |
| **0.5b** | **Guardia anti-main** | **ERROR FATAL** (v4.0.1) |
| **0.5c** | **Validacion start_uc** | **ERROR FATAL** (v4.0.1) |
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
| Gestionar Trello state | ✅ | — |
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
| **Python** | 3.12+ | FastAPI, SQLAlchemy 2 async, Pydantic v2, Repository pattern | 2 docs |
| **Google Apps Script** | V8 | clasp + TypeScript + esbuild, batch operations, PropertiesService | 4 docs |

Cada stack tiene su carpeta en `architecture/` con overview, folder-structure, patterns, testing-strategy, y e2e-testing (Flutter/React).

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
| `pre-commit-lint.sh` | PostToolUse (git commit) | **BLOQUEANTE**: falla commit si lint tiene errores |
| `on-session-end.sh` | Stop | Registra telemetria en .quality/logs/ + Engram |
| `implement-checkpoint.sh` | Manual (/implement) | Guarda progreso de fase para resume |
| `implement-healing.sh` | Manual (/implement) | Registra eventos de self-healing |
| `post-implement-validate.sh` | Manual (/implement) | Detecta regresion de baseline |
| `mcp-report.sh` | Utility | Cliente MCP reutilizable para telemetria remota |

Configuracion en `.claude/settings.json`. Telemetria remota controlada por `DEV_ENGINE_MCP_URL` env var.

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

## Spec-Driven Pipeline (Trello)

Pipeline basado en especificacion con Trello como fuente de verdad.

### Jerarquia

```
Board (proyecto)
├── US-01: User Story (card en lista workflow)
│   ├── UC-001: Use Case (card hija)
│   │   ├── AC-01: Acceptance Criterion (checklist item)
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

### Tools MCP para Trello

| Tool | Proposito |
|------|-----------|
| `setup_board` | Crear board con listas workflow |
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
| `get_board_status` | Estado completo del board |
| `get_delivery_report` | Reporte de entrega |

### Configuracion

En `.claude/project-config.json` (PREFERIDO):

```json
{
  "trello": {
    "boardId": "ID_DEL_BOARD"
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

## Hardened Autopilot Guards (v4.0.1)

La v4.0.1 introduce **HARD BLOCKS** que previenen las violaciones de protocolo mas criticas durante la implementacion autonoma. Estas validaciones detienen el pipeline inmediatamente si se detecta una inconsistencia.

### Paso 0.5b: Guardia anti-main (ERROR FATAL)

```
¿Estamos implementando codigo directamente en main/master?
├── En Paso 0: OK (el Paso 1 creara la rama)
├── En Paso 5+: ❌ ERROR FATAL — PARAR INMEDIATAMENTE
└── Razon: Sin rama feature/ → sin PR → sin acceptance evidence → sin review
```

### Paso 0.5c: Validacion Trello state (ERROR FATAL)

```
¿Se llamo start_uc antes de implementar? (solo Trello spec-driven)
├── SI y status == "in_progress": OK
├── SI pero status incorrecto: Recovery automatico (reintentar start_uc)
└── NO: ❌ ERROR FATAL — llamar start_uc o PARAR
```

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
| 3 | UC en estado `in_progress` (Trello) | Recovery + WARNING |
| 4 | `veg_images_pending == false` | Merge bloqueado, espera usuario |

### Por que estos guards son necesarios

Antes de v4.0.1, estas validaciones eran "soft requirements" — documentadas en el skill pero no validadas en runtime. El agente podia:
- Implementar todo en main sin crear rama
- Crear PR sin haber llamado start_uc
- Auto-merge con imagenes placeholder degradando calidad visual
- Saltarse complete_uc dejando el board Trello inconsistente

Ahora son **HARD BLOCKS** que detienen el pipeline.

---

## MCP Server

Servidor MCP unificado con 73+ tools en un solo endpoint.

### Arquitectura

```
server/
├── server.py              # FastMCP main server
├── dashboard_api.py       # REST API para dashboard
├── auth_gateway.py        # Credenciales per-session
├── trello_client.py       # Async httpx con retry
├── board_helpers.py       # Card parsing, custom fields
├── models.py              # Pydantic models (US, UC, AC)
├── pdf_generator.py       # Markdown → PDF
├── tools/                 # 10 modulos de tools
│   ├── engine.py          # 3 tools: version, status, rules
│   ├── plans.py           # 3 tools: list, read, architecture
│   ├── quality.py         # 4 tools: baseline, logs, evidence
│   ├── skills.py          # 2 tools: list, read
│   ├── features.py        # 7 tools: in-progress, designs
│   ├── telemetry.py       # 8 tools: sessions, events, dashboard
│   ├── hooks.py           # 3 tools: list, config, source
│   ├── onboarding.py      # 10+ tools: register, onboard, upgrade
│   ├── state.py           # 20 tools: report, checkpoint, healing
│   └── spec_driven.py     # 21 tools: Trello domain (US/UC/AC)
├── resources/             # 8 MCP Resources
└── dashboard/             # React 19 + Vite frontend
```

### Ejecucion

```bash
# Instalar dependencias
pip install -e .

# Ejecutar servidor
sdd-jps-engine

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
- Spec-Driven: estado de boards Trello
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

Generacion automatica de diseños UI via Google Stitch.

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
| Fase de implementacion | ~8,700 tokens |
| Resumen de sub-agente | Max 5 lineas |
| Plan (lectura unica) | Sin limite |
| Checkpoint | ~200 tokens |

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
sdd-jps-engine/
├── CLAUDE.md                          # Instrucciones del engine para Claude
├── ENGINE_VERSION.yaml                # Version 4.0.1, stacks, servicios, changelog
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
│   ├── skills/                        #   8 Agent Skills
│   │   ├── prd/SKILL.md              #     PRD generator
│   │   ├── plan/SKILL.md             #     Plan + Stitch + VEG
│   │   ├── implement/SKILL.md        #     Autopilot (1500+ lineas)
│   │   ├── adapt-ui/SKILL.md         #     UI component scanner
│   │   ├── optimize-agents/SKILL.md  #     Agent system auditor
│   │   ├── quality-gate/SKILL.md     #     Quality gates
│   │   ├── explore/SKILL.md          #     Read-only exploration
│   │   └── feedback/SKILL.md         #     Developer feedback
│   └── hooks/                         #   6 Hook scripts
│       ├── mcp-report.sh             #     MCP client helper
│       ├── pre-commit-lint.sh        #     Lint on commit (BLOQUEANTE)
│       ├── on-session-end.sh         #     Session telemetry
│       ├── implement-checkpoint.sh   #     Phase checkpointing
│       ├── implement-healing.sh      #     Healing event logging
│       └── post-implement-validate.sh #    Baseline regression
│
├── server/                            # MCP Server + Dashboard
│   ├── server.py                      #   FastMCP main
│   ├── dashboard_api.py               #   REST API
│   ├── auth_gateway.py                #   Per-session credentials
│   ├── trello_client.py               #   Async Trello client
│   ├── board_helpers.py               #   Card parsing
│   ├── models.py                      #   Pydantic models
│   ├── pdf_generator.py               #   Markdown → PDF
│   ├── tools/                         #   10 modules, 73+ tools
│   │   ├── engine.py                  #     Version, status, rules
│   │   ├── plans.py                   #     Plans management
│   │   ├── quality.py                 #     Quality baselines
│   │   ├── skills.py                  #     Skill discovery
│   │   ├── features.py               #     Feature tracking
│   │   ├── telemetry.py              #     Sessions, events
│   │   ├── hooks.py                   #     Hook config
│   │   ├── onboarding.py             #     Project onboarding
│   │   ├── state.py                   #     State reporting
│   │   └── spec_driven.py            #     Trello domain (21 tools)
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
└── tests/                             # 208 tests unificados
```

---

## Ejemplo: Flujo Completo

### 1. Crear PRD + Board Trello

```
> /prd "Sistema de gestion de staff" "Necesitamos una pantalla para
  gestionar el personal: ver lista, crear, editar, eliminar.
  Cada miembro tiene nombre, email, rol y estado activo/inactivo."
```

**Resultado:**
- `doc/prd/PRD_staff_management.md` con US-01, UC-001..003, AC-01..09
- Board Trello con cards US y UC creadas
- Definition Quality Gate: todos los AC verificados como testables

### 2. Generar Plan + Diseños

```
> /plan US-01
```

**Resultado:**
- `doc/plans/staff_management_plan.md` con 5 fases
- `doc/design/staff_management/*.html` (pantallas Stitch)
- `doc/veg/staff_management/veg-*.md` (VEG artifacts)
- Plan adjunto como PDF a la US en Trello

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
cd ~/sdd-jps-engine && ./install.sh

# 2. Copiar CLAUDE.md template
cp ~/sdd-jps-engine/templates/CLAUDE.md.template ./CLAUDE.md
# Editar placeholders

# 3. Copiar agentes necesarios
mkdir -p .claude/agents
cp ~/sdd-jps-engine/agents/{orchestrator,feature-generator,qa-validation}.md .claude/agents/

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
cd ~/sdd-jps-engine
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

---

## Licencia

MIT

---

v4.0.3 | 2026-03-10 | JPS Developer
