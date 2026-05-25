# SpecBox Engine v6.0.2

> **SpecBox Engine by JPS**
> Sistema de programacion agentica para Claude Code.
> Monorepo unificado: engine + MCP server + Gherkin BDD + Quality Audit ISO/IEC 25010 + Product Discovery. Tracking multi-developer corre sobre Supabase y se consume desde **specbox_cloud** (panel web externo).

## Que es este repositorio

Este repositorio es un **monorepo unificado** con el sistema completo de programacion agentica para Claude Code. Incluye:

- **Commands** (`/prd`, `/visual-setup`, `/plan`, `/implement`, `/adapt-ui`, `/optimize-agents`, `/feedback`) — flujo completo de desarrollo
- **Agent Teams** — configuracion para orquestacion multi-agente nativa de Claude Code
- **Architecture** — patrones por stack (Flutter, React, Python, Google Apps Script)
- **Infrastructure** — patrones por servicio (Supabase, Neon, Stripe, Firebase, n8n)
- **Design** — integracion con Google Stitch MCP para diseño UI + VEG (Visual Experience Generation)
- **Templates** — CLAUDE.md, settings.json, team-config para nuevos proyectos
- **Agents** — templates genericos de roles especializados
- **Server** — MCP server unificado (FastMCP, JSON-RPC + minimal `/health`)
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

## Native Backend (v5.34.0)

Cuarto backend del `SpecBackend` ABC (junto a Trello / Plane / FreeForm), respaldado
por una instancia gestionada de Supabase Postgres. Pensado para **colaboración
multi-developer**: un único board source-of-truth compartido entre varios developers,
con concurrencia optimista para que dos personas no pisen el mismo trabajo.

Es **opt-in por proyecto** y **aditivo** — no reemplaza a ningún backend. Los tres
backends existentes siguen siendo el default; `auth_gateway.py` despacha a
`NativeBackend` solo cuando `backend_type='native'`.

```
set_auth_token(api_key="", token="<dev-token>", backend_type="native", project_id="<proj>")
```

| Componente | Archivo | Rol |
|------------|---------|-----|
| NativeBackend | `server/backends/native_backend.py` | 26 métodos del ABC sobre pool asyncpg |
| Schema multi-tenant | `server/db/migrations/0001_native_schema.sql` | Tablas US/UC/AC + concurrencia optimista (`expected_version`) |
| Identity | `0002_developers.sql` + `0004_github_identities.sql` + `0005_mcp_tokens.sql` + `server/coordination/identity.py` | Resolución token→developer vía `mcp_tokens` JOIN `developers` (filtrando `revoked_at IS NULL`). N:1 GitHub identity ↔ developer cubre el caso freelance. Frontier 1 authz (UNAUTHENTICATED / FORBIDDEN). v5.34.1. |
| Reservations + branches | `0003_claims.sql` + `0007_rename_claims_to_reservations.sql` + `server/coordination/{reservations,branches}.py` | Reserva exclusiva de UC por developer + registro de rama feature. v5.35.0 renombró tabla, módulo, tools y vocabulario (US-CLAIM-RENAME). |
| Mutation gate + audit | `server/coordination/identity.py` (`authenticate_and_authorize_cached`, TTL 30s hardcoded) + `server/coordination/audit.py` + `server/db/migrations/0006_audit_log.sql` | Cada uno de los 9 mutadores del NativeBackend re-valida identidad + membresía con cache (hit ~1µs / miss ~10-25ms). Tras un revoke, exposición ≤ 30s. `delete_acceptance_criterion` y `archive_item` escriben fila en `audit_log` tras SQL exitoso. v5.34.1. |
| Tools MCP nativas | `server/tools/coordination.py` | `whoami`, `reserve_uc`, `release_uc`, `register_native_branch`. **CRUD de developers / mcp_tokens / github_identities NO se expone como tool MCP** desde v5.34.1 — vive en el SpecBox Control Panel (panel web externo). v5.35.0 también registra el alias deprecado `claim_uc` (con `DeprecationWarning` + payload dual) que se elimina en v5.37.0. |

**Nota de vocabulario (v5.35.0 — US-CLAIM-RENAME)**: desde v5.35.0 el concepto antes
llamado **"claim"** se llama **"reservation"** end-to-end: tabla `uc_reservations`,
módulo `coordination/reservations.py`, tool MCP `reserve_uc`, payload `reserved_at`,
códigos `ALREADY_RESERVED` / `NOT_RESERVATION_OWNER`. Las tools MCP `claim_uc` y el
código `ALREADY_CLAIMED` están **deprecados** desde v5.35.0 (emiten
`DeprecationWarning` + devuelven payload dual con ambos vocabularios) y se eliminan
en **v5.37.0** (UC-612). Rationale: "claim" es jerga (claim check pattern, JWT
claims) — "reservation" es transparente para no técnicos.

**Frontier 2 — seguridad de credenciales**: el DSN de la base vive exclusivamente en la
variable de entorno `SPECBOX_NATIVE_DSN`. Nunca se persiste en disco ni en `meta.json`,
de modo que una fuga de board export o config no expone acceso a la base.

Postgres dev local para verificar migraciones y tests:
```bash
docker compose -f docker-compose.dev.yml up -d   # postgres:16, puerto 55432, db specbox_native
```

La suite native (`tests/test_native_*.py`) corre verde contra una instancia Supabase
gestionada del mantenedor (Postgres 17+): 50 passed, 0 skipped. Cada operador del
MCP es responsable de provisionar su propia instancia Supabase.

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
│   │   └── post-implement-validate.mjs
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
├── server/                ← MCP server unificado
│   ├── server.py          ← FastMCP (JSON-RPC + minimal /health)
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
│   ├── tools/             ← tool modules
│   │   ├── engine.py      ← version, status, stacks
│   │   ├── plans.py
│   │   ├── quality.py
│   │   ├── skills.py
│   │   ├── features.py
│   │   ├── telemetry.py
│   │   ├── hooks.py
│   │   ├── onboarding.py
│   │   ├── state.py
│   │   ├── spec_driven.py ← backend-agnostic via SpecBackend
│   │   ├── spec_mutations.py
│   │   ├── milestone_management.py
│   │   ├── board_operations.py
│   │   ├── acceptance_automation.py
│   │   ├── _mutation_helpers.py
│   │   ├── migration.py   ← Trello ↔ Plane migration
│   │   ├── stitch.py      ← Stitch MCP proxy
│   │   ├── acceptance.py
│   │   ├── benchmark.py
│   │   ├── hints.py
│   │   ├── skill_registry.py
│   │   ├── sync.py        ← Spec-Code Sync (get/write implementation status)
│   │   ├── coordination.py ← Native: whoami, reserve_uc, release_uc, register_native_branch
│   │   └── audit.py       ← submit_quality_audit + helpers
│   ├── stitch_client.py
│   ├── trello_client.py
│   ├── board_helpers.py
│   ├── models.py
│   ├── pdf_generator.py
│   ├── auth_gateway.py    ← Per-session credentials (multi-backend)
│   └── resources/         ← MCP Resources
├── tests/                 ← Tests unificados
├── Dockerfile             ← Single-stage Python (v6.1.0)
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

