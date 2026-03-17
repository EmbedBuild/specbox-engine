# Plan Tecnico: Remote State Management

**Feature:** Remote State Management para SpecBox Engine
**Fecha:** 2026-03-17
**Engine version base:** v5.1.0
**UCs cubiertos:** UC-001 a UC-010
**Estimacion:** 18-24 horas
**Restriccion clave:** No crear servicios nuevos — extender el servidor existente. Mantener JSONL/JSON como state store.

---

## Arquitectura

3 capas nuevas, 3 archivos nuevos, 4 archivos modificados:

| Capa | Archivo | Proposito |
|------|---------|-----------|
| Heartbeat Ingestion (UC-001) | `server/tools/state.py` (extender) | Nuevo tool `report_heartbeat` + persist `project_state.json` |
| Heartbeat Emission (UC-002) | `.claude/hooks/heartbeat-sender.sh` (nuevo) | Construye payload y envia heartbeat desde maquina local |
| GitHub Sync (UC-005) | `server/github_sync.py` (nuevo) | Lee specbox-state.json de repos via GitHub API |
| Live State Query (UC-007-010) | `server/tools/live_state.py` (nuevo) | 5 MCP tools conversacionales para iPhone |
| REST Endpoints (UC-001,005) | `server/dashboard_api.py` (extender) | POST /api/heartbeat, POST /api/sync/github |
| Local State File (UC-004) | `.claude/hooks/heartbeat-sender.sh` | Escribe specbox-state.json en raiz del repo |

Modificaciones: `server/server.py` (+4 lineas registro), `.claude/hooks/on-session-end.sh` (+3 lineas), `.claude/hooks/implement-checkpoint.sh` (+3 lineas), `docker-compose.yml` (+2 env vars)

## Estado como project_state.json

Cada proyecto tendra un archivo `/data/state/projects/{project}/project_state.json` (sobrescribe, no append):

```json
{
  "project": "mcprofit",
  "timestamp": "2026-03-17T14:28:00Z",
  "received_at": "2026-03-17T14:28:01Z",
  "source": "heartbeat",
  "session_active": true,
  "current_phase": "implement",
  "current_feature": "pl-monthly",
  "current_branch": "feat/pl-monthly",
  "plan_progress": {
    "total_ucs": 18,
    "completed_ucs": 12,
    "current_uc": "UC-013"
  },
  "last_verdict": "ACCEPTED",
  "coverage_pct": 87.2,
  "tests_passing": 142,
  "tests_failing": 0,
  "open_feedback": 0,
  "blocking_feedback": 0,
  "healing_health": "healthy",
  "self_healing_events": 0,
  "last_operation": "implement",
  "last_commit": "refactor P&L aggregation query",
  "last_commit_at": "2026-03-15T14:28:00Z"
}
```

### Session Decay (lazy)

Al leer `project_state.json`, si `received_at` tiene mas de 30 minutos y `session_active == true`, se retorna `session_active: false` sin modificar el archivo (evaluacion lazy, sin cron).

### Regla de merge heartbeat vs GitHub sync

- `report_heartbeat` SIEMPRE escribe (sobrescribe project_state.json)
- GitHub sync solo escribe si `received_at` tiene mas de 30 minutos de antiguedad
- Esto evita que el cron sobreescriba datos en tiempo real

---

## Fases de Implementacion

### Fase 1: Heartbeat Ingestion (UC-001, UC-003)
**Archivos:** `server/tools/state.py`, `server/dashboard_api.py`
**Agente:** AG-01 (Feature Generator)
**Budget:** ~2500 tokens

