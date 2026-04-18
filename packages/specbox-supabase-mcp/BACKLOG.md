# Backlog — specbox-supabase-mcp

## UC-SB-8 `base_url` self-hosted support (H2 v1.1)

**Status**: partially implemented, not tested against real self-hosted.

The `base_url` parameter exists in all tools and `SupabaseClient`, defaulting
to `https://api.supabase.com`. Self-hosted support would add integration tests
against a self-hosted instance when demand appears.

**Contract**: pass `base_url="https://my-supabase-selfhosted.example.com"` to any
tool. Validation rejects non-HTTPS URLs (same rule as webhook URLs in Stripe MCP).

## UC-SB-9 Alias store for PATs (H2 v1.1)

**Status**: deferred.

**Reason**: not critical for single-project flow. When a developer manages
multiple Supabase projects, a `~/.specbox/supabase_tokens.json` store mapping
alias → PAT would remove the need to pass the raw token on every call.

**Contract sketch**:

```python
set_edge_secret(
    access_token_alias="motofan",  # resolves via alias store
    # OR: supabase_access_token="sbp_..." (literal takes precedence)
    ...
)
```

New error: `E_ALIAS_NOT_FOUND` if alias unknown.

## Integration test infrastructure (incremental)

Currently `tests/integration/test_supabase_e2e.py` exists as a stub. Full
integration requires a dedicated Supabase CI project and credentials exported
as `SUPABASE_CI_ACCESS_TOKEN` + `SUPABASE_CI_PROJECT_REF`. Defer until the
first real CI run demands it.
