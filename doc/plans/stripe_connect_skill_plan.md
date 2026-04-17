# Plan: Skill `/stripe-connect` v1 (SpecBox Engine v5.25.0)

> Generado: 2026-04-17
> Origen: [doc/prds/stripe_connect_skill_prd.md](../prds/stripe_connect_skill_prd.md) — US-SPONSORSHIP-SKILL (FreeForm local)
> Estado: Pendiente
> Target engine version: v5.25.0 "Stripe Connect"

---

## Resumen

Implementar la skill operativa `/stripe-connect` como feature interna del engine SpecBox v5.25.0. La skill vive en [.claude/skills/stripe-connect/](.claude/skills/stripe-connect/) y, al invocarse sobre un proyecto consumidor con stack Supabase + React o Flutter, genera en un único comando: US-SPONSORSHIP con 12 UCs en el spec backend del proyecto, templates de código parametrizados (5 Edge Functions + 4 migraciones SQL + 4 archivos React o 5 Flutter), 6 diseños Stitch si hay VEG, hook `stripe-safety-guard.mjs`, documentación parametrizada (README, Connect setup, events catalog, test scenarios), cableado del Stripe MCP oficial, y tests Gherkin de aceptación. Esta skill no añade tools al servidor MCP del engine — orquesta piezas existentes (SDK Stripe, Stripe MCP oficial, Stripe CLI, Stitch MCP, pipeline spec-driven) con opinión fuerte: Connect Express + Direct charges + subscriptions embedded-only.

## Análisis UI (Fase 0)

### Componentes Requeridos

La skill **no tiene UI propia** — es un comando conversacional que corre en la terminal de Claude Code sobre un proyecto consumidor. No se analizan widgets ni pantallas para el engine.

Las 6 pantallas que la skill genera en el proyecto consumidor (UC-306 del PRD) se producen delegando al Stitch MCP ya existente (tool `stitch_generate_screen`). No se crean widgets nuevos en el engine para esto — el engine ya integra Stitch vía [server/stitch_client.py](../../server/stitch_client.py) y [server/tools/stitch.py](../../server/tools/stitch.py).

| Requisito | Componente | Estado | Acción |
|-----------|------------|--------|--------|
| Conversación interactiva con el usuario | Skill Markdown con pasos | Patrón existente (ver `/prd`, `/release`) | Reutilizar patrón |
| Escritura de templates parametrizados | Write tool + sustitución de tokens `{project}`, `{fee_default}`, etc. | Patrón existente en `/release`, `/compliance` | Reutilizar |
| Validación de antipatrones en código | Hook tipo PreToolUse | Patrón existente en `quality-first-guard.mjs`, `spec-guard.mjs` | Clonar patrón |
| Generación de diseños | Stitch MCP `stitch_generate_screen` | Tool ya existente | Delegar |
| Creación de US/UC/AC en spec backend | `set_auth_token` + `import_spec` del MCP SpecBox | Tools ya existentes | Delegar |
| Cableado de MCP externo en settings | Edit de JSON + merge no-destructivo | Patrón existente en `/compliance` y hook setup | Reutilizar |

### Widgets a crear

Ninguno. Es feature 100% backend/CLI sin UI.

---

## Visual Experience Generation

**Modo VEG**: **Desactivado** para esta feature.

**Justificación**: El PRD declara explícitamente VEG DISABLED para la skill misma (la skill no tiene UI que estilizar). La sección "Audiencia" del PRD define un único target ("Desarrollador SpecBox") sin JTBD emocional ni referentes visuales que justifiquen generar artefactos VEG. Los 6 diseños Stitch que la skill produce en runtime consumen el VEG del **proyecto consumidor**, no del engine — eso se valida funcionalmente por AC-22 del PRD (tests sobre el caso piloto con VEG configurado).

Pipeline legacy aplica. Ningún archivo en [doc/veg/](../veg/) de este repo.

---

## Fases de Implementación

### Fase 1 — Andamiaje de la skill (estructura + frontmatter + pasos conversacionales)

> Fundamental. Todas las fases posteriores cuelgan de aquí.

