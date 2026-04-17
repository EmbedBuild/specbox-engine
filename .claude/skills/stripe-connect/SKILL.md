---
name: stripe-connect
description: >
  Scaffolds a Stripe Connect marketplace integration (Express + Direct charges +
  subscriptions embedded) in Supabase + React/Flutter projects. Generates
  US-SPONSORSHIP with 12 UCs in the project's spec backend, backend Edge
  Functions + SQL migrations with RLS, frontend templates with Payment
  Element/Sheet + Apple/Google Pay + Express Checkout, Stitch designs (if VEG
  configured), stripe-safety-guard hook, events catalog, and wires the official
  Stripe MCP. Use when the user says "stripe connect", "marketplace billing",
  "integrar pagos marketplace", "implementar pagos stripe", "monta pagos
  marketplace". v1 scope: Supabase only, Connect Express only, Direct charges
  only, subscriptions only.
context: direct
allowed-tools: Read, Grep, Glob, Bash(*), Write, Edit, mcp__specbox-engine__*, mcp__stitch__*
---

# /stripe-connect — Marketplace Connect integration scaffolder

Genera en un solo comando la integración de Stripe Connect marketplace para un proyecto SpecBox: 12 UCs en el backlog + templates backend Supabase + templates frontend React/Flutter + diseños Stitch (si VEG) + hook de seguridad + docs parametrizadas + Stripe MCP cableado.

La skill **NO envuelve la API de Stripe**. Orquesta piezas existentes (SDK oficial, Stripe MCP oficial, Stripe CLI, pipeline spec-driven, Stitch MCP) con opinión fuerte: **Connect Express + Direct charges + subscriptions embedded-only**.

## Uso

```
/stripe-connect
```

Sin argumentos. La skill detecta todo del proyecto y pregunta solo lo imprescindible.

## Alcance v1 (opinionado)

| Dimensión | Decisión |
|-----------|----------|
| Backend | **Supabase únicamente** (Neon/Firestore/FastAPI → v2 si hay demanda real) |
| Frontend | React 19 o Flutter 3.38+ (Web + Mobile) |
| Account type | Stripe Connect Express |
| Charge model | Direct charges (no Destination, no Separate) |
| Subscriptions | Sí (es el modelo core) |
| Checkout UX | Embedded-only: Payment Element (React) + Payment Sheet (Flutter) |
| Apple/Google Pay | Default on |
| Customer Portal | Fuera (Direct charges → Customer vive en connected account) |
| Marketplace de referencia | Fan suscribe a seller con fee dinámico vía `application_fee_percent` |

Si tu caso no encaja con esto, sal de la skill y usa `infra/stripe/patterns.md` manualmente, o espera a `/stripe` (SaaS vanilla) en v2.

---

## Paso 0 — Preflight: detectar entorno del proyecto

### 0.1 Validar que estamos en un proyecto SpecBox onboardeado

```bash
test -f .claude/settings.local.json || test -f .claude/settings.json || {
  echo "ERROR: Este directorio no parece un proyecto SpecBox. Ejecuta 'onboard_project' primero."
  exit 1
}
```

### 0.2 Detectar stack frontend

```bash
# React
if [ -f package.json ] && grep -q '"react"' package.json; then STACK="react"; fi

# Flutter
if [ -f pubspec.yaml ] && grep -q "flutter:" pubspec.yaml; then
  # Distinguir Web vs Mobile por platforms
  if [ -d ios ] || [ -d android ]; then STACK="flutter-mobile"; else STACK="flutter-web"; fi
fi
```

Si no detecta ni React ni Flutter → abortar con mensaje: *"v1 solo soporta React o Flutter. Otros stacks no están cubiertos."*

### 0.3 Detectar backend Supabase (obligatorio en v1)

```bash
test -d supabase && test -f supabase/config.toml || {
  echo "ERROR: v1 de /stripe-connect requiere Supabase CLI inicializado."
  echo "Ejecuta 'supabase init' antes de continuar, o espera a v2 para otros backends."
  exit 0
}
```

