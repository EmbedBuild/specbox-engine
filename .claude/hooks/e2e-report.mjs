#!/usr/bin/env node
/**
 * e2e-report.mjs — Hook: Report E2E results to SpecBox Engine MCP
 * Usage: node e2e-report.mjs [results-json-path]
 */

import { getProjectName, fileExists, readJsonFile } from './lib/utils.mjs';
import { mcpCall, getMcpUrl } from './lib/http.mjs';

let resultsJson = process.argv[2] || '';
const projectName = getProjectName();
const mcpUrl = getMcpUrl();

// Auto-detect results file
if (!resultsJson) {
  const candidates = [
    'e2e/test-results.json',
    'test-results/results.json',
    'playwright-report/results.json',
  ];
  for (const candidate of candidates) {
    if (fileExists(candidate)) {
      resultsJson = candidate;
      break;
    }
  }
}

if (!mcpUrl || !resultsJson || !fileExists(resultsJson)) {
  process.exit(0);
}

const results = readJsonFile(resultsJson);
if (!results || !results.stats) {
  process.exit(0);
}

const total = (results.stats.expected || 0) + (results.stats.unexpected || 0) + (results.stats.skipped || 0);
const passing = results.stats.expected || 0;
const failing = results.stats.unexpected || 0;
const skipped = results.stats.skipped || 0;
const duration = results.stats.duration || 0;

// Fire-and-forget: await the call but don't block on failure
try {
  await mcpCall('report_e2e_results', {
    project: projectName,
    total,
    passing,
    failing,
    skipped,
    duration_ms: duration,
    viewports: ['desktop-chrome', 'tablet', 'mobile'],
    report_path: 'doc/test_cases/reports/',
  });
} catch { /* fire-and-forget */ }

console.log(`[e2e-report] ${passing}/${total} passing → reported to MCP`);
process.exit(0);
