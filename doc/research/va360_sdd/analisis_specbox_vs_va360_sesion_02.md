# SpecBox Engine vs VA360 Sesión 2 — análisis comparativo

> **Estado:** research note · capturada el 2026-05-19 para abordar más adelante
> **Fuente:** [VA360_Sesion_02_Generacion_con_criterio.md](VA360_Sesion_02_Generacion_con_criterio.md) (sesión 2/5 del bloque 1, VALEN · VA360 LABS)
> **Versión SpecBox comparada:** v5.33.0 "FreeForm Path Safety"

## TL;DR

Valentín enseña SDD **manual con 4 slash commands**. SpecBox Engine es **una implementación industrial de exactamente esa idea**, con 18 meses de tooling encima: las 4 fases están, los 4 artefactos están, pero formalizadas en una jerarquía US→UC→AC, con 159 tools MCP, hooks bloqueantes que enforcan el contrato, y 5 capas extra (VEG visual, Quality Audit, Acceptance Engine, Stripe MCP, Session Continuity) que la sesión 2 no toca.

**SpecBox no contradice a Valentín — es el "siguiente paso" del que él habla en el slide 39: "empieza a mano, adopta tooling cuando duela".**

---

## Mapeo 1:1 — las 4 fases

```
VA360 Sesión 2                          SpecBox Engine v5.33
─────────────────                       ────────────────────
01 Specify  → spec.md           ←→     /prd → US-XX + UC-XXX + AC-XX (Trello/Plane/FreeForm)
                                        + Definition Quality Gate (Paso 2.5)
                                        + Evidence PDF adjunto a US card
                                        + doc/app/app_prd.md canónico (v5.29)

02 Plan     → plan.md           ←→     /plan → doc/plans/{feature}_plan.md
                                        + VEG (Visual Experience Generation)
                                        + Stitch designs via MCP (HTML)
                                        + 19 decision_keys auto/manual/queue
                                        + Evidence PDF adjunto a US card

03 Tasks    → tasks.md          ←→     UC granularity + AC checklist
                                        + find_next_uc / start_uc / complete_uc
                                        + branch por UC automática
                                        + dependencias entre UCs

04 Implement → código           ←→     /implement con 5 fases internas:
                                        Foundation → DB → Core → Polish → Acceptance
                                        + Task Isolation (v5.32, execution_context.json)
                                        + Self-healing budget (8 attempts max)
                                        + AG-08 Quality Audit + AG-09a/b Acceptance
                                        + Merge secuencial automático
```

## La "constitution" de Spec Kit en SpecBox

Valentín muestra `constitution.md` con principios como *"TDD obligatorio"*, *"prohibido `any`"*. SpecBox **lo distribuye en 4 lugares**, todos enforceados mecánicamente:

| Constitution de Valentín | Equivalente en SpecBox |
|---|---|
| `constitution.md` (texto) | `CLAUDE.md` + `rules/GLOBAL_RULES.md` (texto) |
| "TDD obligatorio" (manual) | Hook `pre-commit-lint.mjs` + GGA + `quality-baseline.json` (ratchet) |
| "No tocar fuera de la tarea" (manual) | Hook `file-ownership-guard.mjs` (PreToolUse Write/Edit) |
| `/speckit.analyze` para drift cross-artefacto | Hook `app-docs-sync-guard.mjs` + skill `/app-sync` (4 subcomandos) |
| PR rule: spec cambia con código | Hook `commit-spec-guard.mjs` + `spec-guard.mjs` (BLOCKING) |

Valentín lo deja en *"convención del equipo"*; SpecBox lo convierte en *"el agente físicamente no puede saltárselo"*.

## Los 3 tipos de drift (slide 34) — cobertura

| Drift de Valentín | Cómo lo previene SpecBox |
|---|---|
| **1. Drift de implementación** (código diverge de spec en silencio) | **Spec-Code Sync** (v5.0): después de cada fase, `/implement` genera delta estructurado y lo escribe append-only en el PRD como `## Implementation Status`. + `phase_outputs.jsonl` por feature (v5.32). |
| **2. Drift por cambio de requisitos** (cambia el código, no la spec) | Hook `spec-guard.mjs` **bloquea** Write/Edit en `src/` si no hay `active_uc.json`. Sin UC → sin código. Y `app-docs-sync-guard.mjs` detecta drift en `app_prd.md`/`app_spec.md`. |
| **3. Drift cruzado** (dos specs se contradicen) | Tool MCP `detect_app_docs_drift` (4 fuentes: stack lockfiles, brand-kit refs, roadmap-vs-tracking, canonical undocumented) + skill `/queue review` para decisiones diferidas. |

Valentín lo deja en *"hook que avisa"*. SpecBox tiene **4 hooks bloqueantes** + **telemetría JSONL** + **heartbeat al VPS**.

## Lo que SpecBox tiene de más (no aparece en la sesión 2)

