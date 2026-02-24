# JPS Dev Engine v3.1.0

> Sistema de programacion agentica para Claude Code.
> Repositorio canonico con commands, patrones, templates y configuracion de Agent Teams.

## Que es este repositorio

Este repositorio contiene el **sistema completo de programacion agentica** para trabajar con Claude Code. Incluye:

- **Commands** (`/prd`, `/plan`, `/implement`, `/adapt-ui`, `/optimize-agents`) — flujo completo de desarrollo
- **Agent Teams** — configuracion para orquestacion multi-agente nativa de Claude Code
- **Architecture** — patrones por stack (Flutter, React, Python, Google Apps Script)
- **Infrastructure** — patrones por servicio (Supabase, Neon, Stripe, Firebase, n8n)
- **Design** — integracion con Google Stitch MCP para diseño UI
- **Templates** — CLAUDE.md, settings.json, team-config para nuevos proyectos
- **Agents** — templates genericos de roles especializados

## Stack soportado

| Stack | Version | Estado |
|-------|---------|--------|
| Flutter | 3.38+ | Completo |
| React | 19.x | Completo |
| Python (FastAPI) | 3.12+ | Completo |
| Google Apps Script | V8 | Completo |
| Supabase | 2.x | Completo |
| Neon (Postgres serverless) | - | Completo |
| Stripe | latest | Completo |
| Firebase | latest | Completo |
| n8n | latest | Completo |
| Google Stitch MCP | - | Completo |

## Instalacion

```bash
git clone <repo-url> jps_dev_engine
cd jps_dev_engine
./install.sh
```

Esto instala Skills en `~/.claude/skills/`, hooks en `~/.claude/hooks/` y commands en `~/.claude/commands/`.

## Flujo de desarrollo

```
/prd → PRD + Trello/Plane
  ↓
/plan → Plan tecnico + Diseños Stitch (MCP) + HTML
  ↓
/implement → Autopilot: rama + fases + design-to-code + QA + PR
  ↓
/optimize-agents → Audita y optimiza sistema agentico del proyecto
```

## Estructura del repositorio

```
jps_dev_engine/
├── CLAUDE.md              ← Este archivo
├── ENGINE_VERSION.yaml    ← Version del engine
├── install.sh             ← Instala skills, hooks, commands
├── .claude/
│   ├── skills/            ← Agent Skills (v3.0)
│   │   ├── prd/SKILL.md
│   │   ├── plan/SKILL.md
│   │   ├── implement/SKILL.md
│   │   ├── adapt-ui/SKILL.md
│   │   ├── optimize-agents/SKILL.md
│   │   ├── quality-gate/SKILL.md
│   │   └── explore/SKILL.md
│   ├── hooks/             ← Hooks (v3.0)
│   │   ├── pre-commit-lint.sh
│   │   ├── on-session-end.sh
│   │   └── implement-checkpoint.sh
│   └── settings.json      ← Hooks config
├── commands/              ← Commands (referencia legacy)
│   ├── prd.md
│   ├── plan.md
│   ├── implement.md
│   ├── adapt-ui.md
│   ├── optimize-agents.md
│   └── quality-gate.md
├── agents/                ← Templates de agentes por rol
│   ├── orchestrator.md
│   ├── feature-generator.md
│   ├── uiux-designer.md
│   ├── db-specialist.md
│   ├── qa-validation.md
│   ├── design-specialist.md
│   ├── n8n-specialist.md
│   ├── appscript-specialist.md
│   └── quality-auditor.md
├── agent-teams/           ← Agent Teams nativo (Claude Code)
│   ├── README.md
│   ├── templates/
│   ├── prompts/
│   └── hooks/
├── architecture/          ← Patrones por stack
│   ├── flutter/
│   ├── react/
│   ├── python/
│   └── google-apps-script/
├── design/                ← Integracion Stitch MCP
│   └── stitch/
├── infra/                 ← Patrones por servicio
│   ├── supabase/
│   ├── neon/
│   ├── stripe/
│   ├── firebase/
│   └── n8n/
├── templates/             ← Templates para nuevos proyectos
│   ├── CLAUDE.md.template
│   ├── settings.json.template
│   ├── team-config.json.template
│   └── quality-baseline.json.template
├── .quality/              ← Telemetria y evidencia (v3.0)
├── rules/                 ← Reglas globales
│   └── GLOBAL_RULES.md
└── docs/                  ← Documentacion del sistema
    ├── getting-started.md
    ├── commands.md
    ├── agent-teams.md
    └── architecture.md
```

## Para contribuir

1. Las Skills en `.claude/skills/` son los archivos activos del sistema
2. Los commands en `commands/` se mantienen como referencia legacy
3. Tras modificar una Skill, ejecutar `./install.sh` para actualizar en global
4. Versionar cambios en ENGINE_VERSION.yaml

## Available Skills (v3.0)

Skills are auto-discoverable. Claude will use them when relevant. You can also invoke them explicitly.

| Skill | Trigger phrases | Mode | Tools | Notes |
|-------|----------------|------|-------|-------|
| /prd | "create PRD", "new feature", "write requirements" | fork:Plan | Full | |
| /plan | "plan feature", "technical plan", "analyze for implementation" | fork:Plan | Full | |
| /implement | "implement plan", "execute plan", "autopilot" | direct | Full | Self-healing with 4-level auto-recovery |
| /adapt-ui | "scan UI", "map components", "detect widgets" | fork:Explore | Read-only | |
| /optimize-agents | "audit agents", "optimize system", "agent score" | fork:Explore | Read-only | |
| /quality-gate | "check quality", "run gates", "coverage check" | direct | Lint+Read | |
| /explore | "analyze codebase", "explore code", "understand architecture" | fork:Explore | Read-only | |

## Hooks (v3.0)

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| pre-commit-lint | PostToolUse (git commit) | BLOCKING: fails commit if lint has errors |
| on-session-end | Stop | Logs session telemetry to .quality/logs/ |
| implement-checkpoint | Manual (called by /implement) | Saves phase progress for resume |
| implement-healing | Manual (called by /implement) | Logs self-healing events to evidence |
| post-implement-validate | Manual (called by /implement) | Checks baseline regression after implementation |

## Context Rules (v3.0)

- Skills with `context: fork` run in isolated subagents — they don't pollute your main session
- /implement delegates phases to isolated Tasks to prevent context saturation
- Read-only Skills (explore, optimize-agents, adapt-ui) cannot modify files
- File ownership per agent is documented in .claude/skills/implement/file-ownership.md

## Quality Scripts

| Script | Usage | Purpose |
|--------|-------|---------|
| `create-baseline.sh` | `.quality/scripts/create-baseline.sh [path]` | Generate initial quality baseline |
| `update-baseline.sh` | `.quality/scripts/update-baseline.sh [path]` | Ratchet-safe baseline update (only improves) |
| `analyze-sessions.sh` | `.quality/scripts/analyze-sessions.sh [--last N]` | Telemetry report: sessions, healing, checkpoints |

## Engine Version

Current: v3.1.0 "Skills Engine"
Config: ENGINE_VERSION.yaml
