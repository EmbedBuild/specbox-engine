# SDD-JPS Engine v4.0.0

> **Spec-Driven Development Engine by JPS**
> Sistema de programacion agentica para Claude Code.
> Monorepo unificado: engine + MCP server (73+ tools) + Sala de Máquinas + Gherkin BDD.

## Que es este repositorio

Este repositorio es un **monorepo unificado** con el sistema completo de programacion agentica para Claude Code. Incluye:

- **Commands** (`/prd`, `/plan`, `/implement`, `/adapt-ui`, `/optimize-agents`, `/feedback`) — flujo completo de desarrollo
- **Agent Teams** — configuracion para orquestacion multi-agente nativa de Claude Code
- **Architecture** — patrones por stack (Flutter, React, Python, Google Apps Script)
- **Infrastructure** — patrones por servicio (Supabase, Neon, Stripe, Firebase, n8n)
- **Design** — integracion con Google Stitch MCP para diseño UI + VEG (Visual Experience Generation)
- **Templates** — CLAUDE.md, settings.json, team-config para nuevos proyectos
- **Agents** — templates genericos de roles especializados
- **Server** — MCP server unificado (73+ tools) + Sala de Máquinas dashboard (React 19)
- **Spec-Driven** — Trello domain tools para US/UC/AC (21 tools integrados en MCP)
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

## Instalacion

```bash
git clone <repo-url> sdd-jps-engine
cd sdd-jps-engine
./install.sh
```

Esto instala Skills en `~/.claude/skills/`, hooks en `~/.claude/hooks/` y commands en `~/.claude/commands/`.

## Flujo de desarrollo

```
Spec-Driven (Trello):
  US-XX (User Story) → UC-XXX (Use Cases) → AC-XX (Acceptance Criteria)
  ↓
/prd → Enriquece spec firmado + PRD + evidencia PDF → Trello
  ↓
/plan → Plan tecnico por UC + VEG + Diseños Stitch (MCP) + evidencia PDF → Trello
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

Freeform (Plane / texto):
  /prd → PRD + Plane    →  /plan → Plan tecnico  →  /implement → Autopilot
```

## Estructura del repositorio

```
sdd-jps-engine/
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
│   │   └── feedback/SKILL.md
│   ├── hooks/             ← Hooks (v3.3)
│   │   ├── mcp-report.sh
│   │   ├── pre-commit-lint.sh
│   │   ├── on-session-end.sh
│   │   ├── implement-checkpoint.sh
│   │   ├── implement-healing.sh
│   │   └── post-implement-validate.sh
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
├── server/                ← MCP server unificado (v4.0)
│   ├── server.py          ← FastMCP (73+ tools)
│   ├── dashboard_api.py   ← REST API /api/*
│   ├── tools/             ← 10 tool modules
│   │   ├── engine.py      ← 3 tools (version, status, stacks)
│   │   ├── plans.py       ← 3 tools
│   │   ├── quality.py     ← 4 tools
│   │   ├── skills.py      ← 2 tools
│   │   ├── features.py    ← 7 tools
│   │   ├── telemetry.py   ← 8 tools
│   │   ├── hooks.py       ← 3 tools
│   │   ├── onboarding.py  ← 10 tools (+ setup_board + archive_project)
│   │   ├── state.py       ← 20 tools
│   │   └── spec_driven.py ← 21 tools Trello domain
│   ├── trello_client.py   ← Async httpx con retry
│   ├── board_helpers.py   ← Card parsing, custom fields
│   ├── models.py          ← Pydantic: US, UC, AC, WorkflowState
│   ├── pdf_generator.py   ← Markdown → PDF (fpdf2)
│   ├── auth_gateway.py    ← Per-session credentials
│   ├── resources/         ← 8 MCP Resources
│   └── dashboard/         ← React 19 + Vite (Sala de Máquinas)
│       └── src/
├── tests/                 ← Tests unificados (208 tests)
├── Dockerfile             ← Multi-stage (Node + Python)
├── docker-compose.yml
├── pyproject.toml         ← name = "sdd-jps-engine"
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

## Available Skills (v3.5)

Skills are auto-discoverable. Claude will use them when relevant. You can also invoke them explicitly.

| Skill | Trigger phrases | Mode | Tools | Notes |
|-------|----------------|------|-------|-------|
| /prd | "create PRD", "new feature", "write requirements" | fork:Plan | Full | Definition Quality Gate (Paso 2.5) valida AC-XX |
| /plan | "plan feature", "technical plan", "analyze for implementation" | fork:Plan | Full | VEG generation (Paso 2.5b) |
| /implement | "implement plan", "execute plan", "autopilot" | direct | Full | Self-healing + AG-09 acceptance gate + merge secuencial |
| /adapt-ui | "scan UI", "map components", "detect widgets" | fork:Explore | Read-only | |
| /optimize-agents | "audit agents", "optimize system", "agent score" | fork:Explore | Read-only | |
| /quality-gate | "check quality", "run gates", "coverage check" | direct | Lint+Read | |
| /explore | "analyze codebase", "explore code", "understand architecture" | fork:Explore | Read-only | |
| /feedback | "report feedback", "found a bug", "this doesn't work" | direct | Full | AG-10 + GitHub issue + invalida acceptance |

## Hooks (v3.5)

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| pre-commit-lint | PostToolUse (git commit) | BLOCKING: runs `gga run` (cached lint, skips unmodified files). Falls back to direct lint if GGA not installed |
| on-session-end | Stop | Logs session telemetry to .quality/logs/ + persists summary to Engram |
| implement-checkpoint | Manual (called by /implement) | Saves phase progress for resume |
| implement-healing | Manual (called by /implement) | Logs self-healing events to evidence |
| post-implement-validate | Manual (called by /implement) | Checks baseline regression after implementation |

## Remote Telemetry (v3.3)

Hooks can report to a remote MCP server for centralized state tracking.
Set `DEV_ENGINE_MCP_URL=https://mcp-dev-engine.jpsdeveloper.com/mcp` in your shell profile.
Reporting is fire-and-forget — if the MCP is unreachable, hooks work normally.

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

## Engine Version

Current: v4.0.0 "Monorepo + Gherkin Acceptance"
Brand: SDD-JPS Engine (Spec-Driven Development Engine by JPS)
Config: ENGINE_VERSION.yaml
