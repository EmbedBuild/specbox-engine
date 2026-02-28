---
name: prd-generator
description: >
  Generate structured Product Requirements Documents from feature descriptions.
  Use when the user says "create PRD", "new feature", "write requirements",
  "define feature", or references creating specifications for implementation.
  Supports Plane and Trello work item creation.
context: fork
agent: Plan
---

# /prd (Global)

Genera un PRD (Product Requirements Document) y crea un Work Item en Plane.

## Uso

```
/prd [título] [descripción de requerimientos]
```

---

## Paso 0: Detectar Proyecto de Plane

1. Buscar en `.claude/settings.local.json` → `plane.defaultProject`
2. Buscar en CLAUDE.md menciones a proyectos de Plane
3. Si no se encuentra → Preguntar y usar `plane:list_projects`
4. Detectar estado inicial preferido (Backlog o To-Do)

### Configuración por proyecto

El archivo `.claude/settings.local.json` puede contener:

```json
{
  "plane": {
    "defaultProject": "MCPROFIT",
    "defaultState": "Backlog",
    "projectId": "a6a688dd-03e2-4863-bcd8-c9cb64607cd3",
    "defaultAssignee": "d325686f-2d7c-491f-9e28-dffbf4e23c55"
  }
}
```

### Asignee por defecto

**OBLIGATORIO**: Todas las tareas creadas con `/prd` se asignan automáticamente a:
- **Usuario**: Jesus Perez Sanchez (jesus.perez.developer@gmail.com)
- **ID**: `d325686f-2d7c-491f-9e28-dffbf4e23c55`

---

## Paso 1: Detectar Tipo de PRD

### PRD Feature
**Detectar**: "nueva", "añadir", "crear", "implementar", "feature", "funcionalidad", "como [usuario] quiero"

### PRD Técnico (Refactor)
**Detectar**: "refactor", "simplificar", "migrar", "eliminar", "cambiar", "reorganizar"

---

## Paso 2: Recopilar Información

### Preguntas obligatorias para PRD Feature:
1. ¿Qué problema resuelve?
2. ¿Quién es el usuario objetivo?
3. ¿Qué funcionalidades principales necesita? (mínimo 3)

### Preguntas para sección UI (CRÍTICO):
Para cada funcionalidad, determinar:
- **Datos**: ¿Qué datos muestra? ¿Cuántos items típicamente?
- **Acciones**: ¿Qué puede hacer el usuario? (ver, filtrar, seleccionar, crear, editar, eliminar)
- **Frecuencia**: ¿Con qué frecuencia se usa? (diaria, ocasional, rara)
- **Criticidad**: ¿Qué pasa si el usuario se equivoca? (reversible, irreversible, costoso)

---

## Template: PRD Feature

```markdown
# PRD: [Título]

## Descripción
[1-2 párrafos: qué es y qué problema resuelve]

## Objetivo
[Una oración clara]

## Usuario Objetivo
[Rol del usuario]

---

## Funcionalidades

### F1: [Nombre funcionalidad]
- **Descripción**: [Qué hace]
- **Datos**: [Qué datos muestra/maneja]
- **Volumen**: [Cantidad típica de items: 1-5 | 5-20 | 20-100 | 100+]

### F2: [Nombre funcionalidad]
...

---

## Interacciones UI

> Esta sección alimenta el análisis de componentes en /plan

### Visualización de datos
| Dato | Volumen | Atributos visibles | Acciones por item |
|------|---------|-------------------|-------------------|
| [ej: Propiedades] | [20-100] | [nombre, dirección, precio] | [ver, editar, eliminar] |

### Acciones del usuario
| Acción | Frecuencia | Criticidad | Requiere confirmación |
|--------|------------|------------|----------------------|
| [ej: Crear propiedad] | Ocasional | Media | No |
| [ej: Eliminar propiedad] | Rara | Alta | Sí |

### Selecciones/Filtros
| Filtro | Opciones | Selección | Frecuencia |
|--------|----------|-----------|------------|
| [ej: Tipo propiedad] | [5-7] | Única | Frecuente |
| [ej: Estado] | [3-4] | Múltiple | Ocasional |

### Formularios
| Formulario | Campos | Contexto |
|------------|--------|----------|
| [ej: Nueva propiedad] | [8-12] | Modal / Página dedicada |

---

## Stack Técnico (estimado)

- **Modelo**: [Nuevo / Existente: nombre]
- **Repository**: [nombre]_repository
- **BLoC**: [nombre]_bloc
- **Páginas**: [lista]

## Archivos Principales
```
lib/
├── data/models/[nombre]_model.dart
├── domain/repositories/[nombre]_repository.dart
├── data/repositories/[nombre]_repository_impl.dart
└── presentation/features/[nombre]/
    ├── bloc/
    ├── page/
    └── widgets/
