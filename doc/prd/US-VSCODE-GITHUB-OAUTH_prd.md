# PRD: US-VSCODE-GITHUB-OAUTH — GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth

> Origen: FreeForm board `ff-ed0c02f4565a` | US-VSCODE-GITHUB-OAUTH
> Tipo: PRD Spec-Driven (feature) sobre extensión existente + endpoint cloud
> Generado: 2026-05-27
> Release target: v6.3.0 "Native Default OAuth" (minor)
> Discovery: [doc/discovery/us_vscode_github_oauth/icp_jtbd.md](../discovery/us_vscode_github_oauth/icp_jtbd.md) — verdict `READY_FOR_PRD`, drift resolved como `documented_exception`.

## Resumen

La US-VSCODE-MARKETPLACE (v6.2.0) abrió la puerta de la instalación en un click vía VSCode Marketplace. Pero el embudo se rompe en el siguiente paso: para usar el **Native Backend** —el único que habilita colaboración multi-developer real y telemetría de adopción— hay que provisionar manualmente un `mcp_token` desde `cloud.specbox.build` y pegarlo en `.claude/settings.local.json`. ICP-2 abandona en ese punto.

Esta US integra **GitHub OAuth en la extensión** apoyándose en el sistema de auth de Supabase ya en producción en `cloud.specbox.build`. Al primer activate de la extensión, el usuario ve una notificación con dos opciones: **"Sign in with GitHub"** (camino feliz, recomendado, queda registrado en Supabase como dev activo) o **"Continuar en modo local (FreeForm)"** (escape persistente, sin auth, conserva el principio v5.29).

**Hallazgo de inspección del repo `specbox_cloud`** (clonado en `~/Desktop/Proyectos/0_jps_iautomat/embed.build/repositorios/specbox_cloud`): el cloud ya tiene en producción Supabase Auth nativo con GitHub OAuth, plugin Fastify `auth.ts` con JWT JWKS + cache 30s (mismo TTL que `authenticate_and_authorize_cached` del engine — ya alineado), endpoints `POST /api/mcp-tokens` y `POST /api/mcp-tokens/:id/revoke`, tablas `panel.profiles`, `developers`, `github_identities`, `mcp_tokens`, `audit_log`. Lo único que falta para cerrar el flow de la extensión es: (a) un endpoint **self-service** que un developer normal pueda llamar para emitirse a sí mismo un mcp_token (el actual `POST /api/mcp-tokens` requiere `requireSuperAdmin`), y (b) una **página web** que sirva de pasarela entre el browser de OAuth y el loopback de la extensión.

Por tanto, la US se divide en dos:
- **Esta US** (US-VSCODE-GITHUB-OAUTH en `specbox-engine`) cubre el lado consumidor: loopback, SecretStorage, notification onboarding, sidebar, MCP UNAUTHENTICATED graceful, tests E2E, docs.
- **US paralela** (US-AUTH-VSCODE-SELF-SERVICE-TOKEN en `EmbedBuild/specbox_cloud`) cubre el endpoint self-service + la página web. Se crea como parte de este mismo flow `/prd`.

El flujo real del usuario es: notification al activate → click "Sign in with GitHub" → loopback en 127.0.0.1:random → openExternal a `cloud.specbox.build/vscode/issue-token?return_to=<loopback>&state=<csrf>` → si no hay sesión Supabase, `signInWithOAuth({provider: 'github'})` (GitHub OAuth ya configurado) → web llama `POST /api/mcp-tokens/issue-for-self` con JWT → recibe `clear_token` → redirige a `return_to?mcp_token=<clear>&state=<csrf>` → extensión guarda en SecretStorage → MCP local se re-spawn con env var → status bar "Signed in as @handle". Cero copy-paste de tokens.

Aprovecha la infraestructura ya existente sin reinventar:
- `authenticate_and_authorize_cached` (TTL 30s) en `server/coordination/identity.py` del engine cierra la ventana de revoke a ≤30s.
- `plugins/auth.ts` del cloud (cache 30s también) garantiza coherencia bidireccional.
- Tablas `developers`, `github_identities`, `mcp_tokens` en Supabase production.
- `issueMcpToken()` en `apps/api/src/lib/tokens.ts` (sha256_hex, mismo algoritmo que el engine).
- `audit_log` con `metadata.via` (`'self-service' | 'superadmin'`) ya implementado en UC-207.

## Decisiones congeladas (no reabrir)

Heredadas off-band del owner — documentadas en Engram `architecture/vscode-github-oauth` #5746:

1. **Default backend**: Native + GitHub OAuth como recomendado; FreeForm como escape **discreto pero visible**, no obligatorio.
2. **MCP sin auth**: tools nativas responden `UNAUTHENTICATED` graceful; FreeForm/Trello/Plane operan offline.
3. **Token storage**: VSCode SecretStorage API (Keychain macOS / DPAPI Windows / libsecret Linux). Cero plaintext en disco.
4. **Timing prompt OAuth**: notification al **primer activate** de la extensión (workspaceContains: `ENGINE_VERSION.yaml` o `.claude/settings.json`). Una sola vez por workspace, dismissable. Si el usuario dismiss, NO vuelve a aparecer hasta `/onboard` explícito o comando que requiera identidad.
5. **OAuth provider**: Supabase Auth de `cloud.specbox.build` con redirect al loopback de la extensión. **NO** `vscode.authentication.getSession('github', ...)` nativo, **NO** GitHub OAuth App propia de la extensión. Un solo IdP, RLS de Supabase aplica directo, reusa lo que el panel ya tiene.

## Alcance

### Incluye

- **Loopback OAuth server efímero** en la extensión (puerto random, listen-localhost-only, single-use, cierra tras callback o timeout 5min).
- **Consumo del browser flow `cloud.specbox.build/vscode/issue-token`** que combina la sesión Supabase Auth (GitHub OAuth ya en producción) + emisión self-service de mcp_token. La implementación del endpoint+página web vive en una **US paralela del repo `EmbedBuild/specbox_cloud`** (US-AUTH-VSCODE-SELF-SERVICE-TOKEN). Esta US del engine solo cubre el lado consumidor (validación de respuesta, manejo de errores, fallback).
- **VSCode SecretStorage** para persistir mcp_token + handshake con MCP server local al arrancar (preferred: env var inyectada al spawn del MCP por la extensión vía `claude.mcpServers.*` config).
- **Notification al activate** con CTA "Sign in with GitHub" + link discreto "Continuar en modo local (FreeForm)". Estado de dismiss persistente en `workspaceState`.
- **UNAUTHENTICATED graceful** en las 4 tools nativas. Validar: hoy en `server/coordination/identity.py` algunas paths levantan exceptions; debe ser uniforme retornar `{error: "UNAUTHENTICATED", message: "..."}`.
- **UI en sidebar de la extensión**: "Signed in as @handle" (o "Not signed in (FreeForm mode)") + comando "SpecBox: Sign out".
- **Tests de integración E2E** del flow loopback OAuth contra Supabase test mode.
- **README + CHANGELOG + runbook** reflejando el nuevo onboarding default.
- **Settings template update**: `templates/settings.json.template` con `backend_type=native` como default y override visible a FreeForm.

### No incluye

