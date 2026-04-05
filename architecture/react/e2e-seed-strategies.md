# E2E Seed Strategies — React/Next.js

> Guia de estrategias de seed/cleanup para tests E2E con Playwright.
> Define como crear y destruir datos de test por tipo de base de datos.
> Complementa `e2e-testing.md` (infra Playwright) y `acceptance-tester.md` (Gherkin BDD).

---

## Principios

| Principio | Descripcion |
|-----------|------------|
| **Aislamiento** | Cada suite crea su mundo y lo destruye. Cero residuos |
| **Determinismo** | IDs fijos con prefijo `e2e-`. Sin `gen_random_uuid()` |
| **Idempotencia** | Ejecutar seed 2 veces produce el mismo resultado (UPSERT o cleanup previo) |
| **FK-safe cleanup** | Borrar en orden inverso de dependencias |
| **Sin colision** | Datos E2E nunca colisionan con dev/demo/prod gracias al prefijo |
| **Transaccionalidad** | Si un INSERT falla, se revierte todo (donde el backend lo soporte) |

---

## Interfaz comun — SeedStrategy

Todos los backends implementan esta interfaz:

```typescript
// e2e/seed/seed-strategy.ts
export interface SeedStrategy {
  /** Crea datos de test para un UC especifico */
  seed(ucId: string): Promise<void>

  /** Destruye TODOS los datos con prefijo e2e- */
  cleanup(): Promise<void>

  /** Verifica conexion a la DB — falla rapido si no hay acceso */
  healthCheck(): Promise<boolean>
}

export interface AuthStrategy {
  /** Crea usuario en el sistema de auth */
  createTestUser(user: TestUser): Promise<void>

  /** Obtiene cookies/tokens para inyectar en el browser */
  getAuthSession(user: TestUser): Promise<AuthSession>

  /** Elimina usuario de test del sistema de auth */
  deleteTestUser(userId: string): Promise<void>
}
```

---

## Deteccion automatica de backend

```
¿Existe supabase/ o .env con SUPABASE_URL?    → SQL Strategy (Supabase)
¿Existe firebase.json o .firebaserc?           → Firestore Strategy
¿Existe .env con MONGO_URI o MONGODB_URI?      → MongoDB Strategy
¿Existe prisma/schema.prisma?                  → Prisma Strategy (SQL generico)
¿Otro?                                         → ERROR: configurar manualmente
```

---

## SQL Strategy (Supabase / PostgreSQL)

### Arquitectura

Funciones PL/pgSQL almacenadas en la DB. Se invocan con `supabase.rpc()`.
Ejecutan con `SECURITY DEFINER` (bypassa RLS con permisos del creador).

```
Playwright beforeAll → supabase.rpc('seed_e2e_base')
                     → supabase.rpc('seed_e2e_{uc}')
                     → tests ejecutan...
Playwright afterAll  → supabase.rpc('cleanup_e2e')
```

### Migracion de funciones seed

Crear una migracion dedicada (ej: `XXX_e2e_seed_functions.sql`):

