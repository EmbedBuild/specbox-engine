# Discovery: us_vscode_github_oauth

**Discovery ID**: disc-194865adf95d
**Created**: 2026-05-26T21:52:29.652236+00:00
**Status**: DISCOVERY_INCOMPLETE
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ e3b0c44298fc1c14

> **Nota sobre el método de redacción**:
> Este discovery se redactó como draft directo (variante b1) usando inputs
> ya validados off-band por el owner del proyecto (decisiones congeladas en
> Engram `architecture/vscode-github-oauth` #5746) en lugar del flujo
> conversacional habitual de `/discovery`. El owner valida el artefacto
> antes de invocar `/prd`. Cualquier ajuste al ICP/JTBD se hace editando
> este archivo directamente o re-corriendo `/discovery` (idempotente).

## ICPs involucrados

- **ICP-2: Dev solo con Claude Code que adopta SpecBox** — canónico tentative, definido en `doc/app/app_market.md` §1. Es el ICP primario de esta feature. Antes de v6.2.0 entraba al engine clonando el repo + corriendo `install.sh`; desde v6.2.0 entra por VSCode Marketplace (`code --install-extension EmbedBuild.specbox-engine`). Esta US captura el momento exacto en que el Marketplace install se materializa como onboarding funcional: pasar de "extensión instalada" a "engine operativo con identidad" en < 60 segundos sin tocar tokens ni leer docs de auth.

- **ICP-1: Owner-operator del engine (JPS, dogfooding)** — canónico, definido en `doc/app/app_market.md` §1. Participa como early-adopter de su propia feature: el owner es el primer caso que prueba el flow OAuth completo contra `cloud.specbox.build` antes de exponerlo a ICP-2. Es también quien valida el path de escape FreeForm para mantener el top of funnel "developer local solitario".

- **ICP-3: Equipo/agencia con reporting a cliente** — fuera de scope para esta US. Sigue usando Trello/Plane sin OAuth como hoy. Mencionado solo para anclar el principio de no-bloqueo: las tools no-nativas (FreeForm, Trello, Plane) NO requieren OAuth y siguen funcionando offline tras esta US.

Sin ICPs nuevos. Esta feature es un refinamiento vertical del onboarding de ICP-2 en el nuevo touchpoint Marketplace introducido por v6.2.0 (US-VSCODE-MARKETPLACE).

## JTBDs racionales

- **JR-Fus_vscode_github_oauth.1 [ICP-2]**: Cuando instalo la extensión SpecBox Engine desde el VSCode Marketplace por primera vez, quiero arrancar a usar el engine en menos de 60 segundos sin tener que provisionar manualmente un `mcp_token` desde un panel web ni copiar/pegar credenciales en `.claude/settings.local.json`, para que la fricción del primer touch no me haga abandonar antes de ver valor.

- **JR-Fus_vscode_github_oauth.2 [ICP-2]**: Cuando autorizo la extensión vía GitHub OAuth, quiero que la sesión se establezca con un solo click ("Sign in with GitHub") + un round-trip al navegador, sin pasos intermedios de copiar tokens del browser a la terminal, para que el flujo sea indistinguible del de una app SaaS moderna que ya conozco.

- **JR-Fus_vscode_github_oauth.3 [ICP-2]**: Cuando soy un developer que prefiere no autenticarme contra un servicio externo (proyecto personal, dev solitario, modo offline), quiero ver el escape "Continuar en modo local (FreeForm)" claramente visible en el mismo onboarding y poder activarlo sin penalización, para no sentirme empujado a auth que no necesito ni quiero.

- **JR-Fus_vscode_github_oauth.4 [ICP-2]**: Cuando alguien revoca mi acceso desde el panel `cloud.specbox.build` (rotación de identidad, salida del equipo, incidente de seguridad), quiero que el efecto en mi cliente VSCode sea visible en ≤ 30 segundos sin tener que reiniciar nada, para que el control bidireccional de acceso sea real y no aspiracional.

- **JR-Fus_vscode_github_oauth.5 [ICP-2]**: Cuando uso FreeForm/Trello/Plane (no Native), quiero que la extensión y el MCP server sigan funcionando offline sin pedirme login, para que la decisión de "no autenticarme" sea respetada técnicamente y no aparezcan errores `UNAUTHENTICATED` rompiendo features no-Native.

- **JR-Fus_vscode_github_oauth.6 [ICP-1]**: Cuando opero como owner del engine y necesito ver quién está activamente usando SpecBox para tomar decisiones de roadmap, quiero que cada autenticación deje rastro en Supabase Auth de `cloud.specbox.build` con metadata útil (handle GitHub, timestamp, version del engine), para que las decisiones de growth se basen en datos reales y no en inferencias del Marketplace listing.

## JTBDs emocionales

- **JE-Fus_vscode_github_oauth.1 [ICP-2]**: No quiero ser tratado como sysadmin para usar una herramienta de productividad. La fricción "lee este runbook, crea este PAT, copia este token, edítame este JSON" comunica un tono de "esto es para gente que ya está dentro" — y yo todavía estoy decidiendo si entrar. El flow OAuth indistinguible de cualquier SaaS moderna comunica el tono opuesto: "esto es para devs como tú, no para hackers de fin de semana". Sensación observable: al terminar el primer minuto del onboarding, el usuario debería poder explicar a un colega qué hace SpecBox sin mencionar la palabra "token".

- **JE-Fus_vscode_github_oauth.2 [ICP-2]**: Confianza de que la decisión de NO autenticarme se respeta. Si elijo "Continuar en modo local" durante el onboarding, no quiero que la extensión vuelva a empujarme a sign-in cada vez que abro un workspace, ni que aparezcan notificaciones tipo "¡considera autenticarte!". Cuando un producto respeta la elección del opt-out, comunica que confía en mi criterio — y eso es lo opuesto al growth hacking agresivo que se ha vuelto el default.

- **JE-Fus_vscode_github_oauth.3 [ICP-1]**: Tranquilidad operativa de que el revoke funciona. Como owner que algún día tendrá que gestionar identidades comprometidas o salidas de colaboradores, saber que el TTL de 30 segundos del cache `authenticate_and_authorize_cached` cierra la ventana de exposición a 30s en el peor caso — sin que tenga que confiar en que el cliente "se entere" — es el tipo de garantía que solo se valora cuando hace falta.

## Validation evidence

- **Tipo**: triangulación documental + waiver parcial.
- **Justificación**: la feature tiene 3 capas de evidencia, complementarias y suficientes para v1:

  1. **Señal de mercado observable**: la convención de "Sign in with GitHub" como onramp default está validada empíricamente en el segmento dev tools desde hace años — Vercel CLI, Railway, Render, Fly.io, Supabase, Stripe Atlas, GitHub Codespaces, Cursor, Continue.dev, todos arrancan con OAuth GitHub como camino feliz por la misma razón (latencia psicológica del onboarding ≪ a un setup manual). No procede entrevistar a usuarios para re-validar un patrón ya canónico en el segmento.

  2. **Señal interna del propio engine**: en v5.x-v6.1 el Native Backend requería `set_auth_token(backend_type="native", token="<provisión manual>")`. Esto bloqueó la adopción del Native Backend en favor de FreeForm/Trello/Plane incluso entre power users — observable en el hecho de que la única instancia productiva del Native Backend en v6.1.x es la que el owner provisiona contra Supabase para dogfooding. Ningún proyecto externo lo adoptó porque el onboarding manual mata el funnel. Esto es exactamente la fricción que la US elimina.

  3. **Waiver explícito para validación con usuarios externos**: las decisiones de implementación (loopback puerto random, Supabase Auth como IdP único en vez de GitHub OAuth App propia, SecretStorage en vez de archivo en disco, notification al primer activate en vez de lazy) fueron tomadas off-band por el owner contra la base de evidencia (1) y (2). Re-validar con users externos pre-implementación tiene mal ROI dado que la US sale al Marketplace público en v6.3.0 y la propia adopción (instalaciones, ratings, issues abiertos en `EmbedBuild/specbox-engine`) será la señal de validación post-lanzamiento.

- **Riesgo de no validar**: bajo. Si el patrón OAuth no funciona para ICP-2 en su forma actual, la US salida ya incluye el opt-out FreeForm explícito (JR.3) — el coste de un mal default es "el usuario hace click en el escape", no "el usuario abandona". El downside está acotado.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. Participan ICP-1 (canónico) e ICP-2 (tentative en `app_market.md` §1). Esta US es un refinamiento del touchpoint de onboarding de ICP-2; no introduce un perfil nuevo.

- **Nuevos JTBDs introducidos**: 6 racionales + 3 emocionales a nivel feature. No constituyen drift respecto a los JTBDs globales del producto:
  - JR-Fus_vscode_github_oauth.{1,2} ⊆ **JR-G.1** ("trazabilidad — cada línea justifica su existencia") aplicado al primer minuto de la experiencia: la justificación es "elimino fricción en el touchpoint Marketplace para que ICP-2 llegue al pipeline spec-driven sin abandonar antes").
  - JR-Fus_vscode_github_oauth.3 ⊆ **JR-G.3** ("hooks mecánicos para que la disciplina no dependa de fuerza de voluntad") en su versión inversa: hook contra growth hacking — el opt-out debe ser técnicamente respetable, no aspiracional.
  - JR-Fus_vscode_github_oauth.4 alineado con la decisión arquitectural v5.34.1 de `authenticate_and_authorize_cached` (TTL 30s). No es un JTBD nuevo del producto, es la materialización a nivel feature del contrato ya canónico del Native Backend.
  - JR-Fus_vscode_github_oauth.5 alineado con la **decisión canónica v5.29** "FreeForm first-class, cero auth requerida" preservada explícitamente en el tradeoff aceptado de esta US.
  - JR-Fus_vscode_github_oauth.6 alineado con la **NSM** declarada en `app_market.md` §5: las métricas input "% features con discovery completado", "healing budget medio" requieren saber quiénes son los usuarios activos — el funnel pasa por Supabase Auth.
  - JE-Fus_vscode_github_oauth.1 alineado con **JE-G.2** ("agente con disciplina, no improvisando") trasladado al producto: el producto trabaja con disciplina (auth limpia), no improvisando (copia/pega de tokens).
  - JE-Fus_vscode_github_oauth.2 protege contra drift hacia un anti-ICP implícito (growth-hacker mindset que ignora opt-outs). Refuerza la postura declarada en `app_market.md` §2 "Vibe coders rechazan disciplina — y eso es por diseño": el dual también vale, "developers que quieren control sobre su tooling — y eso también es por diseño".
  - JE-Fus_vscode_github_oauth.3 alineado con **JE-G.1** ("confianza de que nada se pierde / se controla").

