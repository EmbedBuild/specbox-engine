# PRD: US-VSCODE-MARKETPLACE — Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine

> Origen: FreeForm backend `ff-ed0c02f4565a` | US-VSCODE-MARKETPLACE
> Tipo: PRD Técnico (release infrastructure + onboarding UX)
> Generado: 2026-05-26
> Release target: v6.2.0 "VSCode Marketplace" (minor)
> Vía elegida: A pura (publish + CI sync, sin refactor thin-extension)

## Resumen Ejecutivo

La extensión `EmbedBuild.specbox-engine` existe en el repo (`vscode-extension/`) y declara `publisher: "EmbedBuild"`, pero **no está publicada en el VSCode Marketplace**. Hoy se instala vía VSIX local generado por `install-ext.mjs` durante `./install.sh`, lo cual requiere que el usuario primero clone el repo. Esto rompe el flujo natural "Marketplace → un click → instalada" que un usuario VSCode espera.

Adicionalmente, la extensión está **drifteada**: `vscode-extension/package.json` declara `version: "5.21.1"` mientras el engine va por `v6.1.1` (más de un mes y 6 versiones de retraso). El motivo es que no hay un mecanismo que sincronice ambas versiones en cada release del engine.

Esta US cierra los dos problemas a la vez:
1. **Publicar** la extensión al VSCode Marketplace bajo `EmbedBuild.specbox-engine`.
2. **Establecer CI que la mantenga en lockstep con el engine**: cada tag `v*.*.*` del engine bumpea automáticamente `vscode-extension/package.json` y publica al Marketplace vía `vsce publish`.

Decisiones de scope ya cerradas con el usuario:
- **Solo VSCode Marketplace** (no Open VSX en este release — Cursor e Insiders leen del mismo Marketplace transparentemente).
- **Lockstep estricto**: `extension.version == engine.version` siempre.
- **Vía A pura**: NO refactor a "thin extension" (descargar engine matching desde GitHub al activar). Eso queda diferido a una US v6.3.x.
- **NO** "Setup MCP Server" guiado — fuera de scope.
- **i18n EN + ES en V1**: listing del Marketplace (displayName, description) + README bilingüe + strings user-facing de la extensión via `vscode-nls`. EN es idioma canónico (fallback); ES localizado.
- **Telemetría Marketplace API en V1**: scraper 1×/día contra el Marketplace REST API público, persiste a `.quality/marketplace-stats.jsonl`, expone tool MCP `get_marketplace_stats`. Cero telemetría activa en la extensión — solo datos públicos agregados. Privacy-clean.

## Alcance

### Incluye

- **Sync de versionado**: script `scripts/sync-extension-version.sh` que lee `ENGINE_VERSION.yaml` y escribe la misma versión en `vscode-extension/package.json`. Idempotente.
- **CI publish workflow**: `.github/workflows/publish-vscode-extension.yml` que dispara en cada tag `v*.*.*`, builda el VSIX, lo publica al Marketplace con `vsce publish`, y adjunta el `.vsix` al GitHub Release.
- **Pre-flight de release**: el skill `/release` (o el script de release) verifica que la versión de la extensión matchea la del engine antes de cortar el tag.
- **Setup de publisher**: documentación del flujo `vsce login EmbedBuild`, configuración del PAT en GitHub Secrets (`VSCE_PAT`), README de la extensión actualizado para Marketplace.
- **Metadata profesional de Marketplace**: `vscode-extension/package.json` con `icon`, `categories`, `keywords`, `repository`, `bugs`, `homepage`, `galleryBanner` revisados; README con badges, screenshots, troubleshooting; `CHANGELOG.md` de la extensión sincronizado con el del engine.
- **Smoke test post-publish**: script que instala la extensión recién publicada en un VSCode limpio (Docker o GitHub Actions runner) y verifica que `specbox.healthCheck` retorna OK.
- **i18n EN + ES (V1)**: localización del listing del Marketplace (`displayName`, `description`, `categories`-friendly text) + `README.md` (EN canon) + `README.es.md` + estructura `vscode-nls` para los strings user-facing de la extensión (notificaciones, prompts, output channel). Archivos `package.nls.json` (default EN) + `package.nls.es.json`.
- **Telemetría Marketplace stats (V1)**: workflow CI `.github/workflows/marketplace-stats.yml` corre 1×/día (cron) o on-demand, llama al Marketplace REST API público (`https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery`), extrae installs/downloads/avgRating/trending, appendea entry a `.quality/marketplace-stats.jsonl`. Tool MCP `get_marketplace_stats(window_days=30)` expone los datos agregados. Cero telemetría activa, cero PII.
- **First-release v6.2.0**: publicar el primer build alineado en el Marketplace al cortar v6.2.0.

