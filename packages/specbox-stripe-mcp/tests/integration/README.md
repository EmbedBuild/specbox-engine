# Integration tests — specbox-stripe-mcp

These tests run **against a real Stripe test-mode account**. They are skipped
automatically unless `STRIPE_CI_SECRET_KEY` is exported.

## Setup

1. Create a dedicated Stripe test-mode account for CI. Do **not** reuse a
   production account, even in test mode — the teardown fixture cleans up
   every SpecBox-managed resource it finds.
2. Enable Connect on that account (one click in the dashboard).
3. Export:
   ```bash
   export STRIPE_CI_SECRET_KEY="sk_test_..."
   ```
4. Run:
   ```bash
   pytest tests/integration/ -m integration
   ```

## What these tests exercise

For each of T1-T4 MVP tools:

- **First-run**: the resource does not exist → CREATE path
- **Reuse**: re-invoking with identical inputs → idempotent path (no dupes)
- **Error**: a realistic failure shape → mapped to our error codes

## Teardown contract

The `stripe_teardown` fixture deletes:

- All webhook endpoints with `metadata.specbox_managed=true`
- All products with `metadata.specbox_managed=true` (archived, since Stripe
  forbids DELETE when prices reference them)
- All prices with `metadata.specbox_managed=true` (archived)

Teardown runs BEFORE each test (for a clean slate) and AFTER (to leave the
account clean for subsequent runs).

## Rate limits

Stripe test-mode has generous limits but the canary in T1 creates+deletes a
platform account, which is rate-limited more aggressively than other endpoints.
If you see intermittent E_STRIPE_ERROR, try:

- Running tests serially (no `-n auto`)
- Adding `skip_canary=True` to T1 calls in your test

## Local quick-run without integration tests

```bash
pytest tests/unit/ -q
```

This is what CI runs by default without any Stripe credentials.
