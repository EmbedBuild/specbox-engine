# US-05: Benchmarking Público con Datos Reales — Plan Técnico

## Resumen

Implementación de generación automática de benchmark snapshots y endpoint público
para exponer métricas reales de proyectos del Engine de forma anonimizada.

## Use Cases

### UC-013: Generación automática de benchmark snapshot
- **AC-59**: Tool `generate_benchmark_snapshot` que consulta estado y genera Markdown agregado
- **AC-60**: Nombres anonimizados como "Proyecto A", "Proyecto B"; categorías genéricas de stack
- **AC-61**: Sección "Metodología" explicando cálculos y período
- **AC-62**: Archivo generado en `docs/benchmarks/snapshot_{date}.md`

### UC-014: Endpoint de métricas públicas en dashboard
- **AC-63**: GET `/api/benchmark/public` retorna JSON con mismas métricas
- **AC-64**: Sin autenticación requerida (rate limit a nivel infra)
- **AC-65**: Incluye campos `generated_at` y `engine_version`
- **AC-66**: Retorna 404 si no hay datos

## Arquitectura

### Archivos creados
1. `server/benchmark_generator.py` — Lógica de agregación y rendering Markdown
2. `server/tools/benchmark.py` — MCP tool `generate_benchmark_snapshot`
3. `tests/test_benchmark.py` — 31 tests cubriendo todas las ACs

### Archivos modificados
1. `server/server.py` — Registro del nuevo tool module
2. `server/dashboard_api.py` — Nuevo endpoint REST `/api/benchmark/public`

### Flujo de datos
```
State (/data/state/)
  ├── registry.json → lista de proyectos
  └── projects/{name}/
      ├── sessions.jsonl → delta_count
      ├── healing.jsonl → healing resolution rate
      ├── acceptance_validations.jsonl → acceptance rate
      ├── checkpoints.jsonl → time per UC
      └── meta.json → uc_count, coverage
          ↓
benchmark_generator.generate_benchmark()
          ↓
    ┌─────┴─────┐
    │            │
  MCP tool    REST endpoint
  (snapshot)  (/api/benchmark/public)
    │
    ↓
  docs/benchmarks/snapshot_{date}.md
```

## Métricas agregadas
- Total UCs
- Cobertura promedio (%)
- Tasa de resolución healing (%)
- Tasa de aceptación AG-09b (%)
- Tiempo promedio por UC (horas)
- Delta count promedio (archivos/sesión)

## Tests
31 tests en `tests/test_benchmark.py`:
- 5 tests de anonimización
- 7 tests de categorización de stack
- 10 tests de generación de métricas
- 7 tests de rendering Markdown
- 1 test de generación de archivo
- 1 test de comportamiento 404