1. Añadir helper `_read_project_state(project_dir)` y `_write_project_state(project_dir, data)` en state.py
2. Añadir helper `_apply_session_decay(state)` que retorna state con `session_active=false` si `received_at > 30 min`
3. Añadir MCP tool `report_heartbeat(project, timestamp, session_active, current_phase, current_feature, current_branch, plan_total_ucs, plan_completed_ucs, plan_current_uc, last_verdict, coverage_pct, tests_passing, tests_failing, open_feedback, blocking_feedback, healing_health, self_healing_events, last_operation, last_commit, last_commit_at)` que:
   - Llama `_ensure_project_dir` + `_auto_register`
   - Construye dict del payload
   - Añade `received_at` con timestamp del servidor
   - Añade `source: "heartbeat"`
   - Escribe `project_state.json` (sobrescribe)
   - Actualiza meta.json con `last_activity`
   - Invalida cache
   - Retorna `{"status": "ok", "project": project}`
4. Añadir REST endpoint `POST /api/heartbeat` en dashboard_api.py:
   - Auth via `SPECBOX_SYNC_TOKEN` env var (Bearer)
   - Parsea JSON body
   - Valida campos requeridos (project, timestamp)
   - Escribe `project_state.json` directamente (misma logica que el tool)
   - Retorna `{"status": "ok"}`
5. Exportar helpers nuevos en los imports de dashboard_api.py

**AC cubiertos:** AC-01, AC-02, AC-03, AC-04, AC-10, AC-11

### Fase 2: Heartbeat Emission (UC-002)
**Archivos:** `.claude/hooks/heartbeat-sender.sh` (nuevo), `.claude/hooks/on-session-end.sh`, `.claude/hooks/implement-checkpoint.sh`
**Agente:** AG-01
**Budget:** ~2000 tokens

1. Crear `heartbeat-sender.sh`:
   - Lee `SPECBOX_ENGINE_MCP_URL` (igual que mcp-report.sh)
   - Recibe como argumentos: project_name (obligatorio)
   - Detecta automaticamente: git branch, coverage (si existe .quality/baselines/), checkpoint.json, feedback-summary.json
   - Lee `specbox-state.json` local si existe (para plan_progress)
   - Construye payload JSON del heartbeat
   - Primero intenta enviar via HTTP POST directo a `/api/heartbeat` (mas rapido, sin MCP protocol overhead)
   - Si falla, guarda en `.quality/pending_heartbeats.jsonl`
   - Al inicio, revisa si hay pending heartbeats y los envia
   - Todo en background (`&`), fire-and-forget
2. Extender `on-session-end.sh`: añadir llamada a `heartbeat-sender.sh` al final (3 lineas)
3. Extender `implement-checkpoint.sh`: añadir llamada a `heartbeat-sender.sh` al final (3 lineas)

**AC cubiertos:** AC-05, AC-06, AC-07, AC-08, AC-09

### Fase 3: specbox-state.json Local (UC-004)
**Archivos:** `.claude/hooks/heartbeat-sender.sh` (extender), `templates/CLAUDE.md.template`
**Agente:** AG-01
**Budget:** ~1000 tokens

1. En `heartbeat-sender.sh`, tras enviar heartbeat exitoso, escribir `specbox-state.json` en la raiz del repo con el mismo payload + `source: "local"`
2. Añadir `specbox-state.json` al `.gitignore` del template de SpecBox Engine
3. Documentar en `templates/CLAUDE.md.template` la existencia de specbox-state.json

**AC cubiertos:** AC-12, AC-13, AC-14

### Fase 4: GitHub Sync (UC-005, UC-006)
**Archivos:** `server/github_sync.py` (nuevo), `server/dashboard_api.py` (extender)
**Agente:** AG-01
**Budget:** ~2500 tokens

1. Crear `github_sync.py`:
   - Funcion `async sync_project(owner, repo, branch, state_path, force=False)`:
     - GET `https://api.github.com/repos/{owner}/{repo}/contents/specbox-state.json?ref={branch}` con auth header
     - Decodifica base64 content
     - Lee project_state.json existente; si `received_at < 30 min` y `force=False`, skip (heartbeat tiene prioridad)
     - Si actualiza: añade `source: "github_sync"`, `received_at: now()`
     - Retorna status dict
   - Funcion `async sync_all(state_path, force=False)`:
     - Lee registry.json, filtra proyectos con `repo_url`
     - Parsea owner/repo de cada URL
     - Llama sync_project por cada uno
     - Retorna lista de resultados
   - Funcion `parse_repo_url(url) -> (owner, repo)`:
     - Soporta `https://github.com/owner/repo` y `git@github.com:owner/repo.git`
   - Usa `httpx.AsyncClient` (ya instalado) con `GITHUB_TOKEN` env var
