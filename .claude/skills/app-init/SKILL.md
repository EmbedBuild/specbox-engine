---
name: app-init
description: >
  Initialize or refresh the canonical project documents `doc/app/app_prd.md`
  and `doc/app/app_spec.md`. These are the single source of truth that
  `/prd`, `/plan`, and `/visual-setup` consult before asking the user
  questions whose answers can be inherited from the project. Idempotent:
  safe to run multiple times. Detects state (empty / tracking-populated /
  app-already-exists) and adapts behavior accordingly. Use when the user
  says "app init", "init app docs", "create canonical docs", "setup
  project canon", or after a fresh clone before running `/prd`.
context: direct
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git:*), Bash(pwd), Bash(realpath:*)
---

# /app-init — Inicializa o refresca documentos canónicos del proyecto

Genera o actualiza `doc/app/app_prd.md` y `doc/app/app_spec.md`. Son la
fuente de verdad que el resto del pipeline (`/prd`, `/plan`,
`/visual-setup`) consulta para no repreguntar al usuario lo que ya está
decidido a nivel de proyecto.

## Uso

```
/app-init                       # Detecta estado y actúa
/app-init --refresh             # Reescaner stack/backend y refrescar zonas auto
/app-init --upgrade-zones       # Para docs creados manualmente sin marcadores
/app-init --migrate-freeform-data  # Reservado para PR-9 (v5.28→v5.29 con datos en VPS)
```

---

## Paso 1 — Detectar estado del proyecto

Ejecuta esta detección antes de hacer nada:

1. **¿Estamos en un repo git?**
   ```bash
   git rev-parse --show-toplevel
   ```
   Si falla → aborta con mensaje "El skill /app-init requiere un repo git inicializado. Ejecuta `git init` primero."
   Si tiene éxito → guarda el path como `PROJECT_ROOT` (absoluto, será el que pase a `set_auth_token` para FreeForm).

2. **¿Existe `doc/app/`?**
   - Si **NO** → modo `init`.
   - Si **SÍ** y los archivos canónicos existen → modo `refresh` (no destructivo).
   - Si **SÍ** pero los archivos no tienen marcadores `@specbox:zone` → modo `upgrade_zones` (asistir al usuario para insertar marcadores sin destruir contenido).

3. **¿Existe `doc/tracking/`?**
   - Si **SÍ** → puede inferir stack y roadmap desde items.json.
   - Si **NO** → `/app-init` también creará `doc/tracking/` y configurará FreeForm como backend default.

4. **¿Existe `.claude/settings.local.json`?**
   - Si **SÍ** → respeta `specbox.autopilot.level` y `backend_type` existentes; solo añade lo que falte.
   - Si **NO** → genera con `level: "equilibrado"` y `backend_type: "freeform"` por defecto.

---

## Paso 2 — Modo `init`: crear desde cero

### 2.1 — Preguntas mínimas

**Una sola pasada de 5 preguntas** (no más). Las respuestas se mapean a las zonas `manual` de `app_prd.md` y `app_spec.md`.

```
1. Nombre del proyecto (corto, slug-friendly):
2. ¿Qué problema resuelve esta aplicación? (1-2 frases)
3. ¿Quién es la audiencia? Lista de targets/ICPs separados por coma.
4. Stack técnico principal: [Flutter | React | Python+FastAPI | Go | Apps Script | otro]
5. ¿Necesitas reporting externo a un cliente?
   [a] No — uso FreeForm (rápido, local, sin API)
   [b] Sí — Trello
   [c] Sí — Plane
```

> **Nota sobre la pregunta 5**: con autopilot `equilibrado` o superior, esta pregunta se auto-confirma a `freeform` (decision_key: `backend_selection`, default canónico de v5.29.0). Si el usuario quiere otro backend, debe declararlo explícitamente.

### 2.2 — Generar archivos

1. Crea `doc/app/` si no existe.
2. Lee `templates/app_prd.md.template` y `templates/app_spec.md.template` desde el engine.
3. Sustituye placeholders `{project_name}` y `{date_iso}` (ISO 8601 UTC).
4. Escribe `doc/app/app_prd.md` y `doc/app/app_spec.md` con las zonas pobladas según las respuestas del usuario:
   - **Zona `vision`** (manual): respuesta a la pregunta 2.
   - **Zona `audience`** (manual): respuesta a la pregunta 3, formato lista.
   - **Zona `scope`** (manual): vacío con placeholder para que el usuario rellene.
   - **Zona `roadmap`** (auto): vacío hasta primer `add_uc()`.
   - **Zona `stack`** (auto): respuesta a pregunta 4 + auto-detección complementaria de lockfiles (`pubspec.yaml`, `package.json`, `pyproject.toml`, `go.mod`).
   - **Zona `tracking_backend`** (auto): respuesta a pregunta 5 + path absoluto resuelto.
   - **Zona `autopilot`** (auto): refleja contenido de `settings.local.json`.

### 2.3 — Crear `doc/tracking/` si backend = freeform

Si la pregunta 5 = `[a] FreeForm`:

1. Crea `doc/tracking/` (relativo al repo) y resuélvelo a absoluto:
   ```bash
   ABS_TRACKING="$(pwd)/doc/tracking"
   ```
