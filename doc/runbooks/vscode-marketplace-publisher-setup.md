# VSCode Marketplace Publisher Setup — Runbook

> One-time setup que debes ejecutar **una sola vez** antes del primer publish a Marketplace.
> Introducido en v6.2.0 por UC-639 (US-VSCODE-MARKETPLACE).
>
> **Tiempo aprox.:** 20-30 minutos si nunca lo has hecho.
> **Re-ejecución:** solo al rotar el PAT (caduca máx. 1 año en Azure DevOps).

## Antes de empezar

| Necesitas | Estado | Cómo |
|-----------|:------:|------|
| Cuenta Microsoft (Outlook, Hotmail, etc.) | obligatorio | Si no tienes, regístrate en https://outlook.com |
| Acceso admin al repo `EmbedBuild/specbox-engine` | obligatorio | Para añadir secrets en GitHub Actions |
| Node.js 18+ instalado localmente | obligatorio | `node --version` |
| `vsce` CLI | opcional (lo instalamos en el paso 3) | `vsce --version` |
| `gh` CLI autenticado | recomendado | `gh auth status` |

---

## Paso 1: crear cuenta y organización en Azure DevOps

El Marketplace de VSCode usa Azure DevOps como sistema de identidad para los publishers. Necesitas una organización (puede ser personal, gratis).

1. Ve a https://aex.dev.azure.com/ e inicia sesión con tu cuenta Microsoft.
2. Si nunca has usado Azure DevOps, te pedirá crear una organización. Pon un nombre cualquiera (no se muestra públicamente, p. ej. `jps-marketplace-org`).
3. La región puede ser cualquiera; "West Europe" suele dar latencia razonable.
4. **No necesitas crear un Project** dentro de la organización. Marketplace solo usa la organización como contenedor de PATs.

---

## Paso 2: generar el Personal Access Token (PAT)

1. En el dashboard de Azure DevOps, esquina superior derecha: **User Settings** (icono de persona) → **Personal access tokens**.
2. Botón **+ New Token**.
3. Configura el token:
   | Campo | Valor |
   |-------|-------|
   | Name | `specbox-engine-marketplace-publish` |
   | Organization | **All accessible organizations** (importante — si seleccionas solo una, vsce a veces falla con permisos) |
   | Expiration (UTC) | máx **1 año** (Microsoft impone el límite, no se puede más) |
   | Scopes | **Custom defined** → expande **Marketplace** → marca **Manage** |
4. Click **Create**.
5. **COPIA EL TOKEN YA**. Microsoft solo te lo muestra una vez. Si lo pierdes, tienes que regenerar.
6. Pégalo temporalmente en algún sitio seguro (1Password, gestor de credenciales, archivo `.env` que NO se commitea).

> **Importante**: el PAT da permiso para **publicar y borrar** cualquier extensión del publisher `EmbedBuild`. Trátalo como una credencial sensible.

---

## Paso 3: instalar `vsce` y registrar el publisher

```bash
# Instala vsce globalmente
npm install -g @vscode/vsce
vsce --version    # debe mostrar 3.x

# Registra el publisher en local (vincula tu PAT con el nombre 'EmbedBuild')
vsce login EmbedBuild
# Pegará el PAT cuando lo pida.
```

> **Por qué `EmbedBuild`**: es el `publisher` declarado en `vscode-extension/package.json:6`, alineado con el owner del repo en GitHub (`https://github.com/EmbedBuild/specbox-engine`). Decisión consciente: mantener el mismo nombre en el Marketplace y en GitHub para que el branding sea coherente. Si quisieras cambiarlo, habría que editar `package.json`, los workflows CI, todas las URLs/badges del Marketplace en los READMEs, los runbooks, el script de stats y el extension ID en `install-ext.mjs`.

### Si el publisher `EmbedBuild` no existe todavía

vsce te dará un error tipo `publisher 'EmbedBuild' not found`. En ese caso:

1. Ve a https://marketplace.visualstudio.com/manage
2. Inicia sesión con la misma cuenta Microsoft del paso 1.
3. Click **+ New Publisher** (o **Create publisher**).
4. **Publisher ID**: `EmbedBuild` (exactamente este, **CamelCase**, sin sufijos).
5. **Display Name**: `Embed.build` (lo que se ve en el listing del Marketplace).
6. Acepta los términos del Marketplace.
7. Vuelve a ejecutar `vsce login EmbedBuild` con tu PAT.

---

## Paso 4: añadir el PAT como secret en GitHub

El workflow `.github/workflows/publish-vscode-extension.yml` (UC-638) lee `secrets.VSCE_PAT`. Sin este secret el workflow fallará en el paso de publish.

### Opción A: vía `gh` CLI (recomendada)

```bash
# Te pedirá pegar el PAT
gh secret set VSCE_PAT --repo EmbedBuild/specbox-engine
```

### Opción B: vía web UI

1. https://github.com/EmbedBuild/specbox-engine/settings/secrets/actions
2. **New repository secret**.
3. Name: `VSCE_PAT`. Secret: pega el PAT.
4. **Add secret**.

### Verificación (AC-05)

```bash
gh secret list --repo EmbedBuild/specbox-engine
# Debe aparecer VSCE_PAT en el listado (NO muestra el valor, eso es esperado).
```

---

## Paso 5: comando de verificación (AC-03)

Antes del primer publish, verifica que vsce reconoce el publisher:

