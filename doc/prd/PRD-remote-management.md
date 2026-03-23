# PRD: specbox-remote-management

## Descripcion

SpecBox Engine v5.2.0 gestiona 21+ proyectos pero solo es operable desde el MacBook local via Claude Code CLI. El estado activo de desarrollo vive localmente y no es accesible desde fuera. Este proyecto habilita la consulta de estado y ejecucion de comandos del engine desde iPhone (via Claude.ai iOS con MCP remoto nativo) y desde WhatsApp/Discord (via OpenClaw Gateway), aprovechando la suscripcion Claude Max (~200 euros/mes) que ya incluye soporte nativo para MCP servers remotos, sin coste incremental.

## Objetivo

Hacer operable SpecBox Engine desde cualquier dispositivo remoto (iPhone, WhatsApp, Discord) con zero-cost incremental, reutilizando toda la infraestructura existente (MCP Server en VPS, heartbeat protocol, GitHub sync, state store JSON).

## Usuario Objetivo

Developer (Jesus Perez Sanchez) — consulta y gestiona el estado de desarrollo de 21+ proyectos desde movil o mensajeria.

## Alcance

### Incluye
- Validacion y documentacion de conexion Claude.ai iOS a MCP remoto (auth, transport, URL)
- Polish de tools conversacionales existentes (JSON crudo a Markdown humanizado para movil)
- Observabilidad de heartbeats (llegan, fallan, estadisticas)
- OpenClaw Gateway Skill para WhatsApp/Discord
- Tools de escritura remota Fase 2 (mover UCs, marcar ACs, ejecutar reports)

### No incluye
- Migracion del state store a PostgreSQL (se mantiene JSON/JSONL en Docker volume)
- Cambios en el engine local (heartbeat-sender.sh ya funciona correctamente)
- Creacion de app nativa para iOS
- Interfaz web nueva (la Sala de Maquinas ya existe)
- Nuevos servicios de pago o API keys adicionales

---

## User Stories y Use Cases

### US-01: Acceso Remoto via Claude.ai iOS

> Como developer, quiero consultar el estado de mis proyectos desde mi iPhone via Claude.ai iOS conectado al MCP remoto, para tener visibilidad completa del desarrollo sin necesitar el MacBook.

#### UC-001: Validar conexion Claude.ai iOS a MCP remoto
- **Actor**: Developer (iPhone)
- **Horas estimadas**: 3h
- **Pantallas**: N/A (configuracion)

**Acceptance Criteria:**
- [ ] **AC-01**: Claude.ai iOS se conecta exitosamente al endpoint `https://mcp-specbox-engine.jpsdeveloper.com/mcp` usando transport streamable-http con Bearer token SPECBOX_SYNC_TOKEN en el header Authorization
- [ ] **AC-02**: Las 4 tools conversacionales existentes (get_project_live_state, get_all_projects_overview, get_active_sessions, refresh_project_state) responden correctamente desde Claude.ai iOS con latencia < 500ms medida desde el timestamp de la request al primer byte de respuesta
- [ ] **AC-03**: Si el Bearer token es invalido o ausente, el MCP server retorna error 401 Unauthorized sin exponer datos de estado

#### UC-002: Polish de respuestas conversacionales para movil
- **Actor**: Developer (iPhone)
- **Horas estimadas**: 5h
- **Pantallas**: N/A (output de tools MCP)

**Acceptance Criteria:**
- [ ] **AC-04**: `get_project_live_state` retorna un campo `summary` con texto Markdown humanizado que incluye: nombre del proyecto, estado de sesion (activa/inactiva), feature actual, progreso de UCs (X/Y), ultimo veredicto, y health indicator — en un maximo de 300 caracteres
- [ ] **AC-05**: `get_all_projects_overview` retorna un campo `summary_table` con una tabla Markdown donde cada fila es un proyecto con columnas: nombre, estado (emoji circle), feature actual, ultima actividad — ordenados por actividad mas reciente
- [ ] **AC-06**: `get_active_sessions` retorna un campo `summary` con texto conversacional en espanol que lista las sesiones activas con su feature y fase actual, o el mensaje "No hay sesiones activas en este momento" si no hay ninguna
- [ ] **AC-07**: Todas las respuestas de tools conversacionales incluyen timestamps formateados como "hace X minutos/horas/dias" en espanol, nunca timestamps ISO crudos en los campos de summary

