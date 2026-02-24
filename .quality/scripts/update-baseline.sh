#!/bin/bash
# Actualiza baseline tras una implementación exitosa (ratchet: solo mejora)
# Uso: .quality/scripts/update-baseline.sh [project_path]
set -e

PROJECT="${1:-.}"
PROJECT_NAME="$(basename "$(realpath "$PROJECT")")"
BASELINE_FILE=".quality/baselines/${PROJECT_NAME}.json"

if [ ! -f "$BASELINE_FILE" ]; then
  echo "No baseline found. Run create-baseline.sh first."
  exit 1
fi

cd "$PROJECT"

# Get current metrics
CURRENT_ERRORS=0
CURRENT_WARNINGS=0

if [ -f "pubspec.yaml" ]; then
  RESULT="$(dart analyze --no-fatal-infos 2>&1 || true)"
  CURRENT_ERRORS="$(echo "$RESULT" | grep -ci " error " || echo 0)"
  CURRENT_WARNINGS="$(echo "$RESULT" | grep -ci " warning " || echo 0)"
elif [ -f "package.json" ]; then
  if command -v npx &>/dev/null; then
    RESULT="$(npx eslint . --format json 2>/dev/null || echo '[]')"
    CURRENT_ERRORS="$(echo "$RESULT" | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(f.get('errorCount',0) for f in data))" 2>/dev/null || echo 0)"
    CURRENT_WARNINGS="$(echo "$RESULT" | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(f.get('warningCount',0) for f in data))" 2>/dev/null || echo 0)"
  fi
elif [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
  if command -v ruff &>/dev/null; then
    CURRENT_ERRORS="$(ruff check . --output-format json 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)"
  fi
fi

# Read previous baseline
PREV_ERRORS=$(python3 -c "import json; d=json.load(open('$BASELINE_FILE')); print(d['metrics']['lint_errors'])" 2>/dev/null || echo 0)
PREV_WARNINGS=$(python3 -c "import json; d=json.load(open('$BASELINE_FILE')); print(d['metrics']['lint_warnings'])" 2>/dev/null || echo 0)

# Ratchet: only update if metrics improved or stayed same
if [ "$CURRENT_ERRORS" -le "$PREV_ERRORS" ] && [ "$CURRENT_WARNINGS" -le "$PREV_WARNINGS" ]; then
  # Update baseline with current (better or same) values
  TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  python3 -c "
import json
with open('$BASELINE_FILE') as f:
    data = json.load(f)
data['metrics']['lint_errors'] = $CURRENT_ERRORS
data['metrics']['lint_warnings'] = $CURRENT_WARNINGS
data['timestamp'] = '$TIMESTAMP'
with open('$BASELINE_FILE', 'w') as f:
    json.dump(data, f, indent=2)
print('Baseline updated (ratchet): errors', data['metrics']['lint_errors'], 'warnings', data['metrics']['lint_warnings'])
"
else
  echo "RATCHET VIOLATION: Current metrics are worse than baseline!"
  echo "  Errors: $PREV_ERRORS → $CURRENT_ERRORS"
  echo "  Warnings: $PREV_WARNINGS → $CURRENT_WARNINGS"
  echo "Baseline NOT updated."
  exit 1
fi
