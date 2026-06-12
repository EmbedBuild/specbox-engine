<p align="center">
  <img src=".github/assets/Logo SpecBox.png" alt="SpecBox Engine" width="280" />
</p>

<h1 align="center">SpecBox Engine</h1>

<p align="center">
  <strong>Programación agéntica con Claude Code, sin ceder calidad por velocidad.</strong><br/>
  v 6.10.2 — "Mirror Bootstrap" (sobre v6.10.1 "Reentrant Reserve")<br/>
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

## Lo nuevo en v6.10

**v6.10.0 — "UC Lifecycle Metrics"** dos capacidades nuevas: métricas honestas de lead time por UC computadas en la BD, y espejo dual-backend hacia Native:

- **Captura de lifecycle por triggers** — toda transición de `use_cases.state` (sea cual sea el escritor) queda registrada transaccionalmente en `uc_state_transitions`, con `started_at`/`completed_at` mantenidos en la fila. El inicio que antes no se registraba y el fin best-effort que podía perderse quedan blindados.
- **KPIs en la BD, engine fino** — `v_lifecycle_kpis` (lead time p50/p90 solo sobre UCs medibles, `coverage_pct` como KPI de honestidad, imports excluidos por construcción y visibles), `v_active_time_estimate` (tiempo activo estimado por clustering de sesiones), rol read-only para el panel y tool `get_project_kpis`.
- **Backfill histórico preparado, no ejecutado** — `fn_backfill_lifecycle` (dry-run default) con rollback exacto; se activará por proyecto tras calibrar estimadores con datos reales.
- **Dual-backend espejo Native (US-11)** — un primario Trello/Plane/FreeForm intocable puede reportar a la vez a un espejo Native best-effort que jamás degrada al primario (`enable_mirror`/`disable_mirror` con backfill idempotente).

100% backwards-compatible. Las migraciones de producción (`20260611000012..16`) se aplican vía Supabase ledger en el despliegue.

