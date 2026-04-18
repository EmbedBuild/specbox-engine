# PRD — `specbox-supabase` MCP

**Status**: Draft v1
**Author**: Claude (opus-4-7, via autopilot session 2026-04-18)
**Target executor**: SpecBox Engine team
**Related skills**: `/stripe-connect`, `/manual-test`, skills futuras que tocan Edge Functions
**Sibling PRD**: `specbox-stripe` MCP — tools T1-T4 ya implementadas (packages/specbox-stripe-mcp/, H1 shipped 2026-04-17). Este PRD desbloquea UC-7 de ese paquete.

---

## 1. Motivación y problema

El MCP `specbox-stripe` (shipped 2026-04-17) automatiza setup de Stripe hasta el punto de dejar a mano los webhook secrets y la API key en un formato listo para inyectar. La skill `/stripe-connect` los necesita **en Supabase Edge Functions** como variables de entorno (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET_PLATFORM`, `STRIPE_WEBHOOK_SECRET_CONNECT`, `DEFAULT_APPLICATION_FEE_PERCENT`).

### El caso real que disparó este PRD

Durante la ejecución de la skill `/stripe-connect` en **moto.fan** (2026-04-17):

1. Backend Supabase desplegado vía MCP (migration + 5 Edge Functions) ✅
2. Setup Stripe automatizado vía `specbox-stripe` MCP (Connect canary + webhooks + products/prices) ✅
3. Al llegar al paso "inyectar los 4 secrets en Supabase" → **acción manual bloqueante**: el developer tiene que ir a `dashboard.supabase.com/project/{ref}/settings/functions` y pegar los 4 valores a mano.

Ese único paso rompe el flujo de automatización end-to-end que SpecBox promete. Es también el último click manual irreducible entre `/stripe-connect` y `/plan UC-301`.

### Por qué el MCP oficial de Supabase no cierra esta brecha

El MCP oficial (`github.com/supabase-community/supabase-mcp`, ~20 tools) cubre: database, edge functions deploy, development, debugging, branching, storage. **NO cubre secrets management** — documentado explícitamente como gap en [supabase-community/supabase-mcp#120](https://github.com/supabase-community/supabase-mcp/issues/120).

### Por qué tiene sentido que SpecBox lo llene

Mismo razonamiento que el PRD de `specbox-stripe`: SpecBox es la capa de setup-as-code declarativa. Los MCPs verticales (`specbox-stripe`, este nuevo `specbox-supabase`, futuros `specbox-firebase`, etc.) llenan gaps específicos de los MCPs oficiales sin competir con ellos — se combinan. Este paquete es **pequeño por diseño** (3 tools) y se puede extender más adelante si surgen más gaps de Supabase Management.

### Resultado del research técnico

La [Supabase Management API](https://supabase.com/docs/reference/api/introduction) expone oficialmente:

- `GET /v1/projects/{ref}/secrets` — list ([docs](https://supabase.com/docs/reference/api/list-all-secrets))
- `POST /v1/projects/{ref}/secrets` — bulk create/overwrite ([docs](https://supabase.com/docs/reference/api/bulk-create-secrets))
- `DELETE /v1/projects/{ref}/secrets` — bulk delete ([docs](https://supabase.com/docs/reference/api/bulk-delete-secrets))

Auth: Personal Access Token global del usuario, header `Authorization: Bearer <PAT>`. Rate limit: 120 req/min por usuario+proyecto. El comando CLI `supabase secrets set` usa exactamente esta misma API por debajo (no hay endpoint privado). Esto simplifica las decisiones de diseño: **Opción A — llamar la Management API directamente**.

---

## 2. Objetivos y no-objetivos

### Objetivos (v1)

- **O1**. Permitir que la skill `/stripe-connect` (y futuras) inyecte secrets en Supabase Edge Functions sin intervención manual del developer.
- **O2**. Ofrecer operaciones **idempotentes**: la API de Supabase sobrescribe secrets por nombre, pero el MCP debe detectar no-ops (mismo valor ya presente) para que el heartbeat refleje `idempotency_hit=true` y no se contamine el log de cambios.
- **O3**. Ofrecer un `list_edge_secrets` que cualquier skill pueda llamar para verificar estado antes de reconciliar.
- **O4**. Seguir la estética SpecBox heredada de `specbox-stripe`:
  - Response envelope estándar `{success, data, error, warnings, evidence}`.
  - Evidencia Engram fire-and-forget por call.
  - Heartbeat `event_type="supabase_mcp_call"` al engine.
  - Redacción de valores sensibles en logs (nunca loggear el **valor** del secret, solo el nombre).
  - Safeguards explícitas: este MCP maneja datos sensibles por diseño, toda operación de escritura requiere confirmación explícita en el input.
- **O5**. Ser la base para futuras tools de Supabase Management API no cubiertas por el MCP oficial (custom domains, network restrictions, API keys rotation, etc.) sin tener que refactorizar.

### No-objetivos (v1)

- **N1**. **No reimplementar operaciones de database, edge functions deploy, storage, branching**. Esos los cubre el MCP oficial de Supabase. Duplicar invita bugs.
- **N2**. **No soportar self-hosted Supabase** en v1. La Management API es cloud-only. Se evaluará demanda tras v1.
- **N3**. **No automatizar creación de proyectos Supabase** (`POST /v1/projects`). Fuera de alcance — el proyecto existe antes de la skill.
- **N4**. **No tocar database secrets ni auth config**. Solo Edge Function environment secrets (el endpoint `/v1/projects/{ref}/secrets`).
- **N5**. **No rotar secrets existentes automáticamente**. Rotación es una decisión de negocio; si el dev quiere rotar, invoca `set_edge_secret` explícitamente con el nuevo valor.
- **N6**. **No persistir secrets en disco**. Ni en `.quality/`, ni en Engram, ni en logs. Solo el **nombre** del secret puede aparecer como evidencia; el **valor** fluye del caller a la API y se descarta.

---

## 3. Casos de uso prioritarios

### CU-1: Cierre del flujo `/stripe-connect` (caso disparador)

**Actor**: skill `/stripe-connect` (tras ejecutar los 4 tools de `specbox-stripe`)
**Precondición**: la skill tiene en memoria los 4 valores (2 whsec de `setup_webhook_endpoints`, sk_test de env, DEFAULT_APPLICATION_FEE_PERCENT)
**Flujo**:
1. Skill llama `set_edge_secret(project_ref="gjwqsehingipcqmngbso", secrets={STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET_PLATFORM, STRIPE_WEBHOOK_SECRET_CONNECT, DEFAULT_APPLICATION_FEE_PERCENT})` → recibe `{applied: [4 names], skipped: []}`
2. Skill llama `mcp__specbox-stripe__get_setup_status(...)` → `verdict: "ready"`
3. Skill muestra resumen final al dev: "Setup completo. Ejecuta `/plan UC-301`."

**Resultado**: cero clicks manuales entre `/stripe-connect` y `/plan`.

### CU-2: Re-ejecución idempotente

**Actor**: skill `/stripe-connect` re-ejecutada tras crash intermedio
**Precondición**: 2 de los 4 secrets ya fueron seteados en un intento anterior
**Flujo**:
1. `list_edge_secrets(project_ref)` → devuelve los 2 ya presentes con sus `updated_at` (no su valor — la API de Supabase nunca retorna valores en `GET`).
2. `set_edge_secret` con los 4 valores. La API de Supabase sobrescribe por nombre (no es error si ya existen). El tool retorna `{applied: [4 names], all_overwritten: true}`.

**Nota crítica**: la Management API NO permite leer el valor de un secret via `GET`. Por eso `list_edge_secrets` solo devuelve nombres + timestamps, nunca valores. La idempotencia es por existencia del nombre, no por comparación de valor.

### CU-3: Verificación pre-deployment

**Actor**: skill `/manual-test` antes de testear suscripciones Stripe
**Flujo**:
1. `list_edge_secrets(project_ref)` → recibe `{names: [STRIPE_SECRET_KEY, ...]}`.
2. Skill compara contra la lista esperada (`expected_names=[...]`) y avisa al dev si falta alguno.

### CU-4: Cleanup entre proyectos demo

**Actor**: dev limpiando un proyecto demo
**Flujo**:
1. `unset_edge_secret(project_ref, names=["STRIPE_SECRET_KEY", ...], confirm_token="I understand this removes secrets from the Supabase project")` → `{deleted: [...]}`.
2. El dev verifica con `list_edge_secrets` que efectivamente desaparecieron.

---

## 4. Alcance de tools v1

### Priorización (todas MVP en v1 — son 3, no tiene sentido diferir)

| # | Tool | Prioridad | Justificación |
|---|---|---|---|
| T1 | `set_edge_secret` | **MVP** | Cierra el loop de `/stripe-connect`. Desbloqueador principal. |
| T2 | `list_edge_secrets` | **MVP** | Health check + pre-flight para idempotencia de skills. |
| T3 | `unset_edge_secret` | **MVP** | DX para iteración y cleanup. Safety: requiere confirm_token. |

### Decisiones de diseño transversales

**D1. Autenticación — PAT por call, igual que `specbox-stripe` con la Stripe API key**:
- **v1**: parámetro `supabase_access_token` en cada call. Flexibilidad multi-proyecto; el tool-call log es sensible por diseño.
- **v1.1**: resolver por alias en un secret store opcional (ej. `access_token_alias: "motofan-pat"`). Alineado con la misma evolución propuesta para `specbox-stripe`.

**D2. No hay distinción test/live** (a diferencia de Stripe):
- Supabase no tiene modos. Un PAT da acceso a los proyectos del usuario. El tool rechaza operaciones sobre proyectos que no pertenecen al PAT (la API devuelve 404/403 naturalmente).
- **Safeguard equivalente al live-mode de Stripe**: operaciones destructivas (`unset_edge_secret`) requieren `confirm_token` literal. Operaciones de escritura de secrets loggean nombre + project_ref pero nunca el valor.

**D3. Idempotencia**:
- `set_edge_secret` es idempotente por diseño de la API de Supabase (POST bulk sobrescribe por nombre). El tool emite heartbeat con `idempotency_hit=true` si **todos los nombres ya existían antes del POST** (detectado via `list_edge_secrets` previo). Esto matches la semántica de `specbox-stripe`.
- **Compromiso explícito**: el MCP hace UN GET antes del POST para poder reportar `idempotency_hit` correctamente. Coste: 2 requests por call en lugar de 1. Aceptable dado el budget de 120 req/min.
- `unset_edge_secret` es idempotente solo en la API (DELETE no falla si el nombre no existe). El tool reporta en `data.skipped` los nombres que no estaban presentes.

**D4. Formato estándar de respuestas** — **hereda exactamente el envelope de `specbox-stripe`** (PRD §4 D4):

```ts
{
  success: boolean,
  data?: T,
  error?: { code: string, message: string, remediation?: string },
  warnings?: string[],
  evidence?: { engram_observation_id?: string }
}
```

**D5. Persistencia en Engram fire-and-forget**: observación `type=config` con `project_ref`, `tool`, `names_applied`, `names_skipped`, `duration_ms`. **NUNCA el valor del secret**.

**D6. Telemetría vía engine heartbeat**:

```
report_heartbeat(event_type="supabase_mcp_call", payload={
  tool, success, duration_ms, project_ref, idempotency_hit
})
```

**D7. Redacción en logs**:
- Solo el **nombre** del secret puede aparecer en logs/evidence. El **valor** nunca, ni siquiera redactado parcialmente.
- El PAT se redacta igual que la API key de Stripe: `sbp_****<last6>` via `lib/safety.redact_log_line` (extender el regex existente en `specbox-stripe-mcp/src/specbox_stripe_mcp/lib/safety.py`, o duplicar en el nuevo paquete — ver §6).

**D8. Error codes estables** (herencia del vocabulario de `specbox-stripe`):
- `E_INVALID_TOKEN` — PAT malformado o rechazado por Supabase (401).
- `E_PROJECT_NOT_FOUND` — ref no existe o no accesible con el PAT (404).
- `E_INSUFFICIENT_PERMISSIONS` — PAT sin acceso al proyecto (403).
- `E_INVALID_INPUT` — nombres vacíos, valores no-string, etc.
- `E_RATE_LIMITED` — 429 tras retry exhausted.
- `E_CONFIRM_TOKEN_MISMATCH` — `unset_edge_secret` sin el token literal.
- `E_SUPABASE_ERROR` — cualquier otro error genérico de la API.

---

## 5. Contratos de tools (especificación completa)

### T1 — `set_edge_secret`

**Intent**: "Inyecta (crea o sobrescribe) uno o más secrets en las Edge Functions de este proyecto Supabase."

**Input schema**:

```json
{
  "type": "object",
  "required": ["supabase_access_token", "project_ref", "secrets"],
  "properties": {
    "supabase_access_token": {
      "type": "string",
      "pattern": "^sbp_[A-Za-z0-9_-]+$",
      "description": "Supabase Personal Access Token. Format sbp_*."
    },
    "project_ref": {
      "type": "string",
      "pattern": "^[a-z0-9]{20}$",
      "description": "Supabase project ref (20 lowercase alphanumeric). Ej: 'gjwqsehingipcqmngbso'."
    },
    "secrets": {
      "type": "object",
      "additionalProperties": { "type": "string" },
      "minProperties": 1,
      "description": "Map {NAME: value}. Names conventionally UPPER_SNAKE_CASE, values are strings."
    },
    "project_hint": {
      "type": "string",
      "description": "Free-form tag for evidence + telemetry (e.g. 'motofan'). Default: 'unknown'."
    }
  }
}
```

**Output schema** (success):

```json
{
  "success": true,
  "data": {
    "project_ref": "gjwqsehingipcqmngbso",
    "applied": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET_PLATFORM",
                "STRIPE_WEBHOOK_SECRET_CONNECT", "DEFAULT_APPLICATION_FEE_PERCENT"],
    "all_overwritten": false,
    "previously_present": ["STRIPE_SECRET_KEY"],
    "previously_absent": ["STRIPE_WEBHOOK_SECRET_PLATFORM",
                          "STRIPE_WEBHOOK_SECRET_CONNECT",
                          "DEFAULT_APPLICATION_FEE_PERCENT"]
  },
  "evidence": { "engram_observation_id": "obs_..." }
}
```

**Behavior**:

1. Validate input schema. On malformed PAT or project_ref → `E_INVALID_INPUT` before any HTTP.
2. Validate secret names: all keys must match `^[A-Z][A-Z0-9_]*$` (POSIX env var convention). Reject with `E_INVALID_INPUT` listing invalid names.
3. `GET https://api.supabase.com/v1/projects/{ref}/secrets` with `Authorization: Bearer {PAT}` to get existing names. This powers `idempotency_hit` detection and `previously_present` reporting.
4. `POST https://api.supabase.com/v1/projects/{ref}/secrets` with body `[{name, value}, ...]`. Supabase overwrites by name.
5. On success, extract `applied` = list of names posted. `all_overwritten` = `set(applied) ⊆ set(existing_before)`. `idempotency_hit` for heartbeat = `all_overwritten`.
6. Write Engram observation with `applied`, `project_ref`, `duration_ms`. Never log values.
7. Emit heartbeat.

