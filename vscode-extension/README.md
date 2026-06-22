<p align="center">
  <img src="media/banner.png" alt="SpecBox Engine — Agentic Development for Claude Code" width="100%" />
</p>

<p align="center">
  <img src="media/icon.png" alt="SpecBox Engine" width="96" />
</p>

<h1 align="center">SpecBox Engine</h1>
<p align="center"><strong>Agentic Dev for Claude Code</strong></p>

<p align="center">
  <a href="https://marketplace.visualstudio.com/items?itemName=EmbedBuild.specbox-engine"><img src="https://img.shields.io/visual-studio-marketplace/v/EmbedBuild.specbox-engine?label=marketplace&color=00B4D8&style=flat-square" alt="Version" /></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=EmbedBuild.specbox-engine"><img src="https://img.shields.io/visual-studio-marketplace/i/EmbedBuild.specbox-engine?color=0077B6&style=flat-square" alt="Installs" /></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=EmbedBuild.specbox-engine"><img src="https://img.shields.io/visual-studio-marketplace/r/EmbedBuild.specbox-engine?style=flat-square" alt="Rating" /></a>
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License" />
  <img src="https://img.shields.io/badge/platform-win%20%7C%20mac%20%7C%20linux-0B1120?style=flat-square" alt="Platform" />
  <img src="https://img.shields.io/badge/claude--code-ready-00B4D8?style=flat-square" alt="Claude Code" />
  <img src="https://img.shields.io/badge/i18n-EN%20%7C%20ES-1a1a2e?style=flat-square" alt="Languages" />
</p>

<p align="center">
  <strong>English</strong> · <a href="README.es.md">Español</a>
</p>

<p align="center">
  One-click setup for the SpecBox Engine agentic programming system.<br/>
  Skills, hooks, MCP servers, and Engram memory — cross-platform, zero config.
</p>

---

## Why SpecBox Engine?

Claude Code is powerful out of the box. SpecBox Engine makes it **systematic**:

| Without SpecBox | With SpecBox |
|----------------|-------------|
| Ad-hoc coding, no structure | Spec-driven: US → UC → AC pipeline |
| No quality enforcement | 20+ hooks: read-before-write, branch guards, lint gates |
| Context lost between sessions | Engram persistent memory saves decisions & discoveries |
| Manual project management | Trello/Plane/FreeForm integration with 110+ MCP tools |
| No acceptance testing | BDD acceptance engine with HTML evidence reports |

---

## Features

The extension provides 5 commands available from the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`):

| Command | What it does |
|---------|--------------|
| **SpecBox: Install Engine** | One-click install of 15 skills, 20+ hooks, settings, and MCP servers |
| **SpecBox: Health Check** | Diagnostic report (Node, Claude Code, Engram, skills, hooks, MCP) |
| **SpecBox: Check Prerequisites** | Verify critical prerequisites are installed; warns if SpecBox may not work correctly |
| **SpecBox: Onboard Project** | Interactive wizard that walks you through full setup |
| **SpecBox: Show Status** | Quick status view of the engine in the current workspace |
| **SpecBox: Configure MCP Servers** | Set up or repair SpecBox MCP + Engram memory MCP servers |

Plus a **sidebar panel** with `Status` and `Skills` tree views, and a **status bar** indicator that shows engine health at a glance.

![Command Palette filtered by SpecBox](media/screenshots/command-palette.png)

---

## Quick Start

### 1. Install the extension

Search **"SpecBox Engine"** in the VSCode Marketplace, or run:

```bash
code --install-extension EmbedBuild.specbox-engine
```

### 2. Choose your mode on first activate

On the first activation in a workspace, the extension shows a one-time
notification with two choices:

- **Sign in with GitHub** — opens your browser, completes a GitHub OAuth
  flow via [cloud.specbox.build](https://cloud.specbox.build), and stores
  the resulting MCP token in your OS keychain via VSCode SecretStorage.
  Enables Native backend (shared tracking, multi-developer reservations).
- **Continue in local mode (FreeForm)** — no auth, no cloud. All tracking
  lives on disk under `doc/tracking/`. See
  [Local mode (no auth)](#local-mode-no-auth) below.

You can switch modes at any time later: `Ctrl+Shift+P` → **SpecBox: Sign
in with GitHub** or **SpecBox: Sign out**.

### 3. Run the onboarding wizard

`Ctrl+Shift+P` → **SpecBox: Onboard Project**

The wizard handles everything:

```
Step 1  →  Check prerequisites (Node, Claude Code, Engram)
Step 2  →  Locate engine repo (auto-detect or clone)
Step 3  →  Install all skills + 20+ hooks + settings
Step 4  →  Configure MCP servers (SpecBox + Engram)
```

### 4. Start building

```
/prd "User authentication with OAuth2"     → Requirements
/plan PROJECT-42                            → Technical plan + UI designs
/implement auth_plan                        → Autopilot implementation
```

---

## Local mode (no auth)

FreeForm remains **first-class**. If you pick "Continue in local mode" you
get the full engine — skills, hooks, BDD acceptance, MCP tools that do not
require shared state — without ever opening a browser or storing a token.

What works without signing in:
- The full pipeline: `/prd`, `/plan`, `/implement`, `/audit`, etc.
- Trello and Plane backends (you provide their own API keys).
- All non-Native tools (110+ tools).

What requires signing in:
- The Native backend's UC reservation system (multi-developer locking).
- The four native tools: `whoami`, `reserve_uc`, `release_uc`,
  `register_native_branch`.

See [doc/runbooks/freeform-only-mode.md](https://github.com/EmbedBuild/specbox-engine/blob/main/doc/runbooks/freeform-only-mode.md)
for a detailed walkthrough.

---

## How sign-in works under the hood

1. You click **Sign in with GitHub**. The extension starts a one-shot HTTP
   server on `127.0.0.1` (random port assigned by the OS), generates a
   64-hex CSRF state, and opens `https://cloud.specbox.build/vscode/issue-token`
   in your default browser, passing the loopback URL and state as query params.
