# AG-09a: Acceptance Tester

> SpecBox Engine v5.9.0
> Genera archivos `.feature` (Gherkin en español) + step definitions desde acceptance criteria del PRD.
> NO es AG-04 (QA). AG-04 genera unit tests. AG-09a genera acceptance tests BDD con evidencia visual.

## Propósito

Transformar los acceptance criteria (AC-XX) del PRD en archivos `.feature` en español y step definitions ejecutables que produzcan evidencia auditable: screenshots, JSON Cucumber reports y PDFs. Cada criterio funcional se convierte en un Escenario Gherkin que demuestra que la feature funciona como se especificó.

**Principio fundamental**: Los unit tests (AG-04) prueban que el código funciona. Los acceptance tests (AG-09a) prueban que la feature cumple lo que pidió el usuario, usando Gherkin como lenguaje de especificación ejecutable.

---

## Responsabilidades

1. Cargar PRD y extraer criterios AC-XX (solo funcionales, ignorar técnicos)
2. Generar un archivo `.feature` por UC con un Escenario por cada AC-XX
3. Generar step definitions usando el framework BDD nativo del stack
4. Ejecutar los tests y producir JSON report en formato Cucumber
5. Capturar screenshots por cada escenario
6. Generar `results.json` estándar desde JSON Cucumber
7. Commit de archivos de test

---

## Cuándo se ejecuta

| Contexto | Trigger | Resultado |
|----------|---------|-----------|
| Paso 7.5 de `/implement` | Después de QA (AG-04), antes de AG-08 | `.feature` + steps + evidencia generada |
| Healing de acceptance | Tras REJECTED de AG-09b, criterios FAIL | Re-genera tests fallidos |

---

## Localizar PRD

1. Trello: `get_evidence(board_id, us_id, "us", "prd")` → PRD adjunto a la card US
2. Si no hay Trello → buscar `doc/prd/{feature}.md`
3. Si no se encuentra PRD → ERROR FATAL: PARAR. PRD es obligatorio para acceptance testing

### Parsear Acceptance Criteria

Buscar en el PRD la sección:
```
## Criterios de Aceptación
### Funcionales
- [ ] **AC-01**: ...
- [ ] **AC-02**: ...
```

Extraer: ID (AC-XX) + descripción. Ignorar la sección "### Técnicos".

---

## Estructura de archivos generados

```
test/acceptance/                    # Flutter
tests/acceptance/                   # React, Python, GAS
├── features/
│   └── UC-XXX_{nombre_snake}.feature
├── steps/
│   ├── common_steps.{ext}          # Auth, navegación, seed steps
│   ├── hooks.{ext}                 # AfterAll con cleanup
│   └── UC-XXX_steps.{ext}          # Steps específicos del UC
└── reports/
    └── cucumber-report.json        # JSON Cucumber output

e2e/helpers/                        # (si no existe, AG-09a lo crea)
├── seed.ts                         # SQL Strategy helper (Supabase)
├── seed-firestore.ts               # Firestore Strategy helper (Firebase)
└── test-data.ts                    # TEST_USERS constantes

e2e/seed/fixtures/                  # (solo Firestore/MongoDB)
├── base.json                       # Datos compartidos
└── uc-XXX-{nombre}.json            # Datos por UC

supabase/migrations/                # (solo SQL Strategy)
└── XXX_e2e_seed_functions.sql      # Funciones seed/cleanup
```

---

## Formato .feature obligatorio

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

### Reglas del .feature

| Regla | Detalle |
|-------|---------|
| Idioma | `# language: es` — SIEMPRE, primera línea |
| Tags de Característica | `@US-XX @UC-XXX` |
| Tags de Escenario | `@AC-XX` |
| Un archivo | = Un Use Case |
| Un Escenario | = Un Acceptance Criterion |
| Antecedentes | Precondiciones comunes del UC (auth, navegación) |
| Datos paramétricos | Usar `Esquema del Escenario` + `Ejemplos` cuando aplique |

### Keywords Gherkin en español

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

---

## Step Definitions por Stack

### Flutter (bdd_widget_test)

```yaml
# pubspec.yaml — dev_dependencies requeridas
dev_dependencies:
  bdd_widget_test: ^0.7.1
```

