# Plan: [US-VSCODE-AUTOCLONE] Auto-clone del engine público desde la extensión

> Generado: 2026-05-31
> Origen: US-VSCODE-AUTOCLONE (FreeForm board `ff-ed0c02f4565a`, doc/tracking/items.json)
> PRD: doc/prd/US-VSCODE-AUTOCLONE_prd.md
> Discovery: doc/discovery/vscode_autoclone/icp_jtbd.md (READY_FOR_PRD, drift=no_drift)
> Estado: Pendiente
> Stack: TypeScript (extensión VSCode) + Node ESM (tests)
> VEG: DISABLED — sin UI de producto; solo diálogos/notificaciones de la extensión
> Stitch: N/A — feature backend-only de la extensión, sin pantallas

---

## Resumen

La extensión VSCode hoy muere en un `showOpenDialog` cuando no encuentra el repo del
engine en una máquina limpia (apunta a una carpeta que aún no existe). Como el repo es
**público**, la extensión lo clona ella misma automáticamente a un directorio gestionado
(`~/.specbox/specbox-engine`) — notificando, no preguntando — e instala skills/hooks desde
ahí. El updater mantiene ese clon al día con `git pull --ff-only`. Un clon propio del
usuario en otra ruta nunca se toca (protección ICP-1).

---

## Análisis UI (Fase 0)

**No aplica UI de producto.** Las únicas superficies son notificaciones/diálogos nativos de
VSCode ya existentes (`showInformationMessage`, `showErrorMessage`, `showOpenDialog`,
`withProgress`). No hay widgets nuevos, no hay Stitch, no hay VEG.

| Superficie | Tipo VSCode | UC | Nuevo/Existente |
|-----------|-------------|-----|-----------------|
| "Cloning SpecBox Engine…" / "Cloned" | `withProgress` + `showInformationMessage` | UC-110 | Patrón existente (reutiliza `withProgress` de `runFullInstall`) |
| Error de clone + degradación | `showErrorMessage` → `showOpenDialog` | UC-110 | `showOpenDialog` ya existe (paso 4 actual) |
| Warning de `git pull` fallido | `showWarningMessage` no bloqueante | UC-111 | Patrón existente (`updater.ts` Phase warnings) |

---

## Arquitectura: patrón pure/UI + runner inyectable (decisión clave)

El resto de la extensión separa **core puro** (sin `vscode`, sin red — testeable con
`node:test` cargando `out/*.js` y stubeando `vscode`) de una **capa UI fina**. Esta feature
sigue ese patrón y añade un detalle: las operaciones git tienen efectos de red/disco, así
que se inyecta un **`gitRunner`** (función `(args, cwd) => Promise<{ok, stdout, stderr}>`)
con un default real (`cp.execFile('git', …)`) que los tests sustituyen por un stub —
**ningún test toca git ni la red**.

```
src/install.ts
  ── PURO (sin vscode, sin git) ──────────────────────────────
  ENGINE_REPO_URL  (const)                          AC-01
  managedEnginePath(): string                       AC-01  → os.homedir() + /.specbox/specbox-engine
  isManagedPath(p): boolean                          AC-02
  ── EFECTOS (git + fs), runner inyectable ───────────────────
  cloneManagedEngine(deps): Promise<CloneResult>     AC-04/AC-05  (git clone + cleanup parcial)
  ── ORQUESTACIÓN (vscode UI fina) ───────────────────────────
  resolveEnginePath()  ← inserta auto-clone entre paso 3 y paso 4  AC-03

src/updater.ts
  ── EFECTOS ─────────────────────────────────────────────────
  pullManagedEngine(deps): Promise<PullResult>       AC-06/AC-07  (git pull --ff-only)
  ── ORQUESTACIÓN ────────────────────────────────────────────
  runUpdateFlow()  ← nueva Phase 0 (pull si isManagedPath)  AC-06/AC-07
```

`CloneResult`/`PullResult` son objetos planos (`{ ok, path?, error? }`) → la parte testeable
no lanza nunca (NFR "no bloqueo de activación"); la capa UI decide qué notificar.

---

## Fases de Implementación

Cada fase = un UC. Orden por dependencia (UC-109 helpers puros primero; UC-110 los usa;
UC-111 reutiliza `isManagedPath`; UC-112 docs al final). Todas tocan solo `vscode-extension/`.

