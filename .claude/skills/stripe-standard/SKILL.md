---
name: stripe-standard
description: >
  Scaffolds a Stripe **Standard account** integration (no Connect) in
  Supabase + React/Flutter projects. Generates US-STRIPE-CHECKOUT with up to
  12 UCs covering the 4 canonical billing modalities (single subscription,
  tiered subscriptions, metered billing, one-shot checkout) in the project's
  spec backend, backend Edge Functions + SQL migrations with RLS, frontend
  templates with Payment Element/Sheet + Apple/Google Pay + Express Checkout,
  Stitch designs (if VEG configured), reuses the stripe-safety-guard hook,
  events catalog, and wires the official Stripe MCP. Use when the user says
  "stripe standard", "stripe sin connect", "subscriptions saas",
  "checkout one-shot", "billing saas", "monta pagos saas", "monta pagos
  e-commerce". v1 scope: Supabase only, the 4 modalities are flags so the
  user opts in.
context: direct
allowed-tools: Read, Grep, Glob, Bash(*), Write, Edit, mcp__specbox-engine__*, mcp__stitch__*
---

# /stripe-standard — Stripe billing scaffolder for normal (non-Connect) accounts

The companion of `/stripe-connect` for the 80% of Stripe consumers that don't
need a marketplace: SaaS subscriptions, e-commerce one-shot, B2B invoicing,
metered billing, donations, paywalls. Generates the same kind of bundle
(spec + Edge Functions + SQL + RLS + frontend templates + Stitch designs +
safety hook) but tuned for **a single Stripe account** with **a single
webhook endpoint** and zero Connect machinery.

## When to use this vs /stripe-connect

| Use case | Skill |
|----------|-------|
| You sell access to your own product (SaaS, app, content) | **`/stripe-standard`** |
| You run an e-commerce shop selling your own goods | **`/stripe-standard`** |
| You have one-shot purchases (donations, lifetime deals) | **`/stripe-standard`** |
| You need metered billing (usage-based pricing) | **`/stripe-standard`** |
| You operate a marketplace where other sellers receive money | `/stripe-connect` |
| You take a cut from third-party transactions | `/stripe-connect` |

If unsure, default to `/stripe-standard`. Adding Connect later is a refactor
but supported by the same `setup_webhook_endpoints(account_mode='connect')`
of the underlying MCP — no data loss.

## Uso

```
/stripe-standard
```

Sin argumentos por defecto activa **las 4 modalidades**. Para acotar:

```
/stripe-standard --modes=single_sub,one_shot
/stripe-standard --modes=metered
```

Modalidades válidas:

| Flag | Qué genera |
|------|-----------|
| `single_sub` | 1 sola suscripción mensual o anual fija (caso SaaS clásico) |
| `tiered_sub` | Múltiples planes con upgrade/downgrade y proration |
| `metered` | Facturación por uso (usage records + reporting) |
| `one_shot` | Pagos únicos sin recurrencia (e-commerce, donaciones, lifetime) |

---

## Alcance v1 (opinionado)

| Dimensión | Decisión |
|-----------|----------|
| Backend | **Supabase únicamente** (Neon/Firestore/FastAPI → v2) |
| Frontend | React 19 o Flutter 3.38+ |
| Account type | **Stripe Standard** (la cuenta normal — sin Connect) |
| Charge model | Direct charges sobre la propia cuenta |
| Subscriptions | 4 modalidades disponibles, opt-in vía flags |
| Checkout UX | Embedded-only: Payment Element (React) + Payment Sheet (Flutter). Hosted Checkout queda como fallback opcional vía `stripe-create-checkout-session` |
| Apple/Google Pay | Default on |
| Customer Portal | **Sí** (en Standard sí podemos abrir el portal — el customer vive en nuestra propia cuenta) |
| Webhook endpoints | **1 solo** (vs 2 de Connect) |
| MCP underneath | `specbox-stripe-mcp` v0.2 con `account_mode='standard'` |

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
  if [ -d ios ] || [ -d android ]; then STACK="flutter-mobile"; else STACK="flutter-web"; fi
