# Discovery: orphan_tenant_provision

**Discovery ID**: disc-cc9b688f5c6c
**Created**: 2026-06-03T07:33:01Z
**Status**: READY_FOR_PRD
**Mode**: standard
**Source of inheritance**: doc/app/app_market.md @ e3b0c44298fc1c14

> Bug interno del engine encontrado en dogfooding (2026-06-03) probando v6.9.3
> "Tenant Provisioning". Cierra el cuarto eslabón de la cadena de hallazgos:
> v6.9.3 implementó la lógica de auto-provisión correctamente, pero otra ruta
> (`setup_board`) crea un tenant sin membresía que **desactiva** esa lógica en
> el camino real. Origen: `HALLAZGO-v6.9.4-setup-board-tenant-huerfano.md`.

---

## ICPs involucrados

Hereda de `app_market.md`. Esta es una feature **interna del engine** (corrección
de infraestructura de migración native), no una feature de producto de cara a un
usuario externo. El ICP afectado es:

- **ICP-1: Owner-operator del engine (JPS, dogfooding)** — canónico.
  Es quien ejecuta `start_migration_session` para subir su proyecto
  (`specbox_cloud`) a SpecBox Cloud (Native backend) y se topa con el FORBIDDEN.
  El bug se manifiesta exactamente en su flujo de dogfooding: migrar un proyecto
  real freeform→native desde cero.

ICP-2 (dev solo que adopta) e ICP-3 (equipo/agencia) heredan el beneficio
indirectamente: cuando adopten el Native backend, la provisión desde cero será
robusta. Pero no son el driver de esta feature.

## JTBDs racionales

Hereda los JTBDs globales; el más directamente servido:

- **JR-G.1** (trazabilidad y código que justifica su existencia): la migración a
  Native es el transporte que lleva la spec auditada a la nube. Si la provisión
  falla, la trazabilidad se rompe en el último metro.

JTBDs racionales específicos de esta feature (heredables, derivados de JR-G.1/JR-G.3):

- **JR-FOTP.1 [ICP-1]**: Cuando subo un proyecto nuevo a SpecBox Cloud (native)
  por primera vez desde cero, quiero que la provisión de tenant + membresía
  ocurra automáticamente y de forma atómica, para no recibir un FORBIDDEN
  inexplicable cuando soy yo mismo el creador y tengo identidad válida.

- **JR-FOTP.2 [ICP-1]**: Cuando una operación previa (set_auth_token, start_uc,
  import_spec) ya tocó el proyecto y dejó una fila "fantasma" sin miembros,
  quiero que la migración se recupere de ese estado sucio en vez de fallar, para
  que el orden de mis acciones no determine si la migración funciona o no.

- **JR-FOTP.3 [ICP-1]**: Cuando confío en que el test E2E cubre la feature,
  quiero que ese test reproduzca el **camino sucio real** (no solo BD virgen),
  para que "pasa en test" implique "funciona en producción" — rompiendo la
  cadena de 4 hallazgos donde el test cubría el camino ideal y el dogfooding
  el real.

## JTBDs emocionales

Hereda los globales; el más directamente servido:

- **JE-G.2** (sentir que el agente trabaja **con** disciplina, no improvisando):
  un FORBIDDEN cuando eres el dueño legítimo rompe la confianza en el sistema —
  "el ecosistema se sabotea a sí mismo" (frase literal del hallazgo). El fix
  restaura la sensación de que la infraestructura es coherente consigo misma.

- **JE-FOTP.1 [ICP-1]**: No sentir que el orden de mis acciones es un campo
  minado. Hoy, hacer set_auth_token antes de migrar deja una mina (huérfano)
  que explota después. Quiero la tranquilidad de que el estado sucio es
  recuperable, no terminal.

## Validation evidence

**[d] Datapoint de dogfooding directo (evidence interna, fuerte).**

El bug está reproducido con SQL directo contra Postgres (verificado en el
hallazgo):

- Tras `start_migration_session(target='EmbedBuild/specbox_cloud')` sobre BD
  **verificada vacía**: `public.projects` = 1 fila (sin membresía),
  `public.project_members` = 0, `public.audit_log` = 0.
