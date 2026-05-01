#!/usr/bin/env node

/**
 * maestro-evidence-generator.js
 *
 * Post-procesador que genera un HTML Evidence Report self-contained
 * a partir de los resultados de Maestro (JUnit XML + screenshots PNG + opcional MP4).
 *
 * Produce el MISMO formato que patrol-evidence-generator.js,
 * de modo que AG-09b y validate-results-json.js no distinguen el origen.
 *
 * Uso:
 *   node maestro-evidence-generator.js \
 *     --uc-id UC-001 \
 *     --us-id US-01 \
 *     --feature crear-propiedad \
 *     --junit build/maestro/results.xml \
 *     --screenshots build/maestro/UC-001/ \
 *     --output .quality/evidence/crear-propiedad/acceptance/e2e-evidence-report.html
 *
 * Argumentos opcionales:
 *   --video build/maestro/UC-001/recording.mp4    Embed video link in report
 *
 * SpecBox Engine v5.28.0
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
const usId = getArg('--us-id') || 'N/A';
const feature = getArg('--feature') || 'unknown';
const junitPath = getArg('--junit');
const screenshotsDir = getArg('--screenshots') || 'build/maestro';
const videoPath = getArg('--video');
const outputPath = getArg('--output') || `.quality/evidence/${feature}/acceptance/e2e-evidence-report.html`;

// ---------------------------------------------------------------------------
// Parse JUnit XML (minimal parser — no dependencies)
//
// Maestro emits standard JUnit XML. Each <testcase> represents one flow file.
// Failures appear as <failure message="..."> children.
// ---------------------------------------------------------------------------
function parseJunitXml(xmlContent) {
  const testCases = [];
  const tcRegex = /<testcase\s+([^>]*?)(?:\/>|>([\s\S]*?)<\/testcase>)/g;
  let match;

  while ((match = tcRegex.exec(xmlContent)) !== null) {
    const attrs = match[1];
    const body = match[2] || '';

    const name = (attrs.match(/name="([^"]*)"/) || [])[1] || 'Unknown';
    const classname = (attrs.match(/classname="([^"]*)"/) || [])[1] || '';
    const time = parseFloat((attrs.match(/time="([^"]*)"/) || [])[1] || '0');
    const failed = /<failure/.test(body) || /<error/.test(body);

    let errorMsg = null;
    const failureMatch = body.match(/<failure[^>]*message="([^"]*)"[^>]*>([\s\S]*?)<\/failure>/);
    const errorTag = body.match(/<error[^>]*message="([^"]*)"[^>]*>([\s\S]*?)<\/error>/);
    if (failureMatch) {
      errorMsg = (failureMatch[2] || failureMatch[1] || '').trim() || failureMatch[1];
    } else if (errorTag) {
      errorMsg = (errorTag[2] || errorTag[1] || '').trim() || errorTag[1];
    } else {
      const selfClosingFailure = body.match(/<failure[^>]*message="([^"]*)"[^>]*\/>/);
      if (selfClosingFailure) errorMsg = selfClosingFailure[1];
    }

    testCases.push({
      name,
      classname,
      durationMs: Math.round(time * 1000),
      failed,
      error: errorMsg ? errorMsg.trim() : null,
    });
  }

  const totalMatch = xmlContent.match(/tests="(\d+)"/);
  const failMatch = xmlContent.match(/failures="(\d+)"/);

  return {
    testCases,
    totalFromSuite: totalMatch ? parseInt(totalMatch[1]) : testCases.length,
    failuresFromSuite: failMatch ? parseInt(failMatch[1]) : testCases.filter(t => t.failed).length,
  };
}

// ---------------------------------------------------------------------------
// Collect screenshots from --screenshots dir (recursive, in case Maestro
// nests them per flow). Filenames must match AC-XX_step_N_description.png
// per the convention documented in maestro-setup.md.
// ---------------------------------------------------------------------------
function collectScreenshots(dir) {
  const screenshots = {};
  if (!fs.existsSync(dir)) return screenshots;

  function walk(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const full = path.join(d, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (/\.(png|jpg|jpeg)$/i.test(entry.name)) {
        const key = entry.name.replace(/\.(png|jpg|jpeg)$/i, '');
        const b64 = fs.readFileSync(full).toString('base64');
        const ext = path.extname(entry.name).slice(1).toLowerCase();
        const mime = ext === 'png' ? 'image/png' : 'image/jpeg';
        screenshots[key] = { base64: b64, mime, srcPath: full };
      }
    }
  }
  walk(dir);
  return screenshots;
}

// ---------------------------------------------------------------------------
// Map test cases to AC results.
//
// Maestro flows are typically named after the AC ("AC-01: ..."). We extract
// the AC-XX prefix from the testcase name to correlate with screenshots
// (which follow AC-XX_step_N_description.png convention).
// ---------------------------------------------------------------------------
function buildResults(parsed, screenshots) {
  return parsed.testCases.map(tc => {
    const acMatch = tc.name.match(/AC-(\d+)/i) || tc.classname.match(/AC-(\d+)/i);
    const acId = acMatch ? `AC-${acMatch[1].padStart(2, '0')}` : tc.name;

    // Match files like AC-01_step_1_logged_in.png — case-insensitive substring match
    // on the canonical AC-XX prefix (the documented naming convention).
    const acPrefix = acId.toLowerCase();
    const matchingScreenshots = Object.entries(screenshots)
      .filter(([key]) => key.toLowerCase().includes(acPrefix))
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, data]) => ({ name: key, mime: data.mime, base64: data.base64 }));

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

// ---------------------------------------------------------------------------
// Generate HTML — same shape as patrol-evidence-generator.js so AG-09b
// and validate-results-json.js cannot tell the difference.
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
      ${errorBlock}
    </div>`;
  }).join('\n');

  const videoBlock = videoPath && fs.existsSync(videoPath)
    ? `<div style="margin:16px 0;padding:12px;background:#f3f4f6;border-radius:8px;font-size:13px;color:#4b5563">Video recording: <code>${escapeHtml(videoPath)}</code> (not embedded due to size; available alongside this report)</div>`
    : '';

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
      Source: <strong>Maestro</strong> (Flutter Mobile, black-box)<br>
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

  ${videoBlock}

  <h2 style="font-size:18px;margin:24px 0 12px">Acceptance Criteria Evidence</h2>
  ${screenshotCards}

  <div class="footer">
    SpecBox Engine v5.28.0 — AG-09a Acceptance Tester (Maestro + Evidence Generator)<br>
    Generated automatically from Maestro E2E test execution
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
// Generate results.json (standard SpecBox contract — same as Patrol/Playwright)
// ---------------------------------------------------------------------------
function generateResultsJson(results, totalTests, totalPass, totalFail) {
  return {
    feature,
    uc_id: ucId,
    us_id: usId,
    timestamp: new Date().toISOString(),
    source: 'maestro-junit-xml',
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
    })),
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  if (!junitPath || !fs.existsSync(junitPath)) {
    console.error(`ERROR: Maestro JUnit XML not found at: ${junitPath}`);
    console.error('Usage: node maestro-evidence-generator.js --junit <path> --screenshots <dir> --uc-id <id> --feature <name>');
    process.exit(1);
  }

  const xmlContent = fs.readFileSync(junitPath, 'utf-8');
  const parsed = parseJunitXml(xmlContent);

  if (parsed.testCases.length === 0) {
    console.error('WARNING: No test cases found in Maestro JUnit XML');
  }

  const screenshots = collectScreenshots(screenshotsDir);
  console.log(`Found ${Object.keys(screenshots).length} screenshots in ${screenshotsDir}`);

  const results = buildResults(parsed, screenshots);
  const totalTests = results.length || parsed.totalFromSuite;
  const totalPass = results.filter(r => r.status === 'PASS').length;
  const totalFail = results.filter(r => r.status === 'FAIL').length;
  const passRate = totalTests > 0 ? Math.round((totalPass / totalTests) * 100) : 0;

  const html = generateHtml(results, totalTests, totalPass, totalFail, passRate);

  const outputDir = path.dirname(outputPath);
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, html, 'utf-8');
  console.log(`HTML Evidence Report: ${outputPath}`);

  const resultsJson = generateResultsJson(results, totalTests, totalPass, totalFail);
  const resultsPath = path.join(outputDir, 'results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(resultsJson, null, 2), 'utf-8');
  console.log(`Results JSON: ${resultsPath}`);

  for (const [key, data] of Object.entries(screenshots)) {
    const ext = data.mime === 'image/png' ? 'png' : 'jpg';
    const dest = path.join(outputDir, `${key}.${ext}`);
    if (data.srcPath && fs.existsSync(data.srcPath) && data.srcPath !== dest) {
      fs.copyFileSync(data.srcPath, dest);
    }
  }

  console.log(`\nPass rate: ${passRate}% (${totalPass}/${totalTests})`);
  if (totalFail > 0) {
    console.log(`FAILED: ${results.filter(r => r.status === 'FAIL').map(r => r.id).join(', ')}`);
  }
}

main();
