# SpecBox Engine v5.6.0

> **SpecBox Engine by JPS**
> Sistema de programacion agentica para Claude Code.
> Monorepo unificado: engine + MCP server (108+ tools) + Sala de Máquinas + Gherkin BDD.

## Que es este repositorio

Este repositorio es un **monorepo unificado** con el sistema completo de programacion agentica para Claude Code. Incluye:

- **Commands** (`/prd`, `/plan`, `/implement`, `/adapt-ui`, `/optimize-agents`, `/feedback`) — flujo completo de desarrollo
- **Agent Teams** — configuracion para orquestacion multi-agente nativa de Claude Code
- **Architecture** — patrones por stack (Flutter, React, Python, Google Apps Script)
- **Infrastructure** — patrones por servicio (Supabase, Neon, Stripe, Firebase, n8n)
- **Design** — integracion con Google Stitch MCP para diseño UI + VEG (Visual Experience Generation)
- **Templates** — CLAUDE.md, settings.json, team-config para nuevos proyectos
- **Agents** — templates genericos de roles especializados
- **Server** — MCP server unificado (108+ tools) + Sala de Máquinas dashboard (React 19)
- **Spec-Driven** — Backend-agnostic tools para US/UC/AC (21 tools + 5 migration, Trello y Plane)
- **Gherkin BDD** — Acceptance testing en español con frameworks por stack

## Stack soportado

| Stack | Version | Estado |
|-------|---------|--------|
| Flutter | 3.38+ | Completo |
| React | 19.x | Completo |
| Python (FastAPI) | 3.12+ | Completo |
| Google Apps Script | V8 | Completo |
| Supabase | 2.x | Completo |
| Neon (Postgres serverless) | - | Completo |
| Stripe | latest | Completo |
| Firebase | latest | Completo |
| n8n | latest | Completo |
| Google Stitch MCP | - | Completo |
| VEG (Visual Experience Generation) | v3.9 | Completo |

## Gestores de proyecto (Spec-Driven)

| Gestor | Auth | Estado |
|--------|------|--------|
| Trello | API key + token | Completo |
| Plane | API key + base_url + workspace_slug | Completo |

Ambos gestores se usan de forma identica gracias a la abstraccion `SpecBackend`.
Los 21 tools de spec-driven funcionan con cualquier backend configurado por proyecto.
Plane funciona tanto self-hosted (CE) como cloud — solo cambia el `base_url`.
Migracion bidireccional disponible via `migrate_preview` / `migrate_project`.

## Instalacion

```bash
git clone <repo-url> specbox-engine
cd specbox-engine
./install.sh
```

Esto instala Skills en `~/.claude/skills/`, hooks en `~/.claude/hooks/` y commands en `~/.claude/commands/`.

## Flujo de desarrollo

```
Spec-Driven (Trello o Plane):
  US-XX (User Story) → UC-XXX (Use Cases) → AC-XX (Acceptance Criteria)
  ↓
/prd → Enriquece spec firmado + PRD + evidencia PDF → Trello/Plane
  ↓
/plan → Plan tecnico por UC + VEG + Diseños Stitch (MCP) + evidencia PDF → Trello/Plane
  ↓
/implement → find_next_uc → start_uc → rama + fases + QA + Acceptance Gate + PR
  ↓                                                         ↑
  ├── AG-08 Quality Audit → GO/NO-GO ──────────────────────┤
  ├── AG-09a Acceptance Tests → evidencia visual ──────────┤
  └── AG-09b Acceptance Validator → ACCEPTED/REJECTED ─────┘
  ↓
/feedback → Developer testing → FB-NNN + GitHub issue → puede INVALIDAR verdict
  ↓
complete_uc → Merge secuencial → pull main → find_next_uc (siguiente UC)
  ↓
/optimize-agents → Audita y optimiza sistema agentico del proyecto

Backend selection: set_auth_token(backend_type="trello"|"plane")
Migration: migrate_preview → migrate_project (bidirectional Trello ↔ Plane)
```

## Estructura del repositorio

