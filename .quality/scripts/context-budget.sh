#!/bin/bash
# Context Budget Estimator — estima tokens aproximados de archivos/directorios
# Uso: .quality/scripts/context-budget.sh <path> [--detail]
# Ratio: ~1 token por 4 caracteres (aproximación conservadora para código)
set -e

TARGET="${1:-.}"
DETAIL="${2:-}"
TOKEN_RATIO=4

if [ ! -e "$TARGET" ]; then
  echo "Error: $TARGET not found"
  exit 1
fi

estimate_tokens() {
  local file="$1"
  local chars=$(wc -c < "$file" 2>/dev/null || echo 0)
  echo $(( chars / TOKEN_RATIO ))
}

echo "╔══════════════════════════════════════╗"
echo "║  Context Budget Estimator            ║"
echo "╚══════════════════════════════════════╝"
echo ""

if [ -f "$TARGET" ]; then
  tokens=$(estimate_tokens "$TARGET")
  echo "  File: $TARGET"
  echo "  Estimated tokens: $tokens"
  echo "  Context window %: $(echo "scale=1; $tokens * 100 / 200000" | bc)%"
  exit 0
fi

# Directory scan
TOTAL_TOKENS=0
declare -A DIR_TOKENS

while IFS= read -r -d '' file; do
  tokens=$(estimate_tokens "$file")
  TOTAL_TOKENS=$((TOTAL_TOKENS + tokens))
  dir=$(dirname "$file" | sed "s|^$TARGET/||" | cut -d'/' -f1-2)
  DIR_TOKENS[$dir]=$(( ${DIR_TOKENS[$dir]:-0} + tokens ))
done < <(find "$TARGET" -type f \
  -not -path '*/node_modules/*' \
  -not -path '*/.dart_tool/*' \
  -not -path '*/build/*' \
  -not -path '*/.git/*' \
  -not -path '*/.*' \
  -not -name '*.lock' \
  -not -name '*.g.dart' \
  -not -name '*.freezed.dart' \
  -print0)

echo "  Directory: $TARGET"
echo "  Total estimated tokens: $TOTAL_TOKENS"
echo "  Context window %: $(echo "scale=1; $TOTAL_TOKENS * 100 / 200000" | bc)%"
echo ""

if [ "$DETAIL" = "--detail" ]; then
  echo "  Breakdown by directory:"
  echo "  ─────────────────────────────────────"
  for dir in $(echo "${!DIR_TOKENS[@]}" | tr ' ' '\n' | sort); do
    tokens=${DIR_TOKENS[$dir]}
    pct=$(echo "scale=1; $tokens * 100 / 200000" | bc)
    printf "  %-35s %6d tokens (%s%%)\n" "$dir" "$tokens" "$pct"
  done
fi

echo ""
echo "  Budget thresholds:"
echo "  ├── Green:  < 15% (safe for single task)"
echo "  ├── Yellow: 15-30% (consider splitting)"
echo "  └── Red:    > 30% (must split into subtasks)"
