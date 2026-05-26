# Plan: US-VSCODE-MARKETPLACE — Publicar la extensión SpecBox al VSCode Marketplace con sync automático al engine

> **Generado**: 2026-05-26 (por `/plan`)
> **Origen**: US-VSCODE-MARKETPLACE (FreeForm board `ff-ed0c02f4565a`)
> **PRD**: [doc/prd/US-VSCODE-MARKETPLACE_prd.md](../prd/US-VSCODE-MARKETPLACE_prd.md)
> **Release target**: v6.2.0 "VSCode Marketplace" (minor)
> **Estado**: Pendiente — listo para `/implement`
> **Estimación total**: ~42h, 10 UCs, ~52 ACs
> **Tipo**: Release infrastructure + onboarding UX (sin UI nueva)

---

## Resumen

Esta US tiene **dos productos** distintos pero acoplados que se entregan juntos en v6.2.0:

1. **Publicación al VSCode Marketplace** + **CI lockstep** — la extensión `jpsdeveloper.specbox-engine` se vuelve descubrible vía un click y queda imposible de drifear respecto al engine.
2. **i18n EN+ES** + **Telemetría de adopción** — el listing y la UI runtime son bilingües; un cron diario contra el Marketplace REST API público alimenta `.quality/marketplace-stats.jsonl` y la nueva tool MCP `get_marketplace_stats`.

Sin UI nueva → **Pasos 2.5b (VEG) y 6 (Stitch) saltados** del flujo estándar de `/plan`.

## Decisiones canónicas heredadas (Paso 0.0)

| Decisión | Valor heredado | Aplicación al plan |
|----------|---------------|---------------------|
| Stack engine | Python 3.12 (uv) + Node.js ESM (.mjs) | UC-643 tool MCP es Python; CI workflows usan Node 20 LTS; sync script en Bash + Python parser |
| Backend tracking | FreeForm `ff-ed0c02f4565a`, path absoluto a `doc/tracking/` | Plan se guarda en `doc/plans/`; UCs entran al board con `add_uc` MCP tool |
| Autopilot | equilibrado, image_budget 5€, queue off | Pre-flight gate de UC-635: `equilibrado` permite auto-confirm del bump de versión + commit, pero NO auto-tag (tagging sigue requiriendo `ask` por inviolable `destructive_action`) |
| Convenciones | PR-only a main, README bump en cada versión, tests pytest, lint vía GGA | UC-637 actualiza README raíz también; UCs 638/640/643 testean con pytest + node:test; CI corre lint via `gga run` |
| VEG | Uniforme, arquetipo Startup | **No aplica** — US sin UI. Sí aplica al copy del listing del Marketplace (UC-636: galleryBanner color/theme acorde a Startup branding) |
| Brand | SpecBox Engine by JPS | Listing del Marketplace mantiene este branding |

ℹ️ Las settings de stitch están vacías en este proyecto (engine es backend, sin UI propia) — Paso 6 saltado limpiamente.

---

## Análisis UI (Fase 0)

**NO APLICA** — US sin UI nueva.

La extensión VSCode ya tiene comandos y views registradas en `package.json` (UC-636 audita la metadata, no añade comandos nuevos). UC-642 toca strings runtime de `src/extension.ts` pero no añade widgets ni UI nueva.

---

## Visual Experience Generation

**MODO**: Desactivado (US sin UI).

No se generan archivos en `doc/veg/`. El único elemento "visual" tocado es el `galleryBanner` del listing del Marketplace (UC-636), que hereda el arquetipo Startup ya documentado en `doc/app/app_spec.md` §3.

---

## Dependencias entre UCs

Grafo de dependencias (orden de implementación recomendado):

```
                     ┌─────────────────────────────────────┐
                     │  UC-639 (publisher setup runbook)   │
                     │  ONE-TIME / HUMAN / NO-CODE         │
                     │  Puede arrancar EN PARALELO         │
                     └─────────────────────────────────────┘

  ┌── UC-634 (sync script) ───────┐
  │   foundational                │
  └────┬──────────────────────────┘
       │
       ├──→ UC-635 (release gate hook)
       │
       ├──→ UC-636 (package.json metadata) ──┐
       │                                      │
       │    UC-641 (i18n listing NLS) ────────┤
       │                                      │
       │    UC-642 (i18n runtime l10n) ───────┤
       │                                      │
       │    UC-637 (README + CHANGELOG) ──────┤
       │                                      │
       └──→ UC-638 (CI publish workflow) ←────┘
                  │
                  ├──→ UC-640 (smoke test post-publish)
                  │
                  └──→ UC-643 (Marketplace stats telemetry)
                            │ (puede arrancar antes — solo necesita listing live)
```

**Camino crítico**: UC-634 → UC-636 → UC-638. Si UC-638 está verde, el publish puede dispararse aunque UC-640/643 sigan en proceso.

**UCs paralelizables sin bloqueo**:
- UC-639 (runbook humano, no toca código).
- UC-641, UC-642 (i18n — orto­gonal al CI).
- UC-637 (README/CHANGELOG — solo depende de UC-636 para citar metadata).

---

## Fases de Implementación

Total: 10 UCs en **5 fases**.

### Fase 1 — Foundation (UC-634, UC-639)

**Objetivo**: tener el sync script funcionando + el publisher registrado en el Marketplace.

#### UC-634 — Script `sync-extension-version.sh` (4h) [AG-01 Feature Generator]

