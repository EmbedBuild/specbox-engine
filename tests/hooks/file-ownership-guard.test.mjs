/**
 * Smoke tests for file-ownership-guard.mjs and lib/ownership-map.mjs (v5.32.0).
 */

import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync, copyFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  parseOwnershipCell,
  parseOwnershipMap,
  globToRegExp,
  isSuspiciousPath,
  pathAllowedForAgent,
} from '../../.claude/hooks/lib/ownership-map.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hookPath = join(repoRoot, '.claude/hooks/file-ownership-guard.mjs');
const realOwnershipMd = join(repoRoot, '.claude/skills/implement/file-ownership.md');

// ── parseOwnershipCell ────────────────────────────────────────────────

function testParseOwnershipCellSplitsCommas() {
  assert.deepEqual(
    parseOwnershipCell('lib/features/**, src/features/**, app/**'),
    ['lib/features/**', 'src/features/**', 'app/**']
  );
}

function testParseOwnershipCellEmpty() {
  assert.deepEqual(parseOwnershipCell(''), []);
  assert.deepEqual(parseOwnershipCell(undefined), []);
}

// ── parseOwnershipMap ─────────────────────────────────────────────────

function testParseRealOwnershipMap() {
  const map = parseOwnershipMap(realOwnershipMd);
  assert.ok(Object.keys(map).length >= 8, 'expected >=8 agents in map');
  assert.ok(map['AG-01'].length > 0);
  assert.ok(map['AG-04'].length > 0);
}

function testParseMissingFileReturnsEmpty() {
  const map = parseOwnershipMap('/path/that/does/not/exist.md');
  assert.deepEqual(map, {});
}

// ── globToRegExp ──────────────────────────────────────────────────────

function testGlobMatchesDoubleStar() {
  const r = globToRegExp('lib/features/**');
  assert.equal(r.test('lib/features/staff/x.dart'), true);
  assert.equal(r.test('lib/features/x.dart'), true);
  assert.equal(r.test('lib/widgets/x.dart'), false);
}

function testGlobMatchesMiddleDoubleStar() {
  const r = globToRegExp('lib/**/widgets/**');
  assert.equal(r.test('lib/foo/widgets/x.dart'), true);
  assert.equal(r.test('lib/widgets/x.dart'), true);
  assert.equal(r.test('lib/foo/screens/x.dart'), false);
}

function testGlobMatchesSingleStar() {
  const r = globToRegExp('lib/*.dart');
  assert.equal(r.test('lib/main.dart'), true);
  assert.equal(r.test('lib/sub/main.dart'), false);
}

function testGlobMatchesQuestion() {
  const r = globToRegExp('lib/file?.dart');
  assert.equal(r.test('lib/file1.dart'), true);
  assert.equal(r.test('lib/files.dart'), true);
  assert.equal(r.test('lib/file12.dart'), false);
}

// ── isSuspiciousPath ──────────────────────────────────────────────────

function testSuspiciousDoubleDot() {
  assert.equal(isSuspiciousPath('../etc/passwd'), true);
}

function testSuspiciousAbsolute() {
  assert.equal(isSuspiciousPath('/etc/passwd'), true);
}

function testSuspiciousEmpty() {
  assert.equal(isSuspiciousPath(''), true);
  assert.equal(isSuspiciousPath(null), true);
}

function testNotSuspiciousNormal() {
  assert.equal(isSuspiciousPath('lib/main.dart'), false);
}

// ── pathAllowedForAgent ───────────────────────────────────────────────

function testPathAllowedHappy() {
  const map = parseOwnershipMap(realOwnershipMd);
  assert.equal(pathAllowedForAgent('lib/features/staff/x.dart', 'AG-01', map), true);
  assert.equal(pathAllowedForAgent('test/foo.dart', 'AG-04', map), true);
  assert.equal(pathAllowedForAgent('supabase/migrations/01.sql', 'AG-03', map), true);
}

function testPathAllowedMismatch() {
  const map = parseOwnershipMap(realOwnershipMd);
  assert.equal(pathAllowedForAgent('test/foo.dart', 'AG-01', map), false);
  assert.equal(pathAllowedForAgent('supabase/migrations/01.sql', 'AG-01', map), false);
}

function testPathAllowedUnknownAgent() {
  const map = parseOwnershipMap(realOwnershipMd);
  assert.equal(pathAllowedForAgent('foo.dart', 'AG-99', map), null);
}

