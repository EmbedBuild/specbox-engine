# Decisión arquitectural — MCP Path Contract (v6.0.1)

**Fecha**: 2026-05-25
**Status**: Adoptada
**Ámbito**: 17 tools cat A en `server/tools/`
**Reemplaza**: el patrón v5.29 absolute-path-only (que mitigaba parcialmente el mismo bug para 2 tools)

## Contexto

v6.0.0 introdujo el módulo `/discovery` y la fundación multi-doc canónica. Durante la prueba con MCP remoto (`SPECBOX_ENGINE_MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp`) ejecutando `/discovery test_inheritance_helper`, la tool `start_discovery` devolvió `app_market_present: false` aunque el archivo `doc/app/app_market.md` existía en el cliente con contenido real.

**Causa raíz**: `Path(project_path).resolve()` en MCP remoto resuelve contra el filesystem del proceso MCP server (VPS), no del cliente. Las tools de cat A (filesystem-pure):

- Lecturas devuelven datos del VPS — típicamente nada, o el propio repo `specbox-engine` que vive ahí.
- Escrituras crean archivos en el VPS, invisibles para el cliente.
- El validador siempre lee del VPS, nunca del cliente.

Auditoría completa (2026-05-25) en `doc/plans/v6.0.1_mcp_path_contract_plan.md §1.3`: **17 tools cat A vulnerables** (de 19 totales — `detect_local_root_path` es declaración de contrato y `benchmark` se trata aparte por ser solo escritura).

## Opciones consideradas

| Opción | Trade-off | Veredicto |
|--------|-----------|-----------|
| **(a) Absolute-path universal** (extender patrón v5.29 a las 17 tools) | Mínima invasión, retro-compatible. **Pero**: solo funciona en MCP local (stdio); roto en MCP remoto, contenedores, multi-tenant SaaS, claude.ai web. Resuelve el síntoma, no la causa. Sigue asumiendo "MCP comparte filesystem con cliente". | ❌ Es deuda técnica con careta de fix |
| **(b) Content-passing universal** (las tools reciben contenido por parámetro, nunca tocan filesystem) | Más cambios. **Pero**: funciona idéntico en local/remoto/contenedor/multi-tenant. Elimina la clase entera de bugs filesystem-remote. Auto-documentado en firma. | ✅ Elegida |
| **(c) Híbrido** (cat A1 content-passing, cat A2 absolute-path) | Convivencia de dos patrones, dos paths de debugging, dos cosas que mantener. | ❌ Maximiza deuda técnica |

## Decisión

**Content-passing universal.** El cliente (skill o hook) es responsable de todo I/O contra el filesystem del repo del usuario. Las tools MCP operan únicamente sobre strings que el cliente pasa, y devuelven strings que el cliente escribe. Las tools quedan filesystem-agnósticas.

## Patrón canónico

**Antes (roto en MCP remoto):**
```python
@mcp.tool
def start_discovery(feature_name: str, project_path: str = ".", mode: str = "auto"):
    root = Path(project_path).resolve()
    market_path = root / "doc/app/app_market.md"
    app_market_present = market_path.exists()  # ← lee filesystem del MCP
    # ...
```

**Después (content-passing):**
```python
@mcp.tool
def start_discovery(
    feature_name: str,
    app_market_content: str | None = None,        # ← cliente provee
    existing_artifact_content: str | None = None, # ← cliente provee
    mode: str = "auto",
):
    app_market_present = (
        app_market_content is not None and app_market_content.strip() != ""
    )
    # ... toda la lógica opera sobre los strings, no toca filesystem
    return {
        "discovery_id": ...,
        "status": ...,
        "skeleton_content": "...",  # ← cliente escribe esto con Write
    }
```

**El cliente (skill) hace I/O:**
```yaml
# .claude/skills/discovery/SKILL.md (Paso 0)
- Read doc/app/app_market.md → app_market_content
- Read doc/discovery/<feat>/icp_jtbd.md (si existe) → existing_artifact_content
- Call mcp__SpecBox-MCP__start_discovery(feature_name, app_market_content, existing_artifact_content)
- Write doc/discovery/<feat>/icp_jtbd.md ← skeleton_content del response
```

