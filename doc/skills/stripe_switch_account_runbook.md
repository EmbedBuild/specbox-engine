# Runbook — `/stripe-switch-account`

> Detailed operational playbook for the Stripe credentials rotation skill.
> Read the [SKILL.md](.claude/skills/stripe-switch-account/SKILL.md) first
> for the conceptual overview.

## When to use

Use `/stripe-switch-account` when you need to **change which Stripe account
backs a SpecBox project's infrastructure**. Common cases:

| Case | from → to | Notes |
|------|-----------|-------|
| Going to production | `staging` (sk_test) → `prod` (sk_live) | First-time live launch |
| Splitting from a partner | `joint_prod` → `solo_prod` | New legal entity, customers stay where they are |
| Incident rollback | `prod` → `staging` | Diagnose the issue without serving prod traffic |
| Refresh compromised key | `prod_old` → `prod_new` | When `sk_live_*` may have leaked |
| Test → test environment swap | `staging` → `dev` | Two test accounts, e.g. for two devs |

**Do NOT use this skill for**:

- Migrating customers/subscriptions across Stripe accounts (impossible by Stripe design — the source-of-truth lives in the account that created them).
- Switching between Connect and Standard modes (it's a `/stripe-connect` ↔ `/stripe-standard` re-scaffold, not a credential rotation).

## Pre-conditions checklist

Before running the skill, ensure:

- [ ] Both `sk_*` keys are valid and not expired.
- [ ] You have at least 2 aliases in the encrypted store (`from` and `to`).
- [ ] `specbox-stripe-mcp` v0.3+ is registered in `.claude/settings.local.json`.
- [ ] (Recommended) `specbox-supabase-mcp` is also registered for auto-rotation of Edge Function secrets.
- [ ] You have a Supabase Personal Access Token (`SUPABASE_ACCESS_TOKEN`) with project-edit scope, and the project_ref (e.g. `abcd1234`).
- [ ] You know which `account_mode` your project uses (`standard` or `connect`). When unsure, run `mcp__specbox-stripe__get_setup_status_tool` against the source account first.
- [ ] `.gitignore` includes `.claude/secrets/` (the alias store auto-adds this on first use; verify with `grep -q "\\.claude/secrets/" .gitignore`).

## Choose your scope_action

The single most important decision in the flow.

| Action | Effect on source | When to use | Reversible? |
|--------|------------------|-------------|-------------|
| `keep_old_active` | None | **Default**. You want a quick rollback path. The source still receives webhooks for legacy customers; if you find a bug post-switch, swap back. | Yes |
| `archive_products_only` | Source's SpecBox-managed products marked `active=false` | The source must stop accepting NEW signups but legacy subs keep renewing on it. | Partially — un-archive products manually |
| `deactivate_webhooks_only` | Source's SpecBox-managed webhooks `disabled=true` | You want the source to stop reporting events to your app, but products remain orderable from outside. Rare case. | Yes — re-enable in dashboard |
| `full_archive` | Above + cancel all SpecBox-managed subscriptions on source | Permanent decommission of the source. Customers will get cancellation emails immediately. | **No** — canceled subs cannot be uncanceled |

**Rule of thumb**: start with `keep_old_active` for the first switch. Once
production has been stable on the destination for a week, consider running
the skill again with `archive_products_only` to prevent further confusion.

`full_archive` requires the literal `confirm_token` and should never be
used the same day as the switch — give yourself buffer to roll back.

## Walkthrough — happy path

```bash
# 0. (one-off) Register your Stripe credentials in the alias store
mcp__specbox-stripe__store_stripe_alias_tool({
  alias_name: "staging",
  stripe_api_key: "sk_test_...",
  project_path: "/Users/me/projects/myapp"
})
mcp__specbox-stripe__store_stripe_alias_tool({
  alias_name: "prod",
  stripe_api_key: "sk_live_...",
  project_path: "/Users/me/projects/myapp"
})

# 1. Run the skill
/stripe-switch-account
# → from: staging
# → to:   prod
# → mode: standard
# → scope_action: keep_old_active
# Skill runs dry_run=true, shows the plan, asks for "Yes, switch from staging to prod"
# You confirm.
# Skill runs dry_run=false, replicates webhooks + products, pushes secrets to Supabase.
# ✅ Switch completed in ~12s.

# 2. Smoke-test
stripe listen --forward-to https://abcd1234.supabase.co/functions/v1/stripe-webhook
# In another terminal: trigger a test signup with card 4242
# Verify the customer appears in https://dashboard.stripe.com/customers (LIVE dashboard, not test).

# 3. (Optional, after 1 week stable) Lock down the source
/stripe-switch-account
# → from: prod
# → to:   prod   ← yes, same alias — this is just a re-run of the scope_action
# Wait, that's an error. The skill rejects from==to.
# Instead, manually invoke:
mcp__specbox-stripe__switch_stripe_account_tool({
  ...same args as before...
  scope_action: "archive_products_only",
  dry_run: false
})
```

Note the limitation in step 3: the skill's UX is for switching, not for
applying a delayed scope_action. The MCP tool can be invoked directly for
that case.

## Walkthrough — rollback

If you decide to rollback because the destination has issues:

```bash
/stripe-switch-account
# → from: prod      (the new one we switched to)
# → to:   staging   (the old one we left as keep_old_active)
# → scope_action: keep_old_active   (don't lock down prod yet — you may want to re-switch)
```

This works because we left `staging` active. If we had used `full_archive`
on the original switch, this rollback would not work — there would be
nothing to switch back to.

## Failure modes

### Webhook URL doesn't resolve from Stripe's network

Symptom: `setup_webhook_endpoints` succeeds (Stripe accepts the URL syntactically) but the destination starts getting `500 Endpoint not reachable` warnings in the Stripe dashboard.

Cause: a typo in `platform_url`, or DNS not propagated yet.

Fix: edit the webhook in the dashboard manually, or re-run the skill with the corrected URL — idempotency means it'll update in place.

### Supabase secrets push fails mid-way

Symptom: `E_SUPABASE_WRITE_FAILED` after webhook creation succeeded.

What the journal does: the webhook on destination is **not** rolled back automatically (it's idempotent — re-running converges). Only the secrets attempt is undone (which is a no-op since nothing was written).

Fix: re-run with `dry_run=false` after fixing the Supabase issue.

### Rollback partially fails

Symptom: `runbook_path` is non-null in the response. `doc/SWITCH_FAILURE_RUNBOOK.md` exists.

What to do:
1. Open the runbook.
2. Walk through the manual recovery checklist top-to-bottom.
3. Once stable, run `mcp__specbox-stripe__get_setup_status_tool({account_mode, ...})` against both accounts to confirm consistent state.
4. Delete the runbook file when done.

## Integration testing locally

Two Stripe test accounts are required (Stripe gives you 1 by default; create a second one in your Stripe Dashboard under "Account settings" → "Profile" → switch account dropdown → "Create new account").

```bash
export STRIPE_CI_SECRET_KEY_A="sk_test_..."  # first test account
export STRIPE_CI_SECRET_KEY_B="sk_test_..."  # second test account

# Store both as aliases in a sandbox project.
export SPECBOX_ALIAS_PASSPHRASE="ci-passphrase"
mcp__specbox-stripe__store_stripe_alias_tool({alias_name:"a", stripe_api_key:"$A", project_path:"/tmp/ci"})
mcp__specbox-stripe__store_stripe_alias_tool({alias_name:"b", stripe_api_key:"$B", project_path:"/tmp/ci"})

# Switch a → b
mcp__specbox-stripe__switch_stripe_account_tool({
  from_alias:"a", to_alias:"b", account_mode:"standard",
  project_path:"/tmp/ci",
  platform_url:"https://example.com/webhook",
  platform_events:["customer.subscription.updated"],
  scope_action:"keep_old_active",
  dry_run:false
})

# Switch b → a (round trip)
mcp__specbox-stripe__switch_stripe_account_tool({
  from_alias:"b", to_alias:"a", account_mode:"standard",
  project_path:"/tmp/ci",
  platform_url:"https://example.com/webhook",
  platform_events:["customer.subscription.updated"],
  scope_action:"keep_old_active",
  dry_run:false
})
```

Both invocations should report `dry_run=False` and `created_or_reused`
matching expectations. The second invocation in the same direction should
report `reused` for everything (idempotency check).

## Security notes

- Plaintext `sk_*` keys live in memory only during the call — they enter via the alias store decrypt and never get logged, persisted, or sent to Engram.
- Webhook signing secrets (`whsec_*`) are returned from the destination account's webhook creation and pushed to Supabase. If specbox-supabase-mcp is unavailable, they get written to `doc/PENDING_SWITCH_SECRETS.md` (which is your responsibility to handle — `git status` will show it; **do not commit it**).
- The encrypted alias store at `.claude/secrets/stripe_aliases.enc.json` should never be committed. The skill checks `.gitignore` on first store and adds the entry, but if you copy-pasted a project from elsewhere, double-check.
- Master key derivation: macOS Keychain entry `com.specbox.stripe-alias-store` (preferred) or PBKDF2-HMAC-SHA256 from `SPECBOX_ALIAS_PASSPHRASE` (480k iterations). Both produce a 256-bit key fed into AES-256-GCM with a fresh 96-bit nonce on every write.
- The alias store does NOT support per-alias keys — losing the master key means losing all aliases. Plan for this: keep your `sk_*` keys recoverable from Stripe Dashboard separately (every Stripe account lets you regenerate them).

## Glossary

- **alias**: a user-friendly name (e.g. "prod", "staging") for a Stripe API key, stored encrypted in the project.
- **account_mode**: 'standard' (single Stripe account, no Connect) or 'connect' (marketplace platform with sellers).
- **scope_action**: what the tool does to the source account once destination is converged.
- **dry_run**: when true (default), show the plan without mutating anything.
- **journal**: append-only log of mutating operations, replayed in reverse on rollback.
- **runbook**: human-readable manual recovery guide written when rollback itself fails.
