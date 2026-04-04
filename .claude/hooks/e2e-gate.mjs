#!/usr/bin/env node
/**
 * e2e-gate.mjs — PostToolUse hook for git commit
 * BLOCKING: Ensures acceptance evidence meets quality standards before commit.
 *
 * What it checks (only when committing acceptance/evidence files):
 *   1. results.json exists and passes schema validation
 *   2. e2e-evidence-report.html exists and has real content
 *   3. Evidence files referenced in results.json actually exist
 *
 * v5.12.0 — E2E Evidence Quality Gate
 */

import { readStdin, git, fileExists, findFiles, readJsonFile } from './lib/utils.mjs';
import { execSync } from 'child_process';
import { dirname, join } from 'path';
import { readFileSync } from 'fs';

const input = readStdin();

// Extract staged files
const stagedOutput = git('diff --cached --name-only');
if (!stagedOutput) {
  process.exit(0);
}

const stagedFiles = stagedOutput.split('\n').filter(Boolean);

// Check if this commit includes acceptance test files
const hasAcceptanceFiles = stagedFiles.some(f =>
  /(test\/acceptance\/|tests\/acceptance\/|e2e\/acceptance\/|e2e\/.*\.spec\.)/.test(f)
);

// Also check if it includes evidence files
const hasEvidenceFiles = stagedFiles.some(f =>
  /\.quality\/evidence\/.*\/acceptance\//.test(f)
);

// If no acceptance or evidence files → this is a normal commit, allow
if (!hasAcceptanceFiles && !hasEvidenceFiles) {
  process.exit(0);
}

// --- Acceptance files detected: validate evidence ---

// Find the active UC
const activeUCData = readJsonFile('.quality/active_uc.json');
const activeUC = activeUCData?.uc_id || '';
const activeFeature = activeUCData?.feature || '';

// Find results.json files in evidence directories
const resultsFiles = findFiles('.quality/evidence', /^results\.json$/, 'acceptance');

if (resultsFiles.length === 0) {
  // No results.json found — check if this is a partial commit (just .feature files)
  if (!hasEvidenceFiles) {
    // Only acceptance test files (no evidence) — AG-09a generating tests
    // Allow: tests can be committed before running them
    process.exit(0);
  }

  console.log('');
  console.log('============================================================');
  console.log('  E2E GATE: Evidence files without results.json');
  console.log('============================================================');
  console.log('  Commit includes evidence files but no results.json found.');
  console.log('');
  console.log('  Expected: .quality/evidence/{feature}/acceptance/results.json');
  console.log('');
  console.log('  To fix:');
  console.log('    1. Run acceptance tests to generate results.json');
  console.log('    2. For Playwright: results are generated automatically');
  console.log('    3. For Patrol: run patrol-evidence-generator.js');
  console.log('    4. For Python: run api-evidence-generator.js');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// Validate each results.json found
const VALIDATOR = '.quality/scripts/validate-results-json.js';

if (!fileExists(VALIDATOR)) {
  console.log('');
  console.log('============================================================');
  console.log('  E2E GATE: Validator not found');
  console.log('============================================================');
  console.log(`  Expected: ${VALIDATOR}`);
  console.log('');
  console.log('  To fix: run install.sh to restore quality scripts,');
  console.log('  or copy validate-results-json.js from the engine repo.');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

let validationFailed = false;
let validationErrors = '';

for (const resultsFile of resultsFiles) {
  const evidenceDir = dirname(resultsFile);

  // Only validate results.json that match the active UC or staged evidence
  let relevant = false;

  // Check if any staged file is in this evidence directory
  if (stagedFiles.some(f => f.includes(evidenceDir))) {
    relevant = true;
  }

  // Or if the active UC matches
  if (activeUC) {
    try {
      const content = readFileSync(resultsFile, 'utf-8');
      if (content.includes(activeUC)) {
        relevant = true;
      }
    } catch { /* ignore */ }
  }

  if (!relevant) continue;

  // Run schema validation
  try {
    execSync(`node ${VALIDATOR} ${resultsFile} --check-evidence`, {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } catch (e) {
    validationFailed = true;
    const output = (e.stdout || '') + (e.stderr || '');
    validationErrors += `\n  ${resultsFile}:\n${output}`;
  }

  // Check HTML report exists
  const htmlReport = join(evidenceDir, 'e2e-evidence-report.html');
  if (!fileExists(htmlReport)) {
    validationFailed = true;
    validationErrors += `\n  Missing HTML Evidence Report: ${htmlReport}`;
  }
}

if (validationFailed) {
  console.log('');
  console.log('============================================================');
  console.log('  E2E GATE: Evidence validation FAILED');
  console.log('============================================================');
  console.log('');
  console.log('  Acceptance files or evidence staged for commit, but');
  console.log('  evidence validation failed:');
  console.log('');
  console.log(validationErrors);
  console.log('');
  console.log('  To fix:');
  console.log('    1. Ensure results.json follows doc/specs/results-json-spec.md');
  console.log('    2. Ensure e2e-evidence-report.html exists');
  console.log('    3. Ensure evidence files referenced in results.json exist');
  console.log('    4. Run: node .quality/scripts/validate-results-json.js <path>');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

process.exit(0);
