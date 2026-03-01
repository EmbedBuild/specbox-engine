---
name: developer-feedback
description: >
  Capture developer testing feedback as structured evidence and GitHub issues.
  Use when the user says "report feedback", "found a bug", "this doesn't work",
  "feedback on feature", "AC-XX is wrong", or reports an issue found during
  manual testing. Links feedback to acceptance criteria and blocks merge if unresolved.
context: direct
allowed-tools: Read, Grep, Glob, Bash(*), Write, Edit, mcp__github__create_issue
---

# /feedback (Global)

Captura feedback de testing manual del desarrollador, genera evidencia local y crea GitHub issue vinculado a acceptance criteria.

## Uso

```
/feedback [feature] [--ac AC-XX] [--severity critical|major|minor]
```

**Modos de invocacion:**
- `/feedback invoice-detail` → Feedback para feature "invoice-detail"
- `/feedback` → Sin argumento: auto-detecta feature desde la rama actual
- `/feedback invoice-detail --ac AC-03 --severity critical` → Con metadata inline
- `/feedback resolve FB-NNN` → Marcar feedback como resuelto
- `/feedback list [feature]` → Listar feedback del feature

---

## Paso 0: Detectar Contexto del Feature

### 0.1 Resolver feature name

```
¿Que recibi?
├── nombre_de_feature → Usar directamente
├── "resolve FB-NNN" → Ir a sub-comando Resolve (Paso R)
├── "list [feature]" → Ir a sub-comando List (Paso L)
├── sin argumento → Detectar desde rama actual
│   ├── feature/invoice-detail → feature = "invoice-detail"
│   ├── main/master → Preguntar: "¿Para que feature es el feedback?"
│   └── otro → Extraer nombre de la rama
└── Argumento no reconocido → Preguntar al usuario
```

```bash
git branch --show-current
```

### 0.2 Verificar directorio de evidencia

```bash
ls .quality/evidence/${feature}/ 2>/dev/null
```

Si no existe:
- Crear directorio: `mkdir -p .quality/evidence/${feature}/feedback/`
- INFO: "Directorio de evidencia creado para '{feature}'."

Si existe pero no tiene subdirectorio feedback:
- Crear: `mkdir -p .quality/evidence/${feature}/feedback/`

### 0.3 Detectar repositorio GitHub

```bash
git remote get-url origin 2>/dev/null
```

Extraer owner/repo del URL para la creacion del GitHub issue.
Si no hay remote → WARNING: "No se detecto repositorio remoto. Solo se creara evidencia local."

---

## Paso 1: Localizar PRD y Acceptance Criteria

### 1.1 Buscar PRD

```
¿Donde esta el PRD?
├── .quality/evidence/${feature}/acceptance-report.json existe
│   └── Extraer criteria de ahi (ya parseados por AG-09b)
├── doc/prd/${feature}.md existe
│   └── Parsear seccion "Criterios de Aceptacion > Funcionales"
├── Plan referencia work item (PROYECTO-XX)
│   └── Obtener via doc/plans/${feature}_plan.md
└── No se encuentra PRD
    └── Continuar SIN AC-XX linkage (campo ac_ids sera [])
    └── WARNING: "No PRD found. Feedback will be created without AC-XX linkage."
```

### 1.2 Mostrar AC-XX disponibles

Si se encontro PRD, listar los AC-XX con sus descripciones para que el usuario pueda seleccionar.

Si ya existe `acceptance-report.json`, mostrar tambien el status actual de cada AC-XX:

```
AC-XX disponibles:
  AC-01: Usuario puede crear propiedad [PASS]
  AC-02: Validacion inline al perder foco [PASS]
  AC-03: Preview de factura con zoom [PASS]
```

---

## Paso 2: Recopilar Feedback del Desarrollador

### 2.1 Informacion requerida

Preguntar interactivamente (a menos que se proporcione inline con --ac y --severity):

