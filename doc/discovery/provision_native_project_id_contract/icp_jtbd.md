# Discovery: provision_native_project_id_contract

**Discovery ID**: disc-73746ae3b2bc
**Created**: 2026-06-02T22:49:14Z
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ e3b0c44298fc1c14

> Framing de **"provisión y migración de un proyecto nuevo a Native, de cero, de
> punta a punta"** — el caso de uso central del producto ("subir mi proyecto a
> SpecBox Cloud"), hoy bloqueado por dos gaps combinados encontrados en el
> dogfooding de v6.9.2 (ver `HALLAZGO-v6.9.3-provision-y-project-id.md`).

---

## ICPs involucrados

Heredados de `doc/app/app_market.md` — **sin ICPs nuevos** (no drift de ICP).

- **ICP-2: Dev solo con Claude Code que adopta SpecBox** (primario para esta feature).
  Es quien intenta por primera vez "subir mi proyecto a Cloud" desde un tracking
  local (FreeForm) hacia Native, y se choca con el muro huevo-gallina en su
  **primer intento**. No conoce las tablas internas de Postgres; espera que
  "migrar a Cloud" funcione de una.
- **ICP-3: Equipo/agencia con reporting a cliente** (secundario).
  Native es el único backend multi-developer; la provisión correcta del creador
  como `project_admin` es el cimiento de la colaboración que este ICP necesita
  (un admin que luego invita al resto desde el panel).
- **ICP-1: Owner-operator (JPS, dogfooding)** (el que reporta el gap).
  Migrando `specbox_cloud` (13 US / 89 UC / 466 AC) tropezó con el bloqueo; es
  quien valida la no-regresión del E2E de cero.

## JTBDs racionales

Derivan de **JR-G.1** (trazabilidad US→UC→AC con cada pieza justificada) aplicado
al onboarding a Cloud.

- **JR-F693.1 [ICP-2]**: Cuando subo mi proyecto local a SpecBox Cloud por primera
  vez, quiero que la migración provisione automáticamente mi tenant y mi
  membresía como admin, para no chocarme con un "no eres miembro de un proyecto
  que aún no existe" y abandonar en el primer intento.
- **JR-F693.2 [ICP-2/ICP-3]**: Cuando el engine y el panel hablan del mismo
  proyecto, quiero que ambos usen **un único formato de identificador** acordado,
  para que la migración apunte al mismo tenant que el panel y no se creen dos
  proyectos divergentes (`EmbedBuild/specbox_cloud` vs `embedbuild-specbox-cloud`).
- **JR-F693.3 [ICP-3]**: Cuando quedo como creador de un proyecto Native migrado,
  quiero quedar como `project_admin` (no `member`), para poder invitar al resto
  del equipo desde el panel sin pedirle a nadie que me promueva.
- **JR-F693.4 [ICP-1]**: Cuando la provisión ocurre server-side dentro de una
  migración, quiero que valide mi dev_token, escriba solo en mi tenant y quede en
  audit, para que abrir el flujo de provisión no relaje el blindaje de seguridad
  (`deny_anon` / `service_role`) que protege el resto de tenants.

## JTBDs emocionales

Derivan de **JE-G.2** (sentir que el agente trabaja con disciplina, no improvisando)
y **JE-G.3** (la cara visible del producto refleja la disciplina interna).

- **JE-F693.1 [ICP-2]**: Sentir que "subir a Cloud" es un camino sólido y no un
  campo minado — que el primer intento funciona y no me deja con un proyecto a
  medio crear en una base que no veo.
- **JE-F693.2 [ICP-1/ICP-3]**: Confianza de que engine y panel son **un solo
  producto coherente**, no dos sistemas que nunca acordaron cómo se llaman los
  proyectos. El identificador que veo en el panel y el que migra el engine son la
  misma cosa.

## Validation evidence

**[d] Datapoint de dogfooding (señal directa de uso real).**
El 2026-06-03, validando v6.9.2 sobre un proyecto real (`specbox_cloud`, 186 KB
items.json), la migración freeform→native por lotes **funcionó en transporte** pero
se bloqueó en `start_migration_session` con
`Developer jesusperezdeveloper is not a member of project EmbedBuild/specbox_cloud`.
La identidad autenticaba (`whoami` OK) pero faltaba la membresía, y el tenant ni
existía (BD vacía a propósito). Es el caso de uso central del producto chocando con
un muro en su primer intento — exactamente lo que un ICP-2 real viviría. No es waiver:
es evidencia de operar el producto como cliente real (la misma cadena que parió
v6.9.1 y v6.9.2).

