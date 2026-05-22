---
name: switch-backend
description: >
  Cambia el backend de tracking de un proyecto entre los 4 (FreeForm / Trello /
  Plane / Native) de forma guiada y sin pérdida de avance. Migra US/UC/AC/comments/
  estado al destino, actualiza atómicamente los 3 lugares de verdad, y ofrece
  regenerar evidencias. Use when the user says "switch backend", "cambiar backend",
  "migrar de FreeForm a Trello/Plane/Native", "mover el tracking a", "change tracking
  backend".
context: direct
---

# /switch-backend (US-BACKEND-SWITCH)

Orquestador guiado del cambio de backend de tracking entre los 4 backends de
spec-driven. Envuelve las tools MCP `migrate_backend`, `switch_backend` y
`regenerate_evidence` con una UX segura de principio a fin: preview obligatorio,
confirmación literal y reporte auditable.

> **Garantía de no-pérdida**: la migración es **aditiva** — el backend origen
> permanece intacto y legible hasta que confirmes. Nada se borra. La evidencia de
> acceptance (`.quality/evidence/`) tampoco se toca: vive en el filesystem,
> independiente del board.

## Precondición — MCP local (BLOQUEANTE)

Este skill escribe en el **filesystem local** del repo (`.claude/settings.local.json`,
`doc/app/app_spec.md`) y, para FreeForm, en `doc/tracking/`. Por tanto **requiere que
el MCP de SpecBox corra como proceso local (stdio)**, no como conector remoto (VPS).

```
¿El MCP de SpecBox es local (stdio)?
├── SÍ → continuar
└── NO (conector remoto / claude.ai) → AVISAR y PARAR:
    "El cambio de backend escribe el filesystem local. Reconecta SpecBox como
     MCP local (stdio) antes de continuar — un MCP remoto escribiría en el VPS,
     no en tu repo. Ver decisión canónica 'FreeForm requiere MCP local'."
```

## Uso

```
/switch-backend
/switch-backend a:native           # destino sugerido
/switch-backend de:freeform a:trello
```

---

## Paso 1 — Detectar backend actual

Llama a `detect_project_backend(project_path=".")`. Reporta al usuario el backend
actual y de qué fuente se infirió (settings / items.json / app_spec / default).

```
Backend actual: {freeform|trello|plane|native} (fuente: {...})
```

Si el detector no encuentra ningún backend → el proyecto no está onboardeado;
sugiere `/app-init` u `onboard_project` antes de migrar.

---

## Paso 2 — Elegir destino + credenciales (de forma segura)

Pregunta el backend **destino** entre los 3 restantes (nunca el actual). Una vez
elegido, solicita las credenciales del destino **según su tipo**, con esta tabla:

| Destino | Qué necesita | Cómo se aporta |
|---------|--------------|----------------|
| **FreeForm** | `root_path` absoluto del repo cliente | El skill lo resuelve vía `git rev-parse --show-toplevel` + `/doc/tracking`. No se pide por chat. |
| **Trello** | `api_key` + `token` | `set_migration_target` con las credenciales de Trello. |
| **Plane** | `base_url` + `api_key` + `workspace_slug` | `set_migration_target` con las credenciales de Plane. |
| **Native** | `project_id` + acceso a Postgres | El DSN se lee **exclusivamente** de la env var `SPECBOX_NATIVE_DSN` (Frontier 2). **NUNCA pidas el DSN por chat** ni lo escribas en ningún archivo. Si la env var no está, avisa al usuario de que la exporte y para. |

> **Regla Frontier 2 (inviolable)**: el DSN de Native jamás se solicita por chat,
> ni se persiste en sesión, ni se escribe en `meta.json` / `settings.local.json` /
> reportes. Solo vive en `SPECBOX_NATIVE_DSN`.

Para destinos Trello/Plane, llama a `set_migration_target` con las credenciales del
destino antes del preview.

---

## Paso 3 — Preview obligatorio (dry-run)

**BLOQUEANTE**: antes de ejecutar nada, llama a:

```
migrate_backend(
  source_type="{actual}",
  source_id="{board/project id actual}",
  target_type="{destino}",
  target_id={id destino o None para crear},
  dry_run=True
)
```

Presenta el preview al usuario con los counts y las degradaciones de estado:

```
📋 Preview de migración — {actual} → {destino}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User Stories:        {N}
Use Cases:           {N}
Acceptance Criteria: {N}
Comments:            {N}

⚠️ Degradaciones de estado (si las hay):
  {Si el destino es Plane: lista de UCs cuyo estado 'review' degradará a
   'in_progress' y US 'user_stories' → 'backlog'. Si no hay: "ninguna".}

{Si el origen es Native: aviso de que claims / identidad de developers /
 branches registradas NO se migran y se listarán en el reporte final.}
```

