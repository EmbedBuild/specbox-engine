---
name: prd-generator
description: >
  Generate structured Product Requirements Documents from feature descriptions.
  Use when the user says "create PRD", "new feature", "write requirements",
  "define feature", or references creating specifications for implementation.
  Supports Trello (spec-driven) and Plane work item creation.
context: fork
agent: Plan
---

# /prd (Global)

Genera un PRD (Product Requirements Document) y crea Work Items en Trello o Plane.

## Uso

```
/prd [titulo] [descripcion de requerimientos]
/prd US-01                    # Spec-driven: enriquece desde Trello
/prd board:BOARD_ID           # Spec-driven: lista US del board para elegir
```

---

## Paso 0: Detectar Modo y Origen

### 0.1 Detectar modo

```
Que recibi?
├── US-XX (ej: "US-01") → Modo SPEC-DRIVEN (Trello)
├── board:BOARD_ID → Modo SPEC-DRIVEN (listar US, elegir)
├── PROYECTO-N (ej: "MCPROFIT-42") → Modo FREEFORM (Plane)
└── Texto libre → Modo FREEFORM (detectar destino)
```

### 0.2 Detectar configuracion del proyecto

Buscar en `.claude/settings.local.json`:

```json
{
  "trello": {
    "boardId": "BOARD_ID_AQUI"
  },
  "plane": {
    "defaultProject": "MCPROFIT",
    "projectId": "uuid",
    "defaultState": "Backlog",
    "defaultAssignee": "d325686f-2d7c-491f-9e28-dffbf4e23c55"
  }
}
```

**Prioridad de destino:**
1. Si el input es US-XX o board:ID → Trello
2. Si el input es PROYECTO-N → Plane
3. Si hay `trello.boardId` → Trello
4. Si hay `plane.defaultProject` → Plane
5. Si ninguno → Preguntar al usuario

### 0.3 Asignee por defecto (Plane)

**OBLIGATORIO** para Plane: Todas las tareas se asignan a:
- **Usuario**: Jesus Perez Sanchez (jesus.perez.developer@gmail.com)
- **ID**: `d325686f-2d7c-491f-9e28-dffbf4e23c55`

---

## Modo SPEC-DRIVEN (Trello)

> El documento del cliente (US/UC/AC) ya existe en Trello.
> El PRD ENRIQUECE pero nunca reinventa lo que el cliente firmo.

### S1: Cargar datos desde Trello

```
1. Obtener board_id de settings o del input
2. Llamar get_us(board_id, us_id) via MCP dev-engine-trello
3. Llamar list_uc(board_id, us_id) para obtener todos los UCs hijos
4. Para cada UC: llamar get_uc(board_id, uc_id) para detalle completo
```

**Datos que se obtienen automaticamente:**
- US: nombre, descripcion, horas estimadas, pantallas
- UCs: nombre, actor, horas, pantallas, estado
- ACs: ID (AC-XX), texto, estado (done/pending)

### S2: Enriquecer con contexto tecnico

El PRD spec-driven NO repite la info del cliente. Anade:
1. **Contexto tecnico**: stack, dependencias, integraciones
2. **Interacciones UI**: volumenes, frecuencias, criticidad (del analisis)
3. **NFRs**: rendimiento, seguridad, accesibilidad
4. **Riesgos**: dependencias externas, complejidad, incertidumbres
5. **Alcance**: que SI incluye y que NO incluye explicitamente

### S3: Generar PRD Spec-Driven

Usar **Template: PRD Spec-Driven** (ver abajo).

### S4: Validar Calidad de Definicion (Paso 2.5)

Ejecutar el Definition Quality Gate sobre los AC-XX que vienen de Trello.
Si algun criterio no pasa → proponer mejoras al usuario ANTES de continuar.

### S5: Adjuntar evidencia a Trello

```
1. Llamar attach_evidence(board_id, us_id, "us", "prd", markdown_content)
   → Genera PDF y lo adjunta a la card US en Trello
2. Confirmar al usuario
```

---

## Modo FREEFORM (Plane o Trello nuevo)

> No hay spec previa. Se genera el PRD desde cero a partir de descripcion del usuario.

### Paso 1: Detectar Tipo de PRD

#### PRD Feature
**Detectar**: "nueva", "anadir", "crear", "implementar", "feature", "funcionalidad", "como [usuario] quiero"

