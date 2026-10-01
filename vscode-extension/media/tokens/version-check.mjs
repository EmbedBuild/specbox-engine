#!/usr/bin/env node
/**
 * @specbox/tokens — version-check (UC-4404)
 *
 * Viaja a cada app junto a los tokens (dist/version-check.mjs → <app>/…/tokens/). Compara la
 * versión que la app recibió (version.json, a su lado) con la vigente en el orquestador y
 * AVISA si difieren. Nunca bloquea: sale siempre con 0.
 *
 *   node <carpeta de tokens>/version-check.mjs [--current <x.y.z>]
 *
 * La versión vigente se busca, por orden, en:
 *   1. --current <x.y.z> o la variable SPECBOX_TOKENS_VERSION;
 *   2. el orquestador en disco: subiendo carpetas hasta packages/tokens/package.json
 *      (los satélites viven anidados en specbox-manager/repositorios/);
 *   3. GitHub: `gh api` sobre EmbedBuild/specbox-manager (en CI, con GH_TOKEN con acceso).
 * En GitHub Actions el aviso sale además como anotación ::warning::.
 */
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));
const PKG_NAME = '@specbox/tokens';
const REPO = 'EmbedBuild/specbox-manager';

function received() {
  const f = join(HERE, 'version.json');
  return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : null;
}

function fromArgs() {
  const i = process.argv.indexOf('--current');
  const v = i > -1 ? process.argv[i + 1] : process.env.SPECBOX_TOKENS_VERSION;
  return v ? { version: v, where: i > -1 ? '--current' : 'SPECBOX_TOKENS_VERSION' } : null;
}

function fromDisk() {
  for (let dir = HERE; ; dir = dirname(dir)) {
    const f = join(dir, 'packages', 'tokens', 'package.json');
    if (existsSync(f)) {
      const pkg = JSON.parse(readFileSync(f, 'utf8'));
      if (pkg.name === PKG_NAME) return { version: pkg.version, where: resolve(f) };
    }
    if (dirname(dir) === dir) return null;
  }
}

function fromGitHub() {
  try {
    const raw = execFileSync('gh', ['api', `repos/${REPO}/contents/packages/tokens/package.json`, '-H', 'Accept: application/vnd.github.raw'], {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], timeout: 15000,
    });
    return { version: JSON.parse(raw).version, where: `github.com/${REPO}` };
  } catch {
    return null;
  }
}

const major = (v) => Number(String(v).split('.')[0]);
const warn = (msg) => {
  console.warn(`⚠ ${msg}`);
  if (process.env.GITHUB_ACTIONS) console.log(`::warning title=Sistema de diseño desactualizado::${msg}`);
};

const mine = received();
if (!mine) {
  warn(`No hay version.json junto a ${HERE}: esta app no recibió los tokens por la sincronización del orquestador.`);
  process.exit(0);
}
const current = fromArgs() || fromDisk() || fromGitHub();
if (!current) {
  console.log(`· ${PKG_NAME} ${mine.version} en esta app; no se pudo consultar la vigente (sin orquestador en disco ni acceso con gh).`);
} else if (current.version === mine.version) {
  console.log(`✔ Sistema de diseño al día: ${PKG_NAME} ${mine.version} (vigente según ${current.where}).`);
} else {
  const kind = major(current.version) !== major(mine.version) ? ' Cambio MAYOR: renombra o elimina tokens, lee el CHANGELOG antes de sincronizar.' : '';
  warn(
    `Esta app usa ${PKG_NAME} ${mine.version} y el orquestador está en ${current.version} (${current.where}).` +
    `${kind} Re-sincroniza con \`npm run build:sync\` en packages/tokens del orquestador.`,
  );
}
process.exit(0);
