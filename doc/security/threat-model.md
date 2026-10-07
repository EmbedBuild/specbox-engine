# Modelo de amenazas del MCP remoto de SpecBox

> **Referencia obligatoria para cualquier tool nueva del servidor** (US-43/UC-4303). Antes de
> registrar una tool con `@mcp.tool`, pasa la lista de la sección 8 y actualiza la tabla de la
> sección 4 en la misma PR. Vigente para el engine 6.14.1 (2026-09-29); se revisa con cada
> cambio en `server/coordination/` o en el transporte.

## 1. Qué protege

| Activo | Dónde vive | Quién debe verlo |
|---|---|---|
| El board de cada tenant (US/UC/AC, reservas, ramas, comentarios, auditoría) | Postgres gestionado (Supabase), esquema `public` | Solo los miembros del proyecto (`project_members`) |
| La identidad de cada persona (`developers`, `mcp_tokens`, `github_identities`, membresías) | Mismo Postgres | La persona y el panel cloud; el servidor solo la resuelve |
| El registro de proyectos onboarded y el estado del servidor (`STATE_PATH`) | Volumen del contenedor | Quien registró cada entrada o es miembro del tenant al que está ligada |
| El registro de accesos por tool (`tool_access_log`) | Postgres, solo inserción | El operador |
| Los ficheros del cliente (`doc/tracking`, PRDs, planes) | La máquina de la persona | El servidor **nunca** los lee: trabaja con el contenido que el cliente envía |

## 2. Quién puede llamar

| Actor | Cómo se identifica | Qué se le permite |
|---|---|---|
| **Persona identificada** (developer) | Token de dispositivo en `Authorization: Bearer` en cada petición HTTP (lo envía la extensión de VSCode o el ayudante de cabeceras de `specbox login`), o `set_auth_token(backend_type="native", token=…)` en la sesión | Sus proyectos, sus reservas, sus entradas del registro |
| **Administrador de proyecto** (`project_admin`) | Igual, con ese rol en `project_members` | Además, sembrar o mutar el tenant (`setup_board`, `import_spec`, …) |
| **Operador** | SuperAdmin del panel (`panel.profiles.role='superadmin'` enlazado por `developer_id`) o id listado en `SPECBOX_OPERATOR_DEVELOPER_IDS` | Registro de accesos y reinicios de estado |
| **Conexión sin identidad** | Sin token (o token que no resuelve) | Según `SPECBOX_TRANSPORT_AUTH`: `off` deja pasar, `grace` avisa con fecha límite, `enforce` rechaza (401). En cualquier modo, ninguna tool de datos responde sin identidad: `UNAUTHENTICATED` uniforme y sin datos |
| **Servicios internos** (API del panel con `service_role`, publicador del site) | Credenciales propias, fuera del MCP | No pasan por el servidor MCP |
| **Proxy inverso** (Traefik) | Añade `X-Forwarded-For` | Es la única fuente fiable de la IP del cliente para los límites |

En transporte `stdio` (servidor local) no hay autenticación de transporte: quien lo ejecuta es la
dueña de la máquina y del estado.

## 3. Superficie de entrada

```
cliente ──HTTPS──▶ proxy ──▶ TransportAuthMiddleware ──▶ AbuseGuardMiddleware ──▶ FastMCP
                                (token → identidad)        (2 MB, 60/min)          │
                                                                        ToolAccessLogMiddleware
                                                                                   │
                                                                                 tool
```

- `/mcp` (streamable-http) y `/sse`: todas las peticiones, la inicialización incluida, pasan por
  los tres middlewares en ese orden (`server/coordination/transport_auth.py`,
  `server/coordination/abuse_guard.py`, `server/coordination/access_log.py`).
- `/health`: sin token; devuelve solo estado y versión.
- No hay más rutas. El puerto del contenedor solo es alcanzable desde el proxy.

## 4. Con qué identidad se ejecuta cada tool

