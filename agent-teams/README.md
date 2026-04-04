# Agent Teams - Orquestacion Multi-Agente Nativa de Claude Code

## Que son los Agent Teams

Agent Teams es una funcionalidad **experimental** de Claude Code que permite ejecutar
multiples agentes en paralelo dentro de una misma sesion. Cada agente (teammate) tiene
su propio contexto, sus propias reglas y acceso restringido a archivos especificos del
proyecto.

A diferencia de ejecutar un solo agente que hace todo secuencialmente, Agent Teams permite:

- Dividir una tarea compleja en subtareas especializadas
- Ejecutar trabajo en paralelo (ej: frontend y backend al mismo tiempo)
- Aislar contexto para que cada agente solo vea lo que necesita
- Reducir errores por conflictos de archivos

## Diferencia con subagentes legacy (.claude/agents/)

| Aspecto | Legacy (.claude/agents/) | Agent Teams |
|---------|--------------------------|-------------|
| Ejecucion | Secuencial, uno a la vez | Paralela, multiples teammates |
| Contexto | Compartido (todo el proyecto) | Aislado por File Ownership |
| Coordinacion | Manual (el usuario decide) | Lead Agent coordina automaticamente |
| Comunicacion | No existe entre agentes | message, broadcast, debate |
| Hooks | No disponibles | TeammateIdle, TaskCompleted |
| Conflictos | Frecuentes (archivos compartidos) | Prevenidos por File Ownership Matrix |
| Estado | Produccion | Experimental |

Los archivos en `.claude/agents/` siguen siendo utiles para tareas simples con un solo
agente. Agent Teams es para proyectos donde se necesita coordinacion real entre multiples
especialistas.

## Como habilitar Agent Teams

### 1. Variable de entorno

En el archivo `.claude/settings.json` del proyecto:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

O como variable de entorno en tu shell:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

### 2. Configuracion del equipo

Copiar el template de configuracion al proyecto:

```bash
cp specbox-engine/agent-teams/templates/team-config.template.json \
   mi_proyecto/.claude/team-config.json
```

Ajustar los roles y File Ownership segun el stack del proyecto.

### 3. Prompts de teammates

Copiar los prompts necesarios:

```bash
cp specbox-engine/agent-teams/prompts/lead-agent.md \
   mi_proyecto/.claude/team-prompts/lead.md
```

## Patron Lead Agent (Coordinador)

El Lead Agent es el teammate que **coordina pero no implementa**. Su rol es:

1. **Planificar**: Recibe la tarea del usuario y la descompone en subtareas
2. **Delegar**: Asigna cada subtarea al teammate especializado
3. **Monitorear**: Revisa el progreso y resuelve bloqueos
4. **Sintetizar**: Combina los resultados y reporta al usuario

Reglas del Lead Agent:

- NUNCA modifica archivos de codigo directamente
- SIEMPRE delega la implementacion a un especialista
- Mantiene un task board con el estado de cada subtarea
- Resuelve conflictos de dependencias entre teammates
- Es el unico que se comunica directamente con el usuario

## File Ownership Matrix

La File Ownership Matrix previene conflictos asignando archivos exclusivos a cada teammate.
Ningun teammate puede modificar archivos fuera de su dominio.

Ejemplo para un proyecto Flutter + Supabase:

```
FlutterSpecialist:
  - lib/**/*.dart
  - test/**/*.dart
  - pubspec.yaml

DBInfra:
  - supabase/migrations/**
  - supabase/functions/**
  - supabase/config.toml

DesignSpecialist:
  - doc/design/**
  - assets/images/**

QAReviewer:
  - test/**/*_test.dart  (solo lectura, sugiere cambios)
  - .github/workflows/ci.yml

Lead:
  - doc/plan/**
  - doc/status/**
```

Si un teammate necesita modificar un archivo fuera de su dominio, debe solicitar
permiso al Lead Agent, que reasigna temporalmente la propiedad.

## Comunicacion entre Teammates

### message (punto a punto)

Un teammate envia un mensaje directo a otro. Util para dependencias especificas.

```
FlutterSpecialist -> DBInfra: "Necesito el endpoint /api/users con paginacion"
```

### broadcast

Un teammate envia un mensaje a todos los demas. Util para cambios que afectan a todos.

```
Lead -> ALL: "Se cambio el esquema de autenticacion. Revisen sus implementaciones"
```

### debate

Dos o mas teammates discuten una decision tecnica. El Lead Agent modera y decide.

```
debate(FlutterSpecialist, ReactSpecialist):
  tema: "Formato del API response para paginacion"
  resultado: Lead decide el formato estandar
```

## Hooks

### TeammateIdle

Se ejecuta cuando un teammate termina su tarea actual y queda disponible.

Usos:
- Registrar el tiempo de completado en el log
- Verificar calidad del trabajo realizado
- Asignar la siguiente tarea pendiente

Script: `agent-teams/hooks/teammate-idle.mjs`

### TaskCompleted

Se ejecuta cuando una tarea completa se marca como finalizada.

Usos:
- Ejecutar linting y analisis estatico
- Correr tests automaticos
- Verificar cobertura de tests
- Notificar al Lead Agent

Script: `agent-teams/hooks/task-completed.mjs`

## Cuando usar Teams vs Agente unico

### Usar agente unico cuando:

- La tarea es simple y afecta pocos archivos
- Solo involucra un stack (solo Flutter, solo React)
- Es un bug fix localizado
- Es una refactorizacion dentro de un modulo

### Usar Agent Teams cuando:

- La tarea involucra multiples stacks (frontend + backend + infra)
- Hay trabajo paralelizable (UI + API + migraciones)
- El proyecto tiene mas de 3 modulos independientes
- Se necesita QA simultaneo mientras se desarrolla
- La tarea es una feature completa de punta a punta

## Migracion desde subagentes legacy

Ejecutar el comando `/optimize-agents` con la opcion de migracion a Agent Teams:

```
/optimize-agents --migrate-to-teams
```

Este comando:

1. Analiza los agentes existentes en `.claude/agents/`
2. Genera la configuracion de team-config.json equivalente
3. Crea los prompts de teammates basados en los agentes legacy
4. Configura la File Ownership Matrix segun los patrones del proyecto
5. Preserva los agentes legacy como respaldo

## Estructura de archivos

```
agent-teams/
  README.md                              <- Este archivo
  templates/
    team-config.template.json            <- Template de configuracion del equipo
  prompts/
    lead-agent.md                        <- Prompt del coordinador
    flutter-specialist.md                <- Prompt del especialista Flutter
    react-specialist.md                  <- Prompt del especialista React
    design-specialist.md                 <- Prompt del especialista en diseyo
    db-infra.md                          <- Prompt del especialista DB/Infra
    qa-reviewer.md                       <- Prompt del revisor QA
  hooks/
    teammate-idle.mjs                    <- Hook: teammate queda libre
    task-completed.mjs                   <- Hook: tarea completada
```

## Referencias

- Documentacion oficial: Claude Code Agent Teams (experimental)
- Variable de entorno: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- Comando de migracion: `/optimize-agents`
- Configuracion de Stitch MCP: ver `design/stitch/`
