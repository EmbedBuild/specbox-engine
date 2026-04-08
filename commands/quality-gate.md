# /quality-gate (Global)

Sistema de quality gates adaptativo con baseline auto-descubierto, plan progresivo y evidencia auditable.

## Uso

```
/quality-gate [mode]
```

**Modos:**
- `audit` (default) — Escanea proyecto, descubre estado actual, genera baseline
- `check` — Valida cambios contra baseline. Retorna GO/NO-GO
- `plan` — Genera plan progresivo de mejora desde el baseline
- `fix` — Ejecuta el siguiente paso del plan de mejora
- `report` — Genera report detallado en `.quality/reports/`

---

## Paso 0: Detectar Proyecto y Stack

### 0.1 Detectar stack

| Archivo | Stack | Lint command | Test command | Coverage command |
|---------|-------|-------------|-------------|-----------------|
| `pubspec.yaml` | Flutter | `dart analyze` | `flutter test` | `flutter test --coverage` |
| `package.json` con react/next | React | `npx eslint . && npx tsc --noEmit` | `npx jest --passWithNoTests` | `npx jest --coverage` |
| `pyproject.toml` con fastapi/django | Python | `ruff check . && mypy .` | `pytest` | `pytest --cov --cov-report=json` |
| `.clasp.json` | Apps Script | `npm run lint` | `npm run test` | `npm run test -- --coverage` |

### 0.2 Detectar baseline existente

```bash
# Buscar baseline existente
cat .quality/baseline.json 2>/dev/null
```

**Si existe** → Cargar y usar como referencia
**Si no existe** → Generar (modo audit)

---

## Modo: `audit` (default)

> Escanea el proyecto completo, descubre el estado real y fija el baseline.

### 1. Ejecutar lint

```bash
# Flutter
dart analyze 2>&1 | tee /tmp/quality-lint.log
# Contar: errors, warnings, infos

# React
npx eslint . 2>&1 | tee /tmp/quality-lint.log
npx tsc --noEmit 2>&1 | tee -a /tmp/quality-lint.log

# Python
ruff check . 2>&1 | tee /tmp/quality-lint.log
mypy . 2>&1 | tee -a /tmp/quality-lint.log
```

**Lint es SIEMPRE zero-tolerance: 0 errors, 0 warnings, 0 infos.**

Si lint no está limpio:
```
🛑 LINT NO ESTÁ LIMPIO

Errors: N | Warnings: N | Infos: N

ACCIÓN REQUERIDA: Limpiar lint ANTES de generar baseline.
Ejecutar:
  [comando fix del stack]

El baseline NO se genera hasta que lint esté en 0/0/0.
```

**BLOQUEANTE**: No continuar hasta que lint sea 0/0/0.

### 2. Ejecutar tests

```bash
# Flutter
flutter test 2>&1 | tee /tmp/quality-tests.log
# Extraer: total, passing, failing, skipped

# React
npx jest --passWithNoTests --json 2>/tmp/quality-tests.json
# Extraer de JSON: numTotalTests, numPassedTests, numFailedTests

# Python
pytest --tb=short -q 2>&1 | tee /tmp/quality-tests.log
# Extraer: passed, failed, errors, skipped
```

**Si hay tests fallando**: Reportar pero NO bloquear el audit. Registrar en baseline como `failing: N`.

### 3. Medir coverage

```bash
# Flutter
flutter test --coverage
lcov --summary coverage/lcov.info 2>&1

# React
npx jest --coverage --coverageReporters=json-summary
cat coverage/coverage-summary.json

# Python
pytest --cov --cov-report=json
cat coverage.json
```

Extraer porcentaje global de coverage.

### 4. Detectar dead code

```bash
# Flutter
dart analyze --unused 2>/dev/null || grep -c "unused" /tmp/quality-lint.log

# React
npx ts-prune 2>/dev/null | wc -l

# Python
vulture . 2>/dev/null | wc -l
```