Orden de resolución (`server/coordination/scope.py::resolve_caller_scope`): el token explícito
de la tool (`dev_token`) manda sobre el de la sesión native (`set_auth_token`), y este sobre el
del transporte (`transport_identity`). El resultado es un `CallerScope` = developer + proyectos
de los que es miembro. Sin identidad, la tool devuelve el envelope `UNAUTHENTICATED` y **ningún
dato**; con identidad pero sin permiso, `FORBIDDEN` o «inexistente», nunca una pista.

| Categoría | Ejemplos | Identidad exigida | Alcance de los datos |
|---|---|---|---|
| Información del engine | `get_engine_version`, `get_supported_stacks`, `list_skills`, `get_global_rules` | Ninguna | Datos públicos del propio engine (los mismos que el repositorio) |
| Board native | `list_us`, `get_uc`, `start_uc`, `mark_ac`, `complete_uc`, `import_spec`, `delete_uc`, las de épicas (`add_epic`, `update_epic`, `delete_epic`, `set_us_epic`, `list_epics`, `get_epic`), `declare_satellites`, … | Developer miembro del proyecto que se lee o se escribe (el `board_id` de la llamada, US-34 y US-83) | Solo ese tenant: toda consulta lleva `project_id`; las PK son `(project_id, id)`. `delete_uc` con `purge=true` borra de verdad solo una UC sin trabajo y deja la copia en `audit_log` |
| Coordinación | `whoami`, `reserve_uc`, `release_uc`, `register_native_branch` | Developer | Su tenant; las reservas ajenas se ven, no se sueltan |
| Registro de proyectos y onboarding | `list_onboarded_projects`, `get_onboarding_status`, `onboard_project`, `upgrade_project`, `get_version_matrix`, `register_project`, `update_project_meta`, `archive_project`, `switch_backend`, `enable_mirror`, `disable_mirror` | Developer | Solo las entradas que registró o ligadas a un tenant del que es miembro (`CallerScope.can_see`). Lo ajeno se responde como inexistente (`PROJECT_NOT_VISIBLE`, `available` = solo lo propio) |
| FreeForm remoto | Cualquier tool de board con `items_content` | Ninguna (el contenido es del cliente) | Únicamente el contenido enviado en esa llamada; el servidor no lo persiste ni lee su disco (`FREEFORM_REMOTE_DISK_MODE_REJECTED`, `FREEFORM_CONTENT_REQUIRED`) |
| Diseño (Stitch, Claude Design) | `stitch_*`, `claude_design_*` | Credencial del proyecto en la sesión | Solo la cuenta de diseño configurada en esa sesión. La clave de Stitch vive solo en la sesión: el servidor no la escribe en disco ni la lee de él, y otra sesión que nombre el mismo proyecto no puede usarla (UC-8601). Los registros de uso (`stitch_usage.jsonl`, `claude_design_usage.jsonl`) solo se escriben con servidor local: en remoto ya está el registro de accesos (UC-8603) |
| Telemetría y estado de un proyecto | `report_*` (sesión, checkpoint, healing, aceptación, merge, feedback, e2e), `report_heartbeat`, `get_project_activity`, `get_project_timeline`, `attach_audit_evidence`, `get_last_audit`, `upload_design_md_to_stitch` | En remoto, developer que ve el proyecto; en `stdio`, ninguna | Solo `STATE_PATH/projects/<project>` de un proyecto registrado y visible (`CallerScope.can_see`); lo ajeno o lo no registrado se responde como inexistente (`PROJECT_NOT_VISIBLE`, `available` = solo lo propio) y no se registra solo. El nombre se valida en todo transporte (`INVALID_PROJECT_NAME`): un nombre o un `owner/repo`, nunca fuera de `projects/` (`ProjectStateScopeMiddleware`, `project_state_dir`, UC-8603) |
| Documentos canónicos, cola y decisiones (`app_docs`) | `verify_app_docs`, `apply_app_docs_sync`, `record_app_docs_signature`, las de decisiones canónicas y de la cola, `evaluate_autopilot_decision`, `detect_app_docs_drift`, `detect_project_backend`, las de la migración v5.29, `get_implementation_status`, `write_implementation_status` | Ninguna (el contenido es del cliente) | En remoto no leen ni escriben el disco: responden `APP_DOCS_CONTENT_REQUIRED` antes de resolver la ruta, también con el valor por defecto `"."` (`ClientPathGuardMiddleware`, UC-8604) |
| Otras tools con una ruta del cliente | `claude_design_status`/`create_project`/`sync_design_system` (`project_root`), `upload_design_md_to_stitch`, `validate_stitch_prompt` (`project_root`), `sync_multirepo_state`, `migrate_to_freeform_tool` | Las de su categoría | En remoto responden `REMOTE_PATH_REJECTED` sin tocar el disco cuando reciben la ruta. `switch_backend`, `switch_project_backend`, `enable_mirror` y `disable_mirror` escriben solo el registro y devuelven `client_writes` (settings y zona `tracking_backend`) para que el cliente los aplique (UC-8604) |
| Documento de diseño | `generate_design_md_tool`, `get_visual_gap_report` (`code_files`) | Ninguna (el contenido es del cliente) | Únicamente los ficheros enviados en esa llamada (`*_content`); en remoto no lee ni escribe el disco ni guarda nada del proyecto (`DESIGN_MD_CONTENT_REQUIRED`) |
| Operación | `get_tool_access_log`, `reset_all_state`, `reset_project` | Operador | Global; cada reinicio queda en el registro de accesos como `state_reset` |

