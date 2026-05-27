---
generated_at: 2026-05-27T11:00:00Z
generator: claude-opus-4-7-autopilot
schema_version: 1
project: specbox-engine
session_id: v6.5.0-stitch-native-migration-pr2-autopilot
trigger: end-of-autopilot-session
ttl_minutes: 4320
branch: feature/stitch-native-migration-pr2
active_uc: null
next_action: human_review_pr_then_smoke_then_merge
---

# SpecBox Handoff — v6.5.0 "Stitch Native Migration — Behavioural (PR-2)"

## 🎯 Mission

PR-2 cierra el ciclo de la migración Stitch. PR-1 (v6.4.0, ya mergeada en
`e8d90b0`) trajo la foundation; PR-2 la cablea al pipeline real. Sin cambios
breaking — todo es opt-in vía `stitch.contract`.

## Summary

| Phase | Status | Notes |
|---|---|---|
| F5 — generate_design_md_tool → Material 3 | ✅ done | Material3FrontMatter + writer extendido + contract param |
| F6 — stitch_generate_screen_v2 prompt cleaner | ✅ done | heurística `_strip_theme_directives` + 5 prompt modes |
| F7 — stitch_migration.py + skill | ✅ done | 6 casos A-F + recipe planning + telemetry aggregator |
| F9 — upgrade_project + version_matrix | ✅ done | hint + columna stitch_contract + summary global |
| Tests dedicados | ✅ done | +67 (1316 passed total) |
| Docs + version bump | ✅ done | v6.5.0 en yaml/toml/CLAUDE.md/CHANGELOG |

**Branch**: `feature/stitch-native-migration-pr2` (1 commit, `673bcb4`).
**Suite**: 1316 passed, 71 skipped, 0 failed.

## What changed

### Nuevos módulos
- `server/design_md/material3_view.py` (308 líneas) — proyección M3 del DesignMd.
- `server/tools/stitch_migration.py` (519 líneas) — 3 MCP tools planning.
- 3 archivos de tests dedicados.

### Modificados
- `server/design_md/io.py` — `save(..., material3=...)` pass-through.
- `server/design_md/writer.py` — frontmatter alternativo M3 + sección VEG Notes.
- `server/tools/stitch_v2.py` — `contract` param en generate_design_md_tool +
  stitch_generate_screen_v2; helpers `_strip_theme_directives` +
  `_resolve_prompt_for_contract`; quitado `build_site` del adapter (era ghost).
- `server/tools/onboarding.py` — hint stitch_migration_alignment + columna
  stitch_contract en version_matrix + summary global.
- `server/server.py` — registra register_stitch_migration_tools.
- `.claude/skills/visual-setup/SKILL.md` — sección Modo `--migrate-stitch` v6.5.0.
- `tests/test_stitch_v2_design_md.py` — 2 tests legacy ajustados para forzar
  `contract="inline_prefix_v1"` (la tool legacy parsea con schema viejo).

### Docs
- `ENGINE_VERSION.yaml`, `pyproject.toml`, `CLAUDE.md`, `CHANGELOG.md` →
  v6.5.0 "Stitch Native Migration — Behavioural (PR-2)".

## Critical findings during PR-2

1. **El default `contract=native_v2` rompe el reader legacy de
   `upload_design_md_to_stitch`** porque ese tool sigue parseando con el
   schema SpecBox-native (que requiere `text_primary`, `fontFamily.heading`,
   etc.). Fix: el tool legacy queda restringido al contrato legacy. Tests
   actualizados para pasar `contract="inline_prefix_v1"` explícitamente.
   Esto es **comportamiento deseado** — la migración v7.0 elimina ese tool.

2. **`build_site` ya era ghost en `_StitchOpsAdapter`** (eliminado del
   StitchClient en v6.4.0). Reemplazado por comment apuntando a
   `stitch_build_site_batched_v2`.

