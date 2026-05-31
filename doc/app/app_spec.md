# App Spec — specbox-engine

**Última actualización:** 2026-05-25T00:00:00Z
**Versión del documento:** 2
**Mantenido por:** /app-init (idempotente) y eventos del pipeline

---

<!-- @specbox:zone start kind="auto" id="stack" auto_sync_on="lockfile_change,framework_detected,release_version_bump" -->
## 1. Stack

| Capa | Tecnología | Versión | Detectado de |
|------|------------|---------|--------------|
| Engine / MCP server | Python (FastMCP) | >=3.12 | `pyproject.toml` |
| Gestor de dependencias | uv | — | `uv.lock` |
| Engine package | specbox-engine | 6.1.x | `pyproject.toml` / `ENGINE_VERSION.yaml` |
| Hooks / scripts | Node.js (ESM `.mjs`) | — | `.claude/hooks/*.mjs` |
| Contenedor | Docker single-stage Python | — | `Dockerfile` / `docker-compose.yml` |
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="tracking_backend" auto_sync_on="set_auth_token" -->
## 2. Tracking backend

- **Tipo:** freeform
- **Path absoluto** (si freeform): `/Users/jesusperezsanchez/Desktop/Proyectos/0_jps_iautomat/jpsdeveloper/specbox-engine/doc/tracking`
- **Board id:** `ff-ed0c02f4565a` (board_name: specbox-engine)
- **Reporting externo:** no

> Esta zona la mantiene el engine. Si el usuario cambia el backend, llamar `/app-init --refresh` o esperar al evento set_auth_token.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="brand_visual" -->
## 3. Brand & Visual

- **Brand kit:** SpecBox Engine (SpecBox Engine by JPS) — ver `ENGINE_VERSION.yaml`
- **VEG arquetipo:** Startup
- **Modo VEG:** uniforme
- **Stitch project_id:** (no configurado — el engine es un sistema sin UI de producto propia; la visión multi-proyecto vive en specbox_cloud, panel web externo)
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="manual" id="conventions" -->
## 4. Convenciones del proyecto

- **Naming:** US-XX, UC-XXX, AC-XX
- **Tests:** pytest (Python) en `tests/`
- **E2E:** API (pytest-bdd + httpx para tools del server); el engine no tiene UI de producto E2E
- **Lint:** GGA (`gga run`, cached lint) vía hook `pre-commit-lint`; fallback a lint directo
- **Deployment:** rama `main` protegida; trabajo en ramas `feature/*` / `chore/*`; PR-only salvo autorización explícita; commits firmados con `Co-Authored-By: Claude`
- **Multirepo:** no
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="autopilot" auto_sync_on="autopilot_config_change" -->
## 5. Autopilot

- **Level:** equilibrado
- **Image budget €/feature:** 5
- **Auto-confirm overrides:** []
- **Always-ask overrides:** []
- **Queue enabled:** false

> Esta zona se sincroniza automáticamente desde `.claude/settings.local.json`. Para cambiar la política, edita ese archivo y `/app-sync --refresh`.
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="hybrid" id="canonical_decisions" merge="append_only" -->
## 6. Decisiones canónicas

- **Backend default = FreeForm** — proyectos personales/internos usan FreeForm; Trello/Plane solo para reporting externo a clientes.
- **PR-only a main** — nunca push directo a main salvo autorización explícita del usuario en la sesión.
- **README bump en cada versión** — toda versión (major/minor/patch) actualiza README.md (bloques ES + EN), no solo ENGINE_VERSION.yaml/CLAUDE.md/CHANGELOG.
- ~~**FreeForm requiere MCP local (stdio)**~~ — **REVISADA/SUSTITUIDA** (2026-05-31, UC-668) por **Transporte único MCP remoto + content-passing** (ver abajo). Ref. `doc/prd/specbox_connectivity_ux_prd.md`. La premisa original (filesystem-local exige transporte-local) quedó obsoleta con el MCP Path Contract (v6.0.1): content-passing rompe ese acople. Histórico conservado (append-only): para escribir `doc/tracking/` el MCP debía correr como proceso local.
- **`claim`→`reservation` (v5.35.0)**: renombre del concepto de coordinación multi-developer del Native Backend; rationale = legibilidad para no técnicos; alias deprecados v5.35–v5.36; tools MCP `claim_uc` removed in v5.37.0.
- **Transporte único MCP remoto + content-passing** (2026-05-31, UC-668) — el MCP server nunca toca un filesystem ajeno; el estado del cliente (FreeForm, evidencia, audit) entra/sale por content-passing vía el bridge Node (`.claude/hooks/lib/mcp-client-io.mjs`); el estado cloud (Trello/Plane/Native) lo opera el server directamente contra su API. Transporte único: MCP remoto, online-first (no existe modo offline en un sistema agéntico que depende de Claude Code, que exige red). **Sustituye** a "FreeForm requiere MCP local (stdio)". Ref. `doc/prd/specbox_connectivity_ux_prd.md`.

<!-- engine-entries-below -->
{(vacío hasta que la Capa 4 detecte 3 confirmaciones consecutivas idénticas)}
<!-- @specbox:zone end -->
