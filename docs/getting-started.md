# Getting Started - JPS Dev Engine v2.0.0

## Requisitos

- [Claude Code](https://claude.ai/code) instalado
- Git
- Terminal (bash/zsh)

## Instalacion

### 1. Clonar el repositorio

```bash
git clone <repo-url> ~/jps_dev_engine
cd ~/jps_dev_engine
```

### 2. Instalar commands globales

```bash
./install.sh
```

Esto crea symlinks en `~/.claude/commands/` apuntando a los commands del engine.
Los commands quedan disponibles globalmente: `/prd`, `/plan`, `/adapt-ui`, `/optimize-agents`.

### 3. Verificar instalacion

```bash
ls -la ~/.claude/commands/
```

Deberias ver symlinks a los archivos en el engine.

## Uso en un proyecto nuevo

### Paso 1: Crear el CLAUDE.md del proyecto

Copia el template y personaliza:

```bash
cd /path/to/mi-proyecto
cp ~/jps_dev_engine/templates/CLAUDE.md.template CLAUDE.md
```

Edita CLAUDE.md reemplazando los placeholders `{...}` con los datos de tu proyecto.

### Paso 2: Configurar settings (opcional)

Si usas Agent Teams, Stitch o Plane:

```bash
mkdir -p .claude
cp ~/jps_dev_engine/templates/settings.json.template .claude/settings.local.json
```

### Paso 3: Configurar agentes (opcional)

#### Opcion A: Subagentes legacy

Copia los agentes que necesites:

```bash
mkdir -p .claude/agents
cp ~/jps_dev_engine/agents/orchestrator.md .claude/agents/
cp ~/jps_dev_engine/agents/feature-generator.md .claude/agents/
# ... etc
```

#### Opcion B: Agent Teams (recomendado)

```bash
cp ~/jps_dev_engine/templates/team-config.json.template .claude/team-config.json
```

Activa Agent Teams en settings.json:
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### Paso 4: Empezar a desarrollar

```bash
# Crear un PRD para una nueva feature
/prd "Gestion de usuarios con roles y permisos"

# Generar plan de implementacion (incluye diseños Stitch si hay UI)
/plan PROYECTO-42

# Auditar configuracion agentica
/optimize-agents audit
```

## Actualizacion del engine

```bash
cd ~/jps_dev_engine
git pull
./install.sh
```

Los symlinks se actualizan automaticamente ya que apuntan a los archivos del repo.

## Estructura del engine

Ver [CLAUDE.md](../CLAUDE.md) en la raiz del repositorio para la estructura completa.

## Referencia rapida

| Quiero... | Accion |
|-----------|--------|
| Instalar commands | `./install.sh` |
| Crear un PRD | `/prd "descripcion"` |
| Planificar feature | `/plan PROYECTO-N` |
| Escanear widgets | `/adapt-ui /path/proyecto` |
| Auditar agentes | `/optimize-agents audit` |
| Ver patrones Flutter | `architecture/flutter/` |
| Ver patrones React | `architecture/react/` |
| Ver patrones Python | `architecture/python/` |
| Configurar Supabase | `infra/supabase/patterns.md` |
| Configurar Stripe | `infra/stripe/patterns.md` |
| Estilos UI | `uiux/` |
