#!/usr/bin/env node
/**
 * post-implement-validate.mjs — Hook: post-implementation validation
 * NON-BLOCKING: Checks that the baseline hasn't regressed.
 */

import { fileExists, readJsonFile, findFiles, commandExists } from './lib/utils.mjs';
import { execSync } from 'child_process';
import { basename, join } from 'path';

const BASELINE_DIR = '.quality/baselines';
if (!fileExists(BASELINE_DIR)) {
  process.exit(0);
}

// Normalize: replace underscores with hyphens to match MCP registry name
const projectName = basename(process.cwd()).replace(/_/g, '-');
const baselineFile = join(BASELINE_DIR, `${projectName}.json`);

if (!fileExists(baselineFile)) {
  console.log(`[POST-IMPLEMENT] No baseline found for ${projectName}, skipping validation`);
  process.exit(0);
}

console.log('[POST-IMPLEMENT] Validating against baseline...');

// Quick lint check
let errors = 0;

if (fileExists('pubspec.yaml')) {
  try {
    const output = execSync('dart analyze --no-fatal-infos', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
    const matches = output.match(/ error /gi);
    errors = matches ? matches.length : 0;
  } catch (e) {
    const output = (e.stdout || '') + (e.stderr || '');
    const matches = output.match(/ error /gi);
    errors = matches ? matches.length : 0;
  }
} else if (fileExists('package.json')) {
  try {
    const output = execSync('npx eslint . --format json', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
    const data = JSON.parse(output);
    errors = data.reduce((sum, f) => sum + (f.errorCount || 0), 0);
  } catch { errors = 0; }
} else if (fileExists('pyproject.toml')) {
  try {
    const output = execSync('ruff check . --output-format json', { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
    const data = JSON.parse(output);
    errors = data.length;
  } catch { errors = 0; }
}

const baseline = readJsonFile(baselineFile);
const baselineErrors = baseline?.metrics?.lint_errors || 0;

if (errors > baselineErrors) {
  console.log(`[POST-IMPLEMENT] Lint errors increased: ${baselineErrors} -> ${errors} (ratchet violation)`);
} else {
  console.log(`[POST-IMPLEMENT] Lint errors OK: ${errors} (baseline: ${baselineErrors})`);
}
