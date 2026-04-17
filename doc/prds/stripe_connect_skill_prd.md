# PRD: [US-SPONSORSHIP-SKILL] Skill `/stripe-connect` para integración de pagos en marketplaces

> Origen: FreeForm local (engine SpecBox) | US-SPONSORSHIP-SKILL
> Generado: 2026-04-17

## Resumen

SpecBox Engine añade una nueva skill operativa, `/stripe-connect`, que permite a cualquier proyecto onboardeado con stack **Supabase + React o Flutter (Web/Mobile)** implementar pagos Stripe Connect con subscriptions, Direct charges, fee dinámico por seller y UX 100% embedded (Payment Element/Sheet + Apple Pay / Google Pay / Express Checkout) en ~3 días de trabajo real, frente a las 2-3 semanas que cuesta hoy.

La skill no envuelve la API de Stripe ni crea tools MCP nuevas en el servidor SpecBox. Se limita a orquestar piezas que ya existen en el ecosistema (Stripe MCP oficial para runtime, Stripe CLI para testing, SDK oficial en el código de producción, pipeline spec-driven existente para estructura) y a aportar **disciplina y estructura correcta por defecto**: los 12 UCs del dominio billing cargados en el backlog, templates de código parametrizados con el stack y el Brand Kit del proyecto, hooks de seguridad que impiden los errores típicos (webhook sin firma, handler sin idempotencia, Checkout hosted en lugar de embedded), catálogo de eventos webhook con acciones, test scenarios con `stripe trigger` y test clocks, y diseños Stitch coherentes con el VEG del proyecto.

El caso piloto de validación es un marketplace de micropatrocinios para pilotos de motociclismo no profesionales donde los fans se suscriben al piloto por 10/15/20€ mensuales, la plataforma cobra un fee dinámico vía `application_fee_percent` (variable para ambassadors) y los pilotos reciben el resto directamente en su cuenta Stripe Connect. El modelo Direct charges es un requisito fiscal del dueño del marketplace (autónomo en España) para no tributar IRPF sobre el importe total.

## Alcance

### Incluye
- Nueva skill `/stripe-connect` con `context: direct` en `.claude/skills/stripe-connect/SKILL.md`
- Detección automática de stack del proyecto (Supabase + React / Flutter Web / Flutter Mobile)
- Generación de US-SPONSORSHIP con 12 UCs (UC-301 a UC-312) en el backend spec-driven activo del proyecto (Trello / Plane / FreeForm)
- Templates de código parametrizados:
  - Backend Supabase: 5 Edge Functions + 4 migraciones SQL con RLS
  - Frontend React: 4 archivos en `src/billing/` con Payment Element + Express Checkout
  - Frontend Flutter: 4 archivos en `lib/billing/` con Payment Sheet + Apple/Google Pay
- Diseños Stitch de 6 pantallas generados automáticamente si hay VEG configurado en el proyecto (con fallback limpio si no)
- Hook `stripe-safety-guard.mjs` instalado en el proyecto para bloquear antipatrones (sk_live en código, webhook sin firma, handler sin idempotencia, Checkout hosted, Payment Links)
- Documentación parametrizada: checklist de setup, activación de Connect, Apple/Google Pay, catálogo de 10 eventos webhook críticos, test scenarios
- Cableado del Stripe MCP oficial en `.claude/settings.local.json` del proyecto
- Caso de uso piloto: validación end-to-end sobre un marketplace real (pilotos de motociclismo) con subscriptions Direct charges + fee dinámico

### No incluye
- Tools MCP nuevas en el servidor SpecBox que envuelvan la API de Stripe (anti-patrón rechazado explícitamente: duplica el SDK oficial y el Stripe MCP oficial, consume contexto innecesario)
- Stacks distintos de Supabase + React/Flutter (Neon, Firestore, FastAPI se añadirán en v2 solo si aparecen proyectos reales que lo requieran)
- Skill hermana `/stripe` para SaaS vanilla (subscriptions + one-time sin Connect) — queda para v2 reutilizando los templates depurados con Connect
- Checkout hosted (redirect a stripe.com) ni Payment Links — la skill es embedded-only por diseño
- Customer Portal de Stripe para gestión de suscripciones — con Direct charges el Customer vive en la connected account, por eso la cancelación es via API propia (UC-309)
- Stripe Connect con account types Standard o Custom (solo Express en v1)
- Charge models Destination o Separate charges + transfers (solo Direct charges en v1, por constraint fiscal del caso piloto)
- Refunds manuales, disputes, cambio de tier con proration, multi-currency, Stripe Tax — fuera de v1, se añadirán por UC cuando el caso real los necesite
- Cloud Functions / Firebase Extensions / Stripe Firestore Extension — no aplica al stack Supabase de v1
- Validación fiscal/legal del dev (alta autónomo del piloto en España, facturación a Hacienda): la skill solo muestra warning en UC-301

---

## User Story

**ID**: US-SPONSORSHIP-SKILL
**Nombre**: Skill `/stripe-connect` v1 para marketplaces embedded
**Actor**: Desarrollador que usa SpecBox Engine en un proyecto Supabase + React/Flutter
**Horas estimadas**: 60h
**Pantallas**: Ninguna directa en la skill (genera pantallas Stitch para el proyecto consumidor)

