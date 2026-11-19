#!/usr/bin/env node

/**
 * patrol-evidence-generator.js
 *
 * Post-procesador que genera un HTML Evidence Report self-contained
 * a partir de los resultados de Patrol v4 (JUnit XML + screenshots).
 *
 * Produce el MISMO formato que AG-09a genera con Playwright,
 * de modo que AG-09b no distingue el origen.
 *
 * Uso:
 *   node patrol-evidence-generator.js \
 *     --uc-id UC-001 \
 *     --feature crear-propiedad \
 *     --screenshots build/app/outputs/connected_android_test_additional_output/emulator-5554/ \
 *     --junit build/app/outputs/androidTest-results/connected/TEST-MainActivityTest.xml \
 *     --output .quality/evidence/crear-propiedad/acceptance/e2e-evidence-report.html
 *
 *   --contract <contract.json>  The UC's contract (UC-12801); default: contract.json next to the report.
 *   --tests <dir>               Tests with a «// contract: AC-01.pre1, AC-01.post1» comment above them
 *                               (default: patrol_test and integration_test).
 *
 * SpecBox Engine v5.12.0
 */

const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------
const args = process.argv.slice(2);
function getArg(name) {
  const i = args.indexOf(name);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : null;
}

const ucId = getArg('--uc-id') || 'UC-000';
const feature = getArg('--feature') || 'unknown';
const screenshotsDir = getArg('--screenshots') || 'build/screenshots';
const junitPath = getArg('--junit');
const outputPath = getArg('--output') || `.quality/evidence/${feature}/acceptance/e2e-evidence-report.html`;
const usId = getArg('--us-id') || 'N/A';
const contractArg = getArg('--contract'); // UC-12801: contract.json (default: next to the report)
const testsDir = getArg('--tests'); // UC-12801: tests with their «// contract:» comment (default: patrol_test, integration_test)
let CONTRACT = null;

// ---------------------------------------------------------------------------
// Contract (US-128 · UC-12801) — the same block in the three evidence generators
// (api, maestro, patrol); tests/hooks/evidence-generators-contract.test.mjs checks it.
//
// Each test cites the conditions of contract.json it checks: Gherkin tags
// (@pre:AC-01.pre1 @post:AC-01.post1) or a «contract:» comment in the flow or the test
// (# contract: AC-01.pre1, AC-01.post1). They go to results[].contract, and the
// report shows the UC's contract (--contract, or contract.json next to the report)
// in the card of each criterion.
// ---------------------------------------------------------------------------
const CONTRACT_CONDITION_RE = /^AC-(\d{1,4})\.(pre|post)(\d{1,4})$/i;

function normalizeConditionId(raw) {
  const m = CONTRACT_CONDITION_RE.exec(String(raw).trim());
  return m ? `AC-${String(Number(m[1])).padStart(2, '0')}.${m[2].toLowerCase()}${Number(m[3])}` : null;
}

/** Citations from Gherkin tags: the tag says the kind (@pre: / @post:). */
function citationsFromTags(tags) {
  const out = { pre: [], post: [] };
  for (const tag of tags || []) {
    const m = /^@?(pre|post):(.+)$/i.exec(String(tag).trim());
    if (!m) continue;
    const kind = m[1].toLowerCase();
    const id = normalizeConditionId(m[2]) || m[2].trim();
    if (!out[kind].includes(id)) out[kind].push(id);
  }
  return out;
}

/** Citations from a «contract:» comment: the id says the kind (AC-01.pre1, AC-01.post1). */
function citationsFromComment(text) {
  const out = { pre: [], post: [] };
  for (const part of String(text || '').split(/[\s,;]+/).filter(Boolean)) {
    const id = normalizeConditionId(part);
    if (!id) continue;
    const kind = id.includes('.pre') ? 'pre' : 'post';
    if (!out[kind].includes(id)) out[kind].push(id);
  }
  return out;
}

const hasCitations = (c) => !!c && (c.pre.length > 0 || c.post.length > 0);

/** The UC's contract.json (--contract, or next to the report), or null. Never fails the report. */
function loadContract(explicitPath, reportDir) {
  const candidate = explicitPath || path.join(reportDir, 'contract.json');
  if (!fs.existsSync(candidate)) {
    if (explicitPath) console.error(`WARNING: contract not found at ${explicitPath}`);
    return null;
  }
  try {
    const data = JSON.parse(fs.readFileSync(candidate, 'utf-8'));
    const criteria = {};
    for (const [key, entry] of Object.entries((data && data.criteria) || {})) {
      const m = /^AC-(\d{1,4})$/i.exec(String(key).trim());
      if (m && entry && typeof entry === 'object') criteria[`AC-${String(Number(m[1])).padStart(2, '0')}`] = entry;
    }
    return { criteria };
  } catch (e) {
    console.error(`WARNING: contract at ${candidate} is not valid JSON (${e.message})`);
    return null;
  }
}

