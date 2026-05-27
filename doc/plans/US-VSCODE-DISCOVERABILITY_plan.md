# Plan: US-VSCODE-DISCOVERABILITY — Sidebar de descubrimiento y ayuda para la extensión VSCode

> **Generado**: 2026-05-27 — autopilot agresivo
> **Origen**: FreeForm `ff-ed0c02f4565a` → US-VSCODE-DISCOVERABILITY (UC-701..UC-705)
> **PRD**: [doc/prd/US-VSCODE-DISCOVERABILITY_prd.md](../prd/US-VSCODE-DISCOVERABILITY_prd.md)
> **Discovery**: [doc/discovery/vscode_discoverability_sidebar/icp_jtbd.md](../discovery/vscode_discoverability_sidebar/icp_jtbd.md)
> **Target release**: v6.6.0 "VSCode Discoverability"
> **Estado**: Pendiente
> **stitch_designs**: N/A (UI de VSCode nativa, no UI de producto generable por Stitch)

---

## Resumen

Refactor del TreeView `specbox.skills` de la extensión VSCode para que (a) liste skills reales del filesystem en lugar del array `CORE_SKILLS` hardcoded, (b) los agrupe en 7 categorías canónicas, (c) abra una ficha de ayuda al hacer click con cuatro bloques (qué/cuándo/comando/ejemplo) + botón "Copiar al portapapeles", (d) extienda el walkthrough con un quinto step de tour. El click NO ejecuta el skill.

---

## Análisis UI (Fase 0)

### Componentes Requeridos

| Requisito | Componente | Estado | Acción |
|-----------|------------|--------|--------|
| Lista jerárquica de categorías + skills | `TreeView` (VSCode API) | ✅ | Reutilizar — ya existe `specbox.skills` |
| Categoría root colapsable con `(N)` skills | `TreeItem` con `collapsibleState = Collapsed` | ✅ | Crear nuevo subclase `CategoryItem` |
| Item de skill clickeable | `TreeItem` con `command` | ⚠️ | Hoy existe `SkillItem` sin `command:` — añadirlo |
| Ficha de ayuda (qué/cuándo/comando/ejemplo) | `WebviewPanel` o `QuickPick` con `details` rico | ❌ | CREAR — decisión técnica abajo |
| Botón "Copiar al portapapeles" | Botón en webview o `QuickPickItem.buttons` | ❌ | CREAR |
| Notificación toast de copia | `vscode.window.showInformationMessage` | ✅ | Reutilizar API estándar |
| Walkthrough step nuevo | `walkthrough` step en `package.json` + `media/walkthrough/*.md` | ✅ | Reutilizar patrón existente |
| Tooltip rico en items | `TreeItem.tooltip = MarkdownString` | ✅ | Reutilizar API estándar |

### Decisión técnica: Webview vs QuickPick para la ficha

El PRD difería la decisión al plan. Análisis:

| Criterio | WebviewPanel | QuickPick con detail |
|---|---|---|
| Layout HTML libre (4 bloques + botón) | ✅ Sí | ⚠️ Limitado a label + description + detail |
| Theme adaptation (claro/oscuro) | ⚠️ Requiere CSS con `var(--vscode-*)` | ✅ Nativo |
| Tamaño de bundle (sin deps externas) | ✅ HTML+CSS inline en el .ts | ✅ Cero coste |
| Mantenimiento (cambios cosméticos) | ⚠️ HTML embebido en string template | ✅ Strings simples |
| Botones extra (Copy command) | ✅ `<button onclick="...">` con `acquireVsCodeApi()` postMessage | ⚠️ `QuickPickItem.buttons[]` permite iconos clickeables |
| Cerrar limpio sin estado residual | ⚠️ Requiere disposal explícito | ✅ Nativo (Esc) |
| Accesibilidad (screen readers) | ⚠️ HTML custom — depende de markup | ✅ Heredada de VSCode |
| Riesgo de churn visual con theme oscuro | Medio | Cero |

**Decisión: QuickPick con `detail` markdown + botón inline `buttons[]`**. Razones:

1. **Cero riesgo de churn visual** — heredamos el tema nativo de VSCode automáticamente, no hay CSS que mantener.
2. **Accesibilidad gratis** — VSCode resuelve aria por nosotros.
3. **Mantenimiento más simple** — el contenido es strings markdown que entran en `detail`, no plantillas HTML.
4. **El botón "Copiar comando"** se implementa como `QuickPickItem.buttons[]` con icono `copy` de `ThemeIcon`; al pulsarlo, callback con `vscode.env.clipboard.writeText` + notificación toast.
5. **Disposal automático** al pulsar Esc — sin riesgo de leak.