### No incluye

- **Open VSX Registry** — diferido. La US toca solo VSCode Marketplace.
- **Refactor a "thin extension"** (extensión descarga engine matching desde GitHub) — diferido a US v6.3.x. La extensión sigue empaquetando los recursos como hoy.
- **Auto-update de la extensión empujando un upgrade del engine instalado** — fuera de scope. El usuario sigue corriendo `./install.sh` o el comando `SpecBox: Install Engine` manualmente.
- **Comando `SpecBox: Setup MCP Server`** — fuera de scope, otra US.
- **JetBrains / Eclipse / otros IDEs** — solo VSCode.
- **Eliminación del flujo VSIX local** (`install-ext.mjs`) — se mantiene como fallback para devs del engine que necesiten testear cambios sin publicar.
- **Telemetría activa en la extensión** (Application Insights, eventos de uso, opt-in flow) — fuera de V1. Solo datos públicos del Marketplace.
- **Localización a más idiomas** (FR, DE, PT, etc.) — V1 solo EN + ES. La estructura `vscode-nls` permite añadir locales luego sin refactor.
- **CHANGELOG bilingüe** — `CHANGELOG.md` se mantiene en EN únicamente (convención estándar del ecosistema VSCode/npm).

---

## Objetivos

1. **Reducir fricción de instalación a un click**: usuario busca "SpecBox" en VSCode Extensions → Install → tiene los comandos `SpecBox: *` disponibles. Sin clonar el repo.
2. **Eliminar el drift estructural**: la extensión publicada SIEMPRE matchea el engine actual en `main`. Imposible publicar un tag del engine sin que la extensión esté sincronizada (gate en CI).
3. **Discoverability**: SpecBox aparece en búsquedas del Marketplace con `claude`, `claude-code`, `agentic`, `MCP`, `spec-driven`, `BDD`.
4. **Reproducible release**: cortar v6.2.0 publica automáticamente la extensión sin pasos manuales (más allá de la rotación inicial del PAT).
5. **Audit trail**: el workflow deja evidencia en GitHub Actions de cada publish (versión, SHA, fecha, output de `vsce`).
6. **Accesibilidad bilingüe**: hispanohablantes ven el listing del Marketplace y los mensajes de la extensión en español sin perder la audiencia internacional (EN sigue siendo canónico y fallback).
7. **Visibilidad de adopción**: el mantenedor puede consultar `get_marketplace_stats` o leer `.quality/marketplace-stats.jsonl` para ver instalaciones/downloads/rating en el tiempo, sin recurrir a scraping manual del portal web del Marketplace.

---

## Estado Actual vs Propuesto

### ACTUAL

```
vscode-extension/package.json:version           "5.21.1"  (engine va por 6.1.1)
vscode-extension/install-ext.mjs                builda VSIX local on-demand
install.sh:401-419                              llama install-ext.mjs si VSCode CLI presente
.github/workflows/                              SIN workflow de publish al Marketplace
scripts/release/                                SIN sync de versión extensión ↔ engine
VSCode Marketplace                              EXTENSIÓN NO LISTADA
GitHub Releases v6.1.0, v6.1.1                  NO incluyen .vsix como asset
README del repo                                 menciona instalación via clone+install.sh, no Marketplace
vscode-extension/                               sin estructura i18n (sin package.nls.json, sin l10n/)
vscode-extension/src/extension.ts               strings user-facing hardcoded en EN dentro del código
.quality/                                       sin marketplace-stats.jsonl
server/tools/                                   sin tool get_marketplace_stats
```

### PROPUESTO

```
✓ vscode-extension/package.json:version          matchea ENGINE_VERSION.yaml en cada tag
✓ scripts/sync-extension-version.sh              CREADO; lee yaml, escribe package.json
✓ .github/workflows/publish-vscode-extension.yml CREADO; trigger on tag v*.*.*
✓ .github/workflows/marketplace-stats.yml        CREADO; cron daily 06:00 UTC + workflow_dispatch
✓ GitHub Secrets:VSCE_PAT                        configurado (PAT del publisher EmbedBuild)
✓ /release skill                                 invoca sync-extension-version antes del tag
✓ vscode-extension/CHANGELOG.md                  CREADO; entries paralelas al CHANGELOG del engine (EN únicamente)
✓ vscode-extension/README.md                     EN canon; reescrito para audiencia Marketplace
✓ vscode-extension/README.es.md                  ES traducción completa; link cruzado desde README.md
✓ vscode-extension/package.json                  metadata Marketplace completa, displayName/description vía nls
✓ vscode-extension/package.nls.json              EN strings (default fallback)
✓ vscode-extension/package.nls.es.json           ES strings
✓ vscode-extension/src/l10n/bundle.l10n.json     EN runtime strings (vscode-l10n)
✓ vscode-extension/src/l10n/bundle.l10n.es.json  ES runtime strings
✓ vscode-extension/src/extension.ts              strings via vscode.l10n.t(...) en vez de literales
✓ Marketplace listing                            público en https://marketplace.visualstudio.com/items?itemName=EmbedBuild.specbox-engine, visible en EN y ES
✓ .quality/marketplace-stats.jsonl               append-only, una entry por día con installs/downloads/rating/trending
✓ server/tools/marketplace.py                    CREADO; expone get_marketplace_stats(window_days) MCP tool
✓ GitHub Release v6.2.0                          adjunta .vsix; release notes apuntan al Marketplace
✓ README raíz del repo                           sección "Instalación" con el Marketplace como vía recomendada
```

