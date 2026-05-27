# PRD — Stitch Native Migration (v6.4.0 candidate)

**ID**: US-STITCH-NATIVE-MIGRATION
**Status**: Draft (autopilot agresivo nocturno, 2026-05-26)
**Owner**: Jesús Pérez
**Engine target**: v6.4.0
**Cutover target**: v7.0 (breaking — inline_prefix_v1 retirado)

---

## 1. Contexto

SpecBox Engine integra Google Stitch desde v5.6 vía un proxy MCP propio
(`server/stitch_client.py` + `server/tools/stitch.py` con 13 tools). La capa
"Stitch Autopilot v5.31" añadió 6 tools v2 más (`generate_design_md_tool`,
`upload_design_md_to_stitch`, `validate_stitch_prompt`,
`stitch_generate_screen_v2`, `stitch_build_site_batched_v2`,
`get_stitch_quota_status`) para mitigar drift visual, fallos de generación
y cuota de la UI web de Stitch.

Tras un audit profundo de la documentación oficial post-Google I/O 2026 y
**dos smoke tests reales contra el MCP de Stitch con la API key del
mantenedor**, se confirmó:

1. El MCP oficial `https://stitch.googleapis.com/mcp` expone **14 tools
   nativas** (no 12 como asume el cliente actual). Las **6 tools de
   design-system** (`upload_design_md`, `create_design_system`,
   `create_design_system_from_design_md`, `update_design_system`,
   `list_design_systems`, `apply_design_system`) no están registradas en
   el cliente de SpecBox.
2. La capa v5.31 `upload_design_md_to_stitch` opera en modo
   `inline-prefix` (prepende DESIGN.md al prompt en cada generación)
   porque cuando se diseñó "Stitch MCP no exponía endpoint nativo de
   attach". Eso **ya no es cierto**: las 6 tools de design-system existen
   y operan persistencia server-side de Material 3 tokens (smoke verdict
   `pass`, end-to-end en 78s reales).
