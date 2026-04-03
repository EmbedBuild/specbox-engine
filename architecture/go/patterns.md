# Arquitectura Go - Patrones

## 1. Repository Interface + Implementation

El dominio define la interface (puerto); la infraestructura la implementa (adaptador).

### Interface en domain

```go
// internal/domain/club_repository.go
package domain

import (
    "context"

    "github.com/google/uuid"
)

type ClubRepository interface {
    FindAll(ctx context.Context) ([]Club, error)
    FindByID(ctx context.Context, id uuid.UUID) (*Club, error)
    Create(ctx context.Context, club *Club) error
    Update(ctx context.Context, club *Club) error
    Delete(ctx context.Context, id uuid.UUID) error
}
```

### Implementacion con sqlc + pgx

```go
// internal/infrastructure/persistence/postgres/club_repo.go
package postgres

import (
    "context"
    "errors"
    "fmt"

    "github.com/google/uuid"
    "github.com/jackc/pgx/v5"
    "github.com/jackc/pgx/v5/pgxpool"

    "myapp/internal/domain"
    "myapp/internal/infrastructure/persistence/postgres/sqlcgen"
)

type clubRepo struct {
    pool *pgxpool.Pool
    q    *sqlcgen.Queries
}

func NewClubRepo(pool *pgxpool.Pool) domain.ClubRepository {
    return &clubRepo{
        pool: pool,
        q:    sqlcgen.New(pool),
    }
}

func (r *clubRepo) FindByID(ctx context.Context, id uuid.UUID) (*domain.Club, error) {
    row, err := r.q.GetClub(ctx, id)
    if errors.Is(err, pgx.ErrNoRows) {
        return nil, nil
    }
    if err != nil {
        return nil, fmt.Errorf("querying club %s: %w", id, err)
    }
    return toDomainClub(row), nil
}

func (r *clubRepo) Create(ctx context.Context, club *domain.Club) error {
    err := r.q.CreateClub(ctx, sqlcgen.CreateClubParams{
        ID:      club.ID,
        Name:    club.Name,
        Slug:    club.Slug,
        Country: club.Country,
    })
    if err != nil {
        return fmt.Errorf("creating club: %w", err)
    }
    return nil
}

func toDomainClub(row sqlcgen.Club) *domain.Club {
    return &domain.Club{
        ID:        row.ID,
        Name:      row.Name,
        Slug:      row.Slug,
        Country:   row.Country,
        CreatedAt: row.CreatedAt,
    }
}
```

### Queries sqlc

```sql
-- internal/infrastructure/persistence/postgres/queries/clubs.sql

-- name: GetClub :one
SELECT id, name, slug, country, created_at
FROM clubs
WHERE id = $1;

-- name: ListClubs :many
SELECT id, name, slug, country, created_at
FROM clubs
ORDER BY name;

-- name: CreateClub :exec
INSERT INTO clubs (id, name, slug, country)
VALUES ($1, $2, $3, $4);

-- name: UpdateClub :exec
UPDATE clubs
SET name = $2, slug = $3, country = $4
WHERE id = $1;

-- name: DeleteClub :exec
DELETE FROM clubs WHERE id = $1;
```

### Configuracion sqlc

```yaml
# internal/infrastructure/persistence/postgres/sqlc.yaml
version: "2"
sql:
  - engine: postgresql
    queries: queries/
    schema: migrations/
    gen:
      go:
        package: sqlcgen
        out: sqlcgen
        sql_package: pgx/v5
        emit_json_tags: true
        emit_empty_slices: true
```

## 2. Service Layer con Error Handling

### Sentinel Errors

```go
// internal/domain/errors.go
package domain

import "errors"

var (
    ErrNotFound     = errors.New("resource not found")
    ErrConflict     = errors.New("resource already exists")
    ErrUnauthorized = errors.New("unauthorized")
    ErrForbidden    = errors.New("forbidden")
    ErrValidation   = errors.New("validation failed")
)
```

### Custom Error Type

```go
// internal/domain/errors.go
type ValidationError struct {
    Field   string
    Message string
}

func (e *ValidationError) Error() string {
    return fmt.Sprintf("validation: %s — %s", e.Field, e.Message)
}

func (e *ValidationError) Unwrap() error {
    return ErrValidation
}
```

