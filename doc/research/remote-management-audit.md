# Auditoría: Sala de Máquinas + Remote Management

> **Fecha**: 2026-03-18
> **Engine**: v5.18.0
> **Objetivo**: Mapear el estado real de la infraestructura antes de diseñar el PRD de Remote Management

---

## 0.1 Servidor MCP del Engine

### ¿Qué hace `get_sala_de_maquinas`?

**Archivo**: `server/tools/state.py` (línea ~969)

Lee **exclusivamente del state registry local** (`/data/state/`). No hace ningún HTTP call externo.

**Fuentes de datos** (todas en `/data/state/projects/{project}/`):

| Archivo | Tipo | Contenido |
|---------|------|-----------|
| `registry.json` | Catálogo | Lista de proyectos registrados con stack, infra, repo_url |
| `sessions.jsonl` | Append-only | Sesiones de desarrollo (tokens, duración) |
| `healing.jsonl` | Append-only | Eventos de self-healing |
| `acceptance_validations.jsonl` | Append-only | Verdicts AG-09b |
| `merge_events.jsonl` | Append-only | Pipeline de merge |
| `feedback.jsonl` | Append-only | Feedback del developer |
| `e2e_results.jsonl` | Append-only | Resultados E2E |
| `meta.json` | Overwrite | Metadata (last_activity, active_feature) |

**Caché**: `dashboard_cache.json` con TTL de 5 minutos. Se invalida automáticamente en cualquier operación de escritura.

**Output**: Agregados globales — sesiones totales, tokens consumidos, healing health, acceptance rate, merge rate, E2E stats, proyecto más activo.

### ¿Qué retorna `get_sala_de_maquinas`?

```json
{
  "period_days": 7,
  "generated_at": "2026-03-18T...",
  "projects": {
    "mcprofit": {
      "sessions": 15,
      "tokens_est": 125000,
      "healing_health": "healthy",
      "acceptance_rate": "85%",
      "merge_rate": "100%",
      "feedback_open": 2,
      "e2e_pass_rate": "92%"
    }
  },
  "aggregates": {
    "total_sessions": 45,
    "total_tokens": 450000,
    "most_active_project": "mcprofit",
    "global_health": "healthy",
    "overall_acceptance_rate": "90%"
  }
}
```

Todos los campos vienen del state registry. El timestamp es el momento de generación. **No hay freshness tracking de los datos individuales** — un proyecto puede tener datos de hace semanas y no se indica.

### ¿Qué datos retorna `get_all_projects_overview`?

**Archivo**: `server/tools/live_state.py` (línea 149)

Lee de `registry.json` + `project_state.json` (heartbeat snapshots) por proyecto. Incluye health emoji basado en freshness del heartbeat + healing_health.

### ¿Qué datos retorna `get_project_live_state`?

**Archivo**: `server/tools/live_state.py` (línea 76)

Lee de `project_state.json` (escrito por heartbeat o GitHub sync). Aplica **session decay**: si `received_at` > 30 minutos, marca `session_active=false`. Incluye time-ago humanizado en español.

---

## 0.2 Endpoints HTTP existentes

### Dashboard API

**Archivo**: `server/dashboard_api.py` (~843 líneas)

El servidor FastMCP expone REST API y sirve archivos estáticos del dashboard React. Todo en un solo proceso.

| Endpoint | Método | Auth | Función |
|----------|--------|------|---------|
| `/health` | GET | No | Container healthcheck |
| `/api/sala` | GET | Bearer | Global dashboard (llama `get_sala_de_maquinas`) |
| `/api/projects` | GET | Bearer | Lista proyectos registrados |
| `/api/project/{name}` | GET | Bearer | Detalle proyecto + actividad 7d |
| `/api/project/{name}/timeline` | GET | Bearer | Timeline cronológico de eventos |
| `/api/project/{name}/quality` | GET | Bearer | Quality baseline del proyecto |
| `/api/healing` | GET | Bearer | Self-healing summary global |
| `/api/e2e` | GET | Bearer | E2E testing summary |
| `/api/upgrades` | GET | Bearer | Version matrix |
| `/api/spec-driven` | GET | Bearer | Board status (Trello/Plane) |
| `/api/benchmark/public` | GET | No | Métricas anonimizadas |
| `/api/heartbeat` | POST | Bearer | Recibe heartbeat de hooks locales |
| `/api/sync/github` | POST | Bearer | Trigger GitHub sync |