## Available Skills (v5.30)

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
| /release | "release", "bump version", "sube version", "prepara release" | direct | Full | v5.8 — Audit residuals + update version/changelog/docs + push |
| /compliance | "check compliance", "audit specbox", "specbox audit", "is specbox up to date" | direct | Bash+Read | v5.18 — Compliance audit + version alignment + auto-fix |
| /audit | "audit project", "quality audit", "ISO 25010", "SQuaRE audit" | direct | Full | v5.22 — Quality Audit ISO/IEC 25010 on-demand (AG-10, 8 analyzers, PDF+JSON) |
| /stripe-connect | "stripe connect", "marketplace billing", "integrar pagos marketplace" | direct | Full | v5.25 — Marketplace Connect (Express + Direct charges + subscriptions embedded) + Supabase + React/Flutter |
| /stripe-standard | "stripe standard", "stripe sin connect", "subscriptions saas", "billing saas", "monta pagos saas" | direct | Full | v5.27 — Stripe Standard (no Connect) + 4 modalidades (single/tiered/metered/one_shot) + Supabase + React/Flutter |
| /stripe-switch-account | "switch stripe account", "rotar cuenta stripe", "cambiar cuenta stripe" | direct | Full | v5.27 — Stripe credentials rotation (alias store + switch_stripe_account tool, both Standard and Connect modes, dry-run + automatic rollback) |
| /handoff | "handoff", "save state", "guarda contexto", "voy a hacer compactación" | direct | Read+Bash+Write | v5.30 — Persiste estado fino a `.quality/handoff.md` + Engram structured. **Llamar ANTES de proponer compactación**. |
| /switch-backend | "switch backend", "cambiar backend", "migrar de FreeForm a Trello/Plane/Native", "mover el tracking a" | direct | Full | v5.35 — Cambio guiado de backend N×N entre los 4 (FreeForm/Trello/Plane/Native). Preview obligatorio + confirmación literal + switch transaccional (3 lugares con rollback) + regenerate_evidence opt-in. Migración aditiva, no destruye origen. |

## Hooks (v5.34.0)

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
| **healing-budget-guard** | PreToolUse (Write/Edit) | **BLOCKING**: counts healing.jsonl entries per feature. Blocks at 8 attempts (HARD limit). Prevents infinite healing loops. |
| **pipeline-phase-guard** | PreToolUse (Write/Edit) | **BLOCKING**: reads pipeline_state.json to verify phase dependencies are met. Prevents out-of-order execution (e.g., feature code before DB). |
| **stripe-safety-guard** | PreToolUse (Write/Edit on billing paths) | **BLOCKING**: scans `src/billing/`, `lib/billing/`, `supabase/functions/stripe-*`. Blocks 5 anti-patterns: sk_live_* hardcoded, webhook sin firma, webhook sin idempotencia (`stripe_processed_events`), `redirectToCheckout`/`ui_mode:hosted`, Payment Links. Escape hatches: `// stripe-safety-guard:ignore` / `:disable-file`. v5.25 — scaffoldeado por `/stripe-connect`. |
| checkpoint-freshness-guard | PostToolUse (git commit) | Non-blocking WARNING: warns if checkpoint is stale (>30min) or missing during active UC implementation. |
| uc-lifecycle-guard | PostToolUse (git push) | Non-blocking WARNING: warns if pushing feature branch without calling move_uc (board out of sync). |
| **session-start** | SessionStart | Non-blocking: injects `.quality/handoff.md` (if fresh), active UC + checkpoint, and auto zones from `app_spec.md` as `additionalContext` for the new session. Capped at 14k chars. v5.30. |
| **pre-read-budget-guard** | PreToolUse (Read) | Non-blocking WARNING: estimates tokens for the file being read; warns if ≥ `specbox.context_budget.warn_pct` of the window (default 5% of 1M). v5.30. |
| **stitch-quota-guard** | PreToolUse (mcp__SpecBox-MCP__stitch_*) | WARNING ≥80% PRO/Flash; **BLOCKING** when PRO is exhausted AND `flash_safety_net=false`. Reads cached quota from `.quality/stitch_quota.json` (written by `get_stitch_quota_status`). No-op when no cache. v5.31. |
| **freeform-path-guard** | PreToolUse (mcp__SpecBox-MCP__set_auth_token, mcp__SpecBox-MCP__onboard_project) | Auto-rewrites relative FreeForm `root_path` / `freeform_root_absolute` to an absolute path resolved against `git rev-parse --show-toplevel` via `hookSpecificOutput.updatedInput`. Covers the implicit-default case (`onboard_project` with no `backend_type` AND no `trello_board_name`). **BLOCKING** (exit 2) only when CWD is not a git repo and resolution is ambiguous. Logs every rewrite to `.quality/logs/freeform-path-rewrites.jsonl`. Defense in depth on top of the v5.29 server-side guard. v5.33. |

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

## Cross-project state (v6.1.0 Cloud Cutover)

El dashboard "Sala de Máquinas" (frontend React + REST `/api/*` + hooks de
heartbeat + skill `/remote` + GitHub sync) **fue eliminado en v6.1.0**. La
visión multi-proyecto vive ahora en **specbox_cloud** (panel web externo),
que se alimenta leyendo directamente la instancia Supabase del Native
Backend y llamando al MCP cuando necesita escribir reservations.

Consecuencias prácticas:

- Ya no existen los hooks `heartbeat-sender.mjs`, `mcp-report.mjs`,
  `e2e-report.mjs`, ni el archivo `specbox-state.json` en la raíz del repo.
- Ya no se exponen tools `get_project_live_state`, `get_all_projects_overview`,
  `get_active_sessions`, `refresh_project_state`, `get_heartbeat_stats`.
