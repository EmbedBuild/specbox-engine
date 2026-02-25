#!/bin/bash
# Analiza logs de sesiones con métricas de contexto
# Uso: .quality/scripts/analyze-sessions.sh [--last N]
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
TOTAL_FILES_MOD=0
TOTAL_TOKENS=0
TOTAL_HEALING=0
TOTAL_DAYS=0

for logfile in $LOG_FILES; do
  DATE=$(basename "$logfile" | sed 's/sessions_//' | sed 's/.jsonl//')
  COUNT=$(wc -l < "$logfile" | tr -d ' ')
  TOTAL_SESSIONS=$((TOTAL_SESSIONS + COUNT))
  TOTAL_DAYS=$((TOTAL_DAYS + 1))

  # Parse context metrics if available (requires jq or grep fallback)
  if command -v jq &>/dev/null; then
    DAY_TOKENS=$(jq -r '.context_tokens_est // 0' "$logfile" 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)
    DAY_FILES=$(jq -r '.files_modified // 0' "$logfile" 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)
    DAY_HEALING=$(jq -r '.healing_events // 0' "$logfile" 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)
  else
    DAY_TOKENS=$(grep -o '"context_tokens_est": [0-9]*' "$logfile" 2>/dev/null | grep -o '[0-9]*$' | paste -sd+ | bc 2>/dev/null || echo 0)
    DAY_FILES=$(grep -o '"files_modified": [0-9]*' "$logfile" 2>/dev/null | grep -o '[0-9]*$' | paste -sd+ | bc 2>/dev/null || echo 0)
    DAY_HEALING=$(grep -o '"healing_events": [0-9]*' "$logfile" 2>/dev/null | grep -o '[0-9]*$' | paste -sd+ | bc 2>/dev/null || echo 0)
  fi

  TOTAL_FILES_MOD=$((TOTAL_FILES_MOD + DAY_FILES))
  TOTAL_TOKENS=$((TOTAL_TOKENS + DAY_TOKENS))
  TOTAL_HEALING=$((TOTAL_HEALING + DAY_HEALING))

  printf "  %s: %d sessions | ~%d tokens | %d files | %d heals\n" "$DATE" "$COUNT" "$DAY_TOKENS" "$DAY_FILES" "$DAY_HEALING"
done

echo ""
echo "  ─── Totals ($TOTAL_DAYS days) ───"
echo "  Sessions:        $TOTAL_SESSIONS"
echo "  Files modified:  $TOTAL_FILES_MOD"
echo "  Context tokens:  ~$TOTAL_TOKENS (estimated)"
echo "  Healing events:  $TOTAL_HEALING"

if [ "$TOTAL_SESSIONS" -gt 0 ]; then
  AVG_TOKENS=$((TOTAL_TOKENS / TOTAL_SESSIONS))
  AVG_FILES=$((TOTAL_FILES_MOD / TOTAL_SESSIONS))
  echo ""
  echo "  ─── Averages (per session) ───"
  echo "  Avg tokens:     ~$AVG_TOKENS"
  echo "  Avg files:      $AVG_FILES"

  # Context budget health
  if [ "$AVG_TOKENS" -lt 30000 ]; then
    echo "  Budget health:   🟢 Healthy (< 15% avg)"
  elif [ "$AVG_TOKENS" -lt 60000 ]; then
    echo "  Budget health:   🟡 Moderate (15-30% avg)"
  else
    echo "  Budget health:   🔴 High (> 30% avg) — consider splitting tasks"
  fi
fi

echo ""

# Healing summary
if [ "$TOTAL_HEALING" -gt 0 ]; then
  echo "  ─── Healing Summary ───"
  for logfile in $LOG_FILES; do
    if command -v jq &>/dev/null; then
      FEATURES=$(jq -r 'select(.active_feature != "") | .active_feature' "$logfile" 2>/dev/null | sort -u)
    else
      FEATURES=$(grep -o '"active_feature": "[^"]*"' "$logfile" 2>/dev/null | grep -v '""' | sort -u | sed 's/.*: "//;s/"//')
    fi
    for feat in $FEATURES; do
      echo "  Feature: $feat"
    done
  done
  echo ""
fi
