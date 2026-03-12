---
name: implementation-plan
description: >
  Generate technical implementation plans with UI component analysis,
  agent mapping, and Stitch design generation. Use when the user says
  "plan feature", "create plan", "technical plan", "analyze for implementation",
  or references planning before coding. Reads PRDs from Plane/Trello.
context: fork
agent: Plan
---

# /plan (Global)

Genera un plan de implementacion detallado con analisis de componentes UI.

## Uso

```
/plan [origen]
```

**Origenes soportados:**
- `US-XX` → User Story de Trello (spec-driven)
- `board:BOARD_ID` → Listar US de un board Trello para elegir
- `MCPROFIT-42` → Work Item de Plane por identificador
- `"descripcion de feature"` → Texto directo
- `feature:nombre` → Analiza feature existente en el proyecto

---

## Paso 0: Detectar Origen y Extraer Requisitos

```
Que recibi?
├── US-XX (ej: "US-01") → Obtener datos de Trello
├── board:BOARD_ID → Listar US del board, elegir una
├── PROYECTO-N (ej: "MCPROFIT-42") → Obtener PRD de Plane
├── Texto entre comillas → Tratar como mini-PRD
└── feature:nombre → Analizar codigo existente en lib/
```

### Si es US-XX (Trello spec-driven):
1. Obtener board_id de `.claude/settings.local.json` → `trello.boardId`
2. Llamar `get_us(board_id, us_id)` via MCP dev-engine-trello
3. Llamar `list_uc(board_id, us_id)` para obtener todos los UCs hijos
4. Para cada UC: `get_uc(board_id, uc_id)` para detalle completo (ACs, pantallas, actor)
5. Buscar PRD adjunto: `get_evidence(board_id, us_id, "us", "prd")`
6. Si hay PRD adjunto → parsear secciones (Interacciones UI, NFRs, Riesgos)
7. Si no hay PRD → usar datos directos de Trello (nombre, descripcion, UCs, ACs)

**Datos disponibles desde Trello:**
- US: nombre, descripcion, horas, pantallas, estado
- UCs: nombre, actor, horas, pantallas, ACs con estado
- Evidencia: PDFs adjuntos (PRD, plans anteriores)

### Si es identificador de Plane (PROYECTO-N):
1. Usar `plane:retrieve_work_item_by_identifier` con:
   - `project_identifier`: "MCPROFIT" (extraer del identificador)
   - `issue_identifier`: 42 (numero extraido)
2. Extraer descripcion del work item (contiene el PRD)
3. Parsear secciones: User Stories, Use Cases, Interacciones UI, Criterios

### Si es texto directo:
1. Generar PRD minimo internamente:
   - Inferir funcionalidades del texto
   - Preguntar datos faltantes para seccion UI si es ambiguo
2. Continuar con el flujo

### Si es feature existente:
1. Buscar en `lib/presentation/features/{nombre}/`
2. Analizar codigo para extraer: modelos, estados, widgets
3. Identificar gaps o mejoras posibles

---

## Paso 1: Explorar Proyecto

### Detectar estructura
```bash
# Buscar configuración Claude
ls -la .claude/ 2>/dev/null

# Detectar stack
cat pubspec.yaml 2>/dev/null | grep -E "flutter:|dependencies:"  # Flutter
cat package.json 2>/dev/null | grep -E "react|next"              # React/Node
cat pyproject.toml 2>/dev/null | grep -E "fastapi|django"        # Python
ls .clasp.json appsscript.json 2>/dev/null                       # Google Apps Script

# Encontrar biblioteca de widgets/componentes
find lib -type d -name "widgets" 2>/dev/null                      # Flutter
find src -type d -name "components" 2>/dev/null                   # React
find src -type d \( -name "html" -o -name "ui" \) 2>/dev/null    # Apps Script
```

### Mapeo de estructura detectada

| Detectado | Acción |
|-----------|--------|
| `.claude/orchestrator.md` | Usar agentes del proyecto |
| `.claude/agents/` | Mapear tareas a agentes específicos |
| `lib/core/widgets/` | Usar como biblioteca de componentes (Flutter) |
| `lib/presentation/shared/widgets/` | Alternativa de biblioteca (Flutter) |
| `src/components/` | Biblioteca de componentes (React) |
| `.clasp.json` + `src/html/` | Proyecto Apps Script con clasp |
| Ninguna biblioteca | Proponer crear según stack detectado |

