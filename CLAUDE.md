# JPS Dev Engine v3.5.0

> Sistema de programacion agentica para Claude Code.
> Repositorio canonico con commands, patrones, templates y configuracion de Agent Teams.

## Que es este repositorio

Este repositorio contiene el **sistema completo de programacion agentica** para trabajar con Claude Code. Incluye:

- **Commands** (`/prd`, `/plan`, `/implement`, `/adapt-ui`, `/optimize-agents`, `/feedback`) — flujo completo de desarrollo
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
/prd → PRD + Trello/Plane (con Definition Quality Gate)
  ↓
/plan → Plan tecnico + Diseños Stitch (MCP) + HTML
  ↓
/implement → Autopilot: rama + fases + design-to-code + QA + Acceptance Gate + PR
  ↓                                                         ↑
  ├── AG-08 Quality Audit → GO/NO-GO ──────────────────────┤
  ├── AG-09a Acceptance Tests → evidencia visual ──────────┤
  └── AG-09b Acceptance Validator → ACCEPTED/REJECTED ─────┘
  ↓
/feedback → Developer testing → FB-NNN + GitHub issue → puede INVALIDAR verdict
  ↓
Merge secuencial → pull main → siguiente card
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
│   ├── skills/            ← Agent Skills (v3.5)
│   │   ├── prd/SKILL.md
│   │   ├── plan/SKILL.md
│   │   ├── implement/SKILL.md
│   │   ├── adapt-ui/SKILL.md
│   │   ├── optimize-agents/SKILL.md
│   │   ├── quality-gate/SKILL.md
│   │   ├── explore/SKILL.md
│   │   └── feedback/SKILL.md
│   ├── hooks/             ← Hooks (v3.3)
│   │   ├── mcp-report.sh
│   │   ├── pre-commit-lint.sh
│   │   ├── on-session-end.sh
│   │   ├── implement-checkpoint.sh
│   │   ├── implement-healing.sh
│   │   └── post-implement-validate.sh
│   └── settings.json      ← Hooks config
├── commands/              ← Commands (referencia legacy)
│   ├── prd.md
│   ├── plan.md
│   ├── implement.md
│   ├── adapt-ui.md
│   ├── optimize-agents.md
│   ├── quality-gate.md
│   └── feedback.md
├── agents/                ← Templates de agentes por rol
│   ├── orchestrator.md
│   ├── feature-generator.md
│   ├── uiux-designer.md
│   ├── db-specialist.md
│   ├── qa-validation.md
│   ├── design-specialist.md
│   ├── n8n-specialist.md
│   ├── appscript-specialist.md
│   ├── quality-auditor.md
│   ├── acceptance-tester.md
│   ├── acceptance-validator.md
│   └── developer-tester.md
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
├── .quality/              ← Telemetria y evidencia (v3.1)
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

## Available Skills (v3.5)

Skills are auto-discoverable. Claude will use them when relevant. You can also invoke them explicitly.

| Skill | Trigger phrases | Mode | Tools | Notes |
|-------|----------------|------|-------|-------|
| /prd | "create PRD", "new feature", "write requirements" | fork:Plan | Full | Definition Quality Gate (Paso 2.5) valida AC-XX |
| /plan | "plan feature", "technical plan", "analyze for implementation" | fork:Plan | Full | |
| /implement | "implement plan", "execute plan", "autopilot" | direct | Full | Self-healing + AG-09 acceptance gate + merge secuencial |
| /adapt-ui | "scan UI", "map components", "detect widgets" | fork:Explore | Read-only | |
| /optimize-agents | "audit agents", "optimize system", "agent score" | fork:Explore | Read-only | |
| /quality-gate | "check quality", "run gates", "coverage check" | direct | Lint+Read | |
| /explore | "analyze codebase", "explore code", "understand architecture" | fork:Explore | Read-only | |
| /feedback | "report feedback", "found a bug", "this doesn't work" | direct | Full | AG-10 + GitHub issue + invalida acceptance |

## Hooks (v3.5)

Automatic enforcement — no need to remember running these manually:

| Hook | Event | Behavior |
|------|-------|----------|
| pre-commit-lint | PostToolUse (git commit) | BLOCKING: fails commit if lint has errors |
| on-session-end | Stop | Logs session telemetry to .quality/logs/ |
| implement-checkpoint | Manual (called by /implement) | Saves phase progress for resume |
| implement-healing | Manual (called by /implement) | Logs self-healing events to evidence |
| post-implement-validate | Manual (called by /implement) | Checks baseline regression after implementation |

