# `.quality/handoff.md` — Contrato formal

> Documento de continuidad de sesión. Lo escribe la skill `/handoff` y lo lee el hook `session-start.mjs` al arrancar la siguiente sesión.

---

## Propósito

Cuando una sesión de Claude Code se acerca al límite de la ventana de contexto (o el usuario quiere cerrar voluntariamente), persiste el **estado fino** que el checkpoint mecánico de `/implement` no captura: decisiones tomadas mid-session, hot files, próximo paso concreto, preguntas pendientes.

La sesión siguiente arranca leyendo este archivo vía `SessionStart` hook, evitando exploración ciega.

---

## Ubicación

```
<repo_root>/.quality/handoff.md
```

- Vive en `.quality/` junto al resto de telemetría.
- Por defecto **no versionado** (igual que el resto de `.quality/`).
- Convive con `specbox-state.json` (ese es snapshot machine-readable; este es human-readable narrativo).

---

## Estructura

```markdown
---
generated_at: 2026-05-02T14:33:12Z
generator: specbox-handoff-v1
schema_version: 1
project: <project-slug>
session_id: <hash-12-chars>
trigger: manual | auto-pre-compact | session-end
ttl_minutes: 1440
branch: <git-branch>
active_uc: <UC-XXX | null>
---

# SpecBox Handoff — <project>

## State snapshot
- **Branch**: <branch>
- **Active UC**: <UC-XXX (Phase N — Phase Name)> | none
- **Backend**: <freeform | trello | plane>
- **Last commit**: <sha> "<subject>"
- **Healing events this session**: <int>
- **Open feedback (blocking)**: <int>
- **Context tokens estimated this session**: <int>

## What this session did
- <bullet 1>
- <bullet 2>
- ...

## Decisions taken (with key)
- `<decision_key>` → <value> (<reason>)
- ...

## Open questions
- <question 1> → <state>
- ...

## Hot files (top N by edits this session)
- <path 1>
- <path 2>
- ...

## Next concrete step
<one paragraph or one-liner with the exact next action>

## Pointers para la próxima sesión
- Plan: <path or null>
- PRD: <path or null>
- Checkpoint: <path or null>
- Engram observation_id: <obs-id or null>
```

---

## Campos del frontmatter

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `generated_at` | ISO 8601 | sí | Timestamp UTC de generación |
| `generator` | string | sí | Identificador del generador. Valor fijo para v1: `specbox-handoff-v1` |
| `schema_version` | int | sí | Versión del schema. v5.30.0 = `1` |
| `project` | string | sí | Slug del proyecto (basename del CWD) |
| `session_id` | string | sí | Hash corto (12 chars) determinista por `cwd + date` para correlación con telemetría |
| `trigger` | enum | sí | `manual` (usuario llamó `/handoff`), `auto-pre-compact` (Claude lo invocó antes de compactar), `session-end` (hook on-session-end lo generó) |
| `ttl_minutes` | int | sí | TTL en minutos. Default `1440` (24h). Tras esto, `session-start.mjs` avisa que está stale |
| `branch` | string | sí | Rama git activa al momento de generar |
| `active_uc` | string\|null | sí | UC activo (de `.quality/active_uc.json`) o `null` |

## Secciones del cuerpo

Todas son **obligatorias**. Si una sección no aplica, debe escribirse el contenido literal `_(none)_` para que el parser la encuentre.

| Sección | Contenido |
|---------|-----------|
| `## State snapshot` | Bullets de estado mecánico (rama, UC, backend, commit, healing, feedback, context tokens) |
| `## What this session did` | Bullets narrativos (la sesión los enumera, no se autogenera) |
| `## Decisions taken (with key)` | Bullets formato `` `key` → value (reason)`` |
| `## Open questions` | Bullets de preguntas con estado |
| `## Hot files (top N by edits this session)` | Lista de paths relativos al repo |
| `## Next concrete step` | Texto libre (una acción, no roadmap) |
| `## Pointers para la próxima sesión` | Bullets formato `Plan: <path>` etc. |

---

## Reglas operativas

1. **Idempotente**: `/handoff` puede ejecutarse N veces. La N-ésima sobrescribe la anterior.
2. **TTL 24h**: tras `ttl_minutes`, `session-start.mjs` debe seguir leyéndolo pero adjuntar warning `[STALE]` al exponerlo.
3. **Tamaño máximo**: el archivo completo debe caber en ~3.5k tokens (~14k caracteres). Si excede, recortar primero `Hot files`, luego `What this session did`.
4. **No persistir secrets**: el contenido va a Engram también. Cualquier valor que parezca secret (`sk_*`, tokens, passwords) debe redactarse a `<redacted>` antes de escribir.
5. **Pointers verificables**: los paths en `Pointers` deben existir en disco al momento de escribir. Si no existen → omitir el bullet (no escribir un puntero roto).

---

## Validación

Validador: `.quality/scripts/validate-handoff.mjs <path>` (creado en Phase 1).

Comprueba:
- Frontmatter parsea como YAML válido.
- Todos los campos obligatorios del frontmatter presentes y con tipo correcto.
- `schema_version === 1`.
- Todas las secciones obligatorias presentes.
- Tamaño total ≤ 14000 chars.
- `branch` coincide con `git branch --show-current` (warning si no, no error — la sesión puede haber cambiado de rama).

Salida: exit 0 si válido, exit 1 con stderr describiendo el primer fallo.

---

## Engram companion

Cada vez que `/handoff` escribe el `.md`, también ejecuta:

```bash
engram save "session:<project>:<branch>" '<json-payload>'
```

donde `<json-payload>` es:

```json
{
  "type": "handoff",
  "schema_version": 1,
  "project": "<slug>",
  "branch": "<branch>",
  "session_id": "<hash>",
  "generated_at": "<iso>",
  "active_uc": "<UC-XXX|null>",
  "next_step": "<texto del Next concrete step>",
  "handoff_path": ".quality/handoff.md"
}
```

Permite a la próxima sesión hacer `mem_search "session:<project>:<branch>"` y traer la entrada exacta.

---

## Ejemplos

Ver `tests/fixtures/handoff/`:
- `valid-minimal.md` — handoff mínimo válido
- `valid-full.md` — handoff completo con todas las secciones pobladas
- `invalid-missing-section.md` — falta `## Open questions`
- `invalid-no-frontmatter.md` — sin frontmatter YAML
- `invalid-stale-ttl.md` — `generated_at` > `ttl_minutes` ago

---

## Integración con hooks y skills

| Componente | Uso |
|------------|-----|
| skill `/handoff` | Productor primario. Usa `handoff-builder.mjs` |
| hook `session-start.mjs` | Consumidor: lee al inicio de cada sesión |
| hook `on-session-end.mjs` | Productor secundario: si no existe handoff o es muy viejo, genera uno mínimo automáticamente al cerrar sesión |
| `heartbeat-sender.mjs` | Reporta `handoff_present` y `handoff_age_minutes` |
| `analyze-sessions.sh` | Métrica `handoff_rate` (% sesiones con handoff al cierre) |
