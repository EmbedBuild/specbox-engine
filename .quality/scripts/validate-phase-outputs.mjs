#!/usr/bin/env node
/**
 * validate-phase-outputs.mjs — zero-deps validator (v5.32.0).
 *
 * Usage:
 *   node .quality/scripts/validate-phase-outputs.mjs <path-to-jsonl>
 *
 * Exit codes:
 *   0  — every line valid
 *   1  — at least one line invalid (specific reasons to stderr)
 */

import { existsSync, readFileSync } from 'node:fs';

const REQUIRED = ['schema_version', 'phase', 'phase_index', 'agent', 'status'];
const ALLOWED = new Set([
  'schema_version',
  'ts',
  'phase',
  'phase_index',
  'agent',
  'task_id',
  'duration_s',
  'status',
  'files_created',
  'files_modified',
  'files_deleted',
  'summary',
  'tokens_used_prompt',
  'tokens_used_response',
  'healing_attempts',
  'error',
]);
const VALID_STATUSES = new Set(['ok', 'error', 'partial']);

const path = process.argv[2];
if (!path) {
  console.error('Usage: validate-phase-outputs.mjs <path-to-jsonl>');
  process.exit(1);
}
if (!existsSync(path)) {
  console.error(`File not found: ${path}`);
  process.exit(1);
}

const body = readFileSync(path, 'utf-8');
const lines = body.split('\n');
let invalid = 0;
let validCount = 0;

for (let i = 0; i < lines.length; i++) {
  const raw = lines[i].trim();
  if (!raw) continue;
  let obj;
  try {
    obj = JSON.parse(raw);
  } catch (err) {
    console.error(`L${i + 1}: invalid JSON — ${err.message}`);
    invalid++;
    continue;
  }
  const errors = validateEntry(obj);
  if (errors.length > 0) {
    console.error(`L${i + 1}: ${errors.join('; ')}`);
    invalid++;
  } else {
    validCount++;
  }
}

if (invalid > 0) {
  console.error(`\n${invalid} invalid lines (${validCount} valid)`);
  process.exit(1);
}
console.log(`${validCount} lines valid`);

// ── Validators ────────────────────────────────────────────────────────

function validateEntry(obj) {
  const errors = [];
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    return ['expected JSON object'];
  }
  for (const key of REQUIRED) {
    if (!(key in obj)) errors.push(`missing required field: ${key}`);
  }
  for (const key of Object.keys(obj)) {
    if (!ALLOWED.has(key)) errors.push(`unexpected field: ${key}`);
  }
  if (obj.schema_version !== 1) {
    errors.push(`unsupported schema_version: ${obj.schema_version}`);
  }
  if (typeof obj.phase !== 'string' || obj.phase.length === 0) {
    errors.push('phase must be a non-empty string');
  }
  if (!Number.isInteger(obj.phase_index) || obj.phase_index < 1) {
    errors.push('phase_index must be a positive integer');
  }
  if (typeof obj.agent !== 'string' || !/^AG-\d{2}[a-z]?$/.test(obj.agent)) {
    errors.push(`agent must match AG-XX[a-z]?, got ${JSON.stringify(obj.agent)}`);
  }
  if (typeof obj.status !== 'string' || !VALID_STATUSES.has(obj.status)) {
    errors.push(`status must be ok|error|partial, got ${JSON.stringify(obj.status)}`);
  }
  for (const arrField of ['files_created', 'files_modified', 'files_deleted']) {
    if (arrField in obj) {
      if (!Array.isArray(obj[arrField])) {
        errors.push(`${arrField} must be an array`);
      } else {
        for (const p of obj[arrField]) {
          if (typeof p !== 'string') {
            errors.push(`${arrField} contains non-string entry`);
            break;
          }
          if (p.startsWith('/')) {
            errors.push(`${arrField} contains absolute path: ${p}`);
            break;
          }
        }
      }
    }
  }
  if ('healing_attempts' in obj && !Number.isInteger(obj.healing_attempts)) {
    errors.push('healing_attempts must be an integer');
  }
  if ('duration_s' in obj && typeof obj.duration_s !== 'number') {
    errors.push('duration_s must be a number');
  }
  return errors;
}
