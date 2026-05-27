# PRD: [US-VSCODE-DISCOVERABILITY] Sidebar de descubrimiento y ayuda para la extensión VSCode

> **Origen**: Discovery `disc-6e6f4a7048af` (2026-05-27) → READY_FOR_PRD
> **Discovery artifact**: [doc/discovery/vscode_discoverability_sidebar/icp_jtbd.md](../discovery/vscode_discoverability_sidebar/icp_jtbd.md)
> **Tracking**: FreeForm board `ff-ed0c02f4565a`
> **Target release**: v6.6.0 "VSCode Discoverability"
> **Generado**: 2026-05-27 — autopilot agresivo

---

## Resumen

La extensión VSCode publicada en Marketplace en v6.2.0 (`EmbedBuild.specbox-engine`) abrió la puerta de adopción, y v6.3.0 añadió GitHub OAuth + Native default. El funnel post-install sigue roto: el sidebar `specbox.skills` muestra una lista hardcoded de 15 skills (de los cuales `remote` ya no existe — eliminado en v6.1.0 Cloud Cutover) y le faltan otros 11 skills clave (`/discovery`, `/handoff`, `/audit`, `/feedback`, los tres `/stripe-*`, `/switch-backend`, `/app-init`, `/app-sync`, `/manual-test`, `/queue-review`). Los items del TreeView no son clickables — el click no hace nada.

Esta US cierra el gap entre "instalada" y "activamente usada": el usuario que instala la extensión podrá descubrir los 25 skills SpecBox, agruparlos mentalmente por fase de workflow, y al hacer click ver una ficha completa con qué hace el skill, cuándo usarlo, el comando exacto a teclear y un ejemplo realista. **La invocación queda manual en el chat de Claude Code** — el sidebar es discovery + ayuda, no launcher.

---

## Alcance

### Incluye

- Refactor de `vscode-extension/src/views/skills-tree.ts` para que la lista de skills se derive del filesystem real (`~/.claude/skills/` global y/o `.claude/skills/` del workspace), no de un array hardcoded.
- Agrupación de los skills en categorías fijas: **Pipeline** (`/prd`, `/plan`, `/implement`, `/feedback`), **Quality** (`/audit`, `/compliance`, `/quality-gate`, `/acceptance-check`), **Visual** (`/visual-setup`, `/adapt-ui`, `/check-designs`), **Tracking** (`/switch-backend`, `/app-init`, `/app-sync`, `/queue-review`), **Stripe** (`/stripe-connect`, `/stripe-standard`, `/stripe-switch-account`), **Lifecycle** (`/release`, `/compliance`, `/handoff`, `/discovery`, `/quickstart`, `/manual-test`, `/optimize-agents`, `/explore`).
- Categoría **Otros** como catch-all para skills no clasificables (forward-compat con skills nuevos de releases futuros que aún no tengan categoría asignada).
- Skill desconocido = entrada con icono neutro + categoría "Otros". No bloquea el árbol.
- Para cada skill: ficha en webview o quickpick desplegada al hacer click, con cuatro bloques fijos:
  1. **Qué hace** — descripción de una frase.
  2. **Cuándo usarlo** — 2-3 contextos típicos.
  3. **Comando exacto** — el slash command como string copiable (`/skill_name [args]`) + botón "Copiar al portapapeles".
  4. **Ejemplo realista** — caso de uso concreto en este proyecto o equivalente.
- Botón "Copiar comando" en la ficha que copia el slash command al portapapeles del sistema y muestra notificación "Comando copiado, pega en el chat de Claude Code".
- Actualización del walkthrough `specbox.gettingStarted`: el step `step-install.md` debe dejar de afirmar "Install 15 skills" — cambiar a "Install all SpecBox skills" (sin número hardcoded). Añadir un quinto step `step-discover-skills` que apunte al sidebar.
- Tooltip de cada item del TreeView con el resumen de una línea (la versión condensada de "Qué hace").
- Tests `node:test` zero-deps para la lógica de carga de skills desde filesystem + agrupación por categoría.

### No incluye