> Como **desarrollador** que construye un marketplace con Supabase + React o Flutter, quiero **ejecutar `/stripe-connect` y recibir la integración de Stripe Connect estructurada y correcta por defecto**, para **pasar de 2-3 semanas a ~3 días de trabajo real y evitar los errores típicos de producción (idempotencia rota, eventos no manejados, SCA mal cableado en connected accounts, UX rota por redirect a Stripe)**.

---

## Use Cases

### UC-301: Bootstrap interactivo de la skill
- **Actor**: Desarrollador
- **Horas**: 4h
- **Pantallas**: Ninguna (skill conversacional)
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-01**: Al ejecutar `/stripe-connect` en un proyecto, la skill detecta automáticamente: stack frontend (`react`/`flutter-web`/`flutter-mobile`), backend (`supabase` obligatorio en v1 — si no, aborta con mensaje claro), spec backend activo (Trello/Plane/FreeForm leyendo `.claude/settings.local.json`), presencia de VEG (buscando `doc/veg/` y `brand-kit.md`)
- [ ] **AC-02**: Si el backend detectado no es Supabase, la skill aborta con mensaje "v1 solo soporta Supabase. Otros backends previstos para v2" y sale con código 0 sin escribir nada
- [ ] **AC-03**: La skill hace exactamente 2 preguntas al usuario: (1) confirmación del stack detectado, (2) fee default en porcentaje para sellers estándar (número entre 1 y 50). Ninguna otra pregunta obligatoria
- [ ] **AC-04**: Al finalizar la fase de bootstrap, la skill muestra un plan de los archivos que va a crear/modificar antes de escribir nada, y pide confirmación explícita ("s/n") del usuario

### UC-302: Generación de US-SPONSORSHIP con 12 UCs en el backend spec-driven
- **Actor**: Sistema (skill)
- **Horas**: 6h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-05**: La skill crea en el spec backend detectado una User Story con id `US-SPONSORSHIP`, nombre "Integración de pagos marketplace con Stripe Connect", y descripción parametrizada con el nombre del proyecto y el fee default confirmado en UC-301
- [ ] **AC-06**: La skill crea los 12 UCs (UC-301 a UC-312 en el proyecto consumidor — no confundir con los UCs de este PRD) como cards/issues hijas de US-SPONSORSHIP, cada uno con título, descripción, horas estimadas (entre 2h y 8h según UC), y al menos 3 acceptance criteria AC-XX por UC
- [ ] **AC-07**: Cada AC-XX generado cumple el Definition Quality Gate (especificidad ≥ 1, medibilidad ≥ 1, testabilidad ≥ 1, promedio ≥ 1.5/2.0) — verificable porque la skill invoca internamente la validación del skill `/prd` sobre los ACs antes de crear las cards
- [ ] **AC-08**: Si el backend spec-driven no responde (Trello/Plane offline), la skill hace fallback a FreeForm local en `doc/tracking/` del proyecto sin perder los UCs, y avisa al usuario del fallback

### UC-303: Generación de templates de backend Supabase
- **Actor**: Sistema (skill)
- **Horas**: 10h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-09**: La skill crea exactamente 5 Edge Functions en `supabase/functions/` del proyecto: `create-rider-account-link/index.ts`, `create-fan-subscription/index.ts`, `cancel-fan-subscription/index.ts`, `create-rider-dashboard-link/index.ts`, `stripe-webhook/index.ts`, cada una con importación de `stripe@^14` (Deno/ESM) y uso del `Stripe-Account` header para Direct charges
- [ ] **AC-10**: La función `stripe-webhook/index.ts` incluye verificación de firma con `stripe.webhooks.constructEventAsync`, distingue webhooks de plataforma vs Connect leyendo el header `Stripe-Signature` contra dos secrets (`STRIPE_WEBHOOK_SECRET_PLATFORM` y `STRIPE_WEBHOOK_SECRET_CONNECT`), y consulta la tabla `stripe_processed_events` para idempotencia antes de procesar cualquier evento
- [ ] **AC-11**: La skill crea 4 migraciones SQL numeradas en `supabase/migrations/`: `riders_stripe_account.sql` (stripe_account_id, fee_percent nullable, onboarding status), `sponsorships.sql` (fan_id, rider_id, subscription_id, amount, status, timestamps), `stripe_processed_events.sql` (event_id PK, received_at, processed_at), `rls_policies.sql` con policies que garantizan que un fan solo ve sus sponsorships y un piloto solo ve los que le corresponden
- [ ] **AC-12**: La función `create-fan-subscription/index.ts` crea la Subscription pasando `application_fee_percent` dinámico leído de la columna `riders.fee_percent` (o `DEFAULT_APPLICATION_FEE_PERCENT` del env si es null), y con `payment_behavior: 'default_incomplete'` + expansión de `pending_setup_intent` para SCA correcto
- [ ] **AC-13**: Las migraciones SQL son idempotentes (`CREATE TABLE IF NOT EXISTS`, `CREATE POLICY IF NOT EXISTS`) y se aplican sin error en una base Supabase vacía, verificado ejecutando `supabase db reset` seguido de `supabase db push` en el caso piloto

