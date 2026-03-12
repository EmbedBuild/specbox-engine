# Changelog

All notable changes to SDD-JPS Engine are documented here.

## [4.2.0] - 2026-03-12

### Added
- **Stitch Design Gate** (Paso 0.5d in `/implement`) — BLOQUEANTE: impide generar codigo de presentacion sin diseños Stitch previos. Si el UC tiene pantallas y no existen HTMLs en `doc/design/{feature}/`, el pipeline se detiene con mensaje claro.
- **Stitch Config Gate** (Paso 6.0a in `/plan`) — Si el plan tiene pantallas y no hay config Stitch, pregunta al usuario (nunca salta silenciosamente). Opciones: configurar Stitch, marcar PENDING, o generar manualmente.
- **`stitch_designs` field** — Campo obligatorio en el output de `/plan` con valores `GENERATED`, `PENDING`, `MANUAL`, o `N/A`. `/implement` lee este campo y bloquea si es `PENDING`.
- **Design traceability comment** — Paso 4.3 en `/implement` obliga a incluir `// Generated from: doc/design/{feature}/{screen}.html` en cada pagina generada por design-to-code.
- **AG-08 Check 6: Design Traceability Audit** — Nuevo check en Quality Auditor que verifica que toda pagina bajo `presentation/pages/` tiene comentario de trazabilidad. Pagina sin trazabilidad = CRITICAL → NO-GO.
- **`/check-designs` skill** — Escaneo retroactivo de compliance Stitch. Soporta Trello, Plane y planes locales. Genera tabla con status COMPLIANT/MISSING/PARTIAL/PENDING/SKIP por UC.
- **`design-gate.sh` hook** — PostToolUse hook (NON-BLOCKING) que emite WARNING cuando se crean/modifican archivos en `presentation/pages/` sin diseño Stitch correspondiente o sin comentario de trazabilidad.
- **Design Compliance Ratchet** — Enforcement progresivo en 3 niveles (L0=info, L1=ratchet, L2=zero-tolerance) para proyectos con codigo UI legacy. El nivel sube automaticamente al cruzar umbrales de compliance (30% → L1, 80% → L2). Nunca baja.
- **`design-baseline.sh`** — Script que mide design compliance (features con diseño, paginas con trazabilidad, compliance rate) y aplica ratchet enforcement.
- **`/quality-gate` Paso 5.6: Design Compliance Gate** — Verifica ratchet de diseño segun nivel del proyecto. Integrado en el flujo existente.
- **`/implement` Paso 0.5d.1: Retrofit Protocol** — En L0 el design gate emite WARNING (no bloquea), en L1 solo bloquea planes nuevos, en L2 bloquea siempre. Permite migracion gradual.
- **`/check-designs` retrofit roadmap** — Genera roadmap de retrofit priorizado por frecuencia de modificacion + actualizacion de baseline.
- **`quality-baseline.json.template` seccion `designCompliance`** — Metricas de compliance, nivel de enforcement, lista de features grandfathered.
- **`GLOBAL_RULES.md` politica Design Compliance** — Tabla L0/L1/L2, reglas de trazabilidad, umbrales de escalado automatico.

### Changed
- **`/implement` pre-flight checks** — Nuevo Paso 0.5d se ejecuta despues de 0.5c y antes de crear la rama feature/.
- **`/implement` Paso 4.3 → 4.4** — El commit parcial de diseños se renumero a 4.4 para dar espacio al nuevo paso de traceability.
- **AG-08 responsibilities** — 6 verificaciones (antes 5) + 2 outputs (report + evidence). Design Traceability añadido como Check 6.
- **AG-08 audit.json** — Nuevo campo `designTraceability` con `pagesWithoutTraceability` y `brokenReferences`.
- **`settings.json`** — 2 nuevos hooks PostToolUse para Write y Edit con `input_contains: "presentation/pages/"`.
- **CLAUDE.md** — Skills table incluye `/check-designs`, hooks table incluye `design-gate`, directory tree actualizado.