// ── hook end-to-end ───────────────────────────────────────────────────

function makeTempDir() {
  const dir = join('/tmp', `v532-own-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  mkdirSync(dir, { recursive: true });
  // Provide the ownership map at the conventional location.
  mkdirSync(join(dir, '.claude/skills/implement'), { recursive: true });
  copyFileSync(realOwnershipMd, join(dir, '.claude/skills/implement/file-ownership.md'));
  // .quality dir for active_agent.json
  mkdirSync(join(dir, '.quality'), { recursive: true });
  return dir;
}

function setActiveAgent(cwd, agent) {
  writeFileSync(
    join(cwd, '.quality/active_agent.json'),
    JSON.stringify({ agent, feature_slug: 'uc-x', phase: 'feature', started_at: 'now' })
  );
}

function setSettings(cwd, mode) {
  mkdirSync(join(cwd, '.claude'), { recursive: true });
  writeFileSync(
    join(cwd, '.claude/settings.local.json'),
    JSON.stringify({ specbox: { implement: { task_isolation: { ownership_mode: mode } } } })
  );
}

function runHook(payload, cwd) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(payload),
    cwd,
    encoding: 'utf-8',
  });
  return { code: result.status, stderr: result.stderr };
}

function testHookNoOpWithoutActiveAgent() {
  const cwd = makeTempDir();
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: 'test/foo.dart' } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookAllowsAgentInOwnership() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-01');
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: 'lib/features/staff/x.dart' } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookWarnsOnMismatch() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-01');
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: 'test/foo.dart' } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.match(r.stderr, /WARNING/);
    assert.match(r.stderr, /AG-04/); // suggestion
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookBlocksInStrictMode() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-01');
  setSettings(cwd, 'strict');
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: 'supabase/migrations/01.sql' } },
      cwd
    );
    assert.equal(r.code, 2);
    assert.match(r.stderr, /BLOCKED/);
    assert.match(r.stderr, /AG-03/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookBlocksSuspiciousPathAlways() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-01');
  // Even in default warn mode, ../ is blocked.
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: '../etc/passwd' } },
      cwd
    );
    assert.equal(r.code, 2);
    assert.match(r.stderr, /BLOCKED/);
    assert.match(r.stderr, /suspicious/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookFailsOpenForUnknownAgent() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-99');
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: 'foo.dart' } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.match(r.stderr, /WARNING/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookOffMode() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-01');
  setSettings(cwd, 'off');
  try {
    const r = runHook(
      { tool_name: 'Write', tool_input: { file_path: 'test/foo.dart' } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookNoOpForReadTool() {
  const cwd = makeTempDir();
  setActiveAgent(cwd, 'AG-01');
  try {
    const r = runHook({ tool_name: 'Read', tool_input: { file_path: 'lib/main.dart' } }, cwd);
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// ── runner ────────────────────────────────────────────────────────────

const tests = [
  testParseOwnershipCellSplitsCommas,
  testParseOwnershipCellEmpty,
  testParseRealOwnershipMap,
  testParseMissingFileReturnsEmpty,
  testGlobMatchesDoubleStar,
  testGlobMatchesMiddleDoubleStar,
  testGlobMatchesSingleStar,
  testGlobMatchesQuestion,
  testSuspiciousDoubleDot,
  testSuspiciousAbsolute,
  testSuspiciousEmpty,
  testNotSuspiciousNormal,
  testPathAllowedHappy,
  testPathAllowedMismatch,
  testPathAllowedUnknownAgent,
  testHookNoOpWithoutActiveAgent,
  testHookAllowsAgentInOwnership,
  testHookWarnsOnMismatch,
  testHookBlocksInStrictMode,
  testHookBlocksSuspiciousPathAlways,
  testHookFailsOpenForUnknownAgent,
  testHookOffMode,
  testHookNoOpForReadTool,
];

let failed = 0;
for (const t of tests) {
  try {
    t();
    console.log(`  ok ${t.name}`);
  } catch (err) {
    failed++;
    console.error(`  FAIL ${t.name}: ${err.message}`);
  }
}

if (failed > 0) {
  console.error(`\n${failed} of ${tests.length} tests failed`);
  process.exit(1);
}
console.log(`\n${tests.length} tests passed`);
