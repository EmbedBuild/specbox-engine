# MCP Dev Engine — 3 Tools Nuevas para v3.4.0 "Acceptance Engine"

> Prompt para implementar en el repositorio del MCP server (mcp-dev-engine).
> Estas tools se invocan desde los hooks del JPS Dev Engine v3.4.0 via `mcp-report.sh`.

---

## Contexto

El JPS Dev Engine v3.4.0 introduce un pipeline de validación funcional completo:

1. **Definition Quality Gate** — `/prd` rechaza acceptance criteria vagos/no-testables
2. **AG-09a Acceptance Tester** — Genera E2E tests desde AC-XX del PRD con evidencia visual
3. **AG-09b Acceptance Validator** — Valida cumplimiento funcional, emite ACCEPTED/CONDITIONAL/REJECTED
4. **Merge Secuencial** — Auto-merge si AG-08=GO + AG-09=ACCEPTED, pull main, siguiente card

Los hooks del engine ya reportan 3 tools existentes al MCP:
- `report_session` — telemetría de sesión
- `report_checkpoint` — progreso de fases de /implement
- `report_healing` — eventos de self-healing

Se necesitan **3 tools nuevas** para centralizar el tracking del pipeline de acceptance.

---

## Tool 1: `report_acceptance_tests`

### Propósito
Registrar los resultados de los acceptance tests generados por AG-09a (Paso 7.5 de /implement).

### Cuándo se invoca
Después de que AG-09a ejecuta los acceptance tests y genera `results.json` en `.quality/evidence/{feature}/acceptance/`.

### Invocación desde hook
```bash
.claude/hooks/mcp-report.sh report_acceptance_tests '{
  "project": "tempo-zenon",
  "feature": "staff_management",
  "timestamp": "2026-02-28T14:30:00Z",
  "stack": "flutter",
  "tests_total": 5,
  "tests_passed": 4,
  "tests_failed": 1,
  "results": [
    {"id": "AC-01", "description": "Usuario puede crear propiedad", "status": "PASS", "duration_ms": 3200, "screenshot": "AC-01_crear_propiedad.png"},
    {"id": "AC-02", "description": "Validación inline al perder foco", "status": "FAIL", "duration_ms": 1800, "error": "Expected red border on blur, found none", "screenshot": null},
    {"id": "AC-03", "description": "Listado paginado de 20 items", "status": "PASS", "duration_ms": 2100, "screenshot": "AC-03_listado.png"},
    {"id": "AC-04", "description": "Filtro por categoría", "status": "PASS", "duration_ms": 1500, "screenshot": "AC-04_filtro.png"},
    {"id": "AC-05", "description": "Búsqueda por nombre", "status": "PASS", "duration_ms": 900, "screenshot": "AC-05_busqueda.png"}
  ]
}'
```

### Schema de argumentos

```typescript
interface ReportAcceptanceTestsArgs {
  project: string;           // Nombre del proyecto
  feature: string;           // Nombre de la feature
  timestamp: string;         // ISO 8601
  stack: "flutter" | "react" | "python" | "google-apps-script";
  tests_total: number;
  tests_passed: number;
  tests_failed: number;
  results: Array<{
    id: string;              // AC-XX
    description: string;     // Descripción del criterio
    status: "PASS" | "FAIL"; // Resultado
    duration_ms?: number;    // Duración del test
    error?: string;          // Error si FAIL
    screenshot?: string;     // Nombre del archivo de evidencia
  }>;
}
```

### Almacenamiento sugerido
- Tabla: `acceptance_tests`
- Primary key: `(project, feature, timestamp)`
- Índices: `project`, `feature`, `status` (para dashboard de tendencias)

---

## Tool 2: `report_acceptance_validation`

### Propósito
Registrar el veredicto de AG-09b (Acceptance Validator) tras evaluar si la feature cumple todos los acceptance criteria del PRD.