**Errores específicos**:
- `E_INVALID_TOKEN` — 401 de Supabase.
- `E_PROJECT_NOT_FOUND` — 404 (distinguir de 403 por status code, no por mensaje).
- `E_INSUFFICIENT_PERMISSIONS` — 403.
- `E_RATE_LIMITED` — 429 tras 3 reintentos con backoff exponencial (0.5s, 1s, 2s).
- `E_INVALID_INPUT` — keys o values mal formados.

**Idempotencia garantizada**: misma input 10× → mismo estado final. `all_overwritten=true` a partir del 2º call.

**Seguridad crítica**:
- NUNCA loggear el mapa `secrets` completo.
- Engram observation content: solo los **nombres** (`applied: [...]`), nunca los valores.
- El PAT se redacta en logs con `sbp_****<last6>` via regex reutilizado de `specbox-stripe-mcp/src/specbox_stripe_mcp/lib/safety.py`.

---

### T2 — `list_edge_secrets`

**Intent**: "¿Qué secrets están hoy configurados en las Edge Functions de este proyecto?"

**Input schema**:

```json
{
  "type": "object",
  "required": ["supabase_access_token", "project_ref"],
  "properties": {
    "supabase_access_token": { "type": "string" },
    "project_ref": { "type": "string" },
    "expected_names": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Optional: if provided, response includes missing_names + extra_names for diff."
    },
    "project_hint": { "type": "string" }
  }
}
```

