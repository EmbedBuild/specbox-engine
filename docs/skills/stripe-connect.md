# `/stripe-connect` — Stripe Connect marketplace scaffolder

> Introducida en **SpecBox Engine v5.25.0** — "Stripe Connect"

Scaffoldea una integración de pagos **Stripe Connect marketplace** completa en proyectos SpecBox con stack Supabase + React/Flutter. Pasa de ~3 semanas de trabajo manual a ~3 días con estructura correcta por defecto (idempotencia, firma de webhooks, SCA en connected accounts, UX embedded, fee dinámico por seller).

La skill **no envuelve la API de Stripe**. Orquesta piezas del ecosistema ya existentes:
- **SDK oficial** de Stripe para el código de producción
- **Stripe MCP oficial** para operaciones runtime del developer (crear products, listar customers…)
- **Stripe CLI** para testing (`stripe listen`, `stripe trigger`, test clocks)
- **Stitch MCP** para diseños de pantallas (si el proyecto tiene VEG)
- **Pipeline spec-driven** para crear los UCs en Trello/Plane/FreeForm

---

## Qué hace

Al ejecutar `/stripe-connect` en un proyecto SpecBox onboardeado, en ~5 minutos:

1. **Detecta** stack frontend (React / Flutter Web / Flutter Mobile), backend (Supabase obligatorio), spec backend activo y presencia de VEG
2. **Pregunta** 2 cosas: confirmación del stack y fee default en %
3. **Muestra plan** de archivos a crear y pide confirmación explícita
4. **Crea** US-SPONSORSHIP + 12 UCs (UC-301..UC-312) en el spec backend del proyecto
5. **Escribe** ~30 archivos parametrizados:
   - 5 Edge Functions Supabase + 4 migraciones SQL con RLS
   - 5 archivos React o 7 archivos Flutter (según stack)
   - 5 docs (README setup, Connect setup, Apple/Google Pay, events catalog, test scenarios)
   - 12 Gherkin `.feature` de aceptación
6. **Instala** el hook `stripe-safety-guard.mjs` en `.claude/hooks/`
7. **Genera** 6 diseños Stitch en `doc/design/sponsorship/` (si hay VEG, skip limpio si no)
8. **Cablea** el Stripe MCP oficial en `.claude/settings.local.json` del proyecto

El dev a partir de ahí rellena 4 envvars del checklist, corre `supabase db push`, arranca `stripe listen` y ejecuta `/plan UC-301` para empezar por el onboarding del seller.

---

## Cuándo usarla

Cuando necesites **pagos marketplace** (fan→seller, comprador→vendedor, etc.) en una app con:

- Backend **Supabase** (Edge Functions + Postgres)
- Frontend **React** (19+) o **Flutter** (3.38+, Web o Mobile)
- Modelo de negocio: **subscriptions recurrentes** con fee de plataforma dinámico por seller

**No la uses si**:
- Tu modelo es SaaS vanilla (subscriptions sin terceros) → espera a `/stripe` en v2
- Tu backend no es Supabase → v2 cuando aparezcan proyectos reales que lo necesiten
- Necesitas Destination charges (la plataforma es merchant of record) → usa `infra/stripe/patterns.md` manualmente
- Necesitas React Native → no está soportado en SpecBox

---

## Prerrequisitos

Antes de invocar:

1. Proyecto onboardeado con `onboard_project` (o `.claude/settings.*` presentes)
2. Supabase CLI inicializado (`supabase init` + `supabase/config.toml`)
3. React 19 + Vite **o** Flutter 3.38+ con `ios/` y `android/` si es mobile
4. (Opcional pero recomendado) `/visual-setup` ejecutado previamente — genera Brand Kit que parametriza el appearance del Payment Element/Sheet
5. Stripe CLI instalado localmente (`stripe --version`)
6. Cuenta Stripe con Connect activable en dashboard

---

## Flujo paso a paso de los 12 UCs que genera

| UC | Título | Actor |
|----|--------|-------|
| UC-301 | Onboarding del piloto con advertencia fiscal (Account Link Express) | Piloto (seller) |
| UC-302 | Retorno post-onboarding: activación del perfil tras `account.updated` | Sistema |
| UC-303 | Piloto con onboarding incompleto no aparece en listado público | Sistema |
| UC-304 | Fan ve perfil del piloto y elige plan 10/15/20€ | Fan |
| UC-305 | Fan se suscribe con Payment Element/Sheet embedded + fee dinámico | Fan |
| UC-306 | Webhook handler con firma + idempotencia (tabla `stripe_processed_events`) | Sistema |
| UC-307 | Sincronización DB sponsorships con events Stripe | Sistema |
| UC-308 | Payment failed → status past_due → retry UX | Fan + Piloto |
| UC-309 | Fan cancela suscripción desde su área (API en connected account) | Fan |
| UC-310 | Rider dashboard con MRR + Express Dashboard link | Piloto |
| UC-311 | Admin dashboard: total fees + export CSV para gestor | Admin |
| UC-312 | Apple Pay / Google Pay / Express Checkout Element default on | Fan |

Cada UC genera sus ACs + un `.feature` Gherkin listo para consumir por AG-09a del pipeline `/implement`.

