#!/usr/bin/env bash
# design-gate.sh — PostToolUse hook for Write/Edit on UI page files
# BLOCKING: Prevents creating/modifying UI pages without Stitch designs.
#
# This hook enforces the design-to-code contract:
# "No UI code without a Stitch design. No exceptions."
#
# Triggers: Write/Edit to files matching presentation/pages/, src/pages/, app/*page.tsx
# Behavior:
#   1. Extracts feature name from the file path
#   2. Checks if Stitch design HTML exists in doc/design/{feature}/
#   3. If no design HTML → BLOCKS the write
#   4. If design exists but no traceability comment → WARNING (non-blocking)
#
# v5.10.0 — Design Discipline Enforcement (upgraded from WARNING to BLOCKING)

set -euo pipefail

# The tool input is passed via stdin as JSON
INPUT=$(cat)

# Extract the file path from the tool input
FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Check if the file is a UI page file (Flutter, React, Next.js)
if ! echo "$FILE_PATH" | grep -qE '(presentation/pages/|src/pages/|app/.*page\.(tsx|ts|jsx))'; then
  exit 0
fi

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
  echo ""
  echo "============================================================"
  echo "  DESIGN GATE: No Stitch design found — UI write blocked"
  echo "============================================================"
  echo "  File: ${FILE_PATH}"
  echo "  Feature: ${FEATURE}"
  echo "  Expected: ${DESIGN_DIR}/*.html"
  echo ""
  echo "  The SpecBox Engine contract requires ALL UI pages to be"
  echo "  generated from Stitch designs (design-to-code pipeline)."
  echo ""
  echo "  To proceed:"
  echo "    1. Run /plan to generate Stitch designs for this feature"
  echo "    2. Or manually create designs in ${DESIGN_DIR}/"
  echo "    3. Then implement the UI from the HTML designs"
  echo ""
  echo "  This is non-negotiable. UI without design = no visual"
  echo "  consistency = no traceability = quality degradation."
  echo "============================================================"
  echo ""
  exit 1
fi

# Design exists — check for traceability comment (WARNING only, not blocking)
if [ -f "$FILE_PATH" ]; then
  if ! head -10 "$FILE_PATH" | grep -q "Generated from: doc/design/"; then
    echo ""
    echo "WARNING: Missing design traceability comment in ${FILE_PATH}"
    echo "  Expected (within first 10 lines): // Generated from: doc/design/${FEATURE}/{screen}.html"
    echo "  This is required for AG-08 Check 6 compliance."
    echo ""
  fi
fi

exit 0
