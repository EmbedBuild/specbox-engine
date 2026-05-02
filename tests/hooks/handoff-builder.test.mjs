#!/usr/bin/env node
/**
 * Smoke tests for handoff-builder.mjs.
 *
 * Run: node tests/hooks/handoff-builder.test.mjs
 * Exit: 0 on all pass, 1 on any failure.
 *
 * No external test framework — uses node:assert/strict directly.
 */

import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync, existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execSync } from 'node:child_process';

import {
  computeSessionId,
  buildHandoffData,
  renderHandoff,
  writeHandoff,
} from '../../.claude/hooks/lib/handoff-builder.mjs';

let pass = 0;
let fail = 0;
const failures = [];

function test(name, fn) {
  try {
    fn();
    pass++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    fail++;
    failures.push({ name, error: e.message });
    console.log(`  ✗ ${name}: ${e.message}`);
  }
}

function withTempRepo(fn) {
  const original = process.cwd();
  const dir = mkdtempSync(join(tmpdir(), 'handoff-test-'));
  try {
    process.chdir(dir);
    execSync('git init -q', { stdio: 'ignore' });
    execSync('git config user.email test@test', { stdio: 'ignore' });
    execSync('git config user.name test', { stdio: 'ignore' });
    writeFileSync('README.md', '# test\n');
    execSync('git add . && git commit -q -m "init"', { stdio: 'ignore' });
    fn(dir);
  } finally {
    process.chdir(original);
    rmSync(dir, { recursive: true, force: true });
  }
}

console.log('handoff-builder smoke tests');
console.log('===========================');

test('computeSessionId is deterministic for same inputs', () => {
  const a = computeSessionId('/repo/x', '2026-05-02T10:00:00Z');
  const b = computeSessionId('/repo/x', '2026-05-02T20:00:00Z');
  assert.equal(a, b, 'same date should yield same id');
  assert.equal(a.length, 12);
});

test('computeSessionId differs across cwds', () => {
  const a = computeSessionId('/repo/x', '2026-05-02T10:00:00Z');
  const b = computeSessionId('/repo/y', '2026-05-02T10:00:00Z');
  assert.notEqual(a, b);
});

test('buildHandoffData returns required fields in clean repo', () => {
  withTempRepo(() => {
    const data = buildHandoffData({ trigger: 'manual' });
    assert.ok(data.generated_at);
    assert.equal(data.schema_version, 1);
    assert.ok(data.project);
    assert.ok(data.session_id);
    assert.equal(data.trigger, 'manual');
    assert.equal(data.ttl_minutes, 1440);
    assert.ok(data.branch);
    assert.equal(data.active_uc, null);
    assert.equal(data.active_uc_display, 'none');
    assert.equal(data.healing_events, 0);
    assert.equal(data.blocking_feedback, 0);
    assert.deepEqual(data.pointers, { plan: null, prd: null, checkpoint: null });
  });
});

test('buildHandoffData picks up active_uc from .quality/active_uc.json', () => {
  withTempRepo(() => {
    mkdirSync('.quality', { recursive: true });
    writeFileSync('.quality/active_uc.json', JSON.stringify({
      uc_id: 'UC-042',
      started_at: '2026-05-02T10:00:00Z',
    }));
    const data = buildHandoffData();
    assert.equal(data.active_uc, 'UC-042');
    assert.equal(data.active_uc_display, 'UC-042');
  });
});

test('buildHandoffData includes phase from latest checkpoint', () => {
  withTempRepo(() => {
    mkdirSync('.quality/evidence/UC-042', { recursive: true });
    writeFileSync('.quality/active_uc.json', JSON.stringify({ uc_id: 'UC-042' }));
    writeFileSync('.quality/evidence/UC-042/checkpoint.json', JSON.stringify({
      feature: 'UC-042',
      phase: 3,
      phase_name: 'UI/UX',
      branch: 'feature/uc-042',
      timestamp: '2026-05-02T10:00:00Z',
    }));
    const data = buildHandoffData();
    assert.match(data.active_uc_display, /Phase 3 — UI\/UX/);
  });
});

test('buildHandoffData detects freeform backend', () => {
  withTempRepo(() => {
    mkdirSync('doc/tracking', { recursive: true });
    writeFileSync('doc/tracking/items.json', '{}');
    const data = buildHandoffData();
    assert.equal(data.backend, 'freeform');
  });
});

test('buildHandoffData reads backend_type from settings.local.json', () => {
  withTempRepo(() => {
    mkdirSync('.claude', { recursive: true });
    writeFileSync('.claude/settings.local.json', JSON.stringify({
      specbox: { backend_type: 'plane' },
    }));
    const data = buildHandoffData();
    assert.equal(data.backend, 'plane');
  });
});

