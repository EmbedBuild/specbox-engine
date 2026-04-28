# Plan: US-STRIPE-MCP-V2 — Desacoplar Connect del specbox-stripe-mcp (v0.2)

> Generado: 2026-04-28
> Origen: FreeForm board `ff-bc73b5d69f91` (specbox-engine-stripe)
> Estado: Pendiente
> Horas estimadas: 16h (5 UCs)
> Versión objetivo del paquete: `specbox-stripe-mcp` v0.2.0

---

## Resumen

Refactor del paquete `packages/specbox-stripe-mcp/` para que sus tools soporten
cuentas Stripe **Standard** (no-Connect) como first-class citizen. Hoy todas
las tools asumen Connect. v0.2 introduce `account_mode: Literal["standard", "connect"]`
como discriminador, mantiene backward-compat con calls existentes, y sienta la
base para US-STRIPE-STANDARD (skill `/stripe-standard`) y US-STRIPE-SWITCH-ACCOUNT.

**No hay UI** — backend puro Python. Sin pantallas, sin VEG, sin Stitch.

---

## Análisis de impacto en código actual

Tras leer el código del paquete, los puntos de acoplamiento a Connect son tres
y están bien aislados:

| Archivo | Acoplamiento actual | Cambio en v0.2 |
|---------|---------------------|-----------------|
| `tools/verify_connect_enabled.py` | Canary create+delete de cuenta Express obligatorio | Nuevo `verify_account_setup(account_mode)`. En `standard` solo `GET /v1/account`. Antiguo nombre queda como alias deprecated. |
| `tools/setup_webhook_endpoints.py` | Param `connect_events: list[str]` no-opcional, crea siempre 2 endpoints | `account_mode='standard'` → 1 endpoint, `connect_events`/`connect_url` rechazados si se pasan. `account_mode='connect'` → comportamiento actual idéntico. |
| `tools/get_setup_status.py` | Valida 4 cosas (key, webhook_platform, webhook_connect, products, connect_enabled) | Modal-aware: en `standard` valida solo 3 (key, webhook_platform, products). Sin `webhook_connect` ni `connect_enabled`. |
| `tools/setup_products_and_prices.py` | **Ya es agnóstico** — no menciona Connect | Sin cambios |

Helpers en `lib/` (`safety`, `idempotency`, `response`, `stripe_client`,
`engram_writer`, `heartbeat`) son agnósticos. **No tocar**.

---

## Decisión clave: `account_mode` como discriminador, no flag opcional

Alternativas consideradas:

| Opción | Por qué descartada |
|--------|---------------------|
| `is_connect: bool = True` flag | Confunde al lector: ¿qué default? Booleanos no escalan si añadimos modos futuros. |
| Tools separadas (`setup_webhook_endpoints_standard` vs `..._connect`) | Duplica código de idempotencia, validación, telemetría. Rompe el patrón actual. |
| `account_mode: Literal["standard", "connect"]` requerido | **Elegida**. Explícito, type-safe, extensible (futuro `"custom"`/`"express"` granular). Force al caller a decidir conscientemente. |

Backward-compat: todas las tools v0.1 que reciban llamadas sin `account_mode`
asumirán `"connect"` (con `DeprecationWarning`) hasta v0.3 que lo hará error.

---

## Fases de Implementación

### Fase 1: Núcleo del refactor — UC-001 (3h)

**Archivo principal**: `tools/verify_connect_enabled.py` → renombrar a `verify_account_setup.py`

- [ ] Crear `tools/verify_account_setup.py` con la nueva firma:
  ```python
  def verify_account_setup(
      *,
      stripe_api_key: str,
      account_mode: Literal["standard", "connect"],
      project_hint: str = "unknown",
      skip_canary: bool = False,
      allow_live_mode: bool = False,
      live_mode_confirm_token: str | None = None,
  ) -> dict[str, Any]
  ```
- [ ] Implementar branch `mode == "standard"`:
  - `GET /v1/account` (Stripe SDK: `stripe.Account.retrieve()`)
  - Si OK → devolver `{enabled: true, platform_account_id, capabilities, mode: "standard"}`
  - Si fallo de permisos (key restricted) → `E_INSUFFICIENT_PERMISSIONS` con remediation
