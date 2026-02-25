#!/bin/bash
# Hook helper: registra evento de self-healing en evidence
# Uso: .claude/hooks/implement-healing.sh <feature> <phase> <level> <action> [result]

set -e

FEATURE="$1"
PHASE="$2"
LEVEL="$3"
ACTION="$4"
RESULT="${5:-attempted}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ -z "$FEATURE" ] || [ -z "$PHASE" ] || [ -z "$LEVEL" ]; then
  echo "Usage: implement-healing.sh <feature> <phase> <level> <action> [result]"
  exit 1
fi

mkdir -p ".quality/evidence/${FEATURE}"

printf '{"phase": %s, "level": %s, "action": "%s", "result": "%s", "timestamp": "%s"}\n' \
  "$PHASE" "$LEVEL" "$ACTION" "$RESULT" "$TIMESTAMP" \
  >> ".quality/evidence/${FEATURE}/healing.jsonl"

echo "[HEALING] Level ${LEVEL} action logged for ${FEATURE} phase ${PHASE}"

# Report to MCP (fire-and-forget)
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null || echo "unknown")
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
"$HOOKS_DIR/mcp-report.sh" "report_healing" "{\"project\": \"$PROJECT_NAME\", \"feature\": \"$FEATURE\", \"phase\": $PHASE, \"level\": $LEVEL, \"action\": \"$ACTION\", \"result\": \"$RESULT\", \"timestamp\": \"$TIMESTAMP\"}" &
