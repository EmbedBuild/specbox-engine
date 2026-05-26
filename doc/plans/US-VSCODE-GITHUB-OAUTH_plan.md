# Plan: US-VSCODE-GITHUB-OAUTH — Onboarding con GitHub OAuth (Native default + FreeForm escape)

> Generado: 2026-05-27 por `/plan`
> Origen: FreeForm board `ff-ed0c02f4565a` | US-VSCODE-GITHUB-OAUTH
> Discovery: [doc/discovery/us_vscode_github_oauth/icp_jtbd.md](../discovery/us_vscode_github_oauth/icp_jtbd.md) — verdict READY_FOR_PRD
> PRD: [doc/prd/US-VSCODE-GITHUB-OAUTH_prd.md](../prd/US-VSCODE-GITHUB-OAUTH_prd.md)
> Release target: v6.3.0 "Native Default OAuth"
> Estado: pendiente de `/implement`

## Resumen

Este plan materializa los **8 UCs** del lado consumidor de la US (UC-644…UC-651) en una secuencia de fases ordenada por dependencias técnicas. La US es cross-repo con `EmbedBuild/specbox_cloud` (US-09 paralela en otra sesión), pero el contrato cross-repo está congelado en 2 puntos (URL del browser flow + shape del callback), así que **este plan puede ejecutarse independiente** mientras el cloud avanza en paralelo. El gate de integración es UC-650 (E2E test) que valida ambos lados juntos.

VEG **desactivado**: la US extiende UI existente (sidebar `specbox.status` creado en US-VSCODE-MARKETPLACE), sin pantallas nuevas. Reuso de iconos VSCode codicon (`$(github-inverted)`, `$(person)`) y NLS bundles existentes.

## Análisis UI (Fase 0)

| Requisito | Componente | Existe | Ubicación | Acción |
|---|---|---|---|---|
| Identity item en top of status tree | `IdentityTreeItem` (subclass de `StatusItem`) | ❌ | `vscode-extension/src/views/status-tree.ts` | CREAR — añadir al inicio de `getChildren()` de `StatusTreeProvider` |
| Status bar identity (right side) | `IdentityStatusBarItem` | ❌ | `vscode-extension/src/statusbar.ts` (extender) | EXTENDER el `StatusBarManager` existente con segundo item |
| Quick pick context menu | nativo `vscode.window.showQuickPick` | ✅ | API VSCode | Reutilizar |
| Notification `showInformationMessage` | nativo | ✅ | API VSCode | Reutilizar (ya usado en `extension.ts:71`) |
| Loopback HTTP server | módulo `node:http` | ✅ | stdlib Node | Reutilizar |
| Generación CSRF token random hex | `crypto.randomBytes` | ✅ | stdlib Node | Reutilizar |
| SecretStorage wrapper | `context.secrets.store/get/delete` | ✅ | API VSCode 1.86+ | Reutilizar (engines.vscode ya está en ^1.86.0 desde UC-642) |

**Widgets a crear**: 1 (`IdentityTreeItem`). Trivial — herencia de `vscode.TreeItem`.

## Decisiones canónicas heredadas (Paso 0.0)

| Decisión | Valor heredado | Aplicación al plan |
|---|---|---|
| Stack engine | Python 3.12 (FastMCP) + TypeScript (extension) | Tools nativas en Python (UC-648), todo lo demás TypeScript |
| Backend tracking | FreeForm `ff-ed0c02f4565a` | UC tracking + ACs ya importadas; el plan no cambia tracking |
| Autopilot (real, en `.claude/settings.local.json`) | agresivo | Implementación puede auto-confirmar gates no-inviolables. Inviolables se respetan (`destructive_action`, `branch_to_main_push`) |
| Convenciones | PR-only a main, lint via GGA, README bump por release, ES neutral sin argentinismos | Plan respeta. README/CHANGELOG bumps en UC-651 |
| VEG | Uniforme/Startup canónico | **No aplica** — US sin pantallas |
| i18n existente (US-MARKETPLACE v6.2.0) | `package.nls.{json,es.json}` + `l10n/bundle.l10n.{json,es.json}` + linter `scripts/lint-extension-strings.mjs` con allowlist | Plan EXTIENDE ambos bundles con keys nuevas (UC-647, UC-649). Linter sigue con la misma allowlist (install/mcp/onboard/updater en pending) |
| SecretStorage requirement | VSCode ≥1.86 (engines.vscode ya bumpeado en UC-642) | Sin bump adicional |

**Drift detectado y NO arreglado en este plan**: `doc/app/app_spec.md` declara `autopilot.level=equilibrado`, pero `.claude/settings.local.json` real está en `agresivo`. Cosmético, no bloquea. Se sincroniza con `/app-sync --refresh` cuando se quiera (fuera de scope).

**Drift detectado en el board y NO arreglado**: la `description` de US-VSCODE-GITHUB-OAUTH en `items.json` todavía menciona `cloud.specbox.build/auth/github` (modelo antiguo, anterior al hallazgo cross-repo). `update_us` retorna `US_NOT_FOUND` aunque `get_us` lo encuentra — probable bug del MCP. El PRD ya tiene el modelo correcto y es source of truth. Anotado como follow-up para `/app-sync` o re-import futuro.

---

## Dependencias entre UCs

Grafo de dependencias técnicas (no temporales — algunas paralelizables):

