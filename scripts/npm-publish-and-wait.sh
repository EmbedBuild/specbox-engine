#!/bin/bash
# npm-publish-and-wait.sh — publica un paquete y espera a que npm lo sirva (UC-5902).
#
# Usage (desde el directorio del paquete):
#   bash scripts/npm-publish-and-wait.sh <paquete> <versión> [argumentos de npm publish...]
#   bash ../../scripts/npm-publish-and-wait.sh specbox 6.16.1 --provenance --access public
#
# npm puede aceptar una publicación y tardar en servirla: specbox@6.16.0 quedó
# «staged» ~31 minutos. Relanzar mientras tanto devuelve E409 «previously staged».
# Este script trata ese E409 como publicación aceptada y sigue comprobando hasta
# que `npm view` sirve la versión o se agota el plazo.
#
# Env:
#   NPM           binario de npm (por defecto: npm; las pruebas lo sustituyen)
#   WAIT_SECONDS  plazo de espera (por defecto: 2700 = 45 min)
#   POLL_SECONDS  pausa entre comprobaciones (por defecto: 30)
#   RERUN_HINT    cómo relanzar, para el mensaje de error

set -uo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <package> <version> [npm publish args...]" >&2
    exit 2
fi

PKG="$1"
VERSION="$2"
shift 2

NPM="${NPM:-npm}"
WAIT_SECONDS="${WAIT_SECONDS:-2700}"
POLL_SECONDS="${POLL_SECONDS:-30}"
RERUN_HINT="${RERUN_HINT:-gh workflow run publish-specbox-cli.yml --repo EmbedBuild/specbox-engine -f tag=v$VERSION}"

served() {
    [ "$("$NPM" view "$PKG@$VERSION" version --prefer-online 2>/dev/null || true)" = "$VERSION" ]
}

# --- Publish ---
OUT="$("$NPM" publish "$@" 2>&1)"
STATUS=$?
printf '%s\n' "$OUT"

if [ "$STATUS" -eq 0 ]; then
    echo "npm accepted $PKG@$VERSION; waiting until the registry serves it (up to $((WAIT_SECONDS / 60)) min)"
elif printf '%s' "$OUT" | grep -qiE 'E409|previously staged|cannot publish over the previously published'; then
    # Una ejecución anterior ya la publicó: npm la tiene «staged» o la acaba de servir.
    echo "::notice::npm already has $PKG@$VERSION (staged or published by an earlier run); waiting until it serves it"
else
    echo "::error::npm publish failed for $PKG@$VERSION (exit $STATUS) — see the output above"
    exit "$STATUS"
fi

# --- Wait until npm serves it ---
START=$SECONDS
while true; do
    if served; then
        echo "npm serves $PKG@$VERSION (after $((SECONDS - START))s)"
        exit 0
    fi
    if [ $((SECONDS - START)) -ge "$WAIT_SECONDS" ]; then
        break
    fi
    sleep "$POLL_SECONDS"
done

echo "::error::npm accepted $PKG@$VERSION but still does not serve it after $((WAIT_SECONDS / 60)) min. npm sometimes keeps a version staged for longer; nothing is lost. Relaunch later with: $RERUN_HINT — it finishes green without publishing again as soon as npm serves the version."
exit 1