/** The contract of a criterion in its card, with the conditions this test cites marked. */
function contractHtml(contract, acId, cited) {
  if (!contract) return '';
  const entry = contract.criteria[acId];
  const box = 'margin-top:8px;padding:8px 12px;border:1px solid #e5e7eb;border-radius:6px;font-size:13px';
  if (!entry) {
    return `<div class="contract" style="${box};color:#b45309">Sin contrato para este criterio</div>`;
  }
  const all = [...((cited && cited.pre) || []), ...((cited && cited.post) || [])];
  const conditions = (list) => (Array.isArray(list) ? list : []).map((c) => {
    const id = normalizeConditionId(c && c.id) || String((c && c.id) || '');
    const mark = all.includes(id) ? ' <strong title="comprobada por esta prueba">✓</strong>' : '';
    return `<li><code>${escapeHtml(id)}</code> ${escapeHtml((c && c.text) || '')}${mark}</li>`;
  }).join('');
  const undef = (Array.isArray(entry.undefined) ? entry.undefined : [])
    .map((u) => `<li>${escapeHtml(u)}</li>`).join('') || '<li>Nada</li>';
  return `<div class="contract" style="${box}">
        <div style="font-weight:600;margin-bottom:4px">Contrato</div>
        <div>Precondiciones</div><ul style="margin:2px 0 6px 18px;padding:0">${conditions(entry.pre)}</ul>
        <div>Postcondiciones</div><ul style="margin:2px 0 6px 18px;padding:0">${conditions(entry.post)}</ul>
        <div>Sin definir</div><ul style="margin:2px 0 0 18px;padding:0">${undef}</ul>
      </div>`;
}

/** Which «contract:» comment belongs to a test: by its name, else the only one of its criterion. */
function matchCitations(result, sources, results) {
  const byName = sources.find((s) => s.names.some((n) => n && (result.scenario === n || result.scenario.includes(n))));
  if (byName) return byName.citations;
  const sameAc = results.filter((r) => r.id === result.id);
  if (sameAc.length !== 1) return null;
  const mine = sources.filter((s) => [...s.citations.pre, ...s.citations.post].every((id) => id.startsWith(`${result.id}.`))
    && hasCitations(s.citations));
  return mine.length === 1 ? mine[0].citations : null;
}
// --- end of the contract block ---

/** The tests with the «// contract:» comment just above them (UC-12801), by test name. */
function collectTestCitations(dirs) {
  const out = [];
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) {
        walk(full);
        continue;
      }
      if (!entry.name.endsWith('.dart')) continue;
      let pending = '';
      for (const line of fs.readFileSync(full, 'utf-8').split(/\r?\n/)) {
        const comment = /^\s*\/\/\s*contract:\s*(.+)$/i.exec(line);
        if (comment) {
          pending += `,${comment[1]}`;
          continue;
        }
        const test = /\b(?:patrolTest|testWidgets|test)\(\s*(['"])(.+?)\1/.exec(line);
        if (test && pending) {
          out.push({ names: [test[2]], citations: citationsFromComment(pending) });
          pending = '';
        }
      }
    }
  };
  for (const dir of dirs) if (dir && fs.existsSync(dir)) walk(dir);
  return out;
}