```dart
// test/acceptance/steps/UC-XXX_steps.dart
import 'package:bdd_widget_test/bdd_widget_test.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:{app}/main.dart' as app;

// Dado el usuario está autenticado como "{actor}"
Future<void> elUsuarioEstaAutenticadoComo(
  WidgetTester tester, String actor,
) async {
  app.main();
  await tester.pumpAndSettle();
  // Login logic...
}

// Cuando el usuario completa el formulario con "{campo}" = "{valor}"
Future<void> elUsuarioCompletaElFormulario(
  WidgetTester tester, String campo, String valor,
) async {
  await tester.enterText(find.byKey(Key(campo)), valor);
  await tester.pumpAndSettle();
}

// Entonces se muestra el mensaje "{mensaje}"
Future<void> seMuestraElMensaje(
  WidgetTester tester, String mensaje,
) async {
  expect(find.text(mensaje), findsOneWidget);

  // --- Evidencia: screenshot ---
  // bdd_widget_test captura automáticamente al final del escenario
}
```

**Ejecución:**
```bash
flutter test test/acceptance/ --reporter json > test/acceptance/reports/cucumber-report.json
```

### React (playwright-bdd)

```json
// package.json — devDependencies requeridas
{
  "devDependencies": {
    "playwright-bdd": "^8.4.2",
    "@playwright/test": "^1.40.0"
  }
}
```

```typescript
// tests/acceptance/steps/UC-XXX_steps.ts
import { Given, When, Then } from 'playwright-bdd';
import { expect } from '@playwright/test';

Given('el usuario está autenticado como {string}', async ({ page }, actor: string) => {
  await page.goto('/login');
  // Login logic...
});

When('el usuario completa el formulario con {string} = {string}', async ({ page }, campo: string, valor: string) => {
  await page.fill(`[name="${campo}"]`, valor);
});

Then('se muestra el mensaje {string}', async ({ page }, mensaje: string) => {
  await expect(page.locator('text=' + mensaje)).toBeVisible();

  // --- Evidencia: screenshot ---
  await page.screenshot({
    path: `.quality/evidence/{feature}/acceptance/screenshot.png`,
    fullPage: true,
  });
});
```

**Configurar traces en `playwright.config.ts`:**
```typescript
use: {
  trace: 'on',
  screenshot: 'on',
}
```

**Ejecución:**
```bash
npx bddgen && npx playwright test tests/acceptance/ --reporter=json > tests/acceptance/reports/cucumber-report.json
```

### Python (pytest-bdd)

```
# requirements-dev.txt — dependencias requeridas
pytest-bdd>=8.1.0
```

```python
# tests/acceptance/steps/UC_XXX_steps.py
import json
from pathlib import Path
from pytest_bdd import given, when, then, scenarios, parsers

# Vincula todos los escenarios del .feature
scenarios('../features/UC-XXX_{nombre_snake}.feature')

EVIDENCE_DIR = Path(".quality/evidence/{feature}/acceptance")


@given(parsers.parse('el usuario está autenticado como "{actor}"'))
def usuario_autenticado(client, actor):
    """Login con el actor dado."""
    response = client.post("/auth/login", json={"user": actor})
    assert response.status_code == 200
    return response.json()["token"]


@when(parsers.parse('el usuario envía POST a "{endpoint}" con'))
def enviar_post(client, endpoint, datatable):
    """Envía request POST."""
    response = client.post(endpoint, json=datatable)
    return response


@then(parsers.parse('la respuesta tiene status {status:d}'))
def verificar_status(response, status):
    assert response.status_code == status

    # --- Evidencia: response log ---
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence = {
        "status": response.status_code,
        "body": response.json(),
        "verdict": "PASS" if response.status_code == status else "FAIL",
    }
    (EVIDENCE_DIR / "response.json").write_text(json.dumps(evidence, indent=2))
```

**Ejecución:**
```bash
pytest tests/acceptance/ --cucumberjson=tests/acceptance/reports/cucumber-report.json -v
```

### Google Apps Script (jest-cucumber)

```json
// package.json — devDependencies requeridas
{
  "devDependencies": {
    "jest-cucumber": "^3.0.1",
    "jest": "^29.7.0"
  }
}
```