Tradeoff: el layout es menos personalizable (no podemos hacer un grid bonito). Aceptable — el contenido es texto, no datos visuales.

### Widgets a Crear

1. **`SkillCategoryItem`** (`vscode-extension/src/views/skills-tree.ts`)
   - Subclase de `vscode.TreeItem`.
   - Props: `categoryId`, `categoryLabel`, `skillCount`, `themeIconName`.
   - `collapsibleState = TreeItemCollapsibleState.Expanded`.
   - `description = "(N)"` con el conteo.

2. **`SkillItem`** (refactor del existente en `skills-tree.ts`)
   - Ya existe. Cambiar:
     - `iconPath` de `check`/`circle-slash` → icono propio del skill o `ThemeIcon('extensions')` neutral.
     - Añadir `command: { command: 'specbox.showSkillCard', arguments: [skillName], title: '...' }`.
     - `tooltip` pasa a ser `MarkdownString` con la primera frase de "Qué hace".
     - Se mantienen la descripción y el slash.

3. **`buildSkillCardItems(skill: SkillInfo): vscode.QuickPickItem[]`** (`vscode-extension/src/views/skill-card.ts`, nuevo)
   - Función pura que devuelve un array de items para el QuickPick:
     - Item 1 (label: "What it does", detail: descripción)
     - Item 2 (label: "When to use it", detail: lista)
     - Item 3 (label: "Command", detail: el slash command, `buttons: [{iconPath: ThemeIcon('copy'), tooltip: 'Copy to clipboard'}]`)
     - Item 4 (label: "Example", detail: ejemplo)
     - Item 5 (label: separator)
     - Item 6 (label: "Source: from SKILL.md | from extension defaults", `picked: false`, `alwaysShow: true`)
   - Sin side effects — testeable con `node:test`.

4. **`showSkillCard(skillName: string): Promise<void>`** (`vscode-extension/src/views/skill-card.ts`, nuevo)
   - Wrapper que registra el QuickPick, expone el botón "Copiar comando", lo conecta a `vscode.env.clipboard.writeText`, y muestra el toast.
   - Cierra el QuickPick automáticamente al pulsar Esc o al copiar (consistencia: el botón cierra después de copiar).

5. **`loadSkillsFromFilesystem(rootPaths: string[]): Promise<SkillInfo[]>`** (`vscode-extension/src/views/skill-loader.ts`, nuevo)
   - Función pura que itera `rootPaths` (en orden de prioridad: workspace local > global) y lee cada `SKILL.md` para extraer name + description del frontmatter YAML.
   - Devuelve `SkillInfo[]` deduplicado por `name` (primer hit gana — local sobre global).
   - Manejo de errores: si una entrada falla, loguea a `OutputChannel` y continúa (no propaga).
   - Sin dependencia de `vscode` — recibe paths y devuelve datos. Testeable.

6. **`getCategoryFor(skillName: string): SkillCategory`** (`vscode-extension/src/views/skill-categories.ts`, nuevo)
   - Función pura. Lookup en mapa estático `SKILL_CATEGORIES: Record<string, SkillCategory>`.
   - Si el skill no está en el mapa → devuelve `'other'`.

7. **`step-discover-skills.md`** (`vscode-extension/media/walkthrough/`, nuevo)
   - Markdown corto del nuevo paso del walkthrough.

---

## Análisis de impacto cruzado

El refactor toca el array `CORE_SKILLS` en `vscode-extension/src/constants.ts:12-17`. Esta constante se usa en:

1. **`skills-tree.ts`** — fuente principal, refactor central.
2. **`install.ts:114-118`** `getInstalledSkills()` — filtra `CORE_SKILLS` contra el filesystem para reportar al status tree. **Esto debe refactorizarse junto** o el árbol mostrará los 25 skills reales pero el status seguirá contando solo los 15 hardcoded → el "Skills: N/M" del `status-tree.ts:65-67` quedará incoherente. **Crítico — añadir a UC-701**.
3. **`health.ts`** (no inspeccionado directamente pero referenciado por `getInstalledSkills`) — depende transitivamente. Si `install.ts.getInstalledSkills()` cambia su semántica (de "15 conocidos" a "todos detectados"), el reporte del status tree muestra el conteo real.

**Conclusión**: hay que tratar `CORE_SKILLS` como **lista de skills oficiales del engine** (no como lista de discovery). Renombrar a `KNOWN_SKILLS` y usar como tabla de **categorización** (input para `SKILL_CATEGORIES`), no como fuente de verdad del filesystem. El loader siempre lee del filesystem.

---

## Fases de Implementación

