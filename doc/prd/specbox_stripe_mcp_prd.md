# PRD — `specbox-stripe` MCP

**Status**: Draft v1
**Author**: Claude (opus-4-7, via moto.fan session 2026-04-17)
**Target executor**: SpecBox Engine team
**Related skills**: `/stripe-connect`, `/manual-test`, `/stripe` (future v2 SaaS variant)
**Sibling gap**: `specbox-supabase` MCP — `set_edge_secret` tool (tracked separately, same root cause)

---

## 1. Motivación y problema

SpecBox ha cerrado la brecha spec ↔ code ↔ UI ↔ tests con sus MCPs verticales (Supabase, Trello, Stitch, Engram). Queda **una brecha crítica sin cerrar**: la infraestructura de pagos.

### El caso real que disparó este PRD

Durante la ejecución de la skill `/stripe-connect` en el proyecto **moto.fan** (2026-04-17):

1. La skill generó correctamente 5 Edge Functions + migración DB vía `mcp__supabase__apply_migration` + `deploy_edge_function`. **Todo el backend quedó desplegado sin tocar CLI**.
2. Al llegar al paso "hazlo operativo" aparecieron **4 acciones manuales bloqueantes** que el agente NO pudo ejecutar:
   - Activar Stripe Connect en la cuenta (1 click en dashboard — no hay API)
   - Crear 2 webhook endpoints con los eventos correctos (manual en dashboard)
   - Crear Products + Prices con metadata `tier` coherente (tediosamente manual)
   - Setear 4 secrets en Supabase Edge Functions (no hay endpoint MCP para secrets)
3. El Stripe MCP oficial (`https://mcp.stripe.com/v1`) **no expone** los endpoints de setup:
   - `POST /v1/webhook_endpoints` — no está
   - `POST /v1/accounts` (Connect) — no está
   - `GET /v1/accounts/{id}` (verificación) — no está
   - Solo expone operaciones runtime de negocio: coupons, prices, products, payment_links, promotion_codes, refunds, customers, invoices, subscriptions.
4. Consecuencia: **fricción de contexto** entre el agente (que ya tiene toda la info) y el developer (que tiene que traducirla a clicks en dashboards). El flujo se rompe justo cuando la automatización era más valiosa.

### Por qué el Stripe MCP oficial no cierra esta brecha

El Stripe MCP oficial está diseñado para **conversaciones de negocio en runtime**:
> *"Crea un reembolso para esta factura", "cancela la suscripción de este cliente", "muéstrame los pagos fallidos del mes"*

No está diseñado para **setup-as-code de infraestructura**. Eso es exactamente el terreno de SpecBox.

### Por qué tiene sentido que SpecBox lo llene

SpecBox ya es la capa que orquesta infra declarativa para proyectos: plantillas de tablas, RLS, Edge Functions, Trello boards, Stitch designs. Un MCP de **setup-as-code para Stripe** encaja perfectamente en ese eje. Complementa al Stripe MCP oficial: **SpecBox-Stripe monta la pista; Stripe MCP oficial corre sobre ella**.

---

## 2. Objetivos y no-objetivos

### Objetivos (v1)

- **O1**. Permitir que una skill SpecBox (empezando por `/stripe-connect`) deje un proyecto **operativo end-to-end** sin intervención manual del developer (excepto el único click inevitable: activar Connect).
- **O2**. Ofrecer operaciones de setup **idempotentes** — ejecutar la skill dos veces no duplica recursos ni rompe nada.
- **O3**. Ofrecer un `get_setup_status` que cualquier skill pueda llamar al arrancar para decidir si hace setup o skip.
- **O4**. Seguir la estética SpecBox: `test_mode` por defecto, safeguards explícitas para `live_mode`, evidencia persistente en Engram, telemetría vía heartbeats.
- **O5**. Ser la base para futuras skills (`/stripe`, `/stripe-billing-saas`, `/stripe-refund-flow`) sin tener que reescribir setup.

### No-objetivos (v1)

- **N1**. **No reimplementar runtime de negocio**. `create_customer`, `create_subscription`, `refund`, `cancel_subscription`, `dispute` → esos son del Stripe MCP oficial. Duplicar allá invita bugs.
- **N2**. **No automatizar la activación de Connect**. La Stripe API no expone "enable Connect platform" — es un click único que requiere T&Cs en dashboard. Vivimos con él y lo documentamos.
- **N3**. **No resolver setup de secrets en Supabase**. Eso cae en `specbox-supabase.set_edge_secret` (tool paralelo, PRD hermano). Este PRD asume que existe y lo invoca.
- **N4**. **No soportar providers alternativos** (Adyen, Paddle, LemonSqueezy) en v1. Se evaluará demanda tras tener v1 estable.
- **N5**. **No gestionar compliance / T&Cs / tax** programáticamente. El developer sigue siendo responsable de leer y aceptar lo que Stripe pida.

---

## 3. Casos de uso prioritarios

### CU-1: Bootstrap completo tras `/stripe-connect`