### UC-304: Generación de templates de frontend React
- **Actor**: Sistema (skill)
- **Horas**: 6h
- **Pantallas**: Ninguna (templates para el proyecto)
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-14**: Si el stack detectado es React, la skill crea en `src/billing/` del proyecto: `stripe-provider.tsx` (con `<Elements>`, `appearance` parametrizada desde Brand Kit si existe), `sponsor-rider-form.tsx` (con `<PaymentElement>` + `<ExpressCheckoutElement>`), `use-sponsorship.ts` (hook que llama la Edge Function `create-fan-subscription` y maneja estados loading/success/error/requires_action), `rider-onboarding-button.tsx` (CTA que llama `create-rider-account-link` y redirige)
- [ ] **AC-15**: El componente `sponsor-rider-form.tsx` nunca importa `redirectToCheckout` ni referencia Payment Links — solo usa métodos de `stripe.confirmPayment` sobre el PaymentIntent de la Subscription
- [ ] **AC-16**: Si existe `doc/design/brand-kit.md` en el proyecto, el `appearance` del `<Elements>` se parametriza automáticamente con los tokens `colorPrimary`, `fontFamily`, `borderRadius` extraídos del Brand Kit; si no existe, usa valores neutros y deja comentario `// TODO: parametrizar con Brand Kit cuando exista`
- [ ] **AC-17**: Los templates compilan sin errores TypeScript en un proyecto React 19 + Vite con `@stripe/stripe-js` y `@stripe/react-stripe-js` instalados, verificado ejecutando `npm run typecheck` en el caso piloto

### UC-305: Generación de templates de frontend Flutter
- **Actor**: Sistema (skill)
- **Horas**: 6h
- **Pantallas**: Ninguna (templates para el proyecto)
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-18**: Si el stack detectado es Flutter (Web o Mobile), la skill crea en `lib/billing/` del proyecto: `stripe_service.dart` (init de `Stripe.publishableKey` + configuración Apple Pay + Google Pay + appearance), `sponsor_rider_controller.dart` (controlador con Payment Sheet init y present + manejo de estados Riverpod o BLoC según detección), `apple_pay_button.dart`, `google_pay_button.dart`, `rider_onboarding_launcher.dart` (abre Account Link con `url_launcher` + deep link de retorno)
- [ ] **AC-19**: El `Stripe-Account` header se pasa correctamente en las llamadas al backend para Direct charges, detectable porque el repositorio de API incluye interceptor que añade el header con el `stripe_account_id` del piloto seleccionado
- [ ] **AC-20**: Apple Pay y Google Pay están configurados por defecto en `stripe_service.dart` con `merchantCountryCode` leído de configuración del proyecto (default 'ES'), sin comentarios "TODO enable later" — están activos desde el template inicial
- [ ] **AC-21**: Los templates compilan sin errores Dart en un proyecto Flutter 3.38+ con `flutter_stripe: ^10.0.0` instalado, verificado ejecutando `flutter analyze` en el caso piloto

### UC-306: Generación de diseños Stitch para pantallas de billing
- **Actor**: Sistema (skill)
- **Horas**: 8h
- **Pantallas**: 6 pantallas generadas en `doc/design/sponsorship/` del proyecto
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-22**: Si el proyecto tiene VEG configurado (detectado por presencia de `doc/veg/` y `brand-kit.md`), la skill invoca `stitch_generate_screen` exactamente 6 veces con prompts pre-armados adaptados al arquetipo VEG detectado (Corporate / Startup / Consumer / Creative / Gen-Z / Gobierno), para las pantallas: `rider-onboarding`, `rider-public-profile`, `sponsor-modal`, `sponsorship-success`, `fan-subscriptions`, `rider-dashboard`
- [ ] **AC-23**: Los HTMLs generados se guardan en `doc/design/sponsorship/{screen}.html` del proyecto consumidor, y cada prompt enviado a Stitch queda registrado en `doc/design/sponsorship/stitch_prompts.md` (para reproducibilidad y ajuste futuro)
- [ ] **AC-24**: Si el proyecto no tiene VEG, la skill skipea la fase de Stitch con mensaje "VEG no detectado. Saltando generación de diseños. Ejecuta `/visual-setup` antes de `/stripe-connect` si quieres diseños coherentes con tu brand" y continúa el resto de la skill sin error
- [ ] **AC-25**: Los prompts a Stitch nunca piden "botón que redirige a Stripe Checkout" — especifican explícitamente "contenedor modal/sheet que va a alojar el Payment Element de Stripe embedded, con altura X, padding Y, formulario embebido, footer con Powered by Stripe"

### UC-307: Instalación del hook `stripe-safety-guard`
- **Actor**: Sistema (skill)
- **Horas**: 5h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-26**: La skill copia `stripe-safety-guard.mjs` a `.claude/hooks/` del proyecto consumidor y añade la entrada correspondiente en `.claude/settings.json` bajo `hooks.PreToolUse` con matcher para Write/Edit en archivos de `src/billing/`, `lib/billing/`, `supabase/functions/`
- [ ] **AC-27**: El hook detecta y bloquea con exit code 2 y mensaje explicativo: (a) strings que empiecen por `sk_live_` en código (no en `.env` ni docs), (b) handlers de webhook que no llamen `constructEvent` o `constructEventAsync`, (c) Edge Functions que procesen eventos sin consultar tabla `stripe_processed_events` previamente, (d) importaciones de `redirectToCheckout` o creación de Checkout Sessions con `ui_mode: 'hosted'`, (e) uso de Payment Links en código
- [ ] **AC-28**: Cuando el hook bloquea, el mensaje explica el antipatrón detectado + la razón concreta (ej: "webhooks duplicados causan doble cobro en producción — añade verificación de idempotencia con tabla stripe_processed_events") + ejemplo de código correcto
- [ ] **AC-29**: El hook tiene falsos positivos < 5% medido sobre al menos 30 archivos reales del caso piloto (verificar que no bloquea código correcto y sí bloquea los 5 antipatrones con casos sintéticos)

