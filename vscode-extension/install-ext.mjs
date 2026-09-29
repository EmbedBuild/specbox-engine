#!/usr/bin/env node
/**
 * Cross-platform VSCode extension installer for SpecBox Engine.
 * Can be invoked by Claude Code, install.sh, the extension's updater, or directly by users.
 *
 * Usage:
 *   node vscode-extension/install-ext.mjs           # build + install
 *   node vscode-extension/install-ext.mjs --check   # just check if installed
 *   node vscode-extension/install-ext.mjs --vsix    # install pre-built .vsix if available
 *   node vscode-extension/install-ext.mjs --prefer-marketplace --expect 6.14.1
 *
 * UC-4307: it only ever installs the expected version (--expect, or the engine's
 * ENGINE_VERSION.yaml). A .vsix of any other version lying in this folder is
 * ignored — an old one used to be installed with --force and downgrade the
 * extension. --prefer-marketplace (the updater) tries the Marketplace release
 * of that exact version first. After installing, it prints the version VSCode
 * actually has as `INSTALLED_VERSION=x.y.z` and fails if it is not the expected one.
 */

import { execSync } from 'child_process';
import { existsSync, readdirSync, readFileSync, realpathSync, writeFileSync, unlinkSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXTENSION_ID = 'EmbedBuild.specbox-engine';

// --- Pure helpers (exported for tests) ---

/** The package for exactly `version` among `files`, or null. Never another version. */
export function pickVsix(files, version) {
  if (!version) { return null; }
  const wanted = `specbox-engine-${version}.vsix`;
  return files.includes(wanted) ? wanted : null;
}

/** The installed version of the extension in `code --list-extensions --show-versions` output. */
export function parseListedVersion(listOutput) {
  for (const line of String(listOutput ?? '').split('\n')) {
    const [id, version] = line.trim().split('@');
    if (id && version && id.toLowerCase() === EXTENSION_ID.toLowerCase()) { return version; }
  }
  return null;
}

/** The value after `--expect`, or null. */
export function expectedFromArgs(argv) {
  const i = argv.indexOf('--expect');
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : null;
}

// --- Helpers ---

function run(cmd, opts = {}) {
  try {
    return execSync(cmd, { encoding: 'utf-8', timeout: 60_000, stdio: 'pipe', ...opts }).trim();
  } catch {
    return null;
  }
}

function findCode() {
  // Try multiple CLI names — VSCode, VSCode Insiders, Cursor, Codium
  for (const cmd of ['code', 'code-insiders', 'cursor', 'codium']) {
    const result = run(`${cmd} --version`);
    if (result) { return cmd; }
  }
  return null;
}

function isExtensionInstalled(codeCli) {
  const list = run(`${codeCli} --list-extensions`);
  if (!list) { return false; }
  return list.split('\n').some(ext => ext.trim().toLowerCase() === EXTENSION_ID.toLowerCase());
}

function installedVersion(codeCli) {
  return parseListedVersion(run(`${codeCli} --list-extensions --show-versions`));
}

function engineVersion() {
  const engineYaml = join(__dirname, '..', 'ENGINE_VERSION.yaml');
  if (!existsSync(engineYaml)) { return null; }
  const match = readFileSync(engineYaml, 'utf-8').match(/^version:\s*(.+)/m);
  return match ? match[1].trim().replace(/^["']|["']$/g, '') : null;
}

function findVsix(version) {
  try {
    const name = pickVsix(readdirSync(__dirname), version);
    return name ? join(__dirname, name) : null;
  } catch {
    return null;
  }
}

function syncVersionFromEngine() {
  // Sync package.json version with ENGINE_VERSION.yaml
  const pkgPath = join(__dirname, 'package.json');
  const version = engineVersion();
  if (!version || !existsSync(pkgPath)) { return; }

  try {
    const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
    if (pkg.version !== version) {
      console.log(`  Syncing version: ${pkg.version} → ${version}`);
      pkg.version = version;
      writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n', 'utf-8');
    }
  } catch { /* ignore — non-critical */ }
}

function buildVsix(version) {
  // Check if npm and tsc are available
  const hasNpm = run('npm --version');
  if (!hasNpm) {
    console.error('  npm not found. Cannot build extension.');
    return null;
  }

  // Sync version with engine before building
  syncVersionFromEngine();

  console.log('  Installing dependencies...');
  run('npm install', { cwd: __dirname, stdio: 'inherit' });

  console.log('  Compiling TypeScript...');
  const compiled = run('npm run compile', { cwd: __dirname });
  if (compiled === null && !existsSync(join(__dirname, 'out', 'extension.js'))) {
    console.error('  TypeScript compilation failed.');
    return null;
  }

  // Remove old .vsix files before packaging
  try {
    for (const f of readdirSync(__dirname).filter(f => f.endsWith('.vsix'))) {
      unlinkSync(join(__dirname, f));
    }
  } catch { /* ignore */ }

  console.log('  Packaging .vsix...');
  const packResult = run('npx vsce package --allow-missing-repository', { cwd: __dirname, timeout: 180_000 });
  if (packResult === null) {
    console.error('  Failed to package extension.');
    return null;
  }

  return findVsix(version);
}

// --- Main ---

function main(argv) {
  const isCheck = argv.includes('--check');
  const usePrebuilt = argv.includes('--vsix');
  const preferMarketplace = argv.includes('--prefer-marketplace');
  const expected = expectedFromArgs(argv) ?? engineVersion();

  const codeCli = findCode();

  if (!codeCli) {
    console.log('  VSCode CLI not found in PATH.');
    console.log('  To enable: VSCode → Cmd+Shift+P → "Shell Command: Install \'code\' command in PATH"');
    console.log('  Or install manually: Extensions → Install from VSIX...');
    process.exit(isCheck ? 1 : 0); // Not an error for install — just skip
  }

  console.log(`  VSCode CLI: ${codeCli}`);

  // Check mode
  if (isCheck) {
    const installed = isExtensionInstalled(codeCli);
    console.log(`  SpecBox Extension: ${installed ? 'installed' : 'not installed'}`);
    process.exit(installed ? 0 : 1);
  }

  if (!expected) {
    console.error('  Cannot tell which version to install (no --expect and no ENGINE_VERSION.yaml).');
    process.exit(1);
  }

  // Already installed?
  if (isExtensionInstalled(codeCli)) {
    console.log(`  SpecBox Extension already installed. Updating to v${expected}...`);
  }

  let installedOk = false;

  // 1. The Marketplace release of exactly this version (the updater's first choice).
  if (preferMarketplace) {
    console.log(`  Installing ${EXTENSION_ID}@${expected} from the Marketplace...`);
    installedOk = run(`${codeCli} --install-extension ${EXTENSION_ID}@${expected} --force`, { timeout: 120_000 }) !== null;
    if (!installedOk) { console.log(`  v${expected} is not on the Marketplace yet. Falling back to a local package.`); }
  }

  // 2. A local package of exactly this version, else 3. build it.
  if (!installedOk) {
    let vsixPath = findVsix(expected);
    if (!vsixPath && !usePrebuilt) {
      console.log(`  No package for v${expected} in this folder. Building...`);
      vsixPath = buildVsix(expected);
    }
    if (!vsixPath) {
      console.error(`  No package for v${expected} available. Build the extension first:`);
      console.error('    cd vscode-extension && npm install && npm run compile && npx vsce package');
      process.exit(1);
    }
    console.log(`  Installing ${vsixPath}...`);
    installedOk = run(`${codeCli} --install-extension "${vsixPath}" --force`) !== null;
    if (!installedOk) {
      console.error('  Failed to install extension. Try manually:');
      console.error(`    ${codeCli} --install-extension "${vsixPath}"`);
      process.exit(1);
    }
  }

  // Verify what VSCode actually has now.
  const actual = installedVersion(codeCli);
  console.log(`INSTALLED_VERSION=${actual ?? 'unknown'}`);
  if (actual !== expected) {
    console.error(`  Expected v${expected} but VSCode reports v${actual ?? 'unknown'}.`);
    process.exit(1);
  }
  console.log(`  SpecBox Extension v${actual} installed successfully.`);
  console.log('  Reload VSCode to activate: Cmd+Shift+P → "Developer: Reload Window"');
}

const invokedDirectly = (() => {
  try {
    return Boolean(process.argv[1]) && realpathSync(process.argv[1]) === realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
})();

if (invokedDirectly) {
  main(process.argv.slice(2));
}
