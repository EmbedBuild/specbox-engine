# E2E Evidence Report — Template

> Spec del HTML Evidence Report que AG-09a genera para TODOS los stacks.
> Self-contained: CSS inline, evidencia embebida base64, sin dependencias externas.
> Un humano abre este HTML en cualquier browser y valida la calidad del UC.

---

## Estructura visual

```
┌──────────────────────────────────────────────────┐
│  E2E Evidence Report                             │
│  Feature: {feature} | UC: {uc_id} | US: {us_id} │
│  Source: {stack} ({source})                       │
│  Generated: {timestamp}                          │
├──────────────────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐            │
│  │ XX%  │ │  N   │ │  N   │ │  N   │            │
│  │ Pass │ │Passed│ │Failed│ │Total │            │
│  │ Rate │ │      │ │      │ │      │            │
│  └──────┘ └──────┘ └──────┘ └──────┘            │
├──────────────────────────────────────────────────┤
│  AC-01: Texto del escenario          [PASS]      │
│  ┌────────────────────────────────────────┐      │
│  │  Screenshot (PNG base64)              │      │
│  │  — o —                                │      │
│  │  Request/Response log (JSON formateado)│      │
│  └────────────────────────────────────────┘      │
│  Steps: Dado ✓ → Cuando ✓ → Entonces ✓ (1.2s)  │
├──────────────────────────────────────────────────┤
│  AC-02: Texto del escenario          [FAIL]      │
│  ┌────────────────────────────────────────┐      │
│  │  Screenshot del estado al fallar      │      │
│  │  — o —                                │      │
│  │  Response con error                   │      │
│  └────────────────────────────────────────┘      │
│  Error: Expected 'X' but got 'Y'                │
│  Steps: Dado ✓ → Cuando ✓ → Entonces ✗ (0.9s)  │
├──────────────────────────────────────────────────┤
│  SpecBox Engine v5.18.0 — AG-09a                 │
│  Stack: {stack} | Source: {source}               │
└──────────────────────────────────────────────────┘
```

---

## Input

El report se genera desde `results.json` (ver `doc/specs/results-json-spec.md`).

---

## Evidencia por stack

| Stack | evidence_type | Qué se embebe en el HTML |
|-------|--------------|--------------------------|
| Flutter Web | `screenshot` | `<img src="data:image/png;base64,{b64}" />` |
| Flutter Mobile | `screenshot` | `<img src="data:image/png;base64,{b64}" />` |
| React | `screenshot` | `<img src="data:image/png;base64,{b64}" />` |
| Python | `response-log` | `<pre>{JSON formateado con syntax highlight}</pre>` |

Cuando `evidence` es null (no se capturó): mostrar placeholder gris con texto "No evidence captured".

---

## Colores

| Pass Rate | Color |
|-----------|-------|
| >= 80% | `#22c55e` (green) |
| 50-79% | `#eab308` (yellow) |
| < 50% | `#ef4444` (red) |

| Status | Badge |
|--------|-------|
| PASS | `background: #22c55e; color: white` |
| FAIL | `background: #ef4444; color: white` |

| Step status | Color |
|-------------|-------|
| PASS | `#22c55e` |
| FAIL | `#ef4444` |

---