```
┌─────────────────────────────────────────────────────────────┐
│  Capas adicionales que VA360 Sesión 2 no cubre              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  /visual-setup → Brand Kit + Stitch DS + VEG                │
│        ↓        + Multi-Form-Factor                         │
│                                                             │
│  VEG v3.9     → 3 pilares (imágenes + motion + diseño)      │
│        ↓        derivados de target/JTBD/ICP del PRD        │
│                                                             │
│  Stitch MCP   → 13 tools v1 + 6 tools v2 (autopilot)        │
│        ↓        DESIGN.md canónico Google + fallback chain  │
│                                                             │
│  Acceptance   → AG-09a Tester + AG-09b Validator            │
│  Engine         (Playwright/Maestro/Patrol/pytest-bdd)      │
│        ↓        HTML Evidence Reports self-contained        │
│                                                             │
│  Quality      → AG-08 interno (por fase, bloqueante)        │
│  Audit          AG-10 externo (ISO/IEC 25010 SQuaRE)        │
│        ↓        8 analyzers, PDF + JSON evidence            │
│                                                             │
│  Stripe MCP   → setup-as-code (verify_connect,              │
│        ↓        setup_webhooks, products_and_prices)        │
│                                                             │
│  Supabase MCP → set_edge_secret (cierra gap oficial)        │
│        ↓                                                    │
│                                                             │
│  Session      → /handoff + .quality/handoff.md              │
│  Continuity     + session-start.mjs                         │
│        ↓        + pre-read-budget-guard                     │
│                                                             │
│  Telemetría   → heartbeats al VPS + Sala de Máquinas        │
│                 + /remote para WhatsApp/Discord             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Nada de esto está en la sesión 2 porque Valentín está enseñando **el patrón**, no un sistema. La sesión 2 vale para alguien que arranca; SpecBox es lo que pasa cuando ese alguien lleva 18 meses iterando el patrón en producción.

## Lo que SpecBox tiene de menos (o distinto) — **gaps a abordar**

| Concepto VA360 | Estado en SpecBox | Acción pendiente |
|---|---|---|
| **`/speckit.clarify`** (resuelve ambigüedades) | Equivalente parcial: Definition Quality Gate en `/prd` Paso 2.5, pero no es un slash command standalone. | **Gap real.** Evaluar exponer un `/clarify` skill que itere sobre AC vagas. |
| **`/speckit.analyze`** (gaps cross-artefacto) | Cubierto por `detect_app_docs_drift` (interno) pero no expuesto como skill conversacional. | **Gap menor.** Considerar wrapper conversacional. |
| **Constitution como archivo único** | Disperso entre `CLAUDE.md`, `GLOBAL_RULES.md`, `app_spec.md`, `settings.local.json`. | **Trade-off conocido.** Un solo archivo sería más legible pero rompe separación de scopes. Documentar la decisión. |
| **Empieza a mano** | SpecBox arranca con `./install.sh` + 14 skills + 20 hooks + MCP. | **Curva de entrada alta.** ¿Modo "lean" para onboarding? Valentín gana en pedagogía inicial. |

## La frase clave de Valentín mapeada a SpecBox

> "The spec is the prompt." (slide 11)

En SpecBox esto se materializa en **3 niveles concretos**:

1. **PRD** (lo que ve el agente al planear): `doc/prds/{feature}_prd.md` con AC-XX numerados
2. **Plan técnico** (lo que ve el agente al implementar): `doc/plans/{feature}_plan.md`
3. **Acceptance evidence** (lo que valida que se cumplió): `e2e-evidence-report.html` + `results.json`

> "Si el código no se desprende lógicamente de algo escrito en la spec, no es código: es deuda técnica con disfraz." (slide 35)

→ En SpecBox esto es **un hook que bloquea físicamente**:
- `spec-guard.mjs` (no UC activo → no Write)
- `branch-guard.mjs` (main → no Write)
- `pipeline-phase-guard.mjs` (fase out-of-order → no Write)

## Tabla resumen

|  | VA360 Sesión 2 | SpecBox Engine v5.33 |
|---|---|---|
| **Audiencia** | Equipos arrancando | Equipos en producción |
| **Setup** | 0 dependencias | `./install.sh` + MCP + VPS |
| **Slash commands** | 4 (manuales) | 14 skills + 159 tools MCP |
| **Enforcement** | Convención | 20 hooks bloqueantes |
| **Granularidad** | spec→plan→tasks | US→UC→AC + 5 sub-fases |
| **Drift** | 3 mitigaciones manuales | 4 hooks + telemetría |
| **Visual** | No cubierto | VEG + Stitch + Brand Kit |
| **Acceptance** | TDD opcional | AG-09a/b + 6 frameworks |
| **Curva** | Baja | Alta |

## Conclusión

Valentín y SpecBox dicen lo mismo. Valentín lo dice para que lo entiendas; SpecBox lo dice para que sea imposible saltárselo. La pregunta no es *"cuál es mejor"* — es *"en qué punto de madurez está el equipo"*. La sesión 2 es el manifesto; SpecBox es la fábrica.

## Próximos pasos sugeridos (para retomar)

1. **Evaluar `/clarify` standalone** — ¿lo extraemos del Definition Quality Gate de `/prd` como skill independiente?
2. **Wrapper conversacional para `detect_app_docs_drift`** — exponerlo como `/analyze` para paridad pedagógica con Spec Kit.
3. **Documentar la "constitution distribuida"** — explicar por qué SpecBox la divide en 4 archivos en vez de uno (trade-off de scopes).
4. **Modo lean de onboarding** — perfil mínimo que arranca con solo PRD/Plan/Tasks sin VEG/Stitch/Acceptance para bajar la curva inicial.
5. **Revisar sesiones 3-5 de VA360** cuando estén disponibles para extender este análisis al ciclo completo (Review/Refactor, Tooling avanzado, etc.).
