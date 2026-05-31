# PRD: [US-VSCODE-AUTOCLONE] Auto-clone del engine público desde la extensión

> Origen: FreeForm board (doc/tracking/items.json)
> Discovery: doc/discovery/vscode_autoclone/icp_jtbd.md (READY_FOR_PRD, drift=no_drift)
> Generado: 2026-05-31
> Stack: TypeScript (extensión VSCode) + Node ESM
> VEG: DISABLED (sin UI de producto nueva — solo diálogos/notificaciones de la extensión)

## Resumen

Hoy, cuando la extensión VSCode no encuentra el repo del engine en disco
(`resolveEnginePath()` falla en config / workspace / rutas comunes), su único
fallback es un `showOpenDialog` que pide al usuario **seleccionar la carpeta del
repo**. En una máquina limpia ese repo no existe todavía y el usuario no sabe que
primero debe `git clone` — el onboarding muere en un diálogo que apunta a una
carpeta inexistente.

El repo es **público** (`https://github.com/EmbedBuild/specbox-engine`), así que la
extensión puede cerrar esta brecha clonándolo ella misma, **automáticamente y sin
fricción**, a un directorio gestionado (`~/.specbox/specbox-engine`) — notificando al
usuario, no pidiéndole confirmación — e instalando skills/hooks desde ahí. El updater
existente (UC-666) mantiene ese clon al día con `git pull` automático. Un clon propio
del usuario en otra ruta NO se toca nunca (protección de ICP-1).

**Decisión de producto (cerrada con el usuario)**: el auto-clone es automático (no
pregunta), porque el repo es público (sin auth) y el destino es un directorio
gestionado propio de la extensión (no ensucia el home del usuario ni toca su trabajo).
El único punto interactivo es la **degradación**: si el clone automático falla, se cae
al `showOpenDialog` actual.

## Alcance

### Incluye
- Nuevo paso de auto-clone en `resolveEnginePath()`, ANTES del fallback `showOpenDialog`.
- Clone **automático** (sin confirmación, solo notificación) a `~/.specbox/specbox-engine` (directorio gestionado).
- `git pull` automático del clon gestionado en el flujo de update, solo si el engine resuelto ES el gestionado.
- Protección de clon del usuario: si el engine ya se resuelve por config/workspace/rutas comunes, NO clonar ni tocar.
- Manejo de errores de red/git: si el clone falla, degradar al `showOpenDialog` actual con mensaje claro.
- Walkthrough + README (EN/ES) actualizados: el paso 0 "git clone manual" deja de ser necesario.

### No incluye
- Prompt de confirmación previo al clone (decisión: clone automático + notificación posterior).
- Soporte de repos privados / auth (el repo es público; fuera de alcance).
- Migrar el clon del usuario existente al directorio gestionado (se respeta donde esté).
- Cambiar el modelo de instalación skills/hooks (sigue siendo symlink/copy desde el engine resuelto).

---

## User Story

**ID**: US-VSCODE-AUTOCLONE
**Nombre**: Auto-clone del engine público desde la extensión
**Actor**: Dev que instala la extensión en una máquina sin el repo clonado (ICP-2 / ICP-3)
**Horas estimadas**: 9h

> Como dev que instala la extensión SpecBox en una máquina limpia, quiero que la
> extensión clone el engine público por mí automáticamente cuando no lo encuentra,
> para tener SpecBox operativo en minutos sin saber qué repo clonar ni dónde — y que
> un clon propio mío nunca se vea afectado.

---

## Use Cases

### UC-109: Helper puro de resolución de directorio gestionado + URL canónica
- **Actor**: Sistema (extensión)
- **Horas**: 2h
- **Estado**: user_stories

> Aísla la lógica pura (sin vscode, sin red) para que sea testeable con node:test,
> siguiendo el patrón pure/UI del resto de la extensión (prerequisites.ts, migration.ts).

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fautoclone.2]: Existe una función pura `managedEnginePath()` que devuelve el path absoluto `~/.specbox/specbox-engine` resolviendo `os.homedir()`, y una constante `ENGINE_REPO_URL = "https://github.com/EmbedBuild/specbox-engine.git"`. Test node:test: `managedEnginePath()` termina en `/.specbox/specbox-engine` y es absoluto; `ENGINE_REPO_URL` es la URL pública `.git`.
- [ ] **AC-02** [JR-Fautoclone.4]: Existe una función pura `isManagedPath(p)` que devuelve `true` solo si `p` es exactamente el directorio gestionado, y `false` para cualquier otra ruta (clon del usuario). Test: `isManagedPath(managedEnginePath())===true`; `isManagedPath("/Users/x/specbox-engine")===false`.