// ---------------------------------------------------------------------------
// Parse JUnit XML (minimal parser — no dependencies)
// ---------------------------------------------------------------------------
function parseJunitXml(xmlContent) {
  const testCases = [];
  const tcRegex = /<testcase\s+([^>]*)\/?>(?:([\s\S]*?)<\/testcase>)?/g;
  let match;

  while ((match = tcRegex.exec(xmlContent)) !== null) {
    const attrs = match[1];
    const body = match[2] || '';

    const name = (attrs.match(/name="([^"]*)"/) || [])[1] || 'Unknown';
    const time = parseFloat((attrs.match(/time="([^"]*)"/) || [])[1] || '0');
    const failed = /<failure/.test(body);
    const errorMsg = (body.match(/<failure[^>]*(?:message="([^"]*)")?[^>]*>(?:([\s\S]*?))<\/failure>/) || [])[2]
      || (body.match(/<failure[^>]*message="([^"]*)"/) || [])[1]
      || null;

    testCases.push({
      name,
      durationMs: Math.round(time * 1000),
      failed,
      error: errorMsg ? errorMsg.trim() : null,
    });
  }

  // Fallback: suite-level attrs
  const totalMatch = xmlContent.match(/tests="(\d+)"/);
  const failMatch = xmlContent.match(/failures="(\d+)"/);

  return {
    testCases,
    totalFromSuite: totalMatch ? parseInt(totalMatch[1]) : testCases.length,
    failuresFromSuite: failMatch ? parseInt(failMatch[1]) : testCases.filter(t => t.failed).length,
  };
}

// ---------------------------------------------------------------------------
// Collect screenshots
// ---------------------------------------------------------------------------
function collectScreenshots(dir) {
  const screenshots = {};
  if (!fs.existsSync(dir)) return screenshots;

  fs.readdirSync(dir)
    .filter(f => /\.(png|jpg|jpeg)$/i.test(f))
    .forEach(f => {
      const key = f.replace(/\.(png|jpg|jpeg)$/i, '');
      const b64 = fs.readFileSync(path.join(dir, f)).toString('base64');
      const ext = path.extname(f).slice(1).toLowerCase();
      const mime = ext === 'png' ? 'image/png' : 'image/jpeg';
      screenshots[key] = { base64: b64, mime };
    });

  return screenshots;
}

// ---------------------------------------------------------------------------
// Map test cases to AC results
// ---------------------------------------------------------------------------
function buildResults(parsed, screenshots) {
  return parsed.testCases.map(tc => {
    // Extract AC-XX from test name
    const acMatch = tc.name.match(/AC-(\d+)/i);
    const acId = acMatch ? `AC-${acMatch[1].padStart(2, '0')}` : tc.name;

    // Find matching screenshots (any that contain the AC id)
    const acKey = acId.replace('-', '_').toLowerCase();
    const matchingScreenshots = Object.entries(screenshots)
      .filter(([key]) => key.toLowerCase().includes(acKey))
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, data]) => ({ name: key, ...data }));

    return {
      id: acId,
      scenario: tc.name,
      status: tc.failed ? 'FAIL' : 'PASS',
      duration_ms: tc.durationMs,
      error: tc.error,
      screenshots: matchingScreenshots,
    };
  });
}

/** Each result with the citations of its test (UC-12801). */
function attachCitations(results, sources) {
  for (const r of results) r.contract = matchCitations(r, sources, results) || { pre: [], post: [] };
  return results;
}

