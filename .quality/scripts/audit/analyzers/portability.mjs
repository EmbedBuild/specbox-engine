/**
 * portability.mjs — adaptability, installability, replaceability.
 * Port of server/audit/analyzers/portability.py (UC-663).
 *
 * Signals: containerization, hardcoded absolute paths, env config.
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding,
} from '../lib/schema.mjs';
import { clamp, scoreFromFindings, trafficLight } from '../lib/scoring.mjs';
import { walkFiles, ext, relPath, readText, anyExists } from '../lib/fs-scan.mjs';

export const characteristic = SquareCharacteristic.PORTABILITY;

// Mirror python r"(/Users/|/home/|C:\\)[A-Za-z0-9_.\-/\\]+".
// NOTE: a /g regex carries mutable `lastIndex`; sharing one module-level
// instance across concurrent analyze() calls (node:test subtests, parallel
// orchestration) corrupts iteration. Build a fresh regex per scan instead.
const HARDCODED_PATH_SOURCE = '(\\/Users\\/|\\/home\\/|C:\\\\)[A-Za-z0-9_.\\-/\\\\]+';
const SCAN_EXTS = new Set(['.py', '.ts', '.tsx', '.js', '.jsx', '.dart', '.go']);

export function analyze(ctx) {
  const root = ctx.root;
  const hasDockerfile = anyExists(root, ['Dockerfile']);
  const hasCompose = anyExists(root, ['docker-compose.yml', 'compose.yaml']);
  const hasEnvExample = anyExists(root, ['.env.example', '.env.sample']);

  const hardcodedHits = [];
  let scanned = 0;
  outer:
  for (const abs of walkFiles(root)) {
    if (scanned >= 500) break;
    if (!SCAN_EXTS.has(ext(abs))) continue;
    scanned += 1;
    const text = readText(abs);
    // Fresh regex per file — no shared mutable lastIndex across calls.
    const re = new RegExp(HARDCODED_PATH_SOURCE, 'g');
    let m;
    while ((m = re.exec(text)) !== null) {
      const line = text.slice(0, m.index).split('\n').length;
      hardcodedHits.push([relPath(abs, root), line]);
      if (hardcodedHits.length >= 20) break outer;
    }
  }

  const findings = [];
  for (const [rel, line] of hardcodedHits.slice(0, 10)) {
    findings.push(finding({
      severity: Severity.MEDIUM,
      description: `Hardcoded filesystem path in ${rel}:${line}`,
      remediation: 'Move to env var or config file; avoid absolute paths in source.',
      file: rel,
      line,
    }));
  }
  if (!hasDockerfile && !hasCompose) {
    findings.push(finding({
      severity: Severity.LOW,
      description: 'No Dockerfile or docker-compose found — project is not containerized.',
      remediation: 'Add a Dockerfile to enable reproducible deployment.',
    }));
  }
  if (!hasEnvExample) {
    findings.push(finding({
      severity: Severity.LOW,
      description: "No .env.example — contributors can't discover required env vars.",
      remediation: 'Commit a .env.example with all required keys (empty values).',
    }));
  }

  let base = 85.0;
  if (hasDockerfile) base += 5;
  if (hasCompose) base += 3;
  if (hasEnvExample) base += 2;
  base = clamp(base);
  const score = scoreFromFindings(findings, base);

  const raw = {
    has_dockerfile: hasDockerfile,
    has_compose: hasCompose,
    has_env_example: hasEnvExample,
    hardcoded_paths_found: hardcodedHits.length,
    files_scanned: scanned,
  };
  const justification =
    `Containerization=${hasDockerfile || hasCompose}, `
    + `env template=${hasEnvExample}, hardcoded paths=${hardcodedHits.length}.`;

  return characteristicResult({
    characteristic, score, traffic_light: trafficLight(score),
    justification, raw_metrics: raw, findings,
  });
}
