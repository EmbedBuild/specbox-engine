#!/usr/bin/env node
/**
 * implement-healing.mjs — Hook helper: logs self-healing event in evidence
 * Usage: node implement-healing.mjs <feature> <phase> <level> <action> [result]
 */

import { mkdir, now, appendLine } from './lib/utils.mjs';
import { join } from 'path';

const feature = process.argv[2] || '';
const phase = process.argv[3] || '';
const level = process.argv[4] || '';
const action = process.argv[5] || '';
const result = process.argv[6] || 'attempted';
const timestamp = now();

if (!feature || !phase || !level) {
  console.log('Usage: implement-healing.mjs <feature> <phase> <level> <action> [result]');
  process.exit(1);
}

const evidenceDir = `.quality/evidence/${feature}`;
mkdir(evidenceDir);

const entry = JSON.stringify({
  phase: Number(phase),
  level: Number(level),
  action,
  result,
  timestamp,
});

appendLine(join(evidenceDir, 'healing.jsonl'), entry);

console.log(`[HEALING] Level ${level} action logged for ${feature} phase ${phase}`);

// v6.1.0 Cloud Cutover: mcp-report.mjs no longer exists (UC-7204 removes the
// leftover dispatch). The healing event stays in .quality/evidence/ above.
