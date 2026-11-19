/**
 * Smoke tests for context-budget-guard.mjs and lib/token-counter.mjs (v5.32.0).
 *
 * Uses only node:assert/strict + node:fs (no test framework dependency)
 * to match the convention of v5.30 hook tests.
 */

import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnWithStdin } from './_spawn-stdin.mjs';
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
  const result = spawnWithStdin('node', [hookPath], JSON.stringify(payload), {
    cwd,
    encoding: 'utf-8',
    // Sin preguntar al tablero (UC-12210): la prueba no sale de la máquina.
    env: { ...process.env, SPECBOX_ENFORCEMENT_POLICY: 'off' },
  });
  // A warning reaches the agent as additionalContext (US-93/UC-9302), not on stderr.
  let note = '';
  try { note = JSON.parse(result.stdout || '{}').hookSpecificOutput?.additionalContext || ''; } catch { /* not a note */ }
  return { code: result.status, stderr: result.stderr, note };
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
    assert.equal(r.stderr, '');
    assert.match(r.note, /se pasa de presupuesto/);
    assert.match(r.note, /presupuesto 16000/);
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
    assert.match(r.stderr, /SpecBox detuvo la operación por la medida context_budget/);
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
    assert.match(r.stderr, /el presupuesto es 100/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// ── UC-12208: «Agent» (hoy) y «Task» (antes) ─────────────────────────

const realAgentPayload = JSON.parse(
  readFileSync(join(repoRoot, 'tests/hooks/fixtures/agent-subagent-pretooluse.json'), 'utf-8')
);

function counters(cwd) {
  return JSON.parse(readFileSync(join(cwd, '.quality/task_isolation.json'), 'utf-8'));
}

function writeSettings(cwd, file, content) {
  mkdirSync(join(cwd, '.claude'), { recursive: true });
  writeFileSync(join(cwd, '.claude', file), JSON.stringify(content));
}

// AC-01: queda registrado el nombre que llega al hook, con la carga real de un subagente.
function testHookRunsForRealAgentPayloadAndRecordsTheName() {
  const cwd = makeTempDir();
  try {
    const r = runHook(realAgentPayload, cwd);
    assert.equal(r.code, 0);
    assert.equal(r.note, '');
    const c = counters(cwd);
    assert.equal(c.tasks_run_total, 1, 'el guard no se ejecutó con «Agent»');
    assert.equal(c.last_tool_name, 'Agent');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// AC-02: el nombre anterior sigue valiendo.
function testHookStillRunsForTask() {
  const cwd = makeTempDir();
  try {
    const r = runHook({ tool_name: 'Task', tool_input: { prompt: 'small task' } }, cwd);
    assert.equal(r.code, 0);
    assert.equal(counters(cwd).last_tool_name, 'Task');
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// AC-02: el registro del hook (engine y plantilla) cubre los dos nombres y nada más.
function testMatcherCoversAgentAndTask() {
  for (const file of ['.claude/settings.json', 'templates/settings.json.template']) {
    const settings = JSON.parse(readFileSync(join(repoRoot, file), 'utf-8'));
    const groups = (settings.hooks?.PreToolUse ?? []).filter((g) =>
      (g.hooks ?? []).some((h) => /context-budget-guard\.mjs/.test(h.command ?? ''))
    );
    assert.equal(groups.length, 1, `${file}: context-budget-guard debe registrarse una vez`);
    const matcher = new RegExp(`^(?:${groups[0].matcher})$`);
    assert.ok(matcher.test('Agent'), `${file}: el matcher no cubre «Agent»`);
    assert.ok(matcher.test('Task'), `${file}: el matcher no cubre «Task»`);
    assert.ok(!matcher.test('Read'), `${file}: el matcher cubre más de lo que debe`);
  }
}

// AC-03: con un presupuesto de 1 token en «warn», lanzar un subagente muestra el aviso.
function testRealAgentPayloadWarnsAtOneTokenBudget() {
  const cwd = makeTempDir();
  try {
    writeSettings(cwd, 'settings.local.json', {
      specbox: { implement: { task_isolation: { task_budget_tokens: 1, task_budget_mode: 'warn' } } },
    });
    const r = runHook(realAgentPayload, cwd);
    assert.equal(r.code, 0);
    assert.match(r.note, /se pasa de presupuesto/);
    assert.match(r.note, /presupuesto 1,/);
    assert.equal(counters(cwd).tasks_failed_budget, 1);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// La plantilla escribe task_isolation en settings.json: ahora el guard lo lee.
function testReadsTheTemplateLocationInSettingsJson() {
  const cwd = makeTempDir();
  try {
    writeSettings(cwd, 'settings.json', {
      implement: { task_isolation: { task_budget_tokens: 100, task_budget_mode: 'strict' } },
    });
    const r = runHook({ tool_name: 'Agent', tool_input: { prompt: 'x'.repeat(500) } }, cwd);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /el presupuesto es 100/);
    assert.match(r.stderr, /\(Agent\)/);
  } finally {
    rmSync(cwd, { recursive: true, force: true });
  }
}

// Una clave escrita en settings.local.json gana a la de settings.json.
function testLocalSettingsWinOverShared() {
  const cwd = makeTempDir();
  try {
    writeSettings(cwd, 'settings.json', { implement: { task_isolation: { task_budget_mode: 'strict' } } });
    writeSettings(cwd, 'settings.local.json', {
      specbox: { implement: { task_isolation: { task_budget_mode: 'warn' } } },
    });
    const r = runHook({ tool_name: 'Agent', tool_input: { prompt: 'x'.repeat(80000) } }, cwd);
    assert.equal(r.code, 0, 'el modo local («warn») debe ganar al compartido («strict»)');
    assert.match(r.note, /se pasa de presupuesto/);
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
  testHookRunsForRealAgentPayloadAndRecordsTheName,
  testHookStillRunsForTask,
  testMatcherCoversAgentAndTask,
  testRealAgentPayloadWarnsAtOneTokenBudget,
  testReadsTheTemplateLocationInSettingsJson,
  testLocalSettingsWinOverShared,
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
