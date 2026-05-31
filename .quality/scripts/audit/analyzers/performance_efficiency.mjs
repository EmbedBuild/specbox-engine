/**
 * performance_efficiency.mjs — time behaviour, resource utilization, capacity.
 * Port of server/audit/analyzers/performance_efficiency.py (UC-663).
 *
 * v1: static heuristics. Large source files (hot-path proxy) + perf config presence.
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding,
} from '../lib/schema.mjs';
import { clamp, scoreFromFindings, trafficLight } from '../lib/scoring.mjs';
import { walkFiles, ext, relPath, sizeOf, exists, SOURCE_EXTS } from '../lib/fs-scan.mjs';

export const characteristic = SquareCharacteristic.PERFORMANCE_EFFICIENCY;

const LARGE_FILE_BYTES = 60_000; // ~1.5k LOC

export function analyze(ctx) {
  const root = ctx.root;
  const largeFiles = [];
  let totalSrc = 0;

  for (const abs of walkFiles(root)) {
    if (!SOURCE_EXTS.has(ext(abs))) continue;
    totalSrc += 1;
    const size = sizeOf(abs);
    if (size >= LARGE_FILE_BYTES) largeFiles.push([relPath(abs, root), size]);
  }

  const findings = [];
  for (const [rel, size] of largeFiles.slice(0, 10)) {
    findings.push(finding({
      severity: Severity.LOW,
      description: `Large source file (${Math.floor(size / 1024)} KB): ${rel}`,
      remediation: 'Consider splitting; large files correlate with hot-path risk and slow startup.',
      file: rel,
    }));
  }

  let perfHints = 0;
  for (const marker of ['vite.config.ts', 'vite.config.js', 'webpack.config.js', 'pytest.ini', 'benchmark.yaml']) {
    if (exists(root, marker)) perfHints += 1;
  }

  const base = perfHints ? 90.0 : 80.0;
  const score = scoreFromFindings(findings, base);

  const raw = {
    source_files: totalSrc,
    large_files: largeFiles.length,
    large_file_threshold_bytes: LARGE_FILE_BYTES,
    perf_config_markers: perfHints,
  };
  const justification =
    `${totalSrc} source files scanned; ${largeFiles.length} exceed `
    + `${Math.floor(LARGE_FILE_BYTES / 1024)}KB threshold. Perf config markers: ${perfHints}.`;

  return characteristicResult({
    characteristic, score: clamp(score), traffic_light: trafficLight(score),
    justification, raw_metrics: raw, findings,
  });
}
