# AG-09a: Acceptance Tester

> SpecBox Engine v5.11.0
> Genera archivos `.feature` (Gherkin en español) + step definitions + E2E tests reales con Playwright.
> Para Flutter y React: genera tests E2E reales contra la app corriendo (browser).
> Para Python: genera tests de integración HTTP. Para GAS: tests con jest-cucumber.
> NO es AG-04 (QA). AG-04 genera unit tests. AG-09a genera E2E acceptance tests con evidencia visual.

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

### Flutter (Playwright E2E contra CanvasKit web build)

> **IMPORTANTE**: Flutter usa Playwright contra web build CanvasKit, NO widget tests.
> Los widget tests son AG-04 (unit). AG-09a genera E2E reales en browser.
> Referencia completa: `architecture/flutter/e2e-testing.md`

```json
// package.json en e2e/ — devDependencies requeridas
{
  "devDependencies": {
    "playwright-bdd": "^8.4.2",
    "@playwright/test": "^1.40.0"
  }
}
```

```typescript
// e2e/acceptance/steps/UC-XXX_steps.ts
import { Given, When, Then } from 'playwright-bdd';
import { expect } from '@playwright/test';
import { evidenceStep } from '../../helpers/evidence';

Given('el usuario está autenticado como {string}', async ({ page, testInfo }, actor: string) => {
  await evidenceStep(page, testInfo, 'setup', 0, `Auth como ${actor}`, async () => {
    // Supabase API → localStorage injection → reload
    // Ver architecture/flutter/e2e-testing.md para auth rápida
  });
});

When('el usuario completa el formulario con {string} = {string}', async ({ page, testInfo }, campo: string, valor: string) => {
  await evidenceStep(page, testInfo, 'AC-XX', 1, `Completar ${campo}`, async () => {
    // CanvasKit: usar getByRole() semánticos, NUNCA selectores DOM
    await page.getByRole('textbox', { name: campo }).click();
    await page.keyboard.type(valor, { delay: 10 });
  });
});

Then('se muestra el mensaje {string}', async ({ page, testInfo }, mensaje: string) => {
  await evidenceStep(page, testInfo, 'AC-XX', 2, `Verificar "${mensaje}"`, async () => {
    await expect(page.getByText(mensaje)).toBeVisible();
  });
});
```

**Pre-requisito: build web antes de tests:**
```bash
flutter build web --web-renderer canvaskit --release
```

**Ejecución:**
```bash
npx bddgen && npx playwright test e2e/acceptance/ --reporter=html,json
```

**Notas CanvasKit:**
- Selectores: SIEMPRE `getByRole()` semánticos (CanvasKit no genera DOM HTML real)
- Input: `click()` + `keyboard.type({ delay: 10 })`, NUNCA `fill()`
- Navegación: `window.location.hash`, NUNCA `page.goto('/route')` (pierde auth)
- Tab: NUNCA usar Tab entre campos (pierde primer keystroke)

### React (Playwright E2E real con evidenceStep)

> **IMPORTANTE**: React usa Playwright E2E real contra la app corriendo.
> Cada paso captura screenshot automaticamente via `evidenceStep()`.
> Referencia completa: `architecture/react/e2e-testing.md`

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
import { evidenceStep } from '../../helpers/evidence';

Given('el usuario está autenticado como {string}', async ({ page, testInfo }, actor: string) => {
  await evidenceStep(page, testInfo, 'setup', 0, `Auth como ${actor}`, async () => {
    await page.goto('/login');
    await page.fill('[name="email"]', `${actor}@test.com`);
    await page.fill('[name="password"]', 'test-password');
    await page.click('button[type="submit"]');
    await page.waitForURL('/dashboard');
  });
});

When('el usuario completa el formulario con {string} = {string}', async ({ page, testInfo }, campo: string, valor: string) => {
  await evidenceStep(page, testInfo, 'AC-XX', 1, `Completar ${campo}`, async () => {
    await page.fill(`[name="${campo}"]`, valor);
  });
});