2. The cloud handles the GitHub OAuth dance (no plaintext credentials ever
   touch the extension or the engine — only the cloud).
3. The cloud redirects back to the loopback with `?mcp_token=spbx_<base64url>&state=<csrf>`. The token shape is the cloud's `issueMcpToken()` output — `spbx_` prefix + base64url body, mirroring the engine's `register_mcp_token` algorithm.
4. The extension validates the state, regex-checks the token, persists it
   to **VSCode SecretStorage** (Keychain on macOS, Credential Manager on
   Windows, libsecret on Linux), and tells Claude Code to respawn the MCP
   server so the token is in scope.
5. If the token is **revoked** on the cloud, the engine reports
   `UNAUTHENTICATED` on the next native tool call (≤30s thanks to the
   server-side auth cache TTL). The sidebar polls every 60s and updates
   on its own — total revoke-visibility ≤ 90s.

The cloud side is implemented in [`EmbedBuild/specbox_cloud`](https://github.com/EmbedBuild/specbox_cloud)
(US-09). See [doc/decisions/native_default_oauth.md](https://github.com/EmbedBuild/specbox-engine/blob/main/doc/decisions/native_default_oauth.md)
for the architectural rationale and the residual security trade-offs.

---

## Activation telemetry (funnel)

To measure how many people who discover SpecBox on the website actually install
the extension, the extension emits a single, anonymous **`activation`** event the
first time it runs after installation. This closes the loop with the website's
anonymous funnel (page view → install intent → activation).

How it works:

1. When you click **Get the extension** on the SpecBox site, the site opens a
   deep-link `vscode://EmbedBuild.specbox-engine/activate?anon_id=<uuid>`. The
   `anon_id` is the website's opaque, randomly-generated anonymous session id —
   it is **not** tied to your identity, GitHub account, email, or repository.
2. The extension validates the `anon_id` (must be a UUID v4) and stores it in VS
   Code global state.
3. On the next activation, the extension posts **one** `activation` event to the
   public funnel endpoint (the same Supabase project the website uses). The event
   carries the `anon_id` (so the install can be correlated with the anonymous web
   session) plus a small technical `meta` block: **extension version**,
   **OS platform**, and **VS Code version**. Nothing else.
4. The event is emitted **at most once per install** (an idempotency flag in
   global state). If the deep-link `anon_id` never arrived (e.g. you installed
   from the Marketplace directly), the activation is still emitted, just without a
   web-session origin.

What is **never** sent: local file paths, your git email or name, workspace or
repo contents, MCP/auth tokens, or any other personally identifiable data. The
`anon_id` is opaque and is never enriched.

Respecting your preferences: if you have **disabled VS Code telemetry**
(`telemetry.telemetryLevel: "off"`, surfaced as `vscode.env.isTelemetryEnabled`),
the extension emits **nothing**. The emitter is fully best-effort and
fire-and-forget — it never blocks activation and never surfaces errors to you.

Implementation: [`src/activation.ts`](src/activation.ts) (US-26, UC-2601/UC-2602).

---

## Requirements

- **Claude Code** — [install](https://claude.ai/code) or the official Claude VSCode extension.
- **Node.js 18+** — [download](https://nodejs.org)
- **Git** — [download](https://git-scm.com)
- **VSCode 1.86+** — required for runtime localization (`vscode.l10n`).

---

## What Gets Installed

### 15 Agent Skills

| Skill | What it does |
|-------|--------------|
| `/prd` | Generate Product Requirements Documents |
| `/plan` | Technical plans + Stitch UI designs |
| `/implement` | End-to-end autopilot with quality gates |
| `/feedback` | Capture testing feedback as evidence |
| `/quality-gate` | Adaptive quality checks before PR |
| `/explore` | Read-only codebase analysis |
| `/visual-setup` | Brand kit + design system configuration |
| `/adapt-ui` | Scan and map project UI components |
| `/optimize-agents` | Audit and optimize agent configuration |
| `/acceptance-check` | Standalone BDD acceptance validation |
| `/check-designs` | Retroactive Stitch design compliance |
| `/quickstart` | Interactive tutorial for new users |
| `/audit` | ISO/IEC 25010 quality audit on-demand |
| `/release` | Version audit, changelog, and publish |
| `/compliance` | Full SpecBox compliance audit |

### 20+ Quality Hooks

Automatic enforcement — Claude Code follows the rules without being told:

| Hook | What it prevents |
|------|------------------|
| **quality-first-guard** | Modifying a file without reading it first |
| **spec-guard** | Writing code without an active Use Case |
| **branch-guard** | Writing code directly on main/master |
| **no-bypass-guard** | Using `--no-verify`, `push --force`, `reset --hard` |
| **healing-budget-guard** | Infinite healing loops (hard limit at 8 attempts) |
| **pipeline-phase-guard** | Out-of-order execution (e.g., feature code before DB) |
| **design-gate** | Creating UI pages without Stitch designs |
| **e2e-gate** | Committing acceptance evidence without valid reports |

### 2 MCP Servers

| Server | Tools | Purpose |
|--------|-------|---------|
| **SpecBox Engine** | 110+ | Plans, quality, features, telemetry, spec-driven, Stitch proxy |
| **Engram** | 6 | Persistent memory across sessions and context compactions |

---

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `specbox.enginePath` | _(auto-detect)_ | Path to the SpecBox Engine repo |
| `specbox.autoHealthCheck` | `true` | Check health on startup |
| `specbox.mcpAutoStart` | `true` | Auto-configure MCP on install |

---

## Languages

The extension UI and Marketplace listing are available in:

- 🇺🇸 **English** (default, canonical)
- 🇪🇸 **Spanish** (España, neutral)

VSCode auto-resolves the language based on `vscode.env.language`. To force a locale, launch VSCode with `code --locale=es` or `code --locale=en`.

---

## Cross-Platform

| Feature | macOS | Linux | Windows |
|---------|-------|-------|---------|
| Skills installation | Symlinks | Symlinks | Copy (auto-fallback) |
| Hooks installation | Copy | Copy | Copy |
| MCP configuration | JSON config | JSON config | JSON config |
| Settings merge | Smart merge | Smart merge | Smart merge |
| Engram install | Homebrew | Homebrew | Manual binary |

The extension uses symlinks where possible, with automatic fallback to file copy on Windows.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Claude Code not detected" | Install [Claude Code](https://claude.ai/code) or the VSCode Claude extension first. |
| MCP servers unreachable | Run **SpecBox: Configure MCP Servers** to (re)write the MCP config. The SpecBox MCP server uses a free hosted endpoint — verify network access and that `npx` is on `PATH`. |
| Engine version mismatch warning | The extension and the local engine repo are out of sync. Run **SpecBox: Install Engine** to update local files, or `git pull` in the engine repo. |
| Commands show in English even with `--locale=es` | Reload the window after install (`Ctrl+Shift+P` → "Developer: Reload Window"). VSCode caches NLS bundles between sessions. |
| Walkthrough not appearing | Run **SpecBox: Onboard Project** manually. The walkthrough only auto-launches on first install. |

For other issues, [open an issue on GitHub](https://github.com/EmbedBuild/specbox-engine/issues).

---

## Terminal Alternative

For CI/CD or headless environments (macOS/Linux only):

```bash
git clone https://github.com/EmbedBuild/specbox-engine.git ~/specbox-engine
cd ~/specbox-engine && ./install.sh
```

Note: `install.sh` does not configure MCP servers. See [Getting Started](https://github.com/EmbedBuild/specbox-engine/blob/main/docs/getting-started.md) for manual MCP setup.

---

<p align="center">
  <strong>SpecBox Engine by JPS</strong><br/>
  <sub>Agentic programming system for Claude Code</sub><br/>
  <a href="https://github.com/EmbedBuild/specbox-engine">GitHub</a> · <a href="https://github.com/EmbedBuild/specbox-engine/blob/main/docs/getting-started.md">Docs</a> · <a href="https://github.com/EmbedBuild/specbox-engine/issues">Issues</a> · <a href="CHANGELOG.md">Changelog</a>
</p>
