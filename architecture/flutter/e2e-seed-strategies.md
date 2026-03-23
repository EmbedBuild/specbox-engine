# E2E Seed Strategies — Flutter Web

> Guia de estrategias de seed/cleanup para tests E2E con Playwright en Flutter web.
> Define como crear y destruir datos de test por tipo de base de datos.
> Complementa `e2e-testing.md` (infra Playwright + CanvasKit) y `acceptance-tester.md` (Gherkin BDD).

---

## Principios

Identicos a React — ver `architecture/react/e2e-seed-strategies.md` para los principios base:
aislamiento, determinismo, idempotencia, FK-safe cleanup, sin colision, transaccionalidad.

---

## Interfaz comun — SeedStrategy

```typescript
// e2e/seed/seed-strategy.ts (compartida con React)
export interface SeedStrategy {
  seed(ucId: string): Promise<void>
  cleanup(): Promise<void>
  healthCheck(): Promise<boolean>
}

export interface AuthStrategy {
  createTestUser(user: TestUser): Promise<void>
  getAuthSession(user: TestUser): Promise<AuthSession>
  deleteTestUser(userId: string): Promise<void>
}
```

---

## Deteccion automatica de backend

| Archivo | Backend | Strategy |
|---------|---------|----------|
| `firebase.json` o `.firebaserc` | Firebase/Firestore | Firestore Strategy |
| `.env` con `SUPABASE_URL` | Supabase | SQL Strategy |
| `.env` con `MONGO_URI` | MongoDB | MongoDB Strategy |

La mayoria de proyectos Flutter usan Firebase. La SQL Strategy es identica a React
(ver `architecture/react/e2e-seed-strategies.md` seccion "SQL Strategy").

---

## Firestore Strategy (principal para Flutter)

### Arquitectura

Firebase Admin SDK con batch writes. Los fixtures son archivos JSON.
El seed se ejecuta desde el directorio `e2e/` (Node.js project separado del Flutter project).

```
Flutter project/
├── lib/                    # Dart code
├── build/web/              # Flutter web build (CanvasKit)
└── e2e/                    # Node.js project (Playwright)
    ├── package.json        # @playwright/test, firebase-admin, @supabase/supabase-js
    ├── playwright.config.ts
    ├── helpers/
    │   ├── flutter-web.ts  # waitForFlutterReady(), etc.
    │   ├── auth.ts         # loginViaAPI()
    │   ├── seed.ts         # Seed strategy (auto-detect)
    │   └── test-data.ts
    └── seed/
        └── fixtures/       # JSON fixtures por UC
```

### Fixtures JSON

```json
// e2e/seed/fixtures/base.json
{
  "collections": [
    {
      "path": "Championships/e2e-champ-001",
      "data": {
        "name": "E2E Test Championship 2026",
        "status": "active",
        "year": 2026,
        "createdAt": "SERVER_TIMESTAMP"
      },
      "subcollections": [
        {
          "path": "Races/e2e-race-001",
          "data": {
            "name": "E2E Gran Premio de Test",
            "circuit": "Circuito de Test",
            "date": "2026-04-15",
            "status": "upcoming"
          },
          "subcollections": [
            {
              "path": "Sessions/e2e-session-fp1",
              "data": {
                "name": "FP1",
                "type": "practice",
                "status": "scheduled"
              }
            }
          ]
        }
      ]
    }
  ]
}
```

### Helper TypeScript

```typescript
// e2e/helpers/seed-firestore.ts
import { initializeApp, cert, App } from 'firebase-admin/app'
import { getFirestore, Firestore } from 'firebase-admin/firestore'
import { getAuth, Auth } from 'firebase-admin/auth'
import * as path from 'path'
import * as fs from 'fs'

let app: App
let db: Firestore
let auth: Auth

function init() {
  if (app) return
  app = initializeApp({
    credential: cert(JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT!))
  })
  db = getFirestore(app)
  auth = getAuth(app)
}

// --- Tipos ---

interface FixtureDoc {
  path: string
  data: Record<string, unknown>
  subcollections?: FixtureDoc[]
}

interface FixtureFile {
  collections: FixtureDoc[]
}

// --- Seed ---

async function loadFixture(name: string): Promise<FixtureFile> {
  const filePath = path.join(__dirname, `../seed/fixtures/${name}.json`)
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'))
}

async function writeDocRecursive(basePath: string, doc: FixtureDoc): Promise<void> {
  const fullPath = basePath ? `${basePath}/${doc.path}` : doc.path
  const data = { ...doc.data }

  // Reemplazar marcadores
  for (const [key, val] of Object.entries(data)) {
    if (val === 'SERVER_TIMESTAMP') {
      data[key] = new Date()
    }
  }

  await db.doc(fullPath).set(data)

  if (doc.subcollections) {
    for (const sub of doc.subcollections) {
      await writeDocRecursive(fullPath, sub)
    }
  }
}

export async function seedFirestore(fixtureName: string): Promise<void> {
  init()
  const fixture = await loadFixture(fixtureName)
  for (const doc of fixture.collections) {
    await writeDocRecursive('', doc)
  }
}

// --- Cleanup ---

export async function cleanupFirestore(): Promise<void> {
  init()
  // Colecciones raiz a limpiar — adaptar por proyecto
  const rootCollections = [
    'Championships', 'Users', 'Notifications',
    'Accreditations', 'RoleRequests', 'GeneralData'
  ]

  for (const collName of rootCollections) {
    const snapshot = await db.collection(collName).get()
    for (const doc of snapshot.docs) {
      if (doc.id.startsWith('e2e-')) {
        // recursiveDelete borra doc + TODAS sus subcollections
        await db.recursiveDelete(doc.ref)
      }
    }
  }
}

// --- Auth ---

export async function createTestUsers(): Promise<void> {
  init()
  const users = [
    { uid: 'e2e-user-admin', email: 'e2e-admin@test.com', password: 'TestPass123!', displayName: 'E2E Admin' },
    { uid: 'e2e-user-player', email: 'e2e-player@test.com', password: 'TestPass123!', displayName: 'E2E Player' },
    { uid: 'e2e-user-coach', email: 'e2e-coach@test.com', password: 'TestPass123!', displayName: 'E2E Coach' },
  ]
  for (const u of users) {
    try {
      await auth.createUser(u)
    } catch (e: any) {
      if (e.code !== 'auth/uid-already-exists') throw e
    }
  }
}

export async function deleteTestUsers(): Promise<void> {
  init()
  const result = await auth.listUsers()
  for (const u of result.users) {
    if (u.uid.startsWith('e2e-')) {
      await auth.deleteUser(u.uid)
    }
  }
}

export async function healthCheck(): Promise<boolean> {
  init()
  try {
    await db.collection('Championships').limit(1).get()
    return true
  } catch {
    return false
  }
}
```

