---
generated_at: 2026-05-27T00:15:00Z
generator: claude-opus-4-7-autopilot
schema_version: 1
project: specbox-engine
session_id: v6.4.0-stitch-native-migration-pr1-autopilot
trigger: end-of-autopilot-session
ttl_minutes: 4320
branch: feature/stitch-native-migration
active_uc: null
next_action: human_review_pr_then_smoke_then_merge
---

# SpecBox Handoff — v6.4.0 "Stitch Native Migration" PR-1 ready for review

## 🎯 What I shipped in autopilot

Scope original (autopilot agresivo total, ~37–52h estimadas): aplazado al PR-2.
Scope realista entregado esta noche: **PR-1 foundation + cleanup + tests +
docs**, mergeable mañana sin riesgo y sin tocar las tools que aún dependen del
mapping VEG↔M3 que necesita validación humana.

## Summary

| Phase | Status | Result |
|---|---|---|
| F1 — Smoke test gate | ✅ pass | 8/8 steps verde contra MCP real |
| F2 — PRD + 13 UCs | ✅ done | doc/prd/stitch_native_migration_prd.md |
| F3 — Foundation técnica | ✅ done | enums + 6 wrappers + REST helper |
| F4 — VEG ↔ M3 mapper | ✅ done | 6 archetypes + brand kit + JTBD overrides |
| F8 — Quota purge | ✅ done | módulo entero + hook + settings + tests |
| F11 — Tests dedicados | ✅ done | 40 new tests, 100% pass |
| F10 — Docs + version | ✅ done | v6.4.0 bumped, CLAUDE.md updated |
| **F5, F6, F7, F9** | ⏸ aplazado PR-2 | mapping VEG↔M3 necesita tu OK matinal |

**Suite final**: `1249 passed, 71 skipped, 0 failed` (+57 vs baseline).

**Commits in branch** (`feature/stitch-native-migration`):
1. `706b8c3` F1+F2 — smoke tests verde + PRD + 13 UCs
2. `cfbe96a` F3+F4+F8+F11 — foundation + mapper + quota purge + tests
3. `84876db` F10 — docs + version bump to v6.4.0

## Critical findings during F1 (these CHANGE the architecture)

The smoke test was the gate, and it surfaced important discrepancies between
docs and reality:

1. **`extract_design_context` and `build_site` ARE NOT in the Stitch MCP**.
   Both lived in your `StitchClient` for months. `tools/list` confirms 14
   tools, neither is among them. Removed in PR-1.

2. **`create_design_system_from_design_md` IS available via MCP** (verified
   end-to-end in smoke v2). The CLAUDE.md statement "Stitch MCP no expone hoy
   un endpoint nativo de attach" was false. Removed.

3. **Stitch MCP is free of charge**. The 350+200/month limit applies to the
   Stitch web UI only. The Gemini CLI extension literally states "Stitch MCP
   is free of charge". The entire quota subsystem in v5.31 was solving a
   non-problem. **Removed in PR-1**.

4. **`get_project` requires `name` (full path "projects/{id}"), NOT
   `projectId`**. Your v5.31 client uses `projectId`. This worked for some
   payloads via server alias tolerance, but it's brittle. In PR-1 the new
   wrappers use `name` correctly; the legacy `get_project` was not touched
   yet (PR-2 scope).

5. **Real enums differ from public docs**:
   - 65 fonts, not 9. Includes `GEIST`, `DM_SANS`, `JETBRAINS_MONO`, all the
     Google Sans family.
   - `TONAL_SPOT`, not `TONAL`.
   - `NEUTRAL` exists (not in docs).
   - `ROUND_TWO` exists (not in docs).
   - `AGNOSTIC` DeviceType does **not** exist (was in your enums local).
   These are pinned in `server/stitch_enums.py` with a test that diffs against
   the canonical schema JSON, so future Google updates surface as test
   failures.

## Latencies (real, smoke v2)