| Campo | Obligatorio | Ejemplo |
|-------|:-----------:|---------|
| **description** | Si | "El boton de factura abre un PDF en vez de mostrar preview inline con zoom" |
| **expected** | Si | "Preview inline del PDF con controles de zoom y pan, embebido en la pagina" |
| **actual** | Si | "Se abre una nueva pestana con el PDF raw sin controles de zoom" |
| **severity** | Si | `critical` / `major` / `minor` |
| **ac_ids** | No | `["AC-03", "AC-05"]` (seleccionar de la lista del Paso 1) |
| **screenshot_path** | No | `./screenshots/invoice-bug.png` (path relativo o absoluto) |
| **steps_to_reproduce** | No | Lista de pasos para reproducir |

### 2.2 Validar severity

| Severity | Criterio | Efecto en merge |
|----------|----------|-----------------|
| `critical` | Funcionalidad principal rota, crash, data loss | **BLOQUEA** merge |
| `major` | Funcionalidad secundaria rota, UX grave | **BLOQUEA** merge |
| `minor` | Cosmetico, texto incorrecto, mejora visual | NO bloquea (warning) |

### 2.3 Validar AC-XX

Si el usuario proporciono --ac AC-XX:
- Verificar que el AC-XX existe en el PRD o acceptance-report.json
- Si no existe → WARNING y preguntar si continuar sin linkage

---

## Paso 3: Asignar ID al Feedback

### 3.1 Calcular siguiente FB-NNN

```bash
existing=$(ls .quality/evidence/${feature}/feedback/FB-*.json 2>/dev/null | wc -l | tr -d ' ')
next_id=$(printf "FB-%03d" $((existing + 1)))
```

### 3.2 Timestamp

```bash
timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

---

## Paso 4: Crear Archivo de Feedback Local

### 4.1 Guardar JSON

Archivo: `.quality/evidence/${feature}/feedback/${next_id}.json`

```json
{
  "id": "FB-001",
  "feature": "{feature}",
  "timestamp": "2026-03-01T14:30:00Z",
  "reporter": "developer",
  "severity": "critical",
  "status": "open",
  "ac_ids": ["AC-03"],
  "description": "Invoice detail shows PDF open button instead of inline preview",
  "expected": "Inline PDF preview with zoom and pan controls embedded in the page",
  "actual": "Opens a new tab with raw PDF without zoom controls",
  "steps_to_reproduce": [
    "Navigate to Invoices list",
    "Click on any invoice",
    "Click 'View PDF' button"
  ],
  "screenshot": "feedback/FB-001-screenshot.png",
  "github_issue": null,
  "invalidates_acceptance": true,
  "resolution": null,
  "resolved_at": null
}
```

### 4.2 Copiar screenshot (si se proporciono)

Si `screenshot_path` fue proporcionado:
```bash
cp "${screenshot_path}" ".quality/evidence/${feature}/feedback/${next_id}-screenshot.png"
```

Si no se proporciono screenshot → `"screenshot": null`

### 4.3 Determinar `invalidates_acceptance`

```
SI ac_ids no esta vacio:
  SI acceptance-report.json existe:
    SI algun AC-XX referenciado tiene status "PASS":
      invalidates_acceptance = true
      WARNING: "Este feedback invalida un criterio previamente ACCEPTED."
    SI todos los AC-XX referenciados ya tienen status "FAIL":
      invalidates_acceptance = false
      INFO: "Los criterios referenciados ya estaban en FAIL."
  ELSE:
    invalidates_acceptance = true (precaucion)
ELSE (sin AC-XX linkage):
  invalidates_acceptance = false
  SI severity == "critical":
    invalidates_acceptance = true (un critical sin AC-XX linkage aun bloquea)
```

---

## Paso 5: Crear GitHub Issue

### 5.1 Pre-condicion

Si no se detecto remote en Paso 0.3 → saltar este paso. `"github_issue": null`.

### 5.2 Construir titulo y body

**Titulo**: `[FB-{NNN}] [{severity}] {description_short} ({feature})`
Max 100 caracteres. Truncar description si necesario.

**Body**:
```markdown
## Developer Feedback: FB-{NNN}

