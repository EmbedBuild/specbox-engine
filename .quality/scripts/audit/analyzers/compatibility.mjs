/**
 * compatibility.mjs — co-existence and interoperability with target environments.
 * Port of server/audit/analyzers/compatibility.py (UC-663).
 *
 * Heuristics: declared engine versions, lockfile presence, infra services.
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding,
} from '../lib/schema.mjs';
import { scoreFromFindings, trafficLight } from '../lib/scoring.mjs';
import { exists, anyExists, readText } from '../lib/fs-scan.mjs';
import { join } from 'node:path';

export const characteristic = SquareCharacteristic.COMPATIBILITY;

const LOCKFILES = [
  'poetry.lock', 'uv.lock', 'requirements.txt', 'package-lock.json',
  'pnpm-lock.yaml', 'yarn.lock', 'pubspec.lock', 'go.sum',
];

export function analyze(ctx) {
  const root = ctx.root;
  const findings = [];
  const raw = {};

  const hasLockfile = anyExists(root, LOCKFILES);
  raw.has_lockfile = hasLockfile;
  if (!hasLockfile) {
    findings.push(finding({
      severity: Severity.MEDIUM,
      description: 'No dependency lockfile found — builds are not reproducible.',
      remediation: 'Commit a lockfile appropriate to the stack (poetry.lock, package-lock.json, pubspec.lock, …).',
    }));
  }

  const declared = {};
  if (exists(root, 'pyproject.toml')) declared.python_pyproject = 'present';
  if (exists(root, 'package.json')) {
    try {
      const data = JSON.parse(readText(join(root, 'package.json')));
      if (data && data.engines) {
        declared.engines = JSON.stringify(data.engines).slice(0, 200);
      } else {
        findings.push(finding({
          severity: Severity.LOW,
          description: 'package.json has no `engines` field — Node version not pinned.',
          remediation: 'Add `"engines": {"node": ">=20"}` (or appropriate) to package.json.',
        }));
      }
    } catch {
      // ignore malformed package.json (mirrors except OSError/JSONDecodeError)
    }
  }
  if (exists(root, 'pubspec.yaml')) declared.flutter_pubspec = 'present';

  raw.declared_versions = declared;
  raw.infra_services = ctx.infra || [];

  const base = hasLockfile ? 85.0 : 75.0;
  const score = scoreFromFindings(findings, base);

  const justification =
    `Lockfile present: ${hasLockfile}. Declared version manifests: `
    + `${Object.keys(declared).sort().join(', ') || 'none'}.`;

  return characteristicResult({
    characteristic, score, traffic_light: trafficLight(score),
    justification, raw_metrics: raw, findings,
  });
}