#### PRD Tecnico (Refactor)
**Detectar**: "refactor", "simplificar", "migrar", "eliminar", "cambiar", "reorganizar"

### Paso 2: Recopilar Informacion

#### Preguntas obligatorias para PRD Feature:
1. Que problema resuelve?
2. Quien es el usuario objetivo?
3. Cuales son las User Stories principales? (minimo 1 US con sus UCs)

#### Preguntas para seccion UI (CRITICO):
Para cada Use Case, determinar:
- **Datos**: Que datos muestra? Cuantos items tipicamente?
- **Acciones**: Que puede hacer el usuario? (ver, filtrar, seleccionar, crear, editar, eliminar)
- **Frecuencia**: Con que frecuencia se usa? (diaria, ocasional, rara)
- **Criticidad**: Que pasa si el usuario se equivoca? (reversible, irreversible, costoso)

---

## Template: PRD Spec-Driven

```markdown
# PRD: [US-XX] [Nombre de la User Story]

> Origen: Trello board [board_name] | US-XX
> Generado: [fecha]

## Resumen

[1-2 parrafos: objetivo de la US y que problema resuelve para el usuario]

## Alcance

### Incluye
- [Funcionalidad explicita 1]
- [Funcionalidad explicita 2]

### No incluye
- [Exclusion explicita 1 — evita scope creep]
- [Exclusion explicita 2]

---

## User Story

**ID**: [US-XX]
**Nombre**: [nombre]
**Actor**: [usuario objetivo]
**Horas estimadas**: [N]h
**Pantallas**: [lista]

> Como [actor], quiero [objetivo], para [beneficio].

---

## Use Cases

### UC-XXX: [Nombre]
- **Actor**: [actor]
- **Horas**: [N]h
- **Pantallas**: [pantallas]
- **Estado**: [backlog/ready/in_progress/review/done]

#### Acceptance Criteria
- [ ] **AC-01**: [Criterio especifico y testable]
- [ ] **AC-02**: [Criterio especifico y testable]

### UC-XXX: [Nombre]
...

---

## Interacciones UI

> Esta seccion alimenta el analisis de componentes en /plan

### Visualizacion de datos
| Dato | Volumen | Atributos visibles | Acciones por item |
|------|---------|-------------------|-------------------|
| [ej: Propiedades] | [20-100] | [nombre, direccion, precio] | [ver, editar, eliminar] |

### Acciones del usuario
| Accion | UC asociado | Frecuencia | Criticidad | Requiere confirmacion |
|--------|-------------|------------|------------|----------------------|
| [ej: Crear propiedad] | UC-001 | Ocasional | Media | No |

### Formularios
| Formulario | UC asociado | Campos | Contexto |
|------------|-------------|--------|----------|
| [ej: Nueva propiedad] | UC-002 | [8-12] | Modal / Pagina dedicada |

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medicion |
|-----|----------|----------|
| Rendimiento | Carga inicial < 2s en 4G | Lighthouse / DevTools |
| Seguridad | RLS por tenant | Test de aislamiento |
| Accesibilidad | WCAG 2.1 AA | axe-core audit |
| Offline | [Si aplica] | Test sin conexion |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| [Dependencia externa X] | Media | Alto | [Plan B] |
| [Complejidad de integracion] | Alta | Medio | [Spike previo] |

---

## Stack Tecnico (estimado)

- **Modelo**: [Nuevo / Existente: nombre]
- **Repository**: [nombre]_repository
- **State**: [BLoC/Store/Context]
- **Paginas**: [lista]

## Archivos Principales
[Estructura estimada segun stack detectado]

---

## Criterios de Aceptacion (consolidado)

### Funcionales (validados por AG-09)
[Copiar todos los AC-XX de los UCs arriba, consolidados]

- [ ] **AC-01**: [Criterio — de UC-XXX]
- [ ] **AC-02**: [Criterio — de UC-XXX]
...

### Tecnicos (no validados por AG-09)
- [ ] Proyecto compila sin errores
- [ ] Tests con 85%+ coverage

---
**Prioridad**: [urgent/high/medium/low/none]
**Complejidad**: [Baja/Media/Alta]
*Generado: [fecha]*
```

---

## Template: PRD Feature (Freeform)

