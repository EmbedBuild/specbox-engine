/**
 * reliability.mjs — maturity, availability, fault tolerance, recoverability.
 * Port of server/audit/analyzers/reliability.py (UC-663).
 *
 * Signals: SpecBox healing summary + test pass rate (from local signals).
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding, round3,
} from '../lib/schema.mjs';
import { clamp, scoreFromFindings, trafficLight } from '../lib/scoring.mjs';

export const characteristic = SquareCharacteristic.RELIABILITY;

export function analyze(ctx) {
  const signals = ctx.signals || {};
  const healing = signals.healing || {};
  const total = Number(healing.total_events || 0);
  const resolved = Number(healing.resolved || 0);
  const failed = Number(healing.failed || 0);
  const healingRatio = total ? resolved / total : 1.0;

  const tests = signals.tests || {};
  const passed = Number(tests.passed || 0);
  const totalTests = Number(tests.total || 0);
  const passRate = totalTests ? passed / totalTests : 1.0;

  const findings = [];
  if (total && healingRatio < 0.7) {
    findings.push(finding({
      severity: Severity.HIGH,
      description: `Self-healing resolution ratio is ${pct(healingRatio)} (${resolved}/${total}).`,
      remediation: 'Review healing log for systemic failures; reduce healing reliance.',
    }));
  }
  if (totalTests && passRate < 0.95) {
    findings.push(finding({
      severity: Severity.MEDIUM,
      description: `Test pass rate ${pct(passRate)} (${passed}/${totalTests}).`,
      remediation: 'Fix failing tests before release.',
    }));
  }

  const base = passRate * 60 + healingRatio * 40;
  const score = scoreFromFindings(findings, base);

  const raw = {
    healing_events_total: total,
    healing_resolved: resolved,
    healing_failed: failed,
    healing_resolution_ratio: round3(healingRatio),
    tests_total: totalTests,
    tests_passed: passed,
    test_pass_rate: round3(passRate),
  };
  const justification =
    `Score = test_pass_rate*60 + healing_ratio*40 `
    + `(${pct(passRate)} / ${pct(healingRatio)}) minus finding penalties.`;

  return characteristicResult({
    characteristic, score: clamp(score), traffic_light: trafficLight(score),
    justification, raw_metrics: raw, findings,
  });
}

function pct(r) {
  return `${Math.round(r * 100)}%`;
}
