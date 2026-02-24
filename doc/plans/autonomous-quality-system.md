# Plan: Sistema de Programación Autónoma con Calidad Garantizada

> Fecha: 2026-02-24
> Rama: feature/autonomous-quality-system
> Estado: 🟡 En diseño

---

## Diagnóstico del Estado Actual

### Lo que funciona bien ✅

1. **Flujo end-to-end definido**: `/prd` → `/plan` → `/implement` — el pipeline existe
2. **Multi-stack**: Flutter, React, Python, Apps Script — bien cubiertos
3. **Stitch integrado**: Design-to-code con MCP — pipeline UI existe
4. **Agentes especializados**: 7 agentes con roles claros (AG-01 a AG-07)
5. **GLOBAL_RULES.md**: Reglas por stack, testing 85%, lint obligatorio
6. **install.sh con symlinks**: Distribución limpia de commands

### Lo que falta para autonomía total 🔴

| Gap | Severidad | Descripción |
|-----|-----------|-------------|
| **No hay quality gates automáticos** | CRÍTICA | El pipeline confía en que Claude "recuerde" hacer lint/test entre fases. No hay enforcement real |
| **No hay evidencia persistente** | CRÍTICA | No se genera ningún artefacto auditable: no hay logs, no hay reports, no hay métricas guardadas |
| **Coverage solo se comprueba al final** | ALTA | Si la fase 3 genera código sin tests, no se detecta hasta fase 5. Demasiado tarde |
| **No hay baseline por proyecto** | ALTA | El 85% es fijo para todos. Un proyecto legacy con 30% no puede alcanzar 85% de golpe |
| **No hay `/quality-gate` command** | ALTA | El sistema puede evaluar agentes (`/optimize-agents`) pero NO puede evaluar código |
| **No hay retry inteligente** | MEDIA | Si un test falla, el implement reintenta 3 veces genéricamente. No hay análisis del fallo |
| **No hay post-mortem** | MEDIA | Si una feature se implementa mal, no queda registro de qué falló ni por qué |
| **El orquestador no valida entre fases** | ALTA | orchestrator.md dice "validar entre fases" pero no especifica QUÉ validar ni CÓMO |
| **No hay mecanismo de "stop the line"** | ALTA | Si lint falla o coverage baja, el flujo debería parar. Hoy depende de la voluntad del agente |
| **No hay diff de quality pre/post** | MEDIA | Imposible saber si una feature MEJORÓ o EMPEORÓ la salud del proyecto |

### Gap crítico: El agente "confía en sí mismo"

Hoy el flujo es:
```
AG-01 genera código → AG-04 testea → PR

¿Quién valida que AG-01 no generó basura? AG-04.
¿Quién valida que AG-04 no generó tests vacíos? Nadie.
```

**Falta un agente INDEPENDIENTE que valide la calidad sin ser el mismo que generó el código ni los tests.** Es como si el albañil y el inspector de obra fueran la misma persona.

---

## Arquitectura Propuesta

### Principio: "Trust but verify" → "Verify, then trust"

```
                    ┌─────────────────────────────┐
                    │     /quality-gate audit      │
                    │   (descubre baseline actual)  │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │    .quality/baseline.json     │
                    │  (estado actual del proyecto)  │
                    └──────────────┬──────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        ▼                          ▼                          ▼
  /implement                /quality-gate check        /quality-gate fix
  (entre cada fase)         (pre-commit / CI)          (mejora progresiva)
        │                          │
        ▼                          ▼
  .quality/reports/          GO ✅ / NO-GO 🛑
  {fecha}_{feature}.md       (bloquea merge si falla)
```

### Nuevo agente: AG-08 Quality Auditor

**No es AG-04.** AG-04 genera tests. AG-08 **audita que todo sea real**:

- ¿Los tests realmente prueban algo? (no son `expect(true).toBe(true)`)
- ¿El coverage reportado es real? (no hay archivos excluidos tramposamente)
- ¿El lint está limpio? (0/0/0 — no negociable)
- ¿Se respeta la arquitectura? (imports cruzados, capas violadas)
- ¿Hay código muerto nuevo?
- ¿Las dependencias son las correctas?

---

## Componentes a Implementar

### 1. `/quality-gate` command (NUEVO)

**Archivo**: `commands/quality-gate.md`

**Modos:**
| Modo | Qué hace | Modifica archivos |
|------|----------|:-----------------:|
| `audit` | Escanea proyecto, genera baseline + report | Sí (`.quality/`) |
| `check` | Valida contra baseline. GO/NO-GO | No |
| `plan` | Genera plan progresivo de mejora | Sí (`.quality/plan.md`) |
| `fix` | Ejecuta siguiente paso del plan | Sí (código) |
| `report` | Genera report completo en `.quality/reports/` | Sí (report) |

### 2. `.quality/` directorio (NUEVO)

