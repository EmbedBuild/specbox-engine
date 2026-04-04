#!/usr/bin/env node
/**
 * pre-commit-lint.mjs — PostToolUse hook for git commit
 * BLOCKING: Runs lint validation before each commit.
 * Uses GGA (Gentleman Guardian Angel) for cached validation.
 * Falls back to direct lint if GGA not installed.
 *
 * v5.7.0
 */

import { commandExists, fileExists } from './lib/utils.mjs';
import { execSync } from 'child_process';

function runCommand(cmd) {
  try {
    execSync(cmd, { stdio: 'inherit', encoding: 'utf-8' });
    return 0;
  } catch (e) {
    return e.status || 1;
  }
}

// --- GGA (cached validation) ---
if (commandExists('gga')) {
  console.log('[QG] Running GGA cached validation...');
  const result = runCommand('gga run');

  if (result !== 0) {
    console.log('');
    console.log('[QUALITY GATE] GGA validation failed. Fix errors before committing.');
    console.log('   Policy: zero-tolerance (0 errors, 0 warnings)');
    console.log('   Tip: only modified files were checked (cache active)');
    process.exit(1);
  }

  console.log('[QUALITY GATE] GGA passed (cached — unmodified files skipped)');
  process.exit(0);
}

// --- Fallback: lint directo (sin cache) ---
console.log('[QG] GGA not found, falling back to direct lint...');

// Detect OS for install suggestion
let installCmd;
switch (process.platform) {
  case 'darwin':
    installCmd = 'brew install gentleman-programming/tap/gga';
    break;
  case 'linux':
    installCmd = 'brew install gentleman-programming/tap/gga  OR  git clone + ./install.sh';
    break;
  default:
    installCmd = 'git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git && cd gga && ./install.sh';
    break;
}
console.log(`[QG] Install GGA for cached validation: ${installCmd}`);

// Detect stack and run appropriate linter
let result;
if (fileExists('pubspec.yaml')) {
  console.log('[QG] Running dart analyze...');
  result = runCommand('dart analyze --no-fatal-infos');
} else if (fileExists('package.json')) {
  if (commandExists('eslint')) {
    console.log('[QG] Running eslint...');
    result = runCommand('npx eslint . --max-warnings=0');
  } else {
    console.log('[QG] Running npm run lint...');
    result = runCommand('npm run lint');
  }
} else if (fileExists('pyproject.toml') || fileExists('requirements.txt')) {
  console.log('[QG] Running ruff check...');
  result = runCommand('ruff check .');
} else {
  console.log('[QG] No linter detected, skipping');
  process.exit(0);
}

if (result !== 0) {
  console.log('');
  console.log('[QUALITY GATE] Lint failed. Fix errors before committing.');
  console.log('   Policy: zero-tolerance (0 errors, 0 warnings)');
  console.log('   Note: install GGA for cached validation (skips unmodified files)');
  process.exit(1);
}

console.log('[QUALITY GATE] Lint passed (no cache — install GGA for faster runs)');
process.exit(0);