- [ ] Crear directorio [.claude/skills/stripe-connect/](.claude/skills/stripe-connect/)
- [ ] Crear [.claude/skills/stripe-connect/SKILL.md](.claude/skills/stripe-connect/SKILL.md) con frontmatter:
  ```yaml
  ---
  name: stripe-connect
  description: >
    Scaffolds Stripe Connect marketplace integration (Express + Direct charges +
    subscriptions embedded) in Supabase + React/Flutter projects. Generates
    US-SPONSORSHIP with 12 UCs, backend Edge Functions + SQL migrations,
    frontend templates with Payment Element/Sheet + Apple/Google Pay, Stitch
    designs (if VEG configured), stripe-safety-guard hook, and wires the
    official Stripe MCP. Use when the user says "stripe connect",
    "marketplace billing", "integrar pagos marketplace", "implementar pagos
    stripe". v1 scope: Supabase only, Connect Express only, Direct charges only.
  context: direct
  allowed-tools: Read, Grep, Glob, Bash(*), Write, Edit, mcp__specbox-engine__*, mcp__stitch__*
  ---
  ```
- [ ] Estructurar los 12 pasos conversacionales del SKILL.md siguiendo el patrón de `/release` (cada paso con id, título, bash/tool calls, confirmación si aplica):
  - Paso 0: Preflight (detectar stack, backend, spec backend, VEG)
  - Paso 1: Aborto si backend ≠ Supabase (AC-02)
  - Paso 2: Preguntas al usuario (stack confirm + fee default, AC-03)
  - Paso 3: Plan de archivos + confirmación "s/n" (AC-04)
  - Paso 4: Crear US-SPONSORSHIP + 12 UCs en spec backend (AC-05..AC-08)
  - Paso 5: Escribir templates Supabase (AC-09..AC-13)
  - Paso 6: Escribir templates frontend según stack (AC-14..AC-21)
  - Paso 7: Invocar Stitch si VEG (AC-22..AC-25)
  - Paso 8: Instalar hook `stripe-safety-guard` (AC-26..AC-29)
  - Paso 9: Escribir docs parametrizadas (AC-30..AC-33)
  - Paso 10: Cablear Stripe MCP oficial (AC-34..AC-36)
  - Paso 11: Generar `.feature` Gherkin (AC-37..AC-39)
  - Paso 12: Resumen final + siguiente paso sugerido (`/plan UC-301`)
- [ ] **Tiempo estimado**: 6h

### Fase 2 — Templates Supabase (backend)

> Templates estáticos con placeholders `{project}`, `{fee_default}`, `{ambassador_fee_default}` que la skill sustituye en Fase 5 del SKILL.

- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/functions/create-rider-account-link/index.ts](.claude/skills/stripe-connect/templates/supabase/functions/create-rider-account-link/index.ts) — Edge Function Deno que crea Account Link para onboarding Express (AC-09)
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/functions/create-fan-subscription/index.ts](.claude/skills/stripe-connect/templates/supabase/functions/create-fan-subscription/index.ts) con: import `stripe` Deno, `Stripe-Account` header, `application_fee_percent` leído de `riders.fee_percent` (fallback env), `payment_behavior: default_incomplete`, expansión `pending_setup_intent` (AC-10, AC-12)
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/functions/cancel-fan-subscription/index.ts](.claude/skills/stripe-connect/templates/supabase/functions/cancel-fan-subscription/index.ts) — DELETE Subscription en connected account
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/functions/create-rider-dashboard-link/index.ts](.claude/skills/stripe-connect/templates/supabase/functions/create-rider-dashboard-link/index.ts) — genera login link Express Dashboard
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/functions/stripe-webhook/index.ts](.claude/skills/stripe-connect/templates/supabase/functions/stripe-webhook/index.ts) con: verificación firma `constructEventAsync` contra 2 secrets (platform/connect), routing por header, consulta tabla `stripe_processed_events` ANTES de procesar (idempotencia), switch sobre los 10 eventos críticos de v1 (AC-10)
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/migrations/001_riders_stripe_account.sql](.claude/skills/stripe-connect/templates/supabase/migrations/001_riders_stripe_account.sql) — columna `stripe_account_id TEXT UNIQUE`, `fee_percent NUMERIC NULL` (NULL = usa default env), `onboarding_status TEXT` (`pending/restricted/enabled`), `CREATE ... IF NOT EXISTS` (AC-11, AC-13)
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/migrations/002_sponsorships.sql](.claude/skills/stripe-connect/templates/supabase/migrations/002_sponsorships.sql) — `fan_id`, `rider_id`, `stripe_subscription_id`, `stripe_account_id`, `amount`, `currency`, `status`, `created_at`, `updated_at`
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/migrations/003_stripe_processed_events.sql](.claude/skills/stripe-connect/templates/supabase/migrations/003_stripe_processed_events.sql) — `event_id TEXT PRIMARY KEY`, `received_at TIMESTAMPTZ`, `processed_at TIMESTAMPTZ NULL`, `event_type TEXT`, índice por `event_type + received_at`
- [ ] Crear [.claude/skills/stripe-connect/templates/supabase/migrations/004_rls_policies.sql](.claude/skills/stripe-connect/templates/supabase/migrations/004_rls_policies.sql) — `ENABLE RLS` en `sponsorships` y `riders`, policies: fan ve sus sponsorships, piloto ve los que le corresponden, service role bypass para webhook
- [ ] **Tiempo estimado**: 10h