**Output schema**:

```json
{
  "success": true,
  "data": {
    "project_ref": "gjwqsehingipcqmngbso",
    "names": ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET_PLATFORM", "..."],
    "count": 4,
    "missing_names": [],
    "extra_names": ["SOMETHING_ELSE"],
    "last_updated_at": "2026-04-18T10:12:34Z"
  }
}
```

**Behavior**:

1. `GET /v1/projects/{ref}/secrets` with PAT.
2. Collect names + `updated_at` timestamps (values never returned by API — doc lo confirma).
3. If `expected_names` provided → compute `missing_names = expected - actual` and `extra_names = actual - expected`. Ambos ordenados alfabéticamente.
4. Read-only. Heartbeat con `idempotency_hit=true` siempre (no muta estado).

**Errores específicos**: mismos que T1 salvo que no hay `E_INVALID_INPUT` por valor (no hay values de entrada).

---

### T3 — `unset_edge_secret`

**Intent**: "Elimina uno o más secrets del proyecto Supabase."

**Input schema**:

```json
{
  "type": "object",
  "required": ["supabase_access_token", "project_ref", "names", "confirm_token"],
  "properties": {
    "supabase_access_token": { "type": "string" },
    "project_ref": { "type": "string" },
    "names": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1,
      "description": "Names of secrets to delete."
    },
    "confirm_token": {
      "type": "string",
      "const": "I understand this removes secrets from the Supabase project",
      "description": "Literal safety token."
    },
    "project_hint": { "type": "string" }
  }
}
```

