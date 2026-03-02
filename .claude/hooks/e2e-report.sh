#!/usr/bin/env bash
# Hook: Report E2E results to Dev Engine MCP
# Usage: ./hooks/e2e-report.sh [results-json-path]
set -euo pipefail

RESULTS_JSON="${1:-}"
PROJECT=$(basename "$(git rev-parse --show-toplevel)")
ENGINE_VERSION=$(grep 'version:' "$(dirname "$0")/../../ENGINE_VERSION.yaml" 2>/dev/null | head -1 | awk '{print $2}' || echo "unknown")
MCP_URL="${DEV_ENGINE_MCP_URL:-}"

# Auto-detect results file
if [[ -z "$RESULTS_JSON" ]]; then
  for candidate in e2e/test-results.json test-results/results.json playwright-report/results.json; do
    if [[ -f "$candidate" ]]; then
      RESULTS_JSON="$candidate"
      break
    fi
  done
fi

if [[ -z "$MCP_URL" || -z "$RESULTS_JSON" || ! -f "$RESULTS_JSON" ]]; then
  exit 0
fi

TOTAL=$(jq '.stats.expected + .stats.unexpected + .stats.skipped' "$RESULTS_JSON")
PASSING=$(jq '.stats.expected' "$RESULTS_JSON")
FAILING=$(jq '.stats.unexpected' "$RESULTS_JSON")
SKIPPED=$(jq '.stats.skipped' "$RESULTS_JSON")
DURATION=$(jq '.stats.duration' "$RESULTS_JSON")

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/mcp-report.sh"

mcp_call "report_e2e_results" "{
  \"project\": \"$PROJECT\",
  \"total\": $TOTAL,
  \"passing\": $PASSING,
  \"failing\": $FAILING,
  \"skipped\": $SKIPPED,
  \"duration_ms\": $DURATION,
  \"viewports\": [\"desktop-chrome\", \"tablet\", \"mobile\"],
  \"report_path\": \"doc/test_cases/reports/\",
  \"engine_version\": \"$ENGINE_VERSION\"
}"

echo "[e2e-report] $PASSING/$TOTAL passing → reported to MCP"