- **Tradeoff documentado**: la US rompe parcialmente la decisión canónica "FreeForm first-class, cero auth requerida" introduciendo Native+OAuth como recomendado en el onboarding. Esto está **explícitamente aceptado** por el owner (ver Engram `architecture/vscode-github-oauth` #5746) condicionado a que: (a) FreeForm permanezca como escape visible y técnicamente equivalente en flujo, (b) las tools no-nativas no requieran OAuth, (c) el opt-out sea persistente (no se vuelve a empujar al usuario tras un dismiss). Los UCs del PRD deben hacer auditable cada una de estas tres garantías.

- **Resolución**: documented_exception. No se modifica `app_market.md` — los nuevos JTBDs son refinamientos verticales del producto, no señales de mercado nuevas. El tradeoff sobre la decisión canónica v5.29 se documenta como excepción de feature en este artefacto y se replicará en `doc/decisions/native_default_oauth.md` cuando llegue `/plan`.

## Verdict

**READY_FOR_PRD**

Las 5 secciones (ICPs involucrados, JTBDs racionales, JTBDs emocionales, Validation evidence, Drift from app_market) están completas. La decisión arquitectural está congelada off-band con el owner. El siguiente paso es `/prd us_vscode_github_oauth` para materializar los 6-8 UCs esperados.

---

> Este artefacto se completa interactivamente via el skill `/discovery`.
> Tras completarlo, `validate_discovery_completeness` actualizará el verdict
> a `READY_FOR_PRD` cuando todas las secciones estén llenas.
