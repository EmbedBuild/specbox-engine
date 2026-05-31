/**
 * lib/scoring.mjs — Client-side mirror of server/audit/scoring.py (UC-663).
 *
 * Pure functions, no I/O. Kept numerically identical to the Python so a report
 * built on the client scores the same as the legacy server-side audit did.
 */

import { Severity, TrafficLight } from './schema.mjs';

// Traffic light thresholds (score out of 100) — mirror scoring.py.
export const GREEN_MIN = 80.0;
export const AMBER_MIN = 60.0;

export function trafficLight(score) {
  if (score >= GREEN_MIN) return TrafficLight.GREEN;
  if (score >= AMBER_MIN) return TrafficLight.AMBER;
  return TrafficLight.RED;
}

export function clamp(value, lo = 0.0, hi = 100.0) {
  return Math.max(lo, Math.min(hi, value));
}

// Severity → points deducted from a starting score (mirror SEVERITY_PENALTY).
export const SEVERITY_PENALTY = Object.freeze({
  [Severity.CRITICAL]: 25.0,
  [Severity.HIGH]: 12.0,
  [Severity.MEDIUM]: 5.0,
  [Severity.LOW]: 2.0,
  [Severity.INFO]: 0.5,
});

/**
 * Deduct points from `base` per finding severity. Floor at 0.
 * @param {Array<{severity:string}>} findings
 * @param {number} [base]
 */
export function scoreFromFindings(findings, base = 100.0) {
  let score = base;
  for (const f of findings) {
    score -= SEVERITY_PENALTY[f.severity] ?? 1.0;
  }
  return clamp(score);
}

/** Normalize a 0..1 ratio to 0..100. If invert, higher ratio is worse. */
export function ratioToScore(ratio, invert = false) {
  const r = Math.max(0.0, Math.min(1.0, ratio));
  return clamp(invert ? (1 - r) * 100 : r * 100);
}

// ------ Maintainability 60/40 mix ------

export const CLASSIC_WEIGHT = 0.6;
export const SPECBOX_WEIGHT = 0.4;

/**
 * Combine classic industry metrics (60%) with SpecBox MCP signals (40%).
 * @returns {[number, object]} [finalScore, breakdown]
 */
export function maintainabilityScore(classicScore, specboxScore) {
  const final = classicScore * CLASSIC_WEIGHT + specboxScore * SPECBOX_WEIGHT;
  const r2 = (x) => Math.round((x + Number.EPSILON) * 100) / 100;
  const breakdown = {
    classic_60: {
      score: r2(classicScore),
      weight: CLASSIC_WEIGHT,
      contribution: r2(classicScore * CLASSIC_WEIGHT),
    },
    specbox_40: {
      score: r2(specboxScore),
      weight: SPECBOX_WEIGHT,
      contribution: r2(specboxScore * SPECBOX_WEIGHT),
    },
    formula: '0.60 * classic + 0.40 * specbox',
  };
  return [clamp(final), breakdown];
}

// ------ Global aggregation ------

/** Simple mean of non-skipped characteristic scores (mirror global_score). */
export function globalScore(results) {
  const active = results.filter((r) => !r.skipped).map((r) => r.score);
  if (active.length === 0) return 0.0;
  return clamp(active.reduce((a, b) => a + b, 0) / active.length);
}