### Fase 1 — UC-109: Helpers puros + URL canónica (2h)

**Archivo**: `vscode-extension/src/install.ts` (top-level exports, fuera de la clase).

- [ ] `export const ENGINE_REPO_URL = 'https://github.com/EmbedBuild/specbox-engine.git';`
- [ ] `export function managedEnginePath(): string` → `path.join(os.homedir(), '.specbox', 'specbox-engine')`.
- [ ] `export function isManagedPath(p: string): boolean` → comparación exacta normalizada (`path.resolve(p) === managedEnginePath()`). `false` para cualquier otra ruta.
- [ ] Tests `tests/autoclone.test.mjs` (node:test, stub de `vscode`):
  - AC-01: `managedEnginePath()` termina en `/.specbox/specbox-engine`, es absoluto; `ENGINE_REPO_URL` es la URL pública `.git`.
  - AC-02: `isManagedPath(managedEnginePath()) === true`; `isManagedPath('/Users/x/specbox-engine') === false`.

> Nota: exportar como funciones top-level (no métodos de instancia) para que el test las
> cargue directo desde `out/install.js` sin instanciar `InstallManager` (que requiere un
> `ExtensionContext`). Coherente con el patrón de `prerequisites.ts`.

### Fase 2 — UC-110: Auto-clone en resolveEnginePath (3h)

**Archivo**: `vscode-extension/src/install.ts`.

- [ ] **`cloneManagedEngine`** (efectos, runner inyectable) — firma orientativa:
  ```ts
  interface CloneDeps {
    gitRunner?: (args: string[], cwd?: string) => Promise<{ code: number; stderr: string }>;
    existsSync?: (p: string) => boolean;
    mkdirSync?: (p: string, opts?: fs.MakeDirectoryOptions) => void;
    rmSync?: (p: string, opts?: fs.RmOptions) => void;
  }
  interface CloneResult { ok: boolean; path?: string; error?: string; }
  async function cloneManagedEngine(deps?: CloneDeps): Promise<CloneResult>
  ```
  Lógica:
  1. Crear `~/.specbox` si no existe (`mkdirSync recursive`).
  2. `gitRunner(['clone', ENGINE_REPO_URL, managedEnginePath()])`.
  3. Si `code === 0` **y** existe `managedEnginePath()/ENGINE_VERSION.yaml` → `{ ok:true, path: managedEnginePath() }`.
  4. Si falla (código ≠ 0, git ausente → runner rechaza/`ENOENT`, o falta `ENGINE_VERSION.yaml`) → **limpiar dir parcial** (`rmSync(managedEnginePath(), {recursive,force})`) y devolver `{ ok:false, error }`. **No lanza.**
- [ ] **`resolveEnginePath()`** — insertar entre paso 3 (common locations) y paso 4 (showOpenDialog):
  ```
  3. common locations …
  3.5 (NUEVO) si NO existe managedEnginePath()/ENGINE_VERSION.yaml:
        - withProgress "Cloning SpecBox Engine…"
        - r = await cloneManagedEngine()
        - si r.ok → showInformationMessage("Cloned"); update config specbox.enginePath = r.path (Global); return r.path
        - si !r.ok → showErrorMessage(error accionable: "git missing or network down — select the folder manually") → CAER al paso 4
      si SÍ existe managedEnginePath()/ENGINE_VERSION.yaml → return managedEnginePath() (idempotencia, NFR: no re-clona)
  4. showOpenDialog (degradación, sin cambios)
  ```
- [ ] Tests:
  - AC-03: con managed dir ausente + sin engine resuelto (config/workspace/common stubeados a "no existe"), la rama invoca `cloneManagedEngine` ANTES del `showOpenDialog`. Spy: clone llamado, openDialog no (en el camino feliz).
  - AC-04: `gitRunner` stub que "crea" el dir con `ENGINE_VERSION.yaml` (via `existsSync` stub que devuelve true post-clone) → `resolveEnginePath` devuelve managed path, `config.update('specbox.enginePath', managed, Global)` llamado, info notificada, sin confirmación intermedia.
  - AC-05: `gitRunner` stub que falla → `cloneManagedEngine` no lanza, devuelve `{ok:false}`, `rmSync` invocado sobre el managed path (cleanup parcial), `resolveEnginePath` cae al `showOpenDialog`.