Cinco fases mapeadas 1:1 a los 5 UCs. Ejecutar **en orden** — F1 (loader) es prerequisito de F2 (categorización), F2 es prerequisito de F3 (ficha al click), F4 (walkthrough + tooltip) depende de F1 y F3. F5 (tests + release) cierra.

### Fase 1: UC-701 — Auto-detección de skills desde filesystem (4h)

**Objetivo**: reemplazar `CORE_SKILLS` hardcoded por loader dinámico que lee `~/.claude/skills/` global + workspace.

**Archivos a crear/modificar**:

- ✏️ `vscode-extension/src/constants.ts` — `CORE_SKILLS` renombrado a `KNOWN_SKILLS` o eliminado completo (decidir en F2 cuando se construya el mapa de categorías).
- ✏️ `vscode-extension/src/install.ts:114-118` — `getInstalledSkills()` lee del filesystem, no filtra por `CORE_SKILLS`.
- 🆕 `vscode-extension/src/views/skill-loader.ts` — `loadSkillsFromFilesystem()`, `parseSkillFrontmatter()`, tipo `SkillInfo`.
- ✏️ `vscode-extension/src/views/skills-tree.ts` — `SkillsTreeProvider.getChildren()` usa el loader.
- ✏️ `vscode-extension/src/extension.ts:38-39` — pasar workspace paths al constructor del provider si hace falta.

**Sub-tareas**:

1. Definir tipo `SkillInfo`:
   ```typescript
   interface SkillInfo {
     name: string;            // sin slash
     description: string;     // primera frase del frontmatter o fallback
     source: 'local' | 'global';
     skillMdPath: string;     // path absoluto al SKILL.md leído
     hasFrontmatter: boolean; // false si fallback aplicó
   }
   ```

2. Implementar `parseSkillFrontmatter(content: string): { name?: string; description?: string }` — parser YAML minimalista, sin deps (3-4 líneas matcheando `---\n...\n---`).

3. Implementar `loadSkillsFromFilesystem(rootPaths: string[]): Promise<SkillInfo[]>`:
   - Para cada root, `fs.readdirSync` con `withFileTypes: true`, filtrar directorios.
   - Para cada dir, intentar leer `SKILL.md`. Si falla → loguear, skip.
   - Deduplicar por `name` (orden: local > global).

4. Modificar `SkillsTreeProvider`:
   - Constructor recibe `workspaceFolders: string[]` además de `installer`.
   - `getChildren()` async — llama al loader.
   - Caché en memoria con invalidación en `refresh()`.

5. Modificar `extension.ts`:
   - Pasar `vscode.workspace.workspaceFolders?.map(f => f.uri.fsPath) ?? []` al constructor de `SkillsTreeProvider`.

6. Refactorizar `InstallManager.getInstalledSkills()`:
   - Leer directamente `fs.readdirSync(CLAUDE_SKILLS_DIR)` filtrando dirs con `SKILL.md`.
   - Devolver `string[]` con los nombres detectados (no filtrar contra `CORE_SKILLS`).

7. Error path (AC-03):
   - Si `fs.readdirSync` lanza, atrapar y devolver `[]`.
   - El `SkillsTreeProvider.getChildren()` detecta `[]` → devuelve un item informativo.
   - Loguear stack trace a `OutputChannel('SpecBox')`.

**Mapeo AC**:
- AC-01 → sub-tareas 1-4
- AC-02 → sub-tarea 3 (dedup local>global)
- AC-03 → sub-tarea 7
- AC-04 → caché invalidable en `SkillsTreeProvider.refresh()` (ya hay método, llamarlo tras install)

**Verificación local rápida**:
```bash
cd vscode-extension
npm run compile
# Abrir Extension Development Host (F5), confirmar que el sidebar muestra los 25 skills reales
```

### Fase 2: UC-702 — Agrupación de skills por categoría (3h)

**Objetivo**: introducir 7 categorías root en el TreeView con icono + conteo `(N)`.

**Archivos a crear/modificar**:

- 🆕 `vscode-extension/src/views/skill-categories.ts` — mapa skill→categoría + tipos + ordering + iconos.
- ✏️ `vscode-extension/src/views/skills-tree.ts` — `getChildren()` ahora devuelve categorías root cuando se llama sin elemento; con elemento, devuelve los skills hijos.
- ✏️ `vscode-extension/src/views/skills-tree.ts` — añadir clase `SkillCategoryItem`.

**Sub-tareas**:

1. Crear `skill-categories.ts`:
   ```typescript
   export type SkillCategory =
     | 'pipeline' | 'quality' | 'visual' | 'tracking'
     | 'stripe' | 'lifecycle' | 'other';

   export const CATEGORY_ORDER: SkillCategory[] = [
     'pipeline', 'quality', 'visual', 'tracking',
     'stripe', 'lifecycle', 'other',
   ];

   export const CATEGORY_LABELS: Record<SkillCategory, string> = {
     pipeline: 'Pipeline',
     quality: 'Quality',
     visual: 'Visual',
     tracking: 'Tracking',
     stripe: 'Stripe',
     lifecycle: 'Lifecycle',
     other: 'Other',
   };

   export const CATEGORY_ICONS: Record<SkillCategory, string> = {
     pipeline: 'rocket',
     quality: 'shield',
     visual: 'paintcan',
     tracking: 'list-tree',
     stripe: 'credit-card',
     lifecycle: 'tools',
     other: 'question',
   };

   const SKILL_TO_CATEGORY: Record<string, SkillCategory> = {
     prd: 'pipeline', plan: 'pipeline', implement: 'pipeline', feedback: 'pipeline',
     audit: 'quality', compliance: 'quality',
     'quality-gate': 'quality', 'acceptance-check': 'quality',
     'visual-setup': 'visual', 'adapt-ui': 'visual', 'check-designs': 'visual',
     'switch-backend': 'tracking', 'app-init': 'tracking',
     'app-sync': 'tracking', 'queue-review': 'tracking',
     'stripe-connect': 'stripe', 'stripe-standard': 'stripe',
     'stripe-switch-account': 'stripe',
     release: 'lifecycle', handoff: 'lifecycle', discovery: 'lifecycle',
     quickstart: 'lifecycle', 'manual-test': 'lifecycle',
     'optimize-agents': 'lifecycle', explore: 'lifecycle',
   };

   export function getCategoryFor(skillName: string): SkillCategory {
     return SKILL_TO_CATEGORY[skillName] ?? 'other';
   }
   ```

2. Refactorizar `SkillsTreeProvider`:
   - `getChildren(element?: TreeItem)`:
     - Si `element` es `undefined` (root) → devolver 7 `SkillCategoryItem` en `CATEGORY_ORDER` (incluso si `count === 0`).
     - Si `element` es `SkillCategoryItem` → devolver los `SkillItem` de esa categoría, ordenados alfabéticamente.
     - Si `element` es `SkillItem` → devolver `[]` (leaf).
   - Caché de skills por categoría calculada en una pasada tras el loader.

3. Crear `SkillCategoryItem`:
   ```typescript
   class SkillCategoryItem extends vscode.TreeItem {
     constructor(public readonly category: SkillCategory, public readonly count: number) {
       super(CATEGORY_LABELS[category], vscode.TreeItemCollapsibleState.Expanded);
       this.description = `(${count})`;
       this.iconPath = new vscode.ThemeIcon(CATEGORY_ICONS[category]);
       this.contextValue = 'specboxSkillCategory';
     }
   }
   ```

4. Vincular skill→category al iterar:
   - En `getChildren()` del flujo root, agrupar la lista de `SkillInfo` por `getCategoryFor(skill.name)` con `Map<SkillCategory, SkillInfo[]>`.
   - Para cada `cat` en `CATEGORY_ORDER`, devolver `new SkillCategoryItem(cat, skillsByCategory.get(cat)?.length ?? 0)`.

**Mapeo AC**:
- AC-05 → sub-tarea 2 + `CATEGORY_ORDER` exacto
- AC-06 → `CATEGORY_ICONS` con 7 ThemeIcons distintos
- AC-07 → `skill-categories.ts` con tipado estricto + fallback `'other'`
- AC-08 → `description = "(${count})"` siempre, incluso `count === 0`
- AC-09 → el mapping `SKILL_TO_CATEGORY` cubre los 25 skills

**Verificación local rápida**:
```bash
cd vscode-extension && npm run compile
# Abrir Extension Development Host (F5)
# Confirmar 7 categorías visibles con su conteo correcto
```

### Fase 3: UC-703 — Ficha de skill al hacer click (6h)

**Objetivo**: click en un skill abre QuickPick con 4 bloques + botón "Copiar".

**Archivos a crear/modificar**:

- 🆕 `vscode-extension/src/views/skill-card.ts` — `buildSkillCardItems()`, `showSkillCard()`, lectura de descripciones fallback.
- 🆕 `vscode-extension/src/views/skill-defaults.ts` — diccionario de fallback con qué/cuándo/comando/ejemplo por skill.
- ✏️ `vscode-extension/src/extension.ts` — registrar comando `specbox.showSkillCard`.
- ✏️ `vscode-extension/package.json` — declarar comando en `contributes.commands`.
- ✏️ `vscode-extension/src/views/skills-tree.ts` — `SkillItem` con `command: { command: 'specbox.showSkillCard', arguments: [skill.name] }`.