3. **6 casos de migración cubiertos con default opinado**:
   - A: native_v2 → no-op
   - B: Stitch unused → flip marker
   - C: DESIGN.md sin project → backup + regen + bootstrap
   - **D: project con screens → MIGRATE-RETROACTIVE literal + apply DS**
   - **E: DESIGN.md custom → APPLY-PROPOSAL literal**
   - F: multirepo → delegate al orchestrator (precedence sobre A si hay
     conflicto, por diseño — protección de coordinación)

## What you need to do tomorrow morning

### 1. Review focus

1. **`server/design_md/material3_view.py`** — particularmente la tabla
   `_FAMILY_TO_FONT` (línea ~70) y `_derive_m3_colors` (línea ~140). Son
   las dos opiniones más subjetivas: qué fuentes mapeamos y qué anchors
   M3 surfaceamos al YAML.

2. **`server/tools/stitch_migration.py::_recipe_for_case`** — los 6 casos
   con sus actions/files_to_write/stitch_calls. Particularmente caso D
   (preview obligatorio + literal confirmation) y E (write proposal +
   literal confirmation).

3. **`.claude/skills/visual-setup/SKILL.md`** — sección "Modo
   `--migrate-stitch` (v6.5.0)". El playbook de 5 pasos es el contrato
   que ejecutará el agente cuando corra `/visual-setup --migrate-stitch`.

### 2. Smoke test opcional (5-10 min)

Si quieres validar en tu API key real antes de mergear:

```bash
# 1. Generate M3 DESIGN.md
mcp__SpecBox-MCP__generate_design_md_tool(
  project="<your-project>",
  project_root="/abs/path/to/project",
  contract="native_v2"
)

# 2. Upload via REST batchCreate
mcp__SpecBox-MCP__stitch_upload_design_md(
  project="<your-project>",
  stitch_project_id="<from-step-1>",
  design_md_content="<contents of generated DESIGN.md>"
)

# 3. Create DS from MD
mcp__SpecBox-MCP__stitch_create_design_system_from_design_md(...)

# 4. Generate a screen with cleaned prompt
mcp__SpecBox-MCP__stitch_generate_screen_v2(
  project="<your-project>",
  stitch_project_id=...,
  prompt="Hero landing with two CTAs",
  contract="native_v2"
)
# Expected: prompt_mode="design_system_applied", design_system_info.count>=1
```

### 3. Merge + tag

Si review verde:

```bash
gh pr merge <PR_NUMBER> --squash --delete-branch
git checkout main && git pull
git tag -a v6.5.0 -m "v6.5.0 — Stitch Native Migration (PR-2 behavioural)"
git push origin v6.5.0
```

## Risks remaining

| Risk | Mitigation |
|---|---|
| El mapeo `_FAMILY_TO_FONT` no cubre alguna fuente común que uses | Lista en una sola tabla; fácil añadir. Las 22 cubiertas son las más probables del Brand Kit |
| El stripping heurístico de prompts elimina líneas legítimas | Falsos positivos posibles. Caller puede pre-limpiar y pasar `contract="inline_prefix_v1"` para escapar |
| El preview pre/post de caso D no está implementado en PR-2 | El recipe declara la acción `preview_apply_design_system` pero la implementación visual queda en la skill (PR-3 si se necesita más sofisticada) |
| Adopción de native_v2 antes de v7.0 cutover | `get_version_matrix` ahora cuenta y emite hint — métrica observable |

## What's NOT in this PR

- Implementación gráfica del `preview_apply_design_system` (la skill recibe
  el recipe pero el preview visual queda como ejercicio del agente).
- Refactor de `/plan` Paso 6 para auto-detectar DS y pasar `designSystem`
  al generate (sigue siendo PR-2 del PRD si decidimos hacerlo aparte).
- Stripping más fino del prompt (LLM-based en vez de regex) — la heurística
  cubre los casos comunes; refinamiento opcional post-telemetría.

## TTL

Este handoff vale hasta **2026-05-30** (72h). Después, fíate del git state.
