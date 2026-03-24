---
name: engine-release
description: >
  Audits, cleans, and releases a new SpecBox Engine version. Checks for residual
  code, updates ENGINE_VERSION.yaml, CLAUDE.md, changelog, and pushes to remote.
  Use when the user says "release", "bump version", "new version", "cut release",
  "audit and release", "sube version", "prepara release".
context: direct
allowed-tools: Read, Grep, Glob, Bash(*), Write, Edit, Agent
---

# /release — SpecBox Engine Release Pipeline

Audita residuos, actualiza version, CLAUDE.md, changelog, y sube a remoto.

## Uso

```
/release [version] [codename]
```

**Ejemplos:**
- `/release 5.9.0` — Release con version explicita
- `/release 5.9.0 "Pipeline Guards"` — Con codename
- `/release` — Auto-detecta: bump minor desde version actual
- `/release patch` — Bump patch (5.8.0 → 5.8.1)
- `/release major` — Bump major (5.8.0 → 6.0.0)

---

## Paso 0: Resolver Version

### 0.1 Leer version actual

```bash
grep "^version:" ENGINE_VERSION.yaml | head -1
```

### 0.2 Calcular nueva version

```
¿Que recibi?
├── X.Y.Z explicito → Usar directamente
├── "patch" → Bump patch (X.Y.Z → X.Y.Z+1)
├── "minor" o sin argumento → Bump minor (X.Y.Z → X.Y+1.0)
├── "major" → Bump major (X.Y.Z → X+1.0.0)
└── Codename → Segundo argumento o preguntar
```

Si no se proporciona codename, **preguntar al usuario**:
> "Version {X.Y.Z} — ¿Con que codename? (ej: 'Pipeline Guards', 'FreeForm', etc.)"

### 0.3 Verificar estado git

```bash
git status --short
git branch --show-current
```

- Si hay cambios sin commitear → WARNING: "Hay cambios pendientes. Los incluire en el release commit."
- Si no esta en `main` → WARNING: "No estas en main. ¿Continuar en rama `{branch}`?"

---

## Paso 1: Auditoria de Residuos

Lanzar **3 auditorias en paralelo** usando Agent tool (subagent_type=Explore):

### 1.1 Codigo residual

Buscar en todo el proyecto:

- `TODO`, `FIXME`, `HACK`, `XXX` en archivos de codigo (`.py`, `.ts`, `.tsx`, `.sh`, `.dart`)
- `console.log`, `print(` en archivos de produccion (no tests, no scripts)
- Archivos `.bak`, `.orig`, `.tmp`, archivos vacios
- Imports no usados (buscar patrones comunes)
- Archivos en `server/` que no esten referenciados desde `server.py` o `tools/`

### 1.2 Consistencia de documentacion

- Version en `ENGINE_VERSION.yaml` vs `CLAUDE.md` header vs `pyproject.toml`
- Features listadas en ENGINE_VERSION.yaml que no estan en CLAUDE.md
- Skills listadas en CLAUDE.md que no existen en `.claude/skills/`
- Hooks listados en CLAUDE.md que no existen en `.claude/hooks/`
- Agents listados en CLAUDE.md que no existen en `agents/`
- Tools count en CLAUDE.md vs archivos reales en `server/tools/`

### 1.3 Integridad estructural

- `__init__.py` en cada directorio de `server/` y `server/backends/` y `server/tools/`
- Todos los backends en `server/backends/` importados en `auth_gateway.py`
- Archivos en `commands/` tienen correspondencia con `skills/`
- `install.sh` copia todas las skills que existen

### 1.4 Reporte de auditoria

Presentar resultados al usuario como tabla:

```
## Auditoria de Release v{X.Y.Z}

| Categoria | Estado | Hallazgos |
|-----------|--------|-----------|
| Codigo residual | OK/WARN | N TODOs, N console.logs, N archivos tmp |
| Documentacion | OK/WARN | N inconsistencias |
| Estructura | OK/WARN | N problemas |
```

**Si hay hallazgos WARN:**
- Listar cada uno con ubicacion (archivo:linea)
- Preguntar: "¿Corrijo estos N problemas antes de continuar con el release?"

**Si el usuario dice si:** Corregir automaticamente lo que sea safe:
- Eliminar archivos `.bak`, `.orig`, `.tmp`
- Corregir version inconsistente en docs
- NO eliminar TODOs (pueden ser intencionales)
- NO eliminar console.log/print (pueden ser logging real)

**Si el usuario dice no o no hay hallazgos:** Continuar al Paso 2.

