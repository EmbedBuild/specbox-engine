# Getting Started - SpecBox Engine v5.25.0

## Requisitos

- [Claude Code](https://claude.ai/code) instalado
- [VSCode](https://code.visualstudio.com/) (recomendado) o terminal con bash/zsh
- Git
- Node.js 18+
- Python 3.12+ (para el MCP server)

## Instalacion

### Opcion A: Extensi\u00f3n VSCode (recomendado, cross-platform)

La forma mas rapida de instalar SpecBox Engine en cualquier sistema operativo (Windows, macOS, Linux).

#### 1. Instalar la extension

Busca **"SpecBox Engine"** en el marketplace de VSCode, o desde la terminal:

```bash
code --install-extension jpsdeveloper.specbox-engine
```

#### 2. Clonar el repositorio

```bash
git clone https://github.com/jpsdeveloper/specbox-engine.git ~/specbox-engine
```

#### 3. Ejecutar el wizard de onboarding

Abre VSCode y ejecuta desde el Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`):

```
SpecBox: Onboard Project
```

El wizard:
1. Verifica prerequisitos (Node, Python, Claude Code, Engram)
2. Localiza el repositorio del engine (auto-deteccion o seleccion manual)
3. Instala skills, hooks y settings
4. Configura los MCP servers (SpecBox Engine + Engram)
5. Muestra un health check final

#### 4. Verificar instalacion

La status bar de VSCode mostrara:
- `SpecBox v5.25.0` (con check verde) — todo OK
- `SpecBox v5.25.0` (con alerta) — hay componentes por configurar

Tambien puedes abrir el panel lateral de SpecBox en la barra de actividad para ver el estado de cada componente.

---

### Opcion B: install.sh (macOS/Linux, CI/headless)

Para entornos sin interfaz grafica o automatizacion en CI:

```bash
git clone https://github.com/jpsdeveloper/specbox-engine.git ~/specbox-engine
cd ~/specbox-engine
./install.sh
```

Esto instala:
- **Skills** como symlinks en `~/.claude/skills/`
- **Hooks** copiados a `~/.claude/hooks/`
- **Settings** en `~/.claude/settings.json`
- **GGA** (Gentleman Guardian Angel) para cached lint

> **Nota:** `install.sh` no configura los MCP servers. En macOS/Linux, ejecuta manualmente:
>
> ```bash
> # Instalar Engram (memoria persistente — obligatorio)
> pip install engram
> # O con pipx:
> pipx install engram
> ```
>
> Luego configura los MCP servers en `~/.claude/settings.local.json`:
> ```json
> {
>   "mcpServers": {
>     "engram": {
>       "command": "engram",
>       "args": ["mcp", "--tools=agent"]
>     },
>     "specbox-engine": {
>       "command": "uv",
>       "args": ["run", "--directory", "~/specbox-engine", "specbox-engine"]
>     }
>   }
> }
> ```

---

## Uso en un proyecto nuevo

### Paso 1: Crear el CLAUDE.md del proyecto

Copia el template y personaliza:

```bash
cd /path/to/mi-proyecto
cp ~/specbox-engine/templates/CLAUDE.md.template CLAUDE.md
```

Edita CLAUDE.md reemplazando los placeholders `{...}` con los datos de tu proyecto.

### Paso 2: Configurar settings (opcional)

Si usas Agent Teams, Stitch o Plane:

```bash
mkdir -p .claude
cp ~/specbox-engine/templates/settings.json.template .claude/settings.local.json
```

### Paso 3: Empezar a desarrollar

```bash
# Crear un PRD para una nueva feature
/prd "Gestion de usuarios con roles y permisos"

# Generar plan de implementacion (incluye diseños Stitch si hay UI)
/plan PROYECTO-42

# Implementar el plan (autopilot end-to-end)
/implement nombre_del_plan

# Verificar calidad antes de PR
/quality-gate check

# Auditar configuracion agentica
/optimize-agents audit
```

## Actualizacion del engine

### Con extension VSCode
1. `git pull` en el repositorio del engine
2. Ejecutar `SpecBox: Install Engine` desde el Command Palette

### Con install.sh
```bash
cd ~/specbox-engine
git pull
./install.sh
```

## Referencia rapida

| Quiero... | Accion |
|-----------|--------|
| Instalar todo (VSCode) | `SpecBox: Onboard Project` |
| Instalar todo (terminal) | `./install.sh` |
| Verificar instalacion | `SpecBox: Health Check` |
| Crear un PRD | `/prd "descripcion"` |
| Planificar feature | `/plan PROYECTO-N` |
| Implementar plan | `/implement nombre_plan` |
| Escanear widgets | `/adapt-ui /path/proyecto` |
| Auditar agentes | `/optimize-agents audit` |
| Explorar codebase | `/explore` |
| Verificar calidad | `/quality-gate check` |
| Ver patrones Flutter | `architecture/flutter/` |
| Ver patrones React | `architecture/react/` |