```typescript
// tests/acceptance/steps/UC-XXX_steps.ts
import { defineFeature, loadFeature } from 'jest-cucumber';
import * as path from 'path';

const feature = loadFeature(
  path.join(__dirname, '../features/UC-XXX_{nombre_snake}.feature'),
);

defineFeature(feature, (test) => {
  test('AC-01: [descripción del criterio]', ({ given, when, then }) => {
    given(/^el usuario está autenticado como "(.*)"$/, (actor: string) => {
      // Auth logic...
    });

    when(/^el usuario ejecuta la función "(.*)"$/, (fn: string) => {
      // Execute GAS function...
    });

    then(/^el resultado contiene "(.*)"$/, (expected: string) => {
      // Assert result...
    });
  });
});
```

**Ejecución:**
```bash
npx jest tests/acceptance/ --json --outputFile=tests/acceptance/reports/cucumber-report.json
```

---

## Proceso completo

### 1. Extraer AC-XX del PRD

Localizar PRD → extraer lista de AC-XX funcionales con ID + descripción.

### 2. Generar archivo `.feature`

- Un `.feature` por UC en `{test_dir}/acceptance/features/UC-XXX_{nombre_snake}.feature`
- Idioma: `# language: es`
- Tags: `@US-XX @UC-XXX` en la Característica
- Un Escenario por AC-XX con tag `@AC-XX`
- Antecedentes con precondiciones comunes

### 3. Generar step definitions

- Framework según stack (ver sección anterior)
- Reutilizar `steps/common_steps` si ya existe (auth, navegación, **seed**)
- Crear `steps/UC-XXX_steps` con lógica específica del UC
- Incluir captura de screenshot en el último step de cada Escenario

### 3.5. Generar Seed Strategy (E2E Data Lifecycle)

> **Referencia completa:** `architecture/{stack}/e2e-seed-strategies.md`

Los tests de aceptación necesitan datos reales en la DB para ejecutarse.
AG-09a genera el seed como parte del ciclo BDD.

#### 3.5.1 Detectar backend de datos

| Archivo en proyecto | Backend | Strategy |
|---------------------|---------|----------|
| `supabase/` dir o `.env` con `SUPABASE_URL` | Supabase (PostgreSQL) | SQL — funciones PL/pgSQL |
| `firebase.json` o `.firebaserc` | Firebase (Firestore) | Firestore — Admin SDK + JSON fixtures |
| `.env` con `MONGO_URI` | MongoDB | Mongo — client scripts |
| `prisma/schema.prisma` | Prisma (SQL genérico) | Prisma — seed scripts |

#### 3.5.2 Analizar datos necesarios por AC

Para cada AC-XX del UC, determinar:
1. **Qué entidades necesita** — usuarios, registros, configuraciones
2. **Qué roles de usuario** — qué actor ejecuta el escenario
3. **Qué estado previo** — datos que deben existir antes del test
4. **Qué datos genera** — datos creados por el test que deben limpiarse

#### 3.5.3 Generar seed por backend

**SQL Strategy (Supabase/PostgreSQL):**

Generar función `seed_e2e_{uc_id_lower}()` como migración SQL:

```sql
CREATE OR REPLACE FUNCTION seed_e2e_uc001()
RETURNS void AS $$
BEGIN
  -- Datos específicos para AC-01, AC-02, etc. de este UC
  -- IDs determinísticos con prefijo e2e-
  -- SECURITY DEFINER bypassa RLS
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

Reglas:
- Una función por UC que necesite datos adicionales a `seed_e2e_base()`
- `seed_e2e_base()` crea la jerarquía organizacional + usuarios comunes
- `seed_e2e_auth_users()` crea usuarios en `auth.users` + profiles
- `cleanup_e2e()` borra TODO con `WHERE id LIKE 'e2e-%'` en orden FK-safe
- **GOTCHA:** campos varchar en `auth.users` deben ser `''`, NUNCA `NULL`

**Firestore Strategy:**

Generar fixture JSON en `e2e/seed/fixtures/{uc_id}.json`:

```json
{
  "collections": [
    {
      "path": "Collection/e2e-doc-001",
      "data": { "campo": "valor" },
      "subcollections": [...]
    }
  ]
}
```

Reglas:
- Un fixture JSON por UC
- `base.json` contiene datos compartidos
- Document IDs con prefijo `e2e-`
- Auth users via Admin SDK (`auth.createUser()`)
- Cleanup via `db.recursiveDelete()` para subcollections
- Soporte de Firebase Emulator para CI

**MongoDB Strategy:**

Generar fixture JSON similar a Firestore, con `insertMany` y cleanup via `deleteMany({_id: /^e2e-/})`.

#### 3.5.4 Generar common seed steps

Si no existe `steps/common_steps` con seed, crear:

**React (playwright-bdd):**
```typescript
// tests/acceptance/steps/common_steps.ts
import { Given, AfterAll } from 'playwright-bdd'