- [ ] Implementar branch `mode == "connect"`:
  - Mover la lógica actual de canary (líneas ~30-150 del fichero original)
  - Devolver el mismo shape v0.1 pero añadiendo `mode: "connect"` en data
- [ ] Validar `account_mode` no válido → `E_INVALID_ARGUMENT` con mensaje listando los 2 valores
- [ ] Mantener `tools/verify_connect_enabled.py` como **shim deprecated**:
  ```python
  def verify_connect_enabled(**kwargs) -> dict[str, Any]:
      warnings.warn(
          "verify_connect_enabled is deprecated. Use verify_account_setup(account_mode='connect').",
          DeprecationWarning,
          stacklevel=2,
      )
      return verify_account_setup(account_mode="connect", **kwargs)
  ```
- [ ] Registrar nueva tool en `server.py` (`@mcp.tool()`)
- [ ] Mantener registro de la antigua para no romper clientes existentes

**Cubre AC**: UC-001 AC-01 a AC-07.

**Tiempo estimado**: 3h.

---

### Fase 2: Webhooks modal-aware — UC-002 (4h)

**Archivo**: `tools/setup_webhook_endpoints.py`

- [ ] Cambiar firma para añadir `account_mode` como kwarg requerido:
  ```python
  def setup_webhook_endpoints(
      *,
      stripe_api_key: str,
      account_mode: Literal["standard", "connect"],
      platform_url: str,
      platform_events: list[str],
      connect_events: list[str] | None = None,   # opcional ahora
      connect_url: str | None = None,
      api_version: str | None = None,
      project_hint: str = "unknown",
      description_prefix: str | None = None,
      allow_live_mode: bool = False,
      live_mode_confirm_token: str | None = None,
  ) -> dict[str, Any]
  ```
- [ ] Validación de args por modo (helper `_validate_mode_args(account_mode, connect_events, connect_url)`):
  - `mode='standard'` + `connect_events not None` → `E_INVALID_ARGUMENT("connect_events solo aplica a mode='connect'")`
  - `mode='standard'` + `connect_url not None` → `E_INVALID_ARGUMENT` análogo
  - `mode='connect'` + `connect_events is None or []` → `E_MISSING_ARGUMENT("connect_events requerido en mode='connect'")`
- [ ] Branch `mode == "standard"`:
  - Reconciliar 1 solo endpoint con `connect=False`
  - Guardar `metadata.specbox_account_mode = "standard"` en el endpoint
  - Devolver envelope `{data: {platform: {...}}}` SIN `data.connect`
- [ ] Branch `mode == "connect"`:
  - Mantener lógica actual (líneas 100-200): reconciliar platform + connect
  - Añadir `metadata.specbox_account_mode = "connect"` en ambos endpoints
  - Shape de respuesta idéntico a v0.1
- [ ] **Migración silenciosa de endpoints v0.1**:
  - Si encuentra un endpoint `specbox_managed=true` SIN `specbox_account_mode`, asumir `connect` por defecto y anotar `metadata.specbox_account_mode = "connect"` en el primer reuse
  - Si en `mode='standard'` se reutiliza un endpoint v0.1, anotar `mode='standard'` (re-clasificación)
- [ ] Idempotencia preservada en ambos modos:
  - Idempotency-key incluye `account_mode` para evitar colisiones cross-mode
  - Lookup por `metadata.specbox_managed='true' + url + connect_flag + account_mode`

**Cubre AC**: UC-002 AC-01 a AC-08.

**Tiempo estimado**: 4h.

---

### Fase 3: Status modal-aware — UC-003 (3h)

**Archivo**: `tools/get_setup_status.py`

- [ ] Cambiar firma para incluir `account_mode`:
  ```python
  def get_setup_status(
      *,
      stripe_api_key: str,
      account_mode: Literal["standard", "connect"],
      expected_webhook_url: str | None = None,
      expected_tier_keys: list[str] | None = None,
      expected_platform_events: list[str] | None = None,
      expected_connect_events: list[str] | None = None,
      project_hint: str = "unknown",
      allow_live_mode: bool = False,
      live_mode_confirm_token: str | None = None,
  ) -> dict[str, Any]
  ```