- **Refactor de `cloud.specbox.build`**: el endpoint `/auth/github` debe crearse pero NO se reescribe el panel completo. Out of scope.
- **OAuth providers adicionales** (GitLab, Bitbucket, Google). GitHub-only en v1.
- **MFA / 2FA explícito en el flow**: heredado de GitHub OAuth + Supabase. No añadimos capa propia.
- **Multi-account switching** en la extensión. Un solo dev signed in a la vez. Switch = sign out + sign in.
- **Migrar proyectos FreeForm existentes a Native automáticamente**. La US existente `US-BACKEND-SWITCH` (skill `/switch-backend`) cubre esa transición.
- **Auto-creación de proyectos en Native al sign-in**. El sign-in solo registra al developer; el proyecto se crea como hoy (`onboard_project`).
- **Revocación desde la extensión**. El revoke vive en `cloud.specbox.build` (Sala de Máquinas v2 / panel admin). La extensión solo respeta el revoke (TTL 30s).

---

## User Story

**ID**: US-VSCODE-GITHUB-OAUTH
**Nombre**: GitHub OAuth en la extensión VSCode, Native Backend como default registrado en Supabase Auth
**Actor**: Dev solo con Claude Code que adopta SpecBox (ICP-2 canónico, ver `app_market.md` §1)
**Pantallas**: ninguna nueva (extensión existente; UI dentro del sidebar `specbox.status` y notification al activate)
**Backend**: FreeForm `ff-ed0c02f4565a` para tracking de esta US

> **Como** developer que acaba de instalar SpecBox Engine desde el VSCode Marketplace,
> **quiero** autenticarme con GitHub en menos de 60 segundos sin tocar tokens manualmente,
> **para** empezar a usar el engine en modo Native sin pelearme con setup de credenciales —
> con la garantía de que si prefiero quedarme en local (FreeForm) puedo hacerlo
> con un click sin que el producto me empuje a sign-in en cada workspace.

---

## Use Cases

### UC-644: Loopback OAuth server efímero en la extensión

- **Actor**: Engine (VSCode extension)
- **Pantallas**: ninguna
- **Estado**: backlog

#### Descripción
La extensión, al disparar el flow OAuth, levanta un servidor HTTP local efímero en `127.0.0.1:<puerto-random>`, abre el browser apuntando a `cloud.specbox.build/auth/github?redirect_uri=http://127.0.0.1:<puerto>/callback&state=<csrf-token>`, espera el callback con el `mcp_token`, lo guarda en SecretStorage y cierra el servidor. Single-use, timeout 5min.

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fus_vscode_github_oauth.2]: El comando `SpecBox: Sign in with GitHub` levanta un servidor HTTP en `127.0.0.1` con puerto random asignado por el SO (puerto 0), escucha solo en loopback (NUNCA `0.0.0.0`), y abre el browser del usuario apuntando a `cloud.specbox.build/auth/github` con query params `redirect_uri=http://127.0.0.1:<port>/callback` y `state=<random-32-byte-hex>` en menos de 1 segundo medido desde el click del CTA hasta el `vscode.env.openExternal`.
- [ ] **AC-02** [JR-Fus_vscode_github_oauth.2]: El servidor loopback acepta exactamente **una** request a `/callback` con query params `mcp_token` y `state`; valida que `state` matchea el enviado en AC-01 (rechaza con HTTP 400 si no matchea), guarda el `mcp_token` en SecretStorage y cierra el server en el mismo tick. Cualquier segunda request al puerto recibe HTTP 410 Gone.
- [ ] **AC-03** [JE-Fus_vscode_github_oauth.1]: Si el callback no llega en 5 minutos desde el `openExternal`, el server se cierra automáticamente y la extensión muestra notification `vscode.l10n.t("Sign in cancelled — no callback received. Try again from the SpecBox sidebar.")` (con su variante ES en `bundle.l10n.es.json`). Test verificable con timer mock.
- [ ] **AC-04** [JR-Fus_vscode_github_oauth.2]: Tras callback exitoso, la página HTML servida en el browser muestra título `vscode.l10n.t("Signed in to SpecBox")` + cuerpo `vscode.l10n.t("You can close this tab and return to VSCode.")` + style inline mínimo (sin assets externos para evitar leaks de telemetría) + auto-close del tab vía `window.close()` con fallback texto si el browser lo bloquea.
- [ ] **AC-05** [JE-Fus_vscode_github_oauth.3]: El servidor loopback rechaza con HTTP 400 cualquier request que no venga del `Origin: cloud.specbox.build` o que use HTTP methods distintos de GET (defense in depth contra DNS rebinding). Test cubierto con request manual desde origen falso.

---

### UC-645: Consumir endpoint self-service `cloud.specbox.build/vscode/issue-token` (cross-repo dependency)

- **Actor**: Engine (VSCode extension, consumer)
- **Pantallas**: ninguna (server-side del cross-repo)
- **Estado**: backlog
- **Cross-repo dependency**: la implementación del endpoint+página web vive en **specbox_cloud** bajo US-AUTH-VSCODE-SELF-SERVICE-TOKEN (US paralela creada en este mismo flow).

#### Descripción

**Cambio mayor de modelo descubierto al inspeccionar specbox_cloud**: ya hay GitHub OAuth en producción usando **Supabase Auth nativo** (no un endpoint custom `/auth/github`). El JWT viene con `user_metadata.user_name` = github_login. `apps/api/plugins/auth.ts` decora `request.user` desde el JWT con cache 30s — mismo TTL que el discovery ya documentaba. `POST /api/mcp-tokens` (UC-121) existe pero **requiere `requireSuperAdmin`** — un developer normal no puede emitirse tokens.

El patrón real del flow en v6.3.0 es:

1. **Extensión** (UC-644) abre browser hacia `cloud.specbox.build/vscode/issue-token?return_to=http://127.0.0.1:<port>/callback&state=<csrf>`.
2. **Página web "Generate VSCode token"** (en `apps/web/src/routes/vscode/issue-token.tsx`, **a crear en US paralela del cloud**):
   - Si NO hay sesión Supabase activa → dispara `supabase.auth.signInWithOAuth({provider: 'github', options: {redirectTo: <current_url_with_return_to_preserved>}})`. GitHub OAuth ya está configurado en Supabase project, NO se reimplementa.
   - Si SÍ hay sesión → llama `POST /api/mcp-tokens/issue-for-self` con JWT Bearer (Authorization header). El endpoint nuevo (a crear en US paralela del cloud) valida que `req.user.developer_id` no es null y emite mcp_token con `name="vscode-<hostname>"` (UC-121 reutilizado pero sin `requireSuperAdmin`; en su lugar valida `req.user.role === 'developer'` o superadmin + `developer_id` = sub del JWT).
   - Recibe response `{token_id, name, created_at, clear_token}` y redirige a `return_to?mcp_token=<clear_token>&state=<csrf>`.
3. **Loopback** (UC-644) recibe callback, guarda token en SecretStorage.

Este UC en el PRD del engine cubre el **lado consumidor**: validación del shape de respuesta, manejo de errores del endpoint cloud, fallback a copy-paste manual si el flow falla.

#### Acceptance Criteria