> **Testabilidad de `resolveEnginePath`**: hoy es un método de instancia que llama directo a
> `vscode.*` y `fs.*`. Para no reescribir toda la clase, la rama 3.5 delega en
> `cloneManagedEngine(deps)` (testeada de forma aislada) y el test del flujo de decisión
> stubea `vscode.window.*` + las funciones `fs` vía el mismo mecanismo
> `Module._resolveFilename` ya usado en los demás tests. Si extraer el cuerpo de decisión a
> un helper puro `chooseEnginePathStrategy(probe, ui, cloner)` resulta más limpio durante la
> implementación, hacerlo — la decisión final queda para /implement, pero el contrato de los
> AC (clone antes que dialog; cleanup en fallo; idempotencia) es el invariante.

### Fase 3 — UC-111: git pull del clon gestionado en el update flow (2h)

**Archivo**: `vscode-extension/src/updater.ts`.

- [ ] **`pullManagedEngine`** (efectos, runner inyectable):
  ```ts
  async function pullManagedEngine(enginePath: string, deps?): Promise<{ ok: boolean; skipped?: boolean; error?: string }>
  ```
  1. Si `!isManagedPath(enginePath)` → `{ ok:true, skipped:true }` (NO toca clon de usuario — AC-06).
  2. `gitRunner(['pull', '--ff-only'], enginePath)`.
  3. `code === 0` → `{ ok:true }`; si falla → `{ ok:false, error }` (NO lanza — AC-07).
- [ ] **`runUpdateFlow(enginePath)`** — añadir **Phase 0** ANTES de Phase 1 (binary), porque el
      pull debe ocurrir antes de reinstalar skills/hooks desde el engine:
  ```
  Phase 0 (NUEVO): try { const r = await pullManagedEngine(enginePath); if(!r.ok && !r.skipped) showWarningMessage(warning no bloqueante) } catch(e){ console.warn }
  Phase 1 binary … (sin cambios)
  ```
  Mantener el wrap try/catch por fase (patrón fire-and-forget v6.6.2): el pull nunca aborta
  la activación ni el resto del flujo.
- [ ] Tests:
  - AC-06: `enginePath = managedEnginePath()` → `gitRunner` (spy) invocado con `['pull','--ff-only']`. `enginePath = '/Users/x/specbox-engine'` → runner NO invocado, `{skipped:true}`.
  - AC-07: `gitRunner` stub que falla → `pullManagedEngine` resuelve sin throw `{ok:false}`; `runUpdateFlow` no lanza y emite warning (spy en `showWarningMessage`).

### Fase 4 — UC-112: Walkthrough + docs sin "clone first" obligatorio (2h)

**Archivos**: `vscode-extension/media/walkthrough/step-prerequisites.md` (+ `step-install.md` si
aplica), `README.md` (bloques EN + ES).

- [ ] **Walkthrough**: `step-prerequisites.md` ya **no** instruye `git clone` (verificado: lista
      Node/Claude/Engram/GGA, sin paso de clone). Añadir una línea breve: "When the extension
      can't find the engine repo, it clones the public engine for you automatically into a
      managed folder (`~/.specbox/specbox-engine`)." Revisar `step-install.md` por si menciona
      clone manual como prerequisito y matizarlo.
- [ ] **README.md**: los 2 bloques "Quick Start" (ES ~L169, EN ~L524) tienen `git clone <repo-url> ~/specbox-engine` para la **instalación CLI manual del engine** (`./install.sh`) — ese flujo sigue siendo válido y NO se borra. La acción de AC-08 es: en la sección/bloque que describe el **onboarding de la extensión VSCode**, dejar claro que la extensión auto-clona el engine y que `git clone` manual NO es prerequisito de la extensión. Añadir nota EN+ES.
- [ ] Test (grep) `tests/autoclone.test.mjs`:
  - AC-08: el walkthrough de prerequisitos NO contiene una instrucción "clone the repo first" como prerequisito de la extensión, y SÍ menciona el auto-clone gestionado (`~/.specbox/specbox-engine` o "clones the engine for you"). Grep sobre el contenido del `.md`.

---

## Comandos Finales (verificación)

