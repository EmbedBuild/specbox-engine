#!/usr/bin/env bash
# spec-guard.sh — PostToolUse hook for Write/Edit on source files (src/, lib/)
# BLOCKING: Prevents writing source code without an active UC in the project manager.
#
# This hook enforces the SpecBox Engine contract:
# "No code without traceability. No implementation without an active UC."
#
# Triggers: Write/Edit to files matching src/ or lib/ (excluding tests, docs, config)
# Behavior:
#   1. Checks if the project has a board configured (.claude/project-config.json)
#   2. If spec-driven: verifies at least one UC is "in_progress" via MCP
#   3. If no UC active → BLOCKS the write with clear instructions
#   4. If not spec-driven (no board) → allows (non-spec projects are unaffected)
#
# v5.7.0 — Pipeline Integrity Enforcement

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

# --- Check if project is spec-driven ---
# Supports all backends: Trello (boardId), Plane (boardId), FreeForm (backend_type=freeform)

BOARD_ID=""
BACKEND_TYPE=""

for config_file in ".claude/project-config.json" ".claude/settings.local.json"; do
  if [ -f "$config_file" ]; then
    # Check boardId (Trello/Plane)
    if [ -z "$BOARD_ID" ]; then
      BOARD_ID=$(grep -oE '"boardId"\s*:\s*"[^"]*"' "$config_file" 2>/dev/null | head -1 | sed 's/.*"boardId"\s*:\s*"//;s/"$//')
    fi
    # Check board_id (snake_case variant)
    if [ -z "$BOARD_ID" ]; then
      BOARD_ID=$(grep -oE '"board_id"\s*:\s*"[^"]*"' "$config_file" 2>/dev/null | head -1 | sed 's/.*"board_id"\s*:\s*"//;s/"$//')
    fi
    # Check backend_type (FreeForm detection)
    if [ -z "$BACKEND_TYPE" ]; then
      BACKEND_TYPE=$(grep -oE '"backend_type"\s*:\s*"[^"]*"' "$config_file" 2>/dev/null | head -1 | sed 's/.*"backend_type"\s*:\s*"//;s/"$//')
    fi
  fi
done

# If no board and no backend configured → not spec-driven, allow
if [ -z "$BOARD_ID" ] && [ -z "$BACKEND_TYPE" ]; then
  exit 0
fi

# --- Spec-driven project: verify active UC ---

# Check for active UC marker (written by start_uc or /implement)
ACTIVE_UC_FILE=".quality/active_uc.json"

if [ -f "$ACTIVE_UC_FILE" ]; then
  # Verify it's not stale (older than 24 hours)
  if [ "$(uname -s)" = "Darwin" ]; then
    FILE_AGE=$(( $(date +%s) - $(stat -f %m "$ACTIVE_UC_FILE") ))
  else
    FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$ACTIVE_UC_FILE") ))
  fi

  # 24 hours = 86400 seconds
  if [ "$FILE_AGE" -lt 86400 ]; then
    # Active UC exists and is fresh → allow
    exit 0
  else
    echo ""
    echo "============================================================"
    echo "  ⛔ SPEC GUARD: Active UC marker is stale (>24h)"
    echo "============================================================"
    echo "  File: $FILE_PATH"
    echo "  The active UC marker at $ACTIVE_UC_FILE is older than 24 hours."
    echo "  This likely means the previous implementation session ended"
    echo "  without completing the UC."
    echo ""
    echo "  To proceed:"
    echo "    1. Run start_uc(board_id, uc_id) to activate a UC"
    echo "    2. Or use /implement to start the pipeline properly"
    echo "============================================================"
    echo ""
    exit 1
  fi
fi

# No active UC marker → BLOCK
echo ""
echo "============================================================"
echo "  ⛔ SPEC GUARD: No active UC — implementation blocked"
echo "============================================================"
echo "  File: $FILE_PATH"
echo "  Board: $BOARD_ID"
echo ""
echo "  This project uses spec-driven development (Trello/Plane)."
echo "  You MUST have an active UC before writing source code."
echo ""
echo "  The SpecBox Engine contract is non-negotiable:"
echo "  No code without traceability. No implementation without pipeline."
echo ""
echo "  To proceed:"
echo "    1. find_next_uc(board_id) → identify the next UC"
echo "    2. start_uc(board_id, uc_id) → move to In Progress"
echo "    3. Then implement the code"
echo "    4. mark_ac_batch(...) → check acceptance criteria"
echo "    5. complete_uc(board_id, uc_id) → move to Done"
echo ""
echo "  If /implement skill is unavailable, execute these steps"
echo "  MANUALLY. The pipeline is the contract, not the skill."
echo "============================================================"
echo ""
exit 1