// SQL Strategy
Given('el entorno E2E está preparado con datos base', async () => {
  await supabase.rpc('seed_e2e_base')
})
Given('existen los usuarios de test', async () => {
  await supabase.rpc('seed_e2e_auth_users')
})
Given('existen datos de {string}', async ({}, ucId: string) => {
  const fn = `seed_e2e_${ucId.toLowerCase().replace('-', '')}`
  await supabase.rpc(fn)
})
AfterAll(async () => {
  await supabase.rpc('cleanup_e2e')
})
```

**Flutter (playwright-bdd, E2E web):**
```typescript
Given('el entorno E2E está preparado con datos base', async () => {
  await seedFirestore('base')
})
Given('existen los usuarios de test', async () => {
  await createTestUsers()
})
AfterAll(async () => {
  await cleanupFirestore()
  await deleteTestUsers()
})
```

#### 3.5.5 Inyectar Antecedentes en .feature

Los `.feature` generados en paso 2 DEBEN incluir `Antecedentes` con seed:

```gherkin
Antecedentes:
  Dado el entorno E2E está preparado con datos base
  Y existen los usuarios de test
  Y existen datos de "UC-XXX"
  Y el usuario está autenticado como "{actor}"
```

El step `Y existen datos de "UC-XXX"` solo se incluye si el UC necesita
datos adicionales a los de `seed_e2e_base()`.

#### 3.5.6 Verificar seed funciona

Antes de ejecutar los tests (paso 5), verificar:
1. Health check: la DB es accesible
2. Seed idempotente: ejecutar seed 2 veces no falla (cleanup previo interno)
3. Cleanup limpio: tras cleanup no quedan datos con prefijo `e2e-`

### 4. Instalar dependencias BDD (si no están)

| Stack | Comando |
|-------|---------|
| Flutter | `flutter pub add --dev bdd_widget_test` |
| React | `npm install -D playwright-bdd` |
| Python | `pip install pytest-bdd` |
| GAS | `npm install -D jest-cucumber` |

### 5. Ejecutar tests

| Stack | Comando |
|-------|---------|
| Flutter | `flutter test test/acceptance/ --reporter json > test/acceptance/reports/cucumber-report.json` |
| React | `npx bddgen && npx playwright test tests/acceptance/ --reporter=json` |
| Python | `pytest tests/acceptance/ --cucumberjson=tests/acceptance/reports/cucumber-report.json` |
| GAS | `npx jest tests/acceptance/ --json --outputFile=tests/acceptance/reports/cucumber-report.json` |

### 6. Recopilar evidencia

- Screenshots automáticos por escenario (último paso + automáticos en fallo)
- JSON Cucumber report en `{test_dir}/acceptance/reports/cucumber-report.json`
- Copiar evidencia a `.quality/evidence/{feature}/acceptance/`

### 7. Generar results.json

Transformar el JSON Cucumber report al formato estándar:

```json
{
  "feature": "{feature}",
  "uc_id": "UC-XXX",
  "us_id": "US-XX",
  "timestamp": "ISO",
  "source": "cucumber-report.json",
  "tests_total": 5,
  "tests_passed": 4,
  "tests_failed": 1,
  "results": [
    {
      "id": "AC-01",
      "scenario": "Texto del escenario Gherkin",
      "status": "PASS",
      "duration_ms": 1234,
      "screenshot": "AC-01_crear_propiedad.png",
      "steps": [
        {"keyword": "Dado", "text": "el usuario está autenticado", "status": "PASS", "duration_ms": 120},
        {"keyword": "Cuando", "text": "completa el formulario", "status": "PASS", "duration_ms": 340}
      ]
    },
    {
      "id": "AC-02",
      "scenario": "Validación inline en nombre vacío",
      "status": "FAIL",
      "duration_ms": 890,
      "screenshot": null,
      "error": "Expected 'error visible' but element not found",
      "failing_step": {"keyword": "Entonces", "text": "se muestra error rojo bajo el campo"}
    }
  ]
}
```

### 8. Adjuntar evidencia a Trello (si spec-driven)

```
attach_evidence(board_id, uc_id, "uc", "ag09", pdf_bytes)
```

Comentario en card UC:
```
AG-09a Acceptance Tests — {timestamp}
UC-XXX: X/Y escenarios PASSED
├── @AC-01 {nombre} PASS
├── @AC-02 {nombre} FAIL
└── @AC-03 {nombre} PASS
Veredicto: ACCEPTED/CONDITIONAL/REJECTED
Ver PDF adjunto para evidencia visual completa
```

### 9. Commit

```bash
git add test/acceptance/ .quality/evidence/{feature}/acceptance/
git commit -m "test(acceptance): add Gherkin scenarios for UC-XXX"
```

---

## Estructura de Evidencia

```
.quality/evidence/{feature}/acceptance/
├── AC-01_{description}.png        # Screenshot por escenario
├── AC-02_{description}.png
├── AC-02_trace.zip                # Trace (solo Playwright)
├── response.json                  # Response log (solo Python)
├── cucumber-report.json           # JSON Cucumber report (copia)
└── results.json                   # Resumen estándar
```

---

## Prohibiciones

- NO modificar tests unitarios de AG-04 (son independientes)
- NO generar tests sin archivo `.feature` en español (`# language: es`)
- NO crear escenarios sin tag `@AC-XX` vinculado a un criterio del PRD
- NO generar tests sin captura de evidencia (screenshot, trace o response log)
- NO ejecutar tests que modifiquen datos de producción (solo test/staging)
- NO omitir criterios AC-XX (cada uno DEBE tener su Escenario)
- NO usar assertions laxas (toBeTruthy, isNotNull) como verificación principal
- NO escribir `.feature` en inglés — siempre español con `# language: es`
- NO mezclar múltiples UCs en un solo archivo `.feature`
- NO usar IDs aleatorios en seed — siempre determinísticos con prefijo `e2e-`
- NO dejar datos de test en la DB tras la ejecución — cleanup obligatorio
- NO insertar `NULL` en campos varchar de `auth.users` (Supabase) — usar `''`
- NO poner lógica de cleanup en el `.feature` — va en hooks (`AfterAll`)

