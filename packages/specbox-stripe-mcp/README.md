# specbox-stripe-mcp

> SpecBox MCP server for Stripe **setup-as-code**.
> Complements the [official Stripe MCP](https://mcp.stripe.com/v1): SpecBox-Stripe
> builds the track (Connect gate, webhooks, products/prices, health check),
> Stripe MCP runs business operations on top of it.

## What it does

Closes the setup-as-code gap that the official Stripe MCP does not cover, so
SpecBox skills like `/stripe-connect` can leave a project **operational
end-to-end** without a single manual dashboard click (beyond the irreducible
"enable Connect" toggle).

## Tool catalog (v0.1 MVP)

| Tool | Intent | Input | Output (key fields) |
|------|--------|-------|---------------------|
| `verify_connect_enabled` | Can I create Connect Express accounts? | `stripe_api_key`, `project_hint`, `skip_canary?` | `enabled`, `platform_account_id`, `capabilities_available`, `mode` |
| `setup_webhook_endpoints` | Create/reuse the 2 webhook endpoints | `stripe_api_key`, `platform_url`, `platform_events[]`, `connect_events[]`, `connect_url?`, `api_version?` | `platform.{id,secret,events,created_or_reused}`, `connect.{...}` |
| `setup_products_and_prices` | Reconcile catalog by tier_key | `stripe_api_key`, `catalog[]`, `archive_unmanaged_tiers?` | `products[]`, `prices[]`, `archived[]`, `tier_mapping` |
| `get_setup_status` | Read-only health check | `stripe_api_key`, `expected_webhook_url?`, `expected_tier_keys?`, `expected_platform_events?`, `expected_connect_events?` | `verdict` ∈ {ready, partial, not_setup}, `checks`, `remediation_steps` |

v1.1 will add `setup_test_sellers` and `teardown_test_mode` (H3 backlog).

## Standard response envelope

Every tool returns the same shape (PRD §4, D4):

```ts
{
  success: boolean,
  data?: T,
  error?: { code: string, message: string, remediation?: string },
  warnings?: string[],
  evidence?: { engram_observation_id?: string }
}
```

Stable error codes:
- `E_INVALID_KEY` — Stripe API key is missing or malformed.
- `E_LIVE_MODE_NOT_ALLOWED` — sk_live_* without explicit opt-in + confirm token.
- `E_CONNECT_NOT_ENABLED` — platform needs to activate Connect in the dashboard.
- `E_INSUFFICIENT_PERMISSIONS` — key lacks permission (e.g. restricted key).
- `E_INVALID_URL` — webhook URL is not HTTPS.
- `E_INVALID_INPUT` — empty events, missing tier_key, etc.
- `E_UNKNOWN_EVENT_TYPE` — Stripe rejected an event name for the given api_version.
- `E_LIMIT_REACHED` — Stripe resource limit hit.
- `E_DUPLICATE_TIER_KEY` — catalog has two items with the same tier_key.
- `E_CURRENCY_NOT_ENABLED` — currency not enabled on the platform account.
- `E_PRICE_CONFLICT` — non-SpecBox price conflicts with the intended shape.
- `E_STRIPE_ERROR` — generic Stripe API error (see `error.message` for detail).

## Design principles

- **Idempotent by design.** Every create uses `metadata.specbox_managed="true"`
  plus a natural lookup key (webhook url+connect, product tier_key, etc.).
  Re-running the same call is always safe.
- **Test-only by default.** `sk_live_*` is rejected unless you pass
  `allow_live_mode: true` AND
  `live_mode_confirm_token: "I acknowledge this affects real money"`.
- **Fire-and-forget evidence.** Each call writes a config observation to Engram
  and a heartbeat to the SpecBox engine. Neither is a dependency — tools keep
  working if those systems are offline.
- **Secrets never leak.** Logs redact `sk_test_****abc123` and
  `whsec_****xyz789`. Webhook secrets flow to the caller and should be injected
  into Supabase (or equivalent) via the sibling `specbox-supabase` MCP —
  never written to the project's disk.

## Quickstart

```bash
# From source
cd packages/specbox-stripe-mcp
pip install -e ".[dev]"

# Run as MCP server (stdio mode, for Claude Code)
specbox-stripe-mcp
```

Then in `~/.claude/mcp.json`:

```json
{
  "servers": {
    "specbox-stripe": {
      "command": "specbox-stripe-mcp"
    }
  }
}
```

## End-to-end example (moto.fan)

```python
# 1. Gate: is Connect enabled?
verify_connect_enabled(
    stripe_api_key="sk_test_...",
    project_hint="motofan",
)
# → data.enabled=true, mode="test"

# 2. Webhooks — create or reuse
setup_webhook_endpoints(
    stripe_api_key="sk_test_...",
    platform_url="https://gjwqsehingipcqmngbso.supabase.co/functions/v1/stripe-webhook",
    platform_events=[
        "account.updated", "capability.updated",
        "account.application.deauthorized", "application_fee.created",
    ],
    connect_events=[
        "customer.subscription.created", "customer.subscription.updated",
        "customer.subscription.deleted",
        "invoice.paid", "invoice.payment_failed", "charge.refunded",
    ],
    project_hint="motofan",
)
# → data.platform.secret = "whsec_...", data.connect.secret = "whsec_..."

# 3. Catalog — 3 tiers (bronce/plata/oro)
setup_products_and_prices(
    stripe_api_key="sk_test_...",
    catalog=[
        {"tier_key": "bronce", "product_name": "Sponsor Bronce",
         "description": "Contenido exclusivo básico, badge de sponsor, feed privado.",
         "unit_amount": 500, "currency": "eur", "interval": "month"},
        {"tier_key": "plata",  "product_name": "Sponsor Plata",
         "description": "Todo lo de Bronce + contenido premium, menciones, descuentos merch.",
         "unit_amount": 700, "currency": "eur", "interval": "month"},
        {"tier_key": "oro",    "product_name": "Sponsor Oro",
         "description": "Todo lo de Plata + VIP eventos, videollamada mensual, nombre en vehículo.",
         "unit_amount": 900, "currency": "eur", "interval": "month"},
    ],
    project_hint="motofan",
)
# → data.tier_mapping = {bronce: {product_id, price_id}, plata: {...}, oro: {...}}

# 4. Inject secrets into Supabase via sibling tool (specbox-supabase — PRD pending):
#    mcp__specbox-supabase__set_edge_secret({
#      STRIPE_SECRET_KEY: "sk_test_...",
#      STRIPE_WEBHOOK_SECRET_PLATFORM: <from step 2>,
#      STRIPE_WEBHOOK_SECRET_CONNECT:  <from step 2>,
#      DEFAULT_APPLICATION_FEE_PERCENT: "20",
#    })

# 5. Verdict
get_setup_status(
    stripe_api_key="sk_test_...",
    expected_webhook_url="https://gjwqsehingipcqmngbso.supabase.co/functions/v1/stripe-webhook",
    expected_tier_keys=["bronce", "plata", "oro"],
    expected_platform_events=["account.updated", "capability.updated",
                              "account.application.deauthorized", "application_fee.created"],
    expected_connect_events=["customer.subscription.created", "customer.subscription.updated",
                             "customer.subscription.deleted",
                             "invoice.paid", "invoice.payment_failed", "charge.refunded"],
    project_hint="motofan",
)
# → data.verdict = "ready"
```

## Security

- **Default mode is test-only.** `sk_live_*` keys trigger
  `E_LIVE_MODE_NOT_ALLOWED` unless the caller passes `allow_live_mode:true`
  and the literal confirm token.
- **Webhook secrets** are returned to the caller for injection into Supabase;
  they are never persisted to the project's filesystem by this package.
- **Logs redact** API keys and webhook secrets — only the last 6 characters
  appear.
- **Teardown** (v1.1) is hardcoded-blocked in live mode and requires a literal
  confirm token.
- **Idempotency keys** are deterministic per (tool, lookup-key, api_version)
  so two concurrent calls collapse into one Stripe object.

## Running tests

```bash
# Unit tests only (what CI runs by default)
pytest tests/unit/ -q

# With coverage (gated at 85% by pyproject.toml)
pytest tests/unit/ --cov=specbox_stripe_mcp --cov-report=term

# Integration tests against a real test-mode account
export STRIPE_CI_SECRET_KEY="sk_test_..."
pytest tests/integration/ -m integration
```

See [tests/integration/README.md](tests/integration/README.md) for the teardown
contract.

## References

- **PRD**: [doc/prd/specbox_stripe_mcp_prd.md](../../doc/prd/specbox_stripe_mcp_prd.md)
- **Sibling MCP** (blocking for UC-7): `specbox-supabase.set_edge_secret`
  (separate PRD, pending).
- **Consumer skill**: `/stripe-connect` in SpecBox Engine v5.25.0.

## Status

**H1 milestone complete**: T1-T4 MVP tools + transversal telemetry (UC-1..UC-4,
UC-8) + integration suite (UC-9). Documentation (UC-10) delivered here.
Tracked in SpecBox FreeForm backend under US-SPECBOX-STRIPE.

**Backlog**:
- UC-5 `setup_test_sellers` (H3)
- UC-6 `teardown_test_mode` (H3)
- UC-7 integration with `/stripe-connect` Paso 9.5 (blocked on
  `specbox-supabase.set_edge_secret`)
