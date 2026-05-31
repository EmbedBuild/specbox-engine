/**
 * usability.mjs — readability, learnability, accessibility (heuristic v1).
 * Port of server/audit/analyzers/usability.py (UC-663).
 *
 * Signals: README / CLAUDE.md / docs/ / Stitch designs presence.
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding,
} from '../lib/schema.mjs';
import { clamp, scoreFromFindings, trafficLight } from '../lib/scoring.mjs';
import { anyExists, exists, isDir } from '../lib/fs-scan.mjs';

export const characteristic = SquareCharacteristic.USABILITY;

export function analyze(ctx) {
  const root = ctx.root;
  const findings = [];

  const hasReadme = anyExists(root, ['README.md', 'README.rst', 'README.txt']);
  const hasClaude = exists(root, 'CLAUDE.md');
  const hasDocs = isDir(root, 'docs') || isDir(root, 'doc');
  const hasDesigns = isDir(root, 'doc', 'design');

  if (!hasReadme) {
    findings.push(finding({
      severity: Severity.MEDIUM,
      description: 'README missing — new contributors have no entry point.',
      remediation: 'Add a README with purpose, install, run, and test instructions.',
    }));
  }
  if (!hasClaude) {
    findings.push(finding({
      severity: Severity.LOW,
      description: 'CLAUDE.md missing — project not onboarded into SpecBox flows.',
      remediation: 'Run onboard_project to create CLAUDE.md and settings.',
    }));
  }

  let scoreBase = 70;
  if (hasReadme) scoreBase += 10;
  if (hasClaude) scoreBase += 5;
  if (hasDocs) scoreBase += 10;
  if (hasDesigns) scoreBase += 5;
  scoreBase = clamp(scoreBase);
  const score = scoreFromFindings(findings, scoreBase);

  const raw = {
    has_readme: hasReadme,
    has_claude_md: hasClaude,
    has_docs_dir: hasDocs,
    has_stitch_designs: hasDesigns,
  };
  const justification =
    `README=${hasReadme}, CLAUDE.md=${hasClaude}, docs=${hasDocs}, `
    + `designs=${hasDesigns}. Documentation presence proxies learnability.`;

  return characteristicResult({
    characteristic, score, traffic_light: trafficLight(score),
    justification, raw_metrics: raw, findings,
  });
}