### Cuándo se invoca
Después de que AG-09b genera `acceptance-report.json` en `.quality/evidence/{feature}/` (Paso 7.7 de /implement).

### Invocación desde hook
```bash
.claude/hooks/mcp-report.sh report_acceptance_validation '{
  "project": "tempo-zenon",
  "feature": "staff_management",
  "timestamp": "2026-02-28T14:35:00Z",
  "prd_source": "TEMPO-42",
  "validator": "AG-09b",
  "criteria_total": 5,
  "criteria_passed": 4,
  "criteria_failed": 1,
  "criteria_partial": 0,
  "verdict": "CONDITIONAL",
  "blocking_criteria": ["AC-02"],
  "criteria": [
    {
      "id": "AC-01",
      "status": "PASS",
      "has_code": true,
      "has_unit_test": true,
      "has_acceptance_test": true,
      "has_evidence": true
    },
    {
      "id": "AC-02",
      "status": "FAIL",
      "has_code": true,
      "has_unit_test": false,
      "has_acceptance_test": true,
      "has_evidence": false,
      "missing": "Validación inline on focus lost no implementada"
    }
  ],
  "healing_attempt": 0
}'
```

### Schema de argumentos

```typescript
interface ReportAcceptanceValidationArgs {
  project: string;
  feature: string;
  timestamp: string;         // ISO 8601
  prd_source: string;        // Work item ID o path al PRD
  validator: string;         // "AG-09b"
  criteria_total: number;
  criteria_passed: number;
  criteria_failed: number;
  criteria_partial: number;
  verdict: "ACCEPTED" | "CONDITIONAL" | "REJECTED";
  blocking_criteria: string[]; // IDs de criterios que bloquean
  criteria: Array<{
    id: string;              // AC-XX
    status: "PASS" | "FAIL" | "PARTIAL";
    has_code: boolean;
    has_unit_test: boolean;
    has_acceptance_test: boolean;
    has_evidence: boolean;
    missing?: string;        // Qué falta si FAIL
  }>;
  healing_attempt: number;   // 0 = primera evaluación, 1-2 = post-healing
}
```

### Almacenamiento sugerido
- Tabla: `acceptance_validations`
- Primary key: `(project, feature, timestamp)`
- Índices: `project`, `verdict`, `healing_attempt`

### Reglas de veredicto (referencia)
- **ACCEPTED**: 100% criteria PASS + evidencia completa
- **CONDITIONAL**: ≥ 80% PASS + ningún criterio F1 (funcionalidad principal) en FAIL
- **REJECTED**: < 80% PASS o cualquier criterio F1 en FAIL

---

## Tool 3: `report_merge_status`

### Propósito
Registrar el resultado del merge secuencial (Paso 8.5 de /implement): si la PR fue mergeada automáticamente o bloqueada.

### Cuándo se invoca
Después del intento de merge secuencial (Paso 8.5), tanto si fue exitoso como si fue bloqueado.

### Invocación desde hook
```bash
# Merge exitoso
.claude/hooks/mcp-report.sh report_merge_status '{
  "project": "tempo-zenon",
  "feature": "staff_management",
  "timestamp": "2026-02-28T14:40:00Z",
  "pr_number": 14,
  "branch": "feature/staff-management",
  "merge_status": "merged",
  "merge_method": "squash",
  "ag08_verdict": "GO",
  "ag09_verdict": "ACCEPTED",
  "blocked_by": null,
  "next_card": "TEMPO-43"
}'

# Merge bloqueado
.claude/hooks/mcp-report.sh report_merge_status '{
  "project": "tempo-zenon",
  "feature": "property_validation",
  "timestamp": "2026-02-28T15:10:00Z",
  "pr_number": 15,
  "branch": "feature/property-validation",
  "merge_status": "blocked",
  "merge_method": null,
  "ag08_verdict": "GO",
  "ag09_verdict": "REJECTED",
  "blocked_by": "AG-09b",
  "next_card": null
}'
```

