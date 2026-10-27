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
