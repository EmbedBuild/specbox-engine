# Changelog

All notable changes to SpecBox Engine (formerly SDD-JPS Engine) are documented here.

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