- [ ] Crear `scripts/sync-extension-version.sh` con shebang `#!/bin/bash` + `set -euo pipefail`.
- [ ] Implementar parseo de `ENGINE_VERSION.yaml` (reusar el pattern de `install.sh:11`: `grep 'version:' | head -1 | awk '{print $2}'`).
- [ ] Implementar `--check` (default): lee `vscode-extension/package.json` con `python3 -c "import json; print(json.load(open(...))['version'])"`, compara con engine version. Exit 0 si match; exit 1 + mensaje rojo si difieren.
- [ ] Implementar `--write`: reescribe `vscode-extension/package.json` usando `python3` + `json` (NO sed/regex — preserva indentación 2-space y orden de keys que ya tiene el archivo).
- [ ] `--write` también actualiza `vscode-extension/package-lock.json` top-level `version` field si existe.
- [ ] Tests: `scripts/tests/test-sync-extension-version.sh` con 3 casos (synced, drift+check, drift+write). Usa fixture `/tmp/specbox-test-XXX` con `ENGINE_VERSION.yaml` + `package.json` mockeados.
- [ ] Verificar: correr `bash scripts/sync-extension-version.sh --check` desde la raíz del repo. Debe devolver exit 1 hoy (drift v5.21.1 vs v6.1.1). Tras `--write`, exit 0.
- **Tiempo estimado**: 4h
- **Archivos creados**: `scripts/sync-extension-version.sh`, `scripts/tests/test-sync-extension-version.sh`
- **Archivos modificados**: ninguno
- **AC coverage**: AC-01 → AC-05 del PRD UC-634

#### UC-639 — Runbook de publisher setup + PAT (2h) [AG-01 + HUMANO]