- [ ] **AC-01** [JR-Fus_vscode_github_oauth.2]: La URL que la extensión abre via `vscode.env.openExternal` es exactamente `https://cloud.specbox.build/vscode/issue-token?return_to=<URI-encoded-loopback>&state=<csrf-token>` (NO `/auth/github` ni endpoints OAuth directos — el OAuth real vive dentro del web flow de specbox_cloud). Test: spy sobre `openExternal` en VSCode test runner, assert el URL exacto con regex `^https://cloud\.specbox\.build/vscode/issue-token\?return_to=http%3A%2F%2F127\.0\.0\.1%3A\d+%2Fcallback&state=[a-f0-9]{64}$`.
- [ ] **AC-02** [JR-Fus_vscode_github_oauth.2]: El callback al loopback que la página `cloud.specbox.build/vscode/issue-token` envía tiene la forma `GET /callback?mcp_token=<64-hex>&state=<csrf>`. La extensión valida `state` matchea el enviado en AC-01 y que `mcp_token` matchea regex `^[a-f0-9]{64}$` (formato fijado por `lib/tokens.ts` del cloud — sha256_hex). Si no matchea, rechaza con HTTP 400 desde el loopback sin guardar nada.
- [ ] **AC-03** [JE-Fus_vscode_github_oauth.3]: La extensión NO toca directamente `POST /api/mcp-tokens/issue-for-self` ni gestiona JWT — esa interacción vive completamente dentro del browser flow de specbox_cloud. El acoplamiento de specbox-engine con specbox_cloud queda restringido a 2 puntos: URL del web flow (AC-01) y shape del callback (AC-02). Test: grep en `vscode-extension/src/` no encuentra referencias a `Authorization: Bearer` ni a `supabase.auth.*` ni a `/api/mcp-tokens` directas — el contrato es solo URL params del browser flow.
- [ ] **AC-04** [JE-Fus_vscode_github_oauth.1]: Si el browser flow del cloud falla y retorna `?error=<code>&error_description=<msg>` al loopback (en vez de `mcp_token`), la extensión muestra notification `vscode.l10n.t("Sign in failed: {0}", error_description)` con CTA "Try again" (re-dispara UC-644 con state nuevo) y CTA "Continue in local mode (FreeForm)" (cae a UC-647 path FreeForm). Cero stack traces visibles al usuario.
- [ ] **AC-05** [JR-Fus_vscode_github_oauth.4]: El `mcp_token` recibido se valida llamando `whoami()` al MCP server local con el token inyectado vía env. Si `whoami()` retorna OK (válido + developer activo en Supabase), la extensión persiste en SecretStorage (UC-646). Si `whoami()` retorna `UNAUTHENTICATED` u otro error, la extensión muestra notification con CTA "Sign in again" sin guardar nada — el flow se considera roto del lado del cloud y se reporta como bug si es repetible. Test E2E cubierto en UC-650.
- [ ] **AC-06** [JR-Fus_vscode_github_oauth.4]: Documentación: `vscode-extension/README.md` sección "How sign-in works under the hood" referencia explícitamente la US paralela del cloud (`EmbedBuild/specbox_cloud` US-AUTH-VSCODE-SELF-SERVICE-TOKEN) y link a las dos páginas del cloud que la extensión consume (`/vscode/issue-token`). Mantiene a los futuros maintainers conscientes del acoplamiento cross-repo. Test: `grep -c "vscode/issue-token" vscode-extension/README.md` ≥ 1.

---

### UC-646: VSCode SecretStorage + handshake con MCP server local

- **Actor**: Engine (VSCode extension)
- **Pantallas**: ninguna
- **Estado**: backlog

#### Descripción
Tras recibir el `mcp_token` por callback, la extensión: (1) lo guarda con `context.secrets.store('specbox.mcpToken', token)` (Keychain/DPAPI/libsecret); (2) hace handshake con el MCP server local re-spawning el proceso con env var `SPECBOX_NATIVE_MCP_TOKEN=<token>` injectada vía `claude.mcpServers.specbox-engine.env` (modificando `.vscode/settings.json` del workspace o `.claude/settings.local.json` según convención del proyecto); (3) muestra status bar "✓ Signed in as @handle". Cero plaintext del token en `settings.json`.

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fus_vscode_github_oauth.1]: Tras callback OAuth exitoso, el `mcp_token` queda persistido en `context.secrets.store('specbox.mcpToken', token)`. Verificable en macOS con `security find-generic-password -s "vscodeapplicationextension"` mostrando una entry; en Linux con `secret-tool search application vscode`; en Windows con la API de Credential Manager. Test E2E desde VSCode test runner que llama `await context.secrets.get('specbox.mcpToken')` y compara con el token devuelto por mock OAuth.
- [ ] **AC-02** [JE-Fus_vscode_github_oauth.1]: NINGÚN archivo en el workspace (`.vscode/settings.json`, `.claude/settings.local.json`, `.claude/mcp.json`, ni cualquier otro) contiene el `mcp_token` en plaintext después del sign-in. Verificable con `grep -r "<token>" .vscode/ .claude/` retornando 0 matches. La config de MCP que la extensión escribe en `claude.mcpServers.specbox-engine.env` usa el placeholder `${SPECBOX_NATIVE_MCP_TOKEN}` que se resuelve vía un proceso wrapper que lee de SecretStorage al spawn del MCP.
- [ ] **AC-03** [JR-Fus_vscode_github_oauth.1]: El MCP server local, al arrancar, lee `SPECBOX_NATIVE_MCP_TOKEN` de env, llama `set_auth_token(api_key="", token=<env>, backend_type="native")` automáticamente, y registra en `.quality/logs/mcp-handshake.jsonl` el evento `{event: "auto_authenticated", developer_handle: "...", timestamp: "..."}` (sin el token en plaintext). Verificable con un MCP test session que inicia con env set y llama `whoami()` retornando el developer correcto.
- [ ] **AC-04** [JE-Fus_vscode_github_oauth.3]: Si el `mcp_token` es revocado en Supabase, la próxima llamada a cualquier tool nativa retorna `UNAUTHENTICATED` en ≤30s (cubierto por `authenticate_and_authorize_cached` TTL 30s ya existente en v5.34.1). Test: revocar `mcp_tokens.revoked_at = now()` en Supabase mientras una sesión MCP está activa; siguiente `whoami()` post-30s retorna `{error: "UNAUTHENTICATED"}`. La extensión detecta el error y muestra notification "Your session was revoked. Sign in again?".
- [ ] **AC-05** [JE-Fus_vscode_github_oauth.1]: El comando `SpecBox: Sign out` borra `context.secrets.delete('specbox.mcpToken')`, remueve la env var de la config MCP, mata el proceso MCP actual y lo respawn sin token. Tras sign-out, el sidebar muestra "Not signed in (FreeForm mode)" y las tools nativas retornan `UNAUTHENTICATED` graceful. Verificable con e2e: sign-in → assert state="signed_in" → sign-out → assert state="signed_out" sin reiniciar VSCode.

---

### UC-647: Onboarding notification al primer activate (one-shot, dismissable, persistente)

- **Actor**: Engine (VSCode extension)
- **Pantallas**: ninguna (notification + CTAs)
- **Estado**: backlog