fi
```

Si no detecta ni React ni Flutter → abortar: *"v1 solo soporta React o Flutter. Otros stacks no están cubiertos."*

### 0.3 Detectar backend Supabase (obligatorio en v1)

```bash
test -d supabase && test -f supabase/config.toml || {
  echo "ERROR: v1 de /stripe-standard requiere Supabase CLI inicializado."
  echo "Ejecuta 'supabase init' antes de continuar, o espera a v2 para otros backends."
  exit 0
}
```

### 0.4 Detectar spec backend activo (Trello / Plane / FreeForm)

Leer `.claude/settings.local.json`:
- `trello.boardId` → Trello
- `plane.defaultProject` → Plane
- Sin ninguno → FreeForm en `doc/tracking/`

### 0.5 Detectar presencia de VEG

```bash
test -d doc/veg && test -f doc/design/brand-kit.md && VEG_PRESENT=true || VEG_PRESENT=false
```

### 0.6 Parsear flag `--modes`

```bash
MODES_INPUT="${1:---modes=single_sub,tiered_sub,metered,one_shot}"
MODES=$(echo "$MODES_INPUT" | sed 's/--modes=//')

# Validate every mode is in the supported set.
VALID="single_sub tiered_sub metered one_shot"
for m in $(echo "$MODES" | tr ',' ' '); do
  echo "$VALID" | grep -qw "$m" || {
    echo "ERROR: modalidad '$m' no soportada. Válidas: single_sub, tiered_sub, metered, one_shot."
    exit 1
  }
done
```

### 0.7 Detectar specbox-stripe-mcp instalado

```bash
# Either as a globally registered MCP or as a workspace package.
test -d packages/specbox-stripe-mcp || command -v specbox-stripe-mcp >/dev/null || {
  echo "WARN: specbox-stripe-mcp no detectado. La skill puede continuar pero los tools de"
  echo "      setup-as-code (verify_account_setup, setup_webhook_endpoints, etc.) no estarán"
  echo "      disponibles para el proyecto. Instálalo con: pip install specbox-stripe-mcp"
}
```

---

## Paso 1 — Confirmar plan con el usuario

Antes de tocar el filesystem, presentar:

```
📋 Stripe Standard scaffolder — plan de generación

  Stack detectado:    {STACK}
  Spec backend:       {Trello|Plane|FreeForm}
  VEG presente:       {sí|no}
  Modalidades:        {modes activadas}

  Va a crear:
  - 1 US-STRIPE-CHECKOUT + N UCs en {spec_backend}
  - Edge Functions Supabase ({lista funciones})
  - Migraciones SQL ({lista migraciones})
  - Templates frontend en {src/billing|lib/billing}/
  - {N} pantallas Stitch (si VEG activo)
  - 1 PRD en doc/prd/stripe_standard_prd.md

  Va a NO crear:
  - Cuenta Stripe (debes tenerla ya, en test mode)
  - Secrets en .env (los pegas tú; la skill solo guía con el placeholder)

¿Continuar? (s/n)
```

Si responde `n` → exit 0 sin tocar nada.

---

## Paso 2 — Crear US-STRIPE-CHECKOUT + UCs en spec backend (AC-01..AC-06)

El catálogo canónico de los 12 UCs vive en `templates/uc-catalog.json`. La skill
filtra por `MODES` activadas y llama `import_spec` con el subset.

```python
# Pseudocódigo de la skill — la implementación real es Bash + jq.
catalog = json.load(open(".claude/skills/stripe-standard/templates/uc-catalog.json"))
selected_ucs = [
    uc for uc in catalog["ucs"]
    if any(m in uc["modes"] for m in MODES.split(","))
    or "always" in uc["modes"]   # webhook handler, customer creation, paywall siempre van
]

spec = {
    "user_stories": [{
        "us_id": "US-STRIPE-CHECKOUT",
        "name": "Integración de pagos Stripe (cuenta Standard, modalidades activadas: " + MODES + ")",
        "description": "...",
        "hours": sum(u["hours"] for u in selected_ucs),
        "use_cases": selected_ucs,
    }]
}

import_spec(board_id=board_id, spec=spec)
```

### 2.1 Re-run idempotente (AC-05)

Si `list_us(board_id)` ya devuelve un US-STRIPE-CHECKOUT:

```
⚠ Ya existe US-STRIPE-CHECKOUT en este board.
  ¿Qué quieres hacer?
  (1) skip — no cambiar nada en el spec backend
  (2) update — añadir las UCs nuevas (las modalidades que faltan)
  (3) replace — borrar la US existente y crearla desde cero (destructivo)