### UC-110: Auto-clone con confirmación en resolveEnginePath
- **Actor**: Dev (ICP-2/ICP-3)
- **Horas**: 3h
- **Estado**: user_stories

> Inserta el paso de auto-clone entre la búsqueda en rutas conocidas y el fallback
> showOpenDialog. Automático (sin prompt previo); el openDialog queda solo como degradación.

#### Acceptance Criteria
- [ ] **AC-03** [JR-Fautoclone.1]: Cuando `resolveEnginePath()` no encuentra el engine por config/workspace/rutas comunes Y `~/.specbox/specbox-engine/ENGINE_VERSION.yaml` no existe, la extensión intenta el auto-clone **automáticamente** (sin diálogo de confirmación previo) ANTES de recurrir al `showOpenDialog`. El `showOpenDialog` solo se alcanza si el clone automático falla. Test: con managed dir ausente y sin engine resuelto, la rama de decisión invoca el clone antes que el openDialog (función testeable con stubs de git + UI).
- [ ] **AC-04** [JR-Fautoclone.1]: El auto-clone ejecuta `git clone https://github.com/EmbedBuild/specbox-engine.git ~/.specbox/specbox-engine` (creando `~/.specbox` si no existe), muestra una notificación informativa ("Cloning SpecBox Engine…/Cloned") y, al terminar con éxito, devuelve ese path como enginePath y lo persiste en `specbox.enginePath`. Test: con un `git clone` stub que crea un dir con `ENGINE_VERSION.yaml`, `resolveEnginePath` devuelve el managed path y la config queda seteada — sin paso de confirmación intermedio.
- [ ] **AC-05** [JE-Fautoclone.1]: Si el `git clone` falla (red caída, git ausente), la extensión muestra un error accionable y degrada al `showOpenDialog` actual SIN colgarse ni dejar un directorio a medias (limpia `~/.specbox/specbox-engine` parcial si la clonación abortó). Test: con un clone stub que falla, la función no lanza, reporta error, limpia el dir parcial, y cae al openDialog.

### UC-111: git pull del clon gestionado en el update flow
- **Actor**: Sistema (extensión)
- **Horas**: 2h
- **Estado**: user_stories

> Mantiene el clon gestionado al día sin tocar clones del usuario. Se engancha en el
> flujo de update existente (updater.ts, UC-666) de forma fire-and-forget.

#### Acceptance Criteria
- [ ] **AC-06** [JR-Fautoclone.3]: Cuando el engine resuelto ES el directorio gestionado (`isManagedPath(enginePath)===true`), el update flow ejecuta `git pull --ff-only` sobre él antes de reinstalar skills/hooks. Test: con enginePath = managed, el flujo invoca el pull (spy); con enginePath = ruta de usuario, NO lo invoca.
- [ ] **AC-07** [JR-Fautoclone.4]: Si `git pull` falla (sin red, conflicto), el update continúa con la copia local existente y reporta un warning no bloqueante — nunca aborta la activación (patrón fire-and-forget v6.6.2). Test: con un pull stub que falla, el flujo resuelve sin throw y emite warning.

### UC-112: Walkthrough + docs sin paso de clone manual
- **Actor**: Dev que onboarda (ICP-2/ICP-3)
- **Horas**: 2h
- **Estado**: user_stories

> Cierra el drift entre lo que la doc dice ("clona primero") y lo que la extensión
> ahora hace por ti (JE-G.3: la cara visible refleja la realidad).

#### Acceptance Criteria
- [ ] **AC-08** [JE-Fautoclone.2]: El walkthrough de prerequisitos y el README (EN+ES) ya no instruyen al usuario a `git clone` manualmente como paso previo obligatorio; en su lugar describen que la extensión ofrece clonar el engine automáticamente. Test (grep): el walkthrough/README no contienen una instrucción de "clone the repo first" como prerequisito y sí mencionan el auto-clone gestionado.

