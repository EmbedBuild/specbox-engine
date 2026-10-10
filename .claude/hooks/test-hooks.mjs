#!/usr/bin/env node
/**
 * test-hooks.mjs — Validation script for all migrated Node.js hooks
 * Runs each hook with simulated input and verifies exit codes + output.
 *
 * Usage: node .claude/hooks/test-hooks.mjs
 */

import { execSync, spawnSync } from 'child_process';
import { existsSync, writeFileSync, mkdirSync, mkdtempSync, unlinkSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { dirname, join, resolve } from 'path';

const HOOKS_DIR = '.claude/hooks';
let passed = 0;
let failed = 0;
const results = [];

function test(name, hookFile, stdin, expectedExit, expectedOutput, { cwd, env } = {}) {
  try {
    const result = spawnSync('node', [resolve(HOOKS_DIR, hookFile)], {
      input: stdin,
      encoding: 'utf-8',
      timeout: 10000,
      cwd: cwd ?? process.cwd(),
      env: env ?? process.env,
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
  2,
  'GUARDIA DE CALIDAD'
);
test(
  'no-bypass-guard: blocks push --force',
  'no-bypass-guard.mjs',
  '{"command":"git push origin main --force"}',
  2,
  'GUARDIA DE CALIDAD'
);
test(
  'no-bypass-guard: blocks reset --hard',
  'no-bypass-guard.mjs',
  '{"command":"git reset --hard HEAD~1"}',
  2,
  'GUARDIA DE CALIDAD'
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
// commit-spec-guard reads the project config and the current branch, so each case
// runs in its own throwaway repository: the same result in a PR, on main and on any
// local branch (UC-8502; it ran in the engine repo, which is spec-driven, and
// failed on every push to main).
function scratchRepo(branch, { specDriven }) {
  const dir = mkdtempSync(join(tmpdir(), 'commit-spec-guard-'));
  spawnSync('git', ['init', '-q', '-b', branch], { cwd: dir });
  if (specDriven) {
    mkdirSync(join(dir, '.claude'));
    writeFileSync(join(dir, '.claude', 'project-config.json'), JSON.stringify({ board_id: 'test-board' }));
  }
  return dir;
}
test(
  'commit-spec-guard: non-spec project on main',
  'commit-spec-guard.mjs',
  '{}',
  0,
  undefined,
  { cwd: scratchRepo('main', { specDriven: false }) }
);
test(
  'commit-spec-guard: spec-driven project on main → blocks',
  'commit-spec-guard.mjs',
  '{}',
  2,
  'COMMIT BLOQUEADO',
  { cwd: scratchRepo('main', { specDriven: true }) }
);
test(
  'commit-spec-guard: spec-driven project on a feature branch',
  'commit-spec-guard.mjs',
  '{}',
  0,
  undefined,
  { cwd: scratchRepo('feature/x', { specDriven: true }) }
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
// pre-commit-lint runs the project's linter on the files of the commit (UC-9302), so it runs in an
// empty folder whose PATH only has node: the same result on any computer (UC-7204).
test(
  'pre-commit-lint: no repo and no linters → skips in silence',
  'pre-commit-lint.mjs',
  '{}',
  0,
  undefined,
  { cwd: mkdtempSync(join(tmpdir(), 'pre-commit-lint-')), env: { ...process.env, PATH: dirname(process.execPath) } }
);

// ---- e2e-gate.mjs ----
test(
  'e2e-gate: empty staged files',
  'e2e-gate.mjs',
  '{}',
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