```
specbox-engine/
├── CLAUDE.md              ← Este archivo
├── ENGINE_VERSION.yaml    ← Version del engine
├── install.sh             ← Instala skills, hooks, commands, GGA
├── .gga                   ← Config de Gentleman Guardian Angel (cached lint)
├── .vscode/mcp.json       ← Servidor MCP de Engram (memoria persistente)
├── .claude/
│   ├── skills/            ← Agent Skills (v3.5)
│   │   ├── prd/SKILL.md
│   │   ├── plan/SKILL.md
│   │   ├── implement/SKILL.md
│   │   ├── adapt-ui/SKILL.md
│   │   ├── optimize-agents/SKILL.md
│   │   ├── quality-gate/SKILL.md
│   │   ├── explore/SKILL.md
│   │   ├── feedback/SKILL.md
│   │   └── check-designs/SKILL.md
│   ├── hooks/             ← Hooks (v3.3)
│   │   ├── mcp-report.sh
│   │   ├── pre-commit-lint.sh
│   │   ├── on-session-end.sh
│   │   ├── implement-checkpoint.sh
│   │   ├── implement-healing.sh
│   │   ├── post-implement-validate.sh
│   │   └── design-gate.sh
│   └── settings.json      ← Hooks config
├── commands/              ← Commands (referencia legacy)
│   ├── prd.md
│   ├── plan.md
│   ├── implement.md
│   ├── adapt-ui.md
│   ├── optimize-agents.md
│   ├── quality-gate.md
│   └── feedback.md
├── agents/                ← Templates de agentes por rol
│   ├── orchestrator.md
│   ├── feature-generator.md
│   ├── uiux-designer.md
│   ├── db-specialist.md
│   ├── qa-validation.md
│   ├── design-specialist.md
│   ├── n8n-specialist.md
│   ├── appscript-specialist.md
│   ├── quality-auditor.md
│   ├── acceptance-tester.md
│   ├── acceptance-validator.md
│   └── developer-tester.md
├── agent-teams/           ← Agent Teams nativo (Claude Code)
│   ├── README.md
│   ├── templates/
│   ├── prompts/
│   └── hooks/
├── architecture/          ← Patrones por stack
│   ├── flutter/
│   ├── react/
│   ├── python/
│   └── google-apps-script/
├── design/                ← Integracion Stitch MCP + VEG
│   └── stitch/
├── doc/
│   ├── templates/         ← VEG templates y arquetipos
│   │   ├── veg-template.md
│   │   └── veg-archetypes.md
│   └── research/          ← Investigacion de tooling VEG
├── infra/                 ← Patrones por servicio
│   ├── supabase/
│   ├── neon/
│   ├── stripe/
│   ├── firebase/
│   └── n8n/
├── templates/             ← Templates para nuevos proyectos
│   ├── CLAUDE.md.template
│   ├── settings.json.template
│   ├── team-config.json.template
│   └── quality-baseline.json.template
├── .quality/              ← Telemetria y evidencia (v3.1)
├── rules/                 ← Reglas globales
│   └── GLOBAL_RULES.md
├── server/                ← MCP server unificado (v5.5)
│   ├── server.py          ← FastMCP (108+ tools)
│   ├── dashboard_api.py   ← REST API /api/*
│   ├── spec_backend.py    ← SpecBackend ABC + DTOs (backend-agnostic)
│   ├── backends/          ← Backend implementations
│   │   ├── trello_backend.py  ← TrelloBackend (wraps TrelloClient)
│   │   ├── plane_backend.py   ← PlaneBackend (Plane CE self-hosted)
│   │   └── plane_client.py    ← Async httpx client for Plane API v1
│   ├── tools/             ← 13 tool modules
│   │   ├── engine.py      ← 3 tools (version, status, stacks)
│   │   ├── plans.py       ← 3 tools
│   │   ├── quality.py     ← 4 tools
│   │   ├── skills.py      ← 2 tools
│   │   ├── features.py    ← 7 tools
│   │   ├── telemetry.py   ← 8 tools
│   │   ├── hooks.py       ← 3 tools
│   │   ├── onboarding.py  ← 10 tools (+ setup_board + archive_project)
│   │   ├── state.py       ← 20 tools
│   │   ├── spec_driven.py ← 21 tools (backend-agnostic via SpecBackend)
│   │   ├── migration.py   ← 5 tools (Trello ↔ Plane migration)
│   │   ├── stitch.py      ← 13 tools (Stitch MCP proxy)
│   │   └── heartbeat_stats.py ← 1 tool (get_heartbeat_stats)
│   ├── stitch_client.py   ← Async MCP JSON-RPC client for Google Stitch
│   ├── trello_client.py   ← Async httpx con retry
│   ├── board_helpers.py   ← Card parsing, custom fields (Trello)
│   ├── models.py          ← Pydantic: US, UC, AC, WorkflowState
│   ├── pdf_generator.py   ← Markdown → PDF (fpdf2)
│   ├── auth_gateway.py    ← Per-session credentials (multi-backend)
│   ├── resources/         ← 8 MCP Resources
│   └── dashboard/         ← React 19 + Vite (Sala de Máquinas)
│       └── src/
├── tests/                 ← Tests unificados
├── Dockerfile             ← Multi-stage (Node + Python)
├── docker-compose.yml
├── pyproject.toml         ← name = "specbox-engine"
└── docs/                  ← Documentacion del sistema
    ├── getting-started.md
    ├── commands.md
    ├── agent-teams.md
    └── architecture.md
```