**Sub-tareas**:

1. Crear tipo y diccionario de fallback:
   ```typescript
   export interface SkillCardContent {
     name: string;
     whatItDoes: string;        // 1 línea
     whenToUse: string[];       // 2-3 bullets
     command: string;           // ej "/prd <feature_name>"
     example: string;           // 1-2 líneas
     source: 'skill-md' | 'defaults';
   }
   ```

2. Implementar `skill-defaults.ts` — diccionario con los 25 skills (lookup por name → SkillCardContent sin `name` ni `source`). Contenido en EN (decisión del PRD).

3. Implementar `buildSkillCardContent(skill: SkillInfo): SkillCardContent`:
   - Si `skill.hasFrontmatter` y el frontmatter tiene `description` parseable como cuatro bloques → usar SKILL.md (source='skill-md').
   - Si no → fallback a defaults (source='defaults').
   - Si tampoco hay defaults → contenido placeholder `"(no description available)"`.

4. Implementar `buildSkillCardItems(content: SkillCardContent): QuickPickItem[]`:
   - Pura, sin side effects. Devuelve los 6 items descritos en el análisis UI.

5. Implementar `showSkillCard(skillName: string)`:
   - Buscar el `SkillInfo` correspondiente (cache compartida con el provider).
   - Construir contenido + items.
   - Crear `QuickPick` con `vscode.window.createQuickPick()`.
   - `quickPick.items = items` (read-only, sin selección).
   - Listener `onDidTriggerItemButton` → si el botón es el de copy, llamar `vscode.env.clipboard.writeText(content.command)` + toast "Comando copiado — pega en el chat de Claude Code" + cerrar QuickPick.
   - Listener `onDidHide` → dispose.

6. Registrar comando en `extension.ts`:
   ```typescript
   vscode.commands.registerCommand('specbox.showSkillCard', async (skillName: string) => {
     await showSkillCard(skillName);
   });
   ```

7. Declarar comando en `package.json`:
   ```json
   {
     "command": "specbox.showSkillCard",
     "title": "%command.showSkillCard.title%"
   }
   ```
   + entradas correspondientes en `package.nls.json` (EN) y `package.nls.es.json` (ES — solo el title, no el contenido de las fichas).

8. Asociar el click en `SkillItem`:
   - En `skills-tree.ts`, el item gana:
     ```typescript
     this.command = {
       command: 'specbox.showSkillCard',
       arguments: [skill.name],
       title: vscode.l10n.t('Show skill card'),
     };
     ```

**Mapeo AC**:
- AC-10 → sub-tareas 4-6
- AC-11 → sub-tarea 3 (source labeled en el último item del QuickPick)
- AC-12 → item de "Command" con `buttons: [ThemeIcon('copy')]`
- AC-13 → listener `onDidTriggerItemButton` con `clipboard.writeText` + `showInformationMessage`
- AC-14 → `onDidHide → dispose` + `command` permite reentrada
- AC-15 → validación manual de 5 ejemplos (parte del smoke de F5)

**Verificación local rápida**:
```bash
cd vscode-extension && npm run compile
# Click en /prd → debe abrirse el QuickPick con 4 bloques
# Click en el icono copy del bloque Command → toast aparece y comando va al portapapeles
```

### Fase 4: UC-704 — Walkthrough actualizado + tooltip rico (3h)

**Objetivo**: walkthrough deja de hardcodear "15 skills", gana un 5º paso que apunta al sidebar; cada item del TreeView gana tooltip rico.

**Archivos a crear/modificar**:

- ✏️ `vscode-extension/media/walkthrough/step-install.md` — eliminar "Install 15 skills" → "Install all SpecBox skills and hooks".
- 🆕 `vscode-extension/media/walkthrough/step-discover-skills.md` — nuevo markdown con el tour del sidebar.
- ✏️ `vscode-extension/package.json` — añadir `step-discover-skills` al array `walkthroughs[0].steps`.
- ✏️ `vscode-extension/package.nls.json` y `.es.json` — `walkthrough.step.discoverSkills.title` strings.
- ✏️ `vscode-extension/src/views/skills-tree.ts` — `SkillItem.tooltip` pasa de string a `MarkdownString`.

**Sub-tareas**:

1. Reescribir `step-install.md`. La descripción del step en `package.json` ya dice "Install 15 skills, 20+ hooks, and quality settings" — actualizar también esa descripción a "Install all SpecBox skills, 20+ hooks, and quality settings".

