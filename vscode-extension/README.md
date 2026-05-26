<p align="center">
  <img src="media/banner.png" alt="SpecBox Engine — Agentic Development for Claude Code" width="100%" />
</p>

<p align="center">
  <img src="media/icon.png" alt="SpecBox Engine" width="96" />
</p>

<h1 align="center">SpecBox Engine</h1>
<p align="center"><strong>Agentic Dev for Claude Code</strong></p>

<p align="center">
  <a href="https://marketplace.visualstudio.com/items?itemName=jpsdeveloper.specbox-engine"><img src="https://img.shields.io/visual-studio-marketplace/v/jpsdeveloper.specbox-engine?label=marketplace&color=00B4D8&style=flat-square" alt="Version" /></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=jpsdeveloper.specbox-engine"><img src="https://img.shields.io/visual-studio-marketplace/i/jpsdeveloper.specbox-engine?color=0077B6&style=flat-square" alt="Installs" /></a>
  <a href="https://marketplace.visualstudio.com/items?itemName=jpsdeveloper.specbox-engine"><img src="https://img.shields.io/visual-studio-marketplace/r/jpsdeveloper.specbox-engine?style=flat-square" alt="Rating" /></a>
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
| **SpecBox: Health Check** | Diagnostic report (Node, Python, Claude Code, Engram, skills, hooks, MCP) |
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
code --install-extension jpsdeveloper.specbox-engine
```

### 2. Run the onboarding wizard

`Ctrl+Shift+P` → **SpecBox: Onboard Project**

The wizard handles everything:

```
Step 1  →  Check prerequisites (Node, Python, Claude Code, Engram)
Step 2  →  Locate engine repo (auto-detect or clone)
Step 3  →  Install 15 skills + 20+ hooks + settings
Step 4  →  Configure MCP servers (SpecBox + Engram)
```

### 3. Start building

```
/prd "User authentication with OAuth2"     → Requirements
/plan PROJECT-42                            → Technical plan + UI designs
/implement auth_plan                        → Autopilot implementation
```

---

## Requirements

- **Claude Code** — [install](https://claude.ai/code) or the official Claude VSCode extension.
- **Node.js 18+** — [download](https://nodejs.org)
- **Python 3.12+** — [download](https://python.org)
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
| Engram install | pip/pipx | pip/pipx | pip/pipx |

The extension uses symlinks where possible, with automatic fallback to file copy on Windows.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Claude Code not detected" | Install [Claude Code](https://claude.ai/code) or the VSCode Claude extension first. |
| MCP servers unreachable | Run **SpecBox: Configure MCP Servers** to (re)write the MCP config. Verify Python ≥ 3.12 is on `PATH`. |
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