Evidencia de código que fundamenta las decisiones (file:line):
- `server/db/migrations/0002_developers.sql:50-58` — `project_members.project_id`
  tiene FK `REFERENCES projects(project_id) ON DELETE CASCADE`: **a nivel de BD** no
  puedes añadir un miembro antes de que exista la fila en `projects`. El huevo-gallina
  está enforced en el esquema, no es accidental.
- `server/backends/native_backend.py:336-361` — `setup_board` ya hace
  `INSERT INTO projects ... ON CONFLICT DO UPDATE`: la pieza de creación de tenant existe.
- `server/migration/native_handling.py:154-222` — `seed_native_identity` ya
  registra developer + token + `add_project_member`, **pero con `role` por defecto**.
- `server/coordination/identity.py:276-299` — `add_project_member` default
  `role="member"`, NO `project_admin`: aunque el seed corra, no concede admin.
- `server/tools/migration.py:629-644` — el path NO-batch (`migrate_backend`) SÍ llama
  `setup_board` + `seed_native_identity` antes de escribir; el path **batch**
  (`start_migration_session` → `commit` → `ingest_atomic`) **no provisiona nada** y por
  eso revienta en el gate de `authenticate_and_authorize_cached`.
- `server/backends/native_backend.py:344` + `0001_native_schema.sql` — `projects.project_id`
  es **TEXT libre (PK)**: el native no impone ningún formato. La validación slug
  (`^[a-z0-9][a-z0-9-]*$`, lowercase, `/`→`-`) vive **solo en el panel**
  (`apps/api/src/routes/projects.ts:140,173`, repo `EmbedBuild/specbox_cloud`).

## Decisiones canónicas tomadas en este discovery