```bash
cd vscode-extension
tsc -p ./                      # AC técnico: compila sin errores → out/
node --test tests/*.test.mjs   # AC técnico: suite verde, incluye autoclone.test.mjs
```

El gate E2E del engine (Playwright/pytest) **no aplica** — esta feature es de la extensión
VSCode y su evidencia es la suite `node:test` (igual que US-VSCODE-PREREQ-GATE, OAUTH, etc.).

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|----------------|------------------------|-------|
| Confirmación previa al clone | Automático + notificación | Prompt "¿Clonar?" | Repo público (sin auth), destino gestionado propio — la fricción no aporta valor (decisión cerrada en PRD) |
| Destino del clone | `~/.specbox/specbox-engine` (oculto, gestionado) | `~/specbox-engine` (común) | No ensucia el home; `isManagedPath` distingue limpio el clon nuestro del del usuario |
| Invocación git | `cp.execFile('git', …)` con runner inyectable | librería git (simple-git) | Cero deps nuevas; coherente con `cp.execFile` ya usado en `updater.ts`; runner inyectable = tests sin red |
| `git pull` strategy | `--ff-only` | `pull` normal / `reset --hard` | `--ff-only` no crea merges ni pisa cambios locales; si diverge falla limpio → warning (AC-07). `reset --hard` lo bloquea `no-bypass-guard` y destruiría ediciones del usuario en el gestionado |
| Fase del pull en updater | Phase 0 (antes del binary) | después de reinstalar | Reinstalar skills/hooks debe leer el código ya actualizado por el pull |
| Cleanup de clone parcial | `rmSync(recursive,force)` del managed dir | dejarlo | Un dir parcial con/sin `ENGINE_VERSION.yaml` rompería futuras detecciones (NFR seguridad de disco) |

---

## Archivos a Crear/Modificar

```
vscode-extension/
├── src/
│   ├── install.ts          # MOD: ENGINE_REPO_URL, managedEnginePath, isManagedPath,
│   │                       #      cloneManagedEngine, rama auto-clone en resolveEnginePath
│   └── updater.ts          # MOD: pullManagedEngine + Phase 0 en runUpdateFlow
├── tests/
│   └── autoclone.test.mjs  # NUEVO: AC-01..AC-08 (helpers + clone + pull + docs grep)
├── media/walkthrough/
│   ├── step-prerequisites.md  # MOD: nota de auto-clone
│   └── step-install.md        # REVISAR: quitar "clone first" si lo menciona
README.md                      # MOD: bloques EN+ES — extensión auto-clona; clone CLI manual intacto
```

---

## Mapeo a Agentes (/implement)

| Fase | UC | Agente sugerido | Notas |
|------|-----|----------------|-------|
| 1 | UC-109 | AG-01 Feature Generator | Helpers puros + tests |
| 2 | UC-110 | AG-01 Feature Generator | Lógica de clone + integración en resolveEnginePath |
| 3 | UC-111 | AG-01 Feature Generator | Pull en updater |
| 4 | UC-112 | AG-01 / docs | Edición de Markdown + grep test |
| todas | — | AG-04 QA | Suite node:test verde + `tsc` limpio |
| cierre | US | AG-09b Acceptance Validator | Verifica AC-01..AC-08 contra evidencia (suite verde) |

> **Auto-merge OFF recomendado** para esta US (coherente con US-VSCODE-DISCOVERABILITY): el
> smoke real del auto-clone en una máquina sin el repo solo lo valida un humano. La suite
> `node:test` cubre el flujo de decisión con stubs, pero el `git clone` real contra GitHub es
> el gate humano final.

---

## Referencias

- PRD: [doc/prd/US-VSCODE-AUTOCLONE_prd.md](doc/prd/US-VSCODE-AUTOCLONE_prd.md)
- Discovery: [doc/discovery/vscode_autoclone/icp_jtbd.md](doc/discovery/vscode_autoclone/icp_jtbd.md)
- Patrón pure/UI de referencia: [vscode-extension/src/prerequisites.ts](vscode-extension/src/prerequisites.ts)
- Fire-and-forget en updater: [vscode-extension/src/updater.ts](vscode-extension/src/updater.ts) (v6.6.2)
- Código a modificar: [vscode-extension/src/install.ts:73-112](vscode-extension/src/install.ts#L73-L112) (resolveEnginePath)