Then('se muestra el mensaje {string}', async ({ page, testInfo }, mensaje: string) => {
  await evidenceStep(page, testInfo, 'AC-XX', 2, `Verificar "${mensaje}"`, async () => {
    await expect(page.getByText(mensaje)).toBeVisible();
  });
});
```

**Configurar en `playwright.config.ts`:**
```typescript
use: {
  screenshot: 'on',              // Screenshot en cada test
  video: 'retain-on-failure',    // Video solo en fallos
  trace: 'retain-on-failure',    // Trace solo en fallos
},
reporter: [
  ['html', { outputFolder: 'doc/test_cases/reports', open: 'never' }],
  ['json', { outputFile: 'tests/acceptance/reports/playwright-results.json' }],
],
```

**Ejecución:**
```bash
npx bddgen && npx playwright test tests/acceptance/ --reporter=html,json
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
| Flutter | `cd e2e && npm install -D playwright-bdd @playwright/test && npx playwright install` |
| React | `npm install -D playwright-bdd @playwright/test && npx playwright install` |
| Python | `pip install pytest-bdd` |
| GAS | `npm install -D jest-cucumber` |

### 5. Ejecutar tests

| Stack | Comando | Reporter |
|-------|---------|----------|
| Flutter | `cd e2e && npx bddgen && npx playwright test e2e/acceptance/ --reporter=html,json` | HTML + JSON |
| React | `npx bddgen && npx playwright test tests/acceptance/ --reporter=html,json` | HTML + JSON |
| Python | `pytest tests/acceptance/ --cucumberjson=tests/acceptance/reports/cucumber-report.json` | JSON |
| GAS | `npx jest tests/acceptance/ --json --outputFile=tests/acceptance/reports/cucumber-report.json` | JSON |

**OBLIGATORIO para Flutter y React**: Usar reporter `html` para generar informe visual con screenshots embebidos.

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

### 8. Generar HTML Evidence Report (Flutter y React OBLIGATORIO)

> Para Flutter y React, AG-09a DEBE generar un informe HTML self-contained
> con screenshots embebidos base64 que el humano pueda abrir en cualquier browser.

**Archivo de salida:** `.quality/evidence/{feature}/acceptance/e2e-evidence-report.html`

**Proceso:**
1. Leer `results.json` generado en paso 7
2. Para cada AC-XX con screenshot, leer el PNG y convertir a base64
3. Generar HTML usando el template de `doc/templates/e2e-evidence-report-template.md`
4. El HTML DEBE ser self-contained (CSS inline, imagenes base64, sin dependencias externas)

**Contenido del informe:**

```
┌─────────────────────────────────────────────┐
│  E2E Evidence Report                        │
│  Feature: {feature} | UC: {uc_id}           │
│  {timestamp} | Pass Rate: XX%               │
├─────────────────────────────────────────────┤
│  Summary                                    │
│  ✅ 4 passed  ❌ 1 failed  ⏭️ 0 skipped     │
│  Duration: 12.3s | Viewports: 3             │
├─────────────────────────────────────────────┤
│  AC-01: Crear nuevo registro     ✅ PASS    │
│  ┌─────────────────────────────────────┐    │
│  │  [Screenshot fullpage embebido]     │    │
│  └─────────────────────────────────────┘    │
│  Steps: Dado → Cuando → Entonces (1.2s)    │
├─────────────────────────────────────────────┤
│  AC-02: Validar campo obligatorio ❌ FAIL   │
│  ┌─────────────────────────────────────┐    │
│  │  [Screenshot del estado al fallar]  │    │
│  └─────────────────────────────────────┘    │
│  Error: Expected 'error visible'...        │
│  Steps: Dado ✅ → Cuando ✅ → Entonces ❌   │
├─────────────────────────────────────────────┤
│  Viewport Coverage                          │
│  Desktop ✅ | Tablet ✅ | Mobile ✅          │
└─────────────────────────────────────────────┘
```

**Implementacion (script inline en step definitions):**

