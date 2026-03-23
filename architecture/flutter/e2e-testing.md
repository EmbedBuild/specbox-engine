# E2E Testing — Flutter Web con Playwright

> Guía exhaustiva de E2E testing para Flutter web (CanvasKit) con Playwright.
> Validación de flujos completos: auth, navegación, interacciones, responsive.
> Genera HTML report con screenshots como evidencia de cada paso (PASS/FAIL).

---

## Arquitectura

| Componente | Tecnología | Propósito |
|-----------|-----------|----------|
| Test runner | Playwright | Tests cross-browser con HTML report |
| Renderer | CanvasKit (default) | Genera `<canvas>` + accessibility tree |
| Server | `npx serve` con flag `-s` | SPA fallback para GoRouter hash routing |
| Auth | Supabase API + localStorage injection | Login sin UI para tests que no prueban auth |
| Evidence | Screenshots automáticos por paso | Adjuntados al HTML report |

---

## Reglas Críticas — CanvasKit

### 1. NO usar `fill()` ni `type()` de Playwright

CanvasKit no genera `<input>` DOM. El accessibility tree crea nodos semánticos.

```typescript
// ✅ Correcto
const emailInput = page.getByRole('textbox', { name: 'Correo electrónico' });
await emailInput.click();
await page.keyboard.type('user@example.com', { delay: 10 });

// ❌ NUNCA
await page.fill('#email', 'user@example.com');   // No hay DOM
await page.locator('input').fill('...');          // No hay <input>
```

### 2. NO usar Tab para navegar entre campos

Tab pierde el primer keystroke del siguiente campo en CanvasKit.

```typescript
// ✅ Correcto
await nextField.click();
await page.waitForTimeout(200);
await page.keyboard.type('value', { delay: 10 });

// ❌ NUNCA
await page.keyboard.press('Tab');
await page.keyboard.type('value');  // Pierde el primer carácter
```

### 3. Hash Routing

Flutter GoRouter usa `/#/route`. `page.goto('/route')` causa reload completo y pierde auth.

```typescript
// ✅ Correcto
await page.evaluate(r => window.location.hash = r, '/target-route');
await page.waitForTimeout(2000);

// ❌ NUNCA (pierde auth state)
await page.goto('/target-route');
```

### 4. Accessibility Tree Activation

CanvasKit tiene un botón oculto off-viewport que debe activarse para que aparezcan nodos semánticos.

```typescript
async function enableAccessibility(page: Page) {
  await page.evaluate(() => {
    const btn = document.querySelector('flt-semantics-placeholder button');
    btn?.dispatchEvent(new Event('click', { bubbles: true }));
  });
  await page.waitForTimeout(1000);
}
```

### 5. Flutter Ready Detection

```typescript
async function waitForFlutterReady(page: Page) {
  await page.waitForFunction(
    () => document.querySelector('flutter-view')
      && (document.querySelector('flt-semantics-placeholder')
          || document.querySelectorAll('flt-semantics').length > 0),
    { timeout: 30_000 }
  );
  await enableAccessibility(page);
}
```

---

## Estructura de Proyecto E2E

```
e2e/
├── package.json                    # @playwright/test, @supabase/supabase-js, firebase-admin, serve, dotenv
├── tsconfig.json
├── playwright.config.ts            # 3 viewports, HTML reporter, webServer
├── .env                            # SUPABASE_URL / FIREBASE_SERVICE_ACCOUNT (gitignored)
├── helpers/
│   ├── flutter-web.ts              # waitForFlutterReady(), navigateToRoute(), waitForRoute()
│   ├── auth.ts                     # loginViaAPI() (token injection), loginViaUI()
│   ├── evidence.ts                 # captureEvidence(), evidenceStep()
│   ├── seed.ts                     # Seed strategy (SQL/Firestore) — ver e2e-seed-strategies.md
│   └── test-data.ts                # TEST_USERS constantes
├── seed/
│   └── fixtures/                   # JSON fixtures (solo Firestore/MongoDB)
│       ├── base.json
│       └── uc-XXX-{nombre}.json
├── fixtures/
│   └── base-fixtures.ts            # playerPage, coachPage, adminPage pre-autenticados
├── tc-01-auth.spec.ts              # Auth + onboarding
├── tc-02-feature-flow.spec.ts      # Flujo principal
├── ...
└── tc-NN-edge-cases.spec.ts
```

> **Seed/Cleanup de datos:** Ver `e2e-seed-strategies.md` para la guía completa
> de cómo crear y destruir datos de test por tipo de base de datos (Firestore, SQL, MongoDB).

---