```markdown
# PRD: [Titulo]

## Descripcion
[1-2 parrafos: que es y que problema resuelve]

## Objetivo
[Una oracion clara]

## Usuario Objetivo
[Rol del usuario]

## Alcance

### Incluye
- [Funcionalidad explicita]

### No incluye
- [Exclusion explicita]

---

## User Stories y Use Cases

### US-01: [Nombre de la User Story]

> Como [actor], quiero [objetivo], para [beneficio].

#### UC-001: [Nombre del Use Case]
- **Actor**: [actor]
- **Horas estimadas**: [N]h
- **Pantallas**: [lista]

**Acceptance Criteria:**
- [ ] **AC-01**: [Criterio especifico y testable]
- [ ] **AC-02**: [Criterio especifico y testable]

#### UC-002: [Nombre del Use Case]
...

### US-02: [Nombre]
...

---

## Interacciones UI

> Esta seccion alimenta el analisis de componentes en /plan

### Visualizacion de datos
| Dato | Volumen | Atributos visibles | Acciones por item |
|------|---------|-------------------|-------------------|
| [ej: Propiedades] | [20-100] | [nombre, direccion, precio] | [ver, editar, eliminar] |

### Acciones del usuario
| Accion | UC asociado | Frecuencia | Criticidad | Requiere confirmacion |
|--------|-------------|------------|------------|----------------------|
| [ej: Crear propiedad] | UC-001 | Ocasional | Media | No |

### Selecciones/Filtros
| Filtro | Opciones | Seleccion | Frecuencia |
|--------|----------|-----------|------------|
| [ej: Tipo propiedad] | [5-7] | Unica | Frecuente |

### Formularios
| Formulario | UC asociado | Campos | Contexto |
|------------|-------------|--------|----------|
| [ej: Nueva propiedad] | UC-002 | [8-12] | Modal / Pagina dedicada |

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medicion |
|-----|----------|----------|
| Rendimiento | [Criterio medible] | [Como se mide] |
| Seguridad | [Criterio medible] | [Como se mide] |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| [Riesgo identificado] | [B/M/A] | [B/M/A] | [Plan] |

---

## Stack Tecnico (estimado)

- **Modelo**: [Nuevo / Existente: nombre]
- **Repository**: [nombre]_repository
- **State**: [BLoC/Store/Context]
- **Paginas**: [lista]

## Archivos Principales
[Estructura estimada segun stack]

## Dependencias
- [Features o servicios requeridos]

---

## Criterios de Aceptacion (consolidado)

### Funcionales
- [ ] **AC-01**: [Criterio especifico y testable — de UC-001]
- [ ] **AC-02**: [Criterio especifico y testable — de UC-001]
- [ ] **AC-03**: [Criterio especifico y testable — de UC-002]

### Tecnicos (no validados por AG-09)
- [ ] Proyecto compila sin errores
- [ ] Tests con 85%+ coverage

---
**Prioridad**: [urgent/high/medium/low/none]
**Complejidad**: [Baja/Media/Alta]
*Generado: [fecha]*
```

---

## Template: PRD Tecnico

```markdown
# PRD: [Titulo]

## Resumen Ejecutivo
[2-3 parrafos: objetivo del refactor y por que es necesario]

## Alcance

### Incluye
- [Cambio explicito]

### No incluye
- [Exclusion explicita]

---

## Objetivos
1. **[Objetivo 1]** - [Descripcion]
2. **[Objetivo 2]** - [Descripcion]

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

---

## A Eliminar
- [ ] [Elemento] - [Razon]

## A Mantener
- [Elemento]

---

## Plan de Implementacion (alto nivel)

### Fase 1: [Nombre]
- [Tarea]

### Fase 2: [Nombre]
- [Tarea]

### Fase 3: Cleanup
- Eliminar archivos no usados
- Validar compilacion

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|------------|
| [Riesgo identificado] | [B/M/A] | [B/M/A] | [Plan] |

---

## Criterios de Aceptacion

### Funcionales
- [ ] **AC-01**: [Criterio especifico y testable]
- [ ] **AC-02**: [Criterio especifico y testable]

### Tecnicos (no validados por AG-09)
- [ ] Proyecto compila sin errores
- [ ] Tests pasan

---
*Generado: [fecha]*
```

---

## Paso 2.5: Validar Calidad de Definicion (BLOQUEANTE)

> Antes de crear el Work Item, validar que los acceptance criteria permiten testing automatizado.
> El Work Item NO se crea hasta que este gate pase.

