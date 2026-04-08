#!/usr/bin/env node
/**
 * uc-lifecycle-guard.mjs — PostToolUse hook for git push
 * WARNING (non-blocking): Warns if pushing a feature branch without having
 * called move_uc to move the UC to Review. Ensures the board stays in sync.
 *
 * Also warns if mark_ac_batch hasn't been called (no ACs marked).
 *
 * v5.19.0 — Compliance Enforcement
 */

import { readStdin, git, fileExists, readJsonFile } from './lib/utils.mjs';
import { getProjectConfig, getActiveUC } from './lib/config.mjs';
import { printWarning, printBlock } from './lib/output.mjs';

const input = readStdin();

// Extract command to verify it's a git push
let command = '';
try {
  const parsed = JSON.parse(input);
  command = parsed.command || '';
} catch {
  const match = input.match(/"command"\s*:\s*"([^"]*)"/);
  command = match ? match[1] : '';
}

// Only check git push commands
if (!command.includes('git push')) {
  process.exit(0);
}

// Only check spec-driven projects
const { isSpecDriven } = getProjectConfig();
if (!isSpecDriven) {
  process.exit(0);
}

// Only check feature branches
const branch = git('branch --show-current');
if (!branch || !branch.startsWith('feature/')) {
  process.exit(0);
}

// Check if there's an active UC
const activeUC = getActiveUC();
if (!activeUC) {
  // No active UC but pushing feature branch — unusual but not necessarily wrong
  // (could be pushing after complete_uc was already called)
  process.exit(0);
}

const feature = activeUC.feature;
const warnings = [];

// Check 1: Has mark_ac_batch been called?
// We detect this by checking if any AC evidence exists
const evidenceDir = `.quality/evidence/${feature}`;
const acMarkerFile = `${evidenceDir}/ac_marked.json`;
if (!fileExists(acMarkerFile)) {
  // Also check the audit.json for any AC data
  const audit = readJsonFile(`${evidenceDir}/audit.json`);
  if (!audit || !audit.ac_results) {
    warnings.push(
      'No acceptance criteria have been marked (mark_ac_batch not called). ' +
      'The board will not reflect which ACs passed.'
    );
  }
}

// Check 2: Has the UC been moved to Review?
// We detect this by checking if a move_uc marker exists
const moveMarkerFile = `${evidenceDir}/uc_moved_to_review.json`;
if (!fileExists(moveMarkerFile)) {
  warnings.push(
    `UC "${activeUC.ucId}" has NOT been moved to Review. ` +
    'Call move_uc(board_id, uc_id, "review") before or after creating the PR. ' +
    'The board must reflect the current state.'
  );
}

if (warnings.length > 0) {
  printBlock('UC LIFECYCLE — Board may be out of sync', [
    `Feature: ${feature}`,
    `UC: ${activeUC.ucId}`,
    `Branch: ${branch}`,
    '',
    ...warnings.map(w => `WARNING: ${w}`),
    '',
    'These are non-blocking warnings. The push will proceed.',
    'But the board should always reflect reality.',
  ]);
}

process.exit(0);