#### Descripción
Al disparar el `activate()` de la extensión (`workspaceContains: ENGINE_VERSION.yaml` o `.claude/settings.json`), la extensión verifica si ya hay decisión previa de onboarding en `workspaceState.get('specbox.onboardingDecision')`. Si **no la hay**, muestra `vscode.window.showInformationMessage` con dos CTAs equivalentes en jerarquía: **"Sign in with GitHub"** (primary, abre flow OAuth) y **"Continue in local mode (FreeForm)"** (secondary, equally visible, NO está como "Dismiss" sutil). Sea cual sea la elección, se persiste en `workspaceState` y NO se vuelve a mostrar.

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fus_vscode_github_oauth.1]: Al primer `activate()` por workspace, si `context.workspaceState.get('specbox.onboardingDecision') === undefined`, la extensión llama `vscode.window.showInformationMessage` con message localizado y EXACTAMENTE 2 botones: el primero `vscode.l10n.t("Sign in with GitHub")`, el segundo `vscode.l10n.t("Continue in local mode (FreeForm)")`. NO existe un tercer botón "Dismiss"/"Later" — la X del corner del notification cierra sin elegir y eso NO persiste decisión (volverá a aparecer en próximo activate).
- [ ] **AC-02** [JE-Fus_vscode_github_oauth.2]: Si el usuario hace click en "Continue in local mode (FreeForm)", la extensión escribe `context.workspaceState.update('specbox.onboardingDecision', {mode: 'freeform', timestamp: ISO, ext_version: '...'})`. En el siguiente activate del mismo workspace, el notification NO se muestra. Verificable: reload workspace × 3, el notification aparece solo en el primer activate.
- [ ] **AC-03** [JR-Fus_vscode_github_oauth.3]: Al elegir "Continue in local mode (FreeForm)", la extensión ejecuta el equivalente a `set_auth_token(backend_type="freeform", token="", root_path=<absolute>)` resolviendo `root_path` vía el helper existente `.claude/hooks/lib/freeform-path.mjs` (defensa v5.29). El sidebar muestra "Local mode (FreeForm)" sin status bar de identidad.
- [ ] **AC-04** [JE-Fus_vscode_github_oauth.2]: Aún en modo FreeForm, el comando `SpecBox: Sign in with GitHub` permanece disponible en el Command Palette (no oculto). Pero NO aparecen notifications proactivas como "consider signing in" en ningún momento. Test: simular 10 días de uso en modo FreeForm con activates diarios → 0 notifications de auth aparecen.
- [ ] **AC-05** [JE-Fus_vscode_github_oauth.2]: Si el usuario cierra la X del notification sin elegir (decisión ambigua), la extensión registra el evento en telemetría local `.quality/logs/onboarding.jsonl` como `{event: "dismissed_without_decision", workspace_hash: sha256, ext_version}` pero NO cambia `workspaceState`. En el próximo activate vuelve a aparecer. Justificación: la ambigüedad de "cierre lateral" no se trata como opt-out — fuerza una decisión explícita.

---

### UC-648: `UNAUTHENTICATED` graceful en las 4 tools nativas

- **Actor**: Engine (MCP server, `server/coordination/`)
- **Pantallas**: ninguna
- **Estado**: backlog

#### Descripción
Auditar y unificar el comportamiento de `whoami`, `reserve_uc`, `release_uc`, `register_native_branch` cuando no hay token o el token es inválido. Hoy en `server/coordination/identity.py` algunos paths levantan excepciones (`UnauthorizedError`) que se propagan como MCP errors `isError=true` con stack trace. Debe ser uniforme: retornar un payload `{status: "unauthenticated", code: "UNAUTHENTICATED", message: "Sign in with GitHub via the VSCode extension or run /onboard.", docs_url: "https://github.com/EmbedBuild/specbox-engine#native-backend"}` sin levantar excepción. FreeForm/Trello/Plane no se ven afectados (no usan `authenticate_and_authorize_cached`).

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fus_vscode_github_oauth.5]: Las 4 tools (`whoami`, `reserve_uc`, `release_uc`, `register_native_branch`) cuando se invocan sin `SPECBOX_NATIVE_MCP_TOKEN` set retornan el payload de error JSON arriba descrito con `code="UNAUTHENTICATED"` y MCP `isError=true`. Test: crear MCP session sin auth token + invocar cada tool + assertar exact shape del payload + assertar que NO hay stack trace en el `message`.
- [ ] **AC-02** [JR-Fus_vscode_github_oauth.5]: Si el token es válido pero el `mcp_tokens.revoked_at IS NOT NULL` en Supabase, las mismas 4 tools retornan `code="UNAUTHENTICATED"` con `message="Your session was revoked. Sign in again."` después de ≤30s (cubierto por TTL del cache). Test: revocar token en BD, esperar 31s, invocar tool, assertar el message exacto.
- [ ] **AC-03** [JR-Fus_vscode_github_oauth.5]: Las tools NO-nativas (`onboard_project`, `add_uc`, `mark_ac`, `list_us`, `complete_uc`, etc. — todas las que operan sobre FreeForm/Trello/Plane) NO requieren `SPECBOX_NATIVE_MCP_TOKEN`. Test: invocar 20 tools no-nativas en sesión sin auth, assert todas retornan `isError=false`.
- [ ] **AC-04** [JR-Fus_vscode_github_oauth.5]: El comportamiento `UNAUTHENTICATED` graceful está cubierto por test `tests/test_native_unauthenticated.py` con al menos 8 casos: (a) cada una de las 4 tools sin token, (b) cada una de las 4 tools con token revocado post-30s. Suite verde en CI.
- [ ] **AC-05** [JE-Fus_vscode_github_oauth.1]: El `message` en el payload `UNAUTHENTICATED` está localizado server-side (i18n del server, no de la ext) usando un mecanismo similar al `vscode.l10n.t` de la ext: el cliente MCP envía `Accept-Language` header en el handshake, el server responde con el message en EN o ES según corresponda. Test: 2 sesiones MCP con `Accept-Language: en` y `Accept-Language: es`, mismo error, distinto `message`.

---

### UC-649: UI en sidebar de la extensión — "Signed in as @user" + comando "Sign out"

- **Actor**: Engine (VSCode extension)
- **Pantallas**: sidebar `specbox.status` (existente, se extiende)
- **Estado**: backlog