---

## User Stories y Use Cases

### US-VSCODE-MARKETPLACE

**Como usuario hispanohablante de Claude Code en VSCode**
**quiero instalar SpecBox Engine desde el VSCode Marketplace en un click y ver la interfaz en mi idioma**
**para empezar a usar los skills `/prd /plan /implement` sin tener que clonar repos ni correr scripts, y sin pelearme con strings en inglés.**

**Como usuario internacional (EN)**
**quiero el mismo flujo de un click pero con la UI en inglés**
**porque es el idioma canónico de mi entorno de desarrollo.**

**Como mantenedor del engine**
**quiero (a) que cada release del engine publique automáticamente la extensión sincronizada, y (b) ver métricas de adopción (instalaciones, downloads, rating) sin tener que abrir el portal del Marketplace manualmente**
**para que la extensión nunca quede drifteada respecto al engine y para tomar decisiones de roadmap basadas en señales reales de uso.**

---

### UC-634 — Script sync-extension-version

**Actor**: Engine
**Horas estimadas**: 4

**Descripción**: Crear `scripts/sync-extension-version.sh` que lee `ENGINE_VERSION.yaml` y escribe la misma versión en `vscode-extension/package.json`. Idempotente. Falla con exit code != 0 si las versiones ya no coinciden y NO se le pasó `--write`.

**Acceptance Criteria**:
- AC-01: Script lee `version:` de `ENGINE_VERSION.yaml` (mismo parseo que `install.sh:11`: `grep 'version:' | head -1 | awk '{print $2}'`).
- AC-02: Modo `--check` (default sin args): exit 0 si `package.json.version` == engine version; exit 1 con mensaje claro si difieren. No escribe nada.
- AC-03: Modo `--write`: actualiza `vscode-extension/package.json` con la versión del engine usando `jq` o un parser Python `json` (NO sed/regex sobre JSON). Preserva indentación y orden de keys.
- AC-04: Modo `--write` también actualiza `vscode-extension/package-lock.json` si existe (top-level `version` field).
- AC-05: Tests en `scripts/tests/test-sync-extension-version.sh`: caso "ya sincronizadas", caso "drift detectado en --check", caso "drift corregido en --write".

---

### UC-635 — Hook de release: bloquear tag si extensión drifteada

**Actor**: Engine
**Horas estimadas**: 3

**Descripción**: Integrar `sync-extension-version.sh --check` en el flujo del skill `/release` ANTES de generar el tag git. Si retorna != 0, el skill ofrece autorun `--write` + commit, o aborta.

**Acceptance Criteria**:
- AC-01: `/release` SKILL.md actualizado: nuevo paso "Pre-flight: verify VSCode extension version sync" antes del paso de tagging.
- AC-02: El paso corre `bash scripts/sync-extension-version.sh --check`. Si exit 0, sigue.
- AC-03: Si exit != 0, el skill prompta al usuario: opción 1 "auto-fix + commit" (corre `--write`, hace commit `chore(vscode-ext): sync version to vX.Y.Z`), opción 2 "abort release". Sin opción 3 (no se permite tagear con drift).
- AC-04: Si se elige opción 1, el commit de sync entra ANTES del commit de release notes y del tag. Verificado por `git log --oneline -3` post-release.
- AC-05: Test manual documentado en el SKILL.md de `/release`: cómo simular drift y verificar que el gate dispara.

---

### UC-636 — Metadata Marketplace en package.json

**Actor**: Engine
**Horas estimadas**: 3

**Descripción**: Auditar y actualizar `vscode-extension/package.json` para cumplir best practices del Marketplace (icon ≥128x128, categories válidas, keywords relevantes, repository/bugs/homepage URLs, galleryBanner, license, badges).

