---
name: quality-gate
description: >
  Adaptive quality gates with auto-discovered baseline and auditable evidence.
  Use when the user says "check quality", "run gates", "quality report",
  "coverage check", or before creating a PR to validate code quality.
  Policies: zero-tolerance lint, ratchet coverage, no-regression tests.
allowed-tools: Bash(dart *), Bash(flutter *), Bash(npm *), Bash(python *), Bash(ruff *), Bash(eslint *), Read, Grep, Glob
---

# Quality Gate System

Validates code quality with adaptive gates and auditable evidence.

## Usage

```
/quality-gate [mode]
```

**Modes:**
- `check` (default) — Run all gates, report pass/fail
- `baseline` — Generate or update quality baseline
- `report` — Generate detailed report in `.quality/evidence/`

---

## Paso 0: Detectar Stack y Baseline

### 0.1 Detectar stack

| Archivo | Stack | Lint command | Test command |
|---------|-------|-------------|-------------|
| `pubspec.yaml` | Flutter/Dart | `dart analyze` | `flutter test --coverage` |
| `package.json` | Node/React | `npx eslint .` | `npx jest --coverage` |
| `pyproject.toml` | Python | `ruff check .` | `pytest --cov` |
| `.clasp.json` | Apps Script | `npm run lint` | `npm run test` |

### 0.2 Cargar baseline

```bash
BASELINE=".quality/baselines/$(basename $(pwd)).json"
if [ -f "$BASELINE" ]; then
  echo "Baseline found: $BASELINE"
  cat "$BASELINE"
else
  echo "No baseline found. Run /quality-gate baseline to create one."
fi
```

---

## Paso 1: Gate de Lint (BLOQUEANTE)

**Política: Zero-tolerance** — 0 errors, 0 warnings.

### Flutter/Dart
```bash
dart analyze --no-fatal-infos 2>&1
# Exit code != 0 → FAIL
```

### Node/React
```bash
npx eslint . --max-warnings=0 2>&1
# Any warning or error → FAIL
```

### Python
```bash
ruff check . 2>&1
# Any issue → FAIL
```

### Apps Script
```bash
npm run lint 2>&1
```

**Si falla:** Reportar errores exactos con ubicación. NO continuar a otros gates.

---

## Paso 2: Gate de Tests (BLOQUEANTE)

**Política: No-regression** — Todos los tests existentes deben pasar.

### Flutter
```bash
flutter test --coverage 2>&1
```

### Node/React
```bash
npx jest --coverage --passWithNoTests 2>&1
```

### Python
```bash
pytest --cov --cov-report=term-missing 2>&1
```

**Si falla:** Listar tests fallidos con stack trace resumido.

---

## Paso 3: Gate de Coverage (BLOQUEANTE)

**Política: Ratchet** — Coverage nunca puede bajar del baseline.

1. Leer coverage actual del resultado del Paso 2
2. Comparar con baseline:
   - `coverage_actual >= coverage_baseline` → PASS
   - `coverage_actual < coverage_baseline` → FAIL
3. Si no hay baseline → PASS pero reportar "No baseline, coverage: X%"

**Mínimo absoluto:** 85% (configurable)

---

## Paso 4: Generar Evidence

Crear reporte auditable:

```bash
mkdir -p .quality/evidence/$(date -u +%Y-%m-%d)
```

### Formato del reporte

```markdown
# Quality Gate Report

**Project**: [nombre]
**Date**: [timestamp]
**Branch**: [rama actual]
**Commit**: [SHA corto]

## Results

| Gate | Policy | Result | Details |
|------|--------|--------|---------|
| Lint | zero-tolerance | PASS/FAIL | X errors, Y warnings |
| Tests | no-regression | PASS/FAIL | X passing, Y failing |
| Coverage | ratchet (baseline: Z%) | PASS/FAIL | Current: X% |

## Overall: PASS / FAIL

## Files with low coverage
| File | Coverage | Lines uncovered |
|------|----------|----------------|
```

---

## Paso 5: Output

### Si PASS

```
✅ QUALITY GATE: ALL PASSED

| Gate | Result | Details |
|------|--------|---------|
| Lint | ✅ PASS | 0 errors, 0 warnings |
| Tests | ✅ PASS | X passing, 0 failing |
| Coverage | ✅ PASS | X% (baseline: Y%) |

Evidence saved to: .quality/evidence/[date]/report.md
```

### Si FAIL

```
❌ QUALITY GATE: FAILED

| Gate | Result | Details |
|------|--------|---------|
| Lint | ❌ FAIL | X errors, Y warnings |
| Tests | ✅ PASS | ... |
| Coverage | ⚠️ WARN | ... |

Blocking issues:
1. [error details]
2. [error details]

Fix these before committing or creating a PR.
```

---

## Mode: baseline

Cuando se ejecuta con `baseline`:

1. Ejecutar lint, tests y coverage
2. Guardar resultados como nuevo baseline en `.quality/baselines/`
3. Formato JSON:

```json
{
  "project": "nombre",
  "stack": "flutter|node|python",
  "timestamp": "ISO8601",
  "metrics": {
    "lint_errors": 0,
    "lint_warnings": 0,
    "test_coverage_pct": 87,
    "tests_passing": 42,
    "tests_failing": 0
  },
  "policies": {
    "lint": "zero-tolerance",
    "coverage": "ratchet",
    "tests": "no-regression"
  }
}
```

---

## Paso 5.5: E2E Gate (opcional, si existe directorio e2e/ o playwright.config.ts)

### Detección

1. **Detectar config E2E:**
   - Flutter: `ls e2e/playwright.config.ts`
   - React: `ls playwright.config.ts` o `ls e2e/playwright.config.ts`

2. **Si existe config:**
   - Flutter: verificar `build/web/index.html` → si no existe SKIP con warning "Flutter web build required"
   - React: verificar `npm run build` exitoso
   - Ejecutar: `npx playwright test --reporter=json`
   - Parse JSON: total, passing, failing
   - Gate: `failing == 0` y `passing >= baseline.e2e.passing`
   - Evidence: copiar JSON summary a `.quality/evidence/{feature}/e2e-results.json`

3. **Si no existe config:** SKIP silencioso (E2E no configurado)

### Output

```
| E2E | no-regression | ✅ PASS | X passing, 0 failing (3 viewports) |
```

o

```
| E2E | — | ⏭ SKIP | No playwright config found |
```

---

## Checklist

- [ ] Stack detectado correctamente
- [ ] Baseline cargado (si existe)
- [ ] Lint ejecutado con zero-tolerance
- [ ] Tests ejecutados sin regresiones
- [ ] Coverage comparado con baseline
- [ ] E2E ejecutados (si config existe)
- [ ] Evidence generado y guardado
- [ ] Resultado reportado claramente