- **No se ejecuta el slash command desde el sidebar.** El click despliega la ficha; la invocación queda manual en el chat de Claude Code. Decisión de diseño cerrada en discovery — elimina el bloqueador técnico de "¿existe API de Claude Code para invocar slash commands desde una extensión?".
- **No hay webview dashboard con métricas dinámicas** (Marketplace stats, UCs completados, healing budget). Diferido a US futura cuando haya señal de demanda.
- **No se modifica `status-tree.ts`** ni la identity row OAuth/FreeForm de v6.3.0 — ya está estable.
- **No se añaden tests E2E con automatización de UI de VSCode** (Extension Development Host). La validación visual queda en review humano antes del merge.
- **No se cambia la activity bar icon, color de la galería, ni el icon SVG del sidebar.** Cambios cosméticos diferidos.
- **No se internacionaliza el contenido de las fichas de skills** (qué hace, cuándo usarlo, ejemplo). Solo strings de UI (labels, tooltips de tree items, botones) van por `package.nls.json` / `package.nls.es.json` siguiendo el patrón de v6.3.0. El contenido descriptivo queda en EN para v1; ES se añade en US futura si hay demanda.

---

## User Story

**ID**: US-VSCODE-DISCOVERABILITY
**Nombre**: Sidebar de descubrimiento y ayuda para la extensión VSCode
**Actor**: Dev que instala la extensión SpecBox desde Marketplace (ICP-2) + owner-operator del engine (ICP-1)
**Horas estimadas**: 24h
**Pantallas**: sidebar `specbox.skills` (TreeView con categorías) + ficha de skill (webview o quickpick — decisión en `/plan`)

> Como dev que acaba de instalar SpecBox desde el Marketplace, quiero que el sidebar de la extensión refleje los skills reales del engine agrupados por categoría y que al hacer click sobre cada uno vea qué hace, cuándo usarlo y el comando exacto a teclear, para descubrir el sistema sin tener que leer el README de 1500 líneas y empezar a usarlo de verdad.

---

## Use Cases

### UC-701: Auto-detección de skills desde filesystem

- **Actor**: Engine + extensión VSCode
- **Horas**: 4h
- **Pantallas**: ninguna (lógica)
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-01** [JR-F.1]: `SkillsTreeProvider.getChildren()` lee skills desde `~/.claude/skills/*/SKILL.md` (global) y `${workspace}/.claude/skills/*/SKILL.md` (local) en lugar del array `CORE_SKILLS` hardcoded; cada skill detectado es una entrada con su nombre (sin el slash) y su `description` extraída del frontmatter YAML del SKILL.md.
- [ ] **AC-02**: si un skill aparece tanto en global como en local, prevalece el local; el árbol nunca muestra duplicados.
- [ ] **AC-03**: si el filesystem no es legible (permisos, FS corrupto), el TreeView muestra un único item informativo "No skills detected — run /install or check ~/.claude/skills/" en vez de fallar; el bug se loguea a la output channel `SpecBox` con stack trace completo.
- [ ] **AC-04** [JR-F.1]: tras instalar un skill nuevo vía `installer.runFullInstall()`, llamar `skillsTree.refresh()` repuebla el árbol con el skill nuevo sin reiniciar VSCode.

### UC-702: Agrupación de skills por categoría

- **Actor**: Extensión VSCode
- **Horas**: 3h
- **Pantallas**: sidebar `specbox.skills`
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-05** [JR-F.5]: el TreeView muestra 7 categorías de primer nivel colapsables: **Pipeline**, **Quality**, **Visual**, **Tracking**, **Stripe**, **Lifecycle**, **Otros**, en ese orden exacto.
- [ ] **AC-06**: cada categoría tiene un icono `ThemeIcon` distinto y consistente (p.ej. `rocket` para Pipeline, `shield` para Quality, `paintcan` para Visual, `list-tree` para Tracking, `credit-card` para Stripe, `tools` para Lifecycle, `question` para Otros).
- [ ] **AC-07**: el mapeo skill → categoría está declarado en un objeto/Map en `skills-tree.ts` (o un archivo dedicado `skill-categories.ts`) con tipado TypeScript estricto; skills no listados en el mapping caen automáticamente en **Otros**.
- [ ] **AC-08**: cada categoría muestra entre paréntesis el número de skills detectados que contiene, p.ej. "Pipeline (4)", "Otros (0)" cuando esté vacía. Una categoría con 0 skills sigue mostrándose colapsada con "(0)" para preservar el mental model.
- [ ] **AC-09**: el mapping cubre al menos los 25 skills actualmente instalados del engine: prd, plan, implement, feedback (Pipeline); audit, compliance, quality-gate, acceptance-check (Quality); visual-setup, adapt-ui, check-designs (Visual); switch-backend, app-init, app-sync, queue-review (Tracking); stripe-connect, stripe-standard, stripe-switch-account (Stripe); release, handoff, discovery, quickstart, manual-test, optimize-agents, explore (Lifecycle).