Si Supabase no está inicializado → salir con exit 0 (no es error del engine, es prerequisito del proyecto). AC-02.

### 0.4 Detectar spec backend activo (Trello / Plane / FreeForm)

Leer `.claude/settings.local.json`:
- `trello.boardId` → Trello
- `plane.defaultProject` → Plane
- Sin ninguno → FreeForm en `doc/tracking/`

### 0.5 Detectar presencia de VEG

```bash
test -d doc/veg && test -f doc/design/brand-kit.md && VEG_PRESENT=true || VEG_PRESENT=false
```

Si VEG está presente, la skill generará diseños Stitch en Paso 7. Si no, skip limpio con aviso.

### 0.6 Resumen al usuario

```
Detectado:
  Stack frontend: {STACK}
  Backend: Supabase ✓
  Spec backend: {Trello|Plane|FreeForm}
  VEG: {Sí (arquetipo X) | No — se saltará Stitch}
```

---

## Paso 1 — Pregunta mínima al usuario (AC-03)

Solo 2 preguntas obligatorias:

1. **Confirmar stack detectado** (`y/n`). Si `n`, salir — el dev debe corregir el proyecto antes de volver.
2. **Fee default en porcentaje** para sellers estándar: número entre 1 y 50. Se usará como `DEFAULT_APPLICATION_FEE_PERCENT` en el template de env vars y como default cuando `riders.fee_percent IS NULL`.

No hay más preguntas. El usuario puede ajustar todo lo demás editando los templates generados.

---

## Paso 2 — Mostrar plan de archivos a crear + confirmación (AC-04)

Antes de escribir nada, mostrar lista completa de archivos que se crearán/modificarán, agrupados por categoría:

```
Voy a crear:
  Backend Supabase (9 archivos):
    supabase/functions/create-rider-account-link/index.ts
    supabase/functions/create-fan-subscription/index.ts
    supabase/functions/cancel-fan-subscription/index.ts
    supabase/functions/create-rider-dashboard-link/index.ts
    supabase/functions/stripe-webhook/index.ts
    supabase/migrations/NNN_riders_stripe_account.sql
    supabase/migrations/NNN_sponsorships.sql
    supabase/migrations/NNN_stripe_processed_events.sql
    supabase/migrations/NNN_rls_policies.sql

  Frontend {react|flutter} (N archivos):
    ...

  Documentación (5 archivos):
    infra/stripe/README.md
    infra/stripe/connect-setup.md
    infra/stripe/apple-google-pay-setup.md  (solo Flutter)
    doc/design/billing/events-catalog.md
    doc/design/billing/test-scenarios.md

  Tests de aceptación (12 archivos):
    tests/acceptance/sponsorship/UC-301.feature
    ... UC-312.feature

  Hook de seguridad:
    .claude/hooks/stripe-safety-guard.mjs
    .claude/settings.json (modificado: añade PreToolUse entry)

  MCP externo:
    .claude/settings.local.json (modificado: añade Stripe MCP oficial)

  Spec backend:
    {N} US-SPONSORSHIP + 12 UCs con ACs generados

Total: ~30 archivos nuevos + 2 modificados.
¿Continuar? (s/n)
```

Si `n` → abortar sin escribir nada. Si `s` → proceder.

---

## Paso 3 — Crear US-SPONSORSHIP + 12 UCs en spec backend (AC-05..AC-08)

Usar tools del MCP SpecBox según backend detectado:

```
spec = {
  "us": [{
    "id": "US-SPONSORSHIP",
    "name": "Integración de pagos marketplace con Stripe Connect",
    "description": "Marketplace con fans suscribiendo a sellers vía Stripe Connect Express + Direct charges + application_fee_percent dinámico. Generado por /stripe-connect v5.25.0.",
    "hours": 90,
    "ucs": [
      {"id": "UC-301", "name": "Onboarding de seller (piloto) vía Account Link Express", "actor": "Seller", "hours": 6, ...},
      {"id": "UC-302", "name": "Retorno post-onboarding: activación de perfil", "actor": "Sistema", "hours": 4, ...},
      ... (12 UCs totales)
    ]
  }]
}
```