## [4.1.0] - 2026-03-11

### Added
- **Multi-Backend Abstraction** — Plane added as alternative project manager alongside Trello. Both backends work identically through backend-agnostic `SpecBackend` ABC.
- **SpecBackend ABC** (`server/spec_backend.py`) — Abstract interface defining 23 methods for unified project management operations. Includes DTOs: `ItemDTO`, `ChecklistItemDTO`, `CommentDTO`, `AttachmentDTO`, `ModuleDTO`, `BackendUser`, `BoardConfig`.
- **TrelloBackend** (`server/backends/trello_backend.py`) — Wraps existing `TrelloClient` + `board_helpers` into `SpecBackend` interface. Zero breaking changes.
- **PlaneBackend** (`server/backends/plane_backend.py`) — Full `SpecBackend` implementation for Plane (Cloud and CE). Metadata encoding via labels and name prefixes. AC stored as sub-work-items.
- **PlaneClient** (`server/backends/plane_client.py`) — Direct httpx async client for Plane REST API v1 with retry logic and pagination.
- **Migration tools** (`server/tools/migration.py`) — 5 new MCP tools: `migrate_preview`, `migrate_project`, `migrate_status`, `set_migration_target`, `switch_backend`. Idempotent via `external_source` + `external_id`.
- **Per-session backend selection** — `get_session_backend(ctx)` returns appropriate backend based on session credentials. `store_plane_credentials()` for Plane auth.
- **78+ MCP tools** — 21 spec-driven tools (backend-agnostic) + 5 migration tools + 52 engine tools.
- **Test suite expansion** — `test_spec_backend.py`, `test_plane_backend.py`, `test_migration.py`, `test_auth_gateway_v2.py` (82 new tests).

### Changed
- **spec_driven.py rewritten** — All 21 tools now use `get_session_backend(ctx)` instead of direct `TrelloClient`. Tool descriptions updated to say "board/project" instead of "Trello board".
- **auth_gateway.py** — `store_session_credentials()` now stores both legacy and unified keys. `clear_session_credentials()` clears both.
- **models.py** — `UseCaseDetail` gains `backend_item_id`, `backend_item_url`, `backend_type` fields.
- **server.py** — Registers migration tools after spec-driven tools.
- **`set_auth_token`** — Now accepts `backend_type`, `base_url`, `workspace_slug` params for Plane.
- **CLAUDE.md** — Updated to v4.1.0, 78+ tools, new "Gestores de proyecto" section.
- **ENGINE_VERSION.yaml** — v4.1.0 "Multi-Backend Abstraction", new `project_managers` section.

### Fixed
- **PlaneBackend priority mapping** — `update_item()` now maps priority strings consistently with `create_item()`.
- **PlaneClient auth header** — Uses `X-Api-Key` header (Plane REST API standard).
- **PlaneClient parent expand** — Default expand includes `parent` to prevent AttributeError on hierarchy traversal.
- **PlaneBackend AC label** — `create_acceptance_criteria()` auto-creates "AC" label if missing.
- **TrelloBackend UC parent_id** — Now resolves `parent_id` from `us_id` metadata during `list_items()`.
- **PlaneBackend state cache** — Repopulates caches after `setup_board()` instead of just invalidating.
- **PlaneBackend HTML entity round-trip** — `_extract_meta_from_html()` now unescapes HTML entities.
- **spec_backend parse_item_id** — Unknown prefix returns `("", name)` instead of silently falling back to US pattern.
- **Unused imports removed** — `WorkflowState`, `ChecklistItemDTO` from spec_driven.py; `TargetType` from models.py.
- **Stale test files removed** — 8 test files with broken imports from pre-consolidation module layout.

## [4.0.3] - 2026-03-10

