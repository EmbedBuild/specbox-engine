---
generated_at: 2026-05-31T19:39:39Z
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
- **Last commit**: 7a40b79 "fix(release): add CHANGELOG.md [6.8.0] entry (last file missed in the v6.8.0 bump)"
- **Healing events this session**: 0
- **Open feedback (blocking)**: 0
- **Context tokens estimated this session**: 5099

## What this session did
- Cerró y entregó la feature US-CONN-TRANSPORT completa (9 UC): Hito 2 (audit analyzers a Node), Hito 4 (updater pedagógico extensión), deuda UC-661 AC-02 (/feedback al bridge). PR #85 mergeado a main.
- Release v6.8.0 'Connectivity UX' versionada y pusheada (HEAD 7a40b79) — requirió 2 commits de fix porque varios Edits fallaron en silencio y se commiteó con validador en rojo (lección crítica).
- Respondió por qué la extensión pide el directorio del engine (no clona: asume que ya lo clonaste; instala skills/hooks por symlink desde tu repo).
- Arrancó NUEVA feature vscode_autoclone: /discovery completado (READY_FOR_PRD), PRD escrito en doc/prd/US-VSCODE-AUTOCLONE_prd.md (1 US, 4 UC: UC-109..112, 8 AC).
- Decisiones de producto del auto-clone cerradas con el usuario y aplicadas al PRD.

## Decisions taken (with key)
- Auto-clone del engine: la extensión clona el repo PÚBLICO github.com/EmbedBuild/specbox-engine a ~/.specbox/specbox-engine (dir oculto gestionado).
- Clone AUTOMÁTICO sin confirmación previa (solo notifica); el showOpenDialog queda solo como degradación si el clone falla.
- git pull AUTOMÁTICO del clon gestionado en el update flow, SOLO si isManagedPath(engine)===true. Clon del usuario en otra ruta NUNCA se toca (protección ICP-1).
- Pipeline completo elegido (/discovery → /prd → /plan → /implement) para esta feature.

## Open questions
- El PRD US-VSCODE-AUTOCLONE está escrito pero NO commiteado ni importado al board FreeForm todavía. Falta: import_spec (content-passing) con UC-109..112 + AC-01..08.
- El board usa external_id con prefijos slug (US-CONN-*, UC numéricos hasta 108). Para esta feature: US-VSCODE-AUTOCLONE + UC-109..112. Verificar bloque libre antes de import_spec.
- El canal de output Bash/Read se atascó repetidamente toda la sesión (flush intermitente) — quedan wakeups obsoletos programados; descartar al disparar.

## Hot files (top N by edits this session)
- .quality/app_docs_drift.jsonl
- .quality/read_tracker.jsonl
- .quality/discovery_gate_events.jsonl

## Next concrete step
Commitear el discovery + PRD de vscode_autoclone (doc/discovery/vscode_autoclone/icp_jtbd.md + doc/prd/US-VSCODE-AUTOCLONE_prd.md) en una rama feature/US-VSCODE-AUTOCLONE, luego importar la spec al board FreeForm (import_spec content-passing con UC-109..112 / AC-01..08), luego /plan US-VSCODE-AUTOCLONE. La implementación toca vscode-extension/src/install.ts (resolveEnginePath + managedEnginePath/isManagedPath/ENGINE_REPO_URL) y updater.ts (git pull del gestionado) + tests autoclone.test.mjs.

## Pointers para la próxima sesión
_(none)_