Cada UC con **mínimo 3 ACs** redactados para pasar el Definition Quality Gate (score ≥ 1.5/2.0). Los AC templates viven en `templates/tests/UC-NNN.feature` y se generan en Paso 10, pero los títulos/descripciones de los ACs se escriben en el spec backend aquí.

### 3.1 Fallback si el spec backend está offline (AC-08)

Try/catch sobre la llamada MCP. Si falla:
```
⚠ Spec backend {Trello|Plane} no responde. Guardando como FreeForm local en doc/tracking/.
```
Llamar `set_auth_token(backend_type="freeform", root_path="doc/tracking")` y reintentar `import_spec`.

---

## Paso 4 — Escribir templates backend Supabase (AC-09..AC-13)

Copiar y parametrizar desde `.claude/skills/stripe-connect/templates/supabase/`:

### 4.1 Edge Functions

5 funciones copiadas a `supabase/functions/` del proyecto:
- `create-rider-account-link/index.ts`
- `create-fan-subscription/index.ts` — usa `application_fee_percent` dinámico desde `riders.fee_percent` (fallback env `DEFAULT_APPLICATION_FEE_PERCENT={fee_default}`), `payment_behavior: 'default_incomplete'`, expansión `pending_setup_intent`
- `cancel-fan-subscription/index.ts`
- `create-rider-dashboard-link/index.ts`
- `stripe-webhook/index.ts` — verificación firma con `constructEventAsync`, routing platform vs connect por header, idempotencia con tabla `stripe_processed_events`

Placeholders a sustituir: `{project_name}`, `{fee_default}`.

### 4.2 Migraciones SQL

4 migraciones copiadas a `supabase/migrations/` con timestamp prefix:
- `NNN_riders_stripe_account.sql` — columnas `stripe_account_id`, `fee_percent NULL`, `onboarding_status`
- `NNN_sponsorships.sql` — tabla completa
- `NNN_stripe_processed_events.sql` — idempotencia
- `NNN_rls_policies.sql` — RLS sobre sponsorships + riders

Todas con `CREATE ... IF NOT EXISTS` para idempotencia (AC-13).

### 4.3 Verificación

```bash
# Opcional: intentar aplicar migraciones localmente si supabase está corriendo
if supabase status 2>/dev/null | grep -q "API URL"; then
  echo "Aplicando migraciones a Supabase local..."
  supabase db push --local && echo "✓ Migraciones aplicadas" || echo "⚠ Revisa los logs de Supabase"
fi
```

---

## Paso 5 — Escribir templates frontend (AC-14..AC-21)

Según `STACK` detectado en Paso 0:

### 5.1 Si STACK=react

Copiar desde `templates/react/` a `src/billing/` del proyecto:
- `stripe-provider.tsx` — `<Elements>` con `appearance` parametrizada
- `sponsor-rider-form.tsx` — `<PaymentElement>` + `<ExpressCheckoutElement>`
- `use-sponsorship.ts` — hook estado loading/success/error/requires_action
- `rider-onboarding-button.tsx`

**Brand Kit integration (AC-16)**:
```bash
if [ -f doc/design/brand-kit.md ]; then
  # Extraer colorPrimary, fontFamily, borderRadius del brand-kit
  # Sustituir en stripe-provider.tsx
else
  # Dejar valores neutros + comentario TODO
fi
```

Mergear dependencias en `package.json` del proyecto (no reemplazar):
```json
{ "@stripe/stripe-js": "^3", "@stripe/react-stripe-js": "^2" }
```

### 5.2 Si STACK=flutter-web o flutter-mobile