### Service con error handling completo

```go
// internal/application/club/service.go
package club

import (
    "context"
    "errors"
    "fmt"
    "log/slog"

    "github.com/google/uuid"

    "myapp/internal/domain"
)

var (
    ErrClubNotFound  = fmt.Errorf("club: %w", domain.ErrNotFound)
    ErrDuplicateSlug = fmt.Errorf("club slug: %w", domain.ErrConflict)
)

type Service struct {
    repo   domain.ClubRepository
    logger *slog.Logger
}

func NewService(repo domain.ClubRepository, logger *slog.Logger) *Service {
    return &Service{repo: repo, logger: logger}
}

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

func (s *Service) CreateClub(ctx context.Context, club *domain.Club) error {
    if err := club.Validate(); err != nil {
        return fmt.Errorf("creating club: %w", err)
    }

    club.ID = uuid.New()
    if err := s.repo.Create(ctx, club); err != nil {
        return fmt.Errorf("creating club: %w", err)
    }

    s.logger.InfoContext(ctx, "club created",
        slog.String("club_id", club.ID.String()),
        slog.String("name", club.Name),
    )
    return nil
}

func (s *Service) ListClubs(ctx context.Context) ([]domain.Club, error) {
    clubs, err := s.repo.FindAll(ctx)
    if err != nil {
        return nil, fmt.Errorf("listing clubs: %w", err)
    }
    return clubs, nil
}
```

## 3. HTTP Handler Pattern

### Handler struct con inyeccion de dependencias

```go
// internal/infrastructure/http/handlers/club_handler.go
package handlers

import (
    "encoding/json"
    "errors"
    "log/slog"
    "net/http"

    "github.com/google/uuid"

    "myapp/internal/application/club"
    "myapp/internal/domain"
    "myapp/internal/pkg/httputil"
)

type ClubHandler struct {
    service *club.Service
    logger  *slog.Logger
}

func NewClubHandler(s *club.Service, l *slog.Logger) *ClubHandler {
    return &ClubHandler{service: s, logger: l}
}

func (h *ClubHandler) List(w http.ResponseWriter, r *http.Request) {
    clubs, err := h.service.ListClubs(r.Context())
    if err != nil {
        httputil.Error(w, err, http.StatusInternalServerError)
        return
    }
    httputil.JSON(w, http.StatusOK, clubs)
}

func (h *ClubHandler) GetByID(w http.ResponseWriter, r *http.Request) {
    id, err := uuid.Parse(r.PathValue("id"))
    if err != nil {
        httputil.Error(w, err, http.StatusBadRequest)
        return
    }

    c, err := h.service.GetClub(r.Context(), id)
    if err != nil {
        if errors.Is(err, domain.ErrNotFound) {
            httputil.Error(w, err, http.StatusNotFound)
            return
        }
        httputil.Error(w, err, http.StatusInternalServerError)
        return
    }
    httputil.JSON(w, http.StatusOK, c)
}

func (h *ClubHandler) Create(w http.ResponseWriter, r *http.Request) {
    var input domain.Club
    if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
        httputil.Error(w, err, http.StatusBadRequest)
        return
    }

    if err := h.service.CreateClub(r.Context(), &input); err != nil {
        if errors.Is(err, domain.ErrValidation) {
            httputil.Error(w, err, http.StatusUnprocessableEntity)
            return
        }
        if errors.Is(err, domain.ErrConflict) {
            httputil.Error(w, err, http.StatusConflict)
            return
        }
        httputil.Error(w, err, http.StatusInternalServerError)
        return
    }
    httputil.JSON(w, http.StatusCreated, input)
}
```

### HTTP Response Helpers

```go
// internal/pkg/httputil/response.go
package httputil

import (
    "encoding/json"
    "log/slog"
    "net/http"
)

func JSON(w http.ResponseWriter, status int, data any) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    if err := json.NewEncoder(w).Encode(data); err != nil {
        slog.Error("encoding JSON response", "err", err)
    }
}

func Error(w http.ResponseWriter, err error, status int) {
    JSON(w, status, map[string]string{
        "error": err.Error(),
    })
}
```

## 4. Middleware Pattern

### Logging Middleware