---

## Paso 2: Recolectar Cambios para Changelog

### 2.1 Obtener commits desde ultima version

```bash
# Encontrar tag o commit de la version anterior
git log --oneline $(git log --oneline --all --grep="feat: v" | head -2 | tail -1 | cut -d' ' -f1)..HEAD
```

Si no hay tags, comparar con el commit del changelog anterior:

```bash
git log --oneline --since="$(grep -A1 'date:' ENGINE_VERSION.yaml | tail -1 | sed 's/.*date: //')" 2>/dev/null || git log --oneline -20
```

### 2.2 Categorizar cambios

Agrupar commits por tipo:
- `feat:` → Nuevas funcionalidades
- `fix:` → Correcciones
- `refactor:` → Refactorizaciones
- `docs:` → Documentacion
- `test:` → Tests

### 2.3 Generar changelog entries

Para cada cambio significativo, crear entrada con formato:
```yaml
- "tipo: descripcion clara y concisa"
```

**Reglas:**
- Maximo 15 entries (agrupar cambios menores)
- Cada entry empieza con `feat:`, `fix:`, `refactor:`, `docs:`, o `test:`
- Descripcion en ingles (consistente con changelog existente)
- No incluir merges, bumps, ni commits de infraestructura triviales

---

## Paso 3: Actualizar ENGINE_VERSION.yaml

### 3.1 Actualizar campos base

```yaml
version: {nueva_version}
codename: "{codename}"
release_date: {YYYY-MM-DD de hoy}
```

### 3.2 Agregar nuevas features

Revisar los cambios del Paso 2 y determinar que features nuevas se agregan a la lista.
Agregar bajo comentario `# New (v{X.Y.Z})`.

### 3.3 Agregar changelog entry

Agregar al inicio de la seccion `changelog:`:

```yaml
  {nueva_version}:
    date: {YYYY-MM-DD}
    changes:
      - "feat: ..."
      - "fix: ..."
```

---

## Paso 4: Actualizar CLAUDE.md

### 4.1 Version en header

```markdown
# SpecBox Engine v{nueva_version}
```

### 4.2 Secciones afectadas

Revisar cada seccion de CLAUDE.md y actualizar si los cambios del release la afectan:

- **"Que es este repositorio"** — Si se anaden nuevas capacidades top-level
- **"Stack soportado"** — Si se anade nuevo stack
- **"Gestores de proyecto"** — Si se anade nuevo backend
- **"Estructura del repositorio"** — Si hay nuevos directorios/archivos clave
- **"Available Skills"** — Si se anade nueva skill
- **"Hooks"** — Si se anade nuevo hook
- **"Agents"** — Si se anade nuevo agente
- **"Engine Version"** — Siempre: actualizar `Current: v{X.Y.Z} "{codename}"`
- **Tools count** — Si cambia el numero de tools MCP

### 4.3 Consistencia

- Todos los archivos referenciados en CLAUDE.md deben existir
- Tablas deben reflejar el estado actual del codigo
- Counts (108+ tools, etc.) deben ser precisos

---

## Paso 5: Actualizar pyproject.toml

```toml
version = "{nueva_version}"
```

---

## Paso 6: Commit y Push

### 6.1 Verificar cambios

```bash
git diff --stat
git status --short
```

Mostrar resumen al usuario de todos los archivos que se van a commitear.

### 6.2 Commit

```bash
git add ENGINE_VERSION.yaml CLAUDE.md pyproject.toml [otros archivos corregidos en auditoria]
git commit -m "feat: v{nueva_version} {codename} — {resumen de 1 linea}

{lista de cambios principales, max 5 lineas}

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### 6.3 Push

```bash
git push
```

### 6.4 Confirmacion final

```
## Release v{nueva_version} "{codename}" completado

- Commit: {hash corto}
- Archivos modificados: N
- Changelog: N entries
- Auditoria: {resultado}
- Pushed to: {remote}/{branch}
```

---

## Reglas de Seguridad

1. **NUNCA** hacer release si hay tests fallando (verificar con `pytest` o equivalente si hay tests)
2. **NUNCA** eliminar codigo sin confirmar con el usuario
3. **NUNCA** modificar archivos de `server/tools/` o `server/backends/` durante release — solo docs y config
4. Si la auditoria encuentra problemas criticos → **BLOQUEAR** release y reportar
5. El codename es obligatorio — si no se proporciona, preguntar
6. Siempre mostrar diff completo antes de commitear para que el usuario revise
