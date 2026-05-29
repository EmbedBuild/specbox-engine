---
id: US-CLAIM-RENAME
ordinal: US-05
title: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
status: draft
hours:
owner: Jesús Pérez
created: 2026-05-23
updated: 2026-05-29
source: items.json (FreeformBackend)
---

# US-CLAIM-RENAME — Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel

## Como… quiero… para…

> # US-CLAIM-RENAME: Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel
> 
> **Horas estimadas:** 0
> **Pantallas:** 
> 
> Como usuario no técnico (o developer que empieza) que opera SpecBox, quiero que el concepto de coordinación multi-developer del Native Backend (la reserva temporal exclusiva de un UC por un developer) se llame "reservation" en vez de "claim", para entenderlo inmediatamente sin jerga de sistemas distribuidos.
> 
> **Contexto del concepto**
> 
> Un "claim" en el Native Backend es una **reserva temporal exclusiva** de un UC por un developer concreto, registrada en la tabla `uc_claims` (`(project_id, uc_id)` PK + `developer_id` + `branch` + `claimed_at`). No es un lock de DB ni una asignación impuesta por un jefe: es un marcador de coordinación social — "este UC me lo pido yo, no lo toquéis hasta que lo suelte". Mecánicamente, dos `claim_uc(UC-201)` concurrentes sobre el mismo `(project_id, uc_id)` colisionan en la PK y solo uno gana (el otro recibe `ALREADY_CLAIMED`). Su contrapartida es `release_uc`, que solo puede ejecutar el dueño (si no, `NOT_CLAIM_OWNER`). En `start_uc_atomic` el claim se hace en la misma transacción que el cambio de estado del UC a `in_progress`, de forma que nunca hay claim huérfano.
> 
> **Por qué renombrar**
> 
> "Claim" es jerga (claim check pattern, JWT claims, claim-based auth). Para un no técnico — la audiencia primaria del Control Panel — el verbo "reservar" (reservar una mesa, una sala, un libro) ya carga toda la semántica del concepto sin necesidad de explicación. Decisión tomada con el usuario el 2026-05-23: el término elegido es **reservation / reserve_uc** (descartados: `assignment` por implicar jerarquía, `lock` por sugerir bloqueo de DB y dar miedo, `checkout` por requerir conocer git/biblioteca en inglés).
> 
> **Alcance**
> 
> Dos repositorios cambian de forma coordinada:
> 
> 1. `specbox-engine` (este repo): renombre del término a nivel SQL (tabla, índices, columna `claimed_at`), Python (módulo, clases, errores, tools MCP, payloads, tests), docs (CLAUDE.md, READMEs, PRDs/plans históricos referenciados desde código activo), evidencia de tracking. **Backwards compatibility:** las tools MCP antiguas `claim_uc` / `release_uc` se mantienen como alias deprecados durante v5.35–v5.36 emitiendo warning, y se eliminan en v5.37. El payload de error mantiene también el campo viejo (`already_claimed` ⇄ `already_reserved`) durante el mismo periodo.
> 
> 2. `specbox-control-panel` (repo hermano en `/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/embed.build/repositorios/specbox-control-panel`): renombre del término en SQL (la API leerá la tabla renombrada, no hay tablas propias del panel para claims), API (endpoints, plugins, schemas), UI (ruta `/claims` → `/reservations`, `ClaimsPage`, `ClaimsIcon`, sidebar, breadcrumbs, copy en español, mock data, tipos), tracking (UC-005, UC-114, UC-125, descripciones, ACs), brand/VEG si menciona el término, tests E2E.
> 
> **Estrategia de release**
> 
> La US **no se inicia ahora** — el usuario está activamente implementando el Control Panel con la nomenclatura actual y romperla a mitad de implementación es costoso. La US se aborda **después** de cerrar el trabajo en curso del Control Panel. El orden de ejecución será: (1) merge en `specbox-engine` con alias deprecados activos → release v5.35.0 → (2) merge en `specbox-control-panel` consumiendo la nueva API y emitiendo el rename → (3) v5.37.0 elimina alias deprecados del engine. Mientras tanto los UCs del Control Panel ya mergeados (UC-005, UC-114, UC-125) siguen vivos con su nombre histórico — esta US los renombrará en su momento.
> 
> **Fuera de alcance**
> 
> - Cambiar la semántica del concepto (sigue siendo reserva exclusiva temporal sin TTL, sin auto-expiración, idempotente para el mismo dueño).
> - Tocar otras tablas del Native Backend (`developers`, `mcp_tokens`, `github_identities`, `audit_log`, `branch_registry`).
> - Renombrar el módulo `server/coordination/` completo — solo el archivo `claims.py` y su contenido.
> - Migrar datos de producción (la migración SQL `ALTER TABLE … RENAME` preserva todas las filas).
> - Cambiar el comportamiento de `release_uc` (sigue exigiendo ser el dueño).

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-601 | [Migración SQL: renombrar uc_claims → uc_reservations en specbox-engine](../uc/UC-028-migracion-sql-renombrar-uc-claims-uc-reservations-en-specbox.md) | review |
| UC-602 | [Renombrar módulo Python coordination/claims.py → reservations.py y todas las APIs internas](../uc/UC-029-renombrar-modulo-python-coordination-claims-py-reservations-.md) | review |
| UC-603 | [Actualizar tools MCP: reserve_uc, release_uc, payloads de error y meta heredada](../uc/UC-030-actualizar-tools-mcp-reserve-uc-release-uc-payloads-de-error.md) | review |
| UC-604 | [Alias deprecados claim_uc/ALREADY_CLAIMED + DeprecationWarning para v5.35-v5.36](../uc/UC-031-alias-deprecados-claim-uc-already-claimed-deprecationwarning.md) | review |
| UC-605 | [Renombrar tests: test_coordination_claims.py + test_native_handling.py + assertions](../uc/UC-032-renombrar-tests-test-coordination-claims-py-test-native-hand.md) | review |
| UC-606 | [Documentación del engine: CLAUDE.md, GLOBAL_RULES, READMEs, plans históricos](../uc/UC-033-documentacion-del-engine-claude-md-global-rules-readmes-plan.md) | review |
| UC-607 | [Coordinación cross-repo: ventana de release v5.35.0 + heads-up Control Panel](../uc/UC-034-coordinacion-cross-repo-ventana-de-release-v5-35-0-heads-up-.md) | review |
| UC-608 | [Control Panel — API: renombrar endpoint /claims/active → /reservations/active y schemas](../uc/UC-035-control-panel-api-renombrar-endpoint-claims-active-reservati.md) | review |
| UC-609 | [Control Panel — UI: ruta /claims → /reservations, ClaimsPage, sidebar, breadcrumbs, copy](../uc/UC-036-control-panel-ui-ruta-claims-reservations-claimspage-sidebar.md) | review |
| UC-610 | [Control Panel — Mock data, tipos compartidos y tests E2E Playwright](../uc/UC-037-control-panel-mock-data-tipos-compartidos-y-tests-e2e-playwr.md) | review |
| UC-611 | [Control Panel — Docs (CLAUDE.md, README, app_spec.md, app_prd.md)](../uc/UC-038-control-panel-docs-claude-md-readme-app-spec-md-app-prd-md.md) | review |
| UC-612 | [v5.37.0: eliminación de alias deprecados (tool claim_uc, código ALREADY_CLAIMED, campo claimed_at)](../uc/UC-039-v5-37-0-eliminacion-de-alias-deprecados-tool-claim-uc-codigo.md) | ready |
| UC-613 | [Eliminar deuda de wire-protocol cross-language: renombrar cache JSON + hook Node + endpoint REST de claim → reservation](../uc/UC-040-eliminar-deuda-de-wire-protocol-cross-language-renombrar-cac.md) | done |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
