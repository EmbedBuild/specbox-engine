#!/bin/bash
# Genera baseline de metricas para el proyecto actual
# Uso: .quality/scripts/create-baseline.sh [project_path]

set -e

PROJECT="${1:-.}"
PROJECT_NAME="$(basename "$(realpath "$PROJECT")")"
BASELINE_FILE=".quality/baselines/${PROJECT_NAME}.json"

cd "$PROJECT"

echo "Generating baseline for ${PROJECT_NAME}..."

# Defaults
STACK="unknown"
ERRORS=0
WARNINGS=0
COVERAGE=0
TESTS_PASS=0
TESTS_FAIL=0

# Detectar stack y metricas
if [ -f "pubspec.yaml" ]; then
  STACK="flutter"
  RESULT="$(dart analyze --no-fatal-infos 2>&1 || true)"
  ERRORS="$(echo "$RESULT" | grep -ci " error " || true)"
  WARNINGS="$(echo "$RESULT" | grep -ci " warning " || true)"

elif [ -f "package.json" ]; then
  STACK="node"
  if command -v npx &>/dev/null && npx eslint --version &>/dev/null; then
    RESULT="$(npx eslint . --format json 2>/dev/null || echo '[]')"
    ERRORS="$(echo "$RESULT" | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(f.get('errorCount',0) for f in data))" 2>/dev/null || echo 0)"
    WARNINGS="$(echo "$RESULT" | python3 -c "import sys,json; data=json.load(sys.stdin); print(sum(f.get('warningCount',0) for f in data))" 2>/dev/null || echo 0)"
  fi

elif [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
  STACK="python"
  if command -v ruff &>/dev/null; then
    ERRORS="$(ruff check . --output-format json 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)"
  fi

elif [ -f ".clasp.json" ] || [ -f "appsscript.json" ]; then
  STACK="appscript"
fi

# Ensure numeric values
ERRORS="${ERRORS:-0}"
WARNINGS="${WARNINGS:-0}"

mkdir -p "$(dirname "$BASELINE_FILE")"

cat > "$BASELINE_FILE" << EOF
{
  "project": "${PROJECT_NAME}",
  "stack": "${STACK}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "metrics": {
    "lint_errors": ${ERRORS},
    "lint_warnings": ${WARNINGS},
    "test_coverage_pct": ${COVERAGE},
    "tests_passing": ${TESTS_PASS},
    "tests_failing": ${TESTS_FAIL}
  },
  "policies": {
    "lint": "zero-tolerance",
    "coverage": "ratchet",
    "tests": "no-regression"
  }
}
EOF

echo "Baseline saved to ${BASELINE_FILE}"
cat "$BASELINE_FILE"