## 5. Qué se comparte entre clientes y qué no

- **Compartido por diseño**: dentro de un tenant, todos sus miembros ven el mismo board y las
  mismas reservas. Esa es la razón de ser del backend native.
- **Nunca sale del servidor**: los tokens (no se registran ni se devuelven; el registro de
  accesos guarda un hash en memoria durante 30 s), el DSN de la base (`SPECBOX_NATIVE_DSN`, solo
  en el entorno), los valores de los argumentos de las llamadas (el registro guarda solo sus
  nombres), el contenido FreeForm de un cliente (no se persiste), y las rutas locales o
  descripciones de los proyectos (ya no se almacenan; `SENSITIVE_REGISTRY_FIELDS`).
- **Nunca se revela a otro tenant**: la existencia de un proyecto, de una persona o de un token.
- **Solo el operador**: el registro de accesos completo, incluidas las llamadas sin identidad.

## 6. Amenazas consideradas

| # | Amenaza | Mitigación | Dónde se prueba |
|---|---|---|---|
| T1 | Una sesión lee o escribe el board de otro tenant | Toda lectura y toda escritura native valida la membresía del proyecto que toca, no el de la sesión (escrituras desde US-34, lecturas desde US-83/UC-8301), y el intento deja `cross_tenant_denied` en la auditoría de ese proyecto; PK compuestas `(project_id, id)`; RLS y denegaciones restrictivas para los roles públicos en la base | `tests/test_tenant_isolation.py` (inventarios de mutadores y de lecturas), `tests/test_native_mutation_authz.py`, `tests/test_native_tenant_pk.py`, `tests/test_db_surface_tables.py` |
| T2 | Enumerar proyectos o personas que no son propios | `CallerScope.can_see`; lo ajeno = inexistente; `available` solo con lo propio, también en las lecturas de actividad (UC-8603); `PROJECT_NAME_TAKEN` sin más detalle | `tests/test_registry_scope.py`, `tests/test_project_state_scope.py` |
| T3 | Leer o escribir el disco del servidor a través de cualquier tool que reciba una ruta del cliente (FreeForm, DESIGN.md, documentos canónicos, decisiones, migraciones, Claude Design, cambio de backend…) | `is_remote_transport()` decide por el transporte del servidor; modo `content_only`; `.dockerignore` excluye `doc/tracking/`; `generate_design_md_tool` solo acepta contenido en remoto; `ClientPathGuardMiddleware` responde antes de resolver la ruta (`APP_DOCS_CONTENT_REQUIRED`, `REMOTE_PATH_REJECTED`); el cambio de backend en remoto escribe solo el registro y devuelve `client_writes` (US-86/UC-8604); un inventario sobre las tools registradas falla si aparece una con ruta sin guarda ni motivo | `tests/test_freeform_remote*.py`, `tests/test_design_md_system_tokens.py`, `tests/test_client_path_guard.py` |
| T4 | Usar un token caducado, revocado o de otro dispositivo | Caducidad (90 días), revocación con motivo, un token activo por dispositivo, rechazo `401` antes de la sesión; caché de identidad de 30 s | `tests/test_device_tokens.py`, `tests/test_transport_auth.py` |
| T5 | Conectar sin identidad y usar tools de datos | `SPECBOX_TRANSPORT_AUTH` (`grace` con fecha límite, `enforce`); las tools de datos exigen identidad en cualquier modo. Las que trabajan sobre ficheros del cliente no exigen identidad porque en remoto no tocan nada del servidor (T3); las de estado por proyecto la exigen desde UC-8603 (T17) | `tests/test_transport_auth.py`, `tests/test_native_unauthenticated.py`, `tests/test_client_path_guard.py`, `tests/test_project_state_scope.py` |
| T6 | Abuso por volumen (cuerpos enormes, ráfagas de llamadas) | 2 MB por petición; 60 `tools/call` por minuto por identidad, o por IP del proxy sin token; `413`/`429` con `Retry-After` | `tests/test_abuse_guard.py` |
| T7 | Escalada dentro del contenedor | Proceso como `specbox` (uid 10001); `/app` de solo lectura; `setpriv` en el arranque | `scripts/verify-nonroot.sh`, workflow `container-nonroot.yml` |
| T8 | Borrar el estado del servidor o de un proyecto sin ser operador | Palabra de confirmación **y** identidad de operador; evento `state_reset` en el registro de accesos | `tests/test_state_reset_operator.py` |
| T9 | Fuga de credenciales en logs, exports o configuración | DSN solo en el entorno; tokens redactados; nada de secretos en `meta.json` ni en los exports del board (la clave de Stitch tampoco, desde UC-8601); el publicador del site redacta el `service_role` | `tests/test_tool_access_log.py`, `tests/test_site_publish_publisher.py`, `tests/test_stitch_key_session_only.py` |
| T10 | Superficie de la base expuesta por PostgREST (vistas, funciones o tablas con roles públicos) | Migraciones 0023/0024; `python -m server.db.surface_check` en CI con lista aprobada con motivo | `tests/test_db_surface_*.py`, workflow `db-surface-check.yml` |
| T11 | Un paquete antiguo devuelve la extensión a una versión anterior | `install-ext.mjs` solo instala la versión esperada; el updater no retrocede | `vscode-extension/tests/extension-no-downgrade.test.mjs` |
| T12 | Falsear la IP para repartir los límites entre varias identidades | Se toma el último `X-Forwarded-For`, el que escribe el proxy; el cliente no puede añadirlo detrás | `tests/test_abuse_guard.py` |
| T13 | Versión anunciada distinta de la publicada (cliente que cree estar al día) | El handshake anuncia `ENGINE_VERSION.yaml`; una prueba lo compara con el changelog | `tests/test_engine_version_contract.py` |
| T14 | Borrar sin rastro trabajo hecho, o una UC de otro tenant, con el borrado real (`delete_uc` + `purge=true`) | Solo UC en backlog o archivada, sin AC hechos, sin evidencia y sin reserva, comprobado dentro de la transacción con la UC bloqueada; membresía del tenant que se escribe; lo rechazado se archiva, nunca se pierde; copia de la UC y de sus AC en `audit_log` (`purge_uc`), que no se borra | `tests/test_uc_purge.py` |
| T15 | Hacerse miembro de un proyecto ajeno abriendo sesión en él | `setup_board` (lo que ejecuta `set_auth_token` native) solo da rol al crear un proyecto o adoptar uno sin miembros; en uno con miembros exige serlo ya (`FORBIDDEN` si no) y nunca cambia el rol (D2, US-83/UC-8302) | `tests/test_native_provision.py` |
| T16 | Usar la credencial de diseño de otro proyecto nombrándolo | `stitch_set_api_key` guarda la clave solo en la sesión (estado de FastMCP con el identificador de la sesión como prefijo); ninguna tool `stitch_*` la busca en disco, así que sin clave en la sesión responde que falta configurarla (US-86/UC-8601) | `tests/test_stitch_key_session_only.py` |
| T17 | Leer o escribir el estado de otro proyecto nombrándolo (telemetría, actividad, evidencia de auditoría) o salir de `projects/` con el nombre | `ProjectStateScopeMiddleware`: nombre válido en todo transporte y, en remoto, identidad y proyecto visible antes de llamar a la tool; `project_state_dir` es la única forma de construir la carpeta de un proyecto; sin registro automático en remoto (US-86/UC-8603) | `tests/test_project_state_scope.py` |

