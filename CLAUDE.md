# SpecBox Engine v6.21.0

> **⚠️ SATÉLITE del ecosistema SpecBox (rol: `engine`).** Desde 2026-06-03, el tracking
> OPERATIVO de trabajo NUEVO vive en el **board native del orquestador**
> `EmbedBuild/specbox-manager` (topología orchestrator/satellite). Toda US/UC nueva se abre
> AHÍ, etiquetada con `set_uc_satellite(uc, "engine")` — **no** en el `doc/tracking/` local de
> este repo, que queda como **histórico congelado read-only** (21 US / 108 UC). Orquestador en
> `../..` (layout anidado). Ver `repositorios/specbox_cloud/doc/specs/multirepo-orchestrator.md`.

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
- **Quality Audit** — ISO/IEC 25010 (SQuaRE) on-demand via `/audit` + AG-11 auditor externo
- **Spec-Driven** — Backend-agnostic tools para US/UC/AC (21 tools + 12 migration, Trello y Plane)
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
| Schema multi-tenant | `server/db/migrations/0001_native_schema.sql` + `0008_audit_log_metadata.sql` + `0009_tenant_scoped_pks.sql` | Tablas US/UC/AC + concurrencia optimista (`expected_version`). **0009 (v6.9.5, UC-707)**: PK compuesta `(project_id, id)` en US/UC/AC + FKs hijas compuestas same-tenant — dos proyectos pueden compartir `US-01` en el mismo Postgres. |
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

Si el puerto 55432 ya está ocupado, elige otro con `SPECBOX_NATIVE_PG_PORT`. El contenedor
lo publica en ese puerto y las pruebas construyen su DSN de desarrollo con él cuando
`SPECBOX_NATIVE_DSN` no está definido (UC-5903):
```bash
export SPECBOX_NATIVE_PG_PORT=55434
docker compose -f docker-compose.dev.yml up -d
python -m pytest tests/test_native_*.py
```

Las pruebas que usan Postgres (UC-5901) son las de los módulos que pasan por
`tests/_native_db.py`; `tests/conftest.py` les pone el marcador `native_db`, así que
`python -m pytest -m native_db tests` las corre todas (461 hoy, ~35 s contra un Postgres 16
limpio) y un módulo nuevo entra solo con usar el helper. Es check obligatorio para fusionar en
main. La CI las ejecuta en cada PR y en
cada push a main contra un `postgres:16-alpine` de servicio:
`.github/workflows/native-tests.yml`, check `native-tests`. Tres reglas que las sostienen:

- **La pool no sobrevive a la prueba que la abrió.** `server/db/pool.py` es un singleton por
  proceso y pytest-asyncio da un loop por prueba; `tests/conftest.py` la cierra al terminar
  cada prueba, en su propio loop. No la sueltes con `_pool = None`: sus conexiones siguen
  abiertas en el servidor con sus bloqueos, y el siguiente `apply_migrations` espera para
  siempre (era el cuelgue de la suite completa).
- **Organización, como en el panel.** `provision_native_project` (y con él `setup_board`)
  coloca un proyecto nuevo en la organización de su creador; en producción la da el registro
  del panel (UC-1303). Las fixtures que quieren ese comportamiento la crean con
  `tests._native_db.seed_organization(conn, developer_id)`; sin ella el proyecto se crea sin
  organización, como en un engine sin panel (ver «Proyectos sin organización»).
- **Una prueba bloqueada falla por tiempo**: `pytest-timeout`, 120 s por prueba
  (`pyproject.toml`); la más lenta tarda ~4 s.

**Una versión por migración (UC-6202).** `server/db/migrations/NNNN_<nombre>.sql` es la fuente
del esquema del board (la aplican el runner, las pruebas y la CI) y
`supabase/migrations/<versión de 14 cifras>_<nombre>.sql` es su copia byte a byte, la que se
aplica en producción con `apply_migration`. Las migraciones que solo existen en Supabase (tablas
del site, historia que la cadena local sustituyó) se declaran con su motivo en
`server/db/migration_twins.yaml`. Una migración nueva se escribe en `server/db/migrations` y
`python -m server.db.migration_twins --fix` crea su copia (versión = fecha UTC + `00NNNN`);
sin `--fix` comprueba, y el workflow `db-surface-check.yml` falla si falta una copia o difiere
en un solo byte. Tests: `tests/test_migration_twins.py`.

Cada operador del MCP es responsable de provisionar su propia instancia Supabase.

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
├── install.sh             ← Instala skills, hooks, GGA
├── .gga                   ← Config de Gentleman Guardian Angel (cached lint)
├── .vscode/mcp.json       ← Servidor MCP de Engram (memoria persistente)
├── .claude/
│   ├── skills/            ← Agent Skills (v5.18)
│   │   ├── acceptance-check/SKILL.md
│   │   ├── adapt-ui/SKILL.md
│   │   ├── app-init/SKILL.md
│   │   ├── app-sync/SKILL.md
│   │   ├── audit/SKILL.md
│   │   ├── check-designs/SKILL.md
│   │   ├── compliance/SKILL.md
│   │   ├── discovery/SKILL.md
│   │   ├── explore/SKILL.md
│   │   ├── feedback/SKILL.md
│   │   ├── handoff/SKILL.md
│   │   ├── implement/SKILL.md
│   │   ├── manual-test/SKILL.md
│   │   ├── optimize-agents/SKILL.md
│   │   ├── plan/SKILL.md
│   │   ├── prd/SKILL.md
│   │   ├── quality-gate/SKILL.md
│   │   ├── queue-review/SKILL.md
│   │   ├── quickstart/SKILL.md
│   │   ├── release/SKILL.md
│   │   ├── stripe-connect/SKILL.md
│   │   ├── stripe-standard/SKILL.md
│   │   ├── stripe-switch-account/SKILL.md
│   │   ├── switch-backend/SKILL.md
│   │   └── visual-setup/SKILL.md
│   ├── hooks/             ← Hooks (los registra .claude/settings.json; ver «Hooks»)
│   │   ├── lib/           ← Módulos compartidos de los hooks
│   │   ├── legacy-bash/   ← Versiones .sh anteriores a la 5.17
│   │   ├── app-docs-sync-guard.mjs
│   │   ├── branch-guard.mjs
│   │   ├── checkpoint-freshness-guard.mjs
│   │   ├── commit-spec-guard.mjs
│   │   ├── context-budget-guard.mjs
│   │   ├── design-gate.mjs
│   │   ├── design-system-gate.mjs
│   │   ├── e2e-gate.mjs
│   │   ├── file-ownership-guard.mjs
│   │   ├── freeform-path-guard.mjs
│   │   ├── healing-budget-guard.mjs
│   │   ├── implement-checkpoint.mjs
│   │   ├── implement-healing.mjs
│   │   ├── no-bypass-guard.mjs
│   │   ├── on-session-end.mjs
│   │   ├── pipeline-phase-guard.mjs
│   │   ├── post-implement-validate.mjs
│   │   ├── pre-commit-lint.mjs
│   │   ├── pre-prd-discovery-check.mjs
│   │   ├── pre-read-budget-guard.mjs
│   │   ├── quality-first-guard.mjs
│   │   ├── read-tracker.mjs
│   │   ├── session-start.mjs
│   │   ├── spec-guard.mjs
│   │   ├── stripe-safety-guard.mjs
│   │   ├── test-hooks.mjs
│   │   └── uc-lifecycle-guard.mjs
│   └── settings.json      ← Hooks config
├── agents/                ← Templates de agentes por rol
│   ├── acceptance-tester.md
│   ├── acceptance-validator.md
│   ├── ag-10-quality-auditor.md
│   ├── appscript-specialist.md
│   ├── db-specialist.md
│   ├── design-specialist.md
│   ├── developer-tester.md
│   ├── feature-generator.md
│   ├── n8n-specialist.md
│   ├── orchestrator.md
│   ├── qa-validation.md
│   ├── quality-auditor.md
│   └── uiux-designer.md
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
│   │   ├── freeform_backend.py ← FreeformBackend (local JSON + Markdown)
│   │   ├── native_backend.py   ← NativeBackend (Postgres gestionado, tenant por project_id)
│   │   └── dual_backend.py     ← DualBackendWrapper (espejo Native best-effort sobre otro primario)
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
| `context: direct` | Sesión principal, herramientas completas (Read, Write, Edit, Bash, MCPs). Contamina el contexto de la sesión. | Skills **operativos** que escriben artefactos al filesystem, llaman MCPs de escritura, crean PRs, adjuntan evidencia. Ejemplos: `prd`, `plan`, `visual-setup`, `implement`, `feedback`, `release`, `compliance`. |
| `context: fork` + `agent: Explore` | Delega al sub-agente nativo Explore, read-only por diseño. Aísla el contexto de la sesión principal. | Skills **read-only** que analizan código y devuelven un informe. Ejemplos: `explore`, `adapt-ui`, `check-designs`, `optimize-agents` (modo audit). |
| `context: fork` **sin** `agent:` | **ROTO.** El harness no sabe a quién delegar — el sub-agente recibe el SKILL.md como contexto descriptivo, no como instrucción, y responde "no se me ha pedido nada". | Nunca. |
| `context: fork` + `agent: Plan` | Funciona pero fuerza modo read-only (el sub-agente nativo Plan es un arquitecto read-only). El skill puede llamar MCPs externos pero **no puede escribir al filesystem local**. | Nunca para skills de SpecBox — causa bugs silenciosos tipo "el plan se adjunta a Trello pero no se escribe `doc/plans/*.md`". |

**Regla simple**: si el skill escribe archivos o crea artefactos locales → `direct`. Si el skill solo lee y reporta → `fork` + `agent: Explore`.

**Test rápido** para confirmar que un skill funciona: ejecutar su slash command en una sesión nueva (los cambios en SKILL.md no afectan sesiones ya abiertas). Si el skill responde "espero tu solicitud" o falla con error de escritura, el frontmatter está mal.

## Available Skills

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
| /audit | "audit project", "quality audit", "ISO 25010", "SQuaRE audit" | direct | Full | v5.22 — Quality Audit ISO/IEC 25010 on-demand (AG-11, 8 analyzers, PDF+JSON) |
| /stripe-connect | "stripe connect", "marketplace billing", "integrar pagos marketplace" | direct | Full | v5.25 — Marketplace Connect (Express + Direct charges + subscriptions embedded) + Supabase + React/Flutter |
| /stripe-standard | "stripe standard", "stripe sin connect", "subscriptions saas", "billing saas", "monta pagos saas" | direct | Full | v5.27 — Stripe Standard (no Connect) + 4 modalidades (single/tiered/metered/one_shot) + Supabase + React/Flutter |
| /stripe-switch-account | "switch stripe account", "rotar cuenta stripe", "cambiar cuenta stripe" | direct | Full | v5.27 — Stripe credentials rotation (alias store + switch_stripe_account tool, both Standard and Connect modes, dry-run + automatic rollback) |
| /handoff | "handoff", "save state", "guarda contexto", "voy a hacer compactación" | direct | Read+Bash+Write | v5.30 — Persiste estado fino a `.quality/handoff.md` + Engram structured. **Llamar ANTES de proponer compactación**. |
| /switch-backend | "switch backend", "cambiar backend", "migrar de FreeForm a Trello/Plane/Native", "mover el tracking a" | direct | Full | v5.35 — Cambio guiado de backend N×N entre los 4 (FreeForm/Trello/Plane/Native). Preview obligatorio + confirmación literal + switch transaccional (3 lugares con rollback) + regenerate_evidence opt-in. Migración aditiva, no destruye origen. |
| /discovery | "discovery", "framing", "antes de PRD", "definir ICP", "definir JTBD" | direct | Full | v6.0 — Product Discovery ligero antes de /prd: ICP + JTBD + gate → `doc/discovery/<feature>/icp_jtbd.md` |
| /manual-test | "manual test", "pruebas manuales", "test plan", "testear la app" | direct | Full | Pruebas manuales sistemáticas con resolución de bugs en vivo y evidencia para stakeholders |
| /queue-review | "queue review", "revisar cola", "resolver pendientes" | direct | Full | v5.29 — Revisa y resuelve `doc/app/decisions_queue.md` (decisiones aplazadas por el autopilot) |
| /app-init | "app init", inicializar documentos canónicos | direct | Full | v5.29 — Crea o refresca `doc/app/app_prd.md` y `app_spec.md`, la fuente que consultan /prd, /plan y /visual-setup |
| /app-sync | "app sync", "sync app docs" | direct | Full | v5.29 — `--check`, `--repair`, `--review` y `--rebuild-from-tracking` de los documentos canónicos |

## Hooks

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| **quality-first-guard** | PreToolUse (Write/Edit) | **BLOCKING**: verifies the agent read the file before modifying it. Enforces "read before write." |
| **read-tracker** | PostToolUse (Read) | Non-blocking: records which files the agent reads. Used by quality-first-guard. |
| **spec-guard** | PostToolUse (Write/Edit on src/ or lib/) | **BLOCKING**: verifies active UC exists + branch is not main. No UC or main branch = no code writes. |
| branch-guard | Not wired | Superseded: `spec-guard` already blocks writing code on main/master. The file stays for projects that wired it by hand. |
| **commit-spec-guard** | PostToolUse (git commit) | **BLOCKING** (branch) + WARNING (rest): blocks commits on main; warns UC/checkpoint/size. |
| pre-commit-lint | PostToolUse (git commit) | **BLOCKING**: runs `gga run` (cached lint, skips unmodified files). Falls back to direct lint if GGA not installed |
| **e2e-gate** | PostToolUse (git commit) | **BLOCKING**: validates results.json schema + HTML Evidence Report exists + evidence integrity when committing acceptance files. Uses `validate-results-json.js`. |
| **no-bypass-guard** | PreToolUse (--no-verify, push --force, reset --hard) | **BLOCKING**: prevents agent shortcuts under pressure — must fix root cause, not bypass quality checks. |
| **design-gate** | PostToolUse (Write/Edit on pages/) | **BLOCKING**: blocks UI page creation/modification without Stitch HTML design in doc/design/. |
| on-session-end | Stop | Logs session telemetry to .quality/logs/ + persists summary to Engram |
| implement-checkpoint | Manual (called by /implement) | Saves phase progress for resume |
| implement-healing | Manual (called by /implement) | Logs self-healing events to evidence |
| post-implement-validate | Manual | Checks baseline regression after implementation (run by hand; no skill calls it today) |
| **healing-budget-guard** | PreToolUse (Write/Edit) | **BLOCKING**: counts healing.jsonl entries per feature. Blocks at 8 attempts (HARD limit). Prevents infinite healing loops. |
| **pipeline-phase-guard** | PreToolUse (Write/Edit) | **BLOCKING**: reads pipeline_state.json to verify phase dependencies are met. Prevents out-of-order execution (e.g., feature code before DB). |
| **stripe-safety-guard** | PreToolUse (Write/Edit on billing paths) | **BLOCKING**: scans `src/billing/`, `lib/billing/`, `supabase/functions/stripe-*`. Blocks 5 anti-patterns: sk_live_* hardcoded, webhook sin firma, webhook sin idempotencia (`stripe_processed_events`), `redirectToCheckout`/`ui_mode:hosted`, Payment Links. Escape hatches: `// stripe-safety-guard:ignore` / `:disable-file`. v5.25 — scaffoldeado por `/stripe-connect`. |
| checkpoint-freshness-guard | PostToolUse (git commit) | Non-blocking WARNING: warns if checkpoint is stale (>30min) or missing during active UC implementation. |
| uc-lifecycle-guard | PostToolUse (git push) | Non-blocking WARNING: warns if pushing feature branch without calling move_uc (board out of sync). |
| **session-start** | SessionStart | Non-blocking: injects `.quality/handoff.md` (if fresh), active UC + checkpoint, and auto zones from `app_spec.md` as `additionalContext` for the new session. Capped at 14k chars. v5.30. |
| **pre-read-budget-guard** | PreToolUse (Read) | Non-blocking WARNING: estimates tokens for the file being read; warns if ≥ `specbox.context_budget.warn_pct` of the window (default 5% of 1M). v5.30. |
| **design-system-gate** | PreToolUse (mcp__SpecBox-MCP__move_uc → review/done, mcp__SpecBox-MCP__complete_uc, `gh pr create`) | **BLOCKING in autopilot** (exit 2): scans the UI files changed on the branch against the project's `design-system.tokens.json` — colours written directly, fonts outside the system, weights above the system maximum, gradients — and lists each with `file:line` and what to do. Warns outside autopilot; `specbox.design_gate.mode` overrides. US-49 · UC-4902. |
| **freeform-path-guard** | PreToolUse (mcp__SpecBox-MCP__set_auth_token, mcp__SpecBox-MCP__onboard_project) | Auto-rewrites relative FreeForm `root_path` / `freeform_root_absolute` to an absolute path resolved against `git rev-parse --show-toplevel` via `hookSpecificOutput.updatedInput`. Covers the implicit-default case (`onboard_project` with no `backend_type` AND no `trello_board_name`). **BLOCKING** (exit 2) only when CWD is not a git repo and resolution is ambiguous. Logs every rewrite to `.quality/logs/freeform-path-rewrites.jsonl`. Defense in depth on top of the v5.29 server-side guard. v5.33. |
| context-budget-guard | PreToolUse (Task) | Non-blocking by default: estimates the tokens of a subagent's prompt and warns when it exceeds the budget; `specbox.implement.task_isolation.task_budget_mode: strict` blocks. v5.32. |
| file-ownership-guard | PreToolUse (Write/Edit) | Non-blocking by default: warns when an /implement subagent writes outside the files its role owns (`.claude/skills/implement/file-ownership.md`); `ownership_mode: strict` blocks. v5.32. |
| pre-prd-discovery-check | PreToolUse (Skill) | Off unless `specbox.discovery.gate_mode` in `.claude/settings.local.json` is `warn` or `block`: then `/prd` without a discovery for the feature warns or blocks; spec-driven invocations (`US-XX`, `UC-XXX`) pass. v6.0. |
| app-docs-sync-guard | PostToolUse (git commit) | Non-blocking WARNING: detects drift between the canonical docs in `doc/app/` and their signatures in `.quality/app_docs_sync.lock`; `specbox.app_docs_sync` can make it block. v5.29/v6.0. |
| test-hooks | — | Not a hook: smoke tests for the hooks (`node .claude/hooks/test-hooks.mjs`, run by CI `hooks.yml`). |

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

