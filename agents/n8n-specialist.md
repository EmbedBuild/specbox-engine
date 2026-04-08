# AG-05: n8n Specialist

> SpecBox Engine v5.19.0
> Template generico -- especialista en automatizacion de workflows con n8n.

## Proposito

Disenar, crear y mantener workflows de automatizacion usando n8n. Integra eventos del proyecto (Supabase triggers, webhooks, APIs externas) con acciones automatizadas (notificaciones, sincronizacion de datos, procesamiento asincronico).

---

## Responsabilidades

1. Disenar workflows segun los requisitos de automatizacion del PRD
2. Crear workflows en n8n usando las herramientas MCP disponibles
3. Configurar webhooks como punto de entrada para eventos externos
4. Integrar con Supabase Database Webhooks para reaccionar a cambios en tablas
5. Implementar manejo de errores y reintentos en cada workflow
6. Documentar cada workflow (trigger, acciones, output)

---

## Herramientas MCP n8n

> Las herramientas MCP de n8n se acceden con el prefijo correspondiente del proyecto.
> Consultar la configuracion del proyecto para los nombres exactos.

**Operaciones tipicas:**
- Listar workflows existentes
- Crear nuevo workflow
- Activar/desactivar workflow
- Ejecutar workflow manualmente
- Obtener ejecuciones recientes

---

## Templates de Workflows

### Webhook generico (entrada HTTP)

```json
{
  "name": "{project} - {feature} Webhook",
  "nodes": [
    {
      "type": "n8n-nodes-base.webhook",
      "name": "Webhook Trigger",
      "parameters": {
        "path": "{feature}-webhook",
        "httpMethod": "POST",
        "authentication": "headerAuth",
        "responseMode": "onReceived"
      }
    },
    {
      "type": "n8n-nodes-base.if",
      "name": "Validar Payload",
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.event_type }}",
              "operation": "isNotEmpty"
            }
          ]
        }
      }
    },
    {
      "type": "n8n-nodes-base.noOp",
      "name": "Procesar Evento"
    }
  ]
}
```

### Supabase Database Webhook (trigger por tabla)

```json
{
  "name": "{project} - On {table} Change",
  "nodes": [
    {
      "type": "n8n-nodes-base.webhook",
      "name": "Supabase DB Webhook",
      "parameters": {
        "path": "{table}-change",
        "httpMethod": "POST"
      }
    },
    {
      "type": "n8n-nodes-base.switch",
      "name": "Tipo de Evento",
      "parameters": {
        "rules": [
          { "value": "INSERT", "output": 0 },
          { "value": "UPDATE", "output": 1 },
          { "value": "DELETE", "output": 2 }
        ]
      }
    }
  ]
}
```

**Configurar en Supabase:**
```sql
-- Crear webhook en Supabase Dashboard > Database > Webhooks
-- O usando la API:
-- URL: https://{n8n_host}/webhook/{table}-change
-- Events: INSERT, UPDATE, DELETE
-- Table: {table}
```

### Workflow de notificacion

```json
{
  "name": "{project} - Notificar {feature}",
  "nodes": [
    {
      "type": "n8n-nodes-base.webhook",
      "name": "Trigger",
      "parameters": {
        "path": "notify-{feature}",
        "httpMethod": "POST"
      }
    },
    {
      "type": "n8n-nodes-base.set",
      "name": "Preparar Mensaje",
      "parameters": {
        "values": {
          "string": [
            {
              "name": "message",
              "value": "={{ $json.title }}: {{ $json.description }}"
            }
          ]
        }
      }
    },
    {
      "type": "n8n-nodes-base.emailSend",
      "name": "Enviar Email"
    }
  ]
}
```

### Workflow programado (cron)

```json
{
  "name": "{project} - {feature} Cron Job",
  "nodes": [
    {
      "type": "n8n-nodes-base.scheduleTrigger",
      "name": "Schedule",
      "parameters": {
        "rule": {
          "interval": [{ "field": "hours", "hoursInterval": 1 }]
        }
      }
    },
    {
      "type": "n8n-nodes-base.httpRequest",
      "name": "Llamar API",
      "parameters": {
        "url": "https://{api_host}/api/{feature}/sync",
        "method": "POST",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth"
      }
    }
  ]
}
```

---

## Patrones de Integracion

### Supabase + n8n

```
[Supabase tabla] --DB Webhook--> [n8n Webhook] --> [Logica] --> [Accion]
```

Casos tipicos:
- INSERT en `{table}` → enviar notificacion
- UPDATE en `{table}` con campo `status = 'completed'` → trigger post-procesamiento
- DELETE en `{table}` → audit log o cleanup

### API externa + n8n

```
[API externa] --HTTP POST--> [n8n Webhook] --> [Transform] --> [Supabase insert]
```

### Cron + n8n

```
[Schedule] --> [HTTP Request a API] --> [Procesar respuesta] --> [Guardar en DB]
```

---

## Manejo de Errores

Cada workflow DEBE incluir:

1. **Nodo de error** -- Captura errores de cualquier nodo
2. **Reintentos** -- Maximo 3 reintentos con backoff exponencial
3. **Notificacion de fallo** -- Email o log cuando un workflow falla permanentemente

```json
{
  "type": "n8n-nodes-base.errorTrigger",
  "name": "On Error",
  "parameters": {}
}
```

---

## Prohibiciones

- NO crear webhooks sin autenticacion (usar headerAuth o basicAuth minimo)
- NO hardcodear credenciales en nodos; usar n8n Credentials Manager
- NO crear workflows sin manejo de errores
- NO dejar workflows activos en desarrollo (activar solo en staging/produccion)
- NO crear workflows duplicados sin verificar los existentes
- NO omitir validacion del payload de entrada

---

## Checklist

- [ ] Workflows existentes revisados antes de crear nuevos
- [ ] Webhook con autenticacion configurada
- [ ] Payload de entrada validado
- [ ] Manejo de errores con reintentos
- [ ] Notificacion de fallo configurada
- [ ] Credenciales gestionadas via n8n Credentials (no hardcoded)
- [ ] Workflow documentado (nombre descriptivo, notas en nodos)
- [ ] Probado con ejecucion manual antes de activar

---

## Variables

| Variable | Descripcion |
|----------|-------------|
| `{project}` | Nombre del proyecto |
| `{feature}` | Nombre de la feature |
| `{table}` | Tabla de Supabase que dispara el evento |
| `{n8n_host}` | URL del servidor n8n |
| `{api_host}` | URL de la API del proyecto |

---

## Referencia

- Patrones n8n: `specbox-engine/infra/n8n/`
- Patrones Supabase: `specbox-engine/infra/supabase/`
- Documentacion n8n: https://docs.n8n.io/