```go
// internal/infrastructure/http/middleware/logging.go
package middleware

import (
    "log/slog"
    "net/http"
    "time"
)

type statusRecorder struct {
    http.ResponseWriter
    status int
}

func (r *statusRecorder) WriteHeader(status int) {
    r.status = status
    r.ResponseWriter.WriteHeader(status)
}

func Logging(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        rec := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

        next.ServeHTTP(rec, r)

        slog.Info("request",
            slog.String("method", r.Method),
            slog.String("path", r.URL.Path),
            slog.Int("status", rec.status),
            slog.Duration("duration", time.Since(start)),
            slog.String("remote", r.RemoteAddr),
        )
    })
}
```

### Recovery Middleware

```go
// internal/infrastructure/http/middleware/recovery.go
package middleware

import (
    "log/slog"
    "net/http"
    "runtime/debug"
)

func Recovery(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rec := recover(); rec != nil {
                slog.Error("panic recovered",
                    "panic", rec,
                    "stack", string(debug.Stack()),
                    "path", r.URL.Path,
                )
                http.Error(w, "internal server error", http.StatusInternalServerError)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

### CORS Middleware

```go
// internal/infrastructure/http/middleware/cors.go
package middleware

import "net/http"

func CORS(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("Access-Control-Allow-Origin", "*")
        w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

        if r.Method == http.MethodOptions {
            w.WriteHeader(http.StatusNoContent)
            return
        }

        next.ServeHTTP(w, r)
    })
}
```

### Auth Middleware

```go
// internal/infrastructure/http/middleware/auth.go
package middleware

import (
    "context"
    "net/http"
    "strings"
)

type contextKey string

const UserIDKey contextKey = "user_id"

type Authenticator interface {
    ValidateToken(ctx context.Context, token string) (userID string, err error)
}

func Auth(auth Authenticator) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            header := r.Header.Get("Authorization")
            if !strings.HasPrefix(header, "Bearer ") {
                http.Error(w, "unauthorized", http.StatusUnauthorized)
                return
            }

            token := strings.TrimPrefix(header, "Bearer ")
            userID, err := auth.ValidateToken(r.Context(), token)
            if err != nil {
                http.Error(w, "invalid token", http.StatusUnauthorized)
                return
            }

            ctx := context.WithValue(r.Context(), UserIDKey, userID)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}
```

## 5. Configuration Pattern

### Struct-based config con Viper

```go
// internal/infrastructure/config/config.go
package config

import (
    "fmt"
    "strings"
    "time"

    "github.com/spf13/viper"
)

type Config struct {
    Server   ServerConfig   `mapstructure:"server"`
    Database DatabaseConfig `mapstructure:"database"`
    Auth     AuthConfig     `mapstructure:"auth"`
    Log      LogConfig      `mapstructure:"log"`
}

type ServerConfig struct {
    Port            int           `mapstructure:"port"`
    ReadTimeout     time.Duration `mapstructure:"read_timeout"`
    WriteTimeout    time.Duration `mapstructure:"write_timeout"`
    ShutdownTimeout time.Duration `mapstructure:"shutdown_timeout"`
}

type DatabaseConfig struct {
    URL             string        `mapstructure:"url"`
    MaxConns        int32         `mapstructure:"max_conns"`
    MinConns        int32         `mapstructure:"min_conns"`
    MaxConnLifetime time.Duration `mapstructure:"max_conn_lifetime"`
}

type AuthConfig struct {
    JWKSUrl  string `mapstructure:"jwks_url"`
    Issuer   string `mapstructure:"issuer"`
    Audience string `mapstructure:"audience"`
}

type LogConfig struct {
    Level  string `mapstructure:"level"`
    Format string `mapstructure:"format"` // "json" o "text"
}