**Acceptance Criteria**:
- AC-01: `package.json` declara: `displayName`, `description`, `version`, `publisher: "EmbedBuild"`, `license: "MIT"`, `engines.vscode`, `icon` (path a PNG ≥128x128), `categories` (mínimo `["AI", "Other"]`, considerar `"Programming Languages"` y `"Snippets"` si aplica), `keywords` (mínimo `claude`, `claude-code`, `agentic`, `MCP`, `spec-driven`, `BDD`).
- AC-02: `package.json` declara `repository.url=https://github.com/EmbedBuild/specbox-engine`, `bugs.url=https://github.com/EmbedBuild/specbox-engine/issues`, `homepage=https://github.com/EmbedBuild/specbox-engine#readme`. **El `publisher` del Marketplace es `EmbedBuild`**, alineado con el owner del repo en GitHub para que el branding sea coherente entre ambas plataformas.
- AC-03: `package.json` declara `galleryBanner.color` y `galleryBanner.theme` ("dark" o "light") consistente con el branding.
- AC-04: `vscode:prepublish` script existe y compila TypeScript sin errores (`tsc -p ./`).
- AC-05: `vsce ls --tree` corre sin warnings ni errores sobre missing fields o `.vscodeignore` mal configurado.

---

### UC-637 — README y CHANGELOG de la extensión para Marketplace

**Actor**: Engine
**Horas estimadas**: 4

**Descripción**: Reescribir `vscode-extension/README.md` para audiencia Marketplace (no devs del engine): qué hace la extensión, cómo instalarla, qué comandos provee, screenshots, link al engine. Crear `vscode-extension/CHANGELOG.md` con entries paralelas a las del engine.

**Acceptance Criteria**:
- AC-01: `vscode-extension/README.md` reescrito: sección "Features" con los 5 comandos (`SpecBox: Install`, `Health Check`, `Onboard Project`, `Show Status`, `Configure MCP`), sección "Requirements" (Claude Code CLI o VSCode extension de Claude), sección "Quick Start" (3 pasos), sección "Troubleshooting", link al repo del engine.
- AC-02: README incluye al menos 1 screenshot del comando `SpecBox: Show Status` o del sidebar `specbox.status` view. Imagen vive en `vscode-extension/media/screenshots/`.
- AC-03: README incluye badges: VSCode Marketplace version, VSCode Marketplace installs, License, engine version compatibility.
- AC-04: `vscode-extension/CHANGELOG.md` creado con formato Keep a Changelog. Entry `[6.2.0]` describe "First Marketplace release; lockstep versioning with SpecBox Engine."
- AC-05: La sincronización de CHANGELOG entre engine y extensión queda documentada: cada release del engine añade su entry también en el CHANGELOG de la extensión (manual en v1; el skill `/release` lo recuerda al humano).

---

### UC-638 — Workflow CI: publish al Marketplace en tag

**Actor**: Engine
**Horas estimadas**: 6

**Descripción**: Crear `.github/workflows/publish-vscode-extension.yml` que dispara on tag `v*.*.*`, instala Node.js, builda el VSIX, lo publica al Marketplace con `vsce publish` usando `VSCE_PAT` de GitHub Secrets, y adjunta el `.vsix` al GitHub Release correspondiente.

**Acceptance Criteria**:
- AC-01: Workflow file en `.github/workflows/publish-vscode-extension.yml`. Trigger: `on: push: tags: ['v*.*.*']`.
- AC-02: Job corre en `ubuntu-latest`, Node.js 20 LTS, instala `@vscode/vsce` globalmente, hace `cd vscode-extension && npm ci && npm run vscode:prepublish`.
- AC-03: Step "Sync version" corre `bash scripts/sync-extension-version.sh --check` y falla el workflow si hay drift (red flag — no debería pasar si UC-635 funciona, pero defense-in-depth).
- AC-04: Step "Publish" corre `vsce publish --pat "${{ secrets.VSCE_PAT }}"`. Output capturado en logs del workflow.
- AC-05: Step "Attach VSIX to release" corre `vsce package -o specbox-engine-${VERSION}.vsix` + `gh release upload v${VERSION} specbox-engine-${VERSION}.vsix` (usa `GITHUB_TOKEN` para upload). Si el GitHub Release aún no existe (porque `/release` lo crea en otro workflow), el step espera y reintenta hasta 3 veces.
- AC-06: Workflow respeta el principio "no skipping hooks" — si el `vsce publish` falla, el job entero falla y notifica.

---

### UC-639 — Setup inicial del publisher y secrets

**Actor**: Humano (one-time setup)
**Horas estimadas**: 2

**Descripción**: Documentar y ejecutar el setup one-time del publisher `EmbedBuild` en el VSCode Marketplace y la configuración del PAT en GitHub Secrets. Generar un runbook reproducible para rotación futura del PAT.