---

## Paso 2: Análisis de Componentes UI (OBLIGATORIO)

> Esta fase se ejecuta SIEMPRE, independiente del origen

### 2.1 Leer skill de decisiones UI

```
Consultar: .claude/skills/adapt-ui/SKILL.md (seccion de criterios UI)
Si no existe: Usar criterios embebidos (ver Anexo A)
```

### 2.2 Extraer requisitos UI del PRD

Del PRD (o texto), identificar:

| Categoría | Qué buscar | Archivo de referencia |
|-----------|------------|----------------------|
| Navegación | Secciones, tabs, flujos | navigation.md |
| Visualización | Listas, tablas, cards, volúmenes | data-display.md |
| Selección | Filtros, opciones, dropdowns | selection.md |
| Entrada | Formularios, campos, validación | data-entry.md |
| Feedback | Confirmaciones, errores, loading | feedback.md |
| Acciones | Botones, FAB, swipe actions | actions.md |

### 2.3 Aplicar árboles de decisión

Para cada requisito funcional:

```
Requisito: "Mostrar lista de propiedades con acciones"
    ↓
Volumen: 20-100 items
Acciones por item: ver, editar, eliminar
Visual importante: Sí (thumbnail)
    ↓
Decisión: Cards con actions (no lista simple)
    ↓
Widget: PropertyCard
```

### 2.4 Buscar en biblioteca existente

```bash
# Buscar widgets existentes
find lib/core/widgets lib/presentation/shared/widgets -name "*.dart" 2>/dev/null
```

### 2.5 Generar tabla de componentes

```markdown
## Componentes UI Requeridos

| Requisito | Componente | Existe | Ubicación | Acción |
|-----------|------------|--------|-----------|--------|
| Lista de propiedades | PropertyCard | ✅ | core/widgets/cards/ | Reutilizar |
| Filtro por tipo | FilterDropdown | ❌ | - | CREAR |
| Confirmación eliminar | ConfirmDialog | ✅ | core/widgets/feedback/ | Reutilizar |
| Empty state | EmptyStateView | ❌ | - | CREAR |

### Widgets a Crear

1. **FilterDropdown** (`lib/core/widgets/inputs/filter_dropdown.dart`)
   - Props: options, selected, onChanged
   - Criterio: 5-7 opciones, selección única, uso frecuente

2. **EmptyStateView** (`lib/core/widgets/feedback/empty_state_view.dart`)
   - Props: icon, title, subtitle, action
   - Criterio: Estado inicial, guiar al usuario
```

---

## Paso 2.5b: Visual Experience Generation (VEG)

> Este paso genera artefactos VEG que condicionan los diseños Stitch y el design-to-code.
> Se ejecuta SOLO si el PRD tiene seccion "Audiencia" con al menos 1 target.
> Si no hay targets → saltar a Paso 3 (pipeline legacy, backward compatible).

### 2.5b.1 Determinar modo VEG

Leer la seccion "Audiencia" del PRD y decidir:

```
Hay ICPs con JTBD definidos para landings?
├── SI → Modo 3: VEG por ICP + JTBD
│   └── Generar 1 VEG por ICP
├── NO → Hay multiples targets con expectativas visuales distintas?
│   ├── SI → Modo 2: VEG por Perfil
│   │   └── Generar 1 VEG por target
│   └── NO → Hay al menos 1 target definido?
│       ├── SI → Modo 1: VEG Uniforme
│       │   └── Generar 1 VEG unico
│       └── NO → Sin VEG (pipeline legacy)
```

### 2.5b.2 Generar VEG(s)

Para cada VEG a generar:

1. Tomar el perfil del target/ICP como entrada
2. Cruzar con:
   - Tipo de producto (SaaS, e-commerce, app interna, landing...)
   - Stack del proyecto (Flutter = flutter_animate, React = motion)
   - Branding del proyecto (si existe en settings o design system)
   - Plataforma (mobile-first vs desktop-first)