| Operation | Observed | Configured timeout |
|---|---|---|
| `create_project` | 1.1s | 30s |
| `upload_design_md` (MCP, <5KB) | 4.2s | 180s |
| `upload_via_rest_batch_create` | similar (smoke v1) | 180s |
| `get_project` | 0.9s | 30s |
| `list_design_systems` | 1.5s | 30s |
| **`create_design_system_from_design_md`** | **43s** | 180s |
| `update_design_system` | 6.3s | 180s |
| **`apply_design_system`** | **19s** | 180s (per screen) |

## What you need to do tomorrow morning

### 1. Open the PR

Branch `feature/stitch-native-migration` is pushed (or about to be — see
the last todo). PR URL will be in the next-to-last log line.

### 2. Review focus (in this order)

1. **`doc/prd/stitch_native_migration_prd.md`** — read this first. It captures
   the "why" of every UC, the canonical decisions you took (D.2 retroactive,
   v7.0 cutover), and the risk matrix. ~30 min.

2. **`server/veg/material3_mapper.py` — the VEG↔M3 mapping table** (lines
   115–162). This is the **biggest opinionated choice** in the PR. The
   archetypes you have are:
   - corporate → INTER + NEUTRAL + ROUND_FOUR + #1A56DB
   - startup → SPACE_GROTESK + FIDELITY + ROUND_EIGHT + #7C3AED
   - creative → PLAYFAIR_DISPLAY + EXPRESSIVE + ROUND_TWELVE + #EC4899
   - consumer → DM_SANS + VIBRANT + ROUND_EIGHT + #F59E0B
   - gen_z → BEBAS_NEUE + RAINBOW + ROUND_FULL (DARK) + #14F195
   - gobierno → INTER + MONOCHROME + ROUND_FOUR + #1F2937

   If any feel off, this is the cheapest moment to change: edit
   `_ARCHETYPE_TABLE` and the test `test_reverse_map_corporate_theme` (which
   pins the expected score). PR-2 will depend on these.

3. **`.quality/evidence/stitch_smoke/`** — reproduce the smoke if you want
   independent verification. `STITCH_API_KEY=... python3 smoke_test_mcp_v2.py`
   should print `EXIT=0` and write a `pass` verdict.

4. **CLAUDE.md sections** — the rewritten "Stitch MCP Proxy" and
   "Stitch Autopilot" sections. Particularly check that the cutover plan
   description (v7.0 cutover) reflects what you decided.

### 3. Manual smoke (5 minutes)

Quickest way to verify the wrappers work end-to-end in your environment:

```bash
cd /Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/specbox-engine
STITCH_API_KEY="<your-key>" python3 .quality/evidence/stitch_smoke/smoke_test_mcp_v2.py
# Expected: EXIT=0, verdict pass, asset_id resolved.
```

If that passes, the chain works. The wrappers are thin facades over the same
JSON-RPC the smoke uses, so green smoke = green wrappers.

### 4. Merge & tag

If review passes:

```bash
gh pr merge <PR_NUMBER> --squash --delete-branch
git checkout main && git pull
git tag -a v6.4.0 -m "v6.4.0 — Stitch Native Migration (PR-1 foundation)"
git push origin v6.4.0
```

### 5. Stitch cleanup (manual UI)

Smoke v1 + v2 created 2 projects in your Stitch workspace named
`SmokeTest-NativeChain-*` and `SmokeMCPv2-*` that the API key cannot delete
(returned 403 PERMISSION_DENIED on REST DELETE). Delete them from the Stitch
web UI when you have a minute — they're not blocking anything but they clutter
`stitch_list_projects`.

## What I left for PR-2 and why

