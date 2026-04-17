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

## References

- PRD: `doc/prd/specbox_stripe_mcp_prd.md`
- Main tracking: SpecBox FreeForm board `ff-2051992d4368`, US-SPECBOX-STRIPE
- H1 milestone (shipped): UC-1, UC-2, UC-3, UC-4, UC-8, UC-9, UC-10
- H2 milestone (blocked on dependency): UC-7
- H3 milestone (v1.1 backlog): UC-5, UC-6