- El env var `SPECBOX_SYNC_TOKEN` deja de tener sentido y debe quitarse del
  shell profile si lo tenías.
- El MCP server local sigue exponiendo un endpoint `/health` mínimo para el
  HEALTHCHECK del Dockerfile, sin telemetría.

Proyectos onboarded en v5.x con los hooks viejos no se rompen: los `spawn`
de heartbeat-sender fallan silenciosamente con `ENOENT`. Para limpiar a
fondo, re-ejecutar `./install.sh` desde v6.1.0 o borrar manualmente los
3 archivos `.mjs` mencionados arriba.

## Context Engineering (v5.24.0)

- Skills with `context: fork` run in isolated subagents — they don't pollute your main session
- /implement delegates phases to isolated Tasks with a **context budget of ~20,000 tokens per phase** (v5.24.0: expanded from 8,700 to leverage Opus 4.7 1M context window)
- Read-only Skills (explore, optimize-agents, adapt-ui) cannot modify files
- File ownership per agent is documented in .claude/skills/implement/file-ownership.md
- Context budget estimator: `.quality/scripts/context-budget.sh <path> [--detail]`
- Session context metrics logged automatically via on-session-end hook
- Full context engineering rules in `rules/GLOBAL_RULES.md` section "Context Engineering"

## Session Continuity (v5.30.0)

SpecBox provee persistencia de sesión más rica que la compactación nativa de Claude Code. Antes de proponer al usuario "compactar", "iniciar nueva sesión" o `/clear`:

1. **Ejecutá `/handoff`** — persiste el estado fino de la sesión a `.quality/handoff.md` y a Engram como observación estructurada con topic `session:<project>:<branch>`.
2. Confirmá al usuario que el handoff fue exitoso (validador: `node .quality/scripts/validate-handoff.mjs .quality/handoff.md`).
3. Solo entonces, sugerí compactar/cerrar.

La nueva sesión arranca con el handoff cargado vía hook `session-start.mjs`, que inyecta:
- El contenido completo de `.quality/handoff.md` si existe y es < 24h ([FRESH]) o con marca [STALE] si es más viejo.
- Si no hay handoff: UC activo + último checkpoint + zonas auto de `app_spec.md` (tracking_backend, autopilot, stack).
- Output capeado a 14 000 caracteres (~3.5k tokens).

**Cuándo es obligatorio el handoff**:
- Antes de proponer compactación al usuario.
- Antes de `/clear`.
- Cuando hay UC activo (`.quality/active_uc.json` existe).
- Cuando hay checkpoint < 30 min.

**Cuándo es opcional**:
- Cierre voluntario sin trabajo en progreso.
- Sesiones puramente exploratorias.

**Anti-pattern**: ejecutar `/handoff` en cada turno. Una vez por sesión (o antes de compactar) basta. El handoff es idempotente pero pesa contra el contexto.

Componentes:
- Skill: `.claude/skills/handoff/SKILL.md`
- Builder: `.claude/hooks/lib/handoff-builder.mjs` (puro, testeable)
- SessionStart hook: `.claude/hooks/session-start.mjs`
- Validador: `.quality/scripts/validate-handoff.mjs`
- Spec: `doc/specs/handoff-spec.md`
- Pre-read budget guard: `.claude/hooks/pre-read-budget-guard.mjs` (warning no bloqueante para Read >5% de la ventana)

## Quality Scripts

| Script | Usage | Purpose |
|--------|-------|---------|
| `create-baseline.sh` | `.quality/scripts/create-baseline.sh [path]` | Generate initial quality baseline |
| `update-baseline.sh` | `.quality/scripts/update-baseline.sh [path]` | Ratchet-safe baseline update (only improves) |
| `analyze-sessions.sh` | `.quality/scripts/analyze-sessions.sh [--last N]` | Telemetry: sessions, context tokens, healing, checkpoints |
| `context-budget.sh` | `.quality/scripts/context-budget.sh <path> [--detail]` | Estimate token cost of files/directories |
| `design-baseline.sh` | `.quality/scripts/design-baseline.sh [path] [--update\|--init]` | Measure design compliance, enforce ratchet (L0/L1/L2) |
| `maestro-evidence-generator.js` | `.quality/scripts/maestro-evidence-generator.js --junit <xml> --screenshots <dir> ...` | Generate HTML Evidence Report from Maestro results (v5.28+, recommended for Flutter Mobile) |
| `patrol-evidence-generator.js` | `.quality/scripts/patrol-evidence-generator.js --junit <xml> --screenshots <dir> ...` | Generate HTML Evidence Report from Patrol v4 results (legacy Flutter Mobile) |
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

## Maestro Flutter E2E (v5.28.0)

Maestro (mobile-dev-inc) es el runner **recomendado por defecto** para Flutter Mobile desde v5.28. Patrol v4 sigue soportado como ruta legacy y se mantiene para casos que requieran acceso a estado interno Dart o aserciones que YAML no expresa bien.

### Por qué Maestro

- **Anti-flakiness por diseño**: auto-retry y wait-for-stability built-in. Resuelve la mayor parte del dolor histórico con Patrol en CI.
- **YAML, no Dart**: QA y PMs pueden escribir flows. Misma semántica BDD que el resto del engine.
- **Black-box cross-platform**: el mismo flow YAML corre en iOS y Android.
- **Production builds testables**: opera sobre APK/IPA reales, no requiere debug/profile.

### Cuándo elegir Patrol en lugar de Maestro

- El test necesita leer estado Dart-side (Provider, BLoC, GetIt singleton)
- Necesitas mockear servicios desde el lado app desde el test
- Ya tienes una suite Patrol estable y migrar no aporta ROI

### Integración en SpecBox

- **Adapter de stack**: `architecture/flutter/maestro-setup.md` (instalación, semantics, YAML, troubleshooting)
- **Generator de evidencia**: `.quality/scripts/maestro-evidence-generator.js` produce el mismo HTML Evidence Report y `results.json` que Patrol — AG-09b no distingue el origen
- **Template CI**: `templates/github-actions/maestro-e2e.yml` (Android emulator + iOS simulator)
- **Source en results.json**: `maestro-junit-xml` (registrado en `doc/specs/results-json-spec.md`)
- **Hook compatibility**: `e2e-gate.mjs` y `validate-results-json.js` aceptan Maestro sin cambios — el contrato es source-agnostic

### Limitaciones conocidas (heredadas)

