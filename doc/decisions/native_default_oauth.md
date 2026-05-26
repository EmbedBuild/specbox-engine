# ADR — Native Default OAuth (v6.3.0)

- **Status**: Accepted
- **Date**: 2026-05-27
- **Tracking**: FreeForm board `ff-ed0c02f4565a` / US-VSCODE-GITHUB-OAUTH
- **Plan**: [doc/plans/US-VSCODE-GITHUB-OAUTH_plan.md](../plans/US-VSCODE-GITHUB-OAUTH_plan.md)
- **PRD**: [doc/prd/US-VSCODE-GITHUB-OAUTH_prd.md](../prd/US-VSCODE-GITHUB-OAUTH_prd.md)
- **Discovery**: [doc/discovery/us_vscode_github_oauth/icp_jtbd.md](../discovery/us_vscode_github_oauth/icp_jtbd.md)
- **Cross-repo dependency**: `EmbedBuild/specbox_cloud` US-09

## Context

Prior to v6.3.0 there was no first-class onboarding path for Native backend
users. A developer who wanted multi-developer reservations had to:

1. Manually create a Supabase user.
2. Manually generate an `mcp_token` via the cloud's REST API or psql.
3. Manually paste that token into `.claude/settings.local.json` as an env
   var on the SpecBox-MCP server entry.

This violated the **"zero plaintext on disk"** spirit and required a
non-obvious sequence of steps that excluded everyone except internal
maintainers from the Native backend.

The v5.29 canonical decision had also set `freeform` as the default backend
for new projects, on the grounds that FreeForm was the lower-friction path
and Native was opt-in for power users.

## Decision

Ship a first-class sign-in flow in the VSCode extension that:

1. Uses **cloud-mediated GitHub OAuth** (the cloud does the dance; the
   extension only consumes the resulting token).
2. Uses the **loopback HTTP server pattern** (`127.0.0.1` random port, one-shot)
   so the extension never needs an exposed callback URL.
3. Persists the token **only** to VSCode SecretStorage — never to disk in
   plaintext.
4. Surfaces the choice via an **onboarding notification on first activate**
   with exactly two options: "Sign in with GitHub" or "Continue in local mode
   (FreeForm)". Closing the X is **not** a decision — the notification
   reappears next session.
5. Shows the current identity in the **sidebar** and on the **status bar**
   so users always know which mode they are in.

Native becomes the **recommended default for all new projects**.
FreeForm stays first-class for solo and air-gapped users.

**Implementation site**: `server/tools/onboarding.py`. The
module-level constant `DEFAULT_BACKEND_TYPE = "native"` and the helper
`resolve_default_backend_type()` materialize the decision. Pre-v6.3.0
the default in the same call site was `"freeform"` (v5.29.0 PR-8).

**Backwards compatibility**: existing projects are **not migrated**.
`detect_backend()` (the runtime resolver in `server/app_docs/discovery.py`)
still falls back to `"freeform"` when no explicit signal is present in
`.claude/settings.local.json` or in `doc/app/app_spec.md`. Only NEW
onboards via `onboard_project()` without an explicit `backend_type` get
`"native"` from v6.3.0 onwards.

Owner sign-off on this default flip: **confirmed** in conversation on
2026-05-27 during the `/implement US-VSCODE-GITHUB-OAUTH` session.

## Three auditable guarantees

1. **`docs_url` in every UNAUTHENTICATED error.** The four native tools
   (`whoami`, `reserve_uc`, `release_uc`, `register_native_branch`) now
   return a uniform payload `{status: "unauthenticated", code:
   "UNAUTHENTICATED", message, docs_url, locale}` instead of a stack
   trace. The `docs_url` points at the README section "How sign-in works
   under the hood". Implemented in `server/coordination/i18n_messages.py`
   + `server/tools/coordination.py`, verified by
   `tests/test_native_unauthenticated.py`.

2. **≤30s revoke visibility from the server.** `mcp_tokens.revoked_at` is
   read through a 30-second TTL cache
   (`server/coordination/identity.py:_CACHE_TTL_SECONDS = 30`). A revoke on
   the cloud propagates to the local MCP within 30 seconds without
   restarting anything. Combined with the extension's 60-second sidebar
   polling, total user-visible revoke latency is ≤90s.

3. **Opt-out persistence.** Once a user picks "Continue in local mode
   (FreeForm)", the decision is stored in `workspaceState` under
   `specbox.onboardingDecision`. The extension does **not** show proactive
   auth notifications afterwards — verified by integration test (10
   simulated activates in FreeForm mode → 0 calls to
   `vscode.window.showInformationMessage` with auth CTAs).

## Drift from app_market

The v5.29 canonical decision (FreeForm as default backend) is **partially
broken** here: Native is now the recommended path for multi-developer
scenarios. We did not invent this drift unilaterally — it is the natural
outcome of (a) US-VSCODE-MARKETPLACE landing first-class Marketplace
distribution in v6.2.0, and (b) the cloud cutover in v6.1.0 removing the
specbox-control-panel dashboard in favor of an external cloud panel.

The Discovery output explicitly classifies this as
`documented_exception` rather than `feature_creep_rejected` — the
multi-developer experience was a known gap, not scope creep.

## Trade-offs accepted

### Token in env var, not in SecretStorage at the MCP-server level