// ---------------------------------------------------------------------------
// Generate HTML
// ---------------------------------------------------------------------------
function generateHtml(results, totalTests, totalPass, totalFail, passRate) {
  const passRateColor = passRate >= 80 ? '#22c55e' : passRate >= 50 ? '#eab308' : '#ef4444';
  const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  const screenshotCards = results.map(r => {
    const imgs = r.screenshots.length > 0
      ? r.screenshots.map(s =>
          `<img src="data:${s.mime};base64,${s.base64}" style="max-width:100%;border:1px solid #e5e7eb;border-radius:8px;margin:4px 0;" />`
        ).join('\n')
      : '<p style="color:#999;font-style:italic">No screenshot captured</p>';

    const statusBadge = r.status === 'PASS'
      ? '<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:4px;font-size:13px">PASS</span>'
      : '<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:4px;font-size:13px">FAIL</span>';

    const errorBlock = r.error
      ? `<pre style="background:#fef2f2;border:1px solid #fecaca;padding:8px;border-radius:4px;font-size:12px;overflow-x:auto;margin-top:8px">${escapeHtml(r.error)}</pre>`
      : '';

    return `<div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px;background:white">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="margin:0;font-size:16px">${escapeHtml(r.id)}: ${escapeHtml(r.scenario)}</h3>
        ${statusBadge}
      </div>
      ${imgs}
      <div style="margin-top:4px;font-size:12px;color:#9ca3af">Duration: ${r.duration_ms}ms</div>
      ${contractHtml(CONTRACT, r.id, r.contract)}
      ${errorBlock}
    </div>`;
  }).join('\n');

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>E2E Evidence — ${escapeHtml(ucId)}</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 0 auto; padding: 24px; background: #fafafa; color: #1f2937; }
    .header { background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    .header h1 { margin: 0 0 8px 0; font-size: 24px; }
    .header .meta { color: #6b7280; font-size: 14px; }
    .summary { display: flex; gap: 16px; margin: 16px 0; }
    .summary .card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; flex: 1; text-align: center; }
    .summary .card .number { font-size: 28px; font-weight: bold; }
    .summary .card .label { font-size: 12px; color: #6b7280; text-transform: uppercase; }
    .pass-rate { font-size: 48px; font-weight: bold; color: ${passRateColor}; }
    .footer { text-align: center; color: #9ca3af; font-size: 12px; margin-top: 32px; padding-top: 16px; border-top: 1px solid #e5e7eb; }
  </style>
</head>
<body>
  <div class="header">
    <h1>E2E Evidence Report</h1>
    <div class="meta">
      Feature: <strong>${escapeHtml(feature)}</strong> | UC: <strong>${escapeHtml(ucId)}</strong> | US: <strong>${escapeHtml(usId)}</strong><br>
      Source: <strong>Patrol v4</strong> (Flutter Mobile)<br>
      Generated: ${timestamp}
    </div>
  </div>

  <div class="summary">
    <div class="card">
      <div class="pass-rate">${passRate}%</div>
      <div class="label">Pass Rate</div>
    </div>
    <div class="card">
      <div class="number" style="color:#22c55e">${totalPass}</div>
      <div class="label">Passed</div>
    </div>
    <div class="card">
      <div class="number" style="color:#ef4444">${totalFail}</div>
      <div class="label">Failed</div>
    </div>
    <div class="card">
      <div class="number">${totalTests}</div>
      <div class="label">Total</div>
    </div>
  </div>

  <h2 style="font-size:18px;margin:24px 0 12px">Acceptance Criteria Evidence</h2>
  ${screenshotCards}

  <div class="footer">
    SpecBox Engine v5.12.0 — AG-09a Acceptance Tester (Patrol + Evidence Generator)<br>
    Generated automatically from Patrol E2E test execution
  </div>
</body>
</html>`;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Also generate results.json (standard format for AG-09b)
// ---------------------------------------------------------------------------
function generateResultsJson(results, totalTests, totalPass, totalFail) {
  // Follows doc/specs/results-json-spec.md contract
  return {
    feature,
    uc_id: ucId,
    us_id: usId,
    timestamp: new Date().toISOString(),
    source: 'patrol-junit-xml',
    stack: 'flutter-mobile',
    evidence_type: 'screenshot',
    tests_total: totalTests,
    tests_passed: totalPass,
    tests_failed: totalFail,
    results: results.map(r => ({
      id: r.id,
      scenario: r.scenario,
      status: r.status,
      duration_ms: r.duration_ms,
      evidence: r.screenshots.length > 0 ? `${r.screenshots[0].name}.png` : null,
      error: r.error,
      ...(hasCitations(r.contract) ? { contract: r.contract } : {}),
    })),
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  // Read JUnit XML
  if (!junitPath || !fs.existsSync(junitPath)) {
    console.error(`ERROR: JUnit XML not found at: ${junitPath}`);
    console.error('Usage: node patrol-evidence-generator.js --junit <path> --screenshots <dir> --uc-id <id> --feature <name>');
    process.exit(1);
  }

  const xmlContent = fs.readFileSync(junitPath, 'utf-8');
  const parsed = parseJunitXml(xmlContent);

  if (parsed.testCases.length === 0) {
    console.error('WARNING: No test cases found in JUnit XML');
  }

  // Collect screenshots
  const screenshots = collectScreenshots(screenshotsDir);
  console.log(`Found ${Object.keys(screenshots).length} screenshots in ${screenshotsDir}`);

  // Build results
  const results = attachCitations(buildResults(parsed, screenshots),
    collectTestCitations(testsDir ? [testsDir] : ['patrol_test', 'integration_test']));
  const totalTests = results.length || parsed.totalFromSuite;
  const totalPass = results.filter(r => r.status === 'PASS').length;
  const totalFail = results.filter(r => r.status === 'FAIL').length;
  const passRate = totalTests > 0 ? Math.round((totalPass / totalTests) * 100) : 0;

  // Generate HTML (with the UC's contract in each card, UC-12801)
  CONTRACT = loadContract(contractArg, path.dirname(outputPath));
  const html = generateHtml(results, totalTests, totalPass, totalFail, passRate);

  // Write output
  const outputDir = path.dirname(outputPath);
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, html, 'utf-8');
  console.log(`HTML Evidence Report: ${outputPath}`);

  // Write results.json alongside
  const resultsJson = generateResultsJson(results, totalTests, totalPass, totalFail);
  const resultsPath = path.join(outputDir, 'results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(resultsJson, null, 2), 'utf-8');
  console.log(`Results JSON: ${resultsPath}`);

  // Copy screenshots to evidence dir
  for (const [key, data] of Object.entries(screenshots)) {
    const ext = data.mime === 'image/png' ? 'png' : 'jpg';
    const dest = path.join(outputDir, `${key}.${ext}`);
    const src = path.join(screenshotsDir, `${key}.${ext}`);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, dest);
    }
  }

  // Summary
  console.log(`\nPass rate: ${passRate}% (${totalPass}/${totalTests})`);
  if (totalFail > 0) {
    console.log(`FAILED: ${results.filter(r => r.status === 'FAIL').map(r => r.id).join(', ')}`);
  }
}

main();