#### Descripción
La vista `specbox.status` del sidebar (creada en US-VSCODE-MARKETPLACE) muestra hoy una lista de checks (`Engine`, `Engine Path`, `Node.js`, `Python`, `Claude Code`, `Engram`, etc.). Esta US añade en la cabecera de esa vista el bloque de identidad: **"Signed in as @<github_handle>"** con icono `$(github-inverted)` si hay token activo; **"Not signed in (FreeForm mode)"** con icono `$(person)` si no. Click en el bloque abre acciones contextuales: `SpecBox: Sign out` (si signed in) o `SpecBox: Sign in with GitHub` (si no).

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fus_vscode_github_oauth.6]: La vista `specbox.status` añade un primer elemento (top of tree) que muestra el estado de identidad. Si hay `mcp_token` en SecretStorage Y `whoami()` retorna OK, el label es `"Signed in as @<handle>"`. Si no, label es `"Not signed in (FreeForm mode)"`. Test: VSCode test runner activa la ext con/sin token mockeado y assert el TreeItem.label correcto.
- [ ] **AC-02** [JR-Fus_vscode_github_oauth.6]: Click en el TreeItem signed-in despliega quick pick con 2 acciones: `vscode.l10n.t("Sign out")` (ejecuta `SpecBox: Sign out`) y `vscode.l10n.t("Open profile on cloud.specbox.build")` (abre browser a `cloud.specbox.build/me`). Click en el TreeItem not-signed-in despliega quick pick con 1 acción: `vscode.l10n.t("Sign in with GitHub")`.
- [ ] **AC-03** [JE-Fus_vscode_github_oauth.3]: La vista hace polling discreto cada 60s para detectar revoke: re-invoca `whoami()` desde el MCP local, y si pasa de OK a UNAUTHENTICATED, actualiza el TreeItem y muestra `vscode.l10n.t("Your session was revoked. Sign in again?")` como notification con CTA. Test: mock `whoami` returning OK→UNAUTHENTICATED, assert que en ≤90s (60s polling + margen) la UI se actualiza.
- [ ] **AC-04** [JR-Fus_vscode_github_oauth.6]: El status bar de VSCode (área inferior) muestra `$(github-inverted) @<handle>` cuando signed-in, sin nada cuando no. Click en el status bar = `vscode.commands.executeCommand('specbox.showStatus')` (ya existe). Test: render del status bar con/sin token, assert texto e icono.
- [ ] **AC-05** [JE-Fus_vscode_github_oauth.1]: Tanto el sidebar como el status bar respetan locale: con `code --locale=es`, el label es `"Conectado como @<handle>"` / `"Sin conexión (modo local FreeForm)"`. Cubierto por `package.nls.es.json` extended (claves nuevas) + `bundle.l10n.es.json` extended. Smoke test workflow de UC-640 (matrix locale en/es) extendido para verificar también los nuevos labels.

---

### UC-650: Tests de integración E2E del flow loopback OAuth (Supabase test mode)

- **Actor**: Engine (CI + test infrastructure)
- **Pantallas**: ninguna
- **Estado**: backlog

#### Descripción
Suite de tests E2E que cubre el flow completo desde el click "Sign in with GitHub" hasta el handshake con el MCP server. Usa Supabase test mode (proyecto `specbox-cloud-test` con su propia GitHub OAuth App de test) para ejercitar el flow real sin tocar producción. El test corre en CI vía un workflow nuevo `.github/workflows/oauth-e2e.yml` con runtime ubuntu-latest, xvfb + Playwright para automatizar el browser, y un mock GitHub OAuth para CI determinístico (alternativa: usar Supabase test mode con cuenta GitHub de servicio CI).

#### Acceptance Criteria
- [ ] **AC-01** [JR-Fus_vscode_github_oauth.4]: Test `tests/e2e/oauth-flow.spec.ts` con Playwright: (a) lanza VSCode + ext, (b) ejecuta comando "Sign in with GitHub", (c) intercepta el `openExternal` y dispara Playwright contra `cloud.specbox.build-test/auth/github`, (d) Playwright completa el GitHub mock OAuth, (e) callback llega al loopback, (f) verifica `context.secrets.get('specbox.mcpToken')` retorna un valor non-null. Test corre en `<60s`.
- [ ] **AC-02** [JR-Fus_vscode_github_oauth.4]: Test `tests/e2e/oauth-flow.spec.ts::reject_csrf` verifica que un callback con `state` distinto al enviado falla con HTTP 400 desde el loopback y NO actualiza SecretStorage. Defense in depth contra CSRF.
- [ ] **AC-03** [JR-Fus_vscode_github_oauth.4]: Test `tests/e2e/oauth-flow.spec.ts::timeout_5min` simula que el callback nunca llega (mock GitHub que no redirect), verifica que el server loopback se cierra en 5min + 30s margen, y la extension muestra notification de cancelación.
- [ ] **AC-04** [JE-Fus_vscode_github_oauth.3]: Test `tests/e2e/oauth-flow.spec.ts::revoke_visible_in_30s` integration: completa OAuth → invoca `whoami()` exitoso → revoca `mcp_tokens.revoked_at = now()` en Supabase test DB → espera 35s → invoca `whoami()` nuevamente → assert que retorna UNAUTHENTICATED.
- [ ] **AC-05** [JR-Fus_vscode_github_oauth.5]: Test `tests/e2e/oauth-flow.spec.ts::freeform_unaffected` verifica que en una sesión sin sign-in, todas las tools FreeForm/Trello/Plane funcionan normalmente (`onboard_project`, `add_uc`, `mark_ac`, `list_us`). Suite verde en CI.
- [ ] **AC-06** [JR-Fus_vscode_github_oauth.4]: Workflow CI `.github/workflows/oauth-e2e.yml` corre en cada PR con touch en `vscode-extension/src/{onboard,mcp,sidebar}.ts` o `server/coordination/identity.py`. Job en ubuntu-latest, xvfb, Playwright pinned, Supabase test mode credentials desde GitHub Secrets (`SPECBOX_TEST_SUPABASE_URL`, `SPECBOX_TEST_SUPABASE_ANON_KEY`). Falla con issue auto-created si rompe (siguiendo patrón de UC-640).

---

### UC-651: Docs + README + CHANGELOG + ADR — onboarding default = Native+OAuth

- **Actor**: Engine
- **Pantallas**: ninguna
- **Estado**: backlog

#### Descripción
Actualizar la documentación user-facing y el ADR para reflejar que el default del onboarding pasa de FreeForm a Native+OAuth (con FreeForm como escape preservado). Concretamente: `vscode-extension/README.md` y `README.es.md` (sección Quick Start), `vscode-extension/CHANGELOG.md` (entry [6.3.0]), `README.md` raíz, `docs/getting-started.md`, `doc/decisions/native_default_oauth.md` (ADR nuevo con el tradeoff documentado del discovery), `templates/settings.json.template` (override default a Native con comment apuntando al runbook FreeForm), y `CLAUDE.md` (sección "Native Default OAuth (v6.3.0)").

#### Acceptance Criteria
- [ ] **AC-01** [JE-Fus_vscode_github_oauth.1]: `vscode-extension/README.md` Quick Start reescrito: paso 1 sigue siendo "Install from Marketplace", paso 2 ahora es "Click 'Sign in with GitHub' on first activate (or 'Continue in local mode (FreeForm)' if preferred)", paso 3 es "Start building" (igual que antes). Sin mención a "provisionar token manualmente". `README.es.md` simétrico.
- [ ] **AC-02** [JR-Fus_vscode_github_oauth.3]: El README incluye sección explícita **"Local mode (no auth)"** con 3 líneas explicando que FreeForm sigue siendo un first-class citizen, link al runbook `doc/runbooks/freeform-only-mode.md` (nuevo), y aclaración de que las features no-Native funcionan idénticamente sin signing in. Visible en TOC del README, NO en footer.
- [ ] **AC-03** [JR-Fus_vscode_github_oauth.6]: `vscode-extension/CHANGELOG.md` entry `[6.3.0] - 2026-XX-XX` con sección "Added": GitHub OAuth onboarding, Native Backend como default, sidebar identity bloque. Sección "Changed": `templates/settings.json.template` default `backend_type=native`. Sección "Security": SecretStorage para mcp_token, ≤30s revoke visibility.
- [ ] **AC-04** [JE-Fus_vscode_github_oauth.2]: `doc/decisions/native_default_oauth.md` (ADR nuevo) replica el tradeoff documentado del discovery: rompe parcialmente la decisión canónica v5.29 "FreeForm first-class, cero auth requerida" pero compensa con las 3 garantías auditables (FreeForm visible, no-Native sin OAuth, opt-out persistente). El ADR linkea al discovery `icp_jtbd.md` y al Engram `architecture/vscode-github-oauth`. Test: existe el archivo y `grep -c "documented_exception" doc/decisions/native_default_oauth.md` ≥ 1.
- [ ] **AC-05** [JE-Fus_vscode_github_oauth.2]: `CLAUDE.md` añade sección "Native Default OAuth (v6.3.0)" con la nueva default + el escape FreeForm + link al ADR. La sección 6.1.1 Cloud Cutover (que removió Sala de Máquinas) sigue intacta — esta US es complementaria, no contradice. Test manual: leer CLAUDE.md tras el merge y verificar coherencia narrativa (no hay "FreeForm first-class" + "Native default" contradictoriamente).