This enforces the principle: **the LLM provides speed; SpecBox provides control and quality.**
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

## Agents

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
| AG-11 | Quality Auditor (externo, /audit) | `agents/ag-10-quality-auditor.md` (nombre histórico) | **opus** (v5.24.0) |

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

## Stitch MCP Proxy (v6.4.0 — Native Material 3 Chain)

Proxy completo de Google Stitch a través del SpecBox Engine MCP server. Permite que usuarios de claude.ai usen Stitch sin configurar un conector OAuth adicional — la API Key se configura por proyecto. Cubre las **14 tools nativas** del MCP de Stitch (verificadas vía `tools/list` el 2026-05-26, ver `.quality/evidence/stitch_smoke/mcp_tools_schema.json`) + 1 tool de configuración.

### Tools (15)

| Tool | Descripción | Timeout |
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
| `stitch_upload_design_md` | Subir DESIGN.md (Material 3 YAML) a Stitch (MCP <5KB / REST batchCreate ≥5KB) | 3 min |
| `stitch_create_design_system` | Crear un Design System vacío para luego poblarlo con update | 3 min |
| `stitch_create_design_system_from_design_md` | Parsear DESIGN.md previo y materializar DS server-side | 3 min |
| `stitch_update_design_system` | Mutar tokens del theme in-place (M3) | 3 min |
| `stitch_list_design_systems` | Listar DS aplicados al proyecto | normal |
| `stitch_apply_design_system` | Aplicar DS a un batch de screen instances | 3 min |

**Removed in v6.4.0** (ghost tools — no existían en el MCP real, sólo en el cliente local): `stitch_extract_design_context` y `stitch_build_site`. Para el primero, usa `stitch_get_screen` (devuelve `designTheme`) o `stitch_list_design_systems`. Para el segundo, usa múltiples `stitch_generate_screen` con `designSystem: "assets/{id}"` compartido, o `stitch_build_site_batched_v2` (capa autopilot).

### Enums (verificados contra el servidor real)

Los enums se mantienen en `server/stitch_enums.py` y se pinnean en CI contra `mcp_tools_schema.json` para detectar drift cuando Google actualice el servidor.

- **DeviceType**: `DESKTOP`, `MOBILE`, `TABLET`, `AGNOSTIC` (sin dispositivo concreto; la API lo acepta, comprobado el 2026-10-05, UC-8407).
- **ModelId** (UC-8405): `GEMINI_3_8_FLASH` (calidad, default) / `GEMINI_3_5_FLASH_LITE` (pantallas simples y cadena de respaldo). Desde 2026-10 la API solo acepta estos dos; `resolve_model` traduce un `modelId` antiguo de la configuración (`GEMINI_3_PRO`, `GEMINI_3_1_PRO` → `GEMINI_3_8_FLASH`; `GEMINI_3_FLASH` → `GEMINI_3_5_FLASH_LITE`) y lo avisa en `model_notice`; cualquier otro se rechaza antes de llamar a Stitch.
- **ColorMode**: `LIGHT`, `DARK`.
- **ColorVariant** (10): `FIDELITY`, `TONAL_SPOT` (no `TONAL` como dicen las docs), `VIBRANT`, `EXPRESSIVE`, `CONTENT`, `MONOCHROME`, `NEUTRAL`, `RAINBOW`, `FRUIT_SALAD` (+ UNSPECIFIED).
- **Roundness**: `ROUND_FOUR`, `ROUND_EIGHT`, `ROUND_TWELVE`, `ROUND_FULL` (+ UNSPECIFIED). `ROUND_TWO` sigue en el enum pero la API lo marca «Unused»: el engine no lo produce (`2px` → `ROUND_FOUR`).
- **StitchFont**: 68 fuentes (esquema del 2026-10-05) — incluye `GEIST`, `DM_SANS`, `GOOGLE_SANS_*`, `JETBRAINS_MONO`, `SOURCE_SANS_3`, `SOURCE_SERIF_4`, `METROPHOBIC`… `SOURCE_SANS_THREE`, `SOURCE_SERIF_FOUR` y `METROPOLIS` están obsoletas: `current_theme` envía las dos primeras con su nombre nuevo y el engine no ofrece ninguna (UC-8407).
- **CreativeRange** (variantes): `REFINE` (sutil), `EXPLORE` (moderado), `REIMAGINE` (radical).
- **VariantAspect**: `LAYOUT`, `COLOR_SCHEME`, `IMAGES`, `TEXT_FONT`, `TEXT_CONTENT`.
- **ScreenType** (REST batchCreate): `DOCUMENT` (HTML / Markdown), `IMAGE` (PNG / JPEG / WebP).

### Flujo (chain canónica de 7 pasos — verificada en `.quality/evidence/stitch_smoke/smoke_test_mcp_v2.py`, verdict `pass`)

1. `stitch_list_projects()` → identificar proyecto, o `stitch_create_project(title)`.
2. `stitch_upload_design_md(stitch_project_id, design_md_content)` — sube DESIGN.md (Material 3 YAML frontmatter). El wrapper auto-elige MCP (<5KB) o REST `batchCreate` (≥5KB). Devuelve `{id, sourceScreen}` del screen DOCUMENT.
3. `stitch_create_design_system_from_design_md(stitch_project_id, screen_instance_id, source_screen, device_type)` — parsea el YAML frontmatter y materialise el DS server-side. Latencia observada ~43s. Devuelve `{assetId}`.
4. `stitch_list_design_systems(stitch_project_id)` — resuelve `assets/{id}` para uso posterior.
5. (opcional) `stitch_update_design_system(asset_name, project_id, theme)` — mutar tokens M3 sin regenerar.
6. `stitch_apply_design_system(stitch_project_id, asset_id, [{id, sourceScreen}, ...])` — aplica DS a screens existentes (~19s por screen). **Importante**: el array debe contener solo `id` y `sourceScreen`; `x/y/width/height` son rechazados por el servidor.
7. `stitch_generate_screen(project, stitch_project_id, prompt, ...)` con el DS ya aplicado → los prompts **NO** deben incluir colors / fonts / roundness, Stitch los aplica server-side.

### Mapper VEG ↔ Material 3

`server/veg/material3_mapper.py` traduce los 6 arquetipos VEG (`corporate`, `startup`, `creative`, `consumer`, `gen_z`, `gobierno`) a `Material3Theme` server-validatable. Resolution order: archetype defaults → JTBD overrides (whitelist de 3 campos) → BrandKit overrides. La función inversa `material3_to_veg_hints` propone candidatos VEG dado un theme existente — útil para migration case E (DESIGN.md custom).

### Almacenamiento de API Key

- **Sesión**: Credenciales en FastMCP session state (aisladas por cliente). Es el único sitio: desde UC-8601 (US-86) el servidor no escribe la clave en `meta.json` ni la lee de disco, así que el cliente la vuelve a enviar con `stitch_set_api_key` en cada sesión (la tiene en `stitch.apiKey` de su `settings.local.json`). Tests: `tests/test_stitch_key_session_only.py`.
- **Telemetría**: Uso registrado en `stitch_usage.jsonl` por proyecto.

### Cuota — sin cuota

Stitch MCP es **free of charge** (verificado por la extensión oficial Gemini CLI + smoke v2 contra el endpoint real). La cuota documentada de 350 Standard + 200 Experimental por mes **corresponde a la UI web**, no al MCP. v6.4.0 elimina el subsistema entero de tracking (`get_stitch_quota_status`, hook `stitch-quota-guard.mjs`, settings `quota`/`flash_safety_net`) — resolvía un problema que no existe.

### Arquitectura

- `server/stitch_client.py` — Cliente async MCP JSON-RPC (Streamable HTTP + SSE) + helper REST `batchCreate` para uploads grandes.
- `server/stitch_enums.py` — 8 enums pinneados contra `mcp_tools_schema.json`.
- `server/tools/stitch.py` — 12 tools v1 + 6 tools de design-system v6.4.0 registradas en FastMCP.
- `server/veg/material3_mapper.py` — Mapper determinista VEG ↔ M3.
- `server/auth_gateway.py` — `store_stitch_credentials()` / `get_stitch_client()` per-project.
- Timeouts: 30s default, 6 min para `generate_*`, 3 min para tools de DS (`create_design_system_from_design_md` mide ~43s).
- Retry con backoff exponencial para errores transitorios.

## Stitch Autopilot (v5.31.0 + /plan migration v5.31.1, refactored v6.4.0)

Capa que se asienta encima del Stitch MCP Proxy v1 para resolver los bloqueos
recurrentes de autopilot causados por (a) drift visual entre pantallas, (b)
fallos terminales de generación sin recuperación, (c) prompts mal estructurados
que producen primeras generaciones peores de lo necesario.

**Histórico**: la v5.31 original también mitigaba (d) cuota mensual y (e) la
ausencia de endpoint nativo de attach para DESIGN.md. Tras la auditoría
post-Google-I/O y los smoke tests reales contra el servidor (ver
`.quality/evidence/stitch_smoke/`), ambos motivos resultaron obsoletos:
**Stitch MCP es free of charge** y **`upload_design_md` +
`create_design_system_from_design_md` SÍ existen nativamente** desde mediados
de 2026. v6.4.0 retira las defensas correspondientes (quota subsystem, Flash
safety net) y prepara la transición del `inline-prefix` al native chain.

**v5.31.1 update**: `/plan` ya está migrado al pipeline v2. Cada generación
pasa por `validate_stitch_prompt` → `stitch_generate_screen_v2` (con fallback
chain) y los planes con >5 pantallas usan `stitch_build_site_batched_v2`. La
adaptación de `/plan` y `stitch_generate_screen_v2` para usar la chain nativa
y omitir tokens del prompt cuando DS está aplicado se entrega en una **PR-2
posterior** (UC-705 del PRD `stitch_native_migration_prd.md`).

**Decisión de calidad**: el modelo default es `GEMINI_3_8_FLASH`, el mejor que
acepta Stitch desde 2026-10 (ya no hay modelo Pro). La cadena de respaldo
reintenta con `GEMINI_3_5_FLASH_LITE` y lo marca `degraded` con
`degraded_reason: fallback_model` (UC-8405). El safety-net de Flash por cuota
**fue eliminado en v6.4.0** — degradar por una cuota inexistente no tenía sentido.

### 5 capas (todas aditivas, v1 sigue funcionando)