2. Crear `step-discover-skills.md` con copy en EN:
   ```markdown
   # Explore your new skills

   SpecBox installed N agentic skills (commands like /prd, /plan, /implement) and 20+ hooks that enforce quality automatically.

   Open the **SpecBox** activity bar on the left, expand a category (Pipeline, Quality, Visual...), and click any skill to see what it does, when to use it, the exact slash command to type in Claude Code, and a realistic example.
   ```

3. Declarar el nuevo step en `package.json` con su command link:
   ```json
   {
     "id": "specbox.step.discoverSkills",
     "title": "%walkthrough.step.discoverSkills.title%",
     "description": "Open the SpecBox activity bar to discover all available agentic skills.\n\n[Open SpecBox sidebar](command:workbench.view.extension.specbox)",
     "media": { "markdown": "media/walkthrough/step-discover-skills.md" }
   }
   ```

4. Añadir strings i18n:
   - `package.nls.json`: `"walkthrough.step.discoverSkills.title": "Explore your skills"`.
   - `package.nls.es.json`: `"walkthrough.step.discoverSkills.title": "Explora tus skills"`.

5. Modificar `SkillItem.tooltip`:
   - Construir `vscode.MarkdownString` con `**${skill.name}** — ${skill.description}` (primera frase, ≤120 chars).
   - Soportar `MarkdownString.isTrusted = false` (no necesitamos command links en el tooltip).

**Mapeo AC**:
- AC-16 → sub-tarea 1 (tanto markdown como description en package.json)
- AC-17 → sub-tareas 2 + 3
- AC-18 → sub-tarea 5
- AC-19 → sub-tareas 3 + 4

**Verificación local rápida**:
```bash
cd vscode-extension && npm run compile
# Help > Welcome → debe verse el step "Explore your skills"
# Hover sobre cualquier skill del sidebar → tooltip con la primera frase de "qué hace"
```

### Fase 5: UC-705 — Tests + smoke manual + bump versión (6h)

**Objetivo**: cierre de la US — tests `node:test` zero-deps para la lógica pura, smoke manual del reviewer, bump 6.5.0→6.6.0.

**Archivos a crear/modificar**:

- 🆕 `vscode-extension/tests/skill-loader.test.mjs`
- 🆕 `vscode-extension/tests/skill-categories.test.mjs`
- 🆕 `vscode-extension/tests/skill-card.test.mjs`
- ✏️ `vscode-extension/package.json` — bump 6.3.0 → 6.6.0
- ✏️ `vscode-extension/CHANGELOG.md` — sección [6.6.0]
- ✏️ `ENGINE_VERSION.yaml` — bump 6.5.0 → 6.6.0
- ✏️ `CLAUDE.md` — sección "VSCode Discoverability (v6.6.0)"
- ✏️ `CHANGELOG.md` — root del repo, sección [6.6.0]

**Sub-tareas**:

1. **`tests/skill-loader.test.mjs`** (cubre AC-20 a-c y partial d):
   - Setup: dos directorios mock en `os.tmpdir()` con SKILL.md sintéticos.
   - Test 1: `loadSkillsFromFilesystem([dirA])` lee N skills correctamente.
   - Test 2: `loadSkillsFromFilesystem([dirLocal, dirGlobal])` con mismo skill en ambos → solo aparece el local.
   - Test 3: `loadSkillsFromFilesystem(['/path/que/no/existe'])` no lanza, devuelve `[]`.
   - Test 4: SKILL.md con frontmatter mal formado → entry con `hasFrontmatter=false`.
   - Test 5: `parseSkillFrontmatter("---\nname: foo\ndescription: bar\n---\n...")` parsea correctamente.

2. **`tests/skill-categories.test.mjs`** (cubre AC-20 e + AC-09):
   - Test 1: `getCategoryFor('prd')` === `'pipeline'`.
   - Test 2: `getCategoryFor('skill-inexistente')` === `'other'`.
   - Test 3: para los 25 skills del PRD, validar que ninguno cae en `'other'` (drift detector).
   - Test 4: `CATEGORY_ORDER.length === 7` y contiene `'other'` al final.

3. **`tests/skill-card.test.mjs`** (cubre AC-21):
   - Test 1: `buildSkillCardContent(skillConFrontmatter)` devuelve `source: 'skill-md'`.
   - Test 2: `buildSkillCardContent(skillSinFrontmatter)` con name en defaults → `source: 'defaults'`.
   - Test 3: `buildSkillCardContent(skillDesconocidoSinDefaults)` → contenido placeholder, no lanza.
   - Test 4: `buildSkillCardItems(content)` devuelve exactamente 6 items (4 bloques + separator + source).
   - Test 5: el item "Command" tiene exactamente 1 entry en `buttons[]`.

