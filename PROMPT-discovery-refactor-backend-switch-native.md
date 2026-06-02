# Prompt: Discovery + Refactor del cambio de backend hacia/desde Native (Cloud)

> Dispara esto desde una sesión de Claude **dentro del repo `specbox-engine`**.
> Es un trabajo de discovery + refactor de fondo, no un parche. Sigue el propio
> pipeline del engine (`/discovery` → `/prd` → `/plan` → `/implement`).

---

## Contexto (descubierto en dogfooding real, 2026-06-02)

Soy el dueño de SpecBox. Operando el producto **como cliente real** sobre el panel
**SpecBox Cloud** (repo hermano `specbox_cloud`, frontend del backend native), descubrí
que **el cambio de backend hacia/desde `native` (Cloud) está roto para el escenario
real de despliegue: MCP remoto + archivos del cliente en local + datos productivos en
Supabase.** Quiero un **discovery honesto** del flujo completo y luego un **refactor**.

### Lo que reproduje en vivo (evidencia, no teoría)

1. Un proyecto en backend **freeform** (tracking en `doc/tracking/*.md` del cliente)
   cuyo panel Cloud lee de **Postgres native** (Supabase). Son dos fuentes que nadie
   reconcilia: una US nueva creada por `/prd` en freeform **nunca llega a la BD**, así
   que el panel no la ve. La BD se pobló **una sola vez a mano** vía `import_spec` en un
   smoke-test.

2. Intenté `migrate_backend(source_type='freeform', source_id='.', target_type='native', ...)`
   con **dry_run**. El preview leyó el filesystem del **servidor MCP remoto** (`/app/...`),
   no el repo local del cliente:
   - Desde una sesión → devolvió **22 US / 112 UC** (el tracking del *engine*, que vive en
     el disco del servidor), no las **11 US / 88 UC** del panel.
   - Desde otra sesión con `.` → devolvió **0 / 0** (un directorio vacío del servidor).
   - En ambos casos: **`source_id='.'` se resuelve contra el CWD del servidor remoto, no
     contra el repo del cliente.** Ejecutar `dry_run=False` habría escrito un proyecto
     vacío (o el del engine) en native y luego `switch_backend` habría apuntado el panel
     a la nada.

3. Conclusión: `migrate_backend` / `migrate_preview` / `_read_source` **no usan
   content-passing** (el patrón que el engine YA adoptó en v6.0.1 "MCP Path Contract"
   para otras 17 tools cat-A). Son un **hueco no cubierto**.

### Lo que ya existe en el engine (NO duplicar, verifícalo y reúsalo)

- **`detect_local_root_path()`** (`server/tools/onboarding.py:478`) — handshake v6.0.1 que
  declara si el MCP es remoto y la receta de resolución de path en cliente.
- **Patrón content-passing** ya aplicado a `read_app_docs_tool`, `get_inheritable_values_tool`,
  etc. (param `*_content`, el cliente lee sus archivos y pasa el **contenido**, no el path).
- **`US-MCP-PATH-CONTRACT`** (10 UC, UC-614…623, status `ready`) — la deuda ya identificada
  de portar 17 tools cat-A a content-passing. **PERO `migrate_backend`/`switch_backend`/
  `migrate_preview` NO están en su alcance.** Este trabajo cierra ese hueco.
- **Native como TARGET**: `setup_board` (`server/backends/native_backend.py:336`, UPSERT
  `ON CONFLICT`), `seed_native_identity` (`server/migration/native_handling.py`).
- **Native como SOURCE**: `collect_discarded_native_state`, `build_native_exit_report`
  (`migration.py:578-587`, `native_handling.py`) — ya hay andamiaje para salir de native.
- **`apply_switch_transactional`** (`server/migration/transactional_switch.py`) — actualiza
  atómicamente 3 lugares (registry / app_spec / settings) con rollback; YA contempla native.
- **`NativeBackend.list_items` / `get_acceptance_criteria` / `get_item_children`**
  (`native_backend.py:374+`) — lectura usable para native-como-source.

---

## PRINCIPIO RECTOR DEL REFACTOR (esto es el corazón del encargo)

Hoy "cambiar de backend" está partido en **procesos separados** que el usuario/agente debe
encadenar a mano: `migrate_backend` (copia datos) + `seed_native_identity` + `switch_backend`
(cambia el flag de config) + helpers de salida (`collect_discarded_native_state`…). **Esa
separación ES la causa raíz de los estados rotos** que reproduje:

- solo `switch_backend` → config dice "native" pero la BD queda vacía → el panel no muestra nada.
- solo `migrate_backend` → datos en la BD pero la config sigue en freeform → el engine sigue
  escribiendo a archivos.
- en orden equivocado o con un paso olvidado → limbo inconsistente, rollback parcial.

**Quiero que rediseñes "cambiar de backend" como UNA sola operación atómica y completa.** El
usuario emite una orden ("pasa mi proyecto a Cloud" / "saca mi proyecto de Cloud a freeform")
y el sistema ejecuta **internamente toda la cadena de propagación que ese origen×destino
requiera**, de forma transaccional, con preview/dry-run fiable y rollback total: o queda todo
bien, o no queda nada a medias. `migrate_backend` / `seed_native_identity` / `switch` /
helpers de salida pasan a ser **piezas internas** de esa operación, no tools que el usuario
invoca por separado y puede olvidar.

