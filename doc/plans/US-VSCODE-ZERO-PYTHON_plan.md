# Plan: [US-VSCODE-ZERO-PYTHON] Onboarding cero-Python de la extensión VSCode

> Generado: 2026-05-28
> Origen: FreeForm US-VSCODE-ZERO-PYTHON (board ff-ed0c02f4565a)
> PRD: doc/prd/US-VSCODE-ZERO-PYTHON_prd.md
> Discovery: doc/discovery/zero_python_onboarding/icp_jtbd.md
> Estado: Pendiente
> Tipo: refactor (backend-only de la extensión — sin pantallas UI, sin VEG, sin Stitch)

---

## Resumen

Eliminar Python por completo del path del cliente de la extensión VSCode:
matar el modo Local del MCP (solo Remote), migrar Engram de pip/pipx a brew, y
purgar toda referencia a Python de los artefactos visibles.

## Análisis UI

No aplica. Esta feature no añade ni modifica pantallas de producto. Se saltan
los pasos VEG (2.5b) y Stitch (5.5, 6). `stitch_designs: N/A`.

---

## Hallazgos de exploración (estado real verificado)

- `findEnginePath()` se usa en **dos** sitios: `src/mcp.ts:96` (branch local) y
  `src/health.ts:30` (dentro de checkPython, vía `enginePath` para resolver el
  server). Al borrar el branch local Y checkPython, **ambos usos desaparecen**
  → `findEnginePath` queda huérfano en los dos archivos → eliminar las dos
  definiciones (`mcp.ts:166`, `health.ts:98`).
- l10n (`l10n/bundle.l10n.json`, `bundle.l10n.es.json`) y
  `package.nls*.json` **NO** contienen "python" actualmente → no requieren
  cambios, pero el grep final (AC-10) los cubre.
- Test runner: `npm test` = `tsc -p ./` + `node --test tests/*.test.mjs`.
  Los tests existentes (oauth, skill-*, cloud-api) prueban módulos puros sin
  importar `vscode`. **Riesgo**: `mcp.ts`/`health.ts` importan `vscode`, no
  testeable directo con `node:test`. Mitigación en Fase 4.

---

## Fases de Implementación

> Cada fase mapea 1:1 a un UC. Rama: `feature/US-VSCODE-ZERO-PYTHON` (nunca main).

### Fase 1 — UC-001: Configuración MCP solo-Remote  [mcp.ts]

- [ ] En `configureSpecbox()` (src/mcp.ts ~L78): eliminar el `showQuickPick`
      local/remote y todo el branch `// Local mode` (L94–130).
- [ ] Reemplazar por configuración Remote directa:
      `addMcpServer('SpecBox-MCP', { command: 'npx', args: ['mcp-remote',
      'https://mcp-specbox-engine.jpsdeveloper.com/mcp'] })` + `return true`.
- [ ] Eliminar import/uso de `commandExists` si queda huérfano en mcp.ts tras
      el borrado (sigue usándose para `engram`/`brew` en configureEngram —
      verificar antes de quitar el import).
- [ ] Cubre AC-01, AC-02.

### Fase 2 — UC-002: Engram vía brew  [mcp.ts]

- [ ] En `configureEngram()` (src/mcp.ts ~L46): cambiar las opciones del
      warning de `'Install with pip' / 'Install with pipx'` a
      `'Install with Homebrew'` → `brew install gentleman-programming/tap/engram`.
- [ ] Si `brew` no está disponible (`commandExists('brew')===false`): mostrar
      mensaje accionable con vía manual (release binary / git clone + build de
      github.com/Gentleman-Programming/engram), **sin** pip, sin abortar el
      resto del onboarding (return false controlado).
- [ ] Engram sigue Required (no se degrada).
- [ ] Cubre AC-03, AC-04.

### Fase 3 — UC-003: Health check sin Python  [health.ts, constants.ts, statusbar.ts, onboard.ts, views/status-tree.ts]

- [ ] `health.ts`: eliminar `checkPython()` (L138–148), el campo `python` de
      `HealthReport` (L16), su entrada en `Promise.all` (L33–35) y en el objeto
      retornado (L51), y la fila Python de la tabla markdown (L75).
- [ ] `health.ts`: eliminar `findEnginePath()` (L98) ahora huérfano.
- [ ] `constants.ts`: eliminar `REQUIRED_PYTHON_VERSION` (L27) y su import en
      `health.ts` (L7).
- [ ] `statusbar.ts`: eliminar el push de issue `'Python 3.12+ missing'` (L27).
- [ ] `onboard.ts`: eliminar el campo `python` del tipo (L70) y la línea
      `Python 3.12+: ...` del report (L77).
- [ ] `views/status-tree.ts`: eliminar el `StatusItem` de Python (L60).
- [ ] Cubre AC-05, AC-06.

### Fase 4 — UC-004: Documentación cero-Python  [walkthrough, package.json, README EN+ES]