### Emulator Support (CI)

```bash
# firebase.json — configurar emulators
{
  "emulators": {
    "firestore": { "port": 8080 },
    "auth": { "port": 9099 }
  }
}
```

```bash
# CI pipeline
firebase emulators:start --only firestore,auth &
FIRESTORE_EMULATOR_HOST=localhost:8080 \
FIREBASE_AUTH_EMULATOR_HOST=localhost:9099 \
  npx playwright test
```

Firebase Admin SDK auto-detecta las env vars de emulator y redirige las operaciones.

### Diferencias con Supabase Auth en Flutter

| Aspecto | Supabase (localStorage) | Firebase (localStorage) |
|---------|------------------------|------------------------|
| Token key | `sb-{ref}-auth-token` | `firebase:authUser:{apiKey}:{appName}` |
| Inyeccion | `localStorage.setItem(key, JSON.stringify(session))` | `localStorage.setItem(key, JSON.stringify(user))` |
| Gotcha | varchar fields MUST be `''` not `NULL` | `displayName` puede ser `null` sin problema |
| Admin API | SQL INSERT en `auth.users` | `auth.createUser()` via Admin SDK |

### Auth injection para Flutter web + Firebase

```typescript
export async function loginViaAPI(page: Page, user: TestUser): Promise<void> {
  // 1. Sign in via Firebase Client SDK (REST API)
  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=${FIREBASE_API_KEY}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: user.email,
        password: user.password,
        returnSecureToken: true,
      }),
    }
  )
  const data = await response.json()
  if (!data.idToken) throw new Error(`Login failed for ${user.email}`)

  // 2. Navigate to app and inject token
  await page.goto('/')
  await waitForFlutterReady(page)

  await page.evaluate(({ apiKey, data }) => {
    const key = `firebase:authUser:${apiKey}:[DEFAULT]`
    localStorage.setItem(key, JSON.stringify({
      uid: data.localId,
      email: data.email,
      stsTokenManager: {
        refreshToken: data.refreshToken,
        accessToken: data.idToken,
        expirationTime: Date.now() + 3600 * 1000,
      },
    }))
  }, { apiKey: FIREBASE_API_KEY, data })

  // 3. Reload para que Flutter lea el token
  await page.reload()
  await waitForFlutterReady(page)
}
```

---

## Integracion con Gherkin BDD (bdd_widget_test / playwright-bdd)

### Opcion A: E2E via Playwright (recomendado para Flutter web)

Los `.feature` usan `Antecedentes` para seed, igual que en React:

```gherkin
# language: es
@US-01 @UC-001
Caracteristica: UC-001 — Login del usuario

  Antecedentes:
    Dado el entorno E2E esta preparado con datos base
    Y existen los usuarios de test

  @AC-01
  Escenario: Login exitoso con email y password
    Dado el usuario esta en la pagina de login
    Cuando ingresa "e2e-player@test.com" en el campo email
    Y ingresa "TestPass123!" en el campo password
    Y pulsa el boton "Iniciar sesion"
    Entonces es redirigido al dashboard principal
```

### Opcion B: Widget tests con bdd_widget_test (unit-level BDD)

Para tests que no necesitan browser ni DB real, `bdd_widget_test` ejecuta
en el test runner de Flutter con mocks. En ese caso, el seed son mocks
inyectados via GetIt/Provider, NO datos en DB.

No mezclar: E2E con Playwright usa seed real. Widget tests usan mocks.

---

## Convencion de IDs

Identica a React (ver `architecture/react/e2e-seed-strategies.md`):
- Prefijo `e2e-` en todos los IDs
- Deterministicos, descriptivos, sin colision

---

## Checklist por proyecto

- [ ] Backend detectado (Firestore / Supabase / MongoDB)
- [ ] Fixtures JSON creados en `e2e/seed/fixtures/`
- [ ] Helper de seed creado (`e2e/helpers/seed-firestore.ts` o `seed.ts`)
- [ ] Auth users creados via Admin SDK
- [ ] Auth injection funciona con CanvasKit (localStorage)
- [ ] Cleanup funciona (recursiveDelete para subcollections)
- [ ] Health check funciona
- [ ] `beforeAll` / `afterAll` integrados en specs
- [ ] Gherkin `Antecedentes` usan steps de seed
- [ ] IDs con prefijo `e2e-` en todos los datos de test
- [ ] Emulator configurado para CI (firestore + auth)
- [ ] Cleanup verificado: no quedan residuos tras `afterAll`

---

*Referencia: SpecBox Engine v5.5.0 — E2E Seed Strategies (Flutter Web)*
