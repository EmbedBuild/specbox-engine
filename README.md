<p align="center">
  <img src=".github/assets/Logo SpecBox.png" alt="SpecBox Engine" width="280" />
</p>

<h1 align="center">SpecBox Engine</h1>

<p align="center">
  <strong>Programación agéntica con Claude Code, sin ceder calidad por velocidad.</strong><br/>
  v 6.22.2 — "Mesura" (sobre v6.22.1 "Llave")<br/>
  <a href="https://specbox.build">specbox.build</a> · <a href="#english-version">English version below</a>
</p>

---

## ¿Qué es esto?

Un sistema que convierte a Claude Code en un compañero de equipo serio:

- **Te ayuda a ir rápido** sin saltarse trazabilidad ni calidad.
- **Aprende de tu proyecto** y deja de preguntarte lo que ya has decidido.
- **Bloquea atajos peligrosos** (push a main, AC vagos, code sin UC, paths inseguros).
- **Convive con tu flujo**: spec-driven con FreeForm/Trello/Plane según el cliente.

> The LLM provides speed. SpecBox provides quality and traceability.

---

## Lo nuevo en v6.22

**v6.22.0 — "Cerrojo"** echa el cerrojo a lo que el servidor alojado abría a quien nombrara un proyecto, y pone las tools de Stitch al día con su API:

- **La clave de Stitch vive solo en tu sesión** — el servidor ya no la guarda en disco, y otra sesión que nombre tu proyecto no puede usarla. `/plan` y `/visual-setup` la vuelven a enviar en cada sesión.
- **El estado de un proyecto solo lo toca quien lo ve** — en el servidor alojado, la telemetría, la actividad y la evidencia de auditoría exigen que el proyecto sea tuyo, y los errores solo listan tus proyectos.
- **El servidor alojado no lee ni escribe tu disco** — las tools que reciben una ruta de tu máquina responden antes de tocar nada; úsalas con el MCP local. Cambiar de backend devuelve los cambios de tus ficheros para que los escribas tú.
- **Una prueba impide que vuelva a pasar** — recorre todas las tools registradas y falla si una nueva abre alguno de estos huecos.
- **Stitch, al día** — llamadas con la forma actual de la API, errores que llegan como errores, esperas de 6 minutos sin repetir la generación, modelo por defecto `GEMINI_3_8_FLASH`, sistemas de diseño de la cuenta y proyectos compartidos.

Con el MCP alojado cambia una cosa: las tools de documentos canónicos, cola, decisiones y estado de implementación responden con un aviso en vez de usar el disco del servidor. Con el MCP local todo sigue igual.

**v6.22.1 — "Llave"** devuelve esas tools al MCP alojado: les envías tus ficheros y te devuelven lo que hay que escribir, sin que el servidor toque su disco. Además, el MCP lee del board solo lo que necesita y la extensión pregunta quién eres cada 30 minutos en vez de cada minuto.

**v6.22.2 — "Mesura"** hace que la pestaña de cambios de la extensión en el Marketplace vuelva a decir qué cambia en cada versión.

---

## Lo nuevo en v6.21

**v6.21.0 — "Gavilla"** ata las historias en épicas, como espigas en un haz:

- **Épicas en el board** — por encima de la historia hay una sola agrupación, la épica, con nombre, objetivo y orden. Su estado y su avance no se escriben: se deducen de sus historias, y sin criterios no inventa un 0 %.
- **Todo el flujo las conoce** — seis tools para crearlas y consultarlas; las lecturas dicen la épica y el satélite de cada historia y caso de uso; `/prd` pregunta a qué épica va la feature y la siembra la crea; `/implement EP-NN` trabaja una épica de principio a fin.
- **Verificado no es aceptado** — el board guarda aparte la aceptación de una persona, que se anula sola si la UC deja de estar hecha, y la home pública cuenta cuántas UC cerradas aceptó alguien.
- **Cada proyecto solo se lee desde dentro** — las lecturas del board comprueban la membresía igual que las escrituras, y abrir sesión no hace miembro a nadie.
- **Los milestones se retiran en la 6.23.0** — siguen funcionando dos versiones más y avisan en cada respuesta; usa las épicas.

100% backwards-compatible: sin épicas, el board y el autopilot responden como siempre.

---

## Lo nuevo en v6.20

**v6.20.0 — "Cableado"** hace que los hooks que SpecBox promete lleguen conectados:

- **Los proyectos reciben todos los hooks** — la plantilla activa los siete que el engine usaba y no llegaban a los proyectos: retomar la sesión con el traspaso, avisar antes de leer ficheros enormes, el presupuesto de contexto y la propiedad de ficheros de los subagentes de `/implement`, las rutas de FreeForm, el gate de discovery y el de los documentos canónicos. Ninguno bloquea por defecto.
- **La extensión avisa de un hook roto** — «Comprobar salud» lista cada hook que un proyecto configura y no tiene en disco. Un hook que no arranca no protege.
- **`CLAUDE.md` cuenta lo que hay** — skills, hooks y agentes completos y comprobados en cada PR; el auditor de `/audit` pasa a AG-11.

100% backwards-compatible: ningún hook nuevo bloquea por defecto y no hay migraciones.

---

## Lo nuevo en v6.19

**v6.19.0 — "Escaparate"** hace que lo que el engine enseña en público cuadre con lo que tiene:

- **Un escaparate con recibos reales** — la home de [specbox.build](https://specbox.build) enseña en vivo una UC de nuestro propio board y los recibos de sus criterios, desde una vista pública de solo lectura que nunca enseña el detalle ni los criterios internos.
- **Cifras que cuadran** — el site cuenta las 192 tools que lista el MCP (antes 126), deja de contar lo retirado, conserva los nombres de código en el changelog y su foto de actividad suma.
- **Cada evento de AC sabe de qué UC es** — el `audit_log` guarda `uc_id` en cada marca, edición, alta o borrado de un criterio.
- **Una sola versión de cada migración** — `migration_twins.py` comprueba que `supabase/migrations` es copia exacta de `server/db/migrations`.
- **El hook dice lo que es** — el bloqueo de «lee antes de escribir» ya no dice que SpecBox aporta la velocidad: la velocidad la pone el modelo; SpecBox, el control y la calidad.

100% backwards-compatible: sin migraciones del board.

---

## Lo nuevo en v6.18

**v6.18.0 — "Mudanza"** lleva el servidor alojado a `mcp.specbox.build` y deja que los clientes se muden solos:

- **El servidor responde en `mcp.specbox.build`** — y en su nombre anterior, `mcp-specbox-engine.jpsdeveloper.com`, que sigue funcionando sin fecha de retirada. `scripts/check-mcp-hosts.mjs` comprueba que los dos responden igual: cada lunes en GitHub y en cada release con el token del ordenador.
- **La extensión y `specbox login` usan el nombre nuevo** — al actualizarse, la extensión reescribe las entradas de Claude Code que apuntaban al anterior (la de usuario y las de cada proyecto) y antes guarda una copia en `~/.specbox/backups/`, sin ningún token.
- **Nadie pierde la conexión** — la credencial del ordenador vale para los dos nombres: la que se guardó con el nombre anterior se sigue usando.
- **Todo bajo specbox.build** — el site vive en [specbox.build](https://specbox.build), el contacto es `hola@specbox.build`, y la política de seguridad, las guías de conexión y las páginas de npm y del Marketplace apuntan ahí.

100% backwards-compatible: una instalación sin actualizar sigue funcionando con el nombre anterior.

---

## Lo nuevo en v6.17

**v6.17.0 — "Evidencias"** hace que cada criterio de aceptación aceptado enseñe su recibo:

- **Recibos estructurados** — `mark_ac` y `mark_ac_batch` aceptan, además del texto libre de siempre, un recibo `{type: test|screenshot|diff|url|pr, label, link?, detail?}`. El board native lo guarda junto al AC con quién lo marcó y cuándo; un recibo mal formado no marca nada.
- **`get_uc` enseña los recibos** — por cada AC, sus evidencias con tipo, etiqueta, enlace, quién y cuándo, y quién lo aceptó. En Trello, Plane y FreeForm se reconstruyen de los comentarios con el autor desconocido: nunca se inventa.
- **Lo de antes también tiene recibo** — la migración 0028 convierte los comentarios «AC-XX: PASSED — …» en recibos con su fecha.
- **Las pruebas del backend native corren en cada PR** contra un Postgres real y la suite completa ya no se cuelga; la CLI espera a npm aunque la versión quede «staged», y el Postgres de desarrollo arranca en el puerto que elijas (`SPECBOX_NATIVE_PG_PORT`).

100% backwards-compatible: la evidencia en texto libre se guarda y se comenta igual que antes.

**v6.17.1 — "EngineFirst"** el engine crea proyectos aunque no haya panel: si no hay organización que asignar, `setup_board` crea el proyecto sin ella en vez de fallar.

---

## Lo nuevo en v6.16

**v6.16.0 — "Goma"** borra lo que se creó por error y corrige lo que salió mal al cerrar "Tinta":

- **Borrar de verdad una UC creada por error** — `delete_uc` con `purge=true` borra la UC, sus AC, sus transiciones, su reserva y su rama en una sola transacción y deja una copia en la auditoría. Solo si la UC nunca tuvo trabajo (en backlog o archivada, sin AC hechos, sin evidencia y sin reserva); si no, la archiva como siempre y dice por qué.
- **La extensión habla español de principio a fin** — con VSCode en español ya no aparecen avisos, botones ni pasos de instalación en inglés; `npm test` falla si un texto se queda sin traducir.
- **El comprobador de seguridad de cada release** ya no confunde los tokens de diseño con credenciales.

100% backwards-compatible: sin `purge`, `delete_uc` sigue archivando; en Trello y Plane, `purge` archiva.

---

## Lo nuevo en v6.15

**v6.15.0 — "Tinta"** pone el engine y la extensión a hablar el sistema de diseño único del ecosistema SpecBox: una sola fuente de colores, tipografía y componentes para el panel, el portal, el site y la extensión.

- **Las herramientas de diseño leen el sistema** — `generate_design_md_tool` toma los tokens del sistema (`design-system.tokens.json`) como única fuente y dice qué valores se salen; lo que generan Stitch y Claude Design queda marcado como candidato y `/plan` escribe la fuente de diseño de cada plan.
- **El gate de diseño bloquea lo que se sale del sistema** — colores escritos a mano, fuentes ajenas, pesos por encima del máximo y gradientes, con fichero y línea; en autopilot bloquea antes de pasar a revisión o abrir la PR.
- **La extensión habla el mismo idioma visual** — la página de vuelta del inicio de sesión y el diagnóstico usan los tokens del sistema (oscuros por defecto y con el tema de VSCode) e iconos Lucide con nombre; la barra de estado dice siempre la palabra del estado y, con todo bien, `[x] SpecBox vX · listo`.
- **La CLI `specbox` se publica sola en npm** con cada etiqueta (trusted publishing).

100% backwards-compatible: un proyecto sin tokens del sistema sigue con su Brand Kit y recibe un aviso con el enlace a la guía.

---

## Lo nuevo en v6.14

**v6.14.0 — "Front Door"** hace que nadie hable con el MCP remoto sin identificarse, y que conectarse no obligue a copiar tokens.

- **Autenticación en el transporte** — el servidor remoto comprueba el token en cada petición HTTP; el operador decide cuándo exigirlo (modos `off`, `grace` con aviso y fecha, `enforce`).
- **Un token por dispositivo, con caducidad** — iniciar sesión otra vez desde el mismo ordenador reemplaza el token en vez de sumar otro; caduca a los 90 días y se renueva solo.
- **`npx specbox login`** — un código de un solo uso que se confirma en el panel con GitHub; el token va al almacén seguro del sistema (Llavero, Secret Service, DPAPI) y Claude Code lo envía con un ayudante de cabeceras.
- **La extensión de VSCode hace lo mismo al iniciar sesión** — y, al actualizarse, conecta el ordenador sin pasos manuales. La barra de estado enseña con qué cuenta y dispositivo, y cuándo caduca.
- **Aislamiento por usuario** — el backend FreeForm remoto trabaja solo con el contenido que envía el cliente, el registro de proyectos solo enseña los de quien llama, cada llamada a una tool queda en un registro de accesos y la base de datos del board solo es legible por quien tiene permiso.

100% backwards-compatible: la autenticación del transporte nace en `off` y los tokens existentes siguen funcionando.

**v6.14.1 — "Forward Only"** — la extensión nunca se degrada al actualizarse, los tokens anteriores a la caducidad caducan el 2026-12-28, `SECURITY.md` explica cómo avisar de un problema de seguridad y el release exige que cada versión con cambios de seguridad cuente qué evita.

**v6.14.2 — "Idle Watch"** — un token sin uso durante 60 días se revoca solo (el reloj empieza el 2026-09-29, así que el primero cae el 2026-11-28), nadie tiene más de cinco dispositivos (el sexto no entra hasta desconectar otro, y el panel enseña cuál) y la extensión mantiene la conexión del ordenador antes de cualquier aviso de arranque que pueda quedarse esperando.

---

## Lo nuevo en v6.13

**v6.13.0 — "Tenant Guard"** cruza dos historias en el mismo punto: qué se le enseña al cliente y quién puede tocarlo.

- **La membresía se valida contra el proyecto que se escribe** — no contra el de la sesión. Cierra una escritura cruzada entre clientes en los mutadores del backend native. El guard vive en un único punto, así que el mutador número catorce lo hereda sin que nadie se acuerde.
- **Criterios de aceptación como entregable** — el campo `internal` oculta lo que no se le enseña al cliente, pero **sigue contando** en el avance: ocultar no descuenta.
- **El gate de testabilidad pasa del 30,54 % al 98,17 %** — aprobaba lo vago ("debe ser rápida") y rechazaba lo verificable por tests.
- **Check de exposición** — avisa de criterios que citan credenciales o rutas internas. Avisa, no bloquea.

100% backwards-compatible. `internal` nace en `false`: ningún criterio existente cambia de visibilidad.

---

## Lo nuevo en v6.12

**v6.12.0 — "Claude Design Native"** añade **Claude Design** como segundo proveedor visual del VEG, alineando la plataforma de diseño con la de ejecución (SpecBox es agéntico para Claude):

- **Proveedor visual seleccionable por proyecto** — `veg.providers` ∈ `["stitch"]`, `["claude_design"]` o ambos. Claude Design diseña con los **componentes reales compilados** del design-system (1:1 a código), no con mockups de texto.
- **Preferido cuando hay design-system compilado** — Stitch queda como fallback para la fase temprana sin código. Un proyecto sin config nueva se comporta **exactamente como hoy** (solo Stitch).
- **Sin tokens** — usa el login de claude.ai de la máquina vía la tool `DesignSync`; el consumo recae en la **suscripción del usuario logueado**. Sin login → `pending`.
- **Anclaje por topología** — en multirepo el design-system vive una sola vez en el **orquestador** (los satélites de UI lo consumen); en monorepo, en el repo. Gate que detecta `package.json` + `dist/`/Storybook.
- **5 MCP tools `claude_design_*`** + integración en `/visual-setup` y `/plan` + motor de sync idempotente que delega en `/design-sync`.

100% backwards-compatible. Stitch sigue siendo el default; no hay borrado programático de proyectos Claude Design (US-29).

---

## Lo nuevo en v6.11

**v6.11.0 — "Self Update"** la extensión VSCode ahora detecta una versión más nueva del engine al arrancar y ofrece actualizar — antes solo comparaba la versión instalada contra el disco, nunca el remoto:

- **Chequeo de versión remota al arrancar** — `git fetch` + leer `origin/main:ENGINE_VERSION.yaml`, comparación semver numérica (`6.10.2 > 6.9.4`). Sin red / sin git → se omite en silencio, la activación no se bloquea.
- **Diálogo accionable X→Y** — modal `Update now` / `View changes` / `Later`; "Later" silencia esa versión durante la sesión, una más nueva sí vuelve a preguntar.
- **Upgrade garantizado** — `pull --ff-only` y luego **verifica** releyendo la versión en disco: un pull que no movió la versión se reporta como error, nunca como éxito silencioso.
- **Camino de divergencia con backup** — un clon managed divergido (el caso del developer del engine) ofrece `reset --hard` con backup `git branch` previo y confirmación modal; un clon de usuario nunca se resetea, solo se avisa.

100% backwards-compatible. `extension.ts` intacto; la feature solo *ofrece* el upgrade, nunca lo aplica sin consentimiento (US-14, PR #125).

**v6.11.1 — "Living Funnel"** cierra el funnel site↔engine: el engine publica su estado vivo y su inventario de capacidades (13 agentes, 120 tools, 25 skills) al site en cada `/release`, y la extensión VSCode emite el evento de activación que cierra el funnel anónimo — `page_view→cta_click→install_intent→activation` como una conversión correlada y sin PII (US-16/US-20/US-26).

---

## Lo nuevo en v6.10

**v6.10.0 — "UC Lifecycle Metrics"** dos capacidades nuevas: métricas honestas de lead time por UC computadas en la BD, y espejo dual-backend hacia Native:

- **Captura de lifecycle por triggers** — toda transición de `use_cases.state` (sea cual sea el escritor) queda registrada transaccionalmente en `uc_state_transitions`, con `started_at`/`completed_at` mantenidos en la fila. El inicio que antes no se registraba y el fin best-effort que podía perderse quedan blindados.
- **KPIs en la BD, engine fino** — `v_lifecycle_kpis` (lead time p50/p90 solo sobre UCs medibles, `coverage_pct` como KPI de honestidad, imports excluidos por construcción y visibles), `v_active_time_estimate` (tiempo activo estimado por clustering de sesiones), rol read-only para el panel y tool `get_project_kpis`.
- **Backfill histórico preparado, no ejecutado** — `fn_backfill_lifecycle` (dry-run default) con rollback exacto; se activará por proyecto tras calibrar estimadores con datos reales.
- **Dual-backend espejo Native (US-11)** — un primario Trello/Plane/FreeForm intocable puede reportar a la vez a un espejo Native best-effort que jamás degrada al primario (`enable_mirror`/`disable_mirror` con backfill idempotente).

100% backwards-compatible. Las migraciones de producción (`20260611000012..16`) se aplican vía Supabase ledger en el despliegue.

**v6.10.1 — "Reentrant Reserve"** hotfix: `reserve_uc` reentrante dentro de una transacción usa `INSERT ... ON CONFLICT DO NOTHING` en vez de capturar `UniqueViolationError`, arreglando el `current transaction is aborted` de `start_uc` tras `reserve_uc` del mismo developer (UC-1208, PR #118).

**v6.10.2 — "Mirror Bootstrap"** hotfix: `enable_mirror` auto-inicializa `projects.json` y auto-siembra la entrada del proyecto desde el primario cuando el registry nunca se materializó en el host MCP cloud — cierra el `CONFIG_FAILED`/`failing_place=registry` al activar el espejo Native sobre el cliente potencial_digital_2026; el primario en disco nunca se sobrescribe y la rollback transaccional borra el `projects.json` recién creado (US-11/UC-1104, PR #123).

---

## Lo nuevo en v6.9

**v6.9.0 — "Self-Provisioning"** la extensión de VS Code se aprovisiona el engine ella misma, sin clone manual:

- **Auto-clone del engine público** — cuando la extensión no encuentra el engine en disco, clona `github.com/EmbedBuild/specbox-engine` a una carpeta gestionada (`~/.specbox/specbox-engine`) automáticamente (notifica, no pregunta), antes de recurrir a pedirte la carpeta a mano.
- **Auto-pull del clon gestionado** — el update flow mantiene ese clon al día con `git pull --ff-only`. Un clon propio tuyo en otra ruta **nunca** se toca.
- **Onboarding sin "clona primero"** — el walkthrough y el README ya no te piden `git clone` como paso previo de la extensión.

100% backwards-compatible. El auto-clone es el último recurso: config/workspace/rutas comunes ganan, y un clone fallido degrada al diálogo de selección manual.

**v6.9.1 — "Atomic Switch"** cambiar de backend (incl. hacia/desde Cloud/Native) pasa a ser **una sola operación atómica todo-o-nada**: el nuevo `switch_project_backend` migra datos + asocia identidad + conmuta la config + reporta lo descartado en una llamada con rollback total. Cierra además el path-bug de MCP remoto: el source se lee del cliente (content-passing), nunca del filesystem del servidor.

**v6.9.2 — "Batch Ingest"** subir un proyecto freeform real (133 KB / cientos de ítems) a Cloud/Native ya funciona end-to-end: la migración cruza por **lotes verificables** (`start → append × N → commit`, SHA-256 por chunk) que el servidor reensambla y escribe en **una transacción atómica** (rollback total ante fallo). Cierra el gap de transporte de v6.9.1 — el `items.json` ya no tiene que caber en un único parámetro de tool.

**v6.9.3 — "Tenant Provisioning"** subir un proyecto a Cloud/Native **de cero** ya funciona: la migración **auto-aprovisiona** el tenant + tu membresía como `project_admin` server-side antes del gate (rompe el huevo-gallina "no eres miembro de un proyecto que aún no existe"), y engine y panel acuerdan un único formato de `project_id` (`owner/repo` canónico + slug derivado para URLs). Cierra los 2 gaps de v6.9.2.

**v6.9.4 — "Orphan Tenant Recovery"** cierra el bug que aún rompía la migración de cero real: `setup_board` creaba la fila del proyecto **sin membresía** (tenant huérfano), y eso **desactivaba** la auto-provisión de v6.9.3 → `FORBIDDEN` sobre una BD vacía. Doble defensa: `setup_board` native ahora aprovisiona tenant + membresía de forma atómica (nunca deja 0 miembros), y la auto-provisión **adopta** un tenant huérfano (0 miembros) mientras sigue protegiendo los tenants con dueño (AC-13). El E2E ahora parte del **estado sucio real** (huérfano primero), no de una BD virgen. 100% backwards-compatible.

**v6.9.5 — "Tenant-Scoped Keys"** cierra el último bloqueante de la migración a Cloud/Native: el ingest colisionaba en `user_stories_pkey` porque la PK era el id lógico (`US-01`) **sin** namespacing por proyecto — dos proyectos no podían compartir un `US-01` en el mismo Postgres. La PK de US/UC/AC pasa a **compuesta `(project_id, id)`** (migración 0009, idempotente). Además, `/switch-backend` ahora entiende el **dialecto FreeForm "exploded"** (`index.json` anidado + AC en checkboxes `.md`) vía un normalizador puro a `items.json` + un **pre-flight de formato** y un **gate de prerequisitos native** que sacan los fallos al paso 0 en vez de a mitad de la migración. Tests stale realineados a los contratos UC-660/UC-706. 100% backwards-compatible.

---

## Lo nuevo en v6.8

**v6.8.0 — "Connectivity UX"** hace que SpecBox funcione de verdad con el MCP server en remoto: el server nunca toca un filesystem ajeno y el estado del cliente fluye por content-passing:

- **FreeForm operativo end-to-end** — las 7 tools de mutación + un bridge Node (`readTrackingBundle`/`writeTrackingBundle`) leen/escriben `doc/tracking` del cliente vía content-passing. Cierra la regresión #82.
- **`/audit` operativo en remoto** — los 8 analyzers ISO/IEC 25010 portados a Node client-side escanean el FS del cliente, no el del VPS.
- **Updater pedagógico de la extensión** — detecta config obsoleta tras un update, migra el transporte sola (con backup + revert) y explica qué cambió.
- **Drift gate consciente de las decisiones canónicas** — valida contra `app_spec.md`, la causa-raíz que dejó pasar #82.

100% backwards-compatible. Cierra una clase de fallo silencioso en MCP remoto.

---

## Lo nuevo en v6.7

**v6.7.0 — "Zero-Friction Onboarding"** quita toda la fricción de instalar la extensión VSCode y hace que avise con claridad cuando le falta algo:

- **Onboarding cero-Python** — el MCP server se consume solo por el endpoint hospedado gratuito (se eliminó el modo Local que pedía Python). Engram se instala como binario nativo vía Homebrew, no por pip. Health check, walkthrough y README ya no mencionan Python.
- **Gate de prerequisitos** — al arrancar, si falta un requisito crítico (Claude Code, Engram, Node o los servidores MCP) la extensión avisa de forma clara y no bloqueante que SpecBox puede no funcionar correctamente, con acciones de un clic. Silencio cuando todo está listo.
- **Comando "SpecBox: Check Prerequisites"** — re-evalúa el entorno a demanda desde la paleta.

100% backwards-compatible. Decisión: sin fallback air-gapped (el MCP remoto es gratuito); el aviso avisa, no impide.

---

## Lo nuevo en v6.0

**v6.0.2 — "Smoke Test Followups"** cierra los 3 issues abiertos descubiertos en el smoke test de v6.0.1 (#60, #61, #62) y elimina el último hardcodeo de versión runtime que arrastraba el server desde v5.29:

- **`submit_quality_audit` autogenera `audit_id`** si el cliente no lo pasa (cliente puede seguir pasando el suyo si necesita idempotencia).
- **`run_quality_audit` deprecation hace `raise`** → MCP envelope con `isError=true`. Clientes que solo inspeccionan el envelope detectan la deprecación correctamente.
- **`validate_discovery_completeness`** acepta las 4 resoluciones canónicas de drift (`feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`) y expone nuevo campo `drift.kind` para futuros gates estrictos.
- **`server/server.py`** ya no hardcodea la versión — la lee de `ENGINE_VERSION.yaml` al cargar el módulo. Bug latente `submit_quality_audit.fn(...)` eliminado de paso. `fastmcp 3.1.0 → 3.3.1` con pin `>=3.3.1,<4.0.0`.

100% backwards-compatible. Suite `1243 passed / 71 skipped / 0 failed`.

---

**v6.0.1 — "MCP Path Contract"** hotfix arquitectural que migra 17 tools cat A en `server/tools/` a un patrón de **content-passing universal**: ninguna tool registrada con `@mcp.tool` resuelve `Path(project_path).resolve()` para acceder al filesystem del cliente. El cliente lee los archivos localmente con `Read`, pasa el contenido como string, y escribe lo que la tool devuelva. Resuelve el bug crítico de MCP remoto donde las tools devolvían datos del filesystem del VPS, no del cliente. Skills actualizadas (`/discovery`, `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check`) + nuevo helper cliente `.claude/hooks/lib/mcp-client-io.mjs`.

---

**v6.0.0 — "Discovery Foundations"** introduce un módulo de **Product Discovery** permanente integrado en el pipeline canónico (`/discovery → /prd → /plan → /implement`) + el tercer documento canónico `doc/app/app_market.md` (ICPs primarios + no-ICPs + JTBDs globales + NSM + posicionamiento) + la **fundación arquitectural multi-doc** (`server/app_docs/registry.py`) que sostiene la extensión a N documentos canónicos en v6.x+. Proyectos v5.x reciben `app_market.md` como plantilla `template-pristine` vía `upgrade_project` sin modificar archivos existentes.

---

## Lo nuevo en v5.34

**v5.34.0 — "Native Collaboration"** estrena el **Native Backend**: un cuarto backend del `SpecBackend` ABC (junto a Trello / Plane / FreeForm), respaldado por una instancia gestionada de Supabase Postgres, pensado para equipos donde varios developers comparten un único board source-of-truth.

- **Backend Postgres/Supabase multi-tenant** — los 26 métodos del ABC sobre un pool asyncpg, con **concurrencia optimista** (`expected_version`) para que dos developers no pisen el mismo trabajo.
- **Identidad de developer + autorización** — resolución token→developer, Frontier 1 authz (UNAUTHENTICATED / FORBIDDEN). Tools `whoami`, `claim_uc`, `release_uc`, `register_native_branch` (la emisión / revoke de tokens vive en el SpecBox Control Panel desde v5.34.1).
- **Claims de UC + registro de ramas** — un developer reserva un UC y registra su rama feature.
- **Seguridad de credenciales (Frontier 2)** — el DSN vive solo en `SPECBOX_NATIVE_DSN`, nunca en disco ni en `meta.json`.

Opt-in y aditivo: si no configuras `backend_type='native'`, todo se comporta como antes. 100% backwards-compatible — Trello / Plane / FreeForm intactos. Validado en producción contra Supabase real (50 tests verdes).

**v5.34.1** añade dos piezas grandes sobre la misma línea Native, sin tocar el comportamiento de los otros 3 backends:

- **Cambio guiado de backend N×N (`/switch-backend`)** — un proyecto puede migrar de cualquiera de los 4 backends a cualquier otro (12 pares) sin perder US/UC/AC, estado, comments ni evidencia. Migración aditiva (el origen permanece intacto), preview obligatorio, switch transaccional de los 3 lugares de verdad (registry, `app_spec.md`, `settings.local.json`) con rollback, y oferta opt-in de `regenerate_evidence` para refrescar acceptance tras la migración.
- **Native blindado contra mutaciones de identidades revocadas** — cada uno de los 9 mutadores del NativeBackend re-valida identidad + membresía contra `mcp_tokens` con cache TTL hardcoded 30s. Ventana de exposición tras revoke ≤ 30s (antes: horas). `delete_acceptance_criterion` y `archive_item` dejan rastro forense en `audit_log`. Modelo de identidad rediseñado limpio (`developers` + `github_identities` N:1 + `mcp_tokens` revocables) listo para el panel web — el CRUD de equipo deja de vivir en el MCP.

---

## Lo nuevo en v5.33

**v5.33.0 — "FreeForm Path Safety"** convierte el BLOCKER de v5.29 (FreeForm + MCP remoto escribiendo en el VPS) en un bug mecánicamente imposible. v5.29 ya lo resolvía a nivel `/app-init` y server-side; v5.33 añade dos capas más para cubrir clientes que no pasan por la skill:

- **Hook universal `freeform-path-guard.mjs`** — PreToolUse intercepta `set_auth_token` y `onboard_project`. Si el path es relativo (o `doc/tracking` queda implícito), lo reescribe al absoluto del repo via `git rev-parse --show-toplevel` antes de que la llamada salga al MCP. Auto-rewrite silencioso vía `hookSpecificOutput.updatedInput`. Audit trail en `.quality/logs/freeform-path-rewrites.jsonl`.
- **Tool MCP `detect_local_root_path()`** — read-only handshake que declara el contrato (requires_absolute_path, client_resolution_recipe). Sirve a `/app-init`, claude.ai mobile e integraciones externas como documentación ejecutable.
- **`/app-init` Paso 2.3 reforzado** — 3-step handshake: handshake con la tool del contrato, resolución explícita desde PROJECT_ROOT, pasa absoluto a `set_auth_token`. El hook queda como red de seguridad para clientes que no usan la skill.

3 capas aditivas e independientes. Remover cualquiera no desbloquea el bug mientras las otras estén en pie. 100% backwards-compatible — clientes pre-v5.33 sin el hook siguen hitting el server-side guard de v5.29.

---

## Lo nuevo en v5.32

**v5.32.0 — "Implement Task Isolation"** cierra el out-of-scope explícito de v5.30: el SKILL.md de `/implement` ya documentaba la delegación a Tasks aisladas, pero el contrato no estaba mecánicamente forzado. v5.32 añade los 5 guardrails que faltaban — sin rediseñar la arquitectura — y los cablea de forma observable:

- **`execution_context.json`** persistido por feature (branch / stack / paths). Cada Task lo lee del disco en lugar de recibir esos valores en el prompt → fixea la causa raíz del context exhaustion en UCs grandes.
- **`context-budget-guard.mjs`** PreToolUse(Task) — estima tokens, warn @ 16k (default), strict como settings flip.
- **`file-ownership-guard.mjs`** PreToolUse(Write/Edit) — valida la ruta contra el ownership del agente activo. Suspicious paths (`..`, `/abs`) siempre BLOCKED.
- **`phase_outputs.jsonl`** — cada Task escribe su delta estructurado al cierre. Spec-Code Sync deja de depender de `git diff` vivo desde el orquestador.
- **Telemetría local** en `.quality/task_isolation.json` con `{enabled, tasks_run_total, tasks_failed_*}` (consumible por scripts ad-hoc o specbox_cloud).

100% backwards-compatible. Modos `warn` por defecto durante la migración.

**v5.32.1** convierte la regla "README + CHANGELOG en cada bump" en un guardrail mecánico: el skill `/release` ahora bumpea ambos archivos como pasos obligatorios y un nuevo validador `version-consistency-check.mjs` aborta la release si cualquiera de los 5 archivos de versión queda desincronizado.

---

## Lo nuevo en v5.31

**v5.31.0 — "Stitch Autopilot"** alinea la integración de Google Stitch con sus best practices oficiales y elimina los bloqueadores recurrentes de autopilot al generar diseños:

- **DESIGN.md canónico** ([formato oficial Google](https://github.com/google-labs-code/design.md)) generado automáticamente desde Brand Kit + VEG. Resuelve el drift visual entre pantallas en raíz.
- **Pipeline v2 con fallback chain** (`edit_baseline → variants_refine → regenerate`) — los timeouts y errores transitorios ya no rompen autopilot.
- **Validator de prompts en 4 capas** (Context / Components / Style con hex codes / Platform) — primera generación más cerca de la marca, menos iteración.
- **Batched build_site** para planes con >5 pantallas + pasada final de tema unificado.
- **Quota tracking** (350 Standard + 200 Experimental) con warnings ≥80% y hook bloqueante a 100% (Flash safety net opt-in).

**Modelo default sigue siendo `GEMINI_3_PRO`**. Calidad-first. Flash queda solo como red de seguridad opt-in.

**v5.31.1** activa todo lo anterior en `/plan` Paso 6 (antes seguía usando v1 directo). Migración transparente — sin cambios de settings necesarios.

---

## ¿Por qué v5.29.0?

**Problema**: a medida que llevas más proyectos en paralelo, SpecBox te interrumpe demasiado. Cada decisión, cada confirmación, cada pregunta — multiplicado por proyectos abiertos = carga cognitiva imposible.

**v5.29.0** introduce un sistema de **decisiones con autonomía auditable**: el engine se queda decidiendo lo cosmético y lo repetitivo por ti, mientras te garantiza que nunca toca lo crítico (acciones destructivas, push a main, gastos sobre presupuesto).

**Resultado medido**: las interrupciones por feature pasan de ≥17 (baseline v5.28) a ≤8 con el preset por defecto `equilibrado`.

---

## Lo nuevo en una imagen

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tu proyecto en v5.29                         │
│                                                                 │
│   doc/app/app_prd.md      ← Producto: visión, audiencia, scope │
│   doc/app/app_spec.md     ← Técnico: stack, brand, autopilot   │
│              │                                                  │
│              ▼  /prd, /plan, /visual-setup leen esto antes      │
│              │  de preguntar nada                               │
│                                                                 │
│   Autopilot: [equilibrado]  ─── reduce preguntas a la mitad    │
│   Hooks: pre-commit + drift detection                           │
│   Sync: doc/app/ siempre alineado con la realidad              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

> **¿Usas la extensión de VS Code?** No necesitas clonar nada a mano: cuando la
> extensión no encuentra el engine, lo clona por ti automáticamente desde el
> repo público a una carpeta gestionada (`~/.specbox/specbox-engine`) y la
> mantiene al día. Los pasos de abajo son para la instalación manual del engine
> por CLI.

```bash
# Instalar el engine globalmente (instalación manual por CLI)
git clone <repo-url> ~/specbox-engine
cd ~/specbox-engine
./install.sh

# En tu proyecto
cd /ruta/a/mi-proyecto
/app-init                 # crea doc/app/ + configura autopilot=equilibrado
/prd "tu primera feature" # hereda audiencia y stack desde app_prd.md
/plan US-01
/implement
```

Eso es todo. Las skills se auto-descubren cuando son relevantes; los hooks corren solos.

---

## Arrancar un proyecto con la extensión de VS Code

Si usas la **extensión de VS Code** (Marketplace), el arranque no tiene un botón
"Init" mágico: la extensión **instala y configura** el engine, y el *onboarding
del proyecto* (crear el board, elegir backend) sigue ocurriendo en el chat de
Claude Code con las skills/tools. Esto es lo que hace cada acción de la UI por
debajo:

| Acción en la extensión (Command Palette / sidebar) | Comando interno | Qué dispara por debajo |
|---|---|---|
| **SpecBox: Onboard Project** | `specbox.onboard` | Wizard de 5 pasos: prerequisitos → localizar/clonar engine (`resolveEnginePath`, auto-clone desde el repo público si falta) → instalar skills+hooks (`runFullInstall`) → **Configure MCP** → health check. **No crea el board**: deja el entorno listo para que tú corras las skills. |
| **SpecBox: Install Engine** | `specbox.install` | Copia skills a `~/.claude/skills/` y hooks a `~/.claude/hooks/` (equivale a `./install.sh`). |
| **SpecBox: Configure MCP Servers** | `specbox.configureMcp` | Escribe la config del MCP remoto de SpecBox (`npx mcp-remote …`) + Engram en el `settings.json` de Claude Code. |
| **SpecBox: Sign in with GitHub** | `specbox.signIn` | OAuth de GitHub (loopback) → provisiona un `mcp_token` para el **backend native** (Cloud) y lo guarda en el SecretStorage de VS Code. Es el paso que habilita el board native compartido. |
| **SpecBox: Check Prerequisites** | `specbox.checkPrerequisites` | Re-evalúa el entorno (Claude Code, Engram, Node, MCPs) y avisa si falta algo. |

Tras `Onboard Project` + `Sign in with GitHub`, el **arranque real del proyecto**
(crear/poblar el board) se hace en el chat con las tools del MCP:

```text
onboard_project(...)   # registra el proyecto (backend native por defecto desde v6.3.0)
setup_board(...)       # crea el tenant native + tu membresía como project_admin
/app-init              # crea los documentos canónicos doc/app/ (ver nota abajo)
/prd → /plan → /implement
```

> **Nota — "app init" ≠ ningún botón.** Si alguien dice *"app init"*, se refiere a
> la **skill `/app-init`** (crea/refresca `doc/app/app_prd.md` y `app_spec.md` —
> v5.29). **No** es lo mismo que **`onboard_project`** (tool MCP que registra el
> proyecto y autodetecta el stack) ni que **`/quickstart`** (tutorial interactivo
> de onboarding). Los tres son cosas distintas; la extensión no renombra ninguno.

---

## ¿Cómo funciona?

### 1. Documentos canónicos del proyecto

Cuando ejecutas `/app-init`, SpecBox crea dos documentos vivos:

- **`doc/app/app_prd.md`** — Producto: visión, audiencia, JTBDs, perímetro, métricas, roadmap.
- **`doc/app/app_spec.md`** — Técnico: stack, backend, brand, convenciones, autopilot.

Cada documento tiene **zonas tipadas** que el engine respeta:

- 🔒 **`manual`** — solo tú las editas. El engine las lee como input.
- 🤖 **`auto`** — solo el engine las reescribe (tras eventos como `complete_uc`).
- 🤝 **`hybrid`** — append-only, ambos contribuyen con marcadores explícitos.

A partir de aquí, `/prd`, `/plan` y `/visual-setup` consultan estos documentos en su Paso 0 y **dejan de repreguntarte** la audiencia, el stack, el modo VEG, el backend de tracking, etc.

### 2. Autopilot

Cada gate del engine se etiqueta con un `decision_key`. El nivel de autopilot decide qué se auto-confirma y qué se pregunta:

| Nivel | A quién pregunta | Cuándo usarlo |
|-------|------------------|---------------|
| `low` | Todo (= v5.28) | Proyecto con muchas decisiones críticas todavía abiertas |
| `conservador` | Todo menos cosmético | Quieres control visual fino |
| **`equilibrado`** ← default | Solo arquitectura, presupuesto, ambigüedad real | Caso por defecto |
| `agresivo` | Solo destructivo y AC objetivamente malos | Tras 1-2 semanas validando equilibrado |

**Reglas inviolables** que ningún nivel ni override puede saltar:

- ❌ Acciones destructivas (`reset --hard`, force-push, etc.).
- ❌ Push directo a main.
- ❌ Coste de imágenes por encima del presupuesto declarado.

Toda auto-decisión se registra en `.quality/autopilot_decisions.jsonl` (auditable, revertible).

### 3. Sync enforcement (Capa 5)

Sin enforcement, los documentos canónicos se convierten en mentira documentada en 2-3 sprints. Por eso v5.29 incluye:

- **Hook pre-commit** que detecta drift entre `app_*.md` y la realidad del proyecto.
- **Skill `/app-sync`** para reconciliar (4 modos: check / repair / review / rebuild).
- **Drift detector multi-fuente** que pilla cosas que el hook por sí solo no ve (lockfiles nuevos, brand kit roto, roadmap mintiendo, canonicals sin documentar).

En v5.29.0 está en **modo warning**: avisa pero no bloquea. Cuando hayas validado que los warnings son siempre accionables (1-2 semanas típicamente), pones `specbox.app_docs_sync.block_on_drift=true` y se vuelve bloqueante.

---

## Pipeline de desarrollo

```
/app-init       (una vez por proyecto)
    ↓
/prd            ← captura feature, hereda audiencia desde app_prd.md
    ↓
/visual-setup   ← brand kit + VEG + Stitch DS, hereda arquetipo
    ↓
/plan US-XX     ← plan técnico por UC + diseños Stitch
    ↓
/implement      ← fases + AG-08 calidad + AG-09 acceptance + PR auto
    ↓
/feedback       ← testing manual del usuario, puede invalidar verdict
    ↓
merge secuencial → siguiente UC
```

Cada paso del pipeline tiene su skill, su hook bloqueante, y su evidencia auditable.

---

## Skills disponibles

23 skills auto-descubribles. Las que más vas a usar:

| Skill | Para qué |
|-------|----------|
| `/app-init` ← v5.29 | Crea/refresca documentos canónicos del proyecto |
| `/app-sync` ← v5.29 | Reconcilia drift entre canónicos y realidad |
| `/queue review` ← v5.29 | Resuelve decisiones diferidas en batch |
| `/prd` | Genera PRD spec-driven con quality gate |
| `/visual-setup` | Brand kit + Stitch + VEG |
| `/plan` | Plan técnico por UC con designs |
| `/implement` | Auto-implementación con acceptance gates |
| `/feedback` | Captura bugs como evidencia + GitHub issue |
| `/release` | Audita, bumpa version, push |

Skills de billing (Stripe): `/stripe-connect`, `/stripe-standard`, `/stripe-switch-account`.

Skills de auditoría: `/audit` (ISO 25010), `/compliance`, `/quality-gate`, `/check-designs`, `/manual-test`.

Skills de exploración: `/explore`, `/adapt-ui`, `/optimize-agents`, `/quickstart`, `/remote`.

---

## Backends de tracking

| Backend | Cuándo |
|---------|--------|
| **`freeform`** ← default v5.29 | Proyectos personales, prototipos, sin reporting externo. Datos en `doc/tracking/` (JSON + Markdown auto-generado). |
| `trello` | Cliente externo necesita ver progreso. |
| `plane` | Equipo distribuido, multi-equipo. Self-hosted o cloud. |

Auto-discovery: SpecBox detecta tu backend leyendo settings, filesystem, o app_spec.md sin preguntarte.

Migración bidireccional: Trello ↔ Plane (`migrate_project`), Trello/Plane → FreeForm (`migrate_to_freeform_tool`).

---

## Hooks que importan

23 hooks `.mjs` ejecutados automáticamente por Claude Code. Los **bloqueantes** son los que evitan que metas la pata:

- `quality-first-guard` — no escribir sin haber leído el archivo primero.
- `spec-guard` — no escribir código sin UC activo.
- `branch-guard` — no escribir en main.
- `commit-spec-guard` — no commitear en main, avisos sobre UC y checkpoint.
- `e2e-gate` — no commitear evidencia E2E sin `results.json` válido.
- `no-bypass-guard` — bloquea `--no-verify`, `push --force`, `reset --hard`.
- `design-gate` — no UI sin diseño Stitch primero.
- `pipeline-phase-guard` — no feature code antes de DB phase.
- `healing-budget-guard` — corta self-healing tras 8 intentos.
- `stripe-safety-guard` — bloquea anti-patterns Stripe (sk_live, webhook sin firma, etc.).
- `app-docs-sync-guard` ← v5.29 — detecta drift en docs canónicos (warning por defecto).

---

## Stacks soportados

| Stack | Versión | E2E |
|-------|---------|-----|
| Flutter | 3.38+ | Maestro (recomendado) o Patrol v4 (legacy) |
| React | 19.x | Playwright |
| Go | 1.23+ | testing + httptest + testcontainers-go |
| Python (FastAPI) | 3.12+ | pytest-bdd + httpx |
| Google Apps Script | V8 | jest-cucumber |

Servicios de infraestructura: Supabase, Neon, Stripe, Firebase, n8n, Stitch MCP.

MCPs propios en [`packages/`](packages/): `specbox-stripe-mcp` (setup-as-code Stripe), `specbox-supabase-mcp` (Edge Function secrets).

---

## Migración desde v5.28

Tooling automático que clasifica tu proyecto en uno de 10 estados conocidos:

```python
detect_v529_migration_case(project_path=".")  # te dice qué caso aplica
run_v529_migration(project_path=".", apply=False)  # dry-run / apply seguro
```

Casos sensibles que se difieren para revisión manual: feature en curso (caso 7), datos posiblemente en VPS (caso 3), `app_*.md` creados a mano (caso 9).

100% backwards-compatible. Sin `doc/app/`, sin sección `autopilot`, sin nada — el proyecto se comporta como v5.28.

---

## ¿Quieres saber más?

- 📖 **Plan completo de v5.29.0**: [doc/plans/v5.29.0_cognitive_load_reduction_plan.md](doc/plans/v5.29.0_cognitive_load_reduction_plan.md)
- 📋 **PRD del problema**: [doc/prds/cognitive_load_reduction_prd.md](doc/prds/cognitive_load_reduction_prd.md)
- 📜 **Histórico**: [CHANGELOG.md](CHANGELOG.md)
- 🛠️ **Reference técnico exhaustivo**: [CLAUDE.md](CLAUDE.md)

---

## Releases recientes

- **v5.29.0** ← actual — Cognitive Load Reduction.
- **v5.28.0** — Maestro Flutter E2E como runner recomendado para mobile.
- **v5.27.0** — `/stripe-standard` + `/stripe-switch-account`.
- **v5.26.0** — Paquete `specbox-supabase-mcp` para Edge Function secrets.
- **v5.25.0** — `/stripe-connect` para marketplaces.

---

## Configuración mínima

`.claude/settings.local.json`:

```json
{
  "specbox": {
    "backend_type": "freeform",
    "freeform_root_absolute": "/ruta/absoluta/al/proyecto/doc/tracking",
    "autopilot": {
      "level": "equilibrado",
      "image_budget_eur_per_feature": 5
    },
    "app_docs_sync": {
      "block_on_drift": false
    }
  }
}
```

---

## Licencia

[Indicar licencia del proyecto]

---

<a id="english-version"></a>

# SpecBox Engine — English version

> **Agentic programming with Claude Code, without trading quality for speed.**
> v 6.22.2 — "Mesura" (over v6.22.1 "Llave")
> [specbox.build/en](https://specbox.build/en/)

## What is this?

A system that turns Claude Code into a serious teammate:

- **Helps you go fast** without skipping traceability or quality.
- **Learns your project** and stops asking you what you already decided.
- **Blocks dangerous shortcuts** (push to main, vague AC, code without UC, unsafe paths).
- **Coexists with your flow**: spec-driven with FreeForm/Trello/Plane depending on the client.

> The LLM provides speed. SpecBox provides quality and traceability.

## What's new in v6.22

**v6.22.0 — "Cerrojo"** ("deadbolt") bolts what the hosted server left open to anyone who named a project, and brings the Stitch tools up to date with its API:

- **Your Stitch key lives only in your session** — the server no longer stores it on disk, and another session naming your project cannot use it. `/plan` and `/visual-setup` send it again in each session.
- **A project's state is touched only by who can see it** — on the hosted server, telemetry, activity and audit evidence require the project to be yours, and errors list only your projects.
- **The hosted server neither reads nor writes your disk** — tools that take a path on your machine answer before touching anything; use them with the local MCP. Switching backend returns the changes to your files for you to write.
- **A test keeps it from coming back** — it walks every registered tool and fails when a new one opens any of these holes.
- **Stitch, up to date** — calls in the current API shape, failures that arrive as errors, 6-minute waits without repeating a generation, `GEMINI_3_8_FLASH` by default, account design systems and shared projects.

With the hosted MCP one thing changes: the canonical documents, queue, decisions and implementation status tools answer with a notice instead of using the server's disk. With the local MCP nothing changes.

**v6.22.1 — "Llave"** ("key") brings those tools back to the hosted MCP: you send your files and get back what to write, without the server touching its disk. Also, the MCP reads from the board only what it needs and the extension asks who you are every 30 minutes instead of every minute.

**v6.22.2 — "Mesura"** ("restraint") makes the extension's changelog tab on the Marketplace say again what each version changes.

## What's new in v6.21

**v6.21.0 — "Gavilla"** ("sheaf") binds stories into epics, like ears of wheat in a sheaf:

- **Epics in the board** — above the story there is a single grouping, the epic, with a name, an objective and an order. Its state and progress are not written: they come from its stories, and without criteria it does not make up a 0 %.
- **The whole flow knows them** — six tools to create and query them; reads name the epic and the satellite of each story and use case; `/prd` asks which epic a feature belongs to and seeding creates it; `/implement EP-NN` works an epic from start to finish.
- **Verified is not accepted** — the board keeps a person's acceptance apart, voided by itself if the use case stops being done, and the public home counts how many closed use cases someone accepted.
- **A project is only read from inside** — board reads check membership just like writes, and opening a session makes nobody a member.
- **Milestones go away in 6.23.0** — they keep working for two more versions and warn in every answer; use epics.

100% backwards-compatible: without epics, the board and the autopilot answer as always.

## What's new in v6.20

**v6.20.0 — "Cableado"** ("wiring") makes the hooks SpecBox promises arrive connected:

- **Projects get every hook** — the template wires the seven the engine used and projects never received: resuming the session from the handoff, warning before reading huge files, the context budget and file ownership of `/implement` subagents, FreeForm paths, the discovery gate and the canonical-docs gate. None blocks by default.
- **The extension flags a broken hook** — the health check lists every hook a project configures and does not have on disk. A hook that does not start protects nothing.
- **`CLAUDE.md` names what exists** — skills, hooks and agents complete and checked on every PR; the `/audit` auditor becomes AG-11.

100% backwards-compatible: no new hook blocks by default and there are no migrations.

## What's new in v6.19

**v6.19.0 — "Escaparate"** ("shop window") makes what the engine shows in public match what it has:

- **A shop window with real receipts** — the [specbox.build](https://specbox.build/en/) home shows, live, a use case from our own board and the receipts of its criteria, from a public read-only view that never shows the detail nor the internal criteria.
- **Figures that add up** — the site counts the 192 tools the MCP lists (126 before), stops counting what was retired, keeps code names in the changelog, and its activity snapshot adds up.
- **Every AC event knows its use case** — the `audit_log` stores `uc_id` on every mark, edit, creation or deletion of a criterion.
- **One version of each migration** — `migration_twins.py` checks that `supabase/migrations` is an exact copy of `server/db/migrations`.
- **The hook says what it is** — the "read before you write" block no longer says SpecBox brings the speed: the LLM brings the speed; SpecBox, the control and the quality.

100% backwards-compatible: no board migrations.

## What's new in v6.18

**v6.18.0 — "Mudanza"** ("moving house") moves the hosted server to `mcp.specbox.build` and lets clients move by themselves:

- **The server answers at `mcp.specbox.build`** — and at its earlier name, `mcp-specbox-engine.jpsdeveloper.com`, which keeps working with no retirement date. `scripts/check-mcp-hosts.mjs` checks that both answer the same: every Monday on GitHub and in every release with this computer's token.
- **The extension and `specbox login` use the new name** — after updating, the extension rewrites the Claude Code entries that pointed at the earlier one (user scope and every project) and first saves a copy in `~/.specbox/backups/`, without any token.
- **Nobody loses the connection** — this computer's credential serves both names: the one saved under the earlier name keeps being used.
- **Everything under specbox.build** — the site lives at [specbox.build](https://specbox.build/en/), the contact is `hola@specbox.build`, and the security policy, the connection guides and the npm and Marketplace pages point there.

100% backwards-compatible: an installation that is not updated keeps working with the earlier name.

## What's new in v6.17

**v6.17.0 — "Evidencias"** ("receipts") makes every accepted acceptance criterion show its receipt:

- **Structured receipts** — `mark_ac` and `mark_ac_batch` accept, besides the usual free text, a receipt `{type: test|screenshot|diff|url|pr, label, link?, detail?}`. The Native board stores it with the AC, together with who marked it and when; a malformed receipt marks nothing.
- **`get_uc` shows the receipts** — per AC, its evidence with type, label, link, who and when, and who accepted it. On Trello, Plane and FreeForm they are rebuilt from the comments with the author unknown: never invented.
- **What came before has a receipt too** — migration 0028 turns the `AC-XX: PASSED — …` comments into receipts with their date.
- **The native backend tests run on every PR** against a real Postgres and the full suite no longer hangs; the CLI waits for npm even when a version stays "staged", and the dev Postgres starts on the port you choose (`SPECBOX_NATIVE_PG_PORT`).

100% backwards-compatible: free-text evidence is stored and commented exactly as before.

**v6.17.1 — "EngineFirst"** the engine creates projects without the panel: when there is no organization to assign, `setup_board` creates the project without one instead of failing.

**v6.16.0 — "Goma"** ("eraser") removes what was created by mistake and fixes what went wrong when closing "Tinta":

- **Really delete a UC created by mistake** — `delete_uc` with `purge=true` deletes the UC, its ACs, its state transitions, its reservation and its branch record in one transaction and keeps a copy in the audit log. Only when the UC never had work (backlog or archived, no AC done, no evidence, no reservation); otherwise it archives it as always and says why.
- **The extension speaks Spanish end to end** — with VS Code in Spanish, no notification, button or install step is left in English; `npm test` fails when a text is left untranslated.
- **The release security check** no longer takes design tokens for credentials.

100% backwards-compatible: without `purge`, `delete_uc` keeps archiving; on Trello and Plane, `purge` archives.

**v6.15.0 — "Tinta"** makes the engine and the extension speak the SpecBox ecosystem's single design system: one source of colours, type and components for the panel, the portal, the site and the extension.

- **Design tools read the system** — `generate_design_md_tool` takes the system tokens (`design-system.tokens.json`) as the only source and reports which values fall outside; Stitch and Claude Design output is marked as a candidate and `/plan` writes each plan's design source.
- **The design gate blocks what leaves the system** — hand-written colours, foreign fonts, weights above the maximum and gradients, with file and line; in autopilot it blocks before review or opening the PR.
- **The extension speaks the same visual language** — the sign-in return page and the health panel use the system tokens (dark by default and following the VS Code theme) and named Lucide icons; the status bar always shows the state word and, when everything is fine, `[x] SpecBox vX · ready`.
- **The `specbox` CLI publishes itself to npm** on every tag (trusted publishing).

100% backwards-compatible: a project without system tokens keeps its Brand Kit and gets a notice with a link to the guide.

---

## What's new in v6.14

**v6.14.0 — "Front Door"** makes sure nobody talks to the remote MCP without identifying themselves, and that connecting never means copying tokens.

- **Transport authentication** — the remote server checks the token on every HTTP request; the operator decides when to require it (`off`, `grace` with a notice and a deadline, `enforce`).
- **One token per device, with expiry** — signing in again from the same computer replaces the token instead of adding one; it expires after 90 days and renews itself.
- **`npx specbox login`** — a one-time code confirmed in the panel with GitHub; the token goes into the system secure store (Keychain, Secret Service, DPAPI) and Claude Code sends it through a headers helper.
- **The VS Code extension does the same on sign-in** — and, when it updates, connects the computer with no manual steps. The status bar shows the account, the device and when the token expires.
- **Per-user isolation** — remote FreeForm works only with the content the client sends, the project registry only shows the caller's projects, every tool call lands in an access log and the board database is readable only by those allowed.

100% backwards-compatible: transport authentication starts in `off` and existing tokens keep working.

**v6.14.1 — "Forward Only"** — the extension never downgrades when it updates, tokens issued before expiry existed expire on 2026-12-28, `SECURITY.md` explains how to report a security problem, and the release now requires every version with security changes to say what it prevents.

**v6.14.2 — "Idle Watch"** — a token unused for 60 days is revoked by itself (the clock starts on 2026-09-29, so the first one falls on 2026-11-28), nobody holds more than five devices (the sixth does not get in until another is disconnected, and the panel shows which) and the extension keeps the computer connected before any start-up notice that might sit waiting.

---

## What's new in v6.13

**v6.13.0 — "Tenant Guard"** brings together two stories that meet at the same place: what the client is shown, and who may change it.

- **Membership is validated against the project being written** — not the session's. Closes a cross-tenant write in the native backend mutators. The guard lives in a single place, so mutator number fourteen inherits it without anyone remembering to add it.
- **Acceptance criteria as a deliverable** — the `internal` flag hides what the client shouldn't see, while it **still counts** towards progress: hiding does not discount.
- **The testability gate goes from 30.54% to 98.17%** — it used to approve vague statements ("must be fast") and reject test-verified ones.
- **Exposure check** — warns about criteria quoting credentials or internal paths. Warns, never blocks.

100% backwards-compatible. `internal` defaults to `false`: no existing criterion changes visibility.

---

## What's new in v6.12

**v6.12.0 — "Claude Design Native"** adds **Claude Design** as a second VEG visual provider, aligning the design platform with the execution platform (SpecBox is agentic for Claude):

- **Per-project visual provider** — `veg.providers` ∈ `["stitch"]`, `["claude_design"]`, or both. Claude Design designs with the **real compiled components** of the design-system (1:1 to code), not text mockups.
- **Preferred when a design-system is compiled** — Stitch stays the fallback for the early phase without code. A project without the new config behaves **exactly like today** (Stitch-only).
- **No tokens** — uses the machine's claude.ai login via the `DesignSync` tool; consumption is billed to the **logged-in user's subscription**. No login → `pending`.
- **Topology-aware anchoring** — in multirepo the design-system lives once in the **orchestrator** (UI satellites consume it); in monorepo, in the repo. Gate detects `package.json` + `dist/`/Storybook.
- **5 `claude_design_*` MCP tools** + `/visual-setup` and `/plan` integration + an idempotent sync engine that delegates to `/design-sync`.

100% backwards-compatible. Stitch remains the default; there is no programmatic delete of Claude Design projects (US-29).

---

## What's new in v6.11

**v6.11.0 — "Self Update"** the VSCode extension now detects a newer engine version on start-up and offers to update — it used to only compare the installed version against the on-disk one, never the remote:

- **Remote version check on start-up** — `git fetch` + read `origin/main:ENGINE_VERSION.yaml`, numeric semver compare (`6.10.2 > 6.9.4`). No network / no git → skipped silently, activation never blocks.
- **Actionable X→Y dialog** — `Update now` / `View changes` / `Later` modal; "Later" postpones that version for the session, a newer one re-prompts.
- **Guaranteed upgrade** — `pull --ff-only` then **verifies** by re-reading the on-disk version: a pull that did not move the version is surfaced as an error, never a silent success.
- **Diverged path with backup** — a diverged managed clone (the engine developer's case) offers `reset --hard` with a `git branch` backup first and a modal confirmation; a user clone is never reset, only warned.

100% backwards-compatible. `extension.ts` untouched; the feature only *offers* the upgrade, never applies it without consent (US-14, PR #125).

**v6.11.1 — "Living Funnel"** closes the site↔engine funnel: the engine publishes its live state and capability inventory (13 agents, 120 tools, 25 skills) to the site on every `/release`, and the VSCode extension emits the activation event that closes the anonymous funnel — `page_view→cta_click→install_intent→activation` as one correlated, PII-free conversion (US-16/US-20/US-26).

## What's new in v6.10

**v6.10.0 — "UC Lifecycle Metrics"** two new capabilities: honest per-UC lead-time metrics computed in the database, and a dual-backend Native mirror:

- **Trigger-based lifecycle capture** — every `use_cases.state` transition (whatever the writer) is recorded transactionally in `uc_state_transitions`, with `started_at`/`completed_at` maintained on the row. The start that was never recorded and the best-effort completion that could be silently lost are now bulletproof.
- **KPIs in the DB, thin engine** — `v_lifecycle_kpis` (lead time p50/p90 over measurable UCs only, `coverage_pct` as the honesty KPI, imports excluded by construction yet visible), `v_active_time_estimate` (session-clustering active-time estimate), a read-only role for the panel and the `get_project_kpis` tool.
- **Historical backfill prepared, not executed** — `fn_backfill_lifecycle` (dry-run default) with exact rollback; activated per project after calibrating estimators against real trigger data.
- **Dual-backend Native mirror (US-11)** — an untouchable Trello/Plane/FreeForm primary can simultaneously report to a best-effort Native mirror that never degrades the primary (`enable_mirror`/`disable_mirror` with idempotent backfill).

100% backwards-compatible. Production migrations (`20260611000012..16`) apply via the Supabase ledger at deploy time.

**v6.10.1 — "Reentrant Reserve"** hotfix: reentrant `reserve_uc` inside a transaction uses `INSERT ... ON CONFLICT DO NOTHING` instead of catching `UniqueViolationError`, fixing the `current transaction is aborted` error on `start_uc` after the same developer's `reserve_uc` (UC-1208, PR #118).

**v6.10.2 — "Mirror Bootstrap"** hotfix: `enable_mirror` auto-inits `projects.json` and auto-seeds the project entry from the primary when the registry was never materialised on the cloud MCP host — fixes the `CONFIG_FAILED`/`failing_place=registry` when enabling the Native mirror on the potencial_digital_2026 client; the on-disk primary is never overwritten and the transactional rollback deletes a just-created `projects.json` (US-11/UC-1104, PR #123).

---

## What's new in v6.9

**v6.9.0 — "Self-Provisioning"** the VS Code extension provisions the engine itself, no manual clone:

- **Auto-clone of the public engine** — when the extension can't find the engine on disk, it clones `github.com/EmbedBuild/specbox-engine` into a managed folder (`~/.specbox/specbox-engine`) automatically (notifies, doesn't ask), before falling back to asking you for the folder.
- **Auto-pull of the managed clone** — the update flow keeps that clone current with `git pull --ff-only`. A clone of your own in any other path is **never** touched.
- **Onboarding without "clone first"** — the walkthrough and README no longer ask you to `git clone` as a prerequisite of the extension.

100% backwards-compatible. Auto-clone is the last resort: config/workspace/common paths win, and a failed clone degrades to the manual folder picker.

**v6.9.1 — "Atomic Switch"** changing a project's backend (incl. to/from Cloud/Native) becomes **one all-or-nothing operation**: the new `switch_project_backend` migrates data + seeds identity + switches the config + reports what was discarded in a single call with full rollback. It also closes the remote-MCP path bug: the source is read from the client (content-passing), never the server filesystem.

**v6.9.2 — "Batch Ingest"** uploading a real freeform project (133 KB / hundreds of items) to Cloud/Native now works end-to-end: the migration crosses in **verifiable chunks** (`start → append × N → commit`, SHA-256 per chunk) that the server reassembles and writes in **one atomic transaction** (full rollback on failure). Closes the v6.9.1 transport gap — the `items.json` no longer has to fit in a single tool parameter.

**v6.9.3 — "Tenant Provisioning"** uploading a project to Cloud/Native **from scratch** now works: the migration **auto-provisions** the tenant + your membership as `project_admin` server-side before the gate (breaks the egg-chicken "you're not a member of a project that doesn't exist yet"), and engine and panel agree on a single `project_id` format (canonical `owner/repo` + a derived slug for URLs). Closes the two v6.9.2 gaps.

**v6.9.4 — "Orphan Tenant Recovery"** closes the bug that still broke real from-scratch migration: `setup_board` created the project row **without a membership** (orphan tenant), which **disabled** v6.9.3's auto-provision → `FORBIDDEN` on an empty DB. Double defense: native `setup_board` now provisions tenant + membership atomically (never leaves 0 members), and the auto-provision **adopts** an orphan tenant (0 members) while still protecting tenants that have owners (AC-13). The E2E now starts from the **real dirty state** (orphan first), not a virgin DB. 100% backwards-compatible.

**v6.9.5 — "Tenant-Scoped Keys"** closes the last Cloud/Native migration blocker: the ingest collided on `user_stories_pkey` because the PK was the logical id (`US-01`) **without** per-project namespacing — two projects couldn't share a `US-01` in the same Postgres. The US/UC/AC PK moves to **composite `(project_id, id)`** (migration 0009, idempotent). On top, `/switch-backend` now understands the **FreeForm "exploded" dialect** (nested `index.json` + AC as `.md` checkboxes) via a pure normalizer to `items.json` + a **format pre-flight** and a **native prerequisite gate** that surface failures at step 0 instead of mid-migration. Stale tests realigned to the UC-660/UC-706 contracts. 100% backwards-compatible.

---

## What's new in v6.8

**v6.8.0 — "Connectivity UX"** makes SpecBox truly work with the MCP server running remotely: the server never touches a foreign filesystem and client state flows via content-passing:

- **FreeForm operative end-to-end** — the 7 mutation tools + a Node bridge (`readTrackingBundle`/`writeTrackingBundle`) read/write the client's `doc/tracking` via content-passing. Closes the #82 regression.
- **`/audit` operative over remote MCP** — the 8 ISO/IEC 25010 analyzers ported to Node client-side scan the client's FS, not the VPS.
- **Pedagogical extension updater** — detects stale config after an update, auto-migrates transport (with backup + revert) and explains what changed.
- **Canonical-decision-aware drift gate** — validates against `app_spec.md`, the root cause that let #82 through.

100% backwards-compatible. Closes a class of silent failure on remote MCP.

---

## What's new in v6.7

**v6.7.0 — "Zero-Friction Onboarding"** removes all the friction from installing the VSCode extension and makes it tell you clearly when something is missing:

- **Python-free onboarding** — the MCP server is consumed only through the free hosted endpoint (the Local mode that required Python is gone). Engram installs as a native binary via Homebrew, not pip. Health check, walkthrough and README no longer mention Python.
- **Prerequisites gate** — on startup, if a critical requirement is missing (Claude Code, Engram, Node, or the MCP servers) the extension warns — clearly and non-blocking — that SpecBox may not work correctly, with one-click fixes. Silent when everything is ready.
- **"SpecBox: Check Prerequisites" command** — re-evaluate the environment on demand from the Command Palette.

100% backwards-compatible. Decision: no air-gapped fallback (the remote MCP is free); the gate warns, it does not block.

---

## What's new in v6.0

**v6.0.2 — "Smoke Test Followups"** closes the 3 open issues surfaced by the v6.0.1 smoke test (#60, #61, #62) and removes the last runtime version literal that survived in the server since v5.29:

- **`submit_quality_audit` autogenerates `audit_id`** if the client does not pass one (clients that need idempotency can still pass their own).
- **`run_quality_audit` deprecation now `raise`s** → MCP envelope correctly sets `isError=true`. Clients that only inspect the envelope now detect the deprecation.
- **`validate_discovery_completeness`** accepts all 4 canonical drift resolutions (`feature_creep_rejected`, `app_market_updated`, `documented_exception`, `no_drift`) and exposes new `drift.kind` field for future strict-gate modes.
- **`server/server.py`** no longer hardcodes the version — reads it from `ENGINE_VERSION.yaml` at module load. Latent `submit_quality_audit.fn(...)` bug eliminated as a side effect. `fastmcp 3.1.0 → 3.3.1` pinned `>=3.3.1,<4.0.0`.

100% backwards-compatible. Suite `1243 passed / 71 skipped / 0 failed`.

---

**v6.0.1 — "MCP Path Contract"** architectural hotfix that migrates 17 cat-A tools in `server/tools/` to a **universal content-passing pattern**: no `@mcp.tool`-registered function resolves `Path(project_path).resolve()` against the host filesystem. The client reads files locally with `Read`, passes content as string, and writes whatever the tool returns. Fixes the critical remote-MCP bug where tools were returning data from the VPS filesystem, not the client's. Skills updated (`/discovery`, `/prd`, `/plan`, `/visual-setup`, `/app-sync`, `/audit`, `/acceptance-check`) + new client helper `.claude/hooks/lib/mcp-client-io.mjs`.

---

**v6.0.0 — "Discovery Foundations"** introduces a permanent **Product Discovery** module integrated into the canonical pipeline (`/discovery → /prd → /plan → /implement`) + the third canonical document `doc/app/app_market.md` (primary ICPs + non-ICPs + global JTBDs + NSM + positioning) + the **multi-doc architectural foundation** (`server/app_docs/registry.py`) that supports extending to N canonical docs in v6.x+. v5.x projects get `app_market.md` as a `template-pristine` template via `upgrade_project` without touching existing files.

---

## What's new in v5.34

**v5.34.0 — "Native Collaboration"** introduces the **Native Backend**: a fourth `SpecBackend` implementation (alongside Trello / Plane / FreeForm), backed by a managed Supabase Postgres instance, built for teams where multiple developers share a single source-of-truth board.

- **Multi-tenant Postgres/Supabase backend** — all 26 ABC methods over an asyncpg pool, with **optimistic concurrency** (`expected_version`) so two developers don't clobber each other's work.
- **Developer identity + authorization** — token→developer resolution, Frontier 1 authz (UNAUTHENTICATED / FORBIDDEN). Tools `whoami`, `claim_uc`, `release_uc`, `register_native_branch` (token issuance / revoke moves to the SpecBox Control Panel in v5.34.1).
- **UC claims + branch registry** — a developer claims a UC and registers its feature branch.
- **Credential security (Frontier 2)** — the DSN lives only in `SPECBOX_NATIVE_DSN`, never on disk or in `meta.json`.

Opt-in and additive: if you don't set `backend_type='native'`, everything behaves as before. 100% backwards-compatible — Trello / Plane / FreeForm untouched. Validated in production against real Supabase (50 green tests).

**v5.34.1** adds two big pieces along the same Native line, without touching the other 3 backends:

- **Guided N×N backend switching (`/switch-backend`)** — a project can migrate from any of the 4 backends to any other (12 pairs) without losing US/UC/AC, state, comments or evidence. Additive migration (origin stays intact), mandatory dry-run preview, transactional switch of the 3 sources of truth (registry, `app_spec.md`, `settings.local.json`) with rollback, and opt-in `regenerate_evidence` to refresh acceptance after a migration.
- **Native hardened against mutations from revoked identities** — each of the 9 NativeBackend mutators re-validates identity + membership against `mcp_tokens` with a hardcoded 30s TTL cache. Exposure window after a revoke ≤ 30s (previously: hours). `delete_acceptance_criterion` and `archive_item` leave a forensic trail in `audit_log`. Cleanly redesigned identity model (`developers` + `github_identities` N:1 + revocable `mcp_tokens`) ready for the panel — team CRUD leaves the MCP.

---

## What's new in v5.33

**v5.33.0 — "FreeForm Path Safety"** turns the v5.29 BLOCKER (FreeForm + remote MCP writing the tracking folder on the VPS) into a mechanically impossible bug. v5.29 fixed it at the `/app-init` and server-side levels; v5.33 adds two more layers covering clients that don't go through the skill:

- **Universal hook `freeform-path-guard.mjs`** — PreToolUse intercepts `set_auth_token` and `onboard_project`. If the path is relative (or `doc/tracking` is the implicit default), it auto-rewrites to the absolute repo path via `git rev-parse --show-toplevel` before the call reaches the MCP. Silent auto-rewrite via `hookSpecificOutput.updatedInput`. Audit trail at `.quality/logs/freeform-path-rewrites.jsonl`.
- **MCP tool `detect_local_root_path()`** — read-only handshake declaring the contract (requires_absolute_path, client_resolution_recipe). Serves `/app-init`, claude.ai mobile, and external integrations as executable documentation.
- **`/app-init` Paso 2.3 reinforced** — 3-step handshake: call the contract tool, resolve from PROJECT_ROOT explicitly, pass absolute to `set_auth_token`. The hook remains as safety net for clients that don't use the skill.

3 additive, independent layers. Removing any one does not unblock the bug while the others stand. 100% backwards-compatible — pre-v5.33 clients without the hook still hit the v5.29 server-side guard.

---

## What's new in v5.32

**v5.32.0 — "Implement Task Isolation"** closes the explicit out-of-scope from v5.30: the `/implement` SKILL.md already documented Task delegation, but the contract wasn't mechanically enforced. v5.32 adds the 5 missing guardrails — without redesigning the architecture — and wires them observably:

- **`execution_context.json`** persisted per-feature (branch / stack / paths). Each Task reads it from disk instead of receiving those values in the prompt → fixes the root cause of context exhaustion on large UCs.
- **`context-budget-guard.mjs`** PreToolUse(Task) — estimates tokens, warns @ 16k (default), strict as a settings flip.
- **`file-ownership-guard.mjs`** PreToolUse(Write/Edit) — validates the path against the active agent's ownership. Suspicious paths (`..`, `/abs`) always BLOCKED.
- **`phase_outputs.jsonl`** — every Task writes a structured delta at close. Spec-Code Sync no longer depends on live `git diff` from the orchestrator.
- **Local telemetry** in `.quality/task_isolation.json` with `{enabled, tasks_run_total, tasks_failed_*}` (consumable by ad-hoc scripts or specbox_cloud).

100% backwards-compatible. `warn` modes default during the migration.

**v5.32.1** turns the "bump README + CHANGELOG on every release" rule into a mechanical guardrail: the `/release` skill now bumps both files as mandatory steps and a new `version-consistency-check.mjs` validator aborts the release if any of the 5 version files drifts out of sync.

---

## What's new in v5.31

**v5.31.0 — "Stitch Autopilot"** aligns the Google Stitch integration with its official best practices and removes the recurring autopilot blockers when generating designs:

- **Canonical DESIGN.md** ([Google's official format](https://github.com/google-labs-code/design.md)) auto-generated from Brand Kit + VEG. Solves cross-screen visual drift at the root.
- **v2 pipeline with fallback chain** (`edit_baseline → variants_refine → regenerate`) — timeouts and transient errors no longer break autopilot.
- **4-layer prompt validator** (Context / Components / Style with hex codes / Platform) — first generations closer to the brand, less iteration.
- **Batched build_site** for plans with >5 screens + final unified-theme pass.
- **Quota tracking** (350 Standard + 200 Experimental) with warnings ≥80% and a blocking hook at 100% (Flash safety net opt-in).

**Default model stays `GEMINI_3_PRO`**. Quality-first. Flash is only an opt-in safety net.

**v5.31.1** activates the above inside `/plan` Paso 6 (which until v5.31.0 still used the legacy v1 tool directly). Transparent migration — no settings change required.

## Why v5.29.0?

**Problem**: as you take on more parallel projects, SpecBox interrupts you too much. Every decision, every confirmation — multiplied by open projects = unmanageable cognitive load.

**v5.29.0** introduces a system of **decisions with auditable autonomy**: the engine handles cosmetic and repetitive choices, while guaranteeing it never touches the critical ones (destructive actions, push to main, costs over budget).

**Measured result**: friction points per feature drop from ≥17 (v5.28 baseline) to ≤8 with the default `equilibrado` preset.

## Quick Start

> **Using the VS Code extension?** You don't need to clone anything by hand —
> when the extension can't find the engine, it clones the public engine for you
> automatically into a managed folder (`~/.specbox/specbox-engine`) and keeps it
> up to date. The steps below are for the manual CLI install of the engine.

```bash
# Manual CLI install of the engine
git clone <repo-url> ~/specbox-engine
cd ~/specbox-engine
./install.sh

cd /path/to/your-project
/app-init                 # creates doc/app/ + configures autopilot=equilibrado
/prd "your first feature" # inherits audience and stack from app_prd.md
/plan US-01
/implement
```

That's it. Skills auto-discover when relevant; hooks run automatically.

## How it works

**1. Canonical project documents**: `/app-init` creates `doc/app/app_prd.md` (product: vision, audience, scope, metrics, roadmap) and `doc/app/app_spec.md` (technical: stack, backend, brand, conventions, autopilot). Each has typed zones — `manual` (only you edit), `auto` (only the engine rewrites), `hybrid` (append-only, both contribute). From here, `/prd`, `/plan` and `/visual-setup` consult these documents and **stop re-asking** for project-level decisions.

**2. Autopilot**: 4 tiers (low / conservador / **equilibrado** / agresivo) decide per-decision whether to auto-confirm, ask, or block. Inviolable rules: no auto-confirm of destructive actions, push to main, or costs over budget. Every auto-decision is logged to `.quality/autopilot_decisions.jsonl`.

**3. Sync enforcement**: pre-commit hook detects drift between `app_*.md` and reality. `/app-sync` reconciles. Multi-source drift detector catches what the hook alone misses (new lockfiles, broken brand kit refs, lying roadmaps, undocumented canonical decisions). Warning-only by default; flip `block_on_drift=true` when validated.

## Skills

23 auto-discoverable skills. v5.29 highlights:

- `/app-init` — Creates/refreshes canonical docs.
- `/app-sync` — Verify, repair, review, or rebuild canonical docs.
- `/queue review` — Resolve deferred decisions in batch.

Plus existing pipeline skills: `/prd`, `/plan`, `/visual-setup`, `/implement`, `/feedback`, `/release`, `/audit`, `/compliance`, `/quality-gate`, plus billing (`/stripe-*`), exploration (`/explore`, `/adapt-ui`, `/quickstart`), and operations (`/manual-test`, `/check-designs`, `/optimize-agents`, `/remote`, `/acceptance-check`).

## Backends

`freeform` is the v5.29 default for personal projects. `trello` and `plane` remain first-class for projects with external client reporting. 5-level auto-discovery picks the right one without asking.

Migration: Trello ↔ Plane (existing), Trello/Plane → FreeForm (new in v5.29).

## Stacks

Flutter 3.38+ (Maestro recommended), React 19.x (Playwright), Go 1.23+ (testing + httptest), Python 3.12+ FastAPI (pytest-bdd), Google Apps Script V8. Services: Supabase, Neon, Stripe, Firebase, n8n, Stitch MCP. Independent MCP packages in `packages/`.

## Migrating from v5.28

`detect_v529_migration_case` classifies your project into one of 10 known states. Sensitive cases (active feature, possible VPS data, manually-created app docs) are deferred for user review. 100% backwards-compatible: without `doc/app/` or `autopilot` config, behavior is identical to v5.28.

## Recent releases

- **v5.29.0** ← current — Cognitive Load Reduction.
- **v5.28.0** — Maestro Flutter E2E.
- **v5.27.0** — Stripe Standard + Switch Account.
- **v5.26.0** — Supabase Edge Secrets MCP.
- **v5.25.0** — Stripe Connect.

Full history in [CHANGELOG.md](CHANGELOG.md). Exhaustive technical reference in [CLAUDE.md](CLAUDE.md).

## Philosophy

> The LLM provides speed. SpecBox provides quality and traceability.

The engine doesn't take shortcuts for you — it **prevents them**. Every blocking hook exists because the alternative (LLM bypassing under pressure) is systematically worse than the friction.

## License

[Project license]