2. Llama a la tool MCP `set_auth_token`:
   ```
   set_auth_token(
     api_key="freeform",
     token="",
     backend_type="freeform",
     root_path=ABS_TRACKING  # ¡absoluto, requerido por v5.29!
   )
   ```
3. Llama a `setup_board(board_name=PROJECT_NAME)` para inicializar la estructura.

### 2.4 — Asegurar `.claude/settings.local.json`

Si no existe o no tiene la sección, escribe (o fusiona, no sobreescribir lo existente):

```json
{
  "specbox": {
    "backend_type": "freeform",
    "freeform_root_absolute": "/Users/.../doc/tracking",
    "autopilot": {
      "level": "equilibrado",
      "image_budget_eur_per_feature": 5
    }
  }
}
```

### 2.5 — Output al usuario

Resumen breve:

```
✅ /app-init completado.
   doc/app/app_prd.md          (6 zonas: 5 manuales + 1 auto)
   doc/app/app_spec.md         (6 zonas: 4 auto + 2 manuales/hybrid)
   doc/tracking/                (FreeForm, path absoluto: /Users/.../doc/tracking)
   .claude/settings.local.json (autopilot: equilibrado)

Próximo paso recomendado:
   /prd "tu primera feature"   — comenzar el flujo de desarrollo
```

---

## Paso 3 — Modo `refresh`

Cuando los docs ya existen:

1. **No tocar zonas `manual` ni `hybrid`.** Son del usuario.
2. **Refrescar zonas `auto`** desde fuentes vivas:
   - `stack` ← detectar lockfiles + framework files.
   - `tracking_backend` ← leer `.claude/settings.local.json`.
   - `autopilot` ← leer `.claude/settings.local.json` `specbox.autopilot`.
   - `roadmap` ← inferir desde `doc/tracking/items.json` (FreeForm) o llamar `list_us()` (Trello/Plane).
3. Usar `replace_zone_body(content, zone_id, new_body)` del módulo `server/app_docs/zones.py` para que las sustituciones sean seguras.
4. Antes de escribir, calcular `compute_signature` del documento previo y nuevo. Si son iguales, no escribir (preserva mtime y evita ruido en git).
5. Output: lista de zonas tocadas o "Sin cambios — todo sincronizado".

---

## Paso 4 — Modo `upgrade_zones`

Para proyectos donde el usuario creó `app_prd.md`/`app_spec.md` manualmente sin marcadores. Asistencia interactiva:

1. Lee el documento existente.
2. Detecta secciones por encabezado (`## 1. Visión`, `## 2. Audiencia`, etc.) y propone mapping a `manual` / `auto` / `hybrid` según contenido.
3. Muestra diff con marcadores propuestos.
4. **Pide confirmación** antes de reescribir.
5. Backup del original en `.quality/edits_backup/{date}_{filename}` antes de aplicar.

---

## Paso 5 — Validación final

Tras cualquier modo, valida los documentos resultantes:

```python
from server.app_docs.zones import parse_document, validate_document, ZoneKind
doc = parse_document("doc/app/app_prd.md")
issues = validate_document(doc, required_zones={
    "vision": ZoneKind.MANUAL,
    "audience": ZoneKind.MANUAL,
    "scope": ZoneKind.MANUAL,
    "success_metrics": ZoneKind.HYBRID,
    "roadmap": ZoneKind.AUTO,
    "stakeholders": ZoneKind.MANUAL,
})
errors = [i for i in issues if i.severity == "error"]
```

Si hay errores → muestra al usuario y aborta sin commitear cambios.

---

## Paso 6 — Auto-commit (opcional, no destructivo)

Si el usuario está en una rama feature/* y `git status` está limpio antes de la operación, el skill puede proponer un commit:

```
He generado los documentos canónicos. ¿Crear commit ahora?
  [s] Sí — `chore: init app_prd.md + app_spec.md (v5.29.0)`
  [n] No — los dejo sin commitear
```

**No** crear commit automáticamente sin confirmación del usuario.

---

## Reglas inviolables

- Nunca borrar contenido de zonas `manual`.
- Nunca sobrescribir zona `hybrid` antes del marcador `<!-- engine-entries-below -->`.
- Si una operación de refresh fallaría por documento mal formado (errores del parser), abortar limpiamente y mostrar los errores — nunca dejar el documento en estado inconsistente.
- Path FreeForm SIEMPRE absoluto (validado por `FreeformBackend` y `set_auth_token` desde v5.29.0 PR-1).

---

## Ejemplo de invocación end-to-end

```
$ /app-init

🔍 Detectando estado del proyecto...
   PROJECT_ROOT = /Users/me/myproject
   doc/app/        no existe
   doc/tracking/   no existe
   settings.local  no existe
   → modo: init (proyecto nuevo)

📝 5 preguntas mínimas:
   1. Nombre: myproject
   2. Problema: "Plataforma para gestionar X..."
   3. Audiencia: PMs, devs senior
   4. Stack: React 19
   5. Backend tracking: [a] FreeForm  ← auto-confirmado por equilibrado

⚙️  Generando...
   doc/app/app_prd.md         escrito (6 zonas)
   doc/app/app_spec.md        escrito (6 zonas)
   doc/tracking/              inicializado (board: myproject)
   .claude/settings.local.json escrito (autopilot: equilibrado)

✅ Listo. Próximo: /prd "tu primera feature"
```
