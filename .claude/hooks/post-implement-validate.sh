#!/bin/bash
# Hook: validación post-implementación — verifica que el baseline no ha regresado
# NO bloqueante: informa pero no bloquea
set -e

BASELINE_DIR=".quality/baselines"
if [ ! -d "$BASELINE_DIR" ]; then
  exit 0
fi

PROJECT_NAME="$(basename "$(pwd)")"
BASELINE_FILE="$BASELINE_DIR/${PROJECT_NAME}.json"

if [ ! -f "$BASELINE_FILE" ]; then
  echo "[POST-IMPLEMENT] No baseline found for $PROJECT_NAME, skipping validation"
  exit 0
fi

echo "[POST-IMPLEMENT] Validating against baseline..."

# Quick lint check
ERRORS=0
if [ -f "pubspec.yaml" ]; then
  ERRORS=$(dart analyze --no-fatal-infos 2>&1 | grep -ci " error " || echo 0)
elif [ -f "package.json" ]; then
  ERRORS=$(npx eslint . --format json 2>/dev/null | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(f.get('errorCount',0) for f in data))" 2>/dev/null || echo 0)
elif [ -f "pyproject.toml" ]; then
  ERRORS=$(ruff check . --output-format json 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
fi

BASELINE_ERRORS=$(python3 -c "import json; print(json.load(open('$BASELINE_FILE'))['metrics']['lint_errors'])" 2>/dev/null || echo 0)

if [ "$ERRORS" -gt "$BASELINE_ERRORS" ]; then
  echo "[POST-IMPLEMENT] Lint errors increased: $BASELINE_ERRORS -> $ERRORS (ratchet violation)"
else
  echo "[POST-IMPLEMENT] Lint errors OK: $ERRORS (baseline: $BASELINE_ERRORS)"
fi
