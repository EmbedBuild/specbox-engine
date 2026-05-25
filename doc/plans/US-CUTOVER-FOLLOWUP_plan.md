# Plan: US-CUTOVER-FOLLOWUP — v6.1.1 Cutover Followup

> Generado: 2026-05-25
> Origen: FreeForm backend `ff-ed0c02f4565a` | US-CUTOVER-FOLLOWUP
> PRD: `doc/prd/US-CUTOVER-FOLLOWUP_prd.md`
> Estado: Pendiente
> Release target: v6.1.1 "Cutover Followup" (patch)
> stitch_designs: N/A (cleanup interno, sin UI)

---

## Resumen

Patch release que cierra 11 residuos de Sala de Máquinas en `main` tras v6.1.0. Cero código nuevo: sólo deletes + cleanup de strings, distribuidos en 9 UCs secuenciales (UC-625..UC-633) de complejidad baja. La pieza más grave es la tool MCP `get_sala_de_maquinas` que sigue registrada y expuesta — el primer UC la elimina.

## Análisis UI (Fase 0)

**N/A**. Esta US no tiene pantallas. Todos los UCs son cleanup interno (Python, Node hooks, skill markdown, canónicos, manifests, VSCode extension config). Se saltan Pasos 2.5b VEG y Paso 6 Stitch del SKILL.

---

## Fases de Implementación

> Cada UC es una fase. Implementación secuencial, una rama feature por UC (estándar SpecBox), commit + PR + merge antes del siguiente.

### Fase 1 — UC-625: Eliminar tool MCP `get_sala_de_maquinas` + helpers
- **Rama**: `feature/UC-625-rm-sala-tool`
- **Archivos**: `server/tools/state.py`, `server/server.py`
- **Operaciones**:
  1. `grep -rn "get_sala_de_maquinas\|_get_sala\|sala_de_maquinas" server/` → identificar todos los símbolos relacionados.
  2. Auditar helpers privados en `state.py` (los que NO usan `report_session`, `report_checkpoint`, `report_healing`, `report_acceptance_*`, `report_merge_status`, `report_feedback`, `report_e2e_results`). Sólo eliminar los exclusivos.
  3. Eliminar `def get_sala_de_maquinas` y helpers exclusivos.
  4. Limpiar `server/server.py:135` instructions string.
  5. `pytest -q` → verificar ≥1190 passed, 0 failed.
- **Tiempo estimado**: 30 min
- **Tests**: pytest existente cubre el path (los tests de live_state/heartbeat ya fueron eliminados en v6.1.0).
- **Riesgo**: helpers privados compartidos. Mitigación: `grep` exhaustivo antes de borrar.

### Fase 2 — UC-626: Docstrings Python
- **Rama**: `feature/UC-626-rm-sala-docstrings-py`
- **Archivos**:
  - `server/tools/benchmark.py:31` (1 mención)
  - `server/audit/persistence.py:2` (1 mención)
  - `server/app_docs/drift_detector.py:26,321` (2 menciones)
- **Operaciones**:
  1. Reescribir "para Sala de Máquinas" → "para consumidores externos (specbox_cloud, scripts ad-hoc)" donde corresponda.
  2. Eliminar referencias puramente descriptivas si no aportan.
  3. `grep "Sala de Máquinas" server/tools/benchmark.py server/audit/ server/app_docs/` → 0 matches.
  4. `pytest -q server/audit server/app_docs` → verde.
- **Tiempo estimado**: 12 min
- **Riesgo**: ninguno (sólo docstrings).

### Fase 3 — UC-627: Docstrings Node hooks
- **Rama**: `feature/UC-627-rm-sala-docstrings-mjs`
- **Archivos**:
  - `.claude/hooks/app-docs-sync-guard.mjs:36`
  - `.claude/hooks/context-budget-guard.mjs:21`
- **Operaciones**:
  1. Reescribir comentarios "surface to Sala de Máquinas" → "surface via local artifacts".
  2. `node --check .claude/hooks/app-docs-sync-guard.mjs .claude/hooks/context-budget-guard.mjs`.
  3. `grep "Sala de Máquinas" .claude/hooks/*.mjs` → 0 matches.
- **Tiempo estimado**: 6 min
- **Riesgo**: ninguno (sólo comentarios).

### Fase 4 — UC-628: Skills (plan/audit/discovery)
- **Rama**: `feature/UC-628-rm-sala-skills`
- **Archivos**:
  - `.claude/skills/plan/SKILL.md:584`
  - `.claude/skills/audit/SKILL.md:61`
  - `.claude/skills/discovery/SKILL.md:414`
- **Operaciones**:
  1. Reescribir o eliminar menciones según pertinencia (manteniendo flujo conversacional del skill).
  2. NO tocar frontmatter (`name:`, `description:`, `triggers:`).
  3. `grep "Sala de Máquinas" .claude/skills/{plan,audit,discovery}/SKILL.md` → 0 matches.
