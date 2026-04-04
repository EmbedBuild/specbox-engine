#!/usr/bin/env node
/**
 * test-hooks.mjs — Validation script for all migrated Node.js hooks
 * Runs each hook with simulated input and verifies exit codes + output.
 *
 * Usage: node .claude/hooks/test-hooks.mjs
 */

import { execSync, spawnSync } from 'child_process';
import { existsSync, writeFileSync, mkdirSync, unlinkSync, readFileSync } from 'fs';
import { join } from 'path';

const HOOKS_DIR = '.claude/hooks';
let passed = 0;
let failed = 0;
const results = [];

function test(name, hookFile, stdin, expectedExit, expectedOutput) {
  try {
    const result = spawnSync('node', [join(HOOKS_DIR, hookFile)], {
      input: stdin,
      encoding: 'utf-8',
      timeout: 10000,
      cwd: process.cwd(),
    });

    const exitCode = result.status ?? -1;
    const output = (result.stdout || '') + (result.stderr || '');
    const exitOk = exitCode === expectedExit;
    const outputOk = !expectedOutput || output.includes(expectedOutput);

    if (exitOk && outputOk) {
      results.push({ name, status: 'PASS', exitCode });
      passed++;
    } else {
      results.push({
        name,
        status: 'FAIL',
        exitCode,
        expectedExit,
        expectedOutput: expectedOutput || '(any)',
        actualOutput: output.slice(0, 200),
      });
      failed++;
    }
  } catch (e) {
    results.push({ name, status: 'ERROR', error: e.message });
    failed++;
  }
}

console.log('============================================================');
console.log('  SpecBox Engine — Hook Migration Test Suite');
console.log('============================================================\n');

// ---- read-tracker.mjs ----
// Should always exit 0 (non-blocking)
test(
  'read-tracker: empty input',
  'read-tracker.mjs',
  '',
  0
);
test(
  'read-tracker: valid file_path',
  'read-tracker.mjs',
  '{"file_path":"src/test.dart"}',
  0
);

// ---- quality-first-guard.mjs ----
// Empty input → exit 0
test(
  'quality-first-guard: empty input',
  'quality-first-guard.mjs',
  '',
  0
);
// Non-existent file → exit 0 (new file creation)
test(
  'quality-first-guard: new file (non-existent)',
  'quality-first-guard.mjs',
  '{"file_path":"src/brand_new_file_that_does_not_exist.dart"}',
  0
);
// .quality/ file → exit 0 (skip)
test(
  'quality-first-guard: skip .quality/ files',
  'quality-first-guard.mjs',
  '{"file_path":".quality/some_file.json"}',
  0
);

// ---- no-bypass-guard.mjs ----
test(
  'no-bypass-guard: safe command',
  'no-bypass-guard.mjs',
  '{"command":"git status"}',
  0
);
test(
  'no-bypass-guard: blocks --no-verify',
  'no-bypass-guard.mjs',
  '{"command":"git commit --no-verify -m test"}',
  1,
  'QUALITY GUARD'
);
test(
  'no-bypass-guard: blocks push --force',
  'no-bypass-guard.mjs',
  '{"command":"git push origin main --force"}',
  1,
  'QUALITY GUARD'
);
test(
  'no-bypass-guard: blocks reset --hard',
  'no-bypass-guard.mjs',
  '{"command":"git reset --hard HEAD~1"}',
  1,
  'QUALITY GUARD'
);

// ---- branch-guard.mjs ----
test(
  'branch-guard: non-source file',
  'branch-guard.mjs',
  '{"file_path":"README.md"}',
  0
);
test(
  'branch-guard: test file in src/',
  'branch-guard.mjs',
  '{"file_path":"src/test/widget_test.dart"}',
  0
);

// ---- spec-guard.mjs ----
test(
  'spec-guard: non-source file',
  'spec-guard.mjs',
  '{"file_path":"test/some_test.dart"}',
  0
);
test(
  'spec-guard: empty input',
  'spec-guard.mjs',
  '',
  0
);

// ---- commit-spec-guard.mjs ----
// In the engine repo (not spec-driven), should exit 0
test(
  'commit-spec-guard: non-spec project',
  'commit-spec-guard.mjs',
  '{}',
  0
);

// ---- design-gate.mjs ----
test(
  'design-gate: non-page file',
  'design-gate.mjs',
  '{"file_path":"src/utils/helper.dart"}',
  0
);
test(
  'design-gate: empty input',
  'design-gate.mjs',
  '',
  0
);

// ---- pre-commit-lint.mjs ----
// This one actually runs linters so we skip it in automated tests
// but verify it parses correctly
test(
  'pre-commit-lint: syntax check (import)',
  'pre-commit-lint.mjs',
  '{}',
  0  // In engine repo with no pubspec/package.json detected, exits 0
);

// ---- e2e-gate.mjs ----
test(
  'e2e-gate: empty staged files',
  'e2e-gate.mjs',
  '{}',
  0
);

// ---- mcp-report.mjs ----
// Without SPECBOX_ENGINE_MCP_URL, should exit silently
test(
  'mcp-report: no MCP URL configured',
  'mcp-report.mjs',
  '',
  0
);

// ---- on-session-end.mjs ----
test(
  'on-session-end: runs without error',
  'on-session-end.mjs',
  '',
  0
);

// ---- post-implement-validate.mjs ----
test(
  'post-implement-validate: no baseline dir',
  'post-implement-validate.mjs',
  '',
  0
);

// ---- implement-checkpoint.mjs ----
// Without args, should exit 1 with usage message
test(
  'implement-checkpoint: no args → usage',
  'implement-checkpoint.mjs',
  '',
  1,
  'Usage'
);

// ---- implement-healing.mjs ----
test(
  'implement-healing: no args → usage',
  'implement-healing.mjs',
  '',
  1,
  'Usage'
);

// ---- Print results ----
console.log('');
console.log('Results:');
console.log('------------------------------------------------------------');
for (const r of results) {
  const status = r.status === 'PASS' ? 'PASS' : 'FAIL';
  const detail = r.status !== 'PASS'
    ? ` (exit=${r.exitCode}, expected=${r.expectedExit}${r.error ? `, error=${r.error}` : ''})`
    : '';
  console.log(`  [${status}] ${r.name}${detail}`);
}
console.log('------------------------------------------------------------');
console.log(`  Total: ${passed + failed} | Passed: ${passed} | Failed: ${failed}`);
console.log('============================================================');

process.exit(failed > 0 ? 1 : 0);