### UC-703: Ficha de skill al hacer click

- **Actor**: Dev (ICP-1 y ICP-2)
- **Horas**: 6h
- **Pantallas**: webview o quickpick (decisión técnica en `/plan`)
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-10** [JR-F.4]: al hacer click en un skill del TreeView, se abre una ficha (webview panel o quickpick con descripción rica — decisión en plan) que muestra cuatro bloques claramente separados: **Qué hace**, **Cuándo usarlo**, **Comando exacto**, **Ejemplo**.
- [ ] **AC-11**: la información de los cuatro bloques se lee del frontmatter `description` del `SKILL.md` correspondiente cuando esté presente, y de un fallback estático (objeto en código de la extensión) cuando el SKILL.md no tenga ese contenido estructurado. La fuente del contenido se etiqueta visiblemente al pie de la ficha ("from SKILL.md" o "from extension defaults").
- [ ] **AC-12** [JR-F.4]: el bloque "Comando exacto" muestra el slash command como string monoespaciado (p.ej. `/prd <feature_name>`) con un botón "Copiar al portapapeles" inmediatamente al lado.
- [ ] **AC-13**: al pulsar "Copiar al portapapeles", el comando se copia (vía `vscode.env.clipboard.writeText`) y aparece una notificación `Información copiada — pega en el chat de Claude Code` durante 3 segundos.
- [ ] **AC-14**: cerrar la ficha (`X` del webview, `Esc` del quickpick) la cierra sin dejar estado residual; volver a hacer click en el mismo skill la vuelve a abrir.
- [ ] **AC-15** [JE-F.3]: el "Ejemplo" mostrado para cada skill es funcional — el comando exacto del bloque "Comando exacto" debe ejecutarse correctamente si el usuario lo pega tal cual en el chat. Validado manualmente para los 5 skills más usados (prd, plan, implement, audit, handoff) antes del merge.

### UC-704: Walkthrough actualizado + tooltip rico

- **Actor**: Dev nuevo tras `Install` (ICP-2)
- **Horas**: 3h
- **Pantallas**: walkthrough `specbox.gettingStarted` + tooltips del TreeView
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-16** [JR-F.3]: el step `step-install.md` del walkthrough deja de afirmar "Install 15 skills" — la nueva copia es agnóstica al número exacto: "Install all SpecBox skills and hooks".
- [ ] **AC-17** [JR-F.3]: el walkthrough gana un quinto step `step-discover-skills` con título "Explore your new skills" + descripción que indica abrir el sidebar `SpecBox` en la activity bar y hacer click en cualquier skill para ver su ficha; incluye command link a `command:workbench.view.extension.specbox` para abrir la activity bar correspondiente.
- [ ] **AC-18** [JR-F.2]: cada item de skill en el TreeView muestra como tooltip (al hover) la primera frase de "Qué hace" tomada del mismo source que la ficha. El tooltip debe ser legible en <5 segundos (≤120 caracteres en la primera línea).
- [ ] **AC-19**: el `package.json` declara `step-discover-skills` y su markdown asociado en `vscode-extension/media/walkthrough/step-discover-skills.md`; el step pasa el linter de i18n existente (`tests/oauth.test.mjs` ya valida shape — extender o añadir test sibling).

### UC-705: Tests + smoke manual + bump versión

