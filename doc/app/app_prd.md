# App PRD — specbox-engine

**Última actualización:** 2026-05-25T00:00:00Z
**Versión del documento:** 2
**Mantenido por:** /app-init (idempotente) y eventos del pipeline

---

<!-- @specbox:zone start kind="manual" id="vision" -->
## 1. Visión

SpecBox Engine es un sistema de programación agentica para Claude Code: un monorepo unificado (engine + MCP server + Gherkin BDD + Quality Audit ISO/IEC 25010 + Product Discovery) que aporta trazabilidad spec-driven (US → UC → AC), enforcement automático vía hooks, y un pipeline completo de desarrollo (`/prd` → `/plan` → `/implement` → `/feedback`). La visión cross-proyecto (dashboard multi-tenant) vive en **specbox_cloud**, panel web externo que lee directamente la instancia Supabase del Native Backend. SpecBox aporta la velocidad; el LLM aporta el rigor.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="audience" -->
## 2. Audiencia + JTBD

**Modo VEG aplicable:** uniforme

### Targets
- **JPS (uso propio)** — Desarrollador principal y dueño del engine. JTBD racional: programar features end-to-end con trazabilidad y calidad sin reinventar el flujo cada vez. JTBD emocional: confianza de que nada se pierde entre sesiones y que el pipeline protege la calidad bajo presión.
- **Devs que usan Claude Code** — Desarrolladores externos que adoptan SpecBox para programación agentica en sus propios proyectos. JTBD racional: convertir un PRD en código verificado con evidencia. JTBD emocional: sentir que el agente trabaja con disciplina, no improvisando.
- **Equipos / agencias** — Equipos multi-dev y agencias con necesidad de trazabilidad spec-driven y reporting a clientes (Trello/Plane). JTBD racional: demostrar avance auditable a stakeholders. JTBD emocional: control y transparencia frente al cliente.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="scope" -->
## 3. Perímetro

### v1 (in scope)
- Pipeline spec-driven completo (`/prd`, `/visual-setup`, `/plan`, `/implement`, `/feedback`)
- MCP server unificado (FastMCP, JSON-RPC + minimal `/health`)
- 3 backends de tracking intercambiables (FreeForm, Trello, Plane) vía abstracción `SpecBackend`
- Enforcement vía hooks (quality-first, spec-guard, branch-guard, pipeline-integrity, etc.)
- Acceptance Engine (AG-08/AG-09/AG-10) + Quality Audit ISO/IEC 25010 on-demand
- VEG (Visual Experience Generation) + integración Google Stitch MCP
- Documentos canónicos `doc/app/` + autopilot (Cognitive Load Reduction v5.29)
- Paquetes MCP independientes (specbox-stripe-mcp, specbox-supabase-mcp)

### v2+ (out of scope hoy, planeado)
- Backend nativo Postgres centralizado para colaboración multi-dev en tiempo real
- Quality Audit con histórico / tendencias / diffs entre auditorías + gates bloqueantes
- Hooks automáticos post-`/implement` (audit no manual)

### Nunca (out of scope permanente)
- **Un IDE propio** — SpecBox vive ENCIMA de Claude Code (skills, hooks, MCP). Nunca será un editor/IDE ni un fork del CLI.
- **Soporte a otros LLMs/runtimes agénticos** — Es específico de Claude Code. No abstraerá GPT/Gemini/otros como runtime.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="hybrid" id="success_metrics" merge="append_only" -->
## 4. Métricas de éxito

- Interrupciones por feature ≤ 8 en preset `equilibrado` (baseline v5.28: ≥17).
- Trazabilidad 100%: toda línea de código de un proyecto spec-driven nace de un UC activo (enforced por spec-guard).
- Cobertura de evidencia E2E: todo UC ACCEPTED tiene HTML Evidence Report.
- Compliance audit del propio engine ≥ A en cada release.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="roadmap" auto_sync_on="complete_uc,move_uc,add_uc,delete_uc,mark_ac_batch" -->
## 5. Roadmap de US

{Esta zona la mantiene el engine. NO EDITES MANUALMENTE — los cambios serán sobrescritos en la próxima sincronización tras eventos del pipeline.}

| US | Título | Estado | UCs | Última actualización |
|----|--------|--------|-----|----------------------|
| (vacío) | (sin US en el backend FreeForm `ff-ed0c02f4565a` — `items.json` vacío) | | | |
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="stakeholders" -->
## 6. Stakeholders

- **Product owner:** Jesús Pérez (JPS)
- **Reporting externo:** no, FreeForm interno (board id "ff-ed0c02f4565a")
<!-- @specbox:zone end -->
