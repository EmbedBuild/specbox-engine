# Plan Tecnico: US-01 — Spec-Code Sync Layer

**US:** US-01 Spec-Code Sync Layer
**Fecha:** 2026-03-13
**Engine version base:** v4.2.0
**UCs cubiertos:** UC-001, UC-002, UC-003
**Estimacion:** 11-16 horas
**Restriccion clave:** No modificar el flujo core — las mejoras se añaden como extensiones.

---

## Arquitectura

3 capas nuevas, 4 archivos nuevos, 4 archivos modificados:

| Capa | Archivo | Proposito |
|------|---------|-----------|
| Captura (UC-001) | `server/delta_generator.py` | Genera bloques delta Markdown por fase |
| Escritura (UC-002) | `server/prd_writer.py` | Localiza PRD + append Implementation Status |
| Consulta (UC-003) | `server/prd_parser.py` | Parsea Implementation Status → JSON |
| MCP Tool (UC-003) | `server/tools/sync.py` | Tool `get_implementation_status` |

Modificaciones: `server/server.py` (+3 líneas registro), `.claude/skills/implement/SKILL.md` (+60 líneas pasos 5.1.1a, 7.7a, 8.5.3a)

## Fases

1. **Delta Generator** (UC-001) — `delta_generator.py` + tests
2. **PRD Writer** (UC-002) — `prd_writer.py` + tests
3. **PRD Parser + MCP Tool** (UC-003) — `prd_parser.py` + `tools/sync.py` + tests
4. **Integración SKILL.md** — pasos adicionales en /implement

## Formato Delta Block

```markdown
### Fase {N}: {phase_name}
- **Estado:** {complete|failed|needs_healing}
- **Archivos creados:** {lista o "ninguno"}
- **Archivos modificados:** {lista o "ninguno"}
- **Deltas vs plan:** {descripcion o "Sin deltas — implementacion conforme al plan"}
- **Decisiones:** {lista o "ninguna"}
- **Self-healing:** {tipo} — {resultado} (solo si aplica)
- **Error:** {resumen} (solo si fase falló)
```

## MCP Tool Response Schema

```json
{
  "uc_id": "UC-001",
  "timestamp": "2026-03-15T14:32:00Z",
  "branch": "feature/spec-code-sync",
  "phases": [{"phase_number": 1, "phase_name": "...", "status": "complete", ...}],
  "overall_status": "conforme|con_deltas|parcial|not_implemented",
  "delta_count": 0
}
```
