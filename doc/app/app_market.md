# App Market — specbox-engine

**Última actualización:** 2026-05-27
**Versión del documento:** 1
**Mantenido por:** /discovery (bootstrap) + /app-init/refresh + eventos del pipeline

---

<!-- @specbox:zone start kind="manual" id="icps_primary" -->
## 1. ICPs primarios

### ICP-1: Owner-operator del engine (JPS, dogfooding)
- **Quién**: Desarrollador único que mantiene SpecBox Engine y lo usa simultáneamente como producto y herramienta diaria.
- **Atributos diferenciadores**: conoce el código entero; programa, refactoriza y libera versiones semanalmente; escribe tests sobre la propia base del engine; tolera fricción de v1 porque la corrige él mismo.
- **Sanity check 3 personas concretas**: ✅ trivial — es 1 persona explícita (el owner), single-tenant por diseño en v1.
- **Estado**: canónico.

### ICP-2: Dev solo con Claude Code que adopta SpecBox
- **Quién**: Desarrollador individual que instala el engine en sus propios proyectos para tener trazabilidad spec-driven sin reinventar pipeline.
- **Atributos diferenciadores**: ya usa Claude Code como entorno principal; valora disciplina spec-driven; rechaza "vibe coding"; está dispuesto a leer hooks y entender enforcement mecánico.
- **Sanity check 3 personas concretas**: tentative — hay early adopters identificables en la comunidad pero no comprometidos formalmente todavía en v1.
- **Estado**: tentative.

### ICP-3: Equipo/agencia con reporting a cliente
- **Quién**: Equipos multi-dev que necesitan demostrar avance auditable a stakeholders externos vía Trello/Plane.
- **Atributos diferenciadores**: tienen cliente externo que pide reporting; usan Trello o Plane como gestor; necesitan PDFs de evidencia adjuntables a cards; el handoff entre devs del equipo importa.
- **Sanity check 3 personas concretas**: tentative — segmento hipotético v1, real esperado v2 con Native Backend (colaboración multi-dev en tiempo real).
- **Estado**: tentative.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="no_icps" -->
## 2. No-ICPs (anti-mercado)

Protección contra feature creep. Estos perfiles NO son target — no priorizamos features para ellos y rechazamos feedback que los favorezca si rompe el contrato con los ICPs primarios.

- **Usuarios de IDEs que no son Claude Code** (Cursor, Copilot CLI, Aider, etc.). SpecBox vive como skills/hooks/MCP de Claude Code específicamente; no abstraerá runtimes.
- **Equipos que buscan un PM tool standalone** (Linear/Jira-replacement). SpecBox es agentic infra, no un product management tool. La capa US/UC/AC existe para alimentar al agente, no para ser dashboard ejecutivo.
- **"Vibe coders" que rechazan disciplina spec-driven**. Si el dev no quiere PRD/UC/AC/evidencia, SpecBox le incomodará — y eso es por diseño.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="jtbds_rational_global" -->
## 3. JTBDs racionales globales

- **JR-G.1**: Cuando desarrollo una feature compleja, quiero un pipeline que traduzca el problema en código verificado con trazabilidad US→UC→AC, para que cada línea de código justifique su existencia y pueda explicarse al stakeholder o a mí mismo en 3 meses.
- **JR-G.2**: Cuando vuelvo a un proyecto tras días/semanas, quiero recuperar el contexto completo sin reconstruir mental state, para no perder horas re-orientándome (handoff + heartbeat + active_uc.json son la materialización).
- **JR-G.3**: Cuando el agente improvisa bajo presión (tests rojos, deadline, healing loop), quiero que hooks mecánicos le impidan saltarse calidad (sin `--no-verify`, sin push a main, sin write sin read previo), para que la disciplina no dependa de fuerza de voluntad del agente ni del humano.
- **JR-G.4**: Cuando hago refactor de la base, quiero suite verde con evidencia HTML como gate de merge, para detectar regresiones antes del deploy y producir artefacto auditable.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="jtbds_emotional_global" -->
## 4. JTBDs emocionales globales

- **JE-G.1**: Confianza de que nada se pierde entre sesiones. Handoff + heartbeat son la red de seguridad psicológica que permite cerrar el laptop sin ansiedad de "¿retomaré dónde lo dejé?".
- **JE-G.2**: Sentir que el agente trabaja **con** disciplina, no improvisando. El ruido constante de "cuidado, validá esto, no te saltes aquello" desaparece porque los hooks ya lo hacen mecánicamente — el humano puede dedicar el ciclo cognitivo a la lógica del problema, no al policing del agente.
- **JE-G.3**: Sentir que cada artefacto visible del producto — listing del Marketplace, sidebar de la extensión VSCode, walkthrough, README, panel cloud, CLI de ayuda — refleja la disciplina interna del engine. Drift entre la realidad del código y lo que la UI muestra (skills fantasma, descripciones desactualizadas, iconos mudos) mata la credibilidad del producto frente a quien lo está adoptando. La cara visible del producto es la primera evidencia de su calidad.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="north_star" -->
## 5. North Star Metric

### NSM
**Interrupciones por feature** (preguntas al usuario durante `/prd → /plan → /implement` en preset `equilibrado`).
- **Target**: ≤ 8 por feature.
- **Baseline v5.28**: ≥ 17 por feature.
- **Mide**: cognitive load real impuesto al humano por el pipeline.

### Input metrics
- **% features con discovery completado antes de `/prd`** (target ≥ 80% v6.x, ≥ 95% v6.2+).
- **% UCs ACCEPTED con HTML Evidence Report adjunto** (target 100%).
- **Healing budget medio por feature** (target < 4 attempts; hard cap 8).
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="exportable_copy" auto_sync_on="discovery_completed,record_app_docs_signature" -->
## 6. Exportable copy (derivada)

{Esta zona la mantiene el engine. NO EDITES MANUALMENTE — derivada de ICPs + JTBDs globales.}

### Landing headline
> Programación agéntica con disciplina. SpecBox aporta la velocidad; el LLM aporta el rigor.

### LinkedIn post template
> Después de N features hechas con SpecBox Engine sobre Claude Code, lo que cambia no es la velocidad —es la confianza. Cada línea de código nace de un AC, cada AC tiene evidencia HTML, y nada se pierde entre sesiones. El agente trabaja con disciplina, no improvisando.

### Elevator pitch (30s)
> SpecBox Engine es un sistema de programación agéntica para Claude Code que añade pipeline spec-driven (US→UC→AC), enforcement automático vía hooks, y evidencia auditable de cada feature. Pensado para devs que quieren velocidad sin renunciar a trazabilidad — porque el LLM aporta el rigor cuando la infraestructura le obliga.
<!-- @specbox:zone end -->