## 7. Supuestos y fuera de alcance

- El proveedor de la base (Supabase), el VPS y el proxy no están comprometidos.
- La máquina de la persona y el almacén seguro de su sistema (Llavero, Secret Service, DPAPI)
  son de confianza; el cliente MCP se ejecuta ahí.
- El panel cloud y su API tienen su propio modelo (repositorio `specbox_cloud`) y son los únicos
  que usan `service_role`.
- Un miembro legítimo de un tenant puede exportar su board: eso es uso, no amenaza.

## 8. Lista obligatoria para una tool nueva

1. **¿Toca datos de alguien?** Resuelve la identidad con `resolve_caller_scope(ctx, token=…)` (o
   `transport_identity`) y responde `UNAUTHENTICATED`/`FORBIDDEN` uniformes, sin datos, cuando
   falte o no alcance.
2. **Filtra siempre por el tenant de la sesión** (`project_id`) en SQL. Un `board_id` o
   `project_id` que llega del cliente no vale nada hasta comprobar la membresía.
3. **Nada del disco del servidor en transporte remoto**: recibe el contenido (`items_content`) y
   devuélvelo mutado; no escribas marcadores locales (`_marker_is_local`).
4. **No devuelvas ni registres** tokens, DSN ni valores de argumentos. El registro de accesos ya
   anota la llamada; no dupliques con `print`/logs propios.
5. **Lo ajeno se responde como inexistente**, sin listas ni sugerencias.
6. **Si escribe en la base**: migración con RLS activa y denegación restrictiva para `anon` y
   `authenticated`; pasa `surface_check`; añade la excepción a `surface_allowlist.yaml` solo con
   motivo.
7. **Pruebas mínimas**: un caso sin identidad, un caso de otro developer (no ve, no escribe) y,
   si hay límites o confirmaciones, un caso que los dispara.
8. **Actualiza este documento** (categoría en la sección 4 y, si aplica, una fila en la sección
   6) en la misma PR.

## Referencias

- `server/coordination/transport_auth.py`, `abuse_guard.py`, `identity.py`, `scope.py`,
  `access_log.py`; `server/transport.py`; `server/db/surface_check.py`.
- Runbooks: `doc/runbooks/transport-auth.md`, `doc/runbooks/tool-access-log.md`,
  `doc/runbooks/db-surface.md`, `doc/runbooks/registry-hygiene.md`.
- Política de divulgación: `SECURITY.md`.