**Feature**: {feature}
**Severity**: {severity}
**Date**: {timestamp}
**Acceptance Criteria**: {ac_ids o "N/A"}

### Expected Behavior
{expected}

### Actual Behavior
{actual}

### Steps to Reproduce
{steps_to_reproduce o "Not provided"}

### Screenshot
{Si hay screenshot: adjuntar referencia. Si no: "Not provided"}

### Impact on Acceptance
{Si invalidates_acceptance: "⚠️ This feedback invalidates previously ACCEPTED criteria: {ac_ids}. Merge is blocked until resolved."}
{Si no: "No direct impact on acceptance criteria."}

---
Filed by [JPS Dev Engine](https://github.com/jesusperezdeveloper/jps_dev_engine) `/feedback`
```

### 5.3 Labels

```
labels: ["feedback", "{severity}"]
```

### 5.4 Crear issue via MCP

Usar `mcp__github__create_issue` con owner, repo, title, body, labels.

### 5.5 Actualizar JSON local

Tras crear el issue, actualizar `${next_id}.json`:
```json
"github_issue": {"number": N, "url": "https://github.com/{owner}/{repo}/issues/{N}"}
```

Si falla la creacion del issue:
- WARNING: "No se pudo crear GitHub issue. Evidencia local guardada."
- `"github_issue": null`
- NO bloquear el flujo

---

## Paso 6: Actualizar Estado del Pipeline

### 6.1 Actualizar acceptance-report.json (si aplica)

Solo si `invalidates_acceptance == true` Y `acceptance-report.json` existe:

Para cada AC-XX referenciado en ac_ids con status "PASS":
- Cambiar `"status": "PASS"` → `"status": "INVALIDATED"`
- Agregar campo `"invalidated_by": "FB-{NNN}"`
- Agregar campo `"invalidated_at": "{timestamp}"`

Recalcular summary:
- Si antes era ACCEPTED y ahora hay criterios INVALIDATED → cambiar verdict a `"INVALIDATED"`
- Actualizar `blocking_criteria` con los criterios invalidados

### 6.2 Crear/actualizar feedback-summary.json

Archivo: `.quality/evidence/${feature}/feedback-summary.json`

Leer todos los `FB-*.json` del directorio y agregar:

```json
{
  "feature": "{feature}",
  "last_updated": "ISO",
  "total": 3,
  "open": 2,
  "resolved": 1,
  "by_severity": {
    "critical": 1,
    "major": 1,
    "minor": 0
  },
  "blocking": true,
  "blocking_ids": ["FB-001", "FB-002"],
  "invalidated_criteria": ["AC-03"]
}
```

Campo `blocking`: `true` si hay algun feedback open con severity "critical" o "major".
Campo `blocking_ids`: lista de FB-NNN que son open + critical/major.
Campo `invalidated_criteria`: union de ac_ids de todos los FB-NNN con invalidates_acceptance=true y status=open.

---

## Output Final

```
## Feedback Registrado

**ID**: FB-{NNN}
**Feature**: {feature}
**Severity**: {severity}
**AC-XX afectados**: {ac_ids o "Ninguno"}

### Evidencia local
`.quality/evidence/{feature}/feedback/FB-{NNN}.json`

### GitHub Issue
{url del issue o "No creado (sin remote)"}

### Impacto en Acceptance
{Si invalidates_acceptance: "⚠️ El veredicto de AG-09b ha sido INVALIDATED. AC-XX cambiados a INVALIDATED. El merge esta bloqueado hasta resolver este feedback."}
{Si no: "Sin impacto directo en acceptance gate."}

### Siguiente paso
- Corregir el problema y ejecutar `/feedback resolve FB-{NNN}`
- O re-ejecutar `/implement` que re-evaluara los criterios
```

---

## Sub-comando: /feedback resolve FB-{NNN}

### Paso R.1: Localizar feedback

```bash
cat .quality/evidence/${feature}/feedback/FB-{NNN}.json
```

Si no se proporciono feature → buscar FB-{NNN}.json en todos los features:
```bash
find .quality/evidence/ -name "FB-{NNN}.json" 2>/dev/null
```

### Paso R.2: Validar resolucion

Preguntar al desarrollador:
- "¿El problema fue corregido? Describe brevemente la resolucion."

### Paso R.3: Actualizar feedback JSON

Modificar `FB-{NNN}.json`:
```json
{
  "status": "resolved",
  "resolution": "{descripcion de la resolucion}",
  "resolved_at": "ISO timestamp"
}
```

### Paso R.4: Actualizar acceptance-report.json

Si el feedback tenia `invalidates_acceptance: true` y AC-XX fue INVALIDATED por este feedback:
- Cambiar status del AC-XX de "INVALIDATED" a "NEEDS_REVALIDATION"
- Esto indica que AG-09b debe re-ejecutarse para confirmar

**IMPORTANTE**: NEEDS_REVALIDATION no es PASS. El merge sigue bloqueado hasta que AG-09b re-valide.

### Paso R.5: Actualizar feedback-summary.json

Recalcular contadores (total, open, resolved, blocking, blocking_ids, invalidated_criteria).

### Paso R.6: Cerrar GitHub issue

Si `github_issue` no es null:

```bash
gh issue comment {number} --body "✅ Resolved: {resolution}

Marked as resolved by JPS Dev Engine \`/feedback resolve\`"

gh issue close {number}
```

### Paso R.7: Output

```
## Feedback Resuelto

**ID**: FB-{NNN}
**Resolucion**: {resolution}
**GitHub Issue**: Cerrado ({url})

### Estado del pipeline
{Si quedan feedback blocking: "Aun hay {N} feedback abiertos bloqueando merge: {blocking_ids}"}
{Si no quedan blocking: "No hay feedback bloqueante. AC-XX en NEEDS_REVALIDATION — ejecutar /implement para re-validar."}
```

---

## Sub-comando: /feedback list [feature]

### Paso L.1: Resolver feature

Si se proporciona feature → usar ese.
Si no → detectar desde rama actual (misma logica que Paso 0.1).

### Paso L.2: Listar feedback

Leer `feedback-summary.json` y todos los `FB-*.json`:

```
## Feedback: {feature}

| ID | Severity | AC-XX | Status | GitHub | Descripcion |
|----|----------|-------|--------|--------|-------------|
| FB-001 | critical | AC-03 | open | #42 | Preview PDF no funciona |
| FB-002 | major | AC-01 | resolved | #43 | Error en creacion |
| FB-003 | minor | — | open | #44 | Typo en label |

**Bloqueantes**: FB-001 (critical)
**Criterios invalidados**: AC-03
```

Si no hay feedback → "No hay feedback registrado para '{feature}'."

---

## Checklist

- [ ] Feature detectado (de argumento o rama)
- [ ] PRD localizado (si existe) y AC-XX listados
- [ ] Feedback recopilado (description, expected, actual, severity)
- [ ] FB-NNN ID asignado secuencialmente
- [ ] JSON guardado en .quality/evidence/{feature}/feedback/
- [ ] Screenshot copiado (si proporcionado)
- [ ] GitHub issue creado con labels correctos
- [ ] JSON actualizado con github_issue URL
- [ ] acceptance-report.json actualizado si invalidates_acceptance
- [ ] feedback-summary.json creado/actualizado
- [ ] Output final con impacto en acceptance reportado

---

## Referencia rapida

| Accion | Comando |
|--------|---------|
| Nuevo feedback | `/feedback [feature]` |
| Con metadata | `/feedback feature --ac AC-03 --severity critical` |
| Resolver | `/feedback resolve FB-001` |
| Listar | `/feedback list [feature]` |
| Severity que bloquea | critical, major |
| Severity que no bloquea | minor |
| Evidencia local | `.quality/evidence/{feature}/feedback/` |
| Resumen agregado | `.quality/evidence/{feature}/feedback-summary.json` |
