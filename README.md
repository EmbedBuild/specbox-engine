# JPS Dev Engine v2.0.0

Sistema de programacion agentica para Claude Code.

Repositorio canonico que contiene commands, patrones de arquitectura, templates de agentes, configuracion de Agent Teams y patrones de infraestructura para desarrollo profesional con Claude Code.

## Quick Start

```bash
# 1. Clonar
git clone <repo-url> ~/jps_dev_engine
cd ~/jps_dev_engine

# 2. Instalar commands globales
./install.sh

# 3. Verificar
ls -la ~/.claude/commands/
# Deberias ver: prd.md, plan.md, adapt-ui.md, optimize-agents.md
```

Los commands quedan disponibles globalmente en Claude Code: `/prd`, `/plan`, `/adapt-ui`, `/optimize-agents`.

## Que incluye

### Commands (`commands/`)

| Comando | Proposito |
|---------|-----------|
| `/prd` | Genera PRD + crea work item en Plane/Trello |
| `/plan` | Plan de implementacion + diseños UI via Stitch MCP |
| `/adapt-ui` | Escanea widgets existentes y genera mapeo UI |
| `/optimize-agents` | Audita y optimiza sistema agentico del proyecto |

### Arquitectura (`architecture/`)

Patrones y convenciones por stack:

| Stack | Contenido |
|-------|-----------|
| **Flutter 3.38+** | Clean Architecture, BLoC+Freezed, Responsive (3 layouts), DataSource pattern, Testing |
| **React 19.x** | Next.js 15 App Router, Server Components, TanStack Query, Zustand, Tailwind CSS |
| **Python 3.12+** | FastAPI, SQLAlchemy 2 async, Pydantic v2, Repository pattern |

### Agentes (`agents/`)

Templates genericos de agentes especializados:

| Agente | Rol |
|--------|-----|
| Orchestrator | Coordinador de subagentes |
| Feature Generator (AG-01) | Genera features completas (multi-stack) |
| UI/UX Designer (AG-02) | Diseño de interfaces |
| DB Specialist (AG-03) | Supabase, Neon, Firebase |
| QA Validation (AG-04) | Testing (85%+ coverage) |
| n8n Specialist (AG-05) | Workflows de automatizacion |
| Design Specialist (AG-06) | Google Stitch MCP |

### Agent Teams (`agent-teams/`)

Configuracion para Agent Teams nativo de Claude Code (feature experimental):

- Templates de team-config.json
- Prompts por rol (Lead, Flutter, React, DB, QA, Design)
- Hooks de calidad (teammate-idle, task-completed)
- Documentacion de patrones

### Infraestructura (`infra/`)

Patrones por servicio:

| Servicio | Contenido |
|----------|-----------|
| **Supabase** | MCP tools, RLS, migrations, Realtime, DataSource pattern |
| **Neon** | Connection pooling, branching, Drizzle ORM |
| **Stripe** | Webhooks, Checkout, Subscriptions, Customer Portal |
| **Firebase** | Firestore rules, Auth, Cloud Functions, Storage |
| **n8n** | Workflow patterns, triggers, webhooks |

### Diseño (`design/`)

Integracion con Google Stitch MCP:

- Configuracion y workflow
- Template de prompts reutilizable
- Estrategia de paralelizacion

### Templates (`templates/`)

Templates para configurar un nuevo proyecto:

- `CLAUDE.md.template` - Instrucciones del proyecto para Claude
- `settings.json.template` - Permisos y config de Claude Code
- `team-config.json.template` - Configuracion de Agent Teams

### Reglas (`rules/`)

- `GLOBAL_RULES.md` - Reglas universales multi-stack

## Flujo de desarrollo

```
/prd --> PRD + Work Item
  |
/plan --> Plan tecnico + Diseños Stitch (HTML)
  |
Implementacion --> Agentes/Teams ejecutan el plan
  |
/optimize-agents --> Validar y optimizar sistema agentico
```

## Uso en un proyecto existente

1. **Instalar commands** (si no lo has hecho): `./install.sh`
2. **Copiar CLAUDE.md template** al proyecto y personalizar
3. **Copiar agentes** que necesites a `.claude/agents/`
4. **Ejecutar `/optimize-agents audit`** para evaluar tu configuracion actual
5. **Seguir recomendaciones** del audit para mejorar

Ver guia completa en [docs/getting-started.md](docs/getting-started.md).

## Actualizacion

```bash
cd ~/jps_dev_engine
git pull
./install.sh
```

Los symlinks se actualizan automaticamente.

## Estructura completa

```
jps_dev_engine/
├── CLAUDE.md                  # Descripcion del engine
├── ENGINE_VERSION.yaml        # Version y changelog
├── install.sh                 # Instalador de commands
├── commands/                  # Commands globales (4 archivos)
├── agents/                    # Templates de agentes (7 roles)
├── agent-teams/               # Agent Teams config
│   ├── templates/
│   ├── prompts/
│   └── hooks/
├── architecture/              # Patrones por stack
│   ├── flutter/
│   ├── react/
│   └── python/
├── design/                    # Integracion Stitch MCP
│   └── stitch/
├── infra/                     # Patrones por servicio
│   ├── supabase/
│   ├── neon/
│   ├── stripe/
│   ├── firebase/
│   └── n8n/
├── templates/                 # Templates para nuevos proyectos
├── rules/                     # Reglas globales
└── docs/                      # Documentacion
```

## Filosofia

1. Consistencia > Velocidad
2. Documentacion ejecutable
3. Claude como arquitecto critico
4. Escalable desde dia 1
5. Multi-stack desde el core

## Licencia

MIT

---

v2.0.0 | 2026-02-24 | JPS Developer