4. Bump de versión y CHANGELOG:
   - `vscode-extension/package.json`: `"version": "6.3.0"` → `"6.6.0"`.
   - `vscode-extension/CHANGELOG.md`: nueva sección al principio:
     ```markdown
     ## [6.6.0] — "Discoverability"

     ### Added
     - Sidebar `specbox.skills` now auto-detects installed skills from filesystem...
     - Skill card opened via click on any skill item...
     - New walkthrough step "Explore your skills"...
     ### Changed
     - `getInstalledSkills()` now reads filesystem directly...
     ### Removed
     - `CORE_SKILLS` hardcoded array (replaced by dynamic loader + `KNOWN_SKILLS` categorization map).
     ```
   - `ENGINE_VERSION.yaml`: bump y codename:
     ```yaml
     version: 6.6.0
     codename: "VSCode Discoverability"
     ```
   - `CHANGELOG.md` root: análogo.
   - `CLAUDE.md`: nueva sección "## VSCode Discoverability (v6.6.0)" documentando el sidebar mejorado + referencia al PRD.

5. **AC-22 (suite verde sin regresión)**:
   - Ejecutar `npm test` en `vscode-extension/`. Antes del cierre de F5 todos los tests previos (oauth, oauth-integration) + los 3 nuevos archivos verdes.

6. **AC-25 (smoke manual del reviewer)**:
   - Compilar VSIX con `npm run compile && npx vsce package` (ya está en `package.json:scripts.package`).
   - Instalar VSIX en una instancia limpia de VSCode (`code --install-extension specbox-engine-6.6.0.vsix`).
   - Reviewer (JPS) verifica los 4 puntos del AC-25 y deja el veredicto como comentario del PR antes del merge.

**Mapeo AC**:
- AC-20 → sub-tarea 1 (5 tests cubren a-e)
- AC-21 → sub-tarea 3 (5 tests cubren a-c + 2 extras)
- AC-22 → sub-tarea 5
- AC-23 → sub-tarea 4 (parte extensión)
- AC-24 → sub-tarea 4 (parte engine)
- AC-25 → sub-tarea 6

---

## Fase 6: Integración + Quality Gates (transversal)

No es una fase nueva — se ejecutan dentro de `/implement` automáticamente, pero las documento aquí para que el plan sea autocontenido.

- **AG-08 Quality Audit**: tras cada fase, `quality-first-guard` + `pre-commit-lint` + `pipeline-phase-guard` validan el commit.
- **AG-09a Acceptance Tester**: para los UCs con AC funcionales (UC-701..704), genera/ejecuta los tests `node:test` añadidos en F5.
- **AG-09b Acceptance Validator**: verifica que cada AC tiene evidencia. AC-25 (smoke manual) queda en estado `qualitative_gate_passed` solo tras el comentario del reviewer humano.
- **`/implement` paso 8.5 (merge secuencial)**: NO auto-merge esta US — el usuario pidió review humano antes del merge (Opción A). El paso 8.5 se ejecuta hasta el `gh pr create`; el merge queda explícitamente diferido.

---

## Comandos Finales

Al cerrar la US (después de F5):