**Actor**: skill `/stripe-connect` (invocada por dev)
**Precondición**: backend Supabase desplegado, Connect activado manualmente
**Flujo**:
1. Skill llama `verify_connect_enabled` → obtiene `{enabled: true, platform_name, country}`
2. Skill llama `setup_webhook_endpoints` con las 2 listas de eventos → recibe `{platform: {id, secret}, connect: {id, secret}}`
3. Skill llama `setup_products_and_prices` con los 3 tiers del proyecto → recibe `{products: [...], prices: [{id, tier_key}]}`
4. Skill invoca `mcp__specbox-supabase__set_edge_secret` (tool hermano) con los 4 secrets → éxito
5. Skill llama `get_setup_status` con expected config → recibe `verdict: 'ready'`
6. Skill escribe en el proyecto un `doc/billing/stripe-setup-evidence.md` con los IDs obtenidos
7. Dev ejecuta `/plan UC-301` y arranca frontend

**Resultado**: cero intervención manual entre `/stripe-connect` y `/plan`.

### CU-2: Re-ejecución idempotente tras fallo parcial

**Actor**: skill `/stripe-connect` tras un crash intermedio
**Precondición**: webhook endpoints creados en un intento anterior, products no
**Flujo**:
1. `setup_webhook_endpoints` detecta endpoints existentes con `metadata.specbox_managed=true` y mismo URL → **retorna los mismos IDs + secrets** sin crear duplicados
2. `setup_products_and_prices` no encuentra products con `metadata.tier={tier_key}` → los crea
3. Resultado final idéntico al CU-1 sin duplicados

### CU-3: Health check desde skill arbitraria

**Actor**: skill `/manual-test` antes de testear flujo de suscripción
**Flujo**:
1. `get_setup_status({expected_webhook_url, expected_tiers: ['bronce','plata','oro']})` → `verdict: 'partial', missing: ['connect_webhook_endpoint']`
2. Skill muestra al dev qué falta y ofrece ejecutar `/stripe-connect` para completar

### CU-4: Sembrar sellers test para E2E

**Actor**: skill `/manual-test` o `/quickstart`
**Flujo**:
1. `setup_test_sellers({count: 3, country: 'ES'})` → recibe 3 `account_id` + 3 `onboarding_url`
2. Patrol E2E tests usan esos `account_id` vía `Stripe-Account` header

### CU-5: Teardown entre iteraciones

**Actor**: dev que ejecuta `/manual-test` múltiples veces
**Flujo**:
1. `teardown_test_mode({confirm_token: "I understand this deletes test mode data"})` → borra todo objeto con `metadata.specbox_managed=true` en modo test
2. Preserva objetos creados por el dev manualmente (sin metadata SpecBox)

---

## 4. Alcance de tools v1

### Priorización (MVP vs nice-to-have)

| # | Tool | Prioridad | Justificación |
|---|---|---|---|
| T1 | `verify_connect_enabled` | **MVP** | Gate de entrada para todas las skills de pagos |
| T2 | `setup_webhook_endpoints` | **MVP** | El más doloroso manualmente, alto valor |
| T3 | `setup_products_and_prices` | **MVP** | Core para cualquier proyecto subscription-based |
| T4 | `get_setup_status` | **MVP** | Enable health-check desde skills |
| T5 | `setup_test_sellers` | v1.1 | Necesario para E2E, puede esperar a 2ª iteración |
| T6 | `teardown_test_mode` | v1.1 | Útil para DX, no bloqueante en v1 |

### Decisiones de diseño transversales

**D1. Idempotencia por `metadata.specbox_managed = "true"` + lookup key natural**:
- Webhooks: `url` + `connect` (bool) — hay 2 por URL, uno platform + uno connect
- Products: `metadata.tier` (unique per project)
- Prices: `product + unit_amount + recurring.interval + currency` (composite)
- Sellers: `metadata.specbox_test_seller_idx`

**D2. Autenticación — el MCP server lee Stripe secret key de una de 3 fuentes**:
- **v1**: parámetro `stripe_api_key` en cada call (flexibilidad multi-proyecto, el tool-call log es ya sensible por diseño)
- **v1.1**: resolver por alias en un secret store opcional (ej. `stripe_key_alias: "motofan-test"`)
- **v2 productivo**: OAuth con Stripe Connect OAuth v2 si Stripe lo estabiliza

**D3. Modo de seguridad "test-only" por defecto**:
- Si la key empieza por `sk_live_*` → reject con error `E_LIVE_MODE_NOT_ALLOWED` salvo que el call incluya `allow_live_mode: true` + `live_mode_confirm_token: "I acknowledge this affects real money"`
- Loggear en Engram cada vez que una tool se ejecuta en live mode

**D4. Formato estándar de respuestas** (JSON):
```ts
{
  success: boolean,
  data?: T,
  error?: { code: string, message: string, remediation?: string },
  warnings?: string[],
  evidence?: { engram_observation_id?: string, supabase_heartbeat?: bool }
}
```

**D5. Persistencia en Engram fire-and-forget**: cada tool que crea recursos escribe una observación `type=config` con los IDs creados, para recovery y auditoría.

**D6. Telemetría vía engine heartbeat**: cada call reporta `report_heartbeat(event_type="stripe_mcp_call", payload={tool, success, duration_ms})`.

---

## 5. Contratos de tools (especificación completa)

### T1 — `verify_connect_enabled`

**Intent**: "¿Puedo crear cuentas Connect Express en esta plataforma?"

**Input schema**:
```json
{
  "type": "object",
  "required": ["stripe_api_key"],
  "properties": {
    "stripe_api_key": {
      "type": "string",
      "pattern": "^sk_(test|live)_[A-Za-z0-9]+$"
    }
  }
}
```