**v6.10.1 — "Reentrant Reserve"** hotfix: `reserve_uc` reentrante dentro de una transacción usa `INSERT ... ON CONFLICT DO NOTHING` en vez de capturar `UniqueViolationError`, arreglando el `current transaction is aborted` de `start_uc` tras `reserve_uc` del mismo developer (UC-1208, PR #118).

**v6.10.2 — "Mirror Bootstrap"** hotfix: `enable_mirror` auto-inicializa `projects.json` y auto-siembra la entrada del proyecto desde el primario cuando el registry nunca se materializó en el host MCP cloud — cierra el `CONFIG_FAILED`/`failing_place=registry` al activar el espejo Native sobre el cliente potencial_digital_2026; el primario en disco nunca se sobrescribe y la rollback transaccional borra el `projects.json` recién creado (US-11/UC-1104, PR #123).

---

## Lo nuevo en v6.9

**v6.9.0 — "Self-Provisioning"** la extensión de VS Code se aprovisiona el engine ella misma, sin clone manual:

- **Auto-clone del engine público** — cuando la extensión no encuentra el engine en disco, clona `github.com/EmbedBuild/specbox-engine` a una carpeta gestionada (`~/.specbox/specbox-engine`) automáticamente (notifica, no pregunta), antes de recurrir a pedirte la carpeta a mano.
- **Auto-pull del clon gestionado** — el update flow mantiene ese clon al día con `git pull --ff-only`. Un clon propio tuyo en otra ruta **nunca** se toca.
- **Onboarding sin "clona primero"** — el walkthrough y el README ya no te piden `git clone` como paso previo de la extensión.

100% backwards-compatible. El auto-clone es el último recurso: config/workspace/rutas comunes ganan, y un clone fallido degrada al diálogo de selección manual.

**v6.9.1 — "Atomic Switch"** cambiar de backend (incl. hacia/desde Cloud/Native) pasa a ser **una sola operación atómica todo-o-nada**: el nuevo `switch_project_backend` migra datos + asocia identidad + conmuta la config + reporta lo descartado en una llamada con rollback total. Cierra además el path-bug de MCP remoto: el source se lee del cliente (content-passing), nunca del filesystem del servidor.

**v6.9.2 — "Batch Ingest"** subir un proyecto freeform real (133 KB / cientos de ítems) a Cloud/Native ya funciona end-to-end: la migración cruza por **lotes verificables** (`start → append × N → commit`, SHA-256 por chunk) que el servidor reensambla y escribe en **una transacción atómica** (rollback total ante fallo). Cierra el gap de transporte de v6.9.1 — el `items.json` ya no tiene que caber en un único parámetro de tool.

**v6.9.3 — "Tenant Provisioning"** subir un proyecto a Cloud/Native **de cero** ya funciona: la migración **auto-aprovisiona** el tenant + tu membresía como `project_admin` server-side antes del gate (rompe el huevo-gallina "no eres miembro de un proyecto que aún no existe"), y engine y panel acuerdan un único formato de `project_id` (`owner/repo` canónico + slug derivado para URLs). Cierra los 2 gaps de v6.9.2.

**v6.9.4 — "Orphan Tenant Recovery"** cierra el bug que aún rompía la migración de cero real: `setup_board` creaba la fila del proyecto **sin membresía** (tenant huérfano), y eso **desactivaba** la auto-provisión de v6.9.3 → `FORBIDDEN` sobre una BD vacía. Doble defensa: `setup_board` native ahora aprovisiona tenant + membresía de forma atómica (nunca deja 0 miembros), y la auto-provisión **adopta** un tenant huérfano (0 miembros) mientras sigue protegiendo los tenants con dueño (AC-13). El E2E ahora parte del **estado sucio real** (huérfano primero), no de una BD virgen. 100% backwards-compatible.

**v6.9.5 — "Tenant-Scoped Keys"** cierra el último bloqueante de la migración a Cloud/Native: el ingest colisionaba en `user_stories_pkey` porque la PK era el id lógico (`US-01`) **sin** namespacing por proyecto — dos proyectos no podían compartir un `US-01` en el mismo Postgres. La PK de US/UC/AC pasa a **compuesta `(project_id, id)`** (migración 0009, idempotente). Además, `/switch-backend` ahora entiende el **dialecto FreeForm "exploded"** (`index.json` anidado + AC en checkboxes `.md`) vía un normalizador puro a `items.json` + un **pre-flight de formato** y un **gate de prerequisitos native** que sacan los fallos al paso 0 en vez de a mitad de la migración. Tests stale realineados a los contratos UC-660/UC-706. 100% backwards-compatible.

---

## Lo nuevo en v6.8

**v6.8.0 — "Connectivity UX"** hace que SpecBox funcione de verdad con el MCP server en remoto: el server nunca toca un filesystem ajeno y el estado del cliente fluye por content-passing:

- **FreeForm operativo end-to-end** — las 7 tools de mutación + un bridge Node (`readTrackingBundle`/`writeTrackingBundle`) leen/escriben `doc/tracking` del cliente vía content-passing. Cierra la regresión #82.
- **`/audit` operativo en remoto** — los 8 analyzers ISO/IEC 25010 portados a Node client-side escanean el FS del cliente, no el del VPS.
- **Updater pedagógico de la extensión** — detecta config obsoleta tras un update, migra el transporte sola (con backup + revert) y explica qué cambió.
- **Drift gate consciente de las decisiones canónicas** — valida contra `app_spec.md`, la causa-raíz que dejó pasar #82.

100% backwards-compatible. Cierra una clase de fallo silencioso en MCP remoto.

---

## Lo nuevo en v6.7

**v6.7.0 — "Zero-Friction Onboarding"** quita toda la fricción de instalar la extensión VSCode y hace que avise con claridad cuando le falta algo:

- **Onboarding cero-Python** — el MCP server se consume solo por el endpoint hospedado gratuito (se eliminó el modo Local que pedía Python). Engram se instala como binario nativo vía Homebrew, no por pip. Health check, walkthrough y README ya no mencionan Python.
- **Gate de prerequisitos** — al arrancar, si falta un requisito crítico (Claude Code, Engram, Node o los servidores MCP) la extensión avisa de forma clara y no bloqueante que SpecBox puede no funcionar correctamente, con acciones de un clic. Silencio cuando todo está listo.
- **Comando "SpecBox: Check Prerequisites"** — re-evalúa el entorno a demanda desde la paleta.

100% backwards-compatible. Decisión: sin fallback air-gapped (el MCP remoto es gratuito); el aviso avisa, no impide.

---

## Lo nuevo en v6.0

**v6.0.2 — "Smoke Test Followups"** cierra los 3 issues abiertos descubiertos en el smoke test de v6.0.1 (#60, #61, #62) y elimina el último hardcodeo de versión runtime que arrastraba el server desde v5.29:

- **`submit_quality_audit` autogenera `audit_id`** si el cliente no lo pasa (cliente puede seguir pasando el suyo si necesita idempotencia).
- **`run_quality_audit` deprecation hace `raise`** → MCP envelope con `isError=true`. Clientes que solo inspeccionan el envelope detectan la deprecación correctamente.
- **`validate_discovery_completeness`** acepta las 4 resoluciones canónicas de drift (`feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`) y expone nuevo campo `drift.kind` para futuros gates estrictos.
- **`server/server.py`** ya no hardcodea la versión — la lee de `ENGINE_VERSION.yaml` al cargar el módulo. Bug latente `submit_quality_audit.fn(...)` eliminado de paso. `fastmcp 3.1.0 → 3.3.1` con pin `>=3.3.1,<4.0.0`.

100% backwards-compatible. Suite `1243 passed / 71 skipped / 0 failed`.

---

**v6.0.1 — "MCP Path Contract"** hotfix arquitectural que migra 17 tools cat A en `server/tools/` a un patrón de **content-passing universal**: ninguna tool registrada con `@mcp.tool` resuelve `Path(project_path).resolve()` para acceder al filesystem del cliente. El cliente lee los archivos localmente con `Read`, pasa el contenido como string, y escribe lo que la tool devuelva. Resuelve el bug crítico de MCP remoto donde las tools devolvían datos del filesystem del VPS, no del cliente. Skills actualizadas (`/discovery`, `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check`) + nuevo helper cliente `.claude/hooks/lib/mcp-client-io.mjs`.

---

**v6.0.0 — "Discovery Foundations"** introduce un módulo de **Product Discovery** permanente integrado en el pipeline canónico (`/discovery → /prd → /plan → /implement`) + el tercer documento canónico `doc/app/app_market.md` (ICPs primarios + no-ICPs + JTBDs globales + NSM + posicionamiento) + la **fundación arquitectural multi-doc** (`server/app_docs/registry.py`) que sostiene la extensión a N documentos canónicos en v6.x+. Proyectos v5.x reciben `app_market.md` como plantilla `template-pristine` vía `upgrade_project` sin modificar archivos existentes.

---

## Lo nuevo en v5.34

**v5.34.0 — "Native Collaboration"** estrena el **Native Backend**: un cuarto backend del `SpecBackend` ABC (junto a Trello / Plane / FreeForm), respaldado por una instancia gestionada de Supabase Postgres, pensado para equipos donde varios developers comparten un único board source-of-truth.

- **Backend Postgres/Supabase multi-tenant** — los 26 métodos del ABC sobre un pool asyncpg, con **concurrencia optimista** (`expected_version`) para que dos developers no pisen el mismo trabajo.
- **Identidad de developer + autorización** — resolución token→developer, Frontier 1 authz (UNAUTHENTICATED / FORBIDDEN). Tools `whoami`, `claim_uc`, `release_uc`, `register_native_branch` (la emisión / revoke de tokens vive en el SpecBox Control Panel desde v5.34.1).
- **Claims de UC + registro de ramas** — un developer reserva un UC y registra su rama feature.
- **Seguridad de credenciales (Frontier 2)** — el DSN vive solo en `SPECBOX_NATIVE_DSN`, nunca en disco ni en `meta.json`.

Opt-in y aditivo: si no configuras `backend_type='native'`, todo se comporta como antes. 100% backwards-compatible — Trello / Plane / FreeForm intactos. Validado en producción contra Supabase real (50 tests verdes).

**v5.34.1** añade dos piezas grandes sobre la misma línea Native, sin tocar el comportamiento de los otros 3 backends:

- **Cambio guiado de backend N×N (`/switch-backend`)** — un proyecto puede migrar de cualquiera de los 4 backends a cualquier otro (12 pares) sin perder US/UC/AC, estado, comments ni evidencia. Migración aditiva (el origen permanece intacto), preview obligatorio, switch transaccional de los 3 lugares de verdad (registry, `app_spec.md`, `settings.local.json`) con rollback, y oferta opt-in de `regenerate_evidence` para refrescar acceptance tras la migración.
- **Native blindado contra mutaciones de identidades revocadas** — cada uno de los 9 mutadores del NativeBackend re-valida identidad + membresía contra `mcp_tokens` con cache TTL hardcoded 30s. Ventana de exposición tras revoke ≤ 30s (antes: horas). `delete_acceptance_criterion` y `archive_item` dejan rastro forense en `audit_log`. Modelo de identidad rediseñado limpio (`developers` + `github_identities` N:1 + `mcp_tokens` revocables) listo para el panel web — el CRUD de equipo deja de vivir en el MCP.

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
- **Telemetría local** en `.quality/task_isolation.json` con `{enabled, tasks_run_total, tasks_failed_*}` (consumible por scripts ad-hoc o specbox_cloud).

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

> **¿Usas la extensión de VS Code?** No necesitas clonar nada a mano: cuando la
> extensión no encuentra el engine, lo clona por ti automáticamente desde el
> repo público a una carpeta gestionada (`~/.specbox/specbox-engine`) y la
> mantiene al día. Los pasos de abajo son para la instalación manual del engine
> por CLI.

```bash
# Instalar el engine globalmente (instalación manual por CLI)
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

## Arrancar un proyecto con la extensión de VS Code

Si usas la **extensión de VS Code** (Marketplace), el arranque no tiene un botón
"Init" mágico: la extensión **instala y configura** el engine, y el *onboarding
del proyecto* (crear el board, elegir backend) sigue ocurriendo en el chat de
Claude Code con las skills/tools. Esto es lo que hace cada acción de la UI por
debajo:

| Acción en la extensión (Command Palette / sidebar) | Comando interno | Qué dispara por debajo |
|---|---|---|
| **SpecBox: Onboard Project** | `specbox.onboard` | Wizard de 5 pasos: prerequisitos → localizar/clonar engine (`resolveEnginePath`, auto-clone desde el repo público si falta) → instalar skills+hooks (`runFullInstall`) → **Configure MCP** → health check. **No crea el board**: deja el entorno listo para que tú corras las skills. |
| **SpecBox: Install Engine** | `specbox.install` | Copia skills a `~/.claude/skills/` y hooks a `~/.claude/hooks/` (equivale a `./install.sh`). |
| **SpecBox: Configure MCP Servers** | `specbox.configureMcp` | Escribe la config del MCP remoto de SpecBox (`npx mcp-remote …`) + Engram en el `settings.json` de Claude Code. |
| **SpecBox: Sign in with GitHub** | `specbox.signIn` | OAuth de GitHub (loopback) → provisiona un `mcp_token` para el **backend native** (Cloud) y lo guarda en el SecretStorage de VS Code. Es el paso que habilita el board native compartido. |
| **SpecBox: Check Prerequisites** | `specbox.checkPrerequisites` | Re-evalúa el entorno (Claude Code, Engram, Node, MCPs) y avisa si falta algo. |

Tras `Onboard Project` + `Sign in with GitHub`, el **arranque real del proyecto**
(crear/poblar el board) se hace en el chat con las tools del MCP:

```text
onboard_project(...)   # registra el proyecto (backend native por defecto desde v6.3.0)
setup_board(...)       # crea el tenant native + tu membresía como project_admin
/app-init              # crea los documentos canónicos doc/app/ (ver nota abajo)
/prd → /plan → /implement
```

> **Nota — "app init" ≠ ningún botón.** Si alguien dice *"app init"*, se refiere a
> la **skill `/app-init`** (crea/refresca `doc/app/app_prd.md` y `app_spec.md` —
> v5.29). **No** es lo mismo que **`onboard_project`** (tool MCP que registra el
> proyecto y autodetecta el stack) ni que **`/quickstart`** (tutorial interactivo
> de onboarding). Los tres son cosas distintas; la extensión no renombra ninguno.

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
> v 6.10.2 — "Mirror Bootstrap" (over v6.10.1 "Reentrant Reserve")

## What is this?

A system that turns Claude Code into a serious teammate:

- **Helps you go fast** without skipping traceability or quality.
- **Learns your project** and stops asking you what you already decided.
- **Blocks dangerous shortcuts** (push to main, vague AC, code without UC, unsafe paths).
- **Coexists with your flow**: spec-driven with FreeForm/Trello/Plane depending on the client.

> SpecBox provides speed. The LLM provides quality.

## What's new in v6.10

**v6.10.0 — "UC Lifecycle Metrics"** two new capabilities: honest per-UC lead-time metrics computed in the database, and a dual-backend Native mirror:

- **Trigger-based lifecycle capture** — every `use_cases.state` transition (whatever the writer) is recorded transactionally in `uc_state_transitions`, with `started_at`/`completed_at` maintained on the row. The start that was never recorded and the best-effort completion that could be silently lost are now bulletproof.
- **KPIs in the DB, thin engine** — `v_lifecycle_kpis` (lead time p50/p90 over measurable UCs only, `coverage_pct` as the honesty KPI, imports excluded by construction yet visible), `v_active_time_estimate` (session-clustering active-time estimate), a read-only role for the panel and the `get_project_kpis` tool.
- **Historical backfill prepared, not executed** — `fn_backfill_lifecycle` (dry-run default) with exact rollback; activated per project after calibrating estimators against real trigger data.
- **Dual-backend Native mirror (US-11)** — an untouchable Trello/Plane/FreeForm primary can simultaneously report to a best-effort Native mirror that never degrades the primary (`enable_mirror`/`disable_mirror` with idempotent backfill).

100% backwards-compatible. Production migrations (`20260611000012..16`) apply via the Supabase ledger at deploy time.

**v6.10.1 — "Reentrant Reserve"** hotfix: reentrant `reserve_uc` inside a transaction uses `INSERT ... ON CONFLICT DO NOTHING` instead of catching `UniqueViolationError`, fixing the `current transaction is aborted` error on `start_uc` after the same developer's `reserve_uc` (UC-1208, PR #118).

**v6.10.2 — "Mirror Bootstrap"** hotfix: `enable_mirror` auto-inits `projects.json` and auto-seeds the project entry from the primary when the registry was never materialised on the cloud MCP host — fixes the `CONFIG_FAILED`/`failing_place=registry` when enabling the Native mirror on the potencial_digital_2026 client; the on-disk primary is never overwritten and the transactional rollback deletes a just-created `projects.json` (US-11/UC-1104, PR #123).

---

## What's new in v6.9

**v6.9.0 — "Self-Provisioning"** the VS Code extension provisions the engine itself, no manual clone:

- **Auto-clone of the public engine** — when the extension can't find the engine on disk, it clones `github.com/EmbedBuild/specbox-engine` into a managed folder (`~/.specbox/specbox-engine`) automatically (notifies, doesn't ask), before falling back to asking you for the folder.
- **Auto-pull of the managed clone** — the update flow keeps that clone current with `git pull --ff-only`. A clone of your own in any other path is **never** touched.
- **Onboarding without "clone first"** — the walkthrough and README no longer ask you to `git clone` as a prerequisite of the extension.

100% backwards-compatible. Auto-clone is the last resort: config/workspace/common paths win, and a failed clone degrades to the manual folder picker.

**v6.9.1 — "Atomic Switch"** changing a project's backend (incl. to/from Cloud/Native) becomes **one all-or-nothing operation**: the new `switch_project_backend` migrates data + seeds identity + switches the config + reports what was discarded in a single call with full rollback. It also closes the remote-MCP path bug: the source is read from the client (content-passing), never the server filesystem.

**v6.9.2 — "Batch Ingest"** uploading a real freeform project (133 KB / hundreds of items) to Cloud/Native now works end-to-end: the migration crosses in **verifiable chunks** (`start → append × N → commit`, SHA-256 per chunk) that the server reassembles and writes in **one atomic transaction** (full rollback on failure). Closes the v6.9.1 transport gap — the `items.json` no longer has to fit in a single tool parameter.

**v6.9.3 — "Tenant Provisioning"** uploading a project to Cloud/Native **from scratch** now works: the migration **auto-provisions** the tenant + your membership as `project_admin` server-side before the gate (breaks the egg-chicken "you're not a member of a project that doesn't exist yet"), and engine and panel agree on a single `project_id` format (canonical `owner/repo` + a derived slug for URLs). Closes the two v6.9.2 gaps.

**v6.9.4 — "Orphan Tenant Recovery"** closes the bug that still broke real from-scratch migration: `setup_board` created the project row **without a membership** (orphan tenant), which **disabled** v6.9.3's auto-provision → `FORBIDDEN` on an empty DB. Double defense: native `setup_board` now provisions tenant + membership atomically (never leaves 0 members), and the auto-provision **adopts** an orphan tenant (0 members) while still protecting tenants that have owners (AC-13). The E2E now starts from the **real dirty state** (orphan first), not a virgin DB. 100% backwards-compatible.

**v6.9.5 — "Tenant-Scoped Keys"** closes the last Cloud/Native migration blocker: the ingest collided on `user_stories_pkey` because the PK was the logical id (`US-01`) **without** per-project namespacing — two projects couldn't share a `US-01` in the same Postgres. The US/UC/AC PK moves to **composite `(project_id, id)`** (migration 0009, idempotent). On top, `/switch-backend` now understands the **FreeForm "exploded" dialect** (nested `index.json` + AC as `.md` checkboxes) via a pure normalizer to `items.json` + a **format pre-flight** and a **native prerequisite gate** that surface failures at step 0 instead of mid-migration. Stale tests realigned to the UC-660/UC-706 contracts. 100% backwards-compatible.

---

## What's new in v6.8

**v6.8.0 — "Connectivity UX"** makes SpecBox truly work with the MCP server running remotely: the server never touches a foreign filesystem and client state flows via content-passing:

- **FreeForm operative end-to-end** — the 7 mutation tools + a Node bridge (`readTrackingBundle`/`writeTrackingBundle`) read/write the client's `doc/tracking` via content-passing. Closes the #82 regression.
- **`/audit` operative over remote MCP** — the 8 ISO/IEC 25010 analyzers ported to Node client-side scan the client's FS, not the VPS.
- **Pedagogical extension updater** — detects stale config after an update, auto-migrates transport (with backup + revert) and explains what changed.
- **Canonical-decision-aware drift gate** — validates against `app_spec.md`, the root cause that let #82 through.

100% backwards-compatible. Closes a class of silent failure on remote MCP.

---

## What's new in v6.7

**v6.7.0 — "Zero-Friction Onboarding"** removes all the friction from installing the VSCode extension and makes it tell you clearly when something is missing:

- **Python-free onboarding** — the MCP server is consumed only through the free hosted endpoint (the Local mode that required Python is gone). Engram installs as a native binary via Homebrew, not pip. Health check, walkthrough and README no longer mention Python.
- **Prerequisites gate** — on startup, if a critical requirement is missing (Claude Code, Engram, Node, or the MCP servers) the extension warns — clearly and non-blocking — that SpecBox may not work correctly, with one-click fixes. Silent when everything is ready.
- **"SpecBox: Check Prerequisites" command** — re-evaluate the environment on demand from the Command Palette.

100% backwards-compatible. Decision: no air-gapped fallback (the remote MCP is free); the gate warns, it does not block.

---

## What's new in v6.0

**v6.0.2 — "Smoke Test Followups"** closes the 3 open issues surfaced by the v6.0.1 smoke test (#60, #61, #62) and removes the last runtime version literal that survived in the server since v5.29:

- **`submit_quality_audit` autogenerates `audit_id`** if the client does not pass one (clients that need idempotency can still pass their own).
- **`run_quality_audit` deprecation now `raise`s** → MCP envelope correctly sets `isError=true`. Clients that only inspect the envelope now detect the deprecation.
- **`validate_discovery_completeness`** accepts all 4 canonical drift resolutions (`feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`) and exposes new `drift.kind` field for future strict-gate modes.
- **`server/server.py`** no longer hardcodes the version — reads it from `ENGINE_VERSION.yaml` at module load. Latent `submit_quality_audit.fn(...)` bug eliminated as a side effect. `fastmcp 3.1.0 → 3.3.1` pinned `>=3.3.1,<4.0.0`.

100% backwards-compatible. Suite `1243 passed / 71 skipped / 0 failed`.

---

**v6.0.1 — "MCP Path Contract"** architectural hotfix that migrates 17 cat-A tools in `server/tools/` to a **universal content-passing pattern**: no `@mcp.tool`-registered function resolves `Path(project_path).resolve()` against the host filesystem. The client reads files locally with `Read`, passes content as string, and writes whatever the tool returns. Fixes the critical remote-MCP bug where tools were returning data from the VPS filesystem, not the client's. Skills updated (`/discovery`, `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check`) + new client helper `.claude/hooks/lib/mcp-client-io.mjs`.

---

**v6.0.0 — "Discovery Foundations"** introduces a permanent **Product Discovery** module integrated into the canonical pipeline (`/discovery → /prd → /plan → /implement`) + the third canonical document `doc/app/app_market.md` (primary ICPs + non-ICPs + global JTBDs + NSM + positioning) + the **multi-doc architectural foundation** (`server/app_docs/registry.py`) that supports extending to N canonical docs in v6.x+. v5.x projects get `app_market.md` as a `template-pristine` template via `upgrade_project` without touching existing files.

---

## What's new in v5.34

**v5.34.0 — "Native Collaboration"** introduces the **Native Backend**: a fourth `SpecBackend` implementation (alongside Trello / Plane / FreeForm), backed by a managed Supabase Postgres instance, built for teams where multiple developers share a single source-of-truth board.

- **Multi-tenant Postgres/Supabase backend** — all 26 ABC methods over an asyncpg pool, with **optimistic concurrency** (`expected_version`) so two developers don't clobber each other's work.
- **Developer identity + authorization** — token→developer resolution, Frontier 1 authz (UNAUTHENTICATED / FORBIDDEN). Tools `whoami`, `claim_uc`, `release_uc`, `register_native_branch` (token issuance / revoke moves to the SpecBox Control Panel in v5.34.1).
- **UC claims + branch registry** — a developer claims a UC and registers its feature branch.
- **Credential security (Frontier 2)** — the DSN lives only in `SPECBOX_NATIVE_DSN`, never on disk or in `meta.json`.

Opt-in and additive: if you don't set `backend_type='native'`, everything behaves as before. 100% backwards-compatible — Trello / Plane / FreeForm untouched. Validated in production against real Supabase (50 green tests).

**v5.34.1** adds two big pieces along the same Native line, without touching the other 3 backends:

- **Guided N×N backend switching (`/switch-backend`)** — a project can migrate from any of the 4 backends to any other (12 pairs) without losing US/UC/AC, state, comments or evidence. Additive migration (origin stays intact), mandatory dry-run preview, transactional switch of the 3 sources of truth (registry, `app_spec.md`, `settings.local.json`) with rollback, and opt-in `regenerate_evidence` to refresh acceptance after a migration.
- **Native hardened against mutations from revoked identities** — each of the 9 NativeBackend mutators re-validates identity + membership against `mcp_tokens` with a hardcoded 30s TTL cache. Exposure window after a revoke ≤ 30s (previously: hours). `delete_acceptance_criterion` and `archive_item` leave a forensic trail in `audit_log`. Cleanly redesigned identity model (`developers` + `github_identities` N:1 + revocable `mcp_tokens`) ready for the panel — team CRUD leaves the MCP.

---

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
- **Local telemetry** in `.quality/task_isolation.json` with `{enabled, tasks_run_total, tasks_failed_*}` (consumable by ad-hoc scripts or specbox_cloud).

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

> **Using the VS Code extension?** You don't need to clone anything by hand —
> when the extension can't find the engine, it clones the public engine for you
> automatically into a managed folder (`~/.specbox/specbox-engine`) and keeps it
> up to date. The steps below are for the manual CLI install of the engine.

```bash
# Manual CLI install of the engine
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