### UC-308: Generación de documentación parametrizada
- **Actor**: Sistema (skill)
- **Horas**: 4h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-30**: La skill crea `infra/stripe/README.md` en el proyecto con checklist de 4 a 6 pasos concretos: envvars a rellenar (con nombres exactos y dónde obtenerlos), comando exacto de `stripe listen --forward-to` para el endpoint del proyecto, activación de Connect en dashboard, creación opcional de Products si el proyecto los usa (no siempre aplica con Direct charges)
- [ ] **AC-31**: La skill crea `infra/stripe/connect-setup.md` con pasos específicos de Connect: activación en dashboard, branding del onboarding Express, fee default, enlaces a documentación oficial de Stripe para test sellers y test bank accounts por país
- [ ] **AC-32**: La skill crea `doc/design/billing/events-catalog.md` con los 10 eventos webhook críticos de v1 (`account.updated`, `capability.updated`, `account.application.deauthorized`, `customer.subscription.created/updated/deleted`, `invoice.paid`, `invoice.payment_failed`, `charge.refunded`, `application_fee.created`), cada uno con: qué lo dispara, si llega al webhook de plataforma o Connect, qué debe hacer el backend, qué fila de la DB se modifica
- [ ] **AC-33**: La skill crea `doc/design/billing/test-scenarios.md` con un bloque de comandos ejecutables por UC del proyecto: `stripe trigger` para cada evento, comandos de test clock para simular renovación mensual y trial ending (aunque trial no aplica al caso piloto, se incluye para futuro)

### UC-309: Cableado del Stripe MCP oficial
- **Actor**: Sistema (skill)
- **Horas**: 3h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-34**: La skill lee `.claude/settings.local.json` del proyecto y añade (sin reemplazar config existente) la entrada para el Stripe MCP oficial bajo `mcpServers.stripe` con URL oficial publicada por Stripe y placeholder `STRIPE_SECRET_KEY` que apunta a env var
- [ ] **AC-35**: Si `.claude/settings.local.json` no existe, la skill lo crea con la estructura mínima (`permissions`, `mcpServers`) sin tocar `.claude/settings.json` (que es del engine, no del proyecto)
- [ ] **AC-36**: Tras ejecutar la skill, en una nueva sesión de Claude Code sobre el proyecto, las tools del Stripe MCP oficial (`create_product`, `create_price`, `list_customers`, etc.) están disponibles — verificable listando las tools `mcp__stripe__*` desde la sesión

### UC-310: Generación de tests de aceptación AG-09 para cada UC
- **Actor**: Sistema (skill)
- **Horas**: 6h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-37**: La skill genera por cada UC del proyecto (UC-301 a UC-312 del proyecto, no de este PRD) un archivo `*.feature` Gherkin en español en `tests/acceptance/sponsorship/` con escenarios cableados a `stripe trigger` + test clocks, listos para ser consumidos por AG-09a del pipeline `/implement` sin modificación manual
- [ ] **AC-38**: Cada archivo `.feature` incluye al menos un escenario negativo (pago fallido con `card_decline`, webhook duplicado, piloto sin onboarding completado, etc.) además del flujo feliz
- [ ] **AC-39**: El test de UC-306 del proyecto (webhook con firma + idempotencia) usa `stripe trigger --replay` o envío repetido del mismo event.id para verificar que el handler no procesa el evento dos veces y que la tabla `stripe_processed_events` registra el evento correctamente
- [ ] **AC-40**: Tras ejecutar la skill sobre el caso piloto y correr `/implement` sobre los UCs resultantes, al menos el UC-305 del proyecto (Payment Element embedded con Direct charge + fee dinámico) produce un HTML Evidence Report válido generado por AG-09, verificado en el caso piloto

### UC-311: Validación end-to-end sobre el caso piloto (marketplace de pilotos)
- **Actor**: Desarrollador del caso piloto
- **Horas**: 4h
- **Pantallas**: Ninguna (criterio operativo)
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-41**: En el proyecto piloto del marketplace de pilotos, ejecutar `/stripe-connect` crea todos los archivos listados en UC-303 a UC-310 de este PRD sin errores, y la US-SPONSORSHIP + 12 UCs aparecen en el backend spec-driven del proyecto piloto (FreeForm en `doc/tracking/`)
- [ ] **AC-42**: En el proyecto piloto, tras ejecutar `/stripe-connect` + rellenar las 4 envvars del checklist de `infra/stripe/README.md` + `supabase db push`, un fan de prueba puede completar una suscripción a un piloto de prueba usando tarjeta `4242 4242 4242 4242` en el Payment Element, el webhook procesa `invoice.paid`, y la fila correspondiente aparece en la tabla `sponsorships` con status `active`, sin tocar nada del código generado por la skill
- [ ] **AC-43**: En el escenario de AC-42, el fee dinámico se aplica correctamente: si el piloto tiene `fee_percent = 15`, el balance de la plataforma recibe 1.50€ de los 10€ cobrados; si el piloto es ambassador con `fee_percent = 8`, recibe 0.80€ — verificable consultando `application_fee.created` en el dashboard de Stripe
- [ ] **AC-44**: El flujo AC-42 funciona idéntico en React (test con Playwright sobre la app web del marketplace) y en Flutter Web (test con Patrol o manual), con evidencia visual (screenshots del Payment Element in-app sin redirect a stripe.com)

