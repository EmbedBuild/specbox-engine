# Cloud Cutover — Sala de Máquinas removal (v6.1.0)

**Status**: Accepted
**Date**: 2026-05-25
**Supersedes**: "Remote State Management (v5.6.0)", "Remote Telemetry (v3.3)"

## Context

SpecBox Engine shipped, since v5.6.0, a built-in dashboard called **Sala de
Máquinas** — a React 19 + Vite frontend served from the MCP container plus a
REST API (`server/dashboard_api.py`, 16 endpoints) plus a telemetry layer
(hooks `heartbeat-sender.mjs`, `mcp-report.mjs`, `e2e-report.mjs`) plus a
GitHub sync background job (`server/github_sync.py`) plus 5 MCP tools
(`get_project_live_state`, `get_all_projects_overview`, `get_active_sessions`,
`refresh_project_state`, `get_heartbeat_stats`) plus a conversational skill
`/remote` for OpenClaw / WhatsApp / Discord access.

The whole stack was a single-user observability tool deployed on a VPS at
`mcp-specbox-engine.jpsdeveloper.com`. It was never adopted in a meaningful
way: `/remote` was never used effectively, the iPhone flow never went past
prototype, and the VPS dashboard saw essentially zero traffic outside of
manual smoke tests.

In parallel, the team built **specbox_cloud** — an external web panel that
reads the Native Backend's Supabase instance directly and only calls the
MCP server for write operations (reservations, audit submissions). It
covers the same product surface (multi-project status, who-is-working-on-
what, audit history) with proper auth, RLS, multi-tenant boundaries, and a
team-grade UI.

## Decision

Eliminate the entire Sala de Máquinas stack from `specbox-engine` in
v6.1.0. specbox_cloud absorbs every consumer-facing role of the dashboard.

Specifically removed:

| Layer | What |
|---|---|
| Frontend | `server/dashboard/` (React 19 + Vite + Tailwind + Recharts, ~1.8k LoC TSX/TS + 237k LoC node_modules) |
| Backend HTTP | `server/dashboard_api.py` (877 LoC, 16 REST endpoints), `server/github_sync.py` (225 LoC) |
| MCP tools | `get_project_live_state`, `get_all_projects_overview`, `get_active_sessions`, `refresh_project_state`, `get_heartbeat_stats` |
| Hooks | `heartbeat-sender.mjs` (231 LoC), `mcp-report.mjs` (29 LoC), `e2e-report.mjs` (59 LoC), `lib/http.mjs` (144 LoC, MCP HTTP client) |
| Skill | `/remote` |
| Telemetry artefact | `specbox-state.json` in repo root (was committed despite being live state) |
| Env var | `SPECBOX_SYNC_TOKEN` |
| Docker | Stage 1 `dashboard-builder` (Node 20-slim) — single-stage Python now |
| Tests | `test_dashboard_api`, `test_github_sync`, `test_heartbeat`, `test_heartbeat_stats`, `test_live_state`, `test_remote_summaries` |

Preserved:

- **NativeBackend on Supabase** (`server/backends/native_backend.py`,
  `server/db/`, `server/coordination/`, 7 SQL migrations, the
  `mcp_tokens` / `developers` / `uc_reservations` / `audit_log` schema)
  is untouched. specbox_cloud reads the same instance.
- **Coordination tools** (`whoami`, `reserve_uc`, `release_uc`,
  `register_native_branch`) are the MCP-side write API specbox_cloud
  uses for reservations.
- **`/health`** endpoint is kept as a minimal liveness probe on
  `server/server.py` itself (single `@mcp.custom_route`) so the Docker
  HEALTHCHECK keeps working.

## Rationale

1. **Two implementations of the same problem are worse than one.**
   Sala de Máquinas was a single-user dashboard; specbox_cloud is a
   multi-tenant team product. Maintaining both meant duplicate state,
   duplicate auth surface, duplicate domain knowledge.