#### UC-003: Observabilidad de heartbeats
- **Actor**: Developer (iPhone)
- **Horas estimadas**: 5h
- **Pantallas**: N/A (MCP tools + REST endpoint)

**Acceptance Criteria:**
- [ ] **AC-08**: Existe un nuevo MCP tool `get_heartbeat_stats` que retorna: total de heartbeats recibidos en las ultimas 24h, heartbeats por proyecto, ultimo heartbeat de cada proyecto con timestamp, y lista de proyectos con heartbeat stale (> 30 min sin heartbeat y sesion activa)
- [ ] **AC-09**: Existe un nuevo REST endpoint `GET /api/heartbeats/stats` que retorna las mismas metricas que el tool `get_heartbeat_stats` en formato JSON, protegido por Bearer token auth
- [ ] **AC-10**: Cada heartbeat recibido en `POST /api/heartbeat` se registra en un archivo `heartbeats.jsonl` dentro de `/data/state/projects/{project}/` con timestamp, source IP, y status code de procesamiento
- [ ] **AC-11**: Si un proyecto tiene session_active=true y no ha recibido heartbeat en mas de 30 minutos, `get_heartbeat_stats` lo marca como "stale" en la lista de alertas

---

### US-02: Acceso Remoto via WhatsApp/Discord (OpenClaw Gateway)

> Como developer, quiero consultar el estado de mis proyectos desde WhatsApp o Discord via OpenClaw Gateway, para tener acceso desde cualquier plataforma de mensajeria.

#### UC-004: OpenClaw Gateway Skill
- **Actor**: Developer (WhatsApp/Discord)
- **Horas estimadas**: 8h
- **Pantallas**: N/A (skill de integracion)

**Acceptance Criteria:**
- [ ] **AC-12**: Existe una nueva skill `/remote` en `.claude/skills/remote/SKILL.md` que define los comandos conversacionales: "estado de [proyecto]", "resumen de todos", "sesiones activas", "refresh [proyecto]", documentados con triggers y ejemplos
- [ ] **AC-13**: La skill `/remote` invoca los MCP tools conversacionales existentes (get_project_live_state, get_all_projects_overview, get_active_sessions, refresh_project_state) y formatea las respuestas en texto plano sin Markdown complejo (max 2000 caracteres por respuesta) para compatibilidad con WhatsApp
- [ ] **AC-14**: La skill `/remote` incluye documentacion en su SKILL.md de como configurar OpenClaw Gateway para conectar WhatsApp/Discord a Claude Code con el MCP remoto habilitado

---

### US-03: Tools de Escritura Remota (Fase 2)

> Como developer, quiero ejecutar operaciones de escritura en mis proyectos desde el movil (mover UCs, marcar ACs, obtener reports), para gestionar el flujo de desarrollo sin el MacBook.

#### UC-005: Tool remoto para mover UCs entre estados
- **Actor**: Developer (iPhone/WhatsApp)
- **Horas estimadas**: 4h
- **Pantallas**: N/A (MCP tool)

**Acceptance Criteria:**
- [ ] **AC-15**: El MCP tool existente `move_uc` es accesible y funcional desde Claude.ai iOS via MCP remoto, ejecutando la operacion en el backend configurado (Trello o Plane) del proyecto especificado
- [ ] **AC-16**: La respuesta de `move_uc` ejecutada remotamente incluye un campo `summary` con texto humanizado que confirma: "UC-XXX movido de [estado_origen] a [estado_destino] en [proyecto]"