3. Consultar tabla de arquetipos en `doc/templates/veg-archetypes.md`
4. Identificar el arquetipo base mas cercano por senales del target
5. Aplicar defaults del arquetipo
6. Si hay JTBD emocional: evaluar si contradice algun pilar y ajustar (max 2 cambios)
7. Si hay referentes visuales: cruzar con defaults y ajustar mood/type si difieren
8. Generar prompts de imagen contextualizados:
   - Combinar: mood del pilar 1 + tipo de imagen + contexto del producto + JTBD
   - Ejemplo: Target "CTO enterprise" + producto "analytics SaaS" + JTBD emocional "sentirse en control"
     → Hero prompt: "Professional executive reviewing holographic data dashboard,
       blue ambient lighting, modern office, photorealistic, cinematic composition,
       sense of control and clarity"

9. Guardar en `doc/veg/{feature}/veg-{slug}.md` usando template de `doc/templates/veg-template.md`

### 2.5b.3 Preview y confirmacion del VEG

**OBLIGATORIO**: Presentar al usuario un resumen del VEG derivado antes de continuar.

```
📋 VEG Preview — {feature}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Modo: {1-Uniforme / 2-Por Perfil / 3-Por ICP}
Target: {nombre del target/ICP}
Arquetipo base: {Corporate / Startup / Creative / Consumer / Gen-Z / Gobierno}

Pilar 1 — Imagenes:
  Tipo: {photography / illustration_flat / illustration_3d / mixed}
  Mood: {professional / energy / premium / confidence / playful / calm}
  Paleta: {cool / vibrant / muted / warm / neutral}

Pilar 2 — Motion:
  Nivel: {subtle / moderate / expressive}
  Page enter: {animation} {duration}ms
  Loading: {style}

Pilar 3 — Diseno:
  Densidad: {compact / balanced / spacious}
  Whitespace: {tight / moderate / generous}
  Jerarquia: {card-based / full-bleed / editorial / dashboard}
  CTA: {subtle / medium / high}

⚠️ Costes de imagenes (Paso 3.5 de /implement):
  Las imagenes se generan via MCP de pago. Coste estimado:
  {N} imagenes × $0.02-0.19 = ${min}-${max} (segun provider)
  Puedes elegir "skip" en /implement para solo documentar prompts.

¿El VEG derivado es correcto? (s/n/ajustar)
  s = continuar con este VEG
  n = descartar VEG, usar pipeline legacy
  ajustar = indicar que cambiar (ej: "cambiar motion a subtle", "usar photography en vez de illustration")
```

Si el usuario dice `ajustar`:
1. Aplicar los cambios indicados al VEG
2. Mostrar preview actualizado
3. Repetir hasta confirmacion

Si el usuario dice `n`:
1. Descartar VEG generado
2. Continuar con pipeline legacy (sin VEG)
3. No generar archivos en `doc/veg/`

### 2.5b.4 Incluir VEG en el output del plan

Anadir seccion al plan generado:

```markdown
## Visual Experience Generation

**Modo**: {1-Uniforme / 2-Por Perfil / 3-Por ICP}
**Justificacion**: {por que este modo}

### VEGs Generados

| Target/ICP | Archivo | Modo |
|------------|---------|------|
| {nombre} | doc/veg/{feature}/veg-{slug}.md | {modo} |

### VEG Activo para Stitch
{Indicar cual VEG se usara para la generacion Stitch.
En Modo 1: el unico. En Modo 2/3: el del target principal o todos si se generan variantes.}

### Resumen VEG Compacto (para sub-agentes)

> Este bloque (~400 tokens) se inyecta en el contexto de AG-02 y AG-06.

{Pegar el bloque "Resumen para inyeccion" del VEG activo}
```

---

## Paso 3: Detectar Agentes/Skills Disponibles

### Si existe `.claude/orchestrator.md`:

Leer y mapear agentes:

| Agente | Tareas que puede ejecutar |
|--------|--------------------------|
| AG-01 Feature Generator | Estructura, modelos, BLoC, routes |
| AG-02 UI/Design | Widgets, estilos, layouts |
| AG-03 Supabase | DB, queries, RLS |
| AG-04 QA | Tests, validación |
| AG-05 n8n | Workflows, automatizaciones |
| AG-07 Apps Script | Scripts GAS, clasp, triggers, Web Apps |