## Para contribuir

1. Las Skills en `.claude/skills/` son los archivos activos del sistema
2. Los commands en `commands/` se mantienen como referencia legacy
3. Tras modificar una Skill, ejecutar `./install.sh` para actualizar en global
4. Versionar cambios en ENGINE_VERSION.yaml

## Available Skills (v5.5)

Skills are auto-discoverable. Claude will use them when relevant. You can also invoke them explicitly.

| Skill | Trigger phrases | Mode | Tools | Notes |
|-------|----------------|------|-------|-------|
| /prd | "create PRD", "new feature", "write requirements" | fork:Plan | Full | Definition Quality Gate (Paso 2.5) valida AC-XX |
| /plan | "plan feature", "technical plan", "analyze for implementation" | fork:Plan | Full | VEG generation (Paso 2.5b) |
| /implement | "implement plan", "execute plan", "autopilot" | direct | Full | Self-healing + AG-09 + Spec-Code Sync + merge secuencial |
| /adapt-ui | "scan UI", "map components", "detect widgets" | fork:Explore | Read-only | |
| /optimize-agents | "audit agents", "optimize system", "agent score" | fork:Explore | Read-only | |
| /quality-gate | "check quality", "run gates", "coverage check" | direct | Lint+Read | |
| /explore | "analyze codebase", "explore code", "understand architecture" | fork:Explore | Read-only | |
| /feedback | "report feedback", "found a bug", "this doesn't work" | direct | Full | AG-10 + GitHub issue + invalida acceptance |
| /check-designs | "check designs", "design compliance", "verify designs" | fork:Explore | Read-only | Retroactive Stitch compliance scan |
| /acceptance-check | "check acceptance", "validate AC", "acceptance gate" | fork | Full | v5.0 — Standalone BDD acceptance without /implement |
| /quickstart | "quickstart", "tutorial", "getting started" | fork | Full | v5.0 — Interactive onboarding tutorial (< 5 min) |
| /remote | "estado de", "resumen de todos", "sesiones activas" | direct | Full | v5.5 — Remote project management for OpenClaw (WhatsApp/Discord) |

## Hooks (v3.5)

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| pre-commit-lint | PostToolUse (git commit) | BLOCKING: runs `gga run` (cached lint, skips unmodified files). Falls back to direct lint if GGA not installed |
| on-session-end | Stop | Logs session telemetry to .quality/logs/ + persists summary to Engram |
| implement-checkpoint | Manual (called by /implement) | Saves phase progress for resume |
| implement-healing | Manual (called by /implement) | Logs self-healing events to evidence |
| post-implement-validate | Manual (called by /implement) | Checks baseline regression after implementation |
| design-gate | PostToolUse (Write/Edit on presentation/pages/) | NON-BLOCKING: warns if presentation page lacks Stitch design or traceability comment |
| heartbeat-sender | Manual (called by on-session-end, implement-checkpoint) | Sends consolidated project state snapshot to VPS; queues locally if offline |

## Remote Telemetry (v3.3)

Hooks can report to a remote MCP server for centralized state tracking.
Set `SPECBOX_ENGINE_MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp` in your shell profile.
Reporting is fire-and-forget — if the MCP is unreachable, hooks work normally.

