---
generated_at: 2026-05-02T13:14:30Z
generator: specbox-handoff-v1
schema_version: 1
project: specbox-engine
session_id: 6e5f258e3d95
trigger: manual
ttl_minutes: 1440
branch: chore/v5.29.0-docs-update
active_uc: UC-SB-1
---

# SpecBox Handoff — specbox-engine

## State snapshot
- **Branch**: chore/v5.29.0-docs-update
- **Active UC**: UC-SB-1
- **Backend**: unknown
- **Last commit**: b57fc5a "docs(v5.29.0): regenerate README + add changelog entries v5.26..v5.29"
- **Healing events this session**: 0
- **Open feedback (blocking)**: 0
- **Context tokens estimated this session**: 184

## What this session did
- Diseñé spec de .quality/handoff.md
- Creé handoff-builder.mjs con buildHandoffData/renderHandoff/writeHandoff
- Escribí skill /handoff con 7 pasos

## Decisions taken (with key)
- `engram_topic_format` → session:<project>:<branch> (permite filtrado por mem_search)
- `handoff_max_chars` → 14000 (3.5k tokens cap)

## Open questions
- ¿Versionar .quality/handoff.md? → leaning gitignored como resto de .quality/

## Hot files (top N by edits this session)
- specbox-state.json
- .quality/read_tracker.jsonl

## Next concrete step
Crear tests unitarios para handoff-builder en tests/hooks/handoff-builder.test.mjs y ejecutarlos.

## Pointers para la próxima sesión
_(none)_
