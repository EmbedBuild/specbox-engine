#!/usr/bin/env node
/**
 * Cross-platform VSCode extension installer for SpecBox Engine.
 * Can be invoked by Claude Code, install.sh, or directly by users.
 *
 * Usage:
 *   node vscode-extension/install-ext.mjs           # build + install
 *   node vscode-extension/install-ext.mjs --check   # just check if installed
 *   node vscode-extension/install-ext.mjs --vsix    # install pre-built .vsix if available
 */

import { execSync } from 'child_process';
import { existsSync, readdirSync, readFileSync, writeFileSync, unlinkSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXTENSION_ID = 'jpsdeveloper.specbox-engine';

const isCheck = process.argv.includes('--check');
const usePrebuilt = process.argv.includes('--vsix');

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

function findVsix() {
  // Look for pre-built .vsix in extension dir
  try {
    const files = readdirSync(__dirname).filter(f => f.endsWith('.vsix'));
    if (files.length > 0) {
      // Pick the newest one (sort by name, semver in filename)
      files.sort().reverse();
      return join(__dirname, files[0]);
    }
  } catch { /* ignore */ }
  return null;
}

function syncVersionFromEngine() {
  // Sync package.json version with ENGINE_VERSION.yaml
  const engineYaml = join(__dirname, '..', 'ENGINE_VERSION.yaml');
  const pkgPath = join(__dirname, 'package.json');

  if (!existsSync(engineYaml) || !existsSync(pkgPath)) { return; }

  try {
    const yamlContent = readFileSync(engineYaml, 'utf-8');
    const match = yamlContent.match(/^version:\s*(.+)/m);
    if (!match) { return; }
    const engineVersion = match[1].trim();

    const pkg = JSON.parse(readFileSync(pkgPath, 'utf-8'));
    if (pkg.version !== engineVersion) {
      console.log(`  Syncing version: ${pkg.version} → ${engineVersion}`);
      pkg.version = engineVersion;
      writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n', 'utf-8');
    }
  } catch { /* ignore — non-critical */ }
}

function buildVsix(codeCli) {
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
  const compiled = run('npx tsc -p ./', { cwd: __dirname });
  if (compiled === null) {
    // tsc returns empty string on success, null on error
    const check = existsSync(join(__dirname, 'out', 'extension.js'));
    if (!check) {
      console.error('  TypeScript compilation failed.');
      return null;
    }
  }

  // Remove old .vsix files before packaging
  try {
    for (const f of readdirSync(__dirname).filter(f => f.endsWith('.vsix'))) {
      unlinkSync(join(__dirname, f));
    }
  } catch { /* ignore */ }

  console.log('  Packaging .vsix...');
  const packResult = run('npx vsce package --allow-missing-repository', { cwd: __dirname });
  if (packResult === null) {
    console.error('  Failed to package extension.');
    return null;
  }

  return findVsix();
}

// --- Main ---

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

// Already installed?
if (isExtensionInstalled(codeCli)) {
  console.log('  SpecBox Extension already installed. Updating...');
}

// Find or build .vsix
let vsixPath = findVsix();

if (!vsixPath && !usePrebuilt) {
  console.log('  No pre-built .vsix found. Building...');
  vsixPath = buildVsix(codeCli);
}

if (!vsixPath) {
  console.error('  No .vsix available. Build the extension first:');
  console.error('    cd vscode-extension && npm install && npm run compile && npx vsce package');
  process.exit(1);
}

console.log(`  Installing ${vsixPath}...`);
const installResult = run(`${codeCli} --install-extension "${vsixPath}" --force`);

if (installResult !== null) {
  console.log('  SpecBox Extension installed successfully.');
  console.log('  Reload VSCode to activate: Cmd+Shift+P → "Developer: Reload Window"');
} else {
  console.error('  Failed to install extension. Try manually:');
  console.error(`    ${codeCli} --install-extension "${vsixPath}"`);
  process.exit(1);
}