**Acceptance Criteria**:
- AC-01: `doc/runbooks/vscode-marketplace-publisher-setup.md` creado. Documenta: crear cuenta Azure DevOps, crear org, crear PAT scope "Marketplace > Manage", registrar publisher `EmbedBuild` con `vsce create-publisher`, añadir `VSCE_PAT` a GitHub Secrets del repo.
- AC-02: El runbook incluye sección "Rotación del PAT" (los PATs de Azure DevOps caducan máx 1 año): cómo regenerar sin perder ownership del publisher, cómo actualizar el secret en GitHub.
- AC-03: El runbook incluye comando de verificación: `vsce ls-publishers` debe mostrar `EmbedBuild` y `vsce show EmbedBuild.specbox-engine` debe responder OK tras el primer publish.
- AC-04: El runbook documenta el "unpublish" de emergencia (`vsce unpublish EmbedBuild.specbox-engine`) y advertencias del Marketplace (puede tardar horas en propagarse).
- AC-05: Una vez ejecutado el setup, en `GitHub Repo Settings → Secrets and variables → Actions` existe `VSCE_PAT` (verificable por listado, no por valor).

---

### UC-641 — i18n del listing del Marketplace (EN + ES)

**Actor**: Engine
**Horas estimadas**: 4

**Descripción**: Estructurar el `package.json` para que `displayName`, `description` y los `title` de comandos/views/settings se carguen desde archivos `package.nls.json` (EN, fallback) y `package.nls.es.json` (ES). VSCode auto-resuelve según `vscode.env.language` del cliente. EN es canónico; ES traduce.

**Acceptance Criteria**:
- AC-01: `vscode-extension/package.nls.json` (EN) creado con keys: `extension.displayName`, `extension.description`, `command.install.title`, `command.healthCheck.title`, `command.onboard.title`, `command.showStatus.title`, `command.configureMcp.title`, `view.status.title`. Cada key tiene su valor en inglés.
- AC-02: `vscode-extension/package.nls.es.json` creado con las mismas keys traducidas al español neutro (España, tuteo estándar). Ejemplos: `command.install.title="SpecBox: Instalar Engine"`, `command.healthCheck.title="SpecBox: Comprobar Salud"`.
- AC-03: `vscode-extension/package.json` actualizado: `displayName` y `description` apuntan a `"%extension.displayName%"` y `"%extension.description%"`. Cada `command.title` y `view.name` referencia su key NLS correspondiente.
- AC-04: Smoke test local: `code --locale=es` + abrir VSCode con la extensión instalada → todos los items del Command Palette empiezan por "SpecBox:" en español. `code --locale=en` → en inglés.
- AC-05: El Marketplace listing (panel web del Marketplace) muestra la descripción en español cuando el navegador del usuario tiene `Accept-Language: es-*` (verificable post-publish abriendo la URL del listing con cookie de idioma ES).

---

### UC-642 — i18n de strings runtime de la extensión (vscode-l10n)

**Actor**: Engine
**Horas estimadas**: 6

**Descripción**: Refactorizar `vscode-extension/src/extension.ts` y módulos relacionados para que todos los strings user-facing (notificaciones `showInformationMessage`, prompts `showInputBox`, output channel labels, error messages) pasen por `vscode.l10n.t(...)`. Bundlear traducciones en `l10n/bundle.l10n.json` (EN) y `l10n/bundle.l10n.es.json` (ES).

**Acceptance Criteria**:
- AC-01: `vscode-extension/package.json` declara `"l10n": "./l10n"` apuntando al directorio que contiene los bundles. Mecanismo oficial `vscode-l10n` (VSCode ≥1.86).
- AC-02: `vscode-extension/l10n/bundle.l10n.json` contiene todos los strings user-facing en EN, extraídos de `src/extension.ts` y comandos. Cada key es el string EN literal (convención `vscode-l10n`).
- AC-03: `vscode-extension/l10n/bundle.l10n.es.json` traduce todas las keys de AC-02 a español. Strings con placeholders (`{0}`, `{1}`) preservan el orden de argumentos.
- AC-04: `src/extension.ts` y archivos hermanos NO contienen literales de strings user-facing — todos pasan por `vscode.l10n.t("...")`. Verificado por un linter custom (`scripts/lint-extension-strings.mjs`) que falla si encuentra `vscode.window.showInformationMessage("literal"...)` sin `l10n.t`.
- AC-05: Smoke test: instalar la extensión en VSCode con locale `es` → ejecutar `SpecBox: Health Check` → la notificación de output sale en español. Misma operación con locale `en` → sale en inglés.

---

### UC-643 — Telemetría de instalaciones via Marketplace API