### Fase 3 — Templates frontend React

- [ ] Crear [.claude/skills/stripe-connect/templates/react/stripe-provider.tsx](.claude/skills/stripe-connect/templates/react/stripe-provider.tsx) con `<Elements>` + `appearance` parametrizada con tokens `{brand_primary}`, `{brand_font}`, `{brand_radius}` (leídos del Brand Kit del proyecto; fallback a valores neutros con TODO comentado) — AC-14, AC-16
- [ ] Crear [.claude/skills/stripe-connect/templates/react/sponsor-rider-form.tsx](.claude/skills/stripe-connect/templates/react/sponsor-rider-form.tsx) con `<PaymentElement>` + `<ExpressCheckoutElement>` + submit via `stripe.confirmPayment`; **cero referencias a `redirectToCheckout` o Payment Links** (AC-15)
- [ ] Crear [.claude/skills/stripe-connect/templates/react/use-sponsorship.ts](.claude/skills/stripe-connect/templates/react/use-sponsorship.ts) — hook que llama Edge Function `create-fan-subscription`, maneja estados `loading | success | error | requires_action`, refresca sesión Supabase
- [ ] Crear [.claude/skills/stripe-connect/templates/react/rider-onboarding-button.tsx](.claude/skills/stripe-connect/templates/react/rider-onboarding-button.tsx) — CTA que llama `create-rider-account-link` y `window.location.href = url`
- [ ] Crear [.claude/skills/stripe-connect/templates/react/package.json.fragment.json](.claude/skills/stripe-connect/templates/react/package.json.fragment.json) — dependencias a añadir: `@stripe/stripe-js@^3`, `@stripe/react-stripe-js@^2`. La skill **mergea** (no reemplaza) el `package.json` del proyecto.
- [ ] **Tiempo estimado**: 6h

### Fase 4 — Templates frontend Flutter

- [ ] Crear [.claude/skills/stripe-connect/templates/flutter/stripe_service.dart](.claude/skills/stripe-connect/templates/flutter/stripe_service.dart) — init `Stripe.publishableKey`, config Apple Pay + Google Pay con `merchantCountryCode: '{country}'` default `'ES'`, `PaymentSheetAppearance` parametrizada con Brand Kit (AC-18, AC-20)
- [ ] Crear [.claude/skills/stripe-connect/templates/flutter/sponsor_rider_controller.dart](.claude/skills/stripe-connect/templates/flutter/sponsor_rider_controller.dart) — flujo completo con `initPaymentSheet` + `presentPaymentSheet`, estado con Riverpod por defecto (opción alternativa BLoC si el proyecto usa BLoC, detectable por presencia de `flutter_bloc` en pubspec)
- [ ] Crear [.claude/skills/stripe-connect/templates/flutter/apple_pay_button.dart](.claude/skills/stripe-connect/templates/flutter/apple_pay_button.dart) + [google_pay_button.dart](.claude/skills/stripe-connect/templates/flutter/google_pay_button.dart) — wrappers con branding oficial
- [ ] Crear [.claude/skills/stripe-connect/templates/flutter/rider_onboarding_launcher.dart](.claude/skills/stripe-connect/templates/flutter/rider_onboarding_launcher.dart) — abre Account Link con `url_launcher` + deep link de retorno `{app_scheme}://billing/onboarding-complete`
- [ ] Crear [.claude/skills/stripe-connect/templates/flutter/pubspec.fragment.yaml](.claude/skills/stripe-connect/templates/flutter/pubspec.fragment.yaml) — dependencias: `flutter_stripe: ^10.0.0`, `url_launcher: ^6.0.0`. Merge en pubspec del proyecto.
- [ ] Crear [.claude/skills/stripe-connect/templates/flutter/api_interceptor.dart](.claude/skills/stripe-connect/templates/flutter/api_interceptor.dart) — interceptor Dio/http que añade `Stripe-Account` header con `stripe_account_id` del piloto seleccionado (AC-19)
- [ ] **Tiempo estimado**: 6h

