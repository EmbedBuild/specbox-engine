---
name: handoff
description: >
  Persiste el estado fino de la sesión actual a `.quality/handoff.md` y a Engram
  como observación estructurada. Use when the user says "handoff", "save state",
  "guarda contexto", "persistir sesión", "voy a hacer compactación", or before
  `/clear`. CRITICAL: si Claude está por proponer compactación o el usuario
  menciona "compactar"/"nueva sesión", invocar este skill ANTES.
context: direct
allowed-tools: Read, Bash(*), Write, Edit
---

# /handoff — Session Continuity

Persiste un snapshot narrativo de la sesión activa para que la próxima sesión
arranque con el estado preciso. Es el complemento human-readable del checkpoint
mecánico de `/implement`.

Contrato: `doc/specs/handoff-spec.md`.

---

## Cuándo invocar

**Obligatorio**:
- Antes de proponer al usuario compactar la sesión.
- Antes de `/clear`.
- Cuando el usuario lo pide explícitamente ("handoff", "guarda estado").

**Recomendado**:
- Al cerrar voluntariamente una sesión con UC activo.
- Después de tomar varias decisiones que no quedaron en commits.

**No invocar**:
- En sesiones puramente exploratorias sin estado que persistir.
- Cuando ya hay un `.quality/handoff.md` < 5 min y nada cambió.

---

## Flujo

### Paso 1 — Recolectar estado mecánico

Importar y llamar `buildHandoffData()` desde `.claude/hooks/lib/handoff-builder.mjs`:

```bash
node -e "import('./.claude/hooks/lib/handoff-builder.mjs').then(m => console.log(JSON.stringify(m.buildHandoffData(), null, 2)))"
```

Esto retorna un objeto con: `branch`, `active_uc`, `backend`, `last_commit_*`,
`healing_events`, `blocking_feedback`, `context_tokens_est`, `hot_files`,
`pointers` (plan/prd/checkpoint).

### Paso 2 — Componer la narrativa

A partir de la conversación actual, redacta cuatro bloques:

#### a) `what_this_session_did` (3-7 bullets)
Verbos en pasado, una frase por bullet. Cosas que el usuario debería poder
reconocer al volver. **No** copiar el git diff — resumir intención.

Ejemplo:
- Scaffolded /handoff skill in .claude/skills/handoff/
- Refactored on-session-end.mjs to emit structured Engram payload
- Documented v5.30.0 plan in doc/plans/

#### b) `decisions_taken` (0-N bullets)
Formato: `` `decision_key` → value (reason)``. Si la decisión no tiene `key`
formal, usar texto descriptivo. Sólo decisiones tomadas en ESTA sesión.

Ejemplo:
- `engram_topic_format` → `session:<project>:<branch>` (permite mem_search filtrado)
- Skipped CI updates (out of scope per plan §7)

#### c) `open_questions` (0-N bullets)
Cosas sin resolver al cierre de sesión. Formato libre.

Ejemplo:
- ¿Versionar `.quality/handoff.md` o mantener gitignored? → pendiente
- ¿Engram structured payload rompe búsquedas legacy? → no validado

#### d) `next_concrete_step` (1 párrafo)
La acción exacta que la próxima sesión debe ejecutar primero. **Una** acción,
no un roadmap. Si hay UC activo, mencionar el comando o paso.

Ejemplo:
> Continuar Phase 3 del plan v5.30.0: crear `.claude/hooks/session-start.mjs`
> y registrarlo en `.claude/settings.json`.

### Paso 3 — Renderizar y escribir

Usar `writeHandoff(narrative, opts)`. Esto:
1. Construye `data` con `buildHandoffData()`.
2. Renderiza con `renderHandoff(data, narrative)`.
3. Escribe a `.quality/handoff.md`.
4. Devuelve `{ path, data }`.

Wrapper bash recomendado:

```bash
NARRATIVE_JSON='<JSON con los 4 bloques>'
node -e "
  import('./.claude/hooks/lib/handoff-builder.mjs').then(m => {
    const n = JSON.parse(process.env.HANDOFF_NARRATIVE);
    const out = m.writeHandoff(n, { trigger: 'manual' });
    console.log(JSON.stringify(out));
  });
" 
```

(Pasar `narrative` por env var `HANDOFF_NARRATIVE` para evitar problemas de quoting.)

### Paso 4 — Validar

```bash
node .quality/scripts/validate-handoff.mjs .quality/handoff.md
```

Si exit != 0, leer stderr y arreglar antes de continuar.

### Paso 5 — Persistir en Engram (estructurado)

Si `engram` está disponible:

```bash
PROJECT=$(basename "$(pwd)")
BRANCH=$(git branch --show-current)
TOPIC="session:${PROJECT}:${BRANCH}"

PAYLOAD=$(jq -nc \
  --arg type "handoff" \
  --argjson schema_version 1 \
  --arg project "$PROJECT" \
  --arg branch "$BRANCH" \
  --arg session_id "$SESSION_ID" \
  --arg generated_at "$GENERATED_AT" \
  --arg active_uc "$ACTIVE_UC" \
  --arg next_step "$NEXT_STEP" \
  --arg handoff_path ".quality/handoff.md" \
  '{type:$type, schema_version:$schema_version, project:$project, branch:$branch,
    session_id:$session_id, generated_at:$generated_at, active_uc:$active_uc,
    next_step:$next_step, handoff_path:$handoff_path}')

engram save "$TOPIC" "$PAYLOAD" 2>/dev/null || true
```

Fire-and-forget: si Engram falla, el handoff local sigue siendo útil.

### Paso 6 — Reportar al usuario

Mensaje final al usuario:

```
✅ Handoff persistido

Archivo:    .quality/handoff.md
Engram:     session:<project>:<branch>
Stale en:   24h

Podés:
  • Cerrar sesión con seguridad
  • Ejecutar /clear
  • Aceptar compactación si Claude la propone

La próxima sesión arrancará leyendo este archivo automáticamente.
```

---

## Idempotencia

`/handoff` es seguro de ejecutar N veces. Cada llamada:
- Sobrescribe `.quality/handoff.md`.
- Crea una nueva observación Engram (no actualiza la anterior, no es problema).

Si el usuario lo llama dos veces seguidas sin cambios, el segundo handoff es
prácticamente idéntico al primero salvo `generated_at` y `session_id`.

---

## Edge cases

| Caso | Comportamiento |
|------|----------------|
| Sin git repo | `branch=unknown`, `last_commit_*=unknown`. Sigue funcionando. |
| Sin Engram instalado | Skip Paso 5 sin error. Avisar al usuario que Engram no está. |
| Sin `SPECBOX_ENGINE_MCP_URL` | Skip Paso 6 sin error. |
| Archivo > 14000 chars | Builder trunca automáticamente con marca `_(truncated)_`. |
| Active UC sin checkpoint | `active_uc_display = uc_id` sin "Phase X". |
| Sin cambios git | `hot_files = []`, sección queda como `_(none)_`. |

---

## Anti-patterns

- **No** copiar el output de `git diff` literal en `what_this_session_did`. Resumí.
- **No** incluir secrets en `next_concrete_step`. El builder redacta `sk_live_*` y
  tokens de 32+ chars, pero el primer filtro sos vos.
- **No** dejar las cuatro secciones narrativas vacías. Si todo está vacío, el
  handoff no aporta sobre el checkpoint mecánico — mejor no escribirlo.
- **No** invocar `/handoff` en cada turno: pesa contra el contexto y satura
  Engram. Una vez por sesión (o antes de compactar) basta.