```bash
cd vscode-extension
npm run compile         # tsc -p ./
npm test                # oauth + oauth-integration + skill-loader + skill-categories + skill-card
npx vsce package        # genera specbox-engine-6.6.0.vsix
# Smoke manual del reviewer
# Una vez verde + smoke OK:
# Commit + push a feature/us-vscode-discoverability
# PR a main
# Tras review humano + merge:
git tag -a v6.6.0 -m "v6.6.0 — VSCode Discoverability"
git push origin v6.6.0
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|---|---|---|---|
| Ficha de skill | QuickPick con `detail` + button | WebviewPanel con HTML custom | Cero riesgo de churn visual con theme; accesibilidad y disposal automáticos; mantenimiento más simple |
| Fuente de descripciones | Frontmatter SKILL.md + fallback estático | Solo SKILL.md (sin fallback) | Los SKILL.md actuales no tienen estructura "qué/cuándo/comando/ejemplo" — el fallback estático garantiza UX consistente desde día 1 |
| Categorización | Mapa estático `SKILL_TO_CATEGORY` | Frontmatter `category:` en cada SKILL.md | Más simple, single source of truth en la extensión, no requiere mantener 25 SKILL.md sincronizados |
| Skills no mapeados | Caen en categoría "Other" | Bloquear / warning | Forward-compat: skills nuevos de releases futuros aparecen sin requerir update inmediato del mapping |
| Click en skill | Abre ficha de ayuda | Ejecuta el slash command | Decisión cerrada en discovery — la API de Claude Code no expone invocación pública y la UX de "fachada" mata adopción si el click parece prometer algo que no entrega |
| i18n | Solo strings UI (labels, titles, tooltips); contenido de fichas en EN | Traducir también el contenido de las fichas | Coste alto vs valor — EN es default en VSCode y los slash commands son universales; ES para fichas se difiere a US futura si hay demanda |
| Tests | `node:test` zero-deps sobre lógica pura | Vitest / Jest | Consistente con el patrón actual de `tests/oauth.test.mjs`; cero deps nuevas en el bundle |

---

## Archivos a Crear/Modificar

```
vscode-extension/
├── src/
│   ├── constants.ts                          # ✏️ CORE_SKILLS → KNOWN_SKILLS o eliminar
│   ├── install.ts                            # ✏️ getInstalledSkills() lee del FS
│   ├── extension.ts                          # ✏️ workspace folders al provider + comando showSkillCard
│   └── views/
│       ├── skills-tree.ts                    # ✏️ refactor mayor: loader + categorías + click
│       ├── skill-loader.ts                   # 🆕 loadSkillsFromFilesystem + parser frontmatter
│       ├── skill-categories.ts               # 🆕 mapping + tipos + iconos + ordering
│       ├── skill-card.ts                     # 🆕 buildSkillCardContent + buildSkillCardItems + showSkillCard
│       └── skill-defaults.ts                 # 🆕 diccionario fallback con 25 skills
├── media/walkthrough/
│   ├── step-install.md                       # ✏️ eliminar "15 skills"
│   └── step-discover-skills.md               # 🆕
├── tests/
│   ├── skill-loader.test.mjs                 # 🆕
│   ├── skill-categories.test.mjs             # 🆕
│   └── skill-card.test.mjs                   # 🆕
├── package.json                              # ✏️ versión 6.6.0 + comando showSkillCard + walkthrough step
├── package.nls.json                          # ✏️ strings nuevos
├── package.nls.es.json                       # ✏️ strings nuevos en ES
└── CHANGELOG.md                              # ✏️ sección [6.6.0]

ENGINE_VERSION.yaml                            # ✏️ 6.5.0 → 6.6.0 + codename
CLAUDE.md                                      # ✏️ sección VSCode Discoverability (v6.6.0)
CHANGELOG.md                                   # ✏️ root del repo, sección [6.6.0]
```

---

## Visual Experience Generation

**Modo**: DISABLED

**Justificación**: la feature toca UI de VSCode (TreeView nativo + QuickPick nativo), no UI de producto generable por Stitch. El theme se hereda del propio VSCode (claro/oscuro automático vía `var(--vscode-*)`), no hay brand assets a generar, no hay placeholders de imagen. Pipeline VEG no aplica.

---

## Referencias

- **PRD**: [doc/prd/US-VSCODE-DISCOVERABILITY_prd.md](../prd/US-VSCODE-DISCOVERABILITY_prd.md)
- **Discovery**: [doc/discovery/vscode_discoverability_sidebar/icp_jtbd.md](../discovery/vscode_discoverability_sidebar/icp_jtbd.md)
- **Tracking**: FreeForm board `ff-ed0c02f4565a` → US-VSCODE-DISCOVERABILITY → UC-701..UC-705
- **VSCode API docs**: [TreeView](https://code.visualstudio.com/api/extension-guides/tree-view), [QuickPick](https://code.visualstudio.com/api/references/vscode-api#QuickPick), [Walkthroughs](https://code.visualstudio.com/api/references/contribution-points#contributes.walkthroughs)
- **Engram memory**: `architecture/vscode-discoverability-sidebar` topic

---

## Resumen ejecutivo

| Métrica | Valor |
|---|---|
| Fases | 5 (mapeadas 1:1 a 5 UCs) |
| Archivos nuevos | 6 (4 src + 1 walkthrough + ... 3 tests) |
| Archivos modificados | 8 |
| Líneas estimadas | ~600 src + ~300 tests + ~80 docs |
| Tiempo total estimado | 22h (24h presupuestadas con 2h buffer) |
| Riesgo técnico | Bajo — todas las APIs de VSCode usadas ya están en uso (TreeView, QuickPick, walkthrough); cero deps nuevas |
| Bloqueador conocido | Ninguno — el bloqueador histórico (API de Claude Code para invocar slash commands) quedó eliminado al decidir en discovery que el click NO ejecuta |
| Auto-merge | NO (review humano antes del merge — Opción A acordada con el usuario) |

*Generado: 2026-05-27 — autopilot agresivo*