```
                    ┌──────────────────────────────────────┐
                    │ UC-648 (UNAUTHENTICATED graceful)    │
                    │ MCP server-side, INDEPENDIENTE       │
                    │ Puede arrancar primero               │
                    └──────────────────────────────────────┘

  ┌── UC-644 (loopback OAuth server) ───────┐
  │   foundational, sin deps                │
  └────┬────────────────────────────────────┘
       │
       ├──→ UC-645 (consumir browser flow del cloud)
       │     └─ depende del contrato URL del cloud (US-09 cross-repo)
       │       pero solo de URL+shape, no de implementación
       │
       └──→ UC-646 (SecretStorage + handshake MCP)
              └─ depende de tener un mcp_token válido (recibido en UC-644)

  ┌── UC-647 (notification onboarding) ─────┐
  │   depende de UC-644+645+646 funcionando │
  │   para que el CTA "Sign in" sea real    │
  └────┬────────────────────────────────────┘
       │
       └──→ UC-649 (sidebar identity UI)
              └─ depende de UC-646 (lee SecretStorage) + UC-648 (whoami sin error)

  ┌── UC-650 (E2E tests cross-repo) ────────┐
  │   gate de integración                   │
  │   depende de UC-644..649 + US-09 cloud  │
  └─────────────────────────────────────────┘

  ┌── UC-651 (docs + ADR + CHANGELOG) ──────┐
  │   últimos                               │
  └─────────────────────────────────────────┘
```

**Camino crítico**: UC-644 → UC-645 → UC-646 → UC-649. UC-647 es paralelo a 645+646 (solo necesita 644 listo). UC-648 es independiente y puede ejecutarse en paralelo a todo. UC-650 cierra. UC-651 cierra.

**Cross-repo gate**: UC-650 AC-01..05 requieren que la US-09 del cloud esté en producción para correr E2E reales. Mientras tanto, los tests pueden correr contra un **mock loopback target** (servidor de prueba en `localhost:9999/vscode/issue-token` que simula el cloud) para desbloquear desarrollo del engine.

---

## Fases de Implementación

Total: 8 UCs en **5 fases**. Cada fase es checkpoint natural de implementación.

### Fase 1 — Server-side independiente (UC-648)

**Objetivo**: el MCP server retorna `UNAUTHENTICATED` graceful uniforme. Es independiente del lado de la extensión, puede ejecutarse antes que todo lo demás.

#### UC-648 — `UNAUTHENTICATED` graceful en 4 tools nativas [AG-01 + AG-04 tests]

- [ ] Auditar `server/coordination/identity.py`: hoy `UnauthenticatedError` se levanta como excepción en `resolve_developer`. Las 4 tools nativas (`whoami`, `reserve_uc`, `release_uc`, `register_native_branch`) propagan la excepción → MCP envelope `isError=true` con stack trace.
- [ ] Auditar `server/tools/coordination.py`: capturar `UnauthenticatedError` en cada tool wrapper y retornar payload uniforme `{status: "unauthenticated", code: "UNAUTHENTICATED", message: "...", docs_url: "https://github.com/EmbedBuild/specbox-engine#native-backend"}`. Sin stack trace.
- [ ] Implementar `Accept-Language` handling server-side:
    - Pequeño módulo `server/coordination/i18n_messages.py` con dict `{lang: {code: message}}`. Solo `en` (default) y `es`.
    - Las tools leen `req.headers.get("Accept-Language", "en")` (FastMCP/Starlette context) y eligen mensaje.
    - Fallback a `en` si locale no soportado.
- [ ] Token revocado: cuando `mcp_tokens.revoked_at IS NOT NULL`, `resolve_developer` ya retorna `UnauthenticatedError` después del TTL del cache (`authenticate_and_authorize_cached` línea 397, `_CACHE_TTL_SECONDS = 30`). Garantía AC-02 ya está en infra existente, solo verificar con test.
- [ ] Tests nuevos en `tests/test_native_unauthenticated.py`:
    - 8 casos mínimos por AC-04: 4 tools × {sin token, token revocado post-30s}.
    - Test parity i18n: misma tool, distinto `Accept-Language` → distinto `message`.
    - Test: tools no-nativas (`add_uc`, `mark_ac`, `list_us`, `onboard_project`) NO requieren token, retornan `isError=false`.
- **Archivos creados**: `tests/test_native_unauthenticated.py`, `server/coordination/i18n_messages.py`
- **Archivos modificados**: `server/coordination/identity.py` (cambios menores en logging), `server/tools/coordination.py` (4 wrappers)
- **AC coverage**: AC-01 → AC-05 del PRD UC-648
- **Estado de partida**: `authenticate_and_authorize_cached` y `_CACHE_TTL_SECONDS=30` YA existen en `identity.py:397`. Plan reusa.

### Fase 2 — Foundation extensión (UC-644)

**Objetivo**: loopback HTTP server efímero funcional. Sin OAuth real todavía (mock target).

#### UC-644 — Loopback OAuth server efímero [AG-01]

- [ ] Crear `vscode-extension/src/oauth.ts`:
    - Función `startLoopbackServer(): Promise<{port: number, awaitCallback: Promise<CallbackResult>, close: () => void}>`.
    - Usa `node:http.createServer` con `listen(0, '127.0.0.1')` (puerto random asignado por SO, loopback-only).
    - Acepta exactamente UNA request a `/callback`. Segunda request → 410 Gone.
    - Valida `Origin` header: solo permite si está vacío (browser default) o matchea `https://cloud.specbox.build`. Rechaza otros con 400.
    - Methods: solo GET. Otros → 400.
    - Page HTML del callback exitoso: título + texto + style inline + `window.close()` auto. Strings localizados via `vscode.l10n.t`.
    - Timeout 5min via `setTimeout` que cierra el server automáticamente si callback no llega.
    - Genera CSRF state como `crypto.randomBytes(32).toString('hex')` (64-hex).