Copiar desde `templates/flutter/` a `lib/billing/` del proyecto:
- `stripe_service.dart` — init + Apple Pay + Google Pay con `merchantCountryCode: 'ES'` default
- `sponsor_rider_controller.dart` — detectar si proyecto usa Riverpod o BLoC (`grep -l "flutter_bloc\|flutter_riverpod" pubspec.yaml`) y generar la variante correspondiente
- `apple_pay_button.dart` + `google_pay_button.dart`
- `rider_onboarding_launcher.dart`
- `api_interceptor.dart` — añade `Stripe-Account` header

Mergear deps en `pubspec.yaml`:
```yaml
dependencies:
  flutter_stripe: ^10.0.0
  url_launcher: ^6.0.0
```

**Apple Pay + Google Pay default on** (AC-20): los templates no tienen TODOs — vienen activos. El dev puede desactivarlos comentando manualmente si quiere.

---

## Paso 6 — Instalar hook `stripe-safety-guard` (AC-26..AC-29)

### 6.1 Copiar hook al proyecto

```bash
cp .claude/skills/stripe-connect/templates/hooks/stripe-safety-guard.mjs \
   {PROJECT_ROOT}/.claude/hooks/stripe-safety-guard.mjs
```

### 6.2 Registrar en `.claude/settings.json` del proyecto

Añadir (merge no-destructivo) bajo `hooks.PreToolUse`:
```json
{
  "matcher": "Write|Edit",
  "hooks": [{
    "type": "command",
    "command": "node .claude/hooks/stripe-safety-guard.mjs"
  }]
}
```

El hook bloquea con exit 2:
1. `sk_live_*` en código (no en `.env*` ni `.md`)
2. Handler webhook sin `constructEvent`/`constructEventAsync`
3. Edge Function que procesa eventos sin consultar `stripe_processed_events`
4. Import de `redirectToCheckout` o `ui_mode: 'hosted'`
5. URL de Payment Link `https://buy.stripe.com/`

Escape hatch: `// stripe-safety-guard:ignore` en la línea previa al patrón.

---

## Paso 7 — Generar diseños Stitch si VEG presente (AC-22..AC-25)

Si `VEG_PRESENT=false` → skip con mensaje:
```
⚠ No se detectó VEG en el proyecto. Saltando generación de diseños Stitch.
  Ejecuta /visual-setup antes de /stripe-connect para diseños coherentes con tu brand.
```

Si `VEG_PRESENT=true`:

### 7.1 Leer arquetipo VEG activo

```bash
ARCHETYPE=$(grep "^archetype:" doc/veg/*.md | head -1 | awk '{print $2}')
# Ejemplo: Corporate | Startup | Creative | Consumer | Gen-Z | Gobierno
```

### 7.2 Invocar Stitch 6 veces

Prompts pre-armados en `templates/stitch-prompts/{screen}.txt`, adaptados por arquetipo:

1. `rider-onboarding` — pantalla piloto con CTA Account Link + warning autónomo
2. `rider-public-profile` — perfil piloto con 3 planes (10/15/20€)
3. `sponsor-modal` — **contenedor del Payment Element/Sheet embebido**, NO redirect a Stripe
4. `sponsorship-success` — confirmación inline
5. `fan-subscriptions` — gestión de suscripciones del fan
6. `rider-dashboard` — MRR, sponsors, Express Dashboard link

Para cada pantalla:
```
mcp__stitch__generate_screen_from_text(
  projectId: "{stitch_project_id}",
  prompt: "{prompt_adaptado_arquetipo}",
  deviceType: "DESKTOP",
  modelId: "GEMINI_3_PRO"
)
```

Guardar HTMLs en `doc/design/sponsorship/{screen}.html` y registrar prompts en `doc/design/sponsorship/stitch_prompts.md`.

**Regla obligatoria en prompts (AC-25)**: nunca pedir "botón que redirige a Stripe Checkout". Siempre: *"contenedor modal que aloja el Payment Element de Stripe embedded, con header precio/plan, form interno, footer Powered by Stripe"*.

### 7.3 Fallback si Stitch falla

```
⚠ Stitch no respondió a tiempo. Generando PENDING_DESIGNS.md con los 6 prompts.
   Puedes re-ejecutar manualmente con: mcp__stitch__generate_screen_from_text(...)
```