1. **DESIGN.md canónico** — formato oficial Google
   ([google-labs-code/design.md](https://github.com/google-labs-code/design.md)).
   `/visual-setup` Paso 3.7 invoca `generate_design_md_tool` que sintetiza
   `doc/design/DESIGN.md` (YAML front-matter + Markdown body) desde Brand Kit
   + VEG + canónicos `app_prd.md` / `app_spec.md`. Cuando faltan inputs,
   completa desde 6 arquetipos VEG (corporate / startup / creative / consumer
   / gen_z / gov). `upload_design_md_to_stitch` v5.31 lo registra contra el
   proyecto Stitch en modo `inline-prefix` legacy (prepende DESIGN.md al
   prompt). La chain nativa v6.4.0 (`stitch_upload_design_md` +
   `stitch_create_design_system_from_design_md` + `stitch_apply_design_system`)
   ya está disponible y será el contrato default desde **v7.0** (cutover
   duro previsto; ver `doc/migrations/v7_stitch_native_chain.md`).

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
   natural falla. Clasifica el error (`transient | content | unknown`)
   para decidir si reintentar. El Flash safety-net fue eliminado en
   v6.4.0 (cuota inexistente). El parámetro `max_total_attempts: 3` se
   mantiene como hard ceiling para evitar loops de healing.

4. **Batched build_site** — `stitch_build_site_batched_v2` particiona
   pantallas en grupos de ≤4 (priorizando tag `group` explícito, luego
   prefijo de `route`, luego chunks ordenados) y aplica una pasada final
   de `edit_screens` con un prompt de unificación de tema cuando hay >1
   batch. Resuelve el límite duro de ~5 pantallas conectadas por
   `build_site` que Google reporta en foros.

5. **Quota tracking + safety net** — **ELIMINADO en v6.4.0**. Stitch MCP es
   free of charge — la tool `get_stitch_quota_status`, el hook
   `stitch-quota-guard.mjs`, el cache `.quality/stitch_quota.json` y las
   settings `quota` + `flash_safety_net` fueron retirados. Cualquier referencia
   en la documentación de versiones previas es obsoleta.

### Settings (`templates/settings.json.template` → `stitch`, v6.4.0)

```json
{
  "stitch": {
    "modelId": "GEMINI_3_8_FLASH",
    "contract": "native_v2",
    "fallback": {
      "enabled": true,
      "strategy": ["edit_baseline", "variants_refine", "regenerate"],
      "max_total_attempts": 3
    },
    "prompt": { "validator_mode": "warn" }
  }
}
```

### Compatibilidad

- 100% backwards-compatible para callers v5.31: las 13 tools v1 siguen
  registradas. Las tools v2 v5.31 (`generate_design_md_tool`,
  `upload_design_md_to_stitch`, `validate_stitch_prompt`,
  `stitch_generate_screen_v2`, `stitch_build_site_batched_v2`) siguen
  funcionando en modo `stitch.contract=inline_prefix_v1`.
- 6 tools nuevas en v6.4.0 (chain nativa): `stitch_upload_design_md`,
  `stitch_create_design_system`, `stitch_create_design_system_from_design_md`,
  `stitch_update_design_system`, `stitch_list_design_systems`,
  `stitch_apply_design_system`. Default `stitch.contract=native_v2` para
  proyectos nuevos.
- `/plan` Paso 6 fue migrado al pipeline v2 en v5.31.1. La transición a la
  chain nativa (omitir tokens del prompt cuando DS aplicado) se entrega en
  la PR-2 del PRD `stitch_native_migration_prd.md`.
- Cutover duro previsto en **v7.0**: `inline_prefix_v1` se elimina,
  migración obligatoria al upgrade. Documentado en
  `doc/migrations/v7_stitch_native_chain.md`.

### Migration tools (v6.5.0)

3 tools nuevos en `server/tools/stitch_migration.py` orquestan el paso de
`inline_prefix_v1` a `native_v2`, todos siguiendo el MCP Path Contract
v6.0.1 (content-passing):

- **`detect_stitch_migration_case`** — clasifica el proyecto en uno de
  los 6 casos canónicos (A: ya en native_v2; B: Stitch unused; C:
  DESIGN.md sin Stitch project; D: Stitch project con screens sin DS;
  E: DESIGN.md custom; F: multirepo). Devuelve `recommended_action` +
  `evidence`.
- **`migrate_project_to_native_v2`** — planning-only. Dada una case,
  devuelve `actions[]` + `files_to_write` + `stitch_calls[]` +
  `settings_patch` + `confirmation_required` (caso D pide literal
  `MIGRATE-RETROACTIVE`, caso E pide `APPLY-PROPOSAL`). La skill
  `/visual-setup --migrate-stitch` orquesta la ejecución.
- **`get_stitch_migration_stats`** — agrega
  `.quality/logs/stitch-migration.jsonl` y devuelve un verdict
  `{no_data | in_progress | completed | failed}` para dashboards de
  readiness de cara al cutover v7.0.

`upgrade_project` emite el hint `stitch_migration_alignment` y la
columna `stitch_contract` en `get_version_matrix` cuenta cuántos
proyectos siguen en legacy. El playbook completo de la skill vive en
[.claude/skills/visual-setup/SKILL.md](.claude/skills/visual-setup/SKILL.md)
sección "Modo `--migrate-stitch` (v6.5.0)".

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
`findings[]` con severidad, `recommendations[]` priorizadas por AG-11.

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

### Agente AG-11 Quality Auditor

Distinto de **AG-08** (gate interno por fase en `/implement`). AG-11 es
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

## VSCode Discoverability (v6.6.0)

US-VSCODE-DISCOVERABILITY cierra el funnel post-install que abrieron
v6.2.0 (Marketplace) y v6.3.0 (Native Default OAuth). El sidebar
`specbox.skills` ya no muestra una lista hardcoded de 15 skills (con
un fantasma `remote` eliminado en v6.1.0 y 11 skills reales ausentes):
ahora **auto-detecta** los skills instalados leyendo
`~/.claude/skills/*/SKILL.md` (global) y
`${workspace}/.claude/skills/*/SKILL.md` (local), los agrupa en
**7 categorías canónicas** (Pipeline / Quality / Visual / Tracking /
Stripe / Lifecycle / Other), y al hacer click sobre cualquier skill
abre una **ficha de ayuda** con 4 bloques (qué hace, cuándo usarlo,
comando exacto a teclear, ejemplo) + botón "Copiar al portapapeles".

**El click NO ejecuta el skill** — sólo despliega la ficha. La
invocación queda manual en el chat de Claude Code. Decisión cerrada
en `/discovery vscode_discoverability_sidebar`: la API de Claude Code
no expone hoy invocación pública de slash commands desde extensiones.

Componentes nuevos en `vscode-extension/`:

| Archivo | Rol |
|---|---|
| `src/views/skill-loader.ts` | Loader puro del filesystem + parser de frontmatter YAML mínimo |
| `src/views/skill-categories.ts` | Mapping skill→categoría tipado, 7 categorías en orden fijo, iconos consistentes |
| `src/views/skill-card.ts` | `buildSkillCardContent` + `buildSkillCardItems` + `showSkillCard` (QuickPick + botón copy) |
| `src/views/skill-defaults.ts` | Diccionario estático con las 4 secciones de cada uno de los 25 skills canónicos |
| `media/walkthrough/step-discover-skills.md` | 5º paso del walkthrough "Explore your skills" con command link al sidebar |
| `tests/skill-{loader,categories,card}.test.mjs` | 20 nuevos casos `node:test` zero-deps |

Cambios cross-impact en código existente:

- `src/constants.ts` — `CORE_SKILLS` renombrado a **`KNOWN_SKILLS`**:
  ahora es la lista canónica de categorización (drift detector source
  of truth), no la fuente de verdad runtime. El runtime lee del
  filesystem siempre.
- `src/install.ts::getInstalledSkills()` — lee directamente con
  `readdirSync`, no filtra contra `KNOWN_SKILLS`.
- `src/health.ts::checkSkills()` — `installed` es lo que hay en disco
  (conteo honesto en el sidebar); `missing` es `KNOWN_SKILLS` menos
  disco (mantiene el checklist del onboarding).
- `media/walkthrough/step-install.md` y su descripción en
  `package.json` — eliminada la afirmación "Install 15 skills"; ahora
  "Install all SpecBox skills and hooks".
- `src/views/skills-tree.ts` — refactor mayor: del flat list al árbol
  jerárquico (7 categorías root colapsables → skills hijos) +
  `command` en cada `SkillItem` + tooltip rico desde
  `SKILL_DEFAULTS.whatItDoes`.

Tests: 34/34 verdes (`npm test` en `vscode-extension/`), sin
regresión sobre los 14 OAuth previos. El smoke test manual del
reviewer humano (AC-25 del PRD) queda como gate antes del merge —
auto-merge OFF para esta US.

- Plan: [doc/plans/US-VSCODE-DISCOVERABILITY_plan.md](doc/plans/US-VSCODE-DISCOVERABILITY_plan.md)
- PRD: [doc/prd/US-VSCODE-DISCOVERABILITY_prd.md](doc/prd/US-VSCODE-DISCOVERABILITY_prd.md)
- Discovery: [doc/discovery/vscode_discoverability_sidebar/icp_jtbd.md](doc/discovery/vscode_discoverability_sidebar/icp_jtbd.md)

## Loopback Resilience (v6.6.1)

UC-652 (bajo US-VSCODE-GITHUB-OAUTH) cierra dos defectos del flujo OAuth de la
extensión descubiertos en el smoke test post-deploy de v6.3.0 (cross-repo con
`specbox_cloud#49` / UC-905):

1. **Timeout del loopback prematuro.** `startLoopbackServer` armaba el timeout
   de 5 min al crear el server, antes de que el usuario navegara. Leer la
   pantalla "Confirm your account" del cloud, cambiar de cuenta GitHub o
   despejar el diálogo "open external website" de VS Code agotaba el reloj y el
   callback caía en un puerto muerto (`ERR_CONNECTION_REFUSED`). Ahora el
   timeout es de **10 min** y se arma vía `armTimeout()` idempotente **sólo tras
   un `openExternal` exitoso**, de modo que el tiempo de setup no cuenta contra
   la ventana de sign-in.

2. **Token persistido sin verificar identidad.** `runSignIn` guardaba el
   `mcp_token` sin comprobar a qué developer resuelve. Ahora llama
   `fetchWhoami()` antes de persistir, rechaza con `identity_unverified` si el
   cloud no confirma identidad, y muestra el handle real ("Signed in as
   @handle"). Cierra **UC-645 AC-05**, que estaba especificado pero sin
   implementar.

Helper `describeSignInError()` centraliza copys accionables (`timeout` /
`browser_blocked` / `identity_unverified`) para el onboarding y el comando
directo `specbox.signIn`. Strings nuevas en los bundles l10n EN + ES.

Sólo toca `vscode-extension/` (`oauth.ts`, `auth.ts`, `extension.ts`, l10n) +
tests (47/47 verde, +4 del timeout diferido).

- PR: [#80](https://github.com/EmbedBuild/specbox-engine/pull/80)

## Fast Activate (v6.6.2)

UC-653 (bajo US-VSCODE-GITHUB-OAUTH) es un hotfix crítico descubierto tras
publicar v6.6.1 al Marketplace: la extensión se quedaba indefinidamente en
**"Activating…"** para prácticamente todos los usuarios.

**Causa raíz** (confirmada vía Extension Host log: `specbox-engine` inicia
activación y nunca reporta finalización): `activate()` hacía `await` en serie
de `health.run()`, el prompt del `ExtensionUpdater` y el onboarding gate. El
`showInformationMessage("SpecBox Engine updated to vX. Update extension?")` del
updater **bloquea hasta que el usuario pulsa**. Como cada release bumpa la
versión, tras publicar v6.6.1 todos tenían engine local 6.6.0 ≠ extensión
6.6.1 → el prompt saltaba en cada primer `activate` y, al estar `await`eado,
VS Code se quedaba en "Activating…" hasta que el usuario respondiera.

**Fix** (sólo `vscode-extension/src/extension.ts`): `activate()` ahora registra
comandos/vistas y arma el polling de identidad de forma **síncrona**, y retorna
de inmediato. Todo el trabajo lento o interactivo (health check, prompt de
update, onboarding gate, refresh inicial de identidad) se mueve a
`runStartupTasks()`, disparado con `void` (fire-and-forget) y con guards en cada
fase para que nada pueda volver a colgar la activación.

Trade-off aceptado: las welcome views del sidebar pueden mostrar estado vacío
~1-15s al arrancar (hasta que `health.run()` resuelve y dispara `setContext`) —
un parpadeo breve a cambio de eliminar el cuelgue.

- PR: [#81](https://github.com/EmbedBuild/specbox-engine/pull/81)

## Zero-Friction Onboarding (v6.7.0)

Dos features encadenadas del onboarding de la extensión VSCode, mergeadas en
PR [#82](https://github.com/EmbedBuild/specbox-engine/pull/82).

**US-VSCODE-ZERO-PYTHON** elimina Python del path del cliente. El beta-tester
ICP-2 se bloqueó por la dependencia de Python; como el MCP server se sirve
gratis en remoto, el modo Local no aportaba valor suficiente para justificar
la fricción. Cambios en `vscode-extension/`:

- `src/mcp.ts` — eliminado el modo Local del MCP (la QuickPick local/remote, la
  rama `uv run` / `python -m server.server` y el `findEnginePath` huérfano).
  `configureSpecbox()` ahora escribe directamente el endpoint hospedado
  (`npx mcp-remote https://mcp-specbox-engine.jpsdeveloper.com/mcp`). Engram
  migra de `pip/pipx install engram` a `brew install
  gentleman-programming/tap/engram` (binario nativo sin dependencias) con
  fallback a instalación manual del binario cuando no hay Homebrew. Engram
  sigue **Required**. Helpers puros testeables: `buildRemoteServerConfig`,
  `buildEngramInstallPlan`.
- `src/health.ts` + `constants.ts` + `statusbar.ts` + `onboard.ts` +
  `views/status-tree.ts` — eliminado `checkPython`, el campo `python` de
  `HealthResult`, `REQUIRED_PYTHON_VERSION` y toda referencia derivada. El panel
  Status ya no muestra fila Python.
- `media/walkthrough/step-prerequisites.md`, `package.json`, `README.md`,
  `README.es.md` — purgada toda mención a Python; Engram documentado vía brew.

**US-VSCODE-PREREQ-GATE** añade un gate de prerequisitos no bloqueante. Cierra
el drift entre "lo que la UI sugiere" y "la realidad" (JE-G.3): un usuario podía
creer que SpecBox estaba operativo cuando le faltaba una pieza crítica.

- `src/prerequisites.ts` (nuevo) — `evaluatePrerequisites(health)` puro:
  clasifica el entorno en `ready | degraded` sobre el set crítico (Claude Code,
  Engram, Node, MCP SpecBox, MCP Engram; GGA es opcional y no dispara).
  `buildPrereqWarning` produce el texto accionable. `showPrereqGate` es la capa
  vscode.
- `src/extension.ts` — en `runStartupTasks`, tras el health check, dispara el
  gate con su propio try/catch (patrón fire-and-forget de v6.6.2): si
  `degraded`, `showWarningMessage` no bloqueante con botones (Run Setup Wizard /
  Configure MCP / Open Guide) avisando que SpecBox puede no funcionar
  correctamente; silencio si `ready`. Nuevo comando `specbox.checkPrerequisites`
  ("SpecBox: Check Prerequisites") para re-evaluar a demanda.
- Documentado en walkthrough + README EN/ES; comando en `package.json` +
  `package.nls.json` / `package.nls.es.json`.

Tests: +9 (`tests/mcp.test.mjs` + `tests/prerequisites.test.mjs`), 56/56 verde.
Decisiones de producto: sin fallback air-gapped (MCP remoto gratuito); severidad
warning no bloqueante; alcance del gate incluye MCP configurado.

## Engine Auto-Clone (v6.9.0)

US-VSCODE-AUTOCLONE cierra el funnel de onboarding en máquina limpia: hasta
v6.8.0 la extensión VSCode, cuando no encontraba el engine en disco
(`resolveEnginePath()` fallaba en config/workspace/rutas comunes), solo ofrecía
un `showOpenDialog` que apuntaba a una carpeta inexistente — el usuario no sabía
qué repo clonar. Como el repo es **público**, la extensión ahora lo clona ella
misma, **automáticamente y sin preguntar** (solo notifica).

- **UC-109/UC-110** (`vscode-extension/src/install.ts`): helpers puros
  `ENGINE_REPO_URL`, `managedEnginePath()` (`~/.specbox/specbox-engine`),
  `isManagedPath()`; y `cloneManagedEngine(deps)` con git runner inyectable que
  **nunca lanza** y limpia el dir parcial si el clone aborta. `resolveEnginePath`
  inserta el auto-clone como paso 3.5 (entre rutas comunes y `showOpenDialog`),
  idempotente: un clon gestionado ya presente se reutiliza sin re-clonar.
- **UC-111** (`vscode-extension/src/updater.ts`): `pullManagedEngine()` hace
  `git pull --ff-only` como Phase 0 de `runUpdateFlow`, **solo** si el engine
  resuelto ES el gestionado (`isManagedPath===true`). Un clon propio del usuario
  en otra ruta nunca se toca (protección ICP-1). Un pull fallido es un warning no
  bloqueante (patrón fire-and-forget v6.6.2).
- **UC-112**: walkthrough + README (ES+EN) describen el auto-clone; el `git clone`
  manual deja de ser prerequisito de la extensión (la instalación CLI se conserva).

Tests: +14 (`vscode-extension/tests/autoclone.test.mjs`), 94/94 verde, `tsc` limpio.
Auto-merge OFF: el smoke real del clone contra GitHub en máquina limpia fue el
gate humano (PR #86, mergeado).

- Plan: [doc/plans/US-VSCODE-AUTOCLONE_plan.md](doc/plans/US-VSCODE-AUTOCLONE_plan.md)
- PRD: [doc/prd/US-VSCODE-AUTOCLONE_prd.md](doc/prd/US-VSCODE-AUTOCLONE_prd.md)

## Atomic Backend Switch (v6.9.1)

US-BACKEND-SWITCH-NATIVE rediseña "cambiar de backend" como **una sola
operación atómica** y cierra el path-bug de MCP remoto que dejaba el cambio
hacia/desde `native` (Cloud) roto en producción (reproducido en dogfooding:
un `migrate_backend(freeform→native, dry_run=True)` leía el filesystem del
**servidor MCP remoto** —22 US/112 UC del propio engine en el VPS, o 0/0— en
vez de las 11/88 del cliente).

- **Tool atómica `switch_project_backend`** (`server/tools/migration.py`):
  orquesta migrate → seed identity → switch de los 3 lugares de config →
  exit-report como **todo-o-nada**. `migrate_backend`/`switch_backend` siguen
  funcionando pero recomiendan la tool atómica.
- **Orquestador testeable** (`server/migration/orchestrator.py`): `run_switch`
  compone los pasos como callables inyectables; `rollback.py` deshace la
  migración de datos (DELETE del proyecto native nuevo) si un paso posterior
  falla; `count_guard.py` bloquea el execute si el dry-run leyó 0 items o el
  conteo confirmado no coincide.
- **Content-passing** (`resolve_source_backend`): el source `freeform` se lee
  del `source_content` del cliente vía memory-mode `FreeformBackend`, nunca del
  FS del servidor. trello/plane de la API; native del `NativeBackend` DTO.
- **Native**: `require_dev_token` fail-fast antes de cualquier I/O;
  `write_target` preserva estados (no degrada a backlog como `import_spec`);
  colisión `on_collision`; `native_exit_report` (reservas/membresías/audit)
  mostrado antes de confirmar; `onboard_project --backend native` documenta
  `native_db_state=empty`.
- **Skill `/switch-backend` online-first**: elimina la precondición bloqueante
  "MCP local" (contradecía la decisión canónica "Transporte único MCP remoto +
  content-passing", UC-668), lee el source del cliente y escribe los 3 lugares
  de config de vuelta en el cliente (write-back).

Tests: `tests/test_backend_switch_native.py` — 24 passed (0 skipped con
`docker compose -f docker-compose.dev.yml up`). AC-18 reproduce el bug original;
AC-19 migra freeform→native contra Postgres real preservando estados.

- PRD: [doc/prd/US-BACKEND-SWITCH-NATIVE_prd.md](doc/prd/US-BACKEND-SWITCH-NATIVE_prd.md)
- Plan: [doc/plans/US-BACKEND-SWITCH-NATIVE_plan.md](doc/plans/US-BACKEND-SWITCH-NATIVE_plan.md)
- Discovery: [doc/discovery/backend_switch_native/icp_jtbd.md](doc/discovery/backend_switch_native/icp_jtbd.md)

## Batch Ingest a Native (v6.9.2)

US-NATIVE-BATCH-INGEST cierra el gap de **transporte** de v6.9.1 descubierto en
dogfooding migrando `specbox_cloud` (133 KB / 568 ítems) freeform→native: la
**lógica** del switch funcionaba, pero `switch_project_backend` con
`source_type='freeform'` exigía el `items.json` completo como **un único string**
(`source_content`), y un board real no cabe fiablemente en un parámetro de tool sin
riesgo de truncado/corrupción silenciosa. El MCP es siempre remoto desde v6.7.0 (no
ve el filesystem del cliente).

La solución es **ingesta por lotes server-side**: una sesión de migración
multi-llamada `start → append × N → commit` donde el cliente envía el `items.json` en
chunks pequeños y verificables (SHA-256 por chunk), el servidor los acumula en una
zona de staging efímera, y al commit verifica integridad global (hash reensamblado +
conteo declarado) **antes** de ingestar en **una transacción atómica**. El chunking es
solo del transporte; la escritura sigue siendo todo-o-nada (rollback total ante fallo
a mitad). No relaja el blindaje de seguridad (dev_token validado server-side al start,
escritura solo en el tenant, sin exponer `service_role`).

| Componente | Archivo | Rol |
|------------|---------|-----|
| Sesión + staging | `server/migration/batch_session.py` | `MigrationSession` + `SessionStore` (dict en memoria + TTL, time_fn/id_fn inyectables). Staging efímero: una sesión sin commit expira y el cliente reinicia limpio (no hay resume). |
| Integridad | `server/migration/integrity.py` | `sha256_hex` puro — único punto de hashing para chunk-check y pre-flight global. |
| Escritura atómica | `server/backends/native_backend.py::ingest_atomic` | 3 fases (US, UC+AC, comments) en **una** `conn.transaction()` → rollback total real (vs el per-item `continue` de `write_target`). Estados preservados verbatim. Re-valida membresía al commit (cubre TTL de identidad expirado en migración lenta). |
| Plan I/O-free | `server/migration/writer.py::build_write_plan` | Clasificación + resolución de parent + orden como datos puros, compartido por `write_target` (intacto) e `ingest_atomic`. |
| Tools MCP | `server/tools/migration.py` | `start_migration_session` (valida dev_token 1 vez, cache reusado), `append_migration_chunk` (hash por chunk), `commit_migration_session` (pre-flight global + ingesta atómica). `switch_project_backend` acepta `batch_session_id` y rutea su paso de escritura por la ingesta cuando el source freeform excede `BATCH_TRANSPORT_THRESHOLD_BYTES` (64 KB). |
| Skill | `.claude/skills/switch-backend/SKILL.md` | Paso 3b: plan de transporte por lotes (nº chunks, tamaño, hash) + resumen post-commit, **sin pegar el blob**. |

Envelopes de las tools: `accepted` / `CHUNK_HASH_MISMATCH` / `SESSION_NOT_FOUND` /
`DUPLICATE_CHUNK_INDEX` / `UNAUTHENTICATED` / `FORBIDDEN_SESSION` / `committed` /
`PREFLIGHT_FAILED` / `COMMIT_FAILED`.

Tests: `tests/test_native_batch_ingestion.py` — 19 passed (10 unit + 9 Postgres-gated
con `docker compose -f docker-compose.dev.yml up`). El E2E (UC-684) cruza un
`items.json` **≥100 KB / 120 UC** de estados mixtos por el transporte por lotes real
verificando Postgres == source y estados done/backlog 1:1 — el test que faltaba y por
el que el gap pasó (los previos usaban fixtures pequeñas en memoria). Suite native sin
regresión (78 passed).

- PRD: [doc/prd/US-NATIVE-BATCH-INGEST_prd.md](doc/prd/US-NATIVE-BATCH-INGEST_prd.md)
- Plan: [doc/plans/US-NATIVE-BATCH-INGEST_plan.md](doc/plans/US-NATIVE-BATCH-INGEST_plan.md)
- Discovery: [doc/discovery/native_batch_ingestion/icp_jtbd.md](doc/discovery/native_batch_ingestion/icp_jtbd.md)
- Hallazgo origen: [HALLAZGO-v6.9.2-transporte-source-grande.md](HALLAZGO-v6.9.2-transporte-source-grande.md)

## Provisión + contrato de project_id (v6.9.3)

US-NATIVE-PROVISION cierra los 2 gaps que bloquearon el caso de uso central
("subir mi proyecto a SpecBox Cloud") descubiertos validando v6.9.2 al migrar
`specbox_cloud` freeform→native de cero: el **transporte por lotes funcionó**
pero la migración se bloqueó en `start_migration_session` con
`Developer X is not a member of project EmbedBuild/specbox_cloud`. Dos gaps de
diseño combinados:

- **GAP 1 — provisión**: el path batch (`start → append → commit`) no
  provisionaba `public.projects` + `public.project_members` cuando el proyecto
  nace de cero. Huevo-gallina **enforced por FK**
  (`project_members.project_id REFERENCES projects(project_id)`): para ser
  miembro el tenant debe existir, pero lo crearía la propia migración. El path
  **no-batch** (`migrate_backend`) sí provisionaba; el batch no.
- **GAP 2 — contrato project_id**: engine/native usa `owner/repo` (TEXT libre);
  el panel slugifica a `embedbuild-specbox-cloud`. Los dos lados nunca acordaron
  el formato.

Decisiones canónicas (discovery `provision_native_project_id_contract`,
registradas en `app_spec.md` §6 + `doc/decisions/native_project_id_contract.md`):

- **D1 `native_project_id_contract`** = `owner/repo` canónico almacenado +
  display slug derivado URL-safe. Punto único de normalización
  `server/coordination/project_id.py` (`canonical_project_id` / `display_slug` /
  `validate_project_id`); el panel consume el mismo contrato. Cero migración de
  ids existentes, sin colisión cross-owner, trazabilidad GitHub directa.
- **D2 `native_provision_authority`** = el engine auto-provisiona **al creador**
  como `project_admin` server-side en migración de cero (excepción de bootstrap).
  El §6 del panel (*"panel = único editor de project_members"*) se acota: el
  panel sigue siendo editor de **otros** miembros; un proyecto pre-existente del
  que el caller no es miembro NO se auto-une (`FORBIDDEN`).

| Componente | Archivo | Rol |
|------------|---------|-----|
| Helper canónico | `server/coordination/project_id.py` | `canonical_project_id` / `display_slug` / `validate_project_id` — punto único de verdad (UC-818) |
| Role en seed | `server/migration/native_handling.py::seed_native_identity(role=...)` + `identity.py::add_project_member` (valida `VALID_PROJECT_ROLES`) | creador como `project_admin` (UC-819) |
| Provisión atómica | `server/migration/native_handling.py::provision_native_project` | UPSERT `projects` + `seed_native_identity(project_admin)` + fila `audit_log` (`OP_PROVISION_PROJECT`), una transacción, idempotente, no degrada admin (UC-820) |
| Integración batch | `server/tools/migration.py::start_migration_session` (`_maybe_auto_provision`) | auto-provisión antes del gate cuando el target nace de cero; `ForbiddenError` → envelope `FORBIDDEN` (UC-821) |

Seguridad (Frontier 2): la provisión valida el dev_token (fail-fast), escribe
solo en el tenant del caller, queda en `audit_log`, no relaja `deny_anon` ni
expone `service_role`; el DSN nunca se serializa.

Tests: `tests/test_native_provision.py` — 15 passed (4 puros UC-818 + 11
Postgres-gated). El E2E `test_e2e_provision_then_migrate_from_scratch` (UC-822)
cruza BD vacía → auto-provisión → ingesta por lotes → verificación (project_id
canónico, creador `project_admin`, 1 US / 40 UC / 120 AC con estados
done/backlog preservados, display_slug correcto) — el camino sin cobertura por
el que el gap de v6.9.2 pasó. Suite native sin regresión (402 passed).

**Cambio coordinado en el panel** (`EmbedBuild/specbox_cloud`, su propio repo):
relajar la validación INSERT de `apps/api/src/routes/projects.ts:140,173` para
aceptar `owner/repo` cuando el backend es native + derivar el display slug con
el contrato compartido. Documentado en `doc/decisions/native_project_id_contract.md`.

- PRD: [doc/prd/US-NATIVE-PROVISION_prd.md](doc/prd/US-NATIVE-PROVISION_prd.md)
- Plan: [doc/plans/US-NATIVE-PROVISION_plan.md](doc/plans/US-NATIVE-PROVISION_plan.md)
- Discovery: [doc/discovery/provision_native_project_id_contract/icp_jtbd.md](doc/discovery/provision_native_project_id_contract/icp_jtbd.md)
- Decisión: [doc/decisions/native_project_id_contract.md](doc/decisions/native_project_id_contract.md)
- Hallazgo origen: [HALLAZGO-v6.9.3-provision-y-project-id.md](HALLAZGO-v6.9.3-provision-y-project-id.md)

## Tenant huérfano + auto-provisión robusta (v6.9.4)

US-ORPHAN-PROVISION cierra el cuarto eslabón de la cadena de hallazgos del
dogfooding: v6.9.3 implementó la lógica de auto-provisión correctamente, pero
**otra ruta la desactivaba en el camino real**. Validando v6.9.3 migrando
`specbox_cloud` freeform→native de cero, `start_migration_session` seguía
bloqueándose con `FORBIDDEN` sobre una BD verificada vacía.

**El bug, en una frase**: `setup_board`
([`server/backends/native_backend.py`](server/backends/native_backend.py)) hacía
`INSERT INTO projects` **sin crear membresía**, fuera de `provision_native_project`.
Se dispara en cada `set_auth_token` native (`spec_driven.py:276`), en `import_spec`
y en migraciones legacy. Cualquiera deja un **tenant huérfano** (fila en
`public.projects` con CERO miembros). Entonces `_maybe_auto_provision`
(`migration.py`) veía `exists=True` → `return False` (creía que era un tenant
legítimo) → el gate de membresía → **FORBIDDEN**. El ecosistema se saboteaba a sí
mismo. El test de v6.9.3 (UC-822) no lo veía porque ejercía el camino **limpio**
(BD vacía → provisión), nunca un `setup_board` previo creando la fila huérfana.

**Decisión (discovery `orphan_tenant_provision`): Enfoque Combinado — defensa en
profundidad**, dos capas aditivas:

- **FIX A (UC-824)** — `setup_board` para native delega en `provision_native_project`
  (tenant + membresía en una transacción), resolviendo la identidad del session
  `dev_token`. Nunca deja un proyecto con cero miembros. Idempotente: no degrada un
  admin existente. `setup_board` ahora **requiere** un token válido (no puede crear
  un tenant sin dueño). El id no se valida contra el contrato canónico aquí
  (`validate_id=False`) — preserva la permisividad histórica de `setup_board` sobre
  el id; el camino de migración from-scratch sí valida (`validate_id=True`).
- **FIX B (UC-825)** — `_maybe_auto_provision` distingue **tenant huérfano**
  (0 miembros → adopta, crea la membresía del creador) de **tenant real**
  (≥1 miembro → `FORBIDDEN`, AC-13 intacto). La condición pasa de "no existe" a
  "no existe O sin miembros".

**Invariante**: *un tenant native nunca debe existir sin al menos un miembro; si por
estado sucio legacy lo está, la auto-provisión lo adopta*. El flujo es convergente:
cualquier estado sucio (0 miembros) se recupera a limpio (1 miembro = creador admin)
en el primer `start_migration_session`, sin `FORBIDDEN`.

**Seguridad**: un tenant con 0 miembros no tiene a quién robar — adoptarlo es seguro.
**No contradice la decisión canónica D2** (`native_provision_authority`): la refina,
precisando que "proyecto pre-existente protegido por AC-13" = fila con ≥1 miembro.

| Componente | Archivo | Cambio |
|------------|---------|--------|
| FIX A | `server/backends/native_backend.py::setup_board` | Delega en `provision_native_project` (UC-824) |
| FIX A helper | `server/migration/native_handling.py::provision_native_project` | Params opcionales `name` + `validate_id` |
| FIX B | `server/tools/migration.py::_maybe_auto_provision` | Cuenta `project_members`; adopta huérfano (UC-825) |

**Estándar transversal adoptado (UC-827)**: los E2E de migración deben partir de
**estados sucios realistas**, no solo de BD/fixtures vírgenes. El patrón recurrente
de los 4 hallazgos del dogfooding fue *"el test pasa con el camino ideal; el
dogfooding encuentra el camino real"*. El E2E `test_e2e_orphan_then_migrate_recovers`
([`tests/test_native_orphan_provision.py`](tests/test_native_orphan_provision.py))
crea la fila huérfana **primero** y verifica la recuperación end-to-end por el
transporte por lotes (≥64 KB), preservando estados done/backlog 1:1. Tests:
`tests/test_native_orphan_provision.py` 7 passed; suite native completa sin regresión
(396 passed).

- PRD: [doc/prd/US-ORPHAN-PROVISION_prd.md](doc/prd/US-ORPHAN-PROVISION_prd.md)
- Plan: [doc/plans/US-ORPHAN-PROVISION_plan.md](doc/plans/US-ORPHAN-PROVISION_plan.md)
- Discovery: [doc/discovery/orphan_tenant_provision/icp_jtbd.md](doc/discovery/orphan_tenant_provision/icp_jtbd.md)
- Hallazgo origen: [HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md](HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md)

## Tenant-Scoped Keys + FreeForm exploded migration (v6.9.5)

Tres cierres descubiertos en el dogfooding de migrar `Dental-Data/DDBoss-Web-Saas`
freeform→native (PRs #100/#101/#102):

**UC-707 — Tenant-scoping de PKs (el bloqueante).** El ingest atómico
FreeForm→Native colisionaba en `user_stories_pkey` porque la PK era el `us_id`
lógico (`US-01`) **sin** namespacing por proyecto: en un Postgres multi-tenant
compartido dos proyectos no podían tener ambos un `US-01`. Causa raíz **solo de
schema** — `native_backend.py` ya estaba tenant-scoped (toda query filtra
`project_id AND id`, todo INSERT pasa `project_id`); solo faltaba la constraint.
`0009_tenant_scoped_pks.sql` (+ mirror supabase) mueve la PK de
US/UC/AC a compuesta `(project_id, id)` y recablea las 2 FKs hijas a compuestas
same-tenant (idempotente vía guards `pg_constraint`, sin backfill). Bundle:
envelope accionable `SOURCE_TOO_LARGE_USE_BATCH` (>64 KB freeform→native sin
sesión de lotes), target native autosuficiente desde `dev_token` en
`_ensure_target` (antes el imposible "Target backend not configured"), y
`parse_item_id` aceptando sufijo alfabético (`[UC-004b]` → `UC-004b`).

**UC-708 — Tests stale.** 7 en `test_spec_mutations.py` (el mock
`_fake_get_session_backend` no aceptaba el kwarg `items_content` de UC-660) + 2 en
`test_audit_log_destructive.py` (UC-706 hizo que `create_us/uc/ac` auditen; los
tests esperaban el contrato previo). Conteos/orden ajustados contra Postgres dev.

**UC-709 — Dialecto FreeForm exploded en `/switch-backend`.** Algunos repos
guardan FreeForm como `index.json` anidado (`{user_stories:[...]}`) +
`us/*.md`/`uc/*.md` con AC en checkboxes `- [x]`, en vez del array `items.json`
plano que la migración consume — fallaba en el preview con `got dict`. Nuevo
`server/migration/freeform_normalize.py` (transform puro anidado→flat; modo
*faithful* con `ac_texts`, modo *degradado* sintetizando placeholders desde
`ac_total` con conteos exactos + flag `ac_degraded`). Error accionable en
`freeform_backend.py` que nombra el dialecto + la receta. `SKILL.md` añade
pre-flight de formato (Paso 3/3a, el fallo sale en el paso 0) + gate de
prerequisitos native (Paso 2: tenant + whoami + DSN-en-server) antes de leer el
source. Validado contra escala DDBoss (15 US / 82 UC / 501 AC).

- PRs: [#100](https://github.com/EmbedBuild/specbox-engine/pull/100),
  [#101](https://github.com/EmbedBuild/specbox-engine/pull/101),
  [#102](https://github.com/EmbedBuild/specbox-engine/pull/102)

## Dual-Backend — espejo Native best-effort (v6.10.0)

US-11 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) permite que un
proyecto **reporte a dos backends a la vez**: un primario (`trello`/`plane`/`freeform`,
fuente de verdad, escritura síncrona) y un **espejo Native** best-effort (escritura tras el
primario, fallos logueados y nunca propagados; las lecturas solo consultan el primario).
Caso disparador: cliente con Trello intocable (alimenta herramienta de cliente-final) que
quiere el panel Native a la vez. Regla dura: primario `native` → dual prohibido
(`MIRROR_ON_NATIVE_FORBIDDEN`).

| Componente | Archivo | Rol |
|---|---|---|
| Wrapper | `server/backends/dual_backend.py` | `DualBackendWrapper(SpecBackend)`: duplica los 12 métodos de escritura, resuelve el item espejo por id lógico (`UC-XXX`/`US-XX`), traga y loguea todo fallo del espejo |
| Dispatch | `server/auth_gateway.py::get_session_backend` | Único chokepoint: con bloque `mirror` en config envuelve el primario; sin él, path idéntico al baseline |
| Config | bloque `mirror` en los 3 lugares de verdad (registry / app_spec / settings) | Persistencia transaccional con rollback (`apply_switch_transactional`); solo `project_id`+`dev_token`, nunca DSN (Frontier 2) |
| Tools | `enable_mirror` / `disable_mirror` | Validan auth del espejo + backfill inicial idempotente |
| Tests | `tests/test_dual_backend.py` | Garantía crítica vía fallo inyectado: el primario nunca se degrada por el espejo |

- PRs: [#106](https://github.com/EmbedBuild/specbox-engine/pull/106)–[#110](https://github.com/EmbedBuild/specbox-engine/pull/110)

## UC Lifecycle Metrics (v6.10.0)

US-12 (board del orquestador, satélite engine) hace medible el lead time real de
implementación por UC en el backend Native, corrigiendo tres defectos estructurales: el
inicio nunca se registraba (`start_uc_atomic` hace un UPDATE crudo sin auditar), el evento
de fin era best-effort y podía perderse (`_release_uc_native` traga fallos por diseño), y
no existían `started_at`/`completed_at`. **El cómputo vive en la BD; el engine queda fino.**

### Captura (migración 0012)

- **Triggers sobre `use_cases`**: cualquier escritor de `state` — presente o futuro,
  incluido SQL manual — queda capturado transaccionalmente. `AFTER UPDATE OF state … WHEN
  (OLD.state IS DISTINCT FROM NEW.state)` inserta en **`uc_state_transitions`**
  (append-only: from/to, `us_id` snapshoteado, developer, source, occurred_at; sin FKs,
  como `audit_log`). Un BEFORE trigger mantiene `use_cases.started_at` (primer inicio gana,
  re-ciclos no lo pisan) y `completed_at` (último cierre gana).
- **Contexto vía session GUCs** (`SET LOCAL`, mueren con la transacción — cero fuga de
  pool): `server/coordination/lifecycle.py::set_lifecycle_context` inyecta
  `app.developer_id` / `app.change_source` en los 3 escritores (`start_uc_atomic`,
  `update_item` con cambio de state — side-fix: UPDATE+audit ahora atómicos —,
  `ingest_atomic` con `source='import'`). Degradación honesta: sin GUC → developer NULL +
  `interactive`, nunca un error.
- **Imports excluidos por construcción**: la ingesta hace INSERT (no dispara el trigger de
  UPDATE) → UCs importados ya `done` quedan sin transiciones ni timestamps y no contaminan
  la métrica.

### Analítica (0013, 0014, 0016) — contrato de honestidad

Vistas planas (no matviews; <3ms con 1000 UCs): **`v_uc_lifecycle`** (lead_time,
`measurable`, `cycles`, `last_source`), **`v_lifecycle_kpis`** (p50/p90 SOLO sobre medibles
interactivos; **`coverage_pct`** dice qué fracción del done representa la métrica;
`done_by_import`/`done_unmeasured` siempre visibles, jamás promediados), `v_us_progress`,
`v_weekly_throughput`, y **`v_active_time_estimate`** (clustering de sesiones por huecos
>30min — estimación etiquetada como tal, NULL antes que un 0 falso). Consumo: rol
**`specbox_analytics_ro`** (0014, GRANT solo vistas — el panel lee directo) y tool MCP
read-only **`get_project_kpis`** (tenant = el de la sesión). NO confundir con la vista
`project_kpis` (0011, US-08): dominio progreso/reservas, intacta.

### Backfill histórico (0015) — preparado, NO ejecutado

`fn_backfill_lifecycle(project_id, dry_run DEFAULT true)` estima el histórico pre-0012
(started_at ← primer `reserve_uc` del audit o `branch_registry.created_at`; completed_at ←
`complete_uc`, con flag `burst` para ráfagas <10s) marcando todo `source='backfill_estimate'`
y rellenando solo NULLs. **Transiciones = verdad, columnas = caché**: el rollback es
`DELETE … WHERE source='backfill_estimate'` + `fn_recompute_lifecycle_columns(project_id)`,
restauración exacta. La ejecución por proyecto queda gated por la calibración de
estimadores contra datos reales de triggers en periodo solapado.

### Despliegue

Producción aplica los espejos del ledger (`supabase/migrations/20260611000012..16`) vía
`apply_migration` en orden — **pendiente de aplicar**; hasta entonces `get_project_kpis`
fallará en prod por vistas inexistentes. El runner local (`server/db/migrate.py`) las
re-aplica solo en dev/tests.

- PRs: [#111](https://github.com/EmbedBuild/specbox-engine/pull/111)–[#117](https://github.com/EmbedBuild/specbox-engine/pull/117)
- PRD/Plan: `doc/prd/uc-lifecycle-metrics/prd.md` + `doc/plans/uc-lifecycle-metrics_plan.md` en `EmbedBuild/specbox-manager`
- Tests: `tests/test_uc_lifecycle_capture.py` + `TestCompleteTransitionResilience` en `tests/test_audit_uc_lifecycle.py`

## reserve_uc reentrante en transacción (v6.10.1)

UC-1208 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) es un hotfix
descubierto en dogfooding cerrando MGR-US-01 UC-06: tras `reserve_uc(UC)`, llamar `start_uc(UC)`
con el mismo developer fallaba con `current transaction is aborted, commands ignored until end
of transaction block`. Las lecturas, `reserve_uc` directo y `move_uc` funcionaban; solo `start_uc`
rompía.

**Causa raíz**: `reserve_uc` ([server/coordination/reservations.py](server/coordination/reservations.py))
implementaba el re-reserve idempotente capturando `asyncpg.UniqueViolationError` y ejecutando un
`SELECT` de recuperación. En Postgres, **un statement que falla aborta toda la transacción**, y un
`try/except` de Python NO abre un savepoint que la rescate. `start_uc_atomic` envuelve `reserve_uc`
+ `UPDATE use_cases` en una sola transacción; cuando la UC ya estaba reservada por el mismo dev, el
INSERT duplicado violaba la PK `uc_reservations_pkey(project_id, uc_id)`, abortaba la tx, y el SELECT
de recuperación y el UPDATE posterior devolvían el error. **No** era el trigger de lifecycle de la
US-12 (verificado: el `UPDATE use_cases` con sus triggers funciona aislado). El test unitario no lo
detectaba porque usaba un `FakeConn` mock sin la semántica de "transacción abortada" de Postgres
real — patrón UC-827.

**Fix**: `INSERT ... ON CONFLICT (project_id, uc_id) DO NOTHING RETURNING *`. Nunca lanza → la
transacción externa nunca se aborta → el SELECT de recuperación es seguro. Idempotencia (mismo dev)
y `AlreadyReservedError` (otro dev) preservados; el `audit_log` solo se escribe en la primera reserva
genuina. Test PG-gated nuevo `test_start_uc_atomic_after_reserve_same_dev_does_not_abort_tx` reproduce
el bug (sin el fix falla con `InFailedSQLTransactionError`; con el fix pasa). Suite
native/reservas/coordinación/lifecycle: 347 passed.

- PR: [#118](https://github.com/EmbedBuild/specbox-engine/pull/118)

## enable_mirror: auto-init del registry en cloud (v6.10.2)

UC-1104 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) es un hotfix de
producción descubierto en dogfooding al activar el espejo Native sobre el cliente
`potencial_digital_2026` (primario Trello). El backfill Trello→Native se ejecutó y verificó
(11 US / 36 UC / 111 AC), pero persistir el bloque `mirror` falló con `CONFIG_FAILED` /
`failing_place: "registry"` / `Project registry not found at /data/state/projects.json`, así que
el dual-write nunca se activó. El primario (Trello) quedó read-only todo el flujo — la garantía
dura se respetó.

**Causa raíz**: `_write_registry_mirror`
([server/migration/transactional_switch.py](server/migration/transactional_switch.py)) lanzaba
`FileNotFoundError` cuando `$STATE_PATH/projects.json` no existía y `KeyError` cuando el slug no
estaba. En el host MCP **cloud** ese registry nunca se materializó para el proyecto, por lo que la
**primera** escritura de config (el bloque mirror) abortaba la transacción de 3 lugares en el
primer escritor.

**Fix**: el espejo es opt-in best-effort sobre un primario ya vivo, así que ahora auto-bootstrapea
lo que necesita: un `projects.json` ausente se crea, y una entrada de proyecto ausente se
**auto-siembra desde el PRIMARIO** (`spec_backend`/`board_id` tomados de `spec_backend_config` de la
sesión + el arg `primary_board_id`) **antes** de fijar el bloque `mirror`. Una entrada existente
**nunca** se sobrescribe — el primario en disco gana; el bloque mirror es puramente aditivo.
`disable_mirror` sobre fichero/entrada ausente es un no-op seguro. La rollback transaccional borra
el `projects.json` recién creado si un lugar posterior falla (`_read_registry_snapshot` registra
`file_present`; `_restore_registry` lo borra) → el dir de estado queda byte-idéntico.
`primary_backend`/`primary_board_id` se propagan `enable_mirror → apply_mirror_transactional →
_write_registry_mirror` como kwargs opcionales (default vacío → 100% backwards-compatible).

5 tests nuevos en [tests/test_dual_backend.py](tests/test_dual_backend.py) ejercen el estado sucio
real que la suite previa no tocaba (la fixture `trello_project` siempre pre-sembraba la entrada —
patrón UC-827): auto-init con fichero ausente, auto-seed con slug ausente, primario existente no
sobrescrito, rollback que borra el fichero creado, y un e2e de `enable_mirror` que siembra el
registry desde la sesión. Suites dual-backend + transactional-switch: 63 passed, 1 skipped.

- Spec: [doc/feature-requests/FIX_enable_mirror_registry_autoinit.md](doc/feature-requests/FIX_enable_mirror_registry_autoinit.md)

## Living Funnel — site publish-on-release + activation event (v6.11.1)

Tres US del board del orquestador `EmbedBuild/specbox-manager` (satélite engine) cierran el
**funnel site↔engine de punta a punta**: el engine publica su estado vivo y su inventario de
capacidades al site `specbox.build` en cada `/release`, y la extensión VSCode emite el
evento de activación que cierra el funnel anónimo. La única vía de liberar (`/release`) es también
la única vía de publicar → el changelog y el inventario del site nunca divergen del engine.

| US | Qué | Componentes |
|----|-----|-------------|
| **US-16** | **Publish-on-release del estado del engine.** Parser puro de `ENGINE_VERSION.yaml` + `CHANGELOG.md` con derivación determinista de `public_highlights`; publicador UPSERT idempotente a Supabase vía PostgREST con service-role (cliente HTTP inyectable, secreto redactado en logs); CLI re-ejecutable `python -m server.site_publish`. El site lee las tablas y refleja la versión recién liberada sin editar `.astro` a mano. | `server/site_publish/parser.py`, `server/site_publish/publisher.py`, `server/site_publish/__main__.py` (UC-1601..1603, PR #126) |
| **US-20** | **Publish del inventario de capacidades.** Parser puro `build_capability_inventory` extrae del propio código: agentes (`agents/*.md`), decoradores `@*.tool` **reales** (no comentados), skills (`.claude/skills/*/SKILL.md`) y la versión de la extensión VSCode — verificado vs el repo real: **13 agentes, 120 tools, 25 skills, ext v6.11.x**. UPSERT idempotente `merge-duplicates` a 4 tablas `public.engine_{agent,tool,skill,vscode_ext}`; migración SQL versionada `20260618000020` (RLS read-only anon) que cierra la deuda de US-15 (tablas creadas por MCP sin `.sql` en repo). | `server/site_publish/inventory.py`, `supabase/migrations/20260618000020_engine_capability_inventory.sql` (UC-2001..2003, PR #127) |
| **US-26** | **Activation event que cierra el funnel.** `registerActivationUriHandler` persiste el `anon_id` del deep-link de activación en `globalState`; `maybeEmitActivation` emite **UN** evento `activation` idempotente a la RPC `ingest_site_event` sobre `node:https` (cero deps), **sin PII** (solo `ext_version`/`platform`/`vscode_version`), respetando `isTelemetryEnabled`. Verificado e2e: `page_view→cta_click→install_intent→activation` = conversión completa correlacionada en `site_event`. | `vscode-extension/src/activation.ts`, `vscode-extension/src/constants.ts`, `vscode-extension/src/extension.ts` (UC-2601/2602) |

`/release` Paso 6.5 publica estado + inventario en una invocación (`python -m server.site_publish`)
como paso post-commit **no bloqueante**: si la publicación falla, se reporta como WARNING accionable
y el release NO se revierte. El publicador es UPSERT idempotente — re-ejecutarlo es seguro.

**Las tools salen del registro del servidor (UC-6201, US-62).** Leer decoradores `@*.tool` con regex
se perdía las tools registradas como `mcp_instance.tool(...)(fn)`: el site decía 126 cuando el MCP
exponía 192. `registered_tools(engine_root)` pregunta a `server.server.mcp` (lo mismo que devuelve
`tools/list`, con el nombre público y el fichero que la define) y se niega a describir otro checkout
que el importado. `tests/test_site_publish_inventory_parser.py` compara el inventario con lo que un
cliente MCP real recibe en `tools/list`; lo ejecuta el workflow `site-inventory.yml` en cada PR que
toca `server/`.

Tests: +56 verdes — 44 Python (`tests/test_site_publish_*.py`: parser, publisher, inventory
parser/publisher, main) + 6 VSCode `node:test` (`activation.test.mjs`); 94% cobertura del código
nuevo de `site_publish`, ruff limpio, service-role nunca logueada.

- PRD/Plan: `doc/prd/site-self-maintaining-showcase/` + `doc/prd/specbox-site-living-showcase/` en `EmbedBuild/specbox-manager`
- PRs: [#126](https://github.com/EmbedBuild/specbox-engine/pull/126), [#127](https://github.com/EmbedBuild/specbox-engine/pull/127), US-26 mergeada a main

## VSCode Self-Update — remote version check + guaranteed upgrade (v6.11.0)

US-14 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) cierra el funnel que
abrió el auto-clone de v6.9.0: la extensión clonaba y hacía `git pull --ff-only` al arrancar, pero
**solo comparaba la versión de la extensión instalada (`package.json`) contra el `ENGINE_VERSION.yaml`
en disco** ([updater.ts](vscode-extension/src/updater.ts)) — **nunca consultaba el remoto**. Un clon
managed en versión vieja (o una rama divergida del developer) se quedaba atrás en silencio: el
`--ff-only` fallaba sobre historia divergida y solo emitía un warning no bloqueante. Reproducido en
dogfooding el 2026-06-14: el clon en 6.9.4 mientras `origin/main` ya estaba en 6.10.2.

La extensión ahora, al arrancar (fase −1 de `runUpdateFlow`, antes del pull, fire-and-forget):

| UC | Qué | Dónde |
|----|-----|-------|
| UC-1401 | `git fetch origin --tags` + leer `git show origin/main:ENGINE_VERSION.yaml`; sin red / sin git (code 127) → se omite en silencio, activación normal | `vscode-extension/src/install.ts` (`fetchRemote`, `remoteEngineVersion`) |
| UC-1402 | Comparación **semver numérica** (`6.10.2 > 6.9.4`, no lexicográfica); si remota > local → modal accionable **X→Y** con `Update now` / `View changes` / `Later`; "Later" silencia esa versión durante la sesión | `install.ts` (`compareSemver`) + `updater.ts` (`checkRemoteAndOffer`) |
| UC-1403 | `pull --ff-only` en progress bar + **verificación post-upgrade**: relee `ENGINE_VERSION.yaml` y, si la versión no se movió, `showErrorMessage` accionable en vez de declarar éxito | `updater.ts` (`applyUpgrade`, `verifyAndFinish`) |
| UC-1404 | Divergencia (caso developer): `reset --hard origin/main` **con backup `git branch` previo + confirmación modal**; un clon de usuario (no managed) **nunca** se resetea, solo se avisa (`isManagedPath` gate, ICP-1) | `updater.ts` (`handleDivergence`) + `install.ts` (`isDivergedFromRemote`) |

Decisiones (confirmadas con el usuario): fuente de verdad = `origin/main:ENGINE_VERSION.yaml` (no
GitHub Releases API ni tags); detección de divergencia robusta vía
`git rev-list --left-right --count origin/main...HEAD` (ahead>0) además del stderr. `extension.ts`
sin cambios (sigue llamando `runUpdateFlow` fire-and-forget). Helpers puros (sin `vscode`, git
inyectable) siguiendo el split de `install.ts`/`prerequisites.ts`.

Tests: `vscode-extension/tests/updater-remote.test.mjs` — 16 casos `node:test` con `GitRunner` mock
(AC-01..AC-15). Suite 109/109 verde, ningún test toca git ni red.

- PR: [#125](https://github.com/EmbedBuild/specbox-engine/pull/125)
- PRD/Plan: `doc/prd/vscode-engine-autoupdate/` + `doc/plans/vscode-engine-autoupdate_plan.md` en `EmbedBuild/specbox-manager`

## El MCP remoto solo enseña a cada usuario lo suyo (US-38)

US-38 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) responde al
reporte de un tester externo (2026-09-24): con el MCP hospedado, una sesión FreeForm leía el
backlog del propio engine desde `/app/doc/tracking` con cualquier `board_id`, y
`list_onboarded_projects` devolvía el registro compartido entero (~100 proyectos con
descripciones de clientes, importes, NDA, URLs de repos y rutas locales) a cualquier sesión.

### UC-3801 — el backend FreeForm remoto no toca el disco del servidor (PR #138)

- `server/transport.py`: `is_remote_transport()` decide por el **transporte del servidor**
  (`MCP_TRANSPORT` = http / streamable-http / sse), no por `SPECBOX_ENGINE_MCP_URL` (un
  ajuste de cliente que nadie pone en el VPS — esa era la causa raíz).
- En remoto, `set_auth_token(backend_type='freeform', root_path=…)` se rechaza con
  `FREEFORM_REMOTE_DISK_MODE_REJECTED` + `how_to`; sin `root_path` abre una sesión
  `content_only`. Cada lectura/mutación recibe `items_content` del cliente y las mutaciones
  devuelven el contenido actualizado (`server/tools/_content_passing.py`); sin contenido, el
  chokepoint `get_session_backend` responde `FREEFORM_CONTENT_REQUIRED` — también para
  sesiones legacy con `root_path`.
- `.dockerignore` excluye `doc/tracking/`; el hook `freeform-path-guard` elimina `root_path`
  cuando el MCP es remoto; la extensión escribe `env.SPECBOX_ENGINE_MCP_URL` al elegir FreeForm.

### UC-3802 — el registro de proyectos solo muestra los proyectos del usuario identificado

- **Chokepoint** `server/coordination/scope.py`: `resolve_caller_scope(ctx, token=…)` convierte
  el token de la sesión native (o el parámetro `dev_token`) en un `CallerScope` = developer +
  proyectos native de los que es miembro (`project_members`). Sin token, token inválido o
  servidor sin `SPECBOX_NATIVE_DSN` → `UnauthenticatedError` → payload uniforme
  `UNAUTHENTICATED` (UC-648) y **ningún dato**.
- **Regla de visibilidad** `CallerScope.can_see`: una entrada es tuya si la registraste
  (`registered_by`) o si está ligada a un proyecto native del que eres miembro
  (`native_project_id`, `board_id` native, tenant del `mirror`, o el propio nombre canónico).
  Lo que no es tuyo se responde **igual que lo inexistente** (`PROJECT_NOT_VISIBLE`, con
  `available` = solo tus nombres): no hay enumeración.
- **Tools con la regla** (todas aceptan `dev_token` opcional para sesiones no native):
  `list_onboarded_projects` (devuelve `{developer_id, total, projects}` con campos
  whitelisted — `public_entry`), `get_onboarding_status`, `onboard_project`, `upgrade_project`,
  `upgrade_all_projects`, `get_version_matrix`, `archive_project`, `register_project`,
  `update_project_meta`, y sobre el registro de switch (`projects.json`): `switch_backend`,
  `switch_project_backend`, `enable_mirror` (la entrada auto-sembrada queda atribuida),
  `disable_mirror`. Un nombre ya registrado por otra identidad → `PROJECT_NAME_TAKEN`.
- **Sin descripción ni rutas** (AC-04): los escritores dejan de guardar `description` y rutas
  locales (`SENSITIVE_REGISTRY_FIELDS`); `description` se acepta por compatibilidad y se
  reporta como `ignored`. El auto-registro de la telemetría crea entradas sin dueño, invisibles
  hasta que se reclaman.
- **Purga del registro existente**: `python -m server.registry_hygiene --state-path /data/state
  [--dry-run] --backup-to <fichero.enc> [--claim <developer_id> --all|nombres]` — copia cifrada
  primero (PBKDF2-SHA256 → Fernet, passphrase en `SPECBOX_REGISTRY_BACKUP_PASSPHRASE`), luego
  limpia `registry.json`, `projects.json` y cada `meta.json`. Runbook:
  [doc/runbooks/registry-hygiene.md](doc/runbooks/registry-hygiene.md).
- Tests: `tests/test_registry_scope.py` (una prueba por tool + unidad del scope) y
  `tests/test_registry_hygiene.py`.

### UC-3803 — cada llamada a una tool queda registrada con quién, qué y cuándo

- **Middleware** `server/coordination/access_log.py::ToolAccessLogMiddleware` (registrado en
  `server.py` con `mcp.add_middleware`): por cada `tools/call`, en cualquier transporte, un
  `AccessRecord` con fecha/hora, tool, identidad (`developer_id` o el motivo de no tenerla:
  `anonymous` / `invalid_token` / `unresolved` → etiqueta "anónimo"), resultado
  (`ok` / `error` / `exception`) con `error_code` corto, duración, transporte, cliente MCP, IP,
  `session_id` y **solo los nombres** de los argumentos (`arg_keys`). Nunca el token, ni valores
  de argumentos, ni el payload devuelto, ni mensajes (AC-03). La identidad se resuelve una vez
  por token cada 30 s (caché en memoria por hash, que tampoco se persiste). La escritura es
  fire-and-forget: el log jamás rompe ni retrasa una tool.
- **Almacén append-only** (AC-01): migración `0022_tool_access_log.sql` (+ espejo Supabase
  `20260928000022`): tabla `tool_access_log` con trigger de sentencia que rechaza UPDATE /
  DELETE / TRUNCATE para cualquier rol (42501), privilegios revocados a PUBLIC / anon /
  authenticated y RLS activo sin políticas (PostgREST no la ve; el engine conecta como dueño).
  `PostgresStore` inserta y, si la BD no responde, encola en `STATE_PATH/tool_access_log.spool.jsonl`
  y reproduce en la siguiente escritura correcta. Sin `SPECBOX_NATIVE_DSN` → `JsonlStore`
  (`STATE_PATH/tool_access_log.jsonl`).
- **Consulta reservada al operador** (AC-02): tool `get_tool_access_log(developer_id, date_from,
  date_to, tool, limit, dev_token)` en `server/tools/access_log.py`. Operador = SuperAdmin del
  panel (`panel.profiles.role='superadmin'` enlazado por `developer_id`) o un id listado en
  `SPECBOX_OPERATOR_DEVELOPER_IDS` (override explícito de bootstrap/dev). Cualquier otra
  identidad → `FORBIDDEN` y `entries: []`; sin identidad → `UNAUTHENTICATED`. Filtro
  `developer_id="anónimo"` selecciona las llamadas sin identidad. Runbook:
  [doc/runbooks/tool-access-log.md](doc/runbooks/tool-access-log.md).
- Tests: `tests/test_tool_access_log.py` (middleware, almacenes, tool; los casos Postgres
  —trigger, store, spool/replay, rol de operador— corren cuando `SPECBOX_NATIVE_DSN` apunta a
  una BD de pruebas).

### UC-3804 — las operaciones de borrado de estado exigen identidad de operador

- `reset_all_state(confirm, dev_token)` y `reset_project(project, confirm, dev_token)`
  (`server/tools/state.py`) pasan por `_operator_gate`: identidad resuelta con
  `resolve_caller_scope` + `is_operator` (SuperAdmin del panel o `SPECBOX_OPERATOR_DEVELOPER_IDS`).
  Sin identidad → `UNAUTHENTICATED`; cualquier otra identidad → `FORBIDDEN`; en ambos casos no se
  borra nada. La palabra `confirm='yes'` sigue siendo obligatoria además de la identidad.
- AC-02: cada reinicio ejecutado escribe en el registro de accesos un evento `state_reset` con el
  `developer_id` del operador y el proyecto afectado en `project_id` (`*` en el reinicio global),
  además de la entrada de la llamada que ya anota el middleware (intentos denegados incluidos). El
  spool del registro de accesos no es "estado" y sobrevive al reinicio global.
- Tests: `tests/test_state_reset_operator.py`.

## Leer un proyecto exige ser su miembro (US-83 · UC-8301)

Hasta UC-8301 solo las escrituras native pasaban por el gate de membresía (US-34): una lectura
llevaba a SQL el `board_id` que mandaba el cliente, así que una sesión del proyecto A leía las
historias, criterios, comentarios y épicas de B con solo nombrarlo. Hallado y reproducido el
2026-10-05 al preparar las tools de épicas.

- `NativeBackend._require_read_access(board_id)` = `_require_membership_cached(board_id)`: mismo
  punto de cruce, misma caché de 30 s y misma fila `cross_tenant_denied` en la auditoría del
  proyecto pedido. Lo llaman `get_board_name`, `list_items`, `get_item`, `find_item_by_field`,
  `get_item_children`, `get_uc_acceptance`, `get_acceptance_criteria`, `list_epics`,
  `get_comments`, `get_attachments` y `get_labels` (y los atajos `find_us_items`/`find_uc_items`).
  `get_state_id` y `get_states` devuelven constantes y no consultan la base.
- Cambia UC-502 AC-06: un token revocado ya no lee el board (el transporte ya lo rechazaba
  antes de cualquier tool desde UC-3901).
- Tests: `tests/test_tenant_isolation.py` — `TestReaderInventory` prueba cada lectura desde
  otro proyecto y `test_catalog_covers_every_reader` falla si aparece una lectura nueva sin
  clasificar (como el inventario de mutadores).
## Abrir sesión no hace miembro a nadie (US-83 · UC-8302)

`provision_native_project` (lo que ejecutan `setup_board` y, con él, cada `set_auth_token`
native) solo da rol al crear un proyecto nuevo o al adoptar uno sin miembros. En un proyecto con
miembros exige que quien abre la sesión ya lo sea: si no, `ForbiddenError` (`FORBIDDEN` en
`set_auth_token`) sin escribir nada; si lo es, conserva su rol (un `member` no sube a
`project_admin`). Es la regla D2 (`native_provision_authority`), que hasta ahora solo aplicaba la
ruta de migración. Tests: `tests/test_native_provision.py::TestSessionNeverJoinsAProject`.

## El esquema del board solo es legible por quien tiene permiso (US-40)

US-40 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) versiona y completa
el hotfix aplicado en producción el 2026-09-28 (`hotfix_p0_*`): hasta entonces las seis vistas del
board se evaluaban con los privilegios de su dueño y conservaban el SELECT que Supabase regala a
`anon`/`authenticated`, así que la clave pública del proyecto podía leer el board de todos los
tenants por PostgREST.

### UC-4001 — las vistas y funciones del board respetan la seguridad por filas

- Migración `0023_board_views_security_invoker.sql` (+ espejo Supabase `20260928000023`):
  `security_invoker = on` en `project_kpis`, `v_uc_lifecycle`, `v_lifecycle_kpis`,
  `v_us_progress`, `v_weekly_throughput` y `v_active_time_estimate`; `REVOKE ALL` a PUBLIC /
  `anon` / `authenticated`; `service_role` conserva SELECT (la API cloud lee `project_kpis`).
- Funciones de indicadores y ciclo de vida (`fn_lifecycle_kpis`, `fn_backfill_lifecycle`,
  `fn_recompute_lifecycle_columns`) y los triggers `uc_lifecycle_columns`, `uc_record_transition`
  y `tool_access_log_append_only`: `search_path = public, pg_temp` fijado y EXECUTE retirado a
  PUBLIC / `anon` / `authenticated`; las tres `fn_*` quedan para `service_role` (y
  `fn_lifecycle_kpis` para `specbox_analytics_ro`, como en 0014). Un trigger se ejecuta aunque
  quien escribe no tenga EXECUTE sobre su función (Postgres lo comprueba solo al crearlo).
- `specbox_analytics_ro` conserva sus grants sobre las vistas, pero con `security_invoker` ya no
  hereda los privilegios del dueño: un usuario LOGIN colgado de ese rol no lee nada hasta que se le
  concedan las tablas base y la RLS lo permita. Hoy no existe ninguno.
- **Regla para migraciones futuras**: `CREATE OR REPLACE VIEW` borra las opciones de la vista y
  `CREATE OR REPLACE FUNCTION` borra sus `SET` (verificado en Postgres 16). Quien redefina una de
  estas vistas o funciones debe repetir `WITH (security_invoker = on)` / `SET search_path`.
- Tests: `tests/test_db_surface_views.py` (PG-gated): recrea los privilegios por defecto de
  Supabase sobre estos objetos, reaplica las migraciones y comprueba que toda vista de `public`
  corre con los derechos de quien consulta, que leerla o llamar a las funciones como `anon` o
  `authenticated` es un error de permisos, que los roles del servidor conservan su acceso y que
  los triggers de lifecycle siguen registrando transiciones sin EXECUTE.

### UC-4002 — los roles públicos pierden los permisos de escritura por defecto

- Migración `0024_public_roles_without_writes.sql` (+ espejo `20260928000024`). Los privilegios por
  defecto de Supabase dan a `anon`/`authenticated` todo (`arwdDxtm`) en cada tabla nueva de
  `public`; solo la RLS los frenaba, y en cinco tablas sensibles (`audit_log`, `github_identities`,
  `mcp_tokens`, `organizations`, `organization_members`) la denegación era **permisiva**.
- Las 15 tablas del board: ningún privilegio para PUBLIC/`anon`/`authenticated`, RLS activa y una
  política `specbox_deny_anon_<tabla>` **RESTRICTIVE** `FOR ALL TO anon, authenticated USING (false)
  WITH CHECK (false)` (el nombre que ya usa producción; se reemplaza la permisiva). Nada legítimo
  lee el board con la clave pública: el engine es el dueño, la API cloud usa `service_role` y el
  portal su puerta de lectura `SECURITY DEFINER`.
- El resto de tablas de `public` (inventario y eventos del site): conservan SELECT (lo gobierna su
  RLS) y pierden toda escritura; el site escribe por la RPC `ingest_site_event` (`SECURITY
  DEFINER`) y el publicador con `service_role`. Secuencias de `public`: nada para los roles públicos.
- Privilegios por defecto del rol que ejecuta las migraciones (`postgres` en Supabase): las tablas
  nuevas nacen con solo SELECT para `anon`/`authenticated` y las secuencias sin nada.
- Tests: `tests/test_db_surface_tables.py` (PG-gated): recrea los privilegios por defecto de
  Supabase, reaplica las migraciones y comprueba que ningún rol público puede escribir en ninguna
  tabla de `public`, que las del board no les conceden nada, que escribir como ellos es `42501`,
  que una tabla nueva nace de solo lectura, que toda tabla del board tiene RLS y denegación
  restrictiva, y que una política permisiva `USING (true)` más SELECT devuelto no abre ninguna
  tabla sensible.
- Efecto conocido en el panel: su suscripción Realtime a `mcp_tokens` (aviso de token revocado)
  ya no recibía filas antes de este cambio, porque la denegación cubría también a `authenticated`.
  Ese aviso necesita un canal broadcast (como el de proyecto), no `postgres_changes`.

### UC-4003 — la superficie expuesta de la base de datos se vigila en integración continua

- `server/db/surface_check.py` (`python -m server.db.surface_check [--dsn] [--schemas] [--allowlist]`):
  falla con `view_bypasses_rls`, `table_without_rls`, `function_executable_by_anon` (sin triggers
  ni funciones de extensiones) o `table_writable_by_public_role` (solo en `public`) salvo que
  `server/db/surface_allowlist.yaml` lo apruebe con un motivo; una entrada sin motivo hace fallar
  la comprobación. Salida 0/1/2; el DSN nunca se imprime.
- Lista aprobada (5): `public.ingest_site_event` y `public.site_funnel` (RPC del site), vistas
  `public.site_activity` y `public.site_stats` (solo recuentos) y `business.project_specs`
  (puerta de lectura del portal, filtra por `business.is_project_member`). Las entradas que no
  encuentran nada se informan como `unused` sin fallar.
- CI: `.github/workflows/db-surface-check.yml` monta Postgres 16 como Supabase (roles y
  privilegios por defecto), aplica las migraciones y ejecuta la comprobación y
  `tests/test_db_surface_*.py`. Con las migraciones hasta la 0022 falla con 36 hallazgos (las 6
  vistas, 13 tablas sin RLS, 3 funciones, 14 tablas escribibles); con la 0023 y la 0024, limpia.
- Producción se comprueba desde dentro del contenedor del MCP (el DSN no sale del servidor) con
  `--schemas public,panel,business`. Runbook: [doc/runbooks/db-surface.md](doc/runbooks/db-surface.md).
- Tests: `tests/test_db_surface_check.py` (lista, reparto hallazgo/aprobado/sin uso, CLI y los
  cuatro tipos de hallazgo contra Postgres).

## La historia sigue a sus UC (UC-4305)

UC-4305 (US-02 del board del orquestador, satélite engine) hace que el board diga en todo momento
qué está en progreso, en revisión y hecho sin mover la historia a mano. Origen (2026-09-28):
`start_uc` dejaba la historia en su columna inicial y `complete_uc` solo comentaba en ella, así que
dos historias seguían abiertas con todas sus UC hechas.

- `derive_us_state(uc_states)` (`server/tools/spec_driven.py`, puro): todas hechas → `done`; alguna
  en progreso → `in_progress`; todas en revisión o hechas → `review`; avance parcial con UC
  pendientes → `in_progress`; nada empezado → `None` (la historia nunca vuelve sola a las columnas
  pendientes). Las UC archivadas (estados fuera del workflow) no cuentan.
- `_sync_parent_us_state` se ejecuta en `start_uc` (native y el resto de backends), `move_uc` y
  `complete_uc` justo después de mover la UC: cambia **solo la historia** (a diferencia de
  `move_us`, que arrastra a las UC) y es best-effort — si mover la historia falla, la operación de
  la UC no falla y la respuesta lo dice. Cuando la historia cambia, la respuesta incluye
  `us_state_change = {us_id, from, to}`.
- `move_us` queda para correcciones manuales; `/implement` y `GLOBAL_RULES.md` lo reflejan.
- Tests: `tests/test_us_follows_ucs.py` — tabla del derivador, FreeForm por contenido (inicio,
  reapertura, revisión, cierre de la última UC, UC archivada, fallo al mover la historia) y un ciclo
  native PG-gated completo (inicio → revisión → cierre → reapertura).

## Nadie habla con el MCP remoto sin identificarse (US-39)

### UC-3901 — el servidor remoto exige un token válido en cada conexión

- `server/coordination/transport_auth.py::TransportAuthMiddleware` (ASGI puro, montado por
  `server.main()` en `streamable-http` y `sse`, no en stdio) lee `Authorization: Bearer` en **cada**
  petición HTTP salvo `/health`, antes de que el MCP la vea (inicialización incluida):
  token presente e inválido / caducado / revocado → `401 invalid_token` en cualquier modo; identidad
  caída → `503 auth_unavailable`; token válido → `TransportIdentity` en `scope["state"]`.
  Resolución token→developer cacheada 30 s por SHA-256 (el token nunca se registra).
- Conexión **sin** token según `SPECBOX_TRANSPORT_AUTH`: `off` (por defecto — desplegar no cambia
  nada), `grace` (hasta `SPECBOX_TRANSPORT_AUTH_GRACE_UNTIL`, con aviso en cada respuesta de tool
  vía `TransportNoticeMiddleware`; desde esa fecha, `401 token_required` con el mismo mensaje) y
  `enforce`. Configuración mala → falla cerrada (`enforce`). Mensajes ES/EN por `Accept-Language`.
  Activar la gracia es decisión del operador: runbook [doc/runbooks/transport-auth.md](doc/runbooks/transport-auth.md).
- Identidad de la conexión en las tools (AC-02), siempre detrás del token explícito y del de la
  sesión native: `transport_token(ctx)` / `transport_identity(ctx)` alimentan
  `identity_for_log` (el registro de accesos atribuye la llamada), `resolve_caller_scope` (UC-3802)
  y `set_auth_token(backend_type="native", token="")`. La especificación MCP exige el token en cada
  petición HTTP; lo que no se repite es pasarlo a las tools.
- AC-04: `FastMCP(version=_ENGINE_VERSION)` — el handshake anuncia `ENGINE_VERSION.yaml`, y
  `tests/test_engine_version_contract.py` falla si difiere de la última entrada de `CHANGELOG.md`.
- Tests: `tests/test_transport_auth.py` (política, parseo, middleware y un servidor FastMCP real por
  HTTP: `initialize` rechazado sin token o con token falso, identidad y atribución durante la sesión,
  aviso de gracia en la respuesta) y `tests/test_engine_version_contract.py`.

### UC-3903 — el servidor no corre con privilegios y limita el abuso

- **Sin root** (AC-01): la imagen crea el usuario `specbox` (uid 10001, home `/home/specbox`);
  `docker-entrypoint.sh` arranca como root solo para hacer `chown -R` del volumen de estado (lo
  escribieron contenedores anteriores como root), exporta `HOME` y cede privilegios con `setpriv`
  antes de ejecutar el servidor: PID 1 es `python -m server` como `specbox`. `/app` sigue siendo de
  root y de solo lectura. `docker exec` sigue entrando como root (operaciones de mantenimiento).
  Prueba del despliegue: `scripts/verify-nonroot.sh <contenedor>` (falla si PID 1 es root o no puede
  escribir su estado) y el workflow `.github/workflows/container-nonroot.yml`, que construye la
  imagen y la arranca sobre un volumen de estado propiedad de root, como el de producción.
- **Límites** (AC-02): `server/coordination/abuse_guard.py::AbuseGuardMiddleware`, justo detrás de
  la autenticación de transporte. Cuerpo > `SPECBOX_MAX_REQUEST_BYTES` (2 MB) → `413
  request_too_large` (por `Content-Length` o contando los bytes); más de
  `SPECBOX_RATE_LIMIT_PER_MINUTE` (60) `tools/call` en un minuto deslizante desde la misma identidad
  → `429 rate_limited` + `Retry-After`. Identidad = developer del transporte o, sin token, la IP del
  cliente que añade el proxy (el último elemento de `X-Forwarded-For`, que el cliente no puede
  falsificar). Cada identidad tiene su cupo; los mensajes del protocolo no gastan cupo; `/health`,
  GET y preflights no se limitan. Cupos en memoria (un proceso).
- Tests: `tests/test_abuse_guard.py`.

### UC-3904 (base de datos e identidad) — un token por dispositivo, con caducidad

- Migración `0025_device_tokens.sql` (+ espejo `20260929000025`), aditiva: `mcp_tokens` gana
  `expires_at`, `device_id` (SHA-256 que calcula el cliente con el id de máquina y el cliente; el
  servidor nunca ve el id de máquina), `device_name`, `client`, `issued_via`
  (`vscode|cli|manual|panel`) y `revoked_reason` (lista cerrada: `replaced`, `renewed`, `user`,
  `org_admin`, `superadmin`, `banned`, `idle`, `logout`); versiona también `name`, que solo existía
  en producción. Índice único parcial: como mucho un token activo por (developer, dispositivo),
  escriba quien escriba.
- `public.issue_device_token(...)`: emite un token de dispositivo en una transacción. Revoca el token
  activo del dispositivo (`replaced`) o el que se renueva (`renewed`, que debe seguir válido:
  `TOKEN_NOT_RENEWABLE`/28000 si no) e inserta el nuevo con caducidad (90 días por defecto, 1–365).
  Adopta un token antiguo sin dispositivo cuando se renueva con los datos del dispositivo.
  `SECURITY INVOKER` con `search_path` fijado; `EXECUTE` solo para `service_role` (la API del panel).
- `identity.resolve_developer`: un token caducado no autentica (UC-3902 AC-01), y la misma sentencia
  anota el uso real en `last_used_at` como mucho una vez por hora. Hasta ahora solo lo escribía
  `/api/whoami` del panel, así que las fechas anteriores no reflejan el uso del MCP.
- Orden de despliegue: la migración se aplica en producción **antes** de fusionar (el resolver
  consulta `expires_at`).
- Tests: `tests/test_device_tokens.py` (PG-gated). Plan completo de clientes (panel, CLI `specbox`,
  extensión): `doc/plans/US-39-conexion-dispositivos_plan.md` del orquestador.

### UC-3904 / UC-3901 AC-03 (clientes) — `specbox login` y la extensión envían el token solos

- **`packages/specbox-cli`** (npm `specbox`, Node ≥ 18.17, sin dependencias):
  - `specbox login`: código de un solo uso del panel (`/api/device/code` → la persona confirma en
    `/device` con GitHub → `/api/device/token`). El token va al almacén seguro (`lib/store.mjs`:
    Llavero por stdin con `security -i`, Secret Service, DPAPI; fichero 0600 como último recurso)
    y nunca se imprime.
  - `lib/install.mjs` copia el ayudante `lib/mcp-headers.mjs` (y los módulos que importa) a
    `~/.specbox/bin`. `lib/claude.mjs` configura Claude Code con
    `claude mcp add-json SpecBox-MCP {type:http,url,headersHelper} --scope user` (nunca edita
    `~/.claude.json` a mano) y añade el ayudante a las entradas locales que apuntan al mismo servidor.
  - El ayudante imprime `{"Authorization": "Bearer …"}` para la URL de
    `CLAUDE_CODE_MCP_SERVER_URL`; desde 14 días antes de caducar renueva (`/api/devices/renew`) con
    cerrojo en `~/.specbox/renew.lock` y relee tras 409; sin credencial imprime `{}`.
  - `device_id` = sha256(id de máquina : cliente), el mismo para la extensión y la CLI: un ordenador,
    un dispositivo, un token.
  - Órdenes internas para la extensión (`lib/internal.mjs`, JSON por stdin/stdout): `_device`,
    `_status`, `_connect`, `_configure`, `_adopt` (`/api/devices/adopt`, NO revoca el token anterior),
    `_renew`, `_disconnect`.
  - Tests: `packages/specbox-cli/test/*.test.mjs`; workflow `specbox-cli.yml` (macOS, Linux, Windows ×
    Node 18/22). Publicación en npm: automática con cada etiqueta `vX.Y.Z`
    (`publish-specbox-cli.yml`, trusted publishing sin token). `scripts/npm-publish-and-wait.sh`
    espera hasta 45 min a que npm sirva la versión (un `E409 previously staged` cuenta como
    aceptada) y, pasado el plazo, dice cómo relanzar (UC-5902). Runbook:
    `doc/runbooks/npm-trusted-publishing.md`.
- **Extensión de VSCode**: `copy-cli.mjs` empaqueta `packages/specbox-cli` en `specbox-cli/` al
  compilar (generado, en `.gitignore`); `src/specbox-cli.ts` lo ejecuta con el Node del sistema.
  - Iniciar sesión añade el dispositivo a `/vscode/issue-token` y llama a `_connect`.
  - Al arrancar, `device-connection.ts` adopta el token de versiones anteriores, renueva y restaura
    el ayudante; `mcp.ts` retira la entrada muerta `SpecBox-MCP` de `~/.claude/settings.local.json`
    (con copia `.bak-uc3904-*`). El lanzador `bin/mcp-launcher.mjs` desaparece.
  - La barra de estado enseña cuenta, dispositivo y caducidad; un 401 de `/api/whoami` (tras mirar
    si el ayudante ya renovó) avisa de que la conexión terminó y de las dos formas de reconectar.
  - Tests: `vscode-extension/tests/device-connection.test.mjs` y `mcp.test.mjs`.
- `transport_auth`: los rechazos enlazan `https://cloud.specbox.build/como-se-conecta` (ES) o
  `/how-to-connect` (EN) según `Accept-Language`.

## La extensión solo avanza y cada versión cuenta qué evita (v6.14.1)

- **UC-4307 (US-14) — la extensión nunca se degrada al actualizarse.**
  `vscode-extension/install-ext.mjs` solo instala el `.vsix` cuya versión es la esperada;
  `updater.ts` no reconstruye la extensión cuando el engine local está por detrás de la versión
  en ejecución, y el aviso muestra la versión que quedó instalada (error si no coincide con la
  esperada). Origen: un `.vsix` antiguo olvidado en la carpeta de la extensión la devolvía a una
  versión anterior en cada arranque. Tests: `vscode-extension/tests/extension-no-downgrade.test.mjs`.
- **UC-4302 (US-43) — comprobación de seguridad del release.**
  `.quality/scripts/changelog-security-check.mjs` lista los commits desde la etiqueta de la
  versión anterior, los clasifica como de seguridad por su mensaje (ES/EN) o por los ficheros
  sensibles que tocan, y exige que la entrada superior de `CHANGELOG.md` tenga `### Security`
  con contenido que cuente qué evita la versión, sin severidades, incidentes, reportes ni
  identificadores de vulnerabilidad. `/release` la ejecuta en el paso 7;
  `tests/test_changelog_security_check.py` la cubre, con un caso vivo sobre el propio repositorio.
- **UC-3902 (US-39)** — migración `0026_legacy_tokens_expire.sql`: los tokens sin `expires_at`
  caducan el 2026-12-28.
- **UC-4301 (US-43)** — `SECURITY.md` (ES/EN): cómo avisar de un problema de seguridad, canal
  privado y plazos de respuesta.
- **UC-4302 AC-02 (US-43) — la sección Security llega al site.** El parser del changelog une
  los ítems envueltos en varias líneas (antes solo viajaba la primera) y el publicador envía la
  sección `### Security` de cada versión en `engine_changelog_entry.security_notes` (migración
  `supabase/migrations/20260929000027`, que además versiona `engine_release`, `engine_feature` y
  `engine_changelog_entry`, creadas en su día sin `.sql`). El site la pinta como «Seguridad —
  qué evita esta versión».
- **UC-4303 AC-02 (US-43) — modelo de amenazas del MCP remoto.**
  [doc/security/threat-model.md](doc/security/threat-model.md): quién puede llamar a qué, con
  qué identidad y qué datos se comparten entre clientes. **Referencia obligatoria para toda tool
  nueva**: su sección 8 es la lista que hay que pasar antes de registrar una tool, y la tabla de
  la sección 4 se actualiza en la misma PR.

## Los tokens sin uso caducan solos y cinco dispositivos por persona (v6.14.2)

- **UC-3902 AC-03 (US-39) — revocación por inactividad.** Migración `0027_token_policy.sql`:
  `public.revoke_idle_mcp_tokens(p_idle_days = 60, p_floor = 2026-09-29)` revoca con
  `revoked_reason = 'idle'` los tokens activos y no caducados sin uso real en 60 días, con una
  fila de `audit_log` por token. El reloj nunca empieza antes del 2026-09-29 (cuando el engine
  empezó a anotar `last_used_at`): el primer token puede caer el 2026-11-28. En Supabase el job
  de pg_cron `revoke-idle-mcp-tokens` la ejecuta a las 03:17 UTC; sin pg_cron solo existe la
  función. Runbook: [doc/runbooks/transport-auth.md](doc/runbooks/transport-auth.md).
- **UC-3902 AC-04 (US-39) — cinco dispositivos.** `public.issue_device_token` rechaza el sexto
  dispositivo nuevo con `DEVICE_LIMIT` (SQLSTATE 53400) y deshace lo revocado; entrar de nuevo,
  renovar o reemplazar en uno conocido nunca tropieza; los tokens sin dispositivo y los caducados
  no ocupan plaza. El panel (specbox_cloud v0.6.4) responde `409 device_limit` con la lista;
  `specbox login` y la extensión («Gestionar dispositivos») explican el caso.
  Tests: `tests/test_token_policy.py` (PG-gated).
- **UC-3901 AC-03 — la conexión del ordenador va primero.** `runStartupTasks` ejecuta
  `ensureDeviceConnection` (adopción, renovación, limpieza de la entrada legacy) antes del health
  check, el updater y las puertas de arranque que pueden esperar un clic.

## Las herramientas de diseño leen el sistema, no un brand kit aparte (US-49 · UC-4901)

Cuando un proyecto tiene **tokens del sistema** (`design-system.tokens.json`, el formato que
`@specbox/tokens` deja en cada app con `npm run build:sync`), son la única fuente de diseño.
Guía pública: [doc/guides/design-system-tokens.md](doc/guides/design-system-tokens.md).

| Pieza | Archivo | Qué hace |
|---|---|---|
| Lector | `server/design_system/tokens.py` | `parse_system_tokens(content, source=)`: resuelve alias por tema y mapea papeles (principal, fondo, texto, estados; h1/h2/body…). Falta un papel obligatorio o el JSON es malo → `SystemTokensError` que dice qué falta |
| Comprobador | `server/design_system/conformance.py` | `find_values_outside(documento, tokens)`: colores, longitudes y duraciones, pesos, interlineados sin unidad, familias y enums de Stitch (`ROUND_*`, `*_FONT`) que ningún token define, con su ubicación. Lo reutilizará UC-4902 |
| Procedencia | `server/design_system/provenance.py` | `candidate_marker(provider)` (`design_role: candidate`, `production_source: system_tokens`, nota y `html_banner`) y `system_tokens_notice()` (aviso `SYSTEM_TOKENS_MISSING` con enlace a la guía); ES/EN por `Accept-Language` |
| Vista del sistema | `server/design_md/system_view.py` | DESIGN.md hecho solo de tokens (front-matter, cuerpo y vista Material 3 para Stitch); el Brand Kit y el arquetipo no se leen |

- **`generate_design_md_tool`** tiene modo **contenido** (`system_tokens_content`,
  `system_tokens_path`, `brand_kit_content`, `veg_content`, `app_prd_content`,
  `app_spec_content` → devuelve `design_md_content` + `suggested_relpath`, sin tocar el disco del
  servidor) y conserva el modo **disco** solo con servidor local (busca los tokens en
  `SYSTEM_TOKENS_CANDIDATE_PATHS`). En remoto, `project_root` sin contenido →
  `DESIGN_MD_CONTENT_REQUIRED`. Con tokens la respuesta trae `values_outside_system` (vacío =
  conforme) y `warnings` (p. ej. una fuente que Stitch no ofrece); sin tokens, `notice`; tokens
  rotos → `SYSTEM_TOKENS_INVALID`, nunca un DESIGN.md del Brand Kit en silencio.
- **Salida candidata**: `stitch_generate_screen[_v2]`, `stitch_edit_screen`,
  `stitch_generate_variants`, `stitch_fetch_screen_code`, `stitch_build_site_batched_v2` y el `ok`
  de `claude_design_sync_design_system` (que además nombra su `system_input`) llevan
  `candidate_marker`.
- **Skills**: `/plan` busca los tokens, genera el DESIGN.md en modo contenido, se lo da a Stitch
  (`stitch_upload_design_md` + `stitch_create_design_system_from_design_md`), guarda cada HTML
  con `html_banner` y escribe la sección **«Fuente de diseño»** en cada plan; sus prompts ya no
  inventan colores ni fuentes. `/visual-setup` 3.7 sigue el mismo contrato.
- El esquema de DESIGN.md admite `None` en pesos, interlineados, radios y espaciado para que un
  documento del sistema no arrastre defaults de arquetipo (`bold: 700`, `lineHeight 1.2`).
- Tests: `tests/test_design_system_tokens.py`, `tests/test_design_md_system_tokens.py`,
  `tests/test_design_candidate_output.py` (fixture: los tokens reales de Tinta en
  `tests/fixtures/design_system/`).

### El gate de diseño bloquea lo que se sale del sistema (UC-4902)

- **Escáner** con las mismas reglas en dos sitios: `server/design_system/code_gaps.py` (para el
  informe) y `.claude/hooks/lib/design-gaps.mjs` (para el hook). Detecta `direct_color` (hex,
  `rgb()`/`hsl()`/`oklch()`…, clases de paleta de Tailwind como `bg-blue-500` o `text-white`,
  `Color(0x…)`/`Colors.x` de Flutter), `font_outside` (familias de `font-family`, `fontFamily`,
  `font-[…]`, Google Fonts, `GoogleFonts.x`), `weight_above` (peso mayor que el máximo de los
  tokens: 600 en Tinta) y `gradient` (gradientes CSS, `bg-gradient-*`/`bg-linear-*`,
  `LinearGradient`). Solo ficheros de UI (css/scss/ts/tsx/js/jsx/astro/vue/svelte/html/dart),
  fuera de `node_modules`, `dist`, `public`, pruebas, `doc/` y las carpetas de tokens vendorizados.
  Vía de escape documentada: `design-gate:ignore` (línea) y `design-gate:disable-file`.
  `tests/fixtures/design_system/code_gap_cases.json` es el contrato que cumplen las dos.
- **Informe**: `get_visual_gap_report(code_files=…, system_tokens_content=…)` añade `design_gaps`
  (hallazgos con `fichero:línea` y `fix`, `by_kind`, `how_to_fix`) y `design_gate` = `pass` |
  `block`. Con tokens, los artefactos del Brand Kit cuentan como presentes (el sistema lo sustituye).
- **Hook** `design-system-gate.mjs` (PreToolUse sobre `move_uc` a review/done, `complete_uc` y
  `gh pr create`): escanea los ficheros de UI cambiados en la rama (commits desde la base +
  sin commit + nuevos) y, en autopilot (`specbox.autopilot.level` ≠ `low`), bloquea con exit 2
  listando qué se detectó y qué hacer; fuera de autopilot avisa. `specbox.design_gate.mode`
  (`block`|`warn`|`off`) lo fija. Sin tokens del sistema no hay nada que comparar: pasa.
- `/implement` Paso 7.8 llama al informe antes de la PR y no sigue con `design_gate: block`.
- Tests: `tests/test_design_code_gaps.py` (casos compartidos en Python y en Node, informe y hook
  contra un repositorio git temporal).

### La extensión habla el mismo idioma visual (UC-4903)

- **Tokens en la extensión**: `npm run sync -- specbox-engine` en `packages/tokens` del
  orquestador vendoriza los tokens en `vscode-extension/media/tokens/` y el símbolo en
  `vscode-extension/media/brand/` (no se editan aquí). El paquete `.vsix` solo lleva
  `foundation.css`, `semantic-light.css`, `semantic-dark.css` y los dos SVG del símbolo
  (`.vscodeignore`).
- **`vscode-extension/src/design.ts`**: `pageTheme()` (el tema de VSCode; oscuro por defecto,
  claro con Light/HighContrastLight), `tokensCss()`, `brandMark()`/`brandBlock()` (la caja
  marcada, decorativa), `lucideIcon(name, {label})` (Lucide al grosor del sistema, con nombre o
  `aria-hidden`) y `renderPage()` (IBM Plex + variables del sistema + clases de estilo de texto de
  `foundation.css`). Ningún color escrito.
- **Página de retorno OAuth** (`oauth.ts`: `renderSuccessPage`/`renderErrorPage`) y **diagnóstico**
  (`health.ts`: `renderHealthReport`, que se repinta al cambiar el tema de VSCode) usan esa
  plantilla. El diagnóstico dice el estado con palabra: `[x] Listo`, `[ ] Pendiente`,
  `[ ] Opcional`.
- **Barra de estado** (`statusbar.ts`): icono nativo de VSCode (la única opción de la plataforma) y
  siempre la palabra — `comprobando`, `sin instalar`, `N pendientes`; con todo bien,
  `[x] SpecBox vX · listo` (la forma de terminal del símbolo). Los avisos de acciones terminadas
  empiezan por `[x]` con `markDone(texto)` de `design.ts` (el lint de cadenas no acepta plantillas
  literales como primer argumento de `show*Message`).
- Tests: `vscode-extension/tests/design-system.test.mjs`.

## Borrar de verdad una UC que nunca tuvo trabajo (US-55 · UC-5501)

`delete_uc` sigue archivando por defecto. Con `purge=true` borra de verdad una UC creada por
error (el origen fue UC-4304, duplicada de UC-3904 y borrada a mano por SQL el 2026-09-30).

- **Quién se puede borrar**: `server/spec_backend.py::purge_refusal` — solo una UC en `backlog` o
  `archived`, sin ningún AC hecho, sin evidencia (adjunto en la UC o en un AC, o el sufijo
  `[META: …]` de `set_ac_metadata`) y sin reserva. Si no, `PurgeRefused` con su código
  (`PURGE_UC_STATE`, `PURGE_UC_HAS_DONE_AC`, `PURGE_UC_HAS_EVIDENCE`, `PURGE_UC_RESERVED`) y la
  tool archiva como sin `purge`, devolviendo `purge_refused = {code, message}`.
- **Native** (`NativeBackend.purge_use_case`): una transacción con la UC bloqueada (`FOR UPDATE`)
  borra `acceptance_criteria`, `uc_state_transitions`, `uc_reservations`, `branch_registry` y la
  fila de `use_cases`, y escribe en `audit_log` la operación `purge_uc` con el motivo, las filas
  borradas por tabla y la copia de la UC y de sus AC (`metadata.snapshot`). `audit_log` no se
  toca. Membresía contra el `board_id` que se escribe (US-34).
- **FreeForm** (`FreeformBackend.purge_use_case`): quita la UC y sus AC de `items.json` (o la UC
  de `archive.json` si estaba archivada; la tool la busca por su id lógico), sus comentarios y
  sus carpetas de adjuntos vacías, y añade la copia a `purged.jsonl`. En memoria (MCP remoto)
  devuelve el board sin la UC y la copia en la respuesta.
- **Trello y Plane** heredan el método por defecto: `PURGE_NOT_SUPPORTED` y la UC se archiva.
  El backend dual borra en el principal y replica en el espejo sin propagar sus fallos.
- Modelo de amenazas: T14 en `doc/security/threat-model.md`. Tests: `tests/test_uc_purge.py`
  (las native, contra Postgres).

## Cada criterio aceptado enseña su recibo (US-56 · UC-5601, v6.17.0)

`mark_ac` y `mark_ac_batch` guardan, además del estado, el **recibo** de cada AC: qué lo respalda,
dónde está, quién lo marcó y cuándo. El panel (árbol de especificaciones) y el portal (roadmap)
lo enseñan con la `EvidenceCard` del registro `@specbox/ui`.

- **Entrada** (`server/ac_evidence.py::normalize_evidence`): `evidence` es texto libre, que se
  guarda como `{type: "url", label: <texto completo>, link: null, detail: null}` y deja el
  comentario de la UC igual que siempre, o un objeto `{type: test|screenshot|diff|url|pr, label,
  link?, detail?}` (`link` solo http/https). Un recibo inválido devuelve `INVALID_EVIDENCE` y no
  marca nada; en `mark_ac_batch` se validan todos antes de tocar el board.
- **Native**: el mismo `UPDATE` que mueve `done` escribe `acceptance_criteria.meta.verdict =
  {passed, by, at}` y añade el recibo a `meta.evidence` con `by` (developer de la sesión) y `at`
  (`now()` del servidor). Quién y cuándo nunca los pone el llamante. Sin tabla nueva: no cambian
  la superficie de la BD, los permisos ni las RLS.
- **Salida**: `get_uc` devuelve por AC `evidence` (`{type, label, link, detail, by, at, passed}`) y
  `accepted` (`{by, at}`, solo si el AC está hecho y su último veredicto lo aceptó; si se hizo por
  otra vía, `null`: no se atribuye una aceptación que no consta).
- **Trello, Plane y FreeForm** no tienen almacén por AC: aceptan el parámetro y lo ignoran, y
  `get_uc` reconstruye recibos y veredictos de los comentarios de la UC con `by: null`
  (`evidence_from_comments`, `verdicts_from_comments`).
- **Migración 0028** (`server/db/migrations/0028_ac_evidence_backfill.sql`, gemela en
  `supabase/migrations/20261001000028_…`, sin DDL): convierte los comentarios «AC-XX:
  PASSED|FAILED — …» en recibos `source: "migrated"` con su fecha y `by: null`, y el último
  veredicto (incluidas las líneas de «Validacion AG-09b») en `verdict` solo si coincide con `done`.
  Idempotente y segura en cualquier orden con el despliegue. Mismas expresiones regulares que
  `server/ac_evidence.py`.
- `SpecBackend.mark_acceptance_criterion(..., evidence=None)`: los cinco backends y los dobles de
  pruebas aceptan el parámetro; el dual lo reenvía al espejo native.
- Tests: `tests/test_ac_evidence.py` (las native, contra Postgres).

## Verificado no es aceptado: la aceptación la da una persona (US-76 · UC-7601)

El veredicto de `mark_ac` lo firma el dueño del token de la sesión, así que en autopilot dice
«aceptado por» una persona aunque marque el agente. Desde US-76 ese veredicto es una
**verificación**, y la **aceptación** la da el owner o un admin del proyecto desde el panel, una
vez por UC.

- **Migración 0029** (`server/db/migrations/0029_uc_acceptances.sql`, gemela en
  `supabase/migrations/20261004100029_…`): tabla `uc_acceptances (project_id, uc_id,
  accepted_by_developer_id, accepted_at)`, una fila por UC aceptada y borrada en cascada con la
  UC. Sin privilegios para PUBLIC, `anon` ni `authenticated`, con RLS y denegación restrictiva
  (como 0024). `accepted_by_developer_id` no lleva clave foránea, como `audit_log`.
- **Se anula sola**: dos triggers borran la aceptación si la UC sale de `done` o si un criterio no
  interno queda sin hacer (se desmarca, se añade uno sin hacer o uno interno sin hacer pasa a
  visible). Sus funciones tienen `search_path` fijo y no se pueden ejecutar desde los roles públicos.
- **Solo escribe el API del panel**, con su rol de servicio y tras comprobar la sesión y el rol.
  Ninguna tool ni backend del engine escribe en la tabla, y una prueba lo comprueba.
- **Lectura**: `SpecBackend.get_uc_acceptance` (native; el resto devuelve `None`). `get_uc`
  devuelve `human_acceptance {by, by_id, at}` por UC y, por AC, `verified` (el veredicto de la
  sesión). `accepted` por AC queda como alias de `verified` para quien ya lo lee.
- Tests: `tests/test_uc_acceptances.py` (las de la tabla, contra Postgres).

## La épica agrupa las historias (US-78 · UC-7801, decisión D20)

Por encima de la historia hay una sola agrupación: la **épica**, con ficha propia, y cada historia
pertenece a una épica o a ninguna. Su estado y su avance no se guardan: se deducen de sus historias.

- **Native** (migración `0030_epics.sql`, gemela `supabase/migrations/20261005000030_epics.sql`):
  tabla `epics (project_id, id EP-NN, name, objective, link, position, target_date, version, …)`
  y columna `user_stories.epic_id` con clave ajena compuesta y `ON DELETE SET NULL (epic_id)`
  (Postgres 15+): borrar una épica deja sus historias sin épica. Cerrada a los roles públicos con
  RLS y denegación restrictiva (0024). Cada escritura comprueba la membresía del proyecto escrito
  (US-34) y deja su fila en `audit_log` (`create_epic`, `update_epic`, `delete_epic`,
  `set_us_epic`). Dos creaciones a la vez no se pisan el número: bloqueo consultivo por proyecto.
- **FreeForm**: la épica es un elemento más de `items.json` (`labels: ["EP"]`, `id: EP-NN`, campos
  en `meta`), así viaja con el contenido del board; la historia lleva `meta.epic_id`. Las tools
  solo cuentan elementos US/UC/AC, así que un `EP` no entra en los totales.
- **`SpecBackend`**: `list_epics`, `create_epic` (sin `epic_id` toma el siguiente EP-NN),
  `update_epic` (`target_date=""` la borra), `delete_epic` y `set_us_epic` no son abstractos.
  Trello y Plane listan cero épicas y rechazan escribir con `EpicError(EPICS_NOT_SUPPORTED)`; el
  backend dual escribe en el principal y replica en el espejo con el mismo EP-NN. Errores con
  código estable: `EPIC_EXISTS`, `EPIC_NOT_FOUND`, `EPIC_INVALID`.
- **`server/epics.py`** (puro): `summarize_epic` aplica la regla de `derive_us_state` (UC-4305) a
  los estados de las historias (sin nada empezado, `backlog`), cuenta criterios hechos sobre total
  de sus UC no archivadas (sin criterios, `pct = None`, nunca un 0 % inventado) y junta los
  satélites; `summarize_board` añade el grupo `sin_epica` para que los grupos sumen el board.
- **Tools (UC-7802, `server/tools/epics.py`)**: `add_epic`, `update_epic`, `delete_epic`,
  `set_us_epic` (por `us_id`; `epic_id=None` la saca), `list_epics` (épicas en orden con estado,
  avance y satélites, más `sin_epica`) y `get_epic` (lo mismo de una épica y cada una de sus
  historias con sus recuentos). Native y FreeForm con `items_content`; los rechazos vuelven como
  sobre `{code, error}` (`EPIC_*`, `US_NOT_FOUND`, `FORBIDDEN`, `UNAUTHENTICATED`), nunca con datos.
- **El identificador, una sola vez** (UC-7802 AC-03): `with_item_id(id, nombre)` de
  `server/spec_backend.py` quita las copias del id al principio del nombre y lo pone una vez;
  lo usan `import_spec`, `add_uc`, `update_uc`, `update_uc_batch` y `update_us`. Antes
  `import_spec` anteponía el id aunque el nombre ya lo trajera («US-76: US-76: …»).
- **Lecturas con épica y satélite (UC-7803)**: `list_us`/`get_us` devuelven `epic_id` y
  `satellites` (los de sus UC, sin repetir); `list_uc`/`get_uc` y cada UC de `get_us`, `satellite`
  y la épica de su historia; `get_board_status` añade `epic_id` a `us_summary` y `by_epic`
  (`summarize_board`: grupos que suman el board, con `sin_epica` al final).
- **Satélites declarados en el board (UC-7803)**: `declare_satellites(board_id, satellites)`
  guarda la lista en `projects.meta.satellites` (Native, con membresía y fila
  `declare_satellites` en `audit_log`). `mh.check_satellite` valida `set_uc_satellite`,
  `update_uc`, `update_uc_batch` y `add_uc` contra esa lista; sin ella, y solo con el MCP local,
  contra el `settings.local.json` del orquestador; sin nada declarado acepta cualquier clave. Un
  rechazo lista los satélites válidos. Antes solo se leía el disco del servidor, así que en remoto
  se aceptaba cualquier texto. FreeForm en remoto no guarda declaración.
- **Dependencias entre satélites (UC-7803)**: `get_cross_repo_dependencies` reconoce
  identificadores de cualquier longitud (`\bUC-\d+[a-zA-Z]?\b`); con `UC-\d{3}` leía UC-5101
  como «UC-510» y daba dependencias falsas.
- **La siembra declara épicas (UC-7805)**: `import_spec` acepta `epics: [{epic_id?, name,
  objective, link, target_date}]`, `epic` en cada historia (EP-NN o el nombre) y `satellite` en
  cada caso de uso (validado con `check_satellite`). Crea las épicas que no existen, reutiliza
  las que sí (por id o nombre), asigna cada historia y lo cuenta en `epics.created/reused/
  assigned`; en Trello/Plane siembra el resto y lo explica en `epics.skipped`. Quita del título
  de la historia las marcas `[satélite]` de los satélites conocidos y, al re-sembrar una historia
  que ya existe, **ya no le cambia el estado** (antes volvía a `user_stories`). La skill `/prd`
  (Paso 2.7) pregunta a qué épica va la feature salvo que el PRD lo declare
  (`decision_key` `feature_epic_assignment`, siempre `ask`).
- **El autopilot por épica o satélite (UC-7804)**: `find_next_uc(board_id, epic=?, satellite=?)`
  (combinables con `uc_scope`; sin ellos, el mismo resultado de siempre). Con `epic`, las UC van
  en el orden de sus historias (orden natural: US-9 antes que US-10), la historia con trabajo en
  curso primero, y sin pendientes devuelve `None`; una épica que no existe, `EPIC_NOT_FOUND`.
  `/implement EP-NN` (§0.1a-bis y §8.5.5 de la skill) encadena las UC de la épica y para al
  recibir `None`.
- **Los milestones se retiran (UC-7806 → UC-7807)**: desde la v6.21.0 las tools
  `set_uc_milestone`, `set_uc_milestone_batch`, `get_milestone_status`, `rebalance_milestones` y
  `milestone_acceptance_check` llevan `[DEPRECATED …]` en su descripción y `deprecation`
  (`since`, `removed_in: 6.23.0`, `use_instead`, `message`) en cada respuesta; `update_uc`,
  `update_uc_batch`, `update_us`, `add_uc` y `get_satellite_queue` solo avisan cuando reciben un
  milestone (`mh.milestone_deprecated(fn, when=mh.uses_milestone)`). Siguen funcionando hasta que
  UC-7807 los quite en la 6.23.0. Las plantillas FreeForm llevan `epic` (US) y `satellite` (UC).
- `/switch-backend` todavía no migra las épicas entre backends.
- Tests: `tests/test_epics.py`, `tests/test_epics_tools.py` y
  `tests/test_board_reads_epic_satellite.py`, `tests/test_import_spec_epics.py` y
  `tests/test_find_next_uc_epic.py` y `tests/test_milestone_deprecation.py` (las native, contra
  Postgres) y `epics` en las tablas del board de `tests/test_db_surface_tables.py`.

## Proyectos sin organización (US-60 · UC-6001, v6.17.1)

«Organización» es un concepto del panel, no del engine (migración 0020): los proyectos del
engine son multi-tenant solo por `project_id`. `provision_native_project` (y `setup_board`)
coloca un proyecto en una organización cuando hay alguna que asignar — la que se pasa en
`organization_id`, la que ya tiene el proyecto o una del developer — y, si no hay ninguna
(un engine sin panel, cuyos developers no pertenecen a ninguna), lo crea con
`organization_id` NULL y deja el aviso `native_project_without_organization` en el log.

- Todas las tools del engine funcionan igual sobre un proyecto sin organización.
- En el panel, un proyecto sin organización no lo ve ningún tenant (los filtros de UC-1304
  van por organización) hasta que el SuperAdmin se la asigna.
- Re-aprovisionar un proyecto nunca le cambia ni le quita la organización: el `ON CONFLICT`
  no toca `organization_id`.
- Tests: `tests/test_native_provision.py` y `tests/test_native_orphan_provision.py`.

## El servidor alojado vive en mcp.specbox.build (US-51 · UC-5101/5102)

El MCP alojado responde en **`https://mcp.specbox.build/mcp`** y en su nombre anterior,
`mcp-specbox-engine.jpsdeveloper.com`: los dos son el mismo servicio de EasyPanel y el antiguo
no tiene fecha de retirada. `scripts/check-mcp-hosts.mjs` compara los dos (versión, token
inválido, sin token y, con `--with-device-token`, sesión con token); corre cada lunes sin
token (`mcp-hosts.yml`) y con token en el Paso 6.7 de `/release`.

Los clientes se mudan solos:

- La CLI (`packages/specbox-cli/lib/config.mjs`) y la extensión (`vscode-extension/src/mcp.ts`)
  usan el nombre nuevo por defecto; el anterior está en `LEGACY_MCP_URLS` /
  `LEGACY_REMOTE_MCP_URLS`.
- **Una sola credencial para los dos nombres:** `accountFor()` traduce el nombre anterior al
  nuevo, y el almacén (`withLegacyAccounts`) copia a la clave nueva la credencial que una
  versión anterior guardó con la antigua la primera vez que la lee. `specbox logout` borra las
  dos.
- **Entradas de Claude Code:** `claudeUsesHelper()` devuelve `false` si `SpecBox-MCP` apunta al
  nombre anterior, así que la extensión actualizada llama a `_configure`. Este reescribe al
  nombre nuevo la entrada de usuario y las locales de cada proyecto, y antes guarda las entradas
  tal como estaban en `~/.specbox/backups/claude-mcp-<fecha>.json` (sin el valor de ningún
  `Authorization`).
- Una instalación sin actualizar sigue funcionando con el nombre anterior.
- Tests: `packages/specbox-cli/test/mudanza.test.mjs` y `vscode-extension/tests/mcp.test.mjs`.

## Engine Version

Current: v6.21.0 "Gavilla"
Brand: SpecBox Engine (SpecBox Engine by JPS)
Config: ENGINE_VERSION.yaml

## Native Default OAuth (v6.3.0)

US-VSCODE-GITHUB-OAUTH añade onboarding first-class para el Native backend
desde la extensión VSCode (publicada en v6.2.0) **y promueve `native` a
backend por defecto en `onboard_project()`** (antes era `freeform` desde
v5.29.0). FreeForm sigue first-class para uso solo / air-gapped y los
proyectos legacy no se migran — `detect_backend()` runtime conserva
`freeform` como fallback final.

El flow es:

1. Extensión arranca un servidor HTTP one-shot en `127.0.0.1` (puerto
   random). Abre el browser contra `https://cloud.specbox.build/vscode/issue-token`
   con `?return_to=<loopback>&state=<csrf>`.
2. La nube (US-09 de `EmbedBuild/specbox_cloud`) hace el OAuth de GitHub,
   provisiona un `mcp_token` en Supabase, y redirige al loopback con
   `?mcp_token=<64-hex>&state=<csrf>`.
3. La extensión valida (origin allow-list + state + regex), guarda el
   token en VSCode SecretStorage (Keychain/Credential Manager/libsecret),
   actualiza el config del MCP server local, y dispara `claude.mcpRestart`.

**FreeForm sigue first-class** — el onboarding muestra dos opciones de
igual peso ("Sign in with GitHub" / "Continue in local mode (FreeForm)"). La
decisión persiste en `workspaceState`. Cerrar la X no es una decisión.

**Server-side UNAUTHENTICATED graceful** (UC-648): las 4 tools nativas
(`whoami`, `reserve_uc`, `release_uc`, `register_native_branch`) retornan
payload uniforme `{status, code, message, docs_url, locale}` con
`Accept-Language` respetado (EN default, ES fallback). Revoke visible en
≤30s (cache TTL del server) + 60s (sidebar polling) = ≤90s total.

Componentes nuevos:

| Archivo | Rol |
|---|---|
| `vscode-extension/src/oauth.ts` | Loopback HTTP server + cloud URL builder |
| `vscode-extension/src/secret-storage.ts` | SecretStorage wrapper |
| `vscode-extension/src/auth.ts` | signIn / signOut / onboarding gate |
| `vscode-extension/bin/mcp-launcher.mjs` | Spawn shim que inyecta el token desde env del proceso padre |
| `server/coordination/i18n_messages.py` | Dict EN/ES + `Accept-Language` parser |
| `tests/test_native_unauthenticated.py` | 26 casos verde para AC-01..AC-05 de UC-648 |
| `vscode-extension/tests/oauth.test.mjs` | 10 unit tests del loopback (zero-deps `node:test`) |
| `vscode-extension/tests/oauth-integration.test.mjs` | 3 integration tests del round-trip mock-cloud ↔ loopback |
| `.github/workflows/oauth-e2e.yml` | CI gate que corre compile + lint i18n + suite OAuth en PRs |
| `doc/decisions/native_default_oauth.md` | ADR del cambio + rollback plan |
| `doc/runbooks/freeform-only-mode.md` | Runbook para usuarios que prefieren FreeForm |
| `doc/runbooks/github-oauth-troubleshooting.md` | Errores comunes y recovery |

Cross-repo: la mitad del cloud es `EmbedBuild/specbox_cloud` US-09 (mergeada
en PR #47, 2026-05-27). El contrato (URL + shape del callback +
`clear_token` con prefijo `spbx_`) está documentado en
`doc/decisions/native_default_oauth.md` sección "Contract surface".

**Default canónico del onboarding**:

| Período | `onboard_project()` sin `backend_type` | Justificación |
|---|---|---|
| pre-v5.29.0 | "trello" si `trello_board_name`, error si no | Solo Trello era first-class |
| v5.29.0..v6.2.x | "trello" si `trello_board_name`, else **"freeform"** | FreeForm pasa a first-class — discovery prioritizado |
| **v6.3.0+** | "trello" si `trello_board_name`, else **"native"** | Native OAuth disponible — multi-developer y compartido por defecto |

El cambio se materializa en `server/tools/onboarding.py::DEFAULT_BACKEND_TYPE`
(constante module-level) + `resolve_default_backend_type()` (helper puro,
testeable). El `detect_backend()` runtime conserva su fallback en
`freeform` para no romper proyectos legacy.

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

### Defensas v5.29 de FreeForm (decisión permanente — revisada en v6.2)

El hook `freeform-path-guard.mjs` y `FreeformPathError` permanecen como defensa en profundidad **permanente**, no como deuda transitoria. Una nota anterior decía "eliminación formal planeada para v6.1"; tras revisión en v6.2 esa intención queda revocada porque:

1. El hook tiene **uso real verificable** en producción (entries en `.quality/logs/freeform-path-rewrites.jsonl`).
2. `FreeformPathError` tiene tests vivos en `tests/test_freeform_path_guard.py` — cubre el server-side guard de path absoluto.
3. `onboard_project` todavía expone `freeform_root_absolute: str = ""` como argumento opcional; sin las defensas, un cliente que omite el argumento y pasa por el default implícito `doc/tracking` rompería en MCP remoto exactamente como el bug original de v5.29.
4. `/app-init` SKILL.md explícitamente referencia el hook como red de seguridad para clientes que no pasan por la skill (claude.ai mobile, integraciones externas).

La arquitectura de 3 capas (skill explícita / hook auto-rewrite / server-side validation) es deliberada y se mantiene.

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
