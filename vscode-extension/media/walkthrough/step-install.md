## Install Engine

One click installs everything Claude Code needs:

### Skills (15)
Slash commands that extend Claude Code with structured workflows:
`/prd` `/plan` `/implement` `/feedback` `/quality-gate` `/explore`
`/visual-setup` `/adapt-ui` `/optimize-agents` `/acceptance-check`
`/check-designs` `/quickstart` `/remote` `/release` `/compliance`

### Hooks (20+)
Automatic enforcement rules that run before/after Claude Code actions:
- **quality-first-guard** — must read a file before modifying it
- **spec-guard** — no code without an active Use Case
- **branch-guard** — no code writes on main
- **no-bypass-guard** — blocks `--no-verify` and `push --force`

### Settings
Hook configurations merged into `~/.claude/settings.json` (preserves your existing settings).

Click **Install SpecBox Engine** to install all components.
