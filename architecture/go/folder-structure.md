# Arquitectura Go - Estructura de Carpetas

## Estructura Completa

```
project-root/
├── cmd/
│   └── server/
│       └── main.go                      # Entry point, wiring, graceful shutdown
│
├── internal/                            # Codigo privado (no importable externamente)
│   ├── domain/                          # Entidades y puertos
│   │   ├── club.go                      # Entidad Club
│   │   ├── club_repository.go           # Interface ClubRepository
│   │   ├── rider.go                     # Entidad Rider
│   │   ├── rider_repository.go          # Interface RiderRepository
│   │   └── errors.go                    # Sentinel errors del dominio
│   │
│   ├── application/                     # Casos de uso / servicios
│   │   ├── club/
│   │   │   └── service.go              # ClubService (logica de negocio)
│   │   └── rider/
│   │       └── service.go              # RiderService
│   │
│   ├── infrastructure/                  # Adaptadores (implementaciones)
│   │   ├── persistence/
│   │   │   └── postgres/
│   │   │       ├── queries/            # Archivos .sql para sqlc
│   │   │       │   ├── clubs.sql       # Queries SQL para clubs
│   │   │       │   └── riders.sql      # Queries SQL para riders
│   │   │       ├── migrations/         # SQL migrations (golang-migrate)
│   │   │       │   ├── 001_create_clubs.up.sql
│   │   │       │   ├── 001_create_clubs.down.sql
│   │   │       │   ├── 002_create_riders.up.sql
│   │   │       │   └── 002_create_riders.down.sql
│   │   │       ├── sqlc.yaml           # Configuracion sqlc
│   │   │       ├── db.go              # Pool de conexiones (pgx)
│   │   │       ├── club_repo.go       # ClubRepository impl
│   │   │       └── rider_repo.go      # RiderRepository impl
│   │   │
│   │   ├── http/                       # Capa HTTP
│   │   │   ├── router.go              # Registro de rutas + middleware
│   │   │   ├── middleware/
│   │   │   │   ├── auth.go            # JWT / session validation
│   │   │   │   ├── logging.go         # Request logging (slog)
│   │   │   │   ├── cors.go            # CORS headers
│   │   │   │   └── recovery.go        # Panic recovery
│   │   │   └── handlers/
│   │   │       ├── club_handler.go    # HTTP handlers para clubs
│   │   │       ├── rider_handler.go   # HTTP handlers para riders
│   │   │       └── health_handler.go  # Health check endpoint
│   │   │
│   │   ├── auth/                       # Integracion auth provider
│   │   │   └── keycloak.go            # Keycloak client (ejemplo)
│   │   │
│   │   └── config/                     # Carga de configuracion
│   │       └── config.go              # Viper config struct
│   │
│   └── pkg/                            # Utilidades internas compartidas
│       ├── validator/
│       │   └── validator.go            # Validacion de structs
│       ├── httputil/
│       │   └── response.go            # JSON(), Error(), helpers
│       └── testutil/
│           └── testutil.go            # Test helpers, fixtures
│
├── pkg/                                # Codigo exportable (libreria publica, si aplica)
│
├── api/                                # Especificaciones de API
│   └── openapi.yaml                   # OpenAPI 3.x spec
│
├── deployments/                        # Archivos de despliegue
│   ├── Dockerfile                     # Multi-stage build
│   └── docker-compose.yml             # Desarrollo local
│
├── scripts/                            # Scripts auxiliares
│   ├── migrate.sh                     # Wrapper para migraciones
│   └── seed.sh                        # Datos de prueba
│
├── go.mod                              # Dependencias del modulo
├── go.sum                              # Checksums
├── Makefile                            # Comandos frecuentes
├── .golangci.yml                       # Configuracion del linter
├── .air.toml                           # Configuracion hot reload
└── README.md
```

## Descripcion de Carpetas

### Nivel raiz

| Carpeta | Proposito |
|---------|-----------|
| `cmd/` | Entry points de la aplicacion. Un subdirectorio por binario. |
| `internal/` | Codigo privado del proyecto. Go impide importarlo desde otros modulos. |
| `pkg/` | Codigo exportable como libreria. Solo si el proyecto expone API publica. |
| `api/` | Especificaciones OpenAPI, archivos proto (gRPC), schemas JSON. |
| `deployments/` | Dockerfile, docker-compose, manifiestos k8s, Helm charts. |
| `scripts/` | Scripts de CI/CD, migraciones, seed de datos. |

