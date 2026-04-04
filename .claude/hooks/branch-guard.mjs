#!/usr/bin/env node
/**
 * branch-guard.mjs — PostToolUse hook for Write/Edit on source files (src/, lib/)
 * BLOCKING: Prevents writing source code while on main/master branch.
 *
 * v5.10.0 — Branch Discipline Enforcement
 */

import { readStdin, git } from './lib/utils.mjs';

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

// Check if we're in a git repository
const isGit = git('rev-parse --is-inside-work-tree');
if (!isGit) {
  process.exit(0);
}

// Get current branch
const currentBranch = git('branch --show-current');

if (!currentBranch) {
  // Detached HEAD or no branch — allow (could be during rebase)
  process.exit(0);
}

// Block if on main or master
if (currentBranch === 'main' || currentBranch === 'master') {
  console.log('');
  console.log('============================================================');
  console.log(`  BRANCH GUARD: Writing source code on ${currentBranch} blocked`);
  console.log('============================================================');
  console.log(`  File: ${filePath}`);
  console.log(`  Branch: ${currentBranch}`);
  console.log('');
  console.log('  The SpecBox Engine contract requires ALL implementation');
  console.log('  code to be written on a feature branch, never on main.');
  console.log('');
  console.log('  To proceed:');
  console.log('    1. git checkout -b feature/{nombre-del-feature} main');
  console.log('    2. Then write your code on the feature branch');
  console.log('    3. Create a PR when ready to merge');
  console.log('');
  console.log('  If using /implement, this branch is created in Paso 1.');
  console.log('  If implementing manually, create the branch FIRST.');
  console.log('');
  console.log('  This is non-negotiable. Code on main = no PR = no review');
  console.log('  = no acceptance evidence = no traceability.');
  console.log('============================================================');
  console.log('');
  process.exit(1);
}

// Not on main/master → allow
process.exit(0);
