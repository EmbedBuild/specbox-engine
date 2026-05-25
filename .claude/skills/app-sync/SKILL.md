---
name: app-sync
description: >
  Verify, repair, review, or rebuild the canonical project documents
  `doc/app/app_prd.md` and `doc/app/app_spec.md`. Runs the four
  subcommands of the v5.29.0 sync layer: --check (CI-friendly drift
  report), --repair (interactive auto-zone reconciliation), --review
  (human-mediated case-by-case), --rebuild-from-tracking (emergency
  regenerate). Use when the user says "app sync", "sync app docs",
  "check app drift", "reparar app docs", "rebuild canonical docs", or
  after an `app-docs-sync-guard` warning to act on the drift.
context: direct
allowed-tools: Read, Write, Edit, Bash(node:*), Bash(pwd), Bash(git:*)
---

# /app-sync — Reconciliación de documentos canónicos

Capa 5 del sistema de carga cognitiva (v5.29.0). Ejecuta el verificador,
reparador o reconstructor según el subcomando elegido. El hook
`app-docs-sync-guard.mjs` (PR-13) avisa cuando hay drift; este skill
es la forma legítima de resolverlo.

## Uso

```
/app-sync --check                  # Reporta drift (no escribe nada)
/app-sync --repair                 # Aplica reconciliación con confirmación previa
/app-sync --review                 # Modo interactivo, caso por caso
/app-sync --rebuild-from-tracking  # Emergencia: regenera desde 0
```

---

## Paso 0 — Comprobaciones previas

1. Ejecuta `git status`. Si hay cambios sin commitear que afectan a `doc/app/`, advierte al usuario y ofrece opciones:
   - Stashearlos antes de operar.
   - Continuar (aceptando que la operación los puede sobrescribir si tocan zonas auto).
   - Cancelar.
2. Llama a `verify_app_docs(project_path=".")` para obtener el estado actual.

---

## Subcomando `--check`

```
verify_app_docs(project_path=".")
```

Imprime el resultado en un formato amigable para humanos y CI:

```
🔎 App Docs Sync Check

  app_prd.md: signature 5fd3a1...    [in sync ✓]
  app_spec.md: signature 8c0f44...   [drift: signature changed since 2026-05-02 09:14]

Drift entries (1):
  [warning] app_spec — app_spec.md signature drifted since the last recorded sync.

Run /app-sync --review for a guided fix or /app-sync --repair to auto-reconcile.
```

Exit code:
- `0` si `in_sync=true`.
- `1` si hay errores estructurales (zonas malformadas).
- `2` si hay drift (warnings) pero estructuralmente OK.

CI puede invocar este skill como `/app-sync --check` y bloquear el merge cuando exit ≠ 0.

---

## Subcomando `--repair`

Reconcilia automáticamente las zonas `auto` desde la realidad del proyecto. Pasos:

1. `verify_app_docs(...)` para detectar drift.
2. Recolecta inputs vivos:
   - **stack** ← detectar lockfiles (`pubspec.yaml`, `package.json`, `pyproject.toml`, `go.mod`).
   - **tracking_backend** ← `detect_project_backend(project_path=".")` (PR-8).
   - **autopilot** ← `.claude/settings.local.json` → `specbox.autopilot`.
   - **roadmap** ← según backend: `list_us()` (Trello/Plane) o `doc/tracking/items.json` (FreeForm).
   - **canonical_decisions** ← `list_canonical_decisions(project_path=".")` (PR-7).
3. Llama a `apply_app_docs_sync(event_type, payload, project_path=".")` para cada evento aplicable:
   - `set_auth_token` con el backend detectado.
   - `lockfile_change` con el stack inferido.
   - `autopilot_config_change` con el contenido de settings.
   - `complete_uc` con las filas del roadmap (si el backend tiene items).
   - `canonical_decision_created` con la lista actual de canonicals.
4. Muestra un diff resumido de qué cambió en cada doc.
5. **Pide confirmación** antes de escribir.
6. Aplica los cambios.
7. Llama `record_app_docs_signature(project_path=".")` para sellar la nueva baseline.

