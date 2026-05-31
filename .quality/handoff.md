---
generated_at: 2026-05-31T16:05:00Z
generator: specbox-handoff-v1
schema_version: 1
project: specbox-engine
session_id: e64c4942
trigger: manual
ttl_minutes: 1440
branch: feature/US-CONN-TRANSPORT
active_uc: UC-660
---

# SpecBox Handoff — specbox-engine

## What this session did
- Creó rama feature/US-CONN-TRANSPORT + commiteó tracking de la feature (ebd2d14).
- Implementó UC-660 (content-passing FreeForm vía memory-mode) end-to-end, verde, committeado (9c44d34).
- Hubo 3 commits rotos intermedios por edits que aplicaron en sitio equivocado (funciones homónimas spec_driven/spec_mutations); arreglados con amend hasta dejar la suite en 107 passed / 0 failed.

## State snapshot
- **Branch**: feature/US-CONN-TRANSPORT
- **Active UC**: UC-660 — COMPLETO, verde, committeado (1a3c4f9)
- **Backend**: freeform (MCP remoto en VPS — no toca items.json local; ESE es el bug que UC-660 arregla)
- **Commits en la rama** (sobre main 18451f5):
  - ebd2d14 — tracking de la feature (4 US, 9 UC, 22 AC)
  - 63c35a3 (HEAD) — UC-660 content-passing (código + test + tracking marcado) ✅ VERDE

## UC-660 ✅ DONE Y VERDE
Content-passing para las 7 tools de mutación FreeForm vía **memory-mode en FreeformBackend**.
- FreeformBackend(items_content=...) → opera en memoria, root=None, get_items_content() devuelve string mutado. _regenerate_progress/archive/comments no-op en memoria.
- get_session_backend(ctx, *, items_content=None).
- add_uc, add_ac, update_uc, import_spec, start_uc, complete_uc, mark_ac, find_next_uc, **get_uc** + items_content (get_uc lo necesita porque start_uc/find_next_uc lo invocan).
- AC-01/02/03 verdes: tests/test_freeform_content_passing.py (12 passed).
- Suite: 229 passed sin MCP_URL / 229 con MCP_URL, 0 failed (verificado ANTES del commit final 63c35a3 (HEAD)).
- Divergencia plan→código (memory-mode vs *_impl) documentada en doc/tracking/uc/UC-100-*.md.

## Lecciones de esta sesión (LEER antes de seguir)
1. **pytest = `uv run pytest`**, NUNCA `python3 -m pytest` (el python homebrew no tiene pytest → "no tests ran", da falsos verdes/rojos).
2. **Los Edit con old_string del plan fallan silenciosamente** cuando la firma real difiere. spec_mutations.py y spec_driven.py tienen funciones HOMÓNIMAS (mark_ac/start_uc/complete_uc/update_uc). Las registradas como tools MCP son las de spec_driven.py (excepto add_uc/add_ac/update_uc que son spec_mutations). SIEMPRE leer la firma real antes de editar y VERIFICAR que el Edit aplicó (varios fallaron y commitée roto 2 veces, arreglado con amend).
3. Tras CADA Edit a una función con wiring nuevo, correr el test ANTES de commitear. Commitée d3608bd y 8a49ff6 rotos; 1a3c4f9 es el bueno.
4. ImportSpec.screens espera STRING, no lista.
5. Bash flush con retraso → correr a /tmp + Read.

## Próximo paso: UC-661 (bridge cliente)
- Archivo: `.claude/hooks/lib/mcp-client-io.mjs` (YA existe, 157 líneas, con resolveProjectRoot/readContentBundle/writeContentBundle + guard path-traversal + test mcp-client-io.test.mjs).
- AC-04: añadir readTrackingBundle()/writeTrackingBundle() (o reusar los existentes) para que skills FreeForm lean/escriban doc/tracking/ resolviendo raíz vía git rev-parse. Test node:test con guard activo.
- AC-05: las skills /prd /implement /feedback usan el bridge en vez de pasar paths al server (grep en .claude/skills/).
- Depende del contrato de UC-660 (string in/out) — YA cerrado.
- Test runner cliente: `node --test` (no pytest).
- Orden plan: UC-661 → UC-662 (FreeForm first-class onboarding extensión) cierra Hito 1.

## Hot files
- server/tools/spec_driven.py / spec_mutations.py / auth_gateway.py / backends/freeform_backend.py (UC-660, committed)
- .claude/hooks/lib/mcp-client-io.mjs (UC-661, next)
- tests/test_freeform_content_passing.py (UC-660 evidence)
