# Cifras del Marketplace y uso de la extensión — Runbook

> Cómo sabe SpecBox cuánta gente lo instala y lo usa, sin saber quién es nadie.
> Introducido en v6.2.0 (UC-643) como un workflow con un fichero que nunca se guardó; desde v6.33.0
> (US-118) la extensión mide su uso, y desde v6.34.0 (US-119) la foto diaria vive en la base.

## Resumen

Hay dos medidas distintas, y las dos acaban en la base de SpecBox (Supabase propio del VPS):

| Medida | Qué cuenta | De dónde sale | Dónde queda |
|---|---|---|---|
| **Foto diaria de fuera** | Instalaciones y actualizaciones acumuladas del Marketplace, descargas diarias de npm, estrellas y forks de GitHub (y el tráfico del repo, solo para el SuperAdmin) | Una tarea diaria del VPS que lee las APIs públicas (06:15 UTC) | Tabla `external_signal_daily` |
| **Uso de la extensión** | Instalaciones que se activan y las que siguen en uso cada día | La propia extensión: una activación al instalarse y un latido al día | Tabla `site_event` (`activation`, `heartbeat`) |

La foto cuenta descargas, no personas. El uso cuenta instalaciones con la telemetría de VS Code activa.
Las dos se ven juntas en la página «Adopción» del SuperAdmin del panel.

## La foto diaria (US-119)

La hace `ops/external-signals/specbox-external-signals.py`, un temporizador systemd del VPS, en el
repo **specbox-manager**. Su runbook (instalar, relanzar a mano, token de GitHub y qué hacer si falla)
es [`doc/runbooks/foto-diaria-externa.md`](https://github.com/EmbedBuild/specbox-manager/blob/main/doc/runbooks/foto-diaria-externa.md)
de ese repo. El esquema es la migración `20261112000000_external_signal_daily.sql` de **specbox_cloud**:

- una fila por día (UTC), fuente y métrica; repetir la foto del día deja el último valor;
- `record_external_signals` la escribe y `external_signals_core` la lee, las dos solo para `service_role`.

El workflow `marketplace-stats.yml` y su script `fetch-marketplace-stats.mjs` se retiraron en v6.34.0:
escribían en `.quality/marketplace-stats.jsonl`, que git ignora, así que nunca guardaron nada.

### El endpoint del Marketplace

`POST https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery` con
`{"filters":[{"criteria":[{"filterType":7,"value":"EmbedBuild.specbox-engine"}]}],"flags":914}`
(`filterType: 7` = `publisher.extensionName` exacto). De `results[0].extensions[0].statistics` se
guardan `install` → `installs` y `updateCount` → `updates`. Es el mismo endpoint que usa `vsce show`;
no tiene límites documentados y una consulta al día está muy por debajo de cualquiera.

## La tool `get_marketplace_stats`

Lee la foto de la base con el pool del servidor MCP: las mismas cifras que la foto diaria.

```
get_marketplace_stats(window_days=30)
```

Devuelve `total_installs`, `total_updates`, `install_growth_pct` y `daily_series` (Marketplace), `npm`
(descargas del periodo y por día) y `github` (estrellas y forks). Solo cifras públicas: el tráfico del
repo (clonaciones y visitas), que GitHub solo enseña a quien administra el repo, no sale por la tool.
Sin base o antes de la primera foto responde `status: "no_data_yet"` con su `reason`.
`jsonl_content` se acepta por compatibilidad y se ignora desde v6.34.0.

## El uso de la extensión (US-118)

Desde v6.33.0 **la extensión sí envía telemetría de uso, anónima**:

- **Activación**: una vez por instalación, con un identificador aleatorio de esa instalación (o el de
  la visita al site, si llegó por su enlace), la versión de la extensión, la plataforma, la versión de
  VS Code y el origen (`site` o `marketplace`). Desde v6.33.1 sale nada más arrancar, sin esperar a
  ningún aviso.
- **Latido**: como mucho uno por día natural UTC mientras se usa, con el mismo identificador, la
  versión, la plataforma, la versión de VS Code y el tipo de board de la carpeta abierta (`freeform`,
  `native`, `trello`, `plane` o `none`).
- **Nunca** rutas, nombres de proyecto o repositorio, correos, cuentas ni tokens.
- **Se apaga** con la telemetría de VS Code (`telemetry.telemetryLevel` en `off`): sin ella no se
  envía nada.

Código: `vscode-extension/src/activation.ts` y `heartbeat.ts`, con sus pruebas. Lo explican el README
de la extensión («Usage telemetry») y la página de privacidad del site
(<https://specbox.build/privacy>).

## Troubleshooting

| Síntoma | Causa probable | Acción |
|---|---|---|
| `get_marketplace_stats` responde `no_data_yet` con `snapshot_table_missing` | El MCP apunta a una base sin la migración del panel | Aplicar `20261112000000_external_signal_daily.sql` de specbox_cloud |
| Responde `no_snapshot_in_window` | La foto no ha corrido en el periodo | Ver el registro del temporizador (`journalctl -u specbox-external-signals`) y relanzarlo (runbook del manager) |
| Faltan días en la serie | El VPS no ejecutó la foto ese día | Los días pasados de npm se recuperan solos en la siguiente foto; los acumulados del Marketplace de ese día no |
| `delta` negativo en `daily_series` | El Marketplace retiró instalaciones (fraude o duplicados) | Normal de vez en cuando |
| No llegan activaciones ni latidos | Telemetría de VS Code apagada, o una extensión anterior a la 6.33.1 | Comprobar la versión instalada; sin telemetría no se cuenta, por diseño |
