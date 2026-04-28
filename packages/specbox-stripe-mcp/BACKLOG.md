# Backlog — specbox-stripe-mcp

## UC-5 `setup_test_sellers` (H3 — v1.1)

**Status**: deferred to v1.1

**Reason**: not in the critical path to close the moto.fan use case (that was
T1-T4 + set_edge_secret). Seeds N test sellers for E2E and manual-test workflows.
Out of scope for H1 alpha.

**Contract sketch** (per PRD §5, T5):

```python
setup_test_sellers(
    stripe_api_key: str,
    count: int,                  # 1-10
    country: str = "ES",
    email_pattern: str = "specbox-test-{idx}+{timestamp}@example.com",
    capabilities: list[str] = ["card_payments", "transfers"],
    generate_onboarding_links: bool = True,
    auto_complete_onboarding: bool = False,  # test_mode only; needs research
) -> {
    "sellers": [
        {"account_id", "email", "country", "onboarding_url", "status",
         "specbox_test_seller_idx"},
        ...
    ]
}
```

Idempotency by `metadata.specbox_test_seller_idx`. Blocked in live mode with
`auto_complete_onboarding=true`.

**Open research items**:
- Stripe test helpers — how much of KYC can we automate with Jenny Rosen / SSN
  000-00-0000 / bank number `STRIPE_US_BANK_ACCOUNT_NUMBER`?
- Whether test accounts can be marked `charges_enabled=true` without manual
  intervention.

---

## UC-6 `teardown_test_mode` (H3 — v1.1)

**Status**: deferred to v1.1

**Reason**: DX tool, not required for the first production run. Removes all
SpecBox-managed resources from test-mode accounts between iterations.

**Contract sketch** (per PRD §5, T6):

```python
teardown_test_mode(
    stripe_api_key: str,
    confirm_token: str,                 # literal: "I understand this deletes test mode data"
    scope: list[str] = ["webhooks", "products", "prices", "sellers"],
) -> {"deleted": {"webhooks": N, "products": N, ...}, "errors": []}
```

**Safety**:
- Hardcoded deny if `stripe_api_key.startswith("sk_live_")` — no escape hatch.
- `confirm_token` must match literal exactly.
- Writes a pre-action Engram observation with the exact IDs about to be touched.
- Archives products/prices (Stripe forbids DELETE when prices are referenced);
  DELETE for webhooks; `Account.reject` for test sellers.

**Note**: the integration test teardown fixture (`tests/integration/conftest.py`)
already implements this behavior ad-hoc and is a good reference.

---

## UC-7 Integration with skill `/stripe-connect` Paso 9.5 (H2 — blocked)

**Status**: BLOCKED

**Blocker**: sibling MCP tool `specbox-supabase.set_edge_secret` does not yet
exist. Its PRD has not been written (tracked separately).

**Why it matters**: without `set_edge_secret`, the full moto.fan end-to-end
flow still requires the developer to copy 4 secrets manually into the Supabase
dashboard. That is exactly the manual step the PRD argues against.

**What's needed to unblock**:

1. Write PRD for `specbox-supabase-set-edge-secret` (pending).
2. Implement that tool in a new `packages/specbox-supabase-mcp/` package (same
   layout as this one).
3. Wire both MCPs into `/stripe-connect` skill Paso 9.5 (described in full
   detail in PRD §7 of this package).

Until that's done, developers consuming `specbox-stripe-mcp` will need to
handle secret injection manually — but the MCP itself is usable standalone
(T1-T4 already cover the Stripe-side automation).

**Acceptance criteria** (deferred — see SpecBox board UC-7 for the full list):

- Skill `/stripe-connect` updated with Paso 9.5 that invokes T1 → T2 → T3 →
  `set_edge_secret` → T4 in order.
- If get_setup_status returns `verdict=ready`, Paso 11 shows only 1 manual
  action (activate Connect).
- Graceful degradation if specbox-stripe MCP is unavailable — skill falls back
  to 4 manual steps.
- Skill aborts early with dashboard URL if `verify_connect_enabled` returns
  `enabled=false`.

---

## Alias store / OAuth v2 — promoted from H3 to H2

**Status**: planned for v0.3 (was previously v1.1 backlog).

**Why promoted**: US-STRIPE-SWITCH-ACCOUNT (FreeForm board `ff-bc73b5d69f91`)
needs an alias store as a hard dependency. Switching the active Stripe account
of a SpecBox project requires holding multiple credentials at once (e.g.
`prod` and `staging`), addressing them by alias instead of passing raw
`sk_live_*` / `sk_test_*` strings, and rotating them safely. The switch
workflow cannot be implemented on top of v0.2 alone.

**Sketch contract**:

```python
# Encrypted at rest (.claude/secrets/stripe_aliases.enc.json) using AES-256-GCM
# with a key derived from the macOS Keychain (or a passphrase fallback).
store_stripe_alias(alias_name="prod", stripe_api_key="sk_live_...", project_path=".")
list_stripe_aliases(project_path=".")  # → names + last_used_at + key mode (test/live), no values
delete_stripe_alias(alias_name="legacy", project_path=".", confirm_token="…literal…")

# Existing tools take account_alias as an alternative to stripe_api_key.
verify_account_setup(account_alias="prod", account_mode="connect")
```

**Open items**:
- Where to derive the encryption key from on Linux/Windows when there is no
  macOS Keychain. Probably libsecret + DPAPI fallback chain.
- Migration of in-memory keys passed via the existing `stripe_api_key`
  argument — keep both signatures or force aliases?

---

## References

- PRD: `doc/prd/specbox_stripe_mcp_prd.md`
- Main tracking: SpecBox FreeForm board `ff-2051992d4368`, US-SPECBOX-STRIPE
- v0.2 tracking: SpecBox FreeForm board `ff-bc73b5d69f91`, US-STRIPE-MCP-V2
- H1 milestone (shipped, v0.1): UC-1, UC-2, UC-3, UC-4, UC-8, UC-9, UC-10
- v0.2 milestone (shipped, US-STRIPE-MCP-V2): account_mode discriminator on T1/T2/T4
- H2 milestone (planned for v0.3): UC-7 (Paso 9.5 wiring) + alias store / OAuth v2
- H3 milestone (v1.1 backlog): UC-5 setup_test_sellers, UC-6 teardown_test_mode
