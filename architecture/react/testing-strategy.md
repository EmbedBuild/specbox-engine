# Estrategia de Testing — React/Next.js

## Tipos de Tests

| Tipo | Qué testear | Cuándo | Herramientas |
|------|-------------|--------|--------------|
| **Unit** | Hooks, stores, utils, services | Siempre | `vitest`, `@testing-library/react` |
| **Component** | Renders, interacciones, formularios | Siempre | `@testing-library/react`, `vitest` |
| **E2E** | Flujos completos cross-browser | Features críticas | `playwright` |
| **Acceptance** | Criterios AC-XX del PRD | Siempre (si hay PRD) | `playwright` |

## Screen Sizes para Tests

```typescript
const viewports = {
  mobile: { width: 393, height: 852 },   // iPhone 14 Pro
  tablet: { width: 810, height: 1080 },  // iPad Pro 11
  desktop: { width: 1280, height: 720 }, // Desktop Chrome
};
```

---

## Unit Tests (Vitest + Testing Library)

### Setup

```json
// package.json
{
  "devDependencies": {
    "vitest": "^3.x",
    "@testing-library/react": "^16.x",
    "@testing-library/jest-dom": "^6.x",
    "@testing-library/user-event": "^14.x",
    "jsdom": "^25.x"
  }
}
```

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      thresholds: {
        global: {
          branches: 85,
          functions: 85,
          lines: 85,
          statements: 85,
        },
      },
    },
  },
});
```

### Estructura

```
tests/
├── setup.ts                        # Testing Library + matchers
├── unit/
│   ├── hooks/
│   │   └── use-auth.test.ts
│   ├── stores/
│   │   └── user-store.test.ts
│   └── utils/
│       └── format-date.test.ts
├── components/
│   ├── ui/
│   │   └── button.test.tsx
│   └── features/
│       └── login-form.test.tsx
└── acceptance/
    ├── ac-01-user-login.spec.ts
    └── ac-02-create-item.spec.ts
```

### Template: Hook Test

```typescript
// tests/unit/hooks/use-auth.test.ts
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useAuth } from '@/hooks/use-auth';

