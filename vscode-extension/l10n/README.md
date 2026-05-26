# l10n bundles

Runtime translations for SpecBox Engine VSCode extension. Loaded by `vscode.l10n` (requires VSCode ≥ 1.86).

- `bundle.l10n.json` — English source (canonical, fallback).
- `bundle.l10n.es.json` — Spanish translation (Spain neutral, tuteo standard).

Key convention: each key is the literal English string, per `vscode-l10n` spec.

## Adding a new locale

1. Create `bundle.l10n.<lang>.json` with the same keys as `bundle.l10n.json`.
2. Add `package.nls.<lang>.json` for the static manifest strings (commands, settings).
3. Update `tests/test_l10n_parity.py` to include the new locale.

## Coverage

Currently localised: `extension.ts`, `health.ts`, `statusbar.ts`, `constants.ts`, `util.ts`, `views/*.ts`.

Pending follow-up (tracked in `scripts/lint-extension-strings.mjs` ALLOWLIST_FILES):
- `install.ts`
- `mcp.ts`
- `onboard.ts`
- `updater.ts`

Once those files are refactored, remove the entry from `ALLOWLIST_FILES` and the linter will enforce.