## Remote State Management (v5.6.0)

Gestionar el estado de todos los proyectos desde iPhone via Claude.ai iOS + MCP remoto, y desde WhatsApp/Discord via OpenClaw Gateway.

### Heartbeat Protocol
- Hooks locales envian `project_state.json` al VPS tras cada operacion significativa
- `heartbeat-sender.sh` auto-detecta: git branch, coverage, checkpoint, feedback
- Si el VPS no responde, los heartbeats se guardan en `.quality/pending_heartbeats.jsonl`
- Escribe `specbox-state.json` en la raiz del repo para GitHub sync

### GitHub Sync
- Cron (n8n) cada 15 min lee `specbox-state.json` de cada repo via GitHub API
- Solo actualiza si el ultimo heartbeat tiene > 30 min de antiguedad
- `POST /api/sync/github` para trigger manual

### MCP Tools para iPhone
| Tool | Uso |
|------|-----|
| `get_project_live_state` | "¿Como va McProfit?" |
| `get_all_projects_overview` | "Dame resumen de todos" |
| `get_active_sessions` | "¿Que tiene sesion activa?" |
| `refresh_project_state` | "Actualiza estado de X" |
| `get_heartbeat_stats` | "¿Llegan los heartbeats?" |

### Heartbeat Observability (v5.6.0)
- Cada heartbeat recibido se registra en `heartbeats.jsonl` por proyecto
- `get_heartbeat_stats` retorna: total 24h, por proyecto, stale detection
- `GET /api/heartbeats/stats` — mismo dato via REST con Bearer auth
- Proyectos con `session_active=true` y sin heartbeat > 30 min marcados como stale

### Conversational Summaries (v5.6.0)
- Todos los tools de live_state incluyen campo `summary` humanizado en espanol
- `get_all_projects_overview` incluye `summary_table` con tabla Markdown
- Timestamps siempre como "hace X minutos/horas" — nunca ISO crudos en summaries
- Tools de escritura (`move_uc`, `mark_ac`, reports) incluyen `summary` + `generated_at`

### Skill /remote (v5.6.0)
- Wrapper conversacional para OpenClaw Gateway (WhatsApp/Discord)
- Respuestas en texto plano (max 2000 chars) sin Markdown complejo
- Triggers: "estado de [proyecto]", "resumen de todos", "sesiones activas"

### Env vars requeridas
- `SPECBOX_SYNC_TOKEN` — auth para endpoints de heartbeat y sync (VPS + local)
- `GITHUB_TOKEN` — para GitHub API (solo VPS)

## Context Engineering (v3.5)

- Skills with `context: fork` run in isolated subagents — they don't pollute your main session
- /implement delegates phases to isolated Tasks with a **context budget of ~8,700 tokens per phase**
- Read-only Skills (explore, optimize-agents, adapt-ui) cannot modify files
- File ownership per agent is documented in .claude/skills/implement/file-ownership.md
- Context budget estimator: `.quality/scripts/context-budget.sh <path> [--detail]`
- Session context metrics logged automatically via on-session-end hook
- Full context engineering rules in `rules/GLOBAL_RULES.md` section "Context Engineering"

## Quality Scripts

| Script | Usage | Purpose |
|--------|-------|---------|
| `create-baseline.sh` | `.quality/scripts/create-baseline.sh [path]` | Generate initial quality baseline |
| `update-baseline.sh` | `.quality/scripts/update-baseline.sh [path]` | Ratchet-safe baseline update (only improves) |
| `analyze-sessions.sh` | `.quality/scripts/analyze-sessions.sh [--last N]` | Telemetry: sessions, context tokens, healing, checkpoints |
| `context-budget.sh` | `.quality/scripts/context-budget.sh <path> [--detail]` | Estimate token cost of files/directories |
| `design-baseline.sh` | `.quality/scripts/design-baseline.sh [path] [--update\|--init]` | Measure design compliance, enforce ratchet (L0/L1/L2) |

## Agents (v3.5)

