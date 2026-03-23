# Plan: specbox-remote-management

> Generado: 2026-03-18
> Origen: PRD `doc/prd/PRD-remote-management.md`
> Estado: Pendiente

---

## Resumen

Habilitar la operacion remota completa de SpecBox Engine desde iPhone (Claude.ai iOS + MCP remoto) y WhatsApp/Discord (OpenClaw Gateway), anadiendo polish conversacional a los tools existentes, observabilidad de heartbeats, una skill `/remote`, y summaries humanizados a los tools de escritura.

## Analisis UI (Fase 0)

No aplica. Este PRD no tiene pantallas visuales. Todos los UCs operan a traves de tools MCP y REST endpoints.

**stitch_designs**: N/A

## Visual Experience Generation

**Modo VEG**: Desactivado (sin UI visual, sin seccion Audiencia con targets)

---

## Fases de Implementacion

### Fase 1: Observabilidad de Heartbeats (UC-003) — AC-08 a AC-11

**Archivos a modificar/crear:**

| Archivo | Accion |
|---------|--------|
| `server/tools/heartbeat_stats.py` | CREAR — nuevo modulo de tool |
| `server/dashboard_api.py` | MODIFICAR — anadir endpoint `GET /api/heartbeats/stats` y logging de heartbeats en JSONL |
| `server/server.py` | MODIFICAR — registrar `register_heartbeat_stats_tools` |

**Detalle:**

1. **Logging de heartbeats en JSONL (AC-10)**: En el handler existente de `POST /api/heartbeat` dentro de `dashboard_api.py` (linea 661), tras escribir `project_state.json`, anadir un append a `heartbeats.jsonl` dentro de `/data/state/projects/{project}/`. Cada entrada incluye: `timestamp`, `received_at`, `source_ip` (de `request.client.host`), `status` ("ok").

2. **Tool `get_heartbeat_stats` (AC-08)**: Nuevo archivo `server/tools/heartbeat_stats.py` con funcion `register_heartbeat_stats_tools(mcp, state_path)`. El tool lee `heartbeats.jsonl` de todos los proyectos, filtra ultimas 24h, computa:
   - `total_24h`: total de heartbeats recibidos
   - `by_project`: dict con cuenta por proyecto y `last_heartbeat` timestamp
   - `stale_projects`: lista de proyectos con `session_active=true` en `project_state.json` pero sin heartbeat en 30+ min (AC-11)

   Patron a seguir: `register_live_state_tools` en `live_state.py` — misma estructura con `state_path`, importaciones de helpers de `state.py`.

3. **REST endpoint `GET /api/heartbeats/stats` (AC-09)**: En `dashboard_api.py`, nuevo route que invoca la misma logica del tool (extraer la logica a una funcion helper compartida, no duplicar). Protegido con `_check_auth`.

4. **Registro en `server.py`**: Anadir import de `register_heartbeat_stats_tools` y llamada de registro, siguiendo el patron existente (linea 147 como referencia).

**Tests (archivo nuevo: `tests/test_heartbeat_stats.py`):**
- Test: heartbeat logging escribe JSONL correctamente
- Test: get_heartbeat_stats retorna conteo correcto en 24h
- Test: filtro de stale projects con session_active=true y heartbeat > 30 min
- Test: REST endpoint retorna JSON con auth
- Test: REST endpoint retorna 401 sin auth
- Estimacion: 8 tests

---

### Fase 2: Polish de Respuestas Conversacionales (UC-002) — AC-04 a AC-07

**Archivos a modificar:**

| Archivo | Accion |
|---------|--------|
| `server/tools/live_state.py` | MODIFICAR — anadir campos `summary` / `summary_table` |

**Detalle:**

1. **`get_project_live_state` — campo `summary` (AC-04)**: Tras construir el dict de retorno (linea 124-146), generar un string Markdown de max 300 caracteres:
   ```
   "**mcprofit** — sesion activa | Feature: invoice-detail | UCs: 12/18 | Ultimo veredicto: ACCEPTED | Health: green_circle | Ultima actividad: hace 5 minutos"
   ```
   Usar `_humanize_timedelta` (ya existe) para timestamps. El campo `summary` se anade al dict de retorno.

2. **`get_all_projects_overview` — campo `summary_table` (AC-05)**: Generar tabla Markdown ordenada por actividad:
   ```markdown
   | Proyecto | Estado | Feature | Ultima actividad |
   |----------|--------|---------|-----------------|
   | mcprofit | green_circle | invoice-detail | hace 5 min |
   | futplanner | yellow_circle | — | hace 2 dias |
   ```
   El campo `summary_table` es un string con la tabla completa.

3. **`get_active_sessions` — campo `summary` (AC-06)**: Anadir un string conversacional en espanol. Si hay sesiones: "Hay 2 sesiones activas: mcprofit (implement, invoice-detail), futplanner (plan, onboarding)". Si no hay: ya existe el mensaje "No hay sesiones activas en este momento" (linea 251).

