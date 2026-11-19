# results.json — Contrato formal

> Formato estándar que TODOS los stacks deben producir tras ejecutar acceptance tests.
> AG-09b consume este archivo para validar. Si no existe o no cumple el schema, AG-09b rechaza.

---

## Schema

```json
{
  "feature": "string — nombre del feature (snake_case)",
  "uc_id": "string — UC-XXX",
  "us_id": "string — US-XX",
  "timestamp": "string — ISO 8601",
  "source": "string — origen de los datos",
  "stack": "string — flutter-web | flutter-mobile | react | go | python",
  "evidence_type": "string — screenshot | response-log",
  "tests_total": "number",
  "tests_passed": "number",
  "tests_failed": "number",
  "results": [
    {
      "id": "string — AC-XX",
      "scenario": "string — texto del escenario Gherkin",
      "status": "string — PASS | FAIL",
      "duration_ms": "number",
      "evidence": "string | null — nombre del archivo de evidencia",
      "error": "string | null — mensaje de error si FAIL",
      "steps": [
        {
          "keyword": "string — Dado | Cuando | Entonces | Y",
          "text": "string — texto del step",
          "status": "string — PASS | FAIL",
          "duration_ms": "number"
        }
      ],
      "contract": {
        "pre": ["string — AC-XX.preN que la prueba comprueba"],
        "post": ["string — AC-XX.postN que la prueba comprueba"]
      }
    }
  ]
}
```

---

## Campos obligatorios

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `feature` | string | Nombre del feature en snake_case |
| `uc_id` | string | ID del Use Case (UC-XXX) |
| `us_id` | string | ID de la User Story (US-XX) |
| `timestamp` | string | Fecha ISO 8601 de la ejecución |
| `source` | string | Identificador del origen (ver tabla abajo) |
| `stack` | string | Stack que generó los resultados |
| `evidence_type` | string | Tipo de evidencia que acompaña los resultados |
| `tests_total` | number | Total de escenarios ejecutados |
| `tests_passed` | number | Escenarios con status PASS |
| `tests_failed` | number | Escenarios con status FAIL |
| `results` | array | Array de resultados por AC |

## Campo `results[]`

| Campo | Tipo | Obligatorio | Descripción |
|-------|------|-------------|-------------|
| `id` | string | Sí | ID del acceptance criterion (AC-XX) |
| `scenario` | string | Sí | Texto descriptivo del escenario |
| `status` | string | Sí | PASS o FAIL |
| `duration_ms` | number | Sí | Duración en milisegundos |
| `evidence` | string/null | Sí | Nombre del archivo de evidencia (screenshot o response log) |
| `error` | string/null | Sí | Mensaje de error (null si PASS) |
| `steps` | array | No | Desglose de steps Gherkin (si disponible) |
| `contract` | object | No (sí con contrato) | Las condiciones del contrato que comprueba la prueba: `{"pre": [...], "post": [...]}` con ids `AC-XX.preN` / `AC-XX.postN` de su criterio. Ver «Contrato de cada criterio» |

---

## Valores de `source` por stack

| Stack | source | Descripción |
|-------|--------|-------------|
| Flutter Web | `playwright-cucumber` | Playwright + playwright-bdd |
| Flutter Mobile | `maestro-junit-xml` | **Recomendado** — Maestro YAML flows + JUnit XML (v5.28+) |
| Flutter Mobile | `patrol-junit-xml` | Legacy soportado — Patrol v4 + JUnit XML |
| React | `playwright-cucumber` | Playwright + playwright-bdd |
| Python | `pytest-bdd` | pytest-bdd + httpx |

## Valores de `evidence_type`

| Valor | Descripción | Stacks |
|-------|-------------|--------|
| `screenshot` | PNG de la pantalla (fullpage o viewport) | Flutter Web, Flutter Mobile, React |
| `response-log` | JSON con request/response HTTP | Python |

## Valores de `evidence` por tipo

| evidence_type | Formato del nombre | Ejemplo |
|---------------|-------------------|---------|
| `screenshot` | `AC-XX_{descripcion}.png` | `AC-01_crear_propiedad.png` |
| `response-log` | `AC-XX_{descripcion}.json` | `AC-01_crear_endpoint.json` |

---

## Ejemplo: Flutter Web / React (screenshot)

```json
{
  "feature": "crear_propiedad",
  "uc_id": "UC-001",
  "us_id": "US-01",
  "timestamp": "2026-03-28T14:30:45.000Z",
  "source": "playwright-cucumber",
  "stack": "flutter-web",
  "evidence_type": "screenshot",
  "tests_total": 5,
  "tests_passed": 4,
  "tests_failed": 1,
  "results": [
    {
      "id": "AC-01",
      "scenario": "Usuario crea propiedad con datos válidos",
      "status": "PASS",
      "duration_ms": 1234,
      "evidence": "AC-01_crear_propiedad.png",
      "error": null,
      "steps": [
        { "keyword": "Dado", "text": "el usuario está autenticado como \"propietario\"", "status": "PASS", "duration_ms": 120 },
        { "keyword": "Cuando", "text": "completa el formulario con datos válidos", "status": "PASS", "duration_ms": 340 },
        { "keyword": "Entonces", "text": "la propiedad aparece en el listado", "status": "PASS", "duration_ms": 774 }
      ]
    },
    {
      "id": "AC-02",
      "scenario": "Validación inline en nombre vacío",
      "status": "FAIL",
      "duration_ms": 890,
      "evidence": null,
      "error": "Expected 'error visible' but element not found",
      "steps": [
        { "keyword": "Cuando", "text": "deja el nombre vacío y pulsa guardar", "status": "PASS", "duration_ms": 200 },
        { "keyword": "Entonces", "text": "se muestra error rojo bajo el campo", "status": "FAIL", "duration_ms": 690 }
      ]
    }
  ]
}
```

