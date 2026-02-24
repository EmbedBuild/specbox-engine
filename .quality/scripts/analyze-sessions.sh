#!/bin/bash
# Analiza logs de sesiones y genera resumen
# Uso: .quality/scripts/analyze-sessions.sh [--last N] [--date YYYY-MM-DD]
set -e

LOGS_DIR=".quality/logs"
LAST_N="${1:-7}"

if [ ! -d "$LOGS_DIR" ]; then
  echo "No logs directory found at $LOGS_DIR"
  exit 0
fi

LOG_FILES=$(find "$LOGS_DIR" -name "sessions_*.jsonl" -type f | sort -r | head -n "$LAST_N")

if [ -z "$LOG_FILES" ]; then
  echo "No session logs found"
  exit 0
fi

echo "╔══════════════════════════════════════╗"
echo "║  Session Telemetry Report            ║"
echo "╚══════════════════════════════════════╝"
echo ""

TOTAL_SESSIONS=0
TOTAL_FILES=0

for logfile in $LOG_FILES; do
  DATE=$(basename "$logfile" | sed 's/sessions_//' | sed 's/.jsonl//')
  COUNT=$(wc -l < "$logfile" | tr -d ' ')
  TOTAL_SESSIONS=$((TOTAL_SESSIONS + COUNT))
  TOTAL_FILES=$((TOTAL_FILES + 1))
  echo "  $DATE: $COUNT events"
done

echo ""
echo "  Total: $TOTAL_SESSIONS events across $TOTAL_FILES days"
echo ""

# Check healing logs
HEALING_FILES=$(find ".quality/evidence" -name "healing.jsonl" -type f 2>/dev/null || true)
if [ -n "$HEALING_FILES" ]; then
  echo "╔══════════════════════════════════════╗"
  echo "║  Self-Healing Summary                ║"
  echo "╚══════════════════════════════════════╝"
  echo ""
  for hf in $HEALING_FILES; do
    FEATURE=$(basename "$(dirname "$hf")")
    TOTAL=$(wc -l < "$hf" | tr -d ' ')
    RESOLVED=$(grep -c '"resolved"' "$hf" 2>/dev/null || echo 0)
    FAILED=$(grep -c '"failed"' "$hf" 2>/dev/null || echo 0)
    L3_PLUS=$(grep -E '"level": [34]' "$hf" 2>/dev/null | wc -l | tr -d ' ')
    echo "  $FEATURE: $TOTAL events ($RESOLVED resolved, $FAILED failed, $L3_PLUS level 3+)"
  done
  echo ""
fi

# Check checkpoints
CHECKPOINTS=$(find ".quality/evidence" -name "checkpoint.json" -type f 2>/dev/null || true)
if [ -n "$CHECKPOINTS" ]; then
  echo "╔══════════════════════════════════════╗"
  echo "║  Active Features (checkpoints)       ║"
  echo "╚══════════════════════════════════════╝"
  echo ""
  for cp in $CHECKPOINTS; do
    FEATURE=$(basename "$(dirname "$cp")")
    PHASE=$(grep -o '"phase": [0-9]*' "$cp" | grep -o '[0-9]*')
    STATUS=$(grep -o '"status": "[^"]*"' "$cp" | grep -o '"[^"]*"$' | tr -d '"')
    BRANCH=$(grep -o '"branch": "[^"]*"' "$cp" | grep -o '"[^"]*"$' | tr -d '"')
    echo "  $FEATURE: phase $PHASE ($STATUS) on $BRANCH"
  done
  echo ""
fi

echo "Done."
