/**
 * functional_suitability.mjs — completeness, correctness, appropriateness.
 * Port of server/audit/analyzers/functional_suitability.py (UC-663).
 *
 * Evidence: SpecBox AC status + AG-09 acceptance verdicts (from local signals).
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding, round3,
} from '../lib/schema.mjs';
import { clamp, scoreFromFindings, trafficLight } from '../lib/scoring.mjs';

export const characteristic = SquareCharacteristic.FUNCTIONAL_SUITABILITY;

export function analyze(ctx) {
  const signals = ctx.signals || {};
  const ac = signals.ac_status || {};
  const acTotal = Number(ac.total || 0);
  const acDone = Number(ac.completed || 0);
  const completionRatio = acTotal ? acDone / acTotal : 1.0;

  const findings = [];
  if (acTotal && completionRatio < 0.5) {
    findings.push(finding({
      severity: Severity.HIGH,
      description: `Only ${acDone}/${acTotal} acceptance criteria completed (${pct(completionRatio)}).`,
      remediation: 'Complete remaining ACs via /implement before shipping.',
    }));
  } else if (acTotal && completionRatio < 0.8) {
    findings.push(finding({
      severity: Severity.MEDIUM,
      description: `${acDone}/${acTotal} ACs completed — functional gaps remain.`,
      remediation: 'Review pending ACs; confirm they are still required.',
    }));
  }

  const acceptance = signals.acceptance || {};
  const rejected = Number(acceptance.rejected || 0);
  if (rejected) {
    findings.push(finding({
      severity: Severity.HIGH,
      description: `${rejected} acceptance validations rejected (AG-09b).`,
      remediation: 'Inspect AG-09b evidence and fix root causes.',
    }));
  }

  const base = completionRatio * 100;
  const score = findings.length ? scoreFromFindings(findings, base) : clamp(base);

  const raw = {
    ac_total: acTotal,
    ac_completed: acDone,
    ac_completion_ratio: round3(completionRatio),
    acceptance_rejected: rejected,
    acceptance_accepted: Number(acceptance.accepted || 0),
  };

  const justification =
    `Score derived from AC completion ratio (${acDone}/${acTotal}) `
    + `minus severity-weighted penalties from ${findings.length} finding(s).`;

  return characteristicResult({
    characteristic, score, traffic_light: trafficLight(score),
    justification, raw_metrics: raw, findings,
  });
}

function pct(r) {
  return `${Math.round(r * 100)}%`;
}