```sql
-- ============================================================
-- seed_e2e_base() — Datos compartidos entre todas las suites
-- ============================================================
CREATE OR REPLACE FUNCTION seed_e2e_base()
RETURNS void AS $$
BEGIN
  -- Limpiar residuos de ejecuciones previas (idempotencia)
  PERFORM cleanup_e2e();

  -- Jerarquia organizacional
  INSERT INTO accounts (id, name)
  VALUES ('e2e-account-001', 'E2E Test Account');

  INSERT INTO groups (id, name, account_id)
  VALUES ('e2e-group-001', 'E2E Test Group', 'e2e-account-001');

  INSERT INTO companies (id, name, group_id)
  VALUES ('e2e-company-001', 'E2E Test Company', 'e2e-group-001');

  INSERT INTO clinics (id, name, company_id, status)
  VALUES
    ('e2e-clinic-001', 'E2E Clinica Centro', 'e2e-company-001', 'active'),
    ('e2e-clinic-002', 'E2E Clinica Norte',  'e2e-company-001', 'active');

END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- seed_e2e_auth_users() — Usuarios en auth.users + profiles
-- ============================================================
CREATE OR REPLACE FUNCTION seed_e2e_auth_users()
RETURNS void AS $$
BEGIN
  -- GOTCHA CRITICO: todos los varchar deben ser '' (NO NULL)
  -- GoTrue (Go) no puede scanear NULL en tipo string → HTTP 500
  INSERT INTO auth.users (
    id, email, encrypted_password, email_confirmed_at,
    email_change, email_change_token_new, email_change_token_current,
    phone_change, phone_change_token,
    confirmation_token, recovery_token, reauthentication_token,
    role, aud, created_at, updated_at
  ) VALUES
    ('e2e-user-owner', 'e2e-owner@test.com',
     crypt('TestPass123!', gen_salt('bf')), now(),
     '', '', '', '', '', '', '', '',
     'authenticated', 'authenticated', now(), now()),
    ('e2e-user-admin', 'e2e-admin@test.com',
     crypt('TestPass123!', gen_salt('bf')), now(),
     '', '', '', '', '', '', '', '',
     'authenticated', 'authenticated', now(), now()),
    ('e2e-user-am', 'e2e-am@test.com',
     crypt('TestPass123!', gen_salt('bf')), now(),
     '', '', '', '', '', '', '', '',
     'authenticated', 'authenticated', now(), now()),
    ('e2e-user-staff', 'e2e-staff@test.com',
     crypt('TestPass123!', gen_salt('bf')), now(),
     '', '', '', '', '', '', '', '',
     'authenticated', 'authenticated', now(), now());

  -- Profiles
  INSERT INTO profiles (id, email, full_name)
  VALUES
    ('e2e-user-owner', 'e2e-owner@test.com', 'E2E Owner'),
    ('e2e-user-admin', 'e2e-admin@test.com', 'E2E Admin'),
    ('e2e-user-am',    'e2e-am@test.com',    'E2E Account Manager'),
    ('e2e-user-staff', 'e2e-staff@test.com', 'E2E Staff');

  -- Roles
  INSERT INTO user_clinic_roles (user_id, clinic_id, role, is_active)
  VALUES
    ('e2e-user-owner', 'e2e-clinic-001', 'CLINIC_OWNER', true),
    ('e2e-user-admin', 'e2e-clinic-001', 'CLINIC_ADMIN', true),
    ('e2e-user-staff', 'e2e-clinic-001', 'CLINIC_STAFF_RECEPCION', true);

  -- AM con internal_role + clinicas asignadas
  UPDATE profiles SET internal_role = 'ACCOUNT_MANAGER' WHERE id = 'e2e-user-am';

  INSERT INTO account_manager_clinics (user_id, clinic_id)
  VALUES
    ('e2e-user-am', 'e2e-clinic-001'),
    ('e2e-user-am', 'e2e-clinic-002');

END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- seed_e2e_{uc}() — Datos especificos por Use Case
-- ============================================================
-- Patron: una funcion por UC que necesite datos adicionales.
-- Ejemplo para un UC de Strategy Dashboard:
CREATE OR REPLACE FUNCTION seed_e2e_uc005()
RETURNS void AS $$
BEGIN
  INSERT INTO health_scores (id, clinic_id, overall_score, balance_pct, trends_pct, critical_impact_pct, calculated_at)
  VALUES ('e2e-hs-001', 'e2e-clinic-001', 72.5, 80.0, 65.0, 70.0, now());

  INSERT INTO kpi_snapshots (id, clinic_id, area_id, kpi_config_id, value, period_start, period_end)
  VALUES
    ('e2e-kpi-snap-001', 'e2e-clinic-001', 'e2e-area-001', 'e2e-kpi-001', 85.0, '2026-01-01', '2026-01-31'),
    ('e2e-kpi-snap-002', 'e2e-clinic-001', 'e2e-area-001', 'e2e-kpi-001', 88.0, '2026-02-01', '2026-02-28');

  INSERT INTO risk_alerts (id, clinic_id, area_id, severity, message, is_active)
  VALUES ('e2e-risk-001', 'e2e-clinic-001', 'e2e-area-001', 'warning', 'KPI conversion bajo umbral', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- cleanup_e2e() — Destruye TODO con prefijo e2e-
-- ============================================================
CREATE OR REPLACE FUNCTION cleanup_e2e()
RETURNS void AS $$
BEGIN
  -- Orden inverso de dependencias (FK-safe)
  DELETE FROM audit_log          WHERE clinic_id LIKE 'e2e-%';
  DELETE FROM risk_alerts        WHERE id LIKE 'e2e-%';
  DELETE FROM kpi_snapshots      WHERE id LIKE 'e2e-%';
  DELETE FROM health_scores      WHERE id LIKE 'e2e-%';
  DELETE FROM data_trust_scores  WHERE clinic_id LIKE 'e2e-%';
  DELETE FROM kpi_configs        WHERE id LIKE 'e2e-%';
  DELETE FROM areas              WHERE id LIKE 'e2e-%';
  DELETE FROM tags               WHERE id LIKE 'e2e-%';
  DELETE FROM severities         WHERE id LIKE 'e2e-%';
  DELETE FROM cadences           WHERE id LIKE 'e2e-%';
  DELETE FROM close_reasons      WHERE id LIKE 'e2e-%';
  DELETE FROM account_manager_clinics WHERE user_id LIKE 'e2e-%';
  DELETE FROM user_clinic_roles  WHERE user_id LIKE 'e2e-%';
  DELETE FROM profiles           WHERE id LIKE 'e2e-%';
  DELETE FROM auth.users         WHERE id::text LIKE 'e2e-%';
  DELETE FROM clinics            WHERE id LIKE 'e2e-%';
  DELETE FROM companies          WHERE id LIKE 'e2e-%';
  DELETE FROM groups             WHERE id LIKE 'e2e-%';
  DELETE FROM accounts           WHERE id LIKE 'e2e-%';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Helper TypeScript

```typescript
// e2e/helpers/seed.ts
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_ANON_KEY!
)

