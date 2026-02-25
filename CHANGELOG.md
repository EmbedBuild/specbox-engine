# Changelog

All notable changes to JPS Dev Engine are documented here.

## [3.2.0] - 2026-02-25

### Added
- **Context Engineering System**: Token budget per phase (~8,700 tokens max), context pruning rules, and context saturation prevention in `/implement` Task Isolation
- `context-budget.sh` — estimates token cost of files and directories with breakdown and threshold indicators
- `on-session-end.sh` now tracks context metrics: estimated tokens consumed, files modified, healing events, active feature
- `analyze-sessions.sh` rewritten with context metrics, per-session averages, and budget health indicator (green/yellow/red)
- `GLOBAL_RULES.md` new section "Context Engineering" with budgets per operation type, pruning rules, and telemetry thresholds

### Changed
- `/implement` Task Isolation section rewritten with explicit context budget table, loading rules (include/exclude), phase task template, and saturation prevention protocol
- `CLAUDE.md` section "Context Rules" renamed to "Context Engineering (v3.2)" with budget references

### Fixed
- CLAUDE.md tree: remaining `(v3.0)` annotations changed to `(v3.1)` on skills/ and .quality/ lines

## [3.1.2] - 2026-02-25

### Fixed
- `install.sh --uninstall` now removes skills (symlinks) and hooks in addition to commands
- `install.sh` summary now generates dynamic hook list instead of hardcoding 3 of 5
- `install.sh` header comment no longer hardcodes version number

### Changed
- CLAUDE.md section headers updated from `(v3.0)` to `(v3.1)` for Available Skills, Hooks, and Context Rules
- CLAUDE.md tree structure now lists all 5 hooks (added `implement-healing.sh` and `post-implement-validate.sh`)

## [3.1.1] - 2026-02-25

### Added
- `docs/agent-teams.md` — executive summary of Agent Teams for developers (8 roles, engine awareness, File Ownership, hooks, setup, migration)
- `docs/architecture.md` — multi-stack architecture guide with per-stack document inventory (Flutter 5 docs, React 1, Python 1, GAS 4) and infra/design references
- Complete `docs/` directory now matches CLAUDE.md structure: getting-started, commands, agent-teams, architecture

## [3.1.0] - 2026-02-24

### Added
- Self-healing protocol: 4-level auto-recovery in `/implement` with healing log
- Telemetry analysis script: `analyze-sessions.sh` with healing and checkpoint reports
- Ratchet-safe baseline updater: `update-baseline.sh` (only improves, never regresses)
- Post-implement validation hook for baseline regression detection
- `implement-healing.sh` hook for structured healing event logging

### Changed
- Agent Teams prompts updated for v3 engine integration (Skills, hooks, quality)
- `install.sh` migrated from cp to symlinks for Skills (instant updates with git pull)

## [3.0.0] - 2026-02-24

### Added
- Agent Skills system with YAML frontmatter and auto-discovery
- Hooks system: pre-commit lint, session telemetry, checkpointing
- Context isolation with fork and Task patterns
- File ownership enforcement per agent
- `/explore` Skill for read-only codebase analysis
- `/quality-gate` Skill for adaptive quality gates
- Checkpoint/resume system for `/implement`

### Changed
- All commands migrated to Agent Skills
- `install.sh` updated to copy skills + hooks

## [2.4.0] - 2026-02-24

### Added
- `/quality-gate` command — auto-discovered baseline, progressive ratchet, auditable evidence
- AG-08 Quality Auditor — independent quality verification agent
- Quality gates between `/implement` phases — lint 0/0/0 blocking, coverage ratchet
- `.quality/` directory with baseline.json, plan.md, evidence/ and reports/
- Policies: zero-tolerance (lint), ratchet (coverage/arch/deadcode), no-regression (tests)
- Evidence auditable per feature: pre-gate, phase-N-gate, final-gate, report
- Agent Teams prompt for quality-auditor
- Template `quality-baseline.json.template`

### Changed
- Orchestrator updated with AG-08 and mandatory gates between phases
- GLOBAL_RULES updated with Quality Gates section

## [2.3.0] - 2026-02-24

### Added
- `/implement` command — end-to-end autopilot implementation
- Multi-stack support: Flutter, React, Python, Google Apps Script
- Partial commits per phase, coverage check 85%+, automatic PR with gh

### Changed
- Development flow updated: /prd → /plan → /implement → done

## [2.2.0] - 2026-02-24

### Added
- Google Apps Script stack (V8 + clasp + TypeScript)
- `architecture/google-apps-script/` — overview, folder-structure, patterns, testing-strategy
- AG-07 Apps Script Specialist
- Agent Teams: AppScriptSpecialist role with prompt and file ownership
- Detection of `.clasp.json` / `appsscript.json` in optimize-agents, plan and adapt-ui

### Changed
- GLOBAL_RULES.md updated with Apps Script rules
- Templates updated (CLAUDE.md, team-config, feature-generator)

## [2.1.0] - 2026-02-24

### Added
- `/optimize-agents` Engine Sync section — detects engine version and compares project files
- Step 0.6: locates jps_dev_engine, compares copied agents/prompts/config vs engine
- Audit output section 7: Engine Sync with symlink status and outdated files

## [2.0.1] - 2026-02-24

### Removed
- `uiux/` library — Stitch MCP defines visual style freely

### Changed
- AG-02 (uiux-designer) rewritten: works from Stitch designs, no predefined styles
- Cleaned references to uiux/ in CLAUDE.md, README.md, docs

## [2.0.0] - 2026-02-24

### Added
- Complete restructuring: canonical repository for the agentic system
- Multi-stack: Flutter 3.38+, React 19.x, Python 3.12+
- Agent Teams native (Claude Code experimental)
- Google Stitch MCP integration for UI design
- Infrastructure patterns: Supabase, Neon, Stripe, Firebase, n8n
- `/optimize-agents` command with Agent Teams support
- Generic agent templates per role

### Changed
- `install.sh`: command installation via symlinks

### Removed
- Sync/upgrade scripts (engine is reference, not tool)

## [1.0.0] - 2025-01-15

### Added
- Initial engine setup
- Global commands (prd, plan, adapt-ui)
- GLOBAL_RULES.md for Claude Code
- Setup and sync scripts (removed in v2)
