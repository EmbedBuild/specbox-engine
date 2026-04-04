#!/usr/bin/env bash
# branch-guard.sh — PostToolUse hook for Write/Edit on source files (src/, lib/)
# BLOCKING: Prevents writing source code while on main/master branch.
#
# This hook enforces the branch discipline contract:
# "No code on main. Every implementation on a feature branch."
#
# Triggers: Write/Edit to files matching src/ or lib/ (same as spec-guard.sh)
# Behavior:
#   1. Checks current git branch
#   2. If on main/master → BLOCKS the write with clear instructions
#   3. If on feature/* or any other branch → allows
#   4. If not a git repo → allows (non-git projects unaffected)
#
# v5.10.0 — Branch Discipline Enforcement

set -euo pipefail

# Parse tool input from stdin
INPUT=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only guard source code files (src/, lib/), not tests, docs, config, etc.
if ! echo "$FILE_PATH" | grep -qE '(^|/)(src|lib)/'; then
  exit 0
fi

# Skip test files, config files, generated files
if echo "$FILE_PATH" | grep -qE '(test/|tests/|\.test\.|\.spec\.|_test\.dart|\.g\.dart|\.freezed\.dart|\.config\.|\.json$|\.yaml$|\.md$)'; then
  exit 0
fi

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")

if [ -z "$CURRENT_BRANCH" ]; then
  # Detached HEAD or no branch — allow (could be during rebase)
  exit 0
fi

# Block if on main or master
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo ""
  echo "============================================================"
  echo "  BRANCH GUARD: Writing source code on $CURRENT_BRANCH blocked"
  echo "============================================================"
  echo "  File: $FILE_PATH"
  echo "  Branch: $CURRENT_BRANCH"
  echo ""
  echo "  The SpecBox Engine contract requires ALL implementation"
  echo "  code to be written on a feature branch, never on main."
  echo ""
  echo "  To proceed:"
  echo "    1. git checkout -b feature/{nombre-del-feature} main"
  echo "    2. Then write your code on the feature branch"
  echo "    3. Create a PR when ready to merge"
  echo ""
  echo "  If using /implement, this branch is created in Paso 1."
  echo "  If implementing manually, create the branch FIRST."
  echo ""
  echo "  This is non-negotiable. Code on main = no PR = no review"
  echo "  = no acceptance evidence = no traceability."
  echo "============================================================"
  echo ""
  exit 1
fi

# Not on main/master → allow
exit 0
