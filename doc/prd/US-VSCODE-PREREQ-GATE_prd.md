# PRD: [US-VSCODE-PREREQ-GATE] Gate de prerequisitos de la extensión VSCode

> Origen: FreeForm board `ff-ed0c02f4565a` | US-VSCODE-PREREQ-GATE
> Discovery: doc/discovery/prerequisites_gate/icp_jtbd.md (READY_FOR_PRD)
> Tipo: PRD Feature
> Generado: 2026-05-28

## Descripción

Añadir un gate de prerequisitos a la extensión VSCode que avise de forma clara
y accionable cuando falten requisitos críticos, dejando explícito que **SpecBox
puede no funcionar correctamente** sin ellos. Hoy la extensión tiene un
HealthChecker que detecta lo que falta, pero no lo comunica proactivamente: solo
avisa en startup si el *engine* no está instalado, no si faltan prerequisitos
(Claude Code, Engram, Node) o si los servidores MCP no están configurados.

## Objetivo

Que el usuario sepa, sin ambigüedad y en el momento del arranque, si su entorno
está listo — y si no lo está, qué le falta y cómo resolverlo.

## Usuario Objetivo

ICP-2 (dev solo con Claude Code que adopta SpecBox) como primario; ICP-1
(owner-operator) como secundario. JTBDs: JR-FPG.1..4, JE-FPG.1..2.

## Alcance

### Incluye
- Una función pura de evaluación de prerequisitos que, dado el `HealthResult`,
  decide el veredicto del gate: `ready` | `degraded` (falta algo crítico). Los
  requisitos críticos son: **Claude Code, Engram, Node, y MCP configurado**
  (SpecBox + Engram). GGA es opcional y NO dispara el gate.
- Un gate no bloqueante en `runStartupTasks`: si el veredicto es `degraded`,
  muestra un `showWarningMessage` accionable que (a) lista qué falta, (b) deja
  claro que SpecBox puede no funcionar correctamente, (c) ofrece acciones
  (Run Setup Wizard / Configure MCP / Open guide). Silencio total si `ready`.
- Un comando dedicado `specbox.checkPrerequisites` ("SpecBox: Check
  Prerequisites") que evalúa a demanda y muestra el mismo gate (o un mensaje de
  "todo OK" cuando se invoca manualmente).
- Entrada del comando en `package.json` (`contributes.commands`).
- Documentar el gate en el walkthrough y README (EN + ES).
- Tests `node:test` de la función pura de evaluación.

### No incluye
- Severidad bloqueante (decisión de producto: warning no bloqueante).
- Re-evaluar/instalar automáticamente los requisitos (el gate avisa y enlaza
  acciones existentes; no instala por su cuenta más allá de los comandos ya
  disponibles).
- Cambios en el HealthChecker más allá de exponer lo necesario para el veredicto
  (ya expone node/claudeCode/engram/mcpSpecbox/mcpEngram).
- Reintroducir Python (la US previa lo eliminó; este gate NO lo menciona).
- Bump de versión (lo hace /release tras merge).

---

## User Stories y Use Cases

### US-01: US-VSCODE-PREREQ-GATE — Gate de prerequisitos

> Como dev que adopta SpecBox (ICP-2), quiero que la extensión me avise
> claramente si me faltan requisitos críticos, para no creer que todo funciona
> cuando en realidad SpecBox puede fallar.

#### UC-001: Evaluación de prerequisitos (función pura)
- **Actor**: Dev solo con Claude Code (ICP-2)
- **Contexto**: Nueva función pura `evaluatePrerequisites(health)` en un módulo
  testeable sin `vscode`, que clasifica el entorno y enumera lo que falta.

**Acceptance Criteria:**
- [ ] **AC-01**: Existe una función pura `evaluatePrerequisites(health)` que
      devuelve `{ verdict: 'ready' | 'degraded', missing: string[] }` donde
      `missing` lista los requisitos críticos ausentes (Claude Code, Engram,
      Node, MCP SpecBox, MCP Engram). El veredicto es `degraded` si y solo si
      `missing.length > 0`.
- [ ] **AC-02**: GGA ausente NO produce `degraded` (es opcional). Con todos los
      críticos presentes y GGA ausente, el veredicto es `ready`.

#### UC-002: Gate no bloqueante en el arranque
- **Actor**: Dev solo con Claude Code (ICP-2)
- **Contexto**: En `runStartupTasks`, tras el health check, dispara el gate.