### Si NO existe orquestador:

Generar plan sin referencias a agentes (tareas genéricas)

---

## Paso 4: Generar Plan de Implementación

### Template de Plan

```markdown
# Plan: [Título del PRD]

> Generado: [fecha]
> Origen: [US-XX (Trello) / MCPROFIT-N (Plane) / texto / feature]
> Estado: Pendiente

---

## Resumen

[1-2 oraciones del objetivo]

## Análisis UI (Fase 0)

### Componentes Requeridos

| Requisito | Componente | Estado | Acción |
|-----------|------------|--------|--------|
| [req] | [widget] | ✅/❌ | Reutilizar/CREAR |

### Widgets a Crear

[Lista con specs básicas]

---

## Fases de Implementación

### Fase 1: Preparación [AG-03 si existe]

- [ ] Verificar/crear tablas en DB
- [ ] Configurar índices y RLS
- [ ] Tiempo estimado: X min

### Fase 2: Componentes UI [AG-02 si existe]

- [ ] Crear widgets faltantes en `lib/core/widgets/`
- [ ] [Lista de widgets a crear]
- [ ] Tiempo estimado: X min

### Fase 3: Feature Structure [AG-01 si existe]

- [ ] Modelo con Freezed
- [ ] Repository contract + impl
- [ ] BLoC + Events + States
- [ ] Page + Layouts responsivos
- [ ] Routes con GoRouteData
- [ ] Tiempo estimado: X min

### Fase 4: Integración

- [ ] Registrar en DI
- [ ] Añadir rutas
- [ ] build_runner
- [ ] dart fix --apply
- [ ] Tiempo estimado: X min

### Fase 5: QA [AG-04 si existe]

- [ ] Tests unitarios BLoC
- [ ] Tests de repository
- [ ] Widget tests
- [ ] Coverage 85%+
- [ ] Tiempo estimado: X min

---

## Comandos Finales

```bash
dart run build_runner build --delete-conflicting-outputs
dart fix --apply && dart analyze
flutter test --coverage
```

---

## Alternativas y Tradeoffs

| Decision | Opcion elegida | Alternativa descartada | Razon |
|----------|---------------|----------------------|-------|
| [ej: State mgmt] | [BLoC] | [Riverpod] | [Consistencia con proyecto] |
| [ej: Navegacion] | [GoRouter] | [Auto Route] | [Ya integrado] |

---

## Archivos a Crear/Modificar

```
lib/
├── core/widgets/           # Nuevos widgets compartidos
│   └── [widgets nuevos]
├── data/
│   ├── models/[feature]_model.dart
│   └── repositories/[feature]_repository_impl.dart
├── domain/
│   └── repositories/[feature]_repository.dart
└── presentation/features/[feature]/
    ├── bloc/
    ├── page/
    ├── layouts/
    ├── widgets/
    └── routes/
```

---

## Referencias

- PRD: [link al work item en Plane]
- UI Patterns: `doc/ui-reference/UI_PATTERNS.md` (si existe)
- Skill UI: `.claude/skills/adapt-ui/`
```

---

## Paso 5: Guardar Plan

1. Crear archivo: `doc/plans/[nombre]_plan.md`
2. Si no existe `doc/plans/`: crearlo
3. Confirmar al usuario

---

## Paso 6: Generar Diseños en Google Stitch (OBLIGATORIO via MCP)

> Esta sección genera diseños HTML automáticamente usando el MCP de Stitch.
> **NO se copia/pega manualmente** — Claude ejecuta la generación directamente.
> **OBLIGATORIO**: Si el UC/plan tiene pantallas, los diseños DEBEN generarse aquí.
> /implement bloqueará la implementación si no existen diseños (Paso 0.5d).

### 6.0a Stitch Config Gate (OBLIGATORIO si hay pantallas)