Si la herramienta no está disponible, registrar como `"deadCode": {"count": -1, "tool": "not-available"}`.

### 5. Detectar dependencias outdated

```bash
# Flutter
dart pub outdated 2>&1 | grep -c "resolvable"

# React
npm outdated 2>&1 | tail -n +2 | wc -l

# Python
pip list --outdated 2>&1 | tail -n +3 | wc -l
```

### 6. Verificar arquitectura

Por stack, verificar violaciones de capas:

#### Flutter
```bash
# Buscar imports de data/ en domain/ (violación)
grep -r "import.*data/" lib/domain/ 2>/dev/null | wc -l

# Buscar imports de presentation/ en domain/ (violación)
grep -r "import.*presentation/" lib/domain/ 2>/dev/null | wc -l

# Buscar imports de SupabaseClient directos en repositories (violación del patrón DataSource)
grep -r "SupabaseClient" lib/data/repositories/ 2>/dev/null | wc -l
```

#### React
```bash
# Buscar imports directos de stores en Server Components (violación)
grep -r "use.*Store" app/ --include="*.tsx" -l 2>/dev/null | \
  xargs grep -L "'use client'" 2>/dev/null | wc -l
```

#### Python
```bash
# Buscar imports de router en service (violación)
grep -r "from.*router import" app/*/service.py 2>/dev/null | wc -l
```

### 7. Generar baseline

Crear `.quality/baseline.json`:

```json
{
  "$schema": "quality-baseline-v1",
  "project": "[nombre del directorio]",
  "stack": "[stack detectado]",
  "generatedAt": "[ISO timestamp]",
  "engineVersion": "[version del engine]",
  
  "lint": {
    "errors": 0,
    "warnings": 0,
    "infos": 0,
    "policy": "zero-tolerance",
    "command": "[lint command del stack]"
  },
  
  "coverage": {
    "current": "[porcentaje detectado]",
    "baseline": "[porcentaje detectado]",
    "target": 85,
    "policy": "ratchet",
    "command": "[coverage command del stack]"
  },
  
  "tests": {
    "total": "[total]",
    "passing": "[passing]",
    "failing": "[failing]",
    "skipped": "[skipped]",
    "policy": "no-regression",
    "command": "[test command del stack]"
  },
  
  "architecture": {
    "layerViolations": "[count]",
    "policy": "ratchet"
  },
  
  "deadCode": {
    "count": "[count]",
    "policy": "ratchet"
  },
  
  "deps": {
    "outdated": "[count]",
    "vulnerable": 0,
    "policy": "info"
  }
}
```

Crear directorio `.quality/` si no existe.

### 8. Mostrar resultado

```
════════════════════════════════════════════════════════════
  QUALITY GATE AUDIT
  Project: [nombre]
  Stack: [stack]
  Date: [fecha]
════════════════════════════════════════════════════════════

📊 BASELINE GENERADO

  Lint:          0E / 0W / 0I  ✅ (zero-tolerance)
  Coverage:      [X]%          → baseline fijado: [X]%
  Tests:         [N] total ([N] passing, [N] failing)
  Architecture:  [N] violations
  Dead code:     [N] unused refs
  Dependencies:  [N] outdated

  Baseline guardado en: .quality/baseline.json

════════════════════════════════════════════════════════════
  POLÍTICAS ACTIVAS
════════════════════════════════════════════════════════════

  Lint:          🔒 ZERO-TOLERANCE (0/0/0 siempre, bloqueante)
  Coverage:      📈 RATCHET (nunca bajar de [X]%, subir progresivamente)
  Tests:         🛡️ NO-REGRESSION (nunca menos tests passing)
  Architecture:  📈 RATCHET (nunca más violaciones)
  Dead code:     📈 RATCHET (nunca más refs sin usar)
  Dependencies:  ℹ️  INFO (reportar, no bloquear)

════════════════════════════════════════════════════════════

Siguiente paso:
  /quality-gate plan    → Generar plan de mejora progresiva
  /quality-gate check   → Validar cambios contra baseline
```