- [ ] Refactor del `checks` builder para que sea condicional al modo:
  ```python
  checks: dict[str, CheckResult] = {
      "key": _check_key(stripe_api_key),
      "webhook_platform": _check_webhook_platform(...),
      "products": _check_products(...),
  }
  if account_mode == "connect":
      checks["webhook_connect"] = _check_webhook_connect(...)
      checks["connect_enabled"] = _check_connect_enabled(...)
  ```
- [ ] `verdict` se calcula sobre los checks aplicables al modo:
  - `ready`: todos los checks aplicables `pass`
  - `partial`: al menos uno `pass` y al menos uno `fail`
  - `not_setup`: ninguno `pass`
- [ ] `remediation_steps` modal-aware:
  - En `standard` nunca menciona "activate Connect"
  - En `connect` mantiene el mensaje actual cuando `connect_enabled=fail`
- [ ] `expected_connect_events` ignorado (con warning en logs) si `mode='standard'`

**Cubre AC**: UC-003 AC-01 a AC-07.

**Tiempo estimado**: 3h.

---

### Fase 4: Tests unitarios — distribuidos en UC-001/002/003 (incluidos en sus 10h)

**Archivos**:
- `tests/unit/test_verify_account_setup.py` (nuevo)
- `tests/unit/test_verify_connect_enabled.py` (existente — ahora cubre el shim deprecated + DeprecationWarning)
- `tests/unit/test_setup_webhook_endpoints.py` (extender)
- `tests/unit/test_get_setup_status.py` (extender)

Casos a cubrir por archivo:

#### `test_verify_account_setup.py`
- `test_standard_mode_returns_capabilities_no_canary` — mock GET /v1/account, asserts no Account.create
- `test_connect_mode_runs_canary_and_deletes` — mock POST /v1/accounts + DELETE
- `test_invalid_account_mode_returns_error` — assert `E_INVALID_ARGUMENT`
- `test_standard_mode_with_restricted_key` — mock 401/403, assert `E_INSUFFICIENT_PERMISSIONS`
- `test_response_includes_mode_field` — verify `data.mode in ('standard', 'connect')`

#### `test_verify_connect_enabled.py` (extender)
- `test_alias_emits_deprecation_warning` — `pytest.warns(DeprecationWarning)`
- `test_alias_returns_same_shape_as_v01` — call alias, compare keys

#### `test_setup_webhook_endpoints.py` (extender)
- `test_standard_mode_creates_one_endpoint` — assert single endpoint, `data.connect` ausente
- `test_standard_mode_rejects_connect_events` — `E_INVALID_ARGUMENT`
- `test_standard_mode_rejects_connect_url` — `E_INVALID_ARGUMENT`
- `test_connect_mode_requires_connect_events` — `E_MISSING_ARGUMENT`
- `test_idempotency_within_same_mode` — 2nd call returns `reused`
- `test_idempotency_cross_mode_no_collision` — `mode='standard'` no reusa endpoint `mode='connect'`
- `test_silent_migration_v01_endpoint` — endpoint sin `specbox_account_mode` se anota correctamente

#### `test_get_setup_status.py` (extender)
- `test_standard_mode_excludes_connect_checks` — assert keys `webhook_connect` y `connect_enabled` ausentes
- `test_standard_mode_verdict_ready` — 3 checks pass
- `test_standard_mode_verdict_partial` — webhook fail
- `test_standard_mode_verdict_not_setup` — todos fail
- `test_remediation_no_connect_in_standard` — assert "Connect" no aparece en mensajes

**Cubre AC**: UC-001 AC-06, UC-002 AC-07, UC-003 AC-07.

**Tiempo estimado**: incluido en las horas de cada UC (ya contadas).

---

### Fase 5: Tests de integración — UC-004 (3h)

**Archivo**: `tests/integration/test_mvp_end_to_end.py` (extender)

Tests gated por `STRIPE_CI_SECRET_KEY` (test mode):

- [ ] `test_flow_standard`:
  ```python
  verify_account_setup(mode='standard')           # → enabled=true
  setup_webhook_endpoints(mode='standard', ...)   # → 1 endpoint
  setup_products_and_prices(...)                  # → catálogo
  get_setup_status(mode='standard')               # → verdict='ready'
  ```