---

## Interacciones UI

> No hay UI de producto. Las superficies son diálogos/notificaciones de la extensión.

### Acciones del usuario
| Acción | UC asociado | Frecuencia | Criticidad | Requiere confirmación |
|--------|-------------|------------|------------|----------------------|
| Auto-clone del engine (notifica, no pregunta) | UC-110 | Una vez (máquina nueva) | Media (operación de red+disco a dir gestionado) | No (automático) |
| Seleccionar carpeta manual (solo si el clone falla) | UC-110 | Rara | Baja | Sí (diálogo de degradación) |
| git pull del clon gestionado | UC-111 | Cada update | Baja (reversible) | No (auto, fire-and-forget) |

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| No bloqueo de activación | El clone/pull nunca cuelga `activate()` (patrón fire-and-forget v6.6.2) | Test: flujo resuelve aunque clone/pull fallen |
| Idempotencia | Re-ejecutar onboarding con el clon ya presente no re-clona (lo detecta en rutas conocidas) | Test: managed dir presente → no prompt de clone |
| Seguridad de disco | Un clone abortado no deja un directorio parcial que rompa futuras detecciones | Test AC-05 |
| Aislamiento del usuario | Un clon del usuario en otra ruta nunca recibe git pull ni se sobrescribe | Test AC-06 |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| `git` no instalado en la máquina | Media | Alto | AC-05: detectar fallo del clone → degradar a showOpenDialog con mensaje "instala git o selecciona la carpeta" |
| Clone parcial por corte de red | Baja | Medio | AC-05: limpiar `~/.specbox/specbox-engine` si la clonación aborta |
| `git pull --ff-only` falla por divergencia (usuario editó el clon gestionado) | Baja | Bajo | AC-07: warning no bloqueante, sigue con copia local |
| Doble fuente: usuario tiene clon propio Y el gestionado | Baja | Bajo | Orden de `resolveEnginePath`: config/workspace/comunes ganan; el gestionado es último recurso antes del diálogo |

---

## Stack Técnico (estimado)

- **Lenguaje**: TypeScript (extensión), Node ESM (tests)
- **Archivos**: `vscode-extension/src/install.ts` (resolveEnginePath + helpers nuevos), `vscode-extension/src/updater.ts` (git pull del gestionado), walkthrough + README
- **Tests**: `vscode-extension/tests/autoclone.test.mjs` (node:test, stub de vscode + stub de git)
- **Build**: `tsc -p ./` → `out/`; tests sobre `out/*.js`

## Archivos Principales
```
vscode-extension/src/install.ts        # managedEnginePath, isManagedPath, ENGINE_REPO_URL, auto-clone en resolveEnginePath
vscode-extension/src/updater.ts        # git pull del clon gestionado en el update flow
vscode-extension/tests/autoclone.test.mjs   # NUEVO — tests de los helpers + flujo
vscode-extension/media/walkthrough/step-prerequisites.md   # quitar "clone first"
README.md / README.es.md (o bloques EN/ES)   # describir auto-clone
```

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)
- [ ] **AC-01**: `managedEnginePath()` + `ENGINE_REPO_URL` correctos (UC-109)
- [ ] **AC-02**: `isManagedPath()` distingue gestionado vs clon de usuario (UC-109)
- [ ] **AC-03**: auto-clone automático antes del openDialog (UC-110)
- [ ] **AC-04**: clone exitoso → managed path + config persistida + notificación (UC-110)
- [ ] **AC-05**: clone fallido → degrada a openDialog, sin dir parcial (UC-110)
- [ ] **AC-06**: git pull solo sobre el clon gestionado (UC-111)
- [ ] **AC-07**: git pull fallido → warning no bloqueante (UC-111)
- [ ] **AC-08**: walkthrough/README sin "clone first" obligatorio (UC-112)

### Técnicos (no validados por AG-09)
- [ ] `tsc -p ./` compila sin errores
- [ ] Suite node:test de la extensión verde (incluye autoclone.test.mjs)

---
**Prioridad**: high
**Complejidad**: Media
*Generado: 2026-05-31*