- **Flutter Web sobre CanvasKit es frágil** (mismo techo que Playwright) — SpecBox sigue usando Playwright para Web
- **Flutter Desktop NO soportado** por Maestro
- **iOS solo en inglés** para diálogos del sistema (mismo issue que Patrol)
- **Maestro Cloud (paralelización)** es paid — la CLI local gratis ejecuta serial

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

## Stitch Autopilot (v5.31.0 + /plan migration v5.31.1)

Capa que se asienta encima del Stitch MCP Proxy v1 para resolver los bloqueos
recurrentes de autopilot causados por (a) drift visual entre pantallas, (b)
fallos terminales de generación sin recuperación, (c) falta de visibilidad
sobre la cuota mensual de Google Stitch (350 Standard + 200 Experimental, sin
upgrade), y (d) prompts mal estructurados que producen primeras generaciones
peores de lo necesario.

**v5.31.1 update**: `/plan` ya está migrado al pipeline v2. Cada generación
pasa por `validate_stitch_prompt` → `stitch_generate_screen_v2` (con fallback
chain) y los planes con >5 pantallas usan `stitch_build_site_batched_v2`. Ver
Paso 5.5 (pre-check DESIGN.md + cuota) y Paso 6.3/6.7 del SKILL.md de `/plan`.

**Decisión de calidad**: el modelo default sigue siendo `GEMINI_3_PRO`. Flash
NO es default — solo está disponible como red de seguridad opt-in
(`specbox.stitch.fallback.flash_safety_net=false` por defecto).

### 5 capas (todas aditivas, v1 sigue funcionando)

