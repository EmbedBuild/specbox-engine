#!/bin/bash
# Hook: Ejecuta lint antes de cada commit. BLOQUEANTE.
# Si lint falla, el commit se detiene.

set -e

# Detectar stack
if [ -f "pubspec.yaml" ]; then
  echo "[QG] Running dart analyze..."
  dart analyze --no-fatal-infos 2>&1
  RESULT=$?
elif [ -f "package.json" ]; then
  if command -v eslint &> /dev/null; then
    echo "[QG] Running eslint..."
    npx eslint . --max-warnings=0 2>&1
    RESULT=$?
  else
    echo "[QG] Running npm run lint..."
    npm run lint 2>&1
    RESULT=$?
  fi
elif [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
  echo "[QG] Running ruff check..."
  ruff check . 2>&1
  RESULT=$?
else
  echo "[QG] No linter detected, skipping"
  exit 0
fi

if [ $RESULT -ne 0 ]; then
  echo ""
  echo "❌ [QUALITY GATE] Lint failed. Fix errors before committing."
  echo "   Policy: zero-tolerance (0 errors, 0 warnings)"
  exit 1
fi

echo "✅ [QUALITY GATE] Lint passed"
exit 0
