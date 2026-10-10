# Sesiones reales de UC-9302 (canales)

> 2026-10-10 · Claude Code 2.1.288 · `claude -p --model haiku --permission-mode bypassPermissions --setting-sources project`

## 1. Qué canal llega al modelo en PreToolUse

Un hook de PreToolUse sobre Bash respondía distinto según la orden. El modelo informó así:

| Orden | Salida del hook | ¿Se ejecutó? | ¿Llegó al modelo? |
|---|---|---|---|
| `git status --short` | `exit 0` + JSON `additionalContext` | Sí | **Sí**, literal |
| `git log --oneline -1` | `exit 0` + `permissionDecision: allow` con motivo | Sí | No |
| `git branch --show-current` | `exit 0` + stderr | Sí | No |
| `git diff --stat` | `exit 2` + stderr | **No** | **Sí**, literal |

## 2. Los hooks de UC-9302 en un proyecto spec-driven

Proyecto en `main` con `.claude/project-config.json` (board declarado), el registro PreToolUse/Bash de
`templates/settings.json.template`, `.claude/hooks/` del engine, un cambio sin guardar en `a.txt`, un
`malo.py` con un import sin usar y un remoto local.

Pasos pedidos, en este orden:

1. `git reset --hard HEAD`
2. `git commit -am "en main"`
3. `git checkout -b feature/UC-1`
4. `git add malo.py && git commit -m "con lint"`
5. `git push --force-with-lease origin feature/UC-1`

Respuesta del modelo:

1. `git reset --hard HEAD` — NO — GUARDIA DE CALIDAD: orden bloqueada
2. `git commit -am "en main"` — NO — COMMIT BLOQUEADO: no se hace commit en main
3. `git checkout -b feature/UC-1` — SÍ — NADA
4. `git add malo.py && git commit -m "con lint"` — NO — LINT: el commit no pasa el linter del proyecto
5. `git push --force-with-lease origin feature/UC-1` — SÍ — NADA

Estado después: `a.txt` conserva el cambio sin guardar; el log solo tiene el commit inicial; el remoto
tiene `feature/UC-1`.

Segunda sesión, en la rama y sin `malo.py`: `git commit -am "sin UC"` → se hizo el commit y el modelo
recibió «SPEC GUARD: el commit sigue, pero conviene arreglar esto — No hay UC activa (board
EmbedBuild/demo): llama a start_uc antes de implementar y a mark_ac_batch al terminar».
