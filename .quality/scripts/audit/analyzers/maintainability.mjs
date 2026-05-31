/**
 * maintainability.mjs — 60/40 mix.
 * Port of server/audit/analyzers/maintainability.py (UC-663).
 *
 *   60% classic: cyclomatic complexity (lizard), duplication (jscpd),
 *                file size, test ratio
 *   40% SpecBox: AC pending, UC evidence, healing ratio, US blocked, PRD divergence
 *
 * The breakdown MUST appear in the report (RF-3). Returns { result, toolsUsed }.
 */

import {
  Severity, SquareCharacteristic, characteristicResult, finding, toolUsage, round3,
} from '../lib/schema.mjs';
import { clamp, maintainabilityScore, scoreFromFindings, trafficLight } from '../lib/scoring.mjs';
import { runTool, detectVersion } from '../lib/tool-runner.mjs';
import { walkFiles, ext, isTestPath, sizeOf, SOURCE_EXTS } from '../lib/fs-scan.mjs';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export const characteristic = SquareCharacteristic.MAINTAINABILITY;

export function analyze(ctx) {
  const toolsUsed = [];
  const [classicScore, classicRaw, classicFindings] = classic(ctx, toolsUsed);
  const [specboxScore, specboxRaw] = specbox(ctx);

  let [final, breakdown] = maintainabilityScore(classicScore, specboxScore);
  const findings = [...classicFindings];
  final = scoreFromFindings(findings, final);

  const raw = { classic: classicRaw, specbox: specboxRaw };
  const justification =
    `Maintainability = 0.60*classic(${classicScore.toFixed(1)}) + `
    + `0.40*specbox(${specboxScore.toFixed(1)}) = ${final.toFixed(1)}. `
    + 'Breakdown documented to make the score auditable.';

  const result = characteristicResult({
    characteristic, score: clamp(final), traffic_light: trafficLight(final),
    justification, raw_metrics: raw, findings, breakdown,
  });
  return { result, toolsUsed };
}