**Acceptance Criteria:**
- [ ] **AC-03**: Cuando `evaluatePrerequisites` devuelve `degraded` al arrancar,
      la extensión muestra un `showWarningMessage` (no modal, no bloqueante) que
      enumera los requisitos ausentes e indica explícitamente que SpecBox puede
      no funcionar correctamente sin ellos.
- [ ] **AC-04**: Cuando el veredicto es `ready` al arrancar, NO se muestra
      ningún aviso de prerequisitos (silencio).
- [ ] **AC-05**: El gate de arranque nunca lanza una excepción no controlada
      (guard try/catch propio); un fallo del gate no rompe la activación ni el
      resto de runStartupTasks.

#### UC-003: Comando "Check Prerequisites" a demanda
- **Actor**: Owner-operator (ICP-1)
- **Contexto**: Comando dedicado para re-evaluar tras instalar algo.

**Acceptance Criteria:**
- [ ] **AC-06**: Existe el comando `specbox.checkPrerequisites` registrado y
      declarado en `package.json` con título "SpecBox: Check Prerequisites".
- [ ] **AC-07**: Al invocarlo con todo OK, muestra un mensaje informativo de
      entorno listo; al invocarlo con requisitos ausentes, muestra el mismo
      gate accionable que el de arranque.

#### UC-004: Documentación del gate
- **Actor**: Owner-operator (ICP-1)
- **Contexto**: Walkthrough + README reflejan el nuevo gate/comando.

**Acceptance Criteria:**
- [ ] **AC-08**: El walkthrough (step-prerequisites.md) menciona que la
      extensión avisa automáticamente si falta un requisito y cómo re-comprobar.
- [ ] **AC-09**: README.md y README.es.md documentan el comando "SpecBox: Check
      Prerequisites" en la tabla de comandos.
- [ ] **AC-10**: `npm run compile` y `npm test` pasan sin errores tras todos los
      cambios (incluye los tests nuevos de evaluatePrerequisites).

---

## Interacciones UI

### Acciones del usuario
| Acción | UC | Frecuencia | Criticidad | Confirmación |
|--------|----|-----------|-----------|--------------|
| Ver aviso de prerequisitos al arrancar | UC-002 | Solo si falta algo | Media | No (no bloqueante) |
| Ejecutar "Check Prerequisites" | UC-003 | Ocasional | Baja | No |
| Pulsar acción del aviso (wizard / configure MCP / guía) | UC-002/003 | Ocasional | Media | No |

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| No bloqueo | El gate nunca bloquea la activación ni el flujo | Revisión de código + AC-05 |
| Arranque rápido | El gate corre dentro de runStartupTasks (fire-and-forget), no en activate() | Coherente con v6.6.2 |
| Testabilidad | La lógica de veredicto es pura (sin vscode) | Tests node:test |
| Honestidad | Silencio cuando todo OK; aviso claro cuando falta | AC-04 / AC-03 |

---

## Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|--------|-------|---------|------------|
| Falsos positivos de MCP no configurado (detección por aliases) | Media | Medio | Reutilizar checkMcpConfigured existente, ya cubre aliases y permissions |
| El warning se vuelve ruido si el usuario lo ignora siempre | Baja | Bajo | No bloqueante + silencio cuando ready; opción futura "no avisar" fuera de v1 |
| Doble aviso (engine-not-installed + prereq gate) en startup | Media | Bajo | Ordenar: si engine no instalado, ese flujo ya guía; el prereq gate complementa sin duplicar wording |

---

## Stack Técnico

- TypeScript (extensión). Tests `node:test` zero-deps con stub de `vscode`.
- Reutiliza `HealthChecker` (ya expone node/claudeCode/engram/mcpSpecbox/mcpEngram).

## Archivos Principales
```
vscode-extension/
  src/prerequisites.ts        # NUEVO — evaluatePrerequisites (pura) + helpers de UI
  src/extension.ts            # MODIFICAR — comando + gate en runStartupTasks
  package.json                # MODIFICAR — contributes.commands
  media/walkthrough/step-prerequisites.md  # MODIFICAR
  README.md / README.es.md    # MODIFICAR — tabla comandos
  tests/prerequisites.test.mjs # NUEVO
```

## Dependencias
- US-VSCODE-ZERO-PYTHON (rama base): el HealthResult ya no tiene `python`; el
  gate evalúa el set post-cero-Python.

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] AC-01..AC-09 (ver UCs arriba)

### Técnicos (no validados por AG-09)
- [ ] AC-10: compile + tests verdes
- [ ] Sin reintroducir referencias a Python

---
**Prioridad**: high
**Complejidad**: Baja-Media
*Generado: 2026-05-28*
