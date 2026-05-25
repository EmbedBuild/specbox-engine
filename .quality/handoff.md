---
generated_at: 2026-05-25T02:10:00Z
generator: claude-opus-4-7-handoff
schema_version: 1
project: specbox-engine
session_id: v6.0.1-mcp-path-contract-prep
trigger: end-of-session
ttl_minutes: 4320
branch: main
active_uc: null
next_action: autopilot_aggressive_us_mcp_path_contract
---

# SpecBox Handoff — v6.0.1 "MCP Path Contract" listo para AUTOPILOT AGRESIVO

## 🎯 Misión para la sesión nocturna

**Implementar US-MCP-PATH-CONTRACT end-to-end en autopilot agresivo. Mañana por la mañana debe estar lista para commitear a main.**

- US ya creada en tracking (`doc/tracking/items.json`).
- Plan técnico completo en `doc/plans/v6.0.1_mcp_path_contract_plan.md` — **leer primero**.
- 10 UCs (UC-614 → UC-623), 58 ACs, ~32h estimadas.
- 7 UCs corren en paralelo, 3 secuenciales al final.

**MODO: autopilot agresivo, sin auto-merge, abrir PR único al final con squash merge.**

---

## TL;DR del bug

Durante la prueba de `/discovery test_inheritance_helper` en specbox-control-panel con MCP remoto (`SPECBOX_ENGINE_MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp`), la tool `start_discovery` devolvió `app_market_present: false` aunque el archivo existe en el cliente con contenido real.

**Causa raíz:** `Path(project_path).resolve()` en MCP remoto resuelve contra el filesystem del VPS, no del cliente. **17 tools cat A** tienen este bug arquitectural (auditoría completa en plan §1.3).

**Decisión arquitectural:** content-passing universal (las tools reciben contenido por parámetro, nunca tocan filesystem cliente). Reemplaza el patrón v5.29 absolute-path-only que solo funcionaba en MCP local.

---

## Estado actual del repo

- **Branch:** `main` (tag `v6.0.0` ya existe, mergeado)
- **Working tree:** limpio salvo `.quality/handoff.md`, `.quality/app_docs_drift.jsonl`, `.quality/read_tracker.jsonl`, `specbox-state.json`, `doc/tracking/items.json` (US nueva), `doc/plans/v6.0.1_mcp_path_contract_plan.md` (plan nuevo)
- **Active UC:** ninguno (`.quality/active_uc.json` no existe)
- **Backend:** freeform
- **MCP:** remoto (VPS)

---

## Pre-flight checklist (HACER ANTES DE NADA)

1. **Leer el plan completo:** `doc/plans/v6.0.1_mcp_path_contract_plan.md` — es la fuente de verdad de qué hacer.
2. **Confirmar que la US existe en tracking:**
   ```bash
   grep -A2 "US-MCP-PATH-CONTRACT" doc/tracking/items.json | head -10
   ```
3. **Confirmar branch:**
   ```bash
   git checkout main && git pull
   git checkout -b hotfix/v6.0.1-mcp-path-contract
   ```
4. **Confirmar suite verde antes de tocar nada:**
   ```bash
   .venv/bin/pytest tests/ -q 2>&1 | tail -20
   ```
   Si rojo, **PARAR** — algo no relacionado está roto, arreglar antes.

---

## Plan de ejecución (orden recomendado para autopilot)

### Fase 1 — Discovery + helper fundacional (paralelizable: UC-614, UC-621)

**UC-614** — Refactor `server/tools/discovery.py` a content-passing
- Archivos: `server/tools/discovery.py` (líneas 443-662 son las 3 @mcp.tool registradas).
- Cambiar firmas:
  - `start_discovery(feature_name, app_market_content, existing_artifact_content, mode="auto")`
  - `validate_discovery_completeness(feature_name, icp_jtbd_content)`
  - `detect_v60_migration_case(app_prd_content, app_spec_content, app_market_content, settings_local_json_content)`
- Eliminar `Path(project_path).resolve()`, `.read_text()`, `.write_text()`, `.exists()` de las 3 tools. Todo el state se computa sobre strings.
- Mantener helpers privados `_app_market_is_pristine_or_missing()`, `_validate_icp_jtbd()`, `_render_initial_icp_jtbd()` adaptados a strings.
- Tests nuevos: `tests/test_discovery_content_api.py` — 5 casos por tool (happy, empty, malformed, idempotent, partial bundle).
- Tests viejos `tests/test_discovery.py` adaptados.

**UC-621** — Helper cliente `mcp-client-io.mjs`
- Archivo nuevo: `.claude/hooks/lib/mcp-client-io.mjs`
- Exporta:
  ```js
  export function resolveProjectRoot()                  // git rev-parse --show-toplevel
  export function readContentBundle(paths)              // Array<string> → {path: content|null}
  export function writeContentBundle(bundle)            // {path: content} → escribe todos
  ```
- Tests Node: `tests/test_mcp_client_io.mjs` (puede ser un script bash que invoca node con mocks).

