#!/bin/bash
# Hook: Ejecuta validacion de lint antes de cada commit. BLOQUEANTE.
# Usa GGA (Gentleman Guardian Angel) para cache inteligente:
# solo valida archivos modificados desde el ultimo commit exitoso.
# Si GGA no esta instalado, ejecuta lint directo (sin cache).

set -e

# --- GGA (cached validation) ---
if command -v gga &>/dev/null; then
  echo "[QG] Running GGA cached validation..."
  gga run 2>&1
  RESULT=$?

  if [ $RESULT -ne 0 ]; then
    echo ""
    echo "[QUALITY GATE] GGA validation failed. Fix errors before committing."
    echo "   Policy: zero-tolerance (0 errors, 0 warnings)"
    echo "   Tip: only modified files were checked (cache active)"
    exit 1
  fi

  echo "[QUALITY GATE] GGA passed (cached — unmodified files skipped)"
  exit 0
fi

# --- Fallback: lint directo (sin cache) ---
echo "[QG] GGA not found, falling back to direct lint..."

# Detect OS for install suggestion
OS_NAME="$(uname -s)"
case "$OS_NAME" in
  Darwin)  INSTALL_CMD="brew install gentleman-programming/tap/gga" ;;
  Linux)   INSTALL_CMD="brew install gentleman-programming/tap/gga  OR  git clone + ./install.sh" ;;
  *)       INSTALL_CMD="git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git && cd gga && ./install.sh" ;;
esac
echo "[QG] Install GGA for cached validation: $INSTALL_CMD"

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
  echo "[QUALITY GATE] Lint failed. Fix errors before committing."
  echo "   Policy: zero-tolerance (0 errors, 0 warnings)"
  echo "   Note: install GGA for cached validation (skips unmodified files)"
  exit 1
fi

echo "[QUALITY GATE] Lint passed (no cache — install GGA for faster runs)"
exit 0