- **Tiempo estimado**: 12 min
- **Riesgo**: bajo (cambios sólo en cuerpo del SKILL.md, no en frontmatter discovery-relevant).

### Fase 5 — UC-629: Canónicos `doc/app/`
- **Rama**: `feature/UC-629-rm-sala-canon`
- **Archivos**: `doc/app/app_spec.md`, `doc/app/app_prd.md`
- **Operaciones**:
  1. `app_spec.md` zona "stack": eliminar filas Dashboard React + Dashboard Vite (líneas 17-18). Bumpear contador.
  2. `app_spec.md` zona "brand_visual" (línea 40): quitar "salvo Sala de Máquinas" del Stitch project_id.
  3. `app_prd.md` zona "vision" (línea 12): reescribir "MCP server con 164 tools + Sala de Máquinas + Gherkin BDD" → "MCP server + Gherkin BDD + Quality Audit ISO/IEC 25010 + Product Discovery".
  4. `app_prd.md` zona "scope" v1 (línea 31): eliminar mención.
  5. Bumpear "Versión del documento: 1 → 2" en ambos archivos.
  6. `verify_app_docs` via MCP → confirmar drift legítimo (cambios manuales, no contaminación).
- **Tiempo estimado**: 18 min
- **Riesgo**: medio. `app-docs-sync-guard` puede warnear porque hay drift. Mitigación: hook está en `warn` mode, no bloquea. El warning sería correcto (drift es intencional).

### Fase 6 — UC-630: `ENGINE_VERSION.yaml` features array
- **Rama**: `feature/UC-630-rm-sala-engine-version`
- **Archivos**: `ENGINE_VERSION.yaml` (línea 66)
- **Operaciones**:
  1. Eliminar línea `- sala-de-maquinas-embedded` del array `features:`.
  2. NO tocar array `commits:` histórico.
  3. `python3 -c "import yaml; yaml.safe_load(open('ENGINE_VERSION.yaml'))"` → YAML válido.
- **Tiempo estimado**: 3 min
- **Riesgo**: ninguno.

### Fase 7 — UC-631: `.claude/settings.local.json` allowedTools
- **Rama**: `feature/UC-631-rm-sala-settings`
- **Archivos**: `.claude/settings.local.json` (línea 16)
- **Operaciones**:
  1. Eliminar entrada `"mcp__specbox-engine__get_sala_de_maquinas"` del array allowedTools.
  2. `python3 -c "import json; json.load(open('.claude/settings.local.json'))"` → JSON válido.
- **Tiempo estimado**: 3 min
- **Riesgo**: ninguno (settings local, no afecta otros usuarios).

### Fase 8 — UC-632: VSCode extension
- **Rama**: `feature/UC-632-rm-sala-vscode`
- **Archivos**:
  - `vscode-extension/package.json` (líneas 61-64, 152-161)
  - `vscode-extension/src/extension.ts` (líneas 56-57)
  - `vscode-extension/out/` (rebuild)
- **Operaciones**:
  1. `package.json`: eliminar bloque `{ "command": "specbox.openDashboard", ... }` y bloque `"specbox.dashboardUrl": { ... }`.
  2. `package.json`: bump version `"5.21.0"` → `"5.21.1"`.
  3. `src/extension.ts`: eliminar `vscode.commands.registerCommand('specbox.openDashboard', ...)` (líneas 56-57).
  4. `cd vscode-extension && npm run compile` → TS sin errores.
  5. JSON válido + TS compile verde + `grep -n "openDashboard\|dashboardUrl" vscode-extension/` → 0 matches.
- **Tiempo estimado**: 24 min
- **Riesgo**: TS compile podría fallar si hay refs colgando. Mitigación: cambio acotado a 2 líneas + es muy localizado.

### Fase 9 — UC-633: Release v6.1.1
- **Rama**: `feature/UC-633-release-v6.1.1`
- **Archivos**:
  - `ENGINE_VERSION.yaml` (version + codename)
  - `pyproject.toml` (version + description)
  - `CLAUDE.md` (header h1 + footer "Engine Version")
  - `CHANGELOG.md` (nueva entry al inicio)
  - `doc/decisions/cloud_cutover.md` (sección "v6.1.1 followup" al final)
- **Operaciones**:
  1. `ENGINE_VERSION.yaml`: `version: 6.1.0 → 6.1.1`, `codename: "Cloud Cutover" → "Cutover Followup"`.
  2. `pyproject.toml`: `version = "6.1.0" → "6.1.1"`, actualizar `description`.
  3. `CLAUDE.md`: `# SpecBox Engine v6.1.0 → v6.1.1`; footer `Current: v6.1.0 → v6.1.1 "Cutover Followup"`.
  4. `CHANGELOG.md`: insertar entry `[6.1.1] - 2026-05-25 — "Cutover Followup"` con secciones Removed (residuos), Changed (texto), Tests (suite verde sin cambios numéricos). Entradas históricas intactas.
  5. `doc/decisions/cloud_cutover.md`: sección final "## v6.1.1 followup — Residual cleanup".
  6. Si existe `node .quality/scripts/version-consistency-check.mjs`: ejecutar y validar verde.