### UC-312: Documentación de la skill en el propio engine SpecBox
- **Actor**: Sistema (mantenedor del engine)
- **Horas**: 4h
- **Pantallas**: Ninguna
- **Estado**: backlog

#### Acceptance Criteria
- [ ] **AC-45**: La skill aparece listada en la tabla "Available Skills" de `CLAUDE.md` del engine con trigger phrases (ej: "stripe connect", "marketplace billing", "integrar pagos"), modo (`context: direct`), herramientas (Full), y notas (v5.25 — Marketplace Connect + Direct charges + Supabase)
- [ ] **AC-46**: Existe `docs/skills/stripe-connect.md` en el engine con: qué hace, cuándo usarla, prerrequisitos (Supabase + React/Flutter onboardeado), flujo paso a paso con los 12 UCs que genera, limitaciones explícitas (v1 scope), enlaces a docs de Stripe relevantes
- [ ] **AC-47**: `ENGINE_VERSION.yaml` se bumpea a v5.25.0 con changelog describiendo la nueva skill, y `CHANGELOG.md` recoge la entrada con la misma descripción
- [ ] **AC-48**: La skill pasa `/compliance` audit del propio engine sin nuevas violaciones (frontmatter correcto con `context: direct`, hook `stripe-safety-guard.mjs` presente en `.claude/hooks/`, entry en `settings.json.template`)

---

## Interacciones UI

> La skill `/stripe-connect` NO tiene UI propia — es un comando conversacional que genera artefactos. Esta sección describe las **interacciones durante la ejecución del comando** y las pantallas que la skill genera para el proyecto consumidor.

### Visualización de datos (durante ejecución del comando)
| Dato | Volumen | Atributos visibles | Acciones por item |
|------|---------|-------------------|-------------------|
| Archivos detectados (stack scan) | 5-10 | Ruta, tipo, propósito | Confirmar detección |
| Plan de archivos a crear | 20-30 | Ruta destino, nuevo/modificado | Confirmar "s/n" |
| UCs generados en backend | 12 | ID, título, horas | Listado inline |

### Acciones del usuario (durante ejecución)
| Acción | UC asociado | Frecuencia | Criticidad | Requiere confirmación |
|--------|-------------|------------|------------|----------------------|
| Confirmar stack detectado | UC-301 | Una vez | Alta | Sí |
| Introducir fee default | UC-301 | Una vez | Media | No (validación de rango 1-50) |
| Confirmar plan de archivos | UC-301 | Una vez | Alta | Sí |

### Formularios (durante ejecución — mínimos, diálogo conversacional)
| Formulario | UC asociado | Campos | Contexto |
|------------|-------------|--------|----------|
| Stack confirmation | UC-301 | 1 (y/n) | Diálogo inline |
| Fee default input | UC-301 | 1 (número 1-50) | Diálogo inline |
| Plan confirmation | UC-301 | 1 (y/n) | Diálogo inline con resumen de 20-30 archivos |

### Pantallas generadas para el proyecto consumidor (via Stitch — UC-306)
| Pantalla | UC del proyecto | Propósito | Arquetipo VEG adaptado |
|----------|-----------------|-----------|------------------------|
| `rider-onboarding.html` | UC-301 proyecto | CTA a Account Link + warning autónomo | Sí |
| `rider-public-profile.html` | UC-304 proyecto | Perfil del piloto con 3 planes | Sí |
| `sponsor-modal.html` | UC-305 proyecto | Contenedor Payment Element embedded | Sí |
| `sponsorship-success.html` | UC-305 proyecto | Confirmación inline | Sí |
| `fan-subscriptions.html` | UC-309 proyecto | Gestión subs del fan con cancelar | Sí |
| `rider-dashboard.html` | UC-310 proyecto | MRR, sponsors, payout, Express Dashboard link | Sí |

---

## Audiencia (alimenta VEG)

> Esta skill es una herramienta interna del engine SpecBox. Su "audiencia" son los desarrolladores que consumen el engine, no los usuarios finales. No activa VEG para la skill misma, pero sí **consume VEG del proyecto consumidor** cuando genera los diseños Stitch (UC-306).