### Fase 5 — Hook `stripe-safety-guard.mjs`

- [ ] Crear [.claude/hooks/stripe-safety-guard.mjs](.claude/hooks/stripe-safety-guard.mjs) siguiendo el patrón de [spec-guard.mjs](.claude/hooks/spec-guard.mjs):
  - PreToolUse sobre Write/Edit
  - Matcher de path: `src/billing/`, `lib/billing/`, `supabase/functions/`, `lib/data/billing/`
  - 5 detectores (AC-27):
    1. Regex `/sk_live_[A-Za-z0-9]+/` en contenido (excluye `.env*`, `*.md`)
    2. Archivo `stripe-webhook` sin string `constructEvent` ni `constructEventAsync`
    3. Handler en `supabase/functions/stripe-*` sin referencia a `stripe_processed_events`
    4. Import de `redirectToCheckout` o string `ui_mode: 'hosted'`
    5. URL de Payment Link `https://buy.stripe.com/`
  - Exit code 2 + mensaje con razón + ejemplo correcto (AC-28)
  - Soporta escape hatch: línea con comentario `// stripe-safety-guard:ignore` excluye la regla en esa línea
- [ ] Crear también copia del hook en [.claude/skills/stripe-connect/templates/hooks/stripe-safety-guard.mjs](.claude/skills/stripe-connect/templates/hooks/stripe-safety-guard.mjs) — es la que la skill copia al proyecto consumidor en Paso 8 (AC-26). Usar symlink o duplicación (decidir en implementación según política del repo — `install.sh` ya usa symlinks para skills globales, pero el hook lo copiamos como archivo para que el proyecto consumidor no dependa del engine instalado)
- [ ] Crear [.quality/hooks/stripe-safety-guard.test.mjs](.quality/hooks/stripe-safety-guard.test.mjs) — suite de tests con 30 casos sintéticos (10 positivos que deben bloquear, 20 negativos que NO deben bloquear) — AC-29
- [ ] Añadir entrada en [.claude/settings.json](.claude/settings.json) bajo `hooks.PreToolUse` — para que funcione dentro del repo del engine mismo (dogfooding)
- [ ] Añadir entrada equivalente en [templates/settings.json.template](templates/settings.json.template) — para que proyectos nuevos onboardeados ya tengan el hook previsto cuando corran `/stripe-connect`
- [ ] **Tiempo estimado**: 5h

### Fase 6 — Templates de documentación parametrizada

