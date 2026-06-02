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

# /switch-backend (US-BACKEND-SWITCH / US-BACKEND-SWITCH-NATIVE)

Orquestador guiado del cambio de backend de tracking entre los 4 backends de
spec-driven. Envuelve la tool atómica MCP `switch_project_backend` (que internamente
hace migrate + seed + switch + exit-report como **una operación todo-o-nada**) y
`regenerate_evidence` con una UX segura de principio a fin: preview obligatorio con
**confirmación de conteo**, confirmación literal y reporte auditable.

> **Garantía de no-pérdida**: la migración es **aditiva** — el backend origen
> permanece intacto y legible hasta que confirmes. Nada se borra. La evidencia de
> acceptance (`.quality/evidence/`) tampoco se toca: vive en el filesystem,
> independiente del board.

> **Garantía de atomicidad (US-BACKEND-SWITCH-NATIVE)**: el cambio es **todo-o-nada**.
> O queda todo coherente (datos migrados + los 3 lugares de config conmutados) o no
> queda nada a medias — si cualquier paso falla, se hace rollback total (incluida la
> migración de datos a Postgres si el destino era Native nuevo).

## Online-first (MCP remoto + cliente local)

> **Cambio US-BACKEND-SWITCH-NATIVE**: este skill **ya NO exige MCP local**. Cumple
> la decisión canónica "Transporte único MCP remoto + content-passing" (UC-668): el
> skill lee el source del **cliente** (con `Read`) y lo pasa por **content-passing**;
> al confirmar, escribe el contenido devuelto de los 3 lugares de config en el
> filesystem del **cliente**. El servidor MCP nunca toca un filesystem ajeno.

Implicación práctica: en MCP remoto, **nunca** dejes que el server resuelva el source
desde su propio filesystem. Para un origen `freeform`, lee `doc/tracking/items.json`
del cliente con `Read` y pásalo como `source_content`. Si el preview reporta 0 items o
un conteo inesperado (p.ej. el del engine), **PARA** — el source no es el tuyo.

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

## Paso 3 — Leer el source del cliente (content-passing)

> Solo para origen `freeform`. Para `trello`/`plane`/`native` el source vive detrás
> de una API/DB que el server lee directamente — sáltate la lectura local.

Si el origen es `freeform`:

1. Resuelve el path absoluto del cliente: `git rev-parse --show-toplevel` + `/doc/tracking/items.json`.
2. Lee ese archivo con la tool `Read`.
3. Tendrás su contenido en memoria para pasarlo como `source_content` en el preview.

---

## Paso 3b — Source grande hacia Native: ingesta por lotes (US-NATIVE-BATCH-INGEST)

> Solo aplica cuando **destino = native** y el `items.json` del cliente es grande
> (> ~64 KB). Un `items.json` real (133 KB / cientos de ítems) NO cabe fiablemente
> en un único parámetro `source_content` — pasarlo de golpe arriesga truncado/corrupción
> silenciosa, y el skill debe **negarse** a pasar un blob no verificable. En su lugar,
> usa la **ingesta por lotes**: troceo verificable del transporte + escritura atómica.

Decisión de ruta:

```
¿destino == native Y len(items.json en bytes) > 64 KB?
├── NO  → ruta estándar: pasa source_content de una pieza (Paso 4 / Paso 5).
└── SÍ  → ruta por lotes (este paso):
    1. Calcula sha256 del items.json completo y el nº de ítems (US+UC+AC) que vas a migrar.
    2. Trocea el items.json en chunks de ≤16 KB. Calcula sha256 de cada chunk.
    3. Presenta al usuario el PLAN DE TRANSPORTE antes de ejecutar:
```

```
📦 Plan de transporte por lotes — items.json grande → Native
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tamaño:  {N} KB        Ítems declarados: {US+UC+AC}
Chunks:  {M} × ≤16 KB  SHA-256 source:   {hash[:16]}…
La escritura sigue siendo atómica (commit diferido en 1 transacción, rollback total).
```

```
    4. start_migration_session(target_project_id={pid native}, source_type="freeform",
         declared_items={N}, declared_bytes={bytes}, source_sha256={hash},
         chunk_count={M}, dev_token={token del panel})
       → session_id. (NO escribe nada en Postgres todavía.)
    5. Por cada chunk i en orden:
         append_migration_chunk(session_id, chunk_index=i, chunk_data={chunk_i},
           chunk_sha256={hash_i}, dev_token={token})
       Si alguno devuelve CHUNK_HASH_MISMATCH → el transporte corrompió ese chunk;
       reenvíalo. No sigas al commit con un chunk dudoso.
    6. Confirma el conteo con el usuario (mismo guard rail del Paso 4) y ejecuta el
       switch atómico pasando batch_session_id en vez de source_content (Paso 5).
```

> El commit (dentro del switch o vía `commit_migration_session`) verifica que llegaron
> los M chunks, que el SHA-256 reensamblado == el declarado, y que el conteo parseado ==
> el confirmado, **antes** de escribir un solo INSERT. Si algo falla → no escribe nada.
> **NUNCA** le pidas al usuario que pegue el blob de 133 KB a mano.

---

## Paso 4 — Preview obligatorio (dry-run) + confirmación de conteo

**BLOQUEANTE**: antes de ejecutar nada, llama a la tool atómica en modo preview:

```
switch_project_backend(
  project_slug="{slug}",
  source_type="{actual}",
  target_type="{destino}",
  source_content={contenido de items.json leído en Paso 3, o None si no es freeform},
  target_id={id destino o None para crear},
  project_path=".",
  dev_token={token del panel si destino/origen es native, "" si no},
  dry_run=True
)
```