| Phase | What it does | Why deferred |
|---|---|---|
| F5 — `generate_design_md_tool` refactor to M3 | Emit Material 3 frontmatter from VEG inputs | Depends on mapper validation (see point 2 above) |
| F6 — `stitch_generate_screen_v2` prompt clean | Omit colors/fonts/roundness when DS applied | Behavioral change — needs visual regression smoke first |
| F7 — `/visual-setup --migrate-stitch` skill | Full 6-case update flow including D.2 retroactive preview | Largest behavioral piece; benefits from review of F3+F4 first |
| F9 — `upgrade_project` integration + `version_matrix` column | Detect & hint per migration case | Depends on F7 |
| Telemetry JSONL + stats tool | `.quality/logs/stitch-migration.jsonl` | Bound to F7 |
| `doc/decisions/stitch_native_chain.md` | Architectural decision record | Will reference v6.4.0 evidence; better authored once F5 lands |

PR-2 scope estimate: ~20–25h (the "process" side of the migration).
Recommended timing: once you OK the mapping table and merge PR-1, I can pick
PR-2 up in a fresh autopilot session.

## Decisions I took unilaterally

1. **Mapping VEG↔M3 table content**. I tried to match each archetype's
   character from `doc/templates/veg-archetypes.md`. If you disagree on
   specific values, the table is in one place
   (`server/veg/material3_mapper.py` lines 115–162).
2. **Removed `flash_safety_net` from `stitch_generate_screen_v2`** — this
   is a small behavioural change. The wrapper now signs differently. No
   external caller in the repo uses this param (verified by grep), but I
   left a `Note:` in the docstring explaining the removal in case an
   external integration cared.
3. **Removed `extract_design_context` and `build_site` MCP tools** without
   a deprecation period. Justification: they were never functional —
   their underlying server endpoints don't exist. Anybody calling them
   was already broken; an explicit `AttributeError` is better than a
   silent timeout.
4. **PR-1 instead of full autopilot agresivo**. After F1 revealed the
   discrepancies, doing all 13 UCs in one PR became risky. PR-1 ships the
   reversible foundation; PR-2 ships the behavioural migration. You can
   pause between them.

## Risks remaining

| Risk | Mitigation in place |
|---|---|
| You don't like the VEG↔M3 mapping | Table is in one place; trivial to edit + run `pytest tests/test_veg_material3_mapper.py` |
| Stitch changes the API again | Smoke is reproducible and pinned in the repo (`mcp_tools_schema.json`); CI can flag drift |
| Inline-prefix users break at v7.0 | v7.0 PR will gate `upgrade_project` with a loud error; multiple v6.x months between now and then to migrate |
| Existing tests broke during F8 cleanup | Verified `1249 passed, 71 skipped, 0 failed` post-cleanup |

## Files touched (summary)

- **3 new modules**: `server/stitch_enums.py`, `server/veg/__init__.py`,
  `server/veg/material3_mapper.py`
- **4 modified**: `server/stitch_client.py`, `server/tools/stitch.py`,
  `server/tools/stitch_v2.py`, `server/stitch_orchestration/fallback.py`
- **5 deletions**: `server/stitch_quota/__init__.py`,
  `server/stitch_quota/computation.py`, `.claude/hooks/stitch-quota-guard.mjs`,
  `tests/test_stitch_quota.py`, `.quality/stitch_quota.json`
- **3 new tests**: `tests/test_stitch_enums.py`,
  `tests/test_stitch_client_native.py`,
  `tests/test_veg_material3_mapper.py` (40 tests total)
- **Docs**: `CLAUDE.md`, `CHANGELOG.md`, `ENGINE_VERSION.yaml`,
  `pyproject.toml`, `doc/prd/stitch_native_migration_prd.md`,
  `doc/migrations/v7_stitch_native_chain.md`
- **Evidence**: `.quality/evidence/stitch_smoke/` (3 scripts + 4 reports + schema)

## API key handling

The Stitch API key you pasted lived only in shell env vars during this session.
It is **not** persisted anywhere in the repo, in `.quality/`, or in any log.
It was used to drive the smoke tests in `.quality/evidence/stitch_smoke/`, all
of which read it from `STITCH_API_KEY` env var only.

## TTL

This handoff is valid until **2026-05-30** (72h). After that, prefer current
git state over recalled details from this document.