**Output schema** (on success):
```json
{
  "success": true,
  "data": {
    "enabled": true,
    "platform_account_id": "acct_1TGSBuRjinbf6Ah6",
    "display_name": "Moto.Fan",
    "country": "ES",
    "default_currency": "eur",
    "capabilities_available": ["card_payments", "transfers", "sepa_debit_payments"],
    "mode": "test"
  }
}
```

**Behavior**:
1. `GET /v1/accounts/{platform_id}` para leer platform account info (el id implícito en la key)
2. **Canary**: intenta `POST /v1/accounts` con `type=express`, `country=ES`, `capabilities={card_payments:requested,transfers:requested}` + `metadata.specbox_probe=true`
3. Si éxito → borrar inmediatamente con `DELETE /v1/accounts/{acct_id}` y devolver `enabled: true`
4. Si falla con `platform_not_active` o similar → devolver `enabled: false` con `remediation: "Activa Connect en https://dashboard.stripe.com/{mode}/connect/overview"`

**Errores específicos**:
- `E_INVALID_KEY`: key mal formada o no autenticada
- `E_CONNECT_NOT_ENABLED`: canary falla por Connect inactivo
- `E_INSUFFICIENT_PERMISSIONS`: key no tiene permisos para accounts

**Evidence**: sin side-effects persistentes (salvo heartbeat)

---

### T2 — `setup_webhook_endpoints`

**Intent**: "Déjame los 2 webhook endpoints (platform + connect) con los eventos correctos y dame sus secrets."

**Input schema**:
```json
{
  "type": "object",
  "required": ["stripe_api_key", "platform_url", "platform_events", "connect_events"],
  "properties": {
    "stripe_api_key": {"type": "string"},
    "platform_url": {
      "type": "string",
      "format": "uri",
      "description": "URL pública del endpoint que recibe platform events"
    },
    "connect_url": {
      "type": "string",
      "format": "uri",
      "description": "URL pública del endpoint que recibe connect events (default = platform_url, dual-secret pattern)"
    },
    "platform_events": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Ej: ['account.updated', 'application_fee.created', ...]"
    },
    "connect_events": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Ej: ['customer.subscription.*', 'invoice.paid', ...]"
    },
    "api_version": {
      "type": "string",
      "description": "Ej: '2024-11-20.acacia' (default = latest stable)"
    },
    "description_prefix": {
      "type": "string",
      "description": "Prefijo para la description del endpoint. Default: 'SpecBox managed — {project_hint}'"
    }
  }
}
```

**Output schema**:
```json
{
  "success": true,
  "data": {
    "platform": {
      "id": "we_1AbCdEf...",
      "url": "https://xxx.supabase.co/functions/v1/stripe-webhook",
      "secret": "whsec_...",
      "events": ["account.updated", "..."],
      "status": "enabled",
      "created_or_reused": "created"
    },
    "connect": {
      "id": "we_2XyZwV...",
      "url": "https://xxx.supabase.co/functions/v1/stripe-webhook",
      "secret": "whsec_...",
      "events": ["customer.subscription.created", "..."],
      "connect": true,
      "status": "enabled",
      "created_or_reused": "reused"
    }
  },
  "evidence": {
    "engram_observation_id": "obs_..."
  }
}
```

**Behavior**:
1. Listar webhooks existentes: `GET /v1/webhook_endpoints?limit=100`
2. Para cada uno, leer `metadata.specbox_managed`. Si existe y `url === platform_url && connect === false` → reutilizar; si diferente URL o eventos → UPDATE para alinear; si no existe → CREATE.
3. Mismo para connect (filtro `connect: true`).
4. En CREATE: `POST /v1/webhook_endpoints` con:
   ```json
   {
     "url": "{platform_url}",
     "enabled_events": [...],
     "connect": false,
     "metadata": {
       "specbox_managed": "true",
       "specbox_project_hint": "{description_prefix}",
       "specbox_created_at": "2026-04-17T..."
     },
     "description": "SpecBox managed — platform events for {project}",
     "api_version": "2024-11-20.acacia"
   }
   ```
5. Extraer `secret` de la response (solo disponible en el CREATE — en REUSE hay que usar `GET /v1/webhook_endpoints/{id}` con `expand: ['secret']`).
6. Escribir observación Engram con los 2 IDs + secrets cifrados.

**Errores específicos**:
- `E_INVALID_URL`: URL no HTTPS o no alcanzable (ping opcional en v1.1)
- `E_UNKNOWN_EVENT_TYPE`: algún event type no existe en la api_version dada
- `E_LIMIT_REACHED`: cuenta alcanzó límite de webhooks (Stripe limita por cuenta)

**Idempotencia garantizada**: misma input → mismos IDs. Re-ejecución 10× = 2 endpoints finales.

**Nota crítica sobre secrets**: el `secret` de un webhook solo es visible en el POST de CREATE. Para REUSE hay que consultar con `expand: ['secret']`. **La tool gestiona ambos casos transparentemente**.

---

### T3 — `setup_products_and_prices`

**Intent**: "Crea el catálogo de productos/precios del proyecto alineado con los tiers que define el PRD."