export async function seedBase(): Promise<void> {
  const { error } = await supabase.rpc('seed_e2e_base')
  if (error) throw new Error(`seed_e2e_base failed: ${error.message}`)
}

export async function seedAuthUsers(): Promise<void> {
  const { error } = await supabase.rpc('seed_e2e_auth_users')
  if (error) throw new Error(`seed_e2e_auth_users failed: ${error.message}`)
}

export async function seedUC(ucId: string): Promise<void> {
  const fnName = `seed_e2e_${ucId.toLowerCase().replace('-', '')}`
  const { error } = await supabase.rpc(fnName)
  if (error) throw new Error(`${fnName} failed: ${error.message}`)
}

export async function cleanup(): Promise<void> {
  const { error } = await supabase.rpc('cleanup_e2e')
  if (error) throw new Error(`cleanup_e2e failed: ${error.message}`)
}

export async function healthCheck(): Promise<boolean> {
  const { error } = await supabase.from('clinics').select('id').limit(1)
  return !error
}
```

### Integracion con Playwright

```typescript
// e2e/us-01/uc-001-login.spec.ts
import { test, expect } from '@playwright/test'
import { seedBase, seedAuthUsers, cleanup } from '../helpers/seed'
import { loginViaAPI } from '../helpers/auth'
import { TEST_USERS } from '../helpers/test-data'

test.beforeAll(async () => {
  await seedBase()
  await seedAuthUsers()
})

test.afterAll(async () => {
  await cleanup()
})

test('AC-01: Login exitoso con email y password', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill(TEST_USERS.owner.email)
  await page.getByLabel('Contrasena').fill(TEST_USERS.owner.password)
  await page.getByRole('button', { name: /iniciar sesion/i }).click()
  await expect(page).toHaveURL(/select-clinic|strategy/)
})
```

---

## Firestore Strategy (Firebase)

### Arquitectura

Admin SDK con batch writes. No hay funciones almacenadas en Firestore.
Los fixtures son archivos JSON que se cargan programaticamente.

```
Playwright beforeAll → seedFirestore('base')
                     → seedFirestore('{uc}')
                     → tests ejecutan...
Playwright afterAll  → cleanupFirestore()
```

### Fixtures JSON

```
e2e/seed/fixtures/
├── base.json              # Datos compartidos
├── uc-001-auth.json       # Datos para UC de auth
├── uc-005-dashboard.json  # Datos para UC de dashboard
└── cleanup-paths.json     # Paths a borrar (orden)
```

```json
// e2e/seed/fixtures/base.json
{
  "collections": [
    {
      "path": "Championships/e2e-champ-001",
      "data": {
        "name": "E2E Test Championship",
        "status": "active",
        "createdAt": "SERVER_TIMESTAMP"
      },
      "subcollections": [
        {
          "path": "Races/e2e-race-001",
          "data": {
            "name": "E2E Test Race",
            "date": "2026-03-15",
            "status": "upcoming"
          }
        }
      ]
    }
  ]
}
```

### Helper TypeScript

```typescript
// e2e/helpers/seed-firestore.ts
import { initializeApp, cert } from 'firebase-admin/app'
import { getFirestore } from 'firebase-admin/firestore'
import { getAuth } from 'firebase-admin/auth'
import * as path from 'path'
import * as fs from 'fs'

