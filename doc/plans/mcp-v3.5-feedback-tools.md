# MCP Dev Engine — 2 Tools Nuevas + 1 Ajuste para v3.5.0 "Feedback Loop"

> Prompt para implementar en el repositorio del MCP server (mcp-dev-engine).
> Estas tools se invocan desde los hooks del SDD-JPS Engine v3.5.0 via `mcp-report.sh`.

---

## Contexto

El SDD-JPS Engine v3.5.0 introduce un pipeline de feedback de testing manual:

1. **AG-10 Developer Tester** — Captura feedback humano durante testing manual
2. **/feedback skill** — Genera evidencia local (FB-NNN.json) + GitHub issue
3. **Feedback invalida acceptance** — Puede cambiar AG-09b verdict de ACCEPTED a INVALIDATED
4. **/feedback resolve** — Marca feedback resuelto, AC-XX pasa a NEEDS_REVALIDATION
5. **Merge gate** — Paso 8.5 verifica feedback abierto antes de auto-merge

Los hooks del engine ya reportan 6 tools existentes al MCP:
- `report_session` — telemetria de sesion
- `report_checkpoint` — progreso de fases de /implement
- `report_healing` — eventos de self-healing
- `report_acceptance_tests` — resultados de AG-09a
- `report_acceptance_validation` — veredicto de AG-09b
- `report_merge_status` — resultado del merge secuencial

Se necesitan **2 tools nuevas** y **1 ajuste** a tool existente para centralizar el tracking del feedback loop.

---

## Tool Nueva 1: `report_feedback`

### Proposito
Registrar cada feedback ticket creado por el developer durante testing manual via `/feedback`.

### Cuando se invoca
Cuando el developer ejecuta `/feedback` y se crea un FB-NNN.json en `.quality/evidence/{feature}/feedback/`.

### Invocacion desde hook
```bash
.claude/hooks/mcp-report.sh report_feedback '{
  "project": "tempo-zenon",
  "feature": "invoice-detail",
  "timestamp": "2026-03-01T14:30:00Z",
  "feedback_id": "FB-001",
  "severity": "critical",
  "status": "open",
  "ac_ids": ["AC-03"],
  "description": "Invoice detail shows PDF open button instead of inline preview with zoom",
  "expected": "Inline PDF preview with zoom and pan controls embedded in the page",
  "actual": "Opens a new tab with raw PDF without zoom controls",
  "github_issue_number": 42,
  "github_issue_url": "https://github.com/owner/repo/issues/42",
  "invalidates_acceptance": true,
  "reporter": "developer"
}'
```

### Schema de argumentos

```typescript
interface ReportFeedbackArgs {
  project: string;              // Nombre del proyecto
  feature: string;              // Nombre de la feature
  timestamp: string;            // ISO 8601
  feedback_id: string;          // FB-NNN
  severity: "critical" | "major" | "minor";
  status: "open" | "resolved";
  ac_ids: string[];             // AC-XX afectados (puede estar vacio)
  description: string;          // Descripcion del problema
  expected: string;             // Comportamiento esperado
  actual: string;               // Comportamiento actual
  github_issue_number?: number; // Numero del issue creado (null si no se creo)
  github_issue_url?: string;    // URL del issue
  invalidates_acceptance: boolean; // Si invalida un ACCEPTED previo
  reporter: string;             // "developer"
}
```

### Almacenamiento sugerido
- Tabla: `feedback_tickets`
- Primary key: `(project, feature, feedback_id)`
- Indices: `project`, `feature`, `severity`, `status`, `invalidates_acceptance`

---

## Tool Nueva 2: `report_feedback_resolution`

### Proposito
Registrar cuando un feedback ticket es resuelto via `/feedback resolve`.

### Cuando se invoca
Cuando el developer ejecuta `/feedback resolve FB-NNN` y el ticket pasa a status "resolved".

