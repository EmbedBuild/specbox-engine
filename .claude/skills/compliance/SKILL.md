---
name: compliance
description: "SpecBox Engine compliance audit — checks version alignment, hooks, settings, quality infra, skills, and spec-driven compliance. Auto-fixes gaps and generates remediation plan."
triggers:
  - "check compliance"
  - "audit specbox"
  - "compliance check"
  - "specbox audit"
  - "compliance report"
  - "check specbox"
  - "audit engine"
  - "is specbox up to date"
context: direct
model: sonnet
tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# /compliance — SpecBox Engine Compliance Audit

## Objetivo

Auditar exhaustivamente el nivel de cumplimiento de un proyecto con SpecBox Engine.
Si la versión no está alineada, propone y ejecuta el upgrade.
Si está alineada, ejecuta una auditoría completa con scoring, gaps, y plan de remediación.

## Flujo

### Paso 0: Ejecutar auditor local

```bash
node .quality/scripts/specbox-audit.mjs "$(pwd)" --json --verbose
```

Si el script no existe en el proyecto, buscarlo en el engine:
```bash
# Localizar engine root
ENGINE_ROOT=$(cd "$(dirname "$(readlink -f ~/.claude/hooks/utils.mjs 2>/dev/null || echo ~/.claude/hooks)")" && cd ../.. && pwd)
node "${ENGINE_ROOT}/.quality/scripts/specbox-audit.mjs" "$(pwd)" --json --verbose
```

Parsear el JSON de salida. Este contiene toda la auditoría estructurada.

### Paso 1: Evaluar resultado

Leer el JSON y clasificar:

| Score | Grade | Acción |
|-------|-------|--------|
| 100% | A+ | Reportar compliance completo, felicitar |
| 90-99% | A | Reportar gaps menores, proponer fixes |
| 75-89% | B | Reportar gaps moderados, ejecutar auto-fix si hay |
| 60-74% | C | Reportar gaps significativos, plan de remediación |
| <60% | D/F | CRÍTICO — listar todo lo que falta |

### Paso 2: Si `needs_upgrade = true`

El proyecto no está en la versión del engine. Ofrecer al usuario:

1. **Mostrar qué cambiaría** — diff de versiones, features nuevas
2. **Ejecutar upgrade** — `upgrade_project` via MCP o `./install.sh`
3. **Re-auditar** — volver a ejecutar Paso 0 tras upgrade

**IMPORTANTE**: No ejecutar upgrade sin confirmación del usuario.

### Paso 3: Si hay `auto_fixable` items

Informar al usuario:

```
Se encontraron N problemas auto-resolvibles:
- Hook X.mjs no instalado → copiar desde engine
- Directorio .quality/baselines/ no existe → crear

¿Quieres que los arregle automáticamente?
```

Si el usuario confirma, ejecutar:
```bash
node .quality/scripts/specbox-audit.mjs "$(pwd)" --fix --json
```

### Paso 4: Generar reporte visual

Presentar al usuario una tabla Markdown con el resultado por categoría:

```markdown
## SpecBox Compliance Audit — {proyecto}

| Categoría | Score | Checks | Estado |
|-----------|-------|--------|--------|
| Version Alignment | 100% | 3/3 | ✓ |
| Hooks Installation | 87% | 13/15 | ✗ 2 hooks faltantes |
| Settings Configuration | 75% | 12/16 | ✗ 4 hooks sin registrar |
| Quality Infrastructure | 100% | 6/6 | ✓ |
| Skills Installation | 100% | 11/11 | ✓ |
| Spec-Driven Compliance | 100% | 3/3 | ✓ |

**Score global: 92% — Grade A (Minor gaps)**

### Issues críticos
(ninguno)

### Plan de remediación
1. Instalar hooks faltantes: healing-budget-guard.mjs, pipeline-phase-guard.mjs
2. Registrar hooks en settings.json: healing-budget-guard, pipeline-phase-guard
```

### Paso 5: Guardar evidencia

El auditor ya guarda `compliance-audit.json` en `.quality/evidence/`.
Informar al usuario de la ubicación del reporte.

## Reglas

1. **NUNCA** ejecutar upgrade sin confirmación del usuario
2. **SIEMPRE** ejecutar el script local primero — es la fuente de verdad
3. Si el script no existe en el proyecto, ejecutar desde el engine root
4. Mostrar resultados de forma clara y accionable
5. Si hay issues CRITICAL, enfatizarlos — son los que causan que el LLM se salte pasos
6. El score del audit debe persistir en `.quality/evidence/compliance-audit.json`
