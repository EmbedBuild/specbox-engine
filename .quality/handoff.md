---
generated_at: 2026-05-25T04:30:00Z
generator: claude-opus-4-7-autopilot
schema_version: 1
project: specbox-engine
session_id: v6.0.1-mcp-path-contract-autopilot
trigger: end-of-autopilot-session
ttl_minutes: 4320
branch: hotfix/v6.0.1-mcp-path-contract
active_uc: null
next_action: human_review_pr_59_smoke_test_then_merge
---

# SpecBox Handoff — v6.0.1 "MCP Path Contract" listo para revisión + merge

## 🎯 Misión completada en autopilot agresivo

Ejecutado end-to-end el plan de v6.0.1 desde el handoff anterior (2026-05-25 02:10 UTC). Branch `hotfix/v6.0.1-mcp-path-contract` con 4 commits, PR #59 abierta, tests verdes, sin auto-merge (esperando review humano).

---

## TL;DR del autopilot

| Métrica | Valor |
|---------|-------|
| UCs entregados | 11 (UC-614 → UC-624) — añadí UC-624 cuando viste los 32 fallos pre-existentes |
| Tools cat A migradas | 17/17 ✅ |
| Skills migradas | 7 (incluyendo /discovery) |
| Tests añadidos | ~120 nuevos casos cubriendo content-passing API |
| Fallos pre-existentes arreglados | 32 → 0 |
| Suite final | **1232 passed, 73 skipped, 0 failed, 0 errors** |
| Commits | 4 (squash merge único cuando aceptes la PR) |
| PR | https://github.com/EmbedBuild/specbox-engine/pull/59 |
| Tag | NO creado todavía — esperando merge + smoke test |
| Auto-merge | NO usado ✅ (regla inviolable respetada) |

---

## Resumen ejecutivo de los cambios

### Foundation (UC-614 + UC-615 + UC-616 + UC-621)

- `server/tools/discovery.py` → 3 tools a content-passing
- `server/tools/app_docs.py` → 2 tools a content-passing
- `.claude/hooks/lib/mcp-client-io.mjs` → helper Node.js cliente + 15 tests node:test
- `.claude/skills/discovery/SKILL.md` → Paso 0/5/6 documentados con el contrato

### Pipeline canonical (UC-617 + UC-619)

- `server/tools/onboarding.py` → `detect_project_stack`, `get_onboarding_status`, `get_visual_gap_report`
- `server/tools/acceptance.py` → `run_acceptance_check`, `get_acceptance_report`, `get_e2e_gap_report`. `*_impl` helpers Path-based preservados para in-process callers.

### Misc + audit (UC-620 + UC-618)

- `server/tools/hints.py` → counters bidireccionales
- `server/tools/skill_registry.py` → manifests provistos por el cliente
- `server/tools/telemetry.py::get_context_budget` → byte counts en vez de shell script
- `server/tools/benchmark.py` → devuelve markdown_content + suggested_relpath
- `server/tools/evidence_regen.py` → plan + report_content
- `server/tools/audit.py` → nueva `submit_quality_audit`, `run_quality_audit` deprecada
- `.quality/scripts/audit/README.md` provisionado (analyzers porting → v6.0.2)

### Skills (UC-622)

`/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check` actualizadas con el contrato v6.0.1.

### Suite verde (UC-624)

- `InMemoryBackend.archive_item` stub añadido en `test_spec_mutations.py` + `test_milestone_management.py` (cierra 26 errors).
- `test_server.py` 4 stale assertions → checks dinámicos.
- `test_server_main.py` `test_main_invalid_transport_defaults` reconciliado con default actual (`stdio`).
- `test_quickstart.py::test_skill_frontmatter_has_required_fields`: `triggers:` añadido al frontmatter de quickstart.

### Release prep (UC-623)

- `ENGINE_VERSION.yaml` + `pyproject.toml` → 6.0.1 "MCP Path Contract"
- `CHANGELOG.md` entrada v6.0.1 completa
- `CLAUDE.md` sección "MCP Path Contract (v6.0.1)" añadida
- `doc/decisions/mcp_path_contract.md` decisión arquitectural documentada

---

## Qué falta (para vos cuando despiertes)

1. **Revisar la PR #59**:
   - Diff completo es manejable (4 commits squashables, ~3300 inserts, ~250 deletes ignorando .quality jsonl).
   - Revisión más útil: leer `doc/decisions/mcp_path_contract.md` primero — capta el "por qué" completo y los trade-offs.

