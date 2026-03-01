#!/bin/bash
# Hook helper: envía datos al MCP remoto (fire-and-forget)
# Uso: mcp-report.sh <tool_name> '<json_arguments>'
# Requiere: DEV_ENGINE_MCP_URL env var
# Si no está configurado o falla, no hace nada (silencioso)

# Exit silently if MCP URL not configured
[ -z "$DEV_ENGINE_MCP_URL" ] && exit 0

TOOL_NAME="$1"
TOOL_ARGS="$2"

[ -z "$TOOL_NAME" ] && exit 0

# Resolve engine version dynamically from ENGINE_VERSION.yaml
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENGINE_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENGINE_VERSION="unknown"
if [ -f "$ENGINE_ROOT/ENGINE_VERSION.yaml" ]; then
  ENGINE_VERSION=$(grep '^version:' "$ENGINE_ROOT/ENGINE_VERSION.yaml" | head -1 | awk '{print $2}')
fi

# Run entire MCP call in background, silently
(
  MCP_URL="$DEV_ENGINE_MCP_URL"

  # Step 1: Initialize MCP session
  INIT_RESPONSE=$(curl -s --max-time 5 --connect-timeout 2 \
    -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json, text/event-stream" \
    -D /dev/stderr \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-03-26\",\"capabilities\":{},\"clientInfo\":{\"name\":\"jps-dev-engine-hook\",\"version\":\"$ENGINE_VERSION\"}}}" \
    2>/tmp/mcp_headers_$$ || exit 0)

  # Extract session ID from response headers
  SESSION_ID=$(grep -i 'mcp-session-id' /tmp/mcp_headers_$$ 2>/dev/null | tr -d '\r' | awk '{print $2}')
  rm -f /tmp/mcp_headers_$$

  [ -z "$SESSION_ID" ] && exit 0

  # Step 2: Send initialized notification
  curl -s --max-time 5 --connect-timeout 2 \
    -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
    > /dev/null 2>&1 || exit 0

  # Step 3: Call the tool
  curl -s --max-time 5 --connect-timeout 2 \
    -X POST "$MCP_URL" \
    -H "Content-Type: application/json" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$TOOL_NAME\",\"arguments\":$TOOL_ARGS}}" \
    > /dev/null 2>&1 || exit 0

) > /dev/null 2>&1 &

exit 0