---

## Modo: `check`

> Valida el estado actual contra el baseline. Retorna GO o NO-GO.
> Diseñado para ejecutarse entre fases de /implement, pre-commit, o CI.

### 1. Cargar baseline

```bash
cat .quality/baseline.json
```

**Si no existe** → Error: "No hay baseline. Ejecuta `/quality-gate audit` primero."

### 2. Ejecutar checks

Para cada métrica en el baseline, ejecutar el comando y comparar:

| Métrica | Condición GO | Condición NO-GO |
|---------|-------------|-----------------|
| Lint | 0/0/0 | Cualquier error/warning/info |
| Coverage | ≥ baseline.coverage.baseline | < baseline.coverage.baseline |
| Tests passing | ≥ baseline.tests.passing | < baseline.tests.passing |
| Tests failing | = 0 | > 0 |
| Architecture violations | ≤ baseline.architecture.layerViolations | > baseline |
| Dead code | ≤ baseline.deadCode.count | > baseline |

### 3. Generar resultado

**Si todos los checks pasan:**

```
✅ QUALITY GATE: GO

  Lint:          0/0/0 ✅
  Coverage:      74.1% ✅ (baseline: 72.3%, +1.8%)
  Tests:         183 passing ✅ (baseline: 148, +35)
  Architecture:  0 violations ✅
  Dead code:     10 refs ✅ (baseline: 12, -2)
```

**Si algún check falla:**

```
🛑 QUALITY GATE: NO-GO

  Lint:          0E / 2W / 0I  🛑 BLOQUEANTE — zero-tolerance
  Coverage:      71.8% 🛑 (baseline: 72.3%, -0.5%)
  Tests:         183 passing ✅ (baseline: 148, +35)
  Architecture:  0 violations ✅
  Dead code:     10 refs ✅

ACCIONES REQUERIDAS:
  1. [Lint] Resolver 2 warnings:
     - lib/features/staff/bloc/staff_bloc.dart:42 — unused import
     - lib/features/staff/widgets/staff_card.dart:18 — prefer_const_constructors
  2. [Coverage] Añadir tests para cubrir +0.5%:
     - lib/features/staff/bloc/staff_bloc.dart — 67% (necesita ≥72.3%)
```

### 4. Guardar evidencia (opcional, si se pasa `--evidence {feature}`)

```bash
# Guardar en .quality/evidence/{feature}/
mkdir -p .quality/evidence/{feature}
```

Guardar:
- `{phase}-gate.json` con métricas
- `lint.log` con output completo
- `test-results.json` con resultados

---

## Modo: `plan`

> Genera un plan progresivo para mejorar desde el baseline actual hasta el target.

### 1. Cargar baseline

Leer `.quality/baseline.json`. Si no existe → ejecutar audit primero.

### 2. Calcular sprints

```
Gap = target - current
Sprints = ceil(gap / increment)

Donde increment depende del gap:
  gap > 30%  → increment = 3% por sprint (mucho que mejorar, ir despacio)
  gap 15-30% → increment = 4% por sprint
  gap 5-15%  → increment = 3% por sprint
  gap < 5%   → increment = 2% por sprint (más fino cerca del target)
```

### 3. Generar plan

Crear `.quality/plan.md`:

```markdown
# Quality Improvement Plan

> Proyecto: [nombre]
> Baseline: [coverage actual]%
> Target: 85%
> Sprints estimados: [N]
> Generado: [fecha]

## Resumen

| Sprint | Coverage target | Acciones |
|--------|----------------|----------|
| 1 | [X]% | Dead code cleanup, tests para archivos >100 LOC sin coverage |
| 2 | [X]% | Tests para BLoCs/Stores sin coverage |
| 3 | [X]% | Tests para repositories |
| 4 | [X]% | Tests para widgets/components críticos |
| 5 | [X]% | Edge cases y error handling |

## Sprint 1: [Coverage actual]% → [Target 1]%

### Prioridades
1. Eliminar dead code ([N] refs — reducción directa de denominador)
2. Archivos sin coverage con >100 LOC:
   - `lib/features/X/bloc/x_bloc.dart` (0%, 120 LOC)
   - `lib/features/Y/service/y_service.dart` (0%, 95 LOC)
3. Actualizar [N] dependencias outdated

### Comandos
```
/quality-gate fix
```

## Sprint 2: [Target 1]% → [Target 2]%
...
```

### 4. Actualizar baseline con plan

Añadir sección `plan` al `baseline.json` con los sprints generados.

---

## Modo: `fix`

> Ejecuta el siguiente paso del plan de mejora.

### 1. Cargar plan

Leer `.quality/plan.md` y `.quality/baseline.json`.
Determinar sprint actual (el primero no completado).

### 2. Ejecutar acciones del sprint

Para cada acción del sprint actual:

| Acción | Cómo ejecutar |
|--------|--------------|
| Dead code cleanup | Eliminar imports no usados, funciones no referenciadas |
| Tests para archivo X | Generar tests siguiendo patrones de AG-04 |
| Deps update | Ejecutar `dart pub upgrade` / `npm update` / `pip install -U` |
| Fix architecture violations | Mover imports, reestructurar según capas |

### 3. Verificar mejora

Después de cada acción:
```bash
# Re-ejecutar checks
/quality-gate check
```

### 4. Actualizar baseline si mejora

Si el coverage subió:
```json
{
  "coverage": {
    "current": 75.2,
    "baseline": 75.2,  // ← RATCHET: sube con el progreso
    "target": 85
  },
  "plan": {
    "currentSprint": 1  // ← avanza al siguiente
  }
}
```

### 5. Commit del fix

```bash
git add .
git commit -m "quality: sprint N — [descripción de mejoras]"
```

---

## Modo: `report`

> Genera un report completo legible por humanos.

### 1. Ejecutar audit completo

Mismos pasos que modo `audit`, pero sin modificar baseline.

### 2. Comparar con baseline

Si existe baseline, calcular deltas para cada métrica.

### 3. Generar report

Crear `.quality/reports/{fecha}_audit.md`:

```markdown
# Quality Report

> Proyecto: [nombre]
> Fecha: [fecha]
> Stack: [stack]
> Engine: v[version]

## Resumen Ejecutivo

| Métrica | Valor | Baseline | Delta | Estado |
|---------|-------|----------|-------|--------|
| Lint | 0/0/0 | 0/0/0 | = | ✅ |
| Coverage | 74.1% | 72.3% | +1.8% | ✅ ↑ |
| Tests | 183 | 148 | +35 | ✅ ↑ |
| Architecture | 0 | 0 | = | ✅ |
| Dead code | 10 | 12 | -2 | ✅ ↓ |
| Deps outdated | 2 | 2 | = | ℹ️ |

## Health Score: [X]/100

### Cálculo
- Lint clean: +20 (0/0/0)
- Coverage ≥ baseline: +20
- Coverage ≥ 85%: +10 (o proporcional)
- Tests no-regression: +15
- Zero failing tests: +10
- Architecture clean: +10
- Dead code ≤ baseline: +5
- Deps up to date: +5
- Plan progress: +5

## Detalle por Métrica

### Lint
[output completo]

### Coverage
[top 10 archivos con menor coverage]

### Tests
[resumen de suites]

### Archivos sin Coverage (candidatos para /quality-gate fix)
| Archivo | LOC | Coverage | Prioridad |
|---------|-----|----------|-----------|
| ... | ... | ... | ... |
```

---

## Integración con /implement

> CRÍTICO: `/implement` DEBE ejecutar quality gates entre cada fase.