El preview devuelve `read_counts` (`us`/`uc`/`ac`) **leídos del cliente**, las
degradaciones de estado, la `collision` si el destino native ya tiene items, y el
`discarded_native_state` si el origen es native. Preséntalo:

```
📋 Preview de migración — {actual} → {destino}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Leídas DEL CLIENTE:  {read_counts.us} US / {read_counts.uc} UC / {read_counts.ac} AC

⚠️ Degradaciones de estado (si las hay):
  {Si el destino es Plane: UCs 'review' → 'in_progress', US 'user_stories' → 'backlog'.
   Si no: "ninguna".}

{Si el destino native ya existe (collision): item_count actual + pide on_collision.}
{Si el origen es Native: lista de reservas / developers / branches que NO se migran.}
```

### Guard rail de conteo (BLOQUEANTE — US-BACKEND-SWITCH-NATIVE)

Si `read_counts.us + read_counts.uc == 0`, o el conteo **no coincide** con lo que
esperas de tu repo (p.ej. lee 22/112 = el engine, en vez de tus 11/88) → **PARA**.
El source no es el tuyo (típico bug de path en MCP remoto). No ejecutes el real.

### Confirmación literal del conteo (BLOQUEANTE)

```
Voy a migrar {read_counts.us} US / {read_counts.uc} UC leídas de TU repo, de
{actual} a {destino}, y cambiar el backend activo. El origen NO se borra y la
operación es atómica (todo-o-nada). ¿Confirmas ese conteo? (escribe "migrar")
```

Si el usuario no confirma → PARAR.

---

## Paso 5 — Ejecutar el switch atómico + write-back

Tras la confirmación, llama a la MISMA tool con `dry_run=False` y el conteo confirmado:

```
switch_project_backend(
  project_slug="{slug}",
  source_type="{actual}",
  target_type="{destino}",
  source_content={mismo contenido del Paso 3, o None si usaste la ruta por lotes},
  batch_session_id={session_id del Paso 3b, o "" si pasaste source_content},
  target_id={id destino o None},
  project_path=".",
  dev_token={token si native},
  on_collision={"reuse"|"skip"|"fail" si hubo collision},
  dry_run=False,
  confirmed_count={"us": read_counts.us, "uc": read_counts.uc}
)
```

> **Ruta por lotes (Paso 3b)**: pasa `batch_session_id` (no `source_content`). El paso de
> escritura del switch ingesta los chunks acumulados de forma atómica; el resto de la
> operación (config de los 3 lugares) es idéntico y sigue siendo todo-o-nada — la config
> solo cambia si la ingesta tuvo éxito.

Internamente, **en una sola llamada todo-o-nada**: verifica el conteo, (target native)
exige dev_token, crea el proyecto destino, copia US/UC/AC **preservando estados**,
asocia el developer, (source native) recopila el estado descartado, y conmuta los **3
lugares de verdad** (registry / app_spec / settings). Si cualquier paso falla → rollback
total (incluida la migración de datos), y devuelve `rolled_back=true` con `failing_step`.

**Si la respuesta trae `rolled_back: true`** → reporta el fallo al usuario y NO continúes
al reporte de éxito; el proyecto quedó en su backend original.

**Write-back de los 3 lugares (cliente)**: si la respuesta incluye contenido de
`app_spec.md` y `settings.local.json` (porque el MCP remoto no escribe el FS del
cliente), escríbelos con la tool `Write` en sus rutas del repo:
`doc/app/app_spec.md` y `.claude/settings.local.json`. Verifica que
`.claude/settings.local.json` del cliente refleja el nuevo `backend_type`.

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
- **NUNCA** ejecutes `switch_project_backend(dry_run=False)` sin preview + confirmación del conteo.
- **NUNCA** ejecutes el real si el preview leyó 0 items o un conteo que no es el de tu repo.
- **NUNCA** dejes que el server resuelva un source `freeform` desde su propio filesystem en MCP remoto — pásalo por `source_content` (source pequeño) o por la ingesta por lotes del Paso 3b (source grande). Nunca pegues un blob grande no verificable en `source_content`.
- **NUNCA** borres ni modifiques el backend origen — la migración es aditiva.
- **NUNCA** continúes al reporte de éxito si la respuesta trae `rolled_back: true`.
- **NUNCA** muevas o alteres `.quality/evidence/` — solo se regenera vía `regenerate_evidence`.

## Tools MCP usadas

| Tool | Paso | Rol |
|------|------|-----|
| `detect_project_backend` | 1, 5 | Detectar backend actual / verificar consistencia |
| `Read` (cliente) | 3 | Leer `doc/tracking/items.json` del cliente (content-passing) |
| `set_migration_target` | 2 | Credenciales del destino (Trello/Plane) |
| `switch_project_backend` | 4, 5 | **Operación atómica**: preview (dry_run) + migrate+seed+switch+exit todo-o-nada con rollback |
| `start_migration_session` | 3b | Abrir sesión de ingesta por lotes (source freeform grande → Native) |
| `append_migration_chunk` | 3b | Subir un chunk hash-verificado del `items.json` |
| `commit_migration_session` | 3b/5 | Verificar integridad global + ingesta atómica (vía el switch o standalone) |
| `Write` (cliente) | 5 | Write-back de `app_spec.md` + `settings.local.json` en el repo del cliente |
| `regenerate_evidence` | 6 | Reejecutar acceptance por UC (opt-in) |

> `migrate_backend` y `switch_backend` siguen disponibles como tools sueltas, pero
> este skill usa `switch_project_backend` (atómica) — no las encadena a mano.