```
¿El plan tiene pantallas/screens definidos?
├── NO → Saltar Paso 6 completamente (UC sin UI)
└── SI → Verificar config Stitch:
    │
    ¿Existe stitch.projectId en configuración?
    ├── SI → Continuar con 6.0 (detección normal)
    └── NO → PREGUNTAR al usuario (NUNCA saltar silenciosamente):
        "El plan requiere {N} pantallas pero no hay config Stitch.
         Opciones:
         a) Configurar Stitch ahora (necesito projectId)
         b) Marcar diseños como PENDING (bloquea /implement)
         c) Generar diseños manualmente en doc/design/{feature}/

         ¿Qué prefieres?"
        │
        ├── a) → Obtener projectId → Continuar con 6.0
        ├── b) → Registrar en plan: stitch_designs: PENDING
        │        Crear doc/design/{feature}/ vacío
        │        Continuar sin generar
        └── c) → Registrar en plan: stitch_designs: MANUAL
                 Crear doc/design/{feature}/ vacío
                 Continuar sin generar
```

### 6.0 Detectar Proyecto Stitch

1. Buscar `stitch.projectId` en `.claude/settings.local.json` del proyecto
2. Si no existe, buscar en `~/.claude/settings.local.json` (global)
3. Si no se encuentra → preguntar al usuario o usar `mcp__stitch__list_projects`

**Configuración en settings:**
```json
{
  "stitch": {
    "projectId": "10448117637612065749",
    "deviceType": "DESKTOP",
    "modelId": "GEMINI_3_PRO"
  }
}
```

### 6.1 Determinar pantallas a generar

Del análisis del PRD (Paso 2), identificar las pantallas únicas necesarias.

**Regla de decisión:**

| Situación | ¿Generar en Stitch? |
|-----------|:-------------------:|
| Feature con pantallas nuevas | Si |
| Feature solo backend/lógica | No (saltar Paso 6) |
| Modificación menor de UI existente | No |
| Nuevo flujo o experiencia de usuario | Si |

Para cada pantalla, definir:
- **Nombre**: Título descriptivo (ej: "Staff Management - Main View")
- **Prompt**: Descripción detallada para Stitch
- **Device**: DESKTOP o MOBILE (según proyecto)

### 6.2 Construir prompts por pantalla

> ⚠️ **IMPORTANTE:** SIEMPRE generar prompts en **LIGHT MODE**. NO usar dark mode.

Cada prompt DEBE incluir:

1. **Contexto del Design System** (colores, tipografía, estilos del proyecto)
2. **Descripción funcional** de la pantalla
3. **Componentes requeridos** (del análisis UI del Paso 2)
4. **Estados** (loaded, empty, loading, error)
5. **Layout** (desktop-first o mobile-first)
6. **Iconos** (Material Symbols)

**Template de prompt por pantalla:**

```
Design a [screen description] for [App Name].

Design System:
- Theme: Light Mode
- Background: #F5F5F5 (page), #FFFFFF (cards)
- Primary: [color primario del proyecto]
- Text: #1F2937 (primary), #6B7280 (secondary)
- Borders: #E5E7EB, radius 12px
- Font: [font del proyecto] / Inter / system-ui
- Shadows: subtle shadow-sm on cards

Screen: [Nombre de la pantalla]

[Descripcion detallada de que muestra la pantalla, que elementos tiene,
que acciones puede hacer el usuario, que datos se muestran]

Components:
- [Lista de componentes del analisis UI]

States to show:
- Loaded state with sample data
- Empty state with illustration + CTA
- [Loading state if complex]

Layout: Desktop (1280px wide)
Icons: Material Symbols
```

**Si hay VEG activo (Paso 2.5b), ENRIQUECER el prompt con directivas visuales:**

```
Design a [screen description] for [App Name].

Design System:
- Theme: Light Mode
- [colores, tipografia del proyecto]

Visual Direction (from VEG - {target_name}):
- Density: {density}, Whitespace: {whitespace}
- Visual hierarchy: {style}, CTA prominence: {prominence}
- Typography: headings {weight}, body {spacing}, hero {scale}
- Section separation: {separation_style}
- Mood: {mood} — this should FEEL {JTBD emocional}
- Data presentation: {data_style}

Image Placeholders (generate with placeholder boxes):
- Hero: [{type}] {brief description of what the image should convey}
- Section 2: [{type}] {description}
- (mark each with [IMAGE: {id}] for later replacement)

Screen: [Nombre de la pantalla]
[Descripcion funcional]

Components:
- [Lista de componentes]

States to show:
- Loaded state with sample data
- Empty state with illustration + CTA

Layout: Desktop (1280px wide)
Icons: Material Symbols
```

