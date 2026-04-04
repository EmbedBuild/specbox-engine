#!/usr/bin/env bash
# read-tracker.sh — PostToolUse hook for Read tool
# NON-BLOCKING: Records which files the agent has read in the current session.
# Used by quality-first-guard.sh to enforce "read before write."
#
# Behavior:
#   1. Extracts file_path from the Read tool input
#   2. Appends a JSON line to .quality/read_tracker.jsonl
#   3. Never blocks — this is a passive tracker
#
# Session lifecycle:
#   - The tracker file is auto-cleared at session start by on-session-end.sh
#   - If the file doesn't exist, it's created on first Read
#   - Stale trackers (>24h) are cleared automatically
#
# v5.15.0 — Quality First Enforcement

set -euo pipefail

INPUT=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Ensure .quality directory exists
mkdir -p .quality

TRACKER_FILE=".quality/read_tracker.jsonl"

# Clear stale tracker (older than 24 hours)
if [ -f "$TRACKER_FILE" ]; then
  if [ "$(uname -s)" = "Darwin" ]; then
    FILE_AGE=$(( $(date +%s) - $(stat -f %m "$TRACKER_FILE") ))
  else
    FILE_AGE=$(( $(date +%s) - $(stat -c %Y "$TRACKER_FILE") ))
  fi

  if [ "$FILE_AGE" -gt 86400 ]; then
    rm -f "$TRACKER_FILE"
  fi
fi

# Append the read event
TIMESTAMP=$(date +%s)
echo "{\"file\":\"$FILE_PATH\",\"ts\":$TIMESTAMP}" >> "$TRACKER_FILE"

exit 0
