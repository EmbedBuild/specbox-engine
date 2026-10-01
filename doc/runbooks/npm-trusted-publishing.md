# La CLI `specbox` se publica sola en npm (trusted publishing)

`packages/specbox-cli` es el paquete `specbox` de npm (`npx specbox login`, UC-3904). Desde
esta guía, cada etiqueta `vX.Y.Z` del engine lo publica el workflow
`.github/workflows/publish-specbox-cli.yml`, igual que `publish-vscode-extension.yml` publica
la extensión. Nadie ejecuta `npm publish` a mano ni guarda un token en el repositorio.

## Cómo funciona

- **Trusted publishing** (OIDC). npmjs.com conoce al publicador de confianza del paquete: el
  repositorio `EmbedBuild/specbox-engine` y el fichero de workflow. En cada ejecución, npm
  (≥ 11.5.1) cambia el `id-token` del job (`permissions: id-token: write`) por una credencial de
  un solo uso. No hay `NPM_TOKEN`, no hay 2FA que superar y nada que rotar.
- **Procedencia.** `npm publish --provenance` deja en npm la atestación de qué commit y qué
  workflow produjeron el paquete; la página del paquete la enseña.
- **Idempotente.** Si la versión ya está en npm, el job termina sin publicar (sirve para
  relanzarlo sin miedo). Si `packages/specbox-cli/package.json` no coincide con la etiqueta, el
  job falla antes de publicar (`/release` sincroniza esa versión).
- **Verificación.** El job no se da por bueno hasta que `npm view specbox@X.Y.Z version`
  responde la versión publicada. Espera hasta 45 minutos (`scripts/npm-publish-and-wait.sh`,
  UC-5902): npm a veces acepta la publicación y tarda en servirla.

## Si npm tarda en servir la versión («staged»)

npm puede aceptar `npm publish` y dejar la versión «staged» un rato antes de servirla
(specbox@6.16.0 tardó ~31 minutos). Mientras tanto, volver a publicar responde
`E409 … previously staged`. El workflow trata ese E409 como publicación aceptada y sigue
comprobando cada 30 segundos hasta 45 minutos; termina en verde en cuanto npm la sirve.

Si pasan los 45 minutos, el job falla con un mensaje que dice cómo relanzarlo. No se pierde
nada: relánzalo más tarde y, en cuanto npm sirva la versión, termina en verde sin volver a
publicar.

```bash
gh workflow run publish-specbox-cli.yml --repo EmbedBuild/specbox-engine -f tag=vX.Y.Z
```

## Configuración en npmjs.com (una vez, la hace el dueño del paquete)

1. Entra en https://www.npmjs.com/package/specbox/access con la cuenta dueña
   (`jesusperezdeveloper`, con 2FA).
2. En **Trusted publishing** → **Add trusted publisher** → **GitHub Actions**:
   - Organization or user: `EmbedBuild`
   - Repository: `specbox-engine`
   - Workflow filename: `publish-specbox-cli.yml`
   - Environment: (vacío)
3. Guarda. Desde ese momento el workflow puede publicar.

Opcional pero recomendable: en **Publishing access** elige «Require two-factor authentication
and disallow tokens» — con trusted publishing no hace falta ningún token, y así nadie puede
publicar con uno filtrado.

## Publicar una versión ya etiquetada (p. ej. la primera vez)

```bash
gh workflow run publish-specbox-cli.yml --repo EmbedBuild/specbox-engine -f tag=v6.14.2
gh run watch --repo EmbedBuild/specbox-engine
npm view specbox version
```

## Plan B: token de automatización

Si algún día trusted publishing no está disponible: crea en npm un **granular access token**
con permiso de publicar sobre `specbox` y «bypass 2FA», guárdalo como secreto `NPM_TOKEN` del
repositorio y añade al workflow, antes de `npm publish`:

```yaml
      - run: echo "//registry.npmjs.org/:_authToken=${NPM_TOKEN}" > ~/.npmrc
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
```

Es un secreto de larga vida: rótalo al menos una vez al año y bórralo en cuanto vuelvas al
publicador de confianza.

## Cómo saber qué versión sirve npm

```bash
npm view specbox version dist-tags
npx specbox@latest --version
```
