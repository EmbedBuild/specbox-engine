# Agent Teams

> JPS Dev Engine v3.3.0 — Orquestacion multi-agente nativa de Claude Code (experimental)

## Que es Agent Teams

Agent Teams permite ejecutar multiples agentes en paralelo dentro de una misma sesion de Claude Code. Cada agente (teammate) tiene contexto aislado, reglas propias y acceso restringido a archivos especificos del proyecto.

A diferencia del flujo con un solo agente que trabaja secuencialmente, Agent Teams divide tareas complejas entre especialistas que operan en paralelo, coordinados por un Lead Agent que planifica, delega y sintetiza resultados.

## Cuando usar Teams vs Agente unico

**Agente unico** es suficiente cuando la tarea es simple, afecta pocos archivos, involucra un solo stack, o es un bug fix localizado.

**Agent Teams** es preferible cuando la tarea involucra multiples stacks (frontend + backend + infra), hay trabajo paralelizable, el proyecto tiene mas de 3 modulos independientes, o se necesita QA simultaneo durante el desarrollo.

## Estructura

```
agent-teams/
  prompts/       (8 prompts de teammates)
  hooks/         (2 hooks de coordinacion)
  templates/     (1 template de configuracion)
```

## Roles disponibles

| Rol | Archivo | Funcion |
|-----|---------|---------|
| Lead Agent | `lead-agent.md` | Coordina sin implementar: planifica, delega, monitorea y sintetiza |
| FlutterSpecialist | `flutter-specialist.md` | Implementacion Flutter con BLoC, Clean Architecture |
| ReactSpecialist | `react-specialist.md` | Implementacion React con Next.js, Server Components |
| DesignSpecialist | `design-specialist.md` | Diseyo UI con Stitch MCP, assets y layouts |
| DBInfra | `db-infra.md` | Base de datos, migraciones, edge functions, infraestructura |
| QAReviewer | `qa-reviewer.md` | Testing, CI/CD, revision de calidad |
| QualityAuditor | `quality-auditor.md` | Verificacion de baselines, evidencia y gates de calidad |
| AppScriptSpecialist | `appscript-specialist.md` | Google Apps Script con clasp, V8, batch operations |

## Engine Awareness

Todos los prompts de teammates incluyen una seccion de integracion con el engine v3.2. Esto les da conocimiento de:

- **Skills disponibles**: `/prd`, `/plan`, `/implement`, `/quality-gate`, etc.
- **Hooks automaticos**: pre-commit-lint, session telemetry, checkpoints
- **Quality System**: baselines en `.quality/`, ratchet enforcement, evidencia auditable
- **File Ownership**: restricciones de archivos por rol para prevenir conflictos

El Lead Agent tiene la vista completa del sistema; los especialistas conocen las reglas que afectan su dominio.

## File Ownership Matrix

La File Ownership Matrix previene conflictos asignando archivos exclusivos a cada teammate. Ningun teammate puede modificar archivos fuera de su dominio sin autorizacion del Lead Agent.

Ejemplo para un proyecto Flutter + Supabase:

```
FlutterSpecialist:  lib/**/*.dart, test/**/*.dart, pubspec.yaml
DBInfra:            supabase/migrations/**, supabase/functions/**
DesignSpecialist:   doc/design/**, assets/images/**
QAReviewer:         test/**/*_test.dart (lectura), .github/workflows/
Lead:               doc/plan/**, doc/status/**
```

## Hooks de coordinacion

**task-completed.sh** — Se ejecuta cuando una tarea se marca como finalizada. Lanza linting, analisis estatico, tests automaticos y verifica cobertura.

**teammate-idle.sh** — Se ejecuta cuando un teammate termina y queda disponible. Registra tiempo de completado, verifica calidad del trabajo y reasigna la siguiente tarea pendiente.

## Comunicacion entre teammates

Tres mecanismos nativos:

- **message**: comunicacion punto a punto entre dos teammates (ej: FlutterSpecialist solicita un endpoint a DBInfra)
- **broadcast**: un teammate notifica a todos (ej: Lead anuncia cambio en esquema de autenticacion)
- **debate**: dos o mas teammates discuten una decision tecnica, moderados por el Lead Agent

## Setup rapido

1. Habilitar la feature experimental:
   ```json
   { "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" } }
   ```

2. Copiar el template de configuracion al proyecto:
   ```bash
   cp agent-teams/templates/team-config.template.json mi_proyecto/.claude/team-config.json
   ```

3. Copiar los prompts necesarios segun los stacks del proyecto:
   ```bash
   cp agent-teams/prompts/lead-agent.md mi_proyecto/.claude/team-prompts/lead.md
   cp agent-teams/prompts/flutter-specialist.md mi_proyecto/.claude/team-prompts/
   ```

## Migracion desde subagentes legacy

Los archivos en `.claude/agents/` siguen siendo utiles para tareas simples. Para migrar a Agent Teams:

```
/optimize-agents --migrate-to-teams
```

El comando analiza los agentes existentes, genera `team-config.json`, crea prompts de teammates equivalentes, configura la File Ownership Matrix y preserva los agentes legacy como respaldo.

## Referencia completa

Ver [agent-teams/README.md](../agent-teams/README.md) para documentacion detallada con ejemplos de comunicacion, patron Lead Agent y configuracion avanzada.