- [ ] `media/walkthrough/step-prerequisites.md`: eliminar fila "Python 3.12+";
      cambiar la fila Engram para indicar instalación vía brew.
- [ ] `media/walkthrough/step-mcp.md`: revisar; no menciona Python hoy, pero
      confirmar que el copy de "Configure MCP" no implica elección local.
- [ ] `package.json`: L180 (descripción health check "Node.js, Python 3.12+,
      and Claude Code") → quitar Python; L203 revisar wording de configureMcp.
- [ ] `README.md`: L54, L98, L163, L255 → quitar Python de tabla comandos,
      diagrama de pasos, prerequisitos y troubleshooting; L244 (tabla
      instalación Engram pip/pipx → brew).
- [ ] `README.es.md`: L54, L99, L166, L258 análogos; L247 (Engram → brew).
- [ ] Cubre AC-07, AC-08, AC-09.

### Fase 5 — UC-005: Verificación global cero-Python  [tests + gate]

- [ ] Test nuevo `tests/mcp.test.mjs` (o ampliar uno existente):
      - Estrategia para evitar el import de `vscode`: extraer la lógica pura
        testeable a una función exportable sin dependencia de `vscode` (p.ej.
        `buildRemoteServerConfig()` y `buildEngramInstallPlan(hasBrew)` en
        mcp.ts), e importar SOLO esas. Afirmar:
        - `buildRemoteServerConfig()` → `{command:'npx', args:['mcp-remote',
          'https://mcp-specbox-engine.jpsdeveloper.com/mcp']}`.
        - `buildEngramInstallPlan(true)` usa brew; `buildEngramInstallPlan(false)`
          devuelve la vía manual y NO contiene 'pip'.
      - Si extraer funciones puras resulta excesivo para el alcance, alternativa:
        test de "source contract" que lee el texto de `out/mcp.js` (post-tsc) y
        afirma ausencia de `python`/`pip install`/`uv run` y presencia de la URL
        remota. Decidir en implementación según menor complejidad.
- [ ] Ejecutar grep final case-insensitive de `python` sobre src/, media/
      walkthrough/, package.json, README*, l10n/ → cero resultados user-facing
      (AC-10).
- [ ] `npm run compile` && `npm test` verdes (AC-11).

---

## Comandos Finales

```bash
cd vscode-extension
npm run compile
npm test
# grep gate (debe salir vacío de user-facing):
grep -rni "python\|pip install\|pipx\|uv run\|python -m server" src/ media/walkthrough/ package.json README.md README.es.md l10n/
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|------------------------|-------|
| Modo local | Eliminar del todo | Ocultar para power-users | Decisión de producto: máxima reducción de fricción, MCP remoto gratuito |
| Engram installer | brew | mantener pip | Engram es binario nativo sin deps; pip arrastra Python innecesariamente |
| Engram severidad | Required | degradar a Optional | Es fundamental; solo cambia el instalador, no su criticidad |
| Test de mcp.ts | Funciones puras exportables | Mock de vscode | `node:test` zero-deps no resuelve `import vscode`; el resto de la suite ya evita vscode |
| Fallback brew ausente | Vía manual (no pip) | dejar sin Engram | Mantener Required + cero Python obliga a vía manual documentada |

---

## Archivos a Crear/Modificar

```
vscode-extension/
├── src/
│   ├── mcp.ts                  # MODIFICAR — kill QuickPick+local branch; Engram→brew; +funciones puras
│   ├── health.ts               # MODIFICAR — quitar checkPython, campo python, findEnginePath huérfano
│   ├── constants.ts            # MODIFICAR — quitar REQUIRED_PYTHON_VERSION
│   ├── statusbar.ts            # MODIFICAR — quitar issue Python
│   ├── onboard.ts              # MODIFICAR — quitar campo/línea Python
│   └── views/status-tree.ts    # MODIFICAR — quitar StatusItem Python
├── media/walkthrough/
│   ├── step-prerequisites.md   # MODIFICAR — quitar fila Python; Engram=brew
│   └── step-mcp.md             # REVISAR
├── package.json                # MODIFICAR — descripciones walkthrough/comandos sin Python
├── README.md                   # MODIFICAR — requisitos/pasos/Engram/troubleshooting
├── README.es.md                # MODIFICAR — idem ES
└── tests/
    └── mcp.test.mjs            # CREAR — config Remote + Engram brew + no-pip
```

---

## Referencias

- PRD: doc/prd/US-VSCODE-ZERO-PYTHON_prd.md
- Discovery: doc/discovery/zero_python_onboarding/icp_jtbd.md
- Engram tap: gentleman-programming/tap/engram (single binary, zero deps)
- Decisión canónica relacionada (NO afectada): "FreeForm requiere MCP local
  (stdio)" en app_spec.md es sobre el MCP de *tracking*, no el MCP del engine.