```

Por defecto la skill elige (1) si no hay TTY interactivo.

### 2.2 Fallback si el spec backend está offline

Try/catch sobre `import_spec`. Si falla:

```
⚠ Spec backend {Trello|Plane} no responde. Guardando como FreeForm local en doc/tracking/.
```

Llamar `set_auth_token(backend_type="freeform", root_path="doc/tracking")` y reintentar.

---

## Paso 3 — Generar PRD adjunto (AC-07)

Escribir `doc/prd/stripe_standard_prd.md` desde
`templates/docs/stripe_standard_prd.md.template` con las secciones por modalidad
activada. Cada modalidad incluye:

- **Caso de uso** (resumen de 2-3 frases)
- **Flujo principal** (numerado)
- **Casos de error** (lista)
- **Eventos Stripe relevantes** (subset del events catalog)
- **Frontend components afectados**

Si `--modes=single_sub,one_shot`, el PRD solo tiene esas 2 secciones.

---

## Paso 4 — Escribir templates backend Supabase (AC-07/UC-007)

Copiar y parametrizar desde `.claude/skills/stripe-standard/templates/supabase/`:

### 4.1 Edge Functions

Funciones generadas según modalidades activadas:

| Function | Modalidad |
|----------|-----------|
| `stripe-create-customer/index.ts` | always |
| `stripe-webhook/index.ts` | always (1 solo endpoint, sin separar platform/connect) |
| `stripe-create-subscription/index.ts` | si activas `single_sub`, `tiered_sub` o `metered` |
| `stripe-create-payment-intent/index.ts` | si activas `one_shot` |
| `stripe-create-checkout-session/index.ts` | siempre — fallback hosted (con `ui_mode='embedded'` por defecto) |
| `stripe-create-portal-session/index.ts` | always (Customer Portal) |
| `stripe-report-usage/index.ts` | si activas `metered` |

Placeholders: `{project_name}`, `{frontend_url}`, `{currency}` (default `eur`).

### 4.2 Migraciones SQL

3 migraciones copiadas a `supabase/migrations/` con timestamp prefix:

| Migration | Contenido |
|-----------|-----------|
| `NNN_stripe_customers.sql` | tabla `stripe_customers (user_id FK auth.users, stripe_customer_id UNIQUE)` |
| `NNN_stripe_subscriptions.sql` | tabla `stripe_subscriptions (customer_id FK, stripe_subscription_id, price_id, status, current_period_end, cancel_at_period_end, metadata JSONB)` |
| `NNN_stripe_processed_events.sql` | tabla `stripe_processed_events (event_id UNIQUE PK, type, processed_at)` |

RLS policies en una 4ª migración: usuarios solo ven sus propias rows; service_role
lee/escribe todo desde Edge Functions.

Todas con `CREATE ... IF NOT EXISTS` para idempotencia.

---

## Paso 5 — Escribir templates frontend (UC-009 / UC-010)

### 5.1 React (`STACK=react`)

Copiar desde `templates/react/` a `src/billing/` del proyecto:

- `stripe-provider.tsx` — `<Elements>` con `appearance` parametrizada por brand-kit
- `subscription-form.tsx` — `<PaymentElement>` + `<ExpressCheckoutElement>` para single/tiered subs
- `checkout-embedded.tsx` — `loadStripe + initEmbeddedCheckout` para one-shot
- `paywall-gate.tsx` — wrapper que bloquea acceso si no hay sub activa
- `billing-portal-link.tsx` — botón que abre el Customer Portal vía Edge Function
- `usage-meter.tsx` — solo si `metered` activado (componente para mostrar uso)
- `use-billing.ts` — hook centralizado de estado de subs/payments

Mergear dependencias en `package.json`:
```json
{
  "@stripe/stripe-js": "^3",
  "@stripe/react-stripe-js": "^2"
}
```

### 5.2 Flutter (`STACK=flutter-mobile` o `flutter-web`)

Copiar desde `templates/flutter/` a `lib/billing/`:

- `stripe_service.dart` — init + Apple Pay + Google Pay
- `subscription_screen.dart` — PaymentSheet para single/tiered subs
- `one_shot_checkout_sheet.dart` — PaymentSheet para compras únicas
- `paywall_gate.dart` — widget gate que bloquea si no hay sub
- `billing_portal_button.dart` — abre el portal en navegador (`url_launcher`)
- `usage_meter_card.dart` — solo si `metered` activado
- `billing_controller.dart` — estado centralizado

Mergear dependencias en `pubspec.yaml`:
```yaml
flutter_stripe: ^11.0.0
url_launcher: ^6.0.0
```

---

## Paso 6 — Stitch designs (UC-011)

Si `VEG_PRESENT=true`, generar pantallas vía `mcp__stitch__generate_screen_from_text`.

Pantallas según modalidades activadas:

| Pantalla | Modalidades requeridas |
|----------|------------------------|
| `paywall.html` | siempre |
| `billing-portal.html` | siempre |
| `checkout-success.html` | siempre |
| `checkout-cancel.html` | siempre |
| `subscription-management.html` | si hay alguna sub modalidad activa |
| `metered-usage-dashboard.html` | si `metered` activado |

Guardar en `doc/design/stripe_standard/`. Registrar prompts en
`doc/design/stripe_standard/stripe_standard_stitch_prompts.md`.

Si `VEG_PRESENT=false` → saltar este paso silenciosamente.

---

## Paso 7 — Reusar hook stripe-safety-guard (UC-012)

El hook ya existe en `.claude/hooks/stripe-safety-guard.mjs` (vino con
`/stripe-connect`). Detecta los 5 anti-patterns en `src/billing/`,
`lib/billing/` y `supabase/functions/stripe-*`:

1. `sk_live_*` hardcoded
2. Webhook handler sin verificación de firma
3. Webhook handler sin idempotencia (`stripe_processed_events`)
4. `redirectToCheckout` o `ui_mode='hosted'`
5. Payment Links

No tocamos el hook. Solo verificamos que está activado en `.claude/settings.json`:

```bash
grep -q "stripe-safety-guard" .claude/settings.json || {
  echo "WARN: stripe-safety-guard hook no activo. Activa con /compliance --fix."
}
```

---

## Paso 8 — Wire Stripe MCP oficial (idéntico a /stripe-connect Paso 8)

Mergear en `.claude/settings.local.json`:

```json
{
  "mcpServers": {
    "stripe": {
      "command": "npx",
      "args": ["-y", "@stripe/mcp", "--api-key", "${STRIPE_API_KEY}"],
      "env": { "STRIPE_API_KEY": "${STRIPE_SECRET_KEY}" }
    }
  }
}
```

Esto da acceso al **MCP oficial** de Stripe (runtime de negocio: customers,
charges, refunds, etc.) además del `specbox-stripe-mcp` (setup-as-code).

---

## Paso 9 — Inyectar secrets en Supabase Edge Functions (UC-013)

Standard solo necesita **3 secrets** (vs los 4 de Connect):

| Secret | Origen |
|--------|--------|
| `STRIPE_SECRET_KEY` | tu cuenta Stripe (test mode) |
| `STRIPE_WEBHOOK_SECRET` | salida de `stripe listen --forward-to ...` o el dashboard |
| `STRIPE_PUBLISHABLE_KEY` | tu cuenta Stripe |

NO existe `STRIPE_WEBHOOK_SECRET_CONNECT` aquí — Standard solo tiene 1 endpoint.

### 9.1 Detectar specbox-supabase MCP

Intentar `mcp__specbox-supabase__list_edge_secrets_tool({supabase_pat: "...", project_ref: "..."})`.

- Si responde → Paso 9.2 (auto-inyección).
- Si no responde / no está registrado → Paso 9.3 (manual, escribe doc/PENDING_SECRETS.md).

### 9.2 Inyección automática

```
mcp__specbox-supabase__set_edge_secret_tool({
  supabase_pat: env.SUPABASE_PAT,
  project_ref: env.SUPABASE_PROJECT_REF,
  secrets: {
    STRIPE_SECRET_KEY:       env.STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET:   env.STRIPE_WEBHOOK_SECRET,
    STRIPE_PUBLISHABLE_KEY:  env.STRIPE_PUBLISHABLE_KEY,
  },
  confirm: true,
  reason: "/stripe-standard initial setup"
})
```

Verificar con `list_edge_secrets({expected_names: [...]})`.

### 9.3 Fallback manual

Si MCP ausente, escribir `doc/PENDING_SECRETS.md`:

```markdown
# Secrets pendientes