- Esa firma (projects sí, members no, audit no) es de `setup_board`
  (`native_backend.py:344`), NO de `provision_native_project` (que escribiría
  membresía + audit en la misma transacción).
- Síntoma recurrente confirmado: la fila fantasma reaparece sola cada vez que el
  MCP toca el proyecto — origen `set_auth_token` (`spec_driven.py:276`) que llama
  `setup_board` en cada auth.

No requiere validación con usuarios externos (waiver implícito por ser feature
interna del engine, alineado con la regla del skill). La evidence es el repro
SQL + la traza file:line, que es más fuerte que una conversación de usuario para
un bug de infraestructura.

## Análisis técnico — trazado de rutas y decisión de diseño

### Rutas que crean `public.projects` para native (verificado, file:line)

| Ruta | Crea membresía | Atómico | Deja huérfano |
|------|----------------|---------|---------------|
| `provision_native_project` (`native_handling.py:288-312`) | **Sí** (`add_project_member`) | **Sí** (1 transacción) | No |
| `setup_board` (`native_backend.py:342-354`) | **No** | No | **Sí** ⚠️ |

`setup_board` se invoca desde:
- `spec_driven.py:276` — `set_auth_token` (¡en CADA auth native! → origen del
  síntoma recurrente "la fila fantasma reaparece sola").
- `spec_driven.py:460` — `import_spec`.
- `migration.py:337, 630, 1009` — caminos de migración legacy
  (`migrate_backend`, `migrate_project`, `switch_backend`).
- `start_uc` (vía spec backend).

### El invariante a establecer

> **Un tenant native nunca debe existir sin al menos un miembro.**
> Si, por una ruta legacy o un estado sucio preexistente, la fila existe con 0
> miembros, la auto-provisión debe saber **adoptarlo** (crear la membresía del
> creador) en vez de tratarlo como un tenant legítimo protegido por AC-13.

### Decisión: Enfoque Combinado (3) — defensa en profundidad

Confirmado con el usuario (2026-06-03). Dos capas independientes y aditivas:

**FIX A — Cerrar la puerta de raíz.** `setup_board` para native debe pasar por
la provisión atómica (tenant + membresía juntos) cuando dispone de identidad
(dev_token). Nunca debe poder dejar un proyecto con 0 miembros. Esto requiere
que `setup_board` conozca al developer; en native el `NativeBackend` ya recibe
`dev_token`, así que puede resolver la identidad y delegar en
`provision_native_project` en lugar del INSERT desnudo. Donde no haya identidad
disponible (improbable en native, pero defensivo), `setup_board` no debe crear
una fila huérfana silenciosamente.

**FIX B — Auto-provisión robusta a estados sucios.** `_maybe_auto_provision`
(`migration.py:1462-1467`) cambia su condición de:
```
exists = SELECT 1 FROM projects WHERE project_id = $1
if exists: return False
```
a:
```
si el proyecto NO existe            → provisiona (como hoy)
si existe pero tiene 0 miembros     → adopta (provisiona la membresía del creador)
si existe y tiene ≥1 miembro        → return False (tenant real → AC-13 protege)
```
`provision_native_project` ya es idempotente y no degrada admin existente, así
que "adoptar" reutiliza esa función sin código nuevo de escritura — solo cambia
la condición de entrada de "no existe" a "no existe O sin miembros".

### Razonamiento de seguridad — ¿es seguro adoptar un tenant con 0 miembros?

**Sí, siempre.** El guard AC-13 (decisión D2 de v6.9.3) protege contra el caso
real de robo: auto-unirse como admin a un proyecto **que ya tiene dueños**
(Alice migra al `project_id` de Bob y se vuelve admin de sus datos).

Un tenant con **CERO** miembros:
- **No tiene a quién robar.** Sin miembros no hay dueño, no hay autoridad que
  usurpar, no hay escalada de privilegios posible.
- **No es un vector de ataque útil.** Si un atacante crea deliberadamente un
  huérfano para que otro se auto-una, el beneficiario es la *víctima* (que se
  vuelve admin del tenant vacío), no el atacante. No hay ganancia para quien
  ataca.
