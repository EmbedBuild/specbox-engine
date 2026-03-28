#!/usr/bin/env node

/**
 * validate-results-json.js
 *
 * Validates results.json against doc/specs/results-json-spec.md contract.
 * Returns exit code 0 if valid, 1 if invalid with structured error output.
 *
 * Used by:
 *   - e2e-gate.sh hook (blocking)
 *   - AG-09b before emitting verdict
 *   - CI pipelines
 *
 * Usage:
 *   node validate-results-json.js <path-to-results.json> [--check-evidence]
 *
 *   --check-evidence: Also verify that evidence files referenced exist on disk
 *
 * SpecBox Engine v5.12.0
 */

const fs = require('fs');
const path = require('path');

const filePath = process.argv[2];
const checkEvidence = process.argv.includes('--check-evidence');

if (!filePath) {
  console.error('Usage: node validate-results-json.js <path-to-results.json> [--check-evidence]');
  process.exit(1);
}

if (!fs.existsSync(filePath)) {
  console.error(`FAIL: File not found: ${filePath}`);
  process.exit(1);
}

const errors = [];
const warnings = [];

try {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const data = JSON.parse(raw);

  // --- Required top-level fields ---
  const requiredFields = {
    feature: 'string',
    uc_id: 'string',
    us_id: 'string',
    timestamp: 'string',
    source: 'string',
    stack: 'string',
    evidence_type: 'string',
    tests_total: 'number',
    tests_passed: 'number',
    tests_failed: 'number',
    results: 'array',
  };

  for (const [field, type] of Object.entries(requiredFields)) {
    if (data[field] === undefined || data[field] === null) {
      errors.push(`Missing required field: ${field}`);
    } else if (type === 'array' && !Array.isArray(data[field])) {
      errors.push(`Field '${field}' must be array, got ${typeof data[field]}`);
    } else if (type !== 'array' && typeof data[field] !== type) {
      errors.push(`Field '${field}' must be ${type}, got ${typeof data[field]}`);
    }
  }

  // --- Validate stack values ---
  const validStacks = ['flutter-web', 'flutter-mobile', 'react', 'python'];
  if (data.stack && !validStacks.includes(data.stack)) {
    errors.push(`Invalid stack '${data.stack}'. Must be one of: ${validStacks.join(', ')}`);
  }

  // --- Validate evidence_type values ---
  const validEvidenceTypes = ['screenshot', 'response-log'];
  if (data.evidence_type && !validEvidenceTypes.includes(data.evidence_type)) {
    errors.push(`Invalid evidence_type '${data.evidence_type}'. Must be one of: ${validEvidenceTypes.join(', ')}`);
  }

  // --- Validate counts consistency ---
  if (Array.isArray(data.results)) {
    if (data.tests_total !== data.results.length) {
      errors.push(`tests_total (${data.tests_total}) !== results.length (${data.results.length})`);
    }

    const actualPassed = data.results.filter(r => r.status === 'PASS').length;
    const actualFailed = data.results.filter(r => r.status === 'FAIL').length;

    if (typeof data.tests_passed === 'number' && data.tests_passed !== actualPassed) {
      errors.push(`tests_passed (${data.tests_passed}) !== actual PASS count (${actualPassed})`);
    }
    if (typeof data.tests_failed === 'number' && data.tests_failed !== actualFailed) {
      errors.push(`tests_failed (${data.tests_failed}) !== actual FAIL count (${actualFailed})`);
    }

    const sum = (data.tests_passed || 0) + (data.tests_failed || 0);
    if (typeof data.tests_total === 'number' && sum !== data.tests_total) {
      errors.push(`tests_passed + tests_failed (${sum}) !== tests_total (${data.tests_total})`);
    }

    // --- Validate each result entry ---
    for (let i = 0; i < data.results.length; i++) {
      const r = data.results[i];
      const prefix = `results[${i}]`;

      if (!r.id || typeof r.id !== 'string') {
        errors.push(`${prefix}.id missing or not string`);
      } else if (!/^AC-\d+$/i.test(r.id)) {
        errors.push(`${prefix}.id '${r.id}' does not match AC-XX format`);
      }

      if (!r.scenario || typeof r.scenario !== 'string') {
        errors.push(`${prefix}.scenario missing or not string`);
      }

      if (!r.status || !['PASS', 'FAIL'].includes(r.status)) {
        errors.push(`${prefix}.status must be 'PASS' or 'FAIL', got '${r.status}'`);
      }

      if (typeof r.duration_ms !== 'number') {
        errors.push(`${prefix}.duration_ms must be number, got ${typeof r.duration_ms}`);
      }

      // evidence field must exist (can be null)
      if (!('evidence' in r)) {
        warnings.push(`${prefix}.evidence field missing (should be string or null)`);
      }

      // error field must exist (can be null)
      if (!('error' in r)) {
        warnings.push(`${prefix}.error field missing (should be string or null)`);
      }

      // --- Check evidence files exist (optional, with --check-evidence) ---
      if (checkEvidence && r.evidence) {
        const evidenceDir = path.dirname(filePath);
        const evidencePath = path.join(evidenceDir, r.evidence);
        if (!fs.existsSync(evidencePath)) {
          errors.push(`${prefix}.evidence file not found: ${r.evidence} (expected at ${evidencePath})`);
        }
      }
    }
  }

  // --- Check HTML report exists alongside results.json ---
  if (checkEvidence) {
    const htmlReport = path.join(path.dirname(filePath), 'e2e-evidence-report.html');
    if (!fs.existsSync(htmlReport)) {
      errors.push(`HTML Evidence Report not found: ${htmlReport}`);
    } else {
      const htmlContent = fs.readFileSync(htmlReport, 'utf-8');
      const htmlSize = Buffer.byteLength(htmlContent, 'utf-8');

      // Minimum size check — a valid report is at least 1KB
      if (htmlSize < 1024) {
        errors.push(`HTML Evidence Report too small (${htmlSize} bytes) — likely empty or placeholder`);
      }

      // Must be actual HTML
      if (!htmlContent.includes('<!DOCTYPE html') && !htmlContent.includes('<html')) {
        errors.push('HTML Evidence Report is not valid HTML (missing <!DOCTYPE html> or <html>)');
      }

      // Must contain UC reference
      if (data.uc_id && !htmlContent.includes(data.uc_id)) {
        errors.push(`HTML Evidence Report does not contain UC reference '${data.uc_id}'`);
      }

      // Must contain pass rate section (proves it's a real report, not fake)
      if (!htmlContent.includes('Pass Rate') && !htmlContent.includes('pass-rate')) {
        errors.push('HTML Evidence Report missing pass rate section — not a valid evidence report');
      }

      // Must contain at least one AC card
      if (!htmlContent.includes('AC-')) {
        errors.push('HTML Evidence Report contains no AC-XX references — no acceptance criteria evidenced');
      }

      // Screenshot evidence: must have actual base64 images embedded
      if (data.evidence_type === 'screenshot') {
        if (!htmlContent.includes('data:image/')) {
          errors.push('HTML report claims screenshot evidence but contains no embedded base64 images');
        }
      }

      // Response-log evidence: must have formatted JSON blocks
      if (data.evidence_type === 'response-log') {
        if (!htmlContent.includes('"status"') && !htmlContent.includes('&quot;status&quot;')) {
          warnings.push('HTML report claims response-log evidence but no JSON response blocks found');
        }
      }

      // Self-contained check: no external CSS/JS references
      if (htmlContent.includes('<link rel="stylesheet"') || htmlContent.includes('<script src=')) {
        warnings.push('HTML report has external dependencies — should be self-contained');
      }
    }
  }

  // --- Validate timestamp format ---
  if (data.timestamp && isNaN(Date.parse(data.timestamp))) {
    errors.push(`timestamp '${data.timestamp}' is not valid ISO 8601`);
  }

} catch (e) {
  if (e instanceof SyntaxError) {
    errors.push(`Invalid JSON: ${e.message}`);
  } else {
    errors.push(`Error reading file: ${e.message}`);
  }
}

// --- Output ---
if (errors.length > 0) {
  console.error(`VALIDATION FAILED: ${filePath}`);
  console.error(`  ${errors.length} error(s), ${warnings.length} warning(s)\n`);
  errors.forEach(e => console.error(`  ERROR: ${e}`));
  warnings.forEach(w => console.error(`  WARN:  ${w}`));
  process.exit(1);
} else {
  if (warnings.length > 0) {
    warnings.forEach(w => console.log(`  WARN: ${w}`));
  }
  console.log(`VALID: ${filePath}`);
  process.exit(0);
}