- **Tiempo estimado**: 42 min
- **Riesgo**: drift entre los 4 lugares de versión. Mitigación: el validator (introducido en v5.32.1) detecta drift.

---

## Comandos de Validación (entre fases)

```bash
# Suite Python
.venv/bin/pytest -q --no-header

# Node hooks lib
node --test .claude/hooks/lib/*.test.mjs

# VSCode extension (sólo UC-632 en adelante)
cd vscode-extension && npm run compile

# Smoke server
.venv/bin/python -c "import server.server as s; print(s._ENGINE_VERSION)"

# Verify canónicos (sólo UC-629 en adelante)
# (vía MCP tool verify_app_docs con app_prd_content + app_spec_content)
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|---|---|---|---|
| Granularidad | 9 UCs (uno por residuo lógico) | 1 UC monolítico | Trazabilidad por commit/PR, rollback granular si algo falla |
| Estrategia PR | 1 PR final squash de 9 commits | 9 PRs separados | Más eficiente para patch release; suite verde validada al final |
| Helpers privados state.py | Auditar antes de borrar (UC-625 op 2) | Borrar archivo entero | report_* tools comparten infraestructura — borrar archivo rompe MCP |
| VSCode extension | Cleanup quirúrgico + bump 5.21.1 | Eliminar extensión completa | Extensión tiene 5 capacidades independientes (install/health/onboard/mcp/status) |
| Docs históricos | Preservar (no scope) | Mover a doc/archive/ o borrar | ADRs de su época, git history los preserva |
| Tests nuevos | Ninguno | Cobertura adicional para los deletes | Los tests del dominio Sala de Máquinas ya fueron eliminados en v6.1.0; el resto es cleanup textual |

---

## Archivos Tocados (consolidado)

```
server/
├── tools/
│   ├── state.py            # UC-625: rm get_sala_de_maquinas + helpers
│   └── benchmark.py        # UC-626: docstring cleanup
├── server.py               # UC-625: rm instructions line
├── audit/
│   └── persistence.py      # UC-626: docstring cleanup
└── app_docs/
    └── drift_detector.py   # UC-626: docstring cleanup

.claude/
├── hooks/
│   ├── app-docs-sync-guard.mjs    # UC-627: comment cleanup
│   └── context-budget-guard.mjs   # UC-627: comment cleanup
├── skills/
│   ├── plan/SKILL.md       # UC-628: body cleanup
│   ├── audit/SKILL.md      # UC-628: body cleanup
│   └── discovery/SKILL.md  # UC-628: body cleanup
└── settings.local.json     # UC-631: rm allowedTool

doc/
├── app/
│   ├── app_spec.md         # UC-629: rm Dashboard rows + brand mention
│   └── app_prd.md          # UC-629: rewrite vision + scope
└── decisions/
    └── cloud_cutover.md    # UC-633: append v6.1.1 followup section

vscode-extension/
├── package.json            # UC-632: rm command + setting + bump 5.21.1
├── src/extension.ts        # UC-632: rm 2 lines
└── out/extension.js        # UC-632: rebuild

ENGINE_VERSION.yaml         # UC-630 + UC-633: features array + version
pyproject.toml              # UC-633: version + description
CLAUDE.md                   # UC-633: header + footer
CHANGELOG.md                # UC-633: new entry
```

---

## Visual Experience Generation

**N/A** — esta US no tiene pantallas. VEG no aplica.

---

## Diseños Stitch

**stitch_designs: N/A** — esta US no tiene pantallas. Paso 6 del SKILL `/plan` saltado.

---

## Output

- **Fases**: 9 (una por UC)
- **Componentes UI analizados**: 0 (cleanup interno)
- **Widgets a crear**: 0
- **Agentes involucrados**: ninguno (orchestrator no configurado en este repo; flujo lineal autopilot vía `/implement`)
- **Tiempo total estimado**: 2.5h
- **Suite target**: ≥1190 passed, 0 failed (sin cambios numéricos vs baseline 1192)

## Referencias

- PRD: `doc/prd/US-CUTOVER-FOLLOWUP_prd.md`
- ADR padre: `doc/decisions/cloud_cutover.md` (v6.1.0)
- Backend tracking: FreeForm `ff-ed0c02f4565a`
- Release anterior: tag `v6.1.0` (PR #66, squash `25c9426`)

---

## Siguiente paso

```
/implement
```

Autopilot UC por UC: `find_next_uc` → `start_uc(UC-625)` → fases → commit → PR → merge → siguiente UC. Cierre al completar UC-633 + tag `v6.1.1`.
