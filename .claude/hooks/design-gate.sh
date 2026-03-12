#!/usr/bin/env bash
# design-gate.sh — PostToolUse hook for Write/Edit on presentation/pages/ files
# Warns when presentation page files are created/modified without Stitch designs.
# NON-BLOCKING: emits warning only (AG-08 enforces the hard block).

set -euo pipefail

# The tool input is passed via stdin as JSON
INPUT=$(cat)

# Extract the file path from the tool input
FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//')

# If no file_path found, try command field (for Bash tool creating files)
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Check if the file is under presentation/pages/ (Flutter) or pages/ (React/Next)
if echo "$FILE_PATH" | grep -qE '(presentation/pages/|src/pages/|app/.*page\.(tsx|ts|jsx))'; then
  # Extract feature name from the path
  # Flutter: lib/presentation/features/{feature}/pages/
  # React: src/pages/{feature}/ or app/{feature}/page.tsx
  FEATURE=$(echo "$FILE_PATH" | grep -oE '(features|pages)/[^/]+' | head -1 | sed 's/^[^/]*\///')

  if [ -z "$FEATURE" ]; then
    exit 0
  fi

  # Check if Stitch designs exist for this feature
  DESIGN_DIR="doc/design/${FEATURE}"
  HTML_COUNT=0
  if [ -d "$DESIGN_DIR" ]; then
    HTML_COUNT=$(find "$DESIGN_DIR" -name "*.html" 2>/dev/null | wc -l | tr -d ' ')
  fi

  if [ "$HTML_COUNT" -eq 0 ]; then
    echo "WARNING: No Stitch design found for '${FEATURE}'. Design-to-code traceability broken."
    echo "  File: ${FILE_PATH}"
    echo "  Expected: ${DESIGN_DIR}/*.html"
    echo "  Run /plan to generate designs or create them manually."
  fi

  # Check for traceability comment in the file
  if [ -f "$FILE_PATH" ]; then
    if ! head -5 "$FILE_PATH" | grep -q "Generated from: doc/design/"; then
      echo "WARNING: Missing design traceability comment in ${FILE_PATH}"
      echo "  Expected: // Generated from: doc/design/{feature}/{screen}.html"
    fi
  fi
fi

exit 0
