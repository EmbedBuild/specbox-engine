# Arquitectura Go - Overview

## Stack Principal

| Tecnologia | Version | Proposito |
|------------|---------|-----------|
| Go | 1.23+ | Runtime y lenguaje |
| net/http (stdlib) | - | HTTP server (Go 1.22+ enhanced routing) |
| Chi | 5.x | Router HTTP (middleware chain avanzado, opcional) |
| sqlc | 1.x | Type-safe SQL → Go code generation |
| pgx | 5.x | PostgreSQL driver nativo (pool, copy, listen/notify) |
| golang-migrate | 4.x | Migraciones de base de datos |
| slog (stdlib) | - | Structured logging (Go 1.21+) |
| Viper | 1.x | Configuration management |
| Wire | 0.6+ | Compile-time dependency injection |
| golangci-lint | 1.x | Linter aggregator |
| testify | 1.x | Testing assertions y mocks |
| testcontainers-go | 0.34+ | Integration tests con containers |
| Docker | - | Containerizacion (multi-stage builds) |
| Air | 1.x | Hot reload en desarrollo |

## Principios Fundamentales

### 1. Standard Library First

Preferir stdlib sobre dependencias externas. Go 1.22+ tiene routing con metodos HTTP nativos.
Solo usar Chi cuando se necesite middleware chain avanzado o subrouting complejo.

```go
// CORRECTO: stdlib routing (Go 1.22+)
mux := http.NewServeMux()
mux.HandleFunc("GET /api/v1/clubs", h.List)
mux.HandleFunc("GET /api/v1/clubs/{id}", h.GetByID)
mux.HandleFunc("POST /api/v1/clubs", h.Create)
mux.HandleFunc("PUT /api/v1/clubs/{id}", h.Update)
mux.HandleFunc("DELETE /api/v1/clubs/{id}", h.Delete)
```

### 2. Clean Architecture / Hexagonal

Separacion en capas con interfaces en el domain. Los puertos (interfaces) los define el domain;
los adaptadores (implementaciones) viven en infrastructure.

```
┌─────────────────────────────────────────────┐
│           INFRASTRUCTURE                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ HTTP     │  │ Postgres │  │  Config   │  │
│  │ Handlers │  │  Repos   │  │  (Viper)  │  │
│  └────┬─────┘  └────┬─────┘  └───────────┘  │
└───────┼─────────────┼───────────────────────┘
        │             │
        ▼             ▼
┌─────────────────────────────────────────────┐
│              APPLICATION                     │
│  ┌──────────────────────────────────────┐    │
│  │           Services (Use Cases)       │    │
│  └──────────────────┬───────────────────┘    │
└─────────────────────┼───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│                DOMAIN                        │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Entities │  │  Errors  │  │ Repo Intf │  │
│  └──────────┘  └──────────┘  └───────────┘  │
└─────────────────────────────────────────────┘
```

### 3. Errors are Values

Error handling explicito con `errors.Is()`, `errors.As()`, sentinel errors y custom error types.
**NUNCA** panic en codigo de aplicacion. Usar `fmt.Errorf` con `%w` para wrapping.

```go
// Sentinel errors en domain
var (
    ErrClubNotFound  = errors.New("club not found")
    ErrDuplicateSlug = errors.New("club slug already exists")
)

// Wrapping con contexto
func (s *Service) GetClub(ctx context.Context, id uuid.UUID) (*domain.Club, error) {
    club, err := s.repo.FindByID(ctx, id)
    if err != nil {
        return nil, fmt.Errorf("getting club %s: %w", id, err)
    }
    if club == nil {
        return nil, ErrClubNotFound
    }
    return club, nil
}
```

### 4. Composition over Inheritance

Interfaces implicitas, embedding para composicion. Interfaces pequenas (1-3 metodos).
**Accept interfaces, return structs.**

```go
// Interface pequena — definida donde se consume
type ClubRepository interface {
    FindAll(ctx context.Context) ([]Club, error)
    FindByID(ctx context.Context, id uuid.UUID) (*Club, error)
    Create(ctx context.Context, club *Club) error
}

// Struct concreta — devuelta por constructores
func NewClubService(repo ClubRepository, logger *slog.Logger) *ClubService {
    return &ClubService{repo: repo, logger: logger}
}
```

### 5. Concurrency Patterns

Goroutines + channels para concurrencia. Context para cancelacion y timeouts.
`errgroup` para operaciones paralelas con manejo de errores.