Cuando `/implement` ejecuta una feature, inserta gates así:

```
[Pre-flight]
  → /quality-gate check --evidence {feature}
  → Guardar como .quality/evidence/{feature}/pre-gate.json

[Fase N completada]
  → Ejecutar lint del stack
  → Si lint ≠ 0/0/0 → PARAR. Fix automático. Re-check.
  → Ejecutar compilación
  → Si falla → PARAR. Reportar error.
  → /quality-gate check --evidence {feature}
  → Guardar como .quality/evidence/{feature}/phase-N-gate.json
  → Si NO-GO en lint o compile → BLOQUEANTE (parar /implement)
  → Si NO-GO en coverage → WARNING (continuar, reportar al final)

[Post QA (AG-04)]
  → /quality-gate check --evidence {feature}
  → Guardar como .quality/evidence/{feature}/final-gate.json

[Post Quality Audit (AG-08)]
  → Generar .quality/evidence/{feature}/report.md
  → Incluir report en body de la PR
```

---

## Integración con CI (GitHub Actions)

Sugerir al usuario crear `.github/workflows/quality-gate.yml`:

```yaml
name: Quality Gate
on: [pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup [stack]
        # setup del stack
      - name: Load baseline
        run: cat .quality/baseline.json
      - name: Lint
        run: [lint command]
      - name: Tests
        run: [test command]
      - name: Coverage check
        run: |
          BASELINE=$(jq '.coverage.baseline' .quality/baseline.json)
          CURRENT=$(# extraer coverage actual)
          if (( $(echo "$CURRENT < $BASELINE" | bc -l) )); then
            echo "🛑 Coverage dropped: $CURRENT% < $BASELINE%"
            exit 1
          fi
```

---

## Políticas de gates

### zero-tolerance (lint)

```
Resultado debe ser EXACTAMENTE 0 errors, 0 warnings, 0 infos.
NO hay excepción. NO hay "lint-ignore" sin justificación en PR.
BLOQUEANTE en todos los contextos.
```

### ratchet (coverage, architecture, dead code)

```
El valor actual se convierte en el nuevo mínimo.
Nunca puede empeorar. Solo puede mantenerse o mejorar.
Si mejora, el baseline se actualiza automáticamente.

Ejemplo:
  Sprint 0: baseline = 45%
  Feature A: coverage = 47% → nuevo baseline = 47%
  Feature B: coverage = 46% → 🛑 NO-GO (baseline es 47%)
  Feature B fix: coverage = 48% → nuevo baseline = 48%
```

### no-regression (tests)

```
El número de tests passing nunca puede bajar.
Tests failing siempre debe ser 0.
Tests skipped: permitidos pero reportados como warning.
```

### strict (para proyectos nuevos)

```
Igual que ratchet pero el baseline empieza en el target (85%).
No hay margen para bajar. Solo aplica a proyectos que empiezan de cero.
```

### info (deps)

```
Se reporta pero no bloquea.
Solo bloquea si hay vulnerabilidades conocidas (CVE).
```

---

## Checklist

- [ ] Stack detectado correctamente
- [ ] Lint verificado (0/0/0)
- [ ] Tests ejecutados
- [ ] Coverage medida
- [ ] Dead code contado
- [ ] Deps verificadas
- [ ] Arquitectura verificada
- [ ] `.quality/baseline.json` generado o actualizado
- [ ] Report guardado si modo report
- [ ] Evidence guardada si modo check con --evidence

---

## Referencia rápida

| Quiero... | Comando |
|-----------|---------|
| Ver estado del proyecto | `/quality-gate` |
| Verificar antes de commit | `/quality-gate check` |
| Plan para mejorar coverage | `/quality-gate plan` |
| Ejecutar mejoras | `/quality-gate fix` |
| Report completo | `/quality-gate report` |

---

*SpecBox Engine v5.19.0 — Quality Gate System*
