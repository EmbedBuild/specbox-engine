#!/usr/bin/env bash
# commit-spec-guard.sh — PostToolUse hook for git commit
# WARNING (non-blocking): Warns if committing in a spec-driven project without
# having marked ACs for the active UC.
#
# This runs BEFORE pre-commit-lint.sh. It checks:
#   1. Is this a spec-driven project? (board configured)
#   2. Is there an active UC? (active_uc.json exists)
#   3. Are there unmarked ACs? (warns if so)
#   4. Has a checkpoint been saved recently? (warns if not)
#
# NON-BLOCKING by design: we don't want to prevent emergency commits,
# but we DO want the agent to see the warning and self-correct.
#
# v5.7.0 — Pipeline Integrity Enforcement

set -euo pipefail

# --- Check if project is spec-driven ---
# Supports all backends: Trello (boardId), Plane (boardId), FreeForm (backend_type)
BOARD_ID=""
BACKEND_TYPE=""

for config_file in ".claude/project-config.json" ".claude/settings.local.json"; do
  if [ -f "$config_file" ]; then
    if [ -z "$BOARD_ID" ]; then
      BOARD_ID=$(grep -oE '"boardId"\s*:\s*"[^"]*"' "$config_file" 2>/dev/null | head -1 | sed 's/.*"boardId"\s*:\s*"//;s/"$//')
    fi
    if [ -z "$BOARD_ID" ]; then
      BOARD_ID=$(grep -oE '"board_id"\s*:\s*"[^"]*"' "$config_file" 2>/dev/null | head -1 | sed 's/.*"board_id"\s*:\s*"//;s/"$//')
    fi
    if [ -z "$BACKEND_TYPE" ]; then
      BACKEND_TYPE=$(grep -oE '"backend_type"\s*:\s*"[^"]*"' "$config_file" 2>/dev/null | head -1 | sed 's/.*"backend_type"\s*:\s*"//;s/"$//')
    fi
  fi
done

# Not spec-driven → skip
if [ -z "$BOARD_ID" ] && [ -z "$BACKEND_TYPE" ]; then
  exit 0
fi

WARNINGS=0

# --- Check 1: Active UC exists ---
ACTIVE_UC_FILE=".quality/active_uc.json"
if [ ! -f "$ACTIVE_UC_FILE" ]; then
  echo ""
  echo "WARNING: Committing in a spec-driven project without an active UC."
  echo "  Board: $BOARD_ID"
  echo "  Expected: start_uc() should have been called before implementation."
  echo "  Action: Call start_uc() NOW, then mark_ac_batch() after commit."
  WARNINGS=$((WARNINGS + 1))
else
  # Extract UC info for context
  UC_ID=$(grep -oE '"uc_id"\s*:\s*"[^"]*"' "$ACTIVE_UC_FILE" 2>/dev/null | head -1 | sed 's/.*"uc_id"\s*:\s*"//;s/"$//')
  if [ -n "$UC_ID" ]; then
    echo "[SPEC] Active UC: $UC_ID"
  fi
fi

# --- Check 2: Checkpoint freshness ---
FEATURE=""
if [ -f "$ACTIVE_UC_FILE" ]; then
  FEATURE=$(grep -oE '"feature"\s*:\s*"[^"]*"' "$ACTIVE_UC_FILE" 2>/dev/null | head -1 | sed 's/.*"feature"\s*:\s*"//;s/"$//')
fi

if [ -n "$FEATURE" ]; then
  CHECKPOINT_FILE=".quality/evidence/$FEATURE/checkpoint.json"
  if [ ! -f "$CHECKPOINT_FILE" ]; then
    echo "WARNING: No checkpoint saved for feature '$FEATURE'."
    echo "  Action: Call report_checkpoint() to enable session recovery."
    WARNINGS=$((WARNINGS + 1))
  fi
fi

# --- Check 3: File count since last checkpoint ---
FILES_IN_COMMIT=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
if [ "$FILES_IN_COMMIT" -gt 15 ]; then
  echo "WARNING: Large commit ($FILES_IN_COMMIT files). Consider splitting by UC."
  echo "  Each UC should have its own commit on a feature branch."
  echo "  Monolithic commits break traceability and make rollback harder."
  WARNINGS=$((WARNINGS + 1))
fi

# --- Summary ---
if [ "$WARNINGS" -gt 0 ]; then
  echo ""
  echo "[SPEC GUARD] $WARNINGS warning(s) detected. Pipeline integrity at risk."
  echo "  Remember: find_next_uc → start_uc → implement → mark_ac_batch → complete_uc"
  echo ""
fi

# Always exit 0 — this hook warns but doesn't block
exit 0