## HTML Template

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>E2E Evidence — ${ucId}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; background: #fafafa; color: #1f2937; }
    .header { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    .header h1 { margin: 0 0 8px 0; font-size: 24px; }
    .header .meta { color: #6b7280; font-size: 14px; }
    .summary { display: flex; gap: 16px; margin: 16px 0; }
    .summary .card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; flex: 1; text-align: center; }
    .summary .card .number { font-size: 28px; font-weight: bold; }
    .summary .card .label { font-size: 12px; color: #6b7280; text-transform: uppercase; }
    .pass-rate { font-size: 48px; font-weight: bold; }
    .ac-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: white; }
    .ac-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    .ac-header h3 { margin: 0; font-size: 16px; }
    .badge-pass { background: #22c55e; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; }
    .badge-fail { background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 13px; }
    .evidence-img { max-width: 100%; border: 1px solid #e5e7eb; border-radius: 8px; }
    .evidence-json { background: #f9fafb; border: 1px solid #e5e7eb; padding: 12px; border-radius: 8px; font-size: 13px; font-family: 'SF Mono', Menlo, monospace; overflow-x: auto; white-space: pre-wrap; }
    .evidence-none { color: #999; font-style: italic; }
    .steps { margin-top: 8px; font-size: 13px; color: #6b7280; }
    .step-pass { color: #22c55e; }
    .step-fail { color: #ef4444; }
    .duration { margin-top: 4px; font-size: 12px; color: #9ca3af; }
    .error-block { background: #fef2f2; border: 1px solid #fecaca; padding: 8px; border-radius: 4px; font-size: 12px; overflow-x: auto; margin-top: 8px; font-family: 'SF Mono', Menlo, monospace; }
    .footer { text-align: center; color: #9ca3af; font-size: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; }
  </style>
</head>
<body>
  <!-- HEADER -->
  <div class="header">
    <h1>E2E Evidence Report</h1>
    <div class="meta">
      Feature: <strong>${feature}</strong> | UC: <strong>${ucId}</strong> | US: <strong>${usId}</strong><br>
      Source: <strong>${stack}</strong> (${source})<br>
      Generated: ${timestamp}
    </div>
  </div>

  <!-- SUMMARY CARDS -->
  <div class="summary">
    <div class="card">
      <div class="pass-rate" style="color: ${passRateColor}">${passRate}%</div>
      <div class="label">Pass Rate</div>
    </div>
    <div class="card">
      <div class="number" style="color:#22c55e">${totalPass}</div>
      <div class="label">Passed</div>
    </div>
    <div class="card">
      <div class="number" style="color:#ef4444">${totalFail}</div>
      <div class="label">Failed</div>
    </div>
    <div class="card">
      <div class="number">${testsTotal}</div>
      <div class="label">Total</div>
    </div>
  </div>

  <h2 style="font-size:18px;margin:24px 0 12px">Acceptance Criteria Evidence</h2>

  <!-- AC CARDS (repeat per result) -->
  <div class="ac-card">
    <div class="ac-header">
      <h3>${acId}: ${scenario}</h3>
      <span class="badge-${status}">${STATUS}</span>
    </div>

    <!-- EVIDENCE: screenshot -->
    <img class="evidence-img" src="data:image/png;base64,${b64}" />

    <!-- EVIDENCE: response-log (Python) -->
    <div class="evidence-json">${formattedJson}</div>

    <!-- EVIDENCE: none -->
    <p class="evidence-none">No evidence captured</p>

    <!-- STEPS -->
    <div class="steps">
      <span class="step-${stepStatus}">${keyword}</span> ${text} → ...
    </div>
    <div class="duration">Duration: ${durationMs}ms</div>

    <!-- ERROR (only if FAIL) -->
    <pre class="error-block">${errorMessage}</pre>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    SpecBox Engine v5.18.0 — AG-09a Acceptance Tester<br>
    Stack: ${stack} | Source: ${source}
  </div>
</body>
</html>
```

---

## Generadores que producen este HTML

| Stack | Generador | Input |
|-------|-----------|-------|
| Flutter Web | Inline en step definitions (Playwright `afterAll`) | Playwright HTML + cucumber JSON |
| Flutter Mobile | `.quality/scripts/patrol-evidence-generator.js` | JUnit XML + screenshots |
| React | Inline en step definitions (Playwright `afterAll`) | Playwright HTML + cucumber JSON |
| Python | `.quality/scripts/api-evidence-generator.js` | cucumber JSON + response logs |

Todos producen el mismo HTML. AG-09b no distingue el origen.

---

*SpecBox Engine v5.18.0 — E2E Evidence Report Template*