**Actor**: Engine
**Horas estimadas**: 6

**Descripción**: Crear workflow CI que consulta diariamente el Marketplace REST API público (`extensionquery` endpoint), extrae métricas de adopción (installs, downloads, avgRating, trending, daily delta) y las persiste en `.quality/marketplace-stats.jsonl`. Exponer los datos vía tool MCP `get_marketplace_stats(window_days=30)`. Cero telemetría activa en la extensión — solo datos públicos del listing.

**Acceptance Criteria**:
- AC-01: `.github/workflows/marketplace-stats.yml` creado. Triggers: `schedule: cron "0 6 * * *"` (diario 06:00 UTC) + `workflow_dispatch` (manual). Job en `ubuntu-latest` con Node.js 20.
- AC-02: Script `scripts/fetch-marketplace-stats.mjs` invocado por el workflow: POST a `https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery` con body `{"filters":[{"criteria":[{"filterType":7,"value":"EmbedBuild.specbox-engine"}]}],"flags":914}`. Parsea response, extrae `statistics[]` (installs, updateCount, avgRating, ratingCount, trendingDaily, trendingMonthly). Appendea a `.quality/marketplace-stats.jsonl` una línea JSON con shape `{date, version, installs, downloads, avg_rating, rating_count, trending_daily, trending_monthly, delta_installs_24h}`. El `delta_installs_24h` se computa contra la última entry del jsonl.
- AC-03: Workflow commitea el jsonl actualizado a `main` con mensaje `chore(stats): marketplace stats YYYY-MM-DD` usando `peter-evans/create-pull-request@v6` (PR auto-merged si la rama es `main` y el commit toca solo `.quality/marketplace-stats.jsonl`) O commit directo si el workflow corre con write permission. Falla suave si el endpoint retorna 404 (la extensión aún no está publicada — log warning, exit 0).
- AC-04: `server/tools/marketplace.py` creado: registra tool MCP `get_marketplace_stats(window_days: int = 30, project_path: str = "")` que lee `.quality/marketplace-stats.jsonl`, filtra por ventana de tiempo, retorna `{total_installs, total_downloads, avg_rating, install_growth_pct, daily_series[{date, installs, delta}], current_trending_rank}`. Sigue el MCP Path Contract v6.0.1 (content-passing si `project_path` no se resuelve localmente, fallback a path-based para in-process callers).
- AC-05: Test `tests/test_marketplace_tool.py` con jsonl fixture: 30 entries simuladas → la tool retorna métricas correctas, el `install_growth_pct` es positivo, el `daily_series` tiene exactamente 30 entries. Test de edge case: jsonl vacío → tool retorna `{"status": "no_data_yet", "reason": "extension_not_published_or_no_stats"}`.
- AC-06: Documentación: `doc/runbooks/marketplace-stats.md` con (a) cómo el endpoint funciona, (b) qué `flags=914` significa (`IncludeStatistics | IncludeVersions | IncludeCategoryAndTags | IncludeFiles`), (c) límites de rate limiting (no documentados oficialmente; se observa que >10 req/min puede bloquear temporalmente — el cron 1×/día está muy lejos), (d) cómo consultar manualmente vía `gh workflow run marketplace-stats.yml`.
- AC-07: **Privacy**: el workflow y la tool NO capturan ningún dato del usuario final. Solo agregados públicos del Marketplace listing. Documentado en `doc/runbooks/marketplace-stats.md` sección "Privacy & data sources".

---

### UC-640 — Smoke test post-publish

**Actor**: Engine
**Horas estimadas**: 4

**Descripción**: Crear `.github/workflows/smoke-test-marketplace.yml` que tras un publish exitoso instala la extensión desde el Marketplace en un VSCode limpio (en GitHub Actions runner con `code-server` o `xvfb` + VSCode headless) y verifica que la extensión se activa y los comandos están registrados.

**Acceptance Criteria**:
- AC-01: Workflow en `.github/workflows/smoke-test-marketplace.yml`. Trigger: `workflow_run` después de `publish-vscode-extension.yml` exitoso, O manual via `workflow_dispatch`.
- AC-02: Job en `ubuntu-latest`, instala VSCode CLI (`code` via apt o snap), corre `code --install-extension EmbedBuild.specbox-engine --force`.
- AC-03: Job verifica `code --list-extensions | grep EmbedBuild.specbox-engine` retorna exit 0 y la versión instalada matchea el tag actual.
- AC-04: Job crea un workspace dummy con `ENGINE_VERSION.yaml` (trigger de activación de la extensión, ver `activationEvents` en `package.json`), abre VSCode headless, verifica vía `code --status` o un test script que la extensión está activa.
- AC-05: Job corre el smoke en matrix `locale: [en, es]` — instala con `code --locale=en` y luego `code --locale=es`, verifica para cada uno que el comando `SpecBox: Install Engine` (EN) / `SpecBox: Instalar Engine` (ES) aparece en el listado de comandos registrados. Falla el job si alguna variante no resuelve la traducción correcta.
- AC-06: Si el smoke test falla, el workflow abre automáticamente un issue en el repo con label `marketplace-smoke-fail` y el output del workflow. NO hace rollback automático (el unpublish es manual y consciente).