### Autenticación

- Variable: `SPECBOX_SYNC_TOKEN`
- Método: `Authorization: Bearer <token>` o query param `?token=<token>`
- Si no hay env var configurada, permite todo (modo desarrollo)

---

## 0.3 Stack del Dashboard (Sala de Máquinas)

### Frontend

| Aspecto | Valor |
|---------|-------|
| Framework | React 19.0.0 |
| Bundler | Vite 6.0.0 |
| CSS | Tailwind 3.4.17 |
| Routing | react-router-dom 7.1.0 |
| Charts | recharts 2.15.0 |
| Icons | lucide-react |
| TypeScript | 5.7.0 |
| Módulos | ES Modules |

### Páginas existentes

1. **Overview** — KPIs globales, tabla de proyectos, health
2. **ProjectDetail** — Sesiones, healing, acceptance, merge, feedback, E2E por proyecto
3. **Timeline** — Eventos cronológicos de un proyecto
4. **Healing** — Agregados de self-healing
5. **E2ETesting** — Resultados E2E globales
6. **Upgrades** — Version matrix
7. **SpecDriven** — Board status (Trello/Plane US/UC/AC)

### Auto-refresh

Hook `useAutoRefresh.ts` — polling cada 30 segundos al API.

### Backend

**No tiene backend propio**. El frontend se sirve como SPA estática desde el mismo proceso Python (FastMCP + Starlette). Las rutas `/api/*` las maneja `dashboard_api.py`, y todo lo demás hace fallback a `index.html`.

### Despliegue

**Docker multi-stage**:
1. Stage 1 (Node 20): `npm ci && npm run build` → genera `dist/`
2. Stage 2 (Python 3.12): copia `dist/`, instala deps Python, ejecuta `python -m server`

**docker-compose.yml**:
```yaml
services:
  specbox-engine:
    ports: ["8000:8000"]
    environment:
      MCP_TRANSPORT: http          # streamable-http
      SPECBOX_SYNC_TOKEN: ${SPECBOX_SYNC_TOKEN:-}
      GITHUB_TOKEN: ${GITHUB_TOKEN:-}
    volumes:
      - engine-state:/data/state   # Persistencia del state registry
```

### Transport MCP

**Archivo**: `server/server.py` (línea ~153)

```python
transport = os.getenv("MCP_TRANSPORT", "stdio")
if transport in ("http", "streamable-http"):
    mcp.run(transport="streamable-http", host=host, port=port)
elif transport == "sse":
    mcp.run(transport="sse", host=host, port=port)
else:
    mcp.run(transport="stdio")  # Default: Claude Code local
```

- **Local (Claude Code)**: stdio (default)
- **VPS (Docker)**: streamable-http en puerto 8000
- SSE disponible como alternativa

---

## 0.4 specbox-state.json

### ¿Dónde se genera?

**Archivo**: `.claude/hooks/heartbeat-sender.sh` (144 líneas)

Se ejecuta como parte de los hooks `on-session-end` e `implement-checkpoint`.

### ¿Cómo funciona?

1. Recolecta estado del filesystem local del proyecto:
   - Git: branch actual, último commit
   - Checkpoint: último `checkpoint.json` en `.quality/evidence/`
   - Coverage: primer baseline en `.quality/baselines/*.json`
   - Healing: cuenta líneas en `healing.jsonl`
   - Feedback: cuenta archivos `FB-*.json` abiertos

2. Envía POST a `/api/heartbeat` en el VPS (fire-and-forget, timeout 5s)

3. Si el POST tiene éxito → escribe `specbox-state.json` en la raíz del repo
4. Si falla → encola en `.quality/pending_heartbeats.jsonl` para retry