**Output schema**:

```json
{
  "success": true,
  "data": {
    "project_ref": "gjwqsehingipcqmngbso",
    "deleted": ["OLD_SECRET_A", "OLD_SECRET_B"],
    "skipped": ["NEVER_EXISTED"],
    "before_count": 5,
    "after_count": 3
  }
}
```

**Behavior**:

1. Reject if `confirm_token` doesn't match literal → `E_CONFIRM_TOKEN_MISMATCH`.
2. `GET` to determine which `names` actually exist (populates `deleted` vs `skipped`).
3. `DELETE /v1/projects/{ref}/secrets` with body `[name, name, ...]`.
4. Engram observation pre-action with the exact list about to be deleted + project_ref. Posted BEFORE the DELETE for audit trail.
5. Heartbeat con `idempotency_hit=false` si `deleted` no está vacío, `true` si todo estaba en `skipped`.

**Safety**:
- Si el PAT resuelve a un proyecto distinto al esperado, el DELETE afecta al wrong project. No hay mitigación a nivel API — es responsabilidad del caller verificar `project_ref` antes de invocar.
- **Sin equivalente a live-mode de Stripe** porque Supabase no tiene modos. El `confirm_token` es el único gate.

**Errores específicos**: `E_CONFIRM_TOKEN_MISMATCH`, más los comunes de T1.

---

## 6. Arquitectura y empaquetado

### Decisión: MCP server separado `packages/specbox-supabase-mcp/`