## Ejemplo: Python API (response-log)

```json
{
  "feature": "autenticacion_api",
  "uc_id": "UC-010",
  "us_id": "US-03",
  "timestamp": "2026-03-28T14:30:45.000Z",
  "source": "pytest-bdd",
  "stack": "python",
  "evidence_type": "response-log",
  "tests_total": 3,
  "tests_passed": 3,
  "tests_failed": 0,
  "results": [
    {
      "id": "AC-01",
      "scenario": "Login con credenciales válidas retorna token JWT",
      "status": "PASS",
      "duration_ms": 45,
      "evidence": "AC-01_login_valido.json",
      "error": null,
      "steps": [
        { "keyword": "Dado", "text": "un usuario registrado con email \"user@test.com\"", "status": "PASS", "duration_ms": 5 },
        { "keyword": "Cuando", "text": "envía POST a \"/auth/login\" con credenciales válidas", "status": "PASS", "duration_ms": 30 },
        { "keyword": "Entonces", "text": "la respuesta tiene status 200 y contiene \"access_token\"", "status": "PASS", "duration_ms": 10 }
      ]
    }
  ]
}
```

---

## Ubicación del archivo

```
.quality/evidence/{feature}/acceptance/results.json
```

Siempre en la misma ruta, independientemente del stack. AG-09b busca aquí.

---

## Validación

Un `results.json` es válido si:

1. `tests_total === results.length`
2. `tests_passed + tests_failed === tests_total`
3. Cada `results[].id` comienza con `AC-`
4. Cada `results[].status` es `PASS` o `FAIL`
5. `stack` es uno de los valores definidos
6. `evidence_type` es `screenshot` o `response-log`
7. Si `evidence` no es null, el archivo referenciado existe en el mismo directorio
8. Si un resultado trae `contract`, es un objeto con `pre` y `post` como listas de ids

Con `--check-contract <contract.json>`, además, cada criterio del contrato tiene su `pre`, su `post`
y su `undefined`, y cada resultado cita al menos una `pre` y una `post` **de su criterio** que el
contrato tiene. Las condiciones que ninguna prueba cita salen como aviso.

```bash
node .quality/scripts/validate-results-json.js \
  .quality/evidence/{feature}/acceptance/results.json \
  --check-evidence --check-contract .quality/evidence/{feature}/acceptance/contract.json
```

---

## Contrato de cada criterio (US-128 · UC-12801)

Antes de generar ninguna prueba de aceptación, AG-09a escribe el contrato de la UC: por cada
criterio vigente, sus precondiciones, sus postcondiciones y el comportamiento que el criterio no
define. Las pruebas se generan desde el contrato y cada una cita lo que comprueba.

**Ubicación**: `.quality/evidence/{feature}/acceptance/contract.json`, junto a `results.json`. Se
adjunta como evidencia `ag09` de la UC.

```json
{
  "schema": 1,
  "uc_id": "UC-001",
  "criteria": {
    "AC-01": {
      "pre": [{ "id": "AC-01.pre1", "text": "El usuario está autenticado como propietario" }],
      "post": [
        { "id": "AC-01.post1", "text": "La propiedad aparece en el listado con el nombre enviado" },
        { "id": "AC-01.post2", "text": "El contador de propiedades sube en 1" }
      ],
      "undefined": ["Qué pasa si dos propietarios crean a la vez una propiedad con el mismo nombre"]
    }
  }
}
```

| Regla | Detalle |
|-------|---------|
| `schema` | `1` |
| `uc_id` | La UC del contrato; debe coincidir con la de `results.json` |
| Una entrada por criterio | Cada criterio vigente de la UC, con su id (`AC-01`); un criterio retirado no lleva |
| `pre` y `post` | Al menos una de cada; cada condición con `id` (`AC-01.pre1`, `AC-01.post1`: su criterio, su clase y un número) y `text` |
| `undefined` | Lista de textos; puede estar vacía, pero se escribe: decir que no hay nada sin definir también es una decisión |
| Límites | 512 KB por contrato, 200 criterios, 50 condiciones por clase, 2000 caracteres por texto |

**Cómo cita una prueba lo que comprueba**:

| Stack | Dónde | Ejemplo |
|-------|-------|---------|
| Gherkin (Playwright, pytest-bdd) | Etiquetas del escenario | `@AC-01 @pre:AC-01.pre1 @post:AC-01.post1` |
| Maestro | Comentario de cabecera del flujo | `# contract: AC-01.pre1, AC-01.post1` |
| Patrol | Comentario encima del test | `// contract: AC-01.pre1, AC-01.post1` |

Los generadores de evidencia llevan esas citas a `results[].contract`.

**Comprobación**: la tool `check_acceptance_contract(contract_content, uc_criteria, uc_id,
results_content)` (pura: no lee el tablero ni el disco) dice qué criterios no tienen contrato
(`missing`), cuáles no tienen `pre`, `post` o `undefined` (`incomplete`), qué entradas no valen
(`invalid`) y, con los resultados, qué pruebas no citan su `pre` y su `post` (`uncited`) o citan
una condición que no es de su criterio (`unknown`). El validador usa las mismas reglas
(`.claude/hooks/lib/acceptance-contract.mjs`, espejo de `server/acceptance_contract.py`).

---

*SpecBox Engine v5.19.0 — results.json Contract*
