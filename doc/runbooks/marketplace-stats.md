# Marketplace Stats Snapshot — Runbook

> Telemetría pública de adopción para la extensión `jpsdeveloper.specbox-engine`
> en el VSCode Marketplace.
> Introducido en v6.2.0 por UC-643 (US-VSCODE-MARKETPLACE).

## Resumen

Una vez al día, GitHub Actions consulta el endpoint REST público del Marketplace de Microsoft, extrae las métricas agregadas de la extensión (installs, downloads, ratings, trending) y las añade como una línea JSON a [`.quality/marketplace-stats.jsonl`](../../.quality/marketplace-stats.jsonl). El histórico se commitea automáticamente a `main` para que cualquier consumidor (la tool MCP `get_marketplace_stats`, scripts ad-hoc, dashboards externos) pueda leerlo.

## Privacy & data sources

**Cero PII.** Toda la información viene del endpoint público del Marketplace y refleja datos agregados del listing — no se recoge nada del cliente de cada usuario que instala la extensión. La extensión en sí no contiene telemetría activa (no envía eventos a Application Insights ni a servicios similares).

- **Fuente única**: `POST https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery`
- **Datos extraídos**: `install`, `updateCount` (downloads), `averagerating`, `ratingcount`, `trendingdaily`, `trendingweekly`, `trendingmonthly`.
- **Datos NO recogidos**: IPs de instalación, IDs de máquina, paths de filesystem, comandos ejecutados, errores runtime, locale del usuario.

## Componentes

| Archivo | Rol |
|---------|-----|
| [`.github/workflows/marketplace-stats.yml`](../../.github/workflows/marketplace-stats.yml) | Cron diario (06:00 UTC) + `workflow_dispatch` manual |
| [`scripts/fetch-marketplace-stats.mjs`](../../scripts/fetch-marketplace-stats.mjs) | Cliente Node 20 zero-deps que llama al endpoint y appendea al jsonl |
| [`.quality/marketplace-stats.jsonl`](../../.quality/marketplace-stats.jsonl) | Histórico append-only, una línea JSON por día |
| [`server/tools/marketplace.py`](../../server/tools/marketplace.py) | Tool MCP `get_marketplace_stats` que agrega métricas dentro de una ventana |
| [`tests/test_marketplace_tool.py`](../../tests/test_marketplace_tool.py) | 9 tests pytest sobre la función pura `aggregate_marketplace_stats` |

## El endpoint `extensionquery`

Endpoint REST no documentado oficialmente por Microsoft, pero ampliamente usado por el ecosistema (la propia `vsce` lo utiliza para `vsce show`). Esquema observado:

**Request** (JSON):

```json
{
  "filters": [{
    "criteria": [{"filterType": 7, "value": "jpsdeveloper.specbox-engine"}],
    "pageSize": 1,
    "pageNumber": 1
  }],
  "flags": 914
}
```

`filterType: 7` = filtrar por `publisher.extensionName` exacto.

### Qué significa `flags=914`

El campo `flags` es un bitmask con las opciones de respuesta que pedimos. `914` corresponde a la suma de los bits más comunes para extraer estadísticas:

| Bit  | Constante                  | Incluido en 914 |
|------|----------------------------|:---------------:|
| 2    | `IncludeVersions`          | ✓               |
| 16   | `IncludeStatistics`        | ✓               |
| 128  | `IncludeAssetUri`          | ✓               |
| 256  | `IncludeCategoryAndTags`   | ✓               |
| 512  | `IncludeVersionProperties` | ✓               |

Estos cinco flags suman exactamente 914. No incluye `IncludeFiles` (1) ni `IncludeInstallationTargets` (8) — no los necesitamos y aumentarían el payload.

### Response shape (relevante)

```json
{
  "results": [{
    "extensions": [{
      "publisher": {"publisherName": "jpsdeveloper"},
      "extensionName": "specbox-engine",
      "versions": [{"version": "6.2.0", "lastUpdated": "..."}],
      "statistics": [
        {"statisticName": "install", "value": 123},
        {"statisticName": "updateCount", "value": 45},
        {"statisticName": "averagerating", "value": 4.7},
        {"statisticName": "ratingcount", "value": 12},
        {"statisticName": "trendingdaily", "value": 0.12},
        ...
      ]
    }]
  }]
}
```

Si la extensión no está publicada todavía, el endpoint devuelve `404` o `results[].extensions == []`. El script trata ambos casos como "no data yet" y exit 0 sin contaminar el jsonl.

## Rate limiting

Microsoft no documenta límites oficiales. La observación de la comunidad sugiere que >10 req/min desde la misma IP puede devolver 429 temporal. El cron diario (1 req/día) está **muy** por debajo de cualquier umbral razonable.

Si en algún momento el workflow falla con 429, el job exit code != 0 → reintento manual al día siguiente. NO añadir backoff agresivo en el script para evitar amplificar el problema.

## Uso manual

### Disparar el snapshot fuera del cron

```bash
gh workflow run marketplace-stats.yml -R EmbedBuild/specbox-engine
```

El job tarda <1 minuto. El resultado se commitea automáticamente a `main` si hay datos nuevos.

### Consultar las stats agregadas vía MCP

Desde un cliente MCP (Claude Code, claude.ai, etc.):

```
get_marketplace_stats(window_days=30, jsonl_content=<contenido del jsonl>)
```

El cliente debe leer localmente `.quality/marketplace-stats.jsonl` y pasar el contenido (v6.0.1 Path Contract).

### Inspección directa del jsonl

```bash
tail -7 .quality/marketplace-stats.jsonl | jq .
```

## Troubleshooting

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| Workflow falla con `404` | Extensión aún no publicada o `extensionName` cambió | Verificar listing en marketplace.visualstudio.com. El script ya hace soft-skip si pasa antes del primer publish. |
| Workflow falla con `429` | Rate limit (improbable con cron diario) | Esperar 24h. Si persiste, revisar si hay otro proceso disparando el endpoint. |
| jsonl tiene gaps (días sin entry) | Cron no se ejecutó (incidente GitHub Actions o repo archivado) | Disparar manualmente con `gh workflow run marketplace-stats.yml`. Los gaps son cosméticos — `aggregate_marketplace_stats` los tolera. |
| `delta_installs_24h` saliendo negativo | Edge raro: Microsoft retira instalaciones contadas como fraude o duplicadas | Aceptable, sucede ocasionalmente en extensiones populares. El jsonl preserva los datos brutos. |

## Cuándo actualizar este runbook

- Microsoft cambia el shape del endpoint `extensionquery` (improbable, es API estable desde 2017).
- El script `fetch-marketplace-stats.mjs` evoluciona (p. ej. añadimos un nuevo stat).
- Se añade telemetría activa en la extensión — en ese caso ya **no es zero PII** y este runbook debe actualizarse o reemplazarse.
