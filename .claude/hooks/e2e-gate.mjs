#!/usr/bin/env node
/**
 * e2e-gate.mjs — PreToolUse hook for `git commit`
 * BLOCKING (exit 2, before the commit exists): acceptance tests or evidence go into the commit and
 * the evidence does not meet the contract:
 *   1. results.json exists and passes schema validation
 *   2. e2e-evidence-report.html exists and has real content
 *   3. Evidence files referenced in results.json actually exist
 * Acceptance tests committed before running them (no evidence yet) pass.
 *
 * v5.12.0 — E2E Evidence Quality Gate · US-93/UC-9302: runs before the commit (after it, the
 * staging area was empty and the gate never acted) and its reason reaches the agent.
 */

import { readHookInput, gitDirForCommand, git, commitFiles, fileExists, findFiles, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';
import { blockWith } from './lib/output.mjs';
import { spawnSync } from 'child_process';
import { dirname, join } from 'path';
import { readFileSync } from 'fs';

const { toolInput, cwd } = readHookInput();
const command = String(toolInput.command || '');
if (command && !/\bgit\b[^;&|]*\bcommit\b/.test(command)) process.exit(0);
try {
  process.chdir(gitDirForCommand(command, cwd));
} catch {
  process.exit(0);
}
if (!git('rev-parse --show-toplevel')) process.exit(0);

const files = commitFiles(command);
const hasAcceptanceFiles = files.some((f) => /(test\/acceptance\/|tests\/acceptance\/|e2e\/acceptance\/|e2e\/.*\.spec\.)/.test(f));
const hasEvidenceFiles = files.some((f) => /\.quality\/evidence\/.*\/acceptance\//.test(f));
if (!hasAcceptanceFiles && !hasEvidenceFiles) process.exit(0);

const activeUC = readJsonFile('.quality/active_uc.json')?.uc_id || '';
const resultsFiles = findFiles('.quality/evidence', /^results\.json$/, 'acceptance');

if (resultsFiles.length === 0) {
  // Only acceptance tests, no evidence yet (AG-09a writing tests before running them): allowed.
  if (!hasEvidenceFiles) process.exit(0);
  blockWith('E2E GATE: evidencia sin results.json', [
    'El commit lleva ficheros de evidencia pero no hay ningún results.json.',
    'Se espera: .quality/evidence/{feature}/acceptance/results.json',
    'Para arreglarlo: ejecuta las pruebas de aceptación (Playwright lo genera solo; Patrol y Python,',
    'con patrol-evidence-generator.js o api-evidence-generator.js).',
  ]);
}

// Multi-repo: the validator may live in the orchestrator repo.
const { orchestratorRoot } = getProjectConfig();
const VALIDATOR = ['.quality/scripts/validate-results-json.js', join(orchestratorRoot, '.quality/scripts/validate-results-json.js')]
  .find((p) => fileExists(p));
if (!VALIDATOR) {
  blockWith('E2E GATE: no está el validador', [
    'Falta .quality/scripts/validate-results-json.js: ejecuta install.sh o cópialo del engine.',
  ]);
}

const errors = [];
for (const resultsFile of resultsFiles) {
  const evidenceDir = dirname(resultsFile);
  let relevant = files.some((f) => f.includes(evidenceDir));
  if (!relevant && activeUC) {
    try {
      relevant = readFileSync(resultsFile, 'utf-8').includes(activeUC);
    } catch { /* unreadable: not relevant */ }
  }
  if (!relevant) continue;
  const res = spawnSync(process.execPath, [VALIDATOR, resultsFile, '--check-evidence'], { encoding: 'utf-8' });
  if (res.status !== 0) errors.push(`${resultsFile}:`, ...`${res.stdout || ''}${res.stderr || ''}`.trim().split('\n').slice(-15).map((l) => `  ${l}`));
  const htmlReport = join(evidenceDir, 'e2e-evidence-report.html');
  if (!fileExists(htmlReport)) errors.push(`Falta el HTML Evidence Report: ${htmlReport}`);
}

if (errors.length) {
  blockWith('E2E GATE: la evidencia de aceptación no es válida', [
    ...errors,
    '',
    'Para arreglarlo: results.json según doc/specs/results-json-spec.md, e2e-evidence-report.html presente',
    'y los ficheros de evidencia que cita results.json existentes. Comprueba con:',
    'node .quality/scripts/validate-results-json.js <results.json> --check-evidence',
  ]);
}
process.exit(0);