**Input schema**:
```json
{
  "type": "object",
  "required": ["stripe_api_key", "catalog"],
  "properties": {
    "stripe_api_key": {"type": "string"},
    "catalog": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["tier_key", "product_name", "unit_amount", "currency"],
        "properties": {
          "tier_key": {
            "type": "string",
            "description": "Identificador semántico único del tier (ej. 'bronce', 'plata', 'oro'). Usado para idempotencia y para que el frontend lo resuelva."
          },
          "product_name": {"type": "string", "description": "Ej: 'Sponsor Bronce'"},
          "description": {"type": "string"},
          "unit_amount": {
            "type": "integer",
            "description": "Importe en céntimos. Ej: 500 para 5.00 €"
          },
          "currency": {"type": "string", "description": "ISO 4217 lowercase. Ej: 'eur'"},
          "interval": {
            "type": "string",
            "enum": ["month", "year"],
            "default": "month"
          },
          "trial_period_days": {"type": "integer", "description": "Optional"},
          "extra_metadata": {
            "type": "object",
            "description": "Metadata extra a añadir (se merge con specbox_managed y tier)"
          }
        }
      }
    },
    "archive_unmanaged_tiers": {
      "type": "boolean",
      "default": false,
      "description": "Si true, busca products con metadata.specbox_managed=true cuyo tier_key NO esté en el catalog nuevo y los archiva (active=false). Útil cuando cambias el pricing."
    }
  }
}
```

**Output schema**:
```json
{
  "success": true,
  "data": {
    "products": [
      {"id": "prod_...", "tier_key": "bronce", "name": "Sponsor Bronce", "created_or_reused": "created"},
      {"id": "prod_...", "tier_key": "plata", "name": "Sponsor Plata", "created_or_reused": "reused"}
    ],
    "prices": [
      {"id": "price_...", "tier_key": "bronce", "product_id": "prod_...", "unit_amount": 500, "currency": "eur", "created_or_reused": "created"},
      ...
    ],
    "archived": []
  }
}
```

**Behavior**:
1. Listar productos existentes con `metadata.specbox_managed=true`: `GET /v1/products?active=true&limit=100` + filter client-side
2. Por cada item del catalog:
   - Buscar product con `metadata.tier_key === item.tier_key`
   - Si existe y campos difieren → `POST /v1/products/{id}` para actualizar nombre/description
   - Si no existe → `POST /v1/products` con metadata `{specbox_managed: "true", tier_key, ...extra_metadata}`
3. Para cada product, buscar price con `unit_amount + currency + recurring.interval` match
   - Si existe → reutilizar
   - Si no existe → `POST /v1/prices` con `metadata.tier_key`
   - Prices NO se editan (Stripe no permite); si cambia precio → crear nuevo price + archivar el anterior con `POST /v1/prices/{id}` `active=false`
4. Si `archive_unmanaged_tiers=true` → archivar products SpecBox-managed no presentes en catalog

**Errores específicos**:
- `E_CURRENCY_NOT_ENABLED`: currency no habilitada en la platform account
- `E_DUPLICATE_TIER_KEY`: catalog tiene dos items con el mismo tier_key
- `E_PRICE_CONFLICT`: existe price activo con ese amount+currency+interval pero sin metadata SpecBox

**Evidence**: observación Engram con mapping `tier_key → {product_id, price_id}`

---

### T4 — `get_setup_status`

**Intent**: "¿Está todo listo para arrancar `/plan UC-301`? Dime qué falta si no."

**Input schema**:
```json
{
  "type": "object",
  "required": ["stripe_api_key"],
  "properties": {
    "stripe_api_key": {"type": "string"},
    "expected_webhook_url": {"type": "string", "description": "Optional: valida que existan 2 webhooks apuntando a esta URL"},
    "expected_tier_keys": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Optional: valida que existan products + prices para cada tier_key"
    },
    "expected_currency": {"type": "string", "default": "eur"}
  }
}
```

**Output schema**:
```json
{
  "success": true,
  "data": {
    "verdict": "ready" | "partial" | "not_setup",
    "checks": {
      "connect_enabled": true,
      "platform_webhook_endpoint": {"present": true, "id": "we_...", "events_ok": true},
      "connect_webhook_endpoint": {"present": true, "id": "we_...", "events_ok": true},
      "products_found": ["bronce", "plata", "oro"],
      "products_missing": [],
      "prices_found": {"bronce": "price_...", "plata": "price_...", "oro": "price_..."},
      "prices_missing": []
    },
    "summary": "3/3 checks pass. Ready for /plan UC-301.",
    "remediation_steps": []
  }
}
```

**Behavior**: read-only; combina llamadas de T1 + lookup de webhooks + lookup de products. Nunca modifica nada.

**Uso esperado**: prefijo de cualquier skill de pagos (`/stripe-connect`, `/manual-test` sobre flujos de billing, `/plan UC-30x`).

---

### T5 — `setup_test_sellers` (v1.1)

**Intent**: "Siembra N sellers test para E2E y manual-test."

**Input schema**:
```json
{
  "type": "object",
  "required": ["stripe_api_key", "count"],
  "properties": {
    "stripe_api_key": {"type": "string"},
    "count": {"type": "integer", "minimum": 1, "maximum": 10},
    "country": {"type": "string", "default": "ES"},
    "email_pattern": {
      "type": "string",
      "default": "specbox-test-{idx}+{timestamp}@example.com"
    },
    "capabilities": {
      "type": "array",
      "items": {"type": "string"},
      "default": ["card_payments", "transfers"]
    },
    "generate_onboarding_links": {
      "type": "boolean",
      "default": true
    },
    "auto_complete_onboarding": {
      "type": "boolean",
      "default": false,
      "description": "v1.1: si true, usa Stripe test helpers para marcar KYC como completed sin interacción humana. NO disponible en live_mode."
    }
  }
}
```