### Security
- **CORS configurable** — `DASHBOARD_CORS_ORIGIN` env var controla que origenes pueden hacer requests al dashboard. Sin configurar = no se envian headers CORS (same-origin only). Antes era `Access-Control-Allow-Origin: *` hardcodeado.
- **.gitignore hardened** — Añadidos patrones para `.env*`, `*.key`, `*.pem`, `*.p12`, `*.pfx`, `*.jks`, `id_rsa*`, `secrets.*`, `credentials.json`, `firebase-adminsdk*.json`, `google-services.json`, `GoogleService-Info.plist`.
- **Dashboard dist removido del tracking** — `server/dashboard/dist/` ya no se commitea (el Dockerfile lo construye en Stage 1).
- **Credenciales personales eliminadas** — Email, UUID de Plane y rutas locales absolutas parametrizadas o eliminadas.
- **URLs internas reemplazadas** — Dominios de infraestructura reemplazados por placeholders `example.com`.

### Added
- **SECURITY.md** — Politica de responsible disclosure, versiones soportadas, best practices de seguridad.
- **.env.example** — Template de variables de entorno con documentacion inline.
- **`DASHBOARD_CORS_ORIGIN`** — Nueva variable de entorno para configurar CORS del dashboard.

### Changed
- **README.md** — Seccion "Sala de Maquinas" clarifica que cada usuario despliega su propia instancia (no hay servidor central compartido). Incluye tabla de configuracion de seguridad en produccion.
- **docker-compose.yml** — Incluye `DASHBOARD_CORS_ORIGIN` en variables de entorno.
- **Plane assignee** — Parametrizado como `{PLANE_ASSIGNEE_ID}` en `/prd` skill y command (antes era UUID hardcodeado).

## [4.0.2] - 2026-03-09