- [ ] Crear `doc/runbooks/vscode-marketplace-publisher-setup.md`.
- [ ] Documentar: pasos para crear cuenta Azure DevOps (https://aex.dev.azure.com/), crear org `jps-marketplace` (o reusar existente si ya hay), generar PAT con scope `Marketplace > Manage` y expiry 1 año.
- [ ] Documentar: `npm install -g @vscode/vsce`, `vsce create-publisher jpsdeveloper` (one-time), `vsce login jpsdeveloper` (interactivo, ingresar el PAT).
- [ ] Documentar: añadir `VSCE_PAT` a GitHub Secrets vía `gh secret set VSCE_PAT --repo EmbedBuild/specbox-engine`.
- [ ] Sección "Rotación del PAT": calendar reminder antes de expiry, `vsce login jpsdeveloper` con el nuevo PAT, `gh secret set VSCE_PAT` para actualizar el secret. NO requiere republish.
- [ ] Sección "Verificación": `vsce ls-publishers` debe listar `jpsdeveloper`; `vsce show jpsdeveloper.specbox-engine` tras el primer publish debe responder OK.
- [ ] Sección "Unpublish de emergencia": `vsce unpublish jpsdeveloper.specbox-engine@X.Y.Z` (versión específica) vs `vsce unpublish jpsdeveloper.specbox-engine` (extensión completa). Advertir: propagación tarda horas.
- [ ] **EJECUCIÓN HUMANA**: el usuario corre los pasos del runbook one-time. Confirmar con captura/screenshot que el secret existe en GitHub repo settings.
- **Tiempo estimado**: 2h doc + ~30min ejecución humana
- **Archivos creados**: `doc/runbooks/vscode-marketplace-publisher-setup.md`
- **Bloqueante para**: UC-638 publish (sin `VSCE_PAT`, el workflow falla)
- **AC coverage**: AC-01 → AC-05 del PRD UC-639

### Fase 2 — Metadata + Versionado (UC-635, UC-636)

**Objetivo**: el package.json está pulido para Marketplace; `/release` no permite tagear con drift.

#### UC-635 — Hook de release: gate de version sync (3h) [AG-01]

- [ ] Editar `.claude/skills/release/SKILL.md`: nuevo paso entre el "0.2 Calcular nueva version" y el paso de actualizar `ENGINE_VERSION.yaml`. Llamarlo "0.2.5 Pre-flight: VSCode extension version sync".
- [ ] El paso ejecuta `bash scripts/sync-extension-version.sh --check`. Si exit 0, sigue.
- [ ] Si exit != 0: el skill muestra al usuario el output de `--check` y ofrece dos opciones:
    - `[a]` autofix: corre `--write`, hace `git add vscode-extension/package.json vscode-extension/package-lock.json`, hace commit `chore(vscode-ext): sync version to v{N}` (commit separado, ANTES de los commits de release notes y tag).
    - `[b]` abort: termina el skill, el usuario debe resolver el drift manualmente.
- [ ] **No hay opción `[c] ignore`** — el SKILL.md lo dice explícitamente: "Tagear con drift es inviolable. No se permite skip".
- [ ] Documentar en el SKILL.md cómo simular drift para testear: `python3 -c "import json; p=json.load(open('vscode-extension/package.json')); p['version']='0.0.1'; json.dump(p, open('vscode-extension/package.json','w'), indent=2)"`, luego correr `/release` y verificar que el skill atrapa el drift.
- **Tiempo estimado**: 3h
- **Archivos modificados**: `.claude/skills/release/SKILL.md`
- **AC coverage**: AC-01 → AC-05 del PRD UC-635
- **Dependencia**: UC-634 (sync script existe)

#### UC-636 — Metadata Marketplace en `package.json` (3h) [AG-01]

- [ ] Audit del `vscode-extension/package.json` actual contra los campos requeridos por VSCode Marketplace (https://code.visualstudio.com/api/references/extension-manifest).
- [ ] Verificar: `displayName`, `description` (ambos pasarán a NLS keys en UC-641), `publisher: "jpsdeveloper"`, `license: "MIT"`, `engines.vscode: "^1.85.0"` (current minimum), `icon: "media/icon.png"` (verificar ≥128×128 — usar `file media/icon.png` y `identify`).
- [ ] Actualizar `categories`: añadir `"Other"` si no está; considerar `"Programming Languages"` (no aplica), `"Snippets"` (no aplica), mantener `["AI", "Other"]`.
- [ ] Actualizar `keywords`: `["claude", "claude-code", "agentic", "AI", "MCP", "hooks", "skills", "automation", "spec-driven", "onboarding", "BDD", "specbox", "engram"]` (los actuales). Verificar relevancia, sin pad keywords.
- [ ] Actualizar `repository.url`, `bugs.url`, `homepage` a `https://github.com/EmbedBuild/specbox-engine[/issues|#readme]`. (El `repository.url` ya está corregido en una iteración previa).
- [ ] Añadir `galleryBanner.color` (sugerido: `"#1a1a2e"` o color del brand kit) y `galleryBanner.theme: "dark"`.
- [ ] Añadir `qna: false` (deshabilita Q&A en Marketplace listing — usamos GitHub issues vía `bugs.url`).
- [ ] Añadir `pricing: "Free"`.
- [ ] Verificar `vscode:prepublish` script existe en `scripts.vscode:prepublish` y compila TS: `"vscode:prepublish": "tsc -p ./"`.
- [ ] Correr `vsce ls --tree` localmente desde `vscode-extension/` — debe terminar sin errores ni warnings sobre missing fields.
- [ ] Correr `vsce package --no-yarn` localmente — debe generar `specbox-engine-X.Y.Z.vsix` sin warnings.
- **Tiempo estimado**: 3h
- **Archivos modificados**: `vscode-extension/package.json`
- **AC coverage**: AC-01 → AC-05 del PRD UC-636

### Fase 3 — i18n (UC-641, UC-642)

**Objetivo**: listing y runtime UI bilingües EN+ES.

#### UC-641 — i18n del listing del Marketplace via NLS (4h) [AG-01]

- [ ] Crear `vscode-extension/package.nls.json` (EN, fallback) con keys planas:
    ```json
    {
      "extension.displayName": "SpecBox Engine — Agentic Dev for Claude Code",
      "extension.description": "Install and manage SpecBox Engine: skills, hooks, MCP servers, and Engram memory for Claude Code agentic development.",
      "command.install.title": "SpecBox: Install Engine",
      "command.healthCheck.title": "SpecBox: Health Check",
      "command.onboard.title": "SpecBox: Onboard Project",
      "command.showStatus.title": "SpecBox: Show Status",
      "command.configureMcp.title": "SpecBox: Configure MCP Servers",
      "view.status.title": "Status"
    }
    ```
- [ ] Crear `vscode-extension/package.nls.es.json` (ES) con traducciones (español neutro España, tuteo, NO argentinismos):
    ```json
    {
      "extension.displayName": "SpecBox Engine — Desarrollo Agéntico para Claude Code",
      "extension.description": "Instala y gestiona SpecBox Engine: skills, hooks, servidores MCP y memoria Engram para desarrollo agéntico con Claude Code.",
      "command.install.title": "SpecBox: Instalar Engine",
      "command.healthCheck.title": "SpecBox: Comprobar Salud",
      "command.onboard.title": "SpecBox: Inicializar Proyecto",
      "command.showStatus.title": "SpecBox: Ver Estado",
      "command.configureMcp.title": "SpecBox: Configurar Servidores MCP",
      "view.status.title": "Estado"
    }
    ```
- [ ] Editar `vscode-extension/package.json`: reemplazar literales por referencias NLS:
    - `"displayName": "%extension.displayName%"`
    - `"description": "%extension.description%"`
    - Cada `commands[].title` → `"%command.<id>.title%"`
    - Cada `views.specbox[].name` → `"%view.status.title%"` (o key específica si hay más views)
- [ ] Smoke test local:
    - `code --locale=es` → Command Palette debe mostrar "SpecBox: Instalar Engine".
    - `code --locale=en` → debe mostrar "SpecBox: Install Engine".
    - `code --locale=fr` → fallback a EN (esperado, no traducimos a FR).
- [ ] Documentar en `vscode-extension/README.md` (UC-637): cómo añadir un locale nuevo (copiar package.nls.{lang}.json + bundle.l10n.{lang}.json + test).
- **Tiempo estimado**: 4h
- **Archivos creados**: `vscode-extension/package.nls.json`, `vscode-extension/package.nls.es.json`
- **Archivos modificados**: `vscode-extension/package.json`
- **AC coverage**: AC-01 → AC-05 del PRD UC-641

#### UC-642 — i18n de strings runtime via `vscode-l10n` (6h) [AG-01]

- [ ] Auditar `vscode-extension/src/*.ts` (extension.ts, install.ts, health.ts, mcp.ts, onboard.ts, statusbar.ts, updater.ts) buscando todos los strings user-facing:
    - `vscode.window.showInformationMessage(...)`
    - `vscode.window.showErrorMessage(...)`
    - `vscode.window.showWarningMessage(...)`
    - `vscode.window.showQuickPick(...)` labels
    - `vscode.window.showInputBox(...)` prompts
    - `outputChannel.appendLine(...)` user-facing messages
    - `vscode.window.createOutputChannel(...)` channel name
    - Status bar text
- [ ] Inventariar en un archivo temporal `vscode-extension/.l10n-audit.txt` (luego se borra). Estimado: ~40-60 strings.
- [ ] Editar `vscode-extension/package.json` añadiendo `"l10n": "./l10n"` al root.
- [ ] Crear `vscode-extension/l10n/bundle.l10n.json` (EN — keys son los strings EN literales, convención `vscode-l10n`):
    ```json
    {
      "Engine installed successfully": "Engine installed successfully",
      "Engine not found at {0}": "Engine not found at {0}",
      "Run health check": "Run health check",
      ...
    }
    ```
- [ ] Crear `vscode-extension/l10n/bundle.l10n.es.json` (ES) con traducciones de todas las keys de EN.
- [ ] Refactorizar `src/*.ts`: cada string user-facing pasa por `vscode.l10n.t("...")`:
    - Antes: `vscode.window.showInformationMessage("Engine installed successfully")`
    - Después: `vscode.window.showInformationMessage(vscode.l10n.t("Engine installed successfully"))`
    - Con placeholders: `vscode.l10n.t("Engine not found at {0}", enginePath)` (vscode-l10n usa `{0}`, `{1}` para args).
- [ ] Crear `scripts/lint-extension-strings.mjs`:
    - Escanea `vscode-extension/src/**/*.ts`.
    - Busca patrones `vscode.window.show(Info|Error|Warning)Message\("([^"]+)"` (literal sin l10n.t).
    - Falla con exit 1 si encuentra alguno + lista archivo:línea:string.
    - Allowlist: comentarios, console.log/error (no user-facing), strings de prueba en archivos `*.test.ts`.
- [ ] Integrar lint en el workflow CI (UC-638 AC-03 ya lo referencia como gate del build).
- [ ] Smoke test: `code --locale=es` + abrir VSCode con la extensión → ejecutar `SpecBox: Comprobar Salud` → la notificación de éxito sale en español. Con `--locale=en` → en inglés.
- [ ] Verificar engine version compatibility: `vscode.l10n` requiere VSCode ≥1.86 (febrero 2024). El `package.json` actual declara `^1.85.0` — bump a `^1.86.0` (UC-636 lo hace o se hace acá si el orden lo permite).
- **Tiempo estimado**: 6h
- **Archivos creados**: `vscode-extension/l10n/bundle.l10n.json`, `vscode-extension/l10n/bundle.l10n.es.json`, `scripts/lint-extension-strings.mjs`
- **Archivos modificados**: `vscode-extension/package.json` (campo `l10n`, `engines.vscode` bump), todos los `vscode-extension/src/*.ts` con strings user-facing
- **AC coverage**: AC-01 → AC-05 del PRD UC-642
- **Riesgo**: el bump de `engines.vscode` a ≥1.86 puede excluir usuarios con VSCode antiguo. Aceptable: 1.86 es de feb 2024, >2 años de antigüedad.

### Fase 4 — Docs + Branding (UC-637)

**Objetivo**: README listo para Marketplace + CHANGELOG sincronizado.

#### UC-637 — README + CHANGELOG de la extensión (4h) [AG-01]

- [ ] Reescribir `vscode-extension/README.md` (EN canon) para audiencia Marketplace:
    - **Header**: badges (versión Marketplace, installs, license, engine compat). Usar shields.io:
        - `![Version](https://img.shields.io/vscode-marketplace/v/jpsdeveloper.specbox-engine)`
        - `![Installs](https://img.shields.io/vscode-marketplace/i/jpsdeveloper.specbox-engine)`
        - `![Rating](https://img.shields.io/vscode-marketplace/r/jpsdeveloper.specbox-engine)`
        - `![License](https://img.shields.io/badge/license-MIT-green)`
    - **Sección "What is SpecBox Engine?"**: 2-3 párrafos — qué es, qué resuelve, cuándo usarlo.
    - **Sección "Features"**: los 5 comandos con 1-2 líneas cada uno + screenshot del Command Palette mostrando los comandos.
    - **Sección "Requirements"**: Claude Code CLI (link a Anthropic) o extensión Claude para VSCode.
    - **Sección "Quick Start"**: 3 pasos numerados con código:
        1. Install: `Command Palette → "Extensions: Install Extensions" → buscar "SpecBox"`.
        2. Run: `Command Palette → "SpecBox: Install Engine"`.
        3. Verify: `Command Palette → "SpecBox: Health Check"`.
    - **Sección "Available Languages"**: "English (default), Español". Link a `README.es.md`.
    - **Sección "Troubleshooting"**: 3-4 issues comunes (Claude Code not detected, MCP server unreachable, version mismatch entre ext y engine instalado).
    - **Footer**: link al engine repo (`EmbedBuild/specbox-engine`), CHANGELOG, license.
- [ ] Crear `vscode-extension/README.es.md`: traducción completa del README.md. Link cruzado en el header de ambos (`English | [Español](README.es.md)` y viceversa).
- [ ] Generar 1+ screenshot para el README:
    - Captura del Command Palette con `SpecBox:` filtrado, mostrando los 5 comandos.
    - Guardar en `vscode-extension/media/screenshots/command-palette.png` (resolución 1280×720 mínimo).
- [ ] Crear `vscode-extension/CHANGELOG.md` (EN únicamente — convención npm/vscode):
    - Formato Keep a Changelog (https://keepachangelog.com).
    - Entry `[6.2.0] - 2026-XX-XX` con sección "Added": "First Marketplace release. Lockstep versioning with SpecBox Engine. EN+ES localization. Marketplace stats telemetry."
    - Entry `[Unreleased]` vacío arriba para futuras entries.
- [ ] Actualizar `README.md` raíz del repo `specbox-engine/`:
    - Nueva sección "Instalación → VSCode (Marketplace)" como vía **recomendada**.
    - Mantener la sección actual de `git clone + ./install.sh` como "Alternativa para devs del engine".
    - El bump del README raíz por release lo hace `/release` skill (decisión canónica del proyecto), pero esta entrada se mete una sola vez en v6.2.0.
- **Tiempo estimado**: 4h
- **Archivos creados**: `vscode-extension/README.es.md`, `vscode-extension/CHANGELOG.md`, `vscode-extension/media/screenshots/command-palette.png`
- **Archivos modificados**: `vscode-extension/README.md` (rewrite), `README.md` (raíz, sección instalación)
- **AC coverage**: AC-01 → AC-05 del PRD UC-637
- **Dependencia**: UC-636 (metadata final del package.json) para que los badges shields.io resuelvan correctamente.

### Fase 5 — CI + Telemetría + Smoke (UC-638, UC-643, UC-640)

**Objetivo**: bucle automatizado completo de publish + observabilidad.

⚠️ **Hallazgo**: `.github/workflows/` **no existe** en el repo actualmente. UC-638 es el primer workflow CI del proyecto. Esto añade ~30 min de setup (crear el dir, verificar branch protection rules).

#### UC-638 — Workflow CI: publish al Marketplace en tag (6h) [AG-01]

- [ ] Crear `.github/workflows/` si no existe.
- [ ] Crear `.github/workflows/publish-vscode-extension.yml`:
    ```yaml
    name: Publish VSCode Extension
    on:
      push:
        tags: ['v*.*.*']
      workflow_dispatch:  # manual trigger for emergencies
    jobs:
      publish:
        runs-on: ubuntu-latest
        permissions:
          contents: write  # for uploading vsix to release
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-node@v4
            with: { node-version: '20' }
          - name: Install vsce
            run: npm install -g @vscode/vsce
          - name: Verify version sync (defense in depth)
            run: bash scripts/sync-extension-version.sh --check
          - name: Lint extension strings (i18n gate)
            run: node scripts/lint-extension-strings.mjs
          - name: Build extension
            working-directory: vscode-extension
            run: |
              npm ci
              npm run vscode:prepublish
          - name: Package VSIX
            working-directory: vscode-extension
            run: vsce package -o specbox-engine-${GITHUB_REF_NAME#v}.vsix
          - name: Publish to Marketplace
            working-directory: vscode-extension
            run: vsce publish --pat "${{ secrets.VSCE_PAT }}"
          - name: Upload VSIX to GitHub Release
            uses: softprops/action-gh-release@v2
            with:
              files: vscode-extension/specbox-engine-*.vsix
              fail_on_unmatched_files: true
    ```
- [ ] Verificar que `secrets.VSCE_PAT` está configurado (UC-639 ya lo dejó listo).
- [ ] Branch protection rule en `main`: workflow no debe poder ser deshabilitado sin admin review (esto se configura post-merge, fuera del scope del UC pero documentar en runbook UC-639).
- [ ] Probar el workflow con `workflow_dispatch` manual contra un tag pre-release (`v6.2.0-rc1`) para validar end-to-end sin publicar al Marketplace público (vsce permite `--pre-release` flag).
- **Tiempo estimado**: 6h
- **Archivos creados**: `.github/workflows/publish-vscode-extension.yml`
- **AC coverage**: AC-01 → AC-06 del PRD UC-638
- **Dependencias**: UC-634 (script), UC-639 (PAT), UC-636 (package.json válido), UC-642 (lint script)

#### UC-643 — Telemetría Marketplace API (6h) [AG-01 + AG-04 (tests)]

- [ ] Crear `scripts/fetch-marketplace-stats.mjs`:
    - Node 20, zero-deps (usar `fetch` nativo + `fs/promises`).
    - POST a `https://marketplace.visualstudio.com/_apis/public/gallery/extensionquery` con headers `Accept: application/json;api-version=7.2-preview.1` + `Content-Type: application/json` + body:
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
    - Parsear response: `results[0].extensions[0].statistics[]` (array de `{statisticName, value}`).
    - Extraer: `install`, `updateCount`, `averagerating`, `ratingcount`, `trendingdaily`, `trendingmonthly`, `trendingweekly`.
    - Calcular `delta_installs_24h` leyendo la última entry de `.quality/marketplace-stats.jsonl` y restando.
    - Appendear nueva línea JSON: `{date: "2026-XX-XXTHH:MM:SSZ", version: "X.Y.Z" (de extensions[0].versions[0].version), installs, downloads: updateCount, avg_rating, rating_count, trending_daily, trending_monthly, delta_installs_24h}`.
    - **Exit 0 con warning** si extensions[] está vacío (extensión aún no publicada — válido en pre-v6.2.0).
- [ ] Crear `.github/workflows/marketplace-stats.yml`:
    ```yaml
    name: Marketplace Stats Snapshot
    on:
      schedule: [{cron: '0 6 * * *'}]  # daily 06:00 UTC
      workflow_dispatch:
    jobs:
      snapshot:
        runs-on: ubuntu-latest
        permissions:
          contents: write
        steps:
          - uses: actions/checkout@v4
            with: { ref: main }
          - uses: actions/setup-node@v4
            with: { node-version: '20' }
          - run: node scripts/fetch-marketplace-stats.mjs
          - name: Commit stats
            run: |
              if [ -n "$(git status --porcelain .quality/marketplace-stats.jsonl)" ]; then
                git config user.name "specbox-stats-bot"
                git config user.email "noreply@anthropic.com"
                git add .quality/marketplace-stats.jsonl
                git commit -m "chore(stats): marketplace stats $(date -u +%Y-%m-%d)"
                git push origin main
              fi
    ```
- [ ] Crear `server/tools/marketplace.py`:
    - Imports estándar (`from __future__ import annotations`, `Optional`, `pydantic`).
    - Tool `get_marketplace_stats(window_days: int = 30, jsonl_content: Optional[str] = None)`:
        - **MCP Path Contract v6.0.1**: usa `jsonl_content` (content-passing). Si está vacío, intenta leer `.quality/marketplace-stats.jsonl` del CWD del MCP server (fallback in-process).
        - Parsea cada línea JSON, filtra por `date >= now() - window_days`.
        - Retorna:
            ```python
            {
              "total_installs": int,
              "total_downloads": int,
              "avg_rating": float,
              "rating_count": int,
              "install_growth_pct": float,  # (last - first) / first * 100
              "daily_series": [{"date": str, "installs": int, "delta": int}],
              "current_trending_rank": {"daily": int, "weekly": int, "monthly": int},
              "window_days": int,
              "entries_count": int
            }
            ```
        - Caso edge: jsonl vacío o sin entries en la ventana → retorna `{"status": "no_data_yet", "reason": "extension_not_published_or_no_stats", "window_days": window_days}`.
    - Registrar la tool en `server/server.py` (o en el módulo de carga de tools — verificar patrón del proyecto en `server/tools/__init__.py`).
- [ ] Crear `tests/test_marketplace_tool.py`:
    - Fixture: 30 entries simuladas en `tmp_path/marketplace-stats.jsonl` con installs crecientes (10 → 250).
    - Test 1: `get_marketplace_stats(window_days=30, jsonl_content=fixture)` → retorna `total_installs=250`, `install_growth_pct≈2400.0`, `daily_series` tiene 30 entries.
    - Test 2: `window_days=7` → solo últimas 7 entries, métricas recalculadas.
    - Test 3: jsonl vacío → retorna `{"status": "no_data_yet", ...}`.
    - Test 4: jsonl con líneas malformadas → skipea y warnea, no crashea.
- [ ] Crear `doc/runbooks/marketplace-stats.md`:
    - Cómo funciona el endpoint `extensionquery` + qué significa `flags=914` (suma bitwise: 2=IncludeVersions + 16=IncludeStatistics + 128=IncludeCategoryAndTags + 256=IncludeFiles + 512=IncludeVersionProperties = 914).
    - Rate limiting observado (no documentado oficialmente; >10 req/min puede 429).
    - Cómo forzar un snapshot manual: `gh workflow run marketplace-stats.yml`.
    - **Sección "Privacy & data sources"**: zero PII, solo agregados públicos del listing, NO se ejecuta nada en el cliente del usuario.
- **Tiempo estimado**: 6h
- **Archivos creados**: `scripts/fetch-marketplace-stats.mjs`, `.github/workflows/marketplace-stats.yml`, `server/tools/marketplace.py`, `tests/test_marketplace_tool.py`, `doc/runbooks/marketplace-stats.md`
- **Archivos modificados**: `server/server.py` o `server/tools/__init__.py` (registro de la tool nueva)
- **AC coverage**: AC-01 → AC-07 del PRD UC-643
- **Dependencia**: la primera entry útil del jsonl requiere que la extensión esté publicada (UC-638 ejecutado). Pero el workflow se puede crear antes; simplemente loggea "no_data_yet" hasta el primer publish.

#### UC-640 — Smoke test post-publish con matrix locale (4h) [AG-04 QA]

- [ ] Crear `.github/workflows/smoke-test-marketplace.yml`:
    ```yaml
    name: Smoke Test Marketplace Install
    on:
      workflow_run:
        workflows: ["Publish VSCode Extension"]
        types: [completed]
        branches: [main]
      workflow_dispatch:
    jobs:
      smoke:
        if: ${{ github.event.workflow_run.conclusion == 'success' || github.event_name == 'workflow_dispatch' }}
        runs-on: ubuntu-latest
        strategy:
          matrix:
            locale: [en, es]
        steps:
          - uses: actions/checkout@v4
          - name: Install VSCode CLI
            run: |
              wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
              sudo install -o root -g root -m 644 microsoft.gpg /etc/apt/trusted.gpg.d/
              sudo sh -c 'echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/trusted.gpg.d/microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list'
              sudo apt update && sudo apt install -y code xvfb
          - name: Install extension from Marketplace
            run: |
              xvfb-run code --install-extension jpsdeveloper.specbox-engine --force
              code --list-extensions --show-versions | grep jpsdeveloper.specbox-engine
          - name: Verify version matches tag
            run: |
              INSTALLED=$(code --list-extensions --show-versions | grep jpsdeveloper.specbox-engine | cut -d@ -f2)
              ENGINE_VER=$(grep '^version:' ENGINE_VERSION.yaml | awk '{print $2}')
              if [ "$INSTALLED" != "$ENGINE_VER" ]; then
                echo "VERSION MISMATCH: installed=$INSTALLED, engine=$ENGINE_VER"; exit 1
              fi
          - name: Create dummy workspace and verify activation
            env:
              LOCALE: ${{ matrix.locale }}
            run: |
              mkdir -p /tmp/specbox-smoke
              cp ENGINE_VERSION.yaml /tmp/specbox-smoke/
              # Run code with locale, list commands, check for SpecBox: prefix
              xvfb-run code --locale=$LOCALE --extensionDevelopmentPath=/dev/null /tmp/specbox-smoke &
              sleep 10
              # Use code --status or vscode test runner to verify activation
              # (concrete impl: write a small `vscode-test` script that lists commands)
      report-failure:
        needs: smoke
        if: failure()
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - name: Open issue
            uses: actions/github-script@v7
            with:
              script: |
                github.rest.issues.create({
                  owner: context.repo.owner,
                  repo: context.repo.repo,
                  title: `Marketplace smoke test failed: ${context.payload.workflow_run?.head_branch || 'manual'}`,
                  labels: ['marketplace-smoke-fail'],
                  body: `Smoke test failed. Workflow run: ${context.payload.workflow_run?.html_url || 'N/A'}`
                })
    ```
- [ ] El step "Create dummy workspace and verify activation" es el más frágil — el plan inicial usa `xvfb` + heuristic checks. Si la flakiness es alta, considerar reemplazar por `@vscode/test-electron` con un script de prueba dedicado en `vscode-extension/src/test/smoke.ts`.
- [ ] Documentar en `doc/runbooks/vscode-marketplace-publisher-setup.md` (UC-639) cómo correr el smoke test manualmente: `gh workflow run smoke-test-marketplace.yml`.
- **Tiempo estimado**: 4h
- **Archivos creados**: `.github/workflows/smoke-test-marketplace.yml`
- **AC coverage**: AC-01 → AC-06 del PRD UC-640
- **Dependencia**: UC-638 (workflow de publish debe existir para que el `workflow_run` trigger funcione).
- **Riesgo conocido**: VSCode headless en GitHub Actions es históricamente flaky. AC-06 ya cubre el fallback (open issue, no rollback automático). Aceptable.

---

## Comandos Finales (verificación cross-UC)

Tras completar las 5 fases:

```bash
# Versión sincronizada
bash scripts/sync-extension-version.sh --check
# → exit 0

# Lint i18n
node scripts/lint-extension-strings.mjs
# → exit 0

# Build local
cd vscode-extension && npm ci && npm run vscode:prepublish && vsce package
# → genera specbox-engine-6.2.0.vsix sin warnings

# Tests Python
pytest tests/test_marketplace_tool.py -v
# → 4 passed

# Workflow CI local (act)
act -W .github/workflows/publish-vscode-extension.yml -j publish --dry-run

# Verificar branding del listing tras el primer publish
vsce show jpsdeveloper.specbox-engine --json | jq '.displayName, .description, .versions[0].version'
```

---

## Alternativas y Tradeoffs

| Decisión | Opción elegida | Alternativa descartada | Razón |
|----------|---------------|------------------------|-------|
| Telemetría | Marketplace REST API + jsonl (cron diario) | Application Insights con opt-in en la extensión | Privacy-clean, zero consent flow, datos públicos suficientes para visibilidad de adopción. Telemetría activa queda para una US futura si el dato agregado del Marketplace no basta. |
| i18n runtime | `vscode.l10n` (oficial, VSCode ≥1.86) | `vscode-nls` legacy | `vscode.l10n` es el reemplazo oficial desde 2024. API más simple, sin necesidad de loader factory. Bump de `engines.vscode` aceptable. |
| Versionado | Lockstep estricto (`ext.version == engine.version`) | Semver independiente con compat matrix | Ya tenemos un release cadence pequeño y unificado; matriz de compat es overhead innecesario. Decidido por el usuario. |
| Distribución | Solo VSCode Marketplace en V1 | VSCode Marketplace + Open VSX en V1 | Cursor, VSCode Insiders y la mayoría de forks leen del Marketplace transparentemente. Open VSX cubre VSCodium/Gitpod/Theia — minoritario. Diferido. |
| Refactor extensión | Mantener "fat" (embebe recursos) | "Thin extension" (descarga engine matching desde GitHub al activar) | Thin extension es un refactor arquitectural sustancial. Diferido a US v6.3.x para no inflar v6.2.0. |
| Publisher Marketplace | `jpsdeveloper` (cuenta personal) | `EmbedBuild` (org GitHub) | Microsoft Marketplace tiene su propio sistema de publisher; reutilizamos la cuenta personal. Es el patrón estándar (la mayoría de orgs en GitHub tienen publisher personal en el Marketplace). |
| Smoke test framework | `xvfb` + `code` CLI headless | `@vscode/test-electron` con suite formal | Implementación más simple para V1. Si flakiness > 20%, migrar en una US de seguimiento. |

---

## Archivos a Crear/Modificar

```
specbox-engine/
├── scripts/
│   ├── sync-extension-version.sh                       # CREAR (UC-634)
│   ├── fetch-marketplace-stats.mjs                     # CREAR (UC-643)
│   ├── lint-extension-strings.mjs                      # CREAR (UC-642)
│   └── tests/
│       └── test-sync-extension-version.sh              # CREAR (UC-634)
│
├── vscode-extension/
│   ├── package.json                                    # MOD (UC-634/636/641/642)
│   ├── package-lock.json                               # MOD (UC-634 escribe version)
│   ├── package.nls.json                                # CREAR (UC-641, EN)
│   ├── package.nls.es.json                             # CREAR (UC-641, ES)
│   ├── README.md                                       # REWRITE (UC-637, EN canon)
│   ├── README.es.md                                    # CREAR (UC-637, ES)
│   ├── CHANGELOG.md                                    # CREAR (UC-637)
│   ├── l10n/
│   │   ├── bundle.l10n.json                            # CREAR (UC-642, EN)
│   │   └── bundle.l10n.es.json                         # CREAR (UC-642, ES)
│   ├── media/
│   │   └── screenshots/
│   │       └── command-palette.png                     # CREAR (UC-637)
│   └── src/
│       ├── extension.ts                                # MOD (UC-642, l10n.t wrapping)
│       ├── install.ts                                  # MOD (UC-642)
│       ├── health.ts                                   # MOD (UC-642)
│       ├── mcp.ts                                      # MOD (UC-642)
│       ├── onboard.ts                                  # MOD (UC-642)
│       ├── statusbar.ts                                # MOD (UC-642)
│       └── updater.ts                                  # MOD (UC-642)
│
├── server/
│   ├── server.py                                       # MOD (UC-643 registra tool)
│   └── tools/
│       └── marketplace.py                              # CREAR (UC-643)
│
├── tests/
│   └── test_marketplace_tool.py                        # CREAR (UC-643)
│
├── .github/
│   └── workflows/                                      # CREAR DIR
│       ├── publish-vscode-extension.yml                # CREAR (UC-638)
│       ├── marketplace-stats.yml                       # CREAR (UC-643)
│       └── smoke-test-marketplace.yml                  # CREAR (UC-640)
│
├── doc/
│   ├── runbooks/
│   │   ├── vscode-marketplace-publisher-setup.md       # CREAR (UC-639)
│   │   └── marketplace-stats.md                        # CREAR (UC-643)
│   └── plans/
│       └── US-VSCODE-MARKETPLACE_plan.md               # ESTE ARCHIVO
│
├── .claude/
│   └── skills/
│       └── release/
│           └── SKILL.md                                # MOD (UC-635, pre-flight gate)
│
└── README.md                                           # MOD (UC-637, sección Instalación)
```

**Total**: 19 archivos creados, 12 archivos modificados.

---

## Mapeo a Agentes

| UC | Agente | Razón |
|----|--------|-------|
| UC-634 | AG-01 Feature Generator | Script Bash + tests |
| UC-635 | AG-01 | Edición del SKILL.md del release flow |
| UC-636 | AG-01 | JSON metadata, sin lógica |
| UC-637 | AG-01 | Markdown + traducción + screenshot |
| UC-638 | AG-01 | YAML CI |
| UC-639 | AG-01 + HUMANO | Markdown + ejecución one-time del setup |
| UC-640 | AG-04 QA Validation | Smoke test workflow CI |
| UC-641 | AG-01 | JSON i18n + edits a package.json |
| UC-642 | AG-01 | Refactor TS + bundles + linter |
| UC-643 | AG-01 + AG-04 | Tool MCP Python + tests + workflow CI |

No requiere AG-02 (UI/UX), AG-03 (DB), AG-05 (n8n), AG-06 (design), AG-07 (Apps Script). AG-08 (quality auditor) corre automáticamente en `/implement`. AG-09a/b (acceptance) corren al cerrar cada UC.

---

## Stitch Designs

**stitch_designs**: N/A (US sin pantallas).

---

## Pipeline Integrity Notes

- **Spec-guard**: cada UC requiere `start_uc` antes de tocar código en `vscode-extension/src/` o `server/tools/`. Hooks bloquearán Write/Edit sin UC activo.
- **Branch-guard**: trabajo en ramas `feature/UC-634-sync-script`, `feature/UC-635-release-gate`, etc. NO push directo a main (decisión canónica).
- **Pre-commit-lint**: GGA correrá lint en cada commit; archivos `.mjs` y `.ts` modificados se validan.
- **E2E-gate**: no aplica (sin pantallas E2E).
- **Quality-first-guard**: cada UC debe `Read` los archivos antes de editar (especialmente UC-636 sobre `package.json`, UC-642 sobre los `src/*.ts`).
- **No-bypass-guard**: bajo presión del workflow CI fallando, NO usar `--no-verify` ni `push --force`. Fix the root cause.

---

## Métricas de éxito post-implementación

Replicadas del PRD para tracking en `/implement`:

- ✅ Workflow `publish-vscode-extension.yml` corre verde en tag `v6.2.0-rc1` (pre-release test).
- ✅ `vsce show jpsdeveloper.specbox-engine` retorna metadata válida post-publish.
- ✅ Smoke test matrix `[en, es]` verde en el primer publish real.
- ✅ `.quality/marketplace-stats.jsonl` tiene al menos 1 entry tras el primer cron diario.
- ✅ `get_marketplace_stats(window_days=7)` retorna `{"status": "ok", ...}` o `{"status": "no_data_yet", ...}` válido.
- ✅ Acceptance Engine: 52 ACs verdes (AG-09b ACCEPTED para los 10 UCs).
- ✅ Definition Quality Gate (Paso 2.5 de /prd): todos los ACs especifican criterio medible.

---

## Riesgos durante implementación

Replicados del PRD con énfasis en lo accionable durante `/implement`:

| Riesgo | UC afectado | Mitigación en /implement |
|--------|-------------|--------------------------|
| `VSCE_PAT` no configurado al llegar a UC-638 | UC-638 | UC-639 es bloqueante. Verificar `gh secret list` antes de empezar UC-638. |
| Smoke test VSCode headless flaky en CI | UC-640 | AC-06 abre issue, no rollback. Aceptar 1-2 retries manual via `gh workflow run`. |
| Microsoft tarda >24h en aprobar primer publish | UC-638 | El workflow es síncrono, falla rápido si el approve está pendiente. Re-correr cuando se aprueba. |
| Traducción ES inconsistente | UC-641, UC-642 | Revisión humana del mantenedor antes de mergear cada UC. NO traducción automática. |
| Marketplace API responde 404 (extension no listada aún) | UC-643 | Primera ejecución del cron tras v6.2.0; ANTES → `no_data_yet` esperado. |
| `bundle.l10n.es.json` drift de `bundle.l10n.json` | UC-642 | Test `tests/test_l10n_parity.py` (añadido como parte de UC-642 AC-04) corre en CI. |

---

## Referencias

- **PRD**: [doc/prd/US-VSCODE-MARKETPLACE_prd.md](../prd/US-VSCODE-MARKETPLACE_prd.md)
- **Canónicos**: [doc/app/app_prd.md](../app/app_prd.md), [doc/app/app_spec.md](../app/app_spec.md)
- **VSCode Marketplace docs**: https://code.visualstudio.com/api/working-with-extensions/publishing-extension
- **vsce CLI**: https://github.com/microsoft/vscode-vsce
- **vscode-l10n**: https://github.com/microsoft/vscode-l10n
- **Marketplace REST API**: https://github.com/microsoft/vscode-vsce/blob/main/src/show.ts (referencia no oficial del shape del response)
- **Engine version actual**: v6.1.1 (`ENGINE_VERSION.yaml`)
- **Extensión version actual**: 5.21.1 (drift de 6 versiones)
- **Board FreeForm**: `ff-ed0c02f4565a`
- **Repo GitHub**: `EmbedBuild/specbox-engine`
- **Publisher Marketplace**: `jpsdeveloper`

---

## Próximo paso

1. **Si los 10 UCs aún no están en el board**: invocar (manualmente) los `add_uc` MCP tools sobre `ff-ed0c02f4565a` con `us_id="US-VSCODE-MARKETPLACE"` para cada UC-634..UC-643. ~52 ACs en total.
2. **Implementación**: ejecutar `/implement` que:
    - Llamará `find_next_uc` → arrancará por UC-634 (foundational, sin dependencias).
    - Aplicará el orden recomendado de fases.
    - Bloqueará si encuentra dependencias no resueltas (ej. UC-638 sin UC-639 ejecutado humanamente).
3. **Release**: tras los 10 UCs verdes + AG-09b ACCEPTED, invocar `/release 6.2.0 "VSCode Marketplace"`. El hook UC-635 implementado correrá el sync automáticamente.

**Tiempo total estimado**: ~42h de trabajo de implementación + ~30min de setup humano (UC-639) + tiempo de espera Marketplace approval (variable, típicamente <24h).