#### UC-006: Tool remoto para marcar acceptance criteria
- **Actor**: Developer (iPhone/WhatsApp)
- **Horas estimadas**: 3h
- **Pantallas**: N/A (MCP tool)

**Acceptance Criteria:**
- [ ] **AC-17**: El MCP tool existente `mark_ac` es accesible y funcional desde Claude.ai iOS, marcando el AC especificado como done/pending en el backend del proyecto
- [ ] **AC-18**: El MCP tool existente `mark_ac_batch` es accesible y funcional desde Claude.ai iOS, con respuesta que incluye summary humanizado: "Marcados N/M criterios como [done] en UC-XXX"

#### UC-007: Tools remotos para reports
- **Actor**: Developer (iPhone/WhatsApp)
- **Horas estimadas**: 4h
- **Pantallas**: N/A (MCP tools)

**Acceptance Criteria:**
- [ ] **AC-19**: Los MCP tools `get_board_status`, `get_sprint_status`, y `get_delivery_report` retornan campos `summary` con resumen humanizado en Markdown que incluye: total US/UC, progreso en porcentaje, UCs bloqueados, y ultimo merge — en maximo 500 caracteres cada uno
- [ ] **AC-20**: Todos los tools de report accesibles remotamente incluyen un campo `generated_at` con timestamp ISO y un campo `project` con el slug del proyecto para trazabilidad

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medicion |
|-----|----------|----------|
| Latencia | Queries < 500ms desde iPhone en 4G | Timestamp de request vs primer byte de respuesta |
| Resiliencia | Si VPS caido, engine local no se afecta (heartbeat fire-and-forget con timeout 5s) | Test: desconectar VPS, verificar que hooks locales no bloquean |
| Seguridad | Bearer token auth (SPECBOX_SYNC_TOKEN) en todos los endpoints | Test: request sin token retorna 401 |
| Disponibilidad | Heartbeats se encolan localmente si VPS no responde (.quality/pending_heartbeats.jsonl) | Test: simular VPS down, verificar que pending file se llena y se drena al reconectar |
| Privacidad | Datos de proyectos solo accesibles con token valido, no hay datos expuestos sin auth | Audit: revisar todos los endpoints publicos (/health, /api/benchmark/public) |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| Claude.ai iOS no soporte Bearer token custom en MCP remoto | Media | Alto | Investigar documentacion de Claude.ai MCP connector; alternativa: query param auth fallback |
| OpenClaw Gateway no sea estable para produccion | Media | Medio | Skill `/remote` es standalone; OpenClaw es solo un wrapper, se puede reemplazar |
| Latencia > 500ms en state store JSON con 21+ proyectos | Baja | Medio | JSON files son < 100KB; si crece, implementar cache en memoria (ya existe dashboard_cache.json) |
| Heartbeat storm si multiples sesiones activas simultaneamente | Baja | Bajo | Heartbeats ya son fire-and-forget con timeout 5s; rate limit a nivel de Traefik si necesario |

---

## Stack Tecnico

- **Backend**: Python 3.12+ (FastMCP, httpx, structlog) — ya existente
- **State Store**: JSON/JSONL en Docker volume `/data/state/` — ya existente
- **Infra**: EasyPanel + Traefik con SSL en VPS 38.242.206.41 — ya existente
- **Transport**: streamable-http (FastMCP) — ya existente
- **Frontend**: N/A (sin pantallas nuevas)
- **Integraciones**: Claude.ai iOS MCP connector, OpenClaw Gateway

## Archivos Principales

