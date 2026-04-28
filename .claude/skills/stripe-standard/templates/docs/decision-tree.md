# Stripe scaffolders — `/stripe-standard` vs `/stripe-connect`

> If you're not sure which to run, default to **`/stripe-standard`**. Adding
> Connect later is a refactor but supported by the same MCP via
> `setup_webhook_endpoints(account_mode='connect')`.

## Decision tree

```
Are you a marketplace?
i.e. money flows from your customers to OTHER sellers, and you take a cut.
│
├── No → /stripe-standard
│        SaaS, e-commerce, B2B invoicing, donations, paywalls,
│        digital products, lifetime deals.
│
└── Yes → /stripe-connect
         Express accounts for sellers, Direct charges, optional
         application_fee_percent dynamic per seller.
```

## Side-by-side

| Dimension | `/stripe-standard` | `/stripe-connect` |
|-----------|-------------------|-------------------|
| Underlying MCP | `specbox-stripe-mcp` v0.2 with `account_mode='standard'` | same MCP with `account_mode='connect'` |
| Webhook endpoints | **1** (platform-scope only) | **2** (platform + connect) |
| Webhook secrets | 1 (`STRIPE_WEBHOOK_SECRET`) | 2 (`_PLATFORM` + `_CONNECT`) |
| Supabase Edge Functions | 5–7 (depending on activated modes) | 5 (fixed) |
| SQL tables | 3 (`customers`, `subscriptions`, `events`) | 4 (`riders`, `sponsorships`, `customers`, `events`) |
| Customer Portal | **Built-in** (customer lives in your account) | Disabled (customer lives in seller's account) |
| `application_fee_percent` | n/a | Dynamic per seller (default in env) |
| Activate Connect on dashboard | Not required | Required (one click) |
| Sub modalities supported | 4 flags (single/tiered/metered/one_shot) | 1 flag (recurring sub with fee) |
| Spec backend US | `US-STRIPE-CHECKOUT` (12 UCs) | `US-SPONSORSHIP` (12 UCs) |
| Hosted Checkout (`ui_mode='hosted'`) | **Blocked by safety hook** | **Blocked by safety hook** |
| Embedded Checkout | Available as fallback | Available as fallback |
| `stripe-safety-guard` hook | Same instance, same 5 anti-patterns | Same instance |

## When you're really not sure

Examples mapped:

| Use case | Skill |
|----------|-------|
| Notion / Linear / Figma clones (paid app) | `/stripe-standard` (single_sub or tiered_sub) |
| OpenAI-style API with usage pricing | `/stripe-standard` (metered) |
| Online shop selling your own goods | `/stripe-standard` (one_shot) |
| Donations to your nonprofit | `/stripe-standard` (one_shot) |
| Patreon / OnlyFans style — fans to creators | `/stripe-connect` |
| Etsy / eBay — buyers to merchants | `/stripe-connect` |
| Uber / Airbnb — riders to drivers / guests to hosts | `/stripe-connect` |
| In-app purchases for your own digital product (lifetime) | `/stripe-standard` (one_shot) |

## Migration paths

### `/stripe-standard` → `/stripe-connect`

Re-running `/stripe-connect` doesn't auto-migrate Standard data. The
spec, templates and Edge Functions are different. Migration steps:

1. Decide if existing standard subscriptions should stay (continue cobrando
   in your platform account) or move to a connected seller account (rare).
2. Run `/stripe-connect` in a new branch — it scaffolds parallel files.
3. Manually merge any custom UI you'd built on top of Standard templates.
4. The webhook URL stays the same; the underlying MCP migrates the endpoint
   metadata silently when you call `setup_webhook_endpoints(account_mode='connect')`.

### `/stripe-connect` → `/stripe-standard`

This is even rarer (going from marketplace to single-seller). Don't do it
unless the business model genuinely changed.

## What runs the show under the hood

Both skills are **clients** of `specbox-stripe-mcp`. None of them wrap the
Stripe API directly — that lives in the MCP. The skill is just opinionated
boilerplate generation.

```
You run /stripe-standard (or /stripe-connect)
  ↓
Skill writes files (Edge Functions, SQL, UI templates, Stitch HTML)
  ↓
Skill optionally calls specbox-stripe-mcp.setup_products_and_prices
  ↓
Skill optionally calls specbox-supabase-mcp.set_edge_secret
  ↓
Smoke-test in dev with stripe listen
  ↓
get_setup_status(account_mode='standard'|'connect') → verdict='ready'
  ↓
Switch to live (`sk_live_*`)
```