**Reglas inviolables**:
- Nunca tocar zonas `manual`.
- Nunca borrar contenido `hybrid` por encima del marcador `<!-- engine-entries-below -->`.
- Si el usuario abortó previamente con `/app-sync --review`, respetar la decisión y no auto-reescribir hasta que el usuario invoque `/app-sync --repair --force`.

---

## Subcomando `--review`

Modo interactivo paso a paso. Para cada drift detectado:

```
[1/3] app_spec.md — zone "tracking_backend"
  Locked: backend_type=trello, board_id=abc123
  Current: backend_type=freeform (resolved from doc/tracking/)

  Acciones:
  [k]eep current  [r]evert to locked  [s]kip  [a]bort

>
```

Tras cada elección, ejecuta el sync correspondiente y avanza. Al final, sella signature.

Cuando el drift apunta a una **edición manual del usuario en zona auto**, ofrece:

```
He detectado que has editado manualmente la zona "roadmap" de app_prd.md.
  [k]eep my edits — convertir esta zona a `kind="manual"` (tú la mantienes)
  [d]iscard my edits — dejar al engine resincronizar
  [m]erge — mostrar diff y reconciliar manualmente
```

Hace backup en `.quality/edits_backup/{date}_{file}` antes de cualquier escritura.

---

## Subcomando `--rebuild-from-tracking`

Modo emergencia para casos donde los `app_*.md` se han corrompido o perdido. Pasos:

1. **Confirmación literal obligatoria**: el skill pregunta "Esto reemplazará completamente `doc/app/app_prd.md` y `doc/app/app_spec.md`. ¿Continuar? (escribe `RECONSTRUIR` para confirmar)".
2. Backup obligatorio de los archivos existentes (si hay) en `.quality/edits_backup/{date}_pre_rebuild/`.
3. Llama a `read_app_docs_tool(app_prd_content=<contenido>, app_spec_content=<contenido>)` (v6.0.1 content-passing — el cliente lee los archivos con `Read` y pasa el contenido como string) para extraer los valores manuales que se puedan recuperar (visión, audiencia, scope) — si no se pueden, queda en plantilla.
4. Genera `app_prd.md` y `app_spec.md` desde plantilla.
5. Aplica todos los eventos de sincronización (igual que `--repair`).
6. Sella signature.
7. Output con diff vs el backup.

**Cuándo usar**: solo después de un fallo grave (corrupción, conflicto de merge irrecuperable, etc.). El comando es destructivo y siempre pide confirmación literal.

---

## Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `unknown_event_type` | Llamada a `apply_app_docs_sync` con un evento no soportado | Verificar contra `EVENT_ZONE_MAP` en server/app_docs/sync.py |
| `document_not_present` | `doc/app/app_*.md` no existe | Ejecutar `/app-init` primero |
| `zone_not_found_in_document` | El template del proyecto no contiene esa zona | Revisar si fue eliminada manualmente; restaurar desde plantilla |
| Hook `app-docs-sync-guard` BLOCKING | `block_on_drift=true` y hay drift | Ejecutar `/app-sync --repair` antes del próximo commit |

---

## Telemetría

Cada operación de `/app-sync` que escribe en disco emite una observación Engram con:

- `topic_key: "app_docs_sync/{project}/{subcommand}"`
- `type: "sync"`
- Contenido: subcomando, eventos aplicados, hash anterior y nuevo, timestamp.

Si Engram no está disponible, la operación sigue siendo válida (auto-degradación). El log local en `.quality/app_docs_drift.jsonl` (escrito por el hook) sigue siendo la fuente primaria.

---

## Salida estándar

Todas las invocaciones terminan con un resumen como:

```
✅ /app-sync --repair completado
   app_prd.md  zonas tocadas: roadmap
   app_spec.md zonas tocadas: tracking_backend, autopilot
   Signature sellada en .quality/app_docs_sync.lock
   3 zonas auto reconciliadas, 0 zonas manual tocadas
```