### Target único: Desarrollador SpecBox
- **Perfil**: Solo developer o lead técnico de equipo pequeño, 5-15 años de experiencia, cómodo con SDKs oficiales, escéptico de magic/black-box, valora la disciplina y los hooks de seguridad por encima de la velocidad pura
- **Contexto de uso**: Al arrancar la integración de pagos en un proyecto nuevo o al añadir billing a uno existente. Uso one-shot: se ejecuta la skill una vez por feature de billing, no recurrentemente
- **JTBD Racional**: Tener la integración de Stripe Connect con subscriptions correcta desde el día 1 sin leer 40 páginas de docs de Stripe ni recopilar gotchas de producción en el camino duro
- **JTBD Emocional**: Sentirse en control (no engañado por un generador black-box), auditable (hooks + evidencia + tests) y respetado por la herramienta (decisiones opinionated pero explicadas, sin ocultar los tradeoffs)
- **Referentes**: supabase CLI, stripe CLI, planetscale cli — herramientas opinionadas, con mensajes claros, que respetan al usuario
- **Expectativa visual**: Ninguna UI — es un CLI conversacional. Los artefactos que genera sí deben respetar el brand del proyecto consumidor

---

## Requisitos No Funcionales (NFRs)

| NFR | Criterio | Medición |
|-----|----------|----------|
| Rendimiento (sin Stitch) | Ejecución completa de la skill (excluyendo fase Stitch) < 30 segundos en un proyecto de tamaño medio | `time` sobre el comando en el caso piloto |
| Rendimiento (con Stitch) | Fase Stitch de 6 pantallas < 20 minutos total (3 min/pantalla promedio con `GEMINI_3_PRO`) | Log timestamps en `stitch_prompts.md` |
| Seguridad | Cero `sk_live_*` ni secrets hardcoded en los templates generados, verificado por grep sobre el output en el caso piloto | `grep -r "sk_live_\|sk_test_" output/` debe devolver solo referencias a env vars |
| Seguridad | El hook `stripe-safety-guard` rechaza al 100% los 5 antipatrones definidos en AC-27 con casos sintéticos de test | Suite de tests del hook en `.quality/hooks/stripe-safety-guard.test.mjs` |
| Robustez | La skill maneja gracefully la ausencia de VEG, el offline del spec backend, la ausencia de `.claude/settings.local.json` — en los 3 casos completa su trabajo (con degradación) sin crashear | 3 tests manuales sobre proyectos con esas condiciones |
| Compatibilidad | Compatible con SpecBox Engine v5.25.0+ y proyectos con Supabase CLI v1.200+ | Declarado en `SKILL.md` frontmatter y validado por `/compliance` |
| Mantenibilidad | Los templates SQL/TS/Dart son regenerables desde plantillas versionadas en `.claude/skills/stripe-connect/templates/` sin lógica hardcoded dispersa en el código de la skill | Review: templates aislados bajo `/templates/`, skill solo parametriza e inyecta |

---

## Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Stripe cambia la API de Direct charges / `application_fee_percent` | Baja | Alto | Templates usan SDK oficial; pinneamos `stripe@^14` en requirements del template; si Stripe deprecia, se actualiza la versión del template, no la skill |
| Proyectos con configuración no estándar de Supabase (ej: sin `supabase/` folder) fallan | Media | Medio | UC-301 detecta ausencia y aborta con mensaje "Supabase CLI no inicializado. Ejecuta `supabase init` antes de `/stripe-connect`" |
| Stitch API latencia > 3min/pantalla o failure | Alta | Medio | UC-306 implementa retry con backoff + fallback: si Stitch falla, genera `doc/design/sponsorship/PENDING_DESIGNS.md` con los prompts para que el dev los lance manualmente |
| El hook `stripe-safety-guard` bloquea código correcto (falso positivo) | Media | Alto | NFR de falsos positivos < 5%; tests sintéticos en `.quality/hooks/`; escape hatch documentado: `// stripe-safety-guard:ignore` en línea específica |
| Desarrolladores no entienden el constraint fiscal (Direct vs Destination) y usan la skill para un caso SaaS vanilla | Media | Medio | UC-301 muestra warning inicial: "Esta skill genera integración **marketplace Connect**. Para SaaS vanilla (subscriptions sin terceros) espera `/stripe` en v2 o usa templates de `infra/stripe/patterns.md`" |
| Piloto del marketplace no es autónomo en España → Stripe rechaza onboarding o Hacienda reclama | Alta | Alto (reputacional + legal) | UC-301 del proyecto consumidor (no de este PRD) incluye AC obligatorio de mostrar warning al piloto antes del Account Link con enlace al proceso de alta autónomo |

---

## Stack Técnico (estimado)

- **Skill**: `.claude/skills/stripe-connect/SKILL.md` con `context: direct`, `agent` omitido (ejecuta en sesión principal)
- **Templates**: `.claude/skills/stripe-connect/templates/` con subcarpetas `supabase/`, `react/`, `flutter/`, `docs/`, `hooks/`, `tests/`
- **Hook nuevo**: `.claude/hooks/stripe-safety-guard.mjs` (copiable a proyectos consumidores)
- **Docs del engine**: `docs/skills/stripe-connect.md`
- **Integración**: reutiliza `stitch_client.py` / `stitch_generate_screen` existente del MCP, NO añade tools al servidor MCP SpecBox
- **MCPs externos que la skill orquesta**: Stripe MCP oficial (añadido al proyecto consumidor, NO al engine), Stitch MCP (ya existente)

## Archivos Principales (del engine SpecBox)