### Confirmación literal (BLOQUEANTE)

Pide confirmación **literal** antes de ejecutar. No continúes con `dry_run=False`
hasta que el usuario escriba una confirmación explícita:

```
Esto migrará {N} items de {actual} a {destino} y cambiará el backend activo del
proyecto. El origen NO se borra. ¿Confirmas? (escribe "migrar" para continuar)
```

Si el usuario no confirma explícitamente → PARAR, no ejecutar.

---

## Paso 4 — Ejecutar migración

Tras la confirmación literal:

```
migrate_backend(..., dry_run=False)
```

Esto migra US/UC/AC/comments/estado de forma aditiva e idempotente (vía
`external_id`). Si el destino es Native, siembra la identidad del developer; si el
origen es Native, recopila el estado de concurrencia descartado para el reporte.

Captura el resultado: `id_map`, counts de `migrated`/`skipped`/`errors`, y la
sección `discarded_native_state` si aplica.

---

## Paso 5 — Cambiar el backend activo (transaccional)

```
switch_backend(
  project_slug="{slug}",
  backend_type="{destino}",
  board_id="{id destino}",
  project_path="."
)
```

`switch_backend` actualiza **atómicamente los 3 lugares de verdad**:

1. `projects.json` (registry): `spec_backend` + `board_id` + `backend_history`.
2. `doc/app/app_spec.md` zona auto `tracking_backend`.
3. `.claude/settings.local.json` → `specbox.backend_type`.

Si **cualquiera** falla, hace **rollback** de los ya escritos y devuelve un error
que nombra el lugar fallido, dejando el proyecto en su backend original. En ese
caso, reporta el fallo al usuario y NO continúes al reporte de éxito.

Verifica la consistencia llamando a `detect_project_backend(".")` → debe devolver
el nuevo backend.

---

## Paso 6 — Reporte final (4 secciones)

Presenta al usuario un reporte con **exactamente estas 4 secciones**:

```
✅ Cambio de backend completado — {actual} → {destino}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. SWITCH + CONSISTENCIA
   - Items migrados: {N} US / {N} UC / {N} AC / {N} comments (skipped: {N})
   - 3 lugares de verdad actualizados: projects.json ✓ · app_spec.md ✓ · settings.local.json ✓
   - detect_project_backend confirma: {destino}

2. EVIDENCIA INTACTA
   - La evidencia de acceptance (.quality/evidence/) NO se ha movido ni alterado.
     Sigue indexada por uc_id lógico, así que el vínculo evidencia↔UC se mantiene.
   - ⚠️ Riesgo: la evidencia puede quedar STALE respecto al código si éste
     evolucionó. Considera regenerarla (sección 4).

3. ESTADO NATIVE DESCARTADO {solo si el origen era Native}
   - Claims activos descartados: {N} {listar uc_id + developer_id}
   - Identidad de developers no migrada: {N}
   - Branches registradas no migradas: {N}
   - Nota: los backends single-user no tienen el concepto multi-developer.
   {Si el origen NO era Native, omitir esta sección.}

4. REGENERACIÓN DE EVIDENCIAS (opcional)
   - Para refrescar la evidencia contra el código actual:
     ¿Quieres ejecutar regenerate_evidence ahora? (s/n)
   - Si SÍ → llamar regenerate_evidence(project_path=".") y mostrar el progreso
     por UC + el reporte en doc/migrations/.
   - Si NO → recordar que puede ejecutarse después con la tool regenerate_evidence.
```

---

## Anti-patterns

- **NUNCA** pidas el DSN de Native por chat ni lo escribas en disco (Frontier 2).
- **NUNCA** ejecutes `migrate_backend(dry_run=False)` sin preview + confirmación literal.
- **NUNCA** borres ni modifiques el backend origen — la migración es aditiva.
- **NUNCA** continúes al reporte de éxito si `switch_backend` hizo rollback.
- **NUNCA** muevas o alteres `.quality/evidence/` — solo se regenera vía `regenerate_evidence`.

## Tools MCP usadas

| Tool | Paso | Rol |
|------|------|-----|
| `detect_project_backend` | 1, 5 | Detectar backend actual / verificar consistencia |
| `set_migration_target` | 2 | Credenciales del destino (Trello/Plane) |
| `migrate_backend` | 3, 4 | Preview (dry_run) + migración N×N aditiva |
| `switch_backend` | 5 | Cambio transaccional de los 3 lugares con rollback |
| `regenerate_evidence` | 6 | Reejecutar acceptance por UC (opt-in) |