- [ ] `test_flow_connect`: mismo flujo con `mode='connect'`, verdict='ready'
- [ ] `test_idempotency_standard`: corre flow_standard 2 veces, asserts `created_or_reused='reused'` en la 2da
- [ ] `test_mode_isolation`: crea standard, luego connect, verify ambos `verdict='ready'` independientes
- [ ] Extender `conftest.py` teardown fixture para borrar endpoints **de ambos modos** (filtrar por `metadata.specbox_managed='true'` ignora mode)
- [ ] Coverage de integración objetivo `>= 90%` con ambos modos sumados (medir con `pytest-cov`)

**Cubre AC**: UC-004 AC-01 a AC-06 + UC-002 AC-08.

**Tiempo estimado**: 3h.

---

### Fase 6: Release artifacts — UC-005 (3h)

- [ ] **`pyproject.toml`**: bump `version = "0.2.0"`
- [ ] **`README.md`** (`packages/specbox-stripe-mcp/README.md`):
  - Nueva sección "Account modes" con ejemplo lado-a-lado:
    ```python
    # Standard (SaaS, e-commerce, B2B)
    setup_webhook_endpoints(
        account_mode="standard",
        platform_url="https://app.example.com/api/stripe-webhook",
        platform_events=["customer.subscription.updated", "invoice.paid"],
    )

    # Connect (marketplace)
    setup_webhook_endpoints(
        account_mode="connect",
        platform_url="https://app.example.com/api/stripe-webhook",
        platform_events=["account.updated"],
        connect_events=["customer.subscription.created", "invoice.paid"],
    )
    ```
  - Actualizar tabla de tools con columna **"Modes supported"** (`standard`, `connect`, o `both`)
- [ ] **`CHANGELOG.md`** entry v0.2.0:
  - **Breaking**: `verify_connect_enabled` deprecated (alias preservado hasta v0.3)
  - **Breaking**: `account_mode` es kwarg requerido en setup_webhook_endpoints y get_setup_status (default temporal `"connect"` con warning)
  - **New**: Soporte first-class para cuentas Stripe Standard
  - **Migration guide**: cambios mínimos para clientes v0.1 (añadir `account_mode="connect"` a sus calls)
- [ ] **`doc/prd/specbox_stripe_mcp_prd.md`** del repo del engine: añadir sección "Account modes" tras §5
- [ ] **`packages/specbox-stripe-mcp/BACKLOG.md`**: mover entry "alias-store/OAuth v2" de **H3 → H2** (US-STRIPE-SWITCH-ACCOUNT lo necesita como dependencia)
- [ ] Git tag `specbox-stripe-mcp-v0.2.0` + commit firmado en `main` (signing por hook existente)

**Cubre AC**: UC-005 AC-01 a AC-07.

**Tiempo estimado**: 3h.

---

## Componentes UI Requeridos

**N/A** — esta US es backend puro. Sin pantallas, sin VEG, sin Stitch.

---

## Archivos a Crear/Modificar

```
packages/specbox-stripe-mcp/
├── pyproject.toml                                          [MOD] version 0.2.0
├── README.md                                               [MOD] sección Account modes
├── CHANGELOG.md                                            [MOD] entry v0.2.0
├── BACKLOG.md                                              [MOD] H3→H2 alias store
├── src/specbox_stripe_mcp/
│   ├── server.py                                           [MOD] registrar verify_account_setup
│   └── tools/
│       ├── verify_account_setup.py                         [NEW] tool nueva
│       ├── verify_connect_enabled.py                       [MOD] shim deprecated
│       ├── setup_webhook_endpoints.py                      [MOD] account_mode + validación
│       └── get_setup_status.py                             [MOD] checks condicionales
└── tests/
    ├── unit/
    │   ├── test_verify_account_setup.py                    [NEW]
    │   ├── test_verify_connect_enabled.py                  [MOD] tests deprecación
    │   ├── test_setup_webhook_endpoints.py                 [MOD] tests modos
    │   └── test_get_setup_status.py                        [MOD] tests modal-aware
    └── integration/
        ├── conftest.py                                     [MOD] teardown ambos modos
        └── test_mvp_end_to_end.py                          [MOD] flow_standard + isolation

doc/
├── prd/specbox_stripe_mcp_prd.md                           [MOD] sección Account modes
└── plans/stripe_mcp_v2_plan.md                             [NEW] este plan
```

**Total**: 4 archivos nuevos, 11 modificados.