### Fase 2 — Skill /discovery (depende UC-614 + UC-621)

**UC-615** — Skill `.claude/skills/discovery/SKILL.md`
- Editar boot-detection (Paso 0): primero llamar a `resolveProjectRoot()` + `readContentBundle(['doc/app/app_market.md', 'doc/discovery/<feat>/icp_jtbd.md'])`.
- Pasar `app_market_content` + `existing_artifact_content` a `start_discovery`.
- Tras recibir `skeleton_content`, escribir con `writeContentBundle({'doc/discovery/<feat>/icp_jtbd.md': skeleton_content})`.
- Validación gate (Paso 6): re-leer artifact en cliente, pasar a `validate_discovery_completeness`.
- Smoke test manual al final (registrarlo en commit message): ejecutar `/discovery foo_bar` con SPECBOX_ENGINE_MCP_URL set.

### Fase 3 — Tools fundacionales (paralelizable: UC-616, UC-617, UC-619, UC-620)

**UC-616** — `app_docs.py`
- Archivos: `server/tools/app_docs.py` líneas 223-246 (las 2 @mcp.tool).
- Helpers internos (`read_app_docs(project_path)`, `get_inheritable_values(project_path)`) **permanecen Path-based** — solo cambian los wrappers @mcp.tool.
- Tests: `tests/test_app_docs_content_api.py`.

**UC-617** — `onboarding.py` (3 tools cat A)
- Archivos: `server/tools/onboarding.py` líneas 448-1270.
- `detect_local_root_path()` **sin cambios** (es declaración de contrato, no toca filesystem).
- `detect_project_stack(stack_signals: dict[str, str|None])`, `get_onboarding_status(project_files: dict[str, str|None])`, `get_visual_gap_report(design_inventory: dict[str, list[str]])`.
- Tests: `tests/test_onboarding_content_api.py`.

**UC-619** — `acceptance.py` (3 tools cat A)
- Archivos: `server/tools/acceptance.py`.
- `run_acceptance_check(prd_content, item_id, branch, code_diff)`, `get_acceptance_report(prd_content, evidence_files: dict)`, `get_e2e_gap_report(prd_contents: list[str])`.
- Tests: `tests/test_acceptance_content_api.py`.

**UC-620** — Bucket misc (7 tools)
- `evidence_regen.py`: `regenerate_evidence(prd_content, uc_evidence_inputs)`.
- `skill_registry.py`: `list_skills_v2(skill_manifests: list[dict])`, `discover_skills(skill_manifests, stack, keywords)`.
- `hints.py`: `get_skill_hint` / `record_skill_hint` — pasar counter al state registry MCP por `project_slug`.
- `telemetry.py`: `get_context_budget(file_inventory: dict[str, int])`.
- `benchmark.py`: `generate_benchmark_snapshot()` devuelve content string, sin output_path.
- Tests: `tests/test_misc_cat_a_content_api.py`.

### Fase 4 — Audit (UC-618, más complejo, hacer en serie)

**UC-618** — `audit.py` + mover analyzers a cliente
- `check_audit_tools_status(stack: str|None)` — content-passing.
- `run_quality_audit` se renombra a `submit_quality_audit(project, report: QualityReport)`.
- Los 8 analyzers en `server/audit/analyzers/` se **mueven o copian** a `.quality/scripts/audit/` como módulo Python ejecutable standalone.
- Skill `/audit` (UC-622) los invoca via `Bash` y envía el report ya construido.
- Tests: `tests/test_audit_content_api.py` + `tests/test_audit_analyzers_local.py`.

### Fase 5 — Migración skills + release (UC-622, UC-623, secuenciales al final)

**UC-622** — Migrar 6 skills
- `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check`.
- Cada uno: usar `readContentBundle()` en Paso 0, pasar contenido a tools refactoradas, `writeContentBundle()` al final si la tool devuelve contenido a escribir.
- Smoke test manual de cada uno.

**UC-623** — Release v6.0.1
- `CLAUDE.md`: nueva sección "## MCP Path Contract (v6.0.1)".
- `doc/decisions/mcp_path_contract.md`: nueva decisión arquitectural.
- `CHANGELOG.md`: entry v6.0.1.
- `ENGINE_VERSION.yaml`: bump a 6.0.1.
- `pyproject.toml`: bump.
- Crear PR único squash → merge → tag v6.0.1.

---

## Reglas inviolables para el autopilot

1. **PR ÚNICO al final.** No abrir 10 PRs separadas. Squash merge único de los 10 UCs cuando todo esté verde y testeado. Justificación: las APIs cambian en lockstep con sus consumidores (skills) — separar rompe main.
2. **NO AUTO-MERGE.** El humano (yo, jesusperezsanchez) revisa el PR final por la mañana y lo mergea manualmente.
3. **NO modificar las defensas v5.29 de FreeForm.** El hook `freeform-path-guard.mjs` y `FreeformPathError` siguen vivos. Marcarlos `@deprecated` en su header pero no eliminar.
4. **NO refactorizar tools cat B/C.** Solo las 17 cat A listadas en plan §1.3. Tocar cat B (state-pure) es out-of-scope porque NO están rotas.
5. **0 regresión.** `pytest tests/ -q` debe quedar verde al final. Si rojo, healing o revert.
6. **Commits intermedios OK** dentro de la rama `hotfix/v6.0.1-mcp-path-contract`, pero NO push de cada UC por separado — push al final cuando todo esté listo.
7. **Healing budget = 8 attempts por UC.** Si se agota en un UC, parar autopilot y dejar resumen en `.quality/handoff.md`.
8. **NO tocar v6.0 PRs ya mergeados.** v6.0.0 ya está cortado.

