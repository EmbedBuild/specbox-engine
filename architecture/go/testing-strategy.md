# Arquitectura Go - Estrategia de Testing

## Tipos de Tests

| Tipo | Que testear | Cuando | Herramientas |
|------|------------|--------|-------------|
| **Unit** | Logica de servicios, domain, helpers | Siempre | `testing` stdlib, `testify/assert`, `testify/mock` |
| **Integration** | Repositorios contra DB real | Antes de merge | `testcontainers-go`, `pgx`, build tags |
| **HTTP** | Handlers, middleware, routing | Siempre | `net/http/httptest` |
| **E2E / Acceptance** | AC-XX del PRD, flujos completos | AG-09a/AG-09b | `httptest`, BDD, evidence reports |
| **Benchmark** | Paths criticos de performance | Cuando se optimiza | `testing.B` |

## Unit Tests

### Principio: Table-Driven Tests

**TODOS** los unit tests deben seguir el patron table-driven. Es el estandar de Go.

### Estructura de archivos

```
internal/
├── application/
│   └── club/
│       ├── service.go
│       └── service_test.go      # Tests del service
├── domain/
│   ├── club.go
│   └── club_test.go             # Tests de logica de dominio
└── infrastructure/
    └── http/handlers/
        ├── club_handler.go
        └── club_handler_test.go # Tests de handlers
```

### Template: Service Test (Table-Driven)

```go
package club_test

import (
    "context"
    "testing"

    "github.com/google/uuid"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"

    "myapp/internal/application/club"
    "myapp/internal/domain"
)

// Mock generado con testify
type MockClubRepo struct {
    mock.Mock
}

func (m *MockClubRepo) FindAll(ctx context.Context) ([]domain.Club, error) {
    args := m.Called(ctx)
    return args.Get(0).([]domain.Club), args.Error(1)
}

func (m *MockClubRepo) FindByID(ctx context.Context, id uuid.UUID) (*domain.Club, error) {
    args := m.Called(ctx, id)
    if args.Get(0) == nil {
        return nil, args.Error(1)
    }
    return args.Get(0).(*domain.Club), args.Error(1)
}

func (m *MockClubRepo) Create(ctx context.Context, c *domain.Club) error {
    args := m.Called(ctx, c)
    return args.Error(0)
}

func (m *MockClubRepo) Update(ctx context.Context, c *domain.Club) error {
    args := m.Called(ctx, c)
    return args.Error(0)
}

func (m *MockClubRepo) Delete(ctx context.Context, id uuid.UUID) error {
    args := m.Called(ctx, id)
    return args.Error(0)
}

var (
    validID   = uuid.MustParse("550e8400-e29b-41d4-a716-446655440000")
    missingID = uuid.MustParse("550e8400-e29b-41d4-a716-446655440099")
)

func TestClubService_GetClub(t *testing.T) {
    tests := []struct {
        name    string
        id      uuid.UUID
        setup   func(*MockClubRepo)
        want    *domain.Club
        wantErr error
    }{
        {
            name: "club existente devuelve entidad",
            id:   validID,
            setup: func(m *MockClubRepo) {
                m.On("FindByID", mock.Anything, validID).
                    Return(&domain.Club{ID: validID, Name: "SS Lazio"}, nil)
            },
            want:    &domain.Club{ID: validID, Name: "SS Lazio"},
            wantErr: nil,
        },
        {
            name: "club no encontrado devuelve error sentinel",
            id:   missingID,
            setup: func(m *MockClubRepo) {
                m.On("FindByID", mock.Anything, missingID).
                    Return(nil, nil)
            },
            want:    nil,
            wantErr: club.ErrClubNotFound,
        },
        {
            name: "error de base de datos se propaga con wrapping",
            id:   validID,
            setup: func(m *MockClubRepo) {
                m.On("FindByID", mock.Anything, validID).
                    Return(nil, assert.AnError)
            },
            want:    nil,
            wantErr: assert.AnError,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            repo := new(MockClubRepo)
            tt.setup(repo)
            svc := club.NewService(repo, slog.Default())

            got, err := svc.GetClub(context.Background(), tt.id)

            if tt.wantErr != nil {
                assert.ErrorIs(t, err, tt.wantErr)
            } else {
                assert.NoError(t, err)
                assert.Equal(t, tt.want, got)
            }
            repo.AssertExpectations(t)
        })
    }
}
```

### Template: Domain Logic Test

