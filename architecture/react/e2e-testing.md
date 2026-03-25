# E2E Testing — React/Next.js con Playwright

> Guía exhaustiva de E2E testing para React/Next.js con Playwright.
> DOM real, selectores estándar, tests cross-browser con HTML report.
> Screenshots automáticos como evidencia de cada paso (PASS/FAIL).

---

## Arquitectura

| Componente | Tecnología | Propósito |
|-----------|-----------|----------|
| Test runner | Playwright | Tests cross-browser con HTML report |
| Framework | Next.js 15 (App Router) | DOM real, selectores estándar |
| Server | `next dev` o `next start` | Dev server o production build |
| Auth | Supabase API + cookie injection | Login sin UI para tests que no prueban auth |
| Evidence | Screenshots automáticos por paso | Adjuntados al HTML report |

---

## Diferencias Clave con Flutter

| Aspecto | Flutter (CanvasKit) | React (Next.js) |
|---------|-------------------|-----------------|
| DOM | NO hay DOM real, accessibility tree | DOM real |
| Selectores | Solo `getByRole()` semánticos | `getByRole()`, `getByTestId()`, `getByText()`, CSS selectors |
| Input | `click()` + `keyboard.type()` obligatorio | `fill()` funciona normalmente |
| Navegación | `window.location.hash` (hash routing) | `page.goto('/route')` funciona |
| Tab entre campos | PROHIBIDO (pierde keystroke) | Funciona normalmente |
| Ready detection | Custom `waitForFlutterReady()` | `page.waitForLoadState('networkidle')` |
| Accessibility | Activación manual necesaria | Nativo del DOM |
| Timeout default | 60s (CanvasKit es lento) | 30s (DOM estándar) |

---

## Estructura de Proyecto E2E

```
e2e/
├── playwright.config.ts            # 3 viewports, HTML reporter, webServer con next
├── .env.test                       # Variables de entorno para test
├── helpers/
│   ├── auth.ts                     # loginViaAPI() con Supabase SSR
│   ├── evidence.ts                 # captureEvidence(), evidenceStep() (IDÉNTICO a Flutter)
│   ├── seed.ts                     # Seed strategy (SQL/Firestore/Mongo) — ver e2e-seed-strategies.md
│   └── test-data.ts                # TEST_USERS constantes
├── seed/
│   └── fixtures/                   # JSON fixtures (solo Firestore/MongoDB)
│       ├── base.json
│       └── uc-XXX-{nombre}.json
├── fixtures/
│   └── base-fixtures.ts            # authenticatedPage, adminPage, etc.
├── tc-01-auth.spec.ts
├── tc-02-main-flow.spec.ts
├── ...
└── tc-NN-edge-cases.spec.ts
```

> **Seed/Cleanup de datos:** Ver `e2e-seed-strategies.md` para la guía completa
> de cómo crear y destruir datos de test por tipo de base de datos (SQL, Firestore, MongoDB).

---

## Configuración Playwright para React/Next.js

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: 'tc-*.spec.ts',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 1,
  reporter: [['html', { outputFolder: 'doc/test_cases/reports' }]],
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'on',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run build && npm run start',
    port: 3000,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
  },
  projects: [
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'tablet',
      use: { ...devices['iPad Pro 11'] },
      grep: /responsive/,
    },
    {
      name: 'mobile',
      use: { ...devices['iPhone 14 Pro'] },
      grep: /responsive/,
    },
  ],
});
```

---

## Auth via Supabase para Next.js

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

  // Para Next.js con Supabase SSR: inyectar cookies
  await page.context().addCookies([
    {
      name: `sb-${new URL(SUPABASE_URL!).hostname.split('.')[0]}-auth-token`,
      value: JSON.stringify({
        access_token: data.session.access_token,
        refresh_token: data.session.refresh_token,
      }),
      domain: 'localhost',
      path: '/',
    },
  ]);
  await page.goto('/');
}
```

---

## Sistema de Evidencias (compartido con Flutter)

El helper `evidenceStep()` es **idéntico** entre Flutter y React:

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

## Patrones de Test para React

### Selectores