### Schema de specbox-state.json

```json
{
  "project": "mcprofit",
  "timestamp": "2026-03-18T14:23:45Z",
  "session_active": true,
  "current_phase": "implement",
  "current_feature": "invoice_detail",
  "current_branch": "feature/invoice-detail",
  "coverage_pct": 85.2,
  "open_feedback": 2,
  "blocking_feedback": 1,
  "healing_health": "healthy",
  "self_healing_events": 0,
  "last_operation": "implement",
  "last_commit": "feat: invoice detail screen",
  "last_commit_at": "2026-03-18T14:20:00Z",
  "source": "local"
}
```

### ¿Se commitea?

El archivo se escribe en la raíz del repo. **No se encontró referencia en `.gitignore` general del engine** — esto es intencional para que GitHub Sync pueda leerlo vía API.

---

## 0.5 State Registry

### ¿Dónde vive?

Directorio `/data/state/` (Docker volume `engine-state`). En local, configurable.

### Estructura

```
/data/state/
├── registry.json                    ← Catálogo de proyectos
├── dashboard_cache.json             ← Cache 5-min de get_sala_de_maquinas
└── projects/
    └── {slug}/
        ├── project_state.json       ← Snapshot consolidado (overwrite)
        ├── meta.json                ← Metadata (overwrite)
        ├── sessions.jsonl           ← Sesiones (append-only)
        ├── checkpoints.jsonl        ← Checkpoints (append-only)
        ├── healing.jsonl            ← Healing events (append-only)
        ├── acceptance_tests.jsonl   ← AG-09a tests (append-only)
        ├── acceptance_validations.jsonl  ← AG-09b verdicts (append-only)
        ├── merge_events.jsonl       ← Merge pipeline (append-only)
        ├── feedback.jsonl           ← Developer feedback (append-only)
        └── e2e_results.jsonl        ← E2E results (append-only)
```

### ¿Cómo se actualiza?

**Dos vías**:
1. **MCP tools** — `report_session`, `report_checkpoint`, `report_healing`, etc. (llamados por hooks locales que hacen POST al API del VPS)
2. **HTTP POST** — `/api/heartbeat` (escribe `project_state.json` + `meta.json`) y `/api/sync/github` (lee de GitHub)

**Los hooks del engine local** → POST fire-and-forget al VPS → handler en `dashboard_api.py` → llama al MCP tool correspondiente → escribe en `/data/state/`.

---

## 0.6 Infraestructura VPS existente

### Confirmado en el código

| Servicio | Evidencia en el repo |
|----------|---------------------|
| Docker multi-stage | `Dockerfile` + `docker-compose.yml` |
| Streamable HTTP transport | `MCP_TRANSPORT=http` en Dockerfile |
| State volume | `engine-state:/data/state` en docker-compose |
| Bearer auth | `SPECBOX_SYNC_TOKEN` en dashboard_api.py |
| GitHub Sync | `github_sync.py` + endpoint `/api/sync/github` |
| Heartbeat ingest | `/api/heartbeat` endpoint |

### PostgreSQL

**No hay ninguna conexión a PostgreSQL en el código de SpecBox Engine**. El state registry es 100% filesystem-based (JSON + JSONL). PostgreSQL lo usa solo Plane (self-hosted).

### ¿Qué usa Sala de Máquinas para persistencia?

**Archivos JSON/JSONL en un Docker volume**. Sin base de datos.

---

