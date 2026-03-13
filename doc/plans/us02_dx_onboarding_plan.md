# Plan Tecnico: US-02 — DX de Onboarding Mejorada

## User Story
"Como nuevo desarrollador que se incorpora a un proyecto que usa el Engine, quiero un flujo guiado que me ensene el pipeline completo paso a paso con un micro-proyecto de ejemplo, para ser productivo en 1-2 dias en lugar de 4-5."

## Use Cases

### UC-004: Skill /quickstart — Tutorial guiado interactivo
- **Archivo**: `.claude/skills/quickstart/SKILL.md`
- **Tipo**: Skill (YAML frontmatter + Markdown)
- **AC-15 a AC-20**: Crea demo project, guia 4 etapas, bloques explicativos, dry-run, resumen, < 5 min

### UC-005: Hints contextuales en skills existentes
- **Archivos**:
  - `server/hint_manager.py` — Logica pura Python (counters, thresholds, textos)
  - `server/tools/hints.py` — 3 MCP tools (get_skill_hint, record_skill_hint, list_skill_hints)
  - Registro en `server/server.py`
- **AC-21 a AC-25**: Hints para prd/implement/plan/feedback/quality-gate, counter en .quality/hint_counters.json, max 3 usos, threshold > 5 UCs completados

### UC-006: Wizard interactivo en onboard_project
- **Archivo**: `server/tools/onboarding.py` — nuevo tool `get_onboarding_wizard`
- **AC-26 a AC-30**: Wizard con preguntas + explicaciones, retrocompatible, config minima

## Tests
- `tests/test_hint_manager.py` — 18 tests (counters, thresholds, persistence, corruption handling)
- `tests/test_quickstart.py` — 13 tests (skill structure, hint integration, wizard structure)

## Arquitectura

```
server/
  hint_manager.py          <- NEW: Pure logic (should_show_hint, record, get_text)
  tools/
    hints.py               <- NEW: 3 MCP tools wrapping hint_manager
    onboarding.py           <- MODIFIED: +get_onboarding_wizard tool
  server.py                <- MODIFIED: +register_hint_tools import and call

.claude/skills/
  quickstart/SKILL.md      <- NEW: Tutorial interactivo

tests/
  test_hint_manager.py     <- NEW: 18 tests
  test_quickstart.py       <- NEW: 13 tests
```

## Decisiones de diseno

1. **hint_manager.py separado de tools**: La logica de hints es pura Python sin dependencia de FastMCP, facilitando testing y reutilizacion.
2. **Wizard como tool separado**: `get_onboarding_wizard` es un tool independiente en lugar de modificar `onboard_project`, manteniendo retrocompatibilidad total (AC-28).
3. **Counters en .quality/**: Se usa el directorio existente de calidad para almacenar `hint_counters.json`, consistente con otros artefactos del Engine.
4. **Quickstart como Skill fork**: Se ejecuta en subagente aislado para no contaminar la sesion principal. Usa tools basicos (Read, Write, Bash, Glob).
5. **Dry-run textual**: El /implement simulado muestra texto formateado, no ejecuta nada real — cumple AC-18 sin riesgo.