---

## Comandos finales

```bash
# Lint + tests unit
cd packages/specbox-stripe-mcp
uv run ruff check src tests
uv run mypy src
uv run pytest tests/unit -v --cov=src --cov-report=term-missing

# Tests integración (requiere STRIPE_CI_SECRET_KEY exportado)
STRIPE_CI_SECRET_KEY=sk_test_... uv run pytest tests/integration -v

# Build + tag
uv build
git tag -s specbox-stripe-mcp-v0.2.0 -m "specbox-stripe-mcp v0.2.0 — account modes"
git push origin specbox-stripe-mcp-v0.2.0
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|----------------|------------------------|-------|
| Discriminador de modo | `account_mode: Literal[...]` requerido | `is_connect: bool = True` flag | Type-safe, extensible a más modos en futuro, fuerza decisión consciente |
| Backward-compat | Shim deprecated `verify_connect_enabled` con warning | Romper hard en v0.2 | Permite migración gradual de clientes v0.1; warning empuja al cambio |
| Endpoints v0.1 sin `account_mode` | Migración silenciosa al primer reuse | Forzar reset/recreate | No interrumpe sistemas en producción; coste mínimo (1 metadata write) |
| Idempotency cross-mode | Incluir `account_mode` en idempotency-key | Idempotency global | Evita que `mode='standard'` reuse endpoint creado por `mode='connect'` con eventos distintos |
| Pruebas de integración | Gated por `STRIPE_CI_SECRET_KEY` (1 cuenta test) | 2 cuentas test separadas | UC-004 AC-04 dice "misma cuenta test" — verifica isolation por metadata, no por cuenta |

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Cliente v0.1 (skill `/stripe-connect`) rompe al actualizar a v0.2 | Media | Alto | Shim deprecated mantiene shape; CHANGELOG con migration guide; tests cubren alias |
| Endpoints v0.1 ya en producción no migran limpiamente | Baja | Medio | Migración silenciosa testeada (UC-002 AC-06); fallback: si metadata write falla, asumir `connect` |
| Tests integración costosos en cuenta test compartida | Baja | Bajo | Teardown fixture limpia ambos modos; tests gated por env var (no corren en CI sin opt-in) |
| Stripe rate-limit en flow_isolation (4 webhooks creados/borrados) | Baja | Bajo | Tests con backoff exponencial (ya existe en `stripe_client.py`) |

---

## Definition of Done

- [ ] Los 5 UCs marcados como `done` en SpecBox (37 ACs verdes)
- [ ] `pytest tests/unit` verde con coverage `>= 90%` (mantenemos baseline v0.1 = 88%)
- [ ] `pytest tests/integration` verde con `STRIPE_CI_SECRET_KEY` configurado
- [ ] `ruff check` y `mypy` sin errores
- [ ] `uv build` produce wheel publicable
- [ ] Git tag `specbox-stripe-mcp-v0.2.0` empujado a origin
- [ ] CHANGELOG con migration guide visible
- [ ] Skill `/stripe-connect` (consumer) probado contra v0.2 sin cambios (si rompe → bug en backward-compat)

---

## Siguientes pasos

1. **Lanzar `/implement`** sobre este plan con `find_next_uc` (debería empezar por UC-001).
2. Tras release v0.2.0 publicada → **planificar US-STRIPE-STANDARD** (skill `/stripe-standard`, dependencia directa de `account_mode`).
3. Tras `/stripe-standard` → **planificar US-STRIPE-SWITCH-ACCOUNT** (necesita alias store que UC-005 mueve a H2 del backlog del MCP).

---

## Referencias

- US: `ff-bc73b5d69f91` / US-STRIPE-MCP-V2 (5 UCs, 37 ACs)
- Código actual del paquete: [packages/specbox-stripe-mcp/](../packages/specbox-stripe-mcp/)
- PRD original del MCP: [doc/prd/specbox_stripe_mcp_prd.md](../prd/specbox_stripe_mcp_prd.md)
- BACKLOG H3 alias-store: [packages/specbox-stripe-mcp/BACKLOG.md](../packages/specbox-stripe-mcp/BACKLOG.md)
- US dependientes: US-STRIPE-STANDARD, US-STRIPE-SWITCH-ACCOUNT (mismo board)
