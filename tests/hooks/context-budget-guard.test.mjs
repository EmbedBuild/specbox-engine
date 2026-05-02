/**
 * Smoke tests for context-budget-guard.mjs and lib/token-counter.mjs (v5.32.0).
 *
 * Uses only node:assert/strict + node:fs (no test framework dependency)
 * to match the convention of v5.30 hook tests.
 */

import assert from 'node:assert/strict';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  estimateTokens,
  estimatePromptTokens,
} from '../../.claude/hooks/lib/token-counter.mjs';

const repoRoot = resolve(fileURLToPath(import.meta.url), '../../..');
const hookPath = join(repoRoot, '.claude/hooks/context-budget-guard.mjs');

// ── token-counter ─────────────────────────────────────────────────────

function testEstimateTokensEmpty() {
  assert.equal(estimateTokens(''), 0);
  assert.equal(estimateTokens(null), 0);
  assert.equal(estimateTokens(undefined), 0);
}

function testEstimateTokensCharsOver4() {
  // "abcd" = 4 chars → ceil(4/4) = 1 token, but min 1 enforced for non-empty.
  assert.equal(estimateTokens('abcd'), 1);
  // 8 chars → 2 tokens
  assert.equal(estimateTokens('abcdefgh'), 2);
  // 9 chars → ceil(9/4) = 3 tokens
  assert.equal(estimateTokens('abcdefghi'), 3);
}

function testEstimatePromptTokensBreakdown() {
  const r = estimatePromptTokens({
    tool_input: {
      description: 'short',
      prompt: 'a'.repeat(40), // 10 tokens
      system: 'b'.repeat(20), // 5 tokens
    },
  });
  assert.equal(r.breakdown.prompt, 10);
  assert.equal(r.breakdown.system, 5);
  assert.ok(r.total >= 15);
}

function testEstimatePromptTokensFiles() {
  const r = estimatePromptTokens({
    tool_input: {
      prompt: 'hi',
      files: [
        { content: 'x'.repeat(40) }, // 10 tokens
        { content: 'y'.repeat(80) }, // 20 tokens
      ],
    },
  });
  assert.equal(r.breakdown.files, 30);
  assert.ok(r.total >= 30);
}

function testEstimatePromptTokensFlatPayload() {
  // Sometimes called without tool_input wrapper
  const r = estimatePromptTokens({ prompt: 'a'.repeat(40) });
  assert.equal(r.breakdown.prompt, 10);
}

// ── hook end-to-end ───────────────────────────────────────────────────

function makeTempDir() {
  const dir = join('/tmp', `v532-budget-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

function runHook(payload, cwd) {
  const result = spawnSync('node', [hookPath], {
    input: JSON.stringify(payload),
    cwd,
    encoding: 'utf-8',
  });
  return { code: result.status, stderr: result.stderr };
}

function testHookNoOpForNonTask() {
  const cwd = makeTempDir();
  try {
    const r = runHook({ tool_name: 'Read' }, cwd);
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookSilentUnderBudget() {
  const cwd = makeTempDir();
  try {
    const r = runHook(
      { tool_name: 'Task', tool_input: { prompt: 'small task' } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookWarnsOverBudget() {
  const cwd = makeTempDir();
  try {
    const bigPrompt = 'x'.repeat(80000); // ~20k tokens
    const r = runHook(
      { tool_name: 'Task', tool_input: { prompt: bigPrompt } },
      cwd
    );
    assert.equal(r.code, 0); // warn mode is non-blocking
    assert.match(r.stderr, /WARNING/);
    assert.match(r.stderr, /budget 16000/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookBlocksInStrictMode() {
  const cwd = makeTempDir();
  try {
    mkdirSync(join(cwd, '.claude'), { recursive: true });
    writeFileSync(
      join(cwd, '.claude/settings.local.json'),
      JSON.stringify({
        specbox: { implement: { task_isolation: { task_budget_mode: 'strict' } } },
      })
    );
    const bigPrompt = 'x'.repeat(80000);
    const r = runHook(
      { tool_name: 'Task', tool_input: { prompt: bigPrompt } },
      cwd
    );
    assert.equal(r.code, 2);
    assert.match(r.stderr, /BLOCKED/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookOffModeIsNoOp() {
  const cwd = makeTempDir();
  try {
    mkdirSync(join(cwd, '.claude'), { recursive: true });
    writeFileSync(
      join(cwd, '.claude/settings.local.json'),
      JSON.stringify({
        specbox: { implement: { task_isolation: { task_budget_mode: 'off' } } },
      })
    );
    const r = runHook(
      { tool_name: 'Task', tool_input: { prompt: 'x'.repeat(80000) } },
      cwd
    );
    assert.equal(r.code, 0);
    assert.equal(r.stderr, '');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

function testHookCustomBudget() {
  const cwd = makeTempDir();
  try {
    mkdirSync(join(cwd, '.claude'), { recursive: true });
    writeFileSync(
      join(cwd, '.claude/settings.local.json'),
      JSON.stringify({
        specbox: { implement: { task_isolation: { task_budget_tokens: 100, task_budget_mode: 'strict' } } },
      })
    );
    // ~125 tokens — over the 100-token budget
    const r = runHook(
      { tool_name: 'Task', tool_input: { prompt: 'x'.repeat(500) } },
      cwd
    );
    assert.equal(r.code, 2);
    assert.match(r.stderr, /budget 100/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// ── runner ────────────────────────────────────────────────────────────

const tests = [
  testEstimateTokensEmpty,
  testEstimateTokensCharsOver4,
  testEstimatePromptTokensBreakdown,
  testEstimatePromptTokensFiles,
  testEstimatePromptTokensFlatPayload,
  testHookNoOpForNonTask,
  testHookSilentUnderBudget,
  testHookWarnsOverBudget,
  testHookBlocksInStrictMode,
  testHookOffModeIsNoOp,
  testHookCustomBudget,
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
