# Integration tests — specbox-supabase-mcp

These tests run against a **real Supabase project** via the Management API.
They are skipped unless both environment variables are set:

- `SUPABASE_CI_ACCESS_TOKEN` — a PAT for the CI user (sbp_*)
- `SUPABASE_CI_PROJECT_REF` — 20-char ref of a dedicated Supabase CI project

## Setup

1. Create a **dedicated Supabase project** for CI. The autouse teardown fixture
   deletes every secret whose name starts with `SPECBOX_CI_`. Never point this
   suite at a shared / production project.
2. Generate a PAT at <https://supabase.com/dashboard/account/tokens>.
3. Export both env vars and run:

   ```bash
   export SUPABASE_CI_ACCESS_TOKEN="sbp_..."
   export SUPABASE_CI_PROJECT_REF="<20 lowercase chars>"
   pytest tests/integration/ -m integration
   ```

## Teardown contract

`autouse=True` fixture `supabase_teardown`:

- **Before each test**: deletes every secret with a name starting `SPECBOX_CI_`
  to ensure a clean slate.
- **After each test** (success or failure): same cleanup.

Tests must not create secrets whose names don't start with `SPECBOX_CI_`; the
teardown won't clean them up and they'll pollute the project.

## Rate limits

Supabase Management API limit is 120 req/min per user per project. Each test
typically uses 2-4 requests (GET to inventory + POST/DELETE). Running the full
suite sequentially stays well within the budget.

## Local quick-run without integration tests

```bash
pytest tests/unit/ -q
```

This is what CI runs by default when no Supabase credentials are present.