3. La cuota documentada en CLAUDE.md ("350 Standard + 200 Experimental
   por mes, no ampliable") corresponde a la UI web de Stitch, **no al
   MCP**. La extensión oficial Gemini CLI declara literalmente *"Stitch
   MCP is free of charge"*. Todo el subsistema `get_stitch_quota_status`
   + `stitch-quota-guard.mjs` + `flash_safety_net` resuelve un problema
   que no existe.
4. El cliente actual expone 2 tools fantasma (`extract_design_context`,
   `build_site`) que **no aparecen en el inventario real del MCP**.
5. Los enums documentados están desactualizados:
   - **Fonts**: docs públicas listan 9, MCP real expone **65**.
   - **colorVariant**: docs dicen `TONAL`, MCP real expone `TONAL_SPOT`.
   - **colorVariant**: `NEUTRAL` no documentado, existe en server.
   - **roundness**: `ROUND_TWO` no documentado, existe en server.

Evidencia consolidada en
[.quality/evidence/stitch_smoke/](../../.quality/evidence/stitch_smoke/):
- `smoke_report.md` — REST batchCreate verde, 6/7 pasos OK.
- `smoke_mcp_v2_report.md` — **chain nativa MCP 8/8 PASS**.
- `mcp_tools_schema.json` — 14 tools con outputSchema completo.

## 2. Objetivo

Sustituir el modo `inline-prefix` por la **chain nativa Material 3
server-side** de Stitch, exponer los 65 fonts y enums reales, eliminar el
subsistema de cuota innecesario, retirar las 2 tools fantasma, y proveer
un proceso de migración en 6 casos para proyectos onboarded en versiones
previas.

## 3. Non-goals

- **No** soportar OAuth de Stitch — el API key actual basta (verificado).
- **No** abandonar VEG. VEG sigue siendo el modelo conceptual de
  arquetipos; Material 3 es la representación normativa en el YAML
  frontmatter para que el parser server-side la consuma.
- **No** mergear automáticamente la PR — review humano obligatorio.
- **No** publicar v7.0 en este PRD. v7.0 es PRD separado posterior; aquí
  solo se establece la **señalización** y el path de migración.

## 4. Decisiones canónicas

| Decisión | Valor | Rationale |
|---|---|---|
| Caso D default (Stitch project con screens sin DS) | **D.2 Retroactivo asistido** | Coherencia visual total a coste de complejidad de smoke pre/post. El usuario lo aprobó explícitamente. |
| Backwards compat strategy | **Cutover duro en v7.0** | v6.4.0 introduce `native_v2` como opt-in. v7.0 elimina `inline_prefix_v1`. Mantener dos pipelines indefinidamente es deuda. |
| Mapping VEG ↔ Material 3 | Material 3 estricto en YAML frontmatter + VEG preservado como Markdown body en sección "VEG Notes" | Server parsea M3; humanos y agentes leen VEG. Ambas verdades coexisten. |
| Auth | API key (`X-Goog-Api-Key`) | Verificado funcional contra MCP JSON-RPC en smoke v2. |

## 5. Audiencia + JTBD

Audiencia primaria: el propio mantenedor (Jesús) usando SpecBox sobre
proyectos como specbox-control-panel, Potencial Digital 2026, embed.build.
Audiencia secundaria: usuarios de SpecBox que tengan proyectos onboarded
en versiones v5.x con Stitch ya cableado.

JTBD racional: "cuando inicio un proyecto nuevo o itero sobre uno
existente, quiero que el DESIGN.md sirva como source-of-truth server-side
de Stitch para que las pantallas que genere y refactorice mantengan
coherencia automática sin re-prepender tokens en cada prompt".

JTBD emocional: "no quiero seguir explicándole a Stitch los mismos
colores y fuentes cada vez que pido una pantalla".

## 6. Scope técnico — 13 UCs

Cada UC tiene branch propio, tests verdes locales, evidencia, y se
mergea solo tras review humano.

### UC-700 — Foundation: cliente MCP con tools nativas + enums reales

**Files**: `server/stitch_client.py`, `server/stitch_enums.py` (nuevo),
`tests/test_stitch_client_native.py` (nuevo)

**AC**:
- AC-01: Cliente expone los 14 wrappers nativos (incluye los 6 de
  design-system) con type hints y docstrings.
- AC-02: Las 2 tools fantasma (`extract_design_context`, `build_site`)
  quedan eliminadas. Cualquier import externo recibe `AttributeError`
  con mensaje migratorio.
- AC-03: `server/stitch_enums.py` codifica los 5 enums reales (Font 65v,
  ColorMode 3v, ColorVariant 10v, Roundness 6v, ScreenType) como
  StrEnum.
- AC-04: `get_project` acepta tanto `name` (full path) como `projectId`
  (legacy alias), prefiriendo `name`. Hipótesis verificada en smoke
  v2: `name` funciona, `projectId` falla con "Request contains an
  invalid argument".
- AC-05: Tests pytest sin red mockeando httpx — 100% green.

### UC-701 — Tool MCP: chain nativa de design-system en server/tools/stitch.py

**Files**: `server/tools/stitch.py`, `tests/test_stitch_tools_native.py` (nuevo)

**AC**:
- AC-01: 6 tools MCP nuevas registradas: `stitch_upload_design_md`,
  `stitch_create_design_system`,
  `stitch_create_design_system_from_design_md`,
  `stitch_update_design_system`, `stitch_list_design_systems`,
  `stitch_apply_design_system`.
- AC-02: `stitch_apply_design_system` valida que `selectedScreenInstances`
  contenga solo `{id, sourceScreen}` — rechaza payloads con
  `x/y/width/height` con error claro (regla documentada por Google).
- AC-03: `stitch_update_design_system` rechaza el campo legacy `font`
  con error "use headlineFont/bodyFont/labelFont instead".
- AC-04: Telemetría: cada llamada emite entrada en
  `stitch_usage.jsonl` con `tool_name`, `latency_ms`, `outcome`.

### UC-702 — Helper REST batchCreate para DESIGN.md grande

**Files**: `server/stitch_client.py` (método `upload_via_rest`),
`tests/test_stitch_rest_upload.py`

**AC**:
- AC-01: Cuando DESIGN.md ≥ 5KB base64 (~16k tokens), usa
  `POST /v1/projects/{id}/screens:batchCreate` REST.
- AC-02: Acepta MIME `text/markdown`, `text/html`, `image/png`,
  `image/jpeg`, `image/webp`. ScreenType auto: DOCUMENT para md/html,
  IMAGE para imágenes.
- AC-03: Devuelve `screenInstances` con `{id, sourceScreen}` parseado
  para alimentar `create_design_system_from_design_md` aguas abajo.

### UC-703 — VEG ↔ Material 3 mapper

**Files**: `server/veg/material3_mapper.py` (nuevo),
`tests/test_veg_material3_mapper.py`

**Mapping table** (validado contra smoke v2):

| VEG Arquetipo | colorMode | colorVariant | headlineFont | bodyFont | labelFont | roundness | customColor (representative) |
|---|---|---|---|---|---|---|---|
| Corporate | LIGHT | NEUTRAL | INTER | INTER | INTER | ROUND_FOUR | #1A56DB |
| Startup | LIGHT | FIDELITY | SPACE_GROTESK | INTER | INTER | ROUND_EIGHT | #7C3AED |
| Creative | LIGHT | EXPRESSIVE | PLAYFAIR_DISPLAY | INTER | INTER | ROUND_TWELVE | #EC4899 |
| Consumer | LIGHT | VIBRANT | DM_SANS | DM_SANS | DM_SANS | ROUND_EIGHT | #F59E0B |
| Gen-Z | DARK | RAINBOW | BEBAS_NEUE | SPACE_GROTESK | SPACE_GROTESK | ROUND_FULL | #14F195 |
| Gobierno | LIGHT | MONOCHROME | INTER | INTER | INTER | ROUND_FOUR | #1F2937 |

**AC**:
- AC-01: `map_veg_to_material3(archetype, brand_kit)` devuelve un
  `Material3Theme` validado contra los enums reales del MCP.
- AC-02: Si `brand_kit.primary_color` se provee, se usa como
  `customColor` overriding la default del arquetipo.
- AC-03: Si VEG tiene JTBD emocional que override 2 pilares, el mapper
  respeta los overrides documentados en VEG (e.g., un Corporate con
  JTBD emocional "modern" puede subir a ROUND_EIGHT).
- AC-04: Función inversa `material3_to_veg_hints(theme)` para casos de
  migración E (DESIGN.md custom).
- AC-05: 100% de las combinaciones enum válidas tienen test.

### UC-704 — Refactor generate_design_md_tool a Material 3 estricto

**Files**: `server/tools/stitch.py::generate_design_md_tool`,
`doc/templates/design_md_material3_template.md` (nuevo),
`tests/test_design_md_material3.py`

**AC**:
- AC-01: Output tiene YAML frontmatter Material 3 con tokens canónicos
  M3 (surface, on-surface, surface-container-*, primary, on-primary,
  primary-container, on-primary-container, secondary, on-secondary,
  tertiary, error, on-error, background, on-background, outline,
  outline-variant, ≥50 entries).
- AC-02: Output preserva "VEG Notes" como sección Markdown body
  con archetype, JTBD, multi-form-factor notes.
- AC-03: Backup automático del DESIGN.md previo a
  `doc/design/DESIGN.md.pre-migration.bak` cuando detecta formato v5.31.
- AC-04: `validate_stitch_prompt` corre `lint` interno: contrast WCAG AA
  en pares on-*/[parent], missing-primary, missing-typography, em-dash
  ban (extracted from taste-skill v2 — separate work but compatible
  contract).

### UC-705 — Refactor stitch_generate_screen_v2 con prompts limpios

**Files**: `server/tools/stitch.py::stitch_generate_screen_v2`,
`tests/test_stitch_generate_v2_clean_prompt.py`

**AC**:
- AC-01: Cuando `list_design_systems(projectId)` devuelve ≥1 DS, el
  prompt enviado a `generate_screen_from_text` NO incluye colors, fonts
  ni roundness directives. Se pasa `designSystem: "assets/{id}"` como
  parámetro.
- AC-02: Cuando NO hay DS aplicado (caso transición), el prompt sigue
  incluyendo el DESIGN.md prefix con un warning en telemetría:
  `mode=inline_prefix_fallback`.
- AC-03: Fallback chain (`edit_baseline → variants_refine → regenerate`)
  preservada para errores transitorios. Eliminado el Flash safety net
  (cuota no es un problema).

### UC-706 — detect_stitch_migration_case + 6 casos

**Files**: `server/tools/stitch_migration.py` (nuevo),
`tests/test_stitch_migration_detect.py`

**AC**:
- AC-01: Tool `detect_stitch_migration_case(project_root_content)`
  retorna `{case: "A|B|C|D|E|F", evidence: {...}, recommended_action: "..."}`.
- AC-02: Caso A: `stitch.contract=="native_v2"` en settings →
  recommended_action="no_op".
- AC-03: Caso B: settings.stitch.api_key existe + 0 generations en
  `doc/design/` → recommended_action="mark_native_v2_no_data_migration".
- AC-04: Caso C: `doc/design/DESIGN.md` existe sin `stitch.projectId`
  → recommended_action="migrate_design_md_then_bootstrap_ds".
- AC-05: Caso D: `stitch.projectId` existe + screens generadas + 0 DS
  applied → recommended_action="d2_retroactive_assisted" (default).
- AC-06: Caso E: DESIGN.md no parsea como M3 + `stitch.contract` no
  existe → recommended_action="generate_mapping_proposal_for_review".
- AC-07: Caso F: orchestrator + satellites detectados →
  recommended_action="migrate_orchestrator_only".
- AC-08: Tool es content-passing (cliente pasa el contenido de los
  archivos, no paths) — consistente con MCP Path Contract v6.0.1.

### UC-707 — /visual-setup --migrate-stitch (modos: forward / retroactive / proposal)

**Files**: `.claude/skills/visual-setup/SKILL.md` (nuevo Paso 4),
`server/tools/stitch_migration.py::migrate_project_to_native_v2`,
`tests/test_visual_setup_migrate.py`

**AC**:
- AC-01: Sub-modo `/visual-setup --migrate-stitch` llama
  `detect_stitch_migration_case`, presenta el plan al usuario, y
  ejecuta acción según caso.
- AC-02: Caso D ejecuta smoke test visual:
  - Toma 3 screens existentes representativas.
  - Llama `apply_design_system` en modo "preview" (TBD si MCP lo soporta —
    si no, genera mock con `update_design_system` rollback).
  - Pide confirmación literal "MIGRATE-RETROACTIVE".
  - Si rollback necesario, el handler de error revierte el theme.
- AC-03: Caso E genera `doc/design/migration_proposal_material3.md`
  con la tabla de mapping VEG↔M3 propuesta. NO ejecuta hasta que el
  usuario confirme con `--apply-proposal`.
- AC-04: Telemetría JSONL en `.quality/logs/stitch-migration.jsonl`
  con timestamp, case, action, duration_ms, outcome,
  unmapped_tokens.
- AC-05: Estado intermedio persistido en
  `.quality/stitch_migration_state.json` para resume en caso de fallo.

### UC-708 — Limpieza del subsistema quota

**Files**: eliminar `server/tools/stitch.py::get_stitch_quota_status`,
`.claude/hooks/stitch-quota-guard.mjs`,
`.quality/stitch_quota.json`,
secciones `quota` y `flash_safety_net` de `templates/settings.json.template`,
`server/tools/stitch.py::FlashSafetyNet` y referencias.

**AC**:
- AC-01: 0 referencias a `get_stitch_quota_status` en el repo.
- AC-02: Hook `stitch-quota-guard.mjs` eliminado de hooks dir y de
  `templates/settings.json.template` hooks section.
- AC-03: `templates/settings.json.template` actualizado eliminando
  bloques `quota` y `flash_safety_net`.
- AC-04: CHANGELOG v6.4.0 documenta la deprecación con migration note
  "If you depended on quota tracking for UI Stitch usage, that signal
  remains in the Stitch web UI but is no longer surfaced by SpecBox".

### UC-709 — upgrade_project + version_matrix + stitch.contract zona settings

**Files**: `server/tools/onboarding.py::upgrade_project`,
`server/tools/version_matrix.py::get_version_matrix`,
`server/app_docs/registry.py` (zona `stitch_contract` en `app_spec.md`),
`tests/test_upgrade_project_stitch.py`

**AC**:
- AC-01: `upgrade_project` llama `detect_stitch_migration_case` y
  emite `stitch_migration_hint` en el output.
- AC-02: `get_version_matrix` añade columna `stitch_contract` con
  valores `native_v2 | inline_prefix_v1 | migration_pending | not_applicable`.
- AC-03: `app_spec.md` registry incluye zona auto `stitch_contract`
  que el engine rewrite tras un `--migrate-stitch` exitoso.
- AC-04: Settings zone documented in
  `templates/settings.json.template` y `templates/app_spec.md.template`.

### UC-710 — Telemetría + observabilidad

**Files**: `.quality/logs/stitch-migration.jsonl` schema,
`.quality/scripts/stitch-migration-stats.mjs` (nuevo),
documentación en `CLAUDE.md`.

**AC**:
- AC-01: Cada step de migración escribe una entrada JSONL con schema
  validable (`migration_step_v1`).
- AC-02: Script Node.js agrega métricas: count por caso, mediana de
  `unmapped_tokens`, errores recurrentes.
- AC-03: Tool MCP `get_stitch_migration_stats(project)` para que
  specbox_cloud lea el estado.

### UC-711 — Docs masivas + release prep v6.4.0

**Files**: `CLAUDE.md`, `CHANGELOG.md`, `ENGINE_VERSION.yaml`,
`pyproject.toml`, `doc/migrations/v7_stitch_native_chain.md`,
`doc/decisions/stitch_native_chain.md` (nuevo).

**AC**:
- AC-01: `CLAUDE.md` sección `Stitch MCP Proxy v5.6.0` reescrita:
  14 tools, enums reales, sin afirmaciones obsoletas.
- AC-02: `CLAUDE.md` sección `Stitch Autopilot v5.31.0` reescrita
  como `Stitch Native Migration (v6.4.0)` con el flujo de 7 pasos
  documentado.
- AC-03: Elimina la mención "Stitch MCP no expone hoy un endpoint
  nativo de attach".
- AC-04: Elimina la mención "350 Standard + 200 Experimental por mes
  (no ampliable)".
- AC-05: Elimina `AGNOSTIC` del enum DeviceType documentado (no existe
  en el MCP real).
- AC-06: `doc/migrations/v7_stitch_native_chain.md` documenta el
  cutover duro previsto en v7.0 con timeline y checklist por usuario.
- AC-07: `doc/decisions/stitch_native_chain.md` documenta la decisión
  arquitectural completa con evidencia smoke.
- AC-08: `ENGINE_VERSION.yaml` y `pyproject.toml` bumpeados a 6.4.0
  "Stitch Native Migration".
- AC-09: CHANGELOG v6.4.0 entrada con migration guide condensada.

### UC-712 — Suite de tests por caso de migración

**Files**: `tests/test_stitch_migration_e2e.py` (gated por
`STITCH_API_KEY` env var — no corre en CI público sin auth).

**AC**:
- AC-01: Test por caso A-F mockeando `detect_stitch_migration_case`
  inputs.
- AC-02: Test e2e integrado (gated): replica el smoke test v2 como
  pytest si `STITCH_API_KEY` está presente.
- AC-03: Test de coexistencia: `stitch.contract=inline_prefix_v1`
  sigue funcionando sin regresión.
- AC-04: Coverage ≥ 85% en módulos nuevos.

## 7. Riesgos

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| `apply_design_system` retroactivo cambia visualmente screens existentes de forma inaceptable | Media | UC-707 AC-02 con preview opcional + confirmación literal + rollback automatizado en caso de fallo |
| Latencia de `create_design_system_from_design_md` (43s en smoke) confunde al usuario | Media-baja | Telemetría progress + timeout configurable |
| Mapping VEG↔M3 pierde semántica en proyectos creative/gen-z | Media | Preservar VEG Notes como Markdown body, no descartar |
| Cutover v7.0 sorprende a usuarios que no migraron | Alta | Warning loud en v6.4-v6.x, mensajería clara en CHANGELOG, dry-run de migración disponible |
| `stitch.googleapis.com/mcp` endpoint cambia auth a OAuth post-smoke | Baja | Detectable por test e2e gated; aboutmodel doc actualizable |

## 8. Out of scope (futuras)

- v7.0 release work (cutover real).
- Adaptación de `/plan` Paso 6 para detectar DS y eliminar tokens del
  prompt automáticamente (UC-705 lo hace al nivel de tool, pero
  `/plan` puede inyectar el `designSystem` param explícitamente).
- Soporte OAuth ADC como alternativa a API key.
- Integración con CLI oficial `@google/design.md` para lint/diff/export.
- Adaptador de skill oficial Google `taste-skill` / `frontend-design`
  como fallback estético — separado por diseño.

## 9. Evidence

- `.quality/evidence/stitch_smoke/smoke_test.py` + `smoke_report.md` (REST batchCreate)
- `.quality/evidence/stitch_smoke/smoke_test_mcp_v2.py` + `smoke_mcp_v2_report.md` (chain nativa 8/8 PASS)
- `.quality/evidence/stitch_smoke/mcp_tools_schema.json` (14 tools schema)

## 10. Order of execution

1. UC-700 (foundation cliente — sin esto nada compila)
2. UC-708 (limpieza quota — independiente, libera código antes del refactor)
3. UC-701 (tools MCP de design-system — depende de UC-700)
4. UC-702 (helper REST batchCreate — depende de UC-700)
5. UC-703 (mapper VEG↔M3 — independiente, puede ir en paralelo con 701/702)
6. UC-704 (refactor generate_design_md_tool — depende de UC-703)
7. UC-705 (refactor stitch_generate_screen_v2 — depende de UC-701)
8. UC-706 (detect_stitch_migration_case — depende de UC-700, 701, 704)
9. UC-707 (/visual-setup --migrate-stitch — depende de UC-706)
10. UC-709 (upgrade_project integration — depende de UC-706)
11. UC-710 (telemetría — depende de UC-707)
12. UC-712 (tests e2e — depende de UC-700 a 707)
13. UC-711 (docs — al final, refleja estado consolidado)

## 11. Validación post-merge

Manual smoke test del mantenedor con la API key real:

```bash
cd ~/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/specbox-control-panel  # u otro proyecto
export STITCH_API_KEY="..."
/visual-setup --migrate-stitch
# Debe detectar caso D (proyecto tiene screens), pedir MIGRATE-RETROACTIVE,
# aplicar DS, y reflejar en `app_spec.md` zona stitch_contract=native_v2.
```
