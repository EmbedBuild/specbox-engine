# Template: Archivo .feature para Acceptance Testing

## Convenciones obligatorias

| Elemento | Regla |
|----------|-------|
| Idioma | `# language: es` — SIEMPRE |
| Tags | `@US-XX @UC-XXX` en Característica, `@AC-XX` en cada Escenario |
| Nombre archivo | `UC-XXX_{nombre_snake}.feature` |
| Ubicación | `test/acceptance/features/` (Flutter) o `tests/acceptance/features/` (resto) |
| Un archivo | = Un Use Case |
| Un Escenario | = Un Acceptance Criterion |
| Antecedentes | Precondiciones comunes (auth, navegación) |

## Template

```gherkin
# language: es
@US-XX @UC-XXX
Característica: UC-XXX — [Nombre del caso de uso]
  Como [Actor del UC]
  Quiero [Objetivo del UC]
  Para [Beneficio esperado]

  Antecedentes:
    Dado el usuario está autenticado como "[Actor]"
    Y está en la pantalla "[Pantalla principal del UC]"

  @AC-01
  Escenario: [Texto del AC-01 tal como está en el PRD]
    Dado [precondición específica si la hay]
    Cuando [acción del usuario — paso 1]
    Y [acción del usuario — paso 2 si aplica]
    Entonces [resultado observable — qué ve/oye/recibe el usuario]
    Y [resultado adicional si aplica]

  @AC-02
  Escenario: [Texto del AC-02 tal como está en el PRD]
    Cuando [acción]
    Entonces [resultado]
```

## Reglas de step definitions

| Regla | Detalle |
|-------|---------|
| Steps reutilizables | Auth, navegación, assertions genéricas → `steps/common_steps` |
| Steps del UC | Lógica específica → `steps/UC-XXX_steps` |
| Screenshots | Capturar al final de cada Escenario (automático en fallo) |
| Datos de prueba | Usar Esquema del Escenario + Ejemplos para parameterizar |

## Keywords Gherkin en español

| Inglés | Español |
|--------|---------|
| Feature | Característica |
| Background | Antecedentes |
| Scenario | Escenario |
| Scenario Outline | Esquema del Escenario |
| Examples | Ejemplos |
| Given | Dado / Dada / Dados / Dadas |
| When | Cuando |
| Then | Entonces |
| And | Y |
| But | Pero |
