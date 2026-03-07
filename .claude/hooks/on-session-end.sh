#!/bin/bash
# Hook: Registra telemetría al finalizar sesión (incluye context metrics).
# NO bloqueante.

LOGS_DIR=".quality/logs"
mkdir -p "$LOGS_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DATE=$(date -u +%Y-%m-%d)
LOG_FILE="$LOGS_DIR/sessions_$DATE.jsonl"

# Count files modified in this session (git-tracked changes)
FILES_MODIFIED=$(git diff --name-only HEAD 2>/dev/null | wc -l | tr -d ' ')

# Estimate context loaded (sum of modified + staged files in chars)
CONTEXT_CHARS=0
for f in $(git diff --name-only HEAD 2>/dev/null; git diff --cached --name-only 2>/dev/null); do
  if [ -f "$f" ]; then
    chars=$(wc -c < "$f" 2>/dev/null || echo 0)
    CONTEXT_CHARS=$((CONTEXT_CHARS + chars))
  fi
done
CONTEXT_TOKENS=$((CONTEXT_CHARS / 4))

# Count healing events if evidence exists
HEALING_EVENTS=0
FEATURE_DIR=$(find .quality/evidence -name "healing.jsonl" 2>/dev/null | head -1)
if [ -n "$FEATURE_DIR" ]; then
  HEALING_EVENTS=$(wc -l < "$FEATURE_DIR" 2>/dev/null | tr -d ' ')
fi

# Check for checkpoint (active implementation)
ACTIVE_FEATURE=""
CHECKPOINT=$(find .quality/evidence -name "checkpoint.json" -newer "$LOG_FILE" 2>/dev/null | head -1)
if [ -n "$CHECKPOINT" ]; then
  ACTIVE_FEATURE=$(dirname "$CHECKPOINT" | xargs basename)
fi

echo "{\"event\": \"session_end\", \"timestamp\": \"$TIMESTAMP\", \"pwd\": \"$(pwd)\", \"files_modified\": $FILES_MODIFIED, \"context_tokens_est\": $CONTEXT_TOKENS, \"healing_events\": $HEALING_EVENTS, \"active_feature\": \"$ACTIVE_FEATURE\"}" >> "$LOG_FILE"

echo "[TELEMETRY] Session logged to $LOG_FILE (est. ${CONTEXT_TOKENS} tokens, ${FILES_MODIFIED} files)"

# Persist session summary to Engram (REQUERIDO)
# Uses mem_session_summary to store structured session data in FTS5-indexed memory
if command -v engram &>/dev/null; then
  ENGRAM_SUMMARY="Session ended at $TIMESTAMP | Project: $(basename "$(pwd)") | Files modified: $FILES_MODIFIED | Context tokens: $CONTEXT_TOKENS | Healing events: $HEALING_EVENTS | Active feature: $ACTIVE_FEATURE"
  engram save "session-summary" "$ENGRAM_SUMMARY" 2>/dev/null &
  echo "[ENGRAM] Session summary persisted to Engram memory"
else
  # Detect OS and suggest appropriate install method
  OS_NAME="$(uname -s)"
  echo ""
  echo "============================================================"
  echo "  ERROR: ENGRAM NO INSTALADO"
  echo "============================================================"
  echo "  Engram es requerido para la memoria persistente del engine."
  echo "  Sin el, las compactaciones de contexto causan perdida de estado."
  echo ""
  case "$OS_NAME" in
    Darwin)
      echo "  SO detectado: macOS"
      echo ""
      echo "  Instalar:"
      echo "    # Apple Silicon (M1/M2/M3/M4):"
      echo "    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_darwin_arm64.tar.gz | tar xz"
      echo "    # Intel:"
      echo "    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_darwin_amd64.tar.gz | tar xz"
      echo "    mv engram ~/.local/bin/"
      ;;
    Linux)
      echo "  SO detectado: Linux"
      echo ""
      echo "  Instalar:"
      echo "    # x86_64:"
      echo "    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_linux_amd64.tar.gz | tar xz"
      echo "    # arm64:"
      echo "    curl -sL https://github.com/Gentleman-Programming/engram/releases/latest/download/engram_1.7.1_linux_arm64.tar.gz | tar xz"
      echo "    mv engram ~/.local/bin/"
      ;;
    MINGW*|MSYS*|CYGWIN*)
      echo "  SO detectado: Windows"
      echo ""
      echo "  Instalar:"
      echo "    Descargar desde: https://github.com/Gentleman-Programming/engram/releases/latest"
      echo "    Archivo: engram_1.7.1_windows_amd64.zip o engram_1.7.1_windows_arm64.zip"
      echo "    Descomprimir y mover engram.exe a una carpeta en el PATH"
      ;;
    *)
      echo "  SO detectado: $OS_NAME"
      echo ""
      echo "  Descargar desde: https://github.com/Gentleman-Programming/engram/releases/latest"
      ;;
  esac
  echo ""
  echo "  Verificar: engram save \"test\" \"hello engram\""
  echo "  MCP config: .vscode/mcp.json"
  echo "============================================================"
  echo ""
fi

# Report to MCP (fire-and-forget)
# Normalize: replace underscores with hyphens to match MCP registry name
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null | tr '_' '-' || echo "unknown")
HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
"$HOOKS_DIR/mcp-report.sh" "report_session" "{\"project\": \"$PROJECT_NAME\", \"timestamp\": \"$TIMESTAMP\", \"files_modified\": $FILES_MODIFIED, \"context_tokens_est\": $CONTEXT_TOKENS, \"healing_events\": $HEALING_EVENTS, \"active_feature\": \"$ACTIVE_FEATURE\"}" &