specbox-supabase MCP no detectado. Copia estos 3 secrets manualmente en:
https://supabase.com/dashboard/project/{project_ref}/settings/functions

  STRIPE_SECRET_KEY        = <from .env>
  STRIPE_WEBHOOK_SECRET    = <from `stripe listen` output>
  STRIPE_PUBLISHABLE_KEY   = <from .env>
```

Engram observation: registrar éxito/fallo del paso sin valores de secrets.

---

## Paso 10 — Tests + acceptance evidence (UC-015)

Generar `tests/acceptance/` con un test por modalidad activada:

| Test | Modalidad |
|------|-----------|
| `subscribe_single_sub.spec.ts` (React) o `_test.dart` (Flutter) | `single_sub` |
| `switch_tier.spec.ts` | `tiered_sub` |
| `metered_billing.spec.ts` | `metered` |
| `one_shot_checkout.spec.ts` | `one_shot` |

Cada test cubre el happy path + 1-2 error paths (decline, 3DS challenge).

---

## Paso 11 — Próximos pasos (mostrar al usuario)

```
✓ /stripe-standard completado en {duration}.

Siguientes pasos manuales:
  1. {Si Paso 9 fue manual} Copiar los 3 secrets en Supabase dashboard.
  2. Ejecutar `supabase db push` para aplicar las migraciones.
  3. Ejecutar `stripe listen --forward-to <tu-edge-url>/stripe-webhook` en
     terminal separado para testing local.
  4. (Opcional, no bloqueante) Activar Stripe Tax si vas a vender en EU.
  5. /implement US-STRIPE-CHECKOUT — ejecutará los UCs en orden.