### Changed
- **Board Taxonomy refactor** — Trello workflow lists renamed for semantic clarity:
  - `Backlog` → `User Stories` (static US registry, cards don't move)
  - `Ready` → `Backlog` (UC queue, cards flow through pipeline)
- **WorkflowState enum** — Internal states renamed: `backlog` → `user_stories`, `ready` → `backlog`
- **spec_driven.py** — All hardcoded list name lookups (`lst["name"].lower()`) updated to match new names
- **find_next_uc** — Now searches "Backlog" list (formerly "Ready") for next UC to implement
- **move_us** — Movement rules updated: `user_stories` replaces `backlog`, `backlog` replaces `ready`
- **Tests** — conftest fixtures, test_models assertions, test_board_helpers, test_coverage_edges, test_tools_board all aligned
- **implement SKILL.md** — UC lifecycle diagram and merge flow reference new list names

## [4.0.1] - 2026-03-09

### Added
- **HARD BLOCK: Anti-main implementation guard** (Paso 0.5b) — Implementar directamente en main/master es ahora un ERROR FATAL que detiene el pipeline inmediatamente. Previene la violacion mas critica del protocolo de ramas.
- **HARD BLOCK: Pre-merge validation** (Paso 8.5.0) — 4 validaciones bloqueantes antes de cualquier merge: rama feature/ existente, PR abierta, estado UC correcto en Trello, y flag VEG images.
- **HARD BLOCK: Trello state validation** (Paso 0.5c) — Verifica que `start_uc` fue llamado exitosamente antes de permitir implementacion. Incluye recovery automatico si el estado es inconsistente.
- **VEG images pending flag** — Cuando las imagenes VEG no se generan (MCP no disponible o skip), se activa `veg_images_pending = true` que:
  - Limita AG-08 verdict a CONDITIONAL GO maximo
  - Bloquea auto-merge
  - Anade banner visible en el PR body
- **CSS placeholder prohibition** (Paso 3.5.5) — Regla explicita que prohibe sustituir imagenes VEG por gradientes CSS, iconos SVG inline, o iniciales de texto. Solo se permiten imagenes reales o placeholders `<img>` apuntando a paths pendientes.
- **project-config.json support** (Paso 0.1a) — `.claude/project-config.json` es ahora la ubicacion preferida para `trello.boardId` y `stitch` config, ya que Claude Code rechaza campos custom en `settings.local.json`.

### Changed
- **Auto-merge conditions** (Paso 8.5.1) — Nueva condicion: `veg_images_pending == false` requerido para auto-merge.
- **README.md** — Reescrito completamente con documentacion exhaustiva de v4.0.1.

### Fixed
- **Protocol compliance gap** — Las validaciones de rama, PR, y Trello state que antes eran "soft requirements" (documentadas pero no validadas) ahora son HARD BLOCKS que detienen el pipeline.

## [4.0.0] - 2026-03-08

### Added
- **Monorepo unification** — Fusion de jps_dev_engine + dev_engine_mcp + dev-engine-trello-mcp en un solo repositorio
- **MCP unificado** — 73+ tools en un solo endpoint (engine + spec-driven + telemetria)
- **Gherkin en espanol** — Mecanismo estandar de validacion de AC con BDD
- **AG-09a reescrito** — Genera .feature + step definitions por stack
- **AG-09b adaptado** — Valida desde .feature + JSON Cucumber report
- **PDF de evidencia** — Escenarios + screenshots adjuntos a card UC en Trello
- **Template .feature estandar** — doc/templates/gherkin-feature-template.md
- **Frameworks BDD por stack** — bdd_widget_test, playwright-bdd, pytest-bdd, jest-cucumber
- **setup_board** — Integrado en onboard_project como paso opcional
- **archive_project** — Ocultar proyectos obsoletos del dashboard
- **Sala de Maquinas embebida** — React 19 + Vite dashboard en el monorepo
- **Dockerfile multi-stage** — Node dashboard + Python server unificado
- **Backward compatibility** — Symlink ~/jps_dev_engine → ~/sdd-jps-engine

## [3.9.1] - 2026-03-07

### Fixed
- Bump all remaining v3.8.x references to v3.9.0 across 27 files
- Templates updated to v3.9.0 for upgrade_project compatibility
- Knowledge guide updated to v3.9.0 with VEG section

## [3.9.0] - 2026-03-07

### Added
- **VEG (Visual Experience Generation)** — 3-mode visual customization system
- VEG Pilar 1 (Images) — MCP-agnostic image generation with stock-first strategy
- VEG Pilar 2 (Motion) — flutter_animate (Flutter) + motion/Framer Motion (React)
- VEG Pilar 3 (Design) — density/whitespace/hierarchy/typography directives for Stitch
- VEG Mode 1 (Uniform), Mode 2 (Per Profile), Mode 3 (Per ICP+JTBD)
- /prd Audiencia section with targets, ICPs, JTBD definitions
- /plan VEG generation with archetype-based derivation
- /implement Pasos 0.3, 3.5, 4, 6.1b for VEG pipeline
- 6 archetype derivation rules (Corporate, Startup, Creative, Consumer, Gen-Z, Government)
- Image providers: Canva MCP (primary, €0), Freepik, lansespirit (fallback)
- Safety gates: MCP health check, cost warning, PENDING_IMAGES.md fallback

## [3.8.1] - 2026-03-07

### Changed
- **Rebrand** to SDD-JPS Engine (Spec-Driven Development Engine by JPS)
- 50 files updated with new brand — display text only, filesystem paths preserved

## [3.8.0] - 2026-03-07

### Added
- **Spec-Driven pipeline** — US-XX → UC-XXX → AC-XX hierarchy as source of truth
- /prd dual mode: spec-driven (Trello) and freeform
- /plan Trello input: reads US/UC/AC from domain MCP, attaches plan as PDF
- /implement UC execution cycle: find_next_uc → start_uc → implement → complete_uc → merge
- AG-09b per-UC validation with Trello reporting
- Evidence pipeline: PRD→US, Plan→US, AG-09→UC, Delivery→US as PDF
- dev-engine-trello domain MCP with 15 business tools

## [3.7.0] - 2026-03-07

### Added
- **Engram persistent memory** (FTS5) for context compaction survival
- Strict Orchestrator Isolation — main thread under 15% token budget
- GGA (Gentleman Guardian Angel) cached lint validation
- implement.md and SKILL.md rewritten with Phase Task Template

## [3.6.1] - 2026-03-03

### Fixed
- **mcp-report.sh**: Add `Accept: application/json, text/event-stream` header to Steps 2 (initialized notification) and 3 (tool call). FastMCP requires this header on all requests — was causing silent HTTP 406 rejection, preventing all hook telemetry from reaching the MCP server.
- **Project name normalization**: All hooks now normalize project names with `tr '_' '-'` to match MCP registry convention (e.g., `tempo_zenon` → `tempo-zenon`). Affected hooks: `on-session-end.sh`, `implement-checkpoint.sh`, `implement-healing.sh`, `post-implement-validate.sh`.

## [3.3.0] - 2026-02-25

### Added
- **Remote Telemetry**: Hooks report to remote MCP server via `mcp-report.sh` (fire-and-forget)
- `mcp-report.sh` — reusable MCP client helper for streamable-http protocol (initialize → call tool)
- `on-session-end.sh`, `implement-checkpoint.sh`, `implement-healing.sh` now report to remote MCP
- `DEV_ENGINE_MCP_URL` env var controls remote reporting (empty = disabled, no new dependencies)
- Project identification by git root basename, no absolute paths

## [3.2.0] - 2026-02-25

### Added
- **Context Engineering System**: Token budget per phase (~8,700 tokens max), context pruning rules, and context saturation prevention in `/implement` Task Isolation
- `context-budget.sh` — estimates token cost of files and directories with breakdown and threshold indicators
- `on-session-end.sh` now tracks context metrics: estimated tokens consumed, files modified, healing events, active feature
- `analyze-sessions.sh` rewritten with context metrics, per-session averages, and budget health indicator (green/yellow/red)
- `GLOBAL_RULES.md` new section "Context Engineering" with budgets per operation type, pruning rules, and telemetry thresholds

### Changed
- `/implement` Task Isolation section rewritten with explicit context budget table, loading rules (include/exclude), phase task template, and saturation prevention protocol
- `CLAUDE.md` section "Context Rules" renamed to "Context Engineering (v3.2)" with budget references

### Fixed
- CLAUDE.md tree: remaining `(v3.0)` annotations changed to `(v3.1)` on skills/ and .quality/ lines

## [3.1.2] - 2026-02-25

### Fixed
- `install.sh --uninstall` now removes skills (symlinks) and hooks in addition to commands
- `install.sh` summary now generates dynamic hook list instead of hardcoding 3 of 5
- `install.sh` header comment no longer hardcodes version number

### Changed
- CLAUDE.md section headers updated from `(v3.0)` to `(v3.1)` for Available Skills, Hooks, and Context Rules
- CLAUDE.md tree structure now lists all 5 hooks (added `implement-healing.sh` and `post-implement-validate.sh`)

## [3.1.1] - 2026-02-25

### Added
- `docs/agent-teams.md` — executive summary of Agent Teams for developers (8 roles, engine awareness, File Ownership, hooks, setup, migration)
- `docs/architecture.md` — multi-stack architecture guide with per-stack document inventory (Flutter 5 docs, React 1, Python 1, GAS 4) and infra/design references
- Complete `docs/` directory now matches CLAUDE.md structure: getting-started, commands, agent-teams, architecture

## [3.1.0] - 2026-02-24

### Added
- Self-healing protocol: 4-level auto-recovery in `/implement` with healing log
- Telemetry analysis script: `analyze-sessions.sh` with healing and checkpoint reports
- Ratchet-safe baseline updater: `update-baseline.sh` (only improves, never regresses)
- Post-implement validation hook for baseline regression detection
- `implement-healing.sh` hook for structured healing event logging

### Changed
- Agent Teams prompts updated for v3 engine integration (Skills, hooks, quality)
- `install.sh` migrated from cp to symlinks for Skills (instant updates with git pull)

## [3.0.0] - 2026-02-24

### Added
- Agent Skills system with YAML frontmatter and auto-discovery
- Hooks system: pre-commit lint, session telemetry, checkpointing
- Context isolation with fork and Task patterns
- File ownership enforcement per agent
- `/explore` Skill for read-only codebase analysis
- `/quality-gate` Skill for adaptive quality gates
- Checkpoint/resume system for `/implement`

### Changed
- All commands migrated to Agent Skills
- `install.sh` updated to copy skills + hooks

## [2.4.0] - 2026-02-24

### Added
- `/quality-gate` command — auto-discovered baseline, progressive ratchet, auditable evidence
- AG-08 Quality Auditor — independent quality verification agent
- Quality gates between `/implement` phases — lint 0/0/0 blocking, coverage ratchet
- `.quality/` directory with baseline.json, plan.md, evidence/ and reports/
- Policies: zero-tolerance (lint), ratchet (coverage/arch/deadcode), no-regression (tests)
- Evidence auditable per feature: pre-gate, phase-N-gate, final-gate, report
- Agent Teams prompt for quality-auditor
- Template `quality-baseline.json.template`

### Changed
- Orchestrator updated with AG-08 and mandatory gates between phases
- GLOBAL_RULES updated with Quality Gates section

## [2.3.0] - 2026-02-24

### Added
- `/implement` command — end-to-end autopilot implementation
- Multi-stack support: Flutter, React, Python, Google Apps Script
- Partial commits per phase, coverage check 85%+, automatic PR with gh

### Changed
- Development flow updated: /prd → /plan → /implement → done

## [2.2.0] - 2026-02-24

### Added
- Google Apps Script stack (V8 + clasp + TypeScript)
- `architecture/google-apps-script/` — overview, folder-structure, patterns, testing-strategy
- AG-07 Apps Script Specialist
- Agent Teams: AppScriptSpecialist role with prompt and file ownership
- Detection of `.clasp.json` / `appsscript.json` in optimize-agents, plan and adapt-ui

### Changed
- GLOBAL_RULES.md updated with Apps Script rules
- Templates updated (CLAUDE.md, team-config, feature-generator)

## [2.1.0] - 2026-02-24

### Added
- `/optimize-agents` Engine Sync section — detects engine version and compares project files
- Step 0.6: locates jps_dev_engine, compares copied agents/prompts/config vs engine
- Audit output section 7: Engine Sync with symlink status and outdated files

## [2.0.1] - 2026-02-24

### Removed
- `uiux/` library — Stitch MCP defines visual style freely

### Changed
- AG-02 (uiux-designer) rewritten: works from Stitch designs, no predefined styles
- Cleaned references to uiux/ in CLAUDE.md, README.md, docs

## [2.0.0] - 2026-02-24

### Added
- Complete restructuring: canonical repository for the agentic system
- Multi-stack: Flutter 3.38+, React 19.x, Python 3.12+
- Agent Teams native (Claude Code experimental)
- Google Stitch MCP integration for UI design
- Infrastructure patterns: Supabase, Neon, Stripe, Firebase, n8n
- `/optimize-agents` command with Agent Teams support
- Generic agent templates per role

### Changed
- `install.sh`: command installation via symlinks

### Removed
- Sync/upgrade scripts (engine is reference, not tool)

## [1.0.0] - 2025-01-15

### Added
- Initial engine setup
- Global commands (prd, plan, adapt-ui)
- GLOBAL_RULES.md for Claude Code
- Setup and sync scripts (removed in v2)