## Configuración Playwright para Flutter

```typescript
import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
dotenv.config();

export default defineConfig({
  testDir: '.',
  testMatch: 'tc-*.spec.ts',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [['html', { outputFolder: '../doc/test_cases/reports' }]],
  use: {
    screenshot: 'on',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    locale: 'es-ES',
  },
  webServer: {
    command: 'npx serve ../build/web -s -l 4200',
    port: 4200,
    timeout: 15_000,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: 'desktop-chrome',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'tablet',
      use: {
        ...devices['iPad Pro 11'],
        viewport: { width: 810, height: 1080 },
      },
      grep: /responsive/,
    },
    {
      name: 'mobile',
      use: {
        ...devices['iPhone 14 Pro'],
        viewport: { width: 393, height: 852 },
      },
      grep: /responsive/,
    },
  ],
});
```

---

## Sistema de Evidencias

```typescript
import { Page, TestInfo } from '@playwright/test';

export async function evidenceStep(
  page: Page, testInfo: TestInfo,
  tcId: string, stepNumber: number,
  description: string, action: () => Promise<void>
): Promise<void> {
  const stepId = `${tcId}-paso-${stepNumber}`;
  testInfo.annotations.push({
    type: 'test-case-step',
    description: `[${stepId}] ${description}`,
  });
  try {
    await action();
    const screenshot = await page.screenshot({ fullPage: true });
    await testInfo.attach(`${stepId}: PASS - ${description}`, {
      body: screenshot, contentType: 'image/png',
    });
  } catch (error) {
    const screenshot = await page.screenshot({ fullPage: true });
    await testInfo.attach(`${stepId}: FAIL - ${description}`, {
      body: screenshot, contentType: 'image/png',
    });
    throw error;
  }
}
```

---

## Auth via Supabase API

```typescript
import { createClient } from '@supabase/supabase-js';
import { Page } from '@playwright/test';

const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY;

interface TestUser {
  email: string;
  password: string;
  role: string;
}

export async function loginViaAPI(page: Page, user: TestUser): Promise<void> {
  const client = createClient(SUPABASE_URL!, SUPABASE_ANON_KEY!);
  const { data } = await client.auth.signInWithPassword({
    email: user.email, password: user.password,
  });
  if (!data.session) throw new Error(`Login failed for ${user.email}`);
  await page.goto('/');
  await waitForFlutterReady(page);
  await page.evaluate((session) => {
    const key = `sb-${new URL('${SUPABASE_URL}').hostname.split('.')[0]}-auth-token`;
    localStorage.setItem(key, JSON.stringify(session));
  }, data.session);
  await page.reload();
  await waitForFlutterReady(page);
}
```

**Nota:** La función `loginViaAPI` realiza:
1. Login via Supabase SDK (sin UI)
2. Navega a la raíz para iniciar Flutter
3. Inyecta el token en localStorage
4. Recarga para que Flutter lea el token

---

## Cuentas E2E en Supabase — GOTCHA CRÍTICO

Al crear usuarios via SQL INSERT en `auth.users`, **TODOS los campos varchar** deben ser `''` (string vacío), **NO `NULL`**:

```sql
INSERT INTO auth.users (
  id, email, encrypted_password, email_confirmed_at,
  email_change, email_change_token_new, email_change_token_current,
  phone_change, phone_change_token,
  confirmation_token, recovery_token, reauthentication_token,
  role, aud, created_at, updated_at
) VALUES (
  gen_random_uuid(), 'e2e-user@test.com', crypt('password123', gen_salt('bf')),
  now(),
  '', '', '',   -- email_change fields: NUNCA NULL
  '', '',       -- phone_change fields: NUNCA NULL
  '', '', '',   -- token fields: NUNCA NULL
  'authenticated', 'authenticated', now(), now()
);
```

**Por qué:** GoTrue (Go) no puede scanear `NULL` en tipo `string` → causa HTTP 500 "Database error querying schema".

---

## Helpers Reutilizables

### flutter-web.ts

```typescript
import { Page } from '@playwright/test';

export async function enableAccessibility(page: Page): Promise<void> {
  await page.evaluate(() => {
    const btn = document.querySelector('flt-semantics-placeholder button');
    btn?.dispatchEvent(new Event('click', { bubbles: true }));
  });
  await page.waitForTimeout(1000);
}

export async function waitForFlutterReady(page: Page): Promise<void> {
  await page.waitForFunction(
    () => document.querySelector('flutter-view')
      && (document.querySelector('flt-semantics-placeholder')
          || document.querySelectorAll('flt-semantics').length > 0),
    { timeout: 30_000 }
  );
  await enableAccessibility(page);
}

export async function navigateToRoute(page: Page, route: string): Promise<void> {
  await page.evaluate(r => window.location.hash = r, route);
  await page.waitForTimeout(2000);
}

export async function waitForRoute(page: Page, route: string, timeout = 10_000): Promise<void> {
  await page.waitForFunction(
    (r) => window.location.hash.includes(r),
    route,
    { timeout }
  );
}
```