**Output schema**:
```json
{
  "success": true,
  "data": {
    "sellers": [
      {
        "account_id": "acct_...",
        "email": "specbox-test-0+1776447... @example.com",
        "country": "ES",
        "onboarding_url": "https://connect.stripe.com/setup/...",
        "status": "pending",
        "specbox_test_seller_idx": 0
      },
      ...
    ]
  }
}
```

**Behavior**:
1. Listar cuentas con `metadata.specbox_test_seller=true` y `metadata.specbox_test_seller_idx` ∈ [0, count-1]
2. Crear las que falten
3. Si `generate_onboarding_links=true` → `POST /v1/account_links` per cuenta con `type=account_onboarding`
4. Si `auto_complete_onboarding=true` (solo test_mode) → POST endpoint test helper o usa datos dummy de Stripe para completar: nombre `Jenny Rosen`, SSN `000-00-0000`, bank `STRIPE_US_BANK_ACCOUNT_NUMBER`, etc. **Esta feature necesita investigación de lo que Stripe test mode permite automatizar — documentar gaps.**

**Idempotencia**: por `metadata.specbox_test_seller_idx`.

---

### T6 — `teardown_test_mode` (v1.1)

**Intent**: "Limpia todos los recursos SpecBox-managed en modo test para volver a estado vírgen."

**Input schema**:
```json
{
  "type": "object",
  "required": ["stripe_api_key", "confirm_token"],
  "properties": {
    "stripe_api_key": {"type": "string"},
    "confirm_token": {
      "type": "string",
      "pattern": "^I understand this deletes test mode data$",
      "description": "Token literal para confirmar acción destructiva"
    },
    "scope": {
      "type": "array",
      "items": {"enum": ["webhooks", "products", "prices", "sellers", "customers"]},
      "default": ["webhooks", "products", "prices", "sellers"]
    }
  }
}
```

**Output schema**:
```json
{
  "success": true,
  "data": {
    "deleted": {
      "webhooks": 2,
      "products": 3,
      "prices": 3,
      "sellers": 3,
      "customers": 0
    },
    "errors": []
  }
}
```

**Behavior**:
1. Reject si `stripe_api_key` empieza por `sk_live_` (hardcoded deny, sin escape)
2. Reject si `confirm_token` no es literal
3. Por cada scope: listar items con `metadata.specbox_managed=true` y DELETE/ARCHIVE
4. `products`/`prices` → archive (Stripe no permite DELETE si usados)
5. `webhooks` → DELETE real
6. `sellers` (accounts) → `POST /v1/accounts/{id}/reject` (Stripe way of "deleting" test accounts)

**Safety**: escribe resumen detallado en Engram antes de ejecutar, con lista de IDs a tocar.

---

## 6. Arquitectura y empaquetado

### Decisión: MCP server separado vs extensión del SpecBox-Engine MCP actual

**Opción A — Nuevo MCP server `specbox-stripe`**:
- Pro: separación clara de responsabilidades, fail-independiente, puede evolucionar sin tocar engine core
- Pro: sigue el patrón existente (Supabase MCP, Trello MCP, Stitch MCP son todos separados)
- Contra: un MCP más que configurar, duplica boilerplate (auth, heartbeat, engram integration)

**Opción B — Submódulo dentro del SpecBox-Engine MCP existente** (prefix `stripe_`):
- Pro: una sola config, comparte auth/heartbeat
- Contra: ensucia el namespace engine con verticales, obliga a versionar engine cada vez que cambia stripe

**Recomendación**: **Opción A**. Alineada con el resto de MCPs de SpecBox. Evolución independiente. Permite que team Stripe integrations itere sin tocar engine core.

### Stack propuesto

- **Runtime**: Deno (consistente con Edge Functions) o Node.js 20+ (consistente con otros MCPs del engine — elegir según estándar interno)
- **Stripe SDK**: `stripe@^14` (oficial)
- **Transport**: HTTP streaming (MCP estándar) en `https://mcp.specbox.dev/stripe/v1` o similar
- **Auth del server**: PAT del usuario SpecBox (como el resto de MCPs)
- **Auth a Stripe**: `stripe_api_key` por call (v1), alias store (v1.1)

### Estructura de carpetas sugerida

```
packages/specbox-stripe-mcp/
├── src/
│   ├── tools/
│   │   ├── verify-connect-enabled.ts
│   │   ├── setup-webhook-endpoints.ts
│   │   ├── setup-products-and-prices.ts
│   │   ├── get-setup-status.ts
│   │   ├── setup-test-sellers.ts          (v1.1)
│   │   └── teardown-test-mode.ts          (v1.1)
│   ├── lib/
│   │   ├── stripe-client.ts                (wrapper con retry + logging)
│   │   ├── idempotency.ts                  (metadata + lookup helpers)
│   │   ├── engram-writer.ts                (fire-and-forget observations)
│   │   ├── heartbeat.ts                    (SpecBox telemetry)
│   │   └── safety.ts                       (live-mode guards)
│   ├── schemas/                            (JSONSchema por tool)
│   └── index.ts                            (MCP server entrypoint)
├── tests/
│   ├── integration/                        (contra Stripe test mode real)
│   └── unit/
├── README.md
└── package.json
```