### 2.5.1 Asignar ID a cada criterio

Numerar cada criterio funcional: AC-01, AC-02, AC-03...
En modo spec-driven, los IDs ya vienen de Trello — mantenerlos.
Excluir criterios tecnicos genericos ("compila sin errores", "85% coverage") — estos NO cuentan como funcionales.

### 2.5.2 Evaluar cada criterio funcional

Para cada AC-XX, evaluar 3 metricas (0-2):

| Metrica | 0 (RECHAZAR) | 1 (ACEPTABLE) | 2 (IDEAL) |
|---------|-------------|----------------|-----------|
| **Especificidad** | Vago: "funciona bien", "gestiona datos" | General: "mostrar lista de propiedades" | Preciso: "listado paginado de 20 propiedades con foto thumbnail, nombre y precio" |
| **Medibilidad** | Subjetivo: "es rapido", "user-friendly" | Parcial: "carga en poco tiempo" | Cuantificado: "carga inicial < 2s en 4G" |
| **Testabilidad** | No verificable: "buena experiencia" | Solo manual: "el formulario valida campos" | Automatizable: "mostrar error inline rojo bajo el campo si email no contiene @ al perder foco" |

### 2.5.3 Validar cobertura funcional

- Cada Use Case (UC-XXX) DEBE tener al menos 1 criterio AC-XX asociado
- Si un UC no tiene criterio → RECHAZAR
- Ratio minimo: criterios funcionales / use cases >= 1.0

### 2.5.4 Calcular veredicto

```
SI algun criterio tiene score 0 en cualquier metrica → RECHAZAR
SI promedio general de los 3 scores < 1.5 → RECHAZAR
SI algun Use Case no tiene criterio AC-XX → RECHAZAR
ELSE → APROBADO
```

### 2.5.5 Si RECHAZADO

1. Mostrar tabla de evaluacion por criterio:

```
| AC-XX | UC | Especificidad | Medibilidad | Testabilidad | Veredicto |
|-------|-----|--------------|-------------|--------------|-----------|
| AC-01 | UC-001 | 2 | 1 | 2 | OK |
| AC-02 | UC-002 | 0 | 0 | 0 | RECHAZADO |
```

2. Para cada criterio rechazado, proponer una version mejorada concreta
3. Preguntar: "Acepta las mejoras sugeridas o prefiere redactar manualmente?"
4. Aplicar correcciones y re-evaluar
5. NO crear Work Item hasta que pase
6. Maximo 3 iteraciones. Si tras 3 no pasa → pedir al usuario que defina los criterios manualmente

### 2.5.6 Si APROBADO

Continuar a Paso 3 con los AC-XX numerados incorporados al PRD.
Reportar:
```
Definition Quality Gate: APROBADO
Criterios funcionales: {N} (promedio: {score}/2.0)
Cobertura: {N} Use Cases cubiertos de {M}
```

---

## Paso 3: Crear Work Items

### 3a: Destino Trello (spec-driven o freeform)

En modo spec-driven, la US ya existe en Trello. Solo adjuntar evidencia (Paso S5).

En modo freeform con destino Trello:
1. Obtener board_id de settings
2. Llamar import_spec via MCP dev-engine-trello con la estructura US/UC/AC generada
3. Esto crea automaticamente: cards US + cards UC + checklists AC + custom fields

### 3b: Destino Plane

#### Detectar configuracion del proyecto

1. Leer `.claude/settings.local.json` para obtener `plane.projectId`
2. Si no existe, usar `plane:list_projects` y preguntar al usuario
3. Obtener estados con `plane:list_states` para encontrar "Backlog" o "To-Do"
4. Obtener labels con `plane:list_labels` para asignar etiquetas apropiadas

#### Crear el Work Item

Usar `plane:create_work_item`:

```json
{
  "project_id": "[projectId del settings o detectado]",
  "name": "[Titulo del PRD]",
  "description_html": "[PRD completo en HTML]",
  "description_stripped": "[PRD en texto plano]",
  "priority": "[urgent|high|medium|low|none]",
  "state": "[ID del estado Backlog o To-Do]",
  "labels": ["[ID de label si aplica]"],
  "assignees": ["d325686f-2d7c-491f-9e28-dffbf4e23c55"]
}
```

> **IMPORTANTE**: El campo `assignees` SIEMPRE incluye el ID de Jesus Perez