2. **Heartbeat traffic was overhead with no payoff.** Every session,
   every checkpoint, every `/handoff` spawned background HTTP calls
   that, in practice, no human ever read. Removing them tightens the
   feedback loop on hook reliability and removes a class of intermittent
   spawn failures.

3. **`specbox-state.json` in repo root was a latent footgun.** It was
   committed to `main` despite being a live-state artefact; every
   onboarded repo had churn on it on every session. Removing it stops
   the noise without losing information (the same state lives in
   `.quality/` artefacts that are gitignored).

4. **Docker image gets simpler and smaller.** Stage 1 of the Dockerfile
   was `node:20-slim` purely to `npm ci && npm run build` the React
   frontend. With the cutover, the image is single-stage Python: build
   is faster, attack surface smaller, no Node runtime needed at runtime
   or build-time for the engine.

5. **CLAUDE.md adelgaza ~85 líneas** of stale documentation about
   "Heartbeat Observability", "Conversational Summaries", "GitHub Sync"
   and similar capacity that no skill exercised any more.

## Consequences

### Positive

- ~3,800 LoC of live code removed, ~237k LoC of `node_modules` removed.
- 5 MCP tools removed → less tool-discovery noise for new agents.
- 3 hooks + 5 legacy bash hooks removed → install.sh is shorter, the
  hook tree is less daunting for newcomers.
- 1 skill removed → `find-skills` results are tighter.
- Dockerfile build is single-stage; image ~200MB smaller.
- VPS `mcp-specbox-engine.jpsdeveloper.com` and its dominio can be
  shut down (saving hosting + DNS overhead).

### Neutral / migration

- Projects onboarded in v5.x still have the deleted hooks in their
  `.claude/hooks/`. The `spawn(node, hookPath)` calls inside
  `on-session-end.mjs` and `implement-checkpoint.mjs` fail silently
  with `ENOENT` and the rest of the hook continues. Cleanup is
  optional but tidy: re-run `./install.sh` or delete the 3 `.mjs`
  files manually.
- Anyone with `SPECBOX_SYNC_TOKEN` exported in their shell can leave
  it: it's now ignored everywhere.
- Anyone with `SPECBOX_ENGINE_MCP_URL` pointing at the VPS will start
  seeing connection refused when the VPS is torn down. Switch to a
  local MCP (stdio) or to specbox_cloud's MCP gateway.

### Risk: multi-developer coordination UI

specbox_cloud will need to call `reserve_uc` / `release_uc` against the
MCP whenever it implements a "claim this UC" button in its UI. The MCP
endpoint is the same one Claude Code calls. The write side **must not**
be duplicated by writing directly to `uc_reservations` from
specbox_cloud — the cache TTL, identity revalidation, and audit_log
sequencing live in `server/coordination/reservations.py` and would
drift if forked. Reads from `uc_reservations` (a `SELECT` with
appropriate RLS) are fine and explicitly the intended access pattern.

## Rollback plan

If the cutover proves too aggressive (e.g. a customer turns out to
depend on the VPS dashboard we didn't know about), revert the squashed
v6.1.0 merge commit. The 13 commits inside the PR are designed to be
reverted as a single unit; partial revert is not supported because the
Dockerfile, settings, and CLAUDE.md all assume the post-cutover state.

After revert:
1. The dashboard tree, the REST endpoints, the hooks, the 5 MCP tools
   and the `/remote` skill all return.
2. The VPS must be re-enabled (re-deploy v6.0.2 to
   `mcp-specbox-engine.jpsdeveloper.com`).
3. `specbox-state.json` will re-appear in repo roots as soon as any
   session-end hook fires; bumping that to `main` was the historic
   (and unwanted) behaviour.

## Related

- [Multi-doc registry](./multi_doc_registry.md) — sets the precedent
  that capability removal is sometimes the right shape for v6.x minor
  releases.
- [MCP path contract](./mcp_path_contract.md) — v6.0.1's removal of
  filesystem assumptions on the server side is what made it safe to
  let specbox_cloud read Supabase directly without going through the
  MCP for every read.