### Invocacion desde hook
```bash
.claude/hooks/mcp-report.sh report_feedback_resolution '{
  "project": "tempo-zenon",
  "feature": "invoice-detail",
  "timestamp": "2026-03-01T16:00:00Z",
  "feedback_id": "FB-001",
  "resolution": "Implementado PDF viewer inline con controles de zoom y pan usando flutter_pdfium",
  "github_issue_number": 42,
  "github_issue_closed": true,
  "ac_ids_revalidation_needed": ["AC-03"],
  "remaining_open_feedback": 0,
  "blocking_resolved": true
}'
```

### Schema de argumentos

```typescript
interface ReportFeedbackResolutionArgs {
  project: string;
  feature: string;
  timestamp: string;                  // ISO 8601
  feedback_id: string;                // FB-NNN
  resolution: string;                 // Descripcion de la resolucion
  github_issue_number?: number;       // Issue cerrado
  github_issue_closed: boolean;       // Si se cerro exitosamente
  ac_ids_revalidation_needed: string[]; // AC-XX que necesitan re-validacion
  remaining_open_feedback: number;    // Feedback abiertos restantes del feature
  blocking_resolved: boolean;         // Si se resolvio un feedback bloqueante
}
```

### Almacenamiento sugerido
- Tabla: `feedback_resolutions`
- Primary key: `(project, feature, feedback_id, timestamp)`
- O bien: actualizar `feedback_tickets` con campos `resolution`, `resolved_at`
- Indices: `project`, `blocking_resolved`

---

## Ajuste a Tool Existente: `report_merge_status`

### Cambio requerido
Agregar campo `feedback_blocking` al schema existente para indicar si el merge fue bloqueado por feedback de developer.

### Schema actualizado

```typescript
interface ReportMergeStatusArgs {
  project: string;
  feature: string;
  timestamp: string;
  pr_number: number;
  branch: string;
  merge_status: "merged" | "blocked" | "manual_review";
  merge_method?: "squash" | "merge" | "rebase" | null;
  ag08_verdict: "GO" | "CONDITIONAL_GO" | "NO_GO";
  ag09_verdict: "ACCEPTED" | "CONDITIONAL" | "REJECTED" | "INVALIDATED" | "SKIPPED";  // NUEVO: INVALIDATED
  blocked_by?: "AG-08" | "AG-09b" | "feedback" | "user" | null;  // NUEVO: "feedback"
  feedback_blocking?: {                    // NUEVO campo
    total_open: number;
    blocking_ids: string[];                // ["FB-001", "FB-002"]
    invalidated_criteria: string[];        // ["AC-03"]
  } | null;
  next_card?: string | null;
}
```

### Invocacion ejemplo (merge bloqueado por feedback)
```bash
.claude/hooks/mcp-report.sh report_merge_status '{
  "project": "tempo-zenon",
  "feature": "invoice-detail",
  "timestamp": "2026-03-01T15:00:00Z",
  "pr_number": 16,
  "branch": "feature/invoice-detail",
  "merge_status": "blocked",
  "merge_method": null,
  "ag08_verdict": "GO",
  "ag09_verdict": "INVALIDATED",
  "blocked_by": "feedback",
  "feedback_blocking": {
    "total_open": 1,
    "blocking_ids": ["FB-001"],
    "invalidated_criteria": ["AC-03"]
  },
  "next_card": null
}'
```

---

## Dashboard queries nuevas

Con las 2 tools nuevas + ajuste, el dashboard puede responder:

### Feedback por proyecto y severidad
```sql
-- Distribucion de feedback por proyecto y severidad
SELECT project,
       severity,
       COUNT(*) as total,
       SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
       SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved
FROM feedback_tickets
GROUP BY project, severity
ORDER BY project, severity;
```

### Tiempo medio de resolucion
```sql
-- Tiempo medio entre creacion y resolucion de feedback
SELECT f.project,
       f.severity,
       AVG(EXTRACT(EPOCH FROM (r.timestamp::timestamp - f.timestamp::timestamp)) / 3600) as avg_hours_to_resolve
FROM feedback_tickets f
JOIN feedback_resolutions r
  ON f.project = r.project
  AND f.feature = r.feature
  AND f.feedback_id = r.feedback_id
GROUP BY f.project, f.severity;
```

