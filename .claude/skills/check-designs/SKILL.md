---
name: check-designs
description: >
  Retroactive compliance check for Stitch designs. Scans all UCs with screens
  and reports which have Stitch HTML designs and which don't.
  Use when the user says "check designs", "design compliance", "verify designs",
  "stitch status", or wants to audit design-to-code traceability.
context: fork
agent: Explore
---

# /check-designs

Escanea todos los UCs con pantallas y reporta el estado de los diseños Stitch.

## Uso

```
/check-designs [board_id | project_id | local]
```

**Origenes:**
- `board_id` → Escanear UCs del board Trello
- `project_id` → Escanear work items de Plane
- `local` → Escanear planes locales en `doc/plans/`
- Sin argumento → Detectar automaticamente (Trello config → Plane config → local)

---

## Paso 1: Recopilar UCs con pantallas

### Si Trello:
1. Obtener board_id de `.claude/settings.local.json`
2. Listar todas las US: `list_us(board_id)`
3. Para cada US: `list_uc(board_id, us_id)`
4. Para cada UC: `get_uc(board_id, uc_id)` → extraer campo `screens`
5. Filtrar solo UCs con screens no vacio

### Si Plane:
1. Obtener project_id de configuracion
2. Listar work items tipo UC (con label "UC")
3. Extraer campo screens de la descripcion
4. Filtrar solo UCs con screens

### Si local:
1. Listar `doc/plans/*_plan.md`
2. Parsear cada plan → extraer secciones con pantallas/screens
3. Extraer feature name de cada plan

---

## Paso 2: Verificar diseños existentes

Para cada UC/feature con pantallas:

```bash
# Verificar existencia de HTMLs
FEATURE=$(echo "${uc_name}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
DESIGN_DIR="doc/design/${FEATURE}"

if [ -d "$DESIGN_DIR" ]; then
  HTML_COUNT=$(find "$DESIGN_DIR" -name "*.html" | wc -l)
else
  HTML_COUNT=0
fi
```

---

## Paso 3: Verificar trazabilidad en codigo

Para cada feature con diseños:

```bash
# Buscar paginas bajo presentation/pages/ para esta feature
PAGES=$(find lib/presentation/features/${FEATURE}/pages/ -name "*.dart" 2>/dev/null)
# O para React:
PAGES=$(find src/pages/${FEATURE}/ -name "*.tsx" 2>/dev/null)

for page in $PAGES; do
  if head -5 "$page" | grep -q "Generated from: doc/design/"; then
    TRACED="YES"
  else
    TRACED="NO"
  fi
done
```

---

## Paso 4: Verificar campo stitch_designs en planes

```bash
for plan in doc/plans/*_plan.md; do
  STITCH_STATUS=$(grep -oP 'stitch_designs:\s*\K\w+' "$plan" 2>/dev/null || echo "NOT_SET")
done
```

---

## Output

```
## Design Compliance Report

**Fecha**: [timestamp]
**Origen**: [Trello board / Plane project / local plans]

### Resumen

| Metrica | Valor |
|---------|-------|
| Total UCs con pantallas | [N] |
| UCs con diseños completos | [N] |
| UCs con diseños parciales | [N] |
| UCs sin diseños | [N] |
| Paginas con trazabilidad | [N]/[total] |
| Paginas sin trazabilidad | [N] |

### Detalle por UC

| UC | Pantallas esperadas | HTMLs encontrados | Trazabilidad | Status |
|----|--------------------|--------------------|--------------|--------|
| UC-001 | login, register | 2/2 | 2/2 | COMPLIANT |
| UC-002 | dashboard | 0/1 | 0/0 | MISSING |
| UC-003 | settings | 1/1 | 0/1 | PARTIAL (no traceability) |
| UC-004 | (sin pantallas) | N/A | N/A | SKIP |

### Status Legend

- **COMPLIANT**: Diseños existen + paginas tienen comentario de trazabilidad
- **MISSING**: No hay diseños HTML para las pantallas del UC
- **PARTIAL**: Diseños existen pero falta trazabilidad en el codigo
- **PENDING**: Plan tiene `stitch_designs: PENDING` — bloqueara /implement
- **SKIP**: UC no tiene pantallas definidas

### Compliance Metrics

| Metrica | Valor |
|---------|-------|
| Compliance Rate | [N]% |
| Enforcement Level | L0 / L1 / L2 |
| Baseline anterior | [N]% (si existe) |
| Variacion | +[N]% / -[N]% / sin cambios |

### Acciones requeridas

{Si hay UCs MISSING o PARTIAL:}
1. Ejecutar `/plan UC-XXX` para generar diseños faltantes
2. O crear diseños manualmente en `doc/design/{feature}/`
3. Paginas sin trazabilidad: anadir `// Generated from: doc/design/{feature}/{screen}.html`

{Si todo COMPLIANT:}
Todos los UCs con pantallas tienen diseños Stitch y trazabilidad completa.

### Retrofit Roadmap (si compliance < 80%)

Prioridad de retrofit basada en frecuencia de modificacion:

| Prioridad | Feature | Motivo | Esfuerzo |
|-----------|---------|--------|----------|
| Alta | {features tocadas en ultimos 5 commits} | Se modifican frecuentemente | /plan feature:X |
| Media | {features con PRs recientes} | Cambios recientes | /plan feature:X |
| Baja | {features estables sin cambios recientes} | Raramente modificadas | Puede esperar |

Para cada feature prioritaria:
1. `git log --oneline -5 -- lib/presentation/features/{feature}/` → frecuencia
2. `/plan feature:{feature}` → genera diseños Stitch retroactivos
3. Anadir traceability comment a paginas existentes
4. Re-medir con `/check-designs` → compliance deberia subir
```

---

## Paso 5: Actualizar Baseline (opcional)

Si el usuario lo solicita o si es la primera vez:

```bash
.quality/scripts/design-baseline.sh . --update
```

Esto actualiza el campo `designCompliance` en el baseline del proyecto.
El ratchet garantiza que el compliance rate nunca baje.

---

## Checklist

- [ ] Origen detectado (Trello/Plane/local)
- [ ] UCs con pantallas recopilados
- [ ] Existencia de HTMLs verificada por feature
- [ ] Trazabilidad en codigo verificada (comentario `// Generated from:`)
- [ ] Campo `stitch_designs` de planes verificado
- [ ] Tabla de compliance generada
- [ ] Compliance rate calculado y nivel determinado (L0/L1/L2)
- [ ] Retrofit roadmap generado (si compliance < 80%)
- [ ] Baseline actualizado (si solicitado)

---

*SDD-JPS Engine v4.2.0 — Design Compliance Check*
