---
name: quickstart
description: "Interactive tutorial — guides new developers through the full SpecBox Engine pipeline with a demo project"
triggers: ["quickstart", "tutorial", "getting started", "learn engine", "onboarding tutorial"]
context: fork
mode: direct
tools: ["Read", "Write", "Bash", "Glob"]
---

# /quickstart — Tutorial Guiado Interactivo

Tutorial interactivo que guia a nuevos desarrolladores a traves del pipeline completo del SpecBox Engine con un micro-proyecto de ejemplo.

## Uso

```
/quickstart
```

---

## Paso 0: Preparacion del entorno demo

### 0.1 Crear directorio demo

Crea el directorio `~/quickstart-demo/` con una estructura minima de proyecto Flutter (sin necesidad de Flutter SDK real):

```
~/quickstart-demo/
  pubspec.yaml          # Minimal — solo nombre y descripcion
  lib/
    main.dart           # Placeholder
  .quality/
    baselines/
    evidence/
    logs/
    scripts/
  CLAUDE.md             # Generado por el Engine
  .claude/
    settings.json       # Config basica
```

**pubspec.yaml** contenido:
```yaml
name: quickstart_demo
description: Proyecto demo para aprender SpecBox Engine
version: 1.0.0
environment:
  sdk: ">=3.0.0 <4.0.0"
```

**lib/main.dart** contenido:
```dart
// Placeholder — este archivo seria tu app Flutter real
void main() {
  print('Quickstart Demo - SpecBox Engine');
}
```

### 0.2 Mensaje de bienvenida

Mostrar:

```
=== SpecBox Engine — Tutorial Quickstart ===

Bienvenido al tutorial interactivo del SpecBox Engine.
En los proximos minutos vas a recorrer el pipeline completo
que este sistema usa para desarrollar software de forma agentica.

Proyecto demo creado en: ~/quickstart-demo/

Vamos a pasar por 4 etapas:
  1. /prd    — Definir requisitos (PRD + User Stories)
  2. Review  — Revisar lo generado
  3. /plan   — Planificar la implementacion
  4. /implement — Ver como se ejecutaria (modo dry-run)

Cada etapa incluye una explicacion de que esta pasando y por que.
```

---

## Paso 1: Etapa PRD (simulada)

### 1.1 Bloque explicativo

Mostrar al usuario:

```
--- Etapa 1/4: /prd (Product Requirements Document) ---

Que es: El PRD es el documento que define QUE hay que construir.
El Engine descompone cada feature en una jerarquia:
  US (User Story) → UC (Use Case) → AC (Acceptance Criteria)

Cada AC pasa por el "Definition Quality Gate" que rechaza
criterios vagos. Esto garantiza que todo es testable y medible.

Para este demo, vamos a definir una feature sencilla:
"Como usuario, quiero ver una lista de tareas pendientes."
```

### 1.2 Generar PRD demo

Crear el archivo `~/quickstart-demo/doc/prd/demo-prd.md` con contenido:

```markdown
# PRD: Lista de Tareas

## Feature
Como usuario, quiero ver una lista de tareas pendientes para organizar mi dia.

## User Stories

### US-01: Visualizacion de tareas
Como usuario quiero ver mis tareas en una lista scrollable.

#### UC-001: Pantalla principal con lista
- AC-01: La pantalla muestra un ListView con todas las tareas almacenadas
- AC-02: Cada item muestra titulo, fecha y estado (pendiente/completada)
- AC-03: Si no hay tareas, muestra mensaje "No hay tareas pendientes"

#### UC-002: Filtro por estado
- AC-04: Existe un toggle para filtrar entre "todas", "pendientes" y "completadas"
- AC-05: El filtro se aplica instantaneamente sin recarga
```

### 1.3 Explicar resultado

```
El PRD define 1 User Story con 2 Use Cases y 5 Acceptance Criteria.
En un proyecto real, /prd tambien:
  - Crea work items en Trello o Plane
  - Genera un PDF de evidencia
  - Valida que cada AC sea especifico y testable (Definition Quality Gate)
```

---

## Paso 2: Etapa Review

### 2.1 Bloque explicativo

```
--- Etapa 2/4: Review ---

Antes de planificar, siempre se revisa el PRD generado.
Esto es un checkpoint humano — el Engine no avanza sin tu OK.

En este momento revisarias:
  - Que las User Stories cubren el scope deseado
  - Que los Use Cases son atomicos (1 UC = 1 feature testable)
  - Que los Acceptance Criteria son medibles y no ambiguos

El PRD demo esta en: ~/quickstart-demo/doc/prd/demo-prd.md
```

### 2.2 Mostrar el PRD

Leer y mostrar el contenido del PRD generado en el paso anterior.

```
Todo correcto — el PRD es sencillo y claro. Avanzamos a la planificacion.
```

---

## Paso 3: Etapa Plan (simulada)

### 3.1 Bloque explicativo

```
--- Etapa 3/4: /plan (Plan Tecnico) ---

Que es: El plan tecnico define COMO implementar cada UC.
Incluye fases de desarrollo, dependencias, y (si hay UI)
genera disenos visuales con Google Stitch.

Cada fase del plan se ejecuta despues por /implement de forma
autonoma — por eso el plan debe ser preciso y completo.
```

### 3.2 Generar plan demo

Crear el archivo `~/quickstart-demo/doc/plans/UC-001_plan.md` con contenido:

```markdown
# Plan Tecnico: UC-001 — Pantalla principal con lista

## Stack: Flutter
## Patron: feature-first

## Fases

### Fase 1: Modelo de datos
- Crear `lib/features/tasks/domain/task.dart` con clase Task (id, title, date, completed)
- Crear `lib/features/tasks/data/task_repository.dart` con datos mock

### Fase 2: UI — ListView
- Crear `lib/features/tasks/presentation/pages/task_list_page.dart`
- Implementar ListView.builder con TaskTile widget
- Implementar estado vacio ("No hay tareas pendientes")

### Fase 3: Tests
- Unit test para Task model
- Widget test para TaskListPage (con datos y sin datos)

## Acceptance Criteria Mapping
- AC-01 → Fase 2 (ListView.builder)
- AC-02 → Fase 1 (Task model) + Fase 2 (TaskTile)
- AC-03 → Fase 2 (estado vacio)
```

### 3.3 Explicar resultado

```
El plan mapea cada AC a fases concretas de implementacion.
En un proyecto real, /plan tambien:
  - Genera disenos UI con Google Stitch (si el proyecto tiene pantallas)
  - Crea artefactos VEG (Visual Experience Generation) por audiencia
  - Sube el plan como evidencia al gestor de proyecto (Trello/Plane)
```

---

## Paso 4: Etapa Implement (dry-run)

### 4.1 Bloque explicativo

```
--- Etapa 4/4: /implement (Dry-Run) ---

Que es: /implement lee el plan y ejecuta cada fase de forma autonoma.
Un Orchestrator (AG-01) coordina agentes especializados:
  - AG-01: Feature Generator (implementa codigo)
  - AG-02: UI/UX Designer (design-to-code desde Stitch)
  - AG-04: QA Validation (tests + lint)
  - AG-08: Quality Auditor (GO/NO-GO final)
  - AG-09: Acceptance Tester + Validator

En modo dry-run mostramos lo que HARIA cada fase sin ejecutar codigo real.
```

### 4.2 Simular ejecucion

Mostrar la siguiente simulacion (NO ejecutar nada real):

```
[DRY-RUN] Implement UC-001: Pantalla principal con lista

[Fase 1/3] Modelo de datos
  > Crearia: lib/features/tasks/domain/task.dart
  > Crearia: lib/features/tasks/data/task_repository.dart
  > Checkpoint guardado: .quality/evidence/UC-001/checkpoint.json (phase: 1)

[Fase 2/3] UI — ListView
  > Crearia: lib/features/tasks/presentation/pages/task_list_page.dart
  > Crearia: lib/features/tasks/presentation/widgets/task_tile.dart
  > Checkpoint guardado (phase: 2)

[Fase 3/3] Tests
  > Crearia: test/features/tasks/domain/task_test.dart
  > Crearia: test/features/tasks/presentation/task_list_page_test.dart
  > Checkpoint guardado (phase: 3)

[Quality Gate] AG-08 Quality Auditor
  > Verificaria: lint errors = 0, coverage >= baseline, no test regressions
  > Veredicto simulado: GO

[Acceptance] AG-09a Acceptance Tester
  > Generaria tests E2E desde AC-01, AC-02, AC-03
  > Ejecutaria tests con evidencia (screenshots)

[Acceptance] AG-09b Acceptance Validator
  > Verificaria cada AC implementado + testeado + evidenciado
  > Veredicto simulado: ACCEPTED

[PR] Crearia pull request: feat/UC-001-task-list-page
  > Branch: feat/UC-001-task-list-page
  > Target: main
  > Titulo: feat(tasks): implement task list page with empty state
```

---

## Paso 5: Resumen final

### 5.1 Mostrar resumen

```
=== Tutorial Completado ===

Conceptos aprendidos:
  1. PRD: Define QUE construir (US → UC → AC)
  2. Definition Quality Gate: Rechaza AC vagos antes de implementar
  3. Plan Tecnico: Define COMO implementar cada UC en fases
  4. Implement Autopilot: Ejecuta fases con agentes especializados
  5. Quality Gates: Lint, coverage y tests con politica ratchet
  6. Acceptance Engine: Tests E2E + validacion independiente por AC
  7. Self-Healing: Si algo falla, el Engine intenta reparar automaticamente
  8. Merge Secuencial: Solo merge si AG-08=GO + AG-09=ACCEPTED

Para profundizar:
  - docs/getting-started.md    — Guia completa de inicio
  - docs/commands.md           — Referencia de todos los commands
  - docs/agent-teams.md        — Como funcionan los agentes
  - docs/architecture.md       — Patrones por stack

Proyecto demo en: ~/quickstart-demo/
Puedes explorar los archivos generados para ver la estructura.

Para onboardear tu proyecto real, ejecuta:
  /quickstart no es necesario de nuevo — usa directamente:
  → onboard_project (o el wizard interactivo del MCP)
  → /prd para definir tu primera feature
```

### 5.2 Limpiar (opcional)

NO borrar el directorio demo. El usuario puede querer explorarlo.

---

## Reglas

- No requiere Flutter SDK instalado — todo es simulado/placeholder
- No ejecutar comandos reales de build, test o lint
- Cada bloque explicativo debe tener entre 3 y 5 lineas
- El /implement es siempre dry-run — mostrar lo que haria, no hacerlo
- Total de interaccion activa: < 5 minutos
- Idioma: espanol