```
.quality/
├── baseline.json              # Estado actual (auto-generado)
├── plan.md                    # Plan progresivo de mejora
├── config.json                # Overrides del proyecto (opcional)
├── reports/                   # Reports históricos
│   ├── 2026-02-24_audit.md
│   └── 2026-02-24_staff-management.md
└── evidence/                  # Evidencias por feature
    └── {feature}/
        ├── lint.log
        ├── coverage.json
        ├── test-results.json
        └── architecture-check.md
```

### 3. AG-08 Quality Auditor (NUEVO)

**Archivo**: `agents/quality-auditor.md`

Se ejecuta:
- **Entre cada fase de `/implement`** → Gate intermedio
- **Al final de `/implement`** → Gate final
- **En `/quality-gate check`** → Gate bajo demanda
- **En PRs** → Gate de merge

### 4. Modificaciones a commands existentes

#### `/implement` — Añadir gates entre fases

```
ANTES (actual):
  Fase 1 → Fase 2 → Fase 3 → QA → PR

DESPUÉS (propuesto):
  Fase 1 → GATE → Fase 2 → GATE → Fase 3 → GATE → QA → GATE FINAL → PR
              │              │              │              │
              ▼              ▼              ▼              ▼
         .quality/      .quality/      .quality/      .quality/
         evidence/      evidence/      evidence/      evidence/
```

Cada GATE ejecuta:
1. Lint (0/0/0 — BLOQUEANTE)
2. Compilación (BLOQUEANTE)
3. Tests existentes pasan (BLOQUEANTE)
4. Coverage no baja del baseline (WARNING en legacy, BLOQUEANTE en nuevo)
5. Arquitectura respetada (WARNING)

#### `/plan` — Incluir quality expectations

Cada plan generado incluirá:
```markdown
## Quality Expectations

| Métrica | Pre-feature | Post-feature (mínimo) |
|---------|------------|----------------------|
| Lint | 0/0/0 | 0/0/0 |
| Coverage | 72% | 72% (no bajar) |
| Tests | 148 | 148 + nuevos |
| Dead code | 12 refs | ≤ 12 refs |
```

### 5. `baseline.json` schema

```json
{
  "$schema": "quality-baseline-v1",
  "project": "tempo_zenon",
  "stack": "flutter",
  "generatedAt": "2026-02-24T21:00:00Z",
  "engineVersion": "2.4.0",
  
  "lint": {
    "errors": 0,
    "warnings": 0,
    "infos": 0,
    "policy": "zero-tolerance",
    "command": "dart analyze"
  },
  
  "coverage": {
    "current": 72.3,
    "baseline": 72.3,
    "target": 85,
    "policy": "ratchet",
    "ratchetDirection": "up",
    "command": "flutter test --coverage"
  },
  
  "tests": {
    "total": 148,
    "passing": 148,
    "failing": 0,
    "skipped": 0,
    "policy": "no-regression",
    "command": "flutter test"
  },
  
  "architecture": {
    "layerViolations": 0,
    "circularDeps": 0,
    "policy": "ratchet"
  },
  
  "deadCode": {
    "unusedRefs": 12,
    "policy": "ratchet"
  },
  
  "deps": {
    "outdated": 2,
    "vulnerable": 0,
    "policy": "info"
  },
  
  "plan": {
    "sprints": [
      {"id": 1, "coverageTarget": 75, "actions": ["dead code cleanup"]},
      {"id": 2, "coverageTarget": 78, "actions": ["deps update"]},
      {"id": 3, "coverageTarget": 80, "actions": []},
      {"id": 4, "coverageTarget": 83, "actions": []},
      {"id": 5, "coverageTarget": 85, "actions": []}
    ],
    "currentSprint": 0
  }
}
```

### 6. Evidence por feature (AUDITABLE)

Cada feature implementada genera evidencia en `.quality/evidence/{feature}/`:

```
evidence/staff-management/
├── pre-gate.json          # Métricas ANTES de empezar
├── phase-1-gate.json      # Métricas después de fase 1
├── phase-2-gate.json      # Métricas después de fase 2
├── phase-N-gate.json      # ...
├── final-gate.json        # Métricas finales
├── lint.log               # Output completo de lint
├── test-results.json      # Resultados de todos los tests
├── coverage-summary.json  # Coverage por archivo
└── report.md              # Report legible para humanos
```

**`report.md` ejemplo:**
```markdown
# Quality Report: Staff Management

> Generado: 2026-02-24 21:30
> Branch: feature/staff-management
> Engine: v2.4.0

## Resumen

| Métrica | Pre | Post | Delta | Gate |
|---------|-----|------|-------|------|
| Lint | 0/0/0 | 0/0/0 | = | ✅ PASS |
| Coverage | 72.3% | 74.1% | +1.8% | ✅ PASS (baseline: 72.3%) |
| Tests | 148 | 183 | +35 | ✅ PASS |
| Dead code | 12 | 10 | -2 | ✅ PASS |

## Resultado: ✅ GO — PR lista para review

## Detalle por fase

### Fase 1: DB (AG-03)
- Archivos: 2 creados
- Gate: ✅ lint 0/0/0, compilación OK

### Fase 2: Feature (AG-01)  
- Archivos: 12 creados, 3 modificados
- Gate: ✅ lint 0/0/0, compilación OK, coverage 72.3% (mantenido)

### Fase 3: QA (AG-04)
- Tests: 35 nuevos (28 unit, 5 widget, 2 integration)
- Coverage: 72.3% → 74.1%
- Gate: ✅ todos los criterios

### Fase 4: Quality Audit (AG-08)
- Test quality: ✅ No hay tests triviales
- Architecture: ✅ No hay layer violations
- Dead code: ✅ Reducido de 12 a 10
```