---

## Paso 8 — Escribir documentación parametrizada (AC-30..AC-33)

Copiar desde `templates/docs/` al proyecto:

- `infra/stripe/README.md` — checklist 4-6 pasos: envvars exactas (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET_PLATFORM`, `STRIPE_WEBHOOK_SECRET_CONNECT`, `STRIPE_PUBLISHABLE_KEY`, `DEFAULT_APPLICATION_FEE_PERCENT={fee_default}`), comando `stripe listen --forward-to`, activación Connect en dashboard
- `infra/stripe/connect-setup.md` — pasos específicos de Connect: branding Express onboarding, test sellers por país
- `infra/stripe/apple-google-pay-setup.md` — solo si STACK=flutter-*: Merchant ID Apple, domain verification, entitlements iOS, manifest Android
- `doc/design/billing/events-catalog.md` — 10 eventos críticos v1 con: trigger, endpoint plataforma vs Connect, acción backend, fila DB modificada
- `doc/design/billing/test-scenarios.md` — bloques `stripe trigger` + test clocks por UC

---

## Paso 9 — Cablear Stripe MCP oficial (AC-34..AC-36)

### 9.1 Leer `.claude/settings.local.json` del proyecto (o crearlo si no existe)

```bash
if [ ! -f .claude/settings.local.json ]; then
  echo '{"permissions":{"allow":[]},"mcpServers":{}}' > .claude/settings.local.json
fi
```

### 9.2 Merge no-destructivo del fragmento

Leer `settings.local.json`, mergear la clave `mcpServers.stripe` desde `templates/settings.local.json.fragment.json` **sin tocar el resto**:

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

Usar `jq` para el merge (está disponible por defecto en macOS/Linux):
```bash
jq -s '.[0] * .[1]' .claude/settings.local.json templates/settings.local.json.fragment.json > .claude/settings.local.json.tmp \
  && mv .claude/settings.local.json.tmp .claude/settings.local.json
```

Aviso al usuario:
```
✓ Stripe MCP oficial cableado. En una nueva sesión de Claude Code, las tools
  mcp__stripe__* estarán disponibles. Ejemplo: "Crea en Stripe los Products
  Básico/Pro con Prices 10/15/20€ en modo test".
```

---

## Paso 10 — Generar Gherkin `.feature` de aceptación (AC-37..AC-40)

Copiar 12 `.feature` desde `templates/tests/` a `tests/acceptance/sponsorship/` del proyecto:

```
tests/acceptance/sponsorship/
├── UC-301.feature   # Onboarding seller Account Link
├── UC-302.feature   # Retorno onboarding
├── UC-303.feature   # Piloto incompleto oculto
├── UC-304.feature   # Fan elige plan
├── UC-305.feature   # Suscripción con Payment Element/Sheet + fee dinámico
├── UC-306.feature   # Webhook firma + idempotencia (usa stripe trigger --replay)
├── UC-307.feature   # Sync DB sponsorships
├── UC-308.feature   # Payment failed retry
├── UC-309.feature   # Fan cancela
├── UC-310.feature   # Rider dashboard
├── UC-311.feature   # Admin dashboard + export
└── UC-312.feature   # Apple/Google Pay / Express Checkout
```

Cada `.feature` en español, con mínimo 1 flujo feliz + 1 escenario negativo, y comandos `stripe trigger` listos para ejecutar (AC-38, AC-39).

---

## Paso 11 — Resumen final + siguiente paso

Al terminar todos los pasos:

```
✓ /stripe-connect completado.

Creado:
  - US-SPONSORSHIP + 12 UCs en {spec_backend}
  - {N} archivos backend Supabase
  - {N} archivos frontend {react|flutter}
  - {6|0} diseños Stitch en doc/design/sponsorship/
  - Hook stripe-safety-guard instalado
  - Stripe MCP oficial cableado
  - {12} tests Gherkin de aceptación

Siguientes pasos (en orden):

1. Rellena las envvars de infra/stripe/README.md (5 minutos):
   STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET_PLATFORM,
   STRIPE_WEBHOOK_SECRET_CONNECT, STRIPE_PUBLISHABLE_KEY

2. Activa Connect en dashboard.stripe.com/test/connect

3. Aplica migraciones:
   supabase db push

4. Arranca el relay de webhooks (otra terminal):
   stripe listen --forward-to http://localhost:54321/functions/v1/stripe-webhook

5. Ejecuta /plan UC-301 para empezar por el onboarding del seller.

Advertencia fiscal (España):
  Los sellers necesitan estar dados de alta como autónomos o disponer de
  sociedad para recibir Direct charges. Tu skill UC-301 ya incluye este
  warning en el flujo de onboarding.
```

---

## Paso 12 — Telemetría + Engram (opcional)

Registrar ejecución exitosa:
```bash
# Telemetría fire-and-forget (si el engine MCP está configurado)
node .claude/hooks/mcp-report.mjs stripe-connect-executed '{"stack":"{STACK}","veg":{VEG_PRESENT}}'
```

Si `mcp__plugin_engram_engram__mem_save` disponible, guardar observación:
```
mem_save(
  title="stripe-connect executed",
  type="config",
  content="**What**: /stripe-connect ejecutado sobre proyecto {project}. **Stack**: {STACK}. **Fee default**: {fee_default}%. **VEG**: {VEG_PRESENT}."
)
```

---

## Comportamiento en errores

| Situación | Acción |
|-----------|--------|
| Supabase no inicializado | Exit 0, mensaje al usuario, no escribir nada |
| Stack no detectado (ni React ni Flutter) | Exit 0, mensaje, no escribir nada |
| Spec backend offline | Fallback automático a FreeForm local, avisar al usuario |
| Stitch timeout | Generar PENDING_DESIGNS.md con prompts, continuar sin bloquear |
| `.claude/settings.local.json` inexistente | Crearlo mínimo y continuar |
| Migración SQL falla al aplicar | NO revertir archivos ya escritos, avisar al usuario con el error y sugerir `supabase db reset` manual |
| Usuario responde `n` en Paso 2 | Abortar sin escribir nada |
| Hook `stripe-safety-guard` ya presente | Detectar y avisar; no sobreescribir sin confirmación |

---

## Fuera de alcance v1 (explícito)

- Otros backends (Neon, Firestore, FastAPI) → v2
- SaaS vanilla sin Connect → `/stripe` hermana en v2
- Checkout hosted / Payment Links → nunca (embedded-only por diseño)
- Customer Portal de Stripe → no aplica con Direct charges
- Account types Standard o Custom → solo Express en v1
- Charge models Destination o Separate → solo Direct en v1
- Refunds, disputes, proration, multi-currency, Stripe Tax → se añaden UC por UC cuando aparezcan en proyecto real
- React Native → no está en SpecBox
- Connect embedded onboarding en Flutter → no existe limpio, Account Link redirect es la única ruta

## Advertencias legales/fiscales

La skill **no es asesoramiento legal**. El caso piloto asume España + sellers autónomos. Si operas en otra jurisdicción o con sellers sin alta fiscal:
- Consulta asesor antes de lanzar
- El UC-301 del proyecto consumidor debe mostrar warning explícito antes del Account Link

## Referencias

- PRD: `doc/prds/stripe_connect_skill_prd.md` (engine SpecBox)
- Plan técnico: `doc/plans/stripe_connect_skill_plan.md`
- Stripe Docs: [Connect](https://docs.stripe.com/connect) · [Direct charges](https://docs.stripe.com/connect/direct-charges) · [Subscriptions embedded](https://docs.stripe.com/billing/subscriptions/build-subscriptions) · [Webhooks](https://docs.stripe.com/webhooks) · [Testing](https://docs.stripe.com/testing) · [Test clocks](https://docs.stripe.com/billing/testing/test-clocks)
- Stripe MCP oficial: [mcp.stripe.com](https://mcp.stripe.com/v1)