2. Añadir REST endpoint `POST /api/sync/github` en dashboard_api.py:
   - Auth via `SPECBOX_SYNC_TOKEN`
   - Acepta JSON body opcional con `repos` (lista) o usa registry.json
   - Llama `sync_all` o `sync_project` segun params
   - Retorna resultados por repo
3. Parseo de repo_url desde registry.json (UC-006)

**AC cubiertos:** AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21

### Fase 5: MCP Tools Conversacionales (UC-007 a UC-010)
**Archivos:** `server/tools/live_state.py` (nuevo), `server/server.py`
**Agente:** AG-01
**Budget:** ~2500 tokens

1. Crear `server/tools/live_state.py` con `register_live_state_tools(mcp, state_path)`:

   **Tool 1: `get_project_live_state(slug: str)`** (UC-007)
   - Lee `project_state.json` del proyecto
   - Aplica session decay
   - Calcula `time_since_last_update` humanizado ("hace 5 minutos", "hace 2 horas")
   - Si no hay project_state.json, fallback a meta.json con `data_source: "meta_fallback"`
   - Si slug no existe, retorna error con lista de proyectos disponibles

   **Tool 2: `get_all_projects_overview()`** (UC-008)
   - Itera registry.json
   - Lee project_state.json de cada proyecto (con decay)
   - Genera lista resumida: name, stack, session_active, current_feature, last_operation, time_since_last_update, health_emoji
   - health_emoji: "green_circle" (healthy + <1h), "yellow_circle" (degraded o >1h), "red_circle" (critical o >24h)
   - Ordena por last_activity desc
   - Incluye campo `summary`: "N proyectos activos, M con sesion activa, K con feedback abierto"

   **Tool 3: `get_active_sessions()`** (UC-009)
   - Filtra proyectos con session_active=true (post-decay)
   - Retorna lista: name, current_feature, current_phase, time_since_last_update
   - Si vacia: `{"active_sessions": [], "message": "No hay sesiones activas en este momento"}`

   **Tool 4: `refresh_project_state(slug: str)`** (UC-010)
   - Lee repo_url del proyecto en registry.json
   - Llama `sync_project` con `force=True` (ignora regla de 30 min)
   - Retorna project_state actualizado o error descriptivo

2. Registrar en `server/server.py`:
   ```python
   from .tools.live_state import register_live_state_tools
   register_live_state_tools(mcp, STATE_PATH)
   ```

**AC cubiertos:** AC-22 a AC-31

### Fase 6: Integracion y Docker
**Archivos:** `server/server.py`, `docker-compose.yml`, `install.sh`
**Agente:** AG-01
**Budget:** ~1000 tokens

1. Actualizar `server/server.py`:
   - Importar y registrar `register_live_state_tools`
   - Actualizar instructions del MCP con los nuevos tools
2. Actualizar `docker-compose.yml`:
   - Añadir `SPECBOX_SYNC_TOKEN` y `GITHUB_TOKEN` como env vars
3. Actualizar `install.sh`:
   - Copiar `heartbeat-sender.sh` a hooks

### Fase 7: Tests
**Archivos:** `tests/test_heartbeat.py` (nuevo), `tests/test_github_sync.py` (nuevo), `tests/test_live_state.py` (nuevo)
**Agente:** AG-04 (QA)
**Budget:** ~2000 tokens

1. `test_heartbeat.py`:
   - Test report_heartbeat persiste project_state.json
   - Test auto-registro de proyecto
   - Test auth requerido en REST endpoint
   - Test session decay lazy
2. `test_github_sync.py`:
   - Test parse_repo_url (https y git@)
   - Test sync solo actualiza si heartbeat > 30 min
   - Test sync graceful con repo fallido
