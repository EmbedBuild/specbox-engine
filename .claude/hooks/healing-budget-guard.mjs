#!/usr/bin/env node
/**
 * healing-budget-guard.mjs — PreToolUse hook for Write/Edit during /implement healing
 * BLOCKING: Prevents the agent from exceeding the healing budget (max 8 attempts per feature).
 *
 * The healing budget is defined in GLOBAL_RULES.md as a HARD limit.
 * Previously this was instructional-only — the LLM had to count and stop.
 * Now this hook enforces it mechanically.
 *
 * v5.19.0 — Mechanical Enforcement
 */

import { readStdin, fileExists, readJsonFile } from './lib/utils.mjs';
import { printBlock } from './lib/output.mjs';
import { getActiveUC } from './lib/config.mjs';
import { readFileSync } from 'fs';

const MAX_HEALING_ATTEMPTS = 8;

const input = readStdin();

// Extract file path
let filePath = '';
try {
  const parsed = JSON.parse(input);
  filePath = parsed.file_path || '';
} catch {
  const match = input.match(/"file_path"\s*:\s*"([^"]*)"/);
  filePath = match ? match[1] : '';
}

if (!filePath) {
  process.exit(0);
}

// Only check source files (same pattern as spec-guard)
if (!/(^|\/)(?:src|lib)\//.test(filePath)) {
  process.exit(0);
}

// Skip tests, config, generated
if (/(test\/|tests\/|\.test\.|\.spec\.|_test\.dart|\.g\.dart|\.freezed\.dart|\.config\.|\.json$|\.yaml$|\.md$)/.test(filePath)) {
  process.exit(0);
}

// Get active UC to find feature name
const activeUC = getActiveUC();
if (!activeUC || !activeUC.feature) {
  // No active UC → other hooks handle this, not our concern
  process.exit(0);
}

const feature = activeUC.feature;
const healingLog = `.quality/evidence/${feature}/healing.jsonl`;

if (!fileExists(healingLog)) {
  // No healing events yet → allow
  process.exit(0);
}

// Count healing events
let healingCount = 0;
try {
  const content = readFileSync(healingLog, 'utf-8');
  const lines = content.trim().split('\n').filter(l => l.trim());
  healingCount = lines.length;
} catch {
  process.exit(0);
}

if (healingCount >= MAX_HEALING_ATTEMPTS) {
  printBlock('HEALING BUDGET EXCEEDED — Implementation BLOCKED', [
    `Feature: ${feature}`,
    `Healing attempts: ${healingCount} / ${MAX_HEALING_ATTEMPTS}`,
    `Log: ${healingLog}`,
    '',
    'The healing budget (max 8 attempts) has been exhausted.',
    'Continuing to retry will waste tokens without progress.',
    '',
    'REQUIRED ACTIONS:',
    '  1. STOP implementation immediately',
    '  2. Generate a healing report with the issues found',
    '  3. Report to the user: "Healing budget exceeded"',
    '  4. Let the user decide: manual fix, reset, or escalate',
    '',
    'This limit is NON-NEGOTIABLE. See GLOBAL_RULES.md.',
  ]);
  process.exit(1);
}

// Allow — budget not yet exhausted
process.exit(0);