---

## Políticas por tipo de proyecto

### Proyecto nuevo (desde cero)

```json
{
  "lint": {"policy": "zero-tolerance"},
  "coverage": {"baseline": 85, "target": 95, "policy": "strict"},
  "tests": {"policy": "no-regression"},
  "architecture": {"policy": "strict"}
}
```

### Proyecto legacy (código existente)

```json
{
  "lint": {"policy": "zero-tolerance"},
  "coverage": {"baseline": "auto-detect", "target": 85, "policy": "ratchet"},
  "tests": {"policy": "no-regression"},
  "architecture": {"policy": "ratchet"}
}
```

**Ratchet = nunca empeora.** Si hoy tienes 45% coverage, el gate es ≥45%. Cada sprint sube según el plan.

### Zero-tolerance (lint)

```
0 errors, 0 warnings, 0 infos. SIEMPRE. SIN EXCEPCIONES.
No importa si es legacy o nuevo. Lint limpio es innegociable.
```

---

## Flujo completo con quality gates

```
/prd "Gestión de staff"
  │
  ▼
/plan PROYECTO-15
  │  (incluye quality expectations pre/post)
  │
  ▼
/implement staff_management
  │
  ├─ [0] /quality-gate audit (si no existe baseline)
  │      → genera .quality/baseline.json
  │      → registra pre-gate.json
  │
  ├─ [1] Fase DB (AG-03)
  │      → GATE: lint ✅ compile ✅
  │      → phase-1-gate.json
  │
  ├─ [2] Fase Feature (AG-01)
  │      → GATE: lint ✅ compile ✅ coverage ≥ baseline ✅
  │      → phase-2-gate.json
  │
  ├─ [3] Fase QA (AG-04)
  │      → GATE: lint ✅ compile ✅ tests pass ✅ coverage ↑
  │      → phase-3-gate.json
  │
  ├─ [4] Quality Audit (AG-08)  ← NUEVO
  │      → Valida calidad real de tests
  │      → Valida arquitectura respetada
  │      → Genera report.md
  │      → final-gate.json
  │
  ├─ [5] DECISIÓN
  │      ├─ ✅ GO → Crear PR con evidence adjunta
  │      └─ 🛑 NO-GO → Report de qué falla + sugerencias
  │
  └─ [6] PR con quality report en el body
```

---

## Orden de implementación

| # | Tarea | Archivos | Prioridad |
|---|-------|----------|-----------|
| 1 | Crear `commands/quality-gate.md` | 1 archivo | 🔴 ALTA |
| 2 | Crear `agents/quality-auditor.md` (AG-08) | 1 archivo | 🔴 ALTA |
| 3 | Modificar `commands/implement.md` — añadir gates entre fases | 1 archivo | 🔴 ALTA |
| 4 | Modificar `commands/plan.md` — incluir quality expectations | 1 archivo | 🟡 MEDIA |
| 5 | Modificar `agents/orchestrator.md` — incluir AG-08 en flujo | 1 archivo | 🟡 MEDIA |
| 6 | Crear `templates/quality-baseline.json.template` | 1 archivo | 🟡 MEDIA |
| 7 | Actualizar `GLOBAL_RULES.md` — políticas de quality gate | 1 archivo | 🟡 MEDIA |
| 8 | Actualizar `README.md` — documentar quality system | 1 archivo | 🟢 BAJA |
| 9 | Actualizar `ENGINE_VERSION.yaml` — v2.4.0 | 1 archivo | 🟢 BAJA |
| 10 | Crear `agent-teams/prompts/quality-auditor.md` | 1 archivo | 🟢 BAJA |

---

## Métricas de éxito

El sistema será exitoso cuando:

1. **Cada PR tiene un quality report** adjunto con métricas pre/post
2. **Ninguna PR baja el coverage** del baseline (ratchet funciona)
3. **Lint siempre 0/0/0** — bloqueante en todos los gates
4. **Los tests son reales** — AG-08 detecta tests triviales
5. **Se puede auditar a posteriori** — `.quality/evidence/` tiene todo el historial
6. **Proyectos legacy mejoran gradualmente** — el plan progresivo sube el baseline sprint a sprint
7. **Zero intervención humana** — de `/implement` a PR con evidencia, sin preguntas

---

*Generado por Gica 🔥 — 2026-02-24*