1. **DESIGN.md canónico** — formato oficial Google
   ([google-labs-code/design.md](https://github.com/google-labs-code/design.md)).
   `/visual-setup` Paso 3.7 invoca `generate_design_md_tool` que sintetiza
   `doc/design/DESIGN.md` (YAML front-matter + Markdown body) desde Brand Kit
   + VEG + canónicos `app_prd.md` / `app_spec.md`. Cuando faltan inputs,
   completa desde 6 arquetipos VEG (corporate / startup / creative / consumer
   / gen_z / gov). `upload_design_md_to_stitch` lo registra contra el
   proyecto Stitch en modo `inline-prefix` (Stitch MCP no expone hoy un
   endpoint nativo de attach — el contenido se prepende al prompt).

2. **Prompt template 4-capas + validador** — Context (≤80 palabras) /
   Components (lista) / Style (hex codes) / Platform.
   `validate_stitch_prompt` corre por defecto en modo `warn` (errores
   reportados pero no bloqueantes durante 2 semanas para medir falsos
   positivos antes de promover a `strict`). Detecta E1 colores nombrados
   (auto-resuelve contra DESIGN.md), E2 prompts que mezclan layout +
   componentes (propone split layout-first / components-second), W1
   longitud >500 chars (excluye prefijo DESIGN.md), W2 Layer 1 verbosa,
   W3 Layer 2 escrita como prosa.

3. **Fallback chain** — `stitch_generate_screen_v2` aplica el ladder
   `edit_baseline → variants_refine → regenerate` cuando la llamada
   natural falla. Clasifica el error (`transient | quota | content |
   unknown`) para decidir si reintentar. Si todas las estrategias PRO
   fallan AND `flash_safety_net=true`, último intento con
   `GEMINI_3_FLASH` marcando el resultado `degraded=true`.

4. **Batched build_site** — `stitch_build_site_batched_v2` particiona
   pantallas en grupos de ≤4 (priorizando tag `group` explícito, luego
   prefijo de `route`, luego chunks ordenados) y aplica una pasada final
   de `edit_screens` con un prompt de unificación de tema cuando hay >1
   batch. Resuelve el límite duro de ~5 pantallas conectadas por
   `build_site` que Google reporta en foros.

5. **Quota tracking + safety net opt-in** —
   `get_stitch_quota_status` agrega `stitch_usage.jsonl` por mes y modelo,
   surfacea warning a ≥80% y mensaje de exhausted a 100%, y persiste un
   cache compacto en `.quality/stitch_quota.json` para el hook
   `stitch-quota-guard.mjs`. El hook (PreToolUse para tools
   `mcp__SpecBox-MCP__stitch_*`) warnea ≥80% y bloquea (exit 2) cuando
   PRO está exhausted Y `flash_safety_net=false`.

### Settings (`templates/settings.json.template` → `stitch`)

```json
{
  "stitch": {
    "modelId": "GEMINI_3_PRO",
    "fallback": {
      "enabled": true,
      "strategy": ["edit_baseline", "variants_refine", "regenerate"],
      "flash_safety_net": false,
      "max_total_attempts": 3
    },
    "quota": {
      "warn_pct": 80,
      "standard_limit": 350,
      "experimental_limit": 200
    },
    "prompt": { "validator_mode": "warn" }
  }
}
```

### Compatibilidad

- 100% backwards-compatible: las 13 tools v1 siguen registradas. Las 6 tools v2
  son aditivas (`generate_design_md_tool`, `upload_design_md_to_stitch`,
  `validate_stitch_prompt`, `stitch_generate_screen_v2`,
  `stitch_build_site_batched_v2`, `get_stitch_quota_status`).
- `/plan` Paso 6 fue migrado al pipeline v2 en v5.31.1 (esta release).
  Antes de v5.31.1 `/plan` usaba `mcp__stitch__generate_screen_from_text`
  directo; desde v5.31.1 valida prompts antes de generar y usa
  `stitch_generate_screen_v2` con fallback chain.
- Solo se modifica `/visual-setup` (añade Paso 3.7 + 3.8).

### Plan completo

[doc/plans/v5.31.0_stitch_autopilot_plan.md](doc/plans/v5.31.0_stitch_autopilot_plan.md)
documenta los 5 cambios, fases de implementación, riesgos, métricas de
éxito y rollback plan.

## SpecBox-Stripe MCP (v0.1 alpha — independent package)

Setup-as-code para Stripe, complementando al Stripe MCP oficial (que cubre runtime de negocio pero no setup). Empaquetado como `packages/specbox-stripe-mcp/` con stack Python + FastMCP + stripe SDK — mismo runtime que el engine pero versionado y desplegado de forma independiente.

### Tools (H1 MVP)

| Tool | Uso |
|------|-----|
| `verify_connect_enabled` | Gate de entrada: ¿puede esta platform crear cuentas Connect Express? Canary create+delete. |
| `setup_webhook_endpoints` | Crea o reutiliza los 2 webhook endpoints (platform + connect) con eventos correctos. Idempotente por metadata + url + connect. Recupera secret con `expand=['secret']` en reuse. |
| `setup_products_and_prices` | Reconcilia catálogo por `tier_key`. Products mutables, prices inmutables (shape drift → new price + archive old). |
| `get_setup_status` | Health check read-only. Verdict ∈ {ready, partial, not_setup} + remediation_steps. |

### Principios

- Idempotencia por `metadata.specbox_managed="true"` + lookup key natural (url, tier_key, seller_idx).
- Test-mode por defecto; `sk_live_*` rechazado salvo `allow_live_mode=true` + token literal.
- Evidencia fire-and-forget: cada call escribe observación Engram + heartbeat `stripe_mcp_call` al engine, pero ningún fallo en esas integraciones rompe la tool.
- Secrets nunca a disco — se devuelven al caller, que los inyecta vía `specbox-supabase.set_edge_secret` (PRD hermano, pendiente).

### Roadmap

- **H1 (v0.1 alpha)** — T1-T4 + telemetría + tests ✅ (88% coverage, 98 unit + integration suite gated por `STRIPE_CI_SECRET_KEY`)
- **H2 (v1.0 GA)** — integración con `/stripe-connect` Paso 9.5 (bloqueado por set_edge_secret), docs públicas, benchmarks
- **H3 (v1.1)** — `setup_test_sellers`, `teardown_test_mode`, alias store, OAuth v2

### Referencias

- PRD: [doc/prd/specbox_stripe_mcp_prd.md](doc/prd/specbox_stripe_mcp_prd.md)
- README: [packages/specbox-stripe-mcp/README.md](packages/specbox-stripe-mcp/README.md)
- Tracking: FreeForm backend `ff-2051992d4368`, US-SPECBOX-STRIPE

## SpecBox-Supabase MCP (v0.1 alpha — independent package)

Setup-as-code para Supabase Edge Function secrets, complementando al MCP oficial de Supabase (que no cubre secrets management — gap en [supabase-community/supabase-mcp#120](https://github.com/supabase-community/supabase-mcp/issues/120)). Cierra la última acción manual del flujo `/stripe-connect`: inyectar los 4 secrets de Stripe en las Edge Functions del proyecto. Empaquetado como `packages/specbox-supabase-mcp/` con stack Python + FastMCP + httpx + Supabase Management API.

### Tools (H1 MVP)

| Tool | Uso |
|------|-----|
| `set_edge_secret` | Bulk POST /v1/projects/{ref}/secrets. Idempotente (GET previo para computar previously_present/absent). Valores NUNCA en logs ni Engram. |
| `list_edge_secrets` | GET read-only. Devuelve nombres + updated_at (nunca valores). Si expected_names, computa missing_names/extra_names. |
| `unset_edge_secret` | Bulk DELETE con confirm_token literal. Pre-action Engram audit observation antes del DELETE. |

### Principios

- Idempotencia por existence-by-name (la API de Supabase sobrescribe bulk POST).
- Test-mode not applicable (Supabase no tiene modos); seguridad destructiva vía `confirm_token` literal en unset.
- PAT redactado en logs (`sbp_****<last6>`); valores de secrets nunca persisten.
- Reuso de `lib/response.py`, `lib/engram_writer.py`, `lib/heartbeat.py` vía copy-from-stripe (Opción A del PRD §6).

### Integración con /stripe-connect

Paso 9.5 de la skill invoca `set_edge_secret` con los 4 secrets obtenidos de los pasos 9.5.2 previos. Graceful degradation si el MCP no está registrado (fallback a copy-paste manual en dashboard).

### Roadmap

- **H1 (v0.1 alpha)** — T1 (set), T2 (list), T3 (unset) + telemetría + tests + docs + integración con `/stripe-connect` ✅ (91% coverage)
- **H2 (v1.1)** — `base_url` self-hosted support (parcialmente implementado), alias store para PATs multi-proyecto

### Referencias

- PRD: [doc/prd/specbox_supabase_mcp_prd.md](doc/prd/specbox_supabase_mcp_prd.md)
- README: [packages/specbox-supabase-mcp/README.md](packages/specbox-supabase-mcp/README.md)
- Tracking: FreeForm backend `ff-2051992d4368`, US-SPECBOX-SUPABASE (7 UCs, 36 ACs)

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
que cualquier consumidor (incluido specbox_cloud) muestre el último audit
sin escanear el filesystem.

### Fuera de alcance v1 (reservado para v2)

- Hooks automáticos post-`/implement`
- Gates bloqueantes por score mínimo
- Histórico / tendencias / diffs entre auditorías
- Dashboard web dedicado
- Integración con CI/CD externo

## Cognitive Load Reduction (v5.29.0)

Sistema de documentos canónicos `doc/app/app_prd.md` y `doc/app/app_spec.md` que `/prd`, `/plan` y `/visual-setup` consultan en su Paso 0.0 para evitar repreguntar al usuario lo que ya está decidido a nivel de proyecto. Se complementa con un motor de autopilot de 4 niveles (low / conservador / equilibrado / agresivo) que reduce las interrupciones por feature de ≥17 (baseline v5.28) a ≤8 en el preset por defecto `equilibrado`.

### Documentos canónicos (`doc/app/`)

| Archivo | Contenido | Mantenedor |
|---------|-----------|------------|
| `app_prd.md` | Visión, audiencia + JTBD, perímetro v1/v2/never, métricas, roadmap de US, stakeholders | usuario (5 zonas manual) + engine (1 zona auto: roadmap) |
| `app_spec.md` | Stack, tracking backend, brand & visual, convenciones, autopilot, decisiones canónicas | engine (3 zonas auto: stack, tracking_backend, autopilot) + usuario (2 manual) + ambos (1 hybrid: canonical_decisions) |

Cada documento se divide en **zonas con políticas distintas**: `manual` (solo usuario), `auto` (engine reescribe tras eventos), `hybrid` (append-only, ambos contribuyen). Las zonas se delimitan con marcadores HTML `<!-- @specbox:zone start kind="..." id="..." -->` invisibles en renderizado.

### Skills v5.29.0

| Skill | Trigger | Modo | Propósito |
|-------|---------|------|-----------|
| `/app-init` | "app init", "init app docs", "create canonical docs" | direct | Crea o refresca `doc/app/app_prd.md` y `doc/app/app_spec.md`. 3 modos: init (5 preguntas mínimas), refresh (solo zonas auto), upgrade-zones (insertar marcadores en docs manuales). |
| `/app-sync` | "app sync", "check app drift", "reparar app docs" | direct | Verifica/repara/revisa drift entre canónicos y realidad. 4 subcomandos: --check, --repair, --review, --rebuild-from-tracking. |
| `/queue review` | "queue review", "revisar cola", "resolver pendientes" | direct | Procesa decisiones diferidas en `doc/app/decisions_queue.md`. Off por default (`autopilot.queue_enabled=false`). |

### Autopilot

Configuración en `.claude/settings.local.json`:

```json
{
  "specbox": {
    "backend_type": "freeform",
    "freeform_root_absolute": "/Users/.../doc/tracking",
    "autopilot": {
      "level": "equilibrado",
      "image_budget_eur_per_feature": 5,
      "auto_confirm_overrides": [],
      "always_ask_overrides": [],
      "queue_enabled": false
    },
    "app_docs_sync": {
      "block_on_drift": false
    }
  }
}
```

Niveles:

- `low` (v5.28 default implícito): pregunta todo. Sin sección autopilot, este es el comportamiento.
- `conservador`: solo auto-confirma cosmético (tokens, stitch_design_per_screen, design_system_update_check).
- `equilibrado` (recomendado, v5.29 default): cosmético + visual derivado si confianza alta (veg_preview score≥0.8, image_cost dentro de budget) + heredables desde `app_spec.md`.
- `agresivo`: añade definition_quality_gate auto si AC score≥0.7. Recomendable solo después de validar `equilibrado` durante 1-2 semanas.

**Inviolables** (nunca auto-confirman): `image_cost_over_budget`, `destructive_action`, `branch_to_main_push`. Las acciones destructivas siempre se preguntan/bloquean independientemente del nivel y de los overrides del usuario.

Tabla canónica de los 19 `decision_keys` documentada en `doc/plans/v5.29.0_cognitive_load_reduction_plan.md` sección 3.

### Sync enforcement (Capa 5, warning-only en v5.29.0)

5 piezas que mantienen los canónicos alineados con la realidad:

| Pieza | Archivo | Rol |
|-------|---------|-----|
| Orquestador sync | `server/app_docs/sync.py` | `verify_app_docs`, `apply_app_docs_sync(event)`, `record_signature` |
| Decorador transactional | `server/app_docs/decorators.py` | `@requires_app_docs_sync` para tools mutadoras |
| Hook pre-commit | `.claude/hooks/app-docs-sync-guard.mjs` | Detecta drift por signature; warning en v5.29.0, bloqueante en v5.29.1 |
| Skill `/app-sync` | `.claude/skills/app-sync/` | Resolución manual de drift |
| Drift detector multi-fuente | `server/app_docs/drift_detector.py` | S1 stack lockfiles, S2 brand-kit dangling refs, S3 roadmap-vs-tracking, S4 canonical undocumented |

Telemetría unificada en `.quality/app_docs_drift.jsonl`. La tool MCP `app_docs_drift_for_heartbeat` devuelve un payload compacto utilizable por consumidores externos (specbox_cloud, scripts ad-hoc).

Para promover el hook a bloqueante (v5.29.1+):
```json
{ "specbox": { "app_docs_sync": { "block_on_drift": true } } }
```

### FreeForm first-class

`onboard_project` ahora defaults a `backend_type="freeform"` cuando no se pide Trello/Plane explícitamente. Trello/Plane sigue disponible para proyectos con reporting externo a clientes, pero ya no es el default.

Auto-discovery vía `detect_project_backend(project_path)` con prioridad de 5 niveles:

1. `.claude/settings.local.json` → `specbox.backend_type` explícito
2. `doc/tracking/items.json` presente (signal de filesystem)
3. Legacy: `settings.local.json` → `trello.boardId` / `plane.projectId`
4. `doc/app/app_spec.md` zona "tracking_backend"
5. Default: `freeform`

Migración Trello/Plane → FreeForm: nueva tool `migrate_to_freeform_tool(project, target_path, dry_run=True)` que descarga items + comments + attachment URLs al filesystem local. Validación de path absoluto (FreeForm requiere absoluto desde v5.29 por el BLOCKER fix).

### BLOCKER fix: FreeForm + remote MCP

Pre-v5.29 había un bug crítico silencioso: `set_auth_token(backend_type='freeform', root_path='doc/tracking')` con MCP en VPS escribía en el filesystem del VPS, no del cliente. v5.29 ahora:

- Rechaza paths relativos en `FreeformBackend.__init__` con `FreeformPathError`.
- En `set_auth_token`, resuelve paths relativos contra el server CWD solo cuando MCP es local (sin `SPECBOX_ENGINE_MCP_URL`). Con MCP remoto, exige path absoluto del cliente.
- Helper cliente `.claude/hooks/lib/freeform-path.mjs` calcula el absoluto desde `git rev-parse --show-toplevel`.

**v5.33.0 — Defense in depth**: la rama 1 (`/app-init` resuelve el absoluto explícitamente) ya estaba en v5.29. v5.33 añade dos capas más para clientes que no pasan por `/app-init`:

- **Hook universal `.claude/hooks/freeform-path-guard.mjs`** (PreToolUse) intercepta `mcp__SpecBox-MCP__set_auth_token` y `mcp__SpecBox-MCP__onboard_project`. Si el path es relativo (o si la default `"doc/tracking"` queda implícita), el hook lo reescribe al absoluto del repo cliente via `hookSpecificOutput.updatedInput` antes de que la llamada salga al MCP. Auto-rewrite silencioso, no bloquea. Bloquea exit 2 solo cuando el CWD no es git y la resolución es ambigua. Audit trail en `.quality/logs/freeform-path-rewrites.jsonl`.
- **Tool MCP `detect_local_root_path()`** declara el contrato (requires_absolute_path, default_relative_path, client_resolution_recipe). Read-only, sirve a `/app-init`, claude.ai mobile y integraciones externas como documentación ejecutable.

Las 3 capas son aditivas e independientes. Removerla cualquiera no desbloquea el bug mientras las otras estén en pie.

Migration tooling para 10 casos hipotéticos (`detect_v529_migration_case`):

| Case | Estado del proyecto | Acción |
|------|---------------------|--------|
| 1 | Empty | `/app-init` |
| 2 | v5.28 FreeForm + local MCP | Warn, recomendar path absoluto |
| 3 | v5.28 FreeForm + remote MCP | **BACKUP REQUIRED**, descargar VPS data, reconciliar |
| 4 | v5.28 Trello | Sin cambios; `/app-init` opcional |
| 5 | v5.28 Plane | Idem 4 |
| 6 | Multirepo | Solo el orchestrator corre `/app-init`; satellites heredan |
| 7 | Active UC | Diferir migración hasta cierre del UC |
| 8 | Pending feedback | No-destructivo; cae a la rama de backend |
| 9 | Manual app_*.md sin marcadores | `/app-init --upgrade-zones` con backup obligatorio |
| 10 | Fresh clone | `./install.sh` primero |

## Implement Task Isolation (v5.32.0)

Cierra el out-of-scope explícito de v5.30.0 (PR #20): forzar mecánicamente
la delegación a Tasks aisladas que el SKILL.md de `/implement` ya documentaba
pero no enforcer. v5.32 añade los 5 guardrails que faltaban — sin rediseñar
la arquitectura — y los cablea de forma observable.

### Working set por feature

`.quality/evidence/{feature}/` mantiene 4 archivos:

| Archivo | Vida | Quien escribe | Quien lee |
|---------|------|---------------|-----------|
| `pipeline_state.json` | toda la run | orquestador (Paso 0.4a + tras cada fase) | `pipeline-phase-guard.mjs` |
| `execution_context.json` | toda la run, immutable | orquestador (Paso 0.4b) | cada Task delegado, hooks |
| `phase_outputs.jsonl` | append-only durante la run | cada Task al cierre | Spec-Code Sync (Paso 5.1.1b, 8.5.1a) |
| `checkpoint.json` | toda la run, sobrescrito | orquestador post-fase | resume al iniciar nueva sesion |

`.quality/active_agent.json` — **transient** (escrito antes de cada
`Task(AG-XX)`, borrado tras retorno) — leido por
`file-ownership-guard.mjs` para validar Write/Edit del agente activo.

`.quality/task_isolation.json` — telemetría local (counters bumped por hooks +
SKILL post-Task block).

### Tools / módulos (Python)

- `server/implement_context/execution_context.py` — Pydantic model + atomic write.
- `server/implement_context/phase_outputs.py` — append/read/aggregate.
- `aggregate_for_spec_sync(feature)` → `SpecSyncAggregate` con `overall_status`, `delta_count`, `files_*` deduped, `phases[]`, `total_duration_s`, `total_healing_attempts`.

### Hooks nuevos

- `context-budget-guard.mjs` — PreToolUse(Task). Estima tokens del prompt (chars/4) y warn|block según `specbox.implement.task_isolation.task_budget_mode` (default `warn`, budget `16000`).
- `file-ownership-guard.mjs` — PreToolUse(Write/Edit). Valida la ruta contra el ownership del agente declarado en `active_agent.json`. Modes warn|strict|off. Suspicious paths (`..`, `/abs`) siempre BLOCKED.

### Settings

```json
{
  "specbox": {
    "implement": {
      "task_isolation": {
        "enabled": true,
        "task_budget_tokens": 16000,
        "task_budget_mode": "warn",
        "ownership_mode": "warn"
      }
    }
  }
}
```

### Compatibilidad

100% backwards-compatible. Cualquier proyecto sin `execution_context.json`
ni `phase_outputs.jsonl` ve los guards como no-ops, y Spec-Code Sync cae al
fallback de `git diff`.

### Plan completo

[doc/plans/v5.32.0_implement_task_isolation_plan.md](doc/plans/v5.32.0_implement_task_isolation_plan.md)
documenta los 5 gaps cerrados, fases, riesgos, métricas y rollback.

## Engine Version

Current: v6.0.2 "Smoke Test Followups"
Brand: SpecBox Engine (SpecBox Engine by JPS)
Config: ENGINE_VERSION.yaml

## Smoke Test Followups (v6.0.2)

Patch release que cierra los 3 issues abiertos descubiertos en el smoke test de v6.0.1 (#60, #61, #62) y elimina el último hardcodeo de versión runtime que sobrevivía desde antes de v6.0.

### Cambios

| Issue | Módulo | Resumen |
|-------|--------|---------|
| #60 | `server/tools/audit.py` | `run_quality_audit` deprecation shim ahora `raise RuntimeError` → MCP envelope con `isError=true`. Clientes que solo inspeccionan el envelope detectan la deprecación. |
| #61 | `server/tools/audit.py` | `submit_quality_audit` autogenera `audit_id` server-side (formato `audit_YYYYMMDDTHHMMSSZ`) si el cliente no lo pasa. Clientes que necesiten idempotencia pueden seguir pasando su propio `audit_id`. |
| #62 | `server/tools/discovery.py` | `validate_discovery_completeness` parser acepta las 4 resoluciones canónicas (`feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`). Alias legacy `no drift detected` normalizado a `no_drift`. Nuevo campo `drift.kind` habilita futuros gates estrictos sin requerir otro release. |

### Bug latente eliminado de paso

`submit_quality_audit.fn(...)` se llamaba desde el closure local de `register_audit_tools()`, lo cual siempre lanzaba `AttributeError`. No estallaba porque el único test que lo cubría estaba `pytest.skip`-eado por una dependencia de `QualityReport.empty()` que nunca existió. Refactor a llamada directa + fixture reescrito → 3 tests previos unskippeados y verdes.

### Cleanup adicional (sin issue)

`server/server.py` leía `"v5.29.0"` hardcoded en `FastMCP(instructions=...)` desde v5.29 — drifteaba en cada release y los clientes MCP veían una versión incorrecta. Ahora se lee de `ENGINE_VERSION.yaml` al cargar el módulo vía nuevo helper `_load_engine_version()`.

### Dependencias

`fastmcp >=3.0.0 → >=3.3.1,<4.0.0` (latest stable 2026-05-15, security hardening). Pin con upper bound para evitar saltos major silenciosos.

### Tests

`1243 passed / 71 skipped / 0 failed` (vs `1232/73/0` post-bump fastmcp). +11 nuevos / -2 skipped.

### Compatibilidad

100% backwards-compatible. Clientes calling `submit_quality_audit` sin `audit_id` ahora succeed (antes erraban). Clientes solo inspeccionando MCP `isError` en `run_quality_audit` deprecation ahora ven el valor correcto (antes veían `false`). No hay schema changes.

### Referencias

- PRs: [#63](https://github.com/EmbedBuild/specbox-engine/pull/63) (fastmcp bump), [#64](https://github.com/EmbedBuild/specbox-engine/pull/64) (3 issues + cleanup)

## MCP Path Contract (v6.0.1)

v6.0.1 es un hotfix arquitectural que migra **17 tools cat A** en `server/tools/` a un patrón de **content-passing universal**: ninguna tool registrada con `@mcp.tool` resuelve `Path(project_path).resolve()` para acceder al filesystem del cliente. El cliente lee los archivos localmente con `Read`, pasa el contenido como string, y escribe lo que la tool devuelva.

### Motivación

En MCP remoto (`SPECBOX_ENGINE_MCP_URL=...`), `Path(project_path).resolve()` resolvía contra el filesystem del VPS, no del cliente. Las 17 tools cat A devolvían datos falsos sin error visible.

### Tools migradas

| Módulo | Tools |
|--------|-------|
| `discovery.py` | `start_discovery`, `validate_discovery_completeness`, `detect_v60_migration_case` |
| `app_docs.py` | `read_app_docs_tool`, `get_inheritable_values_tool` |
| `onboarding.py` | `detect_project_stack`, `get_onboarding_status`, `get_visual_gap_report` |
| `acceptance.py` | `run_acceptance_check`, `get_acceptance_report`, `get_e2e_gap_report` |
| `audit.py` | `check_audit_tools_status`, `submit_quality_audit` (nueva), `run_quality_audit` (deprecada) |
| `hints.py` | `get_skill_hint`, `record_skill_hint` |
| `skill_registry.py` | `list_skills_v2`, `discover_skills`, `validate_skill_manifest` |
| `telemetry.py` | `get_context_budget` |
| `benchmark.py` | `generate_benchmark_snapshot` (devuelve content + suggested_relpath) |
| `evidence_regen.py` | `regenerate_evidence` (devuelve plan + report_content) |

### Helper cliente

`.claude/hooks/lib/mcp-client-io.mjs` expone tres helpers para skills/hooks Node.js:

- `resolveProjectRoot()` — absolute path al git toplevel del CWD.
- `readContentBundle(paths)` — `{relpath: string | null}` map.
- `writeContentBundle(bundle)` — escribe todo no-null, devuelve `{written, skipped}`.

Path-traversal guard + rechazo de paths absolutos built-in. 15 casos en `mcp-client-io.test.mjs` con `node:test` (zero-deps).

### Skills actualizadas

`/discovery`, `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check` actualizadas para reflejar el nuevo contrato.

### Helpers Path-based preservados

`read_app_docs(project_path)`, `get_inheritable_values(project_path)`, `run_acceptance_check_impl`, `get_acceptance_report_impl`, `_detect_v60_case(project_path)`, `_app_market_is_pristine_or_missing(project_path)` siguen disponibles para callers in-process (otros módulos Python del propio MCP, no consumibles desde la API `@mcp.tool`).

### Excepción: audit analyzers

Los 8 analizadores SQuaRE de `server/audit/analyzers/` necesitan escanear el código real (lint, complexity, dup, security). Serializar un repo entero como bundle es inviable. Solución: los analizadores se moverán a `.quality/scripts/audit/` (porting completo en v6.0.2) y el cliente envía el `QualityReport` construido localmente vía `submit_quality_audit(project, report)`. En v6.0.1 el directorio está provisionado con un README; `run_quality_audit` queda como shim deprecado que retorna error si se invoca sin `report`.

### Defensas v5.29 de FreeForm

El hook `freeform-path-guard.mjs` y `FreeformPathError` siguen vivos en v6.0.1 como defensa en profundidad. Eliminación formal planeada para v6.1.

### Referencias

- Plan técnico: `doc/plans/v6.0.1_mcp_path_contract_plan.md`
- Decisión arquitectural: `doc/decisions/mcp_path_contract.md`
- Tracking: `doc/tracking/items.json` US-MCP-PATH-CONTRACT (UC-614..UC-624)

## Discovery Module (v6.0.0)

v6.0 introduce un módulo de **Product Discovery** permanente integrado en el pipeline canónico + la **fundación arquitectural multi-doc** que sostiene la extensión a N documentos canónicos.

### Pipeline modificado

```
/discovery → /prd → /plan → /implement → (auto-merge si gate verde)
```

`/discovery <feature_name>` produce `doc/discovery/<feature>/icp_jtbd.md` (ICPs + JTBDs racionales y emocionales). Estos JTBDs viajan con la feature hasta los AC del PRD, las UC del plan y los tests E2E.

### Tercer doc canónico

`doc/app/app_market.md` se añade al set existente (`app_prd.md`, `app_spec.md`). Contiene ICPs primarios + no-ICPs + JTBDs globales + NSM + posicionamiento. Creado en modo bootstrap (primer `/discovery` del proyecto) o vía `upgrade_project` como plantilla `template-pristine`.

### Multi-doc Foundation (US-D04)

Sistema `app_docs` refactorizado a registro extensible (`server/app_docs/registry.py`). Añadir un doc canónico nuevo en v6.x+ es trivial: 1 plantilla + 1 entry. Sin tocar `sync.py`, hooks ni skills.

Ver `doc/decisions/multi_doc_registry.md` para rationale completo.

### Tools MCP nuevas (3)

| Tool | Uso |
|------|-----|
| `start_discovery` | Inicia/resume sesión Discovery (idempotente, auto-detecta bootstrap vs standard) |
| `validate_discovery_completeness` | Verifica que `icp_jtbd.md` está READY_FOR_PRD |
| `detect_v60_migration_case` | Clasifica proyecto en 8 casos de migración v5.x → v6.0 |

### Configuración

```json
{
  "specbox": {
    "discovery": {
      "gate_mode": "off | warn | block",
      "engine_version_at_onboard": "6.0.0"
    }
  }
}
```

Defaults:
- Proyecto upgrade desde v5.x: `gate_mode=off` (sin cambio perceptible).
- Proyecto fresh post-v6.0: `gate_mode=warn` (pedagógico).
- Power users: `gate_mode=block` opt-in.

### Backwards compatibility

Proyectos v5.x reciben `app_market.md` plantilla pristine vía `upgrade_project` SIN modificar archivos existentes (`app_prd.md`, `app_spec.md` byte-by-byte intactos). El hook `app-docs-sync-guard` respeta `template-pristine` y `engine_version_at_onboard` — no warnea sobre docs no introducidos aún.
