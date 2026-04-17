# SpecBox Engine v5.25.0

> **SpecBox Engine by JPS**
> Sistema de programacion agentica para Claude Code.
> Monorepo unificado: engine + MCP server (138 tools) + Sala de Máquinas + Gherkin BDD + Quality Audit ISO/IEC 25010.

## Que es este repositorio

Este repositorio es un **monorepo unificado** con el sistema completo de programacion agentica para Claude Code. Incluye:

- **Commands** (`/prd`, `/visual-setup`, `/plan`, `/implement`, `/adapt-ui`, `/optimize-agents`, `/feedback`) — flujo completo de desarrollo
- **Agent Teams** — configuracion para orquestacion multi-agente nativa de Claude Code
- **Architecture** — patrones por stack (Flutter, React, Python, Google Apps Script)
- **Infrastructure** — patrones por servicio (Supabase, Neon, Stripe, Firebase, n8n)
- **Design** — integracion con Google Stitch MCP para diseño UI + VEG (Visual Experience Generation)
- **Templates** — CLAUDE.md, settings.json, team-config para nuevos proyectos
- **Agents** — templates genericos de roles especializados
- **Server** — MCP server unificado (138 tools) + Sala de Máquinas dashboard (React 19)
- **Quality Audit** — ISO/IEC 25010 (SQuaRE) on-demand via `/audit` + AG-10 auditor externo
- **Spec-Driven** — Backend-agnostic tools para US/UC/AC (21 tools + 5 migration, Trello y Plane)
- **Gherkin BDD** — Acceptance testing en español con frameworks por stack

## Stack soportado

| Stack | Version | Estado |
|-------|---------|--------|
| Flutter | 3.38+ | Completo |
| React | 19.x | Completo |
| Go | 1.23+ | Completo |
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

| Gestor | Auth | Almacenamiento | Estado |
|--------|------|----------------|--------|
| Trello | API key + token | Cloud (Trello API) | Completo |
| Plane | API key + base_url + workspace_slug | Cloud/Self-hosted (Plane API) | Completo |
| FreeForm | Ninguna | Local filesystem (`doc/tracking/`) | Completo |

Los 3 gestores se usan de forma identica gracias a la abstraccion `SpecBackend`.
Los 21 tools de spec-driven funcionan con cualquier backend configurado por proyecto.
Plane funciona tanto self-hosted (CE) como cloud — solo cambia el `base_url`.
FreeForm almacena todo como JSON + Markdowns de progreso auto-generados en `doc/tracking/`.
Migracion bidireccional disponible via `migrate_preview` / `migrate_project` (Trello ↔ Plane).

### FreeForm Backend (v5.8.0)

Backend sin API externa para proyectos personales o donde Trello/Plane es overkill.

```
set_auth_token(api_key="freeform", token="", backend_type="freeform", root_path="doc/tracking")
```

Genera automaticamente Markdowns de progreso legibles:
- `doc/tracking/progress/README.md` — Vista general con tablas US/UC
- `doc/tracking/progress/UC-XXX.md` — Detalle por UC con ACs y estado

Los hooks de Pipeline Integrity (spec-guard.mjs) funcionan igual con FreeForm.

## Instalacion

```bash
git clone <repo-url> specbox-engine
cd specbox-engine
./install.sh
```

Esto instala Skills en `~/.claude/skills/` y hooks en `~/.claude/hooks/`.

## Flujo de desarrollo

