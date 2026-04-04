#!/usr/bin/env bash
# quality-first-guard.sh — PreToolUse hook for Write and Edit tools
# BLOCKING: Prevents modifying existing files without reading them first.
#
# Philosophy: SpecBox Engine already provides speed. The LLM's job is QUALITY.
# The #1 cause of wasted tokens and technical debt is modifying code without
# understanding what's already there. This hook enforces "read before write."
#
# Behavior:
#   1. Extracts the target file_path from the tool input
#   2. Checks if the file already exists on disk
#   3. If it exists → verifies the agent has read it in this session
#   4. If not read → BLOCKS with clear instructions
#   5. If file is new (doesn't exist) → allows (creating new files is fine)
#   6. Skips generated files, lock files, and other non-source artifacts
#
# Session tracking:
#   Uses a session file at .quality/read_tracker.jsonl to record Read tool calls.
#   The tracker is cleared on session start (fresh session = fresh tracker).
#   Each line is a JSON object: {"file": "/path/to/file", "ts": 1234567890}
#
# v5.15.0 — Quality First Enforcement

set -euo pipefail

# Parse tool input from stdin
INPUT=$(cat)

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# If the file doesn't exist yet, it's a new file creation — allow
if [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

# Skip files that don't need read-before-write protection
# Generated files, lock files, config files, docs, etc.
if echo "$FILE_PATH" | grep -qE '(\.g\.dart|\.freezed\.dart|\.lock$|package-lock\.json|pubspec\.lock|poetry\.lock|\.min\.js|\.min\.css|node_modules/|\.dart_tool/|build/|dist/|\.next/)'; then
  exit 0
fi

# Skip non-source artifacts that are frequently auto-generated
if echo "$FILE_PATH" | grep -qE '(\.quality/|\.claude/|results\.json|baseline\.json|active_uc\.json|hint_counters\.json)'; then
  exit 0
fi

# --- Check read tracker ---
TRACKER_FILE=".quality/read_tracker.jsonl"

# If no tracker exists, the agent hasn't read anything — block
if [ ! -f "$TRACKER_FILE" ]; then
  echo ""
  echo "============================================================"
  echo "  QUALITY FIRST: Read before you write"
  echo "============================================================"
  echo "  File: $FILE_PATH"
  echo ""
  echo "  You are trying to modify an existing file without reading"
  echo "  it first. This is the #1 cause of wasted tokens and"
  echo "  technical debt."
  echo ""
  echo "  SpecBox provides speed. YOUR job is QUALITY."
  echo ""
  echo "  To proceed:"
  echo "    1. Use the Read tool to read this file"
  echo "    2. Understand what's already there"
  echo "    3. Then make your changes"
  echo ""
  echo "  Think before you act. Read before you write."
  echo "============================================================"
  echo ""
  exit 1
fi

# Normalize the file path for comparison (resolve relative paths)
NORMALIZED_PATH="$FILE_PATH"
if [[ "$FILE_PATH" != /* ]]; then
  NORMALIZED_PATH="$(pwd)/$FILE_PATH"
fi

# Check if the file (or a parent directory scan) was read in this session
# We check both the exact path and common prefixes
FILE_WAS_READ=false

# Check exact match
if grep -qF "\"$FILE_PATH\"" "$TRACKER_FILE" 2>/dev/null; then
  FILE_WAS_READ=true
fi

# Check normalized path
if [ "$FILE_WAS_READ" = false ] && grep -qF "\"$NORMALIZED_PATH\"" "$TRACKER_FILE" 2>/dev/null; then
  FILE_WAS_READ=true
fi

# Check basename match (handles cases where path format differs)
BASENAME=$(basename "$FILE_PATH")
if [ "$FILE_WAS_READ" = false ]; then
  # Match the basename within a full path to avoid false positives
  if grep -qE "\"[^\"]*/$BASENAME\"" "$TRACKER_FILE" 2>/dev/null; then
    FILE_WAS_READ=true
  fi
fi

if [ "$FILE_WAS_READ" = false ]; then
  echo ""
  echo "============================================================"
  echo "  QUALITY FIRST: Read before you write"
  echo "============================================================"
  echo "  File: $FILE_PATH"
  echo ""
  echo "  You are trying to modify an existing file without reading"
  echo "  it first in this session."
  echo ""
  echo "  The Quality First contract requires understanding existing"
  echo "  code before changing it. This prevents:"
  echo "    - Breaking existing functionality"
  echo "    - Duplicating code that already exists"
  echo "    - Introducing inconsistencies with surrounding code"
  echo "    - Wasting tokens on iterations that could be avoided"
  echo ""
  echo "  To proceed:"
  echo "    1. Use the Read tool to read '$FILE_PATH'"
  echo "    2. Understand the existing code"
  echo "    3. Then make your changes"
  echo "============================================================"
  echo ""
  exit 1
fi

# File was read — allow the write/edit
exit 0
