#!/bin/sh
# UC-3903 — el servidor corre sin privilegios.
#
# El contenedor arranca como root solo para dejar el volumen de estado en manos
# del usuario del servidor (los contenedores anteriores lo escribieron como
# root) y cede los privilegios antes de ejecutar el servidor: el proceso que
# queda como PID 1 es `specbox`, no root. El contenido del engine en /app sigue
# siendo de root y de solo lectura para el servidor.
set -eu

STATE_DIR="${STATE_PATH:-/data/state}"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$STATE_DIR"
    chown -R specbox:specbox "$STATE_DIR"
    # setpriv keeps the environment: HOME must stop pointing at /root, or any
    # library cache under $HOME (FastMCP's version check) fails on startup.
    export HOME=/home/specbox
    exec setpriv --reuid=specbox --regid=specbox --init-groups -- "$@"
fi

exec "$@"
