#!/bin/bash
# Hook: Registra telemetría básica al finalizar sesión.
# NO bloqueante.

LOGS_DIR=".quality/logs"
mkdir -p "$LOGS_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DATE=$(date -u +%Y-%m-%d)
LOG_FILE="$LOGS_DIR/sessions_$DATE.jsonl"

# Registrar fin de sesión
echo "{\"event\": \"session_end\", \"timestamp\": \"$TIMESTAMP\", \"pwd\": \"$(pwd)\"}" >> "$LOG_FILE"

echo "[TELEMETRY] Session logged to $LOG_FILE"
