#!/bin/bash
# ==============================================================================
# Hook: TaskCompleted
# Se ejecuta cuando una tarea completa se marca como finalizada.
# Ejecuta validaciones automaticas: lint, analyze, test, cobertura.
#
# Variables de entorno disponibles:
#   TASK_ID          - ID de la tarea completada
#   TASK_NAME        - Nombre descriptivo de la tarea
#   TASK_ASSIGNEE    - Teammate que la completo
#   PROJECT_ROOT     - Raiz del proyecto
#   TEAM_LOG_DIR     - Directorio de logs del equipo
#   STACK            - Stack del proyecto (flutter, react, go, python, multi)
# ==============================================================================

set -euo pipefail

# --- Configuracion ---
LOG_DIR="${TEAM_LOG_DIR:-${PROJECT_ROOT:-.}/.claude/team-logs}"
LOG_FILE="${LOG_DIR}/task-validation.log"
REPORT_FILE="${LOG_DIR}/validation-report-${TASK_ID:-unknown}.txt"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
EXIT_CODE=0

# Crear directorio de logs si no existe
mkdir -p "${LOG_DIR}"

# --- Funciones auxiliares ---

log() {
    echo "[${TIMESTAMP}] $1" >> "${LOG_FILE}"
    echo "$1" >> "${REPORT_FILE}"
}

log_section() {
    echo "" >> "${REPORT_FILE}"
    echo "=== $1 ===" >> "${REPORT_FILE}"
    echo "" >> "${REPORT_FILE}"
}

check_result() {
    local name="$1"
    local result="$2"
    local exit="$3"

    if [ "${exit}" -eq 0 ]; then
        log "PASS | ${name}"
    else
        log "FAIL | ${name}"
        EXIT_CODE=1
    fi
}

# --- Inicio del reporte ---
echo "Reporte de validacion - Tarea: ${TASK_ID:-unknown}" > "${REPORT_FILE}"
echo "Fecha: ${TIMESTAMP}" >> "${REPORT_FILE}"
echo "Tarea: ${TASK_NAME:-sin nombre}" >> "${REPORT_FILE}"
echo "Responsable: ${TASK_ASSIGNEE:-sin asignar}" >> "${REPORT_FILE}"
echo "Stack: ${STACK:-no definido}" >> "${REPORT_FILE}"

log "TASK_COMPLETED | tarea=${TASK_ID:-unknown} | responsable=${TASK_ASSIGNEE:-unknown}"

# --- Detectar stack si no esta definido ---
DETECTED_STACK="${STACK:-}"
if [ -z "${DETECTED_STACK}" ]; then
    if [ -f "pubspec.yaml" ]; then
        DETECTED_STACK="flutter"
    elif [ -f "package.json" ] && [ -f "next.config.ts" -o -f "next.config.js" -o -f "next.config.mjs" ]; then
        DETECTED_STACK="react"
    elif [ -f "pyproject.toml" ] || [ -f "requirements.txt" ]; then
        DETECTED_STACK="python"
    else
        DETECTED_STACK="unknown"
    fi
    log "Stack auto-detectado: ${DETECTED_STACK}"
fi

# --- Validaciones por stack ---

# ---- Flutter ----
if [ "${DETECTED_STACK}" = "flutter" ] || [ "${DETECTED_STACK}" = "multi" ]; then
    if command -v flutter &> /dev/null; then
        log_section "Flutter - Analisis estatico"

        # flutter analyze
        ANALYZE_OUTPUT=$(flutter analyze --no-pub 2>&1 || true)
        ANALYZE_EXIT=$?
        echo "${ANALYZE_OUTPUT}" >> "${REPORT_FILE}"
        check_result "flutter analyze" "${ANALYZE_OUTPUT}" "${ANALYZE_EXIT}"

        # flutter test
        log_section "Flutter - Tests"
        if [ -d "test" ]; then
            TEST_OUTPUT=$(flutter test --no-pub 2>&1 || true)
            TEST_EXIT=$?
            # Extraer resumen
            SUMMARY=$(echo "${TEST_OUTPUT}" | tail -5)
            echo "${SUMMARY}" >> "${REPORT_FILE}"
            check_result "flutter test" "${SUMMARY}" "${TEST_EXIT}"

            # Cobertura
            log_section "Flutter - Cobertura"
            COV_OUTPUT=$(flutter test --coverage --no-pub 2>&1 || true)
            if [ -f "coverage/lcov.info" ]; then
                TOTAL_LINES=$(grep -c "DA:" coverage/lcov.info 2>/dev/null || echo "0")
                COVERED=$(grep "DA:" coverage/lcov.info 2>/dev/null | grep -v ",0$" | wc -l | tr -d ' ' || echo "0")
                if [ "${TOTAL_LINES}" -gt 0 ]; then
                    COVERAGE=$(( COVERED * 100 / TOTAL_LINES ))
                    log "Cobertura: ${COVERAGE}% (${COVERED}/${TOTAL_LINES} lineas)"
                    if [ "${COVERAGE}" -lt 85 ]; then
                        log "WARN | Cobertura por debajo del 85%"
                        EXIT_CODE=1
                    fi
                else
                    log "WARN | No se pudo calcular cobertura (0 lineas)"
                fi
            else
                log "WARN | Archivo de cobertura no generado"
            fi
        else
            log "SKIP | Directorio test/ no encontrado"
        fi
    else
        log "SKIP | Flutter no instalado"
    fi
fi

