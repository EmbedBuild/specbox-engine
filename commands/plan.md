# /plan (Global)

Genera un plan de implementación detallado con análisis de componentes UI.

## Uso

```
/plan [origen]
```

**Orígenes soportados:**
- `MCPROFIT-42` → Work Item de Plane por identificador
- `"descripción de feature"` → Texto directo
- `feature:nombre` → Analiza feature existente en el proyecto

---

## Paso 0: Detectar Origen y Extraer Requisitos

```
¿Qué recibí?
├── PROYECTO-N (ej: "MCPROFIT-42") → Obtener PRD de Plane
├── Texto entre comillas → Tratar como mini-PRD
└── feature:nombre → Analizar código existente en lib/
```

### Si es identificador de Plane (PROYECTO-N):
1. Usar `plane:retrieve_work_item_by_identifier` con:
   - `project_identifier`: "MCPROFIT" (extraer del identificador)
   - `issue_identifier`: 42 (número extraído)
2. Extraer descripción del work item (contiene el PRD)
3. Parsear secciones: Funcionalidades, Interacciones UI, Criterios

### Si es texto directo:
1. Generar PRD mínimo internamente:
   - Inferir funcionalidades del texto
   - Preguntar datos faltantes para sección UI si es ambiguo
2. Continuar con el flujo

### Si es feature existente:
1. Buscar en `lib/presentation/features/{nombre}/`
2. Analizar código para extraer: modelos, estados, widgets
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
Consultar: .claude/skills/adapt-ui/SKILL.md
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
> Origen: [MCPROFIT-N / texto / feature]
> Estado: 🟡 Pendiente

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

## Paso 6: Generar Diseños en Google Stitch (AUTOMÁTICO via MCP)

> Esta sección genera diseños HTML automáticamente usando el MCP de Stitch.
> **NO se copia/pega manualmente** — Claude ejecuta la generación directamente.

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

[Descripción detallada de qué muestra la pantalla, qué elementos tiene,
qué acciones puede hacer el usuario, qué datos se muestran]

Components:
- [Lista de componentes del análisis UI]

States to show:
- Loaded state with sample data
- Empty state with illustration + CTA
- [Loading state if complex]

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

## Paso 7: Actualizar Work Item en Plane (Opcional)

Si el origen fue un identificador de Plane, actualizar el work item con:

1. Añadir link al plan generado en comentario
2. Cambiar estado a "To-Do" si estaba en "Backlog"

Usar `plane:create_work_item_comment`:
```json
{
  "project_id": "[projectId]",
  "work_item_id": "[workItemId]",
  "comment_html": "📋 Plan generado: `doc/plans/[nombre]_plan.md`"
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

### Diseños Stitch:
| Pantalla | Screen ID | Estado |
|----------|-----------|--------|
| [nombre] | [id] | ✅ Generado |
| [nombre] | [id] | ✅ Generado |

**HTMLs guardados en**: `doc/design/[feature]/`
**Prompts registrados en**: `doc/design/[feature]/[feature]_stitch_prompts.md`

### Siguiente paso:
1. Revisar diseños HTML generados
2. Ejecutar `/design-to-code [feature]`
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
- [ ] Pantallas Stitch generadas via MCP (si aplica UI)
- [ ] HTMLs guardados en `doc/design/{feature}/`
- [ ] Prompts de Stitch registrados para trazabilidad

---

## Referencia MCP Plane

### Herramientas principales:
- `plane:list_projects` - Listar proyectos del workspace
- `plane:retrieve_work_item_by_identifier` - Obtener work item por identificador (ej: MCPROFIT-42)
- `plane:retrieve_work_item` - Obtener work item por UUID
- `plane:update_work_item` - Actualizar work item
- `plane:create_work_item_comment` - Añadir comentario a work item
- `plane:list_states` - Listar estados de un proyecto

### Formato de identificador:
- `MCPROFIT-42` → project_identifier: "MCPROFIT", issue_identifier: 42
- El número se extrae parseando el identificador
