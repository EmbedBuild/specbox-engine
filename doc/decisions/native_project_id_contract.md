# Decision: Native project_id contract & provisioning authority (v6.9.3)

> US-NATIVE-PROVISION — cierra los 2 gaps del dogfooding v6.9.2
> (`HALLAZGO-v6.9.3-provision-y-project-id.md`). Discovery
> `provision_native_project_id_contract` (READY_FOR_PRD).
> Estas son **decisiones canónicas** compartidas engine↔panel.

## Contexto

Migrando `specbox_cloud` (13 US / 89 UC / 466 AC) freeform→native de cero, el
transporte por lotes de v6.9.2 funcionó pero la migración se bloqueó en
`start_migration_session` con `Developer jesusperezdeveloper is not a member of
project EmbedBuild/specbox_cloud`. Dos gaps combinados:

- **GAP 1**: el batch-ingest no provisionaba `public.projects` +
  `public.project_members` cuando el proyecto nace de cero. Huevo-gallina
  enforced por FK: `project_members.project_id REFERENCES projects(project_id)`
  ([0001_native_schema.sql](../../server/db/migrations/0001_native_schema.sql),
  [0002_developers.sql:50-58](../../server/db/migrations/0002_developers.sql#L50-L58)).
- **GAP 2**: el engine/native usa `project_id` = `owner/repo`
  (TEXT libre, [native_backend.py:344](../../server/backends/native_backend.py#L344));
  el panel slugifica (`^[a-z0-9][a-z0-9-]*$`, lowercase, `/`→`-`,
  `apps/api/src/routes/projects.ts:140,173` del repo `EmbedBuild/specbox_cloud`).
  Los dos lados nunca acordaron el formato.

---

## D1 — Contrato canónico de `project_id`: `owner/repo` + display slug derivado

`decision_key`: **`native_project_id_contract`**

- **Forma canónica almacenada** (identidad) = `owner/repo`, case-preserving:
  `EmbedBuild/specbox_cloud`. Es el `project_id` real en `public.projects` y el
  target de toda migración Native.
- **Display slug** (solo URLs/visual, nunca identidad) = proyección URL-safe:
  `embedbuild-specbox-cloud` (lowercase + `/`/`_` → `-`).
- **Punto único de normalización**, fuente de verdad del engine, consumido por
  el panel: [`server/coordination/project_id.py`](../../server/coordination/project_id.py)
  - `canonical_project_id(owner, repo) -> "owner/repo"`
  - `display_slug(project_id) -> "owner-repo"` (idempotente)
  - `validate_project_id(project_id) -> project_id` (rechaza malformados con
    `InvalidProjectIdError`).

### Por qué owner/repo y no slug-canónico

| Criterio | owner/repo + slug (ELEGIDA) | slug canónico |
|---|---|---|
| Migración de project_ids existentes | **Ninguna** (ya son owner/repo) | **Todos** (riesgo) |
| Colisión cross-owner | **Imposible** (owner namespacea) | posible (`a/app` vs `b/app`) |
| Trazabilidad GitHub | **Directa** | indirecta |
| URL-safe | sí (vía display slug) | sí (nativo) |
| Cambios en el engine | **Ninguno** | slugificar + migrar |

El slug-canónico rompía el multi-tenant (colisión cross-owner) y exigía migrar
todos los ids existentes — desproporcionado para un problema de URL que el
display slug resuelve sin tocar la identidad.

### Qué pasa con los project_id existentes

Nada — ya están en `owner/repo`. La migración es cero.

---

## D2 — Autoridad de provisión: el engine auto-provisiona al creador como `project_admin` (excepción de bootstrap)

`decision_key`: **`native_provision_authority`**

- En una **migración a un proyecto Native que nace de cero**,
  `start_migration_session` ([migration.py](../../server/tools/migration.py),
  helper `_maybe_auto_provision`) provisiona, server-side y **antes** del gate
  de membresía:
  1. `provision_native_project` ([native_handling.py](../../server/migration/native_handling.py))
     → UPSERT `public.projects` + `seed_native_identity(role="project_admin")`
     para el caller, en una sola transacción + fila `audit_log`
     (`OP_PROVISION_PROJECT`).
- **Revisión de §6 del panel** (`app_spec.md` del repo `specbox_cloud`,
  *"el panel es el único editor de project_members"*): se **acota a una
  excepción de bootstrap**. El panel sigue siendo el **único editor para
  añadir/quitar OTROS miembros**; el engine solo auto-provisiona **al propio
  creador** durante una migración de cero. Un proyecto **pre-existente** del
  que el caller no es miembro NO se auto-une → `FORBIDDEN` (AC-13).
- **Seguridad**: valida el dev_token (fail-fast, `resolve_developer` +
  `require_dev_token`), escribe solo en el tenant del caller, queda en
  `audit_log`, no relaja `deny_anon` ni expone `service_role`. El DSN nunca se
  serializa.
- **Idempotencia**: re-provisión = no-op (projects UPSERT, membresía ya admin),
  nunca degrada `project_admin`→`member`.

### Reparto de responsabilidades engine ↔ panel (resultante)

| Acción | Quién | Formato |
|---|---|---|
| Crear `public.projects` en migración de cero | **engine** (auto-provisión) o panel | `owner/repo` |
| Añadir al **creador** como `project_admin` en migración de cero | **engine** | — |
| Añadir/quitar **otros** miembros, cambiar roles | **panel** (§6 sigue) | — |
| Derivar display slug para URLs | **panel** (consume helper compartido) | `owner-repo` |
| Validar/normalizar `project_id` | helper compartido (single source of truth) | `owner/repo` ↔ `owner-repo` |

---

## Cambio coordinado requerido en el repo del PANEL (`specbox_cloud`)

> Documentado aquí (UC-823 AC-19). La implementación se hace en
> `EmbedBuild/specbox_cloud`, su propio repo.

- **`apps/api/src/routes/projects.ts:173`** — el patrón
  `^[a-z0-9][a-z0-9-]*$` debe **relajarse** para aceptar `owner/repo` cuando el
  backend del proyecto es `native` (almacenar `owner/repo` como id canónico).
- **`apps/api/src/routes/projects.ts:140`** — la slugificación pasa a ser
  **derivación de display** (no de identidad): `display_slug(project_id)`
  usando el mismo contrato que el engine (`canonical_project_id` /
  `display_slug` de `server/coordination/project_id.py`, portado o reimplementado
  1:1 en TS).
- Resultado: panel y engine apuntan al **mismo** `project_id` (`owner/repo`); el
  panel sirve URLs con el display slug. Una sola fuente de verdad del formato.

Contrato de la función compartida (TS equivalente):

```ts
// canonical: "owner/repo" (case-preserving, exactly one slash, no empty segment)
function canonicalProjectId(owner: string, repo: string): string;
function validateProjectId(projectId: string): string;   // throws on malformed
// display only — never an identity key
function displaySlug(projectId: string): string;         // lowercase, [^a-z0-9]+ → "-"
```

---

## Cobertura

- `tests/test_native_provision.py` — UC-818 (4 pure) + UC-819/820/821/822
  (Postgres-gated). El E2E `test_e2e_provision_then_migrate_from_scratch`
  cruza BD vacía → auto-provisión → ingesta por lotes → verificación (project_id
  canónico, creador `project_admin`, US/UC/AC 1:1 con estados preservados,
  display_slug correcto) — el camino que no tenía cobertura y por el que el gap
  de v6.9.2 pasó los tests.

## Referencias

- Discovery: [doc/discovery/provision_native_project_id_contract/icp_jtbd.md](../discovery/provision_native_project_id_contract/icp_jtbd.md)
- PRD: [doc/prd/US-NATIVE-PROVISION_prd.md](../prd/US-NATIVE-PROVISION_prd.md)
- Plan: [doc/plans/US-NATIVE-PROVISION_plan.md](../plans/US-NATIVE-PROVISION_plan.md)
- Hallazgo: [HALLAZGO-v6.9.3-provision-y-project-id.md](../../HALLAZGO-v6.9.3-provision-y-project-id.md)
