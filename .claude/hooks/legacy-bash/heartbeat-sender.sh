#!/bin/bash
# Hook helper: envía heartbeat consolidado al VPS (fire-and-forget)
# Uso: heartbeat-sender.sh [project_name]
# Requiere: SPECBOX_ENGINE_MCP_URL env var (para derivar base URL del API)
# Si no está configurado o falla, guarda en pending queue.

# Exit silently if MCP URL not configured
SPECBOX_ENGINE_MCP_URL="${SPECBOX_ENGINE_MCP_URL:-$DEV_ENGINE_MCP_URL}"
[ -z "$SPECBOX_ENGINE_MCP_URL" ] && exit 0

# Derive API base URL from MCP URL (strip /mcp suffix)
API_BASE="${SPECBOX_ENGINE_MCP_URL%/mcp}"

# Auth token for heartbeat endpoint
SYNC_TOKEN="${SPECBOX_SYNC_TOKEN:-}"

# Project name: argument or auto-detect from git
PROJECT_NAME="${1:-}"
if [ -z "$PROJECT_NAME" ]; then
  PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null | tr '_' '-' || echo "unknown")
fi
[ "$PROJECT_NAME" = "unknown" ] && exit 0

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PENDING_FILE=".quality/pending_heartbeats.jsonl"

# --- Gather state from local filesystem ---

# Git branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# Last commit
LAST_COMMIT=$(git log -1 --pretty=format:'%s' 2>/dev/null || echo "")
LAST_COMMIT_AT=$(git log -1 --pretty=format:'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo "")

# Current feature from checkpoint
CURRENT_FEATURE=""
CURRENT_PHASE=""
CHECKPOINT=$(find .quality/evidence -name "checkpoint.json" 2>/dev/null | sort | tail -1)
if [ -n "$CHECKPOINT" ] && [ -f "$CHECKPOINT" ]; then
  CURRENT_FEATURE=$(jq -r '.feature // ""' "$CHECKPOINT" 2>/dev/null || echo "")
  PHASE_NUM=$(jq -r '.phase // ""' "$CHECKPOINT" 2>/dev/null || echo "")
  if [ -n "$PHASE_NUM" ]; then
    CURRENT_PHASE="implement"
  fi
fi

# Coverage from quality baseline
COVERAGE="null"
BASELINE=$(find .quality/baselines -name "*.json" 2>/dev/null | head -1)
if [ -n "$BASELINE" ] && [ -f "$BASELINE" ]; then
  COV_VAL=$(jq -r '.coverage // .test_coverage // empty' "$BASELINE" 2>/dev/null || echo "")
  [ -n "$COV_VAL" ] && COVERAGE="$COV_VAL"
fi

# Healing health
HEALING_EVENTS=0
HEALING_HEALTH="healthy"
HEALING_FILE=$(find .quality/evidence -name "healing.jsonl" 2>/dev/null | head -1)
if [ -n "$HEALING_FILE" ] && [ -f "$HEALING_FILE" ]; then
  HEALING_EVENTS=$(wc -l < "$HEALING_FILE" 2>/dev/null | tr -d ' ')
  [ "$HEALING_EVENTS" -gt 5 ] && HEALING_HEALTH="degraded"
  [ "$HEALING_EVENTS" -gt 15 ] && HEALING_HEALTH="critical"
fi

# Feedback
OPEN_FEEDBACK=0
BLOCKING_FEEDBACK=0
FB_DIR=".quality/evidence"
if [ -d "$FB_DIR" ]; then
  for fb in $(find "$FB_DIR" -name "FB-*.json" 2>/dev/null); do
    status=$(jq -r '.status // "open"' "$fb" 2>/dev/null || echo "open")
    if [ "$status" = "open" ]; then
      OPEN_FEEDBACK=$((OPEN_FEEDBACK + 1))
      severity=$(jq -r '.severity // "minor"' "$fb" 2>/dev/null || echo "minor")
      if [ "$severity" = "critical" ] || [ "$severity" = "major" ]; then
        BLOCKING_FEEDBACK=$((BLOCKING_FEEDBACK + 1))
      fi
    fi
  done
fi

# Build heartbeat payload
PAYLOAD=$(cat <<ENDJSON
{
  "project": "$PROJECT_NAME",
  "timestamp": "$TIMESTAMP",
  "session_active": true,
  "current_phase": "$CURRENT_PHASE",
  "current_feature": "$CURRENT_FEATURE",
  "current_branch": "$BRANCH",
  "coverage_pct": $COVERAGE,
  "open_feedback": $OPEN_FEEDBACK,
  "blocking_feedback": $BLOCKING_FEEDBACK,
  "healing_health": "$HEALING_HEALTH",
  "self_healing_events": $HEALING_EVENTS,
  "last_operation": "${2:-idle}",
  "last_commit": $(echo "$LAST_COMMIT" | jq -Rs .),
  "last_commit_at": "$LAST_COMMIT_AT"
}
ENDJSON
)

# --- Send pending heartbeats first ---
if [ -f "$PENDING_FILE" ] && [ -s "$PENDING_FILE" ]; then
  while IFS= read -r pending_payload; do
    [ -z "$pending_payload" ] && continue
    AUTH_HEADER=""
    [ -n "$SYNC_TOKEN" ] && AUTH_HEADER="-H \"Authorization: Bearer $SYNC_TOKEN\""
    eval curl -s --max-time 5 --connect-timeout 2 \
      -X POST "$API_BASE/api/heartbeat" \
      -H "Content-Type: application/json" \
      $AUTH_HEADER \
      -d "'$pending_payload'" > /dev/null 2>&1 || true
  done < "$PENDING_FILE"
  > "$PENDING_FILE"  # Clear pending file
fi

# --- Send current heartbeat ---
AUTH_ARGS=""
[ -n "$SYNC_TOKEN" ] && AUTH_ARGS="-H \"Authorization: Bearer $SYNC_TOKEN\""

RESPONSE=$(eval curl -s --max-time 5 --connect-timeout 2 -o /dev/null -w "%{http_code}" \
  -X POST "$API_BASE/api/heartbeat" \
  -H "Content-Type: application/json" \
  $AUTH_ARGS \
  -d "'$PAYLOAD'" 2>/dev/null || echo "000")

if [ "$RESPONSE" = "200" ]; then
  # Success — also write specbox-state.json locally
  REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
  if [ -n "$REPO_ROOT" ]; then
    # Write local state file (without server-side fields)
    LOCAL_STATE=$(echo "$PAYLOAD" | jq '. + {source: "local"}' 2>/dev/null || echo "$PAYLOAD")
    echo "$LOCAL_STATE" > "$REPO_ROOT/specbox-state.json"
  fi
else
  # Failed — queue for retry
  mkdir -p "$(dirname "$PENDING_FILE")"
  echo "$PAYLOAD" >> "$PENDING_FILE"
fi

exit 0
