# PRD: US-CUTOVER-FOLLOWUP — Cerrar deuda residual de Sala de Máquinas tras v6.1.0

> Origen: FreeForm backend `ff-ed0c02f4565a` | US-CUTOVER-FOLLOWUP
> Tipo: PRD Técnico (refactor/cleanup)
> Generado: 2026-05-25
> Release target: v6.1.1 "Cutover Followup" (patch)

## Resumen Ejecutivo

v6.1.0 "Cloud Cutover" (PR #66, tag pushed) eliminó la Sala de Máquinas pero quedaron 11 residuos en `main` distribuidos en código vivo (tool MCP `get_sala_de_maquinas`), docstrings de módulos productivos, hooks, skills, canónicos `doc/app/`, version manifest y la VSCode extension. El más grave es la tool MCP que sigue registrada y expuesta — un cliente que la llame recibe datos vivos del filesystem en vez de un error claro.

Esta US cierra los 11 residuos en una sola PR squashable (v6.1.1, patch release). Cero código nuevo, sólo deletes + cleanup de strings. La VSCode extension se mantiene viva: sólo se eliminan el comando `specbox.openDashboard` y la setting `specbox.dashboardUrl` (las otras 5 capacidades — install / health / onboard / mcp / status — son independientes).

## Alcance

### Incluye

- Eliminación de la tool MCP `get_sala_de_maquinas` y sus helpers asociados.
- Limpieza de docstrings que mencionan "Sala de Máquinas" en módulos productivos.
- Limpieza de menciones en hooks vivos, skills, canónicos `doc/app/`, `ENGINE_VERSION.yaml` features array, y `.claude/settings.local.json`.
- VSCode extension: eliminación quirúrgica del comando + setting Sala-related; bump 5.21.0 → 5.21.1.
- Release v6.1.1: version bump, CHANGELOG entry, actualización del ADR `cloud_cutover.md`.

### No incluye

- **Docs históricos** (PRDs/plans/research que mencionan Sala de Máquinas) — son ADRs de su época, se preservan.
- **CHANGELOG entries históricas** — no se reescribe historia, sólo se añade entry v6.1.1.
- **Commits históricos en `ENGINE_VERSION.yaml`** — el array `commits:` de versiones pasadas no se toca; sólo el array `features:` que es estado actual.
- **Refactor de NativeBackend / Coordination tools** — todo Supabase queda intacto (ya cerrado por v6.1.0).
- **Reapuntar VSCode extension a specbox_cloud** — fuera de scope; cuando specbox_cloud tenga URL pública se hará en otra US.

---

## Objetivos

1. **Cerrar superficie API expuesta** — eliminar la tool MCP `get_sala_de_maquinas` que sigue registrada tras el cutover.
2. **Cero referencias a Sala de Máquinas en código vivo** — docstrings, comentarios, instructions, hooks, skills, canónicos.
3. **Mantener historia auditable** — CHANGELOG histórico, doc/research, doc/plans, doc/prd intactos como ADRs.
4. **VSCode extension funcional sin dashboard** — preservar install/health/onboard/mcp/status, sólo quitar lo Sala-related.

---

## Estado Actual vs Propuesto

### ACTUAL (residuos identificados):

```
server/tools/state.py:969       def get_sala_de_maquinas(...)              CRITICAL (API viva)
server/server.py:135             "View the Sala de Máquinas global..."     instructions string
server/tools/benchmark.py:31     docstring "from Sala de Máquinas state"
server/audit/persistence.py:2    docstring "Sala de Máquinas can surface"
server/app_docs/drift_detector.py:26,321  docstrings + comentario funcional
.claude/hooks/app-docs-sync-guard.mjs:36   docstring
.claude/hooks/context-budget-guard.mjs:21  docstring
.claude/skills/plan/SKILL.md:584    mención heartbeat → Sala de Máquinas
.claude/skills/audit/SKILL.md:61    mención "visible en Sala de Máquinas"
.claude/skills/discovery/SKILL.md:414  "Métricas agregadas en Sala de Máquinas"
doc/app/app_spec.md:17,40         declara React 19 apuntando a server/dashboard/* eliminado
doc/app/app_prd.md:12,31          menciones en zonas vision + scope
ENGINE_VERSION.yaml:66            features array contiene "sala-de-maquinas-embedded"
.claude/settings.local.json:16    allowedTool "get_sala_de_maquinas"
vscode-extension/package.json:61-64,157-161  comando openDashboard + setting dashboardUrl
vscode-extension/src/extension.ts:56-57       registro del comando
```

### PROPUESTO:

```
✓ Tool get_sala_de_maquinas: ELIMINADA
✓ server.py instructions: limpia
✓ Todos los docstrings/comentarios/skills: sin mención
✓ Canónicos doc/app/: reflejo fiel del engine post-cutover
✓ ENGINE_VERSION.yaml features array: sin sala-de-maquinas-embedded
✓ .claude/settings.local.json: sin allowedTool eliminado
✓ VSCode extension: install/health/onboard/mcp/status intactos; comando openDashboard + setting dashboardUrl ELIMINADOS; bump 5.21.0 → 5.21.1
✓ Version: 6.1.0 → 6.1.1 "Cutover Followup"
✓ CHANGELOG.md: nueva entry [6.1.1]
✓ doc/decisions/cloud_cutover.md: nota de follow-up al final
```

---

## A Eliminar

- [ ] Tool MCP `get_sala_de_maquinas` y helpers privados sólo usados por ella en `server/tools/state.py`
- [ ] Línea 135 de `server/server.py` ("View the Sala de Máquinas global dashboard across all projects")
- [ ] Strings "Sala de Máquinas" / "sala_de_maquinas" en docstrings de 5 módulos Python
- [ ] Strings "Sala de Máquinas" en docstrings de 2 hooks Node
- [ ] Menciones en 3 SKILL.md (plan/audit/discovery)
- [ ] Filas + bullets Sala-related en `doc/app/app_spec.md` y `app_prd.md`
- [ ] String `"sala-de-maquinas-embedded"` del array `features:` en `ENGINE_VERSION.yaml`
- [ ] Entry `"mcp__specbox-engine__get_sala_de_maquinas"` en `.claude/settings.local.json`
- [ ] Comando `specbox.openDashboard` + setting `specbox.dashboardUrl` en `vscode-extension/package.json`
- [ ] Líneas 56-57 (registro del comando) en `vscode-extension/src/extension.ts`

## A Mantener

- Toda la infraestructura NativeBackend / Supabase / coordination tools (ya cerrada por v6.1.0)
- Todos los docs históricos (`doc/research/remote-management-audit.md`, planes v5.x, PRDs antiguos)
- Toda la VSCode extension salvo el comando + setting eliminados
- Entradas históricas de CHANGELOG.md (sólo se añade entry v6.1.1)
- Array `commits:` histórico de ENGINE_VERSION.yaml
- Tests existentes (la eliminación no necesita tests nuevos; los tests del dominio ya se eliminaron en v6.1.0)

---

## Plan de Implementación (alto nivel)

### Fase 1: Código vivo Python (UC-625 + UC-626)
- UC-625: eliminar `get_sala_de_maquinas` + helpers + limpiar `server.py` instructions.
- UC-626: docstrings en benchmark/audit/drift_detector.

### Fase 2: Hooks + Skills (UC-627 + UC-628)
- UC-627: docstrings en 2 hooks Node.
- UC-628: menciones en 3 SKILL.md.

### Fase 3: Canónicos + Manifest (UC-629 + UC-630 + UC-631)
- UC-629: `doc/app/app_spec.md` + `app_prd.md` cleanup.
- UC-630: `ENGINE_VERSION.yaml` features array.
- UC-631: `.claude/settings.local.json` allowedTools.

### Fase 4: VSCode Extension (UC-632)
- UC-632: comando + setting + bump + rebuild `out/`.

### Fase 5: Release (UC-633)
- UC-633: version bump 6.1.0 → 6.1.1, CHANGELOG entry, ADR update.

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Algún consumidor externo llama `get_sala_de_maquinas` | Baja | Bajo | Cliente recibe "tool not found"; specbox_cloud no la usa (lee Supabase directo). |
| Helpers privados de state.py compartidos con otras tools | Media | Medio | Auditar uso antes de eliminar; sólo eliminar los exclusivos a `get_sala_de_maquinas`. |
| Cambiar canónicos `doc/app/` rompe `app-docs-sync-guard` hook | Media | Bajo | Hook está en modo warning (no bloquea). Pasar `verify_app_docs` después. |
| VSCode extension rebuild falla por TS error | Baja | Bajo | El cambio es eliminar 2 líneas; tsc reportará si hay refs colgando. |
| Suite pytest rompe por imports muertos | Baja | Medio | Validar con `pytest -q` después de UC-625 y al final. |

---

## User Story

**ID**: US-CUTOVER-FOLLOWUP
**Nombre**: Cerrar deuda residual de Sala de Máquinas tras v6.1.0
**Actor**: Maintainer del engine (JPS)
**Horas estimadas**: 2.5h
**Pantallas**: ninguna (es cleanup interno)

> Como maintainer del engine, quiero eliminar todas las referencias residuales a la Sala de Máquinas que quedaron en `main` tras v6.1.0, para cerrar la superficie API expuesta (`get_sala_de_maquinas`) y dejar el código + docs + canónicos consistentes con la decisión arquitectural ya tomada.

---

## Use Cases

### UC-625: Eliminar tool MCP `get_sala_de_maquinas` + helpers asociados
- **Actor**: Maintainer
- **Horas**: 0.5h
- **Archivos**: `server/tools/state.py`, `server/server.py`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-01**: `grep -rn "def get_sala_de_maquinas" server/` retorna 0 matches.
- [ ] **AC-02**: Una llamada MCP a `get_sala_de_maquinas` recibe error de tool no registrada (no respuesta exitosa).
- [ ] **AC-03**: Los helpers privados en `server/tools/state.py` sólo usados por la tool eliminada también se eliminan (auditados por `grep` antes de borrar). Helpers compartidos con `report_*` se preservan.
- [ ] **AC-04**: `pytest -q` retorna ≥1190 passed, 0 failed tras la eliminación.

---

### UC-626: Limpiar docstrings Python (benchmark + audit + drift_detector)
- **Actor**: Maintainer
- **Horas**: 0.2h
- **Archivos**: `server/tools/benchmark.py`, `server/audit/persistence.py`, `server/app_docs/drift_detector.py`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-05**: `grep -rn "Sala de Máquinas" server/tools/benchmark.py server/audit/ server/app_docs/` retorna 0 matches.
- [ ] **AC-06**: Las funcionalidades de `generate_benchmark_snapshot`, `attach_audit_evidence` y `detect_app_docs_drift` siguen funcionando idénticamente (tests pasan).
- [ ] **AC-07**: Donde la docstring describía un consumidor externo, se reescribe para referirse a "consumidores externos (specbox_cloud, scripts ad-hoc)" en vez de a Sala de Máquinas específicamente.

---

### UC-627: Limpiar docstrings Node hooks
- **Actor**: Maintainer
- **Horas**: 0.1h
- **Archivos**: `.claude/hooks/app-docs-sync-guard.mjs`, `.claude/hooks/context-budget-guard.mjs`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-08**: `grep -n "Sala de Máquinas" .claude/hooks/*.mjs` retorna 0 matches.
- [ ] **AC-09**: Los hooks siguen siendo ejecutables con `node --check` (sintaxis JS válida) y conservan toda su lógica funcional (sólo se modifican comentarios).

---

### UC-628: Limpiar menciones en skills (plan/audit/discovery)
- **Actor**: Maintainer
- **Horas**: 0.2h
- **Archivos**: `.claude/skills/plan/SKILL.md`, `.claude/skills/audit/SKILL.md`, `.claude/skills/discovery/SKILL.md`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-10**: `grep -n "Sala de Máquinas" .claude/skills/{plan,audit,discovery}/SKILL.md` retorna 0 matches.
- [ ] **AC-11**: Donde el skill mencionaba telemetría "a Sala de Máquinas", se reescribe a "consumidores externos (specbox_cloud)" o se elimina si la mención era puramente descriptiva.
- [ ] **AC-12**: Los frontmatters `triggers:`, `name:`, `description:` de los 3 skills permanecen intactos.

---

### UC-629: Limpiar canónicos `doc/app/app_spec.md` + `app_prd.md`
- **Actor**: Maintainer
- **Horas**: 0.3h
- **Archivos**: `doc/app/app_spec.md`, `doc/app/app_prd.md`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-13**: La fila "Dashboard (Sala de Máquinas) | React | ^19.0.0" se elimina de la tabla de Stack en `app_spec.md`. Lo mismo con la fila "Dashboard build | Vite".
- [ ] **AC-14**: La línea de Stitch project_id en `app_spec.md` (zona brand_visual) elimina la mención "salvo Sala de Máquinas" o se reescribe sin ella.
- [ ] **AC-15**: En `app_prd.md` zona vision (línea 12) y zona scope (línea 31), las menciones a "164 tools + Sala de Máquinas" se reescriben de forma consistente con el estado post-cutover. Las versiones del documento se bumpean (`Versión del documento: 1 → 2`).

---

### UC-630: Limpiar `ENGINE_VERSION.yaml` features array
- **Actor**: Maintainer
- **Horas**: 0.05h
- **Archivos**: `ENGINE_VERSION.yaml`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-16**: El string `"sala-de-maquinas-embedded"` ya no aparece en el array `features:` (verificable: `grep "sala-de-maquinas-embedded" ENGINE_VERSION.yaml` → 0 matches en el array de features, las menciones en `commits:` históricos se preservan).

---

### UC-631: Limpiar `.claude/settings.local.json` allowedTools
- **Actor**: Maintainer
- **Horas**: 0.05h
- **Archivos**: `.claude/settings.local.json`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-17**: La entrada `"mcp__specbox-engine__get_sala_de_maquinas"` ya no está en ningún array `allowedTools` / `allow` de `.claude/settings.local.json`. El JSON sigue siendo válido (parseable).

---

### UC-632: VSCode extension — quitar comando + setting + bump 5.21.0→5.21.1
- **Actor**: Maintainer
- **Horas**: 0.4h
- **Archivos**: `vscode-extension/package.json`, `vscode-extension/src/extension.ts`, `vscode-extension/out/*` (rebuild)
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-18**: El comando `specbox.openDashboard` ya no figura en `vscode-extension/package.json` sección `contributes.commands`.
- [ ] **AC-19**: El setting `specbox.dashboardUrl` ya no figura en la sección `contributes.configuration`. JSON sigue válido.
- [ ] **AC-20**: Las líneas 56-57 (`registerCommand('specbox.openDashboard', ...)`) y cualquier import asociado ya no están en `src/extension.ts`. El rebuild `npm run compile` (o equivalente) pasa sin errores TypeScript.
- [ ] **AC-21**: La versión de la extensión se bumpea de `5.21.0` a `5.21.1` en `vscode-extension/package.json`.

---

### UC-633: Release v6.1.1 — version bump + CHANGELOG + ADR update
- **Actor**: Maintainer
- **Horas**: 0.7h
- **Archivos**: `ENGINE_VERSION.yaml`, `pyproject.toml`, `CLAUDE.md`, `CHANGELOG.md`, `doc/decisions/cloud_cutover.md`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-22**: `ENGINE_VERSION.yaml` `version: 6.1.0 → 6.1.1`, `codename: "Cloud Cutover" → "Cutover Followup"`.
- [ ] **AC-23**: `pyproject.toml` `version = "6.1.0" → "6.1.1"` y la `description` se actualiza.
- [ ] **AC-24**: `CLAUDE.md` header (`# SpecBox Engine v6.1.0`) y footer "Engine Version" bumpean a `v6.1.1 "Cutover Followup"`.
- [ ] **AC-25**: `CHANGELOG.md` añade entry `[6.1.1] - 2026-05-25 — "Cutover Followup"` con secciones Removed / Changed / Tests al inicio del archivo. Entradas históricas intactas.
- [ ] **AC-26**: `doc/decisions/cloud_cutover.md` recibe una sección final "v6.1.1 followup" documentando que la deuda residual quedó cerrada en esta release.

---

## Criterios de Aceptación (consolidado)

### Funcionales (26 ACs distribuidos en 9 UCs)

- [ ] **AC-01**: `grep -rn "def get_sala_de_maquinas" server/` → 0 matches. (UC-625)
- [ ] **AC-02**: Llamada MCP a `get_sala_de_maquinas` → tool not found. (UC-625)
- [ ] **AC-03**: Helpers exclusivos eliminados, helpers compartidos preservados. (UC-625)
- [ ] **AC-04**: `pytest -q` ≥1190 passed, 0 failed. (UC-625)
- [ ] **AC-05**: `grep "Sala de Máquinas" server/tools/benchmark.py server/audit/ server/app_docs/` → 0 matches. (UC-626)
- [ ] **AC-06**: Funcionalidades de benchmark/audit/drift siguen idénticas (tests pasan). (UC-626)
- [ ] **AC-07**: Docstrings reescritas mencionan "consumidores externos (specbox_cloud, scripts ad-hoc)". (UC-626)
- [ ] **AC-08**: `grep "Sala de Máquinas" .claude/hooks/*.mjs` → 0 matches. (UC-627)
- [ ] **AC-09**: Hooks pasan `node --check`. (UC-627)
- [ ] **AC-10**: `grep "Sala de Máquinas" .claude/skills/{plan,audit,discovery}/SKILL.md` → 0 matches. (UC-628)
- [ ] **AC-11**: Menciones reescritas o eliminadas según pertinencia. (UC-628)
- [ ] **AC-12**: Frontmatters de los 3 skills intactos. (UC-628)
- [ ] **AC-13**: Filas "Dashboard ..." eliminadas de tabla Stack en `app_spec.md`. (UC-629)
- [ ] **AC-14**: Línea Stitch project_id sin mención "salvo Sala de Máquinas". (UC-629)
- [ ] **AC-15**: `app_prd.md` zonas vision + scope sin "164 tools + Sala de Máquinas"; doc version bump. (UC-629)
- [ ] **AC-16**: `"sala-de-maquinas-embedded"` eliminado de array `features:`. (UC-630)
- [ ] **AC-17**: `mcp__specbox-engine__get_sala_de_maquinas` eliminado de `.claude/settings.local.json`; JSON válido. (UC-631)
- [ ] **AC-18**: Comando `specbox.openDashboard` eliminado de `vscode-extension/package.json`. (UC-632)
- [ ] **AC-19**: Setting `specbox.dashboardUrl` eliminado. (UC-632)
- [ ] **AC-20**: Líneas 56-57 de `extension.ts` eliminadas; `npm run compile` verde. (UC-632)
- [ ] **AC-21**: Extensión bumpeada a 5.21.1. (UC-632)
- [ ] **AC-22**: `ENGINE_VERSION.yaml` 6.1.0 → 6.1.1 + codename "Cutover Followup". (UC-633)
- [ ] **AC-23**: `pyproject.toml` versión + description actualizadas. (UC-633)
- [ ] **AC-24**: `CLAUDE.md` header + footer bumpean a v6.1.1. (UC-633)
- [ ] **AC-25**: `CHANGELOG.md` entry [6.1.1] al inicio. (UC-633)
- [ ] **AC-26**: `doc/decisions/cloud_cutover.md` sección "v6.1.1 followup" añadida. (UC-633)

### Técnicos (no validados por AG-09)

- [ ] Proyecto compila sin errores (Python imports + TS compile de extensión)
- [ ] `pytest -q` ≥1190 passed, 0 failed
- [ ] `node --test .claude/hooks/lib/*.test.mjs` 15/15

---

**Prioridad**: medium (deuda técnica, no bloqueante; pero get_sala_de_maquinas expuesta es una superficie API rota)
**Complejidad**: Baja (sólo deletes + cleanup de strings)
*Generado: 2026-05-25*