### test-data.ts

```typescript
export interface TestUser {
  email: string;
  password: string;
  role: string;
}

export const TEST_USERS: Record<string, TestUser> = {
  admin: {
    email: 'e2e-admin@test.com',
    password: 'TestPassword123!',
    role: 'admin',
  },
  user: {
    email: 'e2e-user@test.com',
    password: 'TestPassword123!',
    role: 'user',
  },
  // Añadir más roles según el proyecto
};
```

---

## Fixtures

```typescript
import { test as base, Page } from '@playwright/test';
import { loginViaAPI } from '../helpers/auth';
import { waitForFlutterReady } from '../helpers/flutter-web';
import { TEST_USERS } from '../helpers/test-data';

type Fixtures = {
  authenticatedPage: Page;
  adminPage: Page;
};

export const test = base.extend<Fixtures>({
  authenticatedPage: async ({ page }, use) => {
    await loginViaAPI(page, TEST_USERS.user);
    await use(page);
  },
  adminPage: async ({ page }, use) => {
    await loginViaAPI(page, TEST_USERS.admin);
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

---

## Ejecución

```bash
# Build Flutter web + ejecutar tests
cd e2e && npm run build-and-test

# Solo tests (requiere build previo)
cd e2e && npm test

# Un test case específico
cd e2e && npx playwright test tc-01

# Ver HTML report
cd e2e && npx playwright show-report ../doc/test_cases/reports

# Con browser visible (debug)
cd e2e && npx playwright test --headed

# Solo un viewport
cd e2e && npx playwright test --project=desktop-chrome
```

### package.json scripts

```json
{
  "scripts": {
    "test": "npx playwright test",
    "build-and-test": "cd .. && flutter build web --wasm && cd e2e && npx playwright test",
    "report": "npx playwright show-report ../doc/test_cases/reports"
  }
}
```

---

## Cobertura E2E Mínima

| Área | Tests mínimos |
|------|--------------|
| Auth (login/register) | 5-7 |
| Flujo principal | 5-10 |
| Settings/perfil | 3-5 |
| Roles especializados | 5-8 |
| Edge cases | 5-8 |
| Responsive (3 viewports) | 10+ screenshots |

**Total mínimo:** 30+ tests

---

## Tabla de Referencia Rápida

| Acción | CanvasKit | DOM estándar |
|--------|-----------|-------------|
| Encontrar input | `getByRole('textbox', { name })` | `locator('input')`, `fill()` |
| Escribir texto | `click()` + `keyboard.type({ delay: 10 })` | `fill()` |
| Cambiar campo | `click()` en siguiente campo | `Tab` o `click()` |
| Navegar | `window.location.hash = route` | `page.goto('/route')` |
| Esperar carga | `waitForFlutterReady()` custom | `waitForLoadState()` |
| Activar a11y | `enableAccessibility()` manual | Nativo |
| Dropdown/Select | `getByRole('combobox')` + `click` opción | `selectOption()` |

---

## Seed y Cleanup de Datos

Los tests E2E necesitan datos reales en la DB. El ciclo completo es:

```
beforeAll → seed (base + UC-specific) → datos creados
tests     → ejecutan contra datos reales
afterAll  → cleanup → datos eliminados
```

**Guía completa:** `architecture/flutter/e2e-seed-strategies.md`

| Backend | Seed | Cleanup | Auth users |
|---------|------|---------|------------|
| Firestore | Admin SDK batch writes + JSON fixtures | `db.recursiveDelete()` | `auth.createUser()` |
| Supabase (SQL) | `supabase.rpc('seed_e2e_...')` | `supabase.rpc('cleanup_e2e')` | SQL INSERT en `auth.users` |

**Reglas clave:**
- IDs determinísticos con prefijo `e2e-`
- Cleanup en `afterAll` (nunca en el `.feature`)
- Seed idempotente (cleanup interno al inicio)
- Firebase Emulator para CI (`FIRESTORE_EMULATOR_HOST`)
- Auth injection: localStorage key `firebase:authUser:{apiKey}:[DEFAULT]`

---

*Referencia: SpecBox Engine v5.6.0 "E2E Sentinel + Seed Lifecycle"*
