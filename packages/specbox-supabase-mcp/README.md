# specbox-supabase-mcp

> SpecBox MCP for **Supabase Edge Function secrets**.
> Complements the [official Supabase MCP](https://github.com/supabase-community/supabase-mcp)
> (which does NOT cover secrets — gap documented in
> [issue #120](https://github.com/supabase-community/supabase-mcp/issues/120)).

## What it does

Automates the last manual step of `/stripe-connect` and other SpecBox skills
that need to inject environment variables into Supabase Edge Functions. Before
this package, a developer had to copy 4+ secrets into the Supabase dashboard
by hand. With this MCP, skills can do it programmatically via the
[Supabase Management API](https://supabase.com/docs/reference/api/introduction).

## Tool catalog (v0.1 MVP)

| Tool | Intent | Input | Output (key fields) |
|------|--------|-------|---------------------|
| `set_edge_secret` | Bulk create/overwrite secrets | `supabase_access_token`, `project_ref`, `secrets: {NAME: value}` | `applied[]`, `previously_present[]`, `previously_absent[]`, `all_overwritten` |
| `list_edge_secrets` | Read-only inventory (names + timestamps, never values) | `supabase_access_token`, `project_ref`, `expected_names?` | `names[]`, `count`, `last_updated_at`, `missing_names?`, `extra_names?` |
| `unset_edge_secret` | Bulk delete with mandatory confirm token | `supabase_access_token`, `project_ref`, `names[]`, `confirm_token` | `deleted[]`, `skipped[]`, `before_count`, `after_count` |

The Supabase Management API **never returns secret values** on `GET` — only
names and timestamps. That's a deliberate design of the API, and this MCP
preserves that invariant end-to-end.

## Standard response envelope

Every tool returns the same shape (copied from `specbox-stripe-mcp`):

```ts
{
  success: boolean,
  data?: T,
  error?: { code: string, message: string, remediation?: string },
  warnings?: string[],
  evidence?: { engram_observation_id?: string }
}
```

### Stable error codes

- `E_INVALID_INPUT` — PAT / project_ref / secret name / value shape wrong (caught before any HTTP).
- `E_INVALID_TOKEN` — Supabase rejected the PAT (401).
- `E_PROJECT_NOT_FOUND` — `project_ref` does not exist or isn't visible with this PAT (404).
- `E_INSUFFICIENT_PERMISSIONS` — PAT lacks permission for this project (403).
- `E_RATE_LIMITED` — Supabase rate limit (120 req/min) hit after retries exhausted.
- `E_CONFIRM_TOKEN_MISMATCH` — `unset_edge_secret` called with wrong literal token.
- `E_SUPABASE_ERROR` — any other Supabase Management API error (see `error.message`).

## Design principles

- **Values never leak.** The `secrets` dict values flow to Supabase via HTTP body
  and are immediately discarded from the MCP process. They never appear in logs,
  Engram observations, responses, or error messages. Only **names** are visible.
- **PAT redaction.** Any `sbp_*` token occurring in a log line is redacted to
  `sbp_****<last6>` via `lib/safety.redact_log_line`.
- **Idempotent by design.** `set_edge_secret` is idempotent because Supabase's
  POST semantics overwrite by name. The tool does a GET first to compute
  `previously_present` / `previously_absent` and emit an accurate
  `idempotency_hit` heartbeat.
- **Fire-and-forget evidence.** Each call writes a config observation to Engram
  (names only) and a heartbeat to the SpecBox engine. Neither is a hard
  dependency — tools work if both are offline.
- **Safe destructive ops.** `unset_edge_secret` requires a literal
  `confirm_token` and writes a pre-action Engram audit observation **before** the
  DELETE is sent.

## Quickstart

```bash
# From source
cd packages/specbox-supabase-mcp
pip install -e ".[dev]"

# Run as MCP server
specbox-supabase-mcp
```

Register in `~/.claude/mcp.json`:

```json
{
  "servers": {
    "specbox-supabase": {
      "command": "specbox-supabase-mcp"
    }
  }
}
```

Create a Personal Access Token at <https://supabase.com/dashboard/account/tokens>
and export it:

```bash
export SUPABASE_ACCESS_TOKEN="sbp_..."
export SUPABASE_PROJECT_REF="gjwqsehingipcqmngbso"  # example
```

## End-to-end example (moto.fan — closes the `/stripe-connect` loop)

```python
# After specbox-stripe-mcp has produced the 2 webhook secrets, inject the
# 4 Stripe-related secrets into Supabase Edge Functions in one shot:
set_edge_secret(
    supabase_access_token="sbp_...",
    project_ref="gjwqsehingipcqmngbso",
    secrets={
        "STRIPE_SECRET_KEY":              "sk_test_...",
        "STRIPE_WEBHOOK_SECRET_PLATFORM": "whsec_...",  # from setup_webhook_endpoints
        "STRIPE_WEBHOOK_SECRET_CONNECT":  "whsec_...",
        "DEFAULT_APPLICATION_FEE_PERCENT": "20",
    },
    project_hint="motofan",
)
# → data.applied = [4 names], data.all_overwritten = false on first run

# Later, verify the setup stayed consistent:
list_edge_secrets(
    supabase_access_token="sbp_...",
    project_ref="gjwqsehingipcqmngbso",
    expected_names=["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET_PLATFORM",
                    "STRIPE_WEBHOOK_SECRET_CONNECT", "DEFAULT_APPLICATION_FEE_PERCENT"],
)
# → data.missing_names = []  → green light for /plan UC-301
```

## Security

- **Default behavior is test-safe**: no mutating operation happens without valid
  input shape and (for deletes) the literal `confirm_token`.
- **PAT scope**: Supabase PATs are user-global (not per-project). Document this
  clearly to the developer; this MCP cannot mitigate a PAT with excessive reach.
- **No storage**: PATs and secret values exist in the MCP process only for the
  duration of one call. Neither disk, Engram, nor heartbeat ever sees them.
- **Audit trail**: `unset_edge_secret` writes a pre-action Engram observation
  listing the exact names about to be deleted, before issuing the DELETE.

## Running tests

```bash
# Unit tests (default, no credentials needed)
pytest tests/unit/ -q

# With coverage (gated at 85% in pyproject.toml)
pytest tests/unit/ --cov=specbox_supabase_mcp --cov-report=term

# Integration tests against a real Supabase project (CI only)
export SUPABASE_CI_ACCESS_TOKEN="sbp_..."
export SUPABASE_CI_PROJECT_REF="<20-char ref>"
pytest tests/integration/ -m integration
```

See [tests/integration/README.md](tests/integration/README.md) for the autouse
teardown contract.

## References

- **PRD**: [doc/prd/specbox_supabase_mcp_prd.md](../../doc/prd/specbox_supabase_mcp_prd.md)
- **Sibling MCP**: [specbox-stripe-mcp](../specbox-stripe-mcp/) — together they
  close the full `/stripe-connect` flow end-to-end.
- **Consumer skill**: `/stripe-connect` (SpecBox Engine) — inserts Paso 9.5.4
  that invokes `set_edge_secret` between webhook setup and final verification.
- **Supabase Management API**: <https://supabase.com/docs/reference/api/introduction>

## Status

**H1 alpha shipped**: 3 MVP tools + telemetry transversal + 85%+ coverage +
integration suite gated by CI credentials + integration into `/stripe-connect`
skill Paso 9.5.4. This UC-SB-7 **unblocks** UC-7 of `specbox-stripe-mcp`.

See [BACKLOG.md](BACKLOG.md) for H2 items (self-hosted, alias store for PATs).
