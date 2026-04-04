#!/usr/bin/env node
/**
 * spec-guard.mjs — PostToolUse hook for Write/Edit on source files (src/, lib/)
 * BLOCKING: Prevents writing source code without an active UC in the project manager.
 *
 * This hook enforces the SpecBox Engine contract:
 * "No code without traceability. No implementation without an active UC."
 *
 * v5.7.0 — Pipeline Integrity Enforcement
 */

import { readStdin, fileExists, fileAge, git } from './lib/utils.mjs';
import { getProjectConfig, getActiveUC, getStaleUC } from './lib/config.mjs';

const input = readStdin();

// Extract file path
let filePath = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || '';
} catch {
  const match = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = match ? match[1] : '';
}

if (!filePath) {
  process.exit(0);
}

// Only guard source code files (src/, lib/), not tests, docs, config, etc.
if (!/(^|\/)(?:src|lib)\//.test(filePath)) {
  process.exit(0);
}

// Skip test files, config files, generated files
if (/(test\/|tests\/|\.test\.|\.spec\.|_test\.dart|\.g\.dart|\.freezed\.dart|\.config\.|\.json$|\.yaml$|\.md$)/.test(filePath)) {
  process.exit(0);
}

// --- Check if project is spec-driven ---
const { boardId, backendType, isSpecDriven } = getProjectConfig();

// If no board and no backend configured → not spec-driven, allow
if (!isSpecDriven) {
  process.exit(0);
}

// --- Spec-driven project: verify branch discipline ---
const currentBranch = git('branch --show-current');

if (currentBranch === 'main' || currentBranch === 'master') {
  console.log('');
  console.log('============================================================');
  console.log(`  SPEC GUARD: Writing source code on ${currentBranch} blocked`);
  console.log('============================================================');
  console.log(`  File: ${filePath}`);
  console.log(`  Branch: ${currentBranch}`);
  console.log('');
  console.log('  Spec-driven projects require ALL code on feature branches.');
  console.log('  Create a branch first: git checkout -b feature/{name} main');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// --- Spec-driven project: verify active UC ---
const activeUC = getActiveUC();
if (activeUC) {
  // Active UC exists and is fresh → allow
  process.exit(0);
}

// Check if stale
const staleUC = getStaleUC();
if (staleUC) {
  console.log('');
  console.log('============================================================');
  console.log('  ⛔ SPEC GUARD: Active UC marker is stale (>24h)');
  console.log('============================================================');
  console.log(`  File: ${filePath}`);
  console.log('  The active UC marker at .quality/active_uc.json is older than 24 hours.');
  console.log('  This likely means the previous implementation session ended');
  console.log('  without completing the UC.');
  console.log('');
  console.log('  To proceed:');
  console.log('    1. Run start_uc(board_id, uc_id) to activate a UC');
  console.log('    2. Or use /implement to start the pipeline properly');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// No active UC marker → BLOCK
console.log('');
console.log('============================================================');
console.log('  ⛔ SPEC GUARD: No active UC — implementation blocked');
console.log('============================================================');
console.log(`  File: ${filePath}`);
console.log(`  Board: ${boardId}`);
console.log('');
console.log('  This project uses spec-driven development (Trello/Plane).');
console.log('  You MUST have an active UC before writing source code.');
console.log('');
console.log('  The SpecBox Engine contract is non-negotiable:');
console.log('  No code without traceability. No implementation without pipeline.');
console.log('');
console.log('  To proceed:');
console.log('    1. find_next_uc(board_id) → identify the next UC');
console.log('    2. start_uc(board_id, uc_id) → move to In Progress');
console.log('    3. Then implement the code');
console.log('    4. mark_ac_batch(...) → check acceptance criteria');
console.log('    5. complete_uc(board_id, uc_id) → move to Done');
console.log('');
console.log('  If /implement skill is unavailable, execute these steps');
console.log('  MANUALLY. The pipeline is the contract, not the skill.');
console.log('============================================================');
console.log('');
process.exit(1);
