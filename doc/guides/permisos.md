# Permisos de Claude Code en los proyectos (US-108 · UC-10808)

## Qué traen los proyectos

`onboard_project` y `upgrade_project` escriben `.claude/settings.json` desde
`templates/settings.json.template`. Ese fichero se versiona: lo recibe todo el que clona el
proyecto.

| | Reglas |
|---|---|
| `allow` (sin preguntar) | `Read`, `Write`, `Edit` del proyecto |
| `deny` (nunca) | leer o editar `~/.ssh/**` y `~/.specbox/**`; leer `.env` y `.env.*`; `curl` y `wget` |
| el resto | Claude Code pregunta: comandos (`Bash`), webs (`WebFetch`), MCP |

Hasta la 6.28 la plantilla daba `Bash` y `WebFetch(domain:*)` sin preguntar. Un texto malicioso
que leyera el agente (una web, un issue, un fichero del repo) podía hacerle ejecutar cualquier
comando, por ejemplo mandar `~/.specbox/credentials.json` a otro servidor, sin que nadie lo viera
(auditoría de seguridad del 2026-10-27, ENG-D-03).

## Modo sin preguntas (autopilot), solo en tu máquina

Para que `/implement` en autopilot no se pare en cada comando, añade los permisos en
`.claude/settings.local.json`. Ese fichero no se versiona y `upgrade_project` no lo toca:

```json
{
  "permissions": {
    "allow": ["Bash", "WebFetch"]
  }
}
```

Claude Code suma las listas `allow` de los dos ficheros y aplica siempre las `deny`: con el modo sin
preguntas siguen prohibidos `curl`, `wget`, `.env` y tus credenciales. Puedes acotar más, por
ejemplo `"Bash(npm test:*)"` o `"WebFetch(domain:docs.github.com)"` en vez de `Bash` y `WebFetch`.

## Comprobación

`tests/test_template_permissions.py` falla si la plantilla vuelve a dar `Bash` o `WebFetch` sin
restricción, si pierde alguna prohibición o si `upgrade_project` escribe `settings.local.json`.