| ID | Rol | Archivo | Modelo |
|----|-----|---------|--------|
| AG-01 | Feature Generator | `agents/feature-generator.md` | opus |
| AG-02 | UI/UX Designer | `agents/uiux-designer.md` | opus |
| AG-03 | DB Specialist | `agents/db-specialist.md` | sonnet |
| AG-04 | QA Validation | `agents/qa-validation.md` | sonnet |
| AG-05 | n8n Specialist | `agents/n8n-specialist.md` | sonnet |
| AG-06 | Design Specialist | `agents/design-specialist.md` | sonnet |
| AG-07 | Apps Script Specialist | `agents/appscript-specialist.md` | sonnet |
| AG-08 | Quality Auditor | `agents/quality-auditor.md` | sonnet |
| AG-09a | Acceptance Tester | `agents/acceptance-tester.md` | sonnet |
| AG-09b | Acceptance Validator | `agents/acceptance-validator.md` | sonnet |
| AG-10 | Developer Tester | `agents/developer-tester.md` | sonnet |

## Acceptance Engine (v3.8)

Pipeline completo de validacion funcional con jerarquia US → UC → AC:

1. **Definition Quality Gate** (`/prd` Paso 2.5) — Rechaza acceptance criteria vagos/no-testables antes de crear work items. Evalua especificidad, medibilidad y testabilidad (0-2 cada una).
2. **AG-09a Acceptance Tester** (`/implement` Paso 7.5) — Genera E2E/integration tests desde AC-XX del PRD con evidencia visual (screenshots, traces, response logs).
3. **AG-09b Acceptance Validator** (`/implement` Paso 7.7) — Validacion independiente por UC: verifica que cada AC-XX del UC esta implementado, testeado y evidenciado. Emite ACCEPTED/CONDITIONAL/REJECTED. US se considera ACCEPTED cuando todos sus UCs pasan.
4. **AG-10 Developer Feedback** (`/feedback`) — Captura feedback de testing manual. Crea evidencia local (FB-NNN.json) + GitHub issue. Puede INVALIDAR verdict de AG-09b. Severity critical/major bloquea merge.
5. **Merge Secuencial** (`/implement` Paso 8.5) — Auto-merge solo si AG-08=GO, AG-09=ACCEPTED y no hay feedback bloqueante. `complete_uc` → pull main → `find_next_uc` para siguiente UC.
6. **Evidence Pipeline** — PRD→US card, Plan→US card, AG-09→UC card, Delivery→US card (Markdown→PDF→Trello attachment).

Frameworks de acceptance testing por stack:

| Stack | Framework | Evidencia | Tests en |
|-------|-----------|-----------|----------|
| Flutter | Patrol + Alchemist | Screenshots + goldens | `test/acceptance/` |
| React | Playwright | Screenshots + traces | `tests/acceptance/` |
| Python | pytest + httpx | Response JSON logs | `tests/acceptance/` |

## Visual Experience Generation — VEG (v3.9)

Sistema que genera decisiones visuales intencionales (imagenes, animaciones, directivas de diseno) adaptadas a la audiencia del producto. Rompe el patron de UI generica al derivar automaticamente estilos desde el target/ICP del PRD.

### 3 Modos de Operacion

| Modo | Cuando | Resultado |
|------|--------|-----------|
| **Modo 1: Uniform** | 1 audiencia homogenea | 1 VEG aplicado a todas las pantallas |
| **Modo 2: Per Profile** | Multiples perfiles de usuario | N VEGs, uno por target profile |
| **Modo 3: Per ICP+JTBD** | Landings por segmento | N VEGs con JTBD racional + emocional por ICP |

### 3 Pilares

| Pilar | Que genera | Herramienta |
|-------|-----------|-------------|
| **Pilar 1: Imagenes** | Prompts + generacion via MCP | Canva MCP (primary, €0) + lansespirit (fallback) |
| **Pilar 2: Motion** | Catalogo de animaciones por nivel | `flutter_animate` (Flutter) / `motion` (React) |
| **Pilar 3: Diseno** | Directivas para Stitch | Density, whitespace, hierarchy, CTA, typography |

### Arquetipos

6 arquetipos base derivados del target (Corporate, Startup, Creative, Consumer, Gen-Z, Gobierno). El JTBD emocional puede sobreescribir max 2 pilares. Definidos en `doc/templates/veg-archetypes.md`.

### Integracion en el Pipeline

