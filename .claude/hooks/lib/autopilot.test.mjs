#!/usr/bin/env node
/**
 * autopilot.test.mjs — Tests for the autopilot policy engine.
 * Run: node .claude/hooks/lib/autopilot.test.mjs
 *
 * Uses Node's built-in test runner (node:test) — zero external deps.
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, mkdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';

import {
  DECISION_KEYS,
  loadAutopilotConfig,
  evaluateDecision,
  logAutoDecision,
  evaluateAndLog,
} from './autopilot.mjs';

// ── Test helpers ─────────────────────────────────────────────────────

function makeProject(level, extra = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'specbox-autopilot-'));
  mkdirSync(join(dir, '.claude'), { recursive: true });
  const settings = level
    ? { specbox: { autopilot: { level, ...extra } } }
    : extra && Object.keys(extra).length > 0
      ? { specbox: { autopilot: extra } }
      : {};
  writeFileSync(join(dir, '.claude', 'settings.local.json'), JSON.stringify(settings, null, 2));
  return dir;
}

function readLog(projectPath) {
  const path = join(projectPath, '.quality', 'autopilot_decisions.jsonl');
  if (!existsSync(path)) return [];
  return readFileSync(path, 'utf-8')
    .trim()
    .split('\n')
    .filter(Boolean)
    .map((l) => JSON.parse(l));
}

// ── loadAutopilotConfig ──────────────────────────────────────────────

test('loadAutopilotConfig returns "low" when no config file exists', () => {
  const dir = mkdtempSync(join(tmpdir(), 'specbox-noconfig-'));
  const cfg = loadAutopilotConfig(dir);
  assert.equal(cfg.level, 'low');
  assert.equal(cfg.image_budget_eur_per_feature, 5);
  assert.deepEqual(cfg.auto_confirm_overrides, []);
  assert.deepEqual(cfg.always_ask_overrides, []);
  assert.equal(cfg.queue_enabled, false);
});

test('loadAutopilotConfig honors explicit level', () => {
  const dir = makeProject('equilibrado');
  assert.equal(loadAutopilotConfig(dir).level, 'equilibrado');
});

test('loadAutopilotConfig falls back to "low" on invalid level', () => {
  const dir = makeProject('chaotic');
  assert.equal(loadAutopilotConfig(dir).level, 'low');
});

test('loadAutopilotConfig reads custom budget', () => {
  const dir = makeProject('equilibrado', { image_budget_eur_per_feature: 12 });
  assert.equal(loadAutopilotConfig(dir).image_budget_eur_per_feature, 12);
});

test('loadAutopilotConfig reads override arrays', () => {
  const dir = makeProject('equilibrado', {
    auto_confirm_overrides: ['veg_preview'],
    always_ask_overrides: ['tokens_confirmation'],
  });
  const cfg = loadAutopilotConfig(dir);
  assert.deepEqual(cfg.auto_confirm_overrides, ['veg_preview']);
  assert.deepEqual(cfg.always_ask_overrides, ['tokens_confirmation']);
});

// ── evaluateDecision: tier defaults ──────────────────────────────────

test('low tier (default) asks for cosmetic decisions', () => {
  const dir = mkdtempSync(join(tmpdir(), 'specbox-low-'));
  const result = evaluateDecision('tokens_confirmation', { projectPath: dir });
  assert.equal(result.action, 'ask');
  assert.equal(result.autoConfirm, false);
});

test('equilibrado auto-confirms cosmetic decisions', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('tokens_confirmation', { projectPath: dir });
  assert.equal(result.action, 'auto');
  assert.equal(result.autoConfirm, true);
});

test('agresivo auto-confirms cosmetic decisions', () => {
  const dir = makeProject('agresivo');
  assert.equal(evaluateDecision('tokens_confirmation', { projectPath: dir }).autoConfirm, true);
});

test('conservador auto-confirms cosmetic decisions but asks for visual_derived', () => {
  const dir = makeProject('conservador');
  assert.equal(evaluateDecision('tokens_confirmation', { projectPath: dir }).autoConfirm, true);
  assert.equal(evaluateDecision('veg_preview', { projectPath: dir, score: 0.95 }).autoConfirm, false);
});

// ── evaluateDecision: score thresholds ───────────────────────────────

test('equilibrado auto-confirms veg_preview when score >= 0.8', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('veg_preview', { projectPath: dir, score: 0.85 });
  assert.equal(result.autoConfirm, true);
  assert.match(result.reason, /score_0\.85_meets_0\.8/);
});

test('equilibrado asks veg_preview when score < 0.8', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('veg_preview', { projectPath: dir, score: 0.7 });
  assert.equal(result.autoConfirm, false);
  assert.match(result.reason, /score_0\.7_below_0\.8/);
});

test('agresivo auto-confirms veg_preview at lower threshold (0.7)', () => {
  const dir = makeProject('agresivo');
  assert.equal(evaluateDecision('veg_preview', { projectPath: dir, score: 0.75 }).autoConfirm, true);
  assert.equal(evaluateDecision('veg_preview', { projectPath: dir, score: 0.65 }).autoConfirm, false);
});

test('missing score forces ask even when tier would auto', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('veg_preview', { projectPath: dir }); // no score
  assert.equal(result.autoConfirm, false);
  assert.equal(result.reason, 'missing_score_or_threshold');
});

// ── evaluateDecision: budget ─────────────────────────────────────────

test('image_cost_under_budget auto-confirms when costEur <= budget', () => {
  const dir = makeProject('equilibrado', { image_budget_eur_per_feature: 5 });
  const result = evaluateDecision('image_cost_under_budget', { projectPath: dir, costEur: 3.2 });
  assert.equal(result.autoConfirm, true);
});

test('image_cost_under_budget asks when costEur > budget', () => {
  const dir = makeProject('equilibrado', { image_budget_eur_per_feature: 5 });
  const result = evaluateDecision('image_cost_under_budget', { projectPath: dir, costEur: 12 });
  assert.equal(result.autoConfirm, false);
});

// ── Inviolable rules ─────────────────────────────────────────────────

test('image_cost_over_budget always asks (inviolable)', () => {
  for (const level of ['low', 'conservador', 'equilibrado', 'agresivo']) {
    const dir = makeProject(level);
    const result = evaluateDecision('image_cost_over_budget', { projectPath: dir });
    assert.equal(result.autoConfirm, false, `tier ${level} must ask`);
    assert.equal(result.reason, 'inviolable_rule');
  }
});

test('destructive_action always asks (inviolable)', () => {
  for (const level of ['low', 'conservador', 'equilibrado', 'agresivo']) {
    const dir = makeProject(level);
    const result = evaluateDecision('destructive_action', { projectPath: dir });
    assert.equal(result.autoConfirm, false);
    assert.equal(result.reason, 'inviolable_rule');
  }
});

test('branch_to_main_push blocks (not asks) regardless of tier', () => {
  for (const level of ['low', 'conservador', 'equilibrado', 'agresivo']) {
    const dir = makeProject(level);
    const result = evaluateDecision('branch_to_main_push', { projectPath: dir });
    assert.equal(result.action, 'block');
  }
});

test('inviolable rule cannot be bypassed by auto_confirm_overrides', () => {
  const dir = makeProject('agresivo', { auto_confirm_overrides: ['image_cost_over_budget'] });
  const result = evaluateDecision('image_cost_over_budget', { projectPath: dir });
  assert.equal(result.autoConfirm, false, 'inviolable beats override');
});

// ── User overrides ───────────────────────────────────────────────────

test('always_ask_overrides forces ask even at agresivo', () => {
  const dir = makeProject('agresivo', { always_ask_overrides: ['tokens_confirmation'] });
  const result = evaluateDecision('tokens_confirmation', { projectPath: dir });
  assert.equal(result.autoConfirm, false);
  assert.equal(result.reason, 'user_override_always_ask');
});

test('auto_confirm_overrides forces auto for non-inviolable', () => {
  const dir = makeProject('low', { auto_confirm_overrides: ['veg_preview'] });
  const result = evaluateDecision('veg_preview', { projectPath: dir });
  assert.equal(result.autoConfirm, true);
  assert.equal(result.reason, 'user_override_auto_confirm');
});

test('always_ask wins over auto_confirm when both list the key', () => {
  const dir = makeProject('agresivo', {
    auto_confirm_overrides: ['veg_preview'],
    always_ask_overrides: ['veg_preview'],
  });
  const result = evaluateDecision('veg_preview', { projectPath: dir });
  assert.equal(result.autoConfirm, false);
});

// ── App PRD/spec inheritance ─────────────────────────────────────────

test('feature_aesthetic_direction auto-confirms when app_spec exists', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('feature_aesthetic_direction', { projectPath: dir, hasAppSpec: true });
  assert.equal(result.autoConfirm, true);
});

test('feature_aesthetic_direction asks when app_spec missing', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('feature_aesthetic_direction', { projectPath: dir, hasAppSpec: false });
  assert.equal(result.autoConfirm, false);
});

// ── Backend selection ────────────────────────────────────────────────

test('backend_selection defaults to freeform at equilibrado+', () => {
  const dir = makeProject('equilibrado');
  const result = evaluateDecision('backend_selection', { projectPath: dir });
  assert.equal(result.autoConfirm, true);
  assert.equal(result.reason, 'freeform_default_v5_29');
});

test('backend_selection asks at low/conservador', () => {
  for (const level of ['low', 'conservador']) {
    const dir = makeProject(level);
    assert.equal(evaluateDecision('backend_selection', { projectPath: dir }).autoConfirm, false);
  }
});

// ── Unknown decision_key ─────────────────────────────────────────────

test('unknown decision_key returns ask with reason', () => {
  const dir = makeProject('agresivo');
  const result = evaluateDecision('made_up_key', { projectPath: dir });
  assert.equal(result.autoConfirm, false);
  assert.equal(result.reason, 'unknown_decision_key');
});

// ── Logging ──────────────────────────────────────────────────────────

test('logAutoDecision writes JSONL entry to .quality/autopilot_decisions.jsonl', () => {
  const dir = makeProject('equilibrado');
  const decision = evaluateDecision('tokens_confirmation', { projectPath: dir });
  logAutoDecision(decision, { projectPath: dir, feature: 'demo', value: 'derived' });

  const entries = readLog(dir);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].decision_key, 'tokens_confirmation');
  assert.equal(entries[0].level, 'equilibrado');
  assert.equal(entries[0].auto_confirm, true);
  assert.equal(entries[0].feature, 'demo');
  assert.equal(entries[0].value, 'derived');
  assert.ok(entries[0].ts);
});

test('evaluateAndLog only writes when autoConfirm=true', () => {
  const dir = makeProject('equilibrado');
  // tokens_confirmation auto-confirms → log appears
  evaluateAndLog('tokens_confirmation', { projectPath: dir });
  // image_cost_over_budget always asks → no log
  evaluateAndLog('image_cost_over_budget', { projectPath: dir });

  const entries = readLog(dir);
  assert.equal(entries.length, 1);
  assert.equal(entries[0].decision_key, 'tokens_confirmation');
});

test('evaluateAndLog appends multiple entries', () => {
  const dir = makeProject('equilibrado');
  evaluateAndLog('tokens_confirmation', { projectPath: dir });
  evaluateAndLog('stitch_design_per_screen', { projectPath: dir });
  evaluateAndLog('design_system_update_check', { projectPath: dir });

  const entries = readLog(dir);
  assert.equal(entries.length, 3);
});

// ── Catalog completeness ─────────────────────────────────────────────

test('every decision in DECISION_KEYS has all four tiers defined', () => {
  for (const [key, def] of Object.entries(DECISION_KEYS)) {
    for (const tier of ['low', 'conservador', 'equilibrado', 'agresivo']) {
      assert.ok(def.tiers[tier], `${key} missing tier ${tier}`);
    }
  }
});

test('inviolable decisions all have ask or block at every tier', () => {
  for (const [key, def] of Object.entries(DECISION_KEYS)) {
    if (!def.inviolable) continue;
    for (const tier of ['low', 'conservador', 'equilibrado', 'agresivo']) {
      assert.match(
        def.tiers[tier],
        /^(ask|block)$/,
        `${key} at ${tier} is "${def.tiers[tier]}" but should be ask/block`
      );
    }
  }
});