func Load() (*Config, error) {
    viper.SetConfigName("config")
    viper.SetConfigType("yaml")
    viper.AddConfigPath(".")
    viper.AddConfigPath("./deployments")

    // Environment variables override
    viper.AutomaticEnv()
    viper.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))

    // Defaults
    viper.SetDefault("server.port", 8080)
    viper.SetDefault("server.read_timeout", "15s")
    viper.SetDefault("server.write_timeout", "15s")
    viper.SetDefault("server.shutdown_timeout", "10s")
    viper.SetDefault("database.max_conns", 25)
    viper.SetDefault("database.min_conns", 5)
    viper.SetDefault("database.max_conn_lifetime", "1h")
    viper.SetDefault("log.level", "info")
    viper.SetDefault("log.format", "json")

    if err := viper.ReadInConfig(); err != nil {
        if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
            return nil, fmt.Errorf("reading config: %w", err)
        }
        // Config file not found — using env vars + defaults
    }

    var cfg Config
    if err := viper.Unmarshal(&cfg); err != nil {
        return nil, fmt.Errorf("unmarshaling config: %w", err)
    }
    return &cfg, nil
}
```

## 6. Concurrency Patterns

### errgroup para operaciones paralelas

```go
// internal/application/dashboard/service.go
package dashboard

import (
    "context"
    "fmt"
    "log/slog"

    "golang.org/x/sync/errgroup"

    "myapp/internal/domain"
)

type DashboardData struct {
    Clubs  []domain.Club
    Riders []domain.Rider
    Stats  *domain.Stats
}

func (s *Service) GetDashboard(ctx context.Context) (*DashboardData, error) {
    var data DashboardData

    g, ctx := errgroup.WithContext(ctx)

    g.Go(func() error {
        clubs, err := s.clubRepo.FindAll(ctx)
        if err != nil {
            return fmt.Errorf("loading clubs: %w", err)
        }
        data.Clubs = clubs
        return nil
    })

    g.Go(func() error {
        riders, err := s.riderRepo.FindAll(ctx)
        if err != nil {
            return fmt.Errorf("loading riders: %w", err)
        }
        data.Riders = riders
        return nil
    })

    g.Go(func() error {
        stats, err := s.statsRepo.Get(ctx)
        if err != nil {
            return fmt.Errorf("loading stats: %w", err)
        }
        data.Stats = stats
        return nil
    })

    if err := g.Wait(); err != nil {
        return nil, fmt.Errorf("loading dashboard: %w", err)
    }
    return &data, nil
}
```

### Worker pool con channels

```go
// Procesamiento de N items con pool de workers
func (s *Service) ProcessBatch(ctx context.Context, items []domain.Item) error {
    const workers = 5

    jobs := make(chan domain.Item, len(items))
    errs := make(chan error, len(items))

    // Lanzar workers
    for range workers {
        go func() {
            for item := range jobs {
                if err := s.processOne(ctx, item); err != nil {
                    errs <- fmt.Errorf("processing %s: %w", item.ID, err)
                    return
                }
                errs <- nil
            }
        }()
    }

    // Enviar jobs
    for _, item := range items {
        jobs <- item
    }
    close(jobs)

    // Recoger resultados
    for range items {
        if err := <-errs; err != nil {
            return err
        }
    }
    return nil
}
```

### Context con timeout

```go
// Timeout por operacion
func (s *Service) FetchExternalData(ctx context.Context, url string) ([]byte, error) {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()

    req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
    if err != nil {
        return nil, fmt.Errorf("creating request: %w", err)
    }

    resp, err := http.DefaultClient.Do(req)
    if err != nil {
        return nil, fmt.Errorf("fetching %s: %w", url, err)
    }
    defer resp.Body.Close()

    return io.ReadAll(resp.Body)
}
```

## 7. Observability Pattern

### Structured Logging con slog

```go
// cmd/server/main.go
func setupLogger(cfg config.LogConfig) *slog.Logger {
    var handler slog.Handler

    opts := &slog.HandlerOptions{
        Level: parseLevel(cfg.Level),
    }

    switch cfg.Format {
    case "text":
        handler = slog.NewTextHandler(os.Stdout, opts)
    default:
        handler = slog.NewJSONHandler(os.Stdout, opts)
    }

    logger := slog.New(handler)
    slog.SetDefault(logger)
    return logger
}

