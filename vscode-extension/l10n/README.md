# l10n bundles

Runtime translations for SpecBox Engine VSCode extension. Loaded by `vscode.l10n` (requires VSCode ≥ 1.86).

- `bundle.l10n.json` — English source (canonical, fallback).
- `bundle.l10n.es.json` — Spanish translation (Spain neutral, tuteo standard).

Key convention: each key is the literal English string, per `vscode-l10n` spec.

## Adding a new locale

1. Create `bundle.l10n.<lang>.json` with the same keys as `bundle.l10n.json`.
2. Add `package.nls.<lang>.json` for the static manifest strings (commands, settings).
3. Add the new bundle to `tests/l10n.test.mjs`.

## Coverage

Every file in `src/` is localised (US-57/UC-5702). `npm test` runs `tests/l10n.test.mjs`, which fails when:

- a text passed to `vscode.l10n.t` (or its `const t = vscode.l10n.t` alias) is missing from either bundle;
- a `vscode.l10n.t` key is not a string literal (it could never be translated);
- the two bundles, or the two `package.nls` files, do not have the same keys;
- an English value differs from its key, or a Spanish value is empty or loses a `{0}` placeholder;
- `scripts/lint-extension-strings.mjs` finds a notification, dialog, progress title/step, terminal
  or status-bar text written as a literal outside `vscode.l10n.t`.

A literal that is a product name rather than copy (the `SpecBox` output channel) carries
`l10n-lint:ignore` on its line.

Not localised on purpose: the content of the skill cards (`views/skill-defaults.ts` and the
description in each `SKILL.md`) is the skills' own documentation.