test('buildHandoffData counts healing events across features', () => {
  withTempRepo(() => {
    mkdirSync('.quality/evidence/UC-001', { recursive: true });
    mkdirSync('.quality/evidence/UC-002', { recursive: true });
    writeFileSync('.quality/evidence/UC-001/healing.jsonl', '{"a":1}\n{"a":2}\n');
    writeFileSync('.quality/evidence/UC-002/healing.jsonl', '{"b":1}\n');
    const data = buildHandoffData();
    assert.equal(data.healing_events, 3);
  });
});

test('buildHandoffData counts only critical/major open feedback', () => {
  withTempRepo(() => {
    mkdirSync('.quality/evidence/feature-a', { recursive: true });
    writeFileSync('.quality/evidence/feature-a/FB-001.json', JSON.stringify({
      status: 'open', severity: 'critical',
    }));
    writeFileSync('.quality/evidence/feature-a/FB-002.json', JSON.stringify({
      status: 'open', severity: 'minor',
    }));
    writeFileSync('.quality/evidence/feature-a/FB-003.json', JSON.stringify({
      status: 'resolved', severity: 'critical',
    }));
    const data = buildHandoffData();
    assert.equal(data.blocking_feedback, 1);
  });
});

test('renderHandoff produces valid frontmatter + all sections', () => {
  const data = {
    generated_at: '2026-05-02T10:00:00Z',
    schema_version: 1,
    project: 'test',
    session_id: 'abc123',
    trigger: 'manual',
    ttl_minutes: 1440,
    branch: 'main',
    active_uc: null,
    active_uc_display: 'none',
    backend: 'freeform',
    last_commit_sha: 'abc',
    last_commit_subject: 'init',
    healing_events: 0,
    blocking_feedback: 0,
    context_tokens_est: 0,
    hot_files: [],
    pointers: { plan: null, prd: null, checkpoint: null },
  };
  const md = renderHandoff(data, {});
  assert.match(md, /^---\n/);
  assert.match(md, /generated_at: 2026-05-02T10:00:00Z/);
  assert.match(md, /## State snapshot/);
  assert.match(md, /## What this session did/);
  assert.match(md, /## Decisions taken \(with key\)/);
  assert.match(md, /## Open questions/);
  assert.match(md, /## Hot files/);
  assert.match(md, /## Next concrete step/);
  assert.match(md, /## Pointers para la próxima sesión/);
});

test('renderHandoff redacts stripe live keys in next_step', () => {
  const data = buildHandoffData({ trigger: 'manual' });
  // Build the fake key at runtime so the source file does not match
  // GitHub secret-scanning patterns. The redactor must catch it anyway.
  const fakeKey = ['sk', 'live', 'abc123XYZdef456ghi789jkl012mno345pqr'].join('_');
  const md = renderHandoff(data, {
    next_concrete_step: `Use ${fakeKey} to charge`,
  });
  assert.ok(!md.includes(fakeKey), 'stripe key should be redacted');
  assert.match(md, /<redacted-stripe-key>/);
});

test('writeHandoff writes valid file to disk', () => {
  withTempRepo(() => {
    const out = writeHandoff(
      {
        what_this_session_did: ['did one thing'],
        decisions_taken: [],
        open_questions: [],
        next_concrete_step: 'do next thing',
      },
      { trigger: 'manual' },
    );
    assert.equal(out.path, '.quality/handoff.md');
    assert.ok(existsSync('.quality/handoff.md'));
    const content = readFileSync('.quality/handoff.md', 'utf-8');
    assert.match(content, /## State snapshot/);
    assert.match(content, /- did one thing/);
    assert.match(content, /do next thing/);
  });
});

test('writeHandoff is idempotent (overwrites cleanly)', () => {
  withTempRepo(() => {
    writeHandoff({ next_concrete_step: 'step 1' }, { trigger: 'manual' });
    writeHandoff({ next_concrete_step: 'step 2' }, { trigger: 'manual' });
    const content = readFileSync('.quality/handoff.md', 'utf-8');
    assert.match(content, /step 2/);
    assert.ok(!content.includes('step 1'), 'first content should be overwritten');
  });
});

console.log('===========================');
console.log(`${pass} passed, ${fail} failed`);
if (fail > 0) {
  console.log('\nFailures:');
  for (const f of failures) console.log(`  - ${f.name}: ${f.error}`);
  process.exit(1);
}
process.exit(0);