# ---- React/Next.js ----
if [ "${DETECTED_STACK}" = "react" ] || [ "${DETECTED_STACK}" = "multi" ]; then
    if command -v npx &> /dev/null && [ -f "package.json" ]; then
        # TypeScript check
        log_section "React - Verificacion de tipos"
        if [ -f "tsconfig.json" ]; then
            TSC_OUTPUT=$(npx tsc --noEmit 2>&1 || true)
            TSC_EXIT=$?
            ERRORS=$(echo "${TSC_OUTPUT}" | grep -c "error TS" || true)
            echo "Errores de tipo: ${ERRORS}" >> "${REPORT_FILE}"
            check_result "tsc --noEmit (${ERRORS} errores)" "${TSC_OUTPUT}" "${TSC_EXIT}"
        fi

        # Next.js lint
        log_section "React - Linting"
        if [ -f "next.config.ts" ] || [ -f "next.config.js" ] || [ -f "next.config.mjs" ]; then
            LINT_OUTPUT=$(npx next lint 2>&1 || true)
            LINT_EXIT=$?
            echo "${LINT_OUTPUT}" | tail -5 >> "${REPORT_FILE}"
            check_result "next lint" "${LINT_OUTPUT}" "${LINT_EXIT}"
        fi

        # Vitest
        log_section "React - Tests"
        if grep -q "vitest" package.json 2>/dev/null; then
            TEST_OUTPUT=$(npx vitest run 2>&1 || true)
            TEST_EXIT=$?
            echo "${TEST_OUTPUT}" | tail -10 >> "${REPORT_FILE}"
            check_result "vitest run" "${TEST_OUTPUT}" "${TEST_EXIT}"

            # Cobertura
            log_section "React - Cobertura"
            COV_OUTPUT=$(npx vitest run --coverage 2>&1 || true)
            echo "${COV_OUTPUT}" | grep -E "(Statements|Branches|Functions|Lines)" >> "${REPORT_FILE}" 2>/dev/null || true
        fi
    else
        log "SKIP | Node/npx no instalado o package.json no encontrado"
    fi
fi

# ---- Python ----
if [ "${DETECTED_STACK}" = "python" ] || [ "${DETECTED_STACK}" = "multi" ]; then
    if command -v python3 &> /dev/null; then
        # Ruff linting
        log_section "Python - Linting"
        if command -v ruff &> /dev/null; then
            RUFF_OUTPUT=$(ruff check . 2>&1 || true)
            RUFF_EXIT=$?
            RUFF_ERRORS=$(echo "${RUFF_OUTPUT}" | grep -c "error" || true)
            echo "Errores de lint: ${RUFF_ERRORS}" >> "${REPORT_FILE}"
            check_result "ruff check (${RUFF_ERRORS} errores)" "${RUFF_OUTPUT}" "${RUFF_EXIT}"
        fi

        # Mypy
        log_section "Python - Verificacion de tipos"
        if command -v mypy &> /dev/null; then
            MYPY_OUTPUT=$(mypy . --ignore-missing-imports 2>&1 || true)
            MYPY_EXIT=$?
            echo "${MYPY_OUTPUT}" | tail -3 >> "${REPORT_FILE}"
            check_result "mypy" "${MYPY_OUTPUT}" "${MYPY_EXIT}"
        fi

        # Pytest
        log_section "Python - Tests"
        if [ -d "tests" ] || [ -d "test" ]; then
            PYTEST_OUTPUT=$(python3 -m pytest --tb=short -q 2>&1 || true)
            PYTEST_EXIT=$?
            echo "${PYTEST_OUTPUT}" | tail -5 >> "${REPORT_FILE}"
            check_result "pytest" "${PYTEST_OUTPUT}" "${PYTEST_EXIT}"

            # Cobertura
            log_section "Python - Cobertura"
            COV_OUTPUT=$(python3 -m pytest --cov --cov-report=term-missing -q 2>&1 || true)
            echo "${COV_OUTPUT}" | grep "TOTAL" >> "${REPORT_FILE}" 2>/dev/null || true
        fi
    else
        log "SKIP | Python3 no instalado"
    fi
fi

# ---- SQL (verificacion de migraciones) ----
if [ -d "supabase/migrations" ]; then
    log_section "SQL - Verificacion de migraciones"
    SQL_FILES=$(find supabase/migrations -name "*.sql" -newer "${LOG_DIR}/.last-check" 2>/dev/null || find supabase/migrations -name "*.sql" 2>/dev/null)

    for sql_file in ${SQL_FILES}; do
        if [ -f "${sql_file}" ]; then
            HAS_CREATE=$(grep -c "CREATE TABLE" "${sql_file}" 2>/dev/null || true)
            HAS_RLS=$(grep -c "ENABLE ROW LEVEL SECURITY" "${sql_file}" 2>/dev/null || true)
            HAS_COMMENT=$(grep -c "COMMENT ON" "${sql_file}" 2>/dev/null || true)

            if [ "${HAS_CREATE}" -gt 0 ]; then
                log "Migracion: ${sql_file}"
                if [ "${HAS_RLS}" -eq 0 ]; then
                    log "WARN | ${sql_file}: Tabla creada sin RLS"
                    EXIT_CODE=1
                else
                    log "PASS | ${sql_file}: RLS habilitado"
                fi
                if [ "${HAS_COMMENT}" -eq 0 ]; then
                    log "WARN | ${sql_file}: Sin COMMENT ON (documentacion)"
                fi
            fi
        fi
    done

    # Actualizar marca de tiempo
    touch "${LOG_DIR}/.last-check"
fi

# --- Resumen ---
log_section "Resumen"

if [ "${EXIT_CODE}" -eq 0 ]; then
    log "RESULTADO: TODAS LAS VALIDACIONES PASARON"
else
    log "RESULTADO: HAY VALIDACIONES FALLIDAS - Revisar el reporte"
fi

log "Reporte completo en: ${REPORT_FILE}"

exit ${EXIT_CODE}
