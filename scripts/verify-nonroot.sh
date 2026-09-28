#!/bin/sh
# UC-3903 AC-01 — falla si el proceso del servidor corre como root dentro del contenedor.
#
# Uso (en la máquina que ejecuta Docker):
#   scripts/verify-nonroot.sh <contenedor>
# En el VPS:
#   ssh specbox-vps 'sh -s -- "$(docker ps -q -f name=mcp_mcp-specbox-engine | head -1)"' < scripts/verify-nonroot.sh
set -eu

C="${1:?uso: verify-nonroot.sh <contenedor>}"

uid=$(docker exec "$C" awk '/^Uid:/{print $2}' /proc/1/status)
user=$(docker exec "$C" sh -c "getent passwd $uid | cut -d: -f1")
cmd=$(docker exec "$C" sh -c 'tr "\0" " " < /proc/1/cmdline')
echo "PID 1: ${cmd}— usuario ${user:-?} (uid $uid)"

if [ "$uid" = "0" ]; then
    echo "ERROR: el servidor corre como root"
    exit 1
fi

if ! docker exec -u "$uid" "$C" sh -c 'test -w "${STATE_PATH:-/data/state}"'; then
    echo "ERROR: el usuario del servidor no puede escribir su estado"
    exit 1
fi

echo "OK: el servidor corre sin privilegios y puede escribir su estado"