## Remote Telemetry (v3.3)

Hooks can report to a remote MCP server for centralized state tracking.
Set `DEV_ENGINE_MCP_URL=https://mcp-dev-engine.jpsdeveloper.com/mcp` in your shell profile.
Reporting is fire-and-forget — if the MCP is unreachable, hooks work normally.

## Context Engineering (v3.5)

- Skills with `context: fork` run in isolated subagents — they don't pollute your main session
- /implement delegates phases to isolated Tasks with a **context budget of ~8,700 tokens per phase**
- Read-only Skills (explore, optimize-agents, adapt-ui) cannot modify files
- File ownership per agent is documented in .claude/skills/implement/file-ownership.md
- Context budget estimator: `.quality/scripts/context-budget.sh <path> [--detail]`
- Session context metrics logged automatically via on-session-end hook
- Full context engineering rules in `rules/GLOBAL_RULES.md` section "Context Engineering"

## Quality Scripts

| Script | Usage | Purpose |
|--------|-------|---------|
| `create-baseline.sh` | `.quality/scripts/create-baseline.sh [path]` | Generate initial quality baseline |
| `update-baseline.sh` | `.quality/scripts/update-baseline.sh [path]` | Ratchet-safe baseline update (only improves) |
| `analyze-sessions.sh` | `.quality/scripts/analyze-sessions.sh [--last N]` | Telemetry: sessions, context tokens, healing, checkpoints |
| `context-budget.sh` | `.quality/scripts/context-budget.sh <path> [--detail]` | Estimate token cost of files/directories |

## Agents (v3.5)

| ID | Rol | Archivo | Modelo |
|----|-----|---------|--------|
| AG-01 | Feature Generator | `agents/feature-generator.md` | opus |
| AG-02 | UI/UX Designer | `agents/uiux-designer.md` | opus |
| AG-03 | DB Specialist | `agents/db-specialist.md` | sonnet |
| AG-04 | QA Validation | `agents/qa-validation.md` | sonnet |
| AG-05 | n8n Specialist | `agents/n8n-specialist.md` | sonnet |
| AG-06 | Design Specialist | `agents/design-specialist.md` | sonnet |
| AG-07 | Apps Script Specialist | `agents/appscript-specialist.md` | sonnet |
| AG-08 | Quality Auditor | `agents/quality-auditor.md` | sonnet |
| AG-09a | Acceptance Tester | `agents/acceptance-tester.md` | sonnet |
| AG-09b | Acceptance Validator | `agents/acceptance-validator.md` | sonnet |
| AG-10 | Developer Tester | `agents/developer-tester.md` | sonnet |

## Acceptance Engine (v3.5)

Pipeline completo de validacion funcional:

1. **Definition Quality Gate** (`/prd` Paso 2.5) — Rechaza acceptance criteria vagos/no-testables antes de crear work items. Evalua especificidad, medibilidad y testabilidad (0-2 cada una).
2. **AG-09a Acceptance Tester** (`/implement` Paso 7.5) — Genera E2E/integration tests desde AC-XX del PRD con evidencia visual (screenshots, traces, response logs).
3. **AG-09b Acceptance Validator** (`/implement` Paso 7.7) — Validacion independiente: verifica que cada AC-XX esta implementado, testeado y evidenciado. Emite ACCEPTED/CONDITIONAL/REJECTED.
4. **AG-10 Developer Feedback** (`/feedback`) — Captura feedback de testing manual. Crea evidencia local (FB-NNN.json) + GitHub issue. Puede INVALIDAR verdict de AG-09b. Severity critical/major bloquea merge.
5. **Merge Secuencial** (`/implement` Paso 8.5) — Auto-merge solo si AG-08=GO, AG-09=ACCEPTED y no hay feedback bloqueante. Pull main antes de siguiente card.

Frameworks de acceptance testing por stack:

| Stack | Framework | Evidencia | Tests en |
|-------|-----------|-----------|----------|
| Flutter | Patrol + Alchemist | Screenshots + goldens | `test/acceptance/` |
| React | Playwright | Screenshots + traces | `tests/acceptance/` |
| Python | pytest + httpx | Response JSON logs | `tests/acceptance/` |

## Engine Version

Current: v3.5.0 "Feedback Loop"
Config: ENGINE_VERSION.yaml