### internal/domain/

| Archivo | Proposito |
|---------|-----------|
| `{entity}.go` | Entidad de dominio con sus campos y metodos de negocio |
| `{entity}_repository.go` | Interface del repositorio (puerto) — definida en domain |
| `errors.go` | Sentinel errors compartidos del dominio |

### internal/application/

| Carpeta | Proposito |
|---------|-----------|
| `{feature}/service.go` | Service con logica de negocio del caso de uso |

### internal/infrastructure/

| Carpeta | Proposito |
|---------|-----------|
| `persistence/postgres/queries/` | Archivos `.sql` que sqlc compila a Go |
| `persistence/postgres/migrations/` | Migraciones SQL (up/down) para golang-migrate |
| `persistence/postgres/{entity}_repo.go` | Implementacion concreta del repositorio |
| `http/router.go` | Registro de rutas y stack de middleware |
| `http/middleware/` | Middleware HTTP: auth, logging, CORS, recovery |
| `http/handlers/` | HTTP handlers que conectan requests con services |
| `auth/` | Clientes de auth providers (Keycloak, Auth0, etc.) |
| `config/config.go` | Struct de configuracion con Viper |

### internal/pkg/

| Carpeta | Proposito |
|---------|-----------|
| `validator/` | Validacion de structs de entrada |
| `httputil/` | Helpers de respuesta HTTP: JSON, Error, pagination |
| `testutil/` | Helpers de tests: fixtures, containers, mocks |

## Ejemplo: Feature "Championship"

```
internal/
├── domain/
│   ├── championship.go                  # type Championship struct
│   └── championship_repository.go       # type ChampionshipRepository interface
├── application/
│   └── championship/
│       └── service.go                   # func NewService, ListChampionships, GetByID, Create
└── infrastructure/
    ├── persistence/postgres/
    │   ├── queries/championships.sql    # -- name: ListChampionships :many
    │   ├── migrations/003_create_championships.up.sql
    │   └── championship_repo.go         # type championshipRepo struct
    └── http/handlers/
        └── championship_handler.go      # List, GetByID, Create handlers
```

## Reglas de Nombrado

| Elemento | Convencion | Ejemplo |
|----------|-----------|---------|
| Paquetes | snake_case, singular, corto | `club`, `httputil`, `config` |
| Archivos | snake_case con `.go` | `club_handler.go`, `club_repo.go` |
| Structs | PascalCase | `ClubService`, `ClubHandler` |
| Interfaces | PascalCase, sufijo descriptivo | `ClubRepository`, `Authenticator` |
| Funciones publicas | PascalCase | `NewClubService`, `ListClubs` |
| Funciones privadas | camelCase | `parseClubInput`, `validateSlug` |
| Constantes | PascalCase o SCREAMING_SNAKE para env | `MaxPageSize`, `DefaultTimeout` |
| Variables | camelCase | `clubService`, `dbPool` |
| Archivos test | mismo nombre + `_test.go` | `service.go` → `service_test.go` |
| Migrations | `NNN_description.{up\|down}.sql` | `001_create_clubs.up.sql` |
| Queries sqlc | `{entity}s.sql` (plural) | `clubs.sql`, `riders.sql` |

## Convenciones Importantes

1. **`internal/`** es obligatorio para codigo privado — Go lo enforcea a nivel de compilador
2. **Un paquete por carpeta** — nunca multiples paquetes en la misma carpeta
3. **Interfaces en domain** — los adaptadores las implementan implicitamente
4. **Un `_test.go` por cada `.go`** en el mismo paquete (white-box) o `_test` (black-box)
5. **Migrations numeradas secuencialmente** con `up` y `down` separados
6. **Queries sqlc anotadas** con `-- name: QueryName :one/:many/:exec`
7. **No usar `pkg/` a nivel raiz** a menos que el proyecto sea una libreria publica
8. **`cmd/server/main.go`** solo contiene wiring y startup — zero logica de negocio
9. **Handlers delegan a services** — nunca acceden a repos directamente
10. **Config via Viper** cargada una vez en startup e inyectada como struct

## Documentos Relacionados

- [Overview](overview.md)
- [Estrategia de Testing](testing-strategy.md)
- [Patrones](patterns.md)
