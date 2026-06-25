# Changelog

All notable changes to SpecBox Engine (formerly SDD-JPS Engine) are documented here.

## [6.12.0] - 2026-06-25 — "Claude Design Native"

Adds **Claude Design** as a second visual provider of the VEG, alongside Stitch. Claude Design (`claude.ai/design`, operated through the harness `DesignSync` tool) designs with the **real compiled components** of the project's design-system — a 1:1 mapping to code — whereas Stitch is text-to-mockup. SpecBox is an agentic system *for Claude*, so the design platform now matches the execution platform. One US from the orchestrator board `EmbedBuild/specbox-manager` (engine satellite), discovery `disc-52cbe4033fae`.

### Added

- **`visual_provider` abstraction** (`server/veg/visual_provider.py`, UC-2901) — the VEG resolves a per-project provider from `veg.providers` ∈ `["stitch"]` | `["claude_design"]` | both. A project without the key resolves to `["stitch"]` (legacy behaviour preserved). When `claude_design` is active and the gate is ready, it is the preferred provider; Stitch is the fallback. Config schema `veg.claude_design` (`projectId`, `syncRepo`) in `templates/settings.json.template`. ADR `doc/decisions/veg_visual_provider.md`.
- **5 `claude_design_*` MCP tools** (`server/tools/claude_design.py`, UC-2902) — `list_projects`, `get_project`, `create_project`, `sync_design_system`, `status`. Orchestrators that delegate to the harness `DesignSync` tool under the session's claude.ai login: no token is accepted or persisted, no programmatic delete. `assert_session_identity` + `resolve_writability` guarantee the consumption is billed to the logged-in user's subscription (multi-account: a writable project owned by another account proceeds with a warning; otherwise pending). Registered in `server/server.py`.
- **Topology-aware design-system gate** (`server/veg/design_system_gate.py`, UC-2903) — resolves where the design-system lives (orchestrator in multirepo, repo in monorepo) and checks `package.json` + `dist/`/Storybook. Not-ready yields `pending` with a reason, never raises.
- **Design-system sync engine** (`server/veg/claude_design_sync.py`, UC-2905) — prepares `.design-sync/config.json` with the anchored `projectId` and delegates the repo→bundle conversion to the harness `/design-sync` skill (does not reimplement `package-build.mjs`/`resync.mjs`). Idempotent via the `_ds_sync.json` anchor.
- **User runbook** `doc/runbooks/claude-design-veg.md` (UC-2906) — activation, Stitch-vs-Claude-Design table, topology anchoring, subscription model, no-delete.

### Changed

- **`/visual-setup`** gains a provider-selection step (Claude Design / Stitch / both; recommends Claude Design when a design-system is compiled) and **`/plan`** gains a Claude Design gate (sync when ready, pending when not — never fails). **`.claude/hooks/lib/autopilot.mjs`** adds `visual_provider_selection` + `claude_design_config_check` decision keys (always `ask`). (UC-2904)

### Decisions

- Claude Design is **complementary**, not a replacement for Stitch: it has its own precondition (a compiled design-system). It is the **preferred** provider when that precondition holds, but Stitch remains the default for projects without the new config.
- **No credentials**: auth is the session's claude.ai login (DesignSync), never an API key — the opposite of Stitch's stored key. **No programmatic delete**: DesignSync exposes none.

### Compatibility

- 100% backwards-compatible. A project without `veg.providers` behaves exactly like Stitch-only. No migration required.

### Tests

- 54 new tests, all green:
  - `test_visual_provider.py` (18), `test_design_system_gate.py` (11), `test_claude_design.py` (16), `test_claude_design_sync.py` (9).
- 34 regression tests on the existing Stitch + VEG suite stay green. `ruff` clean, `server.py` boots with the new tools registered, `autopilot.mjs` valid.

## [6.11.1] - 2026-06-23 — "Living Funnel"

Closes the site↔engine funnel end-to-end. The engine now publishes its own live state and capability inventory to the site `specbox.embed.build` on every `/release`, and the VSCode extension emits the activation event that closes the anonymous funnel. The only path to release is also the only path to publish, so the site changelog and inventory never diverge from the engine. Three US from the orchestrator board `EmbedBuild/specbox-manager` (engine satellite).

### Added