### Merges bloqueados por feedback vs por acceptance
```sql
-- Comparativa: merges bloqueados por feedback vs AG-09b vs AG-08
SELECT DATE_TRUNC('week', timestamp) as week,
       SUM(CASE WHEN blocked_by = 'AG-08' THEN 1 ELSE 0 END) as blocked_quality,
       SUM(CASE WHEN blocked_by = 'AG-09b' THEN 1 ELSE 0 END) as blocked_acceptance,
       SUM(CASE WHEN blocked_by = 'feedback' THEN 1 ELSE 0 END) as blocked_feedback,
       SUM(CASE WHEN merge_status = 'merged' THEN 1 ELSE 0 END) as merged
FROM merge_events
GROUP BY week
ORDER BY week;
```

### Criterios mas invalidados por feedback
```sql
-- Criterios AC-XX que mas se invalidan por feedback de developer
SELECT unnest(ac_ids) as criterion,
       COUNT(*) as invalidation_count,
       COUNT(DISTINCT project) as projects_affected
FROM feedback_tickets
WHERE invalidates_acceptance = true
GROUP BY criterion
ORDER BY invalidation_count DESC
LIMIT 10;
```

### Feedback que bloquea pipeline
```sql
-- Features actualmente bloqueadas por feedback
SELECT f.project, f.feature, f.feedback_id, f.severity, f.description,
       f.timestamp as reported_at,
       f.github_issue_url
FROM feedback_tickets f
WHERE f.status = 'open'
  AND f.severity IN ('critical', 'major')
ORDER BY f.timestamp;
```

---

## Implementacion sugerida

### Prioridad
1. `report_feedback` — el mas importante, registra cada ticket de feedback
2. Ajuste `report_merge_status` — agregar `INVALIDATED` y `feedback` como valores validos + campo `feedback_blocking`
3. `report_feedback_resolution` — complementario, tracking de resolucion

### Patron
Seguir exactamente el mismo patron que las 6 tools existentes:
- Recibir JSON como argumento
- Validar schema
- Almacenar en tabla correspondiente
- Retornar `{ "status": "ok" }` o `{ "status": "error", "message": "..." }`

### Fire-and-forget
Las invocaciones desde hooks son fire-and-forget. Si el MCP no esta disponible, los hooks no bloquean. Los datos se persisten localmente en `.quality/evidence/{feature}/feedback/` y el MCP es solo un mirror centralizado para dashboards cross-proyecto.

### Migracion de base de datos
- Crear tabla `feedback_tickets` con schema de Tool 1
- Crear tabla `feedback_resolutions` con schema de Tool 2 (o agregar columnas a `feedback_tickets`)
- Alterar tabla `merge_events`: agregar columna `feedback_blocking` (JSONB, nullable)
- Alterar enum/check de `ag09_verdict`: agregar valor `"INVALIDATED"`
- Alterar enum/check de `blocked_by`: agregar valor `"feedback"`

---

## Sala de Maquinas (dashboard global)

Agregar al dashboard `get_sala_de_maquinas` una nueva seccion:

### Feedback Loop
```
| Proyecto | Feature | FB Open | FB Blocking | Invalidated AC | Oldest Open |
|----------|---------|---------|-------------|----------------|-------------|
| tempo    | invoice | 1       | 1 (FB-001)  | AC-03          | 2h ago      |
| cashflow | reports | 0       | 0           | -              | -           |
```

Y metricas globales:
- **Feedback rate**: feedback/feature (promedio global)
- **Resolution time**: tiempo medio de resolucion por severidad
- **Invalidation rate**: % de features que reciben feedback que invalida acceptance

---

*SDD-JPS Engine v3.5.0 "Feedback Loop" — MCP Tools Specification*