---

## Interacciones UI

> Esta sección alimenta el análisis de componentes en /plan. La US extiende UI existente.

### Visualización de datos

| Dato | Volumen | Atributos visibles | Acciones por item |
|------|---------|-------------------|-------------------|
| Identity (sidebar header) | 1 | `@handle` + icono github / "Not signed in" + icono person | Click → quick pick |
| Status bar identity | 1 | `@handle` + icono github (solo si signed-in) | Click → showStatus |

### Acciones del usuario

| Acción | UC asociado | Frecuencia | Criticidad | Requiere confirmación |
|--------|-------------|------------|------------|----------------------|
| Sign in with GitHub | UC-647, UC-644 | One-shot por workspace | Media (modifica estado de auth) | No (es opt-in explícito por click) |
| Continue in local mode (FreeForm) | UC-647 | One-shot por workspace | Baja (no requiere reverse) | No |
| Sign out | UC-646 | Raro | Media (cierra sesión, no destructivo) | No (reversible con re-signin) |
| Open profile on cloud.specbox.build | UC-649 | Raro | Nula | No |

### Selecciones/Filtros

No aplica (no hay filtros nuevos en sidebar).

### Formularios

No aplica (no hay formularios nuevos — el browser de GitHub gestiona el form OAuth).

---

## Audiencia (heredada del discovery)

> Discovery validado: [doc/discovery/us_vscode_github_oauth/icp_jtbd.md](../discovery/us_vscode_github_oauth/icp_jtbd.md)

### Targets de la US

- **ICP-2 (Dev solo con Claude Code que adopta SpecBox)** — primario. Touchpoint nuevo: Marketplace install. JTBD principal: arrancar en <60s sin tocar tokens.
- **ICP-1 (Owner-operator JPS, dogfooding)** — early adopter de su propia feature + valida el path de escape FreeForm para conservar el top of funnel.
- **ICP-3 (Equipo/agencia)** — fuera de scope esta US, no afectado.

### JTBDs racionales mapeados a ACs

- **JR-Fus_vscode_github_oauth.1** (< 60s sin tokens) → UC-644 AC-01, UC-646 AC-01-03, UC-647 AC-01
- **JR-Fus_vscode_github_oauth.2** (OAuth indistinguible de SaaS) → UC-644 AC-01-04, UC-645 AC-01-02
- **JR-Fus_vscode_github_oauth.3** (escape FreeForm visible) → UC-647 AC-03, UC-651 AC-02
- **JR-Fus_vscode_github_oauth.4** (revoke ≤30s) → UC-645 AC-03-05, UC-646 AC-04, UC-650 AC-01-06
- **JR-Fus_vscode_github_oauth.5** (no-OAuth para FreeForm/Trello/Plane) → UC-648 AC-01-04, UC-650 AC-05
- **JR-Fus_vscode_github_oauth.6** (telemetría growth) → UC-645 AC-06, UC-649 AC-01-04

### JTBDs emocionales mapeados a ACs

- **JE-Fus_vscode_github_oauth.1** ("no quiero ser sysadmin") → UC-644 AC-03-04, UC-646 AC-02-05, UC-648 AC-05, UC-651 AC-01
- **JE-Fus_vscode_github_oauth.2** (opt-out persistente respetado) → UC-647 AC-02-05, UC-651 AC-02, UC-651 AC-04
- **JE-Fus_vscode_github_oauth.3** (revoke confiable) → UC-644 AC-05, UC-646 AC-04, UC-649 AC-03, UC-650 AC-04

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Latencia OAuth flow | Tiempo desde click "Sign in" hasta status bar "Signed in as @handle" < 30s en conexión 4G estándar | E2E test con `performance.now()` en VSCode + log timestamp `auth_log` |
| Seguridad token storage | mcp_token nunca en plaintext en filesystem accessible al user (incluyendo `.vscode/`, `.claude/`, dotfiles globales) | `grep -r "<token>" $HOME` retorna 0 matches post-signin (test E2E) |
| Seguridad transport | OAuth callback solo en `127.0.0.1`, nunca `0.0.0.0`. Endpoint cloud rechaza redirect_uri no-loopback | Test `curl` con `redirect_uri=https://evil.com` retorna 400 |
| Revoke responsiveness | Tiempo desde `mcp_tokens.revoked_at = now()` hasta `whoami()` returns UNAUTHENTICATED ≤ 30s | Test E2E UC-650 AC-04 |
| Offline resiliencia FreeForm | Con conexión desactivada y sin sign-in previo, comandos FreeForm/Trello/Plane funcionan idénticamente | Test manual + UC-650 AC-05 |
| i18n consistencia | Todos los strings nuevos (notification, sidebar, quick picks) localizados EN + ES; parity de keys | `tests/test_l10n_parity.py` extendido |
| Backwards compat | Usuarios v6.2.0 sin sign-in mantienen su flujo FreeForm sin cambios al upgrade a v6.3.0 | Migration test: workspace con `.claude/settings.local.json` v6.2 abre en v6.3 sin promptear OAuth si `backend_type=freeform` ya está |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| **Microsoft rechaza la ext v6.3 por loopback HTTP server** (clasificación "extension que escucha en localhost") | Baja | Alto | El patrón loopback OAuth es ampliamente usado (Cursor, Continue.dev, GitHub Copilot Chat). La review del Marketplace lo permite. Si pasa: workaround con `vscode.env.asExternalUri` y polling de Supabase. |
| **Browser flow `cloud.specbox.build/vscode/issue-token` aún no existe** (depende de US paralela en specbox_cloud) | Media | Alto | El repo `EmbedBuild/specbox_cloud` está clonado en el workspace (`/Users/.../embed.build/repositorios/specbox_cloud`) y la US paralela `US-AUTH-VSCODE-SELF-SERVICE-TOKEN` se crea en este mismo flow. Coordinación cross-repo: ambos PRs progresan en paralelo, UC-650 (E2E test) sirve de gate de integración. Riesgo recalculado a la baja porque la infraestructura base (Supabase Auth, mcpTokens.ts, auth.ts plugin) ya está en producción y testeada. |
| **GitHub OAuth App rate limiting** (50K req/hora por app) | Muy baja | Bajo | Es un onboarding one-shot por usuario. Saturar 50K req/h implicaría 50K signups en 1h, problema deseable. |
| **VSCode SecretStorage API tiene comportamiento inconsistente entre plataformas** (especialmente en Linux sin libsecret) | Media | Medio | Fallback: si SecretStorage falla al store, mostrar error claro y caer a modo FreeForm. Test específico en Linux runner sin libsecret en CI. |
| **Supabase Auth signInWithIdToken cambia API entre versiones** | Baja | Medio | Pin Supabase SDK version en cloud.specbox.build. Smoke test en cada release del cloud. |
| **Usuario con múltiples cuentas GitHub se confunde sobre cuál usó** | Media | Bajo | El sidebar muestra `@handle` siempre visible. UC-649 AC-04. |
| **Polling cada 60s del whoami consume MCP calls innecesariamente** | Baja | Bajo | UC-649 AC-03 puede degradar a polling-on-focus-change (re-check solo cuando VSCode recibe foco). Decisión a tomar en /plan. |
| **El loopback en Windows con firewall puede pedir permiso UAC** | Media | Bajo | Loopback puerto random no requiere abrir port en firewall (es localhost). Si falla, fallback documentado en runbook. |

