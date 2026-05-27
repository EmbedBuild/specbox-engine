# Discovery: vscode_discoverability_sidebar

**Discovery ID**: disc-6e6f4a7048af
**Created**: 2026-05-27T09:00:12.797975+00:00
**Completed**: 2026-05-27
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ c9941ae49b3a1378

## ICPs involucrados

- **ICP-1** — Owner-operator del engine (JPS, dogfooding) — canónico, heredado de `app_market.md`.
- **ICP-2** — Dev solo con Claude Code que adopta SpecBox — tentative, heredado de `app_market.md`.

ICP-3 (equipo/agencia con reporting a cliente) queda fuera de esta feature — su discoverability vive en specbox_cloud (panel web externo), no en la extensión VSCode.

## JTBDs racionales

### Para ICP-1 (owner-operator)

- **JR-F.1 [ICP-1]**: Cuando libero una nueva versión del engine con skills nuevos (caso real: v6.0 añadió `/discovery`, v6.2 `/handoff`), quiero que el sidebar de la extensión refleje automáticamente los skills reales instalados en disco, para que la lista no derive manualmente cada release y no tenga que recordar tocar `skills-tree.ts`.

- **JR-F.2 [ICP-1]**: Cuando estoy revisando un proyecto onboardeado y quiero recordar la sintaxis exacta de un skill (p.ej. `/audit` acepta argumentos opcionales), quiero consultar la ficha del skill desde el sidebar sin abrir documentación externa ni el `CLAUDE.md`, para refrescar el uso en <5 segundos.

### Para ICP-2 (dev que adopta SpecBox)

- **JR-F.3 [ICP-2]**: Cuando termino el walkthrough de 4 pasos (install + MCP + onboard), quiero descubrir qué slash commands existen y qué hace cada uno sin tener que leer el README o el `CLAUDE.md` de 1500 líneas, para empezar a usar SpecBox de verdad en mi proyecto.

- **JR-F.4 [ICP-2]**: Cuando hago click en un skill del sidebar, quiero que se despliegue una ficha con (a) qué hace el skill, (b) cuándo usarlo, (c) el comando exacto a teclear en el chat de Claude Code, y (d) un ejemplo realista, para entender el skill sin tener que ejecutarlo a ciegas. **El click NO ejecuta el skill** — la invocación la hace el usuario en el chat manualmente; el sidebar es discovery + ayuda, no launcher.

- **JR-F.5 [ICP-2]**: Cuando veo los 25+ skills agrupados por categoría (Pipeline / Quality / Visual / Tracking / Stripe / Lifecycle), quiero entender de un vistazo qué fase del workflow cubre cada uno, para construir mental model del engine sin memorizar nombres sueltos.

## JTBDs emocionales

### Para ICP-1

- **JE-F.1 [ICP-1]**: Sentir que la extensión que publico bajo mi nombre (`EmbedBuild.specbox-engine`) refleja la calidad del engine — no que tiene un sidebar con un skill fantasma (`remote`) eliminado hace dos releases. El drift mata la credibilidad del producto frente a mí mismo cuando hago dogfooding.

### Para ICP-2

- **JE-F.2 [ICP-2]**: Sentir que tras instalar la extensión del Marketplace tengo el sistema entero al alcance — no un icono mudo en la activity bar que muestra status del engine y 15 skills hardcoded de los cuales 3 no existen. La extensión es la cara visible del engine: si parece abandonada, el usuario asume que el engine también.

- **JE-F.3 [ICP-2]**: Confianza de que lo que el sidebar muestra es real. Si un skill aparece como "instalado", su ficha debe describir correctamente lo que hace y el comando debe funcionar al copiarlo al chat. La sensación opuesta — "esto es una fachada, los iconos no hacen nada útil" — es la que mata la adopción post-install.

## Validation evidence

**Resolución: waiver explícito.**

Justificación:

1. **ICP-1 es directo (dogfooding)** — el owner-operator del engine es a la vez el primer usuario. La evidencia es uso propio, no necesita validación con terceros.

2. **La feature nace de un datapoint observado durante este mismo `/discovery`**: la auditoría de `vscode-extension/src/views/skills-tree.ts` reveló drift severo respecto al estado real del filesystem:
   - Skill `remote` hardcoded pese a haber sido eliminado en v6.1.0 (Cloud Cutover).
   - 11 skills instalados en `~/.claude/skills/` ausentes del TreeView (`app-init`, `app-sync`, `audit`, `discovery`, `feedback`, `handoff`, `manual-test`, `queue-review`, `stripe-connect`, `stripe-standard`, `stripe-switch-account`, `switch-backend`).
   - Items del TreeView sin `command:` ni `contextValue` — el click hoy no hace nada.
   - El walkthrough `step-install.md` describe "Install 15 skills" cuando realmente hay 25.

   El código del producto **demuestra el problema** que la US viene a resolver. No es una hipótesis a validar — es un hecho auditable hoy.

3. **ICP-2 es tentative** en `app_market.md` y no hay cohorte real con quien hacer entrevistas v1. Esperar a tener early adopters comprometidos para construir esta US bloquearía el funnel post-install precisamente cuando es más importante (extensión recién publicada en Marketplace en v6.2.0, default Native OAuth en v6.3.0, momento crítico de adopción).

Registrar la auditoría como evidence retrospectiva:

- `vscode-extension/src/views/skills-tree.ts:5-21` — drift hardcoded de 15 skills, 1 fantasma + 11 ausentes vs realidad.
- `vscode-extension/package.json:142` — string "Install 15 skills" en walkthrough description.
- `~/.claude/skills/` — 25 skills reales instalados en disco.
- Engram observación #5780 (2026-05-26) — primera identificación del gap.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. ICP-1 + ICP-2 ya canónicos/tentative en `app_market.md`.
- **Nuevos JTBDs introducidos**:
  - 5 racionales feature-scoped (JR-F.1..F.5) — no candidatos a global, son específicos del sidebar.
  - 2 emocionales feature-scoped (JE-F.2, JE-F.3) — específicos de la UI.
  - 1 emocional con generalización a global (JE-F.1).
- **Resolución**: `app_market_updated` — promovido un nuevo JTBD emocional global **JE-G.3** a `app_market.md` zona `jtbds_emotional_global`:

  > **JE-G.3**: Sentir que cada artefacto visible del producto — listing del Marketplace, sidebar de la extensión VSCode, walkthrough, README, panel cloud, CLI de ayuda — refleja la disciplina interna del engine. Drift entre la realidad del código y lo que la UI muestra (skills fantasma, descripciones desactualizadas, iconos mudos) mata la credibilidad del producto frente a quien lo está adoptando. La cara visible del producto es la primera evidencia de su calidad.

  JE-F.1 (feature-scoped) y JE-G.3 (global) son la **misma idea en dos niveles de abstracción**: JE-F.1 instancia el principio para esta US concreta; JE-G.3 lo declara como contrato del producto aplicable a futuros artefactos.

## Verdict

**READY_FOR_PRD**

- ICPs: 2 declarados, ambos heredados de `app_market.md` (no drift de ICPs).
- JTBDs racionales: 5 (formato canónico "Cuando…, quiero…, para…").
- JTBDs emocionales: 3.
- Validation evidence: waiver explícito con datapoint auditable hoy en el código.
- Drift: resuelto vía `app_market_updated` (JE-G.3 promovido).

Next step recomendado: `/prd vscode_discoverability_sidebar`.

---

> Este artefacto se completó interactivamente vía el skill `/discovery`.
> Los ICPs y JTBDs viajan con la feature: `/prd` los pre-rellena en "Audience" + "Success Criteria", `/plan` valida cobertura JTBD por UC, `/implement` ejecuta qualitative gate en ACs con tag `[JE-F.X]`.