- **US-16 — publish-on-release of the engine state.** Pure parser of `ENGINE_VERSION.yaml` + `CHANGELOG.md` (`server/site_publish/parser.py`) with deterministic `public_highlights` derivation; idempotent UPSERT publisher to Supabase via PostgREST with the service-role (`server/site_publish/publisher.py`), injectable HTTP client, secret redaction; re-runnable CLI `python -m server.site_publish`. The site reads the tables and reflects the freshly-released version without editing `.astro` by hand (UC-1601..1603, PR #126).
- **US-20 — capability inventory publish.** Pure parser `build_capability_inventory` extracts from the engine's own code: agents (`agents/*.md`), real `@*.tool` decorators (not commented-out), skills (`.claude/skills/*/SKILL.md`) and the VSCode extension version — verified vs the real repo: 13 agents, 120 tools, 25 skills, ext v6.11.x. Idempotent `merge-duplicates` UPSERT to 4 `public.engine_*` tables; versioned SQL migration `20260618000020` (RLS read-only anon) closes the US-15 debt of tables created by MCP without an `.sql` in the repo (UC-2001..2003, PR #127).
- **US-26 — activation event that closes the funnel.** `registerActivationUriHandler` persists an `anon_id` from the activation deep-link in `globalState`; `maybeEmitActivation` emits ONE idempotent `activation` event to the `ingest_site_event` RPC over `node:https` (zero deps), no PII (only `ext_version`/`platform`/`vscode_version`), respecting `isTelemetryEnabled`. Verified e2e: `page_view→cta_click→install_intent→activation` is one correlated conversion in `site_event` (UC-2601/2602).

### Changed

- **`/release` Paso 6.5** publishes engine state + capability inventory in one invocation (`python -m server.site_publish`) as a non-blocking post-commit step — a publish failure is an actionable WARNING, never a release rollback. The publisher is idempotent UPSERT, safe to re-run.

### Compatibility

- 100% backwards-compatible. The site_publish subsystem is additive; the activation event is opt-in via existing telemetry consent. The new SQL migration is idempotent (`IF NOT EXISTS` + RLS read-only anon).

### Tests

- +56 tests green:
  - 44 Python (`tests/test_site_publish_parser.py`, `test_site_publish_publisher.py`, `test_site_publish_inventory_parser.py`, `test_site_publish_inventory_publisher.py`, `test_site_publish_main_inventory.py`).
  - 6 VSCode `node:test` (`vscode-extension/tests/activation.test.mjs`).
- 94% coverage on the new `site_publish` code, ruff clean, service-role never logged.

## [6.11.0] - 2026-06-14 — "Self Update"

US-14 (board del orquestador `EmbedBuild/specbox-manager`, satélite engine) cierra el funnel que abrió el auto-clone de v6.9.0: la extensión VSCode clonaba y hacía `git pull --ff-only` al arrancar, pero **solo comparaba la versión de la extensión instalada contra el `ENGINE_VERSION.yaml` en disco** — nunca consultaba el remoto. Un clon managed en versión vieja (o una rama divergida del developer) se quedaba atrás en silencio: el `--ff-only` fallaba sobre historia divergida y solo emitía un warning no bloqueante. Reproducido en dogfooding el 2026-06-14 (clon en 6.9.4 mientras `origin/main` ya estaba en 6.10.2).

### Added

- **Chequeo de versión remota al arrancar (UC-1401)** — fase −1 de `runUpdateFlow`: `git fetch origin --tags` + `git show origin/main:ENGINE_VERSION.yaml`. Helpers puros `fetchRemote` / `remoteEngineVersion` en [vscode-extension/src/install.ts](vscode-extension/src/install.ts) (git inyectable, nunca lanzan). Sin red / sin git (code 127) → se omite en silencio, activación normal.
- **Diálogo accionable X→Y + comparación semver (UC-1402)** — `compareSemver` numérico (`6.10.2 > 6.9.4`, no lexicográfico); si remota > local, modal `Update now` / `View changes` / `Later`. "Later" silencia esa versión durante la sesión (`Set` en memoria); una versión más nueva sí vuelve a preguntar. `View changes` abre el CHANGELOG y reabre la decisión.
- **Upgrade garantizado con verificación (UC-1403)** — `pull --ff-only` en progress bar, luego **relee `ENGINE_VERSION.yaml`** y verifica que la versión es la objetivo; un pull que reporta éxito pero no movió la versión se surface como `showErrorMessage` accionable, nunca como éxito.
- **Camino de divergencia con backup (UC-1404)** — si `--ff-only` falla por historia divergida, `reset --hard origin/main` **con backup `git branch specbox-backup/{rama}-{stamp}` previo + confirmación modal**. Un clon de usuario (no managed) **nunca** se resetea, solo se avisa (`isManagedPath` gate, ICP-1). Detección robusta vía `git rev-list --left-right --count origin/main...HEAD` además del stderr.

### Changed

- `vscode-extension/src/updater.ts` — `ExtensionUpdater` acepta un `GitRunner` inyectable; `runUpdateFlow` gana la fase −1 antes del pull. `extension.ts` **sin cambios** (sigue llamando `runUpdateFlow` fire-and-forget — el patrón de activación de v6.6.2 se preserva).

### Decisions

- Fuente de verdad de la versión remota = `origin/main:ENGINE_VERSION.yaml` (no GitHub Releases API ni tags) — reutiliza el `GitRunner` existente y funciona sin publicar releases.
- El `reset --hard` es opt-in y solo para el clon managed: los usuarios normales tienen el managed limpio en `main` y un `--ff-only` basta; solo el developer del engine diverge.

### Compatibility

- 100% backwards-compatible. `extension.ts` intacto; los helpers nuevos son aditivos. La feature solo *ofrece* el upgrade — nunca lo aplica sin consentimiento explícito del usuario.

### Tests

- 16 nuevos casos `node:test` en [vscode-extension/tests/updater-remote.test.mjs](vscode-extension/tests/updater-remote.test.mjs) con un `GitRunner` mock guionizado, cubriendo AC-01..AC-15. Suite completa de la extensión 109/109 verde; ningún test toca git ni la red.

## [6.10.2] - 2026-06-12 — "Mirror Bootstrap"

Production hotfix found in dogfooding while enabling the Native mirror on the client project `potencial_digital_2026` (Trello primary). The Trello→Native backfill ran and verified (11 US / 36 UC / 111 AC), but persisting the `mirror` config block failed with `CONFIG_FAILED` / `failing_place: "registry"` / `Project registry not found at /data/state/projects.json`, so the dual-write never activated. The primary (Trello) stayed read-only throughout — the hard guarantee held.

### Fixed

- **enable_mirror: registry auto-init + entry auto-seed (US-11 / UC-1104, FIX_enable_mirror_registry_autoinit)** — `_write_registry_mirror` ([server/migration/transactional_switch.py](server/migration/transactional_switch.py)) raised `FileNotFoundError` when `$STATE_PATH/projects.json` was absent and `KeyError` when the slug was missing. On a **cloud** MCP host that registry was never materialised for the project, so the very first config write (the mirror block) aborted the 3-place transaction at the first writer. The mirror is opt-in best-effort over an already-live primary, so it now bootstraps what it needs: a missing `projects.json` is created, and a missing project entry is **auto-seeded from the PRIMARY** (`spec_backend`/`board_id` taken from the live session's `spec_backend_config` + the `primary_board_id` tool arg) **before** the `mirror` block is set. An existing entry's primary fields are **never overwritten** — the on-disk primary always wins; the mirror block is purely additive. `disable_mirror` over a missing file/entry is a safe no-op (no entry is fabricated to remove something that isn't there).
- **Transactional rollback coherent for the just-created file** — `_read_registry_snapshot` now records `file_present`, and `_restore_registry` **deletes** a `projects.json` that a writer created (instead of leaving an empty-but-present registry) when a later place (app_spec/settings) fails — the state dir returns byte-identical to before the transaction.

### Changed

- `apply_mirror_transactional` gains optional `primary_backend` / `primary_board_id` kwargs (default empty → 100% backwards-compatible); `enable_mirror` passes the session primary's `backend_type` + `primary_board_id`. `disable_mirror` is unchanged.

### Tests

- 5 new tests in [tests/test_dual_backend.py](tests/test_dual_backend.py) exercise the real dirty state the previous suite never hit (the `trello_project` fixture always pre-seeded the entry — UC-827 pattern): file-missing auto-init, slug-absent auto-seed (other projects untouched), existing-primary-not-overwritten, rollback-deletes-the-created-file, and an end-to-end `enable_mirror` that seeds the registry from the session when `projects.json` is absent. `test_registry_snapshot_absent_when_no_registry` updated for the new `file_present` key. Dual-backend + transactional-switch suites: 63 passed, 1 skipped; mirror/migration/switch keyword slice: 59 passed.

### Compatibility

- 100% backwards-compatible; no API changes. `disable_mirror` behavior unchanged. Projects whose `projects.json` already contains the entry are written exactly as before.

## [6.10.1] - 2026-06-11 — "Reentrant Reserve"

Hotfix for a bug found in dogfooding while closing MGR-US-01 UC-06: after `reserve_uc(UC)`, calling `start_uc(UC)` with the same developer failed with `current transaction is aborted, commands ignored until end of transaction block`. Reads, standalone `reserve_uc`, and `move_uc` all worked — only `start_uc` broke.

### Fixed

- **reserve_uc reentrant inside a caller transaction (UC-1208, PR #118)** — `reserve_uc` ([server/coordination/reservations.py](server/coordination/reservations.py)) implemented idempotent re-reserve by catching `asyncpg.UniqueViolationError` and running a recovery `SELECT`. In Postgres a failed statement aborts the entire transaction, and a Python `try/except` does NOT open a savepoint to recover it. `start_uc_atomic` wraps `reserve_uc` + `UPDATE use_cases` in one transaction; when the same developer re-reserved a held UC, the duplicate INSERT violated `uc_reservations_pkey(project_id, uc_id)`, poisoning the transaction so the recovery SELECT and the later state UPDATE both failed. Rewritten to `INSERT ... ON CONFLICT (project_id, uc_id) DO NOTHING RETURNING *` — never raises, the transaction stays alive, the recovery SELECT is safe. Idempotency (same dev) and `AlreadyReservedError` (other dev) preserved; `audit_log` only written on the genuine first reservation. NOT the US-12 lifecycle trigger (the `UPDATE use_cases` with its triggers works in isolation).

### Tests

- New PG-gated `test_start_uc_atomic_after_reserve_same_dev_does_not_abort_tx` reproduces the bug (fails with `asyncpg.exceptions.InFailedSQLTransactionError` without the fix, passes with it; confirmed adversarially by stashing only the source). `FakeConn` unit mock updated to ON CONFLICT semantics (the old mock didn't replicate Postgres' aborted-transaction behaviour — UC-827 pattern). Native/reservations/coordination/lifecycle suite: 347 passed, 0 failed.

## [6.10.0] - 2026-06-11 — "UC Lifecycle Metrics"

Two complete User Stories from the orchestrator board (`EmbedBuild/specbox-manager`, satellite `engine`). US-12 makes per-UC implementation lead time honestly measurable on the Native backend — the start was never recorded (`start_uc_atomic` raw UPDATE, unaudited), the completion event was best-effort and could be silently lost (`_release_uc_native` swallows by design), and there were no lifecycle timestamps. The fix delegates capture and analytics to Postgres (triggers + views) keeping the engine thin. US-11 adds the dual-backend Native mirror for clients whose primary tracker is untouchable.

### Added

- **Dual-backend mirror (US-11, PRs #106-#110)** — `DualBackendWrapper` (best-effort Native mirror over a Trello/Plane/FreeForm primary; reads never touch the mirror; mirror failures are logged, never propagated), dual dispatch at the `get_session_backend` chokepoint, transactional 3-place `mirror` config, `enable_mirror`/`disable_mirror` tools with idempotent initial backfill, `tests/test_dual_backend.py` (injected-failure guarantee: the primary is never degraded).
- **Lifecycle capture (US-12 / 0012)** — append-only `uc_state_transitions` (from/to state, snapshotted `us_id`, developer, source; no FKs, audit_log pattern) + `use_cases.started_at` (first start wins) / `completed_at` (last completion wins) maintained by triggers. ANY writer of `use_cases.state` is captured transactionally — including raw SQL. Imports are excluded by construction (INSERTs don't fire the UPDATE trigger).
- **Per-transaction GUC context (0012/UC-1202)** — `server/coordination/lifecycle.py::set_lifecycle_context` (`app.developer_id` / `app.change_source`, SET LOCAL semantics, zero pool leakage) injected in `start_uc_atomic`, `update_item` (state changes) and `ingest_atomic` (`source='import'`). Honest degradation: no GUC → NULL developer + 'interactive', never an error.
- **Analytics views (0013)** — `v_uc_lifecycle` (lead_time, measurable, cycles, last_source), `v_lifecycle_kpis` (`coverage_pct` honesty KPI; p50/p90 over measurable+interactive only; `done_by_import`/`done_by_backfill`/`done_unmeasured` visible, never averaged), `v_us_progress`, `v_weekly_throughput`, `fn_lifecycle_kpis(project_id)`. Plain views — 2.8ms with 1004 UCs.
- **Read-only analytics role + tool (0014)** — `specbox_analytics_ro` (schema USAGE + SELECT on the lifecycle views only; base tables denied) for the panel to read directly; `get_project_kpis` MCP tool (Frontier-1 gated, session-tenant only, intervals as seconds).
- **Historical backfill PREPARED, not executed (0015)** — `fn_backfill_lifecycle(project_id, dry_run DEFAULT true)`: estimators `reserve_uc` → `branch_registry.created_at` for start, `complete_uc` with <10s same-developer `burst` flag for completion; fills NULLs only, marks everything `source='backfill_estimate'` with `metadata {estimator, burst}`. `fn_recompute_lifecycle_columns` makes rollback exact (transitions = source of truth, columns = cache). Execution gated on estimator calibration against real trigger data.
- **Active-time estimate (0016)** — `v_active_time_estimate`: session clustering (>30min gap) over transitions ∪ audit_log events; `events_count`/`sessions_count` as confidence; NULL over a fake 0.

### Changed

- `update_item`: a state change now wraps UPDATE + audit event in one transaction (side-fix: previously two separate autocommits; the audit row could survive without its mutation or vice versa).
- `start_uc_atomic` / `ingest_atomic`: GUC context injection (no behavioral change otherwise).
- `server/tools/coordination.py`: registers `get_project_kpis`.

### Decisions

- Capture lives in DB triggers, not a Python choke point: `use_cases.state` has three writers with no common code path; the trigger captures present and future writers (and manual fixes) transactionally.
- Honesty contract: every aggregated lead-time KPI is computed ONLY over measurable, interactive UCs; everything excluded stays visible and counted. `coverage_pct` reports how representative the metric is.
- Per-UC migration files (0012-0016): the Supabase ledger applies each file once — no post-merge edits to applied migrations.
- RLS on `uc_state_transitions` mirrors the 20260522000004 posture, role-guarded so the local dev Postgres (no anon/authenticated roles) keeps the file byte-for-byte mirrorable.

### Compatibility

- 100% backwards-compatible; no API changes to existing tools.
- **Deploy note**: production applies `supabase/migrations/20260611000012..16` via the Supabase ledger (`apply_migration`), in order — PENDING at release time (gated). Until applied, `get_project_kpis` fails in production (views absent). The local dev runner picks them up automatically.

### Tests

- 23 new tests, all green; full suite **1603 passed / 0 failed**:
  - `tests/test_uc_lifecycle_capture.py` (10) — trigger capture via the real raw UPDATE, re-cycles, ingest shape, injected-failure rollback, chain idempotency, GUC attribution, dirty-state E2E (UC-827 standard: coverage 60.0% / p50 3h exact).
  - `tests/test_audit_uc_lifecycle.py` (+1) — the done transition survives an injected `_release_uc_native` failure.
  - `tests/test_dual_backend.py` (12, US-11) — injected mirror failure never degrades the primary.

## [6.9.5] - 2026-06-04 — "Tenant-Scoped Keys"

Closes the last blocker of the FreeForm→Cloud/Native migration chain, found dogfooding `Dental-Data/DDBoss-Web-Saas`: the atomic ingest collided on `user_stories_pkey` because the native spec-table PK was the logical id alone (`US-01`), not namespaced by project — two projects could not both hold a `US-01` in the same shared Postgres. Plus two follow-ups surfaced in the same run: a format-dialect gap in `/switch-backend` and stale tests left behind by UC-660/UC-706.

### Added

- **`server/migration/freeform_normalize.py` (UC-709)** — pure transform from the nested FreeForm `index.json` (`{user_stories:[...]}`) to the flat `items.json` array the migration consumes (labels US/UC/AC, `parent_id`, `meta`). Faithful mode when the caller passes `ac_texts` extracted from the `.md` checkboxes; degraded mode synthesizes `ac_total` placeholder AC with exact counts (so the count guard passes) and sets `ac_degraded`.
- **`0009_tenant_scoped_pks.sql` (+ supabase mirror, UC-707)** — moves the PK of `user_stories` / `use_cases` / `acceptance_criteria` to composite `(project_id, id)` and rewires the two child FKs to composite same-tenant. Idempotent via `pg_constraint` catalog guards; no data backfill (`project_id` already populated).

### Changed

- **`server/backends/freeform_backend.py` (UC-709)** — memory-mode now detects a nested `index.json` dict and raises an actionable error naming the exploded dialect + the `normalize_source_content` recipe + the AC-in-markdown caveat, instead of the cryptic "got dict".
- **`server/tools/migration.py` (UC-707)** — `_ensure_target` builds the native backend from `dev_token` directly (no longer requires the unsatisfiable `migration_target_config` for native); new `SOURCE_TOO_LARGE_USE_BATCH` envelope for >64 KB freeform→native without a batch session.
- **`server/spec_backend.py` (UC-707)** — `parse_item_id` accepts an optional alphabetic id suffix (`[UC-004b]` → `UC-004b`).
- **`.claude/skills/switch-backend/SKILL.md` (UC-709)** — adds a format pre-flight (Paso 3/3a) that surfaces the items.json-vs-index.json mismatch at step 0, and a native prerequisite gate (Paso 2: tenant + whoami + DSN-on-server) before reading the source.
- **`tests/test_spec_mutations.py` + `tests/test_audit_log_destructive.py` (UC-708)** — realigned to the UC-660 (`items_content` kwarg in the session-backend mock) and UC-706 (creates now audit) contracts.

### Decisions

- Composite PK over surrogate UUID: the app layer was already tenant-scoped (every query filters `project_id AND id`), so the composite PK needs ~zero app-code change — minimal blast radius.
- AC normalization degradation is explicit, not silent: when AC texts aren't extracted from the markdown, counts round-trip exactly with placeholder text and `ac_degraded=True` so the skill warns.

### Compatibility

- 100% backwards-compatible. The PK migration is idempotent and recables constraints only (no row rewrite, no id change). The normalizer passes a flat `items.json` through unchanged.

### Tests

- 11 new in `tests/test_freeform_normalize.py`; `tests/test_native_tenant_pk.py` (cross-tenant isolation, Postgres-gated). Full suite **1548 passed, 0 failed**.

## [6.9.4] - 2026-06-03 — "Orphan Tenant Recovery"

Cierra el **cuarto eslabón** de la cadena de hallazgos del dogfooding (v6.9.1 → v6.9.2 → v6.9.3 → **v6.9.4**). v6.9.3 implementó la lógica de auto-provisión correctamente, pero **otra ruta la desactivaba en el camino real**: `setup_board` (`server/backends/native_backend.py`) hacía `INSERT INTO projects` **sin crear membresía**, fuera de `provision_native_project`. Se dispara en cada `set_auth_token` native, `import_spec` y migraciones legacy → deja un **tenant huérfano** (fila `public.projects` con CERO miembros). Entonces `_maybe_auto_provision` veía `exists=True` → `return False` → el gate de membresía → **FORBIDDEN** sobre una BD verificada vacía. El ecosistema se saboteaba a sí mismo. US-ORPHAN-PROVISION — 4 UC (UC-824..827), PR #90.

### Added

- **`tests/test_native_orphan_provision.py`** (UC-826) — 7 tests Postgres-gated (3 FIX B + 3 FIX A + 1 E2E del camino sucio). El E2E `test_e2e_orphan_then_migrate_recovers` crea la fila huérfana **PRIMERO** y verifica la recuperación end-to-end por el transporte por lotes (≥64 KB), estados done/backlog preservados 1:1 — la cobertura de estado sucio que faltaba y por la que pasó el gap.
- **`provision_native_project(name=..., validate_id=...)`** — dos parámetros opcionales (UC-824): `name` propaga el nombre del board en la provisión (preservando la semántica de `setup_board`); `validate_id=False` salta la validación del contrato canónico cuando el caller (setup_board) ya tiene un id aceptado, manteniendo `setup_board` permisivo sobre el id.

### Changed

- **FIX A — `setup_board` para native** (`server/backends/native_backend.py`, UC-824) delega en `provision_native_project` (tenant + membresía en una transacción), resolviendo la identidad del session `dev_token`. Nunca deja un proyecto con cero miembros; idempotente, no degrada admin. `setup_board` ahora **requiere** un token registrado válido (no puede crear un tenant sin dueño).
- **FIX B — `_maybe_auto_provision`** (`server/tools/migration.py`, UC-825) cuenta `project_members`: la condición pasa de "no existe" a "no existe O sin miembros". Adopta un tenant huérfano (0 miembros) creando la membresía del creador; mantiene `FORBIDDEN` para un tenant con ≥1 miembro (AC-13 intacto).
- **Fixtures de test** (`tests/test_native_handling.py`, `tests/test_native_provision.py`) — `setup_board` ahora requiere identidad registrada (helper `_setup_board_with_identity`); el test AC-13 siembra un owner real (antes era, implícitamente, el caso huérfano que ahora se adopta); el test "empty" espera `developers: 1` (el admin provisionado).

### Decisions

- **Invariante**: un tenant native nunca debe existir sin al menos un miembro; si por estado sucio legacy lo está, la auto-provisión lo adopta. Flujo convergente: cualquier estado sucio (0 miembros) se recupera a limpio (1 miembro = creador admin) en el primer `start_migration_session`, sin `FORBIDDEN`.
- **No contradice D2** (`native_provision_authority`): la refina — "proyecto pre-existente protegido por AC-13" = fila con **≥1 miembro**. Seguridad: un tenant con 0 miembros no tiene a quién robar → adoptarlo es seguro.
- **Estándar transversal (UC-827)**: los E2E de migración deben partir de **estados sucios realistas**, no solo de BD/fixtures vírgenes. Patrón recurrente de los 4 hallazgos: *el test pasa con el camino ideal; el dogfooding encuentra el camino real.*

### Compatibility

- 100% backwards-compatible. `provision_native_project` se reutiliza tal cual (los nuevos params son opcionales con defaults que preservan el comportamiento previo). El contrato `project_id` (D1) y el flujo OAuth/identidad no cambian.

### Tests

- 7 nuevos tests en `tests/test_native_orphan_provision.py`, todos verdes:
  - FIX B (UC-825): adopta huérfano / no adopta tenant con miembros / limpia cache de auth.
  - FIX A (UC-824): crea membresía / idempotente sin degradar admin / adopta huérfano preexistente.
  - E2E (UC-826): huérfano primero → migración por lotes se recupera sin FORBIDDEN, estados 1:1.
- Suite native completa sin regresión (396 passed).
- Las 7 fallas de `test_spec_mutations.py` son **preexistentes** (mock `_fake_get_session_backend` sin `items_content`), verificadas stasheando la rama — no son de esta release.

## [6.9.3] - 2026-06-03 — "Tenant Provisioning"

Cierra los **dos gaps combinados** descubiertos en dogfooding v6.9.2 al migrar `specbox_cloud` freeform→native **de cero**: el transporte por lotes funcionó, pero la migración se bloqueó en `start_migration_session` con `Developer X is not a member of project EmbedBuild/specbox_cloud`. **GAP 1**: el path batch no provisionaba `public.projects` + `public.project_members` cuando el proyecto nace de cero (huevo-gallina enforced por la FK `project_members→projects`). **GAP 2**: engine (`owner/repo`) y panel (slug) nunca acordaron el formato de `project_id`. US-NATIVE-PROVISION — 6 UC (UC-818..823), PR #89.

### Added

- **`server/coordination/project_id.py`** (UC-818) — contrato canónico, punto único de verdad compartido engine↔panel: `canonical_project_id(owner, repo) → "owner/repo"` (identidad, case-preserving), `display_slug(project_id) → "owner-repo"` (proyección URL-safe, idempotente), `validate_project_id` (rechaza malformados con `InvalidProjectIdError`). Funciones puras.
- **`provision_native_project()`** (`server/migration/native_handling.py`, UC-820) — UPSERT `public.projects` + `seed_native_identity(role="project_admin")` para el caller + fila `audit_log` (`OP_PROVISION_PROJECT`), todo en **una transacción**. Idempotente; nunca degrada un admin existente (decisión D2).
- **`_maybe_auto_provision`** (`server/tools/migration.py`, UC-821) — `start_migration_session` auto-provisiona el tenant + creador antes del gate de membresía cuando el target nace de cero, rompiendo el huevo-gallina. Resuelve el `developer_id` real del token y limpia la cache de auth para que el gate relea la membresía fresca.
- **`tests/test_native_provision.py`** (UC-822) — 15 tests (4 puros + 11 Postgres-gated). E2E `test_e2e_provision_then_migrate_from_scratch`: BD vacía → start (auto-provisión) → append → commit → verifica project_id canónico, creador `project_admin`, 1 US / 40 UC / 120 AC con estados done/backlog preservados, display_slug correcto. El camino que no tenía cobertura y por el que pasó el gap de v6.9.2.
- **`doc/decisions/native_project_id_contract.md`** (UC-823) — declara D1 + D2 como decisiones canónicas y documenta el cambio coordinado requerido en el panel (`specbox_cloud`).

### Changed

- **`seed_native_identity`** gana parámetro `role` (default `member`); lo propaga a `add_project_member` (UC-819).
- **`add_project_member`** valida `role` contra `VALID_PROJECT_ROLES` (`{project_admin, member}`) antes del INSERT — un rol arbitrario nunca se persiste (UC-819 AC-06).
- **`server/coordination/audit.py`** — nueva constante `OP_PROVISION_PROJECT` (operación auditada no destructiva).
- **`app_spec.md` §6** — D1 (`native_project_id_contract`) + D2 (`native_provision_authority`) registradas como decisiones canónicas del engine.

### Fixed

- **`start_migration_session`** ahora captura `ForbiddenError` y devuelve un envelope `FORBIDDEN` limpio. Un token válido que no es miembro de un proyecto **pre-existente** era antes un crash sin capturar — la superficie original del error "not a member" del hallazgo. Un proyecto pre-existente del que el caller no es miembro NO se auto-une (§6 del panel acotado a excepción de bootstrap, UC-821 AC-13).

### Decisions

- **D1 — `native_project_id_contract` = `owner/repo` + display slug derivado**: identidad `owner/repo` (cero migración de ids existentes, sin colisión cross-owner, trazabilidad GitHub); slug solo para URLs. Punto único de normalización.
- **D2 — `native_provision_authority` = el engine auto-provisiona al creador como `project_admin` (excepción de bootstrap)**: el panel sigue siendo el único editor de **otros** miembros; el engine solo auto-provisiona al propio creador en una migración de cero.

### Compatibility

- 100% backwards-compatible. El path no-batch (`migrate_backend`) y los proyectos ya provisionados quedan intactos. Cero migración de `project_id` existentes (ya son `owner/repo`).
- Cambio coordinado en el repo del panel (`specbox_cloud`): relajar la validación INSERT de `apps/api/src/routes/projects.ts:140,173` para aceptar `owner/repo` en native + derivar el display slug con el contrato compartido. Se implementa en su propio repo.

### Tests

- 15 nuevos tests en `tests/test_native_provision.py`, todos verdes (4 puros UC-818 + 11 Postgres-gated). Suite native/coordination/migration/audit sin regresión: **402 passed**.
- Pre-existing failures on `main` (`tests/test_spec_mutations.py`, 7 tests, fixture stale `_fake_get_session_backend`) permanecen — verificadas idénticas en el commit base, fuera del alcance de esta release.

## [6.9.2] - 2026-06-02 — "Batch Ingest"

Cierra el gap de **transporte** de v6.9.1 descubierto en dogfooding: la lógica del switch-backend funcionaba, pero `switch_project_backend` con `source_type='freeform'` exigía el `items.json` completo como **un único string** (`source_content`), y un board real (`specbox_cloud`: 133 KB / 568 ítems) no cabe fiablemente en un parámetro de tool sin riesgo de truncado/corrupción silenciosa. El MCP es siempre remoto desde v6.7.0. La migración a Native ahora cruza por **ingesta por lotes server-side**: `start → append × N → commit`, troceo verificable por SHA-256, escritura en **una transacción atómica**. US-NATIVE-BATCH-INGEST — 5 UC (UC-680..684), PR #88.

### Added

- **`server/migration/batch_session.py`** — `MigrationSession` + `SessionStore`: zona de staging en memoria por `session_id`, efímera (TTL), con `time_fn`/`id_fn` inyectables para tests. Una sesión sin commit expira y el cliente reinicia limpio (no hay resume; el commit es el único punto que toca Postgres).
- **`server/migration/integrity.py`** — `sha256_hex`: único punto de hashing para la verificación por chunk y el pre-flight global.
- **`NativeBackend.ingest_atomic`** (`server/backends/native_backend.py`) — escribe las 3 fases (US, UC+AC, comments) dentro de **una** `conn.transaction()` → rollback total real ante fallo a mitad (vs el per-item `continue` de `write_target`). Estados preservados verbatim (done queda done, backlog queda backlog). Re-valida membresía al commit.
- **Tools MCP** (`server/tools/migration.py`): `start_migration_session` (valida `dev_token` una vez, cache reusado, no escribe), `append_migration_chunk` (verifica hash por chunk), `commit_migration_session` (pre-flight global hash + conteo antes de cualquier INSERT, luego `ingest_atomic`).

### Changed

- **`server/migration/writer.py`** — nuevo `build_write_plan(source_data)` + `WritePlan`/`PlannedUC`: extrae la clasificación + resolución de parent + orden como datos I/O-free, compartido por `ingest_atomic`. `write_target` genérico queda intacto.
- **`switch_project_backend`** acepta `batch_session_id`: cuando el source freeform excede `BATCH_TRANSPORT_THRESHOLD_BYTES` (64 KB) y el target es native, su paso de escritura es la ingesta por lotes; el resto del switch atómico (3 lugares de config) no cambia.
- **`.claude/skills/switch-backend/SKILL.md`** — Paso 3b: plan de transporte por lotes (nº chunks, tamaño, hash) + resumen post-commit, sin pegar el blob.
- **`tests/test_native_unauthenticated.py`** — allowlist documentada de `migration.py` en el guard arquitectural (las batch tools son tools native que legítimamente devuelven el envelope `UNAUTHENTICATED`).

### Decisions

- El gap #3 (transacción envolvente) NO se resolvió hilando una `conn` por el `write_target` genérico — rompería la abstracción multi-backend (Trello/Plane no tienen `conn`). Se añadió un método `ingest_atomic` dedicado a Native que abre una transacción única.
- Staging efímero (no reanudable) por decisión de discovery: YAGNI para v1, sin estado parcial en Postgres que reconciliar.
- Chunk recomendado ≤16 KB; verificación SHA-256 por chunk + reensamblado global.

### Compatibility

- 100% backwards-compatible y aditivo. `switch_project_backend` sin `batch_session_id` usa la ruta `source_content` de siempre. No relaja el blindaje de seguridad (dev_token server-side, escritura solo en el tenant, sin exponer `service_role`, sin relajar `deny_anon`).

### Tests

- 19 nuevos tests en `tests/test_native_batch_ingestion.py`, todos verdes:
  - 10 unit (sin DB): `sha256_hex` + `SessionStore` (open/append/hash-mismatch/duplicate/reassemble/close/TTL) + sanity de la fixture ≥100 KB.
  - 9 Postgres-gated (`docker-compose.dev.yml`): tools start/append/commit, identidad cacheada, switch batch integration, `ingest_atomic` E2E ≥100 KB / 120 UC mixtos, atomicidad (rollback total + retry limpio).
- No-regresión en la suite native: 78 passed.
- Los 7 fallos pre-existentes en `main` de `tests/test_spec_mutations.py` (fixture desactualizada con kwarg `items_content`) permanecen, ajenos a esta release.

## [6.9.1] - 2026-06-02 — "Atomic Switch"

Rediseña "cambiar de backend" como **una sola operación atómica todo-o-nada** y cierra el path-bug de MCP remoto que dejaba el cambio hacia/desde `native` (Cloud) roto en producción. Reproducido en dogfooding: un `migrate_backend(freeform→native, dry_run=True)` con MCP remoto leía el filesystem del **servidor** (22 US/112 UC del propio engine en el VPS, o 0/0) en vez de las 11/88 del cliente — ejecutar el real habría escrito un proyecto vacío en Postgres y apuntado el panel Cloud a la nada. US-BACKEND-SWITCH-NATIVE — 8 UC (UC-810..817), PR #87.

### Added

- **`switch_project_backend`** (`server/tools/migration.py`) — tool MCP que orquesta migrate → seed identity → switch de los 3 lugares de config → exit-report como **todo-o-nada**, con rollback end-to-end.
- **`server/migration/orchestrator.py`** — `run_switch` compone los pasos como callables inyectables (testeable sin MCP/Postgres).
- **`server/migration/rollback.py`** — `rollback_data_migration` deshace la migración de datos (DELETE del proyecto native nuevo) si un paso posterior falla.
- **`server/migration/count_guard.py`** — `verify_count` bloquea el execute si el dry-run leyó 0 items o el conteo confirmado no coincide con el preview.
- **`require_dev_token` + `delete_native_project`** (`server/migration/native_handling.py`) — fail-fast de identidad native + DELETE para rollback.

### Changed

- **`resolve_source_backend` / `migrate_preview`** — content-passing: el source `freeform` se lee del `source_content` del cliente (memory-mode `FreeformBackend`), nunca del FS del servidor. trello/plane de la API; native del `NativeBackend` DTO.
- **`migrate_backend` / `switch_backend`** — siguen funcionando pero recomiendan la tool atómica en su respuesta.
- **`FreeformBackend`** — `get_labels`/`get_board_name` hechos FS-safe en memory-mode (devuelven vacío/default en vez de tocar `self.root`). Imports `os`/`shutil` muertos eliminados.
- **`onboard_project --backend native`** — documenta `native_db_state="empty"` + `next_action` (no dejar al usuario esperando datos inexistentes en el panel).
- **Skill `/switch-backend`** — online-first: elimina la precondición bloqueante "MCP local" (contradecía la decisión canónica "Transporte único MCP remoto + content-passing", UC-668), lee el source del cliente y escribe los 3 lugares de config de vuelta en el cliente.

### Decisions

- **Operación única atómica** (D1): `migrate`/`seed`/`switch`/`exit-report` pasan a ser pasos internos, no interfaz pública que el usuario encadena.
- **Salida de native** (D2): reservas/membresías/audit se descartan (no tienen destino single-user) + reporte auditable mostrado antes de confirmar.
- **Guard rail dry-run** (D3): confirmación de conteo obligatoria ("N US / M UC leídas del cliente") antes del execute.
- **Rollback de datos**: garantizado solo para `created_fresh` (proyecto native nuevo). Para `reuse` el rollback cubre la config pero no deshace el merge de items — documentado y avisado en el preview.

### Compatibility

- 100% backwards-compatible: `migrate_backend`/`switch_backend` mantienen su firma (params nuevos opcionales). Ningún cambio de schema.

### Tests

- `tests/test_backend_switch_native.py` — **24 passed** (0 skipped con `docker compose -f docker-compose.dev.yml up`; AC-19 gated en `PG_OK`).
  - AC-18 reproduce el bug original (MCP remoto + 11/88 cliente → lee 11/88, FS del servidor intacto).
  - AC-19 migra freeform→native contra **Postgres real** preservando estados `in_progress`/`done` + developer como miembro.
- Suites native existentes sin regresión: 51 passed (conformance + native_handling + dispatch + nxn).
- Los 7 fallos de `test_spec_mutations.py` en la suite global son preexistentes en `main` (mock desactualizado), ajenos a esta release.

## [6.9.0] - 2026-06-01 — "Self-Provisioning"

Cierra el funnel de onboarding en máquina limpia: la extensión VSCode ahora se auto-aprovisiona el engine. Cuando no encuentra el repo en disco, clona el engine público (`github.com/EmbedBuild/specbox-engine`) a un directorio gestionado (`~/.specbox/specbox-engine`) automáticamente — notifica, no pregunta — y lo mantiene al día con `git pull`. Un clon propio del usuario nunca se toca. US-VSCODE-AUTOCLONE — 4 UC (PR #86).

### Added

- **Auto-clone del engine** (UC-109/UC-110) — `resolveEnginePath()` clona el engine público a `~/.specbox/specbox-engine` automáticamente como paso 3.5, antes del `showOpenDialog` (que queda como degradación). Helpers puros `ENGINE_REPO_URL` / `managedEnginePath()` / `isManagedPath()`; `cloneManagedEngine(deps)` con git runner inyectable que nunca lanza y limpia el dir parcial en fallo. Idempotente: un clon gestionado presente no se re-clona.
- **Auto-pull del clon gestionado** (UC-111) — Phase 0 de `runUpdateFlow` hace `git pull --ff-only` solo si el engine resuelto ES el gestionado (`isManagedPath===true`); un clon de usuario en otra ruta nunca recibe pull (protección ICP-1). Pull fallido → warning no bloqueante (fire-and-forget v6.6.2).

### Changed

- **Walkthrough + README (ES+EN)** (UC-112) — describen el auto-clone gestionado; el `git clone` manual deja de ser prerequisito de la extensión. El bloque Quick Start de instalación CLI manual se conserva.
- **ENGINE_VERSION.yaml** — añadida la entrada 6.8.0 al changelog del manifiesto, que faltaba del release anterior (solo estaba en CHANGELOG.md).

### Compatibility

- 100% backwards-compatible. La extensión sigue resolviendo config/workspace/rutas comunes primero; el auto-clone es el último recurso antes del diálogo. Clones de usuario intactos.

### Tests

- +14 nuevos tests, todos verdes:
  - `vscode-extension/tests/autoclone.test.mjs` — AC-01..AC-08 + NFR idempotencia (stub de vscode/git/fs, sin red).
- Suite de la extensión 94/94 verde, sin regresión. `tsc -p ./` limpio.

## [6.8.0] - 2026-05-31 — "Connectivity UX"

Reenfoca la conectividad cliente/servidor bajo un transporte único (MCP remoto, online-first) donde el server nunca toca un filesystem ajeno y el estado del cliente fluye por content-passing vía un bridge Node. Cierra la regresión #82 (fallo silencioso en MCP remoto), hace `/audit` operativo en remoto, convierte la actualización de la extensión en un proceso pedagógico, y blinda el drift gate contra violaciones de decisiones canónicas. US-CONN-TRANSPORT — 9 UC en 4 hitos (PR #85).

### Added

- **FreeForm content-passing** (UC-660/661/662) — las 7 tools de mutación aceptan `items_content` y operan sobre un dict en memoria; bridge cliente `lib/mcp-client-io.mjs` (`readTrackingBundle`/`writeTrackingBundle`) con guard de path-traversal; FreeForm first-class en el onboarding de la extensión sin Python.
- **Audit analyzers client-side** (UC-663) — los 8 analyzers SQuaRE ISO/IEC 25010 portados de Python a Node `.mjs` en `.quality/scripts/audit/`; `lib/scoring.mjs` réplica de `scoring.py`; `submit_quality_audit(report)` valida el reporte construido en el cliente. El PDF se sigue renderizando server-side.
- **Updater pedagógico de la extensión** (UC-664/665/666) — `detectClientConfigCase()` (5 casos), auto-migración de transporte con backup `.bak-<ts>` + comando "Revert last migration", orquestador `runUpdateFlow()` fire-and-forget por fase, mensaje mínimo para el caso sin cambios.
- **Drift gate canónico** (UC-667/668) — `validate_discovery_completeness` valida contra `app_spec.md § canonical_decisions`; registrada la nueva decisión canónica de transporte (append-only).

### Changed

- `server/tools/spec_mutations.py`, `spec_driven.py`, `backends/freeform_backend.py`, `auth_gateway.py` — content-passing en mutadores FreeForm.
- `server/tools/discovery.py` — gate validado contra decisiones canónicas.
- `.claude/skills/audit/SKILL.md`, `feedback/SKILL.md` — flujo de analyzers locales + cableado al bridge (UC-661 AC-02).
- `vscode-extension/src/{updater,extension,mcp,auth}.ts` — updater orquestador + FreeForm first-class.

### Compatibility

- 100% backwards-compatible. Cierra la clase de fallo silencioso del #82 sin cambios de schema.

### Tests

- Bridge FreeForm 21/21 · Audit analyzers 19/19 · Extensión VSCode 80/80 · suite Python de la feature verde · tsc RC=0.
- Bug fix de paso: regex `/g` module-level con `lastIndex` compartido bajo concurrencia (portability analyzer) → regex fresco por uso + test de regresión.

## [6.7.0] - 2026-05-28 — "Zero-Friction Onboarding"

Dos features encadenadas del onboarding de la extensión VSCode, mergeadas en [PR #82](https://github.com/EmbedBuild/specbox-engine/pull/82). Disparadas por el feedback de un beta-tester (ICP-2) bloqueado por la dependencia de Python: como el MCP server se sirve gratis en remoto, el modo Local no aportaba valor suficiente para justificar la fricción; y la extensión sabía qué faltaba pero no lo comunicaba proactivamente.

### Added

- **Gate de prerequisitos no bloqueante** (US-VSCODE-PREREQ-GATE) — nuevo `vscode-extension/src/prerequisites.ts` con `evaluatePrerequisites(health)` (pura, testeable) que clasifica el entorno en `ready`/`degraded` sobre el set crítico (Claude Code, Engram, Node, MCP SpecBox, MCP Engram; GGA es opcional). En el arranque, si `degraded`, `showWarningMessage` no bloqueante avisa que SpecBox puede no funcionar correctamente, con acciones (Run Setup Wizard / Configure MCP / Open Guide). Silencio si `ready`.
- **Comando "SpecBox: Check Prerequisites"** (`specbox.checkPrerequisites`) — re-evalúa el entorno a demanda desde la paleta; declarado en `package.json` + nls EN/ES.
- **Helpers puros en `mcp.ts`** — `buildRemoteServerConfig` y `buildEngramInstallPlan`, testeables sin `vscode`.

### Changed

- **Onboarding cero-Python** (US-VSCODE-ZERO-PYTHON) — `mcp.ts`: eliminado el modo Local del MCP (QuickPick local/remote + rama `uv`/`python` + `findEnginePath` huérfano); `configureSpecbox` escribe directo el endpoint hospedado (`npx mcp-remote`). Engram migra de `pip/pipx` a `brew install gentleman-programming/tap/engram` con fallback manual; sigue Required.
- **Python eliminado de la UI** — `health.ts` (sin `checkPython` ni campo `python`), `constants.ts` (sin `REQUIRED_PYTHON_VERSION`), `statusbar.ts`, `onboard.ts`, `views/status-tree.ts`. El panel Status ya no muestra fila Python.
- **Docs** — walkthrough, `package.json`, `README.md` y `README.es.md` de la extensión purgados de Python; Engram documentado vía Homebrew. README raíz + CLAUDE.md con sección v6.7.0.

### Decisions

- Sin fallback air-gapped: el cliente depende del MCP remoto gratuito (decisión de producto explícita; no se conserva un modo local oculto).
- Severidad del gate: warning no bloqueante (filosofía "avisar, no impedir" + arranque rápido de v6.6.2).
- Alcance del gate incluye MCP configurado (SpecBox + Engram), no solo binarios.

### Compatibility

- 100% backwards-compatible. No toca el server Python ni el backend de tracking. La decisión canónica "FreeForm requiere MCP local (stdio)" es sobre el MCP de tracking, no sobre el MCP del engine que configura la extensión — no afectada.

### Tests

- +9 tests de la extensión (`tests/mcp.test.mjs` + `tests/prerequisites.test.mjs`), 56/56 verde. `npm run compile` limpio.

## [6.6.2] - 2026-05-28 — "Fast Activate"

Hotfix crítico descubierto tras publicar v6.6.1 al Marketplace: la extensión VSCode se quedaba indefinidamente en **"Activating…"** para prácticamente todos los usuarios. Trazabilidad: UC-653 bajo US-VSCODE-GITHUB-OAUTH ([PR #81](https://github.com/EmbedBuild/specbox-engine/pull/81)).

### Fixed

- **Extensión atascada en "Activating…"** — `activate()` hacía `await` en serie de `health.run()`, el prompt del `ExtensionUpdater` ("Update extension?") y el onboarding gate. El `showInformationMessage` del updater **bloquea hasta que el usuario pulsa**. Como cada release bumpa la versión, tras publicar v6.6.1 todos los usuarios tenían engine local 6.6.0 ≠ extensión 6.6.1 → el prompt saltaba en cada primer `activate` y, al estar `await`eado dentro de `activate()`, VS Code se quedaba en "Activating…" hasta que el usuario respondiera (o para siempre si lo ignoraba). Confirmado vía Extension Host log: `specbox-engine` inicia activación y nunca reporta finalización.

### Changed

- `vscode-extension/src/extension.ts` — `activate()` registra comandos/vistas y arma el polling de identidad de forma **síncrona** y retorna de inmediato. Todo el trabajo lento/interactivo (health check, prompt de update, onboarding gate, refresh inicial de identidad) se mueve a `runStartupTasks()`, disparado con `void` (fire-and-forget) y con guards por fase para que nada pueda volver a colgar la activación.

### Decisions

- Trade-off aceptado: las welcome views del sidebar pueden mostrar estado vacío ~1-15s al arrancar (hasta que `health.run()` resuelve y dispara `setContext`) — un parpadeo breve a cambio de eliminar el cuelgue eterno.

### Compatibility

- 100% backwards-compatible. Sólo toca `vscode-extension/src/extension.ts`; backend MCP, cloud y los otros backends de tracking no se ven afectados.

### Tests

- 47/47 verde en la suite `node:test` de la extensión (sin regresión). `tsc -p ./` y lint i18n limpios. Verificación manual en directo: la extensión pasa de "Activating…" a estado normal sin requerir interacción del usuario.

## [6.6.1] - 2026-05-28 — "Loopback Resilience"

Patch que cierra dos defectos del flujo OAuth de la extensión VSCode descubiertos en el smoke test post-deploy de v6.3.0 (cross-repo con [specbox_cloud#49](https://github.com/EmbedBuild/specbox_cloud/pull/49) / UC-905, ya en producción). El bug de captación de usuarios (identidad cruzada) lo arregló el cloud; este patch endurece el lado consumidor de la extensión. Trazabilidad: UC-652 bajo US-VSCODE-GITHUB-OAUTH ([PR #80](https://github.com/EmbedBuild/specbox-engine/pull/80)).

### Fixed

- **Loopback timeout prematuro (`ERR_CONNECTION_REFUSED`)** — `startLoopbackServer` armaba el timeout de 5 min al crear el server, antes de que el usuario navegara. Leer la pantalla "Confirm your account" del cloud, cambiar de cuenta GitHub o despejar el diálogo "open external website" de VS Code agotaba el reloj y el callback caía en un puerto muerto. Ahora el timeout es de 10 min y se arma vía `armTimeout()` idempotente **sólo tras un `openExternal` exitoso**, de modo que el tiempo de setup no cuenta contra la ventana de sign-in.
- **Token persistido sin verificar identidad** — `runSignIn` guardaba el `mcp_token` sin comprobar a qué developer resuelve. Ahora llama `fetchWhoami()` antes de persistir, rechaza con `identity_unverified` si el cloud no confirma identidad, y muestra el handle real ("Signed in as @handle"). Cierra **UC-645 AC-05**, especificado en v6.3.0 pero sin implementar.

### Added

- **`describeSignInError()`** — helper que centraliza los copys accionables de error de sign-in (`timeout` / `browser_blocked` / `identity_unverified`) para el onboarding y el comando directo `specbox.signIn`. Strings nuevas en los bundles l10n EN + ES (paridad 42/42).

### Changed

- `vscode-extension/src/oauth.ts` — `LoopbackServer` expone `armTimeout()`; `CALLBACK_TIMEOUT_MS` 5 → 10 min.
- `vscode-extension/src/auth.ts` — `runSignIn` verifica identidad vía whoami; `maybeShowOnboarding` muestra el handle real.
- `vscode-extension/src/extension.ts` — el comando `specbox.signIn` usa `describeSignInError`.

### Compatibility

- 100% backwards-compatible. Sólo toca `vscode-extension/`; backend MCP, cloud y los otros 3 backends de tracking no se ven afectados.

### Tests

- 47/47 verde en la suite `node:test` de la extensión (+4 nuevos del timeout diferido, sin regresión sobre los 43 previos). Lint i18n y `tsc -p ./` limpios.

## [6.5.0] - 2026-05-27 — "Stitch Native Migration — Behavioural (PR-2)"

Cierra el ciclo de la migración Stitch iniciado en v6.4.0. PR-1 introdujo la foundation (cliente nativo + enums reales + mapper VEG↔M3 + cleanup quota). **Esta PR-2 cablea esa foundation al pipeline real**: `generate_design_md_tool` emite Material 3 estricto, `stitch_generate_screen_v2` limpia prompts cuando hay DS aplicado, `/visual-setup --migrate-stitch` cubre los 6 casos de migración, y `upgrade_project` + `version_matrix` surfacean el nuevo `stitch.contract`. Cutover duro de `inline_prefix_v1` sigue planificado para v7.0 (ver `doc/migrations/v7_stitch_native_chain.md`).

Trazabilidad: PRD `doc/prd/stitch_native_migration_prd.md` UCs UC-704 (F5), UC-705 (F6), UC-706+UC-707 (F7) y UC-709+UC-710 (F9). UC-700–UC-703 y UC-708 ya entregados en v6.4.0.

### Added

- **`server/design_md/material3_view.py`** — proyección Material 3 de un `DesignMd`. `build_material3_frontmatter(doc, archetype, brand_kit?, jtbd_overrides?)` produce el YAML que Stitch parsea server-side (theme block + tokens M3 + typescale semántica). `render_veg_notes_section` preserva semántica VEG en el cuerpo Markdown.
- **`server/design_md/writer.py`** acepta `material3=<Material3FrontMatter>` y emite el frontmatter alternativo + una sección final `## VEG Notes`. `io.save(...)` propaga el parámetro.
- **`stitch_generate_screen_v2` parámetros nuevos**: `contract` (`native_v2` default, `inline_prefix_v1` legacy) y `design_md_content` (solo legacy). Cuando `native_v2` detecta DS aplicado vía `list_design_systems`, el helper `_strip_theme_directives` elimina líneas con colors / fonts / roundness del prompt antes de pasarlo a la fallback chain. Output enriquecido con `prompt_mode` (`design_system_applied` / `design_system_missing` / `inline_prefix`) + `design_system_info`.
- **`server/tools/stitch_migration.py`** — 3 MCP tools nuevos:
  - `detect_stitch_migration_case(project, settings_local_json?, design_md_content?, generated_screens_count)` clasifica el proyecto en uno de los 6 casos A–F con `evidence` + `recommended_action`.
  - `migrate_project_to_native_v2(project, case, ...)` devuelve la recipe ordenada (`actions`, `files_to_write`, `stitch_calls`, `settings_patch`, `confirmation_required`). Planning-only: no ejecuta, la skill `/visual-setup --migrate-stitch` orquesta. Caso D pide literal `MIGRATE-RETROACTIVE`, caso E pide `APPLY-PROPOSAL`.
  - `get_stitch_migration_stats(project, migration_jsonl_content?)` agrega `.quality/logs/stitch-migration.jsonl` (content-passing) y devuelve `status` ∈ `{no_data, in_progress, completed, failed}` + counts por case / action / outcome.
- **`.claude/skills/visual-setup/SKILL.md`** — sección "Modo `--migrate-stitch` (v6.5.0)" con el playbook de 5 pasos (pre-check → recipe → preview → exec → telemetría) + tabla resumen de los 6 casos.
- **`upgrade_project`** devuelve `stitch_migration_alignment` (advisory con `current_contract`, `target_contract`, `cutover_release=v7.0`, doc link) + `stitch_contract` para que consumidores agreguen sin re-leer meta.
- **`get_version_matrix`** añade columna `stitch_contract` por proyecto (`native_v2 | inline_prefix_v1 | unknown | not_applicable`) + `stitch_contract_summary` con totales globales + `stitch_migration_hint` que cuenta cuántos proyectos siguen en legacy y enlaza al runbook v7.0.
- **3 nuevos archivos de tests** (67 tests):
  - `tests/test_stitch_migration.py` — clasificador (6 casos + multirepo precedence), recipe shape per case, agregador telemetría, recomendaciones.
  - `tests/test_design_md_material3_view.py` — resolución fonts/roundness/luminance, derivación colors M3, mapping ArchetypeId → VegArchetype, serializer M3 vs default.
  - `tests/test_stitch_generate_v2_prompts.py` — heurística `_strip_theme_directives`, `_resolve_prompt_for_contract` en los 5 modos (inline / native_v2 con/sin DS / fallback / list_design_systems failure).

### Changed

- **`generate_design_md_tool`** acepta `contract` (default `native_v2`) y emite el frontmatter Material 3 cuando se activa. Output incluye campos nuevos `contract` y `material3`. `inline_prefix_v1` reproduce el output v5.31 sin cambios.
- **`_StitchOpsAdapter`** ya no expone `build_site` (la tool fantasma se eliminó en v6.4.0); reemplazado por un comentario apuntando a `stitch_build_site_batched_v2`.
- **`server/server.py`** registra `register_stitch_migration_tools(mcp)` después de los wrappers v5.31.
- **`tests/test_stitch_v2_design_md.py::TestUploadDesignMdToStitch`** ajustado: la tool legacy `upload_design_md_to_stitch` requiere ahora `contract="inline_prefix_v1"` en `generate_design_md_tool` porque parsea con el schema SpecBox-native (incompatible con el frontmatter M3 por diseño). El path moderno (v6.4.0+) es `stitch_upload_design_md`.

### Versions

- `ENGINE_VERSION.yaml`: 6.4.0 → 6.5.0.
- `pyproject.toml`: 6.4.0 → 6.5.0 con descripción actualizada.
- `CLAUDE.md` header + "Engine Version" alineados a v6.5.0.

### Tests

Suite final: **1316 passed, 71 skipped, 0 failed** (+67 vs v6.4.0).

### Migration

100% backwards-compatible. Comportamientos relevantes:

- **`generate_design_md_tool` cambia default a `native_v2`**. Proyectos nuevos arrancan directamente en M3. Proyectos legacy que dependan del frontmatter SpecBox-native deben pasar `contract="inline_prefix_v1"` explícitamente (sólo `upload_design_md_to_stitch` v5.31 requiere esto — todo lo demás funciona con M3).
- **`stitch_generate_screen_v2`** ahora ignora colors/fonts/roundness del prompt cuando hay DS aplicado. Si el caller necesita el comportamiento viejo, pasar `contract="inline_prefix_v1"` + `design_md_content`.
- **Skill `/visual-setup --migrate-stitch`** es el camino oficial para migrar proyectos existentes. Caso D (Stitch con screens sin DS) por default usa **D.2 retroactive asistido** con preview pre/post + literal `MIGRATE-RETROACTIVE` antes de aplicar.

---

## [6.4.0] - 2026-05-26 — "Stitch Native Migration"

PR-1 de la migración Stitch a la chain nativa post-Google-I/O. **Foundation, no cutover.** Esta release introduce los componentes técnicos (cliente + enums reales + mapper VEG↔M3 + tests) y elimina deuda visible (subsistema de cuota, tools fantasma). La adaptación de `generate_design_md_tool`, `stitch_generate_screen_v2` y la skill `/visual-setup --migrate-stitch` se entrega en una **PR-2 posterior** una vez validado el mapping VEG↔M3 con el mantenedor.

El smoke test contra la API real (incluido en evidencia bajo `.quality/evidence/stitch_smoke/`) confirma 8 de 8 pasos verde para la chain canónica (upload → create_design_system_from_design_md → list → update → apply), validando el contrato técnico del PRD.

Trazabilidad: PRD `doc/prd/stitch_native_migration_prd.md` con 13 UCs (UC-700 a UC-712). PR-1 cubre UC-700 (foundation cliente), UC-701 (tools MCP de design-system), UC-702 (REST batchCreate), UC-703 (mapper VEG↔M3) y UC-708 (quota purge). PR-2 cubrirá el resto.

### Added

- **`server/stitch_enums.py`** — 8 enums sincronizados con `tools/list` del MCP real: `ColorMode` (3v), `ColorVariant` (10v incluyendo `TONAL_SPOT` y `NEUTRAL` que las docs públicas no listan), `Roundness` (6v incluyendo `ROUND_TWO`), `StitchFont` (**65 fonts** vs 9 documentadas públicamente), `DeviceType` (sin `AGNOSTIC`), `CreativeRange`, `VariantAspect`, `ScreenType`.
- **6 wrappers nativos en `server/stitch_client.py`**: `upload_design_md`, `create_design_system`, `create_design_system_from_design_md`, `update_design_system`, `list_design_systems`, `apply_design_system`. Pre-flight validation: rechaza el campo legacy `font` y los campos `x/y/width/height` en `selectedScreenInstances` que el servidor rechazaría con error opaco.
- **`server/stitch_client.py::upload_via_rest_batch_create`** — helper REST `POST /v1/projects/{id}/screens:batchCreate` para DESIGN.md > 5KB, HTML, e imágenes (PNG / JPEG / WebP). Bypassa el límite de output tokens del LLM en el base64 echo de la MCP tool.
- **6 `@mcp.tool` correspondientes en `server/tools/stitch.py`**: `stitch_upload_design_md` (auto-elige MCP vs REST según tamaño), `stitch_create_design_system`, `stitch_create_design_system_from_design_md`, `stitch_update_design_system`, `stitch_list_design_systems`, `stitch_apply_design_system`.
- **`server/veg/material3_mapper.py`** — mapper determinista de los 6 arquetipos VEG (`corporate`, `startup`, `creative`, `consumer`, `gen_z`, `gobierno`) a `Material3Theme`. Resolution order: archetype defaults → JTBD overrides → brand-kit overrides. Función inversa `material3_to_veg_hints` para migration case E.
- **`tests/test_stitch_enums.py`, `tests/test_veg_material3_mapper.py`, `tests/test_stitch_client_native.py`** — 40 tests dedicados pinning enums contra `mcp_tools_schema.json`, validando todas las combinaciones del mapper y los payloads JSON-RPC de los 6 wrappers nuevos.
- **`.quality/evidence/stitch_smoke/`** — 3 scripts Python standalone (`smoke_test.py`, `smoke_test_mcp.py`, `smoke_test_mcp_v2.py`) + 4 reports (Markdown + JSON) + `mcp_tools_schema.json` con los 14 tool schemas reales del servidor. Reusables: `STITCH_API_KEY=... python3 smoke_test_mcp_v2.py` reproduce el verdict.
- **`doc/prd/stitch_native_migration_prd.md`** (615 líneas) — PRD canónico con 13 UCs, evidencia smoke, decisiones (D.2 retroactivo, cutover v7.0), mapping table VEG↔M3, riesgos, orden de ejecución.

### Removed

- **`server/stitch_quota/`** entero (módulo `computation.py` + `__init__.py`). Stitch MCP es free of charge (verificado por la extensión oficial Gemini CLI + smoke v2). La cuota documentada 350+200 corresponde a la UI web, no al MCP.
- **`get_stitch_quota_status` MCP tool** — junto con los imports muertos en `server/tools/stitch_v2.py`.
- **`FlashSafetyNet` strategy** del enum `FallbackStrategy` + parámetros `enable_flash_safety_net` / `flash_model_id` / `flash_safety_net` de `generate_screen_with_fallback` y `stitch_generate_screen_v2`. Degradar a Flash era un workaround para una cuota que no existe.
- **`.claude/hooks/stitch-quota-guard.mjs`** + su entry `PreToolUse` en `.claude/settings.json`.
- **Secciones `quota` y `flash_safety_net`** de `templates/settings.json.template`.
- **`tests/test_stitch_quota.py`** + clase `TestFlashSafetyNet` de `tests/test_stitch_orchestration.py`.
- **2 tools fantasma**: `StitchClient.extract_design_context` y `StitchClient.build_site` + sus MCP wrappers `stitch_extract_design_context` y `stitch_build_site`. No existen en la API del MCP de Stitch (verificado vía `tools/list`); los tests legacy quedaron como assertions de no-existencia.

### Changed

- **`server/stitch_client.py`** — añadido `STITCH_MCP_URL` y `STITCH_REST_BASE` como constantes separadas; `STITCH_BASE_URL` se mantiene como alias backwards-compat para callers externos. Nuevo timeout `DESIGN_SYSTEM_TIMEOUT = 180s` para tools de DS (la latencia real medida es 43s para `create_design_system_from_design_md` y 19s para `apply_design_system`).
- **`templates/settings.json.template`** — añadida zona `stitch.contract` con valor default `native_v2` (proyectos nuevos arrancan en la chain nativa). El valor `inline_prefix_v1` queda como contrato legacy soportado en v6.x; removido en v7.0.
- **`pyproject.toml`** y **`ENGINE_VERSION.yaml`** bumpeados a `6.4.0` "Stitch Native Migration".

### Documentation

- **`CLAUDE.md`** — sección "Stitch MCP Proxy v5.6.0" reescrita en `Stitch MCP Proxy (v6.4.0)`: lista las 14 tools nativas reales, los enums verdaderos (65 fonts, TONAL_SPOT, etc.), elimina las afirmaciones obsoletas ("350 Standard + 200 Experimental por mes", "Stitch MCP no expone endpoint nativo de attach", `AGNOSTIC` en DeviceType).
- **`CHANGELOG.md`** — esta entrada.

### Tests

Suite verde post-cleanup: **1249 passed, 71 skipped, 0 failed** (+57 vs baseline v6.1.1, -3 tests obsoletos eliminados).

### Migration

**Aditivo, no destructivo.** Proyectos onboarded antes de v6.4.0 mantienen `stitch.contract=inline_prefix_v1` (o sin setting alguno) y siguen funcionando sin cambios. Las 6 tools nativas + el mapper + los enums están disponibles para callers nuevos y para la PR-2 que las integrará en `generate_design_md_tool` y `stitch_generate_screen_v2`.

Para usar la chain nativa hoy manualmente:

```python
client = StitchClient(api_key=STITCH_API_KEY)
upload = await client.upload_via_rest_batch_create(
    project_id, content_bytes=design_md.encode(), mime_type="text/markdown"
)
inst = upload["screenInstances"][0]
ds = await client.create_design_system_from_design_md(
    project_id, selected_screen_instance={"id": inst["id"], "sourceScreen": inst["sourceScreen"]}
)
await client.apply_design_system(project_id, ds["assetId"], [{"id": s, "sourceScreen": ss} for ...])
```

Cutover duro previsto para v7.0: el contrato `inline_prefix_v1` se eliminará y `upload_design_md_to_stitch` operará exclusivamente sobre la chain nativa. Documentado en el PRD bajo "Backwards compat strategy".

---

## [6.1.1] - 2026-05-25 — "Cutover Followup"

Patch release que cierra 11 residuos identificados tras v6.1.0 (Cloud Cutover). La pieza más grave era la tool MCP `get_sala_de_maquinas` que seguía registrada y expuesta — un cliente que la llamase recibía datos vivos en vez del esperado tool-not-found. Sumado a docstrings, menciones en skills, canónicos `doc/app/` desactualizados, entradas huérfanas en VSCode extension y `ENGINE_VERSION.yaml` features array. Cero código nuevo, sólo deletes + cleanup de strings.

Trazabilidad: US-CUTOVER-FOLLOWUP → UC-625..UC-633 → 26 ACs en backend FreeForm `ff-ed0c02f4565a`. PRD en `doc/prd/US-CUTOVER-FOLLOWUP_prd.md`, plan en `doc/plans/US-CUTOVER-FOLLOWUP_plan.md`.

### Removed

- **Tool MCP `get_sala_de_maquinas`** — el gran agujero del cutover. 177 LoC eliminadas de `server/tools/state.py`. Los helpers privados (`_read_registry`, `_filter_by_days`, `_read_jsonl`, `_read_meta`, `_compute_e2e_trend`) se preservan porque las tools `report_*` los siguen usando (UC-625).
- **Línea en `server/server.py:135`** "View the Sala de Máquinas global dashboard..." del FastMCP `instructions` string (UC-625).
- **Fila Dashboard React + fila Dashboard Vite** de la tabla Stack en `doc/app/app_spec.md`. Apuntaban a `server/dashboard/package.json` que ya no existe (UC-629).
- **Entry `sala-de-maquinas-embedded`** del array `features:` en `ENGINE_VERSION.yaml` (UC-630). Array `commits:` histórico preservado.
- **VSCode extension command `specbox.openDashboard` + setting `specbox.dashboardUrl`** + 3 líneas de `src/extension.ts`. Las 5 capacidades restantes (install / healthCheck / onboard / showStatus / configureMcp) + sidebar trees (status / skills) intactas (UC-632).

### Changed

- **Docstrings Python** reescritos para apuntar a "consumidores externos (specbox_cloud, scripts ad-hoc)" en vez de a Sala de Máquinas específicamente (UC-626):
  - `server/tools/benchmark.py::generate_benchmark_snapshot`
  - `server/audit/persistence.py` module docstring
  - `server/app_docs/drift_detector.py` module docstring + `app_docs_drift_for_heartbeat` tool docstring
- **Docstrings Node hooks** mismo cleanup (UC-627):
  - `.claude/hooks/app-docs-sync-guard.mjs`
  - `.claude/hooks/context-budget-guard.mjs`
- **Skills body** (frontmatter intacto) reescriben menciones a "consumidores externos (specbox_cloud)" (UC-628):
  - `.claude/skills/plan/SKILL.md:584`
  - `.claude/skills/audit/SKILL.md:61`
  - `.claude/skills/discovery/SKILL.md:414`
- **Canónicos `doc/app/`** (UC-629):
  - `app_spec.md` versión doc 1 → 2; tabla Stack actualizada (Engine package 5.33.0 → 6.1.x; Contenedor multi-stage → single-stage Python); zona brand_visual menciona specbox_cloud en vez de "salvo Sala de Máquinas"
  - `app_prd.md` versión doc 1 → 2; zona vision menciona specbox_cloud y elimina "164 tools + Sala de Máquinas"; zona scope v1 actualizada
- **VSCode extension** bumped 5.21.0 → 5.21.1 (UC-632).
- **`.claude/settings.local.json`** (gitignored, local-only): entrada `mcp__specbox-engine__get_sala_de_maquinas` eliminada del array de allowedTools (UC-631).

### Documentation

- **`doc/decisions/cloud_cutover.md`** recibe sección final "v6.1.1 followup" documentando que la deuda residual quedó cerrada en esta release (UC-633).
- **`doc/prd/US-CUTOVER-FOLLOWUP_prd.md`** (370 LoC) — PRD técnico con 9 UCs, 26 ACs, Definition Quality Gate aprobado.
- **`doc/plans/US-CUTOVER-FOLLOWUP_plan.md`** (244 LoC) — plan de implementación por fases.

### Tests

Suite verde sin cambios numéricos: **1192 passed, 71 skipped, 0 failed** (idéntico a baseline v6.1.0). Node `node:test` lib tests 15/15 verde.

### Migration

Cero acción requerida para proyectos onboarded. La tool `get_sala_de_maquinas` eliminada no era invocada por specbox_cloud (que lee Supabase directo). Las menciones residuales en proyectos cliente (si las hay en su `.claude/settings.local.json`) se ignoran silenciosamente: tool deregistrada = no aparece en discovery.

## [6.1.0] - 2026-05-25 — "Cloud Cutover"

Minor release que **elimina la "Sala de Máquinas"** — dashboard global multi-proyecto que vivía dentro del MCP server (frontend React + REST API + heartbeats + GitHub sync + skill `/remote`). La función de panel multi-proyecto la absorbe **specbox_cloud** (panel web externo), que lee directamente la instancia Supabase del Native Backend y llama al MCP para escrituras de coordinación (`reserve_uc` / `release_uc`). Reduce ~3.800 LoC de código vivo + ~237k LoC de `node_modules`, deja el Dockerfile single-stage Python (sin Node), apaga el VPS `mcp-specbox-engine.jpsdeveloper.com` y su dominio.

### Removed

- **Frontend dashboard** — `server/dashboard/` completo (React 19 + Vite + Tailwind + Recharts, ~1.800 LoC TSX/TS).
- **Backend HTTP** — `server/dashboard_api.py` (877 LoC, 16 endpoints REST: `/api/sala`, `/api/projects`, `/api/heartbeat`, `/api/sync/github`, etc.) y `server/github_sync.py` (225 LoC).
- **MCP tools** — `get_project_live_state`, `get_all_projects_overview`, `get_active_sessions`, `refresh_project_state`, `get_heartbeat_stats`.
- **Hooks** — `heartbeat-sender.mjs` (231 LoC), `mcp-report.mjs` (29 LoC), `e2e-report.mjs` (59 LoC), `lib/http.mjs` (144 LoC, cliente MCP HTTP).
- **Hooks legacy** — `legacy-bash/{heartbeat-sender,mcp-report,e2e-report,on-session-end,implement-checkpoint}.sh`.
- **Skill** — `/remote` (wrapper conversacional para OpenClaw / WhatsApp / Discord).
- **Tests** — `test_dashboard_api`, `test_github_sync`, `test_heartbeat`, `test_heartbeat_stats`, `test_live_state`, `test_remote_summaries`.
- **Artefacto en repo** — `specbox-state.json` en la raíz (era live state pero se commiteaba a `main`).
- **Env var** — `SPECBOX_SYNC_TOKEN` deja de tener sentido en cualquier lado.
- **Dockerfile Stage 1** — `dashboard-builder` (Node 20-slim) ya no existe; build single-stage Python.

### Changed

- **`server/server.py`** ahora expone una única `@mcp.custom_route("/health")` mínima (status + version) para que el `HEALTHCHECK` del Dockerfile siga funcionando. Sin telemetría, sin live state.
- **`on-session-end.mjs`** y **`implement-checkpoint.mjs`** dejan de hacer `spawn` a los hooks de heartbeat / mcp-report. La telemetría local (`.quality/logs/`, Engram save) sigue intacta.
- **`/handoff` skill** ya no menciona heartbeat en su mensaje final ni en su sección de idempotencia.
- **`/implement` skill** ajusta los dos docstrings que mencionaban `heartbeat-sender.mjs` y "Sala de Máquinas".
- **`CLAUDE.md`** reescrito: header sin "176 tools" ni "Sala de Máquinas dashboard"; tabla de skills sin `/remote`; tabla de hooks sin `heartbeat-sender` / `mcp-report` / `e2e-report`; secciones "Remote Telemetry (v3.3)" y "Remote State Management (v5.6.0)" reemplazadas por una sección "Cross-project state (v6.1.0 Cloud Cutover)" que documenta el cambio y apunta a specbox_cloud.
- **`README.md`** drops 2 menciones de "Sala de Máquinas" (ES + EN) en la sección v5.32.0.
- **`install.sh`** drops `/remote` del echo final de skills instaladas.
- **`pyproject.toml`** versión 6.0.2 → 6.1.0 + nueva descripción.
- **`ENGINE_VERSION.yaml`** versión 6.0.2 → 6.1.0 + codename "Cloud Cutover".

### Preserved

- **NativeBackend on Supabase** (`server/backends/native_backend.py` 1.260 LoC + `server/db/` + `server/coordination/`) intacto. specbox_cloud lee la misma instancia.
- **Tools de coordinación** (`whoami`, `reserve_uc`, `release_uc`, `register_native_branch`) intactas — son la API que specbox_cloud llama para escrituras.
- **Audit log + audit submit** (`submit_quality_audit`, `attach_audit_evidence`) intactos.
- **Engram local save** en `on-session-end.mjs` se mantiene.

### Migration

Proyectos onboarded en v5.x con los 3 hooks `.mjs` viejos en su `.claude/hooks/` **siguen funcionando**: los `spawn` desde `on-session-end.mjs` y `implement-checkpoint.mjs` ahora fallan silenciosamente con `ENOENT` (los archivos ya no existen en el engine) y el resto del hook continúa. Para limpiar a fondo: re-ejecutar `./install.sh` desde v6.1.0 o borrar manualmente los `.mjs`.

Si alguien tiene `SPECBOX_SYNC_TOKEN` o `SPECBOX_ENGINE_MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp` exportados, puede borrar el primero (ya no se lee en ningún sitio) y debe cambiar el segundo a `stdio` local o al endpoint MCP que provea specbox_cloud — la URL del VPS deja de responder cuando se apague el servicio.

### Documentation

- **`doc/decisions/cloud_cutover.md`** — decisión arquitectural completa con contexto, rationale, consecuencias, riesgo (no duplicar escrituras de reservations en specbox_cloud) y rollback plan.

### Tests

Suite: `1243 passed → 1192 passed` (-51 tests, todos del dominio eliminado). 71 skipped, 0 failed. Node `node:test` lib tests: 15/15 verde.

## [6.0.2] - 2026-05-25 — "Smoke Test Followups"

Patch release que cierra los 3 issues abiertos descubiertos durante el smoke test de v6.0.1 (#60, #61, #62) y elimina el último hardcodeo de versión runtime que sobrevivía en `server/server.py` desde v5.29. Bumpea también `fastmcp 3.1.0 → 3.3.1` con pin upper-bounded para evitar saltos major silenciosos. Cero cambios de comportamiento para tools no-deprecadas.

### Added

- **`submit_quality_audit` autogenera `audit_id`** (issue #61). Cuando el cliente no incluye `audit_id` en el `report` payload, el server lo genera con `new_audit_id()` (formato `audit_YYYYMMDDTHHMMSSZ`). Si el cliente quiere idempotencia, puede seguir pasando su propio `audit_id` y el server lo respeta verbatim. Documentado en el docstring de la tool.
- **`drift.kind` en respuesta de `validate_discovery_completeness`** (issue #62). Cuando el parser encuentra la resolución, expone qué resolución matcheó (`feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`). Habilita futuros gates estrictos sin requerir otro release.
- **Sección "Smoke Test Followups (v6.0.2)" en CLAUDE.md** documentando los cambios + bug latente eliminado.
- **Caso (d) `no_drift` en `.claude/skills/discovery/SKILL.md`** Paso 3, con enumeración explícita de las 4 resoluciones canónicas.
- **9 tests nuevos**:
  - `tests/test_discovery_content_api.py::TestDriftResolutionParsing` (6 casos): 4 resoluciones + alias legacy `no drift detected` + pending.
  - `tests/test_audit_content_api.py::TestSubmitQualityAudit::test_audit_id_autogenerated_when_missing`
  - `tests/test_audit_content_api.py::TestSubmitQualityAudit::test_audit_id_respected_when_provided`
  - `tests/test_server.py::TestServerSetup::test_engine_version_read_from_yaml_not_hardcoded`

### Changed

- **`run_quality_audit` deprecation shim ahora `raise RuntimeError`** (issue #60). Cuando se invoca sin `report`, lanza excepción → MCP envelope con `isError=true`. Antes devolvía `dict {error: ..., migration: ...}` con `isError=false`, lo cual era un silent success para clientes que solo inspeccionaban el envelope. El mensaje de la excepción incluye replacement, scope requested, y project_path requested para que el cliente migre fácilmente.
- **`validate_discovery_completeness` parser acepta 4 resoluciones canónicas** en lugar de 3 (issue #62). Añadido `no_drift` (forma canónica). Alias legacy `no drift detected` (con espacios) se sigue aceptando y se normaliza a `no_drift` en la respuesta.
- **`server/server.py` lee la versión de `ENGINE_VERSION.yaml`** al cargar el módulo via nuevo helper `_load_engine_version()`. Antes era `"v5.29.0"` hardcoded en `FastMCP(instructions=...)`, lo cual drifteaba en cada release y los clientes MCP veían una versión incorrecta. Mismo patrón que `dashboard_api._health_version`. Module docstring banner también desacoplado de versión concreta.
- **`fastmcp >=3.0.0 → >=3.3.1,<4.0.0`** en `pyproject.toml`. Bump a latest stable (2026-05-15, security hardening). Pin upper-bounded.
- **CLAUDE.md tool count corregido** de `167`/`159` (stale) → `176` (real, medido via `mcp.list_tools()`).
- **`tests/test_audit_content_api.py` helper `_build_minimal_report`** reescrito sin dependencia de `QualityReport.empty()` (que nunca existió). Esto unskippea 3 tests previos.
- **`tests/test_audit_content_api.py::test_no_report_returns_deprecation`** renombrado a `test_no_report_raises_for_iserror_envelope` y reescrito para validar el nuevo comportamiento.

### Fixed

- **Bug latente eliminado**: `submit_quality_audit.fn(...)` en `run_quality_audit` siempre lanzaba `AttributeError` desde el closure local. No estallaba en producción porque el único test que lo cubría estaba `pytest.skip`-eado por la dependencia de `QualityReport.empty()`. Refactor a llamada directa `submit_quality_audit(project=project, report=report)`.

### Decisions

- **Patrón consistente para versión runtime**: ningún módulo del server debe hardcodear el string de versión. La única source of truth es `ENGINE_VERSION.yaml`, leída al cargar el módulo. Patrón canónico: `dashboard_api._health_version` y nuevo `server._load_engine_version()`.
- **`audit_id` autogenerado server-side por defecto** (opción 3 del issue #61, recomendación del propio issue): cliente sin requisito de idempotencia obtiene comportamiento "just works"; cliente con requisito puede opt-in pasando su propio `audit_id`. Ningún cambio breaking para callers existentes.
- **`run_quality_audit` deprecation no se elimina aún**: queda como `raise` shim para que clientes que lo invoquen en producción reciban señal correcta de migración via `isError=true`. Eliminación formal planeada para v6.1 junto con la limpieza de las defensas v5.29 de FreeForm que ya están en deuda.
- **PR aislada para el bump de fastmcp** (chore #63) separada del PR de fixes (fix #64). Si el bump introdujera regresión, se revierte solo el bump sin tocar los fixes de los 3 issues.

### Compatibility

- 100% backwards-compatible. Clientes calling `submit_quality_audit` sin `audit_id` ahora succeed (antes erraban con `Invalid report payload: 'audit_id'`). Clientes solo inspeccionando MCP `isError` en `run_quality_audit` deprecation ahora detectan correctamente la deprecación. No hay schema changes — `QualityReport.from_dict` sigue aceptando el mismo shape.
- `fastmcp 3.3.1` no requiere ajustes de código consumido por nuestras tools. Las 176 tools registradas siguen funcionando idénticas. Pin upper-bounded `<4.0.0` previene saltos major silenciosos.
- README + CLAUDE.md no afectan runtime — son documentación.

### Tests

- **Suite final: 1243 passed / 71 skipped / 0 failed** en 28.5s (vs baseline post-bump 1232/73/0).
- +11 passed: 6 nuevos TestDriftResolutionParsing + 2 nuevos audit_id + 1 nuevo engine_version + 2 unskippeados (al reparar fixture).
- -2 skipped: los `pytest.skip` antes ocultos ahora corren.
- Smoke import: `from server.server import mcp, _ENGINE_VERSION` carga OK, 176 tools, `instructions` contiene `v6.0.2` leído del YAML.
- Pre-existing failures on `main` documentados en releases previas permanecen y son no relacionados.

## [6.0.1] - 2026-05-25 — "MCP Path Contract"

**Hotfix arquitectural.** v6.0.0 introdujo `/discovery` y el registro multi-doc canónico, pero la prueba con MCP remoto (`SPECBOX_ENGINE_MCP_URL=...`) reveló un bug arquitectural latente: **17 tools cat A en `server/tools/`** resolvían `Path(project_path).resolve()` contra el filesystem del proceso MCP server, no del cliente. En MCP remoto las tools leían/escribían el VPS en vez del repo del usuario, devolviendo datos falsos sin error visible.

v6.0.1 migra las 17 tools a un patrón **content-passing universal**: el cliente lee los archivos localmente, pasa el contenido como string, y escribe cualquier artefacto que la tool devuelva. Las tools quedan filesystem-agnósticas — funcionan idéntico en stdio (local), HTTP/SSE remoto (VPS, claude.ai web) y futuros entornos multi-tenant.

### Added

- **Content-passing API en 17 tools cat A** (`server/tools/`):
  - `discovery.py`: `start_discovery(feature_name, app_market_content, existing_artifact_content, mode)`, `validate_discovery_completeness(feature_name, icp_jtbd_content)`, `detect_v60_migration_case(app_prd_content, app_spec_content, app_market_content, settings_local_json_content, active_uc_present, pending_critical_feedback, has_discovery_dir, has_app_dir)`.
  - `app_docs.py`: `read_app_docs_tool(app_prd_content, app_spec_content)`, `get_inheritable_values_tool(app_prd_content, app_spec_content)`.
  - `onboarding.py`: `detect_project_stack(project_name, marker_files_present, dep_files, feature_dirs_present)`, `get_onboarding_status(project_name, artifact_presence)`, `get_visual_gap_report(settings_local_json_content, artifact_presence, has_design_htmls, has_veg_base_files)`.
  - `acceptance.py`: `run_acceptance_check(prd_content, item_id, branch, code_index)`, `get_acceptance_report(uc_id, report_json_content, report_md_content)`, `get_e2e_gap_report(prd_content, project_name, stack, evidence_index, feature_files, acceptance_check_ucs, code_index)`.
  - `audit.py`: `check_audit_tools_status(stack)`, **nueva** `submit_quality_audit(project, report)`; `run_quality_audit` queda como shim deprecado.
  - `hints.py`: `get_skill_hint(skill_name, current_counter, completed_uc_count)`, `record_skill_hint(skill_name, counters)` (devuelve `updated_counters` para que el cliente escriba).
  - `skill_registry.py`: `list_skills_v2(project_local_manifests)`, `discover_skills(stack, keywords, project_local_manifests)`, `validate_skill_manifest(manifest_yaml_content)`.
  - `telemetry.py`: `get_context_budget(file_inventory, context_window_tokens)` — calcula tokens sobre byte counts proveídos por el cliente; no invoca scripts shell.
  - `benchmark.py`: `generate_benchmark_snapshot()` devuelve `markdown_content` + `suggested_relpath`; el cliente escribe el archivo.
  - `evidence_regen.py`: `regenerate_evidence(prd_content, uc_evidence_inputs, ucs, branch)` devuelve un plan + `report_content` para `doc/migrations/regenerate-evidence-<ts>.md`.

- **`.claude/hooks/lib/mcp-client-io.mjs`** (UC-621): helper Node.js cliente con `resolveProjectRoot()`, `readContentBundle(paths)`, `writeContentBundle(bundle)`. Implementa path-traversal guard + rechazo de paths absolutos. Tests: 15 casos en `mcp-client-io.test.mjs` corriendo con `node:test`.

- **`.quality/scripts/audit/README.md`** (UC-618): documenta el plan de mover los 8 analizadores SQuaRE al cliente (porting completo programado para v6.0.2).

- **6 archivos de tests nuevos** (~120 casos): `test_discovery_content_api.py`, `test_app_docs_content_api.py`, `test_onboarding_content_api.py`, `test_acceptance_content_api.py`, `test_misc_cat_a_content_api.py`, `test_audit_content_api.py`.

### Changed

- **7 skills actualizadas** (UC-622) para reflejar el nuevo contrato: `/discovery`, `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check`. El patrón es leer ficheros locales con `Read`, pasar el contenido al MCP, escribir las respuestas con `Write`.

- **`tests/test_acceptance_check.py`** re-targeted a `run_acceptance_check_impl` / `get_acceptance_report_impl` (los helpers Path-based in-process siguen vivos para callers internos como `evidence_regen.py`).

- **Defensas v5.29 de FreeForm**: el hook `freeform-path-guard.mjs` y `FreeformPathError` siguen vivos. Eliminación formal planeada para v6.1.

### Fixed (32 fallos pre-existentes en main, UC-624)

- `tests/test_spec_mutations.py` y `tests/test_milestone_management.py`: `InMemoryBackend` mock recibió `archive_item` stub que faltaba tras la adición del método abstracto al `SpecBackend` ABC en v5.34. 26 errors → 26 PASS.
- `tests/test_server.py`: 4 aserciones stale eliminadas (esperaban 21 tools / nombre `dev-engine-trello`); reemplazadas por checks dinámicos (≥100 tools, foundational set presente, nombre `specbox-engine`).
- `tests/test_server_main.py`: aserción `test_main_invalid_transport_defaults` ajustada (el default real es `stdio`, no `streamable-http`).
- `tests/test_quickstart.py::test_skill_frontmatter_has_required_fields`: `triggers:` añadido al frontmatter de `quickstart/SKILL.md`.

### Breaking changes (intencional, sin compatibilidad pre-v6.0.1)

Las 17 tools cat A cambiaron firma sin deprecation warnings. v6.0 llevaba <24h en main; la superficie de uso externo es mínima. Los únicos consumidores reales del engine — los skills — se migran en este mismo release.

### Compatibility

100% backwards-compatible para callers **in-process** (otros módulos Python del propio MCP):
- Los helpers Path-based `read_app_docs(project_path)` / `get_inheritable_values(project_path)` siguen vivos en `server/tools/app_docs.py`.
- `run_acceptance_check_impl` / `get_acceptance_report_impl` siguen siendo la API in-process en `server/tools/acceptance.py`.
- Los Path-based `_detect_v60_case(project_path)` / `_app_market_is_pristine_or_missing(project_path)` siguen disponibles en `server/tools/discovery.py`.

### Test results

`pytest tests/ -q` → **1232 passed, 73 skipped, 0 failed, 0 errors**. Pre-v6.0.1: 1103 passed, 6 failed, 26 errors.

### Decisión arquitectural

`doc/decisions/mcp_path_contract.md` documenta las alternativas consideradas y por qué se eligió content-passing universal sobre absolute-path-only o convivencia híbrida.

### Plan técnico

`doc/plans/v6.0.1_mcp_path_contract_plan.md` — fases, dependencias entre UCs, métricas de éxito, rollback plan.

---

## [6.0.0] - 2026-05-25 — "Discovery Foundations"

**Release stable, no experimental.** Introduce el módulo permanente de **Product Discovery** integrado en el pipeline canónico + la **fundación arquitectural multi-doc** que sostiene la extensión a N documentos canónicos en futuras versiones (v6.x+).

### Added

**Product Discovery (US-D01 + US-D02 parcial + US-D03 parcial)**

- **`/discovery <feature_name>`** — slash command nuevo con flujo conversacional de 3 fases (ICP identification, JTBD extraction, validation gate). Produce `doc/discovery/<feature>/icp_jtbd.md` como espinazo trazable que viaja con la feature hasta los AC del PRD, las UC del plan y los tests E2E.
- **Modo bootstrap** (UC-D002): cuando `app_market.md` está vacío/ausente, el flujo primero rellena el doc nivel producto (ICPs canónicos, no-ICPs, JTBDs globales racionales y emocionales, NSM, posicionamiento, anti-features) y después desciende al nivel feature.
- **Pedagogical layer**: micro-justificaciones por concepto, ejemplos del ecosistema (PaddockManager / McProfit / Futbase / SpecBox), anti-patterns explícitos. Progressive onboarding: expanded primeras 5 features, conciso después.
- **Drift detection** (UC-D004 parcial): durante Phase 3 del flujo `/discovery`, compara los ICPs/JTBDs declarados contra `app_market.md` y obliga resolución 3 vías por elemento nuevo: `feature_creep_rejected` (cancela feature) / `app_market_updated` (actualiza producto) / `documented_exception` (excepción justificada).

**Multi-doc canonical registry (US-D04 — Foundation arquitectural permanente)**

- **`server/app_docs/registry.py`** — NEW: `CanonicalDoc` dataclass + `CANONICAL_DOCS` list (3 entries: `app_prd` 5.29, `app_spec` 5.29, `app_market` 6.0.0). Source-of-truth única para qué docs canónicos existen, en qué versión se introdujeron, qué zonas requieren, qué eventos los mutan.
- **`templates/canonical_docs.json`** — NEW: descriptor JSON regenerado desde Python (`registry.py`) por `.quality/scripts/regenerate-canonical-docs-json.py`. Consumido por el hook Node.js. CI valida sincronización (test `test_canonical_docs_sync.py`).
- **`templates/app_market.md.template`** — NEW: plantilla nivel producto con 8 zonas (7 manual con `status="template-pristine"`, 1 auto `exportable_copy`). Creada automáticamente por `upgrade_project` en proyectos cuyo `engine_version_at_onboard < 6.0.0`.
- **Marcador `status="template-pristine"`**: zonas vacías de plantilla recién creada no producen warnings de drift hasta que el usuario las rellena (vía `/discovery` o `/app-init`). El parser de zonas (`server/app_docs/zones.py`) extrae el atributo; sync y hook lo respetan.
- **`engine_version_at_onboard`**: nuevo campo en `meta.json` capturado por `onboard_project` y preservado por `upgrade_project`. Proyectos v5.x preexistentes sin el campo → política conservadora `"unknown"` (verifier solo chequea docs con `introduced_in <= 5.29.0`).
- **`/app-init` y `/app-sync`**: respetan `app_market.md` automáticamente vía el registry. Sin modificar ningún skill.

**MCP tools nuevos (3)**

- **`start_discovery(feature_name, project_path, mode="auto")`** — inicializa/resume artefacto Discovery, idempotente, auto-detecta bootstrap vs standard.
- **`validate_discovery_completeness(feature_name, project_path)`** — verifica las 5 secciones del `icp_jtbd.md`, devuelve verdict `READY_FOR_PRD` o `DISCOVERY_INCOMPLETE` con missing específicos.
- **`detect_v60_migration_case(project_path)`** — clasifica el proyecto en uno de 8 casos del PRD §4.8. Análogo a `detect_v529_migration_case`. Priority-ordered: `case_3_active_uc` y `case_4_pending_feedback` chequean primero (deferral si en curso).

**Hooks**

- **`pre-prd-discovery-check.mjs`** — NEW: PreToolUse hook que intercepta `/prd` invocations. 3 modos: `off` (default upgrade), `warn` (default fresh-clone v6.0), `block` (opt-in power users). Bypass automático en spec-driven (`US-XX`, `UC-XXX`, `board:ID`). Telemetría a `.quality/discovery_gate_events.jsonl`.
- **`app-docs-sync-guard.mjs`** — REFACTOR: itera sobre `templates/canonical_docs.json` con fallback graceful a `app_prd`+`app_spec` hardcoded si descriptor falta (proyectos v5.x). Filtra por `engine_version_at_onboard` para no warnear sobre docs no introducidos aún. Respeta `template-pristine`.

**Refactorizaciones internas (no breaking)**

- `server/app_docs/sync.py`: `verify_app_docs_in_sync`, `record_sync_signature`, `EVENT_ZONE_MAP` ahora iteran sobre `CANONICAL_DOCS`. Constantes `PRD_PATH`/`SPEC_PATH` eliminadas. Backwards compat: `SyncResult.prd_signature`/`spec_signature` preserved + nuevo `signatures: dict[doc_id, str]`.
- `server/tools/onboarding.py`: `upgrade_project` extendido con `_collect_canonical_doc_templates` helper. Devuelve `canonical_docs_to_create: list[dict]` y `discovery_alignment` hint sin modificar archivos existentes. `onboard_project` captura `engine_version_at_onboard` en `meta.json`.

### Changed

- **`get_engine_version` → `"6.0.0"`** codename `"Discovery Foundations"`.
- Server description en `pyproject.toml` refleja v6.0.0 con 167 tools (164 v5.34 + 3 nuevos).

### Decisions resolved

11 open decisions del PRD §11 resueltas. Las nuevas (introducidas por US-D04):
- **D-09**: PR atómica para el refactor multi-doc (mergeada como PR #55 + cadena).
- **D-10**: Python source-of-truth + JSON regenerado (CI verifica sync).
- **D-11**: `engine_version_at_onboard` `"unknown"` con política conservadora (no inferir).

Las 8 originales resueltas en commits previos (PRD §11).

### Backwards compatibility

- ✅ Proyectos v5.29-v5.35: `engine_version_at_onboard < 6.0.0` → hook ignora `app_market.md`. Sin cambio de comportamiento perceptible.
- ✅ Proyectos sin `engine_version_at_onboard` en meta: tratados como `"unknown"` → política conservadora.
- ✅ Hook fallback: si `canonical_docs.json` falta, vuelve a hardcoded `app_prd+app_spec`.
- ✅ Plantillas `template-pristine` no producen warnings.
- ✅ Invariante "upgrade_project nunca pisa contenido existente" preservada — solo CREA archivos nuevos.
- ✅ API externa preservada: tools v5.29 funcionan con su signatura previa.

### Deferred to v6.0.1 / v6.1

- AC-D003-02, AC-D003-03, AC-D003-05, AC-D003-07: integración full de `/discovery` con skills globales `/prd`, `/plan`, `/implement`. Contrato documentado en `SKILL.md` de discovery; promoción cuando v6.0 sea stable.
- AC-D004-05: hook `verify_app_market` drift sistemático → v6.0.1.
- AC-D004-06: `/discovery --review` dashboard → v6.1 (D-08).

### Documentation

- **`doc/decisions/multi_doc_registry.md`** — NEW: documento arquitectural completo sobre por qué multi-doc, qué patrón se eligió, qué se descartó (subclasses, plugins), cómo extender en futuras versiones.
- **`doc/prd/discovery_module_v6_prd.md`** — PRD v6.0.0 stable con 4 US, 6 UCs, 47 ACs, 11 decisions resueltas.
- **`doc/plans/discovery_foundations_plan.md`** — plan consolidado para los 6 UCs con sub-fases, mapping AC→Fase, 5 riesgos adicionales identificados.

### Tests

- 111 tests nuevos verdes:
  - 13 multi-doc registry regression
  - 3 canonical_docs Python↔JSON sync
  - 15 product_discovery tools (start, validate, detect_v60_case, 8 cases)
  - 13 pre-prd-discovery-check hook
  - Plantillas, drift detection, byte-by-byte preservation v5.35→v6.0 fixture
- Regresión 0 en suite app_docs existente (73 tests verdes pre y post refactor).

### Beta validation period

Post-release validation (4 semanas) con 5 power users:
- Jesús (ICP-1) — McProfit + Futbase
- Valentín Ayesa (ICP-2) — flow propio
- Nani (ICP-3) — test pedagógico crítico
- Julio Fariñas (ICP-1) — Tempo
- Ramón Iborra (ICP-1/2) — landing/marketing

Safety net: si ≥3/5 dicen "no aporta", marcar Discovery feature como "needs UX redesign". **Multi-doc Foundation queda en pie en cualquier caso** — es base arquitectural permanente.

### PRs (cadena de merge)

- PR #55 — UC-D005 + UC-D006: Foundation multi-doc + app_market.md
- PR #56 — UC-D001 + UC-D002: Product Discovery flow (basada en PR #55)
- PR #57 — UC-D003 + UC-D004 (parcial): Gate hook + drift detection (basada en PR #56)
- PR #58 (esta): v6.0.0 version bump + CHANGELOG + CLAUDE.md (basada en PR #57)

Orden recomendado de merge: #55 → #56 → #57 → #58.

---

## [5.34.1] - 2026-05-23 — "Native Collaboration" (patch)

Patch sobre v5.34.0 que extiende y blinda la misma línea Native: ahora un
proyecto puede **cambiar de backend de tracking de forma guiada entre los 4
backends (FreeForm/Trello/Plane/Native)** sin perder datos ni avance, y el
**Native Backend queda blindado contra mutaciones de identidades revocadas**
con una ventana de exposición ≤ 30s y un audit log forense de operaciones
destructivas. Cierra US-BACKEND-SWITCH (UC-401..406) y US-NATIVE-SECURITY
(UC-501..506). 13 PRs (#34–#46).

### Added

- **`server/migration/` paquete nuevo** — `backend_dispatch` (build_backend
  de los 4) + `writer` (write_target genérico, aditivo, idempotente vía
  external_id) + `state_mapping` (matriz canónico↔nativo bidireccional;
  Plane es el único *lossy*, las degradaciones se reportan como warnings
  estructurados en vez de perderse en silencio) + `native_handling`
  (salida Native descarta claims/identidad con reporte, entrada Native
  siembra `expected_version=1` + identidad) + `transactional_switch`
  (snapshot + rollback sobre los 3 lugares de verdad).
- **Tool MCP `migrate_backend(source_type, source_id, target_type,
  target_id?, dry_run=True)`** — migración N×N entre los 4 backends,
  aditiva e idempotente. Reemplaza el `migrate_project` solo-Trello-Plane.
- **Tool MCP `switch_backend` generalizada a los 4** con actualización
  atómica de `projects.json` + zona `tracking_backend` de `app_spec.md` +
  `specbox.backend_type` en `settings.local.json`, con rollback completo
  si alguno falla.
- **Tool MCP `regenerate_evidence(project, ucs?)`** — opt-in
  post-migración. Reescanea `.quality/evidence/*/acceptance/results.json`
  (indexada por `uc_id` lógico) y reejecuta acceptance por UC, con progreso
  `[X/N] UC-XXX: PASS|FAIL|SKIP (n ACs)` y reporte persistido en
  `doc/migrations/evidence_regeneration_{ts}.md`.
- **Skill `/switch-backend`** (`.claude/skills/switch-backend/`,
  `context: direct`) — orquestador guiado: detecta backend actual → pide
  credenciales del destino de forma segura (Native vía
  `SPECBOX_NATIVE_DSN` env, jamás por chat) → preview obligatorio →
  confirmación literal → migra → switch transaccional → reporte final
  de 4 secciones. Documenta la precondición de MCP local.
- **Mutation gate con cache TTL 30s** en `authenticate_and_authorize_cached`
  (constante de módulo `_CACHE_TTL_SECONDS = 30`, hardcoded). Aplicado a
  los 9 mutadores del NativeBackend (`create_item`, `update_item`,
  `archive_item`, `mark_acceptance_criterion`, `create_acceptance_criteria`,
  `update_acceptance_criterion`, `delete_acceptance_criterion`,
  `add_comment`, `add_attachment`). Cache hit ~1µs, miss ~10-25ms.
  Lecturas bypassan el gate por diseño (forensics + whoami preservados
  para tokens revocados).
- **`audit_log`** (migración `0006`) — registro forense de las 2
  operaciones destructivas (`delete_acceptance_criterion`, `archive_item`).
  Campos: `developer_id`, `project_id`, `operation`, `target_id`,
  `occurred_at`. Sin diff antes/después: la recuperación se hace desde
  backups de Supabase, no desde el audit.
- **Modelo de identidad rediseñado** — `developers` + `github_identities`
  (N:1 al developer, cubre caso freelance con varias cuentas GitHub;
  `github_user_id BIGINT` como PK estable que sobrevive a renames) +
  `mcp_tokens` (revocable vía `revoked_at`, sin TTL, emitido solo por el
  panel). Migraciones `0004_github_identities.sql` + `0005_mcp_tokens.sql`
  (dropea `developers.token_hash` atómicamente en el mismo archivo).
- **Helpers internos** `register_mcp_token` (idempotente vía
  `ON CONFLICT (token_hash)`) y `revoke_mcp_token` en
  `server/coordination/identity.py`. NO se exponen como tools MCP — los
  usa el panel y los fixtures de tests.

### Changed

- **`NativeBackend.__init__(project_id, dev_token)`** — ambos argumentos
  obligatorios. Empty / `None` → `ValueError` desde el constructor.
- **`auth_gateway.get_session_backend`** rama native ahora lee
  `config["dev_token"]` y lo reenvía al constructor.
- **`store_native_credentials` + `set_auth_token` rama native** rechazan
  `dev_token` vacío con `MISSING_DEV_TOKEN`.
- **`resolve_developer`** ahora consulta
  `mcp_tokens t JOIN developers d ON d.developer_id = t.developer_id WHERE
  t.token_hash = $1 AND t.revoked_at IS NULL`. Un revoke desde el panel
  hace fallar `UnauthenticatedError` la siguiente cache miss del MCP.
- **`register_developer`** firma reducida a `(*, developer_id,
  display_name)` — la emisión de tokens es responsabilidad del panel
  (helper `register_mcp_token` separado).
- **Renderer `tracking_backend` de `server/app_docs/sync.py`** y
  `_extract_backend_from_spec` de `server/app_docs/discovery.py`
  extendidos a `native` (paridad de los 4 backends).
- **Suite de conformance Native** (`test_native_backend_conformance.py`):
  fixture refactorizada para crear `developer + mcp_token + project_member`
  antes de instanciar `NativeBackend`, alineada con el nuevo modelo de
  identidad. 24/24 verde.

### Removed

- **`register_native_developer`** — eliminada del MCP (era una tool
  `@mcp.tool` en `server/tools/coordination.py`). El CRUD de developers /
  github_identities / mcp_tokens ahora es responsabilidad exclusiva del
  SpecBox Control Panel. Las 4 tools native restantes (`whoami`,
  `claim_uc`, `release_uc`, `register_native_branch`) permanecen.
- **`developers.token_hash`** + índice `idx_developers_token_hash` —
  eliminados atómicamente en la migración `0005_mcp_tokens.sql`. El
  almacenamiento de tokens se mueve a la nueva tabla `mcp_tokens`.

### Fixed

- **`0002_developers.sql` ya no rompe la cadena tras un drop de
  `token_hash`** — el `CREATE UNIQUE INDEX` se envolvió en un `DO $$` block
  con check de `information_schema.columns`. Antes, re-aplicar la cadena
  completa tras 0005 fallaba con `column does not exist` (porque
  `IF NOT EXISTS` solo guarda el índice, no la referencia a la columna).
- **`register_mcp_token` idempotencia** — el `INSERT` pasa a `ON CONFLICT
  (token_hash) DO UPDATE ... RETURNING token_id`, así re-registrar el
  mismo token clear no rompe la `UNIQUE` y devuelve el `token_id`
  existente.
- **Lint preexistente saneado en `server/tools/spec_driven.py`** y
  `server/tools/migration.py` (3 errores `E741`/`F841` que el hook
  pre-commit habría bloqueado al tocar esos archivos).

### Security

- **Despersonalización del repo público** (`chore(security)`, PR #40) —
  el `project_ref` específico del mantenedor (`nywjsvumsvxlpflpbord`) y el
  nombre concreto del proyecto Supabase (`SpecBox-DataBase`) fueron
  reemplazados por placeholders genéricos en `CHANGELOG.md`, `CLAUDE.md`,
  `ENGINE_VERSION.yaml`, `doc/runbooks/native-supabase-credential.md`,
  `doc/tracking/items.json`, `doc/tracking/progress/UC-401.md`, y
  `tests/test_native_pool_supabase.py`. El runbook ahora es genérico:
  cada operador del MCP provisiona y opera su propia instancia Supabase.
- **Frontier 2 inalterado** — el DSN sigue siendo env-only
  (`SPECBOX_NATIVE_DSN`); ningún cambio de esta release lo expone. El
  `dev_token` en sesión es Frontier 1 (credencial de usuario), no de DB.
- **Aislamiento de los proyectos existentes** — los proyectos en
  FreeForm/Trello/Plane no tocan código Native por construcción (dispatch
  en `auth_gateway.py` solo construye `NativeBackend` cuando
  `backend_type == "native"`).

### Tests

- **6 nuevos archivos de test** (Postgres dev real, gated por `PG_OK`):
  `test_native_security_schema.py`, `test_native_init_signature.py`,
  `test_resolve_developer.py`, `test_auth_cache_ttl.py`,
  `test_native_mutation_authz.py`, `test_audit_log_destructive.py`,
  `test_native_revoke_adversarial.py`, `test_migrate_backend_nxn.py`,
  `test_switch_backend_transactional.py`, `test_state_mapping.py`,
  `test_write_target_dispatch.py`, `test_native_handling.py`,
  `test_evidence_regen.py`.
- **347 tests verde** tras el merge final (suite Native-Security
  completa + migración + estado global del MCP).
- Conformance suite restaurada al 100% (24/24) con el nuevo modelo de
  identidad.

### Pending operational task (no blocking)

Propagar las 3 migraciones nuevas (`0004_github_identities.sql`,
`0005_mcp_tokens.sql`, `0006_audit_log.sql`) + el patch idempotente de
`0002_developers.sql` a `supabase/migrations/` y aplicar contra la instancia
Supabase real vía `mcp__supabase__apply_migration`. El runbook documenta
el patrón.

## [5.34.0] - 2026-05-22 — "Native Collaboration"

Estrena el **Native Backend**: un cuarto backend del `SpecBackend` ABC (junto a
Trello / Plane / FreeForm) respaldado por una instancia gestionada de Supabase
Postgres, pensado para equipos donde varios developers comparten un único board
source-of-truth. Hasta ahora los backends asumían un solo developer (FreeForm
local) o un servicio externo de reporting (Trello / Plane); ninguno resolvía la
concurrencia multi-developer sobre un mismo board. El Native Backend lo hace con
concurrencia optimista, identidad de developer y claims de UC. Es **opt-in por
proyecto** y **aditivo** — no toca el comportamiento de los tres backends
existentes.

### Added

- **Native Backend** (`server/backends/native_backend.py`) — implementa los 26
  métodos del `SpecBackend` ABC sobre un pool asyncpg contra Supabase Postgres.
  Despachado desde `auth_gateway.py` solo cuando `backend_type='native'`.
- **Schema multi-tenant** (`server/db/migrations/0001_native_schema.sql`) —
  tablas US/UC/AC con guard de **concurrencia optimista** (`expected_version`,
  pasado vía `meta` para no romper la firma del ABC).
- **Identidad de developer** (`0002_developers.sql` +
  `server/coordination/identity.py`) — resolución token→developer, Frontier 1
  authz (UNAUTHENTICATED cuando el token es desconocido, FORBIDDEN cuando un
  developer toca un proyecto del que no es miembro). Tools `whoami`,
  `register_native_developer`.
- **Claims de UC + registro de ramas** (`0003_claims.sql` +
  `server/coordination/{claims,branches}.py`) — un developer reserva un UC y
  registra su rama feature. Tools `claim_uc`, `release_uc`,
  `register_native_branch`.
- **`docker-compose.dev.yml`** — Postgres dev local (postgres:16, puerto 55432,
  db `specbox_native`) para verificar migraciones y tests sin tocar producción.

### Changed

- **Native Backend migrado de Postgres-on-VPS a Supabase gestionado**
  (Postgres 17+, región a elección del operador). El cutover de la instancia
  del mantenedor quedó validado en producción; cada operador del MCP es
  responsable de provisionar su propia instancia Supabase.
- **`auth_gateway.py`** — rama `native` añadida en `get_session_backend`; el DSN
  se lee de `SPECBOX_NATIVE_DSN` (nunca se persiste).
- **Dashboard `/health`** — lee la versión real de `ENGINE_VERSION.yaml` en vez
  de un string hardcoded.
- **Dockerfile** — ARG `CACHEBUST` para forzar recopy del engine en rebuilds de
  EasyPanel.

### Decisions

- El Native Backend es **opt-in y aditivo**, no un reemplazo. Es un cuarto
  backend; los proyectos que no configuran `backend_type='native'` se comportan
  exactamente igual que antes. Por eso la release es un **minor** sin breaking
  changes.
- **Frontier 2 — seguridad de credenciales**: el DSN vive solo en
  `SPECBOX_NATIVE_DSN`. Nunca en disco ni en `meta.json`, de modo que una fuga de
  board export o config no expone acceso a la base.
- **Concurrencia optimista** (`expected_version`) elegida sobre locking para
  evitar que un developer con un lock obsoleto bloquee a todo el equipo.

### Compatibility

- 100% backwards-compatible. La firma del `SpecBackend` ABC no cambia
  (`expected_version` fluye por `meta`). `detect_project_backend` mantiene su
  cadena de prioridad de 5 niveles; native solo se selecciona si está
  explícitamente configurado. Sin `SPECBOX_NATIVE_DSN`, el pool native nunca se
  instancia.

### Tests

- Suites native verdes contra la instancia Supabase real: 50 passed, 0 skipped.
  - `tests/test_native_schema.py`, `tests/test_native_backend_conformance.py`
    (conformance parametrizado del ABC), `tests/test_native_dispatch.py`,
    `tests/test_native_pool_supabase.py`, harness `tests/_native_db.py`.
- Fallos preexistentes en `main` (mock de `InMemoryBackend` sin `archive_item`
  en `test_spec_mutations.py`) documentados en releases previas permanecen y son
  ajenos a este trabajo.

## [5.33.0] - 2026-05-13 — "FreeForm Path Safety"

Convierte el BLOCKER de v5.29 (FreeForm + MCP remoto escribiendo el tracking en
el VPS) en un bug mecánicamente imposible. v5.29 ya tenía el server-side guard
(`FREEFORM_PATH_MUST_BE_ABSOLUTE`) y la skill `/app-init` resolvía el absoluto
explícitamente, pero cualquier cliente que llamara a `set_auth_token` u
`onboard_project` por fuera de la skill (claude.ai mobile, integraciones
externas, otros skills) seguía siendo vulnerable: el server tiraba error y el
usuario tenía que copiar/pegar el path absoluto a mano. v5.33 añade dos capas
más para que el path llegue auto-resuelto al MCP, no para que muera ahí.

### Added

- **`.claude/hooks/freeform-path-guard.mjs`** — nuevo hook PreToolUse que
  intercepta `mcp__SpecBox-MCP__set_auth_token` y
  `mcp__SpecBox-MCP__onboard_project`. Cuando `backend_type='freeform'` y el
  path es relativo (o la default `"doc/tracking"` queda implícita), el hook
  reescribe el argumento al absoluto del repo cliente via
  `git rev-parse --show-toplevel` usando el protocolo nativo del harness
  (`hookSpecificOutput.updatedInput`, exit 0). Cubre el caso implícito donde
  `onboard_project` se llama sin `backend_type` AND sin `trello_board_name`
  (engine defaults a freeform). Bloquea con exit 2 solo cuando el CWD no es
  git y la resolución sería ambigua. Cada reescritura queda en
  `.quality/logs/freeform-path-rewrites.jsonl` para audit trail.
- **`detect_local_root_path()`** — nueva tool MCP read-only en
  `server/tools/onboarding.py`. Declara el contrato:
  `requires_absolute_path`, `default_relative_path`,
  `client_resolution_recipe` (la receta exacta de shell), `hook_helper`
  (path al helper JS). Sirve a `/app-init`, claude.ai mobile e integraciones
  externas como documentación ejecutable del protocolo de path resolution.
- **`/app-init` Paso 2.3 reforzado** — 3-step handshake: (1) llamar
  primero a `detect_local_root_path()` para declarar el contrato, (2)
  resolver `ABS_TRACKING` desde `PROJECT_ROOT` computado en Paso 1, (3)
  pasar el absoluto explícito a `set_auth_token`. Nota nueva sobre el hook
  como defensa en profundidad — la skill sigue pasando el absoluto, el
  hook es red de seguridad para clientes que no usan la skill.

### Changed

- **`.claude/settings.json`** — nuevo matcher en PreToolUse
  `mcp__SpecBox-MCP__(set_auth_token|onboard_project)` que invoca
  `freeform-path-guard.mjs` con timeout 3s.
- **`CLAUDE.md`** — header bumpeado a v5.33.0, sección "Hooks" añade fila
  para `freeform-path-guard`, sección "BLOCKER fix: FreeForm + remote MCP"
  añade párrafo "Defense in depth" documentando las 3 capas aditivas.
  Tools count actualizado en 4 lugares (163→164 total, 158→159 server.py,
  10→11 onboarding.py).

### Decisions

- **Auto-rewrite silencioso > block-with-message.** El protocolo PreToolUse
  del harness soporta `hookSpecificOutput.updatedInput` (exit 0) para
  mutar argumentos antes de la llamada, así que el bug se vuelve
  mecánicamente imposible en lugar de generar un error visible que el
  usuario tiene que arreglar manualmente. El server-side guard
  `FREEFORM_PATH_MUST_BE_ABSOLUTE` de v5.29 sigue activo como última red.
- **3 capas aditivas e independientes.** Capa 1 (`/app-init` explícita) +
  Capa 2 (hook universal) + Capa 3 (server-side reject). Cada capa
  refuerza a las otras sin acoplarse. Quitar cualquiera no desbloquea el
  bug mientras las otras estén en pie.
- **Hook cubre las 2 tools + caso implícito.** Tanto `set_auth_token`
  (arg `root_path`) como `onboard_project` (arg `freeform_root_absolute`),
  y también `onboard_project` sin `backend_type` AND sin
  `trello_board_name` donde el engine cae a freeform por default. 8
  escenarios probados.

### Compatibility

- 100% backwards-compatible. Clientes pre-v5.33 sin el hook instalado
  siguen hitting el server-side guard de v5.29 con el mismo error
  message. Clientes nuevos con el hook obtienen auto-rewrite silencioso.
  La skill `/app-init` de v5.29-v5.32 sigue funcionando — el cambio en
  SKILL.md solo añade el handshake nuevo, el patrón legacy
  `ABS_TRACKING=$(pwd)/doc/tracking` sigue produciendo el mismo absoluto.

### Out of scope

- Extender el hook a claude.ai mobile (transport distinto, hoy sin
  soporte de PreToolUse hooks). Mobile sigue dependiendo del server-side
  guard hasta que Anthropic añada soporte equivalente.
  `detect_local_root_path()` compensa parcialmente surfaceando el
  contrato via MCP discovery.

### Tests

- 8 smoke tests del hook ejecutados manualmente vía stdin simulado:
  relativo → reescribe ✅, absoluto → no-op ✅, tool no watched →
  no-op ✅, trello backend → no-op ✅, `onboard_project` implicit
  freeform → reescribe + stampea `backend_type` ✅, root vacío → reescribe
  al canónico ✅, no-git CWD → bloquea exit 2 ✅, log JSONL escrito ✅.
- Sintaxis validada: `node --check freeform-path-guard.mjs` ✅,
  `ast.parse(onboarding.py)` ✅, `json.load(settings.json)` ✅.
- Pre-existing failures en `main` (test_acceptance_check, test_spec_mutations,
  test_milestone_management, test_pdf_generator) documentados desde v5.29
  permanecen y son ortogonales a esta release.

## [5.32.1] - 2026-05-02 — "Release Skill — README + CHANGELOG enforcement"

Convierte la regla "README + CHANGELOG en cada bump" en un guardrail mecánico
verificable. La regla vivía en memoria persistida desde v5.31.1 y dependía de
que la sesión la cargara — frágil. v5.32.1 la mueve al SKILL de `/release`
como pasos obligatorios y añade un validador que aborta la release si
cualquiera de los 5 archivos de versión queda desincronizado. Misma filosofía
que aplicamos en v5.32 con los Task isolation guards: no confiar en
convenciones, hacerlas verificables.

### Added

- **`/release` SKILL.md Paso 4.5 'Actualizar README.md'** — paso obligatorio
  con sub-steps 4.5.1-4.5.5 que detallan las 4 ubicaciones a bumpear
  (subtítulo ES, bloque "Lo nuevo en vX", subtítulo EN, bloque "What's new
  in vX") y la verificación con `grep`. Documenta la regla del patch sobre
  minor existente: en patch releases NO se añade nuevo bloque "Lo nuevo en
  vX.Y.Z" — se actualiza el bloque vX.Y existente con una línea adicional.
- **`/release` SKILL.md Paso 5.5 'Actualizar CHANGELOG.md'** — paso
  obligatorio que detalla el formato de la entrada nueva (Added / Changed /
  Decisions / Compatibility / Tests) y la verificación con `head -10 | grep`.
- **`/release` SKILL.md Paso 7 'Pre-commit Consistency Check'** —
  bloqueante. Ejecuta el nuevo validador antes del `git commit` del Paso 6.
  Si exit 1, aborta la release.
- **`.quality/scripts/version-consistency-check.mjs`** — validador zero-deps
  que lee `ENGINE_VERSION.yaml` como canónico y verifica la versión en
  `pyproject.toml`, `CLAUDE.md` (header + footer Engine Version),
  `CHANGELOG.md` (entrada superior), `README.md` (subtítulo ES + EN). Per-
  file diagnosis a stderr (OK / MISMATCH / MISSING). Exit 0 = aligned, 1 =
  out of sync.
- **`tests/scripts/version-consistency-check.test.mjs`** — 8 smoke tests
  con mini-repos sintéticos en `/tmp` cubriendo happy path, README out of
  sync, CHANGELOG missing new entry, CLAUDE.md header forgotten, pyproject
  misaligned, ENGINE_VERSION.yaml unreadable, README file absent, y varios
  archivos out of sync simultáneamente.

### Changed

- **`/release` SKILL.md Paso 6.2** — `git add` ahora lista explícitamente
  `README.md` y `CHANGELOG.md` además de los archivos previos.
- README.md y CHANGELOG.md de este repo ahora bumpean con esta release
  siguiendo el nuevo protocolo (patch sobre minor: actualizar bloque
  existente con línea adicional, no nuevo bloque).

### Decisions

- **Mecanizar > Recordar.** La regla "README en cada bump" vivía sólo en
  memoria persistida desde v5.31.1. Funcional cuando la sesión la cargaba,
  frágil cuando no. v5.32.1 la convierte en código verificable.
- **Validador aborta, no avisa.** Exit 1 detiene la release. Si genera falso
  positivo, reportar como bug en lugar de bypasear.
- **Patch sobre minor preserva el bloque "Lo nuevo en vX.Y"** — añade una
  línea, no un nuevo bloque. Mantiene el README legible cuando hay varios
  patches consecutivos.

### Compatibility

- 100% backwards-compatible. Releases pre-v5.32.1 no se ven afectadas — el
  validador sólo se invoca desde el nuevo Paso 7. Proyectos que usen una
  copia anterior del SKILL `/release` siguen funcionando sin el guardrail
  (degradación graceful).

### Tests

- 8 nuevos tests verdes para el validador (`version-consistency-check.test.mjs`).
- Smoke manual contra el repo actual (todo en v5.32.0 al momento del
  desarrollo) verificó que el validador detecta correctamente el estado
  alineado antes del bump.

## [5.32.0] - 2026-05-02 — "Implement Task Isolation"

Cierra el out-of-scope explícito de v5.30.0 (PR #20): el SKILL.md de
`/implement` ya **documentaba** la delegación a Tasks aisladas, pero el
contrato no estaba mecánicamente forzado. v5.32 añade los 5 guardrails
que faltaban — sin rediseñar la arquitectura — y los cablea de forma
observable. En modo warn por defecto durante la migración. Plan técnico
completo en [doc/plans/v5.32.0_implement_task_isolation_plan.md](doc/plans/v5.32.0_implement_task_isolation_plan.md).

### Added

- **`execution_context.json`** persistido en `.quality/evidence/{feature}/`
  con `branch`, `feature_slug`, `stack`, `project_root_absolute`, `plan_hash`
  y demás. Cada Task delegado lee este archivo en lugar de recibir esos
  valores verbatim en el prompt — fixea la causa raíz del context exhaustion
  en UCs grandes. Helpers en `server/implement_context/execution_context.py`
  (Pydantic, atomic write, idempotente) y `.claude/hooks/lib/execution-context.mjs`
  (read-only para hooks).
- **`context-budget-guard.mjs`** PreToolUse(Task). Estima tokens via chars/4
  (zero-deps) y warn|block según
  `specbox.implement.task_isolation.task_budget_mode` (default `warn`,
  budget 16000). Bumpea counters en `.quality/task_isolation.json`.
- **`file-ownership-guard.mjs`** PreToolUse(Write/Edit). Lee
  `.quality/active_agent.json` (transient) para identificar el agente activo
  y valida la ruta contra el ownership map en
  `.claude/skills/implement/file-ownership.md`. Modes warn|strict|off. Path
  traversal (`..`, `/abs`) siempre BLOCKED. Sugiere el owner correcto al
  bloquear. Parser y glob → regex en `lib/ownership-map.mjs`.
- **`phase_outputs.jsonl`** append-only por feature con un delta estructurado
  por Task: `files_created/modified/deleted`, `summary`, `duration_s`,
  `tokens_used_*`, `healing_attempts`, `status`. Schema v1 definido en
  `doc/specs/phase-outputs-spec.md`. Validador zero-deps en
  `.quality/scripts/validate-phase-outputs.mjs`. Aggregator
  `aggregate_for_spec_sync` reemplaza el cálculo de deltas vía git diff que
  vivía en el contexto del orquestador.
- **`/implement` SKILL.md** Paso 0.4b (escribir execution_context.json),
  Paso 5.0 (bloque reusable antes/después de cada `Task(AG-XX)`: write
  active_agent → spawn → cleanup → bump counters), Paso 5.1.1b y 8.5.1a
  (consumen `aggregate_for_spec_sync` en vez de la lista en memoria del
  orquestador). Banner "Working set (v5.32.0)" al inicio del SKILL.
- **Heartbeat enriquecido** con `task_isolation: {enabled, tasks_run_total,
  tasks_failed_budget, tasks_failed_ownership, last_feature_slug,
  last_event_at}` añadido **después** del bloque v5.31 Stitch Autopilot
  (que sigue intacto, igual que el bloque v5.30 Session Continuity).

### Changed

- `pyproject.toml`, `ENGINE_VERSION.yaml`, `CLAUDE.md` bumpean a 5.32.0.
- `templates/settings.json.template` añade el bloque
  `specbox.implement.task_isolation` con defaults preservando comportamiento
  pre-v5.32 (modes warn).
- `.claude/settings.json` registra los dos nuevos hooks.

### Decisions

- **Modo `warn` por defecto** en ambos guards. Promoción a `strict` queda
  como settings flip tras 2 semanas de telemetría — no es cambio de código.
- **NO se rediseña** el SKILL.md de `/implement`. La delegación ya estaba
  documentada (líneas 469-536, 496-506). v5.32 implementa los 5 guardrails
  para que el contrato sea verificable y observable.
- **Healing sigue dentro del mismo Task** que falló. Mover healing a Task
  propio queda como v5.32.1 — release minimalista primero.

### Compatibility

- **100% backwards-compatible.** Proyectos sin `execution_context.json` ni
  `phase_outputs.jsonl` ven los guards como no-ops; el heartbeat reporta
  `task_isolation: null`; Spec-Code Sync cae al fallback de `git diff`.
- Los hooks v1 (`quality-first-guard`, `healing-budget-guard`,
  `pipeline-phase-guard`, `stripe-safety-guard`) siguen ejecutándose en
  Write/Edit antes de `file-ownership-guard`.

### Tests

- 69 tests nuevos, todos verdes:
  - `test_implement_context.py` (18) — schema, paths, write/read,
    idempotency, plan hash, atomic writes
  - `test_phase_outputs.py` (17) — schema, append/read, aggregation,
    dedup, status logic
  - `tests/hooks/context-budget-guard.test.mjs` (11) — token estimator
    + hook end-to-end
  - `tests/hooks/file-ownership-guard.test.mjs` (23) — parser, globs,
    suspicious paths, hook modes
- Pre-existing failures on `main` (`test_acceptance_check::test_registers_two_tools`
  y los TypeErrors en `test_spec_mutations` / `test_milestone_management`
  documentados en v5.29 changelog) NO causados por este PR y persisten.

## [5.31.1] - 2026-05-02 — "Stitch Autopilot — /plan migration"

Patch release que cierra el out-of-scope explícito de v5.31.0: migra
`/plan` Paso 6 al pipeline v2. A partir de esta release, todas las
generaciones de Stitch invocadas por `/plan` pasan por el validator de
prompts y la fallback chain — el agente ya no llama `mcp__stitch__generate_screen_from_text`
directamente. Se añaden Pasos 5.5 (pre-check DESIGN.md + cuota), 6.3.1
(validar prompt antes de generar), 6.3.3 (refinamiento incremental con
`baseline_screen_id`) y 6.7 (batched build_site cuando hay >5 pantallas).

### Changed

- **`/plan` Paso 6.3** — `mcp__stitch__generate_screen_from_text` →
  `stitch_generate_screen_v2`. La instrucción "no reintentar manualmente
  en timeout" del SKILL.md ahora explica que la fallback chain
  (edit_baseline → variants_refine → regenerate) lo hace
  automáticamente, y que el agente debe presentar `attempts[]` al
  usuario si el outcome es `failed`.
- **`/plan` Paso 6.3.1** (nuevo) — toda generación es precedida por
  `validate_stitch_prompt(mode="warn", project_root=...)`. Tabla de
  acción para `valid+warnings`, `requires_split`, modo strict.
- **`/plan` Paso 6.3.3** (nuevo) — documenta uso de `baseline_screen_id`
  para forzar `edit_baseline` sobre `regenerate` en refinamientos
  incrementales (preserva trabajo + ahorra cuota PRO).

### Added

- **`/plan` Paso 5.5** entre Paso 5 y Paso 6:
  - 5.5.1 verifica `doc/design/DESIGN.md`. Si no existe pero hay Brand
    Kit, lo genera automáticamente. Si no hay ninguno, avisa y pide
    confirmación.
  - 5.5.2 registra DESIGN.md frente al Stitch project (mode
    `inline-prefix`) para que las generaciones lo prependan
    automáticamente.
  - 5.5.3 pre-warning de cuota antes del loop de generación. Tabla de
    acción tiered: <80% silencioso, 80-100% pregunta, ≥100% bloquea
    hasta safety net opt-in o reset.
- **`/plan` Paso 6.7** (nuevo) — multi-pantalla con
  `stitch_build_site_batched_v2` cuando hay >5 pantallas relacionadas.
  Documenta cuándo conviene (flujo cohesivo) vs cuándo mantener serial
  (pantallas independientes), y cómo asignar `group` para particionado
  fino.

### Compatibility

- 100% backwards-compatible. Las 13 tools v1 siguen registradas; los
  proyectos que tengan forks personales del SKILL.md verán que el
  call site cambió y deberán mergear, pero ningún proyecto rompe
  funcionalmente.
- Sin cambios de settings necesarios. Defaults preservan calidad-first:
  `GEMINI_3_PRO`, `flash_safety_net=false`, validator en `warn`.

### Decisions

- **Modelo default sigue siendo `GEMINI_3_PRO`**. La migración no
  cambia las decisiones de calidad de v5.31.0 — solo activa
  programáticamente lo que ya estaba construido y disponible.
- **Validator en `warn` mode** durante la migración. Promoción a
  `strict` queda como decisión empírica futura tras 2 semanas de
  telemetría.

## [5.31.0] - 2026-05-02 — "Stitch Autopilot"

Closes the gap between SpecBox and Google's official Stitch best practices,
removing the most common source of autopilot blockers in `/visual-setup` and
`/plan` Paso 2.5b. Modelo default sigue siendo `GEMINI_3_PRO` — la prioridad
declarada del usuario es calidad de diseño, no reducir tiempo. Flash queda
únicamente como red de seguridad opt-in
(`specbox.stitch.fallback.flash_safety_net=false` por defecto). Plan técnico
completo en [doc/plans/v5.31.0_stitch_autopilot_plan.md](doc/plans/v5.31.0_stitch_autopilot_plan.md).

### Added

- **DESIGN.md canonical format** ([google-labs-code/design.md](https://github.com/google-labs-code/design.md))
  with Pydantic schema (rejects named colors at parse time), generator with
  6 VEG archetype defaults (corporate / startup / creative / consumer /
  gen_z / gov), serializer in fixed section order per spec, signature-based
  drift detection. New module `server/design_md/`.
- **Two new MCP tools**: `generate_design_md_tool` (synthesises
  `doc/design/DESIGN.md` from Brand Kit + VEG + canonical app docs,
  idempotent, persists provenance + signature in `meta.json`) and
  `upload_design_md_to_stitch` (registers DESIGN.md against a Stitch
  project; mode `inline-prefix` until Google ships a native attach
  endpoint).
- **`/visual-setup` Paso 3.7 + 3.8** invoke the two new tools right after
  the existing Stitch Design System creation. Existing flow preserved.
- **4-layer prompt template v2** (Context ≤80 words / Components bullets /
  Style hex-only / Platform) at `design/stitch/prompt-template-v2.md` and
  module `server/stitch_prompt/`. New MCP tool `validate_stitch_prompt`
  with `warn` (default) and `strict` modes; detects E1 named colors
  (auto-resolves against DESIGN.md palette), E2 layout+components mixing
  (proposes split, robust to single-line mixed intents), W1-W4 length and
  structure warnings.
- **Fallback chain** at `server/stitch_orchestration/fallback.py` —
  ladder `edit_baseline → variants_refine → regenerate`, optional
  `flash_safety_net` last-resort marking results `degraded=True`. Error
  classification (transient | quota | content | unknown). New MCP tool
  `stitch_generate_screen_v2` over a thin `_StitchOpsAdapter` against the
  real `StitchClient`.
- **Batched build_site** at `server/stitch_orchestration/batching.py` —
  partitions screens into ≤4-screen groups (priority: explicit `group`
  tag → route prefix → order chunks), runs `build_site` per partition,
  applies a final unifying `edit_screens` pass when >1 batch is needed.
  New MCP tool `stitch_build_site_batched_v2`.
- **Quota tracking** at `server/stitch_quota/computation.py` — pure
  aggregator over `stitch_usage.jsonl` by month and model class.
  Pro=Experimental (200/mo), Flash=Standard (350/mo). Counts only
  successful generations; metadata operations are free. New MCP tool
  `get_stitch_quota_status` with optional `write_cache=True` that
  persists a compact summary at `.quality/stitch_quota.json`.
- **Heartbeat enriched** with a `stitch_quota` field appended *after*
  the v5.30.0 Session Continuity block (`handoff_present`,
  `context_pressure` preserved). Best-effort: null when no cache exists.
- **PreToolUse hook `stitch-quota-guard.mjs`** — warns at ≥80% on either
  bucket (exit 0); blocks (exit 2) when PRO is exhausted AND
  `flash_safety_net=false`. Registered in `.claude/settings.json`
  matching `mcp__SpecBox-MCP__stitch_.*`.
- **Settings template** gains `stitch.fallback`, `stitch.quota`,
  `stitch.prompt.validator_mode` blocks. Defaults preserve v5.30
  behaviour: PRO model, no Flash safety net, validator in `warn` mode.

### Changed

- `pyproject.toml` and CLAUDE.md bumped to v5.31.0; tool count 158 → 163.
- New section "Stitch Autopilot (v5.31.0)" in CLAUDE.md right after the
  existing "Stitch MCP Proxy (v5.6.0)" describes the 5 capas, settings
  shape, and compatibility notes. Hooks table gains a row for
  `stitch-quota-guard`.
- `heartbeat-sender.mjs` — appends `stitch_quota` after the v5.30.0
  block (no overwrites, no reordering).

### Decisions

- **Model default stays GEMINI_3_PRO**. Calidad over velocidad.
  `flash_safety_net=false` by default.
- **Slot v5.31.0 reassigned** from "delegación de fases de /implement
  a Tasks aisladas" (originally reserved by PR #20's commit message)
  to Stitch Autopilot, after confirming no PRs or active branches
  existed for that work. The /implement phase delegation moves to a
  future v5.32+ with its own dedicated plan.

### Compatibility

- **100% backwards-compatible.** v1 Stitch tools (the 13 originals) stay
  registered alongside the new v2 tools. `/plan` Paso 2.5b is **NOT**
  modified — it continues to use v1 by default. The migration of
  `/plan` Paso 2.5b to v2 will land in a follow-up patch (`v5.31.x`)
  once telemetry from the warn-only validator confirms a low
  false-positive rate.
- Projects without `doc/design/DESIGN.md` continue to behave like v5.30:
  the heartbeat `stitch_quota` field stays null, the validator passes
  through prompts unchanged in warn mode.

### Tests

- 131 new tests, all green:
  - 38 in `test_design_md.py` (schema, archetypes, generator, writer
    round-trip, signature stability)
  - 15 in `test_stitch_v2_design_md.py` (MCP tool wiring for the
    DESIGN.md tools)
  - 25 in `test_stitch_prompt.py` (builder + validator + tool)
  - 27 in `test_stitch_orchestration.py` (fallback ladder, partitioning,
    end-to-end batched build with FakeOps)
  - 26 in `test_stitch_quota.py` (classification, monthly aggregation,
    payload thresholds, file loader, MCP tool, cache writes)
- Pre-existing failures on `main` (`test_acceptance_check::test_registers_two_tools`
  and the `test_spec_mutations` / `test_milestone_management` TypeErrors
  documented in the v5.29 changelog) are unrelated to this release and
  remain.

## [5.30.0] - 2026-05-02 — "Session Continuity"

Minor release dedicada a **preservar el contexto cuando una sesión de Claude Code se hace larga**. Antes de v5.30, una compactación o `/clear` perdía toda decisión, hot file y "próximo paso" que no estuviera persistido en commits o checkpoints — el usuario tenía que poner al día a la siguiente sesión a mano. v5.30 introduce un protocolo de handoff explícito + carga automática del estado en la nueva sesión + observabilidad de presión de contexto en vivo. Plan técnico completo en [doc/plans/v5.30.0_session_continuity_plan.md](doc/plans/v5.30.0_session_continuity_plan.md).

### Added

- **`/handoff` skill** ([.claude/skills/handoff/SKILL.md](.claude/skills/handoff/SKILL.md)) que persiste estado fino de sesión a `.quality/handoff.md` (Markdown narrativo) y a Engram como observación estructurada bajo topic `session:<project>:<branch>`. Idempotente. Capa human-readable que complementa el checkpoint mecánico de `/implement`. CLAUDE.md instruye a Claude a invocarla **antes** de proponer compactación.
- **`SessionStart` hook** ([.claude/hooks/session-start.mjs](.claude/hooks/session-start.mjs)) que inyecta `.quality/handoff.md` (si existe y es <24h) como `additionalContext` al arrancar la nueva sesión. Cap a 14 000 chars (~3.5k tokens). Marca `[STALE]` cuando supera `ttl_minutes`. Fallback: UC activo + último checkpoint + zonas auto de `app_spec.md`.
- **`pre-read-budget-guard` hook** ([.claude/hooks/pre-read-budget-guard.mjs](.claude/hooks/pre-read-budget-guard.mjs)) — PreToolUse(Read) **no bloqueante** que estima tokens del archivo (chars/4) y avisa si supera `warn_pct` de la ventana de Claude (default 5% de 1M). Empuja a usar Grep/Explore en vez de Read masivo. Configurable vía `.claude/settings.local.json` → `specbox.context_budget`.
- **Builder puro** [.claude/hooks/lib/handoff-builder.mjs](.claude/hooks/lib/handoff-builder.mjs) con API `computeSessionId / buildHandoffData / renderHandoff / writeHandoff`. Auto-redacta `sk_live_*`, `sk_test_*` y tokens >=32 chars. `session_id` determinista (12 chars) por `cwd+date` para correlación cross-tool.
- **Contrato formal** [doc/specs/handoff-spec.md](doc/specs/handoff-spec.md) con frontmatter (9 campos) + 7 secciones obligatorias + tamaño máximo 14000 chars. Validador en [.quality/scripts/validate-handoff.mjs](.quality/scripts/validate-handoff.mjs). Template en [templates/handoff.md.template](templates/handoff.md.template). Fixtures cubren casos válidos + 3 inválidos en [tests/fixtures/handoff/](tests/fixtures/handoff/).
- **Heartbeat enriquecido** ([.claude/hooks/heartbeat-sender.mjs](.claude/hooks/heartbeat-sender.mjs)) reporta `handoff_present`, `handoff_age_minutes` y `context_pressure` ({tokens_est, pct_of_window, level∈{healthy,warn,critical}}). El endpoint `/api/heartbeat` los persiste para Sala de Máquinas.
- **Métrica `handoff_rate`** en [.quality/scripts/analyze-sessions.sh](.quality/scripts/analyze-sessions.sh): % de sesiones que terminaron con `.quality/handoff.md` presente. ≥80% verde, 50-80% amarillo, <50% rojo.
- **CLAUDE.md sección Session Continuity** con el protocolo "antes de proponer compactar → ejecutá /handoff". Tabla de hooks v5.30 incluye `session-start` y `pre-read-budget-guard`. Tabla de skills incluye `/handoff`.
- **19 smoke tests nuevos** (todos verdes, sin framework externo): [tests/hooks/handoff-builder.test.mjs](tests/hooks/handoff-builder.test.mjs) (13) + [tests/hooks/session-start.test.mjs](tests/hooks/session-start.test.mjs) (6).

### Changed

- **`on-session-end.mjs`** ahora escribe a Engram un payload JSON estructurado en lugar del string libre que usaba v5.29.x. Topic key cambia a `session:<project>:<branch>` para permitir filtrado por rama. La forma vieja sigue siendo legible — solo el emisor cambió.
- **`heartbeat-sender.mjs`** payload contiene 3 campos nuevos (handoff_present, handoff_age_minutes, context_pressure). [server/dashboard_api.py](server/dashboard_api.py) `POST /api/heartbeat` los acepta y persiste.

### Compatibility

- 100% backwards-compatible. Proyectos sin `/handoff` siguen funcionando: SessionStart hook solo emite cuando hay state local; budget guard solo avisa; el refactor de Engram preserva la lectura de observaciones legacy.
- Proyectos en v5.29.0 pueden adoptar v5.30 selectivamente vía `/compliance --fix`.

### Out of scope (deferido a v5.31)

- Delegación de fases de `/implement` a Tasks aisladas (idea original O6 del plan). Esta release reduce el **coste** de quedarse sin contexto vía continuity; v5.31 atacará la **probabilidad** vía mejor aislamiento.

## [5.29.0] - 2026-05-02 — "Cognitive Load Reduction"

Minor release diseñada para que un usuario pueda llevar **múltiples proyectos en paralelo** sin que el engine le interrumpa más de la cuenta. Baseline v5.28: ≥17 puntos de fricción por feature; v5.29 con preset `equilibrado`: ≤8. PRD y plan técnico completos en [doc/prds/cognitive_load_reduction_prd.md](doc/prds/cognitive_load_reduction_prd.md) y [doc/plans/v5.29.0_cognitive_load_reduction_plan.md](doc/plans/v5.29.0_cognitive_load_reduction_plan.md).

### Added

**Capa 1 — Documentos canónicos del proyecto** (`doc/app/`):
- `app_prd.md` y `app_spec.md` con zonas tipadas: `manual` (solo usuario), `auto` (solo engine reescribe), `hybrid` (append-only). Marcadores HTML invisibles `<!-- @specbox:zone start kind="..." id="..." -->`.
- Nueva skill `/app-init` (`context: direct`, idempotente) con 3 modos: `init` (5 preguntas mínimas), `refresh` (solo zonas auto), `upgrade-zones` (insertar marcadores en docs creados a mano con backup obligatorio).
- Templates `templates/app_prd.md.template` y `templates/app_spec.md.template` con 6 zonas cada uno.
- Parser `server/app_docs/zones.py`: `parse_document`, `validate_document`, `compute_signature` (SHA-256 sobre tuplas (id, kind, body) ordenadas, preamble-insensitive), `replace_zone_body` (rewrite seguro preservando marcadores).
- Tools MCP `read_app_docs_tool` y `get_inheritable_values_tool` que `/prd`, `/plan`, `/visual-setup` consultan en su Paso 0 para heredar audiencia, stack, modo VEG, backend sin repreguntar.

**Capa 2 — Autopilot policy engine**:
- 4 tiers (`low` / `conservador` / `equilibrado` / `agresivo`) con 19 `decision_keys` catalogados (ver [doc/plans/v5.29.0_*.md](doc/plans/v5.29.0_cognitive_load_reduction_plan.md) sección 3).
- Implementación dual-language: `.claude/hooks/lib/autopilot.mjs` (JS, hooks) + `server/app_docs/autopilot.py` (Python, MCP tools). Test de paridad asegura que ambos catálogos no derivan.
- Reglas inviolables (no auto-confirman a ningún tier ni override): `image_cost_over_budget`, `destructive_action`, `branch_to_main_push` (este último siempre `block`, nunca `ask`).
- Trazabilidad: cada auto-decisión escribe línea en `.quality/autopilot_decisions.jsonl` con timestamp, decision_key, level, valor, razón.
- Config en `.claude/settings.local.json`: `specbox.autopilot.{level, image_budget_eur_per_feature, auto_confirm_overrides, always_ask_overrides, queue_enabled}`.

**Capa 3 — Cola diferida** (off por defecto en v5.29.0, activa en v5.29.1):
- `doc/app/decisions_queue.md` con secciones Pendientes / Resueltas. Cada entrada con `engine_id` único `dq-<utc>-<rand>-<key>`.
- Nueva skill `/queue review` (`context: direct`) para resolver decisiones en batch (confirmar / ajustar / revertir / skip).
- Tools MCP `enqueue_decision_tool`, `list_decisions_queue`, `resolve_queue_entry`.
- Inviolables-for-queue: `destructive_action`, `image_cost_over_budget`, `branch_to_main_push`, `definition_quality_gate`, `feature_problem_definition`, `feedback_field_classification` (nunca aceptan diferimiento).

**Capa 4 — Decisiones canónicas**:
- Almacén local `.quality/canonical_decisions.json`. Tras 3 confirmaciones idénticas consecutivas, una decisión se promueve a canónica y se reutiliza sin preguntar.
- Auto-invalida cuando el usuario elige un valor distinto (reason `user_chose_different_value`) y arranca un counter limpio.
- Tools MCP `get_canonical_decision`, `record_canonical_confirmation`, `list_canonical_decisions`, `revoke_canonical_decision`.
- Engram **no requerido**: el sistema funciona local-first; si Engram está disponible, los callers pueden además persistir cross-session con `topic_key="autopilot/{project}/{decision_key}"`.

**Capa 5 — Sync enforcement** (modo warning-only en v5.29.0; flips a blocking en v5.29.1 vía `specbox.app_docs_sync.block_on_drift=true`):
- Orquestador `server/app_docs/sync.py`: `verify_app_docs`, `apply_app_docs_sync(event, payload)`, `record_signature`. 12 events cableados al map `EVENT_ZONE_MAP`: `complete_uc`/`move_uc`/`add_uc`/`delete_uc`/`mark_ac_batch` → roadmap; `set_auth_token` → tracking_backend; `lockfile_change`/`framework_detected`/`release_version_bump` → stack; `autopilot_config_change` → autopilot; `canonical_decision_created`/`_revoked` → canonical_decisions.
- Decorador `@requires_app_docs_sync(event_type, payload_extractor=, skip_when=)` en `server/app_docs/decorators.py` con built-in extractors para `set_auth_token`, eventos UC, eventos canonical. Strict-mode opt-in (`SPECBOX_APP_DOCS_STRICT_SYNC=true`) promueve fallos a top-level `ok=false`.
- Hook pre-commit `.claude/hooks/app-docs-sync-guard.mjs`. Reimplementa el parser de zonas + signature en JS puro (sin dependencia Python en commit-time) — test de paridad byte-a-byte con la implementación Python. Skip cuando: no `doc/app/`, sin `.quality/app_docs_sync.lock`, o con `.quality/active_uc.json` activo (Caso 7 de la migración). Telemetría a `.quality/app_docs_drift.jsonl`.
- Skill `/app-sync` con 4 subcomandos: `--check` (CI-friendly), `--repair` (auto-reconciliación con confirmación previa), `--review` (caso por caso interactivo), `--rebuild-from-tracking` (emergencia con literal `"RECONSTRUIR"` confirmation y backup obligatorio).
- Drift detector multi-fuente `server/app_docs/drift_detector.py` con 4 signals para drift implícito que el hook por sí solo no captura: **S1** lockfiles presentes pero no declarados en `app_spec.md` zona `stack` (12 lockfiles conocidos), **S2** referencias a paths Markdown en `brand_visual` que no existen, **S3** roadmap dice `done` pero ningún UC para esa US está done en `doc/tracking/items.json` (FreeForm-only en v5.29.0), **S4** entrada activa en `canonical_decisions.json` no documentada en `app_spec.md` zona `canonical_decisions`.
- Tools MCP `verify_app_docs`, `apply_app_docs_sync`, `record_app_docs_signature`, `detect_app_docs_drift`, `app_docs_drift_for_heartbeat` (compact summary para Sala de Máquinas).

**FreeForm First-Class**:
- `onboard_project` defaults a `backend_type="freeform"` cuando no se pide Trello/Plane explícitamente. Genera `settings.local.json` con bloque canónico `specbox.{backend_type, autopilot.level=equilibrado, freeform_root_absolute}`.
- Auto-discovery `server/app_docs/discovery.py` con cadena de prioridad de 5 niveles: (1) `specbox.backend_type` explícito → (2) `doc/tracking/items.json` filesystem signal → (3) legacy `trello.boardId`/`plane.projectId` → (4) `app_spec.md` zona `tracking_backend` → (5) default `freeform`. Tool MCP `detect_project_backend`.
- Migración Trello/Plane → FreeForm: `migrate_to_freeform_tool(project, target_path, dry_run=True)` descarga items + comments + attachment metadata al filesystem local con `config.json` y reporte Markdown bajo `doc/migrations/`. Valida path absoluto (BLOCKER fix). Inverse del `migrate_project` Trello↔Plane existente; código separado intencionalmente.

**Migración v5.28 → v5.29**:
- Tool `detect_v529_migration_case(project_path)` clasifica el proyecto en uno de 10 estados conocidos (empty / freeform-local / freeform-vps / trello / plane / multirepo / feature-in-progress / pending-feedback / manual-app-md / fresh-clone) y retorna un MigrationPlan con steps + severity + backup_required.
- Tool `run_v529_migration(project_path, apply=False, backend_type="freeform")` aplica el subset seguro (solo `settings.local.json`). Casos sensibles (3 VPS, 7 active UC, 9 manual app_md) reportan como `mode: "deferred"` sin tocar nada — esos requieren intervención usuario via `/app-init` o pasos manuales.

### Fixed

**BLOCKER silencioso de FreeForm + remote MCP**:
- Pre-v5.29: `set_auth_token(backend_type="freeform", root_path="doc/tracking")` con MCP en VPS resolvía el path relativo contra el CWD del proceso del VPS, no del cliente. Datos se escribían en el filesystem del VPS sin error visible.
- Fix: `FreeformBackend.__init__` ahora exige path absoluto, lanza `FreeformPathError` si recibe relativo (con `allow_relative=True` como escape hatch para tests). `set_auth_token` detecta MCP remoto via env `SPECBOX_ENGINE_MCP_URL`, rechaza paths relativos en remote, y resuelve transparentemente en local.
- Helper cliente `.claude/hooks/lib/freeform-path.mjs` con `resolveFreeformPath(p)` y `isRemoteMcp()` para que skills/hooks construyan el absoluto desde `git rev-parse --show-toplevel`.

**Consolidación `src/` → `server/`** (deuda fósil eliminada):
- Pre-v5.29 el repo cargaba un directorio `src/` bit-idéntico a `server/` pero gitignored desde v5.21.0. Sin script de sync; los tests importaban `from src.*` y un `git clone` limpio fallaba con `ModuleNotFoundError`. Sin CI = nadie lo notó.
- 29 test files migrados de `from src.X` / `import src.X` / `patch("src.X")` a las rutas canónicas `server.X`. Línea `/src` eliminada de `.gitignore`. Directorio `src/` borrado.
- `server/server.py:STATE_PATH.mkdir` ahora atrapa `OSError` para no abortar imports en filesystems read-only (deuda preexistente que destapó la consolidación). 501 tests collect en clone limpio post-fix.

### Changed

- `onboard_project` añade parámetros `backend_type: str = ""` y `freeform_root_absolute: str = ""`. Default = freeform cuando no se pasa `trello_board_name` (back-compat con scripts v5.28).
- `/prd`, `/plan`, `/visual-setup` añaden bloque "Paso 0.0 — Leer documentos canónicos" que llama `get_inheritable_values_tool` antes de cualquier otra captura. Soft fallback a v5.28 cuando `doc/app/` no existe.
- `/implement` añade "Paso 0.0 — Política de Autopilot" con tabla de 8 decision_keys aplicables (origin_detection, uncommitted_changes_warning, stitch_design_per_screen, image_cost_under_budget, image_cost_over_budget inviolable, stitch_api_key_missing, branch_to_main_push siempre block, destructive_action).
- `/feedback` añade política autopilot mínima — `feedback_field_classification` y `destructive_action` (creación de GitHub issue) siempre `ask`.

### Defaults v5.29.0

- Backend: `freeform` (cuando no hay reporting externo a cliente).
- Autopilot level: `equilibrado`.
- Image budget: 5€/feature.
- Cola diferida: `queue_enabled=false`.
- Sync enforcement: `block_on_drift=false` (warning-only).

### Backwards compatibility

- 100% backwards-compatible: sin `doc/app/`, sin sección `autopilot`, sin `decisions_queue.md`, sin canonicals — el proyecto se comporta idéntico a v5.28.
- Hooks v5.28 instalados siguen funcionando; los nuevos son aditivos.
- Default implícito sin sección `autopilot`: `level=low` (= v5.28 ask-everything).

### Tests

- 222 tests nuevos verde (190 Python + 32 Node test runner). Distribución: BLOCKER fix (16), zonas (29), app_docs tools (10), autopilot Python (38), autopilot JS (32), cola diferida (12), canonicals (15), FreeForm first-class (9), migración v5.29 (18), sync orchestrator (13), decoradores (11), hook (7), drift detector (12).
- Pre-existing failures unaffected (test_pdf_generator reportlab Python 3.14, test_server stale assertions del repo histórico, test_spec_mutations InMemoryBackend missing `archive_item`, test_milestone_management mismo issue).

---

## [5.28.0] - 2026-05-01 — "Maestro Flutter E2E"

Minor release que añade **Maestro (mobile-dev-inc)** como runner E2E recomendado para Flutter Mobile, complementando a Patrol v4 que sigue soportado como ruta legacy.

### Added

**Stack adapter `architecture/flutter/maestro-setup.md`**:
- Instalación, semantics (Flutter 3.19+ `Semantics.identifier` guidance), YAML flow examples con convención de naming `AC-XX_step_N_description` para screenshots, native dialog handling, troubleshooting.
- Matriz "when to use Patrol instead": estado Dart-side (Provider, BLoC, GetIt singleton), mocks desde la app, suite Patrol estable existente sin ROI de migrar.

**Post-processor `.quality/scripts/maestro-evidence-generator.js`**:
- Parsea Maestro JUnit XML + screenshots y genera el mismo HTML Evidence Report y `results.json` que Patrol/Playwright. AG-09b no distingue el origen.
- Contrato `results.json` extendido con `source="maestro-junit-xml"` (registrado en [doc/specs/results-json-spec.md](doc/specs/results-json-spec.md)). `validate-results-json.js` no requirió cambios — el campo `source` acepta strings libres.

**Agent updates**:
- `agents/acceptance-tester.md` — sección Flutter Mobile ahora ofrece Option A (Maestro, recomendado) y Option B (Patrol, legacy). Auto-invocation block 8.5 documenta ambos generators.
- Template CI `templates/github-actions/maestro-e2e.yml` — Android emulator + iOS simulator, incluye Evidence Report generation y validación de contrato.

**CLAUDE.md**: nueva sección "Maestro Flutter E2E (v5.28.0)" explicando rationale, when to choose Patrol, integration points, y limitaciones heredadas (CanvasKit web fragility, no desktop support, iOS solo inglés en diálogos sistema).

### Notes

- Flutter Web sigue en Playwright. Maestro web sobre CanvasKit es frágil (issue mobile-dev-inc/maestro#2591), mismo techo estructural — cambiar herramienta no resuelve el problema raíz.
- Sin breaking changes. Proyectos Patrol existentes siguen funcionando. Migración a Maestro es opt-in por proyecto.

---

## [5.27.1] - 2026-04-29 — Patch (`specbox-stripe-mcp` SDK 7.x compat)

Patch release para arreglar incompatibilidad silenciosa con stripe-python SDK 7.x en Python 3.14.

### Fixed

- **`specbox-stripe-mcp` v0.3.1**: `as_dict()` ahora prueba `to_dict()` (canónico SDK 7+) antes de `to_dict_recursive()` (legacy SDK ≤5). Stripe SDK 7.x renombró el método canónico de serialización a `to_dict()` y eliminó `to_dict_recursive()`. El `as_dict()` previo caía a `dict(StripeObject)` que retorna `{}` en Python 3.14 porque `StripeObject` no es estrictamente mapping-like. Resultado: cada tool recibía `{}` después de cada llamada API exitosa y crasheaba con `KeyError 'id'` en el siguiente `obj['id']`.
- Bug confirmado reproduciendo `setup_products_and_prices` contra una cuenta `sk_test` real el 2026-04-29. Crash en `setup_products_and_prices.py:320` (`product['id']` dentro de `_reconcile_tier`) inmediatamente después de que `Product.create` retornara HTTP 200. Fix validado end-to-end: mismo script ahora succeeds e idempotente en re-run.

### Tests

- 10 tests nuevos en `tests/unit/test_stripe_object_sdk7.py` con un mock `StripeSdk7Object` que explícitamente NO tiene `to_dict_recursive` (replicando el shape real de SDK 7). Pre-fix code reproduce el mismo `KeyError 'id'`; código fixed pasa.
- Combinado con los 15 tests existentes de `test_stripe_object_py314.py` (legacy SDK ≤5 path), el paquete cubre ambas eras del SDK.
- 193 unit tests pasando (era 183), ruff clean. Backward-compat preservado — proyectos pinned a stripe SDKs legacy siguen funcionando vía el fallback `to_dict_recursive()`.

---

## [5.27.0] - 2026-04-28 — "Stripe Standard + Switch Account"

Minor release con dos skills nuevas en el dominio billing: `/stripe-standard` (Stripe sin Connect) y `/stripe-switch-account` (rotación segura de credenciales).

### Added

**Skill `/stripe-standard`** (`context: direct`, scaffolder Stripe sin Connect):
- 4 modalidades canónicas (flags opt-in): single subscription, tiered subscriptions, metered billing, one-shot checkout.
- Genera US-STRIPE-CHECKOUT con hasta 12 UCs en el spec backend del proyecto.
- Backend Edge Functions + SQL migrations con RLS, frontend templates con Payment Element/Sheet + Apple/Google Pay + Express Checkout.
- Reutiliza el hook `stripe-safety-guard` de v5.25.
- Stitch designs (si VEG configurado), events catalog, MCP wiring oficial Stripe.
- Scope v1: Supabase únicamente; las 4 modalidades son flags así que el usuario opta in.

**Skill `/stripe-switch-account`** (`context: direct`):
- Rotación segura de credenciales Stripe. Wrapper UX sobre `switch_stripe_account` MCP tool.
- Muestra alias store actual, pide from/to, ejecuta dry-run, formatea plan en Markdown, pide confirmación literal, ejecuta, surface runbook de rollback si falla.
- Soporta `account_mode='standard'` (SaaS, e-commerce) y `'connect'` (marketplace).

**`specbox-stripe-mcp` v0.3.0**:
- Decoupled Connect-specific functionality — `setup_*` tools detectan account mode y se adaptan.
- Alias store en `state.json` para gestionar múltiples cuentas Stripe del mismo proyecto.
- Tool `switch_stripe_account` con dry-run + execute modes.

### Notes

- v0.3.0 backwards-compatible con proyectos onboardeados con v0.2.x — alias store se inicializa lazy.

---

## [5.26.0] - 2026-04-22 — "Supabase Edge Secrets"

Minor release que cierra la última acción manual del flujo `/stripe-connect`: inyectar secrets en las Edge Functions del proyecto Supabase. Cubre un gap del MCP oficial de Supabase ([supabase-community/supabase-mcp#120](https://github.com/supabase-community/supabase-mcp/issues/120)).

### Added

**Paquete nuevo `packages/specbox-supabase-mcp/`** (Python + FastMCP + httpx wrapper de Supabase Management API):
- Tool `set_edge_secret` — bulk POST `/v1/projects/{ref}/secrets`. Idempotente (GET previo para computar `previously_present`/`absent`). Valores **NUNCA** en logs ni Engram.
- Tool `list_edge_secrets` — GET read-only. Devuelve nombres + `updated_at` (nunca valores). Si `expected_names`, computa `missing_names`/`extra_names`.
- Tool `unset_edge_secret` — bulk DELETE con `confirm_token` literal. Pre-action Engram audit observation antes del DELETE.

**Skill `/stripe-connect` Paso 9.5**:
- Invoca `set_edge_secret` con los 4 secrets obtenidos de los pasos 9.5.2 previos.
- Graceful degradation si el MCP no está registrado (fallback a copy-paste manual en dashboard).

**CLAUDE.md**:
- Nueva sección "SpecBox-Supabase MCP (v0.1 alpha)" documentando 3 tools H1, principios (idempotencia por existence-by-name, PAT redactado en logs como `sbp_****<last6>`, valores nunca persisten), integración con `/stripe-connect`, y referencias.

### Notes

- 91% test coverage. Reuso de `lib/response.py`, `lib/engram_writer.py`, `lib/heartbeat.py` vía copy-from-stripe (Opción A del PRD §6).
- `base_url` para self-hosted Supabase parcialmente implementado (alpha) — refinamiento en v1.1.

---

## [5.25.0] - 2026-04-17 — "Stripe Connect"

Minor release introduciendo la primera skill operativa del dominio **billing**: `/stripe-connect` scaffoldea una integración Stripe Connect marketplace completa (Express + Direct charges + subscriptions embedded) en proyectos **Supabase + React/Flutter** en un único comando. PRD y plan técnico en [doc/prds/stripe_connect_skill_prd.md](doc/prds/stripe_connect_skill_prd.md) y [doc/plans/stripe_connect_skill_plan.md](doc/plans/stripe_connect_skill_plan.md).

### Added

**Nueva skill `/stripe-connect`** (`context: direct`, 12 pasos conversacionales):
- Detecta stack frontend (React / Flutter Web / Flutter Mobile), backend (Supabase obligatorio en v1), spec backend (Trello/Plane/FreeForm) y presencia de VEG
- Pregunta solo 2 cosas: confirmación stack + fee default %, todo lo demás se infiere
- Crea US-SPONSORSHIP con 12 UCs (UC-301..UC-312) en el spec backend del proyecto
- Escribe ~30 archivos: backend Supabase, frontend React/Flutter, docs parametrizadas, hook, Gherkin features, fragmento MCP
- Fallback automático a FreeForm local si el spec backend remoto está offline
- Abort limpio si backend no es Supabase (otros backends → v2)

**Templates parametrizados** (`.claude/skills/stripe-connect/templates/`):
- **Backend Supabase** (9 archivos): 5 Edge Functions (`create-rider-account-link`, `create-fan-subscription` con `application_fee_percent` dinámico, `cancel-fan-subscription`, `create-rider-dashboard-link`, `stripe-webhook`) + 4 migraciones SQL idempotentes (riders con stripe fields, sponsorships con lifecycle completo, stripe_processed_events para idempotencia, RLS policies default-deny)
- **Frontend React** (5 archivos): `stripe-provider.tsx` con `stripeAccount` header para Direct charges, `sponsor-rider-form.tsx` con `<PaymentElement>` + `<ExpressCheckoutElement>`, `use-sponsorship.ts`, `rider-onboarding-button.tsx` con warning fiscal, `package.json.fragment.json`
- **Frontend Flutter** (7 archivos): `stripe_service.dart` con Apple/Google Pay default on, `sponsor_rider_controller.dart` (variante Riverpod), `apple_pay_button.dart` + `google_pay_button.dart`, `rider_onboarding_launcher.dart` con modal de warning fiscal, `api_interceptor.dart` (Dio) con header `Stripe-Account`, `pubspec.fragment.yaml`
- **Documentación** (5 archivos): `infra-stripe-README.md` con checklist envvars + despliegue, `connect-setup.md` con activación Connect, `apple-google-pay-setup.md` (Merchant ID Apple, domain verification), `events-catalog.md` (10 eventos críticos con acción backend), `test-scenarios.md` (comandos `stripe trigger` + test clocks por UC)
- **Tests Gherkin** (12 archivos): `UC-301.feature` a `UC-312.feature` en español con mínimo 1 escenario feliz + 1 negativo cada uno. UC-306 incluye test de idempotencia con `stripe events resend`
- **MCP wiring** (1 fragmento JSON): cable el Stripe MCP oficial en `.claude/settings.local.json` del proyecto sin reemplazar config existente

**Hook `stripe-safety-guard.mjs`** (`.claude/hooks/`, también copiable a proyectos):
- PreToolUse sobre Write/Edit en `src/billing/`, `lib/billing/`, `supabase/functions/stripe-*|-webhook|create-*-subscription`
- 5 detectores BLOCKING con mensajes accionables: sk_live_* hardcoded, webhook sin `constructEvent`/`constructEventAsync`, webhook sin referencia a `stripe_processed_events`, `redirectToCheckout` o `ui_mode: hosted`, Payment Link URL
- Escape hatches: `// stripe-safety-guard:ignore` (línea), `:disable-file`, `:ignore-signature`, `:ignore-idempotency`
- Registrado en `.claude/settings.json` y `templates/settings.json.template` para todos los proyectos futuros
- **30 tests sintéticos** en `.quality/hooks/stripe-safety-guard.test.mjs` (10 positivos, 20 negativos). 30/30 pasan

### Design decisions (rechazos explícitos)

Documentados en el PRD para referencia futura:
- **NO envolver API de Stripe en tools MCP del engine** — duplica SDK oficial + Stripe MCP oficial, consume contexto. La skill orquesta piezas existentes
- **NO Destination/Separate charges en v1** — Direct charges obligatorio por constraint fiscal (seller como merchant of record → tributa su IRPF, no el de la plataforma)
- **NO Checkout hosted / Payment Links** — embedded-only por diseño (Payment Element + Payment Sheet)
- **NO Customer Portal** — con Direct charges el Customer vive en la connected account, cancelación via API propia (UC-309)
- **NO otros backends en v1** — Supabase únicamente; Neon/Firestore/FastAPI → v2 cuando aparezca proyecto real que lo pida
- **NO SaaS vanilla** — `/stripe` hermana (sin Connect) → v2 reutilizando templates depurados con Connect

### Caso piloto de validación

Marketplace de micropatrocinios para pilotos de motociclismo no profesionales. Fans suscriben al piloto 10/15/20€ mensuales. Plataforma cobra fee dinámico (15% estándar, menos para ambassadors) vía `application_fee_percent`. Pilotos reciben el resto directamente en su cuenta Stripe Connect Express. Validación end-to-end reservada para la fase manual sobre el proyecto real (AC-41..AC-44 del PRD).

### Scope v1 vs fuera de v1

Ver [doc/prds/stripe_connect_skill_prd.md](doc/prds/stripe_connect_skill_prd.md) sección "Alcance" para el desglose completo.

---

## [5.23.0] - 2026-04-16 — "Full Mutations"

Minor release que cierra el hueco de mutaciones granulares sobre spec-driven items. Tool count: 114 → **138** (+24). Diseño técnico completo en [doc/design/v5.23.0-full-mutations.md](doc/design/v5.23.0-full-mutations.md).

### Added

**Tier 1 — Granular mutations** (`server/tools/spec_mutations.py` — 8 tools):
- `update_uc` / `update_uc_batch` — UC metadata edits (name, description, hours, screens, actor, context, milestone, satellite) with merge semantics
- `update_us` — US metadata edits with optional milestone propagation to child UCs (existing milestones never overwritten)
- `update_ac` / `update_ac_batch` — AC text/done rewrites; distinct from mark_ac which only toggles done
- `add_ac` — auto-numbered AC append (finds max AC-NN and increments)
- `delete_ac` — AC deletion with automatic renumber of subsequent ACs
- `add_uc` — auto-numbered UC creation under existing US (finds max UC-NNN and increments)

**Tier 2 — Milestone & multirepo** (`server/tools/milestone_management.py` — 8 tools):
- `set_uc_milestone` / `set_uc_milestone_batch` — assign H1..H4 milestones with post-hoc distribution report
- `set_uc_satellite` — assign UC to a satellite repo with validation
- `get_milestone_status` — sprint status filtered by milestone (counts by state, AC pass rate, blocked items)
- `rebalance_milestones` — greedy algorithm to align AC distribution with target percentages (dry_run=True default)
- `get_satellite_queue` — ordered queue of backlog UCs per satellite, optionally filtered by milestone
- `sync_multirepo_state` — propagate satellite labels from orchestrator settings.local.json via uc_prefix matching
- `get_cross_repo_dependencies` — detect UC-NNN references across different satellites

**Tier 3 — Board operations** (`server/tools/board_operations.py` — 5 tools):
- `validate_ac_quality` — retroactive Definition Quality Gate scan (flags too_short, vague, not_testable ACs)
- `set_ac_metadata` — attach evidence_url/screenshot/verdict to a single AC via META JSON suffix
- `link_uc_parent` — formalize UC-to-UC relationships (absorbs, blocks, depends_on, supersedes, related_to) with audit comment on BOTH cards
- `delete_uc` — soft-delete via archive_item; optional absorbed_by link before archival
- `get_board_diff` — compare two timestamped board snapshots (added/removed/modified UCs, milestone moves, AC changes)

**Tier 4 — Acceptance automation** (`server/tools/acceptance_automation.py` — 3 tools):
- `bulk_update_hours_from_description` — parse "Horas estimadas: N" patterns from UC descriptions and sync to hours field (dry_run default; conflict detection)
- `estimate_from_ac` — classify ACs as simple(2h)/integration(4h)/e2e(6h) and return estimate (3 strategies: specbox_heuristic, fibonacci, t_shirt)
- `milestone_acceptance_check` — consolidated acceptance validation per milestone with GO/CONDITIONAL_GO/NO_GO verdicts

**ABC deltas** (+3 methods on SpecBackend, implemented in all 3 backends):
- `update_acceptance_criterion(text?, done?)` — rewrite AC text and/or toggle done state
- `delete_acceptance_criterion(ac_id)` — remove AC from UC (precondition for delete_ac renumber)
- `archive_item(item_id, reason)` — soft-delete per backend (Trello: archived list/label; Plane: cancelled state+comment; FreeForm: archive.json)

**Infrastructure**:
- `server/tools/_mutation_helpers.py` — shared constants (MILESTONES, LINK_TYPES, VERDICT_TYPES), validators, finders, merge_meta, classify_ac, compute_distribution
- TrelloClient: update_checklist_item extended with name param, new delete_checklist_item
- PlaneClient: new delete_work_item method
- 78 new tests across 5 files, 0 regressions on 350-test suite

**Design principles** (documented in design doc, enforced mechanically):
- Batch-first: batch tools call list_items once, granular docstrings reference batch equivalents
- Idempotent: every mutation returns reason="no_change" on repeat calls
- Structured errors: {error, code} dicts, never raised exceptions to MCP client
- Validation in tool layer: milestone/satellite/link_type validated before backend dispatch

### AC-21 (post-merge manual test)

Smoke test end-to-end contra el board real `69cd517b0a0bde849084a262` (proyecto `potencial_digital_2026`) verificando `set_uc_milestone_batch`, `bulk_update_hours_from_description`, `get_milestone_status("H1")`, y `milestone_acceptance_check("H1")`.

---

## [5.22.1] - 2026-04-15

Patch release centrado en consolidar el modelo de frontmatter de skills, eliminar los `commands/*.md` legacy del repo y dejar el compliance audit del propio engine en 100% sin falsos negativos estructurales.

### Fixed
- **Skill Frontmatter Bug** — skills operativos (`plan`, `prd`, `visual-setup`) usaban `context: fork` + `agent: Plan`, lo que los delegaba al sub-agente nativo Plan de Claude Code (arquitecto read-only). Resultado: los skills podían llamar MCPs externos (Trello, Stitch) pero no podían escribir archivos al filesystem local
  - Síntoma reproducible: `/plan US-24` adjuntaba el plan como PDF en la card de Trello pero nunca creaba `doc/plans/us-24_plan.md`
  - Fix: los 3 skills pasan a `context: direct` (ejecución en sesión principal con herramientas completas)
  - Los 4 skills read-only (`explore`, `adapt-ui`, `check-designs`, `optimize-agents`) siguen con `context: fork` + `agent: Explore` — correcto, son análisis sin escritura
- **Frontmatter obsoleto en `acceptance-check` y `quickstart`** — ambos skills tenían el formato antiguo `context: fork` + `mode: direct` + `triggers:` + `tools:` (campos que el harness actual ignora). Normalizados a `context: direct` con `description:` extendido con triggers inline — ahora son auto-descubribles y se ejecutan en sesión principal con permisos de escritura (ambos crean archivos)
- **`/compliance` self-audit falso negativo** — `specbox-audit.mjs` reportaba 2 checks críticos cuando se ejecutaba sobre el propio engine (`Registered in engine state` y `Spec-driven configured`). Son comprobaciones que no aplican al engine como meta-proyecto: no se onboardea consigo mismo ni usa su propia pipeline Trello/Plane/FreeForm. Añadida detección `IS_SELF_AUDIT` que resuelve cuando `projectPath === ENGINE_ROOT` y marca esos checks como "N/A (self-audit)" con pass=true. El header del report muestra "(self-audit)" y el JSON incluye `self_audit: true` para trazabilidad. Score del self-audit ahora: 100% A+

### Changed
- **`commands/audit.md` migrado a skill** — `/audit` pasa a ser `.claude/skills/audit/SKILL.md` con frontmatter correcto (`context: direct` — escribe PDF + JSON de evidencia). Contenido funcional idéntico al command legacy. Ahora descubrible por el harness vía `description:` y alineado con el resto de skills del engine
- **CLAUDE.md — sección "Skill Frontmatter Model"** — nueva sección documentando cuándo usar cada combinación (`direct` vs `fork + agent: Explore`) y cuáles son combinaciones rotas (`fork` solo, `fork + agent: Plan` para skills de escritura). Incluye test rápido para detectar skills mal configurados
- **CLAUDE.md — afirmaciones obsoletas corregidas** — eliminada la mención a `commands/` como "referencia legacy" y la instrucción de reinstalar tras editar un SKILL.md (los skills globales son symlinks al repo, los cambios se propagan automáticamente)
- **Tabla "Available Skills" actualizada** — `prd`, `plan`, `visual-setup`, `acceptance-check`, `quickstart`, `audit` ahora muestran el modo real (`direct`)
- **`install.sh` limpio** — eliminada toda la lógica de instalación/uninstall de `commands/*.md` (ya no existe ese directorio); removida variable `CLAUDE_COMMANDS_DIR`. La sección "Commands:" del summary final también eliminada. El installer ahora gestiona solo skills + hooks + GGA + VSCode extension

### Removed
- **7 commands legacy** eliminados del repo (`commands/adapt-ui.md`, `feedback.md`, `implement.md`, `optimize-agents.md`, `plan.md`, `prd.md`, `quality-gate.md`) y sus symlinks colgantes en `~/.claude/commands/`. Todos tenían equivalente activo en `.claude/skills/*` desde hace versiones
- **`commands/audit.md`** — migrado a `.claude/skills/audit/SKILL.md`, el archivo command original eliminado
- **Directorio `commands/` del repo** — queda vacío y git lo purga automáticamente. El concepto de "command legacy" desaparece del engine por completo — a partir de esta versión **todos los slash commands son skills**

### Added
- **`manual-test` al repo** — el skill `manual-test` vivía suelto en `~/.claude/skills/manual-test/` como directorio plano sin versionar. Se trae al repo (`.claude/skills/manual-test/` con `SKILL.md` + `manifest.yaml` + `templates/`) para que sea symlinkeable como el resto tras `install.sh`

### Compliance
- `/compliance` sobre el propio engine: **100% — A+ (Full Compliance)** tras todos los fixes de esta versión. Todos los bloques a 100% sin críticos, warnings o recommendations

---

## [5.20.1] - 2026-04-10

### Fixed
- **Hook Schema Fix (complete)** — removed invalid `blocking` field and corrected `timeout` from milliseconds to seconds across settings.json and template
  - `blocking` is not a valid Claude Code hook field — PreToolUse hooks block automatically on non-zero exit
  - `timeout` was in milliseconds (5000, 10000, 60000) but Claude Code expects seconds (5, 10, 60)
  - `server/tools/hooks.py`: `list_hooks` now infers blocking status from event type (`PreToolUse`) instead of reading the removed field
  - Root cause: v5.19.0 "Hook Schema Fix" corrected `matcher` format but left `blocking` and `timeout` units untouched

---

## [5.20.0] - 2026-04-10

### Added
- **Multi-Repo Mode** — opt-in support for projects with multiple repositories sharing a single board
  - `lib/config.mjs`: `getProjectConfig()` returns `orchestratorRoot` (defaults to `'.'` for mono-repo, resolves to orchestrator path for satellites)
  - `design-gate.mjs`: resolves Stitch designs from orchestrator repo via `orchestratorRoot`
  - `e2e-gate.mjs`: fallback validator script resolution from orchestrator repo
  - `onboard_project()`: new optional params `multirepo_role` ("orchestrator"|"satellite") and `orchestrator_project` (name of orchestrator in registry)
  - Satellite onboarding auto-generates `.claude/settings.local.json` with multi-repo config and inherited `boardId`
  - `find_next_uc()`: new optional `uc_scope` param to filter UCs by satellite assignment
  - Registry and meta.json store `multirepo_role` and `multirepo_group` fields

### Design Decisions
- **Not preselected**: multi-repo is disabled by default. Only activates when `multirepo.enabled: true` is in settings.local.json
- **100% backwards-compatible**: all defaults reproduce mono-repo behavior (`orchestratorRoot='.'`, `uc_scope=None`, optional params with empty defaults)
- **Upgrade-safe**: multi-repo config lives in `settings.local.json` which is never touched by `upgrade_project`
- **Install-safe**: hook changes use additive patterns with fallbacks — `path.join('.', x)` === `path.join(x)`

---

## [5.6.0] - 2026-03-23

### Added
- **Stitch MCP Proxy** — 13 tools que cubren los 12 tools nativos de Google Stitch + gestion de API Key por proyecto
  - `stitch_set_api_key` — configurar API Key por proyecto (session + disco con base64)
  - `stitch_create_project` — crear proyecto/workspace en Stitch
  - `stitch_list_projects`, `stitch_get_project` — descubrimiento y detalles de proyectos
  - `stitch_list_screens`, `stitch_get_screen` — listado y metadata de pantallas
  - `stitch_fetch_screen_code` — descarga HTML raw de diseños generados
  - `stitch_fetch_screen_image` — screenshots hi-res en base64
  - `stitch_generate_screen` — generacion de pantallas desde prompt (timeout 6 min)
  - `stitch_edit_screen` — edicion de pantallas existentes con prompt
  - `stitch_generate_variants` — variantes con CreativeRange (REFINE/EXPLORE/REIMAGINE) y Aspects
  - `stitch_extract_design_context` — extraccion de Design DNA (fuentes, colores, layouts)
  - `stitch_build_site` — ensamblaje de sitios multi-pagina mapeando screens a rutas
- **StitchClient** — cliente async MCP JSON-RPC con soporte SSE, retry con backoff exponencial
- **Stitch usage telemetry** — `stitch_usage.jsonl` por proyecto para tracking de uso
- **auth_gateway extended** — `store_stitch_credentials()` / `get_stitch_client()` per-project con fallback a disco

### Tests
- `tests/test_stitch.py` — 17 tests (payloads JSON-RPC, auth headers, SSE parsing, errores, telemetria)

---

## [5.5.0] - 2026-03-23

### Added
- **Remote Management** — operabilidad remota completa desde iPhone (Claude.ai iOS + MCP remoto) y WhatsApp/Discord (OpenClaw Gateway)
- **Heartbeat Observability** — nuevo tool `get_heartbeat_stats` con metricas 24h, stale detection, y logging JSONL por proyecto
- `GET /api/heartbeats/stats` REST endpoint protegido con Bearer auth
- **Conversational Summaries** — campos `summary` y `summary_table` en tools de live_state para respuestas humanizadas en movil
  - `get_project_live_state` — summary Markdown (max 300 chars)
  - `get_all_projects_overview` — summary_table con tabla Markdown
  - `get_active_sessions` — summary conversacional en espanol
- **Spec-Driven Summaries** — campos `summary` + `generated_at` en 6 tools de escritura:
  - `move_uc`, `mark_ac`, `mark_ac_batch` — confirmacion humanizada
  - `get_board_status`, `get_sprint_status` — resumen compacto
- **Skill `/remote`** — skill para OpenClaw Gateway (WhatsApp/Discord), texto plano max 2000 chars
- **E2E Seed Strategies** — gestion del ciclo de vida de datos de prueba para acceptance tests (Flutter + React)
- **AG-09a Enhanced** — integracion E2E Seed Lifecycle con Gherkin BDD

### Documentation
- `doc/remote-management/setup-claude-ios.md` — guia paso a paso para Claude.ai iOS
- `doc/remote-management/setup-openclaw.md` — configuracion OpenClaw para WhatsApp/Discord
- `doc/prd/PRD-remote-management.md` — PRD completo (dogfooding con SpecBox)
- `doc/plans/remote-management-plan.md` — plan tecnico en 5 fases
- `doc/research/remote-management-audit.md` — auditoria de Sala de Maquinas

### Tests
- `tests/test_heartbeat_stats.py` — 8 tests de observabilidad
- `tests/test_remote_summaries.py` — 7 tests de summaries

### Version Cleanup
- Todas las referencias de version actualizadas a v5.5.0 en agents, templates, architecture, scripts
- Eliminado residuo de versiones anteriores (v3.9.0, v4.1.0, v4.2.0) en headers de agentes

## [5.2.0] - 2026-03-17

### Added
- **Remote State Management** — gestionar proyectos desde iPhone via Claude.ai iOS + MCP remoto
- **Heartbeat Protocol** — `report_heartbeat` MCP tool + `POST /api/heartbeat` REST endpoint para recibir snapshots consolidados de estado de cada proyecto
- **heartbeat-sender.sh** — hook que auto-detecta estado local (git branch, coverage, checkpoint, feedback) y envia heartbeat al VPS; queue local para offline resilience
- **GitHub Sync** — `github_sync.py` lee `specbox-state.json` de repos via GitHub API; solo actualiza si heartbeat tiene > 30 min de antiguedad
- `POST /api/sync/github` REST endpoint para trigger manual o cron de sync
- **4 MCP tools conversacionales** para iPhone:
  - `get_project_live_state(slug)` — "¿Como va McProfit?"
  - `get_all_projects_overview()` — resumen de todos los proyectos con health emoji
  - `get_active_sessions()` — proyectos con sesion activa
  - `refresh_project_state(slug)` — force refresh desde GitHub
- **project_state.json** — snapshot consolidado por proyecto (overwrite, no append)
- **Session decay lazy** — `session_active=false` si no hay heartbeat en 30 min (sin cron)
- **specbox-state.json** — escrito en raiz del repo tras heartbeat exitoso para GitHub sync
- **Pending heartbeat queue** — `.quality/pending_heartbeats.jsonl` para reintentos
- `SPECBOX_SYNC_TOKEN` y `GITHUB_TOKEN` env vars en docker-compose.yml
- `on-session-end.sh` y `implement-checkpoint.sh` extendidos con emision de heartbeat
- 36 nuevos tests (test_heartbeat, test_github_sync, test_live_state)

### Technical Plan
- `doc/plans/remote_state_management_plan.md`

## [5.1.0] - 2026-03-13

### Changed
- **Rebrand**: SDD-JPS Engine → SpecBox Engine by JPS — display text only, all filesystem paths and API preserved
- `ENGINE_VERSION.yaml`: brand "SpecBox Engine", brand_full "SpecBox Engine by JPS", version 5.1.0, codename "SpecBox"
- All Skills, Agent prompts, templates, server docstrings, install.sh, and dashboard updated
- Tests updated to reflect new brand name
- CHANGELOG header updated (historical entries preserved as-is)

### Also Changed (v5.1.0 phase 2)
- MCP server ID: `sdd-jps-engine` → `specbox-engine` (FastMCP name in server.py)
- Package name: `sdd-jps-engine` → `specbox-engine` (pyproject.toml)
- Docker service/container: `sdd-jps-engine` → `specbox-engine` (docker-compose.yml)
- All ~40 filesystem path references: `sdd-jps-engine/` → `specbox-engine/` (agents, templates, docs, skills, commands)
- GitHub URLs: `jesusperezdeveloper/sdd-jps-engine` → `jesusperezdeveloper/specbox-engine`
- Baseline file: `.quality/baselines/sdd-jps-engine.json` → `specbox-engine.json`
- Migration engine source: `ENGINE_SOURCE = "specbox-engine"` (migration.py)
- Hook client name: `specbox-engine-hook` (mcp-report.sh)

### Not Changed
- Historical documents: ENGINE_VERSION.yaml changelog, doc/prds/, doc/plans/, CHANGELOG entries
- No tool names, endpoints, or API contract changes

## [5.0.0] - 2026-03-13

### Added
- **Spec-Code Sync Layer** — automatic PRD update with Implementation Status after each /implement phase
- **Delta Generator** — structured Markdown delta blocks per phase (max 500 tokens)
- **PRD Writer** — append-only PRD writing with Implementation Status sections
- **PRD Parser** — parse Implementation Status from PRDs into structured data
- MCP tools `get_implementation_status` and `write_implementation_status`
- `/implement` SKILL.md steps 5.1.1a (delta capture), 7.7a (freeform write), 8.5.1a (spec-driven write)
- **/quickstart** skill — interactive tutorial guiding new devs through the full pipeline in < 5 min
- **Hint Manager** — contextual hints system with `.quality/hint_counters.json` (disappear after 3 uses)
- MCP tools `get_skill_hint` and `record_skill_hint`
- **Skill Registry** — external skill manifests, install/uninstall, auto-discovery
- MCP tools `discover_skills`, `validate_skill_manifest`
- `templates/skill-manifest.yaml.template` for external skill authors
- **/acceptance-check** skill — standalone BDD acceptance without full /implement
- MCP tools `run_acceptance_check` and `get_acceptance_report`
- `templates/github-actions/acceptance-gate.yml` — GitHub Action for automated acceptance gates
- **Benchmark Snapshot** — aggregated, anonymized project metrics
- MCP tool `generate_benchmark_snapshot`
- REST endpoint `GET /api/benchmark/public`
- 114+ new tests covering all v5.0 modules

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
