#!/bin/bash
# Hook helper: guarda checkpoint despues de cada fase de /implement
# Llamado desde dentro de la Skill /implement, no como hook automatico
# Uso: .claude/hooks/implement-checkpoint.sh <feature> <phase_number> <phase_name>

set -e

FEATURE="$1"
PHASE="$2"
PHASE_NAME="$3"
BRANCH="$(git branch --show-current 2>/dev/null || echo 'unknown')"

if [ -z "$FEATURE" ] || [ -z "$PHASE" ]; then
  echo "Usage: implement-checkpoint.sh <feature> <phase> <phase_name>"
  exit 1
fi

mkdir -p ".quality/evidence/${FEATURE}"

# Use printf to avoid JSON injection from phase names
printf '{\n  "feature": "%s",\n  "phase": %s,\n  "phase_name": "%s",\n  "branch": "%s",\n  "timestamp": "%s",\n  "status": "complete"\n}\n' \
  "$FEATURE" "$PHASE" "$PHASE_NAME" "$BRANCH" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > ".quality/evidence/${FEATURE}/checkpoint.json"

echo "[CHECKPOINT] Phase ${PHASE} (${PHASE_NAME}) saved for ${FEATURE}"

# Report to MCP (fire-and-forget)
# Normalize: replace underscores with hyphens to match MCP registry name
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null | tr '_' '-' || echo "unknown")
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
"$HOOKS_DIR/mcp-report.sh" "report_checkpoint" "{\"project\": \"$PROJECT_NAME\", \"feature\": \"$FEATURE\", \"phase\": $PHASE, \"phase_name\": \"$PHASE_NAME\", \"branch\": \"$BRANCH\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" &

# Send heartbeat with current phase info (fire-and-forget, background)
"$HOOKS_DIR/heartbeat-sender.sh" "$PROJECT_NAME" "implement" &