// ---- classic 60% ----
function classic(ctx, toolsUsed) {
  const root = ctx.root;
  const raw = {};
  const findings = [];

  let srcFiles = 0;
  let testFiles = 0;
  let totalBytes = 0;
  for (const abs of walkFiles(root)) {
    if (!SOURCE_EXTS.has(ext(abs))) continue;
    totalBytes += sizeOf(abs);
    if (isTestPath(abs, root)) testFiles += 1;
    else srcFiles += 1;
  }

  const totalFiles = srcFiles + testFiles;
  const testRatio = srcFiles ? testFiles / srcFiles : 0.0;
  const avgSizeKb = totalFiles ? totalBytes / totalFiles / 1024 : 0.0;
  Object.assign(raw, {
    source_files: srcFiles,
    test_files: testFiles,
    test_to_source_ratio: round3(testRatio),
    avg_file_size_kb: round2(avgSizeKb),
    total_source_bytes: totalBytes,
  });

  if (srcFiles && testRatio < 0.2) {
    findings.push(finding({
      severity: Severity.MEDIUM,
      description: `Low test ratio: ${testFiles}/${srcFiles} test:source files.`,
      remediation: 'Increase test coverage toward ≥ 0.3 test/source ratio.',
    }));
  }
  if (avgSizeKb > 10) {
    findings.push(finding({
      severity: Severity.LOW,
      description: `Average source file size ${avgSizeKb.toFixed(1)} KB — consider splitting large modules.`,
      remediation: 'Refactor large files into cohesive sub-modules.',
    }));
  }

  // lizard (cyclomatic complexity) — optional
  let complexFuncs = 0;
  const lizardRes = runTool(['lizard', '-C', '15', root], { timeout: 120 });
  if (lizardRes.available) {
    toolsUsed.push(toolUsage({ name: 'lizard', status: lizardRes.timedOut ? 'timeout' : 'ok', version: detectVersion('lizard') }));
    for (const line of (lizardRes.stdout || '').split('\n')) {
      const lc = line.toLowerCase();
      if (lc.includes('warnings') && !lc.includes('nloc')) {
        const tok = line.trim().split(/\s+/)[0];
        const n = parseInt(tok, 10);
        if (!Number.isNaN(n)) complexFuncs = n;
        break;
      }
    }
    raw.complex_functions_cc_gt_15 = complexFuncs;
    if (complexFuncs > 0) {
      findings.push(finding({
        severity: complexFuncs > 10 ? Severity.MEDIUM : Severity.LOW,
        description: `${complexFuncs} functions exceed cyclomatic complexity 15 (lizard).`,
        remediation: 'Refactor complex functions; target CC ≤ 10.',
      }));
    }
  } else {
    toolsUsed.push(toolUsage({ name: 'lizard', status: 'missing', message: 'install via `pip install lizard`' }));
    raw.lizard = 'missing';
  }

  // jscpd (duplication) — optional
  let dupPercent = 0.0;
  const jscpdOut = join(root, '.quality', 'jscpd-tmp');
  const dupRes = runTool(['jscpd', '--reporters', 'json', '--output', jscpdOut, root], { timeout: 120 });
  if (dupRes.available) {
    toolsUsed.push(toolUsage({ name: 'jscpd', status: dupRes.timedOut ? 'timeout' : 'ok', version: detectVersion('jscpd') }));
    const dupReport = join(jscpdOut, 'jscpd-report.json');
    if (existsSync(dupReport)) {
      try {
        const data = JSON.parse(readFileSync(dupReport, 'utf-8'));
        dupPercent = Number(((data.statistics || {}).total || {}).percentage || 0.0);
      } catch {
        // ignore malformed report
      }
    }
    raw.duplication_percent = round2(dupPercent);
    if (dupPercent > 5) {
      findings.push(finding({
        severity: dupPercent > 10 ? Severity.MEDIUM : Severity.LOW,
        description: `Code duplication ${dupPercent.toFixed(1)}% (jscpd).`,
        remediation: 'Extract shared utilities to reduce duplication.',
      }));
    }
  } else {
    toolsUsed.push(toolUsage({ name: 'jscpd', status: 'missing', message: 'install via `npm i -g jscpd`' }));
    raw.jscpd = 'missing';
  }

  // Classic score components (all normalized to 0-100) — mirror python exactly.
  const sizeScore = 100 - Math.min(50, Math.max(0, (avgSizeKb - 6) * 5));
  const testScore = clamp(testRatio * 250);
  const ccScore = clamp(100 - complexFuncs * 3);
  const dupScore = clamp(100 - dupPercent * 4);
  const classicVal = (sizeScore + testScore + ccScore + dupScore) / 4;
  raw.classic_components = {
    size_score: round1(sizeScore),
    test_score: round1(testScore),
    cc_score: round1(ccScore),
    dup_score: round1(dupScore),
  };
  return [clamp(classicVal), raw, findings];
}

// ---- specbox 40% ----
function specbox(ctx) {
  const sig = ctx.signals || {};
  const ac = sig.ac_status || {};
  const acTotal = Number(ac.total || 0);
  const acDone = Number(ac.completed || 0);
  const acRatio = acTotal ? acDone / acTotal : 1.0;

  const evidence = sig.evidence || {};
  const ucTotal = Number(evidence.uc_total || 0);
  const ucWith = Number(evidence.uc_with_evidence || 0);
  const evidenceRatio = ucTotal ? ucWith / ucTotal : 1.0;

  const healing = sig.healing || {};
  const hTotal = Number(healing.total_events || 0);
  const hResolved = Number(healing.resolved || 0);
  const healingRatio = hTotal ? hResolved / hTotal : 1.0;

  const board = sig.board || {};
  const usTotal = Number(board.us_total || 0);
  const usBlocked = Number(board.us_blocked || 0);
  const blockPenalty = usTotal ? usBlocked / usTotal : 0.0;

  const divergence = Number(sig.prd_divergence_ratio || 0.0);

  const score =
    acRatio * 100 * 0.30
    + evidenceRatio * 100 * 0.25
    + healingRatio * 100 * 0.20
    + (1 - blockPenalty) * 100 * 0.15
    + (1 - divergence) * 100 * 0.10;

  const raw = {
    ac_completion_ratio: round3(acRatio),
    uc_evidence_ratio: round3(evidenceRatio),
    healing_resolution_ratio: round3(healingRatio),
    us_blocked_ratio: round3(blockPenalty),
    prd_code_divergence_ratio: round3(divergence),
    weights: { ac: 0.30, evidence: 0.25, healing: 0.20, blocked: 0.15, divergence: 0.10 },
  };
  return [clamp(score), raw];
}

function round1(x) { return Math.round((x + Number.EPSILON) * 10) / 10; }
function round2(x) { return Math.round((x + Number.EPSILON) * 100) / 100; }