```
server/
  tools/live_state.py         ← Polish de respuestas conversacionales (UC-002)
  tools/state.py              ← Registro de heartbeats en JSONL (UC-003)
  tools/heartbeat_stats.py    ← Nuevo: tool get_heartbeat_stats (UC-003)
  tools/spec_driven.py        ← Verificar accesibilidad remota de move_uc, mark_ac (UC-005, UC-006)
  dashboard_api.py            ← Nuevo endpoint /api/heartbeats/stats (UC-003), summaries en reports (UC-007)
  server.py                   ← Registrar nuevo tool module
.claude/skills/remote/SKILL.md ← Nuevo: skill /remote para OpenClaw (UC-004)
doc/remote-management/
  setup-claude-ios.md         ← Documentacion de setup iPhone (UC-001)
  setup-openclaw.md           ← Documentacion de setup OpenClaw (UC-004)
```

## Dependencias
- SpecBox Engine v5.2.0 desplegado en VPS con heartbeat protocol funcional
- Claude Max subscription con soporte MCP remoto en Claude.ai iOS
- OpenClaw Gateway (para US-02 solamente)

---

## Definition Quality Gate

| AC | UC | Especificidad | Medibilidad | Testabilidad | Veredicto |
|----|-----|--------------|-------------|--------------|-----------|
| AC-01 | UC-001 | 2 | 2 | 2 | OK |
| AC-02 | UC-001 | 2 | 2 | 2 | OK |
| AC-03 | UC-001 | 2 | 2 | 2 | OK |
| AC-04 | UC-002 | 2 | 2 | 2 | OK |
| AC-05 | UC-002 | 2 | 2 | 2 | OK |
| AC-06 | UC-002 | 2 | 2 | 1 | OK |
| AC-07 | UC-002 | 2 | 2 | 2 | OK |
| AC-08 | UC-003 | 2 | 2 | 2 | OK |
| AC-09 | UC-003 | 2 | 2 | 2 | OK |
| AC-10 | UC-003 | 2 | 2 | 2 | OK |
| AC-11 | UC-003 | 2 | 2 | 2 | OK |
| AC-12 | UC-004 | 2 | 2 | 1 | OK |
| AC-13 | UC-004 | 2 | 2 | 2 | OK |
| AC-14 | UC-004 | 2 | 1 | 1 | OK |
| AC-15 | UC-005 | 2 | 2 | 2 | OK |
| AC-16 | UC-005 | 2 | 2 | 2 | OK |
| AC-17 | UC-006 | 2 | 2 | 2 | OK |
| AC-18 | UC-006 | 2 | 2 | 2 | OK |
| AC-19 | UC-007 | 2 | 2 | 2 | OK |
| AC-20 | UC-007 | 2 | 2 | 2 | OK |

```
Definition Quality Gate: APROBADO
Criterios funcionales: 20 (promedio: 1.95/2.0)
Cobertura: 7 Use Cases cubiertos de 7
VEG Readiness: DISABLED (sin UI visual)
```

---

## Plan de Implementacion (alto nivel)

### Fase 1 (MVP Lectura): US-01 — UC-001, UC-002, UC-003
**Estimacion**: 13h
1. Documentar y validar conexion Claude.ai iOS a MCP remoto
2. Polish de live_state.py: anadir campos `summary` y `summary_table` a las 4 tools
3. Crear `heartbeat_stats.py` con tool y endpoint de observabilidad
4. Modificar `POST /api/heartbeat` para registrar en heartbeats.jsonl
5. Tests: 20+ tests nuevos

### Fase 2 (Gateway): US-02 — UC-004
**Estimacion**: 8h
1. Crear skill `/remote` con SKILL.md
2. Documentar setup OpenClaw
3. Tests: 5+ tests de formateo

### Fase 3 (Escritura): US-03 — UC-005, UC-006, UC-007
**Estimacion**: 11h
1. Verificar que spec_driven tools funcionan via MCP remoto (ya registrados)
2. Anadir campos `summary` a move_uc, mark_ac, mark_ac_batch
3. Anadir campos `summary` a board_status, sprint_status, delivery_report
4. Tests: 15+ tests nuevos

### Total estimado: 32h

---

*Generado: 2026-03-18*
*Prioridad: high*
*Complejidad: Media*
