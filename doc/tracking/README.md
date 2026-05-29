# Tracking — specbox-engine

Capa de **lectura humana** sobre el FreeformBackend. Cuando necesites revisar
una US o un UC, busca aquí su markdown:

- **[`us/`](us/)** — un `.md` legible por cada User Story (18 docs).
- **[`uc/`](uc/)** — un `.md` legible por cada Use Case con sus ACs y enlace al US padre (99 docs).
- **[`_templates/`](_templates/)** — plantillas para crear US/UC nuevos a mano.

## Fuente de verdad

| Archivo | Rol | ¿Editar a mano? |
|---------|-----|-----------------|
| `items.json` | Fuente de verdad del FreeformBackend (US/UC/AC) | ❌ vía MCP |
| `config.json`, `labels.json`, `archive.json` | Estado del backend | ❌ vía MCP |
| `comments/`, `attachments/` | Comentarios y evidencia adjunta | ❌ vía MCP |
| `progress/` | Telemetría markdown auto-generada por el backend | ❌ auto |
| **`us/`, `uc/`** | **Capa de lectura curada (regenerable)** | ⚠️ regenerar |
| `index.json` | Índice ligero de esta capa | ⚠️ regenerar |

`us/` y `uc/` se **regeneran** desde `items.json` con:

```bash
python3 .quality/scripts/generate-readable-tracking.py
```

> Editar un `.md` de `us/` o `uc/` a mano se perderá en la próxima regeneración.
> Para cambios persistentes, muta el board vía las tools MCP (`update_uc`, `mark_ac`, …)
> y vuelve a generar.

## User Stories

| US | Título | Estado | UCs |
|----|--------|--------|-----|
| [US-BACKEND-SWITCH](us/US-BACKEND-SWITCH_cambio-guiado-de-backend-entre-los-4-freeform-trello-plane-n.md) | Cambio guiado de backend entre los 4 (FreeForm/Trello/Plane/Native) | review | 6 |
| [US-CLAIM-RENAME](us/US-CLAIM-RENAME_renombrar-el-concepto-claim-a-reservation-en-native-backend-.md) | Renombrar el concepto "claim" a "reservation" en Native Backend y Control Panel | draft | 13 |
| [US-CUTOVER-FOLLOWUP](us/US-CUTOVER-FOLLOWUP_cerrar-deuda-residual-de-sala-de-maquinas-tras-v6-1-0.md) | Cerrar deuda residual de Sala de Máquinas tras v6.1.0 | draft | 1 |
| [US-D01](us/US-D01_discovery-conversational-flow-per-feature.md) | Discovery conversational flow per feature | ready | 2 |
| [US-D02](us/US-D02_inheritance-and-traceability-from-discovery-to-implementatio.md) | Inheritance and traceability from discovery to implementation | ready | 1 |
| [US-D03](us/US-D03_strategic-drift-detection-across-project-lifetime.md) | Strategic drift detection across project lifetime | ready | 1 |
| [US-D04](us/US-D04_multi-document-canonical-registry-foundation.md) | Multi-document canonical registry foundation | ready | 2 |
| [US-MCP-OBSERVABILITY](us/US-MCP-OBSERVABILITY_observabilidad-otel-del-mcp-server-v6-2-0.md) | Observabilidad OTel del MCP server (v6.2.0) | draft | 0 |
| [US-MCP-OBSERVABILITY](us/US-MCP-OBSERVABILITY_observabilidad-otel-del-mcp-server-v6-2-0-dup1.md) | Observabilidad OTel del MCP server (v6.2.0) | draft | 8 |
| [US-MCP-PATH-CONTRACT](us/US-MCP-PATH-CONTRACT_eliminar-deuda-tecnica-de-paths-filesystem-mcp-remoto-en-tod.md) | Eliminar deuda técnica de paths filesystem MCP-remoto en todas las tools cat A | ready | 10 |
| [US-NATIVE-BACKEND](us/US-NATIVE-BACKEND_specbox-para-equipos-sobre-postgres-nativo.md) | SpecBox para equipos sobre Postgres nativo | done | 10 |
| [US-NATIVE-SECURITY](us/US-NATIVE-SECURITY_blindar-el-native-backend-contra-mutaciones-de-identidades-r.md) | Blindar el Native Backend contra mutaciones de identidades revocadas | review | 6 |
| [US-NATIVE-SUPABASE](us/US-NATIVE-SUPABASE_migrar-el-native-backend-de-postgres-vps-a-supabase-gestiona.md) | Migrar el Native Backend de Postgres-VPS a Supabase gestionado | done | 5 |
| [US-VSCODE-DISCOVERABILITY](us/US-VSCODE-DISCOVERABILITY_sidebar-de-descubrimiento-y-ayuda-para-la-extension-vscode.md) | Sidebar de descubrimiento y ayuda para la extensión VSCode | draft | 5 |
| [US-VSCODE-GITHUB-OAUTH](us/US-VSCODE-GITHUB-OAUTH_github-oauth-en-la-extension-vscode-native-backend-como-defa.md) | GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth | draft | 10 |
| [US-VSCODE-MARKETPLACE](us/US-VSCODE-MARKETPLACE_publicar-la-extension-specbox-al-vscode-marketplace-con-sync.md) | Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine | draft | 10 |
| [US-VSCODE-PREREQ-GATE](us/US-VSCODE-PREREQ-GATE_gate-de-prerequisitos-de-la-extension-vscode.md) | Gate de prerequisitos de la extensión VSCode | draft | 4 |
| [US-VSCODE-ZERO-PYTHON](us/US-VSCODE-ZERO-PYTHON_onboarding-cero-python-de-la-extension-vscode.md) | Onboarding cero-Python de la extensión VSCode | draft | 5 |

_Generado 2026-05-29 desde `items.json` (18 US · 99 UC · 462 AC)._
