# v7.0 Migration Guide — Stitch Native Chain Cutover

> **Status**: planned cutover. Not yet released.
> **Target release**: v7.0 (date TBD post-validation of v6.4.0 adoption).
> **Companion PRD**: [doc/prd/stitch_native_migration_prd.md](../prd/stitch_native_migration_prd.md)

## TL;DR

In **v6.4.0** (the release this guide ships with), the **Stitch native
Material 3 chain** lands as opt-in. The legacy `inline-prefix` workaround
(prepending `DESIGN.md` to every generation prompt) still works.

In **v7.0**, `inline-prefix` is **removed**. Every project using Stitch must
have migrated to `stitch.contract=native_v2` before upgrading.

This document is the operational checklist for that migration.

## Why we're doing the cutover

The native chain is strictly better:

| Concern | inline-prefix (v5.31) | native chain (v6.4.0+) |
|---|---|---|
| DS persistence | None — re-emit DESIGN.md each call | Server-side, project-level |
| Token cost per generation | DESIGN.md serialized in every prompt | Only `designSystem: "assets/{id}"` parameter |
| Cross-screen coherence | Best-effort (LLM re-interprets DESIGN.md) | Guaranteed (DS applied server-side) |
| Iteration on theme | Edit DESIGN.md + regenerate all screens | `update_design_system` (~6s, no regen) |
| Re-theme of a project | Impossible (one screen at a time) | `apply_design_system` to instance batch |
| Material 3 validation | Local heuristic | Server-side enum validation (65 fonts, etc.) |

Maintaining both pipelines is deuda — `generate_design_md_tool`,
`upload_design_md_to_stitch`, the `stitch_generate_screen_v2` adapter and
the `validate_stitch_prompt` validator all carry conditional branches that
will accumulate bugs.

## What v6.4.0 ships (PR-1)

Foundation. No project is forced to migrate yet.

- The 6 native MCP tools (`stitch_upload_design_md` …
  `stitch_apply_design_system`).
- The REST `batchCreate` helper for `DESIGN.md` > 5 KB.
- `server/stitch_enums.py` with 65 fonts + the real `ColorVariant` /
  `Roundness` values from `tools/list`.
- The VEG ↔ Material 3 mapper.
- The `stitch.contract` setting (default `native_v2` for new projects;
  `inline_prefix_v1` honored for old projects).
- The quota subsystem removed (`get_stitch_quota_status`, hook, settings).

## What v7.0 will ship (PR-2 and PR-3)

PR-2 will:

- Refactor `generate_design_md_tool` to emit strict Material 3
  frontmatter.
- Rewire `stitch_generate_screen_v2` to omit color/font/roundness from
  the prompt when a DS is applied.
- Introduce the `/visual-setup --migrate-stitch` skill with the 6
  migration cases (A–F) documented in the PRD.
- Add `detect_stitch_migration_case` MCP tool.
- Add telemetry under `.quality/logs/stitch-migration.jsonl`.

PR-3 (the v7.0 cut) will:

- Delete `upload_design_md_to_stitch` (inline-prefix path).
- Delete the `stitch.contract=inline_prefix_v1` branch.
- Make `upgrade_project` fail loudly on projects still on
  `inline_prefix_v1` instead of warning.
- Bump engine to **v7.0.0**.

## Migration cases (matches the PRD)

| Case | State | v7.0 action |
|---|---|---|
| **A** Fresh post-v6.4 | `stitch.contract=native_v2` already | no-op |
| **B** Pre-migration, Stitch unused | settings.stitch present but 0 designs generated | flip marker, no data migration |
| **C** DESIGN.md exists, no Stitch project | `doc/design/DESIGN.md` present, no `stitch.projectId` | `/visual-setup --migrate-stitch` rewrites DESIGN.md to strict M3, creates project, bootstraps DS |
| **D** Stitch project with screens, no DS | `stitch.projectId` set, screens exist, no DS applied | **D.2 retroactive** assisted (default chosen by maintainer) — preview, then `apply_design_system` to all instances after `MIGRATE-RETROACTIVE` literal confirmation |
| **E** DESIGN.md custom | User-edited DESIGN.md not following SpecBox v5.31 conventions | mapping proposal generated; user must approve via `--apply-proposal` |
| **F** Multirepo | orchestrator + satellites | only orchestrator migrates; satellites resolve via `orchestratorRoot` |

## Pre-v7 checklist (do during v6.4 timeframe)

For each project that uses Stitch:

- [ ] Confirm `stitch.contract` in `.claude/settings.local.json`. If
  missing, set explicitly to `inline_prefix_v1` (no behaviour change) or
  start the migration to `native_v2`.
- [ ] Verify the project has `STITCH_API_KEY` provisioned (whether via
  `stitch_set_api_key` MCP tool or otherwise). The native chain requires
  the same API key as before; no OAuth is needed.
- [ ] If the project has a `doc/design/DESIGN.md`, make sure it has a
  YAML frontmatter at top. The migration tool needs it as input; if
  absent, the migration falls back to "case E" and asks the user.
- [ ] If you have a `.quality/stitch_quota.json` cache, you can delete
  it — it's no longer read by anything.
- [ ] If you have custom hooks referencing `stitch-quota-guard.mjs`,
  delete the entries; the hook was removed in v6.4.0.

## Rollback

If `apply_design_system` produces unacceptable visual regressions on
existing screens (case D.2):

1. The migration tool keeps the previous theme in
   `.quality/stitch_migration_state.json`.
2. `update_design_system` with the prior theme reverts.
3. Failing that, the original Stitch project remains intact in the
   user's account — you can recreate from scratch and re-import.

The v7.0 release will refuse to install if the rollback path is broken,
to avoid leaving projects in an unrecoverable state.

## Open questions for v7.0 RC

- **Quorum**: at what % adoption of `native_v2` across `list_onboarded_projects`
  do we cut v7.0? Working assumption: ≥80%, measured by the telemetry
  introduced in PR-2.
- **Communication channel**: post in the SpecBox project list with a
  one-week warning before cutover.
- **CI gate**: should `upgrade_project` in v7.0 RC fail the upgrade if
  `stitch.contract=inline_prefix_v1` and Stitch is configured? Probably
  yes — fail-fast is better than silent breakage.

## References

- PRD: [doc/prd/stitch_native_migration_prd.md](../prd/stitch_native_migration_prd.md)
- Smoke evidence: [.quality/evidence/stitch_smoke/smoke_mcp_v2_report.md](../../.quality/evidence/stitch_smoke/smoke_mcp_v2_report.md)
- Tool schema (real, from MCP `tools/list`): [.quality/evidence/stitch_smoke/mcp_tools_schema.json](../../.quality/evidence/stitch_smoke/mcp_tools_schema.json)
- Mapper: [server/veg/material3_mapper.py](../../server/veg/material3_mapper.py)
- Native chain wrappers: [server/stitch_client.py](../../server/stitch_client.py)
