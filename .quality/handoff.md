---
generated_at: 2026-05-31T12:42:40Z
generator: specbox-handoff-v1
schema_version: 1
project: specbox-engine
session_id: f8b8214744b6
trigger: manual
ttl_minutes: 1440
branch: main
active_uc: null
---

# SpecBox Handoff — specbox-engine

## State snapshot
- **Branch**: main
- **Active UC**: none
- **Backend**: freeform
- **Last commit**: 18451f5 "main"
- **Healing events this session**: 0
- **Open feedback (blocking)**: 0
- **Context tokens estimated this session**: 193773

## What this session did
- Analizado el incidente del PR #82 (v6.7.0): eliminar Python mato el modo Local del MCP y rompio FreeForm via extension (MCP remoto en VPS no toca el items.json del cliente)
- Reenfocada la arquitectura de conectividad: Discovery estrategico de 3 arquetipos (A remoto+content-passing / B local empaquetado / C bridge Node), elegido C
- Ejecutado el pipeline completo: /discovery -> /prd -> /plan para la feature specbox_connectivity_ux (4 US, 9 UC UC-660..668, 22 AC)
- Registrado el tracking en items.json via script con backup+guard (el MCP remoto no podia: prueba viva del bug) y regeneradas las capas us/ uc/ (21 US, 108 UC, 448 AC)
- Guardadas las decisiones en memoria (Engram + <redacted-token>.md)

## Decisions taken (with key)
- Arquetipo C -> transporte unico MCP remoto online-first + bridge Node (lib/mcp-client-io.mjs) para I/O FreeForm (offline no existe: Claude Code exige red, descarta B)
- FreeForm = first-class permanente (solo/local), no puente hacia Native
- Audit entra como US propia (US-CONN-AUDIT): analyzers Node solo recolectan senales FS, scoring+PDF se quedan server-side
- 4 US separadas (TRANSPORT/AUDIT/UPGRADE/GATE), orden de implementacion por dependencias decidido en /plan
- Actualizacion: auto-migrar config + explicar despues, inteligencia hibrida (extension detecta, server calcula plan); mover datos sigue pidiendo confirmacion
- Incluido el fix del drift gate (validar contra app_spec.md decisiones canonicas) como causa-raiz del #82
- Drift del Discovery resuelto como documented_exception: sustituye la decision canonica FreeForm-requiere-MCP-local

## Open questions
- 138 archivos de tracking modificados sin commitear (main, PR-only) -> falta crear rama + PR cuando el usuario autorice
- El porting exacto de los 8 analyzers (cuanta logica Python queda server-side) se afina en /implement de UC-663
- El smoke test de UC-660 (add_uc->mark_ac->find_next_uc en remoto) es el gate real de que FreeForm ya no esta roto

## Hot files (top N by edits this session)
- doc/tracking/items.json
- .quality/read_tracker.jsonl
- doc/tracking/index.json
- doc/tracking/README.md
- .quality/app_docs_drift.jsonl
- ...entar-nativebackend-sobre-el-specbackend-abc.md
- .../uc/UC-002-esquema-postgres-multi-tenant.md
- ...eccion-de-backend-nativo-opt-in-por-proyecto.md

## Next concrete step
Arrancar /implement sobre UC-660 (Hito 1, primer UC: tools de mutacion FreeForm con content-passing en server/tools/spec_mutations.py + spec_driven.py, preservando helpers *_impl para callers in-process). Es la base de la que dependen UC-661 y UC-662. Antes, crear rama feature/US-CONN-TRANSPORT y commitear los 138 archivos de tracking pendientes.

## Pointers para la próxima sesión
_(none)_
