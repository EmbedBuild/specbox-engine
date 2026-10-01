#!/bin/bash
# Tests for scripts/npm-publish-and-wait.sh (UC-5902)
# Run from repo root: bash scripts/tests/test-npm-publish-and-wait.sh
#
# Un npm falso decide cómo responde `npm publish` (ok, E409 «staged», otro error)
# y a partir de qué `npm view` sirve la versión, sin tocar el registro real.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCRIPT_UNDER_TEST="$REPO_ROOT/scripts/npm-publish-and-wait.sh"

if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'
else
    RED=''; GREEN=''; NC=''
fi

PASS=0
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Fake npm: FAKE_PUBLISH = ok | staged | denied; FAKE_SERVE_AFTER = nº de `view` antes de servir (-1 nunca) ---
cat > "$TMP/npm" <<'EOF'
#!/bin/bash
case "$1" in
    publish)
        echo "publish" >> "$FAKE_LOG"
        case "$FAKE_PUBLISH" in
            ok) echo "+ specbox@9.9.9"; exit 0 ;;
            staged) echo "npm error code E409"; echo "npm error 409 Conflict - PUT https://registry.npmjs.org/specbox - previously staged"; exit 1 ;;
            denied) echo "npm error code E403"; echo "npm error 403 Forbidden - You do not have permission to publish"; exit 1 ;;
        esac ;;
    view)
        echo "view" >> "$FAKE_LOG"
        n=$(grep -c '^view$' "$FAKE_LOG")
        if [ "$FAKE_SERVE_AFTER" -ge 0 ] && [ "$n" -gt "$FAKE_SERVE_AFTER" ]; then echo "9.9.9"; exit 0; fi
        echo "npm error code E404" >&2; exit 1 ;;
esac
EOF
chmod +x "$TMP/npm"

# run <name> <publish mode> <serve after> <wait seconds> <expected exit> <expected text> <expected views>
run() {
    local name="$1" mode="$2" after="$3" wait="$4" want_exit="$5" want_text="$6" want_views="$7"
    : > "$TMP/log"
    local out code
    out="$(FAKE_LOG="$TMP/log" FAKE_PUBLISH="$mode" FAKE_SERVE_AFTER="$after" \
        NPM="$TMP/npm" WAIT_SECONDS="$wait" POLL_SECONDS=0 RERUN_HINT="relaunch-hint" \
        bash "$SCRIPT_UNDER_TEST" specbox 9.9.9 --access public 2>&1)" && code=0 || code=$?
    local views
    views=$(grep -c '^view$' "$TMP/log" || true)
    if [ "$code" = "$want_exit" ] && printf '%s' "$out" | grep -q -- "$want_text" && [ "$views" = "$want_views" ]; then
        echo -e "${GREEN}PASS${NC} $name"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC} $name (exit $code, want $want_exit; views $views, want $want_views)"
        printf '%s\n' "$out" | sed 's/^/    /'
        FAIL=$((FAIL + 1))
    fi
}

run "publish ok, npm serves it on the 3rd check" ok 2 60 0 "npm serves specbox@9.9.9" 3
run "E409 previously staged counts as accepted and waits" staged 4 60 0 "npm already has specbox@9.9.9" 5
run "E409 then served: ends green" staged 1 60 0 "npm serves specbox@9.9.9" 2
run "another publish error fails without waiting" denied 0 60 1 "npm publish failed" 0
run "never served: fails after the deadline" ok -1 0 1 "still does not serve it" 1
run "the failure says how to relaunch" ok -1 0 1 "relaunch-hint" 1
run "served on the first check: no waiting" ok 0 60 0 "after 0s" 1

# Usage error (sin argumentos) — fuera de run() porque no pasa paquete ni versión
if bash "$SCRIPT_UNDER_TEST" >/dev/null 2>&1; then
    echo -e "${RED}FAIL${NC} no arguments exits non-zero"; FAIL=$((FAIL + 1))
else
    echo -e "${GREEN}PASS${NC} no arguments exits non-zero"; PASS=$((PASS + 1))
fi

echo ""
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