El helper `.claude/hooks/lib/mcp-client-io.mjs` (UC-621) expone `resolveProjectRoot()`, `readContentBundle(paths)`, `writeContentBundle(bundle)` con path-traversal guard y rechazo de paths absolutos para el código Node.js de skills/hooks que necesiten orquestar bundles grandes.

## Excepciones documentadas

### Caso `submit_quality_audit` (UC-618)

Los 8 analizadores SQuaRE (`server/audit/analyzers/`) necesitan escanear el código real (lint, complexity, dup, security). Serializar un repo entero como bundle de contenidos no es viable. Solución: los analizadores se ejecutan en el cliente (script local invocado por skill `/audit`, ubicado en `.quality/scripts/audit/`), generan el `QualityReport`, y se envía solo el report al MCP via `submit_quality_audit(project, report)`.

Es **report-passing** en lugar de content-passing puro — la única excepción documentada. El porting de los 8 analizadores al cliente está reservado para v6.0.2; v6.0.1 deja el directorio `.quality/scripts/audit/` provisionado con un README descriptivo y `run_quality_audit` como shim deprecado que retorna error si se invoca sin `report`.

### Caso helpers internos no-`@mcp.tool`

Los helpers Path-based `read_app_docs(project_path)` y `get_inheritable_values(project_path)` (no decorados con `@mcp.tool`) siguen disponibles. Solo se usan dentro del proceso del MCP server (callers internos como `evidence_regen.py` y tests in-process), donde compartir filesystem con el cliente no aplica porque no hay cliente — son llamadas Python in-process.

## Out-of-scope para v6.0.1 (diferido a v6.1+)

- **Refactorizar tools cat B** (state-pure, ~136 tools): el `project_path` ahí no es path al cliente — es un identifier de proyecto en el state registry del MCP. No es bug.
- **Refactorizar tools cat C** (~12 tools híbridas): tocan paths internos del engine (no del cliente). No están rotas en remoto.
- **Eliminar formalmente `freeform-path-guard.mjs`**: el hook v5.29 sigue vivo en v6.0.1 como defensa en profundidad. Proyectos pre-v6.0.1 todavía lo necesitan para FreeForm onboarding.
- **Documentación pública** (blog post / migration guide) para usuarios del MCP externo.

## Compatibility

100% backwards-compatible para callers **in-process** (otros módulos Python del propio MCP). Las firmas `@mcp.tool` cambiaron sin deprecation warnings — justificación:

1. v6.0 lleva <24h en main; superficie de uso externo mínima.
2. Mantener compat duplica caminos de código y no resuelve el bug en remoto.
3. El único consumidor real son los skills del propio engine, que se migran en UC-622 del mismo PR (squash merge atómico).

## Rollback plan

Si el PR rompe algo no anticipado:

1. **Revert del squash merge** en main devuelve el engine a v6.0.0.
2. Las 17 tools vuelven a la API rota-pero-conocida (`project_path`).
3. Discovery v6.0 sigue roto en MCP remoto — workaround documentado: usar MCP local (stdio) hasta nuevo intento.

Tag `v6.0.1` no se crea hasta verificar smoke tests post-merge.

## Métricas de éxito (post-merge)

- ✅ Las 17 tools cat A no tienen parámetro `project_path` (excepto helpers internos no `@mcp.tool`).
- ✅ Suite `pytest tests/` verde end-to-end (1232 passed, 73 skipped, 0 failed).
- ✅ Smoke test manual `/discovery <feature>` en proyecto con MCP remoto completa con verdict `READY_FOR_PRD`.
- ✅ FreeForm onboarding sigue funcionando (hook v5.29 todavía vivo).
- ✅ Cero `Path(project_path).resolve()` en tools registradas con `@mcp.tool` (excepto el shim deprecado `run_quality_audit`).

## Referencias

- Plan técnico completo: `doc/plans/v6.0.1_mcp_path_contract_plan.md`.
- Patrón v5.29 que sustituye: `CLAUDE.md` sección "Cognitive Load Reduction" → BLOCKER fix.
- Bug discovery session: `.quality/handoff.md` (v6.0.1 hotfix context, 2026-05-25 02:10 UTC).
- Engram memory: topic `architecture:mcp-path-contract`.