```go
// errgroup para operaciones paralelas
g, ctx := errgroup.WithContext(ctx)

g.Go(func() error {
    clubs, err = svc.ListClubs(ctx)
    return err
})
g.Go(func() error {
    stats, err = svc.GetStats(ctx)
    return err
})

if err := g.Wait(); err != nil {
    return fmt.Errorf("loading dashboard: %w", err)
}
```

## Estructura de Carpetas

```
project-root/
├── cmd/
│   └── server/
│       └── main.go                  # Entry point
├── internal/                        # Codigo privado del proyecto
│   ├── domain/                      # Entidades y puertos (interfaces)
│   ├── application/                 # Casos de uso / servicios
│   ├── infrastructure/              # Adaptadores (implementaciones)
│   │   ├── persistence/postgres/    # Base de datos (sqlc + pgx)
│   │   ├── http/                    # Handlers + middleware + router
│   │   ├── auth/                    # Integracion con auth provider
│   │   └── config/                  # Carga de configuracion
│   └── pkg/                         # Utilidades internas compartidas
├── api/                             # OpenAPI specs, proto files
├── deployments/                     # Docker, k8s, compose
├── scripts/                         # Scripts de CI/CD, setup
├── go.mod
├── go.sum
├── Makefile
├── .golangci.yml
└── README.md
```

## Patrones Clave

### HTTP Handler

```go
type ClubHandler struct {
    service *club.Service
    logger  *slog.Logger
}

func NewClubHandler(s *club.Service, l *slog.Logger) *ClubHandler {
    return &ClubHandler{service: s, logger: l}
}

func (h *ClubHandler) List(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    clubs, err := h.service.ListClubs(ctx)
    if err != nil {
        httputil.Error(w, err, http.StatusInternalServerError)
        return
    }
    httputil.JSON(w, http.StatusOK, clubs)
}
```

### Middleware Chain

```go
func NewRouter(h *handlers.ClubHandler) http.Handler {
    mux := http.NewServeMux()

    mux.HandleFunc("GET /api/v1/clubs", h.List)
    mux.HandleFunc("GET /api/v1/clubs/{id}", h.GetByID)
    mux.HandleFunc("POST /api/v1/clubs", h.Create)

    var handler http.Handler = mux
    handler = middleware.Recovery(handler)
    handler = middleware.Logging(handler)
    handler = middleware.CORS(handler)

    return handler
}
```

### Graceful Shutdown

```go
func main() {
    ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer stop()

    srv := &http.Server{Addr: ":8080", Handler: router}

    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            slog.Error("server error", "err", err)
        }
    }()

    <-ctx.Done()
    shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()
    srv.Shutdown(shutdownCtx)
}
```

## Reglas

1. **Standard library** para HTTP routing (Go 1.22+), Chi solo si se justifica
2. **sqlc** para data access, **NUNCA** GORM ni ORMs magicos
3. **slog** para logging, **NUNCA** logrus ni zerolog
4. **Errors are values** — wrapping con `%w`, sentinel errors en domain, **NUNCA** panic
5. **Context** en toda funcion que haga I/O — primer parametro siempre
6. **Interfaces** definidas donde se consumen, no donde se implementan
7. **Table-driven tests** como patron principal de testing
8. **golangci-lint** obligatorio en CI — zero warnings policy
9. **Docker multi-stage builds** para produccion (scratch o alpine)
10. **go mod tidy** antes de cada commit

## Anti-Patrones

| Anti-Patron | Alternativa |
|-------------|-------------|
| GORM / ORMs magicos | sqlc + pgx (type-safe SQL) |
| logrus / zerolog | slog (stdlib, Go 1.21+) |
| gorilla/mux (deprecated) | net/http (Go 1.22+) o Chi 5.x |
| panic() en codigo de app | Return error con wrapping %w |
| init() para logica de negocio | Explicit initialization en main() |
| Global state / singletons | Dependency injection (Wire) |
| Interfaces grandes (>5 metodos) | Interfaces pequenas (1-3 metodos) |
| Channels para todo | Mutex cuando no hay comunicacion entre goroutines |
| vendor/ en el repo | go mod download en CI |
| Barrel files / re-exports | Imports directos al paquete |

## Documentos Relacionados

- [Estructura de Carpetas](folder-structure.md)
- [Estrategia de Testing](testing-strategy.md)
- [Patrones](patterns.md)