const app = initializeApp({
  credential: cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT!))
})
const db = getFirestore(app)
const auth = getAuth(app)

interface FixtureDoc {
  path: string
  data: Record<string, unknown>
  subcollections?: FixtureDoc[]
}

interface FixtureFile {
  collections: FixtureDoc[]
}

async function loadFixture(name: string): Promise<FixtureFile> {
  const filePath = path.join(__dirname, `../seed/fixtures/${name}.json`)
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'))
}

async function writeDoc(doc: FixtureDoc): Promise<void> {
  const data = { ...doc.data }
  // Reemplazar SERVER_TIMESTAMP
  for (const [key, val] of Object.entries(data)) {
    if (val === 'SERVER_TIMESTAMP') {
      data[key] = new Date()
    }
  }
  await db.doc(doc.path).set(data)

  // Subcollections recursivas
  if (doc.subcollections) {
    for (const sub of doc.subcollections) {
      await writeDoc({
        ...sub,
        path: `${doc.path}/${sub.path}`
      })
    }
  }
}

export async function seedFirestore(fixtureName: string): Promise<void> {
  const fixture = await loadFixture(fixtureName)
  for (const doc of fixture.collections) {
    await writeDoc(doc)
  }
}

export async function cleanupFirestore(): Promise<void> {
  // Borrar documentos raiz con prefijo e2e- recursivamente
  const rootCollections = ['Championships', 'Users', 'Notifications']

  for (const collection of rootCollections) {
    const snapshot = await db.collection(collection)
      .where('__name__', '>=', `${collection}/e2e-`)
      .where('__name__', '<', `${collection}/e2e-\uf8ff`)
      .get()

    for (const doc of snapshot.docs) {
      // recursiveDelete borra doc + todas sus subcollections
      await db.recursiveDelete(doc.ref)
    }
  }
}

// Auth users
export async function createTestUsers(): Promise<void> {
  const users = [
    { uid: 'e2e-user-admin', email: 'e2e-admin@test.com', password: 'TestPass123!' },
    { uid: 'e2e-user-player', email: 'e2e-player@test.com', password: 'TestPass123!' },
  ]
  for (const u of users) {
    try {
      await auth.createUser({ uid: u.uid, email: u.email, password: u.password })
    } catch (e: any) {
      if (e.code !== 'auth/uid-already-exists') throw e
    }
  }
}

export async function deleteTestUsers(): Promise<void> {
  const users = await auth.listUsers()
  for (const u of users.users) {
    if (u.uid.startsWith('e2e-')) {
      await auth.deleteUser(u.uid)
    }
  }
}

export async function healthCheck(): Promise<boolean> {
  try {
    await db.collection('Championships').limit(1).get()
    return true
  } catch {
    return false
  }
}
```

### Emulator Support (CI)

```typescript
// e2e/helpers/seed-firestore.ts — detectar emulator
if (process.env.FIRESTORE_EMULATOR_HOST) {
  // Firebase Admin SDK auto-conecta al emulator si la env var existe
  console.log(`Using Firestore Emulator: ${process.env.FIRESTORE_EMULATOR_HOST}`)
}
```

```bash
# CI pipeline
firebase emulators:start --only firestore,auth &
FIRESTORE_EMULATOR_HOST=localhost:8080 npx playwright test
```

### Integracion con Playwright

```typescript
// e2e/us-01/uc-001-auth.spec.ts
import { test, expect } from '../fixtures/base-fixtures'
import { seedFirestore, cleanupFirestore, createTestUsers, deleteTestUsers } from '../helpers/seed-firestore'

test.beforeAll(async () => {
  await createTestUsers()
  await seedFirestore('base')
  await seedFirestore('uc-001-auth')
})

test.afterAll(async () => {
  await cleanupFirestore()
  await deleteTestUsers()
})
```

---

## MongoDB Strategy (futuro)

### Arquitectura

MongoDB client con scripts de seed. Patron similar a Firestore pero con `insertMany`.

```typescript
// e2e/helpers/seed-mongo.ts
import { MongoClient } from 'mongodb'

const client = new MongoClient(process.env.MONGO_URI!)

