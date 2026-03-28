#!/usr/bin/env node

/**
 * api-evidence-generator.js
 *
 * Post-procesador que genera un HTML Evidence Report self-contained
 * a partir de resultados de pytest-bdd (cucumber JSON) + response logs.
 *
 * Para stacks sin UI (Python APIs, MCPs). Embebe request/response JSON
 * formateado en lugar de screenshots, pero produce el MISMO template HTML
 * que Playwright y Patrol generan para stacks con UI.
 *
 * Uso:
 *   node api-evidence-generator.js \
 *     --uc-id UC-010 \
 *     --feature autenticacion-api \
 *     --responses .quality/evidence/autenticacion-api/acceptance/ \
 *     --cucumber tests/acceptance/reports/cucumber-report.json \
 *     --output .quality/evidence/autenticacion-api/acceptance/e2e-evidence-report.html
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
const responsesDir = getArg('--responses') || `.quality/evidence/${feature}/acceptance`;
const cucumberPath = getArg('--cucumber');
const outputPath = getArg('--output') || `.quality/evidence/${feature}/acceptance/e2e-evidence-report.html`;
const usId = getArg('--us-id') || 'N/A';

// ---------------------------------------------------------------------------
// Parse Cucumber JSON (pytest-bdd output)
// ---------------------------------------------------------------------------
function parseCucumberJson(jsonContent) {
  const data = JSON.parse(jsonContent);
  const results = [];

  // pytest-bdd produces an array of features, each with scenarios
  const features = Array.isArray(data) ? data : [data];

  for (const feat of features) {
    const elements = feat.elements || [];
    for (const scenario of elements) {
      const tags = (scenario.tags || []).map(t => t.name || t);
      const acMatch = tags.find(t => /^@?AC-\d+$/i.test(t));
      const acId = acMatch ? acMatch.replace('@', '') : scenario.name;

      const steps = (scenario.steps || []).map(s => ({
        keyword: (s.keyword || '').trim(),
        text: s.name || '',
        status: s.result?.status === 'passed' ? 'PASS' : 'FAIL',
        duration_ms: Math.round((s.result?.duration || 0) / 1_000_000), // nanoseconds to ms
      }));

      const failed = steps.some(s => s.status === 'FAIL');
      const totalDuration = steps.reduce((sum, s) => sum + s.duration_ms, 0);
      const errorStep = steps.find(s => s.status === 'FAIL');
      const errorMsg = errorStep
        ? (scenario.steps?.find(s => s.name === errorStep.text)?.result?.error_message || null)
        : null;

      results.push({
        id: acId.toUpperCase(),
        scenario: scenario.name || 'Unknown',
        status: failed ? 'FAIL' : 'PASS',
        duration_ms: totalDuration,
        error: errorMsg,
        steps,
      });
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Collect response logs (JSON files named AC-XX_*.json)
// ---------------------------------------------------------------------------
function collectResponseLogs(dir) {
  const logs = {};
  if (!fs.existsSync(dir)) return logs;

  fs.readdirSync(dir)
    .filter(f => f.endsWith('.json') && /^AC-/i.test(f) && f !== 'results.json')
    .forEach(f => {
      const key = f.replace('.json', '');
      const content = fs.readFileSync(path.join(dir, f), 'utf-8');
      try {
        logs[key] = JSON.parse(content);
      } catch {
        logs[key] = { raw: content };
      }
    });

  return logs;
}

// ---------------------------------------------------------------------------
// Generate HTML
// ---------------------------------------------------------------------------
function generateHtml(results, totalTests, totalPass, totalFail, passRate, responseLogs) {
  const passRateColor = passRate >= 80 ? '#22c55e' : passRate >= 50 ? '#eab308' : '#ef4444';
  const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19) + ' UTC';

  const acCards = results.map(r => {
    // Find matching response log
    const acKey = r.id.toLowerCase().replace('-', '_');
    const logEntry = Object.entries(responseLogs).find(([key]) =>
      key.toLowerCase().includes(acKey)
    );

    let evidenceBlock;
    if (logEntry) {
      const [logName, logData] = logEntry;
      const formatted = JSON.stringify(logData, null, 2);
      evidenceBlock = `<div style="background:#f9fafb;border:1px solid #e5e7eb;padding:12px;border-radius:8px;font-size:13px;font-family:'SF Mono',Menlo,monospace;overflow-x:auto;white-space:pre-wrap;max-height:400px;overflow-y:auto">${escapeHtml(formatted)}</div>
      <div style="font-size:11px;color:#9ca3af;margin-top:4px">Source: ${escapeHtml(logName)}.json</div>`;
    } else {
      evidenceBlock = '<p style="color:#999;font-style:italic">No response log captured</p>';
    }

    const statusBadge = r.status === 'PASS'
      ? '<span style="background:#22c55e;color:white;padding:2px 8px;border-radius:4px;font-size:13px">PASS</span>'
      : '<span style="background:#ef4444;color:white;padding:2px 8px;border-radius:4px;font-size:13px">FAIL</span>';

    const stepsHtml = (r.steps || []).map(s =>
      `<span style="color:${s.status === 'PASS' ? '#22c55e' : '#ef4444'}">${escapeHtml(s.keyword)}</span> ${escapeHtml(s.text)}`
    ).join(' &rarr; ');

    const errorBlock = r.error
      ? `<pre style="background:#fef2f2;border:1px solid #fecaca;padding:8px;border-radius:4px;font-size:12px;overflow-x:auto;margin-top:8px">${escapeHtml(r.error)}</pre>`
      : '';

    return `<div style="border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px;background:white">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
        <h3 style="margin:0;font-size:16px">${escapeHtml(r.id)}: ${escapeHtml(r.scenario)}</h3>
        ${statusBadge}
      </div>
      ${evidenceBlock}
      <div style="margin-top:8px;font-size:13px;color:#6b7280">${stepsHtml}</div>
      <div style="margin-top:4px;font-size:12px;color:#9ca3af">Duration: ${r.duration_ms}ms</div>
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
      Source: <strong>Python API</strong> (pytest-bdd)<br>
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
  ${acCards}

  <div class="footer">
    SpecBox Engine v5.12.0 — AG-09a Acceptance Tester (API Evidence Generator)<br>
    Generated automatically from pytest-bdd test execution
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
// Generate results.json (follows doc/specs/results-json-spec.md)
// ---------------------------------------------------------------------------
function generateResultsJson(results, totalTests, totalPass, totalFail) {
  return {
    feature,
    uc_id: ucId,
    us_id: usId,
    timestamp: new Date().toISOString(),
    source: 'pytest-bdd',
    stack: 'python',
    evidence_type: 'response-log',
    tests_total: totalTests,
    tests_passed: totalPass,
    tests_failed: totalFail,
    results: results.map(r => ({
      id: r.id,
      scenario: r.scenario,
      status: r.status,
      duration_ms: r.duration_ms,
      evidence: null, // response logs matched at report generation time
      error: r.error,
      steps: r.steps,
    })),
  };
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  if (!cucumberPath || !fs.existsSync(cucumberPath)) {
    console.error(`ERROR: Cucumber JSON not found at: ${cucumberPath}`);
    console.error('Usage: node api-evidence-generator.js --cucumber <path> --responses <dir> --uc-id <id> --feature <name>');
    process.exit(1);
  }

  const jsonContent = fs.readFileSync(cucumberPath, 'utf-8');
  const results = parseCucumberJson(jsonContent);

  if (results.length === 0) {
    console.error('WARNING: No scenarios found in Cucumber JSON');
  }

  // Collect response logs
  const responseLogs = collectResponseLogs(responsesDir);
  console.log(`Found ${Object.keys(responseLogs).length} response logs in ${responsesDir}`);

  const totalTests = results.length;
  const totalPass = results.filter(r => r.status === 'PASS').length;
  const totalFail = results.filter(r => r.status === 'FAIL').length;
  const passRate = totalTests > 0 ? Math.round((totalPass / totalTests) * 100) : 0;

  // Generate HTML
  const html = generateHtml(results, totalTests, totalPass, totalFail, passRate, responseLogs);

  // Write output
  const outputDir = path.dirname(outputPath);
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(outputPath, html, 'utf-8');
  console.log(`HTML Evidence Report: ${outputPath}`);

  // Write results.json
  const resultsJson = generateResultsJson(results, totalTests, totalPass, totalFail);
  const resultsPath = path.join(outputDir, 'results.json');
  fs.writeFileSync(resultsPath, JSON.stringify(resultsJson, null, 2), 'utf-8');
  console.log(`Results JSON: ${resultsPath}`);

  // Summary
  console.log(`\nPass rate: ${passRate}% (${totalPass}/${totalTests})`);
  if (totalFail > 0) {
    console.log(`FAILED: ${results.filter(r => r.status === 'FAIL').map(r => r.id).join(', ')}`);
  }
}

main();
