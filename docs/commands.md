# Referencia de Commands y Skills

> **v5.18.0:** Los commands han sido migrados a **Agent Skills** en `.claude/skills/`. Los archivos en `commands/` se mantienen como referencia. Las Skills son la version activa con auto-discovery, context isolation y hooks.

## Instalacion

```bash
./install.sh          # Instalar commands + skills + hooks
./install.sh --dry-run    # Ver que haria sin cambios
./install.sh --uninstall  # Desinstalar
```

Instala:
- **Commands** (legacy) como symlinks en `~/.claude/commands/`
- **Skills** (v3.5) copiados a `~/.claude/skills/`
- **Hooks** (v3.5) copiados a `~/.claude/hooks/`

## Skills disponibles (v3.5)

| Skill | Modo | Descripcion |
|-------|------|-------------|
| /prd | fork:Plan | Genera PRDs estructurados |
| /plan | fork:Plan | Planes tecnicos con UI analysis y Stitch |
| /implement | direct | Autopilot end-to-end con checkpoint/resume |
| /adapt-ui | fork:Explore | Mapeo de componentes UI |
| /optimize-agents | fork:Explore | Auditoria del sistema agentico |
| /quality-gate | direct | Gates de calidad adaptativos |
| /explore | fork:Explore | Exploracion read-only del codebase |

Las Skills con `fork` corren en subagentes aislados — no contaminan la sesion principal.

---

## Commands en detalle

### /prd

**Archivo**: `commands/prd.md`
**Proposito**: Genera un PRD (Product Requirements Document) y opcionalmente crea un Work Item en Plane.

**Uso**:
```
/prd "titulo" "descripcion de requerimientos"
```

**Que hace**:
1. Detecta tipo de PRD (feature o tecnico/refactor)
2. Recopila informacion (funcionalidades, interacciones UI)
3. Genera PRD con template estructurado
4. Opcionalmente crea Work Item en Plane

**Output**: PRD en formato markdown con secciones de funcionalidades, interacciones UI, stack tecnico y criterios de aceptacion.

---

### /plan

**Archivo**: `commands/plan.md`
**Proposito**: Genera un plan de implementacion detallado con analisis de componentes UI y opcionalmente diseños via Stitch MCP.

**Uso**:
```
/plan PROYECTO-42       # Desde work item de Plane
/plan "descripcion"     # Desde texto directo
/plan feature:nombre    # Analizar feature existente
```

**Que hace**:
1. Detecta origen y extrae requisitos
2. Explora proyecto (stack, agentes, widgets)
3. Analiza componentes UI (obligatorio)
4. Detecta agentes/skills disponibles
5. Genera plan de implementacion por fases
6. Genera diseños en Stitch MCP (si hay UI)
7. Guarda plan en `doc/plans/`

**Output**: Plan en `doc/plans/{nombre}_plan.md` + HTMLs en `doc/design/{feature}/`

---

### /implement

**Archivo**: `commands/implement.md`
**Proposito**: Autopilot de implementacion end-to-end. Lee un plan, crea rama, ejecuta todas las fases, genera diseños Stitch si aplica, valida con QA, y crea PR.

**Uso**:
```
/implement nombre_del_plan        # Busca doc/plans/{nombre}_plan.md
/implement doc/plans/mi_plan.md   # Path directo
/implement                        # Lista planes disponibles
```

**Que hace**:
1. Carga y parsea el plan de `doc/plans/`
2. Crea rama `feature/{nombre-del-plan}` desde main
3. Detecta si el plan requiere diseños Stitch
4. Si faltan diseños: genera con Stitch MCP automaticamente
5. Ejecuta design-to-code (si hay HTMLs de diseño)
6. Ejecuta cada fase del plan en orden
7. Commits parciales por fase
8. Integracion (DI, routing, config)
9. QA: tests con 85%+ coverage, lint
10. Push y crea PR con resumen completo via `gh`

**Output**: Rama con commits por fase + PR lista para review.

---

### /adapt-ui

**Archivo**: `commands/adapt-ui.md`
**Proposito**: Escanea la estructura de widgets de un proyecto y genera un archivo de mapeo UI.

**Uso**:
```
/adapt-ui /path/al/proyecto              # Solo detectar
/adapt-ui /path/al/proyecto --normalize  # Detectar + mover widgets a core
```

**Que hace**:
1. Valida proyecto (Flutter, React, etc.)
2. Detecta ubicacion de widgets
3. Detecta widgets dispersos (candidatos a normalizar)
4. Escanea y categoriza widgets
5. Detecta design tokens
6. Genera `ui-adapter.md`
7. Opcionalmente normaliza ubicaciones

**Output**: `.claude/ui-adapter.md` con mapeo completo de componentes.

---

### /optimize-agents

**Archivo**: `commands/optimize-agents.md`
**Proposito**: Audita, reporta y optimiza el sistema agentico de un proyecto. Soporta tanto subagentes legacy como Agent Teams nativos.

**Modos**:
```
/optimize-agents audit       # Analisis completo con score
/optimize-agents report      # Reporte ejecutivo
/optimize-agents apply       # Aplicar recomendaciones
/optimize-agents team-init   # Inicializar Agent Teams
/optimize-agents migrate     # Migrar legacy → Agent Teams
```

**Que analiza** (6 dimensiones):
1. Documentation Sync (25pts) — CLAUDE.md vs codigo real
2. Validation Strategy (15pts) — hooks y gates de calidad
3. Model Optimization (10pts) — asignacion de modelos por complejidad
4. Team Coordination (20pts) — coordinacion entre agentes
5. Deprecation Hygiene (15pts) — limpieza de codigo obsoleto
6. Agent Teams Readiness (15pts) — preparacion para Agent Teams

**Deteccion**:
- Multi-stack: Flutter, React, Python, Rust, Go, Ruby, .NET
- Infra: Supabase, Firebase, Neon, Stripe, GitHub Actions, Docker, n8n, Stitch MCP
- Agentes: Legacy (.claude/agents/) + Agent Teams nativos

**Output**: Score /100 con recomendaciones priorizadas.

---

## Quality Scripts (v3.5)

Scripts utilitarios para gestión de calidad:

- `create-baseline.sh` — Genera baseline de métricas (lint, coverage, tests)
- `update-baseline.sh` — Actualiza baseline con política ratchet (solo mejora, nunca empeora)
- `analyze-sessions.sh` — Telemetría: sesiones, context tokens, healing, checkpoints
- `context-budget.sh` — Estima coste en tokens de archivos/directorios