#### Mapeo de prioridades

| PRD | Plane Priority |
|-----|----------------|
| Alta | high |
| Media | medium |
| Baja | low |
| Critica | urgent |

---

## Paso 4: Confirmar

### Si destino es Trello (spec-driven):

```
PRD Generado y adjuntado a Trello

**Board**: [nombre del board]
**User Story**: [US-XX] [nombre]
**PDF adjuntado**: Si

### Resumen:
- **Use Cases**: [N]
- **Acceptance Criteria**: [N] (promedio calidad: {score}/2.0)
- **Interacciones UI documentadas**: [N]
- **NFRs**: [N]
- **Riesgos**: [N]

### Siguiente paso:
/plan US-XX
```

### Si destino es Trello (freeform):

```
PRD Creado en Trello

**Board**: [nombre del board]
**User Stories creadas**: [N]
**Use Cases creados**: [N]

### Siguiente paso:
/plan US-XX
```

### Si destino es Plane:

```
PRD Creado en Plane

**Proyecto**: [nombre del proyecto]
**Work Item**: [nombre]
**ID**: [identifier - ej: MCPROFIT-42]
**Estado**: [estado asignado]
**Prioridad**: [prioridad]

### Resumen:
- **User Stories**: [N]
- **Use Cases**: [N]
- **Acceptance Criteria**: [N]
- **Interacciones UI documentadas**: [N]

### Siguiente paso:
/plan MCPROFIT-[numero]
```

---

## Checklist de Calidad

### PRD Feature (spec-driven o freeform):
- [ ] Titulo claro (max 60 chars)
- [ ] Descripcion explica el problema
- [ ] Seccion Alcance (incluye + no incluye)
- [ ] Minimo 1 User Story con Use Cases
- [ ] Cada UC tiene minimo 1 AC-XX
- [ ] Seccion "Interacciones UI" completa
- [ ] Tabla de acciones con UC asociado, frecuencia y criticidad
- [ ] Seccion NFRs con criterios medibles
- [ ] Seccion Riesgos con mitigacion
- [ ] Cada criterio: especificidad >= 1, medibilidad >= 1, testabilidad >= 1
- [ ] Promedio de calidad de criterios >= 1.5/2.0
- [ ] Definition Quality Gate (Paso 2.5) aprobado

### PRD Tecnico:
- [ ] Resumen ejecutivo claro
- [ ] Seccion Alcance (incluye + no incluye)
- [ ] Al menos un cambio ANTES/DESPUES
- [ ] Seccion "Cambios de UI" si afecta interfaz
- [ ] Plan por fases
- [ ] Seccion Riesgos
- [ ] Minimo 2 criterios de aceptacion funcionales con ID (AC-XX)
- [ ] Definition Quality Gate (Paso 2.5) aprobado

---

## Jerarquia Conceptual

```
US-XX (User Story) = unidad presupuestable, valor para el cliente
  └── UC-XXX (Use Case) = unidad atomica de desarrollo
        └── AC-XX (Acceptance Criteria) = verificacion contractual
```

- **US** → se mapea a una card en Trello (label azul) o work item en Plane
- **UC** → se mapea a una card hija en Trello (label verde) vinculada via us_id
- **AC** → se mapea a checkitems en el checklist "Criterios de Aceptacion" del UC
- La US es lo que se presupuesta y el cliente firma
- El UC es lo que el agente implementa (1 UC = 1 ciclo /implement)
- El AC es lo que AG-09 valida

---

## Referencia MCP

### Trello (dev-engine-trello):
- `get_us(board_id, us_id)` — Detalle completo de US con UCs hijos
- `get_uc(board_id, uc_id)` — Detalle completo de UC con ACs
- `list_us(board_id)` — Listar todas las US del board
- `list_uc(board_id, us_id)` — Listar UCs de una US
- `import_spec(board_id, spec)` — Importar estructura US/UC/AC completa
- `attach_evidence(board_id, target_id, target_type, evidence_type, markdown)` — Adjuntar PDF

### Plane:
- `plane:list_projects` — Listar proyectos del workspace
- `plane:list_states` — Listar estados de un proyecto
- `plane:list_labels` — Listar etiquetas de un proyecto
- `plane:create_work_item` — Crear nuevo work item
- `plane:retrieve_work_item_by_identifier` — Obtener work item por identificador