The plan's Option B called for a `mcp-launcher.mjs` wrapper that reads the
token from SecretStorage and injects it as an env var into the spawned
MCP server. We shipped the **structural** version of this wrapper but the
actual SecretStorage → wrapper hand-off relies on VSCode's
`${secretStorage:...}` placeholder resolution in `mcpServers.env` values,
which is **how Claude Code's MCP integration consumes the token**.

If a future audit finds that Claude Code does not yet support
`${secretStorage:...}` placeholder resolution, the wrapper degrades to the
**plan's Option A** (plaintext env var in `settings.local.json`) with the
trade-off noted in the CHANGELOG. The SecretStorage primary store remains
intact regardless — only the spawn-time hand-off is affected.

We deliberately accept this residual trade-off because:

- The token is **already revocable** server-side in ≤30s — a leak is
  bounded in damage.
- The user is **always told** the extension stores a secret (via the
  onboarding notification copy).
- The hand-off improvement is **a v6.4+ follow-up**, not a v6.3.0 blocker.

### Loopback HTTP server in an extension

Microsoft's Marketplace policy allows loopback servers in extensions — the
pattern is widely used by Cursor, Continue.dev, and Copilot Chat. The
extension binds **only** to `127.0.0.1`, accepts **only** GET requests on
`/callback`, validates origin against an allow-list (only
`https://cloud.specbox.build`), accepts the callback **exactly once**, and
auto-closes after 5 minutes. The implementation lives in
`vscode-extension/src/oauth.ts` and is covered by 10 unit tests.

## Alternatives rejected

| Alternative | Why we rejected it |
|---|---|
| `vscode.authentication.getSession('github', ...)` (built-in VSCode GitHub auth) | Returns a GitHub access token that the engine does not need. Native backend needs an `mcp_token` provisioned by the cloud, not a GitHub PAT. |
| Polling Supabase from the extension with `vscode.env.asExternalUri` | Adds a long-poll on the client and a Supabase dependency in the extension. The cloud-mediated loopback flow is strictly simpler. |
| Device code flow (`https://github.com/login/device`) | Bad UX (paste a code into a browser tab manually). Loopback works because the extension can self-bind a port. |
| OAuth client baked into the extension | Requires shipping a client secret in the .vsix, which is leaked the moment the extension is downloaded. The cloud holds the OAuth secret. |

## Rollback plan

If v6.3.0 introduces a critical defect in the OAuth flow:

1. Revert `vscode-extension/src/{oauth.ts,secret-storage.ts,auth.ts}` and the
   `extension.ts` wiring of `specbox.signIn` / `specbox.signOut` /
   `specbox.identityQuickPick`.
2. Revert the `mcp.ts` handshake helpers (`updateMcpServerConfigWithToken`,
   `clearMcpServerConfig`, `respawnMcpServer`).
3. The server-side UNAUTHENTICATED graceful from UC-648 stays — that change
   improves error messages even without OAuth and has no rollback cost.
4. Release a v6.3.1 patch with the rollback. Users who already signed in
   keep their token in SecretStorage; the next sign-in attempt fails
   cleanly because the new commands are gone.

The rollback is intentionally **conservative**: the engine-side changes
(UC-648) survive because they ship value independently of the
client-side OAuth. The extension changes (UC-644..UC-647, UC-649, UC-650,
UC-651) revert as a single unit.

## Cross-repo dependency

This US is one half of a cross-repo feature. The cloud half lives in
`EmbedBuild/specbox_cloud` US-09 (**merged 2026-05-27** in
[PR #47](https://github.com/EmbedBuild/specbox_cloud/pull/47)) and implements:

- `GET /vscode/issue-token?return_to=<loopback>&state=<csrf>` — the
  endpoint the extension redirects the browser to.
- `POST /api/mcp-tokens/issue-for-self` — the API that issues a fresh
  `mcp_token` for the currently authenticated developer (called by the
  page server-side, never by the extension directly).
- The GitHub OAuth dance via Supabase + token provisioning into
  `panel.mcp_tokens`.

**Contract surface (frozen on both sides)**:

| Surface | Value |
|---|---|
| Cloud URL | `https://cloud.specbox.build/vscode/issue-token` |
| Query params (extension → cloud) | `return_to=<URI-encoded loopback>` + `state=<64-hex>` |
| `return_to` regex (cloud-side guard) | `^http://127\.0\.0\.1:\d+/callback$` |
| `state` regex (cloud-side guard) | `^[0-9a-f]{64}$` |
| Success redirect | `<return_to>?mcp_token=<clear>&state=<csrf>` |
| Failure redirect | `<return_to>?error=<code>&error_description=<msg>&state=<csrf>` |
| `clear_token` shape | `spbx_<base64url(32 bytes)>` — issued by the cloud's `issueMcpToken()` |
| Token regex (engine-side guard, `oauth.ts`) | `^spbx_[A-Za-z0-9_-]{32,128}$` |

The engine half ships and is tested against a **mock cloud server**
(`vscode-extension/tests/mock-cloud-server.mjs`) that mirrors the
contract above. The cross-stack live test in the cloud's
`tests/e2e/steps/vscode-self-service.steps.ts` verified the same shape
against the real Supabase + API at merge time.

## Engram references

- `architecture/vscode-github-oauth` topic — the design conversation
  leading to this ADR.
- `architecture/freeform-defenses-permanent` — the v6.2 revision that kept
  the v5.29 path defenses in place. This ADR is consistent with that
  decision (FreeForm is not deprecated, just no longer the only path).
