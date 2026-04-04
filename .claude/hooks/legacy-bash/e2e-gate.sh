#!/usr/bin/env bash
# e2e-gate.sh — PostToolUse hook for git commit
# BLOCKING: Ensures acceptance evidence meets quality standards before commit.
#
# Why this exists:
#   When the agent generates acceptance tests and evidence, the human expects
#   that evidence to be real, valid, and complete. This hook catches mistakes
#   BEFORE they reach the repo — saving the human from reviewing broken evidence.
#
# What it checks (only when committing acceptance/evidence files):
#   1. results.json exists and passes schema validation
#   2. e2e-evidence-report.html exists and has real content
#   3. Evidence files referenced in results.json actually exist
#
# What it does NOT check:
#   - Normal code commits (no acceptance files = no check)
#   - .feature file commits without evidence (tests before running them)
#
# v5.12.0 — E2E Evidence Quality Gate

set -euo pipefail

# Parse tool input from stdin
INPUT=$(cat)

# Extract the commit command to check staged files
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || echo "")

if [ -z "$STAGED_FILES" ]; then
  exit 0
fi

# Check if this commit includes acceptance test files
HAS_ACCEPTANCE_FILES=false
if echo "$STAGED_FILES" | grep -qE '(test/acceptance/|tests/acceptance/|e2e/acceptance/|e2e/.*\.spec\.)'; then
  HAS_ACCEPTANCE_FILES=true
fi

# Also check if it includes evidence files
HAS_EVIDENCE_FILES=false
if echo "$STAGED_FILES" | grep -qE '\.quality/evidence/.*/acceptance/'; then
  HAS_EVIDENCE_FILES=true
fi

# If no acceptance or evidence files → this is a normal commit, allow
if [ "$HAS_ACCEPTANCE_FILES" = false ] && [ "$HAS_EVIDENCE_FILES" = false ]; then
  exit 0
fi

# --- Acceptance files detected: validate evidence ---

# Find the active UC
ACTIVE_UC_FILE=".quality/active_uc.json"
ACTIVE_UC=""
ACTIVE_FEATURE=""

if [ -f "$ACTIVE_UC_FILE" ]; then
  ACTIVE_UC=$(grep -oE '"uc_id"\s*:\s*"[^"]*"' "$ACTIVE_UC_FILE" 2>/dev/null | head -1 | sed 's/.*"uc_id"\s*:\s*"//;s/"$//')
  ACTIVE_FEATURE=$(grep -oE '"feature"\s*:\s*"[^"]*"' "$ACTIVE_UC_FILE" 2>/dev/null | head -1 | sed 's/.*"feature"\s*:\s*"//;s/"$//')
fi

# Find results.json files in evidence directories
RESULTS_FILES=$(find .quality/evidence -name "results.json" -path "*/acceptance/*" 2>/dev/null || echo "")

if [ -z "$RESULTS_FILES" ]; then
  # No results.json found — check if this is a partial commit (just .feature files)
  if [ "$HAS_EVIDENCE_FILES" = false ]; then
    # Only acceptance test files (no evidence) — this is AG-09a generating tests
    # Allow: tests can be committed before running them
    exit 0
  fi

  echo ""
  echo "============================================================"
  echo "  E2E GATE: Evidence files without results.json"
  echo "============================================================"
  echo "  Commit includes evidence files but no results.json found."
  echo ""
  echo "  Expected: .quality/evidence/{feature}/acceptance/results.json"
  echo ""
  echo "  To fix:"
  echo "    1. Run acceptance tests to generate results.json"
  echo "    2. For Playwright: results are generated automatically"
  echo "    3. For Patrol: run patrol-evidence-generator.js"
  echo "    4. For Python: run api-evidence-generator.js"
  echo "============================================================"
  echo ""
  exit 1
fi

# Validate each results.json found
VALIDATOR=".quality/scripts/validate-results-json.js"
VALIDATION_FAILED=false
VALIDATION_ERRORS=""

if [ ! -f "$VALIDATOR" ]; then
  echo ""
  echo "============================================================"
  echo "  E2E GATE: Validator not found"
  echo "============================================================"
  echo "  Expected: $VALIDATOR"
  echo ""
  echo "  To fix: run install.sh to restore quality scripts,"
  echo "  or copy validate-results-json.js from the engine repo."
  echo "============================================================"
  echo ""
  exit 1
fi

for RESULTS_FILE in $RESULTS_FILES; do
  # Only validate results.json that match the active UC or staged evidence
  EVIDENCE_DIR=$(dirname "$RESULTS_FILE")

  # Check if any staged file is in this evidence directory
  RELEVANT=false
  if echo "$STAGED_FILES" | grep -q "$EVIDENCE_DIR"; then
    RELEVANT=true
  fi
  # Or if the active UC matches
  if [ -n "$ACTIVE_UC" ]; then
    if grep -q "$ACTIVE_UC" "$RESULTS_FILE" 2>/dev/null; then
      RELEVANT=true
    fi
  fi

  if [ "$RELEVANT" = false ]; then
    continue
  fi

  # Run schema validation
  RESULT=$(node "$VALIDATOR" "$RESULTS_FILE" --check-evidence 2>&1) || {
    VALIDATION_FAILED=true
    VALIDATION_ERRORS="${VALIDATION_ERRORS}\n  ${RESULTS_FILE}:\n${RESULT}"
  }

  # Check HTML report exists
  HTML_REPORT="${EVIDENCE_DIR}/e2e-evidence-report.html"
  if [ ! -f "$HTML_REPORT" ]; then
    VALIDATION_FAILED=true
    VALIDATION_ERRORS="${VALIDATION_ERRORS}\n  Missing HTML Evidence Report: ${HTML_REPORT}"
  fi
done

if [ "$VALIDATION_FAILED" = true ]; then
  echo ""
  echo "============================================================"
  echo "  E2E GATE: Evidence validation FAILED"
  echo "============================================================"
  echo ""
  echo "  Acceptance files or evidence staged for commit, but"
  echo "  evidence validation failed:"
  echo ""
  echo -e "$VALIDATION_ERRORS"
  echo ""
  echo "  To fix:"
  echo "    1. Ensure results.json follows doc/specs/results-json-spec.md"
  echo "    2. Ensure e2e-evidence-report.html exists"
  echo "    3. Ensure evidence files referenced in results.json exist"
  echo "    4. Run: node .quality/scripts/validate-results-json.js <path>"
  echo "============================================================"
  echo ""
  exit 1
fi

exit 0
