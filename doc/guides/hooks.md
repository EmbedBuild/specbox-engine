# Guía de hooks del engine

Cómo se registra un hook de SpecBox, qué recibe, cómo se escribe su condición y qué salida usar para
que haga lo que promete. Todo lo marcado como comprobado se probó en sesiones reales de Claude Code
2.1.288 (UC-9301; material en `doc/research/hooks-que-no-saltaban/`).

## Dónde se registra

En `.claude/settings.json` del engine y en `templates/settings.json.template`, que es lo que reciben
los proyectos. Los dos registran lo mismo; lo comprueba `tests/hooks/settings-template.test.mjs`.

```json
{
  "matcher": "Bash",
  "hooks": [
    { "type": "command", "if": "Bash(*git commit*)", "command": "node .claude/hooks/commit-spec-guard.mjs", "timeout": 10 }
  ]
}
```

- `matcher` elige la herramienta (`Bash`, `Write`, `Edit`, `mcp__SpecBox-MCP__(move_uc|complete_uc)`…).
- `if` (opcional) filtra cuándo corre ese hook dentro de esa herramienta. Es **una** regla de permisos.

## Cómo se escribe una condición

`if` es una **regla de permisos** de Claude Code, no una expresión regular:

- en **Bash**, `*` vale por cualquier secuencia (también espacios), el resto es literal y la regla casa
  el comando entero;
- en **Write** y **Edit**, la ruta es un glob de gitignore relativo al proyecto: `**` cruza carpetas y
  `*` no.

| Para vigilar | Funciona (comprobado) | No funcionaba (comprobado) |
|---|---|---|
| Un `git commit` | `Bash(*git commit*)` | `Bash(.*git commit.*)` |
| Un `git push` | `Bash(*git push*)` | `Bash(.*git push.*)` |
| `gh pr create` | `Bash(*gh pr create*)` | `Bash(.*gh pr create.*)` |
| Escribir en `src/` del proyecto | `Write(src/**)` | `Write(src/.*)` |
| Páginas en cualquier `src/pages/` | `Write(**/src/pages/**)` | `Write(src/pages/.*)` |

Por qué fallaban: en una regla de permisos, `.*` es «un punto y luego cualquier cosa». Así,
`Bash(.*git commit.*)` solo casa con comandos que empiezan por un punto, y `Write(src/.*)` solo con
ficheros de `src/` cuyo nombre empieza por punto. Las 15 condiciones así escritas dieron 0 disparos en
una sesión real.

Reglas prácticas:
- Una regla por entrada: no hay `&&` ni `||`. Para dos casos, dos entradas con el mismo hook.
- Si el filtro es complejo (varias carpetas, extensiones o profundidad), registra el hook **sin `if`** y
  filtra dentro del script, como `design-gate.mjs`. Cuesta un arranque de Node por escritura y no se
  equivoca.
- `tests/hooks/settings-if-syntax.test.mjs` rechaza cualquier condición con forma de regex y comprueba,
  hook a hook, qué acciones lo disparan y cuáles no. Un hook nuevo con condición entra en su tabla.

## Qué recibe el hook

Un JSON por stdin. Los argumentos de la herramienta van **dentro de `tool_input`**:

```json
{
  "hook_event_name": "PostToolUse",
  "tool_name": "Write",
  "tool_input": { "file_path": "/ruta/absoluta/src/app.ts", "content": "…" },
  "tool_response": { "filePath": "/ruta/absoluta/src/app.ts", "type": "create" },
  "cwd": "/ruta/absoluta"
}
```

- Bash: `tool_input.command`. Write y Edit: `tool_input.file_path`, **con ruta absoluta**: hazla
  relativa a `cwd` antes de compararla con carpetas del proyecto.
- Lee `tool_input` y, si quieres compatibilidad con pruebas antiguas, el nivel superior como
  respaldo: `(parsed.tool_input ?? parsed).command`.

## Qué salida usar

| Quiero… | Evento | Salida |
|---|---|---|
| Impedir la acción y que el agente sepa por qué | PreToolUse | `exit 2` y el motivo por stderr |
| Que el agente sepa algo después de la acción (un aviso que debe corregir) | PostToolUse | `exit 2` y el motivo por stderr (**comprobado**; la acción ya ocurrió) |
| Una nota para el agente, sin tono de error | PostToolUse | `exit 0` y `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "…"}}` por stdout (**comprobado**) |
| — | — | **No uses** `exit 1` para bloquear: no bloquea (**comprobado**) y el agente no ve el mensaje. Tampoco `exit 0` con texto por stdout para avisar: no lo ve nadie |

Un PostToolUse corre después de la acción: un «pre-commit» registrado ahí se ejecuta con el commit ya
hecho. Lo que debe impedir algo va en PreToolUse.

## Cómo se prueba un hook

1. **El script**, con la entrada real (`tool_input`, rutas absolutas) y su código de salida. Ejemplos:
   `tests/hooks/design-gate.test.mjs` y `tests/hooks/hook-input-shape.test.mjs`.
2. **El registro**, con `tests/hooks/settings-if-syntax.test.mjs` y la paridad con la plantilla.
3. **Una sesión real**, cuando cambia una condición o el tipo de salida: un proyecto desechable con el
   hook sustituido por un registrador y `claude -p` haciendo las acciones que deben dispararlo y las
   que no. El montaje está en `doc/research/hooks-que-no-saltaban/sesion-real/` (`mk.mjs`, `log.mjs`
   y `pasos.txt`).
