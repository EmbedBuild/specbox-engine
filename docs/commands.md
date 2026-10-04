# Referencia de Commands y Skills

> **v5.25.0:** Los commands se convirtieron en **Agent Skills** en `.claude/skills/`. La carpeta `commands/` se retiró: las Skills son la única versión, con auto-discovery, context isolation y hooks.

## Instalacion

```bash
./install.sh          # Instalar skills + hooks
./install.sh --dry-run    # Ver que haria sin cambios
./install.sh --uninstall  # Desinstalar
```

Instala:
- **Skills** enlazadas (symlink) en `~/.claude/skills/`
- **Hooks** copiados a `~/.claude/hooks/`

## Skills disponibles (v6.14.2)

| Skill | Modo | Descripcion |
|-------|------|-------------|
| /prd | direct | Genera PRDs estructurados con Definition Quality Gate |
| /visual-setup | direct | Brand Kit + Stitch DS + VEG + Multi-Form-Factor |
| /plan | direct | Planes tecnicos con UI analysis, VEG y Stitch |
| /implement | direct | Autopilot end-to-end con checkpoint/resume + AG-09 |
| /adapt-ui | fork:Explore | Mapeo de componentes UI (read-only) |
| /optimize-agents | fork:Explore | Auditoria del sistema agentico (read-only) |
| /quality-gate | direct | Gates de calidad adaptativos |
| /explore | fork:Explore | Exploracion read-only del codebase |
| /feedback | direct | Captura feedback manual + GitHub issues |
| /check-designs | fork:Explore | Compliance retroactivo de diseños Stitch |
| /acceptance-check | direct | Standalone BDD acceptance sin /implement |
| /quickstart | direct | Tutorial interactivo para nuevos usuarios |
| /release | direct | Audit + version bump + changelog + push |
| /compliance | direct | Compliance audit del engine |
| /audit | direct | Quality Audit ISO/IEC 25010 (SQuaRE, AG-11) |
| /stripe-connect | direct | **v5.25.0** Scaffold de marketplace Stripe Connect (Express + Direct charges + embedded) |
| /stripe-standard | direct | Scaffold de Stripe cuenta estándar (suscripciones, metered, checkout one-shot) |
| /stripe-switch-account | direct | Rotación segura de la cuenta Stripe activa (dry-run + rollback) |
| /switch-backend | direct | Cambia el backend de tracking (FreeForm / Trello / Plane / Native) sin perder avance |
| /discovery | direct | Product Discovery ligero antes de /prd (ICP, JTBD, validation gate) |
| /app-init | direct | Crea o refresca `doc/app/app_prd.md` y `doc/app/app_spec.md` (canon del proyecto) |
| /app-sync | direct | Verifica, repara o reconstruye los documentos canónicos (`--check`, `--repair`, `--review`, `--rebuild-from-tracking`) |
| /queue-review | direct | Revisa y resuelve `doc/app/decisions_queue.md` (decisiones diferidas del autopilot) |
| /handoff | direct | Persiste el estado fino de la sesión en `.quality/handoff.md` y Engram |
| /manual-test | direct | Pruebas manuales sistemáticas con resolución de bugs en vivo y evidencia |

Las Skills con `fork` corren en subagentes aislados — no contaminan la sesion principal.

---

## Commands en detalle

### /prd

**Skill**: `.claude/skills/prd/SKILL.md`
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

**Skill**: `.claude/skills/plan/SKILL.md`
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

**Skill**: `.claude/skills/implement/SKILL.md`
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

**Skill**: `.claude/skills/adapt-ui/SKILL.md`
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

**Skill**: `.claude/skills/optimize-agents/SKILL.md`
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