```
Spec-Driven (Trello o Plane):
  US-XX (User Story) → UC-XXX (Use Cases) → AC-XX (Acceptance Criteria)
  ↓
/prd → Enriquece spec firmado + PRD + evidencia PDF → Trello/Plane
  ↓
/visual-setup → Brand Kit + Stitch DS + VEG base + Multi-Form-Factor
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
│   ├── skills/            ← Agent Skills (v5.18)
│   │   ├── prd/SKILL.md
│   │   ├── plan/SKILL.md
│   │   ├── implement/SKILL.md
│   │   ├── adapt-ui/SKILL.md
│   │   ├── optimize-agents/SKILL.md
│   │   ├── quality-gate/SKILL.md
│   │   ├── explore/SKILL.md
│   │   ├── feedback/SKILL.md
│   │   ├── check-designs/SKILL.md
│   │   ├── visual-setup/SKILL.md
│   │   ├── acceptance-check/SKILL.md
│   │   ├── quickstart/SKILL.md
│   │   ├── remote/SKILL.md
│   │   ├── release/SKILL.md
│   │   └── compliance/SKILL.md
│   ├── hooks/             ← Hooks (v5.18)
│   │   ├── quality-first-guard.mjs
│   │   ├── read-tracker.mjs
│   │   ├── spec-guard.mjs
│   │   ├── branch-guard.mjs
│   │   ├── commit-spec-guard.mjs
│   │   ├── pre-commit-lint.mjs
│   │   ├── e2e-gate.mjs
│   │   ├── no-bypass-guard.mjs
│   │   ├── design-gate.mjs
│   │   ├── healing-budget-guard.mjs
│   │   ├── pipeline-phase-guard.mjs
│   │   ├── checkpoint-freshness-guard.mjs
│   │   ├── uc-lifecycle-guard.mjs
│   │   ├── on-session-end.mjs
│   │   ├── implement-checkpoint.mjs
│   │   ├── implement-healing.mjs
│   │   ├── post-implement-validate.mjs
│   │   ├── heartbeat-sender.mjs
│   │   ├── mcp-report.mjs
│   │   └── e2e-report.mjs
│   └── settings.json      ← Hooks config
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
├── server/                ← MCP server unificado (v5.23)
│   ├── server.py          ← FastMCP (138 tools)
│   ├── dashboard_api.py   ← REST API /api/*
│   ├── spec_backend.py    ← SpecBackend ABC + DTOs (backend-agnostic)
│   ├── backends/          ← Backend implementations
│   │   ├── trello_backend.py   ← TrelloBackend (wraps TrelloClient)
│   │   ├── plane_backend.py    ← PlaneBackend (Plane CE self-hosted)
│   │   ├── plane_client.py     ← Async httpx client for Plane API v1
│   │   └── freeform_backend.py ← FreeformBackend (local JSON + Markdown)
│   ├── audit/             ← Quality Audit ISO/IEC 25010 (v5.22)
│   │   ├── schema.py           ← QualityReport + Finding + schema v1.0
│   │   ├── scoring.py          ← 0-100 normalization, semáforos, 60/40 mix
│   │   ├── tool_runner.py      ← Subprocess wrapper (timeout + graceful)
│   │   ├── tool_check.py       ← Lazy audit-tool availability check
│   │   ├── signals.py          ← SpecBox MCP signals (AC, evidence, healing, board)
│   │   ├── orchestrator.py     ← Fan-out 8 analyzers → QualityReport
│   │   ├── persistence.py      ← Evidence under evidence/audits/ + project_meta
│   │   ├── analyzers/          ← 8 SQuaRE analyzers (one per characteristic)
│   │   └── reporters/          ← JSON + ReportLab PDF (NumberedCanvas + embed.build brand)
│   ├── tools/             ← 24 tool modules (138 tools)
│   │   ├── engine.py      ← 3 tools (version, status, stacks)
│   │   ├── plans.py       ← 3 tools
│   │   ├── quality.py     ← 4 tools
│   │   ├── skills.py      ← 2 tools
│   │   ├── features.py    ← 6 tools
│   │   ├── telemetry.py   ← 6 tools
│   │   ├── hooks.py       ← 3 tools
│   │   ├── onboarding.py  ← 10 tools (detect, status, list, onboard, upgrade, upgrade_all, matrix, wizard, visual_gap, archive)
│   │   ├── state.py       ← 17 tools
│   │   ├── spec_driven.py ← 21 tools (backend-agnostic via SpecBackend)
│   │   ├── spec_mutations.py ← 8 tools (v5.23.0 Tier 1: update_uc/us/ac, add_ac/uc, delete_ac + batch variants)
│   │   ├── milestone_management.py ← 8 tools (v5.23.0 Tier 2: milestones H1-H4, satellite, rebalance, cross-repo deps)
│   │   ├── board_operations.py ← 5 tools (v5.23.0 Tier 3: validate_ac_quality, set_ac_metadata, link_uc_parent, delete_uc, get_board_diff)
│   │   ├── acceptance_automation.py ← 3 tools (v5.23.0 Tier 4: bulk_update_hours, estimate_from_ac, milestone_acceptance_check)
│   │   ├── _mutation_helpers.py ← Internal helpers for Tier 1-4 (constants, validators, finders, merge_meta, classify_ac)
│   │   ├── migration.py   ← 5 tools (Trello ↔ Plane migration)
│   │   ├── stitch.py      ← 13 tools (Stitch MCP proxy)
│   │   ├── heartbeat_stats.py ← 1 tool (get_heartbeat_stats)
│   │   ├── acceptance.py  ← 3 tools (run_acceptance_check, get_acceptance_report, get_e2e_gap_report)
│   │   ├── benchmark.py   ← 1 tool (generate_benchmark_snapshot)
│   │   ├── hints.py       ← 3 tools (get_skill_hint, record, list)
│   │   ├── live_state.py  ← 4 tools (project state, overview, sessions, refresh)
│   │   ├── skill_registry.py ← 3 tools (discover, validate, manifest)
│   │   ├── sync.py        ← 2 tools (GitHub sync)
│   │   └── audit.py       ← 4 tools (run_quality_audit, attach_audit_evidence, get_last_audit, check_audit_tools_status)
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

1. Las Skills en `.claude/skills/` son los archivos activos del sistema (invocados via slash commands `/prd`, `/plan`, etc.)
2. Los `.claude/skills/*` globales (`~/.claude/skills/*`) son **symlinks** al repo tras `./install.sh` — los cambios en el repo se reflejan en global automáticamente, NO hace falta reinstalar tras editar un SKILL.md
3. Al crear o modificar un skill, respetar el modelo de frontmatter (ver sección "Skill Frontmatter Model" abajo)
4. Versionar cambios en ENGINE_VERSION.yaml

## Skill Frontmatter Model

El campo `context:` del frontmatter de un SKILL.md determina cómo el harness de Claude Code ejecuta el skill. Elegir mal la combinación rompe el skill de formas sutiles.

| Combinación | Ejecución | Cuándo usarla |
|-------------|-----------|---------------|
| `context: direct` | Sesión principal, herramientas completas (Read, Write, Edit, Bash, MCPs). Contamina el contexto de la sesión. | Skills **operativos** que escriben artefactos al filesystem, llaman MCPs de escritura, crean PRs, adjuntan evidencia. Ejemplos: `prd`, `plan`, `visual-setup`, `implement`, `feedback`, `release`, `compliance`, `remote`. |
| `context: fork` + `agent: Explore` | Delega al sub-agente nativo Explore, read-only por diseño. Aísla el contexto de la sesión principal. | Skills **read-only** que analizan código y devuelven un informe. Ejemplos: `explore`, `adapt-ui`, `check-designs`, `optimize-agents` (modo audit). |
| `context: fork` **sin** `agent:` | **ROTO.** El harness no sabe a quién delegar — el sub-agente recibe el SKILL.md como contexto descriptivo, no como instrucción, y responde "no se me ha pedido nada". | Nunca. |
| `context: fork` + `agent: Plan` | Funciona pero fuerza modo read-only (el sub-agente nativo Plan es un arquitecto read-only). El skill puede llamar MCPs externos pero **no puede escribir al filesystem local**. | Nunca para skills de SpecBox — causa bugs silenciosos tipo "el plan se adjunta a Trello pero no se escribe `doc/plans/*.md`". |

**Regla simple**: si el skill escribe archivos o crea artefactos locales → `direct`. Si el skill solo lee y reporta → `fork` + `agent: Explore`.

**Test rápido** para confirmar que un skill funciona: ejecutar su slash command en una sesión nueva (los cambios en SKILL.md no afectan sesiones ya abiertas). Si el skill responde "espero tu solicitud" o falla con error de escritura, el frontmatter está mal.

## Available Skills (v5.25)

Skills are auto-discoverable. Claude will use them when relevant. You can also invoke them explicitly.

| Skill | Trigger phrases | Mode | Tools | Notes |
|-------|----------------|------|-------|-------|
| /prd | "create PRD", "new feature", "write requirements" | direct | Full | Definition Quality Gate (Paso 2.5) valida AC-XX |
| /visual-setup | "visual setup", "configure brand", "design system", "brand kit" | direct | Full | v5.14 — Brand Kit + Stitch DS + VEG + Multi-FF |
| /plan | "plan feature", "technical plan", "analyze for implementation" | direct | Full | VEG generation (Paso 2.5b) |
| /implement | "implement plan", "execute plan", "autopilot" | direct | Full | Self-healing + AG-09 + Spec-Code Sync + merge secuencial |
| /adapt-ui | "scan UI", "map components", "detect widgets" | fork:Explore | Read-only | |
| /optimize-agents | "audit agents", "optimize system", "agent score" | fork:Explore | Read-only | |
| /quality-gate | "check quality", "run gates", "coverage check" | direct | Lint+Read | |
| /explore | "analyze codebase", "explore code", "understand architecture" | fork:Explore | Read-only | |
| /feedback | "report feedback", "found a bug", "this doesn't work" | direct | Full | AG-10 + GitHub issue + invalida acceptance |
| /check-designs | "check designs", "design compliance", "verify designs" | fork:Explore | Read-only | Retroactive Stitch compliance scan |
| /acceptance-check | "check acceptance", "validate AC", "acceptance gate" | direct | Full | v5.0 — Standalone BDD acceptance without /implement |
| /quickstart | "quickstart", "tutorial", "getting started" | direct | Full | v5.0 — Interactive onboarding tutorial (< 5 min) |
| /remote | "estado de", "resumen de todos", "sesiones activas" | direct | Full | v5.5 — Remote project management for OpenClaw (WhatsApp/Discord) |
| /release | "release", "bump version", "sube version", "prepara release" | direct | Full | v5.8 — Audit residuals + update version/changelog/docs + push |
| /compliance | "check compliance", "audit specbox", "specbox audit", "is specbox up to date" | direct | Bash+Read | v5.18 — Compliance audit + version alignment + auto-fix |
| /audit | "audit project", "quality audit", "ISO 25010", "SQuaRE audit" | direct | Full | v5.22 — Quality Audit ISO/IEC 25010 on-demand (AG-10, 8 analyzers, PDF+JSON) |
| /stripe-connect | "stripe connect", "marketplace billing", "integrar pagos marketplace" | direct | Full | v5.25 — Marketplace Connect (Express + Direct charges + subscriptions embedded) + Supabase + React/Flutter |

## Hooks (v5.25.0)

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| **quality-first-guard** | PreToolUse (Write/Edit) | **BLOCKING**: verifies the agent read the file before modifying it. Enforces "read before write." |
| **read-tracker** | PostToolUse (Read) | Non-blocking: records which files the agent reads. Used by quality-first-guard. |
| **spec-guard** | PostToolUse (Write/Edit on src/ or lib/) | **BLOCKING**: verifies active UC exists + branch is not main. No UC or main branch = no code writes. |
| **branch-guard** | PostToolUse (Write/Edit on src/ or lib/) | **BLOCKING**: verifies current branch is not main/master. Enforces branch discipline. |
| **commit-spec-guard** | PostToolUse (git commit) | **BLOCKING** (branch) + WARNING (rest): blocks commits on main; warns UC/checkpoint/size. |
| pre-commit-lint | PostToolUse (git commit) | **BLOCKING**: runs `gga run` (cached lint, skips unmodified files). Falls back to direct lint if GGA not installed |
| **e2e-gate** | PostToolUse (git commit) | **BLOCKING**: validates results.json schema + HTML Evidence Report exists + evidence integrity when committing acceptance files. Uses `validate-results-json.js`. |
| **no-bypass-guard** | PreToolUse (--no-verify, push --force, reset --hard) | **BLOCKING**: prevents agent shortcuts under pressure — must fix root cause, not bypass quality checks. |
| **design-gate** | PostToolUse (Write/Edit on pages/) | **BLOCKING**: blocks UI page creation/modification without Stitch HTML design in doc/design/. |
| on-session-end | Stop | Logs session telemetry to .quality/logs/ + persists summary to Engram |
| implement-checkpoint | Manual (called by /implement) | Saves phase progress for resume |
| implement-healing | Manual (called by /implement) | Logs self-healing events to evidence |
| post-implement-validate | Manual (called by /implement) | Checks baseline regression after implementation |
| heartbeat-sender | Manual (called by on-session-end, implement-checkpoint) | Sends consolidated project state snapshot to VPS; queues locally if offline |
| mcp-report | Helper (called by other hooks) | Generic MCP reporter: fire-and-forget HTTP POST to /api/report/* |
| e2e-report | Manual (called by /implement) | Reports Playwright E2E test results to MCP telemetry |
| **healing-budget-guard** | PreToolUse (Write/Edit) | **BLOCKING**: counts healing.jsonl entries per feature. Blocks at 8 attempts (HARD limit). Prevents infinite healing loops. |
| **pipeline-phase-guard** | PreToolUse (Write/Edit) | **BLOCKING**: reads pipeline_state.json to verify phase dependencies are met. Prevents out-of-order execution (e.g., feature code before DB). |
| **stripe-safety-guard** | PreToolUse (Write/Edit on billing paths) | **BLOCKING**: scans `src/billing/`, `lib/billing/`, `supabase/functions/stripe-*`. Blocks 5 anti-patterns: sk_live_* hardcoded, webhook sin firma, webhook sin idempotencia (`stripe_processed_events`), `redirectToCheckout`/`ui_mode:hosted`, Payment Links. Escape hatches: `// stripe-safety-guard:ignore` / `:disable-file`. v5.25 — scaffoldeado por `/stripe-connect`. |
| checkpoint-freshness-guard | PostToolUse (git commit) | Non-blocking WARNING: warns if checkpoint is stale (>30min) or missing during active UC implementation. |
| uc-lifecycle-guard | PostToolUse (git push) | Non-blocking WARNING: warns if pushing feature branch without calling move_uc (board out of sync). |

### Compliance Audit (v5.20.1)

The `/compliance` skill and `specbox-audit.mjs` script provide exhaustive SpecBox compliance auditing:

- **Local execution**: `node .quality/scripts/specbox-audit.mjs [path] [--json] [--fix] [--verbose]`
- **Skill invocation**: `/compliance` from Claude Code
- **Auto-fix**: `--fix` flag copies missing hooks, creates directories
- **6 audit categories**: Version Alignment, Hooks Installation, Settings Configuration, Quality Infrastructure, Skills Installation, Spec-Driven Compliance
- **Scoring**: Weighted score 0-100% with grades A+ through F
- **Evidence**: Saves `compliance-audit.json` in `.quality/evidence/`

### Quality First Enforcement (v5.15.0)

The `quality-first-guard.mjs` hook makes it **impossible** to modify an existing file without
reading it first. The `read-tracker.mjs` hook records every Read tool call in
`.quality/read_tracker.jsonl`. The tracker auto-clears after 24 hours (one session = fresh tracker).

This enforces the principle: **SpecBox provides speed. The LLM provides quality.**
Every time the agent writes without reading, it risks breaking existing code, duplicating
functionality, or introducing inconsistencies. The hook eliminates this antipattern mechanically.

Skipped files: generated (`.g.dart`, `.freezed.dart`), lock files, `.quality/` internals,
build artifacts. New files (that don't exist yet) are always allowed.

See `rules/GLOBAL_RULES.md` section "Quality First" for the complete quality contract.

### Pipeline Integrity (v5.7.0)

The `spec-guard.mjs` hook makes it **impossible** to write source code in a spec-driven project
without an active UC. The marker file `.quality/active_uc.json` is written by `start_uc()` and
cleared by `complete_uc()`. It expires after 24 hours to prevent stale sessions.

The `e2e-gate.mjs` hook makes it **impossible** to commit acceptance evidence without valid
`results.json` (schema-validated via `validate-results-json.js`) + `e2e-evidence-report.html`
(integrity-checked: size, structure, UC reference, embedded evidence).

The `no-bypass-guard.mjs` hook prevents agents from taking shortcuts under pressure
(failing tests, healing loops, timeouts). Blocks `--no-verify`, `push --force`, and
`reset --hard` — the agent must fix the root cause, not bypass the quality check.

**Remote enforcement**: `templates/github-actions/e2e-evidence-check.yml` validates evidence
on PRs to main. Combined with branch protection, this creates server-side enforcement
that complements client-side hooks. See `templates/github-actions/branch-protection-setup.md`.

**If /implement skill is unavailable**, the pipeline MUST be executed manually step by step.
See `rules/GLOBAL_RULES.md` section "Pipeline Integrity" for the full contract.

## Remote Telemetry (v3.3)

Hooks can report to a remote MCP server for centralized state tracking.
Set `SPECBOX_ENGINE_MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp` in your shell profile.
Reporting is fire-and-forget — if the MCP is unreachable, hooks work normally.

## Remote State Management (v5.6.0)

Gestionar el estado de todos los proyectos desde iPhone via Claude.ai iOS + MCP remoto, y desde WhatsApp/Discord via OpenClaw Gateway.

### Heartbeat Protocol
- Hooks locales envian `project_state.json` al VPS tras cada operacion significativa
- `heartbeat-sender.mjs` auto-detecta: git branch, coverage, checkpoint, feedback
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

## Context Engineering (v5.24.0)

- Skills with `context: fork` run in isolated subagents — they don't pollute your main session
- /implement delegates phases to isolated Tasks with a **context budget of ~20,000 tokens per phase** (v5.24.0: expanded from 8,700 to leverage Opus 4.7 1M context window)
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
| `patrol-evidence-generator.js` | `.quality/scripts/patrol-evidence-generator.js --junit <xml> --screenshots <dir> ...` | Generate HTML Evidence Report from Patrol v4 results |
| `api-evidence-generator.js` | `.quality/scripts/api-evidence-generator.js --cucumber <json> --responses <dir> ...` | Generate HTML Evidence Report from Python API test results |
| `validate-results-json.js` | `.quality/scripts/validate-results-json.js <path> [--check-evidence]` | Validate results.json against contract (used by e2e-gate.mjs hook) |
| `specbox-audit.mjs` | `.quality/scripts/specbox-audit.mjs [path] [--json] [--fix] [--verbose]` | Compliance audit: version, hooks, settings, quality infra, skills, spec-driven |

## Agents (v5.24.0)

| ID | Rol | Archivo | Modelo |
|----|-----|---------|--------|
| AG-00 | Orchestrator | `agents/orchestrator.md` | opus |
| AG-01 | Feature Generator | `agents/feature-generator.md` | opus |
| AG-02 | UI/UX Designer | `agents/uiux-designer.md` | opus |
| AG-03 | DB Specialist | `agents/db-specialist.md` | sonnet |
| AG-04 | QA Validation | `agents/qa-validation.md` | sonnet |
| AG-05 | n8n Specialist | `agents/n8n-specialist.md` | sonnet |
| AG-06 | Design Specialist | `agents/design-specialist.md` | sonnet |
| AG-07 | Apps Script Specialist | `agents/appscript-specialist.md` | sonnet |
| AG-08 | Quality Auditor (interno, /implement) | `agents/quality-auditor.md` | sonnet |
| AG-09a | Acceptance Tester | `agents/acceptance-tester.md` | sonnet |
| AG-09b | Acceptance Validator | `agents/acceptance-validator.md` | **opus** (v5.24.0) |
| AG-10 | Developer Tester | `agents/developer-tester.md` | sonnet |
| AG-10 | Quality Auditor (externo, /audit) | `agents/ag-10-quality-auditor.md` | **opus** (v5.24.0) |

## Acceptance Engine (v3.8)

Pipeline completo de validacion funcional con jerarquia US → UC → AC:

1. **Definition Quality Gate** (`/prd` Paso 2.5) — Rechaza acceptance criteria vagos/no-testables antes de crear work items. Evalua especificidad, medibilidad y testabilidad (0-2 cada una).
2. **AG-09a Acceptance Tester** (`/implement` Paso 7.5) — Genera E2E/integration tests desde AC-XX del PRD con evidencia visual (screenshots, traces, response logs).
3. **AG-09b Acceptance Validator** (`/implement` Paso 7.7) — Validacion independiente por UC: verifica que cada AC-XX del UC esta implementado, testeado y evidenciado. Emite ACCEPTED/CONDITIONAL/REJECTED. US se considera ACCEPTED cuando todos sus UCs pasan.
4. **AG-10 Developer Feedback** (`/feedback`) — Captura feedback de testing manual. Crea evidencia local (FB-NNN.json) + GitHub issue. Puede INVALIDAR verdict de AG-09b. Severity critical/major bloquea merge.
5. **Merge Secuencial** (`/implement` Paso 8.5) — Auto-merge solo si AG-08=GO, AG-09=ACCEPTED y no hay feedback bloqueante. `complete_uc` → pull main → `find_next_uc` para siguiente UC.
6. **Evidence Pipeline** — PRD→US card, Plan→US card, AG-09→UC card, Delivery→US card (Markdown→PDF→Trello attachment).

Frameworks de acceptance testing por stack:

| Stack | Framework | Evidencia | Tests en | E2E Report |
|-------|-----------|-----------|----------|------------|
| Flutter Web | **Playwright E2E** (CanvasKit web build) | Screenshots + traces + HTML report | `e2e/acceptance/` | **OBLIGATORIO** |
| Flutter Mobile | **Patrol v4** (native automation) | Screenshots + `patrol-evidence-generator.js` | `test/acceptance/` | **OBLIGATORIO** |
| React | **Playwright E2E** (app web) | Screenshots + traces + HTML report | `tests/acceptance/` | **OBLIGATORIO** |
| Go | `testing` + `httptest` + `testcontainers-go` | Response logs + `api-evidence-generator.js` | `tests/acceptance/` | **OBLIGATORIO** |
| Python | pytest-bdd + httpx | Response logs + `api-evidence-generator.js` | `tests/acceptance/` | **OBLIGATORIO** |
| Google Apps Script | jest-cucumber | JSON only | `tests/acceptance/` | Legacy (sin soporte) |

Todos los stacks activos generan un **HTML Evidence Report** self-contained que el humano
puede abrir en cualquier browser. UI stacks embeben screenshots base64; Python embebe
response logs JSON formateados. El report tiene la misma estructura visual en todos los stacks.
Contrato formal: `doc/specs/results-json-spec.md`. Template: `doc/templates/e2e-evidence-report-template.md`.
Decisión arquitectónica: `doc/decisions/e2e-flutter-strategy.md`.

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

## Multi-Repo Mode (v5.20.1)

Opt-in support for projects with multiple repositories sharing a single spec board (orchestrator/satellite topology).

### Topology

- **Orchestrator**: Main repo with PRDs, designs, and spec board. Onboarded normally.
- **Satellite**: Secondary repo (e.g., backend, mobile). Inherits board from orchestrator.
- **Default**: Standard mono-repo behavior when multi-repo is not configured.

### Configuration

Satellite repos declare multi-repo in `.claude/settings.local.json` (never touched by `upgrade_project`):

```json
{
  "multirepo": {
    "enabled": true,
    "role": "satellite",
    "orchestrator": "../orchestrator-project"
  },
  "boardId": "inherited-from-orchestrator"
}
```

### Affected Components

| Component | Change |
|-----------|--------|
| `lib/config.mjs` | `getProjectConfig()` returns `orchestratorRoot` (defaults to `'.'`) |
| `design-gate.mjs` | Resolves Stitch designs from orchestrator repo |
| `e2e-gate.mjs` | Fallback validator script resolution from orchestrator |
| `onboard_project()` | New params `multirepo_role`, `orchestrator_project` |
| `find_next_uc()` | New `uc_scope` param to filter UCs by satellite |
| Registry/meta.json | Store `multirepo_role` and `multirepo_group` fields |

### Safety

- 100% backwards-compatible: all defaults reproduce mono-repo behavior
- Upgrade-safe: config lives in `settings.local.json`
- Install-safe: hook changes use additive patterns with fallbacks

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
- **MCP tools**: `run_acceptance_check(project_path, item_id, branch)`, `get_acceptance_report(project_path, uc_id)`, `get_e2e_gap_report(project_path, project)`
- **GitHub Action**: `templates/github-actions/acceptance-gate.yml`
- **Output**: PR-comment-ready Markdown with per-AC verdict

## E2E Gap Detection (v5.12.0)

Deteccion automatica de UCs sin evidencia E2E durante el upgrade de proyectos:

- **MCP tool**: `get_e2e_gap_report(project_path, project)` — escanea PRDs, detecta UCs sin HTML Evidence Report, propone plan de testing
- **Integrado en upgrade**: `upgrade_project` incluye `e2e_alignment` hint que recomienda ejecutar el gap report
- **Integrado en matrix**: `get_version_matrix` incluye `e2e_gap_hint` para post-upgrade
- **Output**: Coverage % por UC, lista de ACs sin evidencia, plan propuesto con framework y directorio por stack
- **Flujo**: upgrade_project → copiar files → get_e2e_gap_report → plan E2E → ejecutar tests → evidencia completa

## Contextual Hints (v5.0)

- Hints shown first 3 times a skill is used in a project (then disappear)
- Counter stored in `.quality/hint_counters.json`
- Not shown if project has > 5 completed UCs
- MCP tools: `get_skill_hint(project_path, skill_name)`, `record_skill_hint(...)`

## Public Benchmarking (v5.0)

- **MCP tool**: `generate_benchmark_snapshot(output_path)` — aggregated, anonymized metrics
- **REST endpoint**: `GET /api/benchmark/public` — JSON metrics (no auth required)
- **Output**: `docs/benchmarks/snapshot_{date}.md` with Metodología section

## Quality Audit — ISO/IEC 25010 (v5.22)

On-demand auditoría de calidad de software bajo estándar SQuaRE. Invocación
manual via `/audit [project]`, nunca automática. Produce PDF con brand
embed.build + JSON schema v1.0 persistidos como evidencia del proyecto.

### Características auditadas (8 bloques)

1. **Functional Suitability** — completeness via AC status + AG-09 verdicts
2. **Performance Efficiency** — large files, hot-path heuristics, perf config presence
3. **Compatibility** — lockfile presence, declared engine versions, infra
4. **Usability** — README, CLAUDE.md, docs, Stitch designs
5. **Reliability** — healing ratio + test pass rate
6. **Security** — semgrep (OWASP Top 10) + gitleaks (secrets) + pip-audit/npm audit (deps) + checkov (IaC)
7. **Maintainability** — **mix 60/40 documentado**: 60% clásico (lizard, jscpd, file size, test ratio) + 40% SpecBox (AC, evidencia, healing, board, PRD divergence)
8. **Portability** — Dockerfile/compose, .env.example, hardcoded paths scan

Cada bloque emite: `score` 0-100, `traffic_light`, `raw_metrics`,
`findings[]` con severidad, `recommendations[]` priorizadas por AG-10.

### Herramientas externas (instalación perezosa)

Todas son **opcionales**. Al lanzar `/audit`, el skill:
1. Llama `check_audit_tools_status(project_path)` — detecta qué falta.
2. Si faltan, pregunta al usuario: instalar / continuar sin ellas / cancelar.
3. Si instala → ejecuta `.quality/scripts/install-audit-tools.sh --yes`.
4. Si continúa sin ellas → el audit reporta gaps en `tools_used` sin abortar.

Nada se instala durante `install.sh` o `upgrade_project`. Install completamente
on-demand y consentido.

| Tool | Para | Installer | Stack hint |
|------|------|-----------|------------|
| semgrep | SAST OWASP Top 10 | `uv pip install semgrep` | multi |
| gitleaks | Secret scanning | `brew install gitleaks` (macOS) / `go install ...` | multi |
| pip-audit | Python deps | `uv pip install pip-audit` | python |
| npm | Node/JS deps | Node.js install | react/node |
| checkov | IaC | `uv pip install checkov` | si hay Dockerfile/TF |
| lizard | Cyclomatic complexity | `uv pip install lizard` | multi |
| jscpd | Duplication | `npm install -g jscpd` | multi |

### MCP tools (4)

| Tool | Uso |
|------|-----|
| `run_quality_audit(project, scope, project_path)` | Ejecuta los 8 analizadores y devuelve `QualityReport` bruto + `audit_tools_status` |
| `attach_audit_evidence(project, report)` | Persiste PDF + JSON bajo `evidence/audits/` y actualiza `project_meta.last_audit` |
| `get_last_audit(project)` | Devuelve el resumen del último audit registrado en `meta.json` |
| `check_audit_tools_status(project_path)` | Reporta qué tools externas están instaladas / faltan + comandos de instalación |

### Agente AG-10 Quality Auditor

Distinto de **AG-08** (gate interno por fase en `/implement`). AG-10 es
externo, on-demand, no bloqueante, y su responsabilidad es **sintetizar**
justificaciones y recomendaciones sobre el `QualityReport` bruto que
produce el tool — nunca modifica código ni ejecuta tests.

Definición: `agents/ag-10-quality-auditor.md`.

### Evidencia persistida

```
STATE_PATH/projects/<project>/evidence/audits/
  audit_YYYYMMDDTHHMMSSZ.json    ← schema v1.0
  audit_YYYYMMDDTHHMMSSZ.pdf     ← brand embed.build, NumberedCanvas
```

El `project_meta.last_audit` se actualiza tras `attach_audit_evidence` para
que la Sala de Máquinas muestre el último audit sin escanear el filesystem.

### Fuera de alcance v1 (reservado para v2)

- Hooks automáticos post-`/implement`
- Gates bloqueantes por score mínimo
- Histórico / tendencias / diffs entre auditorías
- Dashboard web dedicado
- Integración con CI/CD externo

## Engine Version

Current: v5.25.0 "Stripe Connect"
Brand: SpecBox Engine (SpecBox Engine by JPS)
Config: ENGINE_VERSION.yaml