- [ ] Crear comando `specbox.signIn` en `package.json` + handler en `extension.ts`:
    - Llama `startLoopbackServer()`, obtiene puerto.
    - Construye URL: `https://cloud.specbox.build/vscode/issue-token?return_to=<URI-encoded-loopback>&state=<csrf>`.
    - `vscode.env.openExternal(vscode.Uri.parse(url))`.
    - Espera promise del callback con timeout.
    - Si exitoso: pasa `mcp_token` a UC-646 (SecretStorage + handshake).
    - Si timeout/error: notification con CTA "Try again" / "Continue in local mode".
- [ ] Tests unit en `vscode-extension/src/test/oauth.test.ts` (o `tests/oauth.test.ts` adyacente, según convención del proyecto):
    - Test: server escucha en 127.0.0.1, NUNCA en 0.0.0.0 (verificable con `server.address()`).
    - Test: segunda request a `/callback` → 410.
    - Test: state mismatch → 400.
    - Test: timer mock 5min01s → server cerrado + notification disparada.
    - Test: request con `Origin: https://evil.com` → 400.
    - Test: method POST → 400.
- **Archivos creados**: `vscode-extension/src/oauth.ts`, `vscode-extension/src/test/oauth.test.ts`
- **Archivos modificados**: `vscode-extension/src/extension.ts` (registrar comando), `vscode-extension/package.json` (declarar comando + l10n keys), `vscode-extension/package.nls.{json,es.json}` (label "Sign in with GitHub"), `vscode-extension/l10n/bundle.l10n.{json,es.json}` (mensajes runtime)
- **AC coverage**: AC-01 → AC-05 del PRD UC-644

### Fase 3 — Bridge cloud + persistencia (UC-645, UC-646)

**Objetivo**: el token recibido del browser flow se valida y se persiste. MCP server local pasa a usar el token automáticamente.

#### UC-645 — Consumir browser flow del cloud [AG-01]

- [ ] El consumidor es trivial: el shape del callback ya está definido en AC-02 del PRD (`?mcp_token=<64-hex>&state=<csrf>` para success, `?error=<code>&error_description=<msg>&state=<csrf>` para failure).
- [ ] En `oauth.ts::startLoopbackServer`, el handler del `/callback`:
    - Parsea query params.
    - Si presente `error`: resuelve la promise con `{ok: false, error, description, state}`.
    - Si presente `mcp_token`: valida regex `^[a-f0-9]{64}$` + state matchea → resuelve con `{ok: true, token, state}`. Si regex falla → 400.
    - El validation de state vs el enviado lo hace el caller (`extension.ts` handler de `specbox.signIn`).
- [ ] Tras recibir token válido en `signIn`: llamar `whoami()` al MCP local con env var temporal injectada (NO en SecretStorage todavía) para validar que el token funciona end-to-end con el cloud → si OK, persiste (UC-646); si retorna UNAUTHENTICATED u otro error → notification "Sign in failed" sin persistir.
- [ ] **NO** la extensión llama `POST /api/mcp-tokens/issue-for-self` directamente. **NO** la extensión gestiona JWT Supabase. Test verificable: `grep -r "Authorization: Bearer\|supabase.auth\|/api/mcp-tokens" vscode-extension/src/` debe retornar 0 matches.
- [ ] Documentación de la sección en `vscode-extension/README.md` (que se materializa en UC-651) referencia explícitamente la US-09 del cloud.
- **Archivos modificados**: `vscode-extension/src/oauth.ts` (callback handler), `vscode-extension/src/extension.ts` (validation de respuesta + flow), `vscode-extension/src/mcp.ts` (handshake helper que pasa env var temp para validar antes de persistir)
- **AC coverage**: AC-01 → AC-06 del PRD UC-645
- **Cross-repo gate**: la implementación real depende de US-09 del cloud para tests E2E. Sin US-09, este UC se valida contra un mock server local que simula el browser flow (parte de UC-650 setup).

#### UC-646 — VSCode SecretStorage + handshake con MCP server local [AG-01]

- [ ] Crear `vscode-extension/src/secrets.ts`:
    - Wrapper minimal sobre `context.secrets.store/get/delete` con key constante `SPECBOX_SECRET_KEY = 'specbox.mcpToken'`.
    - `getToken()`, `storeToken(t)`, `deleteToken()`.
- [ ] Configurar MCP env var injection. Aquí hay 2 opciones técnicas — **decisión**:
    - **Opción A** (recomendada por simplicidad y seguridad): la extensión escribe `claude.mcpServers.specbox-engine.env` en `.vscode/settings.json` del workspace usando `vscode.workspace.getConfiguration().update()`. El valor de `env.SPECBOX_NATIVE_MCP_TOKEN` se setea **directamente al plaintext** del token. Esto VIOLA AC-02 ("zero plaintext en filesystem").
    - **Opción B**: la extensión escribe un valor placeholder `${env:SPECBOX_NATIVE_MCP_TOKEN_FROM_SECRETSTORAGE}` y configura un **proceso wrapper** (`vscode-extension/bin/mcp-launcher.mjs`) que VSCode invoca como `command`. El wrapper lee el token de SecretStorage via API y lo expone como env al MCP server real. **Esto SÍ cumple AC-02**.
    - **Decisión del plan**: **Opción B**. Justificación: AC-02 es explícito sobre cero plaintext. La implementación cuesta ~50 líneas extra de wrapper pero la garantía es real, no nominal.