```bash
vsce ls-publishers
# Debe listar 'EmbedBuild'
```

Después del primer publish exitoso (cuando se corte el tag `v6.2.0-rc1` o `v6.2.0`):

```bash
vsce show EmbedBuild.specbox-engine
# Debe mostrar metadata del listing: versions, statistics, etc.
```

---

## Rotación del PAT (AC-02)

Los PATs de Azure DevOps caducan en máx. 1 año. Cuando se acerque la fecha (Azure DevOps envía email aviso 7 días antes):

### Cómo rotar sin perder ownership del publisher

1. Genera un PAT nuevo siguiendo **Paso 2** (mismo scope `Marketplace > Manage`).
2. Actualiza el login local:
   ```bash
   vsce logout EmbedBuild
   vsce login EmbedBuild
   # Pega el PAT nuevo.
   ```
3. Actualiza el secret en GitHub:
   ```bash
   gh secret set VSCE_PAT --repo EmbedBuild/specbox-engine
   # Pega el PAT nuevo.
   ```
4. Verificación: dispara el workflow manualmente para confirmar que el secret nuevo funciona:
   ```bash
   gh workflow run publish-vscode-extension.yml -R EmbedBuild/specbox-engine \
     -f tag=v6.2.0  # o el tag más reciente
   ```
5. El publisher `EmbedBuild` sigue siendo dueño de la extensión — la rotación del PAT no afecta a la propiedad, solo a las credenciales que usa el workflow para publicar.

### Recordatorio sugerido

Añade un recordatorio en tu calendario / Linear / Todoist 11 meses después de generar el PAT. La caducidad sin haber rotado bloqueará todos los publishes siguientes.

---

## Unpublish de emergencia (AC-04)

Si necesitas retirar una versión por un bug crítico, fuga de secret, o decisión de negocio:

### Retirar solo una versión

```bash
vsce unpublish EmbedBuild.specbox-engine@6.2.0
# Confirma cuando lo pida.
```

Quita esa versión específica del Marketplace. **Instalaciones existentes no se desinstalan** — los usuarios siguen con la versión que tenían. La próxima actualización (si publicas un fix-forward) la verán.

### Retirar la extensión entera

```bash
vsce unpublish EmbedBuild.specbox-engine
# Confirma DOS veces (la segunda con el nombre completo de la extensión).
```

**No hagas esto a menos que sea grave.** Quita la extensión del Marketplace, libera el namespace `EmbedBuild.specbox-engine` (¡otro publisher podría tomarlo!). Tarda **horas** en propagar globalmente — algunos mirrors regionales del Marketplace pueden seguir sirviéndola durante un día.

### Advertencias del Marketplace

- **Propagación**: cualquier cambio (publish, unpublish, edit metadata) tarda **de 5 minutos a varias horas** en aparecer en todos los clientes VSCode. El primer publish puede tardar más por la revisión inicial de Microsoft.
- **Revisión inicial**: Microsoft revisa la primera publicación de cada extensión nueva (categorías, branding, descripción). Suele aprobarse en <24h. Si flaggean algo, recibirás un email.
- **No se puede republicar el mismo número de versión**. Si publicas `6.2.0` y necesitas un fix, tienes que cortar `6.2.1` — el Marketplace rechaza re-publishes de versiones existentes.
- **Pre-release vs stable**: las versiones `-rc*` se publican con flag `--pre-release` y solo aparecen para usuarios que activan "Switch to Pre-Release Version" en el UI de VSCode. Útil para validar el workflow sin exponer al público general.

---

## Troubleshooting

| Síntoma | Causa probable | Acción |
|---------|----------------|--------|
| `vsce publish` falla con `401 Unauthorized` | PAT inválido, caducado o scope insuficiente | Genera un PAT nuevo con scope `Marketplace > Manage`. |
| `vsce publish` falla con `403 Forbidden` | El PAT no tiene permisos sobre `EmbedBuild`. ¿Estás en la organización correcta? | Verifica que el PAT se generó con `Organization: All accessible organizations`. |
| Workflow CI falla en step "Publish to VSCode Marketplace" con "VSCE_PAT is not set" | El secret no existe en el repo | Ejecuta `gh secret set VSCE_PAT --repo EmbedBuild/specbox-engine`. |
| `vsce login EmbedBuild` cuelga sin mensaje | **Causa frecuente: el publisher no existe todavía en el Marketplace**. vsce no muestra error claro y se queda esperando. Otra causa: TTY no interactivo. | (1) Verifica antes de hacer login que `https://marketplace.visualstudio.com/manage/publishers/EmbedBuild` NO devuelve 404. Si lo hace, créalo en `https://marketplace.visualstudio.com/manage`. (2) Como atajo no-interactivo: `vsce verify-pat EmbedBuild` (te pide el PAT pero no se cuelga). |
| El listing aparece publicado pero `vsce show` da 404 | Propagación todavía no completa | Espera 15-30 min y reintenta. |

---

## Cuándo actualizar este runbook

- Microsoft cambia el flujo de Azure DevOps PATs (improbable; estable desde 2017).
- Cambias el `publisher` del Marketplace (no recomendado — implicaría retirar la extensión y republicarla desde un publisher nuevo, perdiendo histórico).
- Actualizas el repo de GitHub (de `EmbedBuild` a otro owner).
- Cambia el procedimiento de `vsce` (nuevas versiones de la CLI pueden simplificar pasos).