### 6.3 Ejecutar generación en Stitch (MCP)

Para cada pantalla identificada:

```
mcp__stitch__generate_screen_from_text(
  projectId: "[stitch.projectId]",
  prompt: "[prompt construido en 6.2]",
  deviceType: "[stitch.deviceType]",    // DESKTOP por defecto
  modelId: "[stitch.modelId]"           // GEMINI_3_PRO por defecto
)
```

**Reglas de ejecución:**
- Generar UNA pantalla a la vez (la tool tarda minutos por pantalla)
- NO reintentar si falla por timeout — usar `mcp__stitch__get_screen` después
- Si `output_components` contiene sugerencias, presentarlas al usuario
- Esperar confirmación antes de generar la siguiente pantalla

### 6.4 Obtener y guardar HTML

Para cada pantalla generada:

1. Usar `mcp__stitch__get_screen` para obtener el HTML completo
2. Guardar en `doc/design/{feature}/{screen_name}.html`
3. Crear carpeta `doc/design/{feature}/` si no existe

```
mcp__stitch__get_screen(
  name: "projects/[projectId]/screens/[screenId]"
)
```

### 6.5 Registrar prompts usados

Guardar los prompts en `doc/design/{feature}/{feature}_stitch_prompts.md` para trazabilidad:

```markdown
# Stitch Prompts - {Feature Name}

> Generado automáticamente por /plan
> Proyecto Stitch: {projectId}
> Fecha: {fecha}

## Screen 1: {nombre}
**Screen ID**: {screenId}
**Prompt**:
{prompt usado}

## Screen 2: {nombre}
**Screen ID**: {screenId}
**Prompt**:
{prompt usado}
```

### 6.6 Preguntar si continuar con más pantallas

Después de cada pantalla generada, preguntar:
- "¿Quieres generar la siguiente pantalla: [nombre]?"
- "¿Quieres ajustar el prompt antes de generar?"
- "¿Saltamos el diseño y pasamos a implementación?"

---

## Paso 7: Actualizar Work Item y Adjuntar Evidencia

### Si origen es Trello (US-XX):
1. Adjuntar plan como PDF a la card US en Trello:
   ```
   attach_evidence(board_id, us_id, "us", "plan", plan_markdown)
   ```
2. Esto genera un PDF y lo sube como attachment a la card

### Si origen es Plane (PROYECTO-N):
1. Anadir link al plan generado en comentario
2. Cambiar estado a "To-Do" si estaba en "Backlog"

Usar `plane:create_work_item_comment`:
```json
{
  "project_id": "[projectId]",
  "work_item_id": "[workItemId]",
  "comment_html": "Plan generado: `doc/plans/[nombre]_plan.md`"
}
```

---

## Output Final

```
## ✅ Plan Generado

**Archivo**: `doc/plans/[nombre]_plan.md`
**Origen**: [tipo de origen]

### Resumen:
- **Fases**: [N]
- **Componentes UI analizados**: [N]
- **Widgets a crear**: [N]
- **Agentes involucrados**: [lista o "N/A"]

### Componentes UI:
| Estado | Cantidad |
|--------|----------|
| ✅ Existentes | [N] |
| ❌ A crear | [N] |

### Visual Experience Generation:
| Campo | Valor |
|-------|-------|
| Modo VEG | {1-Uniforme / 2-Por Perfil / 3-Por ICP / Desactivado} |
| VEGs generados | {N} |
| Archivos | `doc/veg/[feature]/` |

### Disenos Stitch:

**stitch_designs**: {GENERATED / PENDING / MANUAL / N/A}

| Pantalla | Screen ID | Estado | VEG aplicado |
|----------|-----------|--------|--------------|
| [nombre] | [id] | Generado | {Si/No} |
| [nombre] | [id] | Generado | {Si/No} |

**HTMLs guardados en**: `doc/design/[feature]/`
**Prompts registrados en**: `doc/design/[feature]/[feature]_stitch_prompts.md`

> Si `stitch_designs: PENDING` — /implement bloqueará la implementación hasta que
> los diseños se generen manualmente o se re-ejecute /plan con config Stitch.

### Siguiente paso:
1. Revisar disenos HTML generados
2. Ejecutar `/implement` (verificará diseños en Paso 0.5d)
```

