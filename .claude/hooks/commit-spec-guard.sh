#!/usr/bin/env bash
# commit-spec-guard.sh — PostToolUse hook for git commit
# MIXED: Some checks BLOCK, others WARN.
#
# BLOCKING checks:
#   1. Commit on main/master in a spec-driven project → BLOCKED
#
# WARNING checks:
#   2. No active UC → WARNING
#   3. No checkpoint saved → WARNING
#   4. Large commit (>15 files) → WARNING
#
# v5.10.0 — Branch discipline enforcement added (BLOCKING)

set -euo pipefail

# --- Check if project is spec-driven ---
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

# Not spec-driven → skip all checks
if [ -z "$BOARD_ID" ] && [ -z "$BACKEND_TYPE" ]; then
  exit 0
fi

# --- BLOCKING Check: Branch discipline ---
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo ""
  echo "============================================================"
  echo "  COMMIT BLOCKED: Cannot commit to $CURRENT_BRANCH"
  echo "============================================================"
  echo "  This is a spec-driven project. ALL implementation commits"
  echo "  MUST be on a feature branch, never on main/master."
  echo ""
  echo "  To fix:"
  echo "    1. git stash"
  echo "    2. git checkout -b feature/{nombre}"
  echo "    3. git stash pop"
  echo "    4. Then commit on the feature branch"
  echo "============================================================"
  echo ""
  exit 1
fi

WARNINGS=0

# --- WARNING Check: Active UC exists ---
ACTIVE_UC_FILE=".quality/active_uc.json"
if [ ! -f "$ACTIVE_UC_FILE" ]; then
  echo ""
  echo "WARNING: Committing in a spec-driven project without an active UC."
  echo "  Board: $BOARD_ID"
  echo "  Expected: start_uc() should have been called before implementation."
  echo "  Action: Call start_uc() NOW, then mark_ac_batch() after commit."
  WARNINGS=$((WARNINGS + 1))
else
  UC_ID=$(grep -oE '"uc_id"\s*:\s*"[^"]*"' "$ACTIVE_UC_FILE" 2>/dev/null | head -1 | sed 's/.*"uc_id"\s*:\s*"//;s/"$//')
  if [ -n "$UC_ID" ]; then
    echo "[SPEC] Active UC: $UC_ID | Branch: $CURRENT_BRANCH"
  fi
fi

# --- WARNING Check: Checkpoint freshness ---
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

# --- WARNING Check: File count ---
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
  echo "  Remember: find_next_uc -> start_uc -> implement -> mark_ac_batch -> complete_uc"
  echo ""
fi

# Warnings don't block — only the branch check blocks
exit 0