- [ ] Crear `vscode-extension/bin/mcp-launcher.mjs`:
    - Lee `SPECBOX_SECRET_KEY` mediante un canal seguro hacia la extensión (ya existe el pattern de `vscode.commands.executeCommand` para invocar comandos internos).
    - Spawn del proceso MCP real (`specbox-engine` binario del engine) con env extendida.
- [ ] Modificar `vscode-extension/src/mcp.ts`:
    - Función `updateMcpServerConfigWithToken(token: string)` que llama el launcher pattern.
    - Función `clearMcpServerConfig()` para sign-out.
    - Función `respawnMcpServer()` que mata el proceso actual y lo relanza (vía `vscode.commands.executeCommand('claude.mcpRestart', 'specbox-engine')` o equivalente — verificar API exacta de Claude extension en runtime).
- [ ] Comando `specbox.signOut`: borra SecretStorage + clearMcpServerConfig + respawn + actualiza sidebar.
- [ ] Logging local en `.quality/logs/mcp-handshake.jsonl` con shape `{event: "auto_authenticated", developer_handle: "<handle>", timestamp: ISO}`. **NO** logea el token plaintext. El `developer_handle` se obtiene del primer `whoami()` post-spawn.
- [ ] Tests:
    - Unit: SecretStorage wrapper (mock VSCode API).
    - Integration: handshake completo (token en SecretStorage → wrapper → MCP spawn → whoami OK).
    - Negative: SecretStorage delete + respawn → MCP responde UNAUTHENTICATED.
    - Cross-platform: smoke test contra Keychain (macOS local), libsecret stub (Linux CI).
- **Archivos creados**: `vscode-extension/src/secrets.ts`, `vscode-extension/bin/mcp-launcher.mjs`, `vscode-extension/src/test/secrets.test.ts`
- **Archivos modificados**: `vscode-extension/src/mcp.ts` (handshake helpers), `vscode-extension/src/extension.ts` (registrar `specbox.signOut`), `vscode-extension/package.json` (declarar comando)
- **AC coverage**: AC-01 → AC-05 del PRD UC-646
- **Riesgo**: la opción B requiere validar que VSCode + Claude extension permite invocar un wrapper como `command` para spawn del MCP. Si el shape exacto no existe, fallback a opción A con TODO explícito en CHANGELOG documentando la limitación de seguridad. La validación se hace en spike de 1h antes de empezar UC-646 real.

### Fase 4 — Onboarding UX + Identity UI (UC-647, UC-649)

**Objetivo**: el flow completo es descubrible y persistente. Sidebar muestra estado real de identidad.

#### UC-647 — Onboarding notification al primer activate [AG-01]

- [ ] Modificar `vscode-extension/src/extension.ts` función `activate`:
    - Tras los checks existentes (engine installed, etc.), añadir gate de onboarding decision:
        ```typescript
        const decision = context.workspaceState.get<OnboardingDecision>('specbox.onboardingDecision');
        if (!decision) {
            await showOnboardingNotification(context);
        }
        ```
- [ ] Nueva función `showOnboardingNotification(context)`:
    - Llama `vscode.window.showInformationMessage` con exactamente 2 botones: `vscode.l10n.t("Sign in with GitHub")` y `vscode.l10n.t("Continue in local mode (FreeForm)")`. **NO** un tercero "Dismiss".
    - Si user click "Sign in with GitHub" → llama comando `specbox.signIn` (UC-644). Persiste `{mode: 'native', timestamp, ext_version}` en `workspaceState`.
    - Si user click "Continue in local mode (FreeForm)" → llama UC-647 AC-03 path: setea backend a freeform via mecanismo equivalente a `set_auth_token(backend_type="freeform", root_path=<absolute>)`. La ruta absoluta se resuelve con el helper `.claude/hooks/lib/freeform-path.mjs` (defensa v5.29) — la extensión escribe en `.claude/settings.local.json` el `specbox.backend_type=freeform` + `freeform_root_absolute=<abs>`. Persiste `{mode: 'freeform', timestamp, ext_version}` en `workspaceState`.
    - Si user cierra la X (notification dismissed sin elegir): **NO** persistir. Loguear evento en `.quality/logs/onboarding.jsonl` con `{event: "dismissed_without_decision", workspace_hash: sha256(folder_uri), ext_version}`. Próximo activate vuelve a mostrar.
- [ ] **NO** notifications proactivas posteriores. Verificable por test: simular 10 activates en modo FreeForm post-decisión → 0 calls a `showInformationMessage` con CTAs de auth.
- [ ] El comando `specbox.signIn` permanece disponible en Command Palette siempre — aunque el usuario haya elegido FreeForm.
- [ ] i18n keys nuevos en `package.nls.{json,es.json}`:
    - `onboarding.notification.message`
    - `onboarding.notification.signIn`
    - `onboarding.notification.continueLocal`
- [ ] Tests:
    - Unit: gate de decisión (con/sin workspaceState).
    - Test integration: 3 reloads de workspace post-FreeForm → notification aparece solo una vez.
    - Test: cierre X sin elegir → próximo activate la notification reaparece.
- **Archivos creados**: ninguno (solo modificaciones).
- **Archivos modificados**: `vscode-extension/src/extension.ts` (nueva función + gate), `vscode-extension/package.nls.{json,es.json}` (3 keys), `vscode-extension/l10n/bundle.l10n.{json,es.json}` (mensajes runtime si los hay), `vscode-extension/src/test/onboarding.test.ts` (nuevo)
- **AC coverage**: AC-01 → AC-05 del PRD UC-647
- **Follow-up linter**: `install.ts`/`mcp.ts`/`onboard.ts`/`updater.ts` siguen en allowlist del linter desde UC-642. Esta US NO los re-trabaja (sigue siendo deuda). Si el plan termina tocando `mcp.ts` (UC-646 lo hace) o `onboard.ts` (UC-647 lo evita por estar fuera del activate flow), revisar si el linter ahora bloquea — si bloquea, refactor parcial in-place + remover del allowlist.