---

## Métricas de éxito

- **Antes**: 0 instalaciones desde Marketplace, drift de 6 versiones engine ↔ extensión, listing solo posible en EN, cero visibilidad de adopción más allá del portal web manual.
- **Después de v6.2.0**:
  - Extensión publicada y descubrible por búsqueda `SpecBox` en VSCode.
  - Drift estructural imposible: workflow CI bloquea tag si versiones no matchean.
  - First-release smoke test verde en `locale: en` y `locale: es`.
  - `.quality/marketplace-stats.jsonl` con al menos 7 entries (1 semana de scraping diario).
  - Tool MCP `get_marketplace_stats(window_days=7)` retorna datos válidos.
- **A 30 días post-release**:
  - ≥10 instalaciones únicas desde el Marketplace (verificable vía `get_marketplace_stats(window_days=30)` o portal del publisher).
  - ≥1 instalación con `vscode.env.language=es` confirmada (proxy: rating o issue feedback en español).
  - `marketplace-stats.jsonl` con 30 entries continuas (sin gaps > 2 días — métrica de fiabilidad del cron).
- **A 90 días**:
  - Ratio drift = 0 (cada tag entre v6.2.0 y v6.5.0 tiene su publish en el Marketplace con versión matcheada — verificable comparando GitHub tags con `vsce show EmbedBuild.specbox-engine --json | jq .versions`).
  - Crecimiento de instalaciones medible (delta_installs_24h promedio > 0 en `marketplace-stats.jsonl`).
  - Cobertura i18n: 100% de los strings user-facing pasan por `vscode.l10n.t(...)` (verificable por `scripts/lint-extension-strings.mjs` en CI).

---

## Dependencias y riesgos

### Dependencias externas
- Cuenta Azure DevOps activa para el publisher `EmbedBuild`.
- GitHub Secrets disponibles en el repo (requiere acceso admin).
- Marketplace policy review — Microsoft revisa la primera publicación (típicamente <24h, puede tardar más si flaggea categorías o branding).

### Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Microsoft rechaza la primera publicación (branding, categorías, descripciones) | Media | Alto | Revisar [VSCode Marketplace policies](https://aka.ms/vsmarketplace-ToU) antes de publicar; tener metadata UC-636/637 conservadora y profesional. |
| `VSCE_PAT` caduca (PATs Azure DevOps máx 1 año) | Alta a largo plazo | Medio | Runbook UC-639 documenta rotación; añadir reminder a `.quality/` o a Engram. |
| Drift entre publisher name en `package.json` y owner real del PAT | Baja | Alto | UC-639 verifica el match con `vsce ls-publishers` antes del primer publish. |
| Repo URL incorrecto (`EmbedBuild/specbox-engine`) en `package.json` actual rompe badges y links al publicar | Resuelto | Bajo | UC-636 AC-02 fija explícitamente `EmbedBuild/specbox-engine` como URL canónica del repo. Publisher Marketplace sigue siendo `EmbedBuild`. |
| Usuario instala v6.2.0 desde Marketplace pero su engine local sigue en v5.x | Media | Medio | El comando `SpecBox: Health Check` ya detecta version mismatch (capacidad existente); README de UC-637 advierte. Resolución completa pertenece a la US "thin extension" v6.3.x. |
| Smoke test post-publish falla por flakiness de VSCode headless en CI | Media | Bajo | UC-640 AC-06 abre issue automático sin rollback; humano evalúa. |
| Traducción ES inconsistente o incorrecta (calidad de español neutro vs argentinismos) | Media | Bajo | Traducción manual por el mantenedor (hispanohablante nativo); revisar contra guía de estilo "español sin argentinismos" del proyecto. NO usar traducción automática para strings cortos del Command Palette. |
| Strings runtime hardcoded escapan el lint y rompen i18n | Media | Medio | UC-642 AC-04 mete `scripts/lint-extension-strings.mjs` en CI (gate del build de la extensión). Cualquier PR que añada `showInformationMessage("literal")` sin `l10n.t` falla CI. |
| Marketplace REST API rate-limita o cambia el shape de response | Baja | Medio | El cron corre 1×/día (muy lejos de cualquier rate limit). UC-643 AC-03 hace exit 0 con warning si el endpoint retorna error inesperado. Shape se documenta en `doc/runbooks/marketplace-stats.md` para detectar cambios. |
| El endpoint `extensionquery` deja de ser público / Microsoft lo gatea | Baja | Alto | Workflow falla silencioso (jsonl no se actualiza). Mitigación reactiva: migrar a scraping del HTML del portal (más frágil) o aceptar pérdida de visibilidad. No bloqueante para la funcionalidad core del Marketplace. |
| `bundle.l10n.es.json` se desincroniza de `bundle.l10n.json` (keys nuevas en EN sin traducir) | Alta a largo plazo | Bajo | Añadir test en `tests/test_l10n_parity.py` (corre en CI): falla si `bundle.l10n.json` tiene keys que no están en `bundle.l10n.es.json`. Strings sin traducción caen a EN (degradación graceful) pero el test fuerza al desarrollador a traducir antes de mergear. |

