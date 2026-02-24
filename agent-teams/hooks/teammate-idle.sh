#!/bin/bash
# ==============================================================================
# Hook: TeammateIdle
# Se ejecuta cuando un teammate termina su tarea actual y queda disponible.
#
# Variables de entorno disponibles:
#   TEAMMATE_NAME    - Nombre del teammate (ej: FlutterSpecialist)
#   TEAMMATE_ROLE    - Rol del teammate (ej: flutterSpecialist)
#   TASK_ID          - ID de la tarea que acaba de completar
#   TASK_DURATION    - Duracion en segundos de la tarea
#   PROJECT_ROOT     - Raiz del proyecto
#   TEAM_LOG_DIR     - Directorio de logs del equipo
# ==============================================================================

set -euo pipefail

# --- Configuracion ---
LOG_DIR="${TEAM_LOG_DIR:-${PROJECT_ROOT:-.}/.claude/team-logs}"
LOG_FILE="${LOG_DIR}/teammate-activity.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Crear directorio de logs si no existe
mkdir -p "${LOG_DIR}"

# --- Registrar completado ---
echo "[${TIMESTAMP}] IDLE | ${TEAMMATE_NAME:-unknown} | tarea=${TASK_ID:-none} | duracion=${TASK_DURATION:-0}s" >> "${LOG_FILE}"

# --- Verificacion de calidad basica ---
# Solo ejecutar verificaciones si hay archivos modificados
MODIFIED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")

if [ -z "${MODIFIED_FILES}" ]; then
    echo "[${TIMESTAMP}] IDLE | ${TEAMMATE_NAME:-unknown} | Sin archivos modificados, omitiendo verificacion" >> "${LOG_FILE}"
    exit 0
fi

# Verificar segun el rol del teammate
case "${TEAMMATE_ROLE:-}" in
    flutterSpecialist)
        # Verificar que no hay errores de analisis en archivos Dart modificados
        DART_FILES=$(echo "${MODIFIED_FILES}" | grep '\.dart$' || true)
        if [ -n "${DART_FILES}" ]; then
            if command -v flutter &> /dev/null; then
                ANALYZE_RESULT=$(flutter analyze --no-pub 2>&1 || true)
                ERRORS=$(echo "${ANALYZE_RESULT}" | grep -c "error" || true)
                echo "[${TIMESTAMP}] CHECK | ${TEAMMATE_NAME} | flutter analyze: ${ERRORS} errores" >> "${LOG_FILE}"
            fi
        fi
        ;;

    reactSpecialist)
        # Verificar tipos TypeScript en archivos modificados
        TS_FILES=$(echo "${MODIFIED_FILES}" | grep -E '\.(ts|tsx)$' || true)
        if [ -n "${TS_FILES}" ]; then
            if command -v npx &> /dev/null && [ -f "tsconfig.json" ]; then
                TSC_RESULT=$(npx tsc --noEmit 2>&1 || true)
                ERRORS=$(echo "${TSC_RESULT}" | grep -c "error TS" || true)
                echo "[${TIMESTAMP}] CHECK | ${TEAMMATE_NAME} | tsc: ${ERRORS} errores" >> "${LOG_FILE}"
            fi
        fi
        ;;

    dbInfra)
        # Verificar que las migraciones tienen RLS
        SQL_FILES=$(echo "${MODIFIED_FILES}" | grep -E '\.sql$' || true)
        if [ -n "${SQL_FILES}" ]; then
            for sql_file in ${SQL_FILES}; do
                if [ -f "${sql_file}" ]; then
                    HAS_CREATE_TABLE=$(grep -c "CREATE TABLE" "${sql_file}" 2>/dev/null || true)
                    HAS_RLS=$(grep -c "ENABLE ROW LEVEL SECURITY" "${sql_file}" 2>/dev/null || true)
                    if [ "${HAS_CREATE_TABLE}" -gt 0 ] && [ "${HAS_RLS}" -eq 0 ]; then
                        echo "[${TIMESTAMP}] WARN | ${TEAMMATE_NAME} | ${sql_file}: CREATE TABLE sin RLS" >> "${LOG_FILE}"
                    fi
                fi
            done
        fi
        ;;

    qaReviewer)
        # Registrar resultados de cobertura si estan disponibles
        if [ -f "coverage/lcov.info" ]; then
            TOTAL_LINES=$(grep -c "DA:" coverage/lcov.info 2>/dev/null || true)
            COVERED=$(grep "DA:" coverage/lcov.info 2>/dev/null | grep -v ",0$" | wc -l || true)
            if [ "${TOTAL_LINES}" -gt 0 ]; then
                COVERAGE=$(( COVERED * 100 / TOTAL_LINES ))
                echo "[${TIMESTAMP}] CHECK | ${TEAMMATE_NAME} | cobertura: ${COVERAGE}%" >> "${LOG_FILE}"
            fi
        fi
        ;;

    *)
        echo "[${TIMESTAMP}] IDLE | ${TEAMMATE_NAME:-unknown} | Rol no reconocido, sin verificaciones" >> "${LOG_FILE}"
        ;;
esac

echo "[${TIMESTAMP}] IDLE | ${TEAMMATE_NAME:-unknown} | Verificacion post-tarea completada" >> "${LOG_FILE}"

exit 0
