# PRD: [US-VSCODE-ZERO-PYTHON] Onboarding cero-Python de la extensión VSCode

> Origen: FreeForm board `ff-ed0c02f4565a` | US-VSCODE-ZERO-PYTHON
> Discovery: doc/discovery/zero_python_onboarding/icp_jtbd.md (READY_FOR_PRD)
> Tipo: PRD Técnico (refactor)
> Generado: 2026-05-28

## Resumen Ejecutivo

La extensión VSCode de SpecBox impone Python 3.12+ como requisito de onboarding
por dos razones que resultaron innecesarias: (1) el MCP server ofrece un modo
"Local" que corre el server Python en la máquina del cliente, junto al modo
"Remote" que apunta al MCP gratuito hospedado por el owner; (2) Engram (memoria
persistente, obligatoria) se cablea vía `pip/pipx install engram`, cuando en
realidad Engram es un binario nativo single-file sin dependencias, instalable
vía `brew install gentleman-programming/tap/engram`.

Un beta-tester (ICP-2) se quedó bloqueado en el onboarding por la dependencia de
Python. Dado que el MCP remoto se sirve gratis, el modo local no aporta valor
suficiente para justificar la fricción. Este refactor elimina Python por
completo del path del cliente: mata el modo local del todo (sin fallback
oculto), migra Engram a brew, y purga toda referencia a Python de los artefactos
visibles (health check, walkthrough, README EN+ES, package.json, status bar,
onboarding, status tree).

JTBDs servidos (de discovery): JR-FZPY.1..4, JE-FZPY.1..2. NSM impactada:
interrupciones por feature (esta feature elimina una decisión local-vs-remoto en
el onboarding) y reduce tickets de soporte por entorno.

## Alcance

### Incluye
- Eliminar la QuickPick "Local vs Remote" en `configureSpecbox` → configurar
  Remote directamente, sin preguntar.
- Eliminar todo el branch de modo Local (detección Python, uv, python3/python,
  `findEnginePath` si queda huérfano, construcción de serverConfig local).
- Migrar la instalación de Engram de `pip/pipx install engram` a
  `brew install gentleman-programming/tap/engram`, con fallback manual
  documentado para SO sin brew. Engram sigue **Required**.
- Eliminar el chequeo de Python del Health Check y de todos los reportes/vistas
  derivados (statusbar, onboard, status-tree).
- Eliminar `REQUIRED_PYTHON_VERSION` de constants y sus usos.
- Purgar toda mención a Python de: walkthrough (`step-prerequisites.md`,
  `step-mcp.md` si aplica), `package.json` (descripciones de walkthrough), y
  README EN + ES (requisitos, diagrama de pasos, tabla de instalación de Engram,
  troubleshooting).
- Tests nuevos que afirmen: configureSpecbox produce config Remote sin preguntar;
  health check no incluye Python; Engram se cablea vía brew.

### No incluye
- Soporte air-gapped / fallback local oculto (decisión de producto explícita:
  matar el modo local del todo).
- Cambios en el MCP server Python en sí (sigue existiendo y corriendo en el VPS
  del owner; esto es solo sobre cómo la extensión del cliente se conecta).
- Cambios en el backend de tracking FreeForm. La decisión canónica "FreeForm
  requiere MCP local (stdio)" en app_spec.md es sobre el MCP de tracking, NO
  sobre el MCP del engine que configura la extensión — fuera de alcance.
- Bump de versión del engine (lo gestiona /release tras el merge).

---

## Estado Actual vs Propuesto

### ACTUAL (configureSpecbox, vscode-extension/src/mcp.ts):
```
QuickPick { Remote (recommended) | Local (requires Python 3.12+) }
  ├── remote → npx mcp-remote https://mcp-specbox-engine.jpsdeveloper.com/mcp
  └── local  → findEnginePath + commandExists(python3|python) + uv? 
               → serverConfig { uv run | python -m server.server }
configureEngram → pip install engram / pipx install engram
Health check → checkPython() reportado como Required
Walkthrough / README → "Python 3.12+ | Yes | Powers the MCP server"
```

### PROPUESTO:
```
configureSpecbox → (sin QuickPick) addMcpServer('SpecBox-MCP', remote) directo
configureEngram → brew install gentleman-programming/tap/engram (+ fallback manual)
Health check → sin checkPython; Python no aparece en ningún reporte
Walkthrough / README → sin fila Python; Engram instalado vía brew
```

---

## Cambios de UI (extensión)

| Artefacto actual | Cambio | Resultado |
|------------------|--------|-----------|
| QuickPick local/remote | Eliminar | Configuración Remote silenciosa |
| Health Check table (fila Python) | Eliminar fila | Tabla sin Python |
| Status bar ("Python 3.12+ missing") | Eliminar issue | No reporta Python |
| Onboarding report (línea Python) | Eliminar línea | No menciona Python |
| Status tree (item Python) | Eliminar item | Árbol sin Python |
| Walkthrough step-prerequisites | Quitar fila Python; Engram=brew | Cero Python |

---

## A Eliminar
- [ ] Branch `mode.value === 'local'` completo en `configureSpecbox` (mcp.ts).
- [ ] La QuickPick local/remote (mcp.ts).
- [ ] `checkPython()` y campo `python` en `HealthReport` (health.ts).
- [ ] `REQUIRED_PYTHON_VERSION` (constants.ts) y todos sus imports/usos.
- [ ] Referencias a Python en statusbar.ts, onboard.ts, views/status-tree.ts.
- [ ] `pip install engram` / `pipx install engram` (mcp.ts).
- [ ] Fila "Python 3.12+" en media/walkthrough/step-prerequisites.md.
- [ ] Menciones a Python en package.json (descripciones walkthrough/comandos).
- [ ] Menciones a Python en README.md y README.es.md (requisitos, pasos,
      tabla instalación Engram, troubleshooting).