📋 Catálogo de eventos relevantes en doc/stripe-standard-events.md.
```

---

## Anexo A — Comparativa Standard vs Connect

| Dimensión | Standard | Connect |
|-----------|----------|---------|
| Webhook endpoints | 1 (platform-scope) | 2 (platform + connect) |
| Tablas SQL | 3 (customers, subs, events) | 4 (riders/sponsorships también) |
| Edge Functions | 5-7 según modos | 5 fijas |
| Customer Portal | sí (built-in) | requiere onboarding del seller |
| `application_fee_percent` | N/A | dinámico por seller |
| Activación dashboard | nada | hay que activar Connect explícitamente |

---

## Errores frecuentes (FAQ rápido)

**Q**: Mi proyecto ya tiene `/stripe-connect`. ¿Puedo añadir `/stripe-standard`?

**A**: Técnicamente sí pero **no recomendado**. El cliente Stripe abstracto no
distingue Standard de Connect en runtime. Si ya tienes Connect Express, los
flujos de Standard van por la cuenta plataforma — funciona pero crea confusión.
Mejor escoge una de las dos modalidades.

**Q**: ¿Puedo migrar de `/stripe-connect` a `/stripe-standard`?

**A**: La parte de spec/templates es regenerar la skill. La parte de Stripe es
otra cosa: si ya cobraste con Direct charges en Connect, no se mueve a la
plataforma. Customers + subscriptions seguirán viviendo en las cuentas
conectadas. Es una migración pesada — pregunta antes de intentarla.

**Q**: `metered` vs `tiered_sub`, ¿cuál escojo?

**A**: `tiered_sub` = N planes con precio fijo, el usuario puede subir/bajar.
`metered` = un plan + se factura por uso (ej: $0.001 por API call). Son
ortogonales: puedes activar las dos.

---

## Referencias

- Plan original: `doc/plans/stripe_standard_plan.md` (auto-generado por `/plan US-STRIPE-STANDARD`)
- MCP underlying: `packages/specbox-stripe-mcp/` v0.2 (`account_mode='standard'`)
- Skill hermana: `/stripe-connect`
- Tracking: SpecBox board `ff-bc73b5d69f91`, US-STRIPE-STANDARD
