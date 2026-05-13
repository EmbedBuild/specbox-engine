<p align="center">
  <img src=".github/assets/Logo SpecBox.png" alt="SpecBox Engine" width="280" />
</p>

<h1 align="center">SpecBox Engine</h1>

<p align="center">
  <strong>Programación agéntica con Claude Code, sin ceder calidad por velocidad.</strong><br/>
  v5.33.0 — "FreeForm Path Safety" (sobre v5.32.1 "Release Skill — README + CHANGELOG enforcement")<br/>
  <a href="#english-version">English version below</a>
</p>

---

## ¿Qué es esto?

Un sistema que convierte a Claude Code en un compañero de equipo serio:

- **Te ayuda a ir rápido** sin saltarse trazabilidad ni calidad.
- **Aprende de tu proyecto** y deja de preguntarte lo que ya has decidido.
- **Bloquea atajos peligrosos** (push a main, AC vagos, code sin UC, paths inseguros).
- **Convive con tu flujo**: spec-driven con FreeForm/Trello/Plane según el cliente.

> SpecBox provides speed. The LLM provides quality.

---

## Lo nuevo en v5.33

**v5.33.0 — "FreeForm Path Safety"** convierte el BLOCKER de v5.29 (FreeForm + MCP remoto escribiendo en el VPS) en un bug mecánicamente imposible. v5.29 ya lo resolvía a nivel `/app-init` y server-side; v5.33 añade dos capas más para cubrir clientes que no pasan por la skill:

- **Hook universal `freeform-path-guard.mjs`** — PreToolUse intercepta `set_auth_token` y `onboard_project`. Si el path es relativo (o `doc/tracking` queda implícito), lo reescribe al absoluto del repo via `git rev-parse --show-toplevel` antes de que la llamada salga al MCP. Auto-rewrite silencioso vía `hookSpecificOutput.updatedInput`. Audit trail en `.quality/logs/freeform-path-rewrites.jsonl`.
- **Tool MCP `detect_local_root_path()`** — read-only handshake que declara el contrato (requires_absolute_path, client_resolution_recipe). Sirve a `/app-init`, claude.ai mobile e integraciones externas como documentación ejecutable.
- **`/app-init` Paso 2.3 reforzado** — 3-step handshake: handshake con la tool del contrato, resolución explícita desde PROJECT_ROOT, pasa absoluto a `set_auth_token`. El hook queda como red de seguridad para clientes que no usan la skill.

3 capas aditivas e independientes. Remover cualquiera no desbloquea el bug mientras las otras estén en pie. 100% backwards-compatible — clientes pre-v5.33 sin el hook siguen hitting el server-side guard de v5.29.

---

## Lo nuevo en v5.32

**v5.32.0 — "Implement Task Isolation"** cierra el out-of-scope explícito de v5.30: el SKILL.md de `/implement` ya documentaba la delegación a Tasks aisladas, pero el contrato no estaba mecánicamente forzado. v5.32 añade los 5 guardrails que faltaban — sin rediseñar la arquitectura — y los cablea de forma observable:

- **`execution_context.json`** persistido por feature (branch / stack / paths). Cada Task lo lee del disco en lugar de recibir esos valores en el prompt → fixea la causa raíz del context exhaustion en UCs grandes.
- **`context-budget-guard.mjs`** PreToolUse(Task) — estima tokens, warn @ 16k (default), strict como settings flip.
- **`file-ownership-guard.mjs`** PreToolUse(Write/Edit) — valida la ruta contra el ownership del agente activo. Suspicious paths (`..`, `/abs`) siempre BLOCKED.
- **`phase_outputs.jsonl`** — cada Task escribe su delta estructurado al cierre. Spec-Code Sync deja de depender de `git diff` vivo desde el orquestador.
- **Heartbeat enriquecido** con `task_isolation: {enabled, tasks_run_total, tasks_failed_*}` para Sala de Máquinas.

100% backwards-compatible. Modos `warn` por defecto durante la migración.

**v5.32.1** convierte la regla "README + CHANGELOG en cada bump" en un guardrail mecánico: el skill `/release` ahora bumpea ambos archivos como pasos obligatorios y un nuevo validador `version-consistency-check.mjs` aborta la release si cualquiera de los 5 archivos de versión queda desincronizado.

