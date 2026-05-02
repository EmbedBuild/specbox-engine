#!/usr/bin/env node
/**
 * Smoke tests for session-start.mjs.
 * Run: node tests/hooks/session-start.test.mjs
 */

import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync, utimesSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { execSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HOOK_PATH = resolve(fileURLToPath(import.meta.url), '..', '..', '..', '.claude/hooks/session-start.mjs');

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
  const dir = mkdtempSync(join(tmpdir(), 'session-start-test-'));
  const original = process.cwd();
  try {
    process.chdir(dir);
    execSync('git init -q', { stdio: 'ignore' });
    execSync('git config user.email t@t', { stdio: 'ignore' });
    execSync('git config user.name t', { stdio: 'ignore' });
    fn(dir);
  } finally {
    process.chdir(original);
    rmSync(dir, { recursive: true, force: true });
  }
}

function runHook() {
  const r = spawnSync('node', [HOOK_PATH], { encoding: 'utf-8' });
  return { stdout: r.stdout, stderr: r.stderr, status: r.status };
}

console.log('session-start hook smoke tests');
console.log('==============================');

test('emits nothing when no state files exist', () => {
  withTempRepo(() => {
    const r = runHook();
    assert.equal(r.status, 0);
    assert.equal(r.stdout.trim(), '');
  });
});

test('emits handoff content when .quality/handoff.md is fresh', () => {
  withTempRepo(() => {
    mkdirSync('.quality', { recursive: true });
    writeFileSync('.quality/handoff.md', `---
generated_at: 2026-05-02T10:00:00Z
generator: specbox-handoff-v1
schema_version: 1
project: t
session_id: abc123
trigger: manual
ttl_minutes: 1440
branch: main
active_uc: null
---

# SpecBox Handoff — t

## State snapshot
- **Branch**: main

## What this session did
- did stuff

## Decisions taken (with key)
_(none)_

## Open questions
_(none)_

## Hot files (top N by edits this session)
_(none)_

## Next concrete step
do thing

## Pointers para la próxima sesión
_(none)_
`);
    const r = runHook();
    assert.equal(r.status, 0);
    assert.ok(r.stdout.length > 0);
    const out = JSON.parse(r.stdout);
    assert.equal(out.hookSpecificOutput.hookEventName, 'SessionStart');
    assert.match(out.hookSpecificOutput.additionalContext, /\[FRESH\]/);
    assert.match(out.hookSpecificOutput.additionalContext, /SpecBox Handoff/);
    assert.match(out.hookSpecificOutput.additionalContext, /do thing/);
  });
});

test('marks handoff as STALE when older than ttl', () => {
  withTempRepo(() => {
    mkdirSync('.quality', { recursive: true });
    writeFileSync('.quality/handoff.md', '---\nfoo: bar\n---\n# old\n');
    // Set mtime to 2 days ago
    const old = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000);
    utimesSync('.quality/handoff.md', old, old);
    const r = runHook();
    const out = JSON.parse(r.stdout);
    assert.match(out.hookSpecificOutput.additionalContext, /\[STALE\]/);
  });
});

test('falls back to active_uc + checkpoint when no handoff', () => {
  withTempRepo(() => {
    mkdirSync('.quality/evidence/UC-099', { recursive: true });
    writeFileSync('.quality/active_uc.json', JSON.stringify({ uc_id: 'UC-099' }));
    writeFileSync('.quality/evidence/UC-099/checkpoint.json', JSON.stringify({
      feature: 'UC-099',
      phase: 5,
      phase_name: 'QA',
      branch: 'feature/uc-099',
      status: 'complete',
    }));
    const r = runHook();
    assert.equal(r.status, 0);
    const out = JSON.parse(r.stdout);
    assert.match(out.hookSpecificOutput.additionalContext, /Live State/);
    assert.match(out.hookSpecificOutput.additionalContext, /UC-099/);
    assert.match(out.hookSpecificOutput.additionalContext, /phase=5/);
  });
});

test('extracts auto zones from app_spec.md', () => {
  withTempRepo(() => {
    mkdirSync('doc/app', { recursive: true });
    writeFileSync('doc/app/app_spec.md', `# App Spec

<!-- @specbox:zone start kind="auto" id="tracking_backend" -->
- Backend: freeform
- Path: doc/tracking
<!-- @specbox:zone end -->

<!-- @specbox:zone start kind="auto" id="autopilot" -->
- Level: equilibrado
- Queue enabled: false
<!-- @specbox:zone end -->
`);
    const r = runHook();
    assert.equal(r.status, 0);
    const out = JSON.parse(r.stdout);
    assert.match(out.hookSpecificOutput.additionalContext, /Canonical/);
    assert.match(out.hookSpecificOutput.additionalContext, /freeform/);
    assert.match(out.hookSpecificOutput.additionalContext, /equilibrado/);
  });
});

test('stays under MAX_CHARS budget', () => {
  withTempRepo(() => {
    mkdirSync('.quality', { recursive: true });
    writeFileSync('.quality/handoff.md', 'x'.repeat(50000));
    const r = runHook();
    const out = JSON.parse(r.stdout);
    assert.ok(out.hookSpecificOutput.additionalContext.length <= 14000,
      `output ${out.hookSpecificOutput.additionalContext.length} > 14000`);
  });
});

console.log('==============================');
console.log(`${pass} passed, ${fail} failed`);
if (fail > 0) {
  for (const f of failures) console.log(`  - ${f.name}: ${f.error}`);
  process.exit(1);
}
process.exit(0);