---

## Stack Técnico (estimado)

- **VSCode extension** (specbox-engine): TypeScript en `vscode-extension/src/`, nuevos módulos:
  - `oauth.ts` — loopback server + flow management (apuntando a `cloud.specbox.build/vscode/issue-token`, NO a endpoints OAuth directos)
  - `secrets.ts` — wrapper sobre `context.secrets`
  - `sidebar-identity.ts` — extensión de la vista existente `views/status-tree.ts`
- **MCP server** (specbox-engine): Python (existente en `server/coordination/identity.py`). Cambios menores: unificar errores a `UNAUTHENTICATED` payload + añadir `Accept-Language` handling.
- **Cross-repo (specbox_cloud)** — US paralela US-AUTH-VSCODE-SELF-SERVICE-TOKEN:
  - **`apps/api`** (Fastify 5 + jose + Supabase JS + Vitest): nuevo endpoint `POST /api/mcp-tokens/issue-for-self` en `apps/api/src/routes/mcpTokensSelfService.ts`. Reusa el plugin auth.ts existente (JWT JWKS + cache 30s), reusa `issueMcpToken()` de `lib/tokens.ts`. Tests Vitest en `mcpTokensSelfService.test.ts`.
  - **`apps/web`** (Vite + React + Supabase JS): nueva ruta `src/routes/vscode/issue-token.tsx` que dispara `supabase.auth.signInWithOAuth({provider: 'github'})` si no hay sesión + llama al endpoint nuevo + redirige a `return_to`. Tests Playwright en `tests/e2e/vscode-issue-token.spec.ts`.
- **Tests E2E cross-repo** (UC-650): Playwright + `@vscode/test-electron` + Supabase test mode (proyecto separado en Supabase con su propia GitHub OAuth App para CI). El workflow `oauth-e2e.yml` corre matrix: (a) test desde extensión consumiendo cloud-test, (b) test desde web mockeando GitHub OAuth.

## Archivos Principales

```
vscode-extension/
├── src/
│   ├── oauth.ts                          # NEW
│   ├── secrets.ts                        # NEW
│   ├── sidebar-identity.ts               # NEW
│   ├── extension.ts                      # MOD (activate handler + notification)
│   ├── mcp.ts                            # MOD (handshake con SPECBOX_NATIVE_MCP_TOKEN)
│   ├── onboard.ts                        # MOD (integra con OAuth flow)
│   └── views/
│       └── status-tree.ts                # MOD (identity en top of tree)
├── package.nls.json                      # MOD (claves nuevas)
├── package.nls.es.json                   # MOD (idem ES)
├── l10n/bundle.l10n.json                 # MOD (nuevas strings runtime)
├── l10n/bundle.l10n.es.json              # MOD (idem ES)
├── README.md                             # MOD (Quick Start + Local mode section)
├── README.es.md                          # MOD (idem ES)
└── CHANGELOG.md                          # MOD (entry [6.3.0])

server/
├── coordination/
│   └── identity.py                       # MOD (unificar errores UNAUTHENTICATED + i18n)
└── tools/
    └── coordination.py                   # MOD (Accept-Language handling)

tests/
├── e2e/
│   └── oauth-flow.spec.ts                # NEW (Playwright + @vscode/test-electron)
├── test_native_unauthenticated.py        # NEW (UNAUTHENTICATED graceful en 4 tools)
└── test_l10n_parity.py                   # MOD (claves nuevas)

.github/workflows/
└── oauth-e2e.yml                         # NEW (CI workflow para tests E2E)

doc/
├── decisions/
│   └── native_default_oauth.md           # NEW (ADR del tradeoff v5.29)
├── runbooks/
│   ├── freeform-only-mode.md             # NEW (guía explícita modo local)
│   └── github-oauth-troubleshooting.md   # NEW
└── prd/
    └── US-VSCODE-GITHUB-OAUTH_prd.md     # ESTE ARCHIVO

templates/
└── settings.json.template                # MOD (default backend_type=native + comment hacia FreeForm)

CLAUDE.md                                 # MOD (sección "Native Default OAuth (v6.3.0)")
```

## Dependencias cross-repo (no externas — workspace local)

- **`EmbedBuild/specbox_cloud`** (clonado en `~/Desktop/Proyectos/0_jps_iautomat/embed.build/repositorios/specbox_cloud`): implementar la US paralela **US-AUTH-VSCODE-SELF-SERVICE-TOKEN** que crea:
  - `POST /api/mcp-tokens/issue-for-self` en `apps/api/src/routes/` — endpoint Fastify que un developer autenticado por JWT (NO requireSuperAdmin) puede llamar para emitirse a sí mismo un mcp_token con `name="vscode-<hostname>"`. Reusa `issueMcpToken()` de `lib/tokens.ts`.
  - `apps/web/src/routes/vscode/issue-token.tsx` — página Vite/React que: (1) detecta si hay sesión Supabase activa, (2) si no, dispara `supabase.auth.signInWithOAuth({provider: 'github'})` preservando `return_to`+`state`, (3) llama al endpoint nuevo, (4) redirige a `return_to?mcp_token=<clear>&state=<csrf>`.
  - Validation suite Vitest (apps/api) + Playwright (apps/web).
- **GitHub OAuth App de Supabase**: YA EXISTE y está configurado en el Supabase project del cloud (Supabase Auth nativo gestiona GitHub OAuth; no se reimplementa).
- **Tablas Supabase**: `developers`, `github_identities`, `mcp_tokens`, `panel.profiles`, `audit_log` YA EXISTEN en producción y están testeadas. No requieren migrations nuevas en v6.3.0.
- **Supabase test project**: provisionar `specbox-cloud-test` (o reusar staging existente) para CI con GitHub OAuth App de test separada. Documentado en UC-650 AC-06.

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