El dueño del producto delegó la elección al discovery (prompt: *"el discovery debe
evaluar las alternativas con ambos contratos delante y elegir con criterio de
arquitectura"*). Decididas:

### D1 — Contrato canónico de `project_id`: **`owner/repo` + display slug derivado**

`decision_key`: `native_project_id_contract`

- **Forma canónica almacenada** = `owner/repo` (case-preserving): `EmbedBuild/specbox_cloud`.
  Es el `project_id` real en `public.projects` y el target de toda migración Native.
- **Display slug** = proyección URL-safe derivada determinísticamente del canónico:
  `embedbuild-specbox-cloud` (lowercase + `/`→`-`). Se usa **solo** para URLs/visual;
  **nunca** es la clave de identidad.
- **Punto único de normalización**, compartido engine↔panel:
  `canonical_project_id(owner, repo) -> "owner/repo"` y
  `display_slug(project_id) -> "owner-repo"`. El engine es la fuente de verdad del
  helper; el panel consume el mismo contrato.

**Justificación frente a las alternativas:**

| Criterio | owner/repo + display slug (ELEGIDA) | slug canónico | id+slug totalmente separados |
|---|---|---|---|
| Migración de project_ids existentes | **Ninguna** (ya son owner/repo) | **Todos** (riesgo masivo) | media (hay que rellenar el id interno) |
| Colisión cross-owner | **Imposible** (owner namespacea) | posible (`a/app` vs `b/app` → `app`) | imposible |
| Trazabilidad GitHub | **Directa** | indirecta (des-slugificar) | directa |
| URL-safe | sí (vía display slug) | sí (nativo) | sí |
| Cambios en el engine | **Ninguno** | slugificar + migrar | añadir campo id interno |
| Cambios en el panel | relajar patrón INSERT para native + derivar slug display | ninguno | relajar + mapear dos campos |

El slug-canónico se descartó por dos razones de peso: **colisión cross-owner** (rompe
el caso multi-tenant que es la razón de ser de Native) y **migración de todos los
project_id existentes** (riesgo desproporcionado para resolver un problema de URL que
el display slug resuelve sin tocar la identidad). La variante "id interno + slug
totalmente separados" añade un campo y un mapeo sin ganar nada sobre owner/repo, que
**ya es** un id estable y trazable.

**Qué pasa con los project_id existentes:** nada. Ya están en `owner/repo`. El panel
relaja su validación de INSERT para aceptar `owner/repo` cuando el backend es `native`
y deriva el display slug para sus rutas. (Cambio coordinado en el repo del panel —
ver Fase 3 del PRD.)

### D2 — Provisión de tenant+membresía: **el engine auto-provisiona al creador como `project_admin` server-side (excepción de bootstrap)**

`decision_key`: `native_provision_authority`

- En una **migración a un proyecto Native que nace de cero**, la operación de
  switch/ingesta provisiona, server-side y como parte atómica del flujo, **antes** del
  gate de membresía:
  1. `setup_board` → crea `public.projects` (el tenant) si no existe (UPSERT).
  2. `seed_native_identity` con `role="project_admin"` → registra al **caller**
     (resuelto desde su dev_token) como admin del proyecto.
- **Revisión de §6 del panel** (`app_spec.md` del repo `specbox_cloud`,
  *"el panel es el único editor de project_members"*): se acota a una **excepción de
  bootstrap**. El panel sigue siendo el **único editor para añadir/quitar OTROS
  miembros**; el engine solo puede auto-provisionar **al propio creador** durante una
  migración de cero (no puede añadir terceros, no puede cambiar roles de otros). Es la
  única forma de romper el huevo-gallina sin un round-trip manual al panel a mitad de
  migración.
- **Identidad/seguridad (JR-F693.4)**: la provisión valida el dev_token (fail-fast,
  ya existe `require_dev_token`), escribe **solo** en el tenant del caller, queda en
  `audit_log`, y **no relaja** `deny_anon` ni expone `service_role`.
- **Idempotencia/colisión**:
  - tenant ya existe → `setup_board` UPSERT (no duplica).
  - membresía ya existe → `add_project_member` UPSERT; si ya es admin, no-op; si era
    `member`, la auto-provisión del creador puede promover (decisión: solo promueve si
    el caller es quien crea; si el proyecto ya tenía otros admins, no toca a nadie más).
  - id colisiona con otro proyecto → es el mismo `owner/repo`, por definición el mismo
    tenant; no hay colisión semántica posible bajo D1.

### Reparto de responsabilidades engine ↔ panel (resultante)

| Acción | Quién | Formato |
|---|---|---|
| Crear `public.projects` (tenant) en migración de cero | **engine** (auto-provisión) o panel | `owner/repo` |
| Añadir al **creador** como `project_admin` en migración de cero | **engine** (auto-provisión) | — |
| Añadir/quitar **otros** miembros, cambiar roles | **panel** (§6 sigue) | — |
| Derivar display slug para URLs | **panel** (consume helper compartido) | `owner-repo` |
| Validar/normalizar `project_id` | helper compartido (single source of truth) | `owner/repo` ↔ `owner-repo` |

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. La feature hereda ICP-1/ICP-2/ICP-3 de
  `app_market.md` sin alterarlos.
- **Nuevos JTBDs introducidos**: JR-F693.1..4 y JE-F693.1..2 son **especializaciones
  de feature** de los JTBDs globales (JR-G.1, JE-G.2, JE-G.3), no nuevos JTBDs de
  producto. No modifican el perímetro de mercado.
- **Resolución**: `no_drift` — la feature no introduce ICPs ni JTBDs de producto
  nuevos; todo se deriva de lo canónico ya declarado en `app_market.md`.

## Verdict

**READY_FOR_PRD** — ICPs heredados sin drift, JTBDs racionales y emocionales
capturados con trazabilidad a los globales, validation evidence real (dogfooding
datapoint + code evidence file:line), y las dos decisiones de arquitectura (D1
contrato project_id, D2 autoridad de provisión) tomadas y justificadas.

---

> Next step: `/prd provision_native_project_id_contract`
> Las decisiones D1 y D2 se registrarán como **decisiones canónicas** del engine
> (`native_project_id_contract`, `native_provision_authority`) durante el `/prd` para
> que engine y panel tengan una sola fuente de verdad del formato y del reparto de
> responsabilidades.