### Metadata conventions (source of truth)

Toda tool que crea recursos añade:
```json
{
  "specbox_managed": "true",
  "specbox_version": "1.0.0",
  "specbox_project_hint": "{free-form, opcional}",
  "specbox_created_at": "{ISO timestamp}"
}
```

Toda tool que busca recursos filtra por `metadata["specbox_managed"] === "true"` como primer criterio.

---

## 7. Integración con la skill `/stripe-connect`

### Cambios propuestos en la skill

Insertar nuevo **Paso 9.5 — Infraestructura Stripe automatizada** (después del Paso 9 "Cablear Stripe MCP oficial" y antes del Paso 10 "Gherkin"):

```markdown
## Paso 9.5 — Automatizar infraestructura Stripe vía SpecBox-Stripe MCP

### 9.5.1 Verificar Connect

```
mcp__specbox-stripe__verify_connect_enabled({ stripe_api_key: env.STRIPE_SECRET_KEY })
```

Si `enabled: false` → abortar con instrucciones claras (URL al dashboard).

### 9.5.2 Crear webhook endpoints

```
mcp__specbox-stripe__setup_webhook_endpoints({
  stripe_api_key: env.STRIPE_SECRET_KEY,
  platform_url: "{SUPABASE_URL}/functions/v1/stripe-webhook",
  platform_events: [
    "account.updated", "capability.updated",
    "account.application.deauthorized", "application_fee.created"
  ],
  connect_events: [
    "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "invoice.paid",
    "invoice.payment_failed", "charge.refunded"
  ]
})
```

Guardar `{platform.secret, connect.secret}` para paso 9.5.4.

### 9.5.3 Crear Products + Prices

```
mcp__specbox-stripe__setup_products_and_prices({
  stripe_api_key: env.STRIPE_SECRET_KEY,
  catalog: [
    { tier_key: "bronce", product_name: "Sponsor Bronce", unit_amount: 500, currency: "eur" },
    { tier_key: "plata",  product_name: "Sponsor Plata",  unit_amount: 700, currency: "eur" },
    { tier_key: "oro",    product_name: "Sponsor Oro",    unit_amount: 900, currency: "eur" }
  ]
})
```

Guardar mapping `{tier_key → price_id}` en `doc/billing/stripe-catalog.json`.

### 9.5.4 Inyectar secrets en Supabase

```
mcp__specbox-supabase__set_edge_secret({
  project_id: "...",
  secrets: {
    STRIPE_SECRET_KEY:              env.STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET_PLATFORM: {platform.secret de 9.5.2},
    STRIPE_WEBHOOK_SECRET_CONNECT:  {connect.secret de 9.5.2},
    DEFAULT_APPLICATION_FEE_PERCENT: "20"
  }
})
```

### 9.5.5 Verificación final

```
mcp__specbox-stripe__get_setup_status({
  stripe_api_key: env.STRIPE_SECRET_KEY,
  expected_webhook_url: "{SUPABASE_URL}/functions/v1/stripe-webhook",
  expected_tier_keys: ["bronce", "plata", "oro"]
})
```

Si `verdict !== "ready"` → abortar con `remediation_steps`.
```

### Cambios en el Paso 11 (resumen)

Los "Siguientes pasos" pasan de **4 acciones manuales** a:

```
✓ Infraestructura Stripe automatizada (SpecBox-Stripe MCP):
  - Connect: ACTIVO en cuenta {account_id}
  - Webhook endpoints: 2 creados (IDs guardados en doc/billing/)
  - Catálogo: 3 products + 3 prices creados
  - Secrets Supabase: 4 configurados

Siguientes pasos:
  1. Ejecuta /plan UC-301 para arrancar frontend

(No hay pasos 2-4 manuales.)
```

---

## 8. Telemetría, observabilidad, evidencia

### Engram observations (fire-and-forget)

Cada tool escribe una observación al completarse con éxito:

```
type: config
title: "stripe-mcp: {tool_name} executed on {project_hint}"
content: |
  **Tool**: {tool_name}
  **Project**: {project_hint}
  **Mode**: {test|live}
  **Result**: {resumen human-readable}
  **IDs created**: [lista]
  **IDs reused**: [lista]
  **Duration**: {ms}
```

### SpecBox engine heartbeats

```
report_heartbeat({
  event_type: "stripe_mcp_call",
  payload: {
    tool: "{tool_name}",
    success: bool,
    duration_ms: int,
    mode: "test" | "live",
    idempotency_hit: bool  // true si todo reutilizado, false si alguna creación
  }
})
```

### Healing events

Si una tool falla y auto-corrige (ej. reintento tras rate limit, fallback de lookup a create), emitir:

```
report_healing({
  project_id,
  agent: "specbox-stripe-mcp",
  hook: "{tool_name}",
  root_cause: "{stripe_error_code}",
  resolution: "{retry|fallback|degrade}"
})
```

---

## 9. Seguridad

### Amenazas y mitigaciones