---

## Anexo A: Criterios UI Embebidos

Si el skill `ui-component-decisions` no está disponible, usar estos criterios mínimos:

### Visualización de Datos

```
Volumen < 5 → Cards inline
Volumen 5-20 → Lista/Cards con scroll
Volumen 20-100 → Lista virtualizada o paginada
Volumen 100+ → Búsqueda obligatoria + paginación
```

### Selección

```
Opciones 2-3 → Radio buttons / Segmented control
Opciones 4-7 → Dropdown
Opciones 8+ → Autocomplete / Search
Múltiple selección → Chips / Checkboxes
```

### Acciones

```
Acción principal → FAB o botón primario prominente
Acciones secundarias → IconButtons en AppBar
Acciones por item → Trailing icons o swipe actions
Acciones destructivas → Requieren confirmación
```

### Feedback

```
Éxito/Info transitoria → SnackBar (auto-dismiss)
Error recuperable → SnackBar con action
Confirmación crítica → Dialog modal
Loading → Skeleton o CircularProgressIndicator
Empty state → Ilustración + CTA
```

---

## Checklist de Calidad

- [ ] Origen identificado correctamente
- [ ] Fase 0 (UI) ejecutada
- [ ] Tabla de componentes generada
- [ ] Widgets faltantes identificados con specs
- [ ] Fases ordenadas lógicamente
- [ ] Agentes mapeados (si existen)
- [ ] Archivo guardado en `doc/plans/`
- [ ] VEG generado si PRD tiene seccion Audiencia (Paso 2.5b)
- [ ] VEG preview mostrado al usuario y confirmado (Paso 2.5b.3)
- [ ] Costes de imagenes advertidos al usuario en preview
- [ ] VEGs guardados en `doc/veg/{feature}/` con los 3 pilares
- [ ] Resumen VEG compacto (<400 tokens) incluido en el plan
- [ ] Stitch config verificada (Paso 6.0a — si hay pantallas, NUNCA saltar silenciosamente)
- [ ] Campo `stitch_designs` incluido en el plan (GENERATED/PENDING/MANUAL/N/A)
- [ ] Pantallas Stitch generadas via MCP (si aplica UI)
- [ ] Prompts Stitch enriquecidos con VEG (si aplica)
- [ ] HTMLs guardados en `doc/design/{feature}/`
- [ ] Prompts de Stitch registrados para trazabilidad
- [ ] Seccion Alternativas/Tradeoffs incluida
- [ ] Plan adjuntado como evidencia a Trello (si spec-driven)

---

## Referencia MCP

### Trello (dev-engine-trello):
- `get_us(board_id, us_id)` — Detalle completo de US con UCs hijos
- `get_uc(board_id, uc_id)` — Detalle completo de UC con ACs
- `list_us(board_id)` — Listar todas las US del board
- `list_uc(board_id, us_id)` — Listar UCs de una US
- `get_evidence(board_id, target_id, target_type)` — Obtener evidencia adjunta
- `attach_evidence(board_id, target_id, target_type, evidence_type, markdown)` — Adjuntar PDF

### Plane — Herramientas principales:
- `plane:list_projects` - Listar proyectos del workspace
- `plane:retrieve_work_item_by_identifier` - Obtener work item por identificador (ej: MCPROFIT-42)
- `plane:retrieve_work_item` - Obtener work item por UUID
- `plane:update_work_item` - Actualizar work item
- `plane:create_work_item_comment` - Añadir comentario a work item
- `plane:list_states` - Listar estados de un proyecto

### Formato de identificador:
- `MCPROFIT-42` → project_identifier: "MCPROFIT", issue_identifier: 42
- El número se extrae parseando el identificador