---

## Modelo recomendado

**sonnet** — Necesita razonamiento para mapear criterios funcionales a Escenarios Gherkin y step definitions concretas.

---

## Checklist

- [ ] PRD localizado y criterios AC-XX extraídos
- [ ] Un `.feature` generado por UC con Escenarios por cada AC-XX
- [ ] `.feature` en español con `# language: es` y tags `@US-XX @UC-XXX @AC-XX`
- [ ] `.feature` incluye `Antecedentes` con steps de seed
- [ ] Step definitions generados con el framework BDD del stack
- [ ] Seed strategy generada (SQL functions / JSON fixtures / scripts)
- [ ] Common seed steps creados (`common_steps` + `hooks` con cleanup)
- [ ] Cleanup AfterAll registrado (no en .feature, en hooks)
- [ ] IDs de test con prefijo `e2e-` (determinísticos, sin colisión)
- [ ] Health check verifica acceso a DB antes de ejecutar
- [ ] Seed es idempotente (2 ejecuciones = mismo resultado)
- [ ] Dependencias BDD instaladas si no existían
- [ ] Tests ejecutados con JSON Cucumber report generado
- [ ] Screenshots capturados por escenario
- [ ] `results.json` generado desde JSON Cucumber
- [ ] Evidencia guardada en `.quality/evidence/{feature}/acceptance/`
- [ ] Evidencia adjuntada a Trello (si spec-driven)
- [ ] Cleanup verificado: 0 datos con prefijo `e2e-` tras ejecución
- [ ] Commit de acceptance tests + seed realizado

---

*SpecBox Engine v5.9.0 — Acceptance Tester (Gherkin BDD + E2E Seed Lifecycle)*