export async function seedMongo(fixtureName: string): Promise<void> {
  const db = client.db()
  const fixture = await loadFixture(fixtureName)
  for (const coll of fixture.collections) {
    await db.collection(coll.name).insertMany(
      coll.docs.map(d => ({ ...d, _id: d._id ?? `e2e-${d.name}` }))
    )
  }
}

export async function cleanupMongo(): Promise<void> {
  const db = client.db()
  const collections = await db.listCollections().toArray()
  for (const coll of collections) {
    await db.collection(coll.name).deleteMany({ _id: /^e2e-/ })
  }
}
```

---

## Integracion con Gherkin BDD (playwright-bdd)

El seed se integra con los `.feature` via `Antecedentes` (Background):

### En el .feature

```gherkin
# language: es
@US-01 @UC-001
Caracteristica: UC-001 — Login con Supabase Auth
  Como usuario del sistema
  Quiero autenticarme con email y password
  Para acceder a las funcionalidades de mi clinica

  Antecedentes:
    Dado el entorno E2E esta preparado con datos base
    Y existen los usuarios de test

  @AC-01
  Escenario: Login exitoso con email y password
    Dado el usuario esta en la pagina "/login"
    Cuando completa el campo "Email" con "e2e-owner@test.com"
    Y completa el campo "Contrasena" con "TestPass123!"
    Y hace click en "Iniciar sesion"
    Entonces es redirigido a la pagina de seleccion de clinica
    Y la sesion de Supabase Auth esta activa
```

### En los step definitions

```typescript
// tests/acceptance/steps/common_steps.ts
import { Given, When, Then } from 'playwright-bdd'
import { seedBase, seedAuthUsers, seedUC, cleanup } from '../../e2e/helpers/seed'

// --- SEED STEPS (Antecedentes) ---

Given('el entorno E2E esta preparado con datos base', async () => {
  await seedBase()
})

Given('existen los usuarios de test', async () => {
  await seedAuthUsers()
})

Given('existen datos de {string}', async ({}, ucId: string) => {
  await seedUC(ucId)
})

// --- CLEANUP (After hook de playwright-bdd) ---
// Se registra como afterAll en el config, no como step
```

### Cleanup via Playwright hooks (no Gherkin)

El cleanup NO va en el .feature (no es un paso funcional). Va en hooks:

```typescript
// tests/acceptance/steps/hooks.ts
import { AfterAll } from 'playwright-bdd'
import { cleanup } from '../../e2e/helpers/seed'

AfterAll(async () => {
  await cleanup()
})
```

---

## Convencion de IDs

| Tipo | Patron | Ejemplo |
|------|--------|---------|
| Usuarios | `e2e-user-{role}` | `e2e-user-owner`, `e2e-user-am` |
| Clinicas | `e2e-clinic-{NNN}` | `e2e-clinic-001` |
| Organizacion | `e2e-{entity}-{NNN}` | `e2e-account-001`, `e2e-group-001` |
| Datos de dominio | `e2e-{entity}-{NNN}` | `e2e-area-001`, `e2e-kpi-001` |
| Firestore docs | `e2e-{entity}-{NNN}` | `e2e-champ-001`, `e2e-race-001` |

### Reglas de IDs

1. **Siempre prefijo `e2e-`** — permite `LIKE 'e2e-%'` en cleanup
2. **Deterministicos** — nunca `gen_random_uuid()` ni `auto_increment`
3. **Descriptivos** — el ID indica que tipo de entidad es
4. **Sin colision** — el espacio `e2e-*` esta reservado exclusivamente para tests

---

## Checklist por proyecto

- [ ] Backend detectado (SQL / Firestore / MongoDB)
- [ ] Funciones seed creadas (migracion SQL o fixtures JSON)
- [ ] Funcion cleanup creada (FK-safe o recursive delete)
- [ ] Helper TypeScript creado (`e2e/helpers/seed.ts`)
- [ ] Health check funciona
- [ ] `beforeAll` / `afterAll` integrados en specs
- [ ] Gherkin `Antecedentes` usan steps de seed
- [ ] IDs con prefijo `e2e-` en todos los datos de test
- [ ] Cleanup verificado: no quedan residuos tras `afterAll`
- [ ] CI pipeline usa emulator (Firestore) o DB de test (SQL)

---

*Referencia: SpecBox Engine v5.18.0 — E2E Seed Strategies (React/Next.js)*