El discovery DEBE producir una **matriz origen × destino** (freeform / trello / plane / native)
que defina, para cada combinación, la lista completa de pasos de propagación requeridos
(p. ej. "→ native": auth dev_token, leer source por content-passing, crear proyecto en
Postgres, copiar US/UC/AC preservando estados, asociar developer; "native →": además volcar
reservas/membresías/audit/coordination decidiendo qué se preserva y qué se descarta). El
path-bug de MCP-remoto se arregla **dentro** de esta operación unificada (el source nunca se
lee del filesystem del servidor), no como parche aislado.

## Lo que quiero que hagas

### FASE 1 — Discovery (usa `/discovery`)

Haz un discovery honesto del **caso de uso completo "cambiar el backend de un proyecto"**,
partiendo del PRINCIPIO RECTOR de arriba (operación única atómica + matriz origen×destino),
con foco en los dos escenarios que hoy fallan o están incompletos:

- **Destino = native (Cloud):** un cliente con su proyecto en local (freeform/trello/plane)
  quiere "subirlo a SpecBox Cloud". ¿Qué tiene que pasar EXACTAMENTE? (auth con dev_token
  del panel, lectura del source SIN depender del filesystem del servidor remoto, creación
  del proyecto + copia de US/UC/AC a Postgres, asociación del developer como project_admin,
  preservación de estados — hoy `import_spec`/migrate degradan todo a `backlog`, el "G11",
  idempotencia, qué pasa si el proyecto ya existe en native).
- **Origen = native (Cloud):** un proyecto que vive en Cloud quiere salir a otro backend.
  ¿Qué se lee de Postgres, qué pasa con reservas/membresías/audit/coordination, qué se
  descarta y qué se preserva?

Cubre explícitamente, como restricciones del discovery:
- **MCP remoto + cliente local** es el modo de despliegue por defecto (online-first, v6.7+).
  Cualquier resolución de `source_id='.'` contra el servidor es un bug. El source freeform
  DEBE llegar por content-passing o por path absoluto resuelto en cliente.
- **Datos productivos**: la operación toca una BD real. Necesita dry-run fiable (que lea el
  source correcto), backup/preview, idempotencia y rollback.
- **Identidad**: native exige dev_token (lo emite el panel). El flujo debe fallar pronto y
  con mensaje claro si falta, no a mitad de escritura.
- **Coherencia con las decisiones canónicas del Cloud**: el panel NO hace CRUD de specs; el
  service_role solo vive en la API; el front nunca escribe Postgres. El sync lo hace el
  engine/MCP, no la app.

Entrega el discovery con ICP/JTBD, los casos límite, y un mapa "estado actual vs estado
deseado" de cada pieza (migrate_preview, migrate_backend, _read_source, switch_backend,
onboard_project a native).

### FASE 2 — PRD + Plan (usa `/prd` y `/plan`)

Genera una US propia (migrate/switch quedaron fuera del alcance de `US-MCP-PATH-CONTRACT`)
que cubra el **rediseño de "cambiar de backend" como operación única, atómica y completa**,
con la matriz origen×destino del discovery como contrato. Las tools actuales (`migrate_backend`,
`switch_backend`, `seed_native_identity`, helpers de salida) se reorganizan como **pasos
internos** de esa operación, no como interfaz pública que el usuario encadena. Incluye como
mínimo:

1. `migrate_preview` y `migrate_backend`/`migrate_project` con **content-passing**
   (param tipo `items_content` / `source_content`) para que el source freeform/trello/plane
   se lea desde el CONTENIDO que pasa el cliente, nunca desde el filesystem del servidor.
   `_read_source` refactorizado en consecuencia.
2. Resolución de path en cliente reutilizando `detect_local_root_path` (handshake) cuando el
   source sea filesystem y el MCP remoto — con verificación de conteo (el dry-run debe poder
   afirmar "N US / M UC leídas del cliente" y el cliente confirmar antes de escribir).
3. Flujo **destino native** end-to-end: auth dev_token → preview fiable → crear proyecto +
   copiar US/UC/AC a Postgres → asociar developer → **preservar estados** (resolver G11, no
   degradar todo a backlog) → idempotencia/colisión de project_id → switch_backend atómico.
4. Flujo **origen native** end-to-end: lectura desde Postgres como source vía content/DTO,
   manejo de reservas/membresías/audit/coordination al salir, reporte de lo descartado.
5. `onboard_project --backend native`: que deje claro/cierre el caso "proyecto en registry
   pero BD vacía" (o documente que requiere migrate/populate explícito).
6. **Guard rails**: dry-run que no pueda leer el source equivocado (si lee 0 o un proyecto
   que no es el esperado, avisar y no permitir el real), preview con backup, rollback.
7. E2E que reproduzcan el bug original: migrar freeform-local → native con MCP remoto y
   confirmar que lee el conteo del CLIENTE, no del servidor.

### FASE 3 — Implement (usa `/implement`)

Implementa por UCs siguiendo el autopilot. Calidad sobre velocidad.

---

## Verificación de no-regresión (dato real para tus tests)

El proyecto dogfood `EmbedBuild/specbox_cloud` en Supabase está **vacío ahora mismo**
(lo borré en una sesión de diagnóstico, con backup completo en el repo del panel:
`.quality/dogfood-backup/native-project-backup-pre-delete.json` — 10 US / 84 UC / 440 AC /
8 audit / 1 membership). Su tracking freeform local (en el repo `specbox_cloud`) tiene
**11 US / 88 UC** (incluye una US-13 nueva). Un `migrate_backend freeform→native` correcto
DEBE leer **11 US / 88 UC del cliente** y reconstruir el proyecto en Postgres con el
developer `jesusperezdeveloper` como project_admin y los estados preservados.

**Empieza por `/discovery`. No escribas código hasta tener el discovery y el plan aprobados.**