```typescript
// React permite selectores estándar (a diferencia de Flutter CanvasKit):
await page.fill('[name="email"]', 'user@example.com');  // ✅ Funciona
await page.getByRole('textbox', { name: 'Email' }).fill('user@example.com');  // ✅ Preferido
await page.getByTestId('email-input').fill('user@example.com');  // ✅ También válido
```

**Orden de preferencia de selectores:**
1. `getByRole()` — Accesibilidad, más resiliente
2. `getByText()` / `getByLabel()` — Semánticos
3. `getByTestId()` — Cuando no hay semántica adecuada
4. CSS selectors — Último recurso

### Navegación

```typescript
// Navegación directa (no hash routing como Flutter):
await page.goto('/dashboard');  // ✅ Funciona
await page.goto('/settings');   // ✅ Funciona

// Esperar contenido:
await page.waitForLoadState('networkidle');
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
```

### Formularios

```typescript
// fill() funciona normalmente con DOM real:
await page.getByLabel('Email').fill('user@example.com');
await page.getByLabel('Password').fill('SecurePass123!');
await page.getByRole('button', { name: 'Sign In' }).click();

// Tab funciona normalmente:
await page.keyboard.press('Tab');
await page.keyboard.type('next field value');  // ✅ Sin pérdida de keystroke
```

### Esperas

```typescript
// Esperar a que la página cargue completamente:
await page.waitForLoadState('networkidle');

// Esperar elemento específico:
await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible({ timeout: 10_000 });

// Esperar navegación:
await page.waitForURL('/dashboard');

// Esperar respuesta de API:
const responsePromise = page.waitForResponse('**/api/users');
await page.getByRole('button', { name: 'Load' }).click();
await responsePromise;
```

---

## Fixtures

```typescript
import { test as base, Page } from '@playwright/test';
import { loginViaAPI } from '../helpers/auth';
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

## Test Data

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
};
```

---

## Ejecución

```bash
# Build + ejecutar tests
npm run build && npx playwright test

# Solo tests (requiere build previo o dev server)
npx playwright test

# Un test case específico
npx playwright test e2e/tc-01

# Ver HTML report
npx playwright show-report doc/test_cases/reports

# Con browser visible (debug)
npx playwright test --headed

# Solo un viewport
npx playwright test --project=desktop-chrome

# Con trace viewer
npx playwright test --trace on
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

| Acción | React/Next.js | Flutter (CanvasKit) |
|--------|--------------|---------------------|
| Encontrar input | `getByRole()`, `getByTestId()`, CSS | Solo `getByRole()` |
| Escribir texto | `fill()` | `click()` + `keyboard.type()` |
| Cambiar campo | `Tab` o `click()` | Solo `click()` |
| Navegar | `page.goto('/route')` | `window.location.hash` |
| Esperar carga | `waitForLoadState()` | `waitForFlutterReady()` custom |
| Activar a11y | No necesario | `enableAccessibility()` manual |
| Select/Dropdown | `selectOption()` | `getByRole('combobox')` + click |

---

## Seed y Cleanup de Datos

Los tests E2E necesitan datos reales en la DB. El ciclo completo es:

```
beforeAll → seed_e2e_base() + seed_e2e_{uc}() → datos creados
tests     → ejecutan contra datos reales
afterAll  → cleanup_e2e() → datos eliminados
```

**Guía completa:** `architecture/react/e2e-seed-strategies.md`

| Backend | Seed | Cleanup | Auth users |
|---------|------|---------|------------|
| Supabase (SQL) | `supabase.rpc('seed_e2e_...')` | `supabase.rpc('cleanup_e2e')` | SQL INSERT en `auth.users` |
| Firestore | Admin SDK batch writes | `db.recursiveDelete()` | `auth.createUser()` |
| MongoDB | `insertMany` | `deleteMany({_id: /^e2e-/})` | Depende del auth provider |

**Reglas clave:**
- IDs determinísticos con prefijo `e2e-`
- Cleanup en `afterAll` (nunca en el `.feature`)
- Seed idempotente (cleanup interno al inicio)
- Campos varchar en `auth.users` Supabase: `''` nunca `NULL`

---

*Referencia: SpecBox Engine v5.9.0 "E2E Sentinel + Seed Lifecycle"*