### Schema de argumentos

```typescript
interface ReportMergeStatusArgs {
  project: string;
  feature: string;
  timestamp: string;         // ISO 8601
  pr_number: number;
  branch: string;
  merge_status: "merged" | "blocked" | "manual_review";
  merge_method?: "squash" | "merge" | "rebase" | null;
  ag08_verdict: "GO" | "CONDITIONAL_GO" | "NO_GO";
  ag09_verdict: "ACCEPTED" | "CONDITIONAL" | "REJECTED" | "SKIPPED";
  blocked_by?: "AG-08" | "AG-09b" | "user" | null;
  next_card?: string | null; // ID de la siguiente card si hay pipeline
}
```

### Almacenamiento sugerido
- Tabla: `merge_events`
- Primary key: `(project, feature, timestamp)`
- Índices: `project`, `merge_status`, `blocked_by`

---

## Dashboard queries sugeridas

Con estas 3 tools + las 3 existentes, el dashboard puede responder:

### Métricas de acceptance por proyecto
```sql
-- Tasa de aceptación por proyecto (últimos 30 días)
SELECT project,
       COUNT(*) as total_validations,
       SUM(CASE WHEN verdict = 'ACCEPTED' THEN 1 ELSE 0 END) as accepted,
       ROUND(100.0 * SUM(CASE WHEN verdict = 'ACCEPTED' THEN 1 ELSE 0 END) / COUNT(*), 1) as acceptance_rate
FROM acceptance_validations
WHERE timestamp > NOW() - INTERVAL '30 days'
GROUP BY project;
```

### Criterios que más fallan
```sql
-- Top 10 criterios que más fallan (para mejorar quality de definición)
SELECT c.id, c.missing, COUNT(*) as fail_count
FROM acceptance_validations v,
     jsonb_array_elements(v.criteria) as c
WHERE c->>'status' = 'FAIL'
GROUP BY c.id, c.missing
ORDER BY fail_count DESC
LIMIT 10;
```

### Pipeline throughput
```sql
-- Features mergeadas vs bloqueadas por semana
SELECT DATE_TRUNC('week', timestamp) as week,
       SUM(CASE WHEN merge_status = 'merged' THEN 1 ELSE 0 END) as merged,
       SUM(CASE WHEN merge_status = 'blocked' THEN 1 ELSE 0 END) as blocked
FROM merge_events
GROUP BY week
ORDER BY week;
```

### Healing effectiveness
```sql
-- ¿Cuántas veces el healing convierte REJECTED → ACCEPTED?
SELECT v1.project, v1.feature,
       v1.verdict as initial_verdict,
       v2.verdict as after_healing
FROM acceptance_validations v1
JOIN acceptance_validations v2
  ON v1.project = v2.project
  AND v1.feature = v2.feature
  AND v1.healing_attempt = 0
  AND v2.healing_attempt > 0
WHERE v1.verdict != 'ACCEPTED';
```

---

## Implementación sugerida

### Prioridad
1. `report_acceptance_validation` — el más importante, contiene el veredicto
2. `report_acceptance_tests` — complementario, resultados detallados de tests
3. `report_merge_status` — tracking de pipeline, útil para métricas de throughput

### Patrón
Seguir exactamente el mismo patrón que `report_session`, `report_checkpoint` y `report_healing`:
- Recibir JSON como argumento
- Validar schema
- Almacenar en tabla correspondiente
- Retornar `{ "status": "ok" }` o `{ "status": "error", "message": "..." }`

### Fire-and-forget
Las invocaciones desde hooks son fire-and-forget. Si el MCP no está disponible, los hooks no bloquean. Los datos se persisten localmente en `.quality/evidence/` y el MCP es solo un mirror centralizado para dashboards cross-proyecto.

---

*JPS Dev Engine v3.4.0 "Acceptance Engine" — MCP Tools Specification*