- [ ] **AC-01** [JR-2]: Loopback server en 127.0.0.1 puerto random, abre browser <1s (UC-644 AC-01)
- [ ] **AC-02** [JR-2]: Callback valida CSRF state, single-use, segunda request 410 (UC-644 AC-02)
- [ ] **AC-03** [JE-1]: Timeout 5min cierra server + notification i18n (UC-644 AC-03)
- [ ] **AC-04** [JR-2]: Página HTML callback con auto-close + i18n (UC-644 AC-04)
- [ ] **AC-05** [JE-3]: Loopback rechaza requests cross-origin / non-GET (UC-644 AC-05)
- [ ] **AC-06** [JR-2]: Endpoint cloud valida redirect_uri regex loopback (UC-645 AC-01)
- [ ] **AC-07** [JR-2]: Endpoint redirige a GitHub OAuth con scopes correctos, client_secret en env (UC-645 AC-02)
- [ ] **AC-08** [JR-6]: Upsert transaccional en developers/github_identities/mcp_tokens (UC-645 AC-03)
- [ ] **AC-09** [JE-3]: mcp_token = 64-hex random, stored como sha256, never plaintext en logs (UC-645 AC-04)
- [ ] **AC-10** [JR-4]: Multi-device — re-signin no invalida tokens existentes (UC-645 AC-05)
- [ ] **AC-11** [JR-4]: Telemetría auth_log con event sign_in + ip_hash (UC-645 AC-06)
- [ ] **AC-12** [JR-1]: mcp_token en SecretStorage Keychain/DPAPI/libsecret (UC-646 AC-01)
- [ ] **AC-13** [JE-1]: Cero plaintext del token en filesystem accessible al user (UC-646 AC-02)
- [ ] **AC-14** [JR-1]: MCP server auto-authenticates desde env var al spawn (UC-646 AC-03)
- [ ] **AC-15** [JE-3]: Revoke visible en ≤30s vía TTL cache existente (UC-646 AC-04)
- [ ] **AC-16** [JE-1]: Sign out borra SecretStorage + respawn MCP sin token (UC-646 AC-05)
- [ ] **AC-17** [JR-1]: Notification al primer activate, 2 botones equivalentes en jerarquía (UC-647 AC-01)
- [ ] **AC-18** [JE-2]: workspaceState persiste decisión, no se vuelve a mostrar (UC-647 AC-02)
- [ ] **AC-19** [JR-3]: FreeForm escape ejecuta set_auth_token con root_path absoluto (UC-647 AC-03)
- [ ] **AC-20** [JE-2]: En modo FreeForm cero notifications proactivas de auth tras opt-out (UC-647 AC-04)
- [ ] **AC-21** [JE-2]: Cierre lateral del notification NO persiste decisión, vuelve a aparecer (UC-647 AC-05)
- [ ] **AC-22** [JR-5]: 4 tools nativas retornan UNAUTHENTICATED payload uniforme sin stack trace (UC-648 AC-01)
- [ ] **AC-23** [JR-5]: Token revocado retorna UNAUTHENTICATED en ≤30s (UC-648 AC-02)
- [ ] **AC-24** [JR-5]: Tools no-nativas (20 verificadas) funcionan sin auth (UC-648 AC-03)
- [ ] **AC-25** [JR-5]: Suite test_native_unauthenticated.py con ≥8 casos cubre el contrato (UC-648 AC-04)
- [ ] **AC-26** [JE-1]: UNAUTHENTICATED message respeta Accept-Language (EN/ES) (UC-648 AC-05)
- [ ] **AC-27** [JR-6]: Sidebar muestra "Signed in as @handle" o "Not signed in (FreeForm mode)" (UC-649 AC-01)
- [ ] **AC-28** [JR-6]: Quick pick con acciones contextuales según estado (UC-649 AC-02)
- [ ] **AC-29** [JE-3]: Polling 60s detecta revoke y muestra notification (UC-649 AC-03)
- [ ] **AC-30** [JR-6]: Status bar identity con github-inverted icon (UC-649 AC-04)
- [ ] **AC-31** [JE-1]: Sidebar + status bar respetan locale ES (UC-649 AC-05)
- [ ] **AC-32** [JR-4]: E2E test Playwright cubre el happy path <60s (UC-650 AC-01)
- [ ] **AC-33** [JR-4]: E2E test reject_csrf con state mismatch (UC-650 AC-02)
- [ ] **AC-34** [JR-4]: E2E test timeout_5min con server auto-close (UC-650 AC-03)
- [ ] **AC-35** [JE-3]: E2E test revoke_visible_in_30s integration con Supabase (UC-650 AC-04)
- [ ] **AC-36** [JR-5]: E2E test freeform_unaffected verifica 4+ tools no-nativas operan sin auth (UC-650 AC-05)
- [ ] **AC-37** [JR-4]: Workflow oauth-e2e.yml en CI con xvfb + Playwright + Supabase test mode (UC-650 AC-06)
- [ ] **AC-38** [JE-1]: README Quick Start sin "provisionar token manualmente" (UC-651 AC-01)
- [ ] **AC-39** [JR-3]: README sección explícita "Local mode (no auth)" con link al runbook (UC-651 AC-02)
- [ ] **AC-40** [JR-6]: CHANGELOG entry [6.3.0] con Added/Changed/Security (UC-651 AC-03)
- [ ] **AC-41** [JE-2]: ADR doc/decisions/native_default_oauth.md replica tradeoff documented_exception (UC-651 AC-04)
- [ ] **AC-42** [JE-2]: CLAUDE.md sección "Native Default OAuth (v6.3.0)" coherente con secciones existentes (UC-651 AC-05)

### Técnicos (no validados por AG-09)

- [ ] Proyecto compila sin errores: `tsc -p ./` en vscode-extension/ + `uv run pytest tests/` en server
- [ ] Tests con 85%+ coverage en `tests/test_native_unauthenticated.py` + `tests/e2e/oauth-flow.spec.ts`
- [ ] Linter de strings hardcoded (UC-642 v6.2.0) sigue pasando con allowlist actualizada si aplica
- [ ] Sync de versión engine ↔ extension (UC-634 v6.2.0) pasa con v6.3.0 bumpeado en ambos sitios
- [ ] Workflow CI publish-vscode-extension.yml (UC-638 v6.2.0) tagea v6.3.0 sin drift
- [ ] Workflow CI smoke-test-marketplace.yml (UC-640 v6.2.0) corre matrix locale [en, es] verde
- [ ] Workflow CI nuevo oauth-e2e.yml pasa en cada PR que toca paths relevantes

---

## Tradeoff aceptado (replicado del discovery, será ADR en /plan)

**La US rompe parcialmente la decisión canónica v5.29 "FreeForm first-class, cero auth requerida"** introduciendo Native+OAuth como recomendado en el onboarding default.

Está **explícitamente aceptado** por el owner (Engram `architecture/vscode-github-oauth` #5746) condicionado a estas 3 garantías auditables:

1. **FreeForm permanece como escape visible y técnicamente equivalente** — UC-647 AC-01, UC-651 AC-02.
2. **Las tools no-nativas (FreeForm/Trello/Plane) NO requieren OAuth** — UC-648 AC-03, UC-650 AC-05.
3. **El opt-out es persistente** — UC-647 AC-02, UC-647 AC-04.

El ADR completo se redactará en `/plan US-VSCODE-GITHUB-OAUTH` (UC-651 AC-04) materializando esto en `doc/decisions/native_default_oauth.md`.

---

**Prioridad**: high
**Complejidad**: Alta (involucra extensión + cloud endpoint + Supabase + CI nuevo)
*Generado: 2026-05-27 por `/prd` v6.0.1*