- `/prd` → Captura seccion Audiencia (targets, JTBD, ICPs) + detecta modo VEG
- `/plan` → Genera artefactos VEG por target + **preview y confirmacion con usuario** (Paso 2.5b.3) + enriquece prompts Stitch
- `/implement` → Health check MCP (3.5.1) + advertencia costes (3.5.0) + genera imagenes (3.5.2) + auto-instala motion deps (4.0) + inyecta Motion Catalog a AG-02 (4.2)
- AG-06 recibe Pilar 3 para enriquecer prompts Stitch
- AG-02 recibe Pilar 2 (Motion Catalog) para design-to-code con hover→tap enforcement en mobile
- Resumen compacto (~400 tokens) inyectado en contexto de sub-agentes

### Safety Gates

- **Costes**: Advertencia obligatoria antes de generar imagenes con estimacion por provider
- **MCP Health Check**: Verifica que el MCP responde antes de entrar al loop de generacion
- **VEG Preview**: El usuario confirma el VEG derivado antes de que afecte al pipeline
- **Pending Images**: Si MCP falla → `PENDING_IMAGES.md` con prompts + instrucciones de retoma manual
- **Motion auto-install**: Verifica e instala `flutter_animate`/`motion` antes de design-to-code

### Degradacion Graceful

- Sin targets en PRD → pipeline legacy, sin cambios
- Sin MCP de imagenes → health check detecta, genera `PENDING_IMAGES.md` con prompts para uso manual
- Sin VEG config → usa defaults de `templates/settings.json.template`
- MCP config template incluido en `templates/settings.json.template` seccion `veg.mcpServers`

### Costes de Image Generation

| Provider | Coste/imagen | Auth |
|----------|-------------|------|
| **Canva (primary)** | **€0** con Pro/Premium | OAuth (browser) |
| Freepik (alternativo) | Segun plan contratado | `FREEPIK_API_KEY` |
| OpenAI GPT-Image-1 (fallback) | $0.02-0.19 | `OPENAI_API_KEY` |
| Gemini Imagen 4 (fallback) | $0.02-0.06 | `GOOGLE_API_KEY` |

Canva como primary cubre el 90%+ de las imagenes sin coste adicional. Fallback de pago solo para fotorrealismo hiperrealista.
Configuracion MCP de providers en `templates/settings.json.template` → seccion `veg.mcpServers`.

### Archivos VEG

- Templates: `doc/templates/veg-template.md`, `doc/templates/veg-archetypes.md`
- Research: `doc/research/veg-image-providers.md`, `doc/research/veg-motion-strategy.md`
- Decisiones: `doc/research/veg-tooling-decisions.md`
- Por feature: `doc/veg/{feature}/` (generado por /plan)

## Stitch MCP Proxy (v5.6.0)

Proxy completo de Google Stitch a traves del SpecBox Engine MCP server. Permite que usuarios de claude.ai usen Stitch sin configurar un conector OAuth adicional — la API Key se configura por proyecto. Cubre los 12 tools nativos de Stitch + 1 tool de configuracion.

### Tools (13)

| Tool | Descripcion | Timeout |
|------|-------------|---------|
| `stitch_set_api_key` | Configurar/actualizar API Key de Stitch para un proyecto | normal |
| `stitch_create_project` | Crear nuevo proyecto/workspace en Stitch | normal |
| `stitch_list_projects` | Listar proyectos del usuario en Stitch | normal |
| `stitch_get_project` | Obtener detalles de un proyecto Stitch | normal |
| `stitch_list_screens` | Listar pantallas de un proyecto | normal |
| `stitch_get_screen` | Obtener metadata de una pantalla | normal |
| `stitch_fetch_screen_code` | Descargar HTML raw de una pantalla | normal |
| `stitch_fetch_screen_image` | Descargar screenshot hi-res (base64) | normal |
| `stitch_generate_screen` | Generar pantalla desde prompt | 6 min |
| `stitch_edit_screen` | Editar pantalla existente con prompt | 6 min |
| `stitch_generate_variants` | Generar variantes de una pantalla | 6 min |
| `stitch_extract_design_context` | Extraer Design DNA (fuentes, colores, layouts) | normal |
| `stitch_build_site` | Construir sitio multi-pagina mapeando screens a rutas | 6 min |

### Enums de Stitch