---

## Rollback plan

Si tras el primer publish v6.2.0 se detecta un problema crítico (extensión rota, ejecuta acción destructiva, leakea secret):

1. **Inmediato**: `vsce unpublish EmbedBuild.specbox-engine@6.2.0` (saca solo esa versión; las instalaciones existentes no se desinstalan).
2. **Si grave**: `vsce unpublish EmbedBuild.specbox-engine` (saca la extensión completa del Marketplace).
3. **Comunicación**: GitHub Release v6.2.0 → editar release notes con aviso; pin issue en el repo.
4. **Fix forward**: corregir + cortar v6.2.1 + republish. NO se republica la misma versión (Marketplace lo permite pero produce confusión en clientes que ya bajaron 6.2.0).

El workflow CI debe poder reproducir todo desde un repo limpio + el PAT — no debe haber estado manual.

### Rollback parcial por componente

- **Telemetría rota (UC-643)**: deshabilitar el cron temporalmente via `gh workflow disable marketplace-stats.yml`. No impacta a usuarios finales — `.quality/marketplace-stats.jsonl` simplemente para de crecer. Tool MCP `get_marketplace_stats` sigue funcionando con los datos previos.
- **i18n ES inadecuada (UC-641/642)**: borrar `package.nls.es.json` y `bundle.l10n.es.json`. La extensión cae a EN para todos los locales (fallback). Republish patch.
- **Solo el listing rompe pero la extensión funciona**: editar metadata del listing directamente vía `vsce` sin republicar el VSIX — `vsce edit EmbedBuild.specbox-engine` (algunas modificaciones requieren bump de versión).

---

## Decisiones canónicas tomadas

- **Vía A pura**: solo publish + CI sync. Sin "thin extension". Sin "Setup MCP guiado".
- **Solo VSCode Marketplace**: Open VSX queda para una US futura.
- **Lockstep estricto**: `extension.version == engine.version` siempre. Drift = blocker de release.
- **Publisher**: `EmbedBuild` (ya declarado en `package.json` actual; se mantiene).
- **License**: MIT (ya declarada en `vscode-extension/LICENSE`).

---

## Referencias

- Issue / discusión origen: conversación con el usuario 2026-05-26 sobre fricción de instalación SpecBox en VSCode.
- Engine version actual: v6.1.1 (ENGINE_VERSION.yaml).
- Extensión version actual: 5.21.1 (vscode-extension/package.json) — drift de 6 versiones.
- Documentación oficial VSCode Marketplace: https://code.visualstudio.com/api/working-with-extensions/publishing-extension
- `vsce` CLI: https://github.com/microsoft/vscode-vsce
- US relacionadas: US-CUTOVER-FOLLOWUP (v6.1.1) tocó la extensión para quitar el dashboard; esta US es independiente y la deja Marketplace-ready.

---

## Próximo paso

Una vez aprobado el PRD: invocar `/plan US-VSCODE-MARKETPLACE` para generar el plan técnico por UC (con análisis de archivos a tocar, dependencias entre UCs, orden recomendado de implementación, y los diseños Stitch si aplicara — en este caso no aplica porque no hay UI nueva).

Si querés que esta US entre directo al board `ff-ed0c02f4565a` ahora (sin pasar por `/plan` antes), puedo correr los **10 `add_uc` + ~52 `add_ac`** via MCP de FreeForm. Avisame.

---

## Resumen final del scope V1

- **10 UCs** (UC-634 → UC-643), **~42h** estimadas, target release **v6.2.0 "VSCode Marketplace"**.
- Cubre publish + CI sync + lockstep versioning + metadata pro + i18n EN/ES (listing + runtime) + telemetría Marketplace pública.
- NO incluye thin-extension refactor, Open VSX, telemetría activa con consent flow, ni Setup MCP guiado.