---

## Lo nuevo en v5.31

**v5.31.0 — "Stitch Autopilot"** alinea la integración de Google Stitch con sus best practices oficiales y elimina los bloqueadores recurrentes de autopilot al generar diseños:

- **DESIGN.md canónico** ([formato oficial Google](https://github.com/google-labs-code/design.md)) generado automáticamente desde Brand Kit + VEG. Resuelve el drift visual entre pantallas en raíz.
- **Pipeline v2 con fallback chain** (`edit_baseline → variants_refine → regenerate`) — los timeouts y errores transitorios ya no rompen autopilot.
- **Validator de prompts en 4 capas** (Context / Components / Style con hex codes / Platform) — primera generación más cerca de la marca, menos iteración.
- **Batched build_site** para planes con >5 pantallas + pasada final de tema unificado.
- **Quota tracking** (350 Standard + 200 Experimental) con warnings ≥80% y hook bloqueante a 100% (Flash safety net opt-in).

**Modelo default sigue siendo `GEMINI_3_PRO`**. Calidad-first. Flash queda solo como red de seguridad opt-in.

**v5.31.1** activa todo lo anterior en `/plan` Paso 6 (antes seguía usando v1 directo). Migración transparente — sin cambios de settings necesarios.

---

## ¿Por qué v5.29.0?

**Problema**: a medida que llevas más proyectos en paralelo, SpecBox te interrumpe demasiado. Cada decisión, cada confirmación, cada pregunta — multiplicado por proyectos abiertos = carga cognitiva imposible.

**v5.29.0** introduce un sistema de **decisiones con autonomía auditable**: el engine se queda decidiendo lo cosmético y lo repetitivo por ti, mientras te garantiza que nunca toca lo crítico (acciones destructivas, push a main, gastos sobre presupuesto).

**Resultado medido**: las interrupciones por feature pasan de ≥17 (baseline v5.28) a ≤8 con el preset por defecto `equilibrado`.

---

## Lo nuevo en una imagen

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tu proyecto en v5.29                         │
│                                                                 │
│   doc/app/app_prd.md      ← Producto: visión, audiencia, scope │
│   doc/app/app_spec.md     ← Técnico: stack, brand, autopilot   │
│              │                                                  │
│              ▼  /prd, /plan, /visual-setup leen esto antes      │
│              │  de preguntar nada                               │
│                                                                 │
│   Autopilot: [equilibrado]  ─── reduce preguntas a la mitad    │
│   Hooks: pre-commit + drift detection                           │
│   Sync: doc/app/ siempre alineado con la realidad              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
# Instalar el engine globalmente
git clone <repo-url> ~/specbox-engine
cd ~/specbox-engine
./install.sh

# En tu proyecto
cd /ruta/a/mi-proyecto
/app-init                 # crea doc/app/ + configura autopilot=equilibrado
/prd "tu primera feature" # hereda audiencia y stack desde app_prd.md
/plan US-01
/implement
```

Eso es todo. Las skills se auto-descubren cuando son relevantes; los hooks corren solos.

---

## ¿Cómo funciona?

### 1. Documentos canónicos del proyecto

Cuando ejecutas `/app-init`, SpecBox crea dos documentos vivos:

- **`doc/app/app_prd.md`** — Producto: visión, audiencia, JTBDs, perímetro, métricas, roadmap.
- **`doc/app/app_spec.md`** — Técnico: stack, backend, brand, convenciones, autopilot.

Cada documento tiene **zonas tipadas** que el engine respeta:

- 🔒 **`manual`** — solo tú las editas. El engine las lee como input.
- 🤖 **`auto`** — solo el engine las reescribe (tras eventos como `complete_uc`).
- 🤝 **`hybrid`** — append-only, ambos contribuyen con marcadores explícitos.

A partir de aquí, `/prd`, `/plan` y `/visual-setup` consultan estos documentos en su Paso 0 y **dejan de repreguntarte** la audiencia, el stack, el modo VEG, el backend de tracking, etc.

### 2. Autopilot

Cada gate del engine se etiqueta con un `decision_key`. El nivel de autopilot decide qué se auto-confirma y qué se pregunta:

| Nivel | A quién pregunta | Cuándo usarlo |
|-------|------------------|---------------|
| `low` | Todo (= v5.28) | Proyecto con muchas decisiones críticas todavía abiertas |
| `conservador` | Todo menos cosmético | Quieres control visual fino |
| **`equilibrado`** ← default | Solo arquitectura, presupuesto, ambigüedad real | Caso por defecto |
| `agresivo` | Solo destructivo y AC objetivamente malos | Tras 1-2 semanas validando equilibrado |

**Reglas inviolables** que ningún nivel ni override puede saltar:

- ❌ Acciones destructivas (`reset --hard`, force-push, etc.).
- ❌ Push directo a main.
- ❌ Coste de imágenes por encima del presupuesto declarado.

Toda auto-decisión se registra en `.quality/autopilot_decisions.jsonl` (auditable, revertible).

### 3. Sync enforcement (Capa 5)

Sin enforcement, los documentos canónicos se convierten en mentira documentada en 2-3 sprints. Por eso v5.29 incluye:

- **Hook pre-commit** que detecta drift entre `app_*.md` y la realidad del proyecto.
- **Skill `/app-sync`** para reconciliar (4 modos: check / repair / review / rebuild).
- **Drift detector multi-fuente** que pilla cosas que el hook por sí solo no ve (lockfiles nuevos, brand kit roto, roadmap mintiendo, canonicals sin documentar).

En v5.29.0 está en **modo warning**: avisa pero no bloquea. Cuando hayas validado que los warnings son siempre accionables (1-2 semanas típicamente), pones `specbox.app_docs_sync.block_on_drift=true` y se vuelve bloqueante.

---

## Pipeline de desarrollo

```
/app-init       (una vez por proyecto)
    ↓
/prd            ← captura feature, hereda audiencia desde app_prd.md
    ↓
/visual-setup   ← brand kit + VEG + Stitch DS, hereda arquetipo
    ↓
/plan US-XX     ← plan técnico por UC + diseños Stitch
    ↓
/implement      ← fases + AG-08 calidad + AG-09 acceptance + PR auto
    ↓
/feedback       ← testing manual del usuario, puede invalidar verdict
    ↓
merge secuencial → siguiente UC
```

Cada paso del pipeline tiene su skill, su hook bloqueante, y su evidencia auditable.

---

## Skills disponibles

23 skills auto-descubribles. Las que más vas a usar:

| Skill | Para qué |
|-------|----------|
| `/app-init` ← v5.29 | Crea/refresca documentos canónicos del proyecto |
| `/app-sync` ← v5.29 | Reconcilia drift entre canónicos y realidad |
| `/queue review` ← v5.29 | Resuelve decisiones diferidas en batch |
| `/prd` | Genera PRD spec-driven con quality gate |
| `/visual-setup` | Brand kit + Stitch + VEG |
| `/plan` | Plan técnico por UC con designs |
| `/implement` | Auto-implementación con acceptance gates |
| `/feedback` | Captura bugs como evidencia + GitHub issue |
| `/release` | Audita, bumpa version, push |

Skills de billing (Stripe): `/stripe-connect`, `/stripe-standard`, `/stripe-switch-account`.

Skills de auditoría: `/audit` (ISO 25010), `/compliance`, `/quality-gate`, `/check-designs`, `/manual-test`.

Skills de exploración: `/explore`, `/adapt-ui`, `/optimize-agents`, `/quickstart`, `/remote`.

---

## Backends de tracking

| Backend | Cuándo |
|---------|--------|
| **`freeform`** ← default v5.29 | Proyectos personales, prototipos, sin reporting externo. Datos en `doc/tracking/` (JSON + Markdown auto-generado). |
| `trello` | Cliente externo necesita ver progreso. |
| `plane` | Equipo distribuido, multi-equipo. Self-hosted o cloud. |

Auto-discovery: SpecBox detecta tu backend leyendo settings, filesystem, o app_spec.md sin preguntarte.

Migración bidireccional: Trello ↔ Plane (`migrate_project`), Trello/Plane → FreeForm (`migrate_to_freeform_tool`).

---

## Hooks que importan

23 hooks `.mjs` ejecutados automáticamente por Claude Code. Los **bloqueantes** son los que evitan que metas la pata:

- `quality-first-guard` — no escribir sin haber leído el archivo primero.
- `spec-guard` — no escribir código sin UC activo.
- `branch-guard` — no escribir en main.
- `commit-spec-guard` — no commitear en main, avisos sobre UC y checkpoint.
- `e2e-gate` — no commitear evidencia E2E sin `results.json` válido.
- `no-bypass-guard` — bloquea `--no-verify`, `push --force`, `reset --hard`.
- `design-gate` — no UI sin diseño Stitch primero.
- `pipeline-phase-guard` — no feature code antes de DB phase.
- `healing-budget-guard` — corta self-healing tras 8 intentos.
- `stripe-safety-guard` — bloquea anti-patterns Stripe (sk_live, webhook sin firma, etc.).
- `app-docs-sync-guard` ← v5.29 — detecta drift en docs canónicos (warning por defecto).

---

## Stacks soportados

| Stack | Versión | E2E |
|-------|---------|-----|
| Flutter | 3.38+ | Maestro (recomendado) o Patrol v4 (legacy) |
| React | 19.x | Playwright |
| Go | 1.23+ | testing + httptest + testcontainers-go |
| Python (FastAPI) | 3.12+ | pytest-bdd + httpx |
| Google Apps Script | V8 | jest-cucumber |

Servicios de infraestructura: Supabase, Neon, Stripe, Firebase, n8n, Stitch MCP.

MCPs propios en [`packages/`](packages/): `specbox-stripe-mcp` (setup-as-code Stripe), `specbox-supabase-mcp` (Edge Function secrets).

---

## Migración desde v5.28

Tooling automático que clasifica tu proyecto en uno de 10 estados conocidos:

```python
detect_v529_migration_case(project_path=".")  # te dice qué caso aplica
run_v529_migration(project_path=".", apply=False)  # dry-run / apply seguro
```

Casos sensibles que se difieren para revisión manual: feature en curso (caso 7), datos posiblemente en VPS (caso 3), `app_*.md` creados a mano (caso 9).

100% backwards-compatible. Sin `doc/app/`, sin sección `autopilot`, sin nada — el proyecto se comporta como v5.28.

---

## ¿Quieres saber más?

- 📖 **Plan completo de v5.29.0**: [doc/plans/v5.29.0_cognitive_load_reduction_plan.md](doc/plans/v5.29.0_cognitive_load_reduction_plan.md)
- 📋 **PRD del problema**: [doc/prds/cognitive_load_reduction_prd.md](doc/prds/cognitive_load_reduction_prd.md)
- 📜 **Histórico**: [CHANGELOG.md](CHANGELOG.md)
- 🛠️ **Reference técnico exhaustivo**: [CLAUDE.md](CLAUDE.md)

---

## Releases recientes

- **v5.29.0** ← actual — Cognitive Load Reduction.
- **v5.28.0** — Maestro Flutter E2E como runner recomendado para mobile.
- **v5.27.0** — `/stripe-standard` + `/stripe-switch-account`.
- **v5.26.0** — Paquete `specbox-supabase-mcp` para Edge Function secrets.
- **v5.25.0** — `/stripe-connect` para marketplaces.

---

## Configuración mínima

`.claude/settings.local.json`:

```json
{
  "specbox": {
    "backend_type": "freeform",
    "freeform_root_absolute": "/ruta/absoluta/al/proyecto/doc/tracking",
    "autopilot": {
      "level": "equilibrado",
      "image_budget_eur_per_feature": 5
    },
    "app_docs_sync": {
      "block_on_drift": false
    }
  }
}
```

---

## Licencia

[Indicar licencia del proyecto]

---

<a id="english-version"></a>

# SpecBox Engine — English version

> **Agentic programming with Claude Code, without trading quality for speed.**
> v5.33.0 — "FreeForm Path Safety" (over v5.32.1 "Release Skill — README + CHANGELOG enforcement")

## What is this?

A system that turns Claude Code into a serious teammate:

- **Helps you go fast** without skipping traceability or quality.
- **Learns your project** and stops asking you what you already decided.
- **Blocks dangerous shortcuts** (push to main, vague AC, code without UC, unsafe paths).
- **Coexists with your flow**: spec-driven with FreeForm/Trello/Plane depending on the client.

> SpecBox provides speed. The LLM provides quality.

## What's new in v5.33

**v5.33.0 — "FreeForm Path Safety"** turns the v5.29 BLOCKER (FreeForm + remote MCP writing the tracking folder on the VPS) into a mechanically impossible bug. v5.29 fixed it at the `/app-init` and server-side levels; v5.33 adds two more layers covering clients that don't go through the skill:

- **Universal hook `freeform-path-guard.mjs`** — PreToolUse intercepts `set_auth_token` and `onboard_project`. If the path is relative (or `doc/tracking` is the implicit default), it auto-rewrites to the absolute repo path via `git rev-parse --show-toplevel` before the call reaches the MCP. Silent auto-rewrite via `hookSpecificOutput.updatedInput`. Audit trail at `.quality/logs/freeform-path-rewrites.jsonl`.
- **MCP tool `detect_local_root_path()`** — read-only handshake declaring the contract (requires_absolute_path, client_resolution_recipe). Serves `/app-init`, claude.ai mobile, and external integrations as executable documentation.
- **`/app-init` Paso 2.3 reinforced** — 3-step handshake: call the contract tool, resolve from PROJECT_ROOT explicitly, pass absolute to `set_auth_token`. The hook remains as safety net for clients that don't use the skill.

3 additive, independent layers. Removing any one does not unblock the bug while the others stand. 100% backwards-compatible — pre-v5.33 clients without the hook still hit the v5.29 server-side guard.

---

## What's new in v5.32

**v5.32.0 — "Implement Task Isolation"** closes the explicit out-of-scope from v5.30: the `/implement` SKILL.md already documented Task delegation, but the contract wasn't mechanically enforced. v5.32 adds the 5 missing guardrails — without redesigning the architecture — and wires them observably:

- **`execution_context.json`** persisted per-feature (branch / stack / paths). Each Task reads it from disk instead of receiving those values in the prompt → fixes the root cause of context exhaustion on large UCs.
- **`context-budget-guard.mjs`** PreToolUse(Task) — estimates tokens, warns @ 16k (default), strict as a settings flip.
- **`file-ownership-guard.mjs`** PreToolUse(Write/Edit) — validates the path against the active agent's ownership. Suspicious paths (`..`, `/abs`) always BLOCKED.
- **`phase_outputs.jsonl`** — every Task writes a structured delta at close. Spec-Code Sync no longer depends on live `git diff` from the orchestrator.
- **Enriched heartbeat** with `task_isolation: {enabled, tasks_run_total, tasks_failed_*}` for Sala de Máquinas.

100% backwards-compatible. `warn` modes default during the migration.

**v5.32.1** turns the "bump README + CHANGELOG on every release" rule into a mechanical guardrail: the `/release` skill now bumps both files as mandatory steps and a new `version-consistency-check.mjs` validator aborts the release if any of the 5 version files drifts out of sync.

---

## What's new in v5.31

**v5.31.0 — "Stitch Autopilot"** aligns the Google Stitch integration with its official best practices and removes the recurring autopilot blockers when generating designs:

- **Canonical DESIGN.md** ([Google's official format](https://github.com/google-labs-code/design.md)) auto-generated from Brand Kit + VEG. Solves cross-screen visual drift at the root.
- **v2 pipeline with fallback chain** (`edit_baseline → variants_refine → regenerate`) — timeouts and transient errors no longer break autopilot.
- **4-layer prompt validator** (Context / Components / Style with hex codes / Platform) — first generations closer to the brand, less iteration.
- **Batched build_site** for plans with >5 screens + final unified-theme pass.
- **Quota tracking** (350 Standard + 200 Experimental) with warnings ≥80% and a blocking hook at 100% (Flash safety net opt-in).

**Default model stays `GEMINI_3_PRO`**. Quality-first. Flash is only an opt-in safety net.

**v5.31.1** activates the above inside `/plan` Paso 6 (which until v5.31.0 still used the legacy v1 tool directly). Transparent migration — no settings change required.

## Why v5.29.0?

**Problem**: as you take on more parallel projects, SpecBox interrupts you too much. Every decision, every confirmation — multiplied by open projects = unmanageable cognitive load.

**v5.29.0** introduces a system of **decisions with auditable autonomy**: the engine handles cosmetic and repetitive choices, while guaranteeing it never touches the critical ones (destructive actions, push to main, costs over budget).

**Measured result**: friction points per feature drop from ≥17 (v5.28 baseline) to ≤8 with the default `equilibrado` preset.

## Quick Start

```bash
git clone <repo-url> ~/specbox-engine
cd ~/specbox-engine
./install.sh

cd /path/to/your-project
/app-init                 # creates doc/app/ + configures autopilot=equilibrado
/prd "your first feature" # inherits audience and stack from app_prd.md
/plan US-01
/implement
```

That's it. Skills auto-discover when relevant; hooks run automatically.

## How it works

**1. Canonical project documents**: `/app-init` creates `doc/app/app_prd.md` (product: vision, audience, scope, metrics, roadmap) and `doc/app/app_spec.md` (technical: stack, backend, brand, conventions, autopilot). Each has typed zones — `manual` (only you edit), `auto` (only the engine rewrites), `hybrid` (append-only, both contribute). From here, `/prd`, `/plan` and `/visual-setup` consult these documents and **stop re-asking** for project-level decisions.

**2. Autopilot**: 4 tiers (low / conservador / **equilibrado** / agresivo) decide per-decision whether to auto-confirm, ask, or block. Inviolable rules: no auto-confirm of destructive actions, push to main, or costs over budget. Every auto-decision is logged to `.quality/autopilot_decisions.jsonl`.

**3. Sync enforcement**: pre-commit hook detects drift between `app_*.md` and reality. `/app-sync` reconciles. Multi-source drift detector catches what the hook alone misses (new lockfiles, broken brand kit refs, lying roadmaps, undocumented canonical decisions). Warning-only by default; flip `block_on_drift=true` when validated.

## Skills

23 auto-discoverable skills. v5.29 highlights:

- `/app-init` — Creates/refreshes canonical docs.
- `/app-sync` — Verify, repair, review, or rebuild canonical docs.
- `/queue review` — Resolve deferred decisions in batch.

Plus existing pipeline skills: `/prd`, `/plan`, `/visual-setup`, `/implement`, `/feedback`, `/release`, `/audit`, `/compliance`, `/quality-gate`, plus billing (`/stripe-*`), exploration (`/explore`, `/adapt-ui`, `/quickstart`), and operations (`/manual-test`, `/check-designs`, `/optimize-agents`, `/remote`, `/acceptance-check`).

## Backends

`freeform` is the v5.29 default for personal projects. `trello` and `plane` remain first-class for projects with external client reporting. 5-level auto-discovery picks the right one without asking.

Migration: Trello ↔ Plane (existing), Trello/Plane → FreeForm (new in v5.29).

## Stacks

Flutter 3.38+ (Maestro recommended), React 19.x (Playwright), Go 1.23+ (testing + httptest), Python 3.12+ FastAPI (pytest-bdd), Google Apps Script V8. Services: Supabase, Neon, Stripe, Firebase, n8n, Stitch MCP. Independent MCP packages in `packages/`.

## Migrating from v5.28

`detect_v529_migration_case` classifies your project into one of 10 known states. Sensitive cases (active feature, possible VPS data, manually-created app docs) are deferred for user review. 100% backwards-compatible: without `doc/app/` or `autopilot` config, behavior is identical to v5.28.

## Recent releases

- **v5.29.0** ← current — Cognitive Load Reduction.
- **v5.28.0** — Maestro Flutter E2E.
- **v5.27.0** — Stripe Standard + Switch Account.
- **v5.26.0** — Supabase Edge Secrets MCP.
- **v5.25.0** — Stripe Connect.

Full history in [CHANGELOG.md](CHANGELOG.md). Exhaustive technical reference in [CLAUDE.md](CLAUDE.md).

## Philosophy

> SpecBox provides speed. The LLM provides quality.

The engine doesn't take shortcuts for you — it **prevents them**. Every blocking hook exists because the alternative (LLM bypassing under pressure) is systematically worse than the friction.

## License

[Project license]