- **DeviceType**: `DESKTOP`, `MOBILE`, `TABLET`, `AGNOSTIC`
- **ModelId**: `GEMINI_3_PRO` (complejo), `GEMINI_3_FLASH` (simple)
- **CreativeRange** (variantes): `REFINE` (sutil), `EXPLORE` (moderado), `REIMAGINE` (radical)
- **Aspects** (variantes): `LAYOUT`, `COLOR_SCHEME`, `IMAGES`, `TEXT_FONT`, `TEXT_CONTENT`

### Flujo

1. `stitch_set_api_key(project="mi-proyecto", api_key="AIza...")` — configura la key
2. `stitch_create_project(project="mi-proyecto", title="Mi App")` — crea proyecto
3. `stitch_generate_screen(project="mi-proyecto", stitch_project_id="xxx", prompt="...")` — genera diseño
4. `stitch_edit_screen(...)` — itera sobre el diseño
5. `stitch_extract_design_context(...)` — extrae Design DNA para consistencia
6. `stitch_generate_variants(...)` — explora alternativas
7. `stitch_fetch_screen_code(...)` — descarga HTML para integrar en codigo
8. `stitch_build_site(...)` — ensambla sitio multi-pagina

### Almacenamiento de API Key

- **Sesion**: Credenciales en FastMCP session state (aisladas por cliente)
- **Disco**: Key en base64 en `meta.json` del proyecto (fallback entre sesiones)
- **Telemetria**: Uso registrado en `stitch_usage.jsonl` por proyecto

### Arquitectura

- `server/stitch_client.py` — Cliente async MCP JSON-RPC (Streamable HTTP + SSE)
- `server/tools/stitch.py` — 13 tools registrados en FastMCP
- `server/auth_gateway.py` — `store_stitch_credentials()` / `get_stitch_client()` per-project
- Timeout de 6 minutos para operaciones de generacion
- Retry con backoff exponencial para errores transitorios

## Spec-Code Sync (v5.0)

Automatic PRD update with implementation deltas after each /implement phase:

- **Delta capture** (Paso 5.1.1a): After each phase, generates structured Markdown with files, deltas vs plan, healing events
- **PRD write** (Paso 8.5.1a / 7.7a): Appends `## Implementation Status` section to PRD (append-only)
- **MCP tools**: `get_implementation_status(project_path, item_id)`, `write_implementation_status(...)`
- **Parser**: Reads Implementation Status from PRDs into structured JSON with `overall_status` and `delta_count`

## External Skill Registry (v5.0)

External skills with `manifest.yaml` can be installed, versioned, and auto-discovered:

- **Manifest**: `name`, `version` (semver), `author`, `description`, `compatibility` (stacks), `triggers`, `depends_on`
- **Install**: `install.sh --skill <path|git-url>` (global) or `--local` (project)
- **Auto-discovery**: During /prd, skills matching stack + keywords are activated automatically
- **MCP tools**: `discover_skills(...)`, `validate_skill_manifest(...)`
- **Template**: `templates/skill-manifest.yaml.template`

## Standalone Acceptance Check (v5.0)

BDD acceptance testing without full /implement pipeline:

- **Skill**: `/acceptance-check` — validates AC from PRD against code
- **MCP tools**: `run_acceptance_check(project_path, item_id, branch)`, `get_acceptance_report(project_path, uc_id)`
- **GitHub Action**: `templates/github-actions/acceptance-gate.yml`
- **Output**: PR-comment-ready Markdown with per-AC verdict

## Contextual Hints (v5.0)

- Hints shown first 3 times a skill is used in a project (then disappear)
- Counter stored in `.quality/hint_counters.json`
- Not shown if project has > 5 completed UCs
- MCP tools: `get_skill_hint(project_path, skill_name)`, `record_skill_hint(...)`

## Public Benchmarking (v5.0)

- **MCP tool**: `generate_benchmark_snapshot(output_path)` — aggregated, anonymized metrics
- **REST endpoint**: `GET /api/benchmark/public` — JSON metrics (no auth required)
- **Output**: `docs/benchmarks/snapshot_{date}.md` with Metodología section

## Engine Version

Current: v5.6.0 "Stitch Proxy"
Brand: SpecBox Engine (SpecBox Engine by JPS)
Config: ENGINE_VERSION.yaml