```go
package domain_test

import (
    "testing"

    "github.com/stretchr/testify/assert"

    "myapp/internal/domain"
)

func TestClub_Validate(t *testing.T) {
    tests := []struct {
        name    string
        club    domain.Club
        wantErr bool
    }{
        {
            name:    "club valido",
            club:    domain.Club{Name: "SS Lazio", Slug: "ss-lazio", Country: "IT"},
            wantErr: false,
        },
        {
            name:    "nombre vacio es invalido",
            club:    domain.Club{Name: "", Slug: "ss-lazio", Country: "IT"},
            wantErr: true,
        },
        {
            name:    "slug con espacios es invalido",
            club:    domain.Club{Name: "SS Lazio", Slug: "ss lazio", Country: "IT"},
            wantErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            err := tt.club.Validate()
            if tt.wantErr {
                assert.Error(t, err)
            } else {
                assert.NoError(t, err)
            }
        })
    }
}
```

## HTTP Handler Tests

Usar `net/http/httptest` para testear handlers sin levantar un servidor.

### Template: Handler Test

```go
package handlers_test

import (
    "encoding/json"
    "net/http"
    "net/http/httptest"
    "strings"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"

    "myapp/internal/domain"
    "myapp/internal/infrastructure/http/handlers"
)

func TestClubHandler_List(t *testing.T) {
    tests := []struct {
        name       string
        setup      func(*MockClubService)
        wantStatus int
        wantBody   string
    }{
        {
            name: "lista clubs exitosamente",
            setup: func(m *MockClubService) {
                m.On("ListClubs", mock.Anything).
                    Return([]domain.Club{{Name: "SS Lazio"}}, nil)
            },
            wantStatus: http.StatusOK,
            wantBody:   "SS Lazio",
        },
        {
            name: "error interno devuelve 500",
            setup: func(m *MockClubService) {
                m.On("ListClubs", mock.Anything).
                    Return(nil, assert.AnError)
            },
            wantStatus: http.StatusInternalServerError,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            svc := new(MockClubService)
            tt.setup(svc)
            h := handlers.NewClubHandler(svc, slog.Default())

            req := httptest.NewRequest(http.MethodGet, "/api/v1/clubs", nil)
            rec := httptest.NewRecorder()

            h.List(rec, req)

            assert.Equal(t, tt.wantStatus, rec.Code)
            if tt.wantBody != "" {
                assert.Contains(t, rec.Body.String(), tt.wantBody)
            }
            svc.AssertExpectations(t)
        })
    }
}

func TestClubHandler_Create(t *testing.T) {
    tests := []struct {
        name       string
        body       string
        setup      func(*MockClubService)
        wantStatus int
    }{
        {
            name: "crea club con datos validos",
            body: `{"name":"SS Lazio","slug":"ss-lazio","country":"IT"}`,
            setup: func(m *MockClubService) {
                m.On("CreateClub", mock.Anything, mock.AnythingOfType("*domain.Club")).
                    Return(nil)
            },
            wantStatus: http.StatusCreated,
        },
        {
            name:       "body invalido devuelve 400",
            body:       `{invalid json`,
            setup:      func(m *MockClubService) {},
            wantStatus: http.StatusBadRequest,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            svc := new(MockClubService)
            tt.setup(svc)
            h := handlers.NewClubHandler(svc, slog.Default())

            req := httptest.NewRequest(http.MethodPost, "/api/v1/clubs", strings.NewReader(tt.body))
            req.Header.Set("Content-Type", "application/json")
            rec := httptest.NewRecorder()

            h.Create(rec, req)

            assert.Equal(t, tt.wantStatus, rec.Code)
            svc.AssertExpectations(t)
        })
    }
}
```

## Integration Tests

### Build Tag para separar de unit tests

Los integration tests usan el build tag `//go:build integration` para ejecutarse
solo cuando se solicita explicitamente.

### Template: Repository Integration Test

```go
//go:build integration

package postgres_test

import (
    "context"
    "testing"

    "github.com/google/uuid"
    "github.com/jackc/pgx/v5/pgxpool"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
    "github.com/testcontainers/testcontainers-go"
    "github.com/testcontainers/testcontainers-go/modules/postgres"
    "github.com/testcontainers/testcontainers-go/wait"

    pgstore "myapp/internal/infrastructure/persistence/postgres"
    "myapp/internal/domain"
)

func setupTestDB(t *testing.T) *pgxpool.Pool {
    t.Helper()
    ctx := context.Background()

    container, err := postgres.Run(ctx,
        "postgres:16-alpine",
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2),
        ),
    )
    require.NoError(t, err)
    t.Cleanup(func() { container.Terminate(ctx) })

    connStr, err := container.ConnectionString(ctx, "sslmode=disable")
    require.NoError(t, err)

    pool, err := pgxpool.New(ctx, connStr)
    require.NoError(t, err)
    t.Cleanup(func() { pool.Close() })

    // Ejecutar migraciones
    err = pgstore.RunMigrations(connStr)
    require.NoError(t, err)

    return pool
}

func TestClubRepo_CRUD(t *testing.T) {
    pool := setupTestDB(t)
    repo := pgstore.NewClubRepo(pool)
    ctx := context.Background()

    // Create
    newClub := &domain.Club{
        ID:      uuid.New(),
        Name:    "SS Lazio",
        Slug:    "ss-lazio",
        Country: "IT",
    }
    err := repo.Create(ctx, newClub)
    require.NoError(t, err)

    // Read
    found, err := repo.FindByID(ctx, newClub.ID)
    require.NoError(t, err)
    assert.Equal(t, newClub.Name, found.Name)
    assert.Equal(t, newClub.Slug, found.Slug)

    // Update
    found.Name = "S.S. Lazio 1900"
    err = repo.Update(ctx, found)
    require.NoError(t, err)

    updated, err := repo.FindByID(ctx, newClub.ID)
    require.NoError(t, err)
    assert.Equal(t, "S.S. Lazio 1900", updated.Name)

    // Delete
    err = repo.Delete(ctx, newClub.ID)
    require.NoError(t, err)

    deleted, err := repo.FindByID(ctx, newClub.ID)
    require.NoError(t, err)
    assert.Nil(t, deleted)

    // List
    all, err := repo.FindAll(ctx)
    require.NoError(t, err)
    assert.Empty(t, all)
}
```

### Ejecutar integration tests

```bash
# Solo unit tests (default)
go test ./...

# Solo integration tests
go test -tags integration ./...

# Todos
go test -tags integration -race ./...
```

## Benchmark Tests

Para paths criticos de performance — serialization, queries hot, algoritmos.

### Template: Benchmark

```go
package httputil_test

import (
    "testing"

    "myapp/internal/pkg/httputil"
)

func BenchmarkJSONEncode(b *testing.B) {
    data := map[string]any{
        "id":      "550e8400-e29b-41d4-a716-446655440000",
        "name":    "SS Lazio",
        "country": "IT",
        "active":  true,
    }

    b.ResetTimer()
    for b.Loop() {
        httputil.MarshalJSON(data)
    }
}

func BenchmarkSlugGenerate(b *testing.B) {
    inputs := []string{
        "SS Lazio",
        "Real Club Deportivo Mallorca",
        "Borussia Dortmund",
    }

    for _, input := range inputs {
        b.Run(input, func(b *testing.B) {
            for b.Loop() {
                domain.GenerateSlug(input)
            }
        })
    }
}
```

### Ejecutar benchmarks

```bash
# Ejecutar benchmarks
go test -bench=. -benchmem ./...

# Benchmark especifico con perfil de CPU
go test -bench=BenchmarkJSONEncode -benchmem -cpuprofile cpu.prof ./internal/pkg/httputil/
```

## Cobertura

### Comandos

```bash
# Generar reporte de cobertura
go test -coverprofile=coverage.out ./...

# Ver cobertura por paquete
go tool cover -func=coverage.out

# Reporte HTML interactivo
go tool cover -html=coverage.out -o coverage.html

# Cobertura solo de unit tests (sin integration)
go test -coverprofile=coverage.out ./internal/...
```

### Politica de cobertura

| Tipo | Minimo | Objetivo |
|------|--------|----------|
| Domain | 90% | 95% |
| Application (services) | 85% | 90% |
| Handlers | 80% | 85% |
| Infrastructure | 70% | 80% |
| **Global** | **80%** | **85%** |

La politica de ratchet del engine aplica: la cobertura nunca puede bajar del baseline establecido.

## Estructura de Tests Recomendada

```
internal/
├── domain/
│   ├── club.go
│   ├── club_test.go                    # Unit: logica de dominio
│   ├── rider.go
│   └── rider_test.go
│
├── application/
│   └── club/
│       ├── service.go
│       └── service_test.go             # Unit: table-driven con mocks
│
├── infrastructure/
│   ├── persistence/postgres/
│   │   ├── club_repo.go
│   │   └── club_repo_test.go           # Integration: testcontainers (build tag)
│   ├── http/
│   │   ├── middleware/
│   │   │   ├── logging.go
│   │   │   └── logging_test.go         # Unit: httptest
│   │   └── handlers/
│   │       ├── club_handler.go
│   │       └── club_handler_test.go    # Unit: httptest + mock service
│   └── config/
│       ├── config.go
│       └── config_test.go              # Unit: env vars
│
└── pkg/
    └── httputil/
        ├── response.go
        ├── response_test.go            # Unit
        └── response_bench_test.go      # Benchmark
```

## Acceptance Tests (AG-09a / AG-09b)

Los acceptance tests validan los Acceptance Criteria (AC-XX) del PRD.
Se integran con el pipeline del engine para generar evidencia.

### Estructura

```
tests/
└── acceptance/
    ├── features/                       # Definiciones BDD (Gherkin en español)
    │   ├── club_crud.feature
    │   └── rider_registration.feature
    ├── steps/                          # Step definitions
    │   ├── club_steps_test.go
    │   └── rider_steps_test.go
    ├── testmain_test.go               # Setup global (server, DB)
    └── results.json                    # Resultado para AG-09b
```

### Template: Acceptance Test (HTTP E2E)

```go
//go:build acceptance

package acceptance_test

import (
    "context"
    "net/http"
    "net/http/httptest"
    "strings"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

// TestMain levanta el servidor completo con DB real
func TestMain(m *testing.M) {
    // Setup: container PostgreSQL + migraciones + seed
    // ...
    os.Exit(m.Run())
}

// AC-01: El sistema debe permitir crear un club con nombre, slug y pais
func TestAC01_CreateClub(t *testing.T) {
    body := `{"name":"SS Lazio","slug":"ss-lazio","country":"IT"}`
    req := httptest.NewRequest(http.MethodPost, "/api/v1/clubs", strings.NewReader(body))
    req.Header.Set("Content-Type", "application/json")
    rec := httptest.NewRecorder()

    router.ServeHTTP(rec, req)

    require.Equal(t, http.StatusCreated, rec.Code)

    var result map[string]any
    err := json.NewDecoder(rec.Body).Decode(&result)
    require.NoError(t, err)
    assert.Equal(t, "SS Lazio", result["name"])
    assert.Equal(t, "ss-lazio", result["slug"])
    assert.NotEmpty(t, result["id"])
}

// AC-02: El sistema debe listar todos los clubs registrados
func TestAC02_ListClubs(t *testing.T) {
    req := httptest.NewRequest(http.MethodGet, "/api/v1/clubs", nil)
    rec := httptest.NewRecorder()

    router.ServeHTTP(rec, req)

    require.Equal(t, http.StatusOK, rec.Code)

    var result []map[string]any
    err := json.NewDecoder(rec.Body).Decode(&result)
    require.NoError(t, err)
    assert.GreaterOrEqual(t, len(result), 1)
}

// AC-03: El sistema debe devolver 404 cuando el club no existe
func TestAC03_ClubNotFound(t *testing.T) {
    req := httptest.NewRequest(http.MethodGet, "/api/v1/clubs/00000000-0000-0000-0000-000000000099", nil)
    rec := httptest.NewRecorder()

    router.ServeHTTP(rec, req)

    assert.Equal(t, http.StatusNotFound, rec.Code)
}
```

### Ejecutar acceptance tests

```bash
# Solo acceptance tests
go test -tags acceptance ./tests/acceptance/...

# Con generacion de evidencia para AG-09
go test -tags acceptance -v -json ./tests/acceptance/... > tests/acceptance/results.json
```

### Generacion de evidencia

Los acceptance tests generan `results.json` compatible con el contrato del engine
(`doc/specs/results-json-spec.md`). El script `api-evidence-generator.js` genera
el HTML Evidence Report a partir de los resultados JSON.

```bash
# Generar HTML Evidence Report
node .quality/scripts/api-evidence-generator.js \
    --results tests/acceptance/results.json \
    --output .quality/evidence/e2e-evidence-report.html \
    --uc UC-XXX
```

## Reglas de Testing

1. **Table-driven tests** siempre — sin excepciones
2. **`testify/assert`** para assertions, **`testify/mock`** para mocks
3. **Build tags** para separar unit / integration / acceptance
4. **`testcontainers-go`** para integration tests con DB real — nunca mocks de DB
5. **`httptest`** para handler tests — nunca levantar un servidor real en unit tests
6. **Context** en todos los tests que interactuen con servicios
7. **`t.Parallel()`** en tests que no comparten estado mutable
8. **`t.Helper()`** en funciones auxiliares de test para mejorar stack traces
9. **Nombres de test descriptivos** en español: `"club existente devuelve entidad"`
10. **Cobertura minima 80%** — el ratchet del engine impide que baje

## Documentos Relacionados

- [Overview](overview.md)
- [Estructura de Carpetas](folder-structure.md)
- [Patrones](patterns.md)
