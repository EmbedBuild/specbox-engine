# Runbook — Local mode (FreeForm)

> Audience: developers who want to run SpecBox Engine with the board in their own repository,
> without SpecBox Cloud. FreeForm remains first-class and free — no degraded experience.

## TL;DR

1. On first activate, pick **"Continue in local mode (FreeForm)"**.
2. The extension writes `specbox.backend_type = "freeform"` and
   `specbox.freeform_root_absolute = <workspace>/doc/tracking` to
   `.claude/settings.local.json`.
3. It then asks you to **Sign in with GitHub** (UC-11013). It is free and only connects this
   computer to the hosted MCP: the board stays in `doc/tracking/` of your repository.

## The hosted MCP needs an account from 30 October 2026

From **2026-10-30** the hosted MCP (`mcp.specbox.build`) rejects every connection without a token
(`401 token_required`, UC-3901), FreeForm included. Signing in with GitHub, or `npx specbox login`
in a terminal, gives this computer its token; Claude Code sends it on every connection. Until you
sign in, the extension's Status view shows the date and a startup reminder appears at most once a
day. If you run the MCP server yourself over stdio, no account is needed.

## What works in FreeForm

| Capability | Works in FreeForm? |
|---|---|
| `/prd`, `/plan`, `/implement`, `/audit`, `/visual-setup`, `/feedback` | ✅ |
| Stitch MCP design generation | ✅ (requires Stitch API key, unrelated to SpecBox auth) |
| Engram persistent memory | ✅ |
| Trello backend | ✅ (you provide your own Trello API key + token) |
| Plane backend | ✅ (you provide your own Plane API key) |
| The 100+ MCP tools that read/mutate project state | ✅ |
| Native backend (`whoami`, `reserve_uc`, `release_uc`, `register_native_branch`) | ❌ — SpecBox Cloud |

The MCP tools go through the hosted MCP, so from 2026-10-30 they need the account (above).

## FreeForm with the remote MCP: fragments (UC-11103)

The hosted MCP cannot read your repository, so the board travels with each call. Until 6.29.1
the whole `doc/tracking/items.json` went in every call and came back whole: on a board of 134
stories, use cases and criteria that is ~105 KB each way, and the model had to write it.

Now the `freeform-fragment` hook (in `.claude/hooks/`, registered by the project template) does
it for you:

- **Before the call** it reads `items.json` locally and puts in `items_content` only what the tool
  needs, plus the highest US, UC and EP number of the whole board:

  ```json
  {"format": "specbox-freeform-fragment/1",
   "max_ids": {"US": 12, "UC": 131, "EP": 3},
   "items": [ ...the UC, its criteria and its story... ]}
  ```

  The numbers keep new ids unique: `add_uc` answers `UC-132` even if UC-131 did not travel.
- **After the call** it writes into `items.json` what the tool changed (field by field, under a
  lock) and removes the fragment from the answer the model sees.

| Call (134 items) | Before | With fragments |
|---|---|---|
| `add_uc` | ~113 KB | ~0.6 KB (the same with 10 items) |
| `get_uc`, `start_uc`, `mark_ac`, `complete_uc` | ~105 KB | ~5 KB |

Tools without a fragment (whole-board reports such as `list_us` or `get_board_status`) still get
the whole file, but the hook sends it, not the model.

**How to switch to it.** Nothing to migrate: `items.json` keeps its format, and a 6.28 board works
as is. The project needs:
- the hook: `npx specbox hooks update`, or update the SpecBox extension;
- `"backend_type": "freeform"` under `specbox` in `.claude/settings.local.json` (the extension and
  `/app-init` write it).

Then stop passing `items_content` yourself. Three things to know:
- If a tool answers `FREEFORM_CONTENT_REQUIRED`, the hook is missing.
- Never write a `{"format": "specbox-freeform-fragment/1", …}` answer as `items.json`: it is a part
  of the board.
- If the hook cannot save a change, the call shows it (exit 2) and what was sent stays in
  `.quality/freeform-fragments/`: read the board again and repeat the call if the change is not
  there.

Clients without hooks (the claude.ai connector, Cursor) keep sending the whole array, as before. Do
not send them a partial array: without `max_ids`, a new UC can repeat an id that did not travel.

## What SpecBox Cloud adds

The Native backend exists for **multi-developer scenarios** where two or more
people share a single board source-of-truth and need optimistic locking to
avoid double-claiming the same UC. If you are solo or you already have Trello
/ Plane wired up, you do not need it.

## How to switch from FreeForm to Native later

Run from the Command Palette:

```
SpecBox: Sign in with GitHub
```

This opens the OAuth flow, persists the token to SecretStorage, and
restarts the MCP server. Your existing FreeForm tracking is **not** touched
— you continue to read and write `doc/tracking/items.json` until you
explicitly migrate (see `/switch-backend`).

## How to switch from Native back to FreeForm

```
SpecBox: Sign out
```

Wipes the token from SecretStorage and restores the MCP config to its
pre-sign-in state. The FreeForm config in `.claude/settings.local.json`
must be re-added by hand if you removed it (or just run the onboarding
notification by deleting the `specbox.onboardingDecision` key from your
workspaceState — `Developer: Reload Window` re-triggers the prompt).

## Troubleshooting

- The onboarding notification did not appear on first activate.
  - Likely your workspace already has `specbox.onboardingDecision` set in
    `workspaceState`. Reset with the VS Code command palette:
    `Developer: Reset Workspace Storage` for the SpecBox extension only.
- `doc/tracking/items.json` is created in the wrong location.
  - The extension always uses `<workspace>/doc/tracking`. If you want a
    different path, edit `freeform_root_absolute` in
    `.claude/settings.local.json` to an absolute path of your choice. The
    v5.29 hook `freeform-path-guard.mjs` will rewrite any remaining
    relative paths at MCP-call time.