```
specbox-engine/
├── .claude/
│   ├── skills/
│   │   └── stripe-connect/
│   │       ├── SKILL.md                    ← nuevo
│   │       └── templates/
│   │           ├── supabase/
│   │           │   ├── functions/          ← 5 Edge Functions
│   │           │   └── migrations/         ← 4 SQL migrations
│   │           ├── react/                  ← 4 archivos .tsx/.ts
│   │           ├── flutter/                ← 5 archivos .dart
│   │           ├── docs/                   ← README, connect-setup, events-catalog, test-scenarios
│   │           ├── hooks/stripe-safety-guard.mjs
│   │           └── tests/                  ← Gherkin features templates
│   └── hooks/stripe-safety-guard.mjs       ← nuevo (copia source)
├── docs/skills/stripe-connect.md           ← nuevo
├── ENGINE_VERSION.yaml                     ← bump a v5.25.0
├── CHANGELOG.md                            ← entrada v5.25.0
└── CLAUDE.md                               ← añadir skill a tabla "Available Skills"
```

## Dependencias

- SpecBox Engine v5.24.0+ (requerido: skill frontmatter `context: direct` + VEG pipeline + spec-driven backend abstracto)
- Stitch MCP ya integrado en SpecBox (v5.6.0+)
- Stripe MCP oficial publicado por Stripe (externa, cableada a `.claude/settings.local.json` del proyecto consumidor)
- Supabase CLI v1.200+ en el proyecto consumidor
- Stripe CLI en el entorno del desarrollador (para `stripe listen`, `stripe trigger`, test clocks)

---

## Criterios de Aceptación (consolidado)

### Funcionales (validados por AG-09)

- [ ] **AC-01**: Detección automática de stack frontend, backend, spec backend y presencia de VEG al ejecutar `/stripe-connect` — de UC-301
- [ ] **AC-02**: Aborto limpio si backend ≠ Supabase con mensaje explicativo y exit code 0 — de UC-301
- [ ] **AC-03**: Skill hace exactamente 2 preguntas obligatorias (confirmación stack, fee default) — de UC-301
- [ ] **AC-04**: Muestra plan de archivos a crear y pide confirmación explícita antes de escribir — de UC-301
- [ ] **AC-05**: Crea US-SPONSORSHIP en spec backend con descripción parametrizada — de UC-302
- [ ] **AC-06**: Crea 12 UCs hijos con ≥ 3 ACs por UC, horas entre 2h-8h — de UC-302
- [ ] **AC-07**: Todos los ACs generados pasan Definition Quality Gate ≥ 1.5/2.0 — de UC-302
- [ ] **AC-08**: Fallback a FreeForm si spec backend offline, con aviso — de UC-302
- [ ] **AC-09**: Crea 5 Edge Functions en `supabase/functions/` con `Stripe-Account` header — de UC-303
- [ ] **AC-10**: `stripe-webhook` incluye verificación firma + idempotencia con `stripe_processed_events` — de UC-303
- [ ] **AC-11**: Crea 4 migraciones SQL (riders, sponsorships, processed_events, RLS) — de UC-303
- [ ] **AC-12**: `create-fan-subscription` usa `application_fee_percent` dinámico + `payment_behavior: default_incomplete` — de UC-303
- [ ] **AC-13**: Migraciones SQL idempotentes aplicables con `supabase db push` — de UC-303
- [ ] **AC-14**: Crea 4 archivos en `src/billing/` con Payment Element + Express Checkout Element — de UC-304
- [ ] **AC-15**: Cero uso de `redirectToCheckout` ni Payment Links en templates React — de UC-304
- [ ] **AC-16**: Appearance del `<Elements>` parametrizado con Brand Kit si existe — de UC-304
- [ ] **AC-17**: Templates React compilan sin errores TypeScript en React 19 + Vite — de UC-304
- [ ] **AC-18**: Crea 5 archivos en `lib/billing/` con Payment Sheet + Apple/Google Pay — de UC-305
- [ ] **AC-19**: `Stripe-Account` header se pasa en llamadas al backend para Direct charges — de UC-305
- [ ] **AC-20**: Apple Pay + Google Pay configurados por defecto sin TODOs — de UC-305
- [ ] **AC-21**: Templates Flutter compilan sin errores en Flutter 3.38+ con `flutter_stripe: ^10` — de UC-305
- [ ] **AC-22**: Invoca `stitch_generate_screen` 6 veces con prompts adaptados al arquetipo VEG — de UC-306
- [ ] **AC-23**: HTMLs guardados en `doc/design/sponsorship/` + prompts registrados — de UC-306
- [ ] **AC-24**: Skip limpio de fase Stitch si no hay VEG, con mensaje explicativo — de UC-306
- [ ] **AC-25**: Prompts Stitch piden contenedores embedded, nunca redirect a Stripe — de UC-306
- [ ] **AC-26**: Copia `stripe-safety-guard.mjs` a `.claude/hooks/` y actualiza `settings.json` — de UC-307
- [ ] **AC-27**: Hook bloquea 5 antipatrones definidos con exit code 2 — de UC-307
- [ ] **AC-28**: Mensajes de bloqueo incluyen razón + ejemplo de código correcto — de UC-307
- [ ] **AC-29**: Falsos positivos del hook < 5% en 30 archivos reales — de UC-307
- [ ] **AC-30**: Crea `infra/stripe/README.md` con checklist 4-6 pasos concretos — de UC-308
- [ ] **AC-31**: Crea `infra/stripe/connect-setup.md` con pasos específicos Connect — de UC-308
- [ ] **AC-32**: Crea `events-catalog.md` con los 10 eventos críticos y acciones por evento — de UC-308
- [ ] **AC-33**: Crea `test-scenarios.md` con comandos `stripe trigger` + test clocks por UC — de UC-308
- [ ] **AC-34**: Añade Stripe MCP oficial a `.claude/settings.local.json` sin reemplazar existente — de UC-309
- [ ] **AC-35**: Crea `settings.local.json` si no existe sin tocar `settings.json` del engine — de UC-309
- [ ] **AC-36**: Tras ejecutar skill, tools `mcp__stripe__*` disponibles en nueva sesión — de UC-309
- [ ] **AC-37**: Genera `.feature` Gherkin por UC en `tests/acceptance/sponsorship/` consumibles por AG-09a — de UC-310
- [ ] **AC-38**: Cada `.feature` incluye al menos un escenario negativo — de UC-310
- [ ] **AC-39**: Test de UC-306 del proyecto usa `stripe trigger --replay` para verificar idempotencia — de UC-310
- [ ] **AC-40**: UC-305 del proyecto piloto produce HTML Evidence Report válido tras `/implement` — de UC-310
- [ ] **AC-41**: Ejecutar `/stripe-connect` en proyecto piloto crea todos los archivos sin errores + US-SPONSORSHIP en FreeForm — de UC-311
- [ ] **AC-42**: Fan de prueba completa suscripción con tarjeta test en Payment Element + webhook actualiza `sponsorships` a `active` sin tocar código — de UC-311
- [ ] **AC-43**: Fee dinámico aplicado correctamente (15% vs 8% ambassador) verificable en dashboard Stripe — de UC-311
- [ ] **AC-44**: Flujo idéntico en React y Flutter Web con evidencia visual sin redirect a stripe.com — de UC-311
- [ ] **AC-45**: Skill listada en tabla "Available Skills" de `CLAUDE.md` engine con trigger phrases y notas — de UC-312
- [ ] **AC-46**: Existe `docs/skills/stripe-connect.md` con qué hace, prerequisitos, flujo, limitaciones — de UC-312
- [ ] **AC-47**: `ENGINE_VERSION.yaml` bumpeado a v5.25.0 + `CHANGELOG.md` con entrada — de UC-312
- [ ] **AC-48**: Skill pasa `/compliance` audit sin nuevas violaciones — de UC-312