```

## Dependencias
- [Features o servicios requeridos]

---

## Criterios de Aceptación

### Funcionales
- [ ] **AC-01**: [Criterio específico y testable ligado a F1]
- [ ] **AC-02**: [Criterio específico y testable ligado a F1 o F2]
- [ ] **AC-03**: [Criterio específico y testable ligado a F2]
- [ ] **AC-04**: [Criterio específico y testable ligado a F3]

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila sin errores
- [ ] Tests con 85%+ coverage

---
**Prioridad**: [urgent/high/medium/low/none]
**Complejidad**: [Baja/Media/Alta]
*Generado: [fecha]*
```

---

## Template: PRD Técnico

```markdown
# PRD: [Título]

## Resumen Ejecutivo
[2-3 párrafos: objetivo del refactor y por qué es necesario]

---

## Objetivos
1. **[Objetivo 1]** - [Descripción]
2. **[Objetivo 2]** - [Descripción]

---

## Estado Actual vs Propuesto

### ACTUAL:
```
[Estructura actual]
```

### PROPUESTO:
```
[Nueva estructura]
```

---

## Cambios de UI (si aplica)

### Componentes a modificar
| Componente actual | Cambio | Componente nuevo |
|-------------------|--------|------------------|
| [widget_x] | Reemplazar | [widget_y] |

### Nuevas interacciones
| Interacción | Volumen | Frecuencia | Criticidad |
|-------------|---------|------------|------------|
| [descripción] | [N items] | [freq] | [nivel] |

---

## A Eliminar
- [ ] [Elemento] - [Razón]

## A Mantener
- [Elemento]

---

## Plan de Implementación (alto nivel)

### Fase 1: [Nombre]
- [Tarea]

### Fase 2: [Nombre]
- [Tarea]

### Fase 3: Cleanup
- Eliminar archivos no usados
- Validar compilación

---

## Criterios de Aceptación

### Funcionales
- [ ] **AC-01**: [Criterio específico y testable]
- [ ] **AC-02**: [Criterio específico y testable]

### Técnicos (no validados por AG-09)
- [ ] Proyecto compila sin errores
- [ ] Tests pasan

---
*Generado: [fecha]*
```

---

## Paso 2.5: Validar Calidad de Definición (BLOQUEANTE)

> Antes de crear el Work Item, validar que los acceptance criteria permiten testing automatizado.
> El Work Item NO se crea hasta que este gate pase.

### 2.5.1 Asignar ID a cada criterio

Numerar cada criterio funcional: AC-01, AC-02, AC-03...
Excluir criterios técnicos genéricos ("compila sin errores", "85% coverage") — estos NO cuentan como funcionales.

### 2.5.2 Evaluar cada criterio funcional

Para cada AC-XX, evaluar 3 métricas (0-2):

| Métrica | 0 (RECHAZAR) | 1 (ACEPTABLE) | 2 (IDEAL) |
|---------|-------------|----------------|-----------|
| **Especificidad** | Vago: "funciona bien", "gestiona datos", "el sistema debe ser robusto" | General: "mostrar lista de propiedades", "crear usuario" | Preciso: "listado paginado de 20 propiedades con foto thumbnail, nombre y precio en CLP" |
| **Medibilidad** | Subjetivo: "es rápido", "user-friendly", "buena UX" | Parcial: "carga en poco tiempo", "responde rápido" | Cuantificado: "carga inicial < 2s en 4G", "100% de campos validados inline" |
| **Testabilidad** | No verificable: "buena experiencia", "el usuario está satisfecho" | Solo manual: "el formulario valida campos" | Automatizable: "mostrar error inline rojo bajo el campo si email no contiene @ al perder foco" |

### 2.5.3 Validar cobertura funcional

- Cada Funcionalidad (F1, F2, F3...) DEBE tener al menos 1 criterio AC-XX asociado
- Si una funcionalidad no tiene criterio → RECHAZAR
- Ratio mínimo: criterios funcionales / funcionalidades ≥ 1.0

### 2.5.4 Calcular veredicto

```
SI algún criterio tiene score 0 en cualquier métrica → RECHAZAR
SI promedio general de los 3 scores < 1.5 → RECHAZAR
SI alguna funcionalidad no tiene criterio AC-XX → RECHAZAR
ELSE → APROBADO
```

### 2.5.5 Si RECHAZADO

1. Mostrar tabla de evaluación por criterio:

```
| AC-XX | Especificidad | Medibilidad | Testabilidad | Veredicto |
|-------|--------------|-------------|--------------|-----------|
| AC-01 | 2 | 1 | 2 | OK |
| AC-02 | 0 | 0 | 0 | RECHAZADO |
```

2. Para cada criterio rechazado, proponer una versión mejorada concreta
3. Preguntar: "¿Acepta las mejoras sugeridas o prefiere redactar manualmente?"
4. Aplicar correcciones y re-evaluar
5. NO crear Work Item hasta que pase
6. Máximo 3 iteraciones. Si tras 3 no pasa → pedir al usuario que defina los criterios manualmente

### 2.5.6 Si APROBADO

Continuar a Paso 3 con los AC-XX numerados incorporados al PRD.
Reportar:
```
Definition Quality Gate: APROBADO
Criterios funcionales: {N} (promedio: {score}/2.0)
Cobertura: {N} funcionalidades cubiertas de {M}
```

---

## Paso 3: Crear Work Item en Plane

### Detectar configuración del proyecto

1. Leer `.claude/settings.local.json` para obtener `plane.projectId`
2. Si no existe, usar `plane:list_projects` y preguntar al usuario
3. Obtener estados con `plane:list_states` para encontrar "Backlog" o "To-Do"
4. Obtener labels con `plane:list_labels` para asignar etiquetas apropiadas

### Crear el Work Item

Usar `plane:create_work_item`:

```json
{
  "project_id": "[projectId del settings o detectado]",
  "name": "[Título del PRD]",
  "description_html": "[PRD completo en HTML]",
  "description_stripped": "[PRD en texto plano]",
  "priority": "[urgent|high|medium|low|none]",
  "state": "[ID del estado Backlog o To-Do]",
  "labels": ["[ID de label si aplica]"],
  "assignees": ["d325686f-2d7c-491f-9e28-dffbf4e23c55"]
}
```

> **IMPORTANTE**: El campo `assignees` SIEMPRE incluye el ID de Jesus Perez (jesus.perez.developer@gmail.com)

### Mapeo de prioridades

| PRD | Plane Priority |
|-----|----------------|
| Alta | high |
| Media | medium |
| Baja | low |
| Crítica | urgent |

---

## Paso 4: Confirmar

```
## ✅ PRD Creado en Plane

**Proyecto**: [nombre del proyecto]
**Work Item**: [nombre]
**ID**: [identifier - ej: MCPROFIT-42]
**Estado**: [estado asignado]
**Prioridad**: [prioridad]

### Resumen:
- **Funcionalidades**: [N]
- **Interacciones UI documentadas**: [N]
- **Criterios de aceptación**: [N]

### Siguiente paso:
/plan MCPROFIT-[número]
```

---

## Checklist de Calidad

### PRD Feature:
- [ ] Título claro (max 60 chars)
- [ ] Descripción explica el problema
- [ ] Mínimo 3 funcionalidades
- [ ] Sección "Interacciones UI" completa
- [ ] Tabla de visualización de datos
- [ ] Tabla de acciones con frecuencia/criticidad
- [ ] Mínimo 4 criterios de aceptación funcionales con ID (AC-XX)
- [ ] Cada criterio: especificidad ≥ 1, medibilidad ≥ 1, testabilidad ≥ 1
- [ ] Cada funcionalidad (F1, F2...) tiene ≥ 1 criterio AC-XX
- [ ] Promedio de calidad de criterios ≥ 1.5/2.0
- [ ] Definition Quality Gate (Paso 2.5) aprobado

### PRD Técnico:
- [ ] Resumen ejecutivo claro
- [ ] Al menos un cambio ANTES/DESPUÉS
- [ ] Sección "Cambios de UI" si afecta interfaz
- [ ] Plan por fases
- [ ] Mínimo 2 criterios de aceptación funcionales con ID (AC-XX)
- [ ] Definition Quality Gate (Paso 2.5) aprobado

---

## Referencia MCP Plane

### Herramientas principales:
- `plane:list_projects` - Listar proyectos del workspace
- `plane:list_states` - Listar estados de un proyecto
- `plane:list_labels` - Listar etiquetas de un proyecto
- `plane:create_work_item` - Crear nuevo work item
- `plane:retrieve_work_item_by_identifier` - Obtener work item por identificador (ej: MCPROFIT-42)

### Estados típicos de un proyecto:
- **Backlog** (group: backlog) - Estado inicial para nuevos PRDs
- **To-Do** (group: unstarted) - Listo para comenzar
- **En Desarrollo** (group: started) - En progreso
- **En Pruebas** (group: started) - En validación
- **Finalizado** (group: completed) - Completado
- **Cancelled** (group: cancelled) - Cancelado