| Amenaza | Mitigación |
|---|---|
| Ejecución accidental en live mode | `sk_live_*` → reject por default; requiere flag explícita + confirm token. Logging exhaustivo en Engram |
| Leak de secrets en logs | Stripe keys y webhook secrets se redactan en logs (ej. `sk_test_****Abc123` only last 6) |
| Race condition en idempotencia (2 calls concurrent) | Usar `POST /v1/webhook_endpoints` con `Idempotency-Key` header (Stripe lo soporta nativamente) |
| Tool ejecutada con key de terceros por error | Validar que el caller SpecBox PAT tiene permisos para usar esa key (v2 con OAuth, v1 confía en el usuario) |
| Webhook endpoint apuntando a URL de atacante | Validar URL en whitelist opcional (`STRIPE_WEBHOOK_URL_ALLOWLIST` env var). En v1 confiar; en v1.1 añadir |
| Teardown accidental de data crítica | Reject en live mode, confirm_token literal, evidencia pre-action en Engram con IDs a borrar |

### Datos sensibles persistidos

- **Engram**: guardar IDs de recursos, NUNCA guardar `secret` completos. Si hace falta persistir un whsec para re-uso, hacerlo en un secret store separado (Supabase vault / similar).
- **Response JSON**: los secrets van al caller (skill) que los inyecta en Supabase y NO los persiste en disco del proyecto. La skill debe explicitar esto en `doc/billing/*.md` con un aviso de rotación.

---

## 10. Rollout y versionado

### Fases propuestas

- **v0.1 — Alpha interno**: T1 + T2 + T3 + T4. Usado solo en moto.fan para validar end-to-end.
- **v0.5 — Beta cross-project**: después de validar en moto.fan, habilitar en 2 proyectos más (candidatos: los onboardeados con stack Supabase + billing).
- **v1.0 — GA**: tool search/docs en la skill `/stripe-connect`, docs públicas, versionado semver.
- **v1.1**: T5 + T6 + alias store para keys.
- **v2.0**: OAuth con Stripe, multi-provider evaluation, live-mode con guardrails robustos.

### Versionado

- **API version de Stripe**: el MCP soporta un rango (`2023-10-16` → latest). Default `2024-11-20.acacia`. Se puede overridear por call.
- **MCP version**: semver. Breaking changes en output schema → major. Nuevas tools → minor. Fixes → patch.

### Compatibilidad con la skill

La skill `/stripe-connect` actual funciona SIN `specbox-stripe` MCP (fallback manual). Con el MCP, Paso 9.5 se ejecuta; sin él, skill muestra los 4 pasos manuales originales. **Zero breaking change** al añadir.

---

## 11. Métricas de éxito

### DX metrics

- **Tiempo desde `/stripe-connect` hasta `/plan UC-301`**: baseline actual ~15-30 min (manual), target v1 < 2 min (automatizado).
- **Tasa de fallos en primera ejecución**: baseline ~30% (por errores en copy/paste de secrets, URLs mal configuradas), target v1 < 5%.
- **Reejecuciones manuales necesarias**: baseline media 2-3, target v1 < 1.

### Adoption metrics

- Nº de proyectos que invocan `mcp__specbox-stripe__*` por mes (telemetry)
- Nº de tools distintas usadas por proyecto (penetración)
- Ratio de `verify_connect_enabled` → `setup_webhook_endpoints` (funnel de activación)

### Reliability metrics

- % éxito por tool (target > 99% en test mode, > 95% en live mode)
- Latency p95 por tool (< 2s excluyendo Stripe API variable)
- Incidentes de idempotencia rota (duplicados creados) — target 0

---

## 12. Dependencias y riesgos

### Dependencias duras

- **D-1**: `specbox-supabase.set_edge_secret` tool — sin esto el flujo end-to-end no cierra. Debería desarrollarse en paralelo.
- **D-2**: Stripe API key stable across `2024-11-20.acacia` — Stripe deprecaciones podrían romper. Mitigación: pinear api_version, correr CI contra ambos versions.

### Dependencias blandas

- **D-3**: Stripe MCP oficial no se mueve al terreno setup-as-code. Si lo hace, este MCP se vuelve redundante. Probabilidad: baja (Stripe tiene poca traction en MCP setup-focused). Mitigación: si pasa, refactorizar como wrapper o archivar.

### Riesgos

| Riesgo | Impacto | Prob. | Mitigación |
|---|---|---|---|
| Stripe limita rate de `POST /v1/accounts` durante canary T1 | Tool falla intermitente | Baja | Canary opcional con flag `skip_canary: true` |
| Usuario rota keys y MCP no se entera | Errores 401 | Media | Mensajes de error claros con remediation |
| Webhook secret rotation breaks en producción | Downtime billing | Media | Docs explícitos sobre rotación + script de rotación batch |
| Metadata SpecBox colisiona con metadata del dev | Idempotencia falla | Baja | Prefijar TODO con `specbox_` y documentar claim del namespace |

---

## 13. Testing strategy

### Unit tests

- Por tool, mock de Stripe SDK, verificar:
  - Idempotencia (2 calls consecutivas → mismo output)
  - Validación input schema
  - Redacción de secrets en logs
  - Live-mode rejection

### Integration tests

- Cuenta Stripe test dedicada al CI (`sk_test_SPECBOX_CI_*`)
- Test matrix por tool con casos: first-run, reuse, error
- Teardown antes y después de cada test (usa T6 tras ser implementado, o script manual)

### E2E desde skill

- Ejecutar skill `/stripe-connect` completa contra proyecto demo
- Verificar que al terminar, `get_setup_status` devuelve `verdict=ready`
- Ejecutar una compra de prueba con test card `4242 4242 4242 4242` y verificar que el webhook actualiza DB