### Técnicos (no validados por AG-09)

- [ ] `SKILL.md` frontmatter válido con `context: direct` (verificado manualmente por el Skill Frontmatter Model de CLAUDE.md)
- [ ] Templates organizados bajo `.claude/skills/stripe-connect/templates/` con estructura clara
- [ ] Hook `stripe-safety-guard.mjs` con tests unitarios en `.quality/hooks/`
- [ ] Sin referencias a tools MCP nuevas del servidor SpecBox (verificable por grep: la skill NO debe añadir tools a `server/tools/`)
- [ ] Compatibilidad declarada con SpecBox v5.25.0+ en frontmatter
- [ ] Changelog y version bump coherentes

---

## Definition Quality Gate — autoevaluación

Aplico el Paso 2.5 del skill `/prd` sobre los 48 ACs arriba. Muestreo los más representativos:

| AC | UC | Especificidad | Medibilidad | Testabilidad | Veredicto |
|----|-----|---------------|-------------|--------------|-----------|
| AC-01 | UC-301 | 2 (detecciones concretas nombradas) | 2 (verificable por output del comando) | 2 (automatizable con fixtures de proyectos) | OK |
| AC-10 | UC-303 | 2 (funciones, métodos, secrets específicos) | 2 (verificable por inspección del archivo) | 2 (test sintético con payload duplicado) | OK |
| AC-17 | UC-304 | 2 (versión exacta React + comando) | 2 (`npm run typecheck` binario) | 2 (automatizable en CI) | OK |
| AC-27 | UC-307 | 2 (5 antipatrones enumerados + exit code) | 2 (exit code binario + mensaje) | 2 (suite de tests sintéticos) | OK |
| AC-29 | UC-307 | 2 (< 5% sobre 30 archivos) | 2 (ratio numérico) | 1 (requiere dataset de archivos reales — aceptable) | OK |
| AC-42 | UC-311 | 2 (tarjeta exacta, tabla, status, comportamiento) | 2 (fila en DB verificable) | 2 (Playwright + consulta SQL) | OK |
| AC-44 | UC-311 | 2 (stacks específicos + evidencia visual + dominio excluido) | 2 (screenshot vs redirect detectable) | 2 (Playwright) | OK |

**Cobertura**: 12 UCs, 48 ACs → ratio 4.0 (≥ 1.0 requerido). ✅
**Promedio estimado**: 1.9/2.0 sobre la muestra. ✅
**Veredicto**: APROBADO.

**VEG Readiness**: DISABLED para la skill misma (no aplica — es herramienta interna sin UI propia). Los diseños Stitch que la skill genera consumen el VEG del **proyecto consumidor**, que se valida por UC-306/AC-22.

---

**Prioridad**: high
**Complejidad**: Alta (nueva skill con 4 stacks de output + 12 UCs + hook + docs + validación end-to-end sobre caso real)
*Generado: 2026-04-17*
