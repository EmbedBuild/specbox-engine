# Referencia de Commands

## Instalacion

Los commands se instalan como symlinks globales en `~/.claude/commands/`:

```bash
./install.sh          # Instalar/actualizar
./install.sh --dry-run    # Ver que haria sin cambios
./install.sh --uninstall  # Desinstalar
```

## Commands disponibles

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