Mismo razonamiento que `specbox-stripe`: separación clara de responsabilidades, evolución independiente, paridad con el resto de MCPs de SpecBox.

### Reutilización de código con `specbox-stripe-mcp`

Varias piezas son **idénticas**:
- Response envelope (`lib/response.py`).
- Engram writer (`lib/engram_writer.py`).
- Heartbeat (`lib/heartbeat.py`).
- Redacción de secrets (`lib/safety.py` — extender regex para `sbp_*`).
- Patrón de idempotency key stable (aunque no lo necesitamos porque la API de Supabase no pide Idempotency-Key header).

**Opciones de reuso**:

- **Opción A (simple, recomendada v1)**: copiar los 4 módulos `lib/` en el paquete nuevo. Cost: código duplicado. Benefit: cero acoplamiento entre paquetes, cada uno se puede publicar y versionar por separado.
- **Opción B (v2+)**: extraer `lib/` a un paquete común `specbox-mcp-core` que ambos importen. Cost: un tercer paquete que versionar. Benefit: fix de redacción/heartbeat se aplica a todos a la vez.

**Recomendación v1**: Opción A. Cuando salga un tercer MCP de SpecBox, promover a Opción B.

### Stack propuesto

Igual que `specbox-stripe`:

- **Runtime**: Python 3.11+ (alineado con el engine).
- **HTTP client**: `httpx` (ya usado en el engine y en `specbox-stripe`).
- **MCP framework**: `fastmcp>=0.4.0`.
- **Transport**: stdio en v1 (para Claude Code local); opcional HTTP streaming en v2 si hace falta remoto.
- **Build**: hatchling (igual que `specbox-stripe`).

### Estructura de carpetas

```
packages/specbox-supabase-mcp/
├── pyproject.toml
├── README.md
├── BACKLOG.md
├── .gitignore
├── src/
│   └── specbox_supabase_mcp/
│       ├── __init__.py
│       ├── __main__.py
│       ├── server.py                           ← FastMCP, registers 3 tools
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── set_edge_secret.py              (T1)
│       │   ├── list_edge_secrets.py            (T2)
│       │   └── unset_edge_secret.py            (T3)
│       └── lib/
│           ├── __init__.py
│           ├── supabase_client.py              ← httpx wrapper + retry + logging
│           ├── safety.py                       ← PAT validation + redaction (sbp_*)
│           ├── response.py                     ← envelope (copy from specbox-stripe)
│           ├── engram_writer.py                ← fire-and-forget (copy)
│           └── heartbeat.py                    ← telemetry (copy)
└── tests/
    ├── __init__.py
    ├── conftest.py                             ← sys.path injection for Python 3.14 (copy)
    ├── unit/
    │   ├── test_safety.py
    │   ├── test_response.py
    │   ├── test_heartbeat.py
    │   ├── test_supabase_client.py
    │   ├── test_set_edge_secret.py
    │   ├── test_list_edge_secrets.py
    │   ├── test_unset_edge_secret.py
    │   └── test_readme_tool_coverage.py
    └── integration/
        ├── README.md
        ├── conftest.py
        └── test_supabase_e2e.py                ← gated by SUPABASE_CI_ACCESS_TOKEN
```

### `lib/supabase_client.py` — contrato

Similar a `lib/stripe_client.py` de `specbox-stripe` pero sobre `httpx` en lugar de un SDK:

- `SupabaseClient(access_token, base_url="https://api.supabase.com")`
- `.call(op_name, method, path, json=None)` — wrapper con retry (RateLimitError → 429, connection error → transient). Emite `report_healing` en recovery exitoso, igual que `stripe_client`.
- Redacción automática del PAT en cualquier log line via `lib/safety.redact_log_line`.
- Timeout por call: 30 s.
- Retry backoff: 0.5s, 1s, 2s (MAX_RETRIES=3).

### Metadata conventions

A diferencia de Stripe, aquí **no escribimos metadata en Supabase** — el endpoint de secrets no acepta metadata. La "idempotencia" es pura: existence-by-name.

Lo que sí escribimos:
- **Engram observation** con `tool`, `project_ref`, `project_hint`, `names_applied`, `duration_ms`, `mode="cloud"` (placeholder para la futura distinción cloud/self-hosted).
- **Heartbeat** con `tool`, `success`, `duration_ms`, `project_ref`, `idempotency_hit`.

---

## 7. Integración con la skill `/stripe-connect`

### Cambios propuestos en la skill

Actualmente Paso 9.5 de `/stripe-connect` (referenciado en PRD de `specbox-stripe` §7) deja los 4 secrets listos en memoria de la skill. Añadir **Paso 9.5.4** concreto (ya estaba previsto en el PRD de `specbox-stripe`, ahora se instancia con este MCP):

