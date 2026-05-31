---
id: US-MCP-PATH-CONTRACT
ordinal: US-10
title: Eliminar deuda técnica de paths filesystem MCP-remoto en todas las tools cat A
status: ready
hours: 32
owner: Jesús Pérez
created: 2026-05-25
updated: 2026-05-31
source: items.json (FreeformBackend)
---

# US-MCP-PATH-CONTRACT — Eliminar deuda técnica de paths filesystem MCP-remoto en todas las tools cat A

## Como… quiero… para…

> Como operador del SpecBox Engine que ejecuta el MCP en VPS remoto (default en claude.ai web/iOS), quiero que TODAS las tools que tocan filesystem del proyecto cliente operen sobre contenido pasado por parámetro — no sobre paths resueltos contra el filesystem del MCP server — para que las tools nunca devuelvan datos mentirosos cuando MCP y cliente no comparten disco. Reemplaza el patrón v5.29 (absolute-path enforcement, parche local FreeForm-only) por el patrón content-passing universal. Cubre las 17 tools cat A vulnerables identificadas en la auditoría 2026-05-25.

## Use Cases asociados

| UC | Título | Estado |
|----|--------|--------|
| UC-614 | [Refactor 3 tools v6.0 Discovery a content-passing API](../uc/UC-052-refactor-3-tools-v6-0-discovery-a-content-passing-api.md) | ready |
| UC-615 | [Refactor skill /discovery para hacer I/O de filesystem en cliente](../uc/UC-053-refactor-skill-discovery-para-hacer-i-o-de-filesystem-en-cli.md) | ready |
| UC-616 | [Refactor app_docs.py (read_app_docs_tool + get_inheritable_values_tool)](../uc/UC-048-refactor-app-docs-py-read-app-docs-tool-get-inheritable-valu.md) | ready |
| UC-617 | [Refactor onboarding.py tools cat A (detect_project_stack, get_onboarding_status, get_visual_gap_report)](../uc/UC-047-refactor-onboarding-py-tools-cat-a-detect-project-stack-get-.md) | ready |
| UC-618 | [Refactor audit.py tools cat A (check_audit_tools_status, run_quality_audit)](../uc/UC-055-refactor-audit-py-tools-cat-a-check-audit-tools-status-run-q.md) | ready |
| UC-619 | [Refactor acceptance.py tools cat A (run_acceptance_check, get_acceptance_report, get_e2e_gap_report)](../uc/UC-054-refactor-acceptance-py-tools-cat-a-run-acceptance-check-get-.md) | ready |
| UC-620 | [Refactor remaining tools cat A (evidence_regen, skill_registry, hints, telemetry.get_context_budget, benchmark)](../uc/UC-056-refactor-remaining-tools-cat-a-evidence-regen-skill-registry.md) | ready |
| UC-621 | [Migration helpers: client-side path resolution utilities en .claude/hooks/lib/](../uc/UC-050-migration-helpers-client-side-path-resolution-utilities-en-c.md) | ready |
| UC-622 | [Migrar skills consumidores (/prd, /plan, /visual-setup, /app-sync, /audit, /acceptance-check)](../uc/UC-051-migrar-skills-consumidores-prd-plan-visual-setup-app-sync-au.md) | ready |
| UC-623 | [Documentación + CHANGELOG + version bump v6.0.1](../uc/UC-049-documentacion-changelog-version-bump-v6-0-1.md) | ready |

## Notas

_Documento legible auto-generado desde `items.json`. Editar la fuente vía MCP o regenerar con `.quality/scripts/generate-readable-tracking.py`._
