# Plan: [US-VSCODE-PREREQ-GATE] Gate de prerequisitos de la extensión VSCode

> Generado: 2026-05-28
> Origen: FreeForm US-VSCODE-PREREQ-GATE (board ff-ed0c02f4565a)
> UCs backend: UC-706 (func pura), UC-707 (gate startup), UC-708 (comando), UC-709 (docs)
> PRD: doc/prd/US-VSCODE-PREREQ-GATE_prd.md
> Discovery: doc/discovery/prerequisites_gate/icp_jtbd.md
> Rama: feature/US-VSCODE-PREREQ-GATE (parte de la rama cero-Python)
> Tipo: feature (add) — sin pantallas UI, sin VEG, sin Stitch

## Resumen

Gate no bloqueante que avisa cuando faltan requisitos críticos (Claude Code,
Engram, Node, MCP SpecBox/Engram), dejando claro que SpecBox puede no funcionar
correctamente. Dispara automáticamente en el arranque + comando a demanda.

## Análisis UI
No aplica (sin pantallas). `stitch_designs: N/A`.

## Hallazgos de exploración (estado real)

- `HealthResult` (health.ts) ya expone `node`, `claudeCode`, `engram`,
  `mcpSpecbox.configured`, `mcpEngram.configured`, `gga`. Suficiente para el
  veredicto sin tocar el checker.
- `runStartupTasks` (extension.ts) ya corre fire-and-forget tras activate(); el
  gate encaja ahí, tras el health check, con su propio try/catch (patrón v6.6.2).
- Patrón de tests: stub de `vscode` vía `Module._resolveFilename` + require de
  `out/*.js` (ver tests/mcp.test.mjs, skill-card.test.mjs).
- Comandos se declaran en package.json `contributes.commands` y se registran en
  extension.ts con `registerCommand`.

## Fases (mapeo a UCs)

### Fase 1 — UC-706: función pura `evaluatePrerequisites`  [src/prerequisites.ts NUEVO]
- [ ] Crear `src/prerequisites.ts` SIN import de vscode. Tipos:
      `PrereqInput` (subset de HealthResult: node.ok, claudeCode.ok, engram.ok,
      mcpSpecbox.configured, mcpEngram.configured) y
      `PrereqVerdict = { verdict: 'ready'|'degraded', missing: PrereqItem[] }`.
- [ ] `evaluatePrerequisites(input)`: construye `missing` con los críticos
      ausentes (label legible: "Claude Code", "Engram", "Node.js", "MCP SpecBox
      server", "MCP Engram server"); GGA NO entra. `verdict='degraded'` sii
      `missing.length>0`.
- [ ] Helper `buildPrereqWarning(missing)` puro → string del mensaje accionable
      ("SpecBox may not work correctly. Missing: X, Y. ...").
- [ ] Cubre AC-01, AC-02.

### Fase 2 — UC-707: gate en el arranque  [src/extension.ts, src/prerequisites.ts]
- [ ] En `prerequisites.ts`, helper de UI `showPrereqGate(health, { onStartup })`
      (este sí usa vscode): evalúa, si `degraded` muestra `showWarningMessage`
      no modal con el texto de `buildPrereqWarning` + acciones (Run Setup Wizard
      → specbox.onboard, Configure MCP → specbox.configureMcp, Open guide →
      openExternal README). Si `ready` y `onStartup`, no muestra nada.
- [ ] En `runStartupTasks`, tras el bloque de health, llamar
      `await showPrereqGate(result, { onStartup: true })` dentro de su propio
      try/catch (no romper el resto).
- [ ] Cubre AC-03, AC-04, AC-05.

### Fase 3 — UC-708: comando a demanda  [src/extension.ts, package.json]
- [ ] package.json `contributes.commands`: añadir
      `{ command: "specbox.checkPrerequisites", title: "SpecBox: Check Prerequisites" }`.
- [ ] extension.ts: registrar el comando → corre `health.run()` y
      `showPrereqGate(result, { onStartup: false })`; con `ready` muestra
      `showInformationMessage` "All prerequisites are installed. SpecBox is ready."
- [ ] Cubre AC-06, AC-07.

### Fase 4 — UC-709: docs  [walkthrough, README EN+ES]
- [ ] step-prerequisites.md: añadir nota de que la extensión avisa
      automáticamente si falta un requisito + cómo re-comprobar (comando).
- [ ] README.md y README.es.md: añadir fila del comando "SpecBox: Check
      Prerequisites" en la tabla de comandos.
- [ ] Cubre AC-08, AC-09.

### Fase 5 — verificación  [tests]
- [ ] tests/prerequisites.test.mjs: casos de la función pura — todos presentes →
      ready; cada crítico ausente → degraded + missing contiene el label; GGA
      ausente con resto OK → ready; buildPrereqWarning incluye los labels y la
      frase "may not work correctly".
- [ ] `npm run compile` + `npm test` verdes. Cubre AC-10.

## Alternativas y Tradeoffs

| Decisión | Elegido | Descartado | Razón |
|----------|---------|-----------|-------|
| Severidad | Warning no bloqueante | Modal bloqueante | Filosofía SpecBox "avisar, no impedir" + arranque rápido v6.6.2 |
| Lógica de veredicto | Función pura separada | Inline en extension.ts | Testabilidad sin vscode |
| Disparo | Startup + comando | Solo comando | Cobertura proactiva (el usuario no tiene que acordarse) |
| MCP en el set crítico | Sí | No | Decisión de producto: "Todos incl. MCP configurado" |

## Archivos a Crear/Modificar
```
vscode-extension/
  src/prerequisites.ts          # NUEVO — evaluatePrerequisites + buildPrereqWarning + showPrereqGate
  src/extension.ts              # MODIFICAR — comando + gate en runStartupTasks
  package.json                  # MODIFICAR — contributes.commands
  media/walkthrough/step-prerequisites.md  # MODIFICAR
  README.md / README.es.md      # MODIFICAR — tabla comandos
  tests/prerequisites.test.mjs  # NUEVO
```

## Referencias
- PRD: doc/prd/US-VSCODE-PREREQ-GATE_prd.md
- Depende del estado post cero-Python (HealthResult sin `python`).