- **Actor**: Engine (release pipeline)
- **Horas**: 6h
- **Pantallas**: ninguna
- **Estado**: backlog

#### Acceptance Criteria

- [ ] **AC-20**: nuevo archivo `vscode-extension/tests/skills-tree.test.mjs` con suite `node:test` que cubre: (a) `loadSkillsFromFilesystem(rootPaths)` lee correctamente desde dos directorios mock, (b) prevalencia local > global, (c) skill desconocido cae en "Otros", (d) categorías con 0 skills aparecen con sufijo "(0)", (e) `getCategoryFor(skillName)` devuelve la categoría correcta para los 25 skills del mapping declarado.
- [ ] **AC-21**: nuevo archivo `vscode-extension/tests/skill-card.test.mjs` o equivalente con suite `node:test` que cubre: (a) lectura de frontmatter `description` de un SKILL.md sintético, (b) fallback a contenido estático cuando el frontmatter no tiene la estructura esperada, (c) función pura `buildSkillCardContent(skill)` que devuelve los cuatro bloques esperados como string/HTML.
- [ ] **AC-22**: la suite completa de la extensión (`npm test` en `vscode-extension/`) sigue verde — todos los tests previos de OAuth, secret storage, MCP launcher, etc. pasan sin regresión.
- [ ] **AC-23**: el `package.json` de la extensión sube de `6.3.0` a `6.6.0` (lockstep con engine v6.6.0). `CHANGELOG.md` de la extensión gana sección `[6.6.0] — "Discoverability"` con el listado de cambios.
- [ ] **AC-24**: `ENGINE_VERSION.yaml` sube a `6.6.0` con codename `"VSCode Discoverability"`. `CLAUDE.md` gana sección "VSCode Discoverability (v6.6.0)" documentando el sidebar mejorado y referenciando este PRD.
- [ ] **AC-25** [JE-F.1]: smoke test manual ejecutado antes del merge: el reviewer humano (JPS) (a) instala el VSIX recién compilado en una instancia limpia de VSCode, (b) verifica que el sidebar muestra las 7 categorías con conteos correctos, (c) hace click en al menos 3 skills de categorías distintas y confirma que la ficha carga y el botón "Copiar" funciona, (d) ejecuta el walkthrough completo (los 5 pasos) sin errores. El veredicto manual queda como comentario en el PR antes del merge.

---

## Interacciones UI

### Visualización de datos

| Dato | Volumen | Atributos visibles | Acciones por item |
|------|---------|--------------------|-------------------|
| Categoría (root) | 7 fijas | Nombre + icono + `(N)` skills | Expandir/colapsar |
| Skill (hijo) | 25-35 (auto-detectado) | Slash command + descripción corta | Click → ficha |
| Ficha (webview/quickpick) | 1 a la vez | 4 bloques (qué/cuándo/comando/ejemplo) + botón copy | Copiar comando / cerrar |

### Acciones del usuario

| Acción | UC asociado | Frecuencia | Criticidad | Requiere confirmación |
|--------|-------------|------------|------------|----------------------|
| Click en categoría → expandir | UC-702 | Frecuente | Baja | No |
| Click en skill → ver ficha | UC-703 | Frecuente | Baja | No |
| Click en "Copiar comando" | UC-703 | Frecuente | Baja | No |
| Ejecutar walkthrough completo | UC-704 | Ocasional (1 vez post-install) | Baja | No |
| Refresh tras Install | UC-701 | Rara (tras `specbox.install`) | Baja | No |

### Formularios

Ninguno. La feature es read-only de datos del filesystem + acción de copy-to-clipboard.

---

## Audiencia (heredada de discovery)

Heredada del artefacto `disc-6e6f4a7048af`. Cuatro JTBDs racionales adicionales se tagean en los AC:

- **JR-F.1** [ICP-1]: auto-detect skills → AC-01, AC-04.
- **JR-F.2** [ICP-1]: ficha como referencia rápida → AC-18.
- **JR-F.3** [ICP-2]: descubrir skills post-walkthrough → AC-16, AC-17.
- **JR-F.4** [ICP-2]: click → ficha completa → AC-10, AC-12.
- **JR-F.5** [ICP-2]: agrupación por categoría → AC-05.