## Diagrama del estado actual

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MacBook Local                                 │
│                                                                      │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────────┐  │
│  │ Claude Code   │───►│ MCP Server    │───►│ /data/state (local)  │  │
│  │ (stdio)       │    │ (stdio mode)  │    │ registry.json        │  │
│  └──────┬───────┘    └───────────────┘    │ projects/*/           │  │
│         │                                  └──────────────────────┘  │
│         │ hooks                                                       │
│         ▼                                                             │
│  ┌──────────────────┐                                                │
│  │ heartbeat-sender  │─── POST /api/heartbeat (fire-and-forget) ─┐   │
│  │ on-session-end    │                                            │   │
│  │ implement-*       │─── También escribe specbox-state.json     │   │
│  └──────────────────┘    en raíz del repo (para GitHub Sync)     │   │
└───────────────────────────────────────────────────────────────────┘   │
                                                                        │
┌───────────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────────┐
│                   VPS (38.242.206.41) — EasyPanel                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  SpecBox Engine Container (Python 3.12 + React 19 SPA)       │   │
│  │  Port 8000 — streamable-http transport                        │   │
│  │                                                               │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │   │
│  │  │ MCP Server   │  │ Dashboard API │  │ Static SPA Files   │  │   │
│  │  │ (94+ tools)  │  │ /api/*       │  │ React 19 + Vite 6  │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └────────────────────┘  │   │
│  │         │                 │                                    │   │
│  │         └────────┬────────┘                                   │   │
│  │                  ▼                                             │   │
│  │         ┌────────────────┐                                    │   │
│  │         │ /data/state/    │ (Docker volume engine-state)      │   │
│  │         │ registry.json   │                                   │   │
│  │         │ projects/*/     │                                   │   │
│  │         │  ├─ project_state.json  (heartbeat snapshot)       │   │
│  │         │  ├─ sessions.jsonl      (append-only telemetry)    │   │
│  │         │  ├─ healing.jsonl                                  │   │
│  │         │  ├─ feedback.jsonl                                 │   │
│  │         │  └─ ...                                            │   │
│  │         └────────────────┘                                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────────────────────────────────┐    │
│  │ Traefik       │  │ PostgreSQL 17 (solo Plane)               │    │
│  │ SSL + routing │  │ plane.jpsdeveloper.com                    │    │
│  └──────────────┘  └──────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────┐                                                   │
│  │ n8n           │──── Cron cada 15 min: POST /api/sync/github     │
│  └──────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   GitHub (respaldo pasivo)                            │
│                                                                      │
│  repos/*/specbox-state.json ◄── Escrito por heartbeat-sender.sh    │
│       │                          cuando el POST /api/heartbeat OK    │
│       │                                                              │
│       └──── Leído por /api/sync/github cuando heartbeat > 30 min   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                   Consultas remotas (objetivo)                       │
│                                                                      │
│  iPhone (Claude.ai iOS) ──► MCP Server VPS (streamable-http)       │
│                              get_project_live_state(slug)            │
│                              get_all_projects_overview()             │
│                              get_active_sessions()                   │
│                              refresh_project_state(slug)             │
│                                                                      │
│  Browser ──► sala-de-maquinas.jpsdeveloper.com ──► React SPA        │
│              /api/sala, /api/project/{name}, etc.                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Lo que YA EXISTE vs lo que hay que construir

### YA EXISTE (reutilizable)

| Componente | Estado | Notas |
|------------|--------|-------|
| MCP Server con 94+ tools | Completo | Incluye todos los tools de consulta |
| Streamable HTTP transport | Completo | Ya funciona en Docker |
| Dashboard REST API (13 endpoints) | Completo | Auth con Bearer token |
| React 19 SPA (7 páginas) | Completo | Auto-refresh 30s |
| Heartbeat sender hook | Completo | Fire-and-forget, pending queue |
| specbox-state.json (repo-level) | Completo | Escrito por heartbeat-sender.sh |
| GitHub Sync | Completo | Staleness rule 30 min |
| Live State MCP tools | Completo | 4 tools conversacionales en español |
| Docker deployment | Completo | Multi-stage, volume persistence |
| Bearer token auth | Completo | `SPECBOX_SYNC_TOKEN` |
| State Registry (JSON/JSONL) | Completo | /data/state/ con estructura por proyecto |
| Session decay (30 min) | Completo | Lazy decay en live_state.py |
| EasyPanel + Traefik | Existente | SSL automático |
| n8n (para cron) | Existente | Ya configurado en VPS |
| PostgreSQL 17 | Existente | Solo usado por Plane, **NO por SpecBox** |

### HAY QUE CONSTRUIR/CONFIGURAR

| Componente | Esfuerzo | Descripción |
|------------|----------|-------------|
| Conectar Claude.ai iOS al MCP remoto | Configuración | Apuntar Claude.ai a `https://mcp-specbox-engine.jpsdeveloper.com/mcp` con el auth token |
| OpenClaw Gateway Skill | Nuevo | Skill para WhatsApp/Discord → Claude Code subprocess |
| Más tools conversacionales (opcionales) | Pequeño | `get_board_status_summary`, `get_sprint_status_summary` para queries desde móvil |
| Migración a PostgreSQL (opcional) | Medio | Reemplazar JSON/JSONL por tablas. Solo necesario si el volumen de datos crece |
| Autenticación MCP remota (SSE/HTTP) | Revisar | Verificar que Claude.ai puede enviar Bearer token en la conexión MCP |

---

## Recomendación Arquitectónica

### Hallazgo principal

**El 90% de la infraestructura necesaria ya está construida.** El SpecBox Engine v5.2.0 ya tiene:

1. Un MCP server que funciona en modo `streamable-http` en el VPS
2. Tools conversacionales diseñados para iPhone (`get_project_live_state`, `get_all_projects_overview`, etc.)
3. Un pipeline de heartbeat completo (hook → HTTP POST → state registry → query tools)
4. GitHub Sync como fallback cuando el Mac está apagado
5. Un dashboard React funcional con API REST

### Lo que realmente falta

El problema no es arquitectónico — es de **configuración y polish**:

1. **Configuración de Claude.ai iOS**: Apuntar al MCP server remoto del VPS. Verificar que Claude.ai soporta `Authorization: Bearer` en conexiones MCP (si no, implementar alternativa como token en path o query param)

2. **OpenClaw Gateway**: Este es el único componente genuinamente nuevo — un skill/bot que permita interactuar con SpecBox desde WhatsApp/Discord.

3. **Polish de tools conversacionales**: Los tools actuales devuelven JSON crudo. Para una experiencia fluida desde iPhone, podrían devolver texto formateado (Markdown) listo para presentar. Pero esto es mejora, no requisito.

4. **Observabilidad**: No hay forma de saber si los heartbeats están llegando correctamente al VPS. Un simple contador o log sería útil.

### Sobre PostgreSQL

**No recomiendo migrar a PostgreSQL en el MVP.** Razones:
- El state registry actual (JSON/JSONL) funciona correctamente para 21 proyectos
- Las queries son sobre archivos pequeños (< 1MB) — la latencia ya es aceptable
- PostgreSQL añadiría complejidad operacional sin beneficio claro hasta tener 100+ proyectos
- El Docker volume ya persiste los datos entre reinicios

**Cuándo migrar**: Si las queries de `get_sala_de_maquinas` tardan > 2s, o si se necesitan queries SQL complejas (filtros, agregaciones, búsquedas de texto) que el filesystem no soporta bien.

### Sobre zero-cost

El objetivo de zero-cost incremental se cumple:
- Claude Max (ya pagado) incluye remote MCP servers
- El VPS ya está pagado y tiene capacidad libre
- No se necesitan API keys ni servicios adicionales para el MVP de lectura

### Resumen

| Aspecto | Estado |
|---------|--------|
| Infraestructura MCP remoto | ✅ Ya funciona |
| Heartbeat protocol | ✅ Ya funciona |
| GitHub Sync | ✅ Ya funciona |
| State Registry | ✅ Ya funciona |
| Dashboard web | ✅ Ya funciona |
| Conexión Claude.ai iOS | ⚙️ Configuración pendiente |
| OpenClaw Gateway | 🆕 Por construir |
| PostgreSQL migration | ⏸️ No necesario para MVP |

**El PRD debería centrarse en**: (1) validar/documentar la conexión Claude.ai ↔ MCP remoto, (2) diseñar el OpenClaw Gateway, (3) polish de la experiencia móvil, y (4) roadmap para evoluciones futuras (escritura remota, PostgreSQL).