```markdown
### 9.5.4 Inyectar secrets en Supabase Edge Functions

```
mcp__specbox-supabase__set_edge_secret({
  supabase_access_token: env.SUPABASE_ACCESS_TOKEN,
  project_ref: "<ref del proyecto del usuario>",
  secrets: {
    STRIPE_SECRET_KEY:              env.STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET_PLATFORM: <platform.secret de paso 9.5.2>,
    STRIPE_WEBHOOK_SECRET_CONNECT:  <connect.secret de paso 9.5.2>,
    DEFAULT_APPLICATION_FEE_PERCENT: "20"
  },
  project_hint: "motofan"
})
```

Si `success=false` con `error.code="E_INVALID_TOKEN"` → pedir al dev un PAT nuevo y retry.
Si `E_PROJECT_NOT_FOUND` → abortar con mensaje claro (project_ref mal).

### 9.5.5 Verificación final (sin cambios)

`mcp__specbox-stripe__get_setup_status(...)` → `verdict=ready`.
```

### Actualización del Paso 11 de la skill

Los "Siguientes pasos" pasan de **1 acción manual restante** (inyectar secrets) a **0 acciones manuales**:

```
✓ Stripe Connect: ACTIVO
✓ Webhooks: 2 creados (platform + connect)
✓ Catálogo: 3 products + 3 prices
✓ Secrets Supabase: 4 inyectados vía specbox-supabase MCP

Siguientes pasos:
  1. Ejecuta /plan UC-301 para arrancar frontend

(Cero pasos manuales en dashboard.)
```

### Variables de entorno nuevas que documenta la skill

El dev debe exportar, además de `STRIPE_SECRET_KEY`:

- `SUPABASE_ACCESS_TOKEN` — PAT de Supabase del usuario.
- Opcional: `SUPABASE_PROJECT_REF` si la skill quiere pre-rellenar el campo.

---

## 8. Telemetría, observabilidad, evidencia

### Engram observations (fire-and-forget)

Cada tool escribe al completarse con éxito:

```
type: config
title: "supabase-mcp: {tool_name} on {project_hint}"
content:
  **Tool**: {tool_name}
  **Project ref**: {project_ref}
  **Project hint**: {project_hint}
  **Names applied**: [N1, N2, ...]  ← NUNCA los valores
  **Names skipped**: [...]
  **Idempotency hit**: {bool}
  **Duration**: {ms}
```

### SpecBox engine heartbeats

```
report_heartbeat({
  event_type: "supabase_mcp_call",
  payload: {
    tool: "{tool_name}",
    success: bool,
    duration_ms: int,
    project_ref: "{ref}",
    idempotency_hit: bool,
    code: "OK" | "{error_code}"
  }
})
```

### Healing events

Retry exitoso tras 429 o connection error:

```
report_healing({
  project: "{project_hint}",
  agent: "specbox-supabase-mcp",
  hook: "{op_name}",
  root_cause: "rate_limit" | "connection_error",
  resolution: "retry"
})
```

---

## 9. Seguridad

### Amenazas y mitigaciones

| Amenaza | Mitigación |
|---|---|
| Leak del valor del secret en logs | Contrato estricto: nunca loggear `secrets[*]`, solo `list(secrets.keys())`. Unit test que verifica ausencia del valor en observaciones. |
| Leak del PAT en logs | Redacción regex `sbp_[A-Za-z0-9_-]+` → `sbp_****<last6>` en `lib/safety.redact_log_line`. |
| Teardown accidental de secrets críticos | `confirm_token` literal obligatorio en `unset_edge_secret`. Evidencia pre-action en Engram con IDs a borrar. |
| `project_ref` incorrecto (dev teclea mal) | Regex `^[a-z0-9]{20}$` captura typos obvios. Para el resto: responsabilidad del caller. Docs explícitas en README. |
| PAT con demasiado scope (acceso a otros proyectos del user) | Supabase no permite PATs por-proyecto. Workaround: documentar en README que el dev debería tener un PAT de "service-account-like" user con acceso solo a los proyectos relevantes. |
| Race condition en secrets concurrentes | La API de Supabase no expone Idempotency-Key. Dos POSTs concurrentes al mismo ref con el mismo nombre: uno gana (last-write-wins). Aceptable — los secrets son idempotentes por naturaleza (mismo valor produce mismo resultado). |
| Attacker con RCE en el host del MCP lee el PAT en memoria | Fuera de alcance — mismo threat model que `specbox-stripe`. Mitigación: no persistir PATs en disco; solo en memoria per call. |

### Datos sensibles persistidos

- **Engram**: solo nombres + timestamps + project_ref. **Cero valores** de secrets. **Cero PAT**.
- **Response JSON**: `data.applied` y `data.names` contienen nombres; `error.message` puede contener mensaje de Supabase que hay que redactar (el cliente hace `safety.redact_log_line` sobre `exc` antes de meterlo en `error.message`).
- **Caller responsibility**: los valores que el caller pasa en `secrets` viajan a Supabase y se descartan del proceso del MCP inmediatamente tras el POST. Caller decide qué hacer con sus copias locales.

---

## 10. Rollout y versionado

### Fases propuestas