4. **Timestamps humanizados (AC-07)**: Ya se usa `_humanize_timedelta` en todos los tools, pero verificar que no hay ISO timestamps crudos expuestos en los campos de summary. Actualmente `received_at` se pasa como ISO en el loop interno de `get_all_projects_overview` (solo para sort) y se elimina antes del return (linea 206-207), lo cual ya es correcto.

**Tests (modificar `tests/test_live_state.py`):**
- Test: summary de get_project_live_state tiene max 300 chars
- Test: summary_table de get_all_projects_overview es tabla Markdown valida
- Test: summary de get_active_sessions es texto en espanol
- Test: ningun campo summary contiene timestamps ISO crudos
- Estimacion: 6 tests nuevos

---

### Fase 3: Validacion de Conexion Claude.ai iOS (UC-001) — AC-01 a AC-03

**Archivos a crear:**

| Archivo | Accion |
|---------|--------|
| `doc/remote-management/setup-claude-ios.md` | CREAR — guia de configuracion |

**Detalle:**

1. **Documentacion de setup (AC-01)**: Crear guia paso a paso para configurar Claude.ai iOS con el MCP remoto:
   - URL: `https://mcp-specbox-engine.jpsdeveloper.com/mcp`
   - Transport: streamable-http
   - Auth: Bearer token via `SPECBOX_SYNC_TOKEN`
   - Troubleshooting: verificar con `curl -H "Authorization: Bearer TOKEN" https://mcp-specbox-engine.jpsdeveloper.com/health`

2. **Verificacion de latencia (AC-02)**: Anadir seccion con comando de test para medir latencia desde iPhone:
   - El endpoint `/health` ya existe sin auth
   - Las 4 tools conversacionales ya estan registradas en el server

3. **Validacion de auth (AC-03)**: El codigo de auth en `dashboard_api.py` linea 43-49 ya rechaza requests sin token valido con 401 cuando `SPECBOX_SYNC_TOKEN` esta configurado. Para MCP tools, FastMCP no tiene middleware de auth propio — la auth ocurre a nivel de transport/connector de Claude.ai. Documentar este comportamiento.

**Nota**: Este UC es principalmente de configuracion y verificacion manual. No requiere cambios de codigo significativos, pero la documentacion es el entregable.

---

### Fase 4: Skill `/remote` para OpenClaw (UC-004) — AC-12 a AC-14

**Archivos a crear:**

| Archivo | Accion |
|---------|--------|
| `.claude/skills/remote/SKILL.md` | CREAR — nueva skill |
| `doc/remote-management/setup-openclaw.md` | CREAR — guia de configuracion OpenClaw |

**Detalle:**

1. **SKILL.md (AC-12)**: Crear skill con triggers ("estado de", "resumen de todos", "sesiones activas", "refresh") y ejemplos. La skill es un wrapper conversacional que:
   - Parsea la intencion del usuario (que proyecto, que operacion)
   - Invoca el MCP tool correspondiente
   - Formatea la respuesta en texto plano (max 2000 chars) sin Markdown complejo (AC-13)

   Patron a seguir: `.claude/skills/explore/SKILL.md` como referencia de estructura YAML frontmatter.

2. **Formateo para WhatsApp (AC-13)**: Las respuestas deben evitar tablas Markdown complejas (WhatsApp no las renderiza). Usar listas simples con guiones y emojis como indicadores visuales.

3. **Documentacion OpenClaw (AC-14)**: Crear guia con:
   - Como instalar OpenClaw Gateway
   - Como configurar el MCP remoto en OpenClaw
   - Ejemplo de comando WhatsApp → Claude Code → MCP tool → respuesta

**Tests (archivo nuevo: `tests/test_remote_skill.py`):**
- Test: SKILL.md tiene frontmatter YAML valido
- Test: triggers documentados
- Estimacion: 3 tests

---

### Fase 5: Summaries en Tools de Escritura (UC-005, UC-006, UC-007) — AC-15 a AC-20

**Archivos a modificar:**

| Archivo | Accion |
|---------|--------|
| `server/tools/spec_driven.py` | MODIFICAR — anadir campos `summary` a 5 tools |

**Detalle:**

1. **`move_uc` — campo `summary` (AC-15, AC-16)**: En el return dict, anadir:
   ```python
   "summary": f"UC-{uc_id} movido de {original_state} a {target} en {board_id}"
   ```
   Necesita capturar el estado original antes del move. Anadir `original_state = uc_item.state` antes de la llamada a `update_item`.

2. **`mark_ac` — campo `summary` (AC-17)**: En el return dict, anadir:
   ```python
   "summary": f"{ac_id} marcado como {'PASSED' if passed else 'FAILED'} en {uc_id}"
   ```

3. **`mark_ac_batch` — campo `summary` (AC-18)**: En el return dict, anadir:
   ```python
   "summary": f"Marcados {passed_count}/{len(results)} criterios como done en {uc_id}"
   ```