```typescript
// Añadir al final del test run (afterAll o reporter custom)
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join, resolve } from 'path';

function generateEvidenceReport(feature: string, ucId: string, evidenceDir: string) {
  const resultsPath = join(evidenceDir, 'results.json');
  if (!existsSync(resultsPath)) return;

  const results = JSON.parse(readFileSync(resultsPath, 'utf-8'));
  const totalPass = results.results.filter((r: any) => r.status === 'PASS').length;
  const totalFail = results.results.filter((r: any) => r.status === 'FAIL').length;
  const passRate = Math.round((totalPass / results.tests_total) * 100);

  let screenshotCards = '';
  for (const r of results.results) {
    let imgTag = '<p style="color:#999;font-style:italic">No screenshot captured</p>';
    if (r.screenshot) {
      const imgPath = join(evidenceDir, r.screenshot);
      if (existsSync(imgPath)) {
        const b64 = readFileSync(imgPath).toString('base64');
        imgTag = `<img src="data:image/png;base64,${b64}" style="max-width:100%;border:1px solid #e5e7eb;border-radius:8px;" />`;
      }
    }
    const statusBadge = r.status === 'PASS'
      ? '<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:4px;font-size:13px">PASS</span>'
      : '<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:4px;font-size:13px">FAIL</span>';

    const stepsHtml = (r.steps || []).map((s: any) =>
      `<span style="color:${s.status === 'PASS' ? '#22c55e' : '#ef4444'}">${s.keyword}</span> ${s.text}`
    ).join(' → ');

    const errorHtml = r.error
      ? `<pre style="background:#fef2f2;border:1px solid #fecaca;padding:8px;border-radius:4px;font-size:12px;overflow-x:auto">${r.error}</pre>`
      : '';

    screenshotCards += `
      <div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="margin:0;font-size:16px">${r.id}: ${r.scenario}</h3>
          ${statusBadge}
        </div>
        ${imgTag}
        <div style="margin-top:8px;font-size:13px;color:#6b7280">${stepsHtml}</div>
        <div style="margin-top:4px;font-size:12px;color:#9ca3af">Duration: ${r.duration_ms}ms</div>
        ${errorHtml}
      </div>`;
  }

  const html = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>E2E Evidence — ${ucId}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; background: #fafafa; color: #1f2937; }
    .header { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    .header h1 { margin: 0 0 8px 0; font-size: 24px; }
    .header .meta { color: #6b7280; font-size: 14px; }
    .summary { display: flex; gap: 16px; margin: 16px 0; }
    .summary .card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; flex: 1; text-align: center; }
    .summary .card .number { font-size: 28px; font-weight: bold; }
    .summary .card .label { font-size: 12px; color: #6b7280; text-transform: uppercase; }
    .pass-rate { font-size: 48px; font-weight: bold; color: ${passRate >= 80 ? '#22c55e' : passRate >= 50 ? '#eab308' : '#ef4444'}; }
    .footer { text-align: center; color: #9ca3af; font-size: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; }
  </style>
</head>
<body>
  <div class="header">
    <h1>E2E Evidence Report</h1>
    <div class="meta">
      Feature: <strong>${feature}</strong> | UC: <strong>${ucId}</strong> | US: <strong>${results.us_id || 'N/A'}</strong><br>
      Generated: ${new Date().toISOString().replace('T', ' ').slice(0, 19)} UTC
    </div>
  </div>

  <div class="summary">
    <div class="card">
      <div class="pass-rate">${passRate}%</div>
      <div class="label">Pass Rate</div>
    </div>
    <div class="card">
      <div class="number" style="color:#22c55e">${totalPass}</div>
      <div class="label">Passed</div>
    </div>
    <div class="card">
      <div class="number" style="color:#ef4444">${totalFail}</div>
      <div class="label">Failed</div>
    </div>
    <div class="card">
      <div class="number">${results.tests_total}</div>
      <div class="label">Total</div>
    </div>
  </div>

  <h2 style="font-size:18px;margin:24px 0 12px">Acceptance Criteria Evidence</h2>
  ${screenshotCards}

  <div class="footer">
    SpecBox Engine v5.11.0 — AG-09a Acceptance Tester<br>
    Generated automatically from E2E test execution
  </div>
</body>
</html>`;

  writeFileSync(join(evidenceDir, 'e2e-evidence-report.html'), html, 'utf-8');
}
```

### 9. Adjuntar evidencia a Trello/Plane/FreeForm (si spec-driven)

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
- [ ] HTML Evidence Report generado (Flutter/React OBLIGATORIO)
- [ ] Evidencia adjuntada a Trello/Plane/FreeForm (si spec-driven)
- [ ] Cleanup verificado: 0 datos con prefijo `e2e-` tras ejecución
- [ ] Commit de acceptance tests + seed + evidence report realizado

---

*SpecBox Engine v5.11.0 — Acceptance Tester (E2E Playwright + Gherkin BDD + Evidence Reports)*