- **v0.1 — Alpha interno**: T1 + T2 + T3. Integrado con `/stripe-connect` en moto.fan para validar end-to-end.
- **v0.5 — Beta cross-project**: habilitar en 2-3 proyectos más (candidatos: otros que consuman `/stripe-connect`).
- **v1.0 — GA**: docs públicas, tool search, versionado semver congelado.
- **v1.1**: alias store para PATs (v2 secret resolution); soporte self-hosted Supabase (detect via base_url parameter).
- **v2.0**: OAuth si Supabase lo expone para dev tooling; extraer `lib/*` a `specbox-mcp-core`.

### Versionado

- **Supabase Management API version**: actualmente no versionada públicamente (no hay `v2` disponible). Pinear al path `/v1/*` y monitorear depreciaciones vía changelog de Supabase.
- **MCP version**: semver. Breaking changes en output schema → major. Nuevas tools → minor. Fixes → patch.

### Compatibilidad con la skill

La skill `/stripe-connect` actual funciona SIN `specbox-supabase` MCP (fallback a paso manual de dashboard). Con el MCP, Paso 9.5.4 se ejecuta; sin él, skill muestra instrucciones manuales. **Zero breaking change** al añadir.

---

## 11. Métricas de éxito

### DX metrics

- **Acciones manuales restantes tras `/stripe-connect`**: baseline 1 (copiar 4 secrets), target v1 **0**.
- **Tiempo desde `/stripe-connect` hasta `/plan UC-301`**: baseline ~5 min (con secrets manuales), target v1 **< 30 s**.
- **Tasa de fallos en primera ejecución**: baseline ~10% (typos en copy/paste), target v1 **< 1%**.

### Adoption metrics

- Nº de proyectos que invocan `mcp__specbox-supabase__*` por mes.
- Ratio `set_edge_secret` : `list_edge_secrets` (funnel: list debería ser mayoría tras v1.1 si las skills lo usan para health-check preventivo).

### Reliability metrics

- % éxito por tool (target > 99.5% — la API de Supabase es estable).
- Latency p95 (target < 1.5 s excluyendo latencia variable del DC).
- Incidentes de leak de secret (target **0**, zero-tolerance).

---

## 12. Dependencias y riesgos

### Dependencias duras

- **D-1**: Supabase Management API estable en `/v1/*`. Si Supabase deprecia o cambia breaking, el paquete se rompe. Mitigación: pinear path, monitorear changelog, integration test CI semanal.
- **D-2**: `fastmcp>=0.4.0` y `httpx>=0.27.0`. Mismas dependencias que `specbox-stripe`; ya en ecosystem.

### Dependencias blandas

- **D-3**: El MCP oficial de Supabase no añade `set_edge_secret` en el futuro próximo. Probabilidad: baja-media — el issue #120 lleva meses abierto. Mitigación: si pasa, refactorizar como wrapper delgado sobre el MCP oficial; los contratos de tools se mantienen.

### Riesgos

| Riesgo | Impacto | Prob. | Mitigación |
|---|---|---|---|
| Supabase cambia el shape del response (añade/quita campos) | Tool devuelve data parcial pero no rompe | Baja | Parsear defensivo: `.get("name", "")` en vez de `["name"]` |
| PAT rotation no se entera el MCP | Todos los calls 401 | Media | Mensaje claro en `E_INVALID_TOKEN` con link a docs de rotación |
| Supabase baja el rate limit de 120 req/min | Tools fallan intermitente | Baja | Retry backoff ya cubre. Si se generaliza, migrar a 429-aware queue |
| Dev pasa un `project_ref` de otro usuario suyo por error | MCP inyecta secrets en proyecto incorrecto | Media | Ningún control automático viable. Docs explícitas: "verifica el ref antes de invocar" |
| Conflict con `mcp__supabase` oficial si lo añaden más tarde | Namespace colision | Baja | Este es `specbox-supabase`, claramente distinto; namespaces MCP están por server name |

---

## 13. Testing strategy

### Unit tests (mockeados)

- Por tool, mock de `httpx.Client`, verificar:
  - Validación input schema (PAT format, project_ref format, names format, values tipo string).
  - Construction del request correcto (path, method, headers, body).
  - Parsing del response.
  - Idempotency detection (`all_overwritten` calculation).
  - `confirm_token` enforcement en `unset_edge_secret`.
  - Redacción de PAT en logs.
  - Cero aparición del valor del secret en observaciones Engram.
- `lib/supabase_client.py`: retry en 429, en connection error; non-retryable en 401/403/404.
- `lib/safety.py`: redact_log_line para PAT + heredado para sk_/whsec_.

### Integration tests

- **Gated by `SUPABASE_CI_ACCESS_TOKEN` + `SUPABASE_CI_PROJECT_REF`**. Sin esas env vars → tests skipped.
- Un proyecto Supabase dedicado al CI (nunca un proyecto compartido).
- Matriz:
  - T1: first-run (secret no existe) → crea; second-run (existe) → sobrescribe + `idempotency_hit=true`.
  - T2: list vacía, list con N secrets, list con `expected_names` diff.
  - T3: delete existente, delete inexistente (skipped), confirm_token mal.
