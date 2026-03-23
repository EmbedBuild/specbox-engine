# Setup: Claude.ai iOS + SpecBox MCP Remoto

## Requisitos

- iPhone con Claude.ai app (Claude Max subscription)
- SpecBox Engine desplegado en VPS con `MCP_TRANSPORT=http`
- `SPECBOX_SYNC_TOKEN` configurado en el VPS

## Configuracion

### 1. Verificar que el servidor responde

```bash
curl https://mcp-specbox-engine.jpsdeveloper.com/health
# Esperado: {"status": "ok"}
```

### 2. Verificar autenticacion

```bash
curl -H "Authorization: Bearer TU_TOKEN" \
  https://mcp-specbox-engine.jpsdeveloper.com/api/sala
# Esperado: JSON con datos de proyectos
```

### 3. Configurar en Claude.ai iOS

1. Abrir Claude.ai app en iPhone
2. Ir a Settings > Integrations > MCP Servers
3. Añadir nuevo servidor:
   - **Name**: SpecBox Engine
   - **URL**: `https://mcp-specbox-engine.jpsdeveloper.com/mcp`
   - **Transport**: Streamable HTTP
   - **Authentication**: Bearer Token → pegar `SPECBOX_SYNC_TOKEN`

### 4. Probar desde Claude.ai

Escribe cualquiera de estos mensajes:

- "¿Como van mis proyectos?" → invoca `get_all_projects_overview`
- "¿Como va mcprofit?" → invoca `get_project_live_state`
- "¿Hay sesiones activas?" → invoca `get_active_sessions`
- "Actualiza el estado de mcprofit" → invoca `refresh_project_state`
- "¿Como estan los heartbeats?" → invoca `get_heartbeat_stats`

## Latencia esperada

- Queries de estado: < 500ms (JSON files < 100KB)
- Refresh desde GitHub: 1-3s (GitHub API call)
- El dashboard en browser: misma latencia via `/api/*`

## Troubleshooting

### El servidor no responde
```bash
# Verificar que el container esta corriendo
docker ps | grep specbox
# Verificar logs
docker logs specbox-engine --tail 50
```

### 401 Unauthorized
- Verificar que `SPECBOX_SYNC_TOKEN` esta configurado en el VPS
- Verificar que el token en Claude.ai coincide exactamente
- Sin token configurado en el VPS, el servidor acepta todo (modo dev)

### Tools no aparecen en Claude.ai
- Verificar que el transport es `streamable-http` (no SSE ni stdio)
- Verificar que la URL termina en `/mcp`
- Reiniciar la app de Claude.ai

### Datos desactualizados
- Los heartbeats se envian al final de cada sesion y tras cada checkpoint
- Si el Mac esta apagado, GitHub Sync actualiza cada 15 min via n8n
- Usa "refresh [proyecto]" para forzar sync desde GitHub

## Seguridad

- Todo el trafico va por HTTPS (Traefik + Let's Encrypt)
- El Bearer token autentica todas las requests API y MCP
- Los endpoints publicos (`/health`, `/api/benchmark/public`) no exponen datos de proyectos
- No se almacenan credenciales en el iPhone — Claude.ai gestiona el token