JTBDs emocionales (validados en qualitative gate durante `/implement`):

- **JE-F.1** [ICP-1]: calidad del sidebar refleja calidad del engine → AC-25.
- **JE-F.2** [ICP-2]: sistema entero al alcance — implícito en AC-05/AC-09.
- **JE-F.3** [ICP-2]: lo que muestra el sidebar es real → AC-15.

---

## NFRs

| NFR | Criterio | Medición |
|-----|----------|----------|
| Rendimiento — startup | `SkillsTreeProvider.getChildren()` completa la carga inicial en < 200ms en un FS típico (SSD, 30 skills) | `console.time` en dev mode |
| Rendimiento — refresh | tras `specbox.install`, el refresh repuebla el árbol en < 100ms | manual |
| Robustez | si un SKILL.md tiene frontmatter mal formado, el skill aparece igual con descripción placeholder "(no description available)" en lugar de hacer crash | test sintético |
| Accesibilidad | tooltips legibles por screen reader (VSCode los expone vía aria) | inspección manual con VoiceOver |
| Compatibilidad | extensión sigue funcionando en VSCode 1.86+ (engines.vscode actual) | CI compile + tests |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Webview con HTML custom rompe la integración con el theme oscuro/claro de VSCode | Media | Medio | Usar `vscode.window.createWebviewPanel` con `enableScripts: false` + CSS variables del theme (`var(--vscode-foreground)`); fallback a quickpick si webview produce churn visual |
| El frontmatter de SKILL.md tiene drift entre skills (formato libre, no schema strict) | Alta | Bajo | Lectura best-effort con fallback a content estático en código; ningún path lanza excepción al usuario |
| El mapping skill→categoría se queda obsoleto en releases futuros cuando se añaden skills nuevos | Media | Bajo | Categoría "Otros" catch-all + nota en `CLAUDE.md` "actualizar `skill-categories.ts` al añadir un skill nuevo"; idealmente un test futuro que falle si un skill en `~/.claude/skills/` no está mapeado |
| Smoke test manual subjetivo (AC-25) | Media | Medio | Checklist explícito en el AC + el reviewer humano es el ICP-1 (dogfooding) |
| Webview vs quickpick — decisión técnica diferida a `/plan` | Baja | Bajo | El plan elegirá la solución más simple; si webview produce churn lo degradamos a quickpick con descripción rica |

---

## Stack Técnico

- **Lenguaje**: TypeScript 5.5+ (lockstep con extensión actual)
- **Runtime objetivo**: VSCode Extension Host (Node 20+)
- **Dependencias nuevas**: ninguna (`fs/promises`, `path`, `vscode` API son suficientes)
- **Archivos principales**:
  - `vscode-extension/src/views/skills-tree.ts` — refactor mayor (filesystem read + agrupación)
  - `vscode-extension/src/views/skill-categories.ts` — **nuevo** — mapping skill → categoría + tipos
  - `vscode-extension/src/views/skill-card.ts` — **nuevo** — builder del contenido de la ficha + abrir webview/quickpick
  - `vscode-extension/src/constants.ts` — extender `CORE_SKILLS` o reemplazar por loader dinámico
  - `vscode-extension/src/extension.ts` — registrar comando `specbox.showSkillCard`
  - `vscode-extension/package.json` — añadir comando + step de walkthrough
  - `vscode-extension/media/walkthrough/step-discover-skills.md` — **nuevo**
  - `vscode-extension/media/walkthrough/step-install.md` — editar copy
  - `vscode-extension/tests/skills-tree.test.mjs` — **nuevo**
  - `vscode-extension/tests/skill-card.test.mjs` — **nuevo**
  - `CHANGELOG.md` (extensión) — sección 6.6.0
  - `ENGINE_VERSION.yaml` — bump 6.5.0 → 6.6.0
  - `CLAUDE.md` — sección nueva

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