describe('useAuth', () => {
  it('initial state is unauthenticated', () => {
    const { result } = renderHook(() => useAuth());
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('login sets user and authenticated state', async () => {
    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.login('test@test.com', 'password123');
    });

    expect(result.current.user).not.toBeNull();
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('logout clears user state', async () => {
    const { result } = renderHook(() => useAuth());

    await act(async () => {
      await result.current.login('test@test.com', 'password123');
    });
    await act(async () => {
      await result.current.logout();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
});
```

### Template: Zustand Store Test

```typescript
// tests/unit/stores/user-store.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { useUserStore } from '@/stores/user-store';

describe('useUserStore', () => {
  beforeEach(() => {
    useUserStore.setState({ user: null, loading: false });
  });

  it('initial state is correct', () => {
    const state = useUserStore.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(false);
  });

  it('setUser updates user', () => {
    useUserStore.getState().setUser({ id: '1', name: 'Test' });
    expect(useUserStore.getState().user).toEqual({ id: '1', name: 'Test' });
  });
});
```

---

## Component Tests (Testing Library)

### Template: Component Test

```tsx
// tests/components/features/login-form.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { LoginForm } from '@/components/features/login-form';

describe('LoginForm', () => {
  it('renders email and password fields', () => {
    render(<LoginForm onSubmit={vi.fn()} />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('calls onSubmit with form values', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<LoginForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/email/i), 'test@test.com');
    await user.type(screen.getByLabelText(/password/i), 'password123');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      email: 'test@test.com',
      password: 'password123',
    });
  });

  it('shows validation errors for empty fields', async () => {
    const user = userEvent.setup();
    render(<LoginForm onSubmit={vi.fn()} />);

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(screen.getByText(/email is required/i)).toBeInTheDocument();
  });
});
```

### Responsive Component Test

```tsx
// tests/components/features/dashboard-layout.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { DashboardLayout } from '@/components/features/dashboard-layout';

const viewports = {
  mobile: 393,
  tablet: 810,
  desktop: 1280,
};

describe('DashboardLayout responsive', () => {
  Object.entries(viewports).forEach(([name, width]) => {
    it(`renders correctly on ${name} (${width}px)`, () => {
      // Mock window.innerWidth
      Object.defineProperty(window, 'innerWidth', { value: width, writable: true });
      window.dispatchEvent(new Event('resize'));

      render(<DashboardLayout />);

      if (width < 600) {
        expect(screen.getByTestId('mobile-nav')).toBeInTheDocument();
      } else if (width < 1024) {
        expect(screen.getByTestId('tablet-nav')).toBeInTheDocument();
      } else {
        expect(screen.getByTestId('desktop-sidebar')).toBeInTheDocument();
      }
    });
  });
});
```

---

## Acceptance Testing (BDD)

> Tests de aceptación basados en Gherkin que validan AC-XX directamente desde archivos `.feature`.
> Cada UC genera un `.feature`, cada AC genera un Escenario.

### Setup

```json
// package.json
{
  "devDependencies": {
    "playwright-bdd": "^8.4.2",
    "@playwright/test": "^1.x"
  }
}
```

### Ejemplo .feature

```gherkin
# language: es
# tests/acceptance/features/UC-001_crear_propiedad.feature

@US-01 @UC-001
Característica: Crear propiedad
  Como propietario
  Quiero crear una propiedad con nombre, dirección y foto
  Para gestionar mis inmuebles

  Antecedentes:
    Dado que estoy autenticado como "propietario"
    Y estoy en la página de propiedades

  @AC-01
  Escenario: Crear propiedad con datos válidos
    Cuando completo el campo "nombre" con "Depto Centro"
    Y completo el campo "dirección" con "Av. Libertador 1234"
    Y adjunto una foto de la propiedad
    Y presiono "Guardar"
    Entonces veo "Depto Centro" en el listado de propiedades
    Y capturo screenshot de evidencia
```

### Step Definition (TypeScript)

```typescript
// tests/acceptance/steps/UC-001_steps.ts
import { createBdd } from 'playwright-bdd';
import { expect } from '@playwright/test';

const { Given, When, Then } = createBdd();

Given('que estoy autenticado como {string}', async ({ page }, role: string) => {
  // Auth via API + cookie injection
  await page.goto('/login');
  await page.getByLabel('Email').fill(`${role}@test.com`);
  await page.getByLabel('Password').fill('password123');
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL('/dashboard');
});

When('completo el campo {string} con {string}', async ({ page }, campo: string, valor: string) => {
  await page.getByLabel(campo).fill(valor);
});

When('presiono {string}', async ({ page }, boton: string) => {
  await page.getByRole('button', { name: boton }).click();
});

Then('veo {string} en el listado de propiedades', async ({ page }, texto: string) => {
  await expect(page.getByText(texto)).toBeVisible();
});

Then('capturo screenshot de evidencia', async ({ page }, testInfo) => {
  await page.screenshot({
    path: `tests/acceptance/reports/${testInfo.title}.png`,
  });
});
```

### Ejecución

```bash
# Generar tests desde .feature + ejecutar
npx bddgen && npx playwright test tests/acceptance/

# Con HTML report
npx bddgen && npx playwright test tests/acceptance/ --reporter=html
```

### Report

- Formato: JSON Cucumber estándar
- Ubicación: `tests/acceptance/reports/cucumber-report.json`
- PDF de evidencia generado y adjuntado a card UC en Trello (si spec-driven)

### Estructura

```
tests/acceptance/
├── features/
│   ├── UC-001_crear_propiedad.feature
│   └── UC-002_listar_propiedades.feature
├── steps/
│   ├── common_steps.ts         # Auth, navegación, assertions
│   └── UC-001_steps.ts         # Steps específicos del UC
└── reports/
    ├── cucumber-report.json
    └── acceptance-report.pdf
```

---

## E2E Tests (Playwright)

> Tests end-to-end contra Next.js build con Playwright.
> Validan flujos completos: auth, navegación, interacciones.
> Generan HTML report con screenshots como evidencia.

| Aspecto | Detalle |
|---------|---------|
| Framework | Playwright |
| DOM | Real (selectores estándar) |
| Selectores | `getByRole()` preferido, `getByTestId()`, CSS también válidos |
| Input | `fill()` funciona normalmente |
| Navegación | `page.goto('/route')` funciona |
| Auth | Supabase API → cookie injection |
| Evidence | Screenshots por paso (PASS/FAIL) en HTML report |

Ver guía completa: `architecture/react/e2e-testing.md`

### Cobertura E2E Mínima

| Área | Tests mínimos |
|------|--------------|
| Auth (login/register) | 5-7 |
| Flujo principal | 5-10 |
| Settings/perfil | 3-5 |
| Roles especializados | 5-8 |
| Edge cases | 5-8 |
| Responsive (3 viewports) | 10+ screenshots |

---

## Acceptance Tests (Playwright)

> Tests E2E que validan acceptance criteria (AC-XX) del PRD con evidencia visual.
> Generados por AG-09a. Validados por AG-09b.

### Template: Acceptance Test

```typescript
// tests/acceptance/ac-01-user-login.spec.ts
import { test, expect } from '@playwright/test';
import { evidenceStep } from '../helpers/evidence';

test.describe('AC-01: Usuario puede iniciar sesión con email y password', () => {
  test('login exitoso redirige a dashboard', async ({ page }, testInfo) => {
    await evidenceStep(page, testInfo, 'AC-01', 1, 'Navegar a /login', async () => {
      await page.goto('/login');
      await expect(page.getByRole('heading', { name: /sign in/i })).toBeVisible();
    });

    await evidenceStep(page, testInfo, 'AC-01', 2, 'Completar formulario', async () => {
      await page.getByLabel('Email').fill('test@test.com');
      await page.getByLabel('Password').fill('password123');
    });

    await evidenceStep(page, testInfo, 'AC-01', 3, 'Submit y verificar redirect', async () => {
      await page.getByRole('button', { name: /sign in/i }).click();
      await page.waitForURL('/dashboard');
      await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
    });
  });
});
```

### Ejecución

```bash
# Ejecutar acceptance tests
npx playwright test tests/acceptance/

# Con HTML report
npx playwright test tests/acceptance/ --reporter=html
```

### Evidencia

Screenshots se guardan en `.quality/evidence/{feature}/acceptance/`:
- `AC-01_{description}.png`
- `AC-02_{description}.png`
- `results.json` (resumen de ejecución)

### Diferencia con otros tipos de test

| Tipo | Qué valida | Quién genera | Evidencia |
|------|-----------|-------------|-----------|
| Unit (AG-04) | Lógica de código funciona | AG-04 | Coverage % |
| Component (AG-04) | UI renderiza correctamente | AG-04 | — |
| **E2E** | **Flujos completos cross-browser** | **Dev / AG-04** | **Screenshots + HTML report** |
| **Acceptance (AG-09a)** | **Feature cumple el PRD** | **AG-09a** | **Screenshots + report** |

---

## Cobertura

```bash
# Ejecutar tests con coverage
npx vitest run --coverage

# Ver reporte HTML
open coverage/html/index.html
```

**Cobertura mínima:** 85% (ratchet)

## Estructura de Tests Recomendada

```
tests/
├── setup.ts                        # Testing Library matchers + globals
├── unit/
│   ├── hooks/
│   │   └── use-{feature}.test.ts
│   ├── stores/
│   │   └── {feature}-store.test.ts
│   └── utils/
│       └── {util-name}.test.ts
├── components/
│   ├── ui/
│   │   └── {component}.test.tsx
│   └── features/
│       └── {feature}/
│           └── {component}.test.tsx
├── acceptance/
│   ├── ac-01-{description}.spec.ts
│   └── ac-02-{description}.spec.ts
e2e/
├── playwright.config.ts
├── helpers/
├── fixtures/
├── tc-01-{description}.spec.ts
└── tc-NN-{description}.spec.ts
```

---

*Referencia: SpecBox Engine v5.18.0 "E2E Sentinel"*