- **Es semánticamente equivalente a "no existe".** La fila huérfana es un
  artefacto de un INSERT incompleto, no un tenant legítimo. Adoptarlo = terminar
  la provisión que `setup_board` dejó a medias.

**Matiz documentado**: un huérfano puede contener datos (US/UC/AC) si
`import_spec`/`start_uc` escribió tras el `setup_board` huérfano. Adoptar
significa que el **primer** caller que migre se vuelve `project_admin` de esos
datos. Es coherente con D2 ("el creador es el primer admin"): esos datos los
escribió el mismo flujo sin membresía, así que el primer migrador legítimo es su
dueño natural. La condición sigue siendo estricta — basta **un** miembro para
que AC-13 vuelva a proteger, así que no hay ventana de robo de un tenant ya
adoptado.

### Compatibilidad con la decisión canónica `native_provision_authority` (D2)

D2 (app_spec.md §6, v6.9.3 / UC-820,821) establece: *"un proyecto pre-existente
del que el caller no es miembro NO se auto-une (FORBIDDEN)"*. Este discovery
**no contradice D2 — lo refina precisando qué cuenta como "proyecto
pre-existente"**:

- "Proyecto pre-existente protegido por D2/AC-13" = una fila en `public.projects`
  **CON ≥1 miembro**. Tiene dueño; auto-unirse a él es el robo que D2 previene.
  Este caso sigue devolviendo **FORBIDDEN**, sin cambios.
- "Tenant huérfano" = una fila en `public.projects` con **CERO miembros**. Es un
  artefacto de un `setup_board` que dejó la provisión a medias, no un proyecto
  con dueño. D2 nunca pretendió proteger esto (un huérfano no tiene a quién
  robar). La auto-provisión lo **adopta**, completando lo que `setup_board`
  dejó incompleto.

El invariante de D2 ("el creador es el primer y único admin de bootstrap") se
**preserva**: tras adoptar, el caller es el primer admin del tenant, exactamente
como si lo hubiera creado desde cero. FIX A elimina además la causa del huérfano,
de modo que el caso de adopción se vuelve un fallback defensivo para estados
sucios legacy, no el camino normal.

### Idempotencia y robustez a estados sucios

- `provision_native_project` ya es idempotente (UPSERT projects + UPSERT
  membership sin degradar admin). Llamarlo sobre un huérfano lo completa; sobre
  un tenant ya adoptado por el mismo caller es no-op.
- Tras adoptar, `_maybe_auto_provision` ya limpia la cache de auth
  (`_clear_auth_cache`) para que el gate de membresía relea el edge fresco. Ese
  comportamiento se conserva.
- El flujo se vuelve **convergente**: cualquier estado sucio (0 miembros) se
  recupera a estado limpio (1 miembro = el creador admin) en el primer
  `start_migration_session`, sin FORBIDDEN.

## Drift from app_market

- **Nuevos ICPs introducidos**: ninguno. Hereda ICP-1 (owner-operator) de
  `app_market.md`.
- **Nuevos JTBDs introducidos**: los JR-FOTP.* / JE-FOTP.* son derivaciones
  específicas de los JTBDs globales JR-G.1, JR-G.3, JE-G.2 ya canónicos; no
  introducen un job nuevo a nivel de producto, solo lo instancian para esta
  corrección de infraestructura.
- **Resolución**: `no_drift` — la feature no introduce ICPs ni JTBDs nuevos a
  nivel de producto. Es una corrección de robustez de la infraestructura native
  que sirve a los jobs canónicos existentes.

## Verdict

**READY_FOR_PRD**

- ICP heredado e identificado (ICP-1).
- JTBDs racionales y emocionales capturados (heredados + instanciados).
- Validation evidence: datapoint de dogfooding con repro SQL + file:line.
- Drift resuelto: `no_drift`.
- Decisión de diseño técnica cerrada: **Enfoque Combinado (3)**, con seguridad
  razonada y el invariante explícito ("un tenant native nunca sin miembros; si
  lo está, se adopta").

---

> Next step: `/prd orphan_tenant_provision`