- [ ] **AC-01**: `SkillsTreeProvider` lee skills desde filesystem real (no array hardcoded).
- [ ] **AC-02**: prevalencia local > global, sin duplicados.
- [ ] **AC-03**: error de FS muestra item informativo, no crash.
- [ ] **AC-04**: refresh tras install repuebla el árbol sin reiniciar VSCode.
- [ ] **AC-05**: 7 categorías root colapsables en orden fijo.
- [ ] **AC-06**: cada categoría con icono `ThemeIcon` consistente.
- [ ] **AC-07**: mapping skill→categoría tipado, fallback a "Otros".
- [ ] **AC-08**: cada categoría muestra `(N)` con conteo, incluso `(0)`.
- [ ] **AC-09**: mapping cubre los 25 skills actuales del engine.
- [ ] **AC-10**: click en skill abre ficha con 4 bloques.
- [ ] **AC-11**: contenido leído de frontmatter SKILL.md + fallback estático, source etiquetado.
- [ ] **AC-12**: bloque "Comando exacto" como string + botón copiar.
- [ ] **AC-13**: botón copiar funciona + notificación 3s.
- [ ] **AC-14**: cerrar ficha no deja estado residual.
- [ ] **AC-15**: ejemplo del bloque "Comando exacto" es funcional para los 5 skills más usados.
- [ ] **AC-16**: walkthrough step-install deja de hardcodear "15 skills".
- [ ] **AC-17**: nuevo step `step-discover-skills` con command link al sidebar.
- [ ] **AC-18**: tooltip de cada item TreeView ≤120 chars.
- [ ] **AC-19**: package.json declara nuevo step + markdown.
- [ ] **AC-20**: suite `skills-tree.test.mjs` cubre 5 casos.
- [ ] **AC-21**: suite `skill-card.test.mjs` cubre 3 casos.
- [ ] **AC-22**: `npm test` completo sigue verde (sin regresión OAuth/secret storage/MCP launcher).
- [ ] **AC-23**: `package.json` extensión 6.3.0 → 6.6.0 + CHANGELOG entry.
- [ ] **AC-24**: `ENGINE_VERSION.yaml` 6.5.0 → 6.6.0 + CLAUDE.md sección.
- [ ] **AC-25**: smoke manual del reviewer antes del merge.

### Técnicos (no validados por AG-09)

- [ ] Proyecto compila sin errores (`tsc -p ./` en `vscode-extension/`).
- [ ] Linter peninsular: copy del walkthrough en EN (no ES, no argentinismos).
- [ ] CI workflow `oauth-e2e.yml` sigue verde (la extensión no rompe regresión).
- [ ] VSIX package se genera correctamente con `vsce package`.

---

## VEG Readiness

**DISABLED** — la feature toca UI de VSCode (webview + treeview), no UI de producto de un cliente. VEG (Visual Experience Generation) no aplica: la extensión hereda los tokens de theme del propio VSCode, no genera assets desde brand kit.

---

## Definition Quality Gate

Autoevaluación del autopilot agresivo:

| AC | Especificidad | Medibilidad | Testabilidad | Veredicto |
|-----|---------------|-------------|--------------|-----------|
| AC-01..AC-04 | 2 | 2 | 2 | OK |
| AC-05..AC-09 | 2 | 2 | 2 | OK |
| AC-10..AC-15 | 2 | 2 | 2 (excepto AC-15 que es 1 por smoke manual) | OK |
| AC-16..AC-19 | 2 | 2 | 2 | OK |
| AC-20..AC-22 | 2 | 2 | 2 | OK |
| AC-23..AC-24 | 2 | 2 | 2 | OK |
| AC-25 | 2 | 1 (subjetivo dentro del checklist) | 1 (manual) | OK (acceptable) |

**Promedio**: ~1.9/2.0. Todos los UCs tienen al menos 4 ACs. Cobertura funcional: 25 ACs sobre 5 UCs = 5.0 ratio. **APROBADO**.

---

**Prioridad**: high (cierra funnel post-install crítico para v6.2.0/v6.3.0)
**Complejidad**: Media
**Estimación**: 24h (4+3+6+3+6+2h buffer)
**Target release**: v6.6.0 "VSCode Discoverability"

*Generado: 2026-05-27 — autopilot agresivo*
