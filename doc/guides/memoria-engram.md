# Memoria persistente con Engram

Engram es la memoria persistente (FTS5) que SpecBox usa para que una compactación de contexto no
borre el estado de la sesión. Es una **dependencia obligatoria** del engine: el CLAUDE.md de cada
proyecto (zona «memoria») pide comprobarla al empezar y parar si falta.

Esta guía recoge lo que antes iba entero en el CLAUDE.md de plantilla (UC-12209): la instalación
por sistema, el protocolo de persistencia y la tabla de tools.

## Comprobación al empezar la sesión

Al inicio de cada sesión, comprueba que las tools de Engram (`mem_save`, `mem_search`,
`mem_context`) están disponibles. Si no lo están, **para** y enseña los pasos del sistema de la
persona. No hay alternativa: sin Engram, una compactación pierde el estado sin remedio.

> Engram es un binario Go precompilado (~5 MB). No se instala con pip ni npm.
> Releases: https://github.com/Gentleman-Programming/engram/releases

### macOS

```
ENGRAM NO DETECTADO — Sesion detenida.

1. Descargar el binario desde GitHub Releases:
   # Apple Silicon (M1/M2/M3/M4):
   curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_darwin_arm64.tar.gz | tar xz
   # Intel:
   curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_darwin_amd64.tar.gz | tar xz
   (o, con Homebrew: brew install gentleman-programming/tap/engram)

2. Mover al PATH:
   mv engram ~/.local/bin/   # o /usr/local/bin/ con sudo

3. Comprobar que el servidor MCP está registrado (.vscode/mcp.json):
   { "servers": { "engram": { "command": "engram", "args": ["mcp", "--tools=agent"] } } }

4. Reiniciar Claude Code para que cargue el servidor MCP.

5. Verificar:
   engram save "test" "hello engram"
   engram search "hello"
```

### Linux

```
1. Descargar:
   # x86_64:
   curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_linux_amd64.tar.gz | tar xz
   # arm64:
   curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_linux_arm64.tar.gz | tar xz

2. mv engram ~/.local/bin/

3-5. (los mismos pasos que en macOS)
```

### Windows

```
1. Descargar desde https://github.com/Gentleman-Programming/engram/releases/latest
   el archivo engram_1.7.1_windows_amd64.zip o engram_1.7.1_windows_arm64.zip.

2. Descomprimir y mover engram.exe a una carpeta del PATH.

3-5. (los mismos pasos que en macOS)
```

## Tras una compactación

Si has sufrido una compactación (no recuerdas lo que hacías, no reconoces ficheros que se
nombraron o el historial parece cortado), lo primero:

1. `mem_context` con el proyecto actual, para recuperar el estado de sesiones anteriores.
2. `mem_search` con palabras clave si `mem_context` no da bastante detalle.
3. Solo después, sigue con la tarea.

Nunca sigas «de memoria» tras una compactación: consulta Engram primero.

## Persistencia durante el trabajo

- Al empezar una feature: `mem_save` con un título claro, el plan y los ficheros clave.
- Al terminar cada fase de `/implement`: `mem_save` con el resumen de la fase.
- Al resolver un problema complejo: `mem_save` con el diagnóstico y la solución.
- Al empezar la sesión: `mem_session_start`.
- Al terminar la sesión: el hook guarda `mem_session_summary` solo.

## Tools de Engram (MCP)

| Tool | Uso |
|------|-----|
| `mem_save` | Guardar una observación estructurada (title, content, type, project) |
| `mem_search` | Buscar en la memoria por palabras clave (FTS5) |
| `mem_context` | Recuperar el contexto reciente de sesiones anteriores |
| `mem_update` | Modificar una observación por su ID |
| `mem_session_start` | Empezar una sesión de trabajo |
| `mem_session_end` | Cerrar la sesión con un resumen opcional |
| `mem_session_summary` | Guardar el resumen estructurado de fin de sesión |
| `mem_timeline` | Ver el contexto cronológico alrededor de una observación |
| `mem_stats` | Estadísticas de la memoria |
