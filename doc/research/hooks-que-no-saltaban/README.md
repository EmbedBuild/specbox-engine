# Los hooks que no saltaban

> UC-9301 (US-93, EP-13) · 2026-10-10 · Claude Code 2.1.288
> Material: [sesion-real/](sesion-real/) (pasos, configuraciones y disparos de la prueba).

## Resumen

1. **Ninguna condición `if` se disparaba.** Desde la v5.19.0 (2026-04-08), el engine registraba 15
   condiciones escritas como expresiones regulares (`Bash(.*git commit.*)`, `Write(src/.*)`). Para
   Claude Code son reglas de permisos: en Bash, `*` es el comodín y el punto es literal; en Write y
   Edit, la ruta es un glob de gitignore. En una sesión real, las 15 dieron **0 disparos**. Escritas
   como reglas de permisos (`Bash(*git commit*)`, `Write(src/**)`), dan **21 de 21** disparos
   esperados y ninguno de más.
2. **Tres hooks no leían lo que vigilaban.** `no-bypass-guard`, `spec-guard` y `uc-lifecycle-guard`
   buscaban `command` o `file_path` en el nivel superior de la entrada. Claude Code los manda dentro de
   `tool_input`. Aunque se dispararan, salían sin mirar nada. Las pruebas de humo usan el formato
   antiguo, así que no lo detectaban.
3. **Que un hook se ejecute no significa que bloquee.** Casi todos «bloquean» con `exit 1` y escriben
   por stdout. En Claude Code, `exit 1` es un error que no bloquea y el modelo no ve ese stdout.
   Comprobado con `no-bypass-guard` ya arreglado: se disparó, pero `git reset --hard` **se ejecutó**,
   el cambio sin guardar se perdió y el agente no recibió ningún mensaje.

Este cambio arregla los puntos 1 y 2. El 3 cambia lo que se bloquea en cada proyecto, así que es una
decisión aparte: abajo está, hook a hook, qué haría falta.

## Cómo se comprobó

- **Sesión real.** Dos proyectos desechables, cada uno con un remoto local. Cada hook condicionado se
  sustituyó por un registrador con la misma condición: el primer proyecto con las condiciones antiguas
  y el segundo con las nuevas. Haiku ejecutó los mismos 13 pasos en los dos ([pasos.txt](sesion-real/pasos.txt)):
  escrituras en `src/`, `lib/` y `docs/`, `git add`, dos commits (uno con `--no-verify`), tres pushes
  (normal, `--force` y `-f`), `reset --hard`, `gh pr create --help` y `git log`. Los dos ejecutaron los
  13 pasos (ficheros, commits y push al remoto comprobados).

  | Condiciones | Disparos | Inesperados | Esperados que faltan |
  |---|---|---|---|
  | Antiguas (regex) | 0 | 0 | 21 |
  | Nuevas (reglas de permisos) | 21 | 0 | 0 |

  Lo que no debe disparar nada no dispara: escribir en `docs/`, `git add`, `git log` y el `push` normal
  en la guardia de force push.
- **Salida de un hook.** Con hooks mínimos en una sesión real se comprobó que el stderr de un `exit 2`
  en PostToolUse y el `additionalContext` de un `exit 0` llegan al modelo. También se comprobó que un
  `exit 1` en PreToolUse no impide la orden.
- **Simulación por repo.** Cada hook, ya arreglado, se ejecutó en los cinco repos (engine, manager,
  cloud, site y projects) con la configuración de cada uno y una entrada real de Claude Code.
  `pre-commit-lint` no se ejecutó, porque lanza el linter o `gga`; se analizó qué haría. El único hook
  que escribe es `app-docs-sync-guard`: cuando detecta deriva, la anota en
  `.quality/app_docs_drift.jsonl`. Solo la detectó en el engine, en el worktree de esta rama, y se
  restauró. En los demás repos la simulación no modificó ningún fichero (comprobado por fecha).

## Cómo trata Claude Code la salida de un hook

| Salida del hook | PreToolUse (antes de la acción) | PostToolUse (después) |
|---|---|---|
| `exit 0` y texto por stdout | Nadie lo ve | Nadie lo ve |
| `exit 0` y JSON con `hookSpecificOutput.additionalContext` | No comprobado | El modelo lo recibe (**comprobado**) |
| `exit 1` | No bloquea (**comprobado**); el usuario ve «non-blocking status code» | Igual; la acción ya ocurrió |
| `exit 2` y motivo por stderr | Bloquea la acción y el modelo recibe el motivo (según la documentación) | El modelo recibe el motivo (**comprobado**); la acción ya ocurrió |

## Hook por hook: qué cambia al fusionar esto y qué haría falta

