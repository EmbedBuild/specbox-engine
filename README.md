<p align="center">
  <img src=".github/assets/Logo SpecBox.png" alt="SpecBox Engine" width="280" />
</p>

<h1 align="center">SpecBox Engine</h1>

<p align="center">
  <strong>Programación agéntica con Claude Code, sin ceder calidad por velocidad.</strong><br/>
  v5.29.0 — "Cognitive Load Reduction"<br/>
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
> v5.29.0 — "Cognitive Load Reduction"

## What is this?

A system that turns Claude Code into a serious teammate:

- **Helps you go fast** without skipping traceability or quality.
- **Learns your project** and stops asking you what you already decided.
- **Blocks dangerous shortcuts** (push to main, vague AC, code without UC, unsafe paths).
- **Coexists with your flow**: spec-driven with FreeForm/Trello/Plane depending on the client.

> SpecBox provides speed. The LLM provides quality.

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
