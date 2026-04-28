---
name: stripe-switch-account
description: >
  Rotates the active Stripe account of a SpecBox project safely. Wraps the
  switch_stripe_account MCP tool with a UX layer: shows current alias store,
  asks for from/to, runs dry-run, formats the plan in Markdown, asks for
  literal confirmation, executes, and surfaces the rollback runbook if
  something fails. Supports both account_mode='standard' (SaaS, e-commerce)
  and 'connect' (marketplace). Use when the user says "switch stripe
  account", "rotar cuenta stripe", "cambiar cuenta stripe", "cambiar de cuenta
  de stripe", "rotate stripe account", "stripe credentials rotation".
context: direct
allowed-tools: Read, Grep, Glob, Bash(*), Write, Edit, mcp__specbox-stripe__*, mcp__specbox-supabase__*
---

# /stripe-switch-account — Stripe credentials rotation skill

Companion of `/stripe-connect` and `/stripe-standard`. Where those scaffold a
brand-new integration, this one rotates an already-deployed integration to a
**different Stripe account**. Common cases:

- Test → live (going to production for the first time)
- Live → live (changing legal entity, splitting from a former partner)
- Live → test (rolling back to a sandbox after an incident)

The skill never moves money, customers or subscriptions across accounts —
those are immutable once created. What it rotates is the **infrastructure**:
which account the platform's Edge Functions talk to, where the webhooks
fire, which `sk_*` lives in Supabase secrets.

## Uso

```
/stripe-switch-account
```

Sin argumentos. La skill detecta el alias store, pregunta from/to, propone un
plan, pide confirmación literal y ejecuta.

## Pre-requisitos

1. **Alias store** con al menos 2 entradas. Crear con:
   ```
   mcp__specbox-stripe__store_stripe_alias_tool({
     alias_name: "prod",
     stripe_api_key: "sk_live_...",
     project_path: "/abs/path/to/project"
   })
   ```
   La store vive cifrada en `.claude/secrets/stripe_aliases.enc.json`.
2. **specbox-stripe-mcp v0.3+** registrado en `.claude/settings.local.json`.
3. **(Recomendado)** `specbox-supabase-mcp` registrado para auto-rotación de
   Edge Function secrets. Si falta, la skill genera `doc/PENDING_SWITCH_SECRETS.md`
   y guía al usuario para hacerlo manualmente.

---

## Paso 0 — Preflight

### 0.1 Validar proyecto SpecBox

```bash
test -f .claude/settings.local.json || test -f .claude/settings.json || {
  echo "ERROR: No es un proyecto SpecBox. Ejecuta onboard_project primero."
  exit 1
}
```

### 0.2 Detectar `specbox-stripe-mcp`

Comprobar que el MCP está registrado: `grep -q specbox-stripe .claude/settings.local.json`.

Si falta → abortar con instrucciones de instalación:
```
ERROR: specbox-stripe-mcp no está registrado en este proyecto.
Añádelo a .claude/settings.local.json bajo "mcpServers".
Mínimo requerido: v0.3.0 (incluye switch_stripe_account).
```

### 0.3 Detectar el modo del proyecto

Leer `package.json` / `pubspec.yaml` / Edge Functions existentes:
- ¿Hay `supabase/functions/stripe-webhook` con un solo endpoint? → `account_mode='standard'`.
- ¿Hay 2 webhooks (platform + connect) o referencias a `application_fee_percent`? → `account_mode='connect'`.

Si la heurística es ambigua, preguntar al usuario.

### 0.4 Listar aliases disponibles

```
mcp__specbox-stripe__list_stripe_aliases_tool_mcp({ project_path: "{abs}" })
```

Si hay menos de 2 → abortar:
```
ERROR: Necesitas al menos 2 aliases (origen + destino).
Tienes registrados: [lista]
Crea otro con store_stripe_alias_tool antes de switch.
```

---

## Paso 1 — UX inicial

Mostrar al usuario:

```
🔄 Stripe Switch Account

Aliases registrados en este proyecto:
  • prod      (live, last used 2026-04-29 14:22)
  • staging   (test, last used 2026-04-15 10:01)
  • legacy    (live, never used)

¿De qué alias migras? (from): prod
¿A qué alias migras?   (to):   staging
¿Modo de cuenta?              standard

¿Qué hacer con la cuenta de origen tras el switch?
  (1) keep_old_active        — no tocar nada (DEFAULT, recomendado para rollback rápido)
  (2) archive_products_only  — archivar los products SpecBox, dejar webhooks
  (3) deactivate_webhooks_only — deshabilitar webhooks, dejar products
  (4) full_archive           — todo lo anterior + cancelar subs SpecBox-managed (irreversible)

Elección: 1
```

Validar before continuar:
- `from != to`
- `from` y `to` existen en alias_store
- En `connect` → preguntar también `connect_events`/`connect_url` si difieren

---

## Paso 2 — Dry-run obligatorio

```
mcp__specbox-stripe__switch_stripe_account_tool({
  from_alias: "prod",
  to_alias: "staging",
  account_mode: "standard",
  project_path: "{abs}",
  platform_url: "https://{ref}.supabase.co/functions/v1/stripe-webhook",
  platform_events: [...read from project's events.yaml or defaults...],
  scope_action: "keep_old_active",
  dry_run: true
})
```

Formatear la respuesta como Markdown:

```
📋 Plan de migración (dry-run)

ORIGEN (prod, sk_live_***)
  Webhook endpoints:    1 SpecBox-managed
  Products:             3
  Subscriptions activas: 27
  Customers:            142

DESTINO (staging, sk_test_***)
  Webhook endpoints:    0
  Products:             0

ACCIONES PROPUESTAS
  1. Crear 1 webhook endpoint en destino (events: ...)
  2. Replicar catálogo (3 products + sus prices)  ← solo si pasaste catalog
  3. Inyectar secrets en Supabase (3 keys)        ← si specbox-supabase MCP detectado
                                  ↳ si no: doc/PENDING_SWITCH_SECRETS.md
  4. scope_action sobre origen: keep_old_active (no toca nada)

Duración estimada: ~12 segundos

⚠️  IMPORTANTE: Las subscripciones, customers, y métodos de pago de la
   cuenta origen NO se mueven. Siguen vivos en prod. Si alguien tenía
   sesión iniciada y va a renovar, el cobro irá a prod, NO a staging.
   Este flow es para infrastructure rotation, no migración de business data.
```

---

## Paso 3 — Confirmación literal

```
Para ejecutar este switch, escribe EXACTAMENTE:

  Yes, switch from prod to staging

(con esos espacios y mayúsculas; un fallo de typing aborta el switch)
```

Si el usuario escribe cualquier otra cosa → abortar sin tocar nada.

Si `scope_action='full_archive'` → segunda confirmación con
`confirm_token="I understand this archives all SpecBox resources in the source account"`.

---

## Paso 4 — Ejecutar real

```
mcp__specbox-stripe__switch_stripe_account_tool({
  ...mismo payload que dry-run...
  dry_run: false
})
```

Streaming progress al usuario:

```
✓ Pre-flight OK
✓ Webhook endpoint creado en destino: we_1TabcXyz
✓ 3/3 products replicados en destino
✓ Secrets inyectados en Supabase (3 nombres: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY)
✓ scope_action keep_old_active: cuenta origen intacta

✅ Switch completado en 11.2s.
```

Si algún paso falla:

```
✗ Webhook endpoint creado en destino
✗ Products replicación: FAILED (E_LIMIT_REACHED)
🔄 Iniciando rollback automático...
✓ Webhook destino eliminado
⚠ Rollback completo. Sistema de vuelta al estado pre-switch.

Revisa los logs y vuelve a intentar.
```

Si rollback también falla:

```
🚨 Rollback parcialmente fallido. Estado del sistema mixto.
   Runbook generado en: doc/SWITCH_FAILURE_RUNBOOK.md
   Sigue las instrucciones manualmente.
```

---

## Paso 5 — Smoke-test post-switch

Sugerir al usuario:

```
Próximos pasos:
  1. Reload de Edge Functions (Supabase los recoge automáticamente).
  2. stripe listen --forward-to {platform_url}  (con la NUEVA cuenta)
  3. Test de un signup nuevo:
       - Card 4242 4242 4242 4242
       - Verifica que aparece en https://dashboard.stripe.com/{test|live}/customers de la cuenta DESTINO.
  4. Si todo OK y scope_action era 'keep_old_active' → considera ejecutar
     /stripe-switch-account de nuevo con scope_action='archive_products_only'
     una vez confirmes que no necesitas rollback.
```

Si el usuario responde "rollback please":

```
/stripe-switch-account
  from: staging
  to:   prod
```

Es exactamente el mismo flow al revés (siempre que `prod` aún esté `keep_old_active`).

---

## Anexo A — Errores comunes

| Error | Causa | Fix |
|-------|-------|-----|
| `E_ALIAS_NOT_FOUND` | El alias no está en la store | Crear con `store_stripe_alias_tool` |
| `E_DECRYPT_FAILED` | macOS Keychain inaccesible o passphrase distinto | Re-ingresar passphrase / re-crear keychain entry |
| `E_INVALID_KEY` (en alias) | sk_test_/sk_live_ malformado | Pegar de nuevo desde el dashboard |
| `E_LIVE_MODE_NOT_ALLOWED` | sk_live_* sin opt-in | Pasar `allow_live_mode=true` + `live_mode_confirm_token="I acknowledge this affects real money"` |
| `E_LIMIT_REACHED` | >16 webhook endpoints en la cuenta destino | Borrar los huérfanos: `stripe webhooks list --limit=100` y purga manual |
| `E_SUPABASE_WRITE_FAILED` | PAT expirado / project_ref incorrecto | Revisar `SUPABASE_ACCESS_TOKEN` |
| `E_CONFIRMATION_REQUIRED` | Token literal incorrecto | Copiar el token exactamente como aparece en el mensaje de error |

---

## Anexo B — `.gitignore` enforcement

La store cifrada en `.claude/secrets/stripe_aliases.enc.json` se añade a
`.gitignore` automáticamente la primera vez que se llama a
`store_stripe_alias_tool`. La skill lo verifica antes de cualquier acción.
Si por alguna razón está commiteada al repo, **revoca todas las keys de
Stripe inmediatamente y rota** — el archivo cifrado no debería bastar para
recuperarlas, pero asume compromiso.

---

## Referencias

- Tool docs: `mcp__specbox-stripe__switch_stripe_account_tool`
- Alias store: `packages/specbox-stripe-mcp/src/specbox_stripe_mcp/lib/alias_store.py`
- Skills hermanas: `/stripe-connect` (marketplace), `/stripe-standard` (no-Connect)
- Tracking: SpecBox board `ff-bc73b5d69f91`, US-STRIPE-SWITCH-ACCOUNT
