# Quality System

## Directorios

| Directorio | Contenido | Gitignored? |
|-----------|-----------|-------------|
| baselines/ | Baseline de metricas por proyecto | No |
| evidence/ | Evidence por feature (checkpoints, reports) | evidence/**/checkpoint.json: No, resto: Si |
| logs/ | Session logs y telemetria | Si |
| scripts/ | Scripts de automatizacion de quality | No |

## Politicas

| Metrica | Politica | Gate |
|---------|----------|------|
| Lint errors | zero-tolerance | BLOQUEANTE |
| Lint warnings | zero-tolerance | BLOQUEANTE |
| Coverage | ratchet (nunca baja) | BLOQUEANTE |
| Tests passing | no-regression | BLOQUEANTE |
| Architecture violations | ratchet | WARNING |
