---
name: remote
description: >
  Remote project management via MCP tools. Use when the user says
  "estado de [proyecto]", "resumen de todos", "sesiones activas",
  "refresh [proyecto]", "heartbeats", or queries project status
  from mobile/messaging platforms. Formats responses as plain text
  (max 2000 chars) for WhatsApp/Discord compatibility.
context: direct
allowed-tools: Read, Bash(curl *)
---

# Skill: /remote — Remote Project Management

## Proposito

Wrapper conversacional para consultar y gestionar proyectos de SpecBox Engine desde plataformas remotas (Claude.ai iOS, WhatsApp via OpenClaw, Discord). Formatea respuestas en texto plano compatible con mensajeria.

## Comandos

| Comando | MCP Tool | Descripcion |
|---------|----------|-------------|
| "estado de [proyecto]" | `get_project_live_state` | Estado detallado de un proyecto |
| "resumen de todos" | `get_all_projects_overview` | Vista global de todos los proyectos |
| "sesiones activas" | `get_active_sessions` | Proyectos con sesion de desarrollo activa |
| "refresh [proyecto]" | `refresh_project_state` | Forzar sync desde GitHub |
| "heartbeats" | `get_heartbeat_stats` | Estadisticas de heartbeats (observabilidad) |
| "mover UC-XXX a [estado]" | `move_uc` | Mover un UC entre estados (Fase 2) |
| "marcar AC-XX como done" | `mark_ac` | Marcar acceptance criteria (Fase 2) |
| "reporte de [proyecto]" | `get_delivery_report` | Reporte de entrega (Fase 2) |

## Protocolo de Ejecucion

### Paso 1: Detectar intencion

Parsear el mensaje del usuario para identificar:
- **Operacion**: estado, resumen, sesiones, refresh, heartbeats, mover, marcar, reporte
- **Proyecto** (si aplica): slug del proyecto (ej: "mcprofit", "futplanner")

### Paso 2: Invocar MCP tool

Llamar al tool MCP correspondiente con los parametros identificados.

### Paso 3: Formatear respuesta

**Reglas de formateo para WhatsApp/Discord:**

1. Maximo 2000 caracteres por respuesta
2. No usar tablas Markdown (WhatsApp no las renderiza)
3. Usar emojis como indicadores visuales:
   - green_circle = saludable
   - yellow_circle = atencion
   - red_circle = critico
4. Usar listas con guiones para estructura
5. Timestamps siempre como "hace X minutos/horas" (nunca ISO)
6. Si la respuesta del tool incluye campo `summary` o `summary_table`, usarlo como base

**Ejemplo de formato — estado de proyecto:**

```
green_circle mcprofit — sesion activa

- Feature: invoice-detail
- Progreso: 12/18 UCs
- Veredicto: ACCEPTED
- Coverage: 85.2%
- Feedback: 2 abiertos (1 bloqueante)
- Actualizado: hace 5 minutos
```

**Ejemplo de formato — resumen global:**

```
21 proyectos registrados
3 con sesion activa | 5 con feedback abierto

green_circle mcprofit — invoice-detail (hace 5 min)
green_circle futplanner — onboarding (hace 12 min)
yellow_circle gastools — idle (hace 2 dias)
red_circle demo-project — sin heartbeat (hace 3 dias)
```

**Ejemplo de formato — sesiones activas:**

```
Hay 2 sesiones activas:

- mcprofit: implement, invoice-detail (hace 5 min)
- futplanner: plan, onboarding (hace 12 min)
```

## Configuracion OpenClaw

Para conectar WhatsApp/Discord a SpecBox via OpenClaw Gateway:

1. Instalar OpenClaw Gateway en el VPS
2. Configurar el MCP remoto en OpenClaw:
   ```
   MCP_URL=https://mcp-specbox-engine.jpsdeveloper.com/mcp
   MCP_AUTH_TOKEN=<SPECBOX_SYNC_TOKEN>
   ```
3. Configurar el canal de WhatsApp/Discord en OpenClaw
4. La skill `/remote` se activa automaticamente cuando el mensaje llega via OpenClaw

Ver guia completa en `doc/remote-management/setup-openclaw.md`.
