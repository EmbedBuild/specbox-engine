# Changelog — specbox-stripe-mcp

All notable changes to this package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-04-29

### Added

- **`account_mode` discriminator** on `verify_account_setup`,
  `setup_webhook_endpoints`, and `get_setup_status`. Two values:
  - `standard` — SaaS, e-commerce, B2B. Skips Connect-specific checks. Creates
    a single webhook endpoint (platform-scope only).
  - `connect` — marketplace platforms. Preserves v0.1 behavior: optional
    Connect canary, two webhook endpoints (platform + connect), Connect
    activation check.
- New tool `verify_account_setup` exposed as `verify_account_setup_tool` over
  MCP. Replaces `verify_connect_enabled` for new code.
- `data.account_mode` field on every tool's response so callers can
  introspect which mode produced the envelope.
- Cross-mode isolation in `setup_webhook_endpoints`: an endpoint stamped with
  one `specbox_account_mode` is never reused by a caller asking for a
  different mode. The idempotency-key includes `account_mode` for the same
  reason.
- Silent migration of v0.1 webhook endpoints (those without
  `specbox_account_mode` in metadata): on first reuse the endpoint is stamped
  with the requested mode via `WebhookEndpoint.modify` with no new endpoint
  creation. The caller-visible outcome is `created_or_reused="reused"`.
- New error code `E_INVALID_ARGUMENT` for `account_mode` not in the literal
  set or for cross-mode misuse (e.g. `connect_events` in standard mode).
- New error code `E_MISSING_ARGUMENT` replacing `E_INVALID_INPUT` for the
  specific case of `connect_events` missing in `connect` mode.
- Telemetry: heartbeats now carry an `account_mode` field for segmentation.
- 4 new integration tests covering both modes (standard flow, connect flow,
  standard idempotency, mode isolation), gated by `STRIPE_CI_SECRET_KEY`.

### Changed

- `setup_webhook_endpoints`: `connect_events` is now `list[str] | None` (was
  required). Required only when `account_mode='connect'`. Passing it in
  standard mode returns `E_INVALID_ARGUMENT`.
- `setup_webhook_endpoints`: `connect_url` rejected in standard mode with
  `E_INVALID_ARGUMENT`. In connect mode it still defaults to `platform_url`.
- `get_setup_status` checks shape: `connect_webhook_endpoint` and
  `connect_enabled` keys are absent in standard mode. Verdict and remediation
  hints are mode-aware (no "activate Connect" hint in standard).
- `get_setup_status`: `expected_connect_events` in standard mode is ignored
  with a warning rather than rejected.

### Deprecated

- `verify_connect_enabled` is now a thin alias around
  `verify_account_setup(account_mode='connect')`. Emits `DeprecationWarning`.
  Removal planned for v0.3.

### Migration guide v0.1 → v0.2

Existing v0.1 callers need exactly two mechanical changes:

1. **Add `account_mode='connect'`** to every call to `setup_webhook_endpoints`
   and `get_setup_status`. The tools now require it.
2. **(Optional) replace `verify_connect_enabled`** with
   `verify_account_setup(account_mode='connect')`. The old name keeps working
   but emits a `DeprecationWarning` and will be removed in v0.3.

```diff
-from specbox_stripe_mcp.tools.verify_connect_enabled import verify_connect_enabled
+from specbox_stripe_mcp.tools.verify_account_setup import verify_account_setup

-verify_connect_enabled(stripe_api_key=KEY)
+verify_account_setup(stripe_api_key=KEY, account_mode="connect")

 setup_webhook_endpoints(
     stripe_api_key=KEY,
+    account_mode="connect",
     platform_url=URL,
     platform_events=["account.updated"],
     connect_events=["customer.subscription.created"],
 )

 get_setup_status(
     stripe_api_key=KEY,
+    account_mode="connect",
     expected_webhook_url=URL,
 )
```

Webhook endpoints created by v0.1 keep working — the first v0.2 reuse
silently stamps `specbox_account_mode` in their metadata. No re-creation, no
secret rotation, no service interruption.

## [0.1.1] — 2026-04-28

### Fixed

- `StripeObject.get()` AttributeError under Python 3.14 caused by
  `__getattr__` intercepting the `.get()` call. All tools now normalize
  Stripe objects via `lib.stripe_utils.as_dict` / `as_dict_list` before
  calling `.get()`. See `tests/unit/test_stripe_object_py314.py` for the
  regression suite.

## [0.1.0] — 2026-04-17

### Added

- Initial alpha release. T1 (`verify_connect_enabled`),
  T2 (`setup_webhook_endpoints`), T3 (`setup_products_and_prices`),
  T4 (`get_setup_status`) covering Connect Express setup-as-code for SpecBox
  skills. Engram + heartbeat telemetry. Live-mode opt-in safety gate.