---

## Tests a correr al cierre (antes de abrir PR)

```bash
# Suite completa
.venv/bin/pytest tests/ -q

# Subsuites específicas nuevas
.venv/bin/pytest tests/test_discovery_content_api.py -v
.venv/bin/pytest tests/test_app_docs_content_api.py -v
.venv/bin/pytest tests/test_onboarding_content_api.py -v
.venv/bin/pytest tests/test_audit_content_api.py -v
.venv/bin/pytest tests/test_acceptance_content_api.py -v
.venv/bin/pytest tests/test_misc_cat_a_content_api.py -v

# Verificar que NO quedan Path(project_path).resolve() en @mcp.tool decorated functions
python3 << 'EOF'
import re, pathlib
violations = []
for f in pathlib.Path("server/tools").glob("*.py"):
    src = f.read_text()
    # Find @mcp.tool blocks
    for m in re.finditer(r"@mcp\.tool[^\n]*\n\s*(async )?def (\w+)\(([^)]*)\)", src, re.DOTALL):
        fn = m.group(2)
        params = m.group(3)
        if "project_path" in params and fn not in ["onboard_project", "upgrade_project", "set_auth_token"]:
            violations.append(f"{f.name}::{fn}")
if violations:
    print("FAIL — these tools still have project_path:")
    for v in violations:
        print(f"  - {v}")
    exit(1)
else:
    print("OK — no @mcp.tool with project_path remaining.")
EOF
```

---

## Mi recomendación de orden temporal para el autopilot

```
T+0min:    leer plan + crear branch
T+5min:    UC-614 + UC-621 en paralelo (split en 2 sub-Tasks)
T+90min:   UC-615 (depende UC-614 + UC-621)
T+120min:  Smoke test /discovery con MCP remoto — checkpoint humano-readable
T+130min:  UC-616 + UC-617 + UC-619 + UC-620 en paralelo (4 sub-Tasks)
T+300min:  UC-618 (más complejo, serie)
T+420min:  UC-622 (migrar 6 skills, parcialmente paralelizable)
T+540min:  UC-623 (docs + release prep)
T+580min:  Full test suite green
T+590min:  Push branch + abrir PR (NO auto-merge)
T+600min:  Resumen en handoff.md actualizado
```

10 horas brutas. Con autopilot agresivo + paralelización Task isolation (v5.32.0), debería caer a 4-5h reales.

---

## Si algo se atasca

- **Tests rojos persistentes:** healing intenta 3 veces; al cuarto fallo, comentar el test con `pytest.mark.xfail` + nota explicativa, seguir adelante, dejar issue en handoff para revisión humana.
- **Skill smoke test falla:** parar autopilot, dejar último UC en estado `review`, escribir diagnóstico en handoff.md.
- **MCP del servidor no responde:** trabajar offline (las tools nuevas no necesitan MCP para tests unitarios), sincronizar al final.
- **Conflict con main:** rebase contra main, si conflict en files que ya tocaste, resolver favor de tu cambio (estás refactoring esos archivos).

---

## Para la mañana siguiente (mensaje a mí mismo)

Cuando despiertes y leas esto, espero ver:
1. Branch `hotfix/v6.0.1-mcp-path-contract` con 10 UCs implementados.
2. PR abierta (no mergeada) en GitHub.
3. `pytest tests/` verde.
4. `.quality/handoff.md` actualizado con resumen real de qué hizo el autopilot.
5. Engram con observation del bug + fix + decisión.
6. Si algo se atascó, anotado claramente en el handoff.

Luego:
1. Reviso el PR.
2. Smoke test manual `/discovery test_v601 ` en specbox-control-panel.
3. Si verde → merge → tag v6.0.1 → push tag.
4. Si rojo → cherry-pick fixes o re-trabajo manual.

---

## Referencias

- Plan técnico: `doc/plans/v6.0.1_mcp_path_contract_plan.md`
- US tracking: `doc/tracking/items.json` (buscar "US-MCP-PATH-CONTRACT")
- Bug diagnosis original (sesión actual): conversación claude.ai 2026-05-25
- Engram topic: `architecture:mcp-path-contract`
- Patrón v5.29 que sustituye: `CLAUDE.md` sección "Cognitive Load Reduction" → BLOCKER fix

---

*Handoff generado 2026-05-25 02:10 UTC. TTL 72h. Trigger: end-of-session humano antes de autopilot nocturno.*