---

## 14. Open questions

1. **¿El MCP server se empaqueta con el engine o como paquete separado?** Recomendación arriba: separado.
2. **¿La tool `setup_test_sellers` con `auto_complete_onboarding=true` es viable?** Stripe expone `POST /v1/accounts/{id}/capabilities` + `POST /v1/accounts/{id}` con `business_profile` pero completar KYC realmente requiere documentos. Puede ser "casi-enabled" pero no "enabled" sin intervención manual. A investigar.
3. **¿Soportamos `sk_rk_*` (restricted keys) o solo `sk_test_*` / `sk_live_*`?** Restricted keys serían más seguras. A decidir en v1.1.
4. **¿El alias store (v1.1) vive dentro del MCP o fuera?** Candidato: dentro, usando Supabase como backend (circular pero funcional).
5. **Localización de mensajes de error**: ¿ES/EN?. Por defecto EN, con `locale` opcional en input.

---

## 15. Appendix — Estado actual (caso moto.fan 2026-04-17)

Como referencia concreta del problema que motiva este PRD:

### Stack del proyecto
- Flutter (BLoC + supabase_flutter) + Supabase remoto (project id `gjwqsehingipcqmngbso`)
- Workflow MCP-only (sin Supabase CLI)

### Fase 1 completada sin MCP Stripe (backend Supabase)
- Migración `add_stripe_connect_phase_1` aplicada vía `mcp__supabase__apply_migration` ✅
- 5 Edge Functions deployadas vía `mcp__supabase__deploy_edge_function` ✅
- Todo el código fuente en [supabase/functions/](supabase/functions/), branch `feature/stripe-connect-phase-1`, commit `1a7807a`

### Los 4 pasos manuales que el dev (Jesús) tiene que ejecutar HOY
1. Activar Stripe Connect (1 click, irreducible)
2. Crear 2 webhook endpoints en dashboard.stripe.com/test/webhooks con eventos específicos
3. Crear 3 products + 3 prices (bronce/plata/oro con metadata)
4. Copiar 4 secrets al dashboard de Supabase

### Lo que este PRD elimina
- Paso 2 → `setup_webhook_endpoints`
- Paso 3 → `setup_products_and_prices`
- Paso 4 → `specbox-supabase.set_edge_secret` (tool hermano, PRD separado)
- Paso 1 → sigue manual (irreducible), pero detectado por `verify_connect_enabled`

### Eventos críticos acordados para webhook endpoints (copy-paste ready para setup_webhook_endpoints)

**Platform events**:
```
account.updated
capability.updated
account.application.deauthorized
application_fee.created
```

**Connect events**:
```
customer.subscription.created
customer.subscription.updated
customer.subscription.deleted
invoice.paid
invoice.payment_failed
charge.refunded
```

### Catálogo moto.fan v1 (copy-paste ready para setup_products_and_prices)

```json
{
  "catalog": [
    { "tier_key": "bronce", "product_name": "Sponsor Bronce", "description": "Contenido exclusivo básico, badge de sponsor, feed privado.", "unit_amount": 500, "currency": "eur", "interval": "month" },
    { "tier_key": "plata",  "product_name": "Sponsor Plata",  "description": "Todo lo de Bronce + contenido premium, menciones, descuentos merch.", "unit_amount": 700, "currency": "eur", "interval": "month" },
    { "tier_key": "oro",    "product_name": "Sponsor Oro",    "description": "Todo lo de Plata + VIP eventos, videollamada mensual, nombre en vehículo.", "unit_amount": 900, "currency": "eur", "interval": "month" }
  ]
}
```

(Los importes 5/7/9 € reflejan el schema DB actual; US-23 repricing a 9.99/14.99/19.99 € está en backlog y generará una nueva invocación de `setup_products_and_prices` con `archive_unmanaged_tiers: true`.)

### URLs del proyecto para webhook endpoints

```
platform_url: https://gjwqsehingipcqmngbso.supabase.co/functions/v1/stripe-webhook
connect_url:  https://gjwqsehingipcqmngbso.supabase.co/functions/v1/stripe-webhook
```

(Mismo URL — el webhook verifica contra ambos secrets internamente.)

---

## 16. Apéndice — Checklist para el executor del PRD en SpecBox

Cuando SpecBox descomponga este PRD:

- [ ] Crear US-SPECBOX-STRIPE en el board del engine
- [ ] UC-1: `verify_connect_enabled` (T1)
- [ ] UC-2: `setup_webhook_endpoints` (T2)
- [ ] UC-3: `setup_products_and_prices` (T3)
- [ ] UC-4: `get_setup_status` (T4)
- [ ] UC-5 (opcional v1.1): `setup_test_sellers` (T5)
- [ ] UC-6 (opcional v1.1): `teardown_test_mode` (T6)
- [ ] UC-7: integración con skill `/stripe-connect` (Paso 9.5)
- [ ] UC-8: integración con Engram (observations + heartbeats)
- [ ] UC-9: tests de integración contra Stripe test mode
- [ ] UC-10: docs públicas + ejemplos

**PRD hermano bloqueante**: `specbox-supabase-set-edge-secret` (tool para pegar secrets desde MCP en vez de dashboard). Sin él, el flujo no es 100% automatizable.