3. `test_live_state.py`:
   - Test get_project_live_state con project_state.json
   - Test fallback a meta.json
   - Test get_all_projects_overview ordenacion y health_emoji
   - Test get_active_sessions con y sin sesiones
   - Test refresh_project_state

---

## Arbol de Archivos

```
server/
├── tools/
│   ├── state.py              ← MODIFICAR: +report_heartbeat, +_read_project_state, +_write_project_state, +_apply_session_decay
│   └── live_state.py         ← NUEVO: 4 MCP tools conversacionales (get_project_live_state, get_all_projects_overview, get_active_sessions, refresh_project_state)
├── github_sync.py            ← NUEVO: sync_project, sync_all, parse_repo_url
├── dashboard_api.py          ← MODIFICAR: +POST /api/heartbeat, +POST /api/sync/github (auth via SPECBOX_SYNC_TOKEN)
├── server.py                 ← MODIFICAR: +import y registro de live_state_tools
.claude/hooks/
├── heartbeat-sender.sh       ← NUEVO: construye payload, envia HTTP POST, queue local, escribe specbox-state.json
├── on-session-end.sh         ← MODIFICAR: +llamada a heartbeat-sender.sh
├── implement-checkpoint.sh   ← MODIFICAR: +llamada a heartbeat-sender.sh
docker-compose.yml            ← MODIFICAR: +SPECBOX_SYNC_TOKEN, +GITHUB_TOKEN env vars
install.sh                    ← MODIFICAR: +copiar heartbeat-sender.sh
tests/
├── test_heartbeat.py         ← NUEVO
├── test_github_sync.py       ← NUEVO
├── test_live_state.py        ← NUEVO
```

## Patrones a Seguir (del codigo existente)

### MCP Tool (state.py)
```python
@mcp.tool
def report_heartbeat(project: str, timestamp: str, ...) -> dict:
    project_dir = _ensure_project_dir(state_path, project)
    _auto_register(state_path, project)
    # ... build record, write ...
    _invalidate_cache(state_path)
    return {"status": "ok", "project": project, "event": "heartbeat"}
```

### REST Endpoint (dashboard_api.py)
```python
@mcp.custom_route("/api/heartbeat", methods=["POST"])
async def api_heartbeat(request: Request) -> JSONResponse:
    if not _check_sync_auth(request):
        return _json({"error": "Unauthorized"}, 401)
    body = await request.json()
    # ... validate, persist ...
    return _json({"status": "ok"})
```

### Hook (heartbeat-sender.sh)
```bash
#!/bin/bash
# Sigue el patron de mcp-report.sh:
# - Lee SPECBOX_ENGINE_MCP_URL
# - Fire-and-forget en background
# - Silent failure (exit 0)
# PERO envia HTTP POST directo a /api/heartbeat (no MCP protocol)
```

## Dependencias

- `httpx` (ya instalado — usado por PlaneClient, TrelloClient)
- GitHub REST API v3 (via httpx, sin SDK)
- n8n (existente en VPS — para cron de GitHub sync)

## Tradeoffs

| Decision | Alternativa descartada | Razon |
|----------|----------------------|-------|
| JSON file (sobrescribe) vs JSONL (append) para project_state | JSONL append | El state es un snapshot, no un log. Sobrescribir es mas simple y eficiente para lecturas |
| Lazy decay vs cron | Cron cada 30 min | Lazy no requiere proceso adicional, funciona igual de bien para 10-20 proyectos |
| HTTP POST directo vs MCP protocol para heartbeat | MCP protocol (3 roundtrips) | POST directo es 3x mas rapido (1 request vs 3) y el endpoint no necesita ser MCP tool |
| Un archivo live_state.py vs añadir a state.py | Todo en state.py (1250+ lineas) | Separacion de responsabilidades: state.py = ingestion/query existente, live_state.py = consultas conversacionales nuevas |
| SPECBOX_SYNC_TOKEN separado vs DASHBOARD_TOKEN | Reusar DASHBOARD_TOKEN | Diferentes niveles de acceso: dashboard es lectura, heartbeat es escritura |