func parseLevel(level string) slog.Level {
    switch strings.ToLower(level) {
    case "debug":
        return slog.LevelDebug
    case "warn":
        return slog.LevelWarn
    case "error":
        return slog.LevelError
    default:
        return slog.LevelInfo
    }
}
```

### Logging contextual en services

```go
func (s *Service) CreateClub(ctx context.Context, club *domain.Club) error {
    start := time.Now()

    s.logger.DebugContext(ctx, "creating club",
        slog.String("name", club.Name),
        slog.String("slug", club.Slug),
    )

    if err := s.repo.Create(ctx, club); err != nil {
        s.logger.ErrorContext(ctx, "failed to create club",
            slog.String("name", club.Name),
            slog.Any("err", err),
        )
        return fmt.Errorf("creating club: %w", err)
    }

    s.logger.InfoContext(ctx, "club created",
        slog.String("club_id", club.ID.String()),
        slog.String("name", club.Name),
        slog.Duration("duration", time.Since(start)),
    )
    return nil
}
```

## 8. Graceful Shutdown Pattern

```go
// cmd/server/main.go
package main

import (
    "context"
    "fmt"
    "log/slog"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "myapp/internal/infrastructure/config"
)

func main() {
    // 1. Load config
    cfg, err := config.Load()
    if err != nil {
        slog.Error("loading config", "err", err)
        os.Exit(1)
    }

    // 2. Setup logger
    logger := setupLogger(cfg.Log)

    // 3. Connect DB
    pool, err := setupDB(cfg.Database)
    if err != nil {
        logger.Error("connecting to database", "err", err)
        os.Exit(1)
    }
    defer pool.Close()

    // 4. Wire dependencies
    router := wireRouter(pool, logger)

    // 5. Create server
    srv := &http.Server{
        Addr:         fmt.Sprintf(":%d", cfg.Server.Port),
        Handler:      router,
        ReadTimeout:  cfg.Server.ReadTimeout,
        WriteTimeout: cfg.Server.WriteTimeout,
    }

    // 6. Start server in goroutine
    go func() {
        logger.Info("server starting", slog.Int("port", cfg.Server.Port))
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            logger.Error("server error", "err", err)
            os.Exit(1)
        }
    }()

    // 7. Wait for shutdown signal
    ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer stop()
    <-ctx.Done()

    // 8. Graceful shutdown
    logger.Info("shutting down server")
    shutdownCtx, cancel := context.WithTimeout(context.Background(), cfg.Server.ShutdownTimeout)
    defer cancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
        logger.Error("forced shutdown", "err", err)
    }
    logger.Info("server stopped")
}
```

## 9. Docker Multi-Stage Build

```dockerfile
# deployments/Dockerfile

# Build stage
FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /server ./cmd/server

# Runtime stage
FROM alpine:3.20
RUN apk --no-cache add ca-certificates tzdata
COPY --from=builder /server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

## 10. Makefile

```makefile
APP_NAME ?= myapp
DATABASE_URL ?= postgres://localhost:5432/$(APP_NAME)?sslmode=disable

.PHONY: run build test lint migrate-up migrate-down sqlc docker-build

run:
	air

build:
	go build -o bin/server ./cmd/server

test:
	go test -race -coverprofile=coverage.out ./...

test-integration:
	go test -race -tags integration ./...

test-acceptance:
	go test -tags acceptance -v ./tests/acceptance/...

lint:
	golangci-lint run

migrate-up:
	migrate -path internal/infrastructure/persistence/postgres/migrations \
		-database "$(DATABASE_URL)" up

migrate-down:
	migrate -path internal/infrastructure/persistence/postgres/migrations \
		-database "$(DATABASE_URL)" down 1

sqlc:
	sqlc generate -f internal/infrastructure/persistence/postgres/sqlc.yaml

docker-build:
	docker build -t $(APP_NAME) -f deployments/Dockerfile .

cover:
	go tool cover -html=coverage.out -o coverage.html
```

## 11. golangci-lint

```yaml
# .golangci.yml
run:
  timeout: 5m

linters:
  enable:
    - errcheck
    - gosimple
    - govet
    - ineffassign
    - staticcheck
    - unused
    - gofmt
    - goimports
    - misspell
    - unconvert
    - gocritic
    - revive
    - gosec
    - prealloc
    - bodyclose
    - noctx
    - exhaustive

linters-settings:
  revive:
    rules:
      - name: exported
        severity: warning
  gocritic:
    enabled-tags:
      - diagnostic
      - style
      - performance
```

## Documentos Relacionados

- [Overview](overview.md)
- [Estructura de Carpetas](folder-structure.md)
- [Estrategia de Testing](testing-strategy.md)
