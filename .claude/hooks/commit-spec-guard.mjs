#!/usr/bin/env node
/**
 * commit-spec-guard.mjs — PostToolUse hook for git commit
 * MIXED: Some checks BLOCK, others WARN.
 *
 * BLOCKING checks:
 *   1. Commit on main/master in a spec-driven project → BLOCKED
 *
 * WARNING checks:
 *   2. No active UC → WARNING
 *   3. No checkpoint saved → WARNING
 *   4. Large commit (>15 files) → WARNING
 *
 * v5.10.0 — Branch discipline enforcement added (BLOCKING)
 */

import { git, fileExists, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig } from './lib/config.mjs';

// --- Check if project is spec-driven ---
const { boardId, isSpecDriven } = getProjectConfig();

// Not spec-driven → skip all checks
if (!isSpecDriven) {
  process.exit(0);
}

// --- BLOCKING Check: Branch discipline ---
const currentBranch = git('branch --show-current');

if (currentBranch === 'main' || currentBranch === 'master') {
  console.log('');
  console.log('============================================================');
  console.log(`  COMMIT BLOCKED: Cannot commit to ${currentBranch}`);
  console.log('============================================================');
  console.log('  This is a spec-driven project. ALL implementation commits');
  console.log('  MUST be on a feature branch, never on main/master.');
  console.log('');
  console.log('  To fix:');
  console.log('    1. git stash');
  console.log('    2. git checkout -b feature/{nombre}');
  console.log('    3. git stash pop');
  console.log('    4. Then commit on the feature branch');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

let warnings = 0;

// --- WARNING Check: Active UC exists ---
const ACTIVE_UC_FILE = '.quality/active_uc.json';
if (!fileExists(ACTIVE_UC_FILE)) {
  console.log('');
  console.log('WARNING: Committing in a spec-driven project without an active UC.');
  console.log(`  Board: ${boardId}`);
  console.log('  Expected: start_uc() should have been called before implementation.');
  console.log('  Action: Call start_uc() NOW, then mark_ac_batch() after commit.');
  warnings++;
} else {
  const activeUC = readJsonFile(ACTIVE_UC_FILE);
  const ucId = activeUC?.uc_id || '';
  if (ucId) {
    console.log(`[SPEC] Active UC: ${ucId} | Branch: ${currentBranch}`);
  }
}

// --- WARNING Check: Checkpoint freshness ---
let feature = '';
if (fileExists(ACTIVE_UC_FILE)) {
  const activeUC = readJsonFile(ACTIVE_UC_FILE);
  feature = activeUC?.feature || '';
}

if (feature) {
  const checkpointFile = `.quality/evidence/${feature}/checkpoint.json`;
  if (!fileExists(checkpointFile)) {
    console.log(`WARNING: No checkpoint saved for feature '${feature}'.`);
    console.log('  Action: Call report_checkpoint() to enable session recovery.');
    warnings++;
  }
}

// --- WARNING Check: File count ---
const stagedOutput = git('diff --cached --name-only');
const filesInCommit = stagedOutput ? stagedOutput.split('\n').filter(Boolean).length : 0;

if (filesInCommit > 15) {
  console.log(`WARNING: Large commit (${filesInCommit} files). Consider splitting by UC.`);
  console.log('  Each UC should have its own commit on a feature branch.');
  console.log('  Monolithic commits break traceability and make rollback harder.');
  warnings++;
}

// --- Summary ---
if (warnings > 0) {
  console.log('');
  console.log(`[SPEC GUARD] ${warnings} warning(s) detected. Pipeline integrity at risk.`);
  console.log('  Remember: find_next_uc -> start_uc -> implement -> mark_ac_batch -> complete_uc');
  console.log('');
}

// Warnings don't block — only the branch check blocks
process.exit(0);