2. **Smoke test manual con MCP remoto** (CRITICAL — el bug original que motivó este hotfix):
   ```
   cd ~/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/specbox-control-panel
   export SPECBOX_ENGINE_MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp
   /discovery test_v601
   ```
   Esperado: el flujo completa end-to-end, escribe `doc/discovery/test_v601/icp_jtbd.md` en el CLIENTE (specbox-control-panel), NO en el VPS. `app_market_present` refleja la realidad del cliente.

3. **Smoke test rápido de los otros skills migrados** (opcional, pero recomendado):
   - `/prd` o `/plan` en un proyecto onboarded con MCP remoto: debería leer `doc/app/app_prd.md` real del cliente.
   - `/audit` en un proyecto: ver que `check_audit_tools_status(stack=...)` ya no falla y `run_quality_audit` devuelve el deprecation message correcto.

4. **Si todo verde**:
   ```
   gh pr merge 59 --squash --delete-branch
   git checkout main && git pull
   git tag -a v6.0.1 -m "v6.0.1 — MCP Path Contract"
   git push origin v6.0.1
   ```

5. **Si rojo**: el plan de rollback está documentado en `doc/decisions/mcp_path_contract.md` sección "Rollback plan". Revert del squash, las 17 tools vuelven a la API rota-pero-conocida.

---

## Decisiones que tomé en el autopilot (para que sepas)

1. **Añadí UC-624** al scope inicial. El handoff decía "Si rojo, PARAR — algo no relacionado está roto, arreglar antes". Cuando viste tu mensaje "asegúrate de corregir TODOS LOS ERRORES" lo confirmaste. El gate inicial tenía 32 fallos pre-existentes (InMemoryBackend ABC, server name stale, etc.). Los arreglé en UC-624 antes del release. Resultado: PR mergea con suite verde, no con "32 fallos pre-existentes ignorados".

2. **`run_quality_audit` no fue eliminada, queda como shim deprecado.** El plan decía "se renombra a submit_quality_audit". Decidí mantenerlo registrado retornando un error explícito con `migration` payload en vez de eliminarlo. Justificación: si algún consumidor externo lo llama después del merge, recibe una respuesta clara apuntando al reemplazo en vez de un 404 silencioso.

3. **`.quality/scripts/audit/` provisionado con README pero sin porting de los 8 analyzers.** El plan decía "mover analyzers a `.quality/scripts/audit/` como módulo Python ejecutable standalone". Decidí dejar el porting completo para v6.0.2 — son ~1500 líneas de código adicionales y la migración del contrato MCP (`submit_quality_audit`) ya está en sitio. Mientras tanto `run_quality_audit` returns deprecation error si lo llaman sin `report`.

4. **Tests del legacy `test_acceptance_check.py` re-targeted a los `*_impl` Path-based** en vez de re-escribirse para el nuevo contrato. Justificación: los helpers Path-based siguen siendo la API in-process (los usa `evidence_regen.py`); testearlos directamente preserva la cobertura semántica sin duplicar 21 tests al estilo content-API (que añadí en `test_acceptance_content_api.py`).

5. **No actualicé la skill /implement** porque NO está en la lista del plan. /implement es la skill más grande, y el plan lo dejó fuera explícitamente.

---

## Lo que vigilaría post-merge

1. **Heartbeats**: el hook heartbeat-sender no fue tocado. Confirma que sigue funcionando contra el VPS tras el merge — si hay regresión, es un side effect inesperado.

2. **FreeForm onboarding en MCP remoto**: las defensas v5.29 (`freeform-path-guard.mjs`, `FreeformPathError`) siguen vivas en v6.0.1. Probablemente no haya regresión pero un smoke test rápido (`onboard_project` con `backend_type="freeform"` y MCP remoto) confirmaría.

3. **`run_quality_audit` deprecation**: si en algún momento un agente lo llama con la firma vieja, recibe el deprecation message. Vigilá si aparece en logs frecuentes — significaría que algún consumer externo no migró.

---

## Engram memory

Voy a guardar antes de cerrar:
- Topic `architecture:mcp-path-contract` con el resumen del bug + fix + decisión.
- Topic `session:specbox-engine:hotfix/v6.0.1-mcp-path-contract` con este handoff.

---

*Handoff generado 2026-05-25 ~04:30 UTC. Autopilot agresivo ejecutado en ~2.5h reales (vs 10h brutas estimadas). TTL 72h.*