## A Mantener
- Modo Remote como única vía (npx mcp-remote → MCP gratuito del owner).
- Engram como dependencia **Required** (solo cambia su instalador).
- `findEnginePath` SOLO si lo usa otro código fuera del branch local; si queda
  huérfano, eliminarlo también.

---

## Plan de Implementación (alto nivel)

### Fase 1: Núcleo de la extensión (mcp.ts)
- Eliminar QuickPick + branch local; configurar Remote directo.
- Migrar Engram a brew con fallback manual.

### Fase 2: Health / vistas
- Quitar checkPython y todas las referencias derivadas (health, statusbar,
  onboard, status-tree, constants).

### Fase 3: Documentación y copys
- Walkthrough, package.json, README EN + ES.

### Fase 4: Tests + verificación
- Tests nuevos; `npm test` y `npm run compile` verdes; grep final
  confirmando cero menciones a "python" user-facing en vscode-extension/.

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Usuario sin `brew` (Linux/Windows) no puede instalar Engram | Media | Medio | Fallback manual documentado (git clone + build, o release binary) en el copy del warning y README |
| `findEnginePath` u otro símbolo queda huérfano tras borrar el branch local | Media | Bajo | grep de usos antes de borrar; eliminar si huérfano |
| Cliente air-gapped pierde el modo local | Baja | Bajo | Decisión de producto aceptada explícitamente; documentar en CHANGELOG |
| Strings l10n (package.nls*.json) con Python no detectadas | Baja | Bajo | grep exhaustivo en l10n durante Fase 3 |
| Eliminar `python` de constants rompe imports en tests existentes | Media | Bajo | actualizar imports; suite verde como gate |

---

## Stack Técnico

- **Lenguaje**: TypeScript (vscode-extension), Markdown (docs), JSON (package.json, l10n).
- **Tests**: `node:test` zero-deps en `vscode-extension/tests/`.
- **Build**: `npm run compile` (tsc) + `npm test` en `vscode-extension/`.
- **No toca**: el server Python ni el backend de tracking.

## Archivos Principales
```
vscode-extension/
  src/mcp.ts              ← QuickPick + branch local + Engram installer
  src/health.ts          ← checkPython + HealthReport.python
  src/constants.ts       ← REQUIRED_PYTHON_VERSION
  src/statusbar.ts       ← issue "Python 3.12+ missing"
  src/onboard.ts         ← línea Python en report
  src/views/status-tree.ts ← item Python
  media/walkthrough/step-prerequisites.md
  media/walkthrough/step-mcp.md (revisar)
  package.json           ← descripciones walkthrough/comandos
  README.md / README.es.md
  tests/mcp.test.mjs (nuevo o ampliado)
```

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

#### UC-001 — Configuración MCP solo-Remote
- [ ] **AC-01**: Al ejecutar el comando "Configure MCP Servers", la extensión
      escribe la config del servidor `SpecBox-MCP` apuntando a
      `npx mcp-remote https://mcp-specbox-engine.jpsdeveloper.com/mcp` SIN
      mostrar ninguna QuickPick de elección local-vs-remoto.
- [ ] **AC-02**: El código fuente de `vscode-extension/src/mcp.ts` no contiene
      ninguna rama que construya un serverConfig basado en `uv run` o
      `python -m server.server`, ni ninguna llamada a `commandExists('python3')`
      / `commandExists('python')`.

#### UC-002 — Engram vía brew, sin Python
- [ ] **AC-03**: `configureEngram` ofrece instalar Engram con
      `brew install gentleman-programming/tap/engram` y NO con `pip install` ni
      `pipx install`.
- [ ] **AC-04**: Cuando `brew` no está disponible, la extensión muestra un
      mensaje accionable con la vía de instalación manual de Engram (no pip),
      sin abortar el resto del onboarding.

#### UC-003 — Health check sin Python
- [ ] **AC-05**: El reporte del Health Check no incluye ninguna fila ni cadena
      referida a "Python"; `HealthReport` no expone el campo `python` y
      `REQUIRED_PYTHON_VERSION` no existe en `constants.ts`.
- [ ] **AC-06**: La status bar, el reporte de onboarding y el status tree no
      muestran ningún issue ni item relativo a Python.

#### UC-004 — Documentación cero-Python
- [ ] **AC-07**: `media/walkthrough/step-prerequisites.md` no contiene la fila
      "Python 3.12+" y lista Engram con instalación vía brew.
- [ ] **AC-08**: `README.md` y `README.es.md` no contienen ninguna mención a
      Python como requisito (ni en la tabla de prerequisitos, ni en el diagrama
      de pasos, ni en la tabla de instalación de Engram, ni en el
      troubleshooting); la instalación de Engram figura como brew.
- [ ] **AC-09**: `package.json` no contiene ninguna descripción de walkthrough
      o comando que mencione "Python".

#### UC-005 — Verificación global cero-Python
- [ ] **AC-10**: Un grep case-insensitive de `python` sobre los artefactos
      user-facing de `vscode-extension/` (src, media/walkthrough, package.json,
      README*, l10n) devuelve cero resultados user-facing (se admiten solo
      comentarios técnicos internos si los hubiera, justificados).
- [ ] **AC-11**: `npm run compile` y `npm test` pasan en `vscode-extension/`
      sin errores tras todos los cambios.

### Técnicos (no validados por AG-09)
- [ ] La extensión compila sin errores TypeScript.
- [ ] Suite de tests `node:test` verde (incluyendo los nuevos casos).

---
**Prioridad**: high
**Complejidad**: Media
*Generado: 2026-05-28*
