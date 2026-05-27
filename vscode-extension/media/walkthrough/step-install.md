## Install Engine

One click installs everything Claude Code needs:

### Skills
Slash commands that extend Claude Code with structured workflows — discovery, planning, implementation, quality audits, payments scaffolding, and more. The exact list evolves with each engine release; check the **SpecBox** sidebar after install to browse what's available.

### Hooks (20+)
Automatic enforcement rules that run before/after Claude Code actions:
- **quality-first-guard** — must read a file before modifying it
- **spec-guard** — no code without an active Use Case
- **branch-guard** — no code writes on main
- **no-bypass-guard** — blocks `--no-verify` and `push --force`

### Settings
Hook configurations merged into `~/.claude/settings.json` (preserves your existing settings).

Click **Install SpecBox Engine** to install all components.
