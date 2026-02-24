# JPS Dev Engine v2.3.0

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

Esto instala los commands globales en `~/.claude/commands/` como symlinks.

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
├── install.sh             ← Instala commands en ~/.claude/commands/
├── commands/              ← Commands globales (se instalan via install.sh)
│   ├── prd.md
│   ├── plan.md
│   ├── implement.md
│   ├── adapt-ui.md
│   └── optimize-agents.md
├── agents/                ← Templates de agentes por rol
│   ├── orchestrator.md
│   ├── feature-generator.md
│   ├── uiux-designer.md
│   ├── qa-validation.md
│   ├── supabase-specialist.md
│   ├── n8n-specialist.md
│   ├── appscript-specialist.md
│   └── templates/
├── agent-teams/           ← Agent Teams nativo (Claude Code)
│   ├── README.md
│   ├── templates/
│   │   └── team-config.template.json
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
│   └── team-config.json.template
├── rules/                 ← Reglas globales
│   └── GLOBAL_RULES.md
└── docs/                  ← Documentacion del sistema
    ├── getting-started.md
    ├── commands.md
    ├── agent-teams.md
    └── architecture.md
```

## Para contribuir

1. Los commands en `commands/` son los archivos reales que se instalan
2. Tras modificar un command, ejecutar `./install.sh` para actualizar symlinks
3. Versionar cambios en ENGINE_VERSION.yaml