| Hook | Se dispara con | Qué pretende | Cómo sale hoy | Efecto al fusionar este cambio | Qué haría falta |
|---|---|---|---|---|---|
| `no-bypass-guard` | `--no-verify`, `push --force`/`-f`, `reset --hard` (Pre) | Impedir la orden | `exit 1`, stdout | El usuario ve un error que no bloquea; la orden se ejecuta | `exit 2` y stderr, para bloquear de verdad. Ojo: también atrapa `--force-with-lease`, que el flujo de rebase usa a diario; conviene dejarlo pasar |
| `commit-spec-guard` | `git commit` (Post) | No hacer commits en main; avisar si no hay UC | `exit 1` en main; avisos con `exit 0` y stdout | En main, el usuario ve un error, pero el commit ya está hecho. Los avisos no los ve nadie | Pasar a PreToolUse, con `exit 2` en main y los avisos por `additionalContext` |
| `pre-commit-lint` | `git commit` (Post) | Pasar el lint antes del commit | Lanza `gga run` o el linter **después** del commit; `exit 1` si falla | Tras cada commit se pasa el lint de todo el repo (hasta 60 s; en este Mac, `gga run`). El commit ya está hecho | Decidir: pasarlo a PreToolUse (lint antes del commit) o retirarlo en favor de `ci-local` |
| `e2e-gate` | `git commit` (Post) | Validar la evidencia al hacer commit de los tests de aceptación | Mira el área de preparación, que tras el commit está vacía | No hace nada nunca | PreToolUse sobre `git commit` |
| `checkpoint-freshness-guard` | `git commit` (Post) | Avisar si el checkpoint es viejo | `exit 0`, stdout | Nadie lo ve | `additionalContext` |
| `app-docs-sync-guard` | `git commit` (Post) | Avisar si `doc/app/` cambió sin sincronizar | `exit 0`, stdout | Nadie lo ve (en el engine hoy avisaría de deriva en `app_prd` y `app_spec`) | `additionalContext` |
| `uc-lifecycle-guard` | `git push` (Post) | Avisar si la UC no se pasó a revisión | `exit 0`, stdout | Nadie lo ve | `additionalContext` |
| `design-system-gate` | `gh pr create` (Pre); con `move_uc` y `complete_uc` ya funcionaba | Bloquear PR con brechas de diseño | `exit 2`, stderr (modo `block`) | **Bloquea de verdad** `gh pr create` si hay brechas con los tokens (en autopilot). Es el único cambio con efecto real | — |
| `spec-guard` | Write/Edit en `src/` y `lib/` (Post) | No escribir código sin UC o en main | `exit 1`, stdout | El usuario ve un error; la escritura ya está hecha | `exit 2` y stderr, para que el agente lo sepa (como `design-gate`), o PreToolUse para impedirlo |

## Qué habría pasado hoy en cada repo

Resultado de la simulación con los hooks arreglados y la configuración actual de cada repo. Con el
código de hoy (`exit 1`), **nada se habría bloqueado**: el usuario habría visto errores que no bloquean.
La última columna es lo que se bloquearía con lo recomendado arriba.

| Repo (rama del clon) | Spec-driven para los hooks | Lo que salta | Con lo recomendado se bloquearía |
|---|---|---|---|
| engine (rama de trabajo) | Sí (board FreeForm) | `no-bypass-guard` en las tres órdenes; `spec-guard` sin UC activa; avisos invisibles de `commit-spec-guard` (sin UC) y `app-docs-sync-guard` (deriva) | `--no-verify`, `push --force` y `reset --hard`; escribir en `src/` o `lib/` sin UC |
| manager (`docs/marca-de-autor`) | **No**: no declara `boardId` ni `backend_type` | Solo `no-bypass-guard` | Las tres órdenes |
| cloud (`main`) | Sí | `no-bypass-guard`; `commit-spec-guard` y `spec-guard` porque el clon está en `main` | Las tres órdenes; cualquier commit o escritura de código en `main` |
| site (`main`) | **No** | Solo `no-bypass-guard` | Las tres órdenes |
| projects (`main`) | Sí | Igual que cloud | Igual que cloud |

Dos hallazgos más:
- **Manager y site no son spec-driven para los hooks.** Las guardias de UC no se les aplican, aunque
  el manager sea el dueño del board. Se arregla declarando el board en su `.claude/project-config.json`.
- **`pre-commit-lint` usa `gga` si existe**, aunque el repo tenga su propio linter. En este Mac está
  instalado, así que sería lo que se lanzaría en los cinco repos.

## Recomendación

1. **Fusionar este cambio.** Las condiciones y la entrada quedan bien, con pruebas que impiden volver
   atrás. Hay dos efectos inmediatos que conviene saber antes de fusionar:
   - `design-system-gate` empieza a bloquear `gh pr create` con brechas de diseño;
   - `pre-commit-lint` empieza a lanzar el lint (o `gga run`) después de cada commit.

   El resto solo produce errores que no bloquean.
2. **UC siguiente en US-93:** pasar cada hook a su canal, según la última columna de la tabla. Empezar
   por `no-bypass-guard` (`exit 2`, dejando pasar `--force-with-lease`) y por `pre-commit-lint` (antes
   del commit o fuera).
3. **Después, una UC por satélite** para propagar la plantilla. De paso, declarar el board en el
   manager y en site.