#### UC-649 — Sidebar identity UI + comando "Sign out" [AG-01]

- [ ] Modificar `vscode-extension/src/views/status-tree.ts`:
    - Añadir nuevo método `getIdentityItem()` que retorna un `StatusItem` (o subclass `IdentityTreeItem`) con label dinámico:
        - Si `secrets.getToken()` returns non-null AND `health.whoami()` returns OK: `"Signed in as @<handle>"` con icono `$(github-inverted)`.
        - Si no: `"Not signed in (FreeForm mode)"` con icono `$(person)`.
    - `getChildren()` devuelve `[getIdentityItem(), ...existingItems]` (identity siempre primero).
    - `IdentityTreeItem` tiene `command: { command: 'specbox.identityQuickPick', title: '' }` para abrir quick pick al click.
- [ ] Nuevo comando `specbox.identityQuickPick`:
    - Si signed in: quick pick con `["Sign out", "Open profile on cloud.specbox.build"]`.
    - Si not signed in: quick pick con `["Sign in with GitHub"]`.
- [ ] Extender `vscode-extension/src/statusbar.ts`:
    - Añadir segundo `StatusBarItem` (right alignment) que muestra `$(github-inverted) @<handle>` si signed in, oculto si no.
    - Click → `vscode.commands.executeCommand('specbox.showStatus')` (comando ya existe desde US-MARKETPLACE).
- [ ] Polling discreto de revoke:
    - En `extension.ts::activate`, registrar un `setInterval` de 60s que llama `health.whoami()` y actualiza el sidebar si el estado cambió de OK → UNAUTHENTICATED.
    - Cleanup en `deactivate` con `clearInterval`.
    - Si cambio detectado: actualizar TreeView (`statusTree.refresh()`) + mostrar notification con CTA "Sign in again".
- [ ] i18n keys nuevos:
    - `identity.signedInAs` (con placeholder `{0}` para el handle)
    - `identity.notSignedIn`
    - `identity.signOut`
    - `identity.openProfile`
    - `identity.revokedNotification` (mensaje + CTA)
- [ ] Tests:
    - Unit: `IdentityTreeItem` con `signedIn` true/false produce label correcto.
    - Integration: SecretStorage tiene token + whoami mockeado OK → label "Signed in as @handle".
    - Integration: revoke simulado (whoami mockeado pasa de OK a UNAUTHENTICATED) → tras polling, TreeItem se actualiza.
    - Locale: render con `vscode.l10n.t` y locale=es → labels en español.
- **Archivos creados**: `vscode-extension/src/test/identity-ui.test.ts`
- **Archivos modificados**: `vscode-extension/src/views/status-tree.ts`, `vscode-extension/src/statusbar.ts`, `vscode-extension/src/extension.ts` (registrar comando + setInterval polling), `vscode-extension/package.json` (declarar comando), `vscode-extension/package.nls.{json,es.json}`, `vscode-extension/l10n/bundle.l10n.{json,es.json}`
- **AC coverage**: AC-01 → AC-05 del PRD UC-649

### Fase 5 — Tests E2E + Docs (UC-650, UC-651)

**Objetivo**: gate de integración cross-repo + documentación user-facing.

#### UC-650 — Tests E2E del flow loopback OAuth [AG-04 QA]

- [ ] Crear `.github/workflows/oauth-e2e.yml`:
    - Trigger: PRs con touch en `vscode-extension/src/{oauth,secrets,mcp,extension}.ts` o `server/coordination/identity.py`.
    - Runtime: ubuntu-latest + xvfb + Node 20 + Python 3.12.
    - Setup: install Playwright, `@vscode/test-electron`, secrets de Supabase test mode (`SPECBOX_TEST_SUPABASE_URL`, `SPECBOX_TEST_SUPABASE_ANON_KEY`) — añadir secrets al repo cuando exista la US-09 del cloud.
    - Steps: build extensión (`npm run vscode:prepublish`), run E2E suite, upload artifacts (logs + screenshots).
- [ ] Crear `tests/e2e/oauth-flow.spec.ts`:
    - Test `happy_path`: lanza VSCode + ext, ejecuta `specbox.signIn`, intercepta `openExternal` con Playwright spy, lanza Playwright contra `cloud.specbox.build-test/vscode/issue-token`, completa el GitHub mock OAuth, valida callback al loopback, valida `context.secrets.get('specbox.mcpToken')` non-null. <60s.
    - Test `reject_csrf`: callback con state mismatch → no actualiza SecretStorage.
    - Test `timeout_5min`: mock GitHub que nunca redirige → server cerrado + notification.
    - Test `revoke_visible_in_30s`: tras sign-in OK, revoca `mcp_tokens.revoked_at` en Supabase test → espera 35s → `whoami()` retorna UNAUTHENTICATED.
    - Test `freeform_unaffected`: sin sign-in, 4 tools no-nativas funcionan (`onboard_project`, `add_uc`, `mark_ac`, `list_us`).
