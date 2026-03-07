# n8n - Patrones de Infraestructura

> SDD-JPS Engine v3.9.0 | Referencia de patrones para automatizaciones con n8n

---

## 1. Herramientas MCP disponibles

n8n se integra como servicio externo. No dispone de herramientas MCP nativas en este engine, pero se controla mediante:

| Metodo | Uso |
|--------|-----|
| API REST de n8n | Activar/desactivar workflows, consultar ejecuciones |
| Webhooks de n8n | Recibir eventos desde Supabase, Stripe, etc. |
| Supabase Edge Functions | Disparar workflows desde logica de backend |

### Endpoints utiles de la API

```
GET  /api/v1/workflows           -> Listar workflows
POST /api/v1/workflows/{id}/activate   -> Activar workflow
POST /api/v1/workflows/{id}/deactivate -> Desactivar workflow
GET  /api/v1/executions          -> Listar ejecuciones recientes
```

---

## 2. Patrones de diseno de workflows

### Nomenclatura

```
[{project}] {dominio} - {accion} - {trigger}
```

Ejemplos:
```
[{project}] Users - Send Welcome Email - On Signup
[{project}] Orders - Sync to Sheets - On Status Change
[{project}] Reports - Generate Weekly - Cron Monday
```

### Estructura recomendada de un workflow

```
Trigger (Webhook / Cron / Supabase)
    |
Validacion (IF / Switch)
    |
Procesamiento (Code / HTTP Request / API calls)
    |
Accion final (Email / DB Update / Notificacion)
    |
Logging (opcional)
```

### Reglas de diseno

- Un workflow, una responsabilidad. No mezclar logica de distintos dominios.
- Usar nodos `IF` o `Switch` al inicio para validar datos del trigger.
- Nombrar cada nodo de forma descriptiva (no dejar "Code", "HTTP Request" genericos).
- Documentar el proposito del workflow en las notas del trigger.

---

## 3. Integracion con Supabase (triggers)

### Patron: Database Webhook -> n8n

```
Supabase Database Webhook (INSERT en {table})
    -> HTTP POST a n8n webhook URL
        -> n8n procesa evento
```

### Configurar webhook en Supabase

```sql
-- Crear funcion que notifica a n8n
CREATE OR REPLACE FUNCTION notify_n8n_{table}()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM net.http_post(
        url := '{n8n_webhook_url}',
        headers := '{"Content-Type": "application/json"}'::jsonb,
        body := jsonb_build_object(
            'event', TG_OP,
            'table', TG_TABLE_NAME,
            'record', row_to_json(NEW)
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER {table}_n8n_trigger
    AFTER INSERT OR UPDATE ON {table}
    FOR EACH ROW
    EXECUTE FUNCTION notify_n8n_{table}();
```

### Requisito: Habilitar extension pg_net

```sql
CREATE EXTENSION IF NOT EXISTS pg_net;
```

---

## 4. Patrones de webhook en n8n

### Recibir webhook

Nodo: **Webhook**
- Metodo: POST
- Path: `/{project}/{dominio}/{accion}`
- Autenticacion: Header Auth con token compartido

### Validar origen del webhook

```javascript
// En nodo Code tras el webhook
const expectedToken = $env.WEBHOOK_SECRET;
const receivedToken = $input.first().headers['x-webhook-token'];

if (receivedToken !== expectedToken) {
    throw new Error('Token de webhook invalido');
}
```

### Responder al webhook

- Configurar el nodo Webhook con "Respond: Last Node" para enviar respuesta personalizada.
- Para procesamiento largo, responder inmediatamente con 200 y procesar en nodos posteriores.

---

## 5. Manejo de errores

### Patron: Error Workflow

Configurar un workflow dedicado para errores:

```
Error Trigger
    |
Formatear mensaje de error
    |
Notificar (Slack / Email / Discord)
    |
Registrar en tabla de logs (Supabase)
```

### Configuracion por workflow

En la configuracion del workflow:
- **Error Workflow:** Seleccionar el workflow de errores dedicado.
- **Timeout:** Establecer timeout maximo por ejecucion.
- **Retry on Fail:** Activar reintentos en nodos criticos (HTTP Request, API).

### Reintentos en nodos individuales

```
Configuracion del nodo:
    - On Error: Continue (con output de error)
    - Retry On Fail: true
    - Max Tries: 3
    - Wait Between Tries: 1000ms
```

### Buenas practicas de errores

- Siempre asignar un Error Workflow a cada workflow de produccion.
- Usar nodos `IF` para verificar que las respuestas HTTP son exitosas (status 2xx).
- Registrar errores con contexto suficiente (workflow, nodo, datos de entrada).

---

## 6. Patron N8nDatasource (Flutter)

### Regla fundamental

> Los workflows de n8n se invocan a traves de un datasource dedicado, nunca directamente desde repositorios o casos de uso.

### Estructura

```
n8n Webhook URL
    |
N8nDatasource (ejecuta HTTP calls a webhooks de n8n)
    |
Repository (trabaja con datos del dominio)
    |
UseCase / Service
```

### Ejemplo en Dart/Flutter

```dart
abstract class AutomationDatasource {
    Future<Map<String, dynamic>> triggerWorkflow(
        String workflowPath,
        Map<String, dynamic> payload,
    );
}

class N8nDatasource implements AutomationDatasource {
    final http.Client _client;
    final String _baseUrl;
    final String _webhookToken;

    N8nDatasource({
        required http.Client client,
        required String baseUrl,
        required String webhookToken,
    })  : _client = client,
          _baseUrl = baseUrl,
          _webhookToken = webhookToken;

    @override
    Future<Map<String, dynamic>> triggerWorkflow(
        String workflowPath,
        Map<String, dynamic> payload,
    ) async {
        final response = await _client.post(
            Uri.parse('$_baseUrl/webhook/$workflowPath'),
            headers: {
                'Content-Type': 'application/json',
                'x-webhook-token': _webhookToken,
            },
            body: jsonEncode(payload),
        );

        if (response.statusCode != 200) {
            throw AutomationException('Error al ejecutar workflow: ${response.statusCode}');
        }

        return jsonDecode(response.body) as Map<String, dynamic>;
    }
}
```

### Beneficios

- Centraliza la configuracion de conexion a n8n (URL, token).
- Permite reemplazar n8n por otro motor de automatizacion sin afectar la logica de negocio.
- Facilita testing mediante mocks del datasource.
