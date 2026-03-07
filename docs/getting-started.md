# Getting Started - SDD-JPS Engine v3.9.0

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

### 2. Instalar commands, skills y hooks

```bash
./install.sh
```

Esto instala:
- **Commands** como symlinks en `~/.claude/commands/` (legacy)
- **Skills** copiados a `~/.claude/skills/` (v3.5 — auto-discovery)
- **Hooks** copiados a `~/.claude/hooks/` (enforcement automatico)

### 3. Verificar instalacion

```bash
# Commands (legacy)
ls -la ~/.claude/commands/

# Skills (v3.5)
ls -la ~/.claude/skills/
# Deberias ver: prd, plan, implement, adapt-ui, optimize-agents, quality-gate, explore

# Hooks
ls -la ~/.claude/hooks/
```

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

# Implementar el plan (autopilot end-to-end)
/implement nombre_del_plan

# Auditar configuracion agentica
/optimize-agents audit

# Explorar un codebase (read-only)
/explore

# Verificar calidad antes de PR
/quality-gate check
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
| Instalar todo | `./install.sh` |
| Crear un PRD | `/prd "descripcion"` |
| Planificar feature | `/plan PROYECTO-N` |
| Implementar plan | `/implement nombre_plan` |
| Escanear widgets | `/adapt-ui /path/proyecto` |
| Auditar agentes | `/optimize-agents audit` |
| Explorar codebase | `/explore` |
| Verificar calidad | `/quality-gate check` |
| Ver patrones Flutter | `architecture/flutter/` |
| Ver patrones React | `architecture/react/` |
| Ver patrones Python | `architecture/python/` |
| Configurar Supabase | `infra/supabase/patterns.md` |
| Configurar Stripe | `infra/stripe/patterns.md` |