4. **`get_board_status`, `get_sprint_status`, `get_delivery_report` — campo `summary` (AC-19, AC-20)**:
   - `get_board_status`: Anadir summary con total US/UC, progreso, UCs bloqueados
   - `get_sprint_status`: Anadir summary con counts, horas, AC pass rate, bloqueados
   - `get_delivery_report`: Ya tiene campo `summary` pero es un dict, no texto. Anadir campo `summary_text` para no romper backward compatibility

   Todos deben incluir `generated_at` (AC-20). Anadir a `get_sprint_status` y `get_board_status`.

5. **Accesibilidad remota (AC-15, AC-17)**: Los tools ya estan registrados en el MCP server y son accesibles via MCP remoto sin cambios adicionales.

**Tests (archivo nuevo: `tests/test_remote_summaries.py`):**
- Test: move_uc retorna campo summary con texto humanizado
- Test: mark_ac retorna campo summary
- Test: mark_ac_batch retorna campo summary con conteo
- Test: get_sprint_status retorna generated_at y summary
- Test: get_board_status retorna generated_at y summary
- Test: get_delivery_report retorna summary text (max 500 chars)
- Test: summary de report tools no excede 500 caracteres
- Estimacion: 10 tests

---

## Alternativas y Tradeoffs

| Decision | Opcion elegida | Alternativa descartada | Razon |
|----------|---------------|----------------------|-------|
| State store | JSON/JSONL filesystem | PostgreSQL | 21 proyectos con archivos < 100KB; PostgreSQL aniade complejidad operacional sin beneficio medible |
| Heartbeat logging | Append a JSONL por proyecto | SQLite global | Consistencia con el patron existente de todos los demas logs |
| Summary en tools existentes | Anadir campo `summary` al dict de retorno | Crear tools wrapper separados | Backward compatible — campos nuevos no rompen consumidores existentes |
| Skill /remote | SKILL.md standalone | CLI wrapper script | Las skills son el mecanismo canonico del engine |
| Auth MCP remoto | Depender del auth del transport | Implementar auth middleware en FastMCP | FastMCP no expone middleware de auth para tools individuales |
| summary_table format | Tabla Markdown | JSON array | Claude.ai renderiza Markdown nativamente; tabla mas legible desde movil |

---

## Archivos a Crear/Modificar

```
server/
├── tools/
│   ├── heartbeat_stats.py      ← NUEVO: tool get_heartbeat_stats + helper
│   ├── live_state.py           ← MODIFICAR: anadir summary/summary_table a 3 tools
│   ├── spec_driven.py          ← MODIFICAR: anadir summary a move_uc, mark_ac, mark_ac_batch, board_status, sprint_status
│   └── state.py                ← MODIFICAR: anadir _append_heartbeat_log helper (opcional)
├── dashboard_api.py            ← MODIFICAR: logging heartbeats JSONL + GET /api/heartbeats/stats
└── server.py                   ← MODIFICAR: registrar heartbeat_stats tools

.claude/skills/remote/
└── SKILL.md                    ← NUEVO: skill /remote para OpenClaw

doc/remote-management/
├── setup-claude-ios.md         ← NUEVO: guia de setup iPhone
└── setup-openclaw.md           ← NUEVO: guia de setup OpenClaw

tests/
├── test_heartbeat_stats.py     ← NUEVO: 8 tests
├── test_remote_summaries.py    ← NUEVO: 10 tests
├── test_remote_skill.py        ← NUEVO: 3 tests
└── test_live_state.py          ← MODIFICAR: +6 tests para summaries
```

---

## Comandos Finales

```bash
# Run tests
python -m pytest tests/ -v

# Verify tool count
python -c "from server.server import mcp; print(f'Tools: {len(mcp._tool_manager._tools)}')"

# Test heartbeat endpoint locally
curl -X POST http://localhost:8000/api/heartbeat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SPECBOX_SYNC_TOKEN" \
  -d '{"project":"test","session_active":true}'

# Test heartbeat stats endpoint
curl http://localhost:8000/api/heartbeats/stats \
  -H "Authorization: Bearer $SPECBOX_SYNC_TOKEN"
```

---

## Orden de Implementacion y Dependencias

```
Fase 1 (UC-003) ─── No depende de nada, es la base de observabilidad
    ↓
Fase 2 (UC-002) ─── Independiente, pero beneficia testear con Fase 1
    ↓
Fase 3 (UC-001) ─── Requiere Fase 1+2 para validar end-to-end desde iPhone
    ↓
Fase 4 (UC-004) ─── Requiere Fase 2 (summaries) para que las respuestas sean utiles
    ↓
Fase 5 (UC-005-007) ─── Independiente pero logicamente posterior (Fase 2 del PRD)
```

**Estimacion total: 32h**
- Fase 1: 5h
- Fase 2: 5h
- Fase 3: 3h
- Fase 4: 8h
- Fase 5: 11h