---

## Qué archivos crea en el proyecto consumidor

```
proyecto/
├── supabase/
│   ├── functions/
│   │   ├── create-rider-account-link/index.ts
│   │   ├── create-fan-subscription/index.ts       ← application_fee_percent dinámico
│   │   ├── cancel-fan-subscription/index.ts
│   │   ├── create-rider-dashboard-link/index.ts
│   │   └── stripe-webhook/index.ts                ← firma dual + idempotencia
│   └── migrations/
│       ├── NNN_riders_stripe_account.sql
│       ├── NNN_sponsorships.sql
│       ├── NNN_stripe_processed_events.sql
│       └── NNN_rls_policies.sql
├── src/billing/               # si stack=react
│   ├── stripe-provider.tsx
│   ├── sponsor-rider-form.tsx
│   ├── use-sponsorship.ts
│   └── rider-onboarding-button.tsx
├── lib/billing/               # si stack=flutter
│   ├── stripe_service.dart
│   ├── sponsor_rider_controller.dart
│   ├── apple_pay_button.dart
│   ├── google_pay_button.dart
│   ├── rider_onboarding_launcher.dart
│   └── api_interceptor.dart
├── infra/stripe/
│   ├── README.md              ← checklist 4-6 pasos con envvars
│   ├── connect-setup.md
│   └── apple-google-pay-setup.md   # solo Flutter
├── doc/design/billing/
│   ├── events-catalog.md      ← 10 eventos críticos v1
│   └── test-scenarios.md      ← stripe trigger + test clocks
├── doc/design/sponsorship/     # solo si hay VEG
│   └── {6 HTMLs de Stitch}
├── tests/acceptance/sponsorship/
│   └── UC-301.feature ... UC-312.feature
├── .claude/hooks/
│   └── stripe-safety-guard.mjs
└── .claude/settings.*.json    ← actualizado (hook + Stripe MCP)
```

---

## Limitaciones v1

| Dimensión | v1 | v2+ |
|-----------|-----|------|
| Backend | Supabase | Neon, Firestore, FastAPI (on demand) |
| Frontend | React + Flutter | React Native (si entra en SpecBox) |
| Account type | Express | Standard, Custom |
| Charge model | Direct charges | Destination, Separate |
| Checkout UX | Embedded only | Hosted opcional (nunca) |
| Customer Portal | No (Direct charges lo rompe) | — |
| Subscriptions | Sí | — |
| One-time payments | Mediante cambio manual | Skill `/stripe` hermana |
| Connect embedded onboarding | No (redirect Account Link) | Cuando Flutter lo soporte |
| Refunds, disputes, proration | Fuera | Por UC específico cuando aparezca |
| Multi-currency, Stripe Tax | Fuera | — |

---

## Advertencias

### Fiscales (España)

Los sellers que recibirán Direct charges **deben estar dados de alta como autónomos** (o disponer de sociedad) antes de conectar su cuenta Stripe. De lo contrario Hacienda puede reclamarles IRPF sin que hayan facturado correctamente, y tu plataforma queda en una zona gris reputacional.

El UC-301 del proyecto consumidor incluye warning explícito antes del Account Link. Verifica que tu UI lo muestra. **No es asesoramiento legal** — consulta con gestor antes de lanzar.

### Stripe MCP oficial

El fragmento de `settings.local.json.fragment.json` usa la URL pública del Stripe MCP al momento de generar la skill. Antes de lanzar en producción, verifica en https://docs.stripe.com/mcp la URL vigente y ajústala si Stripe la cambia.

### Hook `stripe-safety-guard` vs productividad

El hook es agresivo por diseño: prevenir los errores típicos (webhook sin firma, handlers sin idempotencia, Payment Links) es su razón de ser. Si en un caso legítimo te bloquea, usa los escape hatches (`// stripe-safety-guard:ignore`, `:disable-file`) documentando **en el mismo archivo** por qué. Si los usas en >2 archivos, probablemente la regla está mal calibrada — abre un issue.

---

## Referencias

- **PRD**: [doc/prds/stripe_connect_skill_prd.md](../../doc/prds/stripe_connect_skill_prd.md)
- **Plan técnico**: [doc/plans/stripe_connect_skill_plan.md](../../doc/plans/stripe_connect_skill_plan.md)
- **Skill source**: [.claude/skills/stripe-connect/SKILL.md](../../.claude/skills/stripe-connect/SKILL.md)
- **Stripe docs**:
  - [Connect Overview](https://docs.stripe.com/connect)
  - [Direct Charges](https://docs.stripe.com/connect/direct-charges)
  - [Express Accounts](https://docs.stripe.com/connect/express-accounts)
  - [Subscriptions Build](https://docs.stripe.com/billing/subscriptions/build-subscriptions)
  - [Webhooks](https://docs.stripe.com/webhooks)
  - [Testing](https://docs.stripe.com/testing) · [Test Clocks](https://docs.stripe.com/billing/testing/test-clocks)
  - [Apple Pay setup](https://docs.stripe.com/apple-pay) · [Google Pay setup](https://docs.stripe.com/google-pay)
