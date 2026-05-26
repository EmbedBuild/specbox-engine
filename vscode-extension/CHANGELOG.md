# Changelog

All notable changes to the **SpecBox Engine** VSCode extension are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this extension adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
in lockstep with the SpecBox Engine itself (`extension.version === engine.version`).

## [Unreleased]

## [6.3.0] — "Native Default OAuth"

### Added
- **GitHub OAuth onboarding via cloud-mediated loopback flow.** New command
  `SpecBox: Sign in with GitHub` (`specbox.signIn`) opens a one-shot HTTP
  server on `127.0.0.1` (random port), redirects the browser to
  `https://cloud.specbox.build/vscode/issue-token`, validates the callback
  (CSRF state + token regex + origin allow-list), and persists the resulting
  `mcp_token` to VSCode SecretStorage (Keychain on macOS, Credential Manager
  on Windows, libsecret on Linux). 5-minute callback timeout.
- **Onboarding notification on first activate.** Once per workspace, users
  see a notification with exactly two choices: "Sign in with GitHub" or
  "Continue in local mode (FreeForm)". The decision is persisted to
  `workspaceState`; closing the notification without choosing is logged to
  `.quality/logs/onboarding.jsonl` and the notification reappears on the
  next activate. **No proactive auth notifications after the decision.**
- **Sidebar identity row.** The SpecBox status tree now leads with an
  identity item: `Signed in as @<handle>` with the GitHub icon when a token
  is in SecretStorage, or `Not signed in (FreeForm mode)` otherwise. Click
  opens a quick pick (`Sign out` / `Open profile` or `Sign in with GitHub`).
- **`specbox.signOut` and `specbox.identityQuickPick` commands.** Delete
  the SecretStorage token + restore underlying MCP config + respawn, and
  surface the identity quick pick from the Command Palette respectively.
- **`specbox.signInBaseUrl` setting.** Advanced override of the cloud
  sign-in URL — used by E2E tests against the mock cloud server.
- **MCP-launcher wrapper (`bin/mcp-launcher.mjs`).** Shim that the Claude
  Code MCP config invokes; forwards stdio to the underlying server process
  and lets the parent inject `SPECBOX_NATIVE_MCP_TOKEN` at spawn time so
  the plaintext token does not appear in the inner server command.
- **Server-side i18n.** Identity errors from the engine (`UNAUTHENTICATED`,
  revoked tokens) respect the client's `Accept-Language` header — EN
  default, ES fallback (engine UC-648, shipped in commit `a7410f8`).
- **OAuth test suite.** `tests/oauth.test.mjs` (11 cases) covers the
  loopback HTTP contract: loopback-only binding, single-use, state mismatch,
  invalid method, origin allow-list, token regex (accepts the
  cloud's `spbx_<base64url>` shape, rejects legacy 64-hex), success page
  rendering.
  `tests/oauth-integration.test.mjs` (3 cases) exercises the full mock-cloud
  ↔ loopback round trip, CSRF reject, and error propagation. Zero-deps
  via `node:test`. Wired in `package.json` as `npm test`.
- **CI workflow `oauth-e2e.yml`.** Runs compile + i18n linter + the OAuth
  suite on every PR touching `oauth.ts` / `secret-storage.ts` / `mcp.ts` /
  `auth.ts` / `extension.ts` / engine identity code.
- **Runbooks.** `doc/runbooks/freeform-only-mode.md` and
  `doc/runbooks/github-oauth-troubleshooting.md`.
- **ADR.** `doc/decisions/native_default_oauth.md` documents the partial
  break of the v5.29 FreeForm-first canonical decision, the auditable
  guarantees, and the rollback plan.

### Changed
- Identity polling: the extension polls `whoami()` every 60 seconds and
  refreshes the sidebar when the identity state changes. Combined with the
  engine's 30s auth cache TTL, revocation becomes visible in ≤90s.
- Default backend for **new** projects (templates) remains `freeform`
  pending owner confirmation; **existing** projects are unaffected.

### Security
- `mcp_token` is persisted exclusively to VSCode SecretStorage. The
  launcher wrapper handles env-var injection at spawn time so the inner
  Claude Code settings file does not record the plaintext token — see the
  ADR for the residual trade-off around `${secretStorage:specbox.mcpToken}`
  placeholder resolution.
- Loopback HTTP server binds **only** to `127.0.0.1`, accepts **exactly
  one** GET to `/callback`, validates origin against an allow-list, and
  auto-closes after 5 minutes.

## [6.2.0] — "VSCode Marketplace"

### Added
- **First Marketplace release.** The extension is now published at
  [marketplace.visualstudio.com](https://marketplace.visualstudio.com/items?itemName=EmbedBuild.specbox-engine)
  and installable in one click.
- **Lockstep versioning with SpecBox Engine.** Every tag on the engine repo
  publishes the corresponding extension version. The `scripts/sync-extension-version.sh`
  script enforces this, and the `/release` skill blocks tagging when drift is detected.
- **Internationalization (EN + ES).** The Marketplace listing, command titles,
  view names, walkthrough steps, settings descriptions, and runtime notifications
  are available in English (canonical) and Spanish (Spain neutral, tuteo standard).
  VSCode auto-resolves the language based on `vscode.env.language`.
- **Marketplace stats telemetry.** A daily GitHub Actions cron snapshots
  installs/downloads/rating from the public Marketplace REST API and persists
  the timeseries to `.quality/marketplace-stats.jsonl`. The new MCP tool
  `get_marketplace_stats` exposes the aggregated data. Zero PII, no active
  telemetry from the extension itself.
- New CI workflows under `.github/workflows/`:
  - `publish-vscode-extension.yml` — publishes on tag `v*.*.*` (stable) or `v*.*.*-rc*` (pre-release).
  - `smoke-test-marketplace.yml` — installs the published extension on a clean VSCode and validates activation + locale matrix (`en`, `es`).
  - `marketplace-stats.yml` — daily stats snapshot.

### Changed
- `engines.vscode` bumped from `^1.85.0` to `^1.86.0` to enable `vscode.l10n` runtime localization.
- `@types/vscode` bumped from `^1.85.0` to `^1.86.0`.
- `repository.url`, `bugs.url`, `homepage` now point to the correct GitHub repo
  (`EmbedBuild/specbox-engine`). The Marketplace publisher is `EmbedBuild`.
- `package.json` metadata extended with `galleryBanner`, `pricing: Free`, `qna: false`,
  and explicit `bugs` / `homepage` URLs.
- Runtime user-facing strings in `extension.ts` and `health.ts` now route through
  `vscode.l10n.t(...)`. The remaining four files (`install.ts`, `mcp.ts`, `onboard.ts`,
  `updater.ts`) are tracked as follow-up in `scripts/lint-extension-strings.mjs`
  allowlist.

### Fixed
- `viewsWelcome` link no longer points to a non-existent `jpsdeveloper/specbox-engine`
  GitHub URL — corrected to `EmbedBuild/specbox-engine`.
- Removed reference to the deleted "SpecBox: Open Sala de Maquinas" command
  (eliminated in engine v6.1.0 Cloud Cutover).

## Earlier versions

This is the first version published to the VSCode Marketplace. Internal VSIX
versions before 6.2.0 (the most recent being 5.21.1) were distributed manually
via the `install-ext.mjs` script bundled with the SpecBox Engine repository.
The engine itself has its own [CHANGELOG.md](https://github.com/EmbedBuild/specbox-engine/blob/main/CHANGELOG.md)
covering the full version history.