- [ ] Crear [.claude/skills/stripe-connect/templates/docs/infra-stripe-README.md](.claude/skills/stripe-connect/templates/docs/infra-stripe-README.md) — checklist 4-6 pasos concretos con placeholders: envvars (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET_PLATFORM`, `STRIPE_WEBHOOK_SECRET_CONNECT`, `STRIPE_PUBLISHABLE_KEY`, `DEFAULT_APPLICATION_FEE_PERCENT={fee_default}`), comando `stripe listen --forward-to {supabase_local_url}/functions/v1/stripe-webhook` (AC-30)
- [ ] Crear [.claude/skills/stripe-connect/templates/docs/connect-setup.md](.claude/skills/stripe-connect/templates/docs/connect-setup.md) — activación Connect, branding Express onboarding, enlaces a `dashboard.stripe.com/test/connect/accounts` (AC-31)
- [ ] Crear [.claude/skills/stripe-connect/templates/docs/apple-google-pay-setup.md](.claude/skills/stripe-connect/templates/docs/apple-google-pay-setup.md) — Merchant ID Apple, domain verification, entitlements iOS, manifest Android; solo relevante si stack Flutter
- [ ] Crear [.claude/skills/stripe-connect/templates/docs/events-catalog.md](.claude/skills/stripe-connect/templates/docs/events-catalog.md) — tabla con los 10 eventos críticos de v1 (`account.updated`, `capability.updated`, `account.application.deauthorized`, `customer.subscription.created/updated/deleted`, `invoice.paid`, `invoice.payment_failed`, `charge.refunded`, `application_fee.created`); cada fila: trigger, endpoint plataforma vs Connect, acción backend, fila DB modificada (AC-32)
- [ ] Crear [.claude/skills/stripe-connect/templates/docs/test-scenarios.md](.claude/skills/stripe-connect/templates/docs/test-scenarios.md) — bloques ejecutables de `stripe trigger` + `stripe test_helpers test_clocks advance` por UC del proyecto (AC-33)
- [ ] **Tiempo estimado**: 4h

### Fase 7 — Templates Gherkin de aceptación + cableado Stripe MCP

- [ ] Crear 12 archivos `.feature` bajo [.claude/skills/stripe-connect/templates/tests/](.claude/skills/stripe-connect/templates/tests/), uno por UC del proyecto (UC-301.feature..UC-312.feature), en español, con al menos: 1 escenario feliz + 1 escenario negativo cada uno (AC-37, AC-38)
- [ ] El `.feature` de UC-306 del proyecto (webhook idempotencia) usa `Given stripe trigger --replay` explícitamente (AC-39)
- [ ] Crear [.claude/skills/stripe-connect/templates/settings.local.json.fragment.json](.claude/skills/stripe-connect/templates/settings.local.json.fragment.json) — fragmento para mergear (no reemplazar) en `.claude/settings.local.json` del proyecto:
  ```json
  {
    "mcpServers": {
      "stripe": {
        "url": "https://mcp.stripe.com/v1",
        "transport": "http",
        "env": { "STRIPE_API_KEY": "${STRIPE_SECRET_KEY}" }
      }
    }
  }
  ```
  (Verificar URL oficial vigente al momento de implementación — puede variar.) AC-34, AC-35, AC-36
- [ ] Implementar en el SKILL.md la lógica de merge JSON (leer existente → deep merge → escribir) sin perder claves del usuario
- [ ] **Tiempo estimado**: 5h

### Fase 8 — Documentación en el engine + version bump

- [ ] Crear [docs/skills/stripe-connect.md](docs/skills/stripe-connect.md) con secciones: Qué hace, Cuándo usarla, Prerrequisitos (Supabase + React/Flutter onboardeado), Flujo paso a paso (los 12 UCs que genera), Limitaciones v1 explícitas, Enlaces a docs oficiales de Stripe (Connect, Direct charges, Subscriptions embedded) — AC-46
- [ ] Editar [CLAUDE.md](CLAUDE.md) sección "Available Skills (v5.5)" → renombrar a "(v5.25)" y añadir fila:
  ```
  | /stripe-connect | "stripe connect", "marketplace billing", "integrar pagos" | direct | Full | v5.25 — Marketplace Connect + Direct charges + Supabase |
  ```
  (AC-45)
- [ ] Editar [ENGINE_VERSION.yaml](ENGINE_VERSION.yaml): bump `version: 5.25.0`, `codename: "Stripe Connect"`, `release_date: {fecha_merge}` (AC-47)
- [ ] Editar [CHANGELOG.md](CHANGELOG.md): añadir entrada `[5.25.0] - {fecha} — "Stripe Connect"` con descripción de la skill, contador de archivos/templates añadidos, enlaces al PRD y plan
- [ ] **Tiempo estimado**: 4h

### Fase 9 — Tests unitarios del hook + validación end-to-end sobre caso piloto

- [ ] Implementar los 30 casos sintéticos en [.quality/hooks/stripe-safety-guard.test.mjs](.quality/hooks/stripe-safety-guard.test.mjs) — correr con `node --test` y verificar falsos positivos < 5% (AC-29)
- [ ] Integrar test run del hook en [.quality/scripts/specbox-audit.mjs](.quality/scripts/specbox-audit.mjs) o crear [.quality/scripts/hooks-test.sh](.quality/scripts/hooks-test.sh) — para que `/compliance` lo ejecute
- [ ] **Validación end-to-end** (AC-41, AC-42, AC-43, AC-44): hacer una primera pasada manual sobre el proyecto real del marketplace de pilotos (o un proyecto scaffold creado ad-hoc para v1):
  - Correr `/stripe-connect` en el proyecto piloto
  - Verificar que todos los artefactos del PRD se crean sin errores
  - Rellenar envvars del `infra/stripe/README.md` generado
  - Ejecutar `supabase db push` — debe aplicar 4 migraciones sin error
  - Crear piloto de prueba + fan de prueba + completar suscripción con tarjeta `4242 4242 4242 4242`
  - Verificar que `sponsorships.status = 'active'`
  - Verificar que `application_fee.created` refleja el fee dinámico correcto
  - Repetir con un piloto ambassador (fee reducido) para verificar que el fee_percent variable funciona
- [ ] Pasar `/compliance` al engine — verificar que la skill nueva no rompe ningún audit existente (AC-48)
- [ ] **Tiempo estimado**: 8h

### Fase 10 — Dogfooding sobre el engine (opcional, recomendado)

- [ ] El engine mismo **no** va a implementar billing — pero podemos añadir un test de humo que invoque la skill sobre un proyecto fake en `/tmp` para verificar que no crashea en condiciones de stack distintas (React sin Brand Kit, Flutter sin VEG, Supabase vacío)
- [ ] **Tiempo estimado**: 2h

---

## Comandos Finales (post-implementación)

```bash
# Validar que la skill es invocable
ls -la .claude/skills/stripe-connect/

# Validar frontmatter
head -15 .claude/skills/stripe-connect/SKILL.md

# Ejecutar tests del hook
node --test .quality/hooks/stripe-safety-guard.test.mjs

# Ejecutar compliance audit del engine
node .quality/scripts/specbox-audit.mjs . --verbose

# Verificar version bump
grep "^version:" ENGINE_VERSION.yaml  # → 5.25.0
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|----------------|------------------------|-------|
| Envolver API de Stripe en tools MCP del engine | **NO** | Añadir `stripe_create_product`, `stripe_create_price`, etc. al MCP server | Explícitamente rechazado por el usuario: duplica SDK oficial + Stripe MCP oficial, consume contexto innecesario. La skill **orquesta**, no envuelve. |
| Context de la skill | `direct` | `fork + agent: Explore` | La skill escribe ~30 archivos al repo del proyecto consumidor — es operativa, no read-only. Según "Skill Frontmatter Model" de CLAUDE.md, `fork+Explore` es read-only, incorrecto aquí |
| Hook como archivo nuevo | `stripe-safety-guard.mjs` dedicado | Extender `quality-first-guard.mjs` existente | Los antipatrones son dominio-específicos (Stripe). Mezclarlos con el hook general enturbia la responsabilidad y complica tests |
| Storage de templates | `.claude/skills/stripe-connect/templates/` bajo el skill | Reutilizar `infra/stripe/patterns.md` | Patterns.md es referencia humana (docs). Los templates son código parametrizado con placeholders — archivos distintos, responsabilidades distintas |
| Spec backend destino del PRD de ESTA feature | FreeForm local (`doc/prds/`) | Trello/Plane | Confirmado por el usuario: el engine gestiona su propia backlog en el repo |
| Abstracción de backends (Neon/Firestore/FastAPI) | **Fuera de v1** | Generar templates para los 4 ahora | YAGNI. Alcance explícito del PRD. Se añaden solo cuando haya proyecto real que lo pida |
| SaaS vanilla (skill `/stripe` hermana) | **v2** | Implementar ahora como modo de `/stripe-connect` | Camino B: dos skills hermanas. Mezclar SaaS + Connect en un solo skill lo hace inmantenible. `/stripe` reutilizará templates depurados con Connect |
| Charge model | **Direct charges** | Destination charges / Separate charges | Constraint fiscal del caso piloto (autónomo España no puede ser merchant of record del importe total) |
| Checkout UX | Payment Element + Payment Sheet (embedded-only) | Checkout Session hosted | UX rota por redirect a stripe.com, pérdida de control, statement con dominio de Stripe — rechazado explícitamente por el usuario |
| Customer Portal | **Fuera de v1** (cancelación via API propia en UC-309 del proyecto) | Reutilizar Portal | Con Direct charges el Customer vive en la connected account → Portal de plataforma no gestiona subs del fan al piloto. API propia es la ruta correcta |
| Account Type | **Express** | Standard / Custom | Express = KYC hospedado por Stripe + Express Dashboard para el piloto sin UI propia. Custom duplica el trabajo; Standard saca al piloto a stripe.com durante toda la vida del account |
| Onboarding Flutter | Account Link redirect | Connect embedded components | Los componentes embedded de Connect no tienen equivalente nativo Flutter a fecha 2026-04. React sí (`@stripe/react-connect-js`) pero mantener asimetría entre stacks complica mantenimiento → **uniforme con redirect** |
| Migraciones SQL | `CREATE IF NOT EXISTS` idempotentes | Migraciones no idempotentes | Dev puede re-correr la skill sin romper estado existente |
| Estado Flutter | Detectar Riverpod/BLoC del proyecto | Hardcodear uno | Respetar convención del proyecto consumidor. Detectable por presencia de deps en `pubspec.yaml` |

---

## Archivos a Crear/Modificar

```
specbox-engine/
├── .claude/
│   ├── skills/
│   │   └── stripe-connect/                              ← NUEVO
│   │       ├── SKILL.md                                 ← NUEVO (12 pasos)
│   │       └── templates/
│   │           ├── supabase/
│   │           │   ├── functions/
│   │           │   │   ├── create-rider-account-link/index.ts       ← NUEVO
│   │           │   │   ├── create-fan-subscription/index.ts         ← NUEVO
│   │           │   │   ├── cancel-fan-subscription/index.ts         ← NUEVO
│   │           │   │   ├── create-rider-dashboard-link/index.ts     ← NUEVO
│   │           │   │   └── stripe-webhook/index.ts                  ← NUEVO
│   │           │   └── migrations/
│   │           │       ├── 001_riders_stripe_account.sql            ← NUEVO
│   │           │       ├── 002_sponsorships.sql                     ← NUEVO
│   │           │       ├── 003_stripe_processed_events.sql          ← NUEVO
│   │           │       └── 004_rls_policies.sql                     ← NUEVO
│   │           ├── react/
│   │           │   ├── stripe-provider.tsx                          ← NUEVO
│   │           │   ├── sponsor-rider-form.tsx                       ← NUEVO
│   │           │   ├── use-sponsorship.ts                           ← NUEVO
│   │           │   ├── rider-onboarding-button.tsx                  ← NUEVO
│   │           │   └── package.json.fragment.json                   ← NUEVO
│   │           ├── flutter/
│   │           │   ├── stripe_service.dart                          ← NUEVO
│   │           │   ├── sponsor_rider_controller.dart                ← NUEVO
│   │           │   ├── apple_pay_button.dart                        ← NUEVO
│   │           │   ├── google_pay_button.dart                       ← NUEVO
│   │           │   ├── rider_onboarding_launcher.dart               ← NUEVO
│   │           │   ├── api_interceptor.dart                         ← NUEVO
│   │           │   └── pubspec.fragment.yaml                        ← NUEVO
│   │           ├── docs/
│   │           │   ├── infra-stripe-README.md                       ← NUEVO
│   │           │   ├── connect-setup.md                             ← NUEVO
│   │           │   ├── apple-google-pay-setup.md                    ← NUEVO
│   │           │   ├── events-catalog.md                            ← NUEVO
│   │           │   └── test-scenarios.md                            ← NUEVO
│   │           ├── hooks/
│   │           │   └── stripe-safety-guard.mjs                      ← NUEVO (copia consumible)
│   │           ├── tests/
│   │           │   ├── UC-301.feature ... UC-312.feature            ← NUEVO (12 archivos)
│   │           └── settings.local.json.fragment.json                ← NUEVO
│   ├── hooks/
│   │   └── stripe-safety-guard.mjs                                  ← NUEVO (source dogfood)
│   └── settings.json                                                ← MODIFICAR (añadir hook entry)
├── .quality/
│   ├── hooks/
│   │   └── stripe-safety-guard.test.mjs                             ← NUEVO (30 casos)
│   └── scripts/
│       └── hooks-test.sh                                            ← NUEVO (opcional)
├── templates/
│   └── settings.json.template                                       ← MODIFICAR (añadir hook entry)
├── docs/skills/
│   └── stripe-connect.md                                            ← NUEVO
├── CLAUDE.md                                                        ← MODIFICAR (Available Skills + Hooks tables)
├── ENGINE_VERSION.yaml                                              ← MODIFICAR (5.24 → 5.25.0)
└── CHANGELOG.md                                                     ← MODIFICAR (entrada 5.25.0)
```

**Totales**:
- **36 archivos nuevos**
- **5 archivos modificados**
- **~60h estimadas** (10+10+6+6+5+4+5+4+8+2)

---

## Orden de implementación recomendado

1. **Fase 1** (andamiaje) → antes de nada, fijar contrato del SKILL.md
2. **Fase 5 + Fase 9 parcial** (hook + sus tests) → fundamento de seguridad, útil para dogfooding desde el minuto 0
3. **Fase 2** (Supabase backend) → corazón de la integración
4. **Fase 3 O Fase 4** (React O Flutter — ambos son paralelizables; empezar por el que tenga proyecto piloto listo)
5. **Fase 6** (docs) → se escribe mejor cuando los templates de código están fijados
6. **Fase 7** (Gherkin + MCP) → rápido, cableado mecánico
7. **Fase 3/4 restante** — completar el otro stack frontend
8. **Fase 8** (bump de versión + docs del engine) → penúltimo, para no mover version mid-implementación
9. **Fase 9** (validación end-to-end) → sobre proyecto piloto real
10. **Fase 10** (dogfooding test de humo) → último

---

## Checkpoints para `/implement`

Dado que esta skill es compleja (~60h, 36 archivos nuevos) y `/implement` trabaja UC a UC, recomiendo esta subdivisión al pasar al pipeline:

| UC del proyecto engine (se crean al invocar `/stripe-connect` sobre el engine mismo, dogfooding) | Fases del plan |
|---|---|
| UC-301..UC-302 de este plan → "Skill scaffolding" | Fase 1 |
| UC-303 → "Supabase backend templates" | Fase 2 |
| UC-304 → "React frontend templates" | Fase 3 |
| UC-305 → "Flutter frontend templates" | Fase 4 |
| UC-306 → "Stitch integration" (en runtime de la skill, no hay código que escribir en el engine para esto aparte del SKILL.md paso 7) | Cubierto en Fase 1 |
| UC-307 → "Safety hook" | Fase 5 |
| UC-308 → "Parametrized docs" | Fase 6 |
| UC-309 → "Stripe MCP wiring" | Fase 7 (parte MCP) |
| UC-310 → "Gherkin templates" | Fase 7 (parte tests) |
| UC-311 → "End-to-end validation" | Fase 9 |
| UC-312 → "Engine docs + version bump" | Fase 8 |

O, alternativamente (más simple): tratar este plan como **una única unidad monolítica** no iterable por `/implement`, implementarla manualmente a lo largo de ~2 semanas, y luego usar `/stripe-connect` sobre el caso piloto como validación. Mi recomendación: **monolítica** — la estructura es demasiado fina para beneficiarse del ciclo UC por UC.

---

## Referencias

- PRD: [doc/prds/stripe_connect_skill_prd.md](../prds/stripe_connect_skill_prd.md)
- Frontmatter model reference: [CLAUDE.md](../../CLAUDE.md) sección "Skill Frontmatter Model"
- Skill direct ejemplos: [.claude/skills/prd/SKILL.md](../../.claude/skills/prd/SKILL.md), [.claude/skills/release/SKILL.md](../../.claude/skills/release/SKILL.md), [.claude/skills/feedback/SKILL.md](../../.claude/skills/feedback/SKILL.md)
- Hook pattern reference: [.claude/hooks/spec-guard.mjs](../../.claude/hooks/spec-guard.mjs), [.claude/hooks/quality-first-guard.mjs](../../.claude/hooks/quality-first-guard.mjs)
- Stitch MCP integration: [server/stitch_client.py](../../server/stitch_client.py), [server/tools/stitch.py](../../server/tools/stitch.py)
- Stripe docs consultadas: [docs.stripe.com/connect](https://docs.stripe.com/connect), [docs.stripe.com/billing/subscriptions](https://docs.stripe.com/billing/subscriptions), [docs.stripe.com/api/events/types](https://docs.stripe.com/api/events/types), [docs.stripe.com/webhooks](https://docs.stripe.com/webhooks)
- Stripe CLI docs: [docs.stripe.com/stripe-cli](https://docs.stripe.com/stripe-cli), test clocks: [docs.stripe.com/billing/testing/test-clocks](https://docs.stripe.com/billing/testing/test-clocks)