- [ ] Fail handler: `report-failure` job que abre issue auto con label `oauth-e2e-fail` (siguiendo patrón de `smoke-test-marketplace.yml`).
- [ ] **Mock cross-repo durante desarrollo**: hasta que US-09 del cloud esté en producción, se usa un mock server local en `tests/e2e/mock-cloud-server.ts` que sirve `vscode/issue-token` con el shape del callback definido en UC-645 AC-02. Esto permite que toda la suite E2E corra sin esperar a la US del cloud. Cuando US-09 esté disponible, se añade un test extra que apunta a `cloud-test.specbox.build` real.
- **Archivos creados**: `.github/workflows/oauth-e2e.yml`, `tests/e2e/oauth-flow.spec.ts`, `tests/e2e/mock-cloud-server.ts`, `tests/e2e/playwright.config.ts` (si no existe)
- **Archivos modificados**: `vscode-extension/package.json` (devDependencies: `@playwright/test`, `@vscode/test-electron`)
- **AC coverage**: AC-01 → AC-06 del PRD UC-650

#### UC-651 — Docs + README + CHANGELOG + ADR [AG-01]

- [ ] Reescribir `vscode-extension/README.md` Quick Start:
    - Paso 1 "Install from Marketplace" (sin cambios desde v6.2.0).
    - **Paso 2 NUEVO**: "Click 'Sign in with GitHub' on first activate (or 'Continue in local mode (FreeForm)' if preferred)".
    - Paso 3 "Start building" (sin cambios).
    - Quitar cualquier mención a "provisionar token manualmente".
- [ ] Añadir sección **"Local mode (no auth)"** explícita en `vscode-extension/README.md`:
    - 3 líneas explicando que FreeForm sigue first-class.
    - Link al nuevo runbook `doc/runbooks/freeform-only-mode.md`.
    - Aclaración: features no-Native funcionan idénticamente sin signing in.
    - Visible en el TOC (no en footer).
- [ ] Añadir sección **"How sign-in works under the hood"** en `vscode-extension/README.md`:
    - Diagrama secuencia (texto) del flow loopback + cloud.
    - Link a la US-09 del cloud (`EmbedBuild/specbox_cloud`).
    - Mencionar SecretStorage, ≤30s revoke, opt-out persistente.
- [ ] Crear `vscode-extension/README.es.md` simétrico (español neutro España).
- [ ] Crear `doc/runbooks/freeform-only-mode.md`:
    - Cómo arrancar en modo FreeForm explícitamente.
    - Qué features funcionan sin auth.
    - Cómo volver atrás a Native si cambias de opinión (`SpecBox: Sign in with GitHub` desde Command Palette).
- [ ] Crear `doc/runbooks/github-oauth-troubleshooting.md`:
    - Errores comunes del flow (callback timeout, browser bloqueó popup, network, etc.).
    - Cómo verificar SecretStorage on each platform.
    - Cómo forzar sign-out manual.
- [ ] Crear `doc/decisions/native_default_oauth.md` (ADR):
    - Replica el tradeoff del discovery: rompe parcialmente decisión canónica v5.29.
    - 3 garantías auditables (ya documentadas en discovery `Drift from app_market`).
    - Links a Engram `architecture/vscode-github-oauth #5746`, al discovery `icp_jtbd.md`, al PRD.
    - Sección "Resolución": `documented_exception`.
- [ ] Actualizar `vscode-extension/CHANGELOG.md` con entry `[6.3.0] - 2026-XX-XX`:
    - **Added**: GitHub OAuth onboarding, Native default, sidebar identity bloque.
    - **Changed**: default backend en `templates/settings.json.template` pasa a `native`.
    - **Security**: SecretStorage para mcp_token, ≤30s revoke visibility.
- [ ] Actualizar `CLAUDE.md` del engine: nueva sección "Native Default OAuth (v6.3.0)" con la nueva default + escape FreeForm + link al ADR. NO contradice la sección "Cloud Cutover (v6.1.0)" — son complementarias.
- [ ] Actualizar `templates/settings.json.template`: si la US lo decide finalmente, cambiar `backend_type=native` como default + comentario apuntando al runbook FreeForm. **Decisión pendiente**: ¿el default canónico de proyectos NUEVOS cambia a `native`? El PRD del discovery dice sí; verificar con el owner antes de mergear (puede ser desconvertirá adopción FreeForm legacy).
- **Archivos creados**: `vscode-extension/README.es.md` (si no existía ya — verificar), `doc/runbooks/freeform-only-mode.md`, `doc/runbooks/github-oauth-troubleshooting.md`, `doc/decisions/native_default_oauth.md`
- **Archivos modificados**: `vscode-extension/README.md`, `vscode-extension/CHANGELOG.md`, `CLAUDE.md`, posiblemente `templates/settings.json.template`
- **AC coverage**: AC-01 → AC-05 del PRD UC-651

---

## Comandos Finales (verificación cross-UC)

Tras completar los 5 fases:

```bash
# Compilación + lint
cd vscode-extension && npm install && npm run vscode:prepublish
# → exit 0, sin warnings TS

node scripts/lint-extension-strings.mjs
# → 7 OK (extension.ts, health.ts, oauth.ts, secrets.ts, statusbar.ts, status-tree.ts, etc.), 4 en allowlist (install/mcp/onboard/updater) — UC-646 modifica mcp.ts pero solo las nuevas funciones (sin strings literales)

# Sync versión (UC-634 + UC-635 del v6.2.0)
bash scripts/sync-extension-version.sh --check
# → exit 0 si engine v6.3.0 == ext v6.3.0 (asegurar bump antes del release)

# Tests Python
uv run pytest tests/test_native_unauthenticated.py -v
# → 8+ passed

# Tests TS unit
cd vscode-extension && npm test
# → suite completa pasa

# Tests E2E (con xvfb local o en CI)
cd vscode-extension && npm run test:e2e
# → 5 specs verdes contra mock-cloud-server o cloud-test

# vsce package
cd vscode-extension && npx vsce package
# → genera specbox-engine-6.3.0.vsix sin warnings
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|---|---|---|---|
| Token storage | SecretStorage + wrapper launcher (Opción B) | Env var directa con plaintext en `.vscode/settings.json` (Opción A) | Cumple AC-02 literalmente (cero plaintext en filesystem). 50 líneas extra de wrapper son aceptables vs garantía nominal vs real. |
| Cross-repo testing pre-cloud | Mock cloud server local en tests/e2e | Esperar a US-09 del cloud antes de empezar | Desbloquea desarrollo paralelo. Cuando US-09 esté listo, se añade test extra contra cloud-test real. |
| Comando "Sign in" | `specbox.signIn` (nuevo) | Reutilizar `specbox.onboard` existente | Separación de concerns. `onboard` sigue siendo el wizard completo; `signIn` es el flow OAuth standalone. |
| Polling whoami | `setInterval` 60s | Polling on-focus-change | Predecible. UI siempre fresca dentro de 60s + 30s TTL = ≤90s revoke visible. PRD lo permite. |
| i18n locale handling server-side (UC-648) | Module dict simple `i18n_messages.py` | Usar `gettext`/`Babel` proper | Solo 2 locales (en, es) y ~5 mensajes. Overhead de gettext no se justifica. |
| Default canónico en `templates/settings.json.template` | Cambiar a `backend_type=native` | Mantener `freeform` y proponer `native` solo en onboarding wizard | Coherente con el discovery: Native+OAuth recomendado es el nuevo default. Pero **requiere confirmación del owner antes de mergear** (decisión irreversible para nuevos proyectos onboarded post-v6.3.0). |

---

## Archivos a Crear/Modificar (consolidado)

```
specbox-engine/
├── scripts/                         (sin nuevos — los del v6.2.0 ya cubren sync/lint)
│
├── vscode-extension/
│   ├── package.json                                                MOD (UC-644/646/647/649: 2 comandos nuevos, l10n keys)
│   ├── package.nls.json / package.nls.es.json                      MOD (UC-647/649: ~5 keys nuevas)
│   ├── l10n/bundle.l10n.json / bundle.l10n.es.json                 MOD (UC-644/647/649: ~10 strings runtime)
│   ├── README.md / README.es.md                                    MOD (UC-651)
│   ├── CHANGELOG.md                                                MOD (UC-651 entry [6.3.0])
│   ├── bin/
│   │   └── mcp-launcher.mjs                                        CREAR (UC-646)
│   └── src/
│       ├── extension.ts                                            MOD (UC-644/647/649: comandos, gate onboarding, polling)
│       ├── oauth.ts                                                CREAR (UC-644/645)
│       ├── secrets.ts                                              CREAR (UC-646)
│       ├── mcp.ts                                                  MOD (UC-646: handshake helpers, respawn)
│       ├── statusbar.ts                                            MOD (UC-649: segundo item)
│       ├── views/
│       │   └── status-tree.ts                                      MOD (UC-649: IdentityTreeItem)
│       └── test/
│           ├── oauth.test.ts                                       CREAR (UC-644)
│           ├── secrets.test.ts                                     CREAR (UC-646)
│           ├── onboarding.test.ts                                  CREAR (UC-647)
│           └── identity-ui.test.ts                                 CREAR (UC-649)
│
├── server/
│   └── coordination/
│       ├── identity.py                                             MOD (UC-648: logging cleanup mínimo)
│       └── i18n_messages.py                                        CREAR (UC-648)
│
├── server/tools/
│   └── coordination.py                                             MOD (UC-648: 4 wrappers retornan payload uniforme)
│
├── tests/
│   ├── test_native_unauthenticated.py                              CREAR (UC-648)
│   └── e2e/
│       ├── oauth-flow.spec.ts                                      CREAR (UC-650)
│       ├── mock-cloud-server.ts                                    CREAR (UC-650)
│       └── playwright.config.ts                                    CREAR (UC-650)
│
├── .github/workflows/
│   └── oauth-e2e.yml                                               CREAR (UC-650)
│
├── doc/
│   ├── runbooks/
│   │   ├── freeform-only-mode.md                                   CREAR (UC-651)
│   │   └── github-oauth-troubleshooting.md                         CREAR (UC-651)
│   ├── decisions/
│   │   └── native_default_oauth.md                                 CREAR (UC-651)
│   └── plans/
│       └── US-VSCODE-GITHUB-OAUTH_plan.md                          ESTE ARCHIVO
│
├── templates/
│   └── settings.json.template                                      MOD (UC-651 — pendiente confirmación owner)
│
└── CLAUDE.md                                                       MOD (UC-651: sección "Native Default OAuth (v6.3.0)")
```

**Total**: 14 archivos creados, 13 archivos modificados.

---

## Mapeo a Agentes

| UC | Agente | Razón |
|---|---|---|
| UC-644 | AG-01 Feature Generator | Loopback TS + tests |
| UC-645 | AG-01 | Validación shape + flow |
| UC-646 | AG-01 + AG-03 (storage layer) | Wrapper SecretStorage + launcher |
| UC-647 | AG-01 | Edits a `extension.ts` + i18n |
| UC-648 | AG-01 + AG-03 (server-side coordination) | Python wrappers + i18n_messages |
| UC-649 | AG-01 + AG-02 (UI/UX para TreeView labels) | TreeView + statusbar |
| UC-650 | AG-04 QA Validation | E2E + workflow CI |
| UC-651 | AG-01 | Markdown + ADR |

AG-08 (quality auditor interno) corre automáticamente en `/implement`. AG-09a/b (acceptance) corren al cerrar cada UC.

---

## Pipeline Integrity Notes

- **Spec-guard**: cada UC requiere `start_uc` antes de tocar código en `vscode-extension/src/` o `server/coordination/`.
- **Branch-guard**: trabajo en rama `feature/US-VSCODE-GITHUB-OAUTH` (ya creada). NO push directo a main.
- **Pre-commit-lint**: GGA corre en cada commit; archivos `.ts` y `.py` modificados se validan.
- **No-bypass-guard**: bajo presión NO usar `--no-verify` ni `push --force`. Fix root cause.
- **Quality-first-guard**: cada UC debe `Read` archivos antes de editar (especialmente UC-646 sobre `mcp.ts`, UC-647 sobre `extension.ts`).
- **Stitch designs**: N/A (sin pantallas nuevas — Paso 6 saltado).

---

## Métricas de éxito post-implementación

Replicadas del PRD para tracking durante `/implement`:

- ✅ Tests `test_native_unauthenticated.py` con ≥8 casos verdes
- ✅ Tests TS unit (4 suites) verdes
- ✅ Workflow `oauth-e2e.yml` verde en CI (5 specs)
- ✅ Acceptance Engine: 42 ACs verdes (AG-09b ACCEPTED para los 8 UCs)
- ✅ Smoke test manual: instalar v6.3.0 en VSCode limpio, completar OAuth flow, ver "Signed in as @handle" en sidebar en <60s
- ✅ Smoke test manual modo FreeForm: instalar, click "Continue in local mode (FreeForm)", verificar 0 notifications de auth tras 10 reloads del workspace
- ✅ Linter strings: no nuevas violaciones (allowlist sigue siendo {install, mcp, onboard, updater})
- ✅ Sync version engine ↔ extension: `bash scripts/sync-extension-version.sh --check` exit 0

---

## Riesgos durante implementación

Replicados del PRD con énfasis en lo accionable durante `/implement`:

| Riesgo | UC afectado | Mitigación en /implement |
|---|---|---|
| US-09 del cloud no está lista cuando llegamos a UC-650 | UC-650 | El mock cloud server local desbloquea. AC-06 acepta test con mock. Test contra cloud-test real se añade cuando US-09 esté disponible. |
| Opción B del SecretStorage launcher es inviable en la API actual de VSCode/Claude extension | UC-646 | Spike 1h previo a UC-646. Si inviable, fallback a Opción A con TODO explícito en CHANGELOG documentando la limitación de seguridad. |
| `vscode.commands.executeCommand('claude.mcpRestart', ...)` no existe con ese nombre | UC-646 | Investigar API de la extensión Claude Code en runtime. Fallback: el usuario tiene que reload window manualmente tras sign-in/sign-out (degradación graceful). |
| Polling 60s genera ruido en MCP logs | UC-649 | AC-03 permite degradar a polling-on-focus-change. Decisión en `/implement` según observación de logs. |
| Cambio de `templates/settings.json.template` rompe proyectos legacy | UC-651 | Pendiente confirmación owner. Si rompe, mantener `freeform` como default y proponer `native` solo en onboarding wizard de la ext. |
| Microsoft rechaza extensión v6.3.0 por loopback HTTP server | UC-644 | Patrón ampliamente usado (Cursor, Continue.dev, Copilot Chat). Si pasa, workaround con `vscode.env.asExternalUri` + polling Supabase. |
| El usuario tiene un workspace con extensión v6.2.x + token manual ya provisionado | Backwards compat | Detectar en `activate`: si `SPECBOX_NATIVE_MCP_TOKEN` ya está en env (legacy provisioning), NO mostrar notification (decisión persistida implícitamente como "ya tiene credenciales"). |

---

## Coordinación cross-repo

| Concepto | specbox-engine (esta US) | EmbedBuild/specbox_cloud (US-09 paralela) |
|---|---|---|
| Branch | `feature/US-VSCODE-GITHUB-OAUTH` | `feature/US-09-vscode-self-service-token` |
| Contrato (URL del flow) | UC-645 AC-01 declara el shape | UC-902 implementa la página |
| Contrato (shape callback) | UC-645 AC-02 declara el shape | UC-902 implementa el redirect |
| Gate de integración | UC-650 (E2E con mock + opcionalmente cloud-test real) | UC-903 (tests Vitest + Playwright propios) |
| Ningún cambio invasivo cross | UC-644 no toca cloud | UC-901 no toca engine; reusa `lib/tokens.ts` interno |

Cuando US-09 del cloud esté en producción:
- Añadir secrets `SPECBOX_TEST_SUPABASE_URL` + `SPECBOX_TEST_SUPABASE_ANON_KEY` al repo `EmbedBuild/specbox-engine`.
- Habilitar matrix extra en `oauth-e2e.yml` que apunta a cloud-test real.

---

## Próximo paso

1. **Confirmar mientras tanto**: ¿el default de `templates/settings.json.template` cambia a `native`, o se mantiene `freeform` con `native` solo como recomendado en onboarding? (UC-651 último checkbox, pendiente decisión del owner).
2. **Cuando ambos repos tengan rama + PR**: ejecutar `/implement` en cualquiera de los dos lados. UC-648 puede arrancar primero (server-side, independiente). El orden recomendado del lado engine es Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5.
3. **Release**: tras los 8 UCs verdes + AG-09b ACCEPTED + US-09 del cloud lista, invocar `/release 6.3.0 "Native Default OAuth"`. El hook UC-635 del `/release` skill correrá el sync de versión engine ↔ extension automáticamente.

**Tiempo estimado**: NO incluido por preferencia del owner (estimaciones horarias inventadas no aportan valor predictivo). Orden por dependencias técnicas, no por horas.
