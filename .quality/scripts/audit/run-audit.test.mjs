/**
 * Tests for the client-side ISO/IEC 25010 audit analyzers + orchestrator (UC-663).
 *
 * Zero-dependency node:test. Run with: node --test .quality/scripts/audit/
 *
 * Coverage:
 *   AC-01 — each of the 8 SQuaRE analyzers produces a schema-valid block.
 *   AC-03 — run-audit.mjs orchestrates the 8 in canonical order, computes the
 *           global score, honours --scope, and degrades a crashing analyzer to
 *           a skipped block instead of failing the whole audit.
 *   plus: scoring parity with server/audit/scoring.py, signals from local FS.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { SQUARE_ORDER, SquareCharacteristic, Severity, TrafficLight } from './lib/schema.mjs';
import {
  scoreFromFindings, maintainabilityScore, globalScore, trafficLight, clamp,
} from './lib/scoring.mjs';
import { fetchSpecboxSignals } from './lib/signals.mjs';
import { buildReport } from './run-audit.mjs';

import * as functional from './analyzers/functional_suitability.mjs';
import * as performance from './analyzers/performance_efficiency.mjs';
import * as compatibility from './analyzers/compatibility.mjs';
import * as usability from './analyzers/usability.mjs';
import * as reliability from './analyzers/reliability.mjs';
import * as security from './analyzers/security.mjs';
import * as maintainability from './analyzers/maintainability.mjs';
import * as portability from './analyzers/portability.mjs';

// ── Fixture: a tiny but realistic git repo ──────────────────────────────────

function makeFixtureRepo() {
  const root = mkdtempSync(join(tmpdir(), 'audit-fixture-'));
  // Make it a git repo so commit/root resolution works.
  execSync('git init -q', { cwd: root });
  execSync('git config user.email t@t.dev && git config user.name t', { cwd: root });

  writeFileSync(join(root, 'README.md'), '# Fixture\n');
  writeFileSync(join(root, 'CLAUDE.md'), 'project\n');
  writeFileSync(join(root, 'pyproject.toml'), '[project]\nname="x"\n');
  writeFileSync(join(root, 'uv.lock'), '# lock\n');
  writeFileSync(join(root, 'Dockerfile'), 'FROM python:3.12\n');
  writeFileSync(join(root, '.env.example'), 'KEY=\n');
  mkdirSync(join(root, 'src'));
  writeFileSync(join(root, 'src', 'main.py'), 'def f():\n    return 1\n');
  mkdirSync(join(root, 'tests'));
  writeFileSync(join(root, 'tests', 'test_main.py'), 'def test_f():\n    assert True\n');
  mkdirSync(join(root, 'docs'));
  writeFileSync(join(root, 'docs', 'guide.md'), 'docs\n');

  execSync('git add -A && git commit -q -m init', { cwd: root });
  return root;
}

function cleanup(root) {
  rmSync(root, { recursive: true, force: true });
}

const NEUTRAL_SIGNALS = {
  ac_status: { total: 10, completed: 9 },
  evidence: { uc_total: 5, uc_with_evidence: 5 },
  healing: { total_events: 0, resolved: 0, failed: 0 },
  board: { us_total: 3, us_blocked: 0 },
  acceptance: { accepted: 9, rejected: 0 },
  tests: { total: 100, passed: 100 },
  prd_divergence_ratio: 0.0,
};

function ctxFor(root) {
  return { root, projectName: 'fixture', stack: 'python', infra: [], signals: NEUTRAL_SIGNALS };
}

// A block is schema-valid if it has the required keys with the right types.
function assertValidBlock(block, expectedId) {
  assert.equal(block.id, expectedId, `block id must be ${expectedId}`);
  assert.equal(typeof block.score, 'number');
  assert.ok(block.score >= 0 && block.score <= 100, 'score in 0..100');
  assert.ok(Object.values(TrafficLight).includes(block.traffic_light), 'valid traffic light');
  assert.equal(typeof block.justification, 'string');
  assert.equal(typeof block.raw_metrics, 'object');
  assert.ok(Array.isArray(block.findings), 'findings is array');
  assert.ok(Array.isArray(block.recommendations), 'recommendations is array');
  assert.equal(typeof block.skipped, 'boolean');
  for (const f of block.findings) {
    assert.ok(Object.values(Severity).includes(f.severity), 'finding severity valid');
    assert.equal(typeof f.description, 'string');
    assert.equal(typeof f.remediation, 'string');
  }
}

// ── AC-01: each analyzer produces a valid block ─────────────────────────────

const ANALYZER_CASES = [
  [functional, SquareCharacteristic.FUNCTIONAL_SUITABILITY],
  [performance, SquareCharacteristic.PERFORMANCE_EFFICIENCY],
  [compatibility, SquareCharacteristic.COMPATIBILITY],
  [usability, SquareCharacteristic.USABILITY],
  [reliability, SquareCharacteristic.RELIABILITY],
  [security, SquareCharacteristic.SECURITY],
  [maintainability, SquareCharacteristic.MAINTAINABILITY],
  [portability, SquareCharacteristic.PORTABILITY],
];

for (const [mod, charId] of ANALYZER_CASES) {
  test(`AC-01: ${charId} analyzer produces a valid block`, () => {
    const root = makeFixtureRepo();
    try {
      const out = mod.analyze(ctxFor(root));
      const block = out && out.result ? out.result : out;
      assertValidBlock(block, charId);
    } finally {
      cleanup(root);
    }
  });
}

test('AC-01: maintainability block always includes the 60/40 breakdown', () => {
  const root = makeFixtureRepo();
  try {
    const { result } = maintainability.analyze(ctxFor(root));
    assert.ok(result.breakdown, 'breakdown present');
    assert.equal(result.breakdown.formula, '0.60 * classic + 0.40 * specbox');
    assert.ok('classic_60' in result.breakdown && 'specbox_40' in result.breakdown);
  } finally {
    cleanup(root);
  }
});

test('AC-01: security/maintainability return { result, toolsUsed }', () => {
  const root = makeFixtureRepo();
  try {
    const sec = security.analyze(ctxFor(root));
    assert.ok(Array.isArray(sec.toolsUsed), 'security toolsUsed array');
    const maint = maintainability.analyze(ctxFor(root));
    assert.ok(Array.isArray(maint.toolsUsed), 'maintainability toolsUsed array');
    // Missing optional tools must be reported, never crash.
    for (const t of [...sec.toolsUsed, ...maint.toolsUsed]) {
      assert.ok(['ok', 'missing', 'timeout', 'error'].includes(t.status));
    }
  } finally {
    cleanup(root);
  }
});

// ── AC-03: orchestrator ─────────────────────────────────────────────────────

test('AC-03: buildReport emits all 8 characteristics in canonical order', () => {
  const root = makeFixtureRepo();
  try {
    const report = buildReport({ root, project: 'fixture', stack: 'python', signals: NEUTRAL_SIGNALS });
    assert.equal(report.characteristics.length, 8);
    assert.deepEqual(report.characteristics.map((c) => c.id), SQUARE_ORDER);
    assert.equal(report.audit_schema_version, '1.0');
    assert.match(report.audit_id, /^audit_\d{8}T\d{6}Z$/);
    assert.equal(typeof report.global_score, 'number');
    assert.ok(Object.values(TrafficLight).includes(report.global_traffic_light));
    assert.equal(report.project, 'fixture');
    assert.equal(report.commit.length >= 7 || report.commit === 'unknown', true);
  } finally {
    cleanup(root);
  }
});

test('AC-03: --scope limits to one characteristic, others skipped & not penalizing', () => {
  const root = makeFixtureRepo();
  try {
    const report = buildReport({ root, scope: SquareCharacteristic.SECURITY, signals: NEUTRAL_SIGNALS });
    const active = report.characteristics.filter((c) => !c.skipped);
    assert.equal(active.length, 1);
    assert.equal(active[0].id, SquareCharacteristic.SECURITY);
    // global score == the single active block's score (skipped don't count)
    assert.equal(report.global_score, Math.round((active[0].score + Number.EPSILON) * 100) / 100);
  } finally {
    cleanup(root);
  }
});

test('AC-03: buildReport never throws even when the scan path does not exist', () => {
  // Robustness: a bogus root must not sink the whole audit — every block must
  // still be a number (low-scored or skipped), never a thrown exception.
  const report = buildReport({
    root: '/nonexistent/path/xyz', project: 'p', stack: 'unknown',
    commit: 'deadbee', signals: NEUTRAL_SIGNALS,
  });
  assert.equal(report.characteristics.length, 8);
  assert.ok(report.characteristics.every((c) => typeof c.score === 'number'));
});

// ── scoring parity with scoring.py ──────────────────────────────────────────

test('scoreFromFindings deducts the documented severity penalties', () => {
  assert.equal(scoreFromFindings([], 100), 100);
  assert.equal(scoreFromFindings([{ severity: Severity.CRITICAL }], 100), 75);
  assert.equal(scoreFromFindings([{ severity: Severity.HIGH }], 100), 88);
  assert.equal(scoreFromFindings([{ severity: Severity.MEDIUM }], 100), 95);
  assert.equal(scoreFromFindings([{ severity: Severity.LOW }], 100), 98);
  assert.equal(scoreFromFindings([{ severity: Severity.INFO }], 100), 99.5);
  // floors at 0
  assert.equal(scoreFromFindings(Array(5).fill({ severity: Severity.CRITICAL }), 100), 0);
});

test('maintainabilityScore is 0.60*classic + 0.40*specbox', () => {
  const [score, breakdown] = maintainabilityScore(80, 60);
  assert.equal(score, 72); // 48 + 24
  assert.equal(breakdown.classic_60.contribution, 48);
  assert.equal(breakdown.specbox_40.contribution, 24);
});

test('globalScore is the mean of non-skipped scores; traffic light thresholds', () => {
  assert.equal(globalScore([{ score: 80, skipped: false }, { score: 60, skipped: false }]), 70);
  assert.equal(globalScore([{ score: 80, skipped: false }, { score: 0, skipped: true }]), 80);
  assert.equal(trafficLight(80), TrafficLight.GREEN);
  assert.equal(trafficLight(79.99), TrafficLight.AMBER);
  assert.equal(trafficLight(60), TrafficLight.AMBER);
  assert.equal(trafficLight(59.99), TrafficLight.RED);
  assert.equal(clamp(150), 100);
  assert.equal(clamp(-5), 0);
});

// ── signals from local FS ───────────────────────────────────────────────────

test('fetchSpecboxSignals reads AC/board from doc/tracking/items.json', () => {
  const root = makeFixtureRepo();
  try {
    mkdirSync(join(root, 'doc', 'tracking'), { recursive: true });
    const items = [
      { id: 'us1', labels: ['US'], state: 'done' },
      { id: 'us2', labels: ['US'], state: 'blocked' },
      { id: 'ac1', labels: ['AC'], state: 'done' },
      { id: 'ac2', labels: ['AC'], state: 'todo' },
      { id: 'ac3', meta: { tipo: 'AC' }, state: 'done' },
    ];
    writeFileSync(join(root, 'doc', 'tracking', 'items.json'), JSON.stringify(items));
    const sig = fetchSpecboxSignals(root);
    assert.equal(sig.ac_status.total, 3);
    assert.equal(sig.ac_status.completed, 2);
    assert.equal(sig.board.us_total, 2);
    assert.equal(sig.board.us_blocked, 1);
  } finally {
    cleanup(root);
  }
});

test('fetchSpecboxSignals returns neutral defaults when no board/quality tree', () => {
  const root = mkdtempSync(join(tmpdir(), 'audit-empty-'));
  try {
    const sig = fetchSpecboxSignals(root);
    assert.deepEqual(sig.ac_status, { total: 0, completed: 0 });
    assert.deepEqual(sig.healing, { total_events: 0, resolved: 0, failed: 0 });
    assert.equal(sig.prd_divergence_ratio, 0.0);
  } finally {
    cleanup(root);
  }
});

// ── portability concurrency regression (UC-663 bug fix) ─────────────────────

test('portability analyzer is correct under concurrent calls (no shared regex state)', async () => {
  // Regression for the module-level /g regex bug: a shared lastIndex across
  // concurrent analyze() calls corrupted hardcoded-path iteration. Run several
  // analyses in parallel and assert every block is valid.
  const roots = Array.from({ length: 8 }, makeFixtureRepo);
  try {
    const results = await Promise.all(
      roots.map((r) => Promise.resolve().then(() => portability.analyze(ctxFor(r)))),
    );
    for (const block of results) {
      assertValidBlock(block, SquareCharacteristic.PORTABILITY);
    }
  } finally {
    roots.forEach(cleanup);
  }
});
