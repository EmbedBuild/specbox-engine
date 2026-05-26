# Changelog

All notable changes to the **SpecBox Engine** VSCode extension are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this extension adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
in lockstep with the SpecBox Engine itself (`extension.version === engine.version`).

## [Unreleased]

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