- Autouse fixture `supabase_teardown` que borra todos los secrets `SPECBOX_CI_*` antes y después de cada test.

### E2E desde skill

- Ejecutar skill `/stripe-connect` completa contra proyecto demo con Supabase real.
- Verificar al final: `list_edge_secrets(expected_names=["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET_PLATFORM", "STRIPE_WEBHOOK_SECRET_CONNECT", "DEFAULT_APPLICATION_FEE_PERCENT"])` → `missing_names=[]`.
- Una Edge Function de test deployed que `Deno.env.get("STRIPE_SECRET_KEY")` y devuelve 200 si está presente.

### Coverage gate

- `pyproject.toml` con `fail_under = 85` (mismo target que `specbox-stripe`). Omit `server.py` y `__main__.py` (wiring-only).

---

## 14. Open questions

1. **¿Debería el MCP soportar `PATCH` individual de un secret?** La doc oficial solo documenta bulk POST/DELETE. Confirmar vía OpenAPI spec si existe y si hay endpoint individual. **Acción**: skipear v1; bulk POST cubre el caso.
2. **¿El PAT puede scope-se a un solo proyecto?** Research dice "global del usuario". Si Supabase añade scoped PATs (tipo GitHub fine-grained PAT), refactorizar `v1.1` para exponer "required scope" como warning preventivo.
3. **¿Auto-instalación del paquete al ejecutar `/stripe-connect`?** La skill podría detectar ausencia del MCP e instalarlo. Decisión: **no en v1**. Setup manual + docs claras.
4. **¿Soportamos self-hosted Supabase?** El cloud endpoint es `api.supabase.com`. Self-hosted tiene su propia Management API con base distinto. **Acción v1**: parámetro `base_url` opcional (default `https://api.supabase.com`), pero sin tests contra self-hosted hasta que haya demanda.
5. **Localización de mensajes de error**: ES/EN. Default EN, con `locale` opcional en input (paridad con `specbox-stripe`).

---

## 15. Appendix — Estado actual (caso moto.fan 2026-04-17)

### Lo que ya está automatizado (commit `372da9f`)

- Migración + Edge Functions deployadas vía `mcp__supabase` oficial ✅
- Connect probado vía `verify_connect_enabled` ✅
- 2 webhooks creados vía `setup_webhook_endpoints` ✅ (IDs guardados en memoria de la skill)
- 3 products + 3 prices creados vía `setup_products_and_prices` ✅

### Lo que este PRD elimina

- Paso manual: copiar 4 secrets en `dashboard.supabase.com/project/gjwqsehingipcqmngbso/settings/functions` → **eliminado** via `set_edge_secret`.

### Secrets que inyectar en moto.fan (copy-paste ready para integración inicial)

```json
{
  "supabase_access_token": "$SUPABASE_ACCESS_TOKEN",
  "project_ref": "gjwqsehingipcqmngbso",
  "secrets": {
    "STRIPE_SECRET_KEY": "$STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET_PLATFORM": "<from setup_webhook_endpoints output>",
    "STRIPE_WEBHOOK_SECRET_CONNECT":  "<from setup_webhook_endpoints output>",
    "DEFAULT_APPLICATION_FEE_PERCENT": "20"
  },
  "project_hint": "motofan"
}
```

---

## 16. Apéndice — Checklist para el executor del PRD en SpecBox

Cuando SpecBox descomponga este PRD (similar al de `specbox-stripe`):

- [ ] Crear US-SPECBOX-SUPABASE en el board del engine (FreeForm `ff-*`)
- [ ] UC-1: `set_edge_secret` (T1) — **MVP H1**
- [ ] UC-2: `list_edge_secrets` (T2) — **MVP H1**
- [ ] UC-3: `unset_edge_secret` (T3) — **MVP H1**
- [ ] UC-4: telemetría transversal (Engram + heartbeats + healing + redacción PAT) — **H1** (reutilizar código de `specbox-stripe`)
- [ ] UC-5: tests unit + integration suite contra cuenta Supabase CI — **H1** (target 85% coverage)
- [ ] UC-6: README + docs públicas + CLAUDE.md engine addendum — **H1**
- [ ] UC-7: **Integración con skill `/stripe-connect` Paso 9.5.4** — **H1**, desbloquea el UC-7 pendiente en `specbox-stripe-mcp` (ver BACKLOG.md de ese paquete)
- [ ] UC-8: soporte self-hosted (`base_url` param) — **H2 v1.1**
- [ ] UC-9: alias store para PATs — **H2 v1.1**

**Prioridad crítica**: UC-1 + UC-7 desbloquean cierre end-to-end del flujo de `/stripe-connect` en moto.fan. El resto se puede iterar post-H1.

**Dependencias externas**: ninguna. Este PRD **no depende** de ningún otro PRD pendiente. Puede arrancar inmediatamente.
